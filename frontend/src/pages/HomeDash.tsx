import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Camera, MapPin, Mic, Plus, Shield, Tags, Volume2 } from "lucide-react";
import { Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CircleMarker, MapContainer, Marker, Polyline, Popup, TileLayer } from "react-leaflet";
import { api, ApiError, inr } from "../lib/api";
import { speak } from "../lib/speech";
import { useAuth } from "../auth/AuthContext";
import { db } from "../db/db";
import { Badge, Btn, Card, States, VerifiedMark } from "../components/Bits";

type Lot = {
  public_id: string;
  material: string;
  weight_kg: number;
  status: string;
  estimated_value: number;
  flags: Record<string, boolean>;
  duplicate_status?: string;
};

const STEPS = ["open", "pickup_scheduled", "handed_over", "completed"] as const;

function stepIndex(status: string) {
  if (status === "processing" || status === "disputed") return 2;
  const index = STEPS.indexOf(status as (typeof STEPS)[number]);
  return index < 0 ? 0 : index;
}

export function CollectorDashboard() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const [stats, setStats] = useState<Record<string, number> | null>(null);
  const [lots, setLots] = useState<Lot[]>([]);
  const [board, setBoard] = useState<{ material: string; price_per_kg: number; change_pct?: number }[]>([]);
  const [series, setSeries] = useState<{ period: string; amount: number }[]>([]);
  const [forecast, setForecast] = useState<{ forecast: number; direction: string } | null>(null);
  const [insight, setInsight] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const handovers = Number(stats?.verified_handovers || 0);
  const next = handovers >= 250 ? 250 : handovers >= 100 ? 250 : handovers >= 50 ? 100 : 50;
  const date = new Date().toLocaleDateString(i18n.language === "hi" ? "hi-IN" : i18n.language === "mr" ? "mr-IN" : "en-IN", { weekday: "long", day: "numeric", month: "long" });

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [s, l, b, e, f] = await Promise.all([
          api<Record<string, number>>("/api/collectors/me/stats"),
          api<Lot[]>("/api/lots"),
          api<{ items: { material: string; price_per_kg: number; change_pct: number }[] }>("/api/prices/board"),
          api<{ series: { period: string; amount: number }[] }>("/api/collectors/me/earnings?bucket=month"),
          api<{ forecast: number; direction: string }>("/ai/earnings-predict", { method: "POST" }),
        ]);
        setStats(s);
        setLots(l.slice(0, 4));
        setBoard(b.items);
        setSeries(e.series);
        setForecast(f);
        await db.meta.put({ key: "collector-home", value: JSON.stringify({ stats: s, lots: l.slice(0, 4), board: b.items }) });
        const lat = user?.profile?.lat || 17.44;
        const lng = user?.profile?.lng || 78.49;
        const material = user?.profile?.materials?.[0] || "PCB";
        const ranked = await api<{ ranked: { business_name: string; reason: string }[] }>("/ai/recommend-recycler", { method: "POST", body: JSON.stringify({ material_code: material, weight: 1, lat, lng }) });
        const prediction = await api<{ direction: string }>( "/ai/predict-price", { method: "POST", body: JSON.stringify({ material_code: material, city: user?.profile?.city || "" }) });
        setInsight(`${material}: ${prediction.direction}. ${ranked.ranked[0]?.business_name || ""} ${ranked.ranked[0]?.reason || ""}`);
        setError("");
      } catch (err) {
        const cached = await db.meta.get("collector-home");
        if (cached?.value) {
          const parsed = JSON.parse(cached.value) as { stats: Record<string, number>; lots: Lot[]; board: { material: string; price_per_kg: number }[] };
          setStats(parsed.stats);
          setLots(parsed.lots);
          setBoard(parsed.board);
        }
        setError(err instanceof ApiError ? t(`errors.${err.code}`, { defaultValue: t("common.error") }) : t("common.offline"));
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [user?.id]);

  const monthDelta = (stats?.this_month || 0) - (stats?.last_month || 0);
  const actions = [
    ["/app/collector/lots", "dash.scan", Camera],
    ["/app/collector/lots", "dash.newLot", Plus],
    ["/app/collector/ai", "dash.voice", Mic],
    ["/app/collector/recyclers", "dash.nearby", MapPin],
    ["/app/collector/prices", "dash.prices", Tags],
    ["/app/collector/safety", "dash.safety", Shield],
  ] as const;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-extrabold">{t("dash.greeting", { name: user?.name })}</h1>
          <p className="text-sm text-muted">{date}</p>
        </div>
        <button className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-white px-3 font-bold" onClick={() => speak(`${t("dash.greeting", { name: user?.name })}. ${date}`, i18n.language)}><Volume2 size={16} /> {t("dash.speak")}</button>
      </div>
      <States loading={loading && !stats} error={stats ? "" : error} />
      <section id="tour-earnings" data-testid="collector-earnings" className="rounded-2xl bg-gradient-to-br from-brand-dark to-brand-light p-5 text-white shadow-card">
        <p className="text-sm opacity-80">{t("dashboard.earnings")}</p>
        <p className="font-display text-4xl font-extrabold">{inr(Number(stats?.earned || 0))}</p>
        <p className="mt-2 text-sm">{t("dash.thisMonth")} {inr(stats?.this_month)} {monthDelta >= 0 ? "↑" : "↓"} {t("dash.lastMonth")} {inr(stats?.last_month)}</p>
        {forecast ? <p className="text-sm">{t("dash.forecast")} {inr(forecast.forecast)} · {forecast.direction}</p> : null}
        <div className="mt-3 h-16">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={series}><Line dataKey="amount" stroke="#eaa72b" dot={false} /></LineChart>
          </ResponsiveContainer>
        </div>
      </section>
      <div id="tour-actions" className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {actions.map(([to, key, Icon]) => (
          <Link key={key} to={to} className="flex min-h-20 flex-col items-center justify-center gap-2 rounded-2xl bg-white text-sm font-bold shadow-card"><Icon aria-hidden /> {t(key)}</Link>
        ))}
      </div>
      <div id="tour-prices" className="flex gap-3 overflow-x-auto pb-2">
        {board.map((row) => (
          <Link key={row.material} to="/app/collector/prices" className="min-w-36 rounded-2xl bg-white p-3 shadow-card">
            <b>{row.material}</b>
            <p>{inr(row.price_per_kg)}</p>
            <p className={Number(row.change_pct) >= 0 ? "text-brand" : "text-danger"}>{Number(row.change_pct) >= 0 ? "↑" : "↓"} {row.change_pct ?? 0}%</p>
          </Link>
        ))}
      </div>
      <section id="tour-lots" className="space-y-3">
        {lots.length === 0 && !loading ? <States empty /> : lots.map((lot) => (
          <article key={lot.public_id} className="rounded-2xl bg-white p-4 shadow-card">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Link className="font-bold text-brand" to={`/app/collector/lots/${lot.public_id}`}>{lot.public_id}</Link>
              {lot.duplicate_status === "flagged" ? <Badge tone="danger">{t("dash.duplicate")}</Badge> : null}
            </div>
            <p className="text-sm">{lot.material} · {lot.weight_kg} kg · {inr(lot.estimated_value)}</p>
            <div className="mt-3 grid grid-cols-4 gap-1 text-center text-[11px]">
              {STEPS.map((step, index) => <span key={step} className={`rounded-full px-1 py-1 ${index <= stepIndex(lot.status) ? "bg-brand text-white" : "bg-[#edf2f0]"}`}>{t(`dash.step.${step}`)}</span>)}
            </div>
            <p className="mt-2 text-xs">GPS {lot.flags?.gps_present ? "✓" : "✗"} · {t("lots.photo")} {lot.flags?.photo_present ? "✓" : "✗"} · {t("lots.time")} {lot.flags?.time_ok ? "✓" : "✗"}</p>
          </article>
        ))}
      </section>
      <Card title={t("dash.insights")}>{insight || <States empty />}</Card>
      <div className="grid gap-3 md:grid-cols-2">
        <Card title={t("dash.nextBadge")}>
          <p className="text-3xl font-extrabold">{handovers}/{next}</p>
          <div className="mt-2 h-2 rounded-full bg-[#edf2f0]"><div className="h-2 rounded-full bg-brand" style={{ width: `${Math.min(100, (handovers / next) * 100)}%` }} /></div>
        </Card>
        <Card title={t("dash.referral")}>
          <p className="font-mono text-xl">{user?.referral_code}</p>
          <Btn kind="secondary" onClick={() => void navigator.clipboard.writeText(user?.referral_code || "")}>{t("common.share")}</Btn>
        </Card>
      </div>
    </div>
  );
}

export function RecyclerDashboard() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [pickups, setPickups] = useState<Record<string, string | number | null>[]>([]);
  const [me, setMe] = useState<Record<string, unknown> | null>(null);
  const [tx, setTx] = useState<{ status: string; amount: number; paid_amount: number }[]>([]);
  const [ratings, setRatings] = useState<{ stars: number }[]>([]);
  const [market, setMarket] = useState<Record<string, number>>({});
  const [drag, setDrag] = useState("");

  async function load() {
    const [rows, profile, payments, stars, board] = await Promise.all([
      api<Record<string, string | number | null>[]>("/api/pickups"),
      api<Record<string, unknown>>("/api/recyclers/me"),
      api<{ status: string; amount: number; paid_amount: number }[]>("/api/transactions"),
      api<{ stars: number }[]>("/api/ratings/me"),
      api<{ items: { material: string; price_per_kg: number }[] }>("/api/prices/board?city=Hyderabad"),
    ]);
    setPickups(rows);
    setMe(profile);
    setTx(payments);
    setRatings(stars);
    setMarket(Object.fromEntries(board.items.map((item) => [item.material, item.price_per_kg])));
  }
  useEffect(() => { void load().catch(() => undefined); }, []);

  const columns = useMemo(() => {
    const groups: Record<string, typeof pickups> = { new: [], offered: [], scheduled: [], received: [], processed: [] };
    pickups.forEach((row) => {
      const status = String(row.status);
      const lotStatus = String(row.lot_status || "");
      if (lotStatus === "completed" || lotStatus === "processing") groups.processed.push(row);
      else if (lotStatus === "handed_over") groups.received.push(row);
      else if (status === "accepted") groups.scheduled.push(row);
      else if (status === "requested") groups.new.push(row);
    });
    return groups;
  }, [pickups]);

  if (user?.profile?.status === "pending") return <Card><Badge tone="pending">{t("common.pending")}</Badge><p className="mt-2">{t("auth.pendingNote")}</p></Card>;
  const due = tx.filter((row) => row.status !== "paid").reduce((sum, row) => sum + (row.amount - row.paid_amount), 0);
  const reliability = (me?.reliability as { score?: number }) || {};
  const offers = (me?.offers as { material: string; price_per_kg: number }[]) || [];
  const volume = Object.entries(pickups.reduce<Record<string, number>>((acc, row) => {
    const key = String(row.material || "");
    acc[key] = (acc[key] || 0) + Number(row.weight_kg || 0);
    return acc;
  }, {})).map(([material, kg]) => ({ material, kg }));
  const ratingBuckets = [1, 2, 3, 4, 5].map((stars) => ({ stars, count: ratings.filter((row) => row.stars === stars).length }));
  const points = pickups.filter((row) => row.lat && row.lng);

  return (
    <div className="space-y-4">
      <div id="tour-kpi" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {([
          [t("dash.incoming"), pickups.length],
          [t("dash.today"), pickups.filter((row) => String(row.scheduled_at || "").slice(0, 10) === new Date().toISOString().slice(0, 10)).length],
          [t("dash.due"), inr(due)],
          [t("recyclers.reliability"), reliability.score ?? "—"],
          [t("dash.rating"), String(me?.rating ?? "—")],
        ] as [string, string | number][]).map(([label, value]) => <Card key={label}><p className="text-xs text-muted">{label}</p><p className="text-3xl font-extrabold">{value}</p></Card>)}
      </div>
      <div id="tour-availability" className="flex flex-wrap gap-2">
        {(["available", "busy", "offline"] as const).map((status) => (
          <Btn key={status} kind={user?.profile?.availability === status ? "primary" : "secondary"} onClick={() => void api("/api/recyclers/me/availability", { method: "PATCH", body: JSON.stringify({ status }) }).then(load)}>{t(`common.${status}`)}</Btn>
        ))}
        <Link id="tour-scan" className="inline-flex min-h-11 items-center rounded-lg bg-amber px-4 font-bold text-brand-dark" to="/app/recycler/scan">{t("nav.scan")}</Link>
      </div>
      <section id="tour-kanban" className="grid gap-3 lg:grid-cols-5">
        {(["new", "offered", "scheduled", "received", "processed"] as const).map((column) => (
          <div key={column} className="rounded-2xl bg-white p-3 shadow-card" onDragOver={(event) => event.preventDefault()} onDrop={() => {
            if (column === "scheduled" && drag) void api(`/api/pickups/${drag}`, { method: "PATCH", body: JSON.stringify({ status: "accepted" }) }).then(load);
          }}>
            <h3 className="text-sm font-bold">{t(`dash.kanban.${column}`)}</h3>
            {columns[column].length === 0 ? <p className="mt-3 text-xs text-muted">{t("common.empty")}</p> : columns[column].map((row) => (
              <article key={String(row.id)} draggable={column === "new"} onDragStart={() => setDrag(String(row.id))} className="mt-2 rounded-xl border border-line p-2 text-sm">
                <Link className="font-bold text-brand" to={`/app/recycler/lots/${row.lot_id}`}>{String(row.lot_id)}</Link>
                <p>{String(row.material)} · {String(row.weight_kg)} kg</p>
              </article>
            ))}
          </div>
        ))}
      </section>
      <Card title={t("nav.offers")}>
        <div id="tour-offers" className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-muted"><th>{t("lots.material")}</th><th>{t("prices.perKg")}</th><th>{t("dash.market")}</th></tr></thead>
            <tbody>
              {offers.map((offer) => {
                const avg = market[offer.material];
                const odd = avg && (offer.price_per_kg > avg * 1.25 || offer.price_per_kg < avg * 0.75);
                return (
                  <tr key={offer.material} className="border-t border-line">
                    <td className="py-2">{offer.material}</td>
                    <td><input className="min-h-11 w-24 rounded-lg border px-2" defaultValue={offer.price_per_kg} onBlur={(event) => void api("/api/recyclers/me/offers", { method: "PUT", body: JSON.stringify({ material_code: offer.material, price_per_kg: Number(event.target.value) }) })} /></td>
                    <td>{avg ? inr(avg) : "—"} {odd ? <Badge tone="danger">{t("dash.abnormal")}</Badge> : null}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="h-72 overflow-hidden rounded-2xl">
          <MapContainer center={[17.45, 78.45]} zoom={11}>
            <TileLayer attribution='&copy; OpenStreetMap' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            {user?.profile?.lat != null && user.profile.lng != null ? <CircleMarker center={[user.profile.lat, user.profile.lng]} radius={8} pathOptions={{ color: "#eaa72b" }} /> : null}
            {points.map((row) => (
              <Marker key={String(row.id)} position={[Number(row.lat), Number(row.lng)]}>
                <Popup>{String(row.lot_id)} · {String(row.material)}</Popup>
              </Marker>
            ))}
            {user?.profile?.lat != null && user?.profile?.lng != null && points[0] ? <Polyline positions={[[user.profile.lat, user.profile.lng], [Number(points[0].lat), Number(points[0].lng)]]} /> : null}
          </MapContainer>
        </div>
        <Card title={t("dash.volume")}>
          <div className="h-48"><ResponsiveContainer width="100%" height="100%"><LineChart data={volume}><XAxis dataKey="material" /><YAxis /><Tooltip /><Line dataKey="kg" stroke="#176b52" /></LineChart></ResponsiveContainer></div>
          <div className="h-32"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={ratingBuckets} dataKey="count" nameKey="stars">{ratingBuckets.map((row) => <Cell key={row.stars} fill={row.stars > 3 ? "#176b52" : "#eaa72b"} />)}</Pie></PieChart></ResponsiveContainer></div>
        </Card>
      </div>
      <VerifiedMark />
    </div>
  );
}

export function AdminDashboard() {
  const { t } = useTranslation();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [feed, setFeed] = useState<{ kind: string; at: string; lot_id: string; note: string }[]>([]);
  const [analytics, setAnalytics] = useState<{ lots_by_status: Record<string, number>; paid_by_mode: Record<string, number>; impact: { co2_kg: number; weight_kg: number; by_material: Record<string, { weight_kg: number }> } } | null>(null);
  const [pending, setPending] = useState<{ user_id: string; business_name: string }[]>([]);
  const [map, setMap] = useState<{ recyclers: { business_name: string; lat: number; lng: number }[]; areas: { city: string; weight_kg: number; lots: number }[] } | null>(null);
  const [error, setError] = useState("");

  async function load() {
    try {
      const [summary, activity, charts, queue, community] = await Promise.all([
        api<Record<string, unknown>>("/api/admin/summary"),
        api<typeof feed>("/api/admin/activity"),
        api<NonNullable<typeof analytics>>("/api/admin/analytics"),
        api<typeof pending>("/api/admin/recyclers?status=pending"),
        api<NonNullable<typeof map>>("/api/public/map"),
      ]);
      setData(summary);
      setFeed(activity);
      setAnalytics(charts);
      setPending(queue);
      setMap(community);
      setError("");
    } catch (err) {
      setError(err instanceof ApiError ? t(`errors.${err.code}`) : t("common.error"));
    }
  }
  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 8000);
    return () => window.clearInterval(timer);
  }, []);

  if (!data && error) return <States error={error} />;
  if (!data) return <div className="grid gap-3 sm:grid-cols-3">{[1, 2, 3].map((n) => <div key={n} className="h-24 animate-pulse rounded-2xl bg-white" />)}</div>;
  const impact = data.impact as { co2_kg: number; weight_kg: number };
  const mix = analytics ? Object.entries(analytics.impact.by_material || {}).map(([name, row]) => ({ name, value: row.weight_kg })) : [];
  const statusChart = analytics ? Object.entries(analytics.lots_by_status).map(([name, value]) => ({ name, value })) : [];

  return (
    <div className="space-y-4">
      <div id="tour-kpi" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        {([
          [t("dashboard.collectors"), String(data.collectors)],
          [t("dashboard.recyclers"), String(data.recyclers)],
          [t("dash.lotsToday"), String(data.lots_today)],
          [t("dash.handoverPct"), `${String(data.verified_handover_pct)}%`],
          [t("dash.disputesOpen"), String(data.open_disputes)],
          [t("dashboard.co2"), `${impact.co2_kg.toFixed(1)} kg`],
        ] as [string, string][]).map(([label, value]) => <Card key={label}><p className="text-xs text-muted">{label}</p><p className="text-2xl font-extrabold">{value}</p></Card>)}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={t("dash.activity")}>
          <ul id="tour-activity" className="max-h-72 space-y-2 overflow-auto text-sm">
            {feed.length === 0 ? <States empty /> : feed.map((row) => <li key={row.at + row.kind} className="border-b border-line py-2"><b>{row.kind}</b> {row.lot_id} <span className="text-muted">{row.at}</span></li>)}
          </ul>
        </Card>
        <Card title={t("nav.verification")}>
          <div id="tour-verify">
            {pending.length === 0 ? <States empty /> : pending.map((row) => <p key={row.user_id} className="py-1">{row.business_name}</p>)}
            <Link className="mt-2 inline-block font-bold text-brand" to="/app/admin/verification">{t("admin.approve")}</Link>
          </div>
        </Card>
      </div>
      <div id="tour-charts" className="grid gap-4 lg:grid-cols-2">
        <div className="h-64 rounded-2xl bg-white p-2">
          <ResponsiveContainer width="100%" height="100%"><LineChart data={statusChart}><XAxis dataKey="name" /><YAxis /><Tooltip /><Line dataKey="value" stroke="#176b52" /></LineChart></ResponsiveContainer>
        </div>
        <div className="h-64 rounded-2xl bg-white p-2">
          <ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={mix} dataKey="value" nameKey="name">{mix.map((row) => <Cell key={row.name} fill="#22956f" />)}</Pie><Tooltip /></PieChart></ResponsiveContainer>
        </div>
      </div>
      <div className="h-72 overflow-hidden rounded-2xl">
        <MapContainer center={[18.5, 78.2]} zoom={5}>
          <TileLayer attribution='&copy; OpenStreetMap' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          {map?.recyclers.map((row) => <CircleMarker key={row.business_name} center={[row.lat, row.lng]} radius={7} pathOptions={{ color: "#176b52" }}><Popup>{row.business_name}</Popup></CircleMarker>)}
          {map?.areas.map((area) => <CircleMarker key={area.city} center={area.city === "Pune" ? [18.52, 73.85] : [17.4, 78.48]} radius={Math.max(8, Math.sqrt(area.weight_kg))} pathOptions={{ color: "#eaa72b" }}><Popup>{area.city} · {area.weight_kg} kg · {area.lots}</Popup></CircleMarker>)}
        </MapContainer>
      </div>
      <div id="tour-reset">
        <Btn onClick={() => void api("/api/admin/reset-demo", { method: "POST" }).then(load)}>{t("demo.reset")}</Btn>
      </div>
    </div>
  );
}
