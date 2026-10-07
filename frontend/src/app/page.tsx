"use client";

import Link from "next/link";
import { ArrowRight, ClipboardCheck, HardHat, ShieldCheck } from "lucide-react";
import { ChainHero } from "@/components/chain-hero";
import { Brand, ChainFooter, ConnectivityPill } from "@/components/shell";
import { ButtonLink } from "@/components/ui";
import { homeFor, useAuth } from "@/lib/auth";

const PRINCIPLES = [
  { t: "Assessor-first", d: "The assessor locks a score before any AI interpretation appears. The server enforces it.", ref: "[5]" },
  { t: "Narrow AI", d: "AI finds, tags, segments and flags evidence. It never scores a person.", ref: "[6][7][10]" },
  { t: "Official structure", d: "QP → NOS → PC exactly as in the NQR Q-File. No home-made ontology.", ref: "[4]" },
  { t: "Rubric-bound", d: "Every PC has a versioned 0–4 rubric beside the evidence at scoring time.", ref: "[8]" },
  { t: "Offline-first", d: "Capture, encrypt and queue with zero signal. Sync when connected.", ref: "[1][4]" },
  { t: "Measured, not claimed", d: "Blind double-scoring → weighted κ. Reported only once measured.", ref: "[2]" },
];

const NOT = ["a job portal", "an LMS", "an AI chatbot", "a video classifier", "an RPL registration portal", "a certification authority"];

export default function Landing() {
  const { user } = useAuth();
  return (
    <div className="min-h-dvh flex flex-col">
      <div className="bg-navy-900 text-cream-50">
        <header className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4">
          <Brand dark />
          <div className="ml-auto flex items-center gap-2 sm:gap-3">
            <ConnectivityPill compact />
            {user ? (
              <ButtonLink href={homeFor(user.role)} size="sm">
                <span className="hidden sm:inline">Continue as {user.full_name.split(" ")[0]}</span>
                <span className="sm:hidden">Continue</span> <ArrowRight className="size-4" />
              </ButtonLink>
            ) : (
              <ButtonLink href="/login" size="sm">
                Sign in
              </ButtonLink>
            )}
          </div>
        </header>

        <section className="mx-auto grid max-w-7xl gap-10 px-4 pb-16 pt-8 lg:grid-cols-[1.05fr_1fr] lg:items-center lg:pt-14">
          <div className="animate-fade-up">
            <div className="eyebrow text-amber-500">SIH 2026 · SIH26242 · Smart Education · Team AQUILA123</div>
            <h1 className="mt-3 text-4xl font-bold leading-[1.08] tracking-tight sm:text-5xl">
              Evidence, linked to the <span className="text-amber-500">exact criterion</span> it proves.
            </h1>
            <p className="mt-5 max-w-xl text-lg text-navy-300">
              We don&apos;t collect more evidence. We link existing RPL evidence to the exact NQR Performance Criterion it supports, so every
              score has its proof.
            </p>
            <p className="mt-5 text-lg font-semibold">
              AI finds the evidence. <span className="text-amber-500">The assessor decides what it means.</span>
            </p>
            <div className="mt-8 grid gap-3 sm:grid-cols-3 max-w-2xl">
              <RoleCard href="/login?as=candidate" icon={<HardHat className="size-5" />} title="Candidate" sub="Capture evidence, even offline" />
              <RoleCard href="/login?as=assessor" icon={<ClipboardCheck className="size-5" />} title="Assessor" sub="Review, score, decide" />
              <RoleCard href="/login?as=admin" icon={<ShieldCheck className="size-5" />} title="Admin" sub="Standards, audit, agreement" />
            </div>
          </div>
          <div className="animate-fade-up [animation-delay:120ms]">
            <ChainHero />
          </div>
        </section>
      </div>

      <section className="mx-auto w-full max-w-7xl px-4 py-12">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["Evidence", "Existing RPL evidence: practical video, photos, voice, documents, with time, place and hash."],
            ["Performance criterion", "Each item is linked to the exact NOS → PC it supports, anchored to a time segment."],
            ["Human assessment", "The assessor scores first against the rubric, then sees AI support, then decides."],
            ["Recognition", "An audit-ready record goes to the Awarding Body, which certifies through the existing ecosystem."],
          ].map(([t, d], i) => (
            <div key={t} className="rounded-2xl bg-white p-5 ring-1 ring-navy-900/8">
              <div className="eyebrow text-amber-700">
                {String(i + 1).padStart(2, "0")} · {t}
              </div>
              <p className="mt-2 text-[0.95rem] text-navy-800">{d}</p>
            </div>
          ))}
        </div>

        <div className="mt-10 grid gap-8 lg:grid-cols-[1fr_1.4fr]">
          <div>
            <h2 className="text-xl font-bold text-navy-900">What this is, and what it isn&apos;t</h2>
            <ul className="mt-4 grid grid-cols-2 gap-2 text-sm">
              {NOT.map((n) => (
                <li key={n} className="rounded-lg bg-cream-200/70 px-3 py-2 text-navy-700">
                  <span className="text-bad font-bold mr-1.5">✕</span>Not {n}
                </li>
              ))}
            </ul>
            <p className="mt-4 rounded-xl bg-navy-900 p-4 font-semibold text-cream-50">
              <span className="text-amber-500">✓</span> A traceable evidence-intelligence layer on top of the existing RPL workflow.
            </p>
          </div>
          <div>
            <h2 className="text-xl font-bold text-navy-900">Designed around the assessor</h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {PRINCIPLES.map((p) => (
                <div key={p.t} className="rounded-xl bg-white p-4 ring-1 ring-navy-900/8">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="font-semibold text-navy-900">{p.t}</span>
                    <span className="text-xs font-semibold text-amber-700">{p.ref}</span>
                  </div>
                  <p className="mt-1 text-sm text-muted">{p.d}</p>
                </div>
              ))}
            </div>
            <Link href="/research" className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-navy-800 hover:text-amber-700">
              Research &amp; design basis: 10 sources, each mapped to a design decision <ArrowRight className="size-4" />
            </Link>
          </div>
        </div>
      </section>
      <ChainFooter />
    </div>
  );
}

function RoleCard({ href, icon, title, sub }: { href: string; icon: React.ReactNode; title: string; sub: string }) {
  return (
    <Link href={href} className="group rounded-xl bg-white/5 p-4 ring-1 ring-white/10 transition hover:bg-white/10 hover:ring-amber-500/50">
      <div className="flex items-center gap-2 text-amber-500">
        {icon}
        <span className="font-semibold text-cream-50">{title}</span>
        <ArrowRight className="ml-auto size-4 opacity-0 transition group-hover:opacity-100" />
      </div>
      <p className="mt-1 text-sm text-navy-300">{sub}</p>
    </Link>
  );
}
