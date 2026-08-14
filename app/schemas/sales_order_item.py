"""Sales order item schemas"""
from pydantic import BaseModel, ConfigDict, model_validator
from decimal import Decimal


class _CatalogOrFreeTextMixin(BaseModel):
    """Requires either a catalog item_id or a free-text description (e.g. 'Installation fee')."""
    item_id: int | None = None
    description: str | None = None

    @model_validator(mode="after")
    def _require_item_or_description(self):
        if self.item_id is None and not (self.description and self.description.strip()):
            raise ValueError("Provide either item_id (catalog item) or description (free-text line)")
        return self


class SalesOrderItemInput(_CatalogOrFreeTextMixin):
    """Simple input schema for creating order items (used with order creation)"""
    quantity_ordered: int
    unit_price: Decimal
    requires_delivery: bool = True
    notes: str | None = None


class SalesOrderItemBase(_CatalogOrFreeTextMixin):
    """Base sales order item schema"""
    quantity_ordered: int
    unit_price: Decimal
    line_total: Decimal
    requires_delivery: bool = True
    notes: str | None = None


class SalesOrderItemCreate(SalesOrderItemBase):
    """Sales order item creation schema (for direct item creation)"""
    sales_order_id: int
    workspace_id: int


class SalesOrderItemUpdate(BaseModel):
    """Sales order item update schema"""
    description: str | None = None
    quantity_ordered: int | None = None
    quantity_delivered: int | None = None
    unit_price: Decimal | None = None
    line_total: Decimal | None = None
    requires_delivery: bool | None = None
    notes: str | None = None


class SalesOrderItemFulfillRequest(BaseModel):
    """Optional data captured when fulfilling a non-delivery line item."""
    completion_code: str | None = None


class SalesOrderItemResponse(SalesOrderItemBase):
    """Sales order item response schema"""
    id: int
    workspace_id: int
    sales_order_id: int
    quantity_delivered: int
    fulfillment_completion_code: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SalesOrderItemListResponse(SalesOrderItemResponse):
    """Sales order item list response with related data"""
    item_name: str | None = None
    item_unit: str | None = None
    quantity_remaining: int | None = None
    quantity_planned: int | None = None
    quantity_available_to_plan: int | None = None

    model_config = ConfigDict(from_attributes=True)
