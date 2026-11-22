# Execution notes — `app/managers/delivery_method_manager.py`

> Cases: `tests/unit/managers/delivery_method_manager.cases.md` (revision 2) · Tests: `tests/unit/managers/test_delivery_method_manager.py` · Source commit: e48a092
> Result: 61 passed · 30 xfailed (24 strict, 6 non-strict) · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_delivery_method_manager.py -q -p no:cacheprovider --cov=app.managers.delivery_method_manager --cov-branch --cov-report=term-missing` (with a private `COVERAGE_FILE`)

## How the tests are built
- **Style reference:** `test_department_manager.py`. This file mirrors `test_work_order_type_manager.py`: the same ID tests the same thing in both.
- **Conventions → fixtures/helpers** (top of the file, each commented with its convention):
  - W1/W2 → `w1`, `w2` (`make_workspace`; `w2` depends on `w1`, so `W1.id < W2.id`). U1/U2 → `u1`, `u2` (`make_profile`; `u2` depends on `u1`). M → fixture returning the singleton `delivery_method_manager`. MISSING, T0, NOW → module constants.
  - "method" / "gone" → fixture `method(name, ws=None, gone=False, updated_by=None)`. It inserts one row directly and flushes it, so ids rise in Given order. Defaults: W1, `created_by` U2, `is_active True`, `is_deleted False`. "gone" sets `deleted_at T0`, `deleted_by U2`. W2 rows are also created by U2, as the Conventions say.
  - "N rows, by `add_all`" → fixture `methods_add_all(names, gone=False)`: one `add_all`, one flush.
  - re-read → `reread(db, id)` (`expire_all()` then `SELECT … WHERE id`). unchanged(X) → `snap(db, id)`, which reads **every** column of the table (`__table__.columns`, `created_at` and `updated_at` included) before and after the call. "nothing written" → `count_all(db)` (all workspaces). `count:` → `count_ws(db, ws, name=None)`. `ids()` / `names()` keep the returned order.
  - "rolled back" → `sp = db.begin_nested()` right before the call, plus `commit_spy` (`Mock(wraps=db.commit)` via `monkeypatch`). "sql_log" → `record_sql(db)` context manager (`before_cursor_execute` on `db.connection()`, removed after the call).
- **Mocks:** an autouse `_utcnow` patches `app.dao.delivery_method.utcnow` → NOW. Fixture `race` patches `DeliveryMethodManager._check_name_exists` (class attribute, `return_value=False`); only DMM-C-12, C-13 and U-21 use it. Nothing else is mocked.
- **Race cards** (C-12, C-13, U-21): `pytest.raises(HTTPException)` → `with db.begin_nested():` → call. Today no exception is raised and the duplicate is saved (BUG-1219), so Then 1 fails.
- **Every case has `# Then N` comments** before its assertions (before the `with pytest.raises` line for a `raises:` line).
- **xfail honesty:** `--runxfail` with a scratch plugin maps each failure to its `# Then N` block. All 29 fail in the block their card names:
  - `DID NOT RAISE HTTPException` in Then 1: C-05, C-06, C-12, C-13, U-10, U-21, G-06.
  - `DID NOT RAISE ValidationError` in Then 1: C-07, C-08, U-18, U-19.
  - Untrimmed name in Then 1: C-10 (`' Own Fleet '`) and U-17 (`' Courier '`).
  - `updated_by` U1 instead of U2 in Then 2: U-14, U-15, U-16.
  - `TypeError` (no `include_deleted` parameter): G-08 inside Then 1's `raises` block. G-07 fails in the call line itself, just before `# Then 1`; that is what its card says ("Then 1 (the call raises TypeError)").
  - Then 2 statement checks: S-22 and S-23 (`assert False`).
  - `False is True` in Then 1: N-06, N-07, N-08 and N-13.
  - Today's row order in Then 1: S-05 `[]`, S-06 both live rows, S-07 `[]`, S-20 insertion order, S-21 `['Charlie', 'bravo']`.
- **Reference fix** (scratch plugin `ref_fix.py`, loaded with `-p`, nothing under `app/` touched):
  - It patches in the fix of every named bug. Schemas trim and refuse a blank name (BUG-1702). `_check_name_exists` runs in SQL over the whole workspace on `lower(btrim(name))` (BUG-1700, 1701). Search runs in SQL: deleted rows filtered, `ILIKE` with `%`/`_` escaped, `ORDER BY lower(name), id`, then offset/limit (BUG-1703, 1704).
  - `get` takes `include_deleted` and hides deleted rows by default (BUG-1523). `updated_by` is stamped only on a real rename (BUG-1705).
  - For BUG-1219, create and update map an `IntegrityError` to 409. A partial unique index `(workspace_id, lower(btrim(name))) WHERE NOT is_deleted` is created inside each test's own transaction, so the rollback removes it.
  - Result under `--runxfail`: **90 passed**, so every line past each failure point runs. With the markers on: 61 passed, 23 strict XPASS (red) and 6 non-strict XPASS.
- **Order dependence:** 3 plain runs and one with `PGOPTIONS="-c enable_seqscan=off"` each gave 61 passed, 29 xfailed, with no XPASS.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (63 statements, 26 branches).

## Factories added
None. The `method` and `methods_add_all` builders are local to this file.

## Notes for maintainers
- **Non-strict cards** (S-05, S-06, S-07, S-20, S-21, N-13) depend on physical row order. A fix of BUG-1700, 1703 or 1704 shows up only as XPASS and does not turn the run red, so remove those markers by hand together with the fix.
- **Strict alarms:** S-22 (BUG-1704) and S-23 (BUG-1703) are the strict alarms for the order-dependent bugs. BUG-1700's strict alarm is N-17 (since revision 2); N-13 stays non-strict.
- **When a bug is fixed**, its strict cards XPASS and turn the run red. Remove the markers:
  - BUG-1701: C-05, U-10, N-06, N-07, N-08.
  - BUG-1702: C-06, C-07, C-08, C-10, U-17, U-18, U-19.
  - BUG-1219: C-12, C-13, U-21.
  - BUG-1705: U-14, U-15, U-16.
  - BUG-1523: G-06, G-07, G-08.
  - BUG-1703: S-23, plus non-strict S-05, S-06, S-07.
  - BUG-1704: S-22, plus non-strict S-20, S-21.
  - BUG-1700: N-17, plus non-strict N-13.
- **BUG-1219 fix:** the index must be partial (live rows only), or DMM-C-04 and N-05 (a deleted and a live "Courier") break. U-09 (a row renaming itself in other case) must keep passing.
- **BUG-1703 fix:** DMM-S-15 and S-16 (pass today) guard `%` and `_` escaping once search moves to SQL.
- The 15 `SAWarning: GenericFunction … already registered` lines under `--cov` come from coverage re-importing the dialect, not from these tests.

## Revision history
- **Revision 2 (2026-11-04)** — cases revision 2 (verifier findings 1 and 2). Changed: DMM-S-06 now asserts `len(result) == 1` (Then 1) and `set(ids(result)) <= {A.id, B.id}` (Then 2), still non-strict BUG-1703. New: DMM-N-17 (`# [claude]`, `record_sql`), the strict order-free alarm for BUG-1700: no capped `SELECT … FROM delivery_methods … LIMIT` without `name` in its WHERE. `--runxfail`: N-17 fails in Then 3 (`assert not True`), S-06 in Then 1 (`2 == 1`). The reference plugin (`ref_fix.py`, `_check_name_exists` as one `WHERE … lower(btrim(name)) = … LIMIT 1`) passes all 91. 3 plain runs gave 61 passed, 30 xfailed each. Coverage is still 100% branch, `ruff` is clean, the file is LF. When BUG-1700 is fixed, N-17 XPASSes (red): remove its marker and N-13's together.
- **Cases rev 1 (2026-11-04)** — first implementation: 90 tests, 61 passed, 29 xfailed, 100% branch, `ruff` clean, LF line endings.
