"""Profile model"""
from sqlalchemy import Boolean, Column, Integer, String
from app.db.base_class import Base


class Profile(Base):
    """User profile model"""

    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    # For now, we'll use a simple user_id field instead of linking to auth.users
    # In production, this would link to your authentication system
    user_id = Column(String, nullable=False, unique=True)
    hashed_password = Column(String, nullable=False)
    # IANA timezone for datetime display (e.g. Asia/Dhaka, America/New_York)
    timezone = Column(String(64), nullable=True)
    # Makorsha vendor staff — cross-workspace platform shell (/platform)
    is_platform_admin = Column(Boolean, nullable=False, default=False, server_default="false")
