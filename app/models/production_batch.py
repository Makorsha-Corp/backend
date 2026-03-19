"""Production Batch model - actual production logs"""
from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, Date, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


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
    batch_number = Column(String(50), nullable=False, unique=True, index=True)  # e.g., "BATCH-2025-001"

    # Links
    production_line_id = Column(Integer, ForeignKey("production_lines.id", ondelete="RESTRICT"), nullable=False, index=True)
    formula_id = Column(Integer, ForeignKey("production_formulas.id", ondelete="SET NULL"), nullable=True, index=True)
    # formula_id nullable: Can produce with or without formula (simple mode)

    # Batch metadata
    batch_date = Column(Date, nullable=False, index=True)  # When production happened
    shift = Column(String(20), nullable=True)  # 'morning', 'afternoon', 'night', or custom
    status = Column(String(20), nullable=False, default='draft', index=True)
    # Valid statuses: 'draft', 'in_progress', 'completed', 'cancelled'

    # === EXPECTED VALUES (calculated from formula when batch starts) ===
    expected_output_quantity = Column(Integer, nullable=True)  # Expected output amount
    expected_duration_minutes = Column(Integer, nullable=True)  # Expected production time

    # === ACTUAL VALUES (logged by user when batch completes) ===
    actual_output_quantity = Column(Integer, nullable=True)  # Actual output produced
    actual_duration_minutes = Column(Integer, nullable=True)  # Actual time taken
    actual_start_time = Column(DateTime, nullable=True)  # When production actually started
    actual_end_time = Column(DateTime, nullable=True)  # When production actually ended

    # === VARIANCE (auto-calculated: actual - expected) ===
    output_variance_quantity = Column(Integer, nullable=True)  # Difference in quantity
    output_variance_percentage = Column(Numeric(5, 2), nullable=True)  # Percentage difference
    efficiency_percentage = Column(Numeric(5, 2), nullable=True)  # (actual / expected) * 100

    # Notes
    notes = Column(Text, nullable=True)  # Production notes, issues, observations

    # Audit fields
    created_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    started_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    started_at = Column(DateTime, nullable=True)

    completed_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    workspace = relationship("Workspace", backref="production_batches")
    production_line = relationship("ProductionLine", backref="batches")
    formula = relationship("ProductionFormula", backref="batches")
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_batches")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_batches")
    starter = relationship("Profile", foreign_keys=[started_by], backref="started_batches")
    completer = relationship("Profile", foreign_keys=[completed_by], backref="completed_batches")
