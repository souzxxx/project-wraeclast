from collector.rss_client import parse_feed

RSS2 = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Feed</title>
  <item><title>Best Breach Farm</title><link>https://site/a</link>
    <description>&lt;p&gt;Run breach for &lt;b&gt;exalts&lt;/b&gt;.&lt;/p&gt;</description></item>
  <item><title>No link here</title></item>
</channel></rss>"""

ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><title>Atlas strategy</title>
    <link href="https://site/b"/><summary>Tower setup tips</summary></entry>
</feed>"""


def test_parse_rss2():
    docs = parse_feed(RSS2)
    assert len(docs) == 1  # the link-less item is dropped
    assert docs[0].source_url == "https://site/a"
    assert docs[0].title == "Best Breach Farm"
    assert "exalts" in docs[0].content and "<b>" not in docs[0].content  # html stripped


def test_parse_atom():
    docs = parse_feed(ATOM)
    assert docs[0].source_url == "https://site/b"
    assert "Tower setup tips" in docs[0].content


def test_parse_garbage_returns_empty():
    assert parse_feed("not xml at all") == []
    assert parse_feed("") == []
