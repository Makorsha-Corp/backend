"""
Seed default item tags for a workspace

This module provides functionality to create default system tags
when a new workspace is created.
"""
from sqlalchemy.orm import Session
from app.models.item_tag import ItemTag
from datetime import datetime


DEFAULT_SYSTEM_TAGS = [
    {
        "name": "Raw Material",
        "tag_code": "raw_material",
        "color": "#8B5CF6",
        "icon": "package",
        "description": "Input materials for production",
        "is_system_tag": True,
    },
    {
        "name": "Machine Part",
        "tag_code": "machine_part",
        "color": "#3B82F6",
        "icon": "cog",
        "description": "Parts and components for machines",
        "is_system_tag": True,
    },
    {
        "name": "Project Item",
        "tag_code": "project_item",
        "color": "#10B981",
        "icon": "folder",
        "description": "Items allocated to specific projects",
        "is_system_tag": True,
    },
    {
        "name": "Consumable",
        "tag_code": "consumable",
        "color": "#F59E0B",
        "icon": "fire",
        "description": "Supplies that are used up (oil, cleaning supplies, etc.)",
        "is_system_tag": True,
    },
    {
        "name": "Tool",
        "tag_code": "tool",
        "color": "#EF4444",
        "icon": "wrench",
        "description": "Tools and equipment",
        "is_system_tag": True,
    },
    {
        "name": "Finished Good",
        "tag_code": "finished_good",
        "color": "#14B8A6",
        "icon": "box",
        "description": "Products manufactured/produced by us",
        "is_system_tag": True,
    },
]


def seed_default_tags(db: Session, workspace_id: int, created_by_user_id: int = None) -> list[ItemTag]:
    """
    Seed default system tags for a workspace

    Args:
        db: Database session
        workspace_id: ID of the workspace to seed tags for
        created_by_user_id: Optional user ID who created the workspace

    Returns:
        List of created ItemTag objects

    Note:
        This function does NOT commit the transaction.
        The caller (service layer) is responsible for commit/rollback.
    """
    created_tags = []

    for tag_data in DEFAULT_SYSTEM_TAGS:
        # Check if tag already exists (by tag_code in workspace)
        existing_tag = (
            db.query(ItemTag)
            .filter(
                ItemTag.workspace_id == workspace_id,
                ItemTag.tag_code == tag_data["tag_code"]
            )
            .first()
        )

        if not existing_tag:
            tag = ItemTag(
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


def get_default_tag_codes() -> list[str]:
    """
    Get list of default tag codes

    Returns:
        List of tag codes for default system tags
    """
    return [tag["tag_code"] for tag in DEFAULT_SYSTEM_TAGS]


def get_default_tag_by_code(tag_code: str) -> dict | None:
    """
    Get default tag definition by code

    Args:
        tag_code: Tag code to look up

    Returns:
        Tag definition dict or None if not found
    """
    for tag in DEFAULT_SYSTEM_TAGS:
        if tag["tag_code"] == tag_code:
            return tag
    return None
