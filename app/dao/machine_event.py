"""Machine event DAO operations

SECURITY NOTICE:
This DAO handles workspace-scoped data. All query methods MUST filter by workspace_id
to prevent unauthorized cross-workspace data access.
"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from app.dao.base import BaseDAO
from app.models.machine_event import MachineEvent
from app.models.enums import MachineEventTypeEnum
from app.schemas.machine_event import MachineEventCreate, MachineEventUpdate


class MachineEventDAO(BaseDAO[MachineEvent, MachineEventCreate, MachineEventUpdate]):
    """DAO for MachineEvent model (workspace-scoped)"""

    def get_by_machine(
        self, db: Session, machine_id: int, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[MachineEvent]:
        """
        Get all events for a specific machine, ordered by most recent first (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            machine_id: Machine ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of MachineEvent instances belonging to the workspace
        """
        return db.query(MachineEvent).filter(
            MachineEvent.workspace_id == workspace_id,  # SECURITY: workspace isolation
            MachineEvent.machine_id == machine_id
        ).order_by(desc(MachineEvent.started_at)).offset(skip).limit(limit).all()

    def get_by_type(
        self, db: Session, event_type: MachineEventTypeEnum, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[MachineEvent]:
        """
        Get all events of a specific type (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            event_type: Event type to filter by
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of MachineEvent instances belonging to the workspace
        """
        return db.query(MachineEvent).filter(
            MachineEvent.workspace_id == workspace_id,  # SECURITY: workspace isolation
            MachineEvent.event_type == event_type
        ).order_by(desc(MachineEvent.started_at)).offset(skip).limit(limit).all()

    def get_latest_by_machine(
        self, db: Session, machine_id: int, *, workspace_id: int
    ) -> Optional[MachineEvent]:
        """
        Get the most recent event for a specific machine (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            machine_id: Machine ID
            workspace_id: Workspace ID to filter by

        Returns:
            Latest MachineEvent instance or None
        """
        return db.query(MachineEvent).filter(
            MachineEvent.workspace_id == workspace_id,  # SECURITY: workspace isolation
            MachineEvent.machine_id == machine_id
        ).order_by(desc(MachineEvent.started_at)).first()

    def get_by_machine_and_type(
        self, db: Session, machine_id: int, event_type: MachineEventTypeEnum, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[MachineEvent]:
        """
        Get events for a specific machine filtered by event type (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            machine_id: Machine ID
            event_type: Event type to filter by
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of MachineEvent instances belonging to the workspace
        """
        return db.query(MachineEvent).filter(
            and_(
                MachineEvent.workspace_id == workspace_id,  # SECURITY: workspace isolation
                MachineEvent.machine_id == machine_id,
                MachineEvent.event_type == event_type
            )
        ).order_by(desc(MachineEvent.started_at)).offset(skip).limit(limit).all()

    def get_system_initiated(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[MachineEvent]:
        """
        Get all system-initiated events (initiated_by is NULL) (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of MachineEvent instances belonging to the workspace
        """
        return db.query(MachineEvent).filter(
            MachineEvent.workspace_id == workspace_id,  # SECURITY: workspace isolation
            MachineEvent.initiated_by.is_(None)
        ).order_by(desc(MachineEvent.started_at)).offset(skip).limit(limit).all()

    def get_user_initiated(
        self, db: Session, user_id: int, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[MachineEvent]:
        """
        Get all events initiated by a specific user (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            user_id: Profile ID of the user
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of MachineEvent instances belonging to the workspace
        """
        return db.query(MachineEvent).filter(
            MachineEvent.workspace_id == workspace_id,  # SECURITY: workspace isolation
            MachineEvent.initiated_by == user_id
        ).order_by(desc(MachineEvent.started_at)).offset(skip).limit(limit).all()

    def get_events_in_date_range(
        self, db: Session, start_date: datetime, end_date: datetime, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[MachineEvent]:
        """
        Get events within a specific date range (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            start_date: Start of date range
            end_date: End of date range
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of MachineEvent instances belonging to the workspace
        """
        return db.query(MachineEvent).filter(
            and_(
                MachineEvent.workspace_id == workspace_id,  # SECURITY: workspace isolation
                MachineEvent.started_at >= start_date,
                MachineEvent.started_at <= end_date
            )
        ).order_by(desc(MachineEvent.started_at)).offset(skip).limit(limit).all()

    def count_by_machine(self, db: Session, machine_id: int, *, workspace_id: int) -> int:
        """
        Count total events for a specific machine (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            machine_id: Machine ID
            workspace_id: Workspace ID to filter by

        Returns:
            Total count of events
        """
        return db.query(MachineEvent).filter(
            MachineEvent.workspace_id == workspace_id,  # SECURITY: workspace isolation
            MachineEvent.machine_id == machine_id
        ).count()

    def count_by_type(self, db: Session, event_type: MachineEventTypeEnum, *, workspace_id: int) -> int:
        """
        Count total events of a specific type (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            event_type: Event type to count
            workspace_id: Workspace ID to filter by

        Returns:
            Total count of events
        """
        return db.query(MachineEvent).filter(
            MachineEvent.workspace_id == workspace_id,  # SECURITY: workspace isolation
            MachineEvent.event_type == event_type
        ).count()


# Singleton instance
machine_event_dao = MachineEventDAO(MachineEvent)
