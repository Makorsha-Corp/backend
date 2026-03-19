"""Work order model - tracks any kind of work (maintenance, inspection, etc.)"""
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Text, Numeric, Boolean, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base
from app.models.enums import WorkTypeEnum, WorkOrderPriorityEnum, WorkOrderStatusEnum


class WorkOrder(Base):
    """
    Work orders for tracking any kind of work performed.
    Can target machines or project components. May consume inventory items.
    """

    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    work_order_number = Column(String(50), nullable=False, index=True)
    work_type = Column(Enum(WorkTypeEnum), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Enum(WorkOrderPriorityEnum), nullable=False, default=WorkOrderPriorityEnum.MEDIUM)
    status = Column(Enum(WorkOrderStatusEnum), nullable=False, default=WorkOrderStatusEnum.DRAFT, index=True)

    # Location & target
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=True, index=True)
    project_component_id = Column(Integer, ForeignKey("project_components.id"), nullable=True, index=True)

    # Scheduling
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    # Cost
    cost = Column(Numeric(15, 2), nullable=True)

    # People
    assigned_to = Column(String(255), nullable=True)

    # Order approval
    order_approved = Column(Boolean, default=False, nullable=False)
    order_approved_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)
    order_approved_at = Column(DateTime, nullable=True)

    # Cost approval
    cost_approved = Column(Boolean, default=False, nullable=False)
    cost_approved_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)
    cost_approved_at = Column(DateTime, nullable=True)

    # Notes
    notes = Column(Text, nullable=True)
    completion_notes = Column(Text, nullable=True)

    # Audit fields
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    created_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())
    updated_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Soft delete
    is_active = Column(Boolean, default=True, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Relationships
    factory = relationship("Factory", backref="work_orders")
    machine = relationship("Machine", backref="work_orders")
    project_component = relationship("ProjectComponent", backref="work_orders")
    order_approver = relationship("Profile", foreign_keys=[order_approved_by], backref="order_approved_work_orders")
    cost_approver = relationship("Profile", foreign_keys=[cost_approved_by], backref="cost_approved_work_orders")
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_work_orders")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_work_orders")
    deleter = relationship("Profile", foreign_keys=[deleted_by], backref="deleted_work_orders")
    items = relationship("WorkOrderItem", back_populates="work_order", lazy="dynamic")
