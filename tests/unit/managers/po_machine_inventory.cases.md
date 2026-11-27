# Test cases — `app/managers/po_machine_inventory.py`

> **Spec:** `tests/unit/managers/po_machine_inventory.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — re-run; spec unchanged (still APPROVED at e48a092, 0 callables specified, whole module removed as dead code per Q1). `po_machine_inventory.verify.md` (PASS) has no findings routed to the case designer, so no case changes.
> **Counts:** 0 cases · 0 expected-to-pass · 0 expected-to-fail (bugs) · 0 deferred

## Reviewer summary
- **Per callable:** none specified. The spec specifies 0 callables. The constant
  `PO_MACHINE_SOURCE_TYPE` and the helpers `_quantity_to_int`, `_weighted_avg_price`,
  `_ensure_machine_item` and `_ledger_exists_for_source` are dead code. The
  reviewer marked them, and the whole file, for removal (spec Q1). So they get
  no cases.
- **Notable design choices:** as the spec instructs, no
  `test_po_machine_inventory.py` should be written under `tests/unit/managers/`.
  The live receive-into-machine behavior (whole-unit quantities, weighted-average
  price, finding or creating the machine stock row, the ledger-exists
  double-post guard) belongs to `app/managers/po_receive_inventory.py`
  (`post_receive_event_inventory`). That module is tested under its own spec,
  not here.
- **Needs a decision:** None.

## Conventions for this module
- ID prefix `POMI` = po_machine_inventory (reserved; no cases issued).
- Externals mocked: none.

## Deferred to other specs
None. The spec has no rules. For information only (this is not a rule of this
spec): the double-post guard and machine-stock posting still exist in the live
flow, and they must be covered by the `po_receive_inventory.py`
(`post_receive_event_inventory`) spec.

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `PO_MACHINE_SOURCE_TYPE` | Not specified: dead code, to be removed (Q1) | none (by design) |
| `_quantity_to_int` | Not specified: dead code, to be removed (Q1) | none (by design) |
| `_weighted_avg_price` | Not specified: dead code, to be removed (Q1) | none (by design) |
| `_ensure_machine_item` | Not specified: dead code, to be removed (Q1) | none (by design) |
| `_ledger_exists_for_source` | Not specified: dead code, to be removed (Q1) | none (by design) |
