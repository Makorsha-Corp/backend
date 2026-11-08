from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String

from app.db.base_class import Base
from app.utils.time import utcnow


class ProductionBatchProgram(Base):
    __tablename__ = "production_batch_programs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id", ondelete="CASCADE"), nullable=False, index=True)
    formula_id = Column(Integer, ForeignKey("production_formulas.id", ondelete="RESTRICT"), nullable=False, index=True)
    first_start_at = Column(DateTime, nullable=False)
    cadence = Column(String(16), nullable=False)
    interval_days = Column(Integer, nullable=True)
    end_date = Column(Date, nullable=False)
    status = Column(String(16), nullable=False, default="active", index=True)
    created_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
