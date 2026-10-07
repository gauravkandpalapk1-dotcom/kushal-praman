"use client";

import { ArrowRight, CloudOff, Inbox, RefreshCw } from "lucide-react";
import { AppShell } from "@/components/shell";
import { KIND_ICON } from "@/components/candidate/queue";
import { Badge, Button, ButtonLink, Card, DemoBadge, EmptyState, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { useRequireRole } from "@/lib/auth";
import { istDateTime, mmss } from "@/lib/format";
import { useApi, useInterval } from "@/lib/hooks";
import type { Assessment, Evidence } from "@/lib/types";

const EV_STATUS: Record<Evidence["status"], { label: string; tone: "neutral" | "amber" | "ok" | "bad" }> = {
  received: { label: "New · not processed", tone: "amber" },
  processing: { label: "Processing", tone: "amber" },
  ready: { label: "Evidence surfaced", tone: "ok" },
  failed: { label: "Processing failed", tone: "bad" },
};

const AS_STATUS: Record<Assessment["status"], { label: string; tone: "neutral" | "amber" | "ok" | "info" }> = {
  opened: { label: "Awaiting your initial score", tone: "amber" },
  initial_locked: { label: "Initial locked", tone: "info" },
  ai_revealed: { label: "AI revealed · decide", tone: "info" },
  finalized: { label: "Final decision recorded", tone: "ok" },
};

export default function AssessorHome() {
  const user = useRequireRole(["assessor"]);
  const ev = useApi<Evidence[]>(user ? "/evidence" : null);
  const mine = useApi<Assessment[]>(user ? "/assessments" : null);
  useInterval(() => (ev.reload(), mine.reload()), 8000, !!user);
  if (!user) return <Loading />;

  const assessed = new Map<number, Assessment[]>();
  (mine.data ?? []).forEach((a) => assessed.set(a.evidence.id, [...(assessed.get(a.evidence.id) ?? []), a]));

  return (
    <AppShell>
      <PageHeader
        eyebrow={`Assessor ${user.assessor?.assessor_code ?? ""} · ${user.assessor?.agency?.name ?? ""}`}
        title="Assessment queue"
        sub="Evidence synced from candidates' devices. Open an item to surface the relevant segment, then score each PC: you first, AI second."
        actions={
          <Button variant="outline" onClick={() => (ev.reload(), mine.reload())}>
            <RefreshCw className="size-4" /> Refresh
          </Button>
        }
      />
      <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr] [&>*]:min-w-0">
        <Card className="p-2 sm:p-3">
          <h2 className="px-3 pt-2 font-bold text-navy-900">Evidence</h2>
          {ev.error != null && <div className="p-3"><ErrorBox error={ev.error} onRetry={ev.reload} /></div>}
          {ev.loading && !ev.data && <Loading />}
          {ev.data && ev.data.length === 0 && (
            <EmptyState icon={<Inbox className="size-8" />} title="No evidence synced yet">
              Evidence appears here when a candidate&apos;s device syncs.
            </EmptyState>
          )}
          <ul className="divide-y divide-navy-900/6">
            {ev.data?.map((e) => {
              const Icon = KIND_ICON[e.kind];
              const s = EV_STATUS[e.status];
              const mineHere = assessed.get(e.id) ?? [];
              return (
                <li key={e.id} className="flex flex-wrap items-center gap-3 px-3 py-3.5">
                  <span className="grid size-11 place-items-center rounded-xl bg-navy-900 text-amber-500">
                    <Icon className="size-5" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-bold text-navy-900">{e.label}</span>
                      <span className="text-navy-700">{e.candidate.full_name}</span>
                      {e.is_demo && <DemoBadge kind="media" />}
                    </div>
                    <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-muted">
                      <span>
                        {e.kind}
                        {e.metadata?.duration_s ? ` · ${mmss(e.metadata.duration_s)}` : ""}
                      </span>
                      <span>· synced {istDateTime(e.synced_at)}</span>
                      {e.offline_captured && (
                        <span className="inline-flex items-center gap-1 text-amber-700">
                          <CloudOff className="size-3" /> captured offline
                        </span>
                      )}
                    </div>
                    {mineHere.length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1.5">
                        {mineHere.map((a) => (
                          <Badge key={a.id} tone={AS_STATUS[a.status].tone}>
                            {a.pc.code}: {AS_STATUS[a.status].label}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                  <Badge tone={s.tone}>{s.label}</Badge>
                  <ButtonLink href={`/assessor/workspace?evidence=${e.id}`} size="sm" variant={e.status === "ready" ? "dark" : "primary"}>
                    Open <ArrowRight className="size-4" />
                  </ButtonLink>
                </li>
              );
            })}
          </ul>
        </Card>

        <Card className="p-2 sm:p-3 content-start">
          <h2 className="px-3 pt-2 font-bold text-navy-900">My assessments</h2>
          {mine.data && mine.data.length === 0 && <EmptyState title="None yet">Assessments you open appear here.</EmptyState>}
          <ul className="divide-y divide-navy-900/6">
            {mine.data?.map((a) => (
              <li key={a.id} className="flex items-center gap-3 px-3 py-3">
                <div className="min-w-0 flex-1">
                  <div className="font-semibold text-navy-900">
                    {a.evidence.label} · {a.nos.code} {a.pc.code}
                  </div>
                  <div className="text-xs text-muted">
                    {a.candidate.full_name}
                    {a.initial_score != null ? ` · initial ${a.initial_score}/${a.max_score}` : ""}
                    {a.final_score != null ? ` · final ${a.final_score}/${a.max_score}` : ""}
                  </div>
                </div>
                <ButtonLink href={a.status === "finalized" ? `/trace?assessment=${a.id}` : `/assessor/assess?assessment=${a.id}`} size="sm" variant="outline">
                  {a.status === "finalized" ? "Trace" : "Continue"}
                </ButtonLink>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </AppShell>
  );
}
