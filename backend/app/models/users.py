"""Identity: users, candidates, assessors, agencies, reserved evidence numbers."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base
from backend.app.timeutil import utcnow


class AssessmentAgency(Base):
    __tablename__ = "assessment_agencies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(40), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    assessors: Mapped[list["Assessor"]] = relationship(back_populates="agency")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), index=True)  # candidate | assessor | admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    candidate: Mapped["Candidate | None"] = relationship(back_populates="user", uselist=False)
    assessor: Mapped["Assessor | None"] = relationship(back_populates="user", uselist=False)


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    candidate_code: Mapped[str] = mapped_column(String(40), unique=True)
    qualification_id: Mapped[int | None] = mapped_column(ForeignKey("qualifications.id"), nullable=True)
    preferred_language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Per-candidate evidence-number sequence; offline devices reserve blocks from it (/sync/reserve).
    next_evidence_number: Mapped[int] = mapped_column(Integer, default=1)

    user: Mapped[User] = relationship(back_populates="candidate")


class Assessor(Base):
    __tablename__ = "assessors"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    assessor_code: Mapped[str] = mapped_column(String(20), unique=True)
    agency_id: Mapped[int | None] = mapped_column(ForeignKey("assessment_agencies.id"), nullable=True)

    user: Mapped[User] = relationship(back_populates="assessor")
    agency: Mapped[AssessmentAgency | None] = relationship(back_populates="assessors")


class EvidenceNumberReservation(Base):
    """Evidence numbers handed to an offline device so 'Evidence #17' is real before sync."""

    __tablename__ = "evidence_number_reservations"
    __table_args__ = (UniqueConstraint("candidate_id", "number", name="uq_reservation_candidate_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    reserved_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
