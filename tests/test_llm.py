"""Offline tests for the shared GLM (z.ai) chat helper.

No network: the OpenAI client is monkeypatched out and the streamed response is faked, so we
exercise `_client` construction/guarding and `glm_chat`'s stream assembly + per-call options
without any live key or socket.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import collector.llm as llm
from collector.config import Settings


def _chunk(content: str | None, *, choices: bool = True) -> SimpleNamespace:
    """Mimic an OpenAI streaming chunk: chunk.choices[0].delta.content."""
    if not choices:
        return SimpleNamespace(choices=[])
    delta = None if content is None else SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


class _FakeCompletions:
    def __init__(self, stream: list, recorder: list[dict]) -> None:
        self._stream = stream
        self._recorder = recorder

    def create(self, **kwargs):
        self._recorder.append(kwargs)
        return self._stream


class _FakeClient:
    """Stands in for the OpenAI client. Records `create` kwargs and `with_options` calls."""

    def __init__(self, stream: list, recorder: list[dict], with_options: list[dict]) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions(stream, recorder))
        self._with_options = with_options

    def with_options(self, **kwargs):
        self._with_options.append(kwargs)
        return self


# ── _client ──────────────────────────────────────────────────────────────────


def test_client_raises_without_key(monkeypatch):
    monkeypatch.setattr(llm, "get_settings", lambda: Settings(glm_api_key=""))
    with pytest.raises(RuntimeError, match="GLM_API_KEY"):
        llm._client()


def test_client_passes_key_base_url_and_timeout(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: Settings(
            glm_api_key="secret-key",
            glm_base_url="https://example.test/v1",
            glm_timeout_seconds=12.5,
        ),
    )
    monkeypatch.setattr(llm, "OpenAI", lambda **kwargs: captured.update(kwargs) or object())

    llm._client()

    assert captured == {
        "api_key": "secret-key",
        "base_url": "https://example.test/v1",
        "timeout": 12.5,
    }


# ── glm_chat ─────────────────────────────────────────────────────────────────


def _install_fake(monkeypatch, stream, *, settings: Settings | None = None):
    """Wire `_client` to a fake and pin settings; return (create_calls, with_options_calls)."""
    recorder: list[dict] = []
    with_options: list[dict] = []
    client = _FakeClient(stream, recorder, with_options)
    monkeypatch.setattr(llm, "_client", lambda: client)
    monkeypatch.setattr(llm, "get_settings", lambda: settings or Settings())
    return recorder, with_options


def test_glm_chat_assembles_streamed_content(monkeypatch):
    stream = [_chunk("Hello"), _chunk(", "), _chunk("world")]
    _install_fake(monkeypatch, stream)

    out = llm.glm_chat([{"role": "user", "content": "hi"}])

    assert out == "Hello, world"


def test_glm_chat_skips_empty_and_none_deltas(monkeypatch):
    stream = [
        _chunk("a"),
        _chunk(None, choices=False),  # no choices -> skipped
        _chunk(None),  # delta is None -> skipped
        _chunk(""),  # empty content -> skipped
        _chunk("b"),
    ]
    _install_fake(monkeypatch, stream)

    assert llm.glm_chat([{"role": "user", "content": "x"}]) == "ab"


def test_glm_chat_uses_settings_defaults_and_streams(monkeypatch):
    settings = Settings(glm_chat_model="glm-default", glm_max_tokens=4321)
    recorder, with_options = _install_fake(monkeypatch, [_chunk("ok")], settings=settings)

    llm.glm_chat([{"role": "user", "content": "x"}])

    [call] = recorder
    assert call["model"] == "glm-default"
    assert call["max_tokens"] == 4321
    assert call["temperature"] == 0.3
    assert call["stream"] is True
    assert with_options == []  # no per-call timeout -> default client used


def test_glm_chat_honors_model_temperature_and_max_tokens_overrides(monkeypatch):
    recorder, _ = _install_fake(monkeypatch, [_chunk("ok")])

    llm.glm_chat(
        [{"role": "user", "content": "x"}],
        model="glm-override",
        temperature=0.9,
        max_tokens=99,
    )

    [call] = recorder
    assert call["model"] == "glm-override"
    assert call["temperature"] == 0.9
    assert call["max_tokens"] == 99


def test_glm_chat_applies_per_call_timeout_via_with_options(monkeypatch):
    recorder, with_options = _install_fake(monkeypatch, [_chunk("ok")])

    llm.glm_chat([{"role": "user", "content": "x"}], timeout=7.0)

    assert with_options == [{"timeout": 7.0}]
    assert len(recorder) == 1  # still issued exactly one create call
