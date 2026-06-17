import time

from collector.community_scraper import CommunityPost, _select, parse_listing


def _post(url, score, age_days):
    return CommunityPost(
        url=url, title="t", content="c", score=score,
        created_utc=time.time() - age_days * 86400,
    )


def test_select_filters_by_score_and_age_and_dedups():
    posts = [
        _post("a", 100, 1),
        _post("a", 100, 1),     # duplicate URL
        _post("b", 5, 1),       # below min score
        _post("c", 80, 30),     # too old
        _post("d", 50, 2),
    ]
    out = _select(posts, min_score=25, max_age_days=7)
    urls = [p.url for p in out]
    assert urls == ["a", "d"]   # sorted by score desc, deduped, filtered


def test_parse_listing_defensive():
    payload = {
        "data": {
            "children": [
                {"data": {"permalink": "/r/x/1", "title": "Hello", "selftext": "body",
                          "score": 42, "created_utc": 1.0}},
                {"data": {"title": "no permalink"}},  # skipped
            ]
        }
    }
    posts = parse_listing(payload)
    assert len(posts) == 1
    assert posts[0].url == "https://www.reddit.com/r/x/1"
    assert posts[0].score == 42
    assert "Hello" in posts[0].content
