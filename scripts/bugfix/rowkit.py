"""Row kit: build database rows for throwaway checks, with every required parent filled in.

For the bug fixer and the systems engineer, who can't use the test suite's helpers.
Everything happens inside one transaction that is ROLLED BACK at the end, so
nothing is ever saved.

    from scripts.bugfix.rowkit import scratch_session, make

    with scratch_session() as db:                      # TEST_DATABASE_URL or marker_test
        t = make(db, WorkOrderTemplateApprover)       # builds template, workspace, plan, profile, ...
        s = make(db, FactorySection, is_deleted=True, factory=t.work_order_template.default_factory_section.factory)
        ...

How it fills a model:
  * columns you pass win (`name="X"`, or a relationship object such as `factory=f`);
  * a required foreign key gets a parent row, built the same way (recursively);
  * all rows share ONE workspace, plan and profile per session unless you pass
    your own, so workspace rules (HR-16) hold by default;
  * other required columns get a simple value by type (text "<col>-<n>", 1, 0,
    False, today, the first enum value, {}).
Columns with a default or server default, and nullable ones, are left to the database.

Run checks from the worktree root with `PYTHONPATH=.` so `app` and `scripts` import.
"""
from __future__ import annotations

import datetime as _dt
import decimal
import enum
import itertools
import os
from contextlib import contextmanager

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

import app.db.base  # noqa: F401  (registers every model)
from app.db.base_class import Base

_counter = itertools.count(1)
_SHARED = ("workspaces", "subscription_plans", "profiles")


@contextmanager
def scratch_session():
    url = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/marker_test")
    if not (make_url(url).database or "").endswith("_test"):
        raise RuntimeError("rowkit only runs against a *_test database")
    eng = create_engine(url)
    conn = eng.connect()
    outer = conn.begin()
    db = Session(bind=conn, autoflush=False, join_transaction_mode="create_savepoint")
    db.info["rowkit_cache"] = {}
    try:
        yield db
    finally:
        db.close()
        outer.rollback()   # nothing is ever saved
        conn.close()
        eng.dispose()


def _class_for_table(table) -> type:
    for m in Base.registry.mappers:
        if m.local_table is table:
            return m.class_
    raise LookupError(f"no mapped class for table {table.name}")


def _value_for(col, n: int):
    t = col.type
    if isinstance(t, Enum):
        if t.enum_class is not None:
            first = next(iter(t.enum_class))
            return first.value if isinstance(first, enum.Enum) else first
        return t.enums[0]
    if isinstance(t, Boolean):
        return False
    if isinstance(t, (Integer,)):
        return n
    if isinstance(t, Numeric):
        return decimal.Decimal(0)
    if isinstance(t, DateTime):
        return _dt.datetime.now(_dt.UTC).replace(tzinfo=None)
    if isinstance(t, Date):
        return _dt.datetime.now(_dt.UTC).date()
    if isinstance(t, (JSON, JSONB)):
        return {}
    if isinstance(t, (String, Text)):
        s = f"{col.name}-{n}"
        length = getattr(t, "length", None)
        return s[:length] if length else s
    return None


def make(db: Session, model: type, **overrides):
    """Create, add and flush one `model` row with all required parents. Returns it."""
    cache = db.info.setdefault("rowkit_cache", {})
    mapper = model.__mapper__
    rel_by_fk = {}
    for rel in mapper.relationships:
        for local in rel.local_columns:
            rel_by_fk[local.key] = rel
    values = dict(overrides)
    for rel_name, obj in list(overrides.items()):          # relationship objects passed in
        if rel_name in mapper.relationships and obj is not None:
            for local, remote in mapper.relationships[rel_name].local_remote_pairs:
                values.setdefault(local.key, getattr(obj, remote.key))
    n = next(_counter)
    for col in mapper.local_table.columns:
        key = mapper.get_property_by_column(col).key
        if key in values or col.primary_key and col.autoincrement in (True, "auto"):
            continue
        if col.nullable or col.default is not None or col.server_default is not None:
            continue
        if col.foreign_keys:
            fk = next(iter(col.foreign_keys))
            parent_table = fk.column.table
            if parent_table.name in _SHARED and parent_table.name in cache:
                parent = cache[parent_table.name]
            else:
                parent = make(db, _class_for_table(parent_table))
                if parent_table.name in _SHARED:
                    cache[parent_table.name] = parent
            values[key] = getattr(parent, fk.column.key)
            continue
        v = _value_for(col, n)
        if v is not None:
            values[key] = v
    obj = model(**{k: v for k, v in values.items() if k in mapper.attrs or hasattr(model, k)})
    db.add(obj)
    db.flush()
    if mapper.local_table.name in _SHARED:
        cache.setdefault(mapper.local_table.name, obj)
    return obj
