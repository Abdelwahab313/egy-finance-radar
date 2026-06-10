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
