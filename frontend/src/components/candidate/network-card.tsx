"use client";

import { CloudOff, RefreshCw, Wifi } from "lucide-react";
import { useSyncState } from "@/lib/offline/useSync";
import { istTime } from "@/lib/format";
import type { StrKey } from "@/lib/i18n";
import { Button, cx } from "../ui";

/** Connectivity + field-simulation switch. The simulation pauses the sync engine only. */
export function NetworkCard({ t, pending }: { t: (k: StrKey) => string; pending: number }) {
  const s = useSyncState();
  return (
    <div
      className={cx(
        "rounded-2xl p-4 ring-1 transition-colors",
        s.online ? "bg-ok-soft ring-ok/20" : "bg-navy-900 text-cream-50 ring-amber-500/40",
      )}
    >
      <div className="flex items-center gap-3">
        <div className={cx("grid size-11 place-items-center rounded-xl", s.online ? "bg-ok text-white" : "bg-amber-500 text-navy-950")}>
          {s.online ? <Wifi className="size-5" /> : <CloudOff className="size-5" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className={cx("text-lg font-bold", s.online ? "text-ok" : "text-amber-300")}>{s.online ? t("online").toUpperCase() : t("offline").toUpperCase()}</div>
          <div className={cx("text-xs", s.online ? "text-ok/80" : "text-navy-300")}>
            {s.online
              ? pending > 0
                ? `${pending} item(s) syncing…`
                : s.lastSyncAt
                  ? `Last sync ${istTime(s.lastSyncAt)} IST`
                  : "Connected"
              : t("noSignal")}
          </div>
        </div>
        {s.online && (
          <Button size="sm" variant="outline" onClick={() => void s.engine.syncAll()} loading={s.syncing}>
            {!s.syncing && <RefreshCw className="size-3.5" />} {t("syncNow")}
          </Button>
        )}
      </div>

      <label className={cx("mt-3 flex cursor-pointer items-center gap-3 rounded-xl p-2.5", s.online ? "bg-white/70" : "bg-white/5")}>
        <span className="relative inline-flex">
          <input
            type="checkbox"
            className="peer sr-only"
            checked={s.simulatedOffline}
            onChange={(e) => s.engine.setSimulatedOffline(e.target.checked)}
          />
          <span className="h-7 w-12 rounded-full bg-navy-300 transition peer-checked:bg-amber-500" />
          <span className="absolute left-1 top-1 size-5 rounded-full bg-white shadow transition peer-checked:translate-x-5" />
        </span>
        <span className="text-sm">
          <span className="font-semibold">{t("fieldSim")}</span>
          <span className={cx("block text-xs", s.online ? "text-muted" : "text-navy-300")}>
            Pauses sync to simulate a worksite with zero signal. Turning off Wi-Fi works too.
          </span>
        </span>
      </label>
      {!s.browserOnline && (
        <p className="mt-2 text-xs text-amber-300">The device itself reports no network. Sync resumes automatically when it returns.</p>
      )}
    </div>
  );
}
