# Execution notes — `app/dao/production_line.py`

> Cases: `tests/unit/dao/production_line.cases.md` (READY, Revision 1, 116 cases; spec APPROVED 2026-11-02) · Tests: `tests/unit/dao/test_production_line.py` · Source commit: e48a092
> Result: **116 tests for 116 cases — 89 passed · 27 xfail (13 strict, 14 non-strict) · 0 discrepancies · 0 errors** — branch coverage 94% (16 statements, 0 branches, 1 missed). In run 1 of the file alone 23 xfailed and 4 non-strict xpassed.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_production_line.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file written for this batch (not kept in the repo; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\prodx\gen.py`), so values are the card's own text; an unknown Given, When or Then line stopped it, and none did. Fixtures, builders and helpers were written from the Conventions. A separate audit script checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matching the card's Then count in order with a check under each, every quoted literal of the card present, the When call present, marker strictness and bug matching the Expect line, no unused argument, no fixture used without being an argument, LF line endings. 0 problems.

## How the tests are built
- **Nothing is patched or mocked** (Conventions, Externals: None).
- **Standing rows:** one fixture per Conventions row, each depending on the one listed before it (and on any row it names), so they are flushed one at a time in Conventions order and the ids rise in that order. The autouse `standing_rows` makes all of them exist in every test; a test lists only those it names.
- **Builders:** `new_<row>(...)` builds the Conventions row with its defaults (not added); `mk_<row>(...)` adds and flushes it. A card's columns are passed as keywords in card order. The `add_all` Givens build `new_<row>` objects in a list comprehension and flush once (`add_many`); `newest` / `in_order` lists are taken from that list.
- **Reading helpers (no expected values inside):** `ids`; `snap` ("unchanged": every column by a Core select of the table, after `db.expire_all()`); `without` ("unchanged ... except"); `reread` ("re-read": expire, then `db.get`); `stored_count` ("nothing written"); `count_rows` ("count:" lines, Core count with the stated filter); `seqscan` (the three `SET LOCAL` steps). Only those the cards use are in the file.
- **Statement recorder:** the `recorder` fixture listens on the session's connection (`before_cursor_execute`) from `recorder.start()` at the start of the When to the end of the test, as the Conventions say, and removes the listener at teardown. `sql` (the one SELECT `FROM <table>`, fails loudly unless there is exactly one), `order_part` and `selects` are read at the first `statement:` line or before the first reading helper, whichever comes first, so the helpers' own SELECTs never enter them; `written` is read at its line.
- **Errors:** `pytest.raises(...)` around `db.begin_nested()` around the When (no savepoint for `ValidationError`); `exc` is bound only when a later Then reads it. **Rolled back** cards: `sp = db.begin_nested()` before the When, `patch.object(db, "commit", wraps=db.commit)` as the spy, `sp.rollback()` directly before the first "after the savepoint rollback" check.
- **Given rows no line names again** are built without a variable. Row letters of the cards are lower case in the code.
- **Joined relationships:** checked `app/models/`: none of this module's models has a `lazy="joined"` relationship (the only joined relationship among the seven modules' models is `Product.item`), so the `"JOIN" not in sql` recorder cards hold as designed.

## xfail check (`--runxfail`, failing value read)
Every xfail card was run with `--runxfail`; the failing line's `# Then N` was read against the card's "Fails today on", and the failing value against what the card says. Strict cards: all 13 fail at the Then the card names, with the value the card describes.

| Case | Strict | Fails on | Value read under `--runxfail` |
|---|---|---|---|
| PLN-GW-07 | strict | Then 2 | `AssertionError: assert 'ORDER BY' in 'SELECT production_lines.id AS production_lines_id, production_lines.workspace_id AS production_lines_workspace_i` |
| PLN-GW-08 | non-strict | Then 2 | `assert [931661, 931662, 931660] == [931660, 931661, 931662] At index 0 diff: 931661 != 931660 Use -v to get more diff` |
| PLN-GW-09 | non-strict | Then 2 | `assert [931664, 9316...31667, 931663] == [931663, 9316...31666, 931667] At index 0 diff: 931664 != 931663 Use -v to get more diff` |
| PLN-GF-11 | strict | Then 1 | `assert [<app.models....026AABA38E60>] == [] Left contains one more item: <app.models.production_line.ProductionLine object at 0x0000026AABA38E60>` |
| PLN-GF-12 | strict | Then 1 | `assert [<app.models....026AABA39430>] == [] Left contains one more item: <app.models.production_line.ProductionLine object at 0x0000026AABA39430>` |
| PLN-GF-16 | strict | Then 2 | `AssertionError: assert 'ORDER BY' in 'SELECT production_lines.id AS production_lines_id, production_lines.workspace_id AS production_lines_workspace_i` |
| PLN-GF-17 | non-strict | Then 2 | `assert [931913, 931914, 931915] == [931914, 931915, 931913] At index 0 diff: 931913 != 931914 Use -v to get more diff` |
| PLN-GF-18 | non-strict | — | passed today by physical order (non-strict); failed under the explicit wrong order |
| PLN-GF-19 | non-strict | — | passed today by physical order (non-strict); failed under the explicit wrong order |
| PLN-GF-20 | non-strict | Then 2 | `assert [931921, 931922, 931920] == [931920, 931921, 931922] At index 0 diff: 931921 != 931920 Use -v to get more diff` |
| PLN-GF-21 | non-strict | Then 2 | `assert [931924] == [931925] At index 0 diff: 931924 != 931925 Use -v to get more diff` |
| PLN-GF-22 | non-strict | Then 2 | `assert [931926, 9319...31930, 931927] == [931927, 9319...31930, 931929] At index 0 diff: 931926 != 931927 Use -v to get more diff` |
| PLN-GA-10 | strict | Then 1 | `assert [932176, 932177] == [932177] At index 0 diff: 932176 != 932177 Left contains one more item: 932177 Use -v to get more diff` |
| PLN-GA-11 | strict | Then 1 | `assert [<app.models....026AABA132C0>] == [] Left contains one more item: <app.models.production_line.ProductionLine object at 0x0000026AABA132C0>` |
| PLN-GA-12 | strict | Then 1 | `assert [<app.models....026AACBDE870>] == [] Left contains one more item: <app.models.production_line.ProductionLine object at 0x0000026AACBDE870>` |
| PLN-GA-13 | strict | Then 1 | `assert 2 == 1 + where 2 = len([<app.models.production_line.ProductionLine object at 0x0000026AABA1C470>, <app.models.production_line.ProductionLine ` |
| PLN-GA-17 | strict | Then 2 | `AssertionError: assert 'ORDER BY' in 'SELECT production_lines.id AS production_lines_id, production_lines.workspace_id AS production_lines_workspace_i` |
| PLN-GA-18 | non-strict | Then 2 | `assert [932189, 932190, 932191] == [932190, 932191, 932189] At index 0 diff: 932189 != 932190 Use -v to get more diff` |
| PLN-GA-19 | non-strict | — | passed today by physical order (non-strict); failed under the explicit wrong order |
| PLN-GA-20 | non-strict | — | passed today by physical order (non-strict); failed under the explicit wrong order |
| PLN-GA-21 | non-strict | Then 2 | `assert [932197, 932198, 932196] == [932196, 932197, 932198] At index 0 diff: 932197 != 932196 Use -v to get more diff` |
| PLN-GA-22 | non-strict | Then 2 | `assert [932200] == [932201] At index 0 diff: 932200 != 932201 Use -v to get more diff` |
| PLN-GA-23 | non-strict | Then 2 | `assert [932202, 9322...32206, 932203] == [932203, 9322...32206, 932205] At index 0 diff: 932202 != 932203 Use -v to get more diff` |
| PLN-SCH-01 | strict | Then 1 | `Failed: DID NOT RAISE ValidationError` |
| PLN-SCH-02 | strict | Then 1 | `Failed: DID NOT RAISE ValidationError` |
| PLN-SCH-03 | strict | Then 1 | `AssertionError: assert ' a ' == 'a' - a + a` |
| PLN-SCH-04 | strict | Then 1 | `AssertionError: assert ' a ' == 'a' - a + a` |

## Explicit wrong order (non-strict proof)
A scratch plugin (`prodx\wrong.py`, `-p wrong`) rewrites the module's list SELECT with an explicit wrong `ORDER BY` (unordered lists: `<table>.id DESC` or `ASC`; dated lists: the same date order with the tie broken the wrong way), and the file runs with `--runxfail`.

| Rewrite | Non-strict cards that fail | Pass cards that fail |
|---|---|---|
| `id DESC` (dated lists: date order kept, tie `id ASC`) | 14 of 14 | 3 (PLN-GW-23, PLN-GF-36, PLN-GA-35 in their Revision 1 form; 0 after Revision 1b) |
| `id ASC` (dated lists: tie `id DESC`, the intended order) | 6 of 14 | 0 |

Every non-strict card fails under the first rewrite, each at the Then its card names (checked: 54 of 54 across the batch). Not caught: [].

**Lines past the failure point (reference plugin).** `prodx\ref.py` (`-p ref`) replaces the methods in-process with the intended behaviour of each BUG the cards cite (orders, hide rules, trimmed compare, the formula-code index inside the test's transaction, schema trimming, UTC clocks, numeric suffix); nothing in `app/` changes. With `--runxfail`: **116 passed**, so every check after each xfail's failure point holds once the bug is fixed, and no pass card breaks under the fix.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 80 | dead | `get_by_machine`'s query: the spec lists the method under Not specified as dead code to be removed (P1). No card calls it. |

Branch coverage 94% of `app/dao/production_line.py` (16 statements, 0 branches, 1 missed), run with a private `COVERAGE_FILE`. Everything else is covered; inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
| Run | Passed | xfailed | xpassed (non-strict) | Not as designed |
|---|---|---|---|---|
| Default, run 1 (file alone) | 89 | 23 | 4 | 0 |
| Default, run 2 (file alone) | 89 | 23 | 4 | 0 |
| Default, run 3 (file alone) | 89 | 23 | 4 | 0 |
| `enable_seqscan=off` | 89 | 23 | 4 | 0 |
| `enable_seqscan=off`, hash join and nested loop off | 89 | 19 | 8 | 0 |
| `enable_hashjoin=off` | 89 | 23 | 4 | 0 |
| index, bitmap and index-only scans off | 89 | 23 | 4 | 0 |
| the line above, hash and merge join off | 89 | 23 | 4 | 0 |
| database `TimeZone` `Asia/Dhaka` | 89 | 23 | 4 | 0 |
| database `TimeZone` `America/New_York` | 89 | 23 | 4 | 0 |
| `--runxfail` with the reference plugin | 116 of 116 | — | — | 0 |

Every pass card passed and every strict xfail xfailed in every run above. `PGOPTIONS` carried the forced plans and the time zones.
Non-strict cards that passed by physical order in some runs: PLN-GF-18 (10 of 10), PLN-GF-19 (10 of 10), PLN-GA-19 (10 of 10), PLN-GA-20 (10 of 10), PLN-GW-08 (1 of 10), PLN-GW-09 (1 of 10), PLN-GF-20 (1 of 10), PLN-GA-21 (1 of 10). All of them fail under the explicit wrong order above.

**Clock:** no card here compares two real-clock stamps, so nothing needed repeating.

`ruff check` on the file: all checks passed (the header `noqa` covers SIM117 for the Conventions' nested `with` and DTZ001 for the Conventions' naive datetimes). Line endings: LF.

## Chosen-row cards (Revision 1b)
Revision 1 versions of PLN-GW-23, PLN-GF-36, PLN-GA-35 named one row (`skip=1, limit=1`) on a query with no `ORDER BY` and could fail for order alone (explicit `id DESC`; or a sequential scan after an update moved the first W1 row to the end of the heap). Revision 1b checks `limit=2`: two rows, A and B as a set, Z absent. Re-checked: they pass under both explicit wrong orders, the default plan, `enable_seqscan=off` with and without hash join and nested loop, and forced physical orders (each of Z, A, B moved to the end of the heap). A broken variant that applies the workspace filter after the `LIMIT` fails every one on Then 1 (`1 == 2`). Scratch: `prodx\phys2_test.py`.

## Revision history
- **Revision 1 (2026-11-03):** patched, not regenerated: every existing test block kept byte for byte; added PLN-GW-23, GF-36, GA-35. The dropped `newest` lines of GW-10, GF-25, GA-24 were never written (the variable was unused), so those tests did not change. Revision 1b: PLN-GW-23, PLN-GF-36, PLN-GA-35 patched to `limit=2`, two rows, A and B as a set, Z absent (see Chosen-row cards); full file re-run, ruff, audit. Revision 1 re-run: `--runxfail`, reference plugin, explicit wrong order, 3 runs plus forced plans and time zones, ruff, coverage; tables above are from these runs.

## Notes for maintainers
- When BUG-100, BUG-1310, BUG-1311, BUG-1312, BUG-1313 are fixed, their strict cards XPASS and fail: remove the marker. The non-strict cards then pass every time; remove their marker too.
- "Nothing written" and the `count:` lines count committed rows of all workspaces too. A run beside something that commits to these tables could break them; nothing did here.
- The non-strict order cards force a sequential scan; they rest on physical row order today and can pass by accident (see Stability). Never loosen the strict SQL recorder card beside them.
