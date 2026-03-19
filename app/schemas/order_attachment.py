"""Order attachment schemas"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class OrderAttachmentBase(BaseModel):
    """Base order attachment schema"""
    order_id: int
    attachment_id: int


class OrderAttachmentCreate(OrderAttachmentBase):
    """Order attachment creation schema"""
    attached_by: int


class OrderAttachmentResponse(OrderAttachmentBase):
    """Order attachment response schema"""
    id: int
    attached_at: datetime
    attached_by: int

    model_config = ConfigDict(from_attributes=True)
