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

import collector.run_daily as rd
from collector.run_daily import (
    _step,
    main,
    render_annotations,
    render_step_summary,
    run_all,
)

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
    assert results["s"] == {"ok": True, "result": 7, "optional": False}


def test_step_swallows_exception_and_records_error():
    results: dict = {}

    async def boom():
        raise ValueError("kaboom")

    asyncio.run(_step("s", boom, results))
    assert results["s"] == {"ok": False, "error": "kaboom", "optional": False}


def test_step_records_optional_flag():
    results: dict = {}

    async def ok():
        return 1

    async def boom():
        raise ValueError("x")

    asyncio.run(_step("good", ok, results, optional=True))
    asyncio.run(_step("bad", boom, results, optional=True))
    assert results["good"]["optional"] is True
    assert results["bad"]["optional"] is True


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
    # a required step failing lands in failed_required (turns the run red)
    assert results["summary"]["failed_required"] == [failing]
    assert results["summary"]["failed_optional"] == []
    # all 12 steps were still attempted
    assert len([k for k in results if k != "summary"]) == len(STEP_ORDER)


@pytest.mark.parametrize("failing", ["meta_builds", "rss"])
def test_run_all_optional_failure_does_not_turn_red(monkeypatch, failing):
    calls: list = []
    fail_run = {"meta_builds": "ninja_meta_client", "rss": "rss_client"}[failing]
    _patch_all(monkeypatch, calls, fail=fail_run)

    results = asyncio.run(run_all())

    # the optional step is recorded failed and flagged, but stays out of failed_required
    assert results[failing]["ok"] is False
    assert results[failing]["optional"] is True
    assert results["summary"]["failed_steps"] == [failing]
    assert results["summary"]["failed_optional"] == [failing]
    assert results["summary"]["failed_required"] == []


def test_run_all_marks_only_meta_builds_and_rss_optional(monkeypatch):
    calls: list = []
    _patch_all(monkeypatch, calls)

    results = asyncio.run(run_all())

    optional = {s for s in STEP_ORDER if results[s].get("optional")}
    assert optional == {"meta_builds", "rss"}


# ---- failure surfacing (annotations / step summary / main exit code) ----


def _results(ok=(), failed=(), optional=()):
    """Build a results dict shaped like run_all's return value.

    `optional` is the set of step names (ok or failed) marked non-critical.
    """
    optional = set(optional)
    out = {}
    for name in ok:
        out[name] = {"ok": True, "result": 1, "optional": name in optional}
    failed_names = [n for n, _ in failed]
    for name, err in failed:
        out[name] = {"ok": False, "error": err, "optional": name in optional}
    out["summary"] = {
        "ok_steps": list(ok),
        "failed_steps": failed_names,
        "failed_required": [n for n in failed_names if n not in optional],
        "failed_optional": [n for n in failed_names if n in optional],
    }
    return out


def test_render_annotations_empty_when_all_ok():
    assert render_annotations(_results(ok=["ninja_economy", "curate"])) == []


def test_render_annotations_one_error_command_per_failed_step():
    res = _results(ok=["ninja_economy"], failed=[("curate", "boom"), ("youtube", "429")])
    lines = render_annotations(res)
    assert lines == [
        "::error title=Daily collection::step 'curate' failed: boom",
        "::error title=Daily collection::step 'youtube' failed: 429",
    ]


def test_render_annotations_collapses_multiline_errors():
    # GitHub annotations render on a single line; newlines/extra whitespace must collapse.
    res = _results(failed=[("curate", "line1\n  line2\ttab")])
    assert render_annotations(res) == [
        "::error title=Daily collection::step 'curate' failed: line1 line2 tab"
    ]


def test_render_annotations_tolerates_missing_error_field():
    res = {"summary": {"ok_steps": [], "failed_steps": ["curate"]}}  # no per-step entry
    assert render_annotations(res) == [
        "::error title=Daily collection::step 'curate' failed: unknown error"
    ]


def test_render_annotations_uses_warning_for_optional_failures():
    res = _results(
        ok=["ninja_economy"],
        failed=[("curate", "boom"), ("meta_builds", "404")],
        optional=["meta_builds"],
    )
    lines = render_annotations(res)
    assert lines == [
        "::error title=Daily collection::step 'curate' failed: boom",
        "::warning title=Daily collection::step 'meta_builds' failed (optional): 404",
    ]


def test_render_step_summary_all_ok_has_no_table():
    md = render_step_summary(_results(ok=["a", "b"]))
    assert "## Daily collection" in md
    assert "OK: 2 · Failed: 0" in md
    assert "| Step | Error |" not in md


def test_render_step_summary_lists_failed_rows():
    md = render_step_summary(_results(ok=["a"], failed=[("curate", "boom")]))
    assert "OK: 1 · Failed: 1" in md
    assert "| Step | Error |" in md
    assert "| `curate` | boom |" in md


def test_render_step_summary_marks_optional_failures():
    md = render_step_summary(
        _results(ok=["a"], failed=[("meta_builds", "404")], optional=["meta_builds"])
    )
    assert "1 optional, did not fail the run" in md
    assert "| `meta_builds` | 404 _(optional — did not fail the run)_ |" in md


def test_main_returns_zero_when_only_optional_step_failed(monkeypatch, capsys):
    async def fake_run_all():
        return _results(
            ok=["ninja_economy"], failed=[("meta_builds", "404")], optional=["meta_builds"]
        )

    monkeypatch.setattr(rd, "run_all", fake_run_all)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    # an optional-only failure keeps the run green (exit 0)...
    assert main() == 0
    # ...but is still surfaced as a visible warning annotation.
    out = capsys.readouterr().out
    assert "::warning title=Daily collection::step 'meta_builds' failed (optional): 404" in out


def test_main_returns_one_when_required_fails_even_with_optional(monkeypatch):
    async def fake_run_all():
        return _results(
            ok=["ninja_economy"],
            failed=[("curate", "boom"), ("meta_builds", "404")],
            optional=["meta_builds"],
        )

    monkeypatch.setattr(rd, "run_all", fake_run_all)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert main() == 1


def test_main_returns_zero_when_no_failures(monkeypatch):
    async def fake_run_all():
        return _results(ok=["ninja_economy", "curate"])

    monkeypatch.setattr(rd, "run_all", fake_run_all)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert main() == 0


def test_main_returns_one_when_any_step_failed(monkeypatch, capsys):
    async def fake_run_all():
        return _results(ok=["ninja_economy"], failed=[("curate", "boom")])

    monkeypatch.setattr(rd, "run_all", fake_run_all)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert main() == 1
    # the annotation is emitted so the failure is visible on the run page
    assert "::error title=Daily collection::step 'curate' failed: boom" in capsys.readouterr().out


def test_main_writes_step_summary_when_env_set(monkeypatch, tmp_path):
    summary_file = tmp_path / "summary.md"

    async def fake_run_all():
        return _results(ok=["ninja_economy"], failed=[("curate", "boom")])

    monkeypatch.setattr(rd, "run_all", fake_run_all)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))
    assert main() == 1
    written = summary_file.read_text(encoding="utf-8")
    assert "| `curate` | boom |" in written


def test_main_survives_unwritable_step_summary(monkeypatch, tmp_path):
    # A bad summary path must warn, not crash the run (reporting IO can't sink collection).
    async def fake_run_all():
        return _results(ok=["ninja_economy"])

    monkeypatch.setattr(rd, "run_all", fake_run_all)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "nope" / "missing.md"))
    assert main() == 0


def test_run_all_records_failed_step_and_keeps_going(monkeypatch):
    # A step that raises is recorded as failed but does NOT stop later steps (resilience).
    async def boom():
        raise RuntimeError("kaboom")

    async def fine():
        return 7

    results: dict = {}

    import asyncio

    async def drive():
        await rd._step("first", boom, results)
        await rd._step("second", fine, results)

    asyncio.run(drive())
    assert results["first"] == {"ok": False, "error": "kaboom", "optional": False}
    assert results["second"] == {"ok": True, "result": 7, "optional": False}
