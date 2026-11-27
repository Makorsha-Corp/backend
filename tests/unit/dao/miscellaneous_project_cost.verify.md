# Verification — `app/dao/miscellaneous_project_cost.py`

> **Current verdict: PASS (round 2, 2026-11-10, cases revision 3): findings 1 and 2 are closed. See "Round 2" at the end. Still *revisit after launch*.**
>
> **Verdict:** NEEDS WORK (two card fixes for the case designer; the tests themselves are faithful). Module is **revisit after launch** (owner 2026-11-10): BUG-2460 / BUG-2461 and inherited R2a (OQ-28) stay as tagged; nothing here needs the owner.
> Tests: 74 passed · 13 xfailed (reproduced ✅; GP-27 non-strict XPASSes now and then, as designed) · coverage 100% branch (10 statements, 0 branches)
> Mutation: mutate.py 10 mutants · 10 killed · 0 survived → score 100%. Hand variants 33 · 27 killed · 6 survived → score 93% (after excluding 0 equivalent, 0 dead, 4 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
The 87 tests follow their cards line for line. No mocks, and every xfail fails on Then 2, as its card says. mutate.py kills all 10 mutants. Hand variants kill workspace scoping (`<=` / `>=` / dropped, with W0 and W2 rows on both sides of W1), project / component `<=` / `>=`, matching a component id as a project id, excluding the other link column, no offset, no limit, `limit + 1`, `offset + 1`, paging in Python after the fetch, and the default `skip` / `limit` values. The money facts (half-up rounding, the `Numeric(15,2)` 13 / 14-digit bound, negative and zero stored) are pinned with exact `Decimal` compares.

Two card-level gaps remain:
- The "takes no lock" checks (`lock_part == ""`) are vacuous for a plain `FOR UPDATE`, so `.with_for_update()` on either list survives.
- MPC-GP-25's Given lacks the `db.expire_all()` without which the card cannot pass. The executor added it and recorded why.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing (convention) | MPC-GP-13 Then 3, MPC-GC-11 Then 4 (Conventions "lock_part") | `lock_part` = text after `FOR UPDATE`. The compiled SQL ends `LIMIT … OFFSET … FOR UPDATE`, so `lock_part == ""` holds with a lock too | Hand variants `mpc-gp-lock`, `mpc-gc-lock` SURVIVED | **case designer**: `"FOR UPDATE" not in sql` |
| 2 | card defect (Given) | MPC-GP-25 | Card has no `db.expire_all()` between the Given and the When. Without it the identity map returns the inserted `Decimal("2.125")`, not the stored `2.13`, so the card as written fails on correct code. The test adds the expire (documented in the notes). That is faithful to the card's intent but not to its text. | `test_mpc_gp_25…` line `db.expire_all()` before the When; notes "GP-25 adds db.expire_all()" | **case designer**: add `db.expire_all()` as Given 3 (as SRT-RI-05 has) |

## Surviving mutants
mutate.py: none.

Hand variants:
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | 43 | `get_by_project` `ORDER BY id DESC` | bug-path | Order is BUG-2460; only GP-26 / 27 (non-strict) and GP-28 (strict) see it, all xfail | — |
| 2 | 43 | `get_by_project` `ORDER BY id` | bug-path | The BUG-2460 fix itself | — |
| 3 | 43 | `get_by_project` `.with_for_update()` | case-missing | Finding 1 | **case designer** |
| 4 | 70 | `get_by_component` `ORDER BY id DESC` | bug-path | BUG-2460; GC-22, 23, 24 xfail | — |
| 5 | 70 | `get_by_component` `ORDER BY id` | bug-path | The BUG-2460 fix | — |
| 6 | 70 | `get_by_component` `.with_for_update()` | case-missing | Finding 1 | **case designer** |

## Notes
- Revisit after launch: the BUG-2460 / BUG-2461 xfail reasons carry `(revisit after launch)` and the R2a pass cards carry the docstring tag, as the Conventions ask. No owner action is needed now.
- GP-27 (pages of one after an edit, non-strict) XPASSed in my run 2 (74 passed, 12 xfailed, 1 xpassed). It is the physical-order case the card is non-strict for, and the notes record it. Not counted as flaky.
- Traceability script note: card IDs include `MPC-OQ28-nn`. All 87 matched.

## Traceability
cases 87 · tests 87 · unmatched: none · duplicates: none · marker mismatches: none. 9 strict and 4 non-strict xfails (via `xfail_bug`) match the Expect lines. Reasons name BUG-2460, 2461 and 100, all in `bugs.md`. There is no local-written test.

`--runxfail` (own `whereplug.py`): GP-26 … GP-34, GC-22, GC-23, GC-24 and INH-01 all fail on Then 2, each with the card's expected cause (no `ORDER BY`, or the component-only cost missing).

## Commands run
```
COVERAGE_FILE=…/omdv/B/.cov.miscellaneous_project_cost.{1,2,3} .venv/Scripts/python.exe -m pytest tests/unit/dao/test_miscellaneous_project_cost.py -q -p no:cacheprovider -o addopts="" --cov=app.dao.miscellaneous_project_cost --cov-branch --cov-report=term-missing
  run 1: 74 passed, 13 xfailed · TOTAL 10 0 0 0 100%
  run 2: 74 passed, 12 xfailed, 1 xpassed (GP-27, non-strict) · 100%
  run 3: 74 passed, 13 xfailed · 100%
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_miscellaneous_project_cost.py -q -p no:cacheprovider -o addopts="" --runxfail -rf
  13 failed, 74 passed
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/miscellaneous_project_cost.py tests/unit/dao/test_miscellaneous_project_cost.py --json …/omdv/miscellaneous_project_cost.mut.json
  Mutants: 10 · killed 10 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe …/omdv/B/hand.py …/omdv/B/vars.json …/omdv/B/hand.res.txt 4
  mpc-*: 33 variants · 27 killed · 6 survived
```
The results match the notes (74 / 13, 100%, GP-27 occasional XPASS).

## Round 2 — 2026-11-10
Narrow re-check of cases revision 3 (patched, not regenerated). **Verdict: PASS.**

**Changed cards:** MPC-GP-13 (Then 3) and GC-11 (Then 4): `"FOR UPDATE" not in sql`; the MPC-GP-25 card now has Given 3 `db.expire_all()` (the test already did this).

**Fidelity:** GP-13, GC-11 and GP-25 match their cards line by line. GP-25's card and test now agree. **0 unfaithful.**

**Runs:** 74 passed, 13 xfailed (run 1, run 3) and 74 passed, 12 xfailed, 1 xpassed (run 2: the non-strict GP-27, as designed and noted in round 1) · coverage 100% branch · `--runxfail` 13 failed, 74 passed. No flaky outcome. Runs (private `COVERAGE_FILE`, `omdv\R2\.cov`): `pytest <file> -q -p no:cacheprovider -o addopts=""` with `--cov=app.dao.<module> --cov-branch` once, plain twice, then `--runxfail` once.

**Variants:**
- Lock in `get_by_project` / `get_by_component` (OF and plain): all 4 **killed** (GP-13, GC-11). They used to survive.

Variants: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\plug\r2var.py` (per-method `FOR UPDATE OF <table>` and plain `FOR UPDATE`; create's year hard-coded 2026, bypassing the tests' clock patch; a hidden `db.get` of the parent), driven by `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\run_r2.py` on the pass tests (`-m "not xfail"`); results in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\r2.txt`. `mutate.py` was not re-run: Revision 3 only adds assertions and one card, so no mutant killed in round 1 can survive now.

**Open items:** None.
