"""Audit, agreement, analytics, sync, research, health and demo schemas."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.app.schemas.common import UTCDateTime


# ---- audit ----
class ActorOut(BaseModel):
    id: int | None
    name: str
    role: str
    code: str | None


class AuditOut(BaseModel):
    id: int
    ts: UTCDateTime
    actor: ActorOut
    action: str
    entity_type: str
    entity_id: int | None
    summary: str
    details: dict[str, Any]
    prev_hash: str
    hash: str


class AuditVerifyOut(BaseModel):
    ok: bool
    entries: int
    head_hash: str | None
    broken_at: int | None
    reason: str | None = None


# ---- agreement ----
class PairOut(BaseModel):
    evidence_label: str
    pc_code: str
    candidate: str
    assessor_a: str
    score_a: int
    assessor_b: str
    score_b: int
    is_demo: bool


class AgreementOut(BaseModel):
    threshold: int
    n_pairs: int
    weighting: Literal["quadratic"]
    status: Literal["insufficient", "reported"]
    kappa: float | None
    kappa_linear: float | None
    exact_agreement: float | None
    adjacent_agreement: float | None
    message: str
    data_source: Literal["demo", "pilot", "mixed", "none"]
    pairs: list[PairOut]


# ---- analytics ----
class PilotValue(BaseModel):
    value: float | None
    n: int
    status: Literal["insufficient", "reported"]
    min_n: int


class DemoValue(BaseModel):
    value: float | None
    n: int


class MetricOut(BaseModel):
    key: str
    label: str
    unit: str
    definition: str
    pilot: PilotValue
    demo: DemoValue
    note: str


class AIInfluenceOut(BaseModel):
    post_reveal_change_rate: float | None
    n: int
    note: str
    data_source: Literal["demo", "pilot", "mixed", "none"]


class CountsOut(BaseModel):
    candidates: int
    assessors: int
    evidence: int
    assessments: int
    double_scored: int


class ImpactOut(BaseModel):
    metrics: list[MetricOut]
    ai_influence: AIInfluenceOut
    counts: CountsOut


# ---- sync ----
class ReserveIn(BaseModel):
    count: int = Field(ge=1, le=20)


class ReserveOut(BaseModel):
    numbers: list[int]


class SyncReportIn(BaseModel):
    local_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    outcome: Literal["failed"] = "failed"
    attempts: int = Field(default=1, ge=1, le=10000)
    error: str | None = Field(default=None, max_length=1000)
    offline_captured: bool = True


class SyncItemOut(BaseModel):
    local_id: str
    status: str
    attempts: int
    evidence_id: int | None
    last_error: str | None
    synced_at: UTCDateTime | None
    updated_at: UTCDateTime


class SyncStatsOut(BaseModel):
    items: int
    synced: int
    failed: int
    success_rate: float | None


# ---- research / system / demo ----
class ResearchOut(BaseModel):
    number: int
    short: str
    citation: str
    url: str | None
    doi: str | None
    category: str
    what_it_says: str
    design_decision: str
    where_in_product: list[str]


class DemoResetIn(BaseModel):
    stage: Literal["fresh", "processed", "assessor_a_scored", "both_scored"]


class DemoResetOut(BaseModel):
    ok: bool
    stage: str
    evidence_id: int | None
    assessment_ids: list[int]
    audit_chain: AuditVerifyOut
    message: str
