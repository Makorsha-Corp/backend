"""Account tag assignment schemas"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AccountTagAssignmentBase(BaseModel):
    """Base account tag assignment schema"""
    account_id: int
    tag_id: int


class AccountTagAssignmentCreate(AccountTagAssignmentBase):
    """Schema for creating an account tag assignment (workspace_id injected by service)"""


class AccountTagAssignmentInDB(AccountTagAssignmentBase):
    """Account tag assignment schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    assigned_at: datetime
    assigned_by: int | None


class AccountTagAssignmentResponse(AccountTagAssignmentInDB):
    """Account tag assignment response schema"""
