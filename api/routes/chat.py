"""POST /chat — RAG answer grounded in the curated corpus + owner profile."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


@router.post("")
def post_chat(req: ChatRequest) -> dict[str, Any]:
    from api.rag import answer

    return answer(req.question)
