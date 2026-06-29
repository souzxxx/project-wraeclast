"""Offline tests for db.repo — the shared data-access layer.

No live DB: get_connection/fetch_all/execute are faked at the db.repo seam, so we assert
the SQL dispatch, parameter marshalling (JSON-encoded list/dict columns, the pgvector text
literal), batch sizes, the DELETE-then-insert replace pattern, and the read projections —
all without a network."""

from __future__ import annotations

import json
from contextlib import contextmanager

import db.repo as repo
from db.models import (
    CraftMethod,
    FarmStrategy,
    KnowledgeChunk,
    MetaBuild,
    MySnapshot,
    PriceSnapshot,
)


class FakeCursor:
    def __init__(self, conn: FakeConn) -> None:
        self._conn = conn

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def execute(self, query: str, params: object = None) -> None:
        self._conn.calls.append(("execute", query, params))

    def executemany(self, query: str, seq: object) -> None:
        self._conn.calls.append(("executemany", query, list(seq)))


class FakeConn:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object]] = []
        self.commits = 0

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1


def _patch_conn(monkeypatch) -> FakeConn:
    """Route db.repo.get_connection at a single recording FakeConn."""
    conn = FakeConn()

    @contextmanager
    def fake_get_connection():
        yield conn

    monkeypatch.setattr(repo, "get_connection", fake_get_connection)
    return conn


def _patch_execute(monkeypatch) -> list[tuple[str, object]]:
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(repo, "execute", lambda q, p=None: calls.append((q, p)))
    return calls


def _patch_fetch(monkeypatch, rows: list[dict]) -> list[tuple[str, object]]:
    calls: list[tuple[str, object]] = []

    def fake_fetch_all(q: str, p: object = None) -> list[dict]:
        calls.append((q, p))
        return rows

    monkeypatch.setattr(repo, "fetch_all", fake_fetch_all)
    return calls


# ── pure helper ──────────────────────────────────────────────────────────────────

def test_vec_literal_formats_floats():
    assert repo._vec_literal([1, 2.5, -0.5]) == "[1.0,2.5,-0.5]"


def test_vec_literal_empty():
    assert repo._vec_literal([]) == "[]"


# ── writes via get_connection + executemany ──────────────────────────────────────

def test_insert_price_snapshots_empty_short_circuits(monkeypatch):
    conn = _patch_conn(monkeypatch)
    assert repo.insert_price_snapshots([]) == 0
    assert conn.calls == []  # no connection opened for an empty batch


def test_insert_price_snapshots_marshals_rows(monkeypatch):
    conn = _patch_conn(monkeypatch)
    rows = [
        PriceSnapshot(league="L", item_type="currency", name="Divine Orb",
                      chaos_value=200.0, divine_value=1.0, listing_count=5),
        PriceSnapshot(league="L", item_type="essence", name="Greater Essence"),
    ]
    assert repo.insert_price_snapshots(rows) == 2
    kind, query, seq = conn.calls[0]
    assert kind == "executemany"
    assert "INSERT INTO price_snapshot" in query
    assert seq[0] == ("L", "currency", "Divine Orb", 200.0, 1.0, 5)
    assert seq[1] == ("L", "essence", "Greater Essence", None, None, None)
    assert conn.commits == 1


def test_insert_farm_strategies_json_encodes_sources(monkeypatch):
    conn = _patch_conn(monkeypatch)
    rows = [FarmStrategy(league="L", name="Abyss", est_profit_per_hour=10.0,
                         risk="med", summary="s", sources=[{"url": "u"}])]
    assert repo.insert_farm_strategies(rows) == 1
    _, _, seq = conn.calls[0]
    league, name, pph, inv, risk, summary, sources = seq[0]
    assert (league, name, pph, risk, summary) == ("L", "Abyss", 10.0, "med", "s")
    assert json.loads(sources) == [{"url": "u"}]


def test_insert_farm_strategies_empty(monkeypatch):
    conn = _patch_conn(monkeypatch)
    assert repo.insert_farm_strategies([]) == 0
    assert conn.calls == []


def test_replace_meta_builds_deletes_then_inserts(monkeypatch):
    conn = _patch_conn(monkeypatch)
    builds = [MetaBuild(league="L", char_class="Monk", sample_size=3,
                        gems=[{"name": "Ice Strike", "usage_pct": 80}], sources=[{"url": "u"}])]
    assert repo.replace_meta_builds("L", builds) == 1
    assert conn.calls[0][0] == "execute"
    assert "DELETE FROM meta_build" in conn.calls[0][1]
    assert conn.calls[0][2] == ("L",)
    assert conn.calls[1][0] == "executemany"
    _, _, seq = conn.calls[1]
    league, char_class, sample, gems, sources = seq[0]
    assert (league, char_class, sample) == ("L", "Monk", 3)
    assert json.loads(gems)[0]["name"] == "Ice Strike"
    assert json.loads(sources) == [{"url": "u"}]
    assert conn.commits == 1


def test_replace_meta_builds_empty_still_deletes(monkeypatch):
    conn = _patch_conn(monkeypatch)
    assert repo.replace_meta_builds("L", []) == 0
    # the DELETE always runs (clears stale rows) even with nothing to insert
    assert conn.calls[0][0] == "execute"
    assert "DELETE FROM meta_build" in conn.calls[0][1]


def test_replace_craft_methods_marshals_all_json_columns(monkeypatch):
    conn = _patch_conn(monkeypatch)
    m = CraftMethod(
        league="L", name="Wand", item_base="Siphoning Wand", archetype="caster",
        target_mods=["+3 spell"], steps=["alt", "regal"], mechanics=["essence"],
        inputs={"Greater Essence of Haste": 2.0}, success_prob=0.25,
        output="+3 wand", output_value_div=5.0, sources=[{"url": "u"}], notes="n",
    )
    assert repo.replace_craft_methods("L", [m]) == 1
    assert "DELETE FROM craft_method" in conn.calls[0][1]
    _, _, seq = conn.calls[1]
    row = seq[0]
    assert row[0:4] == ("L", "Wand", "Siphoning Wand", "caster")
    assert json.loads(row[4]) == ["+3 spell"]
    assert json.loads(row[7]) == {"Greater Essence of Haste": 2.0}
    assert row[8] == 0.25 and row[10] == 5.0


def test_replace_farm_guides_uses_dict_get_defaults(monkeypatch):
    conn = _patch_conn(monkeypatch)
    # a sparse dict — missing keys must default, JSON columns to []
    assert repo.replace_farm_guides("L", [{"name": "Abyss"}]) == 1
    assert "DELETE FROM farm_guide" in conn.calls[0][1]
    _, _, seq = conn.calls[1]
    row = seq[0]
    assert row[0:2] == ("L", "Abyss")
    assert json.loads(row[6]) == []  # steps default
    assert json.loads(row[9]) == []  # faq default


def test_replace_craft_guides_marshals(monkeypatch):
    conn = _patch_conn(monkeypatch)
    g = {"name": "Caster wand", "item_base": "Wand", "archetype": "caster",
         "budget": "low", "mechanics": ["essence"], "expected_cost_div": 1.0,
         "roi_pct": 50.0, "overview": "o", "steps": ["s"], "items": [], "faq": [],
         "sources": [{"url": "u"}]}
    assert repo.replace_craft_guides("L", [g]) == 1
    assert "DELETE FROM craft_guide" in conn.calls[0][1]
    _, _, seq = conn.calls[1]
    row = seq[0]
    assert row[0:4] == ("L", "Caster wand", "Wand", "caster")
    assert json.loads(row[5]) == ["essence"]
    assert json.loads(row[12]) == [{"url": "u"}]


# ── writes via execute() ─────────────────────────────────────────────────────────

def test_insert_my_snapshot_json_encodes(monkeypatch):
    calls = _patch_execute(monkeypatch)
    snap = MySnapshot(character_name="Exile", char_class="Monk", level=92,
                      total_currency_chaos=100.0, gear={"weapon": "x"},
                      gems=[{"name": "Ice Strike"}], passive_tree={"hashes": [1, 2]})
    repo.insert_my_snapshot(snap)
    query, params = calls[0]
    assert "INSERT INTO my_snapshot" in query
    assert params[0:4] == ("Exile", "Monk", 92, 100.0)
    assert json.loads(params[4]) == {"weapon": "x"}
    assert json.loads(params[5]) == [{"name": "Ice Strike"}]
    assert json.loads(params[6]) == {"hashes": [1, 2]}


def test_upsert_knowledge_chunk_with_embedding(monkeypatch):
    calls = _patch_execute(monkeypatch)
    chunk = KnowledgeChunk(source_url="u", title="t", content="c",
                           embedding=[0.1, 0.2], topic="craft", discovery_query="ritual farm")
    repo.upsert_knowledge_chunk(chunk)
    query, params = calls[0]
    assert "ON CONFLICT (source_url) DO UPDATE" in query
    # discovery_query preserved on conflict (COALESCE keeps the first attribution)
    assert "COALESCE(knowledge_chunk.discovery_query" in query
    assert params == ("u", "t", "c", "[0.1,0.2]", "craft", "ritual farm")


def test_upsert_knowledge_chunk_without_embedding(monkeypatch):
    calls = _patch_execute(monkeypatch)
    chunk = KnowledgeChunk(source_url="u", content="c")
    repo.upsert_knowledge_chunk(chunk)
    _, params = calls[0]
    assert params[3] is None  # no vector literal when embedding is None
    assert params[5] is None  # discovery_query defaults to None for non-query sources


def test_knowledge_query_attribution_filters_null_and_scopes_to_recent_window(monkeypatch):
    calls = _patch_fetch(monkeypatch, [{"source_url": "u", "discovery_query": "q"}])
    out = repo.knowledge_query_attribution(limit=60)
    assert out == [{"source_url": "u", "discovery_query": "q"}]
    query, params = calls[0]
    assert "discovery_query IS NOT NULL" in query
    # only the most-recent N chunks could ever be fed to a generator -> only they can be cited
    assert "ORDER BY captured_at DESC" in query
    assert "LIMIT" in query
    assert params == (60,)


# ── reads ────────────────────────────────────────────────────────────────────────

def test_latest_prices_passes_league_and_limit(monkeypatch):
    calls = _patch_fetch(monkeypatch, [{"name": "Divine Orb"}])
    out = repo.latest_prices("L", limit=50)
    assert out == [{"name": "Divine Orb"}]
    query, params = calls[0]
    assert "FROM price_snapshot" in query
    assert params == ("L", 50)


def test_latest_farm_strategies_binds_league_twice(monkeypatch):
    calls = _patch_fetch(monkeypatch, [])
    repo.latest_farm_strategies("L", limit=7)
    _, params = calls[0]
    assert params == ("L", "L", 7)  # subquery + outer both bind league


def test_latest_my_snapshot_returns_first_row(monkeypatch):
    _patch_fetch(monkeypatch, [{"character_name": "Exile"}, {"character_name": "Other"}])
    assert repo.latest_my_snapshot() == {"character_name": "Exile"}


def test_latest_my_snapshot_none_when_empty(monkeypatch):
    _patch_fetch(monkeypatch, [])
    assert repo.latest_my_snapshot() is None


def test_latest_meta_build_returns_first(monkeypatch):
    calls = _patch_fetch(monkeypatch, [{"char_class": "Monk"}])
    assert repo.latest_meta_build("L", "Monk") == {"char_class": "Monk"}
    assert calls[0][1] == ("L", "Monk")


def test_latest_meta_build_none(monkeypatch):
    _patch_fetch(monkeypatch, [])
    assert repo.latest_meta_build("L", "Monk") is None


def test_latest_craft_methods_query(monkeypatch):
    calls = _patch_fetch(monkeypatch, [{"name": "Wand"}])
    assert repo.latest_craft_methods("L") == [{"name": "Wand"}]
    assert "FROM craft_method" in calls[0][0]
    assert calls[0][1] == ("L",)


def test_latest_knowledge_chunks_default_limit(monkeypatch):
    calls = _patch_fetch(monkeypatch, [])
    repo.latest_knowledge_chunks()
    assert calls[0][1] == (80,)


def test_latest_craft_knowledge_limit(monkeypatch):
    calls = _patch_fetch(monkeypatch, [])
    repo.latest_craft_knowledge(limit=12)
    assert "topic = 'craft'" in calls[0][0]
    assert calls[0][1] == (12,)


def test_latest_craft_guides_query(monkeypatch):
    calls = _patch_fetch(monkeypatch, [{"name": "g"}])
    assert repo.latest_craft_guides("L") == [{"name": "g"}]
    assert "ORDER BY roi_pct DESC NULLS LAST" in calls[0][0]
    assert calls[0][1] == ("L",)


def test_latest_farm_guides_query(monkeypatch):
    calls = _patch_fetch(monkeypatch, [])
    repo.latest_farm_guides("L")
    assert "FROM farm_guide" in calls[0][0]
    assert calls[0][1] == ("L",)


def test_farm_strategies_since_binds_days(monkeypatch):
    calls = _patch_fetch(monkeypatch, [])
    repo.farm_strategies_since("L", days=5)
    assert calls[0][1] == ("L", 5)


def test_price_snapshots_since_default_days(monkeypatch):
    calls = _patch_fetch(monkeypatch, [])
    repo.price_snapshots_since("L")
    assert calls[0][1] == ("L", 3)


def test_price_history_since_filters_currency(monkeypatch):
    calls = _patch_fetch(monkeypatch, [])
    repo.price_history_since("L", days=14)
    assert "item_type = 'currency'" in calls[0][0]
    assert calls[0][1] == ("L", 14)


def test_knowledge_chunks_since_default(monkeypatch):
    calls = _patch_fetch(monkeypatch, [])
    repo.knowledge_chunks_since()
    assert calls[0][1] == (2,)


# ── search_knowledge: with and without topic ─────────────────────────────────────

def test_search_knowledge_without_topic(monkeypatch):
    calls = _patch_fetch(monkeypatch, [{"source_url": "u"}])
    out = repo.search_knowledge([0.1, 0.2], limit=4)
    assert out == [{"source_url": "u"}]
    query, params = calls[0]
    assert "AND topic = %s" not in query  # no topic clause
    # params: vector (ORDER BY), vector (SELECT similarity), limit
    assert params == ("[0.1,0.2]", "[0.1,0.2]", 4)


def test_search_knowledge_with_topic(monkeypatch):
    calls = _patch_fetch(monkeypatch, [])
    repo.search_knowledge([0.5], limit=3, topic="craft")
    query, params = calls[0]
    assert "AND topic = %s" in query
    # params: vector, topic, vector, limit
    assert params == ("[0.5]", "craft", "[0.5]", 3)
