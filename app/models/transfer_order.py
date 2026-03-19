"""Transfer order model - for internal item movements"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Date
from sqlalchemy.orm import relationship
from datetime import datetime, date
from app.db.base_class import Base


class TransferOrder(Base):
    """
    Transfer orders for internal movement of items between locations.
    No external accounts involved, no invoices generated.
    """

    __tablename__ = "transfer_orders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)

    # === REFERENCE ===
    transfer_number = Column(String(100), nullable=False, unique=True, index=True)
    # Auto-generated: TR-2025-001

    # === SOURCE LOCATION ===
    source_location_type = Column(String(50), nullable=False)  # 'storage', 'machine', 'damaged'
    source_location_id = Column(Integer, nullable=False)  # factory_id, machine_id, etc.

    # === DESTINATION LOCATION ===
    destination_location_type = Column(String(50), nullable=False)  # 'storage', 'machine', 'project', 'damaged'
    destination_location_id = Column(Integer, nullable=False)  # factory_id, machine_id, project_component_id, etc.

    # === DATES ===
    order_date = Column(Date, nullable=False, default=date.today)

    # === WORKFLOW ===
    current_status_id = Column(Integer, ForeignKey("statuses.id", ondelete="RESTRICT"), nullable=False, index=True)

    # === DESCRIPTION & NOTES ===
    description = Column(Text, nullable=True)
    note = Column(Text, nullable=True)

    # === AUDIT ===
    created_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)
    completed_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # === RELATIONSHIPS ===
    current_status = relationship("Status", backref="transfer_orders")
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_transfer_orders")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_transfer_orders")
    completer = relationship("Profile", foreign_keys=[completed_by], backref="completed_transfer_orders")
