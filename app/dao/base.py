"""Base DAO (Data Access Object) operations"""
from typing import Generic, TypeVar, Type, List, Optional, Any, Dict
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.base_class import Base


ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseDAO(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Base DAO class for database operations.

    DAOs handle pure database access and DO NOT commit transactions.
    They use flush() to make changes visible within the transaction.
    The service layer is responsible for commit/rollback.
    """

    def __init__(self, model: Type[ModelType]):
        """
        Initialize DAO object with model

        Args:
            model: SQLAlchemy model class
        """
        self.model = model

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        """
        Get a single record by ID

        Args:
            db: Database session
            id: Record ID

        Returns:
            Model instance or None
        """
        return db.query(self.model).filter(self.model.id == id).first()

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """
        Get multiple records with pagination

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of model instances
        """
        return db.query(self.model).offset(skip).limit(limit).all()

    def create(self, db: Session, *, obj_in: CreateSchemaType | Dict[str, Any]) -> ModelType:
        """
        Create a new record (does NOT commit)

        Args:
            db: Database session
            obj_in: Pydantic schema or dict with creation data

        Returns:
            Created model instance (not yet committed)

        Note:
            Uses flush() to make the object visible within the transaction.
            The service layer must call commit() to persist changes.
        """
        if isinstance(obj_in, dict):
            obj_in_data = obj_in
        else:
            obj_in_data = obj_in.model_dump(by_alias=True)

        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.flush()  # Flush to get ID, but don't commit
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: ModelType,
        obj_in: UpdateSchemaType | Dict[str, Any]
    ) -> ModelType:
        """
        Update an existing record (does NOT commit)

        Args:
            db: Database session
            db_obj: Existing model instance
            obj_in: Pydantic schema or dict with update data

        Returns:
            Updated model instance (not yet committed)

        Note:
            Uses flush() to make changes visible within the transaction.
            The service layer must call commit() to persist changes.
        """
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True, by_alias=True)

        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        db.add(db_obj)
        db.flush()  # Flush but don't commit
        return db_obj

    def remove(self, db: Session, *, id: int) -> ModelType:
        """
        Delete a record (does NOT commit)

        Args:
            db: Database session
            id: Record ID

        Returns:
            Deleted model instance (not yet committed)

        Note:
            Uses flush() to make the deletion visible within the transaction.
            The service layer must call commit() to persist changes.
        """
        obj = db.query(self.model).get(id)
        db.delete(obj)
        db.flush()  # Flush but don't commit
        return obj

    # ==================== WORKSPACE-AWARE METHODS (CRITICAL FOR SECURITY) ====================

    def get_by_workspace(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """
        Get multiple records filtered by workspace (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of model instances belonging to workspace

        Note:
            ALWAYS use this instead of get_multi() for workspace-scoped models
        """
        return (
            db.query(self.model)
            .filter(self.model.workspace_id == workspace_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[ModelType]:
        """
        Get single record by ID AND workspace (SECURITY-CRITICAL)

        Args:
            db: Database session
            id: Record ID
            workspace_id: Workspace ID to filter by

        Returns:
            Model instance or None

        Note:
            ALWAYS use this instead of get() for workspace-scoped models.
            This prevents users from accessing data in other workspaces.
        """
        return (
            db.query(self.model)
            .filter(
                self.model.id == id,
                self.model.workspace_id == workspace_id
            )
            .first()
        )

    def create_in_workspace(
        self, db: Session, *, obj_in: CreateSchemaType, workspace_id: int
    ) -> ModelType:
        """
        Create a new record in workspace (SECURITY-CRITICAL)

        Args:
            db: Database session
            obj_in: Pydantic schema with creation data
            workspace_id: Workspace ID to assign

        Returns:
            Created model instance (not yet committed)

        Note:
            ALWAYS use this instead of create() for workspace-scoped models.
            Automatically sets workspace_id on the created object.
        """
        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data, workspace_id=workspace_id)
        db.add(db_obj)
        db.flush()  # Flush to get ID, but don't commit
        return db_obj
