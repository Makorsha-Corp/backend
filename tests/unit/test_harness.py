"""Checks that the unit-test harness itself behaves: real DB, isolation, rollback."""
from sqlalchemy import func, select, text

from app.models.workspace import Workspace
from tests.unit.factories import make_profile, make_workspace


def test_db_is_the_test_database(db):
    assert db.execute(text("select current_database()")).scalar().endswith("_test")


def test_factories_insert_real_rows(db):
    ws = make_workspace(db)
    user = make_profile(db)
    assert ws.id is not None and user.id is not None
    assert db.get(Workspace, ws.id).slug == ws.slug


def test_rows_from_other_tests_are_gone(db):
    # Runs after test_factories_insert_real_rows: its workspace must have been rolled back.
    assert db.scalar(select(func.count()).select_from(Workspace)) == 0


def test_commit_inside_code_does_not_leak(db):
    make_workspace(db)
    db.commit()  # only releases a savepoint
    assert db.scalar(select(func.count()).select_from(Workspace)) == 1


def test_pg_trgm_available(db):
    assert db.execute(text("select similarity('abc', 'abd')")).scalar() > 0
