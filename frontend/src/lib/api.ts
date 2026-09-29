const configured = import.meta.env.VITE_API_URL;
export const API_URL = configured === undefined ? "http://localhost:8000" : configured;

export function wsBase() {
  if (API_URL) return API_URL.replace(/^http/, "ws");
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}`;
}

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string) {
    super(code);
    this.status = status;
    this.code = code;
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const token = localStorage.getItem("token");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    let code = "error";
    try {
      const body = await response.json();
      code = body?.detail?.code || (typeof body?.detail === "string" ? body.detail : "error");
    } catch {
      code = "error";
    }
    throw new ApiError(response.status, code);
  }
  const type = response.headers.get("content-type") || "";
  if (type.includes("application/json")) return response.json() as Promise<T>;
  return response.blob() as Promise<T>;
}

export function inr(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}
