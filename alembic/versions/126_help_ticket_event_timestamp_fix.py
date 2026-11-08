"""Correct help_ticket_events.created_at skew from naive UTC into TIMESTAMPTZ.

Revision ID: 126_help_ticket_event_timestamp_fix
Revises: 125_help_ticket_events
Create Date: 2026-09-27

Naive utcnow() inserted into TIMESTAMPTZ was interpreted in the DB session timezone,
shifting stored instants (~6h for UTC+6). Realign to authoritative source timestamps
where available; skip rows already within tolerance (post utcnow_aware() fix).
"""
from alembic import op

revision = "126_help_ticket_event_timestamp_fix"
down_revision = "125_help_ticket_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE help_ticket_events e
        SET created_at = t.created_at
        FROM help_tickets t
        WHERE e.help_ticket_id = t.id
          AND e.event_type = 'created'
          AND (t.created_at - e.created_at) > interval '2 hours'
          AND (t.created_at - e.created_at) < interval '12 hours'
        """
    )

    op.execute(
        """
        UPDATE help_ticket_events e
        SET created_at = (d.created_at AT TIME ZONE 'UTC')
        FROM discussions d
        WHERE e.event_type IN ('discussion_message', 'discussion_reply')
          AND e.metadata IS NOT NULL
          AND (e.metadata->>'discussion_id') ~ '^[0-9]+$'
          AND d.id = (e.metadata->>'discussion_id')::integer
          AND abs(
            extract(
              epoch from ((d.created_at AT TIME ZONE 'UTC') - e.created_at)
            )
          ) > 7200
        """
    )

    op.execute(
        """
        UPDATE help_ticket_events e
        SET created_at = (a.uploaded_at AT TIME ZONE 'UTC')
        FROM attachments a
        WHERE e.event_type IN ('attachment_added', 'attachment_removed')
          AND e.metadata IS NOT NULL
          AND (e.metadata->>'attachment_id') ~ '^[0-9]+$'
          AND a.id = (e.metadata->>'attachment_id')::integer
          AND abs(
            extract(
              epoch from ((a.uploaded_at AT TIME ZONE 'UTC') - e.created_at)
            )
          ) > 7200
        """
    )


def downgrade() -> None:
    # Data correction is not reversible without a backup.
    pass
