"use client";

import { InvestmentPlanProps } from "@/components/props";
import { egp, pct } from "@/lib/format";
import { Eyebrow } from "@/components/primitives";

export default function InvestmentPlan({ plan }: InvestmentPlanProps) {
  return (
    <>
      <Eyebrow style={{ marginTop: 34 }}>Investment Plan</Eyebrow>
      <section className="card span-12">
        <div className="sleeves">
          {Object.entries(plan.sleeves).map(([name, s], i) => {
            const wt = s.pct_of_capital != null ? pct(s.pct_of_capital, 0) : s.horizon;
            const ix = s.symbols && s.symbols.length ? s.symbols.join(" · ") : s.horizon;
            const ds = s.review ?? s.rule ?? "";
            return (
              <div className={`sleeve t${(i % 3) + 1}`} key={name}>
                <div className="st">
                  <span className="nm">{name}</span>
                  <span className="wt num">{wt}</span>
                </div>
                <div className="ix">{ix}</div>
                <div className="ds">{ds}</div>
              </div>
            );
          })}
        </div>
        <div className="plan-grid">
          <div>
            <h5>Sell &amp; rotation rules</h5>
            <ul className="rules">
              {plan.sell_rules.map((r, i) => {
                const idx = r.indexOf(":");
                const label = idx > 0 ? r.slice(0, idx) : "Rule";
                const text = idx > 0 ? r.slice(idx + 1).trim() : r;
                return (
                  <li key={i}>
                    <b>{label}</b>
                    {text}
                  </li>
                );
              })}
            </ul>
            <div className="cadence">
              <span title={plan.cadence.monthly}>CADENCE · MONTHLY</span>
              <span title={plan.cadence.quarterly}>CADENCE · QUARTERLY</span>
            </div>
          </div>
          <div className="income">
            <h5>Expected annual income</h5>
            <div className="irow">
              <span className="lab">T-bills</span>
              <span className="v num">{egp(plan.expected_income_egp.tbill_annual)}</span>
            </div>
            <div className="irow">
              <span className="lab">Dividends (net)</span>
              <span className="v num">{egp(plan.expected_income_egp.net_dividends_annual)}</span>
            </div>
            <div className="irow total">
              <span className="lab">Total</span>
              <span className="v num">{egp(plan.expected_income_egp.total_annual)}</span>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
