"""Tests for the /chat access gate — security-critical, so pin its behaviour."""

import pytest
from fastapi import HTTPException

import api.routes.chat as chat_mod


class _Settings:
    def __init__(self, token: str):
        self.chat_access_token = token


def _patch_token(monkeypatch, token: str):
    monkeypatch.setattr(chat_mod, "get_settings", lambda: _Settings(token))


def test_unconfigured_token_is_503(monkeypatch):
    # fail-closed: with no token configured, /chat is disabled
    _patch_token(monkeypatch, "")
    with pytest.raises(HTTPException) as exc:
        chat_mod._check_access("anything")
    assert exc.value.status_code == 503


def test_missing_or_wrong_token_is_401(monkeypatch):
    _patch_token(monkeypatch, "s3cret")
    for bad in (None, "", "wrong"):
        with pytest.raises(HTTPException) as exc:
            chat_mod._check_access(bad)
        assert exc.value.status_code == 401


def test_correct_token_passes(monkeypatch):
    _patch_token(monkeypatch, "s3cret")
    chat_mod._check_access("s3cret")  # must not raise
