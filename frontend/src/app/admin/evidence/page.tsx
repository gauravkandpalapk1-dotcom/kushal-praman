"use client";

import { AppShell } from "@/components/shell";
import { KIND_ICON } from "@/components/candidate/queue";
import { Badge, ButtonLink, Card, DemoBadge, EmptyState, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { useRequireRole } from "@/lib/auth";
import { geo, istDateTime, mmss, shortHash } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Evidence } from "@/lib/types";

export default function AdminEvidence() {
  const user = useRequireRole(["admin"]);
  const ev = useApi<Evidence[]>(user ? "/evidence" : null);
  if (!user) return <Loading />;
  return (
    <AppShell>
      <PageHeader eyebrow="Evidence" title="All evidence" sub="Every item with its integrity status, capture context and AI mapping." />
      {ev.error != null && <ErrorBox error={ev.error} onRetry={ev.reload} />}
      {ev.loading && !ev.data && <Loading />}
      {ev.data && ev.data.length === 0 && (
        <Card>
          <EmptyState title="No evidence yet" />
        </Card>
      )}
      {ev.data && ev.data.length > 0 && (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-sm">
            <thead className="text-left text-xs text-muted">
              <tr>
                {["Evidence", "Candidate", "Captured", "Location", "Integrity", "Status", ""].map((h) => (
                  <th key={h} className="px-4 py-3 font-semibold">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-navy-900/6">
              {ev.data.map((e) => {
                const Icon = KIND_ICON[e.kind];
                return (
                  <tr key={e.id}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2 font-semibold text-navy-900">
                        <Icon className="size-4 text-navy-500" /> {e.label} {e.is_demo && <DemoBadge kind="media" />}
                      </div>
                      <div className="text-xs text-muted">
                        {e.kind}
                        {e.metadata?.duration_s ? ` · ${mmss(e.metadata.duration_s)}` : ""} · {e.offline_captured ? "captured offline" : "captured online"}
                      </div>
                    </td>
                    <td className="px-4 py-3">{e.candidate.full_name}</td>
                    <td className="px-4 py-3 text-xs">{istDateTime(e.captured_at)}</td>
                    <td className="px-4 py-3 text-xs">{geo(e.metadata?.latitude, e.metadata?.longitude)}</td>
                    <td className="px-4 py-3">
                      <Badge tone={e.integrity_ok === false ? "bad" : "ok"}>{e.integrity_ok === false ? "mismatch" : "verified"}</Badge>
                      <div className="mt-0.5 font-mono text-[0.7rem] text-navy-400">{shortHash(e.sha256, 10)}</div>
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone={e.status === "ready" ? "ok" : e.status === "failed" ? "bad" : "amber"}>{e.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <ButtonLink href={`/assessor/workspace?evidence=${e.id}`} size="sm" variant="outline">
                        Workspace
                      </ButtonLink>{" "}
                      <ButtonLink href={`/assessor/mapper?evidence=${e.id}`} size="sm" variant="dark">
                        Mapper
                      </ButtonLink>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}
    </AppShell>
  );
}
