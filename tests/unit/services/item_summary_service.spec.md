# Spec — `app/services/item_summary_service.py`

> **Status:** APPROVED (2026-11-10; owner answered OQ-31 and OQ-32 the same day — applied, BUG-2485, BUG-2486; case-designer gaps G1–G9 closed, see Gap log)
> **Source commit:** e48a092

> **Review round 2026-11-10 (low supervision).** No owner answer in this round. **Delegated:** every new question below (Q1–Q6) is decided by Claude under the reviewer's delegation (2026-11-10); none is the owner's own answer. House-rule lines stand. **Owner:** Q7 (OQ-31, what "total spend" adds up) and Q8 (OQ-32, which purchase lines count as open) are money / stock-counting questions, parked in `docs/testing/owner-questions.md`, not blocking: the rules described today and carried *pending owner* — both answered in round 2 below.
>
> **Review round 3 — 2026-11-10, verifier gap.** `_supplier_rows_from_po_lines` R5b added from the code: an account whose lines all have no date → no last date and no last price. Unreachable from the real caller (`created_at` NOT NULL), so no bug is logged (decided by Claude under the reviewer's delegation (2026-11-10)). Status stays APPROVED.
>
> **Review round 2 — 2026-11-10 (owner answers + fill-gaps).** **Owner:** OQ-31 (Q7) answered "split": `total_spend` counts purchases only, sales revenue is its own figure, transfers stay out of money totals (the same answer as OQ-30 for the orders overview) → BUG-2485. OQ-32 (Q8) answered: open purchase lines leave out orders in their workflow's last status as well as voided ones → BUG-2486. "Pending owner" is gone from every rule. **Delegated (Claude, 2026-11-10):** gap G3 — `_resolve_order_link` / `_resolve_order_number` take the workspace (part of BUG-2520's fix); gap G5 — ledger times are normalised to naive UTC before the merge (BUG-2487); gap G7 — BUG-2523 is fixed in both places: the supplier query gets an `ORDER BY` and the pure helpers apply the id tie keys. Facts for G1, G2, G4, G6, G8, G9 read from the code and models (my scripts `models.py`, `v2.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsup\is\`, no database write).
>
> **Base behaviour is not restated.** The DAO reads are specified and approved in `tests/unit/dao/inventory.spec.md` (`get_by_item`), `tests/unit/dao/product.spec.md` (`get_by_item`), `tests/unit/dao/machine_item.spec.md` (`get_by_item`), `tests/unit/dao/inventory_ledger.spec.md` (`get_by_workspace`), `tests/unit/dao/product_ledger.spec.md` (`get_by_workspace`), `tests/unit/dao/machine_item_ledger.spec.md` (`get_by_item`); the item lookups in `tests/unit/managers/item_manager.spec.md` (`get_item`, `get_tags_for_item`). This spec states only what the service does with their results; each rule names the DAO rule it relies on. `orders_overview_service._po_report_date` / `_in_date_range` are inlined here as outcomes (that service has its own spec).
>
> **Standing decisions applied here (not asked again):** HR-4 (soft-deleted related rows neither count nor show; ledgers are history and keep a deleted factory's / machine's entries, inventory ledger DAO Q3). HR-6 (names case-insensitive, then `id`; no recipe counts as deterministic unless it ends in an id). HR-16 (a link to another workspace's row is invalid data: nothing of that workspace is shown). For items "deleted" is `is_active = False` (item manager standing decision 1). An item's summary stays reachable after the item is removed — the owner's BUG-1339 (2026-11-03) rules what that summary shows, so it presumes the page opens. Voided purchase orders are left out of reports (BUG-717, and the sibling item reports `item_orders_service`, `purchase_order_item_insights_service`, the calendar). Inactive production formulas are a normal visible state (production formula DAO Q1). "Today" is the server's `date.today()`, as everywhere else (machine manager FU-9, product-wide; no bug here).
>
> **Verified by running** (my own script `v1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsup\is\`, one transaction on `marker_test`, rolled back, private `COVERAGE_FILE`): one item with four POs today — PO-1 (Acme, 10 @ 5.00), PO-2 (Acme, 10 unpriced), PO-3 (Beta, **voided**, 100 @ 1.00), PO-4 (an account of **another workspace**, 1 @ 2.00) — one sales line 3 @ 100.00 (line total 300.00), one work order with **two** lines of the item and one **deleted** work order with a **deleted** line, two inventory-ledger entries (`po_receive_event_item` and legacy `purchase_order` sources). Results: `order_stats.all_time` purchase_qty 121.00, sales_qty 3.00, total_quantity 124.00, **total_spend 452.00** (= 50 + 0 + 100 + 2 + **300 sales**), line_count 5; `pricing.last_unit_price` 2.00, open lines **4** / 121.00 (voided included); all-time weighted average `1.369369369369369369369369369` (unrounded), min 1.00, max 5.00; suppliers Beta (voided PO) 100 / 100.00 / 1.00, **Acme avg 2.50** (= (50 + 0) / 20: the unpriced 10 counted at 0), **"OtherWS Supplier"** listed; cheapest **Beta** (voided); usage `work_order_line_count` 3, preview `['WO-DEL', 'WO-1', 'WO-1']`; activity: the `po_receive_event_item` entry has **no order link**, the legacy one links `PO-1`; **36 statements** for the call; a removed item (`is_active = False`) still answers 200; another workspace → `NotFoundError` 404 `Item with ID <id> not found`. **Read, not run:** the web dialog (`ItemDetailsDialog`, `OverviewKpiStrip` "Total spend" = `order_stats.all_time.total_spend`; `OverviewSection` lists preview names), every ledger writer's `source_type` / `source_id`. **Not run:** HTTP; ties; another workspace's factory / section / formula / work order rows (read from the joins).

## Review
> All decided or parked; 2026-11-10.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| HR-16 | Names and ids of another workspace's account, factory, section, formula, batch, project, work order or order are shown when a row of this workspace links to them | bug — BUG-2520 | house rule |
| HR-6 | Name-sorted lists are case-sensitive and have no id tie-break | bug — BUG-2522 | house rule |
| HR-6 | Supplier top 10, "cheapest", "most used" and a supplier's last price pick at random on ties | bug — BUG-2523 | house rule |
| HR-4 | Usage counts and previews include deleted work-order lines, lines of deleted work orders and components of deleted projects; a deleted section is still named | bug — BUG-2525 | house rule |
| Q1 | Voided purchase orders count in quantities, spend, prices, open lines and supplier stats | bug — BUG-2521 | delegation (precedent BUG-717) |
| Q2 | Supplier figures treat an unpriced line as price 0.00; the item's last price is empty when the newest line is unpriced | bug — BUG-2524 | delegation |
| Q3 | The usage previews repeat a work order (or component, formula, batch) once per line | bug — BUG-2526 | delegation |
| Q4 | Recent activity gives no order link for today's purchase receipts, receipt corrections, purchase returns and work orders | bug — BUG-2527 | delegation |
| Q5 | Recent activity reads two rows per ledger entry, for 30 entries of which 10 are shown | bug — BUG-2528 | delegation (precedent BUG-1141) |
| Q6 | Inventory ledger entries are timed by the database clock, machine entries by UTC, and recent activity sorts them together | bug — BUG-2529 | delegation (precedent BUG-1337) |
| Q7 | **OWNER** — "Total spend" adds sales revenue to purchase spend | bug — BUG-2485 (OQ-31: purchases only; sales revenue its own figure) | owner, 2026-11-10 |
| Q8 | **OWNER** — open purchase lines include orders already closed in their workflow's last status | bug — BUG-2486 (OQ-32: leave out terminal-status and voided orders) | owner, 2026-11-10 |
| G5 | Recent activity cannot merge a naive and a zone-aware ledger time (`TypeError`) | bug — BUG-2487 | delegation (gap G5) |

Existing bugs written as rules here, no new ID: **BUG-1339** (removed item hides factory and machine stock; the check is in this service), **BUG-937** (the item lookup; see `get_summary` R2). Reached through the DAOs and cited, one pass-through case each: BUG-884, BUG-1328, BUG-1338, BUG-981, BUG-982, BUG-977, BUG-1326, BUG-932, BUG-640, BUG-1337.

### House-rule violations — applied automatically

- **HR-16** `_machine_location_map` R3, `_inventory_rows` R6, `_product_rows` R4, `_supplier_stats` R3, `_usage` R6, `_resolve_order_link` R5, `_resolve_order_number` R3, `_recent_activity` R6 — every join or lookup behind a link matches the linked row **by id only**: a machine's factory and section, a purchase order's supplier account, a usage line's formula / batch / component / project / work order, a ledger entry's order. A row of this workspace that links to another workspace's row (invalid data; such rows exist through BUG-1010 … BUG-1018) shows that workspace's names and ids (verified for the supplier: "OtherWS Supplier" listed with its spend). Intended: only rows of the caller's workspace are joined or looked up; a link to another workspace's row is treated as not found, and nothing of that workspace — name or id — is shown (per BUG-1086 / BUG-1571 / BUG-1801).
**Answer:** bug — per HR-16 (house rule)
**Resolution:** 🐞 BUG-2520 (pattern `cross-workspace-row-exposed`; one bug for the whole summary). What "not found" means per section is in each rule.
- **HR-6** `_inventory_rows` R7, `_product_rows` R5, `_machine_placements` R5, `_usage` R4 (formula and project previews) — the lists sort by names compared case-sensitively (`"apex"` after `"Zeta"`) and end without an id, so equal names come back in the order the database produced (the DAO reads have no `ORDER BY`: inventory DAO `get_by_item` R5, BUG-1326, BUG-977; the formula and project previews are `LIMIT 5` on `ORDER BY name` only). Intended: names case-insensitive, then the row's id ascending as last key (details in each rule).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2522 (pattern `hr-6-non-default-list-order`, BUG-930 precedent).
- **HR-6** `_supplier_period_snapshot` R3, `_pick_cheapest_supplier` R2, `_pick_most_frequent_supplier` R2, `_supplier_rows_from_po_lines` R6 — the supplier query has no `ORDER BY`; the top-10 cut, both highlights and a supplier's "last price" on one date fall back to that order. Intended: suppliers by spend high to low, then `account_id` ascending; highlights and last price as in the rules, each ending in an id.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2523 (pattern `unordered-pagination`).
- **HR-4** `_usage` R2, R5; `_machine_location_map` R4 — usage counts and previews read the line tables only: a work-order line with `is_deleted = True`, any line of a work order with `is_deleted = True`, and a component of a project with `is_deleted = True` are counted and listed (verified: `WO-DEL` first in the preview). The section shown next to a machine is joined without its `is_deleted` (factory section DAO FU-4 routed it here). Intended: soft-deleted related rows neither count nor show; the rows themselves are untouched and show again when restored.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-2525 (pattern `join-ignores-soft-deleted`; BUG-2332 precedent for the section). `item_orders_service` already drops deleted work-order lines.

Checked and **not** a new line here: **HR-1/2/3** — nothing is written or named by the user here. **HR-5/7/8** — no paging, no search. **HR-9/10** — nothing is written. **HR-11 … HR-14** — no external system, no batch. **HR-15** — nothing is rounded: money figures are sums or products of 2-decimal columns, and the weighted averages are returned at full `Decimal` precision (verified `1.369369369369369369369369369`); no half-even `quantize` exists in the file. **HR-4 (own item)** — the summary of a removed item answers 200: intended (see standing decisions; BUG-1339 rules its content). **Ledgers** keep a deleted factory's or machine's entries and a removed item's entries (inventory ledger DAO Q3, BUG-1339 "Movement history (ledgers) is not hidden"). **Batches** have no soft delete; cancelled batches are listed with their status (report semantics, today). **Machine placements with `qty = 0`** stay listed and counted (machine item DAO FU-2 (b)): decided intended under the reviewer's delegation (2026-11-10) — a machine that should hold the item and holds none is the most useful "low stock" line.

### New questions

### Q1. Voided purchase orders count everywhere on the summary — 🐞 BUG-2521
**Background:** A purchase order can be voided (`voided = True`; the order stays). The item's order list on the same dialog (`GET /items/{id}/orders/`), the purchase line price insights, the calendar and the stock page's incoming summary (BUG-717) all leave voided orders out.
**What happens today:** Every purchase figure of the summary reads purchase lines with no `voided` filter: quantities and spend in the 30-day / 90-day / all-time stats, the last unit price, the weighted / min / max prices, the open-line count and outstanding quantity, and the supplier table with its "cheapest" and "most used" highlights.
**Example:** PO-3 for 100 bolts @ 1.00 from Beta was voided. The dialog shows "Purchased 121", "open lines 4, 121 outstanding", and Beta as the cheapest supplier — all from the voided order (verified).
**Rules affected:** `_order_stats_for_item` R2a, `_pricing` R1a, R4a, `_supplier_stats` R2a
**Suggested answer:** bug — a voided purchase order is left out of every figure, as the order list beside it.
**Answer:** bug — voided purchase orders are left out of every purchase figure of the summary
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10; precedent BUG-717, same root cause): 🐞 BUG-2521 (pattern `voided-record-not-excluded`).

### Q2. Supplier figures treat an unpriced line as free — 🐞 BUG-2524
**Background:** A purchase line's `unit_price` and `line_subtotal` may be empty (an order sent before the price is agreed). The "Pricing" figures of the same response skip unpriced lines.
**What happens today:** In the supplier table an unpriced line counts its quantity at price 0.00: it lowers the supplier's weighted average, can make it "cheapest", and when it is the supplier's newest line its "last price" shows 0.00. Separately, the item's own "last unit price" is the price of the newest line, so when that line is unpriced it shows nothing although older lines have prices.
**Example:** Acme sold 10 bolts @ 5.00 and 10 unpriced. The supplier table shows Acme's average as 2.50 (verified), while the pricing card above says the weighted average of priced lines; if the unpriced order is the newest, "last price" for Acme reads 0.00 and the item's last price is empty.
**Rules affected:** `_supplier_rows_from_po_lines` R4a, R5a; `_pricing` R2a
**Suggested answer:** bug — unpriced lines enter no price figure: a supplier's average is over priced lines only, its last price is that of its newest priced line, and the item's last price is that of the newest priced line. Quantities, spend and order counts keep counting every line.
**Answer:** bug — as suggested
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10): the response already ruled the rule for its own pricing card (`_pricing_snapshot_from_po_lines` R1), so this aligns the supplier table with it; no amount is changed or stored. 🐞 BUG-2524 (pattern `unpriced-line-counted-as-zero`, new).

### Q3. Usage previews repeat a parent once per line — 🐞 BUG-2526
**Background:** The usage section lists up to five formulas, batches, project components and work orders that use the item. A work order may have several lines of the same item (different source locations); there is no unique constraint on any of the four line tables.
**What happens today:** Each preview is one row per **line**, so a work order with two lines of the item appears twice and takes two of the five places (verified `['WO-DEL', 'WO-1', 'WO-1']`); the same holds for a component with the item twice, and for a formula or batch with the item twice in the same role.
**Example:** The dialog's overview reads "Work orders: WO-1, WO-1".
**Rules affected:** `_usage` R4a
**Suggested answer:** bug — each work order once (placed by its newest line), each project component once, each formula and each batch once per role; the five places count distinct entries. The counts stay line counts.
**Answer:** bug — as suggested
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10, display): 🐞 BUG-2526 (pattern `display-list-not-deduplicated`).

### Q4. Recent activity links no order for today's purchase receipts — 🐞 BUG-2527
**Background:** Each ledger entry records what caused it as `source_type` / `source_id`. The summary turns `purchase_order` (a purchase line id) and `transfer_order` (a transfer line id) into an order link. Purchase receiving was rebuilt: receipts now write `po_receive_event_item` (an event item id), corrections `po_receive_event_item_reversal`, legacy reversals `purchase_order_reversal` (a purchase line id), returns `purchase_return_item` (a return item id), work orders `work_order` (the work order id).
**What happens today:** Only old receipts (`purchase_order`) and transfers get a link; every receipt booked since the rebuild, every correction, return and work-order consumption shows no order (verified for `po_receive_event_item`). The machine ledger DAO spec assumed the link "already works".
**Example:** Recent activity shows "+5 bolts, purchase_order" with no PO number, though it came from PO-0042.
**Rules affected:** `_resolve_order_link` R4a
**Suggested answer:** bug — `po_receive_event_item` and `po_receive_event_item_reversal` link to the purchase order of that event item's receive event; `purchase_order_reversal` to the purchase line's order; `purchase_return_item` to the return's purchase order; `work_order` to that work order. Other sources (manual, adjustment, reconciliation, production batch) stay unlinked.
**Answer:** bug — as suggested
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10, display link): 🐞 BUG-2527 (pattern `unmapped-source-type`, new).

### Q5. Recent activity makes two extra reads per entry — 🐞 BUG-2528
**Background:** Up to 10 entries per ledger (30 in all) are read; only the newest 10 are returned.
**What happens today:** Each of the 30 entries resolves its order link and number with up to two single-row reads, before the list is cut to 10. The whole call took 36 statements with two linked entries (verified).
**Example:** An item with busy ledgers costs about 60 extra round trips per dialog open, 40 of them for entries thrown away.
**Rules affected:** `_recent_activity` R7
**Suggested answer:** bug — links and numbers are read together, only for the entries returned; the number of statements does not grow with the entries; result unchanged.
**Answer:** bug — as suggested
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10; precedent BUG-1141): 🐞 BUG-2528 (pattern `n-plus-one-read`).

### Q6. Recent activity sorts two clocks together — 🐞 BUG-2529
**Background:** `inventory_ledger.performed_at` defaults to the database's `now()` on a `timestamp without time zone`, i.e. the session time zone's local time (the test database runs `America/New_York`); no writer passes a time. `machine_item_ledger.performed_at` is Python `utcnow()`. The product ledger had the same default and was ruled a bug (BUG-1337).
**What happens today:** The summary merges the three ledgers by `performed_at`. A storage entry booked at 14:00 UTC is stored as 09:00 (New York) and sorts below a machine entry booked at 10:00 UTC.
**Example:** "Received 5 into storage" (later) appears below "Installed 1 on Press 4" (earlier).
**Rules affected:** `_recent_activity` R3 (no rule changes; the fix is in the model)
**Suggested answer:** bug — `inventory_ledger.performed_at` defaults to `utcnow()` in Python, as the machine ledger (BUG-1337 precedent).
**Answer:** bug — as suggested
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10): 🐞 BUG-2529 (pattern `database-clock-timestamp`). Fix in `app/models/inventory_ledger.py`. Tests here set `performed_at` explicitly.

### Q7. **OWNER** — "Total spend" adds sales revenue to purchase spend — 🐞 BUG-2485 (OQ-31)
**Background:** `order_stats` (per 30 days, 90 days, all time) sums, for the item: purchase lines (quantity, line subtotal), transfer lines (quantity only) and sales lines (quantity, line total). The dialog's KPI strip shows `order_stats.all_time.total_spend` as **"Total spend"**.
**What happens today:** `total_spend` = purchase subtotals **+ sales line totals**; `total_quantity` = purchased + transferred + sold.
**Example:** 20 bolts bought for 50.00 and 3 sold for 300.00 → "Total spend $350.00" (verified 452.00 with the voided and foreign lines).
**Rules affected:** `_order_stats_for_item` R5, R5a
**Suggested answer:** bug — `total_spend` is purchase spend only; sales value is a separate figure (new `sales_total`); `total_quantity` stays the volume of all lines.
**Alternatives:** (a) intended — "order value" across types (then the KPI label is wrong). (b) drop `total_spend` and show purchase and sales value side by side.
**Answer:** owner, 2026-11-10 (OQ-31, same as OQ-30): split — spend counts purchases only, sales revenue is its own figure, transfers stay out of money totals.
**Resolution:** 🐞 BUG-2485 (pattern `report-total-mixes-money-in-and-out`). `total_spend` = purchase line subtotals only; new field `sales_revenue` = sales line totals; `total_quantity` keeps the volume of all three kinds (the owner's answer is about money; "rank by purchased quantity" is about the orders overview's item leaderboard, not this card). Rules: `_order_stats_for_item` R5, R5a.

### Q8. **OWNER** — Open purchase lines include closed orders — 🐞 BUG-2486 (OQ-32)
**Background:** The pricing card's "open lines" and "outstanding quantity" count every purchase line with `quantity_ordered > quantity_received + quantity_refunded`, whatever the order's status. The stock page's incoming summary leaves out orders in their workflow's last (terminal) status.
**What happens today:** A purchase order closed short (completed with 70 of 100 received) shows 30 outstanding on the item summary forever, while the stock page shows nothing incoming from it.
**Example:** "Open PO lines 1 · 30 outstanding" for an order everyone considers finished.
**Rules affected:** `_pricing` R4, R4b
**Suggested answer:** bug — a line counts as open only when its order is neither voided (BUG-2521) nor in its workflow's terminal status, the same rule as the incoming summary.
**Alternatives:** (a) intended — the summary shows what was never delivered, closed or not.
**Answer:** owner, 2026-11-10 (OQ-32): open PO lines leave out orders in the last workflow status as well as voided ones.
**Resolution:** 🐞 BUG-2486 (pattern `terminal-status-not-excluded`). "Last workflow status" is decided exactly as the stock page's incoming summary does (`app/utils/order_workflow_terminal.py`, approved spec `tests/unit/utils/order_workflow_terminal.spec.md`): the terminal status of an order's workflow (`order_workflow_id`, workflow of the same workspace) is the last id of its `status_sequence`; an order with no workflow, no current status or an empty sequence is not terminal. Rules: `_pricing` R4, R4b.

## Follow-ups for other reviews
> Nothing below is a rule of this service and no new bug is logged for it here.

| # | Where | What | Came from |
|---|---|---|---|
| FU-1 | **BUG-937 fix** (`app/managers/item_manager.py` `get_item`) | When `include_deleted` is added, `get_summary` must pass `include_deleted=True`, or the summary of a removed item becomes 404 and BUG-1339's rules have nothing to apply to. Item manager FU-3 is answered for this service: **reachable**. | `get_summary` R2 |
| FU-2 | **Product-wide dates** (machine manager FU-9) | "Today" is `date.today()` (server local date) while order `created_at` is UTC; around midnight a transfer of "today" UTC can fall outside the 30-day window. | `get_summary` R5 |
| FU-3 | **Orders overview service** (`app/services/orders_overview_service.py`) | `_po_report_date` and `_in_date_range` are borrowed from it; a change there changes this summary. | `_order_stats_for_item` R3 |

## Overview
`ItemSummaryService.get_summary` builds the read-only "item hub" dialog (`GET /items/{item_id}/summary/`, `app/api/v1/endpoints/items.py`; the caller's workspace from `get_current_workspace`): the item and its tags, factory stock, finished goods, machine placements, purchase / transfer / sales statistics for 30 days, 90 days and all time, purchase pricing, supplier statistics, where the item is used (formulas, batches, project components, work orders), and the 10 newest stock movements. It must show only this workspace's data, count only live rows, and never write. It is **not** a `BaseService`: it never commits or rolls back.

**Callables:** 22 specified · 2 not specified
**Externals to mock:** none. `date.today()` is read unpatched (build dates from `date.today()` in the test, as machine manager Notes).
**Integration-only behavior:** the RFC 7807 body of `NotFoundError` (`tests/unit/core/exceptions.spec.md`); the endpoint's workspace dependency.

**Notes for the test designer**
- Import: `from app.services.item_summary_service import ItemSummaryService, item_summary_service, _dec, _est_value`. `ItemSummaryService()` takes no arguments. `get_summary(db, *, item_id, workspace_id)` keyword-only.
- Rows needed are built directly (see `v1.py` for minimal required columns): `Status(workspace_id, name, comment)`, `Account(workspace_id, name)`, `Factory(workspace_id, name, abbreviation)`, `PurchaseOrder(workspace_id, po_number, destination_type, destination_id, current_status_id, created_by, account_id, order_date, voided)`, `PurchaseOrderItem(workspace_id, purchase_order_id, line_number, item_id, quantity_ordered, unit_price, line_subtotal)`, `SalesOrder(... sales_order_number unique, account_id, factory_id, current_status_id, created_by, order_date)`, `SalesOrderItem(... quantity_ordered, unit_price, line_total)`, `WorkOrderType(workspace_id, name)`, `WorkOrder(workspace_id, work_order_number, work_order_type_id, title, factory_id)`, `WorkOrderItem(workspace_id, work_order_id, item_id, quantity)`, `InventoryLedger(... qty_before, qty_after, performed_by)`.
- **Set `performed_at` explicitly** on every ledger entry (inventory and product ledgers default to the database clock, BUG-2529; within one transaction all `now()` values are equal).
- The private helpers are pure or near-pure and can be tested directly with tuples / schema rows (`_pricing_snapshot_from_po_lines`, `_supplier_period_snapshot`, `_supplier_rows_from_po_lines`, the two `_pick_*`). Row tuples for the supplier helpers are `(account_id, account_name, po_id, qty, unit_price, line_subtotal, po_date)`.
- Monetary and quantity fields are `Decimal`; compare with `Decimal("…")`. Numeric(15,2) columns come back with two places (`Decimal('121.00')`).
- `ItemSummaryResponse` is a Pydantic model; read fields by attribute.
- **More minimum rows (gap G4; read from the models 2026-11-10).** NOT NULL columns with no default, then foreign keys:

  | Model (table) | Required columns | FKs |
  |---|---|---|
  | `TransferOrder` (`transfer_orders`) | `workspace_id`, `transfer_number`, `source_location_type`, `source_location_id`, `destination_location_type`, `destination_location_id`, `current_status_id`, `created_by` | `current_status_id` → `statuses`, `created_by` → `profiles` |
  | `TransferOrderItem` (`transfer_order_items`) | `workspace_id`, `transfer_order_id`, `line_number`, `item_id`, `quantity` | `transfer_order_id` → `transfer_orders`, `item_id` → `items` |
  | `PoReceiveEvent` (`po_receive_events`, `app/models/po_receive_event.py`) | `workspace_id`, `purchase_order_id`, `event_type` (`'receive'` / `'correction'`) | `purchase_order_id` → `purchase_orders` |
  | `PoReceiveEventItem` (`po_receive_event_items`) | `receive_event_id`, `po_item_id`, `quantity_delta` — **no `workspace_id` column** | `receive_event_id` → `po_receive_events`, `po_item_id` → `purchase_order_items` |
  | `PurchaseOrderReturn` (`purchase_order_returns`) | `workspace_id`, `purchase_order_id`, `return_number`, `created_by` | `purchase_order_id` → `purchase_orders` |
  | `PurchaseOrderReturnItem` (`purchase_order_return_items`) | `workspace_id`, `return_id`, `po_item_id`, `item_id`, `quantity_returned` | `return_id` → `purchase_order_returns`, `po_item_id` → `purchase_order_items` |
  | `ProductionFormula` (`production_formulas`) | `workspace_id`, `formula_code`, `name` | — |
  | `ProductionFormulaItem` (`production_formula_items`) | `workspace_id`, `formula_id`, `item_id`, `item_role`, `quantity` | `formula_id` → `production_formulas` |
  | `ProductionBatch` (`production_batches`) | `workspace_id`, `batch_number`, `production_line_id`, `batch_date` | `production_line_id` → `production_lines`, `formula_id` (nullable) → `production_formulas` |
  | `ProductionBatchItem` (`production_batch_items`) | `workspace_id`, `batch_id`, `item_id`, `item_role` | `batch_id` → `production_batches` |
  | `Project` (`projects`) | `workspace_id`, `factory_id`, `name`, `description` | `factory_id` → `factories` |
  | `ProjectComponent` (`project_components`) | `workspace_id`, `project_id`, `name` | `project_id` → `projects` |
  | `ProjectComponentItem` (`project_component_items`) | `workspace_id`, `project_component_id`, `item_id`, `qty` | `project_component_id` → `project_components` |
  | `InventoryLedger` (`inventory_ledger`) | `workspace_id`, `inventory_type`, `factory_id`, `item_id`, `transaction_type`, `quantity`, `qty_before`, `qty_after` | `factory_id` → `factories`, `performed_by` (nullable) → `profiles` |
  | `ProductLedger` (`product_ledger`) | `workspace_id`, `factory_id`, `item_id`, `transaction_type`, `quantity`, `qty_before`, `qty_after` | `factory_id` → `factories` |
  | `MachineItemLedger` (`machine_item_ledger`) | `workspace_id`, `machine_id`, `item_id`, `transaction_type`, `quantity`, `unit_cost`, `total_cost`, `qty_before`, `qty_after`, `source_type`, `performed_by` | `machine_id` → `machines`, `performed_by` → `profiles` |
  | `ItemTag` (`item_tags`) | `workspace_id`, `name`, `tag_code` | — |
  | `ItemTagAssignment` (`item_tag_assignments`) | `workspace_id`, `item_id`, `tag_id` | `tag_id` → `item_tags` |
  | `MachineSectionAssignment` (`machine_section_assignments`) | `workspace_id`, `machine_id`, `factory_section_id` | `factory_section_id` → `factory_sections` |
  | `WorkOrderItem` (`work_order_items`) | `workspace_id`, `work_order_id`, `item_id`, `quantity` | `work_order_id` → `work_orders` |

  Every model here also has `workspace_id` → `workspaces`, except `PoReceiveEventItem`; every `item_id` → `items`. `WorkOrderItem.created_at` has a database default (`now()`) and **can be set explicitly** (do so, to order the work-order preview). `MachineItemLedger.order_type` (String(30)) and `order_id` (Integer, no FK, polymorphic) are nullable and **can be set** on hand-made rows (`_resolve_order_link` R1).
- **Soft-delete columns (gap G6).** An account's real soft delete (`AccountManager.delete_account` → DAO `update`) writes `is_deleted = True`, `is_active = False`, `deleted_at = utcnow()`, `deleted_by = <user id>`. A stock row's (`DAOInventory.soft_delete`) writes `is_active = False`, `is_deleted = True`, `deleted_at = now()` (database clock), `deleted_by = <user id>`. `Factory`, `FactorySection`, `Machine`, `Product`, `Project` carry the same four columns; `WorkOrderItem` has `is_deleted`, `deleted_at`, `deleted_by` (no `is_active`); `ProductionFormula`, `ItemTag`, `Item` have only `is_active`.
- **Ledger time columns (gap G5).** `inventory_ledger.performed_at` and `product_ledger.performed_at`: `timestamp without time zone`, database default `now()`; `machine_item_ledger.performed_at`: `timestamp without time zone`, Python default `utcnow()` (naive). Values read back from the database are naive; an aware value exists only on an in-session object it was assigned to.
- **Table names (gap G8)**, confirmed from the models: `purchase_order_items`, `accounts`, `products`, `machine_items`, `item_tag_assignments`, `product_ledger`, `inventory_ledger`, `production_formula_items`, `project_component_items` (also `purchase_orders`, `sales_order_items`, `transfer_order_items`, `work_order_items`, `production_batch_items`).
- **Terminal status (BUG-2486).** Build an `OrderWorkflow(workspace_id, name, type, status_sequence=[S1.id, S2.id])` and set the PO's `order_workflow_id` and `current_status_id = S2.id` for a terminal order (columns per `order_workflow_terminal.spec.md` Notes).

## Not specified
- `item_summary_service = ItemSummaryService()` — module singleton, no logic.
- `USAGE_PREVIEW_LIMIT = 5` — constant; its effect is `_usage` R4.

---

## `_dec(value)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: every figure below)

**Purpose:** Turn a column value into a `Decimal`, empty as zero.

**Rules:**
- **R1.** `None` → `Decimal(0)`.
- **R2.** Anything else → `Decimal(str(value))`: `Decimal("5.00")` stays `Decimal("5.00")`, the int `3` gives `Decimal("3")`, the float `0.1` gives `Decimal("0.1")` (not its binary expansion), `0` gives `Decimal("0")`.
- **R3.** A value whose text is not a number (e.g. `"abc"`) raises `decimal.InvalidOperation`.

**Errors:** R3. **Side effects:** none.

---

## `_est_value(qty, avg_price)`
**Shape:** compute · **Persistence:** pure · **Visibility:** internal (used by: `_inventory_rows`)

**Purpose:** Estimated stock value of a bucket.

**Rules:**
- **R1.** `avg_price` `None` → `None`.
- **R2.** `qty <= 0` (0 or negative) → `None`, whatever the price.
- **R3.** Otherwise `Decimal(str(avg_price)) * qty`, not rounded: 7 @ `Decimal("2.50")` → `Decimal("17.50")`; 3 @ `Decimal("0")` → `Decimal("0")` (a zero price is a price).

**Errors:** none. **Side effects:** none.

---

## `ItemSummaryService.get_summary(db, *, item_id, workspace_id)`
**Shape:** get-or-404 (aggregate) · **Persistence:** reads · **Visibility:** public (used by: `GET /items/{item_id}/summary/`)

**Purpose:** The whole item hub for one item of the caller's workspace.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | not checked |
| `item_id` | int | the item |
| `workspace_id` | int | caller's workspace; every section is scoped to it |

**Returns:** `ItemSummaryResponse` with `item`, `kpis`, `inventory_rows`, `product_rows`, `machine_placements`, `order_stats`, `pricing`, `supplier_stats`, `usage_counts`, `usage_details`, `recent_activity`.

**Rules:**
- **R1.** No item with that id, or an item of another workspace (item manager `get_item` R2) → `NotFoundError` (404) with detail `Item with ID <item_id> not found`; nothing else is read.
- **R2.** A removed item (`is_active = False`) is summarised (200), with `item.is_active = False` (verified). This must keep holding after BUG-937: the call then passes `include_deleted=True` (FU-1). What a removed item's summary shows is R7.
- **R3.** `item` carries the item's `id`, `workspace_id`, `name`, `description`, `unit`, `sku`, `is_active`, `created_at`, `updated_at`, `created_by`, `updated_by` as stored, and `tags` = item manager `get_tags_for_item` (active tags of the item in this workspace; order BUG-932), each as `id`, `name`, `tag_code`, `color`, `icon`, `is_system_tag`. A removed item's tags are shown (assignment DAO P1, intended).
- **R4.** `kpis`: `storage_qty_total` = `_inventory_rows` R4; `machine_placement_count` = number of entries in `machine_placements`; `product_qty_total` = `_product_rows` R3; `factory_count_with_stock` = `_inventory_rows` R5.
- **R5.** One "today" (`date.today()`) is read once and used for every window: 30 days = `today − 30 … today`, 90 days = `today − 90 … today`, both bounds inclusive (31 and 91 calendar days); all time = no date bound. A date after today is in "all time" only.
- **R6.** Sections follow their helpers: `inventory_rows` `_inventory_rows`; `product_rows` `_product_rows`; `machine_placements` `_machine_placements`; `order_stats.days_30 / days_90 / all_time` `_order_stats_for_item`; `pricing` `_pricing`; `supplier_stats` `_supplier_stats`; `usage_counts` / `usage_details` `_usage`; `recent_activity` `_recent_activity` (limit 10).
- **R7.** [BUG-1339] For a removed item, `inventory_rows`, `product_rows` and `machine_placements` are empty and `storage_qty_total`, `product_qty_total`, `machine_placement_count`, `factory_count_with_stock` are 0; the stock rows stay untouched and show again once the item is active. Order stats, pricing, suppliers, usage and recent activity are shown as for an active item. *(Today: factory stock and machine placements are shown with their totals; finished goods are hidden only once BUG-1338 is fixed in the product DAO.)*
- **R8.** Nothing is written, flushed, committed or rolled back: a change pending in the session before the call is still pending after it (TC6 in spirit; this is not a `BaseService`). Any exception from a read reaches the caller unchanged.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| missing / other workspace | `NotFoundError` (404) | `Item with ID <item_id> not found` |

**Side effects:** none.

---

## `ItemSummaryService._factory_name_map(db, workspace_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `get_summary` → `_inventory_rows`, `_product_rows`, `_recent_activity`)

**Rules:**
- **R1.** Returns `{factory id: name}` for **every** factory of the workspace, soft-deleted and inactive ones included (names of deleted factories label history). Another workspace's factories are not in it. No factories → `{}`.

---

## `ItemSummaryService._machine_name_map(db, workspace_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `_recent_activity`)

**Rules:**
- **R1.** Returns `{machine id: name}` for every machine of the workspace, soft-deleted ones included. Another workspace's machines are not in it.

---

## `ItemSummaryService._machine_location_map(db, workspace_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `_machine_placements`)

**Purpose:** Where each live machine of the workspace sits.

**Rules:**
- **R1.** One entry per machine of the workspace with `is_deleted = False`: `{machine id: {machine_name, factory_section_id, factory_section_name, factory_id, factory_name}}`. A soft-deleted machine has no entry.
- **R2.** A machine with no section assignment has `factory_section_id` and `factory_section_name` `None`. (A machine has at most one assignment: unique `machine_id`.)
- **R3.** [BUG-2520] (HR-16) The factory and the section are taken only from this workspace: a machine whose factory belongs to another workspace has no entry (its placement then follows `_machine_placements` R3); a section of another workspace is treated as none (`None`, `None`). *(Today: joined by id only; the other workspace's factory / section id and name are returned.)*
- **R4.** [BUG-2525] (HR-4) A soft-deleted section is treated as none (`None`, `None`); the assignment row is untouched. *(Today: the deleted section's id and name are returned.)*
- **R5.** The machine's own factory's state is not read here (a machine of a deleted factory has an entry); hiding those placements is machine item DAO `get_by_item` (BUG-981).

---

## `ItemSummaryService._inventory_rows(db, *, item_id, workspace_id, factory_names)`
**Shape:** list · **Persistence:** reads · **Visibility:** internal (used by: `get_summary`)

**Purpose:** The item's factory stock lines, storage total and the factories holding any.

**Returns:** a tuple `(rows, storage_total, factory_ids)`: `list[ItemSummaryInventoryRow]` (fields `factory_id`, `factory_name`, `inventory_type`, `qty`, `avg_price`, `est_value`), `int`, `set[int]`.

**Rules:**
- **R1.** Reads inventory DAO `get_by_item` (live stock rows of the item in the workspace; [BUG-884] none of a soft-deleted factory). Rows with `is_deleted = True` are skipped (cannot come from the DAO) and rows with `qty <= 0` are skipped.
- **R2.** Each kept row gives `factory_id`, `factory_name` (from the factory map; a factory id missing from it shows `Factory #<id>`), `inventory_type` as its text value (`"STORAGE"`, `"DAMAGED"`, `"WASTE"`, `"SCRAP"` — also when the in-session object holds the type as a plain string), `qty`, `avg_price` as stored (may be `None`), `est_value` = `_est_value(qty, avg_price)`.
- **R3.** Every inventory type is listed, not only STORAGE.
- **R4.** `storage_total` = sum of `qty` of kept rows with type STORAGE only (DAMAGED / WASTE / SCRAP excluded); no kept STORAGE row → 0.
- **R5.** The factory set = distinct `factory_id`s of kept rows of **any** type: a factory holding only DAMAGED stock counts.
- **R6.** [BUG-2520] (HR-16) A stock row whose factory belongs to another workspace is left out of the list, the storage total and the factory set. *(Today: listed as `Factory #<id>`, the other workspace's id, and counted.)*
- **R7.** Order: today factory name ascending **case-sensitively**, then inventory type text ascending; equal pairs keep the DAO's order (none). [BUG-2522] Intended (HR-6): factory name case-insensitive, then `factory_id` ascending, then inventory type text ascending.
- **R8.** [BUG-1339] For a removed item → `[]`, 0, empty set (see `get_summary` R7). *(Today: listed.)*

---

## `ItemSummaryService._product_rows(db, *, item_id, workspace_id, factory_names)`
**Shape:** list · **Persistence:** reads · **Visibility:** internal (used by: `get_summary`)

**Purpose:** The item's finished-goods lines and total.

**Returns:** a tuple `(rows, total_qty)`: `list[ItemSummaryProductRow]` (fields `factory_id`, `factory_name`, `qty`, `avg_cost`, `selling_price`, `is_available_for_sale`, `margin_hint`), `int`.

**Rules:**
- **R1.** Reads product DAO `get_by_item` (live rows of the item in the workspace; [BUG-1328] none of a deleted factory; [BUG-1338] none for a removed item). The `is_deleted` skip cannot run (the DAO excludes them); rows with `qty <= 0` are skipped.
- **R2.** Each kept row: `factory_id`, `factory_name` (map, else `Factory #<id>`), `qty`, `avg_cost`, `selling_price` as stored, `is_available_for_sale` as a bool, `margin_hint` = `selling_price − avg_cost` (exact, may be negative or 0) when both are present, else `None` (either one missing → `None`).
- **R3.** `total_qty` = sum of `qty` of kept rows; none → 0.
- **R4.** [BUG-2520] (HR-16) A row whose factory belongs to another workspace is left out of the list and the total. *(Today: `Factory #<id>`, counted.)*
- **R5.** Order: today factory name ascending case-sensitively; ties keep the DAO's order (none, BUG-1326). [BUG-2522] Intended: factory name case-insensitive, then `factory_id` ascending.

---

## `ItemSummaryService._machine_placements(db, *, item_id, workspace_id, machine_locations)`
**Shape:** list · **Persistence:** reads · **Visibility:** internal (used by: `get_summary`)

**Purpose:** Which machines hold the item.

**Rules:**
- **R1.** Reads machine item DAO `get_by_item` with its defaults ([BUG-981] no rows of a deleted machine or of a machine in a deleted factory; [BUG-982] no 500-row cap). Every row is listed, **including `qty = 0`** (decided intended, see Review).
- **R2.** Each row: `machine_id`, `machine_name`, `factory_id`, `factory_name`, `factory_section_id`, `factory_section_name` from the location map; `qty`, `req_qty`, `defective_qty` as stored; `is_low_stock` = `req_qty` is not `None` **and** `qty < req_qty` (`req_qty` `None` → `False`; `qty == req_qty` → `False`; `req_qty = 0` → `False`).
- **R3.** A machine missing from the location map shows `machine_name` `Machine #<machine_id>`, `factory_id` 0, `factory_name` `—`, section `None` / `None`. After BUG-981 and BUG-2520 only a machine whose factory is of another workspace reaches this — and [BUG-2520] (HR-16) such a placement, and a placement whose machine belongs to another workspace, is left out of the list and the count. *(Today: a machine of another workspace shows as `Machine #<its id>`; a machine whose factory is foreign shows that factory's name.)*
- **R4.** [BUG-1339] For a removed item → `[]` (count 0). *(Today: listed.)*
- **R5.** Order: low-stock rows first, then factory name, then section name (`None` as `""`), then machine name, all case-sensitive today; ties keep the DAO's order (BUG-977). [BUG-2522] Intended: low-stock first, then factory name, section name (none first), machine name, each case-insensitive, then `machine_id` ascending.

---

## `ItemSummaryService._order_stats_for_item(db, *, workspace_id, item_id, from_date, to_date)`
**Shape:** compute · **Persistence:** reads · **Visibility:** internal (used by: `get_summary`, three times)

**Purpose:** Quantities and money of the item's purchase, transfer and sales lines in a window.

**Inputs:** `from_date`, `to_date`: both dates → window; either `None` → no date filter (all time).

**Returns:** `ItemSummaryOrderStats` (`purchase_qty`, `transfer_qty`, `sales_qty`, `total_quantity`, `total_spend` as `Decimal`, `line_count` int; all 0 when nothing matches). [BUG-2485] Plus `sales_revenue` (`Decimal`, default 0) *(requires the new field on `ItemSummaryOrderStats`)*.

**Rules:**
- **R1.** Only lines with this `item_id` on orders whose `workspace_id` is the caller's are read.
- **R2.** Purchase lines: every line counts its `quantity_ordered` into `purchase_qty` and `total_quantity`, its `line_subtotal` (empty → 0) into `total_spend`, and 1 into `line_count`. Order status, receipt and refunds are not read.
- **R2a.** [BUG-2521] Lines of a voided purchase order (`voided = True`) are not counted. *(Today: counted; verified.)*
- **R3.** Purchase date = the order's `order_date`, or the date part of its `created_at` when `order_date` is empty. Window test: `from_date <= date <= to_date`.
- **R4.** Transfer lines: `quantity` into `transfer_qty` and `total_quantity`, 1 into `line_count`, nothing into `total_spend`; date = date part of the transfer order's `created_at`. Status not read.
- **R5.** Sales lines: `quantity_ordered` into `sales_qty` and `total_quantity`, 1 into `line_count`; date = the sales order's `order_date`. Status, delivery and refunds not read.
- **R5a.** [BUG-2485] A sales line's `line_total` (empty → 0) goes into `sales_revenue`, **not** into `total_spend`; `total_spend` = purchase line subtotals only (R2). Transfers add to no money figure (R4). *(Today: `line_total` is added to `total_spend` and there is no `sales_revenue`; verified 452.00 = 152.00 purchases + 300.00 sales.)*
- **R6.** With only one of `from_date` / `to_date` given, no date filter applies (unreachable from `get_summary`).
- **R7.** Fractional quantities are summed exactly (`2.50 + 1.25` → `3.75`).

---

## `ItemSummaryService._pricing_snapshot_from_po_lines(lines)`
**Shape:** compute · **Persistence:** pure · **Visibility:** internal (used by: `_pricing`)

**Inputs:** `lines`: list of `(quantity_ordered, unit_price)`.

**Rules:**
- **R1.** Lines with `unit_price` `None` are ignored entirely.
- **R2.** `min_unit_price` / `max_unit_price` = least / greatest price of the remaining lines; none → `None`. A line with quantity 0 still counts for min / max.
- **R3.** `avg_unit_price_weighted` = Σ(price × quantity) / Σ quantity over the remaining lines, not rounded (`1.369369369369369369369369369` verified); Σ quantity `<= 0` (no lines, or only zero quantities) → `None`.
- **R4.** Empty `lines` → all three `None`.

---

## `ItemSummaryService._pricing(db, *, workspace_id, item_id, today)`
**Shape:** compute · **Persistence:** reads · **Visibility:** internal (used by: `get_summary`)

**Rules:**
- **R1.** Reads the item's purchase lines on orders of the workspace (dates as `_order_stats_for_item` R3).
- **R1a.** [BUG-2521] Lines of voided purchase orders are left out of every figure below. *(Today: included; verified: the voided PO's line was in open lines and prices.)*
- **R2.** `last_unit_price` = the `unit_price` of the line with the latest purchase date, ties broken by the greatest line `id`; no line → `None`.
- **R2a.** [BUG-2524] Only priced lines are considered: the newest **priced** line's price; no priced line → `None`. *(Today: when the newest line is unpriced the result is `None` although older lines have prices.)*
- **R3.** `period.days_30` / `days_90` / `all_time` = `_pricing_snapshot_from_po_lines` over the lines dated in `today − 30 … today`, `today − 90 … today`, and all lines.
- **R4.** `open_po_line_count` = number of lines with `quantity_ordered > quantity_received + quantity_refunded`; `open_qty_outstanding` = Σ(ordered − received − refunded) over them (exact `Decimal`; none → 0). A fully received or fully refunded line is not open; over-received is not open.
- **R4b.** [BUG-2486] Lines of an order whose current status is its workflow's terminal status (per `order_workflow_terminal.spec.md`: last id of the workflow's `status_sequence`, workflow of the same workspace) are not open. An order with no workflow, no current status, or a workflow with an empty sequence stays open. *(Today: counted whatever the status.)*
- **R4a.** [BUG-2521] Lines of voided purchase orders are not open. *(Today: counted; verified 4 / 121.00.)*

---

## `ItemSummaryService._supplier_stats(db, *, workspace_id, item_id, today)`
**Shape:** compute · **Persistence:** reads · **Visibility:** internal (used by: `get_summary`)

**Rules:**
- **R1.** Reads the item's purchase lines on orders of the workspace **that have a supplier** (`account_id` set) with the supplier's name, order id, quantity, unit price, subtotal and purchase date (as `_order_stats_for_item` R3); orders with no account are left out of supplier stats.
- **R2.** `period.days_30` / `days_90` / `all_time` = `_supplier_period_snapshot` with 30, 90, `None` days.
- **R2a.** [BUG-2521] Lines of voided purchase orders are left out. *(Today: included; verified: Beta from a voided PO was "cheapest".)*
- **R3.** [BUG-2520] (HR-16) A line whose supplier account belongs to another workspace is left out of supplier stats. *(Today: listed with that workspace's account name and id; verified.)*
- **R4.** A soft-deleted or inactive supplier account of this workspace is listed under its stored name (history).
- **R5.** [BUG-2523] (HR-6, gap G7) The supplier rows are read in a fixed order: purchase date, then order id, then line id, all ascending, so the helpers below see ties in line-id order. *(Today: no `ORDER BY`.)*

---

## `ItemSummaryService._supplier_period_snapshot(rows, *, today, days)`
**Shape:** compute · **Persistence:** pure · **Visibility:** internal (used by: `_supplier_stats`)

**Rules:**
- **R1.** `days` `None` → every row; otherwise rows whose purchase date is in `today − days … today` (inclusive). A row with no date is left out of a window (unreachable from `_supplier_stats`: the date always has a value).
- **R2.** `highlights.cheapest` = `_pick_cheapest_supplier`, `highlights.most_frequent` = `_pick_most_frequent_supplier`, both over all suppliers of the window (not only the top 10).
- **R3.** `suppliers` = the supplier rows sorted by `total_spend` high to low, at most 10. [BUG-2523] Ties on `total_spend` are ordered by `account_id` ascending, so the 10th place is deterministic; the tie key is applied here in Python and holds for any input order. *(Today: ties keep the input order — the sort is stable — which follows the unordered query.)*
- **R4.** No rows → `highlights` both `None`, `suppliers` `[]`.

---

## `ItemSummaryService._supplier_rows_from_po_lines(rows)`
**Shape:** compute · **Persistence:** pure · **Visibility:** internal (used by: `_supplier_period_snapshot`)

**Rules:**
- **R1.** One row per distinct `account_id`; rows with `account_id` `None` are skipped (unreachable from `_supplier_stats`).
- **R2.** `account_name` = the last non-empty name seen for that account; all empty → `Account #<account_id>`.
- **R3.** `order_count` = number of distinct order ids; `total_qty` = Σ quantity; `total_spend` = Σ `line_subtotal` (empty → 0).
- **R4.** `avg_unit_price_weighted` = Σ(quantity × price) / `total_qty`, unrounded; `total_qty <= 0` → `None`.
- **R4a.** [BUG-2524] Unpriced lines are left out of the average: Σ(quantity × price) / Σ quantity over priced lines only; no priced line (or their quantity sums to 0) → `None`. `total_qty`, `total_spend`, `order_count` keep counting every line. *(Today: an unpriced line counts at price 0 — 10 @ 5.00 + 10 unpriced → 2.50, verified.)*
- **R5.** `last_order_date` = the latest purchase date of the account; `last_unit_price` = the price of the line on that date (empty price → `Decimal(0)` today).
- **R5a.** [BUG-2524] `last_unit_price` is the price of the account's newest **priced** line; no priced line → `None`. `last_order_date` stays the newest line's date. *(Today: an unpriced newest line gives `0`.)*
- **R5b.** An account whose lines all have no date gets `last_order_date = None` and `last_unit_price = None`, while its quantity, spend and order count (R3) and average (R4, R4a) are computed as for dated lines. Lines with no date never replace a dated line's date or price. Unreachable from `_supplier_stats`: the date is `coalesce(order_date, created_at::date)` and `purchase_orders.created_at` is NOT NULL, so every real line has a date; in the 30- and 90-day windows of `_supplier_period_snapshot` an undated line is dropped anyway. No bug (unreachable; a pure-helper rule only).
- **R6.** [BUG-2523] When several lines share the latest date, the line of the greatest order id gives the price; two lines of that same order → the later one in input order, which is the greater line id because `_supplier_stats` R5 reads them by line id. (The row tuple carries no line id, so the pure helper's own key is date, then order id, then input position.) *(Today: the first line seen on the latest date wins — a later equal date does not replace it.)*
- **R7.** Empty `rows` → `[]`.

---

## `ItemSummaryService._pick_cheapest_supplier(rows)`
**Shape:** compute · **Persistence:** pure · **Visibility:** internal

**Returns:** the chosen input row itself (the same `ItemSummarySupplierRow` object, `is` — not a copy and not a separate highlight type; `highlights.cheapest` holds that object), or `None`.

**Rules:**
- **R1.** Candidates = rows with an average and `total_qty > 0`; none → `None`. Otherwise the lowest average; equal averages → the higher `order_count`.
- **R2.** [BUG-2523] A remaining tie → lowest `account_id`. *(Today: the first in input order.)*

---

## `ItemSummaryService._pick_most_frequent_supplier(rows)`
**Shape:** compute · **Persistence:** pure · **Visibility:** internal

**Returns:** as `_pick_cheapest_supplier`: the chosen input row object itself, or `None`.

**Rules:**
- **R1.** Empty → `None`. Otherwise the highest `order_count`; equal counts → the lower average, a row with no average ranking as if 999999999.
- **R2.** [BUG-2523] An average of exactly `0` is a real price and wins that tie (today `0` is falsy and ranks as 999999999); a remaining tie → lowest `account_id` (today: the first in input order).

---

## `ItemSummaryService._usage(db, *, workspace_id, item_id)`
**Shape:** compute · **Persistence:** reads · **Visibility:** internal (used by: `get_summary`)

**Returns:** a tuple `(counts, details)`: `ItemSummaryUsageCounts` (`formula_count`, `batch_line_count`, `project_component_count`, `work_order_line_count`, ints) and `ItemSummaryUsageDetails` (lists `formulas`, `batches`, `projects`, `work_orders`, R3). `get_summary` puts them in `usage_counts` / `usage_details`.

**Rules:**
- **R1.** Counts, each over lines with this `item_id` whose own `workspace_id` is the caller's: `formula_count` = production formula item lines; `batch_line_count` = production batch item lines; `project_component_count` = project component item lines; `work_order_line_count` = work order item lines. They are line counts: a formula with the item as input and output counts 2. Inactive formulas and batches of any status (cancelled included) count.
- **R2.** [BUG-2525] (HR-4) Work-order lines with `is_deleted = True`, lines of a work order with `is_deleted = True`, and lines of a component whose project has `is_deleted = True` are not counted. *(Today: counted; verified 3 with one deleted line on a deleted order.)*
- **R3.** Previews: `formulas` (`formula_id`, `formula_code`, `name`, `item_role`), `batches` (`batch_id`, `batch_number`, `item_role`, `status`), `projects` (`project_id`, `project_name`, `component_id`, `component_name`), `work_orders` (`work_order_id`, `work_order_number`, `title`).
- **R4.** Each preview holds at most 5 entries. Order: formulas by formula name, then role; batches by `batch_date` newest first, then batch id high to low; projects by project name, then component name; work orders by the line's `created_at` newest first, then line id high to low. [BUG-2522] Intended for formulas and projects: names case-insensitive, then formula id / component id ascending as last key (today: collation order, ties undetermined, which decides who is in the 5).
- **R4a.** [BUG-2526] Each work order appears once (placed by its newest line); each project component once; each formula and each batch once per role. The 5 places count distinct entries. *(Today: one entry per line; verified `['WO-DEL', 'WO-1', 'WO-1']`.)*
- **R5.** [BUG-2525] The previews leave out what R2 leaves out. *(Today: `WO-DEL` listed first.)*
- **R6.** [BUG-2520] (HR-16) A line whose formula, batch, component, project or work order belongs to another workspace is neither counted nor listed. *(Today: counted, and listed with that workspace's id, code, name or number.)*
- **R7.** Nothing used → counts 0, previews `[]`.

---

## `ItemSummaryService._resolve_order_link(db, *, order_type, order_id, source_type, source_id)` — after BUG-2520: `(db, *, workspace_id, order_type, order_id, source_type, source_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `_activity_from_ledger`)

**Rules:**
- **R1.** `order_type` and `order_id` both truthy → returned as given, nothing read. (Machine ledger rows never carry them — machine item ledger DAO Q5 — so this branch is reached only by hand-made rows.)
- **R2.** Otherwise, `source_type` or `source_id` empty (`None`, `""`, `0`) → `(None, None)`.
- **R3.** `source_type == "purchase_order"` → `("purchase_order", <order id of purchase line source_id>)`; `"transfer_order"` → `("transfer_order", <order id of transfer line source_id>)`; line not found → `(None, None)`.
- **R4.** Any other source type → `(None, None)`.
- **R4a.** [BUG-2527] `po_receive_event_item` and `po_receive_event_item_reversal` → `("purchase_order", <purchase order of that event item's receive event>)`; `purchase_order_reversal` → `("purchase_order", <order of purchase line source_id>)`; `purchase_return_item` → `("purchase_order", <purchase order of that return>)`; `work_order` → `("work_order", source_id)`; a missing source row → `(None, None)`. `manual`, `adjustment`, `reconciliation`, `production_batch` stay `(None, None)`. *(Today: all `(None, None)`; verified for `po_receive_event_item`.)*
- **R5.** [BUG-2520] (HR-16) Only lines / orders of the caller's workspace resolve; a source in another workspace → `(None, None)`. The workspace is passed in as a new **required** keyword parameter `workspace_id` (no default, so no caller can skip the scope; decided by Claude under the reviewer's delegation (2026-11-10), gap G3), and `_activity_from_ledger` passes it on from `_recent_activity`. R1's pass-through of a given `order_type` / `order_id` is scoped the same way: the named order must be in the workspace, else `(None, None)`. *(Today: no workspace parameter; looked up by id only.)*

---

## `ItemSummaryService._resolve_order_number(db, *, order_type, order_id)` — after BUG-2520: `(db, *, workspace_id, order_type, order_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `_activity_from_ledger`)

**Rules:**
- **R1.** `order_type` or `order_id` empty → `None`.
- **R2.** `purchase_order` → `po_number`; `transfer_order` → `transfer_number`; `sales_order` → `sales_order_number`; `expense_order` → `expense_number`; `work_order` → `work_order_number`; no such order → `None`; any other type → `None`.
- **R3.** [BUG-2520] (HR-16) Only an order of the caller's workspace gives its number; another workspace's → `None` (and the link's type and id are `None` too, `_resolve_order_link` R5). Same new required `workspace_id` parameter as `_resolve_order_link` R5 (gap G3). *(Today: no workspace parameter; looked up by id only.)*

---

## `ItemSummaryService._activity_from_ledger(db, *, source, performed_at, transaction_type, quantity, factory_id=None, factory_name=None, machine_id=None, machine_name=None, inventory_type=None, order_type=None, order_id=None, source_type=None, source_id=None)`
**Shape:** mapper · **Persistence:** reads · **Visibility:** internal (used by: `_recent_activity`)

**Rules:**
- **R1.** Returns `ItemSummaryRecentActivity` with `source`, `performed_at`, `transaction_type`, `quantity`, `factory_id`, `factory_name`, `machine_id`, `machine_name`, `inventory_type` as given, and `order_type` / `order_id` from `_resolve_order_link`, `order_number` from `_resolve_order_number` for that resolved pair.
- **R2.** A `source` other than `inventory`, `product`, `machine` raises `pydantic.ValidationError` (unreachable from `_recent_activity`).
- **R3.** All parameters after `db` are keyword-only; the nine after `quantity` default to `None`. [BUG-2520] After the fix it also takes a required keyword `workspace_id`, passed to both resolvers (gap G3).

---

## `ItemSummaryService._recent_activity(db, *, workspace_id, item_id, factory_names, machine_names, limit=10)`
**Shape:** list · **Persistence:** reads · **Visibility:** internal (used by: `get_summary` with the default `limit`)

**Rules:**
- **R1.** Reads the newest `max(limit, 5)` entries (10 by default) of the item in the workspace from each of: the inventory ledger (inventory ledger DAO `get_by_workspace`), the product ledger (product ledger DAO `get_by_workspace`), the machine ledger (machine item ledger DAO `get_by_item`); each newest first by `performed_at` (ties BUG-640).
- **R2.** Inventory entries: `source` `inventory`, `factory_id`, `factory_name` from the map (`None` when the id is not in it), `inventory_type` text, order link from `source_type` / `source_id`. Product entries: `source` `product`, factory as inventory, no `inventory_type`. Machine entries: `source` `machine`, `machine_id`, `machine_name` from the map (`None` when absent), order link from `order_type` / `order_id`, else `source_type` / `source_id`. `quantity` is the entry's quantity as an int.
- **R3.** The entries of the three ledgers are merged, sorted by `performed_at` newest first, and the first `limit` returned. Equal times keep the order inventory, then product, then machine, and within a ledger the DAO's order.
- **R3a.** [BUG-2487] Before the merge every `performed_at` is brought to naive UTC: a zone-aware value is converted to UTC and its zone dropped; a naive value is taken as UTC already. The returned entries carry the normalised value, and mixing naive and aware entries never raises (decided by Claude under the reviewer's delegation (2026-11-10), gap G5). *(Today: the sort compares the raw values; one naive and one aware entry → `TypeError: can't compare offset-naive and offset-aware datetimes` → 500 (verified with plain datetimes). Values read back from the database are always naive — all three columns are `timestamp without time zone` — so today this happens only with an aware time still held on an in-session object; no writer in `app/` sets an aware `performed_at`.)*
- **R4.** Entries of a deleted factory, of a deleted machine and of a removed item are included (ledgers are history).
- **R5.** No entries → `[]`.
- **R6.** [BUG-2520] (HR-16) An entry whose factory or machine belongs to another workspace shows `factory_id` / `machine_id` and their names as `None`. *(Today: the foreign id is shown, the name `None`.)*
- **R7.** [BUG-2528] Order links and numbers are read together, only for the returned entries; the number of statements does not grow with the number of entries; result unchanged. *(Today: up to two reads per entry for all 30 read entries.)*

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 72–74 | `value is None` | `_dec` R1, R2, R3 |
| 78–80 | `avg_price is None or qty <= 0` | `_est_value` R1–R3 |
| 91–93 | item not found / other workspace | `get_summary` R1, R2 |
| 108–118 | tags loop (0 / many) | `get_summary` R3 |
| 138–152 | today; three windows | `get_summary` R5 |
| 189–190 | factory map, no `is_deleted` filter | `_factory_name_map` R1 |
| 193–194 | machine map | `_machine_name_map` R1 |
| 206 | inner join factory by id | `_machine_location_map` R3, R5 |
| 207–208 | outer join section, no `is_deleted` | `_machine_location_map` R2, R3, R4 |
| 211 | `Machine.is_deleted` false | `_machine_location_map` R1 |
| 240–241 | `is_deleted or qty <= 0` → skip | `_inventory_rows` R1 |
| 242–246 | enum vs string type | `_inventory_rows` R2 |
| 247–248 | STORAGE → total | `_inventory_rows` R4 |
| 249–250 | `qty > 0` (always true here) | `_inventory_rows` R5 |
| 254 | factory name fallback | `_inventory_rows` R2, R6 |
| 262 | sort | `_inventory_rows` R7 |
| 278–279 | `is_deleted or qty <= 0` | `_product_rows` R1 |
| 282–283 | both prices present | `_product_rows` R2 |
| 287 | factory fallback | `_product_rows` R2, R4 |
| 296 | sort | `_product_rows` R5 |
| 311 | `req_qty is not None and qty < req_qty` | `_machine_placements` R2 |
| 312–322 | location fallbacks | `_machine_placements` R3 |
| 319 | `factory_id is not None else 0` | `_machine_placements` R3 |
| 330–337 | sort | `_machine_placements` R5 |
| 357–358, 377–378, 395–396 | both dates given → window | `_order_stats_for_item` R3, R4, R5, R6 |
| 365–371 | purchase loop | `_order_stats_for_item` R2, R2a |
| 385–389 | transfer loop | `_order_stats_for_item` R4 |
| 403–409 | sales loop | `_order_stats_for_item` R5, R5a |
| 420–421 | `price is None` → skip | `_pricing_snapshot_from_po_lines` R1 |
| 429 | `weight_total > 0` | `_pricing_snapshot_from_po_lines` R3 |
| 430–431 | `prices` empty | `_pricing_snapshot_from_po_lines` R2, R4 |
| 445–454 | last row, `po_date desc, id desc` | `_pricing` R2, R2a |
| 480–496 | open lines filter | `_pricing` R4, R4a, R4b |
| 499 | `last_row and last_row[0] is not None` | `_pricing` R2 |
| 535 | `account_id isnot None` | `_supplier_stats` R1 |
| 531 | outer join account by id | `_supplier_stats` R3 |
| 551–558 | `days is None`; `row[6] is not None` | `_supplier_period_snapshot` R1 |
| 562, 568 | sort by spend, cut 10 | `_supplier_period_snapshot` R3 |
| 575–576 | `account_id is None` → skip | `_supplier_rows_from_po_lines` R1 |
| 581, 590–591 | name fallback / overwrite | `_supplier_rows_from_po_lines` R2 |
| 602–606 | later date → last price | `_supplier_rows_from_po_lines` R5, R6 |
| 611–615 | `total_qty > 0` | `_supplier_rows_from_po_lines` R4 |
| 633–642 | candidates; empty → None; min key | `_pick_cheapest_supplier` R1, R2 |
| 647–655 | empty → None; max key; `or 999999999` | `_pick_most_frequent_supplier` R1, R2 |
| 660–695 | four counts, `or 0` | `_usage` R1, R2, R6, R7 |
| 697–773 | four previews, order, `LIMIT 5` | `_usage` R3, R4, R4a, R5, R6 |
| 829–830 | `order_type and order_id` | `_resolve_order_link` R1 |
| 832–833 | empty source | `_resolve_order_link` R2 |
| 835–849 | purchase / transfer lookup, row found or not | `_resolve_order_link` R3, R5 |
| 851 | other source → none | `_resolve_order_link` R4, R4a |
| 860–861 | empty → None | `_resolve_order_number` R1 |
| 863–876 | five order types, else None; row or None | `_resolve_order_number` R2, R3 |
| 906–919 | build activity | `_activity_from_ledger` R1, R2 |
| 931 | `max(limit, 5)` | `_recent_activity` R1 |
| 934–955 | inventory loop; `hasattr(value)`; `if entry.factory_id` | `_recent_activity` R2, R6 |
| 957–972 | product loop | `_recent_activity` R2 |
| 974–991 | machine loop | `_recent_activity` R2 |
| 993–994 | sort, cut | `_recent_activity` R3, R3a, R5 |

## Gap log
- G1 (item_summary_service.cases.md gap G1) — fact — `**Returns:**` added to `_inventory_rows` (`(rows, storage_total, factory_ids)`), `_product_rows` (`(rows, total_qty)`), `_usage` (`(counts, details)`), with field names.
- G2 (gap G2) — fact — full keyword-only signature of `_activity_from_ledger` in its heading; new R3 (defaults `None`; `workspace_id` added by the BUG-2520 fix).
- G3 (gap G3) — intent, decided by Claude under the reviewer's delegation (2026-11-10) — both resolvers get a new required keyword `workspace_id` as part of BUG-2520; `_resolve_order_link` R5 and `_resolve_order_number` R3 say so, headings show the new signature; R1's pass-through is scoped too.
- G4 (gap G4) — fact — Overview Notes: minimum columns and FKs of 20 more models; `WorkOrderItem.created_at` and `MachineItemLedger.order_type` / `order_id` can be set.
- G5 (gap G5) — fact + intent — all three `performed_at` columns are naive `timestamp without time zone`; delegated decision: normalise to naive UTC before the merge → new `_recent_activity` R3a, 🐞 BUG-2487.
- G6 (gap G6) — fact — Overview Notes: columns written by a real account and stock-row soft delete; soft-delete columns per model.
- G7 (gap G7) — intent, decided by Claude under the reviewer's delegation (2026-11-10), within BUG-2523 — both places: supplier query ordered by date, order id, line id (new `_supplier_stats` R5, so SS-12 stays) and Python tie keys in the helpers (`_supplier_period_snapshot` R3; `_supplier_rows_from_po_lines` R6 reworded: the row tuple has no line id, so the helper's last key is input position).
- G8 (gap G8) — fact — Overview Notes: table names confirmed.
- G9 (gap G9) — fact — `**Returns:**` on both pick helpers: the chosen input row object itself (verified `is`), or `None`.
- G-V1 (verifier gap, round 3, source line ~587–606) — Fact — `_supplier_rows_from_po_lines` R5b: all-undated account → `last_order_date` and `last_unit_price` `None`; unreachable via `_supplier_stats` (`created_at` NOT NULL); no bug.
