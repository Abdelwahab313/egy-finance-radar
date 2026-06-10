"""Tiny SQL migration runner — ``python -m app.db.migrate``.

Ensures ``schema_migrations`` exists, finds ``backend/migrations/*.sql`` sorted by
name, and applies each not-yet-applied file inside its own transaction, recording
the filename as the version. Idempotent: re-running applies nothing.
"""

from __future__ import annotations

from pathlib import Path

from app.db import connect, db

# backend/app/db/migrate.py -> backend/migrations
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "migrations"

_ENSURE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def _applied_versions() -> set[str]:
    rows = db.execute_sql("SELECT version FROM schema_migrations;").fetchall()
    return {r[0] for r in rows}


def run() -> int:
    """Apply all pending migrations. Returns the number applied."""
    connect()
    db.execute_sql(_ENSURE_TABLE_SQL)

    applied = _applied_versions()
    files = sorted(MIGRATIONS_DIR.glob("*.sql"), key=lambda p: p.name)

    count = 0
    for path in files:
        version = path.name
        if version in applied:
            print(f"skip   {version} (already applied)")
            continue
        sql = path.read_text()
        with db.atomic():
            db.execute_sql(sql)
            db.execute_sql(
                "INSERT INTO schema_migrations (version) VALUES (%s);", (version,)
            )
        print(f"apply  {version}")
        count += 1

    print(f"done: {count} migration(s) applied, {len(files)} file(s) total")
    return count


if __name__ == "__main__":
    run()
