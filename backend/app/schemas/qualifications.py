"""QP -> NOS -> PC -> Rubric schemas."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend.app.schemas.common import Out


class RubricLevelIO(Out):
    score: int = Field(ge=0, le=100)
    descriptor: str = Field(min_length=1)
    exemplar: str | None = None


class RubricOut(Out):
    id: int
    version: int
    status: Literal["draft", "validated"]
    author_note: str | None = None
    levels: list[RubricLevelIO]


class PCOut(Out):
    id: int
    code: str
    text: str
    is_verbatim: bool
    source_note: str | None
    max_marks: int
    keywords: list[str] = []
    rubric: RubricOut | None = None


class NOSOut(Out):
    id: int
    code: str
    title: str
    version: str | None
    is_mandatory: bool
    pcs: list[PCOut] = []


class QualificationOut(Out):
    id: int
    title: str
    nqr_code: str
    nsqf_level: int
    sector_skill_council: str | None
    version: str | None
    assessment_mode: str | None
    source_ref: int | None


class QualificationListOut(QualificationOut):
    nos_count: int
    pc_count: int


class TreeOut(BaseModel):
    qualification: QualificationOut
    nos: list[NOSOut]


class QualificationIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    nqr_code: str = Field(min_length=1, max_length=80)
    nsqf_level: int = Field(ge=1, le=10)
    sector_skill_council: str | None = None
    version: str | None = None
    assessment_mode: str | None = None
    source_ref: int | None = None


class NOSIn(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=300)
    version: str | None = None
    is_mandatory: bool = True


class PCIn(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    text: str = Field(min_length=1)
    max_marks: int = Field(default=4, ge=1, le=100)
    is_verbatim: bool = False
    source_note: str | None = None
    keywords: list[str] = []


class RubricIn(BaseModel):
    levels: list[RubricLevelIO] = Field(min_length=1)
    status: Literal["draft", "validated"] = "draft"
    author_note: str | None = None
