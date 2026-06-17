"""Community scraper (skill §3): recent, high-signal Reddit posts about PoE2.

Everything collected here is QUALITATIVE context for RAG — never a source of numbers.
Filters by minimum score + recency, dedups by URL. Uses Reddit's public `.json` endpoint
(no auth) by default; a registered app could swap in oauth.reddit.com later.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from collector.config import Settings, get_settings
from collector.http import HttpClient


@dataclass
class CommunityPost:
    url: str
    title: str
    content: str
    score: int
    created_utc: float


def _select(posts: list[CommunityPost], min_score: int, max_age_days: int) -> list[CommunityPost]:
    cutoff = time.time() - max_age_days * 86400
    seen: set[str] = set()
    out: list[CommunityPost] = []
    for p in sorted(posts, key=lambda x: x.score, reverse=True):
        if p.score < min_score or p.created_utc < cutoff or p.url in seen:
            continue
        seen.add(p.url)
        out.append(p)
    return out


def parse_listing(payload: dict[str, Any]) -> list[CommunityPost]:
    """Defensive parse of a Reddit listing JSON into CommunityPost objects."""
    posts: list[CommunityPost] = []
    children = (payload.get("data") or {}).get("children") or []
    for child in children:
        d = child.get("data") or {}
        permalink = d.get("permalink")
        if not permalink:
            continue
        body = d.get("selftext") or ""
        title = d.get("title") or ""
        posts.append(
            CommunityPost(
                url=f"https://www.reddit.com{permalink}",
                title=title,
                content=f"{title}\n\n{body}".strip(),
                score=int(d.get("score") or 0),
                created_utc=float(d.get("created_utc") or 0.0),
            )
        )
    return posts


async def fetch_community(settings: Settings | None = None) -> list[CommunityPost]:
    settings = settings or get_settings()
    url = f"https://www.reddit.com/r/{settings.reddit_subreddit}/top.json"
    async with HttpClient(settings.reddit_user_agent) as http:
        payload = await http.get_json(
            url, params={"t": "week", "limit": 50}, cache_ttl=3600
        )
    posts = parse_listing(payload)
    return _select(posts, settings.scraper_min_score, settings.scraper_max_age_days)


async def run() -> int:
    """Fetch + ingest (embed + write knowledge_chunk)."""
    from collector.ingest import ingest_posts

    posts = await fetch_community()
    n = ingest_posts(posts)
    print(f"knowledge_chunk: ingested {n} community posts")
    return n


if __name__ == "__main__":
    raise SystemExit(0 if asyncio.run(run()) >= 0 else 1)
