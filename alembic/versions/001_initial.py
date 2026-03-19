"""Initial migration - create all tables

Revision ID: 001
Revises:
Create Date: 2026-03-18
"""
from alembic import op
from app.db.base import Base


revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
