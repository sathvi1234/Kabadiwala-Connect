import { createContext, useContext, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";
import iconUrl from "leaflet/dist/images/marker-icon.png";
import iconRetina from "leaflet/dist/images/marker-icon-2x.png";
import shadowUrl from "leaflet/dist/images/marker-shadow.png";
import { useAuth } from "../auth/AuthContext";

L.Icon.Default.mergeOptions({ iconUrl, iconRetinaUrl: iconRetina, shadowUrl });

const ToastContext = createContext<(message: string) => void>(() => undefined);

export function useToast() {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [message, setMessage] = useState("");
  function toast(next: string) {
    setMessage(next);
    window.setTimeout(() => setMessage(""), 2800);
  }
  return (
    <ToastContext.Provider value={toast}>
      {children}
      {message ? <div className="fixed bottom-24 right-4 z-50 max-w-xs rounded-xl bg-[#173f33] px-4 py-3 text-sm text-white">{message}</div> : null}
    </ToastContext.Provider>
  );
}

export function Card({ title, children, className = "" }: { title?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-line bg-white p-4 shadow-sm ${className}`}>
      {title ? <h3 className="mb-3 text-base font-semibold">{title}</h3> : null}
      {children}
    </section>
  );
}

export function Btn({ children, kind = "primary", ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { kind?: "primary" | "secondary" | "danger" }) {
  const styles = {
    primary: "bg-brand text-white",
    secondary: "bg-[#edf2f0] text-[#245f4e]",
    danger: "bg-danger text-white",
  }[kind];
  return (
    <button {...props} className={`inline-flex min-h-11 items-center justify-center rounded-lg px-4 text-sm font-bold disabled:opacity-50 ${styles} ${props.className || ""}`}>
      {children}
    </button>
  );
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-xs text-muted">{label}</span>
      {children}
    </label>
  );
}

export const inputClass = "min-h-11 w-full rounded-lg border border-[#dce2ea] bg-white px-3 outline-none";

export function Badge({ children, tone = "ok" }: { children: React.ReactNode; tone?: "ok" | "pending" | "danger" | "blue" }) {
  const tones = { ok: "bg-[#e6f6ef] text-[#13724f]", pending: "bg-[#fff3d9] text-[#966000]", danger: "bg-[#fdeaea] text-[#a83232]", blue: "bg-[#e8f0ff] text-[#315fa8]" };
  return <span className={`inline-block rounded-full px-2 py-1 text-xs font-bold ${tones[tone]}`}>{children}</span>;
}

export function States({ loading, error, empty }: { loading?: boolean; error?: string; empty?: boolean }) {
  const { t } = useTranslation();
  if (loading) return <p className="text-sm text-muted">{t("common.loading")}</p>;
  if (error) return <p className="text-sm text-danger">{error}</p>;
  if (empty) return <p className="text-sm text-muted">{t("common.empty")}</p>;
  return null;
}

export function VerifiedMark() {
  const { t } = useTranslation();
  return <Badge>{`✓ ${t("common.verified")}`}</Badge>;
}

export function MapPanel({ points, lowData }: { points: { lat: number; lng: number; label: string }[]; lowData?: boolean }) {
  const center = points[0] ? ([points[0].lat, points[0].lng] as [number, number]) : ([17.4, 78.48] as [number, number]);
  if (lowData) {
    return (
      <ul className="space-y-2 text-sm">
        {points.map((point) => (
          <li key={point.label}>
            {point.label} · {point.lat.toFixed(3)}, {point.lng.toFixed(3)}
          </li>
        ))}
      </ul>
    );
  }
  return (
    <MapContainer center={center} zoom={11} className="h-64 w-full rounded-xl">
      <TileLayer attribution='&copy; OpenStreetMap' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {points.map((point) => (
        <Marker key={point.label} position={[point.lat, point.lng]}>
          <Popup>{point.label}</Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}

export function EmergencyButton() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const contact = user?.profile?.emergency_contact;

  async function share(kind: "wa" | "sms") {
    const position = await new Promise<GeolocationPosition>((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject));
    const text = `Emergency ${user?.name || ""}. https://maps.google.com/?q=${position.coords.latitude},${position.coords.longitude}`;
    const phone = contact ? (contact.startsWith("91") ? contact : `91${contact}`) : "";
    const url = kind === "wa" ? `https://wa.me/${phone}?text=${encodeURIComponent(text)}` : `sms:${contact || ""}?body=${encodeURIComponent(text)}`;
    window.open(url, "_blank");
  }

  if (user?.role !== "collector") return null;
  return (
    <>
      <button id="tour-emergency" className="fixed bottom-20 right-4 z-40 min-h-14 rounded-full bg-danger px-5 font-bold text-white shadow-lg md:bottom-4" onClick={() => setOpen(true)}>
        {t("safety.emergency")}
      </button>
      {open ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4" onClick={() => setOpen(false)}>
          <div className="w-full max-w-md rounded-2xl bg-white p-4" onClick={(event) => event.stopPropagation()}>
            <h3 className="text-lg font-bold">{t("safety.emergency")}</h3>
            <p className="mt-2 text-sm text-muted">{t("safety.emergencyHelp")}</p>
            {!contact ? <p className="mt-2 text-sm">{t("safety.noContact")}</p> : null}
            <div className="mt-4 flex flex-wrap gap-2">
              <a className="min-h-11 rounded-lg bg-brand px-4 py-3 font-bold text-white" href="tel:112">{t("safety.call112")}</a>
              <a className="min-h-11 rounded-lg bg-brand px-4 py-3 font-bold text-white" href="tel:108">{t("safety.call108")}</a>
              <Btn onClick={() => void share("wa")}>{t("safety.whatsapp")}</Btn>
              <Btn kind="secondary" onClick={() => void share("sms")}>{t("safety.sms")}</Btn>
            </div>
            <p className="mt-3 text-xs text-muted">{i18n.language}</p>
            <Btn kind="secondary" className="mt-3" onClick={() => setOpen(false)}>{t("common.close")}</Btn>
          </div>
        </div>
      ) : null}
    </>
  );
}

export function LangSelect() {
  const { i18n, t } = useTranslation();
  const { user, refresh } = useAuth();
  async function change(lang: string) {
    localStorage.setItem("kabadi_lang", lang);
    await i18n.changeLanguage(lang);
    if (user) {
      await apiPatchLang(lang);
      await refresh();
    }
  }
  return (
    <select aria-label={t("auth.language")} className="min-h-11 rounded-lg border-0 bg-white px-2 text-brand-dark" value={i18n.language} onChange={(event) => void change(event.target.value)}>
      <option value="en">English</option>
      <option value="hi">हिन्दी</option>
      <option value="mr">मराठी</option>
    </select>
  );
}

async function apiPatchLang(lang: string) {
  const { api } = await import("../lib/api");
  await api("/api/auth/me", { method: "PATCH", body: JSON.stringify({ preferred_language: lang }) });
}

export function BackLink({ to }: { to: string }) {
  const { t } = useTranslation();
  return <Link className="text-sm font-bold text-brand" to={to}>{t("common.back")}</Link>;
}
