"""Orders overview aggregation schemas"""
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class TopItemRow(BaseModel):
    item_id: int
    item_name: str
    item_unit: str | None = None
    total_quantity: Decimal
    total_spend: Decimal
    line_count: int
    purchase_qty: Decimal = Decimal('0')
    transfer_qty: Decimal = Decimal('0')
    sales_qty: Decimal = Decimal('0')


class TopAccountRow(BaseModel):
    account_id: int
    account_name: str
    total_spend: Decimal
    order_count: int


class TopExpenseCategoryRow(BaseModel):
    category: str
    total_spend: Decimal
    order_count: int


class TopFactoryRow(BaseModel):
    factory_id: int
    factory_name: str
    order_count: int
    total_value: Decimal
    purchase_count: int
    transfer_count: int
    sales_count: int
    work_count: int


class OrdersOverviewStatsResponse(BaseModel):
    top_items: list[TopItemRow] = Field(default_factory=list)
    top_vendors: list[TopAccountRow] = Field(default_factory=list)
    top_customers: list[TopAccountRow] = Field(default_factory=list)
    top_expense_categories: list[TopExpenseCategoryRow] = Field(default_factory=list)
    top_factories: list[TopFactoryRow] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
