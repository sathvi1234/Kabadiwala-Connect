export function backoff(attempt: number) {
  return Math.min(60_000, 1000 * 2 ** attempt);
}

export function resolveConflict(kind: "price" | "lot_draft", serverStatus: string) {
  if (kind === "price") return "server_wins" as const;
  if (serverStatus === "open" || serverStatus === "draft") return "client_wins" as const;
  return "server_wins" as const;
}

export function estimateFromCache(weightKg: number, pricePerKg: number) {
  return Math.round(weightKg * pricePerKg * 100) / 100;
}
