# Execution notes — `app/services/project_service.py`

> Cases: `tests/unit/services/project_service.cases.md` (revision 4) · Tests: `tests/unit/services/test_project_service.py` · Source commit: e48a092
> Result: 79 of 79 cases implemented · 64 passed · 15 xfailed (all strict bug cards) · 0 errors · 0 open discrepancies (DISCREPANCY-1 settled by cases revision 3) — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_project_service.py -q -p no:cacheprovider`

## How the tests are built
Same form as `help_ticket_service.notes.md` and `managers/test_project_manager.py`: one test per card, in card order, `# [claude] <ID>` above each, `# Then N` before the checks of Then line N.
- **Standing rows:** autouse fixture `S` builds W0, W1, W2 (`make_workspace`), U1 / U2 / UG with their W1 memberships (ground-team, owner, ground-team), F0, F1, F2, FD (deleted), F9, each flushed, in the Conventions' order. Attributes carry the card names (`S.W1`, `S.UG`, `S.F9` ...).
- **Given rows:** `proj(db, S, name, where=, private=, deleted=, **but)`, `member`, `pmem(..., **but)` (`assigned_at`), `ev`, `bulk(db, S, n)` (one `insert(Project)` with the listed columns, then `expire_all`). `commit_point(db)` = `db.commit()` (releases a savepoint). `extra_x` adds and flushes the W2 row X and returns `X_ID`; `x_count` gives the count for x_gone (0) / x_kept (1). `edit(row)` sets `description = "Edited"` unflushed.
- **Checks:** `snap` (refresh at the commit point, every column) / `unchanged(db, Model, before)` (expire_all + `db.get`, compare every column), `counts` (projects, project_members, project_events, all workspaces), `events_of`, `members_of`, `reread`, `w1_projects`. Ids are copied to locals at the commit point, so checks after the service's rollback never depend on an expired instance. Every `committed:` block starts with one `db.rollback()`.
- **Externals:** autouse `clock` patches `app.managers.project_manager.utcnow` to NOW. `spies` wraps `commit`, `rollback`, `refresh` (yields `cm, rb, rf`); `failing_commit` (commit raises `RuntimeError("boom")`, rollback spy), `failing_refresh` (refresh raises). `recorder` listens on `db.connection()` `before_cursor_execute` and is removed right after the When.
- LM-05 … LM-07 call the endpoint function `list_project_members(project_id=, workspace=S.W1, current_user=, db=)` directly.
- C-04 builds `ProjectCreate.model_construct(...)` with `budget=Decimal("100000000000000000000")` (written as the card writes it; `FURB157` is in the file-level noqa).

## Fails-today check
`--runxfail` with a scratch plugin (`then_check.py`) recording the last test-file line of each failure, mapped to its `# Then N` by `then_report.py` (both in the scratch folder below). All 15 bug cards fail on the Then line their card names, with the value the card describes:
- C-07: Then 2, `'  Line 3 refit '`. U-08: Then 2, `updated_by` is U2's id. U-09: Then 2, `Decimal('1000.00') is None`.
- G-04, LM-02, AM-06, RM-06: Then 1, `DID NOT RAISE HTTPException`.
- L-07: Then 1, `set()`. L-08, L-09: Then 1, both visible rows. L-10: Then 1, `['Zulu', 'apple', 'Banana']`. L-11: Then 1, both projects. L-12: Then 1, AP and AC.
- EV-05: Then 2, `6 <= 3`. LM-05: Then 2, `(14 - 1) - 3 = 10 <= 2` (two statements per member, as the card says).
- Revision 3: re-checked, 15 of 15 on their named Then line, 0 mismatches; no other test fails under `--runxfail`.

## Reference run
`ref_pjs.py` (scratch, loaded with `-p ref_pjs`, `PYTHONPATH` = scratch folder) patches in memory, as the project_manager reference fix does: fixed `ProjectCreate` / `ProjectUpdate` (BUG-1951 stripped non-blank name, BUG-1953 nulls), `require_project_access(include_deleted=False)` and `get_project` (BUG-1954, BUG-1278), `update_project` stamping only on a change and keeping explicit nulls (BUG-1952, BUG-1953), `delete_project` / `set_visibility` / `list_events` still reaching a deleted project, `list_events` reading performers in one `IN` query (BUG-1964), one filtered `list_projects` query (live projects of live factories, factory `is not None`, factory AND status, access filter in SQL, `lower(name), id`, then paging: BUG-1955, 1957, 1958, 1959, 1960). BUG-2271: the endpoint module's `project_service`, `profile_dao` and `workspace_member_dao` are replaced by proxies that read the listed members' profiles and W1 memberships in one statement each and answer the per-member lookups from them.
- With `--runxfail` (revision 3, `REF_LOAD_RELS` unset): **77 passed**.
- Revision 2 history: 72 passed, 5 failed (the DISCREPANCY-1 cards); with `REF_LOAD_RELS=1` (a test-side switch making `Session.refresh` also load lazy relationships) 77 passed. The switch is no longer needed.

## Discrepancies
| ID | Case | Designed | Actual | Evidence | Likely cause |
|---|---|---|---|---|---|
| DISCREPANCY-1 (settled, cases revision 3) | PJS-C-01 (Then 3), PJS-U-01 (Then 2), PJS-D-01 (Then 2), PJS-AM-01 (Then 3), PJS-SV-01 (Then 2) | pass: `inspect(result).expired_attributes == set()` | fails: the set holds only the lazy relationships (`Project`: `members`, `components`, `factory`, `attachments`, `miscellaneous_costs`; `ProjectMember`: `project`, `user`, `assigner` ...) | `db.refresh()` reloads every column but leaves lazy relationships unloaded (SQLAlchemy's documented behaviour); with relationships loaded after the refresh (reference run `REF_LOAD_RELS=1`) the line holds and all later checks pass | Card defect: "returned re-read" should be checked on column attributes only, e.g. `inspect(result).expired_attributes & {c.key for c in inspect(Project).mapper.column_attrs} == set()`. Back to the designer; marked `xfail(strict=True, reason="DISCREPANCY-1 ...")`. The same check appears in `access_control_service.cases.md` and `workspace_service.cases.md` (models with relationships fail it the same way). |

## Coverage gaps
None — 100% (74 statements; the service has no branch of its own).

## Factories added
None.

## Notes for maintainers
- When a bug is fixed its cards XPASS (strict → failed): remove the marker. BUG-1951 / 1953 live in `app/schemas/project.py` and `project_manager.update_project`; BUG-1952, 1954, 1955, 1957 … 1960, 1964, 1278 in `app/managers/project_manager.py`; BUG-2271 in `app/api/v1/endpoints/projects.py`.
- LM-05 counts statements after the last `FROM project_members` read; a fix that reads the members together with profiles in one join must keep that statement recognisable or the count changes meaning.
- Lists cards rely on the hidden rows having the lowest ids and names (L-07 … L-09), so they fail strictly whatever order the fix picks.

## Scratch
`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvce\B\` — `ref_pjs.py`, `then_check.py`, `then_report.py`, `.coverage.PJS`.

## Revision history
- **Revision 3 (2026-11-05)** — cases revision 3 (from DISCREPANCY-1). C-01 (Then 3), U-01, D-01, SV-01 (Then 2) and AM-01 (Then 3) now assert `not ({c.key for c in inspect(result).mapper.column_attrs} & inspect(result).expired_attributes)` as written; the `DISC_1` marker and its definition are removed; header points at revision 3. No other test changed; no ID retired. Re-verified: 62 passed / 15 xfailed in each of 3 plain runs; `--runxfail`: the 15 strict bug cards fail on their named Then lines (0 mismatches), nothing else fails; reference plugin with `--runxfail` and without `REF_LOAD_RELS`: 77 passed; branch coverage 100%; ruff check and format clean; LF.
- **Revision 4 (2026-11-06)** — cases revision 4 (verifier finding 1). Added `test_pjs_l_15__status_filter_before_paging` (PJS-L-15: two PLANNING rows ahead, `status="COMPLETED", limit=2` → both COMPLETED rows) and `test_pjs_l_16__factory_filter_before_paging` (PJS-L-16: two F1 rows ahead, `factory_id=F2, limit=2` → both F2 rows), placed after L-14; both pass. No existing test changed; no ID retired; the reference plugin needed no change. Re-verified: 64 passed / 15 xfailed in each of 3 plain runs; `--runxfail`: 15 of 15 strict cards fail on their named Then line (0 mismatches); `ref_pjs.py` with `--runxfail`: 79 passed; branch coverage 100%; ruff check and format clean; LF.
