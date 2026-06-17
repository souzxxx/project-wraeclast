"""Path of Building code parser — universal account-data fallback (Phase 1).

A PoB export/import code is: base64url( zlib.compress( <PathOfBuilding> XML ) ).
This module decodes it and extracts the bits we care about (level, class, gems, items)
into the same shape `ninja_build_client` produces, so `my_snapshot` is source-agnostic.

Pure, offline, no network — fully unit-testable. Works for any character/level, which is
why it's the fallback when a character isn't on the ninja ladder (skill §2/§2b).
"""

from __future__ import annotations

import base64
import zlib
from typing import Any
from xml.etree import ElementTree as ET

from db.models import MySnapshot


class PoBParseError(ValueError):
    """Raised when the input is not a decodable PoB code."""


def decode_pob_code(code: str) -> str:
    """Return the raw PoB XML for a build code. Raises PoBParseError on bad input."""
    cleaned = code.strip().replace("\n", "").replace("\r", "")
    if not cleaned:
        raise PoBParseError("empty PoB code")
    # PoB uses URL-safe base64; tolerate standard base64 too. Fix padding.
    cleaned = cleaned.replace("-", "+").replace("_", "/")
    cleaned += "=" * (-len(cleaned) % 4)
    try:
        compressed = base64.b64decode(cleaned)
        xml_bytes = zlib.decompress(compressed)
    except (ValueError, zlib.error, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
        raise PoBParseError(f"not a valid PoB code: {exc}") from exc
    return xml_bytes.decode("utf-8", errors="replace")


def _parse_gems(root: ET.Element) -> list[dict[str, Any]]:
    gems: list[dict[str, Any]] = []
    for gem in root.iter("Gem"):
        name = gem.get("nameSpec") or gem.get("skillId") or ""
        if not name:
            continue
        gems.append(
            {
                "name": name,
                "level": _to_int(gem.get("level")),
                "quality": _to_int(gem.get("quality")),
                "enabled": gem.get("enabled", "true") == "true",
            }
        )
    return gems


def _parse_items(root: ET.Element) -> dict[str, Any]:
    """Items are free text inside <Item> nodes; keep the raw text + a best-effort name."""
    items: list[dict[str, str]] = []
    for item in root.iter("Item"):
        text = (item.text or "").strip()
        if not text:
            continue
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        # PoB item text usually starts with "Rarity: X", then the name lines.
        name = ""
        for i, ln in enumerate(lines):
            if ln.lower().startswith("rarity:") and i + 1 < len(lines):
                name = lines[i + 1]
                break
        items.append({"name": name or (lines[0] if lines else ""), "raw": text})
    return {"items": items}


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_pob_code(code: str, *, character_name: str | None = None) -> MySnapshot:
    """Decode a PoB code into a MySnapshot row (gear/gems/level/class)."""
    xml = decode_pob_code(code)
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise PoBParseError(f"PoB XML did not parse: {exc}") from exc

    build = root.find("Build")
    level = _to_int(build.get("level")) if build is not None else None
    class_name = build.get("className") if build is not None else None
    ascendancy = build.get("ascendClassName") if build is not None else None

    gems = _parse_gems(root)
    gear = _parse_items(root)
    if ascendancy and ascendancy not in ("None", ""):
        gear["ascendancy"] = ascendancy

    return MySnapshot(
        character_name=character_name,
        char_class=class_name or None,
        level=level,
        gear=gear,
        gems=gems,
        passive_tree={"source": "pob_code"},
    )
