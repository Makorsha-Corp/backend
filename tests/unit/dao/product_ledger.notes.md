# Execution notes — `app/dao/product_ledger.py`

> Cases: `tests/unit/dao/product_ledger.cases.md` (READY, Revision 1, 95 cases; spec APPROVED 2026-11-02) · Tests: `tests/unit/dao/test_product_ledger.py` · Source commit: e48a092
> Result: **95 tests for 95 cases — 86 passed · 9 xfail (6 strict, 3 non-strict) · 0 discrepancies · 0 errors** — branch coverage 97% (25 statements, 10 branches, 1 missed). In run 1 of the file alone 9 xfailed and 0 non-strict xpassed.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_product_ledger.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file written for this batch (not kept in the repo; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\prodx\gen.py`), so values are the card's own text; an unknown Given, When or Then line stopped it, and none did. Fixtures, builders and helpers were written from the Conventions. A separate audit script checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matching the card's Then count in order with a check under each, every quoted literal of the card present, the When call present, marker strictness and bug matching the Expect line, no unused argument, no fixture used without being an argument, LF line endings. 0 problems.

## How the tests are built
- **Nothing is patched or mocked** (Conventions, Externals: None). `performed_at` is set by hand on every Given row; PLG-INH-05 compares the stored value with the real `utcnow()` (see Stability).
- **Standing rows:** one fixture per Conventions row, each depending on the one listed before it (and on any row it names), so they are flushed one at a time in Conventions order and the ids rise in that order. The autouse `standing_rows` makes all of them exist in every test; a test lists only those it names.
- **Builders:** `new_<row>(...)` builds the Conventions row with its defaults (not added); `mk_<row>(...)` adds and flushes it. A card's columns are passed as keywords in card order. The `add_all` Givens build `new_<row>` objects in a list comprehension and flush once (`add_many`); `newest` / `in_order` lists are taken from that list.
- **Reading helpers (no expected values inside):** `ids`; `snap` ("unchanged": every column by a Core select of the table, after `db.expire_all()`); `without` ("unchanged ... except"); `reread` ("re-read": expire, then `db.get`); `stored_count` ("nothing written"); `count_rows` ("count:" lines, Core count with the stated filter); `seqscan` (the three `SET LOCAL` steps). Only those the cards use are in the file.
- **Statement recorder:** the `recorder` fixture listens on the session's connection (`before_cursor_execute`) from `recorder.start()` at the start of the When to the end of the test, as the Conventions say, and removes the listener at teardown. `sql` (the one SELECT `FROM <table>`, fails loudly unless there is exactly one), `order_part` and `selects` are read at the first `statement:` line or before the first reading helper, whichever comes first, so the helpers' own SELECTs never enter them; `written` is read at its line.
- **Errors:** `pytest.raises(...)` around `db.begin_nested()` around the When (no savepoint for `ValidationError`); `exc` is bound only when a later Then reads it. **Rolled back** cards: `sp = db.begin_nested()` before the When, `patch.object(db, "commit", wraps=db.commit)` as the spy, `sp.rollback()` directly before the first "after the savepoint rollback" check.
- **Given rows no line names again** are built without a variable. Row letters of the cards are lower case in the code.
- **Joined relationships:** checked `app/models/`: none of this module's models has a `lazy="joined"` relationship (the only joined relationship among the seven modules' models is `Product.item`), so the `"JOIN" not in sql` recorder cards hold as designed.

## xfail check (`--runxfail`, failing value read)
Every xfail card was run with `--runxfail`; the failing line's `# Then N` was read against the card's "Fails today on", and the failing value against what the card says. Strict cards: all 6 fail at the Then the card names, with the value the card describes.

| Case | Strict | Fails on | Value read under `--runxfail` |
|---|---|---|---|
| PLG-GW-20 | strict | Then 1 | `assert [] == [94075] Right contains one more item: 94075 Use -v to get more diff` |
| PLG-GW-21 | strict | Then 1 | `assert [] == [94076] Right contains one more item: 94076 Use -v to get more diff` |
| PLG-GW-22 | strict | Then 1 | `assert [] == [94077] Right contains one more item: 94077 Use -v to get more diff` |
| PLG-GW-23 | strict | Then 1 | `assert [<app.models....026AAD28F740>] == [] Left contains one more item: <app.models.product_ledger.ProductLedger object at 0x0000026AAD28F740> ` |
| PLG-GW-42 | strict | Then 4 | `AssertionError: assert '.id' in ' product_ledger.performed_at DESC \n '` |
| PLG-GW-43 | non-strict | Then 2 | `assert [94116, 94117, 94115] == [94117, 94116, 94115] At index 0 diff: 94116 != 94117 Use -v to get more diff` |
| PLG-GW-44 | non-strict | Then 2 | `assert [94118, 94119, 94120, 94121] == [94120, 94119, 94118, 94121] At index 0 diff: 94118 != 94120 Use -v to get more diff` |
| PLG-GW-45 | non-strict | Then 2 | `assert [94123, 94123... 94126, 94122] == [94126, 94125... 94123, 94122] At index 0 diff: 94123 != 94126 Use -v to get more diff` |
| PLG-INH-05 | strict | Then 2 | `assert datetime.timedelta(seconds=21599, microseconds=987069) < datetime.timedelta(seconds=60) + where datetime.timedelta(seconds=21599, microsecond` |

## Explicit wrong order (non-strict proof)
A scratch plugin (`prodx\wrong.py`, `-p wrong`) rewrites the module's list SELECT with an explicit wrong `ORDER BY` (unordered lists: `<table>.id DESC` or `ASC`; dated lists: the same date order with the tie broken the wrong way), and the file runs with `--runxfail`.

| Rewrite | Non-strict cards that fail | Pass cards that fail |
|---|---|---|
| `id DESC` (dated lists: date order kept, tie `id ASC`) | 3 of 3 | 0 |
| `id ASC` (dated lists: tie `id DESC`, the intended order) | 0 of 3 | 0 |

Every non-strict card fails under the first rewrite, each at the Then its card names (checked: 54 of 54 across the batch). Not caught: [].

**Lines past the failure point (reference plugin).** `prodx\ref.py` (`-p ref`) replaces the methods in-process with the intended behaviour of each BUG the cards cite (orders, hide rules, trimmed compare, the formula-code index inside the test's transaction, schema trimming, UTC clocks, numeric suffix); nothing in `app/` changes. With `--runxfail`: **95 passed**, so every check after each xfail's failure point holds once the bug is fixed, and no pass card breaks under the fix.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 65 | dead | the `get_by_id_and_workspace` override: Not specified, dead code to be removed (P4); the inherited method stays. |

Branch coverage 97% of `app/dao/product_ledger.py` (25 statements, 10 branches, 1 missed), run with a private `COVERAGE_FILE`. Everything else is covered; inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
| Run | Passed | xfailed | xpassed (non-strict) | Not as designed |
|---|---|---|---|---|
| Default, run 1 (file alone) | 86 | 9 | 0 | 0 |
| Default, run 2 (file alone) | 86 | 9 | 0 | 0 |
| Default, run 3 (file alone) | 86 | 9 | 0 | 0 |
| `enable_seqscan=off` | 86 | 9 | 0 | 0 |
| `enable_seqscan=off`, hash join and nested loop off | 86 | 9 | 0 | 0 |
| `enable_hashjoin=off` | 86 | 9 | 0 | 0 |
| index, bitmap and index-only scans off | 86 | 9 | 0 | 0 |
| the line above, hash and merge join off | 86 | 9 | 0 | 0 |
| database `TimeZone` `Asia/Dhaka` | 86 | 9 | 0 | 0 |
| database `TimeZone` `America/New_York` | 86 | 9 | 0 | 0 |
| `--runxfail` with the reference plugin | 95 of 95 | — | — | 0 |

Every pass card passed and every strict xfail xfailed in every run above. `PGOPTIONS` carried the forced plans and the time zones.
No non-strict card passed by accident in any run.

**Clock:** PLG-INH-05 is the one card that compares two real-clock stamps (`abs(performed_at - utcnow()) < timedelta(minutes=1)`). Run as 3000 distinct parametrized copies with `--runxfail`: 3000 failed, each on Then 2 with the stamp six hours off under Dhaka (never near the one-minute bound); the same 3000 copies with the reference plugin: 3000 passed. (A first attempt that re-ran one test item 3000 times was discarded: re-running one item breaks fixture caching, so it proved nothing.)

`ruff check` on the file: all checks passed (the header `noqa` covers SIM117 for the Conventions' nested `with` and DTZ001 for the Conventions' naive datetimes). Line endings: LF.

## Revision history
- **Revision 1 (2026-11-03):** patched, not regenerated: every existing test block kept byte for byte; added PLG-GW-65, GW-66, EX-19. Revision 1 re-run: `--runxfail`, reference plugin, explicit wrong order, 3 runs plus forced plans and time zones, ruff, coverage; tables above are from these runs.

## Notes for maintainers
- When BUG-640, BUG-992, BUG-1337 are fixed, their strict cards XPASS and fail: remove the marker. The non-strict cards then pass every time; remove their marker too.
- "Nothing written" and the `count:` lines count committed rows of all workspaces too. A run beside something that commits to these tables could break them; nothing did here.
- PLG-GW-22 and PLG-GW-23 (one aware bound alone, the two the designer flagged) fail as designed under Dhaka: `[]` instead of the row, and the row instead of `[]`.
