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
    glm_api_key: str = ""
    glm_base_url: str = "https://api.z.ai/api/openai/v1"
    glm_chat_model: str = "glm-4.7-flash"
    glm_curation_model: str = "glm-4.7-flash"
    embeddings_api_key: str = ""
    embeddings_base_url: str = "https://api.z.ai/api/openai/v1"
    embeddings_model: str = "embedding-2"
    embedding_dim: int = 1024

    # ── Database ──
    neon_database_url: str = ""

    # ── poe.ninja ──
    # League is read from config, never hardcoded to a specific league string in code.
    # PoE2 0.5.0 challenge league per the spec. Confirm the exact poe.ninja slug with
    # `python -m collector.ninja_client explore` (NOTE: "Mirage" is a PoE1 league — not this).
    poe2_league: str = "Return of the Ancients"
    ninja_base_url: str = "https://poe.ninja"
    ninja_economy_path: str = "/api/data/currencyoverview"
    ninja_item_path: str = "/api/data/itemoverview"
    ninja_builds_base: str = "https://poe.ninja/poe2/builds"
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
