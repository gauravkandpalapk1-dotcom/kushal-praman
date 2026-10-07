"use client";

import Link from "next/link";
import { ArrowRight, Gavel, History, Layers, ScrollText, Users, FileVideo, BarChart3, Scale, Activity } from "lucide-react";
import { AppShell } from "@/components/shell";
import { ChainVerify } from "@/components/audit";
import { ButtonLink, Card, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { useRequireRole } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import type { Impact } from "@/lib/types";

const LINKS = [
  { href: "/admin/qualifications", icon: Layers, t: "Qualifications", d: "QP → NOS → PC, rubrics" },
  { href: "/admin/users", icon: Users, t: "Assessors & candidates", d: "Accounts and access" },
  { href: "/admin/evidence", icon: FileVideo, t: "Evidence", d: "Integrity, capture context, mappings" },
  { href: "/admin/assessments", icon: Gavel, t: "Assessments", d: "Initial vs final, rationale" },
  { href: "/admin/audit", icon: History, t: "Audit log", d: "Hash-chained, verifiable" },
  { href: "/admin/agreement", icon: Scale, t: "Agreement", d: "Blind double-scoring, weighted κ" },
  { href: "/admin/analytics", icon: BarChart3, t: "Impact metrics", d: "Pilot vs demo, kept separate" },
  { href: "/research", icon: ScrollText, t: "Research basis", d: "10 sources → design decisions" },
  { href: "/status", icon: Activity, t: "System health", d: "DB, storage, ffmpeg, AI adapters" },
];

export default function AdminHome() {
  const user = useRequireRole(["admin"]);
  const impact = useApi<Impact>(user ? "/analytics/impact" : null);
  if (!user) return <Loading />;
  return (
    <AppShell>
      <PageHeader
        eyebrow="Administration · assessment agency"
        title="Overview"
        sub="Standards, people, evidence and assurance in one place."
        actions={
          <ButtonLink href="/jury" variant="primary">
            Jury mode <ArrowRight className="size-4" />
          </ButtonLink>
        }
      />
      {impact.error != null && <ErrorBox error={impact.error} onRetry={impact.reload} />}
      {impact.data && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {Object.entries(impact.data.counts).map(([k, v]) => (
            <Card key={k} className="p-4">
              <div className="text-xs capitalize text-muted">{k.replace(/_/g, " ")}</div>
              <div className="text-3xl font-bold tabular text-navy-900">{v}</div>
            </Card>
          ))}
        </div>
      )}
      <div className="mt-6 grid gap-5 lg:grid-cols-[2fr_1fr]">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 content-start">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} className="group rounded-2xl bg-white p-4 ring-1 ring-navy-900/8 transition hover:ring-amber-500">
              <l.icon className="size-5 text-amber-600" />
              <div className="mt-2 font-semibold text-navy-900">{l.t}</div>
              <div className="text-sm text-muted">{l.d}</div>
            </Link>
          ))}
        </div>
        <div className="grid gap-4 content-start">
          <ChainVerify />
        </div>
      </div>
    </AppShell>
  );
}
