"""Embedding + persistence into knowledge_chunk.

Embeddings go through any OpenAI-compatible endpoint (z.ai by default). The vector
dimension must match EMBEDDING_DIM / the DB column (see migration 0001).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from openai import OpenAI

from collector.config import get_settings
from db.models import KnowledgeChunk
from db.repo import upsert_knowledge_chunk

if TYPE_CHECKING:
    from collector.community_scraper import CommunityPost

_MAX_CHARS = 8000  # keep each chunk within a sane embedding window


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
    client = _embeddings_client()
    model = get_settings().embeddings_model
    resp = client.embeddings.create(model=model, input=[t[:_MAX_CHARS] for t in texts])
    return [item.embedding for item in resp.data]


def ingest_posts(posts: list[CommunityPost]) -> int:
    """Embed each post and upsert into knowledge_chunk (dedup by URL)."""
    if not posts:
        return 0
    vectors = embed_texts([p.content for p in posts])
    written = 0
    for post, vector in zip(posts, vectors, strict=True):
        upsert_knowledge_chunk(
            KnowledgeChunk(
                source_url=post.url, title=post.title, content=post.content, embedding=vector
            )
        )
        written += 1
    return written
