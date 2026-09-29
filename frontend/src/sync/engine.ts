import { api } from "../lib/api";
import { db } from "../db/db";
import { backoff } from "./logic";

export async function queueCounts() {
  const rows = await db.queue.toArray();
  return {
    pending: rows.filter((row) => row.status === "pending").length,
    failed: rows.filter((row) => row.status === "failed").length,
  };
}

export async function enqueueLot(payload: Record<string, unknown>, photoBase64?: string) {
  const id = crypto.randomUUID();
  await db.queue.add({
    id,
    type: "create_lot",
    payload,
    photoBase64,
    status: "pending",
    attempts: 0,
    nextAttempt: Date.now(),
  });
  window.dispatchEvent(new Event("kabadi-sync"));
  return id;
}

export async function syncNow() {
  if (!navigator.onLine || !localStorage.getItem("token")) return queueCounts();
  const items = (await db.queue.toArray()).filter((item) => item.status !== "synced" && item.nextAttempt <= Date.now());
  for (const item of items) {
    try {
      const res = await api<{ results: { status: string; error?: string }[] }>("/api/sync/push", {
        method: "POST",
        body: JSON.stringify({
          operations: [
            {
              idempotency_key: item.id,
              type: item.type,
              payload: item.payload,
              photo_base64: item.photoBase64,
            },
          ],
        }),
      });
      const result = res.results[0];
      if (!result || result.status === "failed") throw new Error(result?.error || "failed");
      item.status = "synced";
      await db.queue.put(item);
    } catch (error) {
      item.attempts += 1;
      item.status = "failed";
      item.nextAttempt = Date.now() + backoff(item.attempts);
      item.error = error instanceof Error ? error.message : "failed";
      await db.queue.put(item);
    }
  }
  window.dispatchEvent(new Event("kabadi-sync"));
  return queueCounts();
}

export async function cachePrices(city: string, items: { material: string; price_per_kg: number | null; source: string; date: string; market: string }[]) {
  for (const item of items) {
    if (item.price_per_kg === null) continue;
    await db.prices.put({
      id: `${item.material}|${item.market || city}`,
      material: item.material,
      market: item.market || city,
      price_per_kg: item.price_per_kg,
      source: item.source,
      date: item.date,
    });
  }
}

export async function cachedPrice(material: string, city: string) {
  return (await db.prices.get(`${material}|${city}`)) || (await db.prices.where("material").equals(material).first());
}
