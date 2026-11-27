# Test cases — `app/managers/machine_item_manager.py`

> **Spec:** `tests/unit/managers/machine_item_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 5 (2026-10-31) — verifier finding 3, spec G10: R5 (a) applies whatever the `action_type`. Added MIM-D-247, MIM-D-248, MIM-D-249, MIM-D-250 (`INSTALL`, `BORROW`, `REPLACE`, and one line that meets both (a) and (b)), all xfail BUG-1081. MIM-W-21 … MIM-W-25 keep `next_clock_tick()`; the spec's Note is fixed. No existing card changed.
> Revision 4 (2026-10-31) — verifier findings 1, 2, 4 of `machine_item_manager.verify.md`, all `case-missing`, additive: MIM-L-67, MIM-L-68, MIM-L-69, MIM-L-70, MIM-W-33, MIM-D-246. Finding 1: hidden rows that sort ahead of the visible row, so a filter after paging fails (deleted machine, deleted factory, foreign item on both paths). Finding 2: a `value_after` midpoint. Finding 4: a delete with `qty 1`. No existing card changed.
> Revision 3 (2026-10-31) — executor's discrepancies in `machine_item_manager.notes.md`. MIM-W-21 … MIM-W-25: a `next_clock_tick()` Given line between entries written with the real clock (DISCREPANCY-1), defined in Conventions. MIM-U-25: new Then 4 counts the one event, so "that row" has a referent; the old Then 4 is Then 5. No ID changed.
> Revision 2 (2026-10-31) — spec fill-gaps, Gap log G1–G9 and the owner's correction. Recipe `replace line of O` is now `uses_inventory True`. MIM-D-30 retitled. MIM-D-31 retired. Added MIM-W-32, MIM-D-238, MIM-D-239, MIM-D-240, MIM-D-241, MIM-D-242, MIM-D-243, MIM-D-244, MIM-D-245. MIM-D-38 stays blocking. `Executor confirm` lines removed, Conventions note too; MIM-C-25 names the method on the DAO object. No other ID changed.
> Revision 1 (2026-10-31) — first design. Built in up front, from `item_manager.verify.md` round 6 and `machine_manager.verify.md` rounds 2, 3: every blocker type, non-blocking state and cross-workspace shape, normal rows on foreign parents, lines judged one at a time, sort, dedupe, generic entry last, refusal before any write.
> **Counts:** 490 cases · 280 expected-to-pass · 210 expected-to-fail (bugs) · 14 deferred

## Reviewer summary
- **Per callable:** `_item_name` 2 (0 bug) · `get_machine_item` 20 (11 bug) · `list_machine_items` 70 (28 bug) · `_write_ledger_entry` 33 (17 bug) · `create_machine_item` 52 (18 bug) · `update_machine_item` 64 (24 bug) · `delete_machine_item` 249 (112 bug).
- **Depth:** full (step 1a): this module writes stock and ledger rows and carries money rounding.
- **Expected-to-fail by bug:** BUG-976 2 · BUG-979 2 · BUG-980 1 · BUG-983 1 · BUG-993 17 · BUG-1010 4 · BUG-1040 5 · BUG-1070 10 · BUG-1071 6 · BUG-1072 1 · BUG-1073 1 · BUG-1074 1 · BUG-1075 4 · BUG-1076 2 · BUG-1077 9 · BUG-1078 6 · BUG-1079 6 · BUG-1080 4 · BUG-1081 95 · BUG-1083 8 · BUG-1084 8 · BUG-1085 3 · BUG-1086 14. 8 of the 210 are non-strict (physical order); all others strict.
- **Notable design choices:**
  - **`delete_machine_item` refusal built to the verifiers' item and machine findings up front.** One card per blocker type and open status; each non-blocking state of (a) 9, (b) 9, (c) 5, (d) 5 is a pass card in **four shapes**: own rows, order and line of W2, W1 line on a W2 order, W2 line on a W1 order. The product is deliberate: a fix limited to one shape or state must fail. Blocking shapes, lines judged one at a time, W1 rows on W2 parents, sort by order id with line ids reversed, type order with ids reversed, dedupe, and closed rows beside open ones each have their own cards.
  - **Exact equality** on `args[1]` carries the "no W2 id in the refusal" Note. A separate text search could not fail on its own (verifier R2-4 on machine) and digits of own ids can collide, so there is no such line.
  - **Refusals before a write:** plain `pytest.raises`, no savepoint; `session:` lines check dirty, deleted and a working flush before any re-read. Unknown user has a card with a normal blocker and one with only the generic entry.
  - **BUG-1040:** spec Notes' recipe, an unexpired ledger object at `0.125`. 1 × 0.125 = 0.13 tells half up from half even; 5 × 0.125 = 0.63 also rejects rounding the price first (0.65). The same recipe gives `value_before` 0.13, `value_after` 0.25 (G6). These cards need BUG-993 too, so they carry `xfail BUG-1040` and stay xfail until both are fixed.
  - **Order of checks read from "treated as not found" (Q11):** a foreign-item row gives 404 before the deleted-machine 400 and before the open-order refusal.
  - **Parent and purchase order state does not unblock (R5):** an order's soft-deleted or inactive factory, an order's soft-deleted machine, a soft-deleted or inactive transfer destination (the owner's G12 answer, applied by Claude, G3); a consumed `REPLACE` line with `uses_inventory True` (owner, G4); a pending return at any stage or on a voided purchase order (owner, G5). Stage `Complete` is the `delivered PO` recipe's own stage, so MIM-D-24 is that card.
  - **Takes-no-place cards are strict** by a recipe free of physical order: 2 hidden rows, 1 visible, `limit=2`; today two rows return whichever are picked. Where the hidden rows also sort first by name, a filter applied after the page fails under the intended order too. The spec's own Anvil / Bolt example is a non-strict card beside them.
  - `_item_name` R3 has no direct card, as the spec says: covered by the BUG-1086 update and delete cards. `Author:` lines are not used; a Claude subagent writes the whole file.
- **Needs a decision:** None. Spec gaps 1–9 are closed by the spec's Gap log G1–G9.

## Conventions for this module

**IDs.** `MIM` = `app/managers/machine_item_manager.py`. `IN` _item_name · `G` get_machine_item · `L` list_machine_items · `W` _write_ledger_entry · `C` create_machine_item · `U` update_machine_item · `D` delete_machine_item.

**Actors and fixed values.**
- `M` = the singleton `machine_item_manager` (`from app.managers.machine_item_manager import MachineItemManager, machine_item_manager`). `db` = the test's real session, always the first argument; the rest by keyword, except where a card writes a positional call. `result` = what the When call returns. The session does not autoflush.
- W1, W2 = two `workspaces` rows; U1, U2 = two `profiles` rows from `tests/unit/factories.py`. U1 is `created_by` of every Given row, U2 the acting user.
- Classes: `Factory` (`app.models.factory`), `Machine` (`app.models.machine`), `Item` (`app.models.item`), `MachineItem` (`app.models.machine_item`), `MachineItemLedger` (`app.models.machine_item_ledger`), `MachineActivityEvent` (`app.models.machine_activity_event`), `WorkOrder` (`app.models.work_order`), `WorkOrderType` (`app.models.work_order_type`), `WorkOrderItem` (`app.models.work_order_item`), `TransferOrder` (`app.models.transfer_order`), `TransferOrderItem` (`app.models.transfer_order_item`), `PurchaseOrder` (`app.models.purchase_order`), `PurchaseOrderItem` (`app.models.purchase_order_item`), `PurchaseOrderReturn`, `PurchaseOrderReturnItem` (`app.models.purchase_order_return`), `Status` (`app.models.status`). Schemas `MachineItemBase`, `MachineItemCreate`, `MachineItemUpdate` (`app.schemas.machine_item`). `_machine_in`, `_machine_out`, `get_machine_unit_cost` (`app.managers.inventory_movements`). `machine_item_ledger_dao` (`app.dao.machine_item_ledger`). `Decimal` (`decimal`), `HTTPException` (`fastapi`).
- MISSING = `999999999`: an id no row of any table has. T9, T10, T11, T12 = `datetime(2025, 1, 1, 9, 0, 0)` … `datetime(2025, 1, 1, 12, 0, 0)` (naive, in the past, so the manager's own entry is the newest).
- Money compares by value (`Decimal`). `"→"` in a description is the one character U+2192; copy it.

**Externals.** None is mocked. `performed_at`, `created_at` are checked as set / not set, or are given in the Given.

**Standing rows.** In every test, in this order, no Given line needed; `is_active True`, `is_deleted False`, `workspace_id W1.id`, `created_by U1.id` unless stated. No other row exists unless a Given line builds it.
- Factories: F1 `"Main Plant"` / `"MP"`. FD `"Closed Mill"` / `"CM"`, `is_deleted True` (`is_active` stays True). FI `"Idle Plant"` / `"IP"`, `is_active False`. F9 `"Far Depot"` / `"FR"`, `workspace_id W2.id`.
- Items (`unit "pcs"`): I1 `"Bolt M8"`, `name_normalized "bolt m8"`. I2 `"Washer Ten"` / `"washer ten"`. I3 `"Cotter Pin"` / `"cotter pin"`. IX `"Old Rivet"` / `"old rivet"`, `is_active False`. IX2 `"Old Hinge"` / `"old hinge"`, `is_active False`. I9 `"Far Spring"` / `"far spring"`, W2. I92 `"Far Clip"` / `"far clip"`, W2.
- Machines (`is_running False`): M1 `"Lathe"`, M2 `"Press"` of F1. MX `"Old Saw"` of F1, `is_deleted True`, `is_active False`. MF `"Kiln"` of FD. MA `"Mixer"` of F1, `is_active False`. MN `"Nova"` of FI. M9 `"Grinder"` of F9, W2.
- WT1 = `work_order_types` row `"Repair"`; WT9 `"Far Repair"`, W2. STD, STC = `statuses` rows `name "Draft"`, `"Complete"`, `comment "stage"`; ST9 = the same as STD, W2.

**Given rows.** Built directly, never through `M` unless the line is written as code, flushed one at a time in the order written, so ids rise in that order. A line names a recipe, then after "but" every column that differs. A line written as code is a step to run exactly. Ids are read right after the Given: `MI.id` in a Then is that value, also after a hard delete. Rows of W2, and a row of W1 with an item of W2, are invalid data, built only to prove they are hidden.
- **item** = `items` row: `unit "pcs"`, `workspace_id W1.id`, `is_active True`, `created_by U1.id`; the card gives `name`, `name_normalized`.
- **stock of M, I** = `machine_items`: `workspace_id W1.id`, `machine_id M.id`, `item_id I.id`, `req_qty None`, `defective_qty None`; the card gives `qty`.
- **bulk(n)** = n items named `P00000`, `P00001`, … (`name_normalized` the same in lower case) and n rows stock of M1, one per item, `qty 1`, by `add_all`.
- **entry of M, I** = `machine_item_ledger`: `workspace_id W1.id`, `machine_id M.id`, `item_id I.id`, `transaction_type "manual_add"`, `quantity 10`, `unit_cost Decimal("0.00")`, `total_cost Decimal("0.00")`, `qty_before 0`, `qty_after 10`, `value_before None`, `value_after None`, `avg_price_before None`, `source_type "manual"`, `performed_by U1.id`; the card gives `performed_at`, `avg_price_after`.
- **activity row of M** = `machine_activity_events`: `workspace_id W1.id`, `machine_id M.id`, `event_type "item_added"`, `description "seed"`, `performed_by U1.id`.
- **work order of M** = `work_orders`: `workspace_id W1.id`, `work_order_number` = `"WO-"` + Given name, `work_order_type_id WT1.id`, `title "Service"`, `factory_id F1.id`, `machine_id M.id`, `is_deleted False`; the card gives `status`.
- **source line of O** = `work_order_items`: `workspace_id W1.id`, `work_order_id O.id`, `item_id I1.id`, `quantity 2`, `uses_inventory True`, `consumed_at None`, `source_location_type "machine"`, `source_location_id M1.id`, `replaced_item_id None`, `is_deleted False`.
- **replace line of O** = `work_order_items`: `workspace_id W1.id`, `work_order_id O.id`, `item_id I2.id`, `quantity 1`, `action_type "REPLACE"`, `replaced_item_id I1.id`, `uses_inventory True`, `consumed_at None`, `is_deleted False`.
- **transfer out of M1** = `transfer_orders`: `workspace_id W1.id`, `transfer_number` = `"TR-"` + Given name, `source_location_type "machine"`, `source_location_id M1.id`, `destination_location_type "storage"`, `destination_location_id F1.id`, `current_status_id STD.id`, `created_by U1.id`, `completed_at None`. **TO line of T** = `transfer_order_items`: `workspace_id W1.id`, `transfer_order_id T.id`, `line_number 1`, `item_id I1.id`, `quantity 3`.
- **delivered PO to M1** = `purchase_orders`: `workspace_id W1.id`, `po_number` = `"PO-"` + Given name, `destination_type "machine"`, `destination_id M1.id`, `current_status_id STC.id`, `created_by U1.id`, `voided False`. **PO line of P** = `purchase_order_items`: `workspace_id W1.id`, `purchase_order_id P.id`, `line_number 1`, `item_id I1.id`, `quantity_ordered 5`.
- **return of P** = `purchase_order_returns`: `workspace_id W1.id`, `purchase_order_id P.id`, `return_number` = `"PR-"` + Given name, `created_by U1.id`, `status "pending"`. **return line of R, L** (L a PO line) = `purchase_order_return_items`: `workspace_id W1.id`, `return_id R.id`, `po_item_id L.id`, `item_id I1.id`, `quantity_returned 2`.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id; values are database values. "the returned row" = by `result.id`.
- **unchanged(X)** = after re-read, every column of X equals its value before the call. Snapshot after the last Given line, after `db.refresh(X)`.
- **nothing written** = the row counts of `machine_items`, `machine_item_ledger`, `machine_activity_events` (all workspaces) equal their values before the call.
- **entries_of(M, I)** = a fresh SELECT of `machine_item_ledger` with that `machine_id` and `item_id`, any workspace, ordered by `id`, as a list. `[-1]` is the entry just written.
- **events_of(M)** = a fresh SELECT of `machine_activity_events` with `machine_id == M.id`, ordered by `id`. "that row" = the one row just counted; "the `X` row" = the one row of it with `event_type == "X"`. `metadata_json` is compared as a whole dict, order of `changes` included.
- **ids(x)** = `sorted(r.id for r in x)`, right-hand ids in Given order. **names(x)** = `[r.item_name for r in x]`, order is part of the check.
- `count:` lines count rows in all workspaces, with the filter stated.
- `raises: HTTPException`, `raises: ValueError`: plain `with pytest.raises(...) as exc:` around the call, no savepoint, because a savepoint's rollback would hide a write. The in-use refusal is read from `exc.value.args`, never `str(exc.value)`; `args[1]` is compared with `==` to the literal list, order included.
- `raises: IntegrityError`, `raises: DataError` (`sqlalchemy.exc`): `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the call. `ForeignKeyViolation` = `psycopg2.errors.ForeignKeyViolation`.
- `raises: ValidationError` = `pydantic.ValidationError` around the schema's construction. Further `raises:` lines are assertions on `exc.value` after the block, one per line.
- `session:` lines run on `db` directly, before any re-read: one `assert` each; "`db.flush()` runs and raises nothing" is the bare call.
- `statement:` lines are checks on `sql_log`.

**Targets.** "target `schema`" = the When only builds the schema object.

**Rolled back.** `sp = db.begin_nested()` directly before the call and a spy wrapping `db.commit` (still callable, records calls). The first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks. One per writer.

**next_clock_tick().** A test helper that waits until `utcnow()` has moved on, and patches nothing. Two ledger entries written with the real clock can share `performed_at`, and the latest is then undefined (BUG-664, BUG-641). A Given line naming it runs it at that place.

**sql_log.** A list filled by a `before_cursor_execute` listener on `db.connection()`, started at that Given line, removed after the call. Each entry is the statement text.

**xfail cards.** Write the call and checks as shown, also when a parameter does not exist yet. Strict unless the Expect line says `(non-strict)`: `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False`. No card builds two rows for one workspace + machine + item (BUG-983).

**Race simulations.** MIM-C-25 (`create_machine_item` R8) patches the method `get_by_machine_and_item` on the DAO object `M.machine_item_dao` to return `None`, to put the code in the state "a concurrent request already passed the check". Nothing else may be patched for this.

## `MachineItemManager._item_name`

### MIM-IN-01 — an item of the workspace gives its name
- **Rules:** `_item_name` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1 (standing).

**When**
- `result = M._item_name(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == "Bolt M8"`.

### MIM-IN-02 — a removed item of the workspace gives its name like any other
- **Rules:** `_item_name` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. IX (standing).

**When**
- `result = M._item_name(db, item_id=IX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == "Old Rivet"`.

## `MachineItemManager.get_machine_item`

### MIM-G-01 — a row of the workspace is returned with its item loaded
- **Rules:** `get_machine_item` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.get_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, MachineItem)`.
2. returns: `result.id == MI.id`.
3. returns: `result.machine_id == M1.id`, `result.item_id == I1.id`, `result.workspace_id == W1.id`.
4. returns: `result.qty == 5`, `result.req_qty == 7`, `result.defective_qty == 1`.
5. returns: `result.item_name == "Bolt M8"`, `result.item_unit == "pcs"`.

### MIM-G-02 — positional arguments work, as the service calls it
- **Rules:** `get_machine_item` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `result = M.get_machine_item(db, MI.id, W1.id)`.

**Then**
1. returns: `result.id == MI.id`.

### MIM-G-03 — a row asked for from another workspace gets the same 404
- **Rules:** `get_machine_item` R2, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `M.get_machine_item(db, machine_item_id=MI.id, workspace_id=W2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. unchanged: unchanged(MI).
5. nothing written: nothing written.

### MIM-G-04 — an unknown id gets the same 404
- **Rules:** `get_machine_item` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `M.get_machine_item(db, machine_item_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. unchanged: unchanged(MI).
5. nothing written: nothing written.

### MIM-G-05 — id 0 gets the same 404
- **Rules:** `get_machine_item` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `M.get_machine_item(db, machine_item_id=0, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. unchanged: unchanged(MI).
5. nothing written: nothing written.

### MIM-G-06 — a row of a soft-deleted machine is hidden: 404
- **Rules:** `get_machine_item` R3 [BUG-1077], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1077
- **Fails today on:** Then 1 (no error is raised: the parents are not read and the row is returned)

**Given**
1. MI = stock of MX, I1, `qty 5`.

**When**
- `M.get_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. unchanged: unchanged(MI).
5. nothing written: nothing written.

### MIM-G-07 — include_deleted=True returns a row of a soft-deleted machine
- **Rules:** `get_machine_item` R3a [BUG-1077]
- **Kind:** bug
- **Expect:** xfail BUG-1077
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. MI = stock of MX, I1, `qty 5`.

**When**
- `result = M.get_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == MI.id`.
2. returns: `result.qty == 5`.
3. unchanged: unchanged(MI).
4. nothing written: nothing written.

### MIM-G-08 — a row of a live machine in a soft-deleted factory is hidden: 404
- **Rules:** `get_machine_item` R3 [BUG-1077], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1077
- **Fails today on:** Then 1 (no error is raised: the parents are not read and the row is returned)

**Given**
1. MI = stock of MF, I1, `qty 5`.

**When**
- `M.get_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. unchanged: unchanged(MI).
5. nothing written: nothing written.

### MIM-G-09 — include_deleted=True returns a row of a live machine in a soft-deleted factory
- **Rules:** `get_machine_item` R3a [BUG-1077]
- **Kind:** bug
- **Expect:** xfail BUG-1077
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. MI = stock of MF, I1, `qty 5`.

**When**
- `result = M.get_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == MI.id`.
2. returns: `result.qty == 5`.
3. unchanged: unchanged(MI).
4. nothing written: nothing written.

### MIM-G-10 — a row of a removed item is hidden: 404
- **Rules:** `get_machine_item` R3 [BUG-1077], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1077
- **Fails today on:** Then 1 (no error is raised: the parents are not read and the row is returned)

**Given**
1. MI = stock of M1, IX, `qty 5`.

**When**
- `M.get_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. unchanged: unchanged(MI).
5. nothing written: nothing written.

### MIM-G-11 — include_deleted=True returns a row of a removed item
- **Rules:** `get_machine_item` R3a [BUG-1077]
- **Kind:** bug
- **Expect:** xfail BUG-1077
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. MI = stock of M1, IX, `qty 5`.

**When**
- `result = M.get_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == MI.id`.
2. returns: `result.qty == 5`.
3. unchanged: unchanged(MI).
4. nothing written: nothing written.

### MIM-G-12 — include_deleted=True returns a row with live parents too
- **Rules:** `get_machine_item` R3a [BUG-1077]
- **Kind:** bug
- **Expect:** xfail BUG-1077
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `result = M.get_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == MI.id`.

### MIM-G-13 — include_deleted=True does not open a row of another workspace
- **Rules:** `get_machine_item` R2, R3a [BUG-1077], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1077
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. MI = stock of MX, I1, `qty 5`.

**When**
- `M.get_machine_item(db, machine_item_id=MI.id, workspace_id=W2.id, include_deleted=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. nothing written: nothing written.

### MIM-G-14 — include_deleted=True on an unknown id is still 404
- **Rules:** `get_machine_item` R2, R3a [BUG-1077], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1077
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. No stock rows exist.

**When**
- `M.get_machine_item(db, machine_item_id=MISSING, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. nothing written: nothing written.

### MIM-G-15 — an inactive-but-live machine hides nothing
- **Rules:** `get_machine_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of MA, I1, `qty 5`.

**When**
- `result = M.get_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == MI.id`.
2. returns: `result.item_name == "Bolt M8"`.

### MIM-G-16 — a machine in an inactive-but-live factory hides nothing
- **Rules:** `get_machine_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of MN, I1, `qty 5`.

**When**
- `result = M.get_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == MI.id`.
2. returns: `result.item_name == "Bolt M8"`.

### MIM-G-17 — the read writes nothing
- **Rules:** `get_machine_item` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`.

**When**
- `result = M.get_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == MI.id`.
2. session: `MI not in db.dirty`.
3. unchanged: unchanged(MI).
4. nothing written: nothing written.

### MIM-G-18 — a stored row with another workspace's item is not found
- **Rules:** `get_machine_item` R6 [BUG-1086], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1086
- **Fails today on:** Then 1 (no error is raised: the row is returned and shows the other workspace's item)

**Given**
1. MI = stock of M1, I9, `qty 5`. (A row of W1 with an item of W2, invalid data.)

**When**
- `M.get_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. unchanged: unchanged(MI).
5. nothing written: nothing written.

### MIM-G-19 — a stored row with another workspace's item is not found with include_deleted=True either
- **Rules:** `get_machine_item` R6 [BUG-1086], R3a [BUG-1077], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1086
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. MI = stock of M1, I9, `qty 5`. (A row of W1 with an item of W2, invalid data.)

**When**
- `M.get_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. unchanged: unchanged(MI).

### MIM-G-20 — a stored row with another workspace's item is not found from the item's workspace
- **Rules:** `get_machine_item` R2, R6, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I9, `qty 5`. (A row of W1 with an item of W2, invalid data.)

**When**
- `M.get_machine_item(db, machine_item_id=MI.id, workspace_id=W2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. unchanged: unchanged(MI).

## `MachineItemManager.list_machine_items`

### MIM-L-01 — with a machine_id: only that machine's rows, each with its item loaded
- **Rules:** `list_machine_items` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock of M1, I1, `qty 5`.
2. B = stock of M1, I2, `qty 2`.
3. C = stock of M2, I1, `qty 9`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id, B.id]`.
3. returns: `sorted(r.item_name for r in result) == ["Bolt M8", "Washer Ten"]`.
4. returns: `sorted(r.item_unit for r in result) == ["pcs", "pcs"]`.

### MIM-L-02 — with a machine_id: rows come in item-name order, case-insensitive
- **Rules:** `list_machine_items` R1 [BUG-976]
- **Kind:** bug
- **Expect:** xfail BUG-976 (non-strict)
- **Fails today on:** Then 1 (no ordering is requested; the order is whatever the database produces)

**Given**
1. IZ = item, `name "Zulu"`, `name_normalized "zulu"`.
2. IA = item, `name "apple"`, `name_normalized "apple"`.
3. IB = item, `name "Banana"`, `name_normalized "banana"`.
4. stock of M1, IZ, `qty 1`.
5. stock of M1, IA, `qty 1`.
6. stock of M1, IB, `qty 1`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `names(result) == ["apple", "Banana", "Zulu"]`.

### MIM-L-03 — with a machine_id: a soft-deleted machine gives an empty list
- **Rules:** `list_machine_items` R1 [BUG-979]
- **Kind:** bug
- **Expect:** xfail BUG-979
- **Fails today on:** Then 1 (the rows of the deleted machine are returned)

**Given**
1. A = stock of MX, I1, `qty 5`.
2. B = stock of M1, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=MX.id)`.

**Then**
1. returns: `result == []`.
2. unchanged: unchanged(A).

### MIM-L-04 — with a machine_id: a machine in a soft-deleted factory gives an empty list
- **Rules:** `list_machine_items` R1 [BUG-979]
- **Kind:** bug
- **Expect:** xfail BUG-979
- **Fails today on:** Then 1 (the rows of the machine are returned)

**Given**
1. A = stock of MF, I1, `qty 5`.
2. B = stock of M1, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=MF.id)`.

**Then**
1. returns: `result == []`.
2. unchanged: unchanged(A).

### MIM-L-05 — with a machine_id: a removed item's row is left out, the others stay
- **Rules:** `list_machine_items` R1 [BUG-980]
- **Kind:** bug
- **Expect:** xfail BUG-980
- **Fails today on:** Then 1 (the removed item's row is returned)

**Given**
1. A = stock of M1, IX, `qty 5`.
2. B = stock of M1, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.
2. unchanged: unchanged(A).

### MIM-L-06 — a machine_id of another workspace returns an empty list
- **Rules:** `list_machine_items` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock of M1, I1, `qty 5`.
2. B = stock of M9, I1, `qty 5`, but `workspace_id W2.id`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=M9.id)`.

**Then**
1. returns: `result == []`.

### MIM-L-07 — a machine_id unknown returns an empty list
- **Rules:** `list_machine_items` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock of M1, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=MISSING)`.

**Then**
1. returns: `result == []`.

### MIM-L-08 — a machine_id negative returns an empty list
- **Rules:** `list_machine_items` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock of M1, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=-1)`.

**Then**
1. returns: `result == []`.

### MIM-L-09 — a machine_id of a machine with no rows returns an empty list
- **Rules:** `list_machine_items` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock of M1, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=M2.id)`.

**Then**
1. returns: `result == []`.

### MIM-L-10 — machine_id 0 filters like any integer
- **Rules:** `list_machine_items` R3 [BUG-1074]
- **Kind:** bug
- **Expect:** xfail BUG-1074
- **Fails today on:** Then 1 (0 counts as no filter: every row of the workspace is returned)

**Given**
1. A = stock of M1, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=0)`.

**Then**
1. returns: `result == []`.

### MIM-L-11 — machine_id None lists the whole workspace
- **Rules:** `list_machine_items` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock of M1, I1, `qty 5`.
2. B = stock of M2, I1, `qty 2`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=None)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### MIM-L-12 — without a machine_id: only rows of that workspace
- **Rules:** `list_machine_items` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock of M1, I1, `qty 5`.
2. B = stock of M9, I1, `qty 5`, but `workspace_id W2.id`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MIM-L-13 — without a machine_id: an unknown workspace gives an empty list
- **Rules:** `list_machine_items` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock of M1, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### MIM-L-14 — without a machine_id: an empty workspace gives an empty list
- **Rules:** `list_machine_items` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock of M1, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### MIM-L-15 — with a machine_id: limit 2 of 3 rows gives 2
- **Rules:** `list_machine_items` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. stock of M1, I1, `qty 1`.
2. stock of M1, I2, `qty 1`.
3. stock of M1, I3, `qty 1`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=M1.id, limit=2)`.

**Then**
1. returns: `len(result) == 2`.

### MIM-L-16 — with a machine_id: skip 1 of 3 rows gives 2
- **Rules:** `list_machine_items` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. stock of M1, I1, `qty 1`.
2. stock of M1, I2, `qty 1`.
3. stock of M1, I3, `qty 1`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=M1.id, skip=1)`.

**Then**
1. returns: `len(result) == 2`.

### MIM-L-17 — with a machine_id: by default 101 rows give exactly 100
- **Rules:** `list_machine_items` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(101).

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `len(result) == 100`.

### MIM-L-18 — with a machine_id: by default 100 rows give all 100
- **Rules:** `list_machine_items` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(100).

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `len(result) == 100`.

### MIM-L-19 — with a machine_id: limit 101 over 101 rows gives 101
- **Rules:** `list_machine_items` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(101).

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=M1.id, limit=101)`.

**Then**
1. returns: `len(result) == 101`.

### MIM-L-20 — with a machine_id: limit 0 gives an empty list
- **Rules:** `list_machine_items` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. stock of M1, I1, `qty 1`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=M1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MIM-L-21 — with a machine_id: skip exactly at the end gives an empty list
- **Rules:** `list_machine_items` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. stock of M1, I1, `qty 1`.
2. stock of M1, I2, `qty 1`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=M1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### MIM-L-22 — with a machine_id: skip one short of the end gives the last row
- **Rules:** `list_machine_items` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. stock of M1, I1, `qty 1`.
2. stock of M1, I2, `qty 1`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=M1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.

### MIM-L-23 — with a machine_id: skip past the end gives an empty list
- **Rules:** `list_machine_items` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. stock of M1, I1, `qty 1`.
2. stock of M1, I2, `qty 1`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=M1.id, skip=3)`.

**Then**
1. returns: `result == []`.

### MIM-L-24 — with a machine_id: consecutive windows partition the rows
- **Rules:** `list_machine_items` R5 [BUG-976]
- **Kind:** bug
- **Expect:** xfail BUG-976 (non-strict)
- **Fails today on:** Then 1 (no ordering is requested, so two windows can repeat or miss a row)

**Given**
1. A = stock of M1, I1, `qty 1`.
2. B = stock of M1, I2, `qty 1`.
3. C = stock of M1, I3, `qty 1`.
4. `win1 = M.list_machine_items(db, workspace_id=W1.id, machine_id=M1.id, skip=0, limit=2)`.
5. `A.qty = 7`, `db.flush()` (the update moves A's row, so an unordered query may change its order).

**When**
- `win2 = M.list_machine_items(db, workspace_id=W1.id, machine_id=M1.id, skip=2, limit=2)`.

**Then**
1. returns: `sorted([r.id for r in win1] + [r.id for r in win2]) == [A.id, B.id, C.id]`.

### MIM-L-25 — with a machine_id: a negative limit is rejected by the database
- **Rules:** `list_machine_items` R6, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. stock of M1, I1, `qty 1`.

**When**
- `M.list_machine_items(db, workspace_id=W1.id, machine_id=M1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)` (contains).
4. nothing written: nothing written.

### MIM-L-26 — with a machine_id: a negative skip is rejected by the database
- **Rules:** `list_machine_items` R6, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. stock of M1, I1, `qty 1`.

**When**
- `M.list_machine_items(db, workspace_id=W1.id, machine_id=M1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)` (contains).
4. nothing written: nothing written.

### MIM-L-27 — without a machine_id: limit 2 of 3 rows gives 2
- **Rules:** `list_machine_items` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. stock of M1, I1, `qty 1`.
2. stock of M1, I2, `qty 1`.
3. stock of M1, I3, `qty 1`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `len(result) == 2`.

### MIM-L-28 — without a machine_id: skip 1 of 3 rows gives 2
- **Rules:** `list_machine_items` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. stock of M1, I1, `qty 1`.
2. stock of M1, I2, `qty 1`.
3. stock of M1, I3, `qty 1`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 2`.

### MIM-L-29 — without a machine_id: by default 101 rows give exactly 100
- **Rules:** `list_machine_items` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(101).

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### MIM-L-30 — without a machine_id: by default 100 rows give all 100
- **Rules:** `list_machine_items` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(100).

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### MIM-L-31 — without a machine_id: limit 101 over 101 rows gives 101
- **Rules:** `list_machine_items` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(101).

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, limit=101)`.

**Then**
1. returns: `len(result) == 101`.

### MIM-L-32 — without a machine_id: limit 0 gives an empty list
- **Rules:** `list_machine_items` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. stock of M1, I1, `qty 1`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MIM-L-33 — without a machine_id: skip exactly at the end gives an empty list
- **Rules:** `list_machine_items` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. stock of M1, I1, `qty 1`.
2. stock of M1, I2, `qty 1`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### MIM-L-34 — without a machine_id: skip one short of the end gives the last row
- **Rules:** `list_machine_items` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. stock of M1, I1, `qty 1`.
2. stock of M1, I2, `qty 1`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.

### MIM-L-35 — without a machine_id: skip past the end gives an empty list
- **Rules:** `list_machine_items` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. stock of M1, I1, `qty 1`.
2. stock of M1, I2, `qty 1`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, skip=3)`.

**Then**
1. returns: `result == []`.

### MIM-L-36 — without a machine_id: consecutive windows partition the rows
- **Rules:** `list_machine_items` R5 [BUG-1071]
- **Kind:** bug
- **Expect:** xfail BUG-1071 (non-strict)
- **Fails today on:** Then 1 (no ordering is requested, so two windows can repeat or miss a row)

**Given**
1. A = stock of M1, I1, `qty 1`.
2. B = stock of M1, I2, `qty 1`.
3. C = stock of M1, I3, `qty 1`.
4. `win1 = M.list_machine_items(db, workspace_id=W1.id, skip=0, limit=2)`.
5. `A.qty = 7`, `db.flush()` (the update moves A's row, so an unordered query may change its order).

**When**
- `win2 = M.list_machine_items(db, workspace_id=W1.id, skip=2, limit=2)`.

**Then**
1. returns: `sorted([r.id for r in win1] + [r.id for r in win2]) == [A.id, B.id, C.id]`.

### MIM-L-37 — without a machine_id: a negative limit is rejected by the database
- **Rules:** `list_machine_items` R6, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. stock of M1, I1, `qty 1`.

**When**
- `M.list_machine_items(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)` (contains).
4. nothing written: nothing written.

### MIM-L-38 — without a machine_id: a negative skip is rejected by the database
- **Rules:** `list_machine_items` R6, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. stock of M1, I1, `qty 1`.

**When**
- `M.list_machine_items(db, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)` (contains).
4. nothing written: nothing written.

### MIM-L-39 — without a machine_id: a row of a soft-deleted machine is left out
- **Rules:** `list_machine_items` R7 [BUG-1070]
- **Kind:** bug
- **Expect:** xfail BUG-1070
- **Fails today on:** Then 1 (every row of the workspace is returned)

**Given**
1. A = stock of MX, I1, `qty 5`.
2. B = stock of M2, I2, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.
2. unchanged: unchanged(A).

### MIM-L-40 — without a machine_id: rows of a soft-deleted machine take no place in the page
- **Rules:** `list_machine_items` R7 [BUG-1070]
- **Kind:** bug
- **Expect:** xfail BUG-1070
- **Fails today on:** Then 1 (hidden rows are counted: two rows come back whichever the database picks)

**Given**
1. A = stock of MX, I1, `qty 5`.
2. A2 = stock of MX, I2, `qty 5`.
3. B = stock of M2, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MIM-L-41 — without a machine_id: a row of a machine in a soft-deleted factory is left out
- **Rules:** `list_machine_items` R7 [BUG-1070]
- **Kind:** bug
- **Expect:** xfail BUG-1070
- **Fails today on:** Then 1 (every row of the workspace is returned)

**Given**
1. A = stock of MF, I1, `qty 5`.
2. B = stock of M2, I2, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.
2. unchanged: unchanged(A).

### MIM-L-42 — without a machine_id: rows of a machine in a soft-deleted factory take no place in the page
- **Rules:** `list_machine_items` R7 [BUG-1070]
- **Kind:** bug
- **Expect:** xfail BUG-1070
- **Fails today on:** Then 1 (hidden rows are counted: two rows come back whichever the database picks)

**Given**
1. A = stock of MF, I1, `qty 5`.
2. A2 = stock of MF, I2, `qty 5`.
3. B = stock of M2, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MIM-L-43 — without a machine_id: a row of a removed item is left out
- **Rules:** `list_machine_items` R7 [BUG-1070]
- **Kind:** bug
- **Expect:** xfail BUG-1070
- **Fails today on:** Then 1 (every row of the workspace is returned)

**Given**
1. A = stock of M1, IX, `qty 5`.
2. B = stock of M2, I2, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.
2. unchanged: unchanged(A).

### MIM-L-44 — without a machine_id: rows of a removed item take no place in the page
- **Rules:** `list_machine_items` R7 [BUG-1070]
- **Kind:** bug
- **Expect:** xfail BUG-1070
- **Fails today on:** Then 1 (hidden rows are counted: two rows come back whichever the database picks)

**Given**
1. A = stock of M1, IX, `qty 5`.
2. A2 = stock of M1, IX2, `qty 5`.
3. B = stock of M2, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MIM-L-45 — without a machine_id: a hidden row does not use up the skip
- **Rules:** `list_machine_items` R7 [BUG-1070]
- **Kind:** bug
- **Expect:** xfail BUG-1070
- **Fails today on:** Then 1 (the hidden row counts, so two rows come back)

**Given**
1. A = stock of M1, IX, `qty 5`.
2. B = stock of M2, I1, `qty 5`.
3. C = stock of M2, I2, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.

### MIM-L-46 — without a machine_id: Anvil removed and Bolt active, limit 1 returns Bolt
- **Rules:** `list_machine_items` R7 [BUG-1070]
- **Kind:** bug
- **Expect:** xfail BUG-1070 (non-strict)
- **Fails today on:** Then 1 (the removed item's row takes the place, when the database reads it first)

**Given**
1. IAN = item, `name "Anvil"`, `name_normalized "anvil"`, `is_active False`.
2. IBO = item, `name "Bolt"`, `name_normalized "bolt"`.
3. A = stock of M1, IAN, `qty 5`.
4. B = stock of M1, IBO, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `names(result) == ["Bolt"]`.

### MIM-L-47 — without a machine_id: an inactive-but-live machine hides nothing
- **Rules:** `list_machine_items` R7a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock of MA, I1, `qty 5`.
2. B = stock of M2, I2, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### MIM-L-48 — with a machine_id: an inactive-but-live machine hides nothing
- **Rules:** `list_machine_items` R1, R7a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock of MA, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=MA.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MIM-L-49 — without a machine_id: a machine in an inactive-but-live factory hides nothing
- **Rules:** `list_machine_items` R7a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock of MN, I1, `qty 5`.
2. B = stock of M2, I2, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### MIM-L-50 — with a machine_id: a machine in an inactive-but-live factory hides nothing
- **Rules:** `list_machine_items` R1, R7a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock of MN, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=MN.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MIM-L-51 — listing changes nothing on hidden rows and parents
- **Rules:** `list_machine_items` R7a, R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock of MX, I1, `qty 5`.
2. B = stock of M1, IX, `qty 5`.
3. C = stock of MF, I2, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. session: `A not in db.dirty`.
3. unchanged: unchanged(A).
4. unchanged: unchanged(B).
5. unchanged: unchanged(C).
6. unchanged: unchanged(MX).
7. unchanged: unchanged(IX).
8. unchanged: unchanged(FD).
9. nothing written: nothing written.

### MIM-L-52 — a machine made live again brings its row back unchanged
- **Rules:** `list_machine_items` R7a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock of MX, I1, `qty 5`, but `req_qty 7`.
2. `MX.is_deleted = False`, `MX.is_active = True`, `db.flush()`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].qty == 5`, `result[0].req_qty == 7`.

### MIM-L-53 — a factory made live again brings its row back unchanged
- **Rules:** `list_machine_items` R7a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock of MF, I1, `qty 5`, but `req_qty 7`.
2. `FD.is_deleted = False`, `db.flush()`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].qty == 5`, `result[0].req_qty == 7`.

### MIM-L-54 — an item made active again brings its row back unchanged
- **Rules:** `list_machine_items` R7a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock of M1, IX, `qty 5`, but `req_qty 7`.
2. `IX.is_active = True`, `db.flush()`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].qty == 5`, `result[0].req_qty == 7`.

### MIM-L-55 — without a machine_id: rows come in item-name order, case-insensitive
- **Rules:** `list_machine_items` R8 [BUG-1071]
- **Kind:** bug
- **Expect:** xfail BUG-1071 (non-strict)
- **Fails today on:** Then 1 (no ordering is requested; the order is whatever the database produces)

**Given**
1. IZ = item, `name "Zulu"`, `name_normalized "zulu"`.
2. IA = item, `name "apple"`, `name_normalized "apple"`.
3. IB = item, `name "Banana"`, `name_normalized "banana"`.
4. stock of M1, IZ, `qty 1`.
5. stock of M1, IA, `qty 1`.
6. stock of M2, IB, `qty 1`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id)`.

**Then**
1. returns: `names(result) == ["apple", "Banana", "Zulu"]`.

### MIM-L-56 — without a machine_id: the order is applied before limit
- **Rules:** `list_machine_items` R8 [BUG-1071]
- **Kind:** bug
- **Expect:** xfail BUG-1071 (non-strict)
- **Fails today on:** Then 1 (no ordering is requested; the order is whatever the database produces)

**Given**
1. IZ = item, `name "Zulu"`, `name_normalized "zulu"`.
2. IA = item, `name "apple"`, `name_normalized "apple"`.
3. IB = item, `name "Banana"`, `name_normalized "banana"`.
4. stock of M1, IZ, `qty 1`.
5. stock of M1, IA, `qty 1`.
6. stock of M2, IB, `qty 1`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `names(result) == ["apple"]`.

### MIM-L-57 — without a machine_id: the order is applied before skip
- **Rules:** `list_machine_items` R8 [BUG-1071]
- **Kind:** bug
- **Expect:** xfail BUG-1071 (non-strict)
- **Fails today on:** Then 1 (no ordering is requested; the order is whatever the database produces)

**Given**
1. IZ = item, `name "Zulu"`, `name_normalized "zulu"`.
2. IA = item, `name "apple"`, `name_normalized "apple"`.
3. IB = item, `name "Banana"`, `name_normalized "banana"`.
4. stock of M1, IZ, `qty 1`.
5. stock of M1, IA, `qty 1`.
6. stock of M2, IB, `qty 1`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `names(result) == ["Zulu"]`.

### MIM-L-58 — without a machine_id: equal names in different case come lower row id first
- **Rules:** `list_machine_items` R8 [BUG-1071]
- **Kind:** bug
- **Expect:** xfail BUG-1071 (non-strict)
- **Fails today on:** Then 1 (no ordering is requested; the order is whatever the database produces)

**Given**
1. IU = item, `name "Bolt"`, `name_normalized "bolt one"`.
2. IL = item, `name "bolt"`, `name_normalized "bolt two"`.
3. A = stock of M1, IL, `qty 1`.
4. B = stock of M1, IU, `qty 1`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [A.id, B.id]`.

### MIM-L-59 — without a machine_id: the query asks for an ORDER BY
- **Rules:** `list_machine_items` R8 [BUG-1071]
- **Kind:** bug
- **Expect:** xfail BUG-1071
- **Fails today on:** Then 2 (the query has no ORDER BY)

**Given**
1. stock of M1, I1, `qty 1`.
2. sql_log.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. statement: `any("ORDER BY" in s for s in sql_log if "FROM machine_items" in s)`.

### MIM-L-60 — with a machine_id: a stored row with another workspace's item is left out
- **Rules:** `list_machine_items` R9 [BUG-1086]
- **Kind:** bug
- **Expect:** xfail BUG-1086
- **Fails today on:** Then 1 (the row is listed with the other workspace's item)

**Given**
1. A = stock of M1, I9, `qty 5`. (A row of W1 with an item of W2, invalid data.)
2. B = stock of M1, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.
2. unchanged: unchanged(A).

### MIM-L-61 — with a machine_id: stored rows with another workspace's item take no place in the page
- **Rules:** `list_machine_items` R9 [BUG-1086]
- **Kind:** bug
- **Expect:** xfail BUG-1086
- **Fails today on:** Then 1 (the two invalid rows are counted: two rows come back whichever the database picks)

**Given**
1. A = stock of M1, I9, `qty 5`.
2. A2 = stock of M1, I92, `qty 5`.
3. B = stock of M1, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=M1.id, limit=2)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MIM-L-62 — with a machine_id: rows come back whatever their quantities
- **Rules:** `list_machine_items` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock of M1, I1, `qty 0`.
2. B = stock of M1, I2, `qty -3`.
3. C = stock of M1, I3, `qty 2`, but `req_qty 0`, `defective_qty 0`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id, C.id]`.

### MIM-L-63 — without a machine_id: a stored row with another workspace's item is left out
- **Rules:** `list_machine_items` R9 [BUG-1086]
- **Kind:** bug
- **Expect:** xfail BUG-1086
- **Fails today on:** Then 1 (the row is listed with the other workspace's item)

**Given**
1. A = stock of M1, I9, `qty 5`. (A row of W1 with an item of W2, invalid data.)
2. B = stock of M1, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.
2. unchanged: unchanged(A).

### MIM-L-64 — without a machine_id: stored rows with another workspace's item take no place in the page
- **Rules:** `list_machine_items` R9 [BUG-1086]
- **Kind:** bug
- **Expect:** xfail BUG-1086
- **Fails today on:** Then 1 (the two invalid rows are counted: two rows come back whichever the database picks)

**Given**
1. A = stock of M1, I9, `qty 5`.
2. A2 = stock of M1, I92, `qty 5`.
3. B = stock of M1, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MIM-L-65 — without a machine_id: rows come back whatever their quantities
- **Rules:** `list_machine_items` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock of M1, I1, `qty 0`.
2. B = stock of M1, I2, `qty -3`.
3. C = stock of M1, I3, `qty 2`, but `req_qty 0`, `defective_qty 0`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id, C.id]`.

### MIM-L-66 — with a machine_id: the read writes nothing
- **Rules:** `list_machine_items` R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock of M1, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. session: `A not in db.dirty`.
3. unchanged: unchanged(A).
4. nothing written: nothing written.

### MIM-L-67 — without a machine_id: rows of a soft-deleted machine that sort first take no place in the page
- **Rules:** `list_machine_items` R7 [BUG-1070]
- **Kind:** bug
- **Expect:** xfail BUG-1070
- **Fails today on:** Then 1 (the hidden rows are counted: two rows come back whichever the database picks)

**Given**
1. IA1 = item, `name "Aaa1"`, `name_normalized "aaa1"`.
2. IA2 = item, `name "Aaa2"`, `name_normalized "aaa2"`.
3. A = stock of MX, IA1, `qty 5`.
4. A2 = stock of MX, IA2, `qty 5`.
5. B = stock of M2, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MIM-L-68 — without a machine_id: rows of a machine in a soft-deleted factory that sort first take no place in the page
- **Rules:** `list_machine_items` R7 [BUG-1070]
- **Kind:** bug
- **Expect:** xfail BUG-1070
- **Fails today on:** Then 1 (the hidden rows are counted: two rows come back whichever the database picks)

**Given**
1. IA1 = item, `name "Aaa1"`, `name_normalized "aaa1"`.
2. IA2 = item, `name "Aaa2"`, `name_normalized "aaa2"`.
3. A = stock of MF, IA1, `qty 5`.
4. A2 = stock of MF, IA2, `qty 5`.
5. B = stock of M2, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MIM-L-69 — with a machine_id: stored rows with another workspace's item that sort first take no place in the page
- **Rules:** `list_machine_items` R9 [BUG-1086]
- **Kind:** bug
- **Expect:** xfail BUG-1086
- **Fails today on:** Then 1 (the two invalid rows are counted: two rows come back whichever the database picks)

**Given**
1. IA1 = item, `name "Aaa1"`, `name_normalized "aaa1"`, but `workspace_id W2.id`.
2. IA2 = item, `name "Aaa2"`, `name_normalized "aaa2"`, but `workspace_id W2.id`.
3. A = stock of M1, IA1, `qty 5`. (A row of W1 with an item of W2, invalid data.)
4. A2 = stock of M1, IA2, `qty 5`.
5. B = stock of M1, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, machine_id=M1.id, limit=2)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MIM-L-70 — without a machine_id: stored rows with another workspace's item that sort first take no place in the page
- **Rules:** `list_machine_items` R9 [BUG-1086]
- **Kind:** bug
- **Expect:** xfail BUG-1086
- **Fails today on:** Then 1 (the two invalid rows are counted: two rows come back whichever the database picks)

**Given**
1. IA1 = item, `name "Aaa1"`, `name_normalized "aaa1"`, but `workspace_id W2.id`.
2. IA2 = item, `name "Aaa2"`, `name_normalized "aaa2"`, but `workspace_id W2.id`.
3. A = stock of M1, IA1, `qty 5`. (A row of W1 with an item of W2, invalid data.)
4. A2 = stock of M1, IA2, `qty 5`.
5. B = stock of M1, I1, `qty 5`.

**When**
- `result = M.list_machine_items(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `ids(result) == [B.id]`.

## `MachineItemManager._write_ledger_entry`

### MIM-W-01 — one ledger row is written with the arguments as given
- **Rules:** `_write_ledger_entry` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. No ledger rows exist.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. count: `entries_of(M1, I1)` has exactly 1 row.
3. re-read `entries_of(M1, I1)[-1]`: `workspace_id == W1.id`, `machine_id == M1.id`, `item_id == I1.id`.
4. re-read `entries_of(M1, I1)[-1]`: `transaction_type == "inventory_adjustment"`, `quantity == 2`.
5. re-read `entries_of(M1, I1)[-1]`: `qty_before == 10`, `qty_after == 12`.
6. re-read `entries_of(M1, I1)[-1]`: `source_type == "adjustment"`, `notes == "Count fix"`.
7. re-read `entries_of(M1, I1)[-1]`: `performed_by == U2.id`, `performed_at is not None`.

### MIM-W-02 — source_id, order and transfer columns stay empty
- **Rules:** `_write_ledger_entry` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No ledger rows exist.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. re-read `entries_of(M1, I1)[-1]`: `source_id is None`, `order_id is None`, `order_type is None`, `invoice_id is None`.
3. re-read `entries_of(M1, I1)[-1]`: `transfer_source_id is None`, `transfer_destination_id is None`.
4. re-read `entries_of(M1, I1)[-1]`: `transfer_source_type is None`, `transfer_destination_type is None`.

### MIM-W-03 — source_type defaults to "manual"
- **Rules:** `_write_ledger_entry` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No ledger rows exist.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="manual_add", quantity=4, qty_before=0, qty_after=4, user_id=U2.id, notes="Opening")`.

**Then**
1. returns: `result is None`.
2. re-read `entries_of(M1, I1)[-1]`: `source_type == "manual"`, `transaction_type == "manual_add"`.

### MIM-W-04 — the three prices are the current average
- **Rules:** `_write_ledger_entry` R2 [BUG-993]
- **Kind:** bug
- **Expect:** xfail BUG-993
- **Fails today on:** Then 3 (today every cost field is 0.00)

**Given**
1. LG = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("5.00")`, but `qty_after 10`.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. count: `entries_of(M1, I1)` has exactly 2 rows.
3. re-read `entries_of(M1, I1)[-1]`: `unit_cost == Decimal("5.00")`, `avg_price_before == Decimal("5.00")`, `avg_price_after == Decimal("5.00")`.

### MIM-W-05 — the average applies when qty_before is 0
- **Rules:** `_write_ledger_entry` R2 [BUG-993], R3, R4
- **Kind:** bug
- **Expect:** xfail BUG-993
- **Fails today on:** Then 2 (today every cost field is 0.00)

**Given**
1. LG = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("5.00")`, but `qty_after 0`.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=4, qty_before=0, qty_after=4, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. re-read `entries_of(M1, I1)[-1]`: `unit_cost == Decimal("5.00")`, `avg_price_before == Decimal("5.00")`, `avg_price_after == Decimal("5.00")`.
3. re-read `entries_of(M1, I1)[-1]`: `total_cost == Decimal("20.00")`, `value_before == Decimal("0.00")`, `value_after == Decimal("20.00")`.

### MIM-W-06 — total_cost is quantity times the average
- **Rules:** `_write_ledger_entry` R3 [BUG-993]
- **Kind:** bug
- **Expect:** xfail BUG-993
- **Fails today on:** Then 2 (today every cost field is 0.00)

**Given**
1. LG = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("5.00")`, but `qty_after 10`.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. re-read `entries_of(M1, I1)[-1]`: `total_cost == Decimal("10.00")`.

### MIM-W-07 — total_cost uses the size of the quantity
- **Rules:** `_write_ledger_entry` R3 [BUG-993]
- **Kind:** bug
- **Expect:** xfail BUG-993
- **Fails today on:** Then 3 (today every cost field is 0.00)

**Given**
1. LG = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("5.00")`, but `qty_after 10`.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=-2, qty_before=10, qty_after=12, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. re-read `entries_of(M1, I1)[-1]`: `quantity == -2`.
3. re-read `entries_of(M1, I1)[-1]`: `total_cost == Decimal("10.00")`.

### MIM-W-08 — total_cost of 1 at 0.125 rounds half up to 0.13
- **Rules:** `_write_ledger_entry` R3 [BUG-993] [BUG-1040]
- **Kind:** bug
- **Expect:** xfail BUG-1040
- **Fails today on:** Then 2 (today 0.00, BUG-993; half to even would give 0.12)

**Given**
1. LG = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("0.125")`, but `qty_after 1`. Flush it; **do not refresh or expire it**, and keep the variable LG alive to the end of the test.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=1, qty_before=1, qty_after=2, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. re-read `entries_of(M1, I1)[-1]`: `total_cost == Decimal("0.13")`.

### MIM-W-09 — total_cost of 5 at 0.125 rounds the product, not the price
- **Rules:** `_write_ledger_entry` R3 [BUG-993] [BUG-1040]
- **Kind:** bug
- **Expect:** xfail BUG-1040
- **Fails today on:** Then 2 (today 0.00, BUG-993; half to even would give 0.62, a rounded price 0.65)

**Given**
1. LG = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("0.125")`, but `qty_after 1`. Flush it; **do not refresh or expire it**, and keep the variable LG alive to the end of the test.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=5, qty_before=1, qty_after=6, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. re-read `entries_of(M1, I1)[-1]`: `total_cost == Decimal("0.63")`.

### MIM-W-10 — value_before and value_after use the average
- **Rules:** `_write_ledger_entry` R4 [BUG-993]
- **Kind:** bug
- **Expect:** xfail BUG-993
- **Fails today on:** Then 2 (today every cost field is 0.00)

**Given**
1. LG = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("5.00")`, but `qty_after 10`.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. re-read `entries_of(M1, I1)[-1]`: `value_before == Decimal("50.00")`, `value_after == Decimal("60.00")`.

### MIM-W-11 — a stored negative quantity gives a negative value
- **Rules:** `_write_ledger_entry` R4 [BUG-993]
- **Kind:** bug
- **Expect:** xfail BUG-993
- **Fails today on:** Then 2 (today every cost field is 0.00)

**Given**
1. LG = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("5.00")`, but `qty_after 10`.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=5, qty_before=-3, qty_after=2, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. re-read `entries_of(M1, I1)[-1]`: `value_before == Decimal("-15.00")`, `value_after == Decimal("10.00")`.

### MIM-W-12 — no ledger history: all six cost fields are 0.00
- **Rules:** `_write_ledger_entry` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No ledger rows exist.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. re-read `entries_of(M1, I1)[-1]`: `unit_cost == Decimal("0.00")`, `total_cost == Decimal("0.00")`.
3. re-read `entries_of(M1, I1)[-1]`: `value_before == Decimal("0.00")`, `value_after == Decimal("0.00")`.
4. re-read `entries_of(M1, I1)[-1]`: `avg_price_before == Decimal("0.00")`, `avg_price_after == Decimal("0.00")`.

### MIM-W-13 — history of another machine does not count: all six cost fields are 0.00
- **Rules:** `_write_ledger_entry` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. OT = entry of M2, I1, `performed_at T9`, `avg_price_after Decimal("9.00")`.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. re-read `entries_of(M1, I1)[-1]`: `unit_cost == Decimal("0.00")`, `total_cost == Decimal("0.00")`.
3. re-read `entries_of(M1, I1)[-1]`: `value_before == Decimal("0.00")`, `value_after == Decimal("0.00")`.
4. re-read `entries_of(M1, I1)[-1]`: `avg_price_before == Decimal("0.00")`, `avg_price_after == Decimal("0.00")`.
5. unchanged: unchanged(OT).

### MIM-W-14 — history of another item does not count: all six cost fields are 0.00
- **Rules:** `_write_ledger_entry` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. OT = entry of M1, I2, `performed_at T9`, `avg_price_after Decimal("9.00")`.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. re-read `entries_of(M1, I1)[-1]`: `unit_cost == Decimal("0.00")`, `total_cost == Decimal("0.00")`.
3. re-read `entries_of(M1, I1)[-1]`: `value_before == Decimal("0.00")`, `value_after == Decimal("0.00")`.
4. re-read `entries_of(M1, I1)[-1]`: `avg_price_before == Decimal("0.00")`, `avg_price_after == Decimal("0.00")`.
5. unchanged: unchanged(OT).

### MIM-W-15 — history of another workspace does not count: all six cost fields are 0.00
- **Rules:** `_write_ledger_entry` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. OT = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("9.00")`, but `workspace_id W2.id`.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. re-read `entries_of(M1, I1)[-1]`: `unit_cost == Decimal("0.00")`, `total_cost == Decimal("0.00")`.
3. re-read `entries_of(M1, I1)[-1]`: `value_before == Decimal("0.00")`, `value_after == Decimal("0.00")`.
4. re-read `entries_of(M1, I1)[-1]`: `avg_price_before == Decimal("0.00")`, `avg_price_after == Decimal("0.00")`.
5. unchanged: unchanged(OT).

### MIM-W-16 — an empty latest average counts as 0, whatever value_after holds
- **Rules:** `_write_ledger_entry` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. LG = entry of M1, I1, `performed_at T9`, `avg_price_after None`, but `qty_after 10`, `value_after Decimal("50.00")`.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. re-read `entries_of(M1, I1)[-1]`: `unit_cost == Decimal("0.00")`, `total_cost == Decimal("0.00")`.
3. re-read `entries_of(M1, I1)[-1]`: `value_before == Decimal("0.00")`, `value_after == Decimal("0.00")`.
4. re-read `entries_of(M1, I1)[-1]`: `avg_price_before == Decimal("0.00")`, `avg_price_after == Decimal("0.00")`.

### MIM-W-17 — a latest average of 0.00 stays 0.00 even over a non-zero older one
- **Rules:** `_write_ledger_entry` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. L1 = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("5.00")`.
2. L2 = entry of M1, I1, `performed_at T10`, `avg_price_after Decimal("0.00")`.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. re-read `entries_of(M1, I1)[-1]`: `unit_cost == Decimal("0.00")`, `total_cost == Decimal("0.00")`.
3. re-read `entries_of(M1, I1)[-1]`: `value_before == Decimal("0.00")`, `value_after == Decimal("0.00")`.
4. re-read `entries_of(M1, I1)[-1]`: `avg_price_before == Decimal("0.00")`, `avg_price_after == Decimal("0.00")`.
5. unchanged: unchanged(L1).
6. unchanged: unchanged(L2).

### MIM-W-18 — only the latest entry counts, not row order and not a newer entry of another machine
- **Rules:** `_write_ledger_entry` R8 [BUG-993], R2
- **Kind:** bug
- **Expect:** xfail BUG-993
- **Fails today on:** Then 2 (today every cost field is 0.00)

**Given**
1. L1 = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("3.00")`.
2. L2 = entry of M1, I1, `performed_at T11`, `avg_price_after Decimal("5.00")`.
3. L3 = entry of M1, I1, `performed_at T10`, `avg_price_after Decimal("4.00")`.
4. L4 = entry of M2, I1, `performed_at T12`, `avg_price_after Decimal("9.00")`.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. re-read `entries_of(M1, I1)[-1]`: `avg_price_after == Decimal("5.00")`, `unit_cost == Decimal("5.00")`.

### MIM-W-19 — only the latest entry counts, not row order and not a newer entry of another item
- **Rules:** `_write_ledger_entry` R8 [BUG-993], R2
- **Kind:** bug
- **Expect:** xfail BUG-993
- **Fails today on:** Then 2 (today every cost field is 0.00)

**Given**
1. L1 = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("3.00")`.
2. L2 = entry of M1, I1, `performed_at T11`, `avg_price_after Decimal("5.00")`.
3. L3 = entry of M1, I1, `performed_at T10`, `avg_price_after Decimal("4.00")`.
4. L4 = entry of M1, I2, `performed_at T12`, `avg_price_after Decimal("9.00")`.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. re-read `entries_of(M1, I1)[-1]`: `avg_price_after == Decimal("5.00")`, `unit_cost == Decimal("5.00")`.

### MIM-W-20 — only the latest entry counts, not row order and not a newer entry of another workspace
- **Rules:** `_write_ledger_entry` R8 [BUG-993], R2
- **Kind:** bug
- **Expect:** xfail BUG-993
- **Fails today on:** Then 2 (today every cost field is 0.00)

**Given**
1. L1 = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("3.00")`.
2. L2 = entry of M1, I1, `performed_at T11`, `avg_price_after Decimal("5.00")`.
3. L3 = entry of M1, I1, `performed_at T10`, `avg_price_after Decimal("4.00")`.
4. L4 = entry of M1, I1, `performed_at T12`, `avg_price_after Decimal("9.00")`, but `workspace_id W2.id`.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. re-read `entries_of(M1, I1)[-1]`: `avg_price_after == Decimal("5.00")`, `unit_cost == Decimal("5.00")`.

### MIM-W-21 — chain: receive 10 at 5.00, change to 12 by hand, the balance is 12 worth 60.00
- **Rules:** `_write_ledger_entry` R9 [BUG-993], `update_machine_item` R8
- **Kind:** bug
- **Expect:** xfail BUG-993
- **Fails today on:** Then 2 (today (12, 0.00))

**Given**
1. MI = stock of M1, I1, `qty 0`.
2. `_machine_in(db, machine_id=M1.id, item_id=I1.id, qty=10, unit_cost=Decimal("5.00"), transaction_type="transfer_in", source_type="transfer_order", source_id=31, notes="TO-31", workspace_id=W1.id, user_id=U1.id, source_loc_type=None, source_loc_id=None, activity_event_type="transfer_in", activity_description=None)`, then `db.flush()`.
3. `next_clock_tick()`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.qty == 12`.
2. returns: `machine_item_ledger_dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id) == (12, Decimal("60.00"))`.

### MIM-W-22 — chain: after the manual change the unit cost is still 5.00
- **Rules:** `_write_ledger_entry` R9 [BUG-993]
- **Kind:** bug
- **Expect:** xfail BUG-993
- **Fails today on:** Then 2 (today 0.00)

**Given**
1. MI = stock of M1, I1, `qty 0`.
2. `_machine_in(db, machine_id=M1.id, item_id=I1.id, qty=10, unit_cost=Decimal("5.00"), transaction_type="transfer_in", source_type="transfer_order", source_id=31, notes="TO-31", workspace_id=W1.id, user_id=U1.id, source_loc_type=None, source_loc_id=None, activity_event_type="transfer_in", activity_description=None)`, then `db.flush()`.
3. `next_clock_tick()`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.qty == 12`.
2. returns: `get_machine_unit_cost(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id) == Decimal("5.00")`.

### MIM-W-23 — chain: the balance quantity follows the manual change
- **Rules:** `_write_ledger_entry` R9, R1, `update_machine_item` R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 0`.
2. `_machine_in(db, machine_id=M1.id, item_id=I1.id, qty=10, unit_cost=Decimal("5.00"), transaction_type="transfer_in", source_type="transfer_order", source_id=31, notes="TO-31", workspace_id=W1.id, user_id=U1.id, source_loc_type=None, source_loc_id=None, activity_event_type="transfer_in", activity_description=None)`, then `db.flush()`.
3. `next_clock_tick()`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.qty == 12`.
2. returns: `machine_item_ledger_dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)[0] == 12`.

### MIM-W-24 — chain: a consumption after the manual change is priced at 5.00
- **Rules:** `_write_ledger_entry` R9 [BUG-993]
- **Kind:** bug
- **Expect:** xfail BUG-993
- **Fails today on:** Then 1 (today the consumption is priced 0.00)

**Given**
1. MI = stock of M1, I1, `qty 0`.
2. `_machine_in(db, machine_id=M1.id, item_id=I1.id, qty=10, unit_cost=Decimal("5.00"), transaction_type="transfer_in", source_type="transfer_order", source_id=31, notes="TO-31", workspace_id=W1.id, user_id=U1.id, source_loc_type=None, source_loc_id=None, activity_event_type="transfer_in", activity_description=None)`, then `db.flush()`.
3. `next_clock_tick()`.
4. `M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`, then `db.flush()`.
5. `next_clock_tick()`.

**When**
- `result = _machine_out(db, machine_id=M1.id, item_id=I1.id, qty=2, transaction_type="consumption", source_type="work_order", source_id=17, notes="WO-17 line 1", workspace_id=W1.id, user_id=U1.id, dest_type=None, dest_id=None, activity_event_type="consumption", activity_description=None)`.

**Then**
1. returns: `result == Decimal("5.00")`.

### MIM-W-25 — chain: after the consumption the balance is 10 worth 50.00
- **Rules:** `_write_ledger_entry` R9 [BUG-993]
- **Kind:** bug
- **Expect:** xfail BUG-993
- **Fails today on:** Then 2 (today (10, 0.00))

**Given**
1. MI = stock of M1, I1, `qty 0`.
2. `_machine_in(db, machine_id=M1.id, item_id=I1.id, qty=10, unit_cost=Decimal("5.00"), transaction_type="transfer_in", source_type="transfer_order", source_id=31, notes="TO-31", workspace_id=W1.id, user_id=U1.id, source_loc_type=None, source_loc_id=None, activity_event_type="transfer_in", activity_description=None)`, then `db.flush()`.
3. `next_clock_tick()`.
4. `M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`, then `db.flush()`.
5. `next_clock_tick()`.

**When**
- `result = _machine_out(db, machine_id=M1.id, item_id=I1.id, qty=2, transaction_type="consumption", source_type="work_order", source_id=17, notes="WO-17 line 1", workspace_id=W1.id, user_id=U1.id, dest_type=None, dest_id=None, activity_event_type="consumption", activity_description=None)`.

**Then**
1. re-read MI: `qty == 10`.
2. returns: `machine_item_ledger_dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id) == (10, Decimal("50.00"))`.

### MIM-W-26 — an adjustment writes one inventory_adjusted event
- **Rules:** `_write_ledger_entry` R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No ledger rows exist.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. event: events_of(M1) has exactly 1 row.
3. event: that row: `event_type == "inventory_adjusted"`, `description == "Inventory adjusted on Bolt M8: 10 → 12"`.
4. event: that row: `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == M1.id`.
5. event: that row: `metadata_json == {"item_id": I1.id, "item_name": "Bolt M8", "quantity": 2, "changes": [{"field": "qty", "label": "Quantity", "from_value": "10", "to_value": "12"}]}`.

### MIM-W-27 — the adjustment event of a removed item carries its name
- **Rules:** `_write_ledger_entry` R10, `_item_name` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No ledger rows exist.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=IX.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. event: events_of(M1) has exactly 1 row.
3. event: that row: `description == "Inventory adjusted on Old Rivet: 10 → 12"`.

### MIM-W-28 — a manual_add writes the entry and no event
- **Rules:** `_write_ledger_entry` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No ledger rows exist.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="manual_add", quantity=4, qty_before=0, qty_after=4, user_id=U2.id, notes="Opening")`.

**Then**
1. returns: `result is None`.
2. count: `entries_of(M1, I1)` has exactly 1 row.
3. event: events_of(M1) has exactly 0 rows.

### MIM-W-29 — an unknown user is a foreign key error (manual_add)
- **Rules:** `_write_ledger_entry` R12, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No ledger rows exist.

**When**
- `M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="manual_add", quantity=2, qty_before=10, qty_after=12, user_id=MISSING, notes="Count fix", source_type="adjustment")`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.diag.constraint_name == "machine_item_ledger_performed_by_fkey"`.
4. nothing written: nothing written.

### MIM-W-30 — an unknown user is a foreign key error (inventory_adjustment)
- **Rules:** `_write_ledger_entry` R12, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No ledger rows exist.

**When**
- `M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=MISSING, notes="Count fix", source_type="adjustment")`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.diag.constraint_name == "machine_item_ledger_performed_by_fkey"`.
4. nothing written: nothing written.

### MIM-W-31 — the entry and event are flushed but not committed
- **Rules:** `_write_ledger_entry` R13
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Savepoint and commit spy per **rolled back**.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=2, qty_before=10, qty_after=12, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. count: `entries_of(M1, I1)` has exactly 1 row.
3. event: events_of(M1) has exactly 1 row.
4. count after the savepoint rollback: `machine_item_ledger` has exactly 0 rows.
5. count after the savepoint rollback: `machine_activity_events` has exactly 0 rows.
6. mock called: the `db.commit` spy was never called.

### MIM-W-32 — value_before and value_after at 0.125 round half up
- **Rules:** `_write_ledger_entry` R4 [BUG-993] [BUG-1040]
- **Kind:** bug
- **Expect:** xfail BUG-1040
- **Fails today on:** Then 2 (today 0.00, BUG-993; half to even would give value_before 0.12)

**Given**
1. LG = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("0.125")`, but `qty_after 1`. Flush it; **do not refresh or expire it**, and keep the variable LG alive to the end of the test.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=1, qty_before=1, qty_after=2, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. re-read `entries_of(M1, I1)[-1]`: `value_before == Decimal("0.13")`, `value_after == Decimal("0.25")`.

### MIM-W-33 — value_after at 0.125 on a change from 2 to 1 rounds half up
- **Rules:** `_write_ledger_entry` R4 [BUG-993] [BUG-1040]
- **Kind:** bug
- **Expect:** xfail BUG-1040
- **Fails today on:** Then 2 (today 0.00, BUG-993; half to even would give 0.12)

**Given**
1. LG = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("0.125")`, but `qty_after 2`. Flush it; **do not refresh or expire it**, and keep the variable LG alive to the end of the test.

**When**
- `result = M._write_ledger_entry(db, workspace_id=W1.id, machine_id=M1.id, item_id=I1.id, transaction_type="inventory_adjustment", quantity=1, qty_before=2, qty_after=1, user_id=U2.id, notes="Count fix", source_type="adjustment")`.

**Then**
1. returns: `result is None`.
2. re-read `entries_of(M1, I1)[-1]`: `value_after == Decimal("0.13")`.

## `MachineItemManager.create_machine_item`

### MIM-C-01 — a missing machine gets the same 404
- **Rules:** `create_machine_item` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=MISSING, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine not found in this workspace"`.
4. session: `len(db.new) == 0`.
5. session: `db.flush()` runs and raises nothing.
6. nothing written: nothing written.

### MIM-C-02 — a machine of another workspace gets the same 404
- **Rules:** `create_machine_item` R1, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M9.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine not found in this workspace"`.
4. session: `len(db.new) == 0`.
5. session: `db.flush()` runs and raises nothing.
6. nothing written: nothing written.

### MIM-C-03 — machine id 0 gets the same 404
- **Rules:** `create_machine_item` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=0, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine not found in this workspace"`.
4. session: `len(db.new) == 0`.
5. session: `db.flush()` runs and raises nothing.
6. nothing written: nothing written.

### MIM-C-04 — a soft-deleted machine is refused
- **Rules:** `create_machine_item` R2, Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=MX.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot add items to a deleted machine"`.
4. session: `len(db.new) == 0`.
5. session: `db.flush()` runs and raises nothing.
6. nothing written: nothing written.

### MIM-C-05 — a live machine in a soft-deleted factory is refused like a deleted machine
- **Rules:** `create_machine_item` R3 [BUG-1076], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1076
- **Fails today on:** Then 1 (no error is raised: the factory is not read and the row is saved)

**Given**
1. No stock rows exist.

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=MF.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot add items to a deleted machine"`.
4. session: `len(db.new) == 0`.
5. session: `db.flush()` runs and raises nothing.
6. nothing written: nothing written.

### MIM-C-06 — an inactive-but-live machine is accepted
- **Rules:** `create_machine_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=MA.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `machine_id == MA.id`, `qty == 5`.
3. count: `machine_items` has exactly 1 row.

### MIM-C-07 — a machine in an inactive-but-live factory is accepted
- **Rules:** `create_machine_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=MN.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `machine_id == MN.id`, `qty == 5`.
3. count: `machine_items` has exactly 1 row.

### MIM-C-08 — a missing item gets the same 404
- **Rules:** `create_machine_item` R5 [BUG-1010], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1010
- **Fails today on:** Then 1 (the call raises IntegrityError: the item is not checked and the flush fails on machine_items_item_id_fkey)

**Given**
1. No stock rows exist.

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=MISSING, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Item with ID 999999999 not found"`.
4. session: `len(db.new) == 0`.
5. session: `db.flush()` runs and raises nothing.
6. nothing written: nothing written.

### MIM-C-09 — item id 0 gets the same 404
- **Rules:** `create_machine_item` R5 [BUG-1010], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1010
- **Fails today on:** Then 1 (the call raises IntegrityError: the item is not checked and the flush fails on machine_items_item_id_fkey)

**Given**
1. No stock rows exist.

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=0, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Item with ID 0 not found"`.
4. session: `len(db.new) == 0`.
5. session: `db.flush()` runs and raises nothing.
6. nothing written: nothing written.

### MIM-C-10 — an item of another workspace gets the same 404
- **Rules:** `create_machine_item` R5 [BUG-1010], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1010
- **Fails today on:** Then 1 (no error is raised: the row is saved with the other workspace's item)

**Given**
1. No stock rows exist.

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I9.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {I9.id} not found"`.
4. session: `len(db.new) == 0`.
5. session: `db.flush()` runs and raises nothing.
6. nothing written: nothing written.

### MIM-C-11 — a removed item of the workspace is refused
- **Rules:** `create_machine_item` R6 [BUG-1085], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-1085
- **Fails today on:** Then 1 (no error is raised: the row is saved with a ledger entry and activity)

**Given**
1. No stock rows exist.

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=IX.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot add a removed item to a machine"`.
4. session: `len(db.new) == 0`.
5. session: `db.flush()` runs and raises nothing.
6. nothing written: nothing written.

### MIM-C-12 — the removed-item refusal holds with qty 0
- **Rules:** `create_machine_item` R6 [BUG-1085], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-1085
- **Fails today on:** Then 1 (no error is raised: the row is saved)

**Given**
1. No stock rows exist.

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=IX.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot add a removed item to a machine"`.
4. session: `len(db.new) == 0`.
5. session: `db.flush()` runs and raises nothing.
6. nothing written: nothing written.

### MIM-C-13 — machine check first: a missing machine with a missing item is the machine's 404
- **Rules:** `create_machine_item` R1, R5, Errors row 1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=MISSING, item_id=MISSING, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine not found in this workspace"`.
4. session: `len(db.new) == 0`.
5. session: `db.flush()` runs and raises nothing.
6. nothing written: nothing written.

### MIM-C-14 — machine check first: a deleted machine with a missing item is the 400
- **Rules:** `create_machine_item` R2, R5, Errors row 2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=MX.id, item_id=MISSING, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot add items to a deleted machine"`.
4. session: `len(db.new) == 0`.
5. session: `db.flush()` runs and raises nothing.
6. nothing written: nothing written.

### MIM-C-15 — machine check first: a deleted machine with a removed item is the machine's 400
- **Rules:** `create_machine_item` R2, R6, Errors row 2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=MX.id, item_id=IX.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot add items to a deleted machine"`.
4. session: `len(db.new) == 0`.
5. session: `db.flush()` runs and raises nothing.
6. nothing written: nothing written.

### MIM-C-16 — factory check before the item check: a deleted factory with a missing item is the 400
- **Rules:** `create_machine_item` R3 [BUG-1076], R5, Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1076
- **Fails today on:** Then 1 (the call raises IntegrityError: neither is checked and the flush fails)

**Given**
1. No stock rows exist.

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=MF.id, item_id=MISSING, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot add items to a deleted machine"`.
4. session: `len(db.new) == 0`.
5. session: `db.flush()` runs and raises nothing.
6. nothing written: nothing written.

### MIM-C-17 — item check before the duplicate check: another workspace's item already on the machine is the 404
- **Rules:** `create_machine_item` R5 [BUG-1010], R7, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1010
- **Fails today on:** Then 2 (the duplicate check answers 409)

**Given**
1. MI = stock of M1, I9, `qty 2`. (A row of W1 with an item of W2, invalid data.)

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I9.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {I9.id} not found"`.
4. unchanged: unchanged(MI).
5. nothing written: nothing written.

### MIM-C-18 — removed check before the duplicate check: a removed item already on the machine is the 400
- **Rules:** `create_machine_item` R6 [BUG-1085], R7, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-1085
- **Fails today on:** Then 2 (the duplicate check answers 409)

**Given**
1. MI = stock of M1, IX, `qty 2`.

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=IX.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot add a removed item to a machine"`.
4. unchanged: unchanged(MI).
5. nothing written: nothing written.

### MIM-C-19 — a row for the pair gets the 409
- **Rules:** `create_machine_item` R7, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 3`.

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "This item already exists on this machine. Update the existing record instead."`.
4. session: `len(db.new) == 0`.
5. session: `MI not in db.dirty`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-C-20 — a row for the pair with qty 0 gets the 409
- **Rules:** `create_machine_item` R7, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 0`.

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "This item already exists on this machine. Update the existing record instead."`.
4. session: `len(db.new) == 0`.
5. session: `MI not in db.dirty`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-C-21 — a row of the pair on an inactive machine still gets the 409
- **Rules:** `create_machine_item` R7, R4, Errors row 5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of MA, I1, `qty 3`.

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=MA.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "This item already exists on this machine. Update the existing record instead."`.
4. unchanged: unchanged(MI).
5. nothing written: nothing written.

### MIM-C-22 — the same pair under another workspace_id does not block
- **Rules:** `create_machine_item` R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. OT = stock of M1, I1, `qty 3`, but `workspace_id W2.id`.

**When**
- `result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `qty == 5`.
3. unchanged: unchanged(OT).
4. count: `machine_items` has exactly 2 rows.

### MIM-C-23 — another item on the machine does not block
- **Rules:** `create_machine_item` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OT = stock of M1, I2, `qty 3`.

**When**
- `result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. unchanged: unchanged(OT).
3. count: `machine_items` has exactly 2 rows.

### MIM-C-24 — the item on another machine does not block
- **Rules:** `create_machine_item` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OT = stock of M2, I1, `qty 3`.

**When**
- `result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. unchanged: unchanged(OT).
3. count: `machine_items` has exactly 2 rows.

### MIM-C-25 — a lost race gets the same 409 and nothing is saved
- **Rules:** `create_machine_item` R8 [BUG-983], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-983
- **Fails today on:** Then 1 (no error is raised: there is no unique index and a second row is saved)

**Given**
1. MI = stock of M1, I1, `qty 3`.
2. Race simulation: `unittest.mock.patch.object(M.machine_item_dao, "get_by_machine_and_item", return_value=None)` around the When.

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`, inside `with db.begin_nested():`, inside `pytest.raises(HTTPException)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "This item already exists on this machine. Update the existing record instead."`.
4. count: `machine_items` with `machine_id == M1.id` and `item_id == I1.id` has exactly 1 row.
5. unchanged: unchanged(MI).
6. count: `machine_item_ledger` has exactly 0 rows.
7. count: `machine_activity_events` has exactly 0 rows.

### MIM-C-26 — the row carries the input and the caller's workspace
- **Rules:** `create_machine_item` R9, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=5, req_qty=7, defective_qty=1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, MachineItem)`.
2. returns: `result.id is not None`.
3. returns: `result.item_name == "Bolt M8"`, `result.item_unit == "pcs"`.
4. re-read the returned row: `workspace_id == W1.id`, `machine_id == M1.id`, `item_id == I1.id`.
5. re-read the returned row: `qty == 5`, `req_qty == 7`, `defective_qty == 1`.
6. count: `machine_items` has exactly 1 row.

### MIM-C-27 — optional fields not sent stay empty and qty defaults to 0
- **Rules:** `create_machine_item` R9, R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `qty == 0`, `req_qty is None`, `defective_qty is None`.

### MIM-C-28 — qty above 0 books one manual_add entry
- **Rules:** `create_machine_item` R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No ledger rows exist.

**When**
- `result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `entries_of(M1, I1)` has exactly 1 row.
3. re-read `entries_of(M1, I1)[-1]`: `transaction_type == "manual_add"`, `quantity == 5`.
4. re-read `entries_of(M1, I1)[-1]`: `qty_before == 0`, `qty_after == 5`.
5. re-read `entries_of(M1, I1)[-1]`: `source_type == "manual"`, `notes == "Initial machine inventory record created"`.
6. re-read `entries_of(M1, I1)[-1]`: `performed_by == U2.id`, `workspace_id == W1.id`.
7. re-read `entries_of(M1, I1)[-1]`: `unit_cost == Decimal("0.00")`, `total_cost == Decimal("0.00")`.
8. re-read `entries_of(M1, I1)[-1]`: `value_before == Decimal("0.00")`, `value_after == Decimal("0.00")`.
9. re-read `entries_of(M1, I1)[-1]`: `avg_price_before == Decimal("0.00")`, `avg_price_after == Decimal("0.00")`.

### MIM-C-29 — qty 1 books an entry
- **Rules:** `create_machine_item` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No ledger rows exist.

**When**
- `result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `entries_of(M1, I1)` has exactly 1 row.
3. re-read `entries_of(M1, I1)[-1]`: `quantity == 1`, `qty_after == 1`.

### MIM-C-30 — qty_before is 0 whatever the ledger holds
- **Rules:** `create_machine_item` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. LG = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("0.00")`, but `qty_after 7`.

**When**
- `result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=4), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `entries_of(M1, I1)` has exactly 2 rows.
3. re-read `entries_of(M1, I1)[-1]`: `quantity == 4`, `qty_before == 0`, `qty_after == 4`.
4. unchanged: unchanged(LG).

### MIM-C-31 — the opening entry takes the machine's current average
- **Rules:** `create_machine_item` R10, `_write_ledger_entry` R2 [BUG-993], R3, R4
- **Kind:** bug
- **Expect:** xfail BUG-993
- **Fails today on:** Then 2 (today every cost field is 0.00)

**Given**
1. LG = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("5.00")`, but `qty_after 0`.

**When**
- `result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=4), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read `entries_of(M1, I1)[-1]`: `unit_cost == Decimal("5.00")`, `avg_price_before == Decimal("5.00")`, `avg_price_after == Decimal("5.00")`.
3. re-read `entries_of(M1, I1)[-1]`: `total_cost == Decimal("20.00")`, `value_before == Decimal("0.00")`, `value_after == Decimal("20.00")`.

### MIM-C-32 — a row removed and added again keeps the average
- **Rules:** `create_machine_item` R10, `_write_ledger_entry` R2 [BUG-993], `delete_machine_item` R10
- **Kind:** bug
- **Expect:** xfail BUG-993
- **Fails today on:** Then 2 (today every cost field is 0.00)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. LG = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("3.00")`, but `qty_after 5`, `value_after Decimal("15.00")`.
3. `old_id = MI.id`.
4. `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`, then `db.flush()`.

**When**
- `result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=4), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id != old_id`.
2. re-read `entries_of(M1, I1)[-1]`: `unit_cost == Decimal("3.00")`, `avg_price_after == Decimal("3.00")`.
3. re-read `entries_of(M1, I1)[-1]`: `total_cost == Decimal("12.00")`, `value_after == Decimal("12.00")`.

### MIM-C-33 — qty 0 books no entry
- **Rules:** `create_machine_item` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No ledger rows exist.

**When**
- `result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `machine_item_ledger` has exactly 0 rows.
3. event: events_of(M1) has exactly 1 row.

### MIM-C-34 — qty left at its default books no entry
- **Rules:** `create_machine_item` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No ledger rows exist.

**When**
- `result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `machine_item_ledger` has exactly 0 rows.
3. event: events_of(M1) has exactly 1 row.

### MIM-C-35 — a negative qty is rejected by MachineItemCreate
- **Rules:** `create_machine_item` R12 [BUG-1079], Errors row 6
- **Kind:** bug
- **Expect:** xfail BUG-1079
- **Fails today on:** Then 1 (no error is raised: the schema has no minimum)

**Given**
1. No stock rows exist.

**When**
- build `MachineItemCreate(machine_id=1, item_id=1, qty=-1)` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. count: `machine_items` has exactly 0 rows.

### MIM-C-36 — qty 0 is accepted by MachineItemCreate
- **Rules:** `create_machine_item` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `result = MachineItemCreate(machine_id=1, item_id=1, qty=0)` (target `schema`).

**Then**
1. returns: `result.qty == 0`.

### MIM-C-37 — a qty of 2147483648 is rejected by MachineItemCreate
- **Rules:** `create_machine_item` R14 [BUG-1078], Errors row 6
- **Kind:** bug
- **Expect:** xfail BUG-1078
- **Fails today on:** Then 1 (no error is raised: the schema has no maximum)

**Given**
1. No stock rows exist.

**When**
- build `MachineItemCreate(machine_id=1, item_id=1, qty=2147483648)` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. count: `machine_items` has exactly 0 rows.

### MIM-C-38 — a negative req_qty is rejected by MachineItemCreate
- **Rules:** `create_machine_item` R13 [BUG-1079], Errors row 6
- **Kind:** bug
- **Expect:** xfail BUG-1079
- **Fails today on:** Then 1 (no error is raised: the schema has no minimum)

**Given**
1. No stock rows exist.

**When**
- build `MachineItemCreate(machine_id=1, item_id=1, req_qty=-1)` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. count: `machine_items` has exactly 0 rows.

### MIM-C-39 — req_qty 0 is accepted by MachineItemCreate
- **Rules:** `create_machine_item` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `result = MachineItemCreate(machine_id=1, item_id=1, req_qty=0)` (target `schema`).

**Then**
1. returns: `result.req_qty == 0`.

### MIM-C-40 — a req_qty of 2147483648 is rejected by MachineItemCreate
- **Rules:** `create_machine_item` R14 [BUG-1078], Errors row 6
- **Kind:** bug
- **Expect:** xfail BUG-1078
- **Fails today on:** Then 1 (no error is raised: the schema has no maximum)

**Given**
1. No stock rows exist.

**When**
- build `MachineItemCreate(machine_id=1, item_id=1, req_qty=2147483648)` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. count: `machine_items` has exactly 0 rows.

### MIM-C-41 — a negative defective_qty is rejected by MachineItemCreate
- **Rules:** `create_machine_item` R13 [BUG-1079], Errors row 6
- **Kind:** bug
- **Expect:** xfail BUG-1079
- **Fails today on:** Then 1 (no error is raised: the schema has no minimum)

**Given**
1. No stock rows exist.

**When**
- build `MachineItemCreate(machine_id=1, item_id=1, defective_qty=-1)` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. count: `machine_items` has exactly 0 rows.

### MIM-C-42 — defective_qty 0 is accepted by MachineItemCreate
- **Rules:** `create_machine_item` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `result = MachineItemCreate(machine_id=1, item_id=1, defective_qty=0)` (target `schema`).

**Then**
1. returns: `result.defective_qty == 0`.

### MIM-C-43 — a defective_qty of 2147483648 is rejected by MachineItemCreate
- **Rules:** `create_machine_item` R14 [BUG-1078], Errors row 6
- **Kind:** bug
- **Expect:** xfail BUG-1078
- **Fails today on:** Then 1 (no error is raised: the schema has no maximum)

**Given**
1. No stock rows exist.

**When**
- build `MachineItemCreate(machine_id=1, item_id=1, defective_qty=2147483648)` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. count: `machine_items` has exactly 0 rows.

### MIM-C-44 — req_qty None is accepted by MachineItemCreate
- **Rules:** `create_machine_item` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `result = MachineItemCreate(machine_id=1, item_id=1, req_qty=None)` (target `schema`).

**Then**
1. returns: `result.req_qty is None`.

### MIM-C-45 — defective_qty None is accepted by MachineItemCreate
- **Rules:** `create_machine_item` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `result = MachineItemCreate(machine_id=1, item_id=1, defective_qty=None)` (target `schema`).

**Then**
1. returns: `result.defective_qty is None`.

### MIM-C-46 — MachineItemBase has no minimum
- **Rules:** `create_machine_item` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `result = MachineItemBase(machine_id=1, item_id=1, qty=-1)` (target `schema`).

**Then**
1. returns: `result.qty == -1`.

### MIM-C-47 — 2147483647 is accepted and stored on all three fields
- **Rules:** `create_machine_item` R14
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=2147483647, req_qty=2147483647, defective_qty=2147483647), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `qty == 2147483647`, `req_qty == 2147483647`, `defective_qty == 2147483647`.
3. re-read `entries_of(M1, I1)[-1]`: `quantity == 2147483647`.

### MIM-C-48 — one item_added event with qty above 0
- **Rules:** `create_machine_item` R15
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: events_of(M1) has exactly 1 row.
3. event: that row: `event_type == "item_added"`, `description == "Item added: Bolt M8"`.
4. event: that row: `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == M1.id`.
5. event: that row: `metadata_json == {"item_id": I1.id, "item_name": "Bolt M8", "machine_item_id": result.id, "quantity": 5}`.

### MIM-C-49 — one item_added event with qty 0
- **Rules:** `create_machine_item` R15
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: events_of(M1) has exactly 1 row.
3. event: that row: `event_type == "item_added"`, `description == "Item added: Washer Ten"`.
4. event: that row: `metadata_json == {"item_id": I2.id, "item_name": "Washer Ten", "machine_item_id": result.id, "quantity": 0}`.

### MIM-C-50 — an unknown user with qty above 0 fails on the ledger
- **Rules:** `create_machine_item` R16, Errors row 7
- **Kind:** error
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.diag.constraint_name == "machine_item_ledger_performed_by_fkey"`.
4. nothing written: nothing written.

### MIM-C-51 — an unknown user with qty 0 fails on the activity entry
- **Rules:** `create_machine_item` R16, Errors row 7
- **Kind:** error
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=0), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.diag.constraint_name == "machine_activity_events_performed_by_fkey"`.
4. nothing written: nothing written.

### MIM-C-52 — the create is flushed but not committed
- **Rules:** `create_machine_item` R17
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Savepoint and commit spy per **rolled back**.

**When**
- `result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `machine_items` has exactly 1 row.
3. count: `machine_item_ledger` has exactly 1 row.
4. count: `machine_activity_events` has exactly 1 row.
5. count after the savepoint rollback: `machine_items` has exactly 0 rows.
6. count after the savepoint rollback: `machine_item_ledger` has exactly 0 rows.
7. count after the savepoint rollback: `machine_activity_events` has exactly 0 rows.
8. mock called: the `db.commit` spy was never called.

## `MachineItemManager.update_machine_item`

### MIM-U-01 — a row of another workspace gets the 404
- **Rules:** `update_machine_item` R1, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W2.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-U-02 — an unknown id gets the 404
- **Rules:** `update_machine_item` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `M.update_machine_item(db, machine_item_id=MISSING, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-U-03 — id 0 gets the 404
- **Rules:** `update_machine_item` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `M.update_machine_item(db, machine_item_id=0, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-U-04 — a row of a soft-deleted machine is refused
- **Rules:** `update_machine_item` R2 [BUG-1083], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1083
- **Fails today on:** Then 1 (no error is raised: the parents are not read and the row is updated)

**Given**
1. MI = stock of MX, I1, `qty 5`.

**When**
- `M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update items of a deleted machine"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-U-05 — a row of a soft-deleted machine is refused for a target change alone
- **Rules:** `update_machine_item` R2 [BUG-1083], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1083
- **Fails today on:** Then 1 (no error is raised: the parents are not read and the row is updated)

**Given**
1. MI = stock of MX, I1, `qty 5`.

**When**
- `M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(req_qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update items of a deleted machine"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-U-06 — a row of a soft-deleted machine is refused with no field sent
- **Rules:** `update_machine_item` R2 [BUG-1083], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1083
- **Fails today on:** Then 1 (no error is raised: the call returns the row)

**Given**
1. MI = stock of MX, I1, `qty 5`.

**When**
- `M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update items of a deleted machine"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-U-07 — a row of a soft-deleted machine is refused before an unknown user matters
- **Rules:** `update_machine_item` R2 [BUG-1083], R16, Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1083
- **Fails today on:** Then 1 (the call raises IntegrityError: the row is updated and the flush fails on the ledger)

**Given**
1. MI = stock of MX, I1, `qty 5`.

**When**
- `M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=MISSING)`, in a plain `pytest.raises`, no savepoint.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update items of a deleted machine"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-U-08 — a row of a machine in a soft-deleted factory is refused
- **Rules:** `update_machine_item` R2 [BUG-1083], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1083
- **Fails today on:** Then 1 (no error is raised: the parents are not read and the row is updated)

**Given**
1. MI = stock of MF, I1, `qty 5`.

**When**
- `M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update items of a deleted machine"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-U-09 — a row of a machine in a soft-deleted factory is refused for a target change alone
- **Rules:** `update_machine_item` R2 [BUG-1083], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1083
- **Fails today on:** Then 1 (no error is raised: the parents are not read and the row is updated)

**Given**
1. MI = stock of MF, I1, `qty 5`.

**When**
- `M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(req_qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update items of a deleted machine"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-U-10 — a row of a machine in a soft-deleted factory is refused with no field sent
- **Rules:** `update_machine_item` R2 [BUG-1083], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1083
- **Fails today on:** Then 1 (no error is raised: the call returns the row)

**Given**
1. MI = stock of MF, I1, `qty 5`.

**When**
- `M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update items of a deleted machine"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-U-11 — a row of a machine in a soft-deleted factory is refused before an unknown user matters
- **Rules:** `update_machine_item` R2 [BUG-1083], R16, Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1083
- **Fails today on:** Then 1 (the call raises IntegrityError: the row is updated and the flush fails on the ledger)

**Given**
1. MI = stock of MF, I1, `qty 5`.

**When**
- `M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=MISSING)`, in a plain `pytest.raises`, no savepoint.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update items of a deleted machine"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-U-12 — a row of an inactive-but-live machine is updated
- **Rules:** `update_machine_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of MA, I1, `qty 5`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `qty == 12`.
3. count: `entries_of(MA, I1)` has exactly 1 row.

### MIM-U-13 — a row of a machine in an inactive-but-live factory is updated
- **Rules:** `update_machine_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of MN, I1, `qty 5`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `qty == 12`.
3. count: `entries_of(MN, I1)` has exactly 1 row.

### MIM-U-14 — a row of a removed item is updated like any other
- **Rules:** `update_machine_item` R3, R8, R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, IX, `qty 5`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `qty == 12`.
3. count: `entries_of(M1, IX)` has exactly 1 row.
4. event: events_of(M1) with `event_type == "inventory_adjusted"` has exactly 1 row.
5. event: events_of(M1) with `event_type == "item_updated"` has exactly 1 row.
6. event: the `item_updated` row: `description == "Item updated: Old Rivet"`.

### MIM-U-15 — the row is read FOR UPDATE
- **Rules:** `update_machine_item` R4 [BUG-1072]
- **Kind:** bug
- **Expect:** xfail BUG-1072
- **Fails today on:** Then 2 (the row is read without a lock)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. sql_log.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. statement: `any("FOR UPDATE" in s for s in sql_log if s.lstrip().startswith("SELECT") and "FROM machine_items" in s)`.

### MIM-U-16 — qty alone is written, the omitted fields stay
- **Rules:** `update_machine_item` R5, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `qty == 12`.
3. re-read MI: `req_qty == 7`, `defective_qty == 1`.

### MIM-U-17 — req_qty alone is written, the omitted fields stay
- **Rules:** `update_machine_item` R5, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(req_qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `req_qty == 3`.
3. re-read MI: `qty == 5`, `defective_qty == 1`.

### MIM-U-18 — defective_qty alone is written, the omitted fields stay
- **Rules:** `update_machine_item` R5, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(defective_qty=2), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `defective_qty == 2`.
3. re-read MI: `qty == 5`, `req_qty == 7`.

### MIM-U-19 — all three fields together are written
- **Rules:** `update_machine_item` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12, req_qty=3, defective_qty=2), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `qty == 12`, `req_qty == 3`, `defective_qty == 2`.

### MIM-U-20 — qty 0 is a value and is applied
- **Rules:** `update_machine_item` R5, R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `qty == 0`.
3. event: events_of(M1) with `event_type == "item_updated"` has exactly 1 row.
4. event: that row: `metadata_json == {"item_id": I1.id, "item_name": "Bolt M8", "machine_item_id": MI.id, "changes": [{"field": "qty", "label": "Quantity", "from_value": "5", "to_value": "0"}]}`.

### MIM-U-21 — req_qty 0 is a value and is applied
- **Rules:** `update_machine_item` R5, R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(req_qty=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `req_qty == 0`.
3. event: events_of(M1) with `event_type == "item_updated"` has exactly 1 row.
4. event: that row: `metadata_json == {"item_id": I1.id, "item_name": "Bolt M8", "machine_item_id": MI.id, "changes": [{"field": "req_qty", "label": "Required quantity", "from_value": "7", "to_value": "0"}]}`.

### MIM-U-22 — defective_qty 0 is a value and is applied
- **Rules:** `update_machine_item` R5, R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(defective_qty=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `defective_qty == 0`.
3. event: events_of(M1) with `event_type == "item_updated"` has exactly 1 row.
4. event: that row: `metadata_json == {"item_id": I1.id, "item_name": "Bolt M8", "machine_item_id": MI.id, "changes": [{"field": "defective_qty", "label": "Defective quantity", "from_value": "1", "to_value": "0"}]}`.

### MIM-U-23 — an explicit null clears req_qty and records to_value None
- **Rules:** `update_machine_item` R6 [BUG-1075], R12
- **Kind:** bug
- **Expect:** xfail BUG-1075
- **Fails today on:** Then 2 (`null` is dropped and the old value stays)

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(req_qty=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `req_qty is None`.
3. re-read MI: `qty == 5`, `defective_qty == 1`.
4. count: `machine_item_ledger` has exactly 0 rows.
5. event: events_of(M1) has exactly 1 row.
6. event: that row: `metadata_json == {"item_id": I1.id, "item_name": "Bolt M8", "machine_item_id": MI.id, "changes": [{"field": "req_qty", "label": "Required quantity", "from_value": "7", "to_value": None}]}`.

### MIM-U-24 — an explicit null clears defective_qty and records to_value None
- **Rules:** `update_machine_item` R6 [BUG-1075], R12
- **Kind:** bug
- **Expect:** xfail BUG-1075
- **Fails today on:** Then 2 (`null` is dropped and the old value stays)

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(defective_qty=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `defective_qty is None`.
3. re-read MI: `qty == 5`, `req_qty == 7`.
4. count: `machine_item_ledger` has exactly 0 rows.
5. event: events_of(M1) has exactly 1 row.
6. event: that row: `metadata_json == {"item_id": I1.id, "item_name": "Bolt M8", "machine_item_id": MI.id, "changes": [{"field": "defective_qty", "label": "Defective quantity", "from_value": "1", "to_value": None}]}`.

### MIM-U-25 — null on one field next to a value on another
- **Rules:** `update_machine_item` R6 [BUG-1075], R5
- **Kind:** bug
- **Expect:** xfail BUG-1075
- **Fails today on:** Then 2 (`null` is dropped and the old value stays)

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(req_qty=None, defective_qty=2), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `req_qty is None`.
3. re-read MI: `defective_qty == 2`.
4. event: events_of(M1) has exactly 1 row.
5. event: that row: `metadata_json == {"item_id": I1.id, "item_name": "Bolt M8", "machine_item_id": MI.id, "changes": [{"field": "req_qty", "label": "Required quantity", "from_value": "7", "to_value": None}, {"field": "defective_qty", "label": "Defective quantity", "from_value": "1", "to_value": "2"}]}`.

### MIM-U-26 — a null qty is rejected by MachineItemUpdate
- **Rules:** `update_machine_item` R6 [BUG-1075], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1075
- **Fails today on:** Then 1 (no error is raised: `qty` accepts None)

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- build `MachineItemUpdate(qty=None)` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(MI).

### MIM-U-27 — no field sent: no entry, no event
- **Rules:** `update_machine_item` R7, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. session: `MI not in db.dirty`.
3. unchanged: unchanged(MI).
4. nothing written: nothing written.

### MIM-U-28 — no field sent by an unknown user raises nothing
- **Rules:** `update_machine_item` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. returns: `result is MI`.
2. unchanged: unchanged(MI).
3. nothing written: nothing written.

### MIM-U-29 — the same values: no entry, no event
- **Rules:** `update_machine_item` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=5, req_qty=7, defective_qty=1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. session: `MI not in db.dirty`.
3. unchanged: unchanged(MI).
4. nothing written: nothing written.

### MIM-U-30 — the same values by an unknown user raises nothing
- **Rules:** `update_machine_item` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=5, req_qty=7, defective_qty=1), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. returns: `result is MI`.
2. unchanged: unchanged(MI).
3. nothing written: nothing written.

### MIM-U-31 — null on a field already empty: no entry, no event
- **Rules:** `update_machine_item` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(req_qty=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. session: `MI not in db.dirty`.
3. unchanged: unchanged(MI).
4. nothing written: nothing written.

### MIM-U-32 — null on a field already empty by an unknown user raises nothing
- **Rules:** `update_machine_item` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(req_qty=None), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. returns: `result is MI`.
2. unchanged: unchanged(MI).
3. nothing written: nothing written.

### MIM-U-33 — a qty change up (5 to 12) books one adjustment
- **Rules:** `update_machine_item` R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `qty == 12`.
3. count: `entries_of(M1, I1)` has exactly 1 row.
4. re-read `entries_of(M1, I1)[-1]`: `transaction_type == "inventory_adjustment"`, `quantity == 7`.
5. re-read `entries_of(M1, I1)[-1]`: `qty_before == 5`, `qty_after == 12`.
6. re-read `entries_of(M1, I1)[-1]`: `source_type == "adjustment"`, `notes == "Manual machine inventory adjustment: 5 -> 12"`.
7. re-read `entries_of(M1, I1)[-1]`: `performed_by == U2.id`, `workspace_id == W1.id`.

### MIM-U-34 — a qty change down (12 to 5) books one adjustment
- **Rules:** `update_machine_item` R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 12`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `qty == 5`.
3. count: `entries_of(M1, I1)` has exactly 1 row.
4. re-read `entries_of(M1, I1)[-1]`: `transaction_type == "inventory_adjustment"`, `quantity == 7`.
5. re-read `entries_of(M1, I1)[-1]`: `qty_before == 12`, `qty_after == 5`.
6. re-read `entries_of(M1, I1)[-1]`: `source_type == "adjustment"`, `notes == "Manual machine inventory adjustment: 12 -> 5"`.
7. re-read `entries_of(M1, I1)[-1]`: `performed_by == U2.id`, `workspace_id == W1.id`.

### MIM-U-35 — a qty change to 0 (5 to 0) books one adjustment
- **Rules:** `update_machine_item` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `qty == 0`.
3. count: `entries_of(M1, I1)` has exactly 1 row.
4. re-read `entries_of(M1, I1)[-1]`: `transaction_type == "inventory_adjustment"`, `quantity == 5`.
5. re-read `entries_of(M1, I1)[-1]`: `qty_before == 5`, `qty_after == 0`.
6. re-read `entries_of(M1, I1)[-1]`: `source_type == "adjustment"`, `notes == "Manual machine inventory adjustment: 5 -> 0"`.
7. re-read `entries_of(M1, I1)[-1]`: `performed_by == U2.id`, `workspace_id == W1.id`.

### MIM-U-36 — a qty change from 0 (0 to 5) books one adjustment
- **Rules:** `update_machine_item` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 0`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `qty == 5`.
3. count: `entries_of(M1, I1)` has exactly 1 row.
4. re-read `entries_of(M1, I1)[-1]`: `transaction_type == "inventory_adjustment"`, `quantity == 5`.
5. re-read `entries_of(M1, I1)[-1]`: `qty_before == 0`, `qty_after == 5`.
6. re-read `entries_of(M1, I1)[-1]`: `source_type == "adjustment"`, `notes == "Manual machine inventory adjustment: 0 -> 5"`.
7. re-read `entries_of(M1, I1)[-1]`: `performed_by == U2.id`, `workspace_id == W1.id`.

### MIM-U-37 — no history: the adjustment's cost fields are 0.00
- **Rules:** `update_machine_item` R8, `_write_ledger_entry` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read `entries_of(M1, I1)[-1]`: `unit_cost == Decimal("0.00")`, `total_cost == Decimal("0.00")`.
3. re-read `entries_of(M1, I1)[-1]`: `value_before == Decimal("0.00")`, `value_after == Decimal("0.00")`.
4. re-read `entries_of(M1, I1)[-1]`: `avg_price_before == Decimal("0.00")`, `avg_price_after == Decimal("0.00")`.

### MIM-U-38 — the adjustment takes the current average
- **Rules:** `update_machine_item` R8, `_write_ledger_entry` R2 [BUG-993], R3, R4
- **Kind:** bug
- **Expect:** xfail BUG-993
- **Fails today on:** Then 2 (today every cost field is 0.00)

**Given**
1. MI = stock of M1, I1, `qty 10`.
2. LG = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("5.00")`, but `qty_after 10`, `value_after Decimal("50.00")`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read `entries_of(M1, I1)[-1]`: `unit_cost == Decimal("5.00")`, `avg_price_before == Decimal("5.00")`, `avg_price_after == Decimal("5.00")`.
3. re-read `entries_of(M1, I1)[-1]`: `total_cost == Decimal("10.00")`, `value_before == Decimal("50.00")`, `value_after == Decimal("60.00")`.

### MIM-U-39 — half up through the edit: 1 at 0.125 gives total_cost 0.13
- **Rules:** `update_machine_item` R8, `_write_ledger_entry` R3 [BUG-993] [BUG-1040]
- **Kind:** bug
- **Expect:** xfail BUG-1040
- **Fails today on:** Then 2 (today 0.00, BUG-993; half to even would give 0.12)

**Given**
1. MI = stock of M1, I1, `qty 1`.
2. LG = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("0.125")`, but `qty_after 1`. Flush it; **do not refresh or expire it**, and keep the variable LG alive to the end of the test.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=2), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read `entries_of(M1, I1)[-1]`: `total_cost == Decimal("0.13")`.

### MIM-U-40 — qty sent unchanged next to a changed field: no entry, one event
- **Rules:** `update_machine_item` R9, R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=5, req_qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `qty == 5`, `req_qty == 3`.
3. count: `machine_item_ledger` has exactly 0 rows.
4. event: events_of(M1) has exactly 1 row.
5. event: that row: `metadata_json == {"item_id": I1.id, "item_name": "Bolt M8", "machine_item_id": MI.id, "changes": [{"field": "req_qty", "label": "Required quantity", "from_value": "7", "to_value": "3"}]}`.

### MIM-U-41 — req_qty alone: no ledger entry, one event
- **Rules:** `update_machine_item` R10, R12
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(req_qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. count: `machine_item_ledger` has exactly 0 rows.
3. event: events_of(M1) has exactly 1 row.
4. event: that row: `event_type == "item_updated"`, `description == "Item updated: Bolt M8"`.
5. event: that row: `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == M1.id`.
6. event: that row: `metadata_json == {"item_id": I1.id, "item_name": "Bolt M8", "machine_item_id": MI.id, "changes": [{"field": "req_qty", "label": "Required quantity", "from_value": "7", "to_value": "3"}]}`.

### MIM-U-42 — defective_qty alone: no ledger entry, one event
- **Rules:** `update_machine_item` R10, R12
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(defective_qty=2), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. count: `machine_item_ledger` has exactly 0 rows.
3. event: events_of(M1) has exactly 1 row.
4. event: that row: `event_type == "item_updated"`, `description == "Item updated: Bolt M8"`.
5. event: that row: `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == M1.id`.
6. event: that row: `metadata_json == {"item_id": I1.id, "item_name": "Bolt M8", "machine_item_id": MI.id, "changes": [{"field": "defective_qty", "label": "Defective quantity", "from_value": "1", "to_value": "2"}]}`.

### MIM-U-43 — a qty change gives both activity entries
- **Rules:** `update_machine_item` R11, R12, `_write_ledger_entry` R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. event: events_of(M1) has exactly 2 rows.
3. event: events_of(M1) with `event_type == "inventory_adjusted"` has exactly 1 row.
4. event: events_of(M1) with `event_type == "item_updated"` has exactly 1 row.
5. event: the `inventory_adjusted` row: `description == "Inventory adjusted on Bolt M8: 5 → 12"`.
6. event: the `inventory_adjusted` row: `metadata_json == {"item_id": I1.id, "item_name": "Bolt M8", "quantity": 7, "changes": [{"field": "qty", "label": "Quantity", "from_value": "5", "to_value": "12"}]}`.
7. event: the `item_updated` row: `description == "Item updated: Bolt M8"`.
8. event: the `item_updated` row: `metadata_json == {"item_id": I1.id, "item_name": "Bolt M8", "machine_item_id": MI.id, "changes": [{"field": "qty", "label": "Quantity", "from_value": "5", "to_value": "12"}]}`.

### MIM-U-44 — changes list all three fields in order
- **Rules:** `update_machine_item` R12
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(defective_qty=2, req_qty=3, qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. event: events_of(M1) with `event_type == "item_updated"` has exactly 1 row.
3. event: the `item_updated` row: `metadata_json == {"item_id": I1.id, "item_name": "Bolt M8", "machine_item_id": MI.id, "changes": [{"field": "qty", "label": "Quantity", "from_value": "5", "to_value": "12"}, {"field": "req_qty", "label": "Required quantity", "from_value": "7", "to_value": "3"}, {"field": "defective_qty", "label": "Defective quantity", "from_value": "1", "to_value": "2"}]}`.

### MIM-U-45 — changes leave out a field sent with its old value
- **Rules:** `update_machine_item` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12, req_qty=7, defective_qty=2), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. event: events_of(M1) with `event_type == "item_updated"` has exactly 1 row.
3. event: the `item_updated` row: `metadata_json == {"item_id": I1.id, "item_name": "Bolt M8", "machine_item_id": MI.id, "changes": [{"field": "qty", "label": "Quantity", "from_value": "5", "to_value": "12"}, {"field": "defective_qty", "label": "Defective quantity", "from_value": "1", "to_value": "2"}]}`.

### MIM-U-46 — an empty old value is None in changes
- **Rules:** `update_machine_item` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(req_qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. event: events_of(M1) with `event_type == "item_updated"` has exactly 1 row.
3. event: that row: `metadata_json == {"item_id": I1.id, "item_name": "Bolt M8", "machine_item_id": MI.id, "changes": [{"field": "req_qty", "label": "Required quantity", "from_value": None, "to_value": "3"}]}`.

### MIM-U-47 — a negative qty is rejected by MachineItemUpdate
- **Rules:** `update_machine_item` R13 [BUG-1079], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1079
- **Fails today on:** Then 1 (no error is raised: the schema has no minimum)

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- build `MachineItemUpdate(qty=-1)` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(MI).

### MIM-U-48 — qty 0 is accepted by MachineItemUpdate
- **Rules:** `update_machine_item` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `result = MachineItemUpdate(qty=0)` (target `schema`).

**Then**
1. returns: `result.qty == 0`.

### MIM-U-49 — a qty of 2147483648 is rejected by MachineItemUpdate
- **Rules:** `update_machine_item` R14 [BUG-1078], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1078
- **Fails today on:** Then 1 (no error is raised: the schema has no maximum)

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- build `MachineItemUpdate(qty=2147483648)` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(MI).

### MIM-U-50 — a negative req_qty is rejected by MachineItemUpdate
- **Rules:** `update_machine_item` R13 [BUG-1079], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1079
- **Fails today on:** Then 1 (no error is raised: the schema has no minimum)

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- build `MachineItemUpdate(req_qty=-1)` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(MI).

### MIM-U-51 — req_qty 0 is accepted by MachineItemUpdate
- **Rules:** `update_machine_item` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `result = MachineItemUpdate(req_qty=0)` (target `schema`).

**Then**
1. returns: `result.req_qty == 0`.

### MIM-U-52 — a req_qty of 2147483648 is rejected by MachineItemUpdate
- **Rules:** `update_machine_item` R14 [BUG-1078], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1078
- **Fails today on:** Then 1 (no error is raised: the schema has no maximum)

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- build `MachineItemUpdate(req_qty=2147483648)` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(MI).

### MIM-U-53 — a negative defective_qty is rejected by MachineItemUpdate
- **Rules:** `update_machine_item` R13 [BUG-1079], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1079
- **Fails today on:** Then 1 (no error is raised: the schema has no minimum)

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- build `MachineItemUpdate(defective_qty=-1)` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(MI).

### MIM-U-54 — defective_qty 0 is accepted by MachineItemUpdate
- **Rules:** `update_machine_item` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock rows exist.

**When**
- `result = MachineItemUpdate(defective_qty=0)` (target `schema`).

**Then**
1. returns: `result.defective_qty == 0`.

### MIM-U-55 — a defective_qty of 2147483648 is rejected by MachineItemUpdate
- **Rules:** `update_machine_item` R14 [BUG-1078], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1078
- **Fails today on:** Then 1 (no error is raised: the schema has no maximum)

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- build `MachineItemUpdate(defective_qty=2147483648)` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(MI).

### MIM-U-56 — a row already negative is edited as an ordinary adjustment (-3 to 2)
- **Rules:** `update_machine_item` R13, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty -3`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=2), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `qty == 2`.
3. count: `entries_of(M1, I1)` has exactly 1 row.
4. re-read `entries_of(M1, I1)[-1]`: `transaction_type == "inventory_adjustment"`, `quantity == 5`.
5. re-read `entries_of(M1, I1)[-1]`: `qty_before == -3`, `qty_after == 2`.
6. re-read `entries_of(M1, I1)[-1]`: `source_type == "adjustment"`, `notes == "Manual machine inventory adjustment: -3 -> 2"`.
7. re-read `entries_of(M1, I1)[-1]`: `performed_by == U2.id`, `workspace_id == W1.id`.

### MIM-U-57 — a row already negative is edited as an ordinary adjustment (-3 to 0)
- **Rules:** `update_machine_item` R13, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty -3`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `qty == 0`.
3. count: `entries_of(M1, I1)` has exactly 1 row.
4. re-read `entries_of(M1, I1)[-1]`: `transaction_type == "inventory_adjustment"`, `quantity == 3`.
5. re-read `entries_of(M1, I1)[-1]`: `qty_before == -3`, `qty_after == 0`.
6. re-read `entries_of(M1, I1)[-1]`: `source_type == "adjustment"`, `notes == "Manual machine inventory adjustment: -3 -> 0"`.
7. re-read `entries_of(M1, I1)[-1]`: `performed_by == U2.id`, `workspace_id == W1.id`.

### MIM-U-58 — 2147483647 is accepted and stored on all three fields
- **Rules:** `update_machine_item` R14
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=2147483647, req_qty=2147483647, defective_qty=2147483647), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `qty == 2147483647`, `req_qty == 2147483647`, `defective_qty == 2147483647`.

### MIM-U-59 — a stored row with another workspace's item is not found
- **Rules:** `update_machine_item` R15 [BUG-1086], Errors row 1, `_item_name` R3 [BUG-1086]
- **Kind:** bug
- **Expect:** xfail BUG-1086
- **Fails today on:** Then 1 (no error is raised: the row is updated and its events say `Item #<item_id>`)

**Given**
1. MI = stock of M1, I9, `qty 5`. (A row of W1 with an item of W2, invalid data.)

**When**
- `M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-U-60 — a stored row with another workspace's item is not found with no field sent
- **Rules:** `update_machine_item` R15 [BUG-1086], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1086
- **Fails today on:** Then 1 (no error is raised: the call returns the row)

**Given**
1. MI = stock of M1, I9, `qty 5`. (A row of W1 with an item of W2, invalid data.)

**When**
- `M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-U-61 — not found wins over the deleted-machine refusal for such a row
- **Rules:** `update_machine_item` R15 [BUG-1086], R2 [BUG-1083], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1086
- **Fails today on:** Then 1 (no error is raised: the row is updated and its events say `Item #<item_id>`)

**Given**
1. MI = stock of MX, I9, `qty 5`.

**When**
- `M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-U-62 — an unknown user with a qty change fails on the ledger
- **Rules:** `update_machine_item` R16, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.diag.constraint_name == "machine_item_ledger_performed_by_fkey"`.
4. unchanged: unchanged(MI).
5. nothing written: nothing written.

### MIM-U-63 — an unknown user with only another field changed fails on the activity entry
- **Rules:** `update_machine_item` R16, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(req_qty=3), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.diag.constraint_name == "machine_activity_events_performed_by_fkey"`.
4. unchanged: unchanged(MI).
5. nothing written: nothing written.

### MIM-U-64 — the update is flushed but not committed
- **Rules:** `update_machine_item` R17
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. Savepoint and commit spy per **rolled back**.

**When**
- `result = M.update_machine_item(db, machine_item_id=MI.id, item_data=MachineItemUpdate(qty=12), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI`.
2. re-read MI: `qty == 12`.
3. count: `machine_item_ledger` has exactly 1 row.
4. event: events_of(M1) has exactly 2 rows.
5. re-read MI after the savepoint rollback: `qty == 5`.
6. count after the savepoint rollback: `machine_item_ledger` has exactly 0 rows.
7. count after the savepoint rollback: `machine_activity_events` has exactly 0 rows.
8. mock called: the `db.commit` spy was never called.

## `MachineItemManager.delete_machine_item`

### MIM-D-01 — a row of another workspace gets the 404
- **Rules:** `delete_machine_item` R1, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W2.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-D-02 — an unknown id gets the 404
- **Rules:** `delete_machine_item` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `M.delete_machine_item(db, machine_item_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-D-03 — id 0 gets the 404
- **Rules:** `delete_machine_item` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `M.delete_machine_item(db, machine_item_id=0, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-D-04 — a row of a soft-deleted machine with qty 5 is refused
- **Rules:** `delete_machine_item` R2 [BUG-1084], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1084
- **Fails today on:** Then 1 (no error is raised: the parents are not read and the row is deleted)

**Given**
1. MI = stock of MX, I1, `qty 5`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot remove items from a deleted machine"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-D-05 — a row of a soft-deleted machine with qty 0 is refused
- **Rules:** `delete_machine_item` R2 [BUG-1084], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1084
- **Fails today on:** Then 1 (no error is raised: the parents are not read and the row is deleted)

**Given**
1. MI = stock of MX, I1, `qty 0`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot remove items from a deleted machine"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-D-06 — a row of a soft-deleted machine is refused before an unknown user matters
- **Rules:** `delete_machine_item` R2 [BUG-1084], R12, Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1084
- **Fails today on:** Then 1 (the call raises IntegrityError: the final adjustment fails on the unknown user)

**Given**
1. MI = stock of MX, I1, `qty 5`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=MISSING)`, in a plain `pytest.raises`, no savepoint.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot remove items from a deleted machine"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-D-07 — a row of a soft-deleted machine with an open order gets the 400, not the blockers
- **Rules:** `delete_machine_item` R2 [BUG-1084], R5 [BUG-1081], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1084
- **Fails today on:** Then 1 (no error is raised: the parents are not read and the row is deleted)

**Given**
1. MI = stock of MX, I1, `qty 5`.
2. O1 = work order of M2, `status "DRAFT"`.
3. L1 = source line of O1, but `source_location_id MX.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot remove items from a deleted machine"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.
9. unchanged: unchanged(L1).

### MIM-D-08 — a row of a machine in a soft-deleted factory with qty 5 is refused
- **Rules:** `delete_machine_item` R2 [BUG-1084], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1084
- **Fails today on:** Then 1 (no error is raised: the parents are not read and the row is deleted)

**Given**
1. MI = stock of MF, I1, `qty 5`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot remove items from a deleted machine"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-D-09 — a row of a machine in a soft-deleted factory with qty 0 is refused
- **Rules:** `delete_machine_item` R2 [BUG-1084], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1084
- **Fails today on:** Then 1 (no error is raised: the parents are not read and the row is deleted)

**Given**
1. MI = stock of MF, I1, `qty 0`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot remove items from a deleted machine"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-D-10 — a row of a machine in a soft-deleted factory is refused before an unknown user matters
- **Rules:** `delete_machine_item` R2 [BUG-1084], R12, Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1084
- **Fails today on:** Then 1 (the call raises IntegrityError: the final adjustment fails on the unknown user)

**Given**
1. MI = stock of MF, I1, `qty 5`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=MISSING)`, in a plain `pytest.raises`, no savepoint.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot remove items from a deleted machine"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-D-11 — a row of a machine in a soft-deleted factory with an open order gets the 400, not the blockers
- **Rules:** `delete_machine_item` R2 [BUG-1084], R5 [BUG-1081], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1084
- **Fails today on:** Then 1 (no error is raised: the parents are not read and the row is deleted)

**Given**
1. MI = stock of MF, I1, `qty 5`.
2. O1 = work order of M2, `status "DRAFT"`.
3. L1 = source line of O1, but `source_location_id MF.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot remove items from a deleted machine"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.
9. unchanged: unchanged(L1).

### MIM-D-12 — a row of an inactive-but-live machine is deleted
- **Rules:** `delete_machine_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of MA, I1, `qty 5`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `entries_of(MA, I1)` has exactly 1 row.

### MIM-D-13 — a row of an inactive-but-live machine with an open order is refused with its blockers
- **Rules:** `delete_machine_item` R2, R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of MA, I1, `qty 5`.
2. O1 = work order of M2, `status "DRAFT"`.
3. L1 = source line of O1, but `source_location_id MA.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(L1).

### MIM-D-14 — a row of a machine in an inactive-but-live factory is deleted
- **Rules:** `delete_machine_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of MN, I1, `qty 5`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `entries_of(MN, I1)` has exactly 1 row.

### MIM-D-15 — a row of a machine in an inactive-but-live factory with an open order is refused with its blockers
- **Rules:** `delete_machine_item` R2, R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of MN, I1, `qty 5`.
2. O1 = work order of M2, `status "DRAFT"`.
3. L1 = source line of O1, but `source_location_id MN.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(L1).

### MIM-D-16 — a row of a removed item is deleted like any other
- **Rules:** `delete_machine_item` R3, R6, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, IX, `qty 3`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `entries_of(M1, IX)` has exactly 1 row.
4. event: the `item_removed` row: `description == "Item removed: Old Rivet"`.

### MIM-D-17 — a row of a removed item with an open order is refused like any other
- **Rules:** `delete_machine_item` R3, R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, IX, `qty 3`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1, but `item_id IX.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(L1).

### MIM-D-18 — the row is read FOR UPDATE
- **Rules:** `delete_machine_item` R4 [BUG-1073]
- **Kind:** bug
- **Expect:** xfail BUG-1073
- **Fails today on:** Then 2 (the row is read without a lock)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. sql_log.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. statement: `any("FOR UPDATE" in s for s in sql_log if s.lstrip().startswith("SELECT") and "FROM machine_items" in s)`.

### MIM-D-19 — (a) a DRAFT order with an unconsumed line sourcing from this machine blocks
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(L1).

### MIM-D-20 — (b) a DRAFT order on this machine with a REPLACE line for this item blocks
- **Rules:** `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = replace line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(L1).

### MIM-D-21 — (a) a IN_PROGRESS order with an unconsumed line sourcing from this machine blocks
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "IN_PROGRESS"`.
3. L1 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(L1).

### MIM-D-22 — (b) a IN_PROGRESS order on this machine with a REPLACE line for this item blocks
- **Rules:** `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "IN_PROGRESS"`.
3. L1 = replace line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(L1).

### MIM-D-23 — (c) a not-completed transfer out of this machine with a line for this item blocks
- **Rules:** `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1.
3. TL1 = TO line of TO1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(TO1).
11. unchanged: unchanged(TL1).

### MIM-D-24 — (d) a pending return of a purchase order delivered to this machine blocks
- **Rules:** `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1.
5. RL1 = return line of RT1, POL1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "purchase_return", "id": RT1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(RT1).
11. unchanged: unchanged(RL1).

### MIM-D-25 — (a) the order's own machine is not read: an order of another machine blocks
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M2, `status "DRAFT"`.
3. L1 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).

### MIM-D-26 — (a) the order's own machine is not read: an order with no machine blocks
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `machine_id None`.
3. L1 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).

### MIM-D-27 — (a) the order's soft-deleted factory is not read
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M2, `status "DRAFT"`, but `factory_id FD.id`.
3. L1 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).

### MIM-D-28 — (a) the order's inactive factory is not read
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M2, `status "DRAFT"`, but `factory_id FI.id`.
3. L1 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).

### MIM-D-29 — (a) the order's soft-deleted machine is not read
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of MX, `status "DRAFT"`.
3. L1 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).

### MIM-D-30 — (b) a consumed REPLACE line still blocks: `consumed_at` is not read
- **Rules:** `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = replace line of O1, but `consumed_at T9`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).

### MIM-D-32 — (b) the order's soft-deleted factory is not read
- **Rules:** `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `factory_id FD.id`.
3. L1 = replace line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).

### MIM-D-33 — (b) the order's inactive factory is not read
- **Rules:** `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `factory_id FI.id`.
3. L1 = replace line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).

### MIM-D-34 — (c) the stage is not read: a transfer at stage Complete with completed_at empty blocks
- **Rules:** `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `current_status_id STC.id`.
3. TL1 = TO line of TO1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(TO1).

### MIM-D-35 — (c) a soft-deleted destination factory is not read
- **Rules:** `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `destination_location_id FD.id`.
3. TL1 = TO line of TO1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(TO1).

### MIM-D-36 — (c) an inactive destination factory is not read
- **Rules:** `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `destination_location_id FI.id`.
3. TL1 = TO line of TO1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(TO1).

### MIM-D-37 — (c) a soft-deleted destination machine is not read
- **Rules:** `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `destination_location_type "machine"`, `destination_location_id MX.id`.
3. TL1 = TO line of TO1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(TO1).

### MIM-D-38 — (d) a voided purchase order is not read: its pending return blocks
- **Rules:** `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1, but `voided True`.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1.
5. RL1 = return line of RT1, POL1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "purchase_return", "id": RT1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(RT1).

### MIM-D-39 — (d) the stage is not read: a purchase order at stage Draft with a pending return blocks
- **Rules:** `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1, but `current_status_id STD.id`.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1.
5. RL1 = return line of RT1, POL1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "purchase_return", "id": RT1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(RT1).

### MIM-D-40 — (a) an order and line of W2 on the source machine shows only the generic entry
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(L1).

### MIM-D-41 — (a) a W1 line on an order of W2 shows only the generic entry
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(L1).

### MIM-D-42 — (a) a W2 line on an order of W1 shows only the generic entry
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(L1).

### MIM-D-43 — (a) an IN_PROGRESS order and line of W2 shows only the generic entry
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "IN_PROGRESS"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(L1).

### MIM-D-44 — (b) an order and REPLACE line of W2 on this machine shows only the generic entry
- **Rules:** `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = replace line of O1, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(L1).

### MIM-D-45 — (b) a W1 REPLACE line on an order of W2 shows only the generic entry
- **Rules:** `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = replace line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(L1).

### MIM-D-46 — (b) a W2 REPLACE line on an order of W1 shows only the generic entry
- **Rules:** `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = replace line of O1, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(L1).

### MIM-D-47 — (b) an IN_PROGRESS order and REPLACE line of W2 shows only the generic entry
- **Rules:** `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "IN_PROGRESS"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = replace line of O1, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(L1).

### MIM-D-48 — (c) a transfer and line of W2 shows only the generic entry
- **Rules:** `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `workspace_id W2.id`, `current_status_id ST9.id`, `destination_location_id F9.id`.
3. TL1 = TO line of TO1, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(TO1).
11. unchanged: unchanged(TL1).

### MIM-D-49 — (c) a W1 line on a transfer of W2 shows only the generic entry
- **Rules:** `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `workspace_id W2.id`, `current_status_id ST9.id`, `destination_location_id F9.id`.
3. TL1 = TO line of TO1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(TO1).
11. unchanged: unchanged(TL1).

### MIM-D-50 — (c) a W2 line on a transfer of W1 shows only the generic entry
- **Rules:** `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1.
3. TL1 = TO line of TO1, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(TO1).
11. unchanged: unchanged(TL1).

### MIM-D-51 — (d) a purchase order, return and line all of W2 shows only the generic entry
- **Rules:** `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1, but `workspace_id W2.id`, `current_status_id ST9.id`.
3. POL1 = PO line of PO1, but `workspace_id W2.id`.
4. RT1 = return of PO1, but `workspace_id W2.id`.
5. RL1 = return line of RT1, POL1, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(RT1).
11. unchanged: unchanged(RL1).

### MIM-D-52 — (d) a return and line of W2 on a purchase order of W1 shows only the generic entry
- **Rules:** `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1, but `workspace_id W2.id`.
5. RL1 = return line of RT1, POL1, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(RT1).
11. unchanged: unchanged(RL1).

### MIM-D-53 — (d) a W1 line on a return of W2 shows only the generic entry
- **Rules:** `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1, but `workspace_id W2.id`.
5. RL1 = return line of RT1, POL1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(RT1).
11. unchanged: unchanged(RL1).

### MIM-D-54 — (d) a W2 line on a return of W1 shows only the generic entry
- **Rules:** `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1.
5. RL1 = return line of RT1, POL1, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(RT1).
11. unchanged: unchanged(RL1).

### MIM-D-55 — (a) lines are judged one at a time: own line and W2 line give the entry and the generic one
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1.
4. L2 = source line of O1, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}, {"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(L1).
11. unchanged: unchanged(L2).

### MIM-D-56 — (b) lines are judged one at a time: own line and W2 line give the entry and the generic one
- **Rules:** `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = replace line of O1.
4. L2 = replace line of O1, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}, {"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(L1).
11. unchanged: unchanged(L2).

### MIM-D-57 — (c) lines are judged one at a time: own line and W2 line give the entry and the generic one
- **Rules:** `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1.
3. TL1 = TO line of TO1.
4. TL2 = TO line of TO1, but `workspace_id W2.id`, `line_number 2`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}, {"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(TL1).
11. unchanged: unchanged(TL2).

### MIM-D-58 — (d) lines are judged one at a time: own line and W2 line give the entry and the generic one
- **Rules:** `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1.
5. RL1 = return line of RT1, POL1.
6. RL2 = return line of RT1, POL1, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "purchase_return", "id": RT1.id}, {"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(RL1).
11. unchanged: unchanged(RL2).

### MIM-D-59 — (a) a W1 row on a W2 factory keeps its normal entry
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `factory_id F9.id`.
3. L1 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).

### MIM-D-60 — (a) a W1 row on a W2 work order type keeps its normal entry
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `work_order_type_id WT9.id`.
3. L1 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).

### MIM-D-61 — (a) a W1 row on a W2 machine as its own machine keeps its normal entry
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "DRAFT"`.
3. L1 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).

### MIM-D-62 — (b) a W1 row on a W2 factory keeps its normal entry
- **Rules:** `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `factory_id F9.id`.
3. L1 = replace line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).

### MIM-D-63 — (b) a W1 row on a W2 work order type keeps its normal entry
- **Rules:** `delete_machine_item` R5 (b) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `work_order_type_id WT9.id`.
3. L1 = replace line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).

### MIM-D-64 — (c) a W1 row on a W2 stage keeps its normal entry
- **Rules:** `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `current_status_id ST9.id`.
3. TL1 = TO line of TO1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(TO1).

### MIM-D-65 — (c) a W1 row on a W2 destination factory keeps its normal entry
- **Rules:** `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `destination_location_id F9.id`.
3. TL1 = TO line of TO1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(TO1).

### MIM-D-66 — (c) a W1 row on a W2 destination machine keeps its normal entry
- **Rules:** `delete_machine_item` R5 (c) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `destination_location_type "machine"`, `destination_location_id M9.id`.
3. TL1 = TO line of TO1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(TO1).

### MIM-D-67 — (d) a W1 row on a purchase order at a W2 stage keeps its normal entry
- **Rules:** `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1, but `current_status_id ST9.id`.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1.
5. RL1 = return line of RT1, POL1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "purchase_return", "id": RT1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(RT1).

### MIM-D-68 — (d) a W1 row on a W2 purchase order line behind the return line keeps its normal entry
- **Rules:** `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1.
5. POL9 = PO line of PO1, but `workspace_id W2.id`, `line_number 2`.
6. RL1 = return line of RT1, POL9.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "purchase_return", "id": RT1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(RT1).

### MIM-D-69 — work orders sort by order id, not by line id
- **Rules:** `delete_machine_item` R5a [BUG-1081], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. O2 = work order of M1, `status "DRAFT"`.
4. L2 = source line of O2.
5. L1 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}, {"type": "work_order", "id": O2.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(O2).

### MIM-D-70 — transfers sort by order id, not by line id
- **Rules:** `delete_machine_item` R5a [BUG-1081], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1.
3. TO2 = transfer out of M1.
4. TL2 = TO line of TO2.
5. TL1 = TO line of TO1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}, {"type": "transfer_order", "id": TO2.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(TO1).
11. unchanged: unchanged(TO2).

### MIM-D-71 — returns sort by return id, not by line id
- **Rules:** `delete_machine_item` R5a [BUG-1081], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1.
5. RT2 = return of PO1.
6. RL2 = return line of RT2, POL1.
7. RL1 = return line of RT1, POL1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "purchase_return", "id": RT1.id}, {"type": "purchase_return", "id": RT2.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(RT1).
11. unchanged: unchanged(RT2).

### MIM-D-72 — types sort work order, transfer, return, whatever was built first
- **Rules:** `delete_machine_item` R5a [BUG-1081], R5 (a), R5 (c), R5 (d), Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1.
5. RL1 = return line of RT1, POL1.
6. TO1 = transfer out of M1.
7. TL1 = TO line of TO1.
8. O1 = work order of M1, `status "DRAFT"`.
9. L1 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}, {"type": "transfer_order", "id": TO1.id}, {"type": "purchase_return", "id": RT1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(TO1).
12. unchanged: unchanged(RT1).

### MIM-D-73 — the generic entry comes last, after every type, though its row was built first
- **Rules:** `delete_machine_item` R5a [BUG-1081], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O9 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L9 = source line of O9, but `workspace_id W2.id`.
4. PO1 = delivered PO to M1.
5. POL1 = PO line of PO1.
6. RT1 = return of PO1.
7. RL1 = return line of RT1, POL1.
8. TO1 = transfer out of M1.
9. TL1 = TO line of TO1.
10. O1 = work order of M1, `status "DRAFT"`.
11. L1 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}, {"type": "transfer_order", "id": TO1.id}, {"type": "purchase_return", "id": RT1.id}, {"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O9).
11. unchanged: unchanged(L9).

### MIM-D-74 — a W2 row of another type goes last after a transfer
- **Rules:** `delete_machine_item` R5a [BUG-1081], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O9 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L9 = source line of O9, but `workspace_id W2.id`.
4. TO1 = transfer out of M1.
5. TL1 = TO line of TO1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}, {"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-75 — a W2 row of another type goes last after a return
- **Rules:** `delete_machine_item` R5a [BUG-1081], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O9 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L9 = source line of O9, but `workspace_id W2.id`.
4. PO1 = delivered PO to M1.
5. POL1 = PO line of PO1.
6. RT1 = return of PO1.
7. RL1 = return line of RT1, POL1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "purchase_return", "id": RT1.id}, {"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-76 — a W2 row of another type goes last after a work order
- **Rules:** `delete_machine_item` R5a [BUG-1081], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO9 = transfer out of M1, but `workspace_id W2.id`, `current_status_id ST9.id`, `destination_location_id F9.id`.
3. TL9 = TO line of TO9, but `workspace_id W2.id`.
4. O1 = work order of M1, `status "DRAFT"`.
5. L1 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}, {"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-77 — two blocking lines on one order give one entry
- **Rules:** `delete_machine_item` R5a [BUG-1081], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1.
4. L2 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-78 — two REPLACE lines on one order give one entry
- **Rules:** `delete_machine_item` R5a [BUG-1081], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = replace line of O1.
4. L2 = replace line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-79 — a line under (a) and one under (b) on one order give one entry
- **Rules:** `delete_machine_item` R5a [BUG-1081], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1.
4. L2 = replace line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-80 — two lines on one transfer give one entry
- **Rules:** `delete_machine_item` R5a [BUG-1081], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1.
3. TL1 = TO line of TO1.
4. TL2 = TO line of TO1, but `line_number 2`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-81 — two lines on one return give one entry
- **Rules:** `delete_machine_item` R5a [BUG-1081], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1.
5. RL1 = return line of RT1, POL1.
6. RL2 = return line of RT1, POL1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "purchase_return", "id": RT1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-82 — an (a) order and a separate (b) order give two entries
- **Rules:** `delete_machine_item` R5a [BUG-1081], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1.
4. O2 = work order of M1, `status "DRAFT"`.
5. L2 = replace line of O2.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}, {"type": "work_order", "id": O2.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-83 — two W2 orders give one generic entry
- **Rules:** `delete_machine_item` R5a [BUG-1081], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1, but `workspace_id W2.id`.
4. O2 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
5. L2 = source line of O2, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-84 — two W2 lines on one W2 order give one generic entry
- **Rules:** `delete_machine_item` R5a [BUG-1081], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1, but `workspace_id W2.id`.
4. L2 = source line of O1, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-85 — one W2 row of each type gives one generic entry
- **Rules:** `delete_machine_item` R5a [BUG-1081], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1, but `workspace_id W2.id`.
4. O2 = work order of M1, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
5. L2 = replace line of O2, but `workspace_id W2.id`.
6. TO1 = transfer out of M1, but `workspace_id W2.id`, `current_status_id ST9.id`, `destination_location_id F9.id`.
7. TL1 = TO line of TO1, but `workspace_id W2.id`.
8. PO1 = delivered PO to M1, but `workspace_id W2.id`, `current_status_id ST9.id`.
9. POL1 = PO line of PO1, but `workspace_id W2.id`.
10. RT1 = return of PO1, but `workspace_id W2.id`.
11. RL1 = return line of RT1, POL1, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-86 — (a) a COMPLETED order is not listed beside an open one
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, R5b, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "COMPLETED"`.
3. L1 = source line of O1.
4. O2 = work order of M1, `status "DRAFT"`.
5. L2 = source line of O2.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O2.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-87 — (b) a VOIDED order is not listed beside an open one
- **Rules:** `delete_machine_item` R5 (b) [BUG-1081], R5a, R5b, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "VOIDED"`.
3. L1 = replace line of O1.
4. O2 = work order of M1, `status "DRAFT"`.
5. L2 = replace line of O2.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O2.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-88 — (c) a completed transfer is not listed beside an open one
- **Rules:** `delete_machine_item` R5 (c) [BUG-1081], R5a, R5b, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `completed_at T9`.
3. TL1 = TO line of TO1.
4. TO2 = transfer out of M1.
5. TL2 = TO line of TO2.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO2.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-89 — (d) a completed return is not listed beside a pending one
- **Rules:** `delete_machine_item` R5 (d) [BUG-1081], R5a, R5b, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1, but `status "completed"`.
5. RL1 = return line of RT1, POL1.
6. RT2 = return of PO1.
7. RL2 = return line of RT2, POL1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "purchase_return", "id": RT2.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-90 — (a) a W2 order in a closed state adds no generic entry to an own blocker
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, R5b, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "COMPLETED"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1, but `workspace_id W2.id`.
4. O2 = work order of M1, `status "DRAFT"`.
5. L2 = source line of O2.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O2.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-91 — (b) a W2 order in a closed state adds no generic entry to an own blocker
- **Rules:** `delete_machine_item` R5 (b) [BUG-1081], R5a, R5b, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "VOIDED"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = replace line of O1, but `workspace_id W2.id`.
4. O2 = work order of M1, `status "DRAFT"`.
5. L2 = replace line of O2.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O2.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-92 — (c) a completed W2 transfer adds no generic entry to an own blocker
- **Rules:** `delete_machine_item` R5 (c) [BUG-1081], R5a, R5b, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `workspace_id W2.id`, `current_status_id ST9.id`, `destination_location_id F9.id`, `completed_at T9`.
3. TL1 = TO line of TO1, but `workspace_id W2.id`.
4. TO2 = transfer out of M1.
5. TL2 = TO line of TO2.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO2.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-93 — (d) a completed W2 return adds no generic entry to an own blocker
- **Rules:** `delete_machine_item` R5 (d) [BUG-1081], R5a, R5b, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1, but `workspace_id W2.id`, `status "completed"`.
5. RL1 = return line of RT1, POL1, but `workspace_id W2.id`.
6. PO2 = delivered PO to M1.
7. POL2 = PO line of PO2.
8. RT2 = return of PO2.
9. RL2 = return line of RT2, POL2.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "purchase_return", "id": RT2.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-94 — (a) an own closed order adds nothing to a W2 blocker
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, R5b, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "COMPLETED"`.
3. L1 = source line of O1.
4. O2 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
5. L2 = source line of O2, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-95 — (b) an own closed order adds nothing to a W2 blocker
- **Rules:** `delete_machine_item` R5 (b) [BUG-1081], R5a, R5b, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "VOIDED"`.
3. L1 = replace line of O1.
4. O2 = work order of M1, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
5. L2 = replace line of O2, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-96 — (c) an own completed transfer adds nothing to a W2 blocker
- **Rules:** `delete_machine_item` R5 (c) [BUG-1081], R5a, R5b, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `completed_at T9`.
3. TL1 = TO line of TO1.
4. TO2 = transfer out of M1, but `workspace_id W2.id`, `current_status_id ST9.id`, `destination_location_id F9.id`.
5. TL2 = TO line of TO2, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-97 — (d) an own completed return adds nothing to a W2 blocker
- **Rules:** `delete_machine_item` R5 (d) [BUG-1081], R5a, R5b, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1, but `status "completed"`.
5. RL1 = return line of RT1, POL1.
6. PO2 = delivered PO to M1.
7. POL2 = PO line of PO2.
8. RT2 = return of PO2, but `workspace_id W2.id`.
9. RL2 = return line of RT2, POL2, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-98 — a refused row with qty 0 stays and books nothing
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, R5b, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 0`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-99 — a refused row with a negative qty stays and books nothing
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty -3`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.

### MIM-D-100 — a refused row keeps its target and defect count
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. re-read MI: `qty == 5`, `req_qty == 7`, `defective_qty == 1`.

### MIM-D-101 — a refusal leaves earlier ledger rows and events alone
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. LG = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("5.00")`, but `qty_after 5`.
3. EV = activity row of M1.
4. O1 = work order of M1, `status "DRAFT"`.
5. L1 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(LG).
11. unchanged: unchanged(EV).

### MIM-D-102 — an in-use row deleted by an unknown user gets the refusal, not a database error
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, R12, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (the call raises IntegrityError: orders are not looked at and the final adjustment fails on the unknown user)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=MISSING)`, in a plain `pytest.raises(ValueError)`, no savepoint.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(L1).

### MIM-D-103 — a row blocked only by W2 rows, deleted by an unknown user, gets the generic refusal
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, R12, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (the call raises IntegrityError: orders are not looked at and the final adjustment fails on the unknown user)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1, but `workspace_id W2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=MISSING)`, in a plain `pytest.raises(ValueError)`, no savepoint.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(L1).

### MIM-D-104 — R1 before R5: a row asked for from another workspace is the 404, whatever blocks it
- **Rules:** `delete_machine_item` R1, R5, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W2.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.
9. unchanged: unchanged(L1).

### MIM-D-105 — (a) does not block: a `COMPLETED` order
- **Rules:** `delete_machine_item` R5b, R5 (a)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "COMPLETED"`.
3. L1 = source line of O1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-106 — (a) does not block: W2 order and line: a `COMPLETED` order
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "COMPLETED"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-107 — (a) does not block: W1 line on a W2 order: a `COMPLETED` order
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "COMPLETED"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-108 — (a) does not block: W2 line on a W1 order: a `COMPLETED` order
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "COMPLETED"`.
3. L1 = source line of O1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-109 — (a) does not block: a `VOIDED` order
- **Rules:** `delete_machine_item` R5b, R5 (a)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "VOIDED"`.
3. L1 = source line of O1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-110 — (a) does not block: W2 order and line: a `VOIDED` order
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "VOIDED"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-111 — (a) does not block: W1 line on a W2 order: a `VOIDED` order
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "VOIDED"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-112 — (a) does not block: W2 line on a W1 order: a `VOIDED` order
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "VOIDED"`.
3. L1 = source line of O1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-113 — (a) does not block: a soft-deleted order
- **Rules:** `delete_machine_item` R5b, R5 (a)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `is_deleted True`.
3. L1 = source line of O1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-114 — (a) does not block: W2 order and line: a soft-deleted order
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `is_deleted True`.
3. L1 = source line of O1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-115 — (a) does not block: W1 line on a W2 order: a soft-deleted order
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `is_deleted True`.
3. L1 = source line of O1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-116 — (a) does not block: W2 line on a W1 order: a soft-deleted order
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `is_deleted True`.
3. L1 = source line of O1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-117 — (a) does not block: a soft-deleted line
- **Rules:** `delete_machine_item` R5b, R5 (a)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1, but `is_deleted True`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-118 — (a) does not block: W2 order and line: a soft-deleted line
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1, but `workspace_id W2.id`, `is_deleted True`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-119 — (a) does not block: W1 line on a W2 order: a soft-deleted line
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1, but `is_deleted True`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-120 — (a) does not block: W2 line on a W1 order: a soft-deleted line
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1, but `workspace_id W2.id`, `is_deleted True`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-121 — (a) does not block: a line with `uses_inventory False`
- **Rules:** `delete_machine_item` R5b, R5 (a)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1, but `uses_inventory False`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-122 — (a) does not block: W2 order and line: a line with `uses_inventory False`
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1, but `workspace_id W2.id`, `uses_inventory False`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-123 — (a) does not block: W1 line on a W2 order: a line with `uses_inventory False`
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1, but `uses_inventory False`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-124 — (a) does not block: W2 line on a W1 order: a line with `uses_inventory False`
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1, but `workspace_id W2.id`, `uses_inventory False`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-125 — (a) does not block: a consumed line
- **Rules:** `delete_machine_item` R5b, R5 (a)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1, but `consumed_at T9`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-126 — (a) does not block: W2 order and line: a consumed line
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1, but `workspace_id W2.id`, `consumed_at T9`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-127 — (a) does not block: W1 line on a W2 order: a consumed line
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1, but `consumed_at T9`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-128 — (a) does not block: W2 line on a W1 order: a consumed line
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1, but `workspace_id W2.id`, `consumed_at T9`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-129 — (a) does not block: a storage source with the machine's id
- **Rules:** `delete_machine_item` R5b, R5 (a)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1, but `source_location_type "storage"`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-130 — (a) does not block: W2 order and line: a storage source with the machine's id
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1, but `workspace_id W2.id`, `source_location_type "storage"`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-131 — (a) does not block: W1 line on a W2 order: a storage source with the machine's id
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1, but `source_location_type "storage"`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-132 — (a) does not block: W2 line on a W1 order: a storage source with the machine's id
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1, but `workspace_id W2.id`, `source_location_type "storage"`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-133 — (a) does not block: a source on another machine
- **Rules:** `delete_machine_item` R5b, R5 (a)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1, but `source_location_id M2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-134 — (a) does not block: W2 order and line: a source on another machine
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1, but `workspace_id W2.id`, `source_location_id M2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-135 — (a) does not block: W1 line on a W2 order: a source on another machine
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1, but `source_location_id M2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-136 — (a) does not block: W2 line on a W1 order: a source on another machine
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1, but `workspace_id W2.id`, `source_location_id M2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-137 — (a) does not block: a line of another item
- **Rules:** `delete_machine_item` R5b, R5 (a)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1, but `item_id I2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-138 — (a) does not block: W2 order and line: a line of another item
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1, but `workspace_id W2.id`, `item_id I2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-139 — (a) does not block: W1 line on a W2 order: a line of another item
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = source line of O1, but `item_id I2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-140 — (a) does not block: W2 line on a W1 order: a line of another item
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1, but `workspace_id W2.id`, `item_id I2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-141 — (b) does not block: a `COMPLETED` order
- **Rules:** `delete_machine_item` R5b, R5 (b)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "COMPLETED"`.
3. L1 = replace line of O1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-142 — (b) does not block: W2 order and line: a `COMPLETED` order
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "COMPLETED"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = replace line of O1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-143 — (b) does not block: W1 line on a W2 order: a `COMPLETED` order
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "COMPLETED"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = replace line of O1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-144 — (b) does not block: W2 line on a W1 order: a `COMPLETED` order
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "COMPLETED"`.
3. L1 = replace line of O1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-145 — (b) does not block: a `VOIDED` order
- **Rules:** `delete_machine_item` R5b, R5 (b)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "VOIDED"`.
3. L1 = replace line of O1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-146 — (b) does not block: W2 order and line: a `VOIDED` order
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "VOIDED"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = replace line of O1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-147 — (b) does not block: W1 line on a W2 order: a `VOIDED` order
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "VOIDED"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = replace line of O1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-148 — (b) does not block: W2 line on a W1 order: a `VOIDED` order
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "VOIDED"`.
3. L1 = replace line of O1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-149 — (b) does not block: a soft-deleted order
- **Rules:** `delete_machine_item` R5b, R5 (b)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `is_deleted True`.
3. L1 = replace line of O1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-150 — (b) does not block: W2 order and line: a soft-deleted order
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `is_deleted True`.
3. L1 = replace line of O1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-151 — (b) does not block: W1 line on a W2 order: a soft-deleted order
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `is_deleted True`.
3. L1 = replace line of O1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-152 — (b) does not block: W2 line on a W1 order: a soft-deleted order
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `is_deleted True`.
3. L1 = replace line of O1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-153 — (b) does not block: a soft-deleted line
- **Rules:** `delete_machine_item` R5b, R5 (b)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = replace line of O1, but `is_deleted True`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-154 — (b) does not block: W2 order and line: a soft-deleted line
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = replace line of O1, but `workspace_id W2.id`, `is_deleted True`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-155 — (b) does not block: W1 line on a W2 order: a soft-deleted line
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = replace line of O1, but `is_deleted True`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-156 — (b) does not block: W2 line on a W1 order: a soft-deleted line
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = replace line of O1, but `workspace_id W2.id`, `is_deleted True`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-157 — (b) does not block: a line that is not REPLACE
- **Rules:** `delete_machine_item` R5b, R5 (b)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = replace line of O1, but `action_type "INSTALL"`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-158 — (b) does not block: W2 order and line: a line that is not REPLACE
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = replace line of O1, but `workspace_id W2.id`, `action_type "INSTALL"`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-159 — (b) does not block: W1 line on a W2 order: a line that is not REPLACE
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = replace line of O1, but `action_type "INSTALL"`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-160 — (b) does not block: W2 line on a W1 order: a line that is not REPLACE
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = replace line of O1, but `workspace_id W2.id`, `action_type "INSTALL"`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-161 — (b) does not block: a REPLACE line for another item
- **Rules:** `delete_machine_item` R5b, R5 (b)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = replace line of O1, but `replaced_item_id IX.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-162 — (b) does not block: W2 order and line: a REPLACE line for another item
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = replace line of O1, but `workspace_id W2.id`, `replaced_item_id IX.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-163 — (b) does not block: W1 line on a W2 order: a REPLACE line for another item
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = replace line of O1, but `replaced_item_id IX.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-164 — (b) does not block: W2 line on a W1 order: a REPLACE line for another item
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = replace line of O1, but `workspace_id W2.id`, `replaced_item_id IX.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-165 — (b) does not block: an order of another machine
- **Rules:** `delete_machine_item` R5b, R5 (b)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M2, `status "DRAFT"`.
3. L1 = replace line of O1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-166 — (b) does not block: W2 order and line: an order of another machine
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M2, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = replace line of O1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-167 — (b) does not block: W1 line on a W2 order: an order of another machine
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M2, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = replace line of O1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-168 — (b) does not block: W2 line on a W1 order: an order of another machine
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M2, `status "DRAFT"`.
3. L1 = replace line of O1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-169 — (b) does not block: an order with no machine
- **Rules:** `delete_machine_item` R5b, R5 (b)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `machine_id None`.
3. L1 = replace line of O1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-170 — (b) does not block: W2 order and line: an order with no machine
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `machine_id None`.
3. L1 = replace line of O1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-171 — (b) does not block: W1 line on a W2 order: an order with no machine
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `machine_id None`.
3. L1 = replace line of O1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-172 — (b) does not block: W2 line on a W1 order: an order with no machine
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `machine_id None`.
3. L1 = replace line of O1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-173 — (c) does not block: a completed transfer
- **Rules:** `delete_machine_item` R5b, R5 (c)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `completed_at T9`.
3. TL1 = TO line of TO1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(TO1).
5. unchanged: unchanged(TL1).

### MIM-D-174 — (c) does not block: W2 transfer and line: a completed transfer
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `workspace_id W2.id`, `current_status_id ST9.id`, `destination_location_id F9.id`, `completed_at T9`.
3. TL1 = TO line of TO1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(TO1).
5. unchanged: unchanged(TL1).

### MIM-D-175 — (c) does not block: W1 line on a W2 transfer: a completed transfer
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `workspace_id W2.id`, `current_status_id ST9.id`, `destination_location_id F9.id`, `completed_at T9`.
3. TL1 = TO line of TO1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(TO1).
5. unchanged: unchanged(TL1).

### MIM-D-176 — (c) does not block: W2 line on a W1 transfer: a completed transfer
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `completed_at T9`.
3. TL1 = TO line of TO1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(TO1).
5. unchanged: unchanged(TL1).

### MIM-D-177 — (c) does not block: a transfer into the machine
- **Rules:** `delete_machine_item` R5b, R5 (c)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `source_location_type "storage"`, `source_location_id F1.id`, `destination_location_type "machine"`, `destination_location_id M1.id`.
3. TL1 = TO line of TO1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(TO1).
5. unchanged: unchanged(TL1).

### MIM-D-178 — (c) does not block: W2 transfer and line: a transfer into the machine
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `workspace_id W2.id`, `current_status_id ST9.id`, `source_location_type "storage"`, `source_location_id F1.id`, `destination_location_type "machine"`, `destination_location_id M1.id`.
3. TL1 = TO line of TO1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(TO1).
5. unchanged: unchanged(TL1).

### MIM-D-179 — (c) does not block: W1 line on a W2 transfer: a transfer into the machine
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `workspace_id W2.id`, `current_status_id ST9.id`, `source_location_type "storage"`, `source_location_id F1.id`, `destination_location_type "machine"`, `destination_location_id M1.id`.
3. TL1 = TO line of TO1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(TO1).
5. unchanged: unchanged(TL1).

### MIM-D-180 — (c) does not block: W2 line on a W1 transfer: a transfer into the machine
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `source_location_type "storage"`, `source_location_id F1.id`, `destination_location_type "machine"`, `destination_location_id M1.id`.
3. TL1 = TO line of TO1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(TO1).
5. unchanged: unchanged(TL1).

### MIM-D-181 — (c) does not block: a storage source with the machine's id
- **Rules:** `delete_machine_item` R5b, R5 (c)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `source_location_type "storage"`.
3. TL1 = TO line of TO1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(TO1).
5. unchanged: unchanged(TL1).

### MIM-D-182 — (c) does not block: W2 transfer and line: a storage source with the machine's id
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `workspace_id W2.id`, `current_status_id ST9.id`, `destination_location_id F9.id`, `source_location_type "storage"`.
3. TL1 = TO line of TO1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(TO1).
5. unchanged: unchanged(TL1).

### MIM-D-183 — (c) does not block: W1 line on a W2 transfer: a storage source with the machine's id
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `workspace_id W2.id`, `current_status_id ST9.id`, `destination_location_id F9.id`, `source_location_type "storage"`.
3. TL1 = TO line of TO1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(TO1).
5. unchanged: unchanged(TL1).

### MIM-D-184 — (c) does not block: W2 line on a W1 transfer: a storage source with the machine's id
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `source_location_type "storage"`.
3. TL1 = TO line of TO1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(TO1).
5. unchanged: unchanged(TL1).

### MIM-D-185 — (c) does not block: a transfer out of another machine
- **Rules:** `delete_machine_item` R5b, R5 (c)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `source_location_id M2.id`.
3. TL1 = TO line of TO1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(TO1).
5. unchanged: unchanged(TL1).

### MIM-D-186 — (c) does not block: W2 transfer and line: a transfer out of another machine
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `workspace_id W2.id`, `current_status_id ST9.id`, `destination_location_id F9.id`, `source_location_id M2.id`.
3. TL1 = TO line of TO1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(TO1).
5. unchanged: unchanged(TL1).

### MIM-D-187 — (c) does not block: W1 line on a W2 transfer: a transfer out of another machine
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `workspace_id W2.id`, `current_status_id ST9.id`, `destination_location_id F9.id`, `source_location_id M2.id`.
3. TL1 = TO line of TO1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(TO1).
5. unchanged: unchanged(TL1).

### MIM-D-188 — (c) does not block: W2 line on a W1 transfer: a transfer out of another machine
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `source_location_id M2.id`.
3. TL1 = TO line of TO1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(TO1).
5. unchanged: unchanged(TL1).

### MIM-D-189 — (c) does not block: a line of another item
- **Rules:** `delete_machine_item` R5b, R5 (c)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1.
3. TL1 = TO line of TO1, but `item_id I2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(TO1).
5. unchanged: unchanged(TL1).

### MIM-D-190 — (c) does not block: W2 transfer and line: a line of another item
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `workspace_id W2.id`, `current_status_id ST9.id`, `destination_location_id F9.id`.
3. TL1 = TO line of TO1, but `workspace_id W2.id`, `item_id I2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(TO1).
5. unchanged: unchanged(TL1).

### MIM-D-191 — (c) does not block: W1 line on a W2 transfer: a line of another item
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1, but `workspace_id W2.id`, `current_status_id ST9.id`, `destination_location_id F9.id`.
3. TL1 = TO line of TO1, but `item_id I2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(TO1).
5. unchanged: unchanged(TL1).

### MIM-D-192 — (c) does not block: W2 line on a W1 transfer: a line of another item
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. TO1 = transfer out of M1.
3. TL1 = TO line of TO1, but `workspace_id W2.id`, `item_id I2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(TO1).
5. unchanged: unchanged(TL1).

### MIM-D-193 — (d) does not block: a `completed` return
- **Rules:** `delete_machine_item` R5b, R5 (d)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1, but `status "completed"`.
5. RL1 = return line of RT1, POL1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(RT1).
5. unchanged: unchanged(RL1).

### MIM-D-194 — (d) does not block: all of W2: a `completed` return
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1, but `workspace_id W2.id`, `current_status_id ST9.id`.
3. POL1 = PO line of PO1, but `workspace_id W2.id`.
4. RT1 = return of PO1, but `workspace_id W2.id`, `status "completed"`.
5. RL1 = return line of RT1, POL1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(RT1).
5. unchanged: unchanged(RL1).

### MIM-D-195 — (d) does not block: W1 line on a W2 return: a `completed` return
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1, but `workspace_id W2.id`, `status "completed"`.
5. RL1 = return line of RT1, POL1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(RT1).
5. unchanged: unchanged(RL1).

### MIM-D-196 — (d) does not block: W2 line on a W1 return: a `completed` return
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1, but `status "completed"`.
5. RL1 = return line of RT1, POL1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(RT1).
5. unchanged: unchanged(RL1).

### MIM-D-197 — (d) does not block: a `voided` return
- **Rules:** `delete_machine_item` R5b, R5 (d)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1, but `status "voided"`.
5. RL1 = return line of RT1, POL1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(RT1).
5. unchanged: unchanged(RL1).

### MIM-D-198 — (d) does not block: all of W2: a `voided` return
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1, but `workspace_id W2.id`, `current_status_id ST9.id`.
3. POL1 = PO line of PO1, but `workspace_id W2.id`.
4. RT1 = return of PO1, but `workspace_id W2.id`, `status "voided"`.
5. RL1 = return line of RT1, POL1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(RT1).
5. unchanged: unchanged(RL1).

### MIM-D-199 — (d) does not block: W1 line on a W2 return: a `voided` return
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1, but `workspace_id W2.id`, `status "voided"`.
5. RL1 = return line of RT1, POL1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(RT1).
5. unchanged: unchanged(RL1).

### MIM-D-200 — (d) does not block: W2 line on a W1 return: a `voided` return
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1, but `status "voided"`.
5. RL1 = return line of RT1, POL1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(RT1).
5. unchanged: unchanged(RL1).

### MIM-D-201 — (d) does not block: a purchase order into storage with the machine's id
- **Rules:** `delete_machine_item` R5b, R5 (d)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1, but `destination_type "storage"`.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1.
5. RL1 = return line of RT1, POL1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(RT1).
5. unchanged: unchanged(RL1).

### MIM-D-202 — (d) does not block: all of W2: a purchase order into storage with the machine's id
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1, but `workspace_id W2.id`, `current_status_id ST9.id`, `destination_type "storage"`.
3. POL1 = PO line of PO1, but `workspace_id W2.id`.
4. RT1 = return of PO1, but `workspace_id W2.id`.
5. RL1 = return line of RT1, POL1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(RT1).
5. unchanged: unchanged(RL1).

### MIM-D-203 — (d) does not block: W1 line on a W2 return: a purchase order into storage with the machine's id
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1, but `destination_type "storage"`.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1, but `workspace_id W2.id`.
5. RL1 = return line of RT1, POL1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(RT1).
5. unchanged: unchanged(RL1).

### MIM-D-204 — (d) does not block: W2 line on a W1 return: a purchase order into storage with the machine's id
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1, but `destination_type "storage"`.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1.
5. RL1 = return line of RT1, POL1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(RT1).
5. unchanged: unchanged(RL1).

### MIM-D-205 — (d) does not block: a purchase order to another machine
- **Rules:** `delete_machine_item` R5b, R5 (d)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1, but `destination_id M2.id`.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1.
5. RL1 = return line of RT1, POL1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(RT1).
5. unchanged: unchanged(RL1).

### MIM-D-206 — (d) does not block: all of W2: a purchase order to another machine
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1, but `workspace_id W2.id`, `current_status_id ST9.id`, `destination_id M2.id`.
3. POL1 = PO line of PO1, but `workspace_id W2.id`.
4. RT1 = return of PO1, but `workspace_id W2.id`.
5. RL1 = return line of RT1, POL1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(RT1).
5. unchanged: unchanged(RL1).

### MIM-D-207 — (d) does not block: W1 line on a W2 return: a purchase order to another machine
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1, but `destination_id M2.id`.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1, but `workspace_id W2.id`.
5. RL1 = return line of RT1, POL1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(RT1).
5. unchanged: unchanged(RL1).

### MIM-D-208 — (d) does not block: W2 line on a W1 return: a purchase order to another machine
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1, but `destination_id M2.id`.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1.
5. RL1 = return line of RT1, POL1, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(RT1).
5. unchanged: unchanged(RL1).

### MIM-D-209 — (d) does not block: a return line of another item
- **Rules:** `delete_machine_item` R5b, R5 (d)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1.
5. RL1 = return line of RT1, POL1, but `item_id I2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(RT1).
5. unchanged: unchanged(RL1).

### MIM-D-210 — (d) does not block: all of W2: a return line of another item
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1, but `workspace_id W2.id`, `current_status_id ST9.id`.
3. POL1 = PO line of PO1, but `workspace_id W2.id`.
4. RT1 = return of PO1, but `workspace_id W2.id`.
5. RL1 = return line of RT1, POL1, but `workspace_id W2.id`, `item_id I2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(RT1).
5. unchanged: unchanged(RL1).

### MIM-D-211 — (d) does not block: W1 line on a W2 return: a return line of another item
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1, but `workspace_id W2.id`.
5. RL1 = return line of RT1, POL1, but `item_id I2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(RT1).
5. unchanged: unchanged(RL1).

### MIM-D-212 — (d) does not block: W2 line on a W1 return: a return line of another item
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1.
3. POL1 = PO line of PO1.
4. RT1 = return of PO1.
5. RL1 = return line of RT1, POL1, but `workspace_id W2.id`, `item_id I2.id`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(RT1).
5. unchanged: unchanged(RL1).

### MIM-D-213 — the row's own quantities do not block
- **Rules:** `delete_machine_item` R5b, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.

### MIM-D-214 — a purchase order into the machine with no return does not block
- **Rules:** `delete_machine_item` R5b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1, but `current_status_id STD.id`.
3. POL1 = PO line of PO1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(PO1).
5. unchanged: unchanged(POL1).

### MIM-D-215 — earlier ledger rows and activity do not block and stay
- **Rules:** `delete_machine_item` R5b, R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. LG = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("0.00")`, but `qty_after 5`.
3. EV = activity row of M1.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. unchanged: unchanged(LG).
4. unchanged: unchanged(EV).
5. count: `entries_of(M1, I1)` has exactly 2 rows.

### MIM-D-216 — qty above 0 books one final adjustment to 0
- **Rules:** `delete_machine_item` R6, Returns
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `entries_of(M1, I1)` has exactly 1 row.
4. re-read `entries_of(M1, I1)[-1]`: `transaction_type == "inventory_adjustment"`, `quantity == 5`.
5. re-read `entries_of(M1, I1)[-1]`: `qty_before == 5`, `qty_after == 0`.
6. re-read `entries_of(M1, I1)[-1]`: `source_type == "adjustment"`, `notes == "Machine inventory record deleted"`.
7. re-read `entries_of(M1, I1)[-1]`: `performed_by == U2.id`, `workspace_id == W1.id`.
8. re-read `entries_of(M1, I1)[-1]`: `unit_cost == Decimal("0.00")`, `total_cost == Decimal("0.00")`.
9. re-read `entries_of(M1, I1)[-1]`: `value_before == Decimal("0.00")`, `value_after == Decimal("0.00")`.
10. re-read `entries_of(M1, I1)[-1]`: `avg_price_before == Decimal("0.00")`, `avg_price_after == Decimal("0.00")`.

### MIM-D-217 — the final adjustment writes its inventory_adjusted event
- **Rules:** `delete_machine_item` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. event: the `inventory_adjusted` row: `description == "Inventory adjusted on Bolt M8: 5 → 0"`.
3. event: the `inventory_adjusted` row: `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == M1.id`.
4. event: the `inventory_adjusted` row: `metadata_json == {"item_id": I1.id, "item_name": "Bolt M8", "quantity": 5, "changes": [{"field": "qty", "label": "Quantity", "from_value": "5", "to_value": "0"}]}`.

### MIM-D-218 — the final adjustment is valued at the current average
- **Rules:** `delete_machine_item` R6, `_write_ledger_entry` R2 [BUG-993], R3, R4
- **Kind:** bug
- **Expect:** xfail BUG-993
- **Fails today on:** Then 2 (today every cost field is 0.00)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. LG = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("3.00")`, but `qty_after 5`, `value_after Decimal("15.00")`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. re-read `entries_of(M1, I1)[-1]`: `unit_cost == Decimal("3.00")`, `avg_price_before == Decimal("3.00")`, `avg_price_after == Decimal("3.00")`.
3. re-read `entries_of(M1, I1)[-1]`: `total_cost == Decimal("15.00")`, `value_before == Decimal("15.00")`, `value_after == Decimal("0.00")`.

### MIM-D-219 — after the delete the ledger balance is 0
- **Rules:** `delete_machine_item` R6, `_write_ledger_entry` R9
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. LG = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("3.00")`, but `qty_after 5`, `value_after Decimal("15.00")`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. returns: `machine_item_ledger_dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id) == (0, Decimal("0.00"))`.

### MIM-D-220 — qty 0 books no ledger entry
- **Rules:** `delete_machine_item` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 0`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 0 rows.
4. event: events_of(M1) has exactly 1 row.

### MIM-D-221 — qty below 0 books the same final adjustment
- **Rules:** `delete_machine_item` R8 [BUG-1080]
- **Kind:** bug
- **Expect:** xfail BUG-1080
- **Fails today on:** Then 3 (no ledger entry is written for a negative row)

**Given**
1. MI = stock of M1, I1, `qty -3`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `entries_of(M1, I1)` has exactly 1 row.
4. re-read `entries_of(M1, I1)[-1]`: `transaction_type == "inventory_adjustment"`, `quantity == 3`.
5. re-read `entries_of(M1, I1)[-1]`: `qty_before == -3`, `qty_after == 0`.
6. re-read `entries_of(M1, I1)[-1]`: `source_type == "adjustment"`, `notes == "Machine inventory record deleted"`.

### MIM-D-222 — qty below 0 writes the inventory_adjusted event
- **Rules:** `delete_machine_item` R8 [BUG-1080], R12
- **Kind:** bug
- **Expect:** xfail BUG-1080
- **Fails today on:** Then 2 (no ledger entry and no event are written for a negative row)

**Given**
1. MI = stock of M1, I1, `qty -3`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. event: events_of(M1) with `event_type == "inventory_adjusted"` has exactly 1 row.
3. event: the `inventory_adjusted` row: `description == "Inventory adjusted on Bolt M8: -3 → 0"`.

### MIM-D-223 — qty below 0: the ledger ends at 0
- **Rules:** `delete_machine_item` R8 [BUG-1080]
- **Kind:** bug
- **Expect:** xfail BUG-1080
- **Fails today on:** Then 2 (the balance stays -3)

**Given**
1. MI = stock of M1, I1, `qty -3`.
2. LG = entry of M1, I1, `performed_at T9`, `avg_price_after Decimal("5.00")`, but `qty_after -3`, `value_after Decimal("-15.00")`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. returns: `machine_item_ledger_dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id) == (0, Decimal("0.00"))`.

### MIM-D-224 — a row with qty below 0 is still deleted, with its item_removed event
- **Rules:** `delete_machine_item` R8, R9, R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty -3`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. event: events_of(M1) with `event_type == "item_removed"` has exactly 1 row.

### MIM-D-225 — one item_removed event with qty 5
- **Rules:** `delete_machine_item` R9
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. event: events_of(M1) with `event_type == "item_removed"` has exactly 1 row.
3. event: the `item_removed` row: `description == "Item removed: Bolt M8"`.
4. event: the `item_removed` row: `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == M1.id`.
5. event: the `item_removed` row: `metadata_json == {"item_id": I1.id, "item_name": "Bolt M8", "machine_item_id": MI.id}`.
6. event: events_of(M1) has exactly 2 rows.

### MIM-D-226 — one item_removed event with qty 0
- **Rules:** `delete_machine_item` R9
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 0`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. event: events_of(M1) with `event_type == "item_removed"` has exactly 1 row.
3. event: the `item_removed` row: `description == "Item removed: Bolt M8"`.
4. event: the `item_removed` row: `performed_by == U2.id`, `workspace_id == W1.id`, `machine_id == M1.id`.
5. event: the `item_removed` row: `metadata_json == {"item_id": I1.id, "item_name": "Bolt M8", "machine_item_id": MI.id}`.
6. event: events_of(M1) has exactly 1 row.

### MIM-D-227 — only this row goes: the machine's other rows and the item's rows elsewhere stay
- **Rules:** `delete_machine_item` R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. A = stock of M1, I2, `qty 2`.
3. B = stock of M2, I1, `qty 3`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. unchanged: unchanged(A).
4. unchanged: unchanged(B).
5. count: `machine_items` has exactly 2 rows.

### MIM-D-228 — the target and defect count go with the row
- **Rules:** `delete_machine_item` R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 0`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_items` has exactly 0 rows.

### MIM-D-229 — a later create for the pair gets a new row id
- **Rules:** `delete_machine_item` R10, `create_machine_item` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. `old_id = MI.id`.
3. `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`, then `db.flush()`.

**When**
- `result = M.create_machine_item(db, item_data=MachineItemCreate(machine_id=M1.id, item_id=I1.id, qty=4), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id != old_id`.
2. re-read the returned row: `qty == 4`.
3. count: `machine_items` with `id == old_id` has exactly 0 rows.

### MIM-D-230 — a stored row with another workspace's item is not found
- **Rules:** `delete_machine_item` R11 [BUG-1086], Errors row 1, `_item_name` R3 [BUG-1086]
- **Kind:** bug
- **Expect:** xfail BUG-1086
- **Fails today on:** Then 1 (no error is raised: the row is deleted and its events say `Item #<item_id>`)

**Given**
1. MI = stock of M1, I9, `qty 5`. (A row of W1 with an item of W2, invalid data.)

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-D-231 — not found wins over the deleted-machine refusal for such a row
- **Rules:** `delete_machine_item` R11 [BUG-1086], R2 [BUG-1084], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1086
- **Fails today on:** Then 1 (no error is raised: the row is deleted and its events say `Item #<item_id>`)

**Given**
1. MI = stock of MX, I9, `qty 5`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.

### MIM-D-232 — not found wins over the open-order refusal for such a row
- **Rules:** `delete_machine_item` R11 [BUG-1086], R5 [BUG-1081], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1086
- **Fails today on:** Then 1 (no error is raised: the row is deleted and its events say `Item #<item_id>`)

**Given**
1. MI = stock of M1, I9, `qty 5`. (A row of W1 with an item of W2, invalid data.)
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1, but `item_id I9.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine item not found"`.
4. session: `MI not in db.dirty`.
5. session: `MI not in db.deleted`.
6. session: `db.flush()` runs and raises nothing.
7. unchanged: unchanged(MI).
8. nothing written: nothing written.
9. unchanged: unchanged(L1).

### MIM-D-233 — an unknown user with qty above 0 fails on the ledger
- **Rules:** `delete_machine_item` R12, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.diag.constraint_name == "machine_item_ledger_performed_by_fkey"`.
4. unchanged: unchanged(MI).
5. nothing written: nothing written.

### MIM-D-234 — an unknown user with qty 0 fails on the activity entry
- **Rules:** `delete_machine_item` R12, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 0`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.diag.constraint_name == "machine_activity_events_performed_by_fkey"`.
4. unchanged: unchanged(MI).
5. nothing written: nothing written.

### MIM-D-235 — an unknown user with qty below 0 fails on the ledger
- **Rules:** `delete_machine_item` R12 [BUG-1080], R8, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-1080
- **Fails today on:** Then 3 (no ledger entry is tried, so the activity entry's key fails first)

**Given**
1. MI = stock of M1, I1, `qty -3`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.diag.constraint_name == "machine_item_ledger_performed_by_fkey"`.
4. unchanged: unchanged(MI).

### MIM-D-236 — an unknown user with qty below 0 leaves the row in place
- **Rules:** `delete_machine_item` R12, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty -3`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. unchanged: unchanged(MI).
4. nothing written: nothing written.

### MIM-D-237 — the delete is flushed but not committed
- **Rules:** `delete_machine_item` R13
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. Savepoint and commit spy per **rolled back**.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. event: events_of(M1) has exactly 2 rows.
5. re-read MI after the savepoint rollback: `qty == 5`.
6. count after the savepoint rollback: `machine_item_ledger` has exactly 0 rows.
7. count after the savepoint rollback: `machine_activity_events` has exactly 0 rows.
8. mock called: the `db.commit` spy was never called.

### MIM-D-238 — (b) does not block: a line with `uses_inventory False`
- **Rules:** `delete_machine_item` R5b, R5 (b)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = replace line of O1, but `uses_inventory False`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-239 — (b) does not block: W2 order and line: a line with `uses_inventory False`
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = replace line of O1, but `workspace_id W2.id`, `uses_inventory False`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-240 — (b) does not block: W1 line on a W2 order: a line with `uses_inventory False`
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
3. L1 = replace line of O1, but `uses_inventory False`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-241 — (b) does not block: W2 line on a W1 order: a line with `uses_inventory False`
- **Rules:** `delete_machine_item` R5b, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = replace line of O1, but `workspace_id W2.id`, `uses_inventory False`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `machine_item_ledger` has exactly 1 row.
4. unchanged: unchanged(O1).
5. unchanged: unchanged(L1).

### MIM-D-242 — (d) a W1 return and line on a purchase order of W2 show only the generic entry
- **Rules:** `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. PO1 = delivered PO to M1, but `workspace_id W2.id`, `current_status_id ST9.id`.
3. POL1 = PO line of PO1, but `workspace_id W2.id`.
4. RT1 = return of PO1.
5. RL1 = return line of RT1, POL1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(PO1).
11. unchanged: unchanged(RT1).
12. unchanged: unchanged(RL1).

### MIM-D-243 — (c) the stage is not read: a transfer at stage Cancelled with completed_at empty blocks
- **Rules:** `delete_machine_item` R5 (c) [BUG-1081], R5a, R5b, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. STX = `statuses` row: `name "Cancelled"`, `comment "stage"`, `workspace_id W1.id`.
3. TO1 = transfer out of M1, but `current_status_id STX.id`.
4. TL1 = TO line of TO1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(TO1).

### MIM-D-244 — (d) the stage is not read: a purchase order at stage Planning with a pending return blocks
- **Rules:** `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. STP = `statuses` row: `name "Planning"`, `comment "stage"`, `workspace_id W1.id`.
3. PO1 = delivered PO to M1, but `current_status_id STP.id`.
4. POL1 = PO line of PO1.
5. RT1 = return of PO1.
6. RL1 = return line of RT1, POL1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "purchase_return", "id": RT1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(RT1).

### MIM-D-245 — (d) the stage is not read: a purchase order at stage Receiving with a pending return blocks
- **Rules:** `delete_machine_item` R5 (d) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. STR = `statuses` row: `name "Receiving"`, `comment "stage"`, `workspace_id W1.id`.
3. PO1 = delivered PO to M1, but `current_status_id STR.id`.
4. POL1 = PO line of PO1.
5. RT1 = return of PO1.
6. RL1 = return line of RT1, POL1.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "purchase_return", "id": RT1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(RT1).

### MIM-D-246 — qty 1 books a final adjustment
- **Rules:** `delete_machine_item` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI = stock of M1, I1, `qty 1`.

**When**
- `result = M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` with `id == MI.id` has exactly 0 rows.
3. count: `entries_of(M1, I1)` has exactly 1 row.
4. re-read `entries_of(M1, I1)[-1]`: `transaction_type == "inventory_adjustment"`, `quantity == 1`.
5. re-read `entries_of(M1, I1)[-1]`: `qty_before == 1`, `qty_after == 0`.

### MIM-D-247 — (a) an INSTALL line sourcing this item from this machine blocks
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1, but `action_type "INSTALL"`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(L1).

### MIM-D-248 — (a) a BORROW line sourcing this item from this machine blocks
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1, but `action_type "BORROW"`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(L1).

### MIM-D-249 — (a) a REPLACE line sourcing this item from this machine blocks
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1, but `action_type "REPLACE"`, `replaced_item_id I2.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(L1).

### MIM-D-250 — one line that meets both (a) and (b) gives one entry for the order
- **Rules:** `delete_machine_item` R5 (a) [BUG-1081], R5 (b) [BUG-1081], R5a, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1081
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the row is deleted)

**Given**
1. MI = stock of M1, I1, `qty 5`.
2. O1 = work order of M1, `status "DRAFT"`.
3. L1 = source line of O1, but `action_type "REPLACE"`, `replaced_item_id I1.id`.

**When**
- `M.delete_machine_item(db, machine_item_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine item has open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. session: `MI not in db.dirty`.
6. session: `MI not in db.deleted`.
7. session: `db.flush()` runs and raises nothing.
8. unchanged: unchanged(MI).
9. nothing written: nothing written.
10. unchanged: unchanged(O1).
11. unchanged: unchanged(L1).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| every `HTTPException` refusal | `POST`, `PUT`, `DELETE`, `GET /machine-items/` (integration) | the HTTP status reaches the client |
| `delete_machine_item` R5a; FU-1 (a) | `MachineItemService.delete_machine_item` | the `ValueError` becomes a 400 with `errors` = the blockers, not a 500 |
| `get_machine_item` R3a; FU-1 (b) | `GET /machine-items/{id}/` | `include_deleted` is reachable from the API |
| `create_machine_item` R8; FU-1 (c) | global `IntegrityError` handler (integration) | a lost race answers the exact 409 message, not the generic one |
| `create_machine_item` R12 … R14, `update_machine_item` R6, R13, R14 | `POST`, `PUT /machine-items/` | schema errors at the API: 400 today (BUG-461), 422 intended |
| `list_machine_items` R5, R6; HR-7 | `GET /machine-items/` | `skip >= 0`, `1 <= limit <= 1000` |
| `create_machine_item` R17, `update_machine_item` R17, `delete_machine_item` R13 | `MachineItemService` | the service's commit, rollback and `db.refresh` |
| `update_machine_item` R4, `delete_machine_item` R4; BUG-1072, BUG-1073 | integration | two real concurrent transactions; here only the emitted `FOR UPDATE` |
| `create_machine_item` R8; BUG-983 | `tests/unit/dao/machine_item.spec.md` | the unique index itself, and `scripts/merge_duplicate_machine_items.py` before it |
| BUG-976 order alarm | `tests/unit/dao/machine_item.cases.md` MIT-GM-36 | the strict `ORDER BY` recorder of the `machine_id` path; here one non-strict pass-through |
| BUG-100, BUG-664 | `tests/unit/dao/machine_item.spec.md`, `tests/unit/dao/machine_item_ledger.spec.md` | cited, reached through this manager; no rule of this module |
| BUG-1082; FU-4 | frontend `MachineDetailBody.tsx` | the refusal shows the blockers |
| `delete_machine_item` R5 (b), (d); FU-10 | work order and purchase order services (not yet specified) | `REPLACE` completion with no stock row; a pending return on a voided order can still be completed |
| Q1, Q2a | `scripts/repair_machine_zero_average.py`, `scripts/restate_half_even_averages.py` | one-off scripts, tested by the describer on `marker_test`; not part of this module |

## Spec gaps
None open. Gaps 1–9 of revision 1 are closed by the spec.

| # | Where | Closed by | Effect on the cards |
|---|---|---|---|
| 1 | `delete_machine_item` R5a, (d) **[order]** | G1 | A W1 return and line on a W2 purchase order give the generic entry: new card MIM-D-242. The W2 stage and W2 purchase order line cards keep the normal entry (R5a). |
| 2 | `delete_machine_item` R5 (c), (d), R5b **[order]** | G2 | Transfers and returns have no soft-delete or cancel state, so no card is missing. New card MIM-D-243: a transfer at stage `Cancelled` with `completed_at` empty blocks. |
| 3 | `delete_machine_item` R5 (a), (b), (c) **[order]** | G3 | The parent-state cards stand under the owner's `delete_machine` G12 answer, applied in R5. |
| 4 | `delete_machine_item` R5 (b) **[order, stock]** | G4 | A `REPLACE` line blocks with `uses_inventory True`, consumed or not; with `False` it does not. Recipe changed, MIM-D-30 retitled, MIM-D-31 retired, MIM-D-238 … MIM-D-241 added. |
| 5 | `delete_machine_item` R5 (d) **[order]** | G5 | A pending return blocks whatever the purchase order's state. New cards MIM-D-244, MIM-D-245; Draft is MIM-D-39, voided MIM-D-38, Complete the recipe default in MIM-D-24. |
| 6 | `_write_ledger_entry` R3, R4 **[money]** | G6 | `value_before`, `value_after` round half up, tagged BUG-1040: new card MIM-W-32. |
| 7 | `delete_machine_item` R5a | G7 | `created_by` is NOT NULL and the rows insert: `Executor confirm` removed. |
| 8 | `delete_machine_item` R5 (b), R5b | G8 | `INSTALL` is a valid `action_type`. |
| 9 | `create_machine_item` R8 | G9 | MIM-C-25 patches the method on `M.machine_item_dao`. |

## Retired IDs
| ID | Why |
|---|---|
| MIM-D-31 | duplicated the `replace line` recipe once it set `uses_inventory True` (spec G4): every blocking (b) card now proves what it proved. MIM-D-30 is the nearest card. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_item_name` | R1 | MIM-IN-01 |
| `_item_name` | R2 | MIM-IN-02 MIM-W-27 |
| `_item_name` | R3 | MIM-U-59 MIM-D-230 |
| `get_machine_item` | R1 | MIM-G-01 MIM-G-02 |
| `get_machine_item` | R2 | MIM-G-03 MIM-G-04 MIM-G-05 MIM-G-13 MIM-G-14 MIM-G-20 |
| `get_machine_item` | R3 | MIM-G-06 MIM-G-08 MIM-G-10 |
| `get_machine_item` | R3a | MIM-G-07 MIM-G-09 MIM-G-11 MIM-G-12 MIM-G-13 MIM-G-14 MIM-G-19 |
| `get_machine_item` | R4 | MIM-G-15 MIM-G-16 |
| `get_machine_item` | R5 | MIM-G-17 |
| `get_machine_item` | R6 | MIM-G-18 MIM-G-19 MIM-G-20 |
| `get_machine_item` | Errors row 1 | MIM-G-03 MIM-G-04 MIM-G-05 MIM-G-06 MIM-G-08 MIM-G-10 MIM-G-13 MIM-G-14 MIM-G-18 MIM-G-19 MIM-G-20 |
| `list_machine_items` | R1 | MIM-L-01 MIM-L-02 MIM-L-03 MIM-L-04 MIM-L-05 MIM-L-48 MIM-L-50 |
| `list_machine_items` | R2 | MIM-L-06 MIM-L-07 MIM-L-08 MIM-L-09 |
| `list_machine_items` | R3 | MIM-L-10 MIM-L-11 |
| `list_machine_items` | R4 | MIM-L-11 MIM-L-12 MIM-L-13 MIM-L-14 |
| `list_machine_items` | R5 | MIM-L-15 MIM-L-16 MIM-L-17 MIM-L-18 MIM-L-19 MIM-L-20 MIM-L-21 MIM-L-22 MIM-L-23 MIM-L-24 MIM-L-27 MIM-L-28 MIM-L-29 MIM-L-30 MIM-L-31 MIM-L-32 MIM-L-33 MIM-L-34 MIM-L-35 MIM-L-36 |
| `list_machine_items` | R6 | MIM-L-25 MIM-L-26 MIM-L-37 MIM-L-38 |
| `list_machine_items` | R7 | MIM-L-39 MIM-L-40 MIM-L-41 MIM-L-42 MIM-L-43 MIM-L-44 MIM-L-45 MIM-L-46 MIM-L-67 MIM-L-68 |
| `list_machine_items` | R7a | MIM-L-47 MIM-L-48 MIM-L-49 MIM-L-50 MIM-L-51 MIM-L-52 MIM-L-53 MIM-L-54 |
| `list_machine_items` | R8 | MIM-L-55 MIM-L-56 MIM-L-57 MIM-L-58 MIM-L-59 |
| `list_machine_items` | R9 | MIM-L-60 MIM-L-61 MIM-L-63 MIM-L-64 MIM-L-69 MIM-L-70 |
| `list_machine_items` | R10 | MIM-L-51 MIM-L-62 MIM-L-65 MIM-L-66 |
| `list_machine_items` | Errors row 1 | MIM-L-25 MIM-L-37 |
| `list_machine_items` | Errors row 2 | MIM-L-26 MIM-L-38 |
| `_write_ledger_entry` | R1 | MIM-W-01 MIM-W-02 MIM-W-03 MIM-W-23 |
| `_write_ledger_entry` | R2 | MIM-W-04 MIM-W-05 MIM-W-18 MIM-W-19 MIM-W-20 MIM-C-31 MIM-C-32 MIM-U-38 MIM-D-218 |
| `_write_ledger_entry` | R3 | MIM-W-05 MIM-W-06 MIM-W-07 MIM-W-08 MIM-W-09 MIM-C-31 MIM-U-38 MIM-U-39 MIM-D-218 |
| `_write_ledger_entry` | R4 | MIM-W-05 MIM-W-10 MIM-W-11 MIM-W-32 MIM-W-33 MIM-C-31 MIM-U-38 MIM-D-218 |
| `_write_ledger_entry` | R5 | MIM-W-12 MIM-W-13 MIM-W-14 MIM-W-15 MIM-U-37 |
| `_write_ledger_entry` | R6 | MIM-W-16 |
| `_write_ledger_entry` | R7 | MIM-W-17 |
| `_write_ledger_entry` | R8 | MIM-W-18 MIM-W-19 MIM-W-20 |
| `_write_ledger_entry` | R9 | MIM-W-21 MIM-W-22 MIM-W-23 MIM-W-24 MIM-W-25 MIM-D-219 |
| `_write_ledger_entry` | R10 | MIM-W-26 MIM-W-27 MIM-U-43 |
| `_write_ledger_entry` | R11 | MIM-W-28 |
| `_write_ledger_entry` | R12 | MIM-W-29 MIM-W-30 |
| `_write_ledger_entry` | R13 | MIM-W-31 |
| `_write_ledger_entry` | Errors row 1 | MIM-W-29 MIM-W-30 |
| `create_machine_item` | R1 | MIM-C-01 MIM-C-02 MIM-C-03 MIM-C-13 |
| `create_machine_item` | R2 | MIM-C-04 MIM-C-14 MIM-C-15 |
| `create_machine_item` | R3 | MIM-C-05 MIM-C-16 |
| `create_machine_item` | R4 | MIM-C-06 MIM-C-07 MIM-C-21 |
| `create_machine_item` | R5 | MIM-C-08 MIM-C-09 MIM-C-10 MIM-C-13 MIM-C-14 MIM-C-16 MIM-C-17 |
| `create_machine_item` | R6 | MIM-C-11 MIM-C-12 MIM-C-15 MIM-C-18 |
| `create_machine_item` | R7 | MIM-C-17 MIM-C-18 MIM-C-19 MIM-C-20 MIM-C-21 MIM-C-22 MIM-C-23 MIM-C-24 |
| `create_machine_item` | R8 | MIM-C-25 |
| `create_machine_item` | R9 | MIM-C-26 MIM-C-27 |
| `create_machine_item` | R10 | MIM-C-28 MIM-C-29 MIM-C-30 MIM-C-31 MIM-C-32 MIM-D-229 |
| `create_machine_item` | R11 | MIM-C-27 MIM-C-33 MIM-C-34 |
| `create_machine_item` | R12 | MIM-C-35 MIM-C-36 MIM-C-46 |
| `create_machine_item` | R13 | MIM-C-38 MIM-C-39 MIM-C-41 MIM-C-42 MIM-C-44 MIM-C-45 |
| `create_machine_item` | R14 | MIM-C-37 MIM-C-40 MIM-C-43 MIM-C-47 |
| `create_machine_item` | R15 | MIM-C-48 MIM-C-49 |
| `create_machine_item` | R16 | MIM-C-50 MIM-C-51 |
| `create_machine_item` | R17 | MIM-C-52 |
| `create_machine_item` | Errors row 1 | MIM-C-01 MIM-C-02 MIM-C-03 MIM-C-13 |
| `create_machine_item` | Errors row 2 | MIM-C-04 MIM-C-05 MIM-C-14 MIM-C-15 MIM-C-16 |
| `create_machine_item` | Errors row 3 | MIM-C-08 MIM-C-09 MIM-C-10 MIM-C-17 |
| `create_machine_item` | Errors row 4 | MIM-C-11 MIM-C-12 MIM-C-18 |
| `create_machine_item` | Errors row 5 | MIM-C-19 MIM-C-20 MIM-C-21 MIM-C-25 |
| `create_machine_item` | Errors row 6 | MIM-C-35 MIM-C-37 MIM-C-38 MIM-C-40 MIM-C-41 MIM-C-43 |
| `create_machine_item` | Errors row 7 | MIM-C-50 MIM-C-51 |
| `update_machine_item` | R1 | MIM-U-01 MIM-U-02 MIM-U-03 |
| `update_machine_item` | R2 | MIM-U-04 MIM-U-05 MIM-U-06 MIM-U-07 MIM-U-08 MIM-U-09 MIM-U-10 MIM-U-11 MIM-U-12 MIM-U-13 MIM-U-61 |
| `update_machine_item` | R3 | MIM-U-14 |
| `update_machine_item` | R4 | MIM-U-15 |
| `update_machine_item` | R5 | MIM-U-16 MIM-U-17 MIM-U-18 MIM-U-19 MIM-U-20 MIM-U-21 MIM-U-22 MIM-U-25 |
| `update_machine_item` | R6 | MIM-U-16 MIM-U-17 MIM-U-18 MIM-U-23 MIM-U-24 MIM-U-25 MIM-U-26 MIM-U-27 |
| `update_machine_item` | R7 | MIM-U-27 MIM-U-28 MIM-U-29 MIM-U-30 MIM-U-31 MIM-U-32 |
| `update_machine_item` | R8 | MIM-W-21 MIM-W-23 MIM-U-14 MIM-U-33 MIM-U-34 MIM-U-35 MIM-U-36 MIM-U-37 MIM-U-38 MIM-U-39 MIM-U-56 MIM-U-57 |
| `update_machine_item` | R9 | MIM-U-40 |
| `update_machine_item` | R10 | MIM-U-41 MIM-U-42 |
| `update_machine_item` | R11 | MIM-U-43 |
| `update_machine_item` | R12 | MIM-U-14 MIM-U-20 MIM-U-21 MIM-U-22 MIM-U-23 MIM-U-24 MIM-U-40 MIM-U-41 MIM-U-42 MIM-U-43 MIM-U-44 MIM-U-45 MIM-U-46 |
| `update_machine_item` | R13 | MIM-U-47 MIM-U-48 MIM-U-50 MIM-U-51 MIM-U-53 MIM-U-54 MIM-U-56 MIM-U-57 |
| `update_machine_item` | R14 | MIM-U-49 MIM-U-52 MIM-U-55 MIM-U-58 |
| `update_machine_item` | R15 | MIM-U-59 MIM-U-60 MIM-U-61 |
| `update_machine_item` | R16 | MIM-U-07 MIM-U-11 MIM-U-62 MIM-U-63 |
| `update_machine_item` | R17 | MIM-U-64 |
| `update_machine_item` | Errors row 1 | MIM-U-01 MIM-U-02 MIM-U-03 MIM-U-59 MIM-U-60 MIM-U-61 |
| `update_machine_item` | Errors row 2 | MIM-U-04 MIM-U-05 MIM-U-06 MIM-U-07 MIM-U-08 MIM-U-09 MIM-U-10 MIM-U-11 |
| `update_machine_item` | Errors row 3 | MIM-U-26 MIM-U-47 MIM-U-49 MIM-U-50 MIM-U-52 MIM-U-53 MIM-U-55 |
| `update_machine_item` | Errors row 4 | MIM-U-62 MIM-U-63 |
| `delete_machine_item` | R1 | MIM-D-01 MIM-D-02 MIM-D-03 MIM-D-104 |
| `delete_machine_item` | R2 | MIM-D-04 MIM-D-05 MIM-D-06 MIM-D-07 MIM-D-08 MIM-D-09 MIM-D-10 MIM-D-11 MIM-D-12 MIM-D-13 MIM-D-14 MIM-D-15 MIM-D-231 |
| `delete_machine_item` | R3 | MIM-D-16 MIM-D-17 |
| `delete_machine_item` | R4 | MIM-D-18 |
| `delete_machine_item` | R5 | MIM-D-07 MIM-D-11 MIM-D-104 MIM-D-232 |
| `delete_machine_item` | R5 (a) | MIM-D-13 MIM-D-15 MIM-D-17 MIM-D-19 MIM-D-21 MIM-D-25 MIM-D-26 MIM-D-27 MIM-D-28 MIM-D-29 MIM-D-40 MIM-D-41 MIM-D-42 MIM-D-43 MIM-D-55 MIM-D-59 MIM-D-60 MIM-D-61 MIM-D-72 MIM-D-86 MIM-D-90 MIM-D-94 MIM-D-98 MIM-D-99 MIM-D-100 MIM-D-101 MIM-D-102 MIM-D-103 MIM-D-105 MIM-D-109 MIM-D-113 MIM-D-117 MIM-D-121 MIM-D-125 MIM-D-129 MIM-D-133 MIM-D-137 MIM-D-247 MIM-D-248 MIM-D-249 MIM-D-250 |
| `delete_machine_item` | R5 (b) | MIM-D-20 MIM-D-22 MIM-D-30 MIM-D-32 MIM-D-33 MIM-D-44 MIM-D-45 MIM-D-46 MIM-D-47 MIM-D-56 MIM-D-62 MIM-D-63 MIM-D-87 MIM-D-91 MIM-D-95 MIM-D-141 MIM-D-145 MIM-D-149 MIM-D-153 MIM-D-157 MIM-D-161 MIM-D-165 MIM-D-169 MIM-D-238 MIM-D-250 |
| `delete_machine_item` | R5 (c) | MIM-D-23 MIM-D-34 MIM-D-35 MIM-D-36 MIM-D-37 MIM-D-48 MIM-D-49 MIM-D-50 MIM-D-57 MIM-D-64 MIM-D-65 MIM-D-66 MIM-D-72 MIM-D-88 MIM-D-92 MIM-D-96 MIM-D-173 MIM-D-177 MIM-D-181 MIM-D-185 MIM-D-189 MIM-D-243 |
| `delete_machine_item` | R5 (d) | MIM-D-24 MIM-D-38 MIM-D-39 MIM-D-51 MIM-D-52 MIM-D-53 MIM-D-54 MIM-D-58 MIM-D-67 MIM-D-68 MIM-D-72 MIM-D-89 MIM-D-93 MIM-D-97 MIM-D-193 MIM-D-197 MIM-D-201 MIM-D-205 MIM-D-209 MIM-D-242 MIM-D-244 MIM-D-245 |
| `delete_machine_item` | R5a | MIM-D-13 MIM-D-15 MIM-D-17 MIM-D-19 MIM-D-20 MIM-D-21 MIM-D-22 MIM-D-23 MIM-D-24 MIM-D-25 MIM-D-26 MIM-D-27 MIM-D-28 MIM-D-29 MIM-D-30 MIM-D-32 MIM-D-33 MIM-D-34 MIM-D-35 MIM-D-36 MIM-D-37 MIM-D-38 MIM-D-39 MIM-D-40 MIM-D-41 MIM-D-42 MIM-D-43 MIM-D-44 MIM-D-45 MIM-D-46 MIM-D-47 MIM-D-48 MIM-D-49 MIM-D-50 MIM-D-51 MIM-D-52 MIM-D-53 MIM-D-54 MIM-D-55 MIM-D-56 MIM-D-57 MIM-D-58 MIM-D-59 MIM-D-60 MIM-D-61 MIM-D-62 MIM-D-63 MIM-D-64 MIM-D-65 MIM-D-66 MIM-D-67 MIM-D-68 MIM-D-69 MIM-D-70 MIM-D-71 MIM-D-72 MIM-D-73 MIM-D-74 MIM-D-75 MIM-D-76 MIM-D-77 MIM-D-78 MIM-D-79 MIM-D-80 MIM-D-81 MIM-D-82 MIM-D-83 MIM-D-84 MIM-D-85 MIM-D-86 MIM-D-87 MIM-D-88 MIM-D-89 MIM-D-90 MIM-D-91 MIM-D-92 MIM-D-93 MIM-D-94 MIM-D-95 MIM-D-96 MIM-D-97 MIM-D-98 MIM-D-99 MIM-D-100 MIM-D-101 MIM-D-102 MIM-D-103 MIM-D-106 MIM-D-107 MIM-D-108 MIM-D-110 MIM-D-111 MIM-D-112 MIM-D-114 MIM-D-115 MIM-D-116 MIM-D-118 MIM-D-119 MIM-D-120 MIM-D-122 MIM-D-123 MIM-D-124 MIM-D-126 MIM-D-127 MIM-D-128 MIM-D-130 MIM-D-131 MIM-D-132 MIM-D-134 MIM-D-135 MIM-D-136 MIM-D-138 MIM-D-139 MIM-D-140 MIM-D-142 MIM-D-143 MIM-D-144 MIM-D-146 MIM-D-147 MIM-D-148 MIM-D-150 MIM-D-151 MIM-D-152 MIM-D-154 MIM-D-155 MIM-D-156 MIM-D-158 MIM-D-159 MIM-D-160 MIM-D-162 MIM-D-163 MIM-D-164 MIM-D-166 MIM-D-167 MIM-D-168 MIM-D-170 MIM-D-171 MIM-D-172 MIM-D-174 MIM-D-175 MIM-D-176 MIM-D-178 MIM-D-179 MIM-D-180 MIM-D-182 MIM-D-183 MIM-D-184 MIM-D-186 MIM-D-187 MIM-D-188 MIM-D-190 MIM-D-191 MIM-D-192 MIM-D-194 MIM-D-195 MIM-D-196 MIM-D-198 MIM-D-199 MIM-D-200 MIM-D-202 MIM-D-203 MIM-D-204 MIM-D-206 MIM-D-207 MIM-D-208 MIM-D-210 MIM-D-211 MIM-D-212 MIM-D-239 MIM-D-240 MIM-D-241 MIM-D-242 MIM-D-243 MIM-D-244 MIM-D-245 MIM-D-247 MIM-D-248 MIM-D-249 MIM-D-250 |
| `delete_machine_item` | R5b | MIM-D-86 MIM-D-87 MIM-D-88 MIM-D-89 MIM-D-90 MIM-D-91 MIM-D-92 MIM-D-93 MIM-D-94 MIM-D-95 MIM-D-96 MIM-D-97 MIM-D-98 MIM-D-105 MIM-D-106 MIM-D-107 MIM-D-108 MIM-D-109 MIM-D-110 MIM-D-111 MIM-D-112 MIM-D-113 MIM-D-114 MIM-D-115 MIM-D-116 MIM-D-117 MIM-D-118 MIM-D-119 MIM-D-120 MIM-D-121 MIM-D-122 MIM-D-123 MIM-D-124 MIM-D-125 MIM-D-126 MIM-D-127 MIM-D-128 MIM-D-129 MIM-D-130 MIM-D-131 MIM-D-132 MIM-D-133 MIM-D-134 MIM-D-135 MIM-D-136 MIM-D-137 MIM-D-138 MIM-D-139 MIM-D-140 MIM-D-141 MIM-D-142 MIM-D-143 MIM-D-144 MIM-D-145 MIM-D-146 MIM-D-147 MIM-D-148 MIM-D-149 MIM-D-150 MIM-D-151 MIM-D-152 MIM-D-153 MIM-D-154 MIM-D-155 MIM-D-156 MIM-D-157 MIM-D-158 MIM-D-159 MIM-D-160 MIM-D-161 MIM-D-162 MIM-D-163 MIM-D-164 MIM-D-165 MIM-D-166 MIM-D-167 MIM-D-168 MIM-D-169 MIM-D-170 MIM-D-171 MIM-D-172 MIM-D-173 MIM-D-174 MIM-D-175 MIM-D-176 MIM-D-177 MIM-D-178 MIM-D-179 MIM-D-180 MIM-D-181 MIM-D-182 MIM-D-183 MIM-D-184 MIM-D-185 MIM-D-186 MIM-D-187 MIM-D-188 MIM-D-189 MIM-D-190 MIM-D-191 MIM-D-192 MIM-D-193 MIM-D-194 MIM-D-195 MIM-D-196 MIM-D-197 MIM-D-198 MIM-D-199 MIM-D-200 MIM-D-201 MIM-D-202 MIM-D-203 MIM-D-204 MIM-D-205 MIM-D-206 MIM-D-207 MIM-D-208 MIM-D-209 MIM-D-210 MIM-D-211 MIM-D-212 MIM-D-213 MIM-D-214 MIM-D-215 MIM-D-238 MIM-D-239 MIM-D-240 MIM-D-241 MIM-D-243 |
| `delete_machine_item` | R6 | MIM-D-16 MIM-D-213 MIM-D-216 MIM-D-217 MIM-D-218 MIM-D-219 MIM-D-246 |
| `delete_machine_item` | R7 | MIM-D-220 |
| `delete_machine_item` | R8 | MIM-D-221 MIM-D-222 MIM-D-223 MIM-D-224 MIM-D-235 |
| `delete_machine_item` | R9 | MIM-D-16 MIM-D-224 MIM-D-225 MIM-D-226 |
| `delete_machine_item` | R10 | MIM-C-32 MIM-D-215 MIM-D-224 MIM-D-227 MIM-D-228 MIM-D-229 |
| `delete_machine_item` | R11 | MIM-D-230 MIM-D-231 MIM-D-232 |
| `delete_machine_item` | R12 | MIM-D-06 MIM-D-10 MIM-D-102 MIM-D-103 MIM-D-222 MIM-D-233 MIM-D-234 MIM-D-235 MIM-D-236 |
| `delete_machine_item` | R13 | MIM-D-237 |
| `delete_machine_item` | Errors row 1 | MIM-D-01 MIM-D-02 MIM-D-03 MIM-D-104 MIM-D-230 MIM-D-231 MIM-D-232 |
| `delete_machine_item` | Errors row 2 | MIM-D-04 MIM-D-05 MIM-D-06 MIM-D-07 MIM-D-08 MIM-D-09 MIM-D-10 MIM-D-11 |
| `delete_machine_item` | Errors row 3 | MIM-D-13 MIM-D-15 MIM-D-17 MIM-D-19 MIM-D-20 MIM-D-21 MIM-D-22 MIM-D-23 MIM-D-24 MIM-D-25 MIM-D-26 MIM-D-27 MIM-D-28 MIM-D-29 MIM-D-30 MIM-D-32 MIM-D-33 MIM-D-34 MIM-D-35 MIM-D-36 MIM-D-37 MIM-D-38 MIM-D-39 MIM-D-40 MIM-D-41 MIM-D-42 MIM-D-43 MIM-D-44 MIM-D-45 MIM-D-46 MIM-D-47 MIM-D-48 MIM-D-49 MIM-D-50 MIM-D-51 MIM-D-52 MIM-D-53 MIM-D-54 MIM-D-55 MIM-D-56 MIM-D-57 MIM-D-58 MIM-D-59 MIM-D-60 MIM-D-61 MIM-D-62 MIM-D-63 MIM-D-64 MIM-D-65 MIM-D-66 MIM-D-67 MIM-D-68 MIM-D-69 MIM-D-70 MIM-D-71 MIM-D-72 MIM-D-73 MIM-D-74 MIM-D-75 MIM-D-76 MIM-D-77 MIM-D-78 MIM-D-79 MIM-D-80 MIM-D-81 MIM-D-82 MIM-D-83 MIM-D-84 MIM-D-85 MIM-D-86 MIM-D-87 MIM-D-88 MIM-D-89 MIM-D-90 MIM-D-91 MIM-D-92 MIM-D-93 MIM-D-94 MIM-D-95 MIM-D-96 MIM-D-97 MIM-D-98 MIM-D-99 MIM-D-100 MIM-D-101 MIM-D-102 MIM-D-103 MIM-D-242 MIM-D-243 MIM-D-244 MIM-D-245 MIM-D-247 MIM-D-248 MIM-D-249 MIM-D-250 |
| `delete_machine_item` | Errors row 4 | MIM-D-233 MIM-D-234 MIM-D-235 MIM-D-236 |
