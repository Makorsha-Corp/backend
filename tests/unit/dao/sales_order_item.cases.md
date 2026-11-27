# Test cases — `app/dao/sales_order_item.py`

> **Spec:** `tests/unit/dao/sales_order_item.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open).
> **Revision:** 1 — the spec did not change. Additive, from `sales_order_item.verify.md` (case-missing Findings 1, 2; recipes R-1, R-2; prose Finding 3): R-1 → SOI-G-18; R-2 → SOI-G-19; Finding 3 → SOI-G-13's `Fails today on` parenthesis reworded per plan. New Then lines are numbered last, so no existing Then number moved. No ID retired.
> **Counts:** 19 cases · 15 expected-to-pass · 4 expected-to-fail (bugs) · 4 deferred

## Reviewer summary
- **Per callable:** `get_by_sales_order` 19 (4 bug).
- **Depth:** lighter target (skill step 1a): one thin read; the module writes no stock, money or order state.
- **Expected-to-fail:** BUG-1270 4: SOI-G-12, SOI-G-13, SOI-G-19 non-strict, SOI-G-14 strict (the SQL recorder).
- **Commit spies:** none, the module has no writer of its own.
- **Notable design choices:** every passing card compares a set, because today's order is not fixed. `get_by_item` has no cards: dead code (Q1). No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Revision 1:** SOI-G-18 (an unflushed edit stays unflushed); SOI-G-19 (tied rows differ in price, so a price key fails). SOI-G-13's parenthesis now names the plans.
- **Needs a decision:** None blocking. See the **Order** rows of Spec gaps.

## Conventions for this module

**IDs.** `SOI` = `app/dao/sales_order_item.py`. `G` get_by_sales_order.

**Actors and fixed values.**
- `dao` = the singleton `sales_order_item_dao` (`from app.dao.sales_order_item import sales_order_item_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `SalesOrderItem` = `app.models.sales_order_item.SalesOrderItem`. `Account`, `Factory`, `Status`, `SalesOrder`, `Item` come from `app.models.account`, `.factory`, `.status`, `.sales_order`, `.item`. `Decimal` = `decimal.Decimal`. `date` = `datetime.date`.
- MISSING = `999999999`: an id that no row of any table has.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line (workspaces and the profile from `make_workspace`, `make_profile`; the rest built directly, add + flush):
  - W1, W2 = two `workspaces` rows. U1 = a `profiles` row.
  - AC1 = `Account(workspace_id=W1.id, name="Acme")`. F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`. S1 = `Status(workspace_id=W1.id, name="Draft", comment="Stage")`.
  - SO1 = `SalesOrder(workspace_id=W1.id, sales_order_number="SO-T-001", account_id=AC1.id, factory_id=F1.id, order_date=date(2026, 3, 1), total_amount=0, current_status_id=S1.id, created_by=U1.id)`. SO2 = the same, but `sales_order_number "SO-T-002"`.
  - IR = `Item(workspace_id=W1.id, name="Old Gasket", name_normalized="old gasket", unit="pcs", is_active=False)`.
- **line** = `sales_order_items` row built with `SalesOrderItem`: `workspace_id W1.id`, `sales_order_id SO1.id`, `description "Line"`, `quantity_ordered Decimal("1.00")`, `unit_price Decimal("2.00")`, `line_total Decimal("2.00")`; `item_id` is not passed. After the word "but" the card lists every other column that differs. `description None` means the keyword is passed with the value `None`.
- No `sales_order_items` row exists unless the card's Given lists it.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending. "it is a standing row" means that row is not inserted again; the line only says what it holds.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the number of `sales_order_items` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P and the session after the call, before anything expires it: `db.new`, `db.dirty`, `db.deleted` as the session holds them. A card lists them ahead of its `nothing written:` and `unchanged:` lines; keep that order.
- Passing cards of this module never compare an order: the query has none today (BUG-1270). They compare a set.
- `raises: TypeError` = plain `with pytest.raises(TypeError):` around the call.

**xfail cards.** Write the call and the checks exactly as shown. `Expect: xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `xfail BUG-n (non-strict)` = `strict=False`, for a card comparing an order that rests on physical row order. The assertion of a non-strict card is never weakened. Bugs here: BUG-1270.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `sales_order_items`; `order_part` = the text of `sql` after its first `ORDER BY` (`""` when there is none); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `DAOSalesOrderItem.get_by_sales_order`

### SOI-G-01 — returns a list of the order's lines
- **Rules:** `get_by_sales_order` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line.
2. B = line.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `len(result) == 2`.
3. returns: `set(ids(result)) == {A.id, B.id}`.
4. returns: `isinstance(result[0], SalesOrderItem)`.

### SOI-G-02 — a line of another order of the same workspace is not returned, though it sorts first
- **Rules:** `get_by_sales_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B = line, but `sales_order_id SO2.id`.
2. A = line.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### SOI-G-03 — the right order under another workspace returns an empty list
- **Rules:** `get_by_sales_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### SOI-G-04 — an unknown workspace returns an empty list
- **Rules:** `get_by_sales_order` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### SOI-G-05 — a W2 row on a W1 order is returned for W2: only the row's workspace is compared
- **Rules:** `get_by_sales_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### SOI-G-06 — a W2 row on a W1 order is not returned for W1, though it sorts first
- **Rules:** `get_by_sales_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B = line, but `workspace_id W2.id`.
2. A = line.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### SOI-G-07 — an unknown order id returns an empty list
- **Rules:** `get_by_sales_order` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### SOI-G-08 — order id 0 returns an empty list
- **Rules:** `get_by_sales_order` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### SOI-G-09 — an order with no rows returns an empty list
- **Rules:** `get_by_sales_order` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### SOI-G-10 — a free-text line is returned, with its description as item_name
- **Rules:** `get_by_sales_order` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line, but `description "Custom bracket"`.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].item_id is None`.
3. returns: `result[0].item_name == "Custom bracket"`.

### SOI-G-11 — a line on an inactive item is returned, with that item's name
- **Rules:** `get_by_sales_order` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Item IR has `is_active False`: it is a standing row.
2. A = line, but `item_id IR.id`, `description None`.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].item_id == IR.id`.
3. returns: `result[0].item_name == "Old Gasket"`.

### SOI-G-12 — rows come back by id ascending, when the lowest id was updated
- **Rules:** `get_by_sales_order` R3 [BUG-1270]
- **Kind:** bug
- **Expect:** xfail BUG-1270 (non-strict)
- **Fails today on:** Then 2 (no order is requested; the updated lowest id comes last, but that rests on physical row order)

**Given**
1. A = line, but `description "Zeta"`.
2. B = line, but `description "Mid"`.
3. C = line, but `description "Alpha"`.
4. `A.quantity_ordered = Decimal("3.00")`, then `db.flush()`.
5. `db.expire_all()`.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### SOI-G-13 — rows come back by id ascending, with no update
- **Rules:** `get_by_sales_order` R3 [BUG-1270]
- **Kind:** bug
- **Expect:** xfail BUG-1270 (non-strict)
- **Fails today on:** Then 2 (no order is requested; the result rests on the query plan: with the `items` join it usually fails on the default plan and with index scans off, and passes with sequential scans off)

**Given**
1. A = line, but `description "Zeta"`.
2. B = line, but `description "Mid"`.
3. C = line, but `description "Alpha"`.
4. `db.expire_all()`.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### SOI-G-14 — the query orders by id ascending
- **Rules:** `get_by_sales_order` R3 [BUG-1270]
- **Kind:** bug
- **Expect:** xfail BUG-1270
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = line.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.

### SOI-G-15 — there is no cap: 103 lines give 103 rows
- **Rules:** `get_by_sales_order` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 103 lines E1 … E103, built with `add_all`. `in_order` = their ids, in that order.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 103`.
2. returns: `set(ids(result)) == set(in_order)`.

### SOI-G-16 — a positional `sales_order_id` raises TypeError
- **Rules:** `get_by_sales_order` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `dao.get_by_sales_order(db, SO1.id, workspace_id=W1.id)`.

**Then**
1. raises: `TypeError`.
2. nothing written: nothing written.

### SOI-G-17 — writes nothing: a pending row stays pending and alone in the session
- **Rules:** `get_by_sales_order` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line.
2. `P = SalesOrderItem(workspace_id=W1.id, sales_order_id=SO1.id, description="Line", quantity_ordered=Decimal("1.00"), unit_price=Decimal("2.00"), line_total=Decimal("2.00"))`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO1.id, workspace_id=W1.id)`.

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
10. statement: `"sales_orders" not in sql`.
11. nothing written: nothing written.
12. unchanged: unchanged(A).

### SOI-G-18 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded
- **Rules:** `get_by_sales_order` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line.
2. B = line, but `sales_order_id SO2.id`.
3. `B.description = "Edited"` (not flushed).

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `B in db.dirty`.
3. pending: `len(db.dirty) == 1`.
4. pending: `B.description == "Edited"`.

### SOI-G-19 — rows come back by id ascending, when price would sort the other way
- **Rules:** `get_by_sales_order` R3 [BUG-1270]
- **Kind:** bug
- **Expect:** xfail BUG-1270 (non-strict)
- **Fails today on:** Then 2 (no order is requested; the result rests on the query plan)

**Given**
1. A = line, but `unit_price Decimal("9.00")`, `line_total Decimal("9.00")`.
2. B = line, but `unit_price Decimal("1.00")`, `line_total Decimal("1.00")`.
3. `db.expire_all()`.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Review, HR-16 — line 332 of `sales_manager.py` uses the unscoped inherited `get`, with an id from a row already scoped | `SalesManager` | **Order.** Scoping is the manager's. |
| Overview — inherited `create`, `get_by_id_and_workspace`, `get` | `tests/unit/dao/base.spec.md` | Generic behavior, not repeated. |
| `get_by_item` (Q1) | `docs/testing/dead-code-removal-checklist.md` | Dead code to be removed. No card. |
| Module singleton | none (no logic) | Only used as the entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `get_by_sales_order` R5 | **Order.** The spec names no column for an inactive item: `is_active` comes from `machine_item_ledger.cases.md` Conventions. `item_name` is not defined for a line with both `item_id` and `description`. | The card builds the item line with `description None`, so that shape is not decided here. |
| 2 | Model facts | **Order.** `item` loads by a join, so `"JOIN" not in sql` cannot be used here, and the spec names no other joined relation. | The writes-nothing card forbids `sales_orders` by name only. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_sales_order` | Returns | SOI-G-01 |
| `get_by_sales_order` | R1 | SOI-G-01, SOI-G-02, SOI-G-03, SOI-G-04, SOI-G-05, SOI-G-06, SOI-G-10 |
| `get_by_sales_order` | R2 | SOI-G-07, SOI-G-08, SOI-G-09 |
| `get_by_sales_order` | R3 [BUG-1270] | SOI-G-12, SOI-G-13, SOI-G-14, SOI-G-19 |
| `get_by_sales_order` | R4 | SOI-G-15 |
| `get_by_sales_order` | R5 | SOI-G-11 |
| `get_by_sales_order` | R6 | SOI-G-16 |
| `get_by_sales_order` | Side effects | SOI-G-17, SOI-G-18 |
