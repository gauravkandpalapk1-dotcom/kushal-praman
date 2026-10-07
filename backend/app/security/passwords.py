"""bcrypt password hashing. bcrypt only uses the first 72 bytes, so longer passwords are rejected
at the schema layer instead of being silently truncated."""
from __future__ import annotations

import bcrypt

MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False
