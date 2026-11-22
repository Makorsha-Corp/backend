# Test cases — `app/dao/work_order_item.py`

> **Spec:** `tests/unit/dao/work_order_item.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open).
> **Revision:** 1 — the spec did not change. Additive, from `work_order_item.verify.md` (case-missing Findings 1 … 4; recipes R-1 … R-4; prose Finding 5): R-1 → WOI-I-06; R-2 → WOI-I-07; R-3 → WOI-G-23, WOI-I-08; R-4 → Conventions: WOD gains `deleted_at T12`, `deleted_by U1.id`; WOI-G-20's Given line says so; Finding 5 → WOI-G-16's `Fails today on` parenthesis reworded per plan. New Then lines are numbered last, so no existing Then number moved. No ID retired.
> **Counts:** 31 cases · 28 expected-to-pass · 3 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Per callable:** `get_by_work_order` 23 (3 bug) · `get_by_id_and_workspace` 8.
- **Depth:** lighter target (skill step 1a): two thin reads; the module writes no stock, money or order state. Its reader feeds stock posting, and that is the manager's.
- **Expected-to-fail:** BUG-1272 3: WOI-G-16, WOI-G-17 non-strict, WOI-G-18 strict (the SQL recorder).
- **Commit spies:** none. Both methods only read; the inherited writers are spied by BASE-C-05, BASE-U-12.
- **Notable design choices:** every passing card compares a set, because today's order is not fixed. The soft-deleted line carries `is_deleted`, `deleted_at`, `deleted_by`, as `remove_item` writes them, and sorts ahead of the live row. Each named value of `include_deleted` has its own card. No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Revision 1:** WOI-I-06, WOI-I-07 (by-id read: another workspace's line at the earlier id; a line of WOD, with no `work_orders` in the statement); WOI-G-23, WOI-I-08 (an unflushed edit stays unflushed). WOD now carries every column of the real close.
- **Needs a decision:** None blocking. See the **Order** and **Stock** rows of Spec gaps and Deferred.

## Conventions for this module

**IDs.** `WOI` = `app/dao/work_order_item.py`. `G` get_by_work_order · `I` get_by_id_and_workspace.

**Actors and fixed values.**
- `dao` = the singleton `work_order_item_dao` (`from app.dao.work_order_item import work_order_item_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `WorkOrderItem` = `app.models.work_order_item.WorkOrderItem`. `Factory`, `Item`, `WorkOrderType`, `WorkOrder` come from `app.models.factory`, `.item`, `.work_order_type`, `.work_order`. `Decimal` = `decimal.Decimal`. `datetime` = the `datetime` module's class.
- MISSING = `999999999`: an id that no row of any table has.
- T12 = `datetime(2026, 3, 4, 12, 0, 0)`.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line (workspaces and the profile from `make_workspace`, `make_profile`; the rest built directly, add + flush):
  - W1, W2 = two `workspaces` rows. U1 = a `profiles` row.
  - F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`. I1 = `Item(workspace_id=W1.id, name="Bolt", name_normalized="bolt", unit="pcs")`. I2 = the same, but `name "Nut"`, `name_normalized "nut"`. WT1 = `WorkOrderType(workspace_id=W1.id, name="Repair")`.
  - WO1 = `WorkOrder(workspace_id=W1.id, work_order_number="WO-T-001", title="Order One", factory_id=F1.id, work_order_type_id=WT1.id, created_by=U1.id)`. WO2 = the same, but `work_order_number "WO-T-002"`. WOD = the same, but `work_order_number "WO-T-003"`, `is_deleted True`, `is_active False`, `deleted_at T12`, `deleted_by U1.id`.
- **line** = `work_order_items` row built with `WorkOrderItem`: `workspace_id W1.id`, `work_order_id WO1.id`, `item_id I1.id`, `quantity Decimal("1.00")`. After the word "but" the card lists every other column that differs.
- No `work_order_items` row exists unless the card's Given lists it.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending. "it is a standing row" means that row is not inserted again; the line only says what it holds.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the number of `work_order_items` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P and the session after the call, before anything expires it: `db.new`, `db.dirty`, `db.deleted` as the session holds them. A card lists them ahead of its `nothing written:` and `unchanged:` lines; keep that order.
- Passing cards of this module never compare an order: the query has none today (BUG-1272). They compare a set.
- `raises: TypeError` = plain `with pytest.raises(TypeError):` around the call.

**xfail cards.** Write the call and the checks exactly as shown. `Expect: xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `xfail BUG-n (non-strict)` = `strict=False`, for a card comparing an order that rests on physical row order. The assertion of a non-strict card is never weakened. Bugs here: BUG-1272.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `work_order_items`; `order_part` = the text of `sql` after its first `ORDER BY` (`""` when there is none); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `WorkOrderItemDAO.get_by_work_order`

### WOI-G-01 — returns a list of the order's lines
- **Rules:** `get_by_work_order` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line.
2. B = line.

**When**
- `result = dao.get_by_work_order(db, work_order_id=WO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `len(result) == 2`.
3. returns: `set(ids(result)) == {A.id, B.id}`.
4. returns: `isinstance(result[0], WorkOrderItem)`.

### WOI-G-02 — a line of another order of the same workspace is not returned, though it sorts first
- **Rules:** `get_by_work_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B = line, but `work_order_id WO2.id`.
2. A = line.

**When**
- `result = dao.get_by_work_order(db, work_order_id=WO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WOI-G-03 — the right order under another workspace returns an empty list
- **Rules:** `get_by_work_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line.

**When**
- `result = dao.get_by_work_order(db, work_order_id=WO1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### WOI-G-04 — an unknown workspace returns an empty list
- **Rules:** `get_by_work_order` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line.

**When**
- `result = dao.get_by_work_order(db, work_order_id=WO1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### WOI-G-05 — a W2 row on a W1 order is returned for W2: only the row's workspace is compared
- **Rules:** `get_by_work_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_work_order(db, work_order_id=WO1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WOI-G-06 — a W2 row on a W1 order is not returned for W1, though it sorts first
- **Rules:** `get_by_work_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B = line, but `workspace_id W2.id`.
2. A = line.

**When**
- `result = dao.get_by_work_order(db, work_order_id=WO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WOI-G-07 — an unknown order id returns an empty list
- **Rules:** `get_by_work_order` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line.

**When**
- `result = dao.get_by_work_order(db, work_order_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### WOI-G-08 — order id 0 returns an empty list
- **Rules:** `get_by_work_order` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line.

**When**
- `result = dao.get_by_work_order(db, work_order_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### WOI-G-09 — an order with no rows returns an empty list
- **Rules:** `get_by_work_order` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line.

**When**
- `result = dao.get_by_work_order(db, work_order_id=WO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### WOI-G-10 — left out, include_deleted hides a soft-deleted line that sorts first
- **Rules:** `get_by_work_order` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. B = line, but `is_deleted True`, `deleted_at T12`, `deleted_by U1.id`.
2. A = line.

**When**
- `result = dao.get_by_work_order(db, work_order_id=WO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WOI-G-11 — include_deleted=False hides a soft-deleted line that sorts first
- **Rules:** `get_by_work_order` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. B = line, but `is_deleted True`, `deleted_at T12`, `deleted_by U1.id`.
2. A = line.

**When**
- `result = dao.get_by_work_order(db, work_order_id=WO1.id, workspace_id=W1.id, include_deleted=False)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WOI-G-12 — include_deleted=None acts as False
- **Rules:** `get_by_work_order` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. B = line, but `is_deleted True`, `deleted_at T12`, `deleted_by U1.id`.
2. A = line.

**When**
- `result = dao.get_by_work_order(db, work_order_id=WO1.id, workspace_id=W1.id, include_deleted=None)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WOI-G-13 — an order with only soft-deleted lines returns an empty list
- **Rules:** `get_by_work_order` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. B = line, but `is_deleted True`, `deleted_at T12`, `deleted_by U1.id`.

**When**
- `result = dao.get_by_work_order(db, work_order_id=WO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### WOI-G-14 — include_deleted=True returns soft-deleted lines with the live ones
- **Rules:** `get_by_work_order` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. B = line, but `is_deleted True`, `deleted_at T12`, `deleted_by U1.id`.
2. A = line.

**When**
- `result = dao.get_by_work_order(db, work_order_id=WO1.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `set(ids(result)) == {A.id, B.id}`.

### WOI-G-15 — include_deleted=True still keeps to that order and workspace
- **Rules:** `get_by_work_order` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B = line, but `is_deleted True`, `deleted_at T12`, `deleted_by U1.id`, `work_order_id WO2.id`.
2. C = line, but `is_deleted True`, `deleted_at T12`, `deleted_by U1.id`, `workspace_id W2.id`.
3. A = line, but `is_deleted True`, `deleted_at T12`, `deleted_by U1.id`.

**When**
- `result = dao.get_by_work_order(db, work_order_id=WO1.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WOI-G-16 — rows come back by id ascending, when the lowest id was updated
- **Rules:** `get_by_work_order` R5 [BUG-1272]
- **Kind:** bug
- **Expect:** xfail BUG-1272 (non-strict)
- **Fails today on:** Then 2 (no order is requested; the result rests on the query plan: the updated lowest id usually comes last on the default plan, and not with index or sequential scans forced off)

**Given**
1. A = line, but `quantity Decimal("9.00")`, `item_id I2.id`.
2. B = line, but `quantity Decimal("1.00")`.
3. `A.quantity = Decimal("3.00")`, then `db.flush()`.
4. `db.expire_all()`.

**When**
- `result = dao.get_by_work_order(db, work_order_id=WO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### WOI-G-17 — rows come back by id ascending, with no update
- **Rules:** `get_by_work_order` R5 [BUG-1272]
- **Kind:** bug
- **Expect:** xfail BUG-1272 (non-strict)
- **Fails today on:** Then 2 (no order is requested; physical order usually gives the intended result, which is why this card is non-strict)

**Given**
1. A = line, but `quantity Decimal("9.00")`, `item_id I2.id`.
2. B = line, but `quantity Decimal("1.00")`.
3. `db.expire_all()`.

**When**
- `result = dao.get_by_work_order(db, work_order_id=WO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### WOI-G-18 — the query orders by id ascending
- **Rules:** `get_by_work_order` R5 [BUG-1272]
- **Kind:** bug
- **Expect:** xfail BUG-1272
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = line.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_work_order(db, work_order_id=WO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.

### WOI-G-19 — there is no cap: 101 lines give 101 rows
- **Rules:** `get_by_work_order` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 lines E1 … E101, built with `add_all`. `in_order` = their ids, in that order.

**When**
- `result = dao.get_by_work_order(db, work_order_id=WO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `set(ids(result)) == set(in_order)`.

### WOI-G-20 — the live lines of a soft-deleted order are returned
- **Rules:** `get_by_work_order` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Order WOD has `is_deleted True`, `is_active False`, `deleted_at T12`, `deleted_by U1.id`: it is a standing row.
2. A = line, but `work_order_id WOD.id`.

**When**
- `result = dao.get_by_work_order(db, work_order_id=WOD.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WOI-G-21 — a positional `work_order_id` raises TypeError
- **Rules:** `get_by_work_order` R8
- **Kind:** error
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `dao.get_by_work_order(db, WO1.id, workspace_id=W1.id)`.

**Then**
1. raises: `TypeError`.
2. nothing written: nothing written.

### WOI-G-22 — writes nothing: a pending row stays pending and alone in the session
- **Rules:** `get_by_work_order` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line.
2. `P = WorkOrderItem(workspace_id=W1.id, work_order_id=WO1.id, item_id=I1.id, quantity=Decimal("1.00"))`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_work_order(db, work_order_id=WO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. statement: `len(selects) == 1`.
9. statement: `"FOR UPDATE" not in sql.upper()`.
10. statement: `"work_orders" not in sql`.
11. nothing written: nothing written.
12. unchanged: unchanged(A).

### WOI-G-23 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded
- **Rules:** `get_by_work_order` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line.
2. B = line, but `work_order_id WO2.id`.
3. `B.quantity = Decimal("5.00")` (not flushed).

**When**
- `result = dao.get_by_work_order(db, work_order_id=WO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `B in db.dirty`.
3. pending: `len(db.dirty) == 1`.
4. pending: `B.quantity == Decimal("5.00")`.


## `WorkOrderItemDAO.get_by_id_and_workspace`

### WOI-I-01 — returns the line of that id, not the first line
- **Rules:** `get_by_id_and_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line.
2. B = line.

**When**
- `result = dao.get_by_id_and_workspace(db, id=B.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == B.id`.
2. returns: `isinstance(result, WorkOrderItem)`.

### WOI-I-02 — another workspace returns None
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### WOI-I-03 — an unknown id returns None and nothing is created
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### WOI-I-04 — a soft-deleted line is returned
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = line, but `is_deleted True`, `deleted_at T12`, `deleted_by U1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.is_deleted is True`.

### WOI-I-05 — writes nothing: a read that finds its line leaves the session as it was
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line.
2. `P = WorkOrderItem(workspace_id=W1.id, work_order_id=WO1.id, item_id=I1.id, quantity=Decimal("1.00"))`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. statement: `len(selects) == 1`.
9. statement: `"FOR UPDATE" not in sql.upper()`.
10. nothing written: nothing written.
11. unchanged: unchanged(A).

### WOI-I-06 — a W2 line at the earlier id is not returned for W1
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = line, but `workspace_id W2.id`.
2. A = line.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### WOI-I-07 — a line of a soft-deleted order is returned, and the order is not joined
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Order WOD has `is_deleted True`, `is_active False`, `deleted_at T12`, `deleted_by U1.id`: it is a standing row.
2. A = line, but `work_order_id WOD.id`.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. statement: `"work_orders" not in sql`.

### WOI-I-08 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line.
2. B = line.
3. `B.quantity = Decimal("5.00")` (not flushed).

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `B in db.dirty`.
3. pending: `len(db.dirty) == 1`.
4. pending: `B.quantity == Decimal("5.00")`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Review, HR-4 — BUG-1273: `GET /work-orders/{id}/items/` accepts `include_deleted` | `WorkOrderManager.get_items`, the endpoint (spec FU-1 (b)) | **Order.** The rule of this DAO does not change; the tag belongs to that spec. |
| `get_by_work_order` R7 — BUG-1279: a soft-deleted order is hidden by `get_work_order` | `WorkOrderManager.get_work_order` (spec FU-1 (a)) | **Order.** This DAO returns those lines by rule. |
| `get_by_work_order` R5 — which line posts first at start | `WorkOrderManager` stock posting steps | **Stock.** BUG-1272 fixes the order here; the posting is the manager's. |
| `get_by_id_and_workspace` R1 — a soft-deleted line is refused with 404 `Work order item not found` | `WorkOrderManager.update_item`, `remove_item` | **Order.** Both callers refuse it themselves. |
| Review, HR-16 — BUG-1016: cross-workspace item ids on writes | `WorkOrderManager` | **Order.** This read follows the row. |
| Overview — inherited `create`, `update` | `tests/unit/dao/base.spec.md` | Generic behavior, not repeated. |
| Module singleton | none (no logic) | Only used as the entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `get_by_work_order` R7 | **Order.** The spec names no soft-delete column for the order. `is_deleted`, `is_active` come from `work_order_approver.cases.md`, `work_order_event.spec.md` R4. | The WOD row uses them. **Closed in revision 1:** `deleted_at`, `deleted_by` added from `work_order_item.verify.md` Finding 4. |
| 2 | Notes | **Order.** `WorkOrder(...)` in Notes has no `created_by`; `work_order_approver.cases.md` passes one. | Conventions pass `created_by U1.id`. |
| 3 | `get_by_work_order` R3 | "Any falsy value" names only `None`. | Cards use `None`, `False` and the default; no card for `0` or `""`. |
| 4 | Model facts | **Stock.** `uses_inventory`, `action_type` defaults are not rules of the DAO, and `item`, `replaced_item` load joined. | No card for the defaults. `"JOIN" not in sql` cannot be used, so the writes-nothing card forbids `work_orders` by name. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_work_order` | Returns | WOI-G-01 |
| `get_by_work_order` | R1 | WOI-G-01, WOI-G-02, WOI-G-03, WOI-G-04, WOI-G-05, WOI-G-06 |
| `get_by_work_order` | R2 | WOI-G-07, WOI-G-08, WOI-G-09 |
| `get_by_work_order` | R3 | WOI-G-10, WOI-G-11, WOI-G-12, WOI-G-13 |
| `get_by_work_order` | R4 | WOI-G-14, WOI-G-15 |
| `get_by_work_order` | R5 [BUG-1272] | WOI-G-16, WOI-G-17, WOI-G-18 |
| `get_by_work_order` | R6 | WOI-G-19 |
| `get_by_work_order` | R7 | WOI-G-20 |
| `get_by_work_order` | R8 | WOI-G-21 |
| `get_by_work_order` | Side effects | WOI-G-22, WOI-G-23 |
| `get_by_id_and_workspace` | Returns | WOI-I-01 |
| `get_by_id_and_workspace` | R1 | WOI-I-01, WOI-I-02, WOI-I-03, WOI-I-04, WOI-I-06, WOI-I-07 |
| `get_by_id_and_workspace` | Side effects | WOI-I-05, WOI-I-08 |
