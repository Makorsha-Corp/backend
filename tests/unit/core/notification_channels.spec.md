# Spec — `app/core/notification_channels.py`

> **Status:** APPROVED (2026-11-03; no questions)
> **Source commit:** e48a092

> **Verified by running** (throwaway script `v_core.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\acctdao\`): the value and its length; `LISTEN user_notifications;` on one autocommit connection receives a `pg_notify('user_notifications', …)` sent from another autocommit connection, with channel name and payload unchanged. Nothing was written to any table. **Read, not run:** `NotificationDAO.create` (`app/dao/notification.py`), `notification_event_generator` (`app/services/notification_stream.py`).

## Review
No questions. No house rule applies (a constant; no data, names, lists or money).

## Overview
One constant: the name of the PostgreSQL `LISTEN` / `NOTIFY` channel that carries "a notification was created" signals. `NotificationDAO.create` sends `pg_notify(NOTIFICATION_CHANNEL, payload)` after inserting a notification; `notification_event_generator` (the server-sent-events stream) runs `LISTEN <channel>` with the name pasted **unquoted** into the SQL. Both sides must use the same name, and it must be a valid unquoted identifier, or the stream never receives anything.

**Callables:** 1 specified (the constant) · 0 not specified
**Externals to mock:** none
**Integration-only behavior:** delivery itself. A `NOTIFY` is delivered only when its transaction commits; unit tests run in a transaction that is rolled back, so a delivery test needs two autocommit connections outside the test session (see Notes).

**Notes for the test designer:**
- `from app.core.notification_channels import NOTIFICATION_CHANNEL`.
- R2 can be checked without the database (a regular expression). The optional delivery check (R3) opens two `psycopg2` connections to the test database with `ISOLATION_LEVEL_AUTOCOMMIT`: `LISTEN` on one, `SELECT pg_notify(%s, %s)` on the other, then `select.select([conn], [], [], 5)`, `conn.poll()` and read `conn.notifies`. It writes nothing to any table.

---

## `NOTIFICATION_CHANNEL`
**Shape:** helper (constant)
**Persistence:** pure
**Visibility:** public (used by: `NotificationDAO.create`, `notification_event_generator`)

**Purpose:** The one channel name shared by the sender and the listener of notification signals.

**Rules:**
- **R1.** The value is exactly the string `"user_notifications"` (18 characters).
- **R2.** It is a valid unquoted PostgreSQL identifier that keeps its spelling: only lower-case ASCII letters, digits and `_`, not starting with a digit, at most 63 bytes (`^[a-z_][a-z0-9_]{0,62}$`). So `LISTEN user_notifications;` listens on the same channel that `pg_notify('user_notifications', …)` sends to.
- **R3.** A listener on this channel receives a notify sent to it, channel name and payload unchanged (integration-only; see Notes).

**Errors:** none

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 2 | constant value | R1, R2, R3 |
