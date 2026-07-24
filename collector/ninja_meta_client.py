"""Popular/meta builds from poe.ninja — the reference the build-diff compares the owner against.

Fills the `/build` meta source so the diff stops degrading to "not comparable" (CLAUDE.md
Phase 0, ROADMAP P2). poe.ninja exposes a PoE2 builds ladder; we group its characters by class,
count how often each skill gem appears, and keep the most-used ones per class as a `MetaBuild`.

The AGGREGATION is pure and unit-tested offline. The live endpoint shape mirrors the public
profile (className + skills[{name}]); the exact builds path is config-driven and confirmed in the
deploy with `explore`, exactly like ninja_client / ninja_build_client were bootstrapped (skill
§1/§2b: never hardcode the league/endpoint, validate with a GET, parse defensively).

CLI:
    python -m collector.ninja_meta_client explore    # dump the raw builds payload, no DB writes
    python -m collector.ninja_meta_client discover    # probe candidate paths, report which works
    python -m collector.ninja_meta_client run         # aggregate per class + write meta_build
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter, defaultdict
from typing import Any

from pydantic import BaseModel, Field

from collector.config import Settings, get_settings
from collector.http import HttpClient
from db.models import MetaBuild

CACHE_TTL = 6 * 3600  # builds ladder is a daily-ish snapshot; don't hammer (skill §1).


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


async def fetch_popular_builds(settings: Settings | None = None) -> list[MetaBuild]:
    settings = settings or get_settings()
    async with HttpClient(settings.user_agent, base_url=settings.ninja_base_url) as http:
        payload = await http.get_json(
            settings.ninja_builds_path,
            params={"league": settings.poe2_league},
            cache_ttl=CACHE_TTL,
        )
    chars = extract_characters(payload)[: settings.ninja_meta_max_chars]
    source = {"url": settings.ninja_base_url + "/poe2/builds", "title": "poe.ninja builds"}
    return aggregate_meta_builds(
        chars, settings.poe2_league, min_usage=settings.ninja_meta_min_usage, source=source
    )


# ── endpoint discovery ──────────────────────────────────────────────────────────────
# The daily `meta_builds` step has been failing on a 404 because the PoE2 builds route is
# unconfirmed. `discover` probes the candidate paths (config-driven) and reports which one
# actually returns characters, so the owner can set NINJA_BUILDS_PATH to it — self-service
# diagnosis instead of editing code and guessing one path at a time. The probing is defensive
# (a per-candidate failure is recorded, never fatal) and the selection is pure/offline-tested.


class ProbeResult(BaseModel):
    path: str
    char_count: int = 0
    error: str | None = None


class DiscoveryResult(BaseModel):
    chosen_path: str | None = None
    attempts: list[ProbeResult] = Field(default_factory=list)


def pick_working_endpoint(attempts: list[ProbeResult]) -> str | None:
    """First probed path that returned at least one character (order = probe order). Pure."""
    for attempt in attempts:
        if attempt.error is None and attempt.char_count > 0:
            return attempt.path
    return None


async def discover_builds_path(settings: Settings | None = None) -> DiscoveryResult:
    """Probe each candidate builds path and report which returns a character list.

    Defensive: a candidate that 404s / errors / returns no characters is recorded and the probe
    moves on (one bad guess never aborts the sweep), mirroring how ninja_client tolerates a single
    failing economy category. Does NOT touch the DB or the daily `run()` path."""
    settings = settings or get_settings()
    attempts: list[ProbeResult] = []
    async with HttpClient(settings.user_agent, base_url=settings.ninja_base_url) as http:
        for path in settings.ninja_builds_path_candidate_list:
            try:
                payload = await http.get_json(path, params={"league": settings.poe2_league})
            except Exception as exc:  # noqa: BLE001 — any failure just disqualifies this candidate
                attempts.append(ProbeResult(path=path, error=f"{type(exc).__name__}: {exc}"))
                continue
            attempts.append(ProbeResult(path=path, char_count=len(extract_characters(payload))))
    return DiscoveryResult(chosen_path=pick_working_endpoint(attempts), attempts=attempts)


def render_discovery(result: DiscoveryResult) -> str:
    """Human-readable probe report + the actionable next step. Pure."""
    lines = ["poe.ninja PoE2 builds endpoint discovery:", ""]
    for a in result.attempts:
        if a.error is not None:
            lines.append(f"  ✗ {a.path} — {a.error}")
        elif a.char_count > 0:
            lines.append(f"  ✅ {a.path} — {a.char_count} characters")
        else:
            lines.append(f"  ∅ {a.path} — reachable but no characters found")
    lines.append("")
    if result.chosen_path:
        lines.append(f"Set NINJA_BUILDS_PATH to: {result.chosen_path}")
    else:
        lines.append(
            "No candidate returned characters. Add more guesses via NINJA_BUILDS_PATH_CANDIDATES "
            "or inspect poe.ninja/poe2/builds network calls manually."
        )
    return "\n".join(lines)


async def discover() -> None:
    print(render_discovery(await discover_builds_path()))


async def run() -> int:
    from db.repo import replace_meta_builds

    settings = get_settings()
    builds = await fetch_popular_builds(settings)
    written = replace_meta_builds(settings.poe2_league, builds)
    classes = ", ".join(f"{b.char_class}({b.sample_size})" for b in builds)
    print(f"meta_build: wrote {written} class builds for league={settings.poe2_league} [{classes}]")
    return written


async def explore() -> None:
    """GET the configured builds endpoint and dump raw JSON — confirm shape before modeling."""
    settings = get_settings()
    async with HttpClient(settings.user_agent, base_url=settings.ninja_base_url) as http:
        data = await http.get_json(
            settings.ninja_builds_path, params={"league": settings.poe2_league}
        )
    chars = extract_characters(data)
    print(f"characters found: {len(chars)}")
    print(json.dumps(chars[:3], indent=2, ensure_ascii=False)[:4000])


def _main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "run"
    if cmd == "explore":
        asyncio.run(explore())
        return 0
    if cmd == "discover":
        asyncio.run(discover())
        return 0
    if cmd == "run":
        asyncio.run(run())
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
