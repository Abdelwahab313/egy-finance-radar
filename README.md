# egy-finance-radar

Research tooling for the Egyptian Exchange (EGX). It keeps a small book of
positions in Postgres, pulls prices, classifies each name on fundamentals, runs
a mechanical technical signal over it, and stores a dated recommendation per
position so past verdicts can be checked later. A Next.js dashboard reads the
result.

I built it for one retail account. The tracked data files are a fictional
sample book on real tickers. Nothing here is investment advice.

![Dashboard](docs/dashboard.png)

## Why

EGX has no clean free API. yfinance gives usable prices for the liquid names
and little else, and its fundamentals for EGX are often wrong. The problem I
wanted to solve is not fetching data. It is knowing, for every number on the
screen, whether it is live, a curated fallback, or a price I read off a broker
screen and wrote down with a date. The pipeline carries that provenance
through to the API.

## The two-layer model

The system separates what to own from when to act.

1. **Classification layer**. Hard eligibility gates (market cap, average traded
   value), then a style bucket (`stable_bluechip`, `value`, `growth`,
   `speculative`), then a 0 to 100 quality score, a shortlist, and a balanced
   paper portfolio with per-name and per-sector caps.
2. **Signal layer**. 50 and 200-day structure, RSI(14), 52-week breakout or
   pullback, ATR(14) stop. One action per stock: BUY, HOLD, TRIM, EXIT, AVOID,
   with concrete stop and target levels.

The two layers can disagree, and the dashboard shows the disagreement rather
than resolving it.

A third piece, the **Investigator**, precomputes a deterministic context for one
ticker and then drives a headless LLM agent to research it and write a report.
The structured verdict (action, target, stop, news) is stored as a
**Recommendation** next to the prose. This part needs the `claude` CLI on the
host and does not run inside the container.

## Run it

```bash
docker compose up --build -d
curl -X POST http://localhost:5040/api/refresh
```

Then open http://localhost:5040.

The first command starts Postgres, applies the migrations, seeds the sample
book from `backend/data/`, and serves the dashboard on the one published port.
The second fetches live prices from yfinance and writes the snapshot cache. It
runs in the background; poll `GET /api/refresh/status`. Inside the container the
LLM pass is skipped because the CLI is not there.

Local development without Docker:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest -q                                   # offline unit tests
docker compose up -d db                     # Postgres on localhost:5433
python -m app.db.migrate && python -m app.db.seed
python -m app.agent.collector               # writes data/snapshot.json
uvicorn app.main:app --reload --port 8000

cd ../frontend && npm ci && npm run dev     # http://localhost:3000
```

The database test runs only when `TEST_DATABASE_URL` is set. Locally that is
`postgresql://egx:egx@localhost:5433/egx` with the compose `db` service up. CI
provides a service container.

## Architecture

```
egy-finance-radar/
├── CONTEXT.md                  # domain vocabulary: Position, Order, Horizon, Recommendation...
├── docs/adr/                   # one file per decision, see the index below
├── docker-compose.yml          # db + backend (internal) + frontend (port 5040)
├── backend/
│   ├── app/
│   │   ├── config.py           # every tunable constant: capital, gates, thresholds, signal params
│   │   ├── data/
│   │   │   ├── universe.py     # curated EGX names with dated static fundamentals
│   │   │   ├── sources.py      # DataSource interface; YFinanceSource; MarksOverlaySource
│   │   │   └── marks.py        # dated broker marks that override vendor bars (ADR-0006)
│   │   ├── analysis/
│   │   │   ├── metrics.py      # returns, volatility, liquidity, beta vs an equal-weight proxy
│   │   │   ├── classifier.py   # gates -> bucket -> quality score
│   │   │   └── signals.py      # technical entry and exit engine
│   │   ├── portfolio/account.py# slot allocation, caps, cost model
│   │   ├── agent/
│   │   │   ├── collector.py    # fetch -> metrics -> classify -> signals -> snapshot.json
│   │   │   ├── refresh.py      # background Refresh job: collect, append history, recommend
│   │   │   └── investigator.py # one-ticker deterministic context + headless LLM report
│   │   ├── db/                 # peewee models, migration runner, idempotent seed
│   │   └── main.py             # FastAPI
│   ├── migrations/             # plain SQL, applied in order, recorded in schema_migrations
│   ├── data/                   # orders.json, marks.json, portfolio_history.json (sample book)
│   └── tests/
└── frontend/                   # Next.js 15 dashboard; proxies /api/* to the backend
```

**Store.** Postgres is the system of record (ADR-0001). Tables: `instrument`,
`position`, `orders`, `price_history`, `metric_snapshot`, `news`,
`recommendation`, `recommendation_outcome`, `portfolio_snapshot`. `backend/data/snapshot.json` is a cache
the API serves; a Refresh rebuilds it. The three JSON files under
`backend/data/` seed the database and are safe to edit by hand.
`recommendations.json` holds five sample verdicts so the scorecard has rows.

## API

All routes are served by `backend/app/main.py`.

| Method | Path | What it does |
|---|---|---|
| GET | `/api/health` | Liveness and whether a snapshot exists |
| GET | `/api/snapshot` | Full snapshot: scene, data_quality, stocks, shortlist, portfolio |
| GET | `/api/stocks` | Classified stocks only |
| GET | `/api/portfolio` | Paper portfolio and starting capital |
| GET | `/api/signals` | Per-stock signal plus portfolio actions |
| POST | `/api/refresh` | Start a background Refresh; second call returns `already_running` |
| GET | `/api/refresh/status` | Phase and counts of the current or last Refresh |
| POST | `/api/orders` | Record a placed lot (symbol, shares, price, side, horizon) and re-mark holdings |
| POST | `/api/investigate` | Start a one-ticker investigation in the background |
| GET | `/api/investigate/status?filename=` | Poll an investigation |
| GET | `/api/recommendations?symbol=` | Stored verdicts, newest first, optionally per symbol |
| GET | `/api/scorecard?symbol=` | Realised outcome of every verdict and hit rates by horizon and action |
| GET | `/api/reports` | List investigation reports |
| GET | `/api/reports/{filename}` | One report's markdown; filename is regex-guarded |

## Decisions

One line each; the files carry the options considered.

- [0001](docs/adr/0001-postgres-as-store.md) Postgres as the store, chosen for where the project is going rather than today's data size.
- [0002](docs/adr/0002-always-rerun-refresh.md) Refresh always re-runs the full recommendation pass; freshness over token cost, run as a background job.
- [0003](docs/adr/0003-horizon-per-position.md) Horizon is a per-Position tag set by the owner; one Position per ticker.
- [0004](docs/adr/0004-opportunity-seam-stays-manual.md) Refresh investigates holdings only; researching a new name is a manual act.
- [0005](docs/adr/0005-portfolio-snapshot-history.md) Portfolio-level history is its own dated table, backfilled best-effort.
- [0006](docs/adr/0006-owner-marks-override-vendor-prices.md) A dated price read off the broker outranks every vendor; same-date disagreement above 10% blocks the name.
- [0007](docs/adr/0007-recommendation-scorecard.md) Every stored verdict is scored against the closes that followed it, in its own table, on every Refresh.

## Data honesty

Every snapshot carries a `data_quality` block naming which fields are which.

- **Live.** Prices, returns, volatility, average traded value, beta. Beta is
  against an equal-weight proxy of the universe because Yahoo's `^CASE30`
  returns a single row.
- **Validated live.** P/E and P/B from yfinance pass plausibility bands or fall
  back to static.
- **Static.** Dividend yield, payout, ROE, EPS growth: curated by hand in
  `universe.py`. An absent key means not found. It is never zero and never an
  estimate.
- **Marks.** A dated broker price overrides the vendor's last bar. A same-date
  disagreement above 10% is reported as a conflict and blocks the name.

## Limits

- One price vendor. EODHD sits behind the `DataSource` interface but is not wired.
- Open-ended funds have no price series; they are marked by hand through
  `MANUAL_NAV`.
- The beta proxy includes the stock itself, so it carries a small self-weight bias.
- Refresh status is in-process memory. A restart forgets a running job.
- The Investigator shells out to a CLI on the host. In the container it is skipped.
- Prices are nominal EGP, not FX-adjusted.
- The Market Scene (index level, EGP, inflation, policy rate) is a hand-written
  brief in `collector.py` with its own as-of date. It is not fetched.
- Single user. No auth on the API; do not expose port 5040 beyond localhost.

## Not investment advice

Research tooling for one account whose owner makes their own decisions. The
sample book is fictional. Verify any number here against your broker and the
exchange before acting on it.
