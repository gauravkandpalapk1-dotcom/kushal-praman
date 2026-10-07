"use client";

import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { AudioLines, Check, Eye, FileSearch, Fingerprint, Film, Link2, Loader2, MinusCircle, ScanText, Sparkles, TriangleAlert } from "lucide-react";
import type { Processing, ProcessingStep } from "@/lib/types";
import { cx } from "../ui";

const ICONS: Record<string, typeof Film> = {
  integrity: Fingerprint,
  probe: FileSearch,
  segmentation: Film,
  speech: AudioLines,
  vision: Eye,
  ocr: ScanText,
  llm: Sparkles,
  mapping: Link2,
};

const FALLBACK_LABELS: Record<string, string> = {
  integrity: "Integrity check (SHA-256)",
  probe: "Media probe",
  segmentation: "Video segmentation",
  speech: "Speech-to-text (Indian languages)",
  vision: "Vision tagging",
  ocr: "OCR / documents",
  llm: "LLM evidence description",
  mapping: "Evidence Mapper → NOS → PC",
};

/**
 * Pipeline progress. Statuses come from the server. The only client-side effect is revealing
 * finished steps one by one (≥ 380 ms apart) so a fast run stays readable on a projector.
 */
export function PipelinePanel({ processing, onRevealed }: { processing: Processing | null; onRevealed?: () => void }) {
  const steps = processing?.steps ?? [];
  const settled = steps.filter((s) => s.status !== "pending" && s.status !== "running").length;
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (shown >= settled) return;
    const id = setTimeout(() => setShown((n) => n + 1), 380);
    return () => clearTimeout(id);
  }, [shown, settled]);

  const finished = processing?.status === "done" || processing?.status === "failed";
  useEffect(() => {
    if (finished && steps.length > 0 && shown >= steps.length) onRevealed?.();
  }, [finished, shown, steps.length, onRevealed]);

  return (
    <ol className="grid gap-1.5">
      {steps.map((s, i) => {
        const visible: ProcessingStep = i < shown ? s : i === shown && processing?.status !== "failed" ? { ...s, status: "running" } : { ...s, status: "pending" };
        return <StepRow key={s.key} step={visible} />;
      })}
    </ol>
  );
}

function StepRow({ step }: { step: ProcessingStep }) {
  const Icon = ICONS[step.key] ?? Sparkles;
  const done = step.status === "done";
  const skipped = step.status === "skipped";
  return (
    <motion.li
      layout
      className={cx(
        "flex items-start gap-3 rounded-lg px-3 py-2 transition-colors",
        step.status === "running" ? "bg-amber-500/10 ring-1 ring-amber-500/40" : "bg-white/[0.03]",
      )}
    >
      <Icon className={cx("mt-0.5 size-4 shrink-0", done ? "text-amber-500" : "text-navy-400")} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className={cx("text-sm font-semibold", step.status === "pending" ? "text-navy-400" : "text-cream-50")}>
            {step.label || FALLBACK_LABELS[step.key] || step.key}
          </span>
          {step.status !== "pending" && step.status !== "running" && step.mode && <ModeChip mode={step.mode} />}
        </div>
        {step.detail && step.status !== "pending" && step.status !== "running" && <div className="text-xs text-navy-300 break-words">{step.detail}</div>}
      </div>
      <span className="mt-0.5">
        {step.status === "running" && <Loader2 className="size-4 animate-spin text-amber-500" />}
        {done && <Check className="size-4 text-ok" strokeWidth={3} />}
        {skipped && <MinusCircle className="size-4 text-navy-400" />}
        {step.status === "failed" && <TriangleAlert className="size-4 text-bad" />}
      </span>
    </motion.li>
  );
}

function ModeChip({ mode }: { mode: string }) {
  if (mode === "real") return <span className="rounded bg-ok/20 px-1.5 py-px text-[0.6rem] font-bold tracking-wider text-[#7fd3ac]">REAL</span>;
  if (mode === "demo") return <span className="rounded border border-dashed border-amber-500/70 px-1.5 py-px text-[0.6rem] font-bold tracking-wider text-amber-300">DEMO ANALYSIS</span>;
  return <span className="rounded bg-white/10 px-1.5 py-px text-[0.6rem] font-bold tracking-wider text-navy-300">UNAVAILABLE</span>;
}
