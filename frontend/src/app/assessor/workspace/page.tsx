"use client";

import { Suspense, useCallback, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, Languages, Play, RotateCcw, ScanSearch, Sparkles } from "lucide-react";
import { AppShell } from "@/components/shell";
import { EvidenceHeader, FlowNav } from "@/components/assessor/flow";
import { PipelinePanel } from "@/components/assessor/pipeline";
import { playSegment, SegmentChip, Timeline } from "@/components/assessor/timeline";
import { Badge, Button, ButtonLink, Card, cx, DemoBadge, ErrorBox, KV, Loading } from "@/components/ui";
import { absUrl, api } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import { bytes, istDateTime, mmss, range, shortHash } from "@/lib/format";
import { useApi, useInterval } from "@/lib/hooks";
import type { Assessment, Processing, QualificationTree, Workspace } from "@/lib/types";

export default function WorkspacePage() {
  return (
    <Suspense fallback={<Loading />}>
      <WorkspaceScreen />
    </Suspense>
  );
}

function WorkspaceScreen() {
  const user = useRequireRole(["assessor", "admin"]);
  const params = useSearchParams();
  const router = useRouter();
  const id = Number(params.get("evidence"));
  const ws = useApi<Workspace>(user && id ? `/evidence/${id}/workspace` : null);
  const proc = useApi<Processing>(user && id ? `/evidence/${id}/processing` : null);
  const qid = ws.data?.evidence.qualification_id;
  const tree = useApi<QualificationTree>(qid ? `/qualifications/${qid}/tree` : null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  // runStarted: this assessor pressed "Find relevant evidence" in this session.
  // animDone: the step-by-step pipeline reveal has finished.
  const [runStarted, setRunStarted] = useState(false);
  const [animDone, setAnimDone] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  const status = proc.data?.status;
  const serverBusy = status === "running" || status === "queued";
  const running = serverBusy || (runStarted && !animDone);
  const revealed = runStarted ? animDone : status === "done";

  useInterval(
    () => {
      api
        .get<Processing>(`/evidence/${id}/processing`)
        .then((p) => proc.setData(p))
        .catch(() => {});
    },
    600,
    running && status !== "done" && status !== "failed",
  );

  const reloadWs = ws.reload;
  const onRevealed = useCallback(() => {
    if (!runStarted) return;
    reloadWs();
    setAnimDone(true);
  }, [runStarted, reloadWs]);

  async function findEvidence(force = false) {
    setError(null);
    setAnimDone(false);
    setRunStarted(true);
    try {
      const p = await api.post<Processing>(`/evidence/${id}/process${force ? "?force=true" : ""}`);
      proc.setData(p);
    } catch (e) {
      setRunStarted(false);
      setError(e);
    }
  }

  async function assess(pcId: number) {
    setBusy(`assess-${pcId}`);
    try {
      const a = await api.post<Assessment>("/assessments", { evidence_id: id, pc_id: pcId });
      router.push(`/assessor/assess?assessment=${a.id}`);
    } catch (e) {
      setError(e);
      setBusy(null);
    }
  }

  if (!user) return <Loading />;
  if (!id) return <AppShell><ErrorBox error="No evidence selected." /></AppShell>;

  const w = ws.data;
  const ev = w?.evidence;
  const surfaced = revealed ? (w?.surfaced ?? []) : [];
  const dur = duration || ev?.metadata?.duration_s || 600;
  const seek = (t: number) => {
    if (videoRef.current) videoRef.current.currentTime = t;
    setTime(t);
  };
  const inSurfaced = (t: number) => surfaced.some((s) => t >= s.start_s && t < s.end_s);
  const showPipeline = runStarted ? !animDone : serverBusy || status === "failed";

  return (
    <AppShell wide>
      <FlowNav active="workspace" evidenceId={id} />
      {ws.error != null && <ErrorBox error={ws.error} onRetry={ws.reload} />}
      {!w && !ws.error && <Loading label="Opening evidence…" />}
      {w && ev && (
        <>
          <EvidenceHeader
            ev={ev}
            qualification={tree.data?.qualification}
            right={
              <div className="text-right text-xs text-muted">
                <div className="eyebrow text-navy-500">Screen 2 · Evidence workspace</div>
                <div className="mt-1">Synced {istDateTime(ev.synced_at)}</div>
              </div>
            }
          />

          <div className="grid gap-5 xl:grid-cols-[1.6fr_1fr] [&>*]:min-w-0">
            <div className="grid gap-5 content-start">
              <Card dark className="overflow-hidden">
                <div className="flex items-center justify-between px-5 pt-4">
                  <div className="eyebrow text-cream-100">
                    Practical demonstration · {mmss(dur)} {ev.kind}
                  </div>
                  <span className="font-mono text-sm text-navy-300 tabular">
                    {mmss(time)} / {mmss(dur)}
                  </span>
                </div>
                <div className="px-5 pt-3">
                  {ev.kind === "video" ? (
                    <video
                      ref={videoRef}
                      src={absUrl(ev.media_url)}
                      controls
                      playsInline
                      preload="metadata"
                      onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
                      onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
                      className={cx("aspect-video w-full rounded-lg bg-black transition-shadow", inSurfaced(time) && "ring-4 ring-amber-500")}
                    />
                  ) : ev.kind === "audio" ? (
                    <audio src={absUrl(ev.media_url)} controls className="w-full" />
                  ) : (
                    <img src={absUrl(ev.media_url)} alt={ev.label} className="max-h-[60vh] w-full rounded-lg object-contain bg-black" />
                  )}
                </div>
                {(ev.kind === "video" || ev.kind === "audio") && (
                  <div className="px-5 pb-5 pt-4">
                    <Timeline
                      duration={dur}
                      segments={w.segments}
                      highlights={surfaced.map((s) => ({ start_s: s.start_s, end_s: s.end_s, label: "AI surfaced" }))}
                      current={time}
                      onSeek={seek}
                    />
                  </div>
                )}

                <div className="border-t border-white/10 bg-navy-950/60 p-5">
                  {!revealed && !showPipeline && (
                    <div className="flex flex-wrap items-center gap-4">
                      <div className="min-w-0 flex-1">
                        <p className="font-semibold text-cream-50">Reviewing {mmss(dur)} of footage against {tree.data?.nos.reduce((n, x) => n + x.pcs.length, 0) ?? "the"} performance criteria?</p>
                        <p className="text-sm text-navy-300">AI segments the recording, transcribes speech and proposes where evidence for each PC is. It does not score.</p>
                      </div>
                      <Button size="lg" onClick={() => findEvidence(false)} className="animate-pulse-ring">
                        <ScanSearch className="size-5" /> Find relevant evidence
                      </Button>
                    </div>
                  )}

                  {showPipeline && (
                    <div>
                      <div className="mb-3 flex items-center gap-2">
                        <Sparkles className="size-4 text-amber-500" />
                        <span className="font-semibold text-cream-50">Evidence intelligence pipeline</span>
                        {proc.data?.mode === "demo" && <span className="ml-auto text-[0.7rem] text-amber-300">Demo media: seeded analysis is labelled</span>}
                      </div>
                      <PipelinePanel processing={proc.data} onRevealed={onRevealed} />
                    </div>
                  )}

                  <AnimatePresence>
                    {revealed && (
                      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="grid gap-3">
                        {surfaced.length === 0 ? (
                          <p className="text-navy-300">No segment was proposed for any PC. Review the recording manually; nothing is lost.</p>
                        ) : (
                          surfaced.map((s, i) => (
                            <motion.div
                              key={s.mapping_id}
                              initial={{ opacity: 0, scale: 0.98 }}
                              animate={{ opacity: 1, scale: 1 }}
                              transition={{ delay: 0.15 * i }}
                              className="rounded-xl bg-navy-800 p-4 ring-1 ring-amber-500/50"
                            >
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="eyebrow text-amber-500">AI found</span>
                                <SegmentChip start={s.start_s} end={s.end_s} className="text-sm" />
                                {s.mode === "demo" && <DemoBadge />}
                                <span className="ml-auto text-xs text-navy-300">
                                  {Math.round(s.end_s - s.start_s)} s of {mmss(dur)} surfaced
                                </span>
                              </div>
                              <div className="mt-3 flex flex-wrap items-center gap-2 text-cream-50">
                                <ChainPill k="Evidence" v={ev.label.replace("Evidence ", "")} />
                                <ArrowRight className="size-4 text-amber-500" />
                                <ChainPill k="NOS" v={s.nos_code} />
                                <ArrowRight className="size-4 text-amber-500" />
                                <ChainPill k="PC" v={s.pc_code} accent />
                              </div>
                              <p className="mt-3 text-sm text-cream-100">{s.statement}</p>
                              <div className="mt-3 flex flex-wrap gap-2">
                                <Button variant="light" size="sm" onClick={() => playSegment(videoRef.current, s.start_s, s.end_s)}>
                                  <Play className="size-3.5" /> Play {range(s.start_s, s.end_s)}
                                </Button>
                                <ButtonLink href={`/assessor/mapper?evidence=${id}&mapping=${s.mapping_id}`} variant="light" size="sm">
                                  Open in Evidence Mapper
                                </ButtonLink>
                                {user.role === "assessor" && (
                                  <Button size="sm" onClick={() => assess(s.pc_id)} loading={busy === `assess-${s.pc_id}`}>
                                    Assess {s.pc_code} <ArrowRight className="size-4" />
                                  </Button>
                                )}
                              </div>
                            </motion.div>
                          ))
                        )}
                        <p className="text-xs text-navy-400">
                          Shown now: <b>where</b> the evidence is. Hidden until your initial score is locked: AI confidence, tags and explanation
                          (assessor-first [5]).
                          {status === "done" && (
                            <button onClick={() => findEvidence(true)} className="ml-2 inline-flex items-center gap-1 text-navy-300 underline-offset-2 hover:underline">
                              <RotateCcw className="size-3" /> Re-run
                            </button>
                          )}
                        </p>
                      </motion.div>
                    )}
                  </AnimatePresence>
                  {error != null && <div className="mt-3"><ErrorBox error={error} /></div>}
                </div>
              </Card>
            </div>

            <div className="grid gap-5 content-start">
              <Card className="p-5">
                <div className="flex items-center gap-2">
                  <Languages className="size-4 text-amber-600" />
                  <h2 className="font-bold text-navy-900">Time-aligned transcript</h2>
                  {w.transcript.some((l) => l.mode === "demo") && <DemoBadge className="ml-auto" />}
                </div>
                {w.transcript.length === 0 ? (
                  <p className="mt-3 text-sm text-muted">
                    {status === "done" ? "No speech transcript: the speech service was unavailable or there was no speech." : "Appears after processing."}
                  </p>
                ) : (
                  <ul className="mt-3 max-h-[24rem] overflow-y-auto pr-1 grid gap-1">
                    {w.transcript.map((l, i) => {
                      const active = time >= l.start_s && time < l.end_s;
                      const hot = inSurfaced(l.start_s);
                      return (
                        <li key={i}>
                          <button
                            onClick={() => seek(l.start_s)}
                            className={cx(
                              "w-full rounded-lg px-3 py-2 text-left transition",
                              active ? "bg-navy-900 text-cream-50" : hot ? "bg-amber-50 ring-1 ring-amber-500/40" : "hover:bg-cream-100",
                            )}
                          >
                            <span className={cx("font-mono text-[0.7rem] tabular", active ? "text-amber-300" : "text-amber-700")}>{mmss(l.start_s)}</span>
                            {l.language && <span className="ml-2 text-[0.65rem] font-bold uppercase text-navy-400">{l.language}</span>}
                            <span className="mt-0.5 block text-[0.95rem] leading-snug">{l.text}</span>
                            {l.translation_en && <span className={cx("block text-xs", active ? "text-navy-300" : "text-muted")}>{l.translation_en}</span>}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </Card>

              <Card className="p-5">
                <h2 className="font-bold text-navy-900">Evidence metadata</h2>
                <dl className="mt-2 divide-y divide-navy-900/5">
                  <KV k="Captured" v={istDateTime(ev.captured_at)} />
                  <KV k="Synced" v={istDateTime(ev.synced_at)} />
                  <KV k="Geotag" v={ev.metadata?.latitude != null ? `${ev.metadata.latitude.toFixed(4)}, ${ev.metadata.longitude?.toFixed(4)}` : "—"} />
                  <KV k="Duration" v={ev.metadata?.duration_s ? mmss(ev.metadata.duration_s) : "—"} />
                  <KV k="Resolution" v={ev.metadata?.width ? `${ev.metadata.width}×${ev.metadata.height}` : "—"} />
                  <KV k="Size" v={bytes(ev.size_bytes)} />
                  <KV k="Server SHA-256" v={shortHash(ev.sha256, 16)} mono />
                  <KV
                    k="Device SHA-256"
                    v={
                      <span className="inline-flex items-center gap-2">
                        {shortHash(ev.client_sha256, 16)}
                        <Badge tone={ev.integrity_ok === false ? "bad" : "ok"}>{ev.integrity_ok === false ? "mismatch" : "match"}</Badge>
                      </span>
                    }
                    mono
                  />
                  <KV k="Scene segments" v={w.segments.length || "—"} />
                </dl>
              </Card>
            </div>
          </div>
        </>
      )}
    </AppShell>
  );
}

function ChainPill({ k, v, accent }: { k: string; v: string; accent?: boolean }) {
  return (
    <span className={cx("rounded-lg px-3 py-1.5", accent ? "bg-amber-500 text-navy-950" : "bg-navy-700")}>
      <span className={cx("mr-1.5 text-[0.62rem] font-bold uppercase tracking-wider", accent ? "text-navy-800" : "text-navy-300")}>{k}</span>
      <span className="font-bold">{v}</span>
    </span>
  );
}
