# Verification — `app/utils/audit_logger.py`

> **Verdict:** PASS
> Tests: 45 passed · 20 xfailed (reproduced ✅) · coverage 100% branch
> Mutation: 20 mutants · 20 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 4

## Summary
These tests can be trusted. I re-verified from scratch against cases revision 4, which has the same case content as revision 3.
All 65 case IDs map one-to-one to tests. Every xfail test has `strict=True` and names its BUG. With `--runxfail`, each xfail fails at the point its case gives under "fails today on".
The test run matches the executor's Result line exactly. Three runs gave the same result, so nothing is flaky.
All 20 mutants were killed. I found no fidelity problems. Nothing needs to change.

## Findings
None.

Observations (not findings, no stage required):
- BUG-140..144 are not yet in `docs/testing/bugs.md`. They are recorded in `tests/unit/utils/audit_logger.bugs-staging.md` with matching titles, and batch mode merges them into `bugs.md` later. For this verify I checked the IDs against the staging register (best-practice default, delegated by reviewer). Re-check against `bugs.md` after the merge.
- The coverage report also lists `app/utils/order_catalog_items.py`. This is because another agent is running coverage at the same time. It does not affect this module's numbers (35 stmts, 16 branches, 0 missed).

## Surviving mutants
None. All 20 mutants were killed:

| Line | Mutation | Result |
|---|---|---|
| L104 | `exclude_none` True → False | KILLED |
| L105/106/107 | `'workspace_id'` / `'performed_by'` / `'performed_at'` → `''` | KILLED ×3 |
| L130, L132 | negate if / `is not` → `is` | KILLED ×4 |
| L131, L133 | `'before'` / `'after'` → `''` | KILLED ×2 |
| L134, L176 | `return None` | KILLED ×2 |
| L156 | negate `hasattr` | KILLED |
| L161, L164, L167, L170 | negate if-condition | KILLED ×4 |
| L170 | `and` → `or`, drop `not`, `'__dict__'` → `''` | KILLED ×3 |

## Traceability
- **Cases vs tests:** 65 cases · 60 test functions (65 test items).
  - AUD-L-07/08/09 and AUD-L-24/25/26/28 are parametrized with `pytest.param(id=…)`.
  - Every case ID appears in exactly one test.
  - Every test's docstring carries its case ID(s).
- **Unmatched:** none.
- **Marker mismatches:** none.
  - The 45 `pass` cases have no xfail marker (no DISCREPANCY in the notes).
  - The 20 `xfail` cases carry `xfail(strict=True, reason=BUG_14x)`, and the BUG ID matches the case: L-11/12 → BUG-144; L-13..19, L-21, X-19..21, X-23 → BUG-142; X-06..08 → BUG-141; X-15, X-16, X-18 → BUG-143.
- **Fidelity:** I read every test against its Given/When/Then.
  - L-cases re-read from the DB after `expire_all`.
  - SQL NULL is checked with raw SQL.
  - FLUSH-ERR tests catch the specific `DataError` or `IntegrityError` inside `begin_nested`.
  - The only mock is `app.utils.audit_logger.utcnow`, which the spec lists as an external.
  - AUD-X-05 asserts last-read-wins.
  - No test is weakened, has a changed expectation, or swallows failures.
- **Dishonest xfail:** none. With `--runxfail`, each xfail fails at its stated point:
  - L-11 and L-12 fail with `DataError`, varchar(255) and varchar(45).
  - L-13, 14, 15, 16, 18, 19 and 21 fail with `StatementError` wrapping `TypeError` (Decimal, datetime, UUID, set, timedelta).
  - L-17 fails with `DataError`, "invalid input syntax for type json".
  - X-06, 07 and 08 get float values (`2000.0`, `-5.5`, `nan`).
  - X-15 is missing the `status` key.
  - X-16 fails on `type is Color`.
  - X-18 is missing the key.
  - X-19 through X-23 fail on unconverted values.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_audit_logger.py -q -p no:cacheprovider --cov=app.utils.audit_logger --cov-branch --cov-report=term-missing
  app\utils\audit_logger.py   35   0   16   0   100%
  45 passed, 20 xfailed in 17.96s
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_audit_logger.py -q -p no:cacheprovider --runxfail -rf
  20 failed, 45 passed in 13.16s   (the 20 failures are exactly the 20 xfail cases)
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_audit_logger.py -q -p no:cacheprovider   (x2, flakiness)
  45 passed, 20 xfailed in 9.40s
  45 passed, 20 xfailed in 12.66s
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/utils/audit_logger.py tests/unit/utils/test_audit_logger.py --timeout 180 --json %TEMP%/audit_logger_mut.json
  Mutants: 20 · killed 20 · timeout 0 · survived 0 · score 100%
```
