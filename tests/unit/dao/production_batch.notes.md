# Execution notes — `app/dao/production_batch.py`

> Cases: `tests/unit/dao/production_batch.cases.md` (READY, Revision 1, 227 cases; spec APPROVED 2026-11-02) · Tests: `tests/unit/dao/test_production_batch.py` · Source commit: e48a092
> Result: **227 tests for 227 cases — 189 passed · 38 xfail (29 strict, 9 non-strict) · 0 discrepancies · 0 errors** — branch coverage 95% (36 statements, 6 branches, 1 line and 1 branch missed). In run 1 of the file alone 38 xfailed and 0 non-strict xpassed.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_production_batch.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file written for this batch (not kept in the repo; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\prodx\gen.py`), so values are the card's own text; an unknown Given, When or Then line stopped it, and none did. Fixtures, builders and helpers were written from the Conventions. A separate audit script checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matching the card's Then count in order with a check under each, every quoted literal of the card present, the When call present, marker strictness and bug matching the Expect line, no unused argument, no fixture used without being an argument, LF line endings. 0 problems.

## How the tests are built
- **Patched:** only the clock of `generate_batch_number`: `clocks(L, U)` patches `app.dao.production_batch.datetime` (`.now.return_value = L`) and `app.dao.production_batch.utcnow` (`create=True`, `return_value=U`) around the When, on every GN card. `created_at` / `updated_at` come from the real clock and no card asserts them.
- **Standing rows:** one fixture per Conventions row, each depending on the one listed before it (and on any row it names), so they are flushed one at a time in Conventions order and the ids rise in that order. The autouse `standing_rows` makes all of them exist in every test; a test lists only those it names.
- **Builders:** `new_<row>(...)` builds the Conventions row with its defaults (not added); `mk_<row>(...)` adds and flushes it. A card's columns are passed as keywords in card order. The `add_all` Givens build `new_<row>` objects in a list comprehension and flush once (`add_many`); `newest` / `in_order` lists are taken from that list.
- **Reading helpers (no expected values inside):** `ids`; `snap` ("unchanged": every column by a Core select of the table, after `db.expire_all()`); `without` ("unchanged ... except"); `reread` ("re-read": expire, then `db.get`); `stored_count` ("nothing written"); `count_rows` ("count:" lines, Core count with the stated filter); `seqscan` (the three `SET LOCAL` steps). Only those the cards use are in the file.
- **Statement recorder:** the `recorder` fixture listens on the session's connection (`before_cursor_execute`) from `recorder.start()` at the start of the When to the end of the test, as the Conventions say, and removes the listener at teardown. `sql` (the one SELECT `FROM <table>`, fails loudly unless there is exactly one), `order_part` and `selects` are read at the first `statement:` line or before the first reading helper, whichever comes first, so the helpers' own SELECTs never enter them; `written` is read at its line.
- **Errors:** `pytest.raises(...)` around `db.begin_nested()` around the When (no savepoint for `ValidationError`); `exc` is bound only when a later Then reads it. **Rolled back** cards: `sp = db.begin_nested()` before the When, `patch.object(db, "commit", wraps=db.commit)` as the spy, `sp.rollback()` directly before the first "after the savepoint rollback" check.
- **Given rows no line names again** are built without a variable. Row letters of the cards are lower case in the code.
- **Joined relationships:** checked `app/models/`: none of this module's models has a `lazy="joined"` relationship (the only joined relationship among the seven modules' models is `Product.item`), so the `"JOIN" not in sql` recorder cards hold as designed.

## xfail check (`--runxfail`, failing value read)
Every xfail card was run with `--runxfail`; the failing line's `# Then N` was read against the card's "Fails today on", and the failing value against what the card says. Strict cards: all 29 fail at the Then the card names, with the value the card describes.
4 cards fail in the When, before `# Then 1`, which is what their "Fails today on: Then 1" says (the call itself raises): BAT-GN-25, BAT-GN-26, BAT-GN-27, BAT-GN-28. The exception was read: ValueError: invalid literal for int() with base 10: ''; ValueError: invalid literal for int() with base 10: '12a'; ValueError: invalid literal for int() with base 10: 'ABC'.

| Case | Strict | Fails on | Value read under `--runxfail` |
|---|---|---|---|
| BAT-GW-06 | strict | Then 1 | `assert [707150, 707151] == [707151] At index 0 diff: 707150 != 707151 Left contains one more item: 707151 Use -v to get more diff` |
| BAT-GW-07 | strict | Then 1 | `assert [<app.models....026AACE2B2C0>] == [] Left contains one more item: <app.models.production_batch.ProductionBatch object at 0x0000026AACE2B2C` |
| BAT-GW-11 | strict | Then 1 | `assert [707156, 7071...07158, 707159] == [707159] At index 0 diff: 707156 != 707159 Left contains 3 more items, first extra item: 707157 Use ` |
| BAT-GW-12 | strict | Then 1 | `assert [707161] == [707162] At index 0 diff: 707161 != 707162 Use -v to get more diff` |
| BAT-GW-13 | strict | Then 4 | `AssertionError: assert '.id' in ' production_batches.batch_date DESC \n '` |
| BAT-GW-14 | non-strict | Then 2 | `assert [707166, 7071...07164, 707165] == [707167, 7071...07165, 707164] At index 0 diff: 707166 != 707167 Use -v to get more diff` |
| BAT-GW-15 | non-strict | Then 2 | `assert [707168, 7071...07170, 707171] == [707170, 7071...07168, 707171] At index 0 diff: 707168 != 707170 Use -v to get more diff` |
| BAT-GW-16 | non-strict | Then 2 | `assert [707173, 7071...07176, 707172] == [707176, 7071...07173, 707172] At index 0 diff: 707173 != 707176 Use -v to get more diff` |
| BAT-GL-07 | strict | Then 1 | `assert [<app.models....026AACB83CB0>] == [] Left contains one more item: <app.models.production_batch.ProductionBatch object at 0x0000026AACB83CB` |
| BAT-GL-08 | strict | Then 1 | `assert [<app.models....026AACDDF3B0>] == [] Left contains one more item: <app.models.production_batch.ProductionBatch object at 0x0000026AACDDF3B` |
| BAT-GL-15 | strict | Then 4 | `AssertionError: assert '.id' in ' production_batches.batch_date DESC \n '` |
| BAT-GL-16 | non-strict | Then 2 | `assert [707430, 7074...07428, 707429] == [707431, 7074...07429, 707428] At index 0 diff: 707430 != 707431 Use -v to get more diff` |
| BAT-GL-17 | non-strict | Then 2 | `assert [707432, 7074...07434, 707435] == [707434, 7074...07432, 707435] At index 0 diff: 707432 != 707434 Use -v to get more diff` |
| BAT-GF-06 | strict | Then 1 | `assert [707681, 707682] == [707682] At index 0 diff: 707681 != 707682 Left contains one more item: 707682 Use -v to get more diff` |
| BAT-GF-07 | strict | Then 1 | `assert [<app.models....026AABA6B2C0>] == [] Left contains one more item: <app.models.production_batch.ProductionBatch object at 0x0000026AABA6B2C` |
| BAT-GF-11 | strict | Then 1 | `assert [707688] == [707689] At index 0 diff: 707688 != 707689 Use -v to get more diff` |
| BAT-GF-14 | strict | Then 4 | `AssertionError: assert '.id' in ' production_batches.batch_date DESC \n '` |
| BAT-GF-15 | non-strict | Then 2 | `assert [707695, 7076...07693, 707694] == [707696, 7076...07694, 707693] At index 0 diff: 707695 != 707696 Use -v to get more diff` |
| BAT-GF-16 | non-strict | Then 2 | `assert [707697, 7076...07699, 707700] == [707699, 7076...07697, 707700] At index 0 diff: 707697 != 707699 Use -v to get more diff` |
| BAT-GS-05 | strict | Then 1 | `assert [707946, 707947] == [707947] At index 0 diff: 707946 != 707947 Left contains one more item: 707947 Use -v to get more diff` |
| BAT-GS-06 | strict | Then 1 | `assert [<app.models....026AACDDD370>] == [] Left contains one more item: <app.models.production_batch.ProductionBatch object at 0x0000026AACDDD37` |
| BAT-GS-10 | strict | Then 1 | `assert [707953] == [707954] At index 0 diff: 707953 != 707954 Use -v to get more diff` |
| BAT-GS-22 | strict | Then 4 | `AssertionError: assert '.id' in ' production_batches.batch_date DESC \n '` |
| BAT-GS-23 | non-strict | Then 2 | `assert [707969, 7079...07967, 707968] == [707970, 7079...07968, 707967] At index 0 diff: 707969 != 707970 Use -v to get more diff` |
| BAT-GS-24 | non-strict | Then 2 | `assert [707971, 7079...07973, 707974] == [707973, 7079...07971, 707974] At index 0 diff: 707971 != 707973 Use -v to get more diff` |
| BAT-CS-18 | strict | Then 1 | `assert 2 == 1` |
| BAT-CS-19 | strict | Then 1 | `assert 1 == 0` |
| BAT-CS-20 | strict | Then 1 | `assert 1 == 0` |
| BAT-GN-03 | strict | Then 1 | `AssertionError: assert 'BATCH-2031-001' == 'BATCH-2030-001' - BATCH-2030-001 ? ^ + BATCH-2031-001 ? ^` |
| BAT-GN-04 | strict | Then 1 | `AssertionError: assert 'BATCH-2030-001' == 'BATCH-2031-001' - BATCH-2031-001 ? ^ + BATCH-2030-001 ? ^` |
| BAT-GN-19 | strict | Then 1 | `AssertionError: assert 'BATCH-2026-1000' == 'BATCH-2026-1001' - BATCH-2026-1001 ? ^ + BATCH-2026-1000 ? ^` |
| BAT-GN-20 | strict | Then 1 | `AssertionError: assert 'BATCH-2026-1000' == 'BATCH-2026-1001' - BATCH-2026-1001 ? ^ + BATCH-2026-1000 ? ^` |
| BAT-GN-21 | strict | Then 1 | `AssertionError: assert 'BATCH-2026-1000' == 'BATCH-2026-1002' - BATCH-2026-1002 ? ^ + BATCH-2026-1000 ? ^` |
| BAT-GN-22 | strict | Then 1 | `AssertionError: assert 'BATCH-2026-10000' == 'BATCH-2026-10001' - BATCH-2026-10001 ? ^ + BATCH-2026-10000 ? ^` |
| BAT-GN-25 | strict | the When (Then 1 not reached) | `ValueError: invalid literal for int() with base 10: 'ABC'` |
| BAT-GN-26 | strict | the When (Then 1 not reached) | `ValueError: invalid literal for int() with base 10: ''` |
| BAT-GN-27 | strict | the When (Then 1 not reached) | `ValueError: invalid literal for int() with base 10: '12a'` |
| BAT-GN-28 | strict | the When (Then 1 not reached) | `ValueError: invalid literal for int() with base 10: 'ABC'` |

## Explicit wrong order (non-strict proof)
A scratch plugin (`prodx\wrong.py`, `-p wrong`) rewrites the module's list SELECT with an explicit wrong `ORDER BY` (unordered lists: `<table>.id DESC` or `ASC`; dated lists: the same date order with the tie broken the wrong way), and the file runs with `--runxfail`.

| Rewrite | Non-strict cards that fail | Pass cards that fail |
|---|---|---|
| `id DESC` (dated lists: date order kept, tie `id ASC`) | 9 of 9 | 0 |
| `id ASC` (dated lists: tie `id DESC`, the intended order) | 0 of 9 | 0 |

Every non-strict card fails under the first rewrite, each at the Then its card names (checked: 54 of 54 across the batch). Not caught: [].

**Lines past the failure point (reference plugin).** `prodx\ref.py` (`-p ref`) replaces the methods in-process with the intended behaviour of each BUG the cards cite (orders, hide rules, trimmed compare, the formula-code index inside the test's transaction, schema trimming, UTC clocks, numeric suffix); nothing in `app/` changes. With `--runxfail`: **227 passed**, so every check after each xfail's failure point holds once the bug is fixed, and no pass card breaks under the fix.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 166 | dead | `get_by_date_range`'s query: Not specified, dead code to be removed (P1). |
| 216->220 | dead | the `year` given branch of `generate_batch_number` (`if year is None` false): the `year` parameter is dead, to be removed (P2); no card passes `year`. |

Branch coverage 95% of `app/dao/production_batch.py` (36 statements, 6 branches, 1 line and 1 branch missed), run with a private `COVERAGE_FILE`. Everything else is covered; inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
| Run | Passed | xfailed | xpassed (non-strict) | Not as designed |
|---|---|---|---|---|
| Default, run 1 (file alone) | 189 | 38 | 0 | 0 |
| Default, run 2 (file alone) | 189 | 38 | 0 | 0 |
| Default, run 3 (file alone) | 189 | 38 | 0 | 0 |
| `enable_seqscan=off` | 189 | 38 | 0 | 0 |
| `enable_seqscan=off`, hash join and nested loop off | 189 | 38 | 0 | 0 |
| `enable_hashjoin=off` | 189 | 38 | 0 | 0 |
| index, bitmap and index-only scans off | 189 | 38 | 0 | 0 |
| the line above, hash and merge join off | 189 | 38 | 0 | 0 |
| database `TimeZone` `Asia/Dhaka` | 189 | 38 | 0 | 0 |
| database `TimeZone` `America/New_York` | 189 | 38 | 0 | 0 |
| `--runxfail` with the reference plugin | 227 of 227 | — | — | 0 |

Every pass card passed and every strict xfail xfailed in every run above. `PGOPTIONS` carried the forced plans and the time zones.
No non-strict card passed by accident in any run.

**Clock:** no card here compares two real-clock stamps, so nothing needed repeating.

`ruff check` on the file: all checks passed (the header `noqa` covers SIM117 for the Conventions' nested `with` and DTZ001 for the Conventions' naive datetimes). Line endings: LF.

## Revision history
- **Revision 1 (2026-11-03):** patched, not regenerated: every existing test block kept byte for byte; added BAT-GW-33, GL-34, GF-33, GF-34, GS-41, GS-42, CS-30, CS-31, CS-32, GN-33. Revision 1 re-run: `--runxfail`, reference plugin, explicit wrong order, 3 runs plus forced plans and time zones, ruff, coverage; tables above are from these runs.

## Notes for maintainers
- When BUG-1321, BUG-1330, BUG-1333, BUG-1334 are fixed, their strict cards XPASS and fail: remove the marker. The non-strict cards then pass every time; remove their marker too.
- "Nothing written" and the `count:` lines count committed rows of all workspaces too. A run beside something that commits to these tables could break them; nothing did here.
- BAT-GN-25 … GN-28 fail inside `generate_batch_number` with `ValueError` before Then 1: the `-ABC` row sorts highest under the database collation, as the spec's Today note implies, so the card the designer flagged as a possible XPASS does not XPASS.
