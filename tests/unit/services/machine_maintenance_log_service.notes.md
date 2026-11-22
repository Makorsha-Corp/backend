# Execution notes — `app/services/machine_maintenance_log_service.py`

> Cases: `tests/unit/services/machine_maintenance_log_service.cases.md` (revision 1) · Tests: `tests/unit/services/test_machine_maintenance_log_service.py` · Source commit: e48a092
> Result: 35 of 35 cases implemented · 22 passed · 13 xfail as designed (12 strict, all xfailed; 1 non-strict, L-08, xfailed in every run) · 0 errors · 0 discrepancies — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_machine_maintenance_log_service.py -q -p no:cacheprovider`

## How the tests are built
Same form as `department_service.notes.md`.
- **Standing rows:** chained fixtures in Conventions order: `w1`, `w2`, `u1`, `u2`, `u3`, `f1`, `fd`, `f9`, `m1`, `m2`, `md`, `mf`, `m9`, ending in the autouse `standing_rows`.
- **Given rows:** `mk_log(**but)` inserts a log, flushes, then `db.refresh(row)` (Conventions); `bulk101()`; `gone(u1)`.
- **Reading helpers:** `reread`, `snap_before` / `snap` (log columns), `count_logs(**filters)`, `count_events`, `written` = both counts, `events_of(m)`, `ids`, `unloaded`, `usable`.
- **"that row":** the test keeps `rows = events_of(db, m1)` from the count line and checks `rows[0]`, so the count and the row come from one read.
- **Patches:** the failing commit / refresh wraps; the clock patch `patch("app.dao.machine_maintenance_log.utcnow", create=True, return_value=NOW)` on D-04 only.
- **`Decimal("-5")`, `Decimal("7")`:** kept as the cards write them, with `# noqa: FURB157`.
- C-04 builds the input with `LC.model_construct(...)` (`performed_by` of 256 characters) and gets `DataError` 22001; C-11 gets `IntegrityError` 23503 from an unknown `user_id`. Both are ordinary passes.

## Fails-today check
`--runxfail`, failing line mapped to its `# Then N`, value read:
- C-07 (BUG-1154), G-03 (BUG-1150), G-05 (BUG-1101): Then 1 `DID NOT RAISE HTTPException`. C-10 (BUG-1158): Then 1 `DID NOT RAISE ValidationError`.
- C-08: Then 2 `'  pad  '`. C-09: Then 2 `'  Rahim  '`. U-04: Then 2 `updated_by` is U2. U-05: Then 2 `Decimal('5.00') is None`. U-06: Then 4 `to_value: '7'` against `'7.00'`. L-07: Then 1, one row against `[]`. D-04: Then 3, the database's `now()` against `NOW`.
- G-04: `TypeError` (no `include_deleted`) in the When.
- L-08 (non-strict, BUG-1100): Then 2 `[A, B, C]` against `[C, B, A]`, in every run.

## Reference run
`refplug.py` (scratch) wrapped the service's five methods, changing only what each bug names. It refused a machine of a deleted factory, skipped the stamp on an empty body, stored cost in its two-decimal form and let an explicit null clear it. It gave `get_log` `include_deleted` plus the machine-workspace check, listed with `machine_id` tested against `None` in `maintenance_date DESC, id DESC` order, and took `deleted_at` from the DAO clock. `MachineMaintenanceLogCreate` was replaced in memory by a subclass that trims `summary` and `performed_by` and refuses a negative cost. With `--runxfail` all 35 tests passed; without it all 12 strict cards XPASSed (strict, so they failed) and L-08 XPASSed.

## Stability
5 plain runs plus seqscan off and index/bitmap scans off: 22 passed, 13 xfailed in all 7; no test moved. Ruff passes; LF.

## Discrepancies
None. The `IntegrityError` note (spec G1, MLS-C-11) holds: 23503 at the flush, nothing saved, session usable.

## Coverage gaps
None — 100% branch coverage (42 statements) of `app/services/machine_maintenance_log_service.py`.

## Factories added
None.

## Notes for maintainers
- BUG-1150: G-04 calls with `include_deleted` today and fails on the `TypeError`.
- `nothing written` counts all workspaces' logs and activity events; `marker_test` must hold none committed (it held none on 2026-11-03).
