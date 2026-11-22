# Execution notes — `app/services/department_service.py`

> Cases: `tests/unit/services/department_service.cases.md` (revision 0) · Tests: `tests/unit/services/test_department_service.py` · Source commit: e48a092
> Result: 34 of 34 cases implemented · 22 passed · 12 xfail as designed (8 strict, all xfailed; 4 non-strict, all xfailed in every run) · 0 errors · 0 discrepancies — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_department_service.py -q -p no:cacheprovider`

## How the tests are built
Normal mode, no local model. The first service tests of the project; the seven sibling files follow the same form. Every test carries `# [claude] <ID>`, a `# Then N` comment before the checks of each Then line, and its card's rules in the docstring. Row names are the cards' names in lower case (`A` → `a`, `W1.id` → `w1.id`).

- **Actors:** chained fixtures `w1`, `w2`, `u1`, `u2`, `u3` and an autouse `actors`, so they exist in every test with ids rising in Conventions order. `svc`, `MISSING`, `T0` are module-level.
- **Given rows:** `mk_dept(**but)` inserts one `Department` and flushes; `mk_depts([but, …])` is the cards' "n rows, by `add_all`". `gone(u2)` is the "gone" column set.
- **Commit point:** `commit_point(db)` = `db.commit()`, a savepoint release under the `db` fixture. Rows a card marks "(after the commit point)" are built after it and stay uncommitted.
- **Reading helpers:** `reread` (expire, then SELECT), `snap_before` (columns read from the table right after the commit point) and `snap` (expire, then the same read), `count_depts(**filters)` (all workspaces), `written` (= count of all `departments`), `unloaded(result)` = `inspect(result).unloaded`, `usable(db)`. Helpers hold no assertion.
- **`committed:` lines:** `db.rollback()` once before the first one, then fresh reads. After a rollback the test re-reads by an id saved beforehand (`result_id = result.id`), so nothing reads an expired object.
- **Failing commit / refresh:** exactly the Conventions wraps; `patch.object(db, "rollback", wraps=db.rollback)` counts rollbacks and still runs them.
- **Race simulation:** DSV-C-09 only, `patch.object(svc.department_manager, "_check_name_exists", return_value=False)`. Nothing else is patched.

## Fails-today check
Every xfail was run with `--runxfail` and a scratch plugin that maps the failing line to its `# Then N` comment and prints the failing value:
- C-06, C-08, C-09, G-04: Then 1, `DID NOT RAISE HTTPException`, as their cards say.
- C-07: Then 2, `' Sales ' == 'Sales'`. U-05: Then 2, `updated_by` is U1, not U2.
- G-05, L-06: `TypeError` (no `include_deleted`) in the When, just before `# Then 1`; G-06: the same `TypeError` inside the Then 1 `raises` wrap. Their cards name exactly this `TypeError`.
- Non-strict: L-08 Then 1 `[] == [A, B]`; L-09 Then 1 `[] == [A]`; L-10 Then 2 insertion order. They failed in all 7 runs below as well.

## Reference run
Lines after a failure point never run today. A scratch plugin (`refplug.py`, not in the repo, nothing under `app/` touched) replaced the five service methods at run time with the spec's intended behaviour, written from the spec alone: a trimmed, case-insensitive duplicate check over all live rows (with a raw lookup that the C-09 patch does not reach, standing in for BUG-003's index), `include_deleted` on get and list, filter, search, order `lower(name), id`, then page, and `updated_by` only on a real change. With `--runxfail` all 34 tests passed. Without `--runxfail` all 8 strict cards XPASSed (strict, so they failed) and all 4 non-strict cards XPASSed. So every line of every card ran, and every marker flips once its bug is fixed.

## Stability
5 plain runs plus `PGOPTIONS="-c enable_seqscan=off"` and `PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off"`: 22 passed, 12 xfailed in all 7. No test moved (per-test outcomes compared from JUnit XML). Ruff passes; line endings are LF.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (41 statements) of `app/services/department_service.py`; `app/services/base_service.py` 100% too (run with a private `COVERAGE_FILE`).

## Factories added
None.

## Notes for maintainers
- When a BUG-NNN is fixed, its strict xfails XPASS and fail: remove the marker. The reason names the bug.
- BUG-005, BUG-010 add `include_deleted`. G-05, G-06 and L-06 call with it today and fail on the `TypeError`.
- `nothing written` and the `count:` lines read all workspaces, so `marker_test` must hold no committed `departments` rows (it held none on 2026-11-03).
