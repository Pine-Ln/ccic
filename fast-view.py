"""
异步curl请求器 - 持续发送HTTP请求到指定URL
"""
import asyncio
import aiohttp
import time
import argparse
import logging
from logging.handlers import RotatingFileHandler
import sys
import os
import signal

# 全局变量
TOTAL_REQUESTS = 0
START_TIME = None
RUNNING = True
stats_lock = asyncio.Lock()
logger = None

# 配置日志系统
def setup_logger(log_level=logging.INFO, log_file=None, max_size=5*1024*1024, backup_count=3):
    """设置日志系统"""
    logger = logging.getLogger("curl-requester")
    logger.setLevel(log_level)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s', 
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 如果指定了日志文件，添加文件处理器
    if log_file:
        # 使用 RotatingFileHandler 自动滚动日志文件
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=max_size, 
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

async def send_request(session, url, headers, ssl=False, timeout=10, retry_count=3, retry_delay=1):
    """异步发送单个HTTP请求"""
    global TOTAL_REQUESTS
    
    for attempt in range(retry_count):
        try:
            # 使用更短的单次请求超时
            request_timeout = aiohttp.ClientTimeout(total=timeout)
            async with session.get(url, headers=headers, ssl=ssl, timeout=request_timeout) as response:
                # 读取响应内容但不处理
                _ = await response.read()
                
                # 成功发送请求，更新统计信息
                async with stats_lock:
                    global TOTAL_REQUESTS
                    TOTAL_REQUESTS += 1
                    
                return response.status
        except (aiohttp.ClientError, asyncio.TimeoutError, asyncio.CancelledError) as e:
            error_type = type(e).__name__
            if attempt < retry_count - 1:
                logger.debug(f"请求失败 (尝试 {attempt+1}/{retry_count}): {error_type}: {str(e)}, {retry_delay}秒后重试")
                await asyncio.sleep(retry_delay)
            else:
                logger.debug(f"请求失败: {error_type}: {str(e)}")
                return None
        except Exception as e:
            # 捕获所有其他异常
            error_type = type(e).__name__
            logger.error(f"未预期的错误: {error_type}: {str(e)}")
            if attempt < retry_count - 1:
                logger.debug(f"{retry_delay}秒后重试")
                await asyncio.sleep(retry_delay)
            else:
                return None

async def worker(session, url, headers, ssl, delay, timeout, retry_count, retry_delay):
    """工作协程，持续发送请求"""
    global RUNNING
    
    while RUNNING:
        status = await send_request(session, url, headers, ssl, timeout, retry_count, retry_delay)
        if status:
            logger.debug(f"请求成功，状态码: {status}")
        
        # 如果设置了延迟，则等待
        if delay > 0:
            await asyncio.sleep(delay)

async def stats_reporter(interval=5):
    """定期报告统计信息的协程"""
    global TOTAL_REQUESTS, START_TIME, RUNNING
    
    last_count = 0
    last_time = time.time()
    
    while RUNNING:
        await asyncio.sleep(interval)
        current_time = time.time()
        elapsed = current_time - START_TIME
        current_count = TOTAL_REQUESTS
        
        # 计算总体和当前间隔的速率
        total_rate = current_count / elapsed if elapsed > 0 else 0
        interval_count = current_count - last_count
        interval_time = current_time - last_time
        interval_rate = interval_count / interval_time if interval_time > 0 else 0
        
        logger.info(
            f"已发送: {current_count} 请求, "
            f"运行时间: {elapsed:.1f}s, "
            f"总体速率: {total_rate:.2f}次/秒, "
            f"当前速率: {interval_rate:.2f}次/秒"
        )
        
        last_count = current_count
        last_time = current_time

def handle_interrupt(signum, frame):
    """处理中断信号"""
    global RUNNING
    logger.info("收到中断信号，正在停止...")
    RUNNING = False

async def main_async(args):
    global logger, START_TIME, RUNNING
    
    # 设置日志系统
    log_level = getattr(logging, args.log_level)
    global logger
    logger = setup_logger(log_level=log_level, log_file=args.log_file)
    
    # 默认头信息
    headers = {
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "DNT": "1",
        "Proxy-Connection": "keep-alive",
        "Referer": "http://www.jasongjz.top:8000/app/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0"
    }
    
    # 初始化全局统计信息
    global START_TIME
    START_TIME = time.time()
      # 创建连接池
    connector = aiohttp.TCPConnector(
        force_close=True,  # 每次请求后关闭连接
        limit=0,           # 不限制并发连接数
        ssl=(not args.no_verify_ssl)  # 如果选择不验证SSL，则ssl=False
    )
    
    timeout = aiohttp.ClientTimeout(total=args.timeout)
    
    logger.info(f"开始异步请求 (URL: {args.url}, 并发数: {args.concurrency}, 请求间隔: {args.delay}秒)")
    
    # 启动统计报告协程
    stats_task = asyncio.create_task(stats_reporter(args.stats_interval))
    
    # 创建客户端会话
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # 创建工作协程
        tasks = []
        for _ in range(args.concurrency):
            task = asyncio.create_task(
                worker(
                    session, args.url, headers, 
                    not args.no_verify_ssl, args.delay, 
                    args.timeout, args.retry, args.retry_delay
                )
            )
            tasks.append(task)
        
        # 等待中断信号
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("任务被取消")
            
    # 取消统计报告协程
    stats_task.cancel()
    
    # 计算最终统计信息
    elapsed = time.time() - START_TIME
    rate = TOTAL_REQUESTS / elapsed if elapsed > 0 else 0
    logger.info(f"程序终止。总共发送请求: {TOTAL_REQUESTS}, 总运行时间: {elapsed:.1f}秒, 平均速率: {rate:.2f}次/秒")

def main():
    # 参数解析
    parser = argparse.ArgumentParser(description="异步持续发送HTTP请求")
    parser.add_argument('--url', type=str, default="http://www.jasongjz.top:8000/api/v1/prompts/3", help="请求的URL")
    parser.add_argument('--concurrency', type=int, default=100, help="并发请求数")
    parser.add_argument('--delay', type=float, default=0.01, help="每个请求的间隔(秒)")
    parser.add_argument('--timeout', type=float, default=10.0, help="请求超时时间(秒)")
    parser.add_argument('--retry', type=int, default=3, help="请求失败后的重试次数")
    parser.add_argument('--retry-delay', type=float, default=1.0, help="重试间隔(秒)")
    parser.add_argument('--stats-interval', type=float, default=5.0, help="统计报告间隔(秒)")
    parser.add_argument('--no-verify-ssl', action='store_true', help="不验证SSL证书")
    parser.add_argument('--tcp-nodelay', action='store_true', help="启用TCP_NODELAY选项")
    parser.add_argument('--ttl-dns-cache', type=int, default=10, help="DNS缓存存活时间(秒)")
    parser.add_argument('--log-level', type=str, default='INFO', 
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help="日志级别")
    parser.add_argument('--log-file', type=str, help="日志文件路径")
    args = parser.parse_args()
    
    # 设置信号处理
    signal.signal(signal.SIGINT, handle_interrupt)
    signal.signal(signal.SIGTERM, handle_interrupt)
    
    # 运行异步主函数
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        # 中断信号已经由信号处理函数处理
        pass

if __name__ == "__main__":
    main()
