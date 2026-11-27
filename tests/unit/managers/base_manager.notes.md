# Execution notes — `app/managers/base_manager.py`

> Cases: `tests/unit/managers/base_manager.cases.md` (revision 3) · Tests: `tests/unit/managers/test_base_manager.py` · Source commit: e48a092
> Result: 6 passed · 0 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `COVERAGE_FILE=<private> .venv/Scripts/python.exe -m pytest tests/unit/managers/test_base_manager.py -q -p no:cacheprovider -o addopts="" --cov=app.managers.base_manager --cov-branch --cov-report=term-missing`

## How the tests are built
- One plain test per card, in card order. No database is used: the constructor takes no session, so `db` is not requested and no row is built (Conventions).
- `S = object()` is built inside BMG-I-03, as its Given says. Nothing is patched; the spec lists no externals.

## Verification runs (revision 3)
- 3 plain runs: 6 passed each time. `--runxfail`: 6 passed (no xfail markers left).
- The reference plugin (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsupe\bm\bm_ref.py`) is no longer needed: BMG-I-05 now ignores `__orig_class__`.
- `ruff check`: clean. LF only (0 CR bytes).

## Discrepancies
None. DISCREPANCY-1 (BMG-I-05: `typing` adds `__orig_class__` to instances of a subscripted class) was closed by cases revision 3, which checks `vars(result)["model"]` and allows `__orig_class__` as the only other key.

## Coverage gaps
None — 100% branch coverage (6 statements, 0 branches).

## Factories added
None.

## Notes for maintainers
- BMG-I-06 pins `DepartmentManager`'s attributes to exactly `{"department_dao", "model"}`. Adding an attribute to that manager breaks this card.

## Revision history
- **2026-11-10 — cases revision 2.** First implementation: 6 cases, 5 passed, 1 xfailed (DISCREPANCY-1 on BMG-I-05 Then 2).
- **2026-11-10 — cases revision 3.** BMG-I-05 Then 2 is now `vars(result)["model"] is Department`, and a new Then 3 checks `set(vars(result)) - {"__orig_class__"} == {"model"}`. The DISCREPANCY-1 marker was removed. Result: 6 passed.
