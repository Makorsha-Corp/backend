"""Production Batch model - actual production logs"""
from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, Date, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base
from app.utils.time import utcnow
from app.models.workspace_shift import WorkspaceShift  # noqa: F401 — register before relationship()


class ProductionBatch(Base):
    """
    Production Batch model - represents a single production run.

    Tracks expected vs actual production for variance analysis.
    When formula is used, system calculates expected values.
    User logs actual values when batch completes.
    """

    __tablename__ = "production_batches"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)

    # Batch identification
    batch_number = Column(String(50), nullable=False, index=True)  # e.g., "B-2025-001"

    # Links
    production_line_id = Column(Integer, ForeignKey("production_lines.id", ondelete="RESTRICT"), nullable=False, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id", ondelete="SET NULL"), nullable=True, index=True)
    formula_id = Column(Integer, ForeignKey("production_formulas.id", ondelete="SET NULL"), nullable=True, index=True)
    program_id = Column(
        Integer,
        ForeignKey("production_batch_programs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    route_id = Column(Integer, ForeignKey("production_routes.id", ondelete="SET NULL"), nullable=True, index=True)
    planned_start_at = Column(DateTime, nullable=True)
    sales_order_item_id = Column(
        Integer, ForeignKey("sales_order_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # formula_id nullable: Can produce with or without formula (simple mode)

    # Batch metadata
    batch_date = Column(Date, nullable=False, index=True)  # When production happened
    shift_id = Column(Integer, ForeignKey("workspace_shifts.id", ondelete="SET NULL"), nullable=True, index=True)
    shift = Column(String(80), nullable=True)  # Snapshot of shift name at save/start
    status = Column(String(20), nullable=False, default='draft', index=True)
    # Valid statuses: 'draft', 'recurring', 'in_progress', 'completed', 'cancelled'

    # Output qty, duration, and variance are derived from steps on read.
    actual_start_time = Column(DateTime, nullable=True)
    actual_end_time = Column(DateTime, nullable=True)

    # Notes
    notes = Column(Text, nullable=True)  # Production notes, issues, observations

    # Audit fields
    created_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    started_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    started_at = Column(DateTime, nullable=True)

    completed_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint('workspace_id', 'batch_number', name='uq_batch_workspace_number'),
    )

    # Relationships
    workspace = relationship("Workspace", backref="production_batches")
    production_line = relationship("ProductionLine", backref="batches")
    formula = relationship("ProductionFormula", backref="batches")
    route = relationship("ProductionRoute", backref="batches")
    sales_order_item = relationship("SalesOrderItem", backref="production_batches")
    workspace_shift = relationship("WorkspaceShift", foreign_keys=[shift_id])
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_batches")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_batches")
    starter = relationship("Profile", foreign_keys=[started_by], backref="started_batches")
    completer = relationship("Profile", foreign_keys=[completed_by], backref="completed_batches")
