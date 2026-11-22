# Spec — `app/dao/notification.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-03.** **Delegated:** P1, Q1 and Q2 decided by Claude under the reviewer's delegation (2026-11-03). None is the owner's own answer. BUG-1412 stands from a house rule.

> **Base behaviour:** this DAO does **not** inherit `BaseDAO`; it has only the methods below.
>
> **Standing decisions applied here (not asked again):** a missing tie-break is a bug, and no order recipe counts as deterministic unless it ends in `id`. Logs are history.
>
> **Verified by running** (throwaway scripts `facts.py`, `v_misc.py`, harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsdao\`, each in one transaction rolled back against `marker_test`; nothing committed): the table's columns and constraints (**`read_at` and `created_at` are `timestamp with time zone` in the database**, the model declares plain `DateTime`); `create` with the defaults, `notification_type=None`, a 31-character type, no actor, a recipient of no membership, an unknown recipient, and the `pg_notify` statement it sends; `get_for_user` totals and unread counts with read, unread, another workspace and another user; the SQL (`ORDER BY created_at DESC` only, the actor joined); five rows with one `created_at`: paging one row at a time gave `[5], [5], [7], [6], [0]` (one row twice, one never); `mark_read` with mixed ids, again on read rows, with `[]` (marked all 4) and with `None`; that the session's loaded rows stay unread after `mark_read`; one `read_at` moment written under `UTC`, `America/New_York`, `Asia/Dhaka` and read back as UTC: `17:00`, `22:00`, `11:00`. **Not run:** anything over HTTP; delivery of `pg_notify` (needs a commit); the intended behaviour of the bug rules.

## Review
> All answered; nothing pending.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | The time a notification was read is wrong by the database's time-zone offset | bug — the true moment (BUG-1413) | Claude, delegated |
| Q1 | "Mark these as read" with an empty list marks **every** notification read | bug — an empty list marks none (BUG-1414) | Claude, delegated |
| Q2 | Notifications about a record that was later deleted are still listed | intended — a notification is history | Claude, delegated |

Decided by a house rule: notifications with one timestamp come back in no fixed order (BUG-1412, HR-6).

### House-rule violations — applied automatically

- **HR-6** `get_for_user` R4 — `ORDER BY created_at DESC` only. `created_at` is the database's `now()`, one value per transaction, and one discussion post notifies several people in one transaction, so ties are common. Verified: five rows of one stamp, paged one at a time, gave one row twice and one never. Intended (BUG-1210 precedent): `created_at` descending, then `id` descending, before `skip` / `limit`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1412 (pattern `tied-timestamp-no-tiebreak`). Rules: `get_for_user` R4.

Checked and **not** a new line here: **HR-4** — no soft-delete column; Q2 covers deleted subjects. **HR-5** — the filters are in the query before paging. **HR-7** — `GET /me/notifications/` requires `1 <= limit <= 200`, `skip >= 0`. **HR-8** — no `LIKE`. **HR-9** — no audit columns. **HR-10** — `mark_read` is one conditional `UPDATE`; two at once cannot double anything. **HR-16** — every read and the update filter on the row's `workspace_id` and recipient; `create` stores what the services give it (they pass only active members of the workspace).

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-03)

### P1. The read time depends on the database's time zone — 🐞 BUG-1413
**Background:** `read_at` is `timestamp with time zone` in the database; `mark_read` writes `utcnow()`, a UTC time with no zone, which Postgres reads in the session's `TimeZone`. BUG-1282 is the same mismatch and was ruled a bug. (`created_at` is the database's own `now()` into a `timestamptz`, which is correct.)
**What happens today:** Under `UTC` the moment is right; under `America/New_York` it is 5 hours late, under `Asia/Dhaka` 6 hours early, so a notification can show as read before it was created. (Verified.)
**Example:** Rahim opens his bell at 17:00 UTC on a server whose database runs in Dhaka time; `read_at` says 11:00 UTC, hours before the mention arrived.
**Rules affected:** `mark_read` R3
**Answer:** bug — per BUG-1282 precedent: `read_at` is the true moment of the call, whatever the session's `TimeZone` (written as aware UTC)
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): 🐞 BUG-1413 (pattern `aware-datetime-against-naive-column`). Rules: `mark_read` R3.

### New questions

### Q1. An empty list of ids marks every notification read — 🐞 BUG-1414
**Background:** `POST /me/notifications/read/` takes `{"ids": [...]}`; the schema says "null/omitted = mark all as read". The DAO checks `if ids:`, so an empty list takes the "all" path as well.
**What happens today:** `{"ids": []}` marks every unread notification of the user in the workspace read and answers their number. (Verified: 4 marked.)
**Example:** A client that sends the ids of the notifications on screen sends `[]` when a filter leaves none on screen, and all 30 unread notifications disappear from the badge.
**Rules affected:** `mark_read` R2
**Suggested answer:** `bug — only None (or an omitted field) means "all"; [] marks nothing and returns 0`, as the schema documents. Alternative: `intended` — then the schema comment should say so.
**Answer:** bug — `[]` marks nothing and returns 0
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): 🐞 BUG-1414 (pattern `empty-list-treated-as-missing`). Rules: `mark_read` R2 (tagged), R1 (untagged).

### Q2. Notifications about a deleted record are still listed — ✅ intended
**Background:** A notification names its subject by `entity_type` + `entity_id` (an order, a project component…), with no foreign key; the subject may later be deleted or soft-deleted. The list endpoint resolves a label for each and falls back to `"<type> #<id>"`.
**What happens today:** `get_for_user` does not look at the subject; such notifications are listed and counted as unread.
**Example:** Karim is mentioned on PO-12; the order is deleted before he looks. His bell still shows the mention, labelled `PO-12`.
**Rules affected:** `get_for_user` R1
**Suggested answer:** `intended` — a notification is a message that was sent, history like a log; hiding it would change the unread count behind the user's back. What opening it shows is the frontend's. Alternative: `bug — hide notifications whose subject is deleted` (needs a per-type lookup, as the label resolver does).
**Answer:** intended
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): standing decision "logs are history". Rules unchanged.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Notification service / endpoint** | `mark_read` does not refresh rows already loaded in the session; nothing reads them afterwards today (the service commits at once). `GET /me/notifications/` resolves one label per row (`resolve_notification_entity_label`): up to 200 extra reads per page. | `mark_read` R4 |

## Overview
`NotificationDAO` reads and writes `notifications`, the per-person inbox inside a workspace (mentions, approval requests…). `create` inserts one and announces it on the Postgres channel `user_notifications` for the live stream; `get_for_user` is the bell list with its counts; `mark_read` marks some or all read. Callers: `NotificationService` (`GET /me/notifications/`, `POST /me/notifications/read/`, mention fan-out from discussions) and `approval_notification_service` (order approval notices). It never commits.

**Callables:** 3 specified · 1 not specified
**Externals to mock:** `utcnow` — patch `app.dao.notification.utcnow` for `mark_read`.
**Integration-only behavior:** delivery of `pg_notify`: a notification is delivered to listeners only on commit, and unit tests never commit. A test can observe only that `create` sends `SELECT pg_notify(...)` with the right channel and payload (e.g. with a SQLAlchemy `before_cursor_execute` listener) and raises nothing.

**Model facts (table `notifications`):** `workspace_id` NOT NULL, FK CASCADE; `recipient_user_id` NOT NULL, FK `profiles` CASCADE; `actor_user_id` nullable, FK `profiles` SET NULL; `notification_type` VARCHAR(30) NOT NULL, Python default `'mention'`; `entity_type` VARCHAR(30), `entity_id` INTEGER, `source_type` VARCHAR(30), `source_id` INTEGER, all NOT NULL; `preview` TEXT nullable; `is_read` BOOLEAN NOT NULL default `false` (Python and database); `read_at` `timestamptz` nullable; `created_at` `timestamptz` NOT NULL, database default `now()`. Index `(workspace_id, recipient_user_id, is_read)`.

**Notes for the test designer:** `from app.dao.notification import notification_dao`. Parameters are **positional or keyword** here (not keyword-only). Rows made in one test share one `created_at`; for the order cases set `created_at` explicitly on some rows, and give three rows one value for the tie-break. **BUG-1412:** today's order on a tie rests on physical order → **non-strict** xfail. **BUG-1413:** read `read_at AT TIME ZONE 'UTC'` under `SET LOCAL TimeZone = 'Asia/Dhaka'` with `utcnow` patched to a fixed naive time → **strict** xfail. **BUG-1414:** deterministic → **strict** xfail. After `mark_read`, re-read with a query or `db.expire_all()`.

## Not specified
- `notification_dao` — module-level singleton, no logic.

---

## `NotificationDAO.get_for_user(db, workspace_id, user_id, unread_only=False, skip=0, limit=50)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `NotificationService.list_for_user` ← `GET /me/notifications/`, `limit` 1–200)

**Purpose:** One page of a person's notifications in a workspace, with the totals the bell shows.

**Returns:** a tuple `(items, total, unread_count)`.

**Rules:**
- **R1.** ✅ (Q2) `items` holds rows of that workspace whose recipient is that user; rows of another workspace or another recipient never appear. The subject (`entity_type` / `entity_id`) is not looked at.
- **R2.** With `unread_only=True` only rows with `is_read = False` are listed and counted in `total`; otherwise read and unread rows both are.
- **R3.** `total` counts every row the filter of R1–R2 keeps, before paging. `unread_count` always counts the user's unread rows in the workspace, whether `unread_only` is set or not.
- **R4.** [BUG-1412] (HR-6) Newest first: `created_at` descending, then `id` descending, before `skip` / `limit`. *(Today: `created_at` only; rows with one stamp come back in no fixed order and paging can repeat or skip a row.)*
- **R5.** At most `limit` rows after skipping `skip`; the default is 50. `limit=0` gives `[]` with the counts unchanged; an unknown workspace or user gives `([], 0, 0)`. A negative `skip` or `limit` raises `DataError` (pgcode `2201X` / `2201W`).
- **R6.** Each row comes with its `actor` loaded in the same statement (`None` when there is no actor).

**Errors:** negative paging → `sqlalchemy.exc.DataError`.

**Side effects:** none

---

## `NotificationDAO.create(db, workspace_id, recipient_user_id, actor_user_id, notification_type, entity_type, entity_id, source_type, source_id, preview=None)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `NotificationService.fan_out_mentions`, `approval_notification_service._notify_user`; both pass only active members of the workspace)

**Purpose:** Put one notification in a person's inbox and announce it.

**Returns:** the new `Notification`, flushed (has its `id`), not committed.

**Rules:**
- **R1.** One row is inserted with the given values, `is_read = False`, `read_at = None`, `created_at` the database's `now()`. `notification_type=None` is stored `'mention'` (the default applies); `actor_user_id=None` and `preview=None` are stored `NULL`.
- **R2.** After the flush, `SELECT pg_notify('user_notifications', <payload>)` is sent, where the payload is the JSON text `{"recipient_user_id": …, "workspace_id": …, "notification_id": <new id>}` in that key order. Nothing else is written.
- **R3.** Nothing is checked in Python: a recipient who is not a member of the workspace is stored; the subject is not looked up.
- **R4.** An unknown `workspace_id`, `recipient_user_id` or `actor_user_id` raises `IntegrityError` (pgcode `23503`) at the flush; a `notification_type`, `entity_type` or `source_type` over 30 characters raises `DataError` (pgcode `22001`). In both cases `pg_notify` is not sent.

**Errors:** as R4.

**Side effects:** one row inserted and flushed; one `pg_notify` sent inside the transaction (delivered on commit); not committed.

---

## `NotificationDAO.mark_read(db, workspace_id, user_id, ids=None)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `NotificationService.mark_read` ← `POST /me/notifications/read/`)

**Purpose:** Mark some or all of a person's unread notifications read.

**Returns:** `int`, the number of rows changed.

**Rules:**
- **R1.** With `ids=None` every unread row of that user in that workspace becomes `is_read = True` with `read_at` set; the count is returned. With a non-empty list only those of them are changed; ids of another user, another workspace, unknown ids and `0` are ignored and not counted.
- **R2.** [BUG-1414] (Q1) `ids=[]` changes nothing and returns `0`. *(Today: treated like `None`: every unread row is marked.)*
- **R3.** [BUG-1413] (P1) `read_at` is the moment of the call: read back as UTC it equals `utcnow()`, under any session `TimeZone`. *(Today: the naive UTC value is read in the session's zone: right under `UTC`, 5 hours late under `America/New_York`, 6 hours early under `Asia/Dhaka`.)*
- **R4.** Rows already read are left alone: their `read_at` is kept and they are not counted; a second call gives `0`. The update runs in the database without a flush of its own and without refreshing rows already loaded in the session: those still show `is_read = False` until refreshed.

**Errors:** none of its own.

**Side effects:** rows updated in the database; not committed.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 24–27 | workspace AND recipient | `get_for_user` R1 |
| 28–29 | `unread_only` true → `is_read IS false` | `get_for_user` R2 |
| 31–36 | `total` of the filter; `unread_count` independent | `get_for_user` R3 |
| 38–44 | actor joined; `created_at DESC` only (BUG-1412); offset / limit | `get_for_user` R4, R5, R6 |
| 60–72 | row from the arguments; `None` type → default; flush: FK, length | `create` R1, R3, R4 |
| 73–83 | JSON payload; `pg_notify` | `create` R2 |
| 93–97 | workspace AND recipient AND unread | `mark_read` R1, R4 |
| 98–99 | `if ids:` non-empty → `IN` / `None` and `[]` → all (BUG-1414) | `mark_read` R1, R2 |
| 100–101 | bulk `UPDATE`, `utcnow()` into `timestamptz` (BUG-1413); `synchronize_session=False`; count | `mark_read` R3, R4 |
| 104 | module singleton | Not specified |
