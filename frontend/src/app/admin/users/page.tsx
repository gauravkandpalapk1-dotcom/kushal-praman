"use client";

import { useState } from "react";
import { UserPlus } from "lucide-react";
import { AppShell } from "@/components/shell";
import { Badge, Button, Card, cx, ErrorBox, Field, inputCls, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import type { Role, User } from "@/lib/types";

export default function AdminUsers() {
  const me = useRequireRole(["admin"]);
  const [role, setRole] = useState<"" | Role>("");
  const users = useApi<User[]>(me ? `/admin/users${role ? `?role=${role}` : ""}` : null);
  const [form, setForm] = useState({ full_name: "", email: "", password: "", role: "assessor", assessor_code: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  if (!me) return <Loading />;

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/admin/users", { ...form, assessor_code: form.role === "assessor" ? form.assessor_code || null : undefined });
      setForm({ full_name: "", email: "", password: "", role: "assessor", assessor_code: "" });
      users.reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function toggle(u: User) {
    try {
      await api.patch(`/admin/users/${u.id}`, { is_active: !u.is_active });
      users.reload();
    } catch (err) {
      setError(err);
    }
  }

  return (
    <AppShell>
      <PageHeader eyebrow="Administration" title="Assessors & candidates" sub="Create assessor accounts and deactivate access. Every change is audited." />
      <div className="grid gap-5 lg:grid-cols-[2fr_1fr]">
        <Card className="overflow-x-auto">
          <div className="flex flex-wrap gap-1 p-3">
            {(["", "assessor", "candidate", "admin"] as const).map((r) => (
              <button key={r} onClick={() => setRole(r)} className={cx("rounded-md px-3 py-1.5 text-sm font-semibold capitalize", role === r ? "bg-navy-900 text-cream-50" : "text-navy-700 hover:bg-navy-900/5")}>
                {r || "All"}
              </button>
            ))}
          </div>
          {users.loading && !users.data && <Loading />}
          <table className="w-full min-w-[620px] text-sm">
            <tbody className="divide-y divide-navy-900/6">
              {users.data?.map((u) => (
                <tr key={u.id}>
                  <td className="px-4 py-3">
                    <div className="font-semibold text-navy-900">{u.full_name}</div>
                    <div className="text-xs text-muted">{u.email}</div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={u.role === "admin" ? "dark" : u.role === "assessor" ? "info" : "neutral"} className="capitalize">
                      {u.role}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-xs text-muted">{u.assessor?.assessor_code ?? u.candidate?.candidate_code ?? ""}</td>
                  <td className="px-4 py-3">
                    <Badge tone={u.is_active ? "ok" : "bad"}>{u.is_active ? "active" : "inactive"}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {u.id !== me.id && (
                      <Button size="sm" variant="ghost" onClick={() => toggle(u)}>
                        {u.is_active ? "Deactivate" : "Activate"}
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <Card className="p-5 content-start">
          <h2 className="flex items-center gap-2 font-bold text-navy-900">
            <UserPlus className="size-5 text-amber-600" /> Add user
          </h2>
          <form onSubmit={create} className="mt-4 grid gap-3">
            <Field label="Role">
              <select className={inputCls} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                <option value="assessor">Assessor</option>
                <option value="candidate">Candidate</option>
                <option value="admin">Admin</option>
              </select>
            </Field>
            <Field label="Full name">
              <input className={inputCls} required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
            </Field>
            <Field label="Email">
              <input className={inputCls} type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </Field>
            <Field label="Temporary password" hint="At least 8 characters. Share it securely, never over chat.">
              <input className={inputCls} type="password" minLength={8} required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} autoComplete="new-password" />
            </Field>
            {form.role === "assessor" && (
              <Field label="Assessor code" hint="e.g. A-21">
                <input className={inputCls} value={form.assessor_code} onChange={(e) => setForm({ ...form, assessor_code: e.target.value })} />
              </Field>
            )}
            {error != null && <ErrorBox error={error} />}
            <Button type="submit" loading={busy}>
              Create user
            </Button>
          </form>
        </Card>
      </div>
    </AppShell>
  );
}
