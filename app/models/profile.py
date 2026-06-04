"""Profile model"""
from sqlalchemy import Column, Integer, String
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
    