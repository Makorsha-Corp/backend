# Verification — `app/managers/department_manager.py`

> **Current verdict: PASS** (round 4, 2026-10-31, revision 5, 99 cases; lighter than an independent round). See "Round 4" at the end. The rest of this block is round 1.

> **Round 1 verdict:** NEEDS WORK
> Tests: 53 passed · 38 xfailed (reproduced ✅) · coverage 100% branch
> Mutation: 61 mutants · 58 killed · 3 survived → score 98.3% (58/59, after excluding 2 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
The tests are faithful to the cases: every case ID is implemented exactly once, every xfail is strict, names the right BUG IDs and fails on the assertion the case predicts, and the runs reproduce the notes and are stable. Mutation testing finds one real gap. `update_department` R7 ("`name` explicitly `null` leaves the name unchanged") is checked only by DEPT-U-13, and DEPT-U-13 is xfail for BUG-009 (`updated_by`). So no expected-to-pass test covers an explicit `null` name. If `exclude_none=True` were removed from line 120, the code would write `name = NULL` and hit a NOT NULL error, and no test in the mutation run would notice. The case designer needs to add an expected-to-pass case for R7 with `name=None` that does not assert `updated_by`. The other two survivors are equivalent.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `update_department` R7 / L120 (mutant #42) | R7 ("name omitted or explicitly `null` → name unchanged") is correct today but only has cases that are xfail for another bug: DEPT-U-12/U-13 are `xfail BUG-009` because they also assert `updated_by == U2`. The null-name behaviour therefore has no case expected to pass, and the mutation run skips xfail tests. | Mutant #42 `exclude_none=True -> False` survived. With the mutation, `DepartmentUpdate(name=None)` dumps as `{"name": None}`, `setattr(name, None)` runs, and the flush violates `departments.name NOT NULL`. DEPT-U-13 would still "xfail", only for a different reason. | **case designer**: add a pass case, e.g. W1: live "HR"; `update_department(..., DepartmentUpdate(name=None), W1, U1)` → no error, re-read `name == "HR"` (no `updated_by` assertion, so BUG-009 does not affect it) |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 20 | 109 | `name and name != current` → `name or name != current` | equivalent | The mutant differs only when `name` is `None`, `""` or the current name. For `None`, the extra `_check_name_exists(name=None)` always returns False because `name` is NOT NULL. `""` is a BUG-004 input that the intended schema rejects. For the current name, the department excludes itself, so the extra check could return True only if another live department had the identical name. Once BUG-003 is fixed, the spec invariant makes that state impossible, and the cases' setup conventions forbid it. The mutant runs an extra query but gives the same results in every state the spec allows. | — |
| 41 | 120 | `exclude_unset=True -> False` | equivalent | `DepartmentUpdate` has one field, `name`, and it defaults to `None`. When `name` is unset it dumps as `None`, and `exclude_none=True` still drops it, so the dict is the same. | — |
| 42 | 120 | `exclude_none=True -> False` | case-missing | Observable: an explicit `name=None` writes NULL and the flush fails. Only DEPT-U-13 covers this, and it is xfail for BUG-009. See Finding 1. | **case designer** |

## Traceability
- Cases: 91. Tests: 91 collected (56 functions; 4 parametrized functions produce C-07/08, U-16/17, N-06..09).
- Unmatched: none. No duplicate case IDs, no test without a case ID.
- Markers: 53 `pass` cases have no xfail. All 38 `xfail` cases have `xfail(strict=True)`, and each reason names every listed BUG ID (C-18: BUG-002 + BUG-004; U-15: BUG-004 + BUG-009). BUG-001…BUG-009 all exist in `docs/testing/bugs.md`.
- Mocks: only `app.dao.department.utcnow` (spec Externals) and the `race` fixture (`_check_name_exists` → False). `race` is used only by C-17, C-19, U-22 and U-23, as the cases file lists. The session and DAOs are not mocked.
- Fidelity: every Given/When/Then was compared. No missing, weakened or changed assertions, no wrong setup, no in-memory-only write checks, no swallowed exceptions.
- xfail honesty (`--runxfail`): each xfail fails on its "fails today on" assertion (DID NOT RAISE, untrimmed name, `updated_by` = U1 id, `TypeError` for `include_deleted`, `[]` or insertion order for S-04..07 and S-13..15, `False is True` for the N cases). C-18 and U-15 fail first on `built .name` (BUG-004). That BUG is in their reasons, and the case's named assertion is still present, as the notes record.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_department_manager.py -q -p no:cacheprovider --cov=app.managers.department_manager --cov-branch --cov-report=term-missing
  app\managers\department_manager.py      63      0     26      0   100%
  53 passed, 38 xfailed, 15 warnings in 7.88s

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_department_manager.py -q -p no:cacheprovider --runxfail -rf
  38 failed, 53 passed in 3.77s   (the 38 failures are exactly the 38 xfail cases)

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_department_manager.py -q -p no:cacheprovider   (x2, flakiness check)
  53 passed, 38 xfailed in 3.79s
  53 passed, 38 xfailed in 3.82s

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/department_manager.py tests/unit/managers/test_department_manager.py --json <scratch>/mut_department.json
  (run provided by the caller on the current tests, not re-run) 61 mutants · 58 killed · 3 survived (#20 L109, #41 L120, #42 L120)
```
Result matches the notes (53 passed · 38 xfailed · 100% branch). No flaky tests.

## Round 2 — 2026-10-31 (cases revision 3, narrow)

> **Verdict:** PASS
> Tests: 57 passed · 38 xfailed (reproduced ✅) · coverage 100% branch (63 statements, 26 branches)
> Mutation: 61 mutants · 59 killed · 2 survived → score 100% (59/59, after excluding 2 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 3

### Summary
Finding 1 is closed and mutant #42 is killed. **No card was added in this round.** The card the finding asked for already existed: cases revision 3 added DEPT-U-25 after round 1 ran, and round 1's counts (91 cases, revision 2) are older than that revision. Adding another card would have duplicated it, so the cases file, its Counts, Revision and matrix are unchanged at 95 cases (57 pass, 38 xfail).

**How much this round is worth.** It is lighter than an independent round. One agent did all of it: it decided that no card was missing, made the comment edits and checked the result. It added no cards, so it did not check cards of its own. The cards it relies on came from earlier sessions (revision 3) and no independent verifier has audited them. It read only the tests named under Fidelity against their cards, not every test as round 1 did.

### Findings
None.

| Round 1 finding | Now |
|---|---|
| 1 — `update_department` R7, no pass case for explicit `name=None` | Closed by DEPT-U-25 (pass). Mutant #42 `exclude_none=True -> False` (L120:82) KILLED. |

### Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 20 | 109 | `name and name != current` → `or` | equivalent | Round 1's argument still holds; the line has not changed. | — |
| 41 | 120 | `exclude_unset=True -> False` (col 63) | equivalent | `DepartmentUpdate` has one field, defaulting to `None`, and `exclude_none=True` still drops it. Column checked against the source, so #41 and #42 are not swapped. | — |

### Fidelity (partial)
Read against their cards: DEPT-U-12, U-13, U-14 (narrowed in revision 3 to `updated_by` only) and DEPT-U-25. No missing, weakened or changed assertion. C-20, U-24 and U-26 are covered here only by the mechanical checks and the mutation run.

### Traceability
Cases 95 · tests 95 · unmatched: none · duplicates: none. Checked on the collected pytest items, not on source text: every `xfail` card has exactly one `strict=True` mark whose reason names each listed BUG ID, every `pass` card has no mark, and every BUG ID exists in `bugs.md`. `--runxfail` failed set == the 38 xfail cases. Which assertion each xfail fails on was not re-read; only U-12/13/14 changed there, and each has one assertion.

### Stability
8 whole-file runs, 4 of them after the comment edit, including `enable_seqscan=off` (confirmed with `SHOW`), `enable_indexscan=off` + `enable_bitmapscan=off`, and seq and bitmap scans off. Identical every time; no XPASS.

### Test-file change
Comments only, to make ruff clean, in the form the sibling files use: `# ruff: noqa: SIM117` and `# noqa: DTZ001` on T0 and NOW. No test body changed. The full mutation run was made before this edit; the mutants on L118-122 were re-run after it.

### Left open (outside the Findings table)
- The file has no commit-spy cards, although the spec says "No commit" for `create_department`, `update_department` and `delete_department` and the current designer skill asks for one per writer. The pilot predates that rule.
- DEPT-S-13/14/15 and the other order-dependent cards are strict xfails. The current skill wants non-strict order cards plus one strict `ORDER BY` card per unordered query. They held on every plan tried, so this is a design gap and not a failure today.

### Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_department_manager.py -q -p no:cacheprovider --cov=app.managers.department_manager --cov-branch --cov-report=term-missing
  app\managers\department_manager.py      63      0     26      0   100%
  57 passed, 38 xfailed, 15 warnings
... --runxfail -rf                                   38 failed, 57 passed (failed set == xfail set)
PGOPTIONS="-c enable_seqscan=off"                    57 passed, 38 xfailed
PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off"   57 passed, 38 xfailed
PGOPTIONS="-c enable_seqscan=off -c enable_bitmapscan=off"     57 passed, 38 xfailed (before the comment edit)
.venv/Scripts/python.exe -m ruff check tests/unit/managers/test_department_manager.py     All checks passed!   (9 errors before the edit)
.venv/Scripts/python.exe -m ruff check --select F841,F811 ...                             All checks passed!
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/department_manager.py tests/unit/managers/test_department_manager.py --json <scratch>/mut_department.json
  Mutants: 61 · killed 59 · timeout 0 · survived 2 · score 97%   (#20 L109, #41 L120)
... --lines 118-122  (after the comment edit)        Mutants: 3 · killed 2 · survived 1 (the same `exclude_unset` mutant; `exclude_none` KILLED)
```

## Round 3 — 2026-10-31 (cases revision 4, narrow)

> **Verdict:** PASS
> Tests: 60 passed · 39 xfailed (reproduced ✅) · coverage 100% branch (63 statements, 26 branches)
> Mutation: not re-run this round. Round 2 stands: 61 mutants · 59 killed · 2 equivalent, on the same source; this round only added tests and loosened three xfail markers, and mutation runs skip xfail tests.
> Source commit: e48a092 · Cases revision: 4

### Summary
Closes the two gaps round 2 left open. Added 4 cards: commit spies DEPT-C-21, U-27, D-05, and strict statement recorder DEPT-S-26 (BUG-008). DEPT-S-13/14/15 moved to non-strict xfail, with a reason in the marker. Counts went from 95 to 99 cases (60 pass, 39 xfail). No writer commits, so there is no discrepancy.

**How much this round is worth.** The same agent wrote these cards, wrote their tests and checked them, so this is lighter than an independent round. No independent verifier has audited revision 4. The negative control below is the only evidence here that does not rest on that agent reading its own work.

### Findings
None.

### Checks on the new cards
- **Negative control:** a scratch pytest plugin wrapped all three writers in memory to call `session.commit()` after running (nothing under `app/` changed). C-21, U-27 and D-05 all went red. The failure line was not inspected card by card.
- **Recorder:** DEPT-S-26 fails today on Then 2 (`--runxfail`, `assert any(...)`). Its regex matches the SQL compiled from `select(Department).order_by(func.lower(Department.name), Department.id)`, so it will go green when BUG-008 is fixed that way. A fix that orders differently (for example with a collation) would need the card revised.
- **Non-strict cards:** S-13/14/15 xfailed in every run and never XPASSed, on any plan. Non-strict means an XPASS there would no longer be a failure; S-26 is the alarm instead.

### Not done
- One recorder card, not two. `_check_name_exists` is also unordered today, but R5 asks that every live row be examined, not for an order, so no card was written. The reason is in the cases file's Reviewer summary.
- DEPT-S-04/05/06/07, C-06 and N-12 (strict xfail) and N-11 (pass) still depend on insertion order. The skill's "Missing sort order" rule reaches them too, but this round was asked to move only S-13/14/15. They held on every plan tried.

### Traceability
Cases 99 · tests 99 · marker check on collected items: 0 problems (strict and non-strict each match the Expect cell; every reason names its BUG IDs). `--runxfail` failed set == the 39 xfail cases.

### Stability
Plain runs 3, with no change. Forced plans `enable_seqscan=off`; `enable_indexscan=off` + `enable_bitmapscan=off`; seq + bitmap off: 60 passed, 39 xfailed on each, no XPASS.

### Commands run
```
... test_department_manager.py --cov=app.managers.department_manager --cov-branch      60 passed, 39 xfailed; 100%
... --runxfail -rf                                                                     39 failed, 60 passed (failed set == xfail set)
PGOPTIONS (3 forced plans)                                                             60 passed, 39 xfailed each
.venv/Scripts/python.exe -m ruff check tests/unit/managers/test_department_manager.py  All checks passed!
```

## Round 4 — 2026-10-31 (cases revision 5, narrow)

> **Verdict:** PASS
> Tests: 60 passed · 39 xfailed (reproduced ✅) · coverage 100% branch
> Mutation: not re-run; only xfail markers changed, and mutation runs skip xfail tests. Round 2 stands.
> Source commit: e48a092 · Cases revision: 5

The same agent made these changes and checked them, so this is lighter than an independent round.

Each card was run with `--runxfail` while a scratch plugin rewrote the list statement's order (nothing in `app/` changed):

| Card | Order forced | Result today | Decision |
|---|---|---|---|
| DEPT-S-04 | `is_deleted, name` | passes | non-strict |
| DEPT-S-05 | `is_deleted, name` | passes | non-strict |
| DEPT-S-06 | `name DESC` | passes | non-strict |
| DEPT-S-07 | `name DESC` | passes | non-strict |
| DEPT-C-06 | `name` | passes | non-strict |
| DEPT-N-12 | `name` | passes | non-strict |
| DEPT-N-11 (pass card) | `name`; `name DESC`; match last; match first | passes on all four | stays pass: 100 rows equal the cap, so it cannot fail by row order. Round 3's line and the old note saying it depends on order were wrong. |

No card was left strict, because none has a failure independent of row order.

Runs on the final file: 3 plain and 1 coverage, 60 passed, 39 xfailed; `--runxfail` 39 failed, 60 passed; ruff clean; marker check 0 problems. Forced plans: `enable_seqscan=off` gave 60 passed, 38 xfailed, 1 XPASS (DEPT-C-06); the other two plans gave 60 passed, 39 xfailed. That XPASS would have turned the file red while C-06 was strict, and it did not appear on the same plan in round 3, so the XPASS count is not fixed from run to run.

**Open:** DEPT-S-26 is a strict alarm for BUG-008 only. BUG-001, BUG-006 and BUG-007 now have no strict card, so fixing one of them shows as XPASS and fails nothing. The skill's recipe does not cover this, because those are paging and scan-cap bugs, not missing sort orders.
