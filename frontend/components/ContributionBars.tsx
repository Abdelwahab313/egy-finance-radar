"use client";

import { ContributionBarsProps } from "@/components/props";
import { signed } from "@/lib/format";

export default function ContributionBars(props: ContributionBarsProps) {
  const { items, net } = props;
  const maxAbs = Math.max(1, ...items.map((i) => Math.abs(i.pnl)));

  return (
    <section className="card span-4">
      <div className="card-head">
        <h3>P&amp;L Contribution</h3>
        <span className="meta">EGP · per holding</span>
      </div>
      <div className="contrib">
        {items.map((item) => {
          const halfPct = (Math.abs(item.pnl) / maxAbs) * 46;
          return (
            <div className="cbar" key={item.symbol}>
              <span className="sym">{item.symbol}</span>
              <div className="track">
                <span className="axis" />
                {item.pnl > 0 && (
                  <span className="fill pos" style={{ width: `${halfPct}%` }} />
                )}
                {item.pnl < 0 && (
                  <span className="fill neg" style={{ width: `${halfPct}%` }} />
                )}
              </div>
              {item.pnl === 0 ? (
                <span className="amt" style={{ color: "var(--faint)" }}>
                  0
                </span>
              ) : (
                <span className={`amt ${item.pnl > 0 ? "pos" : "neg"}`}>
                  {signed(item.pnl)}
                </span>
              )}
            </div>
          );
        })}
      </div>
      <div
        style={{
          marginTop: 16,
          paddingTop: 13,
          borderTop: "1px solid var(--border-soft)",
          display: "flex",
          justifyContent: "space-between",
          fontSize: 12,
        }}
      >
        <span style={{ color: "var(--muted)" }}>Net unrealized</span>
        <span className={`num ${net >= 0 ? "pos" : "neg"}`} style={{ fontWeight: 600 }}>
          {signed(net)} EGP
        </span>
      </div>
    </section>
  );
}
