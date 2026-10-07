"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { Brain, CircleCheck, ClipboardCheck, FileDown, Fingerprint, Link2, Lock, LockOpen, LogIn, RefreshCw, ShieldAlert, ShieldCheck, Upload, Wrench } from "lucide-react";
import { api } from "@/lib/api";
import { istDateTime, istTime, shortHash } from "@/lib/format";
import type { AuditEntry, AuditVerify } from "@/lib/types";
import { Badge, Button, cx } from "./ui";

function iconFor(action: string) {
  if (action.startsWith("auth.")) return { Icon: LogIn, tone: "text-navy-400 bg-cream-200" };
  if (action === "evidence.integrity_failed") return { Icon: ShieldAlert, tone: "text-bad bg-bad-soft" };
  if (action.startsWith("evidence.integrity")) return { Icon: Fingerprint, tone: "text-ok bg-ok-soft" };
  if (action.startsWith("evidence.")) return { Icon: Upload, tone: "text-info bg-info-soft" };
  if (action.startsWith("processing.")) return { Icon: Brain, tone: "text-navy-700 bg-cream-200" };
  if (action === "assessment.initial_locked") return { Icon: Lock, tone: "text-navy-950 bg-amber-500" };
  if (action === "ai.revealed") return { Icon: LockOpen, tone: "text-amber-700 bg-amber-100" };
  if (action.startsWith("mapping.")) return { Icon: Link2, tone: "text-amber-700 bg-amber-100" };
  if (action === "assessment.finalized") return { Icon: CircleCheck, tone: "text-white bg-ok" };
  if (action.startsWith("assessment.")) return { Icon: ClipboardCheck, tone: "text-navy-700 bg-cream-200" };
  if (action.startsWith("record.")) return { Icon: FileDown, tone: "text-navy-700 bg-cream-200" };
  return { Icon: Wrench, tone: "text-navy-500 bg-cream-200" };
}

/** Chronological, hash-linked audit timeline. */
export function AuditTimeline({ entries, highlight }: { entries: AuditEntry[]; highlight?: (e: AuditEntry) => boolean }) {
  const sorted = [...entries].sort((a, b) => a.id - b.id);
  return (
    <ol className="relative">
      <span className="absolute left-[19px] top-2 bottom-2 w-px bg-navy-900/12" aria-hidden />
      {sorted.map((e, i) => {
        const { Icon, tone } = iconFor(e.action);
        const hot = highlight?.(e);
        return (
          <motion.li
            key={e.id}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: Math.min(i * 0.05, 1.2) }}
            className="relative flex gap-3 pb-4"
          >
            <span className={cx("relative z-10 grid size-10 shrink-0 place-items-center rounded-full ring-4 ring-white", tone)}>
              <Icon className="size-4.5" />
            </span>
            <div className={cx("min-w-0 flex-1 rounded-xl px-3 py-2", hot ? "bg-amber-50 ring-1 ring-amber-500/40" : "")}>
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="font-mono text-sm font-bold tabular text-navy-900">{istTime(e.ts)}</span>
                <span className="text-[0.95rem] font-semibold text-navy-900">{e.summary}</span>
              </div>
              <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
                {e.actor?.name && (
                  <span>
                    {e.actor.code ? `${e.actor.code} · ` : ""}
                    {e.actor.name} <span className="capitalize">({e.actor.role ?? "system"})</span>
                  </span>
                )}
                {!e.actor?.name && <span>system</span>}
                <span className="font-mono text-navy-400">{e.action}</span>
                <span className="font-mono text-navy-400" title={`hash ${e.hash}\nprev ${e.prev_hash ?? "genesis"}`}>
                  #{shortHash(e.hash, 8)} ← {e.prev_hash ? shortHash(e.prev_hash, 6) : "genesis"}
                </span>
              </div>
            </div>
          </motion.li>
        );
      })}
    </ol>
  );
}

/** Calls /audit/verify, which recomputes the SHA-256 chain on the server. */
export function ChainVerify({ initial }: { initial?: AuditVerify | null }) {
  const [v, setV] = useState<AuditVerify | null>(initial ?? null);
  const [busy, setBusy] = useState(false);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);
  async function run() {
    setBusy(true);
    try {
      setV(await api.get<AuditVerify>("/audit/verify"));
      setCheckedAt(new Date().toISOString());
    } catch {
      setV(null);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className={cx("flex flex-wrap items-center gap-3 rounded-xl p-3", v ? (v.ok ? "bg-ok-soft" : "bg-bad-soft") : "bg-cream-200")}>
      {v ? (
        v.ok ? (
          <ShieldCheck className="size-6 text-ok" />
        ) : (
          <ShieldAlert className="size-6 text-bad" />
        )
      ) : (
        <Fingerprint className="size-6 text-navy-500" />
      )}
      <div className="min-w-0 flex-1 text-sm">
        {v ? (
          <>
            <div className={cx("font-bold", v.ok ? "text-ok" : "text-bad")}>{v.ok ? "Hash chain intact" : `Chain broken at entry #${v.broken_at}`}</div>
            <div className="text-xs text-muted">
              {v.entries} entries · head <span className="font-mono">{shortHash(v.head_hash, 12)}</span>
              {checkedAt ? ` · verified ${istDateTime(checkedAt)}` : ""}
            </div>
          </>
        ) : (
          <>
            <div className="font-bold text-navy-900">Tamper-evident audit log</div>
            <div className="text-xs text-muted">Each entry stores SHA-256(previous hash + entry). Editing any past entry breaks the chain.</div>
          </>
        )}
      </div>
      <Button size="sm" variant="outline" onClick={run} loading={busy}>
        {!busy && <RefreshCw className="size-3.5" />} Verify chain
      </Button>
    </div>
  );
}

export function ActionBadge({ action }: { action: string }) {
  return <Badge tone="neutral" className="font-mono">{action}</Badge>;
}
