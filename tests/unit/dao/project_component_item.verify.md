# Verification — `app/dao/project_component_item.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1, 26 cases). See "Round 2" at the end. The block below is round 1.

> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 21 passed · 4 xfail, 1 strict, 3 non-strict (reproduced ✅) · coverage 100% branch (8 statements, 0 branches, 0 missed)
> Mutation: 5 mutants · 5 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 25 unfaithful** (25 / 25 right)
> Hand variants: 51 · 38 caught by a pass card · 13 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 25 match their cards.
- **Why NEEDS WORK:** 5 of 5 sites killed; one gap for the case designer: side effects.
- No money, stock or order state.

Written by Claude (all 25 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 25. No `project_component_item.local-run.json` exists, so there is no `## Local-coder patterns` section. Script-compared; its differences read by eye (none in this file).

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_component` Side effects: none (skill 1b) | PCI-G-25 checks a pending row only. | the five `g_w_*` pass all 21. | case designer |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv\prop\test_prop_project_component_item.py`, not in the repo. Each passes on today's code (a non-strict xfail recipe may fail today) and on the reference, on all three plans. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card, Side effects | A = entry; B = entry, but `project_component_id C2.id`; `B.qty = 5`, not flushed | `set(ids(result)) == {A.id}`; `session: B in db.dirty`; `session: len(db.dirty) == 1` | pass | the five `g_w_*` |

## Surviving mutants
None. All 5 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 5 mutants with no `-x`: every run reached all 21 pass tests, with no collection or setup error.

## Hand variants
`variants.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv`, on the reference (`order_by(id)` before `offset` / `limit`), with `--runxfail`, on three plans: default, sequential scans off, index and bitmap scans off. Every edit was asserted to apply once and every run reached all 25 tests with no error. Group names: the rule, `w` session side effects, `txt` text compare, `page` paging, `ret` return shape, `ov` parent state.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| g_r1 | 7 | 7 | PCI-G-02, PCI-G-03, PCI-G-04, PCI-G-05, PCI-G-06, PCI-G-07 … | — |
| g_r3 | 4 | 0 | — | `g_r3_none`, `g_r3_desc`, `g_r3_qty`, `g_r3_qty_desc` |
| g_r4 | 4 | 4 | PCI-G-01, PCI-G-02, PCI-G-05, PCI-G-06, PCI-G-16, PCI-G-17 … | — |
| g_r7 | 2 | 2 | PCI-G-01, PCI-G-02, PCI-G-03, PCI-G-04, PCI-G-05, PCI-G-06 … | — |
| g_page | 18 | 15 | PCI-G-01, PCI-G-02, PCI-G-05, PCI-G-06, PCI-G-10, PCI-G-11 … | `g_lim_cap103`, `g_lim_cap104`, `g_lim_cap500` |
| g_ret | 4 | 3 | PCI-G-01, PCI-G-03, PCI-G-04, PCI-G-07, PCI-G-08, PCI-G-09 … | `g_ret_rev` |
| g_w | 12 | 7 | PCI-G-25 | `g_w_expire`, `g_w_expire_post`, `g_w_dirty_refresh`, `g_w_dirty_flush`, `g_w_dirty_expire` |
| **Total** | **51** | **38** |  | **13** |

With the recipes added, 43 of 51 are caught; the rest are below.

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `g_r3_none`, `g_r3_desc`, `g_r3_qty`, `g_r3_qty_desc`, `g_ret_rev` | **Bug path** (BUG-1276). |
| `g_lim_cap103`, `g_lim_cap104`, `g_lim_cap500` | A cap above the card's own 102 rows. |

## xfail tests against the reference
Reference: `order_by(id)` before `offset` / `limit`, swapped in memory. Nothing is written to `app/`. With `--runxfail` on the reference: 25 passed. **The alarm works:** with the markers on, every strict card goes `XPASS(strict)`.

| Card | Marker | Card's Fails line | Seen |
|---|---|---|---|
| PCI-G-12 | non-strict | Then 2 | default: XFAIL 1, XPASS 4; idx: XFAIL 5; seq: XPASS 5; fails on Then 2 when it fails, also under wrong tie orders |
| PCI-G-13 | non-strict | Then 2 | default: XPASS 5; idx: XPASS 5; seq: XPASS 5; fails on Then 2 when it fails, also under wrong tie orders |
| PCI-G-14 | non-strict | Then 2 | default: XFAIL 1, XPASS 4; idx: XFAIL 5; seq: XPASS 5; fails on Then 2 when it fails, also under wrong tie orders |
| PCI-G-15 | strict | Then 2 | fails on Then 2 in 3 of 3 `--runxfail` runs, as the card says |

## Reproduced claims
- Coverage run: `21 passed, 3 xfailed, 1 xpassed in 4.67s`; `app\dao\project_component_item.py       8      0      0      0   100%`. Four more default runs: `21 passed, 1 xfailed, 3 xpassed in 2.63s`, `21 passed, 1 xfailed, 3 xpassed in 2.54s`, `21 passed, 1 xfailed, 3 xpassed in 3.02s`, `21 passed, 1 xfailed, 3 xpassed in 2.71s`.
- `--runxfail -rf`: `1 failed, 24 passed in 2.56s`; failed: PCI-G-15.
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
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/project_component_item.py tests/unit/dao/test_project_component_item.py --timeout 300 --json <scratch>/res/mut_project_component_item.json   (through runmut.py, TEMP in scratch)
  5 mutants · 5 killed · 0 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_project_component_item.py -q -p no:cacheprovider --cov=app.dao.project_component_item --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  21 passed, 3 xfailed, 1 xpassed in 4.67s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_project_component_item.py -q -p no:cacheprovider --runxfail -rf
  1 failed, 24 passed in 2.56s
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
> Tests: 22 passed · 4 xfail, 1 strict, 3 non-strict (reproduced ✅) · coverage as round 1
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 26 unfaithful** (new and changed cards read by eye; all 26 rebuilt by script)
> Hand variants: 51 · 43 caught by a pass card · every round-1 gap variant fails its new card
> Source commit: e48a092 · Cases revision: 1

Every finding of round 1 is closed. No new rule gap. No test edited, no commit. Nothing parked for the owner.

### New and changed tests
PCI-G-26. Each was read against its card. "Fails" means the variant fails that card on the reference with `--runxfail`, on all three plans.

| Card | Recipe | Fails |
|---|---|---|
| PCI-G-26 | R-1 | the five `g_w_*` |

### Rest of the batch
All 51 variants ran again on the reference, each reaching all 26 tests, on all three plans. Left without a pass card: `g_lim_cap103`, `g_lim_cap104`, `g_lim_cap500`, `g_r3_desc`, `g_r3_none`, `g_r3_qty`, `g_r3_qty_desc`, `g_ret_rev`. Each is under round 1's "Considered and not listed" (bug path, a cap above the card's own rows, or equivalent); none is a new rule gap.

### Reproduced
- Coverage run: `22 passed, 3 xfailed, 1 xpassed in 4.60s`; `['app\\dao\\project_component_item.py       8      0      0      0   100%']`. Four more default runs: `22 passed, 1 xfailed, 3 xpassed in 2.60s`, `22 passed, 1 xfailed, 3 xpassed in 2.63s`, `22 passed, 1 xfailed, 3 xpassed in 2.42s`, `22 passed, 1 xfailed, 3 xpassed in 2.37s`.
- `--runxfail`: `1 failed, 25 passed in 2.46s ['pci_g_15']`. Every strict card fails on its card's `Fails today on` line.
- 15 more runs (5 per plan): 22 passed in every run; only non-strict cards move. No flaky test.
- Traceability: cases 26 · tests 26 · unmatched: none · marker mismatches: none. `rebuild.py`: 361 cards over the eleven files, 0 reports (it learned the new `where` name of `mobile_upload_session`). Selftest: 9306 of 9306 planted mistakes, 3 seeds. `ruff check` passes.
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
