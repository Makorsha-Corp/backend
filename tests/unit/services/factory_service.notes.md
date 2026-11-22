# Execution notes — `app/services/factory_service.py`

> Cases: `tests/unit/services/factory_service.cases.md` (revision 1) · Tests: `tests/unit/services/test_factory_service.py` · Source commit: e48a092
> Result: 39 of 39 cases implemented · 25 passed · 14 xfail as designed (11 strict, all xfailed; 3 non-strict, C-08, L-08, L-09) · 0 errors · 0 discrepancies — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_factory_service.py -q -p no:cacheprovider`

## How the tests are built
Same form as `department_service.notes.md`.
- **Actors:** chained fixtures `w1`, `w2`, `u1`, `u2` (autouse `actors`), so all four exist in every test as Conventions say. U1 acts; U2 is `created_by` of every Given row.
- **Given rows:** `mk_fac(**but)` (Convention "fac", flushed), `mk_facs(list_of_but)` (the `add_all` cards C-08, L-02), `gone(u2)`, `mk_line(factory)` ("line of F"), `mk_batch(line, status)` ("batch on L"). `commit_point(db)` = `db.commit()`; rows "after the commit point" are built after it and flushed.
- **Reading helpers:** `reread(db, row, model=Factory)`, `snap_before` / `snap` (every column, any model; `unchanged(B1)` in D-05 uses `ProductionBatch`), `count_facs(**filters)`, `written` (row counts of `factories`, `production_lines`, `production_batches`), `ids`, `unloaded`, `usable`.
- **`committed:` lines:** `db.rollback()` once before the first one, then fresh queries.
- **Patches:** the failing commit / refresh wraps (C-04, C-05); the race simulation of C-09 (`_check_name_exists` → `False`); the create patch of C-10; the delete patch of D-04. Nothing else.
- **Database errors:** reached through `user_id=MISSING` (`created_by` / `deleted_by` foreign keys), no savepoint around the call, as Conventions say (the service rolls back itself).

## Fails-today check
`--runxfail`, failing line mapped to its `# Then N`, value read; each matches the card's "Fails today on":
- Then 1 `DID NOT RAISE HTTPException`: C-07, C-08, C-09, G-04. D-05: Then 1 `DID NOT RAISE ValidationError` (the factory is deleted).
- G-05: `TypeError` (`include_deleted`) in the When; G-06: the same `TypeError` inside Then 1's wrap; L-06: `TypeError` in the When.
- C-06: Then 2, `' Main Plant ' == 'Main Plant'`. U-05: Then 2, `updated_by` = U1's id against U2's.
- L-08: Then 1, `[]` against `[A, B]`. L-09: Then 2, `['Delta', 'alpha', 'echo', 'Bravo']`. L-10: Then 1, `[]` against `[A, B, C]`.
- D-04: Then 1, the patched `ValueError('Factory has open production batches', [...])` escapes unchanged.

## Reference run
`refplug_factory.py` (scratch, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2x\factory\`) replaced, changing only what each bug names:
- manager `_check_name_exists` / `_check_abbreviation_exists`: all live rows, case-insensitive after trimming (BUG-893, BUG-894);
- manager `create_factory`: trimmed values (BUG-896), and the partial unique index emulated after the flush, surfacing as the 409 (BUG-895);
- manager `get_factory` and service `get_factory`: `include_deleted`, deleted hidden by default (BUG-897);
- manager `search_factories` and service `get_factories`: filter in the query before paging, `ORDER BY lower(name), id`, trimmed search, `include_deleted` passed through (BUG-898, BUG-899, BUG-901, BUG-902);
- manager `update_factory`: no `updated_by` stamp when nothing changes (BUG-900);
- manager `delete_factory`: `ValueError("Factory has open production batches", [{"type": "production_batch", "id": …}])` for batches not `completed` / `cancelled`; service `delete_factory`: rollback, then `AppValidationError(detail, errors)` (BUG-1331, both halves).
With `--runxfail` all 39 tests passed; without it the 11 strict cards XPASSed (strict, so they failed) and the 3 non-strict XPASSed.

## Stability
5 plain runs plus `enable_seqscan=off` and `enable_indexscan/bitmapscan/indexonlyscan=off` (scratch plugin `plans_factory.py`, settings verified with `SHOW`): 25 passed, 14 xfailed in 7 of 7. One further plain run (4th of the first five; 4 sibling test files were running on the same database at the time) gave 13 xfailed, 1 XPASS — one of the non-strict cards C-08, L-08, L-09, whose outcome depends on heap order of an unordered query (that is why they are non-strict); 43 further full runs (and 15 of the three cards alone) did not repeat it, so the card is not identified. No strict card moved. Ruff passes (repo config, plus `F841,F811` and an AST pass for unused fixture arguments); LF. The file runs in about 2.7 s.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (41 statements, no branches) of `app/services/factory_service.py`.

## Factories added
None.

## Notes for maintainers
- When BUG-897 / BUG-901 add `include_deleted`, G-05, G-06, L-06 stop raising `TypeError`; when BUG-1331 lands, D-04 and D-05 need both halves (D-04 the service translation only, D-05 the manager too).
- Spec gap 1 (an unknown-text `ValueError` out of delete) has no card; the reference plugin translates any `ValueError`, which is one reading of R3, not a decision.
- C-08 and L-02 insert 100 / 101 rows with `add_all`; each runs well under a second.
