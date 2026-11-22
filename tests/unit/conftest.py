"""Shared fixtures for the unit-test pipeline (tests/unit/).

Every test gets `db`: a real SQLAlchemy session on a real Postgres database,
wrapped in a transaction that is rolled back afterwards, so tests never see each
other's rows and nothing is ever committed.

Database: TEST_DATABASE_URL (default postgresql://postgres:postgres@localhost:5432/marker_test).
The database name must end in `_test` — the harness refuses anything else so a
misconfigured run can never touch dev or production data. It is created if
missing and migrated to the Alembic head once per test session.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/marker_test",
)
_url = make_url(TEST_DATABASE_URL)
if not (_url.database or "").endswith("_test"):
    raise RuntimeError(
        f"Refusing to run unit tests against database {_url.database!r}: "
        "TEST_DATABASE_URL must point at a database whose name ends in '_test'."
    )

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _ensure_database_exists() -> None:
    admin = create_engine(_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": _url.database}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{_url.database}"'))
    admin.dispose()


def _migrate_to_head() -> None:
    if os.environ.get("UNIT_TESTS_SKIP_MIGRATE") == "1":
        return  # set by tests/unit/_tools/mutate.py, which migrates once up front
    # Run Alembic in a subprocess: alembic/env.py reads app settings at import
    # time, and this process may already have imported them with the dev URL.
    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT, env=env, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic upgrade head failed on the test database:\n{result.stderr}")


@pytest.fixture(scope="session")
def engine():
    _ensure_database_exists()
    _migrate_to_head()
    eng = create_engine(TEST_DATABASE_URL)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    """Real session; everything it does is rolled back after the test.

    Code under test may flush freely. A `commit()` inside the code under test
    only releases a savepoint (join_transaction_mode="create_savepoint"), so it
    cannot leak data either. Tests may use `db.begin_nested()` themselves, e.g.
    to observe a database error and keep using the session afterwards.
    Mirrors the app's SessionLocal: autoflush=False.
    """
    connection = engine.connect()
    outer = connection.begin()
    session = Session(
        bind=connection,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()
