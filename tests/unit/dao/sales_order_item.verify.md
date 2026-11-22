# Verification — `app/dao/sales_order_item.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1, 19 cases). See "Round 2" at the end. The block below is round 1.

> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 14 passed · 3 xfail, 1 strict, 2 non-strict (reproduced ✅) · coverage 90% (10 statements, 1 missed: line 40)
> Mutation: 8 mutants · 3 killed · 5 survived → score 100% (after excluding 0 equivalent, 5 dead, 0 bug-path)
> Fidelity: **0 of 17 unfaithful** (17 / 17 right)
> Hand variants: 37 · 26 caught by a pass card · 11 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 17 match their cards.
- **Why NEEDS WORK:** 3 of 3 live sites killed (the 5 survivors sit in dead `get_by_item`), but two rule gaps for the case designer: side effects, and a wrong sort key that passes every card once BUG-1270 is fixed.
- No money computed here. The lines feed delivery and return checks (order workflow); no gap here changes which lines are returned.
- **Ruling on the executor's point:** SOI-G-13: both sentences, the card's and the executor's, describe one plan (Finding 3).

Written by Claude (all 17 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 17. No `sales_order_item.local-run.json` exists, so there is no `## Local-coder patterns` section. Script-compared; its differences read by eye (none in this file).

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_sales_order` Side effects: none (skill 1b) | SOI-G-17 checks a pending row only. | the five `g_w_*` pass all 14 on all three plans. | case designer |
| 2 | case-missing | R3 [BUG-1270], skill 1b sort keys | Every tied card gives all lines one `unit_price` and `line_total`, so `order_by(unit_price, id)` passes every card on the reference, the strict SQL card SOI-G-14 too (`".id" in order_part`). | `g_r3_price` passes all 17 with `--runxfail` on the reference, all three plans. | case designer |
| 3 | prose | SOI-G-13 `Fails today on` | Ruling on the executor's point: the card says physical order usually gives the intended result; the executor saw it fail 5 of 5 because of the `items` join. Mine: XFAIL 5/5 on the default and index-off plans, XPASS 5/5 with sequential scans off, and XPASS in my earlier default runs. Both sentences describe one plan. Marker and assertion are right. | `res/nonstrict.json` | case designer (one parenthesis) |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv\prop\test_prop_sales_order_item.py`, not in the repo. Each passes on today's code (a non-strict xfail recipe may fail today) and on the reference, on all three plans. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card, Side effects | A = line; B = line, but `sales_order_id SO2.id`; `B.description = "Edited"`, not flushed. When `get_by_sales_order(sales_order_id=SO1.id, workspace_id=W1.id)` | `set(ids(result)) == {A.id}`; `session: B in db.dirty`; `session: len(db.dirty) == 1` | pass | the five `g_w_*` |
| R-2 | new card, R3 [BUG-1270], `Author: claude` | A = line, but `unit_price Decimal("9.00")`, `line_total Decimal("9.00")`; B = line, but `unit_price Decimal("1.00")`, `line_total Decimal("1.00")`; `db.expire_all()` | `ids(result) == [A.id, B.id]` | xfail BUG-1270 (non-strict) | `g_r3_price`; fails today on the index-off plan |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | L36 | `skip: int = 0` → 1 | dead | All five are in `get_by_item`, which the spec lists as dead code (Q1, `docs/testing/dead-code-removal-checklist.md`). | — |
| 2 | L37 | `limit: int = 100` → 101 | dead | as #1 | — |
| 3 | L40 | `return` → `return None` | dead | as #1 | — |
| 4 | L43 | `item_id ==` → `!=` | dead | as #1 | — |
| 5 | L44 | `workspace_id ==` → `!=` | dead | as #1 | — |

**Guard.** My own driver re-ran each of the 8 mutants with no `-x`: every run reached all 14 pass tests, with no collection or setup error, and the same five survived.

## Hand variants
`variants.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv`, on the reference (`order_by(id)` in `get_by_sales_order`), with `--runxfail`, on three plans: default, sequential scans off, index and bitmap scans off. Every edit was asserted to apply once and every run reached all 17 tests with no error. Group names: the rule, `w` session side effects, `txt` text compare, `page` paging, `ret` return shape, `ov` parent state.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| g_r1 | 10 | 10 | SOI-G-01, SOI-G-02, SOI-G-03, SOI-G-04, SOI-G-05, SOI-G-06 … | — |
| g_r3 | 4 | 0 | — | `g_r3_none`, `g_r3_desc`, `g_r3_descr`, `g_r3_price` |
| g_r5 | 2 | 2 | SOI-G-01, SOI-G-02, SOI-G-05, SOI-G-06, SOI-G-10, SOI-G-11 … | — |
| g_r6 | 1 | 1 | SOI-G-16 | — |
| g_ov | 1 | 1 | SOI-G-17 | — |
| g_r4 | 3 | 2 | SOI-G-15 | `g_r4_cap_1000` |
| g_ret | 4 | 3 | SOI-G-01, SOI-G-03, SOI-G-04, SOI-G-07, SOI-G-08, SOI-G-09 … | `g_ret_rev` |
| g_w | 12 | 7 | SOI-G-10, SOI-G-17 | `g_w_expire`, `g_w_expire_post`, `g_w_dirty_refresh`, `g_w_dirty_flush`, `g_w_dirty_expire` |
| **Total** | **37** | **26** |  | **11** |

With the recipes added, 35 of 37 are caught; the rest are below.

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `g_r3_none`, `g_r3_desc`, `g_r3_descr`, `g_ret_rev` | **Bug path** (BUG-1270): each fails SOI-G-12, G-13 or the strict G-14. |
| `g_r4_cap_1000` | A cap above the card's own 103 rows; `g_r4_cap_100` and `_101` are caught. |

## xfail tests against the reference
Reference: `order_by(id)` in `get_by_sales_order`, swapped in memory. Nothing is written to `app/`. With `--runxfail` on the reference: 17 passed. **The alarm works:** with the markers on, every strict card goes `XPASS(strict)`.

| Card | Marker | Card's Fails line | Seen |
|---|---|---|---|
| SOI-G-12 | non-strict | Then 2 | default: XFAIL 5; idx: XFAIL 5; seq: XPASS 5; fails on Then 2 when it fails, also under wrong tie orders |
| SOI-G-13 | non-strict | Then 2 | default: XFAIL 5; idx: XFAIL 5; seq: XPASS 5; fails on Then 2 when it fails, also under wrong tie orders |
| SOI-G-14 | strict | Then 2 | fails on Then 2 in 3 of 3 `--runxfail` runs, as the card says |

## Reproduced claims
- Coverage run: `14 passed, 1 xfailed, 2 xpassed in 4.71s`; `app\dao\sales_order_item.py      10      1      0      0    90%   40`. Four more default runs: `14 passed, 1 xfailed, 2 xpassed in 2.74s`, `14 passed, 1 xfailed, 2 xpassed in 2.71s`, `14 passed, 1 xfailed, 2 xpassed in 2.64s`, `14 passed, 1 xfailed, 2 xpassed in 2.51s`.
- `--runxfail -rf`: `1 failed, 16 passed in 2.69s`; failed: SOI-G-14.
- 15 more runs (5 per plan): 14 passed in every run, no pass card or strict card moved. **No flaky test.** Only non-strict cards move between XFAIL and XPASS, which their markers allow; the notes' sample default line is one heap's result.
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
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/sales_order_item.py tests/unit/dao/test_sales_order_item.py --timeout 300 --json <scratch>/res/mut_sales_order_item.json   (through runmut.py, TEMP in scratch)
  8 mutants · 3 killed · 5 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_sales_order_item.py -q -p no:cacheprovider --cov=app.dao.sales_order_item --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  14 passed, 1 xfailed, 2 xpassed in 4.71s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_sales_order_item.py -q -p no:cacheprovider --runxfail -rf
  1 failed, 16 passed in 2.69s
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
> Tests: 15 passed · 4 xfail, 1 strict, 3 non-strict (reproduced ✅) · coverage as round 1
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 19 unfaithful** (new and changed cards read by eye; all 19 rebuilt by script)
> Hand variants: 37 · 31 caught by a pass card · every round-1 gap variant fails its new card
> Source commit: e48a092 · Cases revision: 1

Every finding of round 1 is closed. No new rule gap. No test edited, no commit. Nothing parked for the owner.

### New and changed tests
SOI-G-18, SOI-G-19; SOI-G-13's parenthesis. Each was read against its card. "Fails" means the variant fails that card on the reference with `--runxfail`, on all three plans.

| Card | Recipe | Fails |
|---|---|---|
| SOI-G-18 | R-1 | the five `g_w_*` |
| SOI-G-19 | R-2, non-strict | `g_r3_price`, on all three plans |

### Rest of the batch
All 37 variants ran again on the reference, each reaching all 19 tests, on all three plans. Left without a pass card: `g_r3_desc`, `g_r3_descr`, `g_r3_none`, `g_r3_price`, `g_r4_cap_1000`, `g_ret_rev`. Each is under round 1's "Considered and not listed" (bug path, a cap above the card's own rows, or equivalent); none is a new rule gap.

### Reproduced
- Coverage run: `15 passed, 4 xfailed in 4.58s`; `['app\\dao\\sales_order_item.py      10      1      0      0    90%   40']`. Four more default runs: `15 passed, 4 xfailed in 2.42s`, `15 passed, 4 xfailed in 2.39s`, `15 passed, 4 xfailed in 2.49s`, `15 passed, 1 xfailed, 3 xpassed in 2.52s`.
- `--runxfail`: `1 failed, 18 passed in 2.50s ['soi_g_14']`. Every strict card fails on its card's `Fails today on` line.
- 15 more runs (5 per plan): 15 passed in every run; only non-strict cards move. No flaky test.
- Traceability: cases 19 · tests 19 · unmatched: none · marker mismatches: none. `rebuild.py`: 361 cards over the eleven files, 0 reports (it learned the new `where` name of `mobile_upload_session`). Selftest: 9306 of 9306 planted mistakes, 3 seeds. `ruff check` passes.
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
