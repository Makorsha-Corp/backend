"""Row builders for unit tests.

Each `make_*` inserts one row with sensible defaults, flushes (so it has an id)
and returns it. Override any column with keyword arguments. Values that must be
unique are generated from a counter, so tests can call these freely.

Add a builder here when a second test file needs the same model — do not build
rows with bare MagicMock. Keep defaults minimal: only what NOT NULL / unique
constraints require.
"""
import itertools
import os

from sqlalchemy.orm import Session

from app.models.profile import Profile
from app.models.subscription_plan import SubscriptionPlan
from app.models.workspace import Workspace

# Starts from the process id: test runs side by side share the database, and a committed name must not repeat.
_seq = itertools.count(os.getpid() * 100_000 + 1)


def _n() -> int:
    return next(_seq)


def make_subscription_plan(db: Session, **overrides) -> SubscriptionPlan:
    n = _n()
    fields = {"name": f"plan-{n}", "display_name": f"Plan {n}"}
    fields.update(overrides)
    row = SubscriptionPlan(**fields)
    db.add(row)
    db.flush()
    return row


def make_workspace(db: Session, **overrides) -> Workspace:
    n = _n()
    fields = {"name": f"Workspace {n}", "slug": f"ws-{n}"}
    fields.update(overrides)
    if "subscription_plan_id" not in fields:
        fields["subscription_plan_id"] = make_subscription_plan(db).id
    row = Workspace(**fields)
    db.add(row)
    db.flush()
    return row


def make_profile(db: Session, **overrides) -> Profile:
    n = _n()
    fields = {
        "name": f"User {n}",
        "email": f"user{n}@test.local",
        "user_id": f"test-user-{n}",
        "hashed_password": "not-a-real-hash",
    }
    fields.update(overrides)
    row = Profile(**fields)
    db.add(row)
    db.flush()
    return row
