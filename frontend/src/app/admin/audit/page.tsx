"use client";

import { useState } from "react";
import { AppShell } from "@/components/shell";
import { AuditTimeline, ChainVerify } from "@/components/audit";
import { Card, ErrorBox, inputCls, Loading, PageHeader } from "@/components/ui";
import { useRequireRole } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import type { AuditEntry } from "@/lib/types";

const FILTERS = [
  ["", "All entity types"],
  ["evidence", "Evidence"],
  ["assessment", "Assessments"],
  ["mapping", "Mappings"],
  ["user", "Users"],
  ["qualification", "Qualifications"],
];

export default function AuditPage() {
  const user = useRequireRole(["admin"]);
  const [type, setType] = useState("");
  const [q, setQ] = useState("");
  const audit = useApi<AuditEntry[]>(user ? `/audit?limit=500${type ? `&entity_type=${type}` : ""}` : null);
  if (!user) return <Loading />;
  const shown = (audit.data ?? []).filter((e) => !q || `${e.summary} ${e.action} ${e.actor?.name ?? ""} ${e.actor?.code ?? ""}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <AppShell>
      <PageHeader eyebrow="Auditability" title="Audit log" sub="Every important action, in order, hash-chained. Verifying recomputes the whole chain on the server." />
      <div className="grid gap-5 lg:grid-cols-[1fr_2fr]">
        <div className="grid gap-4 content-start">
          <ChainVerify />
          <Card className="grid gap-3 p-4">
            <select className={inputCls} value={type} onChange={(e) => setType(e.target.value)} aria-label="Entity type">
              {FILTERS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
            <input className={inputCls} placeholder="Search summary, action, actor…" value={q} onChange={(e) => setQ(e.target.value)} />
            <p className="text-xs text-muted">{shown.length} entries shown</p>
          </Card>
        </div>
        <Card className="p-5">
          {audit.error != null && <ErrorBox error={audit.error} onRetry={audit.reload} />}
          {audit.loading && !audit.data && <Loading />}
          {audit.data && <AuditTimeline entries={shown} />}
        </Card>
      </div>
    </AppShell>
  );
}
