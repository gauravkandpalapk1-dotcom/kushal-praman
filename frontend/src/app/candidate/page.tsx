"use client";

import { useState } from "react";
import { ChevronDown, Plus } from "lucide-react";
import { AppShell } from "@/components/shell";
import { NetworkCard } from "@/components/candidate/network-card";
import { KIND_ICON, QueueCard } from "@/components/candidate/queue";
import { Badge, ButtonLink, Card, cx, EmptyState, Loading, PageHeader } from "@/components/ui";
import { useRequireRole } from "@/lib/auth";
import { istDateTime } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import { LangToggle, useI18n } from "@/lib/i18n";
import { useQueue } from "@/lib/offline/useSync";
import type { Evidence, QualificationTree, User } from "@/lib/types";

export default function CandidateHome() {
  const user = useRequireRole(["candidate"]);
  if (!user) return <Loading />;
  return <Dashboard user={user} />;
}

const STATUS_LABEL: Record<Evidence["status"], { label: string; tone: "neutral" | "amber" | "ok" | "bad" }> = {
  received: { label: "With the assessor", tone: "neutral" },
  processing: { label: "Processing", tone: "amber" },
  ready: { label: "Ready for assessment", tone: "ok" },
  failed: { label: "Processing failed", tone: "bad" },
};

function Dashboard({ user }: { user: User }) {
  const { t, lang, setLang } = useI18n(user.candidate?.preferred_language);
  const q = useQueue(user.id);
  const qid = user.candidate?.qualification_id;
  const tree = useApi<QualificationTree>(qid ? `/qualifications/${qid}/tree` : null);
  const evidence = useApi<Evidence[]>(q.online ? `/evidence?v=${q.version}` : null);
  const [openNos, setOpenNos] = useState<number | null>(null);
  const local = q.items.filter((i) => i.status !== "synced");
  const serverById = Object.fromEntries((evidence.data ?? []).map((e) => [e.id, e]));

  return (
    <AppShell>
      <PageHeader
        eyebrow={`${t("namaste")} · ${user.candidate?.candidate_code ?? ""}`}
        title={user.full_name}
        sub="Your existing work is your evidence. Capture it once; it is linked to the official criteria for your qualification."
        actions={
          <>
            <LangToggle lang={lang} setLang={setLang} />
            <ButtonLink href="/candidate/capture" size="md">
              <Plus className="size-4" /> {t("capture")}
            </ButtonLink>
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr] [&>*]:min-w-0">
        <div className="grid gap-5 content-start">
          <Card className="p-5">
            <div className="eyebrow text-amber-700">{t("myQualification")}</div>
            {tree.loading && <Loading />}
            {tree.data && (
              <>
                <h2 className="mt-1 text-xl font-bold text-navy-900">{tree.data.qualification.title}</h2>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Badge>NSQF Level {tree.data.qualification.nsqf_level}</Badge>
                  <Badge tone="info">{tree.data.qualification.nqr_code}</Badge>
                  <Badge tone="amber">Assessment mode: {tree.data.qualification.assessment_mode}</Badge>
                </div>
                <h3 className="mt-5 text-sm font-bold text-navy-800">{t("criteria")}</h3>
                <ul className="mt-2 divide-y divide-navy-900/6 rounded-xl ring-1 ring-navy-900/8">
                  {tree.data.nos.map((n) => (
                    <li key={n.id}>
                      <button
                        className="flex w-full items-center gap-3 px-4 py-3 text-left"
                        onClick={() => setOpenNos(openNos === n.id ? null : n.id)}
                        aria-expanded={openNos === n.id}
                      >
                        <span className="font-mono text-xs font-bold text-navy-600 w-24 sm:w-28 shrink-0">{n.code}</span>
                        <span className="min-w-0 flex-1 text-sm font-semibold text-navy-900">{n.title}</span>
                        <span className="hidden sm:inline text-xs text-muted">{n.pcs.length ? `${n.pcs.length} PC` : "PCs from Q-File"}</span>
                        <ChevronDown className={cx("size-4 text-navy-400 transition", openNos === n.id && "rotate-180")} />
                      </button>
                      {openNos === n.id && (
                        <div className="px-4 pb-4">
                          {n.pcs.length === 0 ? (
                            <p className="text-sm text-muted">Performance criteria for this NOS are not loaded in the demo dataset.</p>
                          ) : (
                            n.pcs.map((p) => (
                              <div key={p.id} className="rounded-lg bg-cream-100 p-3">
                                <div className="flex items-center gap-2">
                                  <span className="font-bold text-amber-700">{p.code}</span>
                                  {p.is_verbatim && <Badge tone="info">Verbatim · NQR [4]</Badge>}
                                </div>
                                <p className="mt-1 text-[0.95rem] text-navy-900">&ldquo;{p.text}&rdquo;</p>
                              </div>
                            ))
                          )}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </Card>

          <Card className="p-5">
            <h2 className="font-bold text-navy-900">{t("submitted")}</h2>
            {!q.online ? (
              <p className="mt-2 text-sm text-muted">Shown when online. Evidence on this device is listed on the right.</p>
            ) : evidence.data && evidence.data.length > 0 ? (
              <ul className="mt-3 divide-y divide-navy-900/6">
                {evidence.data.map((e) => {
                  const Icon = KIND_ICON[e.kind];
                  const s = STATUS_LABEL[e.status];
                  return (
                    <li key={e.id} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 py-3">
                      <Icon className="size-5 text-navy-500" />
                      <div className="min-w-0 flex-1">
                        <div className="font-semibold text-navy-900">{e.label}</div>
                        <div className="text-xs text-muted">
                          {e.kind} · captured {istDateTime(e.captured_at)} {e.offline_captured ? "· offline" : ""}
                        </div>
                      </div>
                      <Badge tone={e.integrity_ok === false ? "bad" : "ok"}>{e.integrity_ok === false ? "Hash mismatch" : "Hash verified"}</Badge>
                      <Badge tone={s.tone}>{s.label}</Badge>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <EmptyState title="No evidence submitted yet">Capture a video, photo, voice note or document of your work.</EmptyState>
            )}
          </Card>
        </div>

        <div className="grid gap-4 content-start">
          <NetworkCard t={t} pending={local.length} />
          <div>
            <h2 className="font-bold text-navy-900">{t("queue")}</h2>
            {local.length === 0 ? (
              <Card className="mt-2">
                <EmptyState title={t("noItems")} />
              </Card>
            ) : (
              <ul className="mt-2 grid gap-3">
                {local.map((item) => (
                  <QueueCard
                    key={item.local_id}
                    item={item}
                    server={item.server_evidence_id ? serverById[item.server_evidence_id] : undefined}
                    online={q.online}
                    t={t}
                    onRetry={() => void q.engine.retry(item.local_id)}
                    onRemove={() => void q.engine.remove(item.local_id)}
                  />
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
