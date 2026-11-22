# Execution notes — `app/dao/production_formula.py`

> Cases: `tests/unit/dao/production_formula.cases.md` (READY, Revision 1, 107 cases; spec APPROVED 2026-11-02) · Tests: `tests/unit/dao/test_production_formula.py` · Source commit: e48a092
> Result: **107 tests for 107 cases — 77 passed · 30 xfail (19 strict, 11 non-strict) · 0 discrepancies · 0 errors** — branch coverage 100% (16 statements, 0 branches, 0 missed). In run 1 of the file alone 27 xfailed and 3 non-strict xpassed.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_production_formula.py -q -p no:cacheprovider`

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
Every xfail card was run with `--runxfail`; the failing line's `# Then N` was read against the card's "Fails today on", and the failing value against what the card says. Strict cards: all 19 fail at the Then the card names, with the value the card describes.

| Case | Strict | Fails on | Value read under `--runxfail` |
|---|---|---|---|
| PFM-GW-05 | strict | Then 2 | `AssertionError: assert 'ORDER BY' in 'SELECT production_formulas.id AS production_formulas_id, production_formulas.workspace_id AS production_formulas` |
| PFM-GW-06 | non-strict | Then 2 | `assert [552739, 552740, 552738] == [552738, 552739, 552740] At index 0 diff: 552739 != 552738 Use -v to get more diff` |
| PFM-GW-07 | non-strict | Then 2 | `assert [552742, 5527...52745, 552741] == [552741, 5527...52744, 552745] At index 0 diff: 552742 != 552741 Use -v to get more diff` |
| PFM-GC-11 | strict | Then 1 | `assert None is not None` |
| PFM-GC-12 | strict | Then 1 | `assert None is not None` |
| PFM-GC-13 | strict | Then 1 | `assert None is not None` |
| PFM-GC-14 | strict | Then 1 | `assert None is not None` |
| PFM-GA-08 | strict | Then 2 | `AssertionError: assert 'ORDER BY' in 'SELECT production_formulas.id AS production_formulas_id, production_formulas.workspace_id AS production_formulas` |
| PFM-GA-09 | non-strict | Then 2 | `assert [553008, 553009, 553010] == [553009, 553010, 553008] At index 0 diff: 553008 != 553009 Use -v to get more diff` |
| PFM-GA-10 | non-strict | — | passed today by physical order (non-strict); failed under the explicit wrong order |
| PFM-GA-11 | non-strict | — | passed today by physical order (non-strict); failed under the explicit wrong order |
| PFM-GA-12 | non-strict | Then 2 | `assert [553016, 553017, 553015] == [553015, 553016, 553017] At index 0 diff: 553016 != 553015 Use -v to get more diff` |
| PFM-GA-13 | non-strict | Then 2 | `assert [553019] == [553020] At index 0 diff: 553019 != 553020 Use -v to get more diff` |
| PFM-GA-14 | non-strict | Then 2 | `assert [553021, 5530...53025, 553022] == [553022, 5530...53025, 553024] At index 0 diff: 553021 != 553022 Use -v to get more diff` |
| PFM-GD-07 | strict | Then 2 | `AssertionError: assert 'ORDER BY' in 'SELECT production_formulas.id AS production_formulas_id, production_formulas.workspace_id AS production_formulas` |
| PFM-GD-08 | non-strict | Then 2 | `assert [553360, 553361, 553362] == [553361, 553362, 553360] At index 0 diff: 553360 != 553361 Use -v to get more diff` |
| PFM-GD-09 | non-strict | — | passed today by physical order (non-strict); failed under the explicit wrong order |
| PFM-GD-10 | non-strict | Then 2 | `assert [553366, 553367, 553365] == [553365, 553366, 553367] At index 0 diff: 553366 != 553365 Use -v to get more diff` |
| PFM-INH-03 | strict | Then 1 | `Failed: DID NOT RAISE IntegrityError` |
| PFM-INH-04 | strict | Then 1 | `Failed: DID NOT RAISE IntegrityError` |
| PFM-INH-05 | strict | Then 1 | `Failed: DID NOT RAISE IntegrityError` |
| PFM-INH-06 | strict | Then 1 | `Failed: DID NOT RAISE IntegrityError` |
| PFM-INH-09 | strict | Then 1 | `Failed: DID NOT RAISE IntegrityError` |
| PFM-INH-10 | strict | Then 1 | `Failed: DID NOT RAISE IntegrityError` |
| PFM-SCH-01 | strict | Then 1 | `Failed: DID NOT RAISE ValidationError` |
| PFM-SCH-02 | strict | Then 1 | `Failed: DID NOT RAISE ValidationError` |
| PFM-SCH-03 | strict | Then 1 | `Failed: DID NOT RAISE ValidationError` |
| PFM-SCH-04 | strict | Then 1 | `AssertionError: assert ' RE-1 ' == 'RE-1' - RE-1 + RE-1 ? + +` |
| PFM-SCH-05 | strict | Then 1 | `AssertionError: assert ' Yarn ' == 'Yarn' - Yarn + Yarn ? + +` |
| PFM-SCH-06 | strict | Then 1 | `AssertionError: assert ' Yarn ' == 'Yarn' - Yarn + Yarn ? + +` |

## Explicit wrong order (non-strict proof)
A scratch plugin (`prodx\wrong.py`, `-p wrong`) rewrites the module's list SELECT with an explicit wrong `ORDER BY` (unordered lists: `<table>.id DESC` or `ASC`; dated lists: the same date order with the tie broken the wrong way), and the file runs with `--runxfail`.

| Rewrite | Non-strict cards that fail | Pass cards that fail |
|---|---|---|
| `id DESC` (dated lists: date order kept, tie `id ASC`) | 11 of 11 | 2 (PFM-GW-21, PFM-GA-26 in their Revision 1 form; 0 after Revision 1b) |
| `id ASC` (dated lists: tie `id DESC`, the intended order) | 4 of 11 | 0 |

Every non-strict card fails under the first rewrite, each at the Then its card names (checked: 54 of 54 across the batch). Not caught: [].

**Lines past the failure point (reference plugin).** `prodx\ref.py` (`-p ref`) replaces the methods in-process with the intended behaviour of each BUG the cards cite (orders, hide rules, trimmed compare, the formula-code index inside the test's transaction, schema trimming, UTC clocks, numeric suffix); nothing in `app/` changes. With `--runxfail`: **107 passed**, so every check after each xfail's failure point holds once the bug is fixed, and no pass card breaks under the fix.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Coverage gaps
None — 100% line and branch coverage of `app/dao/production_formula.py` (16 statements, 0 branches, 0 missed), run with a private `COVERAGE_FILE`. Inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
| Run | Passed | xfailed | xpassed (non-strict) | Not as designed |
|---|---|---|---|---|
| Default, run 1 (file alone) | 77 | 27 | 3 | 0 |
| Default, run 2 (file alone) | 77 | 27 | 3 | 0 |
| Default, run 3 (file alone) | 77 | 27 | 3 | 0 |
| `enable_seqscan=off` | 77 | 27 | 3 | 0 |
| `enable_seqscan=off`, hash join and nested loop off | 77 | 23 | 7 | 0 |
| `enable_hashjoin=off` | 77 | 27 | 3 | 0 |
| index, bitmap and index-only scans off | 77 | 27 | 3 | 0 |
| the line above, hash and merge join off | 77 | 27 | 3 | 0 |
| database `TimeZone` `Asia/Dhaka` | 77 | 27 | 3 | 0 |
| database `TimeZone` `America/New_York` | 77 | 27 | 3 | 0 |
| `--runxfail` with the reference plugin | 107 of 107 | — | — | 0 |

Every pass card passed and every strict xfail xfailed in every run above. `PGOPTIONS` carried the forced plans and the time zones.
Non-strict cards that passed by physical order in some runs: PFM-GA-10 (10 of 10), PFM-GA-11 (10 of 10), PFM-GD-09 (10 of 10), PFM-GW-06 (1 of 10), PFM-GW-07 (1 of 10), PFM-GA-12 (1 of 10), PFM-GD-10 (1 of 10). All of them fail under the explicit wrong order above.

**Clock:** no card here compares two real-clock stamps, so nothing needed repeating.

`ruff check` on the file: all checks passed (the header `noqa` covers SIM117 for the Conventions' nested `with` and DTZ001 for the Conventions' naive datetimes). Line endings: LF.

## Chosen-row cards (Revision 1b)
Revision 1 versions of PFM-GW-21, PFM-GA-26 named one row (`skip=1, limit=1`) on a query with no `ORDER BY` and could fail for order alone (explicit `id DESC`; or a sequential scan after an update moved the first W1 row to the end of the heap). Revision 1b checks `limit=2`: two rows, A and B as a set, Z absent. Re-checked: they pass under both explicit wrong orders, the default plan, `enable_seqscan=off` with and without hash join and nested loop, and forced physical orders (each of Z, A, B moved to the end of the heap). A broken variant that applies the workspace filter after the `LIMIT` fails every one on Then 1 (`1 == 2`). Scratch: `prodx\phys2_test.py`.

## Revision history
- **Revision 1 (2026-11-03):** patched, not regenerated: every existing test block kept byte for byte; added PFM-GW-21, GC-18, GA-26, GD-13. The dropped `newest` lines of GW-08, GA-15 were never written, so those tests did not change. Revision 1b: PFM-GW-21, PFM-GA-26 patched to `limit=2`, two rows, A and B as a set, Z absent (see Chosen-row cards); full file re-run, ruff, audit. Revision 1 re-run: `--runxfail`, reference plugin, explicit wrong order, 3 runs plus forced plans and time zones, ruff, coverage; tables above are from these runs.

## Notes for maintainers
- When BUG-100, BUG-1314, BUG-1315, BUG-1316, BUG-1317 are fixed, their strict cards XPASS and fail: remove the marker. The non-strict cards then pass every time; remove their marker too.
- "Nothing written" and the `count:` lines count committed rows of all workspaces too. A run beside something that commits to these tables could break them; nothing did here.
- The non-strict order cards force a sequential scan; they rest on physical row order today and can pass by accident (see Stability). Never loosen the strict SQL recorder card beside them.
