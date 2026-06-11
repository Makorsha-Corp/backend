"""
Idempotent DDL for project visibility, members, and events.

Runs at app startup when Alembic did not apply revision 023 (e.g. Railway
deploy). Not a data backfill — schema only.
"""
import logging

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _table_names(inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector, table: str) -> set[str]:
    return {c['name'] for c in inspector.get_columns(table)}


def ensure_project_schema(db: Session) -> None:
    bind = db.get_bind()
    inspector = inspect(bind)
    tables = _table_names(inspector)

    if 'projects' in tables:
        project_columns = _column_names(inspector, 'projects')
        if 'visibility' not in project_columns:
            logger.warning('projects.visibility missing — applying startup DDL')
            db.execute(text('DROP TYPE IF EXISTS projectvisibilityenum'))
            db.execute(
                text(
                    "ALTER TABLE projects "
                    "ADD COLUMN visibility varchar(20) NOT NULL DEFAULT 'workspace'"
                )
            )
        else:
            db.execute(
                text(
                    """
                    DO $$ BEGIN
                      ALTER TABLE projects
                        ALTER COLUMN visibility TYPE varchar(20)
                        USING visibility::text;
                    EXCEPTION WHEN others THEN
                      NULL;
                    END $$;
                    """
                )
            )
            db.execute(text('DROP TYPE IF EXISTS projectvisibilityenum'))

    if 'project_members' not in tables:
        logger.warning('project_members table missing — applying startup DDL')
        db.execute(
            text(
                """
                CREATE TABLE project_members (
                    id SERIAL PRIMARY KEY,
                    workspace_id INTEGER NOT NULL
                        REFERENCES workspaces(id) ON DELETE CASCADE,
                    project_id INTEGER NOT NULL
                        REFERENCES projects(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL
                        REFERENCES profiles(id) ON DELETE CASCADE,
                    assigned_by INTEGER
                        REFERENCES profiles(id) ON DELETE SET NULL,
                    assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uq_project_member_project_user
                        UNIQUE (project_id, user_id)
                )
                """
            )
        )
        db.execute(
            text(
                'CREATE INDEX IF NOT EXISTS ix_project_members_workspace_id '
                'ON project_members (workspace_id)'
            )
        )
        db.execute(
            text(
                'CREATE INDEX IF NOT EXISTS ix_project_members_project_id '
                'ON project_members (project_id)'
            )
        )
        db.execute(
            text(
                'CREATE INDEX IF NOT EXISTS ix_project_members_user_id '
                'ON project_members (user_id)'
            )
        )

    if 'project_events' not in tables:
        logger.warning('project_events table missing — applying startup DDL')
        db.execute(
            text(
                """
                CREATE TABLE project_events (
                    id SERIAL PRIMARY KEY,
                    workspace_id INTEGER NOT NULL
                        REFERENCES workspaces(id) ON DELETE CASCADE,
                    project_id INTEGER NOT NULL
                        REFERENCES projects(id) ON DELETE CASCADE,
                    event_type VARCHAR(50) NOT NULL,
                    description TEXT NOT NULL,
                    metadata JSON,
                    performed_by INTEGER
                        REFERENCES profiles(id) ON DELETE SET NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        db.execute(
            text(
                'CREATE INDEX IF NOT EXISTS ix_project_events_workspace_id '
                'ON project_events (workspace_id)'
            )
        )
        db.execute(
            text(
                'CREATE INDEX IF NOT EXISTS ix_project_events_project_id '
                'ON project_events (project_id)'
            )
        )

    logger.info('Project schema ensure complete')
