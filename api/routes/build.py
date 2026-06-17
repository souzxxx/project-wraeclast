"""GET /build — diff of the owner's character vs a popular/meta build."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from api.build_diff import compute_build_diff

router = APIRouter(prefix="/build", tags=["build"])


@router.get("")
def get_build_diff() -> dict[str, Any]:
    from db.repo import latest_my_snapshot

    mine = latest_my_snapshot()
    if not mine:
        raise HTTPException(
            status_code=404,
            detail="No character snapshot yet. Run ninja_build_client (or supply a PoB code).",
        )
    # Phase 0: a popular/meta build snapshot collector isn't wired yet, so meta is None and
    # the diff degrades gracefully (returns the owner's gems + a 'not comparable' note).
    meta = _load_meta_build(mine.get("char_class"))
    return compute_build_diff(mine, meta)


def _load_meta_build(char_class: str | None) -> dict[str, Any] | None:
    """Placeholder for the popular-build source. Returns None until wired (graceful degrade)."""
    return None
