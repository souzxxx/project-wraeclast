"""Shared async HTTP layer: descriptive User-Agent, TTL cache, and a rate limiter
that honors GGG's `x-rate-limit-*` headers (exceeding them = temporary ban).

See skill `poe2-data-collection` sections 1 and 2 for the rules encoded here.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

DEFAULT_TIMEOUT = httpx.Timeout(20.0, connect=10.0)


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class TTLCache:
    """Tiny in-process TTL cache. poe.ninja is a daily snapshot — don't hammer it."""

    def __init__(self) -> None:
        self._store: dict[str, _CacheEntry] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.expires_at < time.monotonic():
            self._store.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        self._store[key] = _CacheEntry(value=value, expires_at=time.monotonic() + ttl_seconds)


@dataclass
class RateLimiter:
    """Honors GGG-style `x-rate-limit-*` headers.

    GGG returns policy lines like `x-rate-limit-account: 60:60:60` and current state
    `x-rate-limit-account-state: 30:60:0`. When usage approaches the cap we sleep until
    the window rolls over. A `Retry-After` header always wins.
    """

    safety_ratio: float = 0.85
    _wait_until: float = field(default=0.0)

    async def before_request(self) -> None:
        now = time.monotonic()
        if self._wait_until > now:
            await asyncio.sleep(self._wait_until - now)

    def observe(self, headers: httpx.Headers) -> None:
        retry_after = headers.get("retry-after")
        if retry_after:
            try:
                self._wait_until = max(self._wait_until, time.monotonic() + float(retry_after))
                return
            except ValueError:
                pass

        # Parse `<name>-state` headers; format "used:window_seconds:restricted_seconds".
        for key, value in headers.items():
            if not key.lower().endswith("-state"):
                continue
            for rule in value.split(","):
                parts = rule.split(":")
                if len(parts) != 3:
                    continue
                try:
                    used, window, restricted = (int(p) for p in parts)
                except ValueError:
                    continue
                if restricted > 0:
                    self._wait_until = max(self._wait_until, time.monotonic() + restricted)
                # Match the policy line to learn the cap, then back off near it.
                policy = headers.get(key.lower().replace("-state", ""))
                if policy:
                    try:
                        cap = int(policy.split(",")[0].split(":")[0])
                    except (ValueError, IndexError):
                        cap = 0
                    if cap and used >= cap * self.safety_ratio:
                        self._wait_until = max(self._wait_until, time.monotonic() + window)


class HttpClient:
    """Thin wrapper over httpx.AsyncClient adding UA, caching and rate limiting."""

    def __init__(
        self,
        user_agent: str,
        *,
        base_url: str = "",
        cache: TTLCache | None = None,
        rate_limiter: RateLimiter | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        merged = {"User-Agent": user_agent, "Accept": "application/json"}
        if headers:
            merged.update(headers)
        self._client = httpx.AsyncClient(
            base_url=base_url, headers=merged, timeout=DEFAULT_TIMEOUT, follow_redirects=True
        )
        self._cache = cache or TTLCache()
        self._rl = rate_limiter or RateLimiter()

    async def get_json(
        self, url: str, *, params: dict[str, Any] | None = None, cache_ttl: float = 0
    ) -> Any:
        cache_key = f"GET {url} {json.dumps(params, sort_keys=True)}" if cache_ttl else ""
        if cache_key:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        await self._rl.before_request()
        resp = await self._client.get(url, params=params)
        self._rl.observe(resp.headers)
        resp.raise_for_status()
        data = resp.json()

        if cache_key:
            self._cache.set(cache_key, data, cache_ttl)
        return data

    async def post_json(
        self, url: str, *, json_body: dict[str, Any] | None = None
    ) -> Any:
        await self._rl.before_request()
        resp = await self._client.post(url, json=json_body)
        self._rl.observe(resp.headers)
        resp.raise_for_status()
        return resp.json()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> HttpClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()
