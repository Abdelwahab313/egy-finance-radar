"use client";

import { useEffect, useRef, useState } from "react";
import { Snapshot, Recommendation } from "@/lib/types";
import { compactEgp } from "@/lib/format";

import SiteHeader from "@/components/SiteHeader";
import HeroBand from "@/components/HeroBand";
import SceneCard from "@/components/SceneCard";
import AccountSummary from "@/components/AccountSummary";
import AllocationDonut from "@/components/AllocationDonut";
import ContributionBars from "@/components/ContributionBars";
import PositionsLedger from "@/components/PositionsLedger";
import InvestmentPlan from "@/components/InvestmentPlan";

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

  const freshnessText = snap
    ? `prices ${snap.price_data_ok_count ?? snap.live_data_ok_count}/${snap.universe_size} · β via ${
        snap.index_source === "CASE30" ? "EGX30" : "proxy"
      } · ${snap.source}`
    : "connecting…";

  const refreshSlot = <RefreshButton onDone={() => { load(); loadRecos(); }} />;

  if (error)
    return (
      <>
        <SiteHeader freshnessText={freshnessText} activeTab="dashboard" refreshSlot={refreshSlot} />
        <div className="wrap">
          <div className="statebox err" style={{ marginTop: 40 }}>{error}</div>
        </div>
      </>
    );

  if (!snap)
    return (
      <>
        <SiteHeader freshnessText={freshnessText} activeTab="dashboard" refreshSlot={refreshSlot} />
        <div className="wrap">
          <div className="statebox" style={{ marginTop: 40 }}>Loading EGX snapshot…</div>
        </div>
      </>
    );

  const pf = snap.portfolio;
  const holdings = snap.holdings ?? null;
  const modelEquity = pf.invested_value + pf.entry_costs_total;
  const sectorExposure = pf.sector_group_exposure ?? pf.sector_exposure;

  const equity = holdings?.market_value_total ?? modelEquity;
  const costBasis = holdings?.cost_basis_total ?? 0;

  return (
    <>
      <SiteHeader freshnessText={freshnessText} activeTab="dashboard" refreshSlot={refreshSlot} />

      <div className="wrap">
        <HeroBand
          equity={equity}
          pnl={holdings?.unrealized_pnl_total ?? 0}
          pnlPct={holdings?.unrealized_pct_total ?? null}
          deployedPct={holdings?.deployed_pct_of_capital ?? 0}
          costBasis={costBasis}
          overUnder={pf.starting_capital - costBasis}
          cash={pf.cash_remaining}
          tbillAmount={pf.tbill_sleeve?.amount_egp ?? null}
          tbillYield={pf.tbill_sleeve?.annual_yield ?? null}
        />

        <SceneCard scene={snap.scene} />

        <div className="bento">
          <AccountSummary
            startingCapital={pf.starting_capital}
            equity={modelEquity}
            equityPct={pf.equity_pct ?? null}
            tbillAmount={pf.tbill_sleeve?.amount_egp ?? null}
            tbillYield={pf.tbill_sleeve?.annual_yield ?? null}
            tbillIncome={pf.tbill_sleeve?.expected_annual_income_egp ?? null}
            cash={pf.cash_remaining}
            broker={pf.broker}
          />
          <AllocationDonut
            bucket={pf.bucket_exposure}
            sector={sectorExposure}
            centerValue={compactEgp(modelEquity)}
          />
          <ContributionBars
            items={(holdings?.lots ?? []).map((l) => ({ symbol: l.symbol, pnl: l.unrealized_pnl }))}
            net={holdings?.unrealized_pnl_total ?? 0}
          />
        </div>

        <p className="eyebrow" style={{ marginTop: 34 }}>Positions Ledger</p>
        <PositionsLedger
          holdings={holdings}
          positions={pf.positions}
          bucketExposure={pf.bucket_exposure}
          sectorExposure={sectorExposure}
          stocks={snap.stocks}
          shortlist={snap.shortlist}
          excludedBySignal={pf.excluded_by_signal}
          modelNotes={pf.notes}
          source={snap.source}
          recosBySym={recosBySym}
          holdingsNote={holdings?.note ?? null}
          addOrderSlot={<AddOrderForm onAdded={load} />}
        />

        {pf.plan && <InvestmentPlan plan={pf.plan} />}

        <footer className="site-footer">
          <span className="disc">Research / education only — not investment advice.</span>
          <span className="sig2">EGY-FINANCE-RADAR · EGX TERMINAL</span>
        </footer>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Stateful controls — logic preserved from the original dashboard,   */
/* restyled into the terminal grammar (.refresh / .addform).          */
/* ------------------------------------------------------------------ */

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
      if (j.status === "already_running") setPhase("already running…");
      startPolling();
    } catch {
      setBusy(false);
      setPhase(null);
      setErr("Could not start the refresh.");
    }
  };

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, justifyContent: "flex-end" }}>
      {phase && <span style={{ fontSize: 10.5, color: "var(--muted)" }}>{phase}</span>}
      {err && <span style={{ fontSize: 10.5, color: "var(--red)" }}>{err}</span>}
      <button className="refresh" onClick={refresh} disabled={busy}>
        <svg viewBox="0 0 24 24" fill="none">
          <path
            d="M3 12a9 9 0 0 1 15-6.7L21 8M21 3v5h-5M21 12a9 9 0 0 1-15 6.7L3 16M3 21v-5h5"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        {busy ? "Refreshing…" : "Refresh"}
      </button>
    </div>
  );
}

const TODAY = () => new Date().toISOString().slice(0, 10);

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

  const valid = symbol.trim() && Number(shares) > 0 && Number(entry) > 0 && tradedAt;

  return (
    <form onSubmit={submit} className="addform">
      <div className="addfield">
        <label>Symbol</label>
        <input
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          placeholder="COMI"
          style={{ width: 96, textTransform: "uppercase" }}
        />
      </div>
      <div className="addfield">
        <label>Side</label>
        <select value={side} onChange={(e) => setSide(e.target.value as "buy" | "sell")}>
          <option value="buy">Buy</option>
          <option value="sell">Sell</option>
        </select>
      </div>
      <div className="addfield">
        <label>Shares</label>
        <input
          value={shares}
          onChange={(e) => setShares(e.target.value)}
          inputMode="decimal"
          placeholder="27"
          style={{ width: 88 }}
        />
      </div>
      <div className="addfield">
        <label>Entry (EGP)</label>
        <input
          value={entry}
          onChange={(e) => setEntry(e.target.value)}
          inputMode="decimal"
          placeholder="130.10"
          style={{ width: 110 }}
        />
      </div>
      <div className="addfield">
        <label>Traded at</label>
        <input type="date" value={tradedAt} onChange={(e) => setTradedAt(e.target.value)} />
      </div>
      <div className="addfield">
        <label>Horizon</label>
        <select value={horizon} onChange={(e) => setHorizon(e.target.value as "core" | "tactical")}>
          <option value="core">Core</option>
          <option value="tactical">Tactical</option>
        </select>
      </div>
      <button type="submit" className="addbtn" disabled={!valid || busy}>
        {busy ? "Adding…" : "Add order"}
      </button>
      {err && <span className="adderr">{err}</span>}
    </form>
  );
}
