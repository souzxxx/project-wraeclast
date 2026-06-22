"""Offline tests for ingest doc-filtering (the path that runs before any embed/DB call)."""

from collector.ingest import KnowledgeDoc, ingest_documents


def test_filters_docs_without_url_or_content_and_short_circuits():
    # docs missing source_url or content are dropped; an all-invalid batch returns 0 WITHOUT
    # ever calling the embeddings API or the DB (so this is safe to run offline).
    n = ingest_documents([
        KnowledgeDoc(source_url="", title="t", content="x"),
        KnowledgeDoc(source_url="u", title="t", content=""),
    ])
    assert n == 0


def test_empty_batch_returns_zero():
    assert ingest_documents([]) == 0
