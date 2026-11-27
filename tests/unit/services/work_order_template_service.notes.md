# Execution notes — `app/services/work_order_template_service.py`

> Cases: `tests/unit/services/work_order_template_service.cases.md` (revision 3) · Tests: `tests/unit/services/test_work_order_template_service.py` · Source commit: e48a092
> Result: 41 passed · 9 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_work_order_template_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.work_order_template_service --cov-branch --cov-report=term-missing` (with a private `COVERAGE_FILE`)

## How the tests are built
- **Standing rows** are built by the `s` fixture in the card's order (W0, W1, W2, U1, U2, MB1, MB2, WT0, WT1, WT2, I1, I2) and are read as `s.W1`, `s.WT1` and so on. `make_workspace` / `make_profile` come from `tests/unit/factories.py`. The other models are built directly through `_add` (add, then flush).
- **Given rows**: `mk_tpl(db, s, **but)` (Convention "template"), `inactive(s)`, `recurring(p)`, `mk_line`, `mk_approver`, `mk_plant` (F1, S1, M1 and M1's assignment to S1). When a card adds more than one change after "but" on top of `recurring`, the test merges them with `{**recurring(p), "k": v}`.
- **Commit point** is `db.commit()` (it releases a savepoint under the `db` fixture). The `unchanged` and `nothing written` snapshots (`snap_before`, `written`) are taken right after it. **Extra row X** (`extra_x`) is flushed after the snapshots and never committed. `x_rows(db, X_ID)` checks x_gone (0) and x_kept (1).
- **committed:** lines: the ids are saved first, then `db.rollback()` runs once, then each line reads again with a fresh query (`reread` = `expire_all` + `db.get`).
- **session: clean** is three asserts on `db.new`, `db.dirty` and `db.deleted`, made before any re-read.
- **Patches**: only the ones Conventions name. These are the failing commit (`commit` raises, `rollback` wrapped), the failing refresh, and the spies (`commit` and `rollback` wrapped). GD-03 patches `svc.manager.generate_drafts` with `boom`, which moves T's date to D30, flushes and raises `E`. GD-04 patches `work_order_manager.create_work_order_from_template` with `flaky`, which raises for T2's `template_id` (keyword, else the second positional argument) and calls the real method otherwise.
- **xfail placement**: for a `raises:` Then 1, the `# Then 1` comment sits before the `with pytest.raises`. In GD-04 the card's Then 1 fails because the call itself raises, so the When call sits inside the `# Then 1` block.
- ruff FURB157 rewrote `Decimal("2")`, `Decimal("3")` and `Decimal("5")` as `Decimal(2)`, `Decimal(3)` and `Decimal(5)`. The values are the same.

## Verification
- **`--runxfail`** with the scratch plugin `failson_wots.py`: it takes the failing line inside the test function and finds the `# Then N` comment above it. All 9 strict xfails fail on the Then line their card names:
  - C-06, C-07, C-09, U-03, U-06 fail in Then 1 with `DID NOT RAISE`.
  - C-08 fails in Then 2: `'  Oil change ' == 'Oil change'`.
  - U-04 fails in Then 2: `updated_by` is U1, not U2.
  - GD-04 fails in Then 1: `HTTPException 400 boom` escapes the run.
  - GD-08 fails in Then 1: one draft is returned.
- **Reference plugin** `ref_wots.py` (scratch, in-process) replaces three methods of `WorkOrderTemplateManager` with the intended behaviour:
  - `create_template` and `update_template`: deleted types refused (BUG-1228); name trimmed (BUG-2334); an inactive approver gives 400 (BUG-2335); "requires approval" with no approver gives 400, using the merged state on update (BUG-2346); an empty update stamps nothing (BUG-2340).
  - `generate_drafts`: one savepoint per template (BUG-2344); a section run skips recurring templates that are not due (BUG-2345).
  - With `--runxfail`, all 50 tests pass under it.
- **3 plain runs**: each gave 41 passed, 9 xfailed. Nothing is flaky.
- ruff is clean. The file has LF line endings.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (91 statements, 2 branches).

## Factories added
None.

## Notes for maintainers
- When BUG-1228, 2334, 2335, 2340, 2344, 2345 or 2346 is fixed in the manager, schema or DAO, its card here XPASSes (strict → red). Remove the marker. BUG-2335 and BUG-2346 have two cards each (C-07 / U-03 and C-09 / U-06).
- L-01 depends on the DAO's `created_at DESC` order: with `skip=1, limit=1`, B (T2) comes before A (T1). BUG-2330 adds a tiebreak but does not change this case.
- GD-04's `flaky` reads `template_id` by keyword and falls back to `a[1]`. If the manager changes how it calls `create_work_order_from_template`, check this first.

## Useful for the coming permissions / notifications / payment features
- **Permissions**: the service and the manager check no role. Any active member can create, update, deactivate or restore a template, change its approvers and run "Plan day" (`generate_drafts`). This is already in `docs/future/permissions.md` (BUG-2347 covers the expense-template side).
- **Notifications**: once BUG-2344 is fixed, `generate_drafts` gives one draft per successful template and skips the failing ones. A "Plan day" notification would need to report the skipped templates, and today nothing records them.
- **Payments**: nothing here.

## Revision history
- **2026-11-09 — Revision 2** (first execution): 48 cases → 39 passed · 9 xfailed. No discrepancies.
- **2026-11-09 — Revision 3** (cases revision 3, from `work_order_template_service.verify.md` findings 1–2 and mutant #8):
  - Changed: WTSV-L-01 gains a matching row A0 (inactive, "Valve", `created_at T0`), so `limit=1` really cuts a row.
  - New: WTSV-L-04 builds 101 templates with `add_all` and one flush; with no `limit` the list returns the newest 100, in order.
  - New: WTSV-GD-10, written as GD-03 but with a `RuntimeError`, the same object reaching the caller.
  - No ID retired. The other 47 tests are unchanged.
  - Result: 41 passed, 9 xfailed. `--runxfail`: the 9 strict xfails still fail on the Then lines their cards name. All 50 pass under `ref_wots.py`, which needed no change. 3 plain runs gave identical results. Coverage is still 100% branch, ruff is clean, the file uses LF.
