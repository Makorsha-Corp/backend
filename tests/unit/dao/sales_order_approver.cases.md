# Test cases — `app/dao/sales_order_approver.py`

> **Spec:** `tests/unit/dao/sales_order_approver.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-01; nothing open).
> **Revision:** 1 — the spec did not change. Additive, from `sales_order_approver.verify.md` (case-missing Findings 1 … 4; recipes R-1 … R-4): Finding 1 → SOA-GO-20; Finding 2 → SOA-GO-21; Finding 3 → one Then line on SOA-GO-19 and SOA-GU-16, and SOA-GU-17; Finding 4 → SOA-GU-18. SOA-GU-16 also gains R2 in its Rules line. The new Then lines are numbered last, so no existing Then number moved. No existing Given, When or ID changed, none retired.
> **Counts:** 39 cases · 35 expected-to-pass · 4 expected-to-fail (bugs) · 8 deferred

## Reviewer summary
- **Depth:** lighter target (skill step 1a). Two thin raw reads; the module writes no stock, money or order state, and the workflow rules live in the managers. Each rule's named inputs still get a card, because a When holds one call.
- **Per callable:** `get_by_order` 21 (4 bug) · `get_by_order_and_user` 18.
- **Expected-to-fail:** BUG-1200 4: GO-12, GO-13 non-strict (the lower id updated, and no update, so physical order lies both ways), GO-21 non-strict (user and approval would sort the other way, so `id` is the column that decides), GO-14 strict (the SQL recorder, the alarm that goes off when the bug is fixed). GO-11 is the passing companion: both tied rows come back, after the earlier one.
- **Commit spies:** none. Both methods only read, and the inherited writers (`create`, `update`, `remove`) are already spied by BASE-C-05, BASE-U-12, BASE-R-02, with no caller on this DAO.
- **Notable design choices:**
  - "Writes nothing" is one card per reader (GO-19, GU-16), and GU-17 for a read that finds its row: a row added and not flushed must stay pending, no write statement is sent, one `SELECT`, no `FOR UPDATE`, no `JOIN`, and P is the only object waiting in the session.
  - Every filter negative puts the other row where it would change the result: earlier than the expected row, or first in `id` order under `.first()`.
  - The cross-workspace row of R2 and R3 is invalid data by HR-16. The cards build it on purpose, because the rules state what the raw read does with it.
  - R4's other side is in the cards with two rows that differ in one key: the same order with two users, the same user on two orders.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking. See the **Order** rows of Spec gaps.

## Conventions for this module

**IDs.** `SOA` = `app/dao/sales_order_approver.py`. `GO` get_by_order · `GU` get_by_order_and_user.

**Actors and fixed values.**
- `dao` = the singleton `sales_order_approver_dao` (`from app.dao.sales_order_approver import sales_order_approver_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `SalesOrderApprover` = `app.models.sales_order_approver.SalesOrderApprover`. `SalesOrder` = `app.models.sales_order.SalesOrder`. `WorkspaceMember` = `app.models.workspace_member.WorkspaceMember`. `date`, `datetime`, `timedelta` = the `datetime` module's classes. `text` = `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.
- T10 = `datetime(2026, 3, 4, 10, 0, 0)`, T11 = `datetime(2026, 3, 4, 11, 0, 0)`, T12 = `datetime(2026, 3, 4, 12, 0, 0)`.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line (workspaces and profiles from `make_workspace`, `make_profile`):
  - W1, W2 = two `workspaces` rows. U1, U2, U3 = three `profiles` rows. None of them has a `workspace_members` row unless the card says `left`.
  - O1 = `sales_orders` row: `SalesOrder(workspace_id=W1.id, sales_order_number="SO-T-001", account_id=MISSING, factory_id=MISSING, order_date=date(2026, 3, 1), total_amount=0, current_status_id=MISSING, created_by=U1.id)`. O2 = the same, but `sales_order_number "SO-T-002"`. O9 = the same, but `workspace_id W2.id`, `sales_order_number "SO-T-009"`.
  - OC = the same as O1, but `sales_order_number "SO-T-003"`, `order_completed True`, `completed_at T12`, `completed_by U1.id`.
  - All of these orders are built between `db.execute(text("SET LOCAL session_replication_role = replica"))` and `db.execute(text("SET LOCAL session_replication_role = origin"))`, because `account_id`, `factory_id` and `current_status_id` name no row. Never `UPDATE` an order: that checks those ids again, so every order column is given at insert.
- **approver** = `sales_order_approvers` row built with `SalesOrderApprover`: `workspace_id W1.id`, `sales_order_id O1.id`, `user_id U1.id`; `assigned_by`, `approved`, `approved_at` are not passed. The card always gives `assigned_at`; after the word "but" it lists every other column that differs.
- **left U** = a `WorkspaceMember(workspace_id=W1.id, user_id=U.id, role="member", status="inactive")` row: the membership of someone removed from W1.
- No `sales_order_approvers` row exists unless the card's Given lists it.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending. "it is a standing row" means the order is not inserted again; the line only says what it holds.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned; the order is part of the check.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the number of `sales_order_approvers` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P after the call, on the object itself. `pending: len(db.new) == 1` checks that P is the only object waiting in the session.
- `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the When: `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the When; keep using `db` afterwards (the savepoint is rolled back). Further `raises:` lines are assertions on `exc.value`, written after the `with` block, one `assert` per line.

**xfail cards.** Write the call and the checks exactly as shown; add `pytest.mark.xfail(strict=True, reason="BUG-1200")`, or `strict=False` on a card whose Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `sales_order_approvers`; `order_part` = the text of `sql` after its first `ORDER BY` (`""` when there is none); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `SalesOrderApproverDAO.get_by_order`

### SOA-GO-01 — returns a list of the order's rows, pending and approved alike
- **Rules:** `get_by_order` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.
2. B = approver, `assigned_at T11`, but `user_id U2.id`, `approved True`, `approved_at T12`.

**When**
- `result = dao.get_by_order(db, sales_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id, B.id]`.
3. returns: `isinstance(result[0], SalesOrderApprover)`.
4. returns: `result[0].approved is False`.
5. returns: `result[1].approved is True`.

### SOA-GO-02 — an earlier row of another order of the same workspace is not returned
- **Rules:** `get_by_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T11`.
2. B = approver, `assigned_at T10`, but `sales_order_id O2.id`, `user_id U2.id`.

**When**
- `result = dao.get_by_order(db, sales_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### SOA-GO-03 — the right order under another workspace returns an empty list
- **Rules:** `get_by_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.

**When**
- `result = dao.get_by_order(db, sales_order_id=O1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### SOA-GO-04 — a W1 row on an order of W2 is returned for W1: only the row's workspace is compared
- **Rules:** `get_by_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`, but `sales_order_id O9.id`.

**When**
- `result = dao.get_by_order(db, sales_order_id=O9.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### SOA-GO-05 — a W1 row on an order of W2 is not returned for W2
- **Rules:** `get_by_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`, but `sales_order_id O9.id`.

**When**
- `result = dao.get_by_order(db, sales_order_id=O9.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### SOA-GO-06 — an unknown order id returns an empty list
- **Rules:** `get_by_order` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.

**When**
- `result = dao.get_by_order(db, sales_order_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### SOA-GO-07 — sales_order_id=0 returns an empty list
- **Rules:** `get_by_order` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.

**When**
- `result = dao.get_by_order(db, sales_order_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### SOA-GO-08 — an unknown workspace returns an empty list
- **Rules:** `get_by_order` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.

**When**
- `result = dao.get_by_order(db, sales_order_id=O1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### SOA-GO-09 — an order with no approvers returns an empty list
- **Rules:** `get_by_order` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.

**When**
- `result = dao.get_by_order(db, sales_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### SOA-GO-10 — rows are ordered by assigned_at ascending, whatever their ids
- **Rules:** `get_by_order` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T12`.
2. B = approver, `assigned_at T11`, but `user_id U2.id`.
3. C = approver, `assigned_at T10`, but `user_id U3.id`.

**When**
- `result = dao.get_by_order(db, sales_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [C.id, B.id, A.id]`.

### SOA-GO-11 — on a tie both rows are returned, after the earlier row
- **Rules:** `get_by_order` R5, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T11`.
2. B = approver, `assigned_at T11`, but `user_id U2.id`.
3. C = approver, `assigned_at T10`, but `user_id U3.id`.
4. `A.approved = True`, `A.approved_at = T12`, then `db.flush()`.
5. `db.expire_all()`.

**When**
- `result = dao.get_by_order(db, sales_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `result[0].id == C.id`.
3. returns: `{r.id for r in result[1:]} == {A.id, B.id}`.

### SOA-GO-12 — on a tie the lowest id comes first, when the lower id was updated
- **Rules:** `get_by_order` R5 [BUG-1200]
- **Kind:** bug
- **Expect:** xfail BUG-1200 (non-strict)
- **Fails today on:** Then 2 (no order is requested among the tied rows; the updated lower-id row can come second, but that rests on physical row order, which can match the intended result by accident)

**Given**
1. A = approver, `assigned_at T11`.
2. B = approver, `assigned_at T11`, but `user_id U2.id`.
3. `A.approved = True`, `A.approved_at = T12`, then `db.flush()`.
4. `db.expire_all()`.

**When**
- `result = dao.get_by_order(db, sales_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### SOA-GO-13 — on a tie the lowest id comes first, with no update
- **Rules:** `get_by_order` R5 [BUG-1200]
- **Kind:** bug
- **Expect:** xfail BUG-1200 (non-strict)
- **Fails today on:** Then 2 (no order is requested among the tied rows; with no update physical order usually gives the intended result, which is why this card is non-strict)

**Given**
1. A = approver, `assigned_at T11`.
2. B = approver, `assigned_at T11`, but `user_id U2.id`.
3. `db.expire_all()`.

**When**
- `result = dao.get_by_order(db, sales_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### SOA-GO-14 — the query orders by assigned_at, then id ascending
- **Rules:** `get_by_order` R5 [BUG-1200]
- **Kind:** bug
- **Expect:** xfail BUG-1200
- **Fails today on:** Then 4 (the query orders by `assigned_at` alone)

**Given**
1. A = approver, `assigned_at T10`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_order(db, sales_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"assigned_at" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("assigned_at") < order_part.index(".id")`.
6. statement: `"DESC" not in order_part.upper()`.

### SOA-GO-15 — there is no cap: 101 approvers give 101 rows
- **Rules:** `get_by_order` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 profiles P1 … P101, each from `make_profile(db)`.
2. 101 approvers E1 … E101, built with `add_all`: Ek = approver, `assigned_at` = `T10 + timedelta(minutes=k)`, but `user_id Pk.id`. `in_order` = the ids of E1, E2, … E101, in that order.

**When**
- `result = dao.get_by_order(db, sales_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == in_order`.

### SOA-GO-16 — the rows of people who left the workspace are returned, pending and approved
- **Rules:** `get_by_order` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. left U2.
2. left U3.
3. A = approver, `assigned_at T10`, but `user_id U2.id`.
4. B = approver, `assigned_at T11`, but `user_id U3.id`, `approved True`, `approved_at T12`.

**When**
- `result = dao.get_by_order(db, sales_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.
2. returns: `result[0].approved is False`.
3. returns: `result[1].approved is True`.

### SOA-GO-17 — the rows of a completed order are returned
- **Rules:** `get_by_order` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order OC has `order_completed True`, `completed_at T12`, `completed_by U1.id`: it is a standing row.
2. A = approver, `assigned_at T10`, but `sales_order_id OC.id`.
3. B = approver, `assigned_at T11`, but `sales_order_id OC.id`, `user_id U2.id`, `approved True`, `approved_at T12`.

**When**
- `result = dao.get_by_order(db, sales_order_id=OC.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### SOA-GO-18 — a row comes back as stored
- **Rules:** `get_by_order` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T11`, but `assigned_by U3.id`, `approved True`, `approved_at T12`.

**When**
- `result = dao.get_by_order(db, sales_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].workspace_id == W1.id`, `result[0].sales_order_id == O1.id`, `result[0].user_id == U1.id`.
3. returns: `result[0].assigned_by == U3.id`, `result[0].assigned_at == T11`.
4. returns: `result[0].approved is True`, `result[0].approved_at == T12`.

### SOA-GO-19 — writes nothing: an earlier pending row stays pending and is not returned
- **Rules:** `get_by_order` R9, Side effects, Overview
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T11`.
2. `P = SalesOrderApprover(workspace_id=W1.id, sales_order_id=O1.id, user_id=U2.id, assigned_at=T10)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_order(db, sales_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. nothing written: nothing written.
5. unchanged: unchanged(A).
6. statement: `written == []`.
7. statement: `len(selects) == 1`.
8. statement: `"FOR UPDATE" not in sql.upper()`.
9. statement: `"JOIN" not in sql.upper()`.
10. pending: `len(db.new) == 1`.

### SOA-GO-20 — an approved row stamped earlier comes before a later pending row
- **Rules:** `get_by_order` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`, but `approved True`, `approved_at T12`.
2. B = approver, `assigned_at T11`, but `user_id U2.id`.

**When**
- `result = dao.get_by_order(db, sales_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### SOA-GO-21 — on a tie the lowest id comes first, when user and approval would sort the other way
- **Rules:** `get_by_order` R5 [BUG-1200]
- **Kind:** bug
- **Expect:** xfail BUG-1200 (non-strict)
- **Fails today on:** Then 2 (no order is requested among the tied rows; physical order usually gives the intended result, which is why this card is non-strict)

**Given**
1. A = approver, `assigned_at T11`, but `user_id U2.id`.
2. B = approver, `assigned_at T11`, but `user_id U1.id`, `approved True`, `approved_at T12`, `assigned_by U3.id`.
3. `db.expire_all()`.

**When**
- `result = dao.get_by_order(db, sales_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.


## `SalesOrderApproverDAO.get_by_order_and_user`

### SOA-GU-01 — returns the row of that user, not the order's first row
- **Rules:** `get_by_order_and_user` R1, R4, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.
2. B = approver, `assigned_at T11`, but `user_id U2.id`.

**When**
- `result = dao.get_by_order_and_user(db, sales_order_id=O1.id, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == B.id`.
2. returns: `isinstance(result, SalesOrderApprover)`.
3. returns: `result.approved is False`.

### SOA-GU-02 — returns the row on that order, not the user's first row
- **Rules:** `get_by_order_and_user` R1, R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.
2. B = approver, `assigned_at T11`, but `sales_order_id O2.id`.

**When**
- `result = dao.get_by_order_and_user(db, sales_order_id=O2.id, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == B.id`.

### SOA-GU-03 — a user with a row only on another order returns None and nothing is created
- **Rules:** `get_by_order_and_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`, but `sales_order_id O2.id`.
2. B = approver, `assigned_at T11`, but `user_id U2.id`.

**When**
- `result = dao.get_by_order_and_user(db, sales_order_id=O1.id, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### SOA-GU-04 — an unknown order id returns None and nothing is created
- **Rules:** `get_by_order_and_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.

**When**
- `result = dao.get_by_order_and_user(db, sales_order_id=MISSING, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### SOA-GU-05 — sales_order_id=0 returns None and nothing is created
- **Rules:** `get_by_order_and_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.

**When**
- `result = dao.get_by_order_and_user(db, sales_order_id=0, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### SOA-GU-06 — an unknown user id returns None and nothing is created
- **Rules:** `get_by_order_and_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.

**When**
- `result = dao.get_by_order_and_user(db, sales_order_id=O1.id, user_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### SOA-GU-07 — user_id=0 returns None and nothing is created
- **Rules:** `get_by_order_and_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.

**When**
- `result = dao.get_by_order_and_user(db, sales_order_id=O1.id, user_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### SOA-GU-08 — the right order and user under another workspace return None
- **Rules:** `get_by_order_and_user` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.

**When**
- `result = dao.get_by_order_and_user(db, sales_order_id=O1.id, user_id=U1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### SOA-GU-09 — a W1 row on an order of W2 is returned for W1: only the row's workspace is compared
- **Rules:** `get_by_order_and_user` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`, but `sales_order_id O9.id`.

**When**
- `result = dao.get_by_order_and_user(db, sales_order_id=O9.id, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### SOA-GU-10 — a W1 row on an order of W2 is not returned for W2
- **Rules:** `get_by_order_and_user` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`, but `sales_order_id O9.id`.

**When**
- `result = dao.get_by_order_and_user(db, sales_order_id=O9.id, user_id=U1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### SOA-GU-11 — a W1 row on an order of W2 still blocks a W2 row for that user
- **Rules:** `get_by_order_and_user` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`, but `sales_order_id O9.id`.
2. `X = SalesOrderApprover(workspace_id=W2.id, sales_order_id=O9.id, user_id=U1.id, assigned_at=T11)`

**When**
- `db.add(X)`, then `db.flush()`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. raises: `"uq_so_approver_so_user" in str(exc.value.orig)`.
4. count: `sales_order_approvers` has exactly 1 row with `sales_order_id == O9.id` and `user_id == U1.id`.
5. unchanged: unchanged(A).

### SOA-GU-12 — a second row for the same order and user is refused
- **Rules:** `get_by_order_and_user` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.
2. `X = SalesOrderApprover(workspace_id=W1.id, sales_order_id=O1.id, user_id=U1.id, assigned_at=T11)`

**When**
- `db.add(X)`, then `db.flush()`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. raises: `"uq_so_approver_so_user" in str(exc.value.orig)`.
4. count: `sales_order_approvers` has exactly 1 row with `sales_order_id == O1.id` and `user_id == U1.id`.
5. unchanged: unchanged(A).

### SOA-GU-13 — an approved row comes back as stored
- **Rules:** `get_by_order_and_user` R5, R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T11`, but `assigned_by U3.id`, `approved True`, `approved_at T12`.

**When**
- `result = dao.get_by_order_and_user(db, sales_order_id=O1.id, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.workspace_id == W1.id`, `result.sales_order_id == O1.id`, `result.user_id == U1.id`.
3. returns: `result.assigned_by == U3.id`, `result.assigned_at == T11`.
4. returns: `result.approved is True`, `result.approved_at == T12`.

### SOA-GU-14 — the pending row of someone who left the workspace is returned
- **Rules:** `get_by_order_and_user` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. left U2.
2. A = approver, `assigned_at T10`, but `user_id U2.id`.

**When**
- `result = dao.get_by_order_and_user(db, sales_order_id=O1.id, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.approved is False`.

### SOA-GU-15 — the row on a completed order is returned
- **Rules:** `get_by_order_and_user` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order OC has `order_completed True`, `completed_at T12`, `completed_by U1.id`: it is a standing row.
2. A = approver, `assigned_at T10`, but `sales_order_id OC.id`.

**When**
- `result = dao.get_by_order_and_user(db, sales_order_id=OC.id, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### SOA-GU-16 — writes nothing: a pending row stays pending and is not returned
- **Rules:** `get_by_order_and_user` R2, Side effects, Overview
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.
2. `P = SalesOrderApprover(workspace_id=W1.id, sales_order_id=O1.id, user_id=U2.id, assigned_at=T11)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_order_and_user(db, sales_order_id=O1.id, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. nothing written: nothing written.
5. unchanged: unchanged(A).
6. statement: `written == []`.
7. statement: `len(selects) == 1`.
8. statement: `"FOR UPDATE" not in sql.upper()`.
9. statement: `"JOIN" not in sql.upper()`.
10. pending: `len(db.new) == 1`.

### SOA-GU-17 — writes nothing: a read that finds its row leaves the session as it was
- **Rules:** `get_by_order_and_user` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.
2. `P = SalesOrderApprover(workspace_id=W1.id, sales_order_id=O1.id, user_id=U2.id, assigned_at=T11)`
3. `db.add(P)` (not flushed).

**When**
- `result = dao.get_by_order_and_user(db, sales_order_id=O1.id, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. nothing written: nothing written.

### SOA-GU-18 — the approved row of someone who left the workspace is returned
- **Rules:** `get_by_order_and_user` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. left U2.
2. A = approver, `assigned_at T10`, but `user_id U2.id`, `approved True`, `approved_at T12`.

**When**
- `result = dao.get_by_order_and_user(db, sales_order_id=O1.id, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.approved is True`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_by_order` R2, `get_by_order_and_user` R3 — a row linking two workspaces cannot reach a response; `list_approvers` answers 404 first (HR-16) | `SalesManager.list_approvers` | This DAO returns the row for its own workspace; the 404 is what keeps it out of a response. |
| `get_by_order` R7, `get_by_order_and_user` R5 — BUG-1201 (FU-2): removal deletes pending rows on open orders, one `approver_removed` event per order; approved rows and closed orders stay | `WorkspaceManager.remove_member_from_workspace` | The rule and the tag belong to that spec. When its new read is added to this DAO, this file gets cards for it. |
| Generic behavior of inherited `get`, `get_multi`, `get_by_workspace`, `get_by_id_and_workspace`, `create`, `update`, `remove` | `tests/unit/dao/base.spec.md` / `base.cases.md` | No caller on this DAO. Commit spies of the writers: BASE-C-05, BASE-U-12, BASE-R-02. |
| Module singleton `sales_order_approver_dao` | none (no logic) | Only used as the entry point of every card. |
| Notes: keyword-only parameters | none (no rule) | Spec gap 1. |
| FU-1 — `list_approvers` R2 says "equal times in no guaranteed order"; after BUG-1200 ties go to the lowest `id` | `SalesManager.list_approvers` | Spec text, when next touched. |
| FU-3 — BUG-1205: sales approvers are notified like the other four order types | `approval_notification_service`, `SalesService` | No rule of this DAO. |
| HR-10 note — if the BUG-720 fix adds a lock option here, `get_by_order_and_user` gets a new rule | `SalesManager.set_approval`, then this spec | Today the writes-nothing cards assert no `FOR UPDATE`. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Notes ("Every parameter after `db` is keyword-only"), Branch map 11–13, 24–26 | Stated as a note, not as a rule. | No card, as in `machine_activity_event.cases.md`, `machine_item.cases.md`, `item_tag.cases.md`. |
| 2 | Overview ("takes no lock"), Branch map 16–19, 29–33 ("no join") | Each stands outside the numbered rules. | Covered anyway, as Overview rows of the matrix, by the two writes-nothing cards. Drop those lines if they are not meant as a contract. |
| 3 | Model facts | These are not rules of the DAO: defaults, cascades, the `now()` default of `assigned_at` storing local time on raw SQL, the docstring "Approve-only". **Order:** among them, deleting a profile also deletes that person's approval. | No card. No code path deletes a profile, so nothing is lost today; those facts are owned by the schema, not by this DAO. |
| 4 | Model facts, Notes | The spec gives the class names, not their modules. `app.models.sales_order_approver` is the path existing tests import. | Conventions use the path. A wrong one fails at import, in every test. |
| 5 | `get_by_order` R7, `get_by_order_and_user` R5 | **Order.** The membership row's class and columns are not in this spec. `WorkspaceMember` with `role`, `status` comes from `core/deps.spec.md` Notes; its module from existing tests. | The `left` line of Conventions uses them. |
| 6 | `get_by_order` R8, `get_by_order_and_user` R5 | **Order.** The columns of a completed order are not in this spec: `order_completed`, `completed_at`, `completed_by` come from `sales_manager.spec.md`, `mark_order_complete` R6. | SOA closed-order cards use them. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_order` | Returns | SOA-GO-01 |
| `get_by_order` | R1 | SOA-GO-01, SOA-GO-02 |
| `get_by_order` | R2 | SOA-GO-03, SOA-GO-04, SOA-GO-05 |
| `get_by_order` | R3 | SOA-GO-06, SOA-GO-07, SOA-GO-08, SOA-GO-09 |
| `get_by_order` | R4 | SOA-GO-10, SOA-GO-11, SOA-GO-20 |
| `get_by_order` | R5 | SOA-GO-11 |
| `get_by_order` | R5 [BUG-1200] | SOA-GO-12, SOA-GO-13, SOA-GO-14, SOA-GO-21 |
| `get_by_order` | R6 | SOA-GO-15 |
| `get_by_order` | R7 | SOA-GO-16 |
| `get_by_order` | R8 | SOA-GO-17 |
| `get_by_order` | R9 | SOA-GO-18, SOA-GO-19 |
| `get_by_order` | Overview | SOA-GO-19 |
| `get_by_order` | Side effects | SOA-GO-19 |
| `get_by_order_and_user` | Returns | SOA-GU-01 |
| `get_by_order_and_user` | R1 | SOA-GU-01, SOA-GU-02, SOA-GU-13 |
| `get_by_order_and_user` | R2 | SOA-GU-03, SOA-GU-04, SOA-GU-05, SOA-GU-06, SOA-GU-07, SOA-GU-16 |
| `get_by_order_and_user` | R3 | SOA-GU-08, SOA-GU-09, SOA-GU-10, SOA-GU-11 |
| `get_by_order_and_user` | R4 | SOA-GU-01, SOA-GU-02, SOA-GU-12 |
| `get_by_order_and_user` | R5 | SOA-GU-13, SOA-GU-14, SOA-GU-15, SOA-GU-18 |
| `get_by_order_and_user` | Errors row 1 (the insert's `IntegrityError`) | SOA-GU-12 |
| `get_by_order_and_user` | Overview | SOA-GU-16 |
| `get_by_order_and_user` | Side effects | SOA-GU-16, SOA-GU-17 |
