"""Order attachment DAO operations

SECURITY NOTICE:
This DAO handles workspace-scoped data. All query methods MUST filter by workspace_id
to prevent unauthorized cross-workspace data access.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.dao.base import BaseDAO
from app.models.order_attachment import OrderAttachment
from app.models.attachment import Attachment
from app.schemas.order_attachment import OrderAttachmentCreate, OrderAttachmentResponse


class OrderAttachmentDAO(BaseDAO[OrderAttachment, OrderAttachmentCreate, OrderAttachmentResponse]):
    """DAO for OrderAttachment junction model (workspace-scoped)"""

    def get_by_order(
        self, db: Session, order_id: int, *, workspace_id: int, include_deleted: bool = False
    ) -> List[Attachment]:
        """
        Get all attachments for a specific order (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            order_id: Order ID
            workspace_id: Workspace ID to filter by
            include_deleted: Whether to include soft-deleted attachments

        Returns:
            List of Attachment instances belonging to the workspace
        """
        query = db.query(Attachment).join(
            OrderAttachment, OrderAttachment.attachment_id == Attachment.id
        ).filter(
            OrderAttachment.workspace_id == workspace_id,  # SECURITY: workspace isolation
            OrderAttachment.order_id == order_id
        )

        if not include_deleted:
            query = query.filter(Attachment.is_deleted == False)

        return query.all()

    def get_by_attachment(
        self, db: Session, attachment_id: int, *, workspace_id: int
    ) -> List[OrderAttachment]:
        """
        Get all order links for a specific attachment (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            attachment_id: Attachment ID
            workspace_id: Workspace ID to filter by

        Returns:
            List of OrderAttachment instances belonging to the workspace
        """
        return db.query(OrderAttachment).filter(
            OrderAttachment.workspace_id == workspace_id,  # SECURITY: workspace isolation
            OrderAttachment.attachment_id == attachment_id
        ).all()

    def get_link(
        self, db: Session, order_id: int, attachment_id: int, *, workspace_id: int
    ) -> Optional[OrderAttachment]:
        """
        Get a specific order-attachment link (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            order_id: Order ID
            attachment_id: Attachment ID
            workspace_id: Workspace ID to filter by

        Returns:
            OrderAttachment instance or None
        """
        return db.query(OrderAttachment).filter(
            and_(
                OrderAttachment.workspace_id == workspace_id,  # SECURITY: workspace isolation
                OrderAttachment.order_id == order_id,
                OrderAttachment.attachment_id == attachment_id
            )
        ).first()

    def link_exists(
        self, db: Session, order_id: int, attachment_id: int, *, workspace_id: int
    ) -> bool:
        """
        Check if an attachment is already linked to an order (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            order_id: Order ID
            attachment_id: Attachment ID
            workspace_id: Workspace ID to filter by

        Returns:
            True if link exists, False otherwise
        """
        return self.get_link(db, order_id, attachment_id, workspace_id=workspace_id) is not None

    def unlink(
        self, db: Session, order_id: int, attachment_id: int, *, workspace_id: int
    ) -> Optional[OrderAttachment]:
        """
        Remove the link between an order and attachment (does NOT commit) (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            order_id: Order ID
            attachment_id: Attachment ID
            workspace_id: Workspace ID to filter by

        Returns:
            Deleted OrderAttachment instance or None
        """
        link = self.get_link(db, order_id, attachment_id, workspace_id=workspace_id)
        if not link:
            return None

        db.delete(link)
        db.flush()
        return link

    def get_attachment_count(
        self, db: Session, order_id: int, *, workspace_id: int
    ) -> int:
        """
        Get the count of active attachments for an order (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            order_id: Order ID
            workspace_id: Workspace ID to filter by

        Returns:
            Count of active attachments
        """
        return db.query(OrderAttachment).join(
            Attachment, OrderAttachment.attachment_id == Attachment.id
        ).filter(
            and_(
                OrderAttachment.workspace_id == workspace_id,  # SECURITY: workspace isolation
                OrderAttachment.order_id == order_id,
                Attachment.is_deleted == False
            )
        ).count()


# Singleton instance
order_attachment_dao = OrderAttachmentDAO(OrderAttachment)
