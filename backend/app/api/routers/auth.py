from __future__ import annotations

from fastapi import APIRouter, Request

from backend.app.api.deps import DB, CurrentUser
from backend.app.errors import AppError, TooManyRequests
from backend.app.security import login_throttle
from backend.app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut
from backend.app.security.jwt import create_access_token
from backend.app.services import presenters as P
from backend.app.services import users as user_svc

router = APIRouter(prefix="/auth", tags=["auth"])


def _token(u) -> dict:
    token, expires_in = create_access_token(u.id, u.role)
    return {"access_token": token, "token_type": "bearer", "expires_in": expires_in, "user": P.user_out(u)}


@router.post("/register", response_model=TokenOut, status_code=201,
             summary="Self-register as candidate or assessor (admin -> 403)")
def register(body: RegisterIn, db: DB):
    return _token(user_svc.register(db, body))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: DB, request: Request):
    ip = request.client.host if request.client else ""
    wait = login_throttle.retry_after(body.email, ip)
    if wait:
        raise TooManyRequests(f"Too many failed sign-in attempts. Try again in {wait} s.")
    try:
        user = user_svc.login(db, body.email, body.password)
    except AppError as exc:
        if exc.status_code == 401:
            login_throttle.record_failure(body.email, ip)
        raise
    login_throttle.record_success(body.email, ip)
    return _token(user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return P.user_out(user)
