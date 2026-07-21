"""Calendar event schemas — normalized cross-entity date feed."""
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CalendarCategory(str, Enum):
    WORK_ORDERS = "work_orders"
    MAINTENANCE = "maintenance"
    PURCHASE = "purchase"
    EXPENSE = "expense"
    SALES = "sales"
    INVOICES = "invoices"
    PRODUCTION = "production"
    PROJECTS = "projects"


class CalendarEventResponse(BaseModel):
    id: str
    category: CalendarCategory
    source_type: str
    record_id: int
    date: date
    date_label: str
    title: str
    subtitle: Optional[str] = None
    link: str
    meta: Dict[str, Any] = Field(default_factory=dict)


class CalendarEventsResponse(BaseModel):
    events: List[CalendarEventResponse]
    total: int
