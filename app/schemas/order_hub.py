"""Shared DTOs for purchase / expense / transfer order hub stats."""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class OrderHubRecentSummary(BaseModel):
    id: int
    order_number: str
    status_id: int
    status_name: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    account_id: int | None = None
    invoice_id: int | None = None
    total_amount: Decimal | None = None
    expense_category: str | None = None
    expense_date: date | None = None
    due_date: date | None = None
    source_location_type: str | None = None
    destination_location_type: str | None = None

    model_config = ConfigDict(from_attributes=True)


class OrderHubPendingHighlight(BaseModel):
    id: int
    order_number: str
    status_name: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderHubPendingStats(BaseModel):
    pending_planning_count: int = 0
    pending_planning: List[OrderHubPendingHighlight] = []
    missing_invoice_count: int = 0
    missing_invoice: List[OrderHubPendingHighlight] = []
    oldest_drafts: List[OrderHubPendingHighlight] = []
