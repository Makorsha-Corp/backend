# Spec — `app/utils/order_catalog_items.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### New questions

### Q1. Custom duplicate-message template is never used — 🗑️ remove
**Background:** The duplicate-line check accepts an optional message template (`detail_template`) so a caller could word the 409 message differently. All three callers (purchase orders, sales orders, transfer orders) leave it out, so every order type always gets the built-in wording. A template containing any placeholder other than `{name}` (or a stray `{`) would crash with a formatting error instead of producing the 409.
**What happens today:** The option exists but no code path reaches it; the message is always "`<item name>` appears more than once on this order".
**Example:** A purchase order with two lines for "Steel Rod" is rejected with 409 "Steel Rod appears more than once on this order"; nothing in the product can produce any other wording, and the template branch is only exercised by tests.
**Rules affected:** `assert_unique_catalog_item_ids` R6, R7
**Answer:** remove (reviewer accepted suggestion)
**Suggested answer:** remove
**Resolution:** the `detail_template` parameter and its branch are dead code, to be removed (reviewer); logged in `order_catalog_items.deadcode-staging.md`. Not a bug — no BUG ID. The function itself stays; only the built-in message is specified (`assert_unique_catalog_item_ids` R6). Former R7 deleted.

### Q2. Empty item name produces a nameless 409 message — 🐞 BUG-220
**Background:** Catalog item names are required but the database accepts an empty string (HR-1 says names are never blank, but legacy/unguarded rows may exist). The minimum-quantity check already falls back to `Item #<id>` when the name is empty; the duplicate-line check and the "already on this order" message do not.
**What happens today:** For an item whose `name` is `""`, the messages read `" appears more than once on this order"` and `" is already on this order"` (leading space, no item named).
**Example:** Item 42 has an empty name; an order listing it twice is rejected with 409 `" appears more than once on this order"` — the user cannot tell which line is wrong.
**Rules affected:** `assert_unique_catalog_item_ids` R5a, `catalog_item_already_on_order_detail` R3
**Answer:** bug — fall back to `Item #<id>` whenever the item is missing **or** its name is empty, matching `assert_meets_minimum_order_quantities` R7 (best-practice default, delegated by reviewer)
**Resolution:** both messages use `Item #<id>` for an empty name. Rules: `assert_unique_catalog_item_ids` R5a, `catalog_item_already_on_order_detail` R3. Logged in `order_catalog_items.bugs-staging.md`. (best-practice default, delegated by reviewer)

## Overview
Shared validation for the line items of orders that reference catalog items. It
rejects an order payload that lists the same catalog item twice (409), builds the
"already on this order" message used when adding a line to an existing order, and
rejects sales-order lines whose quantity is below the sellable product's minimum
order quantity (422). Callers: `PurchaseOrderManager` and `TransferOrderManager`
(duplicate check on create), `SalesManager.create_sales_order_with_items`
(duplicate check, then minimum-quantity check), and the transfer-order /
work-order "catalog item not already on order" guards (message helper). Free-text
lines (no catalog item) are never checked.

**Callables:** 3 specified · 0 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Notes for the test designer:**
- Plain functions; call them directly with the test DB session. `get_item_id` /
  `get_quantity` are caller-supplied accessors — pass simple lambdas over dicts
  or small objects.
- Catalog items (`items` table) have no soft-delete column; they have
  `is_active`. Products (`products` table) have `is_deleted` and `is_active`, and
  a DB unique constraint on (`workspace_id`, `item_id`, `factory_id`,
  `is_available_for_sale`) — so at most one product row matches a lookup.
- `products.min_order_qty` is `Integer`, nullable (schema type `int | None`); it renders in messages as a plain integer, e.g. `5`.
- `Product.item_name` is the linked catalog item's `name` (`items.name` is NOT
  NULL, but may be an empty string).

## Not specified
- `assert_unique_catalog_item_ids(..., detail_template=...)` parameter — dead code, to be removed (reviewer). Tests must not pass it.

---

## `assert_unique_catalog_item_ids(session, workspace_id, entries, *, get_item_id)`
**Shape:** validator
**Persistence:** reads
**Visibility:** public (used by: `PurchaseOrderManager` create, `SalesManager.create_sales_order_with_items`, `TransferOrderManager` create)

**Purpose:** Reject an order payload that lists the same catalog item on more than one line.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | DB session, used only to look up the item's name for the message |
| workspace_id | int | Workspace used for the name lookup only |
| entries | iterable | Order lines; any iterable, may be empty; consumed once |
| get_item_id | callable | Returns the line's catalog item id, or `None` for a free-text line |

**Returns:** `None` when no catalog item id repeats.

**Rules:**
- **R1.** An empty iterable passes (returns `None`).
- **R2.** Lines whose item id is `None` are skipped entirely: any number of free-text lines pass, and they never count as duplicates of each other or of catalog lines. Only `None` is skipped — an item id of `0` is treated as a real id and deduplicated like any other.
- **R3.** Lines with all-distinct item ids pass, whatever their count.
- **R4.** When an item id appears a second time, the function raises `HTTPException` 409 at that second occurrence; lines after it are not examined. With several different duplicated ids, the message names the id whose second occurrence comes first in line order.
- **R5.** The name in the message is the catalog item's `name` when an item with that id exists **in `workspace_id`** (inactive items included — `is_active` is ignored). When no such item exists in that workspace (unknown id, or an item that belongs to another workspace) the name is `Item #<id>`, so another workspace's item name is never revealed.
- **R5a.** [BUG-220] When the matching item exists but its `name` is the empty string, the name in the message is `Item #<id>` (e.g. `"Item #42 appears more than once on this order"`). *(Today: the empty name is used, giving `" appears more than once on this order"`.)* (best-practice default, delegated by reviewer)
- **R6.** The 409 detail is exactly `"<name> appears more than once on this order"` (e.g. `"Steel Rod appears more than once on this order"`). ✅ *(The `detail_template` parameter is dead code to be removed — reviewer, Q1; former R7 deleted.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Same non-`None` item id on two lines | `HTTPException` 409 | `"<name> appears more than once on this order"` |

**Side effects:** none (read-only lookup of the item name, only when a duplicate is found).

---

## `catalog_item_already_on_order_detail(session, *, item_id, workspace_id)`
**Shape:** helper
**Persistence:** reads
**Visibility:** public (used by: `TransferOrderManager` "item not already on order" guard, `WorkOrderManager._ensure_catalog_item_not_on_wo`)

**Purpose:** Build the 409 message shown when a catalog item is added to an order that already has a line for it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | DB session |
| item_id | int | Catalog item id |
| workspace_id | int | Workspace the item is looked up in |

**Returns:** a string; never raises for a missing item.

**Rules:**
- **R1.** When an item with `item_id` exists in `workspace_id` (active or inactive), returns `"<item name> is already on this order"`.
- **R2.** When no item with that id exists in that workspace (unknown id, or it belongs to another workspace), returns `"Item #<item_id> is already on this order"`.
- **R3.** [BUG-220] When the item exists but its `name` is the empty string, returns `"Item #<item_id> is already on this order"`. *(Today: returns `" is already on this order"`.)* (best-practice default, delegated by reviewer)

**Errors:** none.

**Side effects:** none.

---

## `assert_meets_minimum_order_quantities(session, workspace_id, factory_id, entries, *, get_item_id, get_quantity)`
**Shape:** validator
**Persistence:** reads
**Visibility:** public (used by: `SalesManager.create_sales_order_with_items`, with the order's `factory_id` and each line's `quantity_ordered`)

**Purpose:** Reject order lines whose quantity is below the minimum order quantity of the product being sold from that factory.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | DB session |
| workspace_id | int | Workspace of the product lookup |
| factory_id | int | Factory the order sells from |
| entries | iterable | Order lines; may be empty; consumed once |
| get_item_id | callable | Line's catalog item id, or `None` for free-text |
| get_quantity | callable | Line's quantity (the sales caller supplies a `Decimal`) |

**Returns:** `None` when every line meets its minimum.

**Rules:**
- **R1.** An empty iterable passes.
- **R2.** Free-text lines (item id `None`) are skipped; their quantity is never read.
- **R3.** For a catalog line, the minimum comes from the product matching all of: same workspace, same `factory_id`, same `item_id`, `is_available_for_sale = True`, and not soft-deleted. The product's `is_active` flag is not considered.
- **R4.** No matching product (none exists; product only for another factory or workspace; product not available for sale; product soft-deleted) → the line passes whatever its quantity.
- **R5.** Matching product with `min_order_qty` `None` or `0` → no minimum; the line passes whatever its quantity (including 0 or negative).
- **R6.** Matching product with a positive `min_order_qty`: quantity exactly equal to the minimum passes; quantity above passes; quantity below (e.g. `Decimal("4.5")` against 5) raises `HTTPException` 422.
- **R7.** The 422 detail is `"Minimum order quantity for <name> is <min_order_qty> (requested <quantity>)"`, where `<min_order_qty>` renders as a plain integer because `products.min_order_qty` is an `Integer` column (e.g. `5`, never `5.00`), `<quantity>` is the value returned by `get_quantity` rendered with `str()` (e.g. `Decimal("4.5")` → `4.5`), and `<name>` is the product's catalog item name, or `Item #<item_id>` when that name is empty.
- **R8.** Lines are checked in order and the first failing line raises; later lines are not examined.
- **R9.** If `get_quantity` returns `None` for a catalog line whose product has a positive minimum, a `TypeError` is raised (no caller can produce this: the sales input schema requires `quantity_ordered`).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Quantity below a positive product minimum | `HTTPException` 422 | `"Minimum order quantity for <name> is <min> (requested <qty>)"` |

**Side effects:** none.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 20 | loop over entries: empty / one / many | `assert_unique_catalog_item_ids` R1, R3 |
| 22 | item id is `None` → continue | `assert_unique_catalog_item_ids` R2 |
| 24 | item id already seen → raise 409 / else add | `assert_unique_catalog_item_ids` R3, R4 |
| 25 (BaseDAO `get_by_id_and_workspace`) | item filtered by id + workspace | `assert_unique_catalog_item_ids` R5 |
| 28 | item found → name / not found → `Item #<id>`; found with empty name | `assert_unique_catalog_item_ids` R5, R5a |
| 29–32 | fixed detail message (template branch is dead code, removed) | `assert_unique_catalog_item_ids` R6 |
| 38 (BaseDAO `get_by_id_and_workspace`) | item filtered by id + workspace | `catalog_item_already_on_order_detail` R1, R2 |
| 41 | item found / not found; found with empty name | `catalog_item_already_on_order_detail` R1, R2, R3 |
| 57 | loop over entries: empty / one / many; first failure stops | `assert_meets_minimum_order_quantities` R1, R8 |
| 59 | item id is `None` → continue | `assert_meets_minimum_order_quantities` R2 |
| 62 (`ProductDAO.get_by_factory_item_available`) | workspace / factory / item / for-sale / not-deleted filters | `assert_meets_minimum_order_quantities` R3, R4 |
| 66 | product is `None` | `assert_meets_minimum_order_quantities` R4 |
| 66 | `min_order_qty` falsy (None / 0) | `assert_meets_minimum_order_quantities` R5 |
| 66 | quantity < min / == min / > min; quantity `None` | `assert_meets_minimum_order_quantities` R6, R9 |
| 67 | `item_name` truthy / empty | `assert_meets_minimum_order_quantities` R7 |

## Gap log
- G1 (order_catalog_items.cases.md gap 1) — Fact — `products.min_order_qty` is an `Integer` column: added to Overview notes and `assert_meets_minimum_order_quantities` R7 (`<min_order_qty>` renders as e.g. `5`).
- G2 (order_catalog_items.cases.md gap 2) — Intent (decided by best practice, delegated by reviewer) — new Q2 resolved as BUG-220: empty item name falls back to `Item #<id>`; added `assert_unique_catalog_item_ids` R5a and `catalog_item_already_on_order_detail` R3.
