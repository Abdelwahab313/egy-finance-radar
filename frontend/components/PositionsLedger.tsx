"use client";

import { useState } from "react";
import { PositionsLedgerProps } from "@/components/props";
import { grp, num, pct, signed, signedPct, dir, compactEgp, bucketLabel } from "@/lib/format";
import { Tag, Sig, Bkt, Star, ScoreBar } from "@/components/primitives";
import { Bucket } from "@/lib/types";

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
];

export default function PositionsLedger(props: PositionsLedgerProps) {
  const [tab, setTab] = useState<"holdings" | "model" | "universe">("holdings");

  return (
    <section className="card tablecard span-12">
      <div className="segbar">
        <button className={tab === "holdings" ? "on" : ""} onClick={() => setTab("holdings")}>
          My Orders &amp; Holdings
        </button>
        <button className={tab === "model" ? "on" : ""} onClick={() => setTab("model")}>
          Model Portfolio
        </button>
        <button className={tab === "universe" ? "on" : ""} onClick={() => setTab("universe")}>
          EGX Universe
        </button>
      </div>
      {tab === "holdings" && <HoldingsPane {...props} />}
      {tab === "model" && <ModelPane {...props} />}
      {tab === "universe" && <UniversePane {...props} />}
    </section>
  );
}

function HoldingsPane(props: PositionsLedgerProps) {
  const { holdings, holdingsNote } = props;
  const hasLots = !!holdings && holdings.lots.length > 0;

  return (
    <div>
      {hasLots && (
        <div className="tc-head">
          <div className="tc-substats">
            <div className="tss">
              <div className="k">Cost Basis</div>
              <div className="v num">{grp(holdings!.cost_basis_total)}</div>
            </div>
            <div className="tss">
              <div className="k">Market Value</div>
              <div className="v num">{grp(holdings!.market_value_total)}</div>
            </div>
            <div className="tss">
              <div className="k">Unrealized</div>
              <div className={`v num ${dir(holdings!.unrealized_pnl_total)}`}>
                {signed(holdings!.unrealized_pnl_total)} · {signedPct(holdings!.unrealized_pct_total ?? undefined)}
              </div>
            </div>
            <div className="tss">
              <div className="k">Uninvested</div>
              <div className={`v num ${dir(holdings!.cash_uninvested)}`}>{signed(holdings!.cash_uninvested)}</div>
            </div>
          </div>
        </div>
      )}

      {props.addOrderSlot}

      {!hasLots ? (
        <div className="statebox">Log a placed order above — it persists and is marked to a live price.</div>
      ) : (
        <>
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  <th className="l">Symbol / Name</th>
                  <th className="l">Horizon</th>
                  <th>Shares</th>
                  <th>Entry</th>
                  <th>Last</th>
                  <th>Cost</th>
                  <th>Value</th>
                  <th>P&amp;L</th>
                  <th>Signal</th>
                  <th>Stop</th>
                  <th>Target</th>
                </tr>
              </thead>
              <tbody>
                {holdings!.lots.map((lot) => (
                  <tr key={lot.symbol}>
                    <td className="l">
                      <div className="sym-cell">
                        <span className="s">{lot.symbol}</span>
                        <span className="n">{lot.name}</span>
                      </div>
                    </td>
                    <td className="l">
                      <Tag kind={lot.horizon} />
                    </td>
                    <td className="mono">{lot.shares}</td>
                    <td className="mono">{num(lot.entry_price, 2)}</td>
                    <td className={lot.price != null ? "mono" : "mono faint"}>
                      {lot.price != null ? num(lot.price, 2) : <span style={{ color: "var(--faint)" }}>—</span>}
                    </td>
                    <td className="mono">{grp(lot.cost_basis)}</td>
                    <td className="mono">{grp(lot.market_value)}</td>
                    <td className={`plcell ${dir(lot.unrealized_pnl)}`}>
                      {signed(lot.unrealized_pnl)} <small>({signedPct(lot.unrealized_pct ?? undefined)})</small>
                    </td>
                    <td className="l">
                      <Sig signal={lot.signal} />
                    </td>
                    <td className={lot.stop_loss != null ? "mono" : "mono faint"}>
                      {lot.stop_loss != null ? num(lot.stop_loss, 2) : "—"}
                    </td>
                    <td className={lot.take_profit != null ? "mono" : "mono faint"}>
                      {lot.take_profit != null ? num(lot.take_profit, 2) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {holdingsNote && <div className="tnote">▸ {holdingsNote}</div>}
        </>
      )}
    </div>
  );
}

function ModelPane(props: PositionsLedgerProps) {
  const { positions, bucketExposure, sectorExposure, excludedBySignal, modelNotes } = props;

  const bucketRows = Object.entries(bucketExposure).sort((a, b) => b[1] - a[1]);
  const sectorRows = Object.entries(sectorExposure).sort((a, b) => b[1] - a[1]);

  return (
    <div>
      <div className="expose">
        <div>
          <h5>Exposure by bucket</h5>
          {bucketRows.map(([k, v]) => (
            <div className="ebar" key={k}>
              <span className="nm">{bucketLabel[k as Bucket] ?? k}</span>
              <div className="tr">
                <div className="fl" style={{ width: `${v * 100}%`, background: BUCKET_COLOR[k] ?? "var(--muted)" }} />
              </div>
              <span className="pc num">{pct(v, 1)}</span>
            </div>
          ))}
        </div>
        <div>
          <h5>Exposure by sector group</h5>
          {sectorRows.map(([k, v], i) => (
            <div className="ebar" key={k}>
              <span className="nm">{k}</span>
              <div className="tr">
                <div className="fl" style={{ width: `${v * 100}%`, background: SECTOR_PALETTE[i % SECTOR_PALETTE.length] }} />
              </div>
              <span className="pc num">{pct(v, 1)}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th className="l">Symbol / Name</th>
              <th className="l">Bucket</th>
              <th className="l">Sleeve</th>
              <th className="l">Signal</th>
              <th>Price</th>
              <th>Shares</th>
              <th>Value</th>
              <th>Weight</th>
              <th>Stop</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => (
              <tr key={p.symbol}>
                <td className="l">
                  <div className="sym-cell">
                    <span className="s">{p.symbol}</span>
                    <span className="n">{p.name}</span>
                  </div>
                </td>
                <td className="l">
                  <Bkt bucket={p.bucket} />
                </td>
                <td className="l">
                  <Tag kind={p.sleeve} />
                </td>
                <td className="l">
                  <Sig signal={p.signal} />
                </td>
                <td className="mono">{num(p.price, 2)}</td>
                <td className="mono">{p.shares}</td>
                <td className="mono">{grp(p.notional)}</td>
                <td className="mono">{pct(p.actual_weight, 1)}</td>
                <td className={p.stop_loss != null ? "mono" : "mono faint"}>
                  {p.stop_loss != null ? num(p.stop_loss, 2) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {excludedBySignal && excludedBySignal.length > 0 && (
        <div className="tnote">
          ▸ Excluded by signal (EXIT/AVOID): <span className="err">{excludedBySignal.join(", ")}</span>
        </div>
      )}
      {modelNotes?.map((n, i) => (
        <div className="tnote" key={i}>
          ▸ {n}
        </div>
      ))}
    </div>
  );
}

function UniversePane(props: PositionsLedgerProps) {
  const { stocks, shortlist } = props;

  return (
    <div>
      <div className="tc-head">
        <span className="meta" style={{ fontSize: 11.5, color: "var(--muted)" }}>
          {stocks.length} curated EGX names · score-ranked · ★ = shortlist
        </span>
      </div>

      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th className="l">Symbol</th>
              <th className="l">Sector</th>
              <th className="l">Bucket</th>
              <th>Score</th>
              <th>Price</th>
              <th>Mkt Cap</th>
              <th>P/E</th>
              <th>Div</th>
              <th>β</th>
              <th>1Y</th>
              <th>★</th>
            </tr>
          </thead>
          <tbody>
            {stocks.map((s) => (
              <tr key={s.symbol}>
                <td className="l mono" style={{ color: "var(--text)" }}>
                  {s.symbol}
                </td>
                <td className="l">{s.sector}</td>
                <td className="l">
                  <Bkt bucket={s.bucket} />
                </td>
                <td>
                  <ScoreBar score={s.score} bucket={s.bucket} />
                </td>
                <td className="mono">{num(s.metrics.price, 2)}</td>
                <td className="mono">{compactEgp(s.metrics.market_cap)}</td>
                <td className="mono">{num(s.metrics.pe, 1)}</td>
                <td className="mono">{pct(s.metrics.dividend_yield, 1)}</td>
                <td className="mono">{num(s.metrics.beta, 2)}</td>
                <td className={`mono plcell ${dir(s.metrics.ret_1y)}`}>{signedPct(s.metrics.ret_1y)}</td>
                <td>
                  <Star on={shortlist.includes(s.symbol)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="tnote">
        Research / education only — not investment advice. Prices are nominal EGP via {props.source}.
      </div>
    </div>
  );
}
