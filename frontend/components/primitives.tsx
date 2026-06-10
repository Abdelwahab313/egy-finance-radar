"use client";

import { Bucket } from "@/lib/types";
import { bucketLabel, bucketSlug, sigSlug } from "@/lib/format";

/* Small shared atoms used across the dashboard sections. They emit the exact
   CSS classes defined in app/globals.css (ported from the mockup). */

/** Mono uppercase section label with a trailing hairline rule. */
export function Eyebrow({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <p className="eyebrow" style={style}>
      {children}
    </p>
  );
}

/** Core/Tactical/Satellite pill. */
export function Tag({ kind }: { kind?: "core" | "tactical" | "satellite" | null }) {
  if (!kind) return <span style={{ color: "var(--faint)" }}>—</span>;
  const label = kind.charAt(0).toUpperCase() + kind.slice(1);
  return <span className={`tag ${kind}`}>{label}</span>;
}

/** BUY / HOLD / NO_DATA / EXIT … signal pill. */
export function Sig({ signal }: { signal?: string | null }) {
  if (!signal) return <span style={{ color: "var(--faint)" }}>—</span>;
  return <span className={`sig ${sigSlug(signal)}`}>{signal}</span>;
}

/** Bucket dot + label. */
export function Bkt({ bucket }: { bucket: Bucket }) {
  return <span className={`bkt ${bucketSlug[bucket]}`}>{bucketLabel[bucket]}</span>;
}

/** Shortlist star. */
export function Star({ on }: { on: boolean }) {
  return <span className={`star${on ? "" : " off"}`}>★</span>;
}

/** Gradient color for a 0–100 score bar — mirrors the mockup ramp. */
export function scoreGradient(score: number, bucket?: Bucket): string {
  if (score >= 75) return "linear-gradient(90deg,var(--gold-deep),var(--gold))";
  if (score >= 45) return "linear-gradient(90deg,#4a7fd6,#7aa5ff)";
  if (bucket === "growth") return "linear-gradient(90deg,#8a6fb0,var(--b-growth))";
  return "linear-gradient(90deg,#5f6c7d,#8b98a9)";
}

/** Right-aligned score value + track. */
export function ScoreBar({ score, bucket }: { score: number; bucket?: Bucket }) {
  return (
    <div className="scorewrap">
      <span className="scoreval">{score.toFixed(0)}</span>
      <span className="scoretrack">
        <span
          className="scorefill"
          style={{ width: `${Math.min(100, Math.max(0, score))}%`, background: scoreGradient(score, bucket) }}
        />
      </span>
    </div>
  );
}
