# Spec — `app/managers/po_storage_inventory.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Q1. `_quantity_to_int` has no callers left — 🗑️ removed
**Background:** This module used to post fully received purchase-order lines into
factory STORAGE stock (`post_purchase_order_to_storage`). That function was
deleted as dead code in commit `7be54d5` ("dead code removal"); receiving is now
done per receive event by `po_receive_inventory.py`, which has its own helper
(`_delta_to_int`). Other modules (`to_inventory`, `po_return_inventory`,
`po_machine_inventory`, `product_manager`) each define their own private
`_quantity_to_int`; none imports this one.
**What happens today:** `_quantity_to_int` (turn a received Decimal quantity into
a whole number, 400 if fractional or ≤ 0) is left in the file, but nothing in the
application calls it, so no user action can reach it.
**Example:** A user receives 2.5 units on a PO line. The 400 "Line 3 has a
fractional received quantity; storage inventory requires whole units" is never
shown — the live receive flow answers with its own message ("... fractional
quantity delta; inventory requires whole units") from `po_receive_inventory`.
Tests written for this helper would only protect code no one runs.
**Rules affected:** `_quantity_to_int` R1–R6
**Answer:** remove (reviewer accepted suggestion)
**Resolution:** dead code, moved to Not specified and removed from this spec.
Logged in `tests/unit/managers/po_storage_inventory.deadcode-staging.md`
(not a bug — no BUG ID).

### Q2. `_weighted_avg_price` has no callers left — 🗑️ removed
**Background:** Same history as Q1: its only caller, `post_purchase_order_to_storage`,
was deleted in commit `7be54d5`. The live receive flow updates average prices
through `inventory_movements.post_stock_in`. `po_machine_inventory.py` has its
own separate copy of `_weighted_avg_price`.
**What happens today:** `_weighted_avg_price` (weighted-average stock price after
adding units) stays in the file with no caller anywhere in the application.
**Example:** A factory has 10 units at 5.00 and receives 10 more at 7.00. The new
average shown to the user (6.00) is computed by `post_stock_in`, not by this
function; changing or breaking this function changes nothing a user sees.
**Rules affected:** `_weighted_avg_price` R1–R6
**Answer:** remove (reviewer accepted suggestion)
**Resolution:** dead code, moved to Not specified and removed from this spec.
Logged in `tests/unit/managers/po_storage_inventory.deadcode-staging.md`
(not a bug — no BUG ID).

## Overview
Leftover of the legacy "post a completed purchase order into factory STORAGE
inventory" flow. The posting function itself was removed as dead code; what
remains is the constant `PO_INVENTORY_SOURCE_TYPE = 'purchase_order'` (still
imported by `po_receive_inventory.py` as `PO_LEGACY_LINE_SOURCE`, to recognise
ledger rows written by the old flow when reversing receives). The two private
pure helpers that used to feed the deleted posting function (`_quantity_to_int`,
`_weighted_avg_price`) are themselves unreachable dead code — see Q1, Q2 — and
have been removed from scope.

**Callables:** 0 specified · 2 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Notes for the test designer:**
- The constant is data, not a callable: one trivial check that
  `PO_INVENTORY_SOURCE_TYPE == 'purchase_order'` is enough (it must match the
  `source_type` on legacy ledger rows that `po_receive_inventory` looks up).
- Nothing else in this module is reachable; no test cases are designed from the
  two removed helpers.

## Not specified
- `_quantity_to_int` — dead code, to be removed (reviewer)
- `_weighted_avg_price` — dead code, to be removed (reviewer)

---

## `PO_INVENTORY_SOURCE_TYPE` (module constant)
**Shape:** constant · **Persistence:** pure · **Visibility:** public (used by: `app/managers/po_receive_inventory.py`)

**Rules:**
- **R1.** Its value is exactly the string `'purchase_order'`.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 6 | constant value | `PO_INVENTORY_SOURCE_TYPE` R1 |
