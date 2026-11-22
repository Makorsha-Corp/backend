# Execution notes — `app/managers/po_machine_inventory.py`

> Cases: `tests/unit/managers/po_machine_inventory.cases.md` (READY, revision 2, 0 cases) · Tests: none (by design) · Source commit: e48a092
> Result: 0 passed · 0 xfailed · 0 discrepancies · 0 errors — branch coverage N/A (no specified callables; module is dead code)
> Run: none — there is no test file to run.

## How the tests are built
No test file was written. The cases file issues no cases (ID prefix `POMI`
reserved, unused) and its Reviewer summary/Coverage matrix says every
callable gets "none (by design)". The spec's "Notes for the test designer"
is explicit: "nothing to test in this module... Do not write a
`test_po_machine_inventory.py` under `tests/unit/managers/`."

The whole module (`PO_MACHINE_SOURCE_TYPE`, `_quantity_to_int`,
`_weighted_avg_price`, `_ensure_machine_item`, `_ledger_exists_for_source`) is
dead code the reviewer marked for removal (spec Q1): its only caller,
`post_purchase_order_to_machine`, was already deleted in `7be54d5`, and the
live receive-into-machine flow now runs entirely through
`app/managers/po_receive_inventory.py` (`post_receive_event_inventory`),
which has its own quantity/weighted-average/get-or-create/ledger-exists
logic and does not import this file. Removal is logged in
`po_machine_inventory.deadcode-staging.md` (whole file, plus its now-orphaned
imports of `machine_item_dao` and `MachineItemLedger` if nothing else uses
them).

Creating an empty or placeholder test file was deliberately avoided: it
would contradict the spec and would break (ImportError) once the module is
deleted (best-practice default, delegated by reviewer — same precedent as
`app/utils/work_order_calendar.py`, see `tests/unit/utils/work_order_calendar.notes.md`).

No local helpers/builders were needed since no test code was written.

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| Whole file (`PO_MACHINE_SOURCE_TYPE`, `_quantity_to_int`, `_weighted_avg_price`, `_ensure_machine_item`, `_ledger_exists_for_source`) | dead | Listed under the spec's Not specified as dead code to be removed (Q1); unreachable from any live code path since `7be54d5` deleted the sole caller. |

## Factories added
None. No builders needed; none worth promoting.

## Revision history
- Revision 2 re-run (this pass): cases file revision bumped to note the
  verifier's PASS with no findings routed back; nothing about this module
  changed (still 0 cases, source commit still `e48a092`, module still has no
  importers under `app/`, `alembic/`, or `tests/`). Re-confirmed via
  `git rev-parse --short HEAD` (`e48a092`) and a repo-wide grep for
  `po_machine_inventory` outside this file, which found nothing. No test file
  written, no changes made to this notes file beyond this entry and the
  revision tag above (best-practice default, delegated by reviewer: an
  unchanged dead-code verdict needs no new test artifacts).

## Notes for maintainers
- When the dead-code removal lands, delete `app/managers/po_machine_inventory.py`
  and this module's spec/cases/notes/deadcode-staging files together, and drop
  the now-orphaned `machine_item_dao` / `MachineItemLedger` imports if unused
  elsewhere.
- The live receive-into-machine behavior (whole-unit quantities,
  weighted-average price, get-or-create machine stock row, ledger-exists
  double-post guard) is tested under `app/managers/po_receive_inventory.py`'s
  own spec/cases (`post_receive_event_inventory`), not here.
