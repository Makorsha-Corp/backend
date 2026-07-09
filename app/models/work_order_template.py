"""Work order template model - reusable "things that happen all the time" presets"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Numeric, Boolean, Enum, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base
from app.models.enums import WorkOrderPriorityEnum


class WorkOrderTemplate(Base):
    """
    Reusable preset for creating work orders — bundles the work type, parts, billing,
    and approval settings that repeat every time (e.g. "Monthly Oil Change").
    """

    __tablename__ = "work_order_templates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)

    template_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    work_order_type_id = Column(Integer, ForeignKey("work_order_types.id", ondelete="RESTRICT"), nullable=False, index=True)
    priority = Column(Enum(WorkOrderPriorityEnum), nullable=False, default=WorkOrderPriorityEnum.MEDIUM)
    assigned_to = Column(String(255), nullable=True)

    # === PARTS ===
    # When True, template_items are copied onto the generated order; the source factory
    # is always resolved dynamically to whichever machine the template is applied to.
    uses_inventory = Column(Boolean, nullable=False, default=False)

    # === BILLING ===
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True, index=True)
    cost = Column(Numeric(15, 2), nullable=True)

    # === APPROVAL ===
    requires_approval = Column(Boolean, nullable=False, default=False)

    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    # === RECURRENCE (mirrors order_templates) ===
    is_recurring = Column(Boolean, nullable=False, default=False)
    recurrence_type = Column(String(50), nullable=True)  # daily, weekly, monthly
    recurrence_day = Column(Integer, nullable=True)
    next_generation_date = Column(Date, nullable=True)
    auto_generate = Column(Boolean, nullable=False, default=False)

    # === SHEET DEFAULTS ===
    default_factory_section_id = Column(Integer, ForeignKey("factory_sections.id", ondelete="SET NULL"), nullable=True, index=True)
    default_machine_id = Column(Integer, ForeignKey("machines.id", ondelete="SET NULL"), nullable=True, index=True)

    # === AUDIT ===
    created_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

    # === RELATIONSHIPS ===
    work_order_type = relationship("WorkOrderType", backref="work_order_templates")
    account = relationship("Account", backref="work_order_templates")
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_work_order_templates")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_work_order_templates")

    @property
    def work_order_type_name(self) -> str | None:
        return self.work_order_type.name if self.work_order_type else None
