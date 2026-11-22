# Execution notes — `app/dao/product.py`

> Cases: `tests/unit/dao/product.cases.md` (READY, Revision 1, 170 cases; spec APPROVED 2026-11-02) · Tests: `tests/unit/dao/test_product.py` · Source commit: e48a092
> Result: **170 tests for 170 cases — 127 passed · 43 xfail (34 strict, 9 non-strict) · 0 discrepancies · 0 errors** — branch coverage 100% (36 statements, 4 branches, 0 missed). In run 1 of the file alone 38 xfailed and 5 non-strict xpassed.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_product.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file written for this batch (not kept in the repo; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\prodx\gen.py`), so values are the card's own text; an unknown Given, When or Then line stopped it, and none did. Fixtures, builders and helpers were written from the Conventions. A separate audit script checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matching the card's Then count in order with a check under each, every quoted literal of the card present, the When call present, marker strictness and bug matching the Expect line, no unused argument, no fixture used without being an argument, LF line endings. 0 problems.

## How the tests are built
- **Patched:** only `app.dao.product.utcnow` (`create=True`, `return_value=NOW`), around the When of the two cards that say **clock NOW** (PRD-SD-07, PRD-SD-08). The module does not import `utcnow` today, so the patch is unused until BUG-1335 is fixed.
- **Standing rows:** one fixture per Conventions row, each depending on the one listed before it (and on any row it names), so they are flushed one at a time in Conventions order and the ids rise in that order. The autouse `standing_rows` makes all of them exist in every test; a test lists only those it names.
- **Builders:** `new_<row>(...)` builds the Conventions row with its defaults (not added); `mk_<row>(...)` adds and flushes it. A card's columns are passed as keywords in card order. The `add_all` Givens build `new_<row>` objects in a list comprehension and flush once (`add_many`); `newest` / `in_order` lists are taken from that list.
- **Reading helpers (no expected values inside):** `ids`; `snap` ("unchanged": every column by a Core select of the table, after `db.expire_all()`); `without` ("unchanged ... except"); `reread` ("re-read": expire, then `db.get`); `stored_count` ("nothing written"); `count_rows` ("count:" lines, Core count with the stated filter); `seqscan` (the three `SET LOCAL` steps). Only those the cards use are in the file.
- **Statement recorder:** the `recorder` fixture listens on the session's connection (`before_cursor_execute`) from `recorder.start()` at the start of the When to the end of the test, as the Conventions say, and removes the listener at teardown. `sql` (the one SELECT `FROM <table>`, fails loudly unless there is exactly one), `order_part` and `selects` are read at the first `statement:` line or before the first reading helper, whichever comes first, so the helpers' own SELECTs never enter them; `written` is read at its line.
- **Errors:** `pytest.raises(...)` around `db.begin_nested()` around the When (no savepoint for `ValidationError`); `exc` is bound only when a later Then reads it. **Rolled back** cards: `sp = db.begin_nested()` before the When, `patch.object(db, "commit", wraps=db.commit)` as the spy, `sp.rollback()` directly before the first "after the savepoint rollback" check.
- **Given rows no line names again** are built without a variable. Row letters of the cards are lower case in the code.
- **Joined relationship:** `Product.item` is `lazy="joined"`, so every `products` SELECT carries `LEFT OUTER JOIN items AS items_1`. No card of this module asserts `"JOIN" not in sql`; PRD-GW-54 (`len(selects) == 1`, item name and unit read with no further query) relies on it and passes. The recorder's `sql` is the one SELECT `FROM products`.

## xfail check (`--runxfail`, failing value read)
Every xfail card was run with `--runxfail`; the failing line's `# Then N` was read against the card's "Fails today on", and the failing value against what the card says. Strict cards: all 34 fail at the Then the card names, with the value the card describes.
17 cards fail in the When, before `# Then 1`, which is what their "Fails today on: Then 1" says (the call itself raises): PRD-GA-01, PRD-GA-02, PRD-GA-03, PRD-GA-04, PRD-GA-05, PRD-GA-06, PRD-GA-07, PRD-GA-08, PRD-GA-09, PRD-GA-10, PRD-GA-11, PRD-GA-12, PRD-GA-13, PRD-GA-14, PRD-GA-15, PRD-GA-16, PRD-GA-17. The exception was read: AttributeError: 'ProductDAO' object has no attribute '_get_any_by_factory_item_available'. Did you mean: 'get_.

| Case | Strict | Fails on | Value read under `--runxfail` |
|---|---|---|---|
| PRD-GW-24 | strict | Then 1 | `assert [227029, 227030] == [227030] At index 0 diff: 227029 != 227030 Left contains one more item: 227030 Use -v to get more diff` |
| PRD-GW-25 | strict | Then 1 | `assert [<app.models....026AACAB5670>] == [] Left contains one more item: <app.models.product.Product object at 0x0000026AACAB5670> Use -v to ge` |
| PRD-GW-26 | strict | Then 1 | `assert [<app.models....026AACAB4FB0>] == [] Left contains one more item: <app.models.product.Product object at 0x0000026AACAB4FB0> Use -v to ge` |
| PRD-GW-27 | strict | Then 1 | `assert [<app.models....026AACAEFAD0>] == [] Left contains one more item: <app.models.product.Product object at 0x0000026AACAEFAD0> Use -v to ge` |
| PRD-GW-28 | strict | Then 1 | `assert 2 == 1 + where 2 = len([<app.models.product.Product object at 0x0000026AAD2B8CB0>, <app.models.product.Product object at 0x0000026AAD2B8CE0>]` |
| PRD-GW-29 | strict | Then 1 | `assert [227040, 227041] == [227041] At index 0 diff: 227040 != 227041 Left contains one more item: 227041 Use -v to get more diff` |
| PRD-GW-30 | strict | Then 1 | `assert [<app.models....026AAD2BB080>] == [] Left contains one more item: <app.models.product.Product object at 0x0000026AAD2BB080> Use -v to ge` |
| PRD-GW-31 | strict | Then 1 | `assert [<app.models....026AAD2D93A0>] == [] Left contains one more item: <app.models.product.Product object at 0x0000026AAD2D93A0> Use -v to ge` |
| PRD-GW-32 | strict | Then 1 | `assert 2 == 1 + where 2 = len([<app.models.product.Product object at 0x0000026AAD2DAC30>, <app.models.product.Product object at 0x0000026AAD2DAC60>]` |
| PRD-GW-37 | strict | Then 2 | `AssertionError: assert 'ORDER BY' in 'SELECT products.id AS products_id, products.workspace_id AS products_workspace_id, products.item_id AS products_` |
| PRD-GW-38 | non-strict | Then 2 | `assert [227055, 227056, 227057] == [227056, 227057, 227055] At index 0 diff: 227055 != 227056 Use -v to get more diff` |
| PRD-GW-39 | non-strict | — | passed today by physical order (non-strict); failed under the explicit wrong order |
| PRD-GW-40 | non-strict | — | passed today by physical order (non-strict); failed under the explicit wrong order |
| PRD-GW-41 | non-strict | Then 2 | `assert [227062, 227064, 227063] == [227062, 227063, 227064] At index 1 diff: 227064 != 227063 Use -v to get more diff` |
| PRD-GW-42 | non-strict | — | passed today by physical order (non-strict); failed under the explicit wrong order |
| PRD-GW-43 | non-strict | Then 2 | `assert [227069] == [227070] At index 0 diff: 227069 != 227070 Use -v to get more diff` |
| PRD-GW-44 | non-strict | — | passed today by physical order (non-strict); failed under the explicit wrong order |
| PRD-GA-01 | strict | the When (Then 1 not reached) | `AttributeError: 'ProductDAO' object has no attribute '_get_any_by_factory_item_available'. Did you mean: 'get_by_factory_item_available'?` |
| PRD-GA-02 | strict | the When (Then 1 not reached) | `AttributeError: 'ProductDAO' object has no attribute '_get_any_by_factory_item_available'. Did you mean: 'get_by_factory_item_available'?` |
| PRD-GA-03 | strict | the When (Then 1 not reached) | `AttributeError: 'ProductDAO' object has no attribute '_get_any_by_factory_item_available'. Did you mean: 'get_by_factory_item_available'?` |
| PRD-GA-04 | strict | the When (Then 1 not reached) | `AttributeError: 'ProductDAO' object has no attribute '_get_any_by_factory_item_available'. Did you mean: 'get_by_factory_item_available'?` |
| PRD-GA-05 | strict | the When (Then 1 not reached) | `AttributeError: 'ProductDAO' object has no attribute '_get_any_by_factory_item_available'. Did you mean: 'get_by_factory_item_available'?` |
| PRD-GA-06 | strict | the When (Then 1 not reached) | `AttributeError: 'ProductDAO' object has no attribute '_get_any_by_factory_item_available'. Did you mean: 'get_by_factory_item_available'?` |
| PRD-GA-07 | strict | the When (Then 1 not reached) | `AttributeError: 'ProductDAO' object has no attribute '_get_any_by_factory_item_available'. Did you mean: 'get_by_factory_item_available'?` |
| PRD-GA-08 | strict | the When (Then 1 not reached) | `AttributeError: 'ProductDAO' object has no attribute '_get_any_by_factory_item_available'. Did you mean: 'get_by_factory_item_available'?` |
| PRD-GA-09 | strict | the When (Then 1 not reached) | `AttributeError: 'ProductDAO' object has no attribute '_get_any_by_factory_item_available'. Did you mean: 'get_by_factory_item_available'?` |
| PRD-GA-10 | strict | the When (Then 1 not reached) | `AttributeError: 'ProductDAO' object has no attribute '_get_any_by_factory_item_available'. Did you mean: 'get_by_factory_item_available'?` |
| PRD-GA-11 | strict | the When (Then 1 not reached) | `AttributeError: 'ProductDAO' object has no attribute '_get_any_by_factory_item_available'. Did you mean: 'get_by_factory_item_available'?` |
| PRD-GA-12 | strict | the When (Then 1 not reached) | `AttributeError: 'ProductDAO' object has no attribute '_get_any_by_factory_item_available'. Did you mean: 'get_by_factory_item_available'?` |
| PRD-GA-13 | strict | the When (Then 1 not reached) | `AttributeError: 'ProductDAO' object has no attribute '_get_any_by_factory_item_available'. Did you mean: 'get_by_factory_item_available'?` |
| PRD-GA-14 | strict | the When (Then 1 not reached) | `AttributeError: 'ProductDAO' object has no attribute '_get_any_by_factory_item_available'. Did you mean: 'get_by_factory_item_available'?` |
| PRD-GA-15 | strict | the When (Then 1 not reached) | `AttributeError: 'ProductDAO' object has no attribute '_get_any_by_factory_item_available'. Did you mean: 'get_by_factory_item_available'?` |
| PRD-GA-16 | strict | the When (Then 1 not reached) | `AttributeError: 'ProductDAO' object has no attribute '_get_any_by_factory_item_available'. Did you mean: 'get_by_factory_item_available'?` |
| PRD-GA-17 | strict | the When (Then 1 not reached) | `AttributeError: 'ProductDAO' object has no attribute '_get_any_by_factory_item_available'. Did you mean: 'get_by_factory_item_available'?` |
| PRD-GT-10 | strict | Then 1 | `assert [227382, 227383] == [227382] Left contains one more item: 227383 Use -v to get more diff` |
| PRD-GT-11 | strict | Then 1 | `assert [<app.models....026AACB28C80>] == [] Left contains one more item: <app.models.product.Product object at 0x0000026AACB28C80> Use -v to ge` |
| PRD-GT-12 | strict | Then 1 | `assert [<app.models....026AAD364A10>] == [] Left contains one more item: <app.models.product.Product object at 0x0000026AAD364A10> Use -v to ge` |
| PRD-GT-16 | strict | Then 1 | `assert [<app.models....026AACB1E090>] == [] Left contains one more item: <app.models.product.Product object at 0x0000026AACB1E090> Use -v to ge` |
| PRD-GT-17 | strict | Then 2 | `AssertionError: assert 'ORDER BY' in 'SELECT products.id AS products_id, products.workspace_id AS products_workspace_id, products.item_id AS products_` |
| PRD-GT-18 | non-strict | Then 2 | `assert [227392, 227393, 227391] == [227391, 227392, 227393] At index 0 diff: 227392 != 227391 Use -v to get more diff` |
| PRD-GT-19 | non-strict | — | passed today by physical order (non-strict); failed under the explicit wrong order |
| PRD-SD-07 | strict | Then 2 | `assert datetime.datetime(2026, 11, 3, 10, 15, 18, 186282) == datetime.datetime(2031, 5, 6, 7, 8, 9) + where datetime.datetime(2026, 11, 3, 10, 15, 1` |
| PRD-SD-08 | strict | Then 2 | `assert datetime.datetime(2026, 11, 3, 21, 15, 18, 252015) == datetime.datetime(2031, 5, 6, 7, 8, 9) + where datetime.datetime(2026, 11, 3, 21, 15, 1` |

## Explicit wrong order (non-strict proof)
A scratch plugin (`prodx\wrong.py`, `-p wrong`) rewrites the module's list SELECT with an explicit wrong `ORDER BY` (unordered lists: `<table>.id DESC` or `ASC`; dated lists: the same date order with the tie broken the wrong way), and the file runs with `--runxfail`.

| Rewrite | Non-strict cards that fail | Pass cards that fail |
|---|---|---|
| `id DESC` (dated lists: date order kept, tie `id ASC`) | 9 of 9 | 1 (PRD-GW-57 in their Revision 1 form; 0 after Revision 1b) |
| `id ASC` (dated lists: tie `id DESC`, the intended order) | 4 of 9 | 0 |

Every non-strict card fails under the first rewrite, each at the Then its card names (checked: 54 of 54 across the batch). Not caught: [].

**Lines past the failure point (reference plugin).** `prodx\ref.py` (`-p ref`) replaces the methods in-process with the intended behaviour of each BUG the cards cite (orders, hide rules, trimmed compare, the formula-code index inside the test's transaction, schema trimming, UTC clocks, numeric suffix); nothing in `app/` changes. With `--runxfail`: **170 passed**, so every check after each xfail's failure point holds once the bug is fixed, and no pass card breaks under the fix.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Coverage gaps
None — 100% line and branch coverage of `app/dao/product.py` (36 statements, 4 branches, 0 missed), run with a private `COVERAGE_FILE`. Inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
| Run | Passed | xfailed | xpassed (non-strict) | Not as designed |
|---|---|---|---|---|
| Default, run 1 (file alone) | 127 | 38 | 5 | 0 |
| Default, run 2 (file alone) | 127 | 40 | 3 | 0 |
| Default, run 3 (file alone) | 127 | 38 | 5 | 0 |
| `enable_seqscan=off` | 127 | 40 | 3 | 0 |
| `enable_seqscan=off`, hash join and nested loop off | 127 | 37 | 6 | 0 |
| `enable_hashjoin=off` | 127 | 40 | 3 | 0 |
| index, bitmap and index-only scans off | 127 | 38 | 5 | 0 |
| the line above, hash and merge join off | 127 | 40 | 3 | 0 |
| database `TimeZone` `Asia/Dhaka` | 127 | 38 | 5 | 0 |
| database `TimeZone` `America/New_York` | 127 | 38 | 5 | 0 |
| `--runxfail` with the reference plugin | 170 of 170 | — | — | 0 |

Every pass card passed and every strict xfail xfailed in every run above. `PGOPTIONS` carried the forced plans and the time zones.
Non-strict cards that passed by physical order in some runs: PRD-GW-39 (10 of 10), PRD-GW-40 (10 of 10), PRD-GW-42 (6 of 10), PRD-GW-44 (6 of 10), PRD-GT-19 (8 of 10), PRD-GT-18 (2 of 10), PRD-GW-41 (1 of 10). All of them fail under the explicit wrong order above.

**Clock:** no card here compares two real-clock stamps, so nothing needed repeating.

`ruff check` on the file: all checks passed (the header `noqa` covers SIM117 for the Conventions' nested `with` and DTZ001 for the Conventions' naive datetimes). Line endings: LF.

## Chosen-row cards (Revision 1b)
Revision 1 versions of PRD-GW-57 named one row (`skip=1, limit=1`) on a query with no `ORDER BY` and could fail for order alone (explicit `id DESC`; or a sequential scan after an update moved the first W1 row to the end of the heap; for PRD-GW-57, after an update moved that row's item). Revision 1b checks `limit=2`: two rows, A and B as a set, Z absent. Re-checked: they pass under both explicit wrong orders, the default plan, `enable_seqscan=off` with and without hash join and nested loop, and forced physical orders (each of Z, A, B moved to the end of the heap, and A's item moved). A broken variant that applies the workspace filter after the `LIMIT` fails every one on Then 1 (`1 == 2`). Scratch: `prodx\phys2_test.py`.

## Revision history
- **Revision 1 (2026-11-03):** patched, not regenerated: every existing test block kept byte for byte; PRD-GT-16 rewritten as its card now says (`result == []`, strict xfail BUG-1338; the variable `a` is gone with the old Then); added PRD-GW-57, GA-17, GT-23, GT-24, GT-25, RS-10. The dropped `newest` line of GW-45 was never written. The reference plugin's `get_by_item` now also hides a removed item (BUG-1338). Revision 1b: PRD-GW-57 patched to `limit=2`, two rows, A and B as a set, Z absent (see Chosen-row cards); full file re-run, ruff, audit. Revision 1 re-run: `--runxfail`, reference plugin, explicit wrong order, 3 runs plus forced plans and time zones, ruff, coverage; tables above are from these runs.

## Notes for maintainers
- When BUG-1325, BUG-1326, BUG-1327, BUG-1328, BUG-1335, BUG-1336, BUG-1338 are fixed, their strict cards XPASS and fail: remove the marker. The non-strict cards then pass every time; remove their marker too.
- "Nothing written" and the `count:` lines count committed rows of all workspaces too. A run beside something that commits to these tables could break them; nothing did here.
- The non-strict order cards force a sequential scan; they rest on physical row order today and can pass by accident (see Stability). Never loosen the strict SQL recorder card beside them.
- The PRD-GA cards carry `raises=AttributeError`: `_get_any_by_factory_item_available` does not exist; any other failure shows as a real failure.
