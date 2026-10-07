"""Evidence mapping schemas (tier-gated interpretive fields)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend.app.schemas.common import UTCDateTime


class SegmentRef(BaseModel):
    id: int
    start_s: float
    end_s: float


class NOSRef(BaseModel):
    id: int
    code: str
    title: str


class PCRef(BaseModel):
    id: int
    code: str
    text: str
    nos: NOSRef


class QualificationRef(BaseModel):
    id: int
    title: str
    nqr_code: str


class MappingOut(BaseModel):
    id: int
    evidence_id: int
    segment: SegmentRef
    pc: PCRef
    qualification: QualificationRef
    statement: str
    status: Literal["pending", "confirmed", "edited", "rejected"]
    mode: Literal["real", "demo"]
    decided_by: str | None
    decided_at: UTCDateTime | None
    locked: bool
    lock_reason: str | None
    confidence: float | None
    rationale: str | None
    tags: list[str] | None
    signal: Literal["supports", "partial", "not_found"] | None = None


class RejectIn(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class EditIn(BaseModel):
    pc_id: int | None = None
    start_s: float | None = Field(default=None, ge=0)
    end_s: float | None = Field(default=None, ge=0)
    reason: str | None = Field(default=None, max_length=2000)
