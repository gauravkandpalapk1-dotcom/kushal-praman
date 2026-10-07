"""JWT access tokens (HS256)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from backend.app.config import get_settings
from backend.app.errors import Unauthorized

ALGORITHM = "HS256"


def create_access_token(user_id: int, role: str) -> tuple[str, int]:
    s = get_settings()
    now = datetime.now(timezone.utc)
    expires_in = s.JWT_EXPIRE_MINUTES * 60
    payload = {"sub": str(user_id), "role": role, "iat": now, "exp": now + timedelta(seconds=expires_in), "typ": "access"}
    return jwt.encode(payload, s.JWT_SECRET, algorithm=ALGORITHM), expires_in


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, get_settings().JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise Unauthorized("Session expired; sign in again.", "token_expired") from exc
    except jwt.PyJWTError as exc:
        raise Unauthorized("Invalid authentication token.", "invalid_token") from exc
    if payload.get("typ") != "access" or "sub" not in payload:
        raise Unauthorized("Invalid authentication token.", "invalid_token")
    return payload
