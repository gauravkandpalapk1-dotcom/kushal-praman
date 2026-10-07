"use client";

import Link from "next/link";
import { CloudOff, Lock, MapPin, ShieldCheck } from "lucide-react";
import { geo, istDateTime, mmss } from "@/lib/format";
import type { Evidence } from "@/lib/types";
import { Badge, cx, DemoBadge } from "../ui";

export type FlowStep = "workspace" | "mapper" | "assess" | "trace";

/** Screen 2 → 3 → 4 → 5 navigation for one piece of evidence. */
export function FlowNav({
  active,
  evidenceId,
  assessmentId,
}: {
  active: FlowStep;
  evidenceId: number | null;
  assessmentId?: number | null;
}) {
  const steps: { key: FlowStep; n: number; label: string; href: string | null }[] = [
    { key: "workspace", n: 2, label: "Evidence workspace", href: evidenceId ? `/assessor/workspace?evidence=${evidenceId}` : null },
    { key: "mapper", n: 3, label: "Evidence mapper", href: evidenceId ? `/assessor/mapper?evidence=${evidenceId}` : null },
    { key: "assess", n: 4, label: "Assessor-first scoring", href: assessmentId ? `/assessor/assess?assessment=${assessmentId}` : null },
    { key: "trace", n: 5, label: "Traceability & audit", href: assessmentId ? `/trace?assessment=${assessmentId}` : null },
  ];
  return (
    <nav aria-label="Assessment flow" className="mb-5 flex gap-1 overflow-x-auto rounded-xl bg-navy-900 p-1 text-sm [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {steps.map((s) => {
        const cls = cx(
          "flex items-center gap-2 rounded-lg px-3 py-2 whitespace-nowrap font-semibold transition",
          active === s.key ? "bg-amber-500 text-navy-950" : s.href ? "text-cream-100 hover:bg-white/10" : "text-navy-400 cursor-not-allowed",
        );
        const inner = (
          <>
            <span className={cx("grid size-5 place-items-center rounded-full text-[0.7rem]", active === s.key ? "bg-navy-950 text-amber-500" : "bg-white/10")}>{s.n}</span>
            {s.label}
          </>
        );
        return s.href && active !== s.key ? (
          <Link key={s.key} href={s.href} className={cls}>
            {inner}
          </Link>
        ) : (
          <span key={s.key} className={cls} aria-current={active === s.key ? "step" : undefined}>
            {inner}
          </span>
        );
      })}
    </nav>
  );
}

/** Who/what/where header for a piece of evidence. */
export function EvidenceHeader({ ev, qualification, right }: { ev: Evidence; qualification?: { title: string; nsqf_level: number; nqr_code: string } | null; right?: React.ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        <div className="eyebrow text-amber-700">
          {qualification ? `${qualification.title} · NSQF ${qualification.nsqf_level} · ${qualification.nqr_code}` : "Evidence"}
        </div>
        <h1 className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-2xl font-bold text-navy-900">
          <span className="tabular">{ev.label}</span>
          <span className="text-navy-400 font-normal">·</span>
          <span>{ev.candidate.full_name}</span>
          <span className="text-sm font-medium text-muted">{ev.candidate.candidate_code}</span>
        </h1>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
          <Badge tone="dark">
            {ev.kind.toUpperCase()}
            {ev.metadata?.duration_s ? ` · ${mmss(ev.metadata.duration_s)}` : ""}
          </Badge>
          <Badge tone={ev.integrity_ok === false ? "bad" : "ok"} title={`server ${ev.sha256}`}>
            <ShieldCheck className="size-3" /> {ev.integrity_ok === false ? "Hash mismatch" : "SHA-256 verified"}
          </Badge>
          {ev.offline_captured && (
            <Badge tone="amber">
              <CloudOff className="size-3" /> Captured offline
            </Badge>
          )}
          {ev.encrypted_at_rest && (
            <Badge>
              <Lock className="size-3" /> Encrypted on device
            </Badge>
          )}
          <Badge>
            <MapPin className="size-3" /> {geo(ev.metadata?.latitude, ev.metadata?.longitude)}
          </Badge>
          <span className="text-muted">Captured {istDateTime(ev.captured_at)}</span>
          {ev.is_demo && <DemoBadge kind="media" />}
        </div>
      </div>
      {right}
    </div>
  );
}
