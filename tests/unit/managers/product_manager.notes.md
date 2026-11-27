# Execution notes — `app/managers/product_manager.py`

> Cases: `tests/unit/managers/product_manager.cases.md` (revision 3) · Tests: `tests/unit/managers/test_product_manager.py` · Source commit: e48a092
> Result: 143 passed · 102 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_product_manager.py -q -p no:cacheprovider -o addopts="" --cov=app.managers.product_manager --cov-branch --cov-report=term-missing`

## How the tests are built
- **Standing rows** → fixture `s` (a `SimpleNamespace`): W0 < W1 < W2 (`make_workspace`), U1, U2 (`make_profile`), factories F0, F1, F2, FD (soft-deleted, `deleted_at T0`, `deleted_by U1`), FI (inactive), F9, items I0, I1, I2, IX (`is_active False`), I9, account AC1. Each is flushed in card order, and the fixture ends with `db.expire_all()`. Every test takes `db, s`, including the pure `_quantity_to_int` cards, because the convention says the standing rows exist in every test.
- **Given rows**: `mk(db, s, *, for_sale=False, deleted=False, **overrides)` builds the convention "stock" (W1 / I1 / F1, `qty 5`, `created_by U1`). `for_sale=True` sets the flag. `deleted=True` writes all four soft-delete columns. "of W0" / "of W2" are written as `workspace_id=s.W0.id`. `mk_sale` builds the "sale entry" ledger row, and its `unit_cost` also goes into `avg_cost_before` / `avg_cost_after`. The MS cards use `mk_source` (S: `qty 10`, `avg_cost 5.00`) and `mk_target` (T: for sale, `qty 4`, `avg_cost 8.00`). Every Given ends with `db.expire_all()`.
- **Named checks**: `reread` (expire, then SELECT by id), `snap` (every column through a Core SELECT; "unchanged(X)" compares a snapshot taken after the Given with one taken after the When), `counts` ("nothing written": `products` and `product_ledger` in all workspaces), `count(db, Model, *filters)`, `ledger_of(db, s, F, I)` (W1 rows ordered by id; E = `[0]` once the count is checked, N = `[-1]`), `out_row` / `in_row` (`scalar_one()` on `transfer_destination_type` / `transfer_source_type == "product"`). "session clean" is written as three inline asserts.
- **Statement recorder**: the context manager `record(db)` puts a `before_cursor_execute` listener on `db.connection()` around the When only, then sorts the statements into `selects`, `psel` (contains `FROM products`) and `written`. Ids are read into locals before the recorder starts, so expired-object refreshes do not pollute the recorded SQL.
- **Rolled back**: `sp = db.begin_nested()` and `patch.object(db, "commit", wraps=db.commit)` directly before the call. The checks inside the savepoint come first, then `sp.rollback()`, then the "after the savepoint rollback" checks and `spy.assert_not_called()`.
- **Mocks**: none. The spec lists no externals.
- **Parametrized cards** (identical setup and checks, one input differs): C-25 … C-32 (create schema), U-28 … U-35 (update schema), MS-21 … MS-23 (bad quantity). Each param id is the case ID and carries its own strict xfail mark.
- **xfail reasons** use the bug title from `docs/testing/bugs.md`. U-27 and SR-29 carry the literal reason their Expect line gives since revision 3: `"BUG-2777, BUG-2778"` and `"BUG-2794, BUG-1336"`.

### Checks run
- **Fails-on-Then check** (`--runxfail` plus a scratch plugin that maps each failing line to the `# Then N` block it sits in, compared with every card's "Fails today on" line): all 102 strict xfails fail on their named Then line. 77 fail inside the Then block itself (among them U-54 on Then 1, the `raises:` line, with IntegrityError 23505, and PO-20 on Then 4, `Decimal('6.00') is None`). The other 25 fail at the call, which is exactly what their card's "Fails today on: Then 1 (the call raises …)" says:
  - `make_sellable` happy-path cards: AttributeError.
  - G-07 and G-10: TypeError, because `include_deleted` does not exist.
  - PO-14, PO-27, SR-13 and SR-29: IntegrityError 23505.

  The exception types are as the cards say: C-18 fails with a ForeignKeyViolation, C-23 / U-45 / U-46 with a UniqueViolation, and the others with "DID NOT RAISE" or the named assertion value.
- **Reference implementation**: a scratch pytest plugin (outside `app/`) patches `ProductManager` and `app.schemas.product` in-process to the intended behaviour. It applies every bug fix of the spec plus a reference `make_sellable`. Under it with `--runxfail`, **245 / 245 pass**. Revision 3 copy: `C:/Users/User/AppData/Local/Temp/makorsh-pipeline/prodr3/refimpl.py`, with R8a (a bucket created by the call has `avg_cost_before` NULL; a restored row is not new and keeps its average as the cost before) and R10a (R9's 400 is checked before R10's 409) marked in the code.
- **Stability**: 3 plain runs gave identical results (143 passed, 102 xfailed).
- **Lint**: `ruff check` is clean. `datetime` constants carry `# noqa: DTZ001`, as in the other files. Line endings are LF.

## Discrepancies
None open.

- DISCREPANCY-1 (PRDM-PO-20, `avg_cost_before` on a bucket created by a costed output) is **resolved** (2026-11-19). The owner decided it in chat, the spec added `apply_production_output` R8a [BUG-2811], and cases revision 3 makes PO-20 a strict xfail BUG-2811 on Then 4. Only the test's marker and docstring changed; the `DISCREPANCY_1` constant is gone. PO-26 holds the parts of PO-20 that pass today.

## Coverage gaps
None — 100% branch coverage (116 statements, 36 branches).

## Factories added
None. No change needed to `tests/unit/factories.py` or `conftest.py`.

## Notes for maintainers
- **When a bug is fixed**, its strict xfails will XPASS and fail the run. Remove the marker:
  - BUG-2770: U-39, PO-15, SD-21, SR-14.
  - BUG-2771: U-17, U-19.
  - BUG-2772: G-06, G-07.
  - BUG-2773: G-08, G-09, G-10.
  - BUG-2774: D-07, D-08.
  - BUG-2775: C-25 … C-28, C-34, U-30 … U-33.
  - BUG-2776: C-29 … C-32, U-34, U-35.
  - BUG-2777: U-24 … U-29.
  - BUG-2778: C-08, U-21, U-22, U-52, U-53.
  - BUG-2779: C-06, U-15.
  - BUG-2780: C-14, C-15, C-36, C-37, C-38.
  - BUG-2781: U-45, U-46.
  - BUG-2782: SD-18, SD-19.
  - BUG-2783: SR-02.
  - BUG-1011: C-16, C-17, C-18.
  - BUG-1040: PO-18.
  - BUG-2811: PO-20.
  - BUG-1336: C-23, PO-14, PO-27, SR-13.
  - BUG-2794: SR-20 … SR-24, SR-29 (SR-29 also needs BUG-1336).
  - BUG-2793: U-40, U-41, U-42, U-50, U-51, U-54, and all 30 MS cards (once `make_sellable` exists).
- Several cards count rows in **all workspaces** (`count: products has exactly 1 row`, "nothing written"). That relies on `marker_test` holding no committed `products` / `product_ledger` rows (verified empty at run time). The `db` fixture never commits.
- PO-12 and SR-12 run the first posting as a Given step through `M`, as the cards say.
- Spec gap 7 (flip of a stocked row onto a taken key) is closed by `update_product` R10a: the 400 of R9 comes first. U-54 covers it; today it fails with IntegrityError 23505 at flush.
- PO-28 and PO-29 check `result.avg_cost` before any re-read (the in-session value), so a missing `quantize` is caught apart from the `Numeric(15,2)` column.
- The Starlette `HTTP_422_UNPROCESSABLE_ENTITY` deprecation warning comes from `app/managers/product_manager.py:286`. It does not affect the tests.

## Revision history
- **2026-11-19, cases revision 3** (245 cases: 143 pass, 102 strict xfail).
  - Changed: PRDM-PO-20 is now `xfail BUG-2811` (strict, fails on Then 4); it was marked DISCREPANCY-1, which is resolved.
  - Reason only: PRDM-U-27 `"BUG-2777, BUG-2778"` and PRDM-SR-29 `"BUG-2794, BUG-1336"`, as their Expect lines now say. Assertions unchanged.
  - New pass tests: PO-26 (new costed bucket, the parts that hold today), PO-28 (old stock of 1 weighted), PO-29 (1.333… → 1.33, in session too), U-55 (adjustment total 10.05), SD-23 (one-unit delivery), SD-24 (delivery total 13.05), SR-31 (one-unit return), SR-32 (return total 6.45).
  - New strict xfails: PO-27 (BUG-1336, a restored bucket is not new; fails at the call with 23505) and U-54 (BUG-2793 / R10a; fails on Then 1 with 23505 instead of the 400).
  - All other tests unchanged. No ID retired. Reference plugin extended (R8a, R10a): 245 / 245 pass under it. `ruff check` clean, LF line endings.
