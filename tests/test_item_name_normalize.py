"""Unit tests for item name normalization."""
import pytest

from app.utils.item_name_normalize import normalize_item_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Screw Driver 22m", "screw driver 22m"),
        ("Screw Driver 22 m", "screw driver 22m"),
        ("  Screw   Driver  22  m  ", "screw driver 22m"),
        ("Screw-Driver", "screw driver"),
        ("10 mm Bolt", "10mm bolt"),
        ("", ""),
        ("  ", ""),
    ],
)
def test_normalize_item_name(raw: str, expected: str) -> None:
    assert normalize_item_name(raw) == expected


def test_spacing_variants_normalize_to_same_value() -> None:
    assert normalize_item_name("Screw Driver 22m") == normalize_item_name("Screw Driver 22 m")


def test_punctuation_variants_normalize_to_same_value() -> None:
    assert normalize_item_name("Screw-Driver 22m") == normalize_item_name("Screw Driver 22m")
