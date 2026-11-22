# Execution notes — `app/services/inventory_service.py`

> Cases: `tests/unit/services/inventory_service.cases.md` (revision 3) · Tests: `tests/unit/services/test_inventory_service.py` · Source commit: e48a092
> Result: 63 passed · 24 xfailed-as-designed (23 xfailed + 1 non-strict XPASS, INVS-S-09) · 0 discrepancies · 0 errors — branch coverage 98% (49 stmts, 1 missed, 0 branches in file)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_inventory_service.py -q -p no:cacheprovider -o addopts=""`

## How the tests are built
- **Standing rows** W1, W2, U1, U2, F1, I1 are chained fixtures (`w1` → `w2` → `u1` → `u2` → `f1` → `i1`) pulled in by the autouse `standing`, so they are always built in the Conventions order.
- **Builders**: fixture `g` (class `Given`) holds every builder: `g.inv(**but)` (Conventions defaults, `but` = the card's "but" columns), `g.gone()` (the `gone` dict), `g.factory` / `g.item` (with `name_normalized = name.lower()`), the named rows `g.f2() g.fx() g.fd() g.fi() g.i2() g.i3() g.ix()`, `g.foreign(ix, fx, **but)` for "TX = inv, but workspace_id W2.id, item_id IX.id, factory_id FX.id", and `g.flow()` / `g.po(k, F, s_open, wf, **but)` / `g.line(P, **but)` for the incoming rows. Each row is added and flushed on its own, in Given order. INVS-P-09 uses `add_all` as its card says.
- **commit point** = `db.commit()` (a savepoint release). The `unchanged` snapshots (`snap_before`) are taken right after it. **X** = `mk_x(db)` (a flushed `make_workspace`), run after the commit point and returning `X_ID`.
- **Named checks**: `reread` (`expire_all` + `db.get`), `snap_before` / `snap` (the six `unchanged` columns through a fresh column `select`), `ledger(db, R)` (reads R's key with a fresh query, then the ordered ledger list), `ledger_all`, `inv_count`, `x_gone` / `x_there`, `loaded`, `usable`. `committed:` lines start with one `db.rollback()`.
- **Spies / failing commit / failing refresh**: written inline as Conventions word them, with `patch.object` on the session.
- **Recorder** (U-12, D-09): a `before_cursor_execute` listener on `db.connection()` for the duration of the When. `inv_selects` = statements that start with `SELECT` and match `FROM inventory(\s|$)`.
- **Race simulation** (C-09 only): both inventory-DAO duplicate lookups patched to `None`, inside the `raises:` block, so the insert hits `uq_inventory_workspace_item_type_factory` (pgcode 23505).
- **Database error** (C-08, U-08): `model_construct(..., avg_price=Decimal("1e13"))` overflows `Numeric(15,2)` at the flush (a `DataError`). No savepoint is used because the service rolls back itself.
- **xfail markers**: `xfail(n)` builds `pytest.mark.xfail(strict=True, reason="BUG-n: <bugs.md title>")`. The non-strict ones are `xfail(719, strict=False)` (S-09) and `xfail(706, strict=False)` (IS-09). BUG-3082's reason uses its bugs.md title.
- **Ruff**: the file-level `noqa` covers `SIM117` (the nested `with` blocks Conventions prescribe) and `FURB157`, so that `Decimal("7")`, `Decimal("0")` and similar keep the cards' literal text.

### Verification done
- **3 plain runs**: all three identical, `63 passed, 23 xfailed, 1 xpassed`. The XPASS is always INVS-S-09 (non-strict BUG-719): Postgres currently returns the `GROUP BY` rows in enum order. The card allows this ("an XPASS is reported, not fixed").
- **`--runxfail`**: every strict xfail fails inside the card's "Fails today on" Then block. C-05, C-06, U-05, G-04, G-06 and IS-05 fail on Then 1 (DID NOT RAISE, or TypeError for G-06). C-12, U-13 and D-10 fail on Then 3 (`total_cost` None). U-06 fails on Then 2 (`'n1' is None`). U-11 fails on Then 2 (`updated_by` set). U-12 and D-09 fail on Then 2 (no `FOR UPDATE`). U-14 fails on Then 2 (0 ledger rows). P-11 fails on Then 2 (collation order). P-12 and S-08 fail on Then 1 (2 rows match). IS-07 fails on Then 2 (15.00 ≠ 7). D-08 fails on Then 2 (qty -4). C-14, G-05 and G-07 fail on the `result = …` When call (IntegrityError / TypeError), which is what their cards name as Then 1 ("the call raises"). Non-strict IS-09 also fails on Then 2 today.
- **Reference plugin** (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2e\inventory_service\ref_inventory.py`): it patches in-process only and models BUG-700/701/702/703/704/705/706/707/709/710/712/713/714/715/716/717/718/719/3082. With `PYTHONPATH=<that folder> … -p ref_inventory --runxfail` the result is **87 passed**.
- `ruff check` is clean (also `--select F841,F811`). An AST pass found no unused test arguments. The file uses LF line endings. All 87 case IDs appear exactly once.

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 60 | dead | `InventoryService.list_inventory`, which is passed straight to the manager. The spec lists it under Not specified, and it is on `docs/testing/dead-code-removal-checklist.md`. |

## New bugs
None. BUG-3073 and BUG-3074 are unused.

## Factories added
None. Every builder is local to this file.

## Notes for maintainers
- When a BUG-n is fixed, its strict tests will XPASS and fail the run. Remove the marker in the same change. The tests per bug: 700 G-04 · 701 P-11 · 702 P-12, S-08 · 703 U-11 · 704 U-12 · 705 D-09 · 707 C-12, U-13, D-10 · 710 C-05 · 712 U-14 · 713 U-05, U-06 · 714 C-14 · 715 C-06 · 716 D-08 · 717 IS-07 · 718 IS-05 · 3082 G-05, G-06, G-07. The non-strict ones are 706 IS-09 and 719 S-09.
- The fix for BUG-704 / BUG-705 must use `with_for_update(of=Inventory)`. The `item` relationship is a joined eager load (`LEFT OUTER JOIN items`), and Postgres refuses a plain `FOR UPDATE` on it. The spec's G2 notes that `inventory_manager.spec.md` R10 / R8 still say plain `FOR UPDATE`.
- INVS-P-11 depends on the database collation ordering "apple" before "Apple". If the test database is ever created with a C collation, the order flips and the strict xfail would XPASS.
- INVS-S-09 XPASSes today. If it ever starts failing, that is the BUG-719 symptom, not a flaky test.
## Revision history
- **Revision 3 (2026-11-22).** The cards' new note on G-05, G-06 and G-07 is now in their docstrings: remove the xfail only after BUG-700 is fixed too; a BUG-3082 fix that ignores `include_deleted` would still pass them, and only G-04 catches it. No assertion changed. BUG-3082's xfail reason uses its bugs.md title. Re-checked: `--runxfail` gives 23 failed (the strict xfails plus IS-09) and 64 passed; the reference plugin gives 87 passed; 3 plain runs gave `63 passed, 23 xfailed, 1 xpassed` (the xpass is S-09, non-strict); ruff clean; LF.
