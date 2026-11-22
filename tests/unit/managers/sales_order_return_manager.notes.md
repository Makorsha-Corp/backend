# Execution notes — `app/managers/sales_order_return_manager.py`

> Cases: `tests/unit/managers/sales_order_return_manager.cases.md` (revision 2) · Tests: `tests/unit/managers/test_sales_order_return_manager.py` · Source commit: e48a092
> Result: 106 passed · 42 xfailed (40 strict, 2 non-strict) · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_sales_order_return_manager.py -q -p no:cacheprovider -o addopts="" --cov=app.managers.sales_order_return_manager --cov-branch --cov-report=term-missing`

## How the tests are built
Normal mode (no local model): every test sits below a `# [claude] <ID>` comment, one test per card in card order, with a `# Then N` comment before the checks of each numbered Then line.

Conventions → code:
- Standing rows → fixture `s` (SimpleNamespace): `W0 < W1 < W2`, `U1`, `U2`, per workspace `F0/F1/F9`, `ST0/ST1/ST9`, `AC0/AC1/AC9`, items `I1` "Pump" and `I2` "Valve" (W1), orders `O0, O1, O2, O3, O9` numbered `SO-{TAG}-<name>`; `s.TAG` is made once per test.
- line k → `mk_line(db, s, k, **but)` (line 2 has `I2`); free line "D" → `mk_free(db, s, "D", **but)`; return N → `mk_return(db, s, "N", **but)` with `completed(s)` / `VOIDED` for the two states; rline → `mk_rline(db, R, L, "q", **but)` (workspace = the return's unless overridden); credit note → `mk_cn(db, s, W, status, **but)`, `voided_cn`, `confirmed_cn`; seqscan → `seqscan(db)`; bumpL → `bump_l(db, X)`; the Q47 void step → `void_step(db, s, cn)`.
- Requests: `LN`, `REQ`, `V(db, s, req)`, `TOO`, `NOTHERE`; `MISS(q)` is the cards' `SalesOrderReturnItemCreate(so_item_id=MISSING, …)`; `PR(L, q, price)` the Q45 cards' line with `unit_price=`.
- Named checks: `reread(db, Model, id)` (expire, then SELECT), `snap(db, Model, id)` (every mapped column) for unchanged(X), `totals(db)` for "nothing written" (four tables, all workspaces), `assert_session_clean(db)`, `StatementRecorder` (`selects`, `written`, `sel(t)`, `no_lock()`, `locks(t)`) and `order_part(st)`. `sel(t)` matches `FROM t` / `JOIN t` as a whole word, so `sales_order_returns` never matches `sales_order_return_items`.
- Recorder cards: ids are read into locals before `db.expunge_all()`, then the When and every Then run inside the recorder block (the convention records "from the start of the When to the end of the test").
- `sync_return_paid` cards: the return is built with `updated_at T1`, `updated_by None` (`mk_sret`) and passed loaded (no expunge). S-14's commit spy wraps the real `db.commit` around `db.begin_nested()`; "inside" checks run before `sp.rollback()`.
- Q47 cards call the real `account_invoice_manager.void_invoice` (no patch). Its `utcnow` is not patched; no card checks a void timestamp.
- Mocks: none (Externals: none). Race simulations: none.
- Schema cards take the `s` fixture too (the standing rows exist in every test).

Markers: strict xfail with `reason="BUG-n: <title from bugs.md>"`; G-14 and L-09 are `strict=False` as designed (physical order).

Checks done in this run (scratch `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\retprode\so\`, my own files):
- `--runxfail` with plugin `thencheck_so.py` + `compare_so.py`: all 42 xfail tests fail inside the Then block the card names (cards whose Fails-today says "the call raises" fail at the When call, before `# Then 1`); the failing values match the cards' text (e.g. V-15 `only 2.00`, V-18 `only 0`, V-55 NOTHERE, Q45-10 the Valve TOO text, G-10..G-12 `TypeError` on `for_update`).
- Reference plugin `ref_so.py` (`-p ref_so --runxfail`, PYTHONPATH = scratch folder) replaces in-process the intended behaviour of BUG-2760/2796 (available = delivered − this workspace's pending), 2761 (running total), 2763 (lines read `FOR UPDATE OF sales_order_items`), 2786 (price range, after the quantity check), 2797 (name rule), 2762 (schema `max_digits=15, decimal_places=2`), 2764 (`for_update`), 2765 (`items` ordered by id), 2423 (`id DESC` tie-break) and 2788 (`void_invoice` R3c for sales return credit notes): **148 passed**.
- 3 plain runs: 106 passed, 42 xfailed each time (the two non-strict cards xfailed every run). ruff clean; LF line endings.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (47 statements, 12 branches).

## Factories added
None.

## Notes for maintainers
- When a bug is fixed its strict xfails XPASS → remove the marker: BUG-2760 (V-14, V-15, V-17, V-18, V-20), BUG-2761 (V-21, V-23, V-24, V-26, V-27, V-50, V-55, V-56), BUG-2762 (SCH-08..SCH-12), BUG-2763 (V-44), BUG-2764 (G-10..G-12), BUG-2765 (G-13, L-08; non-strict G-14, L-09), BUG-2423 (L-07), BUG-2786 (Q45-01, Q45-03, Q45-04, Q45-10, Q45-12), BUG-2788 (Q47-03..Q47-07), BUG-2796 (V-51..V-53), BUG-2797 (V-57, V-58).
- BUG-2788 is fixed in `account_invoice_manager.void_invoice` R3c, not here; the Q47 cards will flip only with that fix.
- The BUG-2765 fix (relationship `order_by`) is shared with the purchase twin's pattern; G-13 / L-08 look for `sales_order_return_items.id` after `ORDER BY` in the lazy load of `items`.
- The spec's OQ-47 "Suggested answer" quotes `… its goods have already come back …`; the approved rule (`account_invoice_manager.spec.md` R3c, BUG-2788 row) and the card use `… its goods have already moved …`, which is what Q47-07 asserts.
- The SAWarnings about `_regconfig_fn` appear only under `--cov` (coverage re-import) and are harmless.
