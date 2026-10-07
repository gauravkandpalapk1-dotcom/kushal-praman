"use client";

import { motion } from "motion/react";
import { FlaskConical, Users } from "lucide-react";
import type { Agreement } from "@/lib/types";
import { Badge, cx, DemoBadge } from "./ui";

/** Inter-assessor agreement. κ is shown only once the pre-registered minimum of double-scored decisions exists. */
export function AgreementPanel({ data, compact }: { data: Agreement; compact?: boolean }) {
  const progress = Math.min(1, data.n_pairs / Math.max(1, data.threshold));
  const reported = data.status === "reported" && data.kappa != null;
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <Users className="size-5 text-amber-600" />
        <h3 className="font-bold text-navy-900">Inter-assessor agreement</h3>
        <Badge tone="info">weighted κ · {data.weighting}</Badge>
        {(data.data_source === "demo" || data.data_source === "mixed") && <DemoBadge kind="data" />}
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-[1fr_auto] sm:items-center">
        <div>
          {reported ? (
            <div className="text-5xl font-bold tabular text-navy-900">κ = {data.kappa!.toFixed(2)}</div>
          ) : (
            <div className="flex items-center gap-3 rounded-xl bg-navy-900 px-4 py-3 text-cream-50">
              <FlaskConical className="size-6 text-amber-500" />
              <div>
                <div className="font-bold text-amber-300">Pilot measurement underway</div>
                <div className="text-sm text-navy-300">{data.message}</div>
              </div>
            </div>
          )}
          <div className="mt-3">
            <div className="flex justify-between text-xs text-muted">
              <span>Double-scored decisions</span>
              <span className="tabular font-semibold text-navy-900">
                {data.n_pairs} / {data.threshold}
              </span>
            </div>
            <div className="mt-1 h-2.5 overflow-hidden rounded-full bg-cream-200">
              <motion.div initial={{ width: 0 }} animate={{ width: `${progress * 100}%` }} transition={{ duration: 0.8 }} className="h-full rounded-full bg-amber-500" />
            </div>
          </div>
        </div>
        {reported && (
          <dl className="grid grid-cols-3 gap-3 text-center text-sm sm:grid-cols-1 sm:text-right">
            <div><dt className="text-xs text-muted">Linear κ</dt><dd className="font-bold tabular">{data.kappa_linear?.toFixed(2) ?? "—"}</dd></div>
            <div><dt className="text-xs text-muted">Exact</dt><dd className="font-bold tabular">{data.exact_agreement != null ? `${Math.round(data.exact_agreement * 100)}%` : "—"}</dd></div>
            <div><dt className="text-xs text-muted">Within ±1</dt><dd className="font-bold tabular">{data.adjacent_agreement != null ? `${Math.round(data.adjacent_agreement * 100)}%` : "—"}</dd></div>
          </dl>
        )}
      </div>

      {data.pairs.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted">
                <th className="py-1.5 pr-3 font-semibold">Evidence</th>
                <th className="py-1.5 pr-3 font-semibold">PC</th>
                {!compact && <th className="py-1.5 pr-3 font-semibold">Candidate</th>}
                <th className="py-1.5 pr-3 font-semibold">Assessor A</th>
                <th className="py-1.5 pr-3 font-semibold">Assessor B</th>
                <th className="py-1.5 font-semibold">Δ</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-navy-900/6">
              {data.pairs.map((p, i) => {
                const d = Math.abs(p.score_a - p.score_b);
                return (
                  <tr key={i}>
                    <td className="py-2 pr-3 font-semibold">{p.evidence_label}</td>
                    <td className="py-2 pr-3">{p.pc_code}</td>
                    {!compact && <td className="py-2 pr-3">{p.candidate}</td>}
                    <td className="py-2 pr-3 tabular">{p.assessor_a} · <b>{p.score_a}</b></td>
                    <td className="py-2 pr-3 tabular">{p.assessor_b} · <b>{p.score_b}</b></td>
                    <td className={cx("py-2 font-bold tabular", d === 0 ? "text-ok" : d === 1 ? "text-amber-700" : "text-bad")}>{d}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-3 text-xs text-muted">
        Same recording · same PC · same rubric · neither assessor sees the other&apos;s score before submitting. κ is reported only at n ≥ {data.threshold}; we
        never display an unmeasured value.
      </p>
    </div>
  );
}
