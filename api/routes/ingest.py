"""POST /ingest — manually add a URL or text to the knowledge corpus (owner-only).

Gated by the same access token as /chat (it spends embedding quota and writes to the DB).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field, model_validator

from api.routes.chat import _check_access

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestRequest(BaseModel):
    value: str = Field(min_length=1, max_length=20000, description="A URL or raw text")
    title: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _strip(self) -> IngestRequest:
        self.value = self.value.strip()
        return self


@router.post("")
def post_ingest(req: IngestRequest, x_access_token: str = Header(default="")) -> dict[str, Any]:
    _check_access(x_access_token)
    from collector.add_knowledge import ingest_input

    doc = ingest_input(req.value, req.title)
    return {"ok": True, "title": doc.title, "source_url": doc.source_url}
