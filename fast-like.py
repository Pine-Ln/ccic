import asyncio
import aiohttp
import async_timeout
import random

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1  # 秒

async def fetch_prompts(session, skip=0, limit=15):
    url = f'http://www.jasongjz.top:8000/api/v1/prompts/?skip={skip}&limit={limit}'
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN',
        'Connection': 'close',               # 关闭持久连接
        'Accept-Encoding': 'identity',       # 禁用压缩
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

async def main(concurrency=5):
    connector = aiohttp.TCPConnector(force_close=True, limit=0, keepalive_timeout=0)
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        prompt_ids = await fetch_prompts(session)
        if not prompt_ids:
            print("没有获取到任何 prompts，退出。")
            return

        print(f"Fetched prompt IDs: {prompt_ids}")

        sem = asyncio.Semaphore(concurrency)
        async def sem_like(pid):
            async with sem:
                return await like_prompt(session, pid)

        tasks = [sem_like(pid) for pid in prompt_ids]
        results = await asyncio.gather(*tasks)

        for pid, status in results:
            if isinstance(status, Exception):
                print(f"Prompt {pid} 最终失败: {status}")
            else:
                print(f"Prompt {pid} liked, status {status}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="快速点赞脚本（强化版）")
    parser.add_argument('--concurrency', type=int, default=5, help="并发请求数")
    args = parser.parse_args()

    asyncio.run(main(concurrency=args.concurrency))
