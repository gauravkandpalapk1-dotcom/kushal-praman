"""Official hierarchy: Qualification (QP) -> NOS -> Performance Criterion -> versioned Rubric."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base
from backend.app.timeutil import utcnow


class Qualification(Base):
    __tablename__ = "qualifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    nqr_code: Mapped[str] = mapped_column(String(80), unique=True)
    nsqf_level: Mapped[int] = mapped_column(Integer)
    sector_skill_council: Mapped[str | None] = mapped_column(String(200), nullable=True)
    version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    assessment_mode: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_ref: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    nos: Mapped[list["NOS"]] = relationship(back_populates="qualification", order_by="NOS.sort_order")


class NOS(Base):
    __tablename__ = "nos"
    __table_args__ = (UniqueConstraint("qualification_id", "code", name="uq_nos_qualification_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    qualification_id: Mapped[int] = mapped_column(ForeignKey("qualifications.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    qualification: Mapped[Qualification] = relationship(back_populates="nos")
    pcs: Mapped[list["PerformanceCriterion"]] = relationship(back_populates="nos", order_by="PerformanceCriterion.id")


class PerformanceCriterion(Base):
    __tablename__ = "performance_criteria"
    __table_args__ = (UniqueConstraint("nos_id", "code", name="uq_pc_nos_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nos_id: Mapped[int] = mapped_column(ForeignKey("nos.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    max_marks: Mapped[int] = mapped_column(Integer, default=4)
    is_verbatim: Mapped[bool] = mapped_column(Boolean, default=False)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list] = mapped_column(JSON, default=list)

    nos: Mapped[NOS] = relationship(back_populates="pcs")
    rubrics: Mapped[list["Rubric"]] = relationship(back_populates="pc", order_by="Rubric.version")

    @property
    def current_rubric(self) -> "Rubric | None":
        return self.rubrics[-1] if self.rubrics else None


class Rubric(Base):
    __tablename__ = "rubrics"
    __table_args__ = (UniqueConstraint("pc_id", "version", name="uq_rubric_pc_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pc_id: Mapped[int] = mapped_column(ForeignKey("performance_criteria.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | validated
    author_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    pc: Mapped[PerformanceCriterion] = relationship(back_populates="rubrics")
    levels: Mapped[list["RubricLevel"]] = relationship(back_populates="rubric", order_by="RubricLevel.score")


class RubricLevel(Base):
    __tablename__ = "rubric_levels"
    __table_args__ = (UniqueConstraint("rubric_id", "score", name="uq_rubric_level_score"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    rubric_id: Mapped[int] = mapped_column(ForeignKey("rubrics.id", ondelete="CASCADE"), index=True)
    score: Mapped[int] = mapped_column(Integer)
    descriptor: Mapped[str] = mapped_column(Text)
    exemplar: Mapped[str | None] = mapped_column(Text, nullable=True)

    rubric: Mapped[Rubric] = relationship(back_populates="levels")
