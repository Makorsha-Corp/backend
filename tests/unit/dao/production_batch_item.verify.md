# Verification — `app/dao/production_batch_item.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1). See "Round 2" at the end. The block below is round 1.

> **Verdict:** NEEDS WORK — only the case designer has work: one card. No test is wrong.
> Tests: 54 passed · 6 xfail (2 strict, 4 non-strict) (reproduced ✅) · coverage 93% branch (14 statements; line 84 missed, dead `get_by_item`)
> Mutation: 15 mutants · 10 killed · 5 survived → score 100% (after excluding 0 equivalent, 5 dead, 0 bug-path)
> Fidelity: **0 of 60 unfaithful** (my script checked every card; I read the helpers by eye)
> Hand variants: 62 · 51 caught by a pass card · 8 bug path · 3 others: 1 rule gap in Findings, 2 under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** My comparator reported no difference on any of the 60 cards. I checked by eye that the standing rows (F1, F9, L1, L9, B1, B2, BC cancelled, B9, I1 to I3, IX, I9), their order, the `line` builder and the recorder all match the Conventions.
- **Why NEEDS WORK:** one gap, the same one as in `production_formula_item`. `get_by_batch_and_role` has no card where a W2 row sits on a W1 batch and W1 asks for it.
- **Unordered queries have their alarms:**
  - `get_by_batch` (BUG-1322) → G-09, strict
  - `get_by_batch_and_role` (BUG-1323) → R-16, strict

  G-11 and R-18 pass today on every plan, by row order. `get_by_item` is dead (P1), with no card and no alarm.
- **Step 1b, real states:** BC is `status "cancelled"` only. The spec does not say which columns a cancel writes; the batch cases list this as Spec gap 4, owned by the batch spec. It does not weaken R5 here, because the query does not read the batch.

Written by Claude (all 60 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 60. No local-run file exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_batch_and_role` R1 "Another workspace returns `[]`" (step 1b, both sides) | R-03 asks W2 for a W1 line. No card asks W1 while a W2 line on B1 is present. | `r_r1_ge` passes all 60 on all three plans. | **case designer** |

No fidelity finding.

### Scratch card that closes the gap
This card is in `...\prodv\prop\test_prop_production_batch_item.py`. It passes on today's code and on my reference, on three plans, and fails under `r_r1_ge`.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card, R R1 | Z = line, `workspace_id W2.id` (on B1, `item_role "input"`). When `dao.get_by_batch_and_role(db, batch_id=B1.id, item_role="input", workspace_id=W1.id)` | `result == []` | pass | `r_r1_ge` |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 3 | 84 | `return` → `return None` | dead | `get_by_item`: spec P1, "Not specified", dead-code checklist `app/dao/production_batch_item.py:67` | — |
| 5 | 69 | `skip=0` → `1` | dead | same method's default | — |
| 6 | 69 | `limit=100` → `101` | dead | same method's default | — |
| 14 | 87 | `workspace_id ==` → `!=` | dead | same method | — |
| 15 | 88 | `item_id ==` → `!=` | dead | same method | — |

**Guard.** My driver ran each mutant again without `-x`. Every run reached all 54 pass tests, and the sets were the same as `mutate.py`'s.

## Hand variants
| Group | Variants | Pass card | Others |
|---|---|---|---|
| g (`get_by_batch`: workspace, batch, every role, order, no cap, cancelled batch and removed item raw, duplicates, writes) | 20 | 15 | 4 bug path (G-09 to G-11); `g_cap1000` |
| r (`get_by_batch_and_role`: the same, plus 12 exact-role variants) | 31 | 25 | 4 bug path (R-16 to R-18); `r_r1_ge`; `r_cap1000` |
| i (by id) | 11 | 11 | — |
| **Total** | **62** | **51** | **11** |

All variants ran on my reference (`ORDER BY id` on both lists) with `--runxfail`. The candidates were run again on the two other plans, with no change. Each edit applied exactly once, and every run reached all 60 tests.

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `g_cap1000`, `r_cap1000` | A cap above the cards' own 101 rows. `limit(100)` is caught by G-12 and R-19. |

## xfail tests against the reference
- With `--runxfail`: **60 passed**.
- **The alarm works:** with the markers on, `2 failed, 54 passed, 4 xpassed`, and the strict G-09 and R-16 report `XPASS(strict)`.
- On today's code, G-09 and R-16 fail on their `ORDER BY` line on all three plans.

## Reproduced claims
- **The notes' Result line holds:** `54 passed, 4 xfailed, 2 xpassed` in 4 of 4 default runs. No test is flaky.
- **Mocks:** none.
- **`ruff check`** passes.

## Traceability
cases 60 · tests 60 · unmatched: none · marker mismatches: none.
- BUG-1322 and BUG-1323 are in `bugs.md`.
- My comparator found 0 differences. Its selftest caught 1057 of 1057 planted mistakes.

## Commands run
```
pytest --cov=app.dao.production_batch_item --cov-branch             54 passed, 4 xfailed, 2 xpassed; 93% (line 84)
tests/unit/_tools/mutate.py app/dao/production_batch_item.py tests/unit/dao/test_production_batch_item.py --timeout 300 --json <scratch>/res/mut_production_batch_item.json
  15 mutants · 10 killed · 5 survived (L69, L84, L87, L88)
xcheck.py; vdrive.py muts / vars (+ seq, idx); propdrive.py; fid.py; selftest.py
git diff --stat -- app/dao                                          (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\prodv\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add R-1.
2. **Executor,** after step 1: implement it, then send the module back for re-verification.


## Round 2 — 2026-11-03 (Revision 1 and 1b, narrow)

> **Verdict:** PASS
> Tests: 55 passed, 4 xfailed, 2 xpassed (reproduced ✅, 3 of 3 runs, no flaky test) · 61 cards
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 61 unfaithful** (new and changed tests read by eye against their cards; all 61 rebuilt by `fid.py`, 0 differences)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED

Every round 1 finding is closed. I found no new rule gap. No test was edited in this round, and nothing was committed.

- **New / changed cards, read by eye:** BIT-R-25 (R-1). Each matches its card: Given, When, every Then, and the marker.
- **Gap variants against their cards**, on my reference with `--runxfail`, on the default, sequential-off and index-off plans: `r_r1_ge` fails R-25. Each fails its named card on all three plans.
- **Reference:** `--runxfail` gives 61 passed. With markers: 2 failed (strict XPASS), 55 passed, 4 xpassed. The alarms still go off.
- **Today, `--runxfail`:** every strict xfail fails on its card's line, on three plans.
- **Parked for the owner:** nothing.

### Commands run
```
fid.py production_batch_item                                     61 cards, 0 differences
r2.py (reference ±markers; gap variants × 3 plans; today --runxfail × 3 plans; 3 plain runs)
ruff check <the seven test files>               All checks passed!
git diff --stat -- app/dao                      (empty)
```
