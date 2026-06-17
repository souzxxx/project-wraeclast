from collector.add_knowledge import _strip_html, build_doc_from_text


def test_build_doc_from_text_defaults_title_and_stable_id():
    doc = build_doc_from_text("Line one about farming\nmore detail")
    assert doc.title == "Line one about farming"
    assert doc.source_url.startswith("manual:")
    # deterministic id for same text
    assert build_doc_from_text("Line one about farming\nmore detail").source_url == doc.source_url


def test_build_doc_from_text_explicit_title():
    doc = build_doc_from_text("body", title="My note")
    assert doc.title == "My note"
    assert doc.content == "body"


def test_strip_html_extracts_title_and_text():
    title, text = _strip_html(
        "<html><head><title>Guide</title></head><body><script>x()</script>"
        "<p>Farm <b>breach</b></p></body></html>"
    )
    assert title == "Guide"
    assert "Farm breach" in text
    assert "x()" not in text  # script removed
