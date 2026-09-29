import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Html5Qrcode } from "html5-qrcode";
import { ApiError, api } from "../lib/api";
import { useAuth } from "../auth/AuthContext";
import { Badge, Btn, Card, Field, inputClass, LangSelect, States } from "../components/Bits";

const MATERIALS = ["PCB", "Cable", "Battery", "CRT", "LCD", "Plastic", "Metal", "Aluminium", "Copper", "Paper/Cardboard"];

function messageOf(t: (key: string) => string, error: unknown) {
  return error instanceof ApiError ? t(`errors.${error.code}`) : t("common.error");
}

const DEMOS = [
  { role: "collector" as const, test: "demo-collector", name: "demo.collectorName", text: "demo.collectorBlurb" },
  { role: "recycler" as const, test: "demo-recycler", name: "demo.recyclerName", text: "demo.recyclerBlurb" },
  { role: "admin" as const, test: "demo-admin", name: "demo.adminName", text: "demo.adminBlurb" },
];

export function LoginPage() {
  const { t } = useTranslation();
  const { login, demoLogin } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"password" | "otp">("password");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [devOtp, setDevOtp] = useState("");
  const [error, setError] = useState("");
  const [preparing, setPreparing] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      if (mode === "otp") {
        const res = await api<{ token: string; user: { role: string } }>("/api/auth/login/otp", { method: "POST", body: JSON.stringify({ phone, otp }) });
        localStorage.setItem("token", res.token);
        window.location.assign(`/app/${res.user.role}`);
        return;
      }
      if (email.trim()) {
        const res = await api<{ token: string; user: { role: string } }>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
        localStorage.setItem("token", res.token);
        window.location.assign(`/app/${res.user.role}`);
        return;
      }
      const user = await login(phone, password);
      navigate(`/app/${user.role}`);
    } catch (err) {
      setError(messageOf(t, err));
    }
  }

  async function enter(role: "collector" | "recycler" | "admin") {
    setPreparing(true);
    try {
      const account = await demoLogin(role);
      window.setTimeout(() => navigate(`/app/${account.role}`), 700);
    } catch (err) {
      setPreparing(false);
      setError(messageOf(t, err));
    }
  }

  return (
    <main className="grid min-h-screen lg:grid-cols-2">
      <section className="hidden bg-brand-dark p-10 text-white lg:flex lg:flex-col lg:justify-between">
        <p className="font-display text-3xl font-extrabold">{t("app.name")}</p>
        <p className="max-w-md text-lg">{t("demo.panel")}</p>
      </section>
      <section className="mx-auto flex w-full max-w-xl flex-col justify-center p-4">
        <div className="mb-4 flex items-center justify-between"><h1 className="font-display text-2xl font-extrabold text-brand-dark">{t("auth.login")}</h1><LangSelect /></div>
        <div className="mb-3 flex gap-2">
          <button className="min-h-11 rounded-xl bg-white px-3 font-bold" onClick={() => setMode("otp")}>{t("auth.otpLogin")}</button>
          <button className="min-h-11 rounded-xl bg-white px-3 font-bold" onClick={() => setMode("password")}>{t("auth.passwordLogin")}</button>
        </div>
        <Card>
          <form className="space-y-3" onSubmit={submit}>
            <Field label={t("auth.phone")}><input className={inputClass} value={phone} onChange={(e) => setPhone(e.target.value)} /></Field>
            {mode === "password" ? <Field label={t("auth.email")}><input className={inputClass} value={email} onChange={(e) => setEmail(e.target.value)} /></Field> : null}
            {mode === "password" ? <Field label={t("auth.password")}><input className={inputClass} type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field> : <Field label={t("auth.otp")}><input className={inputClass} value={otp} onChange={(e) => setOtp(e.target.value)} /></Field>}
            {mode === "otp" ? <Btn type="button" kind="secondary" onClick={() => void api<{ dev_otp?: string }>("/api/auth/otp/request", { method: "POST", body: JSON.stringify({ phone }) }).then((res) => setDevOtp(res.dev_otp || ""))}>{t("auth.sendOtp")}</Btn> : null}
            {devOtp ? <p className="text-sm">{t("auth.otpSent")} {devOtp}</p> : null}
            <Btn type="submit">{t("auth.login")}</Btn>
            <States error={error} />
          </form>
          <div className="mt-4 flex flex-col gap-2 text-sm font-bold text-brand">
            <Link to="/register">{t("auth.registerCollector")}</Link>
          </div>
        </Card>
        <section id="demo" className="mt-6">
          <h2 className="font-display text-xl font-extrabold">{t("demo.title")}</h2>
          <p className="text-sm text-muted">{t("demo.subtitle")}</p>
          <div className="mt-3 grid gap-3">
            {DEMOS.map((card) => (
              <article key={card.role} className="rounded-2xl border border-line bg-white p-4 shadow-card">
                <Badge>{t(`demo.role.${card.role}`)}</Badge>
                <h3 className="mt-2 font-bold">{t(card.name)}</h3>
                <p className="text-sm text-muted">{t(card.text)}</p>
                <button data-testid={card.test} className="mt-3 min-h-11 rounded-xl bg-amber px-4 font-bold text-brand-dark" onClick={() => void enter(card.role)}>{t("demo.enter", { name: t(card.name) })}</button>
              </article>
            ))}
          </div>
        </section>
        {preparing ? <div className="fixed inset-0 z-50 flex items-center justify-center bg-brand-dark/80 text-white"><p className="font-display text-2xl">{t("demo.preparing")}</p></div> : null}
      </section>
    </main>
  );
}

export function RegisterHub() {
  const { t } = useTranslation();
  return (
    <main className="mx-auto max-w-3xl p-4">
      <h1 className="font-display text-3xl font-extrabold">{t("auth.registerTitle")}</h1>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Link className="rounded-2xl bg-white p-5 shadow-card" to="/register/collector"><b>{t("auth.registerCollector")}</b><p className="text-sm text-muted">{t("demo.collectorBlurb")}</p></Link>
        <Link className="rounded-2xl bg-white p-5 shadow-card" to="/register/recycler"><b>{t("auth.registerRecycler")}</b><p className="text-sm text-muted">{t("demo.recyclerBlurb")}</p></Link>
      </div>
      <p className="mt-4 text-sm"><Link className="font-bold text-brand" to="/login#demo">{t("demo.title")}</Link></p>
    </main>
  );
}

export function RegisterCollector() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", phone: "", password: "", otp: "", area: "", city: "Hyderabad", language: "hi", referral: "", emergency: "" });
  const [materials, setMaterials] = useState<string[]>(["PCB"]);
  const [photo, setPhoto] = useState<File | null>(null);
  const [proof, setProof] = useState<File | null>(null);
  const [devOtp, setDevOtp] = useState("");
  const [error, setError] = useState("");
  function set<K extends keyof typeof form>(key: K, value: string) { setForm({ ...form, [key]: value }); }
  async function sendOtp() {
    const res = await api<{ dev_otp?: string }>("/api/auth/otp/request", { method: "POST", body: JSON.stringify({ phone: form.phone }) });
    setDevOtp(res.dev_otp || "");
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    const body = new FormData();
    Object.entries({ ...form, preferred_language: form.language, referral_code: form.referral, emergency_contact: form.emergency, materials: JSON.stringify(materials) }).forEach(([key, value]) => body.append(key, value));
    if (photo) body.append("profile_photo", photo);
    if (proof) body.append("id_proof", proof);
    try {
      const res = await api<{ token: string }>("/api/auth/register/collector", { method: "POST", body });
      localStorage.setItem("token", res.token);
      window.location.assign("/app/collector");
    } catch (err) {
      setError(messageOf(t, err));
    }
  }
  return (
    <main className="mx-auto max-w-xl p-4">
      <h1 className="mb-4 text-2xl font-extrabold">{t("auth.registerCollector")}</h1>
      <Card>
        <form className="grid gap-3 sm:grid-cols-2" onSubmit={submit}>
          <Field label={t("auth.name")}><input className={inputClass} value={form.name} onChange={(e) => set("name", e.target.value)} required /></Field>
          <Field label={t("auth.phone")}><input className={inputClass} value={form.phone} onChange={(e) => set("phone", e.target.value)} required /></Field>
          <Field label={t("auth.password")}><input className={inputClass} type="password" value={form.password} onChange={(e) => set("password", e.target.value)} required /></Field>
          <Field label={t("auth.otp")}><input className={inputClass} value={form.otp} onChange={(e) => set("otp", e.target.value)} required /></Field>
          <Field label={t("auth.area")}><input className={inputClass} value={form.area} onChange={(e) => set("area", e.target.value)} required /></Field>
          <Field label={t("common.city")}><input className={inputClass} value={form.city} onChange={(e) => set("city", e.target.value)} required /></Field>
          <Field label={t("auth.language")}>
            <select className={inputClass} value={form.language} onChange={(e) => set("language", e.target.value)}><option value="en">English</option><option value="hi">हिन्दी</option><option value="mr">मराठी</option></select>
          </Field>
          <Field label={t("auth.referral")}><input className={inputClass} value={form.referral} onChange={(e) => set("referral", e.target.value)} /></Field>
          <Field label={t("auth.emergency")}><input className={inputClass} value={form.emergency} onChange={(e) => set("emergency", e.target.value)} /></Field>
          <Field label={t("auth.photo")}><input className={inputClass} type="file" accept="image/*" onChange={(e) => setPhoto(e.target.files?.[0] || null)} /></Field>
          <Field label={t("auth.idProof")}><input className={inputClass} type="file" onChange={(e) => setProof(e.target.files?.[0] || null)} /></Field>
          <div className="sm:col-span-2">
            <p className="mb-1 text-xs text-muted">{t("auth.materials")}</p>
            <div className="flex flex-wrap gap-2">{MATERIALS.map((code) => <label key={code} className="min-h-11 rounded-lg border px-3 py-2 text-sm"><input type="checkbox" checked={materials.includes(code)} onChange={() => setMaterials(materials.includes(code) ? materials.filter((item) => item !== code) : [...materials, code])} /> {code}</label>)}</div>
          </div>
          <div className="flex flex-wrap gap-2 sm:col-span-2">
            <Btn type="button" kind="secondary" onClick={() => void sendOtp()}>{t("auth.sendOtp")}</Btn>
            <Btn type="submit">{t("common.submit")}</Btn>
          </div>
          {devOtp ? <p className="text-sm sm:col-span-2">{t("auth.otpSent")} {devOtp}</p> : null}
          <States error={error} />
        </form>
      </Card>
    </main>
  );
}

export function RegisterRecycler() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", phone: "", password: "", otp: "", business_name: "", licence_number: "", address: "", city: "Hyderabad", lat: "", lng: "", language: "en", working_hours: '{"mon":"09:00-18:00"}' });
  const [materials, setMaterials] = useState<string[]>(["PCB"]);
  const [docs, setDocs] = useState<FileList | null>(null);
  const [devOtp, setDevOtp] = useState("");
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    const body = new FormData();
    Object.entries({ ...form, preferred_language: form.language, materials: JSON.stringify(materials) }).forEach(([k, v]) => body.append(k, v));
    if (docs) Array.from(docs).forEach((file) => body.append("documents", file));
    try {
      const res = await api<{ token: string }>("/api/auth/register/recycler", { method: "POST", body });
      localStorage.setItem("token", res.token);
      window.location.assign("/app/recycler");
    } catch (err) {
      setError(messageOf(t, err));
    }
  }
  return (
    <main className="mx-auto max-w-xl p-4">
      <h1 className="mb-2 text-2xl font-extrabold">{t("auth.registerRecycler")}</h1>
      <p className="mb-4 text-sm text-muted">{t("auth.pendingNote")}</p>
      <Card>
        <form className="grid gap-3 sm:grid-cols-2" onSubmit={submit}>
          {(["name", "phone", "password", "otp", "business_name", "licence_number", "address", "city", "lat", "lng"] as const).map((key) => (
            <Field key={key} label={t(`auth.${key === "business_name" ? "business" : key === "licence_number" ? "licence" : key === "city" ? "language" : key}`, { defaultValue: key })}>
              <input className={inputClass} type={key === "password" ? "password" : "text"} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} required={key !== "otp" ? true : true} />
            </Field>
          ))}
          <Field label={t("auth.hours")}><input className={inputClass} value={form.working_hours} onChange={(e) => setForm({ ...form, working_hours: e.target.value })} /></Field>
          <Field label={t("auth.documents")}><input className={inputClass} type="file" multiple onChange={(e) => setDocs(e.target.files)} /></Field>
          <div className="sm:col-span-2 flex flex-wrap gap-2">{MATERIALS.map((code) => <label key={code} className="text-sm"><input type="checkbox" checked={materials.includes(code)} onChange={() => setMaterials(materials.includes(code) ? materials.filter((m) => m !== code) : [...materials, code])} /> {code}</label>)}</div>
          <div className="flex gap-2 sm:col-span-2">
            <Btn type="button" kind="secondary" onClick={() => void api<{ dev_otp?: string }>("/api/auth/otp/request", { method: "POST", body: JSON.stringify({ phone: form.phone }) }).then((res) => setDevOtp(res.dev_otp || ""))}>{t("auth.sendOtp")}</Btn>
            <Btn type="submit">{t("common.submit")}</Btn>
          </div>
          {devOtp ? <p className="sm:col-span-2">{devOtp}</p> : null}
          <States error={error} />
        </form>
      </Card>
    </main>
  );
}

export function VerifyPage() {
  const { lotId = "" } = useParams();
  const { t } = useTranslation();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  useEffect(() => { void api<Record<string, unknown>>(`/api/public/verify/${lotId}`).then(setData); }, [lotId]);
  if (!data) return <States loading />;
  if (!data.found) return <main className="p-6"><Card><p>{t("public.notFound")}</p></Card></main>;
  const verification = data.verification as Record<string, boolean>;
  const timeline = (data.timeline as { event: string; at: string }[]) || [];
  return (
    <main className="mx-auto max-w-lg p-4">
      <Card title={t("public.verify")}>
        <p className="text-sm text-muted">{t("public.noPii")}</p>
        <p className="mt-3 text-xl font-extrabold">{String(data.lot_id)}</p>
        <p>{String(data.material)} · {String(data.weight_kg)} kg · {String(data.city)}</p>
        <Badge>{String(data.status)}</Badge>
        <p className="mt-2 text-sm">GPS {verification.gps ? "✓" : "✗"} · Photo {verification.photo ? "✓" : "✗"} · Time {verification.time ? "✓" : "✗"}</p>
        {timeline.map((event) => <p key={event.at} className="border-l-2 border-brand py-2 pl-3 text-sm">{event.event} · {event.at}</p>)}
      </Card>
    </main>
  );
}

export function CommunityPage() {
  const { t } = useTranslation();
  const [data, setData] = useState<{ recyclers: { business_name: string; city: string; lat: number; lng: number; verified: boolean }[]; events: { title: string; city: string; starts_at: string }[]; areas: { city: string; weight_kg: number; lots: number }[] } | null>(null);
  useEffect(() => { void api<NonNullable<typeof data>>("/api/public/map").then(setData); }, []);
  if (!data) return <States loading />;
  return (
    <main className="mx-auto max-w-3xl space-y-4 p-4">
      <h1 className="text-2xl font-extrabold">{t("public.map")}</h1>
      <Card title={t("public.areas")}>{data.areas.map((area) => <p key={area.city}>{area.city}: {area.weight_kg} kg · {area.lots}</p>)}</Card>
      <Card title={t("public.drives")}>{data.events.map((event) => <p key={event.title}>{event.title} · {event.city} · {event.starts_at}</p>)}</Card>
      <Card title={t("nav.recyclers")}>{data.recyclers.map((row) => <p key={row.business_name}>{row.business_name} · {row.city} · {row.lat.toFixed(3)}, {row.lng.toFixed(3)}</p>)}</Card>
    </main>
  );
}

export function ScanPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [manual, setManual] = useState("");
  useEffect(() => {
    const scanner = new Html5Qrcode("qr-reader");
    scanner.start({ facingMode: "environment" }, { fps: 8, qrbox: 220 }, (text) => {
      void scanner.stop().finally(() => navigate(`/recycler/lots/${encodeURIComponent(text)}`));
    }, () => undefined).catch(() => undefined);
    return () => { scanner.stop().catch(() => undefined); };
  }, [navigate]);
  return (
    <Card title={t("nav.scan")}>
      <div id="qr-reader" className="overflow-hidden rounded-xl" />
      <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); navigate(`/recycler/lots/${manual}`); }}>
        <input className={inputClass} value={manual} onChange={(e) => setManual(e.target.value)} placeholder="LOT-" />
        <Btn type="submit">{t("common.submit")}</Btn>
      </form>
    </Card>
  );
}
