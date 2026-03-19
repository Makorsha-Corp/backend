"""Order schemas"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class OrderBase(BaseModel):
    """Base order schema"""
    req_num: str | None = None
    order_note: str | None = None
    order_type: str | None = None
    department_id: int
    factory_id: int
    machine_id: int | None = None
    factory_section_id: int | None = None
    src_factory: int | None = None
    project_id: int | None = None
    project_component_id: int | None = None
    src_project_component_id: int | None = None


class OrderCreate(OrderBase):
    """Order creation schema"""
    pass


class OrderUpdate(BaseModel):
    """Order update schema"""
    order_note: str | None = None
    current_status_id: int | None = None
    machine_id: int | None = None
    factory_section_id: int | None = None


class OrderResponse(OrderBase):
    """Order response schema"""
    id: int
    created_at: datetime
    created_by_user_id: int
    current_status_id: int
    order_workflow_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class OrderListResponse(OrderResponse):
    """Order list response with related data"""
    # These will be populated via joins or separate queries
    current_status_name: str | None = None
    factory_name: str | None = None
    machine_name: str | None = None
    created_by_name: str | None = None

    model_config = ConfigDict(from_attributes=True)
