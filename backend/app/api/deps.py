"""Request dependencies: DB session, current user, role guards."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.app.db import SessionLocal
from backend.app.errors import Forbidden, Unauthorized
from backend.app.models import User
from backend.app.security.jwt import decode_access_token

_bearer = HTTPBearer(auto_error=False, description="JWT from /api/v1/auth/login")


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DB = Annotated[Session, Depends(get_db)]


def get_current_user(db: DB, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise Unauthorized("Authentication required.", "not_authenticated")
    payload = decode_access_token(creds.credentials)
    try:
        user = db.get(User, int(payload["sub"]))
    except (TypeError, ValueError):
        user = None
    if user is None:
        raise Unauthorized("Account no longer exists; sign in again.", "invalid_token")
    if not user.is_active:
        raise Forbidden("This account is disabled.", "account_disabled")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str) -> Callable[..., User]:
    def _dep(user: CurrentUser) -> User:
        if user.role not in roles:
            raise Forbidden(f"This action requires role: {' or '.join(roles)}.", "forbidden_role")
        return user

    return _dep


AdminUser = Annotated[User, Depends(require_roles("admin"))]
AssessorUser = Annotated[User, Depends(require_roles("assessor"))]
CandidateUser = Annotated[User, Depends(require_roles("candidate"))]
StaffUser = Annotated[User, Depends(require_roles("assessor", "admin"))]
