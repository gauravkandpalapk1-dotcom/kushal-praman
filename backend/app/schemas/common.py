"""Shared schema types."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, PlainSerializer

from backend.app.timeutil import iso

UTCDateTime = Annotated[datetime, PlainSerializer(lambda d: iso(d), return_type=str, when_used="json")]

Role = Literal["candidate", "assessor", "admin"]
Mode = Literal["real", "demo", "unavailable"]


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorOut(BaseModel):
    detail: str
    code: str


class OkOut(BaseModel):
    ok: bool = True
