# Execution notes — `app/services/project_component_note_service.py`

> Cases: `tests/unit/services/project_component_note_service.cases.md` (revision 3) · Tests: `tests/unit/services/test_project_component_note_service.py` · Source commit: e48a092
> Result: 64 of 64 cases implemented · 44 passed · 20 xfail as designed (17 strict, all xfailed; 3 non-strict, L-13, L-15, L-16, xfailed in every run) · 0 errors · 0 discrepancies — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_project_component_note_service.py -q -p no:cacheprovider`

## How the tests are built
Same form as `help_ticket_service.notes.md`: one test per card, in card order, `# [claude] <ID>` above each, `# Then N` before the checks of Then line N.
- **Standing rows:** fixture `S` (a `SimpleNamespace`) builds W0, W1, W2, U1 / U2 / UG with their W1 memberships (U2 `owner`, the others `ground-team`), F0 / F1 / F9, PJ0, PJ1 (`id=XID(1)`), PJP (`invited_only`), PJD (deleted), PJ9, C0, C1 (`id=XID(5)`), C2, CP, CD, C9, in the Conventions order, one flush each. Only tests that touch the database request it (the schema-only cards U-10 needs nothing; C-07 / C-08 / C-11 take `S` for `C1.id`).
- **Given rows:** `note(db, C, name, **but)` and `task(...)` (same row, `is_note=False`), `pmem(db, S, P, U)`, `_add` for the cards' literal rows (PJQ, CQ, CX, K1…K5). `commit_point(db)` = `db.commit()` (releases a savepoint under the `db` fixture). `extra_x(db, S)` (flushed, returns `X_ID`) and `pending_p(db, S)` (added, not flushed) run after the commit point.
- **Ids are copied to locals at the commit point** (`w1_id, ug_id = S.W1.id, S.UG.id` …) so a later expired attribute never fires a lazy load inside a spy, a recorder or after the service's rollback.
- **Checks:** `reread` (expire_all + `db.get`), `snap` / `unchanged` (every column of the model, taken at the commit point), `counts` (`project_component_tasks` and `project_events`, all workspaces = "nothing written"), `x_gone`, `events(db, project_id, type=None)` (`all_events` when no type), `idset`, `names`, `committed_row` (fresh SELECT after the one test-level `db.rollback()`), `spies`, `failing_commit`, `failing_refresh`, `recorder` (listener on `db.connection()`, removed right after the When), `order_part` (text of the recorded `SELECT … FROM project_component_tasks` after `ORDER BY`, before `LIMIT`).
- **DB errors:** L-20 wraps the call in `db.begin_nested()` inside `pytest.raises(DataError)`, as the Conventions say.
- No external is patched (the spec has none). The spies wrap the real `commit` / `rollback`.

## Fails-today check
`--runxfail` with a scratch plugin (`thenmap.py`) that maps the failing test-file line to its `# Then N`. Every xfail fails on the Then line its card names, with the value the card describes:
- L-05, G-09, C-06 (BUG-1278): Then 1, `DID NOT RAISE HTTPException`.
- L-11 (BUG-2294): Then 1, ND is in the set. L-12 (BUG-2293): Then 1, `set()`. L-13 (non-strict): Then 1, both VD and VE. L-14: Then 2, `5 <= 1`.
- L-15 (non-strict): Then 1, `['Zulu', 'apple', 'Banana']`. L-16 (non-strict): Then 1, insertion order. L-17: Then 2, `'name' in ''`.
- G-06, U-05 (BUG-2291): Then 1, the task row is returned. D-03: Then 1, `True is False`.
- C-07, C-08, U-10 (BUG-2290): Then 1, `DID NOT RAISE ValidationError`. C-09: Then 2, `'  Supplier  call  '`. U-09: Then 2, `'  New  '`.
- U-07, U-08 (BUG-2295): Then 2, `1 == 0`.

## Reference run
`refplug_note.py` (scratch `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvce\C\`, loaded with `-p`, PYTHONPATH = that folder, shared helpers in `refcommon.py`) patches in memory, before the test module is imported: a deleted project answers 404 `Project with ID {id} not found` from `project_manager._get_project_or_404` (BUG-1278); `ProjectComponentNoteCreate` / `Update` subclasses that trim the name and refuse a blank one (BUG-2290); `get_by_id_and_workspace` returning `None` for a non-note (BUG-2291); the workspace-wide `get_notes` as one statement joining component and project (same workspace, project not deleted, caller may open it), ordered by `lower(name), id`, paged after the filter (BUG-2292, BUG-2293, BUG-2294); `update_note` writing no event when no sent value differs (BUG-2295).
- With `--runxfail`: **64 passed** (revision 3). Without it: the 17 strict cards XPASS (strict → failed) and the 3 non-strict ones XPASS.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (71 statements, 14 branches).

## Factories added
None.

## Notes for maintainers
- When a bug is fixed its cards XPASS: remove the marker. BUG-1278 lives in `app/managers/project_manager.py` (shared with the task and item services and `PRJM-RC-09`); BUG-2290 in `app/schemas/project_component_note.py`; BUG-2291 … BUG-2295 in the service.
- L-13, L-15, L-16 are non-strict: they rest on today's physical row order (no `ORDER BY`).
- L-14 counts statements containing `project_components`; the main query reads `project_component_tasks`, which does not contain that text. A fix that joins components in one statement passes; a fix that preloads components in a second statement fails (the card allows at most one).
- XID ids come from the pid, so parallel runs never collide on PJ1 / C1.
- Verified: 3 plain runs 44 passed / 20 xfailed each (revision 3); ruff check and format clean; LF.

## Revision history
- **Revision 3 (2026-11-06)** — cases revision 3 (from `project_component_note_service.verify.md` findings 1 and 2, plus G-10). Added `test_pcns_l_22__one_component_read_no_commit_no_rollback` (PCNS-L-22: spied one-component read), `test_pcns_l_23__other_workspaces_notes_do_not_shorten_the_page` (PCNS-L-23: W0 and W2 notes ahead of the page, `limit=2` gives NC, ND) and `test_pcns_g_10__one_row_read_no_commit_no_rollback` (PCNS-G-10: spied one-row read); all three pass. No existing test changed; no card changed or retired. Re-verified: 44 passed / 20 xfailed in each of 3 plain runs; `--runxfail` gives the same 20 failures on the same Then lines as revision 2; the reference plugin needed no change and gives 64 passed under `--runxfail`; branch coverage of the service 100%; ruff check and format clean; LF.
