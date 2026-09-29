import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion, useInView, useReducedMotion } from "framer-motion";
import { useRef } from "react";
import CountUp from "react-countup";
import { Circle, MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import { Line, LineChart, ResponsiveContainer } from "recharts";
import { Battery, Flame, HardHat, Mic, Moon, ShieldAlert, Sun } from "lucide-react";
import { API_URL, api, inr } from "../lib/api";
import { listen, speak } from "../lib/speech";
import { useTheme } from "../theme/ThemeContext";
import { LangSelect } from "../components/Bits";
import { useAuth } from "../auth/AuthContext";

type Price = { material: string; price_per_kg: number | null; change_pct: number; source: string; date: string };
type Stats = { collectors: number; lots: number; tonnes_diverted: number; co2_kg: number; earnings: number };
type RecyclerPin = { business_name: string; lat: number; lng: number; verified: boolean; city: string };

const FALLBACK_HEADLINES = ["en", "hi", "mr"] as const;

function CountStat({ value, decimals = 0 }: { value: number; decimals?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.6 });
  return <span ref={ref}>{inView ? <CountUp end={value} duration={1.2} decimals={decimals} separator="," /> : "0"}</span>;
}

export function LandingPage() {
  const { t, i18n } = useTranslation();
  const { dark, toggle } = useTheme();
  const { user } = useAuth();
  const reduced = useReducedMotion();
  const [headline, setHeadline] = useState(0);
  const [prices, setPrices] = useState<Price[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [down, setDown] = useState(false);
  const [material, setMaterial] = useState("PCB");
  const [weight, setWeight] = useState("5");
  const [quote, setQuote] = useState<{ value: number; low?: number; high?: number; price_per_kg: number } | null>(null);
  const [best, setBest] = useState<{ business_name: string; distance_km: number; net_payout: number; verified: boolean } | null>(null);
  const [spark, setSpark] = useState<{ price: number }[]>([]);
  const [voiceText, setVoiceText] = useState("PCB ka bhav kya hai?");
  const [voiceAnswer, setVoiceAnswer] = useState("");
  const [offline, setOffline] = useState(false);
  const [syncPhase, setSyncPhase] = useState<"idle" | "queued" | "synced">("idle");
  const [lotId, setLotId] = useState("");
  const [verify, setVerify] = useState<Record<string, unknown> | null>(null);
  const [pins, setPins] = useState<RecyclerPin[]>([]);
  const [areas, setAreas] = useState<{ city: string; weight_kg: number }[]>([]);
  const [quotes, setQuotes] = useState<{ name: string; role: string; city: string; quote: Record<string, string> }[]>([]);
  const [activity, setActivity] = useState<{ event: string; material: string; city: string; lot_id: string }[]>([]);
  const [openFaq, setOpenFaq] = useState(0);

  async function loadPublic() {
    try {
      const [priceBody, statBody, mapBody, quoteBody, activityBody] = await Promise.all([
        api<{ items: Price[] }>("/api/public/prices"),
        api<Stats>("/api/public/stats"),
        api<{ recyclers: RecyclerPin[]; areas: { city: string; weight_kg: number }[] }>("/api/public/map"),
        api<typeof quotes>("/api/public/testimonials"),
        api<typeof activity>("/api/public/activity"),
      ]);
      setPrices(priceBody.items.filter((item) => item.price_per_kg != null));
      setStats(statBody);
      setPins(mapBody.recyclers.filter((row) => row.lat && row.lng));
      setAreas(mapBody.areas);
      setQuotes(quoteBody);
      setActivity(activityBody);
      setDown(false);
    } catch {
      setDown(true);
    }
  }

  useEffect(() => {
    void loadPublic();
    const timer = window.setInterval(() => void loadPublic(), 30000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (reduced) return;
    const timer = window.setInterval(() => setHeadline((value) => (value + 1) % 3), 2800);
    return () => window.clearInterval(timer);
  }, [reduced]);

  useEffect(() => {
    document.title = t("landing.metaTitle");
  }, [t, i18n.language]);

  async function tryEstimate(event: FormEvent) {
    event.preventDefault();
    const estimated = await api<{ value: number; price_per_kg: number }>("/ai/estimate-price", {
      method: "POST",
      body: JSON.stringify({ material_code: material, weight: Number(weight), unit: "kg", city: "Hyderabad" }),
    });
    const ranked = await api<{ ranked: { business_name: string; distance_km: number; net_payout: number; verified: boolean }[] }>(`/api/public/recommend?material=${material}&weight=${weight}`);
    const history = await api<{ points: { price: number }[] }>(`/api/public/prices/history?material=${material}&range=30d`);
    setQuote(estimated);
    setBest(ranked.ranked[0] || null);
    setSpark(history.points);
  }

  async function askVoice(text: string) {
    const res = await api<{ answer: string }>("/ai/voice", { method: "POST", body: JSON.stringify({ text, lang: i18n.language }) });
    setVoiceAnswer(res.answer);
    speak(res.answer, i18n.language);
  }

  async function lookup(event: FormEvent) {
    event.preventDefault();
    setVerify(await api(`/api/public/verify/${encodeURIComponent(lotId.trim())}`));
  }

  const steps = ["collection", "pickup", "handover", "recycler", "processing"] as const;
  const faqs = [1, 2, 3] as const;

  return (
    <div className="bg-canvas text-ink">
      <header className="glass sticky top-0 z-30 border-b border-white/50">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <a href="#top" className="font-display text-lg font-extrabold text-brand-dark">{t("app.name")}</a>
          <nav className="hidden items-center gap-4 text-sm font-semibold md:flex" aria-label={t("landing.navLabel")}>
            <a href="#how">{t("landing.nav.how")}</a>
            <a href="#features">{t("landing.nav.features")}</a>
            <a href="#prices">{t("landing.nav.prices")}</a>
            <a href="#impact">{t("landing.nav.impact")}</a>
            <a href="#safety">{t("landing.nav.safety")}</a>
          </nav>
          <div className="flex items-center gap-2">
            <LangSelect />
            <button aria-label={t("shell.theme")} className="min-h-11 min-w-11 rounded-xl border border-line bg-white" onClick={toggle}>{dark ? <Moon className="mx-auto" size={16} /> : <Sun className="mx-auto" size={16} />}</button>
            <Link className="min-h-11 rounded-xl px-3 py-3 text-sm font-bold" to={user ? `/app/${user.role}` : "/login"}>{user ? t("nav.dashboard") : t("auth.login")}</Link>
            <Link data-testid="try-demo" className="min-h-11 rounded-xl bg-amber px-4 py-3 text-sm font-bold text-brand-dark" to="/login#demo">{t("landing.tryDemo")}</Link>
          </div>
        </div>
      </header>

      <main id="top">
        <section className="mx-auto grid max-w-6xl items-center gap-8 px-4 py-12 md:grid-cols-2">
          <div>
            <p className="text-sm font-semibold uppercase tracking-widest text-brand">{t("app.tag")}</p>
            <h1 className="mt-3 min-h-28 font-display text-4xl font-extrabold leading-tight text-brand-dark md:text-5xl">
              <motion.span key={headline} initial={reduced ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>{t(`landing.hero.${FALLBACK_HEADLINES[headline]}`)}</motion.span>
            </h1>
            <p className="mt-4 max-w-xl text-lg text-muted">{t("landing.hero.sub")}</p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link className="min-h-12 rounded-2xl bg-brand px-5 py-3 font-bold text-white" to="/login#demo">{t("landing.tryDemo")}</Link>
              <Link className="min-h-12 rounded-2xl border border-brand px-5 py-3 font-bold text-brand" to="/register/collector">{t("landing.registerCollector")}</Link>
            </div>
            {down ? <p className="mt-4 text-sm text-danger" role="status">{t("landing.fallback")}</p> : null}
          </div>
          <div className="relative">
            <svg viewBox="0 0 420 280" className="w-full" role="img" aria-label={t("landing.hero.art")}>
              <rect x="20" y="70" width="100" height="80" rx="16" fill="#123d31" />
              <rect x="160" y="50" width="110" height="130" rx="18" fill="#176b52" />
              <circle cx="330" cy="110" r="48" fill="#eaa72b" />
              <motion.path d="M120 110 H160" stroke="#22956f" strokeWidth="4" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} />
              <motion.path d="M270 110 H282" stroke="#eaa72b" strokeWidth="4" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} />
            </svg>
            <div className="absolute bottom-2 left-2 right-2 grid gap-2 sm:grid-cols-3">
              {activity.slice(0, 3).map((item) => (
                <motion.article key={item.lot_id + item.event} className="rounded-2xl bg-white/90 p-3 text-xs shadow-card" initial={reduced ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
                  <b>{item.event}</b>
                  <p>{item.material} · {item.city}</p>
                  <p className="text-muted">{item.lot_id}</p>
                </motion.article>
              ))}
            </div>
          </div>
        </section>

        <section id="prices" className="overflow-hidden border-y border-line bg-brand-dark py-3 text-white" aria-label={t("landing.ticker")}>
          <div className="ticker-track flex w-max gap-8 px-4">
            {[...prices, ...prices].map((item, index) => (
              <span key={`${item.material}-${index}`} className="text-sm font-semibold">
                {item.material} {inr(item.price_per_kg)} <span className={item.change_pct >= 0 ? "text-emerald-300" : "text-red-300"}>{item.change_pct >= 0 ? "↑" : "↓"} {item.change_pct}%</span>
              </span>
            ))}
          </div>
        </section>

        <section id="impact" className="mx-auto grid max-w-6xl gap-4 px-4 py-12 sm:grid-cols-2 lg:grid-cols-5">
          {stats ? (
            [
              [t("landing.impact.collectors"), stats.collectors, 0],
              [t("landing.impact.lots"), stats.lots, 0],
              [t("landing.impact.tonnes"), stats.tonnes_diverted, 2],
              [t("landing.impact.co2"), stats.co2_kg, 1],
              [t("landing.impact.earnings"), stats.earnings, 0],
            ] as [string, number, number][]
          ).map(([label, value, decimals]) => (
            <article key={label} className="rounded-2xl bg-white p-4 shadow-card">
              <p className="text-xs text-muted">{label}</p>
              <p className="font-display text-3xl font-extrabold text-brand-dark"><CountStat value={value} decimals={decimals} /></p>
            </article>
          )) : <p className="text-sm text-muted">{down ? t("landing.fallback") : t("common.loading")}</p>}
        </section>

        <section id="how" className="mx-auto max-w-6xl px-4 py-8">
          <h2 className="font-display text-3xl font-extrabold text-brand-dark">{t("landing.howTitle")}</h2>
          <ol className="mt-6 grid gap-4 md:grid-cols-5">
            {steps.map((step, index) => (
              <motion.li key={step} className="rounded-2xl bg-white p-4 shadow-card" initial={reduced ? false : { opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}>
                <p className="text-xs font-bold text-amber">{index + 1}</p>
                <h3 className="mt-2 font-bold">{t(`landing.step.${step}`)}</h3>
                <p className="mt-2 text-sm text-muted">{t(`landing.step.${step}Body`)}</p>
              </motion.li>
            ))}
          </ol>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-8" aria-labelledby="try-title">
          <h2 id="try-title" className="font-display text-3xl font-extrabold">{t("landing.tryTitle")}</h2>
          <form className="mt-4 grid gap-3 rounded-2xl bg-white p-4 shadow-card md:grid-cols-4" onSubmit={(event) => void tryEstimate(event)}>
            <label className="text-sm">{t("lots.material")}<select className="mt-1 min-h-11 w-full rounded-xl border border-line px-3" value={material} onChange={(event) => setMaterial(event.target.value)}>{["PCB", "Cable", "Battery", "CRT", "LCD", "Plastic", "Metal", "Aluminium", "Copper", "Paper/Cardboard"].map((code) => <option key={code}>{code}</option>)}</select></label>
            <label className="text-sm">{t("lots.weight")}<input className="mt-1 min-h-11 w-full rounded-xl border border-line px-3" type="number" min="0.1" value={weight} onChange={(event) => setWeight(event.target.value)} /></label>
            <button className="min-h-11 self-end rounded-xl bg-brand font-bold text-white" type="submit">{t("landing.estimate")}</button>
            <div className="self-end text-sm">
              {quote ? <p><b>{inr(quote.value)}</b> · {inr(quote.price_per_kg)}/kg</p> : null}
              {best ? <p>{best.business_name} · {best.distance_km} km · {inr(best.net_payout)}</p> : null}
            </div>
          </form>
          {spark.length ? (
            <div className="mt-4 h-24 rounded-2xl bg-white p-2">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={spark}><Line type="monotone" dataKey="price" stroke="#176b52" dot={false} /></LineChart>
              </ResponsiveContainer>
            </div>
          ) : null}
        </section>

        <section id="features" className="mx-auto max-w-6xl px-4 py-8">
          <h2 className="font-display text-3xl font-extrabold">{t("landing.featuresTitle")}</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-4">
            {(["collectors", "recyclers", "admins", "ai"] as const).map((group) => (
              <article key={group} className="rounded-2xl bg-white p-4 shadow-card transition hover:-translate-y-1">
                <h3 className="font-bold text-brand">{t(`landing.group.${group}`)}</h3>
                <ul className="mt-3 space-y-2 text-sm">{[1, 2, 3].map((n) => <li key={n}>{t(`landing.group.${group}${n}`)}</li>)}</ul>
              </article>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-8">
          <h2 className="font-display text-3xl font-extrabold">{t("landing.voiceTitle")}</h2>
          <p className="mt-2 text-muted">{t("landing.voiceHint")}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button className="inline-flex min-h-12 items-center gap-2 rounded-full bg-brand px-4 font-bold text-white" onClick={() => void listen(i18n.language).then((text) => { setVoiceText(text); return askVoice(text); }).catch(() => askVoice(voiceText))}><Mic size={18} /> {t("landing.listen")}</button>
            <input className="min-h-12 flex-1 rounded-xl border border-line px-3" value={voiceText} onChange={(event) => setVoiceText(event.target.value)} />
            <button className="min-h-12 rounded-xl bg-amber px-4 font-bold text-brand-dark" onClick={() => void askVoice(voiceText)}>{t("common.submit")}</button>
          </div>
          {voiceAnswer ? <p className="mt-3 rounded-2xl bg-white p-4 shadow-card" role="status">{voiceAnswer}</p> : null}
        </section>

        <section className="mx-auto max-w-6xl px-4 py-8">
          <h2 className="font-display text-3xl font-extrabold">{t("landing.offlineTitle")}</h2>
          <button className="mt-4 min-h-11 rounded-xl bg-brand-dark px-4 font-bold text-white" onClick={() => {
            if (!offline) { setOffline(true); setSyncPhase("queued"); }
            else { setOffline(false); setSyncPhase("synced"); }
          }}>{offline ? t("landing.backOnline") : t("landing.simulate")}</button>
          <p className="mt-3 text-sm">{syncPhase === "queued" ? t("landing.queued") : syncPhase === "synced" ? t("sync.synced") : t("landing.offlineHint")}</p>
          {quote ? <p className="mt-2 text-sm">{material} · {weight} kg · {inr(quote.value)} · {offline ? t("sync.pending") : t("sync.synced")}</p> : null}
        </section>

        <section className="mx-auto max-w-6xl px-4 py-8">
          <h2 className="font-display text-3xl font-extrabold">{t("landing.traceTitle")}</h2>
          <form className="mt-4 flex flex-wrap gap-2" onSubmit={(event) => void lookup(event)}>
            <label className="flex-1 text-sm">{t("landing.lotLabel")}<input className="mt-1 min-h-11 w-full rounded-xl border border-line px-3" value={lotId} onChange={(event) => setLotId(event.target.value)} placeholder="LOT-" /></label>
            <button className="min-h-11 self-end rounded-xl bg-brand px-4 font-bold text-white" type="submit">{t("landing.lookup")}</button>
          </form>
          {verify ? (
            <div className="mt-4 rounded-2xl bg-white p-4 shadow-card">
              {verify.found ? (
                <>
                  <p className="font-bold">{String(verify.lot_id)} · {String(verify.status)}</p>
                  <p>{String(verify.material)} · {String(verify.weight_kg)} kg · {String(verify.city)}</p>
                  <ol className="mt-2 text-sm">{((verify.timeline as { event: string; at: string }[]) || []).map((row) => <li key={row.at}>{row.event} · {row.at}</li>)}</ol>
                </>
              ) : <p>{t("public.notFound")}</p>}
            </div>
          ) : null}
        </section>

        <section className="mx-auto max-w-6xl px-4 py-8" aria-label={t("public.map")}>
          <h2 className="font-display text-3xl font-extrabold">{t("landing.mapTitle")}</h2>
          <div className="mt-4 h-80 overflow-hidden rounded-2xl">
            <MapContainer center={[17.45, 78.45]} zoom={10} scrollWheelZoom={false}>
              <TileLayer attribution='&copy; OpenStreetMap' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              {pins.map((pin) => (
                <Marker key={pin.business_name} position={[pin.lat, pin.lng]}>
                  <Popup>{pin.business_name} · {pin.city} · {pin.verified ? t("common.verified") : ""}</Popup>
                </Marker>
              ))}
              {areas.map((area) => <Circle key={area.city} center={area.city === "Pune" ? [18.52, 73.85] : [17.4, 78.48]} radius={Math.max(area.weight_kg * 40, 500)} pathOptions={{ color: "#176b52" }} />)}
            </MapContainer>
          </div>
        </section>

        <section id="safety" className="mx-auto max-w-6xl px-4 py-8">
          <h2 className="font-display text-3xl font-extrabold">{t("landing.safetyTitle")}</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-4">
            {[{ icon: Battery, key: "battery" }, { icon: ShieldAlert, key: "crt" }, { icon: Flame, key: "burn" }, { icon: HardHat, key: "ppe" }].map((card) => (
              <article key={card.key} className="rounded-2xl bg-white p-4 shadow-card">
                <card.icon aria-hidden />
                <h3 className="mt-2 font-bold">{t(`landing.safe.${card.key}`)}</h3>
                <p className="text-sm text-muted">{t(`landing.safe.${card.key}Body`)}</p>
              </article>
            ))}
          </div>
          <p className="mt-4 text-sm">{t("landing.emergencyExplain")}</p>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-8">
          <h2 className="font-display text-3xl font-extrabold">{t("landing.voicesTitle")}</h2>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            {quotes.map((item) => (
              <blockquote key={item.name} className="rounded-2xl bg-white p-4 shadow-card">
                <p>{item.quote[i18n.language] || item.quote.en}</p>
                <footer className="mt-3 text-sm font-bold">{item.name} · {t(`landing.role.${item.role}`)} · {item.city}</footer>
              </blockquote>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-3xl px-4 py-8">
          <h2 className="font-display text-3xl font-extrabold">{t("landing.faqTitle")}</h2>
          {faqs.map((n) => (
            <div key={n} className="mt-3 rounded-2xl bg-white shadow-card">
              <button className="min-h-12 w-full px-4 text-left font-bold" aria-expanded={openFaq === n} onClick={() => setOpenFaq(openFaq === n ? 0 : n)}>{t(`landing.faq.q${n}`)}</button>
              {openFaq === n ? <p className="px-4 pb-4 text-sm text-muted">{t(`landing.faq.a${n}`)}</p> : null}
            </div>
          ))}
        </section>

        <section className="bg-brand-dark px-4 py-12 text-white">
          <div className="mx-auto max-w-6xl">
            <h2 className="font-display text-3xl font-extrabold">{t("landing.ctaTitle")}</h2>
            <p className="mt-2 max-w-xl">{t("landing.ctaBody")}</p>
            <Link className="mt-4 inline-block min-h-12 rounded-2xl bg-amber px-5 py-3 font-bold text-brand-dark" to="/login#demo">{t("landing.tryDemo")}</Link>
          </div>
        </section>
      </main>
      <footer className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-8 text-sm">
        <p>{t("landing.footer")}</p>
        <div className="flex gap-3">
          <a href={API_URL}>{t("landing.api")}</a>
          <Link to="/community">{t("nav.community")}</Link>
          <Link to="/verify/LOT-">{t("public.verify")}</Link>
        </div>
      </footer>
    </div>
  );
}
