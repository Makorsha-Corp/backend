"""Post completed purchase order lines into factory STORAGE inventory."""
from decimal import Decimal

from fastapi import HTTPException, status

PO_INVENTORY_SOURCE_TYPE = 'purchase_order'


def _quantity_to_int(quantity: Decimal, *, line_number: int) -> int:
    if quantity != quantity.to_integral_value():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f'Line {line_number} has a fractional received quantity; '
                'storage inventory requires whole units'
            ),
        )
    qty = int(quantity)
    if qty <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Line {line_number} has no received quantity to post',
        )
    return qty


def _weighted_avg_price(
    old_qty: int,
    old_avg: Decimal | None,
    add_qty: int,
    unit_cost: Decimal,
) -> Decimal:
    if add_qty <= 0:
        return old_avg or Decimal(0)
    if old_qty > 0 and old_avg is not None:
        numer = Decimal(old_qty) * old_avg + Decimal(add_qty) * unit_cost
        return (numer / Decimal(old_qty + add_qty)).quantize(Decimal('0.01'))
    return unit_cost


