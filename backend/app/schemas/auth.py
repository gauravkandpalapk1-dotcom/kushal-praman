"""Auth and user schemas."""
from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, field_validator

from backend.app.schemas.common import Out, Role
from backend.app.security.passwords import MAX_PASSWORD_BYTES

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _check_email(v: str) -> str:
    v = v.strip().lower()
    if len(v) > 254 or not _EMAIL.match(v):
        raise ValueError("not a valid email address")
    return v


Email = Annotated[str, AfterValidator(_check_email)]


def _check_password(v: str) -> str:
    if len(v.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"password must be at most {MAX_PASSWORD_BYTES} bytes")
    return v


class RegisterIn(BaseModel):
    email: Email
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=200)
    role: Role
    preferred_language: str | None = Field(default=None, max_length=10)
    qualification_id: int | None = None
    district: str | None = Field(default=None, max_length=100)

    _pw = field_validator("password")(_check_password)


class LoginIn(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=200)


class AgencyOut(Out):
    id: int
    name: str
    code: str


class CandidateProfileOut(Out):
    id: int
    candidate_code: str
    qualification_id: int | None
    preferred_language: str | None
    district: str | None


class AssessorProfileOut(Out):
    id: int
    assessor_code: str
    agency: AgencyOut | None


class UserOut(Out):
    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    candidate: CandidateProfileOut | None = None
    assessor: AssessorProfileOut | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserOut


class AdminUserIn(BaseModel):
    email: Email
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=200)
    role: Role
    assessor_code: str | None = Field(default=None, max_length=20)
    qualification_id: int | None = None
    preferred_language: str | None = None
    district: str | None = None

    _pw = field_validator("password")(_check_password)


class AdminUserPatch(BaseModel):
    is_active: bool


class AgencyListOut(AgencyOut):
    assessor_count: int
