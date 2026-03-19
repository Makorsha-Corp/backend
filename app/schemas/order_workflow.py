"""Order workflow schemas"""
from typing import List, Dict, Any
from pydantic import BaseModel, ConfigDict


class OrderWorkflowBase(BaseModel):
    """Base order workflow schema"""
    name: str
    type: str
    description: str | None = None
    status_sequence: List[int]
    allowed_reverts_json: Dict[str, Any] | None = None


class OrderWorkflowCreate(OrderWorkflowBase):
    """Order workflow creation schema"""
    pass


class OrderWorkflowUpdate(BaseModel):
    """Order workflow update schema"""
    name: str | None = None
    description: str | None = None
    status_sequence: List[int] | None = None
    allowed_reverts_json: Dict[str, Any] | None = None


class OrderWorkflowResponse(OrderWorkflowBase):
    """Order workflow response schema"""
    id: int

    model_config = ConfigDict(from_attributes=True)
