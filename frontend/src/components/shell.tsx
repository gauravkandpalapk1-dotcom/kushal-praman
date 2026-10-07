"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { CloudOff, LogOut, Menu, RefreshCw, Wifi, X } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useSyncState } from "@/lib/offline/useSync";
import type { Role } from "@/lib/types";
import { Badge, cx } from "./ui";

export function BrandMark({ className }: { className?: string }) {
  // Two linked nodes = evidence ↔ criterion
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="8" fill="#F5A524" />
      <circle cx="11" cy="16" r="4.2" fill="none" stroke="#7f1414" strokeWidth="2.6" />
      <circle cx="21" cy="16" r="4.2" fill="#7f1414" />
      <path d="M15.2 16h1.6" stroke="#7f1414" strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  );
}

export function Brand({ dark }: { dark?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2.5 shrink-0">
      <BrandMark className="size-8" />
      <span className="leading-tight">
        <span className={cx("block font-bold tracking-tight", dark ? "text-cream-50" : "text-navy-900")}>Kaushal Pramaan</span>
        <span className={cx("hidden sm:block text-[0.68rem] font-semibold tracking-wide", dark ? "text-navy-300" : "text-muted")}>
          RPL Evidence Intelligence
        </span>
      </span>
    </Link>
  );
}

const NAV: Record<Role, { href: string; label: string }[]> = {
  candidate: [
    { href: "/candidate", label: "My qualification" },
    { href: "/candidate/capture", label: "Capture evidence" },
    { href: "/research", label: "Design basis" },
  ],
  assessor: [
    { href: "/assessor", label: "Assessment queue" },
    { href: "/research", label: "Design basis" },
  ],
  admin: [
    { href: "/admin", label: "Overview" },
    { href: "/admin/qualifications", label: "Qualifications" },
    { href: "/admin/users", label: "Users" },
    { href: "/admin/evidence", label: "Evidence" },
    { href: "/admin/assessments", label: "Assessments" },
    { href: "/admin/audit", label: "Audit" },
    { href: "/admin/agreement", label: "Agreement" },
    { href: "/admin/analytics", label: "Impact" },
    { href: "/research", label: "Research" },
    { href: "/status", label: "System" },
  ],
};

export function ConnectivityPill({ compact }: { compact?: boolean }) {
  const s = useSyncState();
  if (s.online)
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-ok-soft px-2.5 py-1 text-xs font-bold text-ok">
        {s.syncing ? <RefreshCw className="size-3.5 animate-spin" /> : <Wifi className="size-3.5" />}
        <span className="hidden sm:inline">{s.syncing ? "SYNCING" : "ONLINE"}</span>
        <span className="sr-only sm:hidden">{s.syncing ? "Syncing" : "Online"}</span>
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-navy-900 px-2.5 py-1 text-xs font-bold text-amber-300" title={s.simulatedOffline ? "Field simulation: sync is paused as if there is no signal" : "Browser reports no network"}>
      <CloudOff className="size-3.5" />
      <span className="hidden sm:inline">OFFLINE{!compact && s.simulatedOffline ? " · simulated" : ""}</span>
      <span className="sm:hidden">OFF</span>
    </span>
  );
}

export function AppShell({ children, wide }: { children: React.ReactNode; wide?: boolean }) {
  const { user, logout, health } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const items = user ? NAV[user.role] : [];

  const isActive = (href: string) =>
    href === pathname || (href !== "/admin" && href !== "/candidate" && href !== "/assessor" && pathname.startsWith(href + "/"));

  return (
    <div className="min-h-dvh flex flex-col">
      <header className="sticky top-0 z-30 border-b border-navy-900/8 bg-cream-50/90 backdrop-blur supports-[backdrop-filter]:bg-cream-50/75">
        <div className={cx("mx-auto flex h-16 items-center gap-2 sm:gap-4 px-4", wide ? "max-w-[1500px]" : "max-w-7xl")}>
          <Brand />
          <nav className="hidden lg:flex items-center gap-0.5 ml-4 overflow-x-auto" aria-label="Main">
            {items.map((i) => (
              <Link
                key={i.href}
                href={i.href}
                className={cx(
                  "rounded-md px-2.5 py-1.5 text-sm font-medium whitespace-nowrap transition-colors",
                  isActive(i.href) ? "bg-navy-900 text-cream-50" : "text-navy-700 hover:bg-navy-900/5",
                )}
              >
                {i.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
            {health?.mode === "demo" && (
              <Badge tone="amber" className="hidden sm:inline-flex" title="Seeded deterministic analysis for demo media. Real services run where available.">
                DEMO MODE
              </Badge>
            )}
            <ConnectivityPill compact />
            {user && (
              <div className="hidden md:flex items-center gap-2 pl-2 ml-1 border-l border-navy-900/10">
                <div className="text-right leading-tight">
                  <div className="text-sm font-semibold text-navy-900">{user.full_name}</div>
                  <div className="text-[0.7rem] text-muted capitalize">
                    {user.role}
                    {user.assessor ? ` · ${user.assessor.assessor_code}` : ""}
                  </div>
                </div>
                <button
                  onClick={() => {
                    logout();
                    router.push("/login");
                  }}
                  className="rounded-md p-2 text-navy-600 hover:bg-navy-900/5"
                  aria-label="Sign out"
                  title="Sign out"
                >
                  <LogOut className="size-4" />
                </button>
              </div>
            )}
            {user && (
              <button className="lg:hidden rounded-md p-2 hover:bg-navy-900/5" onClick={() => setOpen((o) => !o)} aria-label="Menu" aria-expanded={open}>
                {open ? <X className="size-5" /> : <Menu className="size-5" />}
              </button>
            )}
          </div>
        </div>
        {open && user && (
          <nav className="lg:hidden border-t border-navy-900/8 bg-cream-50 px-4 py-2 grid gap-1">
            {items.map((i) => (
              <Link key={i.href} href={i.href} onClick={() => setOpen(false)} className={cx("rounded-md px-3 py-2.5 text-[0.95rem] font-medium", isActive(i.href) ? "bg-navy-900 text-cream-50" : "text-navy-800")}>
                {i.label}
              </Link>
            ))}
            <button
              onClick={() => {
                logout();
                router.push("/login");
              }}
              className="text-left rounded-md px-3 py-2.5 text-[0.95rem] font-medium text-bad"
            >
              Sign out ({user.full_name})
            </button>
          </nav>
        )}
      </header>
      <main className={cx("mx-auto w-full flex-1 px-4 py-6 sm:py-8", wide ? "max-w-[1500px]" : "max-w-7xl")}>{children}</main>
      <ChainFooter />
    </div>
  );
}

export function ChainFooter({ dark }: { dark?: boolean }) {
  return (
    <footer className={cx("border-t px-4 py-4", dark ? "border-white/10 bg-navy-950 text-navy-300" : "border-navy-900/8 text-muted")}>
      <div className="mx-auto max-w-7xl flex flex-wrap items-center justify-between gap-2 text-[0.7rem] font-bold tracking-[0.14em]">
        <span>
          EVIDENCE <span className="text-amber-600">→</span> <span className="text-amber-600">PERFORMANCE CRITERION</span> → HUMAN ASSESSMENT → RECOGNITION
        </span>
        <span className="font-semibold tracking-normal normal-case">AI finds the evidence. The assessor decides what it means.</span>
      </div>
    </footer>
  );
}
