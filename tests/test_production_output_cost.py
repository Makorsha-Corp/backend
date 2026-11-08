"""Raw-material unit cost posted onto finished goods."""
from decimal import Decimal

from app.utils.production_output_cost import unit_cost_from_raw


def test_unit_cost_none_without_raw_or_output():
    assert unit_cost_from_raw(None, 10) is None
    assert unit_cost_from_raw(Decimal("0"), 10) is None
    assert unit_cost_from_raw(Decimal("25"), 0) is None


def test_unit_cost_spreads_raw_across_output_units():
    assert unit_cost_from_raw(Decimal("25"), 10) == Decimal("2.50")
