"""Offline tests for the curated craft seed corpus (pure data — no DB/network needed)."""

from collector.seed_knowledge import seed_documents
from collector.topics import CRAFT

_MAX_CHARS = 8000  # mirrors ingest._MAX_CHARS (the embedding window); local to stay import-light


def test_seed_docs_present_and_well_formed():
    docs = seed_documents()
    assert len(docs) >= 4
    for d in docs:
        assert d.source_url.startswith("http")
        assert d.title.strip()
        assert len(d.content) > 200  # a real note, not a stub
        assert len(d.content) <= _MAX_CHARS  # fits the embedding window in ingest


def test_seed_docs_are_tagged_craft():
    # The whole seed corpus is the craft lane — chat must be able to filter to it.
    for d in seed_documents():
        assert d.topic == CRAFT


def test_seed_source_urls_unique():
    # source_url is the dedup/upsert key — duplicates would collide in knowledge_chunk.
    urls = [d.source_url for d in seed_documents()]
    assert len(urls) == len(set(urls))


def test_seed_covers_core_craft_topics():
    blob = " ".join(f"{d.title} {d.content}" for d in seed_documents()).lower()
    for keyword in ("essence", "omen", "whittling", "exalted", "transmutation", "item level"):
        assert keyword in blob, f"seed corpus is missing core craft topic: {keyword}"
