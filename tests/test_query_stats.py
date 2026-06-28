"""Offline tests for the YouTube query-productivity analyzer (collector.query_stats)."""

import collector.query_stats as qs
from collector.config import Settings
from collector.query_stats import (
    _main,
    build_report,
    collect_cited_urls,
    render_report,
    score_queries,
)


def test_collect_cited_urls_flattens_and_dedupes():
    urls = collect_cited_urls(
        [{"url": "a", "title": "x"}, {"url": "b"}],
        [{"url": "a"}, {"title": "no url"}, {}],
        [{"url": "  c  "}],  # trimmed
        None,  # tolerated
    )
    assert urls == {"a", "b", "c"}


def test_collect_cited_urls_ignores_non_dict_entries():
    assert collect_cited_urls(["not-a-dict", {"url": "a"}]) == {"a"}


def test_score_queries_counts_discovered_and_cited():
    attribution = [
        {"source_url": "u1", "discovery_query": "ritual farm"},
        {"source_url": "u2", "discovery_query": "ritual farm"},
        {"source_url": "u3", "discovery_query": "abyss farm"},
    ]
    cited = {"u1"}  # only one ritual chunk got cited; abyss none
    stats = {s.query: s for s in score_queries(["ritual farm", "abyss farm"], attribution, cited)}

    assert stats["ritual farm"].discovered == 2
    assert stats["ritual farm"].cited == 1
    assert stats["ritual farm"].citation_rate == 0.5
    assert stats["ritual farm"].drop_candidate is False

    assert stats["abyss farm"].discovered == 1
    assert stats["abyss farm"].cited == 0
    assert stats["abyss farm"].drop_candidate is True  # configured but earns nothing


def test_score_queries_flags_configured_query_with_no_chunks():
    stats = {s.query: s for s in score_queries(["dead query"], [], set())}
    s = stats["dead query"]
    assert s.discovered == 0 and s.cited == 0
    assert s.citation_rate == 0.0
    assert s.drop_candidate is True


def test_score_queries_reports_drift_without_flagging_it():
    # a query present only in historical data (config was edited) is surfaced but NOT a drop
    # candidate — we don't pay quota for it anymore.
    attribution = [{"source_url": "u1", "discovery_query": "old query"}]
    stats = {s.query: s for s in score_queries(["new query"], attribution, {"u1"})}
    assert stats["old query"].configured is False
    assert stats["old query"].drop_candidate is False
    assert stats["old query"].cited == 1
    assert stats["new query"].configured is True


def test_score_queries_ignores_blank_attribution_and_sorts_by_citations():
    attribution = [
        {"source_url": "u1", "discovery_query": ""},  # blank query skipped
        {"source_url": "u2", "discovery_query": "  "},
        {"source_url": "u3", "discovery_query": "good"},
        {"source_url": "u4", "discovery_query": "good"},
        {"source_url": "u5", "discovery_query": "ok"},
    ]
    cited = {"u3", "u4", "u5"}
    ordered = [s.query for s in score_queries(["good", "ok"], attribution, cited)]
    assert ordered == ["good", "ok"]  # 2 citations before 1


def test_score_queries_dedupes_and_trims_configured():
    stats = score_queries([" q ", "q", ""], [], set())
    assert [s.query for s in stats] == ["q"]


def test_render_report_marks_keep_drop_and_drift():
    attribution = [
        {"source_url": "u1", "discovery_query": "keepme"},
        {"source_url": "u2", "discovery_query": "drifted"},
    ]
    stats = score_queries(["keepme", "dropme"], attribution, {"u1"})
    out = render_report(stats)
    assert "keep" in out
    assert "⚠️ drop candidate" in out
    assert "drift (not in config)" in out
    assert "## Drop candidates" in out
    assert "dropme" in out
    assert "drifted" in out


def test_render_report_empty():
    assert "No query-attributed knowledge yet" in render_report([])


def test_render_report_no_drop_candidates_line():
    stats = score_queries(["q"], [{"source_url": "u", "discovery_query": "q"}], {"u"})
    out = render_report(stats)
    assert "every configured query pays off" in out


def test_build_report_wires_live_reads(monkeypatch):
    import collector.config as config
    # build_report does `from collector.config import get_settings` at call time, so patching the
    # source module's attribute is what takes effect.
    monkeypatch.setattr(config, "get_settings", lambda: Settings(
        youtube_queries="alpha,beta", poe2_league="L"
    ))

    class _Repo:
        @staticmethod
        def latest_farm_guides(league):
            assert league == "L"
            return [{"sources": [{"url": "u1"}]}]

        @staticmethod
        def latest_craft_guides(league):
            return [{"sources": [{"url": "u2"}]}]

        @staticmethod
        def latest_farm_strategies(league):
            return [{"sources": [{"url": "u3"}]}]

        @staticmethod
        def knowledge_query_attribution():
            return [
                {"source_url": "u1", "discovery_query": "alpha"},
                {"source_url": "x", "discovery_query": "beta"},
            ]

    import db.repo as real_repo
    for name in ("latest_farm_guides", "latest_craft_guides", "latest_farm_strategies",
                 "knowledge_query_attribution"):
        monkeypatch.setattr(real_repo, name, getattr(_Repo, name))

    out = build_report()
    assert "alpha" in out and "beta" in out
    assert "⚠️ drop candidate" in out  # beta discovered "x", never cited


def test_main_run_dispatches(monkeypatch, capsys):
    monkeypatch.setattr(qs, "build_report", lambda: "REPORT_BODY")
    assert _main(["prog", "run"]) == 0
    assert "REPORT_BODY" in capsys.readouterr().out


def test_main_unknown_command_returns_2():
    assert _main(["prog", "bogus"]) == 2
