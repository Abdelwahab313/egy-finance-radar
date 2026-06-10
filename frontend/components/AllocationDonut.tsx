"use client";

import { useState } from "react";
import { AllocationDonutProps } from "@/components/props";
import { bucketLabel, pct } from "@/lib/format";

const C = 2 * Math.PI * 64;

const BUCKET_COLOR: Record<string, string> = {
  stable_bluechip: "var(--b-stable)",
  growth: "var(--b-growth)",
  value: "var(--b-value)",
  watchlist: "var(--muted)",
  speculative: "var(--s-edu)",
};

const SECTOR_PALETTE = [
  "var(--s-bank)",
  "var(--s-realestate)",
  "var(--s-chem)",
  "var(--s-telecom)",
  "var(--s-finserv)",
  "var(--s-fintech)",
  "var(--s-industrials)",
  "var(--s-staples)",
  "var(--s-edu)",
  "var(--s-tobacco)",
  "var(--s-metals)",
  "var(--s-health)",
];

export default function AllocationDonut(props: AllocationDonutProps) {
  const [mode, setMode] = useState<"bucket" | "sector">("bucket");

  const source = mode === "bucket" ? props.bucket : props.sector;
  const entries = Object.entries(source).sort((a, b) => b[1] - a[1]);

  const colorFor = (key: string, i: number) =>
    mode === "bucket"
      ? BUCKET_COLOR[key] ?? "var(--muted)"
      : SECTOR_PALETTE[i % SECTOR_PALETTE.length];

  const labelFor = (key: string) =>
    mode === "bucket"
      ? bucketLabel[key as keyof typeof bucketLabel] ?? key
      : key;

  let cumulative = 0;

  return (
    <section className="card span-4">
      <div className="card-head">
        <h3>Allocation</h3>
        <div className="seg-toggle">
          <button
            className={mode === "bucket" ? "on" : undefined}
            onClick={() => setMode("bucket")}
          >
            Bucket
          </button>
          <button
            className={mode === "sector" ? "on" : undefined}
            onClick={() => setMode("sector")}
          >
            Sector
          </button>
        </div>
      </div>
      <div className="donut-wrap">
        <div style={{ position: "relative", width: "172px", height: "172px" }}>
          <svg className="donut-svg" width="172" height="172" viewBox="0 0 172 172">
            <circle cx="86" cy="86" r="64" fill="none" stroke="var(--panel-3)" strokeWidth="20" />
            {entries.map(([key, ratio], i) => {
              const dasharray = `${ratio * C} ${C}`;
              const dashoffset = `${-cumulative * C}`;
              cumulative += ratio;
              return (
                <circle
                  key={key}
                  cx="86"
                  cy="86"
                  r="64"
                  fill="none"
                  strokeWidth="20"
                  style={{
                    stroke: colorFor(key, i),
                    strokeDasharray: dasharray,
                    strokeDashoffset: dashoffset,
                  }}
                />
              );
            })}
          </svg>
          <div className="donut-center">
            <div className="dc-big num">{props.centerValue}</div>
            <div className="dc-sub">model EGP</div>
          </div>
        </div>
        <div className="legend">
          {entries.map(([key, ratio], i) => (
            <div className="li" key={key}>
              <span className="sw" style={{ background: colorFor(key, i) }}></span>
              <span className="nm">{labelFor(key)}</span>
              <span className="pc num">{pct(ratio, 1)}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
