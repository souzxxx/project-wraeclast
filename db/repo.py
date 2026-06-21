"""Data-access functions. All SQL lives here so collectors and the API share one source.

Vectors are passed as the pgvector text literal `[a,b,c]`; psycopg sends it as text and
Postgres casts to VECTOR on insert/compare.
"""

from __future__ import annotations

import json
from typing import Any

from db.connection import execute, fetch_all, get_connection
from db.models import CraftMethod, FarmStrategy, KnowledgeChunk, MySnapshot, PriceSnapshot


def _vec_literal(embedding: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in embedding) + "]"


# ── writes ──────────────────────────────────────────────────────────────────────

def insert_price_snapshots(rows: list[PriceSnapshot]) -> int:
    if not rows:
        return 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO price_snapshot
                   (league, item_type, name, chaos_value, divine_value, listing_count)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                [
                    (r.league, r.item_type, r.name, r.chaos_value, r.divine_value, r.listing_count)
                    for r in rows
                ],
            )
        conn.commit()
    return len(rows)


def insert_farm_strategies(rows: list[FarmStrategy]) -> int:
    if not rows:
        return 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO farm_strategy
                   (league, name, est_profit_per_hour, investment_required, risk, summary, sources)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [
                    (
                        r.league, r.name, r.est_profit_per_hour, r.investment_required,
                        r.risk, r.summary, json.dumps(r.sources),
                    )
                    for r in rows
                ],
            )
        conn.commit()
    return len(rows)


def insert_my_snapshot(snap: MySnapshot) -> None:
    execute(
        """INSERT INTO my_snapshot
           (character_name, char_class, level, total_currency_chaos, gear, gems, passive_tree)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (
            snap.character_name, snap.char_class, snap.level, snap.total_currency_chaos,
            json.dumps(snap.gear), json.dumps(snap.gems), json.dumps(snap.passive_tree),
        ),
    )


def upsert_knowledge_chunk(chunk: KnowledgeChunk) -> None:
    """Dedup by source_url (see skill §3). Re-running a day refreshes content/embedding."""
    embedding = _vec_literal(chunk.embedding) if chunk.embedding is not None else None
    execute(
        """INSERT INTO knowledge_chunk (source_url, title, content, embedding, topic)
           VALUES (%s, %s, %s, %s, %s)
           ON CONFLICT (source_url) DO UPDATE
             SET title = EXCLUDED.title,
                 content = EXCLUDED.content,
                 embedding = EXCLUDED.embedding,
                 topic = EXCLUDED.topic,
                 captured_at = now()""",
        (chunk.source_url, chunk.title, chunk.content, embedding, chunk.topic),
    )


# ── reads ───────────────────────────────────────────────────────────────────────

def latest_prices(league: str, limit: int = 500) -> list[dict[str, Any]]:
    return fetch_all(
        """SELECT DISTINCT ON (name, item_type) name, item_type, chaos_value, divine_value,
                  listing_count, captured_at
           FROM price_snapshot WHERE league = %s
           ORDER BY name, item_type, captured_at DESC
           LIMIT %s""",
        (league, limit),
    )


def latest_farm_strategies(league: str, limit: int = 20) -> list[dict[str, Any]]:
    return fetch_all(
        """SELECT name, est_profit_per_hour, investment_required, risk, summary, sources,
                  captured_at
           FROM farm_strategy
           WHERE league = %s
             AND captured_at = (SELECT max(captured_at) FROM farm_strategy WHERE league = %s)
           ORDER BY est_profit_per_hour DESC NULLS LAST
           LIMIT %s""",
        (league, league, limit),
    )


def latest_my_snapshot() -> dict[str, Any] | None:
    rows = fetch_all("SELECT * FROM my_snapshot ORDER BY captured_at DESC LIMIT 1")
    return rows[0] if rows else None


def replace_farm_guides(league: str, guides: list[dict[str, Any]]) -> int:
    """Replace this league's guides with a fresh batch (kept stable/curated, not appended)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM farm_guide WHERE league = %s", (league,))
            cur.executemany(
                """INSERT INTO farm_guide
                   (league, name, profit_per_hour, risk, target_currency, overview,
                    steps, items, atlas, faq, sources)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    (
                        league, g.get("name"), g.get("profit_per_hour"), g.get("risk"),
                        g.get("target_currency"), g.get("overview"),
                        json.dumps(g.get("steps", [])), json.dumps(g.get("items", [])),
                        g.get("atlas"), json.dumps(g.get("faq", [])),
                        json.dumps(g.get("sources", [])),
                    )
                    for g in guides
                ],
            )
        conn.commit()
    return len(guides)


def replace_craft_methods(league: str, methods: list[CraftMethod]) -> int:
    """Replace this league's craft methods with a fresh batch (curated/seeded, not appended) —
    idempotent daily re-seed, mirroring replace_farm_guides."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM craft_method WHERE league = %s", (league,))
            cur.executemany(
                """INSERT INTO craft_method
                   (league, name, item_base, archetype, target_mods, steps, inputs,
                    success_prob, output, sources, notes)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    (
                        m.league, m.name, m.item_base, m.archetype,
                        json.dumps(m.target_mods), json.dumps(m.steps), json.dumps(m.inputs),
                        m.success_prob, m.output, json.dumps(m.sources), m.notes,
                    )
                    for m in methods
                ],
            )
        conn.commit()
    return len(methods)


def latest_craft_methods(league: str) -> list[dict[str, Any]]:
    """This league's structured craft methods (newest batch), for the EV engine + Craft tab."""
    return fetch_all(
        """SELECT name, item_base, archetype, target_mods, steps, inputs, success_prob,
                  output, sources, notes, captured_at
           FROM craft_method WHERE league = %s
           ORDER BY captured_at DESC, name""",
        (league,),
    )


def latest_knowledge_chunks(limit: int = 80) -> list[dict[str, Any]]:
    """Newest community knowledge (deduped by URL via the table's unique index), for the graph."""
    return fetch_all(
        "SELECT source_url, title FROM knowledge_chunk ORDER BY captured_at DESC LIMIT %s",
        (limit,),
    )


def latest_craft_knowledge(limit: int = 30) -> list[dict[str, Any]]:
    """Newest craft-lane knowledge chunks (topic='craft') for the Craft tab guides."""
    return fetch_all(
        """SELECT source_url, title, content, captured_at FROM knowledge_chunk
           WHERE topic = 'craft'
           ORDER BY captured_at DESC LIMIT %s""",
        (limit,),
    )


def latest_farm_guides(league: str) -> list[dict[str, Any]]:
    return fetch_all(
        """SELECT name, profit_per_hour, risk, target_currency, overview, steps, items, atlas,
                  faq, sources, captured_at
           FROM farm_guide WHERE league = %s
           ORDER BY profit_per_hour DESC NULLS LAST""",
        (league,),
    )


def farm_strategies_since(league: str, days: int = 3) -> list[dict[str, Any]]:
    """Recent farm strategies (multiple runs) for the day-over-day insight diff."""
    return fetch_all(
        """SELECT name, est_profit_per_hour, risk, summary, sources, captured_at
           FROM farm_strategy
           WHERE league = %s AND captured_at >= now() - make_interval(days => %s)
           ORDER BY captured_at DESC, est_profit_per_hour DESC NULLS LAST""",
        (league, days),
    )


def price_snapshots_since(league: str, days: int = 3) -> list[dict[str, Any]]:
    """Recent price snapshots (multiple runs) for the day-over-day insight diff."""
    return fetch_all(
        """SELECT name, item_type, chaos_value, divine_value, captured_at
           FROM price_snapshot
           WHERE league = %s AND captured_at >= now() - make_interval(days => %s)
           ORDER BY captured_at DESC""",
        (league, days),
    )


def price_history_since(league: str, days: int = 14) -> list[dict[str, Any]]:
    """Currency price snapshots over a recent window, for the 'Hoje' tab sparklines."""
    return fetch_all(
        """SELECT name, item_type, chaos_value, captured_at
           FROM price_snapshot
           WHERE league = %s AND item_type = 'currency'
             AND captured_at >= now() - make_interval(days => %s)
           ORDER BY captured_at""",
        (league, days),
    )


def knowledge_chunks_since(days: int = 2) -> list[dict[str, Any]]:
    """Knowledge captured in the recent window, for the 'new sources today' insight section."""
    return fetch_all(
        """SELECT source_url, title, captured_at FROM knowledge_chunk
           WHERE captured_at >= now() - make_interval(days => %s)
           ORDER BY captured_at DESC""",
        (days,),
    )


def search_knowledge(
    embedding: list[float], limit: int = 6, topic: str | None = None
) -> list[dict[str, Any]]:
    """Cosine-similarity retrieval for RAG. Returns closest chunks first. When `topic` is given,
    restrict to that lane (e.g. 'craft') so craft questions aren't diluted by farm chunks."""
    vec = _vec_literal(embedding)
    topic_clause = "AND topic = %s" if topic else ""
    params: list[Any] = [vec]
    if topic:
        params.append(topic)
    params += [vec, limit]
    return fetch_all(
        f"""SELECT source_url, title, content, topic,
                  1 - (embedding <=> %s::vector) AS similarity
           FROM knowledge_chunk
           WHERE embedding IS NOT NULL {topic_clause}
           ORDER BY embedding <=> %s::vector
           LIMIT %s""",
        tuple(params),
    )
