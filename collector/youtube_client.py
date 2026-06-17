"""YouTube Data API v3 collector — primary automatic farming-knowledge source.

Official API, free tier. For each configured query we search.list (100 quota units) to get
video IDs, then videos.list (1 unit) to get the FULL description (search snippets are
truncated to ~150 chars; guide descriptions hold the actual strategy + timestamps).

Treated as qualitative knowledge (skill §3): titles + descriptions -> knowledge_chunk.

CLI:
    python -m collector.youtube_client explore   # dump a sample search result
    python -m collector.youtube_client run        # search + ingest into knowledge_chunk
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from collector.config import Settings, get_settings
from collector.http import HttpClient
from collector.ingest import KnowledgeDoc

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
UA = "Project-Wraeclast/0.1 (contact: souzxxx)"


def parse_search_ids(payload: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for item in payload.get("items", []) or []:
        vid = (item.get("id") or {}).get("videoId")
        if vid:
            ids.append(vid)
    return ids


def videos_to_docs(payload: dict[str, Any]) -> list[KnowledgeDoc]:
    """Map a videos.list response to KnowledgeDocs (title + full description)."""
    docs: list[KnowledgeDoc] = []
    for item in payload.get("items", []) or []:
        vid = item.get("id")
        sn = item.get("snippet") or {}
        title = sn.get("title") or ""
        desc = sn.get("description") or ""
        channel = sn.get("channelTitle") or ""
        if not vid or not title:
            continue
        content = f"YouTube guide by {channel}: {title}\n\n{desc}".strip()
        docs.append(
            KnowledgeDoc(
                source_url=f"https://www.youtube.com/watch?v={vid}", title=title, content=content
            )
        )
    return docs


async def fetch_youtube(settings: Settings | None = None) -> list[KnowledgeDoc]:
    settings = settings or get_settings()
    if not settings.youtube_api_key:
        return []
    published_after = (
        datetime.now(UTC) - timedelta(days=settings.youtube_published_days)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    seen: set[str] = set()
    all_ids: list[str] = []
    async with HttpClient(UA) as http:
        for query in settings.youtube_query_list:
            try:
                search = await http.get_json(
                    SEARCH_URL,
                    params={
                        "key": settings.youtube_api_key,
                        "part": "snippet",
                        "q": query,
                        "type": "video",
                        "order": "relevance",
                        "relevanceLanguage": "en",
                        "maxResults": settings.youtube_max_results,
                        "publishedAfter": published_after,
                    },
                    cache_ttl=3600,
                )
            except Exception:  # noqa: BLE001 — one bad query shouldn't kill the run
                continue
            for vid in parse_search_ids(search):
                if vid not in seen:
                    seen.add(vid)
                    all_ids.append(vid)

        docs: list[KnowledgeDoc] = []
        for i in range(0, len(all_ids), 50):  # videos.list accepts up to 50 ids
            batch = all_ids[i : i + 50]
            data = await http.get_json(
                VIDEOS_URL,
                params={"key": settings.youtube_api_key, "part": "snippet", "id": ",".join(batch)},
                cache_ttl=3600,
            )
            docs += videos_to_docs(data)
    return docs


async def run() -> int:
    from collector.ingest import ingest_documents

    docs = await fetch_youtube()
    n = ingest_documents(docs)
    print(f"knowledge_chunk: ingested {n} YouTube guides")
    return n


async def explore() -> None:
    settings = get_settings()
    async with HttpClient(UA) as http:
        data = await http.get_json(
            SEARCH_URL,
            params={
                "key": settings.youtube_api_key,
                "part": "snippet",
                "q": settings.youtube_query_list[0],
                "type": "video",
                "maxResults": 3,
            },
        )
    print(json.dumps([i["snippet"]["title"] for i in data.get("items", [])], indent=2))


def _main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "run"
    if cmd == "explore":
        asyncio.run(explore())
        return 0
    if cmd == "run":
        asyncio.run(run())
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
