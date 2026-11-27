# Execution notes — `app/services/order_template_service.py`

> Cases: `tests/unit/services/order_template_service.cases.md` (revision 3) · Tests: `tests/unit/services/test_order_template_service.py` · Source commit: e48a092
> Result: 30 passed · 3 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_order_template_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.order_template_service --cov-branch --cov-report=term-missing` (private `COVERAGE_FILE`)

## How the tests are built
- Normal mode: 33 tests, one per card, in card order, each under `# [claude] <ID>`; `# Then N` marks the checks of the card's Then line N. No `Author: claude` card.
- **Standing rows** — fixtures `w0` → `w1` → `w2` → `u1` → `u2` (chained, so ids rise in the Conventions order; autouse `standing`).
- **Given rows** — `mk_tpl(**but)`, `mk_line(t, n, **but)` insert and flush one row; `inactive(u2)` spells the variant. `commit_point(db)` = `db.commit()` (a savepoint release under the `db` fixture); snapshots (`snap`, `written`) are taken right after it. `extra_x(db, w2)` adds the uncommitted X and returns `X_ID`; `x_count(db, x_id)` is x_gone (0) / x_kept (1).
- **committed:** lines: `db.rollback()` once, then fresh queries (ids captured before the rollback). **loaded:** lines: the column is not in `inspect(result).unloaded`. **session: clean** = three asserts on `db.new`, `db.dirty`, `db.deleted`; **usable** = `SELECT 1`.
- **failing commit / failing refresh / spies** exactly as Conventions write them (`patch.object(db, "commit" | "rollback" | "refresh", …)`); nothing else is patched.
- The TC3 refusal on create (C-02) uses `user_id=MISSING`, so the `created_by` foreign key fails at flush (`IntegrityError`), as the card says.

## Verification
- **`--runxfail`** with the executor's own failson plugin (`<scratch>/failson.py`): C-06 fails in Then 1 (`DID NOT RAISE HTTPException` — the flag is stored for anyone), I-03 in Then 3 (`Decimal('20.00') == Decimal('0.00')` — the stored price 10.00 is used). Both as their cards name. GI-03 (BUG-2366, revision 3) fails in Then 1 (`DID NOT RAISE HTTPException` — `[]` is returned).
- **Reference plugin** (`<scratch>/ref_otm.py`, the manager's intended fixes, in-process only): 33 passed with `--runxfail -p ref_otm`.
- **3 plain runs**: 30 passed, 3 xfailed each time.
- `ruff check` clean (`noqa: SIM117, FURB157`: the nested `with` blocks of Conventions, and the cards' `Decimal("0")`); no unused variables or test arguments; LF line endings.
- `<scratch>` = `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tple\otm\`.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (68 statements, no branches).

## Factories added
None.

## Notes for maintainers
- R-01 reads `quantity` and `description` off the returned line after the commit: the deleted row leaves the identity map before the commit expires it, so its loaded values stay readable (detached). If the session ever expires deleted objects too, R-01 Then 1 fails with `DetachedInstanceError` — that would be a real change of the service's Returns rule.
- When BUG-1226 is fixed, I-03 XPASSes; when BUG-2366 is fixed, GI-03 XPASSes; when BUG-2347 is fixed in the manager, C-06 XPASSes — remove those markers.

## Useful for the coming permissions / notifications / payment features
- **Permissions**: the service has no check of its own; the owner-only "skip approval" rule (BUG-2347) lives in the manager and reaches the caller as a 403 after the service's rollback (C-06), so a permissions layer above the service sees an ordinary `HTTPException`.
- Notifications / payments: nothing here (no events, no money beyond the manager's line subtotals).

## Revision history
- **2026-11-09 — Revision 2** (first execution): 31 cases → 29 passed · 2 xfailed (strict), no discrepancies.
- **2026-11-09 — Revision 3** (`order_template_service.verify.md` findings 1–3): OTSV-L-02 changed — the fifth Given row A0 (inactive "Water", factory, `created_at T0`) added, so `limit=1` cuts a matching row; expected `[A.id]` unchanged and still passes. New OTSV-L-04 (101 templates by `add_all`, no `limit` → the newest 100, pass) and OTSV-GI-03 (another workspace's template → 404, strict xfail BUG-2366, fails in Then 1). No test removed. `ref_otm.py` unchanged (its `get_items` already answers 404): 33 passed under it. 3 plain runs 30 passed · 3 xfailed; coverage still 100%; ruff clean; LF.
