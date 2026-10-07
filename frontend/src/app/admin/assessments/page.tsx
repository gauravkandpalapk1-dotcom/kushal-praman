"use client";

import { AppShell } from "@/components/shell";
import { Badge, ButtonLink, Card, EmptyState, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { useRequireRole } from "@/lib/auth";
import { istDateTime } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Assessment } from "@/lib/types";

export default function AdminAssessments() {
  const user = useRequireRole(["admin"]);
  const list = useApi<Assessment[]>(user ? "/assessments" : null);
  if (!user) return <Loading />;
  return (
    <AppShell>
      <PageHeader
        eyebrow="Assessments"
        title="All PC-level decisions"
        sub="Initial (locked before AI) and final scores side by side. A changed score always carries the assessor's rationale."
      />
      {list.error != null && <ErrorBox error={list.error} onRetry={list.reload} />}
      {list.loading && !list.data && <Loading />}
      {list.data && list.data.length === 0 && (
        <Card>
          <EmptyState title="No assessments yet" />
        </Card>
      )}
      {list.data && list.data.length > 0 && (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-sm">
            <thead className="text-left text-xs text-muted">
              <tr>
                {["Evidence · PC", "Candidate", "Assessor", "Initial", "Final", "Status", "Finalized", ""].map((h) => (
                  <th key={h} className="px-4 py-3 font-semibold">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-navy-900/6">
              {list.data.map((a) => (
                <tr key={a.id}>
                  <td className="px-4 py-3 font-semibold text-navy-900">
                    {a.evidence.label} · {a.nos.code} {a.pc.code}
                  </td>
                  <td className="px-4 py-3">{a.candidate.full_name}</td>
                  <td className="px-4 py-3">{a.assessor.assessor_code}</td>
                  <td className="px-4 py-3 tabular">{a.initial_score != null ? `${a.initial_score}/${a.max_score}` : "—"}</td>
                  <td className="px-4 py-3 tabular font-bold">
                    {a.final_score != null ? `${a.final_score}/${a.max_score}` : "—"}
                    {a.score_changed && <Badge tone="amber" className="ml-2" title={a.final_rationale ?? ""}>changed</Badge>}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={a.status === "finalized" ? "ok" : "amber"}>{a.status.replace("_", " ")}</Badge>
                  </td>
                  <td className="px-4 py-3 text-xs">{istDateTime(a.finalized_at)}</td>
                  <td className="px-4 py-3 text-right">
                    <ButtonLink href={`/trace?assessment=${a.id}`} size="sm" variant="outline">
                      Trace
                    </ButtonLink>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </AppShell>
  );
}
