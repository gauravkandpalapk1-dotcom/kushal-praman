"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { motion } from "motion/react";
import { ArrowRight, Download, FileJson, History, Landmark, Lock } from "lucide-react";
import { AppShell } from "@/components/shell";
import { FlowNav } from "@/components/assessor/flow";
import { AgreementPanel } from "@/components/agreement";
import { AuditTimeline, ChainVerify } from "@/components/audit";
import { Badge, Button, ButtonLink, Card, cx, DemoBadge, ErrorBox, KV, Loading } from "@/components/ui";
import { api, downloadFile } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import { istDateTime, range, shortHash } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Agreement, AISupport, Assessment, AuditEntry } from "@/lib/types";

export default function TracePage() {
  return (
    <Suspense fallback={<Loading />}>
      <Trace />
    </Suspense>
  );
}

function Trace() {
  const user = useRequireRole(["assessor", "admin"]);
  const params = useSearchParams();
  const id = Number(params.get("assessment"));
  const a = useApi<Assessment>(user && id ? `/assessments/${id}` : null);
  const audit = useApi<AuditEntry[]>(user && id ? `/assessments/${id}/audit` : null);
  const agreement = useApi<Agreement>(user?.role === "admin" ? "/agreement" : null);
  const [ai, setAi] = useState<AISupport | null>(null);
  const [dl, setDl] = useState<string | null>(null);
  const [err, setErr] = useState<unknown>(null);

  const as = a.data;
  useEffect(() => {
    // Only read AI support once it has already been revealed to the assessor (no side effects here).
    if (as && (as.status === "ai_revealed" || as.status === "finalized")) api.get<AISupport>(`/assessments/${as.id}/ai-support`).then(setAi).catch(() => {});
  }, [as]);

  if (!user) return <Loading />;
  if (!id) return <AppShell><ErrorBox error="No assessment selected." /></AppShell>;

  async function get(kind: "pdf" | "json") {
    if (!as) return;
    setDl(kind);
    setErr(null);
    try {
      await downloadFile(`/assessments/${as.id}/record.${kind}`, `assessment-record-${as.evidence.display_number}-${as.pc.code}.${kind}`);
      audit.reload();
    } catch (e) {
      setErr(e);
    } finally {
      setDl(null);
    }
  }

  const finding = ai?.findings[0];
  const max = as?.max_score ?? 4;

  return (
    <AppShell wide>
      <FlowNav active="trace" evidenceId={as?.evidence.id ?? null} assessmentId={id} />
      {a.error != null && <ErrorBox error={a.error} onRetry={a.reload} />}
      {!as && !a.error && <Loading label="Loading traceability…" />}
      {as && (
        <>
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
            <div>
              <div className="eyebrow text-amber-700">Screen 5 · Traceability, audit &amp; agreement</div>
              <h1 className="mt-1 text-2xl font-bold text-navy-900">
                {as.candidate.full_name} · {as.nos.code} {as.pc.code}
              </h1>
              <p className="text-muted">Every score has its proof: evidence, criterion, decision order and who did what, when.</p>
            </div>
            <Badge tone={as.status === "finalized" ? "ok" : "amber"} className="text-sm capitalize">
              {as.status.replace("_", " ")}
            </Badge>
          </div>

          {/* Full chain, end to end */}
          <Card dark className="overflow-x-auto p-5">
            <div className="flex min-w-max items-stretch gap-2">
              {[
                { k: "Evidence", v: as.evidence.label.replace("Evidence ", ""), sub: finding ? range(finding.start_s, finding.end_s) : as.evidence.kind },
                { k: "NOS", v: as.nos.code, sub: "NQR [4]" },
                { k: "PC", v: as.pc.code, sub: `rubric v${as.pc.rubric?.version ?? "—"}`, accent: true },
                { k: "① Initial", v: as.initial_score != null ? `${as.initial_score}/${max}` : "—", sub: as.initial_locked_at ? `locked ${istDateTime(as.initial_locked_at).split(", ")[1]}` : "pending", light: true },
                { k: "② AI shown after", v: finding ? finding.signal : "—", sub: finding?.confidence != null ? `${Math.round(finding.confidence * 100)}% ${ai?.mode === "demo" ? "· demo" : ""}` : "locked" },
                { k: "③ Final", v: as.final_score != null ? `${as.final_score}/${max}` : "—", sub: as.assessor.assessor_code },
                { k: "Record", v: "Assessment", sub: "audit-ready" },
                { k: "Awarding Body", v: "Certifies", sub: "existing process", dashed: true },
                { k: "DigiLocker NAD", v: "Existing", sub: "not integrated in MVP", dashed: true },
              ].map((n, i, arr) => (
                <div key={n.k} className="flex items-center gap-2">
                  <motion.div
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.08 }}
                    className={cx(
                      "min-w-[7.5rem] rounded-xl px-3 py-2.5",
                      n.accent ? "bg-amber-500 text-navy-950" : n.light ? "bg-cream-50 text-navy-950" : n.dashed ? "border border-dashed border-white/25 text-navy-300" : "bg-navy-800 text-cream-50",
                    )}
                  >
                    <div className={cx("text-[0.6rem] font-bold uppercase tracking-wider", n.accent || n.light ? "text-navy-700" : "text-navy-300")}>{n.k}</div>
                    <div className="font-bold capitalize tabular">{n.v}</div>
                    <div className={cx("text-[0.68rem]", n.accent || n.light ? "text-navy-700" : "text-navy-400")}>{n.sub}</div>
                  </motion.div>
                  {i < arr.length - 1 && <ArrowRight className={cx("size-4 shrink-0", i >= 6 ? "text-navy-500" : "text-amber-500")} />}
                </div>
              ))}
            </div>
          </Card>

          <div className="mt-5 grid gap-5 xl:grid-cols-[1.35fr_1fr]">
            <Card className="p-5">
              <div className="flex flex-wrap items-center gap-2">
                <History className="size-5 text-amber-600" />
                <h2 className="font-bold text-navy-900">Audit trail</h2>
                <span className="text-xs text-muted">times in IST</span>
              </div>
              <div className="mt-3">
                <ChainVerify />
              </div>
              <div className="mt-5">
                {audit.error != null && <ErrorBox error={audit.error} onRetry={audit.reload} />}
                {audit.data && (
                  <AuditTimeline
                    entries={audit.data}
                    highlight={(e) => ["assessment.initial_locked", "ai.revealed", "assessment.finalized", "mapping.confirmed", "mapping.edited", "mapping.rejected"].includes(e.action)}
                  />
                )}
              </div>
            </Card>

            <div className="grid gap-5 content-start">
              <Card className="p-5">
                <h2 className="font-bold text-navy-900">Assessment record</h2>
                <p className="text-sm text-muted">A PC-level record for the Awarding Body. This is not a certificate.</p>
                <dl className="mt-3 divide-y divide-navy-900/5">
                  <KV k="Candidate" v={`${as.candidate.full_name} · ${as.candidate.candidate_code}`} />
                  <KV k="QP" v={`${as.qualification.title} · NSQF ${as.qualification.nsqf_level}`} />
                  <KV k="NQR" v={as.qualification.nqr_code} mono />
                  <KV k="NOS / PC" v={`${as.nos.code} / ${as.pc.code}`} />
                  <KV k="Evidence" v={`${as.evidence.label} · ${shortHash(as.evidence.sha256, 12)}`} />
                  <KV k="AI evidence" v={finding ? <span>{finding.statement} {ai?.mode === "demo" && <DemoBadge />}</span> : "—"} />
                  <KV k="Initial score" v={as.initial_score != null ? <span className="inline-flex items-center gap-1"><Lock className="size-3" />{as.initial_score}/{max} · {istDateTime(as.initial_locked_at)}</span> : "—"} />
                  <KV k="AI revealed" v={istDateTime(as.ai_revealed_at)} />
                  <KV k="Final score" v={as.final_score != null ? `${as.final_score}/${max} · ${istDateTime(as.finalized_at)}` : "—"} />
                  <KV k="Assessor" v={`${as.assessor.assessor_code} · ${as.assessor.full_name}`} />
                </dl>
                <div className="mt-4 grid grid-cols-2 gap-2">
                  <Button onClick={() => get("pdf")} loading={dl === "pdf"} disabled={as.status !== "finalized"}>
                    <Download className="size-4" /> PDF
                  </Button>
                  <Button variant="outline" onClick={() => get("json")} loading={dl === "json"} disabled={as.status !== "finalized"}>
                    <FileJson className="size-4" /> JSON
                  </Button>
                </div>
                {as.status !== "finalized" && <p className="mt-2 text-xs text-muted">Export is available once the final decision is submitted.</p>}
                {err != null && <div className="mt-2"><ErrorBox error={err} /></div>}
                <div className="mt-4 flex items-start gap-2 rounded-lg border border-dashed border-navy-900/20 p-3 text-xs text-muted">
                  <Landmark className="size-4 shrink-0 text-navy-500" />
                  <span>
                    Output path: Assessment record → Awarding Body certifies → existing certification ecosystem (DigiLocker NAD [3]).{" "}
                    <b className="text-navy-800">DigiLocker is an existing ecosystem, not integrated in this MVP.</b>
                  </span>
                </div>
              </Card>

              <Card className="p-5">
                {user.role === "admin" ? (
                  agreement.data ? (
                    <AgreementPanel data={agreement.data} compact />
                  ) : agreement.error != null ? (
                    <ErrorBox error={agreement.error} />
                  ) : (
                    <Loading />
                  )
                ) : (
                  <div>
                    <h3 className="font-bold text-navy-900">Inter-assessor agreement</h3>
                    <p className="mt-1 text-sm text-muted">
                      Double-scored decisions are compared by administrators (weighted Cohen&apos;s κ). Assessors never see each other&apos;s scores.
                    </p>
                    <ButtonLink href="/research" variant="ghost" size="sm" className="mt-2 -ml-2">
                      Why blind double-scoring? <ArrowRight className="size-3.5" />
                    </ButtonLink>
                  </div>
                )}
              </Card>
            </div>
          </div>
        </>
      )}
    </AppShell>
  );
}
