"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Snapshot, Plan, Sleeve, Recommendation } from "@/lib/types";
import { egp, pct, num, compactEgp, bucketLabel, bucketColor } from "@/lib/format";

const API = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default function Page() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  // latest recommendation per symbol (the /api/recommendations array is newest-first)
  const [recosBySym, setRecosBySym] = useState<Record<string, Recommendation>>({});

  const load = () =>
    fetch(`${API}/api/snapshot`)
      .then((r) => {
        if (!r.ok) throw new Error(`API ${r.status}`);
        return r.json();
      })
      .then(setSnap)
      .catch((e) =>
        setError(
          `Could not reach the backend at ${API}. Start it with: uvicorn app.main:app --port 8000 (and run the collector first). [${e.message}]`
        )
      );

  const loadRecos = () =>
    fetch(`${API}/api/recommendations`)
      .then((r) => (r.ok ? r.json() : []))
      .then((rows: Recommendation[]) => {
        const latest: Record<string, Recommendation> = {};
        // array is newest-first, so the first row seen per symbol is the latest
        for (const r of rows) if (!(r.symbol in latest)) latest[r.symbol] = r;
        setRecosBySym(latest);
      })
      .catch(() => {
        /* recommendations are best-effort — never block the dashboard */
      });

  useEffect(() => {
    load();
    loadRecos();
  }, []);

  if (error)
    return (
      <Shell>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--panel)] p-6 text-[var(--red)]">
          {error}
        </div>
      </Shell>
    );

  if (!snap)
    return (
      <Shell>
        <div className="text-[var(--muted)]">Loading EGX snapshot…</div>
      </Shell>
    );

  const pf = snap.portfolio;
  const invested = pf.invested_value + pf.entry_costs_total;
  const holdings = snap.holdings;

  return (
    <Shell>
      {/* Scene */}
      <section className="rounded-xl border border-[var(--border)] bg-gradient-to-br from-[var(--panel)] to-[var(--panel-2)] p-5">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h2 className="text-sm uppercase tracking-widest text-[var(--accent)]">
            EGX Scene · {snap.scene.as_of}
          </h2>
          <div className="flex items-center gap-3">
            <span className="text-xs text-[var(--muted)]">
              prices {snap.price_data_ok_count ?? snap.live_data_ok_count}/{snap.universe_size} ·
              β via {snap.index_source === "CASE30" ? "EGX30" : "proxy"} · {snap.source}
            </span>
            <RefreshButton onDone={() => { load(); loadRecos(); }} />
          </div>
        </div>
        <p className="mt-2 text-lg">{snap.scene.headline}</p>
        {snap.data_quality && (
          <p className="mt-2 text-xs text-[var(--muted)] border-l-2 border-[var(--accent)]/40 pl-2">
            Live: prices, P/E, P/B, β (β from an equal-weight proxy — Yahoo&apos;s ^CASE30 is unavailable).
            Static fallback (curated, June 2026):{" "}
            <span className="text-[var(--text)]">{snap.data_quality.mostly_static_fields.join(", ")}</span>.
            Wire EODHD for live fundamentals.
          </p>
        )}
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <Mini label="EGP / USD" value={snap.scene.egp_usd} />
          <Mini label="Inflation" value={snap.scene.inflation} />
          <Mini label="Policy rate" value={snap.scene.policy_rate} />
          {snap.scene.tbill_12m && <Mini label="12m T-bill" value={snap.scene.tbill_12m} />}
        </div>
        {snap.scene.tax_note && (
          <p className="mt-2 text-xs text-[var(--muted)]">Tax: {snap.scene.tax_note}</p>
        )}
        <div className="mt-4 grid sm:grid-cols-2 gap-3 text-sm">
          <Tags title="Tailwinds" items={snap.scene.tailwinds} color="var(--green)" />
          <Tags title="Risks" items={snap.scene.risks} color="var(--red)" />
        </div>
      </section>

      {/* Account summary */}
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat label="Starting capital" value={egp(pf.starting_capital)} />
        <Stat
          label="Equity (model)"
          value={egp(invested)}
          sub={pf.equity_pct != null ? `${pct(pf.equity_pct, 0)} of capital` : `incl. ${egp(pf.entry_costs_total, 2)} costs`}
        />
        {pf.tbill_sleeve ? (
          <Stat
            label="T-bill sleeve"
            value={egp(pf.tbill_sleeve.amount_egp)}
            sub={`${pct(pf.tbill_sleeve.annual_yield, 1)} → ${egp(pf.tbill_sleeve.expected_annual_income_egp)}/yr`}
          />
        ) : (
          <Stat label="Cash buffer" value={egp(pf.cash_remaining)} sub={`${pct(pf.cash_buffer_pct, 0)} target`} />
        )}
        <Stat label="Cash" value={egp(pf.cash_remaining)} sub={`broker: ${pf.broker}`} />
      </section>

      {/* My orders — user-placed lots, marked to live prices */}
      <section className="rounded-xl border border-[var(--accent)]/40 bg-[var(--panel)] p-5">
        <SectionTitle
          title="My Orders"
          subtitle={
            holdings && holdings.lots.length > 0
              ? `Placed ${holdings.as_of ?? ""} · ${pct(holdings.deployed_pct_of_capital, 0)} of capital deployed · marked to live prices`
              : "Log a placed order below — it persists and is marked to a live price."
          }
        />
        <AddOrderForm onAdded={load} />
        {holdings && holdings.lots.length > 0 && (
          <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4 mt-5">
            <Stat label="Cost basis" value={egp(holdings.cost_basis_total)} />
            <Stat label="Market value" value={egp(holdings.market_value_total)} />
            <Stat
              label="Unrealized P&L"
              value={egp(holdings.unrealized_pnl_total)}
              sub={pct(holdings.unrealized_pct_total ?? undefined)}
              tone={holdings.unrealized_pnl_total >= 0 ? "green" : "red"}
            />
            <Stat label="Uninvested" value={egp(holdings.cash_uninvested)} sub="vs 20k capital" />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[var(--muted)] border-b border-[var(--border)]">
                  <Th>Symbol</Th><Th>Horizon</Th><Th right>Shares</Th><Th right>Entry</Th><Th right>Last</Th>
                  <Th right>Cost</Th><Th right>Value</Th><Th right>P&L</Th>
                  <Th>Signal</Th><Th>Recommendation</Th><Th right>Stop</Th><Th right>Target</Th>
                </tr>
              </thead>
              <tbody>
                {holdings.lots.map((l) => (
                  <tr key={l.symbol} className="border-b border-[var(--border)]/50 hover:bg-[var(--panel-2)]">
                    <td className="py-3">
                      <div className="font-semibold">{l.symbol}</div>
                      <div className="text-xs text-[var(--muted)]">{l.name}</div>
                    </td>
                    <td><HorizonBadge horizon={l.horizon} /></td>
                    <td className="text-right tabular-nums">{l.shares}</td>
                    <td className="text-right tabular-nums">{egp(l.entry_price, 2)}</td>
                    <td className="text-right tabular-nums">{egp(l.price, 2)}</td>
                    <td className="text-right tabular-nums">{egp(l.cost_basis, 0)}</td>
                    <td className="text-right tabular-nums">{egp(l.market_value, 0)}</td>
                    <td className={`text-right tabular-nums ${ret(l.unrealized_pnl)}`}>
                      {egp(l.unrealized_pnl, 0)} <span className="text-xs">({pct(l.unrealized_pct ?? undefined)})</span>
                    </td>
                    <td><SignalPill signal={l.signal} /></td>
                    <td><RecoCell reco={recosBySym[l.symbol]} /></td>
                    <td className="text-right tabular-nums text-[var(--red)]">{egp(l.stop_loss ?? undefined, 2)}</td>
                    <td className="text-right tabular-nums text-[var(--green)]">{egp(l.take_profit ?? undefined, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {holdings.note && <p className="mt-3 text-xs text-[var(--muted)]">▸ {holdings.note}</p>}
          </>
        )}
      </section>

      {/* Portfolio (model) */}
      <section className="rounded-xl border border-[var(--border)] bg-[var(--panel)] p-5">
        <SectionTitle
          title="Model Portfolio"
          subtitle="Balanced value + growth, gated on the signal (no EXIT/AVOID names)"
        />
        <div className="grid lg:grid-cols-2 gap-4 mb-5">
          <ExposureBar title="By bucket" data={pf.bucket_exposure} colorFor={(k) => bucketColor[k as keyof typeof bucketColor] ?? "var(--muted)"} labelFor={(k) => bucketLabel[k as keyof typeof bucketLabel] ?? k} />
          <ExposureBar title="By sector group" data={pf.sector_group_exposure ?? pf.sector_exposure} />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[var(--muted)] border-b border-[var(--border)]">
                <Th>Symbol</Th><Th>Bucket</Th><Th>Sleeve</Th><Th>Signal</Th><Th right>Price</Th>
                <Th right>Shares</Th><Th right>Value</Th><Th right>Weight</Th><Th right>Stop</Th>
              </tr>
            </thead>
            <tbody>
              {pf.positions.map((p) => (
                <tr key={p.symbol} className="border-b border-[var(--border)]/50 hover:bg-[var(--panel-2)]">
                  <td className="py-3">
                    <div className="font-semibold">{p.symbol}</div>
                    <div className="text-xs text-[var(--muted)]">{p.name}</div>
                  </td>
                  <td><BucketBadge bucket={p.bucket} /></td>
                  <td><SleeveBadge sleeve={p.sleeve} /></td>
                  <td><SignalPill signal={p.signal} /></td>
                  <td className="text-right tabular-nums">{egp(p.price, 2)}</td>
                  <td className="text-right tabular-nums">{p.shares}</td>
                  <td className="text-right tabular-nums">{egp(p.notional, 0)}</td>
                  <td className="text-right tabular-nums">{pct(p.actual_weight)}</td>
                  <td className="text-right tabular-nums text-[var(--red)]">{egp(p.stop_loss ?? undefined, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {pf.excluded_by_signal && pf.excluded_by_signal.length > 0 && (
          <p className="mt-3 text-xs text-[var(--muted)]">
            ▸ Excluded by signal (EXIT/AVOID):{" "}
            <span className="text-[var(--red)]">{pf.excluded_by_signal.join(", ")}</span>
          </p>
        )}
        {pf.notes.map((n, i) => (
          <p key={i} className="mt-3 text-xs text-[var(--muted)]">▸ {n}</p>
        ))}
      </section>

      {/* Plan */}
      {pf.plan && <PlanSection plan={pf.plan} />}

      {/* Classification */}
      <section className="rounded-xl border border-[var(--border)] bg-[var(--panel)] p-5">
        <SectionTitle title="EGX Classification" subtitle={`${snap.stocks.length} curated names · shortlist: ${snap.shortlist.join(", ")}`} />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[var(--muted)] border-b border-[var(--border)]">
                <Th>Symbol</Th><Th>Sector</Th><Th>Bucket</Th><Th right>Score</Th>
                <Th right>Price</Th><Th right>Mkt cap</Th><Th right>P/E</Th>
                <Th right>Div yld</Th><Th right>Beta</Th><Th right>1Y</Th><Th>Shortlist</Th>
              </tr>
            </thead>
            <tbody>
              {snap.stocks.map((s) => {
                const inShort = snap.shortlist.includes(s.symbol);
                return (
                  <tr key={s.symbol} className="border-b border-[var(--border)]/50 hover:bg-[var(--panel-2)]">
                    <td className="py-2.5">
                      <div className="font-semibold">{s.symbol}</div>
                      <div className="text-xs text-[var(--muted)]">{s.name}</div>
                    </td>
                    <td className="text-[var(--muted)]">{s.sector}</td>
                    <td><BucketBadge bucket={s.bucket} /></td>
                    <td className="text-right tabular-nums">
                      <ScoreBar score={s.score} />
                    </td>
                    <td className="text-right tabular-nums">{egp(s.metrics.price, 2)}</td>
                    <td className="text-right tabular-nums">{compactEgp(s.metrics.market_cap)}</td>
                    <td className="text-right tabular-nums">{num(s.metrics.pe)}</td>
                    <td className="text-right tabular-nums">{pct(s.metrics.dividend_yield)}</td>
                    <td className="text-right tabular-nums">{num(s.metrics.beta, 2)}</td>
                    <td className={`text-right tabular-nums ${ret(s.metrics.ret_1y)}`}>{pct(s.metrics.ret_1y)}</td>
                    <td>{inShort ? <span className="text-[var(--accent)]">★</span> : <span className="text-[var(--border)]">·</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-[var(--muted)]">
          Research/education only — not investment advice. Prices are nominal EGP via {snap.source}.
        </p>
      </section>
    </Shell>
  );
}

/* ---------- presentational helpers ---------- */

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen max-w-6xl mx-auto px-4 py-8 flex flex-col gap-6">
      <nav className="flex items-center gap-4 text-sm">
        <Link href="/" className="text-[var(--accent)] font-medium">
          Dashboard
        </Link>
        <span className="text-[var(--border)]">·</span>
        <Link href="/investigate" className="text-[var(--muted)] hover:text-[var(--text)]">
          Investigate
        </Link>
      </nav>
      <header className="flex items-end justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            EGY<span className="text-[var(--accent)]">Finance</span>
          </h1>
          <p className="text-sm text-[var(--muted)]">
            Egyptian Exchange intelligence · 20,000 EGP balanced paper portfolio
          </p>
        </div>
      </header>
      {children}
    </main>
  );
}

const ret = (v?: number) => (v == null ? "" : v >= 0 ? "text-[var(--green)]" : "text-[var(--red)]");

const TODAY = () => new Date().toISOString().slice(0, 10);
const INPUT_CLS =
  "w-full rounded-lg bg-[var(--bg)]/40 border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--accent)]";

function AddOrderForm({ onAdded }: { onAdded: () => void }) {
  const [symbol, setSymbol] = useState("");
  const [shares, setShares] = useState("");
  const [entry, setEntry] = useState("");
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [tradedAt, setTradedAt] = useState(TODAY());
  const [horizon, setHorizon] = useState<"core" | "tactical">("core");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const res = await fetch(`${API}/api/orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: symbol.trim().toUpperCase(),
          shares: Number(shares),
          entry_price: Number(entry),
          side,
          traded_at: tradedAt || undefined,
          horizon,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `API ${res.status}`);
      }
      setSymbol("");
      setShares("");
      setEntry("");
      setSide("buy");
      setTradedAt(TODAY());
      setHorizon("core");
      await onAdded();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to add order.");
    } finally {
      setBusy(false);
    }
  };

  const valid =
    symbol.trim() && Number(shares) > 0 && Number(entry) > 0 && tradedAt;

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
      <Field label="Symbol" w="w-28">
        <input
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          placeholder="COMI"
          className={`${INPUT_CLS} uppercase`}
        />
      </Field>
      <Field label="Side" w="w-24">
        <select
          value={side}
          onChange={(e) => setSide(e.target.value as "buy" | "sell")}
          className={INPUT_CLS}
        >
          <option value="buy">Buy</option>
          <option value="sell">Sell</option>
        </select>
      </Field>
      <Field label="Shares" w="w-28">
        <input
          value={shares}
          onChange={(e) => setShares(e.target.value)}
          inputMode="decimal"
          placeholder="27"
          className={`${INPUT_CLS} tabular-nums`}
        />
      </Field>
      <Field label="Entry price (EGP)" w="w-36">
        <input
          value={entry}
          onChange={(e) => setEntry(e.target.value)}
          inputMode="decimal"
          placeholder="130.10"
          className={`${INPUT_CLS} tabular-nums`}
        />
      </Field>
      <Field label="Traded at" w="w-40">
        <input
          type="date"
          value={tradedAt}
          onChange={(e) => setTradedAt(e.target.value)}
          className={`${INPUT_CLS} tabular-nums`}
        />
      </Field>
      <Field label="Horizon" w="w-28">
        <select
          value={horizon}
          onChange={(e) => setHorizon(e.target.value as "core" | "tactical")}
          className={INPUT_CLS}
        >
          <option value="core">Core</option>
          <option value="tactical">Tactical</option>
        </select>
      </Field>
      <button
        type="submit"
        disabled={!valid || busy}
        className="rounded-lg bg-[var(--accent)] text-[var(--bg)] px-4 py-2 text-sm font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {busy ? "Adding…" : "Add order"}
      </button>
      {err && <span className="text-xs text-[var(--red)] basis-full">{err}</span>}
    </form>
  );
}

function Field({ label, w, children }: { label: string; w: string; children: React.ReactNode }) {
  return (
    <label className={`flex flex-col gap-1 ${w}`}>
      <span className="text-xs text-[var(--muted)]">{label}</span>
      {children}
    </label>
  );
}

function Th({ children, right }: { children: React.ReactNode; right?: boolean }) {
  return <th className={`font-medium pb-2 px-2 ${right ? "text-right" : ""}`}>{children}</th>;
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-[var(--bg)]/40 border border-[var(--border)] px-3 py-2">
      <div className="text-xs text-[var(--muted)]">{label}</div>
      <div className="font-semibold">{value}</div>
    </div>
  );
}

function Tags({ title, items, color }: { title: string; items: string[]; color: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-[var(--muted)] mb-1">{title}</div>
      <div className="flex flex-wrap gap-1.5">
        {items.map((t) => (
          <span key={t} className="text-xs rounded-full px-2.5 py-1 border" style={{ borderColor: color, color }}>
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}

function Stat({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "green" | "red" }) {
  const toneColor = tone === "green" ? "text-[var(--green)]" : tone === "red" ? "text-[var(--red)]" : "";
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--panel)] p-4">
      <div className="text-xs text-[var(--muted)]">{label}</div>
      <div className={`text-xl font-bold mt-1 tabular-nums ${toneColor}`}>{value}</div>
      {sub && <div className="text-xs text-[var(--muted)] mt-0.5">{sub}</div>}
    </div>
  );
}

const SIGNAL_COLOR: Record<string, string> = {
  BUY: "var(--green)",
  HOLD: "var(--accent)",
  TRIM: "var(--accent)",
  EXIT: "var(--red)",
  AVOID: "var(--red)",
};

function SignalPill({ signal }: { signal?: string }) {
  if (!signal) return <span className="text-[var(--border)]">·</span>;
  const c = SIGNAL_COLOR[signal] ?? "var(--muted)";
  return (
    <span className="text-xs rounded-md px-2 py-0.5 font-semibold whitespace-nowrap" style={{ color: c, backgroundColor: `${c}1a` }}>
      {signal}
    </span>
  );
}

function SleeveBadge({ sleeve }: { sleeve?: Sleeve }) {
  if (!sleeve) return <span className="text-[var(--border)]">·</span>;
  const core = sleeve === "core";
  const c = core ? "var(--green)" : "var(--accent)";
  return (
    <span className="text-xs rounded-md px-2 py-0.5 font-medium whitespace-nowrap" style={{ color: c, backgroundColor: `${c}14` }}>
      {core ? "Core" : "Satellite"}
    </span>
  );
}

function HorizonBadge({ horizon }: { horizon?: "core" | "tactical" | null }) {
  if (!horizon) return <span className="text-[var(--border)]">·</span>;
  const core = horizon === "core";
  const c = core ? "var(--green)" : "var(--accent)";
  return (
    <span className="text-xs rounded-md px-2 py-0.5 font-medium whitespace-nowrap" style={{ color: c, backgroundColor: `${c}14` }}>
      {core ? "Core" : "Tactical"}
    </span>
  );
}

const RECO_COLOR: Record<string, string> = {
  add: "var(--green)",
  hold: "var(--accent)",
  trim: "var(--accent)",
  sell: "var(--red)",
};

function RecoCell({ reco }: { reco?: Recommendation }) {
  if (!reco) return <span className="text-[var(--border)]">·</span>;
  const c = RECO_COLOR[reco.action] ?? "var(--muted)";
  return (
    <span
      className="inline-flex items-baseline gap-1.5 cursor-help"
      title={reco.rationale ?? undefined}
    >
      <span className="text-xs rounded-md px-2 py-0.5 font-semibold uppercase whitespace-nowrap" style={{ color: c, backgroundColor: `${c}1a` }}>
        {reco.action}
      </span>
      {reco.as_of && <span className="text-xs text-[var(--muted)]">{reco.as_of}</span>}
    </span>
  );
}

function RefreshButton({ onDone }: { onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const poll = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (poll.current) clearInterval(poll.current); }, []);

  const startPolling = () => {
    if (poll.current) clearInterval(poll.current);
    poll.current = setInterval(async () => {
      try {
        const r = await fetch(`${API}/api/refresh/status`);
        const j = await r.json();
        setPhase(j.steps?.phase ?? j.status);
        if (j.status === "done") {
          if (poll.current) clearInterval(poll.current);
          setBusy(false);
          setPhase(null);
          onDone();
        } else if (j.status === "error" || j.status === "idle") {
          if (poll.current) clearInterval(poll.current);
          setBusy(false);
          setPhase(null);
          if (j.status === "error") setErr(j.error ?? "Refresh failed.");
        }
      } catch {
        if (poll.current) clearInterval(poll.current);
        setBusy(false);
        setPhase(null);
        setErr("Lost contact with the backend.");
      }
    }, 2000);
  };

  const refresh = async () => {
    setErr(null);
    setBusy(true);
    setPhase("starting…");
    try {
      const r = await fetch(`${API}/api/refresh`, { method: "POST" });
      const j = await r.json();
      if (j.status === "already_running") {
        setPhase("already running…");
      }
      startPolling();
    } catch {
      setBusy(false);
      setPhase(null);
      setErr("Could not start the refresh.");
    }
  };

  return (
    <div className="flex items-center gap-2">
      {phase && <span className="text-xs text-[var(--muted)]">{phase}</span>}
      {err && <span className="text-xs text-[var(--red)]">{err}</span>}
      <button
        onClick={refresh}
        disabled={busy}
        className="rounded-lg border border-[var(--accent)]/50 text-[var(--accent)] px-3 py-1.5 text-xs font-semibold disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[var(--accent)]/10"
      >
        {busy ? "Refreshing…" : "Refresh"}
      </button>
    </div>
  );
}

function PlanSection({ plan }: { plan: Plan }) {
  const inc = plan.expected_income_egp;
  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--panel)] p-5">
      <SectionTitle title="Investment Plan" subtitle="Sleeves, sell discipline, and review cadence" />
      <div className="grid lg:grid-cols-3 gap-3 mb-5">
        {Object.entries(plan.sleeves).map(([name, s]) => (
          <div key={name} className="rounded-lg border border-[var(--border)] bg-[var(--bg)]/30 p-4">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-semibold capitalize">{name}</span>
              {s.pct_of_capital != null && (
                <span className="text-xs text-[var(--accent)]">{pct(s.pct_of_capital, 0)}</span>
              )}
            </div>
            <div className="text-xs text-[var(--muted)] mb-2">{s.horizon}</div>
            {s.symbols && s.symbols.length > 0 && (
              <div className="flex flex-wrap gap-1 mb-2">
                {s.symbols.map((sym) => (
                  <span key={sym} className="text-xs rounded px-1.5 py-0.5 bg-[var(--panel-2)]">{sym}</span>
                ))}
              </div>
            )}
            <div className="text-xs text-[var(--muted)]">{s.review ?? s.rule}</div>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        <div>
          <div className="text-xs uppercase tracking-wide text-[var(--muted)] mb-2">Sell rules</div>
          <ul className="flex flex-col gap-1.5 text-sm">
            {plan.sell_rules.map((r, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-[var(--red)]">→</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="flex flex-col gap-4">
          <div>
            <div className="text-xs uppercase tracking-wide text-[var(--muted)] mb-2">Cadence</div>
            <div className="flex flex-col gap-1.5 text-sm">
              <div><span className="text-[var(--accent)] font-medium">Monthly:</span> {plan.cadence.monthly}</div>
              <div><span className="text-[var(--accent)] font-medium">Quarterly:</span> {plan.cadence.quarterly}</div>
              {plan.cadence.note && <div className="text-xs text-[var(--muted)]">{plan.cadence.note}</div>}
            </div>
          </div>
          <div className="rounded-lg border border-[var(--border)] bg-[var(--bg)]/30 p-4">
            <div className="text-xs uppercase tracking-wide text-[var(--muted)] mb-2">Expected annual income</div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <Income label="T-bills" value={egp(inc.tbill_annual)} />
              <Income label="Dividends (net)" value={egp(inc.net_dividends_annual)} />
              <Income label="Total" value={egp(inc.total_annual)} highlight />
            </div>
            {inc.note && <p className="mt-2 text-xs text-[var(--muted)]">{inc.note}</p>}
          </div>
        </div>
      </div>
    </section>
  );
}

function Income({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div>
      <div className={`text-base font-bold tabular-nums ${highlight ? "text-[var(--accent)]" : ""}`}>{value}</div>
      <div className="text-xs text-[var(--muted)]">{label}</div>
    </div>
  );
}

function SectionTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-4">
      <h3 className="text-lg font-semibold">{title}</h3>
      {subtitle && <p className="text-xs text-[var(--muted)]">{subtitle}</p>}
    </div>
  );
}

function BucketBadge({ bucket }: { bucket: keyof typeof bucketColor }) {
  const c = bucketColor[bucket] ?? "var(--muted)";
  return (
    <span className="text-xs rounded-md px-2 py-0.5 font-medium whitespace-nowrap" style={{ color: c, backgroundColor: `${c}1a` }}>
      {bucketLabel[bucket] ?? bucket}
    </span>
  );
}

function ScoreBar({ score }: { score: number }) {
  return (
    <div className="flex items-center gap-2 justify-end">
      <div className="w-16 h-1.5 rounded-full bg-[var(--border)] overflow-hidden">
        <div className="h-full rounded-full bg-[var(--accent)]" style={{ width: `${Math.min(100, score)}%` }} />
      </div>
      <span className="w-9 text-right">{score.toFixed(0)}</span>
    </div>
  );
}

function ExposureBar({
  title,
  data,
  colorFor,
  labelFor,
}: {
  title: string;
  data: Record<string, number>;
  colorFor?: (k: string) => string;
  labelFor?: (k: string) => string;
}) {
  const palette = ["#d4af37", "#3498db", "#2ecc71", "#9b59b6", "#e67e22", "#1abc9c"];
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg)]/30 p-4">
      <div className="text-xs uppercase tracking-wide text-[var(--muted)] mb-2">{title}</div>
      <div className="flex h-3 rounded-full overflow-hidden mb-3">
        {entries.map(([k, v], i) => (
          <div key={k} style={{ width: `${v * 100}%`, backgroundColor: colorFor ? colorFor(k) : palette[i % palette.length] }} />
        ))}
      </div>
      <div className="flex flex-col gap-1 text-xs">
        {entries.map(([k, v], i) => (
          <div key={k} className="flex items-center justify-between">
            <span className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: colorFor ? colorFor(k) : palette[i % palette.length] }} />
              {labelFor ? labelFor(k) : k}
            </span>
            <span className="tabular-nums text-[var(--muted)]">{pct(v)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
