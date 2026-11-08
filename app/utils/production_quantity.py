"""Two-decimal quantities for recipes, batches, and posted stock."""
from decimal import Decimal, ROUND_HALF_UP

QTY_PLACES = Decimal("0.01")


def as_quantity(value) -> Decimal:
    return Decimal(str(value)).quantize(QTY_PLACES, rounding=ROUND_HALF_UP)


def scale_quantity(quantity, multiplier) -> Decimal:
    scaled = Decimal(str(quantity)) * Decimal(str(multiplier))
    if scaled < 0:
        scaled = Decimal("0")
    return scaled.quantize(QTY_PLACES, rounding=ROUND_HALF_UP)
