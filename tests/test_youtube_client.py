from collector.youtube_client import parse_search_ids, videos_to_docs


def test_parse_search_ids():
    payload = {
        "items": [
            {"id": {"videoId": "abc"}, "snippet": {"title": "x"}},
            {"id": {"kind": "channel"}},  # no videoId -> skipped
            {"id": {"videoId": "def"}},
        ]
    }
    assert parse_search_ids(payload) == ["abc", "def"]


def test_videos_to_docs_builds_full_content():
    payload = {
        "items": [
            {
                "id": "abc",
                "snippet": {
                    "title": "32 Div/h Ritual Farming",
                    "description": "Step 1... step 2...",
                    "channelTitle": "MisoxShiru",
                },
            },
            {"id": "no", "snippet": {"description": "no title"}},  # skipped (no title)
        ]
    }
    docs = videos_to_docs(payload)
    assert len(docs) == 1
    d = docs[0]
    assert d.source_url == "https://www.youtube.com/watch?v=abc"
    assert d.title == "32 Div/h Ritual Farming"
    assert "MisoxShiru" in d.content and "Step 1" in d.content


def test_videos_to_docs_empty():
    assert videos_to_docs({}) == []
    assert videos_to_docs({"items": None}) == []
