# Verification — `app/dao/production_formula_item.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1). See "Round 2" at the end. The block below is round 1.

> **Verdict:** NEEDS WORK — only the case designer has work: one card. No test is wrong.
> Tests: 55 passed · 6 xfail (2 strict, 4 non-strict) (reproduced ✅) · coverage 100% branch (12 statements)
> Mutation: 10 mutants · 10 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 61 unfaithful** (my script checked every card; I read the helpers by eye)
> Hand variants: 62 · 51 caught by a pass card · 8 bug path · 3 others: 1 rule gap in Findings, 2 under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** My comparator reported no difference on any of the 61 cards. I checked by eye that the standing rows (PF1, PF2, PFD deactivated as `delete_formula` leaves it, PF9, I1 to I3, IX, I9), their order, the `line` builder and the recorder all match the Conventions.
- **Why NEEDS WORK:** one gap. `get_by_formula_and_role` has no card where a row of W2 sits on a W1 formula and W1 asks for it, so a `>=` on `workspace_id` survives. `get_by_formula` has that card; the role query does not.
- **Unordered queries have their alarms:**
  - `get_by_formula` (BUG-1319) → G-09, strict
  - `get_by_formula_and_role` (BUG-1320) → R-16, strict

  The non-strict tie cards G-11 and R-18 pass today on every plan, by row order. G-10 and R-17 fail. No pass card depends on row order.

Written by Claude (all 61 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 61. No local-run file exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_formula_and_role` R1 "Another workspace returns `[]`" (step 1b, both sides) | R-03 asks W2 while the line is in W1. No card asks W1 while a W2 line is present. | `r_r1_ge` passes all 61 on all three plans. | **case designer** |

No fidelity finding.

### Scratch card that closes the gap
This card is in `...\prodv\prop\test_prop_production_formula_item.py`. It passes on today's code and on my reference, on three plans, and fails under `r_r1_ge`.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card, R R1 | Z = line, `workspace_id W2.id` (on PF1, `item_role "input"`). When `dao.get_by_formula_and_role(db, formula_id=PF1.id, item_role="input", workspace_id=W1.id)` | `result == []` | pass | `r_r1_ge` |

## Surviving mutants
None.

**Guard.** My driver ran each of the 10 mutants again without `-x`. Every run reached all 55 pass tests, and the kills were the same as `mutate.py`'s.

## Hand variants
These ran on my reference with `--runxfail`. The candidates were run again on the sequential-off and index-off plans, with no change. Each edit applied exactly once, and every run reached all 61 tests.

| Group | Variants | Pass card | Others |
|---|---|---|---|
| g (`get_by_formula`: workspace, formula, every role, order, no cap, parents raw, duplicates kept, writes) | 20 | 15 | 4 bug path (G-09 to G-11); `g_cap1000` |
| r (`get_by_formula_and_role`: the same, plus 12 exact-role variants) | 31 | 25 | 4 bug path (R-16 to R-18); `r_r1_ge`; `r_cap1000` |
| i (by id) | 11 | 11 | — |
| **Total** | **62** | **51** | **11** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `g_cap1000`, `r_cap1000` | A cap above the cards' own 101 rows. `limit(100)` is caught by G-12 and R-19. |

## xfail tests against the reference
My reference, `ref/production_formula_item.py`, adds `ORDER BY id` to both lists.
- With `--runxfail`: **61 passed**.
- **The alarm works:** with the markers on, `2 failed, 55 passed, 4 xpassed`, and the strict G-09 and R-16 report `XPASS(strict)`.
- On today's code, G-09 and R-16 fail on their `ORDER BY` line on all three plans.

## Reproduced claims
- **The notes' Result line holds:** `55 passed, 4 xfailed, 2 xpassed` in 4 of 4 default runs. No test is flaky.
- **Mocks:** none.
- **`ruff check`** passes.

## Traceability
cases 61 · tests 61 · unmatched: none · marker mismatches: none.
- BUG-1319 and BUG-1320 are in `bugs.md`.
- My comparator found 0 differences. Its selftest caught 1057 of 1057 planted mistakes.

## Commands run
```
pytest --cov=app.dao.production_formula_item --cov-branch           55 passed, 4 xfailed, 2 xpassed; 100%
tests/unit/_tools/mutate.py app/dao/production_formula_item.py tests/unit/dao/test_production_formula_item.py --timeout 300 --json <scratch>/res/mut_production_formula_item.json
  10 mutants · 10 killed
xcheck.py; vdrive.py muts / vars (+ seq, idx); propdrive.py; fid.py; selftest.py
git diff --stat -- app/dao                                          (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\prodv\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add R-1.
2. **Executor,** after step 1: implement it, then send the module back for re-verification.


## Round 2 — 2026-11-03 (Revision 1 and 1b, narrow)

> **Verdict:** PASS
> Tests: 56 passed, 4 xfailed, 2 xpassed (reproduced ✅, 3 of 3 runs, no flaky test) · 62 cards
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 62 unfaithful** (new and changed tests read by eye against their cards; all 62 rebuilt by `fid.py`, 0 differences)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED

Every round 1 finding is closed. I found no new rule gap. No test was edited in this round, and nothing was committed.

- **New / changed cards, read by eye:** PFI-R-25 (R-1). Each matches its card: Given, When, every Then, and the marker.
- **Gap variants against their cards**, on my reference with `--runxfail`, on the default, sequential-off and index-off plans: `r_r1_ge` fails R-25. Each fails its named card on all three plans.
- **Reference:** `--runxfail` gives 62 passed. With markers: 2 failed (strict XPASS), 56 passed, 4 xpassed. The alarms still go off.
- **Today, `--runxfail`:** every strict xfail fails on its card's line, on three plans.
- **Parked for the owner:** nothing.

### Commands run
```
fid.py production_formula_item                                     62 cards, 0 differences
r2.py (reference ±markers; gap variants × 3 plans; today --runxfail × 3 plans; 3 plain runs)
ruff check <the seven test files>               All checks passed!
git diff --stat -- app/dao                      (empty)
```
