"""Work order template approver model - default approvers copied onto orders generated
from a template that requires approval"""
from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class WorkOrderTemplateApprover(Base):
    __tablename__ = "work_order_template_approvers"
    __table_args__ = (
        UniqueConstraint('work_order_template_id', 'user_id', name='uq_wo_template_approver'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    work_order_template_id = Column(Integer, ForeignKey("work_order_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)

    template = relationship("WorkOrderTemplate", backref="template_approvers")
    user = relationship("Profile")
