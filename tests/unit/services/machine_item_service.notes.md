# Execution notes — `app/services/machine_item_service.py`

> Cases: `tests/unit/services/machine_item_service.cases.md` (revision 1) · Tests: `tests/unit/services/test_machine_item_service.py` · Source commit: e48a092
> Result: 42 of 42 cases implemented (no MIS-D-05 exists) · 24 passed · 18 xfail as designed (17 strict, all xfailed; 1 non-strict, L-08, xfailed in every run) · 0 errors · 0 discrepancies — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_machine_item_service.py -q -p no:cacheprovider`

## How the tests are built
Same form as `department_service.notes.md`.
- **Standing rows:** chained fixtures in Conventions order: `w1`, `w2`, `u1`, `u2`, `f1`, `fd`, `f9`, `i1`, `i2`, `ix`, `i9`, `m1`, `m2`, `mx`, `mf`, `m9`, `wt1` (autouse `standing_rows`). Every standing row has `created_by` U1.
- **Given rows:** `mk_stock(machine, item, qty, **but)`, `bulk(n)`, `mk_order(machine, "A", status=…)`, `mk_source_line(order)`. MIS-L-08's three items use the module's `_item` builder.
- **Reading helpers:** `reread`, `snap_before` / `snap` (`machine_items` columns), `count_rows(table, **filters)`, `written` (the three tables), `entries_of`, `events_of(m, event_type=None)`, `ids`, `unloaded`, `usable`.
- **Patches:** the failing commit / refresh wraps; the manager patch of D-03 (`delete_machine_item` raising `ValueError("Machine item has open orders", BLOCKERS)`); the create patch of C-14 (`ValueError("x", [])`). Nothing else.
- `AppValidationError` = `app.core.exceptions.ValidationError`; `PydanticValidationError` = `pydantic.ValidationError`, imported under those names as Conventions say.

## Fails-today check
`--runxfail`, failing line mapped to its `# Then N`, value read:
- Then 1 `DID NOT RAISE`: G-03, G-06, C-08, C-10, U-03, D-06 (`HTTPException`); C-11, C-12 (pydantic `ValidationError`); D-04 (`AppValidationError`).
- C-09 (BUG-1010): Then 1, `IntegrityError` `machine_items_item_id_fkey`, the card's text. D-03 (BUG-1081): Then 1, the `ValueError` escapes unchanged.
- G-04: `TypeError` in the When; G-05: the `TypeError` inside Then 1's wrap.
- L-06: Then 1, one row against `[]`. L-07: Then 1 `[MX row, B]` against `[B]`. U-04: Then 2 `7 is None`. D-07: Then 3 `len([]) == 1`.
- L-08 (non-strict, BUG-1071): Then 2, insertion order against `[IA, IB, IZ]`, in every run.

## Reference run
`refplug.py` (scratch) wrapped the five service methods, changing only what each bug names:
- get: the item-workspace check and `include_deleted` (deleted machine or factory, removed item);
- list: hidden rows filtered, `machine_id` tested against `None`, ordered by `lower(item name), id`;
- create: deleted factory, unknown or foreign item, removed item;
- update: deleted machine refused; explicit null clears `req_qty`;
- delete: deleted machine refused, open-order blockers raised as the manager's `ValueError`, the final ledger entry of a negative row, and the service's translation into `AppValidationError` after the rollback.

`MachineItemCreate` was replaced in memory by a subclass with `0 <= qty <= 2**31 - 1`. With `--runxfail` all 42 tests passed; without it all 17 strict cards XPASSed (strict, so they failed) and L-08 XPASSed.

## Stability
5 plain runs plus seqscan off and index/bitmap scans off: 24 passed, 18 xfailed in all 7; no test moved. Ruff passes; LF.

## Discrepancies
None. The `IntegrityError` note (spec G1, MIS-C-15) holds: 23503 at the flush, nothing saved, A unchanged, session usable.

## Coverage gaps
None — 100% branch coverage (39 statements) of `app/services/machine_item_service.py`.

## Factories added
None.

## Notes for maintainers
- BUG-1081 has two halves. D-03 checks the service's translation with a patched manager; D-04 is end to end and needs the manager's half too.
- `delete_machine_item` emits SQLAlchemy's `LegacyAPIWarning` (`Query.get` in `app/dao/base.py`); harmless here.
- `bulk(101)` names items `P00000` … with `name_normalized` the same, as the card says.
