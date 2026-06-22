"""Item summary schemas for catalog detail hub."""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field


class ItemSummaryTag(BaseModel):
    id: int
    name: str
    tag_code: str
    color: str | None = None
    icon: str | None = None
    is_system_tag: bool = False


class ItemSummaryItem(BaseModel):
    id: int
    workspace_id: int
    name: str
    description: str | None = None
    unit: str
    sku: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None
    created_by: int | None = None
    updated_by: int | None = None
    tags: List[ItemSummaryTag] = Field(default_factory=list)


class ItemSummaryKpis(BaseModel):
    storage_qty_total: int = 0
    machine_placement_count: int = 0
    product_qty_total: int = 0
    factory_count_with_stock: int = 0


class ItemSummaryInventoryRow(BaseModel):
    factory_id: int
    factory_name: str
    inventory_type: str
    qty: int
    avg_price: Decimal | None = None
    est_value: Decimal | None = None


class ItemSummaryProductRow(BaseModel):
    factory_id: int
    factory_name: str
    qty: int
    avg_cost: Decimal | None = None
    selling_price: Decimal | None = None
    is_available_for_sale: bool = False
    margin_hint: Decimal | None = None


class ItemSummaryMachinePlacement(BaseModel):
    machine_id: int
    machine_name: str
    factory_id: int
    factory_name: str
    factory_section_id: int
    factory_section_name: str
    qty: int
    req_qty: int | None = None
    defective_qty: int | None = None
    is_low_stock: bool = False


class ItemSummaryOrderStats(BaseModel):
    purchase_qty: Decimal = Decimal('0')
    transfer_qty: Decimal = Decimal('0')
    sales_qty: Decimal = Decimal('0')
    total_quantity: Decimal = Decimal('0')
    total_spend: Decimal = Decimal('0')
    line_count: int = 0


class ItemSummaryOrderStatsPeriod(BaseModel):
    days_30: ItemSummaryOrderStats = Field(default_factory=ItemSummaryOrderStats)
    days_90: ItemSummaryOrderStats = Field(default_factory=ItemSummaryOrderStats)
    all_time: ItemSummaryOrderStats = Field(default_factory=ItemSummaryOrderStats)


class ItemSummaryPeriodPricing(BaseModel):
    avg_unit_price_weighted: Decimal | None = None
    min_unit_price: Decimal | None = None
    max_unit_price: Decimal | None = None


class ItemSummaryPricingPeriod(BaseModel):
    days_30: ItemSummaryPeriodPricing = Field(default_factory=ItemSummaryPeriodPricing)
    days_90: ItemSummaryPeriodPricing = Field(default_factory=ItemSummaryPeriodPricing)
    all_time: ItemSummaryPeriodPricing = Field(default_factory=ItemSummaryPeriodPricing)


class ItemSummaryPricing(BaseModel):
    last_unit_price: Decimal | None = None
    open_po_line_count: int = 0
    open_qty_outstanding: Decimal = Decimal('0')
    period: ItemSummaryPricingPeriod = Field(default_factory=ItemSummaryPricingPeriod)


class ItemSummarySupplierRow(BaseModel):
    account_id: int
    account_name: str
    order_count: int
    total_qty: Decimal
    total_spend: Decimal
    avg_unit_price_weighted: Decimal | None = None
    last_unit_price: Decimal | None = None
    last_order_date: date | None = None


class ItemSummarySupplierHighlights(BaseModel):
    cheapest: ItemSummarySupplierRow | None = None
    most_frequent: ItemSummarySupplierRow | None = None


class ItemSummarySupplierPeriod(BaseModel):
    highlights: ItemSummarySupplierHighlights = Field(
        default_factory=ItemSummarySupplierHighlights
    )
    suppliers: List[ItemSummarySupplierRow] = Field(default_factory=list)


class ItemSummarySupplierStatsPeriod(BaseModel):
    days_30: ItemSummarySupplierPeriod = Field(default_factory=ItemSummarySupplierPeriod)
    days_90: ItemSummarySupplierPeriod = Field(default_factory=ItemSummarySupplierPeriod)
    all_time: ItemSummarySupplierPeriod = Field(default_factory=ItemSummarySupplierPeriod)


class ItemSummarySupplierStats(BaseModel):
    period: ItemSummarySupplierStatsPeriod = Field(
        default_factory=ItemSummarySupplierStatsPeriod
    )


class ItemSummaryUsageCounts(BaseModel):
    formula_count: int = 0
    batch_line_count: int = 0
    project_component_count: int = 0
    work_order_line_count: int = 0


class ItemSummaryFormulaUsage(BaseModel):
    formula_id: int
    formula_code: str
    name: str
    item_role: str


class ItemSummaryBatchUsage(BaseModel):
    batch_id: int
    batch_number: str
    item_role: str
    status: str | None = None


class ItemSummaryProjectUsage(BaseModel):
    project_id: int
    project_name: str
    component_id: int
    component_name: str


class ItemSummaryWorkOrderUsage(BaseModel):
    work_order_id: int
    work_order_number: str
    title: str


class ItemSummaryUsageDetails(BaseModel):
    formulas: List[ItemSummaryFormulaUsage] = Field(default_factory=list)
    batches: List[ItemSummaryBatchUsage] = Field(default_factory=list)
    projects: List[ItemSummaryProjectUsage] = Field(default_factory=list)
    work_orders: List[ItemSummaryWorkOrderUsage] = Field(default_factory=list)


class ItemSummaryRecentActivity(BaseModel):
    source: Literal['inventory', 'product', 'machine']
    performed_at: datetime
    transaction_type: str
    quantity: int
    factory_id: int | None = None
    factory_name: str | None = None
    machine_id: int | None = None
    machine_name: str | None = None
    inventory_type: str | None = None
    order_type: str | None = None
    order_id: int | None = None
    order_number: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ItemSummaryResponse(BaseModel):
    item: ItemSummaryItem
    kpis: ItemSummaryKpis
    inventory_rows: List[ItemSummaryInventoryRow] = Field(default_factory=list)
    product_rows: List[ItemSummaryProductRow] = Field(default_factory=list)
    machine_placements: List[ItemSummaryMachinePlacement] = Field(default_factory=list)
    order_stats: ItemSummaryOrderStatsPeriod
    pricing: ItemSummaryPricing
    supplier_stats: ItemSummarySupplierStats
    usage_counts: ItemSummaryUsageCounts
    usage_details: ItemSummaryUsageDetails = Field(default_factory=ItemSummaryUsageDetails)
    recent_activity: List[ItemSummaryRecentActivity] = Field(default_factory=list)
