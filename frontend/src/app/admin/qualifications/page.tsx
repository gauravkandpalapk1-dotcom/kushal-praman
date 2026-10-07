"use client";

import { useState } from "react";
import { Plus, Ruler } from "lucide-react";
import { AppShell } from "@/components/shell";
import { Badge, Button, Card, cx, ErrorBox, Field, inputCls, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import type { PC, Qualification, QualificationTree } from "@/lib/types";

type Panel = null | { kind: "qp" } | { kind: "nos" } | { kind: "pc"; nosId: number } | { kind: "rubric"; pc: PC };

export default function AdminQualifications() {
  const user = useRequireRole(["admin"]);
  const quals = useApi<Qualification[]>(user ? "/qualifications" : null);
  const [picked, setQid] = useState<number | null>(null);
  const qid = picked ?? quals.data?.[0]?.id ?? null;
  const tree = useApi<QualificationTree>(qid ? `/qualifications/${qid}/tree` : null);
  const [panel, setPanel] = useState<Panel>(null);

  if (!user) return <Loading />;
  const done = () => {
    setPanel(null);
    quals.reload();
    tree.reload();
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow="Standards"
        title="Qualifications · QP → NOS → PC"
        sub="Mirror the official NQR Q-File. Enter PC wording verbatim; rubrics are versioned and stay 'draft' until validated."
        actions={
          <Button variant="dark" onClick={() => setPanel({ kind: "qp" })}>
            <Plus className="size-4" /> Add qualification
          </Button>
        }
      />
      <div className="grid gap-5 lg:grid-cols-[1fr_2.2fr]">
        <Card className="p-2 content-start">
          {quals.data?.map((q) => (
            <button key={q.id} onClick={() => setQid(q.id)} className={cx("w-full rounded-xl p-3 text-left", q.id === qid ? "bg-navy-900 text-cream-50" : "hover:bg-cream-100")}>
              <div className="font-semibold">{q.title}</div>
              <div className={cx("text-xs", q.id === qid ? "text-navy-300" : "text-muted")}>
                {q.nqr_code} · NSQF {q.nsqf_level} · {q.nos_count ?? 0} NOS · {q.pc_count ?? 0} PC
              </div>
            </button>
          ))}
        </Card>
        <div className="grid gap-5 content-start">
          {panel && (
            <Card className="p-5 ring-2 ring-amber-500">
              {panel.kind === "qp" && <QpForm onDone={done} onCancel={() => setPanel(null)} />}
              {panel.kind === "nos" && qid && <NosForm qid={qid} onDone={done} onCancel={() => setPanel(null)} />}
              {panel.kind === "pc" && <PcForm nosId={panel.nosId} onDone={done} onCancel={() => setPanel(null)} />}
              {panel.kind === "rubric" && <RubricForm pc={panel.pc} onDone={done} onCancel={() => setPanel(null)} />}
            </Card>
          )}
          {tree.data && (
            <Card className="p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-bold text-navy-900">{tree.data.qualification.title}</h2>
                  <div className="mt-1 flex flex-wrap gap-2">
                    <Badge tone="info">{tree.data.qualification.nqr_code}</Badge>
                    <Badge>NSQF {tree.data.qualification.nsqf_level}</Badge>
                    <Badge>{tree.data.qualification.sector_skill_council}</Badge>
                    <Badge tone="amber">Mode: {tree.data.qualification.assessment_mode}</Badge>
                  </div>
                </div>
                <Button size="sm" variant="outline" onClick={() => setPanel({ kind: "nos" })}>
                  <Plus className="size-4" /> NOS
                </Button>
              </div>
              <ul className="mt-5 grid gap-3">
                {tree.data.nos.map((n) => (
                  <li key={n.id} className="rounded-xl ring-1 ring-navy-900/10">
                    <div className="flex flex-wrap items-center gap-3 border-b border-navy-900/6 px-4 py-3">
                      <span className="font-mono text-sm font-bold text-navy-700">{n.code}</span>
                      <span className="flex-1 font-semibold text-navy-900">{n.title}</span>
                      <span className="text-xs text-muted">v{n.version}</span>
                      <Button size="sm" variant="ghost" onClick={() => setPanel({ kind: "pc", nosId: n.id })}>
                        <Plus className="size-4" /> PC
                      </Button>
                    </div>
                    {n.pcs.length === 0 ? (
                      <p className="px-4 py-3 text-sm text-muted">No PCs loaded. Add them verbatim from the Q-File.</p>
                    ) : (
                      n.pcs.map((p) => (
                        <div key={p.id} className="flex flex-wrap items-start gap-3 px-4 py-3">
                          <span className="rounded-md bg-amber-500 px-2 py-0.5 text-sm font-bold text-navy-950">{p.code}</span>
                          <div className="min-w-0 flex-1">
                            <p className="text-sm text-navy-900">{p.text}</p>
                            <div className="mt-1 flex flex-wrap gap-1.5">
                              {p.is_verbatim && <Badge tone="info">verbatim</Badge>}
                              <Badge>{p.max_marks} marks</Badge>
                              {p.rubric ? (
                                <Badge tone={p.rubric.status === "validated" ? "ok" : "amber"}>
                                  rubric v{p.rubric.version} · {p.rubric.status}
                                </Badge>
                              ) : (
                                <Badge tone="bad">no rubric</Badge>
                              )}
                            </div>
                          </div>
                          <Button size="sm" variant="outline" onClick={() => setPanel({ kind: "rubric", pc: p })}>
                            <Ruler className="size-4" /> Rubric
                          </Button>
                        </div>
                      ))
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      </div>
    </AppShell>
  );
}

function useSubmit(onDone: () => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onDone();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  return { busy, error, run };
}

function Actions({ busy, onCancel, label }: { busy: boolean; onCancel: () => void; label: string }) {
  return (
    <div className="flex gap-2">
      <Button type="submit" loading={busy}>
        {label}
      </Button>
      <Button type="button" variant="ghost" onClick={onCancel}>
        Cancel
      </Button>
    </div>
  );
}

function QpForm({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const s = useSubmit(onDone);
  const [f, setF] = useState({ title: "", nqr_code: "", nsqf_level: "3", sector_skill_council: "", version: "1.0", assessment_mode: "Offline" });
  return (
    <form className="grid gap-3 sm:grid-cols-2" onSubmit={(e) => (e.preventDefault(), s.run(() => api.post("/qualifications", { ...f, nsqf_level: Number(f.nsqf_level) })))}>
      <h3 className="font-bold text-navy-900 sm:col-span-2">New qualification (QP)</h3>
      <Field label="Title"><input className={inputCls} required value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
      <Field label="NQR code"><input className={inputCls} required value={f.nqr_code} onChange={(e) => setF({ ...f, nqr_code: e.target.value })} /></Field>
      <Field label="NSQF level"><input className={inputCls} type="number" min={1} max={10} step="0.5" value={f.nsqf_level} onChange={(e) => setF({ ...f, nsqf_level: e.target.value })} /></Field>
      <Field label="Sector Skill Council"><input className={inputCls} value={f.sector_skill_council} onChange={(e) => setF({ ...f, sector_skill_council: e.target.value })} /></Field>
      <Field label="Version"><input className={inputCls} value={f.version} onChange={(e) => setF({ ...f, version: e.target.value })} /></Field>
      <Field label="Assessment mode"><input className={inputCls} value={f.assessment_mode} onChange={(e) => setF({ ...f, assessment_mode: e.target.value })} /></Field>
      {s.error != null && <div className="sm:col-span-2"><ErrorBox error={s.error} /></div>}
      <div className="sm:col-span-2"><Actions busy={s.busy} onCancel={onCancel} label="Add qualification" /></div>
    </form>
  );
}

function NosForm({ qid, onDone, onCancel }: { qid: number; onDone: () => void; onCancel: () => void }) {
  const s = useSubmit(onDone);
  const [f, setF] = useState({ code: "", title: "", version: "1.0", is_mandatory: true });
  return (
    <form className="grid gap-3 sm:grid-cols-2" onSubmit={(e) => (e.preventDefault(), s.run(() => api.post(`/qualifications/${qid}/nos`, f)))}>
      <h3 className="font-bold text-navy-900 sm:col-span-2">New NOS</h3>
      <Field label="NOS code"><input className={inputCls} required placeholder="ISC/N1003" value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} /></Field>
      <Field label="Version"><input className={inputCls} value={f.version} onChange={(e) => setF({ ...f, version: e.target.value })} /></Field>
      <div className="sm:col-span-2"><Field label="Title"><input className={inputCls} required value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field></div>
      <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" checked={f.is_mandatory} onChange={(e) => setF({ ...f, is_mandatory: e.target.checked })} /> Mandatory</label>
      {s.error != null && <div className="sm:col-span-2"><ErrorBox error={s.error} /></div>}
      <div className="sm:col-span-2"><Actions busy={s.busy} onCancel={onCancel} label="Add NOS" /></div>
    </form>
  );
}

function PcForm({ nosId, onDone, onCancel }: { nosId: number; onDone: () => void; onCancel: () => void }) {
  const s = useSubmit(onDone);
  const [f, setF] = useState({ code: "", text: "", max_marks: "4", is_verbatim: true, source_note: "Verbatim from NQR Q-File" });
  return (
    <form className="grid gap-3" onSubmit={(e) => (e.preventDefault(), s.run(() => api.post(`/nos/${nosId}/pcs`, { ...f, max_marks: Number(f.max_marks) })))}>
      <h3 className="font-bold text-navy-900">New performance criterion</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="PC code"><input className={inputCls} required placeholder="PC11" value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} /></Field>
        <Field label="Max marks"><input className={inputCls} type="number" min={1} max={10} value={f.max_marks} onChange={(e) => setF({ ...f, max_marks: e.target.value })} /></Field>
      </div>
      <Field label="PC text" hint="Paste exactly as written in the Q-File, original spelling included.">
        <textarea className={cx(inputCls, "h-24 py-2")} required value={f.text} onChange={(e) => setF({ ...f, text: e.target.value })} />
      </Field>
      <Field label="Source note"><input className={inputCls} value={f.source_note} onChange={(e) => setF({ ...f, source_note: e.target.value })} /></Field>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.is_verbatim} onChange={(e) => setF({ ...f, is_verbatim: e.target.checked })} /> Verbatim from the official source</label>
      {s.error != null && <ErrorBox error={s.error} />}
      <Actions busy={s.busy} onCancel={onCancel} label="Add PC" />
    </form>
  );
}

function RubricForm({ pc, onDone, onCancel }: { pc: PC; onDone: () => void; onCancel: () => void }) {
  const s = useSubmit(onDone);
  const initial = Array.from({ length: pc.max_marks + 1 }, (_, i) => pc.rubric?.levels.find((l) => l.score === i)?.descriptor ?? "");
  const [levels, setLevels] = useState<string[]>(initial);
  const [status, setStatus] = useState<"draft" | "validated">(pc.rubric?.status ?? "draft");
  return (
    <form
      className="grid gap-3"
      onSubmit={(e) => (
        e.preventDefault(),
        s.run(() => api.put(`/pcs/${pc.id}/rubric`, { status, levels: levels.map((d, score) => ({ score, descriptor: d, exemplar: null })) }))
      )}
    >
      <h3 className="font-bold text-navy-900">
        Rubric for {pc.code} <span className="text-sm font-normal text-muted">(saves as v{(pc.rubric?.version ?? 0) + 1})</span>
      </h3>
      {levels.map((d, i) => (
        <div key={i} className="flex items-start gap-3">
          <span className="mt-2 grid size-8 shrink-0 place-items-center rounded-md bg-navy-900 font-bold text-amber-500">{i}</span>
          <textarea className={cx(inputCls, "h-16 py-2 text-sm")} required value={d} onChange={(e) => setLevels(levels.map((x, j) => (j === i ? e.target.value : x)))} />
        </div>
      ))}
      <Field label="Status">
        <select className={inputCls} value={status} onChange={(e) => setStatus(e.target.value as "draft" | "validated")}>
          <option value="draft">Draft: pending validation</option>
          <option value="validated">Validated with certified assessors</option>
        </select>
      </Field>
      {s.error != null && <ErrorBox error={s.error} />}
      <Actions busy={s.busy} onCancel={onCancel} label="Save new rubric version" />
    </form>
  );
}
