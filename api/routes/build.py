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
    # Compare against the popular/meta build for the owner's class (collected by
    # ninja_meta_client). Still degrades gracefully to "not comparable" when none is available
    # yet (no meta collected, or the class isn't represented on the builds ladder).
    meta = _load_meta_build(mine.get("char_class"))
    return compute_build_diff(mine, meta)


def _load_meta_build(char_class: str | None) -> dict[str, Any] | None:
    """Newest meta build for the owner's class from poe.ninja. None (graceful degrade) when the
    class is unset or nothing has been collected for it yet."""
    if not char_class:
        return None
    from collector.config import get_settings
    from db.repo import latest_meta_build

    return latest_meta_build(get_settings().poe2_league, char_class)
