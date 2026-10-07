"""Processing pipeline orchestration (background thread, own DB session, step-by-step persistence).

Steps (in order): integrity, probe, segmentation, speech, vision, ocr, llm, mapping.
  * integrity / probe / segmentation are ALWAYS real (hashlib, ffprobe, ffmpeg).
  * For the known demo asset in KP_MODE=demo, speech / vision / llm / mapping come from the seeded
    fixture with mode "demo". The real lexical mapper still runs and its ranking is recorded.
  * Otherwise real adapters run if available; unavailable => status "skipped", mode "unavailable",
    with the reason in `detail`. Nothing is faked.
Every AI text passes the guardrail before it is stored.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ai import guardrails
from ai import mapper as lexmap
from ai.base import AdapterError, TimeSpan
from ai.demo_provider import sha256_file
from ai.registry import AdapterSet
from ai.segmentation import ffmpeg_info, probe, segment_media
from backend.app.config import get_settings
from backend.app.db import SessionLocal
from backend.app.errors import Conflict
from backend.app.models import (
    NOS,
    AIAnalysis,
    Evidence,
    EvidenceMapping,
    EvidenceMetadata,
    EvidenceSegment,
    PerformanceCriterion,
    User,
)
from backend.app.services import ai_runtime, audit
from backend.app.services.evidence import stored_path
from backend.app.timeutil import utcnow

log = logging.getLogger("kp.pipeline")

STEPS: list[tuple[str, str]] = [
    ("integrity", "Integrity check (SHA-256)"),
    ("probe", "Media probe (ffprobe)"),
    ("segmentation", "Segmentation (ffmpeg scene detection)"),
    ("speech", "Speech-to-text"),
    ("vision", "Visual tags"),
    ("ocr", "OCR (text in photos/documents)"),
    ("llm", "Neutral segment descriptions (LLM)"),
    ("mapping", "Evidence Mapper (evidence → PC)"),
]
FATAL_STEPS = {"integrity", "probe", "segmentation", "mapping"}
DEMO_BADGE = "DEMO ANALYSIS (seeded fixture for the demo asset)"


class FatalStep(Exception):
    pass


@dataclass
class Outcome:
    status: str  # done | skipped
    mode: str  # real | demo | unavailable
    detail: str
    provider: str | None = None
    model: str | None = None
    output: dict[str, Any] | None = None


@dataclass
class Ctx:
    db: Session
    ev: Evidence
    path: Path
    run: int
    adapters: AdapterSet
    duration: float | None = None
    has_video: bool = False
    has_audio: bool = False
    segments: list[EvidenceSegment] = field(default_factory=list)
    transcript: list[dict[str, Any]] = field(default_factory=list)
    tags: list[dict[str, Any]] = field(default_factory=list)
    descriptions: list[dict[str, Any]] = field(default_factory=list)
    summary: str | None = None
    ocr_text: str = ""

    @property
    def demo(self) -> bool:
        return self.adapters.demo


# --------------------------------------------------------------------------- status / views

def run_rows(db: Session, ev: Evidence, run: int | None = None) -> list[AIAnalysis]:
    r = ev.processing_run if run is None else run
    if not r:
        return []
    return list(db.scalars(select(AIAnalysis).where(AIAnalysis.evidence_id == ev.id, AIAnalysis.run == r)
                           .order_by(AIAnalysis.seq)))


def job_status(rows: list[AIAnalysis]) -> str:
    if not rows:
        return "not_started"
    if any(r.status == "failed" and r.key in FATAL_STEPS for r in rows):
        return "failed"
    if all(r.status == "pending" for r in rows):
        return "queued"
    if any(r.status in ("pending", "running") for r in rows):
        return "running"
    return "done"


def processing_out(db: Session, ev: Evidence) -> dict[str, Any]:
    rows = run_rows(db, ev)
    status = job_status(rows)
    started = [r.started_at for r in rows if r.started_at]
    finished = [r.finished_at for r in rows if r.finished_at]
    return {
        "evidence_id": ev.id,
        "run": ev.processing_run,
        "status": status,
        "mode": ("demo" if any(r.mode == "demo" for r in rows) else "real") if rows else None,
        "started_at": min(started) if started else None,
        "finished_at": max(finished) if finished and status in ("done", "failed") else None,
        "steps": [{"key": r.key, "label": r.label, "status": r.status, "mode": r.mode, "provider": r.provider,
                   "model": r.model, "detail": r.detail, "started_at": r.started_at, "finished_at": r.finished_at}
                  for r in rows],
    }


def step_output(db: Session, ev: Evidence, key: str) -> AIAnalysis | None:
    return next((r for r in run_rows(db, ev) if r.key == key), None)


# --------------------------------------------------------------------------- start

def start(db: Session, ev: Evidence, actor: User, *, force: bool = False, background: bool = True) -> dict[str, Any]:
    with audit.write_lock():
        status = job_status(run_rows(db, ev))
        if status in ("queued", "running"):
            if force:
                raise Conflict("Processing is already running for this evidence.", "processing_running")
            return processing_out(db, ev)
        if status == "done" and not force:
            return processing_out(db, ev)
        if force:
            _clear_previous(db, ev)
        run = (ev.processing_run or 0) + 1
        ev.processing_run = run
        ev.status = "processing"
        for seq, (key, label) in enumerate(STEPS):
            db.add(AIAnalysis(evidence_id=ev.id, run=run, seq=seq, key=key, label=label, status="pending",
                              triggered_by_id=actor.id))
        code = actor.assessor.assessor_code if actor.assessor else actor.full_name
        audit.log(db, actor=actor, action="processing.started", entity_type="evidence", entity_id=ev.id,
                  summary=f"Processing started for {ev.label} by {code}" + (" (forced re-run)" if force else ""),
                  details={"run": run, "force": force, "kp_mode": get_settings().KP_MODE,
                           "demo_asset": ai_runtime.registry().use_demo_for(ev.is_demo)})
    if background:
        threading.Thread(target=run_pipeline, args=(ev.id, run), name=f"kp-pipeline-{ev.id}-{run}", daemon=True).start()
    else:
        run_pipeline(ev.id, run)
        db.expire_all()
    return processing_out(db, ev)


def _clear_previous(db: Session, ev: Evidence) -> None:
    """Forced re-run: drop undecided proposals and unreferenced segments; decided mappings stay."""
    db.execute(delete(EvidenceMapping).where(EvidenceMapping.evidence_id == ev.id, EvidenceMapping.status == "pending"))
    referenced = select(EvidenceMapping.segment_id).where(EvidenceMapping.evidence_id == ev.id)
    db.execute(delete(EvidenceSegment).where(EvidenceSegment.evidence_id == ev.id, EvidenceSegment.id.not_in(referenced)))


# --------------------------------------------------------------------------- run

def run_pipeline(evidence_id: int, run: int) -> None:
    db = SessionLocal()
    try:
        ev = db.get(Evidence, evidence_id)
        if ev is None:
            return
        reg = ai_runtime.registry()
        ctx = Ctx(db=db, ev=ev, path=stored_path(ev), run=run, adapters=reg.adapters_for(ev.is_demo))
        handlers: dict[str, Callable[[Ctx], Outcome]] = {
            "integrity": _integrity, "probe": _probe, "segmentation": _segmentation, "speech": _speech,
            "vision": _vision, "ocr": _ocr, "llm": _llm, "mapping": _mapping,
        }
        failed_at: tuple[str, str] | None = None
        for key, _label in STEPS:
            row = db.scalar(select(AIAnalysis).where(AIAnalysis.evidence_id == evidence_id, AIAnalysis.run == run,
                                                     AIAnalysis.key == key))
            if row is None:
                return  # wiped (e.g. demo reset) while running
            if failed_at:
                row.status, row.mode, row.detail = "skipped", None, f"Not run: '{failed_at[0]}' step failed."
                row.finished_at = utcnow()
                db.commit()
                continue
            row.status, row.started_at = "running", utcnow()
            db.commit()
            try:
                out = handlers[key](ctx)
                row.status, row.mode, row.detail = out.status, out.mode, out.detail
                row.provider, row.model, row.output = out.provider, out.model, out.output
            except (FatalStep, AdapterError, Exception) as exc:  # noqa: BLE001
                msg = str(exc) if isinstance(exc, (FatalStep, AdapterError)) else f"{type(exc).__name__}: {str(exc)[:200]}"
                log.warning("pipeline step %s failed for evidence %s: %s", key, evidence_id, msg)
                db.rollback()
                row = db.get(AIAnalysis, row.id)
                row.status, row.detail = "failed", msg
                row.mode = row.mode or ("demo" if ctx.demo and key in ("speech", "vision", "llm", "mapping") else "real")
                if key in FATAL_STEPS:
                    failed_at = (key, msg)
            row.finished_at = utcnow()
            db.commit()

        ev = db.get(Evidence, evidence_id)
        if ev is None:
            return
        n_maps = len(list(db.scalars(select(EvidenceMapping.id).where(EvidenceMapping.evidence_id == ev.id,
                                                                     EvidenceMapping.run == run))))
        mode = "demo" if ctx.demo else "real"
        if failed_at:
            ev.status = "failed"
            audit.log(db, actor=None, action="processing.completed", entity_type="evidence", entity_id=ev.id,
                      summary=f"Processing failed for {ev.label} at step '{failed_at[0]}'",
                      details={"run": run, "status": "failed", "step": failed_at[0], "error": failed_at[1]})
        else:
            ev.status = "ready"
            audit.log(db, actor=None, action="processing.completed", entity_type="evidence", entity_id=ev.id,
                      summary=(f"Processing completed for {ev.label}: {len(ctx.segments)} segments, "
                               f"{n_maps} potential evidence link(s) proposed ({mode} analysis)"),
                      details={"run": run, "status": "done", "mode": mode, "segments": len(ctx.segments),
                               "mappings": n_maps})
    except Exception:  # noqa: BLE001 - never let a background thread die silently
        log.exception("pipeline crashed for evidence %s", evidence_id)
        db.rollback()
    finally:
        db.close()


# --------------------------------------------------------------------------- steps

def _integrity(ctx: Ctx) -> Outcome:
    if not ctx.path.is_file():
        raise FatalStep("Stored file is missing.")
    sha = sha256_file(ctx.path)
    if sha != ctx.ev.sha256:
        raise FatalStep(f"Stored file hash {sha[:12]}… differs from the hash recorded at receipt "
                        f"{ctx.ev.sha256[:12]}…: file altered after receipt.")
    client = "matches the client hash" if ctx.ev.integrity_ok else "does NOT match the client hash (flagged at receipt)"
    return Outcome("done", "real", f"SHA-256 recomputed on the stored file ({sha[:12]}…); {client}.",
                   "hashlib", "sha256", {"sha256": sha, "client_sha256": ctx.ev.client_sha256,
                                         "client_match": ctx.ev.integrity_ok})


def _fmt_duration(s: float | None) -> str:
    return lexmap.format_ts(s) if s else "unknown duration"


def _probe(ctx: Ctx) -> Outcome:
    ff = ffmpeg_info()
    if ctx.ev.kind == "document":
        return Outcome("skipped", "real", "Not applicable to documents.", "ffprobe", ff.get("version"))
    try:
        p = probe(ctx.path)
    except Exception as exc:  # noqa: BLE001
        raise FatalStep(f"ffprobe could not read the file: {exc}") from exc
    if ctx.ev.kind in ("video", "audio") and not p.duration_s:
        raise FatalStep("ffprobe reported no duration for time-based media.")
    if ctx.ev.kind == "video" and not p.has_video:
        raise FatalStep("No video stream found in a 'video' submission.")
    meta = ctx.ev.meta or EvidenceMetadata(evidence_id=ctx.ev.id)
    meta.duration_s = p.duration_s if ctx.ev.kind in ("video", "audio") else None
    meta.width, meta.height = p.width, p.height
    meta.video_codec, meta.audio_codec = p.video_codec, p.audio_codec
    meta.has_audio, meta.format_name = p.has_audio, p.format_name
    ctx.db.add(meta)
    ctx.duration, ctx.has_video, ctx.has_audio = meta.duration_s, p.has_video, p.has_audio
    parts = []
    if ctx.ev.kind in ("video", "audio"):
        parts.append(_fmt_duration(p.duration_s))
    if p.video_codec:
        parts.append(f"{p.video_codec} {p.width}×{p.height}")
    parts.append(f"audio {p.audio_codec}" if p.has_audio else "no audio track")
    return Outcome("done", "real", " · ".join(parts), "ffprobe", ff.get("version"), p.to_dict())


def _segmentation(ctx: Ctx) -> Outcome:
    s = get_settings()
    ff = ffmpeg_info()
    try:
        res = segment_media(ctx.path, kind=ctx.ev.kind, duration=ctx.duration, has_video=ctx.has_video,
                            threshold=s.SCENE_THRESHOLD, window=s.FALLBACK_WINDOW_S)
    except Exception as exc:  # noqa: BLE001
        raise FatalStep(f"Segmentation failed: {exc}") from exc
    rows = []
    for i, seg in enumerate(res.segments):
        row = EvidenceSegment(evidence_id=ctx.ev.id, run=ctx.run, idx=i, start_s=seg.start_s, end_s=seg.end_s,
                              label=seg.label, source=seg.source)
        ctx.db.add(row)
        rows.append(row)
    ctx.db.flush()
    ctx.segments = rows
    return Outcome("done", "real", res.detail, "ffmpeg", ff.get("version"), res.to_dict())


def _not_applicable(kind: str) -> Outcome:
    return Outcome("skipped", "real", f"Not applicable to {kind}.")


def _unavailable(adapter) -> Outcome | None:
    a = adapter.availability()
    if not a.available:
        return Outcome("skipped", "unavailable", a.detail, adapter.provider, adapter.model or None)
    return None


def _speech(ctx: Ctx) -> Outcome:
    if ctx.ev.kind in ("photo", "document"):
        return _not_applicable(ctx.ev.kind)
    adapter = ctx.adapters.speech
    if not ctx.demo and not ctx.has_audio:
        return Outcome("skipped", "real", "No audio track in the recording.", adapter.provider, adapter.model or None)
    if (skip := _unavailable(adapter)) is not None:
        return skip
    hint = ctx.ev.meta.language if ctx.ev.meta else None
    res = adapter.transcribe(ctx.path, language_hint=hint)
    ctx.transcript = [
        {"start_s": t.start_s, "end_s": t.end_s, "text": t.text, "language": t.language or res.language,
         "translation_en": t.translation_en, "mode": res.mode} for t in res.segments
    ]
    flagged = [i for i, t in enumerate(ctx.transcript) if guardrails.find_violations(t["text"])
               or guardrails.find_violations(t["translation_en"])]
    detail = f"{len(ctx.transcript)} transcript segments, language '{res.language or 'unknown'}'"
    if ctx.demo:
        detail += f" · {DEMO_BADGE}"
    if flagged:
        detail += f" · {len(flagged)} line(s) flagged by guardrail (verbatim speech kept as evidence)"
    return Outcome("done", res.mode, detail, res.provider, res.model,
                   {"language": res.language, "segments": ctx.transcript, "guardrail_flagged": flagged})


def _vision(ctx: Ctx) -> Outcome:
    if ctx.ev.kind in ("audio", "document"):
        return _not_applicable(ctx.ev.kind)
    adapter = ctx.adapters.vision
    if (skip := _unavailable(adapter)) is not None:
        return skip
    spans = [TimeSpan(s.start_s, s.end_s) for s in ctx.segments]
    res = adapter.describe(ctx.path, kind=ctx.ev.kind, spans=spans)
    removed: set[str] = set()
    for st in res.tags:
        clean, v = guardrails.filter_tags(st.tags)
        removed.update(v)
        ctx.tags.append({"start_s": st.start_s, "end_s": st.end_s, "tags": clean})
    n = sum(len(t["tags"]) for t in ctx.tags)
    detail = f"{n} tags across {len(ctx.tags)} segments"
    if ctx.demo:
        detail += f" · {DEMO_BADGE}"
    return Outcome("done", res.mode, detail, res.provider, res.model,
                   {"tags": ctx.tags, "guardrail_removed": sorted(removed)})


def _ocr(ctx: Ctx) -> Outcome:
    if ctx.ev.kind in ("video", "audio"):
        return _not_applicable(ctx.ev.kind)
    adapter = ctx.adapters.ocr
    if (skip := _unavailable(adapter)) is not None:
        return skip
    res = adapter.extract(ctx.path, mime_type=ctx.ev.mime_type)
    ctx.ocr_text = res.text
    return Outcome("done", res.mode, f"{len(res.text)} characters of text extracted", res.provider, res.model,
                   {"text": res.text})


def _qualification_pcs(ctx: Ctx) -> list[tuple[PerformanceCriterion, NOS]]:
    q = select(PerformanceCriterion, NOS).join(NOS, PerformanceCriterion.nos_id == NOS.id).where(
        NOS.qualification_id == ctx.ev.qualification_id)
    return [(pc, n) for pc, n in ctx.db.execute(q).all()]


def _segment_texts(ctx: Ctx) -> list[lexmap.SegmentText]:
    def overlaps(a0, a1, b0, b1) -> bool:
        mid = (b0 + b1) / 2
        return a0 <= mid < a1 or (a0 == a1 == b0)

    out = []
    for s in ctx.segments:
        lines = [t for t in ctx.transcript if overlaps(s.start_s, s.end_s, t["start_s"], t["end_s"])]
        transcript = " ".join(f"{t['text']} {t.get('translation_en') or ''}" for t in lines)
        tags = [tag for t in ctx.tags if overlaps(s.start_s, s.end_s, t["start_s"], t["end_s"]) for tag in t["tags"]]
        desc = " ".join(d["description"] for d in ctx.descriptions
                        if overlaps(s.start_s, s.end_s, d["start_s"], d["end_s"]))
        out.append(lexmap.SegmentText(s.start_s, s.end_s, transcript, tags, desc,
                                      ctx.ocr_text if s.source == "whole" else "", s.id))
    return out


def _llm(ctx: Ctx) -> Outcome:
    adapter = ctx.adapters.llm
    if (skip := _unavailable(adapter)) is not None:
        return skip
    seg_ctx = [{"start_s": t.start_s, "end_s": t.end_s, "transcript": t.transcript.strip()[:1500],
                "tags": t.tags, "ocr": t.ocr[:1500]} for t in _segment_texts(ctx)
               if t.transcript.strip() or t.tags or t.ocr]
    if not seg_ctx and not ctx.demo:
        return Outcome("skipped", "real", "No transcript, tags or OCR text to describe.", adapter.provider,
                       adapter.model or None)
    pcs = [{"code": pc.code, "text": pc.text} for pc, _ in _qualification_pcs(ctx)]
    res = adapter.describe_segments(seg_ctx, pcs)
    removed: set[str] = set()
    for d in res.descriptions:
        g = guardrails.neutralise(d.description)
        removed.update(g.violations)
        ctx.descriptions.append({"start_s": d.start_s, "end_s": d.end_s, "description": g.text})
    gs = guardrails.neutralise(res.summary)
    removed.update(gs.violations)
    ctx.summary = gs.text or None
    detail = f"{len(ctx.descriptions)} neutral segment description(s) and a summary"
    if ctx.demo:
        detail += f" · {DEMO_BADGE}"
    if removed:
        detail += f" · guardrail removed: {', '.join(sorted(removed))}"
    return Outcome("done", res.mode, detail, res.provider, res.model,
                   {"descriptions": ctx.descriptions, "summary": ctx.summary, "guardrail_removed": sorted(removed)})


def _anchor_segment(ctx: Ctx, start: float, end: float) -> EvidenceSegment:
    for s in ctx.segments:
        if abs(s.start_s - start) < 0.51 and abs(s.end_s - end) < 0.51:
            return s
    seg = EvidenceSegment(evidence_id=ctx.ev.id, run=ctx.run, idx=len(ctx.segments), start_s=start, end_s=end,
                          label=f"Surfaced {lexmap.format_ts(start)}–{lexmap.format_ts(end)}", source="mapping")
    ctx.db.add(seg)
    ctx.db.flush()
    ctx.segments.append(seg)
    return seg


def _mapping(ctx: Ctx) -> Outcome:
    pcs = _qualification_pcs(ctx)
    specs = [lexmap.PCSpec(pc.id, pc.code, pc.text, list(pc.keywords or []), n.code) for pc, n in pcs]
    texts = _segment_texts(ctx)
    ranking = lexmap.rank(texts, specs)
    baseline = {code: [m.to_dict() for m in ms[:3]] for code, ms in ranking.items()}
    proposals: list[dict[str, Any]] = []
    by_code = {(n.code, pc.code): pc for pc, n in pcs}

    if ctx.demo:
        for fm in ai_runtime.demo_provider().fixture.get("mappings", []):
            pc = by_code.get((fm["nos_code"], fm["pc_code"]))
            if pc is None:
                continue
            start, end = float(fm["start_s"]), float(fm["end_s"])
            tags = next((t["tags"] for t in ctx.tags if abs(t["start_s"] - start) < 0.51 and abs(t["end_s"] - end) < 0.51), [])
            proposals.append({"pc": pc, "start": start, "end": end, "confidence": fm.get("confidence"),
                              "rationale": fm.get("rationale"), "signal": fm.get("signal", "supports"),
                              "tags": tags, "mode": "demo"})
    else:
        pc_by_id = {pc.id: pc for pc, _ in pcs}
        for m in lexmap.propose(texts, specs):
            proposals.append({"pc": pc_by_id[m.pc_id], "start": m.start_s, "end": m.end_s, "confidence": m.score,
                              "rationale": m.rationale(), "signal": m.signal,
                              "tags": m.matched_keywords + m.matched_terms, "mode": "real"})

    created: list[EvidenceMapping] = []
    with audit.write_lock():
        for p in proposals:
            seg = _anchor_segment(ctx, p["start"], p["end"])
            stmt = guardrails.neutralise(lexmap.statement(p["pc"].code, seg.start_s, seg.end_s)).text
            rationale = guardrails.neutralise(p["rationale"]).text if p["rationale"] else None
            tags, _ = guardrails.filter_tags(p["tags"])
            mp = EvidenceMapping(evidence_id=ctx.ev.id, segment_id=seg.id, pc_id=p["pc"].id, run=ctx.run,
                                 statement=stmt, signal=p["signal"], confidence=p["confidence"], rationale=rationale,
                                 tags=tags, mode=p["mode"], status="pending")
            ctx.db.add(mp)
            created.append(mp)
        ctx.db.flush()
        ctx.db.commit()
        for mp in created:
            pc = mp.pc
            audit.log(ctx.db, actor=None, action="mapping.proposed", entity_type="mapping", entity_id=mp.id,
                      summary=f"{mp.statement[:-1]} ({ctx.ev.label}, {mp.mode} analysis)",
                      details={"evidence_id": ctx.ev.id, "pc_id": pc.id, "pc_code": pc.code,
                               "segment_id": mp.segment_id, "start_s": mp.segment.start_s, "end_s": mp.segment.end_s,
                               "mode": mp.mode, "run": ctx.run})

    output = {"proposed": [{"mapping_id": m.id, "pc_code": m.pc.code, "start_s": m.segment.start_s,
                            "end_s": m.segment.end_s, "mode": m.mode} for m in created],
              "baseline_ranking": baseline,
              "score_note": "Relevance scores are uncalibrated ranking scores, not probabilities."}
    if not specs:
        return Outcome("done", "real", "No Performance Criteria with text in this qualification; nothing to map.",
                       "lexical-baseline", "keyword+PC-text overlap v1", output)
    if ctx.demo:
        parts = [f"{DEMO_BADGE}: {len(created)} seeded mapping(s)"]
        for m in created:
            top = ranking.get(m.pc.code, [])
            if top and top[0].score > 0:
                agree = "agrees" if abs(top[0].start_s - m.segment.start_s) < 0.51 else "differs"
                parts.append(f"real lexical baseline ranks {lexmap.format_ts(top[0].start_s)}–"
                             f"{lexmap.format_ts(top[0].end_s)} first for {m.pc.code} "
                             f"(relevance {top[0].score:.2f}; {agree})")
        return Outcome("done", "demo", " · ".join(parts), "demo", "seeded fixture + lexical baseline", output)
    if not any(t.transcript.strip() or t.tags or t.description or t.ocr for t in texts):
        return Outcome("done", "real", "0 links: no transcript, tags, descriptions or OCR text were available to "
                       "match against PC text (enable ASR / an LLM to give the mapper input).",
                       "lexical-baseline", "keyword+PC-text overlap v1", output)
    return Outcome("done", "real", f"{len(created)} potential evidence link(s) proposed by the lexical baseline "
                   f"(min relevance {lexmap.DEFAULT_MIN_SCORE}).", "lexical-baseline", "keyword+PC-text overlap v1",
                   output)
