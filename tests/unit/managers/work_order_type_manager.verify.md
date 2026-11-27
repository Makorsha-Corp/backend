# Verification — `app/managers/work_order_type_manager.py`

> **Current verdict: PASS** (round 2, 2026-11-04, cases revision 2, 93 cases). Narrow round, see "Round 2" at the end. The block below is round 1.

> **Round 1 verdict:** NEEDS WORK (case designer only; the tests are faithful)
> Tests: 63 passed · 29 xfailed (23 strict, 6 non-strict) (reproduced ✅) · coverage 100% branch (60 statements, 26 branches)
> Mutation: 61 mutants · 59 killed · 2 survived → score 100% (59/59, after excluding 2 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 1

## Summary
The tests can be trusted. Every one of the 92 cards has exactly one test. Every marker matches its Expect line. Each xfail fails today on the Then line its card names. The runs reproduce the notes and stayed the same over 4 plain runs and 2 forced query plans.

The race cards WOTM-C-12 and U-21 pass today. Each asserts pgcode `23505` and constraint `uq_wo_type_workspace_name` on a real `IntegrityError` inside a savepoint. C-13 (a case variant) stays xfail BUG-1214, as the spec says. Mutation testing kills every non-equivalent mutant.

The design does not fully follow designer step 1b, so the verdict is NEEDS WORK. These are the same two gaps as in `delivery_method_manager`, and both go to the case designer:
- **WOTM-S-06** names one chosen row of a page on an unordered query.
- **BUG-1706** (non-strict WOTM-N-13) has no strict alarm on the `_check_name_exists` query.

The executor and the describer have nothing to fix.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | design (step 1b: a card names one chosen row of an unordered page) | WOTM-S-06 | The card expects `ids(result) == [B.id]` from `skip=1` over 2 live rows ("Inspection", "Repair"). The query has no `ORDER BY`. Once BUG-1709 alone is fixed, the result is `[A.id]` or `[B.id]` depending on physical order. The card is filed under BUG-1709 only, so it can XFAIL or XPASS at random for a reason its marker does not name. | Cases L965–966: `Then 1. returns: ids(result) == [B.id]`. Source L111–113 → base `get_by_workspace`, which has no ORDER BY (spec Branch map L266). | **case designer**: use a page-size and set check, e.g. `len(result) == 1` and `set(ids(result)) <= {A.id, B.id}`. This still fails today in the usual order. |
| 2 | design (step 1b: the unordered query behind a non-strict card has no strict alarm) | WOTM-N-13 / `_check_name_exists` L150 | N-13 (BUG-1706, non-strict) rests on physical row order. The strict recorders S-22 and S-23 record only the `search_work_order_types` call. A fix of BUG-1706 would show only as a non-strict XPASS. The cases file says so itself ("BUG-1706 (the 100-row cap) has none"), and so does notes L42. | Cases Reviewer summary L14. The coverage matrix lists only N-12 (pass) and N-13 (non-strict) for R5. | **case designer**: add one strict `sql_log` card (Author: claude) on `M._check_name_exists(db, workspace_id=W1.id, name="Repair")`. It should assert that the uniqueness read is not a capped scan: for example, no `work_order_types` statement has `LIMIT` unless its WHERE compares `name`. It fails today on the `LIMIT 100` statement. Choose the wording so that an EXISTS or `LIMIT 1` fix on the name passes. |

### Step 1b check on the non-strict cards (all six)
| Card | Assertion | Names one chosen row of an unordered page? | Strict alarm for its query |
|---|---|---|---|
| S-05 | `sorted(ids) == [A, B]` (set, limit 2 over exactly 2 live rows) | no | S-23 (BUG-1709) |
| S-06 | `ids == [B]` after `skip=1` | **yes** (Finding 1) | S-23 (BUG-1709) |
| S-07 | `ids == [X]` ("Repair" is the only name that matches "pair") | no: the whole match set | S-23 (BUG-1709) |
| S-20 | full order of 5 rows | order card (R3), allowed by "Missing sort order" | S-22 (BUG-1710) |
| S-21 | `names == ["Charlie", "delta"]` | order card (R3), allowed by "Missing sort order" | S-22 (BUG-1710) |
| N-13 | `result is True` (a boolean, not a row) | no | **none** (Finding 2) |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 20 | 73:11 | `name and name != current` → `or` | equivalent | The mutant differs only for `None`, `""` or the current name. For `None` the extra check is always False, because `name` is NOT NULL. `""` is a BUG-1708 input that the intended schema refuses. For the current name, the type excludes itself, and another row with the identical name is forbidden both by the Conventions and by `uq_wo_type_workspace_name`. The mutant runs an extra query but gives the same results. This is the same argument as department #20. | — |
| 41 | 83:57 | `exclude_unset=True → False` | equivalent | Column 57 is `exclude_unset`; `exclude_none` is at column 76 and was killed. `WorkOrderTypeUpdate` has one field, `name: str \| None = None`, and `exclude_none=True` still drops it when it is unset. | — |

## Traceability
- Cases 92 · tests 92 (92 functions, none parametrized) · unmatched: none · duplicates: none · tests without a card: none. Checked with my own AST script.
- Markers: the 63 `pass` cards have no xfail, including C-12 and U-21, which pass today. The 23 strict cards have `strict=True`. The 6 `(non-strict)` cards have `strict=False`. Every reason names every BUG ID on its Expect line. BUG-1214, 1521 and 1706…1711 all exist in `docs/testing/bugs.md`.
- Mocks: only `app.dao.work_order_type.utcnow` (autouse) and `race`. `race` is used only by C-12, C-13 and U-21. The `db.commit` spy appears only in C-14, U-22 and D-05. The session and the DAOs are not mocked.
- Fidelity: I read every test against its card, including the module's extra cards C-15 and U-23 (a deleted name in other case is free). Every Then line is asserted in order. The race cards follow the Conventions: `pytest.raises(IntegrityError)` → `db.begin_nested()` → call, with `db` used afterwards. They assert `orig.pgcode == "23505"` and `orig.diag.constraint_name`. The counts and re-reads come after the savepoint rollback. I found no missing, weakened or changed assertions, no wrong setup, no write check that is only in memory, and no swallowed exceptions. No setup holds two rows with the exact same name, which today's constraint forbids.
- xfail honesty (`--runxfail --tb=line`, failures mapped to `# Then N`):
  - C-04 and U-08 raise `IntegrityError … uq_wo_type_workspace_name` in the When call. That is what their cards say, and they fail today on BUG-1214, not on a setup error.
  - C-13 fails with `DID NOT RAISE IntegrityError` in Then 1.
  - The other 26 fail the same way as their delivery-method counterparts: DID NOT RAISE, an untrimmed name, `updated_by` in Then 2, `TypeError` for G-07/G-08, `assert False` in Then 2 for S-22 and S-23, `False is True` for the N cards, and row order for S-05/06/07/20/21.
  - The failed set equals the 29 xfail cards.

## Commands run
```
COVERAGE_FILE=<scratch>/.cov_work_order_type .venv/Scripts/python.exe -m pytest tests/unit/managers/test_work_order_type_manager.py -q -p no:cacheprovider --cov=app.managers.work_order_type_manager --cov-branch --cov-report=term-missing
  app\managers\work_order_type_manager.py      60      0     26      0   100%
  63 passed, 29 xfailed, 15 warnings in 8.08s
... --runxfail -rf                                         29 failed, 63 passed (failed set == xfail set)
... --runxfail --tb=line  + <scratch>/thenline.py          each failure in its card's Then block / When call (above)
... (plain, x2)                                            63 passed, 29 xfailed · 63 passed, 29 xfailed
PGOPTIONS="-c enable_seqscan=off" ... -rX                  63 passed, 29 xfailed (no XPASS)
PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off" ... -rX   63 passed, 29 xfailed (no XPASS)
.venv/Scripts/python.exe -m ruff check tests/unit/managers/test_work_order_type_manager.py   All checks passed!
.venv/Scripts/python.exe -I <scratch>/trace_v.py <cases> <test> <runxfail> docs/testing/bugs.md
  cards 92 tests 92 pass 63 xfail 29 (strict 23) · problems: 0
COVERAGE_FILE=<scratch>/.cov_mut_wot .venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/work_order_type_manager.py tests/unit/managers/test_work_order_type_manager.py --json <scratch>/mut_wot.json
  Mutants: 61 · killed 59 · timeout 0 · survived 2 · score 97%   (#20 L73:11, #41 L83:57)
```
`<scratch>` = `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\mgr5v2`. The results match the notes: 63 passed · 29 xfailed (23 strict, 6 non-strict) · 100% branch. No flaky tests.

## Round 2 — 2026-11-04 (cases revision 2, narrow)

> **Verdict:** PASS
> Tests: 63 passed · 30 xfailed (24 strict, 6 non-strict) (reproduced ✅) · coverage 100% branch (60 statements, 26 branches)
> Mutation: not re-run, as the coordinator asked. Round 1 stands: 61 mutants · 59 killed · 2 equivalent, on the same source. Only xfail tests changed or were added.
> Source commit: e48a092 · Cases revision: 2

### Summary
Both round 1 findings are closed. I checked only WOTM-S-06 and the new WOTM-N-17 against their cards. The other 91 tests were covered only by the mechanical checks below.

| Round 1 finding | Now |
|---|---|
| 1 — S-06 names one chosen row of an unordered page | Closed. Then 1 is `len(result) == 1` and Then 2 is `set(ids(result)) <= {A.id, B.id}`, asserted exactly as the card says. It is still non-strict BUG-1709. Today it fails on Then 1 (`assert 2 == 1`). |
| 2 — no strict alarm on the `_check_name_exists` query (BUG-1706) | Closed by WOTM-N-17 (strict, BUG-1706). The test matches the card. Under `--runxfail` it fails on Then 3 (`assert not True`). |

### N-17 against a fixed `_check_name_exists`
I used the same scratch plugin `<scratch>/fixname_v.py`, with both shapes: an uncapped scan with no LIMIT, and a name-filtered `lower(btrim(name)) = … LIMIT 1`.

With either shape, `--runxfail -k _n_` gives 17 passed, N-17 included. With the markers on, N-17 shows `XPASS(strict)` and fails the run, so it works as the alarm. N-13 shows a non-strict XPASS. N-06/07/08 show XPASS(strict) for BUG-1707, which the plugin also fixes.

### Not done
No full mutation run. I did not re-read the 91 unchanged tests.

### Commands run
```
... test_work_order_type_manager.py --cov=app.managers.work_order_type_manager --cov-branch   63 passed, 30 xfailed; 100% (60/26)
... --runxfail -rf                                   30 failed, 63 passed (failed set == xfail set)
... --runxfail --tb=line + <scratch>/thenline.py     S-06 Then 1 `assert 2 == 1`; N-17 Then 3 `assert not True`
... (plain, x3, -rX)                                 63 passed, 30 xfailed ×3, no XPASS
FIXSHAPE=scan|exists PYTHONPATH=<scratch> ... -p fixname_v --runxfail -k _n_    17 passed (each shape)
FIXSHAPE=scan|exists ... -p fixname_v -k _n_ -rX     N-17 XPASS(strict) → failed (each shape)
<scratch>/trace_v.py                                 cards 93 tests 93 pass 63 xfail 30 (strict 24) · problems: 0
ruff check                                           All checks passed!
```
