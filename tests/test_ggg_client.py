"""Offline tests for the GGG OAuth 2.1 + PKCE client (Phase 2, dormant — skill §2).

Pure PKCE/URL builders are exercised directly; the token exchange/refresh httpx surface
is mocked with respx. No live network, no DB — these never touch pathofexile.com. The
module is not in the daily path yet, but hardening it now de-risks enabling Phase 2.
"""

import base64
import hashlib
import json
from urllib.parse import parse_qs, urlparse

import httpx
import respx

import collector.ggg_client as ggg
from collector.config import Settings
from collector.ggg_client import (
    AUTH_URL,
    SCOPES,
    TOKEN_URL,
    TokenSet,
    build_authorize_url,
    exchange_code,
    generate_pkce_pair,
    refresh_token,
)


def _settings(**overrides) -> Settings:
    base = {
        "ggg_client_id": "wraeclast-app",
        "ggg_client_secret": "",
        "ggg_redirect_uri": "https://wraeclast.vercel.app/oauth/callback",
        "ggg_user_agent": "Project-Wraeclast/0.1 (contact: souzxxx)",
    }
    base.update(overrides)
    return Settings(**base)


# --- generate_pkce_pair (pure) ------------------------------------------------


def test_pkce_challenge_is_s256_of_verifier():
    verifier, challenge = generate_pkce_pair()
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    assert challenge == expected


def test_pkce_tokens_are_url_safe_and_unpadded():
    for token in generate_pkce_pair():
        assert token  # non-empty
        assert "=" not in token  # padding stripped (PKCE forbids it)
        assert "+" not in token and "/" not in token  # url-safe alphabet only


def test_pkce_verifier_is_random_per_call():
    assert generate_pkce_pair()[0] != generate_pkce_pair()[0]


# --- build_authorize_url (pure) -----------------------------------------------


def test_build_authorize_url_includes_all_oauth_params():
    url = build_authorize_url("state123", "challenge456", _settings())
    assert url.startswith(AUTH_URL + "?")
    q = parse_qs(urlparse(url).query)
    assert q["client_id"] == ["wraeclast-app"]
    assert q["response_type"] == ["code"]
    assert q["scope"] == [SCOPES]
    assert q["state"] == ["state123"]
    assert q["redirect_uri"] == ["https://wraeclast.vercel.app/oauth/callback"]
    assert q["code_challenge"] == ["challenge456"]
    assert q["code_challenge_method"] == ["S256"]


def test_build_authorize_url_falls_back_to_get_settings(monkeypatch):
    monkeypatch.setattr(ggg, "get_settings", lambda: _settings(ggg_client_id="from-env"))
    q = parse_qs(urlparse(build_authorize_url("s", "c")).query)
    assert q["client_id"] == ["from-env"]


# --- exchange_code (httpx, mocked) --------------------------------------------


@respx.mock
async def test_exchange_code_returns_token_set_and_posts_pkce_body():
    route = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "AT", "refresh_token": "RT", "expires_in": 2419200},
        )
    )
    tokens = await exchange_code("authcode", "verifier123", _settings())
    assert route.called
    assert tokens == TokenSet(access_token="AT", refresh_token="RT", expires_in=2419200)
    body = json.loads(route.calls.last.request.content)
    assert body["grant_type"] == "authorization_code"
    assert body["code"] == "authcode"
    assert body["code_verifier"] == "verifier123"
    assert body["client_id"] == "wraeclast-app"
    assert body["redirect_uri"].endswith("/oauth/callback")
    # empty secret (public/PKCE client) is sent as null, not an empty string
    assert body["client_secret"] is None


@respx.mock
async def test_exchange_code_defaults_missing_optional_fields():
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={"access_token": "AT"}))
    tokens = await exchange_code("c", "v", _settings())
    assert tokens.refresh_token is None
    assert tokens.expires_in == 0


@respx.mock
async def test_exchange_code_forwards_confidential_secret_when_configured():
    route = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "AT"})
    )
    await exchange_code("c", "v", _settings(ggg_client_secret="s3cr3t"))
    body = json.loads(route.calls.last.request.content)
    assert body["client_secret"] == "s3cr3t"


@respx.mock
async def test_exchange_code_falls_back_to_get_settings(monkeypatch):
    monkeypatch.setattr(ggg, "get_settings", lambda: _settings())
    route = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "AT"})
    )
    await exchange_code("c", "v")
    assert route.called


# --- refresh_token (httpx, mocked) --------------------------------------------


@respx.mock
async def test_refresh_token_returns_token_set_and_posts_refresh_grant():
    route = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "AT2", "refresh_token": "RT2", "expires_in": 100},
        )
    )
    tokens = await refresh_token("old-refresh", _settings())
    assert tokens == TokenSet(access_token="AT2", refresh_token="RT2", expires_in=100)
    body = json.loads(route.calls.last.request.content)
    assert body["grant_type"] == "refresh_token"
    assert body["refresh_token"] == "old-refresh"
    assert body["client_id"] == "wraeclast-app"


@respx.mock
async def test_refresh_token_keeps_old_refresh_when_response_omits_it():
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "AT2", "expires_in": 50})
    )
    tokens = await refresh_token("old-refresh", _settings())
    # GGG does not always rotate the refresh token; keep the one we already hold.
    assert tokens.refresh_token == "old-refresh"
    assert tokens.expires_in == 50


@respx.mock
async def test_refresh_token_falls_back_to_get_settings(monkeypatch):
    monkeypatch.setattr(ggg, "get_settings", lambda: _settings())
    route = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "AT"})
    )
    await refresh_token("r")
    assert route.called
