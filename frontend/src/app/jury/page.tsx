"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import {
  AlertTriangle, BarChart3, BookOpen, Brain, CloudOff, History, Layers, Lightbulb, Lock, RotateCcw, Scale, Target, UserRound, X,
} from "lucide-react";
import { AppShell } from "@/components/shell";
import { ChainHero } from "@/components/chain-hero";
import { Badge, Button, Card, cx, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth, useIsDemo, useRequireRole } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import type { Assessment, Evidence } from "@/lib/types";

const DEMO = {
  candidate: { email: "raj@kp.demo", password: "Candidate@2026", label: "Raj Kumar · candidate" },
  a07: { email: "a07@kp.demo", password: "Assessor@2026", label: "A-07 · Assessor A" },
  a12: { email: "a12@kp.demo", password: "Assessor@2026", label: "A-12 · Assessor B" },
  admin: { email: "admin@kp.demo", password: "Admin@2026", label: "Admin" },
};

const STAGES = [
  { key: "fresh", t: "Fresh", d: "Nothing captured. Start the full live flow from the candidate's phone." },
  { key: "processed", t: "Evidence #17 synced & processed", d: "Skip capture. Start at the assessor workspace." },
  { key: "assessor_a_scored", t: "Assessor A scored", d: "A-07 has 3/4 final. Continue with the blind second assessor." },
  { key: "both_scored", t: "Both scored", d: "Show agreement, audit and the record export." },
] as const;

type PanelKey = "problem" | "innovation" | "ai";

export default function JuryPage() {
  const user = useRequireRole(["admin"]);
  const isDemo = useIsDemo();
  const { login, logout } = useAuth();
  const router = useRouter();
  const ev = useApi<Evidence[]>(user ? "/evidence" : null);
  const as = useApi<Assessment[]>(user ? "/assessments" : null);
  const [panel, setPanel] = useState<PanelKey | null>(null);
  const [confirmStage, setConfirmStage] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState<string | null>(null);

  if (!user) return <Loading />;
  const latestEv = ev.data?.[0];
  const finalized = as.data?.find((a) => a.status === "finalized") ?? as.data?.[0];

  async function switchTo(who: keyof typeof DEMO, target: string) {
    setBusy(who);
    try {
      logout();
      await login(DEMO[who].email, DEMO[who].password);
      router.push(target);
    } catch (e) {
      setError(e);
      setBusy(null);
    }
  }

  async function reset(stage: string) {
    setBusy(`reset-${stage}`);
    setError(null);
    try {
      await api.post("/demo/reset", { stage });
      // Demo reset re-seeds users; sign in again as admin to keep a valid session.
      await login(DEMO.admin.email, DEMO.admin.password);
      ev.reload();
      as.reload();
      setDone(stage);
      setConfirmStage(null);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }

  const tiles: { icon: typeof Target; t: string; d: string; onClick: () => void; tone?: "amber" }[] = [
    { icon: AlertTriangle, t: "Problem", d: "Lost wages, inconsistent standards, too few assessors", onClick: () => setPanel("problem") },
    { icon: Lightbulb, t: "Innovation", d: "Evidence → exact PC, not more evidence", onClick: () => setPanel("innovation") },
    {
      icon: Layers,
      t: "Evidence mapper",
      d: latestEv ? `${latestEv.label} → NOS → PC` : "Needs processed evidence (stage 2)",
      onClick: () => latestEv && router.push(`/assessor/mapper?evidence=${latestEv.id}`),
      tone: "amber",
    },
    { icon: Lock, t: "Assessor-first", d: "Score locked → AI revealed → decide", onClick: () => (latestEv ? switchTo("a07", `/assessor/workspace?evidence=${latestEv.id}`) : switchTo("a07", "/assessor")) },
    { icon: CloudOff, t: "Offline capture", d: "Zero signal → encrypted queue → sync", onClick: () => switchTo("candidate", "/candidate/capture") },
    { icon: Brain, t: "AI role", d: "Finds, tags, segments, flags. Never scores", onClick: () => setPanel("ai") },
    { icon: History, t: "Audit trail", d: "Hash-chained, verifiable", onClick: () => router.push(finalized ? `/trace?assessment=${finalized.id}` : "/admin/audit") },
    { icon: Scale, t: "Agreement", d: "A vs B, blind → weighted κ", onClick: () => router.push("/admin/agreement") },
    { icon: BarChart3, t: "Impact", d: "4 metrics, pilot vs demo separated", onClick: () => router.push("/admin/analytics") },
    { icon: BookOpen, t: "Research basis", d: "10 sources → design decisions", onClick: () => router.push("/research") },
  ];

  return (
    <AppShell wide>
      <PageHeader
        eyebrow="Jury mode · team only"
        title="Every answer within one click"
        sub="Use this hub to answer jury questions quickly. It is not visible to candidates or assessors."
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {tiles.map((t) => (
          <button
            key={t.t}
            onClick={t.onClick}
            className={cx(
              "group flex flex-col items-start rounded-2xl p-4 text-left ring-1 transition hover:-translate-y-0.5",
              t.tone === "amber" ? "bg-amber-500 text-navy-950 ring-amber-600" : "bg-navy-900 text-cream-50 ring-white/5 hover:ring-amber-500",
            )}
          >
            <t.icon className={cx("size-6", t.tone === "amber" ? "text-navy-950" : "text-amber-500")} />
            <span className="mt-3 text-lg font-bold">{t.t}</span>
            <span className={cx("text-sm", t.tone === "amber" ? "text-navy-800" : "text-navy-300")}>{t.d}</span>
          </button>
        ))}
      </div>

      <AnimatePresence>
        {panel && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-5">
            <Card className="relative p-6">
              <button onClick={() => setPanel(null)} className="absolute right-4 top-4 rounded-md p-1.5 hover:bg-cream-200" aria-label="Close">
                <X className="size-5" />
              </button>
              {panel === "problem" && <ProblemPanel />}
              {panel === "innovation" && <InnovationPanel />}
              {panel === "ai" && <AiPanel />}
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="mt-6 grid gap-5 lg:grid-cols-[1.2fr_1fr]">
        <Card className="p-5">
          <h2 className="font-bold text-navy-900">3-minute live flow</h2>
          <ol className="mt-3 grid gap-2 text-sm">
            {[
              ["Candidate", "Capture → Field simulation ON → Use practical recording → Save. Evidence #17 · saved locally · waiting.", "candidate", "/candidate/capture"],
              ["Candidate", "Field simulation OFF → synced ✓ hash verified ✓", null, null],
              ["Assessor A-07", "Workspace → Find relevant evidence → AI found 00:42–01:08 → Mapper chain", "a07", "/assessor"],
              ["Assessor A-07", "Assess PC10 → 3/4 → Lock → AI support 91% revealed → Confirm mapping → Final 3/4", null, null],
              ["Assessor A-07", "Audit trail → Verify chain → Record PDF", null, null],
              ["Assessor A-12", "Same evidence, blind → 3/4 → final", "a12", "/assessor"],
              ["Admin", "Agreement: n = 1 → Pilot measurement underway → Impact", "admin", "/admin/agreement"],
            ].map(([who, what, acct, target], i) => (
              <li key={i} className="flex items-start gap-3 rounded-lg bg-cream-100 px-3 py-2">
                <span className="grid size-6 shrink-0 place-items-center rounded-full bg-navy-900 text-xs font-bold text-amber-500">{i + 1}</span>
                <span className="flex-1">
                  <b className="text-navy-900">{who}</b> · {what}
                </span>
                {acct && isDemo && (
                  <Button size="sm" variant="outline" loading={busy === acct} onClick={() => switchTo(acct as keyof typeof DEMO, target as string)}>
                    <UserRound className="size-3.5" /> Go
                  </Button>
                )}
              </li>
            ))}
          </ol>
        </Card>

        <Card className="p-5">
          <h2 className="font-bold text-navy-900">Demo safety net</h2>
          <p className="text-sm text-muted">If any step misbehaves live, jump to a known stage. This wipes and re-seeds the demo database (demo mode only).</p>
          {!isDemo && <Badge tone="bad" className="mt-3">Server is in REAL mode. Reset disabled.</Badge>}
          <ul className="mt-3 grid gap-2">
            {STAGES.map((s, i) => (
              <li key={s.key} className="rounded-xl ring-1 ring-navy-900/10 p-3">
                <div className="flex items-center gap-3">
                  <span className="grid size-7 place-items-center rounded-full bg-cream-200 text-sm font-bold">{i + 1}</span>
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold text-navy-900">
                      {s.t} {done === s.key && <Badge tone="ok">loaded</Badge>}
                    </div>
                    <div className="text-xs text-muted">{s.d}</div>
                  </div>
                  {confirmStage === s.key ? (
                    <div className="flex gap-1">
                      <Button size="sm" variant="danger" loading={busy === `reset-${s.key}`} onClick={() => reset(s.key)}>
                        Confirm
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setConfirmStage(null)}>
                        No
                      </Button>
                    </div>
                  ) : (
                    <Button size="sm" variant="outline" disabled={!isDemo} onClick={() => setConfirmStage(s.key)}>
                      <RotateCcw className="size-3.5" /> Load
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-muted">Also clear the candidate device queue after stage 1: candidate → Capture → remove items, or use a private window.</p>
          {error != null && <div className="mt-3"><ErrorBox error={error} /></div>}
        </Card>
      </div>
    </AppShell>
  );
}

function ProblemPanel() {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div>
        <div className="eyebrow text-amber-700">The problem</div>
        <h2 className="mt-1 text-2xl font-bold text-navy-900">A 10-minute video, judged from memory</h2>
        <p className="mt-3 text-navy-800">
          A practical assessment produces a ten-minute recording. Today the assessor watches all of it and judges it against the standard from
          memory. The link between a score and the exact evidence behind it is not recorded.
        </p>
      </div>
      <ul className="grid gap-3">
        {[
          ["Daily-wage workers lose income to attend assessments", "[1] NCVET 2023"],
          ["Inconsistent application of standards weakens trust", "[2] ILO 2026"],
          ["Too few qualified assessors", "[1][2]"],
        ].map(([t, r]) => (
          <li key={t} className="rounded-xl bg-navy-900 p-4 text-cream-50">
            <div className="font-semibold">{t}</div>
            <div className="text-xs text-amber-300">{r}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function InnovationPanel() {
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr] lg:items-center">
      <div>
        <div className="eyebrow text-amber-700">The innovation</div>
        <h2 className="mt-1 text-2xl font-bold text-navy-900">We don&apos;t collect more evidence. We link existing evidence to the exact PC it supports.</h2>
        <p className="mt-3 text-navy-800">
          Existing RPL evidence + AI evidence discovery + PC-level traceability + assessor-first validation + audit trail + offline-first operation.
          A layer on the current NCVET workflow, not a replacement for it.
        </p>
        <p className="mt-3 text-sm text-muted">Not a job portal, LMS, chatbot, video classifier, registration portal or certification authority.</p>
      </div>
      <ChainHero caption={false} />
    </div>
  );
}

function AiPanel() {
  return (
    <div>
      <div className="eyebrow text-amber-700">The AI role</div>
      <h2 className="mt-1 text-2xl font-bold text-navy-900">AI finds the evidence. The assessor decides what it means.</h2>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <div className="rounded-xl bg-ok-soft p-4">
          <div className="font-bold text-ok">AI does</div>
          <p className="mt-1 text-sm text-navy-800">Segment video, transcribe Indian-language speech, tag tools/actions, describe segments neutrally, propose Evidence → NOS → PC links with a relevance score.</p>
        </div>
        <div className="rounded-xl bg-bad-soft p-4">
          <div className="font-bold text-bad">AI never</div>
          <p className="mt-1 text-sm text-navy-800">Scores a candidate, says &ldquo;competent&rdquo;, or certifies. A guardrail strips any competency verdict from model output [10].</p>
        </div>
        <div className="rounded-xl bg-amber-50 p-4">
          <div className="font-bold text-amber-700">Why so narrow</div>
          <p className="mt-1 text-sm text-navy-800">Video skill scoring is proven mainly in narrow, structured domains [6][7]; explanations alone don&apos;t stop over-reliance [5].</p>
        </div>
      </div>
      <p className="mt-4 text-sm text-muted">
        Before scoring the assessor sees <b>where</b> the evidence is (time saving). After locking a score they see the AI&apos;s confidence and explanation
        (anti-anchoring). The server enforces this order.
      </p>
    </div>
  );
}
