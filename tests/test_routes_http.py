"""Offline HTTP-layer tests for the FastAPI route surface.

The `api/routes/*` modules and `api/main.py`'s read endpoints are the contract the Next.js site
depends on, yet they had zero coverage — a renamed field or a wrong status code would ship
silently. These tests drive the real ASGI stack via `TestClient` (no network, no DB): every route
defers its `db.repo` import to call time, so we monkeypatch `db.repo.*` and the pure projection
helpers run for real. The league is always read from `get_settings()`, never hardcoded.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

import api.main as main_mod
import api.routes.chat as chat_mod
from collector.config import get_settings


@pytest.fixture
def client() -> TestClient:
    # raise_server_exceptions=False so the app's own exception handler is exercised (not re-raised).
    return TestClient(main_mod.app, raise_server_exceptions=False)


@pytest.fixture
def league() -> str:
    return get_settings().poe2_league


# --------------------------------------------------------------------------- static endpoints


def test_health_ok_and_cached(client: TestClient, league: str) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "league": league}
    # the read-cache middleware tags successful GETs so browsers/CDN can hold them briefly
    assert resp.headers["Cache-Control"] == "public, max-age=300"


def test_root_lists_endpoints(client: TestClient, league: str) -> None:
    body = client.get("/").json()
    assert body["service"] == "Project Wraeclast API"
    assert body["league"] == league
    assert "/farm" in body["endpoints"] and "/chat (POST)" in body["endpoints"]


# --------------------------------------------------------------------------- /farm


def test_farm_ranking_shape_and_limit_clamp(client, monkeypatch, league) -> None:
    seen: dict[str, int] = {}

    def fake(lg: str, limit: int) -> list[dict[str, Any]]:
        seen["league"], seen["limit"] = lg, limit
        return [{"name": "Abyss", "est_profit_per_hour": 3.0}]

    monkeypatch.setattr("db.repo.latest_farm_strategies", fake)
    body = client.get("/farm", params={"limit": 500}).json()
    assert body["league"] == league
    assert "estimate" in body["note"].lower()
    assert body["strategies"][0]["name"] == "Abyss"
    assert seen["league"] == league
    assert seen["limit"] == 100  # clamped to the max


def test_farm_limit_floor(client, monkeypatch) -> None:
    seen: dict[str, int] = {}
    monkeypatch.setattr(
        "db.repo.latest_farm_strategies",
        lambda lg, limit: seen.update(limit=limit) or [],
    )
    client.get("/farm", params={"limit": 0})
    assert seen["limit"] == 1  # clamped to the floor


def test_farm_guides(client, monkeypatch, league) -> None:
    monkeypatch.setattr("db.repo.latest_farm_guides", lambda lg: [{"name": "Guide"}])
    body = client.get("/farm/guides").json()
    assert body["league"] == league
    assert body["guides"] == [{"name": "Guide"}]


# --------------------------------------------------------------------------- /price-history


def test_price_history_clamps_and_projects(client, monkeypatch, league) -> None:
    seen: dict[str, int] = {}
    monkeypatch.setattr(
        "db.repo.price_history_since",
        lambda lg, days: seen.update(days=days) or [],
    )
    body = client.get("/price-history", params={"days": 999, "limit": 999}).json()
    assert body["league"] == league
    assert body["sparklines"] == []  # no rows → no series
    assert seen["days"] == 60  # days clamped to the ceiling before the query


def test_price_history_days_floor(client, monkeypatch) -> None:
    seen: dict[str, int] = {}
    monkeypatch.setattr(
        "db.repo.price_history_since",
        lambda lg, days: seen.update(days=days) or [],
    )
    client.get("/price-history", params={"days": 1})
    assert seen["days"] == 2  # make_interval guard floor


# --------------------------------------------------------------------------- /graph


def test_graph_snapshot(client, monkeypatch, league) -> None:
    monkeypatch.setattr("db.repo.latest_farm_guides", lambda *a, **k: [])
    monkeypatch.setattr("db.repo.latest_knowledge_chunks", lambda *a, **k: [])
    monkeypatch.setattr("db.repo.latest_my_snapshot", lambda *a, **k: None)
    monkeypatch.setattr("db.repo.latest_prices", lambda *a, **k: [])
    body = client.get("/graph").json()
    assert body["league"] == league
    assert "nodes" in body and "links" in body
    # the league itself is always a node even with an empty corpus
    assert any(n for n in body["nodes"])


# --------------------------------------------------------------------------- /build


def test_build_404_without_snapshot(client, monkeypatch) -> None:
    monkeypatch.setattr("db.repo.latest_my_snapshot", lambda: None)
    resp = client.get("/build")
    assert resp.status_code == 404
    assert "snapshot" in resp.json()["detail"].lower()


def test_build_degrades_without_meta(client, monkeypatch) -> None:
    monkeypatch.setattr(
        "db.repo.latest_my_snapshot",
        lambda: {"char_class": "Monk", "level": 90, "gems": [{"name": "Ice Strike"}]},
    )
    monkeypatch.setattr("db.repo.latest_meta_build", lambda lg, cls: None)
    body = client.get("/build").json()
    assert body["comparable"] is False
    assert body["my_class"] == "Monk"
    assert "Ice Strike" in body["my_gems"]


def test_build_comparable_with_meta(client, monkeypatch) -> None:
    monkeypatch.setattr(
        "db.repo.latest_my_snapshot",
        lambda: {"char_class": "Monk", "level": 90, "gems": [{"name": "Ice Strike"}]},
    )
    monkeypatch.setattr(
        "db.repo.latest_meta_build",
        lambda lg, cls: {"gems": [{"name": "Ice Strike"}, {"name": "Tempest Bell"}]},
    )
    body = client.get("/build").json()
    assert body["comparable"] is True
    assert body["my_class"] == "Monk"


def test_build_no_meta_query_when_class_missing(client, monkeypatch) -> None:
    # _load_meta_build must short-circuit (never hit the DB) when the snapshot has no class.
    monkeypatch.setattr("db.repo.latest_my_snapshot", lambda: {"level": 5, "gems": []})

    def _boom(*a: Any, **k: Any) -> None:  # pragma: no cover - must not run
        raise AssertionError("latest_meta_build should not be called without a class")

    monkeypatch.setattr("db.repo.latest_meta_build", _boom)
    body = client.get("/build").json()
    assert body["comparable"] is False


# --------------------------------------------------------------------------- /craft/*


def test_craft_knowledge_cards(client, monkeypatch) -> None:
    seen: dict[str, int] = {}

    def fake(limit: int) -> list[dict[str, Any]]:
        seen["limit"] = limit
        return [
            {"source_url": "http://x", "title": "Essence", "content": "abc"},
            {"source_url": None, "title": "dropped"},  # no url → filtered by craft_cards
        ]

    monkeypatch.setattr("db.repo.latest_craft_knowledge", fake)
    body = client.get("/craft/knowledge", params={"limit": 999}).json()
    assert seen["limit"] == 100  # clamped
    assert [c["title"] for c in body["cards"]] == ["Essence"]


def test_craft_guides(client, monkeypatch, league) -> None:
    monkeypatch.setattr("db.repo.latest_craft_guides", lambda lg: [{"title": "Craft"}])
    body = client.get("/craft/guides").json()
    assert body["league"] == league
    assert body["guides"] == [{"title": "Craft"}]


def test_craft_alerts_empty(client, monkeypatch, league) -> None:
    monkeypatch.setattr("db.repo.latest_craft_methods", lambda lg: [])
    monkeypatch.setattr("db.repo.price_snapshots_since", lambda lg, days: [])
    body = client.get("/craft/alerts").json()
    assert body["league"] == league
    assert body["alerts"] == []


def test_craft_ev_ranking(client, monkeypatch, league) -> None:
    monkeypatch.setattr("db.repo.latest_craft_methods", lambda lg: [])
    monkeypatch.setattr("db.repo.latest_prices", lambda lg, limit=1000: [])
    body = client.get("/craft/ev").json()
    assert body["league"] == league
    assert body["methods"] == []
    assert "ROI" in body["note"]


# --------------------------------------------------------------------------- /ingest (gated POST)


def _set_chat_token(monkeypatch, token: str) -> None:
    monkeypatch.setattr(chat_mod, "get_settings", lambda: SimpleNamespace(chat_access_token=token))


def test_ingest_requires_token(client, monkeypatch) -> None:
    _set_chat_token(monkeypatch, "s3cret")
    resp = client.post("/ingest", json={"value": "http://x"})  # no header
    assert resp.status_code == 401


def test_ingest_disabled_without_configured_token(client, monkeypatch) -> None:
    _set_chat_token(monkeypatch, "")  # fail-closed
    resp = client.post("/ingest", json={"value": "http://x"}, headers={"x-access-token": "any"})
    assert resp.status_code == 503


def test_ingest_happy_path(client, monkeypatch) -> None:
    _set_chat_token(monkeypatch, "s3cret")
    captured: dict[str, Any] = {}

    def fake_ingest(value: str, title: str | None) -> SimpleNamespace:
        captured["value"], captured["title"] = value, title
        return SimpleNamespace(title="My Title", source_url="http://x")

    monkeypatch.setattr("collector.add_knowledge.ingest_input", fake_ingest)
    resp = client.post(
        "/ingest",
        json={"value": "  http://x  ", "title": "T"},
        headers={"x-access-token": "s3cret"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "title": "My Title", "source_url": "http://x"}
    assert captured["value"] == "http://x"  # validator stripped whitespace before ingest


def test_ingest_rejects_empty_value(client, monkeypatch) -> None:
    _set_chat_token(monkeypatch, "s3cret")
    resp = client.post("/ingest", json={"value": ""}, headers={"x-access-token": "s3cret"})
    assert resp.status_code == 422  # min_length=1 rejects an empty payload before ingest runs


# --------------------------------------------------------------------------- main.py read endpoints


def test_state_aggregates(client, monkeypatch, league) -> None:
    monkeypatch.setattr("db.repo.latest_farm_strategies", lambda lg, limit: [{"name": "A"}])
    monkeypatch.setattr("db.repo.latest_my_snapshot", lambda: {"char_class": "Monk"})
    monkeypatch.setattr(
        "db.repo.latest_prices",
        lambda lg, limit=1000: [{"name": "Divine"}, {"name": "Chaos"}],
    )
    body = client.get("/state").json()
    assert body["league"] == league
    assert body["price_count"] == 2
    assert body["top_farms"] == [{"name": "A"}]
    assert body["my_snapshot"] == {"char_class": "Monk"}


def test_prices_projects_currency_only(client, monkeypatch, league) -> None:
    monkeypatch.setattr(
        "db.repo.latest_prices",
        lambda lg, limit=1000: [
            {"name": "Divine", "item_type": "currency", "chaos_value": 1, "divine_value": 1},
            {"name": "SomeRune", "item_type": "rune", "chaos_value": 5},  # non-currency → dropped
        ],
    )
    body = client.get("/prices").json()
    assert body["league"] == league
    assert [p["name"] for p in body["prices"]] == ["Divine"]


# --------------------------------------------------------------------------- error handling


def test_unhandled_error_is_json_500_with_cors(client, monkeypatch) -> None:
    origin = get_settings().cors_origin_list[0]

    def _boom(*a: Any, **k: Any) -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr("db.repo.latest_farm_strategies", _boom)
    resp = client.get("/farm", headers={"origin": origin})
    assert resp.status_code == 500
    assert resp.json() == {"detail": "internal server error"}
    # CORS echoed manually so the browser sees a real 500, not an opaque NetworkError
    assert resp.headers["Access-Control-Allow-Origin"] == origin
