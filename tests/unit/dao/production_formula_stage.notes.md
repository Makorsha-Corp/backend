# Execution notes — `app/dao/production_formula_stage.py`

> Cases: `tests/unit/dao/production_formula_stage.cases.md` (Revision 1, READY, 21 cases) · Tests: `tests/unit/dao/test_production_formula_stage.py` · Source commit: e48a092
> Result: **21 tests for 21 cases — 21 passed · 0 xfail (0 strict, 0 non-strict) · 0 discrepancies · 0 errors** — line and branch coverage 100% (10 statements, 0 branches, 0 missed).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_production_formula_stage.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file (not kept; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childx\`), so values are the card's own text; an unknown Given or Then line stopped it. The fixtures and helpers were written by hand from the Conventions. A separate audit script checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matches the card's Then count in order with a check under each, every quoted literal of the card present, the When call as written, marker and bug match the Expect line, no unused argument, no fixture used without being an argument, the autouse fixture lists every standing row, every snapshot before the When. 0 problems.

## How the tests are built
- **Nothing is patched or mocked** (Conventions, Externals: None).
- **Standing rows:** one fixture per Conventions row (`w1`, `w2`, `pf1`, `pf2`, `pfd`), each depending on the row before, so they are flushed one at a time in Conventions order. The autouse `standing_rows` makes all of them exist in every test; a test lists only those it names.
- **Builders:** `mk_stage(stage_order=, **columns)` = "stage"; `mk_many(count)` = the 101-stage Given of G-11, returns `in_order`.
- **Spec gaps checked:** `ProductionFormula` needs no `version` (Python default 1).
- **Reading helpers (no expected values inside):** `ids`, and those the cards use of `snap` ("unchanged", every column by Core select, after `db.expire_all()`), `reread` ("re-read"), `stored_count` ("nothing written"), `seqscan`. `written` stays the card's name for the recorder's list.
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener on the session's connection, around the When only. `recorder.sql()` is the one SELECT naming the table, and fails loudly unless there is exactly one.
- **Given rows no line names again** are built without a variable. "It is a standing row" lines add no code. Row letters of the cards are lower case in the code.

## Explicit wrong order
No xfail here, so the same plugin served as a check of the pass cards.

| Rewrite | Cards that fail under `--runxfail` | Marked run | `--runxfail` run |
|---|---|---|---|
| `production_formula_stages.stage_order DESC` | PFS-G-01, PFS-G-10, PFS-G-11 | 3 failed, 18 passed | 3 failed, 18 passed |

**Proof of the lines past the failure point, and of the alarm.** `CHX_MODE=fix` replaces the methods in-process with the intended query (nothing in `app/`). No card here depends on it: `21 passed`.

## Revision 1: the verifier's named variants fail the new cards
Rebuilt by me in `var_plug.py` (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childx\`), from the names and meanings in `production_formula_stage.verify.md`; none of the verifier's scripts was run. Each variant is swapped in memory on top of the reference (intended) methods, and the file runs with `--runxfail` on three plans (default, `enable_seqscan=off`, index and bitmap scans off). The reference alone: `21 passed`.

| Recipe | New cards | Variant | New cards that fail | Other cards that fail |
|---|---|---|---|---|
| R-1 | PFS-I-05 | `i_r1_ws_ge` | PFS-I-05 | — |
| R-1 | PFS-I-05 | `i_r1_id_ge` | PFS-I-05 | — |
| R-2 | PFS-I-06 | `i_ov_join` | PFS-I-06 | — |
| R-2 | PFS-I-06 | `i_ov_flag` | PFS-I-06 | — |
| R-3 | PFS-G-14, PFS-I-07 | `g_w_expire` | PFS-G-14 | — |
| R-3 | PFS-G-14, PFS-I-07 | `g_w_expire_post` | PFS-G-14 | — |
| R-3 | PFS-G-14, PFS-I-07 | `g_w_dirty_refresh` | PFS-G-14 | — |
| R-3 | PFS-G-14, PFS-I-07 | `g_w_dirty_flush` | PFS-G-14 | — |
| R-3 | PFS-G-14, PFS-I-07 | `g_w_dirty_expire` | PFS-G-14 | — |
| R-3 | PFS-G-14, PFS-I-07 | `i_w_expire` | PFS-I-07 | — |
| R-3 | PFS-G-14, PFS-I-07 | `i_w_expire_post` | PFS-I-07 | — |
| R-3 | PFS-G-14, PFS-I-07 | `i_w_dirty_refresh` | PFS-I-07 | — |
| R-3 | PFS-G-14, PFS-I-07 | `i_w_dirty_flush` | PFS-I-07 | — |
| R-3 | PFS-G-14, PFS-I-07 | `i_w_dirty_expire` | PFS-I-07 | — |

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Coverage gaps
None — 100% line and branch coverage of `app/dao/production_formula_stage.py` (10 statements, 0 branches, 0 missed), run with a private `COVERAGE_FILE`. The inherited `BaseDAO` methods live in `app/dao/base.py` and are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
| Run | Result |
|---|---|
| Default, run 1 | 21 passed |
| Default, run 2 | 21 passed |
| Default, run 3 | 21 passed |
| `enable_seqscan=off` | 21 passed |
| `enable_seqscan=off`, hash join and nested loop off | 21 passed |
| `enable_hashjoin=off` | 21 passed |
| index, bitmap and index-only scans off | 21 passed |
| the line above, hash and merge join off | 21 passed |
| database `TimeZone` `Asia/Dhaka` | 21 passed |
| database `TimeZone` `America/New_York` | 21 passed |
| Coverage run | 21 passed |

Revision 1 runs. Every pass card passed in every run above, with no xfail in the file. 

`PGOPTIONS` carried the forced plans and the time zones. **Clock:** no card here compares two real-clock stamps, so no test can tie on the Windows clock, and nothing needed repeating. `ruff check` on the file: all checks passed. Line endings: LF.

## Revision history
- **Revision 0** (2026-11-02): 17 tests for 17 cases — 17 passed · 0 xfail (0 strict, 0 non-strict) · 0 discrepancies · 0 errors. Run 5 times plus forced plans; prose findings went to the verifier and are closed by Revision 1.
- **Revision 1 of the cases** (2026-11-03): 1 — the spec did not change. Additive, from `production_formula_stage.verify.md` (case-missing Findings 1 … 3; recipes R-1 … R-3): R-1 → PFS-I-05; R-2 → PFS-I-06; R-3 → PFS-G-14, PFS-I-07. New Then lines are numbered last, so no existing Then number moved. No ID retired. The file was patched, not regenerated: the diff against Revision 0 is the new tests, the new Then lines and the standing-row columns the revision names, and nothing else. Run 3 times plus forced plans, both time zones, coverage, `--runxfail`, explicit orders and the reference.

## Notes for maintainers
- No xfail here. The `stage_order` order is pinned by G-01, G-10, G-11.
- "Nothing written" counts committed rows of all workspaces too. A run beside something that commits to this table could break it; nothing did here.
