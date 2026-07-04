"""Offline tests for the daily-orchestration failure surfacing (collector.run_daily).

The orchestration glue itself needs the live DB/LLM, but the *failure surfacing* — the
guarantee that a swallowed collector error turns the Actions run red instead of staying
silently green — is pure and must be tested offline.
"""

import collector.run_daily as rd
from collector.run_daily import (
    main,
    render_annotations,
    render_step_summary,
)


def _results(ok=(), failed=()):
    """Build a results dict shaped like run_all's return value."""
    out = {}
    for name in ok:
        out[name] = {"ok": True, "result": 1}
    for name, err in failed:
        out[name] = {"ok": False, "error": err}
    out["summary"] = {"ok_steps": list(ok), "failed_steps": [n for n, _ in failed]}
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
    assert results["first"] == {"ok": False, "error": "kaboom"}
    assert results["second"] == {"ok": True, "result": 7}
