"""Migrate and seed the sample book into a real Postgres, then check the seed
is idempotent. Skips without ``TEST_DATABASE_URL`` (see conftest.py)."""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd

from app.analysis import scorecard
from app.data.sources import FetchResult, IndexHistory, PriceHistory
from app.data.universe import EGX_UNIVERSE
from app.db import migrate, seed
from app.db.models import (
    Instrument, Orders, PortfolioSnapshot, Position, Recommendation, RecommendationOutcome,
)


def _reset_schema(db):
    db.execute_sql("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")


def test_migrate_then_seed_is_idempotent(db):
    _reset_schema(db)

    applied = migrate.run()
    assert applied == 3
    assert migrate.run() == 0

    seed.seed()
    lots = json.loads(seed.ORDERS_FILE.read_text())["lots"]
    frames = json.loads(seed.HISTORY_FILE.read_text())["rows"]

    assert Instrument.select().count() == len(EGX_UNIVERSE)
    assert Orders.select().count() == len(lots)
    assert Position.select().count() == len({lot["symbol"] for lot in lots})
    assert PortfolioSnapshot.select().count() == len(frames)

    seed.seed()
    assert Orders.select().count() == len(lots), "seed_orders must be seed-once"
    assert Position.select().count() == len({lot["symbol"] for lot in lots})
    assert PortfolioSnapshot.select().count() == len(frames)

    horizons = {p.symbol_id: p.horizon for p in Position.select()}
    assert set(horizons.values()) <= {"core", "tactical"}
    assert horizons == {s: seed.SEED_HORIZONS[s] for s in horizons}

    verdicts = json.loads(seed.RECOMMENDATIONS_FILE.read_text())["rows"]
    assert Recommendation.select().count() == len(verdicts)


class _RisingSource:
    """Every symbol climbs 1% a session from 2026-06-01: targets get hit, stops never."""

    def fetch(self, syms):
        idx = pd.bdate_range("2026-06-01", periods=120)
        prices = {}
        for s in syms:
            close = pd.Series(100.0 * (1.01 ** np.arange(len(idx))), index=idx)
            prices[s] = PriceHistory(s, pd.DataFrame({"Close": close}))
        return FetchResult(prices=prices, index=IndexHistory(pd.DataFrame()), live_info={})


def test_scorecard_upsert_is_idempotent(db):
    n = Recommendation.select().count()
    assert n > 0, "run after the seed test"
    today = date(2026, 9, 27)

    first = scorecard.score_all(source=_RisingSource(), today=today)
    assert first["scored"] == n
    assert RecommendationOutcome.select().count() == n

    second = scorecard.score_all(source=_RisingSource(), today=today)
    assert second == first
    assert RecommendationOutcome.select().count() == n

    rep = scorecard.report()
    assert len(rep["rows"]) == n
    assert set(rep["summary"]) == {"overall", "by_horizon", "by_action", "unscored"}
    assert rep["summary"]["overall"]["scored"] + rep["summary"]["unscored"] == n
    statuses = {r["status"] for r in rep["rows"]}
    assert statuses <= {"target_hit", "stop_hit", "expired", "open", "no_data"}
    assert scorecard.report("COMI")["rows"][0]["symbol"] == "COMI"
