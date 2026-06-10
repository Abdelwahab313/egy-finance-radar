# EGY Finance — EGX Stock Intelligence Agent

A data-collection agent + classifier + technical signal engine + paper-trading portfolio
for **Egyptian Exchange (EGX)** listed stocks, with a Next.js dashboard.

> Built as a full vertical slice: real data pipeline → stock classification → curated
> shortlist → a balanced value+growth paper portfolio → entry/exit signals → a basic UI.
> Polished UI design is a later round.

## The two-layer model

The system deliberately separates **what to own** from **when to act**:

1. **Classification layer** (fundamentals + risk) → buckets, scores, shortlist, and the
   balanced portfolio. Answers *what to own*.
2. **Signal layer** (technical/momentum) → BUY / HOLD / TRIM / EXIT per stock with
   concrete stop-loss and take-profit levels. Answers *when to act*.

These two can — and do — disagree (e.g. a fundamentally cheap name whose price has
broken below its 200-day MA). That disagreement is a feature, not a bug.

## Architecture

```
egy_finance/
├── backend/                 # Python: data agent, classifier, signals, portfolio, FastAPI
│   ├── app/
│   │   ├── config.py        # ALL tunable constants (capital, gates, thresholds, signal params)
│   │   ├── data/
│   │   │   ├── universe.py   # curated EGX names + static fallback fundamentals
│   │   │   └── sources.py    # DataSource abstraction (YFinanceSource now, EODHD-ready)
│   │   ├── analysis/
│   │   │   ├── metrics.py    # price-derived metrics + proxy-market beta + live-value validation
│   │   │   ├── classifier.py # eligibility gates → buckets → composite score
│   │   │   └── signals.py    # technical/momentum entry & exit engine
│   │   ├── portfolio/
│   │   │   └── account.py    # slot allocation, cap-and-redistribute, cost model
│   │   ├── agent/
│   │   │   └── collector.py  # orchestrates everything → writes data/snapshot.json
│   │   └── main.py           # FastAPI serving the snapshot
│   ├── tests/                # pytest invariants (portfolio caps, balance, signals, validation)
│   ├── pytest.ini
│   └── requirements.txt
└── frontend/                # Next.js 15 + Tailwind v4 dashboard (dark theme)

.claude/commands/egx-refresh-review.md   # /egx-refresh-review slash command
```

## Why this design

EGX has **no clean free API**. yfinance (`.CA` suffix, e.g. `COMI.CA`) gives reliable *prices*
for the ~30 liquid index names and is free, so it's the default source — behind a `DataSource`
interface so **EODHD** (`.EGX`, paid, full coverage + fundamentals) can drop in later. We work
from a **curated universe** of liquid blue-chips to sidestep yfinance's flakiness on thin tickers,
and ship **static fallback fundamentals** so the pipeline always produces a result.

### Data honesty (important)

`yfinance` is reliable for **prices** but **not for EGX fundamentals**. The pipeline reflects this:

- **Live / computed:** prices, volatility, returns, liquidity, **beta** (vs a live equal-weight
  proxy — Yahoo's `^CASE30` index returns ~1 row and is unusable), and **validated** P/E & P/B
  (Yahoo's bogus values like a P/E of 0.12 are rejected via plausibility bands → static fallback).
- **Static fallback (curated, ~June 2026):** dividend yield, payout ratio, ROE, 3y EPS growth.

Every snapshot includes a `data_quality` block listing exactly which fields are live vs static.
Wiring **EODHD** is the single highest-value upgrade — it makes the static fields live.

## Run it

### Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m app.agent.collector          # fetch EGX data → classify → signals → portfolio → snapshot.json
uvicorn app.main:app --reload --port 8000
pytest -q                               # run the invariant tests
```

> **yfinance gotcha:** versions < 1.4 are broken against Yahoo's current backend (silent empty
> fetches, "possibly delisted"). requirements.txt pins `yfinance>=1.4.1` + `curl_cffi`.

### Frontend
```bash
cd frontend
npm install
npm run dev        # http://localhost:3000  (expects backend on :8000)
```

### Docker (single port: 5040)
```bash
docker compose up --build       # -> http://localhost:5040
```
The **frontend is the only externally-published service** (host port `5040`). The
backend runs internal-only on the compose network; the frontend proxies `/api/*`
to it (Next.js rewrite → `http://backend:8000`), so there's no second host port to
collide with anything else.

- `backend/data/` is bind-mounted, so the snapshot and your `orders.json` (placed
  orders / live P&L) persist across rebuilds and restarts. The image ships the
  current `snapshot.json` as a seed; `POST /api/refresh` regenerates it live.
- **Deploy target / different port:** change the left side of `"5040:5040"` in
  `docker-compose.yml` for the host port. The proxy target is baked at build time
  (Next serializes `rewrites()` into the build), so to point at a different backend
  host, set the `BACKEND_ORIGIN` **build arg** (already wired in compose).
- The **Investigate** feature shells out to the `claude` CLI, which isn't in the
  container — that endpoint won't work in Docker. The dashboard, classification,
  signals, portfolio, and order-logging all do.

## API endpoints

| Method | Path | Returns |
|---|---|---|
| GET  | `/api/health`    | liveness + whether a snapshot exists |
| GET  | `/api/snapshot`  | full snapshot (scene, data_quality, stocks, shortlist, portfolio) |
| GET  | `/api/stocks`    | classified stocks only |
| GET  | `/api/portfolio` | the portfolio (positions, exposures, **actions** with stop/target) |
| GET  | `/api/signals`   | per-stock signals + portfolio entry/exit actions |
| POST | `/api/refresh`   | re-run the collection agent (slow; hits the network) |

## The signal engine (technical / momentum, long-only)

Per stock, from daily OHLCV (see `analysis/signals.py`):

- **EXIT** — death cross (50-MA below 200-MA), price below the 200-MA, or stop hit.
- **TRIM** — RSI(14) ≥ 70, or price > 20% above the 50-MA (overbought / extended → take profit).
- **BUY** — confirmed uptrend (price > 200-MA and 50-MA > 200-MA) **and** a trigger: golden
  cross, pullback to the 50-MA, 52-week breakout, or an oversold bounce — and not overbought.
- **HOLD** — uptrend, no fresh trigger. **AVOID** — no confirmed uptrend.
- **Levels:** stop = price − 2.5×ATR(14); take-profit = 2× the stop distance; entry zone =
  50-MA up to current price (scale in within).

## Slash command

`/egx-refresh-review [capital_egp]` — refreshes the snapshot with live data and re-runs the
adversarial critique of the output and code (data quality, portfolio invariants, signal sanity).
Optionally pass a capital amount to re-seed the account (e.g. `/egx-refresh-review 20000`).

## Key constants (configurable)

All in `backend/app/config.py`:
- `STARTING_CAPITAL_EGP = 20_000` · `CASH_BUFFER_PCT = 0.10`
- Eligibility gates (min market cap, min avg daily traded value)
- Bucket thresholds (beta, **volatility**, P/E, P/B, dividend yield, ROE, growth)
- Portfolio targets (bucket weights 40/35/25, max position 25%, max sector 40%, target holdings)
- Trading-cost model (stamp duty + EGX/MCDR fees + digital vs traditional brokerage)
- Signal params (SMA 50/200, RSI 14, ATR 14 ×2.5 stop, breakout/pullback/extended bands)

## Caveats

- `data_quality.mostly_static_fields` lists fundamentals that are curated (June 2026), **not** a
  live feed — verify against a broker before any real trade.
- Prices are nominal **EGP** (not FX-adjusted). EGP devaluation distorts long-horizon USD views.
- Beta is computed against an **equal-weight proxy** (the universe itself), not the real EGX30 —
  it includes a small self-weight bias and is directional.
- This is research/education tooling, **not investment advice**.
```
