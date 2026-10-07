"use client";

import { FlaskConical } from "lucide-react";
import type { Impact, Metric } from "@/lib/types";
import { Card, DemoBadge } from "./ui";

function fmt(m: Metric, v: number | null) {
  if (v == null) return "—";
  if (m.unit === "%") return `${v.toFixed(v >= 99.95 || v === 0 ? 0 : 1)}%`;
  if (m.unit === "κ") return v.toFixed(2);
  if (m.unit === "min") return `${v.toFixed(1)} min`;
  return `${v}${m.unit ? ` ${m.unit}` : ""}`;
}

/** Headline = pilot data only. Demo-session values are a secondary, labelled line. */
export function MetricCard({ m, index }: { m: Metric; index: number }) {
  const pilotReported = m.pilot.value != null && m.pilot.status !== "insufficient";
  return (
    <Card className="flex flex-col p-5">
      <div className="eyebrow text-amber-700">{String(index + 1).padStart(2, "0")} · Impact metric</div>
      <h3 className="mt-1 font-bold text-navy-900">{m.label}</h3>
      <div className="mt-4 flex-1">
        <div className="eyebrow text-navy-500">Pilot data</div>
        {pilotReported ? (
          <div className="text-4xl font-bold tabular text-navy-900">{fmt(m, m.pilot.value)}</div>
        ) : (
          <div className="mt-1 flex items-center gap-2 rounded-lg bg-navy-900 px-3 py-2 text-sm font-semibold text-amber-300">
            <FlaskConical className="size-4" /> Pilot measurement underway
          </div>
        )}
        <div className="mt-1 text-xs text-muted">
          n = {m.pilot.n}
          {m.pilot.min_n ? ` · reported from n ≥ ${m.pilot.min_n}` : ""}
        </div>
      </div>
      <div className="mt-4 flex items-center justify-between gap-2 rounded-lg border border-dashed border-amber-600/40 bg-amber-50/60 px-3 py-2 text-sm">
        <span className="text-muted">This demo session</span>
        <span className="flex items-center gap-2">
          <b className="tabular text-navy-900">{m.demo.value != null ? fmt(m, m.demo.value) : "—"}</b>
          <span className="text-xs text-muted">n={m.demo.n}</span>
          <DemoBadge kind="data" />
        </span>
      </div>
      {m.definition && <p className="mt-3 text-xs text-muted">{m.definition}</p>}
    </Card>
  );
}

export function ImpactGrid({ impact }: { impact: Impact }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {impact.metrics.map((m, i) => (
        <MetricCard key={m.key} m={m} index={i} />
      ))}
    </div>
  );
}
