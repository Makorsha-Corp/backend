"""Base Manager class for business logic"""
from typing import Generic, TypeVar, Type
from sqlalchemy.orm import Session
from app.db.base_class import Base


ModelType = TypeVar("ModelType", bound=Base)


class BaseManager(Generic[ModelType]):
    """
    Base manager class for handling business logic.

    Managers coordinate DAOs and implement business rules.
    They receive a session from the service layer and do NOT commit.
    """

    def __init__(self, model: Type[ModelType]):
        """
        Initialize manager with model

        Args:
            model: SQLAlchemy model class
        """
        self.model = model
