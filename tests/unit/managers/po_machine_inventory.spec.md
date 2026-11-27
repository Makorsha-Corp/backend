# Spec — `app/managers/po_machine_inventory.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### New questions

### Q1. The whole module is orphaned — nothing calls any of it — 🗑️ remove
**Background:** This file used to hold `post_purchase_order_to_machine`, which posted fully received PO lines into a machine's stock. That function was deleted in the dead-code removal commit (`7be54d5`). Receiving a PO into a machine now goes through `app/managers/po_receive_inventory.py` (`post_receive_event_inventory`), which has its own ledger-exists check and does not import anything from this file.
**What happens today:** The four helpers left behind (`_quantity_to_int`, `_weighted_avg_price`, `_ensure_machine_item`, `_ledger_exists_for_source`) and the constant `PO_MACHINE_SOURCE_TYPE` are never imported or called anywhere under `app/`. No API request, service, or background job can reach them.
**Example:** A user receives 5 units of a PO into Machine A. The stock and ledger rows are written by `po_receive_inventory.py`. No line of `po_machine_inventory.py` runs. Deleting the file would change nothing a user can see.
**Rules affected:** `_quantity_to_int` R1–R5, `_weighted_avg_price` R1–R4, `_ensure_machine_item` R1–R4, `_ledger_exists_for_source` R1–R4
**Suggested answer:** remove
**Answer:** remove (reviewer accepted suggestion)
**Resolution:** all four helpers are dead code, to be removed; each was the whole reason the file exists, so the whole file `app/managers/po_machine_inventory.py` goes, including the unused constant `PO_MACHINE_SOURCE_TYPE` (best-practice default, delegated by reviewer — same precedent as `work_order_calendar.py`). No caller anywhere in `app/`, and no legacy test outside `tests/unit/` references any of these names. Logged in `po_machine_inventory.deadcode-staging.md`. Not a bug — no BUG ID.

## Overview
This module held leftover helpers from the old "post a completed purchase order into machine inventory" flow: turning a received Decimal quantity into whole units, computing a weighted-average unit price, finding or creating the `machine_items` stock row for a (machine, item) pair, and checking whether a machine-ledger row already exists for a given source (to stop the same line being posted twice). Its public entry point was deleted in `7be54d5` and the live receive flow (`po_receive_inventory.py`) does not call into this file, so every callable here is unreachable (Q1) and the reviewer marked the whole module for removal.

**Callables:** 0 specified · 5 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Notes for the test designer:** nothing to test in this module — every callable is dead code scheduled for removal. Do not write a `test_po_machine_inventory.py` under `tests/unit/managers/`.

## Not specified
- `PO_MACHINE_SOURCE_TYPE` — dead code, to be removed (reviewer). Unused constant, no caller.
- `_quantity_to_int` — dead code, to be removed (reviewer)
- `_weighted_avg_price` — dead code, to be removed (reviewer)
- `_ensure_machine_item` — dead code, to be removed (reviewer)
- `_ledger_exists_for_source` — dead code, to be removed (reviewer)

## Branch map
(none — every decision point belonged to a callable removed as dead code; see Q1)
