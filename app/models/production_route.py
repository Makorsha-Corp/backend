"""Production route — fixed line sequence a formula and batch can follow."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base_class import Base
from app.utils.time import utcnow


class ProductionRoute(Base):
    __tablename__ = "production_routes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id", ondelete="RESTRICT"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    workspace = relationship("Workspace", backref="production_routes")
    factory = relationship("Factory", backref="production_routes")
    creator = relationship("Profile", foreign_keys=[created_by])
    updater = relationship("Profile", foreign_keys=[updated_by])
    steps = relationship(
        "ProductionRouteStep",
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="ProductionRouteStep.step_order",
    )


class ProductionRouteStep(Base):
    __tablename__ = "production_route_steps"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    route_id = Column(Integer, ForeignKey("production_routes.id", ondelete="CASCADE"), nullable=False, index=True)
    step_order = Column(Integer, nullable=False)
    production_line_id = Column(
        Integer, ForeignKey("production_lines.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name = Column(String(200), nullable=False)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("route_id", "step_order", name="uq_route_step_order"),
    )

    route = relationship("ProductionRoute", back_populates="steps")
    production_line = relationship("ProductionLine", backref="route_steps")
