"""Platform waitlist signups from the marketing landing page."""
from sqlalchemy import Boolean, Column, DateTime, Integer, String, func

from app.db.base_class import Base


class WaitlistSignup(Base):
    __tablename__ = "waitlist_signups"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(320), nullable=False, unique=True, index=True)
    wants_product_updates = Column(Boolean, nullable=False, default=False, server_default="false")
    source = Column(String(64), nullable=True)
    ip_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
