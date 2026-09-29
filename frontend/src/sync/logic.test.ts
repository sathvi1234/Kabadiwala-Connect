import { describe, expect, it } from "vitest";
import en from "../i18n/en.json";
import hi from "../i18n/hi.json";
import mr from "../i18n/mr.json";
import { backoff, estimateFromCache, resolveConflict } from "../sync/logic";

function keys(value: unknown, prefix = ""): string[] {
  if (typeof value !== "object" || value === null) return [prefix.slice(0, -1)];
  return Object.entries(value as Record<string, unknown>).flatMap(([key, child]) => keys(child, `${prefix}${key}.`));
}

describe("i18n", () => {
  it("keeps English, Hindi and Marathi keys aligned", () => {
    const english = keys(en).sort();
    expect(keys(hi).sort()).toEqual(english);
    expect(keys(mr).sort()).toEqual(english);
  });
});

describe("offline queue helpers", () => {
  it("backs off and caps delay", () => {
    expect(backoff(0)).toBe(1000);
    expect(backoff(2)).toBe(4000);
    expect(backoff(10)).toBe(60000);
  });
  it("resolves sync conflicts", () => {
    expect(resolveConflict("price", "open")).toBe("server_wins");
    expect(resolveConflict("lot_draft", "open")).toBe("client_wins");
    expect(resolveConflict("lot_draft", "handed_over")).toBe("server_wins");
  });
  it("estimates value from a cached price", () => {
    expect(estimateFromCache(2.5, 420)).toBe(1050);
  });
});
