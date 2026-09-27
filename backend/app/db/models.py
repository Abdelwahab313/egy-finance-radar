"""peewee models mapping the canonical schema (IMPLEMENTATION_PLAN.md DDL).

Models are for queries; ``backend/migrations/0001_init.sql`` is the authoritative
DDL — keep these in sync with it. JSONB columns use ``BinaryJSONField``.
"""

from __future__ import annotations

from peewee import (
    BigAutoField,
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    DecimalField,
    ForeignKeyField,
    IntegerField,
    Model,
    SQL,
    TextField,
)
from playhouse.postgres_ext import BinaryJSONField

from app.db import db


class BaseModel(Model):
    class Meta:
        database = db


class SchemaMigrations(BaseModel):
    version = CharField(primary_key=True)
    applied_at = DateTimeField(constraints=[SQL("DEFAULT now()")])

    class Meta:
        table_name = "schema_migrations"


class Instrument(BaseModel):
    symbol = CharField(primary_key=True)
    name = TextField()
    sector = TextField()
    fundamentals = BinaryJSONField(constraints=[SQL("DEFAULT '{}'::jsonb")])
    in_universe = BooleanField(constraints=[SQL("DEFAULT TRUE")])
    created_at = DateTimeField(constraints=[SQL("DEFAULT now()")])
    updated_at = DateTimeField(constraints=[SQL("DEFAULT now()")])

    class Meta:
        table_name = "instrument"


class Position(BaseModel):
    # One Position per ticker (ADR-0003); symbol IS the PK.
    symbol = ForeignKeyField(
        Instrument, field="symbol", primary_key=True, column_name="symbol",
        backref="position",
    )
    horizon = TextField(constraints=[SQL("CHECK (horizon IN ('core','tactical'))")])
    opened_at = DateField(null=True)
    created_at = DateTimeField(constraints=[SQL("DEFAULT now()")])
    updated_at = DateTimeField(constraints=[SQL("DEFAULT now()")])

    class Meta:
        table_name = "position"


class Orders(BaseModel):
    id = BigAutoField()
    symbol = ForeignKeyField(Instrument, field="symbol", column_name="symbol", backref="orders")
    side = TextField(constraints=[SQL("DEFAULT 'buy'"), SQL("CHECK (side IN ('buy','sell'))")])
    shares = DecimalField(max_digits=18, decimal_places=4, constraints=[SQL("CHECK (shares > 0)")])
    price = DecimalField(max_digits=18, decimal_places=4, constraints=[SQL("CHECK (price > 0)")])
    traded_at = DateField()
    created_at = DateTimeField(constraints=[SQL("DEFAULT now()")])

    class Meta:
        table_name = "orders"


class PriceHistory(BaseModel):
    id = BigAutoField()
    symbol = ForeignKeyField(Instrument, field="symbol", column_name="symbol", backref="price_history")
    as_of = DateField()
    close = DecimalField(max_digits=18, decimal_places=4, null=True)
    created_at = DateTimeField(constraints=[SQL("DEFAULT now()")])

    class Meta:
        table_name = "price_history"
        indexes = ((("symbol", "as_of"), True),)


class MetricSnapshot(BaseModel):
    id = BigAutoField()
    symbol = ForeignKeyField(Instrument, field="symbol", column_name="symbol", backref="metric_snapshots")
    as_of = DateField()
    bucket = TextField(null=True)
    score = DecimalField(max_digits=8, decimal_places=2, null=True)
    metrics = BinaryJSONField(constraints=[SQL("DEFAULT '{}'::jsonb")])
    signal = BinaryJSONField(constraints=[SQL("DEFAULT '{}'::jsonb")])
    created_at = DateTimeField(constraints=[SQL("DEFAULT now()")])

    class Meta:
        table_name = "metric_snapshot"
        indexes = ((("symbol", "as_of"), True),)


class News(BaseModel):
    id = BigAutoField()
    symbol = ForeignKeyField(Instrument, field="symbol", column_name="symbol", backref="news")
    headline = TextField()
    url = TextField(null=True)
    source = TextField(null=True)
    published_at = DateField(null=True)
    summary = TextField(null=True)
    created_at = DateTimeField(constraints=[SQL("DEFAULT now()")])

    class Meta:
        table_name = "news"


class PortfolioSnapshot(BaseModel):
    # One dated frame of the whole book (ADR-0005). Aggregates are nullable so
    # backfilled rows can carry an exact cost_basis without faking a market mark.
    id = BigAutoField()
    as_of = DateField(unique=True)
    reconstructed = BooleanField(constraints=[SQL("DEFAULT FALSE")])
    source = TextField(null=True)
    nav_total = DecimalField(max_digits=18, decimal_places=2, null=True)
    cost_basis = DecimalField(max_digits=18, decimal_places=2, null=True)
    market_value = DecimalField(max_digits=18, decimal_places=2, null=True)
    invested = DecimalField(max_digits=18, decimal_places=2, null=True)
    cash = DecimalField(max_digits=18, decimal_places=2, null=True)
    unrealized_pnl = DecimalField(max_digits=18, decimal_places=2, null=True)
    unrealized_pct = DecimalField(max_digits=10, decimal_places=6, null=True)
    deployed_pct = DecimalField(max_digits=10, decimal_places=6, null=True)
    holdings = BinaryJSONField(constraints=[SQL("DEFAULT '[]'::jsonb")])
    bucket_weights = BinaryJSONField(null=True)
    sector_weights = BinaryJSONField(null=True)
    events = BinaryJSONField(constraints=[SQL("DEFAULT '[]'::jsonb")])
    created_at = DateTimeField(constraints=[SQL("DEFAULT now()")])
    updated_at = DateTimeField(constraints=[SQL("DEFAULT now()")])

    class Meta:
        table_name = "portfolio_snapshot"


class Recommendation(BaseModel):
    id = BigAutoField()
    symbol = ForeignKeyField(Instrument, field="symbol", column_name="symbol", backref="recommendations")
    as_of = DateField()
    horizon = TextField(constraints=[SQL("CHECK (horizon IN ('core','tactical'))")])
    action = TextField(constraints=[SQL("CHECK (action IN ('hold','add','trim','sell'))")])
    rationale = TextField(null=True)
    price_target = DecimalField(max_digits=18, decimal_places=4, null=True)
    stop_loss = DecimalField(max_digits=18, decimal_places=4, null=True)
    news_ids = BinaryJSONField(null=True)
    report_file = TextField(null=True)
    created_at = DateTimeField(constraints=[SQL("DEFAULT now()")])

    class Meta:
        table_name = "recommendation"


class RecommendationOutcome(BaseModel):
    recommendation = ForeignKeyField(Recommendation, field="id", column_name="recommendation_id",
                                     primary_key=True, backref="outcome", on_delete="CASCADE")
    symbol = ForeignKeyField(Instrument, field="symbol", column_name="symbol", backref="outcomes")
    evaluated_at = DateTimeField(constraints=[SQL("DEFAULT now()")])
    window_days = IntegerField()
    window_end = DateField()
    entry_date = DateField(null=True)
    entry_price = DecimalField(max_digits=18, decimal_places=4, null=True)
    last_date = DateField(null=True)
    last_price = DecimalField(max_digits=18, decimal_places=4, null=True)
    max_close = DecimalField(max_digits=18, decimal_places=4, null=True)
    min_close = DecimalField(max_digits=18, decimal_places=4, null=True)
    return_pct = DecimalField(max_digits=10, decimal_places=6, null=True)
    status = TextField(constraints=[SQL(
        "CHECK (status IN ('target_hit','stop_hit','expired','open','no_data'))")])
    resolved_on = DateField(null=True)
    correct = BooleanField(null=True)

    class Meta:
        table_name = "recommendation_outcome"
