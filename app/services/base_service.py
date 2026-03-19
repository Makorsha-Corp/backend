"""Base Service class for orchestrating business operations"""
from sqlalchemy.orm import Session
from typing import Optional


class BaseService:
    """
    Base service class for orchestrating business workflows.

    Services handle:
    1. Transaction boundaries (commit/rollback)
    2. Orchestrating multiple managers
    3. Cross-cutting concerns (notifications, logging, etc.)
    4. Error handling and exception translation
    """

    def _commit_transaction(self, db: Session) -> None:
        """
        Commit the current transaction

        Args:
            db: Database session

        Raises:
            Exception: If commit fails
        """
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise

    def _rollback_transaction(self, db: Session) -> None:
        """
        Rollback the current transaction

        Args:
            db: Database session
        """
        db.rollback()
