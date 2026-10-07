"use client";

import { AnimatePresence, motion } from "motion/react";
import { Check, CloudOff, FileText, Film, Image as ImageIcon, Loader2, Lock, Mic, RefreshCw, TriangleAlert, Trash2 } from "lucide-react";
import type { QueueItem } from "@/lib/offline/store";
import type { Evidence, EvidenceKind } from "@/lib/types";
import { bytes, geo, istDateTime, shortHash } from "@/lib/format";
import type { StrKey } from "@/lib/i18n";
import { Badge, Button, cx } from "../ui";

export const KIND_ICON: Record<EvidenceKind, typeof Film> = { video: Film, photo: ImageIcon, audio: Mic, document: FileText };

type T = (k: StrKey) => string;

interface StepView {
  label: string;
  state: "done" | "active" | "waiting" | "bad" | "idle";
  extra?: string;
}

function stepsFor(item: QueueItem, server: Evidence | undefined, online: boolean, t: T): StepView[] {
  const steps: StepView[] = [{ label: t("savedLocally"), state: "done" }];
  if (item.status === "saved") {
    steps.push({ label: online ? t("uploading") : t("waiting"), state: online ? "active" : "waiting" });
    return steps;
  }
  if (item.status === "uploading") {
    steps.push({ label: `${t("uploading")} ${item.progress}%`, state: "active" });
    return steps;
  }
  if (item.status === "failed") {
    steps.push({ label: t("failed"), state: "bad", extra: item.last_error ?? undefined });
    return steps;
  }
  steps.push({ label: t("synced"), state: "done" });
  const integrityOk = server ? server.integrity_ok !== false : !item.last_error;
  steps.push({ label: integrityOk ? t("hashOk") : "Hash mismatch", state: integrityOk ? "done" : "bad" });
  const st = server?.status;
  if (st === "processing") steps.push({ label: t("processing"), state: "active" });
  else if (st === "ready") steps.push({ label: t("ready"), state: "done" });
  else if (st === "failed") steps.push({ label: "Processing failed", state: "bad" });
  else steps.push({ label: t("queuedForAssessor"), state: "idle" });
  return steps;
}

export function QueueCard({
  item,
  server,
  online,
  t,
  onRetry,
  onRemove,
}: {
  item: QueueItem;
  server?: Evidence;
  online: boolean;
  t: T;
  onRetry: () => void;
  onRemove: () => void;
}) {
  const Icon = KIND_ICON[item.kind];
  const label = item.server_label ?? (item.reserved_number ? `Evidence #${item.reserved_number}` : "Evidence (number on sync)");
  const steps = stepsFor(item, server, online, t);
  const isLocalOnly = item.status === "saved" || item.status === "uploading";
  return (
    <motion.li
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cx(
        "rounded-2xl p-4 ring-1 transition-colors",
        isLocalOnly && !online ? "bg-navy-900 text-cream-50 ring-amber-500/40" : "bg-white ring-navy-900/10",
      )}
    >
      <div className="flex items-start gap-3">
        <div className={cx("grid size-11 shrink-0 place-items-center rounded-xl", isLocalOnly && !online ? "bg-amber-500 text-navy-950" : "bg-cream-200 text-navy-800")}>
          <Icon className="size-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-lg font-bold tabular">{label}</span>
            {isLocalOnly && !online && (
              <Badge tone="dark" className="bg-amber-500/15 text-amber-300">
                <CloudOff className="size-3" /> {t("offline").toUpperCase()}
              </Badge>
            )}
            {item.encrypted && (
              <Badge tone="neutral" className={isLocalOnly && !online ? "bg-white/10 text-cream-100" : ""} title="AES-GCM 256, non-extractable device key">
                <Lock className="size-3" /> AES-GCM
              </Badge>
            )}
          </div>
          <div className={cx("mt-0.5 text-xs", isLocalOnly && !online ? "text-navy-300" : "text-muted")}>
            {item.kind} · {bytes(item.size_bytes)} · {istDateTime(item.captured_at)} · {geo(item.latitude, item.longitude)}
            {item.location_source === "demo" ? " (demo site)" : ""}
          </div>
          <div className={cx("mt-0.5 font-mono text-[0.7rem]", isLocalOnly && !online ? "text-navy-400" : "text-navy-400")}>sha256 {shortHash(item.client_sha256, 16)}</div>

          <ol className="mt-3 grid gap-1.5">
            <AnimatePresence initial={false}>
              {steps.map((s) => (
                <motion.li key={s.label} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} className="flex items-center gap-2 text-sm font-semibold">
                  <StepIcon state={s.state} />
                  <span className={cx(s.state === "bad" && "text-bad", s.state === "waiting" && "text-amber-300")}>{s.label}</span>
                  {s.extra && <span className="text-xs font-normal text-bad">· {s.extra}</span>}
                </motion.li>
              ))}
            </AnimatePresence>
          </ol>
          {item.status === "uploading" && (
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-navy-900/10">
              <div className="h-full bg-amber-500 transition-all" style={{ width: `${item.progress}%` }} />
            </div>
          )}
        </div>
        {item.status === "failed" && (
          <div className="flex flex-col gap-1">
            <Button size="sm" variant="outline" onClick={onRetry}>
              <RefreshCw className="size-3.5" /> {t("retry")}
            </Button>
            <button onClick={onRemove} className="text-xs text-muted hover:text-bad inline-flex items-center gap-1 justify-center" aria-label="Remove from device">
              <Trash2 className="size-3" /> Remove
            </button>
          </div>
        )}
      </div>
    </motion.li>
  );
}

function StepIcon({ state }: { state: StepView["state"] }) {
  if (state === "done")
    return (
      <span className="grid size-5 place-items-center rounded-full bg-ok text-white">
        <Check className="size-3.5" strokeWidth={3} />
      </span>
    );
  if (state === "active") return <Loader2 className="size-5 animate-spin text-amber-500" />;
  if (state === "waiting")
    return (
      <span className="grid size-5 place-items-center rounded-full ring-2 ring-amber-400 text-amber-300 text-[0.7rem] animate-pulse">⏳</span>
    );
  if (state === "bad") return <TriangleAlert className="size-5 text-bad" />;
  return <span className="size-5 rounded-full ring-2 ring-navy-300" />;
}
