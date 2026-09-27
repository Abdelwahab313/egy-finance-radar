"""Shared fixtures.

Unit tests run offline with no database. Tests that need Postgres request the
``db`` fixture, which connects to ``TEST_DATABASE_URL`` and skips when that
variable is unset or the server is unreachable. CI sets it to a service
container; locally, ``docker compose up db`` plus
``TEST_DATABASE_URL=postgresql://egx:egx@localhost:5433/egx`` does the same.
"""

from __future__ import annotations

import os

import pytest
from peewee import OperationalError

from app import config


@pytest.fixture(scope="session")
def db():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set; database tests need Postgres")
    config.DATABASE_URL = url
    from app.db import close, connect

    try:
        connection = connect()
    except OperationalError as exc:
        pytest.skip(f"Postgres unreachable at TEST_DATABASE_URL: {exc}")
    yield connection
    close()
