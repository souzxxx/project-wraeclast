"""Typed runtime configuration, loaded from environment (.env locally).

Golden rule from CLAUDE.md: never hardcode secrets, never hardcode the league.
Everything that varies between environments lives here and is read from env.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ── LLM (GLM via z.ai, OpenAI-compatible) ──
    # Coding Plan uses the coding endpoint; the general /paas endpoint needs separate balance.
    glm_api_key: str = ""
    glm_base_url: str = "https://api.z.ai/api/coding/paas/v4"
    glm_chat_model: str = "glm-5.2"
    glm_curation_model: str = "glm-5.2"
    glm_timeout_seconds: float = 180.0
    glm_max_tokens: int = 6000  # glm-5.x are reasoning models — need budget for thinking + answer
    # z.ai Coding Plan has no embeddings; default to Gemini's OpenAI-compatible endpoint
    # (free tier). gemini-embedding-001 defaults to 3072 dims but supports truncation to
    # `dimensions` (Matryoshka) — we request 1024 to fit the DB column + pgvector hnsw (<=2000).
    embeddings_api_key: str = ""
    embeddings_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    embeddings_model: str = "gemini-embedding-001"
    embedding_dim: int = 1024

    # ── Database ──
    neon_database_url: str = ""

    # ── poe.ninja ──
    # League is read from config, never hardcoded in code. The poe.ninja PoE2 economy API
    # wants the DISPLAY NAME (with spaces), e.g. "Runes of Aldur" — not the URL slug.
    # (NOTE: "Mirage" is a PoE1 league; PoE2 uses 0.x versioning. Confirm via `explore`.)
    poe2_league: str = "Runes of Aldur"
    ninja_base_url: str = "https://poe.ninja"
    # PoE2 economy = the currency-exchange overview (confirmed live; classic /api/data 404s).
    ninja_economy_path: str = "/poe2/api/economy/exchange/0/overview"
    ninja_economy_type: str = "Currency"
    # PoE2 public profile characters: <base>/<account>/<version> returns a JSON list of chars.
    ninja_profile_path: str = "/poe2/api/profile/characters"
    ninja_account: str = ""
    ninja_character: str = ""

    # ── Community scraper ──
    reddit_user_agent: str = "Project-Wraeclast/0.1 (contact: souzxxx)"
    reddit_subreddit: str = "PathOfExile2"
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    scraper_min_score: int = 25
    scraper_max_age_days: int = 7

    # ── GGG OAuth (Phase 2, optional) ──
    ggg_client_id: str = ""
    ggg_client_secret: str = ""
    ggg_redirect_uri: str = ""
    ggg_user_agent: str = "Project-Wraeclast/0.1 (contact: souzxxx)"

    # ── API server ──
    internal_run_token: str = ""
    # Shared password gating /chat (the only endpoint that spends GLM/embeddings quota).
    # The owner enters it once in the site; it is NOT baked into the frontend bundle.
    # If empty, /chat is disabled (fail-closed) so an unconfigured deploy can't be abused.
    chat_access_token: str = ""
    cors_origins: str = "http://localhost:3000"

    # ── Obsidian ──
    obsidian_vault_dir: str = "./vault"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton. Tests can clear the cache via get_settings.cache_clear()."""
    return Settings()
