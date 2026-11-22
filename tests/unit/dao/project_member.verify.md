# Verification — `app/dao/project_member.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1, 30 cases). See "Round 2" at the end. The block below is round 1.

> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 23 passed · 3 xfail, 1 strict, 2 non-strict (reproduced ✅) · coverage 100% branch (10 statements, 0 branches, 0 missed)
> Mutation: 7 mutants · 7 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 26 unfaithful** (26 / 26 right)
> Hand variants: 64 · 45 caught by a pass card · 19 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 26 match their cards.
- **Why NEEDS WORK:** 7 of 7 sites killed; two gaps for the case designer: the other workspace on both reads, and side effects.
- No money, stock or order state. The reads decide who opens a private project.

Written by Claude (all 26 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 26. No `project_member.local-run.json` exists, so there is no `## Local-coder patterns` section. Script-compared; its differences read by eye (none in this file).

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_project` R1 and `get_by_project_and_user` R3, another workspace | Every other-workspace card asks W2 for W1 rows, so `workspace_id >= workspace_id` leaks nothing. A W2 row asked for in W1 is missing. | `g_r1_ws_ge`, `u_r3_ws_ge` pass all 23. | case designer |
| 2 | case-missing | both readers, Side effects: none (skill 1b) | The writes-nothing cards check a pending row only. | the five `g_w_*` and five `u_w_*` pass all 23. | case designer |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv\prop\test_prop_project_member.py`, not in the repo. Each passes on today's code (a non-strict xfail recipe may fail today) and on the reference, on all three plans. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | two new cards | G: A = member, `assigned_at T10`, but `workspace_id W2.id`; When `get_by_project(project_id=PJ1.id, workspace_id=W1.id)`. GU: the same row; When `get_by_project_and_user(project_id=PJ1.id, user_id=U1.id, workspace_id=W1.id)` | `result == []`; `result is None` | pass | `g_r1_ws_ge`, `u_r3_ws_ge` |
| R-2 | two new cards, Side effects | G: A = member, `assigned_at T10`; B = member, `assigned_at T11`, but `project_id PJ2.id`; `B.assigned_by = U2.id`, not flushed. GU: B = member, `assigned_at T11`, but `user_id U2.id`, edited the same way; When by A's project and U1 | the card's result check; `session: B in db.dirty`; `session: len(db.dirty) == 1` | pass | the ten `*_w_*` |

## Surviving mutants
None. All 7 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 7 mutants with no `-x`: every run reached all 23 pass tests, with no collection or setup error.

## Hand variants
`variants.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv`, on the reference (`order_by(assigned_at, id)` in `get_by_project`), with `--runxfail`, on three plans: default, sequential scans off, index and bitmap scans off. Every edit was asserted to apply once and every run reached all 26 tests with no error. Group names: the rule, `w` session side effects, `txt` text compare, `page` paging, `ret` return shape, `ov` parent state.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| g_r1 | 7 | 6 | PMB-G-02, PMB-G-03, PMB-G-04, PMB-G-05, PMB-G-06, PMB-G-07 … | `g_r1_ws_ge` |
| g_r3 | 5 | 5 | PMB-G-01, PMB-G-08, PMB-G-09, PMB-G-10, PMB-G-16 | — |
| g_r4 | 4 | 0 | — | `g_r4_no_tail`, `g_r4_id_desc`, `g_r4_user_tail`, `g_r4_user_desc_tail` |
| g_r5 | 2 | 2 | PMB-G-14, PMB-G-17 | — |
| g_r6 | 1 | 1 | PMB-G-15, PMB-G-17 | — |
| g_r7 | 3 | 1 | PMB-G-16 | `g_r7_cap_101`, `g_r7_cap_1000` |
| g_ret | 4 | 4 | PMB-G-01, PMB-G-03, PMB-G-04, PMB-G-05, PMB-G-06, PMB-G-07 … | — |
| g_w | 12 | 7 | PMB-G-17 | `g_w_expire`, `g_w_expire_post`, `g_w_dirty_refresh`, `g_w_dirty_flush`, `g_w_dirty_expire` |
| u_r1 | 8 | 7 | PMB-GU-01, PMB-GU-02, PMB-GU-03, PMB-GU-04, PMB-GU-05, PMB-GU-06 | `u_r1_one_or_none` |
| u_r3 | 3 | 2 | PMB-GU-06 | `u_r3_ws_ge` |
| u_r4 | 2 | 2 | PMB-GU-07, PMB-GU-08, PMB-GU-09 | — |
| u_ret | 1 | 1 | PMB-GU-01, PMB-GU-02, PMB-GU-07, PMB-GU-08, PMB-GU-09 | — |
| u_w | 12 | 7 | PMB-GU-09 | `u_w_expire`, `u_w_expire_post`, `u_w_dirty_refresh`, `u_w_dirty_flush`, `u_w_dirty_expire` |
| **Total** | **64** | **45** |  | **19** |

With the recipes added, 57 of 64 are caught; the rest are below.

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `g_r4_no_tail`, `g_r4_id_desc`, `g_r4_user_tail`, `g_r4_user_desc_tail` | **Bug path** (BUG-1274). |
| `g_r7_cap_101`, `g_r7_cap_1000` | A cap above the card's own 101 rows. |
| `u_r1_one_or_none` | **Equivalent:** `uq_project_member_project_user`. |

## xfail tests against the reference
Reference: `order_by(assigned_at, id)` in `get_by_project`, swapped in memory. Nothing is written to `app/`. With `--runxfail` on the reference: 26 passed. **The alarm works:** with the markers on, every strict card goes `XPASS(strict)`.

| Card | Marker | Card's Fails line | Seen |
|---|---|---|---|
| PMB-G-11 | non-strict | Then 2 | default: XFAIL 5; idx: XFAIL 5; seq: XPASS 5; fails on Then 2 when it fails, also under wrong tie orders |
| PMB-G-12 | non-strict | Then 2 | default: XPASS 5; idx: XPASS 5; seq: XPASS 5; fails on Then 2 when it fails, also under wrong tie orders |
| PMB-G-13 | strict | Then 4 | fails on Then 4 in 3 of 3 `--runxfail` runs, as the card says |

## Reproduced claims
- Coverage run: `23 passed, 2 xfailed, 1 xpassed in 5.39s`; `app\dao\project_member.py      10      0      0      0   100%`. Four more default runs: `23 passed, 2 xfailed, 1 xpassed in 2.80s`, `23 passed, 2 xfailed, 1 xpassed in 2.99s`, `23 passed, 2 xfailed, 1 xpassed in 3.18s`, `23 passed, 2 xfailed, 1 xpassed in 2.78s`.
- `--runxfail -rf`: `2 failed, 24 passed in 2.79s`; failed: PMB-G-11, PMB-G-13.
- 15 more runs (5 per plan): 23 passed in every run, no pass card or strict card moved. **No flaky test.** Only non-strict cards move between XFAIL and XPASS, which their markers allow; the notes' sample default line is one heap's result.
- **Mocks:** none. No `try`, no `if`, no broad `pytest.raises` in a test body.

## Traceability
cases 26 · tests 26 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md` and each reason carries the row's title. All sit under `# [claude] <ID>`. `ruff check` passes.

My own script (`rebuild.py`) rebuilt each test's Given, snapshots, When, Then and marker from its card, and the constants, standing rows, builders and helpers from the Conventions, and compared by AST, for all 302 cards of the batch: 0 reports. Selftest (`selftest.py`, 3 seeds): 9306 of 9306 planted mistakes of 81 kinds, in tests, helpers and cards, reported on the right card.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents were live on `marker_test`. Every kill is a plain `N failed` with all tests reached.
- **No DDL.** The one schema question (PBL-G-14) was answered with `SET LOCAL session_replication_role = replica` inside a rolled-back test, which switches foreign-key actions off without a lock.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/project_member.py tests/unit/dao/test_project_member.py --timeout 300 --json <scratch>/res/mut_project_member.json   (through runmut.py, TEMP in scratch)
  7 mutants · 7 killed · 0 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_project_member.py -q -p no:cacheprovider --cov=app.dao.project_member --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  23 passed, 2 xfailed, 1 xpassed in 5.39s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_project_member.py -q -p no:cacheprovider --runxfail -rf
  2 failed, 24 passed in 2.79s
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
> Tests: 27 passed · 3 xfail, 1 strict, 2 non-strict (reproduced ✅) · coverage as round 1
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 30 unfaithful** (new and changed cards read by eye; all 30 rebuilt by script)
> Hand variants: 64 · 57 caught by a pass card · every round-1 gap variant fails its new card
> Source commit: e48a092 · Cases revision: 1

Every finding of round 1 is closed. No new rule gap. No test edited, no commit. Nothing parked for the owner.

### New and changed tests
PMB-G-18, PMB-G-19, PMB-GU-10, PMB-GU-11. Each was read against its card. "Fails" means the variant fails that card on the reference with `--runxfail`, on all three plans.

| Card | Recipe | Fails |
|---|---|---|
| PMB-G-18 | R-1 | `g_r1_ws_ge` |
| PMB-GU-10 | R-1 | `u_r3_ws_ge` |
| PMB-G-19 | R-2 | the five `g_w_*` |
| PMB-GU-11 | R-2 | the five `u_w_*` |

### Rest of the batch
All 64 variants ran again on the reference, each reaching all 30 tests, on all three plans. Left without a pass card: `g_r4_id_desc`, `g_r4_no_tail`, `g_r4_user_desc_tail`, `g_r4_user_tail`, `g_r7_cap_1000`, `g_r7_cap_101`, `u_r1_one_or_none`. Each is under round 1's "Considered and not listed" (bug path, a cap above the card's own rows, or equivalent); none is a new rule gap.

### Reproduced
- Coverage run: `27 passed, 2 xfailed, 1 xpassed in 5.50s`; `['app\\dao\\project_member.py      10      0      0      0   100%']`. Four more default runs: `27 passed, 2 xfailed, 1 xpassed in 2.86s`, `27 passed, 2 xfailed, 1 xpassed in 2.81s`, `27 passed, 2 xfailed, 1 xpassed in 2.66s`, `27 passed, 2 xfailed, 1 xpassed in 2.61s`.
- `--runxfail`: `2 failed, 28 passed in 2.81s ['pmb_g_11', 'pmb_g_13']`. Every strict card fails on its card's `Fails today on` line.
- 15 more runs (5 per plan): 27 passed in every run; only non-strict cards move. No flaky test.
- Traceability: cases 30 · tests 30 · unmatched: none · marker mismatches: none. `rebuild.py`: 361 cards over the eleven files, 0 reports (it learned the new `where` name of `mobile_upload_session`). Selftest: 9306 of 9306 planted mistakes, 3 seeds. `ruff check` passes.
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
