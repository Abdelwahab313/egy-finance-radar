"use client";

import { AccountSummaryProps } from "@/components/props";
import { grp, pct } from "@/lib/format";

export default function AccountSummary(props: AccountSummaryProps) {
  return (
    <section className="card span-4">
      <div className="card-head">
        <h3>Account Summary</h3>
        <span className="meta">broker: {props.broker}</span>
      </div>
      <div className="acct">
        <div className="arow">
          <div className="lab">Starting capital</div>
          <div className="val num">{grp(props.startingCapital)}</div>
        </div>
        <div className="arow">
          <div className="lab">
            Equity{" "}
            <small>
              model
              {props.equityPct != null ? ` · ${pct(props.equityPct, 0)} of capital` : ""}
            </small>
          </div>
          <div className="val num">{grp(props.equity)}</div>
        </div>
        {props.tbillAmount != null && (
          <div className="arow">
            <div className="lab">
              T-bill sleeve{" "}
              <small>{props.tbillYield != null ? `${pct(props.tbillYield, 1)} yield` : "rolling"}</small>
            </div>
            <div className="val num">
              {grp(props.tbillAmount)}
              {props.tbillIncome != null && <small>{grp(props.tbillIncome)} EGP / yr</small>}
            </div>
          </div>
        )}
        <div className="arow">
          <div className="lab">
            Cash <small>uninvested</small>
          </div>
          <div className="val num">{grp(props.cash)}</div>
        </div>
      </div>
    </section>
  );
}
