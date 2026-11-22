# Test cases — `app/managers/machine_manager.py`

> **Spec:** `tests/unit/managers/machine_manager.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-10-30). O1–O5 and the four sub-points of O4 are the owner's own answers; P1–P9, Q1–Q4 and the house-rule lines were decided by Claude under the reviewer's delegation (2026-10-30).
> **Revision:** 5 (2026-10-31) — verifier round 2, all `case-missing`: R2-1 D-91, D-92, D-93, D-94 (a foreign row that meets no condition does not block, pass); R2-2 D-95, D-96, D-97 (a W1 row on a W2 parent keeps its normal entry, xfail BUG-968); R2-3 D-98 (own line plus foreign line, xfail BUG-968). The owner's answer on R2a: E-45 (a soft-deleted work order of the workspace gets 404, xfail BUG-1000). No existing card changed. R2-4 and the optional notes are skipped, as instructed.
> Revision 4 (2026-10-30) — correction round, the owner's answers (G3 corrected, G13, BUG-1000). Rows of another workspace are invalid data; a refusal shows them only as one `{"type": "other_workspace"}` entry, last. Changed: D-55 … D-59, D-61, D-62, D-63 (Then 4 is the generic entry, retitled), D-60 (Then 4, retitled), E-10, E-17, E-27 (a real W1 order instead of id `77`; E-27 retitled, its Then 3 is now `unchanged(O1)`), E-11, E-28 (id `0` is now a 404, strict xfail BUG-1000, retitled), E-07, E-08, E-16, E-39 (Errors row number only: the table gained row 3). Added D-78, D-79, D-80 (xfail BUG-968), E-41, E-42, E-43 (xfail BUG-1000), E-44 (pass, R2a "id and workspace only"). D-64 … D-67, E-05, E-29 unchanged. The `Revision 1` to `3` lines below are history: where they call foreign rows blockers listed by id, that is withdrawn. Verifier (`machine_manager.verify.md`, findings 1–9, all `case-missing`) addressed in this revision: D-81 (finding 1, pass), D-82, D-83 (2), D-84 (3), D-85 (4), D-86, D-87 (5), D-88, D-89, D-90 (6), these nine xfail BUG-968; U-138 (7, xfail BUG-975, `from_value` = the order's own old factory, Spec gap 13); U-139 (8, pass); S-114, S-115 (9, pass). None dropped.
> Revision 3 (2026-10-30) — the owner answered Spec gap 12 (G12, "1 and 2 block, 3 not"). Added D-69 … D-74 (strict xfail BUG-968: order's factory soft-deleted, transfer to a soft-deleted factory, transfer to a soft-deleted machine, sourcing line on an order of a soft-deleted machine, consumed line with (i), consumed plus unconsumed line), D-75, D-76 (consumed line, `uses_inventory False`: pass), D-77 (order with no machine, strict xfail BUG-968). No existing card changed: the line recipe already sets `uses_inventory True`.
> Revision 2 (2026-10-30) — pre-empts the item verifier's round 3 for `delete_machine` R4. Added D-61, D-62, D-63 (mixed shapes, xfail BUG-968), D-64 (W1 order on a W2 stage not Complete, xfail BUG-968), D-65, D-66 (stage Complete of W2, pass), D-67 (machine of another workspace in use, pass), D-68 (inactive factory in use, xfail BUG-968). Changed: S-35 (card fault: MK's manufacturer matched the search), U-121 (commit spy dropped, no Then read it), D-41 (two `session:` lines before the re-read). Conventions: `MachineEventCreate`, `MachineEventResponse` live in `app.schemas.machine_event`; `session:` lines; STC9. Spec gap 12 added. No ID changed, none retired.
> Revision 1 (2026-10-30) — spec fill-gaps, Gap log G1–G10. Added U-136 (G1, pass), U-137 (G5, pass), D-55 … D-59 (G3, one per blocker type, xfail BUG-968), D-60 (G3, R4a "sorted in with the rest", xfail BUG-968), S-113 (G7, xfail BUG-957). Changed: U-126 (G1: `approved`, `approved_at`, the order's own stamps), C-33 (G4: asserts the `detail`), D-42, D-45, D-47 (G2: named columns). G6, G8, G9, G10: no card change. Conventions: approver, assignee, I9, ST9, class imports. No ID changed, none retired.
> **Counts:** 478 cases · 304 expected-to-pass · 174 expected-to-fail (bugs) · 18 deferred

## Reviewer summary
- **Per callable:** `create_machine` 51 (19 bug) · `update_machine` 139 (54 bug) · `get_machine` 10 (5 bug) · `search_machines` 115 (27 bug) · `delete_machine` 98 (53 bug) · `create_machine_event` 45 (9 bug) · `_check_name_exists_in_factory` 20 (7 bug).
- **Expected-to-fail by bug:** BUG-886 2 · BUG-887 1 · BUG-888 1 · BUG-889 1 · BUG-890 2 · BUG-891 1 · BUG-892 1 · BUG-909 1 · BUG-950 9 · BUG-951 2 · BUG-952 7 · BUG-953 4 · BUG-954 3 · BUG-955 4 · BUG-957 13 · BUG-958 2 · BUG-959 7 · BUG-960 1 · BUG-961 2 · BUG-962 5 · BUG-963 5 · BUG-964 5 · BUG-965 2 · BUG-966 2 · BUG-967 12 · BUG-968 50 · BUG-970 2 · BUG-971 1 · BUG-972 4 · BUG-973 4 · BUG-974 2 · BUG-975 10 · BUG-1000 6. 6 of the 174 are non-strict (five BUG-957 order cards, one BUG-887 tie); all others strict.
- **Owner's answers and their cards.** BUG-968 (O1): one blocking reason per card, a pass card for each state that does not block, R4b's list each with its own pass card. BUG-974 (O3): E-07, E-08 xfail; R3a and the inactive factory pass. **BUG-975 (O4):** R28 (U-98, U-101), R28e (U-127), R28f (U-131) are strict xfail; R28a, R28c, R28d pass today. R28b: every refusal is a card with the open order unchanged and 0 order events; refusals that are themselves bugs (R3, R10, R12, R13) carry that bug's strict xfail, the others pass. Refused section after the flush: U-119 (orders moved inside the savepoint, xfail) and U-120 (after the rollback, pass).
- **Notable design choices:**
  - **BUG-951 has a deterministic recipe by counting misses:** bulk-insert 101 (or 150) live machines, ask for every name, assert `found.count(False) == 0` (N-11, N-12). No card pins a particular machine. N-13 is the other side at 100; N-14 shows soft-deleted rows use up no place.
  - **Missing sort order.** Only `include_deleted=True` lists without a name order: its pass cards compare sorted ids, order cards are `xfail BUG-957 (non-strict)`, and S-112 is the strict statement-recorder alarm. `get_by_factory` (BUG-343) is unordered too, but the manager exposes no order from it and BUG-951 may replace the lookup, so it has no card here: the alarm stays with the DAO's deferred entry.
  - Page-before-filter has no order-free recipe (any count can come out right by physical order), so that card is non-strict (G6). The ignored filters and the window are order-free and strict.
  - Standing decision 4 (collation is no order) makes the BUG-887 tie S-88 non-strict here; the DAO keeps its strict cards.
  - Inherited DAO bugs: one pass-through card each, to the intended behavior, strict (BUG-886, BUG-888, BUG-889, BUG-890 on both paths, BUG-891, BUG-892) (G8).
  - One commit-spy card per writer: C-51, U-135, D-54, E-40. U-135 carries an open order, so it stays meaningful after BUG-975.
  - Race simulations: C-41, U-51. BUG-960 is the statement recorder; a real race is deferred.
  - `update_machine` R14 "the factory is not looked up" has no observable of its own; the card checks no change and no event.
  - No `Author:` lines: a Claude subagent writes the whole file. The card format and vocabulary are unchanged.
  - **Rows of another workspace are invalid data** (owner, correction round; the first G3 answer is withdrawn). They are built only to prove the refusal hides them: every such card expects one `other_workspace` entry, last, no id (D-55 … D-59, D-60, D-61, D-62, D-63; several rows D-78; an own order through (c) (i) keeps its entry, D-79; nothing of W2 anywhere in the args, D-80, with own rows beside them so the check is not empty). A W1 purchase order on a W2 stage is this workspace's row: D-64, D-65 stay. A foreign row that meets no condition does not block: D-66. D-67: a machine of another workspace in use answers 404. D-41 checks `M1 not in db.dirty` and a working `db.flush()` before the re-read, because `expire_all()` would hide a change left on the object; no savepoint there, as for item D-48.
  - **Verifier findings 1–9.** D-85 (a W1 transfer on a W2 stage) rested on "blocking by id only", now withdrawn; it stays because R4 defines a foreign transfer by its own `workspace_id`, so this is a W1 row with a normal entry. D-88, D-89 use a new item IX; D-90 the standing FI. U-138 asserts `from_value` as the order's own old factory (FI, not the machine's F1): the owner's answer to Spec gap 13.
  - **Verifier round 2.** A foreign row that meets no condition does not block: D-91, D-92, D-93, D-94, with D-66 for the purchase order. A row is foreign by its own `workspace_id`, not its parent's: D-95, D-96, D-97, with D-64, D-85 for stages. D-98 is the (c) (ii) side of D-79. D-96 puts both W2 parents on one card.
  - **BUG-1000 (`create_machine_event` R2a):** E-41, E-42, E-11, E-28 (id `0`), E-43 (the 404 comes before the same-status check), strict. Cards that need an accepted id build a real W1 order: E-10, E-17, E-27. E-44 (pass) covers "id and workspace only"; a soft-deleted order is not a state but names no work order, E-45 (the owner's answer). E-05 keeps id `77`: R2 answers first.
- **Needs a decision:** None. Spec gaps 1–10, 12, 13 and 14 are closed; gap 11 is small and blocks nothing. The consumed-line cards D-73, D-74, D-75, D-76 rest on G12, the generic entry on the owner's approved answer of the correction round, U-138's `from_value` on the owner's answer to gap 13.


## Conventions for this module

**IDs.** `MCM` = `app/managers/machine_manager.py`. `C` create_machine · `U` update_machine · `G` get_machine · `S` search_machines · `D` delete_machine · `E` create_machine_event · `N` _check_name_exists_in_factory.

**Actors and fixed values.**
- `M` = the singleton `machine_manager` (`from app.managers.machine_manager import MachineManager, machine_manager`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns. The session does not autoflush.
- W1, W2 = two `workspaces` rows; U1, U2 = two `profiles` rows from `tests/unit/factories.py`. U1 is `created_by` of every Given row, U2 is the acting user of the calls.
- `Machine` = `app.models.machine.Machine`. `MachineActivityEvent`, `MachineSectionAssignment` = the classes of `app.models.machine_activity_event`, `app.models.machine_section_assignment`. `WorkOrderEvent` = `app.models.work_order_event.WorkOrderEvent`. `MachineCreate`, `MachineUpdate` = the schemas of `app.schemas.machine`. `MachineEventCreate`, `MachineEventResponse` = the schemas of `app.schemas.machine_event`. IDLE, RUNNING, OFF, MAINTENANCE = members of `MachineEventTypeEnum` (`app.models.enums`). `HTTPException` = `fastapi.HTTPException`.
- Row classes: `MachineItem` (`app.models.machine_item`), `PurchaseOrder` (`app.models.purchase_order`), `TransferOrder` (`app.models.transfer_order`), `WorkOrder` (`app.models.work_order`), `WorkOrderType` (`app.models.work_order_type`), `WorkOrderItem` (`app.models.work_order_item`), `Status` (`app.models.status`), `WorkOrderApprover` (`app.models.work_order_approver`), `WorkOrderAssignee` (`app.models.work_order_assignee`).
- MISSING = `999999999`: an id no row of any table has. T0 = `datetime(2025, 12, 1, 8, 0, 0)`, T1 = `datetime(2026, 1, 1, 9, 0, 0)`, T2 = `datetime(2026, 1, 1, 10, 0, 0)`, NOW = `datetime(2026, 3, 1, 10, 0, 0)` (all naive).
- D(n) = `date.today() + timedelta(days=n)`, read in the test. `date` is never patched.
- Text values are Python literals: `"\t"` is one tab. Copy them exactly.

**Externals.** `app.dao.machine.utcnow` is patched to NOW in every test (the helper does it; a card never patches it). Nothing else is mocked, except Race simulations. `created_at` and `updated_at` are asserted as `is None` / `is not None`, or against a value set in the Given, never "later than".

**Standing rows.** These exist in every test, inserted in this order, and need no Given line. Each has `is_active True`, `is_deleted False` unless stated.
- F1 = `factories` row: `name "Main Plant"`, `abbreviation "MP"`, `workspace_id W1.id`. F2 = `"North Yard"`, `"NY"`. F9 = `"Far Depot"`, `"FR"`, `workspace_id W2.id`. FD = `"Closed Mill"`, `"CM"`, `is_deleted True` (`is_active` stays True). FI = `"Idle Plant"`, `"IP"`, `is_active False`.
- S1 = `factory_sections` row: `name "Cutting"`, `factory_id F1.id`, `workspace_id W1.id`. S2 = `"Paint"` of F1. S3 = `"Welding"` of F2. SX = `"Old Line"` of F1, `is_deleted True`. S9 = `"Packing"` of F9, `workspace_id W2.id`.
- WT1 = `work_order_types` row: `name "Repair"`, `workspace_id W1.id`. WT9 = `name "Far Repair"`, `workspace_id W2.id`. I1 = `items` row: `name "Bolt M8"`, `name_normalized "bolt m8"`, `unit "pcs"`, `workspace_id W1.id`, `created_by U1.id`. I2 = the same, `name "Washer Ten"`, `name_normalized "washer ten"`.
- STD = `statuses` row: `name "Draft"`, `comment "stage"`, `workspace_id W1.id`. STC = the same, `name "Complete"`.

**Given rows.** Inserted directly (never through `M`) and flushed one at a time in the order written, so ids rise in that order. A line names a recipe, then after "but" (or after a comma, for values the recipe leaves to the card) every column that differs. No other row exists. A line written as code is a step to run exactly as written. A row of W2 pointing at a W1 machine is invalid data, built only to prove the refusal hides it.
- **machine** = `machines` row: `workspace_id W1.id`, `factory_id F1.id`, `is_running False`, `model_number None`, `manufacturer None`, `note None`, `created_by U1.id`, `updated_by None`, `updated_at None`, `is_active True`, `is_deleted False`; the card gives `name`.
- Machine recipes: **M1** = `"Lathe"`. **M2** = `"Press"`. **M3** = `"Drill"`, `factory_id F2.id`. **MX** = `"Old Saw"`, `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`. **MF** = `"Kiln"`, `factory_id FD.id`. **MI** = `"Mixer"`, `factory_id FI.id`. **M9** = `"Grinder"`, `workspace_id W2.id`, `factory_id F9.id`. List recipes: **MA** = `"Alpha"`, **MB** = `"Beryl"`, **MC** = `"Cobalt"`, **MK** = `"Krypton"`, **MQ** = `"Quartz"`, **MZ** = `"Zenith"`.
- **bulk(n, p)** = n live machines of F1 in W1, inserted with one bulk `insert(Machine)`, named p + the number from 0 on, padded to 5 digits (`bulk(101, "P")` = `P00000` … `P00100`), `is_active True`, `is_deleted False`, `is_running False`, `created_by U1.id`.
- **link of M to S** = `MachineSectionAssignment`: `workspace_id` = M's, `machine_id M.id`, `factory_section_id S.id`, `created_by U1.id`; then `db.expire_all()`.
- **status row of M at T, "X"** = `MachineActivityEvent`: `workspace_id` = M's, `machine_id M.id`, `event_type "status_updated"`, `description "seed"`, `performed_by U1.id`, `created_at T`, `metadata_json {"status": "X"}`.
- **order of M** = `work_orders` row: `workspace_id W1.id`, `work_order_number` = `"WO-"` + the row's Given name (`"WO-O1"`), `work_order_type_id WT1.id`, `title "Service"`, `factory_id F1.id`, `machine_id M.id`, `planned_date None`, `is_deleted False`, `updated_by None`, `updated_at None`; the card gives `status`.
- **line of O** = `work_order_items` row: `workspace_id W1.id`, `work_order_id O.id`, `item_id I1.id`, `quantity 2`, `uses_inventory True`, `consumed_at None`, `is_deleted False`; the card gives `source_location_type`, `source_location_id`.
- **approver of O, U** = `work_order_approvers` row: `workspace_id W1.id`, `work_order_id O.id`, `user_id U.id`; the card gives `approved`, `approved_at`. **assignee of O, U** = `work_order_assignees` row: `workspace_id W1.id`, `work_order_id O.id`, `user_id U.id`.
- **Parents of W2** (only where a Given line names them): **I9** = `items` row: `name "Far Spring"`, `name_normalized "far spring"`, `unit "pcs"`, `workspace_id W2.id`, `created_by U1.id`. **ST9** = `statuses` row: `name "Draft"`, `comment "stage"`, `workspace_id W2.id`. **STC9** = the same, `name "Complete"`. **IX** (W1) = `items` row: `name "Old Rivet"`, `name_normalized "old rivet"`, `unit "pcs"`, `workspace_id W1.id`, `is_active False`, `created_by U1.id`.
- **stock of M, item I** = `machine_items` row: `workspace_id` = M's, `machine_id M.id`, `item_id I.id`, `req_qty None`, `defective_qty None`; the card gives `qty`.
- **purchase order** = `purchase_orders` row: `workspace_id W1.id`, `po_number` = `"PO-"` + the Given name, `destination_type "machine"`, `created_by U1.id`, `voided False`; the card gives `destination_id`, `current_status_id`.
- **transfer order** = `transfer_orders` row: `workspace_id W1.id`, `transfer_number` = `"TR-"` + the Given name, `source_location_type "storage"`, `source_location_id F1.id`, `destination_location_type "storage"`, `destination_location_id F2.id`, `current_status_id STD.id`, `created_by U1.id`, `completed_at None`.
- **stock movement row of I1 in F1** = `inventory_ledger` row built with `InventoryLedger` (`app.models.inventory_ledger`): `workspace_id W1.id`, `inventory_type InventoryTypeEnum.STORAGE`, `factory_id F1.id`, `item_id I1.id`, `transaction_type "manual_add"`, `quantity 2`, `qty_before 0`, `qty_after 2`.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id; the values are database values. "the returned row" = by `result.id`.
- **unchanged(X)** = after re-read, every column of X equals its value before the call. Snapshot after the last Given line, after `db.refresh(X)`. X may be any Given row.
- **nothing written** = the numbers of rows in `machines`, `machine_section_assignments`, `machine_activity_events`, `work_orders`, `work_order_events` (all workspaces) equal their values before the call.
- **links_of(M)** = `db.expire_all()`, then every `machine_section_assignments` row with `machine_id == M.id`, ordered by `id`, as a list.
- **events_of(M)** = a fresh SELECT of `machine_activity_events` with `machine_id == M.id`, ordered by `id`, as a list. **wo_events(O)** = the same on `work_order_events` with `work_order_id == O.id`. "that row" = the one row just counted. `metadata_json` is compared as a whole dict, order of `changes` included.
- **names(x)** = `[r.name for r in x]`, order is part of the check. **ids(x)** = `sorted(r.id for r in x)`, used where today's order is undefined; right-hand ids are in Given order.
- `count:` lines count rows of the named table in all workspaces, with the filter stated.
- `raises: HTTPException`: plain `with pytest.raises(HTTPException) as exc:` around the call; `raises: ValueError` the same; the in-use refusal is read as `exc.value.args`, never `str(exc.value)`.
- `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`, `raises: DataError` = `sqlalchemy.exc.DataError`: `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards. `ForeignKeyViolation` = `psycopg2.errors.ForeignKeyViolation`.
- `session:` lines run on `db` directly, before any re-read: `M1 not in db.dirty` is one `assert`; "`db.flush()` runs and raises nothing" is the bare call.
- `raises: ValidationError` = `pydantic.ValidationError` around the construction of the schema object. Further `raises:` lines are assertions on `exc.value` after the `with` block, one per line.

**Targets.** "target `schema`" = the When only builds the schema object. "target `database`" = the When inserts one row with `db.add(...)`, `db.flush()`; an expected `IntegrityError` is wrapped as above.

**Refused after flush.** `sp = db.begin_nested()` directly before the call; the call in plain `pytest.raises` (no second savepoint); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks. Unchanged-after-rollback snapshots are taken before `sp` opens.

**Rolled back.** The same savepoint, plus a spy that wraps `db.commit` (still callable, records calls). One per writer.

**sql_log.** A list filled by a `before_cursor_execute` listener on `db.connection()`, started at that Given line, removed after the call. Each entry is the statement text. `re` = the standard module.

**Loops.** `_check_name_exists_in_factory` cards with `found` use the one list comprehension of their When: the count of misses is deterministic, which machine is missed is not.

**xfail cards.** Write the call and the checks as shown, also when the call uses a parameter that does not exist yet. Strict unless the Expect line says `(non-strict)`: `pytest.mark.xfail(strict=True, reason="BUG-NNN")` or `strict=False`. Two live machines with one normalised name in one factory are never built (BUG-953 forbids them): same-named rows sit in different factories, or one is soft-deleted.

**Race simulations.** MCM-C-41 (`create_machine` R9) and MCM-U-51 (`update_machine` R10a) patch `MachineManager._check_name_exists_in_factory` to return `False`, to put the code in the state "a concurrent request already passed the Python check". Nothing else may be patched for this.


## `MachineManager.create_machine`

### MCM-C-01 — create stores the machine with the values sent, in the caller's workspace, by the caller
- **Rules:** `create_machine` R5, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id, model_number="L-200", manufacturer="Haas", note="Bay 3"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, Machine)`.
2. returns: `result.id is not None`.
3. re-read the returned row: `name == "Lathe"`, `factory_id == F1.id`.
4. re-read the returned row: `model_number == "L-200"`, `manufacturer == "Haas"`, `note == "Bay 3"`.
5. re-read the returned row: `workspace_id == W1.id`, `created_by == U2.id`.
6. count: `machines` has exactly 1 row.

### MCM-C-02 — a new machine is stopped, live and carries no update or deletion stamp
- **Rules:** `create_machine` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `is_running is False`, `is_active is True`, `is_deleted is False`.
3. re-read the returned row: `created_at is not None`.
4. re-read the returned row: `updated_at is None`, `updated_by is None`.
5. re-read the returned row: `deleted_at is None`, `deleted_by is None`.

### MCM-C-03 — optional fields not sent are stored as None
- **Rules:** `create_machine` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `model_number is None`, `manufacturer is None`, `note is None`.

### MCM-C-04 — an is_running in the request is ignored
- **Rules:** `create_machine` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id, is_running=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `is_running is False`.

### MCM-C-05 — the note is stored as typed, padding kept
- **Rules:** `create_machine` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id, note="  awaiting belt "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `note == "  awaiting belt "`.

### MCM-C-06 — an empty note is stored as an empty string
- **Rules:** `create_machine` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id, note=""), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `note == ""`.

### MCM-C-07 — inner spaces of model number and manufacturer are kept
- **Rules:** `create_machine` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id, model_number="L  200", manufacturer="Haas  Works"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `model_number == "L  200"`, `manufacturer == "Haas  Works"`.

### MCM-C-08 — a padded model number is stored trimmed
- **Rules:** `create_machine` R7 [BUG-967]
- **Kind:** bug
- **Expect:** xfail BUG-967
- **Fails today on:** Then 2 (stored as typed, with the outer spaces)

**Given**
1. No machines exist.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id, model_number=" L-200 "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `model_number == "L-200"`.

### MCM-C-09 — a padded manufacturer is stored trimmed
- **Rules:** `create_machine` R7 [BUG-967]
- **Kind:** bug
- **Expect:** xfail BUG-967
- **Fails today on:** Then 2 (stored as typed, with the outer spaces)

**Given**
1. No machines exist.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id, manufacturer=" Haas "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `manufacturer == "Haas"`.

### MCM-C-10 — an empty model number is stored as None
- **Rules:** `create_machine` R7 [BUG-967]
- **Kind:** bug
- **Expect:** xfail BUG-967
- **Fails today on:** Then 2 (the empty string is stored)

**Given**
1. No machines exist.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id, model_number=""), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `model_number is None`.

### MCM-C-11 — a whitespace-only model number is stored as None
- **Rules:** `create_machine` R7 [BUG-967]
- **Kind:** bug
- **Expect:** xfail BUG-967
- **Fails today on:** Then 2 (the three spaces are stored)

**Given**
1. No machines exist.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id, model_number="   "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `model_number is None`.

### MCM-C-12 — an empty manufacturer is stored as None
- **Rules:** `create_machine` R7 [BUG-967]
- **Kind:** bug
- **Expect:** xfail BUG-967
- **Fails today on:** Then 2 (the empty string is stored)

**Given**
1. No machines exist.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id, manufacturer=""), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `manufacturer is None`.

### MCM-C-13 — a whitespace-only manufacturer is stored as None
- **Rules:** `create_machine` R7 [BUG-967]
- **Kind:** bug
- **Expect:** xfail BUG-967
- **Fails today on:** Then 2 (the tab is stored)

**Given**
1. No machines exist.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id, manufacturer="\t"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `manufacturer is None`.

### MCM-C-14 — the name is stored trimmed, inner spaces and case kept
- **Rules:** `create_machine` R6 [BUG-950]
- **Kind:** bug
- **Expect:** xfail BUG-950
- **Fails today on:** Then 2 (the name is stored as typed, with the outer spaces)

**Given**
1. No machines exist.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="  Big  PRESS ", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `name == "Big  PRESS"`.

### MCM-C-15 — inner whitespace and case of the name are kept
- **Rules:** `create_machine` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="big  PRESS", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `name == "big  PRESS"`.

### MCM-C-16 — an empty name is rejected by MachineCreate
- **Rules:** `create_machine` R6 [BUG-950], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-950
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. No machines exist.

**When**
- `MachineCreate(name="", factory_id=F1.id)` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. count: `machines` has exactly 0 rows.

### MCM-C-17 — a name of three spaces is rejected by MachineCreate
- **Rules:** `create_machine` R6 [BUG-950], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-950
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. No machines exist.

**When**
- `MachineCreate(name="   ", factory_id=F1.id)` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. count: `machines` has exactly 0 rows.

### MCM-C-18 — a name of one tab is rejected by MachineCreate
- **Rules:** `create_machine` R6 [BUG-950], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-950
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. No machines exist.

**When**
- `MachineCreate(name="\t", factory_id=F1.id)` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. count: `machines` has exactly 0 rows.

### MCM-C-19 — a one-character name is accepted by MachineCreate
- **Rules:** `create_machine` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `result = MachineCreate(name="a", factory_id=F1.id)` (target `schema`; M is not called).

**Then**
1. returns: `result.name == "a"`.

### MCM-C-20 — a model_number of 201 characters is rejected by MachineCreate
- **Rules:** `create_machine` R8 [BUG-972], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-972
- **Fails today on:** Then 1 (no error is raised; the schema has no limit)

**Given**
1. No machines exist.

**When**
- `MachineCreate(name="Lathe", factory_id=F1.id, model_number="x" * 201)` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. count: `machines` has exactly 0 rows.

### MCM-C-21 — a model_number of exactly 200 characters is accepted and stored
- **Rules:** `create_machine` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id, model_number="x" * 200), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `model_number == "x" * 200`.

### MCM-C-22 — a manufacturer of 201 characters is rejected by MachineCreate
- **Rules:** `create_machine` R8 [BUG-972], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-972
- **Fails today on:** Then 1 (no error is raised; the schema has no limit)

**Given**
1. No machines exist.

**When**
- `MachineCreate(name="Lathe", factory_id=F1.id, manufacturer="x" * 201)` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. count: `machines` has exactly 0 rows.

### MCM-C-23 — a manufacturer of exactly 200 characters is accepted and stored
- **Rules:** `create_machine` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id, manufacturer="x" * 200), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `manufacturer == "x" * 200`.

### MCM-C-24 — a factory id that does not exist is refused
- **Rules:** `create_machine` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=MISSING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
4. nothing written: nothing written.

### MCM-C-25 — factory id 0 is refused as not found
- **Rules:** `create_machine` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 0 not found"`.
4. nothing written: nothing written.

### MCM-C-26 — a factory of another workspace is refused as not found
- **Rules:** `create_machine` R1, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F9.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {F9.id} not found"`.
4. nothing written: nothing written.

### MCM-C-27 — an unknown workspace id ends at the factory check
- **Rules:** `create_machine` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id), workspace_id=MISSING, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {F1.id} not found"`.
4. nothing written: nothing written.

### MCM-C-28 — a soft-deleted factory is refused
- **Rules:** `create_machine` R2 [BUG-963], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-963
- **Fails today on:** Then 1 (no error is raised: the machine is created)

**Given**
1. No machines exist.

**When**
- `M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=FD.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create machine for deleted factory"`.
4. nothing written: nothing written.

### MCM-C-29 — the deleted-factory refusal comes before the name check
- **Rules:** `create_machine` R2 [BUG-963], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-963
- **Fails today on:** Then 2 (today the name check answers 409)

**Given**
1. MF.

**When**
- `M.create_machine(db, machine_data=MachineCreate(name="Kiln", factory_id=FD.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create machine for deleted factory"`.
4. nothing written: nothing written.
5. unchanged: unchanged(MF).

### MCM-C-30 — a live but inactive factory is accepted
- **Rules:** `create_machine` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=FI.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `factory_id == FI.id`.
3. count: `machines` has exactly 1 row.

### MCM-C-31 — a live machine of the factory with the same name is refused
- **Rules:** `create_machine` R3, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.

**When**
- `M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Machine with name 'Lathe' already exists in this factory"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).

### MCM-C-32 — a name that differs only in case is refused, with the name as submitted
- **Rules:** `create_machine` R3 [BUG-952], Errors row 3; `_check_name_exists_in_factory` R4
- **Kind:** bug
- **Expect:** xfail BUG-952
- **Fails today on:** Then 1 (no error is raised: names are compared exactly)

**Given**
1. M1.

**When**
- `M.create_machine(db, machine_data=MachineCreate(name="LATHE", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Machine with name 'LATHE' already exists in this factory"`.
4. nothing written: nothing written.

### MCM-C-33 — a name that differs only in outer spaces is refused
- **Rules:** `create_machine` R3 [BUG-952], Errors row 3; `_check_name_exists_in_factory` R4
- **Kind:** bug
- **Expect:** xfail BUG-952
- **Fails today on:** Then 1 (no error is raised: names are compared exactly)

**Given**
1. M1.

**When**
- `M.create_machine(db, machine_data=MachineCreate(name=" Lathe ", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Machine with name 'Lathe' already exists in this factory"`.
4. nothing written: nothing written.

### MCM-C-34 — the same name in another factory does not block
- **Rules:** `create_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `factory_id == F2.id`.
3. unchanged: unchanged(M1).

### MCM-C-35 — the same name in another workspace does not block
- **Rules:** `create_machine` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M9, but `name "Lathe"`.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`.
3. unchanged: unchanged(M9).

### MCM-C-36 — the name of a soft-deleted machine can be used again
- **Rules:** `create_machine` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MX.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Old Saw", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `is_deleted is False`.
3. unchanged: unchanged(MX).

### MCM-C-37 — the database refuses a second live machine with the same name in a factory
- **Rules:** `create_machine` R9 [BUG-953]
- **Kind:** bug
- **Expect:** xfail BUG-953
- **Fails today on:** Then 1 (no error is raised: the table has no unique index)

**Given**
1. M1.

**When**
- insert directly (target `database`; M is not called): `db.add(Machine(workspace_id=W1.id, factory_id=F1.id, name="Lathe"))`, then `db.flush()`.

**Then**
1. raises: `IntegrityError` on flush.
2. count: `machines` with `name == "Lathe"` has exactly 1 row.

### MCM-C-38 — the database refuses a second live machine whose name differs only in case and outer spaces
- **Rules:** `create_machine` R9 [BUG-953]
- **Kind:** bug
- **Expect:** xfail BUG-953
- **Fails today on:** Then 1 (no error is raised: the table has no unique index)

**Given**
1. M1.

**When**
- insert directly (target `database`; M is not called): `db.add(Machine(workspace_id=W1.id, factory_id=F1.id, name=" LATHE "))`, then `db.flush()`.

**Then**
1. raises: `IntegrityError` on flush.
2. count: `machines` has exactly 1 row.

### MCM-C-39 — the database accepts a soft-deleted machine with the name of a live one
- **Rules:** `create_machine` R9
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1.

**When**
- insert directly (target `database`; M is not called): `db.add(Machine(workspace_id=W1.id, factory_id=F1.id, name="Lathe", is_deleted=True, is_active=False))`, then `db.flush()`.

**Then**
1. count: `machines` has exactly 2 rows.
2. unchanged: unchanged(M1).

### MCM-C-40 — the database accepts the same name in another factory
- **Rules:** `create_machine` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- insert directly (target `database`; M is not called): `db.add(Machine(workspace_id=W1.id, factory_id=F2.id, name="Lathe"))`, then `db.flush()`.

**Then**
1. count: `machines` has exactly 2 rows.
2. unchanged: unchanged(M1).

### MCM-C-41 — a duplicate that passed the Python check gets the 409, not a database error
- **Rules:** `create_machine` R9 [BUG-953], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-953
- **Fails today on:** Then 1 (no error is raised: there is no index, so the duplicate is saved)

**Given**
1. M1.
2. Race simulation: `MachineManager._check_name_exists_in_factory` is patched to return `False` (Conventions, Race simulations).

**When**
- wrapped as `with pytest.raises(HTTPException) as exc:` then `with db.begin_nested():` then `M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Machine with name 'Lathe' already exists in this factory"`.
4. count: `machines` with `name == "Lathe"` has exactly 1 row.
5. count: `machine_activity_events` has exactly 0 rows.

### MCM-C-42 — a section sent gives the machine a link and the returned machine reads it
- **Rules:** `create_machine` R10, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id, factory_section_id=S1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. returns: `result.factory_section_id == S1.id`.
3. returns: `result.factory_section_name == "Cutting"`.
4. count: `machine_section_assignments` has exactly 1 row.
5. re-read the one row of links_of(result): `factory_section_id == S1.id`, `workspace_id == W1.id`, `created_by == U2.id`.

### MCM-C-43 — without a section no link exists and both section values read None
- **Rules:** `create_machine` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. returns: `result.factory_section_id is None`.
3. returns: `result.factory_section_name is None`.
4. count: `machine_section_assignments` has exactly 0 rows.

### MCM-C-44 — a section id that does not exist refuses the create; the machine stays flushed until the rollback
- **Rules:** `create_machine` R11, R12, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. No machines exist.
2. Savepoint per **refused after flush** (Conventions).

**When**
- `M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id, factory_section_id=MISSING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory section with ID 999999999 not found"`.
4. count: `machines` has exactly 1 row.
5. count: `machine_section_assignments` has exactly 0 rows.
6. count: `machine_activity_events` has exactly 0 rows.
7. count after the savepoint rollback: `machines` has exactly 0 rows.

### MCM-C-45 — section id 0 refuses the create; the machine stays flushed until the rollback
- **Rules:** `create_machine` R11, R12, Errors row 4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No machines exist.
2. Savepoint per **refused after flush** (Conventions).

**When**
- `M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id, factory_section_id=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory section with ID 0 not found"`.
4. count: `machines` has exactly 1 row.
5. count: `machine_section_assignments` has exactly 0 rows.
6. count: `machine_activity_events` has exactly 0 rows.
7. count after the savepoint rollback: `machines` has exactly 0 rows.

### MCM-C-46 — a soft-deleted section refuses the create; the machine stays flushed until the rollback
- **Rules:** `create_machine` R11, R12, Errors row 4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. No machines exist.
2. Savepoint per **refused after flush** (Conventions).

**When**
- `M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id, factory_section_id=SX.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot assign a machine to a deleted factory section"`.
4. count: `machines` has exactly 1 row.
5. count: `machine_section_assignments` has exactly 0 rows.
6. count: `machine_activity_events` has exactly 0 rows.
7. count after the savepoint rollback: `machines` has exactly 0 rows.

### MCM-C-47 — a section of another factory refuses the create; the machine stays flushed until the rollback
- **Rules:** `create_machine` R11, R12, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. No machines exist.
2. Savepoint per **refused after flush** (Conventions).

**When**
- `M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id, factory_section_id=S3.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Factory section does not belong to this machine's factory"`.
4. count: `machines` has exactly 1 row.
5. count: `machine_section_assignments` has exactly 0 rows.
6. count: `machine_activity_events` has exactly 0 rows.
7. count after the savepoint rollback: `machines` has exactly 0 rows.

### MCM-C-48 — a section of another workspace refuses the create; the machine stays flushed until the rollback
- **Rules:** `create_machine` R11, R12, Errors row 4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No machines exist.
2. Savepoint per **refused after flush** (Conventions).

**When**
- `M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id, factory_section_id=S9.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory section with ID {S9.id} not found"`.
4. count: `machines` has exactly 1 row.
5. count: `machine_section_assignments` has exactly 0 rows.
6. count: `machine_activity_events` has exactly 0 rows.
7. count after the savepoint rollback: `machines` has exactly 0 rows.

### MCM-C-49 — one created event is written
- **Rules:** `create_machine` R13
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: events_of(result) has exactly 1 row.
3. event: that row has `event_type == "created"`, `description == "Machine created: Lathe"`.
4. event: that row has `performed_by == U2.id`, `workspace_id == W1.id`.
5. event: that row has `metadata_json is None`.
6. event: that row has `created_at is not None`.

### MCM-C-50 — an unknown user fails on flush and nothing is saved
- **Rules:** `create_machine` R14, Errors row 6
- **Kind:** error
- **Expect:** pass

**Given**
1. No machines exist.

**When**
- `M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"machines_created_by_fkey" in str(exc.value.orig)`.
4. nothing written: nothing written.

### MCM-C-51 — the create is flushed but not committed: a rollback removes machine, link and event
- **Rules:** `create_machine` R15, Returns
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No machines exist.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id, factory_section_id=S1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `machines` has exactly 1 row.
3. count: `machine_section_assignments` has exactly 1 row.
4. count: `machine_activity_events` has exactly 1 row.
5. count after the savepoint rollback: `machines` has exactly 0 rows.
6. count after the savepoint rollback: `machine_section_assignments` has exactly 0 rows.
7. count after the savepoint rollback: `machine_activity_events` has exactly 0 rows.
8. mock called: the `db.commit` spy was never called.

## `MachineManager.update_machine`

### MCM-U-01 — the fields sent are stored, the editor recorded and the same instance returned
- **Rules:** `update_machine` R4, R23, R24, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(name="Big Lathe", model_number="L-300", manufacturer="Haas", note="Bay 4"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `name == "Big Lathe"`.
3. re-read M1: `model_number == "L-300"`, `manufacturer == "Haas"`, `note == "Bay 4"`.
4. re-read M1: `updated_by == U2.id`.
5. re-read M1: `updated_at is not None`.
6. count: `machines` has exactly 1 row.

### MCM-U-02 — fields not sent and the columns nobody edits keep their values
- **Rules:** `update_machine` R4, R22
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1, but `model_number "L-200"`, `manufacturer "Haas"`, `is_running True`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(note="Bay 4"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `note == "Bay 4"`.
3. re-read M1: `name == "Lathe"`, `model_number == "L-200"`, `manufacturer == "Haas"`.
4. re-read M1: `workspace_id == W1.id`, `factory_id == F1.id`, `created_by == U1.id`, `created_at is not None`.
5. re-read M1: `is_running is True`, `is_active is True`, `is_deleted is False`.
6. re-read M1: `deleted_at is None`, `deleted_by is None`.

### MCM-U-03 — an is_running in the request is ignored
- **Rules:** `update_machine` R22
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(note="Bay 4", is_running=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_running is False`.

### MCM-U-04 — an id that no machine has is refused
- **Rules:** `update_machine` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.

**When**
- `M.update_machine(db, machine_id=MISSING, machine_data=MachineUpdate(name="Big Lathe"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine with ID 999999999 not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).

### MCM-U-05 — a machine of another workspace is refused and not changed
- **Rules:** `update_machine` R1, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M9.

**When**
- `M.update_machine(db, machine_id=M9.id, machine_data=MachineUpdate(name="Big Grinder"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M9).

### MCM-U-06 — a soft-deleted machine is refused
- **Rules:** `update_machine` R2, Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MX.

**When**
- `M.update_machine(db, machine_id=MX.id, machine_data=MachineUpdate(note="Bay 4"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted machine"`.
4. nothing written: nothing written.
5. unchanged: unchanged(MX).

### MCM-U-07 — a soft-deleted machine is refused also with an empty request
- **Rules:** `update_machine` R2, Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MX.

**When**
- `M.update_machine(db, machine_id=MX.id, machine_data=MachineUpdate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted machine"`.
4. nothing written: nothing written.
5. unchanged: unchanged(MX).

### MCM-U-08 — the deleted-machine refusal comes before the factory check
- **Rules:** `update_machine` R2, R15, Errors row 2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MX.

**When**
- `M.update_machine(db, machine_id=MX.id, machine_data=MachineUpdate(factory_id=MISSING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted machine"`.
4. nothing written: nothing written.
5. unchanged: unchanged(MX).

### MCM-U-09 — the deleted-machine refusal comes before the name check
- **Rules:** `update_machine` R2, R15, Errors row 2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. MX.

**When**
- `M.update_machine(db, machine_id=MX.id, machine_data=MachineUpdate(name="Lathe"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted machine"`.
4. nothing written: nothing written.
5. unchanged: unchanged(MX).

### MCM-U-10 — a rename of a machine in a soft-deleted factory is refused
- **Rules:** `update_machine` R3 [BUG-964], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-964
- **Fails today on:** Then 1 (no error is raised: the change is saved)

**Given**
1. MF.

**When**
- `M.update_machine(db, machine_id=MF.id, machine_data=MachineUpdate(name="Big Kiln"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted machine"`.
4. nothing written: nothing written.
5. unchanged: unchanged(MF).

### MCM-U-11 — an edit of a machine in a soft-deleted factory is refused
- **Rules:** `update_machine` R3 [BUG-964], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-964
- **Fails today on:** Then 1 (no error is raised: the change is saved)

**Given**
1. MF.

**When**
- `M.update_machine(db, machine_id=MF.id, machine_data=MachineUpdate(note="Bay 4"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted machine"`.
4. nothing written: nothing written.
5. unchanged: unchanged(MF).

### MCM-U-12 — a move out of a machine in a soft-deleted factory is refused
- **Rules:** `update_machine` R3 [BUG-964], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-964
- **Fails today on:** Then 1 (no error is raised: the change is saved)

**Given**
1. MF.

**When**
- `M.update_machine(db, machine_id=MF.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted machine"`.
4. nothing written: nothing written.
5. unchanged: unchanged(MF).

### MCM-U-13 — the deleted-factory refusal comes before the target factory check
- **Rules:** `update_machine` R3 [BUG-964], R15, Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-964
- **Fails today on:** Then 2 (today the target factory check answers 404)

**Given**
1. MF.

**When**
- `M.update_machine(db, machine_id=MF.id, machine_data=MachineUpdate(factory_id=MISSING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted machine"`.
4. nothing written: nothing written.
5. unchanged: unchanged(MF).

### MCM-U-14 — a machine in a live but inactive factory can be edited
- **Rules:** `update_machine` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI.

**When**
- `result = M.update_machine(db, machine_id=MI.id, machine_data=MachineUpdate(note="Bay 4"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI` (the very object that was read).
2. re-read MI: `note == "Bay 4"`.

### MCM-U-15 — an explicit null clears model_number
- **Rules:** `update_machine` R5 [BUG-962]
- **Kind:** bug
- **Expect:** xfail BUG-962
- **Fails today on:** Then 2 (the null is dropped, the old value stays)

**Given**
1. M1, but `model_number "L-200"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(model_number=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `model_number is None`.
3. re-read M1: `updated_by == U2.id`.
4. event: `events_of(M1)[0].metadata_json == {"changes": [{"field": "model_number", "label": "Model number", "from_value": "L-200", "to_value": None}]}`.

### MCM-U-16 — an explicit null clears manufacturer
- **Rules:** `update_machine` R5 [BUG-962]
- **Kind:** bug
- **Expect:** xfail BUG-962
- **Fails today on:** Then 2 (the null is dropped, the old value stays)

**Given**
1. M1, but `manufacturer "Haas"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(manufacturer=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `manufacturer is None`.
3. re-read M1: `updated_by == U2.id`.
4. event: `events_of(M1)[0].metadata_json == {"changes": [{"field": "manufacturer", "label": "Manufacturer", "from_value": "Haas", "to_value": None}]}`.

### MCM-U-17 — an explicit null clears note
- **Rules:** `update_machine` R5 [BUG-962]
- **Kind:** bug
- **Expect:** xfail BUG-962
- **Fails today on:** Then 2 (the null is dropped, the old value stays)

**Given**
1. M1, but `note "Bay 3"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(note=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `note is None`.
3. re-read M1: `updated_by == U2.id`.
4. event: `events_of(M1)[0].metadata_json == {"changes": [{"field": "note", "label": "Note", "from_value": "Bay 3", "to_value": None}]}`.

### MCM-U-18 — a sent null keeps meaning clear-the-section and leaves omitted fields
- **Rules:** `update_machine` R4, R5, R17
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1, but `note "Bay 3"`.
2. L1 = link of M1 to S1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_section_id=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read: `links_of(M1) == []`.
3. re-read M1: `note == "Bay 3"`.
4. re-read M1: `name == "Lathe"`.

### MCM-U-19 — a null name is rejected by MachineUpdate
- **Rules:** `update_machine` R5 [BUG-962], Errors row 7
- **Kind:** bug
- **Expect:** xfail BUG-962
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. M1.

**When**
- `MachineUpdate(name=None)` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(M1).

### MCM-U-20 — a null factory_id is rejected by MachineUpdate
- **Rules:** `update_machine` R5 [BUG-962], Errors row 7
- **Kind:** bug
- **Expect:** xfail BUG-962
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. M1.

**When**
- `MachineUpdate(factory_id=None)` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(M1).

### MCM-U-21 — a padded model number is stored trimmed
- **Rules:** `update_machine` R6 [BUG-967]
- **Kind:** bug
- **Expect:** xfail BUG-967
- **Fails today on:** Then 2 (stored as sent, with the outer spaces)

**Given**
1. M1, but `model_number "L-200"`, `manufacturer "Acme"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(model_number=" L-300 "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `model_number == "L-300"`.

### MCM-U-22 — a padded manufacturer is stored trimmed
- **Rules:** `update_machine` R6 [BUG-967]
- **Kind:** bug
- **Expect:** xfail BUG-967
- **Fails today on:** Then 2 (stored as sent, with the outer spaces)

**Given**
1. M1, but `model_number "L-200"`, `manufacturer "Acme"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(manufacturer=" Haas "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `manufacturer == "Haas"`.

### MCM-U-23 — an empty model number is stored as None
- **Rules:** `update_machine` R6 [BUG-967]
- **Kind:** bug
- **Expect:** xfail BUG-967
- **Fails today on:** Then 2 (the empty string is stored)

**Given**
1. M1, but `model_number "L-200"`, `manufacturer "Acme"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(model_number=""), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `model_number is None`.

### MCM-U-24 — an empty manufacturer is stored as None
- **Rules:** `update_machine` R6 [BUG-967]
- **Kind:** bug
- **Expect:** xfail BUG-967
- **Fails today on:** Then 2 (the empty string is stored)

**Given**
1. M1, but `model_number "L-200"`, `manufacturer "Acme"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(manufacturer=""), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `manufacturer is None`.

### MCM-U-25 — a whitespace-only model number is stored as None
- **Rules:** `update_machine` R6 [BUG-967]
- **Kind:** bug
- **Expect:** xfail BUG-967
- **Fails today on:** Then 2 (the three spaces are stored)

**Given**
1. M1, but `model_number "L-200"`, `manufacturer "Acme"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(model_number="   "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `model_number is None`.

### MCM-U-26 — a whitespace-only manufacturer is stored as None
- **Rules:** `update_machine` R6 [BUG-967]
- **Kind:** bug
- **Expect:** xfail BUG-967
- **Fails today on:** Then 2 (the tab is stored)

**Given**
1. M1, but `model_number "L-200"`, `manufacturer "Acme"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(manufacturer="\t"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `manufacturer is None`.

### MCM-U-27 — a note is stored as sent, padding kept
- **Rules:** `update_machine` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(note="  Bay 4 "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `note == "  Bay 4 "`.

### MCM-U-28 — an empty note is stored as an empty string
- **Rules:** `update_machine` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1, but `note "Bay 3"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(note=""), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `note == ""`.

### MCM-U-29 — a model_number of 201 characters is rejected by MachineUpdate
- **Rules:** `update_machine` R6a [BUG-972], Errors row 7
- **Kind:** bug
- **Expect:** xfail BUG-972
- **Fails today on:** Then 1 (no error is raised; the schema has no limit)

**Given**
1. M1.

**When**
- `MachineUpdate(model_number="x" * 201)` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(M1).

### MCM-U-30 — a model_number of exactly 200 characters is accepted and stored
- **Rules:** `update_machine` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(model_number="x" * 200), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `model_number == "x" * 200`.

### MCM-U-31 — a manufacturer of 201 characters is rejected by MachineUpdate
- **Rules:** `update_machine` R6a [BUG-972], Errors row 7
- **Kind:** bug
- **Expect:** xfail BUG-972
- **Fails today on:** Then 1 (no error is raised; the schema has no limit)

**Given**
1. M1.

**When**
- `MachineUpdate(manufacturer="x" * 201)` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(M1).

### MCM-U-32 — a manufacturer of exactly 200 characters is accepted and stored
- **Rules:** `update_machine` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(manufacturer="x" * 200), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `manufacturer == "x" * 200`.

### MCM-U-33 — a sent name is stored trimmed
- **Rules:** `update_machine` R7 [BUG-950]
- **Kind:** bug
- **Expect:** xfail BUG-950
- **Fails today on:** Then 2 (the name is stored as sent, with the outer spaces)

**Given**
1. M1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(name="  Big  Lathe "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `name == "Big  Lathe"`.

### MCM-U-34 — the own name with outer spaces counts as equal: nothing changes
- **Rules:** `update_machine` R7 [BUG-950], R9
- **Kind:** bug
- **Expect:** xfail BUG-950
- **Fails today on:** Then 2 (the padded name is written)

**Given**
1. M1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(name=" Lathe "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `name == "Lathe"`.
3. event: events_of(M1) has exactly 0 rows.

### MCM-U-35 — an empty name is rejected by MachineUpdate
- **Rules:** `update_machine` R7 [BUG-950], Errors row 7
- **Kind:** bug
- **Expect:** xfail BUG-950
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. M1.

**When**
- `MachineUpdate(name="")` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(M1).

### MCM-U-36 — a name of three spaces is rejected by MachineUpdate
- **Rules:** `update_machine` R7 [BUG-950], Errors row 7
- **Kind:** bug
- **Expect:** xfail BUG-950
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. M1.

**When**
- `MachineUpdate(name="   ")` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(M1).

### MCM-U-37 — a name of one tab is rejected by MachineUpdate
- **Rules:** `update_machine` R7 [BUG-950], Errors row 7
- **Kind:** bug
- **Expect:** xfail BUG-950
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. M1.

**When**
- `MachineUpdate(name="\t")` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(M1).

### MCM-U-38 — a one-character name is accepted by MachineUpdate
- **Rules:** `update_machine` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = MachineUpdate(name="a")` (target `schema`; M is not called).

**Then**
1. returns: `result.name == "a"`.

### MCM-U-39 — a name used by another live machine of the factory is refused and the other fields are not applied
- **Rules:** `update_machine` R8, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.
2. M2.

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(name="Press", note="Bay 4"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Machine with name 'Press' already exists in this factory"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).
6. unchanged: unchanged(M2).

### MCM-U-40 — a name that differs only in case from another machine's is refused
- **Rules:** `update_machine` R8 [BUG-952], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-952
- **Fails today on:** Then 1 (no error is raised: names are compared exactly)

**Given**
1. M1.
2. M2.

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(name="PRESS"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Machine with name 'PRESS' already exists in this factory"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).

### MCM-U-41 — a name used only by a soft-deleted machine is free
- **Rules:** `update_machine` R8
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1.
2. MX.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(name="Old Saw"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `name == "Old Saw"`.
3. unchanged: unchanged(MX).

### MCM-U-42 — a name used only in another factory is free
- **Rules:** `update_machine` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M3.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(name="Drill"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `name == "Drill"`.
3. unchanged: unchanged(M3).

### MCM-U-43 — the name is checked in the resulting factory on a move with a new name
- **Rules:** `update_machine` R8, R10, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.
2. M3.

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(name="Drill", factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Machine with name 'Drill' already exists in this factory"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).

### MCM-U-44 — the own name sent unchanged succeeds and writes no event
- **Rules:** `update_machine` R9, R27
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(name="Lathe"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `name == "Lathe"`.
3. event: events_of(M1) has exactly 0 rows.

### MCM-U-45 — changing only the case of the own name succeeds
- **Rules:** `update_machine` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(name="LATHE"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `name == "LATHE"`.
3. event: events_of(M1) has exactly 1 row.
4. event: `events_of(M1)[0].metadata_json == {"changes": [{"field": "name", "label": "Name", "from_value": "Lathe", "to_value": "LATHE"}]}`.

### MCM-U-46 — a plain move into a factory with a live machine of that name is refused
- **Rules:** `update_machine` R10 [BUG-954], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-954
- **Fails today on:** Then 1 (no error is raised: the move is saved and two live machines share the name)

**Given**
1. M1.
2. M3, but `name "Lathe"`.

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Machine with name 'Lathe' already exists in this factory"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).

### MCM-U-47 — a move re-sending the same name into a factory with a live machine of that name is refused
- **Rules:** `update_machine` R10 [BUG-954], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-954
- **Fails today on:** Then 1 (no error is raised: the move is saved and two live machines share the name)

**Given**
1. M1.
2. M3, but `name "Lathe"`.

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id, name="Lathe"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Machine with name 'Lathe' already exists in this factory"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).

### MCM-U-48 — a plain move into a factory where the name is free succeeds
- **Rules:** `update_machine` R10, R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `factory_id == F2.id`.
3. re-read M1: `name == "Lathe"`.
4. re-read M1: `updated_by == U2.id`.

### MCM-U-49 — a plain move next to a soft-deleted machine of that name succeeds
- **Rules:** `update_machine` R10
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1.
2. MX, but `name "Lathe"`, `factory_id F2.id`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `factory_id == F2.id`.
3. unchanged: unchanged(MX).

### MCM-U-50 — a move with a new name free in the target succeeds, even if taken in the old factory
- **Rules:** `update_machine` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M2.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(name="Press", factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `name == "Press"`, `factory_id == F2.id`.
3. unchanged: unchanged(M2).

### MCM-U-51 — a duplicate that reaches the flush gets the 409, not a database error
- **Rules:** `update_machine` R10a [BUG-953], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-953
- **Fails today on:** Then 1 (no error is raised: there is no index, so the rename is saved)

**Given**
1. M1.
2. M2.
3. Race simulation: `MachineManager._check_name_exists_in_factory` is patched to return `False` (Conventions, Race simulations).

**When**
- wrapped as `with pytest.raises(HTTPException) as exc:` then `with db.begin_nested():` then `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(name="Press"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Machine with name 'Press' already exists in this factory"`.
4. re-read M1: `name == "Lathe"`.
5. count: `machines` with `name == "Press"` has exactly 1 row.

### MCM-U-52 — a target factory that does not exist is refused
- **Rules:** `update_machine` R11, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=MISSING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).

### MCM-U-53 — a target factory of another workspace is refused as not found
- **Rules:** `update_machine` R11, Errors row 3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1.

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F9.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {F9.id} not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).

### MCM-U-54 — a soft-deleted target factory is refused
- **Rules:** `update_machine` R12 [BUG-963], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-963
- **Fails today on:** Then 1 (no error is raised: the machine is moved)

**Given**
1. M1.

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=FD.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot move machine to deleted factory"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).

### MCM-U-55 — the deleted-target refusal comes before the name check
- **Rules:** `update_machine` R12 [BUG-963], R15, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-963
- **Fails today on:** Then 2 (today the name check answers 409)

**Given**
1. M1.
2. MF.

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(name="Kiln", factory_id=FD.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot move machine to deleted factory"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).

### MCM-U-56 — a live but inactive target factory is accepted
- **Rules:** `update_machine` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=FI.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `factory_id == FI.id`.

### MCM-U-57 — factory id 0 is checked like any id
- **Rules:** `update_machine` R13 [BUG-961], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-961
- **Fails today on:** Then 1 (the call raises IntegrityError: 0 skips the check and is written, `machines_factory_id_fkey`)

**Given**
1. M1.

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 0 not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).

### MCM-U-58 — the current factory id sent changes nothing for that field and writes no event
- **Rules:** `update_machine` R14, R27
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `factory_id == F1.id`.
3. event: events_of(M1) has exactly 0 rows.

### MCM-U-59 — the target factory is checked before the name
- **Rules:** `update_machine` R15, Errors row 3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M2.

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(name="Press", factory_id=MISSING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).

### MCM-U-60 — the name is checked before the section
- **Rules:** `update_machine` R15, Errors row 5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M2.

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(name="Press", factory_section_id=MISSING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Machine with name 'Press' already exists in this factory"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).

### MCM-U-61 — a section not sent leaves the link untouched
- **Rules:** `update_machine` R16
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. L1 = link of M1 to S1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(note="Bay 4"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. unchanged: unchanged(L1).
3. returns: `result.factory_section_id == S1.id`.

### MCM-U-62 — a section is set on a machine without one
- **Rules:** `update_machine` R17, R24, R23
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_section_id=S1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. returns: `result.factory_section_id == S1.id`.
3. returns: `result.factory_section_name == "Cutting"`.
4. count: `machine_section_assignments` has exactly 1 row.
5. re-read the one row of links_of(M1): `factory_section_id == S1.id`, `created_by == U2.id`.
6. re-read M1: `updated_by == U2.id`.
7. re-read M1: `updated_at is not None`.

### MCM-U-63 — a section is moved and the returned machine reads the new value although the link was loaded
- **Rules:** `update_machine` R17
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. L1 = link of M1 to S1.
3. `loaded = M1.factory_section_id` (reads the link into the session).

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_section_id=S2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. returns: `result.factory_section_id == S2.id`.
3. returns: `result.factory_section_name == "Paint"`.
4. count: `machine_section_assignments` has exactly 1 row.

### MCM-U-64 — a section is cleared and the returned machine reads None although the link was loaded
- **Rules:** `update_machine` R17
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. L1 = link of M1 to S1.
3. `loaded = M1.factory_section_id` (reads the link into the session).

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_section_id=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. returns: `result.factory_section_id is None`.
3. returns: `result.factory_section_name is None`.
4. re-read: `links_of(M1) == []`.

### MCM-U-65 — clearing a section the machine does not have changes nothing
- **Rules:** `update_machine` R17, R27
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_section_id=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read: `links_of(M1) == []`.
3. event: events_of(M1) has exactly 0 rows.

### MCM-U-66 — a move with a section of the new factory links it, and both changes are logged in order
- **Rules:** `update_machine` R17, R26
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1.
2. L1 = link of M1 to S1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id, factory_section_id=S3.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. returns: `result.factory_section_id == S3.id`.
3. returns: `result.factory_section_name == "Welding"`.
4. re-read M1: `factory_id == F2.id`.
5. event: `events_of(M1)[0].metadata_json == {"changes": [{"field": "factory_id", "label": "Factory", "from_value": str(F1.id), "to_value": str(F2.id)}, {"field": "factory_section_id", "label": "Section", "from_value": str(S1.id), "to_value": str(S3.id)}]}`.

### MCM-U-67 — a section id that does not exist is refused; the field changes stay flushed until the rollback
- **Rules:** `update_machine` R17, R21, Errors row 6
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.
2. Savepoint per **refused after flush** (Conventions).

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(note="Bay 4", factory_section_id=MISSING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory section with ID 999999999 not found"`.
4. re-read M1: `note == "Bay 4"`, `updated_by == U2.id`.
5. re-read: `links_of(M1) == []`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged after the savepoint rollback: unchanged(M1).

### MCM-U-68 — section id 0 is refused; the field changes stay flushed until the rollback
- **Rules:** `update_machine` R17, R21, Errors row 6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. Savepoint per **refused after flush** (Conventions).

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(note="Bay 4", factory_section_id=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory section with ID 0 not found"`.
4. re-read M1: `note == "Bay 4"`, `updated_by == U2.id`.
5. re-read: `links_of(M1) == []`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged after the savepoint rollback: unchanged(M1).

### MCM-U-69 — a soft-deleted section is refused; the field changes stay flushed until the rollback
- **Rules:** `update_machine` R17, R21, Errors row 6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1.
2. Savepoint per **refused after flush** (Conventions).

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(note="Bay 4", factory_section_id=SX.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot assign a machine to a deleted factory section"`.
4. re-read M1: `note == "Bay 4"`, `updated_by == U2.id`.
5. re-read: `links_of(M1) == []`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged after the savepoint rollback: unchanged(M1).

### MCM-U-70 — a section of another factory is refused; the field changes stay flushed until the rollback
- **Rules:** `update_machine` R17, R21, Errors row 6
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.
2. Savepoint per **refused after flush** (Conventions).

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(note="Bay 4", factory_section_id=S3.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Factory section does not belong to this machine's factory"`.
4. re-read M1: `note == "Bay 4"`, `updated_by == U2.id`.
5. re-read: `links_of(M1) == []`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged after the savepoint rollback: unchanged(M1).

### MCM-U-71 — a section of another workspace is refused; the field changes stay flushed until the rollback
- **Rules:** `update_machine` R17, R21, Errors row 6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1.
2. Savepoint per **refused after flush** (Conventions).

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(note="Bay 4", factory_section_id=S9.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory section with ID {S9.id} not found"`.
4. re-read M1: `note == "Bay 4"`, `updated_by == U2.id`.
5. re-read: `links_of(M1) == []`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged after the savepoint rollback: unchanged(M1).

### MCM-U-72 — a section of the old factory sent with a move is refused
- **Rules:** `update_machine` R17, R21, Errors row 6
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.
2. L1 = link of M1 to S1.
3. Savepoint per **refused after flush** (Conventions).

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id, factory_section_id=S1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Factory section does not belong to this machine's factory"`.
4. count: `machine_activity_events` has exactly 0 rows.
5. unchanged after the savepoint rollback: unchanged(M1).
6. unchanged after the savepoint rollback: unchanged(L1).

### MCM-U-73 — re-sending the current section keeps the link row
- **Rules:** `update_machine` R18 [BUG-909]
- **Kind:** bug
- **Expect:** xfail BUG-909
- **Fails today on:** Then 3 (the link is deleted and re-created with a new id)

**Given**
1. M1.
2. L1 = link of M1 to S1.
3. `l1_id = L1.id`

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_section_id=S1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. count: `machine_section_assignments` has exactly 1 row.
3. re-read: `links_of(M1)[0].id == l1_id`.
4. re-read: `links_of(M1)[0].created_by == U1.id`.

### MCM-U-74 — re-sending the current section leaves one link to it and no event
- **Rules:** `update_machine` R18, R27
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. L1 = link of M1 to S1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_section_id=S1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. count: `machine_section_assignments` has exactly 1 row.
3. re-read: `links_of(M1)[0].factory_section_id == S1.id`.
4. event: events_of(M1) has exactly 0 rows.

### MCM-U-75 — an edit re-sending a left-over link to a deleted section succeeds and keeps the link
- **Rules:** `update_machine` R19 [BUG-971]
- **Kind:** bug
- **Expect:** xfail BUG-971
- **Fails today on:** Then 1 (the call raises HTTPException: 400 `Cannot assign a machine to a deleted factory section`)

**Given**
1. M1.
2. L1 = link of M1 to SX.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(note="Bay 4", factory_section_id=SX.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `note == "Bay 4"`.
3. re-read: `links_of(M1)[0].factory_section_id == SX.id`.

### MCM-U-76 — a left-over link to a deleted section can be cleared
- **Rules:** `update_machine` R19
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1.
2. L1 = link of M1 to SX.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_section_id=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read: `links_of(M1) == []`.

### MCM-U-77 — an edit that omits a left-over link to a deleted section works
- **Rules:** `update_machine` R19, R16
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1.
2. L1 = link of M1 to SX.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(note="Bay 4"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `note == "Bay 4"`.
3. unchanged: unchanged(L1).

### MCM-U-78 — a deleted section re-sent with a move is still validated
- **Rules:** `update_machine` R19, R17, Errors row 6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1.
2. L1 = link of M1 to SX.
3. Savepoint per **refused after flush** (Conventions).

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id, factory_section_id=SX.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot assign a machine to a deleted factory section"`.
4. count: `machine_activity_events` has exactly 0 rows.
5. unchanged after the savepoint rollback: unchanged(M1).
6. unchanged after the savepoint rollback: unchanged(L1).

### MCM-U-79 — a move without a section clears the old factory's section
- **Rules:** `update_machine` R20 [BUG-970]
- **Kind:** bug
- **Expect:** xfail BUG-970
- **Fails today on:** Then 3 (the link stays on a section of the old factory)

**Given**
1. M1.
2. L1 = link of M1 to S1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `factory_id == F2.id`.
3. re-read: `links_of(M1) == []`.
4. returns: `result.factory_section_id is None`.

### MCM-U-80 — the log of such a move records the section change
- **Rules:** `update_machine` R20 [BUG-970], R26
- **Kind:** bug
- **Expect:** xfail BUG-970
- **Fails today on:** Then 3 (`changes` lists only `factory_id`)

**Given**
1. M1.
2. L1 = link of M1 to S1.
3. `s1_id = S1.id`

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. event: events_of(M1) has exactly 1 row.
3. event: `events_of(M1)[0].metadata_json == {"changes": [{"field": "factory_id", "label": "Factory", "from_value": str(F1.id), "to_value": str(F2.id)}, {"field": "factory_section_id", "label": "Section", "from_value": str(s1_id), "to_value": None}]}`.

### MCM-U-81 — a move of a machine without a section logs only the factory
- **Rules:** `update_machine` R20, R26, R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. event: events_of(M1) has exactly 1 row.
3. event: that row has `event_type == "updated"`, `description == "Machine details updated"`.
4. event: that row has `performed_by == U2.id`, `workspace_id == W1.id`.
5. event: that row has `metadata_json == {"changes": [{"field": "factory_id", "label": "Factory", "from_value": str(F1.id), "to_value": str(F2.id)}]}`.

### MCM-U-82 — a move with an explicit null clears the link and logs both
- **Rules:** `update_machine` R17, R26
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. L1 = link of M1 to S1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id, factory_section_id=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read: `links_of(M1) == []`.
3. event: `events_of(M1)[0].metadata_json == {"changes": [{"field": "factory_id", "label": "Factory", "from_value": str(F1.id), "to_value": str(F2.id)}, {"field": "factory_section_id", "label": "Section", "from_value": str(S1.id), "to_value": None}]}`.

### MCM-U-83 — the current factory id sent without a section keeps the link
- **Rules:** `update_machine` R20, R16, R14
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. L1 = link of M1 to S1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. unchanged: unchanged(L1).

### MCM-U-84 — an empty request leaves the audit stamp alone
- **Rules:** `update_machine` R24 [BUG-959]
- **Kind:** bug
- **Expect:** xfail BUG-959
- **Fails today on:** Then 2 (`updated_by` is stamped on every successful call)

**Given**
1. M1, but `note "Bay 3"`, `updated_by None`, `updated_at None`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `updated_by is None`.
3. re-read M1: `updated_at is None`.

### MCM-U-85 — values equal to the current ones leaves the audit stamp alone
- **Rules:** `update_machine` R24 [BUG-959]
- **Kind:** bug
- **Expect:** xfail BUG-959
- **Fails today on:** Then 2 (`updated_by` is stamped on every successful call)

**Given**
1. M1, but `note "Bay 3"`, `updated_by None`, `updated_at None`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(name="Lathe", note="Bay 3"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `updated_by is None`.
3. re-read M1: `updated_at is None`.

### MCM-U-86 — clearing an empty section leaves the audit stamp alone
- **Rules:** `update_machine` R24 [BUG-959]
- **Kind:** bug
- **Expect:** xfail BUG-959
- **Fails today on:** Then 2 (`updated_by` is stamped on every successful call)

**Given**
1. M1, but `note "Bay 3"`, `updated_by None`, `updated_at None`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_section_id=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `updated_by is None`.
3. re-read M1: `updated_at is None`.

### MCM-U-87 — the current factory id leaves the audit stamp alone
- **Rules:** `update_machine` R24 [BUG-959]
- **Kind:** bug
- **Expect:** xfail BUG-959
- **Fails today on:** Then 2 (`updated_by` is stamped on every successful call)

**Given**
1. M1, but `note "Bay 3"`, `updated_by None`, `updated_at None`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `updated_by is None`.
3. re-read M1: `updated_at is None`.

### MCM-U-88 — a no-op keeps another user's stamp
- **Rules:** `update_machine` R24 [BUG-959]
- **Kind:** bug
- **Expect:** xfail BUG-959
- **Fails today on:** Then 2 (`updated_by` becomes U2)

**Given**
1. M1, but `updated_by U1.id`, `updated_at T0`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `updated_by == U1.id`.
3. re-read M1: `updated_at == T0`.

### MCM-U-89 — re-sending the section leaves the audit stamp alone
- **Rules:** `update_machine` R24 [BUG-959]
- **Kind:** bug
- **Expect:** xfail BUG-959
- **Fails today on:** Then 2 (`updated_by` is stamped on every successful call)

**Given**
1. M1.
2. L1 = link of M1 to S1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_section_id=S1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `updated_by is None`.

### MCM-U-90 — a no-op by the user already stamped writes nothing
- **Rules:** `update_machine` R24, R27
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1, but `updated_by U2.id`, `updated_at T0`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `updated_by == U2.id`.
3. re-read M1: `updated_at == T0`.
4. event: events_of(M1) has exactly 0 rows.

### MCM-U-91 — an empty request writes no event
- **Rules:** `update_machine` R27
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. event: events_of(M1) has exactly 0 rows.

### MCM-U-92 — values equal to the current ones write no event
- **Rules:** `update_machine` R27
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1, but `note "Bay 3"`, `model_number "L-200"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(name="Lathe", note="Bay 3", model_number="L-200"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. event: events_of(M1) has exactly 0 rows.

### MCM-U-93 — one updated event lists every changed field in the fixed order
- **Rules:** `update_machine` R25, R26
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1, but `model_number "L-200"`, `manufacturer "Acme"`, `note "Bay 3"`.
2. L1 = link of M1 to S1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(note="Bay 4", manufacturer="Haas", model_number="L-300", factory_section_id=S3.id, factory_id=F2.id, name="Big Lathe"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. event: events_of(M1) has exactly 1 row.
3. event: that row has `event_type == "updated"`, `description == "Machine details updated"`.
4. event: that row has `performed_by == U2.id`, `workspace_id == W1.id`.
5. event: that row has `metadata_json == {"changes": [{"field": "name", "label": "Name", "from_value": "Lathe", "to_value": "Big Lathe"}, {"field": "factory_id", "label": "Factory", "from_value": str(F1.id), "to_value": str(F2.id)}, {"field": "factory_section_id", "label": "Section", "from_value": str(S1.id), "to_value": str(S3.id)}, {"field": "model_number", "label": "Model number", "from_value": "L-200", "to_value": "L-300"}, {"field": "manufacturer", "label": "Manufacturer", "from_value": "Acme", "to_value": "Haas"}, {"field": "note", "label": "Note", "from_value": "Bay 3", "to_value": "Bay 4"}]}`.

### MCM-U-94 — a field that did not change is left out of the log
- **Rules:** `update_machine` R26
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1, but `note "Bay 3"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(name="Lathe", note="Bay 4"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. event: events_of(M1) has exactly 1 row.
3. event: that row has `event_type == "updated"`, `description == "Machine details updated"`.
4. event: that row has `performed_by == U2.id`, `workspace_id == W1.id`.
5. event: that row has `metadata_json == {"changes": [{"field": "note", "label": "Note", "from_value": "Bay 3", "to_value": "Bay 4"}]}`.

### MCM-U-95 — a section set from none is logged from None
- **Rules:** `update_machine` R26
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_section_id=S1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. event: events_of(M1) has exactly 1 row.
3. event: that row has `event_type == "updated"`, `description == "Machine details updated"`.
4. event: that row has `performed_by == U2.id`, `workspace_id == W1.id`.
5. event: that row has `metadata_json == {"changes": [{"field": "factory_section_id", "label": "Section", "from_value": None, "to_value": str(S1.id)}]}`.

### MCM-U-96 — a cleared section is logged to None
- **Rules:** `update_machine` R26
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. L1 = link of M1 to S1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_section_id=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. event: events_of(M1) has exactly 1 row.
3. event: that row has `event_type == "updated"`, `description == "Machine details updated"`.
4. event: that row has `performed_by == U2.id`, `workspace_id == W1.id`.
5. event: that row has `metadata_json == {"changes": [{"field": "factory_section_id", "label": "Section", "from_value": str(S1.id), "to_value": None}]}`.

### MCM-U-97 — a value set on an empty field is logged from None
- **Rules:** `update_machine` R26
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(model_number="L-200"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. event: events_of(M1) has exactly 1 row.
3. event: that row has `event_type == "updated"`, `description == "Machine details updated"`.
4. event: that row has `performed_by == U2.id`, `workspace_id == W1.id`.
5. event: that row has `metadata_json == {"changes": [{"field": "model_number", "label": "Model number", "from_value": None, "to_value": "L-200"}]}`.

### MCM-U-98 — an open DRAFT order follows the moved machine
- **Rules:** `update_machine` R28 [BUG-975]
- **Kind:** bug
- **Expect:** xfail BUG-975
- **Fails today on:** Then 3 (the order keeps the old factory)

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `factory_id == F2.id`.
3. re-read O1: `factory_id == F2.id`.
4. re-read O1: `updated_by == U2.id`.
5. re-read O1: `updated_at is not None`.

### MCM-U-99 — every open order of the machine follows, whatever its state
- **Rules:** `update_machine` R28 [BUG-975], R28f
- **Kind:** bug
- **Expect:** xfail BUG-975
- **Fails today on:** Then 2 (no order changes)

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.
3. O2 = order of M1, `status "IN_PROGRESS"`.
4. O3 = order of M1, `status "DRAFT"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read O1: `factory_id == F2.id`.
3. re-read O2: `factory_id == F2.id`.
4. re-read O3: `factory_id == F2.id`.

### MCM-U-100 — the columns of a moved order other than factory and update stamp stay
- **Rules:** `update_machine` R28
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`, `planned_date D(3)`, `required_approvals 2`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read O1: `title == "Service"`, `status == "DRAFT"`, `work_order_number == "WO-O1"`.
3. re-read O1: `planned_date == D(3)`, `machine_id == M1.id`, `workspace_id == W1.id`.
4. re-read O1: `required_approvals == 2`, `is_deleted is False`, `work_order_type_id == WT1.id`.

### MCM-U-101 — each state that is not open, and every other order, stays when one order per state exists
- **Rules:** `update_machine` R28 [BUG-975], R28a, R28f
- **Kind:** bug
- **Expect:** xfail BUG-975
- **Fails today on:** Then 2 (no order changes)

**Given**
1. M1.
2. M2.
3. O1 = order of M1, `status "DRAFT"`.
4. O2 = order of M1, `status "IN_PROGRESS"`.
5. O3 = order of M1, `status "COMPLETED"`.
6. O4 = order of M1, `status "VOIDED"`.
7. O5 = order of M1, `status "DRAFT"`, `is_deleted True`.
8. O6 = order of M2, `status "DRAFT"`.
9. L6 = line of O6, `source_location_type "machine"`, `source_location_id M1.id`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read O1: `factory_id == F2.id`.
3. re-read O2: `factory_id == F2.id`.
4. unchanged: unchanged(O3).
5. unchanged: unchanged(O4).
6. unchanged: unchanged(O5).
7. unchanged: unchanged(O6).
8. count: `work_order_events` has exactly 2 rows.

### MCM-U-102 — a completed order stays in the old factory
- **Rules:** `update_machine` R28a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "COMPLETED"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `factory_id == F2.id`.
3. unchanged: unchanged(O1).
4. count: `work_order_events` has exactly 0 rows.

### MCM-U-103 — a voided order stays in the old factory
- **Rules:** `update_machine` R28a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "VOIDED"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `factory_id == F2.id`.
3. unchanged: unchanged(O1).
4. count: `work_order_events` has exactly 0 rows.

### MCM-U-104 — a soft-deleted order stays in the old factory
- **Rules:** `update_machine` R28a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`, `is_deleted True`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `factory_id == F2.id`.
3. unchanged: unchanged(O1).
4. count: `work_order_events` has exactly 0 rows.

### MCM-U-105 — an order of another machine with a line sourcing from this machine stays
- **Rules:** `update_machine` R28a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M2.
3. O1 = order of M2, `status "DRAFT"`.
4. L1 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. unchanged: unchanged(O1).
3. unchanged: unchanged(L1).
4. count: `work_order_events` has exactly 0 rows.

### MCM-U-106 — an order with this machine id in another workspace stays
- **Rules:** `update_machine` R28a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1.
2. O9 = order of M1, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. unchanged: unchanged(O9).
3. count: `work_order_events` has exactly 0 rows.

### MCM-U-107 — the current factory id sent changes no order and writes no order event
- **Rules:** `update_machine` R28b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F1.id, note="Bay 4"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `note == "Bay 4"`.
3. unchanged: unchanged(O1).
4. count: `work_order_events` has exactly 0 rows.

### MCM-U-108 — an edit without a factory changes no order and writes no order event
- **Rules:** `update_machine` R28b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(name="Big Lathe"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `name == "Big Lathe"`.
3. unchanged: unchanged(O1).
4. count: `work_order_events` has exactly 0 rows.

### MCM-U-109 — a move of a machine without open orders writes no order event
- **Rules:** `update_machine` R28b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `factory_id == F2.id`.
3. count: `work_order_events` has exactly 0 rows.

### MCM-U-110 — a refused move of a machine of another workspace changes no order
- **Rules:** `update_machine` R28b, R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M9.
2. O9 = order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.

**When**
- `M.update_machine(db, machine_id=M9.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
4. unchanged: unchanged(O9).
5. count: `work_order_events` has exactly 0 rows.

### MCM-U-111 — a refused move of a soft-deleted machine changes no order
- **Rules:** `update_machine` R28b, R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MX.
2. O1 = order of MX, `status "DRAFT"`.

**When**
- `M.update_machine(db, machine_id=MX.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted machine"`.
4. unchanged: unchanged(O1).
5. count: `work_order_events` has exactly 0 rows.

### MCM-U-112 — a refused move out of a soft-deleted factory changes no order
- **Rules:** `update_machine` R28b, R3 [BUG-964]
- **Kind:** bug
- **Expect:** xfail BUG-964
- **Fails today on:** Then 1 (no error is raised: the machine moves)

**Given**
1. MF.
2. O1 = order of MF, `status "DRAFT"`, `factory_id FD.id`.

**When**
- `M.update_machine(db, machine_id=MF.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted machine"`.
4. unchanged: unchanged(O1).
5. count: `work_order_events` has exactly 0 rows.

### MCM-U-113 — a move with a taken new name is refused and changes no order
- **Rules:** `update_machine` R28b, R8
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.
3. M3.

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(name="Drill", factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Machine with name 'Drill' already exists in this factory"`.
4. unchanged: unchanged(O1).
5. count: `work_order_events` has exactly 0 rows.
6. unchanged: unchanged(M1).

### MCM-U-114 — a plain move into a taken name is refused and changes no order
- **Rules:** `update_machine` R28b, R10 [BUG-954]
- **Kind:** bug
- **Expect:** xfail BUG-954
- **Fails today on:** Then 1 (no error is raised: the move is saved)

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.
3. M3, but `name "Lathe"`.

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Machine with name 'Lathe' already exists in this factory"`.
4. unchanged: unchanged(O1).
5. count: `work_order_events` has exactly 0 rows.

### MCM-U-115 — a move to a missing factory changes no order
- **Rules:** `update_machine` R28b, R11
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=MISSING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
4. unchanged: unchanged(O1).
5. count: `work_order_events` has exactly 0 rows.

### MCM-U-116 — a move to a factory of another workspace changes no order
- **Rules:** `update_machine` R28b, R11
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F9.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {F9.id} not found"`.
4. unchanged: unchanged(O1).
5. count: `work_order_events` has exactly 0 rows.

### MCM-U-117 — a move to a soft-deleted factory changes no order
- **Rules:** `update_machine` R28b, R12 [BUG-963]
- **Kind:** bug
- **Expect:** xfail BUG-963
- **Fails today on:** Then 1 (no error is raised: the machine is moved)

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=FD.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot move machine to deleted factory"`.
4. unchanged: unchanged(O1).
5. count: `work_order_events` has exactly 0 rows.

### MCM-U-118 — factory id 0 changes no order
- **Rules:** `update_machine` R28b, R13 [BUG-961]
- **Kind:** bug
- **Expect:** xfail BUG-961
- **Fails today on:** Then 1 (the call raises IntegrityError: 0 skips the check and is written)

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 0 not found"`.
4. unchanged: unchanged(O1).
5. count: `work_order_events` has exactly 0 rows.

### MCM-U-119 — a section refused after a move leaves the orders moved and their events written until the rollback
- **Rules:** `update_machine` R28b [BUG-975], R21, Errors row 6
- **Kind:** bug
- **Expect:** xfail BUG-975
- **Fails today on:** Then 5 (the order keeps the old factory)

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.
3. Savepoint per **refused after flush** (Conventions).

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id, factory_section_id=S1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Factory section does not belong to this machine's factory"`.
4. re-read M1: `factory_id == F2.id`.
5. re-read O1: `factory_id == F2.id`.
6. count: `work_order_events` has exactly 1 row.
7. re-read O1 after the savepoint rollback: `factory_id == F1.id`.
8. count after the savepoint rollback: `work_order_events` has exactly 0 rows.

### MCM-U-120 — the rollback after a refused section leaves the order and the machine as they were
- **Rules:** `update_machine` R28b, R21
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.
3. Savepoint per **refused after flush** (Conventions).

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id, factory_section_id=S1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Factory section does not belong to this machine's factory"`.
4. count: `machine_activity_events` has exactly 0 rows.
5. unchanged after the savepoint rollback: unchanged(M1).
6. unchanged after the savepoint rollback: unchanged(O1).
7. count after the savepoint rollback: `work_order_events` has exactly 0 rows.

### MCM-U-121 — a rollback restores moved orders and removes their events
- **Rules:** `update_machine` R28b [BUG-975], R28e
- **Kind:** bug
- **Expect:** xfail BUG-975
- **Fails today on:** Then 2 (the order keeps the old factory)

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.
3. `sp = db.begin_nested()` directly before the call, no spy; `sp.rollback()` before the "after the savepoint rollback" checks.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read O1: `factory_id == F2.id`.
3. count: `work_order_events` has exactly 1 row.
4. re-read O1 after the savepoint rollback: `factory_id == F1.id`.
5. count after the savepoint rollback: `work_order_events` has exactly 0 rows.

### MCM-U-122 — a consumed line keeps its source when its order moves
- **Rules:** `update_machine` R28c
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "IN_PROGRESS"`.
3. L1 = line of O1, `source_location_type "storage"`, `source_location_id F1.id`, `consumed_at T0`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. unchanged: unchanged(L1).
3. re-read L1: `source_location_type == "storage"`, `source_location_id == F1.id`, `consumed_at == T0`.

### MCM-U-123 — a consumed line sourced from a machine keeps its source
- **Rules:** `update_machine` R28c
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M2.
3. O1 = order of M1, `status "IN_PROGRESS"`.
4. L1 = line of O1, `source_location_type "machine"`, `source_location_id M2.id`, `consumed_at T0`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. unchanged: unchanged(L1).

### MCM-U-124 — an unconsumed line keeps the old factory's store as its source
- **Rules:** `update_machine` R28d
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.
3. L1 = line of O1, `source_location_type "storage"`, `source_location_id F1.id`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. unchanged: unchanged(L1).
3. re-read L1: `source_location_type == "storage"`, `source_location_id == F1.id`, `consumed_at is None`.

### MCM-U-125 — an unconsumed line sourced from a machine is unaffected
- **Rules:** `update_machine` R28d
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M2.
3. O1 = order of M1, `status "DRAFT"`.
4. L1 = line of O1, `source_location_type "machine"`, `source_location_id M2.id`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. unchanged: unchanged(L1).

### MCM-U-126 — a move keeps recorded approvals, approver rows and required approvals of a moved DRAFT
- **Rules:** `update_machine` R28d
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`, `required_approvals 2`, `approved_by U1.id`, `approved_at T0`.
3. AP1 = approver of O1, U1, `approved True`, `approved_at T0`.
4. `approvers_before = db.execute(text("select * from work_order_approvers where work_order_id = :i order by id"), {"i": O1.id}).all()`

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read: `db.execute(text("select * from work_order_approvers where work_order_id = :i order by id"), {"i": O1.id}).all() == approvers_before`.
3. re-read AP1: `approved is True`, `approved_at == T0`.
4. re-read O1: `required_approvals == 2`, `approved_by == U1.id`, `approved_at == T0`.

### MCM-U-127 — each moved order gets one updated event with the factory change
- **Rules:** `update_machine` R28e [BUG-975], Side effects
- **Kind:** bug
- **Expect:** xfail BUG-975
- **Fails today on:** Then 2 (no order event is written)

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. event: wo_events(O1) has exactly 1 row.
3. event: that row has `work_order_id == O1.id`, `workspace_id == W1.id`, `event_type == "updated"`.
4. event: that row has `description == "Order details updated"`, `performed_by == U2.id`, `created_at is not None`.
5. event: that row has `metadata_json == {"changes": [{"field": "factory_id", "label": "Factory", "from_value": str(F1.id), "to_value": str(F2.id)}]}`.

### MCM-U-128 — two moved orders get one event each
- **Rules:** `update_machine` R28e [BUG-975]
- **Kind:** bug
- **Expect:** xfail BUG-975
- **Fails today on:** Then 2 (no order event is written)

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.
3. O2 = order of M1, `status "IN_PROGRESS"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. event: wo_events(O1) has exactly 1 row.
3. event: wo_events(O2) has exactly 1 row.
4. count: `work_order_events` has exactly 2 rows.

### MCM-U-129 — the order's event holds only the factory, also when the machine is renamed in the same call
- **Rules:** `update_machine` R28e [BUG-975]
- **Kind:** bug
- **Expect:** xfail BUG-975
- **Fails today on:** Then 3 (no order event is written)

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id, name="Big Lathe", note="Bay 4"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `name == "Big Lathe"`.
3. event: wo_events(O1) has exactly 1 row.
4. event: `wo_events(O1)[0].metadata_json == {"changes": [{"field": "factory_id", "label": "Factory", "from_value": str(F1.id), "to_value": str(F2.id)}]}`.

### MCM-U-130 — the machine's own log records a move with open orders as usual
- **Rules:** `update_machine` R28e, R25
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. event: events_of(M1) has exactly 1 row.
3. event: that row has `event_type == "updated"`, `description == "Machine details updated"`.
4. event: that row has `performed_by == U2.id`, `workspace_id == W1.id`.
5. event: that row has `metadata_json == {"changes": [{"field": "factory_id", "label": "Factory", "from_value": str(F1.id), "to_value": str(F2.id)}]}`.

### MCM-U-131 — an IN_PROGRESS order moves like a draft
- **Rules:** `update_machine` R28f [BUG-975]
- **Kind:** bug
- **Expect:** xfail BUG-975
- **Fails today on:** Then 2 (the order keeps the old factory)

**Given**
1. M1.
2. O1 = order of M1, `status "IN_PROGRESS"`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read O1: `factory_id == F2.id`.
3. re-read O1: `status == "IN_PROGRESS"`.
4. re-read O1: `updated_by == U2.id`.

### MCM-U-132 — consumed parts of an IN_PROGRESS order stay booked out of the old factory
- **Rules:** `update_machine` R28f, R28c
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "IN_PROGRESS"`.
3. L1 = line of O1, `source_location_type "storage"`, `source_location_id F1.id`, `consumed_at T0`.
4. LG = stock movement row of I1 in F1 (`inventory_ledger`, Conventions).

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. unchanged: unchanged(LG).
3. unchanged: unchanged(L1).
4. re-read LG: `factory_id == F1.id`.

### MCM-U-133 — an unknown user fails on flush and nothing is saved
- **Rules:** `update_machine` R29, Errors row 8
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(note="Bay 4"), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"machines_updated_by_fkey" in str(exc.value.orig)`.
4. count: `machine_activity_events` has exactly 0 rows.
5. unchanged: unchanged(M1).

### MCM-U-134 — an empty request by an unknown user succeeds, because nothing is written
- **Rules:** `update_machine` R29 [BUG-959]
- **Kind:** bug
- **Expect:** xfail BUG-959
- **Fails today on:** Then 1 (the call raises IntegrityError: `updated_by` is written on every call)

**Given**
1. M1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. unchanged: unchanged(M1).

### MCM-U-135 — the update is flushed but not committed: a rollback restores the row and removes the event
- **Rules:** `update_machine` R30, R28b, Returns
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.
3. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(name="Big Lathe", factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `name == "Big Lathe"`, `factory_id == F2.id`.
3. event: events_of(M1) has exactly 1 row.
4. unchanged after the savepoint rollback: unchanged(M1).
5. unchanged after the savepoint rollback: unchanged(O1).
6. count after the savepoint rollback: `machine_activity_events` has exactly 0 rows.
7. count after the savepoint rollback: `work_order_events` has exactly 0 rows.
8. mock called: the `db.commit` spy was never called.

### MCM-U-136 — a move keeps the assignee rows and the assigned_to text of a moved order
- **Rules:** `update_machine` R28
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`, `assigned_to "Rahim Uddin"`.
3. AS1 = assignee of O1, U1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. unchanged: unchanged(AS1).
3. count: `work_order_assignees` has exactly 1 row.
4. re-read O1: `assigned_to == "Rahim Uddin"`.

### MCM-U-137 — a section-only change by the user already stamped writes no column of the machine, but the link and the event
- **Rules:** `update_machine` R23, R24, R25
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1, but `updated_by U2.id`, `updated_at T0`.
2. L1 = link of M1 to S1.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_section_id=S2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. returns: `result.factory_section_id == S2.id`.
3. re-read M1: `updated_by == U2.id`.
4. re-read M1: `updated_at == T0`.
5. event: events_of(M1) has exactly 1 row.
6. event: that row has `event_type == "updated"`, `description == "Machine details updated"`.
7. event: that row has `performed_by == U2.id`, `workspace_id == W1.id`.
8. event: that row has `metadata_json == {"changes": [{"field": "factory_section_id", "label": "Section", "from_value": str(S1.id), "to_value": str(S2.id)}]}`.

### MCM-U-138 — an open order not in the machine's old factory still moves
- **Rules:** `update_machine` R28 [BUG-975], R28e
- **Kind:** bug
- **Expect:** xfail BUG-975
- **Fails today on:** Then 2 (the order keeps its factory)

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`, `factory_id FI.id`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read O1: `factory_id == F2.id`.
3. re-read O1: `updated_by == U2.id`.
4. event: wo_events(O1) has exactly 1 row.
5. event: `wo_events(O1)[0].metadata_json["changes"][0]["to_value"] == str(F2.id)`.
6. event: `wo_events(O1)[0].metadata_json["changes"][0]["from_value"] == str(FI.id)`.

### MCM-U-139 — a production line keeps its factory when its machine moves
- **Rules:** `update_machine` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1.
2. PL1 = `production_lines` row built with `ProductionLine` (`app.models.production_line`): `workspace_id W1.id`, `factory_id F1.id`, `name "Line One"`, `machine_id M1.id`.

**When**
- `result = M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `factory_id == F2.id`.
3. unchanged: unchanged(PL1).
4. re-read PL1: `factory_id == F1.id`.

## `MachineManager.get_machine`

### MCM-G-01 — a live machine of the workspace in a live factory is returned
- **Rules:** `get_machine` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.get_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == M1.id`.
2. returns: `result.name == "Lathe"`.

### MCM-G-02 — is_active and is_running are not consulted
- **Rules:** `get_machine` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1, but `is_active False`, `is_running True`.

**When**
- `result = M.get_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == M1.id`.
2. returns: `result.is_running is True`.

### MCM-G-03 — an id that no machine has gives 404
- **Rules:** `get_machine` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.

**When**
- `M.get_machine(db, machine_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine with ID 999999999 not found"`.

### MCM-G-04 — a machine of another workspace gives 404
- **Rules:** `get_machine` R2, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M9.

**When**
- `M.get_machine(db, machine_id=M9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.

### MCM-G-05 — a soft-deleted machine gives 404 by default
- **Rules:** `get_machine` R3 [BUG-955], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-955
- **Fails today on:** Then 1 (no error is raised: the deleted machine is returned)

**Given**
1. MX.

**When**
- `M.get_machine(db, machine_id=MX.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {MX.id} not found"`.

### MCM-G-06 — with include_deleted a soft-deleted machine is returned
- **Rules:** `get_machine` R4 [BUG-955]
- **Kind:** bug
- **Expect:** xfail BUG-955
- **Fails today on:** Then 1 (the call raises TypeError: `include_deleted` does not exist yet)

**Given**
1. MX.

**When**
- `result = M.get_machine(db, machine_id=MX.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == MX.id`.

### MCM-G-07 — with include_deleted a soft-deleted machine of another workspace still gives 404
- **Rules:** `get_machine` R4 [BUG-955], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-955
- **Fails today on:** Then 1 (the call raises TypeError: `include_deleted` does not exist yet)

**Given**
1. M9, but `is_deleted True`, `is_active False`.

**When**
- `M.get_machine(db, machine_id=M9.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.

### MCM-G-08 — a live machine of a soft-deleted factory gives 404 by default
- **Rules:** `get_machine` R5 [BUG-966], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-966
- **Fails today on:** Then 1 (no error is raised: the machine is returned)

**Given**
1. MF.

**When**
- `M.get_machine(db, machine_id=MF.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {MF.id} not found"`.

### MCM-G-09 — with include_deleted a machine of a soft-deleted factory is returned
- **Rules:** `get_machine` R5 [BUG-966]
- **Kind:** bug
- **Expect:** xfail BUG-966
- **Fails today on:** Then 1 (the call raises TypeError: `include_deleted` does not exist yet)

**Given**
1. MF.

**When**
- `result = M.get_machine(db, machine_id=MF.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == MF.id`.

### MCM-G-10 — a live but inactive factory hides nothing
- **Rules:** `get_machine` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI.

**When**
- `result = M.get_machine(db, machine_id=MI.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == MI.id`.

## `MachineManager.search_machines`

### MCM-S-01 — with defaults the list holds the workspace's machines in name order
- **Rules:** `search_machines` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. MC.
2. MA.
3. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id)`.

**Then**
1. returns: `names(result) == ["Alpha", "Cobalt", "Zenith"]`.
2. returns: `isinstance(result, list)`.

### MCM-S-02 — factory_id is handed to the list
- **Rules:** `search_machines` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. MA.
2. MZ, but `factory_id F2.id`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, factory_id=F2.id)`.

**Then**
1. returns: `names(result) == ["Zenith"]`.

### MCM-S-03 — factory_section_id is handed to the list, and each machine reads its section
- **Rules:** `search_machines` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. link of MA to S1.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, factory_section_id=S1.id)`.

**Then**
1. returns: `names(result) == ["Alpha"]`.
2. returns: `result[0].factory_section_id == S1.id`.
3. returns: `result[0].factory_section_name == "Cutting"`.

### MCM-S-04 — is_running is handed to the list
- **Rules:** `search_machines` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. MA, but `is_running True`.
2. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, is_running=True)`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-05 — search is handed to the list
- **Rules:** `search_machines` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. MA.
2. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, search="lph")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-06 — has_model_number is handed to the list
- **Rules:** `search_machines` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. MA, but `model_number "L-200"`.
2. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, has_model_number=True)`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-07 — has_manufacturer is handed to the list
- **Rules:** `search_machines` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. MA, but `manufacturer "Haas"`.
2. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, has_manufacturer=False)`.

**Then**
1. returns: `names(result) == ["Zenith"]`.

### MCM-S-08 — sort_by created_at is handed to the list
- **Rules:** `search_machines` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. MZ, but `created_at T0`.
2. MA, but `created_at T1`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, sort_by="created_at")`.

**Then**
1. returns: `names(result) == ["Zenith", "Alpha"]`.

### MCM-S-09 — sort_dir desc is handed to the list
- **Rules:** `search_machines` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. MC.
2. MA.
3. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, sort_dir="desc")`.

**Then**
1. returns: `names(result) == ["Zenith", "Cobalt", "Alpha"]`.

### MCM-S-10 — skip and limit are handed to the list
- **Rules:** `search_machines` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. MC.
2. MA.
3. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `names(result) == ["Cobalt"]`.

### MCM-S-11 — the default limit on the list path is 100
- **Rules:** `search_machines` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(101, "P").

**When**
- `result = M.search_machines(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### MCM-S-12 — latest_event_type is handed to the list
- **Rules:** `search_machines` R1 [BUG-886]
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the query cannot be built)

**Given**
1. MA.
2. MZ.
3. status row of MA at T1, `"IDLE"`.
4. status row of MZ at T1, `"RUNNING"`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, latest_event_type="IDLE")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-13 — search text is literal through the list
- **Rules:** `search_machines` R1 [BUG-888]
- **Kind:** bug
- **Expect:** xfail BUG-888
- **Fails today on:** Then 1 (`%` acts as a wildcard and matches every machine)

**Given**
1. MA, but `model_number "50%"`.
2. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, search="%")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-14 — search text is trimmed through the list
- **Rules:** `search_machines` R1 [BUG-892]
- **Kind:** bug
- **Expect:** xfail BUG-892
- **Fails today on:** Then 1 (the text is used untrimmed and matches nothing)

**Given**
1. MA.
2. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, search=" alpha ")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-15 — a negative limit fails in the database on the list path
- **Rules:** `search_machines` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. MA.

**When**
- `M.search_machines(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.

### MCM-S-16 — a negative skip fails in the database on the list path
- **Rules:** `search_machines` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. MA.

**When**
- `M.search_machines(db, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.

### MCM-S-17 — another workspace's machines are never returned on the list path
- **Rules:** `search_machines` R3, R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MA.
2. M9.

**When**
- `result = M.search_machines(db, workspace_id=W1.id)`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-18 — soft-deleted machines are never returned on the list path
- **Rules:** `search_machines` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MA.
2. MX.

**When**
- `result = M.search_machines(db, workspace_id=W1.id)`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-19 — a machine of a soft-deleted factory is hidden on the list path
- **Rules:** `search_machines` R3 [BUG-890]
- **Kind:** bug
- **Expect:** xfail BUG-890
- **Fails today on:** Then 1 (the factory row is never looked at: "Kiln" is listed)

**Given**
1. MA.
2. MF.

**When**
- `result = M.search_machines(db, workspace_id=W1.id)`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-20 — a machine of a live but inactive factory is listed on the list path
- **Rules:** `search_machines` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MI.

**When**
- `result = M.search_machines(db, workspace_id=W1.id)`.

**Then**
1. returns: `names(result) == ["Alpha", "Mixer"]`.

### MCM-S-21 — an unknown workspace gives an empty list on the list path
- **Rules:** `search_machines` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.

**When**
- `result = M.search_machines(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### MCM-S-22 — a workspace without machines gives an empty list on the list path
- **Rules:** `search_machines` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.

**When**
- `result = M.search_machines(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### MCM-S-23 — is_active is not consulted on the list path
- **Rules:** `search_machines` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA, but `is_active False`.
2. MZ, but `is_running True`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id)`.

**Then**
1. returns: `names(result) == ["Alpha", "Zenith"]`.

### MCM-S-24 — another workspace's machines are never returned on the maintenance path
- **Rules:** `search_machines` R3, R4, R14
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MA.
2. M9.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="bogus")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-25 — soft-deleted machines are never returned on the maintenance path
- **Rules:** `search_machines` R3, R14
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MA.
2. MX.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="bogus")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-26 — a machine of a soft-deleted factory is hidden on the maintenance path
- **Rules:** `search_machines` R3 [BUG-890]
- **Kind:** bug
- **Expect:** xfail BUG-890
- **Fails today on:** Then 1 (the factory row is never looked at: "Kiln" is listed)

**Given**
1. MA.
2. MF.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="bogus")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-27 — a machine of a live but inactive factory is listed on the maintenance path
- **Rules:** `search_machines` R3, R14
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MI.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="bogus")`.

**Then**
1. returns: `names(result) == ["Alpha", "Mixer"]`.

### MCM-S-28 — an unknown workspace gives an empty list on the maintenance path
- **Rules:** `search_machines` R4, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.

**When**
- `result = M.search_machines(db, workspace_id=MISSING, maintenance_window="bogus")`.

**Then**
1. returns: `result == []`.

### MCM-S-29 — a workspace without machines gives an empty list on the maintenance path
- **Rules:** `search_machines` R4, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.

**When**
- `result = M.search_machines(db, workspace_id=W2.id, maintenance_window="bogus")`.

**Then**
1. returns: `result == []`.

### MCM-S-30 — is_active is not consulted on the maintenance path
- **Rules:** `search_machines` R4, R14
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA, but `is_active False`.
2. MZ, but `is_running True`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="bogus")`.

**Then**
1. returns: `names(result) == ["Alpha", "Zenith"]`.

### MCM-S-31 — a machine with a left-over link to a deleted section stays listed without a section filter
- **Rules:** `search_machines` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MA.
2. link of MA to SX.

**When**
- `result = M.search_machines(db, workspace_id=W1.id)`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-32 — the id of a soft-deleted section finds nothing
- **Rules:** `search_machines` R3 [BUG-889]
- **Kind:** bug
- **Expect:** xfail BUG-889
- **Fails today on:** Then 1 (the section row is never looked at: "Alpha" is returned)

**Given**
1. MA.
2. link of MA to SX.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, factory_section_id=SX.id)`.

**Then**
1. returns: `result == []`.

### MCM-S-33 — window "all" with the maintenance sort filters nothing
- **Rules:** `search_machines` R5, R16
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MZ, `status "DRAFT"`, `planned_date D(3)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, sort_by="maintenance_date")`.

**Then**
1. returns: `names(result) == ["Zenith", "Alpha"]`.

### MCM-S-34 — filters are applied before the window
- **Rules:** `search_machines` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. MA.
2. MZ, but `factory_id F2.id`.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(3)`.
4. O2 = order of MZ, `status "DRAFT"`, `planned_date D(3)`, `factory_id F2.id`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, factory_id=F2.id, maintenance_window="next_7_days")`.

**Then**
1. returns: `names(result) == ["Zenith"]`.

### MCM-S-35 — every list filter holds on the maintenance path, each wrong machine failing exactly one
- **Rules:** `search_machines` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA, but `is_running True`, `model_number "L-200"`, `manufacturer "Haas"`.
2. MB, but `name "Basalt"`, `factory_id F2.id`, `is_running True`, `model_number "L-200"`, `manufacturer "Haas"` (wrong factory).
3. MC, but `model_number "L-200"`, `manufacturer "Haas"` (not running).
4. MZ, but `name "Zara"`, `is_running True`, `manufacturer "Haas"` (no model number).
5. MQ, but `is_running True`, `model_number "L-200"` (no manufacturer).
6. MK, but `is_running True`, `model_number "L-200"`, `manufacturer "Bosch"` (no "a" in name, model number or manufacturer).
7. machine, `name "Salsa"`, `is_running True`, `model_number "L-200"`, `manufacturer "Haas"` (no section).
8. link of MA to S1.
9. link of MB to S1.
10. link of MC to S1.
11. link of MZ to S1.
12. link of MQ to S1.
13. link of MK to S1.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, factory_id=F1.id, factory_section_id=S1.id, is_running=True, search="a", has_model_number=True, has_manufacturer=True, maintenance_window="bogus")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-36 — the list order by name is kept on the maintenance path
- **Rules:** `search_machines` R6, R14
- **Kind:** happy
- **Expect:** pass

**Given**
1. MC.
2. MA.
3. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="bogus")`.

**Then**
1. returns: `names(result) == ["Alpha", "Cobalt", "Zenith"]`.

### MCM-S-37 — descending name order is kept on the maintenance path
- **Rules:** `search_machines` R6, R14
- **Kind:** happy
- **Expect:** pass

**Given**
1. MC.
2. MA.
3. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="bogus", sort_dir="desc")`.

**Then**
1. returns: `names(result) == ["Zenith", "Cobalt", "Alpha"]`.

### MCM-S-38 — created_at order is kept on the maintenance path
- **Rules:** `search_machines` R6, R14
- **Kind:** happy
- **Expect:** pass

**Given**
1. MZ, but `created_at T0`.
2. MA, but `created_at T1`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="bogus", sort_by="created_at")`.

**Then**
1. returns: `names(result) == ["Zenith", "Alpha"]`.

### MCM-S-39 — latest_event_type works on the maintenance path
- **Rules:** `search_machines` R6 [BUG-886], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-886
- **Fails today on:** Then 1 (the call raises AttributeError: the query cannot be built)

**Given**
1. MA.
2. MZ.
3. status row of MA at T1, `"IDLE"`.
4. status row of MZ at T1, `"RUNNING"`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, latest_event_type="IDLE", maintenance_window="bogus")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-40 — the filter finds a machine past the first 10 000
- **Rules:** `search_machines` R7 [BUG-958]
- **Kind:** bug
- **Expect:** xfail BUG-958
- **Fails today on:** Then 1 (only the first 10 000 by name are looked at)

**Given**
1. bulk(10001, "B").
2. O1 = order of the machine named "B10000", `status "DRAFT"`, `planned_date D(1)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="next_7_days")`.

**Then**
1. returns: `names(result) == ["B10000"]`.

### MCM-S-41 — the maintenance sort sees a machine past the first 10 000
- **Rules:** `search_machines` R7 [BUG-958]
- **Kind:** bug
- **Expect:** xfail BUG-958
- **Fails today on:** Then 1 (only the first 10 000 by name are looked at)

**Given**
1. bulk(10001, "B").
2. O1 = order of the machine named "B10000", `status "DRAFT"`, `planned_date D(1)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, sort_by="maintenance_date", limit=1)`.

**Then**
1. returns: `names(result) == ["B10000"]`.

### MCM-S-42 — the machine at place 10 000 is found
- **Rules:** `search_machines` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(10000, "B").
2. O1 = order of the machine named "B09999", `status "DRAFT"`, `planned_date D(1)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="next_7_days")`.

**Then**
1. returns: `names(result) == ["B09999"]`.

### MCM-S-43 — a completed order gives no work date
- **Rules:** `search_machines` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "COMPLETED"`, `planned_date D(3)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="next_7_days")`.

**Then**
1. returns: `names(result) == []`.

### MCM-S-44 — a voided order gives no work date
- **Rules:** `search_machines` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "VOIDED"`, `planned_date D(3)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="next_7_days")`.

**Then**
1. returns: `names(result) == []`.

### MCM-S-45 — a soft-deleted order gives no work date
- **Rules:** `search_machines` R8
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(3)`, `is_deleted True`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="next_7_days")`.

**Then**
1. returns: `names(result) == []`.

### MCM-S-46 — an order without a date gives no work date
- **Rules:** `search_machines` R8, R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="none_scheduled")`.

**Then**
1. returns: `names(result) == ["Alpha", "Zenith"]`.

### MCM-S-47 — another workspace's order gives no work date
- **Rules:** `search_machines` R8
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(3)`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="next_7_days")`.

**Then**
1. returns: `names(result) == []`.

### MCM-S-48 — work at today + 365 counts as scheduled
- **Rules:** `search_machines` R9, R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(365)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="none_scheduled")`.

**Then**
1. returns: `names(result) == ["Zenith"]`.

### MCM-S-49 — work at today + 366 counts as scheduled
- **Rules:** `search_machines` R9 [BUG-973], R13
- **Kind:** bug
- **Expect:** xfail BUG-973
- **Fails today on:** Then 1 (dates past today + 365 are not read, so "Alpha" is listed)

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(366)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="none_scheduled")`.

**Then**
1. returns: `names(result) == ["Zenith"]`.

### MCM-S-50 — work at today + 800 counts as scheduled
- **Rules:** `search_machines` R9 [BUG-973], R13
- **Kind:** bug
- **Expect:** xfail BUG-973
- **Fails today on:** Then 1 (dates past today + 365 are not read, so "Alpha" is listed)

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(800)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="none_scheduled")`.

**Then**
1. returns: `names(result) == ["Zenith"]`.

### MCM-S-51 — in-progress work at today - 3650 is overdue
- **Rules:** `search_machines` R9, R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "IN_PROGRESS"`, `planned_date D(-3650)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="overdue")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-52 — in-progress work at today - 3651 is overdue
- **Rules:** `search_machines` R9 [BUG-973], R10
- **Kind:** bug
- **Expect:** xfail BUG-973
- **Fails today on:** Then 1 (dates older than today - 3650 are not read)

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "IN_PROGRESS"`, `planned_date D(-3651)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="overdue")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-53 — the maintenance sort uses a date at today + 365
- **Rules:** `search_machines` R9, R16
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MZ, `status "DRAFT"`, `planned_date D(365)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, sort_by="maintenance_date")`.

**Then**
1. returns: `names(result) == ["Zenith", "Alpha"]`.

### MCM-S-54 — the maintenance sort uses a date at today + 366
- **Rules:** `search_machines` R9 [BUG-973], R16
- **Kind:** bug
- **Expect:** xfail BUG-973
- **Fails today on:** Then 1 (the date is not read, so "Zenith" has no date and comes last)

**Given**
1. MA.
2. MZ.
3. O1 = order of MZ, `status "DRAFT"`, `planned_date D(366)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, sort_by="maintenance_date")`.

**Then**
1. returns: `names(result) == ["Zenith", "Alpha"]`.

### MCM-S-55 — an IN_PROGRESS order dated yesterday is overdue
- **Rules:** `search_machines` R10, R15
- **Kind:** happy
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "IN_PROGRESS"`, `planned_date D(-1)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="overdue")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-56 — a DRAFT dated yesterday is not overdue
- **Rules:** `search_machines` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(-1)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="overdue")`.

**Then**
1. returns: `names(result) == []`.

### MCM-S-57 — an IN_PROGRESS order dated today is not overdue
- **Rules:** `search_machines` R10, R15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "IN_PROGRESS"`, `planned_date D(0)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="overdue")`.

**Then**
1. returns: `names(result) == []`.

### MCM-S-58 — an IN_PROGRESS order dated tomorrow is not overdue
- **Rules:** `search_machines` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "IN_PROGRESS"`, `planned_date D(1)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="overdue")`.

**Then**
1. returns: `names(result) == []`.

### MCM-S-59 — work dated today is in next_7_days
- **Rules:** `search_machines` R11, R15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(0)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="next_7_days")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-60 — work dated today + 7 is in next_7_days
- **Rules:** `search_machines` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(7)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="next_7_days")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-61 — work dated today + 8 is not in next_7_days
- **Rules:** `search_machines` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(8)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="next_7_days")`.

**Then**
1. returns: `names(result) == []`.

### MCM-S-62 — work dated yesterday is not in next_7_days
- **Rules:** `search_machines` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(-1)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="next_7_days")`.

**Then**
1. returns: `names(result) == []`.

### MCM-S-63 — IN_PROGRESS work dated today + 3 is in next_7_days
- **Rules:** `search_machines` R11, R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "IN_PROGRESS"`, `planned_date D(3)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="next_7_days")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-64 — work dated today is in next_30_days
- **Rules:** `search_machines` R12, R15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(0)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="next_30_days")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-65 — work dated today + 30 is in next_30_days
- **Rules:** `search_machines` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(30)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="next_30_days")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-66 — work dated today + 31 is not in next_30_days
- **Rules:** `search_machines` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(31)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="next_30_days")`.

**Then**
1. returns: `names(result) == []`.

### MCM-S-67 — work dated yesterday is not in next_30_days
- **Rules:** `search_machines` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(-1)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="next_30_days")`.

**Then**
1. returns: `names(result) == []`.

### MCM-S-68 — IN_PROGRESS work dated today + 3 is in next_30_days
- **Rules:** `search_machines` R12, R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "IN_PROGRESS"`, `planned_date D(3)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="next_30_days")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-69 — an overdue machine with a date in the window qualifies
- **Rules:** `search_machines` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "IN_PROGRESS"`, `planned_date D(-5)`.
4. O2 = order of MA, `status "DRAFT"`, `planned_date D(3)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="next_7_days")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-70 — a machine with work tomorrow is not without schedule
- **Rules:** `search_machines` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(1)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="none_scheduled")`.

**Then**
1. returns: `names(result) == ["Zenith"]`.

### MCM-S-71 — a machine with work today is not without schedule
- **Rules:** `search_machines` R13, R15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(0)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="none_scheduled")`.

**Then**
1. returns: `names(result) == ["Zenith"]`.

### MCM-S-72 — a machine with only past open work is without schedule
- **Rules:** `search_machines` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(-1)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="none_scheduled")`.

**Then**
1. returns: `names(result) == ["Alpha", "Zenith"]`.

### MCM-S-73 — a machine with past and future work is scheduled
- **Rules:** `search_machines` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "IN_PROGRESS"`, `planned_date D(-5)`.
4. O2 = order of MA, `status "DRAFT"`, `planned_date D(2)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="none_scheduled")`.

**Then**
1. returns: `names(result) == ["Zenith"]`.

### MCM-S-74 — a machine without any order is without schedule
- **Rules:** `search_machines` R13
- **Kind:** happy
- **Expect:** pass

**Given**
1. MA.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="none_scheduled")`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-75 — window "bogus" filters nothing
- **Rules:** `search_machines` R14
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(100)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="bogus")`.

**Then**
1. returns: `names(result) == ["Alpha", "Zenith"]`.

### MCM-S-76 — window "OVERDUE" filters nothing
- **Rules:** `search_machines` R14
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(100)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="OVERDUE")`.

**Then**
1. returns: `names(result) == ["Alpha", "Zenith"]`.

### MCM-S-77 — window "" filters nothing
- **Rules:** `search_machines` R14
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(100)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="")`.

**Then**
1. returns: `names(result) == ["Alpha", "Zenith"]`.

### MCM-S-78 — an unknown window is still paged
- **Rules:** `search_machines` R14, R19
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MC.
2. MA.
3. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="bogus", skip=1, limit=1)`.

**Then**
1. returns: `names(result) == ["Cobalt"]`.

### MCM-S-79 — the maintenance sort puts the earliest date first and machines without one last
- **Rules:** `search_machines` R16
- **Kind:** happy
- **Expect:** pass

**Given**
1. MA.
2. MC.
3. MZ.
4. O1 = order of MZ, `status "DRAFT"`, `planned_date D(2)`.
5. O2 = order of MC, `status "IN_PROGRESS"`, `planned_date D(9)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, sort_by="maintenance_date")`.

**Then**
1. returns: `names(result) == ["Zenith", "Cobalt", "Alpha"]`.

### MCM-S-80 — a machine's earliest future date decides
- **Rules:** `search_machines` R16
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(5)`.
4. O2 = order of MZ, `status "DRAFT"`, `planned_date D(9)`.
5. O3 = order of MZ, `status "DRAFT"`, `planned_date D(2)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, sort_by="maintenance_date")`.

**Then**
1. returns: `names(result) == ["Zenith", "Alpha"]`.

### MCM-S-81 — past dates are ignored by the maintenance sort
- **Rules:** `search_machines` R16
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(5)`.
4. O2 = order of MZ, `status "IN_PROGRESS"`, `planned_date D(-5)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, sort_by="maintenance_date")`.

**Then**
1. returns: `names(result) == ["Alpha", "Zenith"]`.

### MCM-S-82 — a date equal to today counts for the maintenance sort
- **Rules:** `search_machines` R16, R15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(1)`.
4. O2 = order of MZ, `status "DRAFT"`, `planned_date D(0)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, sort_by="maintenance_date")`.

**Then**
1. returns: `names(result) == ["Zenith", "Alpha"]`.

### MCM-S-83 — ties keep name order
- **Rules:** `search_machines` R16
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MZ.
2. MA.
3. O1 = order of MZ, `status "DRAFT"`, `planned_date D(4)`.
4. O2 = order of MA, `status "DRAFT"`, `planned_date D(4)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, sort_by="maintenance_date")`.

**Then**
1. returns: `names(result) == ["Alpha", "Zenith"]`.

### MCM-S-84 — descending puts the latest first and machines without a date still last
- **Rules:** `search_machines` R17
- **Kind:** happy
- **Expect:** pass

**Given**
1. MA.
2. MC.
3. MZ.
4. O1 = order of MZ, `status "DRAFT"`, `planned_date D(2)`.
5. O2 = order of MC, `status "IN_PROGRESS"`, `planned_date D(9)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, sort_by="maintenance_date", sort_dir="desc")`.

**Then**
1. returns: `names(result) == ["Cobalt", "Zenith", "Alpha"]`.

### MCM-S-85 — descending ties keep name order ascending
- **Rules:** `search_machines` R17
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MZ.
2. MA.
3. MC.
4. O1 = order of MZ, `status "DRAFT"`, `planned_date D(4)`.
5. O2 = order of MA, `status "DRAFT"`, `planned_date D(4)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, sort_by="maintenance_date", sort_dir="desc")`.

**Then**
1. returns: `names(result) == ["Alpha", "Zenith", "Cobalt"]`.

### MCM-S-86 — sort_dir "DESC" sorts ascending
- **Rules:** `search_machines` R17
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MC.
3. MZ.
4. O1 = order of MZ, `status "DRAFT"`, `planned_date D(2)`.
5. O2 = order of MC, `status "IN_PROGRESS"`, `planned_date D(9)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, sort_by="maintenance_date", sort_dir="DESC")`.

**Then**
1. returns: `names(result) == ["Zenith", "Cobalt", "Alpha"]`.

### MCM-S-87 — the maintenance sort is combined with a window
- **Rules:** `search_machines` R5, R16
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MC.
3. MZ.
4. O1 = order of MZ, `status "DRAFT"`, `planned_date D(2)`.
5. O2 = order of MC, `status "IN_PROGRESS"`, `planned_date D(9)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, sort_by="maintenance_date", maintenance_window="next_7_days")`.

**Then**
1. returns: `names(result) == ["Zenith"]`.

### MCM-S-88 — a case-only tie on the maintenance sort falls to id
- **Rules:** `search_machines` R18 [BUG-887]
- **Kind:** bug
- **Expect:** xfail BUG-887 (non-strict)
- **Fails today on:** Then 1 (the order comes from collation: on the test database "bolt" first; standing decision 4 calls that no order, so non-strict)

**Given**
1. machine, `name "Bolt"`.
2. machine, `name "bolt"`, `factory_id F2.id`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, sort_by="maintenance_date")`.

**Then**
1. returns: `names(result) == ["Bolt", "bolt"]`.

### MCM-S-89 — skip and limit are applied last on the maintenance path
- **Rules:** `search_machines` R19
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MC.
3. MZ.
4. MB.
5. O1 = order of MA, `status "DRAFT"`, `planned_date D(3)`.
6. O2 = order of MC, `status "DRAFT"`, `planned_date D(3)`.
7. O3 = order of MZ, `status "DRAFT"`, `planned_date D(3)`.
8. O4 = order of MB, `status "DRAFT"`, `planned_date D(3)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="next_7_days", skip=1, limit=2)`.

**Then**
1. returns: `names(result) == ["Beryl", "Cobalt"]`.

### MCM-S-90 — limit 0 gives an empty list on the maintenance path
- **Rules:** `search_machines` R19
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="bogus", limit=0)`.

**Then**
1. returns: `result == []`.

### MCM-S-91 — limit 1 gives one row on the maintenance path
- **Rules:** `search_machines` R19
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="bogus", limit=1)`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-S-92 — skip at the end gives an empty list on the maintenance path
- **Rules:** `search_machines` R19
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="bogus", skip=2)`.

**Then**
1. returns: `result == []`.

### MCM-S-93 — skip one before the end gives the last row
- **Rules:** `search_machines` R19
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="bogus", skip=1)`.

**Then**
1. returns: `names(result) == ["Zenith"]`.

### MCM-S-94 — the default limit on the maintenance path is 100
- **Rules:** `search_machines` R19
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(101, "P").

**When**
- `result = M.search_machines(db, workspace_id=W1.id, maintenance_window="bogus")`.

**Then**
1. returns: `len(result) == 100`.

### MCM-S-95 — include_deleted lists deleted machines and machines of deleted factories with the live ones
- **Rules:** `search_machines` R21
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MA.
2. MX.
3. MF.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `ids(result) == [MA.id, MX.id, MF.id]`.

### MCM-S-96 — include_deleted stays inside the workspace
- **Rules:** `search_machines` R21
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MA.
2. M9.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `ids(result) == [MA.id]`.

### MCM-S-97 — include_deleted applies factory_id
- **Rules:** `search_machines` R21
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MX, but `factory_id F2.id`.
3. MZ, but `factory_id F2.id`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, include_deleted=True, factory_id=F2.id)`.

**Then**
1. returns: `ids(result) == [MX.id, MZ.id]`.

### MCM-S-98 — include_deleted applies factory_section_id
- **Rules:** `search_machines` R21
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.
3. link of MZ to S1.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, include_deleted=True, factory_section_id=S1.id)`.

**Then**
1. returns: `ids(result) == [MZ.id]`.

### MCM-S-99 — include_deleted applies is_running
- **Rules:** `search_machines` R21
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ, but `is_running True`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, include_deleted=True, is_running=True)`.

**Then**
1. returns: `ids(result) == [MZ.id]`.

### MCM-S-100 — include_deleted applies search
- **Rules:** `search_machines` R21
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA.
2. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, include_deleted=True, search="Alpha")`.

**Then**
1. returns: `ids(result) == [MA.id]`.

### MCM-S-101 — include_deleted applies has_model_number
- **Rules:** `search_machines` R21 [BUG-957]
- **Kind:** bug
- **Expect:** xfail BUG-957
- **Fails today on:** Then 1 (the filter is ignored: both machines are returned)

**Given**
1. MA, but `model_number "L-200"`.
2. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, include_deleted=True, has_model_number=True)`.

**Then**
1. returns: `ids(result) == [MA.id]`.

### MCM-S-102 — include_deleted applies has_manufacturer
- **Rules:** `search_machines` R21 [BUG-957]
- **Kind:** bug
- **Expect:** xfail BUG-957
- **Fails today on:** Then 1 (the filter is ignored: both machines are returned)

**Given**
1. MA, but `manufacturer "Haas"`.
2. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, include_deleted=True, has_manufacturer=True)`.

**Then**
1. returns: `ids(result) == [MA.id]`.

### MCM-S-103 — include_deleted applies latest_event_type
- **Rules:** `search_machines` R21 [BUG-957]
- **Kind:** bug
- **Expect:** xfail BUG-957
- **Fails today on:** Then 1 (the filter is ignored: both machines are returned)

**Given**
1. MA.
2. MZ.
3. status row of MA at T1, `"IDLE"`.
4. status row of MZ at T1, `"RUNNING"`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, include_deleted=True, latest_event_type="IDLE")`.

**Then**
1. returns: `ids(result) == [MA.id]`.

### MCM-S-104 — include_deleted applies the maintenance window
- **Rules:** `search_machines` R21 [BUG-957]
- **Kind:** bug
- **Expect:** xfail BUG-957
- **Fails today on:** Then 1 (the window is ignored: both machines are returned)

**Given**
1. MA.
2. MZ.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(3)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, include_deleted=True, maintenance_window="next_7_days")`.

**Then**
1. returns: `ids(result) == [MA.id]`.

### MCM-S-105 — with include_deleted a deleted machine has no work dates in a window
- **Rules:** `search_machines` R21 [BUG-957], R8
- **Kind:** bug
- **Expect:** xfail BUG-957
- **Fails today on:** Then 1 (the window is ignored: both machines are returned)

**Given**
1. MA.
2. MX.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(3)`.
4. O2 = order of MX, `status "DRAFT"`, `planned_date D(3)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, include_deleted=True, maintenance_window="next_7_days")`.

**Then**
1. returns: `ids(result) == [MA.id]`.

### MCM-S-106 — with include_deleted a deleted machine counts as without schedule
- **Rules:** `search_machines` R21 [BUG-957], R8
- **Kind:** bug
- **Expect:** xfail BUG-957
- **Fails today on:** Then 1 (the window is ignored: both machines are returned)

**Given**
1. MA.
2. MX.
3. O1 = order of MA, `status "DRAFT"`, `planned_date D(3)`.
4. O2 = order of MX, `status "DRAFT"`, `planned_date D(3)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, include_deleted=True, maintenance_window="none_scheduled")`.

**Then**
1. returns: `ids(result) == [MX.id]`.

### MCM-S-107 — include_deleted sorts by name
- **Rules:** `search_machines` R21 [BUG-957]
- **Kind:** bug
- **Expect:** xfail BUG-957 (non-strict)
- **Fails today on:** Then 1 (no display order; may pass by physical order)

**Given**
1. MZ.
2. MA.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `names(result) == ["Alpha", "Zenith"]`.

### MCM-S-108 — include_deleted honours sort_dir
- **Rules:** `search_machines` R21 [BUG-957]
- **Kind:** bug
- **Expect:** xfail BUG-957 (non-strict)
- **Fails today on:** Then 1 (`sort_dir` is ignored; may pass by physical order)

**Given**
1. MA.
2. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, include_deleted=True, sort_dir="desc")`.

**Then**
1. returns: `names(result) == ["Zenith", "Alpha"]`.

### MCM-S-109 — include_deleted honours sort_by created_at
- **Rules:** `search_machines` R21 [BUG-957]
- **Kind:** bug
- **Expect:** xfail BUG-957 (non-strict)
- **Fails today on:** Then 1 (`sort_by` is ignored; may pass by physical order)

**Given**
1. MA, but `created_at T1`.
2. MZ, but `created_at T0`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, include_deleted=True, sort_by="created_at")`.

**Then**
1. returns: `names(result) == ["Zenith", "Alpha"]`.

### MCM-S-110 — include_deleted honours the maintenance sort
- **Rules:** `search_machines` R21 [BUG-957]
- **Kind:** bug
- **Expect:** xfail BUG-957 (non-strict)
- **Fails today on:** Then 1 (`sort_by` is ignored; may pass by physical order)

**Given**
1. MA.
2. MZ.
3. O1 = order of MZ, `status "DRAFT"`, `planned_date D(3)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, include_deleted=True, sort_by="maintenance_date")`.

**Then**
1. returns: `names(result) == ["Zenith", "Alpha"]`.

### MCM-S-111 — include_deleted pages after filtering
- **Rules:** `search_machines` R21 [BUG-957]
- **Kind:** bug
- **Expect:** xfail BUG-957 (non-strict)
- **Fails today on:** Then 1 (the page is cut first, in no defined order, so this may pass by physical order)

**Given**
1. MA.
2. MB.
3. MZ, but `factory_id F2.id`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, include_deleted=True, factory_id=F2.id, limit=2)`.

**Then**
1. returns: `names(result) == ["Zenith"]`.

### MCM-S-112 — the include_deleted query orders by name in SQL
- **Rules:** `search_machines` R21 [BUG-957]
- **Kind:** bug
- **Expect:** xfail BUG-957
- **Fails today on:** Then 2 (no name order is emitted)

**Given**
1. MA.
2. MX.
3. sql_log started (Conventions).

**When**
- `result = M.search_machines(db, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `ids(result) == [MA.id, MX.id]`.
2. sql: a recorded statement that selects from `machines` has `ORDER BY` followed by a name column: `any(re.search(r"FROM machines\b.*ORDER BY .*\bname\b", s, re.S) for s in sql_log)`.

### MCM-S-113 — with include_deleted a live machine of a soft-deleted factory keeps its work dates
- **Rules:** `search_machines` R21 [BUG-957], R8
- **Kind:** bug
- **Expect:** xfail BUG-957
- **Fails today on:** Then 1 (the window is ignored: both machines are returned)

**Given**
1. MZ.
2. MF.
3. O1 = order of MF, `status "DRAFT"`, `planned_date D(3)`, `factory_id FD.id`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, include_deleted=True, maintenance_window="next_7_days")`.

**Then**
1. returns: `ids(result) == [MF.id]`.

### MCM-S-114 — include_deleted applies search to the model number
- **Rules:** `search_machines` R21
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA, but `model_number "L-200"`.
2. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, include_deleted=True, search="L-2")`.

**Then**
1. returns: `ids(result) == [MA.id]`.

### MCM-S-115 — include_deleted applies search to the manufacturer
- **Rules:** `search_machines` R21
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA, but `manufacturer "Haas"`.
2. MZ.

**When**
- `result = M.search_machines(db, workspace_id=W1.id, include_deleted=True, search="haa")`.

**Then**
1. returns: `ids(result) == [MA.id]`.

## `MachineManager.delete_machine`

### MCM-D-01 — a live machine not in use is soft-deleted with stamp and the same instance returned
- **Rules:** `delete_machine` R5, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`, `is_active is False`.
3. re-read M1: `deleted_at == NOW`, `deleted_by == U2.id`.
4. re-read M1: `updated_at is not None`.

### MCM-D-02 — no other column is changed by the delete
- **Rules:** `delete_machine` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1, but `model_number "L-200"`, `note "Bay 3"`, `updated_by U1.id`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `name == "Lathe"`, `factory_id == F1.id`, `workspace_id == W1.id`.
3. re-read M1: `model_number == "L-200"`, `note == "Bay 3"`.
4. re-read M1: `created_by == U1.id`, `updated_by == U1.id`.

### MCM-D-03 — a section link is kept and still read
- **Rules:** `delete_machine` R6, R4b
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1.
2. L1 = link of M1 to S1.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. unchanged: unchanged(L1).
3. re-read M1: `factory_section_id == S1.id`.

### MCM-D-04 — a running machine stays running and is not in use for that
- **Rules:** `delete_machine` R6, R4b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1, but `is_running True`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. re-read M1: `is_running is True`.

### MCM-D-05 — one deactivated event is written
- **Rules:** `delete_machine` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. event: events_of(M1) has exactly 1 row.
3. event: that row has `event_type == "deactivated"`, `description == "Machine deactivated: Lathe"`.
4. event: that row has `performed_by == U2.id`, `metadata_json is None`.
5. event: that row has `workspace_id == W1.id`.

### MCM-D-06 — an id that no machine has is refused
- **Rules:** `delete_machine` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.

**When**
- `M.delete_machine(db, machine_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine with ID 999999999 not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).

### MCM-D-07 — a machine of another workspace is refused and not changed
- **Rules:** `delete_machine` R1, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M9.

**When**
- `M.delete_machine(db, machine_id=M9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M9).

### MCM-D-08 — an already deleted machine is refused, the stamp stays and no event is written
- **Rules:** `delete_machine` R2, Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MX.

**When**
- `M.delete_machine(db, machine_id=MX.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Machine is already deleted"`.
4. nothing written: nothing written.
5. unchanged: unchanged(MX).
6. re-read MX: `deleted_at == T0`, `deleted_by == U1.id`.

### MCM-D-09 — already deleted wins over in use
- **Rules:** `delete_machine` R2, R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MX.
2. ST1 = stock of MX, item I1, `qty 5`.

**When**
- `M.delete_machine(db, machine_id=MX.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Machine is already deleted"`.
4. nothing written: nothing written.
5. unchanged: unchanged(MX).

### MCM-D-10 — a live machine of a soft-deleted factory is refused
- **Rules:** `delete_machine` R3 [BUG-965], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-965
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. MF.

**When**
- `M.delete_machine(db, machine_id=MF.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot delete a machine of a deleted factory"`.
4. nothing written: nothing written.
5. unchanged: unchanged(MF).

### MCM-D-11 — the deleted-factory refusal wins over in use
- **Rules:** `delete_machine` R3 [BUG-965], R4
- **Kind:** bug
- **Expect:** xfail BUG-965
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. MF.
2. ST1 = stock of MF, item I1, `qty 5`.

**When**
- `M.delete_machine(db, machine_id=MF.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot delete a machine of a deleted factory"`.
4. nothing written: nothing written.
5. unchanged: unchanged(MF).

### MCM-D-12 — a machine of a live but inactive factory is deleted
- **Rules:** `delete_machine` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI.

**When**
- `result = M.delete_machine(db, machine_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is MI` (the very object that was read).
2. re-read MI: `is_deleted is True`.

### MCM-D-13 — stock on the machine blocks the delete
- **Rules:** `delete_machine` R4 (a) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. ST1 = stock of M1, item I1, `qty 5`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "machine_stock", "id": ST1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(ST1).

### MCM-D-14 — negative stock blocks the delete
- **Rules:** `delete_machine` R4 (a) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. ST1 = stock of M1, item I1, `qty -1`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "machine_stock", "id": ST1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.

### MCM-D-15 — stock 0 does not block, whatever req_qty and defective_qty hold
- **Rules:** `delete_machine` R4 (a)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. ST1 = stock of M1, item I1, `qty 0`, `req_qty 4`, `defective_qty 2`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(ST1).

### MCM-D-16 — stock of another machine does not block
- **Rules:** `delete_machine` R4 (a)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M2.
3. ST1 = stock of M2, item I1, `qty 5`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(ST1).
4. unchanged: unchanged(M2).

### MCM-D-17 — a purchase order to the machine blocks the delete
- **Rules:** `delete_machine` R4 (b) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. PO1 = purchase order, `destination_id M1.id`, `current_status_id STD.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "purchase_order", "id": PO1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(PO1).

### MCM-D-18 — a purchase order at stage Complete does not block
- **Rules:** `delete_machine` R4 (b)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. PO1 = purchase order, `destination_id M1.id`, `current_status_id STC.id`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(PO1).

### MCM-D-19 — a voided purchase order does not block
- **Rules:** `delete_machine` R4 (b)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. PO1 = purchase order, `destination_id M1.id`, `current_status_id STD.id`, `voided True`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(PO1).

### MCM-D-20 — a purchase order to a store with the same id does not block
- **Rules:** `delete_machine` R4 (b)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. PO1 = purchase order, `destination_type "storage"`, `destination_id M1.id`, `current_status_id STD.id`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(PO1).

### MCM-D-21 — an open DRAFT work order on the machine blocks the delete
- **Rules:** `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(O1).

### MCM-D-22 — an IN_PROGRESS work order on the machine blocks the delete
- **Rules:** `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. O1 = order of M1, `status "IN_PROGRESS"`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.

### MCM-D-23 — an open order of another machine with a live line sourcing from this one blocks
- **Rules:** `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. M2.
3. O1 = order of M2, `status "DRAFT"`.
4. L1 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.

### MCM-D-24 — a completed work order on the machine does not block
- **Rules:** `delete_machine` R4 (c)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "COMPLETED"`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(O1).

### MCM-D-25 — a voided work order on the machine does not block
- **Rules:** `delete_machine` R4 (c)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "VOIDED"`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(O1).

### MCM-D-26 — a soft-deleted work order on the machine does not block
- **Rules:** `delete_machine` R4 (c)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`, `is_deleted True`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(O1).

### MCM-D-27 — a completed order with a line sourcing from the machine does not block
- **Rules:** `delete_machine` R4 (c)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M2.
3. O1 = order of M2, `status "COMPLETED"`.
4. L1 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(O1).
4. unchanged: unchanged(L1).

### MCM-D-28 — a soft-deleted line sourcing from the machine does not block
- **Rules:** `delete_machine` R4 (c)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M2.
3. O1 = order of M2, `status "DRAFT"`.
4. L1 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`, `is_deleted True`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(O1).
4. unchanged: unchanged(L1).

### MCM-D-29 — a line sourcing from a store with the same id does not block
- **Rules:** `delete_machine` R4 (c)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M2.
3. O1 = order of M2, `status "DRAFT"`.
4. L1 = line of O1, `source_location_type "storage"`, `source_location_id M1.id`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(O1).
4. unchanged: unchanged(L1).

### MCM-D-30 — a transfer order from the machine blocks the delete
- **Rules:** `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. TO1 = transfer order, `source_location_type "machine"`, `source_location_id M1.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(TO1).

### MCM-D-31 — a transfer order to the machine blocks the delete
- **Rules:** `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. TO1 = transfer order, `destination_location_type "machine"`, `destination_location_id M1.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.

### MCM-D-32 — a completed transfer order does not block
- **Rules:** `delete_machine` R4 (d)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. TO1 = transfer order, `source_location_type "machine"`, `source_location_id M1.id`, `completed_at T0`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(TO1).

### MCM-D-33 — a transfer with a store of the same id does not block
- **Rules:** `delete_machine` R4 (d)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. TO1 = transfer order, `source_location_id M1.id`, `destination_location_id M1.id`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(TO1).

### MCM-D-34 — an order that qualifies twice is listed once: work order on the machine and sourcing from it
- **Rules:** `delete_machine` R4a [BUG-968]
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.
3. L1 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`.
4. L2 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.

### MCM-D-35 — a transfer from and to the machine is listed once
- **Rules:** `delete_machine` R4a [BUG-968]
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. TO1 = transfer order, `source_location_type "machine"`, `source_location_id M1.id`, `destination_location_type "machine"`, `destination_location_id M1.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.

### MCM-D-36 — two stock rows are two entries, by id
- **Rules:** `delete_machine` R4a [BUG-968]
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. ST1 = stock of M1, item I1, `qty 5`.
3. ST2 = stock of M1, item I2, `qty 1`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "machine_stock", "id": ST1.id}, {"type": "machine_stock", "id": ST2.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.

### MCM-D-37 — two work orders are sorted by id ascending
- **Rules:** `delete_machine` R4a [BUG-968]
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.
3. O2 = order of M1, `status "IN_PROGRESS"`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}, {"type": "work_order", "id": O2.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.

### MCM-D-38 — the four types come in the fixed order, however they were built
- **Rules:** `delete_machine` R4a [BUG-968]
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. TO1 = transfer order, `source_location_type "machine"`, `source_location_id M1.id`.
3. O1 = order of M1, `status "DRAFT"`.
4. PO1 = purchase order, `destination_id M1.id`, `current_status_id STD.id`.
5. ST1 = stock of M1, item I1, `qty 5`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "machine_stock", "id": ST1.id}, {"type": "purchase_order", "id": PO1.id}, {"type": "work_order", "id": O1.id}, {"type": "transfer_order", "id": TO1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.

### MCM-D-39 — the id of a sourcing line is the order's, never the line's
- **Rules:** `delete_machine` R4a [BUG-968]
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. M2.
3. O1 = order of M2, `status "IN_PROGRESS"`.
4. L0 = line of O1, `source_location_type "storage"`, `source_location_id F1.id`.
5. L1 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.

### MCM-D-40 — only blocking rows are listed
- **Rules:** `delete_machine` R4a [BUG-968]
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. ST0 = stock of M1, item I1, `qty 0`.
3. ST1 = stock of M1, item I2, `qty 5`.
4. PO1 = purchase order, `destination_id M1.id`, `current_status_id STC.id`.
5. O1 = order of M1, `status "COMPLETED"`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "machine_stock", "id": ST1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(ST0).
8. unchanged: unchanged(PO1).
9. unchanged: unchanged(O1).

### MCM-D-41 — a machine in use deleted by an unknown user gets the refusal, not a database error
- **Rules:** `delete_machine` R4 [BUG-968], R9
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (the call raises IntegrityError: nothing is looked at, the unknown user fails on flush)

**Given**
1. M1.
2. ST1 = stock of M1, item I1, `qty 5`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "machine_stock", "id": ST1.id}]`.
5. session: `M1 not in db.dirty`.
6. session: `db.flush()` runs and raises nothing.
7. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
8. count: `machine_activity_events` has exactly 0 rows.

### MCM-D-42 — a maintenance log does not block
- **Rules:** `delete_machine` R4b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. ML1 = `machine_maintenance_logs` row built with `MachineMaintenanceLog` (`app.models.machine_maintenance_log`): `workspace_id W1.id`, `machine_id M1.id`, `maintenance_type list(MaintenanceTypeEnum)[0]`, `maintenance_date D(0)`, `summary "Belt changed"` (enum members, its import and the date type: Spec gap 11).

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(ML1).

### MCM-D-43 — activity events do not block
- **Rules:** `delete_machine` R4b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. status row of M1 at T1, `"RUNNING"`, named EV1.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(EV1).

### MCM-D-44 — a machine item ledger row does not block
- **Rules:** `delete_machine` R4b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. LG = `machine_item_ledger` row built with `MachineItemLedger` (`app.models.machine_item_ledger`): `workspace_id W1.id`, `machine_id M1.id`, `item_id I1.id`, `transaction_type "manual_add"`, `quantity 5`, `unit_cost 1`, `total_cost 5`, `qty_before 0`, `qty_after 5`, `source_type "manual"`, `performed_by U1.id`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(LG).

### MCM-D-45 — a work order template naming the machine does not block
- **Rules:** `delete_machine` R4b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. TP1 = `work_order_templates` row built with `WorkOrderTemplate` (`app.models.work_order_template`): `workspace_id W1.id`, `template_name "Monthly"`, `work_order_type_id WT1.id`, `default_machine_id M1.id`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(TP1).

### MCM-D-46 — a production line naming the machine does not block
- **Rules:** `delete_machine` R4b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. PL1 = `production_lines` row built with `ProductionLine` (`app.models.production_line`): `workspace_id W1.id`, `factory_id F1.id`, `name "Line One"`, `machine_id M1.id`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(PL1).

### MCM-D-47 — a formula stage naming the machine does not block
- **Rules:** `delete_machine` R4b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. PF1 = `production_formulas` row built with `ProductionFormula` (`app.models.production_formula`): `workspace_id W1.id`, `formula_code "F-1"`, `name "Mix"`.
3. FS1 = `production_formula_stages` row built with `ProductionFormulaStage` (`app.models.production_formula_stage`): `workspace_id W1.id`, `formula_id PF1.id`, `stage_order 1`, `name "Press"`, `machine_id M1.id`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(FS1).

### MCM-D-48 — after the delete the machine is not listed
- **Rules:** `delete_machine` R8
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MA.
2. M1.
3. a step, `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**When**
- `result = M.search_machines(db, workspace_id=W1.id)`.

**Then**
1. returns: `names(result) == ["Alpha"]`.

### MCM-D-49 — after the delete the name can be reused
- **Rules:** `delete_machine` R8; `create_machine` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1.
2. a step, `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**When**
- `result = M.create_machine(db, machine_data=MachineCreate(name="Lathe", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id != M1.id`.
2. re-read the returned row: `name == "Lathe"`, `is_deleted is False`.

### MCM-D-50 — after the delete an update answers 400
- **Rules:** `delete_machine` R8
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1.
2. a step, `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**When**
- `M.update_machine(db, machine_id=M1.id, machine_data=MachineUpdate(note="Bay 4"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted machine"`.
4. re-read M1: `note is None`.

### MCM-D-51 — after the delete a second delete answers 400
- **Rules:** `delete_machine` R8
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1.
2. a step, `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Machine is already deleted"`.
4. re-read M1: `deleted_by == U1.id`.

### MCM-D-52 — after the delete get_machine answers 404
- **Rules:** `delete_machine` R8; `get_machine` R3 [BUG-955]
- **Kind:** bug
- **Expect:** xfail BUG-955
- **Fails today on:** Then 1 (no error is raised: the deleted machine is returned)

**Given**
1. M1.
2. a step, `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**When**
- `M.get_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M1.id} not found"`.

### MCM-D-53 — an unknown user fails on flush and the machine stays live
- **Rules:** `delete_machine` R9, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"machines_deleted_by_fkey" in str(exc.value.orig)`.
4. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
5. count: `machine_activity_events` has exactly 0 rows.

### MCM-D-54 — the delete is flushed but not committed: a rollback makes the machine live and removes the event
- **Rules:** `delete_machine` R10, Returns
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. event: events_of(M1) has exactly 1 row.
4. re-read M1 after the savepoint rollback: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
5. count after the savepoint rollback: `machine_activity_events` has exactly 0 rows.
6. mock called: the `db.commit` spy was never called.

### MCM-D-55 — stock with another workspace's id on the machine is shown only as the generic entry
- **Rules:** `delete_machine` R4 (a) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. I9.
3. ST1 = stock of M1, item I9, `qty 5`, but `workspace_id W2.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(ST1).

### MCM-D-56 — a purchase order of another workspace to the machine is shown only as the generic entry
- **Rules:** `delete_machine` R4 (b) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. ST9.
3. PO1 = purchase order, `destination_id M1.id`, `current_status_id ST9.id`, but `workspace_id W2.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(PO1).

### MCM-D-57 — a transfer order of another workspace from the machine is shown only as the generic entry
- **Rules:** `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. ST9.
3. TO1 = transfer order, `source_location_type "machine"`, `source_location_id M1.id`, but `workspace_id W2.id`, `destination_location_id F9.id`, `current_status_id ST9.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(TO1).

### MCM-D-58 — a work order of another workspace with this machine id is shown only as the generic entry
- **Rules:** `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(O1).

### MCM-D-59 — a work order of another workspace with a line sourcing from the machine is shown only as the generic entry
- **Rules:** `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. M9.
3. I9.
4. O1 = order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
5. L1 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`, but `workspace_id W2.id`, `item_id I9.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(O1).
8. unchanged: unchanged(L1).

### MCM-D-60 — blockers of both workspaces: own rows listed by type then id, the rest one generic entry, last
- **Rules:** `delete_machine` R4 (a) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. I9.
3. ST1 = stock of M1, item I9, `qty 5`, but `workspace_id W2.id`.
4. ST2 = stock of M1, item I1, `qty 1`.
5. O1 = order of M1, `status "DRAFT"`.
6. ST9.
7. TO1 = transfer order, `source_location_type "machine"`, `source_location_id M1.id`, but `workspace_id W2.id`, `destination_location_id F9.id`, `current_status_id ST9.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "machine_stock", "id": ST2.id}, {"type": "work_order", "id": O1.id}, {"type": "other_workspace"}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(ST1).
8. unchanged: unchanged(ST2).
9. unchanged: unchanged(O1).
10. unchanged: unchanged(TO1).

### MCM-D-61 — a stock row of another workspace with an item of this one is shown only as the generic entry
- **Rules:** `delete_machine` R4 (a) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. ST1 = stock of M1, item I1, `qty 5`, but `workspace_id W2.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(ST1).

### MCM-D-62 — a line of another workspace on an open order of this one is shown only as the generic entry
- **Rules:** `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. M2.
3. O1 = order of M2, `status "DRAFT"`.
4. L1 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`, but `workspace_id W2.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(O1).
8. unchanged: unchanged(L1).

### MCM-D-63 — a line of this workspace on an open order of another one is shown only as the generic entry
- **Rules:** `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. M9.
3. O1 = order of M9, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
4. L1 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(O1).
8. unchanged: unchanged(L1).

### MCM-D-64 — a purchase order of this workspace on a stage of another one, not Complete, blocks
- **Rules:** `delete_machine` R4 (b) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. ST9.
3. PO1 = purchase order, `destination_id M1.id`, `current_status_id ST9.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "purchase_order", "id": PO1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(PO1).

### MCM-D-65 — a purchase order of this workspace on a stage Complete of another one does not block
- **Rules:** `delete_machine` R4 (b)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1.
2. STC9.
3. PO1 = purchase order, `destination_id M1.id`, `current_status_id STC9.id`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(PO1).

### MCM-D-66 — a purchase order of another workspace at its own stage Complete does not block
- **Rules:** `delete_machine` R4 (b)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1.
2. STC9.
3. PO1 = purchase order, `destination_id M1.id`, `current_status_id STC9.id`, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(PO1).

### MCM-D-67 — a machine of another workspace that is in use gets not found, with no blocker ids
- **Rules:** `delete_machine` R1, R4, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M9.
2. I9.
3. ST1 = stock of M9, item I9, `qty 5`.
4. O1 = order of M9, `status "IN_PROGRESS"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.

**When**
- `M.delete_machine(db, machine_id=M9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M9).
6. unchanged: unchanged(ST1).
7. unchanged: unchanged(O1).

### MCM-D-68 — a machine of a live but inactive factory is still refused when in use
- **Rules:** `delete_machine` R3, R4 (a) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. MI.
2. ST1 = stock of MI, item I1, `qty 5`.

**When**
- `M.delete_machine(db, machine_id=MI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "machine_stock", "id": ST1.id}]`.
4. re-read MI: `is_deleted is False`, `is_active is True`, `deleted_by is None`.
5. count: `machine_activity_events` has exactly 0 rows.

### MCM-D-69 — a work order on the machine whose own factory is soft-deleted blocks
- **Rules:** `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`, `factory_id FD.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(O1).

### MCM-D-70 — a transfer whose other end is a soft-deleted factory blocks
- **Rules:** `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. TO1 = transfer order, `source_location_type "machine"`, `source_location_id M1.id`, `destination_location_id FD.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(TO1).

### MCM-D-71 — a transfer whose other end is a soft-deleted machine blocks
- **Rules:** `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. MX.
3. TO1 = transfer order, `source_location_type "machine"`, `source_location_id M1.id`, `destination_location_type "machine"`, `destination_location_id MX.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(TO1).
8. unchanged: unchanged(MX).

### MCM-D-72 — a sourcing line on an open order of a soft-deleted machine blocks
- **Rules:** `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. MX.
3. O1 = order of MX, `status "DRAFT"`.
4. L1 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(O1).
8. unchanged: unchanged(L1).
9. unchanged: unchanged(MX).

### MCM-D-73 — an order on the machine with only a consumed sourcing line blocks through machine_id, listed once
- **Rules:** `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. O1 = order of M1, `status "IN_PROGRESS"`.
3. L1 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`, `consumed_at T0`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(O1).
8. unchanged: unchanged(L1).

### MCM-D-74 — an order of another machine with one consumed and one unconsumed sourcing line blocks, order id once
- **Rules:** `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. M2.
3. O1 = order of M2, `status "IN_PROGRESS"`.
4. L1 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`, `consumed_at T0`.
5. L2 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(O1).
8. unchanged: unchanged(L1).
9. unchanged: unchanged(L2).

### MCM-D-75 — a consumed sourcing line on an open order of another machine does not block
- **Rules:** `delete_machine` R4 (c), R4a, R4b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M2.
3. O1 = order of M2, `status "IN_PROGRESS"`.
4. L1 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`, `consumed_at T0`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(O1).
4. unchanged: unchanged(L1).

### MCM-D-76 — a sourcing line with uses_inventory False on an open order of another machine does not block
- **Rules:** `delete_machine` R4 (c), R4a, R4b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M2.
3. O1 = order of M2, `status "IN_PROGRESS"`.
4. L1 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`, `uses_inventory False`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(O1).
4. unchanged: unchanged(L1).

### MCM-D-77 — a sourcing line on an open order with no machine blocks
- **Rules:** `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`, but `machine_id None`.
3. L1 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(O1).
8. unchanged: unchanged(L1).

### MCM-D-78 — several foreign rows of different types give one generic entry
- **Rules:** `delete_machine` R4 (a) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. I9.
3. ST9.
4. ST1 = stock of M1, item I9, `qty 5`, but `workspace_id W2.id`.
5. PO1 = purchase order, `destination_id M1.id`, `current_status_id ST9.id`, but `workspace_id W2.id`.
6. TO1 = transfer order, `source_location_type "machine"`, `source_location_id M1.id`, but `workspace_id W2.id`, `destination_location_id F9.id`, `current_status_id ST9.id`.
7. O1 = order of M1, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(ST1).
8. unchanged: unchanged(PO1).
9. unchanged: unchanged(TO1).
10. unchanged: unchanged(O1).

### MCM-D-79 — an order of this workspace through machine_id with a foreign line keeps its entry, and the line adds the generic one
- **Rules:** `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`.
3. L1 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`, but `workspace_id W2.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}, {"type": "other_workspace"}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(O1).
8. unchanged: unchanged(L1).

### MCM-D-80 — no id or text of the other workspace appears anywhere in the refusal
- **Rules:** `delete_machine` R4a [BUG-968], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. I9.
3. ST9.
4. ST1 = stock of M1, item I9, `qty 5`, but `workspace_id W2.id`.
5. PO1 = purchase order, `destination_id M1.id`, `current_status_id ST9.id`, but `workspace_id W2.id`.
6. TO1 = transfer order, `source_location_type "machine"`, `source_location_id M1.id`, but `workspace_id W2.id`, `destination_location_id F9.id`, `current_status_id ST9.id`.
7. O1 = order of M1, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
8. ST2 = stock of M1, item I1, `qty 1`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "machine_stock", "id": ST2.id}, {"type": "other_workspace"}]`.
5. raises: `{(e["type"], e.get("id")) for e in exc.value.args[1]}.isdisjoint({("machine_stock", ST1.id), ("purchase_order", PO1.id), ("transfer_order", TO1.id), ("work_order", O1.id)})`.
6. raises: `all(text not in repr(exc.value.args) for text in ("PO-PO1", "TR-TO1", "WO-O1", "Far Spring", "Far Depot"))`.
7. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
8. count: `machine_activity_events` has exactly 0 rows.

### MCM-D-81 — a line sourcing from a third machine does not block
- **Rules:** `delete_machine` R4 (c), R4b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M2.
3. M3.
4. O1 = order of M2, `status "DRAFT"`.
5. L1 = line of O1, `source_location_type "machine"`, `source_location_id M3.id`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(O1).
4. unchanged: unchanged(L1).

### MCM-D-82 — a transfer to the machine from a soft-deleted factory blocks
- **Rules:** `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. TO1 = transfer order, `source_location_id FD.id`, `destination_location_type "machine"`, `destination_location_id M1.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(TO1).

### MCM-D-83 — a transfer to the machine from a soft-deleted machine blocks
- **Rules:** `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. MX.
3. TO1 = transfer order, `source_location_type "machine"`, `source_location_id MX.id`, `destination_location_type "machine"`, `destination_location_id M1.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(TO1).
8. unchanged: unchanged(MX).

### MCM-D-84 — a transfer at stage Complete with completed_at NULL blocks
- **Rules:** `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. TO1 = transfer order, `source_location_type "machine"`, `source_location_id M1.id`, `current_status_id STC.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(TO1).

### MCM-D-85 — a transfer of this workspace on a stage of another one has its normal entry
- **Rules:** `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. ST9.
3. TO1 = transfer order, `source_location_type "machine"`, `source_location_id M1.id`, `current_status_id ST9.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(TO1).

### MCM-D-86 — two purchase orders are sorted by id ascending
- **Rules:** `delete_machine` R4 (b) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. PO1 = purchase order, `destination_id M1.id`, `current_status_id STD.id`.
3. PO2 = purchase order, `destination_id M1.id`, `current_status_id STD.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "purchase_order", "id": PO1.id}, {"type": "purchase_order", "id": PO2.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(PO1).
8. unchanged: unchanged(PO2).

### MCM-D-87 — two transfers are sorted by id ascending
- **Rules:** `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. TO1 = transfer order, `source_location_type "machine"`, `source_location_id M1.id`.
3. TO2 = transfer order, `destination_location_type "machine"`, `destination_location_id M1.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}, {"type": "transfer_order", "id": TO2.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(TO1).
8. unchanged: unchanged(TO2).

### MCM-D-88 — stock of an inactive item blocks
- **Rules:** `delete_machine` R4 (a) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. IX.
3. ST1 = stock of M1, item IX, `qty 5`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "machine_stock", "id": ST1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(ST1).
8. unchanged: unchanged(IX).

### MCM-D-89 — a sourcing line of an inactive item blocks
- **Rules:** `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. M2.
3. IX.
4. O1 = order of M2, `status "DRAFT"`.
5. L1 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`, but `item_id IX.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(O1).
8. unchanged: unchanged(L1).
9. unchanged: unchanged(IX).

### MCM-D-90 — a work order on the machine in an inactive factory blocks
- **Rules:** `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`, `factory_id FI.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(O1).

### MCM-D-91 — foreign stock at quantity 0 meets no condition and does not block
- **Rules:** `delete_machine` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1.
2. ST1 = stock of M1, item I1, `qty 0`, but `workspace_id W2.id`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(ST1).

### MCM-D-92 — a completed transfer of another workspace meets no condition and does not block
- **Rules:** `delete_machine` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1.
2. ST9.
3. TO1 = transfer order, `source_location_type "machine"`, `source_location_id M1.id`, but `workspace_id W2.id`, `destination_location_id F9.id`, `current_status_id ST9.id`, `completed_at T0`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(TO1).

### MCM-D-93 — a COMPLETED order of another workspace meets no condition and does not block
- **Rules:** `delete_machine` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "COMPLETED"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(O1).

### MCM-D-94 — a consumed line of another workspace meets no condition and does not block
- **Rules:** `delete_machine` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1.
2. M2.
3. O1 = order of M2, `status "DRAFT"`.
4. L1 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`, but `workspace_id W2.id`, `consumed_at T0`.

**When**
- `result = M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is M1` (the very object that was read).
2. re-read M1: `is_deleted is True`.
3. unchanged: unchanged(O1).
4. unchanged: unchanged(L1).

### MCM-D-95 — stock of this workspace with an item of another one keeps its normal entry
- **Rules:** `delete_machine` R4 (a) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. I9.
3. ST1 = stock of M1, item I9, `qty 5`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "machine_stock", "id": ST1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(ST1).

### MCM-D-96 — a work order of this workspace with a factory and a type of another one keeps its normal entry
- **Rules:** `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. O1 = order of M1, `status "DRAFT"`, `factory_id F9.id`, `work_order_type_id WT9.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(O1).

### MCM-D-97 — a transfer of this workspace with an end in another one keeps its normal entry
- **Rules:** `delete_machine` R4 (d) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. TO1 = transfer order, `source_location_type "machine"`, `source_location_id M1.id`, `destination_location_id F9.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO1.id}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(TO1).

### MCM-D-98 — an own order through its own line keeps its entry, and a foreign line adds the generic one
- **Rules:** `delete_machine` R4 (c) [BUG-968], R4a, Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-968
- **Fails today on:** Then 1 (no error is raised: the machine is deleted)

**Given**
1. M1.
2. M2.
3. O1 = order of M2, `status "DRAFT"`.
4. L1 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`.
5. L2 = line of O1, `source_location_type "machine"`, `source_location_id M1.id`, but `workspace_id W2.id`.

**When**
- `M.delete_machine(db, machine_id=M1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[0] == "Machine has stock or open orders"`.
4. raises: `exc.value.args[1] == [{"type": "work_order", "id": O1.id}, {"type": "other_workspace"}]`.
5. re-read M1: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. count: `machine_activity_events` has exactly 0 rows.
7. unchanged: unchanged(O1).
8. unchanged: unchanged(L1).
9. unchanged: unchanged(L2).

## `MachineManager.create_machine_event`

### MCM-E-01 — a first status is recorded and is_running follows
- **Rules:** `create_machine_event` R8, R10, R6, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=RUNNING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, MachineEventResponse)`.
2. returns: `result.id is not None`.
3. event: events_of(M1) has exactly 1 row.
4. event: that row has `event_type == "status_updated"`, `performed_by == U2.id`, `workspace_id == W1.id`.
5. event: that row has `metadata_json == {"status": "RUNNING", "note": None, "changes": [{"field": "status", "label": "Status", "from_value": None, "to_value": "RUNNING"}]}`.
6. re-read M1: `is_running is True`.

### MCM-E-02 — an id that no machine has is refused
- **Rules:** `create_machine_event` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.

**When**
- `M.create_machine_event(db, event_data=MachineEventCreate(machine_id=MISSING, event_type=IDLE), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Machine with ID 999999999 not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).

### MCM-E-03 — a machine of another workspace is refused
- **Rules:** `create_machine_event` R1, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M9.

**When**
- `M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M9.id, event_type=IDLE), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M9).

### MCM-E-04 — a soft-deleted machine is refused
- **Rules:** `create_machine_event` R2, Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MX.

**When**
- `M.create_machine_event(db, event_data=MachineEventCreate(machine_id=MX.id, event_type=IDLE), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create event for a deleted machine"`.
4. nothing written: nothing written.
5. unchanged: unchanged(MX).

### MCM-E-05 — a soft-deleted machine is refused also when a work order drives it
- **Rules:** `create_machine_event` R2, Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MX.

**When**
- `M.create_machine_event(db, event_data=MachineEventCreate(machine_id=MX.id, event_type=IDLE), workspace_id=W1.id, user_id=U2.id, work_order_id=77)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create event for a deleted machine"`.
4. nothing written: nothing written.
5. unchanged: unchanged(MX).

### MCM-E-06 — a deleted machine in a deleted factory gets the deleted-machine message
- **Rules:** `create_machine_event` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MX, but `factory_id FD.id`.

**When**
- `M.create_machine_event(db, event_data=MachineEventCreate(machine_id=MX.id, event_type=IDLE), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create event for a deleted machine"`.
4. nothing written: nothing written.

### MCM-E-07 — a manual change on a machine of a soft-deleted factory is refused
- **Rules:** `create_machine_event` R3 [BUG-974], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-974
- **Fails today on:** Then 1 (no error is raised: the event and `is_running` are written)

**Given**
1. MF.

**When**
- `M.create_machine_event(db, event_data=MachineEventCreate(machine_id=MF.id, event_type=RUNNING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create event for a machine of a deleted factory"`.
4. nothing written: nothing written.
5. unchanged: unchanged(MF).

### MCM-E-08 — the deleted-factory refusal comes before the current status
- **Rules:** `create_machine_event` R3 [BUG-974], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-974
- **Fails today on:** Then 3 (today the "already in" message answers)

**Given**
1. MF.
2. status row of MF at T1, `"IDLE"`.

**When**
- `M.create_machine_event(db, event_data=MachineEventCreate(machine_id=MF.id, event_type=IDLE), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create event for a machine of a deleted factory"`.
4. count: `machine_activity_events` has exactly 1 row.
5. unchanged: unchanged(MF).

### MCM-E-09 — a machine of a live but inactive factory is accepted
- **Rules:** `create_machine_event` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MI.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=MI.id, event_type=RUNNING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read MI: `is_running is True`.

### MCM-E-10 — a work order may drive a machine of a soft-deleted factory
- **Rules:** `create_machine_event` R3a, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MF.
2. O1 = order of MF, `status "IN_PROGRESS"`, `factory_id FD.id`.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=MF.id, event_type=RUNNING), workspace_id=W1.id, user_id=U2.id, work_order_id=O1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read MF: `is_running is True`.
3. event: events_of(MF) has exactly 1 row.
4. event: `events_of(MF)[0].metadata_json["work_order_id"] == O1.id`.

### MCM-E-11 — work order id 0 names no order, also on a machine of a soft-deleted factory
- **Rules:** `create_machine_event` R2a [BUG-1000], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1000
- **Fails today on:** Then 1 (no error is raised: the id is not validated)

**Given**
1. MF.

**When**
- `M.create_machine_event(db, event_data=MachineEventCreate(machine_id=MF.id, event_type=RUNNING), workspace_id=W1.id, user_id=U2.id, work_order_id=0)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Work order with ID 0 not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(MF).

### MCM-E-12 — the newest status row decides, not the last inserted
- **Rules:** `create_machine_event` R4, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. status row of M1 at T2, `"RUNNING"`.
3. status row of M1 at T1, `"IDLE"`.

**When**
- `M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=RUNNING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Machine is already in 'RUNNING' state"`.
4. count: `machine_activity_events` has exactly 2 rows.

### MCM-E-13 — on a created_at tie the highest id decides
- **Rules:** `create_machine_event` R4, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. status row of M1 at T2, `"RUNNING"`.
3. status row of M1 at T2, `"IDLE"`.

**When**
- `M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=IDLE), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Machine is already in 'IDLE' state"`.
4. count: `machine_activity_events` has exactly 2 rows.

### MCM-E-14 — another event type is ignored even when newer and carrying a status
- **Rules:** `create_machine_event` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. status row of M1 at T1, `"IDLE"`.
3. status row of M1 at T2, `"OFF"`, but `event_type "updated"`.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=OFF), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: `events_of(M1)[-1].metadata_json["changes"][0]["from_value"] == "IDLE"`.

### MCM-E-15 — a status row of another workspace is ignored
- **Rules:** `create_machine_event` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1.
2. status row of M1 at T1, `"IDLE"`.
3. status row of M1 at T2, `"OFF"`, but `workspace_id W2.id`.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=OFF), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: `events_of(M1)[-1].metadata_json["changes"][0]["from_value"] == "IDLE"`.

### MCM-E-16 — a new status equal to the current one is refused, in upper case
- **Rules:** `create_machine_event` R5, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.
2. status row of M1 at T1, `"MAINTENANCE"`.

**When**
- `M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=MAINTENANCE), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Machine is already in 'MAINTENANCE' state"`.
4. count: `machine_activity_events` has exactly 1 row.
5. unchanged: unchanged(M1).

### MCM-E-17 — the same status is refused also when a work order drives it
- **Rules:** `create_machine_event` R5, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.
2. status row of M1 at T1, `"RUNNING"`.
3. O1 = order of M1, `status "IN_PROGRESS"`.

**When**
- `M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=RUNNING), workspace_id=W1.id, user_id=U2.id, work_order_id=O1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Machine is already in 'RUNNING' state"`.
4. count: `machine_activity_events` has exactly 1 row.

### MCM-E-18 — a different status is accepted and from_value is the current one
- **Rules:** `create_machine_event` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1.
2. status row of M1 at T1, `"RUNNING"`.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=IDLE), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: `events_of(M1)[-1].metadata_json == {"status": "IDLE", "note": None, "changes": [{"field": "status", "label": "Status", "from_value": "RUNNING", "to_value": "IDLE"}]}`.

### MCM-E-19 — a newest row with NULL metadata means no current status; older rows are not consulted
- **Rules:** `create_machine_event` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. status row of M1 at T1, `"IDLE"`.
3. status row of M1 at T2, but `metadata_json None`.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=IDLE), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: `events_of(M1)[-1].metadata_json["changes"][0]["from_value"] is None`.

### MCM-E-20 — a newest row without a status key means no current status
- **Rules:** `create_machine_event` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. status row of M1 at T1, `"IDLE"`.
3. status row of M1 at T2, but `metadata_json {"note": "x"}`.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=IDLE), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: `events_of(M1)[-1].metadata_json["changes"][0]["from_value"] is None`.

### MCM-E-21 — the description without a note
- **Rules:** `create_machine_event` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=IDLE), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: `events_of(M1)[0].description == "Status set to idle"`.

### MCM-E-22 — the description with a note
- **Rules:** `create_machine_event` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=IDLE, note="Belt"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: `events_of(M1)[0].description == "Status set to idle (Belt)"`.

### MCM-E-23 — the description with an empty note
- **Rules:** `create_machine_event` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=IDLE, note=""), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: `events_of(M1)[0].description == "Status set to idle"`.

### MCM-E-24 — the description with a whitespace note
- **Rules:** `create_machine_event` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=IDLE, note="   "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: `events_of(M1)[0].description == "Status set to idle (   )"`.

### MCM-E-25 — the metadata keeps the note as sent
- **Rules:** `create_machine_event` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=OFF, note="  Belt "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: `events_of(M1)[0].metadata_json == {"status": "OFF", "note": "  Belt ", "changes": [{"field": "status", "label": "Status", "from_value": None, "to_value": "OFF"}]}`.

### MCM-E-26 — the metadata keeps an empty note
- **Rules:** `create_machine_event` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=OFF, note=""), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: `events_of(M1)[0].metadata_json["note"] == ""`.

### MCM-E-27 — the id of a work order of the workspace is stored in the metadata
- **Rules:** `create_machine_event` R9
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1.
2. O1 = order of M1, `status "IN_PROGRESS"`.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=IDLE), workspace_id=W1.id, user_id=U2.id, work_order_id=O1.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: `events_of(M1)[0].metadata_json["work_order_id"] == O1.id`.
3. unchanged: unchanged(O1).

### MCM-E-28 — work order id 0 is refused and nothing is stored
- **Rules:** `create_machine_event` R2a [BUG-1000], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1000
- **Fails today on:** Then 1 (no error is raised: the id is not validated)

**Given**
1. M1.

**When**
- `M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=IDLE), workspace_id=W1.id, user_id=U2.id, work_order_id=0)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Work order with ID 0 not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).

### MCM-E-29 — no work order id adds no key
- **Rules:** `create_machine_event` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=IDLE), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: `"work_order_id" not in events_of(M1)[0].metadata_json`.

### MCM-E-30 — IDLE stops a running machine and stamps it
- **Rules:** `create_machine_event` R10, R11
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1, but `is_running True`.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=IDLE), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read M1: `is_running is False`.
3. re-read M1: `updated_by == U2.id`.
4. re-read M1: `updated_at is not None`.

### MCM-E-31 — OFF stops a running machine and stamps it
- **Rules:** `create_machine_event` R10, R11
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1, but `is_running True`.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=OFF), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read M1: `is_running is False`.
3. re-read M1: `updated_by == U2.id`.
4. re-read M1: `updated_at is not None`.

### MCM-E-32 — MAINTENANCE stops a running machine and stamps it
- **Rules:** `create_machine_event` R10, R11
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1, but `is_running True`.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=MAINTENANCE), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read M1: `is_running is False`.
3. re-read M1: `updated_by == U2.id`.
4. re-read M1: `updated_at is not None`.

### MCM-E-33 — RUNNING on a stopped machine stamps it
- **Rules:** `create_machine_event` R10, R11
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=RUNNING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read M1: `is_running is True`.
3. re-read M1: `updated_by == U2.id`.
4. re-read M1: `updated_at is not None`.

### MCM-E-34 — a first IDLE on a stopped machine writes the event, not the stamp
- **Rules:** `create_machine_event` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=IDLE), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: events_of(M1) has exactly 1 row.
3. re-read M1: `updated_by is None`.
4. re-read M1: `updated_at is None`.

### MCM-E-35 — OFF after MAINTENANCE writes the event, not the stamp
- **Rules:** `create_machine_event` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. status row of M1 at T1, `"MAINTENANCE"`.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=OFF), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: events_of(M1) has exactly 2 rows.
3. re-read M1: `updated_by is None`.
4. re-read M1: `updated_at is None`.

### MCM-E-36 — a first RUNNING on a machine already running writes the event, not the stamp
- **Rules:** `create_machine_event` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1, but `is_running True`.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=RUNNING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: events_of(M1) has exactly 1 row.
3. re-read M1: `is_running is True`.
4. re-read M1: `updated_by is None`.
5. re-read M1: `updated_at is None`.

### MCM-E-37 — the response carries the event's values
- **Rules:** `create_machine_event` R13
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=IDLE, note="Belt"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == events_of(M1)[0].id`.
2. returns: `result.workspace_id == W1.id`, `result.machine_id == M1.id`.
3. returns: `result.event_type == IDLE`.
4. returns: `result.note == "Belt"`.
5. returns: `result.started_at == events_of(M1)[0].created_at`.
6. returns: `result.created_at == events_of(M1)[0].created_at`.
7. returns: `result.initiated_by == U2.id`, `result.created_by == U2.id`.

### MCM-E-38 — the machine row is read FOR UPDATE before the current status
- **Rules:** `create_machine_event` R14 [BUG-960]
- **Kind:** bug
- **Expect:** xfail BUG-960
- **Fails today on:** Then 2 (no statement carries `FOR UPDATE`)

**Given**
1. M1.
2. sql_log started (Conventions).

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=RUNNING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. sql: a recorded statement selects from `machines` and carries `FOR UPDATE`: `lock = [i for i, s in enumerate(sql_log) if "FROM machines" in s and "FOR UPDATE" in s]`, `len(lock) >= 1`.
3. sql: `lock[0] < min(i for i, s in enumerate(sql_log) if "FROM machine_activity_events" in s)`.

### MCM-E-39 — an unknown user fails on flush, is_running unchanged and no event
- **Rules:** `create_machine_event` R15, Errors row 6
- **Kind:** error
- **Expect:** pass

**Given**
1. M1.

**When**
- `M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=RUNNING), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"machine_activity_events_performed_by_fkey" in str(exc.value.orig)`.
4. re-read M1: `is_running is False`.
5. count: `machine_activity_events` has exactly 0 rows.

### MCM-E-40 — the change is flushed but not committed: a rollback removes the event and restores the machine
- **Rules:** `create_machine_event` R16
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=RUNNING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read M1: `is_running is True`, `updated_by == U2.id`.
3. event: events_of(M1) has exactly 1 row.
4. re-read M1 after the savepoint rollback: `is_running is False`, `updated_by is None`.
5. count after the savepoint rollback: `machine_activity_events` has exactly 0 rows.
6. mock called: the `db.commit` spy was never called.

### MCM-E-41 — a work order of another workspace gives 404 and nothing is written
- **Rules:** `create_machine_event` R2a [BUG-1000], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1000
- **Fails today on:** Then 1 (no error is raised: the id is stored in the metadata)

**Given**
1. M1.
2. M9.
3. O9 = order of M9, `status "IN_PROGRESS"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.

**When**
- `M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=IDLE), workspace_id=W1.id, user_id=U2.id, work_order_id=O9.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order with ID {O9.id} not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).

### MCM-E-42 — an unknown work order id gives 404 and nothing is written
- **Rules:** `create_machine_event` R2a [BUG-1000], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1000
- **Fails today on:** Then 1 (no error is raised: the id is stored in the metadata)

**Given**
1. M1.

**When**
- `M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=IDLE), workspace_id=W1.id, user_id=U2.id, work_order_id=MISSING)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Work order with ID 999999999 not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).

### MCM-E-43 — the work order 404 fires before the same-status check
- **Rules:** `create_machine_event` R2a [BUG-1000], R5, Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1000
- **Fails today on:** Then 2 (today the same-status check answers 400)

**Given**
1. M1.
2. status row of M1 at T1, `"RUNNING"`.

**When**
- `M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=RUNNING), workspace_id=W1.id, user_id=U2.id, work_order_id=MISSING)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Work order with ID 999999999 not found"`.
4. count: `machine_activity_events` has exactly 1 row.
5. unchanged: unchanged(M1).

### MCM-E-44 — the order's state and machine are not looked at: a completed order of another machine is accepted
- **Rules:** `create_machine_event` R2a, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M2.
3. O1 = order of M2, `status "COMPLETED"`.

**When**
- `result = M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=IDLE), workspace_id=W1.id, user_id=U2.id, work_order_id=O1.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: `events_of(M1)[0].metadata_json["work_order_id"] == O1.id`.
3. unchanged: unchanged(O1).

### MCM-E-45 — a soft-deleted work order of the workspace gives 404 and nothing is written
- **Rules:** `create_machine_event` R2a [BUG-1000], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1000
- **Fails today on:** Then 1 (no error is raised: the id is stored in the metadata)

**Given**
1. M1.
2. O1 = order of M1, `status "IN_PROGRESS"`, `is_deleted True`.

**When**
- `M.create_machine_event(db, event_data=MachineEventCreate(machine_id=M1.id, event_type=IDLE), workspace_id=W1.id, user_id=U2.id, work_order_id=O1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order with ID {O1.id} not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(M1).
6. unchanged: unchanged(O1).

## `MachineManager._check_name_exists_in_factory`

### MCM-N-01 — a live machine of that factory and name is found
- **Rules:** `_check_name_exists_in_factory` R1, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. M2.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Press")`.

**Then**
1. returns: `result is True`.

### MCM-N-02 — a machine of another factory is not found
- **Rules:** `_check_name_exists_in_factory` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M2.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F2.id, name="Press")`.

**Then**
1. returns: `result is False`.

### MCM-N-03 — the factory id seen from another workspace is not found
- **Rules:** `_check_name_exists_in_factory` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M2.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W2.id, factory_id=F1.id, name="Press")`.

**Then**
1. returns: `result is False`.

### MCM-N-04 — a soft-deleted machine is ignored
- **Rules:** `_check_name_exists_in_factory` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MX.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Old Saw")`.

**Then**
1. returns: `result is False`.

### MCM-N-05 — name "press" matches a live "Press"
- **Rules:** `_check_name_exists_in_factory` R4 [BUG-952]
- **Kind:** bug
- **Expect:** xfail BUG-952
- **Fails today on:** Then 1 (names are compared exactly, so the call returns False)

**Given**
1. M2.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="press")`.

**Then**
1. returns: `result is True`.

### MCM-N-06 — name "PRESS" matches a live "Press"
- **Rules:** `_check_name_exists_in_factory` R4 [BUG-952]
- **Kind:** bug
- **Expect:** xfail BUG-952
- **Fails today on:** Then 1 (names are compared exactly, so the call returns False)

**Given**
1. M2.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="PRESS")`.

**Then**
1. returns: `result is True`.

### MCM-N-07 — name "Press " matches a live "Press"
- **Rules:** `_check_name_exists_in_factory` R4 [BUG-952]
- **Kind:** bug
- **Expect:** xfail BUG-952
- **Fails today on:** Then 1 (names are compared exactly, so the call returns False)

**Given**
1. M2.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Press ")`.

**Then**
1. returns: `result is True`.

### MCM-N-08 — name "\tPress" matches a live "Press"
- **Rules:** `_check_name_exists_in_factory` R4 [BUG-952]
- **Kind:** bug
- **Expect:** xfail BUG-952
- **Fails today on:** Then 1 (names are compared exactly, so the call returns False)

**Given**
1. M2.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="\tPress")`.

**Then**
1. returns: `result is True`.

### MCM-N-09 — name "Press  2" does not match a live "Press"
- **Rules:** `_check_name_exists_in_factory` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M2.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Press  2")`.

**Then**
1. returns: `result is False`.

### MCM-N-10 — name "Pres" does not match a live "Press"
- **Rules:** `_check_name_exists_in_factory` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M2.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Pres")`.

**Then**
1. returns: `result is False`.

### MCM-N-11 — every one of 101 live machines is found: no name is missed
- **Rules:** `_check_name_exists_in_factory` R5 [BUG-951]
- **Kind:** bug
- **Expect:** xfail BUG-951
- **Fails today on:** Then 2 (at most 100 machines are loaded, so exactly one name is missed; which one varies, the count does not)

**Given**
1. bulk(101, "P"); `names` = their names.

**When**
- the loop `found = [M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name=n) for n in names]`, where `names` is the list of the bulk names.

**Then**
1. returns: `len(found) == 101`.
2. returns: `found.count(False) == 0`.

### MCM-N-12 — every one of 150 live machines is found
- **Rules:** `_check_name_exists_in_factory` R5 [BUG-951]
- **Kind:** bug
- **Expect:** xfail BUG-951
- **Fails today on:** Then 2 (at most 100 machines are loaded, so 50 names are missed)

**Given**
1. bulk(150, "P"); `names` = their names.

**When**
- the loop `found = [M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name=n) for n in names]`, where `names` is the list of the bulk names.

**Then**
1. returns: `len(found) == 150`.
2. returns: `found.count(False) == 0`.

### MCM-N-13 — every one of exactly 100 live machines is found
- **Rules:** `_check_name_exists_in_factory` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(100, "P"); `names` = their names.

**When**
- the loop `found = [M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name=n) for n in names]`, where `names` is the list of the bulk names.

**Then**
1. returns: `len(found) == 100`.
2. returns: `found.count(False) == 0`.

### MCM-N-14 — soft-deleted machines do not use up a place
- **Rules:** `_check_name_exists_in_factory` R5, R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. bulk(100, "P"), but each with `is_deleted True`, `is_active False`.
2. machine, `name "Zeta"`.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Zeta")`.

**Then**
1. returns: `result is True`.

### MCM-N-15 — the excluded machine is ignored
- **Rules:** `_check_name_exists_in_factory` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. M2.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Press", exclude_id=M2.id)`.

**Then**
1. returns: `result is False`.

### MCM-N-16 — excluding another machine still finds the match
- **Rules:** `_check_name_exists_in_factory` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M2.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Press", exclude_id=M1.id)`.

**Then**
1. returns: `result is True`.

### MCM-N-17 — a same-named machine in another factory is not rescued by exclude_id
- **Rules:** `_check_name_exists_in_factory` R6, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M2.
2. M3, but `name "Press"`.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Press", exclude_id=M2.id)`.

**Then**
1. returns: `result is False`.

### MCM-N-18 — a factory without machines gives False
- **Rules:** `_check_name_exists_in_factory` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M2.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F2.id, name="Press")`.

**Then**
1. returns: `result is False`.

### MCM-N-19 — an unknown factory gives False
- **Rules:** `_check_name_exists_in_factory` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M2.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=MISSING, name="Press")`.

**Then**
1. returns: `result is False`.

### MCM-N-20 — in a soft-deleted factory the answer is False
- **Rules:** `_check_name_exists_in_factory` R8 [BUG-891]
- **Kind:** bug
- **Expect:** xfail BUG-891
- **Fails today on:** Then 1 (the factory row is never looked at, so the call returns True)

**Given**
1. MF.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=FD.id, name="Kiln")`.

**Then**
1. returns: `result is False`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `search_machines` R20 [BUG-956] | `MachineService.get_machines`, `GET /machines/` | `include_deleted` reachable from the API. |
| `get_machine` R4 — reachable from the API (FU-1 b) | `MachineService.get_machine`, `GET /machines/{id}/` | `include_deleted` on the endpoint; 404 by default. |
| `delete_machine` R4a — the 400 body (FU-1 a) | `MachineService.delete_machine`, `DELETE /machines/{id}/` | `ValidationError(detail=args[0], errors=args[1])`; without it a 500. |
| Refusals and schema errors as HTTP | `/machines/` endpoints | Status of the refusals; schema `ValidationError` as 422; `skip >= 0`, `1 <= limit <= 1000`. |
| Writers — commit, rollback, `db.refresh` | `MachineService` | Commit on success, rollback on error. Here one savepoint-and-spy card per writer. |
| FU-1 c — free-text `sort_by`, `sort_dir`, `maintenance_window` | machines endpoint review | Whether unknown values become 422 (P8). |
| `create_machine_event` R14 — the loser of a real race | integration test with two connections | The second caller sees the new status and gets R5. Here the emitted `FOR UPDATE` only. |
| `create_machine` R11, BUG-910 (section of a deleted factory) | assignment manager cards (MSM-SET-19) | Refusal text. Through this manager the factory check answers first once BUG-963 is fixed. |
| `search_machines` R1, `_check_name_exists_in_factory` — the DAO's own rules and bugs (BUG-886 … BUG-892, BUG-343) | machine DAO cards, `tests/unit/dao/machine.cases.md` | Filters, paging, order. Here one pass-through card per argument and bug. The strict `ORDER BY` proof of BUG-343 stays with the DAO's deferred entry. |
| FU-3 — BUG-953 changes DAO `restore` R9 | machine DAO spec | `restore` into a taken name becomes an `IntegrityError`; setups with two live same-named machines change. |
| FU-4 — "restore machine" feature | feature to build | Refuse a name in use with 409; a machine of a deleted factory. |
| FU-5 — O5, BUG-974, BUG-975 on the work order side | `app/managers/work_order_manager.py` | `_set_machine_status`, `create_work_order_from_template` on a deleted machine, always passing `work_order_id`; a `REPLACE` part of a moved order landing in the new factory's damaged bucket; voiding an order, or a `BORROW` return, posting stock back to a machine deleted while the order held a consumed line from it (G12, with BUG-663). |
| FU-6, BUG-969 — frontend | `EditMachineDialog.tsx`, `MachinesPage.tsx` | Sending `null`; showing the blockers. No backend test. |
| FU-7 — other managers taking a machine id | purchase / transfer order, work order, machine item, maintenance log specs | Whether each refuses a deleted machine; cross-workspace rows are refused where they are created (work order `machine_id`, line `source_location_id`, purchase order `destination_id`, transfer location ids, `machine_items`). |
| FU-8 — activity manager | `machine_activity_manager.py` | `get_latest_status`, `get_latest_status_map`. |
| FU-9 — `search_machines` R15 | product-wide date review | Server's `date.today()` against the user's day. Here dates are relative to the same `date.today()`. |
| FU-10 — `production_lines.factory_id` on a move | production line manager | Not changed here. |
| `search_machines` R19 — negative `skip` / `limit` on the maintenance path | none | The rule says no case: unreachable through the API. |

## Spec gaps
All ten gaps of the first version are closed by the spec's Gap log (fill-gaps of 2026-10-30). Gap 12 is closed by G12, the owner's answer. Gaps 13 and 14 are closed by the owner's answers. Gap 11 is new and blocks nothing.

| # | Where | What is missing | How it was closed |
|---|---|---|---|
| 1 | `update_machine` R28, R28d, Notes **(order workflow)** | Class and columns of `work_order_approvers`, what a recorded approval is, the assignees' table. | **Closed (G1, fact).** U-126 builds the row and checks `approved`, `approved_at`, and the order's own `approved_by`, `approved_at`; U-136 (new, pass) covers `work_order_assignees` and `assigned_to`. |
| 2 | `delete_machine` R4b | Class and columns of the maintenance log; the column by which a template or a formula stage names a machine. | **Closed (G2, fact).** The three pass cards name the columns. See gap 11. |
| 3 | `delete_machine` R4 **(order workflow)** | Whether a blocker row with another `workspace_id` blocks. | **Closed (G3, corrected).** The first answer (item carry-over, by machine id only) is withdrawn. Owner's approved answer: such a row is invalid data, must be refused at creation (FU-7), and a delete shows it only as one generic entry, last. D-55 … D-59, D-60, D-78, D-79, D-80. |
| 4 | `create_machine` R3, `update_machine` R8 × R6, R7 | Which text is in the 409 for a padded name. | **Closed (G4, delegated).** The name as the manager receives it, trimmed once BUG-950 is fixed. C-33 now asserts the `detail`. It is tagged BUG-952 and passes only when BUG-950 is fixed too. |
| 5 | `update_machine` R23 × R24 | A section-only change by the user already stamped. | **Closed (G5, delegated).** No column of the row changes; the link and the event record it. U-137 (new, pass). |
| 6 | `search_machines` R21 × Notes | The Notes called all of BUG-957 strict, but page-before-filter depends on row order. | **Closed (G6, delegated).** That card stays non-strict, as designed. No card change. |
| 7 | `search_machines` R21 × R8 | Work dates of a deleted machine; a live machine of a soft-deleted factory with `include_deleted=True`. | **Closed (G7, delegated).** R8 states both. S-105, S-106 stay; S-113 (new, xfail BUG-957) covers the factory. |
| 8 | Notes, inherited DAO bugs | How the pass-through cards are marked. | **Closed (G8, delegated).** Intended behavior, strict, BUG-887 non-strict: as designed. No card change. |
| 9 | `create_machine_event` R13 | The type of `MachineEventResponse.event_type`. | **Closed (G9, fact).** A `MachineEventTypeEnum` member: E-37 stands. No card change. |
| 10 | Overview, `delete_machine` R4 | Class names and import paths of the order and stock tables. | **Closed (G10, fact).** Added to Conventions as imports. No card change. |
| 11 | Notes, `machine_maintenance_logs` row | New: the members and import of `MaintenanceTypeEnum` and the type of `maintenance_date` are not given. | Not blocking: D-42 uses `list(MaintenanceTypeEnum)[0]` and `D(0)`; the executor reports what it used. |
| 12 | `delete_machine` R4 **(order workflow)** | The state of what a blocker points at; a sourcing line already consumed or with `uses_inventory False`. | **Closed (G12, the owner's own answer, "1 and 2 block, 3 not").** Blocks: D-69 … D-74, D-77. Does not block: D-75, D-76. The machine's own state stays with R1–R3 (D-09, D-11), an inactive factory with D-68. |
| 13 | `update_machine` R28, R28e **(order workflow)** | R28e's `from_value` for an order whose `factory_id` already differs from the machine's. | **Closed (the owner's answer, 2026-10-30).** `from_value` is the order's own old factory, not the machine's. U-138 asserts it. |
| 14 | `create_machine_event` R2a **(order workflow)** | From the verifier's round 2: does a soft-deleted work order of the workspace count as a state (accepted) or as naming no work order (404)? | **Closed (the owner's answer, relayed 2026-10-31).** 404, strict xfail BUG-1000: E-45. The spec's R2a still reads "Id and workspace only: the order's state … not looked at" and needs this exception; E-44 (`COMPLETED`, another machine) stands. |


## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_machine` | R1 | C-24, C-25, C-26, C-27 |
| `create_machine` | R2 | C-28 (xfail), C-29 (xfail), C-30 |
| `create_machine` | R3 | C-31, C-32 (xfail), C-33 (xfail) |
| `create_machine` | R4 | C-34, C-35, C-36, D-49 |
| `create_machine` | R5 | C-01, C-02, C-03, C-04 |
| `create_machine` | R6 | C-14 (xfail), C-15, C-16 (xfail), C-17 (xfail), C-18 (xfail), C-19 |
| `create_machine` | R7 | C-05, C-06, C-07, C-08 (xfail), C-09 (xfail), C-10 (xfail), C-11 (xfail), C-12 (xfail), C-13 (xfail) |
| `create_machine` | R8 | C-20 (xfail), C-21, C-22 (xfail), C-23 |
| `create_machine` | R9 | C-37 (xfail), C-38 (xfail), C-39, C-40, C-41 (xfail) |
| `create_machine` | R10 | C-42, C-43 |
| `create_machine` | R11 | C-44, C-45, C-46, C-47, C-48 |
| `create_machine` | R12 | C-44, C-45, C-46, C-47, C-48 |
| `create_machine` | R13 | C-49 |
| `create_machine` | R14 | C-50 |
| `create_machine` | R15 | C-51 |
| `create_machine` | Errors row 1 | C-24, C-25, C-26, C-27 |
| `create_machine` | Errors row 2 | C-28 (xfail), C-29 (xfail) |
| `create_machine` | Errors row 3 | C-31, C-32 (xfail), C-33 (xfail), C-41 (xfail) |
| `create_machine` | Errors row 4 | C-44, C-45, C-46, C-47, C-48 |
| `create_machine` | Errors row 5 | C-16 (xfail), C-17 (xfail), C-18 (xfail), C-20 (xfail), C-22 (xfail) |
| `create_machine` | Errors row 6 | C-50 |
| `create_machine` | Returns | C-01, C-42, C-51 |
| `update_machine` | R1 | U-04, U-05, U-110 |
| `update_machine` | R2 | U-06, U-07, U-08, U-09, U-111 |
| `update_machine` | R3 | U-10 (xfail), U-11 (xfail), U-12 (xfail), U-13 (xfail), U-14, U-112 (xfail) |
| `update_machine` | R4 | U-01, U-02, U-18 |
| `update_machine` | R5 | U-15 (xfail), U-16 (xfail), U-17 (xfail), U-18, U-19 (xfail), U-20 (xfail) |
| `update_machine` | R6 | U-21 (xfail), U-22 (xfail), U-23 (xfail), U-24 (xfail), U-25 (xfail), U-26 (xfail), U-27, U-28 |
| `update_machine` | R6a | U-29 (xfail), U-30, U-31 (xfail), U-32 |
| `update_machine` | R7 | U-33 (xfail), U-34 (xfail), U-35 (xfail), U-36 (xfail), U-37 (xfail), U-38 |
| `update_machine` | R8 | U-39, U-40 (xfail), U-41, U-42, U-43, U-113 |
| `update_machine` | R9 | U-34 (xfail), U-44, U-45 |
| `update_machine` | R10 | U-43, U-46 (xfail), U-47 (xfail), U-48, U-49, U-50, U-114 (xfail) |
| `update_machine` | R10a | U-51 (xfail) |
| `update_machine` | R11 | U-48, U-52, U-53, U-81, U-115, U-116 |
| `update_machine` | R12 | U-54 (xfail), U-55 (xfail), U-56, U-117 (xfail) |
| `update_machine` | R13 | U-57 (xfail), U-118 (xfail) |
| `update_machine` | R14 | U-58, U-83 |
| `update_machine` | R15 | U-08, U-09, U-13 (xfail), U-55 (xfail), U-59, U-60 |
| `update_machine` | R16 | U-61, U-77, U-83 |
| `update_machine` | R17 | U-18, U-62, U-63, U-64, U-65, U-66, U-67, U-68, U-69, U-70, U-71, U-72, U-78, U-82 |
| `update_machine` | R18 | U-73 (xfail), U-74 |
| `update_machine` | R19 | U-75 (xfail), U-76, U-77, U-78 |
| `update_machine` | R20 | U-79 (xfail), U-80 (xfail), U-81, U-83 |
| `update_machine` | R21 | U-67, U-68, U-69, U-70, U-71, U-72, U-119 (xfail), U-120 |
| `update_machine` | R22 | U-02, U-03 |
| `update_machine` | R23 | U-01, U-62, U-137 |
| `update_machine` | R24 | U-01, U-62, U-84 (xfail), U-85 (xfail), U-86 (xfail), U-87 (xfail), U-88 (xfail), U-89 (xfail), U-90, U-137 |
| `update_machine` | R25 | U-93, U-130, U-137 |
| `update_machine` | R26 | U-66, U-80 (xfail), U-81, U-82, U-93, U-94, U-95, U-96, U-97 |
| `update_machine` | R27 | U-44, U-58, U-65, U-74, U-90, U-91, U-92 |
| `update_machine` | R28 | U-98 (xfail), U-99 (xfail), U-100, U-101 (xfail), U-136, U-138 (xfail) |
| `update_machine` | R28a | U-101 (xfail), U-102, U-103, U-104, U-105, U-106 |
| `update_machine` | R28b | U-107, U-108, U-109, U-110, U-111, U-112 (xfail), U-113, U-114 (xfail), U-115, U-116, U-117 (xfail), U-118 (xfail), U-119 (xfail), U-120, U-121 (xfail), U-135 |
| `update_machine` | R28c | U-122, U-123, U-132 |
| `update_machine` | R28d | U-124, U-125, U-126 |
| `update_machine` | R28e | U-121 (xfail), U-127 (xfail), U-128 (xfail), U-129 (xfail), U-130, U-138 (xfail) |
| `update_machine` | R28f | U-99 (xfail), U-101 (xfail), U-131 (xfail), U-132 |
| `update_machine` | R29 | U-133, U-134 (xfail) |
| `update_machine` | R30 | U-135 |
| `update_machine` | Errors row 1 | U-04, U-05 |
| `update_machine` | Errors row 2 | U-06, U-07, U-08, U-09, U-10 (xfail), U-11 (xfail), U-12 (xfail), U-13 (xfail) |
| `update_machine` | Errors row 3 | U-52, U-53, U-57 (xfail), U-59 |
| `update_machine` | Errors row 4 | U-54 (xfail), U-55 (xfail) |
| `update_machine` | Errors row 5 | U-39, U-40 (xfail), U-43, U-46 (xfail), U-47 (xfail), U-51 (xfail), U-60 |
| `update_machine` | Errors row 6 | U-67, U-68, U-69, U-70, U-71, U-72, U-78, U-119 (xfail) |
| `update_machine` | Errors row 7 | U-19 (xfail), U-20 (xfail), U-29 (xfail), U-31 (xfail), U-35 (xfail), U-36 (xfail), U-37 (xfail) |
| `update_machine` | Errors row 8 | U-133 |
| `update_machine` | Returns | U-01, U-135 |
| `update_machine` | Side effects | U-127 (xfail), U-139 |
| `get_machine` | R1 | G-01, G-02 |
| `get_machine` | R2 | G-03, G-04 |
| `get_machine` | R3 | G-05 (xfail), D-52 (xfail) |
| `get_machine` | R4 | G-06 (xfail), G-07 (xfail) |
| `get_machine` | R5 | G-08 (xfail), G-09 (xfail), G-10 |
| `get_machine` | Errors row 1 | G-03, G-04, G-05 (xfail), G-07 (xfail), G-08 (xfail) |
| `get_machine` | Returns | G-01 |
| `search_machines` | R1 | S-01, S-02, S-03, S-04, S-05, S-06, S-07, S-08, S-09, S-10, S-11, S-12 (xfail), S-13 (xfail), S-14 (xfail) |
| `search_machines` | R2 | S-15, S-16 |
| `search_machines` | R3 | S-17, S-18, S-19 (xfail), S-20, S-24, S-25, S-26 (xfail), S-27, S-31, S-32 (xfail) |
| `search_machines` | R4 | S-17, S-21, S-22, S-23, S-24, S-28, S-29, S-30 |
| `search_machines` | R5 | S-28, S-29, S-33, S-34, S-35, S-87 |
| `search_machines` | R6 | S-36, S-37, S-38, S-39 (xfail) |
| `search_machines` | R7 | S-40 (xfail), S-41 (xfail), S-42 |
| `search_machines` | R8 | S-43, S-44, S-45, S-46, S-47, S-63, S-68, S-105 (xfail), S-106 (xfail), S-113 (xfail) |
| `search_machines` | R9 | S-48, S-49 (xfail), S-50 (xfail), S-51, S-52 (xfail), S-53, S-54 (xfail) |
| `search_machines` | R10 | S-51, S-52 (xfail), S-55, S-56, S-57, S-58 |
| `search_machines` | R11 | S-59, S-60, S-61, S-62, S-63, S-69 |
| `search_machines` | R12 | S-64, S-65, S-66, S-67, S-68 |
| `search_machines` | R13 | S-46, S-48, S-49 (xfail), S-50 (xfail), S-70, S-71, S-72, S-73, S-74 |
| `search_machines` | R14 | S-24, S-25, S-27, S-30, S-36, S-37, S-38, S-75, S-76, S-77, S-78 |
| `search_machines` | R15 | S-55, S-57, S-59, S-64, S-71, S-82 |
| `search_machines` | R16 | S-33, S-53, S-54 (xfail), S-79, S-80, S-81, S-82, S-83, S-87 |
| `search_machines` | R17 | S-84, S-85, S-86 |
| `search_machines` | R18 | S-88 (xfail) |
| `search_machines` | R19 | S-78, S-89, S-90, S-91, S-92, S-93, S-94 |
| `search_machines` | R21 | S-95, S-96, S-97, S-98, S-99, S-100, S-101 (xfail), S-102 (xfail), S-103 (xfail), S-104 (xfail), S-105 (xfail), S-106 (xfail), S-107 (xfail), S-108 (xfail), S-109 (xfail), S-110 (xfail), S-111 (xfail), S-112 (xfail), S-113 (xfail), S-114, S-115 |
| `search_machines` | Errors row 1 | S-15, S-16 |
| `search_machines` | Errors row 2 | S-39 (xfail) |
| `search_machines` | Returns | S-01, S-03 |
| `delete_machine` | R1 | D-06, D-07, D-67 |
| `delete_machine` | R2 | D-08, D-09 |
| `delete_machine` | R3 | D-10 (xfail), D-11 (xfail), D-12, D-68 (xfail) |
| `delete_machine` | R4 | D-09, D-11 (xfail), D-41 (xfail), D-67, D-91, D-92, D-93, D-94 |
| `delete_machine` | R4 (a) | D-13 (xfail), D-14 (xfail), D-15, D-16, D-55 (xfail), D-60 (xfail), D-61 (xfail), D-68 (xfail), D-78 (xfail), D-88 (xfail), D-95 (xfail) |
| `delete_machine` | R4 (b) | D-17 (xfail), D-18, D-19, D-20, D-56 (xfail), D-64 (xfail), D-65, D-66, D-86 (xfail) |
| `delete_machine` | R4 (c) | D-21 (xfail), D-22 (xfail), D-23 (xfail), D-24, D-25, D-26, D-27, D-28, D-29, D-58 (xfail), D-59 (xfail), D-62 (xfail), D-63 (xfail), D-69 (xfail), D-72 (xfail), D-73 (xfail), D-74 (xfail), D-75, D-76, D-77 (xfail), D-79 (xfail), D-81, D-89 (xfail), D-90 (xfail), D-96 (xfail), D-98 (xfail) |
| `delete_machine` | R4 (d) | D-30 (xfail), D-31 (xfail), D-32, D-33, D-57 (xfail), D-70 (xfail), D-71 (xfail), D-82 (xfail), D-83 (xfail), D-84 (xfail), D-85 (xfail), D-87 (xfail), D-97 (xfail) |
| `delete_machine` | R4a | D-13 (xfail), D-14 (xfail), D-17 (xfail), D-21 (xfail), D-22 (xfail), D-23 (xfail), D-30 (xfail), D-31 (xfail), D-34 (xfail), D-35 (xfail), D-36 (xfail), D-37 (xfail), D-38 (xfail), D-39 (xfail), D-40 (xfail), D-55 (xfail), D-56 (xfail), D-57 (xfail), D-58 (xfail), D-59 (xfail), D-60 (xfail), D-61 (xfail), D-62 (xfail), D-63 (xfail), D-64 (xfail), D-68 (xfail), D-69 (xfail), D-70 (xfail), D-71 (xfail), D-72 (xfail), D-73 (xfail), D-74 (xfail), D-75, D-76, D-77 (xfail), D-78 (xfail), D-79 (xfail), D-80 (xfail), D-82 (xfail), D-83 (xfail), D-84 (xfail), D-85 (xfail), D-86 (xfail), D-87 (xfail), D-88 (xfail), D-89 (xfail), D-90 (xfail), D-95 (xfail), D-96 (xfail), D-97 (xfail), D-98 (xfail) |
| `delete_machine` | R4b | D-03, D-04, D-42, D-43, D-44, D-45, D-46, D-47, D-75, D-76, D-81 |
| `delete_machine` | R5 | D-01, D-02 |
| `delete_machine` | R6 | D-03, D-04 |
| `delete_machine` | R7 | D-05 |
| `delete_machine` | R8 | D-48, D-49, D-50, D-51, D-52 (xfail) |
| `delete_machine` | R9 | D-41 (xfail), D-53 |
| `delete_machine` | R10 | D-54 |
| `delete_machine` | Errors row 1 | D-06, D-07, D-67 |
| `delete_machine` | Errors row 2 | D-08 |
| `delete_machine` | Errors row 3 | D-10 (xfail) |
| `delete_machine` | Errors row 4 | D-13 (xfail), D-14 (xfail), D-17 (xfail), D-21 (xfail), D-22 (xfail), D-23 (xfail), D-30 (xfail), D-31 (xfail), D-55 (xfail), D-56 (xfail), D-57 (xfail), D-58 (xfail), D-59 (xfail), D-60 (xfail), D-61 (xfail), D-62 (xfail), D-63 (xfail), D-64 (xfail), D-68 (xfail), D-69 (xfail), D-70 (xfail), D-71 (xfail), D-72 (xfail), D-73 (xfail), D-74 (xfail), D-77 (xfail), D-78 (xfail), D-79 (xfail), D-80 (xfail), D-82 (xfail), D-83 (xfail), D-84 (xfail), D-85 (xfail), D-86 (xfail), D-87 (xfail), D-88 (xfail), D-89 (xfail), D-90 (xfail), D-95 (xfail), D-96 (xfail), D-97 (xfail), D-98 (xfail) |
| `delete_machine` | Errors row 5 | D-53 |
| `delete_machine` | Returns | D-01, D-54 |
| `create_machine_event` | R1 | E-02, E-03 |
| `create_machine_event` | R2 | E-04, E-05, E-06 |
| `create_machine_event` | R2a | E-11 (xfail), E-28 (xfail), E-41 (xfail), E-42 (xfail), E-43 (xfail), E-44, E-45 (xfail) |
| `create_machine_event` | R3 | E-06, E-07 (xfail), E-08 (xfail), E-09 |
| `create_machine_event` | R3a | E-10 |
| `create_machine_event` | R4 | E-12, E-13, E-14, E-15 |
| `create_machine_event` | R5 | E-12, E-13, E-16, E-17, E-43 (xfail) |
| `create_machine_event` | R6 | E-01, E-19, E-20 |
| `create_machine_event` | R7 | E-21, E-22, E-23, E-24 |
| `create_machine_event` | R8 | E-01, E-18, E-25, E-26 |
| `create_machine_event` | R9 | E-10, E-27, E-29, E-44 |
| `create_machine_event` | R10 | E-01, E-30, E-31, E-32, E-33 |
| `create_machine_event` | R11 | E-30, E-31, E-32, E-33 |
| `create_machine_event` | R12 | E-34, E-35, E-36 |
| `create_machine_event` | R13 | E-37 |
| `create_machine_event` | R14 | E-38 (xfail) |
| `create_machine_event` | R15 | E-39 |
| `create_machine_event` | R16 | E-40 |
| `create_machine_event` | Errors row 1 | E-02, E-03 |
| `create_machine_event` | Errors row 2 | E-04, E-05 |
| `create_machine_event` | Errors row 3 | E-11 (xfail), E-28 (xfail), E-41 (xfail), E-42 (xfail), E-43 (xfail), E-45 (xfail) |
| `create_machine_event` | Errors row 4 | E-07 (xfail), E-08 (xfail) |
| `create_machine_event` | Errors row 5 | E-16, E-17 |
| `create_machine_event` | Errors row 6 | E-39 |
| `create_machine_event` | Returns | E-01 |
| `_check_name_exists_in_factory` | R1 | N-01 |
| `_check_name_exists_in_factory` | R2 | N-02, N-03, N-17 |
| `_check_name_exists_in_factory` | R3 | N-04, N-14 |
| `_check_name_exists_in_factory` | R4 | C-32 (xfail), C-33 (xfail), N-01, N-05 (xfail), N-06 (xfail), N-07 (xfail), N-08 (xfail), N-09, N-10 |
| `_check_name_exists_in_factory` | R5 | N-11 (xfail), N-12 (xfail), N-13, N-14 |
| `_check_name_exists_in_factory` | R6 | N-15, N-16, N-17 |
| `_check_name_exists_in_factory` | R7 | N-18, N-19 |
| `_check_name_exists_in_factory` | R8 | N-20 (xfail) |
| `search_machines` | R20 [BUG-956] | Deferred (`MachineService.get_machines`, `GET /machines/`) |
