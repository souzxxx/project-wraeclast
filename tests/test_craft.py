"""Offline tests for the craft-knowledge card projection (pure — no DB)."""

from api.craft import craft_cards


def test_projects_title_url_and_snippet():
    rows = [{"source_url": "https://x", "title": "Essence guide", "content": "Use essences."}]
    [c] = craft_cards(rows)
    assert c == {"source_url": "https://x", "title": "Essence guide", "snippet": "Use essences."}


def test_truncates_long_content():
    rows = [{"source_url": "https://x", "title": "T", "content": "a" * 1000}]
    [c] = craft_cards(rows)
    assert len(c["snippet"]) == 400


def test_skips_rows_without_url_or_title():
    rows = [
        {"title": "no url", "content": "x"},
        {"source_url": "https://y", "content": "no title"},
        {"source_url": "https://z", "title": "ok", "content": "keep"},
    ]
    assert [c["title"] for c in craft_cards(rows)] == ["ok"]


def test_tolerates_missing_content():
    [c] = craft_cards([{"source_url": "https://x", "title": "T"}])
    assert c["snippet"] == ""
