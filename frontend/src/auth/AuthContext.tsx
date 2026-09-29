import { createContext, useContext, useEffect, useState } from "react";
import i18n from "../i18n";
import { api } from "../lib/api";
import { syncNow } from "../sync/engine";

export interface SessionUser {
  id: string;
  name: string;
  phone: string;
  role: "collector" | "recycler" | "admin";
  is_demo?: boolean;
  preferred_language: string;
  referral_code: string;
  profile?: {
    area?: string;
    city?: string;
    lat?: number | null;
    lng?: number | null;
    materials?: string[];
    emergency_contact?: string | null;
    low_data_mode?: boolean;
    voice_nav_enabled?: boolean;
    image_quality?: number;
    status?: string;
    business_name?: string;
    availability?: string;
    rejection_reason?: string | null;
    address?: string;
    licence_number?: string;
    rating?: number;
    reliability_score?: number;
  };
}

interface AuthValue {
  user: SessionUser | null;
  ready: boolean;
  login: (phone: string, password: string) => Promise<SessionUser>;
  demoLogin: (role: "collector" | "recycler" | "admin") => Promise<SessionUser>;
  logout: () => void;
  refresh: () => Promise<void>;
  setUser: (user: SessionUser) => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUserState] = useState<SessionUser | null>(null);
  const [ready, setReady] = useState(false);

  function apply(next: SessionUser | null) {
    setUserState(next);
    if (next?.preferred_language) {
      localStorage.setItem("kabadi_lang", next.preferred_language);
      void i18n.changeLanguage(next.preferred_language);
    }
  }

  async function refresh() {
    const me = await api<SessionUser>("/api/auth/me");
    apply(me);
  }

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      setReady(true);
      return;
    }
    refresh()
      .catch(() => localStorage.removeItem("token"))
      .finally(() => setReady(true));
  }, []);

  useEffect(() => {
    const run = () => void syncNow();
    window.addEventListener("online", run);
    return () => window.removeEventListener("online", run);
  }, []);

  useEffect(() => {
    if (!user) return;
    const timer = window.setInterval(() => {
      void api<{ token: string; user: SessionUser }>("/api/auth/refresh", { method: "POST" })
        .then((res) => {
          localStorage.setItem("token", res.token);
          apply(res.user);
        })
        .catch(() => undefined);
    }, 20 * 60 * 1000);
    return () => window.clearInterval(timer);
  }, [user?.id]);

  async function login(phone: string, password: string) {
    const res = await api<{ token: string; user: SessionUser }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ phone, password }),
    });
    localStorage.setItem("token", res.token);
    apply(res.user);
    return res.user;
  }

  async function demoLogin(role: "collector" | "recycler" | "admin") {
    const res = await api<{ token: string; user: SessionUser }>("/api/auth/demo-login", {
      method: "POST",
      body: JSON.stringify({ role }),
    });
    localStorage.setItem("token", res.token);
    apply(res.user);
    return res.user;
  }

  function logout() {
    localStorage.removeItem("token");
    apply(null);
  }

  return <AuthContext.Provider value={{ user, ready, login, demoLogin, logout, refresh, setUser: apply }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("auth");
  return ctx;
}
