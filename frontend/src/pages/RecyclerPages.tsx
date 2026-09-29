import { FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { ApiError, api, inr, wsBase } from "../lib/api";
import { compressImage } from "../lib/compress";
import { useAuth } from "../auth/AuthContext";
import { Badge, Btn, Card, Field, inputClass, States, useToast, VerifiedMark } from "../components/Bits";

function errText(t: (k: string) => string, error: unknown) {
  return error instanceof ApiError ? t(`errors.${error.code}`) : t("common.error");
}

export function RecyclerDashboard() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [pickups, setPickups] = useState<Record<string, string>[]>([]);
  const [me, setMe] = useState<Record<string, unknown> | null>(null);
  useEffect(() => {
    void api<Record<string, string>[]>("/api/pickups").then(setPickups);
    void api<Record<string, unknown>>("/api/recyclers/me").then(setMe);
  }, []);
  if (user?.profile?.status === "pending") return <Card><Badge tone="pending">{t("common.pending")}</Badge><p className="mt-2">{t("auth.pendingNote")}</p></Card>;
  const reliability = (me?.reliability as { score?: number }) || {};
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <Card><p className="text-xs text-muted">{t("nav.pickups")}</p><p className="text-3xl font-extrabold">{pickups.length}</p></Card>
      <Card><p className="text-xs text-muted">{t("recyclers.reliability")}</p><p className="text-3xl font-extrabold">{reliability.score ?? user?.profile?.reliability_score ?? "—"}</p></Card>
      <Card><VerifiedMark /><p className="mt-2 text-sm">{user?.profile?.business_name}</p><p className="text-sm">{user?.profile?.availability}</p></Card>
    </div>
  );
}

export function RecyclerPickups() {
  const { t } = useTranslation();
  const toast = useToast();
  const [rows, setRows] = useState<Record<string, string>[]>([]);
  const [status, setStatus] = useState("available");
  const [slot, setSlot] = useState("");
  async function load() { setRows(await api("/api/pickups")); }
  useEffect(() => { void load(); }, []);
  useEffect(() => {
    const socket = new WebSocket(`${wsBase()}/api/ws/availability`);
    socket.onmessage = () => void load();
    const timer = window.setInterval(() => void load(), 8000);
    return () => { socket.close(); window.clearInterval(timer); };
  }, []);
  return (
    <div className="space-y-4">
      <Card title={t("pickups.setStatus")}>
        <div className="flex flex-wrap gap-2">
          <select className={inputClass} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="available">{t("common.available")}</option>
            <option value="busy">{t("common.busy")}</option>
            <option value="offline">{t("common.offline")}</option>
          </select>
          <input className={inputClass} value={slot} onChange={(e) => setSlot(e.target.value)} placeholder={t("pickups.when")} />
          <Btn onClick={() => void api("/api/recyclers/me/availability", { method: "PATCH", body: JSON.stringify({ status, next_slot: slot }) }).then(() => toast(t("common.save")))}>{t("common.save")}</Btn>
        </div>
      </Card>
      <Card title={t("pickups.calendar")}>
        {rows.length === 0 ? <States empty /> : rows.map((row) => (
          <div key={row.id} className="flex flex-wrap items-center justify-between gap-2 border-t border-line py-3 text-sm">
            <div><Link className="font-bold text-brand" to={`/recycler/lots/${row.lot_id}`}>{row.lot_id}</Link><div>{row.material} · {row.weight_kg} kg · {row.scheduled_at}</div></div>
            <Badge>{row.status}</Badge>
            {row.status === "requested" ? (
              <div className="flex gap-2">
                <Btn onClick={() => void api(`/api/pickups/${row.id}`, { method: "PATCH", body: JSON.stringify({ status: "accepted" }) }).then(load)}>{t("pickups.accept")}</Btn>
                <Btn kind="danger" onClick={() => void api(`/api/pickups/${row.id}`, { method: "PATCH", body: JSON.stringify({ status: "rejected" }) }).then(load)}>{t("pickups.reject")}</Btn>
              </div>
            ) : null}
          </div>
        ))}
      </Card>
    </div>
  );
}

export function OffersPage() {
  const { t } = useTranslation();
  const toast = useToast();
  const [material, setMaterial] = useState("PCB");
  const [price, setPrice] = useState("400");
  return (
    <Card title={t("nav.offers")}>
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); void api("/api/recyclers/me/offers", { method: "PUT", body: JSON.stringify({ material_code: material, price_per_kg: Number(price) }) }).then(() => toast(t("common.save"))); }}>
        <Field label={t("lots.material")}><input className={inputClass} value={material} onChange={(e) => setMaterial(e.target.value)} /></Field>
        <Field label={t("recyclers.offer")}><input className={inputClass} value={price} onChange={(e) => setPrice(e.target.value)} /></Field>
        <Btn type="submit">{t("common.save")}</Btn>
      </form>
    </Card>
  );
}

export function RecyclerLot() {
  const { id = "" } = useParams();
  const { t } = useTranslation();
  const toast = useToast();
  const [lot, setLot] = useState<Record<string, unknown> | null>(null);
  const [weight, setWeight] = useState("");
  const [pay, setPay] = useState({ amount: "", mode: "cash", reference: "" });
  const [error, setError] = useState("");
  async function load() {
    try { setLot(await api(`/api/lots/${id}`)); } catch (err) { setError(errText(t, err)); }
  }
  useEffect(() => { void load(); }, [id]);
  async function confirm(file?: File) {
    const position = await new Promise<GeolocationPosition>((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: false, timeout: 8000 })).catch(() => null);
    const body = new FormData();
    body.append("weight_kg", weight);
    body.append("lat", String(position?.coords.latitude ?? lot?.lat ?? 17.4));
    body.append("lng", String(position?.coords.longitude ?? lot?.lng ?? 78.4));
    body.append("captured_at", new Date().toISOString());
    if (file) body.append("file", await compressImage(file), "handover.webp");
    await api(`/api/handovers/${id}/recycler`, { method: "POST", body });
    toast(t("lots.handover"));
    await load();
  }
  async function payment(event: FormEvent) {
    event.preventDefault();
    const txs = await api<{ public_id: string; lot_id: string }[]>("/api/transactions");
    const tx = txs.find((row) => row.lot_id === id);
    if (!tx) return;
    await api(`/api/transactions/${tx.public_id}/pay`, { method: "POST", body: JSON.stringify({ amount: Number(pay.amount), mode: pay.mode, reference: pay.reference }) });
    toast(t("tx.pay"));
  }
  if (!lot) return <States loading={!error} error={error} />;
  return (
    <div className="space-y-4">
      <Card title={String(lot.public_id)}>
        <p>{String(lot.material)} · {String(lot.weight_kg)} kg · {String(lot.status)}</p>
        <p className="text-sm">{String(lot.collector_name || "")}</p>
      </Card>
      <Card title={t("lots.handover")}>
        <Field label={t("lots.weightVerified")}><input className={inputClass} value={weight} onChange={(e) => setWeight(e.target.value)} /></Field>
        <input className={`${inputClass} mt-2`} type="file" accept="image/*" capture="environment" onChange={(e) => e.target.files?.[0] && void confirm(e.target.files[0]).catch((err) => setError(errText(t, err)))} />
        <Btn className="mt-2" onClick={() => void confirm().catch((err) => setError(errText(t, err)))}>{t("lots.handover")}</Btn>
      </Card>
      <Card title={t("tx.pay")}>
        <form className="grid gap-2 sm:grid-cols-3" onSubmit={payment}>
          <input className={inputClass} value={pay.amount} onChange={(e) => setPay({ ...pay, amount: e.target.value })} placeholder={t("tx.amount")} />
          <select className={inputClass} value={pay.mode} onChange={(e) => setPay({ ...pay, mode: e.target.value })}><option value="cash">{t("tx.cash")}</option><option value="upi">{t("tx.upi")}</option><option value="bank">{t("tx.bank")}</option></select>
          <input className={inputClass} value={pay.reference} onChange={(e) => setPay({ ...pay, reference: e.target.value })} placeholder={t("tx.reference")} />
          <Btn type="submit">{t("tx.pay")}</Btn>
        </form>
      </Card>
      <Btn kind="secondary" onClick={() => void api(`/api/handovers/${id}/processing`, { method: "POST" }).then(() => toast(t("lots.processing")))}>{t("lots.processing")}</Btn>
      <States error={error} />
    </div>
  );
}

export function PaymentsPage() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<{ public_id: string; lot_id: string; amount: number; paid_amount: number; pending_amount: number; status: string }[]>([]);
  useEffect(() => { void api<typeof rows>("/api/transactions").then(setRows); }, []);
  const pending = rows.filter((row) => row.status !== "paid");
  return (
    <Card title={t("dashboard.pendingPay")}>
      {pending.length === 0 ? <States empty /> : pending.map((row) => <p key={row.public_id} className="border-t border-line py-2 text-sm">{row.public_id} · {row.lot_id} · {inr(row.pending_amount)} <Badge tone="pending">{row.status}</Badge></p>)}
    </Card>
  );
}

export function RatingsPage() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<{ stars: number; comment: string; at: string }[]>([]);
  useEffect(() => { void api<typeof rows>("/api/ratings/me").then(setRows); }, []);
  return <Card title={t("nav.ratings")}>{rows.length === 0 ? <States empty /> : rows.map((row) => <p key={row.at}>{"★".repeat(row.stars)} {row.comment}</p>)}</Card>;
}

export function RecyclerAnalytics() {
  const { t } = useTranslation();
  const [history, setHistory] = useState<{ history: { lot_id: string; pickup_status: string; lot_status: string }[]; reliability: { score: number; factors: Record<string, number> } } | null>(null);
  const { user } = useAuth();
  useEffect(() => { if (user) void api<NonNullable<typeof history>>(`/api/recyclers/${user.id}/history`).then(setHistory); }, [user]);
  if (!history) return <States loading />;
  const chart = Object.entries(history.reliability.factors).map(([name, value]) => ({ name, value }));
  return (
    <div className="space-y-4">
      <Card title={t("recyclers.reliability")}><p className="text-3xl font-extrabold">{history.reliability.score}</p><div className="h-48"><ResponsiveContainer width="100%" height="100%"><BarChart data={chart}><XAxis dataKey="name" /><YAxis /><Bar dataKey="value" fill="#176b52" /></BarChart></ResponsiveContainer></div></Card>
      <Card title={t("recyclers.history")}>{history.history.map((row) => <p key={row.lot_id} className="text-sm">{row.lot_id} · {row.pickup_status} · {row.lot_status}</p>)}</Card>
    </div>
  );
}

export function RecyclerProfilePage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  return (
    <Card title={t("nav.profile")}>
      <p className="font-bold">{user?.profile?.business_name}</p>
      <p>{user?.profile?.licence_number}</p>
      <p>{user?.profile?.address}</p>
      <Badge tone={user?.profile?.status === "approved" ? "ok" : "pending"}>{user?.profile?.status}</Badge>
      {user?.profile?.rejection_reason ? <p className="mt-2 text-sm">{user.profile.rejection_reason}</p> : null}
      {user?.profile?.status === "approved" ? <VerifiedMark /> : null}
    </Card>
  );
}
