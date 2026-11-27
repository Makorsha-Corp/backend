# Test cases — `app/services/machine_item_service.py`

> **Spec:** `tests/unit/services/machine_item_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 1 — spec Gap log G1 (the `IntegrityError` example is an unknown `user_id`, not the unknown item). New: MIS-C-15. Changed: Conventions (`IntegrityError` import), Reviewer summary. MIS-C-09 (BUG-1010) unchanged. No other card changed, none retired.
> **Counts:** 42 cases · 24 expected-to-pass · 18 expected-to-fail (bugs) · 8 deferred

## Reviewer summary
- **Per callable:** `get_machine_item` 7 (4 bug) · `get_machine_items` 8 (3 bug) · `create_machine_item` 15 (5 bug) · `update_machine_item` 5 (2 bug) · `delete_machine_item` 7 (4 bug).
- **Depth:** lighter target for the transaction wrapper (skill step 1a): TC2, TC4, TC5 once (on create), TC1 and TC3 once per write, TC6 once per read, each refusal status once. The service's own decision, the BUG-1081 translation, gets full attention: a patched-manager card for the translation itself (exact `detail`, exact blocker list, rollback seen) and one end-to-end card with a real blocking work order. Stock is written here, but every stock rule is the manager's (490 cards); one pass-through per manager bug, all strict except BUG-1071 (non-strict, as the manager's cards).
- **TC1 includes the ledger and activity rows** the manager writes; each error card checks none was saved.
- **Notable design choices:**
  - Commit point and uncommitted-extra-row device as `department_service.cases.md`; here the extra row is a stock row of M2.
  - **Manager patch** on MIS-D-03 only, as the spec's Notes prescribe (the manager does not raise the `ValueError` yet). Declared in Conventions; it is not a race simulation.
  - `create_machine_item` R3 is reached twice: a `DataError` from `qty = 2**31` built by `model_construct` (C-05), and an `IntegrityError` 23503 from an unknown `user_id` (C-15, spec G1). Both are ordinary passes. The unknown item stays BUG-1010's card (C-09), never a today-shape.
  - `delete_machine_item` has no TC5 (no re-read) and its TC4 is the create card's: the commit helper is shared.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `MIS` = `app/services/machine_item_service.py`. `G` get_machine_item · `L` get_machine_items · `C` create_machine_item · `U` update_machine_item · `D` delete_machine_item.

**Actors and fixed values.**
- `svc` = the singleton `machine_item_service` (`from app.services.machine_item_service import MachineItemService, machine_item_service`). `db` = the test's real session, always the first argument; the rest by keyword. `result` = what the When call returns.
- W1, W2 = two `workspaces` rows; U1, U2 = two `profiles` rows (`make_workspace`, `make_profile`). U1 created every Given row, U2 is the acting user.
- Classes: `Factory`, `Machine`, `Item`, `MachineItem`, `MachineItemLedger`, `MachineActivityEvent`, `WorkOrder`, `WorkOrderType`, `WorkOrderItem` (each from `app.models.<snake_case name>`). `MachineItemCreate`, `MachineItemUpdate` (`app.schemas.machine_item`). `AppValidationError` = `app.core.exceptions.ValidationError`; `PydanticValidationError` = `pydantic.ValidationError`. `HTTPException` (`fastapi`); `DataError`, `IntegrityError` (`sqlalchemy.exc`); `inspect`, `text` (`sqlalchemy`); `patch` (`unittest.mock`).
- MISSING = `999999999`.

**Externals.** None is mocked, except the **manager patch** on MIS-D-03: `with patch.object(svc.machine_item_manager, "delete_machine_item", side_effect=ValueError("Machine item has open orders", [{"type": "work_order", "id": 3}, {"type": "other_workspace"}])):` around the When, inside the `raises:` wrap. And the **create patch** on MIS-C-14: `with patch.object(svc.machine_item_manager, "create_machine_item", side_effect=ValueError("x", [])):` around the When, inside the `raises:` wrap (Q1: only delete translates).

**Standing rows.** In every test, in this order, no Given line needed; built directly, `is_active True`, `is_deleted False`, `workspace_id W1.id`, `created_by U1.id` unless stated.
- F1 = `Factory(name="Main Plant", abbreviation="MP")`. FD = the same, but `name "Closed Mill"`, `abbreviation "CM"`, `is_deleted True`. F9 = the same, but `name "Far Depot"`, `abbreviation "FR"`, `workspace_id W2.id`.
- Items, `Item(name=…, name_normalized=…, unit="pcs")`: I1 `"Bolt M8"` / `"bolt m8"`. I2 `"Washer Ten"` / `"washer ten"`. IX `"Old Rivet"` / `"old rivet"`, `is_active False`. I9 `"Far Spring"` / `"far spring"`, `workspace_id W2.id`.
- Machines, `Machine(factory_id=…, name=…, is_running=False)`: M1 `"Lathe"`, M2 `"Press"` of F1. MX `"Old Saw"` of F1, `is_deleted True`, `is_active False`. MF `"Kiln"` of FD. M9 `"Grinder"` of F9, `workspace_id W2.id`.
- WT1 = `WorkOrderType(name="Repair")`.

**Given rows.** Built directly (never through `svc`), flushed one at a time in the order written. A Given line written as code is a step to run exactly.
- **stock of M, I** = `MachineItem(workspace_id=W1.id, machine_id=M.id, item_id=I.id, req_qty=None, defective_qty=None)`; the card gives `qty`.
- **bulk(n)** = n items named `P00000`, `P00001`, … (`name_normalized` the same), and n rows stock of M1, one per item, `qty 1`, by `add_all`.
- **work order of M** = `WorkOrder(workspace_id=W1.id, work_order_number="WO-" + <Given name>, work_order_type_id=WT1.id, title="Service", factory_id=F1.id, machine_id=M.id, is_deleted=False)`; the card gives `status`.
- **source line of O** = `WorkOrderItem(workspace_id=W1.id, work_order_id=O.id, item_id=I1.id, quantity=2, uses_inventory=True, consumed_at=None, source_location_type="machine", source_location_id=M1.id, replaced_item_id=None, is_deleted=False)`.
- **commit point** = after the last Given line the test runs `db.commit()` (a savepoint release under the `db` fixture). A Given line marked "(after the commit point)" runs after it, is flushed, and stays uncommitted.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **nothing written** = the row counts of `machine_items`, `machine_item_ledger`, `machine_activity_events` (all workspaces) equal their values at the commit point.
- **entries_of(M, I)** = a fresh SELECT of `machine_item_ledger` with that `machine_id` and `item_id`, ordered by `id`. **events_of(M)** = a fresh SELECT of `machine_activity_events` with `machine_id == M.id`, ordered by `id`.
- **ids(x)** = `sorted(r.id for r in x)`. `count:` lines count with a fresh query, with the filter stated.
- `loaded:` lines run on the returned object first: each column named is not in `inspect(result).unloaded`.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads or counts with a fresh query.
- `session:` lines check `db` itself; "usable" = `db.execute(text("SELECT 1")).scalar() == 1`.
- `raises: <Type>`: plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint. Further `raises:` lines assert on `exc.value` after the block. A schema card wraps only the schema's construction (target `schema`).
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "refresh", side_effect=RuntimeError("boom")):` around the When.

**xfail cards.** Write the call and checks as shown, also when a parameter does not exist yet. Strict unless the Expect line says `(non-strict)`.

**Race simulations.** None in this module.

## `MachineItemService.get_machine_item`

### MIS-G-01 — a row of the workspace is returned as the manager returns it
- **Rules:** `get_machine_item` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `result = svc.get_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, MachineItem)`.
2. returns: `result.id == MI.id`, `result.qty == 5`, `result.item_id == I1.id`.

### MIS-G-02 — another workspace's call: the 404 passes unchanged
- **Rules:** `get_machine_item` R1, Errors
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `svc.get_machine_item(db, machine_item_id=MI.id, workspace_id=W2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.

### MIS-G-03 — a row of a soft-deleted machine is hidden by default
- **Rules:** `get_machine_item` R2 [BUG-1077], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1077
- **Fails today on:** Then 1 (no error is raised: the row is returned)

**Given**
1. MI = stock of MX, I1, `qty 5`.

**When**
- `svc.get_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.

### MIS-G-04 — include_deleted=True returns a row of a soft-deleted machine
- **Rules:** `get_machine_item` R3 [BUG-1077]
- **Kind:** bug
- **Expect:** xfail BUG-1077
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. MI = stock of MX, I1, `qty 5`.

**When**
- `result = svc.get_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == MI.id`.
2. returns: `result.qty == 5`.

### MIS-G-05 — include_deleted=True does not show a row with another workspace's item
- **Rules:** `get_machine_item` R3 [BUG-1077], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1077
- **Fails today on:** Then 1 (the call raises TypeError, not HTTPException)

**Given**
1. MI = stock of M1, I9, `qty 5`. (A row of W1 with an item of W2, invalid data.)

**When**
- `svc.get_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.

### MIS-G-06 — pass-through BUG-1086: a row with another workspace's item is not found
- **Rules:** `get_machine_item` R1 [BUG-1086]
- **Kind:** bug
- **Expect:** xfail BUG-1086
- **Fails today on:** Then 1 (no error is raised: the row is returned)

**Given**
1. MI = stock of M1, I9, `qty 5`. (A row of W1 with an item of W2, invalid data.)

**When**
- `svc.get_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.

### MIS-G-07 — the read neither commits nor rolls back
- **Rules:** `get_machine_item` R4; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock of M1, I1, `qty 5`.
2. B = stock of M1, I2, `qty 4`.
3. P = stock of M2, I1, `qty 9` (after the commit point).
4. `B.qty = 40` (after the commit point, not flushed).

**When**
- `result = svc.get_machine_item(db, machine_item_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. count: `machine_items` rows with `machine_id == M2.id`: exactly 1.
5. committed: `machine_items` rows with `machine_id == M2.id`: exactly 0.
6. committed: re-read B: `qty == 4`.

## `MachineItemService.get_machine_items`

### MIS-L-01 — machine_id reaches the manager
- **Rules:** `get_machine_items` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock of M1, I1, `qty 5`.
2. B = stock of M2, I2, `qty 5`.

**When**
- `result = svc.get_machine_items(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id]`.

### MIS-L-02 — with the defaults 101 rows give 100
- **Rules:** `get_machine_items` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(101).

**When**
- `result = svc.get_machine_items(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### MIS-L-03 — limit=1000 reaches the manager and gives all 101
- **Rules:** `get_machine_items` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(101).

**When**
- `result = svc.get_machine_items(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.

### MIS-L-04 — skip reaches the manager
- **Rules:** `get_machine_items` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(101).

**When**
- `result = svc.get_machine_items(db, workspace_id=W1.id, skip=100)`.

**Then**
1. returns: `len(result) == 1`.

### MIS-L-05 — the list neither commits nor rolls back
- **Rules:** `get_machine_items` R2; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock of M1, I1, `qty 5`.
2. B = stock of M1, I2, `qty 4`.
3. P = stock of M2, I1, `qty 9` (after the commit point).
4. `B.qty = 40` (after the commit point, not flushed).

**When**
- `result = svc.get_machine_items(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. committed: `machine_items` rows with `machine_id == M2.id`: exactly 0.
5. committed: re-read B: `qty == 4`.

### MIS-L-06 — pass-through BUG-1074: machine_id 0 filters like any integer
- **Rules:** `get_machine_items` R1 [BUG-1074]
- **Kind:** bug
- **Expect:** xfail BUG-1074
- **Fails today on:** Then 1 (0 counts as no filter: every row comes back)

**Given**
1. A = stock of M1, I1, `qty 5`.

**When**
- `result = svc.get_machine_items(db, workspace_id=W1.id, machine_id=0)`.

**Then**
1. returns: `result == []`.

### MIS-L-07 — pass-through BUG-1070: a row of a soft-deleted machine is left out
- **Rules:** `get_machine_items` R1 [BUG-1070]
- **Kind:** bug
- **Expect:** xfail BUG-1070
- **Fails today on:** Then 1 (every row of the workspace is returned)

**Given**
1. A = stock of MX, I1, `qty 5`.
2. B = stock of M2, I2, `qty 5`.

**When**
- `result = svc.get_machine_items(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MIS-L-08 — pass-through BUG-1071: rows come in item-name order, case-insensitive
- **Rules:** `get_machine_items` R1 [BUG-1071]
- **Kind:** bug
- **Expect:** xfail BUG-1071 (non-strict)
- **Fails today on:** Then 2 (no order is requested; the database's order comes back)

**Given**
1. IZ = `Item(name="Zulu", name_normalized="zulu", unit="pcs")`.
2. IA = `Item(name="apple", name_normalized="apple", unit="pcs")`.
3. IB = `Item(name="Banana", name_normalized="banana", unit="pcs")`.
4. stock of M1, IZ, `qty 1`.
5. stock of M1, IA, `qty 1`.
6. stock of M2, IB, `qty 1`.

**When**
- `result = svc.get_machine_items(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `[r.item_id for r in result] == [IA.id, IB.id, IZ.id]`.

## `MachineItemService.create_machine_item`

### MIS-C-01 — a new stock row, its ledger entry and activity row are committed; the row is returned re-read
- **Rules:** `create_machine_item` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `result = svc.create_machine_item(db, item_in=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=5, req_qty=7), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `qty`, `req_qty`, `machine_id`, `item_id`.
2. returns: `isinstance(result, MachineItem)`.
3. returns: `result.qty == 5`, `result.req_qty == 7`, `result.machine_id == M1.id`.
4. committed: the row with `id == result.id` exists: `qty == 5`, `req_qty == 7`, `workspace_id == W1.id`.
5. committed: `entries_of(M1, I1)` has exactly 1 row.
6. committed: that entry: `transaction_type == "manual_add"`, `quantity == 5`, `performed_by == U2.id`.
7. committed: events_of(M1) has exactly 1 row.
8. committed: that row: `event_type == "item_added"`, `performed_by == U2.id`.

### MIS-C-02 — another workspace's machine: the 404 passes unchanged and the session is rolled back
- **Rules:** `create_machine_item` R2, Errors; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock of M1, I1, `qty 5`.
2. X = stock of M2, I2, `qty 3` (after the commit point).

**When**
- `svc.create_machine_item(db, item_in=MachineItemCreate(machine_id=M9.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine not found in this workspace"`.
4. count: `machine_items` rows with `machine_id == M2.id`: exactly 0.
5. nothing written: nothing written.
6. unchanged: unchanged(A).
7. session: usable.

### MIS-C-03 — a soft-deleted machine: the 400 passes unchanged, nothing saved
- **Rules:** `create_machine_item` R2, Errors
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `svc.create_machine_item(db, item_in=MachineItemCreate(machine_id=MX.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot add items to a deleted machine"`.
4. nothing written: nothing written.

### MIS-C-04 — the item already on the machine: the 409 passes unchanged, nothing saved
- **Rules:** `create_machine_item` R2, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = stock of M1, I1, `qty 5`.

**When**
- `svc.create_machine_item(db, item_in=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=2), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "This item already exists on this machine. Update the existing record instead."`.
4. unchanged: unchanged(A).
5. nothing written: nothing written.

### MIS-C-05 — a DataError at the flush passes unchanged; nothing saved; the session is usable
- **Rules:** `create_machine_item` R3, Errors; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. No stock rows exist.
2. `data = MachineItemCreate.model_construct(machine_id=M1.id, item_id=I1.id, qty=2**31, req_qty=None, defective_qty=None)`.

**When**
- `svc.create_machine_item(db, item_in=data, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `DataError`.
2. nothing written: nothing written.
3. session: usable.

### MIS-C-06 — a failing commit is rolled back and re-raised: no row, entry or activity is saved
- **Rules:** `create_machine_item` R4; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `svc.create_machine_item(db, item_in=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `machine_items` rows: exactly 0.
4. count: `entries_of(M1, I1)` has exactly 0 rows.
5. event: events_of(M1) has exactly 0 rows.

### MIS-C-07 — a failing re-read after the commit leaves the row, entry and activity saved
- **Rules:** `create_machine_item` R4; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `svc.create_machine_item(db, item_in=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: `machine_items` rows with `machine_id == M1.id`: exactly 1.
3. committed: `entries_of(M1, I1)` has exactly 1 row.
4. committed: events_of(M1) has exactly 1 row.

### MIS-C-08 — pass-through BUG-1076: a live machine in a soft-deleted factory is refused
- **Rules:** `create_machine_item` R2 [BUG-1076]
- **Kind:** bug
- **Expect:** xfail BUG-1076
- **Fails today on:** Then 1 (no error is raised: the row is saved)

**Given**
1. No stock rows exist.

**When**
- `svc.create_machine_item(db, item_in=MachineItemCreate(machine_id=MF.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot add items to a deleted machine"`.
4. nothing written: nothing written.

### MIS-C-09 — pass-through BUG-1010: an unknown item gets the 404
- **Rules:** `create_machine_item` R2 [BUG-1010]
- **Kind:** bug
- **Expect:** xfail BUG-1010
- **Fails today on:** Then 1 (the call raises IntegrityError: the item is not checked and the flush fails)

**Given**
1. No stock rows exist.

**When**
- `svc.create_machine_item(db, item_in=MachineItemCreate(machine_id=M1.id, item_id=MISSING, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Item with ID 999999999 not found"`.
4. nothing written: nothing written.

### MIS-C-10 — pass-through BUG-1085: a removed item is refused
- **Rules:** `create_machine_item` R2 [BUG-1085]
- **Kind:** bug
- **Expect:** xfail BUG-1085
- **Fails today on:** Then 1 (no error is raised: the row is saved)

**Given**
1. No stock rows exist.

**When**
- `svc.create_machine_item(db, item_in=MachineItemCreate(machine_id=M1.id, item_id=IX.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot add a removed item to a machine"`.
4. nothing written: nothing written.

### MIS-C-11 — pass-through BUG-1079: a negative qty is refused by the schema
- **Rules:** `create_machine_item` R1 [BUG-1079]
- **Kind:** bug
- **Expect:** xfail BUG-1079
- **Fails today on:** Then 1 (the schema has no minimum)

**Given**
1. No stock rows exist.

**When**
- build `MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=-1)` (target `schema`; `svc` is not called).

**Then**
1. raises: `PydanticValidationError`.
2. nothing written: nothing written.

### MIS-C-12 — pass-through BUG-1078: a qty of 2147483648 is refused by the schema
- **Rules:** `create_machine_item` R1 [BUG-1078]
- **Kind:** bug
- **Expect:** xfail BUG-1078
- **Fails today on:** Then 1 (the schema has no maximum)

**Given**
1. No stock rows exist.

**When**
- build `MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=2147483648)` (target `schema`; `svc` is not called).

**Then**
1. raises: `PydanticValidationError`.
2. nothing written: nothing written.

### MIS-C-13 — the schema still accepts qty 2147483647
- **Rules:** `create_machine_item` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `data = MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=2147483647)` (target `schema`; `svc` is not called).

**Then**
1. returns: `data.qty == 2147483647`.

### MIS-C-14 — a ValueError from create is not translated: only delete translates
- **Rules:** `create_machine_item` R3; `delete_machine_item` R2 (scope, Q1)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `svc.create_machine_item(db, item_in=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`, with the create patch active, inside `raises: ValueError`.

**Then**
1. raises: `type(exc.value) is ValueError`.
2. raises: `exc.value.args == ("x", [])`.
3. nothing written: nothing written.

### MIS-C-15 — an unknown user: the IntegrityError passes unchanged; nothing saved; the session is usable
- **Rules:** `create_machine_item` R3, Errors; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = stock of M1, I2, `qty 4`.
2. X = stock of M2, I2, `qty 3` (after the commit point).

**When**
- `svc.create_machine_item(db, item_in=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. count: `machine_items` rows with `item_id == I1.id`: exactly 0.
4. count: `machine_items` rows with `machine_id == M2.id`: exactly 0.
5. nothing written: nothing written.
6. unchanged: unchanged(A).
7. session: usable.

## `MachineItemService.update_machine_item`

### MIS-U-01 — a qty change with its entry and activity is committed; the row is returned re-read
- **Rules:** `update_machine_item` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `result = svc.update_machine_item(db, machine_item_id=MI.id, item_in=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `qty`, `req_qty`.
2. returns: `result.id == MI.id`.
3. returns: `result.qty == 12`.
4. committed: re-read MI: `qty == 12`.
5. committed: `entries_of(M1, I1)` has exactly 1 row.
6. committed: events_of(M1) with `event_type == "item_updated"` has exactly 1 row.
7. committed: events_of(M1) with `event_type == "inventory_adjusted"` has exactly 1 row.

### MIS-U-02 — another workspace's call: the 404 passes unchanged and the session is rolled back
- **Rules:** `update_machine_item` R2, Errors; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. X = stock of M2, I2, `qty 3` (after the commit point).

**When**
- `svc.update_machine_item(db, machine_item_id=MI.id, item_in=MachineItemUpdate(qty=12), workspace_id=W2.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. count: `machine_items` rows with `machine_id == M2.id`: exactly 0.
5. unchanged: unchanged(MI).
6. nothing written: nothing written.

### MIS-U-03 — pass-through BUG-1083: a row of a soft-deleted machine is refused
- **Rules:** `update_machine_item` R2 [BUG-1083]
- **Kind:** bug
- **Expect:** xfail BUG-1083
- **Fails today on:** Then 1 (no error is raised: the row is updated)

**Given**
1. MI = stock of MX, I1, `qty 5`.

**When**
- `svc.update_machine_item(db, machine_item_id=MI.id, item_in=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update items of a deleted machine"`.
4. unchanged: unchanged(MI).
5. nothing written: nothing written.

### MIS-U-04 — pass-through BUG-1075: an explicit null clears req_qty
- **Rules:** `update_machine_item` R1 [BUG-1075]
- **Kind:** bug
- **Expect:** xfail BUG-1075
- **Fails today on:** Then 2 (null is dropped and the old value stays)

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`.

**When**
- `result = svc.update_machine_item(db, machine_item_id=MI.id, item_in=MachineItemUpdate(req_qty=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == MI.id`.
2. committed: re-read MI: `req_qty is None`.

### MIS-U-05 — an update of req_qty alone is committed without a ledger entry
- **Rules:** `update_machine_item` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`.

**When**
- `result = svc.update_machine_item(db, machine_item_id=MI.id, item_in=MachineItemUpdate(req_qty=9), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.req_qty == 9`.
2. committed: re-read MI: `req_qty == 9`, `qty == 5`.
3. committed: `entries_of(M1, I1)` has exactly 0 rows.
4. committed: events_of(M1) has exactly 1 row.

## `MachineItemService.delete_machine_item`

### MIS-D-01 — a delete with its final entry and activity is committed; None is returned
- **Rules:** `delete_machine_item` R1, Returns; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. `mi_id = MI.id`.

**When**
- `result = svc.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. committed: `machine_items` rows with `id == mi_id`: exactly 0.
3. committed: `entries_of(M1, I1)` has exactly 1 row.
4. committed: that entry: `transaction_type == "inventory_adjustment"`, `qty_before == 5`, `qty_after == 0`.
5. committed: events_of(M1) with `event_type == "item_removed"` has exactly 1 row.

### MIS-D-02 — another workspace's call: the 404 passes unchanged and the session is rolled back
- **Rules:** `delete_machine_item` R4, Errors row 2; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. X = stock of M2, I2, `qty 3` (after the commit point).

**When**
- `svc.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W2.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. count: `machine_items` rows with `machine_id == M2.id`: exactly 0.
5. unchanged: unchanged(MI).
6. nothing written: nothing written.
7. session: usable.

### MIS-D-03 — the manager's in-use ValueError becomes the 400 ValidationError with the blockers as given, after a rollback
- **Rules:** `delete_machine_item` R2 [BUG-1081], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (the `ValueError` escapes unchanged)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. X = stock of M2, I2, `qty 3` (after the commit point).

**When**
- `svc.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`, with the manager patch active, inside `raises: AppValidationError`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Machine item has open orders"`.
4. raises: `exc.value.errors == [{"type": "work_order", "id": 3}, {"type": "other_workspace"}]`.
5. count: `machine_items` rows with `machine_id == M2.id`: exactly 0.
6. unchanged: unchanged(MI).

### MIS-D-04 — end to end: an open work order blocks the delete with a 400 that lists it
- **Rules:** `delete_machine_item` R2 [BUG-1081], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: the manager does not look at orders and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, name `"A"`.
3. L1 = source line of O1.

**When**
- `svc.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Machine item has open orders"`.
4. raises: `exc.value.errors == [{"type": "work_order", "id": O1.id}]`.
5. unchanged: unchanged(MI).
6. nothing written: nothing written.

### MIS-D-06 — pass-through BUG-1084: a row of a soft-deleted machine is refused
- **Rules:** `delete_machine_item` R4 [BUG-1084], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1084
- **Fails today on:** Then 1 (no error is raised: the row is deleted)

**Given**
1. MI = stock of MX, I1, `qty 5`.

**When**
- `svc.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot remove items from a deleted machine"`.
4. unchanged: unchanged(MI).
5. nothing written: nothing written.

### MIS-D-07 — pass-through BUG-1080: a row below 0 books its final adjustment to 0
- **Rules:** `delete_machine_item` R1 [BUG-1080]
- **Kind:** bug
- **Expect:** xfail BUG-1080
- **Fails today on:** Then 3 (no ledger entry is written for a negative row)

**Given**
1. MI = stock of M1, I1, `qty -3`.
2. `mi_id = MI.id`.

**When**
- `result = svc.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. committed: `machine_items` rows with `id == mi_id`: exactly 0.
3. committed: `entries_of(M1, I1)` has exactly 1 row.
4. committed: that entry: `qty_before == -3`, `qty_after == 0`.

### MIS-D-08 — a failing commit on delete is rolled back: the row stays
- **Rules:** `delete_machine_item` R5; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `svc.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(MI).
4. nothing written: nothing written.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `delete_machine_item` R3 [BUG-1081] — the 400 body over HTTP (`type`, `title`, `status`, `detail`, `errors`) | `DELETE /machine-items/{id}/` with `api_exception_handler` (integration; `tests/unit/core/exceptions.spec.md`) | 400 with the blocker list; integration-only. |
| BUG-1081 manager half — the `ValueError` with blockers (R5a), every blocker type and cross-workspace shape | `tests/unit/managers/machine_item_manager.cases.md` | Full depth there. |
| BUG-1077 — the `include_deleted` query parameter | `GET /machine-items/{id}/` (integration) | Accepted and passed on. |
| Every other manager rule beyond one pass-through per bug | `machine_item_manager.cases.md` | Not re-tested here. |
| HR-7 — `skip >= 0`, `1 <= limit <= 1000` | `GET /machine-items/` | Endpoint bounds. |
| `DataError` → 500; `IntegrityError` → global 409 | API handlers (integration) | Integration-only. |
| BUG-1082 | frontend | No backend case. |
| Schema errors answer 422 (BUG-461) | `POST`, `PUT /machine-items/` | Integration-only. |

## Spec gaps
None. Revision 0's gap 1 is closed by spec Gap log G1 (MIS-C-15).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_machine_item` | R1 | MIS-G-01, MIS-G-02 |
| `get_machine_item` | R1 [BUG-1086] | MIS-G-06 |
| `get_machine_item` | R2 [BUG-1077] | MIS-G-03 |
| `get_machine_item` | R3 [BUG-1077] | MIS-G-04, MIS-G-05 |
| `get_machine_item` | R4 | MIS-G-07 |
| `get_machine_item` | Errors | MIS-G-02, MIS-G-03, MIS-G-05, MIS-G-06 |
| `get_machine_items` | R1 | MIS-L-01, MIS-L-02, MIS-L-03, MIS-L-04 |
| `get_machine_items` | R1 [BUG-1070] | MIS-L-07 |
| `get_machine_items` | R1 [BUG-1071] | MIS-L-08 |
| `get_machine_items` | R1 [BUG-1074] | MIS-L-06 |
| `get_machine_items` | R2 | MIS-L-05 |
| `create_machine_item` | R1 | MIS-C-01, MIS-C-13 |
| `create_machine_item` | R1 [BUG-1078] | MIS-C-12 |
| `create_machine_item` | R1 [BUG-1079] | MIS-C-11 |
| `create_machine_item` | R2 | MIS-C-02, MIS-C-03, MIS-C-04 |
| `create_machine_item` | R2 [BUG-1010] | MIS-C-09 |
| `create_machine_item` | R2 [BUG-1076] | MIS-C-08 |
| `create_machine_item` | R2 [BUG-1085] | MIS-C-10 |
| `create_machine_item` | R3 | MIS-C-05, MIS-C-14, MIS-C-15 |
| `create_machine_item` | R4 | MIS-C-06, MIS-C-07 |
| `create_machine_item` | Errors | MIS-C-02, MIS-C-03, MIS-C-04, MIS-C-05, MIS-C-15 |
| `create_machine_item` | Returns | MIS-C-01 |
| `update_machine_item` | R1 | MIS-U-01, MIS-U-05 |
| `update_machine_item` | R1 [BUG-1075] | MIS-U-04 |
| `update_machine_item` | R2 | MIS-U-02 |
| `update_machine_item` | R2 [BUG-1083] | MIS-U-03 |
| `update_machine_item` | R3 | MIS-U-02 (rollback of the `except` path); MIS-C-05, MIS-C-06, MIS-C-07 (database error, TC4, TC5 once per service) |
| `update_machine_item` | Errors | MIS-U-02, MIS-U-03 |
| `update_machine_item` | Returns | MIS-U-01 |
| `delete_machine_item` | R1 | MIS-D-01 |
| `delete_machine_item` | R1 [BUG-1080] | MIS-D-07 |
| `delete_machine_item` | R2 | MIS-C-14 (scope: no translation outside delete) |
| `delete_machine_item` | R2 [BUG-1081] | MIS-D-03, MIS-D-04 |
| `delete_machine_item` | R3 [BUG-1081] | Deferred (integration) |
| `delete_machine_item` | R4 | MIS-D-02 |
| `delete_machine_item` | R4 [BUG-1084] | MIS-D-06 |
| `delete_machine_item` | R5 | MIS-D-08 |
| `delete_machine_item` | Errors row 1 | MIS-D-03, MIS-D-04 |
| `delete_machine_item` | Errors row 2 | MIS-D-02, MIS-D-06 |
| `delete_machine_item` | Returns | MIS-D-01 |
| Transaction contract | TC1 | MIS-C-01, MIS-U-01, MIS-D-01 |
| Transaction contract | TC2 | MIS-C-01 (also MIS-U-01) |
| Transaction contract | TC3 | MIS-C-02, MIS-C-05, MIS-C-15, MIS-U-02, MIS-D-02 |
| Transaction contract | TC4 | MIS-C-06, MIS-D-08 |
| Transaction contract | TC5 | MIS-C-07 |
| Transaction contract | TC6 | MIS-G-07, MIS-L-05 |
