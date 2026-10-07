"use client";

import { useState } from "react";
import { BookOpen, ExternalLink, Landmark, LayoutGrid, Table2 } from "lucide-react";
import { AppShell } from "@/components/shell";
import { Badge, Card, cx, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { useApi } from "@/lib/hooks";
import type { ResearchRef } from "@/lib/types";

const NOT_CLAIMED = [
  ["AI certifies candidates", "The Awarding Body certifies through the existing process."],
  ["AI replaces assessors", "AI locates and describes evidence; the assessor scores and decides."],
  ["Live DigiLocker integration", "DigiLocker NAD is an existing ecosystem, not integrated in this MVP."],
  ["A measured κ or impact numbers", "Pilot measurement underway. Numbers are reported only once measured."],
  ["Calibrated AI confidence", "The mapping score is an uncalibrated relevance score; calibration is part of the pilot."],
  ["Generic CV can judge any trade", "Video skill scoring is proven mainly in narrow domains [6][7]."],
];

export default function ResearchPage() {
  const refs = useApi<ResearchRef[]>("/research");
  const [view, setView] = useState<"cards" | "matrix">("cards");

  return (
    <AppShell>
      <PageHeader
        eyebrow="Research & design basis"
        title="Why it is designed this way"
        sub="Every design decision traces to a numbered source from our SIH deck: policy that defines the workflow, and research that sets the limits of AI."
        actions={
          <div className="inline-flex rounded-lg bg-cream-200 p-0.5 text-sm font-semibold">
            <button onClick={() => setView("cards")} aria-pressed={view === "cards"} className={cx("inline-flex h-9 items-center gap-1.5 rounded-md px-3", view === "cards" ? "bg-white shadow-sm" : "text-navy-600")}>
              <LayoutGrid className="size-4" /> Cards
            </button>
            <button onClick={() => setView("matrix")} aria-pressed={view === "matrix"} className={cx("inline-flex h-9 items-center gap-1.5 rounded-md px-3", view === "matrix" ? "bg-white shadow-sm" : "text-navy-600")}>
              <Table2 className="size-4" /> Decision matrix
            </button>
          </div>
        }
      />
      {refs.error != null && <ErrorBox error={refs.error} onRetry={refs.reload} />}
      {refs.loading && <Loading />}
      {refs.data && view === "cards" && (
        <div className="grid gap-8">
          {(["policy", "research"] as const).map((cat) => (
            <section key={cat}>
              <h2 className="mb-3 flex items-center gap-2 text-lg font-bold text-navy-900">
                {cat === "policy" ? <Landmark className="size-5 text-amber-600" /> : <BookOpen className="size-5 text-amber-600" />}
                {cat === "policy" ? "Policy: the workflow we build on" : "Research: the limits we design within"}
              </h2>
              <div className="grid gap-4 md:grid-cols-2">
                {(refs.data ?? [])
                  .filter((r) => r.category === cat)
                  .map((r) => (
                    <Card key={r.number} className="flex flex-col p-5">
                      <div className="flex items-start gap-3">
                        <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-navy-900 font-bold text-amber-500">{r.number}</span>
                        <div className="min-w-0">
                          <h3 className="font-bold text-navy-900">{r.short}</h3>
                          <p className="text-xs text-muted">{r.citation}</p>
                        </div>
                      </div>
                      <div className="mt-4 grid gap-3 text-sm">
                        <div>
                          <div className="eyebrow text-navy-500">What it says</div>
                          <p className="mt-1 text-navy-800">{r.what_it_says}</p>
                        </div>
                        <div className="rounded-xl bg-amber-50 p-3 ring-1 ring-amber-500/25">
                          <div className="eyebrow text-amber-700">How it shaped the product</div>
                          <p className="mt-1 font-medium text-navy-900">{r.design_decision}</p>
                        </div>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {r.where_in_product.map((w) => (
                          <Badge key={w}>{w}</Badge>
                        ))}
                      </div>
                      {r.url && (
                        <a href={r.url} target="_blank" rel="noreferrer" className="mt-auto pt-4 inline-flex items-center gap-1 text-sm font-semibold text-info hover:underline">
                          {r.doi ? `doi:${r.doi}` : r.url.replace(/^https?:\/\//, "")} <ExternalLink className="size-3.5" />
                        </a>
                      )}
                    </Card>
                  ))}
              </div>
            </section>
          ))}
        </div>
      )}
      {refs.data && view === "matrix" && (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="bg-navy-900 text-left text-cream-50">
              <tr>
                <th className="px-4 py-3 font-semibold">#</th>
                <th className="px-4 py-3 font-semibold">Source</th>
                <th className="px-4 py-3 font-semibold">Design decision</th>
                <th className="px-4 py-3 font-semibold">Where in the product</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-navy-900/6">
              {refs.data.map((r) => (
                <tr key={r.number} className="align-top">
                  <td className="px-4 py-3 font-bold text-amber-700">[{r.number}]</td>
                  <td className="px-4 py-3 font-semibold text-navy-900">{r.short}</td>
                  <td className="px-4 py-3 text-navy-800">{r.design_decision}</td>
                  <td className="px-4 py-3 text-muted">{r.where_in_product.join(" · ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <Card dark className="mt-10 p-6">
        <div className="eyebrow text-amber-500">Honesty is a feature</div>
        <h2 className="mt-1 text-xl font-bold">What we deliberately do not claim</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {NOT_CLAIMED.map(([t, d]) => (
            <div key={t} className="rounded-xl bg-white/5 p-4 ring-1 ring-white/10">
              <div className="font-semibold text-cream-50">
                <span className="mr-1.5 text-bad">✕</span>
                {t}
              </div>
              <p className="mt-1 text-sm text-navy-300">{d}</p>
            </div>
          ))}
        </div>
      </Card>
    </AppShell>
  );
}
