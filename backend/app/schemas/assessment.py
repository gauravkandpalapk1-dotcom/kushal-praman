"""Assessment (assessor-first) schemas."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend.app.schemas.common import Mode, UTCDateTime
from backend.app.schemas.evidence import CandidateRef, EvidenceOut
from backend.app.schemas.qualifications import PCOut

Status = Literal["opened", "initial_locked", "ai_revealed", "finalized"]


class OpenIn(BaseModel):
    evidence_id: int
    pc_id: int


class InitialIn(BaseModel):
    score: int
    note: str | None = Field(default=None, max_length=4000)


class FinalIn(BaseModel):
    score: int
    rationale: str | None = Field(default=None, max_length=4000)


class AssessorRef(BaseModel):
    id: int
    assessor_code: str
    full_name: str


class QualificationBrief(BaseModel):
    id: int
    title: str
    nqr_code: str
    nsqf_level: int


class NOSBrief(BaseModel):
    id: int
    code: str
    title: str


class MappingBrief(BaseModel):
    id: int
    status: str


class AssessmentOut(BaseModel):
    id: int
    status: Status
    max_score: int
    blind: bool
    is_second_assessor: bool
    is_demo: bool
    evidence: EvidenceOut
    candidate: CandidateRef
    qualification: QualificationBrief
    nos: NOSBrief
    pc: PCOut
    assessor: AssessorRef
    opened_at: UTCDateTime
    initial_score: int | None
    initial_note: str | None
    initial_locked_at: UTCDateTime | None
    ai_revealed_at: UTCDateTime | None
    final_score: int | None
    final_rationale: str | None
    finalized_at: UTCDateTime | None
    score_changed: bool | None
    mapping: MappingBrief | None


class TranscriptBrief(BaseModel):
    start_s: float
    end_s: float
    text: str
    translation_en: str | None = None


class FindingOut(BaseModel):
    mapping_id: int | None
    start_s: float | None
    end_s: float | None
    statement: str
    signal: Literal["supports", "partial", "not_found"]
    confidence: float | None
    rationale: str | None
    tags: list[str] | None
    mode: Literal["real", "demo"] | None = None
    status: str | None = None
    transcript: list[TranscriptBrief]


class ServiceUsed(BaseModel):
    service: str
    provider: str | None
    model: str | None
    mode: Mode | None
    status: str | None = None


class AISupportOut(BaseModel):
    assessment_id: int
    mode: Literal["real", "demo"]
    pc: dict
    nos: dict
    findings: list[FindingOut]
    summary: str | None
    services: list[ServiceUsed]
    confidence_note: str
    disclaimer: str
    ai_revealed_at: UTCDateTime | None
