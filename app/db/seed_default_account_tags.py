"""
Seed default account tags for a workspace

This module provides functionality to create default system tags
when a new workspace is created.
"""
from sqlalchemy.orm import Session
from app.models.account_tag import AccountTag
from datetime import datetime


DEFAULT_ACCOUNT_TAGS = [
    {
        "name": "Supplier",
        "tag_code": "supplier",
        "color": "#3B82F6",
        "icon": "truck",
        "description": "Distributors whose stores we get parts from",
        "is_system_tag": True,
    },
    {
        "name": "Vendor",
        "tag_code": "vendor",
        "color": "#0EA5E9",
        "icon": "package",
        "description": "Companies whose parts we buy",
        "is_system_tag": True,
    },
    {
        "name": "Client",
        "tag_code": "client",
        "color": "#10B981",
        "icon": "users",
        "description": "Customers and clients we sell to",
        "is_system_tag": True,
    },
    {
        "name": "Utility",
        "tag_code": "utility",
        "color": "#F59E0B",
        "icon": "zap",
        "description": "Utility and service providers (electricity, internet, etc.)",
        "is_system_tag": True,
    },
    {
        "name": "Payroll",
        "tag_code": "payroll",
        "color": "#8B5CF6",
        "icon": "wallet",
        "description": "Employee payroll and salary accounts",
        "is_system_tag": True,
    },
]


def seed_default_account_tags(db: Session, workspace_id: int, created_by_user_id: int = None) -> list[AccountTag]:
    """
    Seed default system account tags for a workspace

    Args:
        db: Database session
        workspace_id: ID of the workspace to seed tags for
        created_by_user_id: Optional user ID who created the workspace

    Returns:
        List of created AccountTag objects

    Note:
        This function does NOT commit the transaction.
        The caller (service layer) is responsible for commit/rollback.
    """
    created_tags = []

    for tag_data in DEFAULT_ACCOUNT_TAGS:
        # Check if tag already exists (by tag_code in workspace)
        existing_tag = (
            db.query(AccountTag)
            .filter(
                AccountTag.workspace_id == workspace_id,
                AccountTag.tag_code == tag_data["tag_code"]
            )
            .first()
        )

        if not existing_tag:
            tag = AccountTag(
                workspace_id=workspace_id,
                name=tag_data["name"],
                tag_code=tag_data["tag_code"],
                color=tag_data["color"],
                icon=tag_data["icon"],
                description=tag_data["description"],
                is_system_tag=tag_data["is_system_tag"],
                is_active=True,
                usage_count=0,
                created_at=datetime.utcnow(),
                created_by=created_by_user_id,
            )
            db.add(tag)
            created_tags.append(tag)

    db.flush()  # Flush to get IDs, but don't commit
    return created_tags


def get_default_account_tag_codes() -> list[str]:
    """
    Get list of default account tag codes

    Returns:
        List of tag codes for default system account tags
    """
    return [tag["tag_code"] for tag in DEFAULT_ACCOUNT_TAGS]


def get_default_account_tag_by_code(tag_code: str) -> dict | None:
    """
    Get default account tag definition by code

    Args:
        tag_code: Tag code to look up

    Returns:
        Tag definition dict or None if not found
    """
    for tag in DEFAULT_ACCOUNT_TAGS:
        if tag["tag_code"] == tag_code:
            return tag
    return None
