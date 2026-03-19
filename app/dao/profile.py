"""DAO operations"""
from typing import Optional
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.profile import Profile
from app.schemas.profile import ProfileCreate, ProfileUpdate
from app.core.security import get_password_hash


class DAOProfile(BaseDAO[Profile, ProfileCreate, ProfileUpdate]):
    """DAO operations for Profile model"""

    def get_by_email(self, db: Session, *, email: str) -> Optional[Profile]:
        """
        Get profile by email

        Args:
            db: Database session
            email: User email

        Returns:
            Profile instance or None
        """
        return db.query(Profile).filter(Profile.email == email).first()

    def create(self, db: Session, *, obj_in: ProfileCreate) -> Profile:
        """
        Create a new profile with hashed password

        Args:
            db: Database session
            obj_in: Profile creation schema

        Returns:
            Created profile instance
        """
        db_obj = Profile(
            name=obj_in.name,
            email=obj_in.email,
            permission=obj_in.permission,
            position=obj_in.position,
            user_id=obj_in.email,  # Use email as user_id for now
            hashed_password=get_password_hash(obj_in.password),
        )
        db.add(db_obj)
        db.flush()  # Flush but don't commit
        return db_obj

    def authenticate(self, db: Session, *, email: str, password: str) -> Optional[Profile]:
        """
        Authenticate user by email and password

        Args:
            db: Database session
            email: User email
            password: Plain password

        Returns:
            Profile instance if authentication successful, None otherwise
        """
        from app.core.security import verify_password

        user = self.get_by_email(db, email=email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user


profile_dao = DAOProfile(Profile)
