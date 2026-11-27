# Verification — `app/dao/work_order_item.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1, 31 cases). See "Round 2" at the end. The block below is round 1.

> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 24 passed · 3 xfail, 1 strict, 2 non-strict (reproduced ✅) · coverage 100% branch (13 statements, 2 branches, 0 missed)
> Mutation: 10 mutants · 10 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 27 unfaithful** (27 / 27 right)
> Hand variants: 68 · 44 caught by a pass card · 24 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 27 match their cards.
- **Why NEEDS WORK:** 10 of 10 sites killed; four gaps for the case designer: the by-id read's workspace and parent shapes, side effects on both reads, and the soft-deleted order's columns.
- **Stock: the reader drives stock posting at work-order start; no gap here changes which lines are returned.**
- **Ruling on the executor's point:** WOI-G-16: the same, one plan (Finding 5).

Written by Claude (all 27 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 27. No `work_order_item.local-run.json` exists, so there is no `## Local-coder patterns` section. Script-compared; its differences read by eye (none in this file).

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_id_and_workspace` R1, another workspace | WOI-I-02 asks W2 for a W1 row. The other workspace's row must be the earlier id. | `i_r1_ws_ge`, `i_r1_id_ge` pass all 24. | case designer |
| 2 | case-missing | skill 1b: a reader does not join its parent (`get_by_id_and_workspace`) | No by-id card on a line of WOD and no `"work_orders" not in sql` for this read. | `i_ov_join`, `i_ov_flag` pass all 24. | case designer |
| 3 | case-missing | both readers, Side effects: none (skill 1b) | The writes-nothing cards check a pending row only. | the five `g_w_*` and five `i_w_*` pass all 24. | case designer |
| 4 | case-missing | skill 1b real states, R7 | WOD has `is_deleted True`, `is_active False`; `WorkOrderDAO.soft_delete` (app/dao/work_order.py:361) also writes `deleted_at` and `deleted_by`. No variant survives today (the `work_orders` statement check catches the joins), so this is the shape, not a kill. | scratch card `test_r5_g_real_close` passes on today's code and on the reference. | case designer |
| 5 | prose | WOI-G-16 `Fails today on` | Ruling on the executor's point: XFAIL 4/5 default, XPASS 5/5 on both forced plans in my runs. The parenthesis describes one plan; marker and assertion are right. | `res/nonstrict.json` | case designer (one parenthesis) |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv\prop\test_prop_work_order_item.py`, not in the repo. Each passes on today's code (a non-strict xfail recipe may fail today) and on the reference, on all three plans. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card, I R1 | Z = line, but `workspace_id W2.id`; then A = line. When `get_by_id_and_workspace(id=Z.id, workspace_id=W1.id)` | `result is None` | pass | `i_r1_ws_ge`, `i_r1_id_ge` |
| R-2 | new card, I, 1b | A = line, but `work_order_id WOD.id`; a recorder. When `get_by_id_and_workspace(id=A.id, workspace_id=W1.id)` | `result.id == A.id`; `statement: "work_orders" not in sql` | pass | `i_ov_join`, `i_ov_flag` |
| R-3 | two new cards, Side effects | G: A = line; B = line, but `work_order_id WO2.id`; `B.quantity = Decimal("5.00")`, not flushed; When `get_by_work_order(work_order_id=WO1.id, workspace_id=W1.id)`. I: A, B = lines, B edited the same way; When by id A | the card's result check; `session: B in db.dirty`; `session: len(db.dirty) == 1` | pass | the ten `*_w_*` |
| R-4 | Conventions | WOD = the same, but `work_order_number "WO-T-003"`, `is_deleted True`, `is_active False`, `deleted_at T12`, `deleted_by U1.id` | WOI-G-20 unchanged | pass | (shape) |

## Surviving mutants
None. All 10 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 10 mutants with no `-x`: every run reached all 24 pass tests, with no collection or setup error.

## Hand variants
`variants.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv`, on the reference (`order_by(id)` in `get_by_work_order`), with `--runxfail`, on three plans: default, sequential scans off, index and bitmap scans off. Every edit was asserted to apply once and every run reached all 27 tests with no error. Group names: the rule, `w` session side effects, `txt` text compare, `page` paging, `ret` return shape, `ov` parent state.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| g_r1 | 7 | 7 | WOI-G-02, WOI-G-03, WOI-G-04, WOI-G-05, WOI-G-06, WOI-G-07 … | — |
| g_r3 | 4 | 2 | WOI-G-10, WOI-G-11, WOI-G-12, WOI-G-13 | `g_r3_at`, `g_r3_by` |
| g_r4 | 3 | 3 | WOI-G-10, WOI-G-13, WOI-G-14, WOI-G-15 | — |
| g_r5 | 4 | 0 | — | `g_r5_none`, `g_r5_desc`, `g_r5_qty`, `g_r5_item` |
| g_r6 | 3 | 1 | WOI-G-19 | `g_r6_cap_101`, `g_r6_cap_1000` |
| g_r7 | 6 | 6 | WOI-G-20, WOI-G-22 | — |
| g_r8 | 1 | 1 | WOI-G-21 | — |
| g_ret | 4 | 3 | WOI-G-01, WOI-G-03, WOI-G-04, WOI-G-07, WOI-G-08, WOI-G-09 … | `g_ret_rev` |
| g_w | 12 | 7 | WOI-G-22 | `g_w_expire`, `g_w_expire_post`, `g_w_dirty_refresh`, `g_w_dirty_flush`, `g_w_dirty_expire` |
| i_r1 | 9 | 6 | WOI-I-01, WOI-I-02, WOI-I-03, WOI-I-04 | `i_r1_ws_ge`, `i_r1_id_ge`, `i_r1_one_or_none` |
| i_ov | 2 | 0 | — | `i_ov_join`, `i_ov_flag` |
| i_ret | 1 | 1 | WOI-I-01, WOI-I-04, WOI-I-05 | — |
| i_w | 12 | 7 | WOI-I-05 | `i_w_expire`, `i_w_expire_post`, `i_w_dirty_refresh`, `i_w_dirty_flush`, `i_w_dirty_expire` |
| **Total** | **68** | **44** |  | **24** |

With the recipes added, 58 of 68 are caught; the rest are below.

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `g_r3_at`, `g_r3_by` | **Equivalent on real states:** `remove_item` writes `is_deleted`, `deleted_at`, `deleted_by` together, so a filter on any one of them gives the same rows. |
| `g_r5_none`, `g_r5_desc`, `g_r5_qty`, `g_r5_item`, `g_ret_rev` | **Bug path** (BUG-1272). |
| `g_r6_cap_101`, `g_r6_cap_1000` | A cap above the card's own 101 rows. |
| `i_r1_one_or_none` | **Equivalent:** primary key. |

## xfail tests against the reference
Reference: `order_by(id)` in `get_by_work_order`, swapped in memory. Nothing is written to `app/`. With `--runxfail` on the reference: 27 passed. **The alarm works:** with the markers on, every strict card goes `XPASS(strict)`.

| Card | Marker | Card's Fails line | Seen |
|---|---|---|---|
| WOI-G-16 | non-strict | Then 2 | default: XFAIL 4, XPASS 1; idx: XPASS 5; seq: XPASS 5; fails on Then 2 when it fails, also under wrong tie orders |
| WOI-G-17 | non-strict | Then 2 | default: XPASS 5; idx: XPASS 5; seq: XPASS 5; fails on Then 2 when it fails, also under wrong tie orders |
| WOI-G-18 | strict | Then 2 | fails on Then 2 in 3 of 3 `--runxfail` runs, as the card says |

## Reproduced claims
- Coverage run: `24 passed, 2 xfailed, 1 xpassed in 4.89s`; `app\dao\work_order_item.py      13      0      2      0   100%`. Four more default runs: `24 passed, 2 xfailed, 1 xpassed in 2.85s`, `24 passed, 2 xfailed, 1 xpassed in 2.77s`, `24 passed, 2 xfailed, 1 xpassed in 2.71s`, `24 passed, 2 xfailed, 1 xpassed in 2.72s`.
- `--runxfail -rf`: `2 failed, 25 passed in 2.65s`; failed: WOI-G-16, WOI-G-18.
- 15 more runs (5 per plan): 24 passed in every run, no pass card or strict card moved. **No flaky test.** Only non-strict cards move between XFAIL and XPASS, which their markers allow; the notes' sample default line is one heap's result.
- **Mocks:** none. No `try`, no `if`, no broad `pytest.raises` in a test body.

## Traceability
cases 27 · tests 27 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md` and each reason carries the row's title. All sit under `# [claude] <ID>`. `ruff check` passes.

My own script (`rebuild.py`) rebuilt each test's Given, snapshots, When, Then and marker from its card, and the constants, standing rows, builders and helpers from the Conventions, and compared by AST, for all 302 cards of the batch: 0 reports. Selftest (`selftest.py`, 3 seeds): 9306 of 9306 planted mistakes of 81 kinds, in tests, helpers and cards, reported on the right card.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents were live on `marker_test`. Every kill is a plain `N failed` with all tests reached.
- **No DDL.** The one schema question (PBL-G-14) was answered with `SET LOCAL session_replication_role = replica` inside a rolled-back test, which switches foreign-key actions off without a lock.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/work_order_item.py tests/unit/dao/test_work_order_item.py --timeout 300 --json <scratch>/res/mut_work_order_item.json   (through runmut.py, TEMP in scratch)
  10 mutants · 10 killed · 0 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_work_order_item.py -q -p no:cacheprovider --cov=app.dao.work_order_item --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  24 passed, 2 xfailed, 1 xpassed in 4.89s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_work_order_item.py -q -p no:cacheprovider --runxfail -rf
  2 failed, 25 passed in 2.65s
repro.py; nonstrict.py (5 runs x 3 plans); thenloc.py                as under Reproduced
drive.py bases | muts | vars --plan default|seq|idx                     as above
propdrive.py (3 plans)                                                  recipes as in the table
rebuild.py; selftest.py 7|21|33                                         302 cards, 0 reports; 9306 of 9306
.venv/Scripts/python.exe -m ruff check <the eleven test files>         All checks passed!
git diff --stat -- app/dao                                              (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add the recipes above; the Givens and Thens are written out. Fix the parenthesis named in the ruling.
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-03 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 28 passed · 3 xfail, 1 strict, 2 non-strict (reproduced ✅) · coverage as round 1
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 31 unfaithful** (new and changed cards read by eye; all 31 rebuilt by script)
> Hand variants: 68 · 58 caught by a pass card · every round-1 gap variant fails its new card
> Source commit: e48a092 · Cases revision: 1

Every finding of round 1 is closed. No new rule gap. No test edited, no commit. Nothing parked for the owner.

### New and changed tests
WOI-I-06, WOI-I-07, WOI-I-08, WOI-G-23; WOD's Conventions and WOI-G-20's Given; WOI-G-16's parenthesis. Each was read against its card. "Fails" means the variant fails that card on the reference with `--runxfail`, on all three plans.

| Card | Recipe | Fails |
|---|---|---|
| WOI-I-06 | R-1 | `i_r1_ws_ge`, `i_r1_id_ge` |
| WOI-I-07 | R-2 | `i_ov_join`, `i_ov_flag` |
| WOI-G-23 | R-3 | the five `g_w_*` |
| WOI-I-08 | R-3 | the five `i_w_*` |
| WOD | R-4 | shape; `wod` fixture equals the Conventions |

### Rest of the batch
All 68 variants ran again on the reference, each reaching all 31 tests, on all three plans. Left without a pass card: `g_r3_at`, `g_r3_by`, `g_r5_desc`, `g_r5_item`, `g_r5_none`, `g_r5_qty`, `g_r6_cap_1000`, `g_r6_cap_101`, `g_ret_rev`, `i_r1_one_or_none`. Each is under round 1's "Considered and not listed" (bug path, a cap above the card's own rows, or equivalent); none is a new rule gap.

### Reproduced
- Coverage run: `28 passed, 1 xfailed, 2 xpassed in 4.97s`; `['app\\dao\\work_order_item.py      13      0      2      0   100%']`. Four more default runs: `28 passed, 1 xfailed, 2 xpassed in 2.82s`, `28 passed, 1 xfailed, 2 xpassed in 2.90s`, `28 passed, 1 xfailed, 2 xpassed in 2.63s`, `28 passed, 2 xfailed, 1 xpassed in 2.79s`.
- `--runxfail`: `2 failed, 29 passed in 2.68s ['woi_g_16', 'woi_g_18']`. Every strict card fails on its card's `Fails today on` line.
- 15 more runs (5 per plan): 28 passed in every run; only non-strict cards move. No flaky test.
- Traceability: cases 31 · tests 31 · unmatched: none · marker mismatches: none. `rebuild.py`: 361 cards over the eleven files, 0 reports (it learned the new `where` name of `mobile_upload_session`). Selftest: 9306 of 9306 planted mistakes, 3 seeds. `ruff check` passes.
- **Limit:** I kept no copy of the round-1 test file; "existing tests unchanged" rests on the rebuild of all cards against the current cases file.

### Commands run
```
drive.py bases | vars --plan default|seq|idx <module>     reference, alarm, variants
r2check.py                                             gap variants against their new cards
repro.py; nonstrict.py; thenloc.py                     as under Reproduced
rebuild.py; selftest.py 7|21|33                        361 cards, 0 reports; 9306 of 9306
.venv/Scripts/python.exe -m ruff check <the eleven test files>     All checks passed!
git diff --stat -- app/dao                             (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv\`. Only this report was edited in the repo. Nothing was stopped or killed.
