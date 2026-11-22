# Verification — `app/dao/sales_delivery_item.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1, 17 cases). See "Round 2" at the end. The block below is round 1.

> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 13 passed · 3 xfail, 1 strict, 2 non-strict (reproduced ✅) · coverage 100% branch (8 statements, 0 branches, 0 missed)
> Mutation: 3 mutants · 3 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 16 unfaithful** (16 / 16 right)
> Hand variants: 35 · 23 caught by a pass card · 12 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 16 match their cards (script; differences read by eye: none).
- **Why NEEDS WORK:** 3 of 3 sites killed; one rule gap, the side-effects shape, for the case designer.
- No money. The reader feeds stock posting at delivery completion; no gap here touches stock.

Written by Claude (all 16 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 16. No `sales_delivery_item.local-run.json` exists, so there is no `## Local-coder patterns` section. Script-compared; its differences read by eye (none in this file).

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_delivery` Side effects: none (skill 1b) | SDI-G-16 checks a pending row only; a read that drops or flushes the caller's unflushed edit passes. | the five `g_w_*` (`expire`, `expire_post`, `dirty_refresh`, `dirty_flush`, `dirty_expire`) pass all 13 on all three plans. | case designer |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv\prop\test_prop_sales_delivery_item.py`, not in the repo. Each passes on today's code (a non-strict xfail recipe may fail today) and on the reference, on all three plans. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card, Side effects | A = line; B = line, but `delivery_id D2.id`; `B.notes = "Edited"`, not flushed. When `get_by_delivery(delivery_id=D1.id, workspace_id=W1.id)` | `set(ids(result)) == {A.id}`; `session: B in db.dirty`; `session: len(db.dirty) == 1` | pass | the five `g_w_*` |

## Surviving mutants
None. All 3 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 3 mutants with no `-x`: every run reached all 13 pass tests, with no collection or setup error.

## Hand variants
`variants.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv`, on the reference (`order_by(id)` in `get_by_delivery`), with `--runxfail`, on three plans: default, sequential scans off, index and bitmap scans off. Every edit was asserted to apply once and every run reached all 16 tests with no error. Group names: the rule, `w` session side effects, `txt` text compare, `page` paging, `ret` return shape, `ov` parent state.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| g_r1 | 8 | 8 | SDI-G-02, SDI-G-03, SDI-G-04, SDI-G-05, SDI-G-06, SDI-G-07 … | — |
| g_r3 | 4 | 0 | — | `g_r3_none`, `g_r3_desc`, `g_r3_notes`, `g_r3_qty` |
| g_r5 | 1 | 1 | SDI-G-15 | — |
| g_ov | 3 | 3 | SDI-G-16 | — |
| g_r4 | 3 | 1 | SDI-G-14 | `g_r4_cap_101`, `g_r4_cap_1000` |
| g_ret | 4 | 3 | SDI-G-01, SDI-G-03, SDI-G-04, SDI-G-07, SDI-G-08, SDI-G-09 … | `g_ret_rev` |
| g_w | 12 | 7 | SDI-G-10, SDI-G-16 | `g_w_expire`, `g_w_expire_post`, `g_w_dirty_refresh`, `g_w_dirty_flush`, `g_w_dirty_expire` |
| **Total** | **35** | **23** |  | **12** |

With the recipes added, 28 of 35 are caught; the rest are below.

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `g_r3_none`, `g_r3_desc`, `g_r3_notes`, `g_r3_qty`, `g_ret_rev` | **Bug path** (BUG-1271): passing cards compare sets by design; each fails SDI-G-11, G-12 or the strict G-13. |
| `g_r4_cap_101`, `g_r4_cap_1000` | A cap above the card's own 101 rows; `g_r4_cap_100` is caught. |

## xfail tests against the reference
Reference: `order_by(id)` in `get_by_delivery`, swapped in memory. Nothing is written to `app/`. With `--runxfail` on the reference: 16 passed. **The alarm works:** with the markers on, every strict card goes `XPASS(strict)`.

| Card | Marker | Card's Fails line | Seen |
|---|---|---|---|
| SDI-G-11 | non-strict | Then 2 | default: XFAIL 3, XPASS 2; idx: XFAIL 5; seq: XPASS 5; fails on Then 2 when it fails, also under wrong tie orders |
| SDI-G-12 | non-strict | Then 2 | default: XPASS 5; idx: XPASS 5; seq: XPASS 5; fails on Then 2 when it fails, also under wrong tie orders |
| SDI-G-13 | strict | Then 2 | fails on Then 2 in 3 of 3 `--runxfail` runs, as the card says |

## Reproduced claims
- Coverage run: `13 passed, 1 xfailed, 2 xpassed in 4.66s`; `app\dao\sales_delivery_item.py       8      0      0      0   100%`. Four more default runs: `13 passed, 1 xfailed, 2 xpassed in 2.61s`, `13 passed, 1 xfailed, 2 xpassed in 2.60s`, `13 passed, 1 xfailed, 2 xpassed in 2.66s`, `13 passed, 2 xfailed, 1 xpassed in 2.53s`.
- `--runxfail -rf`: `2 failed, 14 passed in 2.68s`; failed: SDI-G-11, SDI-G-13.
- 15 more runs (5 per plan): 13 passed in every run, no pass card or strict card moved. **No flaky test.** Only non-strict cards move between XFAIL and XPASS, which their markers allow; the notes' sample default line is one heap's result.
- **Mocks:** none. No `try`, no `if`, no broad `pytest.raises` in a test body.

## Traceability
cases 16 · tests 16 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md` and each reason carries the row's title. All sit under `# [claude] <ID>`. `ruff check` passes.

My own script (`rebuild.py`) rebuilt each test's Given, snapshots, When, Then and marker from its card, and the constants, standing rows, builders and helpers from the Conventions, and compared by AST, for all 302 cards of the batch: 0 reports. Selftest (`selftest.py`, 3 seeds): 9306 of 9306 planted mistakes of 81 kinds, in tests, helpers and cards, reported on the right card.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents were live on `marker_test`. Every kill is a plain `N failed` with all tests reached.
- **No DDL.** The one schema question (PBL-G-14) was answered with `SET LOCAL session_replication_role = replica` inside a rolled-back test, which switches foreign-key actions off without a lock.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/sales_delivery_item.py tests/unit/dao/test_sales_delivery_item.py --timeout 300 --json <scratch>/res/mut_sales_delivery_item.json   (through runmut.py, TEMP in scratch)
  3 mutants · 3 killed · 0 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_sales_delivery_item.py -q -p no:cacheprovider --cov=app.dao.sales_delivery_item --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  13 passed, 1 xfailed, 2 xpassed in 4.66s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_sales_delivery_item.py -q -p no:cacheprovider --runxfail -rf
  2 failed, 14 passed in 2.68s
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
> Tests: 14 passed · 3 xfail, 1 strict, 2 non-strict (reproduced ✅) · coverage as round 1
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 17 unfaithful** (new and changed cards read by eye; all 17 rebuilt by script)
> Hand variants: 35 · 28 caught by a pass card · every round-1 gap variant fails its new card
> Source commit: e48a092 · Cases revision: 1

Every finding of round 1 is closed. No new rule gap. No test edited, no commit. Nothing parked for the owner.

### New and changed tests
SDI-G-17. Each was read against its card. "Fails" means the variant fails that card on the reference with `--runxfail`, on all three plans.

| Card | Recipe | Fails |
|---|---|---|
| SDI-G-17 | R-1 | the five `g_w_*` |

### Rest of the batch
All 35 variants ran again on the reference, each reaching all 17 tests, on all three plans. Left without a pass card: `g_r3_desc`, `g_r3_none`, `g_r3_notes`, `g_r3_qty`, `g_r4_cap_1000`, `g_r4_cap_101`, `g_ret_rev`. Each is under round 1's "Considered and not listed" (bug path, a cap above the card's own rows, or equivalent); none is a new rule gap.

### Reproduced
- Coverage run: `14 passed, 2 xfailed, 1 xpassed in 4.36s`; `['app\\dao\\sales_delivery_item.py       8      0      0      0   100%']`. Four more default runs: `14 passed, 2 xfailed, 1 xpassed in 2.38s`, `14 passed, 2 xfailed, 1 xpassed in 2.47s`, `14 passed, 2 xfailed, 1 xpassed in 2.37s`, `14 passed, 1 xfailed, 2 xpassed in 2.52s`.
- `--runxfail`: `1 failed, 16 passed in 2.40s ['sdi_g_13']`. Every strict card fails on its card's `Fails today on` line.
- 15 more runs (5 per plan): 14 passed in every run; only non-strict cards move. No flaky test.
- Traceability: cases 17 · tests 17 · unmatched: none · marker mismatches: none. `rebuild.py`: 361 cards over the eleven files, 0 reports (it learned the new `where` name of `mobile_upload_session`). Selftest: 9306 of 9306 planted mistakes, 3 seeds. `ruff check` passes.
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
