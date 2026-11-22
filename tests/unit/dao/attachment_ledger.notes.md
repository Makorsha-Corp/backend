# Execution notes — `app/dao/attachment_ledger.py`

> Cases: `tests/unit/dao/attachment_ledger.cases.md` (Revision 1, READY, 73 cases) · Tests: `tests/unit/dao/test_attachment_ledger.py` · Source commit: e48a092
> Result: **73 tests for 73 cases — 64 passed · 9 xfail (7 strict, 2 non-strict) · 0 discrepancies · 0 errors** — line and branch coverage 100% (21 statements, 10 branches, 0 missed). The non-strict cards may XPASS without turning the run red, so a default run reads `64 passed, 9 xfailed`.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_attachment_ledger.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file (not kept; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childx\`), so values are the card's own text; an unknown Given or Then line stopped it. The fixtures and helpers were written by hand from the Conventions. A separate audit script checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matches the card's Then count in order with a check under each, every quoted literal of the card present, the When call as written, marker and bug match the Expect line, no unused argument, no fixture used without being an argument, the autouse fixture lists every standing row, every snapshot before the When. 0 problems.

## How the tests are built
- **Nothing is patched or mocked** (Conventions, Externals: None).
- **Standing rows:** one fixture per Conventions row (`w1`, `w2`, `u1`, `at1`, `at2`, `at9`, `atd`), each depending on the row before, so they are flushed one at a time in Conventions order. The autouse `standing_rows` makes all of them exist in every test; a test lists only those it names.
- **ATD** carries `deleted_by U1.id` (Revision 1, R-6).
- **Builders:** `mk_entry(performed_at=, **columns)` = "entry"; `mk_many(count)` = the 105-row Given of G-45, G-46, returns `in_order`, newest first.
- **Time-zone cards:** the `SET LOCAL TIME ZONE` line is the first statement of the body, as the Conventions ask.
- **Database-error cards** (G-49, G-50): `with pytest.raises(DataError) as exc:` around `with db.begin_nested():`; that block is Then 1, with no `result =`.
- **Spec gaps checked:** `is_deleted`, `deleted_at` are real columns of `Attachment`.
- **Reading helpers (no expected values inside):** `ids`, and those the cards use of `snap` ("unchanged", every column by Core select, after `db.expire_all()`), `reread` ("re-read"), `stored_count` ("nothing written"), `seqscan`. `written` stays the card's name for the recorder's list.
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener on the session's connection, around the When only. `recorder.sql()` is the one SELECT naming the table, and fails loudly unless there is exactly one.
- **Given rows no line names again** are built without a variable. "It is a standing row" lines add no code. Row letters of the cards are lower case in the code.

## xfail location (`--runxfail`, reading the failing value)
Plugin: `chx_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childx\` (`-p chx_plug`; it records the test line and its `# Then N`; nothing in `app/`).

| Card | Strict | Card says | Fails on | Default runs xfailed | Actual |
|---|---|---|---|---|---|
| ATL-G-32 | yes | Then 1 | Then 1 | 3 of 3 | `assert [] == [172824]` |
| ATL-G-33 | yes | Then 1 | Then 1 | 3 of 3 | `assert [172827, 172826] == [172826]` |
| ATL-G-35 | yes | Then 1 | Then 1 | 3 of 3 | `assert [172830, 172831] == [172830]` |
| ATL-G-36 | yes | Then 1 | Then 1 | 3 of 3 | `assert [] == [172832]` |
| ATL-G-37 | yes | Then 1 | Then 1 | 3 of 3 | `assert [172834, 172835] == [172834]` |
| ATL-G-38 | yes | Then 1 | Then 1 | 3 of 3 | `assert [] == [172836]` |
| ATL-G-42 | no | Then 2 | Then 2 | 3 of 3 | `assert [172846, 172847] == [172847, 172846]` |
| ATL-G-43 | no | Then 2 | Then 2 | 3 of 3 | `assert [172848, 172849] == [172849, 172848]` |
| ATL-G-44 | yes | Then 3 | Then 3 | 3 of 3 | `assert '.id DESC' in ' attachment_ledger.performed_at DESC \n LIMIT %(param_1)s OFFSET %(param_2)s'` |

**Proof that the non-strict cards can fail on their Then line.** An explicit order is a legal result for a query that asks for none, and it depends on neither plan nor heap. The plugin rewrites the module's read at `before_cursor_execute`. The recorder keeps seeing the original text, so the strict cards stay on their own Then.

| Rewrite | Cards that fail under `--runxfail` | Marked run | `--runxfail` run |
|---|---|---|---|
| `attachment_ledger.performed_at DESC, attachment_ledger.id` | ATL-G-32, ATL-G-33, ATL-G-35, ATL-G-36, ATL-G-37, ATL-G-38, ATL-G-42, ATL-G-43, ATL-G-44 | 64 passed, 9 xfailed | 9 failed, 64 passed |
| `attachment_ledger.performed_at DESC, attachment_ledger.file_name DESC` | ATL-G-32, ATL-G-33, ATL-G-35, ATL-G-36, ATL-G-37, ATL-G-38, ATL-G-42, ATL-G-43, ATL-G-44 | 64 passed, 9 xfailed | 9 failed, 64 passed |

No pass card failed under any rewrite, so no pass card depends on the order the bug leaves open.

**Proof of the lines past the failure point, and of the alarm.** `CHX_MODE=fix` replaces the methods in-process with the intended query (nothing in `app/`). With `--runxfail`: **73 passed**, so every Then line past a failure point holds on a fixed method. With the markers on: `7 failed, 64 passed, 2 xpassed`, the strict cards going red as `XPASS(strict)`.

## Revision 1: the verifier's named variants fail the new cards
Rebuilt by me in `var_plug.py` (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childx\`), from the names and meanings in `attachment_ledger.verify.md`; none of the verifier's scripts was run. Each variant is swapped in memory on top of the reference (intended) methods, and the file runs with `--runxfail` on three plans (default, `enable_seqscan=off`, index and bitmap scans off). The reference alone: `73 passed`.

| Recipe | New cards | Variant | New cards that fail | Other cards that fail |
|---|---|---|---|---|
| R-1/R-2 | ATL-G-57, ATL-G-58, ATL-G-59, ATL-G-60, ATL-G-61, ATL-G-62, ATL-G-63 | `r3_ilike` | ATL-G-61, ATL-G-62, ATL-G-63 | ATL-G-12 |
| R-1/R-2 | ATL-G-57, ATL-G-58, ATL-G-59, ATL-G-60, ATL-G-61, ATL-G-62, ATL-G-63 | `r3_like` | ATL-G-61, ATL-G-62, ATL-G-63 | — |
| R-1/R-2 | ATL-G-57, ATL-G-58, ATL-G-59, ATL-G-60, ATL-G-61, ATL-G-62, ATL-G-63 | `r3_contains` | ATL-G-59, ATL-G-60, ATL-G-63 | — |
| R-1/R-2 | ATL-G-57, ATL-G-58, ATL-G-59, ATL-G-60, ATL-G-61, ATL-G-62, ATL-G-63 | `r3_contains_raw` | ATL-G-59, ATL-G-60, ATL-G-61, ATL-G-62, ATL-G-63 | — |
| R-1/R-2 | ATL-G-57, ATL-G-58, ATL-G-59, ATL-G-60, ATL-G-61, ATL-G-62, ATL-G-63 | `r3_icontains` | ATL-G-59, ATL-G-60, ATL-G-61, ATL-G-62, ATL-G-63 | ATL-G-12 |
| R-1/R-2 | ATL-G-57, ATL-G-58, ATL-G-59, ATL-G-60, ATL-G-61, ATL-G-62, ATL-G-63 | `r3_startswith` | ATL-G-59, ATL-G-63 | — |
| R-1/R-2 | ATL-G-57, ATL-G-58, ATL-G-59, ATL-G-60, ATL-G-61, ATL-G-62, ATL-G-63 | `r3_endswith` | ATL-G-60, ATL-G-63 | — |
| R-1/R-2 | ATL-G-57, ATL-G-58, ATL-G-59, ATL-G-60, ATL-G-61, ATL-G-62, ATL-G-63 | `r3_lower_both` | ATL-G-63 | ATL-G-12 |
| R-1/R-2 | ATL-G-57, ATL-G-58, ATL-G-59, ATL-G-60, ATL-G-61, ATL-G-62, ATL-G-63 | `r3_lower_col` | ATL-G-63 | — |
| R-1/R-2 | ATL-G-57, ATL-G-58, ATL-G-59, ATL-G-60, ATL-G-61, ATL-G-62, ATL-G-63 | `r3_lower_arg` | **none** | ATL-G-12 |
| R-1/R-2 | ATL-G-57, ATL-G-58, ATL-G-59, ATL-G-60, ATL-G-61, ATL-G-62, ATL-G-63 | `r3_strip_arg` | ATL-G-57, ATL-G-58 | — |
| R-1/R-2 | ATL-G-57, ATL-G-58, ATL-G-59, ATL-G-60, ATL-G-61, ATL-G-62, ATL-G-63 | `r3_lstrip_arg` | ATL-G-57 | — |
| R-1/R-2 | ATL-G-57, ATL-G-58, ATL-G-59, ATL-G-60, ATL-G-61, ATL-G-62, ATL-G-63 | `r3_trim_col` | ATL-G-63 | — |
| R-1/R-2 | ATL-G-57, ATL-G-58, ATL-G-59, ATL-G-60, ATL-G-61, ATL-G-62, ATL-G-63 | `r3_ltrim_col` | ATL-G-63 | — |
| R-3 | ATL-G-64, ATL-G-65, ATL-G-66, ATL-G-67, ATL-G-68, ATL-G-69, ATL-G-70, ATL-G-71 | `r4_ilike` | ATL-G-68, ATL-G-69, ATL-G-70, ATL-G-71 | ATL-G-17 |
| R-3 | ATL-G-64, ATL-G-65, ATL-G-66, ATL-G-67, ATL-G-68, ATL-G-69, ATL-G-70, ATL-G-71 | `r4_like` | ATL-G-68, ATL-G-69, ATL-G-71 | — |
| R-3 | ATL-G-64, ATL-G-65, ATL-G-66, ATL-G-67, ATL-G-68, ATL-G-69, ATL-G-70, ATL-G-71 | `r4_contains` | ATL-G-66, ATL-G-67, ATL-G-70 | — |
| R-3 | ATL-G-64, ATL-G-65, ATL-G-66, ATL-G-67, ATL-G-68, ATL-G-69, ATL-G-70, ATL-G-71 | `r4_contains_raw` | ATL-G-66, ATL-G-67, ATL-G-68, ATL-G-69, ATL-G-70, ATL-G-71 | — |
| R-3 | ATL-G-64, ATL-G-65, ATL-G-66, ATL-G-67, ATL-G-68, ATL-G-69, ATL-G-70, ATL-G-71 | `r4_icontains` | ATL-G-66, ATL-G-67, ATL-G-68, ATL-G-69, ATL-G-70, ATL-G-71 | ATL-G-17 |
| R-3 | ATL-G-64, ATL-G-65, ATL-G-66, ATL-G-67, ATL-G-68, ATL-G-69, ATL-G-70, ATL-G-71 | `r4_startswith` | ATL-G-66, ATL-G-70 | — |
| R-3 | ATL-G-64, ATL-G-65, ATL-G-66, ATL-G-67, ATL-G-68, ATL-G-69, ATL-G-70, ATL-G-71 | `r4_endswith` | ATL-G-67, ATL-G-70 | — |
| R-3 | ATL-G-64, ATL-G-65, ATL-G-66, ATL-G-67, ATL-G-68, ATL-G-69, ATL-G-70, ATL-G-71 | `r4_lower_both` | ATL-G-70 | ATL-G-17 |
| R-3 | ATL-G-64, ATL-G-65, ATL-G-66, ATL-G-67, ATL-G-68, ATL-G-69, ATL-G-70, ATL-G-71 | `r4_lower_col` | ATL-G-70 | — |
| R-3 | ATL-G-64, ATL-G-65, ATL-G-66, ATL-G-67, ATL-G-68, ATL-G-69, ATL-G-70, ATL-G-71 | `r4_lower_arg` | **none** | ATL-G-17 |
| R-3 | ATL-G-64, ATL-G-65, ATL-G-66, ATL-G-67, ATL-G-68, ATL-G-69, ATL-G-70, ATL-G-71 | `r4_strip_arg` | ATL-G-64, ATL-G-65 | — |
| R-3 | ATL-G-64, ATL-G-65, ATL-G-66, ATL-G-67, ATL-G-68, ATL-G-69, ATL-G-70, ATL-G-71 | `r4_lstrip_arg` | ATL-G-64 | — |
| R-3 | ATL-G-64, ATL-G-65, ATL-G-66, ATL-G-67, ATL-G-68, ATL-G-69, ATL-G-70, ATL-G-71 | `r4_trim_col` | ATL-G-70 | — |
| R-3 | ATL-G-64, ATL-G-65, ATL-G-66, ATL-G-67, ATL-G-68, ATL-G-69, ATL-G-70, ATL-G-71 | `r4_ltrim_col` | ATL-G-70 | — |
| R-4 | ATL-G-72 | `r2_le` | ATL-G-72 | — |
| R-5 | ATL-G-73 | `g_w_expire` | ATL-G-73 | — |
| R-5 | ATL-G-73 | `g_w_expire_post` | ATL-G-73 | — |
| R-5 | ATL-G-73 | `g_w_dirty_refresh` | ATL-G-73 | — |
| R-5 | ATL-G-73 | `g_w_dirty_flush` | ATL-G-73 | — |
| R-5 | ATL-G-73 | `g_w_dirty_expire` | ATL-G-73 | — |
| R-7 | ATL-G-42 | `r8_id_asc` | ATL-G-42 | ATL-G-43, ATL-G-44 |
| R-7 | ATL-G-42 | `r8_no_tail` | ATL-G-42 | ATL-G-43, ATL-G-44 |
| R-7 | ATL-G-42 | `r8_name_desc_tail` | ATL-G-42 | ATL-G-43, ATL-G-44 |

Not caught by a new card: `r3_lower_arg`, `r4_lower_arg`. Each lowers the argument only; an existing card catches it (column above), and the report does not name it for these recipes.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Coverage gaps
None — 100% line and branch coverage of `app/dao/attachment_ledger.py` (21 statements, 10 branches, 0 missed), run with a private `COVERAGE_FILE`. The inherited `BaseDAO` methods live in `app/dao/base.py` and are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
| Run | Result | ATL-G-42 | ATL-G-43 |
|---|---|---|---|
| Default, run 1 | 64 passed, 9 xfailed | XFAIL | XFAIL |
| Default, run 2 | 64 passed, 9 xfailed | XFAIL | XFAIL |
| Default, run 3 | 64 passed, 9 xfailed | XFAIL | XFAIL |
| `enable_seqscan=off` | 64 passed, 9 xfailed | XFAIL | XFAIL |
| `enable_seqscan=off`, hash join and nested loop off | 64 passed, 9 xfailed | XFAIL | XFAIL |
| `enable_hashjoin=off` | 64 passed, 9 xfailed | XFAIL | XFAIL |
| index, bitmap and index-only scans off | 64 passed, 8 xfailed, 1 xpassed | XPASS | XFAIL |
| the line above, hash and merge join off | 64 passed, 8 xfailed, 1 xpassed | XPASS | XFAIL |
| database `TimeZone` `Asia/Dhaka` | 64 passed, 7 xfailed, 2 xpassed | XPASS | XPASS |
| database `TimeZone` `America/New_York` | 64 passed, 7 xfailed, 2 xpassed | XPASS | XPASS |
| Coverage run | 64 passed, 9 xfailed | XFAIL | XFAIL |

Revision 1 runs. Every pass card passed in every run above, and every strict card xfailed in every run above. What moves is only whether a non-strict card XPASSES: that follows the heap and the plan.

`PGOPTIONS` carried the forced plans and the time zones. **Clock:** no card here compares two real-clock stamps, so no test can tie on the Windows clock, and nothing needed repeating. `ruff check` on the file: all checks passed. Line endings: LF.

## Revision history
- **Revision 0** (2026-11-02): 56 tests for 56 cases — 47 passed · 9 xfail (7 strict, 2 non-strict) · 0 discrepancies · 0 errors. Run 5 times plus forced plans; prose findings went to the verifier and are closed by Revision 1.
- **Revision 1 of the cases** (2026-11-03): 1 — the spec did not change. Additive, from `attachment_ledger.verify.md` (case-missing Findings 1 … 6; recipes R-1 … R-7): R-1, R-2 → ATL-G-57 … ATL-G-63; R-3 → ATL-G-64 … ATL-G-71; R-4 → ATL-G-72; R-5 → ATL-G-73; R-6 → Conventions: ATD gains `deleted_by U1.id`; ATL-G-55's Given line says so; R-7 → ATL-G-42 now updates the higher id, B; its title and `Fails today on` parenthesis corrected (Finding 6). New Then lines are numbered last, so no existing Then number moved. No ID retired. The file was patched, not regenerated: the diff against Revision 0 is the new tests, the new Then lines and the standing-row columns the revision names, and nothing else. Run 3 times plus forced plans, both time zones, coverage, `--runxfail`, explicit orders and the reference.

## Notes for maintainers
- BUG-1281's fix turns six strict cards red, and BUG-640's turns ATL-G-44 red: `1 + 6` XPASS(strict) in all. Remove each marker with its fix; the two bugs are independent.
- G-37, G-38 mix a naive and an aware bound (Spec gap 3). A fix must hold them too.
- Never read a G-42 or G-43 XPASS as BUG-640 being gone.
- "Nothing written" counts committed rows of all workspaces too. A run beside something that commits to this table could break it; nothing did here.
