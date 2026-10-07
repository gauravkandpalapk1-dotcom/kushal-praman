"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ClipboardCheck, HardHat, ShieldCheck } from "lucide-react";
import { Brand, ChainFooter } from "@/components/shell";
import { Button, ErrorBox, Field, inputCls, Loading } from "@/components/ui";
import { homeFor, useAuth, useIsDemo } from "@/lib/auth";

// Seeded demo accounts (docs/README.md). Quick-fill is shown only when the server runs in DEMO mode.
const DEMO_ACCOUNTS = [
  { role: "candidate", label: "Raj Kumar", sub: "Candidate", email: "raj@kp.demo", password: "Candidate@2026", icon: HardHat },
  { role: "assessor", label: "Assessor A-07", sub: "Assessor A", email: "a07@kp.demo", password: "Assessor@2026", icon: ClipboardCheck },
  { role: "assessor", label: "Assessor A-12", sub: "Assessor B (blind)", email: "a12@kp.demo", password: "Assessor@2026", icon: ClipboardCheck },
  { role: "admin", label: "Administrator", sub: "Admin · Jury mode", email: "admin@kp.demo", password: "Admin@2026", icon: ShieldCheck },
] as const;

export default function LoginPage() {
  return (
    <Suspense fallback={<Loading />}>
      <Login />
    </Suspense>
  );
}

function Login() {
  const { login } = useAuth();
  const isDemo = useIsDemo();
  const router = useRouter();
  const params = useSearchParams();
  const as = params.get("as");
  const next = params.get("next");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function submit(e?: React.FormEvent, creds?: { email: string; password: string }) {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await login(creds?.email ?? email, creds?.password ?? password);
      router.push(next && next.startsWith("/") ? next : homeFor(u.role));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const accounts = DEMO_ACCOUNTS.filter((a) => !as || a.role === as);

  return (
    <div className="min-h-dvh flex flex-col">
      <div className="flex-1 grid lg:grid-cols-2">
        <div className="hidden lg:flex flex-col justify-between bg-navy-900 p-10 text-cream-50">
          <Brand dark />
          <div>
            <p className="text-3xl font-bold leading-tight">
              AI finds the evidence.
              <br />
              <span className="text-amber-500">The assessor decides what it means.</span>
            </p>
            <p className="mt-4 max-w-md text-navy-300">
              A traceable evidence-intelligence layer for Recognition of Prior Learning, built on the existing NCVET workflow and the official
              NQR QP → NOS → PC structure.
            </p>
          </div>
          <p className="text-xs text-navy-400">SIH26242 · Team AQUILA123</p>
        </div>

        <div className="flex items-center justify-center p-6">
          <div className="w-full max-w-md">
            <div className="lg:hidden mb-8">
              <Brand />
            </div>
            <h1 className="text-2xl font-bold text-navy-900">Sign in</h1>
            <p className="mt-1 text-muted">Candidates, assessors and administrators use the same sign-in.</p>

            <form onSubmit={submit} className="mt-6 grid gap-4">
              <Field label="Email">
                <input className={inputCls} type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
              </Field>
              <Field label="Password">
                <input className={inputCls} type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
              </Field>
              {error != null && <ErrorBox error={error} />}
              <Button type="submit" size="lg" loading={busy}>
                Sign in
              </Button>
            </form>

            <p className="mt-4 text-sm text-muted">
              New candidate or assessor?{" "}
              <Link href="/register" className="font-semibold text-navy-900 underline-offset-2 hover:underline">
                Create an account
              </Link>
            </p>

            {isDemo && (
              <div className="mt-8">
                <div className="eyebrow text-amber-700 mb-2">Demo accounts (seeded · demo mode only)</div>
                <div className="grid gap-2 sm:grid-cols-2">
                  {accounts.map((a) => (
                    <button
                      key={a.email}
                      onClick={() => submit(undefined, a)}
                      disabled={busy}
                      className="flex items-center gap-3 rounded-xl bg-white p-3 text-left ring-1 ring-navy-900/10 transition hover:ring-amber-500 disabled:opacity-50"
                    >
                      <a.icon className="size-5 text-amber-600 shrink-0" />
                      <span className="min-w-0">
                        <span className="block font-semibold text-navy-900 truncate">{a.label}</span>
                        <span className="block text-xs text-muted">{a.sub}</span>
                      </span>
                    </button>
                  ))}
                </div>
                {as && (
                  <Link href="/login" className="mt-2 inline-block text-xs text-muted hover:text-navy-900">
                    Show all demo accounts
                  </Link>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
      <ChainFooter />
    </div>
  );
}
