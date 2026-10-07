"""Assessment record export (JSON + PDF). The record is NOT a certificate: it is handed to the
Awarding Body, which certifies through the existing ecosystem."""
from __future__ import annotations

import io
import os
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.models import Assessment, AuditLog, EvidenceMapping
from backend.app.services import audit
from backend.app.services.assessment import primary_mapping
from backend.app.timeutil import iso, utcnow

TITLE = "Assessment Record — not a certificate"
HANDOFF = ("Output passes to the Awarding Body. Certification is issued through the existing ecosystem "
           "(e.g. DigiLocker NAD); not integrated in this MVP.")


def trail_entries(db: Session, a: Assessment) -> list[AuditLog]:
    mapping_ids = list(db.scalars(select(EvidenceMapping.id).where(EvidenceMapping.evidence_id == a.evidence_id,
                                                                   EvidenceMapping.pc_id == a.pc_id)))
    cond = or_(
        and_(AuditLog.entity_type == "assessment", AuditLog.entity_id == a.id),
        and_(AuditLog.entity_type == "evidence", AuditLog.entity_id == a.evidence_id),
        and_(AuditLog.entity_type == "mapping", AuditLog.entity_id.in_(mapping_ids or [-1])),
    )
    return list(db.scalars(select(AuditLog).where(cond).order_by(AuditLog.id)))


def _my_decision(entries: list[AuditLog], a: Assessment) -> dict[str, Any] | None:
    user_id = a.assessor.user_id
    for e in reversed(entries):
        if e.action in ("mapping.confirmed", "mapping.edited", "mapping.rejected") and e.actor_id == user_id:
            return {"action": e.action.split(".", 1)[1], "at": iso(e.ts), "summary": e.summary,
                    "reason": (e.details or {}).get("reason")}
    return None


def build(db: Session, a: Assessment) -> dict[str, Any]:
    ev, pc = a.evidence, a.pc
    nos, q, m = pc.nos, pc.nos.qualification, ev.meta
    rubric = a.rubric
    mp = primary_mapping(db, ev.id, pc.id)
    entries = trail_entries(db, a)
    chain = audit.verify(db)
    return {
        "record_type": "assessment_record",
        "title": TITLE,
        "generated_at": iso(utcnow()),
        "kp_mode": get_settings().KP_MODE,
        "is_demo": a.is_demo,
        "candidate": {"name": a.candidate.user.full_name, "candidate_code": a.candidate.candidate_code,
                      "district": a.candidate.district},
        "qualification": {"title": q.title, "nqr_code": q.nqr_code, "nsqf_level": q.nsqf_level,
                          "sector_skill_council": q.sector_skill_council, "version": q.version},
        "nos": {"code": nos.code, "title": nos.title, "version": nos.version},
        "pc": {"code": pc.code, "text": pc.text, "is_verbatim": pc.is_verbatim, "source_note": pc.source_note,
               "max_marks": pc.max_marks},
        "rubric": None if rubric is None else {
            "version": rubric.version, "status": rubric.status, "author_note": rubric.author_note,
            "levels": [{"score": lv.score, "descriptor": lv.descriptor} for lv in rubric.levels]},
        "evidence": {"label": ev.label, "kind": ev.kind, "sha256": ev.sha256, "client_sha256": ev.client_sha256,
                     "integrity_ok": ev.integrity_ok, "captured_at": iso(ev.captured_at), "synced_at": iso(ev.synced_at),
                     "latitude": m.latitude if m else None, "longitude": m.longitude if m else None,
                     "accuracy_m": m.accuracy_m if m else None, "duration_s": m.duration_s if m else None,
                     "offline_captured": ev.offline_captured, "is_demo": ev.is_demo},
        "ai_evidence": None if mp is None else {
            "statement": mp.statement, "mode": mp.mode,
            "mode_badge": "DEMO ANALYSIS" if mp.mode == "demo" else "REAL ANALYSIS",
            "segment": {"start_s": mp.segment.start_s, "end_s": mp.segment.end_s},
            "mapping_status": mp.status,
            "decided_by": mp.decided_by.assessor_code if mp.decided_by else None,
            "this_assessor_decision": _my_decision(entries, a),
            "note": "AI output identifies and describes evidence. It does not assess competency."},
        "assessment": {
            "id": a.id, "assessor_code": a.assessor.assessor_code, "status": a.status, "blind": a.blind,
            "max_score": a.max_score, "opened_at": iso(a.opened_at),
            "initial_score": a.initial_score, "initial_note": a.initial_note,
            "initial_locked_at": iso(a.initial_locked_at), "ai_revealed_at": iso(a.ai_revealed_at),
            "final_score": a.final_score, "final_rationale": a.final_rationale, "finalized_at": iso(a.finalized_at),
            "score_changed": (a.final_score != a.initial_score) if a.final_score is not None else None},
        "audit_trail": [{"id": e.id, "ts": iso(e.ts), "action": e.action, "actor": audit.actor_view(e)["code"]
                         or audit.actor_view(e)["name"], "summary": e.summary, "hash": e.hash,
                         "hash_short": e.hash[:12]} for e in entries],
        "audit_chain": chain,
        "handoff": HANDOFF,
    }


def log_export(db: Session, a: Assessment, user, fmt: str) -> None:
    audit.log(db, actor=user, action="record.exported", entity_type="assessment", entity_id=a.id,
              summary=f"Assessment record ({fmt.upper()}) exported for {a.evidence.label} · {a.pc.code}",
              details={"format": fmt, "status": a.status})


# --------------------------------------------------------------------------- PDF

_FONT = {"regular": "Helvetica", "bold": "Helvetica-Bold", "unicode": False}


def _fonts() -> dict[str, Any]:
    if _FONT.get("_done"):
        return _FONT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ]
    for reg, bold in candidates:
        if os.path.exists(reg) and os.path.exists(bold):
            try:
                pdfmetrics.registerFont(TTFont("KPSans", reg))
                pdfmetrics.registerFont(TTFont("KPSans-Bold", bold))
                _FONT.update(regular="KPSans", bold="KPSans-Bold", unicode=True)
            except Exception:  # noqa: BLE001 - fall back to built-in fonts
                pass
            break
    _FONT["_done"] = True
    return _FONT


def _t(s: Any) -> str:
    """Escape for reportlab Paragraph markup; degrade non-Latin glyphs if no Unicode font."""
    text = "—" if s is None or s == "" else str(s)
    if not _fonts()["unicode"]:
        text = (text.replace("—", "-").replace("–", "-").replace("→", "->").replace("κ", "kappa")
                .replace("≥", ">=").replace("…", "..."))
        text = text.encode("latin-1", "replace").decode("latin-1")
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _mmss(s: float | None) -> str:
    if s is None:
        return "—"
    s = int(round(s))
    return f"{s // 60:02d}:{s % 60:02d}"


def render_pdf(rec: dict[str, Any]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    f = _fonts()
    navy, amber, cream, grey = colors.HexColor("#7F1414"), colors.HexColor("#B7791F"), colors.HexColor("#F6F1E7"), colors.HexColor("#5A5A5A")
    ss = getSampleStyleSheet()
    body = ParagraphStyle("kp-body", parent=ss["BodyText"], fontName=f["regular"], fontSize=9, leading=12, alignment=TA_LEFT)
    small = ParagraphStyle("kp-small", parent=body, fontSize=7.5, leading=9.5, textColor=grey)
    label = ParagraphStyle("kp-label", parent=body, fontName=f["bold"], textColor=navy)
    h1 = ParagraphStyle("kp-h1", parent=body, fontName=f["bold"], fontSize=16, leading=20, textColor=navy)
    h2 = ParagraphStyle("kp-h2", parent=body, fontName=f["bold"], fontSize=11, leading=14, textColor=navy,
                        spaceBefore=8, spaceAfter=4)
    badge = ParagraphStyle("kp-badge", parent=body, fontName=f["bold"], textColor=amber)

    def kv(rows: list[tuple[str, Any]]) -> Table:
        data = [[Paragraph(_t(k), label), Paragraph(_t(v), body)] for k, v in rows]
        t = Table(data, colWidths=[45 * mm, 125 * mm])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#D9D2C3")),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return t

    c, q, n, pc, ev, a = rec["candidate"], rec["qualification"], rec["nos"], rec["pc"], rec["evidence"], rec["assessment"]
    r, ai, chain = rec.get("rubric"), rec.get("ai_evidence"), rec["audit_chain"]
    story: list[Any] = []
    story.append(Paragraph(_t(TITLE), h1))
    story.append(Paragraph(_t(f"Kaushal Pramaan · generated {rec['generated_at']} · mode {rec['kp_mode'].upper()}"
                              + (" · DEMO DATA" if rec.get("is_demo") else "")), small))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Candidate and qualification", h2))
    story.append(kv([
        ("Candidate", f"{c['name']} ({c['candidate_code']})"),
        ("Qualification (QP)", q["title"]),
        ("NQR code · NSQF", f"{q['nqr_code']} · NSQF Level {q['nsqf_level']}"),
        ("NOS", f"{n['code']} — {n['title']}"),
        ("Performance Criterion", f"{pc['code']}: “{pc['text']}”" + (" (verbatim)" if pc["is_verbatim"] else "")),
        ("Rubric", "—" if r is None else f"version {r['version']} · status {r['status'].upper()}"
                                         + (" (to be validated with SSC-certified assessors)" if r["status"] == "draft" else "")),
    ]))

    story.append(Paragraph("Evidence", h2))
    geo = "—" if ev["latitude"] is None else f"{ev['latitude']:.4f}, {ev['longitude']:.4f}" + (
        f" (±{ev['accuracy_m']:g} m)" if ev.get("accuracy_m") else "")
    story.append(kv([
        ("Evidence", f"{ev['label']} · {ev['kind']}" + (" · DEMO MEDIA" if ev["is_demo"] else "")),
        ("SHA-256 (server)", ev["sha256"]),
        ("Integrity", "Client and server hashes match" if ev["integrity_ok"] else "MISMATCH between client and server hash"),
        ("Captured at", ev["captured_at"]),
        ("Geotag", geo),
        ("Captured offline", "yes" if ev["offline_captured"] else "no"),
    ]))

    story.append(Paragraph("AI evidence (retrieval only — not a judgement)", h2))
    if ai:
        story.append(Paragraph(_t(ai["mode_badge"]), badge))
        dec = ai.get("this_assessor_decision")
        story.append(kv([
            ("AI evidence statement", ai["statement"]),
            ("Segment", f"{_mmss(ai['segment']['start_s'])}–{_mmss(ai['segment']['end_s'])}"),
            ("Mapping decision", (f"{dec['action']} by {a['assessor_code']} at {dec['at']}" + (f" — {dec['reason']}" if dec.get("reason") else ""))
             if dec else f"status {ai['mapping_status']}" + (f" (by {ai['decided_by']})" if ai["decided_by"] else "")),
        ]))
    else:
        story.append(Paragraph(_t("No AI evidence mapping exists for this PC."), body))

    story.append(Paragraph("Assessor decision (assessor-first)", h2))
    mx = a["max_score"]
    story.append(kv([
        ("Assessor", a["assessor_code"] + (" (blind second assessment)" if a["blind"] else "")),
        ("Initial score", "—" if a["initial_score"] is None else f"{a['initial_score']}/{mx} · locked {a['initial_locked_at']}"),
        ("Initial note", a["initial_note"]),
        ("AI support revealed", a["ai_revealed_at"] or "not revealed"),
        ("Final score", "—" if a["final_score"] is None else f"{a['final_score']}/{mx} · {a['finalized_at']}"),
        ("Final rationale", a["final_rationale"] or ("not required (final = initial)" if a["final_score"] is not None else "—")),
        ("Status", a["status"]),
    ]))

    story.append(Paragraph("Audit trail", h2))
    rows = [[Paragraph(_t(h), label) for h in ("#", "Time (UTC)", "Action", "Actor", "Summary", "Hash")]]
    for e in rec["audit_trail"]:
        ts = (e["ts"] or "").replace("T", " ").rstrip("Z")
        rows.append([Paragraph(_t(e["id"]), small), Paragraph(_t(ts), small), Paragraph(_t(e["action"]), small),
                     Paragraph(_t(e["actor"]), small), Paragraph(_t(e["summary"]), small),
                     Paragraph(_t(e["hash_short"][:10]), small)])
    t = Table(rows, colWidths=[7 * mm, 26 * mm, 37 * mm, 20 * mm, 61 * mm, 19 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), cream), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#D9D2C3")),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(t)
    story.append(Spacer(1, 4))
    verdict = (f"Audit chain verified: {chain['entries']} entries, head {str(chain['head_hash'])[:16]}…"
               if chain["ok"] else f"AUDIT CHAIN BROKEN at entry {chain['broken_at']}: {chain.get('reason')}")
    story.append(KeepTogether([Paragraph(_t(verdict), label)]))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(f["regular"], 7.5)
        canvas.setFillColor(grey)
        canvas.drawString(15 * mm, 10 * mm, _t(HANDOFF).replace("&amp;", "&"))
        canvas.drawRightString(195 * mm, 5 * mm, f"Page {doc.page}")
        canvas.setStrokeColor(amber)
        canvas.setLineWidth(1.2)
        canvas.line(15 * mm, 287 * mm, 195 * mm, 287 * mm)
        canvas.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm,
                            bottomMargin=18 * mm, title=TITLE, author="Kaushal Pramaan")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
