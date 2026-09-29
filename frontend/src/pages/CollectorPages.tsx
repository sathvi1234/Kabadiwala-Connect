import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import QRCode from "qrcode";
import { jsPDF } from "jspdf";
import { ApiError, api, inr } from "../lib/api";
import { compressImage, blobToBase64 } from "../lib/compress";
import { listen, speak } from "../lib/speech";
import { cachePrices, cachedPrice, enqueueLot } from "../sync/engine";
import { estimateFromCache } from "../sync/logic";
import { useAuth } from "../auth/AuthContext";
import { useToast, Badge, Btn, Card, Field, inputClass, MapPanel, States, VerifiedMark } from "../components/Bits";

type Material = { code: string; name: Record<string, string> };
type Lot = {
  id: string;
  public_id: string;
  material: string;
  weight_kg: number;
  status: string;
  estimated_value: number;
  price_per_kg: number;
  price_source: string;
  price_date: string;
  price_market: string;
  flags: Record<string, boolean | number | null>;
  duplicate_of?: string | null;
  duplicate_score?: number | null;
  duplicate_status?: string;
  ai_material?: string | null;
  ai_confidence?: number | null;
  condition?: string | null;
  events: { type: string; note: string; at: string; actor_role?: string }[];
  photos: { path: string; kind: string }[];
  city: string;
  lat?: number | null;
  lng?: number | null;
};

function useErr() {
  const { t } = useTranslation();
  return (error: unknown) => (error instanceof ApiError ? t(`errors.${error.code}`, { defaultValue: t("common.error") }) : t("common.error"));
}

export function CollectorDashboard() {
  const { t } = useTranslation();
  const [stats, setStats] = useState<Record<string, number | Record<string, number>> | null>(null);
  const [lots, setLots] = useState<Lot[]>([]);
  const [board, setBoard] = useState<{ material: string; price_per_kg: number }[]>([]);
  const [error, setError] = useState("");
  const message = useErr();
  useEffect(() => {
    Promise.all([api<Record<string, never>>("/api/collectors/me/stats"), api<Lot[]>("/api/lots"), api<{ items: { material: string; price_per_kg: number }[] }>("/api/prices/board")])
      .then(([s, l, b]) => {
        setStats(s as never);
        setLots(l.slice(0, 4));
        setBoard(b.items.slice(0, 4));
      })
      .catch((err) => setError(message(err)));
  }, []);
  return (
    <div className="space-y-4">
      <States error={error} loading={!stats && !error} />
      {stats ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Card><p className="text-xs text-muted">{t("dashboard.lots")}</p><p className="text-2xl font-extrabold">{String(stats.lots)}</p></Card>
          <Card><p className="text-xs text-muted">{t("dashboard.earnings")}</p><p className="text-2xl font-extrabold">{inr(Number(stats.earned))}</p></Card>
          <Card><p className="text-xs text-muted">{t("dashboard.pendingPay")}</p><p className="text-2xl font-extrabold">{inr(Number(stats.pending))}</p></Card>
          <Card><p className="text-xs text-muted">{t("dashboard.co2")}</p><p className="text-2xl font-extrabold">{Number((stats.impact as { co2_kg?: number })?.co2_kg || 0).toFixed(1)} kg</p></Card>
        </div>
      ) : null}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={t("dashboard.trace")}>
          {lots.length === 0 ? <States empty /> : lots.map((lot) => <p key={lot.id} className="border-l-2 border-brand py-2 pl-3 text-sm"><b>{lot.public_id}</b> · {lot.material} · {lot.weight_kg} kg · {lot.status}</p>)}
        </Card>
        <Card title={t("dashboard.board")}>
          {board.map((row) => <p key={row.material} className="text-sm">{row.material} <b>{inr(row.price_per_kg)}/kg</b></p>)}
          <Link className="mt-3 inline-block font-bold text-brand" to="/collector/prices">{t("prices.title")}</Link>
        </Card>
      </div>
    </div>
  );
}

export function LotsPage() {
  const { t, i18n } = useTranslation();
  const toast = useToast();
  const { user } = useAuth();
  const message = useErr();
  const [materials, setMaterials] = useState<Material[]>([]);
  const [lots, setLots] = useState<Lot[]>([]);
  const [material, setMaterial] = useState("PCB");
  const [weight, setWeight] = useState("10");
  const [unit, setUnit] = useState("kg");
  const [gps, setGps] = useState<{ lat: number; lng: number } | null>(null);
  const [photo, setPhoto] = useState<Blob | null>(null);
  const [preview, setPreview] = useState("");
  const [suggestion, setSuggestion] = useState("");
  const [quote, setQuote] = useState<{ value: number; source: string; date: string; cached?: boolean; price_per_kg: number } | null>(null);
  const [created, setCreated] = useState<Lot | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const qrRef = useRef<HTMLCanvasElement>(null);
  const lowData = Boolean(user?.profile?.low_data_mode);
  const quality = user?.profile?.image_quality || (lowData ? 0.45 : 0.7);
  const maxBytes = lowData ? 80 * 1024 : 200 * 1024;

  async function load() {
    setLoading(true);
    try {
      const [mats, rows, board] = await Promise.all([
        api<Material[]>("/api/prices/materials"),
        api<Lot[]>("/api/lots"),
        api<{ city: string; items: { material: string; price_per_kg: number | null; source: string; date: string; market: string }[] }>("/api/prices/board"),
      ]);
      setMaterials(mats);
      setLots(rows);
      await cachePrices(board.city, board.items);
    } catch (err) {
      setError(message(err));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (created && qrRef.current) void QRCode.toCanvas(qrRef.current, created.public_id, { width: 140 });
  }, [created]);

  async function onFile(file: File) {
    const blob = await compressImage(file, maxBytes, quality);
    setPhoto(blob);
    setPreview(URL.createObjectURL(blob));
    if (!navigator.onLine) return;
    const body = new FormData();
    body.append("file", blob, "scrap.webp");
    const identified = await api<{ material: string; confidence: number }>("/ai/identify", { method: "POST", body });
    setSuggestion(`${identified.material} (${Math.round(identified.confidence * 100)}%)`);
    setMaterial(identified.material);
    const condition = await api<{ condition: string; note: string }>("/ai/condition", { method: "POST", body });
    toast(`${condition.condition}: ${condition.note}`);
  }

  async function estimate() {
    const kg = unit === "g" ? Number(weight) / 1000 : Number(weight);
    if (!navigator.onLine) {
      const cached = await cachedPrice(material, user?.profile?.city || "Hyderabad");
      if (!cached) return;
      setQuote({ value: estimateFromCache(kg, cached.price_per_kg), source: cached.source, date: cached.date, cached: true, price_per_kg: cached.price_per_kg });
      return;
    }
    const res = await api<{ value: number; source: string; date: string; price_per_kg: number }>("/api/lots/estimate", {
      method: "POST",
      body: JSON.stringify({ material_code: material, weight: Number(weight), unit, city: user?.profile?.city || "" }),
    });
    setQuote(res);
  }

  async function create() {
    setError("");
    const payload = {
      material_code: material,
      weight: Number(weight),
      unit,
      lat: gps?.lat,
      lng: gps?.lng,
      city: user?.profile?.city || "",
      captured_at: new Date().toISOString(),
      ai_material: suggestion.split(" ")[0] || undefined,
    };
    try {
      if (!navigator.onLine) {
        const photoBase64 = photo ? await blobToBase64(photo) : undefined;
        await enqueueLot(payload, photoBase64);
        toast(t("sync.savedOffline"));
        return;
      }
      const lot = await api<Lot>("/api/lots", { method: "POST", body: JSON.stringify({ ...payload, idempotency_key: crypto.randomUUID() }) });
      if (photo) {
        const body = new FormData();
        body.append("file", photo, "lot.webp");
        const updated = await api<Lot>(`/api/lots/${lot.public_id}/photos`, { method: "POST", body });
        setCreated(updated);
      } else setCreated(lot);
      toast(lot.public_id);
      await load();
    } catch (err) {
      if (photo) {
        await enqueueLot(payload, await blobToBase64(photo));
        toast(t("sync.savedOffline"));
        return;
      }
      setError(message(err));
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={t("lots.create")}>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("lots.material")}>
              <select className={inputClass} value={material} onChange={(e) => setMaterial(e.target.value)}>
                {materials.map((item) => <option key={item.code} value={item.code}>{item.name[i18n.language] || item.code}</option>)}
              </select>
            </Field>
            <Field label={t("lots.weight")}>
              <div className="flex gap-2">
                <input className={inputClass} type="number" min="0" value={weight} onChange={(e) => setWeight(e.target.value)} />
                <select className={inputClass} value={unit} onChange={(e) => setUnit(e.target.value)}><option value="kg">{t("common.kg")}</option><option value="g">{t("common.grams")}</option></select>
              </div>
            </Field>
            <Field label={t("lots.photo")}>
              <input className={inputClass} type="file" accept="image/*" capture="environment" onChange={(e) => e.target.files?.[0] && void onFile(e.target.files[0])} />
            </Field>
            <div className="flex items-end gap-2">
              <Btn kind="secondary" type="button" onClick={() => navigator.geolocation.getCurrentPosition((pos) => setGps({ lat: pos.coords.latitude, lng: pos.coords.longitude }))}>{t("auth.gps")}</Btn>
              <span className="text-xs text-muted">{gps ? `${gps.lat.toFixed(4)}, ${gps.lng.toFixed(4)}` : t("lots.noGps")}</span>
            </div>
          </div>
          {suggestion ? <p className="mt-3 text-sm">{t("lots.suggestion")}: <b>{suggestion}</b>. {t("lots.override")}</p> : null}
          {preview && !lowData ? <img src={preview} alt="" className="mt-3 max-h-32 rounded-lg" /> : null}
          {preview && lowData ? <p className="mt-3 text-xs text-muted">{t("lots.preview")}</p> : null}
          <div className="mt-3 flex flex-wrap gap-2">
            <Btn kind="secondary" type="button" onClick={() => void estimate()}>{t("lots.value")}</Btn>
            <Btn type="button" data-testid="create-lot" onClick={() => void create()}>{t("lots.create")}</Btn>
          </div>
          {quote ? <p className="mt-3 text-sm">{t("lots.value")}: <b>{inr(quote.value)}</b> · {quote.price_per_kg}/kg · {quote.source} · {quote.date} {quote.cached ? `(${t("lots.cached")})` : ""}</p> : null}
          <States error={error} />
        </Card>
        <Card title={t("lots.qr")}>
          {created ? <div className="flex items-center gap-4"><canvas ref={qrRef} /><div><b>{created.public_id}</b><p>{created.material} · {created.weight_kg} kg</p><p>{inr(created.estimated_value)}</p></div></div> : <States empty />}
        </Card>
      </div>
      <Card title={t("lots.recent")}>
        <States loading={loading} />
        <div className="overflow-auto">
          <table className="w-full text-left text-sm">
            <thead><tr className="text-muted"><th className="py-2">ID</th><th>{t("lots.material")}</th><th>{t("lots.weight")}</th><th>{t("lots.value")}</th><th>{t("lots.flags")}</th><th>{t("common.status")}</th></tr></thead>
            <tbody>
              {lots.map((lot) => (
                <tr key={lot.id} className="border-t border-line">
                  <td className="py-2"><Link className="font-bold text-brand" to={`/collector/lots/${lot.public_id}`}>{lot.public_id}</Link></td>
                  <td>{lot.material}</td><td>{lot.weight_kg}</td><td>{inr(lot.estimated_value)}</td>
                  <td>{lot.flags?.gps_present ? "GPS ✓" : "GPS ✗"} {lot.flags?.photo_present ? "Photo ✓" : "Photo ✗"} {lot.flags?.time_ok ? "Time ✓" : "Time ✗"}</td>
                  <td><Badge tone={lot.status === "completed" || lot.status === "paid" ? "ok" : "pending"}>{lot.status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

export function LotDetail() {
  const { id = "" } = useParams();
  const { t } = useTranslation();
  const toast = useToast();
  const message = useErr();
  const [lot, setLot] = useState<Lot | null>(null);
  const [offers, setOffers] = useState<{ recycler_id: string; business_name: string; price_per_kg: number | null; net_payout: number; best?: boolean; distance_km: number; reason: string }[]>([]);
  const [when, setWhen] = useState("");
  const [error, setError] = useState("");
  const qrRef = useRef<HTMLCanvasElement>(null);

  async function load() {
    try {
      const row = await api<Lot>(`/api/lots/${id}`);
      setLot(row);
      const comparison = await api<{ offers: typeof offers }>(`/api/lots/${id}/comparison`);
      setOffers(comparison.offers);
    } catch (err) {
      setError(message(err));
    }
  }
  useEffect(() => { void load(); }, [id]);
  useEffect(() => { if (lot && qrRef.current) void QRCode.toCanvas(qrRef.current, lot.public_id, { width: 120 }); }, [lot]);

  async function schedule(recyclerId: string) {
    try {
      await api("/api/pickups", { method: "POST", body: JSON.stringify({ lot_id: lot?.public_id, recycler_id: recyclerId, scheduled_at: when || new Date(Date.now() + 3600000).toISOString() }) });
      toast(t("lots.schedule"));
      await load();
    } catch (err) {
      setError(message(err));
    }
  }

  async function handover(file: File) {
    const position = await new Promise<GeolocationPosition>((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject));
    const body = new FormData();
    body.append("lat", String(position.coords.latitude));
    body.append("lng", String(position.coords.longitude));
    body.append("captured_at", new Date().toISOString());
    body.append("file", await compressImage(file), "handover.webp");
    await api(`/api/handovers/${lot?.public_id}/collector`, { method: "POST", body });
    toast(t("lots.handover"));
    await load();
  }

  async function dispute(reason: string, file?: File) {
    const body = new FormData();
    body.append("lot_id", lot?.public_id || "");
    body.append("reason", reason);
    if (file) body.append("file", file);
    await api("/api/disputes", { method: "POST", body });
    await load();
  }

  async function rate(stars: number, comment: string) {
    await api("/api/ratings", { method: "POST", body: JSON.stringify({ lot_id: lot?.public_id, stars, comment }) });
    toast(t("lots.rate"));
  }

  if (!lot) return <States loading={!error} error={error} />;
  return (
    <div className="space-y-4">
      <Card title={lot.public_id}>
        <div className="flex flex-wrap gap-4">
          <canvas ref={qrRef} />
          <div className="text-sm">
            <p>{lot.material} · {lot.weight_kg} kg · {inr(lot.estimated_value)}</p>
            <p>{t("lots.source")}: {lot.price_source} · {lot.price_date}</p>
            <p>{t("lots.flags")}: GPS {lot.flags.gps_present ? "✓" : "✗"} · Photo {lot.flags.photo_present ? "✓" : "✗"} · Time {lot.flags.time_ok ? "✓" : "✗"} {lot.flags.distance_suspicious ? "· distance !" : ""}</p>
            <Badge>{lot.status}</Badge>
          </div>
        </div>
        {lot.duplicate_status === "flagged" ? (
          <div className="mt-3 rounded-lg bg-[#fff3d9] p-3 text-sm">
            {t("lots.duplicate")} {lot.duplicate_of} ({lot.duplicate_score})
            <div className="mt-2 flex gap-2">
              <Btn onClick={() => void api(`/api/lots/${lot.public_id}/duplicate/confirm`, { method: "POST" }).then(load)}>{t("lots.confirmDup")}</Btn>
              <Btn kind="secondary" onClick={() => void api(`/api/lots/${lot.public_id}/duplicate/dismiss`, { method: "POST" }).then(load)}>{t("lots.dismissDup")}</Btn>
            </div>
          </div>
        ) : null}
      </Card>
      <Card title={t("lots.timeline")}>
        {lot.events.map((event) => <p key={event.at + event.type} className="border-l-2 border-brand py-2 pl-3 text-sm"><b>{event.type}</b> · {event.note} · {event.at}</p>)}
      </Card>
      <Card title={t("lots.compare")}>
        <Field label={t("pickups.when")}><input className={inputClass} type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} /></Field>
        <div className="mt-3 space-y-2">
          {offers.map((offer) => (
            <div key={offer.recycler_id} className={`rounded-xl border p-3 ${offer.best ? "border-brand bg-[#f0f7f4]" : "border-line"}`}>
              <b>{offer.business_name}</b> {offer.best ? <Badge>{t("lots.best")}</Badge> : null} <VerifiedMark />
              <p className="text-sm text-muted">{offer.distance_km} km · {inr(offer.price_per_kg)}/kg · {t("recyclers.reason")}: {offer.reason}</p>
              <p className="text-sm">{inr(offer.net_payout)}</p>
              <Btn className="mt-2" onClick={() => void schedule(offer.recycler_id)}>{t("lots.schedule")}</Btn>
            </div>
          ))}
          {offers.length === 0 ? <States empty /> : null}
        </div>
      </Card>
      <Card title={t("lots.handover")}>
        <input className={inputClass} type="file" accept="image/*" capture="environment" onChange={(e) => e.target.files?.[0] && void handover(e.target.files[0]).catch((err) => setError(message(err)))} />
      </Card>
      <Card title={t("lots.dispute")}>
        <DisputeForm onSubmit={dispute} />
      </Card>
      <Card title={t("lots.rate")}>
        <RateForm onSubmit={rate} />
      </Card>
      <States error={error} />
    </div>
  );
}

function DisputeForm({ onSubmit }: { onSubmit: (reason: string, file?: File) => Promise<void> }) {
  const { t } = useTranslation();
  const [reason, setReason] = useState("");
  const [file, setFile] = useState<File>();
  return (
    <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); void onSubmit(reason, file); }}>
      <textarea className={inputClass} value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t("lots.reason")} />
      <input type="file" onChange={(e) => setFile(e.target.files?.[0])} />
      <Btn type="submit">{t("lots.dispute")}</Btn>
    </form>
  );
}

function RateForm({ onSubmit }: { onSubmit: (stars: number, comment: string) => Promise<void> }) {
  const { t } = useTranslation();
  const [stars, setStars] = useState(5);
  const [comment, setComment] = useState("");
  return (
    <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); void onSubmit(stars, comment); }}>
      <select className={inputClass} value={stars} onChange={(e) => setStars(Number(e.target.value))}>{[1, 2, 3, 4, 5].map((n) => <option key={n}>{n}</option>)}</select>
      <input className={inputClass} value={comment} onChange={(e) => setComment(e.target.value)} placeholder={t("lots.comment")} />
      <Btn type="submit">{t("lots.rate")}</Btn>
    </form>
  );
}

export function PricesPage() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const [city, setCity] = useState(user?.profile?.city || "Hyderabad");
  const [material, setMaterial] = useState("Copper");
  const [range, setRange] = useState("30d");
  const [items, setItems] = useState<{ material: string; price_per_kg: number; change_pct: number; source: string; date: string }[]>([]);
  const [points, setPoints] = useState<{ date: string; price: number }[]>([]);
  const [forecast, setForecast] = useState<{ direction: string; forecast: { day: number; price: number }[] } | null>(null);
  const [error, setError] = useState("");
  const message = useErr();

  useEffect(() => {
    api<{ items: typeof items; city: string }>(`/api/prices/board?city=${encodeURIComponent(city)}`)
      .then(async (res) => {
        setItems(res.items as typeof items);
        await cachePrices(res.city, res.items as never);
      })
      .catch((err) => setError(message(err)));
  }, [city]);
  useEffect(() => {
    api<{ points: { date: string; price: number }[]; change_pct: number }>(`/api/prices/history?material=${material}&city=${encodeURIComponent(city)}&range=${range}`)
      .then((res) => setPoints(res.points))
      .catch((err) => setError(message(err)));
  }, [material, city, range]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <input className={inputClass} value={city} onChange={(e) => setCity(e.target.value)} aria-label={t("common.city")} />
        {["7d", "30d", "90d", "1y"].map((item) => <Btn key={item} kind={range === item ? "primary" : "secondary"} onClick={() => setRange(item)}>{t(`prices.${item === "7d" ? "d7" : item === "30d" ? "d30" : item === "90d" ? "d90" : "y1"}`)}</Btn>)}
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {items.map((item) => (
          <button key={item.material} className="text-left" onClick={() => setMaterial(item.material)}>
            <Card><p className="text-xs text-muted">{item.material}</p><p className="text-2xl font-extrabold">{inr(item.price_per_kg)}</p><p className="text-xs text-brand">{item.change_pct}%</p><p className="text-xs text-muted">{item.source} · {item.date}</p></Card>
          </button>
        ))}
      </div>
      <Card title={`${t("prices.trend")} · ${material}`}>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points}><CartesianGrid stroke="#e5e9f0" /><XAxis dataKey="date" hide /><YAxis /><Tooltip /><Line dataKey="price" stroke="#176b52" dot={false} /></LineChart>
          </ResponsiveContainer>
        </div>
        <Btn kind="secondary" className="mt-3" onClick={() => void api(`/ai/predict-price`, { method: "POST", body: JSON.stringify({ material_code: material, city }) }).then((res) => setForecast(res as never))}>{t("prices.predict")}</Btn>
        {forecast ? <p className="mt-2 text-sm">{t("prices.direction")}: {forecast.direction}. {forecast.forecast.map((p) => `${p.day}d ${inr(p.price)}`).join(" · ")}</p> : null}
      </Card>
      <States error={error} empty={!items.length && !error} />
      <p className="text-xs text-muted">{i18n.language}</p>
    </div>
  );
}

export function RecyclersPage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [material, setMaterial] = useState(user?.profile?.materials?.[0] || "PCB");
  const [maxKm, setMaxKm] = useState("25");
  const [availability, setAvailability] = useState("");
  const [rows, setRows] = useState<Record<string, never>[]>([]);
  const [error, setError] = useState("");
  const message = useErr();
  const lowData = Boolean(user?.profile?.low_data_mode);

  async function search() {
    const lat = user?.profile?.lat || 17.385;
    const lng = user?.profile?.lng || 78.4867;
    try {
      const data = await api<Record<string, never>[]>(`/api/recyclers/nearby?lat=${lat}&lng=${lng}&material=${material}&max_km=${maxKm}${availability ? `&availability=${availability}` : ""}`);
      setRows(data.filter((row) => (row as { verified?: boolean }).verified));
    } catch (err) {
      setError(message(err));
    }
  }
  useEffect(() => { void search(); }, [material, maxKm, availability]);

  return (
    <div className="space-y-4">
      <Card title={t("recyclers.nearby")}>
        <div className="mb-3 grid gap-2 sm:grid-cols-3">
          <input className={inputClass} value={material} onChange={(e) => setMaterial(e.target.value)} />
          <input className={inputClass} value={maxKm} onChange={(e) => setMaxKm(e.target.value)} aria-label={t("recyclers.distance")} />
          <select className={inputClass} value={availability} onChange={(e) => setAvailability(e.target.value)}>
            <option value="">{t("common.all")}</option>
            <option value="available">{t("common.available")}</option>
            <option value="busy">{t("common.busy")}</option>
          </select>
        </div>
        <MapPanel lowData={lowData} points={rows.map((row) => ({ lat: Number(row.lat), lng: Number(row.lng), label: String(row.business_name) }))} />
      </Card>
      {rows.map((row) => (
        <Card key={String(row.recycler_id)}>
          <div className="flex flex-wrap items-center gap-2"><b>{String(row.business_name)}</b><VerifiedMark /><Badge tone={row.availability === "available" ? "ok" : "pending"}>{String(row.availability)}</Badge></div>
          <p className="text-sm">{row.distance_km} km · {inr(Number(row.price_per_kg))}/kg · {t("recyclers.score")} {String(row.score)}</p>
          <p className="text-sm text-muted">{String(row.reason)}</p>
          <p className="text-xs">{t("recyclers.reliability")} {String(row.reliability_score)}</p>
        </Card>
      ))}
      <States error={error} empty={!rows.length && !error} />
    </div>
  );
}

export function PickupsPage() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<Record<string, string>[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { api<Record<string, string>[]>("/api/pickups").then(setRows).catch(() => setError(t("common.error"))); }, [t]);
  return (
    <Card title={t("nav.pickups")}>
      <States error={error} empty={!rows.length && !error} />
      <table className="w-full text-left text-sm">
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-t border-line">
              <td className="py-3">{row.lot_id}<div className="text-xs text-muted">{row.material} · {row.weight_kg} kg</div></td>
              <td>{row.recycler_name}<div className="text-xs">{row.availability}</div></td>
              <td>{row.scheduled_at}</td>
              <td><Badge tone={row.status === "accepted" ? "ok" : "pending"}>{row.status}</Badge></td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

export function TransactionsPage() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<Record<string, string | number>[]>([]);
  const [ledger, setLedger] = useState<{ balance: number; entries: { type: string; amount: number; balance_after: number; note: string }[] } | null>(null);
  const [earnings, setEarnings] = useState<{ period: string; amount: number }[]>([]);
  const [status, setStatus] = useState("");
  const [material, setMaterial] = useState("");
  const message = useErr();
  const [error, setError] = useState("");

  function query() {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (material) params.set("material", material);
    return params.toString();
  }
  useEffect(() => {
    Promise.all([
      api<typeof rows>(`/api/transactions?${query()}`),
      api<NonNullable<typeof ledger>>("/api/transactions/ledger"),
      api<{ series: { period: string; amount: number }[] }>("/api/collectors/me/earnings?bucket=month"),
    ]).then(([tx, led, earn]) => { setRows(tx); setLedger(led); setEarnings(earn.series); }).catch((err) => setError(message(err)));
  }, [status, material]);

  async function download(path: string, name: string) {
    const blob = await api<Blob>(path, { method: path.includes("receipt") ? "POST" : "GET" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    link.click();
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <Card><p className="text-xs text-muted">{t("tx.balance")}</p><p className="text-2xl font-extrabold">{inr(ledger?.balance || 0)}</p></Card>
        <Card><div className="h-28"><ResponsiveContainer width="100%" height="100%"><LineChart data={earnings}><Line dataKey="amount" stroke="#176b52" dot={false} /></LineChart></ResponsiveContainer></div></Card>
        <Card>
          <select className={inputClass} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">{t("common.all")}</option>
            <option value="pending">{t("tx.pending")}</option>
            <option value="partial">{t("tx.partial")}</option>
            <option value="paid">{t("tx.paid")}</option>
          </select>
          <input className={`${inputClass} mt-2`} placeholder={t("lots.material")} value={material} onChange={(e) => setMaterial(e.target.value)} />
          <Btn className="mt-2" kind="secondary" onClick={() => void download(`/api/transactions/export.csv?${query()}`, "transactions.csv")}>{t("tx.export")}</Btn>
        </Card>
      </div>
      <Card title={t("tx.ledger")}>
        {(ledger?.entries || []).map((entry, index) => <p key={index} className="text-sm">{entry.type === "credit" ? t("tx.credit") : t("tx.debit")} {inr(entry.amount)} · {entry.note} · {inr(entry.balance_after)}</p>)}
      </Card>
      <Card title={t("nav.transactions")}>
        <States error={error} empty={!rows.length && !error} />
        {rows.map((row) => (
          <div key={String(row.public_id)} className="flex flex-wrap items-center justify-between gap-2 border-t border-line py-3 text-sm">
            <div><b>{row.public_id}</b> · {row.lot_id} · {row.material}<div className="text-xs text-muted">{row.recycler_name} · {row.mode || ""}</div></div>
            <div>{inr(Number(row.paid_amount))} / {inr(Number(row.amount))} <Badge tone={row.status === "paid" ? "ok" : "pending"}>{String(row.status)}</Badge></div>
            <div className="flex gap-2">
              <Btn kind="secondary" onClick={() => void download(`/api/transactions/${row.public_id}/receipt`, `${row.public_id}.pdf`)}>{t("tx.receipt")}</Btn>
              <Btn kind="secondary" onClick={() => void download(`/api/transactions/${row.public_id}/certificate`, `${row.lot_id}.pdf`)}>{t("tx.certificate")}</Btn>
              <Btn kind="secondary" onClick={() => void offlineReceipt(row)}>{t("common.share")}</Btn>
            </div>
          </div>
        ))}
      </Card>
    </div>
  );
}

function offlineReceipt(row: Record<string, string | number>) {
  const doc = new jsPDF();
  doc.text(`Kabadiwala Connect`, 20, 20);
  doc.text(`${row.public_id} ${row.lot_id}`, 20, 30);
  doc.text(`${row.amount} ${row.status}`, 20, 40);
  doc.save(`${row.public_id}-local.pdf`);
}

export function AiPage() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const [result, setResult] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [material, setMaterial] = useState("PCB");
  const [quote, setQuote] = useState("100");
  const message = useErr();

  async function run(path: string, body?: BodyInit, json?: boolean) {
    try {
      const data = await api<unknown>(path, { method: "POST", body: json ? body : body });
      setResult(JSON.stringify(data, null, 2));
    } catch (err) {
      setResult(message(err));
    }
  }

  function imageBody() {
    const form = new FormData();
    if (file) form.append("file", file);
    return form;
  }

  return (
    <div className="space-y-4">
      <Card><p className="text-sm">{t("ai.note")}</p></Card>
      <input className={inputClass} type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] || null)} />
      <div className="grid gap-3 md:grid-cols-2">
        <Card title={t("ai.identify")}><Btn onClick={() => void run("/ai/identify", imageBody())}>{t("ai.run")}</Btn></Card>
        <Card title={t("ai.condition")}><Btn onClick={() => void run("/ai/condition", imageBody())}>{t("ai.run")}</Btn></Card>
        <Card title={t("ai.mixed")}><Btn onClick={() => void run("/ai/mixed-scrap", imageBody())}>{t("ai.run")}</Btn></Card>
        <Card title={t("ai.estimate")}><Btn onClick={() => void run("/ai/estimate-price", JSON.stringify({ material_code: material, weight: 10, city: user?.profile?.city || "Hyderabad" }), true)}>{t("ai.run")}</Btn></Card>
        <Card title={t("ai.recommend")}><Btn onClick={() => void run("/ai/recommend-recycler", JSON.stringify({ material_code: material, weight: 10, lat: user?.profile?.lat || 17.4, lng: user?.profile?.lng || 78.5 }), true)}>{t("ai.run")}</Btn></Card>
        <Card title={t("ai.predict")}><Btn onClick={() => void run("/ai/predict-price", JSON.stringify({ material_code: material, city: user?.profile?.city || "Hyderabad" }), true)}>{t("ai.run")}</Btn></Card>
        <Card title={t("ai.abnormal")}>
          <input className={inputClass} value={quote} onChange={(e) => setQuote(e.target.value)} />
          <Btn className="mt-2" onClick={() => void run("/ai/detect-abnormal-price", JSON.stringify({ material_code: material, price_per_kg: Number(quote) }), true)}>{t("ai.run")}</Btn>
        </Card>
        <Card title={t("ai.best")}><Btn onClick={() => void run("/ai/best-sale", JSON.stringify({ material_code: material, weight: 10, lat: user?.profile?.lat || 17.4, lng: user?.profile?.lng || 78.5 }), true)}>{t("ai.run")}</Btn></Card>
        <Card title={t("ai.reliability")}><Btn onClick={() => void api<{ recycler_id: string }[]>("/api/recyclers/nearby?lat=17.4&lng=78.5&material=PCB").then((rows) => api(`/ai/reliability/${rows[0]?.recycler_id || "x"}`)).then((data) => setResult(JSON.stringify(data, null, 2)))}>{t("ai.run")}</Btn></Card>
        <Card title={t("ai.earnings")}><Btn onClick={() => void run("/ai/earnings-predict", "{}", true)}>{t("ai.run")}</Btn></Card>
        <Card title={t("ai.voice")}>
          <Btn onClick={() => void listen(i18n.language).then(async (text) => {
            const data = await api<{ answer: string }>("/ai/voice", { method: "POST", body: JSON.stringify({ text, lang: i18n.language, lat: user?.profile?.lat, lng: user?.profile?.lng }) });
            setResult(data.answer);
            speak(data.answer, i18n.language);
          })}>{t("ai.listen")}</Btn>
        </Card>
        <Card title={t("ai.alerts")}>
          <Btn onClick={() => void run("/ai/price-alerts", JSON.stringify({ material_code: material, direction: "above", threshold: Number(quote), city: user?.profile?.city || "" }), true)}>{t("ai.run")}</Btn>
        </Card>
      </div>
      <label className="text-xs text-muted">{t("lots.material")}<input className={inputClass} value={material} onChange={(e) => setMaterial(e.target.value)} /></label>
      <Card title={t("ai.result")}><pre className="whitespace-pre-wrap text-xs">{result || t("common.empty")}</pre></Card>
    </div>
  );
}

const SAFETY = [
  ["batteryTitle", "battery"],
  ["crtTitle", "crt"],
  ["burnTitle", "burn"],
  ["ppeTitle", "ppe"],
] as const;

export function SafetyPage() {
  const { t, i18n } = useTranslation();
  const [answer, setAnswer] = useState("");
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title={t("safety.title")}>
        <div className="grid gap-3 sm:grid-cols-2">
          {SAFETY.map(([title, body]) => (
            <div key={title} className="rounded-xl border border-line p-3">
              <div className="mb-2 text-3xl" aria-hidden>{title === "batteryTitle" ? "🔋" : title === "crtTitle" ? "🖥" : title === "burnTitle" ? "🔥" : "🧤"}</div>
              <b>{t(`safety.${title}`)}</b>
              <p className="mt-1 text-sm text-muted">{t(`safety.${body}`)}</p>
              <Btn className="mt-2" kind="secondary" onClick={() => speak(t(`safety.${body}`), i18n.language)}>{t("safety.play")}</Btn>
            </div>
          ))}
        </div>
      </Card>
      <Card title={t("safety.assistant")}>
        <Btn onClick={() => void listen(i18n.language).then(async (text) => {
          const data = await api<{ answer: string }>("/ai/safety", { method: "POST", body: JSON.stringify({ text, lang: i18n.language }) });
          setAnswer(data.answer);
          speak(data.answer, i18n.language);
        })}>{t("ai.listen")}</Btn>
        <p className="mt-3 text-sm">{answer}</p>
      </Card>
    </div>
  );
}

export function SettingsPage() {
  const { t, i18n } = useTranslation();
  const { user, refresh } = useAuth();
  const toast = useToast();
  const [low, setLow] = useState(Boolean(user?.profile?.low_data_mode));
  const [voice, setVoice] = useState(Boolean(user?.profile?.voice_nav_enabled));
  const [quality, setQuality] = useState(String(user?.profile?.image_quality || 0.7));
  const [contact, setContact] = useState(user?.profile?.emergency_contact || "");
  const [area, setArea] = useState(user?.profile?.area || "");

  async function save() {
    await api("/api/collectors/me", { method: "PATCH", body: JSON.stringify({ low_data_mode: low, voice_nav_enabled: voice, image_quality: Number(quality), emergency_contact: contact, area }) });
    await api("/api/auth/me", { method: "PATCH", body: JSON.stringify({ preferred_language: i18n.language }) });
    await refresh();
    toast(t("settings.saved"));
  }

  return (
    <Card title={t("settings.title")}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("settings.lowData")}><select className={inputClass} value={low ? "1" : "0"} onChange={(e) => setLow(e.target.value === "1")}><option value="1">{t("common.yes")}</option><option value="0">{t("common.no")}</option></select></Field>
        <Field label={t("settings.voiceNav")}><select className={inputClass} value={voice ? "1" : "0"} onChange={(e) => setVoice(e.target.value === "1")}><option value="1">{t("common.yes")}</option><option value="0">{t("common.no")}</option></select></Field>
        <Field label={t("settings.quality")}><input className={inputClass} type="number" min="0.3" max="0.95" step="0.05" value={quality} onChange={(e) => setQuality(e.target.value)} /></Field>
        <Field label={t("auth.emergency")}><input className={inputClass} value={contact} onChange={(e) => setContact(e.target.value)} /></Field>
        <Field label={t("auth.area")}><input className={inputClass} value={area} onChange={(e) => setArea(e.target.value)} /></Field>
      </div>
      <Btn className="mt-3" onClick={() => void save()}>{t("common.save")}</Btn>
      <Btn className="ml-2 mt-3" kind="secondary" onClick={() => void Notification.requestPermission()}>{t("dashboard.alerts")}</Btn>
    </Card>
  );
}

export function RewardsPage() {
  const { t } = useTranslation();
  const [data, setData] = useState<{ referral_code: string; badges: { code: string; name: string; description: string; threshold: number; earned: boolean }[] } | null>(null);
  useEffect(() => { void api<NonNullable<typeof data>>("/api/rewards").then(setData); }, []);
  if (!data) return <States loading />;
  return (
    <Card title={t("rewards.title")}>
      <p>{t("rewards.code")}: <b>{data.referral_code}</b></p>
      <div className="mt-3 space-y-2">
        {data.badges.map((badge) => <p key={badge.code}>{badge.earned ? "🏅" : "🔒"} {badge.name} — {badge.description} · {badge.earned ? t("rewards.earned") : t("rewards.locked")}</p>)}
      </div>
    </Card>
  );
}

export function TutorialsPage() {
  const { t, i18n } = useTranslation();
  const [rows, setRows] = useState<{ feature: string; title: string; script: string }[]>([]);
  useEffect(() => { void api<typeof rows>(`/api/tutorials?lang=${i18n.language}`).then(setRows); }, [i18n.language]);
  return (
    <Card title={t("tutorials.title")}>
      {rows.length === 0 ? <States empty /> : rows.map((row) => (
        <div key={row.feature} className="border-t border-line py-3">
          <b>{row.title}</b>
          <p className="text-sm text-muted">{row.script}</p>
          <Btn className="mt-2" kind="secondary" onClick={() => speak(row.script, i18n.language)}>{t("tutorials.play")}</Btn>
        </div>
      ))}
    </Card>
  );
}

export function CollectorRedirect() {
  const navigate = useNavigate();
  useEffect(() => { navigate("/collector/lots"); }, [navigate]);
  return null;
}
