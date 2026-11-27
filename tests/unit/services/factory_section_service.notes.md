# Execution notes — `app/services/factory_section_service.py`

> Cases: `tests/unit/services/factory_section_service.cases.md` (revision 1) · Tests: `tests/unit/services/test_factory_section_service.py` · Source commit: e48a092
> Result: 51 of 51 cases implemented · 27 passed · 24 xfail as designed (20 strict, all xfailed; 4 non-strict, C-10, L-09, L-11, L-12, xfailed in every run) · 0 errors · 0 discrepancies — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_factory_section_service.py -q -p no:cacheprovider` (about 3.5 s)

## How the tests are built
Same form as `department_service.notes.md` and `machine_item_service.notes.md`.
- **Standing rows:** chained fixtures in Conventions order: `w1`, `w2`, `u1`, `u2`, `f1`, `f2`, `f9`, `fd`, `fi` (autouse `standing_rows`), every factory `created_by` U1; FD carries `deleted_at` T0, `deleted_by` U1; FI `is_active False`.
- **Given rows:** `mk_section(name, **but)` (every column of the Conventions default written explicitly), `mk_sections(names)` for "n rows, by add_all", `gone` (dict for "but gone"), `mk_machine(factory, name)`, `mk_assignment(machine, section)`. Each builder flushes. "After the commit point" rows are built after `commit_point(db)` (= `db.commit()`, a savepoint release).
- **Reading helpers:** `reread` (sections), `snap_before` / `snap` (every column of any model's row, for `unchanged(X)` of sections, factories and assignments), `count_sections(**filters)`, `written` (row counts of `factory_sections`, `factories`, `machines`, `machine_section_assignments`), `ids`, `names`, `rows_of_section`, `unloaded`, `usable`.
- **`committed:` lines:** `db.rollback()` once before the first one, then fresh queries.
- **Patches:** only the failing commit / failing refresh wraps (C-06, C-07) and the race simulation of C-11 (`_check_name_exists_in_factory` → `False` on the manager instance). Nothing else.
- **Machine rows:** the Conventions list `workspace_id`, `factory_id`, `name`, `is_active`, `is_deleted`; `is_running` (NOT NULL) takes its model default `False`.

## Fails-today check
`--runxfail`, failing line mapped to its `# Then N`, value read; every card fails on its "Fails today on" line:
- Then 1 `DID NOT RAISE HTTPException`: C-09, C-10, C-11, G-04, G-07, U-07, U-10, U-11, D-05.
- Then 1 `TypeError … unexpected keyword argument 'include_deleted'`: G-05, G-08 (in the When), G-06 (inside Then 1's wrap), L-07 (`get_factory_sections`).
- U-09: Then 1, `IntegrityError` `factory_sections_factory_id_fkey` (Key (factory_id)=(0)), as the card says.
- C-08: Then 2, `'  Paint ' == 'Paint'`. U-08: Then 2, `updated_by` = U2's id, not None. D-04: Then 3, `len([]) == 2`.
- L-10: Then 1, `[H]` against `[]`. L-13: Then 1, `[]` against `[A, B]`. L-14: Then 1, both sections against `[]`. L-15: Then 2, `[A, H]` against `[A]`.
- Non-strict: L-09 / L-12 Then 2, insertion order `['Delta', 'alpha', 'echo', 'Bravo', 'charlie']`; L-11 Then 1, `[A]` against `[A, B]`; C-10 Then 1, `DID NOT RAISE` — in every run.

## Reference run
`refplug.py` (scratch, `svc2x/factory_section/`) replaced the five manager methods, the name check, and the two service reads (to accept `include_deleted`), changing only what each bug names:
- create: name trimmed (BUG-915); name check over all live sections of the factory, case-insensitive after trimming (BUG-911, BUG-912); an emulated partial unique index after the flush answering 409 (BUG-913);
- get: deleted section (BUG-916) or section of a deleted factory (BUG-925) is 404 unless `include_deleted=True`, workspace still checked;
- list: `factory_id is not None` (BUG-922), deleted rows and rows of deleted factories filtered in the query before paging (BUG-917, BUG-904, BUG-924), blank search no filter (BUG-921), `include_deleted` (BUG-920), ordered by `lower(name), id` (BUG-903, BUG-918);
- update: section of a deleted factory refused (BUG-926); `factory_id=0` checked like any id (BUG-923); a move of a section with assignments refused (BUG-928); name checked in the target factory on a plain move (BUG-914); `updated_by` only when a value changes (BUG-919);
- delete: section of a deleted factory refused (BUG-927); assignments kept (BUG-908).
With `--runxfail` all 51 tests passed; without it all 20 strict cards XPASSed (strict, so they failed) and the 4 non-strict cards XPASSed.

## Stability
5 plain runs plus `enable_seqscan=off` and `enable_indexscan/bitmapscan/indexonlyscan=off` (scratch `plans.py`, set on each new connection, verified with `SHOW`): 27 passed, 24 xfailed in all 7; no test moved. Ruff passes; no unused test arguments; LF.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (41 statements, no branches) of `app/services/factory_section_service.py`.

## Factories added
None.

## Notes for maintainers
- BUG-916 / BUG-925 / BUG-920 add an `include_deleted` parameter to the service; G-05, G-06, G-08, L-07 call it already.
- L-09, L-11, L-12 and C-10 are non-strict: today's order / page content comes from Postgres without `ORDER BY`. When BUG-903, BUG-917, BUG-918, BUG-911 are fixed they XPASS — remove the markers.
- When BUG-908 is fixed the delete no longer calls `machine_section_assignment_manager.clear_for_section`; D-04 then passes.
