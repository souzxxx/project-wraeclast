import time

import httpx

from collector.http import RateLimiter, TTLCache


def test_ttl_cache_hit_and_expiry():
    cache = TTLCache()
    cache.set("k", 123, ttl_seconds=100)
    assert cache.get("k") == 123
    cache.set("k2", 1, ttl_seconds=-1)  # already expired
    assert cache.get("k2") is None
    assert cache.get("missing") is None


def test_rate_limiter_honors_retry_after():
    rl = RateLimiter()
    rl.observe(httpx.Headers({"retry-after": "2"}))
    assert rl._wait_until > time.monotonic()


def test_rate_limiter_backs_off_near_cap():
    rl = RateLimiter(safety_ratio=0.8)
    headers = httpx.Headers({
        "x-rate-limit-account": "100:60:60",
        "x-rate-limit-account-state": "90:60:0",
    })
    rl.observe(headers)
    assert rl._wait_until > time.monotonic()


def test_rate_limiter_idle_when_below_cap():
    rl = RateLimiter(safety_ratio=0.8)
    headers = httpx.Headers({
        "x-rate-limit-account": "100:60:60",
        "x-rate-limit-account-state": "10:60:0",
    })
    rl.observe(headers)
    assert rl._wait_until <= time.monotonic()
