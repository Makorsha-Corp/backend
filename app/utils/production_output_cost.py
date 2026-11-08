"""Unit cost of a finished good from raw materials consumed on the batch."""
from decimal import Decimal


def unit_cost_from_raw(
    total_raw_cost: Decimal | None,
    output_quantity: Decimal | int,
) -> Decimal | None:
    """Spread consumed raw cost evenly across finished output units."""
    if total_raw_cost is None:
        return None
    qty = Decimal(str(output_quantity))
    if qty <= 0:
        return None
    raw = Decimal(total_raw_cost)
    if raw <= 0:
        return None
    return (raw / qty).quantize(Decimal("0.01"))
