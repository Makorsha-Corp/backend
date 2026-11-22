# Test cases — `app/managers/purchase_order_return_manager.py`

> **Spec:** `tests/unit/managers/purchase_order_return_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 3a (2026-11-19) — executor DISCREPANCY-1, wording only: the "Fails today on" line of RR-01 … RR-04, RR-08, RR-10 … RR-30 now says the card fails before the call (ImportError on the missing schema), not at the call. No other change.
> **Revision:** 3 (2026-11-19) — owner, BUG-2810: new callable `validate_replacement_receipt` RR1–RR8. New cards PORM-RR-01 … PORM-RR-35, all strict xfail BUG-2810 (the method and its schema do not exist). The Deferred row OQ-48 / FU-2 now points at BUG-2810 / FU-2: the writes go to `PurchaseOrderService.receive_replacements`. No existing card changed; no ID retired.
> **Revision:** 2 (2026-11-17) — owner answers of 2026-11-17 and spec Gap log G1–G4. OQ-45 → BUG-2785: Q45-01, Q45-03, Q45-04 are now strict xfails (price refused); Q45-02, Q45-05, Q45-06 stay pass; new Q45-07 … Q45-12 (unpriced line, check order R6a, message names the line and its stored price). OQ-46 → BUG-2787: Q46-01 now a strict xfail (price required); new Q46-03 … Q46-05. OQ-47 → BUG-2788 (check in `AccountInvoiceManager.void_invoice` R3c): Q47-01, Q47-02 stay pass (this method still writes only `paid`); Q47-03 … Q47-05 rewritten to void through `void_invoice` and expect the return freed (strict xfails); new Q47-06 … Q47-08. BUG-2750 confirmed by the owner (cards unchanged). Gap 1: V-41, V-42 now expect `only 0` exactly. Gap 2: new SCH-16, SCH-17 (required fields). Gap 3 → BUG-2792: new V-51 … V-53. Gap 4: new V-54 … V-56 (running total, R1 order). Owner-question header lines removed; Spec gaps closed. No ID retired.
> **Counts:** 181 cases · 104 expected-to-pass · 77 expected-to-fail (bugs) · 11 deferred

## Reviewer summary
- **Per callable:** `has_open_return` 10 · `validate_and_build_items` 50 (16 bug) · schemas 18 (5 bug) · `get_return` 17 (5 bug) · `list_returns` 12 (3 bug) · `sync_return_paid` 14 (0 bug) · owner answers 2026-11-17: price range Q45 12 (6 bug), missing price Q46 5 (2 bug), credit-note void Q47 8 (5 bug) · `validate_replacement_receipt` 35 (35 bug, new, BUG-2810).
- **Expected-to-fail by bug:** BUG-2750 5 · BUG-2751 7 · BUG-2752 5 · BUG-2753 1 · BUG-2754 3 · BUG-2755 4 · BUG-2429 1 (DAO tie-break, seen through `list_returns`) · BUG-2785 6 · BUG-2787 2 · BUG-2788 5 · BUG-2792 3 · BUG-2810 35. 2 of the 77 are non-strict (physical order, G-14, L-09); all others are strict.
- **Depth:** full (step 1a). The module decides how much stock can leave and how big a confirmed credit note gets, and it keeps the credit note's `paid` flag in step.
- **Twin:** `sales_order_return_manager.cases.md` has the same cards under the same numbers (`PORM-V-14` ↔ `SORM-V-14`). The only differences are sales facts: an item name instead of a line number, free-text lines, `payable` credit notes, no OQ-46, and the sales-only cards V-46 … V-50 and V-57 … V-60, numbered after the shared ones. Purchase-only: Q45-07, Q45-08 and all Q46 cards (unpriced lines). V-06 has the same number in both files but a different shape: a line number here, a free-text line there.
- **Notable design choices:**
  - **Owner answers of 2026-11-17:** each one has its own section and ID code. `Q45` (price range, BUG-2785), `Q46` (missing price, BUG-2787), `Q47` (credit-note void, BUG-2788). The cards that were pinning today's behaviour are now strict xfails on the intended result; the edges that hold both today and after the fix stay pass. The Q47 cards void through `AccountInvoiceManager.void_invoice` (where R3c lives) and read the return with this manager.
  - **BUG-2750 (counted twice):** a completed return is built the way `complete_return` leaves it (received −q, returned +q, refund also refunded +q). Each scenario is a strict xfail on the intended number. A separate pass card holds the part that is true today and after the fix: the request is refused with 400.
  - **BUG-2751 (repeats):** repeats that fit stay as separate dicts. That works today, so it is a pass card. Repeats that do not fit are strict xfails, including repeats split by another line, three repeats, repeats on top of a pending reservation, and repeats with decimals.
  - **Decimals:** schema cards (BUG-2752) are strict xfails at 3 decimals and at 14 integer digits. Pass cards cover the edges that stay valid (`0.01`, 13 digits). Manager cards never send 3 decimals, so that they keep passing after the schema fix: `10.01` rather than the spec's `10.001`.
  - **Locks (BUG-2753, BUG-2754):** these are statement-recorder cards. The intended lock is pinned as `FOR UPDATE` with no `SKIP LOCKED` / `NOWAIT`. Every reader also has a pass card that proves it sends no `FOR UPDATE`. The two-transaction outcome is deferred.
  - **Workspaces:** W0 and W2 rows sit on both sides of W1, and orders O1 and O3 on both sides of O2. Rows of another workspace on a W1 order are inserted directly as invalid data.
  - **Refusals:** plain `pytest.raises`, no savepoint. The session is checked to be clean before any re-read, and nothing is written.
- **Replacement receipts (BUG-2810):** every RR card is a strict xfail. They cover the limit counting replacements already received plus a running total in request order; check order type → status → lines; W0/W2 isolation on line and caller; exact Decimal costs per RR6; and session-clean refusals. Four cards set the new `quantity_replaced` column, so they fail in the Given and are marked `Author: claude`.
- **Needs a decision:** two new small gaps on the RR cards (5: the schema's module and line class; 6: an unreachable RR4 shape). Neither blocks a card. Gaps 1–4 are closed.

## Conventions for this module

**IDs.** `PORM` = `app/managers/purchase_order_return_manager.py`. `HO` has_open_return · `V` validate_and_build_items · `SCH` the schemas (target `schema`) · `G` get_return · `L` list_returns · `S` sync_return_paid · `Q45` = return price range (BUG-2785), `Q46` = missing price (BUG-2787), `Q47` = credit-note void (BUG-2788): the owner answers of 2026-11-17 to OQ-45 / OQ-46 / OQ-47.

**Actors and fixed values.**
- `RM` = `purchase_order_return_manager` (`from app.managers.purchase_order_return_manager import purchase_order_return_manager`). `db` = the test's real session, first argument; the rest by keyword. `result` = what the When returns. The session does not autoflush.
- Classes: `PurchaseOrder` (`app.models.purchase_order`), `PurchaseOrderItem` (`app.models.purchase_order_item`), `PurchaseOrderReturn`, `PurchaseOrderReturnItem` (`app.models.purchase_order_return`), `Item` (`app.models.item`), `Factory` (`app.models.factory`), `Status` (`app.models.status`), `Account` (`app.models.account`), `AccountInvoice` (`app.models.account_invoice`). Schemas `PurchaseOrderReturnCreate`, `PurchaseOrderReturnItemCreate` (`app.schemas.purchase_order_return`). `HTTPException` (`fastapi`), `ValidationError` (`pydantic`). `Decimal`, `date`, `datetime`, `text`, `patch`, `uuid` = the usual ones.
- MISSING = `999999999`. TAG = `uuid.uuid4().hex[:8]`, made once per test. T1, T2, T3, T4 = `datetime(2026, 3, 4, 9, 0)`, `(…, 10, 0)`, `(…, 11, 0)`, `(…, 12, 0)` (naive).

**Standing rows** (every test, this order, each flushed, no Given line):
1. W0, W1, W2 = `make_workspace(db)` three times (`W0.id < W1.id < W2.id`). U1, U2 = `make_profile(db)` twice.
2. For W0, W1, W2 in turn: F0 / F1 / F9 = `Factory(workspace_id=…, name="Store", abbreviation="ST")`; ST0 / ST1 / ST9 = `Status(workspace_id=…, name="Receiving", comment="stage")`; AC0 / AC1 / AC9 = `Account(workspace_id=…, name="Supplier")`.
3. I1 = `Item(workspace_id=W1.id, name="Pump", name_normalized="pump", unit="pcs")`. I2 = the same, but `name "Valve"`, `name_normalized "valve"`.
4. Orders, in this order: O0 (W0), O1, O2, O3 (W1), O9 (W2) = `PurchaseOrder(workspace_id=…, po_number=f"PO-{TAG}-<name>", destination_type="storage", destination_id=<that workspace's factory>.id, current_status_id=<that workspace's status>.id, created_by=U1.id)`. So `O1.id < O2.id < O3.id`. Cards work on O2 unless they say otherwise.

**Given rows.** Inserted directly, never through `RM`, flushed one at a time in the order written. After "but", a line lists every column that differs. A line written as code is a step to run exactly, at that place.
- **line k** = `PurchaseOrderItem(workspace_id=W1.id, purchase_order_id=O2.id, line_number=k, item_id=I1.id, quantity_ordered=Decimal("10.00"), quantity_received=Decimal("10.00"), quantity_returned=Decimal("0.00"), quantity_refunded=Decimal("0.00"), unit_price=Decimal("10.00"))`. Line 2 always has `item_id I2.id`.
- **return N** = `PurchaseOrderReturn(workspace_id=W1.id, purchase_order_id=O2.id, return_number=f"PR-{TAG}-N", return_type="refund", created_by=U1.id)`. `status` and `paid` are left to their defaults (`"pending"`, `False`).
- **completed** (on a return) = `status "completed"`, `completed_at T4`, `completed_by U1.id`. **voided** = `status "voided"`, `paid False`, `updated_at T4`. A void leaves `updated_by`, `completed_at` and `completed_by` NULL.
- A completed return's order line already shows the completion, as `complete_return` leaves it: received −q, returned +q, and for `return_type "refund"` also refunded +q. The card writes those columns on the line.
- **rline of R on L, q** = `PurchaseOrderReturnItem(workspace_id=R.workspace_id, return_id=R.id, po_item_id=L.id, item_id=L.item_id, quantity_returned=Decimal(q), unit_price=Decimal("10.00"))`.
- **credit note of W, s** = `AccountInvoice(workspace_id=W.id, account_id=<AC of W>.id, invoice_type="receivable", invoice_amount=Decimal("40.00"), invoice_date=date(2026, 3, 4), payment_status=s)`. **voided credit note** = credit note of W1, `"unpaid"`, but `invoice_status "voided"` (what a void leaves). **confirmed credit note** = credit note of W1, `"unpaid"`, but `invoice_status "confirmed"`.
- **seqscan** = `db.execute(text("SET LOCAL enable_indexscan = off"))`, then the same with `enable_bitmapscan`, then `enable_indexonlyscan`. **bumpL(X)** = `db.execute(text("UPDATE purchase_order_return_items SET notes = notes WHERE id = :i"), {"i": X.id})`, then `db.expire_all()`.

**Requests** (target of `validate_and_build_items`).
- **LN(L, "q")** = `PurchaseOrderReturnItemCreate(po_item_id=L.id, quantity_returned=Decimal("q"))`. `LN(L, "q", notes=n)` also sends `notes=n`. No `unit_price` is sent unless the card writes `unit_price=` (only the `Q45` / `Q46` cards do). REQ sends `reason` although it is optional (G2).
- **REQ(a, b, …)** = `PurchaseOrderReturnCreate(return_type="refund", reason="Faulty", items=[a, b, …])`.
- **V(req)** = `RM.validate_and_build_items(db, purchase_order_id=O2.id, workspace_id=W1.id, data=req)`.
- **TOO(q, n, a)** = the detail text `f"Cannot return {q} of line {n} — only {a} available to return"`, e.g. TOO("11", 1, "10.00") = `"Cannot return 11 of line 1 — only 10.00 available to return"`. The dash is U+2014; copy it.
- **NOTHERE(id)** = `f"Item {id} does not belong to this purchase order"`.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot after the last Given line).
- **nothing written** = the row counts of `purchase_order_returns`, `purchase_order_return_items`, `purchase_order_items` and `account_invoices` (all workspaces) equal their values before the call.
- **session clean** = three asserts on `db`, before anything is re-read: `not db.new`, `not db.dirty`, `not db.deleted`.
- **Statement recorder** = the SQL that the session sends from the start of the When to the end of the test is recorded. `selects` = every `SELECT`. `written` = every `INSERT`, `UPDATE`, `DELETE`. `sel(t)` = the `SELECT`s whose `FROM` names table `t`. `order_part(s)` = the text of `s` after its first `ORDER BY` (`""` if none).
- **no lock** = `all("FOR UPDATE" not in s for s in selects)`.
- **locks t** = some `s` in `sel(t)` has `"FOR UPDATE" in s`, and that `s` has neither `"SKIP LOCKED"` nor `"NOWAIT"`.
- **Clear first:** a card with a statement recorder ends its Given with `db.expunge_all()`, so that no row held in the identity map can hide a read. Ids used in Then come from objects built before that. The `sync_return_paid` cards are the exception: they pass a loaded return, so they do not expunge.
- When a When line writes `result = A`, then B, A is the one call under test. B only reads what it returned (e.g. `list(result.items)`).
- `raises: HTTPException` = plain `with pytest.raises(HTTPException) as exc:` around the call, with no savepoint, because a savepoint would hide a write. Then lines assert `exc.value.status_code` and `exc.value.detail` with `==`, unless they say "starts with".
- `raises: ValidationError` = `pydantic.ValidationError` around the schema's construction. "message contains X" = `X in str(exc.value)`. "loc" = `exc.value.errors()[0]["loc"]`.
- **commit spy** = `sp = db.begin_nested()` directly before the call, inside `with patch.object(db, "commit", wraps=db.commit) as cm:`. The "inside" lines run first, then `sp.rollback()`, then the "after" lines.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`. `(non-strict)` = `strict=False`. Write the call and the checks exactly as shown, also when a parameter does not exist yet.

**Replacement receipts (RR cards).** `PurchaseOrderReturnReplacementCreate` is imported inside each test from `app.schemas.purchase_order_return`, so a missing class fails only that test.
- **RRQ((X, "q"), …)** = `PurchaseOrderReturnReplacementCreate(items=[{"return_item_id": X.id, "quantity": Decimal("q")}, …])`. `MISSING` in place of X means `"return_item_id": MISSING`.
- **RV(R, req)** = `RM.validate_replacement_receipt(db, ret=R, workspace_id=W1.id, data=req)`. R is the loaded return object from the Given.
- "**X has `quantity_replaced Decimal("q")`**" = the return line X is built with that value of the new column `quantity_replaced` (default `0.00`).
- **RTOO(total, n, left)** = `f"Cannot receive {total} replacement(s) for line {n} — only {left} still to replace"`. **NOTPART(id, R)** = `f"Line {id} is not part of return {R.return_number}"`.

**Other manager.** `AIM` = `account_invoice_manager` (`from app.managers.account_invoice_manager import account_invoice_manager`), used only by the Q47 cards to void a credit note the way every void path does. A **void step** in a Given runs exactly as written.

**Externals.** None is mocked. **Race simulations.** None.

## `PurchaseOrderReturnManager.has_open_return`

### PORM-HO-01 — one pending return makes the order open
- **Rules:** `has_open_return` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. R = return "001".

**When**
- `result = RM.has_open_return(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### PORM-HO-02 — a pending return among completed and voided ones still counts
- **Rules:** `has_open_return` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. RC = return "001", but completed.
2. RP = return "002".
3. RV = return "003", but voided.

**When**
- `result = RM.has_open_return(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### PORM-HO-03 — only completed and voided returns: not open
- **Rules:** `has_open_return` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. RC = return "001", but completed.
2. RV = return "002", but voided.

**When**
- `result = RM.has_open_return(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PORM-HO-04 — an order with no returns is not open
- **Rules:** `has_open_return` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No return rows exist.

**When**
- `result = RM.has_open_return(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PORM-HO-05 — pending returns of the orders on both sides do not count
- **Rules:** `has_open_return` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. R1 = return "001", but `purchase_order_id O1.id`.
2. R3 = return "003", but `purchase_order_id O3.id`.

**When**
- `result = RM.has_open_return(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PORM-HO-06 — pending returns of W0 and W2 on the same order id do not count
- **Rules:** `has_open_return` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. R0 = return "000", but `workspace_id W0.id` (invalid data: on the W1 order O2).
2. R9 = return "009", but `workspace_id W2.id` (invalid data: on O2).

**When**
- `result = RM.has_open_return(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PORM-HO-07 — a W1 pending return is not seen from W0
- **Rules:** `has_open_return` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. R = return "001".

**When**
- `result = RM.has_open_return(db, purchase_order_id=O2.id, workspace_id=W0.id)`.

**Then**
1. returns: `result is False`.

### PORM-HO-08 — the check writes nothing and takes no lock
- **Rules:** `has_open_return` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. R = return "001".
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = RM.has_open_return(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. session clean.
3. statement: `written == []`.
4. statement: no lock.

### PORM-HO-09 — an unknown order is not open
- **Rules:** `has_open_return` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. R = return "001".

**When**
- `result = RM.has_open_return(db, purchase_order_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PORM-HO-10 — a W1 pending return is not seen from W2
- **Rules:** `has_open_return` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. R = return "001".

**When**
- `result = RM.has_open_return(db, purchase_order_id=O2.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is False`.

## `PurchaseOrderReturnManager.validate_and_build_items`

### PORM-V-01 — one line with no price sent takes the order line's price
- **Rules:** `validate_and_build_items` R1, R7 (priced line), R8, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "4")))`.

**Then**
1. returns: `result == [{"po_item_id": L1.id, "item_id": I1.id, "quantity_returned": Decimal("4"), "unit_price": Decimal("10.00"), "notes": None}]`.
2. returns: `type(result) is list` and `type(result[0]) is dict`.
3. returns: `set(result[0].keys()) == {"po_item_id", "item_id", "quantity_returned", "unit_price", "notes"}`.

### PORM-V-02 — two lines come back in request order with their notes as sent
- **Rules:** `validate_and_build_items` R1, R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. L1 = line 1.
2. L2 = line 2, but `unit_price Decimal("4.00")`.
3. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L2, "3", notes="box dented"), LN(L1, "2", notes="")))`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `result[0] == {"po_item_id": L2.id, "item_id": I2.id, "quantity_returned": Decimal("3"), "unit_price": Decimal("4.00"), "notes": "box dented"}`.
3. returns: `result[1] == {"po_item_id": L1.id, "item_id": I1.id, "quantity_returned": Decimal("2"), "unit_price": Decimal("10.00"), "notes": ""}`.

### PORM-V-03 — exactly the received quantity is accepted
- **Rules:** `validate_and_build_items` R3 (equal side), R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "10")))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["quantity_returned"] == Decimal("10")`.

### PORM-V-04 — one hundredth more than received is refused
- **Rules:** `validate_and_build_items` R3 (over side); Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "10.01")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == TOO("10.01", 1, "10.00")`.
3. session clean.
4. nothing written.
5. unchanged: unchanged(L1).

### PORM-V-05 — the refused quantity is printed as sent
- **Rules:** `validate_and_build_items` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "11")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot return 11 of line 1 — only 10.00 available to return"`.
3. session clean.
4. nothing written.

### PORM-V-06 — the message names the order line's own line number
- **Rules:** `validate_and_build_items` R3 (D1)
- **Kind:** error
- **Expect:** pass

**Given**
1. L1 = line 1.
2. L3 = line 3, but `quantity_received Decimal("2.00")`.
3. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L3, "3")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot return 3 of line 3 — only 2.00 available to return"`.
3. session clean.

### PORM-V-07 — a pending return reserves its quantity: the rest is accepted
- **Rules:** `validate_and_build_items` R4 (pending)
- **Kind:** happy
- **Expect:** pass

**Given**
1. L1 = line 1.
2. RP = return "001".
3. rline of RP on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "6")))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["quantity_returned"] == Decimal("6")`.

### PORM-V-08 — a pending return reserves its quantity: one more is refused
- **Rules:** `validate_and_build_items` R3, R4 (pending)
- **Kind:** error
- **Expect:** pass

**Given**
1. L1 = line 1.
2. RP = return "001".
3. rline of RP on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "7")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == TOO("7", 1, "6.00")`.
3. session clean.
4. nothing written.

### PORM-V-09 — a voided return reserves nothing
- **Rules:** `validate_and_build_items` R4 (voided)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. L1 = line 1.
2. RV = return "001", but voided.
3. rline of RV on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "10")))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["quantity_returned"] == Decimal("10")`.

### PORM-V-10 — two pending returns add up: exactly the rest is accepted
- **Rules:** `validate_and_build_items` R4 (sum of pending)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. L1 = line 1.
2. RA = return "001".
3. rline of RA on L1, "4.00".
4. RB = return "002".
5. rline of RB on L1, "3.00".
6. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "3")))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["quantity_returned"] == Decimal("3")`.

### PORM-V-11 — two pending returns add up: one more is refused
- **Rules:** `validate_and_build_items` R3, R4 (sum of pending)
- **Kind:** error
- **Expect:** pass

**Given**
1. L1 = line 1.
2. RA = return "001".
3. rline of RA on L1, "4.00".
4. RB = return "002".
5. rline of RB on L1, "3.00".
6. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "4")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == TOO("4", 1, "3.00")`.
3. session clean.

### PORM-V-12 — a pending return on another line does not reserve this line
- **Rules:** `validate_and_build_items` R4 (per line)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. L1 = line 1.
2. L2 = line 2.
3. RP = return "001".
4. rline of RP on L2, "9.00".
5. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "10")))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["po_item_id"] == L1.id`.

### PORM-V-13 — refunded quantity on the line does not lower what can be returned today
- **Rules:** `validate_and_build_items` R4 (refunded quantity is not counted on its own)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. L1 = line 1, but `quantity_ordered Decimal("12.00")`, `quantity_refunded Decimal("2.00")` (2 refunded without goods, OQ-38; 10 received).
2. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "10")))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["quantity_returned"] == Decimal("10")`.

### PORM-V-14 — after a completed return, what is still held can be returned
- **Rules:** `validate_and_build_items` R4 [BUG-2750]
- **Kind:** bug
- **Expect:** xfail BUG-2750
- **Fails today on:** Then 1 (the call raises HTTPException: today only 2.00 is available)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")`, `quantity_refunded Decimal("4.00")` (a refund return of 4 completed).
2. RC = return "001", but completed.
3. rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "6")))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["quantity_returned"] == Decimal("6")`.

### PORM-V-15 — after a completed return, one more than is held is refused with the held quantity
- **Rules:** `validate_and_build_items` R3, R4 [BUG-2750]
- **Kind:** bug
- **Expect:** xfail BUG-2750
- **Fails today on:** Then 2 (detail says "only 2.00")

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")`, `quantity_refunded Decimal("4.00")`.
2. RC = return "001", but completed.
3. rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "7")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == TOO("7", 1, "6.00")`.
3. session clean.

### PORM-V-16 — after a completed return, more than is held is refused (today and after the fix)
- **Rules:** `validate_and_build_items` R3, R4
- **Kind:** error
- **Expect:** pass

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")`, `quantity_refunded Decimal("4.00")`.
2. RC = return "001", but completed.
3. rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "7")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail` starts with `"Cannot return 7 of line 1 — only "`.
3. session clean.
4. nothing written.
5. unchanged: unchanged(L1).

### PORM-V-17 — a completed replace return (no refund) is counted once
- **Rules:** `validate_and_build_items` R4 [BUG-2750]
- **Kind:** bug
- **Expect:** xfail BUG-2750
- **Fails today on:** Then 1 (the call raises HTTPException: today only 2.00 is available)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (a replace return of 4 completed; `quantity_refunded` stays 0.00).
2. RC = return "001", but `return_type "replace"`, completed.
3. rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "6")))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["quantity_returned"] == Decimal("6")`.

### PORM-V-18 — completed and pending together: the pending one alone reserves
- **Rules:** `validate_and_build_items` R4 [BUG-2750]
- **Kind:** bug
- **Expect:** xfail BUG-2750
- **Fails today on:** Then 1 (the call raises HTTPException: today 6 − 4 − 3 is below 0, so 0 is available)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")`, `quantity_refunded Decimal("4.00")`.
2. RC = return "001", but completed.
3. rline of RC on L1, "4.00".
4. RP = return "002".
5. rline of RP on L1, "3.00".
6. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "3")))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["quantity_returned"] == Decimal("3")`.

### PORM-V-19 — completed and pending together: more than the rest is refused (today and after)
- **Rules:** `validate_and_build_items` R3, R4
- **Kind:** error
- **Expect:** pass

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")`, `quantity_refunded Decimal("4.00")`.
2. RC = return "001", but completed.
3. rline of RC on L1, "4.00".
4. RP = return "002".
5. rline of RP on L1, "3.00".
6. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "4")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail` starts with `"Cannot return 4 of line 1 — only "`.
3. session clean.

### PORM-V-20 — a replace return completed and re-received: all ten can be returned
- **Rules:** `validate_and_build_items` R4 [BUG-2750] (spec Q1 example)
- **Kind:** bug
- **Expect:** xfail BUG-2750
- **Fails today on:** Then 1 (the call raises HTTPException: today only 6.00 is available)

**Given**
1. L1 = line 1, but `quantity_received Decimal("10.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, then 4 received again).
2. RC = return "001", but `return_type "replace"`, completed.
3. rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "10")))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["quantity_returned"] == Decimal("10")`.

### PORM-V-21 — the same line sent twice is added up and refused over the limit
- **Rules:** `validate_and_build_items` R5 [BUG-2751]; Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-2751
- **Fails today on:** Then 1 (no exception is raised: each 6 is checked alone)

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "6"), LN(L1, "6")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == TOO("12", 1, "10.00")`.
3. session clean.
4. nothing written.

### PORM-V-22 — repeats that fit stay separate lines, each with its own note
- **Rules:** `validate_and_build_items` R5 (fits), R1, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "6", notes="a"), LN(L1, "4", notes="b")))`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `result[0] == {"po_item_id": L1.id, "item_id": I1.id, "quantity_returned": Decimal("6"), "unit_price": Decimal("10.00"), "notes": "a"}`.
3. returns: `result[1] == {"po_item_id": L1.id, "item_id": I1.id, "quantity_returned": Decimal("4"), "unit_price": Decimal("10.00"), "notes": "b"}`.

### PORM-V-23 — three repeats are added up
- **Rules:** `validate_and_build_items` R5 [BUG-2751]
- **Kind:** bug
- **Expect:** xfail BUG-2751
- **Fails today on:** Then 1 (no exception is raised)

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "6"), LN(L1, "4"), LN(L1, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == TOO("11", 1, "10.00")`.
3. session clean.

### PORM-V-24 — repeats split by another line are still added up
- **Rules:** `validate_and_build_items` R5 [BUG-2751]
- **Kind:** bug
- **Expect:** xfail BUG-2751
- **Fails today on:** Then 1 (no exception is raised)

**Given**
1. L1 = line 1.
2. L2 = line 2.
3. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "6"), LN(L2, "1"), LN(L1, "6")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == TOO("12", 1, "10.00")`.
3. session clean.

### PORM-V-25 — repeats on top of a pending reservation fit the rest exactly
- **Rules:** `validate_and_build_items` R4, R5 (fits)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. L1 = line 1.
2. RP = return "001".
3. rline of RP on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "3"), LN(L1, "3")))`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `[d["quantity_returned"] for d in result] == [Decimal("3"), Decimal("3")]`.

### PORM-V-26 — repeats on top of a pending reservation are checked against the rest
- **Rules:** `validate_and_build_items` R4, R5 [BUG-2751]
- **Kind:** bug
- **Expect:** xfail BUG-2751
- **Fails today on:** Then 1 (no exception is raised: 4 and 3 each fit 6)

**Given**
1. L1 = line 1.
2. RP = return "001".
3. rline of RP on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "4"), LN(L1, "3")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == TOO("7", 1, "6.00")`.
3. session clean.

### PORM-V-27 — decimal repeats are added up exactly
- **Rules:** `validate_and_build_items` R5 [BUG-2751]
- **Kind:** bug
- **Expect:** xfail BUG-2751
- **Fails today on:** Then 1 (no exception is raised)

**Given**
1. L1 = line 1, but `quantity_ordered Decimal("1.00")`, `quantity_received Decimal("1.00")`.
2. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "0.6"), LN(L1, "0.5")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == TOO("1.1", 1, "1.00")`.
3. session clean.

### PORM-V-28 — a good line before a bad one does not help
- **Rules:** `validate_and_build_items` R1, R2
- **Kind:** error
- **Expect:** pass

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "2"), PurchaseOrderReturnItemCreate(po_item_id=MISSING, quantity_returned=Decimal("1"))))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == NOTHERE(999999999)`.
3. session clean.
4. nothing written.

### PORM-V-29 — the first failing line in request order decides the error (too many first)
- **Rules:** `validate_and_build_items` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "11"), PurchaseOrderReturnItemCreate(po_item_id=MISSING, quantity_returned=Decimal("1"))))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == TOO("11", 1, "10.00")`.
3. session clean.

### PORM-V-30 — the first failing line in request order decides the error (not on the order first)
- **Rules:** `validate_and_build_items` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(PurchaseOrderReturnItemCreate(po_item_id=MISSING, quantity_returned=Decimal("1")), LN(L1, "11")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == NOTHERE(999999999)`.
3. session clean.

### PORM-V-31 — an unknown line id does not belong
- **Rules:** `validate_and_build_items` R2; Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(PurchaseOrderReturnItemCreate(po_item_id=MISSING, quantity_returned=Decimal("1"))))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Item 999999999 does not belong to this purchase order"`.
3. session clean.
4. nothing written.

### PORM-V-32 — a line of the order with the lower id does not belong
- **Rules:** `validate_and_build_items` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. L1 = line 1.
2. LA = line 1, but `purchase_order_id O1.id`.
3. `db.expire_all()`.

**When**
- `result = V(REQ(LN(LA, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == NOTHERE(LA.id)`.
3. session clean.
4. unchanged: unchanged(LA).

### PORM-V-33 — a line of the order with the higher id does not belong
- **Rules:** `validate_and_build_items` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. L1 = line 1.
2. LC = line 1, but `purchase_order_id O3.id`.
3. `db.expire_all()`.

**When**
- `result = V(REQ(LN(LC, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == NOTHERE(LC.id)`.
3. session clean.

### PORM-V-34 — a W0 line on this order id does not belong
- **Rules:** `validate_and_build_items` R2 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. L1 = line 1.
2. LZ = line 2, but `workspace_id W0.id` (invalid data: a W0 line on the W1 order O2).
3. `db.expire_all()`.

**When**
- `result = V(REQ(LN(LZ, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == NOTHERE(LZ.id)`.
3. session clean.

### PORM-V-35 — a W2 line on this order id does not belong
- **Rules:** `validate_and_build_items` R2 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. L1 = line 1.
2. LN9 = line 2, but `workspace_id W2.id` (invalid data: a W2 line on the W1 order O2).
3. `db.expire_all()`.

**When**
- `result = V(REQ(LN(LN9, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == NOTHERE(LN9.id)`.
3. session clean.

### PORM-V-36 — W1's own line is not found when the caller's workspace is W2
- **Rules:** `validate_and_build_items` R2 (workspace gate)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = RM.validate_and_build_items(db, purchase_order_id=O2.id, workspace_id=W2.id, data=REQ(LN(L1, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == NOTHERE(L1.id)`.
3. session clean.

### PORM-V-37 — a line of a W2 order does not belong to a W1 order
- **Rules:** `validate_and_build_items` R2 (HR-16: only the id sent is echoed)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. L1 = line 1.
2. L9 = line 1, but `workspace_id W2.id`, `purchase_order_id O9.id`.
3. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L9, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == NOTHERE(L9.id)`.
3. session clean.

### PORM-V-38 — two decimals below the limit are accepted and kept as sent
- **Rules:** `validate_and_build_items` R3, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "9.99")))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["quantity_returned"] == Decimal("9.99")`.

### PORM-V-39 — a fractional received quantity: equal accepted
- **Rules:** `validate_and_build_items` R3, R4 (stored values)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. L1 = line 1, but `quantity_ordered Decimal("10.50")`, `quantity_received Decimal("10.50")`.
2. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "10.50")))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["quantity_returned"] == Decimal("10.50")`.

### PORM-V-40 — a fractional received quantity: one hundredth more refused
- **Rules:** `validate_and_build_items` R3, R4 (stored values)
- **Kind:** error
- **Expect:** pass

**Given**
1. L1 = line 1, but `quantity_ordered Decimal("10.50")`, `quantity_received Decimal("10.50")`.
2. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "10.51")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == TOO("10.51", 1, "10.50")`.
3. session clean.

### PORM-V-41 — fully reserved by a pending return: nothing more can be returned
- **Rules:** `validate_and_build_items` R3 (G1: `0` at zero), R4 (zero left)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. L1 = line 1.
2. RP = return "001".
3. rline of RP on L1, "10.00".
4. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "0.01")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot return 0.01 of line 1 — only 0 available to return"`.
3. session clean.

### PORM-V-42 — over-reserved line (invalid state): available never goes below 0
- **Rules:** `validate_and_build_items` R3 (G1: `0` below zero), R4 ("never below 0")
- **Kind:** boundary
- **Expect:** pass

**Given**
1. L1 = line 1.
2. RA = return "001".
3. rline of RA on L1, "6.00".
4. rline of RA on L1, "6.00" (what BUG-2751 lets through today: 12 reserved of 10).
5. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot return 1 of line 1 — only 0 available to return"` (never `-2.00`).
3. session clean.

### PORM-V-43 — a passing check writes nothing and leaves the order lines as they were
- **Rules:** `validate_and_build_items` R11
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. L1 = line 1.
2. L2 = line 2.
3. RP = return "001".
4. rline of RP on L1, "4.00".
5. Statement recorder on. `db.expunge_all()`.

**When**
- `result = V(REQ(LN(L1, "6"), LN(L2, "10")))`.

**Then**
1. returns: `len(result) == 2`.
2. session clean.
3. statement: `written == []`.
4. nothing written.
5. re-read L1: `quantity_received == Decimal("10.00")`, `quantity_returned == Decimal("0.00")`, `quantity_refunded == Decimal("0.00")`.
6. re-read L2: `quantity_received == Decimal("10.00")`, `quantity_returned == Decimal("0.00")`, `quantity_refunded == Decimal("0.00")`.

### PORM-V-44 — the order's lines are read with a row lock before the check
- **Rules:** `validate_and_build_items` R9 [BUG-2753] (HR-10)
- **Kind:** bug
- **Expect:** xfail BUG-2753
- **Fails today on:** Then 2 (no recorded SELECT carries FOR UPDATE)

**Given**
1. L1 = line 1.
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = V(REQ(LN(L1, "4")))`.

**Then**
1. returns: `len(result) == 1`.
2. statement: locks `purchase_order_items`, or locks `purchase_orders` (either table, as the spec allows).
3. statement: `written == []`.

### PORM-V-51 — a W0 return line pointing at this line reserves nothing
- **Rules:** `validate_and_build_items` R4a [BUG-2792] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-2792
- **Fails today on:** Then 1 (the call raises HTTPException: today the W0 line reserves 4, only 6.00 is available)

**Given**
1. L1 = line 1.
2. R0 = return "000", but `workspace_id W0.id` (invalid data: on the W1 order O2).
3. rline of R0 on L1, "4.00" (its `workspace_id` is W0, as R0's).
4. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "10")))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["quantity_returned"] == Decimal("10")`.

### PORM-V-52 — a W2 return line pointing at this line reserves nothing
- **Rules:** `validate_and_build_items` R4a [BUG-2792] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-2792
- **Fails today on:** Then 1 (the call raises HTTPException: today the W2 line reserves 4)

**Given**
1. L1 = line 1.
2. R9 = return "009", but `workspace_id W2.id` (invalid data: on the W1 order O2).
3. rline of R9 on L1, "4.00" (its `workspace_id` is W2, as R9's).
4. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "10")))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["quantity_returned"] == Decimal("10")`.

### PORM-V-53 — a return line of W2 on a W1 pending return reserves nothing
- **Rules:** `validate_and_build_items` R4a [BUG-2792] (both the line and its return must be of this workspace)
- **Kind:** bug
- **Expect:** xfail BUG-2792
- **Fails today on:** Then 1 (the call raises HTTPException: today the line reserves 4)

**Given**
1. L1 = line 1.
2. R = return "001".
3. rline of R on L1, "4.00", but `workspace_id W2.id` (invalid data).
4. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "10")))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["quantity_returned"] == Decimal("10")`.

### PORM-V-54 — an unknown line between two repeats wins over the repeat that would go over
- **Rules:** `validate_and_build_items` R1, R5 (running total: the first failing line in request order wins)
- **Kind:** error
- **Expect:** pass

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "6"), PurchaseOrderReturnItemCreate(po_item_id=MISSING, quantity_returned=Decimal("99")), LN(L1, "6")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == NOTHERE(999999999)`.
3. session clean.

### PORM-V-55 — a repeat that goes over wins over an unknown line after it
- **Rules:** `validate_and_build_items` R1, R5 [BUG-2751] (running total)
- **Kind:** bug
- **Expect:** xfail BUG-2751
- **Fails today on:** Then 2 (detail today is NOTHERE(999999999): the repeats are not added up)

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "6"), LN(L1, "6"), PurchaseOrderReturnItemCreate(po_item_id=MISSING, quantity_returned=Decimal("99"))))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == TOO("12", 1, "10.00")`.
3. session clean.

### PORM-V-56 — the error names the running total at the repeat that goes over, not the grand total
- **Rules:** `validate_and_build_items` R5 [BUG-2751] (running total)
- **Kind:** bug
- **Expect:** xfail BUG-2751
- **Fails today on:** Then 1 (no exception is raised)

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "6"), LN(L1, "6"), LN(L1, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == TOO("12", 1, "10.00")`.
3. session clean.

## Schemas `PurchaseOrderReturnCreate` / `PurchaseOrderReturnItemCreate`

### PORM-SCH-01 — an empty line list is refused
- **Rules:** `validate_and_build_items` Inputs; Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- build `PurchaseOrderReturnCreate(return_type="refund", reason="Faulty", items=[])` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: message contains `"At least one item must be selected for return"`.

### PORM-SCH-02 — a zero quantity is refused
- **Rules:** `validate_and_build_items` Inputs; Errors row 3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- build `PurchaseOrderReturnCreate(return_type="refund", reason="Faulty", items=[PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("0"))])` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: message contains `"All return quantities must be positive"`.

### PORM-SCH-03 — a negative quantity is refused
- **Rules:** `validate_and_build_items` Inputs; Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- build `PurchaseOrderReturnCreate(return_type="refund", reason="Faulty", items=[PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("-1"))])` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: message contains `"All return quantities must be positive"`.

### PORM-SCH-04 — the smallest positive quantity passes
- **Rules:** `validate_and_build_items` Inputs (other side of > 0), R10 (2 decimals allowed)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = PurchaseOrderReturnCreate(return_type="refund", reason="Faulty", items=[PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("0.01"))])` (target `schema`).

**Then**
1. returns: `result.items[0].quantity_returned == Decimal("0.01")`.
2. returns: `result.items[0].unit_price is None` and `result.items[0].notes is None` (defaults).

### PORM-SCH-05 — a return type other than replace / refund is refused
- **Rules:** `validate_and_build_items` Inputs; Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- build `PurchaseOrderReturnCreate(return_type="exchange", reason="Faulty", items=[PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("1"))])` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: loc `== ("return_type",)`.

### PORM-SCH-06 — the return type is compared exactly (capital letter refused)
- **Rules:** `validate_and_build_items` Inputs
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- build `PurchaseOrderReturnCreate(return_type="Refund", reason="Faulty", items=[PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("1"))])` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: loc `== ("return_type",)`.

### PORM-SCH-07 — return type `replace` passes
- **Rules:** `validate_and_build_items` Inputs
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = PurchaseOrderReturnCreate(return_type="replace", reason="Faulty", items=[PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("1"))])` (target `schema`).

**Then**
1. returns: `result.return_type == "replace"`.

### PORM-SCH-15 — return type `refund` passes
- **Rules:** `validate_and_build_items` Inputs
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = PurchaseOrderReturnCreate(return_type="refund", reason="Faulty", items=[PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("1"))])` (target `schema`).

**Then**
1. returns: `result.return_type == "refund"`.

### PORM-SCH-08 — a quantity with 3 decimals is refused
- **Rules:** `validate_and_build_items` R10 [BUG-2752]; Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-2752
- **Fails today on:** Then 1 (no error: `0.004` passes the > 0 check)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("0.004"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: loc `== ("quantity_returned",)`.

### PORM-SCH-09 — a quantity of 1.001 is refused
- **Rules:** `validate_and_build_items` R10 [BUG-2752]
- **Kind:** bug
- **Expect:** xfail BUG-2752
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("1.001"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: loc `== ("quantity_returned",)`.

### PORM-SCH-10 — a price with 3 decimals is refused
- **Rules:** `validate_and_build_items` R10 [BUG-2752]
- **Kind:** bug
- **Expect:** xfail BUG-2752
- **Fails today on:** Then 1 (no error: `1.005` is accepted and later stored `1.01`)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("1"), unit_price=Decimal("1.005"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: loc `== ("unit_price",)`.

### PORM-SCH-11 — a quantity with 14 integer digits is refused
- **Rules:** `validate_and_build_items` R10 [BUG-2752]
- **Kind:** bug
- **Expect:** xfail BUG-2752
- **Fails today on:** Then 1 (no error: today it fails only at the flush)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("10000000000000"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: loc `== ("quantity_returned",)`.

### PORM-SCH-12 — a price with 14 integer digits is refused
- **Rules:** `validate_and_build_items` R10 [BUG-2752]
- **Kind:** bug
- **Expect:** xfail BUG-2752
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("1"), unit_price=Decimal("10000000000000"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: loc `== ("unit_price",)`.

### PORM-SCH-13 — 13 integer digits and 2 decimals pass in quantity and price
- **Rules:** `validate_and_build_items` R10 (the valid side of both limits)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("9999999999999.99"), unit_price=Decimal("9999999999999.99"))` (target `schema`).

**Then**
1. returns: `result.quantity_returned == Decimal("9999999999999.99")`.
2. returns: `result.unit_price == Decimal("9999999999999.99")`.

### PORM-SCH-14 — a whole quantity with trailing zero decimals passes
- **Rules:** `validate_and_build_items` R10 (`"5.00"` has 2 decimals)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("5.00"), unit_price=Decimal("2.50"))` (target `schema`).

**Then**
1. returns: `result.quantity_returned == Decimal("5.00")`.
2. returns: `result.unit_price == Decimal("2.50")`.

### PORM-SCH-16 — only `return_type` and `items` are required on the return
- **Rules:** `validate_and_build_items` Inputs (G2)
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = PurchaseOrderReturnCreate(return_type="refund", items=[PurchaseOrderReturnItemCreate(po_item_id=1, quantity_returned=Decimal("1"))])` (target `schema`).

**Then**
1. returns: `result.reason is None`.
2. returns: `result.notes is None`.
3. returns: `len(result.items) == 1`.

### PORM-SCH-17 — a line without a quantity is refused
- **Rules:** `validate_and_build_items` Inputs (G2: line id and quantity required)
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- build `PurchaseOrderReturnItemCreate(po_item_id=1)` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: loc `== ("quantity_returned",)`.

### PORM-SCH-18 — a line without the order line id is refused
- **Rules:** `validate_and_build_items` Inputs (G2)
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- build `PurchaseOrderReturnItemCreate(quantity_returned=Decimal("1"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: loc `== ("po_item_id",)`.

## `PurchaseOrderReturnManager.get_return`

### PORM-G-01 — a pending return of this order is returned
- **Rules:** `get_return` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. R = return "001".

**When**
- `result = RM.get_return(db, return_id=R.id, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, PurchaseOrderReturn)`.
2. returns: `result.id == R.id`.
3. returns: `result.status == "pending"`.

### PORM-G-02 — a completed return is returned too
- **Rules:** `get_return` R1 (any status)
- **Kind:** happy
- **Expect:** pass

**Given**
1. RC = return "001", but completed.

**When**
- `result = RM.get_return(db, return_id=RC.id, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == RC.id`.
2. returns: `result.status == "completed"`, `result.completed_by == U1.id`.

### PORM-G-03 — an unknown id is 404
- **Rules:** `get_return` R2; Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. R = return "001".

**When**
- `result = RM.get_return(db, return_id=MISSING, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Return with ID 999999999 not found"`.
3. session clean.

### PORM-G-04 — a return of the lower-id order is 404 when asked under this order
- **Rules:** `get_return` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. RA = return "001", but `purchase_order_id O1.id`.

**When**
- `result = RM.get_return(db, return_id=RA.id, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Return with ID {RA.id} not found"`.
3. session clean.

### PORM-G-05 — a return of the higher-id order is 404 when asked under this order
- **Rules:** `get_return` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. RC3 = return "003", but `purchase_order_id O3.id`.

**When**
- `result = RM.get_return(db, return_id=RC3.id, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Return with ID {RC3.id} not found"`.
3. session clean.

### PORM-G-06 — a W0 return on this order id is 404
- **Rules:** `get_return` R2 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. R0 = return "000", but `workspace_id W0.id` (invalid data: on the W1 order O2).

**When**
- `result = RM.get_return(db, return_id=R0.id, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Return with ID {R0.id} not found"`.
3. session clean.

### PORM-G-07 — a W2 return on this order id is 404
- **Rules:** `get_return` R2 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. R9 = return "009", but `workspace_id W2.id` (invalid data: on O2).

**When**
- `result = RM.get_return(db, return_id=R9.id, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Return with ID {R9.id} not found"`.
3. session clean.

### PORM-G-08 — a W1 return is 404 to a caller in W0
- **Rules:** `get_return` R2 (workspace gate, lower side)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. R = return "001".

**When**
- `result = RM.get_return(db, return_id=R.id, purchase_order_id=O2.id, workspace_id=W0.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Return with ID {R.id} not found"`.

### PORM-G-09 — the default read writes nothing and takes no lock
- **Rules:** `get_return` R3, R4 (default `False` reads without a lock)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. R = return "001".
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = RM.get_return(db, return_id=R.id, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == R.id`.
2. session clean.
3. statement: `written == []`.
4. statement: no lock.

### PORM-G-10 — `for_update=True` reads the return row with a lock
- **Rules:** `get_return` R4 [BUG-2754] (HR-10)
- **Kind:** bug
- **Expect:** xfail BUG-2754
- **Fails today on:** Then 1 (the call raises TypeError: there is no `for_update` parameter)

**Given**
1. R = return "001".
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = RM.get_return(db, return_id=R.id, purchase_order_id=O2.id, workspace_id=W1.id, for_update=True)`.

**Then**
1. returns: `result.id == R.id`.
2. returns: `result.status == "pending"`.
3. statement: locks `purchase_order_returns`.
4. statement: `written == []`.

### PORM-G-11 — `for_update=True` still refuses a return of another workspace
- **Rules:** `get_return` R2, R4 [BUG-2754]
- **Kind:** bug
- **Expect:** xfail BUG-2754
- **Fails today on:** Then 1 (the call raises TypeError, not HTTPException)

**Given**
1. R9 = return "009", but `workspace_id W2.id` (invalid data: on O2).

**When**
- `result = RM.get_return(db, return_id=R9.id, purchase_order_id=O2.id, workspace_id=W1.id, for_update=True)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Return with ID {R9.id} not found"`.
3. session clean.

### PORM-G-12 — `for_update=False` is the unlocked read
- **Rules:** `get_return` R4 [BUG-2754]
- **Kind:** bug
- **Expect:** xfail BUG-2754
- **Fails today on:** Then 1 (the call raises TypeError: there is no `for_update` parameter)

**Given**
1. R = return "001".
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = RM.get_return(db, return_id=R.id, purchase_order_id=O2.id, workspace_id=W1.id, for_update=False)`.

**Then**
1. returns: `result.id == R.id`.
2. statement: no lock.

### PORM-G-13 — the return's lines are read in id order
- **Rules:** `get_return` R5 [BUG-2755] (HR-6)
- **Kind:** bug
- **Expect:** xfail BUG-2755
- **Fails today on:** Then 2 (the lines' SELECT has no ORDER BY)

**Given**
1. L1 = line 1.
2. R = return "001".
3. A = rline of R on L1, "1.00". B = rline of R on L1, "2.00".
4. Statement recorder on. `db.expunge_all()`.

**When**
- `result = RM.get_return(db, return_id=R.id, purchase_order_id=O2.id, workspace_id=W1.id)`, then `lines = list(result.items)`.

**Then**
1. returns: `sorted(x.id for x in lines) == [A.id, B.id]`.
2. statement: some `s` in `sel("purchase_order_return_items")` has `"purchase_order_return_items.id" in order_part(s)`.

### PORM-G-14 — the return's lines come back in id order after an update moves one
- **Rules:** `get_return` R5 [BUG-2755]
- **Kind:** bug
- **Expect:** xfail BUG-2755 (non-strict)
- **Fails today on:** Then 1 (the physical order after the update puts A last; non-strict because physical order is not fixed)
- **Author:** claude

**Given**
1. L1 = line 1.
2. R = return "001".
3. A = rline of R on L1, "1.00". B = rline of R on L1, "2.00". C = rline of R on L1, "3.00".
4. seqscan.
5. bumpL(A).

**When**
- `result = RM.get_return(db, return_id=R.id, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `[x.id for x in result.items] == [A.id, B.id, C.id]`.

### PORM-G-15 — a voided return is returned too
- **Rules:** `get_return` R1 (any status)
- **Kind:** happy
- **Expect:** pass

**Given**
1. RV = return "002", but voided.

**When**
- `result = RM.get_return(db, return_id=RV.id, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == RV.id`.
2. returns: `result.status == "voided"`.

### PORM-G-16 — a W1 return is 404 to a caller in W2
- **Rules:** `get_return` R2 (workspace gate, higher side)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. R = return "001".

**When**
- `result = RM.get_return(db, return_id=R.id, purchase_order_id=O2.id, workspace_id=W2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Return with ID {R.id} not found"`.

### PORM-G-17 — the return's lines are exactly its own lines
- **Rules:** `get_return` R1, R5 (the part that holds today: which lines, not their order)
- **Kind:** happy
- **Expect:** pass

**Given**
1. L1 = line 1.
2. R = return "001".
3. A = rline of R on L1, "1.00". B = rline of R on L1, "2.00".
4. R2 = return "002".
5. C = rline of R2 on L1, "3.00".

**When**
- `result = RM.get_return(db, return_id=R.id, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(x.id for x in result.items) == [A.id, B.id]`.
2. returns: `sorted(x.quantity_returned for x in result.items) == [Decimal("1.00"), Decimal("2.00")]`.

## `PurchaseOrderReturnManager.list_returns`

### PORM-L-01 — the order's returns come newest first
- **Rules:** `list_returns` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. RA = return "001", but `created_at T1`.
2. RB = return "002", but `created_at T3`.
3. RC = return "003", but `created_at T2`.

**When**
- `result = RM.list_returns(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [RB.id, RC.id, RA.id]`.

### PORM-L-02 — every status is listed
- **Rules:** `list_returns` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. RP = return "001", but `created_at T1`.
2. RC = return "002", but `created_at T2`, completed.
3. RV = return "003", but `created_at T3`, voided.

**When**
- `result = RM.list_returns(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [RV.id, RC.id, RP.id]`.
2. returns: `[r.status for r in result] == ["voided", "completed", "pending"]`.

### PORM-L-03 — returns of the orders on both sides are not listed
- **Rules:** `list_returns` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. RA = return "001", but `purchase_order_id O1.id`, `created_at T3`.
2. RB = return "002", but `created_at T1`.
3. RC = return "003", but `purchase_order_id O3.id`, `created_at T2`.

**When**
- `result = RM.list_returns(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [RB.id]`.

### PORM-L-04 — W0 and W2 returns on this order id are not listed
- **Rules:** `list_returns` R1 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. R0 = return "000", but `workspace_id W0.id`, `created_at T3` (invalid data: on O2).
2. RB = return "002", but `created_at T1`.
3. R9 = return "009", but `workspace_id W2.id`, `created_at T2` (invalid data: on O2).

**When**
- `result = RM.list_returns(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [RB.id]`.

### PORM-L-05 — an unknown order gets an empty list
- **Rules:** `list_returns` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. RB = return "002".

**When**
- `result = RM.list_returns(db, purchase_order_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PORM-L-06 — the list writes nothing and takes no lock
- **Rules:** `list_returns` R1 (Side effects: none)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. RB = return "002".
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = RM.list_returns(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [RB.id]`.
2. session clean.
3. statement: `written == []`.
4. statement: no lock.

### PORM-L-07 — returns of one creation time are broken by id, newest first
- **Rules:** `list_returns` R1 (DAO tie-break, BUG-2429)
- **Kind:** bug
- **Expect:** xfail BUG-2429
- **Fails today on:** Then 2 (the ORDER BY has no `id` key)

**Given**
1. RA = return "001", but `created_at T2`.
2. RB = return "002", but `created_at T2`.
3. Statement recorder on. `db.expunge_all()`.

**When**
- `result = RM.list_returns(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(r.id for r in result) == [RA.id, RB.id]`.
2. statement: some `s` in `sel("purchase_order_returns")` has `"purchase_order_returns.id DESC" in order_part(s)`.

### PORM-L-08 — each listed return's lines are read in id order
- **Rules:** `list_returns` R2 [BUG-2755]
- **Kind:** bug
- **Expect:** xfail BUG-2755
- **Fails today on:** Then 2 (the lines' SELECT has no ORDER BY)

**Given**
1. L1 = line 1.
2. R = return "001".
3. A = rline of R on L1, "1.00". B = rline of R on L1, "2.00".
4. Statement recorder on. `db.expunge_all()`.

**When**
- `result = RM.list_returns(db, purchase_order_id=O2.id, workspace_id=W1.id)`, then `lines = list(result[0].items)`.

**Then**
1. returns: `sorted(x.id for x in lines) == [A.id, B.id]`.
2. statement: some `s` in `sel("purchase_order_return_items")` has `"purchase_order_return_items.id" in order_part(s)`.

### PORM-L-09 — listed lines come back in id order after an update moves one
- **Rules:** `list_returns` R2 [BUG-2755]
- **Kind:** bug
- **Expect:** xfail BUG-2755 (non-strict)
- **Fails today on:** Then 1 (the physical order after the update puts A last; non-strict because physical order is not fixed)
- **Author:** claude

**Given**
1. L1 = line 1.
2. R = return "001".
3. A = rline of R on L1, "1.00". B = rline of R on L1, "2.00". C = rline of R on L1, "3.00".
4. seqscan.
5. bumpL(A).

**When**
- `result = RM.list_returns(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `[x.id for x in result[0].items] == [A.id, B.id, C.id]`.

### PORM-L-10 — a caller in W0 sees none of W1's returns
- **Rules:** `list_returns` R1 (workspace gate, lower side)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. RB = return "002".

**When**
- `result = RM.list_returns(db, purchase_order_id=O2.id, workspace_id=W0.id)`.

**Then**
1. returns: `result == []`.

### PORM-L-11 — a caller in W2 sees none of W1's returns
- **Rules:** `list_returns` R1 (workspace gate, higher side)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. RB = return "002".

**When**
- `result = RM.list_returns(db, purchase_order_id=O2.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PORM-L-12 — each listed return carries exactly its own lines
- **Rules:** `list_returns` R1, R2 (the part that holds today: which lines, not their order)
- **Kind:** happy
- **Expect:** pass

**Given**
1. L1 = line 1.
2. RA = return "001", but `created_at T1`.
3. A = rline of RA on L1, "1.00". B = rline of RA on L1, "2.00".
4. RB = return "002", but `created_at T2`.
5. C = rline of RB on L1, "3.00".

**When**
- `result = RM.list_returns(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [RB.id, RA.id]`.
2. returns: `sorted(x.id for x in result[0].items) == [C.id]`.
3. returns: `sorted(x.id for x in result[1].items) == [A.id, B.id]`.

## `PurchaseOrderReturnManager.sync_return_paid`

Every card here builds the return with `updated_at T1` and `updated_by None`, so a write can be seen.

### PORM-S-01 — a fully paid credit note sets `paid` and reports the change
- **Rules:** `sync_return_paid` R1, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. CN = credit note of W1, `"paid"`.
2. R = return "001", but `invoice_id CN.id`, `paid False`, `updated_at T1`.

**When**
- `result = RM.sync_return_paid(db, ret=R, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. re-read R: `paid is True`.
3. re-read R: `updated_at != T1`.
4. re-read R: `status == "pending"`, `updated_by is None`, `completed_at is None`, `completed_by is None`, `invoice_id == CN.id`.
5. re-read CN: `payment_status == "paid"`.

### PORM-S-02 — a partly paid credit note clears `paid`
- **Rules:** `sync_return_paid` R2, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. CN = credit note of W1, `"partial"`.
2. R = return "001", but `invoice_id CN.id`, `paid True`, `updated_at T1`.

**When**
- `result = RM.sync_return_paid(db, ret=R, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. re-read R: `paid is False`.
3. re-read R: `updated_at != T1`.

### PORM-S-03 — an unpaid credit note clears `paid`
- **Rules:** `sync_return_paid` R2, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. CN = credit note of W1, `"unpaid"`.
2. R = return "001", but `invoice_id CN.id`, `paid True`, `updated_at T1`.

**When**
- `result = RM.sync_return_paid(db, ret=R, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. re-read R: `paid is False`.

### PORM-S-04 — an overdue credit note clears `paid`
- **Rules:** `sync_return_paid` R2, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CN = credit note of W1, `"overdue"`.
2. R = return "001", but `invoice_id CN.id`, `paid True`, `updated_at T1`.

**When**
- `result = RM.sync_return_paid(db, ret=R, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. re-read R: `paid is False`.

### PORM-S-05 — already paid and still paid: no change, nothing flushed
- **Rules:** `sync_return_paid` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CN = credit note of W1, `"paid"`.
2. R = return "001", but `invoice_id CN.id`, `paid True`, `updated_at T1`.
3. Statement recorder on.

**When**
- `result = RM.sync_return_paid(db, ret=R, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.
2. session: `R not in db.dirty`.
3. statement: `written == []`.
4. re-read R: `paid is True`, `updated_at == T1`.

### PORM-S-06 — not paid and still not paid: no change, nothing flushed
- **Rules:** `sync_return_paid` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CN = credit note of W1, `"partial"`.
2. R = return "001", but `invoice_id CN.id`, `paid False`, `updated_at T1`.
3. Statement recorder on.

**When**
- `result = RM.sync_return_paid(db, ret=R, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.
2. session: `R not in db.dirty`.
3. statement: `written == []`.
4. re-read R: `paid is False`, `updated_at == T1`.

### PORM-S-07 — no credit note: `paid` is cleared
- **Rules:** `sync_return_paid` R3, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. R = return "001", but `invoice_id None`, `paid True`, `updated_at T1`.

**When**
- `result = RM.sync_return_paid(db, ret=R, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. re-read R: `paid is False`.
3. re-read R: `updated_at != T1`.

### PORM-S-08 — no credit note and not paid: nothing changes
- **Rules:** `sync_return_paid` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. R = return "001", but `invoice_id None`, `paid False`, `updated_at T1`.
2. Statement recorder on.

**When**
- `result = RM.sync_return_paid(db, ret=R, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.
2. statement: `written == []`.
3. re-read R: `paid is False`, `updated_at == T1`.

### PORM-S-09 — a paid invoice of W0 does not count as this return's credit note
- **Rules:** `sync_return_paid` R1, R3 (HR-16, lower workspace id)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. C0 = credit note of W0, `"paid"`.
2. R = return "001", but `invoice_id C0.id` (invalid data), `paid False`, `updated_at T1`.
3. Statement recorder on.

**When**
- `result = RM.sync_return_paid(db, ret=R, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.
2. statement: `written == []`.
3. re-read R: `paid is False`, `updated_at == T1`.
4. unchanged: unchanged(C0).

### PORM-S-10 — a paid invoice of W2 does not keep `paid` set
- **Rules:** `sync_return_paid` R1, R3 (HR-16, higher workspace id)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. C9 = credit note of W2, `"paid"`.
2. R = return "001", but `invoice_id C9.id` (invalid data), `paid True`, `updated_at T1`.

**When**
- `result = RM.sync_return_paid(db, ret=R, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. re-read R: `paid is False`.
3. unchanged: unchanged(C9).

### PORM-S-11 — a voided credit note clears `paid`
- **Rules:** `sync_return_paid` R2 (owner freeze: a return credit note is voidable)
- **Kind:** happy
- **Expect:** pass

**Given**
1. CN = voided credit note.
2. R = return "001", but `invoice_id CN.id`, `paid True`, `updated_at T1`.

**When**
- `result = RM.sync_return_paid(db, ret=R, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. re-read R: `paid is False`.
3. re-read CN: `invoice_status == "voided"`, `payment_status == "unpaid"` (the credit note itself is not touched).

### PORM-S-12 — a completed return follows its credit note too, and keeps its completion
- **Rules:** `sync_return_paid` R1, R5 (any status; `completed_*` untouched)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CN = credit note of W1, `"paid"`.
2. R = return "001", but completed, `invoice_id CN.id`, `paid False`, `updated_at T1`.

**When**
- `result = RM.sync_return_paid(db, ret=R, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. re-read R: `paid is True`.
3. re-read R: `status == "completed"`, `completed_at == T4`, `completed_by == U1.id`, `updated_by is None`.

### PORM-S-13 — a change is flushed in the call, as one UPDATE of the return
- **Rules:** `sync_return_paid` R5 (flushed)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CN = credit note of W1, `"paid"`.
2. R = return "001", but `invoice_id CN.id`, `paid False`, `updated_at T1`.
3. Statement recorder on.

**When**
- `result = RM.sync_return_paid(db, ret=R, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. session: `R not in db.dirty`.
3. statement: `len(written) == 1`.
4. statement: `written[0]` starts with `"UPDATE purchase_order_returns"`.
5. statement: no lock.

### PORM-S-14 — the change is not committed
- **Rules:** `sync_return_paid` R5 (not committed)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CN = credit note of W1, `"paid"`.
2. R = return "001", but `invoice_id CN.id`, `paid False`, `updated_at T1`.

**When**
- commit spy around `result = RM.sync_return_paid(db, ret=R, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. inside: re-read R: `paid is True`.
3. after: `cm.call_count == 0`.
4. after: re-read R: `paid is False`, `updated_at == T1`.

## `PurchaseOrderReturnManager.validate_replacement_receipt` — new method (BUG-2810, owner 2026-11-19)

Every card is a strict xfail BUG-2810, because neither the method nor the schema exists yet. Replacement goods for a completed `replace` return come in through the return; the purchase order stays completed with its invoice frozen. This manager only checks. The writes (quantity_replaced, PO line quantity_received, stock in, ledger rows, PO event) are deferred to `PurchaseOrderService.receive_replacements` (FU-2). Cards that set `quantity_replaced` fail in their Given today and are marked `Author: claude`.

### PORM-RR-01 — a full replacement of one line is accepted at the original line cost
- **Rules:** `validate_replacement_receipt` RR5 (equal side), RR6, Returns
- **Kind:** happy
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((A, "4")))`.

**Then**
1. returns: `result == [{"return_item_id": A.id, "po_item_id": L1.id, "item_id": I1.id, "quantity": Decimal("4"), "unit_cost": Decimal("10.00")}]`.
2. returns: `type(result) is list` and `type(result[0]) is dict`.

### PORM-RR-02 — two lines come back in request order, each at its own PO line cost
- **Rules:** `validate_replacement_receipt` RR3, RR6, Returns
- **Kind:** happy
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00".
4. L2 = line 2, but `unit_price Decimal("4.00")`, `quantity_received Decimal("8.00")`, `quantity_returned Decimal("2.00")`.
5. B = rline of RC on L2, "2.00".
6. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((B, "1.5"), (A, "2")))`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `result[0] == {"return_item_id": B.id, "po_item_id": L2.id, "item_id": I2.id, "quantity": Decimal("1.5"), "unit_cost": Decimal("4.00")}`.
3. returns: `result[1] == {"return_item_id": A.id, "po_item_id": L1.id, "item_id": I1.id, "quantity": Decimal("2"), "unit_cost": Decimal("10.00")}`.

### PORM-RR-03 — one hundredth below what is left is accepted
- **Rules:** `validate_replacement_receipt` RR5
- **Kind:** boundary
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((A, "3.99")))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["quantity"] == Decimal("3.99")`.

### PORM-RR-04 — one hundredth over what was returned is refused
- **Rules:** `validate_replacement_receipt` RR5; Errors row 4
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((A, "4.01")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == RTOO("4.01", 1, "4.00")`.
3. session clean.
4. nothing written.
5. unchanged: unchanged(A).
6. unchanged: unchanged(L1).

### PORM-RR-05 — replacements already received lower the limit: the rest is accepted
- **Rules:** `validate_replacement_receipt` RR5 (already replaced counts)
- **Kind:** boundary
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the test fails before the call: the Given sets `quantity_replaced`, a column that does not exist yet; the method does not exist either)
- **Author:** claude

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00".
4. A has `quantity_replaced Decimal("3.00")` (3 already received).
5. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((A, "1")))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["quantity"] == Decimal("1")`.

### PORM-RR-06 — replacements already received lower the limit: more than the rest is refused
- **Rules:** `validate_replacement_receipt` RR5 (already replaced counts); Errors row 4
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the test fails before the call: the Given sets `quantity_replaced`, a column that does not exist yet; the method does not exist either)
- **Author:** claude

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00".
4. A has `quantity_replaced Decimal("3.00")`.
5. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((A, "2")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == RTOO("2", 1, "1.00")`.
3. session clean.
4. nothing written.

### PORM-RR-07 — a line fully replaced already: nothing is left, printed as 0
- **Rules:** `validate_replacement_receipt` RR5 (`0` when nothing is left)
- **Kind:** boundary
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the test fails before the call: the Given sets `quantity_replaced`, a column that does not exist yet; the method does not exist either)
- **Author:** claude

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00".
4. A has `quantity_replaced Decimal("4.00")`.
5. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((A, "0.01")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == RTOO("0.01", 1, "0")`.
3. session clean.

### PORM-RR-08 — the same line twice is added up (running total)
- **Rules:** `validate_replacement_receipt` RR5 (running total)
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((A, "3"), (A, "2")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == RTOO("5", 1, "4.00")`.
3. session clean.

### PORM-RR-09 — the running total is added to what was already received
- **Rules:** `validate_replacement_receipt` RR5 (running total + already replaced)
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the test fails before the call: the Given sets `quantity_replaced`, a column that does not exist yet; the method does not exist either)
- **Author:** claude

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00".
4. A has `quantity_replaced Decimal("1.00")`.
5. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((A, "2"), (A, "2")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == RTOO("4", 1, "3.00")`.
3. session clean.

### PORM-RR-10 — repeats that fit stay separate entries
- **Rules:** `validate_replacement_receipt` RR3, RR5 (fits)
- **Kind:** boundary
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((A, "2"), (A, "2")))`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `[d["quantity"] for d in result] == [Decimal("2"), Decimal("2")]`.
3. returns: `[d["return_item_id"] for d in result] == [A.id, A.id]`.

### PORM-RR-11 — a refund return cannot receive replacements
- **Rules:** `validate_replacement_receipt` RR1; Errors row 1
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")`, `quantity_refunded Decimal("4.00")`.
2. RC = return "001", but completed (`return_type "refund"`).
3. A = rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((A, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Only a replace return can receive replacements"`.
3. session clean.
4. nothing written.

### PORM-RR-12 — a pending replace return cannot receive replacements yet
- **Rules:** `validate_replacement_receipt` RR2; Errors row 2
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1.
2. RC = return "001", but `return_type "replace"` (pending).
3. A = rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((A, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Complete the return before receiving replacements"`.
3. session clean.
4. nothing written.

### PORM-RR-13 — a voided replace return cannot receive replacements
- **Rules:** `validate_replacement_receipt` RR2; Errors row 2
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1.
2. RC = return "001", but `return_type "replace"`, voided.
3. A = rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((A, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Complete the return before receiving replacements"`.
3. session clean.

### PORM-RR-14 — check order: the return type is checked before the status
- **Rules:** `validate_replacement_receipt` RR1 before RR2
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1.
2. RC = return "001" (`return_type "refund"`, pending).
3. A = rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((A, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Only a replace return can receive replacements"`.
3. session clean.

### PORM-RR-15 — check order: the status is checked before the lines
- **Rules:** `validate_replacement_receipt` RR2 before RR4, RR5
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1.
2. RC = return "001", but `return_type "replace"` (pending).
3. A = rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((MISSING, "99")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Complete the return before receiving replacements"`.
3. session clean.

### PORM-RR-16 — an unknown line id is not part of the return
- **Rules:** `validate_replacement_receipt` RR4; Errors row 3
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((MISSING, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == NOTPART(999999999, RC)`.
3. session clean.
4. nothing written.

### PORM-RR-17 — a line of a return with a lower id is not part of this return
- **Rules:** `validate_replacement_receipt` RR4
- **Kind:** isolation
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")`.
2. RA = return "000", but `return_type "replace"`, completed.
3. X = rline of RA on L1, "1.00".
4. RC = return "001", but `return_type "replace"`, completed.
5. A = rline of RC on L1, "3.00".
6. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((X, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == NOTPART(X.id, RC)`.
3. session clean.
4. unchanged: unchanged(X).

### PORM-RR-18 — a line of a return with a higher id is not part of this return
- **Rules:** `validate_replacement_receipt` RR4
- **Kind:** isolation
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00".
4. RB = return "002", but `return_type "replace"`, completed.
5. Y = rline of RB on L1, "1.00".
6. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((Y, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == NOTPART(Y.id, RC)`.
3. session clean.

### PORM-RR-19 — a W0 line on this return is not part of it
- **Rules:** `validate_replacement_receipt` RR4 (HR-16)
- **Kind:** isolation
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00".
4. Z = rline of RC on L1, "1.00", but `workspace_id W0.id` (invalid data).
5. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((Z, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == NOTPART(Z.id, RC)`.
3. session clean.

### PORM-RR-20 — a W2 line on this return is not part of it
- **Rules:** `validate_replacement_receipt` RR4 (HR-16)
- **Kind:** isolation
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00".
4. Z = rline of RC on L1, "1.00", but `workspace_id W2.id` (invalid data).
5. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((Z, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == NOTPART(Z.id, RC)`.
3. session clean.

### PORM-RR-21 — a caller in W0 sees none of the return's lines
- **Rules:** `validate_replacement_receipt` RR4 (workspace gate, lower side)
- **Kind:** isolation
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = RM.validate_replacement_receipt(db, ret=RC, workspace_id=W0.id, data=RRQ((A, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == NOTPART(A.id, RC)`.
3. session clean.

### PORM-RR-22 — a caller in W2 sees none of the return's lines
- **Rules:** `validate_replacement_receipt` RR4 (workspace gate, higher side)
- **Kind:** isolation
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = RM.validate_replacement_receipt(db, ret=RC, workspace_id=W2.id, data=RRQ((A, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == NOTPART(A.id, RC)`.
3. session clean.

### PORM-RR-23 — a good line before a bad one does not help
- **Rules:** `validate_replacement_receipt` RR3, RR4
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((A, "1"), (MISSING, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == NOTPART(999999999, RC)`.
3. session clean.
4. nothing written.

### PORM-RR-24 — the first failing line in request order decides (too many first)
- **Rules:** `validate_replacement_receipt` RR3
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((A, "5"), (MISSING, "1")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == RTOO("5", 1, "4.00")`.
3. session clean.

### PORM-RR-25 — the first failing line in request order decides (not part first, then a repeat over)
- **Rules:** `validate_replacement_receipt` RR3, RR5 (running total in request order)
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((A, "3"), (MISSING, "1"), (A, "3")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == NOTPART(999999999, RC)`.
3. session clean.

### PORM-RR-26 — an unpriced PO line takes the return line's price as cost
- **Rules:** `validate_replacement_receipt` RR6 (PO line price NULL)
- **Kind:** happy
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1, but `unit_price None`, `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")`.
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00", but `unit_price Decimal("7.50")`.
4. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((A, "2")))`.

**Then**
1. returns: `result == [{"return_item_id": A.id, "po_item_id": L1.id, "item_id": I1.id, "quantity": Decimal("2"), "unit_cost": Decimal("7.50")}]`.

### PORM-RR-27 — a priced PO line's cost wins over the return line's price
- **Rules:** `validate_replacement_receipt` RR6 (original PO line cost)
- **Kind:** boundary
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")`.
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00", but `unit_price Decimal("7.50")`.
4. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((A, "2")))`.

**Then**
1. returns: `result[0]["unit_cost"] == Decimal("10.00")`.

### PORM-RR-28 — a price sent in the request is ignored: there is no price field
- **Rules:** `validate_replacement_receipt` RR6 (never the request's)
- **Kind:** boundary
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00".
4. `db.expire_all()`.

**When**
- `result = RV(RC, PurchaseOrderReturnReplacementCreate(items=[{"return_item_id": A.id, "quantity": Decimal("1"), "unit_price": Decimal("1.00")}]))`.

**Then**
1. returns: `result[0]["unit_cost"] == Decimal("10.00")`.
2. returns: `"unit_price" not in result[0]`.

### PORM-RR-29 — a completed purchase order is accepted
- **Rules:** `validate_replacement_receipt` RR7
- **Kind:** happy
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. STC = `Status(workspace_id=W1.id, name="Complete", comment="stage")`.
2. `O2.current_status_id = STC.id`, then `db.flush()`.
3. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
4. RC = return "001", but `return_type "replace"`, completed.
5. A = rline of RC on L1, "4.00".
6. `db.expire_all()`.

**When**
- `result = RV(RC, RRQ((A, "4")))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["quantity"] == Decimal("4")`.

### PORM-RR-30 — a passing check writes nothing and leaves the return and the lines as they were
- **Rules:** `validate_replacement_receipt` RR8
- **Kind:** side-effect
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (fails before the call: the schema `PurchaseOrderReturnReplacementCreate` or the method `validate_replacement_receipt` doesn't exist yet; ImportError when the request is built)

**Given**
1. L1 = line 1, but `quantity_received Decimal("6.00")`, `quantity_returned Decimal("4.00")` (4 sent back on a replace return, completed).
2. RC = return "001", but `return_type "replace"`, completed.
3. A = rline of RC on L1, "4.00".
4. Statement recorder on. `db.expunge_all()`.
5. RC = `db.get(PurchaseOrderReturn, RC.id)` (loaded again after the expunge).

**When**
- `result = RV(RC, RRQ((A, "2")))`.

**Then**
1. returns: `len(result) == 1`.
2. session clean.
3. statement: `written == []`.
4. nothing written.
5. re-read RC: `status == "completed"`, `return_type == "replace"`, `completed_at == T4`.
6. re-read A: `quantity_returned == Decimal("4.00")`.
7. re-read L1: `quantity_received == Decimal("6.00")`, `quantity_returned == Decimal("4.00")`, `quantity_refunded == Decimal("0.00")`.

### PORM-RR-31 — an empty receipt is refused
- **Rules:** `PurchaseOrderReturnReplacementCreate` (schema) Inputs
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the build raises ImportError: `PurchaseOrderReturnReplacementCreate` does not exist)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `PurchaseOrderReturnReplacementCreate(items=[])` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: loc `== ("items",)`.

### PORM-RR-32 — a zero quantity is refused
- **Rules:** `PurchaseOrderReturnReplacementCreate` (schema) Inputs (> 0)
- **Kind:** boundary
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the build raises ImportError: `PurchaseOrderReturnReplacementCreate` does not exist)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `PurchaseOrderReturnReplacementCreate(items=[{"return_item_id": 1, "quantity": Decimal("0")}])` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: loc `== ("items", 0, "quantity")`.

### PORM-RR-33 — a quantity with 3 decimals is refused
- **Rules:** `PurchaseOrderReturnReplacementCreate` (schema) Inputs (2 decimals, as BUG-2752)
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the build raises ImportError: `PurchaseOrderReturnReplacementCreate` does not exist)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `PurchaseOrderReturnReplacementCreate(items=[{"return_item_id": 1, "quantity": Decimal("0.004")}])` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: loc `== ("items", 0, "quantity")`.

### PORM-RR-34 — a quantity with 14 integer digits is refused
- **Rules:** `PurchaseOrderReturnReplacementCreate` (schema) Inputs (13 integer digits)
- **Kind:** error
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the build raises ImportError: `PurchaseOrderReturnReplacementCreate` does not exist)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `PurchaseOrderReturnReplacementCreate(items=[{"return_item_id": 1, "quantity": Decimal("10000000000000")}])` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: loc `== ("items", 0, "quantity")`.

### PORM-RR-35 — the valid edges pass: 0.01 and 13 integer digits with 2 decimals, notes optional
- **Rules:** `PurchaseOrderReturnReplacementCreate` (schema) Inputs
- **Kind:** boundary
- **Expect:** xfail BUG-2810
- **Fails today on:** Then 1 (the build raises ImportError: `PurchaseOrderReturnReplacementCreate` does not exist)

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = PurchaseOrderReturnReplacementCreate(items=[{"return_item_id": 1, "quantity": Decimal("0.01")}, {"return_item_id": 2, "quantity": Decimal("9999999999999.99")}])` (target `schema`).

**Then**
1. returns: `[i.quantity for i in result.items] == [Decimal("0.01"), Decimal("9999999999999.99")]`.
2. returns: `result.notes is None`.

## Return price range (`validate_and_build_items` R6, R6a) — BUG-2785, owner OQ-45 (2026-11-17)

A price that is sent must be ≥ 0 and ≤ the order line's stored price. Prices inside the range are used as sent. Per line, the checks run in this order: belongs, quantity, price.

### PORM-Q45-01 — a negative price is refused
- **Rules:** `validate_and_build_items` R6 [BUG-2785]; Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-2785
- **Fails today on:** Then 1 (no exception is raised: `-5` is kept as sent)

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("1"), unit_price=Decimal("-5"))))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Return price for line 1 must be between 0 and 10.00"`.
3. session clean.
4. nothing written.

### PORM-Q45-02 — a price of 0 is a price, not "not sent", and is accepted
- **Rules:** `validate_and_build_items` R6 (0 accepted)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("1"), unit_price=Decimal("0"))))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["unit_price"] == Decimal("0")`.
3. returns: `result[0]["unit_price"] is not None`.

### PORM-Q45-03 — a price far above the order line's price is refused
- **Rules:** `validate_and_build_items` R6 [BUG-2785]
- **Kind:** bug
- **Expect:** xfail BUG-2785
- **Fails today on:** Then 1 (no exception is raised)

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("1"), unit_price=Decimal("99999"))))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Return price for line 1 must be between 0 and 10.00"`.
3. session clean.

### PORM-Q45-04 — one hundredth above the order line's price is refused
- **Rules:** `validate_and_build_items` R6 [BUG-2785] (over side of the limit)
- **Kind:** bug
- **Expect:** xfail BUG-2785
- **Fails today on:** Then 1 (no exception is raised)

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("1"), unit_price=Decimal("10.01"))))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Return price for line 1 must be between 0 and 10.00"`.
3. session clean.

### PORM-Q45-05 — a price inside the range is used instead of the line's
- **Rules:** `validate_and_build_items` R6 (inside the range: used as sent), R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("2"), unit_price=Decimal("7.50"), notes="restocking fee")))`.

**Then**
1. returns: `result == [{"po_item_id": L1.id, "item_id": I1.id, "quantity_returned": Decimal("2"), "unit_price": Decimal("7.50"), "notes": "restocking fee"}]`.

### PORM-Q45-06 — exactly the order line's price is accepted
- **Rules:** `validate_and_build_items` R6 (equal side of the limit)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("1"), unit_price=Decimal("10.00"))))`.

**Then**
1. returns: `result[0]["unit_price"] == Decimal("10.00")`.

### PORM-Q45-07 — on an unpriced line a negative price is refused with its own text
- **Rules:** `validate_and_build_items` R6 [BUG-2785] (unpriced line); Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-2785
- **Fails today on:** Then 1 (no exception is raised)

**Given**
1. L1 = line 1, but `unit_price None`.
2. `db.expire_all()`.

**When**
- `result = V(REQ(PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("2"), unit_price=Decimal("-1"))))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Return price for line 1 cannot be negative"`.
3. session clean.

### PORM-Q45-08 — on an unpriced line any price ≥ 0 is accepted (no upper bound)
- **Rules:** `validate_and_build_items` R6 (unpriced line)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. L1 = line 1, but `unit_price None`.
2. `db.expire_all()`.

**When**
- `result = V(REQ(PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("2"), unit_price=Decimal("99999"))))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["unit_price"] == Decimal("99999")`.

### PORM-Q45-09 — on one line, too many beats a bad price
- **Rules:** `validate_and_build_items` R6a (quantity before price), R3
- **Kind:** error
- **Expect:** pass

**Given**
1. L1 = line 1.
2. `db.expire_all()`.

**When**
- `result = V(REQ(PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("11"), unit_price=Decimal("99999"))))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == TOO("11", 1, "10.00")`.
3. session clean.

### PORM-Q45-10 — a bad price on the first line beats too many on the second
- **Rules:** `validate_and_build_items` R1, R6a, R6 [BUG-2785]
- **Kind:** bug
- **Expect:** xfail BUG-2785
- **Fails today on:** Then 2 (detail today is TOO("11", 2, "10.00"): the price is not checked)

**Given**
1. L1 = line 1.
2. L2 = line 2.
3. `db.expire_all()`.

**When**
- `result = V(REQ(PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("1"), unit_price=Decimal("99999")), LN(L2, "11")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Return price for line 1 must be between 0 and 10.00"`.
3. session clean.

### PORM-Q45-11 — too many on the first line beats a bad price on the second
- **Rules:** `validate_and_build_items` R1, R6a
- **Kind:** error
- **Expect:** pass

**Given**
1. L1 = line 1.
2. L2 = line 2.
3. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "11"), PurchaseOrderReturnItemCreate(po_item_id=L2.id, quantity_returned=Decimal("1"), unit_price=Decimal("99999"))))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == TOO("11", 1, "10.00")`.
3. session clean.

### PORM-Q45-12 — the price message names the line's own number and its stored price
- **Rules:** `validate_and_build_items` R6 [BUG-2785]; Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-2785
- **Fails today on:** Then 1 (no exception is raised)

**Given**
1. L1 = line 1.
2. L3 = line 3, but `unit_price Decimal("4.50")`.
3. `db.expire_all()`.

**When**
- `result = V(REQ(PurchaseOrderReturnItemCreate(po_item_id=L3.id, quantity_returned=Decimal("1"), unit_price=Decimal("4.51"))))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Return price for line 3 must be between 0 and 4.50"`.
3. session clean.

## Missing return price on an unpriced line (`validate_and_build_items` R7a, R6a) — BUG-2787, owner OQ-46 (2026-11-17)

When neither the request nor the order line has a price, the line is refused. This is the last check on a line.

### PORM-Q46-01 — an unpriced order line with no price sent is refused
- **Rules:** `validate_and_build_items` R7a [BUG-2787]; Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-2787
- **Fails today on:** Then 1 (no exception is raised: `unit_price None` is returned)

**Given**
1. L1 = line 1, but `unit_price None`.
2. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "2")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Enter a return price for line 1 — the order line has no price"`.
3. session clean.
4. nothing written.

### PORM-Q46-02 — an unpriced order line with a price sent takes the sent price
- **Rules:** `validate_and_build_items` R6, R7a (price sent)
- **Kind:** happy
- **Expect:** pass

**Given**
1. L1 = line 1, but `unit_price None`.
2. `db.expire_all()`.

**When**
- `result = V(REQ(PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("2"), unit_price=Decimal("4.00"))))`.

**Then**
1. returns: `result[0]["unit_price"] == Decimal("4.00")`.

### PORM-Q46-03 — on an unpriced line, too many beats the missing price
- **Rules:** `validate_and_build_items` R6a (quantity before missing price), R3
- **Kind:** error
- **Expect:** pass

**Given**
1. L1 = line 1, but `unit_price None`.
2. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "11")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == TOO("11", 1, "10.00")`.
3. session clean.

### PORM-Q46-04 — on an unpriced line a sent price of 0 is a price
- **Rules:** `validate_and_build_items` R6, R7a (0 is a price)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. L1 = line 1, but `unit_price None`.
2. `db.expire_all()`.

**When**
- `result = V(REQ(PurchaseOrderReturnItemCreate(po_item_id=L1.id, quantity_returned=Decimal("2"), unit_price=Decimal("0"))))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["unit_price"] == Decimal("0")`.

### PORM-Q46-05 — a missing price on the first line beats too many on the second
- **Rules:** `validate_and_build_items` R1, R6a, R7a [BUG-2787]
- **Kind:** bug
- **Expect:** xfail BUG-2787
- **Fails today on:** Then 2 (detail today is TOO("11", 2, "10.00"))

**Given**
1. L1 = line 1, but `unit_price None`.
2. L2 = line 2.
3. `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "2"), LN(L2, "11")))`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Enter a return price for line 1 — the order line has no price"`.
3. session clean.

## Credit-note void and the return (`sync_return_paid` R6) — BUG-2788, owner OQ-47 (2026-11-17)

The owner's freeze rule: a credit note is never editable, but it can be voided. Voiding a pending return's credit note frees the return; voiding a completed return's credit note is refused. The check lives in `AccountInvoiceManager.void_invoice` R3c, so these cards void through it and then read the return with this manager. Payment, event and freeze details are covered by that manager's cards. `sync_return_paid` itself still writes only `paid` (Q47-01, Q47-02).

### PORM-Q47-01 — `sync_return_paid` on a pending return with a voided credit note writes only `paid`
- **Rules:** `sync_return_paid` R5, R6 (this method writes only `paid`)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CN = voided credit note.
2. R = return "001", but `invoice_id CN.id`, `paid True`, `updated_at T1`.

**When**
- `result = RM.sync_return_paid(db, ret=R, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. re-read R: `paid is False`.
3. re-read R: `status == "pending"`, `completed_at is None`, `completed_by is None`.

### PORM-Q47-02 — `sync_return_paid` on a completed return with a voided credit note writes only `paid`
- **Rules:** `sync_return_paid` R5, R6 (this method writes only `paid`)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CN = voided credit note.
2. R = return "001", but completed, `invoice_id CN.id`, `paid True`, `updated_at T1`.

**When**
- `result = RM.sync_return_paid(db, ret=R, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. re-read R: `status == "completed"`, `completed_at == T4`.

### PORM-Q47-03 — after its credit note is voided, the pending return no longer keeps the order open
- **Rules:** `sync_return_paid` R6 [BUG-2788]; `has_open_return` R1
- **Kind:** bug
- **Expect:** xfail BUG-2788
- **Fails today on:** Then 1 (today the return stays pending, so the order is still open)

**Given**
1. CN = confirmed credit note.
2. R = return "001", but `invoice_id CN.id`.
3. void step: `AIM.void_invoice(db, invoice_id=CN.id, workspace_id=W1.id, user_id=U2.id, void_note="Typo")`, then `db.expire_all()`.

**When**
- `result = RM.has_open_return(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PORM-Q47-04 — after its credit note is voided, the pending return no longer reserves its quantity
- **Rules:** `sync_return_paid` R6 [BUG-2788]; `validate_and_build_items` R4
- **Kind:** bug
- **Expect:** xfail BUG-2788
- **Fails today on:** Then 1 (the call raises HTTPException: today the return still reserves 4)

**Given**
1. L1 = line 1.
2. CN = confirmed credit note.
3. R = return "001", but `invoice_id CN.id`.
4. rline of R on L1, "4.00".
5. void step: `AIM.void_invoice(db, invoice_id=CN.id, workspace_id=W1.id, user_id=U2.id, void_note="Typo")`, then `db.expire_all()`.

**When**
- `result = V(REQ(LN(L1, "10")))`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["quantity_returned"] == Decimal("10")`.

### PORM-Q47-05 — after its credit note is voided, the return is served as voided (no longer completable)
- **Rules:** `sync_return_paid` R6 [BUG-2788]; `get_return` R1
- **Kind:** bug
- **Expect:** xfail BUG-2788
- **Fails today on:** Then 2 (status is still "pending")

**Given**
1. CN = confirmed credit note.
2. R = return "001", but `invoice_id CN.id`.
3. void step: `AIM.void_invoice(db, invoice_id=CN.id, workspace_id=W1.id, user_id=U2.id, void_note="Typo")`, then `db.expire_all()`.

**When**
- `result = RM.get_return(db, return_id=R.id, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == R.id`.
2. returns: `result.status == "voided"`.
3. returns: `result.paid is False`.

### PORM-Q47-06 — voiding a pending return's credit note marks the return voided, unpaid
- **Rules:** `sync_return_paid` R6 [BUG-2788] (via `void_invoice` R3c)
- **Kind:** bug
- **Expect:** xfail BUG-2788
- **Fails today on:** Then 2 (status is still "pending")

**Given**
1. CN = confirmed credit note, but `payment_status "paid"`.
2. R = return "001", but `invoice_id CN.id`, `paid True`, `updated_at T1`.

**When**
- `result = AIM.void_invoice(db, invoice_id=CN.id, workspace_id=W1.id, user_id=U2.id, void_note="Typo")`.

**Then**
1. returns: `result.id == CN.id`.
2. re-read R: `status == "voided"`.
3. re-read R: `paid is False`, `completed_at is None`, `completed_by is None`.

### PORM-Q47-07 — voiding a completed return's credit note is refused, nothing changes
- **Rules:** `sync_return_paid` R6 [BUG-2788] (via `void_invoice` R3c)
- **Kind:** bug
- **Expect:** xfail BUG-2788
- **Fails today on:** Then 1 (no exception is raised: today the credit note is voided)

**Given**
1. CN = confirmed credit note.
2. R = return "001", but completed, `invoice_id CN.id`, `updated_at T1`.

**When**
- `result = AIM.void_invoice(db, invoice_id=CN.id, workspace_id=W1.id, user_id=U2.id, void_note="Typo")`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "This return is completed — its goods have already moved. Start a new return or issue a separate credit note."`.
3. session clean.
4. re-read CN: `invoice_status == "confirmed"`.
5. re-read R: `status == "completed"`, `completed_at == T4`, `updated_at == T1`.

### PORM-Q47-08 — voiding the credit note of an already voided return leaves the return as it is
- **Rules:** `sync_return_paid` R6 (void_invoice R3c: already voided → return unchanged)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CN = confirmed credit note.
2. R = return "001", but voided, `invoice_id CN.id`.

**When**
- `result = AIM.void_invoice(db, invoice_id=CN.id, workspace_id=W1.id, user_id=U2.id, void_note="Typo")`.

**Then**
1. returns: `result.id == CN.id`.
2. re-read CN: `invoice_status == "voided"`.
3. re-read R: `status == "voided"`, `paid is False`, `updated_at == T4`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `validate_and_build_items` R9 [BUG-2753] race outcome | integration tests | two sessions start a return on one line at once; the second waits and gets the "only N available" 400; together they never reserve more than received |
| `get_return` R4 [BUG-2754] race outcome | integration tests (and `PurchaseOrderService` FU-1 (d)) | `complete_return` / `void_return` pass `for_update=True`; of two concurrent completes / a complete and a void, the loser gets "Only a pending return can be …" |
| FU-1 (a) | `PurchaseOrderService.start_return` | refuses a voided order and an order with nothing received; a completed order is allowed (owner freeze); BUG-801 fractional quantity on a storage / machine PO refused at start |
| FU-1 (b) | `PurchaseOrderService._attach_return_invoice_for_po` | credit-note line subtotal = unit_price × quantity rounded half up (HR-15); `unit_price or 0` |
| FU-1 (c) | `PurchaseOrderService.void_return` | sets no `updated_by` |
| Owner freeze: a return credit note is never editable, only voidable | `AccountInvoiceManager` (freeze F6; cards RV-37..RV-42, VD-26..VD-28 there) | revert / edit of a credit note refused; void allowed |
| `sync_return_paid` R6 [BUG-2788] details | `AccountInvoiceManager.void_invoice` R3c | the row lock on the return, payments auto-voided, the event, return rows of W0 / W2 pointing at the invoice |
| OQ-47 / FU-3 | `AccountInvoiceService.void_invoice` / `/void` endpoint | the endpoint reaches `void_invoice` R3c (BUG-2788) |
| OQ-48 / FU-2 [BUG-2789, BUG-2810] | `PurchaseOrderService.receive_replacements` (FU-2), `PurchaseOrderManager.reopen_for_return` | a return never reopens a completed order; replacements are received through the return: the return is read `get_return(..., for_update=True)`, then RR1–RR8; per line `quantity_replaced += q` and PO line `quantity_received += q` (`quantity_returned` untouched); stock in at the PO destination with one ledger row per return line (`source_type 'purchase_return_replacement'`, `source_id` = return line id, `unit_cost` per RR6, `total_cost` = cost × q rounded half up, HR-15, notes `Replacement for return {return_number} — PO {po_number} line {line_number}`); one PO event `return_replacement_received`; PO stage, invoice and return status unchanged |
| `validate_replacement_receipt` schema 422 at the API; race between two receipts | `POST /purchase-orders/{po_id}/returns/{return_id}/receive-replacements/`; integration tests | a `ValidationError` answers 422; two concurrent receipts never exceed what was returned (service lock) |
| `validate_and_build_items` Errors row 3 (422 at the API) | `POST /purchase-orders/{id}/returns/` | a `ValidationError` from the schema answers 422 |

## Spec gaps
Gaps 1–4 are closed by the spec's Gap log G1–G4 (2026-11-17).

| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 5 | `validate_replacement_receipt` Inputs | The module of the new schema `PurchaseOrderReturnReplacementCreate` and the name of its line class are not given. | The cards import it from `app.schemas.purchase_order_return` and build lines as dicts. |
| 6 | `validate_replacement_receipt` RR4 | Whether a line of this return whose **return** is of this workspace but whose PO line is of another order counts. No such shape can come from a real return. | No card. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `has_open_return` | R1 | PORM-HO-01, HO-02, HO-03, HO-04, HO-05, HO-09; after a credit-note void Q47-03 |
| `has_open_return` | R2 | PORM-HO-06, HO-07, HO-10 |
| `has_open_return` | R3 | PORM-HO-08 |
| `validate_and_build_items` | R1 | PORM-V-01, V-02, V-22, V-28, V-29, V-30, V-54, V-55, Q45-10, Q45-11, Q46-05 |
| `validate_and_build_items` | R2; Errors 1 | PORM-V-28, V-30, V-31, V-32, V-33, V-34, V-35, V-36, V-37 |
| `validate_and_build_items` | R3; Errors 2 | PORM-V-03, V-04, V-05, V-06, V-08, V-11, V-16, V-19, V-38, V-39, V-40, V-41, V-42, V-54, Q45-09, Q45-11, Q46-03 |
| `validate_and_build_items` | R4 (today = intended: pending, voided, per line) | PORM-V-07, V-08, V-09, V-10, V-11, V-12, V-13, V-16, V-19, V-25, V-41, V-42, Q47-04 |
| `validate_and_build_items` | R4 [BUG-2750] (owner-confirmed) | PORM-V-14, V-15, V-17, V-18, V-20 |
| `validate_and_build_items` | R4a [BUG-2792] | PORM-V-51, V-52, V-53 |
| `validate_and_build_items` | R5 [BUG-2751] (incl. running total) | PORM-V-21, V-23, V-24, V-26, V-27, V-55, V-56 |
| `validate_and_build_items` | R5 (fits) | PORM-V-22, V-25 |
| `validate_and_build_items` | R6 [BUG-2785]; Errors row 3 | PORM-Q45-01, Q45-03, Q45-04, Q45-10, Q45-12, Q45-07 |
| `validate_and_build_items` | R6 (inside the range, holds today) | PORM-Q45-02, Q45-05, Q45-06, Q45-08, Q46-02, Q46-04 |
| `validate_and_build_items` | R6a (check order) | PORM-Q45-09, Q45-10, Q45-11, Q46-03, Q46-05 |
| `validate_and_build_items` | R7 (priced line) | PORM-V-01, V-02, V-22 |
| `validate_and_build_items` | R7a [BUG-2787]; Errors row 4 | PORM-Q46-01, Q46-05 |
| `validate_and_build_items` | R8 | PORM-V-01, V-02, V-22, V-38, Q45-05 |
| `validate_and_build_items` | R9 [BUG-2753] | PORM-V-44; race → Deferred |
| `validate_and_build_items` | R10 [BUG-2752] | PORM-SCH-08, SCH-09, SCH-10, SCH-11, SCH-12 |
| `validate_and_build_items` | R10 (valid side) | PORM-SCH-04, SCH-13, SCH-14 |
| `validate_and_build_items` | R11 | PORM-V-43 (and session clean on every refusal) |
| `validate_and_build_items` | Inputs / Errors (schema; G2 required fields) | PORM-SCH-01, SCH-02, SCH-03, SCH-04, SCH-05, SCH-06, SCH-07, SCH-15, SCH-16, SCH-17, SCH-18 |
| `get_return` | R1 | PORM-G-01, G-02, G-15, Q47-05 |
| `get_return` | R2; Errors 1 | PORM-G-03, G-04, G-05, G-06, G-07, G-08, G-16, G-11 |
| `get_return` | R3 | PORM-G-09 |
| `get_return` | R4 [BUG-2754] | PORM-G-10, G-11, G-12; default unlocked G-09; race → Deferred |
| `get_return` | R5 [BUG-2755] | PORM-G-13, G-14; today's part G-17 |
| `list_returns` | R1 | PORM-L-01, L-02, L-03, L-04, L-05, L-06, L-10, L-11 |
| `list_returns` | R1 tie (BUG-2429) | PORM-L-07 |
| `list_returns` | R2 [BUG-2755] | PORM-L-08, L-09; today's part L-12 |
| `sync_return_paid` | R1 | PORM-S-01, S-09, S-10, S-12 |
| `sync_return_paid` | R2 | PORM-S-02, S-03, S-04, S-11 |
| `sync_return_paid` | R3 | PORM-S-07, S-08, S-09, S-10 |
| `sync_return_paid` | R4 | PORM-S-05, S-06, S-08, S-09 |
| `sync_return_paid` | R5 | PORM-S-01, S-02, S-07, S-12, S-13, S-14 |
| `sync_return_paid` | R6 [BUG-2788] | PORM-Q47-03, Q47-04, Q47-05, Q47-06, Q47-07 |
| `sync_return_paid` | R6 (this method writes only `paid`; already voided return) | PORM-Q47-01, Q47-02, Q47-08 |
| `validate_replacement_receipt` | RR1; Errors 1 | PORM-RR-11, RR-14 |
| `validate_replacement_receipt` | RR2; Errors 2 | PORM-RR-12, RR-13, RR-15 |
| `validate_replacement_receipt` | RR3 | PORM-RR-02, RR-10, RR-23, RR-24, RR-25 |
| `validate_replacement_receipt` | RR4; Errors 3 | PORM-RR-16, RR-17, RR-18, RR-19, RR-20, RR-21, RR-22, RR-23, RR-25 |
| `validate_replacement_receipt` | RR5; Errors 4 | PORM-RR-01, RR-03, RR-04, RR-05, RR-06, RR-07, RR-08, RR-09, RR-10, RR-24 |
| `validate_replacement_receipt` | RR6 | PORM-RR-01, RR-02, RR-26, RR-27, RR-28 |
| `validate_replacement_receipt` | RR7 | PORM-RR-29 |
| `validate_replacement_receipt` | RR8 | PORM-RR-30 |
| `validate_replacement_receipt` | Inputs / Errors 5 (schema) | PORM-RR-31, RR-32, RR-33, RR-34, RR-35 |
