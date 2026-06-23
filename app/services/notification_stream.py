"""SSE generator for notification stream — LISTEN on PostgreSQL NOTIFY channel."""
from __future__ import annotations

import json
import select
from collections.abc import Iterator
from typing import Any

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from app.core.config import settings
from app.core.notification_channels import NOTIFICATION_CHANNEL


def notification_event_generator(user_id: int, workspace_id: int) -> Iterator[str]:
    conn = psycopg2.connect(settings.DATABASE_URL)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute(f"LISTEN {NOTIFICATION_CHANNEL};")

    try:
        yield "event: connected\ndata: {}\n\n"

        while True:
            ready, _, _ = select.select([conn], [], [], 30)
            if not ready:
                yield ": ping\n\n"
                continue

            conn.poll()
            while conn.notifies:
                notify = conn.notifies.pop(0)
                try:
                    data: dict[str, Any] = json.loads(notify.payload)
                except json.JSONDecodeError:
                    continue

                if (
                    data.get("recipient_user_id") == user_id
                    and data.get("workspace_id") == workspace_id
                ):
                    event_data = json.dumps(
                        {"notification_id": data.get("notification_id")}
                    )
                    yield f"event: notification\ndata: {event_data}\n\n"
    finally:
        cur.close()
        conn.close()
