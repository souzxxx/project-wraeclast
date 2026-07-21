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
    glm_timeout_seconds: float = 300.0  # headroom for long 16k-token guide answers (was 180)
    # The /chat path runs on Vercel (function time limit), so it uses a SHORTER timeout than the
    # Actions-side guide batches — it must finish well before the serverless function is killed.
    glm_chat_timeout_seconds: float = 90.0
    # glm-5.x are reasoning models — budget for thinking + a long answer. The daily PT-BR guide
    # batches overran 6000 (truncated mid-JSON); the verbose FARM batch (atlas trees etc.) still
    # truncated at 16000, so go to 24000. The guide parsers also salvage complete guides if a
    # response is still cut off, so this is a generous ceiling, not a guarantee.
    glm_max_tokens: int = 24000
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
    # Current game patch — used as a LABEL for generated guides so they don't claim a stale
    # version. Bump via env when GGG ships a patch (live as of 2026-06-26: 0.5.4). Guide CONTENT
    # is grounded in live data (EV-ranked methods + prices + corpus), not in this number.
    poe2_patch: str = "0.5.4"
    ninja_base_url: str = "https://poe.ninja"
    # PoE2 economy = the currency-exchange overview (confirmed live; classic /api/data 404s).
    ninja_economy_path: str = "/poe2/api/economy/exchange/0/overview"
    ninja_economy_type: str = "Currency"  # single type used by the `explore` CLI
    # The full craft surface lives across several poe.ninja "type" categories (confirmed via
    # exploratory GETs, 2026-06-21). "<NinjaType>:<item_type>" pairs — the EV engine prices a
    # method's inputs by NAME across all of these, while the bench/sparklines still filter to
    # item_type='currency'. Override via env if poe.ninja renames a category.
    ninja_economy_types: str = (
        "Currency:currency,Essences:essence,Runes:rune,SoulCores:soul_core,"
        "Ritual:ritual,Delirium:delirium,Breach:breach,Abyss:abyss,Expedition:expedition"
    )
    # PoE2 public profile characters: <base>/<account>/<version> returns a JSON list of chars.
    ninja_profile_path: str = "/poe2/api/profile/characters"
    ninja_account: str = ""
    ninja_character: str = ""
    # Popular/meta builds ladder (the /build meta source). PoE2 path UNCONFIRMED — config-driven
    # and validated in the deploy with `python -m collector.ninja_meta_client explore`, like the
    # other ninja endpoints were bootstrapped. Aggregation is league-param driven, never hardcoded.
    ninja_builds_path: str = "/poe2/api/builds/overview"
    # Extra candidate builds paths, tried IN ORDER after the primary — the first that responds 200
    # wins and its shape is aggregated defensively. Since the primary route is unconfirmed (and has
    # been 404-ing), this lets the collector self-heal across plausible poe.ninja routes instead of
    # hard-failing on one guess; `.../0/overview` mirrors the CONFIRMED economy path's segment.
    # Comma-separated and env-overridable, so once `explore` pins the real route the owner sets it
    # here with no code change. Empty = try only the primary.
    ninja_builds_fallback_paths: str = "/poe2/api/builds/0/overview"
    ninja_meta_max_chars: int = 200  # cap how many ladder characters feed the aggregate
    ninja_meta_min_usage: float = 0.15  # keep gems used by ≥15% of a class's sample

    # ── Community knowledge sources ──
    # Descriptive User-Agent for all outbound HTTP (ninja, youtube, rss).
    user_agent: str = "Project-Wraeclast/0.1 (contact: souzxxx)"
    # YouTube Data API v3 (official, free tier): the richest legitimate farming + crafting source.
    youtube_api_key: str = ""
    youtube_queries: str = (
        # Farming / atlas strategy.
        "Path of Exile 2 farming strategy,PoE2 best currency farm,PoE2 atlas strategy,"
        "PoE2 tablet tower farming,PoE2 atlas tree guide,"
        # Craft intelligence (epic: rank crafts by calculated EV).
        "PoE2 crafting guide,PoE2 currency crafting,PoE2 crafting for profit,"
        "PoE2 essence crafting,PoE2 omen crafting"
    )
    youtube_max_results: int = 8
    youtube_published_days: int = 21
    # RSS/Atom feeds (syndication is meant to be consumed). Comma-separated; empty = skip.
    rss_feeds: str = ""

    @property
    def youtube_query_list(self) -> list[str]:
        return [q.strip() for q in self.youtube_queries.split(",") if q.strip()]

    @property
    def rss_feed_list(self) -> list[str]:
        return [f.strip() for f in self.rss_feeds.split(",") if f.strip()]

    @property
    def ninja_builds_path_list(self) -> list[str]:
        """Ordered, de-duplicated candidate builds paths: the primary first, then any fallbacks.
        The meta collector tries them in this order and uses the first that responds."""
        out: list[str] = []
        for path in [self.ninja_builds_path, *self.ninja_builds_fallback_paths.split(",")]:
            path = path.strip()
            if path and path not in out:
                out.append(path)
        return out

    @property
    def ninja_economy_category_list(self) -> list[tuple[str, str]]:
        """Parse `ninja_economy_types` into (ninja_type, item_type) pairs. A bare entry with no
        ':' defaults its item_type to 'currency'."""
        pairs: list[tuple[str, str]] = []
        for part in self.ninja_economy_types.split(","):
            ninja_type, _, item_type = part.strip().partition(":")
            ninja_type = ninja_type.strip()
            if ninja_type:
                pairs.append((ninja_type, item_type.strip() or "currency"))
        return pairs

    # ── GGG OAuth (Phase 2, optional) ──
    ggg_client_id: str = ""
    ggg_client_secret: str = ""
    ggg_redirect_uri: str = ""
    ggg_user_agent: str = "Project-Wraeclast/0.1 (contact: souzxxx)"

    # ── API server ──
    # Shared password gating /chat (the only endpoint that spends GLM/embeddings quota).
    # The owner enters it once in the site; it is NOT baked into the frontend bundle.
    # If empty, /chat is disabled (fail-closed) so an unconfigured deploy can't be abused.
    chat_access_token: str = ""
    # Comma-separated allowed browser origins for the API. MUST include the web app's production
    # domain or the browser blocks every fetch (CORS). Defaults below cover local dev + the known
    # Vercel web project; override via CORS_ORIGINS env on the API deploy when the domain changes.
    cors_origins: str = "http://localhost:3000,https://wraeclast-web.vercel.app"

    # ── Obsidian ──
    obsidian_vault_dir: str = "./vault"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton. Tests can clear the cache via get_settings.cache_clear()."""
    return Settings()
