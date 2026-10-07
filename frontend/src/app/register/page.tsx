"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Brand } from "@/components/shell";
import { Button, cx, ErrorBox, Field, inputCls } from "@/components/ui";
import { api } from "@/lib/api";
import { homeFor, useAuth } from "@/lib/auth";
import type { Qualification } from "@/lib/types";

const LANGS = [
  ["hi", "हिन्दी · Hindi"],
  ["en", "English"],
  ["bn", "বাংলা · Bengali"],
  ["mr", "मराठी · Marathi"],
  ["ta", "தமிழ் · Tamil"],
  ["te", "తెలుగు · Telugu"],
  ["gu", "ગુજરાતી · Gujarati"],
  ["kn", "ಕನ್ನಡ · Kannada"],
  ["ml", "മലയാളം · Malayalam"],
  ["or", "ଓଡ଼ିଆ · Odia"],
  ["pa", "ਪੰਜਾਬੀ · Punjabi"],
];

export default function Register() {
  const { register } = useAuth();
  const router = useRouter();
  const [role, setRole] = useState<"candidate" | "assessor">("candidate");
  const [quals, setQuals] = useState<Qualification[]>([]);
  const [form, setForm] = useState({ full_name: "", email: "", password: "", preferred_language: "hi", qualification_id: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api
      .get<Qualification[]>("/qualifications")
      .then((q) => {
        setQuals(q);
        if (q[0]) setForm((f) => ({ ...f, qualification_id: String(q[0].id) }));
      })
      .catch(setError);
  }, []);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await register({
        role,
        full_name: form.full_name,
        email: form.email,
        password: form.password,
        ...(role === "candidate" ? { preferred_language: form.preferred_language, qualification_id: Number(form.qualification_id) || null } : {}),
      });
      router.push(homeFor(u.role));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-dvh flex items-center justify-center p-6">
      <div className="w-full max-w-lg">
        <Brand />
        <h1 className="mt-8 text-2xl font-bold text-navy-900">Create an account</h1>
        <p className="mt-1 text-muted">Administrator accounts are issued by the assessment agency and can&apos;t be self-registered.</p>

        <div className="mt-6 grid grid-cols-2 gap-2 rounded-xl bg-cream-200 p-1" role="tablist">
          {(["candidate", "assessor"] as const).map((r) => (
            <button
              key={r}
              role="tab"
              aria-selected={role === r}
              onClick={() => setRole(r)}
              className={cx("h-11 rounded-lg font-semibold capitalize transition", role === r ? "bg-white text-navy-900 shadow-sm" : "text-navy-600")}
            >
              {r}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="mt-6 grid gap-4">
          <Field label="Full name">
            <input className={inputCls} required minLength={2} value={form.full_name} onChange={set("full_name")} />
          </Field>
          <Field label="Email">
            <input className={inputCls} type="email" required value={form.email} onChange={set("email")} autoComplete="username" />
          </Field>
          <Field label="Password" hint="At least 8 characters.">
            <input className={inputCls} type="password" required minLength={8} value={form.password} onChange={set("password")} autoComplete="new-password" />
          </Field>
          {role === "candidate" && (
            <>
              <Field label="Qualification">
                <select className={inputCls} value={form.qualification_id} onChange={set("qualification_id")} required>
                  {quals.map((q) => (
                    <option key={q.id} value={q.id}>
                      {q.title} · NSQF {q.nsqf_level} · {q.nqr_code}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Preferred language" hint="Used for speech-to-text and interface labels.">
                <select className={inputCls} value={form.preferred_language} onChange={set("preferred_language")}>
                  {LANGS.map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
              </Field>
            </>
          )}
          {error != null && <ErrorBox error={error} />}
          <Button type="submit" size="lg" loading={busy}>
            Create {role} account
          </Button>
        </form>
        <p className="mt-4 text-sm text-muted">
          Already registered?{" "}
          <Link href="/login" className="font-semibold text-navy-900 hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
