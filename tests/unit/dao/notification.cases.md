# Test cases — `app/dao/notification.py`

> **Spec:** `tests/unit/dao/notification.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). P1, Q1 and Q2 were decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. Additive, from `notification.verify.md` (case-missing Finding 1; recipe R-1): R-1 → NTF-GF-19 (the other recipient at the lower id; privacy). No existing card, Convention or ID changed; none retired.
> **Counts:** 39 cases · 34 expected-to-pass · 5 expected-to-fail (bugs) · 4 deferred

## Reviewer summary
- **Per callable:** `get_for_user` 19 (2 bug) · `create` 11 · `mark_read` 9 (3 bug).
- **Revision 1:** GF-19 asks as the later user (U3) with an earlier user's notification present, so a `<=` on the recipient fails (items, total and unread count).
- **Depth:** lighter target (skill step 1a). A per-person inbox; no stock, money or order state.
- **Expected-to-fail:** BUG-1412 2: GF-06 non-strict (the tie itself), GF-07 strict (the SQL recorder). BUG-1414 1 strict: MR-03 (`ids=[]`). BUG-1413 2 strict: MR-04 `Asia/Dhaka`, MR-05 `America/New_York`; MR-01 under `UTC` is the passing companion.
- **Commit spies:** CR-11, MR-09, one per writer.
- **Notable design choices:**
  - Every `mark_read` card that reads `read_at` back sets `SET LOCAL TIME ZONE` first; the moment is read with `AT TIME ZONE 'UTC'`.
  - Rows made in one test share one `created_at`, so order and paging cards give `created_at` explicitly. GF-05 and GF-10 are pass cards on today's `created_at DESC` (distinct stamps).
  - `pg_notify` cannot be delivered without a commit (integration-only); CR-03 records the statement and checks channel, payload keys, values and key order, and that it follows the `INSERT`. The error cards check that no `pg_notify` was sent.
  - MR-08 holds "no flush of its own": a pending notification of the same user stays pending and is not marked.
  - Filter before paging: one card per filter (recipient GF-08, `unread_only` GF-09).
  - No `Author:` lines (caller's instruction). Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `NTF` = `app/dao/notification.py`. `GF` get_for_user · `CR` create · `MR` mark_read.

**Actors and fixed values.**
- `dao` = the singleton `notification_dao` (`from app.dao.notification import notification_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword (the methods also accept positions; no card relies on that). `result` = what the When call returns; for `get_for_user` it is the tuple, `result[0]` the items, `result[1]` the total, `result[2]` the unread count.
- `Notification` = `app.models.notification.Notification`. `text` = `sqlalchemy.text`. `json` = the standard module. `datetime`, `timezone` = the `datetime` module's classes. `DataError`, `IntegrityError` = from `sqlalchemy.exc`. `patch` = `unittest.mock.patch`.
- MISSING = `999999999`. NOW = `datetime(2026, 3, 5, 17, 0, 0)` (naive). EARLY = `datetime(2026, 3, 1, 8, 0, 0, tzinfo=timezone.utc)`. T1, T2, T3 = `datetime(2026, 3, 1, 9, 0, 0, tzinfo=timezone.utc)`, `datetime(2026, 3, 2, 9, 0, 0, tzinfo=timezone.utc)`, `datetime(2026, 3, 3, 9, 0, 0, tzinfo=timezone.utc)`.

**Externals.** `app.dao.notification.utcnow`: every `mark_read` When runs inside `with patch("app.dao.notification.utcnow", return_value=NOW):`. The other methods read no clock.

**Given rows.** Rows are inserted directly (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush.
- Standing rows, no Given line: W1, W2 = two `workspaces` rows from `make_workspace(db)`; U1 (the recipient), U2 (the actor), U3 = three `profiles` rows from `make_profile(db)`. No `notifications` row and no `workspace_members` row exists unless the card's Given lists it.
- **note** = `Notification(workspace_id=W1.id, recipient_user_id=U1.id, actor_user_id=U2.id, notification_type="mention", entity_type="purchase_order", entity_id=1, source_type="discussion", source_id=1)`; `is_read`, `read_at`, `created_at` are not passed (so `False`, `None`, the database's now) unless the card lists them after the word "but". A read note is given as `is_read True`, `read_at EARLY`.
- A Given line written as code is a step to run exactly as written. `db.add(...)` without `db.flush()` leaves the row pending; an attribute set "(not flushed)" stays an unflushed edit.

**Named checks.**
- **idset(items)** = `{r.id for r in items}`. **ids(items)** = `[r.id for r in items]` (order is part of the check).
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its value before the call.
- **utc_read(X)** = `db.execute(text("SELECT read_at AT TIME ZONE 'UTC' FROM notifications WHERE id = :id"), {"id": X.id}).scalar()` — a naive UTC value.
- **nothing written** = the number of `notifications` rows stored equals its value before the call.
- `raises: <DB error>` = `with pytest.raises(<type>) as exc:` then `with db.begin_nested():` then the When; further `raises:` lines assert on `exc.value`, after the block.
- **rolled back** = `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.
- `pending:` / `session:` lines check `db.new`, `db.dirty`, `db.deleted` or an attribute of a loaded object after the call, before anything expires or refreshes the session.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`. The assertion of a non-strict card is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded, with their parameters (a `before_cursor_execute` listener), also when the When raises. `recorded` = every statement text, in order. `sql` = the recorded `SELECT` from `notifications` that contains `LIMIT` (the page); `order_part` = the text of `sql` after its first `ORDER BY` and before `LIMIT` (`""` when there is none); `selects` = every recorded `SELECT`; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. `notify` = the one recorded statement whose text contains `pg_notify`; `notify_args` = the values of its parameters (dict values in order, or the tuple); `payload` = the one value of `notify_args` that is a `str` starting with `"{"`.

**Race simulations.** None in this module.

## `NotificationDAO.get_for_user`

### NTF-GF-01 — the user's rows of the workspace, read and unread, with total and unread count
- **Rules:** `get_for_user` R1, R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = note, but `entity_id MISSING`.
2. B = note, but `is_read True`, `read_at EARLY`.
3. X = note, but `recipient_user_id U3.id`.
4. Y = note, but `workspace_id W2.id`.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `isinstance(result, tuple)`.
2. returns: `len(result) == 3`.
3. returns: `idset(result[0]) == {A.id, B.id}`.
4. returns: `result[1] == 2`.
5. returns: `result[2] == 1`.

### NTF-GF-02 — unread_only lists and counts only unread rows
- **Rules:** `get_for_user` R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = note.
2. B = note, but `is_read True`, `read_at EARLY`.
3. C = note.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, user_id=U1.id, unread_only=True)`.

**Then**
1. returns: `idset(result[0]) == {A.id, C.id}`.
2. returns: `result[1] == 2`.
3. returns: `result[2] == 2`.

### NTF-GF-03 — total and unread count are taken before paging
- **Rules:** `get_for_user` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = note, but `created_at T3`.
2. B = note, but `created_at T2`.
3. C = note, but `created_at T1`.
4. D = note, but `is_read True`, `read_at EARLY`, `created_at T1`.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, user_id=U1.id, limit=1)`.

**Then**
1. returns: `ids(result[0]) == [A.id]`.
2. returns: `result[1] == 4`.
3. returns: `result[2] == 3`.

### NTF-GF-04 — the unread count with unread_only=False still counts only unread rows
- **Rules:** `get_for_user` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = note, but `is_read True`, `read_at EARLY`.
2. B = note, but `is_read True`, `read_at EARLY`.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, user_id=U1.id, unread_only=False)`.

**Then**
1. returns: `idset(result[0]) == {A.id, B.id}`.
2. returns: `result[1] == 2`.
3. returns: `result[2] == 0`.

### NTF-GF-05 — newest first by created_at, whatever the ids
- **Rules:** `get_for_user` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = note, but `created_at T2`.
2. B = note, but `created_at T3`.
3. C = note, but `created_at T1`.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `ids(result[0]) == [B.id, A.id, C.id]`.

### NTF-GF-06 — on a tie the higher id comes first, also after the lowest id was updated
- **Rules:** `get_for_user` R4 [BUG-1412]
- **Kind:** bug
- **Expect:** xfail BUG-1412 (non-strict)
- **Fails today on:** Then 2 (no order among tied rows; physical order puts the updated row last)

**Given**
1. A = note, but `created_at T2`.
2. B = note, but `created_at T2`.
3. C = note, but `created_at T2`.
4. `A.preview = "edited"`, then `db.flush()`.
5. `db.expire_all()`

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `len(result[0]) == 3`.
2. returns: `ids(result[0]) == [C.id, B.id, A.id]`.

### NTF-GF-07 — the query orders by created_at, then id, both descending
- **Rules:** `get_for_user` R4 [BUG-1412]
- **Kind:** bug
- **Expect:** xfail BUG-1412
- **Fails today on:** Then 4 (the query orders by `created_at` alone)

**Given**
1. A = note.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `ids(result[0]) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"created_at" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("created_at") < order_part.index(".id")`.
6. statement: `order_part.upper().count("DESC") == 2`.
7. statement: `order_part.count(",") == 1`.

### NTF-GF-08 — the recipient filter is applied before the page
- **Rules:** `get_for_user` R1, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = note, but `recipient_user_id U3.id`, `created_at T3`.
2. A = note, but `created_at T2`.
3. B = note, but `created_at T1`.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, user_id=U1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result[0]) == [B.id]`.
2. returns: `result[1] == 2`.

### NTF-GF-09 — unread_only is applied before the page
- **Rules:** `get_for_user` R2, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = note, but `is_read True`, `read_at EARLY`, `created_at T3`.
2. A = note, but `created_at T2`.
3. B = note, but `created_at T1`.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, user_id=U1.id, unread_only=True, skip=1, limit=1)`.

**Then**
1. returns: `ids(result[0]) == [B.id]`.
2. returns: `result[1] == 2`.

### NTF-GF-10 — with the default limit 51 rows give the newest 50
- **Rules:** `get_for_user` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 51 notes E1 … E51, built with `add_all`: Ek = note, but `created_at datetime(2026, 3, 1, 9, 0, k, tzinfo=timezone.utc)`.
2. `newest` = the ids of E51, E50, … E1, in that order.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `len(result[0]) == 50`.
2. returns: `ids(result[0]) == newest[:50]`.
3. returns: `result[1] == 51`.

### NTF-GF-11 — limit=1000 gives all 51
- **Rules:** `get_for_user` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 51 notes E1 … E51, built with `add_all`: Ek = note, but `created_at datetime(2026, 3, 1, 9, 0, k, tzinfo=timezone.utc)`.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, user_id=U1.id, limit=1000)`.

**Then**
1. returns: `len(result[0]) == 51`.
2. returns: `result[1] == 51`.

### NTF-GF-12 — limit=0 gives no rows and the counts unchanged
- **Rules:** `get_for_user` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = note.
2. B = note.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, user_id=U1.id, limit=0)`.

**Then**
1. returns: `result[0] == []`.
2. returns: `result[1] == 2`.
3. returns: `result[2] == 2`.

### NTF-GF-13 — an unknown workspace gives ([], 0, 0)
- **Rules:** `get_for_user` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = note.

**When**
- `result = dao.get_for_user(db, workspace_id=MISSING, user_id=U1.id)`.

**Then**
1. returns: `result == ([], 0, 0)`.

### NTF-GF-14 — user id 0 gives ([], 0, 0)
- **Rules:** `get_for_user` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = note.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, user_id=0)`.

**Then**
1. returns: `result == ([], 0, 0)`.

### NTF-GF-15 — a negative skip raises DataError 2201X
- **Rules:** `get_for_user` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = note.

**When**
- `dao.get_for_user(db, workspace_id=W1.id, user_id=U1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. nothing written: nothing written.

### NTF-GF-16 — a negative limit raises DataError 2201W
- **Rules:** `get_for_user` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = note.

**When**
- `dao.get_for_user(db, workspace_id=W1.id, user_id=U1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. nothing written: nothing written.

### NTF-GF-17 — each row comes with its actor, loaded in the page statement
- **Rules:** `get_for_user` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = note, but `created_at T2`.
2. B = note, but `actor_user_id None`, `created_at T1`.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `ids(result[0]) == [A.id, B.id]`.
2. statement: `"profiles" in sql`.
3. statement: `"JOIN" in sql.upper()`.
4. returns: `result[0][0].actor.id == U2.id`.
5. returns: `result[0][1].actor is None`.

### NTF-GF-18 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_for_user` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = note.
2. B = note, but `recipient_user_id U3.id`.
3. `P = Notification(workspace_id=W1.id, recipient_user_id=U1.id, actor_user_id=U2.id, notification_type="mention", entity_type="purchase_order", entity_id=2, source_type="discussion", source_id=2)`
4. `db.add(P)` (not flushed).
5. `B.preview = "edited"` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `ids(result[0]) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. session: `B in db.dirty`.
6. session: `len(db.dirty) == 1`.
7. session: `not db.deleted`.
8. statement: `written == []`.

### NTF-GF-19 — another recipient with a lower id: their rows are not shown or counted
- **Rules:** `get_for_user` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = note.
2. A = note, but `recipient_user_id U3.id`.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, user_id=U3.id)`.

**Then**
1. returns: `idset(result[0]) == {A.id}`.
2. returns: `result[1] == 1`.
3. returns: `result[2] == 1`.

## `NotificationDAO.create`

### NTF-CR-01 — one unread row with the given values, for a recipient of no membership
- **Rules:** `create` R1, R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. U1 has no `workspace_members` row; no purchase order with id MISSING exists.

**When**
- `result = dao.create(db, workspace_id=W1.id, recipient_user_id=U1.id, actor_user_id=U2.id, notification_type="approval_request", entity_type="purchase_order", entity_id=MISSING, source_type="discussion", source_id=7, preview="Please approve")`.

**Then**
1. returns: `isinstance(result, Notification)`.
2. returns: `result.id is not None`.
3. re-read result: `workspace_id == W1.id`, `recipient_user_id == U1.id`, `actor_user_id == U2.id`, `notification_type == "approval_request"`.
4. re-read result: `entity_type == "purchase_order"`, `entity_id == MISSING`, `source_type == "discussion"`, `source_id == 7`, `preview == "Please approve"`.
5. re-read result: `is_read is False`, `read_at is None`.
6. re-read result: `created_at is not None`, `created_at.tzinfo is not None`.

### NTF-CR-02 — no type gives 'mention'; no actor and no preview are stored NULL
- **Rules:** `create` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no notifications.

**When**
- `result = dao.create(db, workspace_id=W1.id, recipient_user_id=U1.id, actor_user_id=None, notification_type=None, entity_type="purchase_order", entity_id=1, source_type="discussion", source_id=1)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `notification_type == "mention"`.
3. re-read result: `actor_user_id is None`, `preview is None`.

### NTF-CR-03 — after the insert, pg_notify is sent on 'user_notifications' with the payload in key order
- **Rules:** `create` R2, Side effects
- **Kind:** external
- **Expect:** pass

**Given**
1. W1 has no notifications.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.create(db, workspace_id=W1.id, recipient_user_id=U1.id, actor_user_id=U2.id, notification_type="mention", entity_type="purchase_order", entity_id=1, source_type="discussion", source_id=1)`.

**Then**
1. returns: `result.id is not None`.
2. statement: `len([s for s in recorded if "pg_notify" in s]) == 1`.
3. statement: `recorded.index(notify) > recorded.index(written[0])`.
4. statement: `"user_notifications" in notify or "user_notifications" in notify_args`.
5. statement: `json.loads(payload) == {"recipient_user_id": U1.id, "workspace_id": W1.id, "notification_id": result.id}`.
6. statement: `list(json.loads(payload).keys()) == ["recipient_user_id", "workspace_id", "notification_id"]`.
7. statement: `len(written) == 1`.
8. statement: `"INSERT INTO notifications" in written[0]`.

### NTF-CR-04 — no membership or subject is looked up
- **Rules:** `create` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no notifications.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.create(db, workspace_id=W1.id, recipient_user_id=U3.id, actor_user_id=U2.id, notification_type="mention", entity_type="purchase_order", entity_id=MISSING, source_type="discussion", source_id=1)`.

**Then**
1. returns: `result.id is not None`.
2. statement: `not any("workspace_members" in s for s in selects)`.
3. statement: `not any("purchase_orders" in s for s in selects)`.

### NTF-CR-05 — an unknown workspace raises IntegrityError 23503; no row, no pg_notify
- **Rules:** `create` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A recorder for the SQL statements the session sends during the When.

**When**
- `dao.create(db, workspace_id=MISSING, recipient_user_id=U1.id, actor_user_id=U2.id, notification_type="mention", entity_type="purchase_order", entity_id=1, source_type="discussion", source_id=1)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. statement: `not any("pg_notify" in s for s in recorded)`.
4. nothing written: nothing written.

### NTF-CR-06 — an unknown recipient raises IntegrityError 23503; no row, no pg_notify
- **Rules:** `create` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A recorder for the SQL statements the session sends during the When.

**When**
- `dao.create(db, workspace_id=W1.id, recipient_user_id=MISSING, actor_user_id=U2.id, notification_type="mention", entity_type="purchase_order", entity_id=1, source_type="discussion", source_id=1)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. statement: `not any("pg_notify" in s for s in recorded)`.
4. nothing written: nothing written.

### NTF-CR-07 — an unknown actor raises IntegrityError 23503; no row, no pg_notify
- **Rules:** `create` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A recorder for the SQL statements the session sends during the When.

**When**
- `dao.create(db, workspace_id=W1.id, recipient_user_id=U1.id, actor_user_id=MISSING, notification_type="mention", entity_type="purchase_order", entity_id=1, source_type="discussion", source_id=1)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. statement: `not any("pg_notify" in s for s in recorded)`.
4. nothing written: nothing written.

### NTF-CR-08 — a type of 31 characters raises DataError 22001; no row, no pg_notify
- **Rules:** `create` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A recorder for the SQL statements the session sends during the When.

**When**
- `dao.create(db, workspace_id=W1.id, recipient_user_id=U1.id, actor_user_id=U2.id, notification_type="t" * 31, entity_type="purchase_order", entity_id=1, source_type="discussion", source_id=1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "22001"`.
3. statement: `not any("pg_notify" in s for s in recorded)`.
4. nothing written: nothing written.

### NTF-CR-09 — types of exactly 30 characters are stored whole
- **Rules:** `create` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no notifications.

**When**
- `result = dao.create(db, workspace_id=W1.id, recipient_user_id=U1.id, actor_user_id=U2.id, notification_type="t" * 30, entity_type="e" * 30, entity_id=1, source_type="s" * 30, source_id=1)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `notification_type == "t" * 30`, `entity_type == "e" * 30`, `source_type == "s" * 30`.

### NTF-CR-10 — an entity type of 31 characters raises DataError 22001
- **Rules:** `create` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no notifications.

**When**
- `dao.create(db, workspace_id=W1.id, recipient_user_id=U1.id, actor_user_id=U2.id, notification_type="mention", entity_type="e" * 31, entity_id=1, source_type="discussion", source_id=1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "22001"`.
3. nothing written: nothing written.

### NTF-CR-11 — the row is flushed, not committed
- **Rules:** `create` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no notifications.
2. Savepoint and commit spy per **rolled back**.

**When**
- `result = dao.create(db, workspace_id=W1.id, recipient_user_id=U1.id, actor_user_id=U2.id, notification_type="mention", entity_type="purchase_order", entity_id=1, source_type="discussion", source_id=1)`.

**Then**
1. returns: `result.id is not None`.
2. count: inside the savepoint, `notifications` has exactly 1 row with `workspace_id == W1.id` (raw `SELECT count(*)`).
3. count: after the savepoint rollback, `notifications` has exactly 0 rows with `workspace_id == W1.id`.
4. mock called: the `db.commit` spy was never called.

## `NotificationDAO.mark_read`

### NTF-MR-01 — ids=None marks every unread row of the user in the workspace, read_at now (UTC session)
- **Rules:** `mark_read` R1, R3, R4, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`
2. A = note.
3. B = note.
4. C = note, but `is_read True`, `read_at EARLY`.
5. X = note, but `recipient_user_id U3.id`.
6. Y = note, but `workspace_id W2.id`.

**When**
- `result = dao.mark_read(db, workspace_id=W1.id, user_id=U1.id, ids=None)`.

**Then**
1. returns: `result == 2`.
2. re-read A: `is_read is True`, `utc_read(A) == NOW`.
3. re-read B: `is_read is True`, `utc_read(B) == NOW`.
4. re-read C: `utc_read(C) == datetime(2026, 3, 1, 8, 0, 0)`.
5. unchanged: unchanged(X).
6. unchanged: unchanged(Y).

### NTF-MR-02 — a list marks only the user's unread rows among them; others are ignored
- **Rules:** `mark_read` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = note.
2. B = note.
3. C = note, but `is_read True`, `read_at EARLY`.
4. X = note, but `recipient_user_id U3.id`.
5. Y = note, but `workspace_id W2.id`.

**When**
- `result = dao.mark_read(db, workspace_id=W1.id, user_id=U1.id, ids=[A.id, C.id, X.id, Y.id, MISSING, 0])`.

**Then**
1. returns: `result == 1`.
2. re-read A: `is_read is True`, `read_at is not None`.
3. re-read B: `is_read is False`, `read_at is None`.
4. unchanged: unchanged(X).
5. unchanged: unchanged(Y).

### NTF-MR-03 — an empty list marks nothing and returns 0
- **Rules:** `mark_read` R2 [BUG-1414]
- **Kind:** bug
- **Expect:** xfail BUG-1414
- **Fails today on:** Then 1 (`[]` is treated like `None` today: 2 is returned)

**Given**
1. A = note.
2. B = note.

**When**
- `result = dao.mark_read(db, workspace_id=W1.id, user_id=U1.id, ids=[])`.

**Then**
1. returns: `result == 0`.
2. re-read A: `is_read is False`.
3. re-read B: `is_read is False`.

### NTF-MR-04 — under Asia/Dhaka, read_at read as UTC is still the moment of the call
- **Rules:** `mark_read` R3 [BUG-1413]
- **Kind:** bug
- **Expect:** xfail BUG-1413
- **Fails today on:** Then 2 (the naive UTC value is read as Dhaka time: 6 hours early)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`
2. A = note.

**When**
- `result = dao.mark_read(db, workspace_id=W1.id, user_id=U1.id, ids=None)`.

**Then**
1. returns: `result == 1`.
2. re-read A: `utc_read(A) == NOW`.

### NTF-MR-05 — under America/New_York, read_at read as UTC is still the moment of the call
- **Rules:** `mark_read` R3 [BUG-1413]
- **Kind:** bug
- **Expect:** xfail BUG-1413
- **Fails today on:** Then 2 (the naive UTC value is read as New York time: 5 hours late)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))`
2. A = note.

**When**
- `result = dao.mark_read(db, workspace_id=W1.id, user_id=U1.id, ids=None)`.

**Then**
1. returns: `result == 1`.
2. re-read A: `utc_read(A) == NOW`.

### NTF-MR-06 — rows already read keep their read_at and are not counted
- **Rules:** `mark_read` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = note, but `is_read True`, `read_at EARLY`.

**When**
- `result = dao.mark_read(db, workspace_id=W1.id, user_id=U1.id, ids=[A.id])`.

**Then**
1. returns: `result == 0`.
2. re-read A: `read_at == EARLY`.

### NTF-MR-07 — rows loaded in the session still show unread until refreshed
- **Rules:** `mark_read` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = note.

**When**
- `result = dao.mark_read(db, workspace_id=W1.id, user_id=U1.id, ids=None)`.

**Then**
1. returns: `result == 1`.
2. session: `A.is_read is False` (read without refreshing).
3. re-read A: `is_read is True`.

### NTF-MR-08 — no flush of its own: a pending notification stays pending and is not marked
- **Rules:** `mark_read` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = note.
2. B = note, but `recipient_user_id U3.id`.
3. `P = Notification(workspace_id=W1.id, recipient_user_id=U1.id, actor_user_id=U2.id, notification_type="mention", entity_type="purchase_order", entity_id=2, source_type="discussion", source_id=2)`
4. `db.add(P)` (not flushed).
5. `B.preview = "edited"` (not flushed).

**When**
- `result = dao.mark_read(db, workspace_id=W1.id, user_id=U1.id, ids=None)`.

**Then**
1. returns: `result == 1`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.

### NTF-MR-09 — the update is not committed
- **Rules:** `mark_read` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = note.
2. Savepoint and commit spy per **rolled back**.

**When**
- `result = dao.mark_read(db, workspace_id=W1.id, user_id=U1.id, ids=None)`.

**Then**
1. returns: `result == 1`.
2. re-read A: inside the savepoint, `db.execute(text("SELECT is_read FROM notifications WHERE id = :id"), {"id": A.id}).scalar() is True`.
3. re-read A: after the savepoint rollback, the same `SELECT` gives `False`.
4. mock called: the `db.commit` spy was never called.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Delivery of `pg_notify` to listeners (needs a commit) | integration tests | Integration-only per the spec; CR-03 holds the statement. |
| FU-1 — `mark_read` does not refresh loaded rows; one label lookup per row on the list page | `NotificationService`, `GET /me/notifications/` | Here MR-07 holds the DAO side. |
| `GET /me/notifications/` requires `1 <= limit <= 200`, `skip >= 0` (HR-7) | the endpoint | Already in place; DAO negatives are GF-15, GF-16. |
| Callers pass only active members (R3) | `NotificationService.fan_out_mentions`, `approval_notification_service._notify_user` | Membership check is the services'. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `create` R2 | Whether the channel `user_notifications` is a literal in the SQL or a bound parameter, and the payload's exact text (separators) are not given. | CR-03 accepts the channel in either place and compares the payload parsed (`json.loads`) plus its key order, not the raw text. |
| 2 | `create` R1 | `created_at` is an aware value read back; the spec does not say whether the test may rely on the returned object holding it before a refresh. | CR-01 checks it after a re-read only. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_for_user` | Returns | NTF-GF-01 |
| `get_for_user` | R1 | NTF-GF-01, NTF-GF-08, NTF-GF-19 |
| `get_for_user` | R2 | NTF-GF-02, NTF-GF-09 |
| `get_for_user` | R3 | NTF-GF-01, NTF-GF-02, NTF-GF-03, NTF-GF-04 |
| `get_for_user` | R4 | NTF-GF-05 |
| `get_for_user` | R4 [BUG-1412] | NTF-GF-06, NTF-GF-07 |
| `get_for_user` | R5 | NTF-GF-08, NTF-GF-09, NTF-GF-10, NTF-GF-11, NTF-GF-12, NTF-GF-13, NTF-GF-14, NTF-GF-15, NTF-GF-16 |
| `get_for_user` | R6 | NTF-GF-17 |
| `get_for_user` | Errors | NTF-GF-15, NTF-GF-16 |
| `get_for_user` | Side effects | NTF-GF-18 |
| `create` | Returns | NTF-CR-01 |
| `create` | R1 | NTF-CR-01, NTF-CR-02 |
| `create` | R2 | NTF-CR-03 |
| `create` | R3 | NTF-CR-01, NTF-CR-04 |
| `create` | R4 | NTF-CR-05, NTF-CR-06, NTF-CR-07, NTF-CR-08, NTF-CR-09, NTF-CR-10 |
| `create` | Errors | NTF-CR-05, NTF-CR-06, NTF-CR-07, NTF-CR-08, NTF-CR-10 |
| `create` | Side effects | NTF-CR-03, NTF-CR-11 |
| `mark_read` | Returns | NTF-MR-01 |
| `mark_read` | R1 | NTF-MR-01, NTF-MR-02 |
| `mark_read` | R2 [BUG-1414] | NTF-MR-03 |
| `mark_read` | R3 | NTF-MR-01 |
| `mark_read` | R3 [BUG-1413] | NTF-MR-04, NTF-MR-05 |
| `mark_read` | R4 | NTF-MR-01, NTF-MR-06, NTF-MR-07, NTF-MR-08 |
| `mark_read` | Side effects | NTF-MR-09 |
