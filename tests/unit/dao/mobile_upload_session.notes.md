# Execution notes — `app/dao/mobile_upload_session.py`

> Cases: `tests/unit/dao/mobile_upload_session.cases.md` (Revision 1, READY, 51 cases) · Tests: `tests/unit/dao/test_mobile_upload_session.py` · Source commit: e48a092
> Result: **51 tests for 51 cases — 45 passed · 6 xfail (6 strict, 0 non-strict) · 0 discrepancies · 0 errors** — line and branch coverage 100% (19 statements, 4 branches, 0 missed).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_mobile_upload_session.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file (not kept; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childx\`), so values are the card's own text; an unknown Given or Then line stopped it. The fixtures and helpers were written by hand from the Conventions. A separate audit script checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matches the card's Then count in order with a check under each, every quoted literal of the card present, the When call as written, marker and bug match the Expect line, no unused argument, no fixture used without being an argument, the autouse fixture lists every standing row, every snapshot before the When. 0 problems.

## How the tests are built
- **Only the clock is patched** (Conventions, Externals). Nothing else is mocked.
- **Standing rows:** one fixture per Conventions row (`w1`, `w2`, `u1`, `u2`), each depending on the row before, so they are flushed one at a time in Conventions order. The autouse `standing_rows` makes all of them exist in every test; a test lists only those it names.
- **`where`** (Conventions, Statement recorder): `where_part_of(sql)`, the text after `WHERE`, for MUS-T-09 and MUS-C-07.
- **Patch:** `patch("app.dao.mobile_upload_session.utcnow", return_value=NOW)` around the When of the `M` cards, the one external the spec lists. The `_naive_utc`, `T` and `C` cards read no clock.
- **Builders:** `mk_session(**columns)` = "session"; `status`, `delivery_type` stay out of the constructor.
- **Unsaved cards:** `S = MobileUploadSession(...)` is built in the test and never added; the standing rows still exist, as the Conventions say for every test.
- **Stored-row cards** (M-15 ... M-17): `SET LOCAL TIME ZONE` first, then the row, `db.expire_all()`, and the When reloads it, inside the patch.
- **Reading helpers (no expected values inside):** `ids`, and those the cards use of `snap` ("unchanged", every column by Core select, after `db.expire_all()`), `reread` ("re-read"), `stored_count` ("nothing written"), `seqscan`. `written` stays the card's name for the recorder's list.
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener on the session's connection, around the When only. `recorder.sql()` is the one SELECT naming the table, and fails loudly unless there is exactly one.
- **Given rows no line names again** are built without a variable. "It is a standing row" lines add no code. Row letters of the cards are lower case in the code.

## xfail location (`--runxfail`, reading the failing value)
Plugin: `chx_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childx\` (`-p chx_plug`; it records the test line and its `# Then N`; nothing in `app/`).

| Card | Strict | Card says | Fails on | Default runs xfailed | Actual |
|---|---|---|---|---|---|
| MUS-N-03 | yes | Then 2 | Then 2 | 3 of 3 | `assert datetime.datetime(2026, 1, 1, 0, 0) == datetime.datetime(2025, 12, 31, 18, 0)` |
| MUS-N-04 | yes | Then 2 | Then 2 | 3 of 3 | `assert datetime.datetime(2026, 1, 1, 8, 0) == datetime.datetime(2026, 1, 1, 13, 0)` |
| MUS-M-13 | yes | Then 2 | Then 2 | 3 of 3 | `assert 'waiting' == 'expired'` |
| MUS-M-14 | yes | Then 2 | Then 2 | 3 of 3 | `assert 'expired' == 'waiting'` |
| MUS-M-16 | yes | Then 2 | Then 2 | 3 of 3 | `assert 'waiting' == 'expired'` |
| MUS-M-17 | yes | Then 2 | Then 2 | 3 of 3 | `assert 'expired' == 'waiting'` |


**Proof of the lines past the failure point, and of the alarm.** `CHX_MODE=fix` replaces the methods in-process with the intended query (nothing in `app/`). With `--runxfail`: **51 passed**, so every Then line past a failure point holds on a fixed method. With the markers on: `6 failed, 45 passed`, the strict cards going red as `XPASS(strict)`.

## Revision 1: the verifier's named variants fail the new cards
Rebuilt by me in `var_plug.py` (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childx\`), from the names and meanings in `mobile_upload_session.verify.md`; none of the verifier's scripts was run. Each variant is swapped in memory on top of the reference (intended) methods, and the file runs with `--runxfail` on three plans (default, `enable_seqscan=off`, index and bitmap scans off). The reference alone: `51 passed`.

| Recipe | New cards | Variant | New cards that fail | Other cards that fail |
|---|---|---|---|---|
| R-1 | MUS-T-10, MUS-T-11, MUS-T-12, MUS-T-13, MUS-T-14, MUS-T-15, MUS-T-16, MUS-T-17, MUS-T-18 | `t_ilike` | MUS-T-13, MUS-T-14, MUS-T-15 | MUS-T-05 |
| R-1 | MUS-T-10, MUS-T-11, MUS-T-12, MUS-T-13, MUS-T-14, MUS-T-15, MUS-T-16, MUS-T-17, MUS-T-18 | `t_like` | MUS-T-13, MUS-T-14 | — |
| R-1 | MUS-T-10, MUS-T-11, MUS-T-12, MUS-T-13, MUS-T-14, MUS-T-15, MUS-T-16, MUS-T-17, MUS-T-18 | `t_contains` | MUS-T-10, MUS-T-16, MUS-T-17, MUS-T-18 | MUS-T-04 |
| R-1 | MUS-T-10, MUS-T-11, MUS-T-12, MUS-T-13, MUS-T-14, MUS-T-15, MUS-T-16, MUS-T-17, MUS-T-18 | `t_contains_raw` | MUS-T-10, MUS-T-13, MUS-T-14, MUS-T-16, MUS-T-17, MUS-T-18 | MUS-T-04 |
| R-1 | MUS-T-10, MUS-T-11, MUS-T-12, MUS-T-13, MUS-T-14, MUS-T-15, MUS-T-16, MUS-T-17, MUS-T-18 | `t_icontains` | MUS-T-10, MUS-T-13, MUS-T-14, MUS-T-15, MUS-T-16, MUS-T-17, MUS-T-18 | MUS-T-04, MUS-T-05 |
| R-1 | MUS-T-10, MUS-T-11, MUS-T-12, MUS-T-13, MUS-T-14, MUS-T-15, MUS-T-16, MUS-T-17, MUS-T-18 | `t_startswith` | MUS-T-10, MUS-T-17 | MUS-T-04 |
| R-1 | MUS-T-10, MUS-T-11, MUS-T-12, MUS-T-13, MUS-T-14, MUS-T-15, MUS-T-16, MUS-T-17, MUS-T-18 | `t_endswith` | MUS-T-10, MUS-T-16, MUS-T-18 | MUS-T-04 |
| R-1 | MUS-T-10, MUS-T-11, MUS-T-12, MUS-T-13, MUS-T-14, MUS-T-15, MUS-T-16, MUS-T-17, MUS-T-18 | `t_lower_both` | MUS-T-15 | MUS-T-05 |
| R-1 | MUS-T-10, MUS-T-11, MUS-T-12, MUS-T-13, MUS-T-14, MUS-T-15, MUS-T-16, MUS-T-17, MUS-T-18 | `t_lower_col` | MUS-T-15 | — |
| R-1 | MUS-T-10, MUS-T-11, MUS-T-12, MUS-T-13, MUS-T-14, MUS-T-15, MUS-T-16, MUS-T-17, MUS-T-18 | `t_lower_arg` | **none** | MUS-T-05 |
| R-1 | MUS-T-10, MUS-T-11, MUS-T-12, MUS-T-13, MUS-T-14, MUS-T-15, MUS-T-16, MUS-T-17, MUS-T-18 | `t_strip_arg` | MUS-T-11, MUS-T-12 | — |
| R-1 | MUS-T-10, MUS-T-11, MUS-T-12, MUS-T-13, MUS-T-14, MUS-T-15, MUS-T-16, MUS-T-17, MUS-T-18 | `t_lstrip_arg` | MUS-T-11 | — |
| R-1 | MUS-T-10, MUS-T-11, MUS-T-12, MUS-T-13, MUS-T-14, MUS-T-15, MUS-T-16, MUS-T-17, MUS-T-18 | `t_trim_col` | MUS-T-16, MUS-T-17 | — |
| R-1 | MUS-T-10, MUS-T-11, MUS-T-12, MUS-T-13, MUS-T-14, MUS-T-15, MUS-T-16, MUS-T-17, MUS-T-18 | `t_ltrim_col` | MUS-T-16 | — |
| R-2 | MUS-T-09, MUS-C-07 | `t_r3_not_cancelled` | MUS-T-09 | MUS-T-06 |
| R-2 | MUS-T-09, MUS-C-07 | `t_r3_not_consumed` | MUS-T-09 | — |
| R-2 | MUS-T-09, MUS-C-07 | `t_r3_not_uploaded` | MUS-T-09 | — |
| R-2 | MUS-T-09, MUS-C-07 | `t_r3_not_expired` | MUS-T-09 | MUS-T-07 |
| R-2 | MUS-T-09, MUS-C-07 | `c_r3_not_cancelled` | MUS-C-07 | MUS-C-05 |
| R-2 | MUS-T-09, MUS-C-07 | `c_r3_not_consumed` | MUS-C-07 | — |
| R-2 | MUS-T-09, MUS-C-07 | `c_r3_not_uploaded` | MUS-C-07 | — |
| R-2 | MUS-T-09, MUS-C-07 | `c_r3_not_expired` | MUS-C-07 | — |
| R-3 | MUS-C-08, MUS-C-09 | `c_r1_id_ge` | MUS-C-08, MUS-C-09 | — |
| R-3 | MUS-C-08, MUS-C-09 | `c_r2_ws_ge` | MUS-C-08 | — |
| R-3 | MUS-C-08, MUS-C-09 | `c_r2_user_ge` | MUS-C-09 | — |
| R-4 | MUS-T-19, MUS-C-10 | `t_w_expire` | MUS-T-19 | — |
| R-4 | MUS-T-19, MUS-C-10 | `t_w_expire_post` | MUS-T-19 | — |
| R-4 | MUS-T-19, MUS-C-10 | `t_w_dirty_refresh` | MUS-T-19 | — |
| R-4 | MUS-T-19, MUS-C-10 | `t_w_dirty_flush` | MUS-T-19 | — |
| R-4 | MUS-T-19, MUS-C-10 | `t_w_dirty_expire` | MUS-T-19 | — |
| R-4 | MUS-T-19, MUS-C-10 | `c_w_expire` | MUS-C-10 | — |
| R-4 | MUS-T-19, MUS-C-10 | `c_w_expire_post` | MUS-C-10 | — |
| R-4 | MUS-T-19, MUS-C-10 | `c_w_dirty_refresh` | MUS-C-10 | — |
| R-4 | MUS-T-19, MUS-C-10 | `c_w_dirty_flush` | MUS-C-10 | — |
| R-4 | MUS-T-19, MUS-C-10 | `c_w_dirty_expire` | MUS-C-10 | — |
| R-5 | MUS-M-01, MUS-M-18 | `m_r4_add_expire_stamp` | MUS-M-01 | — |
| R-5 | MUS-M-01, MUS-M-18 | `m_r4_read_first` | MUS-M-18 | — |

Not caught by a new card: `t_lower_arg`. Each lowers the argument only; an existing card catches it (column above), and the report does not name it for these recipes.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Coverage gaps
None — 100% line and branch coverage of `app/dao/mobile_upload_session.py` (19 statements, 4 branches, 0 missed), run with a private `COVERAGE_FILE`. The inherited `BaseDAO` methods live in `app/dao/base.py` and are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
| Run | Result |
|---|---|
| Default, run 1 | 45 passed, 6 xfailed |
| Default, run 2 | 45 passed, 6 xfailed |
| Default, run 3 | 45 passed, 6 xfailed |
| `enable_seqscan=off` | 45 passed, 6 xfailed |
| `enable_seqscan=off`, hash join and nested loop off | 45 passed, 6 xfailed |
| `enable_hashjoin=off` | 45 passed, 6 xfailed |
| index, bitmap and index-only scans off | 45 passed, 6 xfailed |
| the line above, hash and merge join off | 45 passed, 6 xfailed |
| database `TimeZone` `Asia/Dhaka` | 45 passed, 6 xfailed |
| database `TimeZone` `America/New_York` | 45 passed, 6 xfailed |
| Coverage run | 45 passed, 6 xfailed |

Revision 1 runs. Every pass card passed in every run above, and every strict card xfailed in every run above. 

`PGOPTIONS` carried the forced plans and the time zones. **Clock:** no card here compares two real-clock stamps, so no test can tie on the Windows clock, and nothing needed repeating. `ruff check` on the file: all checks passed. Line endings: LF.

## Revision history
- **Revision 0** (2026-11-02): 37 tests for 37 cases — 31 passed · 6 xfail (6 strict, 0 non-strict) · 0 discrepancies · 0 errors. Run 5 times plus forced plans; prose findings went to the verifier and are closed by Revision 1.
- **Revision 1 of the cases** (2026-11-03): 1 — the spec did not change. Additive, from `mobile_upload_session.verify.md` (case-missing Findings 1 … 5; recipes R-1 … R-5): R-1 → MUS-T-10 … MUS-T-18; R-2 → two Then lines each on MUS-T-09 and MUS-C-07, and `where` in Conventions; R-3 → MUS-C-08, MUS-C-09; R-4 → MUS-T-19, MUS-C-10; R-5 → one Then line on MUS-M-01, and MUS-M-18. New Then lines are numbered last, so no existing Then number moved. No ID retired. The file was patched, not regenerated: the diff against Revision 0 is the new tests, the new Then lines and the standing-row columns the revision names, and nothing else. Run 3 times plus forced plans, both time zones, coverage, `--runxfail`, explicit orders and the reference.

## Notes for maintainers
- All six xfails are strict. A fix of `_naive_utc` turns all six red together.
- MUS-M-08 reads the column with raw SQL and no flush; a `flush()` added to the method fails Then 4 and Then 5.
- "Nothing written" counts committed rows of all workspaces too. A run beside something that commits to this table could break it; nothing did here.
