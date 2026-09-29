import { FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { ApiError, API_URL, api, inr } from "../lib/api";
import { Badge, Btn, Card, Field, inputClass, States, useToast } from "../components/Bits";

function errText(t: (k: string) => string, error: unknown) {
  return error instanceof ApiError ? t(`errors.${error.code}`) : t("common.error");
}

export function AdminDashboard() {
  const { t } = useTranslation();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  useEffect(() => { void api<Record<string, unknown>>("/api/admin/summary").then(setData); }, []);
  if (!data) return <States loading />;
  const impact = data.impact as { weight_kg: number; co2_kg: number };
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Card><p className="text-xs text-muted">{t("dashboard.collectors")}</p><p className="text-3xl font-extrabold">{String(data.collectors)}</p></Card>
      <Card><p className="text-xs text-muted">{t("dashboard.recyclers")}</p><p className="text-3xl font-extrabold">{String(data.recyclers)}</p><p className="text-xs">{t("common.pending")} {String(data.pending_recyclers)}</p></Card>
      <Card><p className="text-xs text-muted">{t("dashboard.lots")}</p><p className="text-3xl font-extrabold">{String(data.lots)}</p></Card>
      <Card><p className="text-xs text-muted">{t("dashboard.co2")}</p><p className="text-3xl font-extrabold">{impact.co2_kg.toFixed(1)} kg</p><p className="text-xs">{impact.weight_kg} kg</p></Card>
    </div>
  );
}

export function VerificationPage() {
  const { t } = useTranslation();
  const toast = useToast();
  const [rows, setRows] = useState<{ user_id: string; business_name: string; licence_number: string; phone: string; materials: string[]; documents: { path: string }[]; status: string }[]>([]);
  const [reason, setReason] = useState("");
  async function load() { setRows(await api("/api/admin/recyclers?status=pending")); }
  useEffect(() => { void load(); }, []);
  async function decide(id: string, decision: "approved" | "rejected") {
    try {
      await api(`/api/admin/recyclers/${id}/decision`, { method: "POST", body: JSON.stringify({ decision, reason }) });
      toast(decision);
      await load();
    } catch (error) {
      toast(errText(t, error));
    }
  }
  return (
    <div className="space-y-3">
      <Field label={t("admin.reason")}><input className={inputClass} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
      {rows.length === 0 ? <States empty /> : rows.map((row) => (
        <Card key={row.user_id}>
          <b>{row.business_name}</b> <Badge tone="pending">{row.status}</Badge>
          <p className="text-sm">{row.licence_number} · {row.phone}</p>
          <p className="text-sm">{row.materials.join(", ")}</p>
          <div className="mt-2 flex flex-wrap gap-2">{row.documents.map((doc) => <a key={doc.path} className="text-sm font-bold text-brand" href={`${API_URL}/api/files/${doc.path}`} target="_blank">{t("admin.documents")}</a>)}</div>
          <div className="mt-3 flex gap-2">
            <Btn data-testid="approve-recycler" onClick={() => void decide(row.user_id, "approved")}>{t("admin.approve")}</Btn>
            <Btn kind="danger" onClick={() => void decide(row.user_id, "rejected")}>{t("admin.reject")}</Btn>
          </div>
        </Card>
      ))}
    </div>
  );
}

export function UsersPage() {
  const { t } = useTranslation();
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<{ id: string; name: string; phone: string; role: string; active: boolean; language: string; lots?: number; earnings?: number; area?: string }[]>([]);
  async function load() {
    const collectors = await api<typeof rows>(`/api/collectors?q=${encodeURIComponent(q)}`);
    const users = await api<typeof rows>("/api/admin/users");
    const merged = users
      .map((user) => ({ ...user, ...collectors.find((c) => c.id === user.id) }))
      .filter((user) => !q || `${user.name} ${user.phone}`.toLowerCase().includes(q.toLowerCase()));
    setRows(merged);
  }
  useEffect(() => { void load(); }, [q]);
  return (
    <Card title={t("nav.users")}>
      <input className={inputClass} placeholder={t("common.search")} value={q} onChange={(e) => setQ(e.target.value)} />
      <table className="mt-3 w-full text-left text-sm">
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-t border-line">
              <td className="py-2">{row.name}<div className="text-xs text-muted">{row.phone} · {row.language} · {row.area || row.role}</div></td>
              <td>{row.lots ?? ""}</td>
              <td>{row.earnings !== undefined ? inr(row.earnings) : ""}</td>
              <td><Badge tone={row.active ? "ok" : "danger"}>{row.active ? t("admin.active") : t("common.offline")}</Badge></td>
              <td><Btn kind="secondary" onClick={() => void api(`/api/admin/users/${row.id}`, { method: "PATCH", body: JSON.stringify({ is_active: !row.active }) }).then(load)}>{row.active ? t("admin.deactivate") : t("admin.activate")}</Btn></td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

export function AdminPrices() {
  const { t } = useTranslation();
  const toast = useToast();
  const [rows, setRows] = useState<{ id: string; material: string; price_per_kg: number; source: string; market: string; recorded_on: string }[]>([]);
  const [form, setForm] = useState({ material_code: "PCB", price_per_kg: "100", source: "Manual board", market: "Hyderabad", recorded_on: new Date().toISOString().slice(0, 10) });
  async function load() { setRows(await api("/api/prices/admin")); }
  useEffect(() => { void load(); }, []);
  async function save(event: FormEvent) {
    event.preventDefault();
    await api("/api/prices/admin", { method: "POST", body: JSON.stringify({ ...form, price_per_kg: Number(form.price_per_kg) }) });
    toast(t("common.save"));
    await load();
  }
  return (
    <div className="space-y-4">
      <Card title={t("prices.add")}>
        <form className="grid gap-2 sm:grid-cols-2" onSubmit={save}>
          <input className={inputClass} value={form.material_code} onChange={(e) => setForm({ ...form, material_code: e.target.value })} />
          <input className={inputClass} value={form.price_per_kg} onChange={(e) => setForm({ ...form, price_per_kg: e.target.value })} />
          <input className={inputClass} value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} />
          <input className={inputClass} value={form.market} onChange={(e) => setForm({ ...form, market: e.target.value })} />
          <input className={inputClass} type="date" value={form.recorded_on} onChange={(e) => setForm({ ...form, recorded_on: e.target.value })} />
          <Btn type="submit">{t("common.save")}</Btn>
        </form>
      </Card>
      <Card>
        {rows.slice(0, 30).map((row) => (
          <div key={row.id} className="flex items-center justify-between border-t border-line py-2 text-sm">
            <span>{row.material} · {row.market} · {inr(row.price_per_kg)} · {row.recorded_on}</span>
            <Btn kind="danger" onClick={() => void api(`/api/prices/admin/${row.id}`, { method: "DELETE" }).then(load)}>{t("admin.reject")}</Btn>
          </div>
        ))}
      </Card>
    </div>
  );
}

export function DisputesPage() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<{ id: string; lot_id: string; reason: string; status: string; evidence: { path: string }[] }[]>([]);
  const [resolution, setResolution] = useState("");
  async function load() { setRows(await api("/api/admin/disputes")); }
  useEffect(() => { void load(); }, []);
  return (
    <div className="space-y-3">
      <Field label={t("admin.reason")}><input className={inputClass} value={resolution} onChange={(e) => setResolution(e.target.value)} /></Field>
      {rows.map((row) => (
        <Card key={row.id}>
          <b>{row.lot_id}</b> <Badge tone={row.status === "open" ? "pending" : "ok"}>{row.status}</Badge>
          <p className="text-sm">{row.reason}</p>
          {row.evidence.map((file) => <a key={file.path} className="text-sm text-brand" href={`${API_URL}/api/files/${file.path}`}>{t("lots.evidence")}</a>)}
          <div className="mt-2 flex gap-2">
            <Btn onClick={() => void api(`/api/admin/disputes/${row.id}/resolve`, { method: "POST", body: JSON.stringify({ status: "resolved", resolution }) }).then(load)}>{t("admin.resolve")}</Btn>
            <Btn kind="secondary" onClick={() => void api(`/api/admin/disputes/${row.id}/resolve`, { method: "POST", body: JSON.stringify({ status: "rejected", resolution }) }).then(load)}>{t("admin.rejectDispute")}</Btn>
          </div>
        </Card>
      ))}
    </div>
  );
}

export function AuditPage() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<{ id: string; action: string; entity_id: string; at: string }[]>([]);
  useEffect(() => { void api<typeof rows>("/api/admin/audit").then(setRows); }, []);
  return <Card title={t("nav.audit")}>{rows.length === 0 ? <States empty /> : rows.map((row) => <p key={row.id} className="text-sm">{row.at} · {row.action} · {row.entity_id}</p>)}</Card>;
}

export function SyncPage() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<{ id: string; key: string; status: string; entity: string; error: string; at: string }[]>([]);
  useEffect(() => { void api<typeof rows>("/api/admin/sync").then(setRows); }, []);
  return <Card title={t("nav.sync")}>{rows.length === 0 ? <States empty /> : rows.map((row) => <p key={row.id} className="text-sm">{row.at} · {row.entity} · {row.status} · {row.key} {row.error}</p>)}</Card>;
}

export function AdminAnalytics() {
  const { t } = useTranslation();
  const [data, setData] = useState<{ lots_by_status: Record<string, number>; impact: { weight_kg: number; co2_kg: number; by_material: Record<string, { weight_kg: number }> } } | null>(null);
  useEffect(() => { void api<NonNullable<typeof data>>("/api/admin/analytics").then(setData); }, []);
  if (!data) return <States loading />;
  const chart = Object.entries(data.lots_by_status).map(([name, value]) => ({ name, value }));
  return (
    <div className="space-y-4">
      <Card title={t("nav.analytics")}><div className="h-56"><ResponsiveContainer width="100%" height="100%"><BarChart data={chart}><XAxis dataKey="name" /><YAxis /><Bar dataKey="value" fill="#22956f" /></BarChart></ResponsiveContainer></div></Card>
      <Card title={t("dashboard.impact")}>
        <p>{data.impact.weight_kg} kg · {data.impact.co2_kg.toFixed(1)} kg CO₂</p>
        {Object.entries(data.impact.by_material).map(([code, row]) => <p key={code} className="text-sm">{code}: {row.weight_kg} kg</p>)}
      </Card>
    </div>
  );
}
