import asyncio
import aiohttp
import async_timeout
import random
import time

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1  # 秒
# 新增变量以便统计信息
TOTAL_LIKES = 0
START_TIME = None


async def fetch_prompts(session, skip=0, limit=15):
    url = f'http://www.jasongjz.top:8000/api/v1/prompts/?skip={skip}&limit={limit}'
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN',
        'Connection': 'close',  # 关闭持久连接
        'Accept-Encoding': 'identity',  # 禁用压缩
        'Referer': 'http://www.jasongjz.top:8000/app/',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36'
    }
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with async_timeout.timeout(10):
                async with session.get(url, headers=headers, ssl=False) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    return [item['id'] for item in data]
        except Exception as e:
            if attempt == MAX_RETRIES:
                print(f"fetch_prompts 最终失败: {e}")
                return []  # 失败后返回空列表
            delay = RETRY_BASE_DELAY * (2 ** (attempt - 1)) + random.random()
            print(f"fetch_prompts 第 {attempt} 次失败: {e}，{delay:.1f}s 后重试")
            await asyncio.sleep(delay)


async def like_prompt(session, prompt_id):
    url = f'http://www.jasongjz.top:8000/api/v1/prompts/{prompt_id}/like'
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN',
        'Connection': 'close',
        'Accept-Encoding': 'identity',
        'Origin': 'http://www.jasongjz.top:8000',
        'Referer': 'http://www.jasongjz.top:8000/app/',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36'
    }
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with async_timeout.timeout(10):
                async with session.put(url, headers=headers, data=b'', ssl=False) as resp:
                    resp.raise_for_status()
                    return prompt_id, resp.status
        except Exception as e:
            if attempt == MAX_RETRIES:
                return prompt_id, e
            delay = RETRY_BASE_DELAY * (2 ** (attempt - 1)) + random.random()
            print(f"like_prompt {prompt_id} 第 {attempt} 次失败: {e}，{delay:.1f}s 后重试")
            await asyncio.sleep(delay)


async def main(concurrency=10, run_forever=True, like_delay=1.0, reuse_ids=True, batch_size=10, batch_interval=5.0):
    global TOTAL_LIKES, START_TIME
    START_TIME = time.time()
    connector = aiohttp.TCPConnector(force_close=True, limit=0)
    timeout = aiohttp.ClientTimeout(total=60)

    print(
        f"开始稳定点赞操作 (并发: {concurrency}, 点赞间隔: {like_delay}秒, 批次大小: {batch_size}, 批次间隔: {batch_interval}秒)")

    # 预先获取一批prompt_ids
    all_prompt_ids = []
    original_ids = []  # 保存原始ID列表用于重复使用
    page_size = 100  # 再次增加批量获取数量

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # 预先加载多页数据
        for skip in range(0, 500, page_size):
            ids = await fetch_prompts(session, skip=skip, limit=page_size)
            if ids:
                all_prompt_ids.extend(ids)
                original_ids.extend(ids)
                print(f"预加载: 获取第 {skip}-{skip + page_size} 个prompt，共 {len(ids)} 个")
            else:
                break

        if not all_prompt_ids:
            print("无法获取任何prompts，退出")
            return

        print(f"预加载完成，共获取 {len(all_prompt_ids)} 个prompt ID")

        # 主循环
        while True:
            try:
                # 如果ID用完，直接重用已有ID而不重新获取
                if not all_prompt_ids:
                    if reuse_ids and original_ids:
                        print("ID列表已用完，重用已有ID")
                        all_prompt_ids = original_ids.copy()
                        random.shuffle(all_prompt_ids)  # 随机打乱顺序
                    else:
                        print("ID列表已用完，重新获取")
                        for skip in range(0, 500, page_size):
                            ids = await fetch_prompts(session, skip=skip, limit=page_size)
                            if ids:
                                all_prompt_ids.extend(ids)
                                if not original_ids:  # 如果原始列表为空，则保存
                                    original_ids.extend(ids)
                            else:
                                break

                # 无法获取任何ID时暂停一下
                if not all_prompt_ids:
                    print("无法获取任何ID，等待5秒后重试")
                    await asyncio.sleep(5)
                    continue

                # 取出一批ID处理，使用固定的批次大小
                current_batch_size = min(batch_size, len(all_prompt_ids))
                batch_ids = all_prompt_ids[:current_batch_size]
                all_prompt_ids = all_prompt_ids[current_batch_size:]

                # 处理当前批次
                sem = asyncio.Semaphore(concurrency)
                tasks = []

                for pid in batch_ids:
                    async def process_id(p_id):
                        async with sem:
                            if like_delay > 0:
                                await asyncio.sleep(like_delay)
                            return await like_prompt(session, p_id)

                    tasks.append(asyncio.create_task(process_id(pid)))

                # 等待当前批次完成
                results = await asyncio.gather(*tasks)

                success_count = 0
                for pid, status in results:
                    if not isinstance(status, Exception):
                        success_count += 1
                        TOTAL_LIKES += 1

                # 显示统计信息
                elapsed = time.time() - START_TIME
                rate = TOTAL_LIKES / elapsed if elapsed > 0 else 0
                print(
                    f"批次完成: 成功 {success_count}/{len(batch_ids)}, 总计: {TOTAL_LIKES}, 运行: {elapsed:.1f}秒, 速率: {rate:.2f}次/秒")

                if not run_forever:
                    break

                # 在批次之间添加间隔，确保服务器有时间处理和恢复
                print(f"等待 {batch_interval} 秒后继续下一批...")
                await asyncio.sleep(batch_interval)

            except Exception as e:
                print(f"主循环错误: {e}，5秒后重试")
                await asyncio.sleep(5)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="稳定点赞脚本")
    parser.add_argument('--concurrency', type=int, default=10, help="并发请求数")
    parser.add_argument('--once', action='store_true', help="只运行一次不循环")
    parser.add_argument('--delay', type=float, default=1.0, help="每个请求间隔(秒)")
    parser.add_argument('--batch-size', type=int, default=10, help="每批处理的点赞数量")
    parser.add_argument('--batch-interval', type=float, default=0.1, help="批次之间的间隔(秒)")
    parser.add_argument('--no-reuse', action='store_true', help="不重复使用已获取的ID")
    args = parser.parse_args()

    try:
        asyncio.run(main(
            concurrency=args.concurrency,
            run_forever=not args.once,
            like_delay=args.delay,
            reuse_ids=not args.no_reuse,
            batch_size=args.batch_size,
            batch_interval=args.batch_interval
        ))
    except KeyboardInterrupt:
        elapsed = time.time() - START_TIME if START_TIME else 0
        rate = TOTAL_LIKES / elapsed if elapsed > 0 else 0
        print(f"\n程序被终止。总共点赞: {TOTAL_LIKES}, 总运行时间: {elapsed:.1f}秒, 平均速率: {rate:.2f}次/秒")
