# Execution notes — `app/dao/invoice_item.py`

> Cases: `tests/unit/dao/invoice_item.cases.md` (Revision 1, READY, 43 cases) · Tests: `tests/unit/dao/test_invoice_item.py` · Source commit: e48a092
> Result: **43 tests for 43 cases — 39 passed · 4 xfail (2 strict, 2 non-strict) · 0 discrepancies · 0 errors** — line and branch coverage 100% (13 statements, 0 branches, 0 missed). The non-strict cards may XPASS without turning the run red, so a default run reads `39 passed, 2 xfailed, 2 xpassed` or `39 passed, 3 xfailed, 1 xpassed`.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_invoice_item.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file (not kept; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childx\`), so values are the card's own text; an unknown Given or Then line stopped it. The fixtures and helpers were written by hand from the Conventions. A separate audit script checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matches the card's Then count in order with a check under each, every quoted literal of the card present, the When call as written, marker and bug match the Expect line, no unused argument, no fixture used without being an argument, the autouse fixture lists every standing row, every snapshot before the When. 0 problems.

## How the tests are built
- **Nothing is patched.** The one spy is the Conventions' `rolled back`, below.
- **Standing rows:** one fixture per Conventions row (`w1`, `w2`, `ac1`, `ac9`, `in1`, `in2`, `inc`, `in9`), each depending on the row before, so they are flushed one at a time in Conventions order. The autouse `standing_rows` makes all of them exist in every test; a test lists only those it names.
- **II-DA-14, II-DA-15** (BUG-1283): the pending lines are added with `db.add(...)` and not flushed, as the cards write them; the count is a Core `SELECT count(*)`.
- **Builders:** `mk_line(line_number=, **columns)` = "line"; `mk_many(count)` = the 101-line `add_all` Given of GI-17, returns `in_order`.
- **`rolled back` (DA-08):** `sp = db.begin_nested()` directly before the call, `patch.object(db, "commit", wraps=db.commit)` around it; Then 3 starts with `sp.rollback()`. It is the one spy, and it is the Conventions' own.
- **`count:` lines:** `row_count(db, invoice_id=...)`, a Core `SELECT count(*)`, so a deleted line is never re-read through its object.
- **Spec gaps checked:** `AccountInvoice` takes no `created_by` (the column is nullable). `line_number` is always given.
- **Reading helpers (no expected values inside):** `ids`, and those the cards use of `snap` ("unchanged", every column by Core select, after `db.expire_all()`), `reread` ("re-read"), `stored_count` ("nothing written"), `seqscan`. `written` stays the card's name for the recorder's list.
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener on the session's connection, around the When only. `recorder.sql()` is the one SELECT naming the table, and fails loudly unless there is exactly one.
- **Given rows no line names again** are built without a variable. "It is a standing row" lines add no code. Row letters of the cards are lower case in the code.

## xfail location (`--runxfail`, reading the failing value)
Plugin: `chx_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childx\` (`-p chx_plug`; it records the test line and its `# Then N`; nothing in `app/`).

| Card | Strict | Card says | Fails on | Default runs xfailed | Actual |
|---|---|---|---|---|---|
| II-GI-14 | no | Then 2 | Then 2 | 2 of 3 | `assert [90271, 90270] == [90270, 90271]` |
| II-GI-15 | no | Then 2 | Then 2 (explicit order below) | 0 of 3 | `assert [90777, 90776] == [90776, 90777]` |
| II-GI-16 | yes | Then 4 | Then 4 | 3 of 3 | `assert '.id' in ' invoice_items.line_number'` |
| II-DA-14 | yes | Then 2 | Then 2 | 3 of 3 | `assert 1 == 0` |

**Proof that the non-strict cards can fail on their Then line.** An explicit order is a legal result for a query that asks for none, and it depends on neither plan nor heap. The plugin rewrites the module's read at `before_cursor_execute`. The recorder keeps seeing the original text, so the strict cards stay on their own Then.

| Rewrite | Cards that fail under `--runxfail` | Marked run | `--runxfail` run |
|---|---|---|---|
| `invoice_items.line_number, invoice_items.id DESC` | II-DA-14, II-GI-14, II-GI-15, II-GI-16 | 39 passed, 4 xfailed | 4 failed, 39 passed |
| `invoice_items.line_number, invoice_items.description` | II-DA-14, II-GI-14, II-GI-15, II-GI-16 | 39 passed, 4 xfailed | 4 failed, 39 passed |
| `invoice_items.line_number, invoice_items.line_subtotal` | II-DA-14, II-GI-14, II-GI-15, II-GI-16 | 39 passed, 4 xfailed | 4 failed, 39 passed |

No pass card failed under any rewrite, so no pass card depends on the order the bug leaves open.

**Proof of the lines past the failure point, and of the alarm.** `CHX_MODE=fix` replaces the methods in-process with the intended query (nothing in `app/`). With `--runxfail`: **43 passed**, so every Then line past a failure point holds on a fixed method. With the markers on: `2 failed, 39 passed, 2 xpassed`, the strict cards going red as `XPASS(strict)`.

## Revision 1: the verifier's named variants fail the new cards
Rebuilt by me in `var_plug.py` (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childx\`), from the names and meanings in `invoice_item.verify.md`; none of the verifier's scripts was run. Each variant is swapped in memory on top of the reference (intended) methods, and the file runs with `--runxfail` on three plans (default, `enable_seqscan=off`, index and bitmap scans off). The reference alone: `43 passed`.

| Recipe | New cards | Variant | New cards that fail | Other cards that fail |
|---|---|---|---|---|
| R-1 | II-GW-05 | `gw_r1_ws_ge` | II-GW-05 | — |
| R-1 | II-GW-05 | `gw_r1_id_ge` | II-GW-05 | — |
| R-2 | II-GW-06 | `gw_ov_join` | II-GW-06 | — |
| R-2 | II-GW-06 | `gw_ov_draft` | II-GW-06 | — |
| R-2 | II-GW-06 | `gw_ov_draft_join` | II-GW-06 | — |
| R-3 | II-GI-21 | `gi_w_expire` | II-GI-21 | — |
| R-3 | II-GI-21 | `gi_w_expire_post` | II-GI-21 | — |
| R-3 | II-GI-21 | `gi_w_dirty_refresh` | II-GI-21 | — |
| R-3 | II-GI-21 | `gi_w_dirty_flush` | II-GI-21 | — |
| R-3 | II-GI-21 | `gi_w_dirty_expire` | II-GI-21 | — |
| R-4 | II-GW-07 | `gw_w_expire` | II-GW-07 | — |
| R-4 | II-GW-07 | `gw_w_expire_post` | II-GW-07 | — |
| R-4 | II-GW-07 | `gw_w_dirty_refresh` | II-GW-07 | — |
| R-4 | II-GW-07 | `gw_w_dirty_flush` | II-GW-07 | — |
| R-4 | II-GW-07 | `gw_w_dirty_expire` | II-GW-07 | — |

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Coverage gaps
None — 100% line and branch coverage of `app/dao/invoice_item.py` (13 statements, 0 branches, 0 missed), run with a private `COVERAGE_FILE`. The inherited `BaseDAO` methods live in `app/dao/base.py` and are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
| Run | Result | II-GI-14 | II-GI-15 |
|---|---|---|---|
| Default, run 1 | 39 passed, 3 xfailed, 1 xpassed | XFAIL | XPASS |
| Default, run 2 | 39 passed, 3 xfailed, 1 xpassed | XFAIL | XPASS |
| Default, run 3 | 39 passed, 2 xfailed, 2 xpassed | XPASS | XPASS |
| `enable_seqscan=off` | 39 passed, 3 xfailed, 1 xpassed | XFAIL | XPASS |
| `enable_seqscan=off`, hash join and nested loop off | 39 passed, 3 xfailed, 1 xpassed | XFAIL | XPASS |
| `enable_hashjoin=off` | 39 passed, 3 xfailed, 1 xpassed | XFAIL | XPASS |
| index, bitmap and index-only scans off | 39 passed, 3 xfailed, 1 xpassed | XFAIL | XPASS |
| the line above, hash and merge join off | 39 passed, 3 xfailed, 1 xpassed | XFAIL | XPASS |
| database `TimeZone` `Asia/Dhaka` | 39 passed, 3 xfailed, 1 xpassed | XFAIL | XPASS |
| database `TimeZone` `America/New_York` | 39 passed, 3 xfailed, 1 xpassed | XFAIL | XPASS |
| Coverage run | 39 passed, 2 xfailed, 2 xpassed | XPASS | XPASS |

Revision 1 runs. Every pass card passed in every run above, and every strict card xfailed in every run above. What moves is only whether a non-strict card XPASSES: that follows the heap and the plan.

`PGOPTIONS` carried the forced plans and the time zones. **Clock:** no card here compares two real-clock stamps, so no test can tie on the Windows clock, and nothing needed repeating. `ruff check` on the file: all checks passed. Line endings: LF.

## Revision history
- **Revision 0** (2026-11-02): 37 tests for 37 cases — 34 passed · 3 xfail (1 strict, 2 non-strict) · 0 discrepancies · 0 errors. Run 5 times plus forced plans; prose findings went to the verifier and are closed by Revision 1.
- **Revision 1 of the cases** (2026-11-03): 1 — the spec changed: its gap round of 2026-11-03 adds `delete_all_for_invoice` R7 [BUG-1283] (owner's answer to Spec gap 1). R7 → II-DA-14 (strict xfail), II-DA-15 (pass). Additive, from `invoice_item.verify.md` (case-missing Findings 1 … 3; recipes R-1 … R-4): R-1 → II-GW-05; R-2 → II-GW-06; R-3 → II-GI-21; R-4 → II-GW-07. New Then lines are numbered last, so no existing Then number moved. No ID retired. The file was patched, not regenerated: the diff against Revision 0 is the new tests, the new Then lines and the standing-row columns the revision names, and nothing else. Run 3 times plus forced plans, both time zones, coverage, `--runxfail`, explicit orders and the reference.

## Notes for maintainers
- When BUG-1283 is fixed (the pending rows written before the `DELETE`), II-DA-14 XPASSES and turns the run red: remove its marker. II-DA-15 holds the other half of that fix.
- When BUG-638 is fixed with `.order_by(line_number, id)` in this DAO, GI-16 XPASSES and turns the run red: remove the three markers.
- Never read a GI-15 XPASS as the bug being gone: it passed in every run without the plugin, with the bug present.
- II-DA-11 pins the stale-instance behavior R6 describes. A change to `synchronize_session` will fail it.
- "Nothing written" counts committed rows of all workspaces too. A run beside something that commits to this table could break it; nothing did here.
