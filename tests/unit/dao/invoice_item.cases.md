# Test cases — `app/dao/invoice_item.py`

> **Spec:** `tests/unit/dao/invoice_item.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open).
> **Revision:** 1 — the spec changed: its gap round of 2026-11-03 adds `delete_all_for_invoice` R7 [BUG-1283] (owner's answer to Spec gap 1). R7 → II-DA-14 (strict xfail), II-DA-15 (pass). Additive, from `invoice_item.verify.md` (case-missing Findings 1 … 3; recipes R-1 … R-4): R-1 → II-GW-05; R-2 → II-GW-06; R-3 → II-GI-21; R-4 → II-GW-07. New Then lines are numbered last, so no existing Then number moved. No ID retired.
> **Counts:** 43 cases · 39 expected-to-pass · 4 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `get_by_invoice` 21 (3 bug) · `get_by_id_and_workspace` 7 · `delete_all_for_invoice` 15 (1 bug).
- **Depth:** full (skill step 1a): `delete_all_for_invoice` removes the money lines of an invoice, and `get_by_invoice` feeds the invoice total.
- **Expected-to-fail:** BUG-1283 1: II-DA-14 strict. BUG-638 3: II-GI-14, II-GI-15 non-strict (the lower id updated, and no update, so physical order lies both ways), II-GI-16 strict (the SQL recorder, the alarm that goes off when the bug is fixed). II-GI-13 is the passing companion.
- **Commit spy:** II-DA-08, on the one writer. II-DA-09 catches the loss of the method's flush; II-DA-10 holds it to one `DELETE` with no workspace.
- **Notable design choices:**
  - Each R6 sentence has its own card; the delete runs in the Given, so the When holds the one read.
  - A deleted line is counted by `invoice_id`, never re-read through its object.
  - `confirmed` is the only non-draft status the spec gives, so R4 has that one card.
  - The Overview sentence "does not look at the invoice's status" is covered on the reader too.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Revision 1:** II-GW-05, II-GW-06 (by-id read: another workspace's line at the earlier id; a confirmed invoice, with no `account_invoices` in the statement); II-GI-21, II-GW-07 (an unflushed edit stays unflushed); II-DA-14 (BUG-1283, strict) and II-DA-15 (its passing companion) for the new R7.
- **Needs a decision:** None. Money gaps 1 and 2 are closed by the spec's gap round.

## Conventions for this module

**IDs.** `II` = `app/dao/invoice_item.py`. `GI` get_by_invoice · `GW` get_by_id_and_workspace · `DA` delete_all_for_invoice.

**Actors and fixed values.**
- `dao` = the singleton `invoice_item_dao` (`from app.dao.invoice_item import invoice_item_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `InvoiceItem` = `app.models.invoice_item.InvoiceItem`. `Account` = `app.models.account.Account`. `AccountInvoice` = `app.models.account_invoice.AccountInvoice`. `Decimal` = `decimal.Decimal`. `date` = `datetime.date`. `text` = `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line (workspaces from `make_workspace`; the rest built directly, add + flush):
  - W1, W2 = two `workspaces` rows.
  - AC1 = `Account(workspace_id=W1.id, name="Acme")`. AC9 = the same, but `workspace_id W2.id`.
  - IN1 = `AccountInvoice(workspace_id=W1.id, account_id=AC1.id, invoice_type="payable", invoice_status="draft", invoice_amount=0, paid_amount=0, invoice_date=date(2026, 3, 1), payment_status="unpaid", allow_payments=True)`. IN2 = the same. INC = the same, but `invoice_status "confirmed"`. IN9 = the same, but `workspace_id W2.id`, `account_id AC9.id`.
- **line** = `invoice_items` row built with `InvoiceItem`: `workspace_id W1.id`, `invoice_id IN1.id`, `description "Line"`, `quantity Decimal("1.00")`, `unit_price Decimal("2.00")`, `line_subtotal Decimal("2.00")`; `item_id`, `source_order_item_id` are not passed. The card always gives `line_number`; after the word "but" it lists every other column that differs.
- No `invoice_items` row exists unless the card's Given lists it.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending. "it is a standing row" means that row is not inserted again; the line only says what it holds.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned; the order is part of the check.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the number of `invoice_items` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P and the session after the call, before anything expires it: `db.new`, `db.dirty`, `db.deleted` as the session holds them. A card lists them ahead of its `nothing written:` and `unchanged:` lines; keep that order.
- `count:` lines are `SELECT count(*)` queries. Never re-read a deleted line through its object: the row is gone, so count by `invoice_id` or `workspace_id`.
- **seqscan** = run, in this order, `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`: transaction-local, gone with the rollback. Today's read then follows physical row order.
- **rolled back** = `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.
- `raises: TypeError` = plain `with pytest.raises(TypeError):` around the call.

**xfail cards.** Write the call and the checks exactly as shown. `Expect: xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `xfail BUG-n (non-strict)` = `strict=False`, for a card comparing an order that rests on physical row order. The assertion of a non-strict card is never weakened. Bugs here: BUG-638.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `invoice_items`; `order_part` = the text of `sql` after its first `ORDER BY` (`""` when there is none); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `InvoiceItemDAO.get_by_invoice`

### II-GI-01 — returns a list of the invoice's lines
- **Rules:** `get_by_invoice` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.
2. B = line, `line_number 2`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=IN1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id, B.id]`.
3. returns: `isinstance(result[0], InvoiceItem)`.

### II-GI-02 — a line of another invoice of the same workspace is not returned, though it sorts first
- **Rules:** `get_by_invoice` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `line_number 2`.
2. B = line, `line_number 1`, but `invoice_id IN2.id`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=IN1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### II-GI-03 — the right invoice under another workspace returns an empty list
- **Rules:** `get_by_invoice` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=IN1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### II-GI-04 — an unknown workspace returns an empty list
- **Rules:** `get_by_invoice` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=IN1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### II-GI-05 — a W2 row on a W1 invoice is returned for W2: only the row's workspace is compared
- **Rules:** `get_by_invoice` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `line_number 1`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=IN1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### II-GI-06 — a W2 row on a W1 invoice is not returned for W1, though it sorts first
- **Rules:** `get_by_invoice` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B = line, `line_number 1`, but `workspace_id W2.id`.
2. A = line, `line_number 2`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=IN1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### II-GI-07 — an unknown invoice id returns an empty list
- **Rules:** `get_by_invoice` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### II-GI-08 — invoice id 0 returns an empty list
- **Rules:** `get_by_invoice` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### II-GI-09 — an invoice with no rows returns an empty list
- **Rules:** `get_by_invoice` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=IN2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### II-GI-10 — a line comes back with its stored money values
- **Rules:** `get_by_invoice` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line, `line_number 4`, but `description "Press plate"`, `quantity Decimal("2.50")`, `unit_price Decimal("1.25")`, `line_subtotal Decimal("3.13")`, `item_id 77`, `source_order_item_id 88`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=IN1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].invoice_id == IN1.id`, `result[0].workspace_id == W1.id`, `result[0].line_number == 4`.
3. returns: `result[0].description == "Press plate"`, `result[0].item_id == 77`, `result[0].source_order_item_id == 88`.
4. returns: `result[0].quantity == Decimal("2.50")`, `result[0].unit_price == Decimal("1.25")`, `result[0].line_subtotal == Decimal("3.13")`.

### II-GI-11 — lines are ordered by line_number ascending, whatever their ids, and as numbers
- **Rules:** `get_by_invoice` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line, `line_number 10`.
2. B = line, `line_number 2`.
3. C = line, `line_number 1`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=IN1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [C.id, B.id, A.id]`.

### II-GI-12 — line_number decides, not the description or the money values
- **Rules:** `get_by_invoice` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `line_number 2`, but `description "Alpha"`, `line_subtotal Decimal("1.00")`.
2. B = line, `line_number 1`, but `description "Zeta"`, `line_subtotal Decimal("9.00")`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=IN1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### II-GI-13 — on a tie both lines are returned, after the lower line_number
- **Rules:** `get_by_invoice` R5, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `line_number 2`.
2. B = line, `line_number 2`.
3. C = line, `line_number 1`.
4. `A.quantity = Decimal("3.00")`, then `db.flush()`.
5. `db.expire_all()`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=IN1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `result[0].id == C.id`.
3. returns: `{r.id for r in result[1:]} == {A.id, B.id}`.

### II-GI-14 — on a tie the lowest id comes first, when the lower id was updated
- **Rules:** `get_by_invoice` R5 [BUG-638]
- **Kind:** bug
- **Expect:** xfail BUG-638 (non-strict)
- **Fails today on:** Then 2 (no order is requested among the tied lines; the updated lower id comes second, but that rests on physical row order)

**Given**
1. A = line, `line_number 1`.
2. B = line, `line_number 1`.
3. `A.quantity = Decimal("3.00")`, then `db.flush()`.
4. `db.expire_all()`.
5. seqscan.

**When**
- `result = dao.get_by_invoice(db, invoice_id=IN1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### II-GI-15 — on a tie the lowest id comes first, when text and money would sort the other way
- **Rules:** `get_by_invoice` R5 [BUG-638]
- **Kind:** bug
- **Expect:** xfail BUG-638 (non-strict)
- **Fails today on:** Then 2 (no order is requested among the tied lines; physical order usually gives the intended result, which is why this card is non-strict)

**Given**
1. A = line, `line_number 1`, but `description "Zeta"`, `line_subtotal Decimal("9.00")`.
2. B = line, `line_number 1`, but `description "Alpha"`, `line_subtotal Decimal("1.00")`.
3. `db.expire_all()`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=IN1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### II-GI-16 — the query orders by line_number, then id ascending
- **Rules:** `get_by_invoice` R5 [BUG-638]
- **Kind:** bug
- **Expect:** xfail BUG-638
- **Fails today on:** Then 4 (the query orders by `line_number` alone)

**Given**
1. A = line, `line_number 1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_invoice(db, invoice_id=IN1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"line_number" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("line_number") < order_part.index(".id")`.
6. statement: `"DESC" not in order_part.upper()`.

### II-GI-17 — there is no cap: 101 lines give 101 rows
- **Rules:** `get_by_invoice` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 lines L1 … L101, built with `add_all`: Lk = line, `line_number` k. `in_order` = the ids of L1, L2, … L101, in that order.

**When**
- `result = dao.get_by_invoice(db, invoice_id=IN1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == in_order`.

### II-GI-18 — a positional `invoice_id` raises TypeError
- **Rules:** `get_by_invoice` R7
- **Kind:** error
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `dao.get_by_invoice(db, IN1.id, workspace_id=W1.id)`.

**Then**
1. raises: `TypeError`.
2. nothing written: nothing written.

### II-GI-19 — the invoice's status is not looked at: the lines of a confirmed invoice are returned
- **Rules:** `get_by_invoice` Overview
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Invoice INC has `invoice_status "confirmed"`: it is a standing row.
2. A = line, `line_number 1`, but `invoice_id INC.id`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=INC.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### II-GI-20 — writes nothing: a pending line that sorts first stays pending and alone in the session
- **Rules:** `get_by_invoice` Side effects, Overview
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `line_number 2`.
2. `P = InvoiceItem(workspace_id=W1.id, invoice_id=IN1.id, description="Line", quantity=Decimal("1.00"), unit_price=Decimal("2.00"), line_subtotal=Decimal("2.00"), line_number=1)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_invoice(db, invoice_id=IN1.id, workspace_id=W1.id)`.

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
10. statement: `"account_invoices" not in sql`.
11. nothing written: nothing written.
12. unchanged: unchanged(A).

### II-GI-21 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded
- **Rules:** `get_by_invoice` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.
2. B = line, `line_number 1`, but `invoice_id IN2.id`.
3. `B.description = "Edited"` (not flushed).

**When**
- `result = dao.get_by_invoice(db, invoice_id=IN1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `B in db.dirty`.
3. pending: `len(db.dirty) == 1`.
4. pending: `B.description == "Edited"`.


## `InvoiceItemDAO.get_by_id_and_workspace`

### II-GW-01 — returns the line of that id, not the first line
- **Rules:** `get_by_id_and_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.
2. B = line, `line_number 2`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=B.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == B.id`.
2. returns: `isinstance(result, InvoiceItem)`.

### II-GW-02 — another workspace returns None
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.
2. B = line, `line_number 2`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=B.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### II-GW-03 — an unknown id returns None and nothing is created
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### II-GW-04 — writes nothing: a read that finds its line leaves the session as it was
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.
2. `P = InvoiceItem(workspace_id=W1.id, invoice_id=IN1.id, description="Line", quantity=Decimal("1.00"), unit_price=Decimal("2.00"), line_subtotal=Decimal("2.00"), line_number=2)`
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

### II-GW-05 — a W2 line at the earlier id is not returned for W1
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = line, `line_number 1`, but `workspace_id W2.id`, `invoice_id IN9.id`.
2. A = line, `line_number 2`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### II-GW-06 — the invoice's status is not looked at and the invoice is not joined: a line of a confirmed invoice is returned
- **Rules:** `get_by_id_and_workspace` Overview
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Invoice INC has `invoice_status "confirmed"`: it is a standing row.
2. A = line, `line_number 1`, but `invoice_id INC.id`.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. statement: `"account_invoices" not in sql`.

### II-GW-07 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.
2. B = line, `line_number 2`.
3. `B.description = "Edited"` (not flushed).

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `B in db.dirty`.
3. pending: `len(db.dirty) == 1`.
4. pending: `B.description == "Edited"`.


## `InvoiceItemDAO.delete_all_for_invoice`

### II-DA-01 — every line of the invoice is deleted; lines of another invoice stay
- **Rules:** `delete_all_for_invoice` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.
2. B = line, `line_number 2`.
3. C = line, `line_number 1`, but `invoice_id IN2.id`.

**When**
- `result = dao.delete_all_for_invoice(db, invoice_id=IN1.id)`.

**Then**
1. returns: `result is None`.
2. count: `invoice_items` has exactly 0 rows with `invoice_id == IN1.id`.
3. count: `invoice_items` has exactly 1 row with `invoice_id == IN2.id`.
4. unchanged: unchanged(C).

### II-DA-02 — lines of another invoice in another workspace stay
- **Rules:** `delete_all_for_invoice` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.
2. C = line, `line_number 1`, but `workspace_id W2.id`, `invoice_id IN9.id`.

**When**
- `result = dao.delete_all_for_invoice(db, invoice_id=IN1.id)`.

**Then**
1. returns: `result is None`.
2. count: `invoice_items` has exactly 0 rows with `invoice_id == IN1.id`.
3. count: `invoice_items` has exactly 1 row with `invoice_id == IN9.id`.
4. unchanged: unchanged(C).

### II-DA-03 — no workspace filter: a W2 row carrying this invoice id is deleted too
- **Rules:** `delete_all_for_invoice` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.
2. B = line, `line_number 2`, but `workspace_id W2.id`.

**When**
- `result = dao.delete_all_for_invoice(db, invoice_id=IN1.id)`.

**Then**
1. returns: `result is None`.
2. count: `invoice_items` has exactly 0 rows with `invoice_id == IN1.id`.
3. count: `invoice_items` has exactly 0 rows with `workspace_id == W2.id`.

### II-DA-04 — an unknown invoice id deletes nothing and raises nothing
- **Rules:** `delete_all_for_invoice` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.

**When**
- `result = dao.delete_all_for_invoice(db, invoice_id=MISSING)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.
3. unchanged: unchanged(A).

### II-DA-05 — invoice id 0 deletes nothing and raises nothing
- **Rules:** `delete_all_for_invoice` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.

**When**
- `result = dao.delete_all_for_invoice(db, invoice_id=0)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.
3. unchanged: unchanged(A).

### II-DA-06 — an invoice with no lines deletes nothing and raises nothing
- **Rules:** `delete_all_for_invoice` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.

**When**
- `result = dao.delete_all_for_invoice(db, invoice_id=IN2.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.
3. unchanged: unchanged(A).

### II-DA-07 — the status is not looked at: the lines of a confirmed invoice are deleted, and the invoice is not touched
- **Rules:** `delete_all_for_invoice` R4, Side effects
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Invoice INC has `invoice_status "confirmed"`: it is a standing row.
2. A = line, `line_number 1`, but `invoice_id INC.id`.
3. B = line, `line_number 2`, but `invoice_id INC.id`.

**When**
- `result = dao.delete_all_for_invoice(db, invoice_id=INC.id)`.

**Then**
1. returns: `result is None`.
2. count: `invoice_items` has exactly 0 rows with `invoice_id == INC.id`.
3. unchanged: unchanged(INC).
4. re-read INC: `invoice_status == "confirmed"`.

### II-DA-08 — the delete is flushed, not committed: gone in the session, back after a rollback
- **Rules:** `delete_all_for_invoice` R5, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `line_number 1`, but `line_subtotal Decimal("7.25")`.
2. B = line, `line_number 2`.
3. Savepoint and commit spy per **rolled back**.

**When**
- `result = dao.delete_all_for_invoice(db, invoice_id=IN1.id)`.

**Then**
1. returns: `result is None`.
2. count: `invoice_items` has exactly 0 rows with `invoice_id == IN1.id` (inside the savepoint).
3. count: after the savepoint rollback, `invoice_items` has exactly 2 rows with `invoice_id == IN1.id`.
4. re-read A after the savepoint rollback: `line_subtotal == Decimal("7.25")`.
5. mock called: the `db.commit` spy was never called.

### II-DA-09 — the method flushes: a line of another invoice waiting in the session is stored by the call
- **Rules:** `delete_all_for_invoice` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.
2. `P = InvoiceItem(workspace_id=W1.id, invoice_id=IN2.id, description="Line", quantity=Decimal("1.00"), unit_price=Decimal("2.00"), line_subtotal=Decimal("2.00"), line_number=1)`
3. `db.add(P)` (not flushed).

**When**
- `result = dao.delete_all_for_invoice(db, invoice_id=IN1.id)`.

**Then**
1. returns: `result is None`.
2. pending: `P not in db.new`.
3. pending: `P.id is not None`.
4. count: `invoice_items` has exactly 0 rows with `invoice_id == IN1.id`.
5. count: `invoice_items` has exactly 1 row with `invoice_id == IN2.id`.

### II-DA-10 — one DELETE statement, on this table only, with no workspace and no invoice read
- **Rules:** `delete_all_for_invoice` Side effects, R2, R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.
2. B = line, `line_number 2`.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.delete_all_for_invoice(db, invoice_id=IN1.id)`.

**Then**
1. returns: `result is None`.
2. statement: `len(written) == 1`.
3. statement: `written[0].upper().startswith("DELETE")`.
4. statement: `"invoice_items" in written[0]`.
5. statement: `"workspace_id" not in written[0]`.
6. statement: `"account_invoices" not in written[0]`.
7. statement: `selects == []`.

### II-DA-11 — after the delete, db.get returns the stale instance with no query
- **Rules:** `delete_all_for_invoice` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `line_number 1`, but `description "Stale"`.
2. `A_id = A.id`.
3. `dao.delete_all_for_invoice(db, invoice_id=IN1.id)`.
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = db.get(InvoiceItem, A_id)`.

**Then**
1. returns: `result is A`.
2. returns: `result.description == "Stale"`.
3. statement: `selects == []`.

### II-DA-12 — after the delete, get_by_invoice runs a query and does not find the line
- **Rules:** `delete_all_for_invoice` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.
2. `dao.delete_all_for_invoice(db, invoice_id=IN1.id)`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=IN1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### II-DA-13 — after the delete, get_by_id_and_workspace runs a query and does not find the line
- **Rules:** `delete_all_for_invoice` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.
2. `A_id = A.id`.
3. `dao.delete_all_for_invoice(db, invoice_id=IN1.id)`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A_id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### II-DA-14 — a line of the same invoice waiting in the session is deleted too, and the flush does not store it
- **Rules:** `delete_all_for_invoice` R7 [BUG-1283]
- **Kind:** bug
- **Expect:** xfail BUG-1283
- **Fails today on:** Then 2 (the `DELETE` runs first, then the method's flush inserts P, so one row is left)

**Given**
1. A = line, `line_number 1`.
2. `P = InvoiceItem(workspace_id=W1.id, invoice_id=IN1.id, description="Line", quantity=Decimal("1.00"), unit_price=Decimal("2.00"), line_subtotal=Decimal("2.00"), line_number=2)`
3. `db.add(P)` (not flushed).

**When**
- `result = dao.delete_all_for_invoice(db, invoice_id=IN1.id)`.

**Then**
1. returns: `result is None`.
2. count: `invoice_items` has exactly 0 rows with `invoice_id == IN1.id`.

### II-DA-15 — with a pending line of each invoice, the other invoice's line is still stored by the flush
- **Rules:** `delete_all_for_invoice` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = line, `line_number 1`.
2. `P1 = InvoiceItem(workspace_id=W1.id, invoice_id=IN1.id, description="Line", quantity=Decimal("1.00"), unit_price=Decimal("2.00"), line_subtotal=Decimal("2.00"), line_number=2)`
3. `db.add(P1)` (not flushed).
4. `P2 = InvoiceItem(workspace_id=W1.id, invoice_id=IN2.id, description="Other", quantity=Decimal("1.00"), unit_price=Decimal("2.00"), line_subtotal=Decimal("2.00"), line_number=1)`
5. `db.add(P2)` (not flushed).

**When**
- `result = dao.delete_all_for_invoice(db, invoice_id=IN1.id)`.

**Then**
1. returns: `result is None`.
2. pending: `P2 not in db.new`.
3. pending: `P2.id is not None`.
4. count: `invoice_items` has exactly 1 row with `invoice_id == IN2.id`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_by_invoice` R5 — BUG-638, the `get_items` and `get_events` halves | `AccountInvoiceManager` | The manager's cards carry the bug; for `get_items` the line to fix is this DAO, and the cards above are its alarm. |
| `delete_all_for_invoice` R4 — the draft check | `AccountInvoiceManager.sync_items_from_list` | **Money.** Lines of a non-draft invoice must not reach this method; here the DAO does not look. |
| `delete_all_for_invoice` R2 — the workspace of the invoice (HR-16) | `AccountInvoiceManager.sync_items_from_list` | **Money.** The caller passes an invoice it already scoped. |
| Review, HR-15 — `_recalculate_invoice_amount` sums session instances, so an unrounded `line_subtotal` not yet read back counts unrounded | `AccountInvoiceManager._recalculate_invoice_amount` | **Money.** The sum lives there; the DAO computes none. |
| Overview — `create`, `update`, `remove` through `/invoice-items/` | `/invoice-items/` endpoints; `tests/unit/dao/base.spec.md` | Inherited writers: BASE-C-05, BASE-U-12, BASE-R-02. |
| Module singleton | none (no logic) | Only used as the entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `delete_all_for_invoice` R1, R5 | **Money.** A line of this same invoice added and not flushed: is it deleted, or stored by the method's flush? The spec does not say. | **Closed in revision 1:** answered by the owner (2026-11-03), spec `delete_all_for_invoice` R7 [BUG-1283]: II-DA-14 (strict), II-DA-15 (pass). |
| 2 | BUG-638, `docs/testing/bugs.md` | **Money.** The bug row names the manager's file, and its intended line for `get_items` says item `id` ascending. The spec keeps `line_number` first and says the fix is in this DAO. | **Closed in revision 1:** the spec's gap round says BUG-638's row now names this DAO. |
| 3 | Model facts | Defaults and cascades, and `line_number` defaulting to `1`, are not rules of the DAO. | No card. Ties are built with an explicit `line_number`. |
| 4 | Notes | `AccountInvoice(...)` in Notes passes no `created_by`; existing tests do. The spec does not say whether it is required. | Conventions follow the Notes. A required column would fail at setup, in every test. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_invoice` | Returns | II-GI-01 |
| `get_by_invoice` | R1 | II-GI-01, II-GI-02, II-GI-10 |
| `get_by_invoice` | R2 | II-GI-03, II-GI-04, II-GI-05, II-GI-06 |
| `get_by_invoice` | R3 | II-GI-07, II-GI-08, II-GI-09 |
| `get_by_invoice` | R4 | II-GI-11, II-GI-12, II-GI-13 |
| `get_by_invoice` | R5 | II-GI-13 |
| `get_by_invoice` | R5 [BUG-638] | II-GI-14, II-GI-15, II-GI-16 |
| `get_by_invoice` | R6 | II-GI-17 |
| `get_by_invoice` | R7 | II-GI-18 |
| `get_by_invoice` | Overview | II-GI-19, II-GI-20 |
| `get_by_invoice` | Side effects | II-GI-20, II-GI-21 |
| `get_by_id_and_workspace` | Returns | II-GW-01 |
| `get_by_id_and_workspace` | R1 | II-GW-01, II-GW-02, II-GW-03, II-GW-05 |
| `get_by_id_and_workspace` | Overview | II-GW-06 |
| `get_by_id_and_workspace` | Side effects | II-GW-04, II-GW-07 |
| `delete_all_for_invoice` | Returns | II-DA-01 |
| `delete_all_for_invoice` | R1 | II-DA-01, II-DA-02 |
| `delete_all_for_invoice` | R2 | II-DA-03, II-DA-10 |
| `delete_all_for_invoice` | R3 | II-DA-04, II-DA-05, II-DA-06 |
| `delete_all_for_invoice` | R4 | II-DA-07, II-DA-10 |
| `delete_all_for_invoice` | R5 | II-DA-08, II-DA-09 |
| `delete_all_for_invoice` | R6 | II-DA-11, II-DA-12, II-DA-13 |
| `delete_all_for_invoice` | R7 | II-DA-15 |
| `delete_all_for_invoice` | R7 [BUG-1283] | II-DA-14 |
| `delete_all_for_invoice` | Side effects | II-DA-07, II-DA-08, II-DA-10 |
