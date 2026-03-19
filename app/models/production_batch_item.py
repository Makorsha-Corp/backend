"""Production Batch Item model - item-level tracking per batch"""
from sqlalchemy import Column, Integer, String, ForeignKey, Text, Numeric
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class ProductionBatchItem(Base):
    """
    Production Batch Item model - tracks individual items in a batch.

    Records expected vs actual for inputs, outputs, waste, and byproducts.
    Includes source/destination for inventory integration.
    """

    __tablename__ = "production_batch_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("production_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="RESTRICT"), nullable=False, index=True)

    # Item role in this batch
    item_role = Column(String(20), nullable=False, index=True)
    # Valid values: 'input', 'output', 'waste', 'byproduct'

    # === EXPECTED (from formula, set when batch starts) ===
    expected_quantity = Column(Integer, nullable=True)  # Expected amount

    # === ACTUAL (logged by user when batch completes) ===
    actual_quantity = Column(Integer, nullable=True)  # Actual amount used/produced

    # === SOURCE/DESTINATION (for inventory ledger integration) ===
    # For INPUTS: where materials came from
    source_location_type = Column(String(50), nullable=True)  # 'storage', 'machine', 'inventory'
    source_location_id = Column(Integer, nullable=True)  # factory_id, machine_id, etc.

    # For OUTPUTS/WASTE: where products/waste go to
    destination_location_type = Column(String(50), nullable=True)  # 'inventory', 'storage', 'damaged'
    destination_location_id = Column(Integer, nullable=True)  # factory_id, etc.

    # === VARIANCE (auto-calculated: actual - expected) ===
    variance_quantity = Column(Integer, nullable=True)  # Difference
    variance_percentage = Column(Numeric(5, 2), nullable=True)  # Percentage difference

    # Notes
    notes = Column(Text, nullable=True)  # Item-specific notes (e.g., "Material quality issue")

    # Relationships
    workspace = relationship("Workspace", backref="production_batch_items")
    batch = relationship("ProductionBatch", backref="batch_items")
    item = relationship("Item", backref="production_batch_items")
