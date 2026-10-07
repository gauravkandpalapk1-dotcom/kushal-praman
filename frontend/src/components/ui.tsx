"use client";

import Link from "next/link";
import { forwardRef } from "react";
import { AlertTriangle, FlaskConical, Loader2 } from "lucide-react";

export function cx(...xs: (string | false | null | undefined)[]) {
  return xs.filter(Boolean).join(" ");
}

type BtnVariant = "primary" | "dark" | "ghost" | "outline" | "danger" | "light";
const btnBase =
  "inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition-all disabled:opacity-45 disabled:cursor-not-allowed select-none active:translate-y-px";
const btnVariants: Record<BtnVariant, string> = {
  primary: "bg-amber-500 text-navy-950 hover:bg-amber-300 shadow-sm shadow-amber-700/20",
  dark: "bg-navy-900 text-cream-50 hover:bg-navy-700",
  ghost: "text-navy-800 hover:bg-navy-900/5",
  outline: "border border-navy-900/20 text-navy-900 hover:border-navy-900/40 hover:bg-white",
  danger: "bg-bad text-white hover:bg-bad/90",
  light: "bg-white/10 text-cream-50 hover:bg-white/20 border border-white/15",
};
const btnSizes = { sm: "h-9 px-3 text-sm", md: "h-11 px-4 text-[0.95rem]", lg: "h-13 px-6 text-base" };

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: BtnVariant;
  size?: keyof typeof btnSizes;
  loading?: boolean;
}
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, className, children, disabled, ...rest },
  ref,
) {
  return (
    <button ref={ref} className={cx(btnBase, btnVariants[variant], btnSizes[size], className)} disabled={disabled || loading} {...rest}>
      {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
});

export function ButtonLink({
  href,
  variant = "primary",
  size = "md",
  className,
  children,
}: {
  href: string;
  variant?: BtnVariant;
  size?: keyof typeof btnSizes;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Link href={href} className={cx(btnBase, btnVariants[variant], btnSizes[size], className)}>
      {children}
    </Link>
  );
}

export function Card({ className, children, dark }: { className?: string; children: React.ReactNode; dark?: boolean }) {
  return (
    <section
      className={cx(
        "rounded-2xl",
        dark ? "bg-navy-900 text-cream-50 ring-1 ring-white/5" : "bg-white ring-1 ring-navy-900/8 shadow-[0_1px_2px_rgba(127,20,20,0.06)]",
        className,
      )}
    >
      {children}
    </section>
  );
}

type Tone = "neutral" | "amber" | "ok" | "bad" | "info" | "dark" | "outline";
const tones: Record<Tone, string> = {
  neutral: "bg-cream-200 text-navy-800",
  amber: "bg-amber-100 text-amber-700",
  ok: "bg-ok-soft text-ok",
  bad: "bg-bad-soft text-bad",
  info: "bg-info-soft text-info",
  dark: "bg-navy-800 text-cream-100",
  outline: "ring-1 ring-current/30 text-current",
};
export function Badge({ tone = "neutral", className, children, title }: { tone?: Tone; className?: string; children: React.ReactNode; title?: string }) {
  return (
    <span title={title} className={cx("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[0.72rem] font-semibold whitespace-nowrap", tones[tone], className)}>
      {children}
    </span>
  );
}

/** Mandatory label for anything produced by seeded deterministic data. */
export function DemoBadge({ kind = "analysis", className }: { kind?: "analysis" | "data" | "media"; className?: string }) {
  const text = kind === "analysis" ? "DEMO ANALYSIS" : kind === "data" ? "DEMO DATA" : "SYNTHETIC DEMO MEDIA";
  const title =
    kind === "analysis"
      ? "Deterministic seeded output for the demo recording, not a live model prediction."
      : kind === "data"
        ? "Generated during this demo. Not pilot data."
        : "Placeholder recording generated for the demo. Replace with a real practical.";
  return (
    <span title={title} className={cx("inline-flex items-center gap-1 rounded-md border border-dashed border-amber-600/60 bg-amber-50 px-1.5 py-0.5 text-[0.65rem] font-bold tracking-wider text-amber-700", className)}>
      <FlaskConical className="size-3" aria-hidden />
      {text}
    </span>
  );
}

export function ModeBadge({ mode, className }: { mode: string | null | undefined; className?: string }) {
  if (mode === "demo") return <DemoBadge className={className} />;
  if (mode === "real")
    return <Badge tone="ok" className={className}>LIVE</Badge>;
  if (mode === "unavailable")
    return <Badge tone="neutral" className={className}>UNAVAILABLE</Badge>;
  return null;
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cx("size-5 animate-spin text-amber-600", className)} aria-label="Loading" />;
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-16 justify-center text-muted">
      <Spinner />
      <span>{label}</span>
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl bg-bad-soft p-4 text-bad">
      <AlertTriangle className="mt-0.5 size-5 shrink-0" />
      <div className="flex-1 text-sm">
        <p className="font-semibold">Something went wrong</p>
        <p className="opacity-90">{msg}</p>
      </div>
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  sub,
  actions,
}: {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  sub?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <div className="eyebrow text-amber-700 mb-1.5">{eyebrow}</div>}
        <h1 className="text-2xl sm:text-[1.7rem] font-bold tracking-tight text-navy-900">{title}</h1>
        {sub && <p className="mt-1 text-muted max-w-3xl">{sub}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function EmptyState({ icon, title, children }: { icon?: React.ReactNode; title: string; children?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center text-center gap-2 py-12 px-6 text-muted">
      {icon && <div className="text-navy-400 mb-1">{icon}</div>}
      <p className="font-semibold text-navy-800">{title}</p>
      {children && <div className="text-sm max-w-md">{children}</div>}
    </div>
  );
}

export const inputCls =
  "w-full h-11 rounded-lg border border-navy-900/15 bg-white px-3 text-[0.95rem] text-ink placeholder:text-navy-400 focus:border-amber-500 focus:ring-2 focus:ring-amber-500/25 outline-none transition";

export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold text-navy-800">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-muted">{hint}</span>}
    </label>
  );
}

/** Small key/value row used in metadata panels. */
export function KV({ k, v, mono }: { k: string; v: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5 text-sm">
      <dt className="text-muted shrink-0">{k}</dt>
      <dd className={cx("text-right text-navy-900 min-w-0 break-words", mono && "font-mono text-[0.8rem]")}>{v}</dd>
    </div>
  );
}
