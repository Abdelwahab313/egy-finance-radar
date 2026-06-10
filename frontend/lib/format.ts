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
