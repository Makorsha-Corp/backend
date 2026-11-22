# Execution notes — `app/managers/work_order_type_manager.py`

> Cases: `tests/unit/managers/work_order_type_manager.cases.md` (revision 2) · Tests: `tests/unit/managers/test_work_order_type_manager.py` · Source commit: e48a092
> Result: 63 passed · 30 xfailed (24 strict, 6 non-strict) · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_work_order_type_manager.py -q -p no:cacheprovider --cov=app.managers.work_order_type_manager --cov-branch --cov-report=term-missing` (with a private `COVERAGE_FILE`)

## How the tests are built
- **Style reference:** `test_department_manager.py`. This file mirrors `test_delivery_method_manager.py`: the same ID tests the same thing. The extra cards here are C-15 and U-23.
- **Conventions → fixtures/helpers:** as in the delivery method file, with these names: `wot(name, ws=None, gone=False, updated_by=None)` for "type", `wots_add_all(names, gone=False)` for "by `add_all`", and M is the singleton `work_order_type_manager`. `reread`, `snap` (every table column), `count_all`, `count_ws`, `ids`, `names`, `commit_spy` and `record_sql` work the same way.
- **Mocks:** an autouse `_utcnow` patches `app.dao.work_order_type.utcnow` → NOW. Fixture `race` patches `WorkOrderTypeManager._check_name_exists` → False; only C-12, C-13 and U-21 use it.
- **Race cards** use `pytest.raises(IntegrityError)` → `with db.begin_nested():` → call. The savepoint keeps `db` usable for the re-reads.
  - C-12 and U-21 pass today: pgcode `23505` on `uq_wo_type_workspace_name` (psycopg2 `orig.pgcode`, `orig.diag.constraint_name`).
  - C-13 (`"repair"` next to live `"Repair"`) gets no IntegrityError today, because the constraint is case-sensitive (BUG-1214).
- **Exact-name setups:** no setup holds two rows with the same exact name. Equal names ignoring case use a deleted row in other case (N-05, S-20, C-15, U-23).
- **xfail honesty:** `--runxfail` with the scratch Then-block plugin. All 29 fail in the block their card names:
  - `DID NOT RAISE HTTPException` in Then 1: C-05, C-06, U-10, G-06.
  - `DID NOT RAISE IntegrityError` in Then 1: C-13.
  - `DID NOT RAISE ValidationError` in Then 1: C-07, C-08, U-18, U-19.
  - Untrimmed name in Then 1: C-10 and U-17.
  - `updated_by` U1 instead of U2 in Then 2: U-14, U-15, U-16.
  - `TypeError`: G-08 inside Then 1. G-07 fails in the call line just before `# Then 1`, which is what its card says.
  - **C-04 and U-08** raise `IntegrityError … uq_wo_type_workspace_name` in the When call, just before `# Then 1`, as their cards say ("the call raises IntegrityError").
  - Then 2 statement checks: S-22 and S-23.
  - `False is True` in Then 1: N-06, N-07, N-08 and N-13.
  - Today's row order in Then 1: S-05, S-06, S-07, S-20 and S-21.
- **Reference fix** (scratch `ref_fix.py`, `-p ref_fix`; `app/` untouched):
  - The manager and schema fixes are the same as for delivery methods: BUG-1706, 1707, 1708, 1709, 1710, 1711 and 1521. The manager does **not** map `IntegrityError` (spec R6/R11).
  - For BUG-1214, each test's own transaction drops `uq_wo_type_workspace_name` and recreates it under the same name as a partial unique index on `(workspace_id, lower(btrim(name))) WHERE NOT is_deleted`.
  - Result under `--runxfail`: **92 passed**, so every line past each failure point runs, and C-12 and U-21 still see the expected constraint name. With the markers on: 63 passed, 23 strict XPASS (red) and 6 non-strict XPASS.
- **Order dependence:** 3 plain runs and one with `PGOPTIONS="-c enable_seqscan=off"` each gave 63 passed, 29 xfailed, with no XPASS.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (60 statements, 26 branches).

## Factories added
None. The `wot` and `wots_add_all` builders are local to this file.

## Notes for maintainers
- **Non-strict cards** (S-05, S-06, S-07, S-20, S-21, N-13) depend on physical row order. Remove their markers by hand together with the fix of BUG-1706, 1709 or 1710. The strict alarms are S-22 (BUG-1710) and S-23 (BUG-1709); BUG-1706's is N-17 (since revision 2).
- **When a bug is fixed**, remove the markers:
  - BUG-1214: C-04, C-13, U-08.
  - BUG-1707: C-05, U-10, N-06, N-07, N-08.
  - BUG-1708: C-06, C-07, C-08, C-10, U-17, U-18, U-19.
  - BUG-1711: U-14, U-15, U-16.
  - BUG-1521: G-06, G-07, G-08.
  - BUG-1709: S-23, plus non-strict S-05, S-06, S-07.
  - BUG-1710: S-22, plus non-strict S-20, S-21.
  - BUG-1706: N-17, plus non-strict N-13.
- **BUG-1214 fix:** C-12 and U-21 (pass) assert the constraint name `uq_wo_type_workspace_name`. If the replacement index gets another name, those two cards need a cases revision.
- The 15 `SAWarning: GenericFunction … already registered` lines under `--cov` come from coverage, not from these tests.

## Revision history
- **Revision 2 (2026-11-04)** — cases revision 2 (verifier findings 1 and 2). Changed: WOTM-S-06 now asserts `len(result) == 1` (Then 1) and `set(ids(result)) <= {A.id, B.id}` (Then 2), still non-strict BUG-1709. New: WOTM-N-17 (`# [claude]`, `record_sql`), the strict order-free alarm for BUG-1706: no capped `SELECT … FROM work_order_types … LIMIT` without `name` in its WHERE. `--runxfail`: N-17 fails in Then 3 (`assert not True`), S-06 in Then 1 (`2 == 1`). The reference plugin passes all 93. 3 plain runs gave 63 passed, 30 xfailed each. Coverage is still 100% branch, `ruff` is clean, the file is LF. When BUG-1706 is fixed, N-17 XPASSes (red): remove its marker and N-13's together.
- **Cases rev 1 (2026-11-04)** — first implementation: 92 tests, 63 passed, 29 xfailed, 100% branch, `ruff` clean, LF line endings.
