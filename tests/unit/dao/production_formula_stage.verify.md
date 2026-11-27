# Verification — `app/dao/production_formula_stage.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1, 21 cases). See "Round 2" at the end. The block below is round 1.

> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 17 passed · 0 xfail, 0 strict, 0 non-strict (reproduced ✅) · coverage 100% branch (10 statements, 0 branches, 0 missed)
> Mutation: 6 mutants · 6 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 17 unfaithful** (17 / 17 right)
> Hand variants: 58 · 41 caught by a pass card · 17 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 17 match their cards.
- **Why NEEDS WORK:** 6 of 6 sites killed; three gaps for the case designer on the by-id read and side effects.
- No money, stock or order state.

Written by Claude (all 17 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 17. No `production_formula_stage.local-run.json` exists, so there is no `## Local-coder patterns` section. Script-compared; its differences read by eye (none in this file).

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_id_and_workspace` R1, another workspace | PFS-I-02 asks W2 for a W1 row. | `i_r1_ws_ge`, `i_r1_id_ge` pass all 17. | case designer |
| 2 | case-missing | skill 1b: a reader does not join its parent (`get_by_id_and_workspace`) | Only `get_by_formula` has `"production_formulas" not in sql` and a PFD card. | `i_ov_join`, `i_ov_flag` pass all 17. | case designer |
| 3 | case-missing | both readers, Side effects: none (skill 1b) | The writes-nothing cards check a pending row only. | the ten `*_w_*` pass all 17. | case designer |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv\prop\test_prop_production_formula_stage.py`, not in the repo. Each passes on today's code (a non-strict xfail recipe may fail today) and on the reference, on all three plans. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card, I R1 | Z = stage, `stage_order 1`, but `workspace_id W2.id`; then A = stage, `stage_order 2`. When by id Z in W1 | `result is None` | pass | `i_r1_ws_ge`, `i_r1_id_ge` |
| R-2 | new card, I, 1b | A = stage, `stage_order 1`, but `formula_id PFD.id`; a recorder. When by id A in W1 | `result.id == A.id`; `statement: "production_formulas" not in sql` | pass | `i_ov_join`, `i_ov_flag` |
| R-3 | two new cards, Side effects | G: A = stage, `stage_order 1`; B = stage, `stage_order 1`, but `formula_id PF2.id`; `B.name = "Edited"`, not flushed. I: A, B = stages 1 and 2, B edited the same way | the card's result check; `session: B in db.dirty`; `session: len(db.dirty) == 1` | pass | the ten `*_w_*` |

## Surviving mutants
None. All 6 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 6 mutants with no `-x`: every run reached all 17 pass tests, with no collection or setup error.

## Hand variants
`variants.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv`, on the reference (none (no bug in this module)), with `--runxfail`, on three plans: default, sequential scans off, index and bitmap scans off. Every edit was asserted to apply once and every run reached all 17 tests with no error. Group names: the rule, `w` session side effects, `txt` text compare, `page` paging, `ret` return shape, `ov` parent state.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| g_r1 | 7 | 7 | PFS-G-02, PFS-G-03, PFS-G-04, PFS-G-05, PFS-G-06, PFS-G-07 … | — |
| g_r3 | 6 | 6 | PFS-G-01, PFS-G-10, PFS-G-11 | — |
| g_r5 | 3 | 3 | PFS-G-12, PFS-G-13 | — |
| g_r4 | 3 | 1 | PFS-G-11 | `g_r4_cap_101`, `g_r4_cap_1000` |
| g_ret | 4 | 4 | PFS-G-01, PFS-G-03, PFS-G-04, PFS-G-07, PFS-G-08, PFS-G-09 … | — |
| g_w | 12 | 7 | PFS-G-13 | `g_w_expire`, `g_w_expire_post`, `g_w_dirty_refresh`, `g_w_dirty_flush`, `g_w_dirty_expire` |
| i_r1 | 8 | 5 | PFS-I-01, PFS-I-02, PFS-I-03 | `i_r1_ws_ge`, `i_r1_id_ge`, `i_r1_one_or_none` |
| i_ov | 2 | 0 | — | `i_ov_join`, `i_ov_flag` |
| i_ret | 1 | 1 | PFS-I-01, PFS-I-04 | — |
| i_w | 12 | 7 | PFS-I-04 | `i_w_expire`, `i_w_expire_post`, `i_w_dirty_refresh`, `i_w_dirty_flush`, `i_w_dirty_expire` |
| **Total** | **58** | **41** |  | **17** |

With the recipes added, 55 of 58 are caught; the rest are below.

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `g_r4_cap_101`, `g_r4_cap_1000` | A cap above the card's own 101 rows. |
| `i_r1_one_or_none` | **Equivalent:** primary key. |

## xfail tests against the reference
No xfail here. With `--runxfail` today and on the reference: 17 passed.

## Reproduced claims
- Coverage run: `17 passed in 4.01s`; `app\dao\production_formula_stage.py      10      0      0      0   100%`. Four more default runs: `17 passed in 2.38s`, `17 passed in 2.38s`, `17 passed in 2.62s`, `17 passed in 2.31s`.
- `--runxfail -rf`: `17 passed in 2.31s`; failed: none.
- 15 more runs (5 per plan): 17 passed in every run, no pass card or strict card moved. **No flaky test.** Only non-strict cards move between XFAIL and XPASS, which their markers allow; the notes' sample default line is one heap's result.
- **Mocks:** none. No `try`, no `if`, no broad `pytest.raises` in a test body.

## Traceability
cases 17 · tests 17 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md` and each reason carries the row's title. All sit under `# [claude] <ID>`. `ruff check` passes.

My own script (`rebuild.py`) rebuilt each test's Given, snapshots, When, Then and marker from its card, and the constants, standing rows, builders and helpers from the Conventions, and compared by AST, for all 302 cards of the batch: 0 reports. Selftest (`selftest.py`, 3 seeds): 9306 of 9306 planted mistakes of 81 kinds, in tests, helpers and cards, reported on the right card.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents were live on `marker_test`. Every kill is a plain `N failed` with all tests reached.
- **No DDL.** The one schema question (PBL-G-14) was answered with `SET LOCAL session_replication_role = replica` inside a rolled-back test, which switches foreign-key actions off without a lock.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/production_formula_stage.py tests/unit/dao/test_production_formula_stage.py --timeout 300 --json <scratch>/res/mut_production_formula_stage.json   (through runmut.py, TEMP in scratch)
  6 mutants · 6 killed · 0 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_production_formula_stage.py -q -p no:cacheprovider --cov=app.dao.production_formula_stage --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  17 passed in 4.01s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_production_formula_stage.py -q -p no:cacheprovider --runxfail -rf
  17 passed in 2.31s
repro.py; nonstrict.py (5 runs x 3 plans); thenloc.py                as under Reproduced
drive.py bases | muts | vars --plan default|seq|idx                     as above
propdrive.py (3 plans)                                                  recipes as in the table
rebuild.py; selftest.py 7|21|33                                         302 cards, 0 reports; 9306 of 9306
.venv/Scripts/python.exe -m ruff check <the eleven test files>         All checks passed!
git diff --stat -- app/dao                                              (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add the recipes above; the Givens and Thens are written out.
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-03 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 21 passed · 0 xfail, 0 strict, 0 non-strict (reproduced ✅) · coverage as round 1
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 21 unfaithful** (new and changed cards read by eye; all 21 rebuilt by script)
> Hand variants: 58 · 55 caught by a pass card · every round-1 gap variant fails its new card
> Source commit: e48a092 · Cases revision: 1

Every finding of round 1 is closed. No new rule gap. No test edited, no commit. Nothing parked for the owner.

### New and changed tests
PFS-I-05, PFS-I-06, PFS-I-07, PFS-G-14. Each was read against its card. "Fails" means the variant fails that card on the reference with `--runxfail`, on all three plans.

| Card | Recipe | Fails |
|---|---|---|
| PFS-I-05 | R-1 | `i_r1_ws_ge`, `i_r1_id_ge` |
| PFS-I-06 | R-2 | `i_ov_join`, `i_ov_flag` |
| PFS-G-14 | R-3 | the five `g_w_*` |
| PFS-I-07 | R-3 | the five `i_w_*` |

### Rest of the batch
All 58 variants ran again on the reference, each reaching all 21 tests, on all three plans. Left without a pass card: `g_r4_cap_1000`, `g_r4_cap_101`, `i_r1_one_or_none`. Each is under round 1's "Considered and not listed" (bug path, a cap above the card's own rows, or equivalent); none is a new rule gap.

### Reproduced
- Coverage run: `21 passed in 4.12s`; `['app\\dao\\production_formula_stage.py      10      0      0      0   100%']`. Four more default runs: `21 passed in 2.28s`, `21 passed in 2.34s`, `21 passed in 2.23s`, `21 passed in 2.22s`.
- `--runxfail`: `21 passed in 2.25s []`. Every strict card fails on its card's `Fails today on` line.
- 15 more runs (5 per plan): 21 passed in every run; only non-strict cards move. No flaky test.
- Traceability: cases 21 · tests 21 · unmatched: none · marker mismatches: none. `rebuild.py`: 361 cards over the eleven files, 0 reports (it learned the new `where` name of `mobile_upload_session`). Selftest: 9306 of 9306 planted mistakes, 3 seeds. `ruff check` passes.
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
