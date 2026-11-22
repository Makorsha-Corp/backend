# Execution notes — `app/services/order_hub_stats_helpers.py`

> Cases: `tests/unit/services/order_hub_stats_helpers.cases.md` (revision 2) · Tests: `tests/unit/services/test_order_hub_stats_helpers.py` · Source commit: e48a092
> Result: 19 passed · 0 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `COVERAGE_FILE=<private> .venv/Scripts/python.exe -m pytest tests/unit/services/test_order_hub_stats_helpers.py -q -p no:cacheprovider --cov=app.services.order_hub_stats_helpers --cov-branch --cov-report=term-missing`

## How the tests are built
- No database: every order is an unsaved model instance built with the card's keyword arguments; a status is an unsaved `Status(id=…, name=…)` assigned to `current_status`. No test requests `db`, so the session-scoped `engine` fixture (and its migration) is never started for this file.
- T1 / T2 are module constants (naive datetimes, as in Conventions).
- "none of (fields)" is written as one `is None` assertion per field.
- Model imports (cases Spec gap 1): `app.models.purchase_order.PurchaseOrder`, `app.models.expense_order.ExpenseOrder`, `app.models.transfer_order.TransferOrder`, `app.models.status.Status`. These are the paths the module under test itself imports, so the Conventions' assumption holds.
- Nothing is patched. 3 plain runs: 19 passed each time.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage. (coverage.py does not count the `status.name if status else None` conditional expressions as branches; both arms are still exercised: P-01/T-01 with a status, P-03/T-03 without.)

## Factories added
None.

## Notes for maintainers
- Unsaved instances carry no column defaults (those apply at INSERT), which is what the "optional fields are None" cards rely on. If a model gains a Python-side `__init__` default for e.g. `total_amount`, OHS-P-03 / OHS-E-02 would fail for that reason, not because of the mapper.
- OHS-H-01 depends on the schema ignoring extra keys (pydantic default `extra="ignore"`).

## Revision history
- **Revision 2 (2026-11-04)**: cases revision 2, from verify.md finding 1 (money scale). OHS-P-01 gained Then 7, `str(result.total_amount) == "1234.50"`. In OHS-E-01 the amount changed from `Decimal("99.95")` to `Decimal("99.90")` in the Given line and in Then 5, and Then 8, `str(result.total_amount) == "99.90"`, was added. No other test changed. Result is still 19 passed with 100% branch coverage, 3 plain runs gave 19 passed each time, and ruff is clean.
