"""Production Line schemas"""

from pydantic import BaseModel, ConfigDict, Field


class ProductionLineBase(BaseModel):
    """Base production line schema"""
    factory_id: int
    machine_id: int | None = None
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    is_active: bool = True


class ProductionLineCreate(ProductionLineBase):
    """Production line creation schema (workspace_id and created_by injected by service)"""


class ProductionLineUpdate(BaseModel):
    """Production line update schema"""
    machine_id: int | None = None
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    is_active: bool | None = None


class ProductionLineInDB(ProductionLineBase):
    """Production line schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    created_by: int | None = None
    updated_by: int | None = None


class ProductionLineResponse(ProductionLineInDB):
    """Production line response schema"""
