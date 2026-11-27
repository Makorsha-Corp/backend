# Execution notes — `app/dao/production_batch_item.py`

> Cases: `tests/unit/dao/production_batch_item.cases.md` (READY, Revision 1, 61 cases; spec APPROVED 2026-11-02) · Tests: `tests/unit/dao/test_production_batch_item.py` · Source commit: e48a092
> Result: **61 tests for 61 cases — 55 passed · 6 xfail (2 strict, 4 non-strict) · 0 discrepancies · 0 errors** — branch coverage 93% (14 statements, 0 branches, 1 missed). In run 1 of the file alone 4 xfailed and 2 non-strict xpassed.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_production_batch_item.py -q -p no:cacheprovider`

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
Every xfail card was run with `--runxfail`; the failing line's `# Then N` was read against the card's "Fails today on", and the failing value against what the card says. Strict cards: all 2 fail at the Then the card names, with the value the card describes.

| Case | Strict | Fails on | Value read under `--runxfail` |
|---|---|---|---|
| BIT-G-09 | strict | Then 2 | `AssertionError: assert 'ORDER BY' in 'SELECT production_batch_items.id AS production_batch_items_id, production_batch_items.workspace_id AS production` |
| BIT-G-10 | non-strict | Then 2 | `assert [63017, 63018, 63016] == [63016, 63017, 63018] At index 0 diff: 63017 != 63016 Use -v to get more diff` |
| BIT-G-11 | non-strict | — | passed today by physical order (non-strict); failed under the explicit wrong order |
| BIT-R-16 | strict | Then 2 | `AssertionError: assert 'ORDER BY' in 'SELECT production_batch_items.id AS production_batch_items_id, production_batch_items.workspace_id AS production` |
| BIT-R-17 | non-strict | Then 2 | `assert [63150, 63151, 63149] == [63149, 63150, 63151] At index 0 diff: 63150 != 63149 Use -v to get more diff` |
| BIT-R-18 | non-strict | — | passed today by physical order (non-strict); failed under the explicit wrong order |

## Explicit wrong order (non-strict proof)
A scratch plugin (`prodx\wrong.py`, `-p wrong`) rewrites the module's list SELECT with an explicit wrong `ORDER BY` (unordered lists: `<table>.id DESC` or `ASC`; dated lists: the same date order with the tie broken the wrong way), and the file runs with `--runxfail`.

| Rewrite | Non-strict cards that fail | Pass cards that fail |
|---|---|---|
| `id DESC` (dated lists: date order kept, tie `id ASC`) | 4 of 4 | 0 |
| `id ASC` (dated lists: tie `id DESC`, the intended order) | 0 of 4 | 0 |

Every non-strict card fails under the first rewrite, each at the Then its card names (checked: 54 of 54 across the batch). Not caught: [].

**Lines past the failure point (reference plugin).** `prodx\ref.py` (`-p ref`) replaces the methods in-process with the intended behaviour of each BUG the cards cite (orders, hide rules, trimmed compare, the formula-code index inside the test's transaction, schema trimming, UTC clocks, numeric suffix); nothing in `app/` changes. With `--runxfail`: **61 passed**, so every check after each xfail's failure point holds once the bug is fixed, and no pass card breaks under the fix.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 84 | dead | `get_by_item`'s query: Not specified, dead code to be removed (P1). |

Branch coverage 93% of `app/dao/production_batch_item.py` (14 statements, 0 branches, 1 missed), run with a private `COVERAGE_FILE`. Everything else is covered; inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
| Run | Passed | xfailed | xpassed (non-strict) | Not as designed |
|---|---|---|---|---|
| Default, run 1 (file alone) | 55 | 4 | 2 | 0 |
| Default, run 2 (file alone) | 55 | 4 | 2 | 0 |
| Default, run 3 (file alone) | 55 | 4 | 2 | 0 |
| `enable_seqscan=off` | 55 | 4 | 2 | 0 |
| `enable_seqscan=off`, hash join and nested loop off | 55 | 4 | 2 | 0 |
| `enable_hashjoin=off` | 55 | 4 | 2 | 0 |
| index, bitmap and index-only scans off | 55 | 4 | 2 | 0 |
| the line above, hash and merge join off | 55 | 4 | 2 | 0 |
| database `TimeZone` `Asia/Dhaka` | 55 | 4 | 2 | 0 |
| database `TimeZone` `America/New_York` | 55 | 4 | 2 | 0 |
| `--runxfail` with the reference plugin | 61 of 61 | — | — | 0 |

Every pass card passed and every strict xfail xfailed in every run above. `PGOPTIONS` carried the forced plans and the time zones.
Non-strict cards that passed by physical order in some runs: BIT-G-11 (10 of 10), BIT-R-18 (10 of 10). All of them fail under the explicit wrong order above.

**Clock:** no card here compares two real-clock stamps, so nothing needed repeating.

`ruff check` on the file: all checks passed (the header `noqa` covers SIM117 for the Conventions' nested `with` and DTZ001 for the Conventions' naive datetimes). Line endings: LF.

## Revision history
- **Revision 1 (2026-11-03):** patched, not regenerated: every existing test block kept byte for byte; added BIT-R-25. Revision 1 re-run: `--runxfail`, reference plugin, explicit wrong order, 3 runs plus forced plans and time zones, ruff, coverage; tables above are from these runs.

## Notes for maintainers
- When BUG-1322, BUG-1323 are fixed, their strict cards XPASS and fail: remove the marker. The non-strict cards then pass every time; remove their marker too.
- "Nothing written" and the `count:` lines count committed rows of all workspaces too. A run beside something that commits to these tables could break them; nothing did here.
- The non-strict order cards force a sequential scan; they rest on physical row order today and can pass by accident (see Stability). Never loosen the strict SQL recorder card beside them.
