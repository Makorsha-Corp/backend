# Execution notes — `app/dao/production_batch_stage_log.py`

> Cases: `tests/unit/dao/production_batch_stage_log.cases.md` (Revision 1, READY, 23 cases) · Tests: `tests/unit/dao/test_production_batch_stage_log.py` · Source commit: e48a092
> Result: **23 tests for 23 cases — 23 passed · 0 xfail (0 strict, 0 non-strict) · 0 discrepancies · 0 errors** — line and branch coverage 100% (10 statements, 0 branches, 0 missed).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_production_batch_stage_log.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file (not kept; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childx\`), so values are the card's own text; an unknown Given or Then line stopped it. The fixtures and helpers were written by hand from the Conventions. A separate audit script checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matches the card's Then count in order with a check under each, every quoted literal of the card present, the When call as written, marker and bug match the Expect line, no unused argument, no fixture used without being an argument, the autouse fixture lists every standing row, every snapshot before the When. 0 problems.

## How the tests are built
- **Nothing is patched or mocked** (Conventions, Externals: None).
- **Standing rows:** one fixture per Conventions row (`w1`, `w2`, `f1`, `pl1`, `pf1`, `b1`, `b2`), each depending on the row before, so they are flushed one at a time in Conventions order. The autouse `standing_rows` makes all of them exist in every test; a test lists only those it names.
- **Builders:** `mk_log(stage_order=, **columns)` = "log"; `mk_many(count)` = the 101-log Given of G-13, returns `in_order`.
- **Spec gaps checked:** `app.models.production_batch_stage_log` is the real path; `status="draft"` is accepted on a batch.
- **`FS1` of G-14** is built with `_add`, as "added and flushed" says.
- **Reading helpers (no expected values inside):** `ids`, and those the cards use of `snap` ("unchanged", every column by Core select, after `db.expire_all()`), `reread` ("re-read"), `stored_count` ("nothing written"), `seqscan`. `written` stays the card's name for the recorder's list.
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener on the session's connection, around the When only. `recorder.sql()` is the one SELECT naming the table, and fails loudly unless there is exactly one.
- **Given rows no line names again** are built without a variable. "It is a standing row" lines add no code. Row letters of the cards are lower case in the code.

## Explicit wrong order
No xfail here, so the same plugin served as a check of the pass cards.

| Rewrite | Cards that fail under `--runxfail` | Marked run | `--runxfail` run |
|---|---|---|---|
| `production_batch_stage_logs.stage_order, production_batch_stage_logs.id DESC` | PBL-G-10, PBL-G-11 | 2 failed, 21 passed | 2 failed, 21 passed |

**Proof of the lines past the failure point, and of the alarm.** `CHX_MODE=fix` replaces the methods in-process with the intended query (nothing in `app/`). No card here depends on it: `23 passed`.

## Revision 1: the verifier's named variants fail the new cards
Rebuilt by me in `var_plug.py` (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childx\`), from the names and meanings in `production_batch_stage_log.verify.md`; none of the verifier's scripts was run. Each variant is swapped in memory on top of the reference (intended) methods, and the file runs with `--runxfail` on three plans (default, `enable_seqscan=off`, index and bitmap scans off). The reference alone: `23 passed`.

| Recipe | New cards | Variant | New cards that fail | Other cards that fail |
|---|---|---|---|---|
| R-1 | PBL-I-05 | `i_r1_ws_ge` | PBL-I-05 | — |
| R-1 | PBL-I-05 | `i_r1_id_ge` | PBL-I-05 | — |
| R-2 | PBL-G-15, PBL-I-04 | `g_ov_join` | PBL-G-15 | — |
| R-2 | PBL-G-15, PBL-I-04 | `g_ov_draft` | PBL-G-15 | — |
| R-2 | PBL-G-15, PBL-I-04 | `i_ov_join` | PBL-I-04 | — |
| R-3 | PBL-G-16, PBL-I-06 | `g_w_expire` | PBL-G-16 | — |
| R-3 | PBL-G-16, PBL-I-06 | `g_w_expire_post` | PBL-G-16 | — |
| R-3 | PBL-G-16, PBL-I-06 | `g_w_dirty_refresh` | PBL-G-16 | — |
| R-3 | PBL-G-16, PBL-I-06 | `g_w_dirty_flush` | PBL-G-16 | — |
| R-3 | PBL-G-16, PBL-I-06 | `g_w_dirty_expire` | PBL-G-16 | — |
| R-3 | PBL-G-16, PBL-I-06 | `i_w_expire` | PBL-I-06 | — |
| R-3 | PBL-G-16, PBL-I-06 | `i_w_expire_post` | PBL-I-06 | — |
| R-3 | PBL-G-16, PBL-I-06 | `i_w_dirty_refresh` | PBL-I-06 | — |
| R-3 | PBL-G-16, PBL-I-06 | `i_w_dirty_flush` | PBL-I-06 | — |
| R-3 | PBL-G-16, PBL-I-06 | `i_w_dirty_expire` | PBL-I-06 | — |
| R-4 | PBL-G-17 | `no_set_null` | PBL-G-17 | — |

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Coverage gaps
None — 100% line and branch coverage of `app/dao/production_batch_stage_log.py` (10 statements, 0 branches, 0 missed), run with a private `COVERAGE_FILE`. The inherited `BaseDAO` methods live in `app/dao/base.py` and are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
| Run | Result |
|---|---|
| Default, run 1 | 23 passed |
| Default, run 2 | 23 passed |
| Default, run 3 | 23 passed |
| `enable_seqscan=off` | 23 passed |
| `enable_seqscan=off`, hash join and nested loop off | 23 passed |
| `enable_hashjoin=off` | 23 passed |
| index, bitmap and index-only scans off | 23 passed |
| the line above, hash and merge join off | 23 passed |
| database `TimeZone` `Asia/Dhaka` | 23 passed |
| database `TimeZone` `America/New_York` | 23 passed |
| Coverage run | 23 passed |

Revision 1 runs. Every pass card passed in every run above, with no xfail in the file. 

`PGOPTIONS` carried the forced plans and the time zones. **Clock:** no card here compares two real-clock stamps, so no test can tie on the Windows clock, and nothing needed repeating. `ruff check` on the file: all checks passed. Line endings: LF.

## Revision history
- **Revision 0** (2026-11-02): 19 tests for 19 cases — 19 passed · 0 xfail (0 strict, 0 non-strict) · 0 discrepancies · 0 errors. Run 5 times plus forced plans; prose findings went to the verifier and are closed by Revision 1.
- **Revision 1 of the cases** (2026-11-03): 1 — the spec did not change. Additive, from `production_batch_stage_log.verify.md` (case-missing Findings 1 … 4; recipes R-1 … R-4): R-1 → PBL-I-05; R-2 → one Then line each on PBL-G-15 and PBL-I-04; R-3 → PBL-G-16, PBL-I-06; R-4 → PBL-G-17; the Reviewer summary line on `SET NULL` corrected (Finding 4). New Then lines are numbered last, so no existing Then number moved. No ID retired. The file was patched, not regenerated: the diff against Revision 0 is the new tests, the new Then lines and the standing-row columns the revision names, and nothing else. Run 3 times plus forced plans, both time zones, coverage, `--runxfail`, explicit orders and the reference.

## Notes for maintainers
- No xfail here. The tie order is pinned by G-10, G-11 and the recorder in G-12.
- "Nothing written" counts committed rows of all workspaces too. A run beside something that commits to this table could break it; nothing did here.
