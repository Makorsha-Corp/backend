# Test cases — `app/managers/po_storage_inventory.py`

> **Spec:** `tests/unit/managers/po_storage_inventory.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 1 — re-run on the same APPROVED spec (source commit e48a092): no rule changes; `po_storage_inventory.verify.md` (PASS) has no case-designer findings, all 31 survivors are in the spec's dead-code helpers. No rows changed.
> **Counts:** 1 case · 1 expected-to-pass · 0 expected-to-fail (bugs) · 0 deferred

## Reviewer summary
- **Per callable:** `PO_INVENTORY_SOURCE_TYPE` 1 case (0 bug). No callables are specified.
- **Notable design choices:** the module only holds a constant, so the single case is a
  pure import-and-compare check: no database rows, no mocks. It checks the exact value
  and that the value is a plain `str` (not an enum member or other type that merely
  compares equal), because it must match the `source_type` text on legacy ledger rows.
  The two removed helpers (`_quantity_to_int`, `_weighted_avg_price`) get no cases, per
  reviewer answers Q1/Q2.
- **Needs a decision:** None.

## Conventions for this module
- Abbreviations: `POSI` = po_storage_inventory; `K` = `PO_INVENTORY_SOURCE_TYPE`.
- No database setup and no externals mocked (spec: "Externals to mock: none").
- A database session is not needed; the case imports the module and reads the constant.
- Race simulations: none.

## `PO_INVENTORY_SOURCE_TYPE`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| POSI-K-01 | R1 | happy | nothing (pure constant) | import `PO_INVENTORY_SOURCE_TYPE` from `app.managers.po_storage_inventory` | value `== "purchase_order"`; `type(value) is str` (exactly `str`, not a subclass or enum) | pass |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| (none) | — | That legacy ledger rows with `source_type = "purchase_order"` are recognised when reversing receives belongs to `po_receive_inventory` (its own spec), not this module. Listed for information only; no rule of this spec is deferred. |

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `PO_INVENTORY_SOURCE_TYPE` | R1 | POSI-K-01 |
| `_quantity_to_int` | not specified (dead code, Q1) | — |
| `_weighted_avg_price` | not specified (dead code, Q2) | — |
