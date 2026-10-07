"use client";

import { AppShell } from "@/components/shell";
import { AgreementPanel } from "@/components/agreement";
import { Card, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { useRequireRole } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import type { Agreement } from "@/lib/types";

export default function AgreementPage() {
  const user = useRequireRole(["admin"]);
  const ag = useApi<Agreement>(user ? "/agreement" : null);
  if (!user) return <Loading />;
  return (
    <AppShell>
      <PageHeader
        eyebrow="Quality check · validation milestone"
        title="Assessor A vs Assessor B"
        sub="Two assessors · same recordings · same PC-level rubric · blind to each other → weighted Cohen's κ. Every double-scored decision feeds the measure."
      />
      {ag.error != null && <ErrorBox error={ag.error} onRetry={ag.reload} />}
      {!ag.data && !ag.error && <Loading />}
      {ag.data && (
        <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
          <Card className="p-5">
            <AgreementPanel data={ag.data} />
          </Card>
          <Card className="p-5 text-sm">
            <h2 className="font-bold text-navy-900">Method</h2>
            <ul className="mt-3 grid gap-2.5 text-navy-800">
              <li>
                <b>Pairing.</b> The first two <i>finalized</i> assessments by different assessors on the same evidence and the same PC; final scores
                are compared.
              </li>
              <li>
                <b>Statistic.</b> Cohen&apos;s κ with quadratic weights over the ordinal 0–{4} rubric scale: κ<sub>w</sub> = 1 − Σw·O / Σw·E, with w
                = (i−j)²/(k−1)². Linear-weighted κ, exact and ±1 agreement are reported alongside.
              </li>
              <li>
                <b>Threshold.</b> κ is withheld until {ag.data.threshold} double-scored decisions exist. Below that, the statistic is too unstable to
                interpret, so the UI says <i>pilot measurement underway</i>.
              </li>
              <li>
                <b>Verification.</b> Our κ implementation is unit-tested against scikit-learn&apos;s <code>cohen_kappa_score</code> (quadratic and
                linear) on random score vectors.
              </li>
              <li>
                <b>Blindness.</b> The API never returns another assessor&apos;s score in an assessment payload; only administrators see pairs.
              </li>
            </ul>
            <p className="mt-4 text-xs text-muted">Motivation: inconsistent application of standards weakens trust in RPL (ILO 2026 [2]); rubric reliability needs to be measured, not assumed [8].</p>
          </Card>
        </div>
      )}
    </AppShell>
  );
}
