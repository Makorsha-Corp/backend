# Execution notes — `app/services/work_order_type_service.py`

> Cases: `tests/unit/services/work_order_type_service.cases.md` (revision 1) · Tests: `tests/unit/services/test_work_order_type_service.py` · Source commit: e48a092
> Result: 28 of 28 cases implemented · 23 passed · 5 xfail as designed (all strict, all xfailed) · 0 errors · 0 discrepancies — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_work_order_type_service.py -q -p no:cacheprovider`

## How the tests are built
Same form as `department_service.notes.md`: normal mode, `# [claude] <ID>`, `# Then N`, lower-case row names. Actors `w1`, `w2`, `u1`, `u2` (autouse `actors`). `mk_type(**but)` / `mk_types([…])` build `WorkOrderType` rows (name "Repair", `created_by` U2); `gone(u2)`; `commit_point(db)`; `reread`, `snap_before` / `snap`, `count_types`, `written`, `unloaded`, `usable`. The schemas the cards use (`WorkOrderTypeCreate`, `WorkOrderTypeUpdate` from `app.schemas.work_order_type`) are the real ones, as spec G1 says. Nothing is patched except the failing commit / refresh wraps.

## Fails-today check
`--runxfail`, failing line mapped to its `# Then N`:
- C-05 (BUG-1214): `IntegrityError` 23505 on `uq_wo_type_workspace_name` in the When, just before `# Then 1`. That is the card's text.
- G-04: Then 1, `DID NOT RAISE HTTPException`.
- G-05, L-06: `TypeError` (no `include_deleted`) in the When; G-06 the same `TypeError` inside Then 1's wrap.

## Reference run
`refplug.py` (scratch) replaced the five service methods with the spec's intended behaviour (`include_deleted` on get and list). Inside each test's own transaction, `uq_wo_type_workspace_name` was dropped and replaced by a unique index on live rows only (BUG-1214), all rolled back with the test. With `--runxfail` all 28 tests passed. Without it all 5 strict cards XPASSed (strict, so they failed).

## Stability
5 plain runs plus seqscan off and index/bitmap scans off: 23 passed, 5 xfailed in all 7; no test moved. Ruff passes; LF.

## Discrepancies
None. The schema names in the cards (spec gap G1) are the real ones.

## Coverage gaps
None — 100% branch coverage (41 statements) of `app/services/work_order_type_service.py`.

## Factories added
None.

## Notes for maintainers
- BUG-1214's fix changes the unique constraint into a partial one on live rows. C-05 then passes; until then two rows of one workspace never share a name in any Given.
- The manager has no spec yet. L-01 … L-04 and L-08 rely only on the search described in spec Facts (G2), on rows that fit one page.
