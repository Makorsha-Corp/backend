# Execution notes — `app/managers/department_manager.py`

> Cases: `tests/unit/managers/department_manager.cases.md` (revision 5) · Tests: `tests/unit/managers/test_department_manager.py` · Source commit: e48a092
> Result: 60 passed · 39 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_department_manager.py -q -p no:cacheprovider --cov=app.managers.department_manager --cov-branch --cov-report=term-missing`

## How the tests are built
- **Conventions → fixtures/helpers** (top of the test file, each commented with its convention):
  - W1/W2 → fixtures `w1`, `w2` (`make_workspace`); U1/U2/U3 → `u1`, `u2`, `u3` (`make_profile`; no `workspace_members` rows). M → fixture `M` (`DepartmentManager()`).
  - "live X" / "deleted X" → fixture `dept(ws, name, deleted=False, updated_by=None)`: inserts one `Department` row directly and flushes it, so ids ascend in insertion order. `created_by` = U2 (U3 for W2 rows); deleted rows get `deleted_at = T0`, `deleted_by = U2`. `updated_by` takes a profile.
  - T0 / NOW → module constants (naive datetimes). MISSING → `missing_id(db)` (max department id + 1000).
  - re-read → `reread(db, id)` (`expire_all()` then a fresh `SELECT … WHERE id`). "W1 count" → `w_count(db, ws)` (fresh `COUNT(*)`, deleted included). `ws_rows(db, ws)` lists a workspace's rows by id for the "exactly one row named X" checks.
  - "unchanged" → `snap(db, id)` captures the Given columns (`name, workspace_id, created_by, updated_by, is_deleted, is_active, deleted_at, deleted_by`) from the database before the call; compared with a second `snap` after it.
  - Result comparison: `names(rows)` (set) by default, `in_order(rows)` (list) for "in order" cases; DEPT-S-14 compares the exact `(name, id)` list.
  - Shared setups: fixture `five` (DEPT-S-08..S-11), fixture `old_then_live` (DEPT-S-04/S-05).
- **Mocks:** autouse fixture `_utcnow` patches `app.dao.department.utcnow` → NOW for every test (spec Externals). Fixture `race` patches `DepartmentManager._check_name_exists` (class attribute, `return_value=False`); used only by DEPT-C-17, C-19, U-22, U-23. Nothing else is mocked.
- **Race cases** wrap the manager call as `pytest.raises(HTTPException)` → `with db.begin_nested():` → call, then re-read with fresh queries.
- **DB-level constraint cases** (DEPT-C-14, C-15, U-21): the offending insert / rename + `flush()` runs inside `with db.begin_nested():` under `pytest.raises(IntegrityError)`; the context manager rolls the savepoint back, then fresh queries re-read. DEPT-C-16 flushes directly (expected to succeed).
- **Parametrized:** DEPT-C-07/C-08, DEPT-U-16/U-17, DEPT-N-06..N-09 — each case ID is its own `pytest.param` id.
- **xfail honesty:** verified with `--runxfail`. Each xfail fails on the "fails today on" assertion (DID NOT RAISE for C-05/06/13/17/19, U-11/22/23, G-04; DID NOT RAISE `ValidationError` for C-07/08, U-16/17; DID NOT RAISE `IntegrityError` for C-14/15, U-21; built name untrimmed for C-10/11, U-18; `updated_by == U1` for U-12/13/14 (now their only assertion); `TypeError` (no `include_deleted`) for G-05/06; `[]` for S-04..07; insertion order for S-13/14/15; `False` for N-06..09, N-12), with two notes:
  - DEPT-C-18 fails first on `built .name == "sales"` (actual `" sales "`, BUG-004), because the Then column puts that assertion before the 409 check the cases file names ("no exception raised", BUG-002). Both are listed bugs of the case; order kept as designed.
  - DEPT-U-15 likewise fails first on `built .name == "HR"` (actual `" HR "`), before the re-read assertion named in "fails today on". Same bug (BUG-004) as named.
- Stability: 3 runs, identical outcome (57 passed, 38 xfailed).
- **No-op update splits (rev 3):** DEPT-U-24/25/26 assert the returned object, the re-read columns and W1 count but deliberately not `updated_by` (BUG-009 lives only in U-12/13/14, which now assert only `updated_by`). DEPT-U-25 is the pass-case guard for `exclude_none=True` in `update_department` (writing `name = NULL` would fail the flush).

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (63 statements, 26 branches).

## Factories added
None. `make_workspace` and `make_profile` already existed; the department builder (`dept` fixture) is local to this module. Move it to `tests/unit/factories.py` as `make_department` once another test file needs departments.

## Notes for maintainers
- **Order-dependent xfails** (BUG-001: C-06, N-12; BUG-006: S-04/05; BUG-007: S-06/07; BUG-008: S-13/14/15) are non-strict: `_row_order` and `BUG_008_ORDER` give the reason. Only DEPT-S-26 stays strict, and it covers BUG-008 only. A fix of BUG-001, 006 or 007 shows up as XPASS and fails nothing, so remove those markers by hand with the fix.
- DEPT-N-11 (pass) does not depend on row order: its 100 rows equal the cap, so every row is examined. It passed with the match first and last.
- **When a bug is fixed**, its strict xfails will XPASS → remove the marker: BUG-001 (C-06, N-12), BUG-002 (C-05, C-18, U-11, N-06..09), BUG-003 (C-14, C-15, C-17, C-19, U-21, U-22, U-23), BUG-004 (C-07, C-08, C-10, C-11, C-13, C-18, U-15, U-16, U-17, U-18), BUG-005 (G-04, G-05, G-06), BUG-006 (S-04, S-05), BUG-007 (S-06, S-07), BUG-008 (S-13, S-14, S-15), BUG-009 (U-12..U-15). When BUG-009 is fixed, U-24/25/26 can optionally gain an `updated_by == U2` assertion only via a cases-file revision. Multi-bug cases (C-18: BUG-002+004; U-15: BUG-004+009) XPASS only once all their bugs are fixed.
- DEPT-S-23/24/25 pass today; they are regression guards for the BUG-007 fix (search moved to SQL must escape `%`/`_`).
- After the BUG-003 fix (partial unique index), DEPT-U-10 (`"HR"` → `"hr"`, same row) must keep passing: the index must not conflict with a row's own rename.
- The 15 `SAWarning: GenericFunction … already registered` warnings under `--cov` come from coverage re-importing the SQLAlchemy Postgres dialect; not from these tests.

## Revision history
- **Cases rev 5 (2026-10-31)** — source commit e48a092. DEPT-C-06, N-12, S-04..07 moved to `strict=False` with `_row_order(...)` as reason. Each passed under `--runxfail` with the list statement rewritten by a scratch plugin to another `ORDER BY` (nothing in `app/` changed), which proves it rests on physical order. N-11 passed under four orders, so it stays pass. Result 60 passed, 39 xfailed, 100% branch.
- **Cases rev 4 (2026-10-31)** — source commit e48a092. Added DEPT-C-21, U-27, D-05 (commit spies: `commit_spy`, savepoint, re-read after rollback) and DEPT-S-26 (strict recorder: `record_sql`), all under `# [claude] <ID>` at the end of the file. DEPT-S-13/14/15 moved to `strict=False` with `BUG_008_ORDER` as reason; an XPASS there is no longer a failure, and S-26 is what fails when BUG-008 is fixed. When BUG-008 is fixed, remove S-26's marker and those three. Result 60 passed, 39 xfailed, 100% branch. No discrepancy.
- **Lint only (2026-10-31)** — no case or test body changed. Comments added so ruff is clean, in the sibling files' form: `# ruff: noqa: SIM117`, and `# noqa: DTZ001` on T0 and NOW. Result unchanged: 57 passed, 38 xfailed, 100% branch.
- **Cases rev 3 (2026-09-27)** — source commit e48a092.
  - Added pass tests DEPT-C-20 (inner double space, no padding, stored as typed), DEPT-U-24 (empty body), DEPT-U-25 (explicit `name=None`; verifier finding 1 / mutant #42), DEPT-U-26 (current name, no self-collision).
  - Narrowed xfail tests DEPT-U-12/U-13/U-14 to the single `updated_by == U2` re-read assertion (name assertions moved to U-24/25/26). Still strict xfail BUG-009; `--runxfail` confirms each fails on `updated_by` (U1 id vs U2 id).
  - DEPT-C-11 row unchanged in content versus the test (built `.name` and re-read both `"Sales  Team"`, xfail BUG-004); test kept as is.
  - No retired IDs. Result 53 → 57 passed, 38 xfailed; coverage still 100% branch.
  - Mutation check on the verifier's surviving mutant: `.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/department_manager.py tests/unit/managers/test_department_manager.py --lines 118-122` →
    `Mutants: 3 · killed 2 · timeout 0 · survived 1 · score 67%`. The `exclude_none=True -> False` mutant (#3 here, verifier #42) is now KILLED. The survivor (#2, `exclude_unset=True -> False`, verifier #41) is the equivalent mutant already classified by the verifier (ast.walk order visits the `exclude_unset` keyword first).
- **Cases rev 2** — initial implementation: 53 passed · 38 xfailed · 100% branch.
