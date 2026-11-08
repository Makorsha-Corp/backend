from decimal import Decimal

from app.utils.production_parameter_numeric import optional_numeric_from_text


def test_optional_numeric_from_text_parses_plain_numbers():
    assert optional_numeric_from_text("350") == Decimal("350")
    assert optional_numeric_from_text(" 1.5 ") == Decimal("1.5")


def test_optional_numeric_from_text_rejects_words():
    assert optional_numeric_from_text("ivory") is None
    assert optional_numeric_from_text("") is None
    assert optional_numeric_from_text(None) is None
