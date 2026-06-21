"""Craft tab data — a pure projection of craft-lane knowledge chunks into guide cards.

The Craft tab surfaces the `topic='craft'` corpus as compact cards (title, source link, snippet).
Pure (no I/O) so the projection/truncation is unit-testable offline.
"""

from __future__ import annotations

from typing import Any

_SNIPPET_CHARS = 400


def craft_cards(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project craft knowledge rows into guide cards, skipping rows without a source or title."""
    cards: list[dict[str, Any]] = []
    for r in rows:
        url = r.get("source_url")
        title = r.get("title")
        if not url or not title:
            continue
        cards.append(
            {
                "source_url": url,
                "title": title,
                "snippet": (r.get("content") or "")[:_SNIPPET_CHARS].strip(),
            }
        )
    return cards
