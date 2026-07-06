"""Daily orchestration: the sequence GitHub Actions runs once per day.

ninja_client -> ninja_build_client -> youtube -> rss -> curate -> guides -> export_obsidian
-> daily_insight.
Each step is wrapped so one failure is logged and the rest still run (resilient collection),
but the run then exits non-zero and emits GitHub Actions annotations so a failed collector is
NEVER silently green — the whole point is that the owner sees a red X, not a buried log line.
The daily report is still committed because the workflow's commit step runs with `if: always()`.
Invoked by GitHub Actions: `python -m collector.run_daily`.
"""

from __future__ import annotations

import asyncio
import logging
import os
import traceback
from collections.abc import Awaitable, Callable
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("run_daily")


async def _step(
    name: str, make_awaitable: Callable[[], Awaitable[Any]], results: dict[str, Any]
) -> None:
    try:
        result = await make_awaitable()
        results[name] = {"ok": True, "result": result}
        log.info("step %s OK: %s", name, result)
    except Exception as exc:  # noqa: BLE001 — resilience: keep going, record the failure
        results[name] = {"ok": False, "error": str(exc)}
        log.error("step %s FAILED: %s\n%s", name, exc, traceback.format_exc())


async def run_all(pob_code: str | None = None) -> dict[str, Any]:
    from collector import (
        craft_guides,
        curate,
        guides,
        ninja_build_client,
        ninja_client,
        ninja_meta_client,
        rss_client,
        seed_craft_methods,
        seed_knowledge,
        youtube_client,
    )
    from scripts import daily_insight, export_obsidian

    results: dict[str, Any] = {}
    await _step("ninja_economy", ninja_client.run, results)
    await _step("my_build", lambda: ninja_build_client.run(pob_code), results)
    # popular/meta builds per class — the /build diff reference (degrades gracefully if it fails).
    await _step("meta_builds", ninja_meta_client.run, results)
    await _step("youtube", youtube_client.run, results)
    await _step("rss", rss_client.run, results)
    # seed curated craft knowledge before curation/guides can use it (sync -> thread).
    await _step("seed_knowledge", lambda: asyncio.to_thread(seed_knowledge.run), results)
    # seed structured craft methods (Craft 2 — recipe data the EV engine will price).
    await _step("seed_craft_methods", lambda: asyncio.to_thread(seed_craft_methods.run), results)
    # curate + guides + export are sync; run them off the event loop thread.
    await _step("curate", lambda: asyncio.to_thread(curate.run), results)
    await _step("guides", lambda: asyncio.to_thread(guides.run), results)
    # craft guides (Craft 4) need the seeded methods + prices above; run after them.
    await _step("craft_guides", lambda: asyncio.to_thread(craft_guides.run), results)
    await _step("export_obsidian", lambda: asyncio.to_thread(export_obsidian.run), results)
    await _step("daily_insight", lambda: asyncio.to_thread(daily_insight.run), results)
    results["summary"] = {
        "ok_steps": [k for k, v in results.items() if isinstance(v, dict) and v.get("ok")],
        "failed_steps": [k for k, v in results.items() if isinstance(v, dict) and not v.get("ok")],
    }
    return results


def _one_line(text: object) -> str:
    """Collapse whitespace/newlines: GitHub annotations render on a single line."""
    return " ".join(str(text).split())


def render_annotations(results: dict[str, Any]) -> list[str]:
    """One GitHub Actions '::error::' workflow command per failed step.

    Pure over its input so it's unit-testable offline. Printing these makes each failed
    collector show up as an annotation on the run page instead of a buried log line.
    """
    failed = results.get("summary", {}).get("failed_steps", [])
    lines: list[str] = []
    for name in failed:
        err = _one_line(results.get(name, {}).get("error", "unknown error"))
        lines.append(f"::error title=Daily collection::step '{name}' failed: {err}")
    return lines


def render_step_summary(results: dict[str, Any]) -> str:
    """Markdown for `$GITHUB_STEP_SUMMARY` — a run-page recap of OK vs failed steps.

    Pure over its input so it's unit-testable offline.
    """
    summary = results.get("summary", {})
    ok = summary.get("ok_steps", [])
    failed = summary.get("failed_steps", [])
    lines = ["## Daily collection", "", f"- OK: {len(ok)} · Failed: {len(failed)}", ""]
    if failed:
        lines += ["| Step | Error |", "| --- | --- |"]
        for name in failed:
            err = _one_line(results.get(name, {}).get("error", "unknown error"))
            lines.append(f"| `{name}` | {err} |")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    """Run the daily collection, surface any failures, and return the process exit code.

    Returns 1 when any step failed so the Actions run goes red (never silently green);
    the report still commits because the workflow's commit step uses `if: always()`.
    """
    out = asyncio.run(run_all())
    summary = out["summary"]
    log.info("daily run complete: %s", summary)
    for line in render_annotations(out):
        print(line)
    step_summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary_path:
        try:
            with open(step_summary_path, "a", encoding="utf-8") as fh:
                fh.write(render_step_summary(out) + "\n")
        except OSError as exc:  # reporting IO must never sink the run
            log.warning("could not write GITHUB_STEP_SUMMARY: %s", exc)
    return 1 if summary["failed_steps"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
