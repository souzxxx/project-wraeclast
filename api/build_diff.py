"""Pure build-diff logic: owner character vs a popular/meta build.

Kept pure (no I/O) so it's unit-testable. Compares gem/skill sets and level; the route
feeds it the owner's my_snapshot and a meta reference (popular ninja build). Relevant with
the ~200 new gems in 0.5.0 — the diff surfaces what to swap.
"""

from __future__ import annotations

from typing import Any


def _gem_names(snapshot: dict[str, Any]) -> set[str]:
    gems = snapshot.get("gems") or []
    names: set[str] = set()
    for g in gems:
        if isinstance(g, dict):
            name = g.get("name")
            if name:
                names.add(str(name).strip())
        elif isinstance(g, str):
            names.add(g.strip())
    return {n for n in names if n}


def compute_build_diff(mine: dict[str, Any], meta: dict[str, Any] | None) -> dict[str, Any]:
    """Return gems to consider adding (in meta, not mine) and cutting (mine, not meta)."""
    my_gems = _gem_names(mine)
    if not meta:
        return {
            "comparable": False,
            "reason": "No meta/popular build available yet (need a ninja popular build snapshot).",
            "my_gems": sorted(my_gems),
            "my_level": mine.get("level"),
            "my_class": mine.get("char_class"),
        }
    meta_gems = _gem_names(meta)
    return {
        "comparable": True,
        "my_class": mine.get("char_class"),
        "my_level": mine.get("level"),
        "meta_class": meta.get("char_class"),
        "consider_adding": sorted(meta_gems - my_gems),
        "consider_cutting": sorted(my_gems - meta_gems),
        "shared": sorted(my_gems & meta_gems),
    }
