# Verification — `app/dao/production_line.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1). See "Round 2" at the end. The block below is round 1.

> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 86 passed · 27 xfail (13 strict, 14 non-strict) (reproduced ✅) · coverage 94% branch (16 statements; line 80 missed, dead `get_by_machine`)
> Mutation: 21 mutants · 18 killed · 3 survived → score 100% (after excluding 0 equivalent, 3 dead, 0 bug-path)
> Fidelity: **0 of 113 unfaithful** (my script against every card; I read every difference and the helpers by eye). 3 nits.
> Hand variants: 101 · 76 caught by a pass card · 19 bug path · 6 others: 1 rule gap (3 variants) in Findings, 3 under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** My comparator rebuilt every test from its card and found no unfaithful test. Its only differences are three unused `newest` lines, which I read. I read the fixtures and helpers against the Conventions by eye: standing rows, their order, FD's and MD's deleted columns, the builders and the recorder all match.
- **Why NEEDS WORK:** one rule gap. In all three paged lists, a workspace filter applied after `LIMIT` survives.
- **Unordered queries have their alarms:**
  - `get_by_workspace` (BUG-100) → GW-07
  - `get_by_factory` (BUG-1310) → GF-16
  - `get_active_by_workspace` (BUG-1311) → GA-17

  These are all strict SQL cards. The tie cards are non-strict.
  - Pass today on every plan, by row order: GF-18, GF-19, GA-19 and GA-20.
  - Pass on the sequential plan only: GF-20 and GA-21.

  No pass card depends on row order. `get_by_machine` is dead (P1).

Written by Claude (all 113 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 113. No local-run file exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_workspace` R1, `get_by_factory` R2, `get_active_by_workspace` R1 (step 1b "filter before paging") | The paged cards hide an inactive or soft-deleted row ahead of the page. None hides another workspace's row there. | `gw_r1_ws_after_page`, `gf_r1_ws_after_page`, `ga_r1_ws_after_page` each pass all 113 on all three plans. | **case designer** |
| 2 | nit, not unfaithful | PLN-GW-10, PLN-GF-25, PLN-GA-24 Given 2 | `newest` = the ids is not built. No Then line uses it. | `fid.py` difference. | executor (optional) |

No fidelity finding.

### Scratch cards that close the gap
These are in `...\prodv\prop\test_prop_production_line.py`. Each one passes on today's code and on my reference, on three plans, and fails under its variant.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1a | new card, GW R1 | Z = line, `name "Alpha"`, `workspace_id W2.id`, `factory_id F9.id`; A = line, `name "Bravo"`; B = line, `name "Charlie"`. When `dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)` | `ids(result) == [B.id]` | pass | `gw_r1_ws_after_page` |
| R-1b | new card, GF R2 | Z = line, `name "Alpha"`, `workspace_id W2.id` (on F1); A = line, `name "Bravo"`; B = line, `name "Charlie"`. When `dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=1, limit=1)` | `ids(result) == [B.id]` | pass | `gf_r1_ws_after_page` |
| R-1c | new card, GA R1 | as R-1a. When `dao.get_active_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)` | `ids(result) == [B.id]` | pass | `ga_r1_ws_after_page` |

Z sorts first under today's row order and under the intended order (`id`; `lower(name), id`).

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 3 | 80 | `return` → `return None` | dead | `get_by_machine`: spec P1, "Not specified", dead-code checklist `app/dao/production_line.py:66` | — |
| 12 | 83 | `workspace_id ==` → `!=` | dead | same method | — |
| 13 | 84 | `machine_id ==` → `!=` | dead | same method | — |

**Guard.** My driver ran each mutant again without `-x`. Every run reached all 86 pass tests, and the sets were the same as `mutate.py`'s.

## Hand variants
Run on my reference with `--runxfail`. Variants not caught by a pass card were run again on the sequential-off and index-off plans, with no change. Each edit applied exactly once, and every run reached all 113 tests.

| Group | Variants | Pass card | Others |
|---|---|---|---|
| gw (workspace, parents raw, order, paging, writes) | 24 | 19 | 3 bug path (GW-07 to GW-09); `gw_r1_ws_after_page`; `gw_pg_cap101` |
| gf (factory, inactive kept, BUG-1312, order, paging, writes) | 34 | 24 | 8 bug path; `gf_r1_ws_after_page`; `gf_pg_cap101` |
| ga (active, machine raw, BUG-1312, order, paging, writes) | 32 | 22 | 8 bug path; `ga_r1_ws_after_page`; `ga_pg_cap101` |
| gi (by id, both workspace sides, raw states, writes) | 11 | 11 | — |
| **Total** | **101** | **76** | **25** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `gw_pg_cap101`, `gf_pg_cap101`, `ga_pg_cap101` | A cap above the cards' own 101 rows. The cap100 variants are caught. |

## xfail tests against the reference
My reference, `ref/production_line.py`, does three things:
- orders `get_by_workspace` by `id`;
- joins `factories` with `is_deleted False`, and orders by `lower(name), id`, in the other two lists;
- trims strings in the two schemas, my BUG-1313 reference, swapped in memory.

Results:
- With `--runxfail`: **113 passed**.
- **The alarm works:** with the markers on, `13 failed, 86 passed, 14 xpassed`, and the strict cards report `XPASS(strict)`.
- With `--runxfail` on today's code, every strict card fails on its "Fails today on" line on all three plans: the SQL cards on their `ORDER BY` / key lines, BUG-1312 on Then 1, and the SCH cards on Then 1.

## Reproduced claims
- **The notes' Result line holds:** `86 passed, 23 xfailed, 4 xpassed` in 4 of 4 default runs. No test is flaky.
- **Mocks:** none. There is no `try` and no broad `pytest.raises`.
- **`ruff check`** passes.

## Traceability
cases 113 · tests 113 · unmatched: none · marker mismatches: none.
- BUG-100 and BUG-1310 to BUG-1313 are in `bugs.md`.
- My comparator found 3 nits. Its selftest caught 1057 of 1057 planted mistakes.

## Commands run
```
pytest --cov=app.dao.production_line --cov-branch                   86 passed, 23 xfailed, 4 xpassed; 94% (line 80)
tests/unit/_tools/mutate.py app/dao/production_line.py tests/unit/dao/test_production_line.py --timeout 300 --json <scratch>/res/mut_production_line.json
  21 mutants · 18 killed · 3 survived (L80, L83, L84)
xcheck.py; vdrive.py muts / vars (+ seq, idx); propdrive.py production_line; fid.py; selftest.py all 6
git diff --stat -- app/dao                                          (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\prodv\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add R-1a to R-1c.
2. **Executor,** after step 1: implement them, then send the module back for re-verification.


## Round 2 — 2026-11-03 (Revision 1 and 1b, narrow)

> **Verdict:** PASS
> Tests: 89 passed, 23 xfailed, 4 xpassed (reproduced ✅, 3 of 3 runs, no flaky test) · 116 cards
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 116 unfaithful** (new and changed tests read by eye against their cards; all 116 rebuilt by `fid.py`, 0 differences)
> Source commit: e48a092 · Cases revision: 1 and 1b; spec APPROVED

Every round 1 finding is closed. I found no new rule gap. No test was edited in this round, and nothing was committed.

- **New / changed cards, read by eye:** PLN-GW-23, GF-36, GA-35 (R-1a … R-1c; Revision 1b `limit=2` with a set check); GW-10, GF-25, GA-24 drop the unused `newest`. Each matches its card: Given, When, every Then, and the marker.
- **Gap variants against their cards**, on my reference with `--runxfail`, on the default, sequential-off and index-off plans: `gw_`, `gf_`, `ga_r1_ws_after_page` fail GW-23, GF-36, GA-35. Each fails its named card on all three plans.
- **Reference:** `--runxfail` gives 116 passed. With markers: 13 failed (strict XPASS), 89 passed, 14 xpassed. The alarms still go off.
- **Today, `--runxfail`:** every strict xfail fails on its card's line, on three plans.
- **My round 1 recipes for the unordered lists were order-fragile:** they named one row of a query with no `ORDER BY`. Revision 1b's `limit=2` cards fix that, and still fail the after-`LIMIT` variant on all three plans.
- **Parked for the owner:** nothing.

### Commands run
```
fid.py production_line                                     116 cards, 0 differences
r2.py (reference ±markers; gap variants × 3 plans; today --runxfail × 3 plans; 3 plain runs)
ruff check <the seven test files>               All checks passed!
git diff --stat -- app/dao                      (empty)
```
