"""Offline tests for the daily orchestrator.

`run_all` sequences every collector/curation step and is deliberately resilient: one step
failing is logged and recorded, but the rest still run. The whole thing is drivable offline
because every step target is looked up as a module attribute at call time — so we monkeypatch
each `.run` with a fake (async collectors → async fakes; sync steps run via `asyncio.to_thread`
→ sync fakes) and assert the ordering, the pob_code threading, and the failure isolation.
No network, no Neon.
"""

from __future__ import annotations

from collector.run_daily import _step, run_all

# every step name run_all is expected to record, in order.
ASYNC_STEPS = {
    "collector.ninja_client.run": "ninja_economy",
    "collector.ninja_build_client.run": "my_build",
    "collector.ninja_meta_client.run": "meta_builds",
    "collector.youtube_client.run": "youtube",
    "collector.rss_client.run": "rss",
}
SYNC_STEPS = {
    "collector.seed_knowledge.run": "seed_knowledge",
    "collector.seed_craft_methods.run": "seed_craft_methods",
    "collector.curate.run": "curate",
    "collector.guides.run": "guides",
    "collector.craft_guides.run": "craft_guides",
    "scripts.export_obsidian.run": "export_obsidian",
    "scripts.daily_insight.run": "daily_insight",
}
ALL_STEPS = set(ASYNC_STEPS.values()) | set(SYNC_STEPS.values())


def _patch_all(monkeypatch, recorder):
    """Wire every step to a fake that records the call and returns a marker."""

    def async_fake(name):
        async def _run(*args):
            recorder.append((name, args))
            return f"{name}-done"

        return _run

    def sync_fake(name):
        def _run(*args):
            recorder.append((name, args))
            return f"{name}-done"

        return _run

    for path, name in ASYNC_STEPS.items():
        monkeypatch.setattr(path, async_fake(name))
    for path, name in SYNC_STEPS.items():
        monkeypatch.setattr(path, sync_fake(name))


async def test_step_records_success():
    results: dict = {}

    async def ok():
        return 7

    await _step("thing", ok, results)
    assert results["thing"] == {"ok": True, "result": 7}


async def test_step_records_failure_without_raising():
    results: dict = {}

    async def boom():
        raise ValueError("nope")

    # a failing step must be swallowed and recorded, never propagate.
    await _step("thing", boom, results)
    assert results["thing"] == {"ok": False, "error": "nope"}


async def test_run_all_every_step_ok(monkeypatch):
    recorder: list = []
    _patch_all(monkeypatch, recorder)

    out = await run_all(pob_code="POB-CODE")

    assert out["summary"]["failed_steps"] == []
    assert set(out["summary"]["ok_steps"]) == ALL_STEPS
    # each step recorded its result marker.
    assert out["curate"] == {"ok": True, "result": "curate-done"}
    # pob_code is threaded specifically into the my_build step and nowhere else.
    assert ("my_build", ("POB-CODE",)) in recorder
    assert ("ninja_economy", ()) in recorder


async def test_run_all_isolates_a_failing_step(monkeypatch):
    recorder: list = []
    _patch_all(monkeypatch, recorder)

    def explode():
        raise RuntimeError("curate blew up")

    monkeypatch.setattr("collector.curate.run", explode)

    out = await run_all()

    assert out["summary"]["failed_steps"] == ["curate"]
    assert out["curate"] == {"ok": False, "error": "curate blew up"}
    # steps sequenced after the failure still ran — resilience is the whole point.
    for later in ("guides", "craft_guides", "export_obsidian", "daily_insight"):
        assert later in out["summary"]["ok_steps"]
