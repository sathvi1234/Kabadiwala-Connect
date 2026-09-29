import Dexie, { type Table } from "dexie";

export interface QueueItem {
  id: string;
  type: string;
  payload: Record<string, unknown>;
  photoBase64?: string;
  status: "pending" | "failed" | "synced";
  attempts: number;
  nextAttempt: number;
  error?: string;
}

export interface PriceRow {
  id: string;
  material: string;
  market: string;
  price_per_kg: number;
  source: string;
  date: string;
}

export interface MetaRow {
  key: string;
  value: string;
}

class KabadiDB extends Dexie {
  queue!: Table<QueueItem, string>;
  prices!: Table<PriceRow, string>;
  recyclers!: Table<Record<string, unknown>, string>;
  meta!: Table<MetaRow, string>;

  constructor() {
    super("kabadiwala");
    this.version(1).stores({
      queue: "id, status, nextAttempt",
      prices: "id, material, market",
      recyclers: "recycler_id",
      meta: "key",
    });
  }
}

export const db = new KabadiDB();
