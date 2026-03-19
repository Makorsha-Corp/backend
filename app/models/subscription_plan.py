"""SubscriptionPlan model"""
from sqlalchemy import Column, Integer, String, Text, Numeric, Boolean, DateTime
from sqlalchemy.types import JSON
from datetime import datetime
from app.db.base_class import Base


class SubscriptionPlan(Base):
    """Subscription plan model with limits and features"""

    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Pricing
    price_monthly = Column(Numeric(10, 2), nullable=True)
    price_yearly = Column(Numeric(10, 2), nullable=True)
    currency = Column(String(3), nullable=False, default='USD')

    # Limits (-1 means unlimited)
    max_members = Column(Integer, nullable=False, default=5)
    max_storage_mb = Column(Integer, nullable=False, default=1000)
    max_orders_per_month = Column(Integer, nullable=False, default=100)
    max_factories = Column(Integer, nullable=False, default=2)
    max_machines = Column(Integer, nullable=False, default=10)
    max_projects = Column(Integer, nullable=False, default=5)

    # Features (JSON array - works with both PostgreSQL and SQLite)
    features = Column(JSON, nullable=False, default=[])

    # Plan metadata
    is_default = Column(Boolean, nullable=False, default=False)
    is_custom = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
