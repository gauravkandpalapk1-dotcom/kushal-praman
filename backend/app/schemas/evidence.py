"""Evidence, processing and workspace schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.schemas.common import Mode, Out, UTCDateTime

Kind = Literal["video", "photo", "audio", "document"]


class EvidenceMetaIn(BaseModel):
    """The `meta` JSON string sent alongside the uploaded file."""

    local_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    kind: Kind
    qualification_id: int | None = None
    pc_hint_id: int | None = None
    client_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    captured_at: datetime | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0)
    device: str | None = Field(default=None, max_length=300)
    language: str | None = Field(default=None, max_length=10)
    reserved_number: int | None = Field(default=None, ge=1)
    encrypted_at_rest: bool = False
    offline_captured: bool = False
    queued_at: datetime | None = None
    sync_attempts: int = Field(default=1, ge=0, le=10000)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("client_sha256")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()


class CandidateRef(Out):
    id: int
    full_name: str
    candidate_code: str


class EvidenceMetadataOut(Out):
    latitude: float | None = None
    longitude: float | None = None
    accuracy_m: float | None = None
    device: str | None = None
    duration_s: float | None = None
    width: int | None = None
    height: int | None = None
    language: str | None = None
    sync_attempts: int | None = None
    queued_at: UTCDateTime | None = None


class EvidenceOut(Out):
    id: int
    display_number: int
    label: str
    kind: Kind
    original_filename: str | None
    mime_type: str
    size_bytes: int
    sha256: str
    client_sha256: str
    integrity_ok: bool
    status: Literal["received", "processing", "ready", "failed"]
    is_demo: bool
    offline_captured: bool
    encrypted_at_rest: bool
    captured_at: UTCDateTime | None
    synced_at: UTCDateTime | None
    qualification_id: int
    pc_hint_id: int | None = None
    candidate: CandidateRef
    metadata: EvidenceMetadataOut
    media_url: str


class StepOut(BaseModel):
    key: Literal["integrity", "probe", "segmentation", "speech", "vision", "ocr", "llm", "mapping"]
    label: str
    status: Literal["pending", "running", "done", "skipped", "failed"]
    mode: Mode | None
    provider: str | None = None
    model: str | None = None
    detail: str | None
    started_at: UTCDateTime | None
    finished_at: UTCDateTime | None


class ProcessingOut(BaseModel):
    evidence_id: int
    run: int
    status: Literal["not_started", "queued", "running", "done", "failed"]
    mode: Literal["real", "demo"] | None
    started_at: UTCDateTime | None
    finished_at: UTCDateTime | None
    steps: list[StepOut]


class SegmentOut(BaseModel):
    id: int
    start_s: float
    end_s: float
    label: str
    source: str


class TranscriptLineOut(BaseModel):
    start_s: float
    end_s: float
    text: str
    language: str | None = None
    translation_en: str | None = None
    mode: Mode


class SurfacedOut(BaseModel):
    mapping_id: int
    segment_id: int
    start_s: float
    end_s: float
    pc_id: int
    pc_code: str
    nos_code: str
    statement: str
    mode: Literal["real", "demo"]


class WorkspaceOut(BaseModel):
    evidence: EvidenceOut
    segments: list[SegmentOut]
    transcript: list[TranscriptLineOut]
    surfaced: list[SurfacedOut]
