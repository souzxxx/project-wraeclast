"""GGG official API — OAuth 2.1 + PKCE (Phase 2, OPTIONAL; skill §2, CLAUDE.md §Fases).

NOT a blocker for anything. Phase 0/1 (ninja + PoB) cover build/gear/passives/skills.
The ONLY thing OAuth adds is real-time stash currency (net worth) and characters off the
ladder. This module is designed to plug in without reworking the rest.

PKCE generation is pure and unit-testable. Token exchange/refresh use httpx. A descriptive
User-Agent is mandatory or GGG blocks you; rate-limit headers must be honored (HttpClient does).
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

from collector.config import Settings, get_settings
from collector.http import HttpClient

AUTH_URL = "https://www.pathofexile.com/oauth/authorize"
TOKEN_URL = "https://www.pathofexile.com/oauth/token"
SCOPES = "account:characters account:stashes"


def generate_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for the S256 PKCE flow."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def build_authorize_url(state: str, code_challenge: str, settings: Settings | None = None) -> str:
    s = settings or get_settings()
    params = {
        "client_id": s.ggg_client_id,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "redirect_uri": s.ggg_redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_in: int
    token_type: str = "bearer"


async def exchange_code(
    code: str, code_verifier: str, settings: Settings | None = None
) -> TokenSet:
    s = settings or get_settings()
    async with HttpClient(s.ggg_user_agent) as http:
        data = await http.post_json(
            TOKEN_URL,
            json_body={
                "client_id": s.ggg_client_id,
                "client_secret": s.ggg_client_secret or None,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": s.ggg_redirect_uri,
                "code_verifier": code_verifier,
            },
        )
    return TokenSet(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        expires_in=int(data.get("expires_in", 0)),
    )


async def refresh_token(refresh: str, settings: Settings | None = None) -> TokenSet:
    s = settings or get_settings()
    async with HttpClient(s.ggg_user_agent) as http:
        data = await http.post_json(
            TOKEN_URL,
            json_body={
                "client_id": s.ggg_client_id,
                "client_secret": s.ggg_client_secret or None,
                "grant_type": "refresh_token",
                "refresh_token": refresh,
            },
        )
    return TokenSet(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", refresh),
        expires_in=int(data.get("expires_in", 0)),
    )
