"""Offline tests for deterministic source citation (collector.source_refs).

The LLM cites a knowledge entry by its ordinal [n]; we resolve [n] back to the chunk's REAL
source_url here, so guide `sources` carry the actual URL the query-productivity analyzer
(collector.query_stats) crosses against discovery_query attribution.
"""

from collector.source_refs import number_knowledge, resolve_source_refs


def test_number_knowledge_numbers_lines_and_builds_ref_map():
    knowledge = [
        {"source_url": "https://www.youtube.com/watch?v=A", "title": "Ritual guide",
         "content": "run rituals"},
        {"source_url": "https://www.youtube.com/watch?v=B", "title": "Abyss guide",
         "content": "open abyss"},
    ]
    text, ref_map = number_knowledge(knowledge, content_chars=700)
    assert "[1] Ritual guide: run rituals" in text
    assert "[2] Abyss guide: open abyss" in text
    assert ref_map == [
        {"url": "https://www.youtube.com/watch?v=A", "title": "Ritual guide"},
        {"url": "https://www.youtube.com/watch?v=B", "title": "Abyss guide"},
    ]


def test_number_knowledge_labels_with_url_when_title_missing_but_keeps_url_in_map():
    text, ref_map = number_knowledge(
        [{"source_url": "https://www.youtube.com/watch?v=A", "content": "c"}]
    )
    assert "[1] https://www.youtube.com/watch?v=A: c" in text
    assert ref_map[0]["url"] == "https://www.youtube.com/watch?v=A"


def test_number_knowledge_truncates_content():
    text, _ = number_knowledge([{"title": "T", "content": "x" * 5000}], content_chars=10)
    assert "[1] T: " + "x" * 10 in text
    assert "x" * 11 not in text


def test_resolve_source_refs_maps_one_based_ints_to_real_urls():
    ref_map = [
        {"url": "https://www.youtube.com/watch?v=A", "title": "A"},
        {"url": "https://www.youtube.com/watch?v=B", "title": "B"},
    ]
    assert resolve_source_refs([2, 1], ref_map) == [
        {"url": "https://www.youtube.com/watch?v=B", "title": "B"},
        {"url": "https://www.youtube.com/watch?v=A", "title": "A"},
    ]


def test_resolve_source_refs_ignores_out_of_range_zero_and_dupes_preserving_order():
    ref_map = [{"url": "u1", "title": "A"}, {"url": "u2", "title": "B"}]
    assert resolve_source_refs([0, 3, 1, 1, 2, -4], ref_map) == [
        {"url": "u1", "title": "A"},
        {"url": "u2", "title": "B"},
    ]


def test_resolve_source_refs_accepts_numeric_strings_ignores_non_numeric():
    ref_map = [{"url": "u1", "title": "A"}]
    assert resolve_source_refs(["1", "abc", None], ref_map) == [{"url": "u1", "title": "A"}]


def test_resolve_source_refs_drops_entries_with_empty_url():
    ref_map = [{"url": "", "title": "no-url"}, {"url": "u2", "title": "B"}]
    assert resolve_source_refs([1, 2], ref_map) == [{"url": "u2", "title": "B"}]


def test_resolve_source_refs_tolerates_non_list():
    assert resolve_source_refs(None, [{"url": "u1", "title": "A"}]) == []
    assert resolve_source_refs("1,2", [{"url": "u1", "title": "A"}]) == []


def test_resolved_refs_link_to_attribution_end_to_end():
    # The linkage PR #27 originally lacked: a chunk's REAL source_url, surfaced into the guide's
    # sources via a numeric ref, now matches that chunk's discovery_query attribution → cited > 0.
    from collector.query_stats import collect_cited_urls, score_queries

    chunk = {"source_url": "https://www.youtube.com/watch?v=ID", "title": "Ritual", "content": "c"}
    _, ref_map = number_knowledge([chunk])
    guide_sources = resolve_source_refs([1], ref_map)  # LLM said it used knowledge [1]

    cited = collect_cited_urls(guide_sources)
    attribution = [{"source_url": chunk["source_url"], "discovery_query": "ritual farm"}]
    [stat] = score_queries(["ritual farm"], attribution, cited)

    assert stat.cited == 1
    assert stat.drop_candidate is False
