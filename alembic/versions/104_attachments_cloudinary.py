"""Extend attachments for Cloudinary and add attachment_links.

Revision ID: 104_attachments_cloudinary
Revises: 103_waitlist_signup_fields
Create Date: 2026-08-10
"""
import sqlalchemy as sa
from alembic import op

from app.db.migration_helpers import (
    add_column_if_not_exists,
    column_exists,
    drop_column_if_exists,
    table_exists,
)

revision = "104_attachments_cloudinary"
down_revision = "103_waitlist_signup_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column_if_not_exists(
        "attachments",
        sa.Column("storage_provider", sa.String(length=32), nullable=False, server_default="cloudinary"),
    )
    add_column_if_not_exists(
        "attachments",
        sa.Column("public_id", sa.String(length=512), nullable=True),
    )
    add_column_if_not_exists(
        "attachments",
        sa.Column("resource_type", sa.String(length=16), nullable=False, server_default="image"),
    )
    add_column_if_not_exists(
        "attachments",
        sa.Column("delivery_type", sa.String(length=16), nullable=False, server_default="upload"),
    )
    add_column_if_not_exists(
        "attachments",
        sa.Column("format", sa.String(length=16), nullable=True),
    )
    add_column_if_not_exists(
        "attachments",
        sa.Column("version", sa.BigInteger(), nullable=True),
    )
    add_column_if_not_exists(
        "attachments",
        sa.Column("width", sa.Integer(), nullable=True),
    )
    add_column_if_not_exists(
        "attachments",
        sa.Column("height", sa.Integer(), nullable=True),
    )
    add_column_if_not_exists(
        "attachments",
        sa.Column("asset_id", sa.String(length=64), nullable=True),
    )
    add_column_if_not_exists(
        "attachments",
        sa.Column("etag", sa.String(length=64), nullable=True),
    )
    add_column_if_not_exists(
        "attachments",
        sa.Column("upload_status", sa.String(length=16), nullable=False, server_default="pending"),
    )

    if column_exists("attachments", "file_url"):
        op.alter_column("attachments", "file_url", existing_type=sa.String(), nullable=True)

    op.create_index(
        "ix_attachments_public_id",
        "attachments",
        ["public_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_attachments_upload_status",
        "attachments",
        ["upload_status"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "uq_attachments_workspace_public_id",
        "attachments",
        ["workspace_id", "public_id"],
        unique=True,
        if_not_exists=True,
    )

    if not table_exists("attachment_links"):
        op.create_table(
            "attachment_links",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("workspace_id", sa.Integer(), nullable=False),
            sa.Column("attachment_id", sa.Integer(), nullable=False),
            sa.Column("entity_type", sa.String(length=64), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("linked_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
            sa.Column("linked_by", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["linked_by"], ["profiles.id"]),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "attachment_id",
                "entity_type",
                "entity_id",
                name="uq_attachment_link_entity",
            ),
        )
        op.create_index(
            "ix_attachment_links_workspace_entity",
            "attachment_links",
            ["workspace_id", "entity_type", "entity_id"],
            unique=False,
        )
        op.create_index(
            "ix_attachment_links_attachment_id",
            "attachment_links",
            ["attachment_id"],
            unique=False,
        )


def downgrade() -> None:
    if table_exists("attachment_links"):
        op.drop_index("ix_attachment_links_attachment_id", table_name="attachment_links", if_exists=True)
        op.drop_index("ix_attachment_links_workspace_entity", table_name="attachment_links", if_exists=True)
        op.drop_table("attachment_links")

    op.drop_index("uq_attachments_workspace_public_id", table_name="attachments", if_exists=True)
    op.drop_index("ix_attachments_upload_status", table_name="attachments", if_exists=True)
    op.drop_index("ix_attachments_public_id", table_name="attachments", if_exists=True)

    drop_column_if_exists("attachments", "upload_status")
    drop_column_if_exists("attachments", "etag")
    drop_column_if_exists("attachments", "asset_id")
    drop_column_if_exists("attachments", "height")
    drop_column_if_exists("attachments", "width")
    drop_column_if_exists("attachments", "version")
    drop_column_if_exists("attachments", "format")
    drop_column_if_exists("attachments", "delivery_type")
    drop_column_if_exists("attachments", "resource_type")
    drop_column_if_exists("attachments", "public_id")
    drop_column_if_exists("attachments", "storage_provider")

    if column_exists("attachments", "file_url"):
        op.alter_column("attachments", "file_url", existing_type=sa.String(), nullable=False)
