"""Create landing_perf_reports table for Share feedback submissions.

Revision ID: 123_landing_perf_reports
Revises: 122_sales_order_decimal_quantities
Create Date: 2026-09-04
"""
import sqlalchemy as sa
from alembic import op

revision = "123_landing_perf_reports"
down_revision = "122_sales_order_decimal_quantities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "landing_perf_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("report_json", sa.JSON(), nullable=False),
        sa.Column("viewport", sa.String(length=32), nullable=True),
        sa.Column("ua_family", sa.String(length=128), nullable=True),
        sa.Column("is_mobile_tour", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("theme", sa.String(length=16), nullable=True),
        sa.Column("drop_rate_pct", sa.Float(), nullable=True),
        sa.Column("session_worst_ms", sa.Float(), nullable=True),
        sa.Column("lcp_ms", sa.Float(), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_landing_perf_reports_id", "landing_perf_reports", ["id"])
    op.create_index("ix_landing_perf_reports_viewport", "landing_perf_reports", ["viewport"])
    op.create_index("ix_landing_perf_reports_created_at", "landing_perf_reports", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_landing_perf_reports_created_at", table_name="landing_perf_reports")
    op.drop_index("ix_landing_perf_reports_viewport", table_name="landing_perf_reports")
    op.drop_index("ix_landing_perf_reports_id", table_name="landing_perf_reports")
    op.drop_table("landing_perf_reports")
