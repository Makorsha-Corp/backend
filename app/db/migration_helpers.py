"""Shared helpers for idempotent Alembic migrations (fresh install + upgrades)."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def table_exists(name: str) -> bool:
    return name in _inspector().get_table_names()


def column_names(table: str) -> set[str]:
    if not table_exists(table):
        return set()
    return {c["name"] for c in _inspector().get_columns(table)}


def column_exists(table: str, column: str) -> bool:
    return column in column_names(table)


def unique_constraint_exists(table: str, name: str) -> bool:
    if not table_exists(table):
        return False
    return name in {c["name"] for c in _inspector().get_unique_constraints(table)}


def foreign_key_constraint_exists(table: str, name: str) -> bool:
    if not table_exists(table):
        return False
    return name in {c["name"] for c in _inspector().get_foreign_keys(table)}


def drop_column_if_exists(table: str, column: str) -> None:
    if column_exists(table, column):
        op.drop_column(table, column)


def add_column_if_not_exists(table: str, column: sa.Column) -> None:
    if not column_exists(table, column.name):
        op.add_column(table, column)


def drop_foreign_key_if_exists(table: str, name: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}"))


def drop_unique_constraint_if_exists(table: str, name: str) -> None:
    op.execute(sa.text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}"))


def create_unique_constraint_if_not_exists(
    table: str, name: str, columns: list[str]
) -> None:
    if not unique_constraint_exists(table, name):
        op.create_unique_constraint(name, table, columns)
