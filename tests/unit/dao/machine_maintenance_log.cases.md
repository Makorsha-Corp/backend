# Test cases — `app/dao/machine_maintenance_log.py`

> **Spec:** `tests/unit/dao/machine_maintenance_log.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-10-31; nothing open). P1, P2, P3, Q1, Q2 were decided by Claude under the reviewer's delegation; none is the owner's own answer.
> **Revision:** 1 — the spec did not change. Additive, from `machine_maintenance_log.verify.md`: Finding 1 → MML-GW-26, GM-24, GT-23, GP-26; Finding 2 → MML-SD-12; Finding 3 → MML-GM-25, GT-24, GP-27; Finding 4 → MML-GT-25; Finding 5 → MML-SD-13, RS-10 (Spec gap 1 closed); Finding 6 → MML-INH-45; the verifier's `factory_active` judgment call → MML-GI-10, GM-26, GP-28. No existing card, Convention or ID changed, none retired. (MML-RS-03's `db.refresh(A)` Given dates from the executor's run, DISCREPANCY-1 in the notes.)
> **Counts:** 183 cases · 165 expected-to-pass · 18 expected-to-fail (bugs) · 14 deferred

## Reviewer summary
- **Per callable:** `get_by_workspace` 26 (5 bug) · `get_by_id_and_workspace` 10 (1 bug) · `get_by_machine` 26 (3 bug) · `get_by_type` 25 (4 bug) · `get_by_machine_and_type` 28 (3 bug) · `soft_delete` 13 (2 bug) · `restore` 10 · `inherited` 45.
- **Expected-to-fail by bug:** BUG-1100 9 (GW-09, GW-10, GW-11, GM-10, GM-11, GT-12, GT-13, GP-15, GP-16) · BUG-1101 7 (GW-24, GW-25, GI-09, GM-20, GT-22, GT-25, GP-25) · BUG-1102 2 (SD-02, SD-05).
- **Strictness:** 13 strict, 5 non-strict (GW-09, GW-11, GM-10, GT-12, GP-15).
- **Depth:** lighter target. The module writes no stock, money or order state and its callables are thin reads and stamps. `cost` is a money column, but the DAO only passes it through; the spec's cost rules (inherited R4, R5, HR-15) get full boundary cards, both sides. No multiplication by enum value or column (inherited R3 has one card per error kind); generic base behavior is deferred to `base.cases.md`, including BUG-100 and BUG-101.
- **Notable design choices:**
  - Readers: each of the five has one "writes nothing" card with a row left pending in the session (GW-02, GI-02, GM-02, GT-02, GP-02). The same cards hold a BUG-1101 row, so "the row stays in the table" is checked by a pass card per reader.
  - Row order: date order is a plain pass card per list. Each list has one strict SQL recorder (GW-10, GM-11, GT-13, GP-16) and one non-strict tie card. Cards not about order compare sorted ids or use distinct dates, so `skip` / `limit` cards stay deterministic today.
  - GW-11 is the one card with a repeated call in its When, as a single list comprehension: "no repeats, no gaps" cannot be seen in one window.
  - Clock: `utcnow` is patched to NOW in every test, as `create=True`, so a card never patches anything. BUG-1102 is SD-02, SD-05. A fixed NOW also settles "whatever the database's `TimeZone`", so no card changes the zone.
  - Commit spy: five writers, one card each (SD-06, RS-05, INH-02, INH-38, INH-40). `remove` has one although the spec's Overview does not list it among the writers.
  - Two cards use `read:` lines after the call, so the four lists are checked once against one delete or restore.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
  - MML-SD-13, RS-10 rest on the table and column the verifier named (`machine_activity_events.machine_id`); the spec does not name them yet.
- **Needs a decision:** None blocking. See Spec gap 3 (workspace cascade).


## Conventions for this module

**IDs.** `MML` = `app/dao/machine_maintenance_log.py`. `GW` get_by_workspace · `GI` get_by_id_and_workspace · `GM` get_by_machine · `GT` get_by_type · `GP` get_by_machine_and_type · `SD` soft_delete · `RS` restore · `INH` inherited `BaseDAO` methods.

**Actors and fixed values.**
- `dao` = the singleton `machine_maintenance_log_dao` (`from app.dao.machine_maintenance_log import machine_maintenance_log_dao`). `db` = the test's real database session, always the first argument. `result` = what the When call returns.
- `MachineMaintenanceLog` = `app.models.machine_maintenance_log.MachineMaintenanceLog`. `MaintenanceTypeEnum` = `app.models.enums.MaintenanceTypeEnum`. `MachineMaintenanceLogCreate`, `MachineMaintenanceLogUpdate` = the schemas of `app.schemas.machine_maintenance_log`. `text` = `sqlalchemy.text`. `date`, `timedelta` = `datetime`. `Decimal` = `decimal.Decimal`.
- MISSING = `999999999`: an id that no row of any table has.
- D1 … D5 = `date(2026, 3, 1)` … `date(2026, 3, 5)`. T0 = `datetime(2020, 1, 2, 3, 4, 5)`. NOW = `datetime(2031, 5, 6, 7, 8, 9)` (naive).
- NEW = `{"workspace_id": W1.id, "machine_id": M1.id, "maintenance_type": MaintenanceTypeEnum.REPAIR, "maintenance_date": D1, "summary": "Bearing change"}`.

**Externals.** In every test `patch("app.dao.machine_maintenance_log.utcnow", create=True, return_value=NOW)` is active (a fixture does it; a card never patches anything itself). `create=True` because the module does not import `utcnow` today. Nothing else is mocked.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line (workspaces and profiles from `make_workspace`, `make_profile` of `tests/unit/factories.py`; the rest built directly):
  - W1, W2 = two `workspaces` rows. P1, P2 = two `profiles` rows.
  - F1 = `factories` row: `workspace_id W1.id`, `name "Factory One"`, `abbreviation "F1"`, `is_active True`, `is_deleted False`. FD = the same, but `name "Old Plant"`, `abbreviation "OP"`, `is_deleted True` (soft-deleted; `is_active` stays True). FI = the same as F1, but `name "Idle Plant"`, `abbreviation "IP"`, `is_active False` (inactive but live). F9 = the same as F1, but `name "Factory Nine"`, `abbreviation "F9"`, `workspace_id W2.id`.
  - M1 = `machines` row: `workspace_id W1.id`, `factory_id F1.id`, `name "Press 1"`, `is_active True`, `is_deleted False`. M2 = the same, but `name "Press 2"`.
  - MD = the same as M1, but `name "Press 4"`, `is_active False`, `is_deleted True` (soft-deleted). MI = the same as M1, but `name "Idle Press"`, `is_active False` (inactive but live). MF = the same as M1, but `name "Lost Press"`, `factory_id FD.id` (live, in a soft-deleted factory). MG = the same as M1, but `name "Quiet Press"`, `factory_id FI.id` (live, in an inactive factory). M9 = the same as M1, but `name "Far Press"`, `workspace_id W2.id`, `factory_id F9.id`.
- **log** = `machine_maintenance_logs` row built with `MachineMaintenanceLog`: `workspace_id W1.id`, `machine_id M1.id`, `maintenance_type MaintenanceTypeEnum.REPAIR`, `maintenance_date D1`, `summary "Bearing change"`; every other column left to its default. After the word "but" the card lists every column that differs. No log exists unless the card's Given lists it.
- **gone** (after "but") = `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by P1.id`. A column named beside it replaces that value.
- **pending log** Q = `Q = MachineMaintenanceLog(workspace_id=W1.id, machine_id=M1.id, maintenance_type=MaintenanceTypeEnum.REPAIR, maintenance_date=D1, summary="Pending")`, then `db.add(Q)`, never flushed. Row counts and snapshots for the Then lines are taken before it is added or with it still unflushed: both give the same numbers.
- A Given line written as code is a step to run exactly as written, at that place in the order.

**Named checks.**
- **ids(result)** = `[r.id for r in result]`: a list in the order returned. `sorted(ids(result)) == [A.id, B.id]` is used where the order is not part of the check; the right-hand ids are in Given order, which is ascending id order.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line; or at the Given line "Snapshot of X taken here"). **unchanged(X) except `c`, …** = the same, leaving out the columns named.
- **nothing written** = the number of `machine_maintenance_logs` rows (all workspaces) equals its value before the call.
- "(raw query)" and every `count:` line = `SELECT count(*)` through `db.scalar(text(...))`, with the filter stated. "W1 has exactly n logs" = rows with `workspace_id == W1.id`.
- A `session:` line is a check on the session object. A `read:` line calls the named `dao` reader after the When and asserts on its result.
- `raises: DataError` = `sqlalchemy.exc.DataError`; `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the call for both: `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards (the savepoint is rolled back). A negative `limit` / `skip` or a bad enum string raises when the query runs: the same wrapping applies. After a failed write, `db.refresh(row)` before reading the row. `NotNullViolation`, `ForeignKeyViolation`, `InvalidTextRepresentation`, `NumericValueOutOfRange`, `StringDataRightTruncation`, `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause` = classes of `psycopg2.errors`.
- Further `raises:` lines of the same card are assertions on `exc.value`, written after the `with` block, one `assert` per line.

**xfail cards.** Write the call and the checks exactly as shown; add `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False` on a card whose Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Rolled back.** `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()`, `db.refresh(row)` where the row still exists, and the "after the savepoint rollback" checks.

**Statement recorder.** The SQL statements sent during the When are recorded with `StatementRecorder` as in `tests/unit/managers/test_ledger_manager.py` (`before_cursor_execute` listener on the engine). `statements` = the list recorded; `sql` = the text of the one `SELECT` sent; `order_part` = the text of `sql` after `ORDER BY` (`""` when there is none). A `statement:` line is a check on these texts.

**Race simulations.** None in this module.


## `MachineMaintenanceLogDAO.get_by_workspace`

### MML-GW-01 — returns a list of the workspace's live logs
- **Rules:** `get_by_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `machine_id M2.id`, `maintenance_type MaintenanceTypeEnum.INSPECTION`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.
3. returns: `isinstance(result[0], MachineMaintenanceLog)`.

### MML-GW-02 — reading writes nothing and leaves a pending row pending
- **Rules:** `get_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.
2. X = log, but `machine_id M9.id`. (Linked to another workspace's machine on purpose.)
3. Q = pending log (Conventions): built, `db.add(Q)`, not flushed. Last line of the Given.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `A.id in ids(result)`.
2. returns: `Q not in result`.
3. session: `Q in db.new`.
4. nothing written: nothing written.
5. count: `machine_maintenance_logs` rows with `summary == "Pending"`: exactly 0 (raw query).
6. unchanged: unchanged(A).
7. unchanged: unchanged(X).
8. count: `machine_maintenance_logs` rows with `id == X.id`: exactly 1 (raw query).

### MML-GW-03 — a log of another workspace does not appear, although it would fit on the page
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.
2. Z = log, but `workspace_id W2.id`, `machine_id M9.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. unchanged: unchanged(Z).

### MML-GW-04 — a soft-deleted log is not returned, an inactive live log is
- **Rules:** `get_by_workspace` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `is_active False`.
3. C = log, but gone.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. unchanged: unchanged(C).

### MML-GW-05 — a soft-deleted log takes no place in the page
- **Rules:** `get_by_workspace` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D3`.
2. B = log, but `maintenance_date D2`, gone.
3. C = log, but `maintenance_date D1`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### MML-GW-06 — logs of deleted and inactive parents are returned
- **Rules:** `get_by_workspace` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MD.id`.
2. B = log, but `machine_id MF.id`.
3. C = log, but `machine_id MI.id`.
4. E = log, but `machine_id MG.id`.
5. G = log.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id, C.id, E.id, G.id]`.

### MML-GW-07 — logs of deleted and inactive parents take a place in the page
- **Rules:** `get_by_workspace` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MD.id`, `maintenance_date D5`.
2. B = log, but `machine_id MF.id`, `maintenance_date D4`.
3. C = log, but `machine_id MI.id`, `maintenance_date D3`.
4. E = log, but `machine_id MG.id`, `maintenance_date D2`.
5. G = log, but `maintenance_date D1`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=4)`.

**Then**
1. returns: `ids(result) == [G.id]`.

### MML-GW-08 — logs with different dates come back latest date first, whatever their ids
- **Rules:** `get_by_workspace` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log, but `maintenance_date D3`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id, C.id]`.

### MML-GW-09 — logs on one date come back highest id first
- **Rules:** `get_by_workspace` R4a [BUG-1100]
- **Kind:** bug
- **Expect:** xfail BUG-1100 (non-strict)
- **Fails today on:** Then 2 (no tie-break is requested; the rows usually come back in physical order, which can match by accident)

**Given**
1. A = log.
2. B = log.
3. C = log.
4. `A.summary = "Edited"`, then `db.flush()`. (Changed after the later rows were created: this usually moves A physically behind them.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id, C.id]`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.

### MML-GW-10 — the query asks for date descending, then id descending
- **Rules:** `get_by_workspace` R4a [BUG-1100]
- **Kind:** bug
- **Expect:** xfail BUG-1100
- **Fails today on:** Then 4 (the `ORDER BY` has `maintenance_date DESC` and no `id` key)

**Given**
1. A = log.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"maintenance_date DESC" in order_part`.
4. statement: `"machine_maintenance_logs.id DESC" in order_part`.
5. statement: `order_part.index("maintenance_date DESC") < order_part.index("machine_maintenance_logs.id DESC")`.

### MML-GW-11 — paging one log at a time over one date shows each log once
- **Rules:** `get_by_workspace` R4a [BUG-1100], R5
- **Kind:** bug
- **Expect:** xfail BUG-1100 (non-strict)
- **Fails today on:** Then 2 (no tie-break is requested; windows usually repeat one log and miss another, but physical order can match by accident)

**Given**
1. A = log.
2. B = log.
3. C = log.
4. E = log.
5. G = log.
6. `A.summary = "Edited"`, then `db.flush()`. (Changed after the later rows were created: this usually moves A physically behind them.)

**When**
- `pages = [ids(dao.get_by_workspace(db, workspace_id=W1.id, skip=k, limit=1)) for k in range(5)]`. (One statement on purpose: the rule is about consecutive windows.)

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1, 1, 1]`.
2. returns: `sorted(sum(pages, [])) == [A.id, B.id, C.id, E.id, G.id]`.
3. returns: `pages == [[G.id], [E.id], [C.id], [B.id], [A.id]]`.

### MML-GW-12 — with the default limit, 101 logs give the latest 100
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows` = 101 logs built with `add_all`, row k (k = 0 … 100) with `maintenance_date` = `date(2025, 1, 1) + timedelta(days=k)`. `all_ids = [r.id for r in rows]` after the flush.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `set(ids(result)) == set(all_ids[1:])`.

### MML-GW-13 — limit=1000 gives all 101 logs
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows` = 101 logs built with `add_all`, row k (k = 0 … 100) with `maintenance_date` = `date(2025, 1, 1) + timedelta(days=k)`. `all_ids = [r.id for r in rows]` after the flush.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `set(ids(result)) == set(all_ids)`.

### MML-GW-14 — skip=1 and limit=2 give the second and third log by date
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D4`.
2. B = log, but `maintenance_date D3`.
3. C = log, but `maintenance_date D2`.
4. E = log, but `maintenance_date D1`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `ids(result) == [B.id, C.id]`.

### MML-GW-15 — limit=1 returns only the latest log
- **Rules:** `get_by_workspace` R5, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log, but `maintenance_date D1`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MML-GW-16 — an unknown workspace returns an empty list
- **Rules:** `get_by_workspace` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = dao.get_by_workspace(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### MML-GW-17 — a workspace with no logs returns an empty list
- **Rules:** `get_by_workspace` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log. (W2 has no logs.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### MML-GW-18 — skip equal to the number of rows returns an empty list
- **Rules:** `get_by_workspace` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.
2. B = log.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### MML-GW-19 — limit=0 returns an empty list
- **Rules:** `get_by_workspace` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.
2. B = log.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MML-GW-20 — skip past the number of rows returns an empty list
- **Rules:** `get_by_workspace` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.
2. B = log.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=3)`.

**Then**
1. returns: `result == []`.

### MML-GW-21 — skip one below the number of rows returns the oldest log
- **Rules:** `get_by_workspace` R5, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log, but `maintenance_date D1`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MML-GW-22 — a negative limit is rejected by Postgres
- **Rules:** `get_by_workspace` R7, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `dao.get_by_workspace(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError` when the query runs.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MML-GW-23 — a negative skip is rejected by Postgres
- **Rules:** `get_by_workspace` R7, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `dao.get_by_workspace(db, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError` when the query runs.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MML-GW-24 — a log linked to another workspace's machine is not returned
- **Rules:** `get_by_workspace` R8 [BUG-1101]
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 3 (X is returned too, with the other workspace's `machine_id`)

**Given**
1. A = log.
2. X = log, but `machine_id M9.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `A.id in ids(result)`.
2. count: `machine_maintenance_logs` rows with `id == X.id`: exactly 1 (raw query).
3. returns: `sorted(ids(result)) == [A.id]`.

### MML-GW-25 — a log linked to another workspace's machine takes no place in the page
- **Rules:** `get_by_workspace` R8 [BUG-1101]
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 3 (X counts, so one log is left after skipping one)

**Given**
1. A = log, but `maintenance_date D1`.
2. X = log, but `machine_id M9.id`, `maintenance_date D3`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `isinstance(result, list)`.
2. count: `machine_maintenance_logs` rows with `id == X.id`: exactly 1 (raw query).
3. returns: `result == []`.

### MML-GW-26 — a soft-deleted log ahead of the skipped row uses up no skip: the filter runs before paging
- **Rules:** `get_by_workspace` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D3`, gone.
2. B = log, but `maintenance_date D2`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [C.id]`.

## `MachineMaintenanceLogDAO.get_by_id_and_workspace`

### MML-GI-01 — returns the session's log with that id
- **Rules:** `get_by_id_and_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.
2. B = log.

**When**
- `result = dao.get_by_id_and_workspace(db, id=B.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is B`.
2. returns: `isinstance(result, MachineMaintenanceLog)`.

### MML-GI-02 — reading writes nothing and leaves a pending row pending
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.
2. X = log, but `machine_id M9.id`. (Linked to another workspace's machine on purpose.)
3. Q = pending log (Conventions): built, `db.add(Q)`, not flushed. Last line of the Given.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is A`.
2. session: `Q in db.new`.
3. nothing written: nothing written.
4. count: `machine_maintenance_logs` rows with `summary == "Pending"`: exactly 0 (raw query).
5. unchanged: unchanged(A).
6. unchanged: unchanged(X).
7. count: `machine_maintenance_logs` rows with `id == X.id`: exactly 1 (raw query).

### MML-GI-03 — a log of another workspace is not found
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = log, but `workspace_id W2.id`, `machine_id M9.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(Z).

### MML-GI-04 — an unknown id returns None
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### MML-GI-05 — id=0 returns None
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = dao.get_by_id_and_workspace(db, id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### MML-GI-06 — a soft-deleted log is found
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but gone.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is A`.
2. returns: `result.is_deleted is True`.
3. unchanged: unchanged(A).

### MML-GI-07 — a log of a soft-deleted machine is found
- **Rules:** `get_by_id_and_workspace` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MD.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is A`.

### MML-GI-08 — a log of a machine in a soft-deleted factory is found
- **Rules:** `get_by_id_and_workspace` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MF.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is A`.

### MML-GI-09 — a log linked to another workspace's machine is not found
- **Rules:** `get_by_id_and_workspace` R6 [BUG-1101]
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 2 (X is returned)

**Given**
1. X = log, but `machine_id M9.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=X.id, workspace_id=W1.id)`.

**Then**
1. count: `machine_maintenance_logs` rows with `id == X.id`: exactly 1 (raw query).
2. returns: `result is None`.

### MML-GI-10 — a log of a machine in an inactive factory is found
- **Rules:** `get_by_id_and_workspace` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MG.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is A`.

## `MachineMaintenanceLogDAO.get_by_machine`

### MML-GM-01 — returns a list of the machine's live logs
- **Rules:** `get_by_machine` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.
2. B = log.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.
3. returns: `isinstance(result[0], MachineMaintenanceLog)`.

### MML-GM-02 — reading writes nothing and leaves a pending row pending
- **Rules:** `get_by_machine` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.
2. X = log, but `machine_id M9.id`. (Linked to another workspace's machine on purpose.)
3. Q = pending log (Conventions): built, `db.add(Q)`, not flushed. Last line of the Given.

**When**
- `result = dao.get_by_machine(db, M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `A.id in ids(result)`.
2. returns: `Q not in result`.
3. session: `Q in db.new`.
4. nothing written: nothing written.
5. count: `machine_maintenance_logs` rows with `summary == "Pending"`: exactly 0 (raw query).
6. unchanged: unchanged(A).
7. unchanged: unchanged(X).
8. count: `machine_maintenance_logs` rows with `id == X.id`: exactly 1 (raw query).

### MML-GM-03 — a log of another machine is not returned
- **Rules:** `get_by_machine` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.
2. C = log, but `machine_id M2.id`.

**When**
- `result = dao.get_by_machine(db, M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. unchanged: unchanged(C).

### MML-GM-04 — the right machine under another workspace returns an empty list
- **Rules:** `get_by_machine` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = dao.get_by_machine(db, M1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### MML-GM-05 — a soft-deleted log is not returned, an inactive live log is
- **Rules:** `get_by_machine` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `is_active False`.
3. C = log, but gone.

**When**
- `result = dao.get_by_machine(db, M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. unchanged: unchanged(C).

### MML-GM-06 — a soft-deleted log takes no place in the page
- **Rules:** `get_by_machine` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D3`.
2. B = log, but `maintenance_date D2`, gone.
3. C = log, but `maintenance_date D1`.

**When**
- `result = dao.get_by_machine(db, M1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### MML-GM-07 — asked for a soft-deleted machine, its logs are returned
- **Rules:** `get_by_machine` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MD.id`.

**When**
- `result = dao.get_by_machine(db, MD.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MML-GM-08 — asked for a machine in a soft-deleted factory, its logs are returned
- **Rules:** `get_by_machine` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MF.id`.

**When**
- `result = dao.get_by_machine(db, MF.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MML-GM-09 — logs with different dates come back latest date first, whatever their ids
- **Rules:** `get_by_machine` R5 [BUG-1100]
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log, but `maintenance_date D3`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = dao.get_by_machine(db, M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id, C.id]`.

### MML-GM-10 — logs on one date come back highest id first
- **Rules:** `get_by_machine` R5 [BUG-1100]
- **Kind:** bug
- **Expect:** xfail BUG-1100 (non-strict)
- **Fails today on:** Then 2 (no tie-break is requested; the rows usually come back in physical order, which can match by accident)

**Given**
1. A = log.
2. B = log.
3. C = log.
4. `A.summary = "Edited"`, then `db.flush()`. (Changed after the later rows were created: this usually moves A physically behind them.)

**When**
- `result = dao.get_by_machine(db, M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id, C.id]`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.

### MML-GM-11 — the query asks for date descending, then id descending
- **Rules:** `get_by_machine` R5 [BUG-1100]
- **Kind:** bug
- **Expect:** xfail BUG-1100
- **Fails today on:** Then 4 (the `ORDER BY` has `maintenance_date DESC` and no `id` key)

**Given**
1. A = log.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_machine(db, M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"maintenance_date DESC" in order_part`.
4. statement: `"machine_maintenance_logs.id DESC" in order_part`.
5. statement: `order_part.index("maintenance_date DESC") < order_part.index("machine_maintenance_logs.id DESC")`.

### MML-GM-12 — with the default limit, 101 logs give the latest 100
- **Rules:** `get_by_machine` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows` = 101 logs built with `add_all`, row k (k = 0 … 100) with `maintenance_date` = `date(2025, 1, 1) + timedelta(days=k)`. `all_ids = [r.id for r in rows]` after the flush.

**When**
- `result = dao.get_by_machine(db, M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `set(ids(result)) == set(all_ids[1:])`.

### MML-GM-13 — skip=1 and limit=2 give the second and third log by date
- **Rules:** `get_by_machine` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D4`.
2. B = log, but `maintenance_date D3`.
3. C = log, but `maintenance_date D2`.
4. E = log, but `maintenance_date D1`.

**When**
- `result = dao.get_by_machine(db, M1.id, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `ids(result) == [B.id, C.id]`.

### MML-GM-14 — an unknown machine id returns an empty list
- **Rules:** `get_by_machine` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = dao.get_by_machine(db, MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MML-GM-15 — machine_id=0 returns an empty list
- **Rules:** `get_by_machine` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = dao.get_by_machine(db, 0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MML-GM-16 — machine_id=None returns an empty list
- **Rules:** `get_by_machine` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = dao.get_by_machine(db, None, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MML-GM-17 — a machine with no logs returns an empty list
- **Rules:** `get_by_machine` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = dao.get_by_machine(db, M2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MML-GM-18 — skip equal to the number of rows returns an empty list
- **Rules:** `get_by_machine` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.
2. B = log.

**When**
- `result = dao.get_by_machine(db, M1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### MML-GM-19 — limit=0 returns an empty list
- **Rules:** `get_by_machine` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.
2. B = log.

**When**
- `result = dao.get_by_machine(db, M1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MML-GM-20 — a log linked to another workspace's machine is not returned
- **Rules:** `get_by_machine` R8 [BUG-1101]
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 3 (X is returned)

**Given**
1. X = log, but `machine_id M9.id`.

**When**
- `result = dao.get_by_machine(db, M9.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. count: `machine_maintenance_logs` rows with `id == X.id`: exactly 1 (raw query).
3. returns: `result == []`.

### MML-GM-21 — asked under the machine's own workspace, the linked log is not returned
- **Rules:** `get_by_machine` R8 [BUG-1101], R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = log, but `machine_id M9.id`.

**When**
- `result = dao.get_by_machine(db, M9.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### MML-GM-22 — a negative limit is rejected by Postgres
- **Rules:** `get_by_machine` R9, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `dao.get_by_machine(db, M1.id, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError` when the query runs.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MML-GM-23 — a negative skip is rejected by Postgres
- **Rules:** `get_by_machine` R9, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `dao.get_by_machine(db, M1.id, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError` when the query runs.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MML-GM-24 — a soft-deleted log ahead of the skipped row uses up no skip: the filter runs before paging
- **Rules:** `get_by_machine` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D3`, gone.
2. B = log, but `maintenance_date D2`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = dao.get_by_machine(db, M1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### MML-GM-25 — limit=1000 gives all 101 logs
- **Rules:** `get_by_machine` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows` = 101 logs built with `add_all`, row k (k = 0 … 100) with `maintenance_date` = `date(2025, 1, 1) + timedelta(days=k)`. `all_ids = [r.id for r in rows]` after the flush.

**When**
- `result = dao.get_by_machine(db, M1.id, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `set(ids(result)) == set(all_ids)`.

### MML-GM-26 — asked for a machine in an inactive factory, its logs are returned
- **Rules:** `get_by_machine` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MG.id`.

**When**
- `result = dao.get_by_machine(db, MG.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

## `MachineMaintenanceLogDAO.get_by_type`

### MML-GT-01 — returns a list of the workspace's live logs of that type
- **Rules:** `get_by_type` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `machine_id M2.id`.

**When**
- `result = dao.get_by_type(db, maintenance_type=MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.
3. returns: `isinstance(result[0], MachineMaintenanceLog)`.

### MML-GT-02 — reading writes nothing and leaves a pending row pending
- **Rules:** `get_by_type` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.
2. X = log, but `machine_id M9.id`. (Linked to another workspace's machine on purpose.)
3. Q = pending log (Conventions): built, `db.add(Q)`, not flushed. Last line of the Given.

**When**
- `result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `A.id in ids(result)`.
2. returns: `Q not in result`.
3. session: `Q in db.new`.
4. nothing written: nothing written.
5. count: `machine_maintenance_logs` rows with `summary == "Pending"`: exactly 0 (raw query).
6. unchanged: unchanged(A).
7. unchanged: unchanged(X).
8. count: `machine_maintenance_logs` rows with `id == X.id`: exactly 1 (raw query).

### MML-GT-03 — a log of another type is not returned
- **Rules:** `get_by_type` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.
2. C = log, but `maintenance_type MaintenanceTypeEnum.INSPECTION`.

**When**
- `result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. unchanged: unchanged(C).

### MML-GT-04 — a log of that type in another workspace is not returned
- **Rules:** `get_by_type` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.
2. Z = log, but `workspace_id W2.id`, `machine_id M9.id`.

**When**
- `result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. unchanged: unchanged(Z).

### MML-GT-05 — a soft-deleted log is not returned, an inactive live log is
- **Rules:** `get_by_type` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `is_active False`.
3. C = log, but gone.

**When**
- `result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. unchanged: unchanged(C).

### MML-GT-06 — a soft-deleted log takes no place in the page
- **Rules:** `get_by_type` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D3`.
2. B = log, but `maintenance_date D2`, gone.
3. C = log, but `maintenance_date D1`.

**When**
- `result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### MML-GT-07 — a plain string equal to a member's value works like the member
- **Rules:** `get_by_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.
2. C = log, but `maintenance_type MaintenanceTypeEnum.INSPECTION`.

**When**
- `result = dao.get_by_type(db, "REPAIR", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MML-GT-08 — maintenance_type=None returns an empty list
- **Rules:** `get_by_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = dao.get_by_type(db, None, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MML-GT-09 — a string that is no member is rejected by Postgres
- **Rules:** `get_by_type` R2, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `dao.get_by_type(db, "BOGUS", workspace_id=W1.id)`.

**Then**
1. raises: `DataError` when the query runs.
2. raises: `isinstance(exc.value.orig, InvalidTextRepresentation)`.
3. raises: `exc.value.orig.pgcode == "22P02"`.
4. nothing written: nothing written.

### MML-GT-10 — a member's value in lower case is rejected by Postgres
- **Rules:** `get_by_type` R2, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `dao.get_by_type(db, "repair", workspace_id=W1.id)`.

**Then**
1. raises: `DataError` when the query runs.
2. raises: `isinstance(exc.value.orig, InvalidTextRepresentation)`.
3. raises: `exc.value.orig.pgcode == "22P02"`.
4. nothing written: nothing written.

### MML-GT-11 — logs with different dates come back latest date first, whatever their ids
- **Rules:** `get_by_type` R3 [BUG-1100]
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log, but `maintenance_date D3`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id, C.id]`.

### MML-GT-12 — logs on one date come back highest id first
- **Rules:** `get_by_type` R3 [BUG-1100]
- **Kind:** bug
- **Expect:** xfail BUG-1100 (non-strict)
- **Fails today on:** Then 2 (no tie-break is requested; the rows usually come back in physical order, which can match by accident)

**Given**
1. A = log.
2. B = log.
3. C = log.
4. `A.summary = "Edited"`, then `db.flush()`. (Changed after the later rows were created: this usually moves A physically behind them.)

**When**
- `result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id, C.id]`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.

### MML-GT-13 — the query asks for date descending, then id descending
- **Rules:** `get_by_type` R3 [BUG-1100]
- **Kind:** bug
- **Expect:** xfail BUG-1100
- **Fails today on:** Then 4 (the `ORDER BY` has `maintenance_date DESC` and no `id` key)

**Given**
1. A = log.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"maintenance_date DESC" in order_part`.
4. statement: `"machine_maintenance_logs.id DESC" in order_part`.
5. statement: `order_part.index("maintenance_date DESC") < order_part.index("machine_maintenance_logs.id DESC")`.

### MML-GT-14 — logs of deleted and inactive parents are returned
- **Rules:** `get_by_type` R3a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MD.id`.
2. B = log, but `machine_id MF.id`.
3. C = log, but `machine_id MI.id`.
4. E = log, but `machine_id MG.id`.
5. G = log.

**When**
- `result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id, C.id, E.id, G.id]`.

### MML-GT-15 — with the default limit, 101 logs give the latest 100
- **Rules:** `get_by_type` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows` = 101 logs built with `add_all`, row k (k = 0 … 100) with `maintenance_date` = `date(2025, 1, 1) + timedelta(days=k)`. `all_ids = [r.id for r in rows]` after the flush.

**When**
- `result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `set(ids(result)) == set(all_ids[1:])`.

### MML-GT-16 — skip=1 and limit=2 give the second and third log by date
- **Rules:** `get_by_type` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D4`.
2. B = log, but `maintenance_date D3`.
3. C = log, but `maintenance_date D2`.
4. E = log, but `maintenance_date D1`.

**When**
- `result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `ids(result) == [B.id, C.id]`.

### MML-GT-17 — an unknown workspace returns an empty list
- **Rules:** `get_by_type` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### MML-GT-18 — skip equal to the number of rows returns an empty list
- **Rules:** `get_by_type` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.
2. B = log.

**When**
- `result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### MML-GT-19 — limit=0 returns an empty list
- **Rules:** `get_by_type` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.
2. B = log.

**When**
- `result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MML-GT-20 — a negative limit is rejected by Postgres
- **Rules:** `get_by_type` R4, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError` when the query runs.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MML-GT-21 — a negative skip is rejected by Postgres
- **Rules:** `get_by_type` R4, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError` when the query runs.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MML-GT-22 — a log linked to another workspace's machine is not returned
- **Rules:** `get_by_type` R5 [BUG-1101]
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 3 (X is returned too)

**Given**
1. A = log.
2. X = log, but `machine_id M9.id`.

**When**
- `result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `A.id in ids(result)`.
2. count: `machine_maintenance_logs` rows with `id == X.id`: exactly 1 (raw query).
3. returns: `sorted(ids(result)) == [A.id]`.

### MML-GT-23 — a soft-deleted log ahead of the skipped row uses up no skip: the filter runs before paging
- **Rules:** `get_by_type` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D3`, gone.
2. B = log, but `maintenance_date D2`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### MML-GT-24 — limit=1000 gives all 101 logs
- **Rules:** `get_by_type` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows` = 101 logs built with `add_all`, row k (k = 0 … 100) with `maintenance_date` = `date(2025, 1, 1) + timedelta(days=k)`. `all_ids = [r.id for r in rows]` after the flush.

**When**
- `result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `set(ids(result)) == set(all_ids)`.

### MML-GT-25 — a log linked to another workspace's machine takes no place in the page
- **Rules:** `get_by_type` R5 [BUG-1101]
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 3 (X counts, so one log is left after skipping one)

**Given**
1. A = log, but `maintenance_date D1`.
2. X = log, but `machine_id M9.id`, `maintenance_date D3`.

**When**
- `result = dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `isinstance(result, list)`.
2. count: `machine_maintenance_logs` rows with `id == X.id`: exactly 1 (raw query).
3. returns: `result == []`.

## `MachineMaintenanceLogDAO.get_by_machine_and_type`

### MML-GP-01 — returns a list of the live logs of that machine and type
- **Rules:** `get_by_machine_and_type` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.
2. B = log.

**When**
- `result = dao.get_by_machine_and_type(db, machine_id=M1.id, maintenance_type=MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.
3. returns: `isinstance(result[0], MachineMaintenanceLog)`.

### MML-GP-02 — reading writes nothing and leaves a pending row pending
- **Rules:** `get_by_machine_and_type` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.
2. X = log, but `machine_id M9.id`. (Linked to another workspace's machine on purpose.)
3. Q = pending log (Conventions): built, `db.add(Q)`, not flushed. Last line of the Given.

**When**
- `result = dao.get_by_machine_and_type(db, M1.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `A.id in ids(result)`.
2. returns: `Q not in result`.
3. session: `Q in db.new`.
4. nothing written: nothing written.
5. count: `machine_maintenance_logs` rows with `summary == "Pending"`: exactly 0 (raw query).
6. unchanged: unchanged(A).
7. unchanged: unchanged(X).
8. count: `machine_maintenance_logs` rows with `id == X.id`: exactly 1 (raw query).

### MML-GP-03 — another type on that machine is not returned
- **Rules:** `get_by_machine_and_type` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.
2. C = log, but `maintenance_type MaintenanceTypeEnum.INSPECTION`.

**When**
- `result = dao.get_by_machine_and_type(db, M1.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MML-GP-04 — that type on another machine is not returned
- **Rules:** `get_by_machine_and_type` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.
2. C = log, but `machine_id M2.id`.

**When**
- `result = dao.get_by_machine_and_type(db, M1.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MML-GP-05 — the same machine and type under another workspace returns an empty list
- **Rules:** `get_by_machine_and_type` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = dao.get_by_machine_and_type(db, M1.id, MaintenanceTypeEnum.REPAIR, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### MML-GP-06 — a soft-deleted log is not returned, an inactive live log is
- **Rules:** `get_by_machine_and_type` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log.
2. B = log, but `is_active False`.
3. C = log, but gone.

**When**
- `result = dao.get_by_machine_and_type(db, M1.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. unchanged: unchanged(C).

### MML-GP-07 — a soft-deleted log takes no place in the page
- **Rules:** `get_by_machine_and_type` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D3`.
2. B = log, but `maintenance_date D2`, gone.
3. C = log, but `maintenance_date D1`.

**When**
- `result = dao.get_by_machine_and_type(db, M1.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### MML-GP-08 — a plain string equal to a member's value works like the member
- **Rules:** `get_by_machine_and_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.
2. C = log, but `maintenance_type MaintenanceTypeEnum.INSPECTION`.

**When**
- `result = dao.get_by_machine_and_type(db, M1.id, "REPAIR", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MML-GP-09 — maintenance_type=None returns an empty list
- **Rules:** `get_by_machine_and_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = dao.get_by_machine_and_type(db, M1.id, None, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MML-GP-10 — a string that is no member is rejected by Postgres
- **Rules:** `get_by_machine_and_type` R2, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `dao.get_by_machine_and_type(db, M1.id, "BOGUS", workspace_id=W1.id)`.

**Then**
1. raises: `DataError` when the query runs.
2. raises: `isinstance(exc.value.orig, InvalidTextRepresentation)`.
3. raises: `exc.value.orig.pgcode == "22P02"`.
4. nothing written: nothing written.

### MML-GP-11 — an unknown machine id returns an empty list
- **Rules:** `get_by_machine_and_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = dao.get_by_machine_and_type(db, MISSING, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MML-GP-12 — machine_id=0 returns an empty list
- **Rules:** `get_by_machine_and_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = dao.get_by_machine_and_type(db, 0, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MML-GP-13 — machine_id=None returns an empty list
- **Rules:** `get_by_machine_and_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = dao.get_by_machine_and_type(db, None, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MML-GP-14 — logs with different dates come back latest date first, whatever their ids
- **Rules:** `get_by_machine_and_type` R3 [BUG-1100]
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D2`.
2. B = log, but `maintenance_date D3`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = dao.get_by_machine_and_type(db, M1.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id, C.id]`.

### MML-GP-15 — logs on one date come back highest id first
- **Rules:** `get_by_machine_and_type` R3 [BUG-1100]
- **Kind:** bug
- **Expect:** xfail BUG-1100 (non-strict)
- **Fails today on:** Then 2 (no tie-break is requested; the rows usually come back in physical order, which can match by accident)

**Given**
1. A = log.
2. B = log.
3. C = log.
4. `A.summary = "Edited"`, then `db.flush()`. (Changed after the later rows were created: this usually moves A physically behind them.)

**When**
- `result = dao.get_by_machine_and_type(db, M1.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id, C.id]`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.

### MML-GP-16 — the query asks for date descending, then id descending
- **Rules:** `get_by_machine_and_type` R3 [BUG-1100]
- **Kind:** bug
- **Expect:** xfail BUG-1100
- **Fails today on:** Then 4 (the `ORDER BY` has `maintenance_date DESC` and no `id` key)

**Given**
1. A = log.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_machine_and_type(db, M1.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"maintenance_date DESC" in order_part`.
4. statement: `"machine_maintenance_logs.id DESC" in order_part`.
5. statement: `order_part.index("maintenance_date DESC") < order_part.index("machine_maintenance_logs.id DESC")`.

### MML-GP-17 — asked for a soft-deleted machine, its logs are returned
- **Rules:** `get_by_machine_and_type` R3a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MD.id`.

**When**
- `result = dao.get_by_machine_and_type(db, MD.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MML-GP-18 — asked for a machine in a soft-deleted factory, its logs are returned
- **Rules:** `get_by_machine_and_type` R3a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MF.id`.

**When**
- `result = dao.get_by_machine_and_type(db, MF.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MML-GP-19 — with the default limit, 101 logs give the latest 100
- **Rules:** `get_by_machine_and_type` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows` = 101 logs built with `add_all`, row k (k = 0 … 100) with `maintenance_date` = `date(2025, 1, 1) + timedelta(days=k)`. `all_ids = [r.id for r in rows]` after the flush.

**When**
- `result = dao.get_by_machine_and_type(db, M1.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `set(ids(result)) == set(all_ids[1:])`.

### MML-GP-20 — skip=1 and limit=2 give the second and third log by date
- **Rules:** `get_by_machine_and_type` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D4`.
2. B = log, but `maintenance_date D3`.
3. C = log, but `maintenance_date D2`.
4. E = log, but `maintenance_date D1`.

**When**
- `result = dao.get_by_machine_and_type(db, M1.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `ids(result) == [B.id, C.id]`.

### MML-GP-21 — skip equal to the number of rows returns an empty list
- **Rules:** `get_by_machine_and_type` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.
2. B = log.

**When**
- `result = dao.get_by_machine_and_type(db, M1.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### MML-GP-22 — limit=0 returns an empty list
- **Rules:** `get_by_machine_and_type` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.
2. B = log.

**When**
- `result = dao.get_by_machine_and_type(db, M1.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MML-GP-23 — a negative limit is rejected by Postgres
- **Rules:** `get_by_machine_and_type` R4, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `dao.get_by_machine_and_type(db, M1.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError` when the query runs.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MML-GP-24 — a negative skip is rejected by Postgres
- **Rules:** `get_by_machine_and_type` R4, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `dao.get_by_machine_and_type(db, M1.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError` when the query runs.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MML-GP-25 — a log linked to another workspace's machine is not returned
- **Rules:** `get_by_machine_and_type` R5 [BUG-1101]
- **Kind:** bug
- **Expect:** xfail BUG-1101
- **Fails today on:** Then 3 (X is returned)

**Given**
1. X = log, but `machine_id M9.id`.

**When**
- `result = dao.get_by_machine_and_type(db, M9.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. count: `machine_maintenance_logs` rows with `id == X.id`: exactly 1 (raw query).
3. returns: `result == []`.

### MML-GP-26 — a soft-deleted log ahead of the skipped row uses up no skip: the filter runs before paging
- **Rules:** `get_by_machine_and_type` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `maintenance_date D3`, gone.
2. B = log, but `maintenance_date D2`.
3. C = log, but `maintenance_date D1`.

**When**
- `result = dao.get_by_machine_and_type(db, M1.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### MML-GP-27 — limit=1000 gives all 101 logs
- **Rules:** `get_by_machine_and_type` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows` = 101 logs built with `add_all`, row k (k = 0 … 100) with `maintenance_date` = `date(2025, 1, 1) + timedelta(days=k)`. `all_ids = [r.id for r in rows]` after the flush.

**When**
- `result = dao.get_by_machine_and_type(db, M1.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `set(ids(result)) == set(all_ids)`.

### MML-GP-28 — asked for a machine in an inactive factory, its logs are returned
- **Rules:** `get_by_machine_and_type` R3a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MG.id`.

**When**
- `result = dao.get_by_machine_and_type(db, MG.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

## `MachineMaintenanceLogDAO.soft_delete`

### MML-SD-01 — a live log is marked deleted by the given user
- **Rules:** `soft_delete` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=P1.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is True`, `is_active is False`.
3. re-read A: `deleted_by == P1.id`.
4. re-read A: `deleted_at is not None`.

### MML-SD-02 — deleted_at comes from utcnow, not the database clock
- **Rules:** `soft_delete` R1a [BUG-1102]
- **Kind:** bug
- **Expect:** xfail BUG-1102
- **Fails today on:** Then 3 (`deleted_at` is the database's `now()`, not NOW)

**Given**
1. A = log.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=P1.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is True`.
3. re-read A: `deleted_at == NOW`.

### MML-SD-03 — no other column changes
- **Rules:** `soft_delete` R2, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("12.50")`, `performed_by "Rahim"`, `created_by P1.id`, `updated_by P2.id`.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=P2.id)`.

**Then**
1. returns: `result is A`.
2. unchanged: unchanged(A) except `is_deleted`, `is_active`, `deleted_at`, `deleted_by`, `updated_at`.
3. re-read A: `cost == Decimal("12.50")`, `performed_by == "Rahim"`, `summary == "Bearing change"`.
4. re-read A: `created_by == P1.id`, `updated_by == P2.id`.
5. re-read A: `updated_at is not None`.

### MML-SD-04 — an already deleted log is stamped again, with no error
- **Rules:** `soft_delete` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but gone.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=P2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is True`, `is_active is False`.
3. re-read A: `deleted_by == P2.id`.
4. re-read A: `deleted_at is not None`, `deleted_at != T0`.

### MML-SD-05 — an already deleted log gets deleted_at from utcnow
- **Rules:** `soft_delete` R3, R1a [BUG-1102]
- **Kind:** bug
- **Expect:** xfail BUG-1102
- **Fails today on:** Then 3 (`deleted_at` is the database's `now()`, not NOW)

**Given**
1. A = log, but gone.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=P2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `deleted_by == P2.id`.
3. re-read A: `deleted_at == NOW`.

### MML-SD-06 — the delete is flushed, not committed: a rollback brings the log back
- **Rules:** `soft_delete` R4, Overview (never commits)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=P1.id)`.

**Then**
1. returns: `result is A`.
2. count: inside the savepoint, `machine_maintenance_logs` rows with `id == A.id` and `is_deleted` true: exactly 1 (raw query).
3. re-read A after the savepoint rollback: `is_deleted is False`, `is_active is True`.
4. re-read A after the savepoint rollback: `deleted_at is None`, `deleted_by is None`.
5. mock called: the `db.commit` spy was never called.

### MML-SD-07 — in the same session the log leaves the four lists and stays readable by id
- **Rules:** `soft_delete` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=P1.id)`.

**Then**
1. returns: `result is A`.
2. read: `dao.get_by_workspace(db, workspace_id=W1.id) == []`.
3. read: `dao.get_by_machine(db, M1.id, workspace_id=W1.id) == []`.
4. read: `dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id) == []`.
5. read: `dao.get_by_machine_and_type(db, M1.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id) == []`.
6. read: `dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id) is A`.

### MML-SD-08 — a log of another workspace is deleted like any other
- **Rules:** `soft_delete` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = log, but `workspace_id W2.id`, `machine_id M9.id`.

**When**
- `result = dao.soft_delete(db, db_obj=Z, deleted_by=P1.id)`.

**Then**
1. returns: `result is Z`.
2. re-read Z: `is_deleted is True`, `deleted_by == P1.id`.

### MML-SD-09 — only that row changes: the machine's other log and the machine stay as they were
- **Rules:** `soft_delete` R5, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.
2. B = log.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=P1.id)`.

**Then**
1. returns: `result is A`.
2. unchanged: unchanged(B).
3. unchanged: unchanged(M1).
4. count: `machine_maintenance_logs` has the same number of rows as before the call.

### MML-SD-10 — an unknown profile fails on flush and nothing is saved
- **Rules:** `soft_delete` R6, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `dao.soft_delete(db, db_obj=A, deleted_by=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.pgcode == "23503"`.
4. raises: `"machine_maintenance_logs_deleted_by_fkey" in str(exc.value.orig)`.
5. re-read A: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
6. unchanged: unchanged(A).
7. nothing written: nothing written.

### MML-SD-11 — deleted_by=None deletes the log with an empty stamp
- **Rules:** `soft_delete` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=None)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is True`, `is_active is False`.
3. re-read A: `deleted_by is None`, `deleted_at is not None`.

### MML-SD-12 — a delete by another profile leaves updated_by as it was
- **Rules:** `soft_delete` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, but `updated_by P2.id`.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=P1.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `deleted_by == P1.id`.
3. re-read A: `updated_by == P2.id`.

### MML-SD-13 — a delete adds no machine activity row
- **Rules:** `soft_delete` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=P1.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is True`.
3. count: `machine_activity_events` rows with `machine_id == M1.id`: exactly 0 (raw query).

## `MachineMaintenanceLogDAO.restore`

### MML-RS-01 — a soft-deleted log is live again, in the database
- **Rules:** `restore` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, but gone.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is False`, `is_active is True`.
3. re-read A: `deleted_at is None`, `deleted_by is None`.

### MML-RS-02 — no other column changes and nobody is recorded
- **Rules:** `restore` R2, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("12.50")`, `performed_by "Rahim"`, `created_by P1.id`, `updated_by P2.id`, gone.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. unchanged: unchanged(A) except `is_deleted`, `is_active`, `deleted_at`, `deleted_by`, `updated_at`.
3. re-read A: `cost == Decimal("12.50")`, `performed_by == "Rahim"`.
4. re-read A: `created_by == P1.id`, `updated_by == P2.id`.
5. re-read A: `updated_at is not None`.

### MML-RS-03 — a live, active log: nothing changes and no UPDATE is issued
- **Rules:** `restore` R3, Side effects
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, read back with `db.refresh(A)` (a log the caller read from the database; setting `None` over an unloaded column would count as a change).
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. statement: no recorded statement starts with `"UPDATE"`.
3. re-read A: `updated_at is None`.
4. unchanged: unchanged(A).

### MML-RS-04 — a live, inactive log becomes active
- **Rules:** `restore` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `is_active False`.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_active is True`, `is_deleted is False`.

### MML-RS-05 — the restore is flushed, not committed: a rollback brings the delete back
- **Rules:** `restore` R5, Overview (never commits)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, but gone.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. count: inside the savepoint, `machine_maintenance_logs` rows with `id == A.id` and `is_deleted` false: exactly 1 (raw query).
3. re-read A after the savepoint rollback: `is_deleted is True`, `is_active is False`.
4. re-read A after the savepoint rollback: `deleted_at == T0`, `deleted_by == P1.id`.
5. mock called: the `db.commit` spy was never called.

### MML-RS-06 — in the same session the log is back in the four lists
- **Rules:** `restore` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, but gone.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. read: `ids(dao.get_by_workspace(db, workspace_id=W1.id)) == [A.id]`.
3. read: `ids(dao.get_by_machine(db, M1.id, workspace_id=W1.id)) == [A.id]`.
4. read: `ids(dao.get_by_type(db, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)) == [A.id]`.
5. read: `ids(dao.get_by_machine_and_type(db, M1.id, MaintenanceTypeEnum.REPAIR, workspace_id=W1.id)) == [A.id]`.

### MML-RS-07 — a log of a soft-deleted machine is restored; the machine and other logs stay as they were
- **Rules:** `restore` R6, Side effects
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = log, but `machine_id MD.id`, gone.
2. B = log, but `machine_id MD.id`, gone.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is False`, `is_active is True`.
3. unchanged: unchanged(MD).
4. unchanged: unchanged(B).

### MML-RS-08 — a log of another workspace is restored like any other
- **Rules:** `restore` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = log, but `workspace_id W2.id`, `machine_id M9.id`, gone.

**When**
- `result = dao.restore(db, db_obj=Z)`.

**Then**
1. returns: `result is Z`.
2. re-read Z: `is_deleted is False`, `is_active is True`.

### MML-RS-09 — delete then restore gives every column back except updated_at
- **Rules:** `restore` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("12.50")`, `performed_by "Rahim"`, `created_by P1.id`, `updated_by P2.id`.
2. Snapshot of A taken here.
3. `dao.soft_delete(db, db_obj=A, deleted_by=P2.id)`.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. unchanged: unchanged(A) except `updated_at`.
3. re-read A: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
4. re-read A: `updated_at is not None`.

### MML-RS-10 — a restore adds no machine activity row
- **Rules:** `restore` R2, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, but gone.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is False`.
3. count: `machine_activity_events` rows with `machine_id == M1.id`: exactly 0 (raw query).

## Inherited `BaseDAO` methods on `MachineMaintenanceLog`

### MML-INH-01 — create with a dict stores a row with the defaults
- **Rules:** `inherited` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `result = dao.create(db, obj_in=NEW)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `machine_id == M1.id`, `maintenance_type == MaintenanceTypeEnum.REPAIR`.
3. re-read the returned row: `maintenance_date == D1`, `summary == "Bearing change"`.
4. re-read the returned row: `is_active is True`, `is_deleted is False`, `created_at is not None`.
5. re-read the returned row: `cost is None`, `performed_by is None`, `created_by is None`.
6. re-read the returned row: `updated_at is None`, `updated_by is None`, `deleted_at is None`, `deleted_by is None`.
7. count: W1 has exactly 1 log.

### MML-INH-02 — create is flushed, not committed: a rollback removes the row
- **Rules:** `inherited` R1, Overview (never commits)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No log exists in W1.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.create(db, obj_in=NEW)`.

**Then**
1. returns: `result.id is not None`.
2. count: inside the savepoint, W1 has exactly 1 log.
3. count: after the savepoint rollback, W1 has exactly 0 logs.
4. mock called: the `db.commit` spy was never called.

### MML-INH-03 — create with a MachineMaintenanceLogCreate fails on flush and saves nothing
- **Rules:** `inherited` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `dao.create(db, obj_in=MachineMaintenanceLogCreate(machine_id=M1.id, maintenance_type=MaintenanceTypeEnum.REPAIR, maintenance_date=D1, summary="Bearing change"))`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `exc.value.orig.pgcode == "23502"`.
4. raises: `"workspace_id" in str(exc.value.orig)`.
5. count: W1 has exactly 0 logs.
6. nothing written: nothing written.

### MML-INH-04 — create with a required column None fails on flush and saves nothing
- **Rules:** `inherited` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `dao.create(db, obj_in={**NEW, "summary": None})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `exc.value.orig.pgcode == "23502"`.
4. count: W1 has exactly 0 logs.
5. nothing written: nothing written.

### MML-INH-05 — create with an unknown machine fails on flush and saves nothing
- **Rules:** `inherited` R3, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `dao.create(db, obj_in={**NEW, "machine_id": MISSING})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.pgcode == "23503"`.
4. raises: `"machine_maintenance_logs_machine_id_fkey" in str(exc.value.orig)`.
5. count: W1 has exactly 0 logs.
6. nothing written: nothing written.

### MML-INH-06 — create with a key the model does not have raises TypeError
- **Rules:** `inherited` R3, Errors row 6
- **Kind:** error
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `dao.create(db, obj_in={**NEW, "nonsense": 1})`.

**Then**
1. raises: `TypeError`.
2. session: `not db.new`.
3. count: W1 has exactly 0 logs.
4. nothing written: nothing written.

### MML-INH-07 — create with a maintenance_type string that is no member fails on flush
- **Rules:** `inherited` R3, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `dao.create(db, obj_in={**NEW, "maintenance_type": "BOGUS"})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, InvalidTextRepresentation)`.
3. raises: `exc.value.orig.pgcode == "22P02"`.
4. count: W1 has exactly 0 logs.
5. nothing written: nothing written.

### MML-INH-08 — HR-15: cost 0.125 is stored as 0.13 (half rounds up)
- **Rules:** `inherited` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `result = dao.create(db, obj_in={**NEW, "cost": Decimal("0.125")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `cost == Decimal("0.13")`.

### MML-INH-09 — HR-15: cost 0.135 is stored as 0.14 (half rounds up)
- **Rules:** `inherited` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `result = dao.create(db, obj_in={**NEW, "cost": Decimal("0.135")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `cost == Decimal("0.14")`.

### MML-INH-10 — HR-15: cost 2.675 is stored as 2.68 (half rounds up)
- **Rules:** `inherited` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `result = dao.create(db, obj_in={**NEW, "cost": Decimal("2.675")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `cost == Decimal("2.68")`.

### MML-INH-11 — HR-15: cost -1.005 is stored as -1.01 (half rounds away from zero)
- **Rules:** `inherited` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `result = dao.create(db, obj_in={**NEW, "cost": Decimal("-1.005")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `cost == Decimal("-1.01")`.

### MML-INH-12 — HR-15: cost 0.124 is stored as 0.12 (just below the half rounds down)
- **Rules:** `inherited` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `result = dao.create(db, obj_in={**NEW, "cost": Decimal("0.124")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `cost == Decimal("0.12")`.

### MML-INH-13 — HR-15: a float cost 1.005 is stored as 1.01
- **Rules:** `inherited` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `result = dao.create(db, obj_in={**NEW, "cost": 1.005})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `cost == Decimal("1.01")`.

### MML-INH-14 — HR-15: the object keeps the value as given until a refresh
- **Rules:** `inherited` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `result = dao.create(db, obj_in={**NEW, "cost": Decimal("0.125")})`.

**Then**
1. returns: `result.cost == Decimal("0.125")`.
2. returns: after `db.refresh(result)`, `result.cost == Decimal("0.13")`.

### MML-INH-15 — HR-15: update rounds the same way
- **Rules:** `inherited` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `result = dao.update(db, db_obj=A, obj_in={"cost": Decimal("0.125")})`.

**Then**
1. returns: `result is A`.
2. re-read A: `cost == Decimal("0.13")`.

### MML-INH-16 — cost at the top of the column is stored
- **Rules:** `inherited` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `result = dao.create(db, obj_in={**NEW, "cost": Decimal("9999999999999.99")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `cost == Decimal("9999999999999.99")`.

### MML-INH-17 — cost that rounds down to the top of the column is stored as .99
- **Rules:** `inherited` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `result = dao.create(db, obj_in={**NEW, "cost": Decimal("9999999999999.994")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `cost == Decimal("9999999999999.99")`.

### MML-INH-18 — cost that rounds past the top of the column is rejected
- **Rules:** `inherited` R5, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `dao.create(db, obj_in={**NEW, "cost": Decimal("9999999999999.995")})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, NumericValueOutOfRange)`.
3. raises: `exc.value.orig.pgcode == "22003"`.
4. count: W1 has exactly 0 logs.
5. nothing written: nothing written.

### MML-INH-19 — cost one digit too long is rejected
- **Rules:** `inherited` R5, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `dao.create(db, obj_in={**NEW, "cost": Decimal("10000000000000")})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, NumericValueOutOfRange)`.
3. raises: `exc.value.orig.pgcode == "22003"`.
4. count: W1 has exactly 0 logs.
5. nothing written: nothing written.

### MML-INH-20 — Decimal NaN is not checked here and is stored as NaN
- **Rules:** `inherited` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `result = dao.create(db, obj_in={**NEW, "cost": Decimal("NaN")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `cost.is_nan()`.

### MML-INH-21 — the schema refuses a NaN cost
- **Rules:** `inherited` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- build `MachineMaintenanceLogCreate(machine_id=M1.id, maintenance_type=MaintenanceTypeEnum.REPAIR, maintenance_date=D1, summary="Bearing change", cost=Decimal("NaN"))` (target `schema`; the DAO is not called).

**Then**
1. raises: `ValidationError` (`pydantic.ValidationError`).
2. count: W1 has exactly 0 logs.

### MML-INH-22 — a negative cost is stored
- **Rules:** `inherited` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `result = dao.create(db, obj_in={**NEW, "cost": Decimal("-3.50")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `cost == Decimal("-3.50")`.

### MML-INH-23 — cost 0 is stored, not treated as empty
- **Rules:** `inherited` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `result = dao.create(db, obj_in={**NEW, "cost": Decimal("0")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `cost == Decimal("0.00")`, `cost is not None`.

### MML-INH-24 — an empty summary and a date of 1900 are stored
- **Rules:** `inherited` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `result = dao.create(db, obj_in={**NEW, "summary": "", "maintenance_date": date(1900, 1, 1)})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `summary == ""`, `maintenance_date == date(1900, 1, 1)`.

### MML-INH-25 — a summary with surrounding spaces and a date of 2099 are stored as given
- **Rules:** `inherited` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `result = dao.create(db, obj_in={**NEW, "summary": "  Pump  ", "maintenance_date": date(2099, 12, 31)})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `summary == "  Pump  "`, `maintenance_date == date(2099, 12, 31)`.

### MML-INH-26 — a summary of 100 000 characters is stored
- **Rules:** `inherited` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `result = dao.create(db, obj_in={**NEW, "summary": "a" * 100000})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `len(summary) == 100000`.

### MML-INH-27 — performed_by of 255 characters is stored
- **Rules:** `inherited` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `result = dao.create(db, obj_in={**NEW, "performed_by": "p" * 255})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `len(performed_by) == 255`.

### MML-INH-28 — performed_by of 256 characters is rejected
- **Rules:** `inherited` R7, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `dao.create(db, obj_in={**NEW, "performed_by": "p" * 256})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, StringDataRightTruncation)`.
3. raises: `exc.value.orig.pgcode == "22001"`.
4. count: W1 has exactly 0 logs.
5. nothing written: nothing written.

### MML-INH-29 — create saves a log for a soft-deleted machine
- **Rules:** `inherited` R8
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `result = dao.create(db, obj_in={**NEW, "machine_id": MD.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `machine_id == MD.id`.
3. unchanged: unchanged(MD).

### MML-INH-30 — create saves a log for another workspace's machine
- **Rules:** `inherited` R8
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No log exists in W1.

**When**
- `result = dao.create(db, obj_in={**NEW, "machine_id": M9.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `machine_id == M9.id`.

### MML-INH-31 — update with the schema applies a value and drops an explicit None
- **Rules:** `inherited` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("12.50")`.

**When**
- `result = dao.update(db, db_obj=A, obj_in=MachineMaintenanceLogUpdate(summary="new", cost=None))`.

**Then**
1. returns: `result is A`.
2. re-read A: `summary == "new"`.
3. re-read A: `cost == Decimal("12.50")`.

### MML-INH-32 — update with the schema applies cost=0
- **Rules:** `inherited` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("12.50")`.

**When**
- `result = dao.update(db, db_obj=A, obj_in=MachineMaintenanceLogUpdate(cost=0))`.

**Then**
1. returns: `result is A`.
2. re-read A: `cost == Decimal("0.00")`.

### MML-INH-33 — update with a dict clears cost and performed_by
- **Rules:** `inherited` R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("12.50")`, `performed_by "Rahim"`.

**When**
- `result = dao.update(db, db_obj=A, obj_in={"cost": None, "performed_by": None})`.

**Then**
1. returns: `result is A`.
2. re-read A: `cost is None`, `performed_by is None`.

### MML-INH-34 — update with a dict moves the log to another machine and skips an unknown key
- **Rules:** `inherited` R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = dao.update(db, db_obj=A, obj_in={"machine_id": M2.id, "nonsense": 1})`.

**Then**
1. returns: `result is A`.
2. re-read A: `machine_id == M2.id`.
3. returns: `not hasattr(A, "nonsense")`.

### MML-INH-35 — update with summary None fails on flush and changes nothing
- **Rules:** `inherited` R10, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log.

**When**
- `dao.update(db, db_obj=A, obj_in={"summary": None})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `exc.value.orig.pgcode == "23502"`.
4. re-read A: `summary == "Bearing change"`.
5. unchanged: unchanged(A).
6. nothing written: nothing written.

### MML-INH-36 — an update sets updated_at and does not stamp updated_by
- **Rules:** `inherited` R11
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.

**When**
- `result = dao.update(db, db_obj=A, obj_in={"summary": "new"})`.

**Then**
1. returns: `result is A`.
2. re-read A: `summary == "new"`.
3. re-read A: `updated_at is not None`.
4. re-read A: `updated_by is None`.

### MML-INH-37 — an update to the current values issues no UPDATE
- **Rules:** `inherited` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("12.50")`.

**When**
- `result = dao.update(db, db_obj=A, obj_in={"summary": "Bearing change", "cost": Decimal("12.50")})`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_at is None`.
3. unchanged: unchanged(A).

### MML-INH-38 — update is flushed, not committed: a rollback restores the old value
- **Rules:** `inherited` Overview (never commits)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.update(db, db_obj=A, obj_in={"summary": "new"})`.

**Then**
1. returns: `result is A`.
2. count: inside the savepoint, `machine_maintenance_logs` rows with `id == A.id` and `summary == "new"`: exactly 1 (raw query).
3. re-read A after the savepoint rollback: `summary == "Bearing change"`.
4. mock called: the `db.commit` spy was never called.

### MML-INH-39 — remove hard-deletes the row and nothing else
- **Rules:** `inherited` R12
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log.
2. `a_id = A.id`.
3. B = log.

**When**
- `result = dao.remove(db, id=a_id)`.

**Then**
1. returns: `result is A`.
2. count: `machine_maintenance_logs` rows with `id == a_id`: exactly 0 (raw query).
3. unchanged: unchanged(B).
4. unchanged: unchanged(M1).

### MML-INH-40 — remove is flushed, not committed: a rollback brings the row back
- **Rules:** `inherited` R12, Overview (never commits)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log.
2. `a_id = A.id`.
3. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.remove(db, id=a_id)`.

**Then**
1. returns: `result is A`.
2. count: inside the savepoint, `machine_maintenance_logs` rows with `id == a_id`: exactly 0 (raw query).
3. count: after the savepoint rollback, `machine_maintenance_logs` rows with `id == a_id`: exactly 1 (raw query).
4. mock called: the `db.commit` spy was never called.

### MML-INH-41 — a hard delete of a machine with a log is refused
- **Rules:** `inherited` R14
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log, but `machine_id M2.id`.

**When**
- `db.execute(text("DELETE FROM machines WHERE id = :id"), {"id": M2.id})`.

**Then**
1. raises: `IntegrityError` when the statement runs.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"machine_maintenance_logs_machine_id_fkey" in str(exc.value.orig)`.
4. unchanged: unchanged(A).
5. unchanged: unchanged(M2).

### MML-INH-42 — a hard delete of a machine with only a soft-deleted log is refused too
- **Rules:** `inherited` R14
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log, but `machine_id M2.id`, gone.

**When**
- `db.execute(text("DELETE FROM machines WHERE id = :id"), {"id": M2.id})`.

**Then**
1. raises: `IntegrityError` when the statement runs.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. unchanged: unchanged(A).
4. unchanged: unchanged(M2).

### MML-INH-43 — a hard delete of a profile named on a log is refused
- **Rules:** `inherited` R14
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log, but gone, and `deleted_by P2.id`.

**When**
- `db.execute(text("DELETE FROM profiles WHERE id = :id"), {"id": P2.id})`.

**Then**
1. raises: `IntegrityError` when the statement runs.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"machine_maintenance_logs_deleted_by_fkey" in str(exc.value.orig)`.
4. unchanged: unchanged(A).

### MML-INH-44 — a hard delete of the workspace removes its logs
- **Rules:** `inherited` R14
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W3 = a third workspace from `make_workspace`, with no other rows of its own.
2. A = log, but `workspace_id W3.id`. (On M1: W3 has no machine, so that nothing else blocks the delete.)
3. `a_id = A.id`.
4. B = log.

**When**
- `db.execute(text("DELETE FROM workspaces WHERE id = :id"), {"id": W3.id})`.

**Then**
1. count: `machine_maintenance_logs` rows with `id == a_id`: exactly 0 (raw query).
2. unchanged: unchanged(B).
3. unchanged: unchanged(M1).

### MML-INH-45 — HR-15: update keeps the value as given until a refresh
- **Rules:** `inherited` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, but `cost Decimal("5.00")`.

**When**
- `result = dao.update(db, db_obj=A, obj_in={"cost": Decimal("0.125")})`.

**Then**
1. returns: `result is A`.
2. returns: `result.cost == Decimal("0.125")`.
3. returns: after `db.refresh(result)`, `result.cost == Decimal("0.13")`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| FU-1 (a) — `get_log` must answer 404 for a soft-deleted log (BUG-966 precedent) | `MachineMaintenanceLogManager` | Here the by-id lookup stays raw. |
| FU-1 (b) — `machine_id=0` treated as no filter | `MachineMaintenanceLogManager.list_logs` | Here `machine_id=0` gives `[]`. |
| FU-1 (c), (j) — no checks on `summary`, `performed_by`, `maintenance_date` | `MachineMaintenanceLogCreate` / `Update`, manager | Here all are stored as given, within the column. |
| FU-1 (d) — **OWNER, money:** no minimum on `cost`; `cost` beyond the column is a 500 | schemas, manager | Here negative values are stored and the range error is raised. |
| FU-1 (e), (f) — no-op stamp (HR-9); `cost` and `performed_by` cannot be cleared | `MachineMaintenanceLogManager.update_log` | Here the DAO behavior only. |
| FU-1 (g) — **OWNER, money:** the activity entry records `cost` as typed, not as stored | `MachineMaintenanceLogManager.update_log` | Here the object keeps the given value until a refresh. |
| FU-1 (h), (i) — writes against a deleted machine or factory; 404 for a BUG-1101 row | `MachineMaintenanceLogManager` | Here `get_by_id_and_workspace` answers `None`. |
| FU-2 — a restore feature must record the user and an activity entry | the future restore feature | Here `restore` records nobody. |
| FU-3 — `created_at`, `updated_at` and the database's `TimeZone` | owner of the time-zone decision | No card pins their zone. |
| FU-4, FU-5 — unused frontend hooks; deleted log ids left in activity events | frontend; machine activity event DAO | No card here. |
| `skip >= 0`, `1 <= limit <= 1000`, the enum value of `maintenance_type` | `GET /machine-maintenance-logs/` | Here unvalidated values reach Postgres. |
| `inherited` R12 [BUG-101] — `remove` of a missing id returns `None` | `tests/unit/dao/base.cases.md` (BASE-R-03) | Same code in `app/dao/base.py`, no card here. |
| `inherited` R13 — `get` and `get_multi` scope and soft-delete; [BUG-100] `get_multi` id order | `tests/unit/dao/base.cases.md` (BASE-G-02, G-03, G-04, GM-04, GM-05, GM-06) | Same code in `app/dao/base.py`, no card here. Neither method has a caller on this DAO. |
| Generic behavior of `create`, `update`, `remove` | `tests/unit/dao/base.cases.md` | Only what this model and its schemas change has cards. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `soft_delete` Side effects; `restore` R2, Side effects; inherited Side effects ("no activity event") | **Closed in revision 1 for `soft_delete` and `restore`:** `verify.md` Finding 5 names the table, `machine_activity_events`. The spec still does not. | MML-SD-13, RS-10 count it. Inherited `create`, `update` have no such card: not asked for, and the base spec owns them. |
| 2 | `get_by_machine` R2; `get_by_machine_and_type` R1 ("the same pair in another workspace") | A machine has one workspace, so a real "same pair" row in another workspace is itself the HR-16 shape. | Designed as W1's log asked for under W2 (MML-GM-04, MML-GP-05). No card stores a W2 log on M1. |
| 3 | Inherited R14 | A hard delete of a workspace was not run (spec header), and whether a workspace with other rows can be deleted is not stated. | The cascade card uses a third workspace with no machine, its log on M1, and a raw `DELETE`. If `make_workspace` rows block it, the executor reports it; it does not change the card. |
| 4 | Inherited Errors ("Detail message: — (not asserted)") | R3, R14 and `soft_delete` Errors name constraints, the Detail column says not asserted. | Loose `in str(exc.value.orig)` lines on the constraint name. Drop them if the text must not be asserted. |
| 5 | `get_by_workspace` R4a, Notes | The SQL text of the fixed order is not stated (qualified column, alias). | The recorders ask for `machine_maintenance_logs.id DESC`, and `maintenance_date DESC` without a table name. A fix that wraps the query in a subquery or an alias would need those lines changed. |
| 6 | Inherited section | The signatures of `create`, `update`, `remove` are not in this spec. | Keyword forms taken from `base.cases.md`. |
| 7 | Notes ("keyword-only", "positional or by name") | Stated as a note, not as a rule. | No card for the `TypeError` of a positional call. The filters are passed positionally in most cards and by name in each happy card. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_workspace` | Returns | MML-GW-01 |
| `get_by_workspace` | R1 | MML-GW-01, MML-GW-03 |
| `get_by_workspace` | R2 | MML-GW-04, MML-GW-05, MML-GW-26 |
| `get_by_workspace` | R3 | MML-GW-06, MML-GW-07 |
| `get_by_workspace` | R4 | MML-GW-08 |
| `get_by_workspace` | R4a [BUG-1100] | MML-GW-09, MML-GW-10, MML-GW-11 |
| `get_by_workspace` | R5 | MML-GW-11, MML-GW-12, MML-GW-13, MML-GW-14, MML-GW-15, MML-GW-21 |
| `get_by_workspace` | R6 | MML-GW-15, MML-GW-16, MML-GW-17, MML-GW-18, MML-GW-19, MML-GW-20, MML-GW-21 |
| `get_by_workspace` | R7 | MML-GW-22, MML-GW-23 |
| `get_by_workspace` | R8 [BUG-1101] | MML-GW-24, MML-GW-25 |
| `get_by_workspace` | Errors row 1 | MML-GW-22 |
| `get_by_workspace` | Errors row 2 | MML-GW-23 |
| `get_by_workspace` | Side effects | MML-GW-02 |
| `get_by_id_and_workspace` | Returns | MML-GI-01 |
| `get_by_id_and_workspace` | R1 | MML-GI-01 |
| `get_by_id_and_workspace` | R2 | MML-GI-03 |
| `get_by_id_and_workspace` | R3 | MML-GI-04, MML-GI-05 |
| `get_by_id_and_workspace` | R4 | MML-GI-06 |
| `get_by_id_and_workspace` | R5 | MML-GI-07, MML-GI-08, MML-GI-10 |
| `get_by_id_and_workspace` | R6 [BUG-1101] | MML-GI-09 |
| `get_by_id_and_workspace` | Side effects | MML-GI-02 |
| `get_by_machine` | Returns | MML-GM-01 |
| `get_by_machine` | R1 | MML-GM-01, MML-GM-03 |
| `get_by_machine` | R2 | MML-GM-04, MML-GM-21 |
| `get_by_machine` | R3 | MML-GM-05, MML-GM-06, MML-GM-24 |
| `get_by_machine` | R4 | MML-GM-07, MML-GM-08, MML-GM-26 |
| `get_by_machine` | R5 [BUG-1100] | MML-GM-09, MML-GM-10, MML-GM-11 |
| `get_by_machine` | R6 | MML-GM-12, MML-GM-13, MML-GM-25 |
| `get_by_machine` | R7 | MML-GM-14, MML-GM-15, MML-GM-16, MML-GM-17, MML-GM-18, MML-GM-19 |
| `get_by_machine` | R8 [BUG-1101] | MML-GM-20, MML-GM-21 |
| `get_by_machine` | R9 | MML-GM-22, MML-GM-23 |
| `get_by_machine` | Errors row 1 | MML-GM-22 |
| `get_by_machine` | Errors row 2 | MML-GM-23 |
| `get_by_machine` | Side effects | MML-GM-02 |
| `get_by_type` | Returns | MML-GT-01 |
| `get_by_type` | R1 | MML-GT-01, MML-GT-03, MML-GT-04, MML-GT-05, MML-GT-06, MML-GT-23 |
| `get_by_type` | R2 | MML-GT-07, MML-GT-08, MML-GT-09, MML-GT-10 |
| `get_by_type` | R3 [BUG-1100] | MML-GT-11, MML-GT-12, MML-GT-13 |
| `get_by_type` | R3a | MML-GT-14 |
| `get_by_type` | R4 | MML-GT-15, MML-GT-16, MML-GT-17, MML-GT-18, MML-GT-19, MML-GT-20, MML-GT-21, MML-GT-24 |
| `get_by_type` | R5 [BUG-1101] | MML-GT-22, MML-GT-25 |
| `get_by_type` | Errors row 1 | MML-GT-20 |
| `get_by_type` | Errors row 2 | MML-GT-21 |
| `get_by_type` | Errors row 3 | MML-GT-09, MML-GT-10 |
| `get_by_type` | Side effects | MML-GT-02 |
| `get_by_machine_and_type` | Returns | MML-GP-01 |
| `get_by_machine_and_type` | R1 | MML-GP-01, MML-GP-03, MML-GP-04, MML-GP-05, MML-GP-06, MML-GP-07, MML-GP-26 |
| `get_by_machine_and_type` | R2 | MML-GP-08, MML-GP-09, MML-GP-10, MML-GP-11, MML-GP-12, MML-GP-13 |
| `get_by_machine_and_type` | R3 [BUG-1100] | MML-GP-14, MML-GP-15, MML-GP-16 |
| `get_by_machine_and_type` | R3a | MML-GP-17, MML-GP-18, MML-GP-28 |
| `get_by_machine_and_type` | R4 | MML-GP-19, MML-GP-20, MML-GP-21, MML-GP-22, MML-GP-23, MML-GP-24, MML-GP-27 |
| `get_by_machine_and_type` | R5 [BUG-1101] | MML-GP-25 |
| `get_by_machine_and_type` | Errors row 1 | MML-GP-23 |
| `get_by_machine_and_type` | Errors row 2 | MML-GP-24 |
| `get_by_machine_and_type` | Errors row 3 | MML-GP-10 |
| `get_by_machine_and_type` | Side effects | MML-GP-02 |
| `soft_delete` | Returns | MML-SD-01 |
| `soft_delete` | R1 | MML-SD-01 |
| `soft_delete` | R1a [BUG-1102] | MML-SD-02, MML-SD-05 |
| `soft_delete` | R2 | MML-SD-03, MML-SD-12 |
| `soft_delete` | R3 | MML-SD-04, MML-SD-05 |
| `soft_delete` | R4 | MML-SD-06, MML-SD-07 |
| `soft_delete` | R5 | MML-SD-08, MML-SD-09 |
| `soft_delete` | R6 | MML-SD-10 |
| `soft_delete` | R7 | MML-SD-11 |
| `soft_delete` | Errors row 1 | MML-SD-10 |
| `soft_delete` | Side effects | MML-SD-03, MML-SD-09, MML-SD-13 |
| `soft_delete` | Overview (never commits) | MML-SD-06 |
| `restore` | Returns | MML-RS-01 |
| `restore` | R1 | MML-RS-01 |
| `restore` | R2 | MML-RS-02, MML-RS-10 |
| `restore` | R3 | MML-RS-03 |
| `restore` | R4 | MML-RS-04 |
| `restore` | R5 | MML-RS-05, MML-RS-06 |
| `restore` | R6 | MML-RS-07, MML-RS-08 |
| `restore` | R7 | MML-RS-09 |
| `restore` | Side effects | MML-RS-02, MML-RS-03, MML-RS-07, MML-RS-10 |
| `restore` | Overview (never commits) | MML-RS-05 |
| `inherited` | R1 | MML-INH-01, MML-INH-02 |
| `inherited` | R2 | MML-INH-03, MML-INH-04 |
| `inherited` | R3 | MML-INH-05, MML-INH-06, MML-INH-07 |
| `inherited` | R4 | MML-INH-08, MML-INH-09, MML-INH-10, MML-INH-11, MML-INH-12, MML-INH-13, MML-INH-14, MML-INH-15, MML-INH-45 |
| `inherited` | R5 | MML-INH-16, MML-INH-17, MML-INH-18, MML-INH-19, MML-INH-20, MML-INH-21 |
| `inherited` | R6 | MML-INH-22, MML-INH-23, MML-INH-24, MML-INH-25, MML-INH-26 |
| `inherited` | R7 | MML-INH-27, MML-INH-28 |
| `inherited` | R8 | MML-INH-29, MML-INH-30 |
| `inherited` | R9 | MML-INH-31, MML-INH-32 |
| `inherited` | R10 | MML-INH-33, MML-INH-34, MML-INH-35 |
| `inherited` | R11 | MML-INH-36, MML-INH-37 |
| `inherited` | R12 | MML-INH-39, MML-INH-40 |
| `inherited` | R14 | MML-INH-41, MML-INH-42, MML-INH-43, MML-INH-44 |
| `inherited` | Errors row 1 | MML-INH-03, MML-INH-04, MML-INH-35 |
| `inherited` | Errors row 2 | MML-INH-05 |
| `inherited` | Errors row 3 | MML-INH-07 |
| `inherited` | Errors row 4 | MML-INH-18, MML-INH-19 |
| `inherited` | Errors row 5 | MML-INH-28 |
| `inherited` | Errors row 6 | MML-INH-06 |
| `inherited` | Overview (never commits) | MML-INH-02, MML-INH-38, MML-INH-40 |
| `inherited` | R12 [BUG-101] (missing id) | Deferred: `base.cases.md` BASE-R-03 |
| `inherited` | R13 [BUG-100] | Deferred: `base.cases.md` BASE-G-02, G-03, G-04, GM-04, GM-05, GM-06 |
| `inherited` | Side effects | Deferred: base spec; activity part has no card (Spec gap 1) |
| BUG-1100 | get_by_workspace R4a, get_by_machine R5, get_by_type R3, get_by_machine_and_type R3 | MML-GW-09, MML-GW-10, MML-GW-11, MML-GM-10, MML-GM-11, MML-GT-12, MML-GT-13, MML-GP-15, MML-GP-16 |
| BUG-1101 | get_by_workspace R8, get_by_id_and_workspace R6, get_by_machine R8, get_by_type R5, get_by_machine_and_type R5 | MML-GW-24, MML-GW-25, MML-GI-09, MML-GM-20, MML-GT-22, MML-GP-25, MML-GT-25 |
| BUG-1102 | soft_delete R1a, R3 | MML-SD-02, MML-SD-05 |
| BUG-100 | inherited R13 | Deferred: `base.cases.md` BASE-GM-04 |
| BUG-101 | inherited R12 | Deferred: `base.cases.md` BASE-R-03 |
