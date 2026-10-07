"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, CircleSlash, Cpu, Database, Film, HardDrive, Link2, RefreshCw, XCircle } from "lucide-react";
import { AppShell } from "@/components/shell";
import { Badge, Button, Card, ErrorBox, Loading, ModeBadge, PageHeader } from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { istDateTime } from "@/lib/format";
import { useSyncState } from "@/lib/offline/useSync";
import { cryptoAvailable } from "@/lib/offline/crypto";
import type { Health } from "@/lib/types";

export default function StatusPage() {
  const health = useApi<Health>("/health");
  const h = health.data;
  const err = health.error;
  const busy = health.loading;
  const load = health.reload;
  const sync = useSyncState();
  const [sw, setSw] = useState<string>("checking");

  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    navigator.serviceWorker.getRegistration().then((r) => setSw(r?.active ? "active" : "not registered (dev build or first load)"));
  }, []);

  return (
    <AppShell>
      <PageHeader
        eyebrow="System"
        title="Health & status"
        sub="What is running, what is real, what is demo, and what is unavailable on this machine."
        actions={
          <Button variant="outline" onClick={load} loading={busy}>
            <RefreshCw className="size-4" /> Refresh
          </Button>
        }
      />
      {err != null && <ErrorBox error={err} onRetry={load} />}
      {!h && !err && <Loading />}
      {h && (
        <div className="grid gap-5 lg:grid-cols-2">
          <Card className="p-5">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-navy-900">Platform</h2>
              <Badge tone={h.mode === "demo" ? "amber" : "ok"}>{h.mode.toUpperCase()} MODE</Badge>
            </div>
            <ul className="mt-3 grid gap-2 text-sm">
              <Row icon={Database} label={`Database${h.db.engine ? ` · ${h.db.engine}` : ""}`} ok={h.db.ok} />
              <Row icon={HardDrive} label="Evidence storage" ok={h.storage.ok} />
              <Row icon={Film} label={`ffmpeg ${h.ffmpeg.version ?? ""}`} ok={h.ffmpeg.available} />
              <Row icon={Link2} label={`Audit hash chain · ${h.audit_chain.entries} entries`} ok={h.audit_chain.ok} />
            </ul>
            <p className="mt-3 text-xs text-muted">
              Server {h.version} · {istDateTime(h.time)}
            </p>
          </Card>
          <Card className="p-5">
            <h2 className="font-bold text-navy-900">This device</h2>
            <ul className="mt-3 grid gap-2 text-sm">
              <Row icon={Cpu} label={`Network: ${sync.browserOnline ? "online" : "offline"}${sync.simulatedOffline ? " · field simulation ON" : ""}`} ok={sync.online} />
              <Row icon={Cpu} label="WebCrypto (SHA-256, AES-GCM)" ok={cryptoAvailable()} />
              <Row icon={Cpu} label="IndexedDB offline queue" ok={typeof indexedDB !== "undefined"} />
              <Row icon={Cpu} label={`Service worker: ${sw}`} ok={sw === "active"} neutral={sw !== "active"} />
            </ul>
          </Card>
          <Card className="p-5 lg:col-span-2">
            <h2 className="font-bold text-navy-900">AI services</h2>
            <p className="text-sm text-muted">Each adapter reports honestly. Unavailable services are skipped in processing, never simulated, except seeded DEMO ANALYSIS for the known demo recording.</p>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[640px] text-sm">
                <thead className="text-left text-xs text-muted">
                  <tr>
                    <th className="py-2 pr-3 font-semibold">Service</th>
                    <th className="py-2 pr-3 font-semibold">Provider</th>
                    <th className="py-2 pr-3 font-semibold">Mode</th>
                    <th className="py-2 pr-3 font-semibold">Available</th>
                    <th className="py-2 font-semibold">Detail</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-navy-900/6">
                  {h.services.map((s) => (
                    <tr key={s.key}>
                      <td className="py-2 pr-3 font-semibold text-navy-900">{s.name}</td>
                      <td className="py-2 pr-3">{s.provider}</td>
                      <td className="py-2 pr-3"><ModeBadge mode={s.mode} /></td>
                      <td className="py-2 pr-3">{s.available ? <CheckCircle2 className="size-4 text-ok" /> : <CircleSlash className="size-4 text-navy-400" />}</td>
                      <td className="py-2 text-xs text-muted">{s.detail}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </AppShell>
  );
}

function Row({ icon: Icon, label, ok, neutral }: { icon: typeof Cpu; label: string; ok: boolean; neutral?: boolean }) {
  return (
    <li className="flex items-center gap-3 rounded-lg bg-cream-100 px-3 py-2">
      <Icon className="size-4 text-navy-500" />
      <span className="flex-1">{label}</span>
      {ok ? <CheckCircle2 className="size-4 text-ok" /> : neutral ? <CircleSlash className="size-4 text-navy-400" /> : <XCircle className="size-4 text-bad" />}
    </li>
  );
}
