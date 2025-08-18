#!/usr/bin/env python3
"""
Quick test: connect to Redis server at redis://localhost:6379
Run with: python -u tests/test_redis_connection.py
"""
import sys
import os
import asyncio

# Ensure project root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.services.redis_message_queue import RedisMessageQueue, RedisConfig

async def main():
    url = os.getenv("REDIS_URL", "redis://localhost:6379")
    cfg = RedisConfig(url=url)
    queue = RedisMessageQueue(config=cfg)

    try:
        print(f"🔌 Attempting to connect to Redis at {cfg.url}...")
        await queue.setup()
        print("✅ Connected to Redis (ping successful)")

        info = await queue.get_stream_info()
        print("ℹ️  Stream info (truncated):")
        if isinstance(info, dict):
            for k in list(info.keys())[:10]:
                print(f"  - {k}")
        else:
            print(info)

        queue.close()
        return 0

    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return 2

if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
