# Test cases — `app/dao/work_order_assignee.py`

> **Spec:** `tests/unit/dao/work_order_assignee.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). P1, P2 were decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. Additive, from `work_order_assignee.verify.md` (case-missing Finding 1; recipe R-1): R-1 → WOA-GU-10. No other card changed; no ID retired. `work_order_completer.cases.md` needs no twin: its single-order read is dead code.
> **Counts:** 35 cases · 35 expected-to-pass · 0 expected-to-fail (bugs) · 5 deferred

## Reviewer summary
- **Per callable:** `get_user_ids_by_orders` 11 · `get_user_ids_by_order` 10 · `replace_for_order` 14.
- **Depth:** lighter target (skill step 1a). The planned workers of a work order: a delete-then-insert of plain link rows and two reads. The rows hold no order state (status, approvals), no stock, no money.
- **Expected-to-fail:** none; the spec has no bug.
- **Commit spies:** `replace_for_order` 1 (WOA-RP-14).
- **Notable design choices:**
  - The spec asks to parametrize every case over the assignee and completer DAOs. Each module has its own cases file, so this file tests `work_order_assignee_dao` and `work_order_completer.cases.md` holds the same cards for `work_order_completer_dao` (without the single-order read, dead there).
  - Order by row id: the rows are inserted for U2 before U1, so row-id order and user-id order differ; WOA-GO-05 and GU-05 update the first row under a sequential scan, so a missing `ORDER BY` shows.
  - WOA-RP-08 and RP-09 run inside the savepoint of the `raises:` wrap and then check that the delete was undone as well.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `WOA` = `app/dao/work_order_assignee.py`. `GO` get_user_ids_by_orders · `GU` get_user_ids_by_order · `RP` replace_for_order.

**Actors and fixed values.**
- `dao` = the singleton `work_order_assignee_dao` (`from app.dao.work_order_assignee import work_order_assignee_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `Row` = `app.models.work_order_assignee.WorkOrderAssignee`. `WorkOrder` = `app.models.work_order.WorkOrder`. `WorkOrderType` = `app.models.work_order_type.WorkOrderType`. `Factory` = `app.models.factory.Factory`. `IntegrityError` = `sqlalchemy.exc.IntegrityError`. `text` = `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.

**Externals.** None. Nothing is mocked.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line: W1, W2 = two `workspaces` rows (`make_workspace`); U1, U2, U3, U4 = four `profiles` rows (`make_profile`), made in that order; F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`, F9 = the same, but `workspace_id W2.id`, `name "Factory Nine"`, `abbreviation "F9"`; WT1 = `WorkOrderType(workspace_id=W1.id, name="Repair")`, WT9 = the same, but `workspace_id W2.id`; WO1 = `WorkOrder(workspace_id=W1.id, work_order_number="WO-1", title="Fix press", factory_id=F1.id, work_order_type_id=WT1.id)`; WO2 = the same, but `work_order_number "WO-2"`; WOD = the same, but `work_order_number "WO-3"`, `is_deleted True`; WO9 = the same, but `workspace_id W2.id`, `work_order_number "WO-9"`, `factory_id F9.id`, `work_order_type_id WT9.id`.
- **row** = `Row(workspace_id=W1.id, work_order_id=WO1.id, user_id=U)`; the card always gives `user_id`; after "but" it lists every other column that differs. No row exists unless the Given lists it.
- **bumpA(X)** = `db.execute(text("UPDATE work_order_assignees SET user_id = user_id WHERE id = :i"), {"i": X.id})`, then `db.expire_all()`.
- **seqscan** = run, in this order, `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.

**Named checks.**
- **users_of(wo, ws)** = `list(db.scalars(text("SELECT user_id FROM work_order_assignees WHERE work_order_id = :w AND workspace_id = :s ORDER BY id"), {"w": wo, "s": ws}))`.
- **row_ids_of(wo)** = `set(db.scalars(text("SELECT id FROM work_order_assignees WHERE work_order_id = :w"), {"w": wo}))`.
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the number of `work_order_assignees` rows stored (all workspaces) equals its value before the call.
- `pending:` lines check the session after the call, before anything expires it. A card lists them ahead of its `nothing written:` and `unchanged:` lines.
- `raises: IntegrityError` = wrap the call: `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards (the savepoint is rolled back). Further `raises:` lines are assertions on `exc.value`, one `assert` per line.
- **rolled back** = `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); "inside the savepoint" checks first; then `sp.rollback()` and the "after the savepoint rollback" checks.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `selects` = every `SELECT` recorded; `sql` = the text of the one `SELECT` from `work_order_assignees`; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `WorkOrderAssigneeDAO.get_user_ids_by_orders`

### WOA-GO-01 — a map from each order to its people, in row order
- **Rules:** `get_user_ids_by_orders` R2, R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = row, `user_id U2.id`.
2. B = row, `user_id U1.id`.
3. C = row, `user_id U3.id`, but `work_order_id WO2.id`.

**When**
- `result = dao.get_user_ids_by_orders(db, work_order_ids=[WO1.id, WO2.id], workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, dict)`.
2. returns: `result == {WO1.id: [U2.id, U1.id], WO2.id: [U3.id]}`.

### WOA-GO-02 — an empty list returns {} with no query
- **Rules:** `get_user_ids_by_orders` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_user_ids_by_orders(db, work_order_ids=[], workspace_id=W1.id)`.

**Then**
1. returns: `result == {}`.
2. statement: `selects == []`.

### WOA-GO-03 — an order with no rows and an unknown id map to []
- **Rules:** `get_user_ids_by_orders` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.

**When**
- `result = dao.get_user_ids_by_orders(db, work_order_ids=[WO2.id, MISSING], workspace_id=W1.id)`.

**Then**
1. returns: `result == {WO2.id: [], MISSING: []}`.

### WOA-GO-04 — an id given twice is one key; keys come in the order first given
- **Rules:** `get_user_ids_by_orders` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.

**When**
- `result = dao.get_user_ids_by_orders(db, work_order_ids=[WO2.id, WO1.id, WO2.id], workspace_id=W1.id)`.

**Then**
1. returns: `list(result.keys()) == [WO2.id, WO1.id]`.
2. returns: `result[WO1.id] == [U1.id]`.
3. returns: `result[WO2.id] == []`.

### WOA-GO-05 — row-id order holds when the first row was updated
- **Rules:** `get_user_ids_by_orders` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = row, `user_id U2.id`.
2. B = row, `user_id U1.id`.
3. C = row, `user_id U3.id`.
4. seqscan.
5. bumpA(A).

**When**
- `result = dao.get_user_ids_by_orders(db, work_order_ids=[WO1.id], workspace_id=W1.id)`.

**Then**
1. returns: `result == {WO1.id: [U2.id, U1.id, U3.id]}`.

### WOA-GO-06 — asked for W2, an order of W1 maps to []
- **Rules:** `get_user_ids_by_orders` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.

**When**
- `result = dao.get_user_ids_by_orders(db, work_order_ids=[WO1.id], workspace_id=W2.id)`.

**Then**
1. returns: `result == {WO1.id: []}`.

### WOA-GO-07 — a W2 row on a W1 order is not read for W1
- **Rules:** `get_user_ids_by_orders` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.
2. Z = row, `user_id U3.id`, but `workspace_id W2.id`.

**When**
- `result = dao.get_user_ids_by_orders(db, work_order_ids=[WO1.id], workspace_id=W1.id)`.

**Then**
1. returns: `result == {WO1.id: [U1.id]}`.

### WOA-GO-08 — a W2 row on a W1 order is read for W2
- **Rules:** `get_user_ids_by_orders` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.
2. Z = row, `user_id U3.id`, but `workspace_id W2.id`.

**When**
- `result = dao.get_user_ids_by_orders(db, work_order_ids=[WO1.id], workspace_id=W2.id)`.

**Then**
1. returns: `result == {WO1.id: [U3.id]}`.

### WOA-GO-09 — the people of a soft-deleted order are returned
- **Rules:** `get_user_ids_by_orders` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`, but `work_order_id WOD.id`.

**When**
- `result = dao.get_user_ids_by_orders(db, work_order_ids=[WOD.id], workspace_id=W1.id)`.

**Then**
1. returns: `result == {WOD.id: [U1.id]}`.

### WOA-GO-10 — one statement, whatever the number of ids
- **Rules:** `get_user_ids_by_orders` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.
2. B = row, `user_id U2.id`, but `work_order_id WO2.id`.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_user_ids_by_orders(db, work_order_ids=[WO1.id, WO2.id, WOD.id], workspace_id=W1.id)`.

**Then**
1. returns: `result == {WO1.id: [U1.id], WO2.id: [U2.id], WOD.id: []}`.
2. statement: `len(selects) == 1`.
3. statement: `"ORDER BY" in sql`.

### WOA-GO-11 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_user_ids_by_orders` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.
2. B = row, `user_id U2.id`, but `work_order_id WO2.id`.
3. `B.user_id = U3.id` (not flushed).
4. `P = Row(workspace_id=W1.id, work_order_id=WO1.id, user_id=U4.id)`
5. `db.add(P)` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_user_ids_by_orders(db, work_order_ids=[WO1.id], workspace_id=W1.id)`.

**Then**
1. returns: `result == {WO1.id: [U1.id]}`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `"FOR UPDATE" not in sql.upper()`.
8. nothing written: nothing written.

## `WorkOrderAssigneeDAO.get_user_ids_by_order`

### WOA-GU-01 — the order's people, in row order
- **Rules:** `get_user_ids_by_order` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = row, `user_id U2.id`.
2. B = row, `user_id U1.id`.

**When**
- `result = dao.get_user_ids_by_order(db, work_order_id=WO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `result == [U2.id, U1.id]`.

### WOA-GU-02 — an order with no rows returns []
- **Rules:** `get_user_ids_by_order` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.

**When**
- `result = dao.get_user_ids_by_order(db, work_order_id=WO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### WOA-GU-03 — an unknown order returns []
- **Rules:** `get_user_ids_by_order` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.

**When**
- `result = dao.get_user_ids_by_order(db, work_order_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### WOA-GU-04 — order id 0 returns []
- **Rules:** `get_user_ids_by_order` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.

**When**
- `result = dao.get_user_ids_by_order(db, work_order_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### WOA-GU-05 — row-id order holds when the first row was updated
- **Rules:** `get_user_ids_by_order` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = row, `user_id U2.id`.
2. B = row, `user_id U1.id`.
3. C = row, `user_id U3.id`.
4. seqscan.
5. bumpA(A).

**When**
- `result = dao.get_user_ids_by_order(db, work_order_id=WO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == [U2.id, U1.id, U3.id]`.

### WOA-GU-06 — an earlier row of another order is not returned
- **Rules:** `get_user_ids_by_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. C = row, `user_id U3.id`, but `work_order_id WO2.id`.
2. A = row, `user_id U1.id`.

**When**
- `result = dao.get_user_ids_by_order(db, work_order_id=WO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == [U1.id]`.

### WOA-GU-07 — a W2 row on the order is not returned for W1
- **Rules:** `get_user_ids_by_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.
2. Z = row, `user_id U3.id`, but `workspace_id W2.id`.

**When**
- `result = dao.get_user_ids_by_order(db, work_order_id=WO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == [U1.id]`.

### WOA-GU-08 — the people of a soft-deleted order are returned
- **Rules:** `get_user_ids_by_order` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`, but `work_order_id WOD.id`.

**When**
- `result = dao.get_user_ids_by_order(db, work_order_id=WOD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == [U1.id]`.

### WOA-GU-09 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_user_ids_by_order` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.
2. B = row, `user_id U2.id`, but `work_order_id WO2.id`.
3. `B.user_id = U3.id` (not flushed).
4. `P = Row(workspace_id=W1.id, work_order_id=WO1.id, user_id=U4.id)`
5. `db.add(P)` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_user_ids_by_order(db, work_order_id=WO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == [U1.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `"FOR UPDATE" not in sql.upper()`.
8. nothing written: nothing written.

### WOA-GU-10 — asked for W2, only the W2 row is read, though the W1 row is earlier
- **Rules:** `get_user_ids_by_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.
2. B = row, `user_id U2.id`, but `workspace_id W2.id`.

**When**
- `result = dao.get_user_ids_by_order(db, work_order_id=WO1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == [U2.id]`.

## `WorkOrderAssigneeDAO.replace_for_order`

### WOA-RP-01 — the people become the distinct ids given, in first-seen order, on new rows
- **Rules:** `replace_for_order` R1, Returns, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.
2. B = row, `user_id U2.id`.

**When**
- `result = dao.replace_for_order(db, work_order_id=WO1.id, workspace_id=W1.id, user_ids=[U3.id, U1.id, U3.id, U2.id])`.

**Then**
1. returns: `result is None`.
2. re-read WO1's rows: `users_of(WO1.id, W1.id) == [U3.id, U1.id, U2.id]`.
3. re-read WO1's rows: `row_ids_of(WO1.id).isdisjoint({A.id, B.id})`.

### WOA-RP-02 — saving the same list again keeps the people and their order, on new rows
- **Rules:** `replace_for_order` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.
2. B = row, `user_id U2.id`.

**When**
- `result = dao.replace_for_order(db, work_order_id=WO1.id, workspace_id=W1.id, user_ids=[U1.id, U2.id])`.

**Then**
1. returns: `result is None`.
2. re-read WO1's rows: `users_of(WO1.id, W1.id) == [U1.id, U2.id]`.
3. re-read WO1's rows: `row_ids_of(WO1.id).isdisjoint({A.id, B.id})`.

### WOA-RP-03 — a shorter list removes the others
- **Rules:** `replace_for_order` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.
2. B = row, `user_id U2.id`.

**When**
- `result = dao.replace_for_order(db, work_order_id=WO1.id, workspace_id=W1.id, user_ids=[U2.id])`.

**Then**
1. returns: `result is None`.
2. re-read WO1's rows: `users_of(WO1.id, W1.id) == [U2.id]`.

### WOA-RP-04 — [] removes everyone
- **Rules:** `replace_for_order` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.
2. B = row, `user_id U2.id`.

**When**
- `result = dao.replace_for_order(db, work_order_id=WO1.id, workspace_id=W1.id, user_ids=[])`.

**Then**
1. returns: `result is None`.
2. count: `row_ids_of(WO1.id) == set()`.

### WOA-RP-05 — another order's rows are untouched
- **Rules:** `replace_for_order` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. C = row, `user_id U3.id`, but `work_order_id WO2.id`.
2. A = row, `user_id U1.id`.

**When**
- `result = dao.replace_for_order(db, work_order_id=WO1.id, workspace_id=W1.id, user_ids=[U2.id])`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(C).
3. re-read WO1's rows: `users_of(WO1.id, W1.id) == [U2.id]`.

### WOA-RP-06 — a call under W2 deletes nothing of W1 and writes its rows under W2
- **Rules:** `replace_for_order` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.

**When**
- `result = dao.replace_for_order(db, work_order_id=WO1.id, workspace_id=W2.id, user_ids=[U2.id])`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(A).
3. re-read WO1's rows: `users_of(WO1.id, W2.id) == [U2.id]`.

### WOA-RP-07 — a W2 row on the order is not deleted
- **Rules:** `replace_for_order` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = row, `user_id U3.id`, but `workspace_id W2.id`.
2. A = row, `user_id U2.id`.

**When**
- `result = dao.replace_for_order(db, work_order_id=WO1.id, workspace_id=W1.id, user_ids=[U1.id])`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(Z).
3. re-read WO1's rows: `users_of(WO1.id, W1.id) == [U1.id]`.

### WOA-RP-08 — inserting the user of a kept W2 row raises 23505; the delete is undone too
- **Rules:** `replace_for_order` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. Z = row, `user_id U1.id`, but `workspace_id W2.id`.
2. A = row, `user_id U2.id`.

**When**
- `dao.replace_for_order(db, work_order_id=WO1.id, workspace_id=W1.id, user_ids=[U1.id])`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23505"`.
2. raises: `"uq_wo_assignee_wo_user" in str(exc.value.orig)`.
3. unchanged: unchanged(Z).
4. re-read WO1's rows: `users_of(WO1.id, W1.id) == [U2.id]`.

### WOA-RP-09 — an unknown user raises 23503; the delete is undone too
- **Rules:** `replace_for_order` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.

**When**
- `dao.replace_for_order(db, work_order_id=WO1.id, workspace_id=W1.id, user_ids=[U2.id, MISSING])`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. re-read WO1's rows: `users_of(WO1.id, W1.id) == [U1.id]`.
3. unchanged: unchanged(A).

### WOA-RP-10 — an unknown order with people raises 23503
- **Rules:** `replace_for_order` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.

**When**
- `dao.replace_for_order(db, work_order_id=MISSING, workspace_id=W1.id, user_ids=[U1.id])`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. nothing written: nothing written.

### WOA-RP-11 — an unknown order with [] raises nothing
- **Rules:** `replace_for_order` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.

**When**
- `result = dao.replace_for_order(db, work_order_id=MISSING, workspace_id=W1.id, user_ids=[])`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### WOA-RP-12 — any existing profile is accepted
- **Rules:** `replace_for_order` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. U4 belongs to no workspace: it is a standing row.

**When**
- `result = dao.replace_for_order(db, work_order_id=WO1.id, workspace_id=W1.id, user_ids=[U4.id])`.

**Then**
1. returns: `result is None`.
2. re-read WO1's rows: `users_of(WO1.id, W1.id) == [U4.id]`.

### WOA-RP-13 — a collection loaded before the call stays stale; a fresh query sees the new rows
- **Rules:** `replace_for_order` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.
2. `loaded = list(WO1.assignee_links)` (loads the collection; it holds A).

**When**
- `result = dao.replace_for_order(db, work_order_id=WO1.id, workspace_id=W1.id, user_ids=[U2.id])`.

**Then**
1. pending: `[l.user_id for l in WO1.assignee_links] == [U1.id]`.
2. re-read WO1's rows: `users_of(WO1.id, W1.id) == [U2.id]`.

### WOA-RP-14 — flushed, not committed: a rollback restores the old rows
- **Rules:** `replace_for_order` R8, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = row, `user_id U1.id`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.replace_for_order(db, work_order_id=WO1.id, workspace_id=W1.id, user_ids=[U2.id])`.

**Then**
1. returns: `result is None`.
2. re-read WO1's rows: inside the savepoint, `users_of(WO1.id, W1.id) == [U2.id]`.
3. re-read WO1's rows: after the savepoint rollback, `users_of(WO1.id, W1.id) == [U1.id]`.
4. mock called: the `db.commit` spy was never called.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Spec FU-1 (a) — **OWNER, order workflow:** a member removed from the workspace stays a planned worker of open work orders | `WorkspaceManager.remove_member_from_workspace`, `WorkOrderManager` | Owner item; not a DAO rule. |
| Spec FU-1 (b) — `WorkOrder.assignee_links` is read nowhere; stale after `replace_for_order` until expired | `WorkOrderManager` | R7 here (WOA-RP-13). |
| HR-16 — the manager passes only active members of the order's workspace | `WorkOrderManager._sync_assignees_from_text` | The DAO accepts any profile (WOA-RP-12). |
| P2 — hiding a deleted order is the work order manager's | `WorkOrderManager`, `WorkOrderService` | The DAO keeps its raw reads (WOA-GO-09, GU-08). |
| Inherited `BaseDAO` methods; module singleton | `tests/unit/dao/base.cases.md` / none | No caller. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Model facts | The modules of `WorkOrder`, `WorkOrderType` and `Factory` are not named, nor whether `WorkOrder` needs other NOT NULL columns. | Conventions use `app.models.work_order`, `app.models.work_order_type`, `app.models.factory` and the five columns the spec lists; a wrong one fails every card. |
| 2 | `get_user_ids_by_orders` R5 | The columns a real soft delete of a work order writes are not given. | WOD carries `is_deleted True` only. |
| 3 | Notes ("parametrize every case over both") | One cases file per module. | This file covers the assignee DAO; `work_order_completer.cases.md` repeats the cards for the completer. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_user_ids_by_orders` | Returns | WOA-GO-01 |
| `get_user_ids_by_orders` | R1 | WOA-GO-02 |
| `get_user_ids_by_orders` | R2 | WOA-GO-01, WOA-GO-03, WOA-GO-04 |
| `get_user_ids_by_orders` | R3 | WOA-GO-01, WOA-GO-05 |
| `get_user_ids_by_orders` | R4 | WOA-GO-06, WOA-GO-07, WOA-GO-08 |
| `get_user_ids_by_orders` | R5 | WOA-GO-09 |
| `get_user_ids_by_orders` | R6 | WOA-GO-10 |
| `get_user_ids_by_orders` | Side effects | WOA-GO-11 |
| `get_user_ids_by_order` | Returns | WOA-GU-01 |
| `get_user_ids_by_order` | R1 | WOA-GU-01, WOA-GU-02, WOA-GU-03, WOA-GU-04, WOA-GU-05, WOA-GU-06 |
| `get_user_ids_by_order` | R2 | WOA-GU-07, WOA-GU-10 |
| `get_user_ids_by_order` | R3 | WOA-GU-08 |
| `get_user_ids_by_order` | Side effects | WOA-GU-09 |
| `replace_for_order` | Returns | WOA-RP-01 |
| `replace_for_order` | R1 | WOA-RP-01 |
| `replace_for_order` | R2 | WOA-RP-02, WOA-RP-03, WOA-RP-04 |
| `replace_for_order` | R3 | WOA-RP-05, WOA-RP-06 |
| `replace_for_order` | R4 | WOA-RP-07, WOA-RP-08 |
| `replace_for_order` | R5 | WOA-RP-09, WOA-RP-10, WOA-RP-11 |
| `replace_for_order` | R6 | WOA-RP-12 |
| `replace_for_order` | R7 | WOA-RP-13 |
| `replace_for_order` | R8 | WOA-RP-14 |
| `replace_for_order` | Errors | WOA-RP-08, WOA-RP-09, WOA-RP-10 |
| `replace_for_order` | Side effects | WOA-RP-01, WOA-RP-14 |
