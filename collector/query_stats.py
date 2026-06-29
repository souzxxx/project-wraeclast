"""YouTube query-productivity analyzer — make `youtube_queries` data-driven, not guesswork.

Each knowledge chunk records the search query that first surfaced it (`discovery_query`, see
migration 0009). Crossing that attribution with the URLs actually CITED in the generated guides
(farm + craft) and strategies tells us which queries earn their quota and which are dead weight:

    productivity(query) = chunks it discovered that ended up cited in a guide / chunks discovered

The pure core (`score_queries` / `render_report`) is offline-tested; the `run` CLI wires the live
DB reads and prints a markdown report the owner uses to tighten `YOUTUBE_QUERIES`.

CLI:
    python -m collector.query_stats        # print the productivity report
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel


class QueryStat(BaseModel):
    """Productivity of a single search query over the accumulated corpus."""

    query: str
    configured: bool  # still present in the current YOUTUBE_QUERIES config
    discovered: int  # chunks this query first surfaced
    cited: int  # of those, how many are cited in a guide/strategy
    citation_rate: float  # cited / discovered (0.0 when nothing discovered)
    drop_candidate: bool  # configured but earning no citations — a tightening candidate


def collect_cited_urls(*source_lists: Iterable[dict[str, Any]]) -> set[str]:
    """Flatten guide/strategy `sources` (each `[{"url","title"}, …]`) into a set of cited URLs."""
    urls: set[str] = set()
    for sources in source_lists:
        for src in sources or []:
            url = (src.get("url") or "").strip() if isinstance(src, dict) else ""
            if url:
                urls.add(url)
    return urls


def score_queries(
    configured_queries: Iterable[str],
    attribution: Iterable[dict[str, Any]],
    cited_urls: set[str],
) -> list[QueryStat]:
    """Rank every query by how many of its discovered chunks got cited.

    `attribution`: chunks as `{source_url, discovery_query}` (repo.knowledge_query_attribution).
    `cited_urls`: URLs referenced by the generated guides/strategies (collect_cited_urls).

    Covers both configured queries (so a dead one shows up even with zero chunks) and any query
    found only in historical data (drift after a config edit), so nothing is silently invisible.
    """
    configured = [q.strip() for q in configured_queries if q and q.strip()]
    configured_set = set(configured)

    discovered: dict[str, int] = {}
    cited: dict[str, int] = {}
    for row in attribution:
        query = (row.get("discovery_query") or "").strip()
        if not query:
            continue
        discovered[query] = discovered.get(query, 0) + 1
        url = (row.get("source_url") or "").strip()
        if url and url in cited_urls:
            cited[query] = cited.get(query, 0) + 1

    stats: list[QueryStat] = []
    for query in configured_set | set(discovered):
        d = discovered.get(query, 0)
        c = cited.get(query, 0)
        is_configured = query in configured_set
        stats.append(
            QueryStat(
                query=query,
                configured=is_configured,
                discovered=d,
                cited=c,
                citation_rate=(c / d) if d else 0.0,
                # only flag queries we still pay quota for; drift queries are reported, not flagged
                drop_candidate=is_configured and c == 0,
            )
        )

    # most productive first; ties broken by reach, then name for deterministic output
    stats.sort(key=lambda s: (-s.cited, -s.discovered, s.query))
    return stats


def render_report(stats: list[QueryStat]) -> str:
    """Markdown report: a productivity table + an explicit list of drop candidates and drift."""
    lines = ["# YouTube query productivity", ""]
    if not stats:
        lines.append("_No query-attributed knowledge yet — run the daily collection first._")
        return "\n".join(lines)

    lines += ["| query | cited | discovered | rate | status |", "|---|---|---|---|---|"]
    for s in stats:
        if not s.configured:
            status = "drift (not in config)"
        elif s.drop_candidate:
            status = "⚠️ drop candidate"
        else:
            status = "keep"
        lines.append(
            f"| {s.query} | {s.cited} | {s.discovered} | {s.citation_rate:.0%} | {status} |"
        )

    drops = [s.query for s in stats if s.drop_candidate]
    lines += ["", "## Drop candidates (configured, zero citations)"]
    lines.append(
        "- " + "\n- ".join(drops) if drops else "_None — every configured query pays off._"
    )

    drift = [s.query for s in stats if not s.configured]
    if drift:
        lines += ["", "## Drift (cited history, no longer configured)", "- " + "\n- ".join(drift)]
    return "\n".join(lines)


def build_report() -> str:
    """Live path: pull config + attribution + cited URLs from the DB and render the report."""
    from collector.config import get_settings
    from db import repo

    settings = get_settings()
    cited = collect_cited_urls(
        *[g.get("sources", []) for g in repo.latest_farm_guides(settings.poe2_league)],
        *[g.get("sources", []) for g in repo.latest_craft_guides(settings.poe2_league)],
        *[s.get("sources", []) for s in repo.latest_farm_strategies(settings.poe2_league)],
    )
    stats = score_queries(
        settings.youtube_query_list, repo.knowledge_query_attribution(), cited
    )
    return render_report(stats)


def _main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "run"
    if cmd == "run":
        print(build_report())
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
