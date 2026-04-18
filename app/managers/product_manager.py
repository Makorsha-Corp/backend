"""Product Manager - business logic for finished goods"""
from typing import List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate
from app.dao.product import product_dao
from app.dao.product_ledger import product_ledger_dao
from app.dao.factory import factory_dao


class ProductManager(BaseManager[Product]):
    """Manager for product (finished goods) business logic."""

    def __init__(self):
        super().__init__(Product)
        self.product_dao = product_dao
        self.ledger_dao = product_ledger_dao

    def create_product(
        self, session: Session, data: ProductCreate,
        workspace_id: int, user_id: int
    ) -> Product:
        """Create product record. Validates factory exists."""
        factory = factory_dao.get_by_id_and_workspace(
            session, id=data.factory_id, workspace_id=workspace_id
        )
        if not factory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Factory with ID {data.factory_id} not found"
            )

        # Check for duplicate
        existing = self.product_dao.get_by_factory_item_available(
            session, factory_id=data.factory_id, item_id=data.item_id,
            is_available_for_sale=data.is_available_for_sale, workspace_id=workspace_id
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Product record already exists for this item/factory/availability combination"
            )

        prod_dict = data.model_dump()
        prod_dict['workspace_id'] = workspace_id
        prod_dict['created_by'] = user_id

        record = self.product_dao.create(session, obj_in=prod_dict)

        # Create initial ledger entry if qty > 0
        if data.qty > 0:
            ledger_dict = {
                'workspace_id': workspace_id,
                'factory_id': data.factory_id,
                'item_id': data.item_id,
                'transaction_type': 'manual_add',
                'quantity': data.qty,
                'unit_cost': data.avg_cost,
                'total_cost': (data.avg_cost * data.qty) if data.avg_cost else None,
                'qty_before': 0,
                'qty_after': data.qty,
                'avg_cost_before': None,
                'avg_cost_after': data.avg_cost,
                'source_type': 'manual',
                'notes': 'Initial product record created',
                'performed_by': user_id,
            }
            self.ledger_dao.create(session, obj_in=ledger_dict)

        return record

    def update_product(
        self, session: Session, prod_id: int, data: ProductUpdate,
        workspace_id: int, user_id: int
    ) -> Product:
        """Update product record. Creates ledger entry if qty changes."""
        record = self.product_dao.get_by_id_and_workspace(
            session, id=prod_id, workspace_id=workspace_id
        )
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product record with ID {prod_id} not found"
            )
        if record.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update a deleted product record"
            )

        old_qty = record.qty
        old_avg = record.avg_cost

        update_dict = data.model_dump(exclude_unset=True)
        update_dict['updated_by'] = user_id

        updated = self.product_dao.update(session, db_obj=record, obj_in=update_dict)

        # If qty changed, create ledger entry
        new_qty = update_dict.get('qty')
        if new_qty is not None and new_qty != old_qty:
            new_avg = update_dict.get('avg_cost', old_avg)
            ledger_dict = {
                'workspace_id': workspace_id,
                'factory_id': record.factory_id,
                'item_id': record.item_id,
                'transaction_type': 'inventory_adjustment',
                'quantity': abs(new_qty - old_qty),
                'unit_cost': new_avg,
                'total_cost': (new_avg * abs(new_qty - old_qty)) if new_avg else None,
                'qty_before': old_qty,
                'qty_after': new_qty,
                'avg_cost_before': old_avg,
                'avg_cost_after': new_avg,
                'source_type': 'adjustment',
                'notes': f'Quantity adjusted from {old_qty} to {new_qty}',
                'performed_by': user_id,
            }
            self.ledger_dao.create(session, obj_in=ledger_dict)

        return updated

    def get_product(self, session: Session, prod_id: int, workspace_id: int) -> Product:
        """Get product record by ID."""
        record = self.product_dao.get_by_id_and_workspace(session, id=prod_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product record with ID {prod_id} not found")
        return record

    def list_products(
        self, session: Session, workspace_id: int,
        factory_id: Optional[int] = None,
        is_available_for_sale: Optional[bool] = None,
        skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """List product records with optional filters."""
        return self.product_dao.get_by_workspace(
            session, workspace_id=workspace_id,
            factory_id=factory_id,
            is_available_for_sale=is_available_for_sale,
            skip=skip, limit=limit
        )

    def delete_product(self, session: Session, prod_id: int, workspace_id: int, user_id: int) -> Product:
        """Soft delete product record."""
        record = self.product_dao.get_by_id_and_workspace(session, id=prod_id, workspace_id=workspace_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product record with ID {prod_id} not found")
        if record.is_deleted:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product record is already deleted")
        return self.product_dao.soft_delete(session, db_obj=record, deleted_by=user_id)

    def apply_production_output(
        self,
        session: Session,
        *,
        workspace_id: int,
        user_id: int,
        factory_id: int,
        item_id: int,
        quantity: int,
        batch_id: int,
        unit_cost: Optional[Decimal] = None,
    ) -> Product:
        """
        Increase finished-goods (products) quantity from a completed batch.
        Uses the not-for-sale product row per factory/item (warehouse / storage bucket).
        Caller must enforce idempotent batch posting.
        """
        if quantity <= 0:
            raise ValueError("Production output quantity must be positive")

        record = self.product_dao.get_by_factory_item_available(
            session,
            factory_id=factory_id,
            item_id=item_id,
            is_available_for_sale=False,
            workspace_id=workspace_id,
        )
        if not record:
            prod_dict = {
                "workspace_id": workspace_id,
                "item_id": item_id,
                "factory_id": factory_id,
                "qty": 0,
                "avg_cost": unit_cost,
                "is_available_for_sale": False,
                "created_by": user_id,
            }
            record = self.product_dao.create(session, obj_in=prod_dict)

        old_qty = record.qty
        old_avg = record.avg_cost
        new_qty = old_qty + quantity

        new_avg: Optional[Decimal]
        if unit_cost is not None:
            if old_qty > 0 and old_avg is not None:
                numer = Decimal(old_qty) * old_avg + Decimal(quantity) * unit_cost
                new_avg = (numer / Decimal(new_qty)).quantize(Decimal("0.01"))
            else:
                new_avg = unit_cost
        else:
            new_avg = old_avg

        ledger_dict = {
            "workspace_id": workspace_id,
            "factory_id": factory_id,
            "item_id": item_id,
            "transaction_type": "production",
            "quantity": quantity,
            "unit_cost": unit_cost,
            "total_cost": (unit_cost * Decimal(quantity)) if unit_cost is not None else None,
            "qty_before": old_qty,
            "qty_after": new_qty,
            "avg_cost_before": old_avg,
            "avg_cost_after": new_avg,
            "source_type": "production_batch",
            "source_id": batch_id,
            "notes": f"Production batch output (batch id {batch_id})",
            "performed_by": user_id,
        }
        self.ledger_dao.create(session, obj_in=ledger_dict)

        self.product_dao.update(
            session,
            db_obj=record,
            obj_in={
                "qty": new_qty,
                "avg_cost": new_avg,
                "updated_by": user_id,
            },
        )
        return record


product_manager = ProductManager()
