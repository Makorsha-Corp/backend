"""Schemas for purchase order line item price history insights."""
from datetime import date
from decimal import Decimal
from typing import List

from pydantic import BaseModel, ConfigDict, Field


class ItemPriceInsightRef(BaseModel):
    purchase_order_id: int
    po_number: str
    account_id: int | None = None
    account_name: str | None = None
    unit_price: Decimal | None = None
    order_date: date | None = None

    model_config = ConfigDict(from_attributes=True)


class ItemPriceInsightLowest(BaseModel):
    avg_supplier: ItemPriceInsightRef | None = None
    all_time: ItemPriceInsightRef | None = None
    days_30: ItemPriceInsightRef | None = None
    days_90: ItemPriceInsightRef | None = None


class ItemPriceInsightRow(BaseModel):
    item_id: int
    last_ordered: ItemPriceInsightRef | None = None
    lowest: ItemPriceInsightLowest


class PoItemPriceInsightsResponse(BaseModel):
    items: List[ItemPriceInsightRow] = Field(default_factory=list)
