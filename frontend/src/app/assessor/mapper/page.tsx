"use client";

import { Suspense, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { motion } from "motion/react";
import { ArrowDown, ArrowRight, Check, ClipboardCheck, Film, FileBadge2, Layers, ListChecks, Lock, Pencil, Ruler, UserCheck, X } from "lucide-react";
import { AppShell } from "@/components/shell";
import { EvidenceHeader, FlowNav } from "@/components/assessor/flow";
import { SegmentChip } from "@/components/assessor/timeline";
import { Badge, Button, Card, cx, DemoBadge, EmptyState, ErrorBox, Field, inputCls, KV, Loading } from "@/components/ui";
import { absUrl, api } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import { geo, istDateTime, mmss, range, shortHash } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Assessment, Mapping, PC, QualificationTree, Workspace } from "@/lib/types";

type NodeKey = "segment" | "evidence" | "nos" | "pc" | "rubric" | "assessor";

export default function MapperPage() {
  return (
    <Suspense fallback={<Loading />}>
      <Mapper />
    </Suspense>
  );
}

function Mapper() {
  const user = useRequireRole(["assessor", "admin"]);
  const params = useSearchParams();
  const router = useRouter();
  const id = Number(params.get("evidence"));
  const wantMapping = Number(params.get("mapping")) || null;
  const ws = useApi<Workspace>(user && id ? `/evidence/${id}/workspace` : null);
  const maps = useApi<Mapping[]>(user && id ? `/evidence/${id}/mappings` : null);
  const mine = useApi<Assessment[]>(user?.role === "assessor" ? "/assessments" : null);
  const qid = ws.data?.evidence.qualification_id;
  const tree = useApi<QualificationTree>(qid ? `/qualifications/${qid}/tree` : null);
  const [selectedId, setSelectedId] = useState<number | null>(wantMapping);
  const [node, setNode] = useState<NodeKey>("pc");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [form, setForm] = useState<null | "edit" | "reject">(null);

  const mapping = useMemo(() => {
    const list = maps.data ?? [];
    return list.find((m) => m.id === selectedId) ?? list[0] ?? null;
  }, [maps.data, selectedId]);

  const pcFull: PC | null = useMemo(() => {
    if (!mapping || !tree.data) return null;
    for (const n of tree.data.nos) for (const p of n.pcs) if (p.id === mapping.pc.id) return p;
    return null;
  }, [mapping, tree.data]);
  const nosFull = tree.data?.nos.find((n) => n.id === mapping?.pc.nos.id) ?? null;
  const myAssessment = mine.data?.find((a) => a.evidence.id === id && mapping && a.pc.id === mapping.pc.id) ?? null;

  if (!user) return <Loading />;
  const ev = ws.data?.evidence;
  const lockedForMe = !!mapping?.locked;
  const canDecide = user.role === "assessor" && !lockedForMe;

  async function decide(kind: "confirm" | "reject" | "edit", body: Record<string, unknown> = {}) {
    if (!mapping) return;
    setBusy(kind);
    setError(null);
    try {
      await api.post(`/mappings/${mapping.id}/${kind}`, body);
      setForm(null);
      maps.reload();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  async function scoreFirst() {
    if (!mapping) return;
    setBusy("open");
    try {
      const a = myAssessment ?? (await api.post<Assessment>("/assessments", { evidence_id: id, pc_id: mapping.pc.id }));
      router.push(`/assessor/assess?assessment=${a.id}`);
    } catch (e) {
      setError(e);
      setBusy(null);
    }
  }

  const seg = mapping?.segment;
  const segTranscript = (ws.data?.transcript ?? []).filter((l) => seg && l.start_s >= seg.start_s - 0.5 && l.start_s < seg.end_s);

  return (
    <AppShell wide>
      <FlowNav active="mapper" evidenceId={id} assessmentId={myAssessment?.id} />
      {(ws.error ?? maps.error) != null && <ErrorBox error={ws.error ?? maps.error} onRetry={() => (ws.reload(), maps.reload())} />}
      {!ev && !ws.error && <Loading label="Loading evidence mapper…" />}
      {ev && (
        <>
          <EvidenceHeader
            ev={ev}
            qualification={tree.data?.qualification}
            right={<div className="eyebrow text-navy-500">Screen 3 · Evidence mapper · core innovation</div>}
          />

          {maps.data && maps.data.length === 0 && (
            <Card className="p-2">
              <EmptyState icon={<Layers className="size-8" />} title="No mappings yet">
                Run <b>Find relevant evidence</b> in the workspace first. The mapper proposes Evidence → NOS → PC links from the processed recording.
              </EmptyState>
            </Card>
          )}

          {mapping && (
            <>
              {maps.data && maps.data.length > 1 && (
                <div className="mb-4 flex flex-wrap gap-2">
                  {maps.data.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => setSelectedId(m.id)}
                      className={cx("rounded-lg px-3 py-1.5 text-sm font-semibold ring-1", m.id === mapping.id ? "bg-navy-900 text-cream-50 ring-navy-900" : "bg-white ring-navy-900/10")}
                    >
                      {m.pc.nos.code} · {m.pc.code} {m.segment ? `· ${range(m.segment.start_s, m.segment.end_s)}` : ""}
                    </button>
                  ))}
                </div>
              )}

              {/* The chain */}
              <Card dark className="p-5 sm:p-7">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="eyebrow text-amber-500">Evidence mapper</div>
                    <div className="text-lg font-semibold text-cream-50">Evidence → NOS → Performance Criterion → Rubric → Assessor</div>
                  </div>
                  <div className="text-xs text-navy-300">Click any link in the chain to inspect it</div>
                </div>
                <div className="mt-6 flex flex-col items-stretch gap-2 lg:flex-row lg:items-center">
                  {(
                    [
                      { key: "segment", icon: Film, k: "Video segment", v: seg ? range(seg.start_s, seg.end_s) : "Whole item" },
                      { key: "evidence", icon: FileBadge2, k: "Evidence", v: ev.label.replace("Evidence ", "") },
                      { key: "nos", icon: Layers, k: "NOS", v: mapping.pc.nos.code },
                      { key: "pc", icon: ListChecks, k: "Performance criterion", v: mapping.pc.code, accent: true },
                      { key: "rubric", icon: Ruler, k: "Rubric", v: `${pcFull?.max_marks ?? 4} marks` },
                      {
                        key: "assessor",
                        icon: UserCheck,
                        k: "Assessor",
                        v: myAssessment?.final_score != null ? `Final ${myAssessment.final_score}/${myAssessment.max_score}` : user.assessor?.assessor_code ?? "Decides",
                      },
                    ] as { key: NodeKey; icon: typeof Film; k: string; v: string; accent?: boolean }[]
                  ).map((n, i, arr) => (
                    <div key={n.key} className="contents">
                      <motion.button
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.12 + i * 0.22, duration: 0.35 }}
                        onClick={() => setNode(n.key)}
                        aria-pressed={node === n.key}
                        className={cx(
                          "group relative flex-1 rounded-xl px-4 py-3 text-left transition ring-1",
                          n.accent ? "bg-amber-500 text-navy-950 ring-amber-300" : "bg-navy-800 text-cream-50 ring-white/10 hover:ring-amber-500/60",
                          node === n.key && (n.accent ? "ring-4 ring-cream-50/80" : "ring-2 ring-amber-500"),
                        )}
                      >
                        <div className={cx("flex items-center gap-1.5 text-[0.62rem] font-bold uppercase tracking-wider", n.accent ? "text-navy-800" : "text-navy-300")}>
                          <n.icon className="size-3.5" /> {n.k}
                        </div>
                        <div className={cx("mt-0.5 font-bold tabular", n.accent ? "text-2xl" : "text-lg")}>{n.v}</div>
                      </motion.button>
                      {i < arr.length - 1 && (
                        <motion.span
                          initial={{ opacity: 0, scale: 0.6 }}
                          animate={{ opacity: 1, scale: 1 }}
                          transition={{ delay: 0.3 + i * 0.22 }}
                          className="self-center text-amber-500"
                          aria-hidden
                        >
                          <ArrowRight className="hidden size-5 lg:block" strokeWidth={3} />
                          <ArrowDown className="size-5 lg:hidden" strokeWidth={3} />
                        </motion.span>
                      )}
                    </div>
                  ))}
                </div>
                <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.6 }} className="mt-5 text-[0.95rem] text-cream-100">
                  {mapping.statement}
                </motion.p>
                <p className="mt-1 text-xs text-navy-400">
                  Structure from the official NQR Q-File: {tree.data?.qualification.title} · {tree.data?.qualification.nqr_code} · NSQF {tree.data?.qualification.nsqf_level} [4]
                </p>
              </Card>

              <div className="mt-5 grid gap-5 xl:grid-cols-[1.5fr_1fr]">
                {/* Node detail */}
                <Card className="p-5">
                  {node === "segment" && (
                    <div>
                      <h2 className="font-bold text-navy-900">Video segment</h2>
                      {ev.kind === "video" && seg ? (
                        <video src={`${absUrl(ev.media_url)}#t=${seg.start_s},${seg.end_s}`} controls playsInline preload="metadata" className="mt-3 aspect-video w-full rounded-lg bg-black" />
                      ) : (
                        <p className="mt-2 text-sm text-muted">This evidence item is not a video.</p>
                      )}
                      {seg && (
                        <p className="mt-2 text-sm text-muted">
                          <SegmentChip start={seg.start_s} end={seg.end_s} /> · {Math.round(seg.end_s - seg.start_s)} s anchored by scene detection (segment-level analysis [7]).
                        </p>
                      )}
                    </div>
                  )}
                  {node === "evidence" && (
                    <div>
                      <h2 className="font-bold text-navy-900">{ev.label}</h2>
                      <dl className="mt-2 divide-y divide-navy-900/5">
                        <KV k="Candidate" v={`${ev.candidate.full_name} · ${ev.candidate.candidate_code}`} />
                        <KV k="Type" v={ev.kind} />
                        <KV k="Captured" v={istDateTime(ev.captured_at)} />
                        <KV k="Geotag" v={geo(ev.metadata?.latitude, ev.metadata?.longitude)} />
                        <KV k="SHA-256" v={shortHash(ev.sha256, 20)} mono />
                        <KV k="Integrity" v={ev.integrity_ok === false ? "Mismatch" : "Device and server hashes match"} />
                      </dl>
                      {segTranscript.length > 0 && (
                        <div className="mt-4">
                          <div className="flex items-center gap-2">
                            <h3 className="text-sm font-bold text-navy-800">Speech in this segment</h3>
                            {segTranscript[0].mode === "demo" && <DemoBadge />}
                          </div>
                          <ul className="mt-2 grid gap-1.5">
                            {segTranscript.map((l, i) => (
                              <li key={i} className="rounded-lg bg-cream-100 px-3 py-2 text-sm">
                                <span className="font-mono text-xs text-amber-700">{mmss(l.start_s)}</span> {l.text}
                                {l.translation_en && <span className="block text-xs text-muted">{l.translation_en}</span>}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                  {node === "nos" && (
                    <div>
                      <h2 className="font-bold text-navy-900">
                        {mapping.pc.nos.code} · {mapping.pc.nos.title}
                      </h2>
                      <dl className="mt-2 divide-y divide-navy-900/5">
                        <KV k="Qualification" v={tree.data?.qualification.title} />
                        <KV k="NQR code" v={tree.data?.qualification.nqr_code} mono />
                        <KV k="NOS version" v={nosFull?.version ?? "—"} />
                        <KV k="Mandatory" v={nosFull?.is_mandatory ? "Yes" : "—"} />
                        <KV k="PCs loaded" v={nosFull?.pcs.map((p) => p.code).join(", ") || "—"} />
                      </dl>
                      <p className="mt-3 text-xs text-muted">Hierarchy QP → NOS → PC is taken from the NQR Q-File, not invented [4].</p>
                    </div>
                  )}
                  {node === "pc" && (
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-xl font-bold text-navy-900">
                          {mapping.pc.code} <span className="text-base font-medium text-muted">of {mapping.pc.nos.code}</span>
                        </h2>
                        {pcFull?.is_verbatim && <Badge tone="info">Verbatim · NQR Q-File [4]</Badge>}
                      </div>
                      <blockquote className="mt-3 border-l-4 border-amber-500 bg-cream-100 px-4 py-3 text-lg leading-snug text-navy-900">
                        &ldquo;{mapping.pc.text}&rdquo;
                      </blockquote>
                      {pcFull?.source_note && <p className="mt-2 text-xs text-muted">{pcFull.source_note}</p>}
                    </div>
                  )}
                  {node === "rubric" && (
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="font-bold text-navy-900">Rubric · {mapping.pc.code}</h2>
                        {pcFull?.rubric && (
                          <Badge tone={pcFull.rubric.status === "validated" ? "ok" : "amber"}>
                            v{pcFull.rubric.version} · {pcFull.rubric.status === "validated" ? "validated" : "draft, pending SSC validation"}
                          </Badge>
                        )}
                      </div>
                      <ol className="mt-3 grid gap-1.5">
                        {[...(pcFull?.rubric?.levels ?? [])].reverse().map((l) => (
                          <li key={l.score} className="flex gap-3 rounded-lg bg-cream-100 px-3 py-2">
                            <span className="grid size-7 shrink-0 place-items-center rounded-md bg-navy-900 font-bold text-amber-500">{l.score}</span>
                            <span className="text-sm text-navy-900">{l.descriptor}</span>
                          </li>
                        ))}
                      </ol>
                      <p className="mt-2 text-xs text-muted">PC-level analytic rubric (Jonsson &amp; Svingby 2007 [8]).</p>
                    </div>
                  )}
                  {node === "assessor" && (
                    <div>
                      <h2 className="font-bold text-navy-900">Human assessment</h2>
                      {user.role === "admin" ? (
                        <p className="mt-2 text-sm text-muted">Assessors score this PC in the assessor-first workspace. See Admin → Assessments for decisions.</p>
                      ) : myAssessment ? (
                        <dl className="mt-2 divide-y divide-navy-900/5">
                          <KV k="Assessor" v={`${myAssessment.assessor.assessor_code} · ${myAssessment.assessor.full_name}`} />
                          <KV k="Status" v={myAssessment.status.replace("_", " ")} />
                          <KV k="Initial score" v={myAssessment.initial_score != null ? `${myAssessment.initial_score}/${myAssessment.max_score}` : "—"} />
                          <KV k="Final decision" v={myAssessment.final_score != null ? `${myAssessment.final_score}/${myAssessment.max_score}` : "—"} />
                        </dl>
                      ) : (
                        <p className="mt-2 text-sm text-muted">You have not scored {mapping.pc.code} for this evidence yet.</p>
                      )}
                      {user.role === "assessor" && (
                        <Button className="mt-4" onClick={scoreFirst} loading={busy === "open"}>
                          <ClipboardCheck className="size-4" /> {myAssessment ? "Open assessment" : `Score ${mapping.pc.code}`}
                        </Button>
                      )}
                    </div>
                  )}
                </Card>

                {/* Confidence + decision */}
                <Card className="p-5">
                  <div className="flex items-center justify-between">
                    <h2 className="font-bold text-navy-900">AI mapping</h2>
                    {mapping.mode === "demo" && <DemoBadge />}
                  </div>
                  <div className="mt-4 rounded-xl bg-navy-900 p-4 text-cream-50">
                    <div className="eyebrow text-navy-300">AI mapping confidence</div>
                    {mapping.locked ? (
                      <div className="mt-2 flex items-start gap-3">
                        <span className="grid size-10 place-items-center rounded-lg bg-white/10">
                          <Lock className="size-5 text-amber-500" />
                        </span>
                        <div>
                          <div className="font-semibold">Hidden until you commit</div>
                          <div className="text-sm text-navy-300">{mapping.lock_reason ?? "Revealed after your initial score is locked."}</div>
                        </div>
                      </div>
                    ) : (
                      <div className="mt-1">
                        <span className="text-4xl font-bold tabular text-amber-500">{mapping.confidence != null ? `${Math.round(mapping.confidence * 100)}%` : "—"}</span>
                        <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/10">
                          <motion.div initial={{ width: 0 }} animate={{ width: `${(mapping.confidence ?? 0) * 100}%` }} className="h-full bg-amber-500" />
                        </div>
                        <p className="mt-2 text-[0.7rem] text-navy-400">Uncalibrated relevance score for the evidence-to-PC link. Not a probability, and not a score of the candidate.</p>
                      </div>
                    )}
                  </div>
                  {!mapping.locked && mapping.rationale && <p className="mt-3 text-sm text-navy-800">{mapping.rationale}</p>}
                  {!mapping.locked && mapping.tags && mapping.tags.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {mapping.tags.map((t) => (
                        <Badge key={t}>{t}</Badge>
                      ))}
                    </div>
                  )}

                  <div className="mt-4 flex items-center justify-between rounded-lg bg-cream-100 px-3 py-2 text-sm">
                    <span className="text-muted">Status</span>
                    <MappingStatus m={mapping} />
                  </div>

                  {user.role === "assessor" && (
                    <>
                      <div className="mt-4 grid grid-cols-3 gap-2">
                        <Button variant="dark" disabled={!canDecide} loading={busy === "confirm"} onClick={() => decide("confirm")} title={!canDecide ? "Lock your initial score first" : undefined}>
                          <Check className="size-4" /> Confirm
                        </Button>
                        <Button variant="outline" disabled={!canDecide} onClick={() => setForm(form === "edit" ? null : "edit")}>
                          <Pencil className="size-4" /> Edit
                        </Button>
                        <Button variant="outline" disabled={!canDecide} onClick={() => setForm(form === "reject" ? null : "reject")} className="text-bad">
                          <X className="size-4" /> Reject
                        </Button>
                      </div>
                      {!canDecide && (
                        <Button variant="ghost" className="mt-2 w-full" onClick={scoreFirst} loading={busy === "open"}>
                          <Lock className="size-4" /> Score {mapping.pc.code} first, then decide on this mapping
                        </Button>
                      )}
                    </>
                  )}
                  {user.role === "admin" && <p className="mt-3 text-xs text-muted">Mapping decisions belong to the assessor who scored the PC.</p>}

                  {form && tree.data && (
                    <DecisionForm
                      key={form}
                      kind={form}
                      tree={tree.data}
                      mapping={mapping}
                      busy={busy === form}
                      onCancel={() => setForm(null)}
                      onSubmit={(body) => decide(form, body)}
                    />
                  )}
                  {error != null && <div className="mt-3"><ErrorBox error={error} /></div>}
                </Card>
              </div>
            </>
          )}
        </>
      )}
    </AppShell>
  );
}

function MappingStatus({ m }: { m: Mapping }) {
  const map = {
    pending: { tone: "amber" as const, text: "Pending assessor confirmation" },
    confirmed: { tone: "ok" as const, text: "Confirmed" },
    edited: { tone: "info" as const, text: "Edited by assessor" },
    rejected: { tone: "bad" as const, text: "Rejected" },
  }[m.status];
  return (
    <span className="flex items-center gap-2">
      <Badge tone={map.tone}>{map.text}</Badge>
      {m.decided_by && <span className="text-xs text-muted">{m.decided_by} · {istDateTime(m.decided_at)}</span>}
    </span>
  );
}

function DecisionForm({
  kind,
  tree,
  mapping,
  busy,
  onCancel,
  onSubmit,
}: {
  kind: "edit" | "reject";
  tree: QualificationTree;
  mapping: Mapping;
  busy: boolean;
  onCancel: () => void;
  onSubmit: (body: Record<string, unknown>) => void;
}) {
  const [pcId, setPcId] = useState(String(mapping.pc.id));
  const [start, setStart] = useState(String(mapping.segment?.start_s ?? 0));
  const [end, setEnd] = useState(String(mapping.segment?.end_s ?? 0));
  const [reason, setReason] = useState("");
  return (
    <form
      className="mt-4 grid gap-3 rounded-xl bg-cream-100 p-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (kind === "reject") onSubmit({ reason });
        else onSubmit({ pc_id: Number(pcId), start_s: Number(start), end_s: Number(end), reason });
      }}
    >
      {kind === "edit" && (
        <>
          <Field label="Link to performance criterion">
            <select className={inputCls} value={pcId} onChange={(e) => setPcId(e.target.value)}>
              {tree.nos.flatMap((n) =>
                n.pcs.map((p) => (
                  <option key={p.id} value={p.id}>
                    {n.code} · {p.code}
                  </option>
                )),
              )}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Start (seconds)">
              <input className={inputCls} type="number" min={0} step="0.5" value={start} onChange={(e) => setStart(e.target.value)} />
            </Field>
            <Field label="End (seconds)">
              <input className={inputCls} type="number" min={0} step="0.5" value={end} onChange={(e) => setEnd(e.target.value)} />
            </Field>
          </div>
        </>
      )}
      <Field label={kind === "reject" ? "Why is this not evidence for the PC?" : "Reason for the change"}>
        <textarea className={cx(inputCls, "h-20 py-2")} required minLength={3} value={reason} onChange={(e) => setReason(e.target.value)} />
      </Field>
      <div className="flex gap-2">
        <Button type="submit" variant={kind === "reject" ? "danger" : "dark"} loading={busy}>
          {kind === "reject" ? "Reject mapping" : "Save edited mapping"}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
      <p className="text-xs text-muted">The original AI proposal is preserved in the audit trail.</p>
    </form>
  );
}
