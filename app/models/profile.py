"""Profile model"""
from sqlalchemy import Column, Integer, String, Enum
from app.db.base_class import Base
from app.models.enums import RoleEnum


class Profile(Base):
    """User profile model"""

    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    permission = Column(Enum(RoleEnum), nullable=False)
    position = Column(String, nullable=False)
    # For now, we'll use a simple user_id field instead of linking to auth.users
    # In production, this would link to your authentication system
    user_id = Column(String, nullable=False, unique=True)
    # Add password hash for simple auth (not in original schema but needed for JWT)
    hashed_password = Column(String, nullable=True) 
    