"""Order model"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


class Order(Base):
    """Order model"""

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    req_num = Column(String, nullable=True)
    order_note = Column(Text, nullable=True)
    order_type = Column(String, ForeignKey("order_workflows.type"), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    current_status_id = Column(Integer, ForeignKey("statuses.id"), nullable=False)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=True)
    factory_section_id = Column(Integer, ForeignKey("factory_sections.id"), nullable=True)
    order_workflow_id = Column(Integer, nullable=True)
    src_factory = Column(Integer, ForeignKey("factories.id"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    project_component_id = Column(Integer, ForeignKey("project_components.id"), nullable=True)
    src_project_component_id = Column(Integer, ForeignKey("project_components.id"), nullable=True)

    # Account & Invoice tracking (NEW)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True, index=True)
    is_invoiced = Column(Boolean, nullable=False, default=False)
    invoice_created_at = Column(DateTime, nullable=True)

    # Relationships
    created_by = relationship("Profile", foreign_keys=[created_by_user_id], backref="created_orders")
    department = relationship("Department", backref="orders")
    current_status = relationship("Status", backref="orders")
    factory = relationship("Factory", foreign_keys=[factory_id], backref="orders")
    machine = relationship("Machine", backref="orders")
    factory_section = relationship("FactorySection", backref="orders")
    workflow = relationship("OrderWorkflow", foreign_keys=[order_type], backref="orders")
    project = relationship("Project", foreign_keys=[project_id], backref="orders")
    project_component = relationship("ProjectComponent", foreign_keys=[project_component_id], backref="orders")
    src_project_component = relationship("ProjectComponent", foreign_keys=[src_project_component_id])
    account = relationship("Account", foreign_keys=[account_id], backref="orders")  # NEW
