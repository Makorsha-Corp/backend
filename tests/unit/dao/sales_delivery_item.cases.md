# Test cases — `app/dao/sales_delivery_item.py`

> **Spec:** `tests/unit/dao/sales_delivery_item.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open).
> **Revision:** 1 — the spec did not change. Additive, from `sales_delivery_item.verify.md` (case-missing Finding 1; recipe R-1): R-1 → SDI-G-17. New Then lines are numbered last, so no existing Then number moved. No ID retired.
> **Counts:** 17 cases · 14 expected-to-pass · 3 expected-to-fail (bugs) · 4 deferred

## Reviewer summary
- **Per callable:** `get_by_delivery` 17 (3 bug).
- **Depth:** lighter target (skill step 1a): one thin read; the module writes no stock, money or order state. Its reader feeds stock posting, and that is the sales manager's.
- **Expected-to-fail:** BUG-1271 3: SDI-G-11, SDI-G-12 non-strict (physical order lies both ways), SDI-G-13 strict (the SQL recorder).
- **Commit spies:** none, the module has no writer of its own.
- **Notable design choices:** every passing card compares a set, because today's order is not fixed. No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Revision 1:** SDI-G-17: an unflushed edit of another line stays unflushed.
- **Needs a decision:** None blocking. See the **Order** rows of Spec gaps.

## Conventions for this module

**IDs.** `SDI` = `app/dao/sales_delivery_item.py`. `G` get_by_delivery.

**Actors and fixed values.**
- `dao` = the singleton `sales_delivery_item_dao` (`from app.dao.sales_delivery_item import sales_delivery_item_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `SalesDeliveryItem` = `app.models.sales_delivery_item.SalesDeliveryItem`. `Account`, `Factory`, `Status`, `SalesOrder`, `SalesOrderItem`, `SalesDelivery` come from `app.models.account`, `.factory`, `.status`, `.sales_order`, `.sales_order_item`, `.sales_delivery`. `Decimal` = `decimal.Decimal`. `date` = `datetime.date`.
- MISSING = `999999999`: an id that no row of any table has.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line (workspaces and the profile from `make_workspace`, `make_profile`; the rest built directly, add + flush):
  - W1, W2 = two `workspaces` rows. U1 = a `profiles` row.
  - AC1 = `Account(workspace_id=W1.id, name="Acme")`. F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`. S1 = `Status(workspace_id=W1.id, name="Draft", comment="Stage")`.
  - SO1 = `SalesOrder(workspace_id=W1.id, sales_order_number="SO-T-001", account_id=AC1.id, factory_id=F1.id, order_date=date(2026, 3, 1), total_amount=0, current_status_id=S1.id, created_by=U1.id)`. SO2 = the same, but `sales_order_number "SO-T-002"`.
  - L1 = `SalesOrderItem(workspace_id=W1.id, sales_order_id=SO1.id, description="Line", quantity_ordered=Decimal("5.00"), unit_price=Decimal("2.00"), line_total=Decimal("10.00"))`.
  - D1 = `SalesDelivery(workspace_id=W1.id, sales_order_id=SO1.id, delivery_number="SD-T-001", delivery_status="planned", created_by=U1.id)`. D2 = the same, but `delivery_number "SD-T-002"`.
- **line** = `sales_delivery_items` row built with `SalesDeliveryItem`: `workspace_id W1.id`, `delivery_id D1.id`, `sales_order_item_id L1.id`, `quantity_delivered Decimal("1.00")`; `item_id`, `notes` are not passed. After the word "but" the card lists every other column that differs.
- No `sales_delivery_items` row exists unless the card's Given lists it.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending. "it is a standing row" means that row is not inserted again; the line only says what it holds.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the number of `sales_delivery_items` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P and the session after the call, before anything expires it: `db.new`, `db.dirty`, `db.deleted` as the session holds them. A card lists them ahead of its `nothing written:` and `unchanged:` lines; keep that order.
- Passing cards of this module never compare an order: the query has none today (BUG-1271). They compare a set.
- `raises: TypeError` = plain `with pytest.raises(TypeError):` around the call.

**xfail cards.** Write the call and the checks exactly as shown. `Expect: xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `xfail BUG-n (non-strict)` = `strict=False`, for a card comparing an order that rests on physical row order. The assertion of a non-strict card is never weakened. Bugs here: BUG-1271.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `sales_delivery_items`; `order_part` = the text of `sql` after its first `ORDER BY` (`""` when there is none); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `DAOSalesDeliveryItem.get_by_delivery`

### SDI-G-01 — returns a list of the delivery's lines
- **Rules:** `get_by_delivery` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line.
2. B = line.

**When**
- `result = dao.get_by_delivery(db, delivery_id=D1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `len(result) == 2`.
3. returns: `set(ids(result)) == {A.id, B.id}`.
4. returns: `isinstance(result[0], SalesDeliveryItem)`.

### SDI-G-02 — a line of another delivery of the same workspace is not returned, though it sorts first
- **Rules:** `get_by_delivery` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B = line, but `delivery_id D2.id`.
2. A = line.

**When**
- `result = dao.get_by_delivery(db, delivery_id=D1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### SDI-G-03 — the right delivery under another workspace returns an empty list
- **Rules:** `get_by_delivery` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line.

**When**
- `result = dao.get_by_delivery(db, delivery_id=D1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### SDI-G-04 — an unknown workspace returns an empty list
- **Rules:** `get_by_delivery` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line.

**When**
- `result = dao.get_by_delivery(db, delivery_id=D1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### SDI-G-05 — a W2 row on a W1 delivery is returned for W2: only the row's workspace is compared
- **Rules:** `get_by_delivery` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_delivery(db, delivery_id=D1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### SDI-G-06 — a W2 row on a W1 delivery is not returned for W1, though it sorts first
- **Rules:** `get_by_delivery` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B = line, but `workspace_id W2.id`.
2. A = line.

**When**
- `result = dao.get_by_delivery(db, delivery_id=D1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### SDI-G-07 — an unknown delivery id returns an empty list
- **Rules:** `get_by_delivery` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line.

**When**
- `result = dao.get_by_delivery(db, delivery_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### SDI-G-08 — delivery id 0 returns an empty list
- **Rules:** `get_by_delivery` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line.

**When**
- `result = dao.get_by_delivery(db, delivery_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### SDI-G-09 — a delivery with no rows returns an empty list
- **Rules:** `get_by_delivery` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line.

**When**
- `result = dao.get_by_delivery(db, delivery_id=D2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### SDI-G-10 — a line comes back as stored, a free-text line included
- **Rules:** `get_by_delivery` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line, but `quantity_delivered Decimal("2.50")`, `notes "Gate 3"`.

**When**
- `result = dao.get_by_delivery(db, delivery_id=D1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].delivery_id == D1.id`, `result[0].sales_order_item_id == L1.id`.
3. returns: `result[0].quantity_delivered == Decimal("2.50")`, `result[0].notes == "Gate 3"`, `result[0].item_id is None`.

### SDI-G-11 — rows come back by id ascending, when the lowest id was updated
- **Rules:** `get_by_delivery` R3 [BUG-1271]
- **Kind:** bug
- **Expect:** xfail BUG-1271 (non-strict)
- **Fails today on:** Then 2 (no order is requested; the updated lowest id comes last, but that rests on physical row order)

**Given**
1. A = line, but `notes "Zeta"`.
2. B = line, but `notes "Alpha"`.
3. `A.quantity_delivered = Decimal("3.00")`, then `db.flush()`.
4. `db.expire_all()`.

**When**
- `result = dao.get_by_delivery(db, delivery_id=D1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### SDI-G-12 — rows come back by id ascending, with no update
- **Rules:** `get_by_delivery` R3 [BUG-1271]
- **Kind:** bug
- **Expect:** xfail BUG-1271 (non-strict)
- **Fails today on:** Then 2 (no order is requested; physical order usually gives the intended result, which is why this card is non-strict)

**Given**
1. A = line, but `notes "Zeta"`.
2. B = line, but `notes "Alpha"`.
3. `db.expire_all()`.

**When**
- `result = dao.get_by_delivery(db, delivery_id=D1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### SDI-G-13 — the query orders by id ascending
- **Rules:** `get_by_delivery` R3 [BUG-1271]
- **Kind:** bug
- **Expect:** xfail BUG-1271
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = line.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_delivery(db, delivery_id=D1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.

### SDI-G-14 — there is no cap: 101 lines give 101 rows
- **Rules:** `get_by_delivery` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 lines E1 … E101, built with `add_all`. `in_order` = their ids, in that order.

**When**
- `result = dao.get_by_delivery(db, delivery_id=D1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `set(ids(result)) == set(in_order)`.

### SDI-G-15 — a positional `delivery_id` raises TypeError
- **Rules:** `get_by_delivery` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `dao.get_by_delivery(db, D1.id, workspace_id=W1.id)`.

**Then**
1. raises: `TypeError`.
2. nothing written: nothing written.

### SDI-G-16 — writes nothing: a pending row stays pending and alone in the session
- **Rules:** `get_by_delivery` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line.
2. `P = SalesDeliveryItem(workspace_id=W1.id, delivery_id=D1.id, sales_order_item_id=L1.id, quantity_delivered=Decimal("1.00"))`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_delivery(db, delivery_id=D1.id, workspace_id=W1.id)`.

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
10. statement: `"sales_deliveries" not in sql`.
11. nothing written: nothing written.
12. unchanged: unchanged(A).

### SDI-G-17 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded
- **Rules:** `get_by_delivery` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line.
2. B = line, but `delivery_id D2.id`.
3. `B.notes = "Edited"` (not flushed).

**When**
- `result = dao.get_by_delivery(db, delivery_id=D1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `B in db.dirty`.
3. pending: `len(db.dirty) == 1`.
4. pending: `B.notes == "Edited"`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Review, HR-16 — a delivery line from another order (BUG-723) | `SalesManager.create_delivery_with_items` | **Order.** The write is the manager's; this read follows the row. |
| Review, HR-10 — check-then-write on completion | `SalesManager.complete_delivery` | **Stock.** Posting and its lock are the manager's; it reads these lines through this DAO. |
| Overview — inherited `create` | `tests/unit/dao/base.spec.md` | Generic behavior, not repeated. |
| Module singleton | none (no logic) | Only used as the entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Notes | **Order.** `SalesDelivery(...)` needs a `delivery_status` and the spec gives no value. `"planned"` comes from `tests/unit/managers/sales_manager.cases.md`. | Conventions use it. |
| 2 | Model facts | **Order.** The spec does not say which relations of the model load joined. | The writes-nothing card forbids only `sales_deliveries` in the statement, not `JOIN`. If that relation does load joined, the line is what is wrong, not the code. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_delivery` | Returns | SDI-G-01 |
| `get_by_delivery` | R1 | SDI-G-01, SDI-G-02, SDI-G-03, SDI-G-04, SDI-G-05, SDI-G-06, SDI-G-10 |
| `get_by_delivery` | R2 | SDI-G-07, SDI-G-08, SDI-G-09 |
| `get_by_delivery` | R3 [BUG-1271] | SDI-G-11, SDI-G-12, SDI-G-13 |
| `get_by_delivery` | R4 | SDI-G-14 |
| `get_by_delivery` | R5 | SDI-G-15 |
| `get_by_delivery` | Side effects | SDI-G-16, SDI-G-17 |
