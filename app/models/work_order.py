"""Work order model - tracks any kind of work (maintenance, inspection, etc.)"""
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Text, Numeric, Boolean, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base
from app.models.enums import WorkOrderPriorityEnum, WorkOrderStatusEnum


class WorkOrder(Base):
    """
    Work orders for tracking any kind of work performed.
    Can target machines or project components. May consume inventory items.
    """

    __tablename__ = "work_orders"
    __table_args__ = (
        UniqueConstraint('workspace_id', 'work_order_number', name='uq_wo_workspace_number'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    work_order_number = Column(String(50), nullable=False, index=True)
    work_order_type_id = Column(Integer, ForeignKey("work_order_types.id", ondelete="RESTRICT"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Enum(WorkOrderPriorityEnum), nullable=False, default=WorkOrderPriorityEnum.MEDIUM)
    # Plain varchar (not a native Postgres enum type) so the value set can evolve without
    # the ALTER TYPE dance — validated at the Pydantic/schema layer via WorkOrderStatusEnum.
    status = Column(String(20), nullable=False, default=WorkOrderStatusEnum.DRAFT.value, index=True)

    # Location & target
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=True, index=True)
    project_component_id = Column(Integer, ForeignKey("project_components.id"), nullable=True, index=True)

    # Set when this order was generated from a template — traceability only.
    work_order_template_id = Column(Integer, ForeignKey("work_order_templates.id", ondelete="SET NULL"), nullable=True, index=True)

    # Scheduling
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    # Decided at creation time (the Maintenance wizard's "parts?" question) — when False,
    # items can never be added, matching the user's stated intent for this order.
    uses_inventory = Column(Boolean, nullable=False, default=True, server_default='true')

    # Cost — manual scalar for internal/free work; account_id/invoice_id for external/billed work
    cost = Column(Numeric(15, 2), nullable=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True, index=True)
    invoice_id = Column(Integer, ForeignKey("account_invoices.id", ondelete="SET NULL"), nullable=True, index=True)

    # People
    assigned_to = Column(String(255), nullable=True)

    # === APPROVALS ===
    required_approvals = Column(Integer, nullable=True)
    approved_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    # === LIFECYCLE STAMPS ===
    started_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # === VOID ===
    void_note = Column(Text, nullable=True)
    voided_at = Column(DateTime, nullable=True)
    voided_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)

    # Notes
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
    work_order_type = relationship("WorkOrderType", backref="work_orders")
    work_order_template = relationship("WorkOrderTemplate", backref="generated_work_orders")
    factory = relationship("Factory", backref="work_orders")
    machine = relationship("Machine", backref="work_orders")
    project_component = relationship("ProjectComponent", backref="work_orders")
    account = relationship("Account", backref="work_orders")
    invoice = relationship("AccountInvoice", backref="work_orders")
    approver = relationship("Profile", foreign_keys=[approved_by], backref="approved_work_orders")
    starter = relationship("Profile", foreign_keys=[started_by], backref="started_work_orders")
    completer = relationship("Profile", foreign_keys=[completed_by], backref="completed_work_orders")
    voider = relationship("Profile", foreign_keys=[voided_by], backref="voided_work_orders")
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_work_orders")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_work_orders")
    deleter = relationship("Profile", foreign_keys=[deleted_by], backref="deleted_work_orders")
    items = relationship("WorkOrderItem", back_populates="work_order", lazy="dynamic")
    approvers = relationship(
        "WorkOrderApprover",
        back_populates="work_order",
        cascade="all, delete-orphan",
    )

    @property
    def work_order_type_name(self) -> str | None:
        return self.work_order_type.name if self.work_order_type else None
