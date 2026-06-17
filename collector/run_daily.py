"""Daily orchestration: the sequence Cloudflare Cron triggers once per day.

ninja_client -> ninja_build_client -> community_scraper(+ingest) -> curate -> export_obsidian.
Each step is wrapped so one failure is logged and the rest still run (resilient collection).
The same function backs the API's internal /run endpoint that cron calls.
"""

from __future__ import annotations

import asyncio
import logging
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
    from collector import community_scraper, curate, ninja_build_client, ninja_client
    from scripts import export_obsidian

    results: dict[str, Any] = {}
    await _step("ninja_economy", ninja_client.run, results)
    await _step("my_build", lambda: ninja_build_client.run(pob_code), results)
    await _step("community", community_scraper.run, results)
    # curate + export are sync; run them off the event loop thread.
    await _step("curate", lambda: asyncio.to_thread(curate.run), results)
    await _step("export_obsidian", lambda: asyncio.to_thread(export_obsidian.run), results)
    results["summary"] = {
        "ok_steps": [k for k, v in results.items() if isinstance(v, dict) and v.get("ok")],
        "failed_steps": [k for k, v in results.items() if isinstance(v, dict) and not v.get("ok")],
    }
    return results


if __name__ == "__main__":
    out = asyncio.run(run_all())
    log.info("daily run complete: %s", out["summary"])
