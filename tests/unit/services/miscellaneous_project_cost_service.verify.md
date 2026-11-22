# Verification — `app/services/miscellaneous_project_cost_service.py`

> **Verdict:** PASS
> Tests: 61 passed · 28 xfailed (27 strict + L-15 non-strict; reproduced ✅) · coverage 100% branch
> Mutation: 52 mutants · 52 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 (target file clean in the working tree) · Cases revision: 2

## Summary
These tests can be trusted. Every card is implemented once and faithfully. Every strict xfail fails on the Then line its card names. Coverage reproduces at 100% branch, and every mutant of the service is killed. L-15 is non-strict because its card says so ("xfail BUG-100 (non-strict)", physical row order). In 3 plain runs on this pass it xfailed each time; the executor saw it xpass twice, which is allowed. L-14 is the strict `ORDER BY` alarm. Nothing to fix. The module stays "revisit after launch" (BUG-2611 … 2618, owner 2026-11-10); that changes no verdict.

## Findings
None.

Not findings:
- The reason constants for BUG-2611 … 2618 add "(revisit after launch)" also on cards without a `Revisit` header. Each reason still names its BUG ID, and the register status explains the suffix.
- L-19 checks `len == 2` plus a subset. That is exactly what its card asks for.

## Surviving mutants
None.

## Traceability
cards 89 · tests 89 (one `# [claude] MPCSV-…` each) · unmatched: none · marker mismatches: none. 61 pass cards have no marker, and 27 cards are `xfail(strict=True)` with a reason naming the card's BUG ID. L-15 is `xfail(strict=False, reason=BUG_100)` as its card says. Every BUG ID exists in `docs/testing/bugs.md`: 100, 1013, 1192, 1278, 2611–2618.

Fidelity: all 89 tests were read against their cards.
- Every numbered Then line is asserted with the exact value and in card order.
- Givens match the Conventions: XID ids, "but" columns, the commit point, and X after it.
- `committed:` lines run `db.rollback()` and then a fresh SELECT.
- No broad `except`, and every `pytest.raises` names the card's type.
- Nothing is patched beyond the Conventions' spies and the failing commit / refresh. The spec lists no externals.
- `--runxfail`: 27 fail on their named Then lines. C-10 and C-11 fail with the FK `IntegrityError` inside `raises(HTTPException)`, as their cards say. L-15 passes.

## Future notes
- Permissions (`docs/future/permissions.md`): the only check is "may open the project". Any such member may add, change or delete any cost, whoever entered it (there is no author column), and sees every amount. The executor's notes already carry this.
- Notifications: none sent by this module.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/services/test_miscellaneous_project_cost_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.miscellaneous_project_cost_service --cov-branch --cov-report=term-missing
  app\services\miscellaneous_project_cost_service.py  89  0  30  0  100%
  61 passed, 28 xfailed
(plain, twice more)   61 passed, 28 xfailed · 61 passed, 28 xfailed
.venv/Scripts/python.exe -m pytest tests/unit/services/test_miscellaneous_project_cost_service.py -q -p no:cacheprovider -o addopts="" --runxfail
  27 failed, 62 passed
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/miscellaneous_project_cost_service.py tests/unit/services/test_miscellaneous_project_cost_service.py --lines 1-120 --timeout 240 --json <scratch>/mut_misc_1.json
  Mutants: 26 · killed 26 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/miscellaneous_project_cost_service.py tests/unit/services/test_miscellaneous_project_cost_service.py --lines 121-999 --timeout 240 --json <scratch>/mut_misc_2.json
  Mutants: 26 · killed 26 · timeout 0 · survived 0 · score 100%
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\authv\` (private `COVERAGE_FILE`s).
