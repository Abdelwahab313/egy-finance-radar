"""Database package — the configured peewee Postgres connection.

`db` is a deferred ``PostgresqlDatabase``; the DSN is read from
``config.DATABASE_URL`` lazily at first ``connect()`` (or any query), so env
overrides such as ``DATABASE_URL=...`` set before a CLI run take effect. Models
in ``app.db.models`` bind to this single instance.
"""

from __future__ import annotations

from urllib.parse import urlparse

from peewee import PostgresqlDatabase

from app import config

# Deferred: no connection params yet. `init()` is called from `_initialized()`
# the first time we connect, reading config.DATABASE_URL at runtime.
db = PostgresqlDatabase(None)


def _dsn_to_kwargs(url: str) -> dict:
    """Parse a postgresql:// URL into peewee/psycopg2 connection kwargs."""
    parsed = urlparse(url)
    return {
        "database": parsed.path.lstrip("/"),
        "user": parsed.username,
        "password": parsed.password,
        "host": parsed.hostname,
        "port": parsed.port or 5432,
    }


def _ensure_initialized() -> None:
    """Bind `db` to the current DATABASE_URL if it hasn't been bound yet."""
    if db.database is None:
        kwargs = _dsn_to_kwargs(config.DATABASE_URL)
        db.init(kwargs.pop("database"), **kwargs)


def connect(reuse_if_open: bool = True):
    """Open (and lazily configure) the connection."""
    _ensure_initialized()
    if not (reuse_if_open and not db.is_closed()):
        db.connect(reuse_if_open=reuse_if_open)
    return db


def close() -> None:
    """Close the connection if open."""
    if not db.is_closed():
        db.close()
