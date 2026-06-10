"use client";

import { motion } from "framer-motion";
import { HeroBandProps } from "@/components/props";
import { grp, signed, signedPct, pct } from "@/lib/format";

export default function HeroBand(props: HeroBandProps) {
  const {
    equity,
    pnl,
    pnlPct,
    deployedPct,
    costBasis,
    overUnder,
    cash,
    tbillAmount,
    tbillYield,
  } = props;

  const pnlPos = pnl >= 0;

  return (
    <motion.section
      className="hero"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <div className="hero-grid">
        <div className="hcell">
          <div className="hlabel">Total Equity · marked to live</div>
          <div className="hbig h-equity">
            {grp(equity)}
            <span
              style={{
                fontSize: 18,
                color: "var(--muted)",
                WebkitTextFillColor: "var(--muted)",
              }}
            >
              {" "}
              EGP
            </span>
          </div>
          <div className="h-sub">market value of all placed lots</div>
        </div>

        <div className="hcell">
          <div className="hlabel">Unrealized P&amp;L</div>
          <div className={`hbig h-pl ${pnlPos ? "pos" : "neg"}`}>
            {signed(pnl)} <span style={{ fontSize: 15 }}>EGP</span>
          </div>
          {pnlPct != null ? (
            <span className={`chip-pl ${pnlPos ? "pos" : "neg"}`}>
              {(pnlPos ? "▲ " : "▼ ") + signedPct(pnlPct) + " on cost"}
            </span>
          ) : (
            <span className={`chip-pl ${pnlPos ? "pos" : "neg"}`}>
              {(pnlPos ? "▲ " : "▼ ") + signed(pnl)}
            </span>
          )}
        </div>

        <div className="hcell">
          <div className="hlabel">Deployed</div>
          <div className="hbig h-mid">
            {(deployedPct * 100).toFixed(0)}
            <span style={{ fontSize: 18, color: "var(--muted)" }}>%</span>
          </div>
          <div className="deploy-track">
            <div
              className="deploy-fill"
              style={{ width: `${Math.min(100, deployedPct * 100)}%` }}
            ></div>
          </div>
          <div className="h-sub" style={{ marginTop: 6 }}>
            cost basis {grp(costBasis)} ·{" "}
            {overUnder < 0 ? (
              <span className="neg">{signed(overUnder)} over</span>
            ) : overUnder > 0 ? (
              <span style={{ color: "var(--muted)" }}>
                {signed(overUnder)} buffer
              </span>
            ) : (
              "fully deployed"
            )}
          </div>
        </div>

        <div className="hcell">
          <div className="hlabel">Cash / Anchor</div>
          <div className="hbig h-mid">{grp(cash)}</div>
          <div className="h-sub">
            {tbillAmount != null
              ? "+ " + grp(tbillAmount) + " T-bill sleeve @ " + pct(tbillYield ?? undefined, 1)
              : "no T-bill sleeve"}
          </div>
        </div>
      </div>
    </motion.section>
  );
}
