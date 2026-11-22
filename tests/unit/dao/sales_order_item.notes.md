# Execution notes — `app/dao/sales_order_item.py`

> Cases: `tests/unit/dao/sales_order_item.cases.md` (Revision 1, READY, 19 cases) · Tests: `tests/unit/dao/test_sales_order_item.py` · Source commit: e48a092
> Result: **19 tests for 19 cases — 15 passed · 4 xfail (1 strict, 3 non-strict) · 0 discrepancies · 0 errors** — line and branch coverage 90% (10 statements, 0 branches, 1 missed). The non-strict cards may XPASS without turning the run red, so a default run reads `15 passed, 1 xfailed, 3 xpassed` or `15 passed, 4 xfailed`.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_sales_order_item.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file (not kept; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childx\`), so values are the card's own text; an unknown Given or Then line stopped it. The fixtures and helpers were written by hand from the Conventions. A separate audit script checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matches the card's Then count in order with a check under each, every quoted literal of the card present, the When call as written, marker and bug match the Expect line, no unused argument, no fixture used without being an argument, the autouse fixture lists every standing row, every snapshot before the When. 0 problems.

## How the tests are built
- **Nothing is patched or mocked** (Conventions, Externals: None).
- **Standing rows:** one fixture per Conventions row (`w1`, `w2`, `u1`, `ac1`, `f1`, `s1`, `so1`, `so2`, `ir`), each depending on the row before, so they are flushed one at a time in Conventions order. The autouse `standing_rows` makes all of them exist in every test; a test lists only those it names.
- **Builders:** `mk_line(**columns)` = "line"; `mk_many(count)` = the 103-line `add_all` Given of G-15.
- **`item` loads by a join** (Spec gap 2), so `sql` holds a `LEFT OUTER JOIN items`, and `"sales_orders" not in sql` holds.
- **Reading helpers (no expected values inside):** `ids`, and those the cards use of `snap` ("unchanged", every column by Core select, after `db.expire_all()`), `reread` ("re-read"), `stored_count` ("nothing written"), `seqscan`. `written` stays the card's name for the recorder's list.
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener on the session's connection, around the When only. `recorder.sql()` is the one SELECT naming the table, and fails loudly unless there is exactly one.
- **Given rows no line names again** are built without a variable. "It is a standing row" lines add no code. Row letters of the cards are lower case in the code.

## xfail location (`--runxfail`, reading the failing value)
Plugin: `chx_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childx\` (`-p chx_plug`; it records the test line and its `# Then N`; nothing in `app/`).

| Card | Strict | Card says | Fails on | Default runs xfailed | Actual |
|---|---|---|---|---|---|
| SOI-G-12 | no | Then 2 | Then 2 | 2 of 3 | `assert [177779, 177780, 177778] == [177778, 177779, 177780]` |
| SOI-G-13 | no | Then 2 | Then 2 (index scans off) | 2 of 3 | `assert [177912, 177911, 177910] == [177910, 177911, 177912]` |
| SOI-G-14 | yes | Then 2 | Then 2 | 3 of 3 | `assert 'ORDER BY' in 'SELECT ...'`: the query has no `ORDER BY` |
| SOI-G-19 | no | Then 2 | Then 2 (index scans off) | 2 of 3 | `assert [178021, 178020] == [178020, 178021]` |

**Proof that the non-strict cards can fail on their Then line.** An explicit order is a legal result for a query that asks for none, and it depends on neither plan nor heap. The plugin rewrites the module's read at `before_cursor_execute`. The recorder keeps seeing the original text, so the strict cards stay on their own Then.

| Rewrite | Cards that fail under `--runxfail` | Marked run | `--runxfail` run |
|---|---|---|---|
| `invoice_items.line_number, invoice_items.id DESC` | SOI-G-12, SOI-G-13, SOI-G-14, SOI-G-19 | 15 passed, 4 xfailed | 4 failed, 15 passed |
| `invoice_items.line_number, invoice_items.description` | SOI-G-12, SOI-G-13, SOI-G-14 | 15 passed, 3 xfailed, 1 xpassed | 3 failed, 16 passed |

No pass card failed under any rewrite, so no pass card depends on the order the bug leaves open.

**Proof of the lines past the failure point, and of the alarm.** `CHX_MODE=fix` replaces the methods in-process with the intended query (nothing in `app/`). With `--runxfail`: **19 passed**, so every Then line past a failure point holds on a fixed method. With the markers on: `1 failed, 15 passed, 3 xpassed`, the strict cards going red as `XPASS(strict)`.

## Revision 1: the verifier's named variants fail the new cards
Rebuilt by me in `var_plug.py` (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childx\`), from the names and meanings in `sales_order_item.verify.md`; none of the verifier's scripts was run. Each variant is swapped in memory on top of the reference (intended) methods, and the file runs with `--runxfail` on three plans (default, `enable_seqscan=off`, index and bitmap scans off). The reference alone: `19 passed`.

| Recipe | New cards | Variant | New cards that fail | Other cards that fail |
|---|---|---|---|---|
| R-1 | SOI-G-18 | `g_w_expire` | SOI-G-18 | — |
| R-1 | SOI-G-18 | `g_w_expire_post` | SOI-G-18 | — |
| R-1 | SOI-G-18 | `g_w_dirty_refresh` | SOI-G-18 | — |
| R-1 | SOI-G-18 | `g_w_dirty_flush` | SOI-G-18 | — |
| R-1 | SOI-G-18 | `g_w_dirty_expire` | SOI-G-18 | — |
| R-2 | SOI-G-19 | `g_r3_price` | SOI-G-19 | — |

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 40 | `dead` | The body of `get_by_item`: dead code, listed under Not specified (spec Q1) and in `docs/testing/dead-code-removal-checklist.md`. |

Everything else is covered (90%; 10 statements, 0 branches, 1 missed). Private `COVERAGE_FILE`.

## Factories added
None.

## Stability
| Run | Result | SOI-G-12 | SOI-G-13 | SOI-G-19 |
|---|---|---|---|---|
| Default, run 1 | 15 passed, 4 xfailed | XFAIL | XFAIL | XFAIL |
| Default, run 2 | 15 passed, 4 xfailed | XFAIL | XFAIL | XFAIL |
| Default, run 3 | 15 passed, 1 xfailed, 3 xpassed | XPASS | XPASS | XPASS |
| `enable_seqscan=off` | 15 passed, 1 xfailed, 3 xpassed | XPASS | XPASS | XPASS |
| `enable_seqscan=off`, hash join and nested loop off | 15 passed, 1 xfailed, 3 xpassed | XPASS | XPASS | XPASS |
| `enable_hashjoin=off` | 15 passed, 1 xfailed, 3 xpassed | XPASS | XPASS | XPASS |
| index, bitmap and index-only scans off | 15 passed, 4 xfailed | XFAIL | XFAIL | XFAIL |
| the line above, hash and merge join off | 15 passed, 2 xfailed, 2 xpassed | XFAIL | XPASS | XPASS |
| database `TimeZone` `Asia/Dhaka` | 15 passed, 1 xfailed, 3 xpassed | XPASS | XPASS | XPASS |
| database `TimeZone` `America/New_York` | 15 passed, 4 xfailed | XFAIL | XFAIL | XFAIL |
| Coverage run | 15 passed, 2 xfailed, 2 xpassed | XFAIL | XPASS | XPASS |

Revision 1 runs. Every pass card passed in every run above, and every strict card xfailed in every run above. What moves is only whether a non-strict card XPASSES: that follows the heap and the plan.

`PGOPTIONS` carried the forced plans and the time zones. **Clock:** no card here compares two real-clock stamps, so no test can tie on the Windows clock, and nothing needed repeating. `ruff check` on the file: all checks passed. Line endings: LF.

## Revision history
- **Revision 0** (2026-11-02): 17 tests for 17 cases — 14 passed · 3 xfail (1 strict, 2 non-strict) · 0 discrepancies · 0 errors. Run 5 times plus forced plans; prose findings went to the verifier and are closed by Revision 1.
- **Revision 1 of the cases** (2026-11-03): 1 — the spec did not change. Additive, from `sales_order_item.verify.md` (case-missing Findings 1, 2; recipes R-1, R-2; prose Finding 3): R-1 → SOI-G-18; R-2 → SOI-G-19; Finding 3 → SOI-G-13's `Fails today on` parenthesis reworded per plan. New Then lines are numbered last, so no existing Then number moved. No ID retired. The file was patched, not regenerated: the diff against Revision 0 is the new tests, the new Then lines and the standing-row columns the revision names, and nothing else. Run 3 times plus forced plans, both time zones, coverage, `--runxfail`, explicit orders and the reference.

## Notes for maintainers
- When BUG-1270 is fixed with `.order_by(id)`, G-14 XPASSES and turns the run red: remove the three markers.
- When `get_by_item` is removed, coverage reaches 100% with no change here.
- "Nothing written" counts committed rows of all workspaces too. A run beside something that commits to this table could break it; nothing did here.
