"""Idempotent seeder — ``python -m app.db.seed``.

Seeds three tables, in FK-safe order:

1. ``instrument`` — one row per ``EGX_UNIVERSE`` entry (upsert; re-running
   updates name/sector/fundamentals, never duplicates).
2. ``orders`` — the seed lots from ``backend/data/orders.json`` as ``buy`` rows.
   Orders have no natural key, so this is **seed-once**: lots are inserted only
   when the ``orders`` table is empty. Re-runs are skipped (logged).
3. ``position`` — one Position per held ticker, with the owner-confirmed Horizon
   (COMI/MFPC/ADIB = core, EMFD = tactical). ``opened_at`` = earliest order
   ``traded_at`` for the symbol. Upsert on the ``symbol`` PK (idempotent).

``seed()`` is safe to import and call from other modules. The whole pass runs
inside a single transaction.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from peewee import SQL

from app.data.universe import EGX_UNIVERSE
from app.db import connect, db
from app.db.models import Instrument, Orders, Position

# backend/app/db/seed.py -> backend/data/orders.json
ORDERS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "orders.json"

# `now()` SQL literal, reused in upsert `update` clauses to bump updated_at.
SQL_NOW = SQL("now()")

# Owner-confirmed Horizons (IMPLEMENTATION_PLAN.md "Seed horizons").
SEED_HORIZONS: dict[str, str] = {
    "COMI": "core",
    "MFPC": "core",
    "ADIB": "core",
    "EMFD": "tactical",
}


def seed_instruments() -> int:
    """Upsert one ``instrument`` row per universe entry. Returns row count."""
    for symbol, profile in EGX_UNIVERSE.items():
        Instrument.insert(
            symbol=symbol,
            name=profile["name"],
            sector=profile["sector"],
            fundamentals=profile.get("fundamentals", {}),
            in_universe=True,
        ).on_conflict(
            conflict_target=[Instrument.symbol],
            update={
                Instrument.name: profile["name"],
                Instrument.sector: profile["sector"],
                Instrument.fundamentals: profile.get("fundamentals", {}),
                Instrument.in_universe: True,
                Instrument.updated_at: SQL_NOW,
            },
        ).execute()
    n = len(EGX_UNIVERSE)
    print(f"instruments: {n} upserted")
    return n


def _load_lots() -> tuple[list[dict], date]:
    data = json.loads(ORDERS_FILE.read_text())
    as_of = date.fromisoformat(data["as_of"])
    return data.get("lots", []), as_of


def seed_orders() -> int:
    """Seed-once insert of orders.json lots. Skips if orders already exist.

    Returns the number of rows inserted (0 when skipped).
    """
    existing = Orders.select().count()
    if existing:
        print(f"orders: skip (table not empty — {existing} row(s) already present)")
        return 0

    lots, as_of = _load_lots()
    for lot in lots:
        # No per-lot date in orders.json -> fall back to the file's as_of.
        traded_at = date.fromisoformat(lot["date"]) if lot.get("date") else as_of
        Orders.insert(
            symbol=lot["symbol"],
            side="buy",
            shares=lot["shares"],
            price=lot["entry_price"],
            traded_at=traded_at,
        ).execute()
    print(f"orders: {len(lots)} seed lot(s) inserted")
    return len(lots)


def seed_positions() -> int:
    """Upsert one Position per ticker that has at least one order.

    Horizon from ``SEED_HORIZONS`` (default 'core' with a warning if missing).
    ``opened_at`` = earliest order ``traded_at`` for that symbol.
    """
    held = (
        Orders.select(Orders.symbol)
        .distinct()
        .tuples()
    )
    symbols = [row[0] for row in held]

    count = 0
    for symbol in symbols:
        horizon = SEED_HORIZONS.get(symbol)
        if horizon is None:
            horizon = "core"
            print(f"  WARNING: {symbol} held but not in horizon map; defaulting to 'core'")

        opened_at = (
            Orders.select(Orders.traded_at)
            .where(Orders.symbol == symbol)
            .order_by(Orders.traded_at.asc())
            .scalar()
        )

        Position.insert(
            symbol=symbol,
            horizon=horizon,
            opened_at=opened_at,
        ).on_conflict(
            conflict_target=[Position.symbol],
            update={
                Position.horizon: horizon,
                Position.opened_at: opened_at,
                Position.updated_at: SQL_NOW,
            },
        ).execute()
        count += 1

    print(f"positions: {count} upserted")
    return count


def seed() -> None:
    """Run the full idempotent seed inside one transaction. Safe to re-call."""
    connect()
    with db.atomic():
        seed_instruments()
        seed_orders()
        seed_positions()
    print("seed: done")


if __name__ == "__main__":
    seed()
