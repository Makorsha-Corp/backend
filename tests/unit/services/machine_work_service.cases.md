# Test cases — `app/services/machine_work_service.py`

> **Spec:** `tests/unit/services/machine_work_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-22) — spec Gap log G1–G3 closed. G1: only `is_deleted` is read, `factories.abbreviation` is the only extra NOT NULL column; **gone** note updated and MWS-CR-26 added (a machine with only `is_deleted True` is left out). G2: relationship names given; MWS-CR-27 added (section assignment and section loaded by the query). G3: HH-08's "contains" check is now the spec's own rule (R3), Then 3 note updated.
> **Revision:** 3 (2026-11-22) — spec Gap log G4 (executor note on MWS-CR-01): the items are `Row`s, not `tuple`s; CR-01 drops the tuple type check and asserts unpacking, indexing, `len == 2` and equality with `(wo, machine)`. Counts unchanged.
> **Revision:** 3a (2026-11-22) — verifier observation on DM-03: its rows are now inserted in mixed date orders (M1 descending, M2 ascending, M3 out of order), so a missing sort fails DM-03 whether the database returns rows in insertion or id order, forwards or backwards. Counts unchanged.
> **Counts:** 70 cases · 65 expected-to-pass · 5 expected-to-fail (bugs) · 2 deferred

## Reviewer summary
- **Per callable:** `collect_raw_items` 27 (2 bug) · `upcoming_work` 16 (2 bug) · `dates_by_machine` 12 (1 bug) · `earliest_upcoming_on_or_after` 4 · `has_overdue` 3 · `has_upcoming_in_horizon` 8 (incl. the not-wrapped `ValueError`, TC6).
- **Depth:** the module writes nothing (no stock, money or order state) and has no access decision, so the lighter target applies to the wrappers; the shared query `collect_raw_items` gets the full 1b shapes once (window both sides, statuses exact on both sides, every filter with a lower and a higher id, W0 and W2, real soft-deleted rows, no lock). `upcoming_work` and `dates_by_machine` get one pass-through card per filter plus full cards for their own logic (grouping, row content, both sort orders, date lists, the no-ids short cut).
- **No write callable.** The service never commits or rolls back (spec Form: TC1–TC5 do not apply), so there are no commit, rollback-with-extra-row or failing-commit cards. Each of the three query methods instead has one TC6 card: commit and rollback spies never called, a flushed uncommitted row still pending, an unflushed edit still dirty, nothing committed. Lock clauses: `collect_raw_items` is checked to emit no `FOR UPDATE` (CR-24); real concurrency is not relevant to a read.
- **Expected-to-fail (all strict):** BUG-1571 4 (CR-15 machine of W2, CR-16 machine of W0, UW-14, DM-09) · BUG-1572 1 (UW-13). Passing companions: the order seen from the machine's own workspace (CR-17, DM-11), a deleted-factory machine kept by `collect_raw_items` and `dates_by_machine` (CR-18, DM-08, D2), an inactive-but-live factory (UW-15).
- **Notable design choices:** all window dates are in 2030 (not the current year); nothing reads the clock. Order numbers carry a per-process suffix (BUG-726 family). `collect_raw_items` has no defined order, so its cards compare sets only.
- **Needs a decision:** None. Gaps 1–3 were closed by the spec in Revision 2.

## Conventions for this module

**IDs.** `MWS` = `app/services/machine_work_service.py`. `CR` collect_raw_items · `UW` upcoming_work · `DM` dates_by_machine · `EU` earliest_upcoming_on_or_after · `HO` has_overdue · `HH` has_upcoming_in_horizon.

**Actors and fixed values.**
- `svc` = `machine_work_service` (`from app.services.machine_work_service import MachineWorkService, machine_work_service`). `db` = the test's real session, first argument; every other argument of the three query methods by keyword. The three helpers are called on the class, positional: `MachineWorkService.has_overdue(dates, today)`. `result` = what the When returns. The session does not autoflush.
- Classes: `Factory`, `Machine`, `FactorySection`, `MachineSectionAssignment`, `WorkOrderType`, `WorkOrder` (each from `app.models.<snake_case name>`); `MachineUpcomingWorkRow` (`app.schemas.machine_work`); `select`, `func`, `text` (`sqlalchemy`); `patch` (`unittest.mock`); `date`, `datetime`, `timedelta` (`datetime`).
- W0, W1, W2 = three `workspaces` rows built in that order (ids rise W0 < W1 < W2); U1 = a `profiles` row (`make_workspace`, `make_profile`). W1 is the caller's workspace unless a card says otherwise.
- MISSING = `999999999`. T0 = `datetime(2025, 12, 1, 8, 0, 0)` (naive). SFX = `str(os.getpid())`, the per-process suffix.
- Window dates: BEFORE = `date(2030, 3, 9)`, START = `date(2030, 3, 10)`, MID = `date(2030, 3, 15)`, END = `date(2030, 3, 20)`, AFTER = `date(2030, 3, 21)`. Helper date: TODAY = `date(2030, 6, 15)`; TD(n) = `TODAY + timedelta(days=n)`.

**Externals.** None is mocked. Nothing patches the clock.

**Standing rows.** In every test, in this order, no Given line needed; `is_active True`, `is_deleted False`.
- Factories (`workspace_id`, `name`, `abbreviation`): F0 W0 `"Zero Works"` / `"ZW"`. F1 W1 `"Main Plant"` / `"MP"`. F2 W1 `"North Yard"` / `"NY"`. F9 W2 `"Far Depot"` / `"FR"`.
- Types: WT0 = `WorkOrderType(workspace_id=W0.id, name="Zero Repair")`. WT1 = `WorkOrderType(workspace_id=W1.id, name="Repair")`. WT9 = `WorkOrderType(workspace_id=W2.id, name="Far Repair")`.

**Given rows.** Built directly, flushed one at a time in the order written, so ids within one table rise in that order. A Given line written as code is a step to run exactly.
- **machine** = `Machine(workspace_id=W1.id, factory_id=F1.id, name=<card>)`; `is_active True`, `is_deleted False` by default. Recipes: **M0** `"Zero Press"`, `workspace_id W0.id`, `factory_id F0.id`. **M1** `"Lathe"`. **M2** `"Press"`. **M3** `"Drill"`, `factory_id F2.id`. **M9** `"Grinder"`, `workspace_id W2.id`, `factory_id F9.id`. **MX** `"Old Saw"`, gone.
- **gone** (after "but", or in a recipe) = `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id` (for a factory, section or type: `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`). Spec Notes G1: only `is_deleted` is read; `deleted_at`, `deleted_by` and `is_active` change nothing, so they are set for realism only (MWS-CR-26 pins that `is_deleted` alone is enough). The only extra NOT NULL column without a default is `factories.abbreviation`, which every Factory here sets; `created_by` is nullable and never set.
- **order L of M** = `WorkOrder(workspace_id=W1.id, work_order_number="WO-" + "L" + "-" + SFX, work_order_type_id=WT1.id, title="Service", factory_id=F1.id, machine_id=M.id, planned_date=MID, status="DRAFT")`, where L is the label the line gives (`order O1 of M1` → number `"WO-O1-" + SFX`). After "but" the card lists every column that differs. **zero order L of M** = the same, but `workspace_id W0.id`, `work_order_type_id WT0.id`, `factory_id F0.id`. **far order L of M** = the same, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
- **link of M to S** = `MachineSectionAssignment(workspace_id=W1.id, machine_id=M.id, factory_section_id=S.id)`; then `db.expire_all()`.
- **commit point** = after the last Given line the test runs `db.commit()` (a savepoint release under the `db` fixture). A line marked "(after the commit point)" runs after it and stays uncommitted; "flushed" or "not flushed" as it says.

**Named checks.**
- **pairs(x)** = `{(o.id, m.id) for (o, m) in x}`. **oids(x)** = `{o.id for (o, m) in x}`. `count:` lines count with a fresh query, filter stated. **re-read X** = `db.expire_all()`, then SELECT X by id.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each then re-reads or counts with a fresh query.
- **sql_log** = a list filled by a `before_cursor_execute` listener on `db.connection()`, started at that Given line, removed after the call; each entry is the statement text. `statement:` lines check it.
- `raises: <Type>`: `with pytest.raises(<Type>) as exc:` around the call; further `raises:` lines assert on `exc.value` after the block.

**xfail cards.** Write the call and checks as shown. `pytest.mark.xfail(strict=True, reason="BUG-NNN")`; every xfail card here is strict.

**Race simulations.** None.

## `MachineWorkService.collect_raw_items`

### MWS-CR-01 — an open dated order on a live machine is returned with its machine
- **Rules:** `collect_raw_items` R1, Returns (G4)
- **Kind:** happy
- **Expect:** pass
- **Note:** the items are SQLAlchemy `Row`s, not `tuple`s (spec G4): no tuple type check; only what callers rely on.

**Given**
1. M1.
2. order O1 of M1.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `len(result) == 1`.
3. returns: `wo, machine = result[0]` unpacks; `wo.id == O1.id`, `machine.id == M1.id`.
4. returns: `result[0][0] is wo`, `result[0][1] is machine` (indexing).
5. returns: `len(result[0]) == 2`.
6. returns: `result[0] == (wo, machine)`.
7. returns: `isinstance(wo, WorkOrder)`, `isinstance(machine, Machine)`.
8. returns: `pairs(result) == {(O1.id, M1.id)}`.

### MWS-CR-02 — the window includes start and end, not the days outside
- **Rules:** `collect_raw_items` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. order OA of M1, but `planned_date AFTER`.
3. order OE of M1, but `planned_date END`.
4. order OS of M1, but `planned_date START`.
5. order OB of M1, but `planned_date BEFORE`.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `oids(result) == {OE.id, OS.id}`.

### MWS-CR-03 — end before start gives []
- **Rules:** `collect_raw_items` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. order OS of M1, but `planned_date START`.
3. order OM of M1, but `planned_date MID`.
4. order OE of M1, but `planned_date END`.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=END, end=START)`.

**Then**
1. returns: `result == []`.

### MWS-CR-04 — start equal to end keeps that one day
- **Rules:** `collect_raw_items` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. order OM of M1, but `planned_date MID`.
3. order ON of M1, but `planned_date date(2030, 3, 16)`.
4. order OP of M1, but `planned_date date(2030, 3, 14)`.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=MID, end=MID)`.

**Then**
1. returns: `oids(result) == {OM.id}`.

### MWS-CR-05 — default statuses are DRAFT and IN_PROGRESS only
- **Rules:** `collect_raw_items` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. order OD of M1.
3. order OP of M1, but `status "IN_PROGRESS"`.
4. order OC of M1, but `status "COMPLETED"`.
5. order OV of M1, but `status "VOIDED"`.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `oids(result) == {OD.id, OP.id}`.

### MWS-CR-06 — default statuses match the stored text exactly
- **Rules:** `collect_raw_items` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. order OK of M1.
3. order O1 of M1, but `status "draft"`.
4. order O2 of M1, but `status " DRAFT"`.
5. order O3 of M1, but `status "DRAF"`.
6. order O4 of M1, but `status "INXPROGRESS"`.
7. order O5 of M1, but `status "IN_PROGRESS_X"`.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `oids(result) == {OK.id}`.

### MWS-CR-07 — given statuses match exactly on the argument side
- **Rules:** `collect_raw_items` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. order OP of M1, but `status "IN_PROGRESS"`.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END, statuses=["in_progress", " IN_PROGRESS", "IN_PROG", "IN%", "IN_PROGRES_"])`.

**Then**
1. returns: `result == []`.

### MWS-CR-08 — statuses=["IN_PROGRESS"] matches IN_PROGRESS only
- **Rules:** `collect_raw_items` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1.
2. order OD of M1.
3. order OP of M1, but `status "IN_PROGRESS"`.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END, statuses=["IN_PROGRESS"])`.

**Then**
1. returns: `oids(result) == {OP.id}`.

### MWS-CR-09 — statuses=[] gives []
- **Rules:** `collect_raw_items` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. order OD of M1.
3. order OP of M1, but `status "IN_PROGRESS"`.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END, statuses=[])`.

**Then**
1. returns: `result == []`.

### MWS-CR-10 — an unknown status raises nothing and matches nothing
- **Rules:** `collect_raw_items` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. order OD of M1.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END, statuses=["NOPE"])`.

**Then**
1. returns: `result == []`.

### MWS-CR-11 — given statuses replace the defaults
- **Rules:** `collect_raw_items` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1.
2. order OD of M1.
3. order OC of M1, but `status "COMPLETED"`.
4. order OV of M1, but `status "VOIDED"`.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END, statuses=["COMPLETED", "VOIDED"])`.

**Then**
1. returns: `oids(result) == {OC.id, OV.id}`.

### MWS-CR-12 — soft-deleted, undated and machine-less orders are never returned
- **Rules:** `collect_raw_items` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1.
2. order OX of M1, but `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.
3. order ON of M1, but `planned_date None`.
4. order OM of M1, but `machine_id None`.
5. order OK of M1.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END, statuses=["DRAFT"])`.

**Then**
1. returns: `oids(result) == {OK.id}`.

### MWS-CR-13 — a soft-deleted machine's orders are left out; an inactive machine's are kept
- **Rules:** `collect_raw_items` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MX.
2. MI = machine, but `name "Idle Mill"`, `is_active False`.
3. order OX of MX.
4. order OI of MI.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `pairs(result) == {(OI.id, MI.id)}`.

### MWS-CR-14 — orders of W0 and W2 are never returned to W1
- **Rules:** `collect_raw_items` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M0.
2. M1.
3. M9.
4. zero order Z0 of M0.
5. order O1 of M1.
6. far order Z9 of M9.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `pairs(result) == {(O1.id, M1.id)}`.

### MWS-CR-15 — BUG-1571: a W1 order naming W2's machine is left out
- **Rules:** `collect_raw_items` R4 [BUG-1571]
- **Kind:** bug
- **Expect:** xfail BUG-1571
- **Fails today on:** Then 1 (the order on M9 is returned with M9)

**Given**
1. M1.
2. M9.
3. order O1 of M1.
4. order OS of M9.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `pairs(result) == {(O1.id, M1.id)}`.
2. returns: `M9.id not in {m.id for (o, m) in result}`.

### MWS-CR-16 — BUG-1571: a W1 order naming W0's machine (lower id) is left out
- **Rules:** `collect_raw_items` R4 [BUG-1571]
- **Kind:** bug
- **Expect:** xfail BUG-1571
- **Fails today on:** Then 1 (the order on M0 is returned with M0)

**Given**
1. M0.
2. M1.
3. order OS of M0.
4. order O1 of M1.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `pairs(result) == {(O1.id, M1.id)}`.
2. returns: `M0.id not in {m.id for (o, m) in result}`.

### MWS-CR-17 — seen from the machine's own workspace, the other workspace's order is not returned
- **Rules:** `collect_raw_items` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M9.
2. order OS of M9.
3. far order Z9 of M9.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W2.id, start=START, end=END)`.

**Then**
1. returns: `pairs(result) == {(Z9.id, M9.id)}`.

### MWS-CR-18 — a live machine of a soft-deleted factory is returned with its orders
- **Rules:** `collect_raw_items` R5 (D2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD = `Factory(workspace_id=W1.id, name="Closed Mill", abbreviation="CM")`, but gone.
2. MF = machine, but `name "Kiln"`, `factory_id FD.id`.
3. order OF of MF, but `factory_id FD.id`.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `pairs(result) == {(OF.id, MF.id)}`.

### MWS-CR-19 — factory_id is compared with the order's factory, lower and higher ids left out
- **Rules:** `collect_raw_items` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. FA = `Factory(workspace_id=W1.id, name="Alpha Works", abbreviation="AW")`.
2. FB = `Factory(workspace_id=W1.id, name="Beta Works", abbreviation="BW")`.
3. FC = `Factory(workspace_id=W1.id, name="Gamma Works", abbreviation="GW")`.
4. MA = machine, but `name "Ax"`, `factory_id FA.id`.
5. MB = machine, but `name "Bx"`, `factory_id FB.id`.
6. MC = machine, but `name "Cx"`, `factory_id FC.id`.
7. order OA of MA, but `factory_id FA.id`.
8. order OB of MC, but `factory_id FB.id`.
9. order OC of MB, but `factory_id FC.id`.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END, factory_id=FB.id)`.

**Then**
1. returns: `pairs(result) == {(OB.id, MC.id)}`.

### MWS-CR-20 — factory_id=None filters nothing
- **Rules:** `collect_raw_items` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1.
2. M3.
3. order O1 of M1.
4. order O3 of M3, but `factory_id F2.id`.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END, factory_id=None)`.

**Then**
1. returns: `oids(result) == {O1.id, O3.id}`.

### MWS-CR-21 — machine_ids keeps only those machines, lower and higher ids left out
- **Rules:** `collect_raw_items` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MA = machine, but `name "Ax"`.
2. MB = machine, but `name "Bx"`.
3. MC = machine, but `name "Cx"`.
4. order OA of MA.
5. order OB of MB.
6. order OC of MC.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END, machine_ids=[MB.id])`.

**Then**
1. returns: `pairs(result) == {(OB.id, MB.id)}`.

### MWS-CR-22 — an unknown machine id matches nothing and raises nothing
- **Rules:** `collect_raw_items` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. order O1 of M1.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END, machine_ids=[MISSING])`.

**Then**
1. returns: `result == []`.

### MWS-CR-23 — machine_ids=[] gives []
- **Rules:** `collect_raw_items` R6, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. order O1 of M1.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END, machine_ids=[])`.

**Then**
1. returns: `result == []`.

### MWS-CR-24 — the query takes no row lock
- **Rules:** `collect_raw_items` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1.
2. order O1 of M1.
3. sql_log starts here (after the commit point).

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `oids(result) == {O1.id}`.
2. statement: `len(sql_log) >= 1`.
3. statement: `all("FOR UPDATE" not in s.upper() for s in sql_log)`.

### MWS-CR-25 — collect_raw_items neither commits nor rolls back
- **Rules:** `collect_raw_items` R7; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = M1.
2. B = M2.
3. order O1 of A.
4. P = machine, but `name "Pending"` (after the commit point, flushed).
5. `B.name = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END)`, inside **spies**.

**Then**
1. returns: `pairs(result) == {(O1.id, A.id)}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db`.
5. session: `B in db.dirty`.
6. session: `len(db.dirty) == 1`.
7. committed: `machines` rows with `name == "Pending"`: exactly 0.
8. committed: re-read B: `name == "Press"`.

### MWS-CR-26 — a machine with only is_deleted set is left out; deleted_at and is_active are not needed
- **Rules:** `collect_raw_items` R3 (Notes G1)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MD = machine, but `name "Half Gone"`, `is_deleted True` (`is_active True`, `deleted_at None`, `deleted_by None`).
2. M1.
3. order OD of MD.
4. order O1 of M1.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `pairs(result) == {(O1.id, M1.id)}`.
2. returns: `MD.id not in {m.id for (o, m) in result}`.

### MWS-CR-27 — the machine's section assignment and its section are loaded by the query
- **Rules:** `collect_raw_items` Returns (Notes G2)
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = `FactorySection(workspace_id=W1.id, factory_id=F2.id, name="Cutting")`.
2. M3.
3. M1.
4. link of M3 to S1.
5. order O3 of M3.
6. order O1 of M1.
7. `db.expire_all()` (after the commit point), so no relationship is loaded before the call.

**When**
- `result = svc.collect_raw_items(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `pairs(result) == {(O3.id, M3.id), (O1.id, M1.id)}`.
2. returns: with `ma` = the machine paired with O3 and `mb` = the machine paired with O1 (from `result`), and `from sqlalchemy import inspect`: `"section_assignment" not in inspect(ma).unloaded`.
3. returns: `"section_assignment" not in inspect(mb).unloaded` (checked before any attribute of `mb` is read).
4. returns: `"factory_section" not in inspect(ma.section_assignment).unloaded`.
5. returns: `ma.section_assignment.factory_section.id == S1.id`, `ma.section_assignment.factory_section.name == "Cutting"`.
6. returns: `mb.section_assignment is None`.

## `MachineWorkService.upcoming_work`

### MWS-UW-01 — no order gives []
- **Rules:** `upcoming_work` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M2.

**When**
- `result = svc.upcoming_work(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `result == []`.

### MWS-UW-02 — the window and the default open statuses reach the query
- **Rules:** `upcoming_work` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. order OB of M1, but `planned_date BEFORE`.
3. order OS of M1, but `planned_date START`.
4. order OE of M1, but `planned_date END`, `status "IN_PROGRESS"`.
5. order OA of M1, but `planned_date AFTER`.
6. order OC of M1, but `status "COMPLETED"`.

**When**
- `result = svc.upcoming_work(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `isinstance(result[0], MachineUpcomingWorkRow)`.
3. returns: `[i.source_id for i in result[0].items] == [OS.id, OE.id]`.

### MWS-UW-03 — factory_id filters on the order's factory; the row shows the machine's factory
- **Rules:** `upcoming_work` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M3.
3. order O1 of M1, but `factory_id F2.id`.
4. order O3 of M3, but `factory_id F1.id`.

**When**
- `result = svc.upcoming_work(db, workspace_id=W1.id, start=START, end=END, factory_id=F2.id)`.

**Then**
1. returns: `[r.machine_id for r in result] == [M1.id]`.
2. returns: `result[0].factory_id == F1.id`.
3. returns: `[i.source_id for i in result[0].items] == [O1.id]`.

### MWS-UW-04 — machine_ids reaches the query
- **Rules:** `upcoming_work` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MA = machine, but `name "Ax"`.
2. MB = machine, but `name "Bx"`.
3. MC = machine, but `name "Cx"`.
4. order OA of MA.
5. order OB of MB.
6. order OC of MC.

**When**
- `result = svc.upcoming_work(db, workspace_id=W1.id, start=START, end=END, machine_ids=[MB.id])`.

**Then**
1. returns: `[r.machine_id for r in result] == [MB.id]`.

### MWS-UW-05 — one row per machine; count and sources equal its number of orders
- **Rules:** `upcoming_work` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1.
2. M2.
3. order O1 of M1, but `planned_date START`.
4. order O2 of M2, but `planned_date START`.
5. order O3 of M1, but `planned_date START`.
6. order O4 of M1, but `planned_date START`.

**When**
- `result = svc.upcoming_work(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `[r.machine_id for r in result] == [M1.id, M2.id]`.
2. returns: `result[0].count == 3`, `result[0].sources.work_orders == 3`, `len(result[0].items) == 3`.
3. returns: `result[1].count == 1`, `result[1].sources.work_orders == 1`, `len(result[1].items) == 1`.

### MWS-UW-06 — the row shows the machine's name, factory and section; no section gives None
- **Rules:** `upcoming_work` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = `FactorySection(workspace_id=W1.id, factory_id=F2.id, name="Cutting")`.
2. M3.
3. M1.
4. link of M3 to S1.
5. order O3 of M3, but `planned_date START`.
6. order O1 of M1, but `planned_date END`.

**When**
- `result = svc.upcoming_work(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `[r.machine_id for r in result] == [M3.id, M1.id]`.
2. returns: `result[0].name == "Drill"`, `result[0].factory_id == F2.id`.
3. returns: `result[0].factory_section_id == S1.id`, `result[0].section_name == "Cutting"`.
4. returns: `result[1].name == "Lathe"`, `result[1].factory_id == F1.id`.
5. returns: `result[1].factory_section_id is None`, `result[1].section_name is None`.

### MWS-UW-07 — a soft-deleted section is still shown
- **Rules:** `upcoming_work` R3 (D3)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. SX = `FactorySection(workspace_id=W1.id, factory_id=F1.id, name="Line B")`, but gone.
2. M1.
3. link of M1 to SX.
4. order O1 of M1.

**When**
- `result = svc.upcoming_work(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].factory_section_id == SX.id`, `result[0].section_name == "Line B"`.

### MWS-UW-08 — each order is one item with its own values; an empty title shows the number
- **Rules:** `upcoming_work` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. WT2 = `WorkOrderType(workspace_id=W1.id, name="Servicing")`.
2. M1.
3. order O1 of M1, but `planned_date START`, `title "Belt check"`.
4. order O2 of M1, but `planned_date MID`, `title ""`, `status "IN_PROGRESS"`, `work_order_type_id WT2.id`.

**When**
- `result = svc.upcoming_work(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `[i.kind for i in result[0].items] == ["work_order", "work_order"]`.
3. returns: `[i.source_id for i in result[0].items] == [O1.id, O2.id]`.
4. returns: `[i.date for i in result[0].items] == [START, MID]`.
5. returns: `[i.title for i in result[0].items] == ["Belt check", "WO-O2-" + SFX]`.
6. returns: `[i.status for i in result[0].items] == ["DRAFT", "IN_PROGRESS"]`.
7. returns: `[i.work_order_type_name for i in result[0].items] == ["Repair", "Servicing"]`.

### MWS-UW-09 — a soft-deleted work order type's name is still shown
- **Rules:** `upcoming_work` R4 (D4)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. WTX = `WorkOrderType(workspace_id=W1.id, name="Servicing")`, but gone.
2. M1.
3. order O1 of M1, but `work_order_type_id WTX.id`.

**When**
- `result = svc.upcoming_work(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `[i.work_order_type_name for i in result[0].items] == ["Servicing"]`.

### MWS-UW-10 — items sort by date then order id; earliest_date is the smallest date
- **Rules:** `upcoming_work` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. order OA of M1, but `planned_date END`.
3. order OB of M1, but `planned_date START`.
4. order OC of M1, but `planned_date MID`.
5. order OD of M1, but `planned_date START`.

**When**
- `result = svc.upcoming_work(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `[i.source_id for i in result[0].items] == [OB.id, OD.id, OC.id, OA.id]`.
3. returns: `result[0].earliest_date == START`.

### MWS-UW-11 — rows sort by earliest date, then name ignoring case, then machine id
- **Rules:** `upcoming_work` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X1 = machine, but `name "gamma"`.
2. X2 = machine, but `name "Beta"`.
3. X3 = machine, but `name "Gamma"`, `factory_id F2.id`.
4. X4 = machine, but `name "alpha"`.
5. X5 = machine, but `name "Zed"`.
6. order A1 of X1, but `planned_date MID`.
7. order A2 of X2, but `planned_date date(2030, 3, 12)`.
8. order A3 of X3, but `planned_date MID`.
9. order A4 of X4, but `planned_date date(2030, 3, 12)`.
10. order A5 of X5, but `planned_date END`.
11. order A6 of X5, but `planned_date START`.

**When**
- `result = svc.upcoming_work(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `[r.name for r in result] == ["Zed", "alpha", "Beta", "gamma", "Gamma"]`.
2. returns: `[r.machine_id for r in result] == [X5.id, X4.id, X2.id, X1.id, X3.id]`.
3. returns: `[r.earliest_date for r in result] == [START, date(2030, 3, 12), date(2030, 3, 12), MID, MID]`.

### MWS-UW-12 — every row is returned, 101 machines give 101 rows
- **Rules:** `upcoming_work` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 machines, named `"P00000"` … `"P00100"` (`"P" + str(n).zfill(5)` for n in 0…100), each = machine, but that `name`.
2. for each of them, in the same order, order L of it, with L = `"N" + str(n)`.

**When**
- `result = svc.upcoming_work(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `result[0].name == "P00000"`, `result[100].name == "P00100"`.

### MWS-UW-13 — BUG-1572: a live machine of a soft-deleted factory is left out with its orders
- **Rules:** `upcoming_work` R6 [BUG-1572]
- **Kind:** bug
- **Expect:** xfail BUG-1572
- **Fails today on:** Then 1 ("Kiln" is listed)

**Given**
1. FD = `Factory(workspace_id=W1.id, name="Closed Mill", abbreviation="CM")`, but gone.
2. MF = machine, but `name "Kiln"`, `factory_id FD.id`.
3. M1.
4. order OF of MF, but `factory_id FD.id`.
5. order O1 of M1.

**When**
- `result = svc.upcoming_work(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `[r.machine_id for r in result] == [M1.id]`.
2. returns: `"Kiln" not in [r.name for r in result]`.

### MWS-UW-14 — BUG-1571: a W1 order on W2's machine is left out; nothing of W2 shown
- **Rules:** `upcoming_work` R1 via `collect_raw_items` R4 [BUG-1571]
- **Kind:** bug
- **Expect:** xfail BUG-1571
- **Fails today on:** Then 1 (M9 "Grinder" is listed)

**Given**
1. M1.
2. M9.
3. order O1 of M1, but `planned_date END`.
4. order OS of M9, but `planned_date START`.

**When**
- `result = svc.upcoming_work(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `[r.machine_id for r in result] == [M1.id]`.
2. returns: `"Grinder" not in [r.name for r in result]`.
3. returns: `F9.id not in [r.factory_id for r in result]`.

### MWS-UW-15 — an inactive but live factory hides nothing
- **Rules:** `upcoming_work` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. FI = `Factory(workspace_id=W1.id, name="Quiet Plant", abbreviation="QP")`, but `is_active False`.
2. MQ = machine, but `name "Quill"`, `factory_id FI.id`.
3. order OQ of MQ, but `factory_id FI.id`.

**When**
- `result = svc.upcoming_work(db, workspace_id=W1.id, start=START, end=END)`.

**Then**
1. returns: `[r.machine_id for r in result] == [MQ.id]`.
2. returns: `result[0].factory_id == FI.id`.

### MWS-UW-16 — upcoming_work neither commits nor rolls back
- **Rules:** `upcoming_work` R7; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = M1.
2. B = M2.
3. order O1 of A.
4. P = machine, but `name "Pending"` (after the commit point, flushed).
5. `B.name = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.upcoming_work(db, workspace_id=W1.id, start=START, end=END)`, inside **spies**.

**Then**
1. returns: `[r.machine_id for r in result] == [A.id]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db`.
5. session: `B in db.dirty`.
6. session: `len(db.dirty) == 1`.
7. committed: `machines` rows with `name == "Pending"`: exactly 0.
8. committed: re-read B: `name == "Press"`.

## `MachineWorkService.dates_by_machine`

### MWS-DM-01 — machine_ids=[] gives {} without reading the database
- **Rules:** `dates_by_machine` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. order O1 of M1.
3. sql_log starts here (after the commit point).

**When**
- `result = svc.dates_by_machine(db, workspace_id=W1.id, machine_ids=[], start=START, end=END)`.

**Then**
1. returns: `result == {}`.
2. statement: `sql_log == []`.

### MWS-DM-02 — an empty generator gives {} without reading the database
- **Rules:** `dates_by_machine` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. order O1 of M1.
3. sql_log starts here (after the commit point).

**When**
- `result = svc.dates_by_machine(db, workspace_id=W1.id, machine_ids=(i for i in []), start=START, end=END)`.

**Then**
1. returns: `result == {}`.
2. statement: `sql_log == []`.

### MWS-DM-03 — one date per order, duplicates kept, each list ascending whatever order the rows come back in
- **Rules:** `dates_by_machine` R2
- **Kind:** happy
- **Expect:** pass
- **Note:** (Revision 3a, verifier observation) the insertion order, and so the id order, of each machine's orders is chosen so that no row order the database could use without sorting by date gives sorted lists. M1 is inserted in descending date order, M2 in ascending order, and M3 out of order (MID, START, END), which is unsorted read either forwards or backwards. A missing sort therefore leaves at least one list unsorted, whether the rows come back in insertion or id order, forwards or backwards. Each order is flushed on its own line, so ids follow the Given order.

**Given**
1. M1.
2. M2.
3. M3.
4. order O1 of M1, but `planned_date END`.
5. order O2 of M1, but `planned_date MID`.
6. order O3 of M1, but `planned_date START`.
7. order O4 of M1, but `planned_date MID`.
8. order O5 of M2, but `planned_date START`, `status "IN_PROGRESS"`.
9. order O6 of M2, but `planned_date END`.
10. order O7 of M3, but `planned_date MID`, `factory_id F2.id`.
11. order O8 of M3, but `planned_date START`, `factory_id F2.id`.
12. order O9 of M3, but `planned_date END`, `factory_id F2.id`.

**When**
- `result = svc.dates_by_machine(db, workspace_id=W1.id, machine_ids=[M1.id, M2.id, M3.id], start=START, end=END)`.

**Then**
1. returns: `isinstance(result, dict)`.
2. returns: `result == {M1.id: [START, MID, MID, END], M2.id: [START, END], M3.id: [START, MID, END]}`.
3. returns: `all(v == sorted(v) for v in result.values())`.

### MWS-DM-04 — a generator of ids is read once and works
- **Rules:** `dates_by_machine` Inputs, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M2.
3. order O1 of M1, but `planned_date START`.
4. order O2 of M2, but `planned_date END`.

**When**
- `result = svc.dates_by_machine(db, workspace_id=W1.id, machine_ids=(i for i in [M1.id, M2.id]), start=START, end=END)`.

**Then**
1. returns: `result == {M1.id: [START], M2.id: [END]}`.

### MWS-DM-05 — the window includes start and end, not the days outside
- **Rules:** `dates_by_machine` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. order OA of M1, but `planned_date AFTER`.
3. order OE of M1, but `planned_date END`.
4. order OS of M1, but `planned_date START`.
5. order OB of M1, but `planned_date BEFORE`.

**When**
- `result = svc.dates_by_machine(db, workspace_id=W1.id, machine_ids=[M1.id], start=START, end=END)`.

**Then**
1. returns: `result == {M1.id: [START, END]}`.

### MWS-DM-06 — statuses=("IN_PROGRESS",) keeps only in-progress dates; default leaves out closed orders
- **Rules:** `dates_by_machine` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1.
2. M2.
3. order O1 of M1, but `planned_date START`, `status "IN_PROGRESS"`.
4. order O2 of M1, but `planned_date MID`.
5. order O3 of M2, but `planned_date MID`.
6. order O4 of M2, but `planned_date END`, `status "COMPLETED"`.

**When**
- `result = svc.dates_by_machine(db, workspace_id=W1.id, machine_ids=[M1.id, M2.id], start=START, end=END, statuses=("IN_PROGRESS",))`.

**Then**
1. returns: `result == {M1.id: [START]}`.

### MWS-DM-07 — unknown ids, soft-deleted machines, machines with no match and machines not asked are absent
- **Rules:** `dates_by_machine` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MX.
2. M1.
3. M2.
4. M3.
5. order OX of MX.
6. order O1 of M1.
7. order O2 of M2, but `status "COMPLETED"`.
8. order O3 of M3.

**When**
- `result = svc.dates_by_machine(db, workspace_id=W1.id, machine_ids=[MISSING, MX.id, M1.id, M2.id], start=START, end=END)`.

**Then**
1. returns: `result == {M1.id: [MID]}`.

### MWS-DM-08 — a machine of a soft-deleted factory keeps its dates
- **Rules:** `dates_by_machine` R3 (D2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD = `Factory(workspace_id=W1.id, name="Closed Mill", abbreviation="CM")`, but gone.
2. MF = machine, but `name "Kiln"`, `factory_id FD.id`.
3. order OF of MF, but `factory_id FD.id`.

**When**
- `result = svc.dates_by_machine(db, workspace_id=W1.id, machine_ids=[MF.id], start=START, end=END)`.

**Then**
1. returns: `result == {MF.id: [MID]}`.

### MWS-DM-09 — BUG-1571: another workspace's machine is absent
- **Rules:** `dates_by_machine` R3 [BUG-1571] (D1)
- **Kind:** bug
- **Expect:** xfail BUG-1571
- **Fails today on:** Then 1 (M9 is a key with the W1 order's date)

**Given**
1. M1.
2. M9.
3. order O1 of M1, but `planned_date START`.
4. order OS of M9, but `planned_date END`.

**When**
- `result = svc.dates_by_machine(db, workspace_id=W1.id, machine_ids=[M9.id, M1.id], start=START, end=END)`.

**Then**
1. returns: `result == {M1.id: [START]}`.

### MWS-DM-10 — orders of W0 and W2 on their own machines never reach W1; seen from W2 the W1 order is absent
- **Rules:** `dates_by_machine` R2, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M0.
2. M1.
3. M9.
4. zero order Z0 of M0.
5. order O1 of M1, but `planned_date START`.
6. far order Z9 of M9.

**When**
- `result = svc.dates_by_machine(db, workspace_id=W1.id, machine_ids=[M0.id, M1.id, M9.id], start=START, end=END)`.

**Then**
1. returns: `result == {M1.id: [START]}`.

### MWS-DM-11 — seen from the machine's own workspace, a W1 order on it gives no date
- **Rules:** `dates_by_machine` R3 (via `collect_raw_items` R4)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M9.
2. order OS of M9.

**When**
- `result = svc.dates_by_machine(db, workspace_id=W2.id, machine_ids=[M9.id], start=START, end=END)`.

**Then**
1. returns: `result == {}`.

### MWS-DM-12 — dates_by_machine neither commits nor rolls back
- **Rules:** `dates_by_machine` R4; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = M1.
2. B = M2.
3. order O1 of A.
4. P = machine, but `name "Pending"` (after the commit point, flushed).
5. `B.name = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.dates_by_machine(db, workspace_id=W1.id, machine_ids=[A.id, B.id], start=START, end=END)`, inside **spies**.

**Then**
1. returns: `result == {A.id: [MID]}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db`.
5. session: `B in db.dirty`.
6. session: `len(db.dirty) == 1`.
7. committed: `machines` rows with `name == "Pending"`: exactly 0.
8. committed: re-read B: `name == "Press"`.

## `MachineWorkService.earliest_upcoming_on_or_after`

### MWS-EU-01 — the earliest date on or after from_date, from an unsorted list
- **Rules:** `earliest_upcoming_on_or_after` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows.

**When**
- `result = MachineWorkService.earliest_upcoming_on_or_after([TD(5), TD(-3), TD(2), TD(9)], TODAY)`.

**Then**
1. returns: `result == TD(2)`.

### MWS-EU-02 — a date equal to from_date counts
- **Rules:** `earliest_upcoming_on_or_after` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows.

**When**
- `result = MachineWorkService.earliest_upcoming_on_or_after([TD(4), TD(0), TD(-1)], TODAY)`.

**Then**
1. returns: `result == TODAY`.

### MWS-EU-03 — only earlier dates give None
- **Rules:** `earliest_upcoming_on_or_after` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows.

**When**
- `result = MachineWorkService.earliest_upcoming_on_or_after([TD(-1), TD(-10)], TODAY)`.

**Then**
1. returns: `result is None`.

### MWS-EU-04 — an empty list gives None
- **Rules:** `earliest_upcoming_on_or_after` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows.

**When**
- `result = MachineWorkService.earliest_upcoming_on_or_after([], TODAY)`.

**Then**
1. returns: `result is None`.

## `MachineWorkService.has_overdue`

### MWS-HO-01 — a date strictly before today is overdue
- **Rules:** `has_overdue` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows.

**When**
- `result = MachineWorkService.has_overdue([TD(3), TD(-1)], TODAY)`.

**Then**
1. returns: `result is True`.

### MWS-HO-02 — today itself and later dates are not overdue
- **Rules:** `has_overdue` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows.

**When**
- `result = MachineWorkService.has_overdue([TD(0), TD(3)], TODAY)`.

**Then**
1. returns: `result is False`.

### MWS-HO-03 — an empty list is not overdue
- **Rules:** `has_overdue` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows.

**When**
- `result = MachineWorkService.has_overdue([], TODAY)`.

**Then**
1. returns: `result is False`.

## `MachineWorkService.has_upcoming_in_horizon`

### MWS-HH-01 — horizon 7: today + 7 counts
- **Rules:** `has_upcoming_in_horizon` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows.

**When**
- `result = MachineWorkService.has_upcoming_in_horizon([TD(7)], TODAY, 7)`.

**Then**
1. returns: `result is True`.

### MWS-HH-02 — horizon 7: today + 8 and a past date do not count
- **Rules:** `has_upcoming_in_horizon` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows.

**When**
- `result = MachineWorkService.has_upcoming_in_horizon([TD(8), TD(-1)], TODAY, 7)`.

**Then**
1. returns: `result is False`.

### MWS-HH-03 — horizon 7: today itself counts
- **Rules:** `has_upcoming_in_horizon` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows.

**When**
- `result = MachineWorkService.has_upcoming_in_horizon([TD(30), TD(0)], TODAY, 7)`.

**Then**
1. returns: `result is True`.

### MWS-HH-04 — an empty list is False
- **Rules:** `has_upcoming_in_horizon` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows.

**When**
- `result = MachineWorkService.has_upcoming_in_horizon([], TODAY, 30)`.

**Then**
1. returns: `result is False`.

### MWS-HH-05 — horizon 0: today counts
- **Rules:** `has_upcoming_in_horizon` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows.

**When**
- `result = MachineWorkService.has_upcoming_in_horizon([TD(0)], TODAY, 0)`.

**Then**
1. returns: `result is True`.

### MWS-HH-06 — horizon 0: tomorrow and yesterday do not count
- **Rules:** `has_upcoming_in_horizon` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows.

**When**
- `result = MachineWorkService.has_upcoming_in_horizon([TD(1), TD(-1)], TODAY, 0)`.

**Then**
1. returns: `result is False`.

### MWS-HH-07 — a negative horizon is False, even for today
- **Rules:** `has_upcoming_in_horizon` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows.

**When**
- `result = MachineWorkService.has_upcoming_in_horizon([TD(0), TD(-1)], TODAY, -1)`.

**Then**
1. returns: `result is False`.

### MWS-HH-08 — a horizon past the last representable date raises ValueError, not wrapped
- **Rules:** `has_upcoming_in_horizon` R3; TC6 (error not wrapped)
- **Kind:** error
- **Expect:** pass

**Given**
1. No rows.

**When**
- `MachineWorkService.has_upcoming_in_horizon([TODAY], TODAY, 10**7)`.

**Then**
1. raises: `ValueError`.
2. raises: `type(exc.value) is ValueError`.
3. raises: `"out of range" in str(exc.value)` (a "contains" check, as spec R3 / Notes G3 fix it: the year in the text varies with `today`).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `dates_by_machine` callers' statuses and helper horizons (default statuses, `("IN_PROGRESS",)` for overdue, horizons 7 and 30; BUG-973 date limits) | `MachineManager.search_machines` (machine manager spec R8–R17) | That the manager passes only its own workspace's machine ids and the right statuses/horizons; overdue counts only `IN_PROGRESS` (owner O2). |
| Window derived from `within_days` / `include_overdue`, `machine_ids` never passed | `MachineService.get_upcoming_work` (`GET /machines/upcoming-work/`) | The start/end the service passes (already in `machine_service.cases.md` MCS-W-01 … W-05). |

## Spec gaps
None. Closed in Revisions 2 and 3 (2026-11-22) by the spec's Gap log:
| # | Resolution | Cards |
|---|---|---|
| 1 | Notes G1: only `is_deleted` is read on work orders, machines and factories; `deleted_at` / `deleted_by` / `is_active` change nothing; only `factories.abbreviation` is an extra NOT NULL column (`created_by` nullable). | **gone** note updated; MWS-CR-26 added. Existing cards unchanged. |
| 2 | Returns + Notes G2: `Machine.section_assignment` and `MachineSectionAssignment.factory_section`, checked with `sqlalchemy.inspect(...).unloaded`. | MWS-CR-27 added. |
| 3 | R3 + Notes G3: assert `ValueError` and that the message contains `out of range`. | MWS-HH-08 Then 3 note updated; checks unchanged. |
| 4 (Rev 3) | Returns + G4: items are `Row`s; callers rely on indexing, unpacking, length 2 and equality with the plain tuple. | MWS-CR-01 Then 3–7 rewritten; tuple type check removed. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `collect_raw_items` | Returns (G2, G4) | MWS-CR-01, MWS-CR-27 |
| `collect_raw_items` | R1 | MWS-CR-01, MWS-CR-02, MWS-CR-03, MWS-CR-04, MWS-CR-05, MWS-CR-11, MWS-CR-12, MWS-CR-14 |
| `collect_raw_items` | R2 | MWS-CR-06, MWS-CR-07, MWS-CR-08, MWS-CR-09, MWS-CR-10, MWS-CR-11, MWS-CR-23 |
| `collect_raw_items` | R3 (G1) | MWS-CR-13, MWS-CR-26 |
| `collect_raw_items` | R4 [BUG-1571] | MWS-CR-15, MWS-CR-16 (xfail); MWS-CR-17 (pass) |
| `collect_raw_items` | R5 (D2) | MWS-CR-18 |
| `collect_raw_items` | R6 | MWS-CR-19, MWS-CR-20, MWS-CR-21, MWS-CR-22, MWS-CR-23 |
| `collect_raw_items` | R7; TC6 | MWS-CR-24, MWS-CR-25 |
| `collect_raw_items` | Errors: none | — |
| `upcoming_work` | R1 | MWS-UW-01, MWS-UW-02, MWS-UW-03, MWS-UW-04; BUG-1571 via R4: MWS-UW-14 (xfail) |
| `upcoming_work` | R2 | MWS-UW-05 |
| `upcoming_work` | R3 (D3) | MWS-UW-03, MWS-UW-06, MWS-UW-07 |
| `upcoming_work` | R4 (D4) | MWS-UW-08, MWS-UW-09 |
| `upcoming_work` | R5 | MWS-UW-10, MWS-UW-11, MWS-UW-12 |
| `upcoming_work` | R6 [BUG-1572] | MWS-UW-13 (xfail); MWS-UW-15 (pass) |
| `upcoming_work` | R7; TC6 | MWS-UW-16 |
| `dates_by_machine` | R1 | MWS-DM-01, MWS-DM-02 |
| `dates_by_machine` | R2, Inputs | MWS-DM-03, MWS-DM-04, MWS-DM-05, MWS-DM-06, MWS-DM-10 |
| `dates_by_machine` | R3 (D2) | MWS-DM-06, MWS-DM-07, MWS-DM-08, MWS-DM-11 |
| `dates_by_machine` | R3 [BUG-1571] (D1) | MWS-DM-09 (xfail); MWS-DM-10, MWS-DM-11 (pass) |
| `dates_by_machine` | R4; TC6 | MWS-DM-12 |
| `earliest_upcoming_on_or_after` | R1 | MWS-EU-01, MWS-EU-02 |
| `earliest_upcoming_on_or_after` | R2 | MWS-EU-03, MWS-EU-04 |
| `has_overdue` | R1 | MWS-HO-01, MWS-HO-02, MWS-HO-03 |
| `has_upcoming_in_horizon` | R1 | MWS-HH-01, MWS-HH-02, MWS-HH-03, MWS-HH-04 |
| `has_upcoming_in_horizon` | R2 | MWS-HH-05, MWS-HH-06, MWS-HH-07 |
| `has_upcoming_in_horizon` | R3; TC6 (not wrapped) | MWS-HH-08 |
| Transaction contract | TC1–TC5 | not applicable (read-only service, spec Form) |
| Transaction contract | TC6 | MWS-CR-25, MWS-UW-16, MWS-DM-12, MWS-HH-08 |
| BUG tags | BUG-1571 | MWS-CR-15, MWS-CR-16, MWS-UW-14, MWS-DM-09 |
| BUG tags | BUG-1572 | MWS-UW-13 |
