# Spec — `app/services/purchase_order_item_insights_service.py`

> **Status:** APPROVED (2026-11-10; no owner question; P1–P2 decided by Claude under the reviewer's delegation (2026-11-10); house-rule lines applied)
> **Source commit:** e48a092

> **Review round 2026-11-10 (low supervision).** No owner answer in this round. **Delegated:** P1 (another workspace's supplier and lines, HR-16) and P2 (server-local "today", BUG-1334 precedent) decided by Claude under the reviewer's delegation (2026-11-10); neither is the owner's own answer. Report semantics (which orders count, future-dated orders, drafts, zero prices) are described as they are today, with no bug: the two sibling reports (`item_orders_service`, `item_summary_service`) use the same "not voided, any stage" scope.
>
> **Base behaviour** cited, not restated: `BaseDAO.get_by_id_and_workspace` (`tests/unit/dao/base.spec.md`: raw lookup by id and workspace, `None` when absent); `PurchaseOrderManager.get_purchase_order` raises the 404 itself. This class is **not** a `BaseService` subclass and never commits or rolls back: it behaves as TC6 of `tests/unit/services/base_service.spec.md` (a read leaves pending changes pending, an exception reaches the caller unchanged).
>
> **Review round 2026-11-10 (2), gaps.** Case designer gaps 1–2 closed (see Gap log): `_HistoryLine` fields; void columns and the post-BUG-2542 clock patch point (delegation). No owner answer affects this spec. Status stays APPROVED.
>
> **Verified by running** (my own scripts `v1.py`, `v2.py`, `v3.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsup\poi\`, one outer transaction on `marker_test`, rolled back, private `COVERAGE_FILE`; nothing persisted): a PO of another workspace and an unknown id (404, detail as R1); a PO with no lines (`items=[]`); two lines of one item on the current PO (one row); an item with no history (all `None`); a voided history PO (left out); a voided current PO (still answered); a history PO of another workspace (left out); a future-dated PO with price `0.00` and no supplier (chosen as `last_ordered`, absent from every "lowest"); a PO with no `order_date` created 2020-01-01 23:00 (dated 2020-01-01); a negative price (never "lowest"); the 30 / 90 day windows; a patched `date.today()` (2031-01-01 → `days_90` `None`); **another workspace's supplier on a history PO** (its name came back in the history lines: P1); **a line with another workspace's `workspace_id` on one of our POs** (counted, became `all_time` at 0.50: P1); **an item of another workspace on the current PO** (got its own row, with its id: P1); **two suppliers tied on average and order count**: the pick followed the order the query returned the lines (Sup B when its line came first, Sup A otherwise; the query has no `ORDER BY`): HR-6 line. **Read, not run:** the endpoint `GET /purchase-orders/{po_id}/item-price-insights/` and the web app's caller (`frontend/src/features/purchaseOrders/purchaseOrdersApi.ts`). **Not run:** anything over HTTP.

## Review
> All decided; applied 2026-11-10.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | Price history shows another workspace's supplier name and counts lines that belong to another workspace; an item of another workspace on the PO gets its own row | bug — BUG-2540, BUG-2541 | delegation (HR-16) |
| P2 | "Last 30 / 90 days" is measured from the server's local date | bug — BUG-2542 | delegation (BUG-1334 precedent) |

Decided by house rules: a tie between two suppliers for "lowest average" is broken by the order the database happens to return rows (BUG-2543).

### House-rule violations — applied automatically

- **HR-6** `_pick_avg_supplier_lowest` R5 — two suppliers with the same average price and the same number of orders: the winner is whichever supplier's line the query returned first, and the query has no `ORDER BY` (verified: the pick flipped between "Sup A" and "Sup B" on the same data). Intended: ties broken by supplier name case-insensitive ascending, then `account_id` ascending.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2543 (new pattern `ranked-tie-follows-row-order`). Rules: `_pick_avg_supplier_lowest` R5.
- **HR-16** `_fetch_history_lines` R1a, R4a; `get_item_price_insights` R3a — see P1.
**Answer:** bug — per HR-16 (house rule)
**Resolution:** 🐞 BUG-2540, BUG-2541.

Checked and **not** a new line here: **HR-4** — purchase orders and their lines have no soft-delete column (a PO is cancelled by `voided`, which is excluded); a soft-deleted or inactive supplier is still named on its old orders and still competes for "lowest average": this is purchase history of orders that did happen, and the PO page shows the same supplier name, so it is report semantics, described as is (`_fetch_history_lines` R4). A soft-deleted catalog item on the current PO still gets a row (the PO line names it). **HR-5 / HR-7 / HR-8** — no paging, no search. **HR-9 / HR-10** — nothing is written. **HR-15** — nothing is rounded: prices are returned as stored (`Numeric(15,2)`); the weighted average is only compared, never returned. **HR-1 / HR-2 / HR-3** — no names written. **Falsy values** — `0` prices are excluded from "lowest" by an explicit `> 0` test (R1 of both pickers), not by truthiness; an empty `account_name` string is replaced only in an internal field that is never returned (`_pick_avg_supplier_lowest` R3 note).

**Permission checks:** none in the service; the endpoint lets any active member of the workspace read every supplier's prices (routed to `docs/future/permissions.md`).

### Delegated questions

### P1. Another workspace's supplier and lines reach the price history — 🐞 BUG-2540, BUG-2541
**Background:** Workspaces are separate (HR-16): a row linking to another workspace's row is invalid data. Such rows exist today because `PurchaseOrderManager` stores the supplier and line items as sent (BUG-1017, open).
**What happens today:** History lines are filtered on the purchase order's workspace only. The supplier (`accounts`) is joined by id alone, so a PO pointing at another workspace's supplier shows that supplier's id and name; a PO line whose own `workspace_id` is another workspace is counted; and an item of another workspace on the current PO gets its own result row (its id), with history searched for it.
**Example:** Workspace A's PO-7 was created through the API with workspace B's supplier "Rahman Steel" at 95.00. Opening PO-12 in workspace A, the "lowest price" box can read "Rahman Steel — 95.00 on PO-7": a name from workspace B.
**Rules affected:** `_fetch_history_lines` R1a, R4a; `get_item_price_insights` R3a
**Answer:** bug — HR-16: only lines whose own `workspace_id` is the caller's count; a supplier of another workspace is treated as no supplier (`account_id` and `account_name` empty, not in "lowest average"); a line of the current PO whose item is not in the caller's workspace gives no row
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10; HR-16, BUG-1571 precedent: an unscoped join on a read). Two bugs, pattern `missing-workspace-scope`: BUG-2540 (history lines and supplier), BUG-2541 (item rows). Creation of such rows is BUG-1017.

### P2. "Last 30 / 90 days" counts from the server's local date — 🐞 BUG-2542
**Background:** The windows compare each order's date with "today". "Today" is the date on the machine running the API (`date.today()`), while an order without an `order_date` is dated by its `created_at`, which is UTC. Number years were moved to UTC for the same reason (BUG-1334, BUG-1441, BUG-2440).
**What happens today:** On a server whose clock is not UTC, "today" can be a day off from the dates the app stores, so an order exactly 30 days old drops in or out of "last 30 days" depending on the server's time zone.
**Example:** Server in Asia/Dhaka (UTC+6) at 02:00 local on 2026-11-10 (20:00 UTC on 2026-11-09): "today" is 2026-11-10, so an order dated 2026-10-10 counts in "last 30 days"; on a UTC server at the same instant it does not.
**Rules affected:** `get_item_price_insights` R6
**Answer:** bug — "today" is the UTC date (`utcnow().date()`)
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10), per BUG-1334 precedent: 🐞 BUG-2542 (pattern `local-clock-instead-of-utc`).

## Follow-ups for other reviews
> Nothing below is a rule of this module and no bug is logged for it here.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Dead-code list** (reviewer, at the next dead-code pass) | Unreachable from the public method: the `if not po` 404 (the manager already raises the same 404); `by_item.setdefault` for an item not asked for; `_pick_last_ordered` R3 (every history line has a date, `created_at` is NOT NULL); the `ln.order_date or date.min` / `else 0` fallbacks; `_pick_avg_supplier_lowest` R7 (weights are never ≤ 0, so a supplier is always chosen); the unused `account_name` / `Account #<id>` bucket field. Specified below as helper-level rules so a removal is a visible change; not put on the removal checklist without the reviewer's `remove`. | Branch map |
| FU-2 | **Purchase order manager / schemas** (`app/managers/purchase_order_manager.py`) | Existing BUG-1017 is what lets a PO hold another workspace's supplier and items; once it is fixed, BUG-2540 / BUG-2541 only matter for rows already stored. | P1 |

## Overview
`PurchaseOrderItemInsightsService` builds the "price history" panel of a purchase order: for every catalog item on the PO it returns the last time the item was ordered and four "lowest price" references (cheapest supplier on average, cheapest line ever, cheapest in the last 30 days, cheapest in the last 90 days), each pointing at one earlier purchase order line. History is every other non-voided purchase order of the workspace, in any stage (Draft included). Its only caller is `GET /purchase-orders/{po_id}/item-price-insights/` (`app/api/v1/endpoints/purchase_orders.py`, any active member via `get_current_workspace`), used by the web app's purchase order page. It reads only; nothing is written, flushed, committed or rolled back.

**Callables:** 7 specified · 1 not specified
**Externals to mock:** none. "Today" is `date.today()` read through the module's `date` name (`patch.object(module, "date", <date subclass with a fixed today()>)`); after BUG-2542 the module imports `utcnow` by name (`from app.utils.time import utcnow`) and "today" is `utcnow().date()`; tests patch `app.services.purchase_order_item_insights_service.utcnow` (with `create=True` until the fix lands), as the verified DAO specs patch `app.dao.<module>.utcnow` (decided by Claude under the reviewer's delegation (2026-11-10), gap 2). **Voided PO** (real columns on `purchase_orders`): `voided` Boolean NOT NULL default `False`; with it a real void writes `void_note` (Text, nullable), `voided_at` (DateTime, nullable) and `voided_by` (FK `profiles.id` ON DELETE SET NULL, nullable). Only `voided` is read by this module; the other three have no effect here.
**Integration-only behavior:** none (the date fallback `COALESCE(order_date, CAST(created_at AS DATE))` is plain SQL and runs on the test database).

**Response shape** (`app/schemas/purchase_order_item_insights.py`): `PoItemPriceInsightsResponse{items: [ItemPriceInsightRow]}`; `ItemPriceInsightRow{item_id, last_ordered: Ref|None, lowest: {avg_supplier, all_time, days_30, days_90: Ref|None}}`; `Ref{purchase_order_id, po_number, account_id|None, account_name|None, unit_price: Decimal|None, order_date: date|None}`.

**Model facts used** (cited; full tables in the PO manager specs): `purchase_orders`: `workspace_id` NOT NULL, `po_number` NOT NULL, `account_id` nullable FK `accounts.id`, `order_date` Date nullable, `created_at` DateTime NOT NULL (Python `utcnow`), `voided` Boolean NOT NULL default False; no soft delete. `purchase_order_items`: own `workspace_id` NOT NULL, `item_id` NOT NULL, `quantity_ordered` Numeric(15,2) NOT NULL, `unit_price` Numeric(15,2) nullable, `line_number` NOT NULL. `accounts`: `workspace_id`, `name` NOT NULL, `is_deleted`, `is_active`.

**Notes for the test designer**
- Rows: a PO needs a `Status` of its workspace (`current_status_id`), `created_by` (a profile), `destination_type`/`destination_id` (any, e.g. `"storage"`, `1`); a line needs `line_number`, `quantity_ordered`. See `make_po` / `make_line` in `tests/unit/managers/test_po_receive_inventory.py`.
- The helpers are plain methods on the singleton `purchase_order_item_insights_service`; they can be called directly with hand-made `_HistoryLine` objects (a frozen dataclass in the module) to reach helper-only rules.
- To show BUG-2543 deterministically, call `_pick_avg_supplier_lowest` with the same two tied lines in both orders and expect the same winner.

## Not specified
- `_HistoryLine` — frozen dataclass (`@dataclass(frozen=True)`), fields only. Exactly nine fields, in this order, none with a default: `item_id: int`, `line_id: int`, `purchase_order_id: int`, `po_number: str`, `account_id: int | None`, `account_name: str | None`, `unit_price: Decimal | None`, `quantity_ordered: Decimal`, `order_date: date | None`. Accepts keywords or positional arguments (generated `__init__`); setting an attribute afterwards raises `dataclasses.FrozenInstanceError`. Annotations are not enforced at run time (gap 1).
- Module singleton `purchase_order_item_insights_service` — instance, no logic.

---

## `_dec(value)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: `_fetch_history_lines`)

**Purpose:** Turn a database number into a `Decimal`.

**Rules:**
- **R1.** `None` gives `Decimal(0)`.
- **R2.** Any other value gives `Decimal(str(value))`: `Decimal("10.00")` stays `Decimal("10.00")`, a float `1.1` gives `Decimal("1.1")` (not the binary expansion), an int `3` gives `Decimal("3")`.

**Errors:** a value whose `str()` is not a number raises `decimal.InvalidOperation` (not reachable: the columns are numeric).
**Side effects:** none.

---

## `_to_ref(line)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** internal (used by all three pickers)

**Rules:**
- **R1.** Returns an `ItemPriceInsightRef` with `purchase_order_id`, `po_number`, `account_id`, `account_name`, `unit_price`, `order_date` copied from the line, unchanged (`None` stays `None`). `item_id`, `line_id` and `quantity_ordered` are not in the result.

**Side effects:** none.

---

## `PurchaseOrderItemInsightsService.get_item_price_insights(db, *, po_id, workspace_id)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (`GET /purchase-orders/{po_id}/item-price-insights/`)

**Purpose:** Price history references for every catalog item on one purchase order.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `po_id` | int | the PO being viewed; must be in `workspace_id` |
| `workspace_id` | int | caller's workspace (endpoint: current workspace) |

**Returns:** `PoItemPriceInsightsResponse`.

**Rules:**
- **R1.** A PO id that does not exist, or belongs to another workspace, is refused with 404 (raised by `PurchaseOrderManager.get_purchase_order`). A voided PO is answered normally.
- **R2.** A PO with no lines (in the workspace) returns `items=[]`.
- **R3.** One row per distinct `item_id` among the PO's lines whose own `workspace_id` is `workspace_id` (lines with another `workspace_id` are not seen); an item on several lines appears once. Rows are in `item_id` ascending order.
- **R3a.** [BUG-2541] A line whose catalog item belongs to another workspace gives no row (its id is not shown); if no line is left, `items=[]`. *(Today: the item gets a row with its id and its history, verified.)*
- **R4.** Each row: `item_id`; `last_ordered` per `_pick_last_ordered`; `lowest.avg_supplier` per `_pick_avg_supplier_lowest`; `lowest.all_time` per `_pick_min_price_ref` with no window; `lowest.days_30` and `lowest.days_90` per `_pick_min_price_ref` with the windows of R6. All are picked from the item's history lines (`_fetch_history_lines`). An item with no history has all five `None`.
- **R5.** The history never includes any line of the PO being viewed (`exclude_po_id = po_id`), nor of voided POs (`_fetch_history_lines` R1).
- **R6.** `days_30` covers order dates from today − 30 days to today, both ends included; `days_90` from today − 90 to today, both included. [BUG-2542] "Today" is the current UTC date. *(Today: the server's local date, `date.today()`.)*
- **R7.** Read only: nothing is written, flushed, committed or rolled back; changes pending in the session stay pending; any exception reaches the caller unchanged (as TC6).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| PO not found in the workspace | `HTTPException` 404 | `Purchase order with ID {po_id} not found` |

**Side effects:** none.

---

## `PurchaseOrderItemInsightsService._fetch_history_lines(db, *, workspace_id, item_ids, exclude_po_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** internal (used by: `get_item_price_insights`)

**Purpose:** Every earlier purchase order line for the given items.

**Rules:**
- **R1.** Returns one `_HistoryLine` per purchase order line where: the line's PO is in `workspace_id`; the line's `item_id` is in `item_ids`; the PO is not voided; the PO is not `exclude_po_id`. Lines of POs of other workspaces are never returned. Unknown item ids simply match nothing (`[]`).
- **R1a.** [BUG-2540] Only lines whose own `workspace_id` is `workspace_id` are returned. *(Today: a line with another workspace's `workspace_id` on one of this workspace's POs is returned and counted, verified.)*
- **R2.** No stage or status filter: Draft, Planning, Receiving and Complete POs all count; quantities received, returned or refunded play no part. A line with no price is returned (`unit_price` `None`).
- **R3.** `order_date` is the PO's `order_date`; when it is empty, the date part of the PO's `created_at` (UTC). Since `created_at` is NOT NULL, every line has a date. A future `order_date` is kept as is.
- **R4.** `account_id` is the PO's `account_id`; `account_name` is that account's name. A PO with no supplier gives both `None`. A soft-deleted or inactive supplier is still named.
- **R4a.** [BUG-2540] A supplier of another workspace is treated as no supplier: `account_id` and `account_name` are `None`. *(Today: its id and name are returned, verified.)*
- **R5.** `unit_price` is a `Decimal` or `None`; `quantity_ordered` a `Decimal`; `line_id` the line's id; `purchase_order_id`, `po_number` the PO's.
- **R6.** Lines come back in no defined order (no `ORDER BY`). Every picker below breaks its ties itself, except the supplier tie of `_pick_avg_supplier_lowest` R5 (BUG-2543).
- **R7.** An empty `item_ids` returns `[]` (helper-only: the public method returns earlier).

**Side effects:** none.

---

## `PurchaseOrderItemInsightsService._pick_last_ordered(lines)`
**Shape:** compute · **Persistence:** pure · **Visibility:** internal

**Rules:**
- **R1.** No lines → `None`.
- **R2.** The line with the latest `order_date`; on a date tie the highest `line_id`. Any line counts, priced or not, with any supplier or none, including a price of 0 or below and a future date (verified: a PO dated 5 days ahead with price `0.00` and no supplier was "last ordered").
- **R3.** (Helper-only, unreachable from R1 of `get_item_price_insights`.) When no line has a date, the line with the highest `line_id`; lines without a date are otherwise ignored when at least one has a date.

**Side effects:** none.

---

## `PurchaseOrderItemInsightsService._pick_min_price_ref(lines, *, from_date=None, to_date=None)`
**Shape:** compute · **Persistence:** pure · **Visibility:** internal

**Rules:**
- **R1.** Only lines with a price greater than 0 are candidates: `None`, `0` and negative prices never count.
- **R2.** When both `from_date` and `to_date` are given, only candidates with `from_date <= order_date <= to_date` remain (a line with no date is dropped). When either bound is missing, no window is applied (helper-only for a single bound; the public method passes both or neither).
- **R3.** No candidate left → `None`.
- **R4.** The cheapest candidate; ties: earliest `order_date` (a missing date counts as earliest, helper-only), then lowest `purchase_order_id`, then lowest `line_id`.
- **R5.** So a future-dated line can be `all_time` but never `days_30` / `days_90`.

**Side effects:** none.

---

## `PurchaseOrderItemInsightsService._pick_avg_supplier_lowest(lines)`
**Shape:** compute · **Persistence:** pure · **Visibility:** internal

**Purpose:** The supplier with the lowest quantity-weighted average price, shown by one of its lines.

**Rules:**
- **R1.** Candidates: lines with a supplier (`account_id` not `None`) and a price greater than 0.
- **R2.** No candidate → `None`.
- **R3.** Per supplier, average = Σ(weight × price) / Σ weight over its candidate lines, where weight is `quantity_ordered`, or 1 when `quantity_ordered` is 0 or less. Exact `Decimal` arithmetic, no rounding; the average itself is not returned. *(Internally a display name, falling back to `Account #<id>`, is kept per supplier but never returned.)*
- **R4.** The supplier with the lowest average wins; on an equal average, the one with more distinct purchase orders among its candidate lines.
- **R5.** [BUG-2543] On an equal average and an equal order count, the supplier whose name is first case-insensitively wins, then the lower `account_id`. *(Today: whichever supplier's line came first in the list, i.e. database order; verified flipping.)*
- **R6.** The returned reference is one of the winner's candidate lines: the cheapest; ties: the latest `order_date` (a missing date counts as oldest, helper-only), then the lowest `purchase_order_id`, then the lowest `line_id`. It is the same line set as R1, so a winning supplier's zero-price line is never shown.
- **R7.** (Unreachable: weights are always > 0.) A supplier whose total weight is ≤ 0 is skipped; if none is left, `None`.

**Side effects:** none.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 26–28 | `value is None` | `_dec` R1, R2 |
| 63 (manager 925–927) | PO missing / other workspace → 404 | `get_item_price_insights` R1 |
| 64–68 | `if not po` (unreachable) | R1; FU-1 |
| 70–73 | lines filtered by workspace; distinct sorted ids | R3, R3a |
| 74–75 | no item ids → `[]` | R2 |
| 85–86 | `setdefault` for unexpected item (unreachable) | R4; FU-1 |
| 88, 99–108 | today and windows | R6 |
| 90–91 | item with no lines | R4 |
| 140–147 | join / outer join / filters | `_fetch_history_lines` R1, R1a, R2, R4, R4a |
| 123–126 | `COALESCE(order_date, created_at::date)` | R3 |
| 148 | no `ORDER BY` | R6; `_pick_avg_supplier_lowest` R5 |
| 155 | `unit_price` None kept | R5 |
| 167–172 | no dated lines / no lines | `_pick_last_ordered` R1, R3 |
| 174–177 | max by (date, line id) | R2 |
| 187–191 | price not None and > 0 | `_pick_min_price_ref` R1 |
| 192–197 | both bounds given; date None dropped | R2 |
| 198–199 | no candidates | R3 |
| 201–209 | tie keys, `date.min` | R4, R5 |
| 213–219 | supplier and price > 0; none | `_pick_avg_supplier_lowest` R1, R2 |
| 226, 233–234 | display name fallback / overwrite (unused) | R3 note; FU-1 |
| 236 | qty > 0 else 1 | R3 |
| 246–247 | total weight ≤ 0 (unreachable) | R7 |
| 250–254 | lower avg / equal avg more orders / first seen | R4, R5 |
| 259–260 | no best (unreachable) | R7 |
| 263–271 | reference line tie keys, `else 0` | R6 |

## Gap log
- G1 (`purchase_order_item_insights_service.cases.md` gap 1) — fact — Not specified `_HistoryLine`: frozen dataclass, nine fields in order with types, keyword or positional, no defaults, frozen.
- G2 (`purchase_order_item_insights_service.cases.md` gap 2) — fact + delegation (2026-11-10) — Overview Externals: real void columns `voided`, `void_note`, `voided_at`, `voided_by` (only `voided` matters); after BUG-2542 the clock is `utcnow` imported by name into the module, patched as `app.services.purchase_order_item_insights_service.utcnow` (`create=True` until fixed).
