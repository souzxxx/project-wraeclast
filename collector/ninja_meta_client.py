"""Popular/meta builds from poe.ninja — the reference the build-diff compares the owner against.

Fills the `/build` meta source so the diff stops degrading to "not comparable" (CLAUDE.md
Phase 0, ROADMAP P2). poe.ninja exposes a PoE2 builds ladder; we group its characters by class,
count how often each skill gem appears, and keep the most-used ones per class as a `MetaBuild`.

The AGGREGATION is pure and unit-tested offline. The ladder itself is served as protobuf
(`application/x-protobuf`), confirmed live 2026-07-06 by reading poe.ninja's own frontend:

    GET /poe2/api/data/index-state                     # JSON; snapshotVersions[] maps league
                                                       # name -> {version, snapshotName}
    GET /poe2/api/builds/{version}/search?overview=<snapshotName>
                                                       # protobuf; per-character columns
                                                       # (class/skills as dictionary indices)
                                                       # + content hashes of the dictionaries
    GET /poe2/api/builds/dictionary/<hash>             # protobuf; position -> display name

We decode the wire format directly (varint + length-delimited fields only) instead of shipping
generated protobuf stubs: the three shapes we touch are tiny, and every field is parsed
defensively (unknown fields skipped, out-of-range indices dropped).

CLI:
    python -m collector.ninja_meta_client explore   # dump the decoded ladder, no DB writes
    python -m collector.ninja_meta_client run        # aggregate per class + write meta_build
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter, defaultdict
from typing import Any

from collector.config import Settings, get_settings
from collector.http import HttpClient
from db.models import MetaBuild

CACHE_TTL = 6 * 3600  # builds ladder is a daily-ish snapshot; don't hammer (skill §1).


# ── protobuf wire-format decoding (pure) ──────────────────────────────────────


def _read_varint(buf: bytes, i: int) -> tuple[int, int]:
    value = shift = 0
    while True:
        byte = buf[i]
        i += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, i
        shift += 7


def _wire_fields(buf: bytes) -> list[tuple[int, int, Any]]:
    """Decode one protobuf message into (field_number, wire_type, value) tuples.

    value is an int for wire type 0 (varint) and bytes for types 2/5/1 (length-delimited and
    fixed 32/64). Raises ValueError/IndexError on malformed input — callers treat that as
    "not the shape we expected" and degrade."""
    i = 0
    out: list[tuple[int, int, Any]] = []
    while i < len(buf):
        tag, i = _read_varint(buf, i)
        field, wire = tag >> 3, tag & 7
        if wire == 0:
            value, i = _read_varint(buf, i)
        elif wire == 2:
            length, i = _read_varint(buf, i)
            value = buf[i : i + length]
            i += length
        elif wire == 5:
            value = buf[i : i + 4]
            i += 4
        elif wire == 1:
            value = buf[i : i + 8]
            i += 8
        else:
            raise ValueError(f"unsupported wire type {wire}")
        out.append((field, wire, value))
    return out


def _packed_varints(buf: bytes) -> list[int]:
    i = 0
    out: list[int] = []
    while i < len(buf):
        value, i = _read_varint(buf, i)
        out.append(value)
    return out


def parse_dictionary(buf: bytes) -> list[str]:
    """Dictionary message: field 1 = id, repeated field 2 = values. A value's position in the
    list IS the index the search columns reference."""
    return [
        value.decode("utf-8", "replace")
        for field, wire, value in _wire_fields(buf)
        if field == 2 and wire == 2
    ]


def _decode_row(buf: bytes) -> dict[str, Any]:
    """One per-character cell: field 1 = string, field 2 = number, field 3 = index list
    (packed or repeated). proto3 omits defaults, so an empty cell means index/number 0."""
    out: dict[str, Any] = {"str": None, "num": 0, "nums": []}
    for field, wire, value in _wire_fields(buf):
        if field == 1 and wire == 2:
            out["str"] = value.decode("utf-8", "replace")
        elif field == 2 and wire == 0:
            out["num"] = value
        elif field == 3 and wire == 2:
            out["nums"] = _packed_varints(value)
        elif field == 3 and wire == 0:
            out["nums"].append(value)
    return out


def parse_search(buf: bytes) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    """Search response: root field 1 = result; result field 5 = per-character columns
    ({1: column id, repeated 2: row cell}), field 6 = dictionary refs ({1: name, 2: hash}).

    Returns (columns, dictionary_hashes); columns maps column id -> decoded row cells."""
    columns: dict[str, list[dict[str, Any]]] = {}
    hashes: dict[str, str] = {}
    results = [v for f, w, v in _wire_fields(buf) if f == 1 and w == 2]
    for result in results:
        for field, wire, value in _wire_fields(result):
            if wire != 2:
                continue
            if field == 5:
                sub = _wire_fields(value)
                ids = [v for f, w, v in sub if f == 1 and w == 2]
                if not ids:
                    continue
                column_id = ids[0].decode("utf-8", "replace")
                columns[column_id] = [_decode_row(v) for f, w, v in sub if f == 2 and w == 2]
            elif field == 6:
                sub = _wire_fields(value)
                name = next((v for f, w, v in sub if f == 1 and w == 2), None)
                digest = next((v for f, w, v in sub if f == 2 and w == 2), None)
                if name and digest:
                    hashes[name.decode("utf-8", "replace")] = digest.decode("utf-8", "replace")
    return columns, hashes


def resolve_snapshot(index_state: Any, league: str) -> dict[str, str] | None:
    """Find the league's builds snapshot in the index-state JSON (matched by display name,
    case-insensitive). Returns {"version", "snapshotName"} or None if the league isn't listed."""
    if not isinstance(index_state, dict):
        return None
    for entry in index_state.get("snapshotVersions") or []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("name", "")).casefold() != league.casefold():
            continue
        version, snapshot_name = entry.get("version"), entry.get("snapshotName")
        if version and snapshot_name:
            return {"version": str(version), "snapshotName": str(snapshot_name)}
    return None


def build_characters(
    columns: dict[str, list[dict[str, Any]]],
    class_names: list[str],
    gem_names: list[str],
) -> list[dict[str, Any]]:
    """Join the search columns with the dictionaries into the {className, skills:[{name}]}
    shape the aggregation consumes. Out-of-range indices are dropped, not guessed."""
    class_rows = columns.get("class", [])
    skill_rows = columns.get("skills", [])
    chars: list[dict[str, Any]] = []
    for i, cell in enumerate(class_rows):
        index = cell["num"]
        if not 0 <= index < len(class_names):
            continue
        gem_indices = skill_rows[i]["nums"] if i < len(skill_rows) else []
        gems = [gem_names[g] for g in gem_indices if 0 <= g < len(gem_names)]
        chars.append({"className": class_names[index], "skills": [{"name": g} for g in gems]})
    return chars


def _char_class(char: dict[str, Any]) -> str | None:
    for key in ("className", "class", "ascendancy", "classId"):
        value = char.get(key)
        if value:
            return str(value).strip()
    return None


def _char_gems(char: dict[str, Any]) -> list[str]:
    """Skill-gem names for one character. Tolerates dict-items ({name}) or bare strings, across
    the field names poe.ninja has used for the gem list."""
    for key in ("skills", "allSkills", "gems", "mainSkills"):
        items = char.get(key)
        if not isinstance(items, list):
            continue
        names: list[str] = []
        for item in items:
            if isinstance(item, dict):
                name = item.get("name")
                if name:
                    names.append(str(name).strip())
            elif isinstance(item, str) and item.strip():
                names.append(item.strip())
        if names:
            return names
    return []


def aggregate_meta_builds(
    chars: list[dict[str, Any]],
    league: str,
    *,
    min_usage: float = 0.15,
    max_gems: int = 12,
    min_sample: int = 3,
    source: dict[str, Any] | None = None,
) -> list[MetaBuild]:
    """Group characters by class and rank skill gems by how many characters of that class run them.

    Keeps gems used by at least `min_usage` of the class's sample (so one-off picks don't pollute
    the meta), capped at `max_gems`, sorted by usage desc then name (deterministic). Classes with
    fewer than `min_sample` characters are skipped — too thin to call a "meta". Pure: no I/O."""
    by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for char in chars:
        char_class = _char_class(char)
        if char_class:
            by_class[char_class].append(char)

    out: list[MetaBuild] = []
    for char_class, members in sorted(by_class.items()):
        sample = len(members)
        if sample < min_sample:
            continue
        counts: Counter[str] = Counter()
        for member in members:
            counts.update(set(_char_gems(member)))  # set: count each gem once per character
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        gems = [
            {"name": name, "usage_pct": round(count / sample * 100, 1)}
            for name, count in ranked
            if count / sample >= min_usage
        ][:max_gems]
        if not gems:
            continue
        out.append(
            MetaBuild(
                league=league,
                char_class=char_class,
                sample_size=sample,
                gems=gems,
                sources=[source] if source else [],
            )
        )
    return out


async def _fetch_characters(settings: Settings) -> list[dict[str, Any]]:
    """index-state -> search -> dictionaries -> joined character dicts (network layer)."""
    async with HttpClient(settings.user_agent, base_url=settings.ninja_base_url) as http:
        index_state = await http.get_json(settings.ninja_index_state_path, cache_ttl=CACHE_TTL)
        snapshot = resolve_snapshot(index_state, settings.poe2_league)
        if snapshot is None:
            raise RuntimeError(
                f"league {settings.poe2_league!r} not found in poe.ninja index-state"
            )
        raw = await http.get_bytes(
            settings.ninja_builds_search_path.format(version=snapshot["version"]),
            params={"overview": snapshot["snapshotName"]},
            cache_ttl=CACHE_TTL,
        )
        columns, hashes = parse_search(raw)
        dictionaries: dict[str, list[str]] = {}
        for name in ("class", "gem"):
            digest = hashes.get(name)
            if not digest:
                raise RuntimeError(f"poe.ninja search response has no {name!r} dictionary")
            buf = await http.get_bytes(
                settings.ninja_builds_dictionary_path.format(hash=digest), cache_ttl=CACHE_TTL
            )
            dictionaries[name] = parse_dictionary(buf)
    return build_characters(columns, dictionaries["class"], dictionaries["gem"])


async def fetch_popular_builds(settings: Settings | None = None) -> list[MetaBuild]:
    settings = settings or get_settings()
    chars = (await _fetch_characters(settings))[: settings.ninja_meta_max_chars]
    source = {"url": settings.ninja_base_url + "/poe2/builds", "title": "poe.ninja builds"}
    return aggregate_meta_builds(
        chars, settings.poe2_league, min_usage=settings.ninja_meta_min_usage, source=source
    )


async def run() -> int:
    from db.repo import replace_meta_builds

    settings = get_settings()
    builds = await fetch_popular_builds(settings)
    written = replace_meta_builds(settings.poe2_league, builds)
    classes = ", ".join(f"{b.char_class}({b.sample_size})" for b in builds)
    print(f"meta_build: wrote {written} class builds for league={settings.poe2_league} [{classes}]")
    return written


async def explore() -> None:
    """Run the full index-state -> search -> dictionary chain and dump the decoded characters —
    confirms the wire format against the live deploy before/after a poe.ninja change."""
    settings = get_settings()
    chars = await _fetch_characters(settings)
    print(f"characters found: {len(chars)}")
    print(json.dumps(chars[:3], indent=2, ensure_ascii=False)[:4000])


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
