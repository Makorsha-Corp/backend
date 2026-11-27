# Execution notes — `app/dao/work_order_item.py`

> Cases: `tests/unit/dao/work_order_item.cases.md` (Revision 1, READY, 31 cases) · Tests: `tests/unit/dao/test_work_order_item.py` · Source commit: e48a092
> Result: **31 tests for 31 cases — 28 passed · 3 xfail (1 strict, 2 non-strict) · 0 discrepancies · 0 errors** — line and branch coverage 100% (13 statements, 2 branches, 0 missed). The non-strict cards may XPASS without turning the run red, so a default run reads `28 passed, 2 xfailed, 1 xpassed`.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_work_order_item.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file (not kept; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childx\`), so values are the card's own text; an unknown Given or Then line stopped it. The fixtures and helpers were written by hand from the Conventions. A separate audit script checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matches the card's Then count in order with a check under each, every quoted literal of the card present, the When call as written, marker and bug match the Expect line, no unused argument, no fixture used without being an argument, the autouse fixture lists every standing row, every snapshot before the When. 0 problems.

## How the tests are built
- **Nothing is patched or mocked** (Conventions, Externals: None).
- **Standing rows:** one fixture per Conventions row (`w1`, `w2`, `u1`, `f1`, `i1`, `i2`, `wt1`, `wo1`, `wo2`, `wod`), each depending on the row before, so they are flushed one at a time in Conventions order. The autouse `standing_rows` makes all of them exist in every test; a test lists only those it names.
- **WOD** carries `deleted_at T12`, `deleted_by U1.id` (Revision 1, R-4).
- **Builders:** `mk_line(**columns)` = "line"; `mk_many(count)` = the 101-line `add_all` Given of G-19.
- **`item` and `replaced_item` load by joins** (Spec gap 4), and `"work_orders" not in sql` holds.
- **Spec gaps checked:** `is_deleted`, `is_active` on the order, `created_by` are real columns.
- **Reading helpers (no expected values inside):** `ids`, and those the cards use of `snap` ("unchanged", every column by Core select, after `db.expire_all()`), `reread` ("re-read"), `stored_count` ("nothing written"), `seqscan`. `written` stays the card's name for the recorder's list.
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener on the session's connection, around the When only. `recorder.sql()` is the one SELECT naming the table, and fails loudly unless there is exactly one.
- **Given rows no line names again** are built without a variable. "It is a standing row" lines add no code. Row letters of the cards are lower case in the code.

## xfail location (`--runxfail`, reading the failing value)
Plugin: `chx_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childx\` (`-p chx_plug`; it records the test line and its `# Then N`; nothing in `app/`).

| Card | Strict | Card says | Fails on | Default runs xfailed | Actual |
|---|---|---|---|---|---|
| WOI-G-16 | no | Then 2 | Then 2 (explicit order below) | 3 of 3 | `assert [123049, 123048] == [123048, 123049]` |
| WOI-G-17 | no | Then 2 | Then 2 (explicit order below) | 0 of 3 | `assert [123051, 123050] == [123050, 123051]` |
| WOI-G-18 | yes | Then 2 | Then 2 | 3 of 3 | `assert 'ORDER BY' in 'SELECT ...'`: the query has no `ORDER BY` |

**Proof that the non-strict cards can fail on their Then line.** An explicit order is a legal result for a query that asks for none, and it depends on neither plan nor heap. The plugin rewrites the module's read at `before_cursor_execute`. The recorder keeps seeing the original text, so the strict cards stay on their own Then.

| Rewrite | Cards that fail under `--runxfail` | Marked run | `--runxfail` run |
|---|---|---|---|
| `invoice_items.line_number, invoice_items.id DESC` | WOI-G-16, WOI-G-17, WOI-G-18 | 28 passed, 3 xfailed | 3 failed, 28 passed |
| `work_order_items.quantity` | WOI-G-16, WOI-G-17, WOI-G-18 | 28 passed, 3 xfailed | 3 failed, 28 passed |

No pass card failed under any rewrite, so no pass card depends on the order the bug leaves open.

**Proof of the lines past the failure point, and of the alarm.** `CHX_MODE=fix` replaces the methods in-process with the intended query (nothing in `app/`). With `--runxfail`: **31 passed**, so every Then line past a failure point holds on a fixed method. With the markers on: `1 failed, 28 passed, 2 xpassed`, the strict cards going red as `XPASS(strict)`.

## Revision 1: the verifier's named variants fail the new cards
Rebuilt by me in `var_plug.py` (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childx\`), from the names and meanings in `work_order_item.verify.md`; none of the verifier's scripts was run. Each variant is swapped in memory on top of the reference (intended) methods, and the file runs with `--runxfail` on three plans (default, `enable_seqscan=off`, index and bitmap scans off). The reference alone: `31 passed`.

| Recipe | New cards | Variant | New cards that fail | Other cards that fail |
|---|---|---|---|---|
| R-1 | WOI-I-06 | `i_r1_ws_ge` | WOI-I-06 | — |
| R-1 | WOI-I-06 | `i_r1_id_ge` | WOI-I-06 | — |
| R-2 | WOI-I-07 | `i_ov_join` | WOI-I-07 | — |
| R-2 | WOI-I-07 | `i_ov_flag` | WOI-I-07 | — |
| R-3 | WOI-G-23, WOI-I-08 | `g_w_expire` | WOI-G-23 | — |
| R-3 | WOI-G-23, WOI-I-08 | `g_w_expire_post` | WOI-G-23 | — |
| R-3 | WOI-G-23, WOI-I-08 | `g_w_dirty_refresh` | WOI-G-23 | — |
| R-3 | WOI-G-23, WOI-I-08 | `g_w_dirty_flush` | WOI-G-23 | — |
| R-3 | WOI-G-23, WOI-I-08 | `g_w_dirty_expire` | WOI-G-23 | — |
| R-3 | WOI-G-23, WOI-I-08 | `i_w_expire` | WOI-I-08 | — |
| R-3 | WOI-G-23, WOI-I-08 | `i_w_expire_post` | WOI-I-08 | — |
| R-3 | WOI-G-23, WOI-I-08 | `i_w_dirty_refresh` | WOI-I-08 | — |
| R-3 | WOI-G-23, WOI-I-08 | `i_w_dirty_flush` | WOI-I-08 | — |
| R-3 | WOI-G-23, WOI-I-08 | `i_w_dirty_expire` | WOI-I-08 | — |

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Coverage gaps
None — 100% line and branch coverage of `app/dao/work_order_item.py` (13 statements, 2 branches, 0 missed), run with a private `COVERAGE_FILE`. The inherited `BaseDAO` methods live in `app/dao/base.py` and are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
| Run | Result | WOI-G-16 | WOI-G-17 |
|---|---|---|---|
| Default, run 1 | 28 passed, 2 xfailed, 1 xpassed | XFAIL | XPASS |
| Default, run 2 | 28 passed, 2 xfailed, 1 xpassed | XFAIL | XPASS |
| Default, run 3 | 28 passed, 2 xfailed, 1 xpassed | XFAIL | XPASS |
| `enable_seqscan=off` | 28 passed, 1 xfailed, 2 xpassed | XPASS | XPASS |
| `enable_seqscan=off`, hash join and nested loop off | 28 passed, 3 xfailed | XFAIL | XFAIL |
| `enable_hashjoin=off` | 28 passed, 1 xfailed, 2 xpassed | XPASS | XPASS |
| index, bitmap and index-only scans off | 28 passed, 1 xfailed, 2 xpassed | XPASS | XPASS |
| the line above, hash and merge join off | 28 passed, 2 xfailed, 1 xpassed | XFAIL | XPASS |
| database `TimeZone` `Asia/Dhaka` | 28 passed, 1 xfailed, 2 xpassed | XPASS | XPASS |
| database `TimeZone` `America/New_York` | 28 passed, 1 xfailed, 2 xpassed | XPASS | XPASS |
| Coverage run | 28 passed, 1 xfailed, 2 xpassed | XPASS | XPASS |

Revision 1 runs. Every pass card passed in every run above, and every strict card xfailed in every run above. What moves is only whether a non-strict card XPASSES: that follows the heap and the plan.

`PGOPTIONS` carried the forced plans and the time zones. **Clock:** no card here compares two real-clock stamps, so no test can tie on the Windows clock, and nothing needed repeating. `ruff check` on the file: all checks passed. Line endings: LF.

## Revision history
- **Revision 0** (2026-11-02): 27 tests for 27 cases — 24 passed · 3 xfail (1 strict, 2 non-strict) · 0 discrepancies · 0 errors. Run 5 times plus forced plans; prose findings went to the verifier and are closed by Revision 1.
- **Revision 1 of the cases** (2026-11-03): 1 — the spec did not change. Additive, from `work_order_item.verify.md` (case-missing Findings 1 … 4; recipes R-1 … R-4; prose Finding 5): R-1 → WOI-I-06; R-2 → WOI-I-07; R-3 → WOI-G-23, WOI-I-08; R-4 → Conventions: WOD gains `deleted_at T12`, `deleted_by U1.id`; WOI-G-20's Given line says so; Finding 5 → WOI-G-16's `Fails today on` parenthesis reworded per plan. New Then lines are numbered last, so no existing Then number moved. No ID retired. The file was patched, not regenerated: the diff against Revision 0 is the new tests, the new Then lines and the standing-row columns the revision names, and nothing else. Run 3 times plus forced plans, both time zones, coverage, `--runxfail`, explicit orders and the reference.

## Notes for maintainers
- When BUG-1272 is fixed with `.order_by(id)`, G-18 XPASSES and turns the run red: remove the three markers.
- "Nothing written" counts committed rows of all workspaces too. A run beside something that commits to this table could break it; nothing did here.
