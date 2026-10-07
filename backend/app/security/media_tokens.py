"""Short-lived HMAC media tokens so <video src> can stream without an Authorization header.

token = "<exp>.<hex hmac_sha256(key, 'media:<evidence_id>:<exp>')>"; bound to one evidence id.
"""
from __future__ import annotations

import hashlib
import hmac
import time

from backend.app.config import get_settings
from backend.app.errors import Forbidden


def _key() -> bytes:
    return hashlib.sha256(("media-token:" + get_settings().JWT_SECRET).encode()).digest()


def _sig(evidence_id: int, exp: int) -> str:
    return hmac.new(_key(), f"media:{evidence_id}:{exp}".encode(), hashlib.sha256).hexdigest()


def issue(evidence_id: int, ttl_s: int | None = None) -> str:
    exp = int(time.time()) + (ttl_s if ttl_s is not None else get_settings().MEDIA_TOKEN_TTL_S)
    return f"{exp}.{_sig(evidence_id, exp)}"


def verify(evidence_id: int, token: str | None) -> None:
    if not token or "." not in token:
        raise Forbidden("Missing or malformed media token.", "invalid_media_token")
    exp_s, sig = token.split(".", 1)
    if not exp_s.isdigit():
        raise Forbidden("Malformed media token.", "invalid_media_token")
    exp = int(exp_s)
    if not hmac.compare_digest(sig, _sig(evidence_id, exp)):
        raise Forbidden("Media token is not valid for this evidence.", "invalid_media_token")
    if exp < time.time():
        raise Forbidden("Media token expired; reload the evidence to get a fresh link.", "media_token_expired")


def media_url(evidence_id: int) -> str:
    return f"/api/v1/evidence/{evidence_id}/media?t={issue(evidence_id)}"
