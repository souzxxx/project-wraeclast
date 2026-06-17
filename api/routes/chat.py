"""POST /chat — RAG answer grounded in the curated corpus + owner profile.

Gated by a shared password (X-Access-Token) because this is the only endpoint that spends
GLM/embeddings quota. Fail-closed: if CHAT_ACCESS_TOKEN is unset, /chat is disabled so a
discovered-but-unconfigured deploy can't burn the owner's tokens.
"""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from collector.config import get_settings

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


def _check_access(provided: str | None) -> None:
    configured = get_settings().chat_access_token
    if not configured:
        raise HTTPException(status_code=503, detail="chat is not configured (no access token set)")
    # constant-time compare to avoid leaking the token via timing
    if not provided or not hmac.compare_digest(provided, configured):
        raise HTTPException(status_code=401, detail="invalid or missing access token")


@router.post("")
def post_chat(req: ChatRequest, x_access_token: str = Header(default="")) -> dict[str, Any]:
    _check_access(x_access_token)
    from api.rag import answer

    return answer(req.question)
