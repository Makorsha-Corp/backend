# Execution notes — `app/services/order_workflow_service.py`

> Cases: `tests/unit/services/order_workflow_service.cases.md` (revision 3) · Tests: `tests/unit/services/test_order_workflow_service.py` · Source commit: e48a092
> Result: 49 passed · 41 xfailed (39 strict, 2 non-strict) · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_order_workflow_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.order_workflow_service --cov-branch --cov-report=term-missing` (with a private `COVERAGE_FILE`)

## How the tests are built
- Normal mode, every test written from its card (`# [claude] <ID>`), in card order; `# Then N` before the checks of Then line N (before the `with pytest.raises` line for a `raises:` line). The two `Author: claude` cards (U-29, D-20) are written the same way.
- Standing rows → fixture `s`: W0, W1, W2, U1, then statuses T0, S1, S2, S3, T2 (`comment="Stage"`), so the ids rise in that order.
- Given rows → `workflow(db, s, **but)`, `purchase_workflow(db, s, **but)`, `order_on(db, s, F, **but)` — direct inserts, one flush each.
- **commit point** → `commit_point(db)`: `db.commit()` (releases a savepoint in the test session), returns the `nothing written` counts. `unchanged(F)` snapshots (`snap_wf`) are taken right after it, before X.
- **nothing written** → `counts(db)`: counts of `order_workflows` and `purchase_orders` over all workspaces (the test database had none committed; parallel runs never commit, so the counts are stable).
- **unchanged(F)** / **unchanged(P)** → `snap_wf` / `snap_po`: a Core `select` of the listed columns, so they are database values.
- **re-read** → `reread_wf` / `reread_po` (`expire_all()` then `db.get`). `committed:` lines: one `db.rollback()` before the first, then fresh reads. Where a `committed:` line reads "the row with id `result.id`", the id is kept in `rid` before the rollback expires `result`.
- **spies**, **failing commit**, **failing refresh**, **failing dao m** → context managers `spies`, `failing_commit` (yields the rollback spy), `failing_refresh`, `failing_dao(m, e)` (patches `app.services.order_workflow_service.order_workflow_dao`, the object the service imports).
- `schema` cards build the schema only; `svc` is not called. Cards U-11, U-13, U-19, U-20 take no fixtures ("No rows needed").
- **Statement recorder** (GL-06) → context manager `record_sql(db)`: a `before_cursor_execute` listener on `db.get_bind()`; `rec.sql` is the (last) `SELECT … FROM order_workflows` sent, `rec.order_part` the text after its first `ORDER BY` and before `LIMIT` (`""` without `ORDER BY`).
- Where a card builds X but checks only `x_gone`, the unused object is bound to `_x` (ruff RUF059).

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (45 statements, 4 branches).

## Factories added
None.

## Checks run
- `--runxfail` with a scratch failing-line plugin (`failson_fo.py`, maps the failing line to its `# Then N` and compares with the card's "Fails today on"): all 37 strict xfails (revision 2; 41 xfails in revision 3, see history) fail inside the named Then line, each with the error the card describes (`DID NOT RAISE` for Then 1 cards; `' Flow B ' == 'Flow B'` for C-05 / U-12; `'Old' is None` for U-17; `{'S2': ['S1']} is None` for U-18; Q24-03 raises `IntegrityError` 23505 inside Then 1).
- Reference plugin (`ref_owfs.py`, scratch only): trimmed / non-blank names and no explicit `null` name or sequence (subclassed schemas swapped in at configure time); purchase create refused 400 before any other check; statuses checked against the workspace in list order (404 names the first bad id); purchase sequence edits refused 400; `exclude_unset` updates (explicit `null` clears); delete refuses `purchase` (`errors == []`) and in-use workflows (own orders by id, then one `other_workspace` entry); every refusal rolls back. Under it with `--runxfail`: 85 passed (revision 3: 90 passed).
- 3 plain runs (revision 2): 48 passed, 37 xfailed each; revision 3: 20 runs, see Notes for maintainers. `ruff` clean, LF endings.

## Notes for maintainers
- GL-01, GL-02, GL-03, GL-07 no longer depend on row order (sizes and sets). The order is checked by GL-04 / GL-05 (non-strict BUG-100: physical order sometimes matches, so they XPASS now and then — expected) and GL-06 (strict SQL alarm: no `ORDER BY` today). In 20 consecutive runs: 12× 49 passed / 41 xfailed, 3× 1 xpassed, 5× 2 xpassed (GL-04 xpassed 7 times, GL-05 6 times); no failure, GL-01/02/03/07 always passed.
- When BUG-100 is fixed (`ORDER BY id` in the base DAO), GL-06 XPASSes (strict → red): remove its marker and those of GL-04 / GL-05.
- When BUG-1215, BUG-1222, BUG-1223, BUG-2348, BUG-2385 or BUG-2386 is fixed, its xfail tests XPASS (strict → red): remove their markers. OWFS-Q24-07 passes before and after BUG-2348's fix by design.
- BUG-2385 / BUG-2386 fixes go in `app/schemas/order_workflow.py`; the schema cards import the schema classes by name, so a fix that swaps the classes must keep the names.

## Useful for the coming permissions / notifications / payments features
- **Permissions**: the service takes no caller; who may create, edit or delete order workflows (today any member through the endpoints) is for the permissions work. The `purchase` row is system-managed after BUG-1223 / BUG-2348: no role should be able to edit its steps or create it.
- **Notifications**: none here. A deleted workflow detaches its purchase orders today (BUG-1222); after the fix the refusal lists the blocking orders — a notification hook needs nothing from this service.
- **Payments**: the purchase workflow's last step decides which purchase orders count as finished (paid / complete views read it); BUG-1223 and BUG-2348 are the guards for that.

## Revision history
- **2026-11-09 — Revision 2** (first execution): 85 cases → 48 passed · 37 xfailed (all strict, all designed).
- **2026-11-09 — Revision 3** — cases revision 3 (verify findings 2–5, coordinator GL rework). Changed: GL-01 (set + size), GL-02 (4 rows, `skip=1, limit=2` → 2 distinct of the four), GL-03 (100 distinct of the 101), C-01 and U-01 (`loaded(result)` moved to Then 1, before any attribute read; `rid` now kept after it). New: GL-07 (`skip=2` of 3 → 1), GL-04 / GL-05 (`Author: claude`, xfail BUG-100 non-strict), GL-06 (strict BUG-100, statement recorder), U-30 (strict BUG-1223: purchase row with a W2 status → 400 STEPS before the 404). Nothing retired. `ref_owfs.py` gained `get_workflows` ordered by id (BUG-100); U-30 already passed under it (purchase check before the status check). `--runxfail`: all 41 xfails fail in their named Then (GL-04/05 in Then 2 with storage order, GL-06 in Then 2 `'ORDER BY' in …`, U-30 in Then 1 DID NOT RAISE); under the reference plugin with `--runxfail` 90 passed. 20 plain runs: see Notes for maintainers. Coverage 100% branch; ruff clean, LF.
