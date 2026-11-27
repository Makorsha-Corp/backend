# Test cases — `app/services/product_service.py`

> **Spec:** `tests/unit/services/product_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-22) — spec fill-gaps G1–G2: G1 confirms today's double rollback on a failing commit, contract stays `>= 1` (no card change); G2 states the `make_sellable` lock clause exactly (`FOR UPDATE OF products`, every bucket read, no `SKIP LOCKED` / `NOWAIT`, one commit) — PRDS-MS-10 Then tightened. Spec gaps closed.
> **Counts:** 92 cases · 58 expected-to-pass · 34 expected-to-fail (bugs) · 11 deferred

## Reviewer summary
- **Per callable:** `create_product` 18 (7 bug) · `update_product` 17 (7 bug) · `get_product` 11 (5 bug) · `list_products` 8 · `delete_product` 6 (1 bug) · `list_ledger` 21 (3 bug) · `make_sellable` 11 (11 bug, new method).
- **Depth:** lighter target (skill step 1a) for the pass-throughs: the manager and the ledger DAO own the stock rules and are not re-tested; each manager or DAO bug the spec lists gets one pass-through card (all strict, as in `product_manager.cases.md`; BUG-640's tied-order card non-strict, as in the ledger DAO). The transaction contract gets full shapes, because this service commits stock and ledger rows: every write has a commit card (commit spy called once, change survives a test rollback, TC2 `loaded`), rollback cards for each refusal status with an uncommitted extra workspace X that must be gone, and a failing-commit card (TC4) that also proves the ledger row is discarded. TC5 on `create_product` and `make_sellable`. TC6 on every read, also on a read that raises (no rollback).
- **Expected-to-fail:** BUG-2793 12 (MS-01 … MS-11, U-05) · BUG-2772 3 · BUG-2773 2 · BUG-1011, BUG-1336, BUG-2780, BUG-2779 ×2, BUG-2778 ×2, BUG-2775 ×2, BUG-2776, BUG-2771, BUG-2777, BUG-2781, BUG-2774, BUG-640 ×2 (one non-strict, one strict SQL recorder), BUG-992.
- **Passing companions (hold today and after the fix):** C-05, C-07, U-07 accept either today's `IntegrityError` or the intended `HTTPException` and check only "nothing saved, X gone, session usable"; C-10 / G-09 (inactive-but-live factory), C-12 / U-15 (zero-cost ledger row exists), C-14 / U-13 (cost stored), U-06 (a row at 0 flips), U-10 (a no-op still commits, writes no ledger row), D-05 (patched manager `ValidationError` passes as the same object), LG-11 (naive date bounds), LG-14 (different times newest first).
- **Notable design choices:**
  - **Lock clause (S4):** the spec says the lock itself is not unit-testable; per the batch rule, MS-10 checks the clause through the recorded SQL (both bucket reads carry exactly `FOR UPDATE OF products`, no bare `FOR UPDATE`, no `SKIP LOCKED` / `NOWAIT`) and that exactly one commit follows in the same call. The race outcome is deferred. `update_product`'s lock (BUG-2770) is the manager's card PRDM-U-39, not repeated.
  - **Schema bugs** (BUG-2775, BUG-2776) are written as the service call with the schema built inline in the When, so the card fails today because a row is stored.
  - D-05 and LG-15 are `Author: claude` (patched manager; forced sequential scan and non-strict).
- **Needs a decision:** None (both gaps closed in Revision 2).

## Conventions for this module

**IDs.** `PRDS` = `app/services/product_service.py`. `C` create_product · `U` update_product · `G` get_product · `L` list_products · `D` delete_product · `LG` list_ledger · `MS` make_sellable.

**Actors and fixed values.**
- `svc` = `product_service` (`from app.services.product_service import ProductService, product_service`). `db` = the test's real session, first argument; the rest by keyword. `result` = what the When returns. The session does not autoflush.
- Classes: `Product` (`app.models.product`), `ProductLedger` (`app.models.product_ledger`), `Factory` (`app.models.factory`), `Item` (`app.models.item`), `Workspace` (`app.models.workspace`). `ProductCreate`, `ProductUpdate` (`app.schemas.product`). `HTTPException` (`fastapi`). `AppValidationError` = `app.core.exceptions.ValidationError`. `PydanticValidationError` = `pydantic.ValidationError`. `IntegrityError`, `DataError` (`sqlalchemy.exc`). `inspect`, `text`, `select`, `func` (`sqlalchemy`). `patch` (`unittest.mock`). `Decimal`, `datetime`, `timedelta`, `timezone`.
- MISSING = `999999999`. T0 = `datetime(2026, 1, 15, 9, 0, 0)`. T1 … T5 = `datetime(2026, 3, 1, 9, 0, 0)`, `(…, 10, 0, 0)`, `(…, 11, 0, 0)`, `(…, 12, 0, 0)`, `(…, 13, 0, 0)`, all naive, all past.
- Money compares as `Decimal`; `qty`, `quantity`, `qty_before`, `qty_after` as `int`. `None` in a Then means `is None`.

**Standing rows** (every test, this order, each flushed, no Given line): W0, W1, W2 = `make_workspace(db)` three times (`W0.id < W1.id < W2.id`); U1, U2 = `make_profile(db)` twice; U2 is the acting user. Factories `Factory(workspace_id=…, name=…, abbreviation=…)`: F0 `"Zero Plant"`/`"Z0"` of W0; F1 `"Factory One"`/`"F1"`, F2 `"Factory Two"`/`"F2"` of W1; FD `"Old Plant"`/`"OP"` of W1 with `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`; FI `"Idle Plant"`/`"IP"` of W1 with `is_active False`; F9 `"Far Plant"`/`"F9"` of W2. Items `Item(workspace_id=…, name=…, name_normalized=<name lower case>, unit="pcs")`: I0 `"Zero Nut"` of W0; I1 `"Bolt"`, I2 `"Cam"` of W1; IX `"Old Gasket"` of W1 with `is_active False`; I9 `"Far Crate"` of W2.

**Given rows.** Built directly (never through `svc`), flushed one at a time in the order written. After "but" a line lists every column that differs. A line written as code is a step to run exactly. No Given holds two `products` rows of one key (workspace, item, factory, for-sale flag), deleted or not.
- **stock** = `Product(workspace_id=W1.id, item_id=I1.id, factory_id=F1.id, qty=5, created_by=U1.id)`; other columns default (`is_available_for_sale False`, `avg_cost`, `selling_price`, `note`, `updated_by` NULL). **for sale** = `is_available_for_sale True`. **deleted** = `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.
- **entry** = `ProductLedger(workspace_id=W1.id, factory_id=F1.id, item_id=I1.id, transaction_type="manual_add", quantity=1, qty_before=0, qty_after=1, performed_at=T1)`.
- **commit point** = after the last Given line without a marker, `db.commit()` (a savepoint release under the `db` fixture). Snapshots for `unchanged` and `nothing written` are taken there. Lines marked "(after the commit point)" run after it, uncommitted.
- **X** (after the commit point) = `X = make_workspace(db)` (flushed, not committed); `X_ID = X.id`.

**Named checks.**
- **re-read R** = `db.expire_all()`, then `db.get(<class>, R.id)`; database values.
- **unchanged(R)** = after re-read, every column of R equals its value at the commit point.
- **nothing written** = the numbers of `products` rows and of `product_ledger` rows (all workspaces) equal their values at the commit point (two asserts).
- **ledger_of(F, I)** = a fresh SELECT of `product_ledger` with `workspace_id W1.id`, that `factory_id` and `item_id`, ordered by `id`, as a list.
- **x_gone** = `db.expire_all()`, then `db.get(Workspace, X_ID) is None`.
- **loaded(r)** = `inspect(r).expired_attributes.isdisjoint({c.key for c in inspect(Product).column_attrs})`; runs first, before any attribute of `r` is read.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads with a fresh query.
- `session:` lines check `db` directly; **usable** = `db.execute(text("SELECT 1")).scalar() == 1`.
- `count:` lines use a fresh query with the filter stated.

**Errors and patches.**
- `raises: <Type>` = plain `with pytest.raises(<Type>) as exc:` around the When, **no** savepoint (the service rolls back itself); later lines assert on `exc.value`, one per line. `raises: IntegrityError or HTTPException` = `pytest.raises((IntegrityError, HTTPException))`.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When (inside any `raises` wrap).
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = the same with `patch.object(db, "refresh", side_effect=RuntimeError("boom"))` and no rollback spy. Checks after the block run with the patches gone.

**Statement recorder.** A `before_cursor_execute` listener on `db.connection()`, started at the end of the Given, removed after the When. `selects` = every recorded `SELECT`; `psel` = those whose text contains `FROM products`; `lsel` = the one whose text contains `FROM product_ledger`; `order_part` = the text of `lsel` after `ORDER BY` and before `LIMIT`. **no lock** = `all("FOR UPDATE" not in s for s in selects)`.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`. Write calls and checks exactly as shown, also when a parameter or method does not exist yet. Every MS card fails today at the call (`AttributeError`: `svc.make_sellable` does not exist).

**Race simulations.** None.

## `ProductService.create_product`

### PRDS-C-01 — a create is committed with its opening ledger row and returned re-read
- **Rules:** `create_product` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no `products` rows.

**When**
- spies: `result = svc.create_product(db, prod_in=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=4, avg_cost=Decimal("12.50")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: loaded(result).
2. returns: `isinstance(result, Product)`, `result.id is not None`, `result.created_at is not None`.
3. returns: `result.qty == 4`, `result.created_by == U2.id`.
4. mock called: `cm.call_count == 1`.
5. mock called: `rb.call_count == 0`.
6. committed: the `products` row with `id == result.id` has `workspace_id == W1.id`, `item_id == I1.id`, `factory_id == F1.id`, `qty == 4`, `avg_cost == Decimal("12.50")`.
7. committed: `ledger_of(F1, I1)` has exactly 1 row.
8. committed: that row has `transaction_type == "manual_add"`, `quantity == 4`, `qty_before == 0`, `qty_after == 4`, `total_cost == Decimal("50.00")`, `performed_by == U2.id`.

### PRDS-C-02 — quantity 0 and no cost: the row is committed with no ledger row
- **Rules:** `create_product` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no `products` rows.

**When**
- `result = svc.create_product(db, prod_in=ProductCreate(item_id=I1.id, factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`, `result.qty == 0`.
2. committed: the `products` row with `id == result.id` has `qty == 0`, `avg_cost is None`, `is_available_for_sale is False`.
3. committed: `product_ledger` has exactly 0 rows.

### PRDS-C-03 — an unknown factory: the 404 passes unchanged and the session is rolled back
- **Rules:** `create_product` R2, Errors row 1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no `products` rows.
2. X (after the commit point).

**When**
- spies: `svc.create_product(db, prod_in=ProductCreate(item_id=I1.id, factory_id=MISSING, qty=3), workspace_id=W1.id, user_id=U2.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
3. mock called: `rb.call_count >= 1`.
4. mock called: `cm.call_count == 0`.
5. count: x_gone.
6. nothing written: nothing written.
7. session: usable.

### PRDS-C-04 — a live row of the key: the 409 passes unchanged and the session is rolled back
- **Rules:** `create_product` R2, Errors row 3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. P = stock, but for sale, `qty 9`.
2. X (after the commit point).

**When**
- `svc.create_product(db, prod_in=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=3, is_available_for_sale=True), workspace_id=W1.id, user_id=U2.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 409`.
2. raises: `exc.value.detail == "Product record already exists for this item/factory/availability combination"`.
3. count: x_gone.
4. nothing written: nothing written.
5. unchanged: unchanged(P).
6. session: usable.

### PRDS-C-05 — an unknown item: whatever is raised, nothing is saved and the session is rolled back
- **Rules:** `create_product` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no `products` rows.
2. X (after the commit point).

**When**
- `svc.create_product(db, prod_in=ProductCreate(item_id=MISSING, factory_id=F1.id, qty=3), workspace_id=W1.id, user_id=U2.id)`, inside `raises: IntegrityError or HTTPException`.

**Then**
1. raises: `isinstance(exc.value, (IntegrityError, HTTPException))`.
2. count: x_gone.
3. nothing written: nothing written.
4. session: usable.

### PRDS-C-06 — pass-through BUG-1011: an unknown item gets the 404
- **Rules:** `create_product` R2 [BUG-1011]
- **Kind:** bug
- **Expect:** xfail BUG-1011
- **Fails today on:** Then 1 (the call raises IntegrityError: the item foreign key fails at flush)

**Given**
1. W1 has no `products` rows.

**When**
- `svc.create_product(db, prod_in=ProductCreate(item_id=MISSING, factory_id=F1.id, qty=3), workspace_id=W1.id, user_id=U2.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Item with ID 999999999 not found"`.
3. nothing written: nothing written.

### PRDS-C-07 — a soft-deleted row of the key: whatever is raised, nothing is saved and the session is rolled back
- **Rules:** `create_product` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. P = stock, but deleted, `qty 0`.
2. X (after the commit point).

**When**
- `svc.create_product(db, prod_in=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=3), workspace_id=W1.id, user_id=U2.id)`, inside `raises: IntegrityError or HTTPException`.

**Then**
1. raises: `isinstance(exc.value, (IntegrityError, HTTPException))`.
2. count: x_gone.
3. nothing written: nothing written.
4. unchanged: unchanged(P).
5. session: usable.

### PRDS-C-08 — pass-through BUG-1336: a soft-deleted row of the key gets the 409
- **Rules:** `create_product` R2 [BUG-1336]
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises IntegrityError 23505 at flush)

**Given**
1. P = stock, but deleted, `qty 0`.

**When**
- `svc.create_product(db, prod_in=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=3), workspace_id=W1.id, user_id=U2.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 409`.
2. raises: `exc.value.detail == "Product record already exists for this item/factory/availability combination"`.
3. nothing written: nothing written.

### PRDS-C-09 — pass-through BUG-2780: a soft-deleted factory gets the 404
- **Rules:** `create_product` R2 [BUG-2780]
- **Kind:** bug
- **Expect:** xfail BUG-2780
- **Fails today on:** Then 1 (no error is raised: the row is created in the deleted factory)

**Given**
1. W1 has no `products` rows.

**When**
- `svc.create_product(db, prod_in=ProductCreate(item_id=I1.id, factory_id=FD.id, qty=3), workspace_id=W1.id, user_id=U2.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Factory with ID {FD.id} not found"`.
3. nothing written: nothing written.

### PRDS-C-10 — an inactive but live factory is accepted and committed
- **Rules:** `create_product` R1 (BUG-2780 companion)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no `products` rows.

**When**
- `result = svc.create_product(db, prod_in=ProductCreate(item_id=I1.id, factory_id=FI.id, qty=2), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.factory_id == FI.id`.
2. committed: the `products` row with `id == result.id` has `factory_id == FI.id`, `qty == 2`.
3. committed: `ledger_of(FI, I1)` has exactly 1 row.

### PRDS-C-11 — pass-through BUG-2779: a zero cost gives a ledger total of 0.00
- **Rules:** `create_product` R1 [BUG-2779]
- **Kind:** bug
- **Expect:** xfail BUG-2779
- **Fails today on:** Then 3 (`total_cost` is NULL)

**Given**
1. W1 has no `products` rows.

**When**
- `result = svc.create_product(db, prod_in=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=5, avg_cost=Decimal("0.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: `ledger_of(F1, I1)` has exactly 1 row.
3. committed: that row has `total_cost == Decimal("0.00")`.

### PRDS-C-12 — a zero cost: the opening ledger row is committed with the zero unit cost
- **Rules:** `create_product` R1 (BUG-2779 companion)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no `products` rows.

**When**
- `result = svc.create_product(db, prod_in=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=5, avg_cost=Decimal("0.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: `ledger_of(F1, I1)` has exactly 1 row.
3. committed: that row has `quantity == 5`, `unit_cost == Decimal("0.00")`, `avg_cost_after == Decimal("0.00")`.

### PRDS-C-13 — pass-through BUG-2778: quantity 0 with a cost writes a zero-quantity ledger row
- **Rules:** `create_product` R1 [BUG-2778]
- **Kind:** bug
- **Expect:** xfail BUG-2778
- **Fails today on:** Then 2 (no ledger row is written)

**Given**
1. W1 has no `products` rows.

**When**
- `result = svc.create_product(db, prod_in=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=0, avg_cost=Decimal("7.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: `ledger_of(F1, I1)` has exactly 1 row.
3. committed: that row has `transaction_type == "manual_add"`, `quantity == 0`, `avg_cost_after == Decimal("7.00")`, `total_cost == Decimal("0.00")`.

### PRDS-C-14 — quantity 0 with a cost: the row is committed with its cost
- **Rules:** `create_product` R1 (BUG-2778 companion)
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no `products` rows.

**When**
- `result = svc.create_product(db, prod_in=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=0, avg_cost=Decimal("7.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: the `products` row with `id == result.id` has `qty == 0`, `avg_cost == Decimal("7.00")`.

### PRDS-C-15 — pass-through BUG-2775: a negative quantity is refused by the schema, nothing saved
- **Rules:** `create_product` R2 [BUG-2775]
- **Kind:** bug
- **Expect:** xfail BUG-2775
- **Fails today on:** Then 1 (no error is raised: a row with `qty -5` is created)

**Given**
1. W1 has no `products` rows.

**When**
- `svc.create_product(db, prod_in=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=-5), workspace_id=W1.id, user_id=U2.id)`, inside `raises: PydanticValidationError` (the schema is built inside the wrap).

**Then**
1. raises: `exc.type is PydanticValidationError`.
2. nothing written: nothing written.

### PRDS-C-16 — pass-through BUG-2776: a cost with three decimals is refused by the schema, nothing saved
- **Rules:** `create_product` R2 [BUG-2776]
- **Kind:** bug
- **Expect:** xfail BUG-2776
- **Fails today on:** Then 1 (no error is raised: the row is created with 10.01)

**Given**
1. W1 has no `products` rows.

**When**
- `svc.create_product(db, prod_in=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=3, avg_cost=Decimal("10.005")), workspace_id=W1.id, user_id=U2.id)`, inside `raises: PydanticValidationError` (the schema is built inside the wrap).

**Then**
1. raises: `exc.type is PydanticValidationError`.
2. nothing written: nothing written.

### PRDS-C-17 — a failing commit discards the row, its ledger row and the extra row
- **Rules:** `create_product` R1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no `products` rows.
2. X (after the commit point).

**When**
- `svc.create_product(db, prod_in=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=4, avg_cost=Decimal("12.50")), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `products` rows of W1: exactly 0.
4. count: `ledger_of(F1, I1)` has exactly 0 rows.
5. count: x_gone.
6. session: usable.

### PRDS-C-18 — a failing re-read after the commit leaves the row and its ledger row saved
- **Rules:** `create_product` R1; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no `products` rows.

**When**
- `svc.create_product(db, prod_in=ProductCreate(item_id=I1.id, factory_id=F1.id, qty=4, avg_cost=Decimal("12.50")), workspace_id=W1.id, user_id=U2.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: `products` rows of W1: exactly 1, with `qty == 4`.
3. committed: `ledger_of(F1, I1)` has exactly 1 row.

## `ProductService.update_product`

### PRDS-U-01 — a quantity change is committed with its adjustment row and returned re-read
- **Rules:** `update_product` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`.

**When**
- spies: `result = svc.update_product(db, prod_id=P.id, prod_in=ProductUpdate(qty=8), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: loaded(result).
2. returns: `result.id == P.id`, `result.qty == 8`, `result.updated_at is not None`.
3. mock called: `cm.call_count == 1`.
4. mock called: `rb.call_count == 0`.
5. committed: re-read P: `qty == 8`, `updated_by == U2.id`, `avg_cost == Decimal("10.00")`.
6. committed: `ledger_of(F1, I1)` has exactly 1 row.
7. committed: that row has `transaction_type == "inventory_adjustment"`, `quantity == 3`, `qty_before == 5`, `qty_after == 8`, `notes == "Quantity adjusted from 5 to 8"`.

### PRDS-U-02 — a price change is committed with no ledger row; omitted fields are kept
- **Rules:** `update_product` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = stock, but `note "Keep"`.

**When**
- `result = svc.update_product(db, prod_id=P.id, prod_in=ProductUpdate(selling_price=Decimal("20.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. committed: re-read P: `selling_price == Decimal("20.00")`, `updated_by == U2.id`.
3. committed: re-read P: `note == "Keep"`, `qty == 5`.
4. committed: `product_ledger` has exactly 0 rows.

### PRDS-U-03 — a row of another workspace: the 404 passes unchanged and the session is rolled back
- **Rules:** `update_product` R2, Errors row 1; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = stock, but `workspace_id W2.id`, `item_id I9.id`, `factory_id F9.id`.
2. X (after the commit point).

**When**
- spies: `svc.update_product(db, prod_id=Z.id, prod_in=ProductUpdate(qty=8), workspace_id=W1.id, user_id=U2.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Product record with ID {Z.id} not found"`.
3. mock called: `rb.call_count >= 1`.
4. mock called: `cm.call_count == 0`.
5. count: x_gone.
6. unchanged: unchanged(Z).
7. nothing written: nothing written.

### PRDS-U-04 — a soft-deleted row: the 400 passes unchanged and the session is rolled back
- **Rules:** `update_product` R2, Errors row 2; TC3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. P = stock, but deleted.
2. X (after the commit point).

**When**
- `svc.update_product(db, prod_id=P.id, prod_in=ProductUpdate(qty=8), workspace_id=W1.id, user_id=U2.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Cannot update a deleted product record"`.
3. count: x_gone.
4. unchanged: unchanged(P).
5. nothing written: nothing written.
6. session: usable.

### PRDS-U-05 — pass-through BUG-2793: flipping a row that holds stock is refused and rolled back
- **Rules:** `update_product` R2 [BUG-2793]; TC3
- **Kind:** bug
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (no error is raised: the whole row is flipped)

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`.
2. X (after the commit point).

**When**
- `svc.update_product(db, prod_id=P.id, prod_in=ProductUpdate(is_available_for_sale=True), workspace_id=W1.id, user_id=U2.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Product record holds stock — use Make sellable to move units"`.
3. count: x_gone.
4. unchanged: unchanged(P).
5. nothing written: nothing written.

### PRDS-U-06 — a row at 0 flips to for sale and is committed
- **Rules:** `update_product` R1 (BUG-2793 companion)
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = stock, but `qty 0`, `avg_cost Decimal("10.00")`.

**When**
- `result = svc.update_product(db, prod_id=P.id, prod_in=ProductUpdate(is_available_for_sale=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. committed: re-read P: `is_available_for_sale is True`, `qty == 0`, `avg_cost == Decimal("10.00")`.
3. committed: `product_ledger` has exactly 0 rows.

### PRDS-U-07 — a flip at 0 onto a taken key: whatever is raised, nothing is saved and the session is rolled back
- **Rules:** `update_product` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. PS = stock, but for sale, `qty 30`.
2. P = stock, but `qty 0`.
3. X (after the commit point).

**When**
- `svc.update_product(db, prod_id=P.id, prod_in=ProductUpdate(is_available_for_sale=True), workspace_id=W1.id, user_id=U2.id)`, inside `raises: IntegrityError or HTTPException`.

**Then**
1. raises: `isinstance(exc.value, (IntegrityError, HTTPException))`.
2. count: x_gone.
3. unchanged: unchanged(P).
4. unchanged: unchanged(PS).
5. nothing written: nothing written.
6. session: usable.

### PRDS-U-08 — pass-through BUG-2781: a flip at 0 onto a taken key gets the 409
- **Rules:** `update_product` R2 [BUG-2781]
- **Kind:** bug
- **Expect:** xfail BUG-2781
- **Fails today on:** Then 1 (the call raises IntegrityError 23505 at flush)

**Given**
1. PS = stock, but for sale, `qty 30`.
2. P = stock, but `qty 0`.

**When**
- `svc.update_product(db, prod_id=P.id, prod_in=ProductUpdate(is_available_for_sale=True), workspace_id=W1.id, user_id=U2.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 409`.
2. raises: `exc.value.detail == "Product record already exists for this item/factory/availability combination"`.
3. unchanged: unchanged(P).

### PRDS-U-09 — pass-through BUG-2771: an empty update does not stamp updated_by
- **Rules:** `update_product` R1 [BUG-2771]; HR-9
- **Kind:** bug
- **Expect:** xfail BUG-2771
- **Fails today on:** Then 2 (`updated_by == U2.id`)

**Given**
1. P = stock.

**When**
- `result = svc.update_product(db, prod_id=P.id, prod_in=ProductUpdate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. committed: re-read P: `updated_by is None`.

### PRDS-U-10 — an empty update still commits and writes no ledger row
- **Rules:** `update_product` R1 (BUG-2771 companion)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = stock.

**When**
- spies: `result = svc.update_product(db, prod_id=P.id, prod_in=ProductUpdate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`, `result.qty == 5`.
2. mock called: `cm.call_count == 1`.
3. committed: re-read P: `qty == 5`, `is_available_for_sale is False`.
4. committed: `product_ledger` has exactly 0 rows.

### PRDS-U-11 — pass-through BUG-2777: an explicit null clears the selling price
- **Rules:** `update_product` R1 [BUG-2777]
- **Kind:** bug
- **Expect:** xfail BUG-2777
- **Fails today on:** Then 2 (the null is dropped: `selling_price` stays 20.00)

**Given**
1. P = stock, but `selling_price Decimal("20.00")`.

**When**
- `result = svc.update_product(db, prod_id=P.id, prod_in=ProductUpdate(selling_price=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. committed: re-read P: `selling_price is None`.

### PRDS-U-12 — pass-through BUG-2778: a cost-only change writes a zero-quantity adjustment row
- **Rules:** `update_product` R1 [BUG-2778]
- **Kind:** bug
- **Expect:** xfail BUG-2778
- **Fails today on:** Then 2 (no ledger row is written)

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`.

**When**
- `result = svc.update_product(db, prod_id=P.id, prod_in=ProductUpdate(avg_cost=Decimal("12.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. committed: `ledger_of(F1, I1)` has exactly 1 row.
3. committed: that row has `transaction_type == "inventory_adjustment"`, `quantity == 0`, `qty_before == 5`, `qty_after == 5`, `avg_cost_before == Decimal("10.00")`, `avg_cost_after == Decimal("12.00")`.

### PRDS-U-13 — a cost-only change is committed on the row
- **Rules:** `update_product` R1 (BUG-2778 companion)
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`.

**When**
- `result = svc.update_product(db, prod_id=P.id, prod_in=ProductUpdate(avg_cost=Decimal("12.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. committed: re-read P: `avg_cost == Decimal("12.00")`, `qty == 5`, `updated_by == U2.id`.

### PRDS-U-14 — pass-through BUG-2779: an adjustment at cost 0 totals 0.00
- **Rules:** `update_product` R1 [BUG-2779]
- **Kind:** bug
- **Expect:** xfail BUG-2779
- **Fails today on:** Then 3 (`total_cost` is NULL)

**Given**
1. P = stock, but `avg_cost Decimal("0.00")`.

**When**
- `result = svc.update_product(db, prod_id=P.id, prod_in=ProductUpdate(qty=8), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.qty == 8`.
2. committed: `ledger_of(F1, I1)` has exactly 1 row.
3. committed: that row has `total_cost == Decimal("0.00")`.

### PRDS-U-15 — an adjustment at cost 0 is committed with the zero unit cost
- **Rules:** `update_product` R1 (BUG-2779 companion)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = stock, but `avg_cost Decimal("0.00")`.

**When**
- `result = svc.update_product(db, prod_id=P.id, prod_in=ProductUpdate(qty=8), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.qty == 8`.
2. committed: `ledger_of(F1, I1)` has exactly 1 row.
3. committed: that row has `quantity == 3`, `unit_cost == Decimal("0.00")`.

### PRDS-U-16 — pass-through BUG-2775: a negative quantity is refused by the schema, nothing saved
- **Rules:** `update_product` R2 [BUG-2775]
- **Kind:** bug
- **Expect:** xfail BUG-2775
- **Fails today on:** Then 1 (no error is raised: `qty -1` is stored with an adjustment row)

**Given**
1. P = stock.

**When**
- `svc.update_product(db, prod_id=P.id, prod_in=ProductUpdate(qty=-1), workspace_id=W1.id, user_id=U2.id)`, inside `raises: PydanticValidationError` (the schema is built inside the wrap).

**Then**
1. raises: `exc.type is PydanticValidationError`.
2. unchanged: unchanged(P).
3. nothing written: nothing written.

### PRDS-U-17 — a failing commit discards the change, its adjustment row and the extra row
- **Rules:** `update_product` R1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. P = stock, but `avg_cost Decimal("10.00")`.
2. X (after the commit point).

**When**
- `svc.update_product(db, prod_id=P.id, prod_in=ProductUpdate(qty=8), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read P: `qty == 5`, `updated_by is None`.
4. count: `product_ledger` has exactly 0 rows.
5. count: x_gone.
6. session: usable.

## `ProductService.get_product`

### PRDS-G-01 — the workspace's live row is returned
- **Rules:** `get_product` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z0 = stock, but `workspace_id W0.id`, `item_id I0.id`, `factory_id F0.id`.
2. P = stock.
3. Z2 = stock, but `workspace_id W2.id`, `item_id I9.id`, `factory_id F9.id`.

**When**
- `result = svc.get_product(db, prod_id=P.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Product)`.
2. returns: `result.id == P.id`, `result.workspace_id == W1.id`, `result.qty == 5`.

### PRDS-G-02 — a row of W0 (lower id) gets the 404
- **Rules:** `get_product` R1, Errors
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z0 = stock, but `workspace_id W0.id`, `item_id I0.id`, `factory_id F0.id`.
2. P = stock.

**When**
- `svc.get_product(db, prod_id=Z0.id, workspace_id=W1.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Product record with ID {Z0.id} not found"`.

### PRDS-G-03 — a row of W2 (higher id) gets the 404
- **Rules:** `get_product` R1, Errors
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P = stock.
2. Z2 = stock, but `workspace_id W2.id`, `item_id I9.id`, `factory_id F9.id`.

**When**
- `svc.get_product(db, prod_id=Z2.id, workspace_id=W1.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Product record with ID {Z2.id} not found"`.

### PRDS-G-04 — pass-through BUG-2772: a soft-deleted row is not found by default
- **Rules:** `get_product` R2 [BUG-2772]
- **Kind:** bug
- **Expect:** xfail BUG-2772
- **Fails today on:** Then 1 (no error is raised: the deleted row is returned)

**Given**
1. P = stock, but deleted.

**When**
- `svc.get_product(db, prod_id=P.id, workspace_id=W1.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Product record with ID {P.id} not found"`.

### PRDS-G-05 — BUG-2772: include_deleted=True returns a soft-deleted row
- **Rules:** `get_product` Inputs, R2 [BUG-2772]
- **Kind:** bug
- **Expect:** xfail BUG-2772
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. P = stock, but deleted.

**When**
- `result = svc.get_product(db, prod_id=P.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == P.id`.
2. returns: `result.is_deleted is True`.

### PRDS-G-06 — BUG-2772: include_deleted=True does not reach another workspace
- **Rules:** `get_product` R1, R2 [BUG-2772]
- **Kind:** bug
- **Expect:** xfail BUG-2772
- **Fails today on:** Then 1 (the call raises TypeError, not HTTPException: the parameter does not exist)

**Given**
1. Z2 = stock, but `workspace_id W2.id`, `item_id I9.id`, `factory_id F9.id`, deleted.

**When**
- `svc.get_product(db, prod_id=Z2.id, workspace_id=W1.id, include_deleted=True)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Product record with ID {Z2.id} not found"`.

### PRDS-G-07 — pass-through BUG-2773: a row of a soft-deleted factory is not found by default
- **Rules:** `get_product` R2 [BUG-2773]
- **Kind:** bug
- **Expect:** xfail BUG-2773
- **Fails today on:** Then 1 (no error is raised: the row is returned)

**Given**
1. P = stock, but `factory_id FD.id`.

**When**
- `svc.get_product(db, prod_id=P.id, workspace_id=W1.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Product record with ID {P.id} not found"`.

### PRDS-G-08 — pass-through BUG-2773: a row of a removed item is not found by default
- **Rules:** `get_product` R2 [BUG-2773]
- **Kind:** bug
- **Expect:** xfail BUG-2773
- **Fails today on:** Then 1 (no error is raised: the row is returned)

**Given**
1. P = stock, but `item_id IX.id`.

**When**
- `svc.get_product(db, prod_id=P.id, workspace_id=W1.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Product record with ID {P.id} not found"`.

### PRDS-G-09 — a row of an inactive but live factory is returned
- **Rules:** `get_product` R1 (BUG-2773 companion)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = stock, but `factory_id FI.id`.

**When**
- `result = svc.get_product(db, prod_id=P.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == P.id`, `result.factory_id == FI.id`.

### PRDS-G-10 — the read neither commits nor rolls back, and takes no lock
- **Rules:** `get_product` R1; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = stock.
2. B = stock, but `item_id I2.id`, `note "Old"`.
3. X (after the commit point).
4. N = stock, but `item_id I2.id`, `factory_id F2.id`: `db.add(N)` only, not flushed (after the commit point).
5. `B.note = "Edited"` (after the commit point, not flushed).
6. The statement recorder.

**When**
- spies: `result = svc.get_product(db, prod_id=P.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `N in db.new`, `len(db.new) == 1`.
5. session: `B in db.dirty`, `len(db.dirty) == 1`.
6. statement: no lock.
7. committed: x_gone.
8. committed: re-read B: `note == "Old"`.

### PRDS-G-11 — a read that raises the 404 does not roll back
- **Rules:** `get_product` R1, Errors; TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. P = stock.
2. X (after the commit point).

**When**
- spies: `svc.get_product(db, prod_id=MISSING, workspace_id=W1.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Product record with ID 999999999 not found"`.
3. mock called: `rb.call_count == 0`.
4. mock called: `cm.call_count == 0`.
5. session: `X in db`.

## `ProductService.list_products`

### PRDS-L-01 — the defaults return the workspace's live rows only (compared as a set)
- **Rules:** `list_products` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z0 = stock, but `workspace_id W0.id`, `item_id I0.id`, `factory_id F0.id`.
2. A = stock.
3. D = stock, but `item_id I2.id`, deleted.
4. B = stock, but for sale.
5. Z2 = stock, but `workspace_id W2.id`, `item_id I9.id`, `factory_id F9.id`.

**When**
- `result = svc.list_products(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `{r.id for r in result} == {A.id, B.id}`.

### PRDS-L-02 — the factory filter is passed on
- **Rules:** `list_products` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock.
2. B = stock, but `factory_id F2.id`.
3. C = stock, but `item_id I2.id`, `factory_id F2.id`.

**When**
- `result = svc.list_products(db, workspace_id=W1.id, factory_id=F2.id)`.

**Then**
1. returns: `{r.id for r in result} == {B.id, C.id}`.

### PRDS-L-03 — is_available_for_sale=False filters (not "no filter")
- **Rules:** `list_products` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock.
2. B = stock, but for sale.
3. C = stock, but `item_id I2.id`.

**When**
- `result = svc.list_products(db, workspace_id=W1.id, is_available_for_sale=False)`.

**Then**
1. returns: `{r.id for r in result} == {A.id, C.id}`.

### PRDS-L-04 — is_available_for_sale=True returns only for-sale rows
- **Rules:** `list_products` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock.
2. B = stock, but for sale.
3. C = stock, but `item_id I2.id`.

**When**
- `result = svc.list_products(db, workspace_id=W1.id, is_available_for_sale=True)`.

**Then**
1. returns: `{r.id for r in result} == {B.id}`.

### PRDS-L-05 — with the defaults 101 live rows give 100 distinct ones
- **Rules:** `list_products` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 items, by `add_all` and one flush: k = 1 … 101, `Item(workspace_id=W1.id, name=f"Part {k:03d}", name_normalized=f"part {k:03d}", unit="pcs")`.
2. 101 rows, by `add_all` and one flush: for each of those items, stock, but `item_id` = that item's id.
3. `all_ids` = the set of the ids of those 101 rows.

**When**
- `result = svc.list_products(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `len({r.id for r in result}) == 100`, `{r.id for r in result} <= all_ids`.

### PRDS-L-06 — skip and limit are passed on: 5 rows, skip=1, limit=2 give 2 of them
- **Rules:** `list_products` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock.
2. B = stock, but for sale.
3. C = stock, but `item_id I2.id`.
4. D = stock, but `item_id I2.id`, for sale.
5. E = stock, but `factory_id F2.id`.

**When**
- `result = svc.list_products(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `len({r.id for r in result}) == 2`, `{r.id for r in result} <= {A.id, B.id, C.id, D.id, E.id}`.

### PRDS-L-07 — skip=4 with limit=1000 gives the one remaining row
- **Rules:** `list_products` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock.
2. B = stock, but for sale.
3. C = stock, but `item_id I2.id`.
4. D = stock, but `item_id I2.id`, for sale.
5. E = stock, but `factory_id F2.id`.

**When**
- `result = svc.list_products(db, workspace_id=W1.id, skip=4, limit=1000)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in {A.id, B.id, C.id, D.id, E.id}`.

### PRDS-L-08 — the list neither commits nor rolls back, and takes no lock
- **Rules:** `list_products` R1; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock.
2. B = stock, but `workspace_id W2.id`, `item_id I9.id`, `factory_id F9.id`, `note "Old"`.
3. X (after the commit point).
4. N = stock, but `item_id I2.id`, `factory_id F2.id`: `db.add(N)` only, not flushed (after the commit point).
5. `B.note = "Edited"` (after the commit point, not flushed).
6. The statement recorder.

**When**
- spies: `result = svc.list_products(db, workspace_id=W1.id)`.

**Then**
1. returns: `{r.id for r in result} == {A.id}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `N in db.new`, `len(db.new) == 1`.
5. session: `B in db.dirty`, `len(db.dirty) == 1`.
6. statement: no lock.
7. committed: x_gone.
8. committed: re-read B: `note == "Old"`.

## `ProductService.delete_product`

### PRDS-D-01 — a row at 0 is soft-deleted, committed and returned re-read
- **Rules:** `delete_product` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = stock, but `qty 0`, `avg_cost Decimal("10.00")`.

**When**
- spies: `result = svc.delete_product(db, prod_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: loaded(result).
2. returns: `result.id == P.id`, `result.is_deleted is True`, `result.deleted_by == U2.id`, `result.deleted_at is not None`.
3. mock called: `cm.call_count == 1`.
4. mock called: `rb.call_count == 0`.
5. committed: re-read P: `is_deleted is True`, `is_active is False`, `deleted_by == U2.id`, `deleted_at is not None`.
6. committed: re-read P: `qty == 0`, `avg_cost == Decimal("10.00")`, `updated_by is None`.

### PRDS-D-02 — an already deleted row: the 400 passes unchanged and the session is rolled back
- **Rules:** `delete_product` R2; TC3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. P = stock, but `qty 0`, deleted.
2. X (after the commit point).

**When**
- spies: `svc.delete_product(db, prod_id=P.id, workspace_id=W1.id, user_id=U2.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Product record is already deleted"`.
3. mock called: `rb.call_count >= 1`.
4. mock called: `cm.call_count == 0`.
5. count: x_gone.
6. unchanged: unchanged(P).
7. session: usable.

### PRDS-D-03 — an unknown id: the 404 passes unchanged and the session is rolled back
- **Rules:** `delete_product` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. P = stock, but `qty 0`.
2. X (after the commit point).

**When**
- `svc.delete_product(db, prod_id=MISSING, workspace_id=W1.id, user_id=U2.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Product record with ID 999999999 not found"`.
3. count: x_gone.
4. unchanged: unchanged(P).

### PRDS-D-04 — pass-through BUG-2774: a row holding stock is refused with its blocker, rolled back
- **Rules:** `delete_product` R2 [BUG-2774]; TC3
- **Kind:** bug
- **Expect:** xfail BUG-2774
- **Fails today on:** Then 1 (no error is raised: the row is deleted with its stock)

**Given**
1. P = stock, but `qty 4`.
2. X (after the commit point).

**When**
- `svc.delete_product(db, prod_id=P.id, workspace_id=W1.id, user_id=U2.id)`, inside `raises: AppValidationError`.

**Then**
1. raises: `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Product record still holds stock"`.
3. raises: `exc.value.errors == [{"type": "product_stock", "id": P.id, "qty": 4}]`.
4. count: x_gone.
5. unchanged: unchanged(P).
6. nothing written: nothing written.

### PRDS-D-05 — the manager's ValidationError passes as the same object after a rollback
- **Rules:** `delete_product` R2 (BUG-2774 companion); TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. P = stock, but `qty 4`.
2. X (after the commit point).
3. `E = AppValidationError("Product record still holds stock", errors=[{"type": "product_stock", "id": 5, "qty": 4}])`.

**When**
- spies, inside `raises: AppValidationError`, inside `with patch.object(product_service.manager, "delete_product", side_effect=E):`: `svc.delete_product(db, prod_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `exc.value is E`.
2. raises: `exc.value.detail == "Product record still holds stock"`.
3. raises: `exc.value.errors == [{"type": "product_stock", "id": 5, "qty": 4}]`.
4. mock called: `rb.call_count >= 1`.
5. mock called: `cm.call_count == 0`.
6. count: x_gone.
7. unchanged: unchanged(P).

### PRDS-D-06 — a failing commit leaves the row live and discards the extra row
- **Rules:** `delete_product` R1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. P = stock, but `qty 0`.
2. X (after the commit point).

**When**
- `svc.delete_product(db, prod_id=P.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read P: `is_deleted is False`, `deleted_by is None`, `deleted_at is None`.
4. count: x_gone.
5. session: usable.

## `ProductService.list_ledger`

### PRDS-LG-01 — the defaults return the workspace's entries only (compared as a set)
- **Rules:** `list_ledger` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z0 = entry, but `workspace_id W0.id`, `factory_id F0.id`, `item_id I0.id`.
2. A = entry.
3. B = entry, but `item_id I2.id`, `performed_at T2`.
4. Z2 = entry, but `workspace_id W2.id`, `factory_id F9.id`, `item_id I9.id`.

**When**
- `result = svc.list_ledger(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `{r.id for r in result} == {A.id, B.id}`.

### PRDS-LG-02 — the factory filter is passed on
- **Rules:** `list_ledger` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = entry.
2. B = entry, but `factory_id F2.id`.
3. C = entry, but `factory_id F2.id`, `item_id I2.id`.

**When**
- `result = svc.list_ledger(db, workspace_id=W1.id, factory_id=F2.id)`.

**Then**
1. returns: `{r.id for r in result} == {B.id, C.id}`.

### PRDS-LG-03 — a factory of W2 (higher workspace id) shows nothing
- **Rules:** `list_ledger` R3; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = entry.
2. Z2 = entry, but `workspace_id W2.id`, `factory_id F9.id`, `item_id I9.id`.

**When**
- `result = svc.list_ledger(db, workspace_id=W1.id, factory_id=F9.id)`.

**Then**
1. returns: `result == []`.

### PRDS-LG-04 — a factory of W0 (lower workspace id) shows nothing
- **Rules:** `list_ledger` R3; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z0 = entry, but `workspace_id W0.id`, `factory_id F0.id`, `item_id I0.id`.
2. A = entry.

**When**
- `result = svc.list_ledger(db, workspace_id=W1.id, factory_id=F0.id)`.

**Then**
1. returns: `result == []`.

### PRDS-LG-05 — the item filter is passed on
- **Rules:** `list_ledger` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = entry.
2. B = entry, but `item_id I2.id`.
3. C = entry, but `factory_id F2.id`, `item_id I2.id`.

**When**
- `result = svc.list_ledger(db, workspace_id=W1.id, item_id=I2.id)`.

**Then**
1. returns: `{r.id for r in result} == {B.id, C.id}`.

### PRDS-LG-06 — an item of W2 shows nothing
- **Rules:** `list_ledger` R3; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = entry.
2. Z2 = entry, but `workspace_id W2.id`, `factory_id F9.id`, `item_id I9.id`.

**When**
- `result = svc.list_ledger(db, workspace_id=W1.id, item_id=I9.id)`.

**Then**
1. returns: `result == []`.

### PRDS-LG-07 — factory_id=0 filters and gives []
- **Rules:** `list_ledger` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry.

**When**
- `result = svc.list_ledger(db, workspace_id=W1.id, factory_id=0)`.

**Then**
1. returns: `result == []`.

### PRDS-LG-08 — item_id=0 filters and gives []
- **Rules:** `list_ledger` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry.

**When**
- `result = svc.list_ledger(db, workspace_id=W1.id, item_id=0)`.

**Then**
1. returns: `result == []`.

### PRDS-LG-09 — the transaction type is compared exactly
- **Rules:** `list_ledger` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = entry.
2. B = entry, but `transaction_type "sale"`.
3. C = entry, but `transaction_type "Sale"`.

**When**
- `result = svc.list_ledger(db, workspace_id=W1.id, transaction_type="sale")`.

**Then**
1. returns: `{r.id for r in result} == {B.id}`.

### PRDS-LG-10 — a blank transaction type applies no filter
- **Rules:** `list_ledger` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry.
2. B = entry, but `transaction_type "sale"`.

**When**
- `result = svc.list_ledger(db, workspace_id=W1.id, transaction_type="")`.

**Then**
1. returns: `{r.id for r in result} == {A.id, B.id}`.

### PRDS-LG-11 — naive date bounds are inclusive at both ends
- **Rules:** `list_ledger` R1 (BUG-992 companion)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry (`performed_at T1`).
2. B = entry, but `performed_at T2`.
3. C = entry, but `performed_at T3`.
4. D = entry, but `performed_at T4`.

**When**
- `result = svc.list_ledger(db, workspace_id=W1.id, start_date=T2, end_date=T3)`.

**Then**
1. returns: `{r.id for r in result} == {B.id, C.id}`.

### PRDS-LG-12 — pass-through BUG-992: aware bounds are compared in UTC
- **Rules:** `list_ledger` R1 [BUG-992]
- **Kind:** bug
- **Expect:** xfail BUG-992
- **Fails today on:** Then 1 (under `Asia/Dhaka` the aware range returns `[]`)

**Given**
1. A = entry, but `performed_at datetime(2026, 3, 1, 12, 0, 0)`.
2. B = entry, but `performed_at T5`.
3. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))` (after the commit point).

**When**
- `result = svc.list_ledger(db, workspace_id=W1.id, start_date=datetime(2026, 3, 1, 11, 30, tzinfo=timezone.utc), end_date=datetime(2026, 3, 1, 12, 30, tzinfo=timezone.utc))`.

**Then**
1. returns: `[r.id for r in result] == [A.id]`.

### PRDS-LG-13 — entries of a deleted factory, a removed item and a deleted product stay listed
- **Rules:** `list_ledger` R1 (D2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. P = stock, but `item_id I2.id`, `qty 0`, deleted.
2. A = entry, but `factory_id FD.id`.
3. B = entry, but `item_id IX.id`.
4. C = entry, but `item_id I2.id`, `transaction_type "inventory_adjustment"`.

**When**
- `result = svc.list_ledger(db, workspace_id=W1.id)`.

**Then**
1. returns: `{r.id for r in result} == {A.id, B.id, C.id}`.

### PRDS-LG-14 — of different times the newest comes first, whatever the id order
- **Rules:** `list_ledger` R2 (today's part)
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = entry, but `performed_at T2`.
2. C = entry, but `performed_at T3`.
3. A = entry (`performed_at T1`, the highest id).

**When**
- `result = svc.list_ledger(db, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [C.id, B.id, A.id]`.

### PRDS-LG-15 — pass-through BUG-640: tied times come back id descending
- **Rules:** `list_ledger` R2 [BUG-640]
- **Kind:** bug
- **Expect:** xfail BUG-640 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no tie-break: after the update the rows usually come back in storage order)

**Given**
1. A = entry.
2. B = entry.
3. C = entry.
4. `A.notes = "x"`, then `db.flush()`.
5. `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))` (after the commit point).
6. `db.expire_all()` (after the commit point).

**When**
- `result = svc.list_ledger(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `[r.id for r in result] == [C.id, B.id, A.id]`.

### PRDS-LG-16 — BUG-640: the ledger query breaks ties by id descending
- **Rules:** `list_ledger` R2 [BUG-640]
- **Kind:** bug
- **Expect:** xfail BUG-640
- **Fails today on:** Then 3 (the `ORDER BY` has `performed_at` only)

**Given**
1. A = entry.
2. B = entry, but `performed_at T2`.
3. The statement recorder.

**When**
- `result = svc.list_ledger(db, workspace_id=W1.id)`.

**Then**
1. returns: `{r.id for r in result} == {A.id, B.id}`.
2. statement: `"performed_at DESC" in order_part`.
3. statement: `"id DESC" in order_part.split("performed_at DESC", 1)[1]`.

### PRDS-LG-17 — with the defaults 101 entries give 100
- **Rules:** `list_ledger` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 entries, by `add_all` and one flush: k = 1 … 101, entry, but `performed_at T1 + timedelta(minutes=k)`.

**When**
- `result = svc.list_ledger(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### PRDS-LG-18 — skip and limit are passed on, after the order
- **Rules:** `list_ledger` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry (`performed_at T1`).
2. B = entry, but `performed_at T2`.
3. C = entry, but `performed_at T3`.
4. D = entry, but `performed_at T4`.
5. E = entry, but `performed_at T5`.

**When**
- `result = svc.list_ledger(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `[r.id for r in result] == [D.id, C.id]`.

### PRDS-LG-19 — skip=4 with limit=1000 gives the oldest entry
- **Rules:** `list_ledger` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry (`performed_at T1`).
2. B = entry, but `performed_at T2`.
3. C = entry, but `performed_at T3`.
4. D = entry, but `performed_at T4`.
5. E = entry, but `performed_at T5`.

**When**
- `result = svc.list_ledger(db, workspace_id=W1.id, skip=4, limit=1000)`.

**Then**
1. returns: `[r.id for r in result] == [A.id]`.

### PRDS-LG-20 — the ledger list neither commits nor rolls back, and takes no lock
- **Rules:** `list_ledger` R1; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = entry.
2. B = entry, but `notes "Old"`.
3. X (after the commit point).
4. N = entry, but `item_id I2.id`: `db.add(N)` only, not flushed (after the commit point).
5. `B.notes = "Edited"` (after the commit point, not flushed).
6. The statement recorder.

**When**
- spies: `result = svc.list_ledger(db, workspace_id=W1.id)`.

**Then**
1. returns: `{r.id for r in result} == {A.id, B.id}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `N in db.new`, `len(db.new) == 1`.
5. session: `B in db.dirty`, `len(db.dirty) == 1`.
6. statement: no lock.
7. committed: x_gone.
8. committed: re-read B: `notes == "Old"`.

### PRDS-LG-21 — a negative limit is rejected by the database, and the service does not roll back
- **Rules:** `list_ledger` Errors; TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. A = entry.
2. X (after the commit point).

**When**
- spies, inside `raises: DataError`, inside `with db.begin_nested():`: `svc.list_ledger(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201W"`.
2. mock called: `rb.call_count == 0`.
3. mock called: `cm.call_count == 0`.
4. session: `X in db`.

## `ProductService.make_sellable` (new method, BUG-2793)

### PRDS-MS-01 — a move is committed on both buckets with two ledger rows; the target is returned re-read
- **Rules:** `make_sellable` S1, Returns (D1); TC1, TC2
- **Kind:** bug
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")`.
2. T = stock, but for sale, `qty 4`, `avg_cost Decimal("8.00")`.

**When**
- spies: `result = svc.make_sellable(db, prod_id=S.id, quantity=3, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: loaded(result).
2. returns: `result.id == T.id`, `result.qty == 7`.
3. mock called: `cm.call_count == 1`.
4. mock called: `rb.call_count == 0`.
5. committed: re-read S: `qty == 7`, `avg_cost == Decimal("5.00")`.
6. committed: re-read T: `qty == 7`, `avg_cost == Decimal("6.71")`.
7. committed: `ledger_of(F1, I1)` has exactly 2 rows, both `transaction_type == "transfer"`, `source_type == "make_sellable"`, `quantity == 3`.

### PRDS-MS-02 — a missing target is created and committed with the source average
- **Rules:** `make_sellable` S1
- **Kind:** bug
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")`.

**When**
- `result = svc.make_sellable(db, prod_id=S.id, quantity=4, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id != S.id`, `result.is_available_for_sale is True`.
2. committed: the `products` row with `id == result.id` has `qty == 4`, `avg_cost == Decimal("5.00")`, `created_by == U2.id`.
3. committed: re-read S: `qty == 6`.
4. committed: `products` rows of W1: exactly 2.
5. committed: `ledger_of(F1, I1)` has exactly 2 rows.

### PRDS-MS-03 — an unknown id: the 404 passes unchanged and the session is rolled back
- **Rules:** `make_sellable` S2
- **Kind:** bug
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`.
2. X (after the commit point).

**When**
- spies: `svc.make_sellable(db, prod_id=MISSING, quantity=3, workspace_id=W1.id, user_id=U2.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Product record with ID 999999999 not found"`.
3. mock called: `rb.call_count >= 1`.
4. mock called: `cm.call_count == 0`.
5. count: x_gone.
6. nothing written: nothing written.

### PRDS-MS-04 — a source of W2: the 404 passes unchanged, nothing saved
- **Rules:** `make_sellable` S2
- **Kind:** bug
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. Z2 = stock, but `workspace_id W2.id`, `item_id I9.id`, `factory_id F9.id`, `qty 10`.
2. X (after the commit point).

**When**
- `svc.make_sellable(db, prod_id=Z2.id, quantity=3, workspace_id=W1.id, user_id=U2.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Product record with ID {Z2.id} not found"`.
3. count: x_gone.
4. unchanged: unchanged(Z2).
5. nothing written: nothing written.

### PRDS-MS-05 — a soft-deleted source: the 400 passes unchanged and the session is rolled back
- **Rules:** `make_sellable` S2
- **Kind:** bug
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, deleted.
2. X (after the commit point).

**When**
- `svc.make_sellable(db, prod_id=S.id, quantity=3, workspace_id=W1.id, user_id=U2.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Cannot update a deleted product record"`.
3. count: x_gone.
4. unchanged: unchanged(S).
5. nothing written: nothing written.

### PRDS-MS-06 — a for-sale source: the 400 passes unchanged and the session is rolled back
- **Rules:** `make_sellable` S2
- **Kind:** bug
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. T = stock, but for sale, `qty 10`.
2. X (after the commit point).

**When**
- `svc.make_sellable(db, prod_id=T.id, quantity=3, workspace_id=W1.id, user_id=U2.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Only a not-for-sale product record can be made sellable"`.
3. count: x_gone.
4. unchanged: unchanged(T).
5. nothing written: nothing written.

### PRDS-MS-07 — quantity 0: the 400 passes unchanged and the session is rolled back
- **Rules:** `make_sellable` S2
- **Kind:** bug
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`.
2. X (after the commit point).

**When**
- `svc.make_sellable(db, prod_id=S.id, quantity=0, workspace_id=W1.id, user_id=U2.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Quantity must be a positive whole number"`.
3. count: x_gone.
4. unchanged: unchanged(S).
5. nothing written: nothing written.

### PRDS-MS-08 — one more than held: the 422 passes unchanged, both buckets kept
- **Rules:** `make_sellable` S2, S3
- **Kind:** bug
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")`.
2. T = stock, but for sale, `qty 4`, `avg_cost Decimal("8.00")`.
3. X (after the commit point).

**When**
- `svc.make_sellable(db, prod_id=S.id, quantity=11, workspace_id=W1.id, user_id=U2.id)`, inside `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 422`.
2. raises: `exc.value.detail == "Insufficient stock to make sellable: requested 11, available 10"`.
3. count: x_gone.
4. unchanged: unchanged(S).
5. unchanged: unchanged(T).
6. nothing written: nothing written.

### PRDS-MS-09 — a failing commit saves nothing: source kept, no ledger row, sum unchanged
- **Rules:** `make_sellable` S1, S3; TC4
- **Kind:** bug
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError, not RuntimeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")`.
2. T = stock, but for sale, `qty 4`, `avg_cost Decimal("8.00")`.
3. X (after the commit point).

**When**
- `svc.make_sellable(db, prod_id=S.id, quantity=3, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read S: `qty == 10`.
4. re-read T: `qty == 4`, `avg_cost == Decimal("8.00")`.
5. re-read S, T: `S.qty + T.qty == 14`.
6. count: `product_ledger` has exactly 0 rows.
7. count: x_gone.

### PRDS-MS-10 — the buckets are locked by the move and committed once in the same call
- **Rules:** `make_sellable` S1, S4 (clause only)
- **Kind:** bug
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")`.
2. T = stock, but for sale, `qty 4`, `avg_cost Decimal("8.00")`.
3. The statement recorder.

**When**
- spies: `result = svc.make_sellable(db, prod_id=S.id, quantity=3, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. statement: `sum("FOR UPDATE OF products" in s for s in psel) >= 2` (the source and the target bucket reads, S4).
3. statement: `all(s.count("FOR UPDATE") == s.count("FOR UPDATE OF products") for s in selects)` (no bare `FOR UPDATE`, no lock on any other table).
4. statement: `not any("SKIP LOCKED" in s for s in selects)`.
5. statement: `not any("NOWAIT" in s for s in selects)`.
6. mock called: `cm.call_count == 1`.

### PRDS-MS-11 — a failing re-read after the commit leaves the move saved
- **Rules:** `make_sellable` S1; TC5
- **Kind:** bug
- **Expect:** xfail BUG-2793
- **Fails today on:** Then 1 (the call raises AttributeError, not RuntimeError: `make_sellable` does not exist)

**Given**
1. S = stock, but `qty 10`, `avg_cost Decimal("5.00")`.
2. T = stock, but for sale, `qty 4`, `avg_cost Decimal("8.00")`.

**When**
- `svc.make_sellable(db, prod_id=S.id, quantity=3, workspace_id=W1.id, user_id=U2.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: re-read S: `qty == 7`.
3. committed: re-read T: `qty == 7`.
4. committed: `ledger_of(F1, I1)` has exactly 2 rows.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Manager rules (`create_product` R0–R7a, `update_product` R1–R10a, `delete_product` R4, `make_sellable` M1–M9) beyond one pass-through per bug | `tests/unit/managers/product_manager.cases.md` | Not re-tested here. |
| BUG-2770 — `update_product` row lock | `product_manager.cases.md` PRDM-U-39 | The spec lists it as not reached; the clause is the manager's. |
| `make_sellable` S4 / M7 — two concurrent moves, lock order lower id first | integration (two transactions) | Real concurrency; MS-10 checks only the clause. |
| BUG-2781 — `create_product` race (R4a) | integration | Two transactions. |
| BUG-1325, BUG-1327 — list order, deleted parents | `tests/unit/dao/product.cases.md` | The DAO's query. |
| BUG-1337 — ledger `performed_at` clock | `tests/unit/dao/product_ledger.cases.md` | The model default. |
| BUG-2772 — `include_deleted` query parameter | `GET /products/{id}/` (integration) | Accepted and passed to the service. |
| BUG-2793 — the new route | `POST /products/{id}/make-sellable/` (integration) | Route exists and calls the service. |
| BUG-2774 — 400 body of `ValidationError` | `tests/unit/core/exceptions.spec.md`, `DELETE /products/{id}/` | Body shape. |
| BUG-991 — date-only `end_date` | `GET /products/ledger/` (integration) | End of day. |
| HR-7 bounds; `IntegrityError` → 409; `DataError` → 500 | `/products/` endpoints, `app/main.py` handlers | Integration-only. |

## Spec gaps
All closed in Revision 2 (spec Gap log, 2026-11-21).

| # | Where | Resolution |
|---|---|---|
| 1 | TC4 (every write) | Closed (G1, code fact): a failing commit rolls back twice today, a manager refusal once; the contract stays "at least one" (spec Notes). The cards keep `rb.call_count >= 1`; no card changed. |
| 2 | `make_sellable` S4 | Closed (G2): S4 states `FOR UPDATE OF products` on each bucket read, no `SKIP LOCKED` / `NOWAIT`, one commit per call. PRDS-MS-10 Then 2–6 now pin exactly that. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_product` | R1 | PRDS-C-01, C-02, C-10, C-12, C-14, C-17, C-18 |
| `create_product` | R1 [BUG-2779] | PRDS-C-11 |
| `create_product` | R1 [BUG-2778] | PRDS-C-13 |
| `create_product` | R2 | PRDS-C-03, C-04, C-05, C-07 |
| `create_product` | R2 [BUG-1011] | PRDS-C-06 |
| `create_product` | R2 [BUG-1336] | PRDS-C-08 |
| `create_product` | R2 [BUG-2780] | PRDS-C-09 |
| `create_product` | R2 [BUG-2775] | PRDS-C-15 |
| `create_product` | R2 [BUG-2776] | PRDS-C-16 |
| `create_product` | Returns | PRDS-C-01 |
| `update_product` | R1 | PRDS-U-01, U-02, U-06, U-10, U-13, U-15, U-17 |
| `update_product` | R1 [BUG-2771] | PRDS-U-09 |
| `update_product` | R1 [BUG-2777] | PRDS-U-11 |
| `update_product` | R1 [BUG-2778] | PRDS-U-12 |
| `update_product` | R1 [BUG-2779] | PRDS-U-14 |
| `update_product` | R2 | PRDS-U-03, U-04, U-07 |
| `update_product` | R2 [BUG-2793] | PRDS-U-05 |
| `update_product` | R2 [BUG-2781] | PRDS-U-08 |
| `update_product` | R2 [BUG-2775] | PRDS-U-16 |
| `update_product` | Returns | PRDS-U-01 |
| `get_product` | R1 | PRDS-G-01, G-02, G-03, G-09, G-10, G-11 |
| `get_product` | R2 [BUG-2772] | PRDS-G-04, G-05, G-06 |
| `get_product` | R2 [BUG-2773] | PRDS-G-07, G-08 |
| `get_product` | Errors | PRDS-G-02, G-03, G-11 |
| `list_products` | R1 | PRDS-L-01 … L-08 |
| `delete_product` | R1 | PRDS-D-01, D-06 |
| `delete_product` | R2 | PRDS-D-02, D-03, D-05 |
| `delete_product` | R2 [BUG-2774] | PRDS-D-04 |
| `delete_product` | Returns | PRDS-D-01 |
| `list_ledger` | R1 | PRDS-LG-01, LG-02, LG-05, LG-07 … LG-11, LG-13, LG-17, LG-18, LG-19, LG-20 |
| `list_ledger` | R1 [BUG-992] | PRDS-LG-12 |
| `list_ledger` | R2 | PRDS-LG-14, LG-18, LG-19 |
| `list_ledger` | R2 [BUG-640] | PRDS-LG-15, LG-16 |
| `list_ledger` | R3 | PRDS-LG-03, LG-04, LG-06 |
| `list_ledger` | Errors | PRDS-LG-21 |
| `make_sellable` | S1 [BUG-2793] | PRDS-MS-01, MS-02, MS-09, MS-10, MS-11 |
| `make_sellable` | S2 [BUG-2793] | PRDS-MS-03 … MS-08 |
| `make_sellable` | S3 [BUG-2793] | PRDS-MS-08, MS-09 |
| `make_sellable` | S4 [BUG-2793] | PRDS-MS-10 (clause); race deferred |
| `make_sellable` | Returns (D1) | PRDS-MS-01, MS-02 |
| Transaction contract | TC1 | PRDS-C-01, U-01, D-01, MS-01 |
| Transaction contract | TC2 | PRDS-C-01, U-01, D-01, MS-01 |
| Transaction contract | TC3 | PRDS-C-03, C-04, C-05, C-07, U-03, U-04, U-05, U-07, D-02, D-03, D-04, D-05, MS-03 … MS-08 |
| Transaction contract | TC4 | PRDS-C-17, U-17, D-06, MS-09 |
| Transaction contract | TC5 | PRDS-C-18, MS-11 |
| Transaction contract | TC6 | PRDS-G-10, G-11, L-08, LG-20, LG-21 |
