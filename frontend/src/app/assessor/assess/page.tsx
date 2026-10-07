"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { motion } from "motion/react";
import { ArrowRight, Check, Download, EyeOff, FileJson, History, Lock, LockOpen, Pencil, Play, Scale, ShieldCheck, UserCheck } from "lucide-react";
import { AppShell } from "@/components/shell";
import { EvidenceHeader, FlowNav } from "@/components/assessor/flow";
import { playSegment, SegmentChip, Timeline } from "@/components/assessor/timeline";
import { Badge, Button, ButtonLink, Card, cx, DemoBadge, ErrorBox, inputCls, Loading } from "@/components/ui";
import { absUrl, api, ApiError, downloadFile } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import { istTime, mmss } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { AISupport, Assessment, RubricLevel, Workspace } from "@/lib/types";

export default function AssessPage() {
  return (
    <Suspense fallback={<Loading />}>
      <Assess />
    </Suspense>
  );
}

function Assess() {
  const user = useRequireRole(["assessor", "admin"]);
  const params = useSearchParams();
  const id = Number(params.get("assessment"));
  const a = useApi<Assessment>(user && id ? `/assessments/${id}` : null);
  const eid = a.data?.evidence.id;
  const ws = useApi<Workspace>(eid ? `/evidence/${eid}/workspace` : null);
  const [ai, setAi] = useState<AISupport | null>(null);
  const [aiError, setAiError] = useState<unknown>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [finalPick, setFinalScore] = useState<number | null>(null);
  const [rationale, setRationale] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [mappingOverride, setMappingStatus] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);

  const as = a.data;
  const locked = !!as && as.status !== "opened";
  const finalized = as?.status === "finalized";

  // Reveal AI support only once the initial score is locked. The server refuses earlier (409).
  useEffect(() => {
    if (!as || !locked || ai) return;
    api
      .get<AISupport>(`/assessments/${as.id}/ai-support`)
      .then(setAi)
      .catch(setAiError);
  }, [as, locked, ai]);

  const finalScore = finalPick ?? as?.final_score ?? as?.initial_score ?? null;
  const mappingStatus = mappingOverride ?? as?.mapping?.status ?? null;

  // Cue the player to the surfaced segment once both the media and the workspace have loaded.
  const segStart = ws.data?.surfaced.find((x) => x.pc_id === as?.pc.id)?.start_s;
  useEffect(() => {
    const v = videoRef.current;
    if (v && segStart != null && duration > 0 && v.currentTime === 0) v.currentTime = segStart;
  }, [segStart, duration]);

  if (!user) return <Loading />;
  if (!id) return <AppShell><ErrorBox error="No assessment selected." /></AppShell>;

  const readOnly = user.role === "admin";
  const surfaced = (ws.data?.surfaced ?? []).filter((s) => s.pc_id === as?.pc.id);
  const seg = surfaced[0];
  const levels: RubricLevel[] = as?.pc.rubric?.levels ?? Array.from({ length: (as?.max_score ?? 4) + 1 }, (_, i) => ({ score: i, descriptor: "", exemplar: null }));
  const max = as?.max_score ?? 4;

  async function lockInitial() {
    if (selected == null || !as) return;
    setBusy("lock");
    setError(null);
    try {
      a.setData(await api.post<Assessment>(`/assessments/${as.id}/initial`, { score: selected, note: note || null }));
    } catch (e) {
      setError(e);
      if (e instanceof ApiError && e.status === 409) a.reload();
    } finally {
      setBusy(null);
    }
  }

  async function submitFinal() {
    if (finalScore == null || !as) return;
    setBusy("final");
    setError(null);
    try {
      a.setData(await api.post<Assessment>(`/assessments/${as.id}/final`, { score: finalScore, rationale: rationale || null }));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  async function confirmMapping(mappingId: number) {
    setBusy("map");
    try {
      await api.post(`/mappings/${mappingId}/confirm`);
      setMappingStatus("confirmed");
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  const changed = as?.initial_score != null && finalScore != null && finalScore !== as.initial_score;
  const finding = ai?.findings[0];

  return (
    <AppShell wide>
      <FlowNav active="assess" evidenceId={eid ?? null} assessmentId={id} />
      {a.error != null && <ErrorBox error={a.error} onRetry={a.reload} />}
      {!as && !a.error && <Loading label="Opening assessment…" />}
      {as && (
        <>
          <EvidenceHeader
            ev={as.evidence}
            qualification={as.qualification}
            right={
              <div className="text-right">
                <div className="eyebrow text-navy-500">Screen 4 · Assessor-first scoring</div>
                <div className="mt-1 text-sm font-semibold text-navy-900">
                  {as.assessor.assessor_code} · {as.assessor.full_name}
                </div>
              </div>
            }
          />

          {as.is_second_assessor && (
            <div className="mb-5 flex items-center gap-3 rounded-xl bg-info-soft px-4 py-3 text-info">
              <EyeOff className="size-5 shrink-0" />
              <p className="text-sm">
                <b>Blind double-scoring.</b> Another assessor has scored this recording. Their score is hidden from you and will be compared
                only after you submit (inter-assessor agreement, weighted κ).
              </p>
            </div>
          )}

          <div className="grid gap-5 xl:grid-cols-[1.25fr_1fr] [&>*]:min-w-0">
            {/* Evidence side */}
            <div className="grid gap-5 content-start">
              <Card className="p-5">
                <div className="flex flex-wrap items-baseline gap-2">
                  <span className="eyebrow text-amber-700">{as.nos.code}</span>
                  <span className="text-sm text-muted">{as.nos.title}</span>
                </div>
                <div className="mt-2 flex items-start gap-3">
                  <span className="rounded-lg bg-amber-500 px-2.5 py-1 text-lg font-bold text-navy-950">{as.pc.code}</span>
                  <p className="text-lg leading-snug text-navy-900">&ldquo;{as.pc.text}&rdquo;</p>
                </div>
                {as.pc.is_verbatim && <p className="mt-2 text-xs text-muted">Verbatim from the NQR Q-File [4]. Max marks {max}.</p>}
              </Card>

              {as.evidence.kind === "video" && (
                <Card dark className="p-5">
                  <video
                    ref={videoRef}
                    src={absUrl(as.evidence.media_url)}
                    controls
                    playsInline
                    preload="metadata"
                    onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
                    onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
                    className="aspect-video w-full rounded-lg bg-black"
                  />
                  <div className="mt-3">
                    <Timeline
                      duration={duration || as.evidence.metadata?.duration_s || 600}
                      segments={ws.data?.segments ?? []}
                      highlights={surfaced.map((s) => ({ start_s: s.start_s, end_s: s.end_s, label: "Surfaced" }))}
                      current={time}
                      onSeek={(t) => {
                        if (videoRef.current) videoRef.current.currentTime = t;
                      }}
                      animateHighlight={false}
                    />
                  </div>
                  {seg && (
                    <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-cream-100">
                      <SegmentChip start={seg.start_s} end={seg.end_s} /> {seg.statement}
                      <Button size="sm" variant="light" className="ml-auto" onClick={() => playSegment(videoRef.current, seg.start_s, seg.end_s)}>
                        <Play className="size-3.5" /> Play segment
                      </Button>
                    </div>
                  )}
                  <p className="mt-3 text-xs text-navy-400">
                    The location of the evidence is shown before scoring. The AI&apos;s confidence and explanation are not.
                  </p>
                </Card>
              )}
            </div>

            {/* Decision side */}
            <div className="grid gap-4 content-start">
              {/* ① Initial score */}
              <Card className={cx("p-5", !locked && "ring-2 ring-amber-500")}>
                <StageTitle n={1} title="Your score · first" done={locked} />
                {!locked ? (
                  readOnly ? (
                    <p className="mt-3 text-sm text-muted">Waiting for the assessor&apos;s initial score.</p>
                  ) : (
                    <>
                      <p className="mt-1 text-sm text-muted">Judge the evidence against the rubric before seeing any AI interpretation.</p>
                      <div className="mt-3 grid gap-1.5" role="radiogroup" aria-label="Initial score">
                        {[...levels].reverse().map((l) => (
                          <button
                            key={l.score}
                            role="radio"
                            aria-checked={selected === l.score}
                            onClick={() => setSelected(l.score)}
                            className={cx(
                              "flex items-start gap-3 rounded-xl p-3 text-left ring-1 transition",
                              selected === l.score ? "bg-navy-900 text-cream-50 ring-navy-900" : "bg-cream-50 ring-navy-900/10 hover:ring-amber-500",
                            )}
                          >
                            <span
                              className={cx(
                                "grid size-10 shrink-0 place-items-center rounded-lg text-lg font-bold tabular",
                                selected === l.score ? "bg-amber-500 text-navy-950" : "bg-white text-navy-900 ring-1 ring-navy-900/10",
                              )}
                            >
                              {l.score}
                            </span>
                            <span className={cx("text-sm leading-snug", selected === l.score ? "text-cream-100" : "text-navy-800")}>{l.descriptor || `Score ${l.score}`}</span>
                          </button>
                        ))}
                      </div>
                      {as.pc.rubric?.status === "draft" && <p className="mt-2 text-[0.7rem] text-amber-700">Rubric v{as.pc.rubric.version} is a draft pending validation with SSC-certified assessors.</p>}
                      <textarea
                        className={cx(inputCls, "mt-3 h-16 py-2 text-sm")}
                        placeholder="Optional note on what you observed"
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                      />
                      <Button size="lg" className="mt-3 w-full" disabled={selected == null} loading={busy === "lock"} onClick={lockInitial}>
                        <Lock className="size-4" /> Lock initial score{selected != null ? ` · ${selected} / ${max}` : ""}
                      </Button>
                      <p className="mt-2 text-center text-xs text-muted">A locked initial score can&apos;t be changed. AI support is revealed only after this.</p>
                    </>
                  )
                ) : (
                  <motion.div initial={{ scale: 0.97, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="mt-3 flex items-center gap-4 rounded-xl bg-navy-900 p-4 text-cream-50">
                    <span className="shrink-0 whitespace-nowrap text-4xl font-bold tabular">
                      {as.initial_score}
                      <span className="text-xl text-navy-300"> / {max}</span>
                    </span>
                    <div className="text-sm">
                      <div className="flex items-center gap-1.5 font-semibold text-amber-300">
                        <Lock className="size-4" /> Locked {istTime(as.initial_locked_at)} IST
                      </div>
                      <div className="text-navy-300">Recorded before AI support was shown{as.initial_note ? ` · “${as.initial_note}”` : ""}</div>
                    </div>
                  </motion.div>
                )}
              </Card>

              {/* ② AI support */}
              <Card dark className={cx("relative overflow-hidden p-5", locked && !finalized && "ring-2 ring-amber-500")}>
                <StageTitle n={2} title="AI support · shown after" done={!!ai} dark />
                <>
                  {!locked ? (
                    <div key="locked" className="mt-3 grid place-items-center gap-2 rounded-xl border border-dashed border-white/15 py-8 text-center">
                      <Lock className="size-8 text-amber-500" />
                      <p className="font-semibold">Locked until your initial score</p>
                      <p className="max-w-xs text-sm text-navy-300">Explanations alone don&apos;t prevent over-reliance on AI, so you score first (Buçinca et al. 2021 [5]).</p>
                    </div>
                  ) : !ai ? (
                    <motion.div key="loading" className="mt-3">
                      {aiError != null ? <ErrorBox error={aiError} /> : <Loading label="Revealing AI support…" />}
                    </motion.div>
                  ) : (
                    <motion.div key="ai" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }} className="mt-3">
                      <div className="flex items-center gap-2">
                        <LockOpen className="size-4 text-amber-500" />
                        <span className="text-sm text-navy-300">Revealed {istTime(as.ai_revealed_at)} IST</span>
                        {ai.mode === "demo" && <DemoBadge className="ml-auto" />}
                      </div>
                      {finding ? (
                        <>
                          <div className="mt-3 flex items-end gap-4">
                            <div>
                              <div className="eyebrow text-navy-300">Evidence signal</div>
                              <div className="text-2xl font-bold capitalize text-cream-50">{finding.signal.replace("_", " ")}</div>
                            </div>
                            <div className="ml-auto text-right">
                              <div className="eyebrow text-navy-300">Mapping confidence</div>
                              <div className="text-3xl font-bold tabular text-amber-500">{finding.confidence != null ? `${Math.round(finding.confidence * 100)}%` : "—"}</div>
                            </div>
                          </div>
                          <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/10">
                            <motion.div initial={{ width: 0 }} animate={{ width: `${(finding.confidence ?? 0) * 100}%` }} transition={{ duration: 0.8, delay: 0.2 }} className="h-full bg-amber-500" />
                          </div>
                          <p className="mt-3 text-[0.95rem] text-cream-50">{finding.statement}</p>
                          {finding.rationale && <p className="mt-2 text-sm text-navy-300">{finding.rationale}</p>}
                          {finding.tags.length > 0 && (
                            <div className="mt-3 flex flex-wrap gap-1.5">
                              {finding.tags.map((t) => (
                                <span key={t} className="rounded-full bg-white/10 px-2.5 py-0.5 text-xs text-cream-100">{t}</span>
                              ))}
                            </div>
                          )}
                          {finding.transcript.length > 0 && (
                            <ul className="mt-3 grid gap-1 rounded-lg bg-white/5 p-3 text-sm">
                              {finding.transcript.slice(0, 3).map((l, i) => (
                                <li key={i}>
                                  <span className="font-mono text-xs text-amber-300">{mmss(l.start_s)}</span> <span className="text-cream-100">{l.translation_en ?? l.text}</span>
                                </li>
                              ))}
                            </ul>
                          )}
                          <div className="mt-4 rounded-xl bg-amber-500/10 p-3 ring-1 ring-amber-500/30">
                            <div className="grid grid-cols-2 gap-3 text-sm">
                              <div>
                                <div className="eyebrow text-navy-300">Your initial score</div>
                                <div className="text-xl font-bold">{as.initial_score} / {max}</div>
                              </div>
                              <div>
                                <div className="eyebrow text-navy-300">AI score</div>
                                <div className="text-xl font-bold text-navy-300">None</div>
                              </div>
                            </div>
                            <p className="mt-2 text-xs text-amber-300">The AI did not score the candidate. It located and described evidence. You decide.</p>
                          </div>
                          {!readOnly && (
                            <div className="mt-3 flex flex-wrap items-center gap-2">
                              <span className="text-xs text-navy-300">Evidence → {as.pc.code} mapping:</span>
                              {mappingStatus === "pending" ? (
                                <>
                                  <Button size="sm" variant="light" loading={busy === "map"} onClick={() => confirmMapping(finding.mapping_id)}>
                                    <Check className="size-3.5" /> Confirm mapping
                                  </Button>
                                  <ButtonLink size="sm" variant="light" href={`/assessor/mapper?evidence=${eid}&mapping=${finding.mapping_id}`}>
                                    <Pencil className="size-3.5" /> Edit / reject in mapper
                                  </ButtonLink>
                                </>
                              ) : (
                                <Badge tone={mappingStatus === "rejected" ? "bad" : "ok"} className="capitalize">{mappingStatus ?? "—"}</Badge>
                              )}
                            </div>
                          )}
                        </>
                      ) : (
                        <p className="mt-3 text-sm text-navy-300">The AI found no segment for this PC. Your judgement stands on the recording.</p>
                      )}
                      <details className="mt-4 text-xs text-navy-400">
                        <summary className="cursor-pointer">Services used &amp; disclaimer</summary>
                        <ul className="mt-2 grid gap-0.5">
                          {ai.services.map((s) => (
                            <li key={s.service}>
                              {s.service}: {s.provider}
                              {s.model ? ` · ${s.model}` : ""} · <span className="uppercase">{s.mode}</span>
                            </li>
                          ))}
                        </ul>
                        <p className="mt-2">{ai.disclaimer}</p>
                      </details>
                    </motion.div>
                  )}
                </>
              </Card>

              {/* ③ Final decision */}
              <Card className={cx("p-5", !locked && "opacity-55")}>
                <StageTitle n={3} title="Final decision · assessor" done={finalized} />
                {finalized ? (
                  <FinalSummary as={as} aiConfidence={finding?.confidence ?? null} aiSignal={finding?.signal ?? null} />
                ) : readOnly ? (
                  <p className="mt-3 text-sm text-muted">Pending the assessor&apos;s final decision.</p>
                ) : (
                  <>
                    <p className="mt-1 text-sm text-muted">Compare, then decide. You may keep or change your initial score.</p>
                    <div className="mt-3 grid grid-cols-5 gap-2">
                      {levels.map((l) => (
                        <button
                          key={l.score}
                          disabled={!locked}
                          onClick={() => setFinalScore(l.score)}
                          aria-pressed={finalScore === l.score}
                          className={cx(
                            "h-14 rounded-xl text-xl font-bold tabular ring-1 transition disabled:cursor-not-allowed",
                            finalScore === l.score ? "bg-navy-900 text-amber-500 ring-navy-900" : "bg-cream-50 text-navy-900 ring-navy-900/10 hover:ring-amber-500",
                          )}
                        >
                          {l.score}
                        </button>
                      ))}
                    </div>
                    {locked && (
                      <>
                        <label className="mt-3 block">
                          <span className={cx("text-sm font-semibold", changed ? "text-bad" : "text-navy-800")}>
                            {changed ? `Explain the difference from your initial ${as.initial_score}/${max} (required)` : "Rationale (optional)"}
                          </span>
                          <textarea
                            className={cx(inputCls, "mt-1 h-20 py-2 text-sm", changed && !rationale && "border-bad")}
                            value={rationale}
                            onChange={(e) => setRationale(e.target.value)}
                            placeholder={changed ? "What in the evidence changed your judgement?" : "e.g. Clean strip, lug crimped and seated; one re-tightening."}
                          />
                        </label>
                        <Button size="lg" variant="dark" className="mt-3 w-full" disabled={finalScore == null || (changed && rationale.trim().length < 3)} loading={busy === "final"} onClick={submitFinal}>
                          <UserCheck className="size-4" /> Submit final decision · {finalScore} / {max}
                        </Button>
                      </>
                    )}
                  </>
                )}
                {error != null && <div className="mt-3"><ErrorBox error={error} /></div>}
              </Card>
            </div>
          </div>
        </>
      )}
    </AppShell>
  );
}

function StageTitle({ n, title, done, dark }: { n: number; title: string; done: boolean; dark?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className={cx("grid size-7 place-items-center rounded-full text-sm font-bold", done ? "bg-ok text-white" : dark ? "bg-amber-500 text-navy-950" : "bg-navy-900 text-amber-500")}>
        {done ? <Check className="size-4" strokeWidth={3} /> : n}
      </span>
      <h2 className={cx("font-bold uppercase tracking-wide text-sm", dark ? "text-cream-50" : "text-navy-900")}>{title}</h2>
    </div>
  );
}

function FinalSummary({ as, aiConfidence, aiSignal }: { as: Assessment; aiConfidence: number | null; aiSignal: string | null }) {
  const [dl, setDl] = useState<string | null>(null);
  const [err, setErr] = useState<unknown>(null);
  async function get(kind: "pdf" | "json") {
    setDl(kind);
    setErr(null);
    try {
      await downloadFile(`/assessments/${as.id}/record.${kind}`, `assessment-record-${as.evidence.display_number}-${as.pc.code}.${kind}`);
    } catch (e) {
      setErr(e);
    } finally {
      setDl(null);
    }
  }
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mt-3">
      <div className="flex flex-wrap items-center gap-2 rounded-xl bg-cream-100 p-3 text-sm font-semibold">
        <span className="rounded-lg bg-white px-2.5 py-1 ring-1 ring-navy-900/10">① {as.initial_score}/{as.max_score}</span>
        <ArrowRight className="size-4 text-amber-600" />
        <span className="rounded-lg bg-navy-900 px-2.5 py-1 text-cream-50">
          ② AI: {aiSignal ?? "—"}
          {aiConfidence != null ? ` · ${Math.round(aiConfidence * 100)}%` : ""}
        </span>
        <ArrowRight className="size-4 text-amber-600" />
        <span className="rounded-lg bg-amber-500 px-2.5 py-1 text-navy-950">③ Final {as.final_score}/{as.max_score}</span>
      </div>
      <div className="mt-3 flex items-start gap-3 rounded-xl bg-ok-soft p-3 text-ok">
        <ShieldCheck className="size-5 shrink-0" />
        <div className="text-sm">
          <b>Decision recorded {istTime(as.finalized_at)} IST by {as.assessor.assessor_code}.</b>{" "}
          {as.score_changed ? `Changed from the initial score: “${as.final_rationale}”` : "Final score matches the locked initial score."}
          <div className="text-ok/80">The AI did not score the candidate. The assessor did.</div>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
        <ButtonLink href={`/trace?assessment=${as.id}`} variant="primary">
          <History className="size-4" /> Audit trail
        </ButtonLink>
        <Button variant="outline" onClick={() => get("pdf")} loading={dl === "pdf"}>
          <Download className="size-4" /> Record PDF
        </Button>
        <Button variant="outline" onClick={() => get("json")} loading={dl === "json"}>
          <FileJson className="size-4" /> Record JSON
        </Button>
      </div>
      {err != null && <div className="mt-2"><ErrorBox error={err} /></div>}
      <p className="mt-3 flex items-center gap-1.5 text-xs text-muted">
        <Scale className="size-3.5" /> Assessment record goes to the Awarding Body. We don&apos;t certify.
      </p>
    </motion.div>
  );
}
