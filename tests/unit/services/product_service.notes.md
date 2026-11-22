# Execution notes — `app/services/product_service.py`

> Cases: `tests/unit/services/product_service.cases.md` (revision 2, 2026-11-22) · Tests: `tests/unit/services/test_product_service.py` · Source commit: e48a092
> Result: 58 passed · 34 xfailed (33 strict, 1 non-strict) · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_product_service.py -q -p no:cacheprovider -o addopts=""`

## How the tests are built
- **One test per card, in card order**: 92 cards → 92 tests (`test_prds_<group>_<nn>__<slug>`). The one `Author: claude` card that is patched (PRDS-D-05) and the non-strict LG-15 are marked `# [claude]`.
- **Standing rows** → fixture `s` (a `SimpleNamespace`): W0 < W1 < W2 (`make_workspace`), U1, U2 (`make_profile`; U2 acts), factories F0, F1, F2, FD (soft-deleted), FI (inactive, live), F9, items I0, I1, I2, IX (inactive), I9. Each is flushed in Conventions order.
- **Given shorthands**: `stock(db, s, **over)` = the "stock" row (W1/I1/F1, qty 5, created_by U1). `FOR_SALE` and `deleted(s)` are the "for sale" and "deleted" column sets. `entry(db, s, **over)` = the "entry" ledger row (`flush=False` for the `add_all` cards and for N in LG-20).
- **Commit point**: `commit_point(db)` runs `db.commit()`, which releases a savepoint under the `db` fixture, and returns the "nothing written" snapshot (`counts`: products and product_ledger row counts, all workspaces). Then come X (`mk_x`), the `unchanged` snapshots (`snap`: the row read through the table, every column) and the uncommitted steps after the commit point.
- **`committed:` lines**: one `db.rollback()` before the first one, then fresh re-reads (`reread`, `ledger_of`, `products_of`, `ledger_count`), all after `db.expire_all()`. Ids are taken before the When, because objects added after the commit point are expunged by a rollback.
- **Patches**: only what Conventions name. `spies` (commit / rollback `wraps`), `failing_commit` (commit raises `RuntimeError("boom")`, rollback spy), `failing_refresh` (refresh raises, no spy), and `patch.object(product_service.manager, "delete_product", side_effect=E)` in D-05.
- **Statement recorder**: a `before_cursor_execute` listener on `db.connection()`, started after the Given and removed after the When. It exposes `selects`, `psel` (`FROM products`), `lsel` (the one `FROM product_ledger`), `order_part` (between `ORDER BY` and `LIMIT`) and `no_lock`.
- **DB-error card** LG-21: `pytest.raises(DataError)` > spies > `db.begin_nested()` > call. The savepoint rollback is not `session.rollback()`, so `rb.call_count == 0` holds and X stays in the session.
- **Raises cards**: `# Then 1` sits before the `with pytest.raises(...)` line (also for the failing commit and failing refresh cards), so a wrong or missing exception lands in Then 1.
- **Checks run outside the plain run** (scratch tools in `C:/Users/User/AppData/Local/Temp/makorsh-pipeline/svc2e/product_service/`, none under `app/`):
  - **Fails-on-Then** (`--runxfail` plus `thencheck.py`, which maps the failing test line to its `# Then N` block, compared by `compare_then.py` with each card's "Fails today on"): all 34 xfail cards fail on their named Then line, 0 mismatches. 30 fail inside the Then block itself. G-05, MS-01, MS-02 and MS-10 fail at the When, which is what their cards say: "Then 1 (the call raises TypeError / AttributeError)", where Then 1 is a `returns:` or `loaded:` line. Details:
    - C-06 / C-08 / U-08: IntegrityError (FK / 23505) escapes `raises: HTTPException`.
    - C-11 / U-14: `None == Decimal('0.00')` on Then 3.
    - LG-16: `'id DESC' in ' \n '` on Then 3.
    - U-09: `updated_by == U2.id` on Then 2.
    - The other MS cards: AttributeError inside Then 1's `raises` block.
  - **Reference implementation** `refimpl_svc.py`: an in-process plugin that applies the intended behaviour:
    - schemas: BUG-2775, BUG-2776 and BUG-2777 (Field bounds and a null check);
    - manager create / update / get / delete: BUG-1011, BUG-1336, BUG-2780, BUG-2779, BUG-2778, BUG-2793 (R9), BUG-2781, BUG-2771, BUG-2772, BUG-2773, BUG-2774;
    - manager `make_sellable` (with `FOR UPDATE OF products` on both bucket reads);
    - ledger DAO: aware bounds turned into naive UTC (BUG-992) and an `id DESC` tie-break (BUG-640);
    - `ProductService.get_product(include_deleted=…)` and `ProductService.make_sellable` (commit once, refresh, roll back on error).

    Under `-p refimpl_svc --runxfail`: **92 / 92 pass**. The pass-companions C-05, C-07 and U-07 pass both today and under it.
  - **Stability**: 3 plain runs gave the same result each time (58 passed, 34 xfailed). `ruff check` is clean, and both files use LF line endings.

## Discrepancies
None.

## Coverage gaps
None. Branch coverage is 100% (47 statements, 0 branches missed; `COVERAGE_FILE` in the scratch folder).

## Factories added
None. All builders are local to the test file.

## New bugs
None. BUG-3077 and BUG-3078 were not used.

## Notes for maintainers
- **When a BUG-n is fixed**, its strict xfail tests will XPASS and fail the run. Remove those markers:
  - BUG-2793: U-05 and MS-01 … MS-11 (`make_sellable` must exist on the service with the signature `(db, prod_id, quantity, workspace_id, user_id)`).
  - BUG-2772: G-04 … G-06 (`include_deleted` on `ProductService.get_product`).
  - BUG-640: LG-16. LG-15 is non-strict and may XPASS by chance today.
  - The pass-through bugs (one or two cards each): BUG-1011, BUG-1336, BUG-2780, BUG-2779, BUG-2778, BUG-2775, BUG-2776, BUG-2781, BUG-2771, BUG-2777, BUG-2773, BUG-2774, BUG-992.
- **LG-15** (non-strict) depends on storage order after an UPDATE under a forced sequential scan. Today it xfails with `[B, C, A]`. Do not make it strict; LG-16, which checks the SQL, is the strict check.
- **LG-12** sets `SET LOCAL TIME ZONE 'Asia/Dhaka'` after the commit point. The fixture's outer rollback resets it.
- **C-05, C-07 and U-07** accept `IntegrityError` or `HTTPException` on purpose. They keep passing after BUG-1011, BUG-1336 and BUG-2781 are fixed.
- **MS-10 Then 3** counts `FOR UPDATE` per statement. A future joined eager load that adds a lock on `items` would fail it, which is intended (no lock on any other table).
