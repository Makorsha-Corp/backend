# Test cases — `app/utils/notification_entity_label.py`

> **Spec:** `tests/unit/utils/notification_entity_label.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — re-run on unchanged spec (commit e48a092); `notification_entity_label.verify.md` (PASS) has no case-designer findings and only bug-path survivors covered by BUG-200 xfail cases. Only change: NEL-R-17 setup no longer gives the inventory a name (verify notes: inventories have no name column); the assertion is unchanged.
> **Counts:** 23 cases · 19 expected-to-pass · 4 expected-to-fail (bugs) · 0 deferred

## Reviewer summary
- **Per callable:** `resolve_notification_entity_label` 23 cases (4 bug, all BUG-200). Several cases are parametrized over entity types (one test function, one ID, one parameter set per type).
- **Notable design choices:**
  - Every BUG-200 rule is split: a passing case asserts only what holds both today and after the fix (a non-empty `str`, ending with the entity id, never another workspace's label), and an xfail case asserts the exact `"<type name> #<id>"` text. Using "ends with the id" as the bug-independent assertion is a best-practice default, delegated by reviewer: both the old `type-id` form and the new `type name #id` form end with the id.
  - The per-type label-field table is tested with one parameter set per type (NEL-R-01), and cross-workspace isolation for every type (NEL-R-09/10), because the spec says each type's lookup may use a DAO override.
  - R9 ("nothing flushed") is observed through the session's pending state (`new`/`dirty`/`deleted` empty) plus re-read row counts and label values. No spy on `flush` (best-practice default, delegated by reviewer).
  - "No lookup is made" (R6, R7) is not directly observable without mocking internals. R7 is covered by having an inventory row exist and still getting the id form. R6 has nothing to look up, so only its output is checked.
- **Needs a decision:** None.

## Conventions for this module
- ID prefix: `NEL` = notification_entity_label; `R` = `resolve_notification_entity_label`.
- `W1`, `W2` = two workspaces. Any profile/customer/supplier/inventory rows needed only to satisfy foreign keys of an entity are created in the same workspace as the entity and are otherwise irrelevant.
- `MISSING` = `2000000000`, an id that no row of any type has.
- Call shape in every case: `resolve_notification_entity_label(db, workspace_id=<W>, entity_type=<str>, entity_id=<int>)`.
- Every case asserts the return value is a `str` (never `None`) and that no exception is raised.
- Standard label values used when a case says "the standard label" for a type:

  | entity_type | row | label field value |
  |---|---|---|
  | `purchase_order` | purchase order | `po_number = "PO-2026-015"` |
  | `sales_order` | sales order | `sales_order_number = "SO-2026-004"` |
  | `expense_order` | expense order | `expense_number = "EXP-2026-007"` |
  | `transfer_order` | transfer order | `transfer_number = "TR-2026-002"` |
  | `work_order` | work order | `work_order_number = "WO-2026-011"` |
  | `project` | project | `name = "Riverside Tower"` |
  | `project_component` | project component | `name = "Foundation Slab"` |
  | `machine` | machine | `name = "CNC Lathe 3"` |
  | `item` | item | `sku = "SKU-100"`, `name = "Hex Bolt"` → label `"SKU-100"` |
  | `account_invoice` | account invoice | `invoice_number = "INV-2026-031"` |
  | `support_ticket` | help ticket | `ticket_number = "TKT-0012"` |

- Type names (R3a): `purchase_order` → "purchase order", `sales_order` → "sales order", `expense_order` → "expense order", `transfer_order` → "transfer order", `work_order` → "work order", `project` → "project", `project_component` → "project component", `machine` → "machine", `item` → "item", `account_invoice` → "account invoice", `support_ticket` → "support ticket".
- Externals mocked: none. No time mocking.
- Race simulations: none.

## `resolve_notification_entity_label`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| NEL-R-01 | R1 | happy | Parametrized over the 10 non-item attachment types (`purchase_order`, `sales_order`, `expense_order`, `transfer_order`, `work_order`, `project`, `project_component`, `machine`, `account_invoice`, `support_ticket`): one row of that type in W1 with the standard label | call with W1, that type, the row's id | returns exactly the standard label for that type (e.g. `"PO-2026-015"`, `"Riverside Tower"`, `"TKT-0012"`) | pass |
| NEL-R-02 | R1 | boundary | a project in W1 with `name = "  Riverside Tower  "` (leading and trailing spaces) | call with W1, `"project"`, its id | returns `"  Riverside Tower  "` unchanged (no trimming) | pass |
| NEL-R-03 | R1, R3 | isolation | a purchase order A in W1 with `po_number = "PO-W1-001"`; a purchase order B in W2 with `po_number = "PO-W2-001"` | call (W1, `"purchase_order"`, A.id); call (W2, `"purchase_order"`, B.id) | first returns `"PO-W1-001"`; second returns `"PO-W2-001"` | pass |
| NEL-R-04 | R2 | happy | an item in W1 with `sku = "SKU-100"`, `name = "Hex Bolt"` | call with W1, `"item"`, its id | returns `"SKU-100"` | pass |
| NEL-R-05 | R2 | boundary | an item in W1 with `sku = NULL`, `name = "Hex Bolt"` | call with W1, `"item"`, its id | returns `"Hex Bolt"` | pass |
| NEL-R-06 | R2 | boundary | an item in W1 with `sku = ""`, `name = "Hex Bolt"` | call with W1, `"item"`, its id | returns `"Hex Bolt"` | pass |
| NEL-R-07 | R3 | boundary | Parametrized over all 11 attachment types (R1 list): W1 has no rows of that type with id `MISSING` | call with W1, that type, `MISSING` | returns a non-empty `str`; the result ends with `"2000000000"` | pass |
| NEL-R-08 | R3, R3a [BUG-200] | bug | Parametrized over all 11 attachment types: as NEL-R-07 | call with W1, that type, `MISSING` | returns exactly `"<type name> #2000000000"` (e.g. `"purchase order #2000000000"`, `"support ticket #2000000000"`) | xfail BUG-200 — fails today on: result is `"<entity_type>-2000000000"` (e.g. `"purchase_order-2000000000"`) |
| NEL-R-09 | R3 | isolation | Parametrized over all 11 attachment types: one row of that type in **W2** with the standard label; W1 has no row with that id | call with W1, that type, the W2 row's id | result is not the standard label (e.g. not `"PO-2026-015"`, for item neither `"SKU-100"` nor `"Hex Bolt"`); result is a non-empty `str` ending with `str(<W2 row id>)` | pass |
| NEL-R-10 | R3, R3a [BUG-200] | bug | as NEL-R-09 | call with W1, that type, the W2 row's id | returns exactly `"<type name> #<W2 row id>"` | xfail BUG-200 — fails today on: result is `"<entity_type>-<id>"` |
| NEL-R-11 | R4 | boundary | Parametrized over empty-label rows, each in W1: (a) account invoice with `invoice_number = NULL`; (b) account invoice with `invoice_number = ""`; (c) item with `sku = ""`, `name = ""`; (d) item with `sku = NULL`, `name = ""`; (e) project with `name = ""` | call with W1, the row's type, its id | result is not `""` and not `None`; result is a `str` ending with `str(<row id>)` | pass |
| NEL-R-12 | R4, R4a [BUG-200] | bug | as NEL-R-11, same five parameter sets | call with W1, the row's type, its id | (a),(b) return `"account invoice #<id>"`; (c),(d) return `"item #<id>"`; (e) returns `"project #<id>"` | xfail BUG-200 — fails today on: result is `"account_invoice-<id>"` / `"item-<id>"` / `"project-<id>"` |
| NEL-R-13 | R5 | soft-delete | Parametrized: (a) a work order in W1, `work_order_number = "WO-2026-099"`, `is_deleted = true`; (b) a project in W1, `name = "Old Depot"`, `is_deleted = true`; (c) a machine in W1, `name = "Press 7"`, `is_deleted = true` | call with W1, the row's type, its id | returns `"WO-2026-099"` / `"Old Depot"` / `"Press 7"` respectively (not a fallback) | pass |
| NEL-R-14 | R6 | boundary | W1 with no rows | call with W1, `"scratch"`, `5` | returns a non-empty `str` ending with `"5"` | pass |
| NEL-R-15 | R6 [BUG-200] | bug | W1 with no rows | call with W1, `"scratch"`, `5` | returns exactly `"scratch #5"` | xfail BUG-200 — fails today on: result is `"scratch-5"` |
| NEL-R-16 | R7 | happy | W1 has no inventory with id 7 | call with W1, `"inventory"`, `7` | returns `"inventory #7"` | pass |
| NEL-R-17 | R7 | boundary | an inventory row exists in W1 (any valid inventory, e.g. for an item named `"Main Warehouse Stock"`) | call with W1, `"inventory"`, its id | returns `"inventory #<its id>"` exactly (the row's existence does not change the result; not any name of the row or its item) | pass |
| NEL-R-18 | R8 | happy | W1 with no rows | call with W1, `"custom_thing"`, `9` | returns `"custom thing #9"` | pass |
| NEL-R-19 | R8 | boundary | a purchase order in W1 with `po_number = "PO-2026-015"` | call with W1, `"Purchase_Order"`, the purchase order's id | returns `"Purchase Order #<its id>"` exactly (case kept; not `"PO-2026-015"`) | pass |
| NEL-R-20 | R8 | boundary | W1 with no rows | call with W1, `""`, `4` | returns `" #4"` | pass |
| NEL-R-21 | R8 | boundary | W1 with no rows | call with W1, `"a__b_c"`, `1` | returns `"a  b c #1"` (every `_` replaced, two spaces between a and b) | pass |
| NEL-R-22 | R8 | boundary | W1 with no rows | call with W1, `"widget"`, `2` | returns `"widget #2"` | pass |
| NEL-R-23 | R9 | side-effect | W1 with: a purchase order (`po_number = "PO-2026-015"`), an item (`sku = "SKU-100"`, `name = "Hex Bolt"`), an account invoice (`invoice_number = NULL`); all flushed; record the row counts of the purchase order, item and account invoice tables | call in turn: (W1, `"purchase_order"`, PO id); (W1, `"purchase_order"`, `MISSING`); (W1, `"item"`, item id); (W1, `"account_invoice"`, invoice id); (W1, `"inventory"`, `7`); (W1, `"scratch"`, `3`); (W1, `"custom_thing"`, `1`) | returns: `"PO-2026-015"`; non-empty str ending `"2000000000"`; `"SKU-100"`; non-empty str ending with the invoice id; `"inventory #7"`; non-empty str ending `"3"`; `"custom thing #1"`. After all calls: `db.new`, `db.dirty`, `db.deleted` are empty; the three row counts are unchanged; re-read rows (after `db.expire_all()`): PO `po_number` `"PO-2026-015"`, item `sku` `"SKU-100"` / `name` `"Hex Bolt"`, invoice `invoice_number` still `NULL` | pass |

## Deferred to other specs
None. (`AttachmentManager.resolve_entity_label` keeps its own `<type>-<id>` fallback per the spec's BUG-200 resolution; that behavior belongs to the attachment manager spec.)

| Rule | Owner | What must be tested there |
|---|---|---|

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `resolve_notification_entity_label` | R1 | NEL-R-01, NEL-R-02, NEL-R-03 |
| `resolve_notification_entity_label` | R2 | NEL-R-04, NEL-R-05, NEL-R-06 |
| `resolve_notification_entity_label` | R3 | NEL-R-03, NEL-R-07, NEL-R-08, NEL-R-09, NEL-R-10 |
| `resolve_notification_entity_label` | R3a [BUG-200] | NEL-R-08, NEL-R-10 |
| `resolve_notification_entity_label` | R4 | NEL-R-11, NEL-R-12 |
| `resolve_notification_entity_label` | R4a [BUG-200] | NEL-R-12 |
| `resolve_notification_entity_label` | R5 | NEL-R-13 |
| `resolve_notification_entity_label` | R6 [BUG-200] | NEL-R-14, NEL-R-15 |
| `resolve_notification_entity_label` | R7 | NEL-R-16, NEL-R-17 |
| `resolve_notification_entity_label` | R8 | NEL-R-18, NEL-R-19, NEL-R-20, NEL-R-21, NEL-R-22 |
| `resolve_notification_entity_label` | R9 | NEL-R-23 |
| `resolve_notification_entity_label` | Errors: none (unknown types fall back, never raise) | NEL-R-18 – NEL-R-22 (no exception asserted in every case) |
| `resolve_notification_entity_label` | BUG-200 | NEL-R-08, NEL-R-10, NEL-R-12, NEL-R-15 |
