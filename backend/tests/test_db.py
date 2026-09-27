"""Migrate and seed the sample book into a real Postgres, then check the seed
is idempotent. Skips without ``TEST_DATABASE_URL`` (see conftest.py)."""

from __future__ import annotations

import json

from app.data.universe import EGX_UNIVERSE
from app.db import migrate, seed
from app.db.models import Instrument, Orders, PortfolioSnapshot, Position


def _reset_schema(db):
    db.execute_sql("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")


def test_migrate_then_seed_is_idempotent(db):
    _reset_schema(db)

    applied = migrate.run()
    assert applied == 2
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
