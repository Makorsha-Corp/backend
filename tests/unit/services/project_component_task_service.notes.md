# Execution notes — `app/services/project_component_task_service.py`

> Cases: `tests/unit/services/project_component_task_service.cases.md` (revision 3) · Tests: `tests/unit/services/test_project_component_task_service.py` · Source commit: e48a092
> Result: 88 of 88 cases implemented · 61 passed · 27 xfail as designed (24 strict, all xfailed; 3 non-strict, L-18, L-20, L-21, xfailed in every run) · 0 errors · 0 discrepancies — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_project_component_task_service.py -q -p no:cacheprovider`

## How the tests are built
Same scaffold as `project_component_note_service.notes.md` (the two cases files share Conventions): fixture `S` with the standing rows in Conventions order (PJ1 `id=XID(1)`, C1 `id=XID(5)`), `task(db, C, name, **but)` / `note(...)`, `pmem`, `commit_point`, `extra_x` / `pending_p` (no `is_note`, so the model default `False`), `reread`, `snap` / `unchanged` (every column), `counts` (`project_component_tasks`, `project_events`), `x_gone`, `events` / all events, `META(S, task_id, name)`, `idset`, `names`, `committed_row`, `spies`, `failing_commit`, `failing_refresh`, `recorder`, `order_part`. One test per card, `# [claude] <ID>`, `# Then N`.
- Ids are copied to locals at the commit point; D-01 builds `META` before the call for the same reason.
- `HIGH` / `URGENT` = `TaskPriorityEnum.HIGH` / `.URGENT` (`app.models.enums`).
- L-25 / L-26 wrap the call in `db.begin_nested()` inside `pytest.raises(DataError)`.
- No external is patched.

## Fails-today check
`--runxfail` with the scratch `thenmap.py` plugin. Every xfail fails on its card's Then line with the value the card describes:
- L-05 (BUG-2301): Then 1, `DID NOT RAISE HTTPException` (the workspace-wide list is returned).
- L-08, G-09, C-08, U-25, D-06 (BUG-1278): Then 1, `DID NOT RAISE HTTPException`.
- L-14 (BUG-2302): Then 1, TG in the set. L-15, L-16 (BUG-2300): Then 1, NN (and TD) in the set.
- L-17 (BUG-2298): Then 1, `set()`. L-18 (non-strict): Then 1, VD and VE. L-19: Then 2, `5 <= 1`.
- L-20 (non-strict): Then 1, `['Zulu', 'apple', 'Banana']`. L-21 (non-strict): Then 1, insertion order. L-22: Then 2, `'name' in ''`.
- C-09, C-10, U-22 (BUG-2297): Then 1, `DID NOT RAISE ValidationError`. C-11: Then 2, `'  Weld  frame  '`. U-21: Then 2, `'  Weld base  '`.
- U-08 (BUG-2304): Then 2, priority still `HIGH`. U-10, U-11: Then 1, `DID NOT RAISE ValidationError`.
- U-12, U-13 (BUG-2303): Then 2, `1 == 0`. U-15, U-27 (BUG-2305): Then 2, `0 == 1`.

## Reference run
`refplug_task.py` (scratch `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvce\C\`, with `refcommon.py`) patches in memory: BUG-1278 (as in the note notes); `ProjectComponentTaskCreate` / `Update` subclasses that trim the name, refuse a blank one (BUG-2297) and refuse an explicit `null` for name, description, completion and kind (BUG-2304); `get_tasks` sending `0` through the guard (BUG-2301) and the workspace-wide list as one joined, filtered statement (project not deleted, caller may open it) with the open-only / kind filters (`incomplete_only` without a kind = open tasks) ordered by `lower(name), id` and paged after the filter (BUG-2298, BUG-2299, BUG-2300, BUG-2302); `update_task` applying the sent fields with `exclude_unset` (an explicit `null` priority clears it, BUG-2304), writing no event when nothing changed (BUG-2303) and choosing the event from the row's kind before the update (a task turned into a note is logged, BUG-2305).
- With `--runxfail`: **88 passed** (revision 3). Without it: the 24 strict cards XPASS (strict → failed), the 3 non-strict ones XPASS.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (81 statements, 24 branches).

## Factories added
None.

## Notes for maintainers
- When a bug is fixed its cards XPASS: remove the marker. BUG-1278 lives in `app/managers/project_manager.py`; BUG-2297 and the schema half of BUG-2304 in `app/schemas/project_component_task.py`; the clear-priority half of BUG-2304 is `BaseDAO.update`'s `exclude_none=True`, so its fix must not change other DAOs' behaviour; BUG-2298 … BUG-2303, BUG-2305 in the service.
- L-18, L-20, L-21 are non-strict: today's order is physical (base `get_by_workspace` has no `ORDER BY` until BUG-100).
- PCTS-U-28 (revision 3) passes: `HIGH` → `URGENT` stores and logs `task_updated`.
- Verified: 3 plain runs 61 passed / 27 xfailed each (revision 3); ruff check and format clean; LF.

## Revision history
- **Revision 3 (2026-11-06)** — cases revision 3 (from `project_component_task_service.verify.md` finding 1, plus G-10). Added `test_pcts_l_29__one_component_read_no_commit_no_rollback` (PCTS-L-29: spied one-component read) and `test_pcts_g_10__one_row_read_no_commit_no_rollback` (PCTS-G-10: spied one-row read); both pass. No existing test changed; no card changed or retired (surviving mutant #40 is equivalent, no card). Re-verified: 61 passed / 27 xfailed in each of 3 plain runs; `--runxfail` gives the same 27 failures on the same Then lines as revision 2; the reference plugin needed no change and gives 88 passed under `--runxfail`; branch coverage of the service 100%; ruff check and format clean; LF.
