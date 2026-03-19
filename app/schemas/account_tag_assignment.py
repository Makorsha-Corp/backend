"""Account tag assignment schemas"""
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class AccountTagAssignmentBase(BaseModel):
    """Base account tag assignment schema"""
    account_id: int
    tag_id: int


class AccountTagAssignmentCreate(AccountTagAssignmentBase):
    """Schema for creating an account tag assignment (workspace_id injected by service)"""
    pass


class AccountTagAssignmentInDB(AccountTagAssignmentBase):
    """Account tag assignment schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    assigned_at: datetime
    assigned_by: Optional[int]


class AccountTagAssignmentResponse(AccountTagAssignmentInDB):
    """Account tag assignment response schema"""
    pass
