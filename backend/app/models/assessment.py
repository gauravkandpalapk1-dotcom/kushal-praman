"""Assessor-first assessments and their append-only scores."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base
from backend.app.timeutil import utcnow


class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (
        UniqueConstraint("evidence_id", "pc_id", "assessor_id", name="uq_assessment_evidence_pc_assessor"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence.id"), index=True)
    pc_id: Mapped[int] = mapped_column(ForeignKey("performance_criteria.id"), index=True)
    assessor_id: Mapped[int] = mapped_column(ForeignKey("assessors.id"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), index=True)
    rubric_id: Mapped[int | None] = mapped_column(ForeignKey("rubrics.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="opened")  # opened|initial_locked|ai_revealed|finalized
    max_score: Mapped[int] = mapped_column(Integer, default=4)
    blind: Mapped[bool] = mapped_column(Boolean, default=False)
    is_second_assessor: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    initial_locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    initial_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_revealed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    final_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    evidence = relationship("Evidence")
    pc = relationship("PerformanceCriterion")
    assessor = relationship("Assessor")
    candidate = relationship("Candidate")
    rubric = relationship("Rubric")
    scores: Mapped[list["AssessmentScore"]] = relationship(back_populates="assessment", order_by="AssessmentScore.id")

    def score_for(self, phase: str) -> "AssessmentScore | None":
        return next((s for s in self.scores if s.phase == phase), None)

    @property
    def initial_score(self) -> int | None:
        s = self.score_for("initial")
        return s.score if s else None

    @property
    def final_score(self) -> int | None:
        s = self.score_for("final")
        return s.score if s else None

    @property
    def is_locked(self) -> bool:
        return self.initial_score is not None


class AssessmentScore(Base):
    """Append-only. One `initial` and at most one `final` row per assessment (DB-enforced)."""

    __tablename__ = "assessment_scores"
    __table_args__ = (UniqueConstraint("assessment_id", "phase", name="uq_score_assessment_phase"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"), index=True)
    phase: Mapped[str] = mapped_column(String(10))  # initial | final
    score: Mapped[int] = mapped_column(Integer)
    max_score: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    assessment: Mapped[Assessment] = relationship(back_populates="scores")
