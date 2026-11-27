# Test cases — `app/managers/product_manager.py`

> **Spec:** `tests/unit/managers/product_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 3 (2026-11-19) — spec 2026-11-19 notes and `product_manager.verify.md` (NEEDS WORK, findings 1–6 and the minor Expect note). BUG-2811 (`apply_production_output` R8a): PO-20 is now a strict xfail on Then 4, unchanged; new PO-26 (pass) keeps its other Thens; new PO-27 (xfail BUG-1336): a restored row is not new. PO-21 … PO-23 start from an existing row, so they are unchanged. Gap 7 → G7 (R10a): new U-54 (xfail BUG-2793). The BUG-2770 fix note (`with_for_update(of=Product)`) needs no card change: the lock cards look for `FOR UPDATE` in any form. Verifier findings: 1 → SD-23; 2 → SR-31; 3 → PO-28; 4 → PO-29 (1.333… → 1.33); 5 → SD-24, SR-32, U-55 (totals in cents); 6 → PO-28, PO-29 check the in-session `avg_cost`. The U-27 and SR-29 Expect lines now name both bugs. Gap 7 closed. No ID retired.
> **Revision:** 2 (2026-11-17) — owner answers OQ-50/51/52 and spec Gap log G1–G6 applied. OQ-50: PO-17 … PO-24 stay pass, now intended (revisit after launch); new PO-25 (old average 0.00 weighted, G1). OQ-51 → BUG-2793: U-40, U-41, U-42 now strict xfails (flip of a row holding stock refused); U-43, U-44 re-set on a row at `qty 0` (still pass); new U-47 … U-51; new callable `make_sellable` MS-01 … MS-30. OQ-52 → BUG-2794: SR-16 … SR-19 pass as intended; new SR-20 … SR-29 (sale-cost fallback). G2: U-27 gains the notes line, new U-52, U-53. G3: PO-14, SR-13 assert every restore column. G4: new C-34 … C-38 (check order). G5: no change. G6: new SR-30. The pending-owner sections and `Owner question:` lines are gone. No ID retired.
> **Revision:** 1 (2026-11-14) — first design.
> **Counts:** 245 cases · 143 expected-to-pass · 102 expected-to-fail (bugs) · 10 deferred

## Reviewer summary
- **Per callable:** `_quantity_to_int` 8 (0 bug) · `create_product` 38 (20 bug) · `update_product` 55 (28 bug) · `get_product` 11 (5 bug) · `list_products` 7 (0 bug) · `delete_product` 11 (2 bug) · `apply_production_output` 29 (5 bug) · `apply_sale_deduction` 24 (3 bug) · `apply_sale_return` 32 (9 bug) · `make_sellable` 30 (30 bug, new method). All xfail cards are strict.
- **Depth:** full (step 1a): this module writes finished-goods stock, cost and ledger rows.
- **Notable design choices:**
  - **Owner answers (2026-11-17)** are applied in place: see the Revision 2 line below. Production cards outside the costed section still use `unit_cost=None`, as both callers do (R7).
  - **Locks (BUG-2770)** are strict-xfail statement-recorder cards, one per method (update, production, deduction, return): a `SELECT` from `products` carries `FOR UPDATE`, with no `SKIP LOCKED` / `NOWAIT`. Readers and the plain soft delete get pass "no lock" cards. The two-transaction outcomes are Deferred.
  - **Today-independent halves pass.** Where a bug changes one part of a result (message text BUG-2782, ledger labels BUG-2783, `total_cost` at cost 0 BUG-2779, `updated_by` on a no-op BUG-2771), a pass card checks the parts that hold today and after the fix; the xfail card holds only the changed part. The BUG-2782 pass cards check that the detail ends with `: requested 3, available N`, which both texts share.
  - **Isolation with W0 and W2:** rows with the same factory and item ids in W0 and in W2 (invalid data, built only to prove they are ignored) sit next to the W1 key on every bucket lookup; by-id refusals use one row of W0 (lower id) and one of W2 (higher id).
  - **Refusals** run with plain `pytest.raises` (no savepoint), check the session first, then nothing written. Today's 23505 paths (BUG-1336, BUG-2781, BUG-1011 unknown item) stay plain too: the strict xfail fails at the raise.
  - Schema rules (BUG-2775, BUG-2776, BUG-2777 nulls for `qty` / `is_available_for_sale`) are target `schema` cards; the 0 boundary and the 13-digit / 2-decimal edge are pass cards.
- **Revision 2 (owner answers, 2026-11-17):** the three owner-question sections are folded back into their callables, with no `Owner question:` lines. OQ-50: costed production (R5–R7) is intended for now and tagged "revisit after launch"; those cards stay pass, and BUG-1040 stays a strict xfail. OQ-51 / BUG-2793: flipping a row that holds stock is refused (strict xfails U-40, U-41, U-42, U-50, U-51); a row at `qty 0` still flips (pass U-43, U-44, U-47, U-48, U-49). The new `make_sellable` has 30 strict-xfail cards: two linked ledger rows with exact Decimal values, half-up weighting, the target created or restored, refusals in check order, W0 / W2 isolation, a lock card and a commit spy. OQ-52 / BUG-2794: a bucket's own average (0.00 included) is kept (pass). The latest sale's cost is used only when the bucket has none (strict xfails), with `performed_at` and id tie cards, a skipped uncosted sale, and W0 / W2 and other-key sale rows that must not count (pass).
- **Needs a decision:** None. Gaps 1–7 are closed by the spec's Gap log (G7 on 2026-11-19).

## Conventions for this module

**IDs.** `PRDM` = `app/managers/product_manager.py`. `QI` _quantity_to_int · `C` create_product · `U` update_product · `G` get_product · `L` list_products · `D` delete_product · `PO` apply_production_output · `SD` apply_sale_deduction · `SR` apply_sale_return · `MS` make_sellable (new method, BUG-2793).

**Actors and fixed values.**
- `M` = the singleton `product_manager`; `_quantity_to_int` = the module function (`from app.managers.product_manager import product_manager, _quantity_to_int`). `db` = the test's real session, always the first argument; every other argument by keyword. `result` = what the When call returns. The session does not autoflush.
- Classes: `Product` (`app.models.product`), `ProductLedger` (`app.models.product_ledger`), `Factory` (`app.models.factory`), `Item` (`app.models.item`), `Account` (`app.models.account`). `ProductCreate`, `ProductUpdate` (`app.schemas.product`). `product_dao` (`app.dao.product`). `HTTPException` (`fastapi`). `AppValidationError` = `app.core.exceptions.ValidationError`; `PydanticValidationError` = `pydantic.ValidationError`. `IntegrityError` (`sqlalchemy.exc`). `Decimal`, `datetime`, `patch` the usual ones.
- MISSING = `999999999`. T0 = `datetime(2026, 1, 15, 9, 0, 0)`, a past stamp.
- Money compares by value as `Decimal` (`Decimal("12.50")`); `qty`, `quantity`, `qty_before`, `qty_after` compare as `int`. `None` in a Then means `is None`.

**Externals.** None is mocked. `performed_at`, `created_at`, `updated_at`, `deleted_at` are checked only as set / not set.

**Standing rows** (every test, this order, each flushed, no Given line):
1. W0, W1, W2 = `make_workspace(db)` three times (`W0.id < W1.id < W2.id`). U1, U2 = `make_profile(db)` twice. U2 is the acting user of every call.
2. Factories (`Factory(workspace_id=…, name=…, abbreviation=…)`): F0 `"Zero Plant"`/`"Z0"` of W0; F1 `"Factory One"`/`"F1"`, F2 `"Factory Two"`/`"F2"` of W1; FD `"Old Plant"`/`"OP"` of W1, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id` (soft-deleted; `is_active` stays True); FI `"Idle Plant"`/`"IP"` of W1, `is_active False` (inactive but live); F9 `"Far Plant"`/`"F9"` of W2.
3. Items (`Item(workspace_id=…, name=…, name_normalized=<name lower case>, unit="pcs")`): I0 `"Zero Nut"` of W0; I1 `"Bolt"`, I2 `"Cam"` of W1; IX `"Old Gasket"` of W1, `is_active False` (removed); I9 `"Far Crate"` of W2.
4. AC1 = `Account(workspace_id=W1.id, name="Acme")`.

**Given rows.** Built directly (never through `M`), flushed one at a time in the order written, so ids rise in that order. After "but" a line lists every column that differs. A line written as code is a step to run exactly, at that place. No Given holds two rows of one key (workspace, factory, item, for-sale flag), deleted or not. No `products` or `product_ledger` row exists unless the Given builds it.
- **stock** = `Product(workspace_id=W1.id, item_id=I1.id, factory_id=F1.id, qty=5, created_by=U1.id)`; `is_available_for_sale` (False), `is_active`, `is_deleted`, `avg_cost`, `selling_price`, `min_order_qty`, `note`, `updated_by` left to their defaults (`updated_by` NULL).
- **for sale** = `is_available_for_sale True`.
- **deleted** (on a row) = `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`: everything a real soft delete writes.
- **sale entry** = `ProductLedger(workspace_id=W1.id, factory_id=F1.id, item_id=I1.id, transaction_type="sale", quantity=1, qty_before=1, qty_after=0, source_type="sales_delivery", source_id=501, performed_by=U1.id, performed_at=…)`; the card gives `performed_at` (T1, T2 = `datetime(2026, 2, 1, 9, 0, 0)`, `datetime(2026, 2, 2, 9, 0, 0)`, both past) and `unit_cost` (which also goes into `avg_cost_before` and `avg_cost_after`), and every column that differs.
- **of W0** / **of W2** on a stock row = only `workspace_id` changes (factory and item ids stay F1, I1 unless the line says otherwise): invalid cross-workspace data, built only to prove the W1 call ignores it.
- Every Given ends with `db.expire_all()` so stored values are read back as the database holds them.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id; values are database values. "the returned row" = by `result.id`.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot after the last Given line).
- **ledger_of(F, I)** = a fresh SELECT of `product_ledger` with `workspace_id W1.id`, that `factory_id` and `item_id`, ordered by `id`, as a list. "E" = its only row when the card has counted exactly 1. "N" = `ledger_of(F1, I1)[-1]`, the row the call wrote, in cards whose Given already holds sale entries.
- **out** / **in** (make_sellable) = the one new `product_ledger` row with `transfer_destination_type == "product"` / with `transfer_source_type == "product"`.
- **nothing written** = the numbers of `products` and `product_ledger` rows (all workspaces) equal their values before the call.
- **session clean** = three asserts on `db` right after the raise, before any re-read: `not db.new`; `not db.dirty`; `not db.deleted`.
- `count:` lines count rows in all workspaces, with the filter stated.

**Errors.**
- `raises: HTTPException`, `raises: ValueError`, `raises: AppValidationError`: plain `with pytest.raises(<Type>) as exc:` around the call, no savepoint (a savepoint's rollback would hide a write). Later `raises:` lines assert on `exc.value`, one per line (`status_code`, `detail`, `errors`, or `str(exc.value)` for `ValueError`).
- `raises: PydanticValidationError` = around the schema's construction (target `schema`); the manager is not called.

**Rolled back.** `sp = db.begin_nested()` directly before the call and a spy wrapping `db.commit` (`patch.object(db, "commit", wraps=db.commit)`); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks. One per writer.

**Statement recorder.** A `before_cursor_execute` listener on `db.connection()`, started at the end of the Given, removed after the When. `selects` = every recorded `SELECT`; `psel` = the recorded `SELECT`s whose text contains `FROM products`; `written` = every recorded `INSERT`, `UPDATE`, `DELETE`.
- **Lock check** = three lines: `any("FOR UPDATE" in s for s in psel)`; `not any("SKIP LOCKED" in s for s in psel)`; `not any("NOWAIT" in s for s in psel)`.
- **No-lock check** = `all("FOR UPDATE" not in s for s in selects)`.

**xfail cards.** Write the call and the checks exactly as shown, also when a parameter does not exist yet. `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`.

**make_sellable cards.** The method does not exist yet (BUG-2793), so every MS card is a strict xfail that fails today at the call (AttributeError). The call is `M.make_sellable(db, prod_id=…, quantity=…, workspace_id=W1.id, user_id=U2.id)`.

**Race simulations.** None.

## `_quantity_to_int`

### PRDM-QI-01 — a whole Decimal with two places becomes an int
- **Rules:** `_quantity_to_int` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = _quantity_to_int(Decimal("5.00"), label="Delivery line")`.

**Then**
1. returns: `result == 5`.
2. returns: `type(result) is int`.

### PRDM-QI-02 — a plain int is returned as is
- **Rules:** `_quantity_to_int` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = _quantity_to_int(7, label="Delivery line")`.

**Then**
1. returns: `result == 7`.
2. returns: `type(result) is int`.

### PRDM-QI-03 — zero is returned as 0
- **Rules:** `_quantity_to_int` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = _quantity_to_int(Decimal("0"), label="Return line")`.

**Then**
1. returns: `result == 0`.
2. returns: `type(result) is int`.

### PRDM-QI-04 — a negative whole value keeps its sign
- **Rules:** `_quantity_to_int` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = _quantity_to_int(Decimal("-3"), label="Return line")`.

**Then**
1. returns: `result == -3`.

### PRDM-QI-05 — one whole unit is 1
- **Rules:** `_quantity_to_int` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = _quantity_to_int(Decimal("1.00"), label="Delivery line")`.

**Then**
1. returns: `result == 1`.

### PRDM-QI-06 — a half unit is refused with the label in the message
- **Rules:** `_quantity_to_int` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `_quantity_to_int(Decimal("2.5"), label="Delivery line")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Delivery line has a fractional quantity; stock requires whole units"`.

### PRDM-QI-07 — one hundredth is refused, with another label
- **Rules:** `_quantity_to_int` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `_quantity_to_int(Decimal("0.01"), label="Return line")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Return line has a fractional quantity; stock requires whole units"`.

### PRDM-QI-08 — just under a whole number is refused
- **Rules:** `_quantity_to_int` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `_quantity_to_int(Decimal("4.99"), label="Delivery line")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Delivery line has a fractional quantity; stock requires whole units"`.

## `ProductManager.create_product`

### PRDM-C-01 — a create stores every field and one opening ledger row
- **Rules:** `create_product` R6, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.create_product(db, data=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=4, avg_cost=Decimal("12.50"), selling_price=Decimal("20.00"), min_order_qty=2, is_available_for_sale=True, note="First lot"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, Product)` and `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `item_id == I1.id`, `factory_id == F1.id`, `qty == 4`.
3. re-read the returned row: `avg_cost == Decimal("12.50")`, `selling_price == Decimal("20.00")`, `min_order_qty == 2`, `is_available_for_sale is True`, `note == "First lot"`.
4. re-read the returned row: `created_by == U2.id`, `updated_by is None`, `is_active is True`, `is_deleted is False`.
5. count: `ledger_of(F1, I1)` has exactly 1 row.
6. re-read E: `transaction_type == "manual_add"`, `quantity == 4`, `qty_before == 0`, `qty_after == 4`.
7. re-read E: `unit_cost == Decimal("12.50")`, `total_cost == Decimal("50.00")`, `avg_cost_before is None`, `avg_cost_after == Decimal("12.50")`.
8. re-read E: `source_type == "manual"`, `source_id is None`, `transfer_source_type is None`, `transfer_source_id is None`, `transfer_destination_type is None`, `transfer_destination_id is None`.
9. re-read E: `notes == "Initial product record created"`, `performed_by == U2.id`, `workspace_id == W1.id`, `performed_at is not None`.

### PRDM-C-02 — a create with only item and factory takes the defaults and writes no ledger row
- **Rules:** `create_product` R6, R7a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.create_product(db, data=ProductCreate(item_id=I1.id, factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `qty == 0`, `avg_cost is None`, `selling_price is None`, `min_order_qty is None`, `is_available_for_sale is False`, `note is None`.
3. re-read the returned row: `created_by == U2.id`, `is_active is True`, `is_deleted is False`.
4. count: `product_ledger` has exactly 0 rows.

### PRDM-C-03 — one unit opens with a ledger row of 1
- **Rules:** `create_product` R7 (other side of `qty > 0`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.create_product(db, data=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=1, avg_cost=Decimal("3.25")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `quantity == 1`, `qty_before == 0`, `qty_after == 1`, `unit_cost == Decimal("3.25")`, `total_cost == Decimal("3.25")`.

### PRDM-C-04 — no cost gives a ledger row with empty cost fields
- **Rules:** `create_product` R7 (`avg_cost` None → `total_cost` NULL)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.create_product(db, data=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=6), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `quantity == 6`, `qty_after == 6`, `unit_cost is None`, `total_cost is None`, `avg_cost_before is None`, `avg_cost_after is None`.

### PRDM-C-05 — a zero cost: the opening row carries the zero cost
- **Rules:** `create_product` R7 (parts that hold today; BUG-2779 is C-06)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.create_product(db, data=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=5, avg_cost=Decimal("0.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `avg_cost == Decimal("0.00")`, `qty == 5`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `quantity == 5`, `unit_cost == Decimal("0.00")`, `avg_cost_after == Decimal("0.00")`.

### PRDM-C-06 — a zero cost gives a ledger total of 0.00
- **Rules:** `create_product` R7 [BUG-2779]
- **Kind:** bug
- **Expect:** xfail BUG-2779
- **Fails today on:** Then 3 (`total_cost` is NULL)

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.create_product(db, data=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=5, avg_cost=Decimal("0.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `total_cost == Decimal("0.00")`.

### PRDM-C-07 — quantity 0 with a cost: the row keeps the cost
- **Rules:** `create_product` R6 (part that holds today; BUG-2778 is C-08)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.create_product(db, data=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=0, avg_cost=Decimal("7.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `qty == 0`, `avg_cost == Decimal("7.00")`.

### PRDM-C-08 — quantity 0 with a cost writes a zero-quantity manual_add row
- **Rules:** `create_product` R7a [BUG-2778]
- **Kind:** bug
- **Expect:** xfail BUG-2778
- **Fails today on:** Then 2 (no ledger row is written)

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.create_product(db, data=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=0, avg_cost=Decimal("7.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `transaction_type == "manual_add"`, `quantity == 0`, `qty_before == 0`, `qty_after == 0`.
4. re-read E: `avg_cost_before is None`, `avg_cost_after == Decimal("7.00")`, `total_cost == Decimal("0.00")`.

### PRDM-C-09 — zero everywhere is accepted
- **Rules:** `create_product` R5 ("0 is accepted everywhere")
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.create_product(db, data=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=0, avg_cost=Decimal("0.00"), selling_price=Decimal("0.00"), min_order_qty=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `qty == 0`, `avg_cost == Decimal("0.00")`, `selling_price == Decimal("0.00")`, `min_order_qty == 0`.

### PRDM-C-10 — an unknown factory is not found
- **Rules:** `create_product` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.create_product(db, data=ProductCreate(item_id=I1.id, factory_id=MISSING, qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
4. session: session clean.
5. nothing written.

### PRDM-C-11 — a factory of W0 (lower workspace id) is not found
- **Rules:** `create_product` R1, Errors row 1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.create_product(db, data=ProductCreate(item_id=I1.id, factory_id=F0.id, qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {F0.id} not found"`.
4. session: session clean.
5. nothing written.

### PRDM-C-12 — a factory of W2 (higher workspace id) is not found
- **Rules:** `create_product` R1, Errors row 1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.create_product(db, data=ProductCreate(item_id=I1.id, factory_id=F9.id, qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {F9.id} not found"`.
4. session: session clean.
5. nothing written.

### PRDM-C-13 — an inactive but live factory is accepted
- **Rules:** `create_product` R2 (inactive-but-live side)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.create_product(db, data=ProductCreate(item_id=I1.id, factory_id=FI.id, qty=2), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `factory_id == FI.id`, `qty == 2`.
3. count: `ledger_of(FI, I1)` has exactly 1 row.

### PRDM-C-14 — a soft-deleted factory is not found
- **Rules:** `create_product` R2 [BUG-2780], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-2780
- **Fails today on:** Then 1 (no exception: the row is created)

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.create_product(db, data=ProductCreate(item_id=I1.id, factory_id=FD.id, qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {FD.id} not found"`.
4. session: session clean.
5. nothing written.

### PRDM-C-15 — a removed item is not found
- **Rules:** `create_product` R2a [BUG-2780], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-2780
- **Fails today on:** Then 1 (no exception: the row is created)

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.create_product(db, data=ProductCreate(item_id=IX.id, factory_id=F1.id, qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {IX.id} not found"`.
4. session: session clean.
5. nothing written.

### PRDM-C-16 — an item of W0 is not found
- **Rules:** `create_product` R2a [BUG-1011], Errors row 2; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-1011
- **Fails today on:** Then 1 (no exception: the row is created with W0's item)

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.create_product(db, data=ProductCreate(item_id=I0.id, factory_id=F1.id, qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {I0.id} not found"`.
4. session: session clean.
5. nothing written.

### PRDM-C-17 — an item of W2 is not found
- **Rules:** `create_product` R2a [BUG-1011], Errors row 2; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-1011
- **Fails today on:** Then 1 (no exception: the row is created with W2's item)

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.create_product(db, data=ProductCreate(item_id=I9.id, factory_id=F1.id, qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {I9.id} not found"`.
4. session: session clean.
5. nothing written.

### PRDM-C-18 — an unknown item is not found
- **Rules:** `create_product` R2a [BUG-1011], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1011
- **Fails today on:** Then 1 (the call raises IntegrityError: the foreign key fails at flush)

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.create_product(db, data=ProductCreate(item_id=MISSING, factory_id=F1.id, qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Item with ID 999999999 not found"`.
4. session: session clean.
5. nothing written.

### PRDM-C-19 — a live row of the same key is a conflict
- **Rules:** `create_product` R3, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 9`.

**When**
- `M.create_product(db, data=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=3, is_available_for_sale=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Product record already exists for this item/factory/availability combination"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(P).

### PRDM-C-20 — a for-sale row does not block a not-for-sale create
- **Rules:** `create_product` R3 (only the exact flag counts)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 9`.

**When**
- `result = M.create_product(db, data=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. returns: `result.id != P.id`.
3. re-read the returned row: `is_available_for_sale is False`, `qty == 3`.
4. unchanged: unchanged(P).

### PRDM-C-21 — rows of another factory or another item do not block
- **Rules:** `create_product` R3 (key = factory and item)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = stock, but `factory_id F2.id`.
2. PB = stock, but `item_id I2.id`.

**When**
- `result = M.create_product(db, data=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `products` with `workspace_id W1.id` has exactly 3 rows.
3. unchanged: unchanged(PA).
4. unchanged: unchanged(PB).

### PRDM-C-22 — same-key rows of W0 and W2 do not block a W1 create
- **Rules:** `create_product` R3 (workspace in the key); HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = stock, of W0.
2. P9 = stock, of W2.

**When**
- `result = M.create_product(db, data=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `qty == 3`.
3. unchanged: unchanged(P0).
4. unchanged: unchanged(P9).
5. count: `ledger_of(F1, I1)` has exactly 1 row.

### PRDM-C-23 — a soft-deleted row of the same key is a conflict
- **Rules:** `create_product` R4 [BUG-1336], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises IntegrityError 23505 at flush)

**Given**
1. P = stock, but deleted, `qty 0`.

**When**
- `M.create_product(db, data=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Product record already exists for this item/factory/availability combination"`.
4. session: session clean.
5. nothing written.

### PRDM-C-24 — the create is flushed but not committed
- **Rules:** `create_product` Returns ("flushed, not committed"); Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Savepoint and commit spy per **Rolled back**.

**When**
- `result = M.create_product(db, data=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=4), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `products` has exactly 1 row.
3. count: `product_ledger` has exactly 1 row.
4. count after the savepoint rollback: `products` has exactly 0 rows.
5. count after the savepoint rollback: `product_ledger` has exactly 0 rows.
6. mock called: the `db.commit` spy was never called.

### PRDM-C-25 — the schema refuses a negative quantity
- **Rules:** `create_product` R5 [BUG-2775], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-2775
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProductCreate(item_id=I1.id, factory_id=F1.id, qty=-1)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PRDM-C-26 — the schema refuses a negative average cost
- **Rules:** `create_product` R5 [BUG-2775]
- **Kind:** bug
- **Expect:** xfail BUG-2775
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProductCreate(item_id=I1.id, factory_id=F1.id, avg_cost=Decimal("-0.01"))` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PRDM-C-27 — the schema refuses a negative selling price
- **Rules:** `create_product` R5 [BUG-2775]
- **Kind:** bug
- **Expect:** xfail BUG-2775
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProductCreate(item_id=I1.id, factory_id=F1.id, selling_price=Decimal("-0.01"))` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PRDM-C-28 — the schema refuses a negative minimum order
- **Rules:** `create_product` R5 [BUG-2775]
- **Kind:** bug
- **Expect:** xfail BUG-2775
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProductCreate(item_id=I1.id, factory_id=F1.id, min_order_qty=-1)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PRDM-C-29 — the schema refuses an average cost with three decimals
- **Rules:** `create_product` R5 [BUG-2776]
- **Kind:** bug
- **Expect:** xfail BUG-2776
- **Fails today on:** Then 1 (no error is raised; today 10.005 × 3 is stored as row 10.01, ledger 30.02)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProductCreate(item_id=I1.id, factory_id=F1.id, qty=3, avg_cost=Decimal("10.005"))` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PRDM-C-30 — the schema refuses a selling price with three decimals
- **Rules:** `create_product` R5 [BUG-2776]
- **Kind:** bug
- **Expect:** xfail BUG-2776
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProductCreate(item_id=I1.id, factory_id=F1.id, selling_price=Decimal("1.005"))` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PRDM-C-31 — the schema refuses an average cost with 14 integer digits
- **Rules:** `create_product` R5 [BUG-2776]
- **Kind:** bug
- **Expect:** xfail BUG-2776
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProductCreate(item_id=I1.id, factory_id=F1.id, avg_cost=Decimal("10000000000000.00"))` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PRDM-C-32 — the schema refuses a selling price with 14 integer digits
- **Rules:** `create_product` R5 [BUG-2776]
- **Kind:** bug
- **Expect:** xfail BUG-2776
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProductCreate(item_id=I1.id, factory_id=F1.id, selling_price=Decimal("10000000000000"))` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PRDM-C-33 — the largest two-decimal cost and price pass the schema
- **Rules:** `create_product` R5 (other side of the 13-digit / 2-decimal limit)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = ProductCreate(item_id=I1.id, factory_id=F1.id, avg_cost=Decimal("9999999999999.99"), selling_price=Decimal("0.01"))` (target `schema`).

**Then**
1. returns: `result.avg_cost == Decimal("9999999999999.99")`.
2. returns: `result.selling_price == Decimal("0.01")`.

### PRDM-C-34 — the schema is checked before the factory
- **Rules:** `create_product` R0, R5 [BUG-2775]
- **Kind:** bug
- **Expect:** xfail BUG-2775
- **Fails today on:** Then 1 (no error: `qty -1` is accepted, so the call would reach the factory check)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProductCreate(item_id=I1.id, factory_id=MISSING, qty=-1)` (target `schema`; the manager is not called).

**Then**
1. raises: `PydanticValidationError`.
2. raises: `exc.value.errors()[0]["loc"] == ("qty",)`.
3. nothing written.

### PRDM-C-35 — an unknown factory wins over a removed item
- **Rules:** `create_product` R0, R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.create_product(db, data=ProductCreate(item_id=IX.id, factory_id=MISSING, qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
4. session: session clean.
5. nothing written.

### PRDM-C-36 — a soft-deleted factory wins over a removed item
- **Rules:** `create_product` R0, R2 [BUG-2780]
- **Kind:** bug
- **Expect:** xfail BUG-2780
- **Fails today on:** Then 1 (no exception: the row is created)

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.create_product(db, data=ProductCreate(item_id=IX.id, factory_id=FD.id, qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {FD.id} not found"`.
4. session: session clean.
5. nothing written.

### PRDM-C-37 — a removed item wins over a taken key
- **Rules:** `create_product` R0, R2a [BUG-2780]
- **Kind:** bug
- **Expect:** xfail BUG-2780
- **Fails today on:** Then 2 (status_code 409: the duplicate check answers first today)

**Given**
1. P = stock, but `item_id IX.id`, `qty 2` (a live row of the key F1 / IX / not for sale).

**When**
- `M.create_product(db, data=ProductCreate(item_id=IX.id, factory_id=F1.id, qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {IX.id} not found"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(P).

### PRDM-C-38 — a soft-deleted factory wins over a taken key
- **Rules:** `create_product` R0, R2 [BUG-2780]
- **Kind:** bug
- **Expect:** xfail BUG-2780
- **Fails today on:** Then 2 (status_code 409: the deleted factory passes today and the duplicate check answers)

**Given**
1. P = stock, but `factory_id FD.id`, `qty 2` (a live row of the key FD / I1 / not for sale).

**When**
- `M.create_product(db, data=ProductCreate(item_id=I1.id, factory_id=FD.id, qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {FD.id} not found"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(P).

## `ProductManager.update_product`

### PRDM-U-01 — an unknown id is not found
- **Rules:** `update_product` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. P = stock.

**When**
- `M.update_product(db, prod_id=MISSING, data=ProductUpdate(note="x"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Product record with ID 999999999 not found"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(P).

### PRDM-U-02 — a row of W0 (lower id) is not found from W1
- **Rules:** `update_product` R1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = stock, but `workspace_id W0.id`, `factory_id F0.id`, `item_id I0.id`.
2. P1 = stock.

**When**
- `M.update_product(db, prod_id=P0.id, data=ProductUpdate(qty=8), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Product record with ID {P0.id} not found"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(P0).

### PRDM-U-03 — a row of W2 (higher id) is not found from W1
- **Rules:** `update_product` R1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P1 = stock.
2. P9 = stock, but `workspace_id W2.id`, `factory_id F9.id`, `item_id I9.id`.

**When**
- `M.update_product(db, prod_id=P9.id, data=ProductUpdate(qty=8), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Product record with ID {P9.id} not found"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(P9).

### PRDM-U-04 — a soft-deleted row cannot be updated
- **Rules:** `update_product` R2, Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. P = stock, but deleted, `qty 0`.

**When**
- `M.update_product(db, prod_id=P.id, data=ProductUpdate(qty=8), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted product record"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(P).

### PRDM-U-05 — a soft-deleted row of W2 is "not found", not "deleted"
- **Rules:** `update_product` R1 before R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P9 = stock, but `workspace_id W2.id`, `factory_id F9.id`, `item_id I9.id`, deleted, `qty 0`.

**When**
- `M.update_product(db, prod_id=P9.id, data=ProductUpdate(qty=8), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Product record with ID {P9.id} not found"`.
4. session: session clean.
5. nothing written.

### PRDM-U-06 — fields other than qty are stored and stamped, with no ledger row
- **Rules:** `update_product` R5 (something changes), R6, R7 (no qty / cost change → no row)
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`, `selling_price Decimal("15.00")`, `min_order_qty 1`, `note "Old"`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(selling_price=Decimal("18.00"), min_order_qty=3, note="New"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `selling_price == Decimal("18.00")`, `min_order_qty == 3`, `note == "New"`.
3. re-read P: `qty == 5`, `avg_cost == Decimal("10.00")`, `is_available_for_sale is False`, `factory_id == F1.id`, `item_id == I1.id`.
4. re-read P: `updated_by == U2.id`, `created_by == U1.id`.
5. count: `product_ledger` has exactly 0 rows.

### PRDM-U-07 — omitted fields are left as they are
- **Rules:** `update_product` R3 (omitted → unchanged), R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`, `selling_price Decimal("15.00")`, `min_order_qty 1`, `note "Old"`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(note="Only note"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `note == "Only note"`.
3. re-read P: `qty == 5`, `avg_cost == Decimal("10.00")`, `selling_price == Decimal("15.00")`, `min_order_qty == 1`.

### PRDM-U-08 — raising the quantity writes one adjustment row
- **Rules:** `update_product` R7, R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(qty=8), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 8`, `avg_cost == Decimal("10.00")`, `updated_by == U2.id`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `transaction_type == "inventory_adjustment"`, `quantity == 3`, `qty_before == 5`, `qty_after == 8`.
5. re-read E: `unit_cost == Decimal("10.00")`, `total_cost == Decimal("30.00")`, `avg_cost_before == Decimal("10.00")`, `avg_cost_after == Decimal("10.00")`.
6. re-read E: `source_type == "adjustment"`, `source_id is None`, `transfer_source_type is None`, `transfer_source_id is None`, `transfer_destination_type is None`, `transfer_destination_id is None`.
7. re-read E: `notes == "Quantity adjusted from 5 to 8"`, `performed_by == U2.id`, `workspace_id == W1.id`.

### PRDM-U-09 — lowering the quantity records the size of the change
- **Rules:** `update_product` R7 (`quantity = |new − old|`)
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(qty=2), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 2`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `quantity == 3`, `qty_before == 5`, `qty_after == 2`, `total_cost == Decimal("30.00")`.
5. re-read E: `notes == "Quantity adjusted from 5 to 2"`.

### PRDM-U-10 — a change of one unit is recorded
- **Rules:** `update_product` R7 (smallest change)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(qty=6), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `quantity == 1`, `qty_before == 5`, `qty_after == 6`, `total_cost == Decimal("10.00")`.

### PRDM-U-11 — setting the quantity to 0 is recorded
- **Rules:** `update_product` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(qty=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 0`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `quantity == 5`, `qty_before == 5`, `qty_after == 0`, `total_cost == Decimal("50.00")`.
5. re-read E: `notes == "Quantity adjusted from 5 to 0"`.

### PRDM-U-12 — a new cost sent with the quantity prices the adjustment
- **Rules:** `update_product` R6, R7 (`avg_cost_after = unit_cost` = the cost sent)
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(qty=7, avg_cost=Decimal("12.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 7`, `avg_cost == Decimal("12.00")`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `quantity == 2`, `qty_before == 5`, `qty_after == 7`.
5. re-read E: `avg_cost_before == Decimal("10.00")`, `avg_cost_after == Decimal("12.00")`, `unit_cost == Decimal("12.00")`, `total_cost == Decimal("24.00")`.

### PRDM-U-13 — no cost: the adjustment has empty cost fields
- **Rules:** `update_product` R7, R8 (`unit_cost` None → `total_cost` NULL)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(qty=9), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `quantity == 4`, `unit_cost is None`, `total_cost is None`, `avg_cost_before is None`, `avg_cost_after is None`.

### PRDM-U-14 — a zero cost: the adjustment carries the zero cost
- **Rules:** `update_product` R7 (parts that hold today; BUG-2779 is U-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but `avg_cost Decimal("0.00")`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(qty=8), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `quantity == 3`, `unit_cost == Decimal("0.00")`, `avg_cost_before == Decimal("0.00")`, `avg_cost_after == Decimal("0.00")`.

### PRDM-U-15 — a zero cost gives an adjustment total of 0.00
- **Rules:** `update_product` R8 [BUG-2779]
- **Kind:** bug
- **Expect:** xfail BUG-2779
- **Fails today on:** Then 3 (`total_cost` is NULL)

**Given**
1. P = stock, but `avg_cost Decimal("0.00")`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(qty=8), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `total_cost == Decimal("0.00")`.

### PRDM-U-16 — the same quantity sent again writes no ledger row
- **Rules:** `update_product` R7 ("sent and differs")
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 5`, `avg_cost == Decimal("10.00")`.
3. count: `product_ledger` has exactly 0 rows.

### PRDM-U-17 — the same values sent again do not stamp updated_by
- **Rules:** `update_product` R5 [BUG-2771]; HR-9
- **Kind:** bug
- **Expect:** xfail BUG-2771
- **Fails today on:** Then 3 (`updated_by == U2.id`)

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`, `note "Same"`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(qty=5, note="Same"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. count: `product_ledger` has exactly 0 rows.
3. re-read P: `updated_by is None`.

### PRDM-U-18 — an empty body returns the row and writes no ledger row
- **Rules:** `update_product` R5 (part that holds today; the stamp is U-19)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 5`, `avg_cost == Decimal("10.00")`.
3. count: `product_ledger` has exactly 0 rows.

### PRDM-U-19 — an empty body does not stamp updated_by
- **Rules:** `update_product` R5 [BUG-2771]; HR-9
- **Kind:** bug
- **Expect:** xfail BUG-2771
- **Fails today on:** Then 2 (`updated_by == U2.id`)

**Given**
1. P = stock.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `updated_by is None`.

### PRDM-U-20 — changing only the cost: the row takes the new cost
- **Rules:** `update_product` R6 (part that holds today; the ledger row is U-21)
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(avg_cost=Decimal("12.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `avg_cost == Decimal("12.00")`, `qty == 5`, `updated_by == U2.id`.

### PRDM-U-21 — changing only the cost writes a zero-quantity adjustment row
- **Rules:** `update_product` R7 [BUG-2778]
- **Kind:** bug
- **Expect:** xfail BUG-2778
- **Fails today on:** Then 2 (no ledger row is written)

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(avg_cost=Decimal("12.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `transaction_type == "inventory_adjustment"`, `quantity == 0`, `qty_before == 5`, `qty_after == 5`.
4. re-read E: `avg_cost_before == Decimal("10.00")`, `avg_cost_after == Decimal("12.00")`, `unit_cost == Decimal("12.00")`, `total_cost == Decimal("0.00")`.
5. re-read E: `source_type == "adjustment"`, `notes == "Average cost adjusted from 10.00 to 12.00"`, `performed_by == U2.id`.

### PRDM-U-22 — the same quantity with a new cost also writes the cost row
- **Rules:** `update_product` R7 [BUG-2778] ("qty unchanged … but avg_cost changes")
- **Kind:** bug
- **Expect:** xfail BUG-2778
- **Fails today on:** Then 2 (no ledger row is written)

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(qty=5, avg_cost=Decimal("11.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `quantity == 0`, `qty_before == 5`, `qty_after == 5`, `avg_cost_after == Decimal("11.00")`.

### PRDM-U-23 — the same cost sent again writes no ledger row
- **Rules:** `update_product` R7 (cost "changes" means differs)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(avg_cost=Decimal("10.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `avg_cost == Decimal("10.00")`.
3. count: `product_ledger` has exactly 0 rows.

### PRDM-U-24 — an explicit null clears the selling price
- **Rules:** `update_product` R3 [BUG-2777]
- **Kind:** bug
- **Expect:** xfail BUG-2777
- **Fails today on:** Then 2 (`selling_price == Decimal("15.00")`)

**Given**
1. P = stock, but `selling_price Decimal("15.00")`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(selling_price=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `selling_price is None`.

### PRDM-U-25 — an explicit null clears the note
- **Rules:** `update_product` R3 [BUG-2777]
- **Kind:** bug
- **Expect:** xfail BUG-2777
- **Fails today on:** Then 2 (`note == "Old"`)

**Given**
1. P = stock, but `note "Old"`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(note=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `note is None`.

### PRDM-U-26 — an explicit null clears the minimum order
- **Rules:** `update_product` R3 [BUG-2777]
- **Kind:** bug
- **Expect:** xfail BUG-2777
- **Fails today on:** Then 2 (`min_order_qty == 4`)

**Given**
1. P = stock, but `min_order_qty 4`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(min_order_qty=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `min_order_qty is None`.

### PRDM-U-27 — an explicit null clears the cost and writes the cost row
- **Rules:** `update_product` R3, R7 [BUG-2777, BUG-2778]
- **Kind:** bug
- **Expect:** xfail BUG-2777, BUG-2778 (one marker, `reason="BUG-2777, BUG-2778"`; strict)
- **Fails today on:** Then 2 (`avg_cost == Decimal("10.00")`)

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(avg_cost=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `avg_cost is None`, `qty == 5`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `quantity == 0`, `qty_before == 5`, `qty_after == 5`, `avg_cost_before == Decimal("10.00")`, `avg_cost_after is None`, `total_cost is None`.
5. re-read E: `notes == "Average cost adjusted from 10.00 to None"`.

### PRDM-U-28 — the schema refuses an explicit null quantity
- **Rules:** `update_product` R3 [BUG-2777], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-2777
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProductUpdate(qty=None)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PRDM-U-29 — the schema refuses an explicit null for-sale flag
- **Rules:** `update_product` R3 [BUG-2777]
- **Kind:** bug
- **Expect:** xfail BUG-2777
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProductUpdate(is_available_for_sale=None)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PRDM-U-30 — the schema refuses a negative quantity
- **Rules:** `update_product` R4 [BUG-2775]
- **Kind:** bug
- **Expect:** xfail BUG-2775
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProductUpdate(qty=-1)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PRDM-U-31 — the schema refuses a negative average cost
- **Rules:** `update_product` R4 [BUG-2775]
- **Kind:** bug
- **Expect:** xfail BUG-2775
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProductUpdate(avg_cost=Decimal("-0.01"))` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PRDM-U-32 — the schema refuses a negative selling price
- **Rules:** `update_product` R4 [BUG-2775]
- **Kind:** bug
- **Expect:** xfail BUG-2775
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProductUpdate(selling_price=Decimal("-0.01"))` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PRDM-U-33 — the schema refuses a negative minimum order
- **Rules:** `update_product` R4 [BUG-2775]
- **Kind:** bug
- **Expect:** xfail BUG-2775
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProductUpdate(min_order_qty=-1)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PRDM-U-34 — the schema refuses a cost with three decimals
- **Rules:** `update_product` R4 [BUG-2776]
- **Kind:** bug
- **Expect:** xfail BUG-2776
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProductUpdate(avg_cost=Decimal("1.005"))` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PRDM-U-35 — the schema refuses a price with 14 integer digits
- **Rules:** `update_product` R4 [BUG-2776]
- **Kind:** bug
- **Expect:** xfail BUG-2776
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProductUpdate(selling_price=Decimal("10000000000000"))` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PRDM-U-36 — zero values pass the update schema and are stored
- **Rules:** `update_product` R4 (0 side), R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`, `selling_price Decimal("15.00")`, `min_order_qty 1`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(selling_price=Decimal("0.00"), min_order_qty=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `selling_price == Decimal("0.00")`, `min_order_qty == 0`.

### PRDM-U-37 — the update touches only its own row
- **Rules:** `update_product` R6; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = stock, of W0.
2. P = stock.
3. PA = stock, but for sale.
4. P9 = stock, of W2.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(qty=8), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 8`.
3. unchanged: unchanged(P0).
4. unchanged: unchanged(PA).
5. unchanged: unchanged(P9).
6. count: `product_ledger` has exactly 1 row.

### PRDM-U-38 — the update is flushed but not committed
- **Rules:** `update_product` Returns ("flushed"); Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = stock.
2. Savepoint and commit spy per **Rolled back**.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(qty=8), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. count: `product_ledger` has exactly 1 row.
3. count: `products` with `qty == 8` has exactly 1 row.
4. count after the savepoint rollback: `product_ledger` has exactly 0 rows.
5. count after the savepoint rollback: `products` with `qty == 5` has exactly 1 row.
6. mock called: the `db.commit` spy was never called.

### PRDM-U-39 — the row is read with a row lock
- **Rules:** `update_product` R11 [BUG-2770]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-2770
- **Fails today on:** Then 4 (no SELECT from `products` carries `FOR UPDATE`)

**Given**
1. P = stock.
2. Statement recorder on.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(qty=8), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. statement: `not any("SKIP LOCKED" in s for s in psel)`.
3. statement: `not any("NOWAIT" in s for s in psel)`.
4. statement: `any("FOR UPDATE" in s for s in psel)`.

### PRDM-U-52 — the new cost is printed as sent in the note
- **Rules:** `update_product` R7, R7a [BUG-2778]
- **Kind:** bug
- **Expect:** xfail BUG-2778
- **Fails today on:** Then 2 (no ledger row is written)

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(avg_cost=Decimal("12")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `notes == "Average cost adjusted from 10.00 to 12"`.
4. re-read E: `avg_cost_after == Decimal("12.00")`, `quantity == 0`.

### PRDM-U-53 — setting a cost on an uncosted row writes the note from None
- **Rules:** `update_product` R7, R7a, R8 [BUG-2778]
- **Kind:** bug
- **Expect:** xfail BUG-2778
- **Fails today on:** Then 2 (no ledger row is written)

**Given**
1. P = stock (`avg_cost` None, `qty 5`).

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(avg_cost=Decimal("12.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `notes == "Average cost adjusted from None to 12.00"`.
4. re-read E: `avg_cost_before is None`, `avg_cost_after == Decimal("12.00")`, `unit_cost == Decimal("12.00")`, `total_cost == Decimal("0.00")`.
5. re-read E: `quantity == 0`, `qty_before == 5`, `qty_after == 5`, `transaction_type == "inventory_adjustment"`.

### PRDM-U-55 — an adjustment with a cost in cents records an exact total
- **Rules:** `update_product` R7, R8 (`total_cost = unit_cost × quantity`, not rounded to whole units)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but `avg_cost Decimal("3.35")`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(qty=8), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `quantity == 3`, `unit_cost == Decimal("3.35")`, `total_cost == Decimal("10.05")`.

## `ProductManager.get_product`

### PRDM-G-01 — the workspace's row is returned
- **Rules:** `get_product` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`, `selling_price Decimal("15.00")`.

**When**
- `result = M.get_product(db, prod_id=P.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Product)`.
2. returns: `result.id == P.id`, `result.workspace_id == W1.id`, `result.qty == 5`, `result.avg_cost == Decimal("10.00")`, `result.selling_price == Decimal("15.00")`.

### PRDM-G-02 — an unknown id is not found
- **Rules:** `get_product` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. P = stock.

**When**
- `M.get_product(db, prod_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Product record with ID 999999999 not found"`.

### PRDM-G-03 — a row of W0 (lower id) is not found from W1
- **Rules:** `get_product` R1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = stock, but `workspace_id W0.id`, `factory_id F0.id`, `item_id I0.id`.
2. P1 = stock.

**When**
- `M.get_product(db, prod_id=P0.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Product record with ID {P0.id} not found"`.

### PRDM-G-04 — a row of W2 (higher id) is not found from W1
- **Rules:** `get_product` R1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P1 = stock.
2. P9 = stock, but `workspace_id W2.id`, `factory_id F9.id`, `item_id I9.id`.

**When**
- `M.get_product(db, prod_id=P9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Product record with ID {P9.id} not found"`.

### PRDM-G-05 — a row of an inactive but live factory is returned
- **Rules:** `get_product` R3 (inactive factory hides nothing)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but `factory_id FI.id`.

**When**
- `result = M.get_product(db, prod_id=P.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == P.id`.

### PRDM-G-06 — a soft-deleted row is not found by default
- **Rules:** `get_product` R2 [BUG-2772]; HR-4
- **Kind:** bug
- **Expect:** xfail BUG-2772
- **Fails today on:** Then 1 (no exception: the row is returned)

**Given**
1. P = stock, but deleted, `qty 0`.

**When**
- `M.get_product(db, prod_id=P.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Product record with ID {P.id} not found"`.

### PRDM-G-07 — include_deleted=True returns a soft-deleted row
- **Rules:** `get_product` R2 [BUG-2772]
- **Kind:** bug
- **Expect:** xfail BUG-2772
- **Fails today on:** Then 1 (the call raises TypeError: `include_deleted` does not exist)

**Given**
1. P = stock, but deleted, `qty 0`.

**When**
- `result = M.get_product(db, prod_id=P.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == P.id`.
2. returns: `result.is_deleted is True`.

### PRDM-G-08 — a row of a soft-deleted factory is not found by default
- **Rules:** `get_product` R3 [BUG-2773]
- **Kind:** bug
- **Expect:** xfail BUG-2773
- **Fails today on:** Then 1 (no exception: the row is returned)

**Given**
1. P = stock, but `factory_id FD.id`.

**When**
- `M.get_product(db, prod_id=P.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Product record with ID {P.id} not found"`.

### PRDM-G-09 — a row of a removed item is not found by default
- **Rules:** `get_product` R3 [BUG-2773]
- **Kind:** bug
- **Expect:** xfail BUG-2773
- **Fails today on:** Then 1 (no exception: the row is returned)

**Given**
1. P = stock, but `item_id IX.id`.

**When**
- `M.get_product(db, prod_id=P.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Product record with ID {P.id} not found"`.

### PRDM-G-10 — include_deleted=True returns a row of a soft-deleted factory
- **Rules:** `get_product` R3 [BUG-2773]
- **Kind:** bug
- **Expect:** xfail BUG-2773
- **Fails today on:** Then 1 (the call raises TypeError: `include_deleted` does not exist)

**Given**
1. P = stock, but `factory_id FD.id`.

**When**
- `result = M.get_product(db, prod_id=P.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == P.id`.

### PRDM-G-11 — the read takes no lock and writes nothing
- **Rules:** `get_product` Side effects (none); HR-10 scope
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = stock.
2. Statement recorder on.

**When**
- `result = M.get_product(db, prod_id=P.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. statement: `all("FOR UPDATE" not in s for s in selects)`.
3. statement: `written == []`.
4. session: `not db.dirty`.

## `ProductManager.list_products`

### PRDM-L-01 — the defaults return the workspace's live rows, as the DAO does
- **Rules:** `list_products` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P0 = stock, but `workspace_id W0.id`, `factory_id F0.id`, `item_id I0.id`.
2. PA = stock.
3. PB = stock, but for sale, `item_id I2.id`.
4. PC = stock, but `factory_id F2.id`, deleted, `qty 0`.
5. P9 = stock, but `workspace_id W2.id`, `factory_id F9.id`, `item_id I9.id`.

**When**
- `result = M.list_products(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(r.id for r in result) == [PA.id, PB.id]`.
2. read: `sorted(r.id for r in result) == sorted(r.id for r in product_dao.get_by_workspace(db, workspace_id=W1.id))`.

### PRDM-L-02 — the factory filter is passed on
- **Rules:** `list_products` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. PA = stock.
2. PB = stock, but `factory_id F2.id`.
3. PC = stock, but `item_id I2.id`.

**When**
- `result = M.list_products(db, workspace_id=W1.id, factory_id=F1.id, limit=1000)`.

**Then**
1. returns: `sorted(r.id for r in result) == [PA.id, PC.id]`.

### PRDM-L-03 — the for-sale filter is passed on
- **Rules:** `list_products` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. PA = stock.
2. PB = stock, but for sale.
3. PC = stock, but for sale, `item_id I2.id`.

**When**
- `result = M.list_products(db, workspace_id=W1.id, is_available_for_sale=True, limit=1000)`.

**Then**
1. returns: `sorted(r.id for r in result) == [PB.id, PC.id]`.

### PRDM-L-04 — the not-for-sale filter is passed on (False is a filter, not "none")
- **Rules:** `list_products` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = stock.
2. PB = stock, but for sale.

**When**
- `result = M.list_products(db, workspace_id=W1.id, is_available_for_sale=False, limit=1000)`.

**Then**
1. returns: `[r.id for r in result] == [PA.id]`.

### PRDM-L-05 — skip and limit are passed on
- **Rules:** `list_products` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Five rows: stock with `item_id I1.id`; stock with `item_id I2.id`; stock but for sale with `item_id I1.id`; stock but for sale with `item_id I2.id`; stock with `factory_id F2.id`.

**When**
- `result = M.list_products(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. read: `len(M.list_products(db, workspace_id=W1.id, skip=4, limit=2)) == 1`.

### PRDM-L-06 — the default limit is 100
- **Rules:** `list_products` R1 (default `limit 100`, `skip 0`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 items `"P000"` … `"P100"` (item recipe of the standing rows, W1), and for each one a stock row with that `item_id`.

**When**
- `result = M.list_products(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### PRDM-L-07 — the list takes no lock and writes nothing
- **Rules:** `list_products` Side effects (none)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PA = stock.
2. Statement recorder on.

**When**
- `result = M.list_products(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `[r.id for r in result] == [PA.id]`.
2. statement: `all("FOR UPDATE" not in s for s in selects)`.
3. statement: `written == []`.

## `ProductManager.delete_product`

### PRDM-D-01 — a row at 0 is soft-deleted and returned
- **Rules:** `delete_product` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = stock, but `qty 0`, `avg_cost Decimal("10.00")`, `selling_price Decimal("15.00")`.

**When**
- `result = M.delete_product(db, prod_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `is_deleted is True`, `is_active is False`, `deleted_at is not None`, `deleted_by == U2.id`.
3. re-read P: `updated_by is None`, `qty == 0`, `avg_cost == Decimal("10.00")`, `selling_price == Decimal("15.00")`.
4. count: `product_ledger` has exactly 0 rows.

### PRDM-D-02 — an unknown id is not found
- **Rules:** `delete_product` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. P = stock, but `qty 0`.

**When**
- `M.delete_product(db, prod_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Product record with ID 999999999 not found"`.
4. session: session clean.
5. unchanged: unchanged(P).

### PRDM-D-03 — a row of W0 (lower id) is not found from W1
- **Rules:** `delete_product` R1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = stock, but `workspace_id W0.id`, `factory_id F0.id`, `item_id I0.id`, `qty 0`.
2. P1 = stock, but `qty 0`.

**When**
- `M.delete_product(db, prod_id=P0.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Product record with ID {P0.id} not found"`.
4. session: session clean.
5. unchanged: unchanged(P0).

### PRDM-D-04 — a row of W2 (higher id) is not found from W1
- **Rules:** `delete_product` R1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P1 = stock, but `qty 0`.
2. P9 = stock, but `workspace_id W2.id`, `factory_id F9.id`, `item_id I9.id`, `qty 4`.

**When**
- `M.delete_product(db, prod_id=P9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Product record with ID {P9.id} not found"`.
4. session: session clean.
5. unchanged: unchanged(P9).

### PRDM-D-05 — an already deleted row is refused
- **Rules:** `delete_product` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. P = stock, but deleted, `qty 0`.

**When**
- `M.delete_product(db, prod_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Product record is already deleted"`.
4. session: session clean.
5. unchanged: unchanged(P).

### PRDM-D-06 — an already deleted row that kept stock is "already deleted"
- **Rules:** `delete_product` R2 before R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. P = stock, but deleted, `qty 4`.

**When**
- `M.delete_product(db, prod_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Product record is already deleted"`.
4. session: session clean.
5. unchanged: unchanged(P).

### PRDM-D-07 — a row holding stock is refused with its blocker
- **Rules:** `delete_product` R3 [BUG-2774]
- **Kind:** bug
- **Expect:** xfail BUG-2774
- **Fails today on:** Then 1 (no exception: the row is deleted with its stock)

**Given**
1. P = stock, but `qty 4`.

**When**
- `M.delete_product(db, prod_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Product record still holds stock"`.
4. raises: `exc.value.errors == [{"type": "product_stock", "id": P.id, "qty": 4}]`.
5. session: session clean.
6. nothing written.
7. unchanged: unchanged(P).

### PRDM-D-08 — a row with negative stock is refused with its blocker
- **Rules:** `delete_product` R3 [BUG-2774] (`qty ≠ 0`, negative side)
- **Kind:** bug
- **Expect:** xfail BUG-2774
- **Fails today on:** Then 1 (no exception: the row is deleted)

**Given**
1. P = stock, but `qty -2`.

**When**
- `M.delete_product(db, prod_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Product record still holds stock"`.
4. raises: `exc.value.errors == [{"type": "product_stock", "id": P.id, "qty": -2}]`.
5. session: session clean.
6. nothing written.
7. unchanged: unchanged(P).

### PRDM-D-09 — the delete touches only its own row
- **Rules:** `delete_product` R4; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = stock, of W0, `qty 0`.
2. P = stock, but `qty 0`.
3. PA = stock, but for sale, `qty 0`.
4. P9 = stock, of W2, `qty 0`.

**When**
- `result = M.delete_product(db, prod_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `is_deleted is True`.
3. unchanged: unchanged(P0).
4. unchanged: unchanged(PA).
5. unchanged: unchanged(P9).

### PRDM-D-10 — the delete takes no lock
- **Rules:** `delete_product` R4 (no lock, HR-10 exempt)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = stock, but `qty 0`.
2. Statement recorder on.

**When**
- `result = M.delete_product(db, prod_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. statement: `all("FOR UPDATE" not in s for s in selects)`.

### PRDM-D-11 — the delete is flushed but not committed
- **Rules:** `delete_product` Side effects ("flushed")
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = stock, but `qty 0`.
2. Savepoint and commit spy per **Rolled back**.

**When**
- `result = M.delete_product(db, prod_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. count: `products` with `is_deleted True` has exactly 1 row.
3. count after the savepoint rollback: `products` with `is_deleted True` has exactly 0 rows.
4. mock called: the `db.commit` spy was never called.

## `ProductManager.apply_production_output`

Cards in this section call with `unit_cost` not given (None), as both callers do. The costed path (R5–R7, intended for now, revisit after launch) is in its own section below.

### PRDM-PO-01 — output into a key with no row creates the not-for-sale bucket
- **Rules:** `apply_production_output` R2, R3, R4, R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, batch_id=77, notes="SYSTEM - PRODUCTION BATCH COMPLETE | B-17")`.

**Then**
1. returns: `isinstance(result, Product)` and `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `factory_id == F1.id`, `item_id == I1.id`, `is_available_for_sale is False`, `qty == 3`, `avg_cost is None`.
3. re-read the returned row: `created_by == U2.id`, `updated_by == U2.id`, `is_deleted is False`.
4. count: `ledger_of(F1, I1)` has exactly 1 row.
5. re-read E: `transaction_type == "production"`, `quantity == 3`, `qty_before == 0`, `qty_after == 3`.
6. re-read E: `unit_cost is None`, `total_cost is None`, `avg_cost_before is None`, `avg_cost_after is None`.
7. re-read E: `source_type == "production_batch"`, `source_id == 77`, `transfer_source_type is None`, `transfer_source_id is None`, `transfer_destination_type is None`, `transfer_destination_id is None`.
8. re-read E: `notes == "SYSTEM - PRODUCTION BATCH COMPLETE | B-17"`, `performed_by == U2.id`, `workspace_id == W1.id`.

### PRDM-PO-02 — output adds to the existing not-for-sale bucket and keeps its cost
- **Rules:** `apply_production_output` R2, R3, R4, R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=4, batch_id=77)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 9`, `avg_cost == Decimal("10.00")`, `updated_by == U2.id`.
3. count: `products` has exactly 1 row.
4. count: `ledger_of(F1, I1)` has exactly 1 row.
5. re-read E: `quantity == 4`, `qty_before == 5`, `qty_after == 9`.
6. re-read E: `unit_cost is None`, `total_cost is None`, `avg_cost_before == Decimal("10.00")`, `avg_cost_after == Decimal("10.00")`.

### PRDM-PO-03 — one unit is accepted
- **Rules:** `apply_production_output` R1 (other side of `<= 0`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=1, batch_id=77)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 6`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.

### PRDM-PO-04 — zero output is refused
- **Rules:** `apply_production_output` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. P = stock.

**When**
- `M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=0, batch_id=77)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Production output quantity must be positive"`.
3. session: session clean.
4. nothing written.
5. unchanged: unchanged(P).

### PRDM-PO-05 — negative output is refused, also with no bucket
- **Rules:** `apply_production_output` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=-1, batch_id=77)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Production output quantity must be positive"`.
3. session: session clean.
4. nothing written.

### PRDM-PO-06 — a for-sale row is never used: a not-for-sale row is created beside it
- **Rules:** `apply_production_output` R2, R2a ("the for-sale row is never touched")
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PS = stock, but for sale, `qty 20`.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, batch_id=77)`.

**Then**
1. returns: `result.id != PS.id`.
2. re-read the returned row: `is_available_for_sale is False`, `qty == 3`.
3. unchanged: unchanged(PS).
4. count: `ledger_of(F1, I1)` has exactly 1 row.
5. re-read E: `qty_before == 0`, `qty_after == 3`.

### PRDM-PO-07 — with both rows present, only the not-for-sale row moves
- **Rules:** `apply_production_output` R2, R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PS = stock, but for sale, `qty 20`.
2. P = stock.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, batch_id=77)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 8`.
3. unchanged: unchanged(PS).

### PRDM-PO-08 — rows of another factory or item are not touched
- **Rules:** `apply_production_output` R2 (key = factory and item)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = stock, but `factory_id F2.id`.
2. P = stock.
3. PB = stock, but `item_id I2.id`.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, batch_id=77)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 8`.
3. unchanged: unchanged(PA).
4. unchanged: unchanged(PB).

### PRDM-PO-09 — same-key rows of W0 and W2 are neither used nor touched
- **Rules:** `apply_production_output` R2 (workspace in the key); HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = stock, of W0, `qty 50`.
2. P9 = stock, of W2, `qty 60`.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, batch_id=77)`.

**Then**
1. returns: `result.id != P0.id` and `result.id != P9.id`.
2. re-read the returned row: `workspace_id == W1.id`, `qty == 3`.
3. unchanged: unchanged(P0).
4. unchanged: unchanged(P9).
5. count: `ledger_of(F1, I1)` has exactly 1 row.

### PRDM-PO-10 — no notes give the default batch note
- **Rules:** `apply_production_output` R8 (`notes` falsy → default)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, batch_id=77)`.

**Then**
1. returns: `result.id == P.id`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `notes == "SYSTEM - PRODUCTION BATCH COMPLETE | batch id 77"`.

### PRDM-PO-11 — empty notes also give the default batch note
- **Rules:** `apply_production_output` R8 (`""` takes the default)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, batch_id=78, notes="")`.

**Then**
1. returns: `result.id == P.id`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `notes == "SYSTEM - PRODUCTION BATCH COMPLETE | batch id 78"`.

### PRDM-PO-12 — a second call for the same batch posts again
- **Rules:** `apply_production_output` R9
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = stock.
2. `M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, batch_id=77)` (first posting, run as a step).
3. `db.expire_all()`.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, batch_id=77)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 11`.
3. count: `ledger_of(F1, I1)` has exactly 2 rows.
4. re-read `ledger_of(F1, I1)`: `[e.source_id for e in it] == [77, 77]`, `[e.qty_after for e in it] == [8, 11]`.

### PRDM-PO-13 — a negative bucket is added to
- **Rules:** `apply_production_output` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but `qty -2`.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=4, batch_id=77)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 2`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `qty_before == -2`, `qty_after == 2`, `quantity == 4`.

### PRDM-PO-14 — a soft-deleted not-for-sale row is restored and added to
- **Rules:** `apply_production_output` R2a [BUG-1336]
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises IntegrityError 23505: a new row is inserted)

**Given**
1. P = stock, but deleted, `qty 6`, `avg_cost Decimal("3.00")`.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=4, batch_id=77)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
3. re-read P: `qty == 10`, `avg_cost == Decimal("3.00")`, `updated_by == U2.id`, `is_available_for_sale is False`.
4. count: `products` has exactly 1 row.
5. count: `ledger_of(F1, I1)` has exactly 1 row.
6. re-read E: `transaction_type == "production"`, `qty_before == 6`, `qty_after == 10`, `quantity == 4`.

### PRDM-PO-15 — the bucket row is read with a row lock
- **Rules:** `apply_production_output` R10 [BUG-2770]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-2770
- **Fails today on:** Then 4 (no SELECT from `products` carries `FOR UPDATE`)

**Given**
1. P = stock.
2. Statement recorder on.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, batch_id=77)`.

**Then**
1. returns: `result.id == P.id`.
2. statement: `not any("SKIP LOCKED" in s for s in psel)`.
3. statement: `not any("NOWAIT" in s for s in psel)`.
4. statement: `any("FOR UPDATE" in s for s in psel)`.

### PRDM-PO-16 — the output is flushed but not committed
- **Rules:** `apply_production_output` Returns ("flushed"); Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Savepoint and commit spy per **Rolled back**.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, batch_id=77)`.

**Then**
1. returns: `result.id is not None`.
2. count: `products` has exactly 1 row.
3. count: `product_ledger` has exactly 1 row.
4. count after the savepoint rollback: `products` has exactly 0 rows.
5. count after the savepoint rollback: `product_ledger` has exactly 0 rows.
6. mock called: the `db.commit` spy was never called.

## `ProductManager.apply_sale_deduction`

### PRDM-SD-01 — a delivery takes units from the for-sale bucket at its average
- **Rules:** `apply_sale_deduction` R5, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 10`, `avg_cost Decimal("4.00")`.

**When**
- `result = M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, delivery_id=55, account_id=AC1.id, notes="Delivery DL-1 for SO-7")`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 7`, `avg_cost == Decimal("4.00")`, `updated_by == U2.id`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `transaction_type == "sale"`, `quantity == 3`, `qty_before == 10`, `qty_after == 7`.
5. re-read E: `unit_cost == Decimal("4.00")`, `total_cost == Decimal("12.00")`, `avg_cost_before == Decimal("4.00")`, `avg_cost_after == Decimal("4.00")`.
6. re-read E: `source_type == "sales_delivery"`, `source_id == 55`, `transfer_destination_type == "customer"`, `transfer_destination_id == AC1.id`, `transfer_source_type is None`, `transfer_source_id is None`.
7. re-read E: `notes == "Delivery DL-1 for SO-7"`, `performed_by == U2.id`, `workspace_id == W1.id`.

### PRDM-SD-02 — a whole Decimal quantity is used as whole units
- **Rules:** `apply_sale_deduction` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 10`, `avg_cost Decimal("4.00")`.

**When**
- `result = M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=Decimal("3.00"), delivery_id=55, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 7`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `quantity == 3`, `total_cost == Decimal("12.00")`.

### PRDM-SD-03 — taking exactly what is held leaves 0
- **Rules:** `apply_sale_deduction` R4 (equal allowed)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 3`, `avg_cost Decimal("4.00")`.

**When**
- `result = M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, delivery_id=55, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 0`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `qty_before == 3`, `qty_after == 0`.

### PRDM-SD-04 — a bucket with no cost records empty cost fields
- **Rules:** `apply_sale_deduction` R6 (average None → NULL)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 10`.

**When**
- `result = M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, delivery_id=55, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `unit_cost is None`, `total_cost is None`, `avg_cost_before is None`, `avg_cost_after is None`.

### PRDM-SD-05 — a zero average records a total of 0.00
- **Rules:** `apply_sale_deduction` R6 (0 → 0.00)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 10`, `avg_cost Decimal("0.00")`.

**When**
- `result = M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, delivery_id=55, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `unit_cost == Decimal("0.00")`, `total_cost == Decimal("0.00")`.

### PRDM-SD-06 — no notes and no account: default note, empty destination id
- **Rules:** `apply_sale_deduction` R6 (default notes; `account_id` may be NULL)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 10`.

**When**
- `result = M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, delivery_id=55)`.

**Then**
1. returns: `result.id == P.id`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `notes == "SYSTEM - SALES DELIVERY | delivery id 55"`.
4. re-read E: `transfer_destination_type == "customer"`, `transfer_destination_id is None`.

### PRDM-SD-07 — empty notes also give the default note
- **Rules:** `apply_sale_deduction` R6 (`notes` falsy)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 10`.

**When**
- `result = M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, delivery_id=56, account_id=AC1.id, notes="")`.

**Then**
1. returns: `result.id == P.id`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `notes == "SYSTEM - SALES DELIVERY | delivery id 56"`.

### PRDM-SD-08 — zero quantity is refused
- **Rules:** `apply_sale_deduction` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 10`.

**When**
- `M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=0, delivery_id=55, account_id=AC1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Sale deduction quantity must be positive"`.
3. session: session clean.
4. nothing written.
5. unchanged: unchanged(P).

### PRDM-SD-09 — a negative quantity is refused
- **Rules:** `apply_sale_deduction` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 10`.

**When**
- `M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=-1, delivery_id=55, account_id=AC1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Sale deduction quantity must be positive"`.
3. session: session clean.
4. nothing written.
5. unchanged: unchanged(P).

### PRDM-SD-10 — a negative fraction is refused as not positive, before the fraction check
- **Rules:** `apply_sale_deduction` R1 ("checked before R2")
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 10`.

**When**
- `M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=Decimal("-0.5"), delivery_id=55, account_id=AC1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Sale deduction quantity must be positive"`.
3. session: session clean.
4. nothing written.

### PRDM-SD-11 — a fractional quantity is refused
- **Rules:** `apply_sale_deduction` R3, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 10`.

**When**
- `M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=Decimal("2.5"), delivery_id=55, account_id=AC1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Delivery line has a fractional quantity; stock requires whole units"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(P).

### PRDM-SD-12 — no for-sale row: refused, available 0
- **Rules:** `apply_sale_deduction` R4 (part that holds today; text is SD-18), Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, delivery_id=55, account_id=AC1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail.startswith("Insufficient sellable stock for ")`.
4. raises: `exc.value.detail.endswith(": requested 3, available 0")`.
5. session: session clean.
6. nothing written.

### PRDM-SD-13 — too little stock: refused with what is available
- **Rules:** `apply_sale_deduction` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 2`, `avg_cost Decimal("4.00")`.

**When**
- `M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, delivery_id=55, account_id=AC1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail.endswith(": requested 3, available 2")`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(P).

### PRDM-SD-14 — a soft-deleted for-sale row counts as missing and is not restored
- **Rules:** `apply_sale_deduction` R4 (deleted row = available 0, not restored)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. P = stock, but for sale, deleted, `qty 10`.

**When**
- `M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, delivery_id=55, account_id=AC1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail.endswith(": requested 3, available 0")`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(P).

### PRDM-SD-15 — the not-for-sale row never counts
- **Rules:** `apply_sale_deduction` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but `qty 10`.

**When**
- `M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, delivery_id=55, account_id=AC1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail.endswith(": requested 3, available 0")`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(P).

### PRDM-SD-16 — for-sale rows of the same key in W0 and W2 do not count
- **Rules:** `apply_sale_deduction` R4 (workspace in the key); HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = stock, of W0, for sale, `qty 10`.
2. P9 = stock, of W2, for sale, `qty 10`.

**When**
- `M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, delivery_id=55, account_id=AC1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail.endswith(": requested 3, available 0")`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(P0).
7. unchanged: unchanged(P9).

### PRDM-SD-17 — a for-sale row of another factory does not count
- **Rules:** `apply_sale_deduction` R4 (key = factory)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = stock, but for sale, `factory_id F2.id`, `qty 10`.

**When**
- `M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, delivery_id=55, account_id=AC1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail.endswith(": requested 3, available 0")`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(PA).

### PRDM-SD-18 — the short-stock message names the item and factory
- **Rules:** `apply_sale_deduction` R4 [BUG-2782]
- **Kind:** bug
- **Expect:** xfail BUG-2782
- **Fails today on:** Then 3 (the detail says `for item <id> at factory <id>`)

**Given**
1. P = stock, but for sale, `qty 2`.

**When**
- `M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, delivery_id=55, account_id=AC1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == 'Insufficient sellable stock for "Bolt" at Factory One: requested 3, available 2'`.

### PRDM-SD-19 — the no-row message names the item and factory
- **Rules:** `apply_sale_deduction` R4 [BUG-2782]
- **Kind:** bug
- **Expect:** xfail BUG-2782
- **Fails today on:** Then 3 (the detail says `for item <id> at factory <id>`)

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F2.id, item_id=I2.id, quantity=3, delivery_id=55, account_id=AC1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == 'Insufficient sellable stock for "Cam" at Factory Two: requested 3, available 0'`.

### PRDM-SD-20 — only the W1 for-sale row moves; its neighbours stay
- **Rules:** `apply_sale_deduction` R4, R5; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = stock, of W0, for sale, `qty 10`.
2. PN = stock, but `qty 10`.
3. P = stock, but for sale, `qty 10`.
4. P9 = stock, of W2, for sale, `qty 10`.

**When**
- `result = M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, delivery_id=55, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 7`.
3. unchanged: unchanged(P0).
4. unchanged: unchanged(PN).
5. unchanged: unchanged(P9).

### PRDM-SD-21 — the for-sale row is read with a row lock
- **Rules:** `apply_sale_deduction` R7 [BUG-2770]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-2770
- **Fails today on:** Then 4 (no SELECT from `products` carries `FOR UPDATE`)

**Given**
1. P = stock, but for sale, `qty 10`.
2. Statement recorder on.

**When**
- `result = M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, delivery_id=55, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. statement: `not any("SKIP LOCKED" in s for s in psel)`.
3. statement: `not any("NOWAIT" in s for s in psel)`.
4. statement: `any("FOR UPDATE" in s for s in psel)`.

### PRDM-SD-22 — the deduction is flushed but not committed
- **Rules:** `apply_sale_deduction` Side effects ("flushed")
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 10`.
2. Savepoint and commit spy per **Rolled back**.

**When**
- `result = M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, delivery_id=55, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. count: `product_ledger` has exactly 1 row.
3. count: `products` with `qty == 7` has exactly 1 row.
4. count after the savepoint rollback: `product_ledger` has exactly 0 rows.
5. count after the savepoint rollback: `products` with `qty == 10` has exactly 1 row.
6. mock called: the `db.commit` spy was never called.

### PRDM-SD-23 — a delivery of one unit is accepted
- **Rules:** `apply_sale_deduction` R1 (other side of `<= 0`), R5, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 10`, `avg_cost Decimal("4.00")`.

**When**
- `result = M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=1, delivery_id=55, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 9`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `quantity == 1`, `qty_before == 10`, `qty_after == 9`, `total_cost == Decimal("4.00")`.

### PRDM-SD-24 — a delivery at an average in cents records an exact total
- **Rules:** `apply_sale_deduction` R6 (`total_cost = avg × quantity`, not rounded to whole units)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 10`, `avg_cost Decimal("4.35")`.

**When**
- `result = M.apply_sale_deduction(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, delivery_id=55, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `unit_cost == Decimal("4.35")`, `total_cost == Decimal("13.05")`, `avg_cost_before == Decimal("4.35")`, `avg_cost_after == Decimal("4.35")`.

## `ProductManager.apply_sale_return`

Cards in this section assert quantities, labels and notes. The cost of the returned units (R5, R6, and the BUG-2794 fallback R6a) has its own section below.

### PRDM-SR-01 — a customer return adds units to the for-sale bucket
- **Rules:** `apply_sale_return` R4, R5 (quantity), R7 (parts that hold today)
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 7`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=2, return_id=12, account_id=AC1.id, notes="Return SR-4 for SO-7")`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 9`, `is_available_for_sale is True`, `updated_by == U2.id`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `transaction_type == "return"`, `quantity == 2`, `qty_before == 7`, `qty_after == 9`.
5. re-read E: `source_id == 12`, `notes == "Return SR-4 for SO-7"`, `performed_by == U2.id`, `workspace_id == W1.id`.

### PRDM-SR-02 — the return row is labelled as coming from the customer
- **Rules:** `apply_sale_return` R7 [BUG-2783]
- **Kind:** bug
- **Expect:** xfail BUG-2783
- **Fails today on:** Then 3 (`source_type == "sales_return_item"`)

**Given**
1. P = stock, but for sale, `qty 7`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=2, return_id=12, account_id=AC1.id, notes="Return SR-4 for SO-7")`.

**Then**
1. returns: `result.id == P.id`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `source_type == "sales_return"`.
4. re-read E: `transfer_source_type == "customer"`, `transfer_source_id == AC1.id`.
5. re-read E: `transfer_destination_type is None`, `transfer_destination_id is None`.

### PRDM-SR-03 — no for-sale row: one is created and filled
- **Rules:** `apply_sale_return` R4 (created), R5 (quantity)
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=2, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `factory_id == F1.id`, `item_id == I1.id`, `is_available_for_sale is True`, `qty == 2`.
3. re-read the returned row: `created_by == U2.id`, `is_deleted is False`.
4. count: `ledger_of(F1, I1)` has exactly 1 row.
5. re-read E: `qty_before == 0`, `qty_after == 2`, `quantity == 2`.

### PRDM-SR-04 — a whole Decimal quantity is used as whole units
- **Rules:** `apply_sale_return` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 7`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=Decimal("2.00"), return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 9`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `quantity == 2`.

### PRDM-SR-05 — zero quantity is refused
- **Rules:** `apply_sale_return` R1, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 7`.

**When**
- `M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=0, return_id=12, account_id=AC1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Sale return quantity must be positive"`.
3. session: session clean.
4. nothing written.
5. unchanged: unchanged(P).

### PRDM-SR-06 — a negative quantity is refused, also with no bucket
- **Rules:** `apply_sale_return` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=-1, return_id=12, account_id=AC1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Sale return quantity must be positive"`.
3. session: session clean.
4. nothing written.

### PRDM-SR-07 — a fractional quantity is refused, and no bucket is created
- **Rules:** `apply_sale_return` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=Decimal("1.5"), return_id=12, account_id=AC1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Return line has a fractional quantity; stock requires whole units"`.
4. session: session clean.
5. nothing written.

### PRDM-SR-08 — no notes give the default return note
- **Rules:** `apply_sale_return` R7 (default notes)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 7`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=2, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `notes == "SYSTEM - SALES RETURN | return id 12"`.

### PRDM-SR-09 — empty notes also give the default return note
- **Rules:** `apply_sale_return` R7 (`notes` falsy)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 7`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=2, return_id=13, account_id=AC1.id, notes="")`.

**Then**
1. returns: `result.id == P.id`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `notes == "SYSTEM - SALES RETURN | return id 13"`.

### PRDM-SR-10 — the not-for-sale row is never used
- **Rules:** `apply_sale_return` R4 (for-sale bucket only)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PN = stock, but `qty 10`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=2, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id != PN.id`.
2. re-read the returned row: `is_available_for_sale is True`, `qty == 2`.
3. unchanged: unchanged(PN).

### PRDM-SR-11 — for-sale rows of the same key in W0 and W2 are neither used nor touched
- **Rules:** `apply_sale_return` R4 (workspace in the key); HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = stock, of W0, for sale, `qty 10`.
2. P9 = stock, of W2, for sale, `qty 10`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=2, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id != P0.id` and `result.id != P9.id`.
2. re-read the returned row: `workspace_id == W1.id`, `qty == 2`.
3. unchanged: unchanged(P0).
4. unchanged: unchanged(P9).

### PRDM-SR-12 — two lines of one item on one return give two rows with the same source
- **Rules:** `apply_sale_return` R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 7`.
2. `M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=2, return_id=12, account_id=AC1.id)` (first line, run as a step).
3. `db.expire_all()`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 12`.
3. count: `ledger_of(F1, I1)` has exactly 2 rows.
4. re-read `ledger_of(F1, I1)`: `[e.source_id for e in it] == [12, 12]`, `[e.qty_after for e in it] == [9, 12]`.

### PRDM-SR-13 — a soft-deleted for-sale row is restored and added to
- **Rules:** `apply_sale_return` R4 [BUG-1336]
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises IntegrityError 23505: a new row is inserted)

**Given**
1. P = stock, but for sale, deleted, `qty 4`, `avg_cost Decimal("3.00")`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=2, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
3. re-read P: `qty == 6`, `avg_cost == Decimal("3.00")`, `updated_by == U2.id`, `is_available_for_sale is True`.
4. count: `products` has exactly 1 row.
5. count: `ledger_of(F1, I1)` has exactly 1 row.
6. re-read E: `qty_before == 4`, `qty_after == 6`.

### PRDM-SR-14 — the for-sale row is read with a row lock
- **Rules:** `apply_sale_return` R9 [BUG-2770]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-2770
- **Fails today on:** Then 4 (no SELECT from `products` carries `FOR UPDATE`)

**Given**
1. P = stock, but for sale, `qty 7`.
2. Statement recorder on.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=2, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. statement: `not any("SKIP LOCKED" in s for s in psel)`.
3. statement: `not any("NOWAIT" in s for s in psel)`.
4. statement: `any("FOR UPDATE" in s for s in psel)`.

### PRDM-SR-15 — the return is flushed but not committed
- **Rules:** `apply_sale_return` Side effects ("flushed")
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Savepoint and commit spy per **Rolled back**.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=2, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `products` has exactly 1 row.
3. count: `product_ledger` has exactly 1 row.
4. count after the savepoint rollback: `products` has exactly 0 rows.
5. count after the savepoint rollback: `product_ledger` has exactly 0 rows.
6. mock called: the `db.commit` spy was never called.

### PRDM-SR-30 — a negative fraction is refused as not positive, before the fraction check
- **Rules:** `apply_sale_return` R1 (G6: checked before R3)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 7`.

**When**
- `M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=Decimal("-0.5"), return_id=12, account_id=AC1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Sale return quantity must be positive"`.
3. session: session clean.
4. nothing written.
5. unchanged: unchanged(P).

### PRDM-SR-31 — a return of one unit is accepted
- **Rules:** `apply_sale_return` R1 (other side of `<= 0`), R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 7`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=1, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 8`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `quantity == 1`, `qty_before == 7`, `qty_after == 8`.

## `ProductManager.apply_production_output` — costed output (R5–R7, intended for now: revisit after launch)

Every card here calls with a `unit_cost`, which no caller passes today (R7). The owner ruled this intended for now (OQ-50, 2026-11-17), to be revisited after launch, when production costing is designed. Revisit these cards then.

### PRDM-PO-17 — a costed output is weighted into the average
- **Rules:** `apply_production_output` R5, R8 (✅ OQ-50, revisit after launch)
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = stock, but `qty 10`, `avg_cost Decimal("5.00")`.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=10, batch_id=77, unit_cost=Decimal("6.00"))`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 20`, `avg_cost == Decimal("5.50")`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `unit_cost == Decimal("6.00")`, `total_cost == Decimal("60.00")`, `avg_cost_before == Decimal("5.00")`, `avg_cost_after == Decimal("5.50")`.
5. re-read E: `qty_before == 10`, `qty_after == 20`, `quantity == 10`.

### PRDM-PO-18 — a weighted average at an exact half cent rounds half up
- **Rules:** `apply_production_output` R5 [BUG-1040] (✅ OQ-50, revisit after launch); HR-15
- **Kind:** bug
- **Expect:** xfail BUG-1040
- **Fails today on:** Then 2 (`avg_cost == Decimal("1.12")`, half to even)

**Given**
1. P = stock, but `qty 3`, `avg_cost Decimal("1.00")`.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=1, batch_id=77, unit_cost=Decimal("1.50"))`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `avg_cost == Decimal("1.13")`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `avg_cost_after == Decimal("1.13")`.

### PRDM-PO-19 — a weighted average that is not a half cent rounds to the nearest cent
- **Rules:** `apply_production_output` R5, R8 (✅ OQ-50, revisit after launch)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but `qty 2`, `avg_cost Decimal("1.00")`.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=1, batch_id=77, unit_cost=Decimal("1.50"))`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 3`, `avg_cost == Decimal("1.17")`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `unit_cost == Decimal("1.50")`, `total_cost == Decimal("1.50")`, `avg_cost_before == Decimal("1.00")`, `avg_cost_after == Decimal("1.17")`.

### PRDM-PO-20 — a costed output into a new bucket takes the unit cost and records no cost before
- **Rules:** `apply_production_output` R2 (`avg_cost = unit_cost`), R6, R8, R8a [BUG-2811] (✅ OQ-50, revisit after launch)
- **Kind:** bug
- **Expect:** xfail BUG-2811
- **Fails today on:** Then 4 (`avg_cost_before == Decimal("6.00")`: the new row is seeded with the cost before the "before" value is read)

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=4, batch_id=77, unit_cost=Decimal("6.00"))`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `qty == 4`, `avg_cost == Decimal("6.00")`, `is_available_for_sale is False`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `unit_cost == Decimal("6.00")`, `total_cost == Decimal("24.00")`, `avg_cost_before is None`, `avg_cost_after == Decimal("6.00")`.

### PRDM-PO-21 — an empty bucket with an old average is revalued at the unit cost
- **Rules:** `apply_production_output` R6 (old `qty` 0) (✅ OQ-50, revisit after launch)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but `qty 0`, `avg_cost Decimal("9.00")`.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=4, batch_id=77, unit_cost=Decimal("6.00"))`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 4`, `avg_cost == Decimal("6.00")`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `avg_cost_before == Decimal("9.00")`, `avg_cost_after == Decimal("6.00")`.

### PRDM-PO-22 — a bucket with stock but no average is revalued at the unit cost
- **Rules:** `apply_production_output` R6 (old `avg_cost` None) (✅ OQ-50, revisit after launch)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=4, batch_id=77, unit_cost=Decimal("6.00"))`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 9`, `avg_cost == Decimal("6.00")`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `avg_cost_before is None`, `avg_cost_after == Decimal("6.00")`, `total_cost == Decimal("24.00")`.

### PRDM-PO-23 — a negative bucket is revalued at the unit cost
- **Rules:** `apply_production_output` R6 (old `qty` negative) (✅ OQ-50, revisit after launch)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but `qty -2`, `avg_cost Decimal("5.00")`.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=4, batch_id=77, unit_cost=Decimal("6.00"))`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 2`, `avg_cost == Decimal("6.00")`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `avg_cost_before == Decimal("5.00")`, `avg_cost_after == Decimal("6.00")`.

### PRDM-PO-24 — a zero unit cost is a cost: weighted in, total 0.00
- **Rules:** `apply_production_output` R5, R8 (`unit_cost` 0 → `total_cost` 0) (✅ OQ-50, revisit after launch)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but `qty 10`, `avg_cost Decimal("5.00")`.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=10, batch_id=77, unit_cost=Decimal("0.00"))`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 20`, `avg_cost == Decimal("2.50")`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `unit_cost == Decimal("0.00")`, `total_cost == Decimal("0.00")`, `avg_cost_after == Decimal("2.50")`.

### PRDM-PO-25 — an old average of 0.00 with stock is weighted as a real cost
- **Rules:** `apply_production_output` R5, R8 (✅ OQ-50, revisit after launch; G1: `is not None`, 0.00 counts)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but `qty 10`, `avg_cost Decimal("0.00")`.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=10, batch_id=77, unit_cost=Decimal("6.00"))`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 20`, `avg_cost == Decimal("3.00")`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `avg_cost_before == Decimal("0.00")`, `avg_cost_after == Decimal("3.00")`, `unit_cost == Decimal("6.00")`, `total_cost == Decimal("60.00")`.

### PRDM-PO-26 — a costed output into a new bucket: what holds today besides the cost before
- **Rules:** `apply_production_output` R2, R6, R8 (the parts of PO-20 that hold today and after BUG-2811)
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=4, batch_id=77, unit_cost=Decimal("6.00"))`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `qty == 4`, `avg_cost == Decimal("6.00")`, `is_available_for_sale is False`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `unit_cost == Decimal("6.00")`, `total_cost == Decimal("24.00")`, `avg_cost_after == Decimal("6.00")`, `qty_before == 0`, `qty_after == 4`.

### PRDM-PO-27 — a restored soft-deleted bucket is not new: its kept average is the cost before
- **Rules:** `apply_production_output` R2a [BUG-1336], R5, R8a (a restored row is not new)
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises IntegrityError 23505: a new row is inserted)

**Given**
1. P = stock, but deleted, `qty 6`, `avg_cost Decimal("3.00")`.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=4, batch_id=77, unit_cost=Decimal("6.00"))`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 10`, `avg_cost == Decimal("4.20")`, `is_deleted is False`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `qty_before == 6`, `qty_after == 10`, `avg_cost_before == Decimal("3.00")`, `avg_cost_after == Decimal("4.20")`, `unit_cost == Decimal("6.00")`, `total_cost == Decimal("24.00")`.

### PRDM-PO-28 — an old stock of 1 is weighted, not revalued
- **Rules:** `apply_production_output` R5 (old `qty > 0` at its smallest), R8 (✅ OQ-50, revisit after launch)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but `qty 1`, `avg_cost Decimal("2.00")`.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, batch_id=77, unit_cost=Decimal("4.00"))`.

**Then**
1. returns: `result.avg_cost == Decimal("3.50")` (in-session value, before any re-read).
2. re-read P: `qty == 4`, `avg_cost == Decimal("3.50")`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `avg_cost_before == Decimal("2.00")`, `avg_cost_after == Decimal("3.50")`, `total_cost == Decimal("12.00")`.

### PRDM-PO-29 — an average whose third decimal is below 5 rounds down, also in the session
- **Rules:** `apply_production_output` R5 (rounded to 2 places; not a half cent, so half up and half even agree), R8 (✅ OQ-50, revisit after launch)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but `qty 2`, `avg_cost Decimal("1.00")`.

**When**
- `result = M.apply_production_output(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=1, batch_id=77, unit_cost=Decimal("2.00"))`.

**Then**
1. returns: `result.avg_cost == Decimal("1.33")` (in-session value, before any re-read: 4.00 / 3 = 1.333…).
2. re-read P: `qty == 3`, `avg_cost == Decimal("1.33")`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `avg_cost_before == Decimal("1.00")`, `avg_cost_after == Decimal("1.33")`, `unit_cost == Decimal("2.00")`, `total_cost == Decimal("2.00")`.

## `ProductManager.update_product` — flipping the for-sale flag (R9 [BUG-2793], R10)

Flipping `is_available_for_sale`. Owner, 2026-11-17 (OQ-51): a row that holds stock is never flipped; its units move through `make_sellable`. A row at `qty 0` still flips, so every card that expects a flip or an R10 conflict uses a source row at `qty 0`.

### PRDM-U-40 — flipping a row that holds stock to for sale is refused
- **Rules:** `update_product` R9 [BUG-2793]; Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (no exception: the whole row is flipped today)

**Given**
1. P = stock, but `avg_cost Decimal("10.00")` (`qty 5`).

**When**
- `M.update_product(db, prod_id=P.id, data=ProductUpdate(is_available_for_sale=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Product record holds stock — use Make sellable to move units"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(P).

### PRDM-U-41 — flipping a stocked for-sale row back is refused too
- **Rules:** `update_product` R9 [BUG-2793] (either direction)
- **Kind:** bug
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (no exception: the row is flipped today)

**Given**
1. P = stock, but for sale, `avg_cost Decimal("10.00")` (`qty 5`).

**When**
- `M.update_product(db, prod_id=P.id, data=ProductUpdate(is_available_for_sale=False), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Product record holds stock — use Make sellable to move units"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(P).

### PRDM-U-42 — a flip sent with a new quantity is refused on a stocked row
- **Rules:** `update_product` R9 [BUG-2793] (a `qty` sent in the same call does not help)
- **Kind:** bug
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (no exception: flipped and adjusted today)

**Given**
1. P = stock, but `avg_cost Decimal("10.00")` (`qty 5`).

**When**
- `M.update_product(db, prod_id=P.id, data=ProductUpdate(is_available_for_sale=True, qty=8), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Product record holds stock — use Make sellable to move units"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(P).

### PRDM-U-43 — for-sale rows of the same key in W0 and W2 do not block a flip
- **Rules:** `update_product` R9, R10 (workspace in the key); HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = stock, of W0, for sale.
2. P = stock, but `qty 0`.
3. P9 = stock, of W2, for sale.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(is_available_for_sale=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `is_available_for_sale is True`.
3. unchanged: unchanged(P0).
4. unchanged: unchanged(P9).

### PRDM-U-44 — for-sale rows of another factory or item do not block a flip
- **Rules:** `update_product` R10 (key = factory and item)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = stock, but for sale, `factory_id F2.id`.
2. P = stock, but `qty 0`.
3. PB = stock, but for sale, `item_id I2.id`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(is_available_for_sale=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `is_available_for_sale is True`.
3. unchanged: unchanged(PA).
4. unchanged: unchanged(PB).

### PRDM-U-45 — flipping onto a key with a live row is a conflict
- **Rules:** `update_product` R10 [BUG-2781], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-2781
- **Fails today on:** Then 1 (the call raises IntegrityError 23505 at flush)

**Given**
1. PS = stock, but for sale, `qty 30`.
2. P = stock, but `qty 0`.

**When**
- `M.update_product(db, prod_id=P.id, data=ProductUpdate(is_available_for_sale=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Product record already exists for this item/factory/availability combination"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(P).
7. unchanged: unchanged(PS).

### PRDM-U-46 — flipping onto a key with a soft-deleted row is a conflict
- **Rules:** `update_product` R10 [BUG-2781]
- **Kind:** bug
- **Expect:** xfail BUG-2781
- **Fails today on:** Then 1 (the call raises IntegrityError 23505 at flush)

**Given**
1. PS = stock, but for sale, deleted, `qty 0`.
2. P = stock, but `qty 0`.

**When**
- `M.update_product(db, prod_id=P.id, data=ProductUpdate(is_available_for_sale=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Product record already exists for this item/factory/availability combination"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(P).

### PRDM-U-47 — a row at 0 flips to for sale with its cost and no ledger row
- **Rules:** `update_product` R9 (row at `qty 0` flips)
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = stock, but `qty 0`, `avg_cost Decimal("10.00")`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(is_available_for_sale=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `is_available_for_sale is True`, `qty == 0`, `avg_cost == Decimal("10.00")`, `updated_by == U2.id`.
3. count: `products` has exactly 1 row.
4. count: `product_ledger` has exactly 0 rows.

### PRDM-U-48 — a for-sale row at 0 flips back
- **Rules:** `update_product` R9 (row at `qty 0`, other direction)
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 0`, `avg_cost Decimal("10.00")`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(is_available_for_sale=False), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `is_available_for_sale is False`, `qty == 0`, `avg_cost == Decimal("10.00")`.
3. count: `product_ledger` has exactly 0 rows.

### PRDM-U-49 — a row at 0 flipped with a new quantity writes only the quantity adjustment
- **Rules:** `update_product` R9, R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = stock, but `qty 0`, `avg_cost Decimal("10.00")`.

**When**
- `result = M.update_product(db, prod_id=P.id, data=ProductUpdate(is_available_for_sale=True, qty=8), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `is_available_for_sale is True`, `qty == 8`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `transaction_type == "inventory_adjustment"`, `quantity == 8`, `qty_before == 0`, `qty_after == 8`.
5. re-read E: `unit_cost == Decimal("10.00")`, `total_cost == Decimal("80.00")`, `notes == "Quantity adjusted from 0 to 8"`.

### PRDM-U-50 — a row with negative stock is not "at 0" and is refused
- **Rules:** `update_product` R9 [BUG-2793] (`qty` not 0)
- **Kind:** bug
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (no exception: the row is flipped today)

**Given**
1. P = stock, but `qty -2`.

**When**
- `M.update_product(db, prod_id=P.id, data=ProductUpdate(is_available_for_sale=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Product record holds stock — use Make sellable to move units"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(P).

### PRDM-U-51 — a stocked row flipped with qty 0 sent is still refused (the stored qty decides)
- **Rules:** `update_product` R9 [BUG-2793]
- **Kind:** bug
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (no exception: flipped and set to 0 today)

**Given**
1. P = stock, but `qty 1`.

**When**
- `M.update_product(db, prod_id=P.id, data=ProductUpdate(is_available_for_sale=True, qty=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Product record holds stock — use Make sellable to move units"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(P).

### PRDM-U-54 — a stocked row flipped onto a taken key gets the stock refusal, not the conflict
- **Rules:** `update_product` R10a (R9 before R10), R9 [BUG-2793]
- **Kind:** bug
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises IntegrityError 23505 at flush, not HTTPException)

**Given**
1. PS = stock, but for sale, `qty 30`.
2. P = stock, but `avg_cost Decimal("10.00")` (`qty 5`).

**When**
- `M.update_product(db, prod_id=P.id, data=ProductUpdate(is_available_for_sale=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Product record holds stock — use Make sellable to move units"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(P).
7. unchanged: unchanged(PS).

## `ProductManager.apply_sale_return` — cost of returned units (R5, R6; R6a [BUG-2794])

Owner, 2026-11-17 (OQ-52): returned units come back at the bucket's average when it has one (0.00 counts); when it has none, at the `unit_cost` of the latest `sale` row of this workspace, factory and item that has a cost (`performed_at`, then `id`, descending), and the bucket takes that cost as its average.

### PRDM-SR-16 — returned units are valued at the bucket's current average, which is kept
- **Rules:** `apply_sale_return` R5, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 7`, `avg_cost Decimal("4.00")`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=2, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `avg_cost == Decimal("4.00")`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `unit_cost == Decimal("4.00")`, `total_cost == Decimal("8.00")`, `avg_cost_before == Decimal("4.00")`, `avg_cost_after == Decimal("4.00")`.

### PRDM-SR-17 — no average and no sale on record: the return has no cost
- **Rules:** `apply_sale_return` R6a (no costed sale: as today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 7`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=2, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `avg_cost is None`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `unit_cost is None`, `total_cost is None`, `avg_cost_before is None`, `avg_cost_after is None`.

### PRDM-SR-18 — a bucket created by the return, with no sale on record, has no average
- **Rules:** `apply_sale_return` R4 (`avg_cost None`), R6a (no costed sale)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=2, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `avg_cost is None`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `unit_cost is None`, `total_cost is None`.

### PRDM-SR-19 — a zero average records a total of 0.00
- **Rules:** `apply_sale_return` R5, R6 (0.00 is an average: 0 → 0.00)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 7`, `avg_cost Decimal("0.00")`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=2, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. count: `ledger_of(F1, I1)` has exactly 1 row.
3. re-read E: `unit_cost == Decimal("0.00")`, `total_cost == Decimal("0.00")`.

### PRDM-SR-20 — no average: the latest sale's cost is used and becomes the average
- **Rules:** `apply_sale_return` R6a [BUG-2794] (spec example)
- **Kind:** bug
- **Expect:** xfail BUG-2794
- **Fails today on:** Then 2 (`avg_cost is None`: no fallback today)

**Given**
1. S1 = sale entry, but `performed_at T1`, `unit_cost Decimal("50.00")`.
2. P = stock, but for sale, `qty 0` (no average).

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=4, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 4`, `avg_cost == Decimal("50.00")`.
3. count: `ledger_of(F1, I1)` has exactly 2 rows.
4. re-read N: `transaction_type == "return"`, `quantity == 4`, `qty_before == 0`, `qty_after == 4`.
5. re-read N: `unit_cost == Decimal("50.00")`, `total_cost == Decimal("200.00")`, `avg_cost_before is None`, `avg_cost_after == Decimal("50.00")`.
6. unchanged: unchanged(S1).

### PRDM-SR-21 — no bucket at all: the created bucket takes the latest sale's cost
- **Rules:** `apply_sale_return` R4, R6a [BUG-2794]
- **Kind:** bug
- **Expect:** xfail BUG-2794
- **Fails today on:** Then 2 (`avg_cost is None`)

**Given**
1. S1 = sale entry, but `performed_at T1`, `unit_cost Decimal("50.00")`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=4, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `qty == 4`, `is_available_for_sale is True`, `avg_cost == Decimal("50.00")`.
3. count: `ledger_of(F1, I1)` has exactly 2 rows.
4. re-read N: `unit_cost == Decimal("50.00")`, `total_cost == Decimal("200.00")`, `avg_cost_before is None`, `avg_cost_after == Decimal("50.00")`.

### PRDM-SR-22 — the latest sale is chosen by performed_at, not by id
- **Rules:** `apply_sale_return` R6a [BUG-2794] (latest = `performed_at` desc)
- **Kind:** bug
- **Expect:** xfail BUG-2794
- **Fails today on:** Then 2 (`avg_cost is None`)

**Given**
1. SA = sale entry, but `performed_at T2`, `unit_cost Decimal("50.00")` (lower id, later time).
2. SB = sale entry, but `performed_at T1`, `unit_cost Decimal("40.00")` (higher id, earlier time).
3. P = stock, but for sale, `qty 0`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=4, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `avg_cost == Decimal("50.00")`.
3. count: `ledger_of(F1, I1)` has exactly 3 rows.
4. re-read N: `unit_cost == Decimal("50.00")`, `total_cost == Decimal("200.00")`.

### PRDM-SR-23 — two sales at one time: the higher id wins
- **Rules:** `apply_sale_return` R6a [BUG-2794] (tie: `id` desc)
- **Kind:** bug
- **Expect:** xfail BUG-2794
- **Fails today on:** Then 2 (`avg_cost is None`)

**Given**
1. SA = sale entry, but `performed_at T1`, `unit_cost Decimal("40.00")`.
2. SB = sale entry, but `performed_at T1`, `unit_cost Decimal("45.00")` (same time, higher id).
3. P = stock, but for sale, `qty 0`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=4, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `avg_cost == Decimal("45.00")`.
3. count: `ledger_of(F1, I1)` has exactly 3 rows.
4. re-read N: `unit_cost == Decimal("45.00")`, `total_cost == Decimal("180.00")`.

### PRDM-SR-24 — a later sale with no cost is skipped for the latest costed one
- **Rules:** `apply_sale_return` R6a [BUG-2794] ("that has a `unit_cost`")
- **Kind:** bug
- **Expect:** xfail BUG-2794
- **Fails today on:** Then 2 (`avg_cost is None`)

**Given**
1. SA = sale entry, but `performed_at T1`, `unit_cost Decimal("30.00")`.
2. SB = sale entry, but `performed_at T2`, `unit_cost None`, `avg_cost_before None`, `avg_cost_after None`, `total_cost None`.
3. P = stock, but for sale, `qty 0`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=4, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `avg_cost == Decimal("30.00")`.
3. count: `ledger_of(F1, I1)` has exactly 3 rows.
4. re-read N: `unit_cost == Decimal("30.00")`, `total_cost == Decimal("120.00")`.

### PRDM-SR-25 — sales of the same key in W0 and W2 do not give a cost
- **Rules:** `apply_sale_return` R6a (other workspace: as today); HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S0 = sale entry, but `workspace_id W0.id`, `performed_at T1`, `unit_cost Decimal("50.00")` (invalid data on F1 / I1).
2. P = stock, but for sale, `qty 0`.
3. S9 = sale entry, but `workspace_id W2.id`, `performed_at T2`, `unit_cost Decimal("60.00")` (invalid data on F1 / I1).

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=4, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 4`, `avg_cost is None`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `unit_cost is None`, `total_cost is None`, `avg_cost_after is None`.
5. unchanged: unchanged(S0).
6. unchanged: unchanged(S9).

### PRDM-SR-26 — sales of another factory or item, and non-sale rows of the key, do not give a cost
- **Rules:** `apply_sale_return` R6a (only `sale` rows of this factory and item)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SF = sale entry, but `factory_id F2.id`, `performed_at T1`, `unit_cost Decimal("50.00")`.
2. SI = sale entry, but `item_id I2.id`, `performed_at T1`, `unit_cost Decimal("51.00")`.
3. SP = sale entry, but `transaction_type "production"`, `source_type "production_batch"`, `performed_at T2`, `unit_cost Decimal("52.00")`.
4. P = stock, but for sale, `qty 0`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=4, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 4`, `avg_cost is None`.
3. count: `ledger_of(F1, I1)` has exactly 2 rows.
4. re-read N: `transaction_type == "return"`, `unit_cost is None`, `total_cost is None`, `avg_cost_after is None`.

### PRDM-SR-27 — a bucket's own average wins over the last sale's cost
- **Rules:** `apply_sale_return` R5, R6 (average set: no fallback)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = sale entry, but `performed_at T1`, `unit_cost Decimal("50.00")`.
2. P = stock, but for sale, `qty 7`, `avg_cost Decimal("4.00")`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=4, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 11`, `avg_cost == Decimal("4.00")`.
3. count: `ledger_of(F1, I1)` has exactly 2 rows.
4. re-read N: `unit_cost == Decimal("4.00")`, `total_cost == Decimal("16.00")`, `avg_cost_before == Decimal("4.00")`, `avg_cost_after == Decimal("4.00")`.

### PRDM-SR-28 — an average of 0.00 is an average: the last sale's cost is not used
- **Rules:** `apply_sale_return` R5, R6 (0.00 counts)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = sale entry, but `performed_at T1`, `unit_cost Decimal("50.00")`.
2. P = stock, but for sale, `qty 7`, `avg_cost Decimal("0.00")`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=4, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `avg_cost == Decimal("0.00")`.
3. count: `ledger_of(F1, I1)` has exactly 2 rows.
4. re-read N: `unit_cost == Decimal("0.00")`, `total_cost == Decimal("0.00")`, `avg_cost_after == Decimal("0.00")`.

### PRDM-SR-29 — a restored uncosted bucket takes the latest sale's cost
- **Rules:** `apply_sale_return` R4 [BUG-1336], R6a [BUG-2794] (needs both fixes)
- **Kind:** bug
- **Expect:** xfail BUG-2794, BUG-1336 (one marker, `reason="BUG-2794, BUG-1336"`; strict)
- **Fails today on:** Then 1 (the call raises IntegrityError 23505: BUG-1336)

**Given**
1. S1 = sale entry, but `performed_at T1`, `unit_cost Decimal("50.00")`.
2. P = stock, but for sale, deleted, `qty 0`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=4, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `is_deleted is False`, `qty == 4`, `avg_cost == Decimal("50.00")`.
3. count: `products` has exactly 1 row.
4. re-read N: `unit_cost == Decimal("50.00")`, `total_cost == Decimal("200.00")`, `avg_cost_before is None`.

### PRDM-SR-32 — a return at an average in cents records an exact total
- **Rules:** `apply_sale_return` R6 (`total_cost = avg × quantity`, not rounded to whole units)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 7`, `avg_cost Decimal("2.15")`.

**When**
- `result = M.apply_sale_return(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, item_id=I1.id, quantity=3, return_id=12, account_id=AC1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `qty == 10`, `avg_cost == Decimal("2.15")`.
3. count: `ledger_of(F1, I1)` has exactly 1 row.
4. re-read E: `unit_cost == Decimal("2.15")`, `total_cost == Decimal("6.45")`, `avg_cost_before == Decimal("2.15")`, `avg_cost_after == Decimal("2.15")`.

## `ProductManager.make_sellable` (new method, BUG-2793)

Owner, 2026-11-17 (OQ-51): N units move from the not-for-sale bucket to the for-sale bucket of the same item and factory, with two linked ledger rows. The cost goes with the units and is weighted into the target. Every card is a strict xfail until the method exists.

### PRDM-MS-01 — units move into the existing for-sale bucket, weighted into its average
- **Rules:** make_sellable M3, M4, M5, M8, Returns
- **Kind:** happy
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")` (the not-for-sale source).
2. T = stock, but for sale, `qty 4`, `avg_cost Decimal("8.00")` (the for-sale target).

**When**
- `result = M.make_sellable(db, prod_id=S.id, quantity=3, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read S: `qty == 7`, `avg_cost == Decimal("5.00")`, `is_available_for_sale is False`, `updated_by == U2.id`.
3. re-read T: `qty == 7`, `avg_cost == Decimal("6.71")`, `is_available_for_sale is True`, `updated_by == U2.id`.
4. re-read S, T: `S.qty + T.qty == 14`.
5. count: `products` has exactly 2 rows.
6. count: `ledger_of(F1, I1)` has exactly 2 rows.

### PRDM-MS-02 — the out row records the source side and points at the target
- **Rules:** make_sellable M6 (out row)
- **Kind:** side-effect
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")` (the not-for-sale source).
2. T = stock, but for sale, `qty 4`, `avg_cost Decimal("8.00")` (the for-sale target).

**When**
- `result = M.make_sellable(db, prod_id=S.id, quantity=3, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read out: `transaction_type == "transfer"`, `source_type == "make_sellable"`, `source_id == T.id`, `quantity == 3`.
3. re-read out: `qty_before == 10`, `qty_after == 7`.
4. re-read out: `unit_cost == Decimal("5.00")`, `total_cost == Decimal("15.00")`, `avg_cost_before == Decimal("5.00")`, `avg_cost_after == Decimal("5.00")`.
5. re-read out: `transfer_destination_type == "product"`, `transfer_destination_id == T.id`.
6. re-read out: `notes == "Made sellable: 3 unit(s)"`, `performed_by == U2.id`, `workspace_id == W1.id`, `factory_id == F1.id`, `item_id == I1.id`.

### PRDM-MS-03 — the in row records the target side and points at the source
- **Rules:** make_sellable M5, M6 (in row)
- **Kind:** side-effect
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")` (the not-for-sale source).
2. T = stock, but for sale, `qty 4`, `avg_cost Decimal("8.00")` (the for-sale target).

**When**
- `result = M.make_sellable(db, prod_id=S.id, quantity=3, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read in: `transaction_type == "transfer"`, `source_type == "make_sellable"`, `source_id == S.id`, `quantity == 3`.
3. re-read in: `qty_before == 4`, `qty_after == 7`.
4. re-read in: `unit_cost == Decimal("5.00")`, `total_cost == Decimal("15.00")`, `avg_cost_before == Decimal("8.00")`, `avg_cost_after == Decimal("6.71")`.
5. re-read in: `transfer_source_type == "product"`, `transfer_source_id == S.id`.
6. re-read in: `notes == "Made sellable: 3 unit(s)"`, `performed_by == U2.id`, `workspace_id == W1.id`.

### PRDM-MS-04 — a weighted target average at an exact half cent rounds half up
- **Rules:** make_sellable M5 (HR-15)
- **Kind:** boundary
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 5`, `avg_cost Decimal("1.50")`.
2. T = stock, but for sale, `qty 3`, `avg_cost Decimal("1.00")`.

**When**
- `result = M.make_sellable(db, prod_id=S.id, quantity=1, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `qty == 4`, `avg_cost == Decimal("1.13")` ((3.00 + 1.50) / 4 = 1.125).
3. re-read in: `avg_cost_after == Decimal("1.13")`, `unit_cost == Decimal("1.50")`, `total_cost == Decimal("1.50")`.

### PRDM-MS-05 — a weighted average below a half cent rounds down
- **Rules:** make_sellable M5 (rounding, other side)
- **Kind:** boundary
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 5`, `avg_cost Decimal("1.50")`.
2. T = stock, but for sale, `qty 2`, `avg_cost Decimal("1.00")`.

**When**
- `result = M.make_sellable(db, prod_id=S.id, quantity=1, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `qty == 3`, `avg_cost == Decimal("1.17")` (3.50 / 3 = 1.1666…).

### PRDM-MS-06 — no for-sale row: the target is created with the source average
- **Rules:** make_sellable M3 (created), M5
- **Kind:** happy
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")` (the not-for-sale source).

**When**
- `result = M.make_sellable(db, prod_id=S.id, quantity=3, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id != S.id`.
2. re-read the returned row: `workspace_id == W1.id`, `factory_id == F1.id`, `item_id == I1.id`, `is_available_for_sale is True`.
3. re-read the returned row: `qty == 3`, `avg_cost == Decimal("5.00")`, `created_by == U2.id`, `is_deleted is False`.
4. re-read S: `qty == 7`.
5. count: `products` has exactly 2 rows.
6. re-read in: `qty_before == 0`, `qty_after == 3`, `avg_cost_before is None`, `avg_cost_after == Decimal("5.00")`, `transfer_source_id == S.id`.
7. re-read out: `transfer_destination_id == result.id`, `source_id == result.id`.

### PRDM-MS-07 — an empty target with an old average takes the source average
- **Rules:** make_sellable M5 (target `qty` 0: otherwise branch)
- **Kind:** boundary
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")` (the not-for-sale source).
2. T = stock, but for sale, `qty 0`, `avg_cost Decimal("9.00")`.

**When**
- `result = M.make_sellable(db, prod_id=S.id, quantity=3, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `qty == 3`, `avg_cost == Decimal("5.00")`.
3. re-read in: `avg_cost_before == Decimal("9.00")`, `avg_cost_after == Decimal("5.00")`.

### PRDM-MS-08 — a target holding stock with no average takes the source average
- **Rules:** make_sellable M5 (target average None)
- **Kind:** boundary
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")` (the not-for-sale source).
2. T = stock, but for sale, `qty 4` (no average).

**When**
- `result = M.make_sellable(db, prod_id=S.id, quantity=3, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `qty == 7`, `avg_cost == Decimal("5.00")`.
3. re-read in: `avg_cost_before is None`, `avg_cost_after == Decimal("5.00")`.

### PRDM-MS-09 — an uncosted source leaves the target average as it was, and the rows carry no cost
- **Rules:** make_sellable M5 (source average None), M6
- **Kind:** boundary
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10` (no average).
2. T = stock, but for sale, `qty 4`, `avg_cost Decimal("8.00")` (the for-sale target).

**When**
- `result = M.make_sellable(db, prod_id=S.id, quantity=3, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `qty == 7`, `avg_cost == Decimal("8.00")`.
3. re-read out: `unit_cost is None`, `total_cost is None`, `avg_cost_before is None`, `avg_cost_after is None`.
4. re-read in: `unit_cost is None`, `total_cost is None`, `avg_cost_before == Decimal("8.00")`, `avg_cost_after == Decimal("8.00")`.

### PRDM-MS-10 — an uncosted source into a missing target creates it with no average
- **Rules:** make_sellable M3, M5 (source average None)
- **Kind:** boundary
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10` (no average).

**When**
- `result = M.make_sellable(db, prod_id=S.id, quantity=3, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id != S.id`.
2. re-read the returned row: `qty == 3`, `avg_cost is None`, `is_available_for_sale is True`.
3. re-read in: `unit_cost is None`, `total_cost is None`, `avg_cost_after is None`.

### PRDM-MS-11 — a source average of 0.00 is a cost: weighted in, totals 0.00
- **Rules:** make_sellable M5, M6 (0 → 0.00)
- **Kind:** boundary
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("0.00")`.
2. T = stock, but for sale, `qty 4`, `avg_cost Decimal("8.00")` (the for-sale target).

**When**
- `result = M.make_sellable(db, prod_id=S.id, quantity=4, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `qty == 8`, `avg_cost == Decimal("4.00")`.
3. re-read out: `unit_cost == Decimal("0.00")`, `total_cost == Decimal("0.00")`.
4. re-read in: `unit_cost == Decimal("0.00")`, `total_cost == Decimal("0.00")`, `avg_cost_after == Decimal("4.00")`.

### PRDM-MS-12 — a soft-deleted for-sale row is restored as the target
- **Rules:** make_sellable M3 (restored, BUG-1336 columns)
- **Kind:** soft-delete
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")` (the not-for-sale source).
2. T = stock, but for sale, deleted, `qty 2`, `avg_cost Decimal("8.00")`.

**When**
- `result = M.make_sellable(db, prod_id=S.id, quantity=3, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`, `updated_by == U2.id`.
3. re-read T: `qty == 5`, `avg_cost == Decimal("6.20")` ((16.00 + 15.00) / 5).
4. count: `products` has exactly 2 rows.
5. re-read in: `qty_before == 2`, `qty_after == 5`, `avg_cost_before == Decimal("8.00")`, `avg_cost_after == Decimal("6.20")`.

### PRDM-MS-13 — moving everything the source holds is allowed and leaves it at 0
- **Rules:** make_sellable M2 (equal side)
- **Kind:** boundary
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")` (the not-for-sale source).
2. T = stock, but for sale, `qty 4`, `avg_cost Decimal("8.00")` (the for-sale target).

**When**
- `result = M.make_sellable(db, prod_id=S.id, quantity=10, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read S: `qty == 0`, `is_deleted is False`, `avg_cost == Decimal("5.00")`.
3. re-read T: `qty == 14`, `avg_cost == Decimal("5.86")` ((32.00 + 50.00) / 14 = 5.857…).
4. re-read out: `qty_before == 10`, `qty_after == 0`, `quantity == 10`, `total_cost == Decimal("50.00")`.

### PRDM-MS-14 — one unit is moved
- **Rules:** make_sellable M2 (smallest whole quantity)
- **Kind:** boundary
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")` (the not-for-sale source).
2. T = stock, but for sale, `qty 4`, `avg_cost Decimal("8.00")` (the for-sale target).

**When**
- `result = M.make_sellable(db, prod_id=S.id, quantity=1, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read S: `qty == 9`.
3. re-read T: `qty == 5`, `avg_cost == Decimal("7.40")` ((32.00 + 5.00) / 5).
4. re-read out: `quantity == 1`, `notes == "Made sellable: 1 unit(s)"`.

### PRDM-MS-15 — a whole Decimal quantity is accepted as whole units
- **Rules:** make_sellable M2 (`Decimal("3.00")` is whole)
- **Kind:** boundary
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")` (the not-for-sale source).
2. T = stock, but for sale, `qty 4`, `avg_cost Decimal("8.00")` (the for-sale target).

**When**
- `result = M.make_sellable(db, prod_id=S.id, quantity=Decimal("3.00"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read S: `qty == 7`.
3. re-read T: `qty == 7`.
4. re-read out: `quantity == 3`.

### PRDM-MS-16 — an unknown id is not found
- **Rules:** make_sellable M1; Errors row 1
- **Kind:** error
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. T = stock, but for sale, `qty 4`.

**When**
- `M.make_sellable(db, prod_id=MISSING, quantity=1, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Product record with ID 999999999 not found"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(T).

### PRDM-MS-17 — a source of W0 (lower workspace id) is not found from W1
- **Rules:** make_sellable M1 (HR-16)
- **Kind:** error
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S0 = stock, of W0, `qty 10`.

**When**
- `M.make_sellable(db, prod_id=S0.id, quantity=1, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Product record with ID {S0.id} not found"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(S0).

### PRDM-MS-18 — a source of W2 (higher workspace id) is not found from W1
- **Rules:** make_sellable M1 (HR-16)
- **Kind:** error
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S9 = stock, of W2, `qty 10`.

**When**
- `M.make_sellable(db, prod_id=S9.id, quantity=1, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Product record with ID {S9.id} not found"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(S9).

### PRDM-MS-19 — a soft-deleted source is refused
- **Rules:** make_sellable M1; Errors row 2
- **Kind:** error
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but deleted, `qty 10`.

**When**
- `M.make_sellable(db, prod_id=S.id, quantity=1, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted product record"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(S).

### PRDM-MS-20 — a for-sale source is refused
- **Rules:** make_sellable M1; Errors row 3
- **Kind:** error
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but for sale, `qty 10`.

**When**
- `M.make_sellable(db, prod_id=S.id, quantity=1, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Only a not-for-sale product record can be made sellable"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(S).

### PRDM-MS-21 — quantity 0 is refused
- **Rules:** make_sellable M2; Errors row 4
- **Kind:** error
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")` (the not-for-sale source).

**When**
- `M.make_sellable(db, prod_id=S.id, quantity=0, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Quantity must be a positive whole number"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(S).

### PRDM-MS-22 — a negative quantity is refused
- **Rules:** make_sellable M2
- **Kind:** error
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")` (the not-for-sale source).

**When**
- `M.make_sellable(db, prod_id=S.id, quantity=-1, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Quantity must be a positive whole number"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(S).

### PRDM-MS-23 — a fractional quantity is refused
- **Rules:** make_sellable M2
- **Kind:** error
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")` (the not-for-sale source).

**When**
- `M.make_sellable(db, prod_id=S.id, quantity=Decimal("1.5"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Quantity must be a positive whole number"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(S).

### PRDM-MS-24 — one more than the source holds is refused
- **Rules:** make_sellable M2; Errors row 5
- **Kind:** error
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")` (the not-for-sale source).
2. T = stock, but for sale, `qty 4`, `avg_cost Decimal("8.00")` (the for-sale target).

**When**
- `M.make_sellable(db, prod_id=S.id, quantity=11, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == "Insufficient stock to make sellable: requested 11, available 10"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(S).
7. unchanged: unchanged(T).

### PRDM-MS-25 — a deleted source is reported before a bad quantity
- **Rules:** make_sellable M2 (order: M1, then M2)
- **Kind:** error
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but deleted, `qty 10`.

**When**
- `M.make_sellable(db, prod_id=S.id, quantity=0, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted product record"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(S).

### PRDM-MS-26 — a for-sale source is reported before too large a quantity
- **Rules:** make_sellable M2 (order: M1, then M2)
- **Kind:** error
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but for sale, `qty 10`.

**When**
- `M.make_sellable(db, prod_id=S.id, quantity=99, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Only a not-for-sale product record can be made sellable"`.
4. session: session clean.
5. nothing written.
6. unchanged: unchanged(S).

### PRDM-MS-27 — for-sale rows of the same key in W0 and W2 are not the target
- **Rules:** make_sellable M3 (target in this workspace); HR-16
- **Kind:** isolation
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. T0 = stock, of W0, for sale, `qty 4`, `avg_cost Decimal("8.00")`.
2. S = stock, but `qty 10`, `avg_cost Decimal("5.00")` (the not-for-sale source).
3. T9 = stock, of W2, for sale, `qty 4`, `avg_cost Decimal("8.00")`.

**When**
- `result = M.make_sellable(db, prod_id=S.id, quantity=3, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id not in (T0.id, T9.id)`.
2. re-read the returned row: `workspace_id == W1.id`, `qty == 3`, `avg_cost == Decimal("5.00")`.
3. unchanged: unchanged(T0).
4. unchanged: unchanged(T9).
5. count: `product_ledger` rows with `workspace_id` W0 or W2 is exactly 0.

### PRDM-MS-28 — for-sale rows of another factory or item are not the target
- **Rules:** make_sellable M3 (same factory and item)
- **Kind:** isolation
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. TA = stock, but for sale, `factory_id F2.id`, `qty 4`.
2. S = stock, but `qty 10`, `avg_cost Decimal("5.00")` (the not-for-sale source).
3. TB = stock, but for sale, `item_id I2.id`, `qty 4`.

**When**
- `result = M.make_sellable(db, prod_id=S.id, quantity=3, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id not in (TA.id, TB.id)`.
2. re-read the returned row: `factory_id == F1.id`, `item_id == I1.id`, `qty == 3`.
3. unchanged: unchanged(TA).
4. unchanged: unchanged(TB).

### PRDM-MS-29 — the rows are read with a row lock
- **Rules:** make_sellable M7 (HR-10; the order of the two locks is Deferred)
- **Kind:** bug
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")` (the not-for-sale source).
2. T = stock, but for sale, `qty 4`, `avg_cost Decimal("8.00")` (the for-sale target).
3. Statement recorder on.

**When**
- `result = M.make_sellable(db, prod_id=S.id, quantity=3, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. statement: `any("FOR UPDATE" in s for s in psel)`.
3. statement: `not any("SKIP LOCKED" in s for s in psel)`.
4. statement: `not any("NOWAIT" in s for s in psel)`.

### PRDM-MS-30 — the move is flushed but not committed
- **Rules:** make_sellable M9
- **Kind:** side-effect
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")` (the not-for-sale source).
2. T = stock, but for sale, `qty 4`, `avg_cost Decimal("8.00")` (the for-sale target).
3. Savepoint and commit spy per **Rolled back**.

**When**
- `result = M.make_sellable(db, prod_id=S.id, quantity=3, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. count: `product_ledger` has exactly 2 rows.
3. count after the savepoint rollback: `product_ledger` has exactly 0 rows.
4. re-read S after the savepoint rollback: `qty == 10`.
5. mock called: the `db.commit` spy was never called.

## Deferred to other specs

| Rule | Owner | What must be tested there |
|---|---|---|
| `create_product` R4a [BUG-2781] (race) | integration tests | two creates of one key at once: the loser gets 409 with the fixed text, not 23505 |
| `update_product` R11, `apply_production_output` R10, `apply_sale_deduction` R7, `apply_sale_return` R9 [BUG-2770] (outcome) | integration tests | two sessions on one bucket: no lost update; the second delivery gets the 422; a lost insert race re-reads and posts. The unit cards only check `FOR UPDATE`. |
| `apply_production_output` R7 (✅ OQ-50, revisit after launch), FU-3 | `ProductionBatchManager` (`complete_batch`, `post_outputs_to_finished_goods`) | the callers pass no `unit_cost`; idempotent batch posting |
| `apply_sale_deduction` / `apply_sale_return` caller arguments (factory, account, notes text), FU-1, FU-2 | `SalesManager.complete_delivery`, `SalesService.complete_return`, `sales_order_return_manager` | the notes `Delivery {n} for SO-{n}` / `Return {n} for SO-{n}`; fractional quantities refused at entry |
| `list_products` R1 order and parent hiding (BUG-1325, BUG-1327) | `tests/unit/dao/product.cases.md` | already covered there; this manager passes through |
| `delete_product` R4 `deleted_at` clock (BUG-1335) | `tests/unit/dao/product.cases.md` | covered there |
| `delete_product` R3 [BUG-2774] 400 body; frontend BUG-2784 | `ProductService` / global handler; frontend | the `errors` list reaches the 400 body; the page shows it (no backend test for BUG-2784) |
| `make_sellable` M7 lock order (lower id first) and race outcome; the new endpoint (BUG-2793) | integration tests; `ProductService` / `POST /products/{id}/make-sellable/` | two moves on one pair do not deadlock; a concurrent deduction waits and M2 is checked on the locked quantity; the endpoint exists and answers per the Errors table |
| API translation (`ValueError` → 400, `IntegrityError` → generic handler, schema → 422) | batch / sales endpoints, `app/core/exceptions.py` | as the spec's Integration-only line |
| FU-4 (who may hand-edit stock) | `docs/future/permissions.md` | note only |

## Spec gaps

None. Gaps 1–6 are closed by the spec's Gap log G1–G6 (2026-11-17); gap 7 by G7 (2026-11-19, `update_product` R10a, card U-54).

## Coverage matrix

| Callable | Rule / Error row | Cases |
|---|---|---|
| `_quantity_to_int` | R1 | QI-01, QI-02, QI-03, QI-04, QI-05 |
| `_quantity_to_int` | R2; Errors row 1 | QI-06, QI-07, QI-08 |
| `create_product` | R0 (check order) | C-34, C-35, C-36, C-37, C-38 |
| `create_product` | R1; Errors row 1 | C-10, C-11, C-12, C-35 |
| `create_product` | R2 [BUG-2780] | C-13, C-14 |
| `create_product` | R2a [BUG-2780, BUG-1011]; Errors row 2 | C-15, C-16, C-17, C-18 |
| `create_product` | R3; Errors row 3 | C-19, C-20, C-21, C-22 |
| `create_product` | R4 [BUG-1336] | C-23 |
| `create_product` | R4a [BUG-2781] | Deferred |
| `create_product` | R5 [BUG-2775, BUG-2776]; Errors row 4 | C-09, C-25 … C-33 |
| `create_product` | R6 | C-01, C-02, C-07 |
| `create_product` | R7 [BUG-2779] | C-01, C-03, C-04, C-05, C-06 |
| `create_product` | R7a [BUG-2778] | C-02, C-08 |
| `create_product` | flushed, not committed | C-24 |
| `update_product` | R1; Errors row 1 | U-01, U-02, U-03, U-05 |
| `update_product` | R2; Errors row 2 | U-04 |
| `update_product` | R3 [BUG-2777] | U-07, U-24 … U-29 |
| `update_product` | R4 [BUG-2775, BUG-2776]; Errors row 4 | U-30 … U-36 |
| `update_product` | R5 [BUG-2771] | U-06, U-17, U-18, U-19 |
| `update_product` | R6 | U-06, U-07, U-12, U-20, U-36, U-37 |
| `update_product` | R7 [BUG-2778] | U-08 … U-14, U-16, U-21, U-22, U-23, U-27, U-49, U-52, U-53, U-55 |
| `update_product` | R7a (note text) | U-21, U-27, U-49, U-52, U-53 |
| `update_product` | R8 [BUG-2779] | U-08, U-13, U-15 |
| `update_product` | R9 [BUG-2793]; Errors row 3 | refused: U-40, U-41, U-42, U-50, U-51; row at 0 flips: U-43, U-44, U-47, U-48, U-49 |
| `update_product` | R10 [BUG-2781]; Errors row 4 | U-43, U-44, U-45, U-46, R10a: U-54 |
| `update_product` | R11 [BUG-2770] | U-39; outcome Deferred |
| `update_product` | flushed, not committed | U-38 |
| `get_product` | R1 | G-01, G-02, G-03, G-04 |
| `get_product` | R2 [BUG-2772] | G-06, G-07 |
| `get_product` | R3 [BUG-2773] | G-05, G-08, G-09, G-10 |
| `get_product` | side effects none, no lock | G-11 |
| `list_products` | R1 | L-01 … L-07 |
| `delete_product` | R1 | D-02, D-03, D-04 |
| `delete_product` | R2 | D-05, D-06 |
| `delete_product` | R3 [BUG-2774] | D-07, D-08 |
| `delete_product` | R4 | D-01, D-09, D-10, D-11 |
| `apply_production_output` | R1; Errors | PO-03, PO-04, PO-05 |
| `apply_production_output` | R2 | PO-01, PO-02, PO-06, PO-07, PO-08, PO-09, PO-20, PO-26 |
| `apply_production_output` | R2a [BUG-1336] (G3 columns) | PO-06, PO-07, PO-14, PO-27 |
| `apply_production_output` | R3 | PO-01, PO-02, PO-13 |
| `apply_production_output` | R4 | PO-01, PO-02 |
| `apply_production_output` | R5 [BUG-1040] (✅ OQ-50, revisit after launch) | PO-17, PO-18, PO-19, PO-24, PO-25 |
| `apply_production_output` | R6 (✅ OQ-50, revisit after launch) | PO-20, PO-21, PO-22, PO-23, PO-26 |
| `apply_production_output` | R7 (✅ OQ-50, revisit after launch) | Deferred (caller fact) |
| `apply_production_output` | R8 | PO-01, PO-02, PO-10, PO-11, PO-17, PO-24 |
| `apply_production_output` | R9 | PO-12 |
| `apply_production_output` | R10 [BUG-2770] | PO-15; outcome Deferred |
| `apply_production_output` | flushed, not committed | PO-16 |
| `apply_sale_deduction` | R1; Errors row 1 | SD-08, SD-09, SD-10 |
| `apply_sale_deduction` | R2 | SD-02 |
| `apply_sale_deduction` | R3; Errors row 2 | SD-11 |
| `apply_sale_deduction` | R4 [BUG-2782]; Errors row 3 | SD-03, SD-12 … SD-20 |
| `apply_sale_deduction` | R5 | SD-01, SD-20 |
| `apply_sale_deduction` | R6 | SD-01, SD-04, SD-05, SD-06, SD-07 |
| `apply_sale_deduction` | R7 [BUG-2770] | SD-21; outcome Deferred |
| `apply_sale_deduction` | flushed, not committed | SD-22 |
| `apply_sale_return` | R1; Errors | SR-05, SR-06, SR-30 |
| `apply_sale_return` | R2 | SR-04 |
| `apply_sale_return` | R3; Errors | SR-07 |
| `apply_sale_return` | R4 [BUG-1336] | SR-01, SR-03, SR-10, SR-11, SR-13, SR-18, SR-21, SR-29 |
| `apply_sale_return` | R5 | quantity: SR-01, SR-03, SR-04, SR-12; average kept: SR-16, SR-19, SR-27, SR-28 |
| `apply_sale_return` | R6 | SR-16, SR-19, SR-27, SR-28 |
| `apply_sale_return` | R6a [BUG-2794] | fallback: SR-20, SR-21, SR-22, SR-23, SR-24, SR-29; no costed sale (as today): SR-17, SR-18, SR-25, SR-26 |
| `apply_sale_return` | R7 [BUG-2783] | SR-01, SR-02, SR-08, SR-09 |
| `apply_sale_return` | R8 | SR-12 |
| `apply_sale_return` | R9 [BUG-2770] | SR-14; outcome Deferred |
| `apply_sale_return` | flushed, not committed | SR-15 |
| `make_sellable` | M1; Errors rows 1–3 | MS-16, MS-17, MS-18, MS-19, MS-20, MS-25, MS-26 |
| `make_sellable` | M2; Errors rows 4–5 | MS-13, MS-14, MS-15, MS-21, MS-22, MS-23, MS-24, MS-25, MS-26 |
| `make_sellable` | M3 | MS-01, MS-06, MS-10, MS-12, MS-27, MS-28 |
| `make_sellable` | M4 | MS-01, MS-13, MS-14 |
| `make_sellable` | M5 (HR-15) | MS-01, MS-03, MS-04, MS-05, MS-06, MS-07, MS-08, MS-09, MS-10, MS-11, MS-12 |
| `make_sellable` | M6 | MS-02, MS-03, MS-09, MS-11 |
| `make_sellable` | M7 | MS-29; lock order and race Deferred |
| `make_sellable` | M8 | MS-01 |
| `make_sellable` | M9 | MS-30; refusals MS-16 … MS-26 |
| `apply_production_output` | R5 (old qty 1; rounds down; in-session value) | PO-28, PO-29 |
| `apply_production_output` | R8a [BUG-2811] | PO-20; restored row not new PO-27; today-holding part PO-26 |
| `apply_sale_deduction` | R1 (quantity 1) ; R6 (total in cents) | SD-23, SD-24 |
| `apply_sale_return` | R1 (quantity 1); R6 (total in cents) | SR-31, SR-32 |
| `update_product` | R8 (total in cents) | U-55 |
