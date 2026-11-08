"""Tests for batch activity count aggregation."""
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.managers.production_batch_manager import ProductionBatchManager


def test_get_batch_activity_counts_groups_by_date():
    manager = ProductionBatchManager()
    session = MagicMock()

    row_a = MagicMock()
    row_a.__getitem__ = lambda self, i: (date(2026, 10, 1), 2)[i]
    row_b = MagicMock()
    row_b.__getitem__ = lambda self, i: (date(2026, 10, 5), 1)[i]

    query = MagicMock()
    session.query.return_value = query
    query.join.return_value = query
    query.filter.return_value = query
    query.group_by.return_value = query
    query.order_by.return_value = query
    query.all.return_value = [row_a, row_b]

    rows = manager.get_batch_activity_counts(
        session,
        workspace_id=1,
        factory_id=2,
        date_from=date(2026, 1, 1),
        date_to=date(2026, 12, 31),
        production_line_ids=[10],
        formula_ids=[5],
        statuses=["completed"],
    )

    assert rows == [
        {"date": date(2026, 10, 1), "count": 2},
        {"date": date(2026, 10, 5), "count": 1},
    ]
    assert query.filter.call_count >= 2
