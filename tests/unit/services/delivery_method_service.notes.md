# Execution notes — `app/services/delivery_method_service.py`

> Cases: `tests/unit/services/delivery_method_service.cases.md` (revision 1) · Tests: `tests/unit/services/test_delivery_method_service.py` · Source commit: e48a092
> Result: 28 of 28 cases implemented · 24 passed · 4 xfail as designed (all strict, all xfailed) · 0 errors · 0 discrepancies — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_delivery_method_service.py -q -p no:cacheprovider`

## How the tests are built
Same form as `department_service.notes.md`. The cards mirror the work order type cards line for line, so the file was derived from `test_work_order_type_service.py` by a scratch substitution script (names, messages, fixed values). Every difference was then checked against this cases file by hand and by a scratch cross-check: ids, Then numbers and order, markers, bug ids, and every quoted string. DMS-C-05 is a pass card here (no unique constraint on `delivery_methods`), not the BUG-1214 xfail of its sibling. Helpers: `mk_method(**but)` / `mk_methods([…])` (name "Courier", `created_by` U2), `gone(u2)`, `commit_point`, `reread`, `snap_before` / `snap`, `count_methods`, `written`, `unloaded`, `usable`. Schemas `DeliveryMethodCreate`, `DeliveryMethodUpdate` from `app.schemas.delivery_method`, as spec G1 says.

## Fails-today check
`--runxfail`: G-04 Then 1 `DID NOT RAISE HTTPException`; G-05, L-06 `TypeError` (no `include_deleted`) in the When; G-06 the same `TypeError` inside Then 1's wrap. All as the cards say.

## Reference run
`refplug.py` (scratch) replaced the five service methods with the spec's intended behaviour (`include_deleted` on get and list). With `--runxfail` all 28 tests passed; without it all 4 strict cards XPASSed (strict, so they failed).

## Stability
5 plain runs plus the two forced plans: 24 passed, 4 xfailed in all 7; no test moved. Ruff passes; LF.

## Discrepancies
None. The schema names in the cards (spec gap G1) are the real ones.

## Coverage gaps
None — 100% branch coverage (41 statements) of `app/services/delivery_method_service.py`.

## Factories added
None.

## Notes for maintainers
- DMS-C-05 checks that a deleted method's name can be used again. It must keep passing if a unique index is ever added: make it partial on live rows.
