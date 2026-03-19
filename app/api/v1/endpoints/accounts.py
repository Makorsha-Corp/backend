"""
Account endpoints

Provides CRUD operations for accounts (unified entity for suppliers, clients, utilities, payroll).
Accounts can be tagged as suppliers, clients, utilities, or payroll entities.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.account import AccountCreate, AccountUpdate, AccountResponse, AccountWithTagsResponse
from app.services.account_service import account_service


router = APIRouter()


@router.get(
    "/",
    response_model=List[AccountWithTagsResponse],
    status_code=status.HTTP_200_OK,
    summary="List all accounts with tags",
    description="""
    Get all accounts with their tags included, with pagination and optional search.

    Returns direct list of accounts with tags (no wrapper).
    """
)
def get_accounts(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, le=100, description="Maximum number of records to return"),
    search: Optional[str] = Query(None, description="Search by account name"),
    tag_code: Optional[str] = Query(None, description="Filter by tag code (e.g. supplier, client, vendor)"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all accounts with their tags included"""
    accounts = account_service.get_accounts_with_tags(
        db, workspace_id=workspace.id, search=search, tag_code=tag_code, skip=skip, limit=limit
    )
    return accounts


@router.get(
    "/{account_id}",
    response_model=AccountWithTagsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get account by ID",
    description="Retrieve a single account by its ID with tags included. Raises 404 if not found."
)
def get_account(
    account_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """
    Get account by ID with tags included.

    Service layer will raise NotFoundError if account doesn't exist,
    which will be caught by exception handler and returned as RFC 7807 error.
    """
    return account_service.get_account_with_tags(db, account_id, workspace_id=workspace.id)


@router.post(
    "/",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new account",
    description="Create a new account. Returns the created account."
)
def create_account(
    account_in: AccountCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create new account.

    Returns created account directly (no wrapper).
    Any exceptions are handled by global exception handlers.
    """
    account = account_service.create_account(db, account_in, workspace.id, current_user.id)
    return account


@router.put(
    "/{account_id}",
    response_model=AccountResponse,
    status_code=status.HTTP_200_OK,
    summary="Update account",
    description="Update an existing account. Returns the updated account."
)
def update_account(
    account_id: int,
    account_in: AccountUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update account.

    Service layer will raise NotFoundError if account doesn't exist.
    Returns updated account directly (no wrapper).
    """
    account = account_service.update_account(db, account_id, account_in, workspace.id, current_user.id)
    return account


@router.delete(
    "/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete account",
    description="Soft delete an account (sets is_deleted=True). Returns 204 No Content on success."
)
def delete_account(
    account_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete account (soft delete).

    Service layer will raise NotFoundError if account doesn't exist.
    Returns 204 No Content on success (no body).
    """
    account_service.delete_account(db, account_id, workspace.id, current_user.id)
