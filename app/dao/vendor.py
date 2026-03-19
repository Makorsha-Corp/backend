"""Vendor DAO operations

SECURITY NOTICE:
This DAO handles workspace-scoped data. All query methods MUST filter by workspace_id
to prevent unauthorized cross-workspace data access.
"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.dao.base import BaseDAO
from app.models.vendor import Vendor
from app.schemas.vendor import VendorCreate, VendorUpdate


class VendorDAO(BaseDAO[Vendor, VendorCreate, VendorUpdate]):
    """DAO for Vendor model (workspace-scoped)"""

    def get_active(
        self, db: Session, id: int, *, workspace_id: int
    ) -> Optional[Vendor]:
        """
        Get a single active (non-deleted) vendor by ID (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            id: Vendor ID
            workspace_id: Workspace ID to filter by

        Returns:
            Vendor instance or None
        """
        return db.query(Vendor).filter(
            and_(
                Vendor.workspace_id == workspace_id,  # SECURITY: workspace isolation
                Vendor.id == id,
                Vendor.is_deleted == False
            )
        ).first()

    def get_multi_active(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[Vendor]:
        """
        Get multiple active vendors with pagination (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of active vendor instances belonging to the workspace
        """
        return db.query(Vendor).filter(
            and_(
                Vendor.workspace_id == workspace_id,  # SECURITY: workspace isolation
                Vendor.is_deleted == False
            )
        ).offset(skip).limit(limit).all()

    def get_by_vendor_code(
        self, db: Session, vendor_code: str, *, workspace_id: int
    ) -> Optional[Vendor]:
        """
        Get vendor by vendor code (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            vendor_code: Vendor code
            workspace_id: Workspace ID to filter by

        Returns:
            Vendor instance or None
        """
        return db.query(Vendor).filter(
            and_(
                Vendor.workspace_id == workspace_id,  # SECURITY: workspace isolation
                Vendor.vendor_code == vendor_code,
                Vendor.is_deleted == False
            )
        ).first()

    def search_by_name(
        self, db: Session, name: str, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[Vendor]:
        """
        Search vendors by name (case-insensitive partial match) (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            name: Search term for vendor name
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of matching vendor instances belonging to the workspace
        """
        return db.query(Vendor).filter(
            and_(
                Vendor.workspace_id == workspace_id,  # SECURITY: workspace isolation
                Vendor.name.ilike(f"%{name}%"),
                Vendor.is_deleted == False
            )
        ).offset(skip).limit(limit).all()

    def get_active_vendors_only(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[Vendor]:
        """
        Get vendors that are both active and not deleted (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of active vendor instances belonging to the workspace
        """
        return db.query(Vendor).filter(
            and_(
                Vendor.workspace_id == workspace_id,  # SECURITY: workspace isolation
                Vendor.is_active == True,
                Vendor.is_deleted == False
            )
        ).offset(skip).limit(limit).all()

    def get_inactive_vendors(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[Vendor]:
        """
        Get vendors that are inactive but not deleted (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of inactive vendor instances belonging to the workspace
        """
        return db.query(Vendor).filter(
            and_(
                Vendor.workspace_id == workspace_id,  # SECURITY: workspace isolation
                Vendor.is_active == False,
                Vendor.is_deleted == False
            )
        ).offset(skip).limit(limit).all()

    def get_by_creator(
        self, db: Session, creator_id: int, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[Vendor]:
        """
        Get vendors created by a specific user (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            creator_id: Profile ID of creator
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of vendor instances belonging to the workspace
        """
        return db.query(Vendor).filter(
            and_(
                Vendor.workspace_id == workspace_id,  # SECURITY: workspace isolation
                Vendor.created_by == creator_id,
                Vendor.is_deleted == False
            )
        ).offset(skip).limit(limit).all()

    def soft_delete(
        self, db: Session, *, id: int, workspace_id: int, deleted_by: int
    ) -> Optional[Vendor]:
        """
        Soft delete a vendor (does NOT commit) (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            id: Vendor ID
            workspace_id: Workspace ID to filter by
            deleted_by: Profile ID of user deleting the vendor

        Returns:
            Soft-deleted vendor instance (not yet committed)
        """
        # Use workspace-filtered get
        vendor = db.query(Vendor).filter(
            and_(
                Vendor.workspace_id == workspace_id,  # SECURITY: workspace isolation
                Vendor.id == id
            )
        ).first()

        if not vendor:
            return None

        vendor.is_deleted = True
        vendor.deleted_at = datetime.utcnow()
        vendor.deleted_by = deleted_by

        db.add(vendor)
        db.flush()
        return vendor

    def restore(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[Vendor]:
        """
        Restore a soft-deleted vendor (does NOT commit) (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            id: Vendor ID
            workspace_id: Workspace ID to filter by

        Returns:
            Restored vendor instance (not yet committed)
        """
        # Use workspace-filtered get
        vendor = db.query(Vendor).filter(
            and_(
                Vendor.workspace_id == workspace_id,  # SECURITY: workspace isolation
                Vendor.id == id
            )
        ).first()

        if not vendor:
            return None

        vendor.is_deleted = False
        vendor.deleted_at = None
        vendor.deleted_by = None

        db.add(vendor)
        db.flush()
        return vendor

    def toggle_active(
        self, db: Session, *, id: int, workspace_id: int, updated_by: int
    ) -> Optional[Vendor]:
        """
        Toggle vendor active status (does NOT commit) (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            id: Vendor ID
            workspace_id: Workspace ID to filter by
            updated_by: Profile ID of user updating the vendor

        Returns:
            Updated vendor instance (not yet committed)
        """
        # Use workspace-filtered get
        vendor = db.query(Vendor).filter(
            and_(
                Vendor.workspace_id == workspace_id,  # SECURITY: workspace isolation
                Vendor.id == id
            )
        ).first()

        if not vendor:
            return None

        vendor.is_active = not vendor.is_active
        vendor.updated_by = updated_by
        vendor.updated_at = datetime.utcnow()

        db.add(vendor)
        db.flush()
        return vendor

    def update_with_user(
        self, db: Session, *, db_obj: Vendor, obj_in: VendorUpdate, updated_by: int
    ) -> Vendor:
        """
        Update vendor with tracking of who updated it (does NOT commit)

        NOTE: This method assumes db_obj has already been validated for workspace access.
        Always retrieve db_obj using workspace-filtered queries before calling this method.

        Args:
            db: Database session
            db_obj: Existing vendor instance (must belong to workspace)
            obj_in: Update data
            updated_by: Profile ID of user updating the vendor

        Returns:
            Updated vendor instance (not yet committed)
        """
        update_data = obj_in.model_dump(exclude_unset=True)
        update_data['updated_by'] = updated_by
        update_data['updated_at'] = datetime.utcnow()

        return self.update(db, db_obj=db_obj, obj_in=update_data)

    def count_active(self, db: Session, *, workspace_id: int) -> int:
        """
        Count total active (non-deleted) vendors (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by

        Returns:
            Count of active vendors in the workspace
        """
        return db.query(Vendor).filter(
            and_(
                Vendor.workspace_id == workspace_id,  # SECURITY: workspace isolation
                Vendor.is_deleted == False
            )
        ).count()

    def get_vendor_usage_count(
        self, db: Session, vendor_id: int, *, workspace_id: int
    ) -> int:
        """
        Count how many order parts reference this vendor (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            vendor_id: Vendor ID
            workspace_id: Workspace ID to filter by

        Returns:
            Count of order parts using this vendor in the workspace
        """
        from app.models.order_part import OrderPart
        return db.query(OrderPart).filter(
            and_(
                OrderPart.workspace_id == workspace_id,  # SECURITY: workspace isolation
                OrderPart.vendor_id == vendor_id
            )
        ).count()


# Singleton instance
vendor_dao = VendorDAO(Vendor)
