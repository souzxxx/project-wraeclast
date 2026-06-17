"""Embedding + persistence into knowledge_chunk.

Embeddings go through any OpenAI-compatible endpoint (Gemini by default). The vector
dimension must match EMBEDDING_DIM / the DB column (see migration 0001).

`KnowledgeDoc` is the common shape every source (YouTube, RSS, manual) produces; they all
funnel through `ingest_documents`.
"""

from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from collector.config import get_settings
from db.models import KnowledgeChunk
from db.repo import upsert_knowledge_chunk

_MAX_CHARS = 8000  # keep each chunk within a sane embedding window


@dataclass
class KnowledgeDoc:
    """A piece of qualitative community knowledge, ready to embed + store."""

    source_url: str
    title: str
    content: str


def _embeddings_client() -> OpenAI:
    s = get_settings()
    key = s.embeddings_api_key or s.glm_api_key
    if not key:
        raise RuntimeError("No embeddings API key (EMBEDDINGS_API_KEY/GLM_API_KEY).")
    return OpenAI(api_key=key, base_url=s.embeddings_base_url)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return one embedding vector per input text."""
    if not texts:
        return []
    settings = get_settings()
    client = _embeddings_client()
    # Request the target dimension (Matryoshka truncation) so the vector matches the DB column
    # regardless of the model's native size (e.g. gemini-embedding-001 is 3072 by default).
    resp = client.embeddings.create(
        model=settings.embeddings_model,
        input=[t[:_MAX_CHARS] for t in texts],
        dimensions=settings.embedding_dim,
    )
    return [item.embedding for item in resp.data]


def ingest_documents(docs: list[KnowledgeDoc]) -> int:
    """Embed each document and upsert into knowledge_chunk (dedup by source_url)."""
    docs = [d for d in docs if d.source_url and d.content]
    if not docs:
        return 0
    vectors = embed_texts([d.content for d in docs])
    for doc, vector in zip(docs, vectors, strict=True):
        upsert_knowledge_chunk(
            KnowledgeChunk(
                source_url=doc.source_url, title=doc.title, content=doc.content, embedding=vector
            )
        )
    return len(docs)
