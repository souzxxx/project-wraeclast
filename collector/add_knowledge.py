"""Manual knowledge curation — the owner drops in a URL or raw text they found valuable.

This is the policy-clean way to capture community gold (a Reddit post, a guide, a tweet):
the owner curating what they've personally read, not automated bulk scraping. Reused by the
`/ingest` API endpoint.

CLI:
    python -m collector.add_knowledge "https://example.com/great-farming-guide"
    python -m collector.add_knowledge "Some farming notes I want to remember..."
"""

from __future__ import annotations

import hashlib
import re
import sys

import httpx

from collector.ingest import KnowledgeDoc, ingest_documents

UA = "Mozilla/5.0 (compatible; Project-Wraeclast/0.1; +contact souzxxx)"


def _strip_html(html: str) -> tuple[str, str]:
    """Return (title, text) from raw HTML."""
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""
    body = re.sub(r"(?is)<(script|style|nav|header|footer|svg|noscript)[^>]*>.*?</\1>", " ", html)
    body = re.sub(r"(?is)<[^>]+>", " ", body)
    body = re.sub(r"\s+", " ", body).strip()
    return title, body


def build_doc_from_text(text: str, title: str | None = None) -> KnowledgeDoc:
    text = text.strip()
    if not title:
        title = (text.splitlines()[0] if text else "note")[:120]
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    return KnowledgeDoc(source_url=f"manual:{digest}", title=title, content=text)


def build_doc_from_url(url: str, title: str | None = None) -> KnowledgeDoc:
    resp = httpx.get(url, headers={"User-Agent": UA}, timeout=25, follow_redirects=True)
    resp.raise_for_status()
    page_title, text = _strip_html(resp.text)
    content = f"{title or page_title}\n\n{text}"[:8000].strip()
    return KnowledgeDoc(source_url=url, title=title or page_title or url, content=content)


def ingest_input(value: str, title: str | None = None) -> KnowledgeDoc:
    """Build a doc from a URL or raw text, persist it, and return the doc."""
    value = value.strip()
    doc = (
        build_doc_from_url(value, title)
        if re.match(r"^https?://", value)
        else build_doc_from_text(value, title)
    )
    ingest_documents([doc])
    return doc


def _main(argv: list[str]) -> int:
    if len(argv) < 2:
        print('usage: python -m collector.add_knowledge "<url or text>"', file=sys.stderr)
        return 2
    doc = ingest_input(argv[1])
    print(f"ingested: {doc.title[:70]} ({doc.source_url})")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
