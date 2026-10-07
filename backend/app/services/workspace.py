"""Tier-1 evidence workspace: WHERE the evidence is (segments, transcript, surfaced statements).

Deliberately contains no confidence, rationale, tags or signal: interpretation is tier 2 and is
released only after the assessor locks an initial score.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Evidence, EvidenceMapping, EvidenceSegment
from backend.app.services import pipeline
from backend.app.services import presenters as P


def build(db: Session, ev: Evidence) -> dict[str, Any]:
    run = ev.processing_run or 0
    segs = list(db.scalars(select(EvidenceSegment).where(EvidenceSegment.evidence_id == ev.id,
                                                         EvidenceSegment.run == run,
                                                         EvidenceSegment.source.in_(("scene", "window", "whole")))
                           .order_by(EvidenceSegment.start_s)))
    speech = pipeline.step_output(db, ev, "speech")
    lines = (speech.output or {}).get("segments", []) if speech and speech.status == "done" else []
    maps = db.scalars(select(EvidenceMapping).where(EvidenceMapping.evidence_id == ev.id,
                                                    EvidenceMapping.status != "rejected").order_by(EvidenceMapping.id))
    surfaced = [{
        "mapping_id": m.id, "segment_id": m.segment_id, "start_s": m.segment.start_s, "end_s": m.segment.end_s,
        "pc_id": m.pc_id, "pc_code": m.pc.code, "nos_code": m.pc.nos.code, "statement": m.statement, "mode": m.mode,
    } for m in maps]
    return {
        "evidence": P.evidence_out(ev),
        "segments": [{"id": s.id, "start_s": s.start_s, "end_s": s.end_s, "label": s.label, "source": s.source}
                     for s in segs],
        "transcript": [{"start_s": t["start_s"], "end_s": t["end_s"], "text": t["text"], "language": t.get("language"),
                        "translation_en": t.get("translation_en"), "mode": t.get("mode", "real")} for t in lines],
        "surfaced": surfaced,
    }
