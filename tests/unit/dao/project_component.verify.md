# Verification — `app/dao/project_component.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1, 27 cases). See "Round 2" at the end. The block below is round 1.

> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 21 passed · 4 xfail, 1 strict, 3 non-strict (reproduced ✅) · coverage 100% branch (8 statements, 0 branches, 0 missed)
> Mutation: 5 mutants · 5 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 25 unfaithful** (25 / 25 right)
> Hand variants: 55 · 40 caught by a pass card · 15 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 25 match their cards.
- **Why NEEDS WORK:** 5 of 5 sites killed; two gaps for the case designer: side effects, and "case-insensitive" in R3, which this database's collation hides.
- No money, stock or order state.

Written by Claude (all 25 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 25. No `project_component.local-run.json` exists, so there is no `## Local-coder patterns` section. Script-compared; its differences read by eye (none in this file).

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_project` Side effects: none (skill 1b) | PCO-G-25 checks a pending row only. | the five `g_w_*` pass all 21. | case designer |
| 2 | case-missing | R3 [BUG-1275] "name case-insensitive" | `marker_test` sorts with `English_United States.1252`, which is already case-blind, so `order_by(name, id)` passes every card on the reference, PCO-G-12, G-13 and the strict G-15 too. PCO-G-13 puts the lower-case name first, which a case-sensitive sort here also gives; on a `C` collation it would be the other way. | `g_r3_case` passes all 25 with `--runxfail` on the reference, all three plans. | case designer |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv\prop\test_prop_project_component.py`, not in the repo. Each passes on today's code (a non-strict xfail recipe may fail today) and on the reference, on all three plans. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card, Side effects | A = component, `name "Part 1"`; B = component, `name "Part 2"`, but `project_id PJ2.id`; `B.description = "Edited"`, not flushed | `set(ids(result)) == {A.id}`; `session: B in db.dirty`; `session: len(db.dirty) == 1` | pass | the five `g_w_*` |
| R-2 | new card, R3 [BUG-1275], `Author: claude` | A = component, `name "roof"`; B = `"Roof"`; C = `"Wall"`; D = `"wall"`; `db.expire_all()`. One pair fails a case-sensitive sort under either collation | `ids(result) == [A.id, B.id, C.id, D.id]` | xfail BUG-1275 (non-strict) | `g_r3_case`, `g_r3_desc`, `g_r3_id_desc` |

## Surviving mutants
None. All 5 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 5 mutants with no `-x`: every run reached all 21 pass tests, with no collection or setup error.

## Hand variants
`variants.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv`, on the reference (`order_by(func.lower(name), id)` before `offset` / `limit`), with `--runxfail`, on three plans: default, sequential scans off, index and bitmap scans off. Every edit was asserted to apply once and every run reached all 25 tests with no error. Group names: the rule, `w` session side effects, `txt` text compare, `page` paging, `ret` return shape, `ov` parent state.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| g_r1 | 7 | 7 | PCO-G-02, PCO-G-03, PCO-G-04, PCO-G-05, PCO-G-06, PCO-G-07 … | — |
| g_r3 | 7 | 1 | PCO-G-10, PCO-G-11, PCO-G-16, PCO-G-18, PCO-G-19, PCO-G-20 … | `g_r3_none`, `g_r3_desc`, `g_r3_case`, `g_r3_id`, `g_r3_no_tail`, `g_r3_id_desc` |
| g_r4 | 4 | 4 | PCO-G-01, PCO-G-02, PCO-G-05, PCO-G-06, PCO-G-16, PCO-G-17 … | — |
| g_r7 | 3 | 3 | PCO-G-24, PCO-G-25 | — |
| g_page | 18 | 15 | PCO-G-01, PCO-G-02, PCO-G-05, PCO-G-06, PCO-G-10, PCO-G-11 … | `g_lim_cap103`, `g_lim_cap104`, `g_lim_cap500` |
| g_ret | 4 | 3 | PCO-G-01, PCO-G-03, PCO-G-04, PCO-G-07, PCO-G-08, PCO-G-09 … | `g_ret_rev` |
| g_w | 12 | 7 | PCO-G-25 | `g_w_expire`, `g_w_expire_post`, `g_w_dirty_refresh`, `g_w_dirty_flush`, `g_w_dirty_expire` |
| **Total** | **55** | **40** |  | **15** |

With the recipes added, 49 of 55 are caught; the rest are below.

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `g_r3_none`, `g_r3_id`, `g_r3_no_tail`, `g_ret_rev` | **Bug path** (BUG-1275). |
| `g_lim_cap103`, `g_lim_cap104`, `g_lim_cap500` | A cap at or above the card's own 103 rows; `cap100`, `cap101` are caught. |

## xfail tests against the reference
Reference: `order_by(func.lower(name), id)` before `offset` / `limit`, swapped in memory. Nothing is written to `app/`. With `--runxfail` on the reference: 25 passed. **The alarm works:** with the markers on, every strict card goes `XPASS(strict)`.

| Card | Marker | Card's Fails line | Seen |
|---|---|---|---|
| PCO-G-12 | non-strict | Then 2 | default: XFAIL 5; idx: XFAIL 5; seq: XFAIL 5; fails on Then 2 when it fails, also under wrong tie orders |
| PCO-G-13 | non-strict | Then 2 | default: XFAIL 5; idx: XFAIL 5; seq: XPASS 5; fails on Then 2 when it fails, also under wrong tie orders |
| PCO-G-14 | non-strict | Then 2 | default: XFAIL 5; idx: XFAIL 5; seq: XFAIL 5; fails on Then 2 when it fails, also under wrong tie orders |
| PCO-G-15 | strict | Then 2 | fails on Then 2 in 3 of 3 `--runxfail` runs, as the card says |

## Reproduced claims
- Coverage run: `21 passed, 4 xfailed in 4.45s`; `app\dao\project_component.py       8      0      0      0   100%`. Four more default runs: `21 passed, 4 xfailed in 2.60s`, `21 passed, 4 xfailed in 2.53s`, `21 passed, 4 xfailed in 2.93s`, `21 passed, 4 xfailed in 2.50s`.
- `--runxfail -rf`: `4 failed, 21 passed in 2.45s`; failed: PCO-G-12, PCO-G-13, PCO-G-14, PCO-G-15.
- 15 more runs (5 per plan): 21 passed in every run, no pass card or strict card moved. **No flaky test.** Only non-strict cards move between XFAIL and XPASS, which their markers allow; the notes' sample default line is one heap's result.
- **Mocks:** none. No `try`, no `if`, no broad `pytest.raises` in a test body.

## Traceability
cases 25 · tests 25 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md` and each reason carries the row's title. All sit under `# [claude] <ID>`. `ruff check` passes.

My own script (`rebuild.py`) rebuilt each test's Given, snapshots, When, Then and marker from its card, and the constants, standing rows, builders and helpers from the Conventions, and compared by AST, for all 302 cards of the batch: 0 reports. Selftest (`selftest.py`, 3 seeds): 9306 of 9306 planted mistakes of 81 kinds, in tests, helpers and cards, reported on the right card.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents were live on `marker_test`. Every kill is a plain `N failed` with all tests reached.
- **No DDL.** The one schema question (PBL-G-14) was answered with `SET LOCAL session_replication_role = replica` inside a rolled-back test, which switches foreign-key actions off without a lock.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/project_component.py tests/unit/dao/test_project_component.py --timeout 300 --json <scratch>/res/mut_project_component.json   (through runmut.py, TEMP in scratch)
  5 mutants · 5 killed · 0 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_project_component.py -q -p no:cacheprovider --cov=app.dao.project_component --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  21 passed, 4 xfailed in 4.45s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_project_component.py -q -p no:cacheprovider --runxfail -rf
  4 failed, 21 passed in 2.45s
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
> Tests: 22 passed · 5 xfail, 1 strict, 4 non-strict (reproduced ✅) · coverage as round 1
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 27 unfaithful** (new and changed cards read by eye; all 27 rebuilt by script)
> Hand variants: 55 · 45 caught by a pass card · every round-1 gap variant fails its new card
> Source commit: e48a092 · Cases revision: 1

Every finding of round 1 is closed. No new rule gap. No test edited, no commit. Nothing parked for the owner.

### New and changed tests
PCO-G-26, PCO-G-27. Each was read against its card. "Fails" means the variant fails that card on the reference with `--runxfail`, on all three plans.

| Card | Recipe | Fails |
|---|---|---|
| PCO-G-26 | R-1 | the five `g_w_*` |
| PCO-G-27 | R-2, non-strict | `g_r3_case`, on all three plans (it XPASSes today, which its marker allows) |

### Rest of the batch
All 55 variants ran again on the reference, each reaching all 27 tests, on all three plans. Left without a pass card: `g_lim_cap103`, `g_lim_cap104`, `g_lim_cap500`, `g_r3_case`, `g_r3_desc`, `g_r3_id`, `g_r3_id_desc`, `g_r3_no_tail`, `g_r3_none`, `g_ret_rev`. Each is under round 1's "Considered and not listed" (bug path, a cap above the card's own rows, or equivalent); none is a new rule gap.

### Reproduced
- Coverage run: `22 passed, 4 xfailed, 1 xpassed in 4.37s`; `['app\\dao\\project_component.py       8      0      0      0   100%']`. Four more default runs: `22 passed, 4 xfailed, 1 xpassed in 2.42s`, `22 passed, 4 xfailed, 1 xpassed in 2.47s`, `22 passed, 4 xfailed, 1 xpassed in 2.77s`, `22 passed, 4 xfailed, 1 xpassed in 2.49s`.
- `--runxfail`: `4 failed, 23 passed in 2.37s ['pco_g_12', 'pco_g_13', 'pco_g_14', 'pco_g_15']`. Every strict card fails on its card's `Fails today on` line.
- 15 more runs (5 per plan): 22 passed in every run; only non-strict cards move. No flaky test.
- Traceability: cases 27 · tests 27 · unmatched: none · marker mismatches: none. `rebuild.py`: 361 cards over the eleven files, 0 reports (it learned the new `where` name of `mobile_upload_session`). Selftest: 9306 of 9306 planted mistakes, 3 seeds. `ruff check` passes.
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
