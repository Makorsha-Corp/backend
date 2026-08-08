"""Platform waitlist signups from the marketing landing page."""
from sqlalchemy import Boolean, Column, DateTime, Integer, String, func

from app.db.base_class import Base
from app.models.enums import WaitlistStatusEnum


class WaitlistSignup(Base):
    __tablename__ = "waitlist_signups"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    company_name = Column(String(200), nullable=True)
    email = Column(String(320), nullable=False, unique=True, index=True)
    wants_product_updates = Column(Boolean, nullable=False, default=False, server_default="false")
    source = Column(String(64), nullable=True)
    status = Column(
        String(20),
        nullable=False,
        default=WaitlistStatusEnum.PENDING.value,
        server_default=WaitlistStatusEnum.PENDING.value,
        index=True,
    )
    ip_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
