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


def test_embed_texts_batches_and_preserves_order(monkeypatch):
    import collector.ingest as ing

    calls: list[int] = []

    class _Item:
        def __init__(self, e):
            self.embedding = e

    class _Resp:
        def __init__(self, data):
            self.data = data

    class _Emb:
        def create(self, model, input, dimensions):  # noqa: A002 - mirrors the SDK kwarg
            calls.append(len(input))
            return _Resp([_Item([float(len(t))]) for t in input])

    class _Client:
        embeddings = _Emb()

    monkeypatch.setattr(ing, "_embeddings_client", lambda: _Client())
    monkeypatch.setattr(ing, "_EMBED_BATCH", 3)
    out = ing.embed_texts(["a", "bb", "ccc", "dddd", "eeeee"])  # 5 texts, batch 3 -> 3 + 2
    assert calls == [3, 2]
    assert out == [[1.0], [2.0], [3.0], [4.0], [5.0]]  # order preserved across batches
