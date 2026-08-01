"""Validation helpers for catalog line items on orders."""
from typing import Callable, Iterable, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dao.item import item_dao


def assert_unique_catalog_item_ids(
    session: Session,
    workspace_id: int,
    entries: Iterable,
    *,
    get_item_id: Callable,
    detail_template: Optional[str] = None,
) -> None:
    """Reject payloads that list the same catalog item more than once."""
    seen: set[int] = set()
    for entry in entries:
        item_id = get_item_id(entry)
        if item_id is None:
            continue  # Free-text lines have no catalog item to dedupe against
        if item_id in seen:
            catalog_item = item_dao.get_by_id_and_workspace(
                session, id=item_id, workspace_id=workspace_id
            )
            name = catalog_item.name if catalog_item else f'Item #{item_id}'
            detail = detail_template or '{name} appears more than once on this order'
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail.format(name=name),
            )
        seen.add(item_id)


def catalog_item_already_on_order_detail(session: Session, *, item_id: int, workspace_id: int) -> str:
    catalog_item = item_dao.get_by_id_and_workspace(
        session, id=item_id, workspace_id=workspace_id
    )
    name = catalog_item.name if catalog_item else f'Item #{item_id}'
    return f'{name} is already on this order'


def assert_meets_minimum_order_quantities(
    session: Session,
    workspace_id: int,
    factory_id: int,
    entries: Iterable,
    *,
    get_item_id: Callable,
    get_quantity: Callable,
) -> None:
    """Reject lines ordered below the sellable Product's minimum order quantity."""
    from app.dao.product import product_dao

    for entry in entries:
        item_id = get_item_id(entry)
        if item_id is None:
            continue  # Free-text lines have no product minimum
        quantity = get_quantity(entry)
        product = product_dao.get_by_factory_item_available(
            session, factory_id=factory_id, item_id=item_id,
            is_available_for_sale=True, workspace_id=workspace_id,
        )
        if product and product.min_order_qty and quantity < product.min_order_qty:
            name = product.item_name or f'Item #{item_id}'
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f'Minimum order quantity for {name} is {product.min_order_qty} (requested {quantity})',
            )
