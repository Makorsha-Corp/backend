"""Production Line schemas"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


class ProductionLineBase(BaseModel):
    """Base production line schema"""
    factory_id: int
    machine_id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    is_active: bool = True


class ProductionLineCreate(ProductionLineBase):
    """Production line creation schema (workspace_id and created_by injected by service)"""
    pass


class ProductionLineUpdate(BaseModel):
    """Production line update schema"""
    machine_id: Optional[int] = None
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class ProductionLineInDB(ProductionLineBase):
    """Production line schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    created_by: Optional[int] = None
    updated_by: Optional[int] = None


class ProductionLineResponse(ProductionLineInDB):
    """Production line response schema"""
    pass
