# Test cases — `app/services/inventory_service.py`

> **Spec:** `tests/unit/services/inventory_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-22) — spec fill-gaps G1–G3: soft-deleted factory FD now carries `deleted_at T0`, `deleted_by U2.id` (C-06, IS-05); lock cards U-12, D-09 pin `FOR UPDATE OF inventory` (new spec rules `update_inventory` R1a, `delete_inventory` R1a), no `NOWAIT` / `SKIP LOCKED`; BUG-706 non-strict confirmed by the spec header. No case added or removed.
> **Revision:** 3 (2026-11-22) — G-05 … G-07 carry a note: remove the xfail only after BUG-700 is fixed too (a BUG-3082 fix that ignores `include_deleted` still passes them; only G-04 catches it). No case added or removed.
> **Counts:** 87 cases · 63 expected-to-pass · 24 expected-to-fail (bugs) · 10 deferred

## Reviewer summary
- **Per callable:** `create_inventory` 16 (4 bug) · `update_inventory` 16 (6 bug) · `get_inventory` 10 (4 bug) · `get_inventory_page` 14 (2 bug) · `get_inventory_stats` 10 (2 bug) · `get_incoming_summary` 10 (3 bug) · `delete_inventory` 11 (3 bug).
- **Depth:** full (skill step 1a): the service writes stock quantities and ledger rows. Every write gets a commit card (TC1 + TC2, with its ledger row), one rollback card per refusal type with an **uncommitted extra workspace X** that must be gone afterwards (TC3), a database-error card, a failing-commit card (TC4) and a failing-refresh card (TC5). Every read gets a TC6 card with commit / rollback spies (neither is called; a pending row and a dirty edit survive), and `get_inventory` / `get_incoming_summary` also a TC6 card on their 404 path.
- **Pass-through arguments:** `get_inventory_page` and `get_inventory_stats` get one card per argument, set up so only that argument excludes a row: a service that dropped or swapped it would return the extra row.
- **Bug rules of this spec:** BUG-3082 (G-05 … G-07, the parameter does not exist: `TypeError`), BUG-700 (G-04), BUG-710 (C-05), BUG-713 (U-05). Manager bugs reached through the service get one pass-through card each, strict unless the order is unasked for: BUG-701, 702 (×2), 703, 704, 705, 707 (×3), 712, 713, 714, 715, 716, 717, 718. Non-strict, `Author: claude`: BUG-706 (IS-09), BUG-719 (S-09). Passing companions that hold today and after the fix: other-workspace 404 (G-02, G-08), inactive live factory accepted (C-07) and summarised (IS-06), live duplicate 409 (C-04), qty-0 clear a no-op (D-02), non-voided PO counted (IS-01), price-only edit committed (U-15), plain search (P-05, S-05), case-insensitive name order (P-10), zero price stored (C-13).
- **Locks (BUG-704, BUG-705):** `FOR UPDATE OF inventory`, no `NOWAIT` / `SKIP LOCKED` (spec R1a), checked through the recorded SQL only (U-12, D-09); real two-connection races are deferred to integration tests.
- **Race simulation:** C-09 only (create R3, `IntegrityError` from a concurrent duplicate), patching the inventory DAO's duplicate lookups as the manager spec's Notes say.
- **Needs a decision:** None (gaps 1 – 3 closed in Revision 2).

## Conventions for this module

**IDs.** `INVS` = `app/services/inventory_service.py`. `C` create_inventory · `U` update_inventory · `G` get_inventory · `P` get_inventory_page · `S` get_inventory_stats · `IS` get_incoming_summary · `D` delete_inventory.

**Imports.** `svc` = `inventory_service` (`from app.services.inventory_service import InventoryService, inventory_service`). `Inventory` (`app.models.inventory`), `InventoryLedger` (`app.models.inventory_ledger`), `Factory` (`app.models.factory`), `Item` (`app.models.item`), `Status` (`app.models.status`), `OrderWorkflow` (`app.models.order_workflow`), `PurchaseOrder` (`app.models.purchase_order`), `PurchaseOrderItem` (`app.models.purchase_order_item`), `Workspace` (`app.models.workspace`), `InventoryTypeEnum` (`app.models.enums`; STORAGE, DAMAGED, WASTE, SCRAP below are its members), `InventoryCreate`, `InventoryUpdate` (`app.schemas.inventory`), `inventory_dao` (`app.dao.inventory`), `HTTPException` (`fastapi`), `IntegrityError`, `DataError` (`sqlalchemy.exc`), `inspect`, `select`, `func` (`sqlalchemy`), `patch` (`unittest.mock`), `Decimal`, `os`, `re`.

**Fixed values.** MISSING = `999999999`. T0 = `datetime(2020, 1, 2, 3, 4, 5)`. SFX = `str(os.getpid())`. `db` = the test's real session, first argument; every other argument by keyword. `result` = what the When returns.

**Standing rows** (every test, in this order, no Given line): W1, W2 = `make_workspace(db)` twice; U1, U2 = `make_profile(db)` twice; F1 = factory; I1 = item. U1 acts; U2 created the Given rows.

**Builders.** Inserted directly (never through `svc`), flushed one at a time in the order written. After "but" a line lists every column that differs.
- **factory** = `Factory(workspace_id=W1.id, name="Main Plant", abbreviation="MAI", is_active=True, is_deleted=False)`.
- **item** = `Item(workspace_id=W1.id, name="Bolt", name_normalized="bolt", unit="pkgs", is_active=True)`. When a card sets `name`, `name_normalized` is that name `.lower()`.
- Built only when a Given line names them: F2 = factory, but `name "Second Plant"`, `abbreviation "SEC"` · FX = factory, but `workspace_id W2.id`, `name "Foreign Plant"`, `abbreviation "FOR"` · I2 = item, but `name "Hex Nut"`, `unit "pcs"` · I3 = item, but `name "Washer"`, `unit "pcs"` · IX = item, but `workspace_id W2.id`, `name "Secret Part"`, `unit "pcs"`.
- **inv** = `Inventory(workspace_id=W1.id, item_id=I1.id, inventory_type=STORAGE, factory_id=F1.id, qty=10, avg_price=Decimal("5.00"), note="n1", is_active=True, is_deleted=False, created_by=U2.id, updated_by=None)`.
- **gone** (after "but", inventory only) = `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U2.id`.
- **Incoming rows:** S_OPEN = `Status(workspace_id=W1.id, name="Ordered", comment="Ordered")`; S_DONE = the same with `"Received"`; WF = `OrderWorkflow(workspace_id=W1.id, name="Flow", type="PFM", status_sequence=[S_OPEN.id, S_DONE.id])`. **po k on F** = `PurchaseOrder(workspace_id=W1.id, po_number=f"PO-INVS-{SFX}-k", destination_type="storage", destination_id=F.id, current_status_id=S_OPEN.id, order_workflow_id=WF.id, voided=False, created_by=U1.id)`. **line of P** = `PurchaseOrderItem(workspace_id=W1.id, purchase_order_id=P.id, line_number=1, item_id=I1.id, quantity_ordered=Decimal("10"), quantity_received=Decimal("3"))`.
- **commit point** = after the last Given line the test runs `db.commit()` (a savepoint release under the `db` fixture). Snapshots for `unchanged` are taken there. A line marked "(after the commit point)" runs after it, uncommitted.
- **X** (only where a card lists it, after the commit point) = `X = make_workspace(db)`, flushed, not committed; `X_ID = X.id`.

**Named checks.**
- **re-read R** = `db.expire_all()`, then `db.get(Inventory, R.id)`; database values.
- **unchanged(R)** = after re-read, `qty`, `avg_price`, `note`, `is_active`, `is_deleted`, `updated_by` of R equal their values at the commit point.
- **ledger(R)** = fresh `select(InventoryLedger)` with `workspace_id`, `factory_id`, `item_id`, `inventory_type` equal to R's, `order_by(InventoryLedger.id)`, as a list. **ledger_all** = fresh count of all `inventory_ledger` rows of W1. **inv_count** = fresh count of all `inventory` rows of W1 (any state).
- **x_gone** = `db.execute(select(Workspace.id).where(Workspace.id == X_ID)).first() is None`. **x_there** = the same `is not None`.
- **loaded(r)** = `inspect(r).expired_attributes.isdisjoint({c.key for c in inspect(Inventory).column_attrs})`; runs first, before any attribute of `result` is read.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads or counts with a fresh query.
- `session:` lines check `db` directly after the call, before any re-read. "usable" = `db.execute(select(1)).scalar() == 1`.
- `raises: <Type>` = plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint (the service rolls back itself); later lines assert on `exc.value`.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When (inside the `raises:` wrap when there is one).
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = the same with only `patch.object(db, "refresh", side_effect=RuntimeError("boom"))`. Checks after the block run with the patches gone.
- **recorder** = a `before_cursor_execute` listener on `db`'s connection records every statement sent during the When. `inv_selects` = the recorded statements that start with `SELECT` and match `re.search(r"FROM inventory(\s|$)", s)` (not `inventory_ledger`).

**xfail cards.** `pytest.mark.xfail(strict=True, reason="BUG-n")`, or `strict=False` when Expect says `(non-strict)`. Write the call and checks as shown, also when a parameter does not exist yet; never weaken a non-strict card.

**Race simulations.** INVS-C-09 only (`create_inventory` R3, manager R9): `with patch.object(inventory_dao, "get_by_factory_item_type", return_value=None), patch.object(inventory_dao, "_get_any_by_factory_item_type", return_value=None, create=True):` around the When, inside the `raises:` wrap.

## `InventoryService.create_inventory`

### INVS-C-01 — a create is committed with its opening ledger entry and returned re-read
- **Rules:** `create_inventory` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no inventory rows.

**When**
- `result = svc.create_inventory(db, inv_in=InventoryCreate(item_id=I1.id, inventory_type=STORAGE, factory_id=F1.id, qty=3, avg_price=Decimal("10.50"), note="Opening"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `isinstance(result, Inventory)`, `result.id is not None`, `result.created_at is not None`.
3. returns: `result.qty == 3`, `result.avg_price == Decimal("10.50")`, `result.created_by == U1.id`.
4. committed: re-read result: `qty == 3`, `avg_price == Decimal("10.50")`, `note == "Opening"`, `workspace_id == W1.id`, `is_deleted is False`.
5. committed: `len(ledger(result)) == 1`.
6. committed: `ledger(result)[0]`: `transaction_type == "manual_add"`, `quantity == 3`, `total_cost == Decimal("31.50")`, `qty_before == 0`, `qty_after == 3`, `performed_by == U1.id`.

### INVS-C-02 — an unknown factory: the 404 passes unchanged and the pending row is discarded
- **Rules:** `create_inventory` R2, Errors; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no inventory rows.
2. X (after the commit point).

**When**
- `svc.create_inventory(db, inv_in=InventoryCreate(item_id=I1.id, inventory_type=STORAGE, factory_id=MISSING, qty=3), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
4. session: `not db.new`, `not db.dirty`.
5. count: x_gone.
6. count: `inv_count == 0`.
7. count: `ledger_all == 0`.
8. session: usable.

### INVS-C-03 — another workspace's factory: the 404 passes unchanged, the pending row is discarded
- **Rules:** `create_inventory` R2, Errors; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. FX.
2. X (after the commit point).

**When**
- `svc.create_inventory(db, inv_in=InventoryCreate(item_id=I1.id, inventory_type=STORAGE, factory_id=FX.id, qty=3), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {FX.id} not found"`.
4. count: x_gone.
5. count: `inv_count == 0`.
6. count: `ledger_all == 0`.

### INVS-C-04 — a live duplicate: the 409 passes unchanged, the pending row is discarded
- **Rules:** `create_inventory` R2, Errors; TC3 (holds today and after BUG-714)
- **Kind:** error
- **Expect:** pass

**Given**
1. T = inv.
2. X (after the commit point).

**When**
- `svc.create_inventory(db, inv_in=InventoryCreate(item_id=I1.id, inventory_type=STORAGE, factory_id=F1.id, qty=7), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Inventory record already exists for this item/type/factory combination"`.
4. count: x_gone.
5. count: `inv_count == 1`.
6. unchanged: unchanged(T).
7. count: `len(ledger(T)) == 0`.
8. session: usable.

### INVS-C-05 — BUG-710: another workspace's item gets the 404 Item, the pending row is discarded
- **Rules:** `create_inventory` R2 [BUG-710], Errors
- **Kind:** bug
- **Expect:** xfail BUG-710
- **Fails today on:** Then 1 (no error is raised: the row is created on IX)

**Given**
1. IX.
2. X (after the commit point).

**When**
- `svc.create_inventory(db, inv_in=InventoryCreate(item_id=IX.id, inventory_type=STORAGE, factory_id=F1.id, qty=3), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {IX.id} not found"`.
4. count: x_gone.
5. count: `inv_count == 0`.
6. count: `ledger_all == 0`.

### INVS-C-06 — pass-through BUG-715: a soft-deleted factory gets the 404, the pending row is discarded
- **Rules:** `create_inventory` R1 [BUG-715], R2
- **Kind:** bug
- **Expect:** xfail BUG-715
- **Fails today on:** Then 1 (no error is raised: the row is created in the deleted factory)

**Given**
1. FD = factory, but `name "Old Plant"`, `abbreviation "OLD"`, `is_deleted True`, `deleted_at T0`, `deleted_by U2.id` (a real factory soft delete; `is_active` stays True).
2. X (after the commit point).

**When**
- `svc.create_inventory(db, inv_in=InventoryCreate(item_id=I1.id, inventory_type=STORAGE, factory_id=FD.id, qty=3), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {FD.id} not found"`.
4. count: x_gone.
5. count: `inv_count == 0`.

### INVS-C-07 — an inactive but live factory is accepted and committed
- **Rules:** `create_inventory` R1 (holds today and after BUG-715)
- **Kind:** happy
- **Expect:** pass

**Given**
1. FI = factory, but `name "Idle Plant"`, `abbreviation "IDL"`, `is_active False`.

**When**
- `result = svc.create_inventory(db, inv_in=InventoryCreate(item_id=I1.id, inventory_type=STORAGE, factory_id=FI.id, qty=2), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.factory_id == FI.id`.
2. committed: re-read result: `qty == 2`, `factory_id == FI.id`.
3. committed: `len(ledger(result)) == 1`.

### INVS-C-08 — a database error at the flush passes unchanged, nothing saved, session usable
- **Rules:** `create_inventory` R3, Errors; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no inventory rows.
2. X (after the commit point).
3. `data = InventoryCreate.model_construct(item_id=I1.id, inventory_type=STORAGE, factory_id=F1.id, qty=1, avg_price=Decimal("1e13"), note=None)`.

**When**
- `svc.create_inventory(db, inv_in=data, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `DataError`.
2. session: `not db.new`, `not db.dirty`.
3. count: x_gone.
4. count: `inv_count == 0`.
5. count: `ledger_all == 0`.
6. session: usable.

### INVS-C-09 — a concurrent duplicate's IntegrityError passes unchanged after the rollback
- **Rules:** `create_inventory` R3, Errors; TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. T = inv.
2. X (after the commit point).

**When**
- `svc.create_inventory(db, inv_in=InventoryCreate(item_id=I1.id, inventory_type=STORAGE, factory_id=F1.id, qty=4), workspace_id=W1.id, user_id=U1.id)`, with the race simulation active.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: x_gone.
4. count: `inv_count == 1`.
5. unchanged: unchanged(T).
6. count: `len(ledger(T)) == 0`.
7. session: usable.

### INVS-C-10 — a failing commit is rolled back and re-raised; row, ledger and pending row gone
- **Rules:** `create_inventory` R4; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no inventory rows.
2. X (after the commit point).

**When**
- `svc.create_inventory(db, inv_in=InventoryCreate(item_id=I1.id, inventory_type=STORAGE, factory_id=F1.id, qty=3), workspace_id=W1.id, user_id=U1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: x_gone.
4. count: `inv_count == 0`.
5. count: `ledger_all == 0`.

### INVS-C-11 — a failing re-read after the commit leaves row and ledger saved
- **Rules:** `create_inventory` R4; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no inventory rows.

**When**
- `svc.create_inventory(db, inv_in=InventoryCreate(item_id=I1.id, inventory_type=STORAGE, factory_id=F1.id, qty=3), workspace_id=W1.id, user_id=U1.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: `inv_count == 1`.
3. committed: `ledger_all == 1`.

### INVS-C-12 — pass-through BUG-707: a zero price gives total_cost 0.00 on the opening entry
- **Rules:** `create_inventory` R1 [BUG-707]
- **Kind:** bug
- **Expect:** xfail BUG-707
- **Fails today on:** Then 3 (`total_cost` is NULL)

**Given**
1. W1 has no inventory rows.

**When**
- `result = svc.create_inventory(db, inv_in=InventoryCreate(item_id=I1.id, inventory_type=STORAGE, factory_id=F1.id, qty=2, avg_price=Decimal("0.00")), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.qty == 2`.
2. committed: `len(ledger(result)) == 1`.
3. committed: `ledger(result)[0].total_cost == Decimal("0.00")`.

### INVS-C-13 — a zero price is stored and the opening entry carries unit_cost 0.00
- **Rules:** `create_inventory` R1 (holds today and after BUG-707)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no inventory rows.

**When**
- `result = svc.create_inventory(db, inv_in=InventoryCreate(item_id=I1.id, inventory_type=STORAGE, factory_id=F1.id, qty=2, avg_price=Decimal("0.00")), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.avg_price == Decimal("0.00")`.
2. committed: re-read result: `avg_price == Decimal("0.00")`, `qty == 2`.
3. committed: `len(ledger(result)) == 1`.
4. committed: `ledger(result)[0]`: `unit_cost == Decimal("0.00")`, `quantity == 2`.

### INVS-C-14 — pass-through BUG-714: a soft-deleted row of the bucket is restored and committed
- **Rules:** `create_inventory` R1 [BUG-714]
- **Kind:** bug
- **Expect:** xfail BUG-714
- **Fails today on:** Then 1 (the call raises IntegrityError: the insert hits the unique constraint)

**Given**
1. TD = inv, but gone.

**When**
- `result = svc.create_inventory(db, inv_in=InventoryCreate(item_id=I1.id, inventory_type=STORAGE, factory_id=F1.id, qty=4, avg_price=Decimal("6.00"), note="Back"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == TD.id`.
2. committed: re-read TD: `is_deleted is False`, `qty == 4`, `avg_price == Decimal("6.00")`, `note == "Back"`.
3. committed: re-read TD: `created_by == U2.id`, `updated_by == U1.id`.
4. committed: `inv_count == 1`.
5. committed: `len(ledger(TD)) == 1`.
6. committed: `ledger(TD)[0]`: `transaction_type == "manual_add"`, `quantity == 4`.

### INVS-C-15 — qty 0 with no price: the row is committed and no ledger entry is written
- **Rules:** `create_inventory` R1 (opening entry only when qty > 0)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no inventory rows.

**When**
- `result = svc.create_inventory(db, inv_in=InventoryCreate(item_id=I1.id, inventory_type=STORAGE, factory_id=F1.id, qty=0), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.qty == 0`.
2. committed: re-read result: `qty == 0`, `avg_price is None`.
3. committed: `len(ledger(result)) == 0`.

### INVS-C-16 — a successful create also commits a change already pending in the session
- **Rules:** `create_inventory` R1; TC1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no inventory rows.
2. X (after the commit point).

**When**
- `result = svc.create_inventory(db, inv_in=InventoryCreate(item_id=I1.id, inventory_type=STORAGE, factory_id=F1.id, qty=1), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.qty == 1`.
2. committed: x_there.
3. committed: `inv_count == 1`.

## `InventoryService.update_inventory`

### INVS-U-01 — a quantity edit is committed with its ledger entry and returned re-read
- **Rules:** `update_inventory` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = inv.

**When**
- `result = svc.update_inventory(db, inv_id=T.id, inv_in=InventoryUpdate(qty=15), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == T.id`, `result.qty == 15`, `result.updated_at is not None`.
3. committed: re-read T: `qty == 15`, `updated_by == U1.id`, `updated_at is not None`.
4. committed: re-read T: `avg_price == Decimal("5.00")`, `note == "n1"`.
5. committed: `len(ledger(T)) == 1`.
6. committed: `ledger(T)[0]`: `transaction_type == "inventory_adjustment"`, `quantity == 5`, `qty_before == 10`, `qty_after == 15`, `notes == "Quantity adjusted from 10 to 15"`, `performed_by == U1.id`.

### INVS-U-02 — another workspace's row: the 404 passes unchanged, the pending row is discarded
- **Rules:** `update_inventory` R2, Errors; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. FX.
2. IX.
3. TX = inv, but `workspace_id W2.id`, `item_id IX.id`, `factory_id FX.id`.
4. X (after the commit point).

**When**
- `svc.update_inventory(db, inv_id=TX.id, inv_in=InventoryUpdate(qty=99), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Inventory record with ID {TX.id} not found"`.
4. session: `not db.new`, `not db.dirty`.
5. count: x_gone.
6. unchanged: unchanged(TX).
7. count: `len(ledger(TX)) == 0`.
8. session: usable.

### INVS-U-03 — an unknown id: the 404 passes unchanged, the pending row is discarded
- **Rules:** `update_inventory` R2, Errors; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = inv.
2. X (after the commit point).

**When**
- `svc.update_inventory(db, inv_id=MISSING, inv_in=InventoryUpdate(qty=99), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Inventory record with ID 999999999 not found"`.
4. count: x_gone.
5. unchanged: unchanged(T).

### INVS-U-04 — a soft-deleted row: the 400 passes unchanged, the pending row is discarded
- **Rules:** `update_inventory` R2, Errors; TC3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. TD = inv, but gone.
2. X (after the commit point).

**When**
- `svc.update_inventory(db, inv_id=TD.id, inv_in=InventoryUpdate(qty=99), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted inventory record"`.
4. count: x_gone.
5. unchanged: unchanged(TD).
6. count: `len(ledger(TD)) == 0`.

### INVS-U-05 — BUG-713: qty sent as null gets the 422, the pending row is discarded
- **Rules:** `update_inventory` R2 [BUG-713], Errors
- **Kind:** bug
- **Expect:** xfail BUG-713
- **Fails today on:** Then 1 (no error is raised: the null is ignored)

**Given**
1. T = inv.
2. X (after the commit point).

**When**
- `svc.update_inventory(db, inv_id=T.id, inv_in=InventoryUpdate(qty=None), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == "qty cannot be empty"`.
4. count: x_gone.
5. unchanged: unchanged(T).

### INVS-U-06 — pass-through BUG-713: a note sent as null is cleared and committed
- **Rules:** `update_inventory` R1 [BUG-713]
- **Kind:** bug
- **Expect:** xfail BUG-713
- **Fails today on:** Then 2 (the note keeps "n1")

**Given**
1. T = inv.

**When**
- `result = svc.update_inventory(db, inv_id=T.id, inv_in=InventoryUpdate(note=None), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == T.id`.
2. returns: `result.note is None`.
3. committed: re-read T: `note is None`, `qty == 10`.

### INVS-U-07 — fields not sent are kept
- **Rules:** `update_inventory` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = inv.

**When**
- `result = svc.update_inventory(db, inv_id=T.id, inv_in=InventoryUpdate(note="Shelf 4"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.note == "Shelf 4"`.
2. committed: re-read T: `note == "Shelf 4"`, `qty == 10`, `avg_price == Decimal("5.00")`.
3. committed: `len(ledger(T)) == 0`.

### INVS-U-08 — a database error at the flush passes unchanged, nothing saved, session usable
- **Rules:** `update_inventory` R3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = inv.
2. X (after the commit point).
3. `data = InventoryUpdate.model_construct(avg_price=Decimal("1e13"))`.

**When**
- `svc.update_inventory(db, inv_id=T.id, inv_in=data, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `DataError`.
2. session: `not db.dirty`.
3. count: x_gone.
4. unchanged: unchanged(T).
5. count: `len(ledger(T)) == 0`.
6. session: usable.

### INVS-U-09 — a failing commit is rolled back: quantity, ledger and pending row not saved
- **Rules:** `update_inventory` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. T = inv.
2. X (after the commit point).

**When**
- `svc.update_inventory(db, inv_id=T.id, inv_in=InventoryUpdate(qty=15), workspace_id=W1.id, user_id=U1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: x_gone.
4. unchanged: unchanged(T).
5. count: `len(ledger(T)) == 0`.

### INVS-U-10 — a failing re-read after the commit leaves the edit saved
- **Rules:** `update_inventory` R3; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. T = inv.

**When**
- `svc.update_inventory(db, inv_id=T.id, inv_in=InventoryUpdate(qty=15), workspace_id=W1.id, user_id=U1.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: re-read T: `qty == 15`.
3. committed: `len(ledger(T)) == 1`.

### INVS-U-11 — pass-through BUG-703: an empty update does not stamp updated_by
- **Rules:** `update_inventory` R1 [BUG-703]
- **Kind:** bug
- **Expect:** xfail BUG-703
- **Fails today on:** Then 2 (`updated_by` becomes U1)

**Given**
1. T = inv.

**When**
- `result = svc.update_inventory(db, inv_id=T.id, inv_in=InventoryUpdate(), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == T.id`.
2. committed: re-read T: `updated_by is None`.

### INVS-U-12 — pass-through BUG-704: the row is read with FOR UPDATE OF inventory
- **Rules:** `update_inventory` R1a [BUG-704]
- **Kind:** bug
- **Expect:** xfail BUG-704
- **Fails today on:** Then 2 (no statement on `inventory` carries `FOR UPDATE`)

**Given**
1. T = inv.

**When**
- `result = svc.update_inventory(db, inv_id=T.id, inv_in=InventoryUpdate(qty=11), workspace_id=W1.id, user_id=U1.id)`, with the **recorder** on.

**Then**
1. returns: `result.qty == 11`.
2. statement: `any(s.rstrip().endswith("FOR UPDATE OF inventory") for s in inv_selects)`.
3. statement: no statement in `inv_selects` contains `NOWAIT` or `SKIP LOCKED`.

### INVS-U-13 — pass-through BUG-707: a quantity edit at price 0.00 gives total_cost 0.00
- **Rules:** `update_inventory` R1 [BUG-707]
- **Kind:** bug
- **Expect:** xfail BUG-707
- **Fails today on:** Then 3 (`total_cost` is NULL)

**Given**
1. T = inv, but `avg_price Decimal("0.00")`.

**When**
- `result = svc.update_inventory(db, inv_id=T.id, inv_in=InventoryUpdate(qty=12), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.qty == 12`.
2. committed: `len(ledger(T)) == 1`.
3. committed: `ledger(T)[0].total_cost == Decimal("0.00")`.

### INVS-U-14 — pass-through BUG-712: a price-only edit writes a ledger entry
- **Rules:** `update_inventory` R1 [BUG-712]
- **Kind:** bug
- **Expect:** xfail BUG-712
- **Fails today on:** Then 2 (no ledger entry is written)

**Given**
1. T = inv.

**When**
- `result = svc.update_inventory(db, inv_id=T.id, inv_in=InventoryUpdate(avg_price=Decimal("6.00")), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.avg_price == Decimal("6.00")`.
2. committed: `len(ledger(T)) == 1`.
3. committed: `ledger(T)[0]`: `transaction_type == "inventory_adjustment"`, `quantity == 0`, `qty_before == 10`, `qty_after == 10`.
4. committed: `ledger(T)[0]`: `avg_price_before == Decimal("5.00")`, `avg_price_after == Decimal("6.00")`, `notes == "Average price adjusted from 5.00 to 6.00"`.

### INVS-U-15 — a price-only edit is committed
- **Rules:** `update_inventory` R1 (holds today and after BUG-712)
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = inv.

**When**
- `result = svc.update_inventory(db, inv_id=T.id, inv_in=InventoryUpdate(avg_price=Decimal("6.00")), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.avg_price == Decimal("6.00")`.
2. committed: re-read T: `avg_price == Decimal("6.00")`, `qty == 10`, `updated_by == U1.id`.

### INVS-U-16 — a successful update also commits a change already pending in the session
- **Rules:** `update_inventory` R1; TC1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = inv.
2. X (after the commit point).

**When**
- `result = svc.update_inventory(db, inv_id=T.id, inv_in=InventoryUpdate(qty=12), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.qty == 12`.
2. committed: x_there.
3. committed: re-read T: `qty == 12`.

## `InventoryService.get_inventory`

### INVS-G-01 — a row of the workspace is returned
- **Rules:** `get_inventory` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. FX.
2. IX.
3. TX = inv, but `workspace_id W2.id`, `item_id IX.id`, `factory_id FX.id`.
4. T = inv.

**When**
- `result = svc.get_inventory(db, inv_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Inventory)`.
2. returns: `result.id == T.id`, `result.qty == 10`, `result.workspace_id == W1.id`.

### INVS-G-02 — another workspace's row: the 404 passes unchanged
- **Rules:** `get_inventory` R1, Errors (holds today and after BUG-700 / BUG-3082)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = inv.
2. FX.
3. IX.
4. TX = inv, but `workspace_id W2.id`, `item_id IX.id`, `factory_id FX.id`.

**When**
- `svc.get_inventory(db, inv_id=TX.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Inventory record with ID {TX.id} not found"`.
4. unchanged: unchanged(TX).

### INVS-G-03 — an unknown id gets the 404
- **Rules:** `get_inventory` R1, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. T = inv.

**When**
- `svc.get_inventory(db, inv_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Inventory record with ID 999999999 not found"`.

### INVS-G-04 — BUG-700: a soft-deleted row is hidden by default
- **Rules:** `get_inventory` R2 [BUG-700], Errors
- **Kind:** bug
- **Expect:** xfail BUG-700
- **Fails today on:** Then 1 (no error is raised: the deleted row is returned)

**Given**
1. TD = inv, but gone.

**When**
- `svc.get_inventory(db, inv_id=TD.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Inventory record with ID {TD.id} not found"`.
4. unchanged: unchanged(TD).

### INVS-G-05 — BUG-3082: include_deleted=True returns a soft-deleted row of the workspace
- **Rules:** `get_inventory` R3 [BUG-3082]
- **Kind:** bug
- **Expect:** xfail BUG-3082
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)
- **Note:** Remove the xfail only after BUG-700 is fixed too. A BUG-3082 fix that ignores `include_deleted` would still pass these cards; only G-04 catches it.

**Given**
1. TD = inv, but gone.

**When**
- `result = svc.get_inventory(db, inv_id=TD.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == TD.id`.
2. returns: `result.is_deleted is True`, `result.qty == 10`.

### INVS-G-06 — BUG-3082: include_deleted=True does not reach another workspace
- **Rules:** `get_inventory` R3 [BUG-3082], Errors
- **Kind:** bug
- **Expect:** xfail BUG-3082
- **Fails today on:** Then 1 (the call raises TypeError, not HTTPException: the parameter does not exist)
- **Note:** Remove the xfail only after BUG-700 is fixed too. A BUG-3082 fix that ignores `include_deleted` would still pass these cards; only G-04 catches it.

**Given**
1. FX.
2. IX.
3. ZD = inv, but `workspace_id W2.id`, `item_id IX.id`, `factory_id FX.id`, gone.

**When**
- `svc.get_inventory(db, inv_id=ZD.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Inventory record with ID {ZD.id} not found"`.

### INVS-G-07 — BUG-3082: include_deleted=False returns a live row
- **Rules:** `get_inventory` Inputs, R1 [BUG-3082]
- **Kind:** bug
- **Expect:** xfail BUG-3082
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)
- **Note:** Remove the xfail only after BUG-700 is fixed too. A BUG-3082 fix that ignores `include_deleted` would still pass these cards; only G-04 catches it.

**Given**
1. T = inv.

**When**
- `result = svc.get_inventory(db, inv_id=T.id, workspace_id=W1.id, include_deleted=False)`.

**Then**
1. returns: `result.id == T.id`.

### INVS-G-08 — a soft-deleted row of another workspace stays 404 by default
- **Rules:** `get_inventory` R1, R3 (holds today and after the fix)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. FX.
2. IX.
3. ZD = inv, but `workspace_id W2.id`, `item_id IX.id`, `factory_id FX.id`, gone.

**When**
- `svc.get_inventory(db, inv_id=ZD.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Inventory record with ID {ZD.id} not found"`.

### INVS-G-09 — the read neither commits nor rolls back
- **Rules:** `get_inventory` R4; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = inv.
2. I2.
3. B = inv, but `item_id I2.id`.
4. X (after the commit point).
5. `B.note = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_inventory(db, inv_id=T.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. returns: `result.id == T.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. count: x_there.
7. committed: x_gone.
8. committed: re-read B: `note == "n1"`.

### INVS-G-10 — a 404 from the manager passes unchanged with no rollback
- **Rules:** `get_inventory` R4; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = inv.
2. X (after the commit point).

**When**
- `svc.get_inventory(db, inv_id=MISSING, workspace_id=W1.id)`, inside **spies**.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. count: x_there.

## `InventoryService.get_inventory_page`

### INVS-P-01 — with the defaults: live rows of the workspace with qty > 0, skip 0, limit 50
- **Rules:** `get_inventory_page` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I2.
2. FX.
3. IX.
4. B = inv, but `item_id I2.id`, `qty 0`.
5. A = inv.
6. TX = inv, but `workspace_id W2.id`, `item_id IX.id`, `factory_id FX.id`.

**When**
- `result = svc.get_inventory_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result.items] == [A.id]`.
2. returns: `result.total == 1`.
3. returns: `result.skip == 0`, `result.limit == 50`, `result.has_more is False`.

### INVS-P-02 — inventory_type reaches the manager
- **Rules:** `get_inventory_page` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. B = inv, but `inventory_type DAMAGED`.
2. A = inv.

**When**
- `result = svc.get_inventory_page(db, workspace_id=W1.id, inventory_type=DAMAGED)`.

**Then**
1. returns: `[r.id for r in result.items] == [B.id]`.
2. returns: `result.total == 1`.

### INVS-P-03 — factory_id reaches the manager
- **Rules:** `get_inventory_page` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F2.
2. B = inv, but `factory_id F2.id`.
3. A = inv.

**When**
- `result = svc.get_inventory_page(db, workspace_id=W1.id, factory_id=F2.id)`.

**Then**
1. returns: `[r.id for r in result.items] == [B.id]`.
2. returns: `result.total == 1`.

### INVS-P-04 — item_id reaches the manager
- **Rules:** `get_inventory_page` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I2.
2. B = inv, but `item_id I2.id`.
3. A = inv.

**When**
- `result = svc.get_inventory_page(db, workspace_id=W1.id, item_id=I2.id)`.

**Then**
1. returns: `[r.id for r in result.items] == [B.id]`.
2. returns: `result.total == 1`.

### INVS-P-05 — search reaches the manager (text in the middle, other case)
- **Rules:** `get_inventory_page` R1 (holds today and after BUG-702)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I2.
2. B = inv, but `item_id I2.id`.
3. A = inv.

**When**
- `result = svc.get_inventory_page(db, workspace_id=W1.id, search="X NU")`.

**Then**
1. returns: `[r.id for r in result.items] == [B.id]`.
2. returns: `result.total == 1`.

### INVS-P-06 — include_zero_qty=True reaches the manager
- **Rules:** `get_inventory_page` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I2.
2. B = inv, but `item_id I2.id`, `qty 0`.
3. A = inv.

**When**
- `result = svc.get_inventory_page(db, workspace_id=W1.id, include_zero_qty=True)`.

**Then**
1. returns: `sorted(r.id for r in result.items) == sorted([A.id, B.id])`.
2. returns: `result.total == 2`.

### INVS-P-07 — skip and limit reach the manager and are echoed
- **Rules:** `get_inventory_page` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I2.
2. I3.
3. RW = inv, but `item_id I3.id`.
4. RB = inv.
5. RH = inv, but `item_id I2.id`.

**When**
- `result = svc.get_inventory_page(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `[r.id for r in result.items] == [RH.id]`.
2. returns: `result.total == 3`.
3. returns: `result.skip == 1`, `result.limit == 1`, `result.has_more is True`.

### INVS-P-08 — limit=1000 reaches the manager
- **Rules:** `get_inventory_page` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I2.
2. I3.
3. RW = inv, but `item_id I3.id`.
4. RB = inv.
5. RH = inv, but `item_id I2.id`.

**When**
- `result = svc.get_inventory_page(db, workspace_id=W1.id, skip=1, limit=1000)`.

**Then**
1. returns: `[r.id for r in result.items] == [RH.id, RW.id]`.
2. returns: `result.limit == 1000`, `result.has_more is False`.

### INVS-P-09 — the default limit is 50: 51 rows give 50
- **Rules:** `get_inventory_page` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 51 items, by `add_all`: k = 1 … 51, item, but `name f"Part {k:02d}"`, `unit "pcs"`.
2. 51 rows, by `add_all`: one inv per item of line 1, but `item_id` that item's id.

**When**
- `result = svc.get_inventory_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result.items) == 50`.
2. returns: `result.total == 51`.
3. returns: `result.limit == 50`, `result.has_more is True`.

### INVS-P-10 — rows come in item-name order ignoring case
- **Rules:** `get_inventory_page` R1 (holds today and after BUG-701)
- **Kind:** happy
- **Expect:** pass

**Given**
1. IC = item, but `name "Cog"`.
2. IA = item, but `name "apple"`.
3. RC = inv, but `item_id IC.id`.
4. RB = inv.
5. RA = inv, but `item_id IA.id`.

**When**
- `result = svc.get_inventory_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result.items] == [RA.id, RB.id, RC.id]`.

### INVS-P-11 — pass-through BUG-701: a case-only tie is broken by inventory id
- **Rules:** `get_inventory_page` R1 [BUG-701]
- **Kind:** bug
- **Expect:** xfail BUG-701
- **Fails today on:** Then 2 (the collation puts "apple" first)

**Given**
1. IU = item, but `name "Apple"`.
2. IL = item, but `name "apple"`.
3. RU = inv, but `item_id IU.id`.
4. RL = inv, but `item_id IL.id`.

**When**
- `result = svc.get_inventory_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result.items) == 2`.
2. returns: `[r.id for r in result.items] == [RU.id, RL.id]`.

### INVS-P-12 — pass-through BUG-702: "%" is literal and matches nothing
- **Rules:** `get_inventory_page` R1 [BUG-702]
- **Kind:** bug
- **Expect:** xfail BUG-702
- **Fails today on:** Then 1 (every row matches)

**Given**
1. I2.
2. A = inv.
3. B = inv, but `item_id I2.id`.

**When**
- `result = svc.get_inventory_page(db, workspace_id=W1.id, search="%")`.

**Then**
1. returns: `result.total == 0`.
2. returns: `result.items == []`.

### INVS-P-13 — the list neither commits nor rolls back
- **Rules:** `get_inventory_page` R2; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = inv.
2. X (after the commit point).
3. `A.note = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_inventory_page(db, workspace_id=W1.id)`, inside **spies**.

**Then**
1. returns: `[r.id for r in result.items] == [A.id]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `A in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. count: x_there.
7. committed: x_gone.
8. committed: re-read A: `note == "n1"`.

### INVS-P-14 — a soft-deleted row is left out
- **Rules:** `get_inventory_page` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. I2.
2. D = inv, but `item_id I2.id`, gone.
3. A = inv.

**When**
- `result = svc.get_inventory_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result.items] == [A.id]`.
2. returns: `result.total == 1`.

## `InventoryService.get_inventory_stats`

### INVS-S-01 — with the defaults: totals of the workspace's live rows with qty > 0
- **Rules:** `get_inventory_stats` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I2.
2. I3.
3. FX.
4. IX.
5. A = inv.
6. B = inv, but `item_id I2.id`, `qty 4`, `avg_price Decimal("2.50")`.
7. Z = inv, but `item_id I3.id`, `qty 0`.
8. TX = inv, but `workspace_id W2.id`, `item_id IX.id`, `factory_id FX.id`.

**When**
- `result = svc.get_inventory_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.records == 2`, `result.total_qty == 14`.
2. returns: `result.estimated_value == Decimal("60.00")`.
3. returns: `len(result.by_type) == 1`.
4. returns: `result.by_type[0].inventory_type == STORAGE`, `result.by_type[0].unique_item_count == 2`, `result.by_type[0].total_qty == 14`.

### INVS-S-02 — inventory_type reaches the manager
- **Rules:** `get_inventory_stats` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = inv.
2. B = inv, but `inventory_type DAMAGED`, `qty 3`.

**When**
- `result = svc.get_inventory_stats(db, workspace_id=W1.id, inventory_type=DAMAGED)`.

**Then**
1. returns: `result.records == 1`, `result.total_qty == 3`.

### INVS-S-03 — factory_id reaches the manager
- **Rules:** `get_inventory_stats` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F2.
2. A = inv.
3. B = inv, but `factory_id F2.id`, `qty 3`.

**When**
- `result = svc.get_inventory_stats(db, workspace_id=W1.id, factory_id=F2.id)`.

**Then**
1. returns: `result.records == 1`, `result.total_qty == 3`.

### INVS-S-04 — item_id reaches the manager
- **Rules:** `get_inventory_stats` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I2.
2. A = inv.
3. B = inv, but `item_id I2.id`, `qty 3`.

**When**
- `result = svc.get_inventory_stats(db, workspace_id=W1.id, item_id=I2.id)`.

**Then**
1. returns: `result.records == 1`, `result.total_qty == 3`.

### INVS-S-05 — search reaches the manager (text in the middle, other case)
- **Rules:** `get_inventory_stats` R1 (holds today and after BUG-702)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I2.
2. A = inv.
3. B = inv, but `item_id I2.id`, `qty 3`.

**When**
- `result = svc.get_inventory_stats(db, workspace_id=W1.id, search="X NU")`.

**Then**
1. returns: `result.records == 1`, `result.total_qty == 3`.

### INVS-S-06 — include_zero_qty=True reaches the manager
- **Rules:** `get_inventory_stats` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I2.
2. A = inv.
3. Z = inv, but `item_id I2.id`, `qty 0`.

**When**
- `result = svc.get_inventory_stats(db, workspace_id=W1.id, include_zero_qty=True)`.

**Then**
1. returns: `result.records == 2`, `result.total_qty == 10`.

### INVS-S-07 — no matching rows: zero totals and an empty breakdown
- **Rules:** `get_inventory_stats` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no inventory rows.

**When**
- `result = svc.get_inventory_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.records == 0`, `result.total_qty == 0`.
2. returns: `result.estimated_value == Decimal("0")`.
3. returns: `result.by_type == []`.

### INVS-S-08 — pass-through BUG-702: "_" is literal and matches nothing
- **Rules:** `get_inventory_stats` R1 [BUG-702]
- **Kind:** bug
- **Expect:** xfail BUG-702
- **Fails today on:** Then 1 (every row matches)

**Given**
1. I2.
2. A = inv.
3. B = inv, but `item_id I2.id`, `qty 3`.

**When**
- `result = svc.get_inventory_stats(db, workspace_id=W1.id, search="_")`.

**Then**
1. returns: `result.records == 0`.
2. returns: `result.total_qty == 0`.

### INVS-S-09 — pass-through BUG-719: the breakdown comes in enum order
- **Rules:** `get_inventory_stats` R1 [BUG-719]
- **Kind:** bug
- **Expect:** xfail BUG-719 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no order is asked for; it may already come in enum order, an XPASS is reported, not fixed)

**Given**
1. inv, but `inventory_type SCRAP`.
2. inv, but `inventory_type WASTE`.
3. inv, but `inventory_type DAMAGED`.
4. inv.

**When**
- `result = svc.get_inventory_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result.by_type) == 4`.
2. returns: `[e.inventory_type for e in result.by_type] == [STORAGE, DAMAGED, WASTE, SCRAP]`.

### INVS-S-10 — the stats neither commit nor roll back
- **Rules:** `get_inventory_stats` R2; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = inv.
2. X (after the commit point).
3. `A.qty = 99` (after the commit point, not flushed).

**When**
- `result = svc.get_inventory_stats(db, workspace_id=W1.id)`, inside **spies**.

**Then**
1. returns: `result.records == 1`, `result.total_qty == 10`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `A in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. count: x_there.
7. committed: x_gone.
8. committed: re-read A: `qty == 10`.

## `InventoryService.get_incoming_summary`

### INVS-IS-01 — one factory: its open PO line is summarised, the other factory's is not
- **Rules:** `get_incoming_summary` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S_OPEN, S_DONE, WF.
2. F2.
3. P1 = po 1 on F1.
4. line of P1.
5. P2 = po 2 on F2.
6. line of P2.

**When**
- `result = svc.get_incoming_summary(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].factory_id == F1.id`, `result[0].item_id == I1.id`.
3. returns: `result[0].total_pending_qty == Decimal("7")`, `result[0].order_count == 1`.
4. returns: `len(result[0].orders) == 1`.
5. returns: `result[0].orders[0]`: `order_kind == "purchase"`, `order_id == P1.id`, `order_number == f"PO-INVS-{SFX}-1"`, `status_name == "Ordered"`, `pending_qty == Decimal("7")`.

### INVS-IS-02 — factory_id=None covers every active factory of the workspace
- **Rules:** `get_incoming_summary` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S_OPEN, S_DONE, WF.
2. F2.
3. P1 = po 1 on F1.
4. line of P1.
5. P2 = po 2 on F2.
6. line of P2.

**When**
- `result = svc.get_incoming_summary(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `{(r.factory_id, r.item_id) for r in result} == {(F1.id, I1.id), (F2.id, I1.id)}`.

### INVS-IS-03 — factory_id=0 gets the 404
- **Rules:** `get_incoming_summary` R1, R2, Errors
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S_OPEN, S_DONE, WF.
2. P1 = po 1 on F1.
3. line of P1.

**When**
- `svc.get_incoming_summary(db, workspace_id=W1.id, factory_id=0)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 0 not found"`.

### INVS-IS-04 — another workspace's factory gets the 404
- **Rules:** `get_incoming_summary` R2, Errors
- **Kind:** isolation
- **Expect:** pass

**Given**
1. FX.

**When**
- `svc.get_incoming_summary(db, workspace_id=W1.id, factory_id=FX.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {FX.id} not found"`.

### INVS-IS-05 — pass-through BUG-718: a soft-deleted factory gets the 404
- **Rules:** `get_incoming_summary` R1 [BUG-718], R2
- **Kind:** bug
- **Expect:** xfail BUG-718
- **Fails today on:** Then 1 (no error is raised: the deleted factory is summarised)

**Given**
1. S_OPEN, S_DONE, WF.
2. FD = factory, but `name "Old Plant"`, `abbreviation "OLD"`, `is_deleted True`, `deleted_at T0`, `deleted_by U2.id` (a real factory soft delete; `is_active` stays True).
3. P1 = po 1 on FD.
4. line of P1.

**When**
- `svc.get_incoming_summary(db, workspace_id=W1.id, factory_id=FD.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {FD.id} not found"`.

### INVS-IS-06 — an inactive but live factory is still summarised
- **Rules:** `get_incoming_summary` R1 (holds today and after BUG-718)
- **Kind:** happy
- **Expect:** pass

**Given**
1. S_OPEN, S_DONE, WF.
2. FI = factory, but `name "Idle Plant"`, `abbreviation "IDL"`, `is_active False`.
3. P1 = po 1 on FI.
4. line of P1.

**When**
- `result = svc.get_incoming_summary(db, workspace_id=W1.id, factory_id=FI.id)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].factory_id == FI.id`, `result[0].total_pending_qty == Decimal("7")`.

### INVS-IS-07 — pass-through BUG-717: a voided PO is not incoming
- **Rules:** `get_incoming_summary` R1 [BUG-717]
- **Kind:** bug
- **Expect:** xfail BUG-717
- **Fails today on:** Then 2 (the voided PO's 8 count: total 15, two orders)

**Given**
1. S_OPEN, S_DONE, WF.
2. P1 = po 1 on F1.
3. line of P1.
4. PV = po 2 on F1, but `voided True`.
5. line of PV, but `quantity_ordered Decimal("8")`, `quantity_received Decimal("0")`.

**When**
- `result = svc.get_incoming_summary(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].total_pending_qty == Decimal("7")`, `result[0].order_count == 1`.
3. returns: `[o.order_id for o in result[0].orders] == [P1.id]`.

### INVS-IS-08 — the summary neither commits nor rolls back
- **Rules:** `get_incoming_summary` R3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S_OPEN, S_DONE, WF.
2. P1 = po 1 on F1.
3. line of P1.
4. T = inv.
5. X (after the commit point).
6. `T.note = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_incoming_summary(db, workspace_id=W1.id, factory_id=F1.id)`, inside **spies**.

**Then**
1. returns: `len(result) == 1`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `T in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. count: x_there.
7. committed: x_gone.
8. committed: re-read T: `note == "n1"`.

### INVS-IS-09 — pass-through BUG-706: factories come in name order ignoring case
- **Rules:** `get_incoming_summary` R1 [BUG-706]
- **Kind:** bug
- **Expect:** xfail BUG-706 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no order is asked for; insertion order, Main before Alpha, usually comes back)

**Given**
1. S_OPEN, S_DONE, WF.
2. FA = factory, but `name "alpha Plant"`, `abbreviation "ALP"`.
3. P1 = po 1 on F1.
4. line of P1.
5. P2 = po 2 on FA.
6. line of P2.

**When**
- `result = svc.get_incoming_summary(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `[r.factory_id for r in result] == [FA.id, F1.id]`.

### INVS-IS-10 — a 404 from the manager passes unchanged with no rollback
- **Rules:** `get_incoming_summary` R2, R3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = inv.
2. X (after the commit point).

**When**
- `svc.get_incoming_summary(db, workspace_id=W1.id, factory_id=0)`, inside **spies**.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. count: x_there.

## `InventoryService.delete_inventory`

### INVS-D-01 — clear stock is committed with its ledger entry; the row stays live
- **Rules:** `delete_inventory` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = inv.

**When**
- `result = svc.delete_inventory(db, inv_id=T.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == T.id`, `result.qty == 0`, `result.is_deleted is False`, `result.updated_at is not None`.
3. committed: re-read T: `qty == 0`, `updated_by == U1.id`, `is_deleted is False`, `is_active is True`.
4. committed: re-read T: `avg_price == Decimal("5.00")`, `note == "n1"`.
5. committed: `len(ledger(T)) == 1`.
6. committed: `ledger(T)[0]`: `transaction_type == "inventory_adjustment"`, `quantity == 10`, `qty_before == 10`, `qty_after == 0`, `total_cost == Decimal("50.00")`, `notes == "Stock cleared"`, `performed_by == U1.id`.

### INVS-D-02 — qty already 0: committed, returned unchanged, no ledger entry
- **Rules:** `delete_inventory` R2 (holds today and after BUG-716)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = inv, but `qty 0`.
2. X (after the commit point).

**When**
- `result = svc.delete_inventory(db, inv_id=T.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == T.id`, `result.qty == 0`.
2. committed: x_there.
3. committed: re-read T: `qty == 0`, `updated_by is None`.
4. committed: `len(ledger(T)) == 0`.

### INVS-D-03 — another workspace's row: the 404 passes unchanged, the pending row is discarded
- **Rules:** `delete_inventory` R3, Errors; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. FX.
2. IX.
3. TX = inv, but `workspace_id W2.id`, `item_id IX.id`, `factory_id FX.id`.
4. X (after the commit point).

**When**
- `svc.delete_inventory(db, inv_id=TX.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Inventory record with ID {TX.id} not found"`.
4. session: `not db.new`, `not db.dirty`.
5. count: x_gone.
6. unchanged: unchanged(TX).
7. count: `len(ledger(TX)) == 0`.
8. session: usable.

### INVS-D-04 — an unknown id: the 404 passes unchanged, the pending row is discarded
- **Rules:** `delete_inventory` R3, Errors; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = inv.
2. X (after the commit point).

**When**
- `svc.delete_inventory(db, inv_id=MISSING, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Inventory record with ID 999999999 not found"`.
4. count: x_gone.
5. unchanged: unchanged(T).

### INVS-D-05 — a soft-deleted row: the 400 passes unchanged, the pending row is discarded
- **Rules:** `delete_inventory` R3, Errors; TC3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. TD = inv, but gone.
2. X (after the commit point).

**When**
- `svc.delete_inventory(db, inv_id=TD.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot clear stock on a deactivated inventory record"`.
4. count: x_gone.
5. unchanged: unchanged(TD).
6. count: `len(ledger(TD)) == 0`.

### INVS-D-06 — a failing commit is rolled back: qty, ledger and pending row not saved
- **Rules:** `delete_inventory` R4; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. T = inv.
2. X (after the commit point).

**When**
- `svc.delete_inventory(db, inv_id=T.id, workspace_id=W1.id, user_id=U1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: x_gone.
4. unchanged: unchanged(T).
5. count: `len(ledger(T)) == 0`.

### INVS-D-07 — a failing re-read after the commit leaves the clear saved
- **Rules:** `delete_inventory` R4; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. T = inv.

**When**
- `svc.delete_inventory(db, inv_id=T.id, workspace_id=W1.id, user_id=U1.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: re-read T: `qty == 0`.
3. committed: `len(ledger(T)) == 1`.

### INVS-D-08 — pass-through BUG-716: a negative quantity is cleared to 0 with a ledger entry
- **Rules:** `delete_inventory` R1 [BUG-716]
- **Kind:** bug
- **Expect:** xfail BUG-716
- **Fails today on:** Then 2 (qty stays -4)

**Given**
1. T = inv, but `qty -4`.

**When**
- `result = svc.delete_inventory(db, inv_id=T.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == T.id`.
2. committed: re-read T: `qty == 0`, `updated_by == U1.id`.
3. committed: `len(ledger(T)) == 1`.
4. committed: `ledger(T)[0]`: `quantity == 4`, `qty_before == -4`, `qty_after == 0`, `notes == "Stock cleared"`.

### INVS-D-09 — pass-through BUG-705: the row is read with FOR UPDATE OF inventory
- **Rules:** `delete_inventory` R1a [BUG-705]
- **Kind:** bug
- **Expect:** xfail BUG-705
- **Fails today on:** Then 2 (no statement on `inventory` carries `FOR UPDATE`)

**Given**
1. T = inv.

**When**
- `result = svc.delete_inventory(db, inv_id=T.id, workspace_id=W1.id, user_id=U1.id)`, with the **recorder** on.

**Then**
1. returns: `result.qty == 0`.
2. statement: `any(s.rstrip().endswith("FOR UPDATE OF inventory") for s in inv_selects)`.
3. statement: no statement in `inv_selects` contains `NOWAIT` or `SKIP LOCKED`.

### INVS-D-10 — pass-through BUG-707: a clear at price 0.00 gives total_cost 0.00
- **Rules:** `delete_inventory` R1 [BUG-707]
- **Kind:** bug
- **Expect:** xfail BUG-707
- **Fails today on:** Then 3 (`total_cost` is NULL)

**Given**
1. T = inv, but `avg_price Decimal("0.00")`.

**When**
- `result = svc.delete_inventory(db, inv_id=T.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.qty == 0`.
2. committed: `len(ledger(T)) == 1`.
3. committed: `ledger(T)[0].total_cost == Decimal("0.00")`.

### INVS-D-11 — a successful clear also commits a change already pending in the session
- **Rules:** `delete_inventory` R1; TC1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = inv.
2. X (after the commit point).

**When**
- `result = svc.delete_inventory(db, inv_id=T.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.qty == 0`.
2. committed: x_there.
3. committed: re-read T: `qty == 0`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| BUG-3082 — the `include_deleted` query parameter | `GET /inventory/{inv_id}/` (integration) | The parameter is accepted and reaches the service. |
| BUG-704, BUG-705 — real concurrency | integration tests (two connections) | The second request waits for the first's commit and sees its quantity; of two clears only one writes a ledger entry. Unit cards check the SQL only. |
| BUG-708, BUG-711 — schema rejects negative / over-precise values (422) | `inventory_manager.cases.md` schema cards; `POST`, `PUT /inventory/` | Schema rules, not the service's; the service never sees an invalid body. |
| BUG-709 — no 500-factory cap | `inventory_manager.cases.md` INV-IS-07 | 501 factories; a service pass-through adds nothing. |
| BUG-706 strict `ORDER BY` alarm for the factory query | factory DAO cases (`get_active_factories`, where the fix lives) | Strict SQL `ORDER BY` check; decided in the spec header (gap 3, closed). |
| `IntegrityError` → 409, `DataError` → 500, body `ValidationError` → 422 | `app/main.py` handlers (integration) | Integration-only. |
| HR-7 — `skip >= 0`, `1 <= limit <= 1000` | `GET /inventory/` | Endpoint bounds. |
| Manager rules (filters, order, search, ledger fields, incoming rules) beyond one pass-through each | `tests/unit/managers/inventory_manager.cases.md` | Not re-tested here. |
| `list_inventory` | dead-code checklist | Not specified; to be removed. |
| Session closed by the request dependency | `get_db` | Integration-only. |

## Spec gaps
None open. Closed in Revision 2 (spec Gap log, 2026-11-22):

| # | Resolution | Cards changed |
|---|---|---|
| 1 | G1 (fact): a real factory soft delete sets `is_deleted`, `deleted_at`, `deleted_by` and leaves `is_active`; the inventory checks read `is_deleted` only. | C-06, IS-05: FD also sets `deleted_at T0`, `deleted_by U2.id` (fully real state). |
| 2 | G2 (fact): new spec rules `update_inventory` R1a, `delete_inventory` R1a: `FOR UPDATE OF inventory` (joined eager load of `items`), no `NOWAIT` / `SKIP LOCKED`. The manager spec's R10 / R8 still say plain `FOR UPDATE` (outside this file). | U-12, D-09: Then 2 pins `FOR UPDATE OF inventory`, new Then 3 rules out `NOWAIT` / `SKIP LOCKED`; Rules cite R1a; Coverage matrix rows moved to R1a. |
| 3 | G3 (contradiction): spec header now says BUG-706 is non-strict here and the strict `ORDER BY` check belongs to the factory DAO cases. | None (IS-09 already non-strict); Deferred row now names the factory DAO cases. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_inventory` | R1 | INVS-C-01, C-07, C-13, C-15, C-16 |
| `create_inventory` | R1 [BUG-707] | INVS-C-12 |
| `create_inventory` | R1 [BUG-714] | INVS-C-14 |
| `create_inventory` | R1 [BUG-715] | INVS-C-06 |
| `create_inventory` | R1 [BUG-711] | Deferred (schema) |
| `create_inventory` | R2 (404 factory, 409) | INVS-C-02, C-03, C-04 |
| `create_inventory` | R2 [BUG-710] | INVS-C-05 |
| `create_inventory` | R3 | INVS-C-08 (`DataError`), C-09 (`IntegrityError`) |
| `create_inventory` | R4 | INVS-C-10 (TC4), C-11 (TC5) |
| `create_inventory` | Errors, Returns | INVS-C-01 … C-05, C-08, C-09 |
| `update_inventory` | R1 | INVS-U-01, U-07, U-15, U-16 |
| `update_inventory` | R1 [BUG-703] | INVS-U-11 |
| `update_inventory` | R1a [BUG-704] | INVS-U-12 |
| `update_inventory` | R1 [BUG-707] | INVS-U-13 |
| `update_inventory` | R1 [BUG-712] | INVS-U-14 |
| `update_inventory` | R1 [BUG-713] | INVS-U-06 |
| `update_inventory` | R2 (404, 400) | INVS-U-02, U-03, U-04 |
| `update_inventory` | R2 [BUG-713] | INVS-U-05 |
| `update_inventory` | R3 | INVS-U-08 (`DataError`), U-09 (TC4), U-10 (TC5) |
| `update_inventory` | Errors, Returns | INVS-U-01 … U-05, U-08 |
| `get_inventory` | Inputs [BUG-3082] | INVS-G-07 |
| `get_inventory` | R1 | INVS-G-01, G-02, G-03, G-08 |
| `get_inventory` | R2 [BUG-700] | INVS-G-04 |
| `get_inventory` | R3 [BUG-3082] | INVS-G-05, G-06 |
| `get_inventory` | R4 | INVS-G-09, G-10 |
| `get_inventory` | Errors | INVS-G-02, G-03, G-04, G-06, G-08, G-10 |
| `get_inventory_page` | R1 | INVS-P-01 … P-10, P-14 |
| `get_inventory_page` | R1 [BUG-701] | INVS-P-11 |
| `get_inventory_page` | R1 [BUG-702] | INVS-P-12 |
| `get_inventory_page` | R2 | INVS-P-13 |
| `get_inventory_stats` | R1 | INVS-S-01 … S-07 |
| `get_inventory_stats` | R1 [BUG-702] | INVS-S-08 |
| `get_inventory_stats` | R1 [BUG-719] | INVS-S-09 |
| `get_inventory_stats` | R2 | INVS-S-10 |
| `get_incoming_summary` | R1 | INVS-IS-01, IS-02, IS-03, IS-06 |
| `get_incoming_summary` | R1 [BUG-706] | INVS-IS-09 |
| `get_incoming_summary` | R1 [BUG-709] | Deferred (manager INV-IS-07) |
| `get_incoming_summary` | R1 [BUG-717] | INVS-IS-07 |
| `get_incoming_summary` | R1 [BUG-718] | INVS-IS-05 |
| `get_incoming_summary` | R2, Errors | INVS-IS-03, IS-04, IS-10 |
| `get_incoming_summary` | R3 | INVS-IS-08, IS-10 |
| `delete_inventory` | R1 | INVS-D-01, D-11 |
| `delete_inventory` | R1a [BUG-705] | INVS-D-09 |
| `delete_inventory` | R1 [BUG-707] | INVS-D-10 |
| `delete_inventory` | R1 [BUG-716] | INVS-D-08 |
| `delete_inventory` | R2 | INVS-D-02 |
| `delete_inventory` | R3, Errors | INVS-D-03, D-04, D-05 |
| `delete_inventory` | R4 | INVS-D-06 (TC4), D-07 (TC5) |
| `delete_inventory` | Returns | INVS-D-01 |
| Transaction contract | TC1 | INVS-C-01, C-16, U-01, U-16, D-01, D-02, D-11 |
| Transaction contract | TC2 | INVS-C-01, U-01, D-01 |
| Transaction contract | TC3 | INVS-C-02 … C-05, C-08, C-09, U-02 … U-05, U-08, D-03, D-04, D-05 |
| Transaction contract | TC4 | INVS-C-10, U-09, D-06 |
| Transaction contract | TC5 | INVS-C-11, U-10, D-07 |
| Transaction contract | TC6 | INVS-G-09, G-10, P-13, S-10, IS-08, IS-10 |
