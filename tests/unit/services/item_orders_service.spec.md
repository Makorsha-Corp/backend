# Spec — `app/services/item_orders_service.py`

> **Status:** APPROVED (2026-11-10; OQ-33 answered by the owner and applied (BUG-2490, BUG-2491); case-designer gaps 1–4 closed, see Gap log)
> **Source commit:** e48a092

> **Review round 2026-11-10 (low supervision).** No owner answer in this round. **Delegated:** every bug below was decided by Claude under the reviewer's delegation (2026-11-10); none is the owner's own answer. **Owner:** Q5 (OQ-33, how partly priced or zero-priced purchase and sales orders show their unit price and line total) is parked in `docs/testing/owner-questions.md`, not blocking: `_purchase_rows` R7, R8 and `_sales_rows` R5 describe today's behaviour and are marked "pending owner".
>
> **Review round 2026-11-10 (owner answer + fill-gaps).** **Owner:** OQ-33 answered 2026-11-10 ("divide by the priced quantity only; a zero-priced order shows 0.00"), applied to `_purchase_rows` R7, R8a and `_sales_rows` R4, R5a as BUG-2490 and BUG-2491; "pending owner" removed (the round note above is kept as history). **Fill-gaps:** gaps 1–4 of `item_orders_service.cases.md` are facts, answered from the code and the models (Facts; `get_orders_for_item` R13; `_purchase_rows` R12; see Gap log). Nothing else changed.
>
> **Collaborators already specified and not restated:** `ItemManager.get_item` — `tests/unit/managers/item_manager.spec.md` (R1–R5; BUG-937). The DAO-level facts of the order tables are in the approved DAO specs (`tests/unit/dao/work_order_item.spec.md`, `sales_order_item.spec.md`, `sales_order.spec.md`). This service does not inherit `BaseService`; it only reads, so of the Transaction contract (`tests/unit/services/base_service.spec.md` TC1–TC6) only **TC6** applies (see `get_orders_for_item` R12).
>
> **Standing decisions applied here (not asked again):** a list order is deterministic only if it ends in a unique key (HR-6, `tied-timestamp-no-tiebreak`); voided records are left out of reports where a sibling report or the same report leaves them out (BUG-717, BUG-1876); HR-16: a row linking to another workspace's row is invalid data and the response never shows that workspace's names or ids (BUG-1086, BUG-1801 precedent: such a row is treated as not found); HR-15: money rounds half up to 2 places.
>
> **Verified by running** (my own script `v1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsup\io\`, one transaction on `marker_test`, rolled back, private `COVERAGE_FILE`; session `TimeZone` was `America/New_York`): purchase rows for a dated PO, a voided PO (left out), a PO with no `order_date` (date = UTC day of `created_at`), a PO partly priced (10 @ 50.00 + 10 unpriced → quantity `20.00`, unit price `2.5`, line total `50.00`), a PO with 3 for `100.00` (unit price `33.33333333333333333333333333`), a PO priced `0.00` (unit price `0`, line total `None`), a PO with quantity 0 and no price (both `None`); labels `Storage (F1)`, `Storage` (factory of another workspace), `Machine #<id>` (machine of another workspace — id shown), `Component #999999` (missing), `weird #7` (unknown type); another workspace's status and account names shown (`ForeignStatus`, `ForeignAcc`); a deleted item (`is_active = False`) still answers; item of another workspace → `NotFoundError` 404 `Item with ID <id> not found`; `from_date` alone ignored (all rows); one-day range; reversed range → 0 rows; `exclude_purchase_order_id` = an id (left out) and `0` (no effect); **any work order line of the item → `AttributeError: 'str' object has no attribute 'value'`** (both with `order_type="work_order"` and with no type); in SQL, the work-order query keeps a `VOIDED` and an `is_deleted` work order and drops a deleted line; transfer rows (two lines 4 + 1.5 → `5.50`; no price, account or label); sales rows (only lines with this `item_id`; a free-text line left out); paging `skip=2, limit=3` (total 7, three rows); `limit=0` (total 7, no rows); **three POs created within one clock tick had equal `created_at` and came back in different orders on two runs** (`PO-G, PO-C, PO-D, PO-E` vs `PO-D, PO-E, PO-G, PO-C`). **Read, not run:** `GET /items/{id}/orders/` (`app/api/v1/endpoints/items.py`), the web app's callers (item Overview "recent purchases", Purchasing section, PO "purchase history" dialog). **Not run:** anything over HTTP.

## Review
> All answered or parked; applied 2026-11-10.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | Any item that appears on a work order makes the whole order list fail (500) | bug — BUG-2550 | delegation (clear crash) |
| Q2 | Voided work orders are listed though voided purchase orders are left out | bug — BUG-2552 | delegation (voided rows, BUG-1876 precedent) |
| Q3 | Deleted work orders are listed (only deleted lines are dropped) | bug — BUG-2553 | delegation (HR-4) |
| Q4 | A date filter with only "from" or only "to" is silently ignored | bug — BUG-2556 | delegation (silently ignored input) |
| Q5 | **OWNER** — a partly priced order spreads its priced total over all its quantity; an order priced at 0.00 shows unit price 0 but no line total | bug — BUG-2490, BUG-2491 (OQ-33) | owner (2026-11-10) |
| — | Order history of a deleted item stays reachable (item manager FU-3) | intended, no bug | delegation |

Decided by house rules: unstable order on ties (BUG-2551), unit price not rounded (BUG-2554), another workspace's names and ids shown (BUG-2555).

### House-rule violations — applied automatically

- **HR-6** `get_orders_for_item` R6 — rows are sorted by date, then `created_at`, newest first, with nothing after that. Rows with the same date and `created_at` (verified: three POs created within one clock tick; work orders created in one transaction share the database's `now()`) come back in the database's arbitrary order, which changed between two runs, so paging can repeat or skip an order. Intended: date newest first, `created_at` newest first, then order type in the fixed order purchase → transfer → sales → work, then order id descending.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2551 (pattern `tied-timestamp-no-tiebreak`). Rules: `get_orders_for_item` R6.
- **HR-15** `_weighted_unit_price` R3 — the unit price is the line total divided by the quantity with no rounding (verified `100.00 / 3` → `33.33333333333333333333333333`). Intended: rounded to 2 decimal places, half away from zero (`33.33`; `0.125` → `0.13`).
**Answer:** bug — per HR-15 (house rule)
**Resolution:** 🐞 BUG-2554 (pattern `unrounded-money-output`, new). Rules: `_weighted_unit_price` R3.
- **HR-16** `_purchase_rows` R10, `_sales_rows` R6, `_transfer_rows` R4, `_build_po_destination_labels` R7 — the account and status are joined by id only, and the destination fallback label shows the raw id. A PO of this workspace whose account, status or destination machine belongs to another workspace shows that workspace's account name, status name and machine id (verified: `ForeignAcc`, `ForeignStatus`, `Machine #<id>`); a component of this workspace under another workspace's project shows that project's name. Intended (BUG-1086 / BUG-1801 precedent): such an order is treated as not found — left out of the rows and of `total`.
**Answer:** bug — per HR-16 (house rule)
**Resolution:** 🐞 BUG-2555 (pattern `cross-workspace-row-exposed`). Rules: `_purchase_rows` R10, `_sales_rows` R6, `_transfer_rows` R4, `_build_po_destination_labels` R7.

Checked and **not** a new line here: **HR-4** — the item: a deleted item still answers (see Q-line "deleted item" above and `get_orders_for_item` R2); destination labels name a deleted factory or machine, which is right for order history (decided by Claude under the reviewer's delegation (2026-11-10)); work orders are Q3. Purchase, transfer and sales orders and their lines have no soft-delete column. **HR-5** — all filters are applied before paging; paging is done in Python on the full filtered list, so pages are never short (a performance matter only). **HR-7** — the service accepts `limit=0` (empty page) but the endpoint requires `1 ≤ limit ≤ 100` and `skip ≥ 0`. **HR-8** — no text search. **HR-9, HR-10** — nothing is written. **HR-1 … HR-3** — no names stored. **Falsy values** — `exclude_purchase_order_id=0` is applied (matches no PO, verified); a `destination_id` of `0` gets no label (`_build_po_destination_labels` R1).

### New questions

### Q1. Any work order line of the item makes the list fail — 🐞 BUG-2550
**Background:** `GET /items/{id}/orders/` merges purchase, transfer, sales and work orders. A work order's `status` is stored as plain text (`"DRAFT"`, `"IN_PROGRESS"`, `"COMPLETED"`, `"VOIDED"`), but the code reads it as if it were an enum member (`status.value`).
**What happens today:** as soon as the item is on any live line of any work order of the workspace, the call raises `AttributeError` → 500, with or without `order_type=work_order`. Items never used on a work order work.
**Example:** "Bolt M8" is consumed by work order WO-0012. Opening the item's Purchasing section or the PO's "purchase history" dialog with no type filter shows an error instead of the item's 14 purchase orders.
**Rules affected:** `_work_rows` R5
**Answer:** bug — `status_name` is the stored status text (`"DRAFT"` …), the call succeeds
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10; a crash, no choice involved): 🐞 BUG-2550 (pattern `enum-access-on-plain-string`, new). Rules: `_work_rows` R5.

### Q2. Voided work orders are listed — 🐞 BUG-2552
**Background:** Purchase orders have a `voided` flag and this same list leaves voided POs out. Work orders are voided by setting `status = "VOIDED"`. The calendar leaves voided work orders out (BUG-1876, owner, OQ-14); voided POs are left out of the incoming-stock summary (BUG-717).
**What happens today:** a voided work order that used the item is listed and counted in `total`, with status `VOIDED`.
**Example:** WO-0040 was created by mistake for 50 bolts and voided. The bolt's order list still shows it next to the real orders, and the count says 15 orders instead of 14.
**Rules affected:** `_work_rows` R2
**Answer:** bug — work orders with status `VOIDED` are left out, as voided purchase orders are
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10; voided rows, BUG-1876 precedent): 🐞 BUG-2552 (pattern `voided-record-not-excluded`). Rules: `_work_rows` R2.

### Q3. Deleted work orders are listed — 🐞 BUG-2553
**Background:** Work orders and their lines are soft-deleted (`is_deleted = True`, the row stays). The query drops deleted lines but never looks at the work order's own flag.
**What happens today:** a deleted work order whose lines were not deleted with it is listed and counted (verified in SQL).
**Example:** A planner deletes work order WO-0051 (its lines stay as they were). The bolt's order list still shows WO-0051.
**Rules affected:** `_work_rows` R3
**Answer:** bug — a deleted work order is left out, whatever its lines' flag (HR-4)
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10): 🐞 BUG-2553 (pattern `join-ignores-soft-deleted`). Rules: `_work_rows` R3.

### Q4. A half-open date range is silently ignored — 🐞 BUG-2556
**Background:** The endpoint documents `from_date` as "requires to_date" and `to_date` as "requires from_date", but enforces neither. The service applies the range only when both are given.
**What happens today:** `?from_date=2030-01-01` alone returns every order of the item, as if no date was sent (verified).
**Example:** An API client asks for "orders since 1 Oct" with only `from_date`; it gets two years of orders and no hint the filter was dropped.
**Rules affected:** `get_orders_for_item` R4a
**Answer:** bug — one bound without the other is refused (422), nothing returned
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10; silently ignored input, BUG-1960 / BUG-2255 precedent; the endpoint already documents both as required together): 🐞 BUG-2556 (pattern `silently-ignored-input`). The check belongs in the endpoint (or a query model); the service keeps ignoring a lone bound. Rules: `get_orders_for_item` R4a. The web app always sends both or neither.

### Q5. **OWNER** — Partly priced and zero-priced orders — 🐞 BUG-2490, BUG-2491 (OQ-33)
**Background:** A PO line may have no price (`unit_price` and `line_subtotal` empty). For each order the list shows one row for the item: `quantity` = sum of the item's ordered quantities, `line_total` = sum of the priced subtotals, `unit_price` = `line_total / quantity`. A line total of 0 or less is shown as empty. Which price a buyer should see is a money decision.
**What happens today:** (a) PO with 10 bolts at 5.00 (50.00) and 10 unpriced bolts → quantity 20, unit price 2.50, line total 50.00 (verified). (b) PO or sales order priced at 0.00 → unit price 0, line total empty (verified for the PO).
**Example:** The "purchase history" dialog on a new PO shows the bolt was last bought at 2.50 when every priced bolt cost 5.00; a free sample order shows "0.00" each but no total.
**Rules affected:** `_purchase_rows` R7, R8; `_sales_rows` R5
**Suggested answer:** bug — the unit price is the priced subtotal divided by the **priced** quantity (5.00 in (a)); `line_total` is the priced subtotal, 0.00 included; both are empty only when no line of the item is priced.
**Alternatives:** (a) intended — keep today's spread. (b) unit price empty whenever any line is unpriced.
**Answer:** owner, 2026-11-10 (OQ-33): suggested answer — divide by the priced quantity only; a zero-priced order shows 0.00.
**Resolution:** 🐞 BUG-2490 (pattern `unpriced-line-counted-as-zero`, as BUG-2524): the unit price is the priced subtotal over the **priced** quantity, rounded half up to 2 places (HR-15, with BUG-2554). 🐞 BUG-2491 (pattern `falsy-zero-treated-as-missing`): `line_total` is the priced sum, 0.00 included; unit price and line total are both empty only when no line of the item is priced. A PO line is "priced" when its `line_subtotal` is set. Sales lines always have `unit_price` and `line_total` (both NOT NULL), so for sales only BUG-2491 applies. `quantity` still counts every line. Rules: `_purchase_rows` R7, R7a, R8, R8a; `_sales_rows` R4, R5, R5a.

### Decided without a question
- **Deleted item** (item manager spec FU-3): the order history of a deleted item stays reachable — old orders link to it from the PO pages. Decided by Claude under the reviewer's delegation (2026-11-10). Today `get_item` returns deleted items, so this holds; when BUG-937 is fixed this service must call `get_item(..., include_deleted=True)`. `get_orders_for_item` R2 guards it; no bug today.

## Follow-ups for other reviews
> Nothing below is a rule of this service and no bug is logged for it here.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **BUG-937 fix** (`app/managers/item_manager.py` `get_item`) | When `include_deleted` is added, this service passes `include_deleted=True` (see "Decided without a question"), otherwise `get_orders_for_item` R2 fails. | item manager FU-3 |
| FU-2 | **Permissions work** (`docs/future/permissions.md`) | Any active member of the workspace reads every order of an item with supplier names and purchase prices. Routed, not decided here. | reading the endpoint |
| FU-3 | **Work order model** (`created_at` server default) | Work order dates here are the date of `created_at`, which the database stamps with `now()` in the session time zone (pattern `database-clock-timestamp`, existing); transfer and PO dates are UTC. Not this module's rule. | verified run |

## Overview
`ItemOrdersService` answers `GET /items/{item_id}/orders/`: every purchase, transfer, sales and work order of the caller's workspace that has the item on at least one line, **one row per order**, newest first, with optional order-type and date filters and a PO to leave out (the PO page uses it to show "other purchases of this item"). Rows carry the order number, a date, the item's summed quantity, a weighted unit price and line total (purchase and sales only), the status name, the account name (purchase and sales) and a destination label (purchase only). It reads only; it holds no state (module singleton `item_orders_service`). It is meant to protect workspace isolation and to show each order once.

**Callables:** 9 specified · 1 not specified
**Externals to mock:** none.
**Integration-only behavior:** none (the date of `created_at` is a plain `CAST(... AS DATE)`).

**Facts for the test designer**
- Import: `from app.services.item_orders_service import ItemOrdersService, item_orders_service, _dec, _in_date_range, _weighted_unit_price, _build_po_destination_labels`. `ItemOrdersService()` takes no arguments. All parameters after `db` are keyword-only, except the module helpers' positional ones as listed.
- Response schemas: `app/schemas/item_orders.py`. `ItemOrderRowResponse` fields: `order_type` (`'purchase_order' | 'transfer_order' | 'sales_order' | 'work_order'`), `order_id`, `order_number`, `order_date` (date or None), `quantity` (Decimal), `unit_price`, `line_total` (Decimal or None), `status_name`, `account_name`, `destination_label` (str or None), `created_at` (datetime). `ItemOrdersListResponse`: `items`, `total`.
- `NotFoundError` is `app.core.exceptions.NotFoundError` (status 404, `.detail`).
- Model facts used: `purchase_orders.order_date` nullable Date, `voided` bool, `destination_type` (`storage` → factory id, `machine` → machine id, `project` → project component id) and `destination_id` NOT NULL; `purchase_order_items.quantity_ordered` NOT NULL, `line_subtotal` nullable; `transfer_orders` and `transfer_order_items` have no soft delete, no void, no price; `sales_orders.order_date` NOT NULL (default today), `account_id` NOT NULL; `sales_order_items.item_id` nullable (free-text lines), `line_total` NOT NULL; `work_orders.status` is `String(20)` (values of `WorkOrderStatusEnum`), `is_deleted`; `work_order_items.is_deleted`. `created_at` of POs, transfers, sales orders: Python `utcnow()`; of work orders: database `now()`.

- **Date columns (gap 2):** every `created_at` here (`purchase_orders`, `transfer_orders`, `sales_orders`, `work_orders`) is `DateTime` without time zone (`timestamp without time zone`, naive). The date is `CAST(created_at AS DATE)` in SQL: the stored wall-clock date, which the session `TimeZone` does not change. POs, transfers and sales orders store Python `utcnow()` (so the date is the UTC day: `created_at` 2026-11-10 23:30 → 2026-11-10 even under `America/New_York`); work orders store the database `now()`, converted to the session time zone at insert (FU-3). A test that sets `created_at` explicitly gets exactly that day. `purchase_orders.order_date` is a nullable `Date`; `sales_orders.order_date` is `Date` NOT NULL.
- **Minimum rows (gap 4)** — NOT NULL columns with no default, and foreign keys (`NN` = NOT NULL):

  | Table | Required (no default) | Foreign keys |
  |---|---|---|
  | `purchase_orders` | `workspace_id`, `po_number`, `destination_type`, `destination_id`, `current_status_id`, `created_by` | `workspace_id`→workspaces NN, `current_status_id`→statuses NN, `created_by`→profiles NN; nullable: `account_id`→accounts, `order_workflow_id`, `invoice_id`, `voided_by`, `updated_by` |
  | `purchase_order_items` | `workspace_id`, `purchase_order_id`, `line_number`, `item_id`, `quantity_ordered` | `purchase_order_id`→purchase_orders NN, `item_id`→items NN, `workspace_id` NN; `unit_price`, `line_subtotal` nullable `Numeric(15,2)` |
  | `transfer_orders` | `workspace_id`, `transfer_number`, `source_location_type`, `source_location_id`, `destination_location_type`, `destination_location_id`, `current_status_id`, `created_by` | `current_status_id`→statuses NN, `created_by`→profiles NN; nullable: `updated_by`, `completed_by` |
  | `transfer_order_items` | `workspace_id`, `transfer_order_id`, `line_number`, `item_id`, `quantity` | `transfer_order_id`→transfer_orders NN, `item_id`→items NN; nullable `approved_by` |
  | `sales_orders` | `workspace_id`, `sales_order_number`, `account_id`, `factory_id`, `current_status_id`, `created_by` | `account_id`→accounts NN, `factory_id`→factories NN, `current_status_id`→statuses NN, `created_by`→profiles NN; nullable: `invoice_id`, `completed_by`, `updated_by` |
  | `sales_order_items` | `workspace_id`, `sales_order_id`, `quantity_ordered`, `unit_price`, `line_total` | `sales_order_id`→sales_orders NN; `item_id`→items nullable |
  | `work_orders` | `workspace_id`, `work_order_number`, `work_order_type_id`, `title`, `factory_id` | `work_order_type_id`→work_order_types NN, `factory_id`→factories NN; nullable: `machine_id`, `project_component_id`, `account_id`, `work_order_template_id`, `invoice_id`, the `*_by` profile links |
  | `work_order_items` | `workspace_id`, `work_order_id`, `item_id`, `quantity` | `work_order_id`→work_orders NN, `item_id`→items NN |
  | `statuses` | `workspace_id`, `name`, `comment` | `workspace_id`→workspaces NN |

  Every line table has its own `workspace_id` NOT NULL. Soft-delete columns: `work_orders.is_deleted`, `work_order_items.is_deleted`, `accounts.is_deleted` (NOT NULL, with a default); purchase orders use `voided`; transfer and sales tables have none.

**Notes for the test designer**
- Equal `created_at`: set it explicitly on rows to make ties (do not rely on the clock).
- Work-order rows cannot be read today without the crash (BUG-2550); every case that puts the item on a live work order line in scope is expected to fail until the fix, including the no-type call. Cases about other types must keep the item off work orders, or filter by type.

## Not specified
- `item_orders_service` — module-level instance, no logic.

---

## `_dec(value)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: `_purchase_rows`, `_transfer_rows`, `_sales_rows`, `_work_rows`)

**Purpose:** Turn a database sum into a `Decimal`, empty as zero.

**Returns:** `Decimal`.

**Rules:**
- **R1.** `None` → `Decimal(0)`.
- **R2.** Any other value → `Decimal(str(value))` (a `Decimal('10.00')` stays `Decimal('10.00')`; a float `0.1` gives `Decimal('0.1')`, not its binary expansion).
- **R3.** A value whose string is not a number (e.g. `"abc"`) raises `decimal.InvalidOperation`.

**Errors:** R3. **Side effects:** none.

---

## `_in_date_range(column, from_date, to_date)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: the four `_*_rows` methods)

**Purpose:** An inclusive date-range condition.

**Rules:**
- **R1.** Returns a SQL condition true when `from_date <= column <= to_date` — both ends included; a reversed range (`from_date > to_date`) matches nothing.

**Errors:** none. **Side effects:** none.

---

## `_weighted_unit_price(line_total, quantity)`
**Shape:** compute · **Persistence:** pure · **Visibility:** internal (used by: `_purchase_rows`, `_sales_rows`)

**Purpose:** Average price per unit of the item on one order.

**Rules:**
- **R1.** `quantity` of 0 or less → `None`.
- **R2.** Otherwise `line_total / quantity` (a `line_total` of 0 gives `Decimal('0')`).
- **R3.** [BUG-2554] The result is rounded to 2 decimal places, half away from zero (HR-15): `100.00 / 3` → `33.33`; `0.25 / 2` → `0.13`. *(Today: not rounded — `33.33333333333333333333333333`, `0.125`.)*

**Errors:** none. **Side effects:** none.

---

## `_build_po_destination_labels(db, *, workspace_id, destinations)`
**Shape:** mapper · **Persistence:** reads · **Visibility:** internal (used by: `_purchase_rows`)

**Purpose:** A readable label for each PO destination.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | caller's workspace |
| `destinations` | sequence of `(type, id)` | duplicates allowed |

**Returns:** dict `(type, id) → label`.

**Rules:**
- **R1.** Pairs whose id is falsy (`0`, `None`) are ignored: no key for them. If no pair remains → `{}` and nothing is read.
- **R2.** `('storage', id)` of a factory of the workspace → `Storage (<factory name>)`.
- **R3.** `('machine', id)` of a machine of the workspace → `Machine (<machine name>)`.
- **R4.** `('project', id)` of a project component of the workspace → `Project · <project name> / <component name>` (middle dot U+00B7, spaces as shown).
- **R5.** Soft-deleted factories and machines are still named (intended: history; decided by Claude under the reviewer's delegation (2026-11-10)).
- **R6.** A storage / machine / project id not found in the workspace → `Storage`, `Machine #<id>`, `Component #<id>`; any other type → `<type> #<id>` (e.g. `weird #7`). Each pair appears once however many times it was given.
- **R7.** [BUG-2555] A destination that exists in **another** workspace (factory, machine, component — or a component of this workspace whose project is another workspace's) gives no label and its PO is left out (`_purchase_rows` R10). *(Today: factory → `Storage`, machine → `Machine #<their id>`, component of another workspace → `Component #<their id>`, foreign project → its name shown.)* A missing id (no row anywhere) keeps the R6 label.

**Errors:** none. **Side effects:** none.

---

## `ItemOrdersService.get_orders_for_item(db, *, workspace_id, item_id, skip=0, limit=50, order_type=None, from_date=None, to_date=None, exclude_purchase_order_id=None)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /items/{item_id}/orders/`, which passes every parameter; `skip ≥ 0`, `1 ≤ limit ≤ 100` enforced there)

**Purpose:** The orders of the workspace that include the item, newest first, one page.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | caller's workspace |
| `item_id` | int | item |
| `skip`, `limit` | int | Python slice; not validated here |
| `order_type` | one of the four types or `None` | `None` = all four |
| `from_date`, `to_date` | date or `None` | used only together |
| `exclude_purchase_order_id` | int or `None` | applies to POs only |

**Returns:** `ItemOrdersListResponse(items=<page>, total=<number of rows before paging>)`.

**Rules:**
- **R1.** Item missing or of another workspace → `NotFoundError` 404 `Item with ID <item_id> not found`; nothing else is read (see `ItemManager.get_item` R2).
- **R2.** A deleted item (`is_active = False`) of the workspace still answers with its orders (intended; see "Decided without a question"). After the BUG-937 fix this needs `include_deleted=True` (FU-1).
- **R3.** `order_type=None` → rows of all four types; a type given → only that type's rows (and only that type's query runs: e.g. `order_type='purchase_order'` is not affected by BUG-2550).
- **R4.** Both `from_date` and `to_date` given → each type keeps only orders whose date (as defined per type) is within the range, both ends included; reversed range → no rows, `total = 0`.
- **R4a.** [BUG-2556] Only one of `from_date` / `to_date` given → refused, 422 (in the endpoint; nothing returned). *(Today: the lone bound is ignored and all rows are returned.)* At the service a lone bound keeps being ignored.
- **R5.** `exclude_purchase_order_id` → that PO is left out (see `_purchase_rows` R4); other types unaffected.
- **R6.** Rows are sorted by date newest first, then `created_at` newest first. [BUG-2551] Remaining ties (same date and `created_at`) are broken by type in the order purchase → transfer → sales → work, then `order_id` descending (HR-6). *(Today: no further key; tied rows of one type come in the database's arbitrary order — verified to change between runs; across types they keep the order purchase, transfer, sales, work.)*
- **R7.** `total` = number of rows after all filters, before paging.
- **R8.** `items` = rows `skip … skip+limit-1` of the sorted list; `skip` beyond the end → `[]`; `limit=0` → `[]` with `total` unchanged.
- **R9.** An item with no orders → `items = []`, `total = 0`.
- **R10.** Only orders of `workspace_id` are listed (each type filters on the order's `workspace_id`).
- **R11.** Every order appears at most once, however many lines it has for the item.
- **R13.** The sort of R6 is done **in Python** on the combined list (`list.sort`, key `(order_date or date.min, created_at)`, `reverse=True`); none of the four queries has an `ORDER BY`. Python's sort is stable, so today a tie keeps the order the rows were built in: all purchase rows, then transfer, sales, work, and inside one type the database's row order (`GROUP BY` output, not fixed). The BUG-2551 tie-break belongs in this Python sort key (type rank, then `order_id` descending, consistent with `reverse=True`); an `ORDER BY` in the queries alone would not fix it.
- **R12.** Nothing is written, committed or rolled back: changes pending in the session stay pending (TC6 of `base_service.spec.md` in meaning; this class does not inherit `BaseService`). An exception from a collaborator reaches the caller unchanged.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| item missing / other workspace | `NotFoundError` (404) | `Item with ID <item_id> not found` |
| work order line in scope (today) | `AttributeError` | BUG-2550 |

**Side effects:** none.

---

## `ItemOrdersService._purchase_rows(db, *, workspace_id, item_id, from_date, to_date, exclude_purchase_order_id=None)`
**Shape:** list · **Persistence:** reads · **Visibility:** internal (used by: `get_orders_for_item`)

**Purpose:** One row per purchase order of the workspace that has the item.

**Rules:**
- **R1.** A PO is listed when it belongs to the workspace and has at least one line with `item_id`; lines of other items are ignored.
- **R2.** Voided POs (`voided = True`) are left out.
- **R3.** The row's date (`order_date`, also the date filtered on) = the PO's `order_date`, or, when empty, the date of `created_at` (UTC).
- **R4.** `exclude_purchase_order_id` given → that PO is left out; `0` or an unknown id leaves everything in.
- **R5.** `quantity` = sum of `quantity_ordered` over the item's lines on the PO (ordered, not received or returned).
- **R6.** `line_total` (internal) = sum of the non-empty `line_subtotal`s of those lines; no priced line → 0.
- **R7.** [BUG-2490] `unit_price` = R6's priced sum divided by the **priced quantity** (sum of `quantity_ordered` of the item's lines whose `line_subtotal` is set), rounded per `_weighted_unit_price` R3: 10 @ 5.00 (50.00) + 10 unpriced → `5.00`. Priced quantity 0 or less (incl. no priced line) → `None`. *(Today: divided by all the quantity, priced or not → `2.5`.)*
- **R7a.** With every line priced the fix changes nothing: 3 for `100.00` → `33.33` (rounding per BUG-2554); quantity 0 and no price → `unit_price None`.
- **R8.** The row's `line_total` = R6's sum when it is greater than 0 (e.g. `50.00`).
- **R8a.** [BUG-2491] When at least one line of the item is priced, `line_total` = R6's sum whatever its value: a PO priced at 0.00 shows `line_total` `0.00` and `unit_price` `0.00`. Only when no line is priced are both `None`. *(Today: a sum of 0 or less gives `line_total None`, while `unit_price` is `0`.)*
- **R9.** `status_name` = name of the PO's current status; `account_name` = the account's name, `None` when the PO has no account; `destination_label` from `_build_po_destination_labels` (missing key → `None`, e.g. destination id 0); `order_type='purchase_order'`, `order_id`, `order_number` = `po_number`, `created_at` = the PO's.
- **R10.** [BUG-2555] A PO whose account, status or destination belongs to another workspace is left out (HR-16). *(Today: listed with that workspace's account and status names and destination id.)*
- **R11.** Rows come in no defined order (ordering is `get_orders_for_item` R6).
- **R12.** Return shape (the same for all four `_*_rows` helpers): a plain Python `list` of `ItemOrderRowResponse` objects (Pydantic, see Facts), one per order. The internal total is not returned separately, only as the row's `line_total` field (R8 / R8a). No rows → `[]`. Fields a type does not fill (e.g. `unit_price` on transfer and work rows) are `None`.

**Errors:** none. **Side effects:** none.

---

## `ItemOrdersService._transfer_rows(db, *, workspace_id, item_id, from_date, to_date)`
**Shape:** list · **Persistence:** reads · **Visibility:** internal (used by: `get_orders_for_item`)

**Rules:**
- **R1.** One row per transfer order of the workspace with at least one line of the item; every transfer order counts, whatever its status (transfers have no void and no soft delete).
- **R2.** The date = date of `created_at` (UTC); the range filter uses it.
- **R3.** `quantity` = sum of the lines' `quantity` for the item (`4` + `1.5` → `5.50`); `unit_price`, `line_total`, `account_name`, `destination_label` are `None`; `status_name` = the current status's name; `order_number` = `transfer_number`.
- **R4.** [BUG-2555] A transfer whose status belongs to another workspace is left out (HR-16). *(Today: listed with that status name.)*

**Errors:** none. **Side effects:** none.

---

## `ItemOrdersService._sales_rows(db, *, workspace_id, item_id, from_date, to_date)`
**Shape:** list · **Persistence:** reads · **Visibility:** internal (used by: `get_orders_for_item`)

**Rules:**
- **R1.** One row per sales order of the workspace with at least one line whose `item_id` is the item (free-text lines without an item never match); any status counts (sales orders have no void or soft delete).
- **R2.** The date = the order's `order_date`, or the date of `created_at` when empty (the column is NOT NULL, so in practice `order_date`); the range filter uses it.
- **R3.** `quantity` = sum of `quantity_ordered` of the item's lines; internal total = sum of their `line_total`.
- **R4.** `unit_price` = `_weighted_unit_price(total, quantity)` (every sales line is priced: `unit_price` and `line_total` are NOT NULL, so the priced quantity is the whole quantity and BUG-2490 does not apply).
- **R5.** The row's `line_total` = the sum when greater than 0.
- **R5a.** [BUG-2491] A sales order whose item lines total 0.00 shows `line_total` `0.00` (and `unit_price` `0.00`); `line_total` is never `None` for a sales row. *(Today: a sum of 0 or less gives `None`.)*
- **R6.** `account_name`, `status_name` as for POs; `destination_label None`; `order_number` = `sales_order_number`. [BUG-2555] An order whose account or status belongs to another workspace is left out (HR-16). *(Today: their names are shown.)*

**Errors:** none. **Side effects:** none.

---

## `ItemOrdersService._work_rows(db, *, workspace_id, item_id, from_date, to_date)`
**Shape:** list · **Persistence:** reads · **Visibility:** internal (used by: `get_orders_for_item`)

**Rules:**
- **R1.** One row per work order of the workspace with at least one **non-deleted** line of the item; deleted lines (`is_deleted = True`) neither count toward `quantity` nor make the order appear.
- **R2.** [BUG-2552] Work orders with status `VOIDED` are left out; `DRAFT`, `IN_PROGRESS`, `COMPLETED` stay. *(Today: voided ones listed.)*
- **R3.** [BUG-2553] Soft-deleted work orders (`is_deleted = True`) are left out, whatever their lines' flag (HR-4). *(Today: listed.)*
- **R4.** The date = date of `created_at` (database clock, see FU-3); the range filter uses it. `quantity` = sum of the live lines' `quantity`; `unit_price`, `line_total`, `account_name`, `destination_label` are `None`; `order_number` = `work_order_number`.
- **R5.** [BUG-2550] `status_name` = the stored status text (`"DRAFT"`, `"IN_PROGRESS"`, `"COMPLETED"`). *(Today: any row raises `AttributeError: 'str' object has no attribute 'value'`, so the whole call fails.)*

**Errors:** today `AttributeError` for any row (BUG-2550). **Side effects:** none.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 35–37 | value is None / else | `_dec` R1, R2, R3 |
| 41 | inclusive range | `_in_date_range` R1 |
| 45–47 | quantity <= 0 / else | `_weighted_unit_price` R1, R2, R3 |
| 56–58 | falsy ids dropped; nothing left → `{}` | `_build_po_destination_labels` R1 |
| 66, 75, 84 | any storage / machine / project ids | R2, R3, R4, R5, R7 |
| 97–100 | already labelled → skip | R2–R4, R6 |
| 101–108 | storage / machine / project / other fallback | R6, R7 |
| 127–129 | item not found | `get_orders_for_item` R1, R2 |
| 133, 144, 154, 164 | type None or matches | R3 |
| 175–181 | sort (incl. `order_date or date.min`: never `None`, all four date expressions are non-null — unreachable fallback) | R6 |
| 182–184 | total, slice | R7, R8, R9 |
| 196–204 | workspace, item, not voided; date fallback | `_purchase_rows` R1, R2, R3, R10 |
| 205–206 | both dates given | R3; `get_orders_for_item` R4, R4a |
| 207–208 | exclude id not None | R4 |
| 227–228 | outer joins account / status | R9, R10 |
| 262–273 | quantity, unit price, `total > 0` | R5–R8 |
| 275–277 | label lookup / missing | R9 |
| 293–298 | transfer filters, both dates | `_transfer_rows` R1, R2 |
| 313 | status outer join | R3, R4 |
| 349–358 | sales filters, date fallback, both dates | `_sales_rows` R1, R2 |
| 375–376 | account / status outer joins | R6 |
| 391–401 | quantity, unit price, `total > 0` | R3, R4, R5 |
| 419–425 | work filters (line not deleted), both dates | `_work_rows` R1, R2, R3, R4 |
| 460 | `status is not None` → `.value` | R5 |
| 174–181 | Python `sort`, stable; no SQL `ORDER BY` | `get_orders_for_item` R13 |
| 262–273, 391–401 | priced quantity / zero total (intended, BUG-2490, BUG-2491) | `_purchase_rows` R7, R7a, R8a; `_sales_rows` R5a |

## Gap log
- G1 (`item_orders_service.cases.md` gap 1) — Fact — added `_purchase_rows` R12: the four helpers return a `list[ItemOrderRowResponse]`; the internal total shows only as the row's `line_total`.
- G2 (cases gap 2) — Fact — Facts "Date columns": all `created_at` columns are naive `timestamp without time zone`; `CAST(... AS DATE)` takes the stored day whatever the session time zone; POs, transfers and sales store UTC, work orders the database's session-local `now()`.
- G3 (cases gap 3) — Fact — added `get_orders_for_item` R13: the sort is a stable Python sort with no SQL `ORDER BY`; the BUG-2551 tie-break belongs in the Python key.
- G4 (cases gap 4) — Fact — Facts "Minimum rows": NOT NULL columns without default and foreign keys of the eight order tables and `statuses`; soft-delete columns.
