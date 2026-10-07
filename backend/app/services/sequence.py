"""Per-candidate evidence-number sequence, allocated atomically.

A read-then-write (`n = cand.next; cand.next = n + k`) races when two requests for the same
candidate arrive together (e.g. the capture screen and the sync engine both reserving numbers):
both read 17 and the second insert violates the unique (candidate_id, number) constraint.
A single `UPDATE ... SET n = n + k ... RETURNING n` is atomic in SQLite and PostgreSQL, so
concurrent callers get disjoint ranges.
"""
from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.orm import Session

from backend.app.models import Candidate


def take(db: Session, candidate: Candidate, count: int = 1) -> list[int]:
    """Atomically take `count` consecutive numbers for `candidate`; returns them in order."""
    new_next = db.execute(
        update(Candidate)
        .where(Candidate.id == candidate.id)
        .values(next_evidence_number=Candidate.next_evidence_number + count)
        .returning(Candidate.next_evidence_number)
        .execution_options(synchronize_session=False)
    ).scalar_one()
    db.refresh(candidate, attribute_names=["next_evidence_number"])
    return list(range(new_next - count, new_next))
