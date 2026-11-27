# Test cases — `app/dao/expense_order_approver.py`

> **Spec:** `tests/unit/dao/expense_order_approver.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-01; nothing open).
> **Revision:** 1 — the spec did not change. Additive, from `expense_order_approver.verify.md` (case-missing Findings 1 … 4; recipes R-1 … R-4): Finding 1 → EOA-GO-21; Finding 2 → EOA-GO-22; Finding 3 → one Then line on EOA-GO-20 and EOA-GU-17, and EOA-GU-18; Finding 4 → EOA-GU-19. EOA-GU-17 also gains R2 in its Rules line. The new Then lines are numbered last, so no existing Then number moved. No existing Given, When or ID changed, none retired.
> **Counts:** 41 cases · 37 expected-to-pass · 4 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Depth:** lighter target (skill step 1a). Two thin raw reads; the module writes no stock, money or order state, and the workflow rules live in the managers. Each rule's named inputs still get a card, because a When holds one call.
- **Per callable:** `get_by_order` 22 (4 bug) · `get_by_order_and_user` 19.
- **Expected-to-fail:** BUG-1200 4: GO-12, GO-13 non-strict (the lower id updated, and no update, so physical order lies both ways), GO-22 non-strict (user and approval would sort the other way, so `id` is the column that decides), GO-14 strict (the SQL recorder, the alarm that goes off when the bug is fixed). GO-11 is the passing companion: both tied rows come back, after the earlier one.
- **Commit spies:** none. Both methods only read, and the inherited writers (`create`, `update`, `remove`) are already spied by BASE-C-05, BASE-U-12, BASE-R-02, with no caller on this DAO.
- **Notable design choices:**
  - "Writes nothing" is one card per reader (GO-20, GU-17), and GU-18 for a read that finds its row: a row added and not flushed must stay pending, no write statement is sent, one `SELECT`, no `FOR UPDATE`, no `JOIN`, and P is the only object waiting in the session.
  - Every filter negative puts the other row where it would change the result: earlier than the expected row, or first in `id` order under `.first()`.
  - The cross-workspace row of R2 and R3 is invalid data by HR-16. The cards build it on purpose, because the rules state what the raw read does with it.
  - R4's other side is in the cards with two rows that differ in one key: the same order with two users, the same user on two orders.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking. See the **Order** rows of Spec gaps.

## Conventions for this module

**IDs.** `EOA` = `app/dao/expense_order_approver.py`. `GO` get_by_order · `GU` get_by_order_and_user.

**Actors and fixed values.**
- `dao` = the singleton `expense_order_approver_dao` (`from app.dao.expense_order_approver import expense_order_approver_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `ExpenseOrderApprover` = `app.models.expense_order_approver.ExpenseOrderApprover`. `ExpenseOrder` = `app.models.expense_order.ExpenseOrder`. `WorkspaceMember` = `app.models.workspace_member.WorkspaceMember`. `date`, `datetime`, `timedelta` = the `datetime` module's classes. `text` = `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.
- T10 = `datetime(2026, 3, 4, 10, 0, 0)`, T11 = `datetime(2026, 3, 4, 11, 0, 0)`, T12 = `datetime(2026, 3, 4, 12, 0, 0)`.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line (workspaces and profiles from `make_workspace`, `make_profile`):
  - W1, W2 = two `workspaces` rows. U1, U2, U3 = three `profiles` rows. None of them has a `workspace_members` row unless the card says `left`.
  - O1 = `expense_orders` row: `ExpenseOrder(workspace_id=W1.id, expense_number="EXP-T-001", expense_category="other", expense_date=date(2026, 3, 1), subtotal=0, total_amount=0, created_by=U1.id, description="Order One")`. O2 = the same, but `expense_number "EXP-T-002"`. O9 = the same, but `workspace_id W2.id`, `expense_number "EXP-T-009"`.
  - OC = the same as O1, but `expense_number "EXP-T-003"`, `completed_at T12`. OV = the same as O1, but `expense_number "EXP-T-004"`, `voided True`.
  - Every order column is given at insert; no order is updated.
- **approver** = `expense_order_approvers` row built with `ExpenseOrderApprover`: `workspace_id W1.id`, `expense_order_id O1.id`, `user_id U1.id`; `assigned_by`, `approved`, `approved_at` are not passed. The card always gives `assigned_at`; after the word "but" it lists every other column that differs.
- **left U** = a `WorkspaceMember(workspace_id=W1.id, user_id=U.id, role="member", status="inactive")` row: the membership of someone removed from W1.
- No `expense_order_approvers` row exists unless the card's Given lists it.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending. "it is a standing row" means the order is not inserted again; the line only says what it holds.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned; the order is part of the check.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the number of `expense_order_approvers` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P after the call, on the object itself. `pending: len(db.new) == 1` checks that P is the only object waiting in the session.
- `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the When: `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the When; keep using `db` afterwards (the savepoint is rolled back). Further `raises:` lines are assertions on `exc.value`, written after the `with` block, one `assert` per line.

**xfail cards.** Write the call and the checks exactly as shown; add `pytest.mark.xfail(strict=True, reason="BUG-1200")`, or `strict=False` on a card whose Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `expense_order_approvers`; `order_part` = the text of `sql` after its first `ORDER BY` (`""` when there is none); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `ExpenseOrderApproverDAO.get_by_order`

### EOA-GO-01 — returns a list of the order's rows, pending and approved alike
- **Rules:** `get_by_order` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.
2. B = approver, `assigned_at T11`, but `user_id U2.id`, `approved True`, `approved_at T12`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id, B.id]`.
3. returns: `isinstance(result[0], ExpenseOrderApprover)`.
4. returns: `result[0].approved is False`.
5. returns: `result[1].approved is True`.

### EOA-GO-02 — an earlier row of another order of the same workspace is not returned
- **Rules:** `get_by_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T11`.
2. B = approver, `assigned_at T10`, but `expense_order_id O2.id`, `user_id U2.id`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### EOA-GO-03 — the right order under another workspace returns an empty list
- **Rules:** `get_by_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### EOA-GO-04 — a W1 row on an order of W2 is returned for W1: only the row's workspace is compared
- **Rules:** `get_by_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`, but `expense_order_id O9.id`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O9.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### EOA-GO-05 — a W1 row on an order of W2 is not returned for W2
- **Rules:** `get_by_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`, but `expense_order_id O9.id`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O9.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### EOA-GO-06 — an unknown order id returns an empty list
- **Rules:** `get_by_order` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.

**When**
- `result = dao.get_by_order(db, expense_order_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### EOA-GO-07 — expense_order_id=0 returns an empty list
- **Rules:** `get_by_order` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.

**When**
- `result = dao.get_by_order(db, expense_order_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### EOA-GO-08 — an unknown workspace returns an empty list
- **Rules:** `get_by_order` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### EOA-GO-09 — an order with no approvers returns an empty list
- **Rules:** `get_by_order` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### EOA-GO-10 — rows are ordered by assigned_at ascending, whatever their ids
- **Rules:** `get_by_order` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T12`.
2. B = approver, `assigned_at T11`, but `user_id U2.id`.
3. C = approver, `assigned_at T10`, but `user_id U3.id`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [C.id, B.id, A.id]`.

### EOA-GO-11 — on a tie both rows are returned, after the earlier row
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
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `result[0].id == C.id`.
3. returns: `{r.id for r in result[1:]} == {A.id, B.id}`.

### EOA-GO-12 — on a tie the lowest id comes first, when the lower id was updated
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
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### EOA-GO-13 — on a tie the lowest id comes first, with no update
- **Rules:** `get_by_order` R5 [BUG-1200]
- **Kind:** bug
- **Expect:** xfail BUG-1200 (non-strict)
- **Fails today on:** Then 2 (no order is requested among the tied rows; with no update physical order usually gives the intended result, which is why this card is non-strict)

**Given**
1. A = approver, `assigned_at T11`.
2. B = approver, `assigned_at T11`, but `user_id U2.id`.
3. `db.expire_all()`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### EOA-GO-14 — the query orders by assigned_at, then id ascending
- **Rules:** `get_by_order` R5 [BUG-1200]
- **Kind:** bug
- **Expect:** xfail BUG-1200
- **Fails today on:** Then 4 (the query orders by `assigned_at` alone)

**Given**
1. A = approver, `assigned_at T10`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"assigned_at" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("assigned_at") < order_part.index(".id")`.
6. statement: `"DESC" not in order_part.upper()`.

### EOA-GO-15 — there is no cap: 101 approvers give 101 rows
- **Rules:** `get_by_order` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 profiles P1 … P101, each from `make_profile(db)`.
2. 101 approvers E1 … E101, built with `add_all`: Ek = approver, `assigned_at` = `T10 + timedelta(minutes=k)`, but `user_id Pk.id`. `in_order` = the ids of E1, E2, … E101, in that order.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == in_order`.

### EOA-GO-16 — the rows of people who left the workspace are returned, pending and approved
- **Rules:** `get_by_order` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. left U2.
2. left U3.
3. A = approver, `assigned_at T10`, but `user_id U2.id`.
4. B = approver, `assigned_at T11`, but `user_id U3.id`, `approved True`, `approved_at T12`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.
2. returns: `result[0].approved is False`.
3. returns: `result[1].approved is True`.

### EOA-GO-17 — the rows of a completed order are returned
- **Rules:** `get_by_order` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order OC has `completed_at T12`: it is a standing row.
2. A = approver, `assigned_at T10`, but `expense_order_id OC.id`.
3. B = approver, `assigned_at T11`, but `expense_order_id OC.id`, `user_id U2.id`, `approved True`, `approved_at T12`.

**When**
- `result = dao.get_by_order(db, expense_order_id=OC.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### EOA-GO-18 — the rows of a voided order are returned
- **Rules:** `get_by_order` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order OV has `voided True`: it is a standing row.
2. A = approver, `assigned_at T10`, but `expense_order_id OV.id`.
3. B = approver, `assigned_at T11`, but `expense_order_id OV.id`, `user_id U2.id`, `approved True`, `approved_at T12`.

**When**
- `result = dao.get_by_order(db, expense_order_id=OV.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### EOA-GO-19 — a row comes back as stored
- **Rules:** `get_by_order` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T11`, but `assigned_by U3.id`, `approved True`, `approved_at T12`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].workspace_id == W1.id`, `result[0].expense_order_id == O1.id`, `result[0].user_id == U1.id`.
3. returns: `result[0].assigned_by == U3.id`, `result[0].assigned_at == T11`.
4. returns: `result[0].approved is True`, `result[0].approved_at == T12`.

### EOA-GO-20 — writes nothing: an earlier pending row stays pending and is not returned
- **Rules:** `get_by_order` R9, Side effects, Overview
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T11`.
2. `P = ExpenseOrderApprover(workspace_id=W1.id, expense_order_id=O1.id, user_id=U2.id, assigned_at=T10)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

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

### EOA-GO-21 — an approved row stamped earlier comes before a later pending row
- **Rules:** `get_by_order` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`, but `approved True`, `approved_at T12`.
2. B = approver, `assigned_at T11`, but `user_id U2.id`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### EOA-GO-22 — on a tie the lowest id comes first, when user and approval would sort the other way
- **Rules:** `get_by_order` R5 [BUG-1200]
- **Kind:** bug
- **Expect:** xfail BUG-1200 (non-strict)
- **Fails today on:** Then 2 (no order is requested among the tied rows; physical order usually gives the intended result, which is why this card is non-strict)

**Given**
1. A = approver, `assigned_at T11`, but `user_id U2.id`.
2. B = approver, `assigned_at T11`, but `user_id U1.id`, `approved True`, `approved_at T12`, `assigned_by U3.id`.
3. `db.expire_all()`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.


## `ExpenseOrderApproverDAO.get_by_order_and_user`

### EOA-GU-01 — returns the row of that user, not the order's first row
- **Rules:** `get_by_order_and_user` R1, R4, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.
2. B = approver, `assigned_at T11`, but `user_id U2.id`.

**When**
- `result = dao.get_by_order_and_user(db, expense_order_id=O1.id, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == B.id`.
2. returns: `isinstance(result, ExpenseOrderApprover)`.
3. returns: `result.approved is False`.

### EOA-GU-02 — returns the row on that order, not the user's first row
- **Rules:** `get_by_order_and_user` R1, R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.
2. B = approver, `assigned_at T11`, but `expense_order_id O2.id`.

**When**
- `result = dao.get_by_order_and_user(db, expense_order_id=O2.id, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == B.id`.

### EOA-GU-03 — a user with a row only on another order returns None and nothing is created
- **Rules:** `get_by_order_and_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`, but `expense_order_id O2.id`.
2. B = approver, `assigned_at T11`, but `user_id U2.id`.

**When**
- `result = dao.get_by_order_and_user(db, expense_order_id=O1.id, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### EOA-GU-04 — an unknown order id returns None and nothing is created
- **Rules:** `get_by_order_and_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.

**When**
- `result = dao.get_by_order_and_user(db, expense_order_id=MISSING, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### EOA-GU-05 — expense_order_id=0 returns None and nothing is created
- **Rules:** `get_by_order_and_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.

**When**
- `result = dao.get_by_order_and_user(db, expense_order_id=0, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### EOA-GU-06 — an unknown user id returns None and nothing is created
- **Rules:** `get_by_order_and_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.

**When**
- `result = dao.get_by_order_and_user(db, expense_order_id=O1.id, user_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### EOA-GU-07 — user_id=0 returns None and nothing is created
- **Rules:** `get_by_order_and_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.

**When**
- `result = dao.get_by_order_and_user(db, expense_order_id=O1.id, user_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### EOA-GU-08 — the right order and user under another workspace return None
- **Rules:** `get_by_order_and_user` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.

**When**
- `result = dao.get_by_order_and_user(db, expense_order_id=O1.id, user_id=U1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### EOA-GU-09 — a W1 row on an order of W2 is returned for W1: only the row's workspace is compared
- **Rules:** `get_by_order_and_user` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`, but `expense_order_id O9.id`.

**When**
- `result = dao.get_by_order_and_user(db, expense_order_id=O9.id, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### EOA-GU-10 — a W1 row on an order of W2 is not returned for W2
- **Rules:** `get_by_order_and_user` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`, but `expense_order_id O9.id`.

**When**
- `result = dao.get_by_order_and_user(db, expense_order_id=O9.id, user_id=U1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### EOA-GU-11 — a W1 row on an order of W2 still blocks a W2 row for that user
- **Rules:** `get_by_order_and_user` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`, but `expense_order_id O9.id`.
2. `X = ExpenseOrderApprover(workspace_id=W2.id, expense_order_id=O9.id, user_id=U1.id, assigned_at=T11)`

**When**
- `db.add(X)`, then `db.flush()`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. raises: `"uq_eo_approver_eo_user" in str(exc.value.orig)`.
4. count: `expense_order_approvers` has exactly 1 row with `expense_order_id == O9.id` and `user_id == U1.id`.
5. unchanged: unchanged(A).

### EOA-GU-12 — a second row for the same order and user is refused
- **Rules:** `get_by_order_and_user` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.
2. `X = ExpenseOrderApprover(workspace_id=W1.id, expense_order_id=O1.id, user_id=U1.id, assigned_at=T11)`

**When**
- `db.add(X)`, then `db.flush()`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. raises: `"uq_eo_approver_eo_user" in str(exc.value.orig)`.
4. count: `expense_order_approvers` has exactly 1 row with `expense_order_id == O1.id` and `user_id == U1.id`.
5. unchanged: unchanged(A).

### EOA-GU-13 — an approved row comes back as stored
- **Rules:** `get_by_order_and_user` R5, R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T11`, but `assigned_by U3.id`, `approved True`, `approved_at T12`.

**When**
- `result = dao.get_by_order_and_user(db, expense_order_id=O1.id, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.workspace_id == W1.id`, `result.expense_order_id == O1.id`, `result.user_id == U1.id`.
3. returns: `result.assigned_by == U3.id`, `result.assigned_at == T11`.
4. returns: `result.approved is True`, `result.approved_at == T12`.

### EOA-GU-14 — the pending row of someone who left the workspace is returned
- **Rules:** `get_by_order_and_user` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. left U2.
2. A = approver, `assigned_at T10`, but `user_id U2.id`.

**When**
- `result = dao.get_by_order_and_user(db, expense_order_id=O1.id, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.approved is False`.

### EOA-GU-15 — the row on a completed order is returned
- **Rules:** `get_by_order_and_user` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order OC has `completed_at T12`: it is a standing row.
2. A = approver, `assigned_at T10`, but `expense_order_id OC.id`.

**When**
- `result = dao.get_by_order_and_user(db, expense_order_id=OC.id, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### EOA-GU-16 — the row on a voided order is returned
- **Rules:** `get_by_order_and_user` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order OV has `voided True`: it is a standing row.
2. A = approver, `assigned_at T10`, but `expense_order_id OV.id`.

**When**
- `result = dao.get_by_order_and_user(db, expense_order_id=OV.id, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### EOA-GU-17 — writes nothing: a pending row stays pending and is not returned
- **Rules:** `get_by_order_and_user` R2, Side effects, Overview
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.
2. `P = ExpenseOrderApprover(workspace_id=W1.id, expense_order_id=O1.id, user_id=U2.id, assigned_at=T11)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_order_and_user(db, expense_order_id=O1.id, user_id=U2.id, workspace_id=W1.id)`.

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

### EOA-GU-18 — writes nothing: a read that finds its row leaves the session as it was
- **Rules:** `get_by_order_and_user` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = approver, `assigned_at T10`.
2. `P = ExpenseOrderApprover(workspace_id=W1.id, expense_order_id=O1.id, user_id=U2.id, assigned_at=T11)`
3. `db.add(P)` (not flushed).

**When**
- `result = dao.get_by_order_and_user(db, expense_order_id=O1.id, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. nothing written: nothing written.

### EOA-GU-19 — the approved row of someone who left the workspace is returned
- **Rules:** `get_by_order_and_user` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. left U2.
2. A = approver, `assigned_at T10`, but `user_id U2.id`, `approved True`, `approved_at T12`.

**When**
- `result = dao.get_by_order_and_user(db, expense_order_id=O1.id, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.approved is True`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_by_order` R2, `get_by_order_and_user` R3 — a row linking two workspaces cannot reach a response; `list_approvers` answers 404 first (HR-16) | `ExpenseOrderManager.list_approvers` | This DAO returns the row for its own workspace; the 404 is what keeps it out of a response. |
| `get_by_order` R7, `get_by_order_and_user` R5 — BUG-1201 (FU-2): removal deletes pending rows on open orders, one `approver_removed` event per order; approved rows and closed orders stay | `WorkspaceManager.remove_member_from_workspace` | The rule and the tag belong to that spec. When its new read is added to this DAO, this file gets cards for it. |
| Generic behavior of inherited `get`, `get_multi`, `get_by_workspace`, `get_by_id_and_workspace`, `create`, `update`, `remove` | `tests/unit/dao/base.spec.md` / `base.cases.md` | No caller on this DAO. Commit spies of the writers: BASE-C-05, BASE-U-12, BASE-R-02. |
| Module singleton `expense_order_approver_dao` | none (no logic) | Only used as the entry point of every card. |
| Notes: keyword-only parameters | none (no rule) | Spec gap 1. |
| FU-1 — `list_approvers` R2 must add the `id` tie-break after BUG-1200 | `ExpenseOrderManager.list_approvers` | Spec text, when next touched. |
| Q1 — an order left with no approver: `required = 1` (BUG-755) | `ExpenseOrderManager.approval_summary` | Logged there. No card here. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Notes ("Every parameter after `db` is keyword-only"), Branch map 11–13, 24–26 | Stated as a note, not as a rule. | No card, as in `machine_activity_event.cases.md`, `machine_item.cases.md`, `item_tag.cases.md`. |
| 2 | Overview ("takes no lock"), Branch map 16–19, 29–33 ("no join") | Each stands outside the numbered rules. | Covered anyway, as Overview rows of the matrix, by the two writes-nothing cards. Drop those lines if they are not meant as a contract. |
| 3 | Model facts | These are not rules of the DAO: defaults, cascades. **Order:** among them, deleting a profile also deletes that person's approval. | No card. No code path deletes a profile, so nothing is lost today; those facts are owned by the schema, not by this DAO. |
| 4 | Model facts, Notes | The spec gives the class names, not their modules. `app.models.expense_order_approver` is the path existing tests import. | Conventions use the path. A wrong one fails at import, in every test. |
| 5 | `get_by_order` R7, `get_by_order_and_user` R5 | **Order.** The membership row's class and columns are not in this spec. `WorkspaceMember` with `role`, `status` comes from `core/deps.spec.md` Notes; its module from existing tests. | The `left` line of Conventions uses them. |
| 6 | `get_by_order` R8, `get_by_order_and_user` R5 | **Order.** The columns are not in this spec: `completed_at` and `voided` come from `expense_order_manager.spec.md`. | EOA-GO and EOA-GU closed-order cards use them. The spec's check set both on one order; here each has its own card. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_order` | Returns | EOA-GO-01 |
| `get_by_order` | R1 | EOA-GO-01, EOA-GO-02 |
| `get_by_order` | R2 | EOA-GO-03, EOA-GO-04, EOA-GO-05 |
| `get_by_order` | R3 | EOA-GO-06, EOA-GO-07, EOA-GO-08, EOA-GO-09 |
| `get_by_order` | R4 | EOA-GO-10, EOA-GO-11, EOA-GO-21 |
| `get_by_order` | R5 | EOA-GO-11 |
| `get_by_order` | R5 [BUG-1200] | EOA-GO-12, EOA-GO-13, EOA-GO-14, EOA-GO-22 |
| `get_by_order` | R6 | EOA-GO-15 |
| `get_by_order` | R7 | EOA-GO-16 |
| `get_by_order` | R8 | EOA-GO-17, EOA-GO-18 |
| `get_by_order` | R9 | EOA-GO-19, EOA-GO-20 |
| `get_by_order` | Overview | EOA-GO-20 |
| `get_by_order` | Side effects | EOA-GO-20 |
| `get_by_order_and_user` | Returns | EOA-GU-01 |
| `get_by_order_and_user` | R1 | EOA-GU-01, EOA-GU-02, EOA-GU-13 |
| `get_by_order_and_user` | R2 | EOA-GU-03, EOA-GU-04, EOA-GU-05, EOA-GU-06, EOA-GU-07, EOA-GU-17 |
| `get_by_order_and_user` | R3 | EOA-GU-08, EOA-GU-09, EOA-GU-10, EOA-GU-11 |
| `get_by_order_and_user` | R4 | EOA-GU-01, EOA-GU-02, EOA-GU-12 |
| `get_by_order_and_user` | R5 | EOA-GU-13, EOA-GU-14, EOA-GU-15, EOA-GU-16, EOA-GU-19 |
| `get_by_order_and_user` | Errors row 1 (the insert's `IntegrityError`) | EOA-GU-12 |
| `get_by_order_and_user` | Overview | EOA-GU-17 |
| `get_by_order_and_user` | Side effects | EOA-GU-17, EOA-GU-18 |
