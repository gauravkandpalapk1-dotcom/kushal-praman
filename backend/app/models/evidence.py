"""Evidence, its metadata, time segments, per-step AI analysis rows and evidence->PC mappings."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base
from backend.app.timeutil import utcnow


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (UniqueConstraint("candidate_id", "display_number", name="uq_evidence_candidate_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), index=True)
    qualification_id: Mapped[int] = mapped_column(ForeignKey("qualifications.id"))
    pc_hint_id: Mapped[int | None] = mapped_column(ForeignKey("performance_criteria.id"), nullable=True)
    display_number: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))  # video | photo | audio | document
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stored_filename: Mapped[str] = mapped_column(String(100))  # <sha256>.<ext>, never user-supplied
    mime_type: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    client_sha256: Mapped[str] = mapped_column(String(64))
    integrity_ok: Mapped[bool] = mapped_column(Boolean)
    local_id: Mapped[str] = mapped_column(String(64), unique=True)  # idempotency key from the device
    status: Mapped[str] = mapped_column(String(20), default="received")  # received|processing|ready|failed
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    offline_captured: Mapped[bool] = mapped_column(Boolean, default=False)
    encrypted_at_rest: Mapped[bool] = mapped_column(Boolean, default=False)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_run: Mapped[int] = mapped_column(Integer, default=0)

    candidate = relationship("Candidate")
    qualification = relationship("Qualification")
    meta: Mapped["EvidenceMetadata | None"] = relationship(back_populates="evidence", uselist=False)

    @property
    def label(self) -> str:
        return f"Evidence #{self.display_number}"


class EvidenceMetadata(Base):
    __tablename__ = "evidence_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), unique=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    device: Mapped[str | None] = mapped_column(String(300), nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sync_attempts: Mapped[int] = mapped_column(Integer, default=1)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_codec: Mapped[str | None] = mapped_column(String(40), nullable=True)
    audio_codec: Mapped[str | None] = mapped_column(String(40), nullable=True)
    has_audio: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    format_name: Mapped[str | None] = mapped_column(String(80), nullable=True)

    evidence: Mapped[Evidence] = relationship(back_populates="meta")


class EvidenceSegment(Base):
    __tablename__ = "evidence_segments"

    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), index=True)
    run: Mapped[int] = mapped_column(Integer, default=1)
    idx: Mapped[int] = mapped_column(Integer, default=0)
    start_s: Mapped[float] = mapped_column(Float)
    end_s: Mapped[float] = mapped_column(Float)
    label: Mapped[str] = mapped_column(String(80))
    source: Mapped[str] = mapped_column(String(20))  # scene | window | whole | mapping | manual


class AIAnalysis(Base):
    """One row per pipeline step per processing run (key, status, mode, provider, model, output)."""

    __tablename__ = "ai_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), index=True)
    run: Mapped[int] = mapped_column(Integer, default=1)
    seq: Mapped[int] = mapped_column(Integer)
    key: Mapped[str] = mapped_column(String(30))
    label: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|running|done|skipped|failed
    mode: Mapped[str | None] = mapped_column(String(20), nullable=True)  # real|demo|unavailable
    provider: Mapped[str | None] = mapped_column(String(60), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    triggered_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EvidenceMapping(Base):
    """Evidence segment -> Performance Criterion link proposed by the mapper.

    `confidence` is an UNCALIBRATED relevance score, not a probability.
    """

    __tablename__ = "evidence_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id", ondelete="CASCADE"), index=True)
    segment_id: Mapped[int] = mapped_column(ForeignKey("evidence_segments.id"))
    pc_id: Mapped[int] = mapped_column(ForeignKey("performance_criteria.id"), index=True)
    run: Mapped[int] = mapped_column(Integer, default=1)
    statement: Mapped[str] = mapped_column(Text)
    signal: Mapped[str] = mapped_column(String(20), default="supports")  # supports|partial|not_found
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    mode: Mapped[str] = mapped_column(String(20))  # real | demo
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|confirmed|edited|rejected
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("assessors.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    segment: Mapped[EvidenceSegment] = relationship()
    pc = relationship("PerformanceCriterion")
    decided_by = relationship("Assessor")
