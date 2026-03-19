"""SubscriptionPlan schemas"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from decimal import Decimal


class SubscriptionPlanBase(BaseModel):
    """Base subscription plan schema"""
    name: str
    display_name: str
    description: str | None = None
    price_monthly: Decimal | None = None
    price_yearly: Decimal | None = None
    currency: str = 'USD'
    max_members: int = 5
    max_storage_mb: int = 1000
    max_orders_per_month: int = 100
    max_factories: int = 2
    max_machines: int = 10
    max_projects: int = 5
    features: list[str] = []
    is_active: bool = True


class SubscriptionPlanCreate(SubscriptionPlanBase):
    """Subscription plan creation schema"""
    is_custom: bool = False


class SubscriptionPlanUpdate(BaseModel):
    """Subscription plan update schema"""
    display_name: str | None = None
    description: str | None = None
    price_monthly: Decimal | None = None
    price_yearly: Decimal | None = None
    max_members: int | None = None
    max_storage_mb: int | None = None
    max_orders_per_month: int | None = None
    max_factories: int | None = None
    max_machines: int | None = None
    max_projects: int | None = None
    features: list[str] | None = None
    is_active: bool | None = None


class SubscriptionPlanResponse(SubscriptionPlanBase):
    """Subscription plan response schema"""
    id: int
    is_default: bool
    is_custom: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
