# Verification — `app/dao/production_formula.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1). See "Round 2" at the end. The block below is round 1.

> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 73 passed · 30 xfail (19 strict, 11 non-strict) (reproduced ✅) · coverage 100% branch (16 statements)
> Mutation: 22 mutants · 22 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 103 unfaithful** (script against every card; the differences and the helpers read by eye). 2 nits.
> Hand variants: 100 · 68 caught by a pass card · 26 bug path · 6 others: 3 rule gaps (4 variants) in Findings, 2 under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** My comparator found no unfaithful test. I read its only differences, two unused `newest` lines, and the fixtures and helpers by eye. Both standing workspaces and the `formula` builder match the Conventions.
- **Why NEEDS WORK:** 3 rule gaps, for the case designer:
  - `get_default_formulas` has no card asking W2 for a W1 row.
  - The BUG-1316 compare has no card with a space *inside* the code.
  - Neither paged list has a card with another workspace's row ahead of the page.
- **Unordered queries have their alarms:**
  - `get_by_workspace` → GW-05
  - `get_active_by_workspace` → GA-08
  - `get_default_formulas` → GD-07

  These are all strict SQL cards. Non-strict cards that pass today on every plan, by row order: GA-10, GA-11 and GD-09 (GA-12 and GD-10 on the sequential plan). `get_by_formula_code` needs no order once BUG-1316 makes the code unique (R4).

Written by Claude (all 103 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 103. No local-run file exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_default_formulas` R1 "Rows of another workspace never appear" (step 1b, both sides) | GD-03 asks W1 while the default is in W2. No card asks W2 while the default is in W1, so a `<=` on `workspace_id` passes. | `gd_r1_le` passes all 103 on all three plans. | **case designer** |
| 2 | case-missing | `get_by_formula_code` R3 [BUG-1316] "trimmed and case-insensitive" | Every card has spaces only at the ends. A compare that drops *all* spaces (`replace(' ', '')`) passes every card, also on the reference. | `gc_r3_nospace` passes all 103 on all three plans. | **case designer** |
| 3 | case-missing | `get_by_workspace` R1, `get_active_by_workspace` R1 (step 1b "filter before paging") | No card has another workspace's row ahead of the skipped row. | `gw_r1_ws_after_page`, `ga_r1_ws_after_page` pass all 103 on all three plans. | **case designer** |
| 4 | nit, not unfaithful | PFM-GW-08, PFM-GA-15 Given 2 | `newest` is not built. No Then line uses it. | `fid.py` difference. | executor (optional) |

No fidelity finding.

### Scratch cards that close the gaps
These are in `...\prodv\prop\test_prop_production_formula.py`. Each one passes on today's code and on my reference, on three plans, and fails under its variant.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card, GD R1 | A = formula, `formula_code "FM-A"`, `name "Alpha"`, `is_default True`. When `dao.get_default_formulas(db, workspace_id=W2.id)` | `result == []` | pass | `gd_r1_le` |
| R-2 | new card, GC R3 | A = formula, `formula_code "YARN-1"`, `name "Yarn"`. When `dao.get_by_formula_code(db, formula_code="YARN -1", workspace_id=W1.id)` | `result is None` | pass (exact today; still no match after the fix) | `gc_r3_nospace` |
| R-3a | new card, GW R1 | Z = formula, `formula_code "FM-Z"`, `name "Alpha"`, `workspace_id W2.id`; A = formula, `formula_code "FM-A"`, `name "Bravo"`; B = formula, `formula_code "FM-B"`, `name "Charlie"`. When `dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)` | `ids(result) == [B.id]` | pass | `gw_r1_ws_after_page` |
| R-3b | new card, GA R1 | as R-3a. When `dao.get_active_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)` | `ids(result) == [B.id]` | pass | `ga_r1_ws_after_page` |

## Surviving mutants
None. All 22 kills end in a plain `N failed`.

**Guard.** My driver ran each mutant again without `-x`. Every run reached all 73 pass tests, and the kills were the same as `mutate.py`'s.

## Hand variants
Run on my reference with `--runxfail`. The candidates were run again on the sequential-off and index-off plans, with no change. Each edit applied exactly once, and every run reached all 103 tests.

- **The variant runs leave out the inherited BUG-1316 index cards.** They ran without my reference index, so the six cards INH-03 to INH-06, INH-09 and INH-10 fail on the reference itself. They are excluded from every variant count.
- **Those six were checked separately,** with the index: see the xfail section.

| Group | Variants | Pass card | Others |
|---|---|---|---|
| gw (workspace, inactive kept, order, paging, writes) | 22 | 17 | 3 bug path (GW-05 to GW-07); `gw_r1_ws_after_page`; `gw_pg_cap101` |
| gc (code lookup: workspace, exact / trim / case variants, inactive found, writes) | 19 | 13 | 5 bug path (GC-11 to GC-14); `gc_r3_nospace` |
| ga (active, order, paging, writes) | 28 | 17 | 9 bug path; `ga_r1_ws_after_page`; `ga_pg_cap101` |
| gd (defaults, active, AND, no cap, order, writes) | 21 | 11 | 9 bug path; `gd_r1_le` |
| gi (by id) | 10 | 10 | — |
| **Total** | **100** | **68** | **32** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `gw_pg_cap101`, `ga_pg_cap101` | A cap above the cards' own 101 rows. The cap100 variants are caught. |

## xfail tests against the reference
My reference, `ref/production_formula.py`, does four things:
- orders by `id`, and by `lower(name), id`;
- compares `lower(trim(code))` on both sides;
- trims strings in the schemas (BUG-1317);
- for the inherited cards, runs `CREATE UNIQUE INDEX ... (workspace_id, lower(trim(formula_code)))` inside each test's own rolled-back transaction. That was one short run; nothing persisted.

Results:
- With `--runxfail`: **103 passed**.
- **The alarm works:** with the markers on, `19 failed, 73 passed, 11 xpassed`, and the strict cards report `XPASS(strict)`.
- On today's code every strict card fails on its "Fails today on" line on all three plans.

## Reproduced claims
- **The notes' Result line holds:** `73 passed, 27 xfailed, 3 xpassed` in 4 of 4 default runs. No test is flaky.
- **Mocks:** none.
- **`ruff check`** passes.

## Traceability
cases 103 · tests 103 · unmatched: none · marker mismatches: none.
- BUG-100 and BUG-1314 to BUG-1317 are in `bugs.md`.
- My comparator found 2 nits. Its selftest caught 1057 of 1057 planted mistakes.

## Commands run
```
pytest --cov=app.dao.production_formula --cov-branch                73 passed, 27 xfailed, 3 xpassed; 100%
tests/unit/_tools/mutate.py app/dao/production_formula.py tests/unit/dao/test_production_formula.py --timeout 300 --json <scratch>/res/mut_production_formula.json
  22 mutants · 22 killed
xcheck.py; vdrive.py muts / vars (+ seq, idx); drive.py --ddl (reference index); propdrive.py; fid.py; selftest.py
git diff --stat -- app/dao                                          (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\prodv\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add R-1, R-2, R-3a and R-3b.
2. **Executor,** after step 1: implement them, then send the module back for re-verification.


## Round 2 — 2026-11-03 (Revision 1 and 1b, narrow)

> **Verdict:** PASS
> Tests: 77 passed, 27 xfailed, 3 xpassed (reproduced ✅, 3 of 3 runs, no flaky test) · 107 cards
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 107 unfaithful** (new and changed tests read by eye against their cards; all 107 rebuilt by `fid.py`, 0 differences)
> Source commit: e48a092 · Cases revision: 1 and 1b; spec APPROVED

Every round 1 finding is closed. I found no new rule gap. No test was edited in this round, and nothing was committed.

- **New / changed cards, read by eye:** PFM-GD-13 (R-1), PFM-GC-18 (R-2), PFM-GW-21 and GA-26 (R-3a, R-3b; Revision 1b `limit=2` with a set check); GW-08, GA-15 drop the unused `newest`. Each matches its card: Given, When, every Then, and the marker.
- **Gap variants against their cards**, on my reference with `--runxfail`, on the default, sequential-off and index-off plans: `gd_r1_le` fails GD-13, `gc_r3_nospace` fails GC-18, `gw_` and `ga_r1_ws_after_page` fail GW-21 and GA-26. Each fails its named card on all three plans.
- **Reference:** `--runxfail` gives 107 passed (with my reference index for the INH cards). With markers: 19 failed (strict XPASS), 77 passed, 11 xpassed. The alarms still go off.
- **Today, `--runxfail`:** every strict xfail fails on its card's line, on three plans.
- **My round 1 recipes for the unordered lists were order-fragile:** they named one row of a query with no `ORDER BY`. Revision 1b's `limit=2` cards fix that, and still fail the after-`LIMIT` variant on all three plans.
- **Parked for the owner:** nothing.

### Commands run
```
fid.py production_formula                                     107 cards, 0 differences
r2.py (reference ±markers; gap variants × 3 plans; today --runxfail × 3 plans; 3 plain runs)
ruff check <the seven test files>               All checks passed!
git diff --stat -- app/dao                      (empty)
```
