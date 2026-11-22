# Execution notes — `app/managers/po_storage_inventory.py`

> Cases: `tests/unit/managers/po_storage_inventory.cases.md` (source commit e48a092) · Tests: `tests/unit/managers/test_po_storage_inventory.py` · Source commit: e48a092
> Result: 1 passed · 0 xfailed · 0 discrepancies · 0 errors — branch coverage 20% overall (100% of reachable code; remaining 80% is dead code out of scope — see Coverage gaps)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_po_storage_inventory.py -q -p no:cacheprovider --cov=app.managers.po_storage_inventory --cov-branch --cov-report=term-missing`

## How the tests are built
- Single case, no Conventions to map: the cases file's only convention is `K` = `PO_INVENTORY_SOURCE_TYPE`, used directly as an import, not a fixture.
- No fixtures, no `db`, no factories: the spec lists no database setup and "Externals to mock: none" — the test imports the module-level constant and asserts its value and exact type (`type(x) is str`, not `isinstance`, per the cases file's "not a subclass or enum" note).
- **Mocks:** none.
- **Parametrized:** no — a single case.
- Coverage command targets `app.managers.po_storage_inventory` as a whole module; the constant itself (line 6) is 100% covered by the one test. The two dead functions (`_quantity_to_int`, `_weighted_avg_price`) are never called, so their 12 statements / 8 branches show as missed — expected, see Coverage gaps.

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 10-24 | dead | body of `_quantity_to_int` (spec "Not specified": dead code, reviewer answer "remove" on Q1 — no caller anywhere in the app since commit 7be54d5) |
| 33-38 | dead | body of `_weighted_avg_price` (spec "Not specified": dead code, reviewer answer "remove" on Q2 — no caller anywhere in the app since commit 7be54d5) |

## Factories added
None. No database rows needed.

## Notes for maintainers
- This module's only reachable code is the constant; if `_quantity_to_int` / `_weighted_avg_price` are ever actually deleted from the source (per the reviewer's "remove" answers on Q1/Q2), this test file needs no change — the deleted lines are exactly the ones already excluded as dead here.
- `PO_INVENTORY_SOURCE_TYPE` is also consumed by `app/managers/po_receive_inventory.py` as `PO_LEGACY_LINE_SOURCE`; that consumption is out of scope for this spec (see the cases file's Deferred table) and belongs to `po_receive_inventory`'s own tests.
