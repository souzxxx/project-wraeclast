"""Deterministic source citation for LLM guides — make `sources` carry REAL chunk URLs.

The generators feed the community knowledge to the LLM and ask it which entries it used. Rather
than have the model reproduce a URL verbatim (it can't — the watch URL is never a stable token it
sees), each knowledge entry is numbered `[n]` in the prompt and the model cites the numbers it
used (`source_refs`). We resolve those numbers back to the chunk's real `source_url` HERE, so the
stored `sources` are the actual chunk URLs — which is exactly what the query-productivity analyzer
(`collector.query_stats`) crosses against `knowledge_chunk.discovery_query` attribution.

This mirrors the `craft_guides` method-id pattern (LLM echoes `m0`/`m1`; we attach the numbers).
"""

from __future__ import annotations

import re
from typing import Any


def number_knowledge(
    knowledge: list[dict[str, Any]], content_chars: int = 700
) -> tuple[str, list[dict[str, str]]]:
    """Render knowledge as numbered prompt lines `[n] label: content` and return the ordinal→source
    map (1-based index n → {url, title}) so the model can cite a source by its number.

    The label falls back to the source_url when a title is missing, but the ref map always carries
    the real `source_url` so resolution stays correct regardless of the label shown.
    """
    lines: list[str] = []
    ref_map: list[dict[str, str]] = []
    for i, x in enumerate(knowledge, 1):
        title = (x.get("title") or "").strip()
        url = (x.get("source_url") or "").strip()
        label = title or url
        content = (x.get("content") or "")[:content_chars]
        lines.append(f"[{i}] {label}: {content}")
        ref_map.append({"url": url, "title": title})
    return "\n".join(lines), ref_map


def _coerce_ref(value: Any) -> int | None:
    """Pull a 1-based reference number from an int / float / numeric string; None otherwise."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        m = re.search(r"\d+", value)
        return int(m.group()) if m else None
    return None


def resolve_source_refs(refs: Any, ref_map: list[dict[str, str]]) -> list[dict[str, str]]:
    """Map LLM-emitted 1-based reference numbers back to real `{url, title}` from `ref_map`.

    Tolerant: accepts ints or numeric strings, ignores out-of-range/zero/negative/duplicate refs,
    preserves citation order, and drops entries that have no url.
    """
    if not isinstance(refs, list):
        return []
    out: list[dict[str, str]] = []
    seen: set[int] = set()
    for r in refs:
        n = _coerce_ref(r)
        if n is None or n < 1 or n > len(ref_map) or n in seen:
            continue
        seen.add(n)
        entry = ref_map[n - 1]
        if entry.get("url"):
            out.append({"url": entry["url"], "title": entry.get("title", "")})
    return out
