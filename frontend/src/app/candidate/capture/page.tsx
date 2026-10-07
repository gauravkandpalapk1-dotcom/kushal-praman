"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { motion } from "motion/react";
import { Camera, Check, Clock, FileText, Film, Fingerprint, FlaskConical, Loader2, MapPin, Mic, Square, X } from "lucide-react";
import { AppShell } from "@/components/shell";
import { NetworkCard } from "@/components/candidate/network-card";
import { QueueCard } from "@/components/candidate/queue";
import { Badge, Button, Card, cx, DemoBadge, EmptyState, ErrorBox, KV, Loading, PageHeader } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useIsDemo, useRequireRole } from "@/lib/auth";
import { bytes, geo, istDateTime } from "@/lib/format";
import { useApi, useInterval } from "@/lib/hooks";
import { LangToggle, useI18n } from "@/lib/i18n";
import { cryptoAvailable, sha256Hex } from "@/lib/offline/crypto";
import { useQueue } from "@/lib/offline/useSync";
import type { Evidence, EvidenceKind, QualificationTree } from "@/lib/types";

const DEMO_SITE = { latitude: 30.3165, longitude: 78.0322, accuracy_m: null, source: "demo" as const };
const ACCEPT: Record<EvidenceKind, string> = {
  video: "video/mp4,video/webm,video/quicktime",
  photo: "image/jpeg,image/png,image/webp",
  audio: "audio/webm,audio/ogg,audio/mpeg,audio/wav,audio/mp4",
  document: "application/pdf,image/jpeg,image/png",
};

interface Pending {
  blob: Blob;
  filename: string;
  kind: EvidenceKind;
  capturedAt: Date;
  sha: string | null;
  location: { latitude: number; longitude: number; accuracy_m: number | null; source: "device" | "demo" } | null;
  locating: boolean;
  url: string;
  isDemoMedia?: boolean;
}

function getDeviceLocation(timeoutMs: number): Promise<Pending["location"]> {
  return new Promise((resolve) => {
    if (!("geolocation" in navigator)) return resolve(null);
    const timer = setTimeout(() => resolve(null), timeoutMs);
    navigator.geolocation.getCurrentPosition(
      (p) => {
        clearTimeout(timer);
        resolve({ latitude: p.coords.latitude, longitude: p.coords.longitude, accuracy_m: Math.round(p.coords.accuracy), source: "device" });
      },
      () => {
        clearTimeout(timer);
        resolve(null);
      },
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 60000 },
    );
  });
}

/** Strip codec parameters so the server's MIME allow-list sees e.g. "video/webm". */
function normalise(blob: Blob, fallback: string) {
  const base = (blob.type || fallback).split(";")[0];
  return base === blob.type ? blob : new Blob([blob], { type: base });
}

export default function CapturePage() {
  const user = useRequireRole(["candidate"]);
  if (!user) return <Loading />;
  return <Capture userId={user.id} qualificationId={user.candidate?.qualification_id ?? null} language={user.candidate?.preferred_language ?? "hi"} />;
}

function Capture({ userId, qualificationId, language }: { userId: number; qualificationId: number | null; language: string }) {
  const { t, lang, setLang } = useI18n(language);
  const isDemo = useIsDemo();
  const q = useQueue(userId);
  const tree = useApi<QualificationTree>(qualificationId ? `/qualifications/${qualificationId}/tree` : null);
  const [pcHint, setPcHint] = useState<string>("");
  const [pending, setPending] = useState<Pending | null>(null);
  const [recorder, setRecorder] = useState<EvidenceKind | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [server, setServer] = useState<Record<number, Evidence>>({});
  const inputs = useRef<Record<string, HTMLInputElement | null>>({});

  // Reserve evidence numbers while online so offline captures get real numbers.
  useEffect(() => {
    if (q.online) void q.engine.ensureReservations(userId);
  }, [q.online, q.engine, userId]);

  const pollServer = () => {
    if (!q.online || !q.items.some((i) => i.server_evidence_id)) return;
    api
      .get<Evidence[]>("/evidence")
      .then((xs) => setServer(Object.fromEntries(xs.map((e) => [e.id, e]))))
      .catch(() => {});
  };
  useEffect(pollServer, [q.online, q.items.length, q.version]); // eslint-disable-line react-hooks/exhaustive-deps
  useInterval(pollServer, 4000, q.online);

  const allPcs = useMemo(() => tree.data?.nos.flatMap((n) => n.pcs.map((p) => ({ ...p, nos: n.code }))) ?? [], [tree.data]);
  const pendingCount = q.items.filter((i) => i.status === "saved" || i.status === "uploading").length;

  async function stage(blob: Blob, filename: string, kind: EvidenceKind, isDemoMedia = false) {
    setError(null);
    const url = URL.createObjectURL(blob);
    const base: Pending = { blob, filename, kind, capturedAt: new Date(), sha: null, location: null, locating: true, url, isDemoMedia };
    setPending(base);
    const [sha, loc] = await Promise.all([
      cryptoAvailable() ? blob.arrayBuffer().then(sha256Hex) : Promise.resolve(null),
      getDeviceLocation(isDemo ? 3500 : 8000),
    ]);
    setPending((p) => (p && p.url === url ? { ...p, sha, location: loc ?? (isDemo ? DEMO_SITE : null), locating: false } : p));
  }

  function onFile(kind: EvidenceKind) {
    return (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0];
      e.target.value = "";
      if (f) void stage(normalise(f, f.type), f.name, kind);
    };
  }

  async function useDemoRecording() {
    setError(null);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE ?? ""}/api/v1/demo/media/practical`);
      if (!res.ok) throw new ApiError(res.status, null, "Demo recording unavailable on the server");
      const blob = normalise(await res.blob(), "video/mp4");
      await stage(blob, "practical_assistant_electrician.mp4", "video", true);
    } catch (e) {
      setError(e instanceof ApiError && e.status === 0 ? new Error("Load the demo recording while online, then go offline to capture it.") : e);
    }
  }

  async function save() {
    if (!pending) return;
    setSaving(true);
    try {
      await q.engine.capture({
        ownerUserId: userId,
        blob: pending.blob,
        filename: pending.filename,
        kind: pending.kind,
        qualificationId,
        pcHintId: pcHint ? Number(pcHint) : null,
        language,
        location: pending.location,
        capturedAt: pending.capturedAt,
      });
      URL.revokeObjectURL(pending.url);
      setPending(null);
    } catch (e) {
      setError(e);
    } finally {
      setSaving(false);
    }
  }

  const tiles: { kind: EvidenceKind; icon: typeof Film; label: string; record?: boolean; capture?: "environment" | "user" }[] = [
    { kind: "video", icon: Film, label: t("video"), record: true, capture: "environment" },
    { kind: "photo", icon: Camera, label: t("photo"), capture: "environment" },
    { kind: "audio", icon: Mic, label: t("voice"), record: true },
    { kind: "document", icon: FileText, label: t("document") },
  ];

  return (
    <AppShell>
      <PageHeader
        eyebrow="Screen 1 · Candidate evidence capture"
        title={t("capture")}
        sub={t("captureSub")}
        actions={<LangToggle lang={lang} setLang={setLang} />}
      />

      <div className="grid gap-6 lg:grid-cols-[1.35fr_1fr] [&>*]:min-w-0">
        <div className="grid gap-5 content-start">
          {tree.data && (
            <Card className="p-4">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-bold text-navy-900">{tree.data.qualification.title}</span>
                <Badge>NSQF {tree.data.qualification.nsqf_level}</Badge>
                <Badge tone="info">{tree.data.qualification.nqr_code}</Badge>
                <Badge tone="amber" title="Official assessment mode in the NQR Q-File [4]">Assessment mode: {tree.data.qualification.assessment_mode ?? "Offline"}</Badge>
              </div>
              <label className="mt-3 block text-sm">
                <span className="font-semibold text-navy-800">Which task does this show? (optional)</span>
                <select className="mt-1 w-full h-11 rounded-lg border border-navy-900/15 bg-white px-3" value={pcHint} onChange={(e) => setPcHint(e.target.value)}>
                  <option value="">Not sure: let the assessor link it to the right criterion</option>
                  {allPcs.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.nos} · {p.code}: {p.text.slice(0, 90)}
                      {p.text.length > 90 ? "…" : ""}
                    </option>
                  ))}
                </select>
              </label>
            </Card>
          )}

          {!pending && !recorder && (
            <div className="grid grid-cols-2 gap-3">
              {tiles.map((tile) => (
                <div key={tile.kind} className="rounded-2xl bg-white p-4 ring-1 ring-navy-900/10">
                  <div className="flex items-center gap-3">
                    <span className="grid size-12 place-items-center rounded-xl bg-navy-900 text-amber-500">
                      <tile.icon className="size-6" />
                    </span>
                    <span className="text-lg font-bold text-navy-900">{tile.label}</span>
                  </div>
                  <div className="mt-3 grid gap-2">
                    {tile.record && typeof MediaRecorder !== "undefined" && (
                      <Button size="md" onClick={() => setRecorder(tile.kind)}>
                        <span className="size-2.5 rounded-full bg-bad" /> {t("record")}
                      </Button>
                    )}
                    <Button size="md" variant="outline" onClick={() => inputs.current[tile.kind]?.click()}>
                      {t("choose")}
                    </Button>
                    <input
                      ref={(el) => {
                        inputs.current[tile.kind] = el;
                      }}
                      type="file"
                      className="hidden"
                      accept={ACCEPT[tile.kind]}
                      {...(tile.capture ? { capture: tile.capture } : {})}
                      onChange={onFile(tile.kind)}
                    />
                  </div>
                </div>
              ))}
              {isDemo && (
                <button
                  onClick={useDemoRecording}
                  className="col-span-2 flex items-center gap-4 rounded-2xl border-2 border-dashed border-amber-500/60 bg-amber-50 p-4 text-left transition hover:bg-amber-100"
                >
                  <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-amber-500 text-navy-950">
                    <FlaskConical className="size-6" />
                  </span>
                  <span className="min-w-0">
                    <span className="block font-bold text-navy-900">Use practical recording · 10:00 video</span>
                    <span className="block text-sm text-muted">Demo mode: loads the synthetic practical demonstration for Assistant Electrician.</span>
                  </span>
                  <DemoBadge kind="media" className="ml-auto hidden sm:inline-flex" />
                </button>
              )}
            </div>
          )}

          {recorder && !pending && (
            <Recorder
              kind={recorder}
              t={t}
              onCancel={() => setRecorder(null)}
              onDone={(blob) => {
                setRecorder(null);
                const ext = recorder === "video" ? "webm" : "webm";
                void stage(normalise(blob, recorder === "video" ? "video/webm" : "audio/webm"), `${recorder}-${Date.now()}.${ext}`, recorder);
              }}
              onError={(e) => {
                setRecorder(null);
                setError(e);
              }}
            />
          )}

          {pending && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
              <Card className="overflow-hidden">
                <div className="bg-navy-950">
                  {pending.kind === "video" && <video src={pending.url} controls playsInline className="aspect-video w-full" />}
                  {pending.kind === "photo" && <img src={pending.url} alt="Captured evidence" className="max-h-80 w-full object-contain" />}
                  {pending.kind === "audio" && <audio src={pending.url} controls className="w-full p-4" />}
                  {pending.kind === "document" && (
                    <div className="flex items-center gap-3 p-6 text-cream-50">
                      <FileText className="size-8 text-amber-500" /> {pending.filename}
                    </div>
                  )}
                </div>
                <div className="p-4">
                  <div className="flex items-center justify-between gap-2">
                    <h2 className="font-bold text-navy-900">{t("capturedAuto")}</h2>
                    {pending.isDemoMedia && <DemoBadge kind="media" />}
                  </div>
                  <dl className="mt-2 divide-y divide-navy-900/5">
                    <KV k={`${t("time")}`} v={<span className="inline-flex items-center gap-1.5"><Clock className="size-3.5 text-amber-600" />{istDateTime(pending.capturedAt.toISOString())}</span>} />
                    <KV
                      k={t("location")}
                      v={
                        pending.locating ? (
                          <span className="inline-flex items-center gap-1.5 text-muted"><Loader2 className="size-3.5 animate-spin" />Locating…</span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5">
                            <MapPin className="size-3.5 text-amber-600" />
                            {geo(pending.location?.latitude, pending.location?.longitude)}
                            {pending.location?.source === "demo" && <Badge tone="amber">demo site</Badge>}
                          </span>
                        )
                      }
                    />
                    <KV
                      k={t("hash")}
                      mono
                      v={
                        pending.sha ? (
                          <span className="inline-flex items-center gap-1.5"><Fingerprint className="size-3.5 text-amber-600" />{pending.sha.slice(0, 24)}…</span>
                        ) : cryptoAvailable() ? (
                          <Loader2 className="size-3.5 animate-spin" />
                        ) : (
                          "Needs HTTPS / localhost"
                        )
                      }
                    />
                    <KV k="Size" v={`${bytes(pending.blob.size)} · ${pending.blob.type || "unknown type"}`} />
                  </dl>
                  {error != null && <div className="mt-3"><ErrorBox error={error} /></div>}
                  <div className="mt-4 flex gap-2">
                    <Button size="lg" className="flex-1" onClick={save} loading={saving} disabled={pending.locating || (cryptoAvailable() && !pending.sha)}>
                      <Check className="size-5" /> {t("saveDevice")}
                    </Button>
                    <Button size="lg" variant="outline" onClick={() => setPending(null)} aria-label="Discard">
                      <X className="size-5" />
                    </Button>
                  </div>
                  <p className="mt-2 text-xs text-muted">{t("saveNote")}</p>
                </div>
              </Card>
            </motion.div>
          )}
          {error != null && !pending && <ErrorBox error={error} />}
        </div>

        <div className="grid gap-4 content-start">
          <NetworkCard t={t} pending={pendingCount} />
          <div>
            <div className="flex items-baseline justify-between">
              <h2 className="font-bold text-navy-900">{t("queue")}</h2>
              <span className="text-xs text-muted">{t("queueSub")}</span>
            </div>
            {q.items.length === 0 ? (
              <Card className="mt-2">
                <EmptyState title={t("noItems")} />
              </Card>
            ) : (
              <ul className="mt-2 grid gap-3">
                {q.items.slice(0, 8).map((item) => (
                  <QueueCard
                    key={item.local_id}
                    item={item}
                    server={item.server_evidence_id ? server[item.server_evidence_id] : undefined}
                    online={q.online}
                    t={t}
                    onRetry={() => void q.engine.retry(item.local_id)}
                    onRemove={() => void q.engine.remove(item.local_id)}
                  />
                ))}
              </ul>
            )}
            <Link href="/candidate" className="mt-3 inline-block text-sm font-semibold text-navy-700 hover:text-amber-700">
              ← {t("myQualification")}
            </Link>
          </div>
        </div>
      </div>
    </AppShell>
  );
}

function Recorder({
  kind,
  t,
  onDone,
  onCancel,
  onError,
}: {
  kind: EvidenceKind;
  t: (k: "stop") => string;
  onDone: (b: Blob) => void;
  onCancel: () => void;
  onError: (e: unknown) => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const recRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const chunks: Blob[] = [];
    navigator.mediaDevices
      .getUserMedia(kind === "video" ? { video: { facingMode: "environment" }, audio: true } : { audio: true })
      .then((stream) => {
        if (cancelled) return stream.getTracks().forEach((tr) => tr.stop());
        streamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;
        const rec = new MediaRecorder(stream);
        rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
        rec.onstop = () => {
          stream.getTracks().forEach((tr) => tr.stop());
          if (!cancelled) onDone(new Blob(chunks, { type: rec.mimeType }));
        };
        rec.start(1000);
        recRef.current = rec;
      })
      .catch((e) => onError(new Error(`Camera/microphone unavailable: ${e?.message ?? e}. Use "Choose file" instead.`)));
    const timer = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => {
      cancelled = true;
      clearInterval(timer);
      streamRef.current?.getTracks().forEach((tr) => tr.stop());
    };
    // run once per recorder mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Card dark className="overflow-hidden">
      {kind === "video" ? (
        <video ref={videoRef} autoPlay muted playsInline className="aspect-video w-full bg-black object-cover" />
      ) : (
        <div className="grid h-40 place-items-center">
          <Mic className="size-12 text-amber-500 animate-pulse" />
        </div>
      )}
      <div className="flex items-center gap-3 p-4">
        <span className="inline-flex items-center gap-2 font-mono text-lg tabular">
          <span className="size-3 rounded-full bg-bad animate-pulse" />
          {String(Math.floor(seconds / 60)).padStart(2, "0")}:{String(seconds % 60).padStart(2, "0")}
        </span>
        <Button className={cx("ml-auto")} onClick={() => recRef.current?.state === "recording" && recRef.current.stop()}>
          <Square className="size-4" /> {t("stop")}
        </Button>
        <Button variant="light" onClick={onCancel} aria-label="Cancel recording">
          <X className="size-4" />
        </Button>
      </div>
    </Card>
  );
}
