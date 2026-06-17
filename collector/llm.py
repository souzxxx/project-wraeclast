"""Shared GLM (z.ai) chat helper.

Always streams: non-streaming completions on the coding endpoint drop the connection on
longer generations (observed ~180s idle -> APIConnectionError). Streaming keeps the socket
busy and also suits the glm-5.x reasoning models, which spend tokens thinking before the
answer (hence the generous max_tokens default).
"""

from __future__ import annotations

from openai import OpenAI

from collector.config import get_settings


def _client() -> OpenAI:
    s = get_settings()
    if not s.glm_api_key:
        raise RuntimeError("GLM_API_KEY is not set.")
    return OpenAI(api_key=s.glm_api_key, base_url=s.glm_base_url, timeout=s.glm_timeout_seconds)


def glm_chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int | None = None,
) -> str:
    """Run a streamed chat completion and return the full assembled text."""
    s = get_settings()
    client = _client()
    stream = client.chat.completions.create(
        model=model or s.glm_chat_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens or s.glm_max_tokens,
        stream=True,
    )
    parts: list[str] = []
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta and delta.content:
            parts.append(delta.content)
    return "".join(parts)
