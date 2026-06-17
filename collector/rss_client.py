"""RSS/Atom feed collector for community/meta knowledge.

Syndication feeds are meant to be consumed, so this is an unambiguously fine automatic
source. Parses both RSS 2.0 and Atom with the stdlib (no extra dependency). Configure feeds
via RSS_FEEDS (comma-separated). Empty -> step is skipped.

CLI:
    python -m collector.rss_client run
"""

from __future__ import annotations

import asyncio
import re
from xml.etree import ElementTree as ET

from collector.config import Settings, get_settings
from collector.http import HttpClient
from collector.ingest import KnowledgeDoc

UA = "Project-Wraeclast/0.1 (contact: souzxxx)"


def _local(tag: str) -> str:
    """Strip XML namespace: '{http://www.w3.org/2005/Atom}entry' -> 'entry'."""
    return tag.rsplit("}", 1)[-1].lower()


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def _find_child(node: ET.Element, name: str) -> ET.Element | None:
    for child in node:
        if _local(child.tag) == name:
            return child
    return None


def _link_of(node: ET.Element) -> str:
    for child in node:
        if _local(child.tag) == "link":
            href = child.get("href")
            if href:
                return href
            if child.text:
                return child.text.strip()
    return ""


def parse_feed(xml_text: str) -> list[KnowledgeDoc]:
    """Parse RSS 2.0 (<item>) or Atom (<entry>) into KnowledgeDocs. Defensive."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    docs: list[KnowledgeDoc] = []
    for node in root.iter():
        if _local(node.tag) not in ("item", "entry"):
            continue
        title_el = _find_child(node, "title")
        title = _strip_html(title_el.text if title_el is not None else "")
        # NB: an ElementTree element with no children is falsy, so select with explicit
        # `is not None` checks — never an `or` chain (that would drop text-only elements).
        body_el = None
        for name in ("description", "summary", "content", "encoded"):
            found = _find_child(node, name)
            if found is not None:
                body_el = found
                break
        body = _strip_html(body_el.text if body_el is not None else "")
        url = _link_of(node)
        if not url or not title:
            continue
        docs.append(KnowledgeDoc(source_url=url, title=title, content=f"{title}\n\n{body}".strip()))
    return docs


async def fetch_rss(settings: Settings | None = None) -> list[KnowledgeDoc]:
    settings = settings or get_settings()
    docs: list[KnowledgeDoc] = []
    seen: set[str] = set()
    accept = {"Accept": "application/rss+xml, application/xml, */*"}
    async with HttpClient(UA, headers=accept) as http:
        for feed in settings.rss_feed_list:
            try:
                resp = await http._client.get(feed)  # raw text, not JSON
                resp.raise_for_status()
                for doc in parse_feed(resp.text):
                    if doc.source_url not in seen:
                        seen.add(doc.source_url)
                        docs.append(doc)
            except Exception:  # noqa: BLE001 — a bad feed shouldn't kill the run
                continue
    return docs


async def run() -> int:
    from collector.ingest import ingest_documents

    docs = await fetch_rss()
    n = ingest_documents(docs)
    print(f"knowledge_chunk: ingested {n} RSS items")
    return n


if __name__ == "__main__":
    raise SystemExit(0 if asyncio.run(run()) >= 0 else 1)
