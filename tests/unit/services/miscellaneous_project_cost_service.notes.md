# Execution notes — `app/services/miscellaneous_project_cost_service.py`

> Cases: `tests/unit/services/miscellaneous_project_cost_service.cases.md` (revision 2) · Tests: `tests/unit/services/test_miscellaneous_project_cost_service.py` · Source commit: e48a092
> Result: 89 of 89 cases implemented · 61 passed · 28 xfail as designed (27 strict, all xfailed; 1 non-strict, L-15, xfailed or xpassed depending on physical row order) · 0 errors · 0 discrepancies — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_miscellaneous_project_cost_service.py -q -p no:cacheprovider -o addopts=""`

## How the tests are built
Same form as `project_component_note_service.notes.md`: one test per card, in card order, `# [claude] <ID>` above each, `# Then N` before the checks of Then line N.
- **Standing rows:** fixture `S` builds W0, W1, W2, U1 / U2 / UG with their W1 memberships (U2 `owner`, the others `ground-team`), F0 / F1 / F9, PJ0, PJ1 (`id=XID(1)`), PJ2 "Yard", PJP (`invited_only`), PJD (deleted), PJ9, C0, C1 (`id=XID(5)`), C2 "Gate", CP, CD, C9, in the Conventions order, one flush each. The schema-only cards C-16, C-17, C-22 take `S` only for `PJ1.id`; U-12, U-13 need nothing.
- **Given rows:** `cost(db, S, **but)`, `cost_on(db, S, C)` ("on C only"), `cost_unlinked(db, S)`. `commit_point(db)` = `db.commit()` (releases a savepoint). `extra_x(db, S)` returns `(X, X_ID)` after the commit point.
- **Ids are copied to locals at the commit point**, so no expired attribute fires a lazy load inside a spy, a recorder or after the service's rollback.
- **Checks:** `reread`, `snap` / `unchanged` (every column, taken at the commit point; amounts as `Decimal`), `counts` (`miscellaneous_project_costs` and `project_events`, all workspaces = "nothing written"), `x_count` (x_kept / x_gone), `events(db, project_id, type)`, `all_events(db, w1_id)` (W1 only), `idset`, `ids`, `committed_row` (fresh SELECT after the one test-level `db.rollback()`), `spies`, `failing_commit`, `failing_refresh`, `recorder`, `order_part` (text of the recorded `SELECT … FROM miscellaneous_project_costs` after `ORDER BY`, before `LIMIT`).
- **DB errors:** L-17 wraps the call in `db.begin_nested()` inside `pytest.raises(DataError)`.
- **No external is patched** (the spec lists none). The spies wrap the real `commit` / `rollback`; the failing commit / refresh are the Conventions' own.
- **xfail reasons:** `"BUG-n: <bugs.md title>"`. BUG-2611 … BUG-2618 carry `(revisit after launch)`: their register status is "open — revisit after launch" (projects deferred, owner 2026-11-10), and BUG-2614's cards are also tagged `Revisit` on the card. Pass cards with a `Revisit` header carry `revisit after launch (owner 2026-11-10)` in the docstring (LA-05, G-12, C-15, C-19, C-20, U-11, D-06).

## Fails-today check
`--runxfail` with a scratch plugin (`thenmap_misc.py`, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\authe\misc\`) that maps the last failing line inside the test function to its `# Then N`. Every xfail fails on the Then line its card names:
- LA-04 (BUG-1192), L-04, G-10, C-09 (BUG-1278), L-05, L-09 (BUG-2614), C-12, C-13 (BUG-2615), C-14 (BUG-1013): Then 1, `DID NOT RAISE HTTPException`.
- C-10, C-11 (BUG-2614): Then 1, `IntegrityError` (FK violation; the guard is skipped), as the card says.
- FA-05, L-11 (BUG-2612): Then 1, the deleted project's cost is kept. L-12 (BUG-2611): Then 1, `set()`. L-13: Then 2, `5 <= 1`. L-14 (BUG-100): Then 2, `'id' in ''`. L-15 (non-strict): Then 1, `[KB, KC, KA]` when it fails.
- G-11, U-06 (BUG-2616): Then 1, the cost is returned. D-05: Then 1, `True is False`.
- C-16, C-17, U-12 (BUG-2613), C-22, U-13 (BUG-2618): Then 1, `DID NOT RAISE ValidationError`. C-18: Then 2, `'  Crane  hire '`.
- U-08, U-09 (BUG-2617): Then 2, `1 == 0`.

## Reference run
`ref_misc.py` (same scratch folder, loaded with `-p ref_misc`, PYTHONPATH = that folder) patches in memory at `pytest_configure`, before the test module is imported: `MiscellaneousProjectCostCreate` / `Update` subclasses that trim the name, refuse a blank one, and refuse more than 13 integer digits (BUG-2613, BUG-2618); a project guard that answers 404 for a deleted project (BUG-1278); `_log_cost_activity` refusing a project of another workspace (BUG-1192); `_filter_accessible_costs` dropping deleted projects (BUG-2612); `get_costs` with "given = not None" (BUG-2614) and the workspace-wide list as one statement (outer join to the workspace's components, accessible non-deleted project ids, `ORDER BY id`, paged after the filter; BUG-100, BUG-2611); `get_by_id` returning `None` for a foreign component (BUG-2616); `create_cost` checking the component when both ids are sent in the G2 order 404 → 403 → 400 (BUG-2615, BUG-1013); `update_cost` writing no event when no sent value differs (BUG-2617).
- With `--runxfail`: **89 passed**.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (89 statements, 30 branches).

## Factories added
None.

## Notes for maintainers
- L-15 is non-strict: today's order is physical (no `ORDER BY`, BUG-100). In three plain runs it xfailed once and xpassed twice (`61 passed, 27 xfailed, 1 xpassed`); both are as designed. L-14 is the strict alarm for the missing `ORDER BY`.
- When a bug is fixed its cards XPASS (strict → failed): remove the marker. BUG-1278 and BUG-1192 live in `app/managers/project_manager.py` (shared with other project services); BUG-2613 / BUG-2618 in `app/schemas/miscellaneous_project_cost.py`; BUG-100 in `app/dao/base.py`; the rest in the service.
- L-13 counts statements containing `FROM project_components`; a fix that joins components into the cost query passes, one that preloads them in a second statement also passes (at most one), one read per cost fails.
- C-10 / C-11 fail today with `IntegrityError` raised inside Then 1's `pytest.raises(HTTPException)` — a strict xfail accepts any exception, so they stay honest.
- XID ids come from the pid, so parallel runs never collide on PJ1 / C1.
- Future permissions work (`docs/future/permissions.md`, spec "Permission checks"): the only check is "may open the project"; any such member may add, change or delete any cost, whoever entered it (no author column), and sees every amount. No notification is sent by this module.
- Verified: 3 plain runs (61 passed / 28 xfailed, then 61 / 27 / 1 xpassed twice — L-15 only); `--runxfail` 28 failures on the named Then lines; reference plugin 89 passed; ruff check and format clean; LF.
