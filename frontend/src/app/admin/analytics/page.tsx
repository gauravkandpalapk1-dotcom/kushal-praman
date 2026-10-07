"use client";

import { Activity } from "lucide-react";
import { AppShell } from "@/components/shell";
import { ImpactGrid } from "@/components/metrics";
import { Card, DemoBadge, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { useRequireRole } from "@/lib/auth";
import { pct } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Impact } from "@/lib/types";

export default function AnalyticsPage() {
  const user = useRequireRole(["admin"]);
  const impact = useApi<Impact>(user ? "/analytics/impact" : null);
  if (!user) return <Loading />;
  return (
    <AppShell>
      <PageHeader
        eyebrow="Impact & analytics"
        title="How we will measure impact"
        sub="The four metrics from our deck, computed live. Pilot data and demo-session data are kept separate; nothing is shown as a result before it is measured."
      />
      {impact.error != null && <ErrorBox error={impact.error} onRetry={impact.reload} />}
      {!impact.data && !impact.error && <Loading />}
      {impact.data && (
        <>
          <ImpactGrid impact={impact.data} />
          <div className="mt-6 grid gap-5 lg:grid-cols-[1fr_1.2fr]">
            <Card className="p-5">
              <div className="flex items-center gap-2">
                <Activity className="size-5 text-amber-600" />
                <h2 className="font-bold text-navy-900">Over-reliance monitor</h2>
              </div>
              <p className="mt-1 text-sm text-muted">{impact.data.ai_influence.note}</p>
              <div className="mt-4 flex items-end gap-3">
                <span className="text-4xl font-bold tabular text-navy-900">{pct(impact.data.ai_influence.post_reveal_change_rate)}</span>
                <span className="pb-1 text-sm text-muted">post-reveal change rate · n = {impact.data.ai_influence.n}</span>
              </div>
              <p className="mt-3 text-xs text-muted">
                Why: if assessors routinely move their score toward the AI after the reveal, the assessor-first design isn&apos;t protecting independent
                judgement (Buçinca et al. 2021 [5]). A near-zero rate with high agreement is the healthy pattern. Interpret only at pilot scale.
              </p>
            </Card>
            <Card className="p-5">
              <h2 className="font-bold text-navy-900">Counts</h2>
              <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
                {Object.entries(impact.data.counts).map(([k, v]) => (
                  <div key={k} className="rounded-xl bg-cream-100 p-3">
                    <dt className="text-xs capitalize text-muted">{k.replace(/_/g, " ")}</dt>
                    <dd className="text-2xl font-bold tabular text-navy-900">{v}</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-3 flex items-center gap-2 text-xs text-muted">
                Records created in demo mode are flagged <DemoBadge kind="data" /> and excluded from pilot figures.
              </p>
            </Card>
          </div>
        </>
      )}
    </AppShell>
  );
}
