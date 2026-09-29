import { useEffect, useMemo, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion, useReducedMotion } from "framer-motion";
import { Bell, Menu, Moon, Search, Sun, X } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { useTheme } from "../theme/ThemeContext";
import { EmergencyButton, LangSelect } from "./Bits";
import { ProductTour } from "./Tour";
import { queueCounts, syncNow } from "../sync/engine";
import { speak } from "../lib/speech";
import { api } from "../lib/api";

const LINKS: Record<string, { to: string; key: string }[]> = {
  collector: [
    { to: "/app/collector", key: "nav.dashboard" },
    { to: "/app/collector/lots", key: "nav.lots" },
    { to: "/app/collector/recyclers", key: "nav.recyclers" },
    { to: "/app/collector/prices", key: "nav.prices" },
    { to: "/app/collector/pickups", key: "nav.pickups" },
    { to: "/app/collector/transactions", key: "nav.transactions" },
    { to: "/app/collector/ai", key: "nav.ai" },
    { to: "/app/collector/safety", key: "nav.safety" },
    { to: "/app/collector/rewards", key: "nav.rewards" },
    { to: "/app/collector/tutorials", key: "nav.tutorials" },
    { to: "/app/collector/settings", key: "nav.settings" },
  ],
  recycler: [
    { to: "/app/recycler", key: "nav.dashboard" },
    { to: "/app/recycler/pickups", key: "nav.pickups" },
    { to: "/app/recycler/offers", key: "nav.offers" },
    { to: "/app/recycler/scan", key: "nav.scan" },
    { to: "/app/recycler/payments", key: "nav.payments" },
    { to: "/app/recycler/ratings", key: "nav.ratings" },
    { to: "/app/recycler/analytics", key: "nav.analytics" },
    { to: "/app/recycler/profile", key: "nav.profile" },
  ],
  admin: [
    { to: "/app/admin", key: "nav.dashboard" },
    { to: "/app/admin/verification", key: "nav.verification" },
    { to: "/app/admin/users", key: "nav.users" },
    { to: "/app/admin/prices", key: "nav.prices" },
    { to: "/app/admin/disputes", key: "nav.disputes" },
    { to: "/app/admin/audit", key: "nav.audit" },
    { to: "/app/admin/sync", key: "nav.sync" },
    { to: "/app/admin/analytics", key: "nav.analytics" },
  ],
};

export function Shell() {
  const { t, i18n } = useTranslation();
  const { user, logout } = useAuth();
  const { dark, toggle } = useTheme();
  const reduced = useReducedMotion();
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [notesOpen, setNotesOpen] = useState(false);
  const [notes, setNotes] = useState<{ id: string; title: string; body: string; read: boolean }[]>([]);
  const [query, setQuery] = useState("");
  const [counts, setCounts] = useState({ pending: 0, failed: 0 });
  const location = useLocation();
  const navigate = useNavigate();
  const role = user?.role || "collector";
  const links = LINKS[role];
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return links.filter((link) => t(link.key).toLowerCase().includes(q));
  }, [query, links, t, i18n.language]);

  useEffect(() => {
    const load = () => void queueCounts().then(setCounts);
    load();
    window.addEventListener("kabadi-sync", load);
    return () => window.removeEventListener("kabadi-sync", load);
  }, []);

  useEffect(() => {
    void api<{ id: string; title: string; body: string; read: boolean }[]>("/api/notifications").then(setNotes).catch(() => setNotes([]));
  }, [location.pathname]);

  useEffect(() => {
    if (!user?.profile?.voice_nav_enabled) return;
    const parts = location.pathname.split("/").filter(Boolean);
    const key = parts[0] === "app" ? parts[2] || "dashboard" : parts[1] || "dashboard";
    const spoken = t(`voiceNav.${key}`, { defaultValue: "" });
    if (spoken) speak(spoken, i18n.language);
  }, [location.pathname, user?.profile?.voice_nav_enabled, i18n.language, t]);

  const label = counts.failed ? t("sync.failed") : counts.pending ? `${t("sync.pending")} ${counts.pending}` : t("sync.synced");

  function go(path: string) {
    setOpen(false);
    setQuery("");
    navigate(path);
  }

  const nav = (
    <nav className="space-y-1" aria-label={t("nav.main")}>
      {links.map((link) => (
        <NavLink
          key={link.to}
          to={link.to}
          end={link.to.split("/").length === 3}
          data-testid={`nav-${link.key.split(".")[1]}`}
          onClick={() => setOpen(false)}
          className={({ isActive }) => `flex min-h-11 items-center rounded-xl px-3 py-3 text-sm ${isActive ? "bg-brand-light text-white" : "text-[#dcebe6] hover:bg-white/10"}`}
        >
          {t(link.key)}
        </NavLink>
      ))}
      <button data-testid="logout" className="mt-4 min-h-11 w-full rounded-xl px-3 text-left text-sm text-[#dcebe6]" onClick={() => { logout(); navigate("/login"); }}>{t("common.logout")}</button>
    </nav>
  );

  return (
    <div className="min-h-screen bg-canvas text-ink">
      {user?.is_demo ? (
        <div className="fixed inset-x-0 top-0 z-50 flex flex-wrap items-center justify-center gap-3 bg-amber px-3 py-2 text-sm font-semibold text-brand-dark">
          <span>{t("demo.banner")}</span>
          <button className="min-h-11 rounded-lg bg-brand-dark px-3 text-white" onClick={() => void api("/api/auth/demo-reset", { method: "POST" }).then(() => window.location.reload())}>{t("demo.reset")}</button>
          <button className="min-h-11 rounded-lg border border-brand-dark px-3" onClick={() => { logout(); navigate("/"); }}>{t("demo.exit")}</button>
        </div>
      ) : null}
      <aside className={`fixed bottom-0 top-0 z-30 hidden overflow-auto bg-brand-dark p-4 text-white md:block ${collapsed ? "w-20" : "w-[255px]"} ${user?.is_demo ? "pt-16" : ""}`}>
        <div className="flex items-center justify-between px-2 pb-4">
          {collapsed ? null : <div className="text-xl font-extrabold">{t("app.name")}<small className="mt-1 block text-[11px] font-medium opacity-70">{t("app.tag")}</small></div>}
          <button aria-label={t("shell.collapse")} className="min-h-11 min-w-11 rounded-lg text-white" onClick={() => setCollapsed((value) => !value)}>{collapsed ? "›" : "‹"}</button>
        </div>
        {collapsed ? null : nav}
      </aside>
      {open ? (
        <div className="fixed inset-0 z-40 bg-black/40 md:hidden" onClick={() => setOpen(false)}>
          <aside className="h-full w-72 overflow-auto bg-brand-dark p-4 text-white" onClick={(event) => event.stopPropagation()}>{nav}</aside>
        </div>
      ) : null}
      <main className={`${collapsed ? "md:ml-20" : "md:ml-[255px]"} ${user?.is_demo ? "pt-14" : ""}`}>
        <header className="glass sticky top-0 z-20 flex flex-wrap items-center justify-between gap-3 border-b border-white/40 px-4 py-3 md:px-8">
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <button aria-label={t("shell.menu")} className="min-h-11 min-w-11 rounded-lg bg-brand-dark text-white md:hidden" onClick={() => setOpen(true)}><Menu className="mx-auto" size={18} /></button>
            <div className="relative min-w-0 flex-1">
              <label className="flex min-h-11 items-center gap-2 rounded-xl border border-line bg-white px-3">
                <Search size={16} aria-hidden />
                <span className="sr-only">{t("shell.search")}</span>
                <input className="w-full bg-transparent outline-none" value={query} placeholder={t("shell.search")} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => {
                  if (event.key === "Enter" && query.toUpperCase().startsWith("LOT-")) go(`/${role === "recycler" ? "app/recycler" : "app/collector"}/lots/${query.trim()}`);
                  else if (event.key === "Enter" && filtered[0]) go(filtered[0].to);
                }} />
              </label>
              {filtered.length ? (
                <div className="absolute z-30 mt-1 w-full rounded-xl border border-line bg-white p-2 shadow-card">
                  {filtered.map((link) => <button key={link.to} className="block min-h-11 w-full rounded-lg px-2 text-left" onClick={() => go(link.to)}>{t(link.key)}</button>)}
                </div>
              ) : null}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <LangSelect />
            <button aria-label={t("shell.theme")} className="min-h-11 min-w-11 rounded-xl border border-line bg-white" onClick={toggle}>{dark ? <Moon className="mx-auto" size={16} /> : <Sun className="mx-auto" size={16} />}</button>
            <div className="relative">
              <button aria-label={t("shell.notifications")} className="min-h-11 min-w-11 rounded-xl border border-line bg-white" onClick={() => setNotesOpen((value) => !value)}><Bell className="mx-auto" size={16} /></button>
              {notesOpen ? (
                <div className="absolute right-0 z-30 mt-2 w-72 rounded-2xl border border-line bg-white p-3 shadow-card">
                  <div className="mb-2 flex items-center justify-between"><b>{t("shell.notifications")}</b><button aria-label={t("common.close")} onClick={() => setNotesOpen(false)}><X size={16} /></button></div>
                  {notes.length === 0 ? <p className="text-sm text-muted">{t("shell.emptyNotes")}</p> : notes.slice(0, 6).map((note) => (
                    <button key={note.id} className="block w-full border-t border-line py-2 text-left text-sm" onClick={() => void api(`/api/notifications/${note.id}/read`, { method: "POST" })}>
                      <b>{note.title}</b>
                      <span className="block text-muted">{note.body}</span>
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
            <span id="tour-sync" className="rounded-full bg-[#e8f6f0] px-3 py-2 text-xs font-bold text-brand">{navigator.onLine ? label : t("common.offline")}</span>
            {role === "collector" ? <button className="min-h-11 rounded-lg bg-brand px-3 text-xs font-bold text-white" onClick={() => void syncNow()}>{t("sync.now")}</button> : null}
          </div>
        </header>
        <motion.div key={location.pathname} className="px-4 pb-28 md:px-8" initial={reduced ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
          <Outlet />
        </motion.div>
      </main>
      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-line bg-white md:hidden" aria-label={t("nav.main")}>
        {links.slice(0, 5).map((link) => (
          <NavLink key={link.to} to={link.to} end={link.to.split("/").length === 3} className={({ isActive }) => `min-h-14 px-1 py-2 text-center text-[11px] font-semibold ${isActive ? "text-brand" : "text-muted"}`}>{t(link.key)}</NavLink>
        ))}
      </nav>
      <EmergencyButton />
      {user?.is_demo ? <ProductTour role={role} /> : null}
    </div>
  );
}
