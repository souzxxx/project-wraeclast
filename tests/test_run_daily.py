"""Offline coverage for collector/run_daily.py.

`run_all` is the daily orchestration GitHub Actions invokes. It defers every
collector/script import to call time, so each step's `run` is monkeypatched on
its home module — async stubs for the network steps that are awaited directly,
plain stubs for the sync steps dispatched via `asyncio.to_thread`. No DB, no
network. We assert the step sequence, pob_code passthrough, the summary split,
and — critically — the resilience contract: one failing step is recorded but
never sinks the rest of the run.
"""

from __future__ import annotations

import asyncio

import pytest

from collector.run_daily import _step, run_all

# every step name run_all is expected to record, in order
STEP_ORDER = [
    "ninja_economy",
    "my_build",
    "meta_builds",
    "youtube",
    "rss",
    "seed_knowledge",
    "seed_craft_methods",
    "curate",
    "guides",
    "craft_guides",
    "export_obsidian",
    "daily_insight",
]

# (module path, run attr name, is_async) for each step in run_all
_ASYNC_STEPS = [
    "collector.ninja_client",
    "collector.ninja_build_client",
    "collector.ninja_meta_client",
    "collector.youtube_client",
    "collector.rss_client",
]
_SYNC_STEPS = [
    "collector.seed_knowledge",
    "collector.seed_craft_methods",
    "collector.curate",
    "collector.guides",
    "collector.craft_guides",
    "scripts.export_obsidian",
    "scripts.daily_insight",
]


# ── _step — the resilient wrapper ────────────────────────────────────────────────────

def test_step_records_success():
    results: dict = {}

    async def ok():
        return 7

    asyncio.run(_step("s", ok, results))
    assert results["s"] == {"ok": True, "result": 7}


def test_step_swallows_exception_and_records_error():
    results: dict = {}

    async def boom():
        raise ValueError("kaboom")

    asyncio.run(_step("s", boom, results))
    assert results["s"] == {"ok": False, "error": "kaboom"}


# ── run_all — full orchestration ─────────────────────────────────────────────────────

def _patch_all(monkeypatch, calls, *, fail=None):
    """Patch every step's run; append its name to `calls` when invoked.

    `fail` (a step name) raises inside that step to exercise the resilience path.
    """
    def make_async(name):
        async def _run(*args, **kwargs):
            calls.append((name, args, kwargs))
            if name == fail:
                raise RuntimeError(f"{name} down")
            return name
        return _run

    def make_sync(name):
        def _run(*args, **kwargs):
            calls.append((name, args, kwargs))
            if name == fail:
                raise RuntimeError(f"{name} down")
            return name
        return _run

    for mod in _ASYNC_STEPS:
        monkeypatch.setattr(f"{mod}.run", make_async(mod.rsplit(".", 1)[-1]))
    for mod in _SYNC_STEPS:
        monkeypatch.setattr(f"{mod}.run", make_sync(mod.rsplit(".", 1)[-1]))


def test_run_all_runs_every_step_in_order_and_summarizes(monkeypatch):
    calls: list = []
    _patch_all(monkeypatch, calls)

    results = asyncio.run(run_all())

    # every declared step recorded, in the documented order
    assert [k for k in results if k != "summary"] == STEP_ORDER
    assert all(results[s]["ok"] for s in STEP_ORDER)
    assert results["summary"]["ok_steps"] == STEP_ORDER
    assert results["summary"]["failed_steps"] == []
    # the pipeline actually invoked each underlying run exactly once
    invoked = [name for name, _, _ in calls]
    assert sorted(invoked) == sorted(m.rsplit(".", 1)[-1] for m in _ASYNC_STEPS + _SYNC_STEPS)


def test_run_all_threads_pob_code_into_my_build(monkeypatch):
    calls: list = []
    _patch_all(monkeypatch, calls)

    asyncio.run(run_all(pob_code="PoB==code"))

    by_name = {name: (args, kwargs) for name, args, kwargs in calls}
    # ninja_build_client.run(pob_code) receives the code positionally via the lambda
    assert by_name["ninja_build_client"][0] == ("PoB==code",)
    # a step that takes no code is called with no args
    assert by_name["ninja_client"] == ((), {})


def test_run_all_one_failing_step_does_not_sink_the_rest(monkeypatch):
    calls: list = []
    _patch_all(monkeypatch, calls, fail="curate")

    results = asyncio.run(run_all())

    # the failure is recorded, isolated, and everything downstream still ran
    assert results["curate"]["ok"] is False
    assert "curate down" in results["curate"]["error"]
    assert results["summary"]["failed_steps"] == ["curate"]
    assert results["summary"]["ok_steps"] == [s for s in STEP_ORDER if s != "curate"]
    # steps after the failure still executed (resilient collection)
    invoked = [name for name, _, _ in calls]
    assert "guides" in invoked and "daily_insight" in invoked


@pytest.mark.parametrize("failing", ["ninja_economy", "daily_insight"])
def test_run_all_resilient_at_the_edges(monkeypatch, failing):
    calls: list = []
    # map summary-name to module-run-name for the two edge steps
    fail_run = {"ninja_economy": "ninja_client", "daily_insight": "daily_insight"}[failing]
    _patch_all(monkeypatch, calls, fail=fail_run)

    results = asyncio.run(run_all())

    assert results[failing]["ok"] is False
    assert results["summary"]["failed_steps"] == [failing]
    # all 12 steps were still attempted
    assert len([k for k in results if k != "summary"]) == len(STEP_ORDER)
