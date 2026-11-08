"""Fractional production quantities stay at two decimals."""
from decimal import Decimal

from app.utils.production_quantity import as_quantity, scale_quantity


def test_as_quantity_keeps_tenths():
    assert as_quantity("1.2") == Decimal("1.20")
    assert as_quantity("9.5") == Decimal("9.50")


def test_scale_quantity_does_not_truncate():
    assert scale_quantity(Decimal("1.2"), 2) == Decimal("2.40")
