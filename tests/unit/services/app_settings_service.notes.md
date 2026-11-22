# Execution notes — `app/services/app_settings_service.py`

> Cases: `tests/unit/services/app_settings_service.cases.md` (revision 2) · Tests: `tests/unit/services/test_app_settings_service.py` · Source commit: e48a092
> Result: 39 of 39 cases implemented · 33 passed · 6 xfail as designed (5 strict, all xfailed; 1 non-strict, L-05, xfailed in every run) · 0 errors · 0 discrepancies — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_app_settings_service.py -q -p no:cacheprovider`

## How the tests are built
Same form as `department_service.notes.md`. This service has no manager and its own transaction (S1–S5).
- Actors `w1`, `w2` (autouse). `mk_setting(**but)` (name "feat", enabled True). Helpers: `commit_point`, `reread`, `snap_before` / `snap`, `count_settings`, `written`, `ids`, `unloaded`, `usable`.
- **spies:** a context manager that patches `commit` and `rollback` with `wraps=`, so both still run.
- **Statement recorder (L-06):** a `before_cursor_execute` listener on `db.connection()`, removed after the call. `the_select` picks the one `SELECT` from `app_settings`; `order_part_of` takes the text between `ORDER BY` and `LIMIT`, or `""` when there is no `ORDER BY`.
- L-07 asserts the aborted session as Conventions say: `db.execute(text("SELECT 1"))` raises `DBAPIError` (`InFailedSqlTransaction`).

## Fails-today check
`--runxfail`, failing line mapped to its `# Then N`, value read:
- L-06 (revision 1): Then 2 `'lower(' in ''`. Today there is no `ORDER BY` at all, so `order_part` is empty, as the revised card says.
- C-03: Then 1 `DID NOT RAISE ValidationError`. C-04: Then 2 `' Feat '`. C-06, C-07: Then 1 `DID NOT RAISE IntegrityError`.
- L-05 (non-strict): Then 2 `['zeta', 'Alpha', 'beta']`, in every run.

## Reference run
`refplug.py` (scratch) replaced `get_settings` with `ORDER BY lower(name), id` before the page, and `AppSettingsCreate` with a subclass that trims and refuses a blank name. Inside each test's transaction it created a unique index on `(workspace_id, lower(btrim(name)))` (BUG-1225). With `--runxfail` all 38 tests passed, including L-06 Then 3 … 6 on the emitted SQL (`ORDER BY lower(app_settings.name), app_settings.id` before `LIMIT`). Without it all 5 strict cards XPASSed (strict, so they failed) and L-05 XPASSed.

## Stability
5 plain runs plus seqscan off and index/bitmap scans off: 32 passed, 6 xfailed in all 7; no test moved. Ruff passes; LF.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (45 statements, 4 branches) of `app/services/app_settings_service.py`.

## Factories added
None.

## Revision history
- **Cases revision 2:** added ASV-L-09 (default `limit`, from verify Finding 1 / R-AS-1); pass. No other test changed. 3 plain runs of the three revised files: 110 passed, 43 xfailed, 1 xpassed (ITS-T-08) each; the reference with `--runxfail` 154 passed. Verifier variant `get_settings_arg_limit_default` (default `limit` 101), rebuilt in scratch `varplug.py`: L-09 fails at Then 1, `101 == 100`.

## Notes for maintainers
- L-06's `order_part` is cut at the literal `LIMIT`; SQLAlchemy renders `LIMIT` after `ORDER BY` on PostgreSQL.
- `nothing written` and the absolute counts read all workspaces; `marker_test` must hold no committed `app_settings` rows.
