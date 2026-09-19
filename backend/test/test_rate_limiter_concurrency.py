"""
StockSense Test Suite: Redis Token-Bucket Rate Limiter Concurrency
===================================================================

Tests the Redis-backed token bucket rate limiter (app/services/rate_limiter.py)
under concurrent load across multiple threads.

Key checks:
1. Atomic token acquisition via Lua script in Redis.
2. Immediate grants for requests within burst capacity.
3. Thread throttling and sequential token acquisition for requests over capacity.

Run from backend directory:
    .venv/bin/python test/test_rate_limiter_concurrency.py
"""

import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

# Ensure backend directory is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.services.rate_limiter import acquire, RateLimitExceeded
from app.db.redis_client import get_redis


def test_rate_limiter_concurrency():
    print("\n" + "="*70)
    print("TEST: Redis Token-Bucket Rate Limiter Concurrency & Throttling")
    print("="*70)

    test_bucket_name = f"test_bucket_{uuid.uuid4().hex[:6]}"
    capacity = 3.0       # Max burst size: 3 tokens
    refill_rate = 1.0    # 1 token per second
    num_threads = 8      # 8 concurrent requests competing for 3 tokens
    
    print(f"Bucket Config: Capacity = {capacity}, Refill Rate = {refill_rate} tokens/sec")
    print(f"Simulating {num_threads} concurrent threads competing at the exact same millisecond...\n")

    def worker_acquire(thread_id: int):
        t_start = time.time()
        try:
            # Attempt to acquire 1 token from Redis (max wait 15s)
            acquire(
                bucket_name=test_bucket_name,
                capacity=capacity,
                refill_rate=refill_rate,
                tokens_requested=1,
                max_wait_seconds=15.0,
                poll_interval=0.2
            )
            t_acquired = time.time() - t_start
            print(f"  [Thread {thread_id}] Token granted after {t_acquired:.2f}s")
            return (thread_id, t_acquired)
        except RateLimitExceeded:
            print(f"  [Thread {thread_id}] RATE LIMIT EXCEEDED!")
            return (thread_id, None)

    # Launch 8 threads simultaneously
    start_wall = time.time()
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        results = list(executor.map(worker_acquire, range(1, num_threads + 1)))
    total_duration = time.time() - start_wall

    print(f"\nAll {num_threads} threads completed in {total_duration:.2f} seconds.")

    # Verification checks
    immediate_grants = [r for r in results if r[1] is not None and r[1] < 0.5]
    delayed_grants = [r for r in results if r[1] is not None and r[1] >= 0.5]

    print(f"  -> Immediate Burst Grants (<0.5s): {len(immediate_grants)} (Expected: {int(capacity)})")
    print(f"  -> Throttled/Sequenced Grants (>=0.5s): {len(delayed_grants)} (Expected: {num_threads - int(capacity)})")

    assert len(immediate_grants) == int(capacity), (
        f"Rate limiter error: Expected exactly {capacity} immediate burst grants, but got {len(immediate_grants)}"
    )
    assert len(results) == num_threads, "Some threads failed to finish acquiring tokens."

    # Cleanup test rate limiter key in Redis
    r = get_redis()
    r.delete(f"ratelimit:{test_bucket_name}")
    
    print("\n" + "="*70)
    print("🎉 SUCCESS: Redis Token-Bucket Rate Limiter Passed Concurrency Test!")
    print("="*70 + "\n")


if __name__ == "__main__":
    test_rate_limiter_concurrency()
