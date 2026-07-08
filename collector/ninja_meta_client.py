"""Popular/meta builds from poe.ninja — the reference the build-diff compares the owner against.

Fills the `/build` meta source so the diff stops degrading to "not comparable" (CLAUDE.md
Phase 0, ROADMAP P2). poe.ninja exposes a PoE2 builds ladder; we group its characters by class,
count how often each skill gem appears, and keep the most-used ones per class as a `MetaBuild`.

The AGGREGATION is pure and unit-tested offline. The live endpoint shape mirrors the public
profile (className + skills[{name}]); the exact builds path is config-driven and confirmed in the
deploy with `explore`, exactly like ninja_client / ninja_build_client were bootstrapped (skill
§1/§2b: never hardcode the league/endpoint, validate with a GET, parse defensively).

CLI:
    python -m collector.ninja_meta_client explore   # dump the raw builds payload, no DB writes
    python -m collector.ninja_meta_client run        # aggregate per class + write meta_build
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter, defaultdict
from typing import Any

import httpx

from collector.config import Settings, get_settings
from collector.http import HttpClient
from db.models import MetaBuild

CACHE_TTL = 6 * 3600  # builds ladder is a daily-ish snapshot; don't hammer (skill §1).


class NinjaBuildsUnavailable(RuntimeError):
    """No configured poe.ninja builds endpoint returned characters. Carries the exact paths +
    statuses tried so the daily run goes red with an actionable message (run_daily surfacing,
    Done 2026-07-04) instead of a bare `404` — the owner can then confirm the route with
    `python -m collector.ninja_meta_client explore` rather than guessing."""


def extract_characters(payload: Any) -> list[dict[str, Any]]:
    """Pull the character list out of a builds payload, defensively. Accepts a bare list or a
    dict carrying the list under a common key (PoE2 shape unconfirmed — tolerate variants)."""
    if isinstance(payload, list):
        return [c for c in payload if isinstance(c, dict)]
    if isinstance(payload, dict):
        for key in ("characters", "accounts", "data", "entries"):
            value = payload.get(key)
            if isinstance(value, list):
                return [c for c in value if isinstance(c, dict)]
    return []


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


async def _fetch_builds_payload(http: HttpClient, settings: Settings) -> tuple[str, Any]:
    """Try each configured builds path in order; return (path, payload) for the FIRST that yields
    characters. A 404/HTTP error or an empty-character payload just moves on to the next candidate.
    Raises `NinjaBuildsUnavailable` listing every attempt if none work (the PoE2 route is
    unconfirmed — see config), so the failure is actionable, not a mystery 404."""
    attempts: list[str] = []
    for path in settings.ninja_builds_path_list:
        try:
            payload = await http.get_json(
                path, params={"league": settings.poe2_league}, cache_ttl=CACHE_TTL
            )
        except httpx.HTTPStatusError as exc:
            attempts.append(f"{path} -> HTTP {exc.response.status_code}")
            continue
        except httpx.HTTPError as exc:  # transport/timeout/etc. — try the next candidate
            attempts.append(f"{path} -> {type(exc).__name__}")
            continue
        if extract_characters(payload):
            return path, payload
        attempts.append(f"{path} -> 0 characters")
    raise NinjaBuildsUnavailable(
        "no poe.ninja builds endpoint returned characters; tried: "
        + "; ".join(attempts)
        + " (run `python -m collector.ninja_meta_client explore` in the deploy to find the route)"
    )


async def fetch_popular_builds(settings: Settings | None = None) -> list[MetaBuild]:
    settings = settings or get_settings()
    async with HttpClient(settings.user_agent, base_url=settings.ninja_base_url) as http:
        _path, payload = await _fetch_builds_payload(http, settings)
    chars = extract_characters(payload)[: settings.ninja_meta_max_chars]
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
    """Try each configured builds endpoint until one yields characters, then dump raw JSON —
    confirm the PoE2 route + shape before modeling. Reports which candidate worked (or, if none
    did, every path + status tried) so the owner can pin `ninja_builds_path` via env."""
    settings = get_settings()
    async with HttpClient(settings.user_agent, base_url=settings.ninja_base_url) as http:
        try:
            path, data = await _fetch_builds_payload(http, settings)
        except NinjaBuildsUnavailable as exc:
            print(str(exc), file=sys.stderr)
            return
    chars = extract_characters(data)
    print(f"builds endpoint: {path}")
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
