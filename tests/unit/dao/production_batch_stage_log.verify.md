# Verification — `app/dao/production_batch_stage_log.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1, 23 cases). See "Round 2" at the end. The block below is round 1.

> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 19 passed · 0 xfail, 0 strict, 0 non-strict (reproduced ✅) · coverage 100% branch (10 statements, 0 branches, 0 missed)
> Mutation: 6 mutants · 6 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 19 unfaithful** (19 / 19 right)
> Hand variants: 62 · 44 caught by a pass card · 18 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 19 match their cards.
- **Why NEEDS WORK:** 6 of 6 sites killed; four gaps for the case designer, one of them the executor's PBL-G-14 point, which I confirm.
- No money, stock or order state.
- **Ruling on the executor's point:** PBL-G-14: the executor is right; a raw `DELETE` card added (Finding 4, Recipe R-4).

Written by Claude (all 19 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 19. No `production_batch_stage_log.local-run.json` exists, so there is no `## Local-coder patterns` section. Script-compared; its differences read by eye (none in this file).

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_id_and_workspace` R1, another workspace | PBL-I-02 asks W2 for a W1 row. | `i_r1_ws_ge`, `i_r1_id_ge` pass all 19. | case designer |
| 2 | case-missing | skill 1b: a reader does not join its parent (both reads) | No card forbids `production_batches` in the statement. Spec: the reads follow the row. | `g_ov_join`, `g_ov_draft`, `i_ov_join` pass all 19. | case designer |
| 3 | case-missing | both readers, Side effects: none (skill 1b) | The writes-nothing cards check a pending row only. | the ten `*_w_*` pass all 19. | case designer |
| 4 | case-missing | `get_by_batch` R5 (ruling on PBL-G-14) | The executor is right. `db.delete(FS1)` loads the backref and sends its own `UPDATE ... SET formula_stage_id=NULL`, so the database's `ON DELETE SET NULL` is never exercised. Proof without DDL: with `SET LOCAL session_replication_role = replica` (foreign-key actions off) the card's shape still passes, a raw `DELETE` fails. The card is faithful to its own text; the Reviewer summary's "SET NULL does the work" is wrong. | scratch `test_s1_orm_delete_no_fk_action` passes, `test_s2_raw_delete_no_fk_action` fails; `test_r3_g_raw_delete` passes with the actions on. | case designer |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv\prop\test_prop_production_batch_stage_log.py`, not in the repo. Each passes on today's code (a non-strict xfail recipe may fail today) and on the reference, on all three plans. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card, I R1 | Z = log, `stage_order 1`, but `workspace_id W2.id`; then A = log, `stage_order 2`. When by id Z in W1 | `result is None` | pass | `i_r1_ws_ge`, `i_r1_id_ge` |
| R-2 | two lines on PBL-G-15 and PBL-I-04 (the writes-nothing cards) | as they are | `statement: "production_batches" not in sql` | pass | `g_ov_join`, `g_ov_draft`, `i_ov_join` |
| R-3 | two new cards, Side effects | G: A = log, `stage_order 1`; B = log, `stage_order 1`, but `batch_id B2.id`; `B.stage_name = "Edited"`, not flushed. I: A, B = logs 1 and 2, B edited the same way | the card's result check; `session: B in db.dirty`; `session: len(db.dirty) == 1` | pass | the ten `*_w_*` |
| R-4 | new card, R5 | FS1 as PBL-G-14; A = log, `stage_order 1`, but `formula_stage_id FS1.id`, `stage_name "Mixing"`; `db.execute(text("DELETE FROM production_formula_stages WHERE id = :i"), {"i": FS1.id})`; `db.expire_all()` | PBL-G-14's three Then lines | pass | a schema without `ON DELETE SET NULL` (shown with FK actions off) |

## Surviving mutants
None. All 6 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 6 mutants with no `-x`: every run reached all 19 pass tests, with no collection or setup error.

## Hand variants
`variants.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv`, on the reference (none (no bug in this module)), with `--runxfail`, on three plans: default, sequential scans off, index and bitmap scans off. Every edit was asserted to apply once and every run reached all 19 tests with no error. Group names: the rule, `w` session side effects, `txt` text compare, `page` paging, `ret` return shape, `ov` parent state.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| g_r1 | 7 | 7 | PBL-G-02, PBL-G-03, PBL-G-04, PBL-G-05, PBL-G-06, PBL-G-07 … | — |
| g_r3 | 10 | 10 | PBL-G-01, PBL-G-10, PBL-G-11, PBL-G-12, PBL-G-13 | — |
| g_r5 | 2 | 2 | PBL-G-01, PBL-G-02, PBL-G-05, PBL-G-06, PBL-G-10, PBL-G-11 … | — |
| g_ov | 2 | 0 | — | `g_ov_join`, `g_ov_draft` |
| g_r4 | 3 | 1 | PBL-G-13 | `g_r4_cap_101`, `g_r4_cap_1000` |
| g_ret | 4 | 4 | PBL-G-01, PBL-G-03, PBL-G-04, PBL-G-07, PBL-G-08, PBL-G-09 … | — |
| g_w | 12 | 7 | PBL-G-14, PBL-G-15 | `g_w_expire`, `g_w_expire_post`, `g_w_dirty_refresh`, `g_w_dirty_flush`, `g_w_dirty_expire` |
| i_r1 | 8 | 5 | PBL-I-01, PBL-I-02, PBL-I-03 | `i_r1_ws_ge`, `i_r1_id_ge`, `i_r1_one_or_none` |
| i_ov | 1 | 0 | — | `i_ov_join` |
| i_ret | 1 | 1 | PBL-I-01, PBL-I-04 | — |
| i_w | 12 | 7 | PBL-I-04 | `i_w_expire`, `i_w_expire_post`, `i_w_dirty_refresh`, `i_w_dirty_flush`, `i_w_dirty_expire` |
| **Total** | **62** | **44** |  | **18** |

With the recipes added, 66 of 62 are caught; the rest are below.

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `g_r4_cap_101`, `g_r4_cap_1000` | A cap above the card's own 101 rows. |
| `i_r1_one_or_none` | **Equivalent:** primary key. |
| `g_r3_no_tail`, `g_r3_stamp_tail`, `g_r3_stamp_desc_tail`, `g_r3_upd_tail` | Caught on all three plans, by PBL-G-10 or G-11 or the recorder G-12 depending on the plan. Not a gap. |

## xfail tests against the reference
No xfail here. With `--runxfail` today and on the reference: 19 passed.

## Reproduced claims
- Coverage run: `19 passed in 4.14s`; `app\dao\production_batch_stage_log.py      10      0      0      0   100%`. Four more default runs: `19 passed in 2.27s`, `19 passed in 2.32s`, `19 passed in 2.29s`, `19 passed in 2.30s`.
- `--runxfail -rf`: `19 passed in 2.52s`; failed: none.
- 15 more runs (5 per plan): 19 passed in every run, no pass card or strict card moved. **No flaky test.** Only non-strict cards move between XFAIL and XPASS, which their markers allow; the notes' sample default line is one heap's result.
- **Mocks:** none. No `try`, no `if`, no broad `pytest.raises` in a test body.

## Traceability
cases 19 · tests 19 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md` and each reason carries the row's title. All sit under `# [claude] <ID>`. `ruff check` passes.

My own script (`rebuild.py`) rebuilt each test's Given, snapshots, When, Then and marker from its card, and the constants, standing rows, builders and helpers from the Conventions, and compared by AST, for all 302 cards of the batch: 0 reports. Selftest (`selftest.py`, 3 seeds): 9306 of 9306 planted mistakes of 81 kinds, in tests, helpers and cards, reported on the right card.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents were live on `marker_test`. Every kill is a plain `N failed` with all tests reached.
- **No DDL.** The one schema question (PBL-G-14) was answered with `SET LOCAL session_replication_role = replica` inside a rolled-back test, which switches foreign-key actions off without a lock.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/production_batch_stage_log.py tests/unit/dao/test_production_batch_stage_log.py --timeout 300 --json <scratch>/res/mut_production_batch_stage_log.json   (through runmut.py, TEMP in scratch)
  6 mutants · 6 killed · 0 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_production_batch_stage_log.py -q -p no:cacheprovider --cov=app.dao.production_batch_stage_log --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  19 passed in 4.14s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_production_batch_stage_log.py -q -p no:cacheprovider --runxfail -rf
  19 passed in 2.52s
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
> Tests: 23 passed · 0 xfail, 0 strict, 0 non-strict (reproduced ✅) · coverage as round 1
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 23 unfaithful** (new and changed cards read by eye; all 23 rebuilt by script)
> Hand variants: 62 · 59 caught by a pass card · every round-1 gap variant fails its new card
> Source commit: e48a092 · Cases revision: 1

Every finding of round 1 is closed. No new rule gap. No test edited, no commit. Nothing parked for the owner.

### New and changed tests
PBL-I-05, PBL-G-16, PBL-I-06, PBL-G-17; new Then lines on PBL-G-15, PBL-I-04. Each was read against its card. "Fails" means the variant fails that card on the reference with `--runxfail`, on all three plans.

| Card | Recipe | Fails |
|---|---|---|
| PBL-I-05 | R-1 | `i_r1_ws_ge`, `i_r1_id_ge` |
| PBL-G-15, PBL-I-04 | R-2 | `g_ov_join`, `g_ov_draft` / `i_ov_join` |
| PBL-G-16 | R-3 | the five `g_w_*` |
| PBL-I-06 | R-3 | the five `i_w_*` |
| PBL-G-17 | R-4 | a raw `DELETE`; the database's `SET NULL` does the work |

### Rest of the batch
All 62 variants ran again on the reference, each reaching all 23 tests, on all three plans. Left without a pass card: `g_r4_cap_1000`, `g_r4_cap_101`, `i_r1_one_or_none`. Each is under round 1's "Considered and not listed" (bug path, a cap above the card's own rows, or equivalent); none is a new rule gap.

### Reproduced
- Coverage run: `23 passed in 4.20s`; `['app\\dao\\production_batch_stage_log.py      10      0      0      0   100%']`. Four more default runs: `23 passed in 2.43s`, `23 passed in 2.37s`, `23 passed in 2.22s`, `23 passed in 2.24s`.
- `--runxfail`: `23 passed in 2.25s []`. Every strict card fails on its card's `Fails today on` line.
- 15 more runs (5 per plan): 23 passed in every run; only non-strict cards move. No flaky test.
- Traceability: cases 23 · tests 23 · unmatched: none · marker mismatches: none. `rebuild.py`: 361 cards over the eleven files, 0 reports (it learned the new `where` name of `mobile_upload_session`). Selftest: 9306 of 9306 planted mistakes, 3 seeds. `ruff check` passes.
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
