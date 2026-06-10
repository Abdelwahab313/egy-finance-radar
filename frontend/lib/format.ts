import { Bucket } from "./types";

export const egp = (v?: number, frac = 0) =>
  v == null ? "—" : `${v.toLocaleString("en-US", { maximumFractionDigits: frac, minimumFractionDigits: frac })} EGP`;

export const pct = (v?: number, frac = 1) =>
  v == null ? "—" : `${(v * 100).toFixed(frac)}%`;

export const num = (v?: number, frac = 1) =>
  v == null ? "—" : v.toFixed(frac);

export const compactEgp = (v?: number) => {
  if (v == null) return "—";
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}bn`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}m`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}k`;
  return v.toFixed(0);
};

/** Grouped number with no currency suffix — for `.num` cells (e.g. 21,875). */
export const grp = (v?: number, frac = 0) =>
  v == null
    ? "—"
    : v.toLocaleString("en-US", { maximumFractionDigits: frac, minimumFractionDigits: frac });

/** Signed grouped number with a leading ▲/▼-free +/− and the en-dash minus. */
export const signed = (v?: number, frac = 0) => {
  if (v == null) return "—";
  const s = Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: frac, minimumFractionDigits: frac });
  return v < 0 ? `−${s}` : `+${s}`;
};

/** Signed percent (value is already a ratio, e.g. 0.011 → "+1.1%"). */
export const signedPct = (v?: number, frac = 1) => {
  if (v == null) return "—";
  const s = (Math.abs(v) * 100).toFixed(frac);
  return v < 0 ? `−${s}%` : `+${s}%`;
};

/** direction → "pos" | "neg" | "" (used for .pos/.neg/.plcell classes). */
export const dir = (v?: number) => (v == null ? "" : v > 0 ? "pos" : v < 0 ? "neg" : "");

/** Bucket enum → the css modifier used by .bkt / score colors. */
export const bucketSlug: Record<Bucket, string> = {
  stable_bluechip: "stable",
  value: "value",
  growth: "growth",
  watchlist: "watchlist",
  speculative: "speculative",
};

/** Signal string → the css modifier used by .sig. */
export const sigSlug = (signal?: string) =>
  (signal ?? "").toLowerCase().replace(/[^a-z]/g, "") || "nodata";

export const bucketLabel: Record<Bucket, string> = {
  stable_bluechip: "Stable blue-chip",
  value: "Value",
  growth: "Growth",
  watchlist: "Watchlist",
  speculative: "Speculative",
};

export const bucketColor: Record<Bucket, string> = {
  stable_bluechip: "#2ecc71",
  value: "#3498db",
  growth: "#d4af37",
  watchlist: "#8b98a9",
  speculative: "#e74c3c",
};
