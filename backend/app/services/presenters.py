"""ORM -> API dict presenters shared by routers and services (shapes follow docs/API.md)."""
from __future__ import annotations

from typing import Any

from backend.app.models import (
    NOS,
    Assessor,
    Candidate,
    Evidence,
    PerformanceCriterion,
    Qualification,
    Rubric,
    User,
)
from backend.app.security import media_tokens


def user_out(u: User) -> dict[str, Any]:
    c, a = u.candidate, u.assessor
    return {
        "id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role, "is_active": u.is_active,
        "candidate": None if c is None else {
            "id": c.id, "candidate_code": c.candidate_code, "qualification_id": c.qualification_id,
            "preferred_language": c.preferred_language, "district": c.district,
        },
        "assessor": None if a is None else {
            "id": a.id, "assessor_code": a.assessor_code,
            "agency": None if a.agency is None else {"id": a.agency.id, "name": a.agency.name, "code": a.agency.code},
        },
    }


def candidate_ref(c: Candidate) -> dict[str, Any]:
    return {"id": c.id, "full_name": c.user.full_name, "candidate_code": c.candidate_code}


def assessor_ref(a: Assessor) -> dict[str, Any]:
    return {"id": a.id, "assessor_code": a.assessor_code, "full_name": a.user.full_name}


def rubric_out(r: Rubric | None) -> dict[str, Any] | None:
    if r is None:
        return None
    return {
        "id": r.id, "version": r.version, "status": r.status, "author_note": r.author_note,
        "levels": [{"score": lv.score, "descriptor": lv.descriptor, "exemplar": lv.exemplar} for lv in r.levels],
    }


def pc_out(pc: PerformanceCriterion, rubric: Rubric | None = None) -> dict[str, Any]:
    return {
        "id": pc.id, "code": pc.code, "text": pc.text, "is_verbatim": pc.is_verbatim, "source_note": pc.source_note,
        "max_marks": pc.max_marks, "keywords": list(pc.keywords or []),
        "rubric": rubric_out(rubric if rubric is not None else pc.current_rubric),
    }


def nos_brief(n: NOS) -> dict[str, Any]:
    return {"id": n.id, "code": n.code, "title": n.title}


def qualification_out(q: Qualification) -> dict[str, Any]:
    return {
        "id": q.id, "title": q.title, "nqr_code": q.nqr_code, "nsqf_level": q.nsqf_level,
        "sector_skill_council": q.sector_skill_council, "version": q.version,
        "assessment_mode": q.assessment_mode, "source_ref": q.source_ref,
    }


def qualification_brief(q: Qualification) -> dict[str, Any]:
    return {"id": q.id, "title": q.title, "nqr_code": q.nqr_code, "nsqf_level": q.nsqf_level}


def tree_out(q: Qualification) -> dict[str, Any]:
    return {
        "qualification": qualification_out(q),
        "nos": [
            {"id": n.id, "code": n.code, "title": n.title, "version": n.version, "is_mandatory": n.is_mandatory,
             "pcs": [pc_out(pc) for pc in n.pcs]}
            for n in q.nos
        ],
    }


def evidence_out(e: Evidence) -> dict[str, Any]:
    m = e.meta
    return {
        "id": e.id, "display_number": e.display_number, "label": e.label, "kind": e.kind,
        "original_filename": e.original_filename, "mime_type": e.mime_type, "size_bytes": e.size_bytes,
        "sha256": e.sha256, "client_sha256": e.client_sha256, "integrity_ok": e.integrity_ok, "status": e.status,
        "is_demo": e.is_demo, "offline_captured": e.offline_captured, "encrypted_at_rest": e.encrypted_at_rest,
        "captured_at": e.captured_at, "synced_at": e.synced_at, "qualification_id": e.qualification_id,
        "pc_hint_id": e.pc_hint_id, "candidate": candidate_ref(e.candidate),
        "metadata": {} if m is None else {
            "latitude": m.latitude, "longitude": m.longitude, "accuracy_m": m.accuracy_m, "device": m.device,
            "duration_s": m.duration_s, "width": m.width, "height": m.height, "language": m.language,
            "sync_attempts": m.sync_attempts, "queued_at": m.queued_at,
        },
        "media_url": media_tokens.media_url(e.id),
    }
