# Spec — `app/services/orders_overview_service.py`

> **Status:** APPROVED (2026-11-10; owner answered OQ-29 → BUG-2480 and OQ-30 → BUG-2481; case-designer gaps G1–G7 closed, see Gap log)
> **Source commit:** e48a092

> **Review round 2026-11-10 (4), verifier gap.** `get_stats` R8c added from the code: an item `unit` of `""` gives `item_unit = None` (intended, decided by Claude under the reviewer's delegation (2026-11-10); no bug). Status stays APPROVED.
>
> **Review round 2026-11-10 (3), fill-gaps.** Cases gap 1 (factory view of another workspace's `factory_id`) closed under the reviewer's delegation (2026-11-10): new `_build_top_factories` R8b, tagged BUG-2504 (no new bug). Status stays APPROVED.
>
> **Review round 2026-11-10 (2), apply-review + fill-gaps.** **Owner** (recorded in `docs/testing/owner-questions.md`): OQ-29 confirmed — every money measure is reported as *committed* (approved and later, not voided), *projected* (drafts and orders awaiting approval) and their *total*; voided orders are in none; the web app shows the three as bar charts → 🐞 BUG-2480. OQ-30 — split: spend counts purchases only, sales revenue is its own figure, transfers stay out of money totals, items are ranked by purchased quantity → 🐞 BUG-2481. **Delegated** (decided by Claude under the reviewer's delegation (2026-11-10)): what "approved and later" means per order kind (Overview, *Money stage* D1–D8, from each order manager's own approval data; this also closes gap G3), that counts and quantities are not split, and the factory row's new money fields. Gaps G1, G2, G4–G7 were facts, answered from the code and models. No "pending owner" rule remains.

> **Review round 2026-11-10 (low supervision).** No owner answer in this round. **Delegated:** Q1–Q3 decided by Claude under the reviewer's delegation (2026-11-10; clear bugs: a crash, a wrong join, voided rows counted where the sibling reports exclude them). House-rule lines applied. **Owner:** OQ-29 (drafts counted as spend) and OQ-30 (totals add buying, moving and selling together) were parked in `docs/testing/owner-questions.md` (answered in round 2 above; the *pending owner* tags are gone).
>
> **Standing decisions applied here (not asked again):** a top-N cut needs a full, stable order ending in `id` (HR-6, BUG-747 precedent). HR-16: a row linking to another workspace's row is invalid data, never shown. Voided purchase and expense orders are left out of the calendar (`calendar_service.spec.md`), `item_orders_service` and `purchase_order_item_insights_service`; voided work orders are left out of the calendar (BUG-1876, owner OQ-14).
>
> **Verified by running** (my own scripts `v1_oo.py`, `v2_oo.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsup\oo\`, one outer transaction on `marker_test`, rolled back, private `COVERAGE_FILE`; session as the unit-test `db` fixture): every `factory_id` (including a factory with no orders) raises `InvalidRequestError: Query.filter() being called on a Query which already has LIMIT or OFFSET applied`; a voided PO (1000.00), a voided expense order (300.00), a `VOIDED` work order and a soft-deleted work order all counted; a PO to project component C1 (of a project in F1) was **not** credited to F1, while a PO whose `destination_id` equals project P2's id was credited to P2's factory F2; a PO to another workspace's factory, with another workspace's account and item, showed `OtherWsFactory`, `OtherWsVendor`, `OtherWsItem` and their ids; `limit=0` → 1 row, `limit=50` → all 3; `from_date > to_date` → five empty lists; `_filter_po_by_factory` matches storage / damaged / machine destinations and a PO with no `order_date` (by its `created_at` day); `_filter_transfer_by_factory` matches a transfer for both factories it touches; top factories credit a transfer to its destination's factory only; `line_subtotal = NULL` adds 0 spend; a work order's `created_at` came back as the database's local time (`00:39` under `America/New_York` for `05:39` UTC). **Read, not run:** the endpoint `app/api/v1/endpoints/orders_overview.py`, the web page `frontend/src/pages/newpages/orders/useOrdersOverviewPage.ts` (sends `factory_id` when a factory is picked, `limit=5`), `item_summary_service.py` (uses `_po_report_date`, `_in_date_range`). **Not run:** anything over HTTP.

## Review
> All decided or parked; applied 2026-11-10.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | Picking a factory on the orders overview always fails (500) | bug — BUG-2502 | delegation (crash) |
| Q2 | Orders sent to a project are credited to whichever project has the component's id | bug — BUG-2503 | delegation (wrong join) |
| Q3 | Voided purchase, expense and work orders are counted | bug — BUG-2500 | delegation (precedent: calendar, sibling reports) |
| Q4 | **OWNER** — drafts and orders awaiting approval count as spend and revenue | bug — BUG-2480 (OQ-29: committed / projected / total) | owner (2026-11-10) |
| Q5 | **OWNER** — "spend", "total value" and "quantity" add purchases, transfers and sales together | bug — BUG-2481 (OQ-30: split) | owner (2026-11-10) |

Decided by house rules: soft-deleted work orders counted (BUG-2501), another workspace's names and ids shown (BUG-2504), ties in every leaderboard (BUG-2505), deleted factories listed (BUG-2506).

### House-rule violations — applied automatically

- **HR-4** `_build_top_factories` R5 — soft-deleted work orders (`is_deleted = True`) are counted (verified). The calendar leaves them out. Intended: a deleted work order counts nowhere.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-2501 (pattern `list-returns-soft-deleted`). Rules: `_build_top_factories` R5a.
- **HR-4** `_build_top_factories` R9 — a soft-deleted factory is a row of the "top factories" list. Intended: a factory with `is_deleted = True` is not a row (its orders still count in the other sections, which list items and accounts, not factories; whether they should is the calendar's OQ-15 question, not raised again here).
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-2506 (pattern `list-returns-soft-deleted`). Rules: `_build_top_factories` R9a.
- **HR-16** `get_stats` R6a, R13a, R16, `_build_top_factories` R8a, `_factory_from_location` R2a, R3, `_filter_po_by_factory` R2a, R3, `_filter_transfer_by_factory` R2 — the item, account, factory, machine and project joins compare ids only, not workspaces. A stored link to another workspace's row (possible through BUG-728, BUG-1016 and the PO/transfer location writes) shows that workspace's item name and unit, account name, factory name and ids (verified). Intended: such a link is treated as not found — the line is left out of top items, the order is left out of vendors / customers, the location resolves to no factory (not credited, not matched by a factory filter); no other workspace's id or name is ever in the response.
**Answer:** bug — per HR-16 (house rule)
**Resolution:** 🐞 BUG-2504 (pattern `cross-workspace-row-exposed`, BUG-1086 / BUG-1801 precedent). Rules: as listed.
- **HR-6** `get_stats` R9, R14, R17, R19, `_build_top_factories` R11 — every leaderboard is cut to `limit` after sorting on its score only; ties keep query row order (no `ORDER BY`), so which tied row makes the cut can change between calls. Intended (BUG-747 precedent): ties broken by name case-insensitive ascending, then id ascending — items by item name then `item_id`; vendors and customers by account name then `account_id`; categories by category text ascending; factories by factory name then `factory_id`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2505 (pattern `unordered-pagination`; one bug for the five lists). Rules: as listed, each with an "a" rule.

Checked and **not** violated: **HR-5** — nothing is paged; every filter is in the query before the cut (the customers' factory filter crashes instead, Q1). **HR-7** — the endpoint requires `1 <= limit <= 10` (422 otherwise) and the service clamps to the same range. **HR-8** — no `LIKE`. **HR-9, HR-10** — read only. **HR-15** — nothing is rounded: sums of `Numeric(15,2)` values are exact `Decimal`s. **HR-3** — `expense_category` is validated to `factory` / `department` / `other` by the expense order manager. **HR-4 for accounts / items** — a soft-deleted account's orders keep counting and its name shows; items have no soft delete. Money already spent with a since-deleted vendor is history, and HR-4 speaks of filters and lists of the deleted rows themselves, so no line. **Workspace of the orders** — every order query filters on the order's own `workspace_id` (R2 of `get_stats`).

**Permission checks:** none in the service; the endpoint requires an active member of the workspace (`get_current_workspace`). Who may see vendor spend and customer revenue is routed to `docs/future/permissions.md`.

### New questions

### Q1. Picking a factory on the orders overview always fails — 🐞 BUG-2502
**Background:** `GET /orders/overview/stats` takes an optional `factory_id`; the web orders overview page sends it whenever a factory is picked in its filter. The "top customers" query is built with its `LIMIT` first and the factory condition added afterwards, which SQLAlchemy refuses.
**What happens today:** any `factory_id` — a real factory, one with no orders, any number — raises `InvalidRequestError` before anything is returned (verified), so the endpoint answers 500 and the page shows no leaderboards.
**Example:** a user opens Orders → Overview, picks "Dhaka plant" in the factory filter, and every panel errors.
**Rules affected:** `get_stats` R18
**Suggested answer:** bug — the factory condition is applied before the cut; the factory view returns the leaderboards described for `factory_id`.
**Answer:** bug — the factory filter works: customers are filtered to the factory before the top-`limit` cut
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10; a crash, no counting rule changes): 🐞 BUG-2502 (pattern `query-filter-after-limit`, new). Rules: `get_stats` R18. The other factory rules (R5, R12, R15, R20, R21) are written to what the code does once the crash is gone.

### Q2. Orders sent to a project are credited to the wrong factory — 🐞 BUG-2503
**Background:** a purchase or transfer order going to a project stores `destination_type = 'project'` and, in `destination_id`, a **project component** id (the PO and transfer managers read it that way: `project_component_dao.get_by_id_and_workspace`). This service looks the id up as a **project** id.
**What happens today:** the order is credited to the factory of the project whose id happens to equal the component's id, or to no factory if there is none (verified: a PO to component C1 of a project in F1 was not credited to F1; a PO whose id value equalled project P2's id was credited to P2's factory). The factory filter matches the same wrong way.
**Example:** a PO for 100.00 of cement goes to component "Foundation" (id 412) of project "Warehouse B" in factory "Chittagong". The overview credits it to factory "Dhaka", owner of unrelated project 412, or leaves it out of "Chittagong" entirely.
**Rules affected:** `_factory_from_location` R3, `_filter_po_by_factory` R3, `_filter_transfer_by_factory` R2
**Suggested answer:** bug — a `'project'` location is resolved component → its project → that project's factory.
**Answer:** bug — a project location is a project component; its factory is the factory of the component's project
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10; a wrong join, the meaning of the id is fixed by the order managers): 🐞 BUG-2503 (pattern `location-id-resolved-against-wrong-table`, new). Not a project-cost question: it decides which factory an order shows under. Rules: `_factory_from_location` R3, `_filter_po_by_factory` R3, `_filter_transfer_by_factory` R2.

### Q3. Voided purchase, expense and work orders are counted — 🐞 BUG-2500
**Background:** purchase and expense orders are voided by setting `voided = True`; work orders by status `VOIDED`. The calendar, the item orders list and the PO item insights leave voided purchase orders out; the calendar also leaves out voided expense orders and (BUG-1876, owner) voided work orders. Sales and transfer orders have no void.
**What happens today:** voided orders count everywhere here: their lines in top items, their totals in vendors and categories, and as orders and value in top factories (verified: a voided 1000.00 PO, a voided 300.00 expense order, a `VOIDED` work order).
**Example:** a 50,000.00 PO to "Rahim Steel" is voided as a mistake; "Rahim Steel" stays top vendor with 50,000.00 of spend.
**Rules affected:** `get_stats` R4a, R11a, `_build_top_factories` R2a, R5a
**Suggested answer:** bug — voided purchase, expense and work orders count nowhere in the overview.
**Answer:** bug — voided purchase orders (`voided`), voided expense orders (`voided`) and `VOIDED` work orders are left out of every section
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10; precedent: the calendar and the sibling item reports already exclude them): 🐞 BUG-2500 (pattern `voided-record-not-excluded`, BUG-717 / BUG-1876 precedent).

### Q4. **OWNER** — Drafts and orders awaiting approval count as spend and revenue — 🐞 BUG-2480 (OQ-29)
**Background:** the overview has no status filter. A draft PO's amount can still change; BUG-634 ruled that draft invoices do not count in money totals.
**What happens today:** every non-voided order in the period counts, whatever its status — draft, awaiting approval, approved, complete.
**Example:** a buyer drafts a 200,000.00 PO to try prices and never sends it; the vendor heads "top vendors" with 200,000.00.
**Rules affected:** `get_stats` R4, R4b, R11, R11b, R16, R16a, R19, R19b, `_build_top_factories` R2, R4, R5, R7a; Overview *Money stage* D1–D8
**Suggested answer:** intended — the overview ranks order activity in the period, as the calendar does; only voided orders are left out (BUG-2500).
**Alternatives:** (a) bug — money columns (spend, value, customer totals) count only orders past approval; counts keep every order. (b) bug — drafts are left out entirely.
**Answer:** owner, 2026-11-10 (OQ-29, confirmed): bug — each money measure is reported three times: *committed* (approved and later, not voided), *projected* (drafts and orders awaiting approval) and their *total*; voided orders are in none; the web app shows them as bar charts.
**Resolution:** 🐞 BUG-2480 (pattern `report-missing-committed-projected-split`, new). What "approved and later" means per order kind was decided by Claude under the reviewer's delegation (2026-11-10), from each order manager's own approval data: Overview *Money stage* D1–D8 (closes gap G3). Counts and quantities are not split: they count every non-voided order (D7). Requires new response fields (`app/schemas/orders_overview.py`) and a web change for the bar charts.

### Q5. **OWNER** — Totals add purchases, transfers and sales together — 🐞 BUG-2481 (OQ-30)
**Background:** one row per item and per factory sums every kind of order.
**What happens today:** an item's `total_spend` = purchase line subtotals **plus** sales line totals (money out plus money in); its `total_quantity` = quantity purchased + transferred + sold (a bolt bought 10, moved 10 and sold 10 shows 30), and items are ranked by that. A factory's `total_value` = PO totals + sales order totals + work order costs. The web page ranks items by `total_quantity` and shows "PO x · TR y"; it shows `total_value` per factory.
**Example:** factory "Dhaka" buys 10,000.00 of steel and sells 12,000.00 of goods in May: its total value reads 22,000.00.
**Rules affected:** `get_stats` R7, R7a, R9, R9a, `_build_top_factories` R7, R7a, R11, R11a
**Suggested answer:** bug — keep the per-kind columns (`purchase_qty`, `transfer_qty`, `sales_qty`) and split money into purchase spend and sales revenue (new fields); rank items by purchased quantity and factories by order count, then purchase spend.
**Alternatives:** (a) intended — the overview measures activity volume, not money. (b) leave transfers out of `total_quantity` only.
**Answer:** owner, 2026-11-10 (OQ-30): bug — split: spend counts purchases only; sales revenue is its own figure; transfers stay out of money totals; items are ranked by purchased quantity.
**Resolution:** 🐞 BUG-2481 (pattern `report-total-mixes-money-in-and-out`, new; the item summary's "Total spend", OQ-31, is the same root). Decided by Claude under the reviewer's delegation (2026-11-10), filling in what the answer leaves open: `total_quantity` and the per-kind quantities stay as they are (volume, not money); a factory's work order cost is its own figure too (it is neither a purchase nor a sale); factories rank by order count, then purchase spend. Requires new response fields.

## Follow-ups for other reviews
> Nothing below is a rule of this service and no bug is logged for it here.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Work order model / DAO** (`app/models/work_order.py`, not yet specified) | `created_at` has `server_default=func.now()` on a naive column: the database's local time (verified `00:39` under `America/New_York` for `05:39` UTC), so this overview's work-order day (`cast(created_at, Date)`) depends on the database time zone. Precedent BUG-2333 (`database-clock-timestamp`). | verifying `_build_top_factories` R5 |
| FU-2 | **Item summary service** (`app/services/item_summary_service.py`, same batch) | It reuses `_po_report_date` and `_in_date_range` from this module; their rules are R1 of each here. Its own voided / workspace handling is its own spec's. | callers |

## Overview
`OrdersOverviewService` builds the five leaderboards of the web "Orders → Overview" page for a date range: top items, top vendors, top customers, top expense categories and top factories. It reads purchase, transfer, sales, expense and work orders of one workspace and aggregates in SQL and Python. It is a plain class (not a `BaseService`), used as the singleton `orders_overview_service` by `GET /orders/overview/stats` (`from_date`, `to_date` required; `factory_id` optional; `limit` 1–10, default 5); `item_summary_service` borrows two date helpers. Read only.

**Callables:** 9 specified · 1 not specified
**Externals to mock:** none.
**Integration-only behavior:** none (plain SQL; the `case` / `coalesce` / `cast(… AS DATE)` expressions run on Postgres in the unit tests).

**Facts for the test designer**
- Import: `from app.services.orders_overview_service import OrdersOverviewService, orders_overview_service, _dec`. `OrdersOverviewService()` takes no arguments.
- Response models in `app/schemas/orders_overview.py`: `OrdersOverviewStatsResponse(top_items, top_vendors, top_customers, top_expense_categories, top_factories)`; `TopItemRow(item_id, item_name, item_unit, total_quantity, total_spend, line_count, purchase_qty, transfer_qty, sales_qty)`; `TopAccountRow(account_id, account_name, total_spend, order_count)`; `TopExpenseCategoryRow(category, total_spend, order_count)`; `TopFactoryRow(factory_id, factory_name, order_count, total_value, purchase_count, transfer_count, sales_count, work_count)`. Money and quantities are `Decimal`; an untouched per-kind quantity is `Decimal("0")`, a touched one carries the column's scale (`Decimal("50.00")`).
- Order dates per kind (the **report day**): PO = `order_date`, or the date part of `created_at` when `order_date` is `NULL`; transfer = date part of `created_at`; sales = `order_date`; expense = `expense_date`; work = date part of `created_at`. `created_at` of POs and transfers is naive UTC (`utcnow`); of work orders see FU-1.
- Location ids: `'storage'` / `'damaged'` → a factory id; `'machine'` → a machine id (machine has `factory_id`); `'project'` → a project component id (component → `project_id` → project's `factory_id`). PO destinations: `storage`, `machine`, `project` (`damaged` is matched too). Transfer sources: `storage`, `machine`, `damaged`; destinations: `storage`, `machine`, `project`, `damaged`.
- Required columns for hand-made rows (verified): `Status(workspace_id, name, comment)`; `PurchaseOrder(po_number, destination_type, destination_id, current_status_id, created_by)`; `PurchaseOrderItem(line_number, item_id, quantity_ordered)`; `TransferOrder(transfer_number, source_location_type/id, destination_location_type/id, current_status_id, created_by)`; `TransferOrderItem(line_number, item_id, quantity)`; `SalesOrder(sales_order_number, account_id, factory_id, current_status_id, created_by)`; `ExpenseOrder(expense_number, expense_category, created_by)`; `WorkOrder(work_order_number, work_order_type_id, title, factory_id)`; `Project(description)` is NOT NULL; `Item(name_normalized, unit)`.
- Line foreign keys (gap G1): `purchase_order_items.purchase_order_id` → `purchase_orders.id` (ON DELETE CASCADE, NOT NULL); `transfer_order_items.transfer_order_id` → `transfer_orders.id` (CASCADE, NOT NULL); `sales_order_items.sales_order_id` → `sales_orders.id`. All three line tables **have** their own `workspace_id` (NOT NULL, FK `workspaces.id` CASCADE); this service never reads it — lines are scoped through their order's `workspace_id` only (R2 of `get_stats`), so a line whose own `workspace_id` differs from its order's is counted under the order's workspace.
- Nullability (gap G6): `sales_orders.order_date` is `Date` **NOT NULL** (Python default `date.today`), so a sales order can never have a `NULL` report day; use `purchase_orders.order_date` (nullable) for a `NULL`-date case — a PO's report day then falls back to `created_at` (`_po_report_date` R1), so the `NULL` branch of `_in_date_range` R1 is reached only by calling it on a nullable column directly (e.g. `PurchaseOrder.order_date` or `PurchaseOrder.expected_delivery_date`).
- Soft delete (gap G5): an account is soft-deleted by `AccountManager.delete_account`, which writes `is_deleted = True`, `is_active = False`, `deleted_at = utcnow()`, `deleted_by = <user id>`. A factory by `DAOFactory.soft_delete`: `is_deleted = True`, `deleted_at = utcnow()`, `deleted_by = <user id>`; `is_active` is left as it was. A work order has `is_deleted`, `deleted_at`, `deleted_by`, `is_active`. Items have no soft-delete column (`is_active` only).
- Names (gap G4): no database uniqueness on `items.name`, `accounts.name` or `factories.name` (only indexes on `items.name_normalized` and `accounts.name`), so tests may insert two rows with the same name directly to reach the id tie-break.
- Method kinds (gap G7): `_factory_from_location` is a `@staticmethod`; `_po_report_date`, `_in_date_range`, `_filter_po_by_factory`, `_filter_transfer_by_factory`, `_accumulate_factory`, `_build_top_factories`, `get_stats` are instance methods (none uses instance state); `_dec` is a module function.

### Money stage (BUG-2480; owner OQ-29, 2026-11-10)
Intended rules, all expected-to-fail until BUG-2480 is fixed *(Today: no split; every non-voided order's money is in the single figure)*. "Approved and later" per kind was decided by Claude under the reviewer's delegation (2026-11-10), from the approval data each order manager already uses (no new column):
- **D1.** Every money measure of the response (listed in the rules that carry BUG-2480) is reported three times: `<measure>_committed`, `<measure>_projected`, and `<measure>` = committed + projected exactly (Decimal, no rounding). An order's money goes wholly to one of the two.
- **D2.** Voided orders (BUG-2500) and soft-deleted work orders (BUG-2501) are in none of the three.
- **D3. "Approvals met"** for an order = at least `required` of its approver rows have `approved = True`, where `required` = `required_approvals` when set (an explicit `0` is met at once), otherwise the number of approver rows, and **at least 1** when there are no approver rows and no explicit requirement (the BUG-755 / BUG-1202 / BUG-1203 rule, applied here to every kind; today those managers give 0 → met). Approver tables: `purchase_order_approvers`, `sales_order_approvers`, `expense_order_approvers`, `work_order_approvers`, each scoped to the order's workspace.
- **D4. Purchase order** — committed when approvals are met (D3), or its current status is the PO stage `Receiving` or `Complete` (the `statuses.name` of `current_status_id`; the stages are `Draft`, `Planning`, `Receiving`, `Complete`). Otherwise (`Draft` / `Planning` without approvals met) projected.
- **D5. Sales order** — committed when approvals are met (D3) or `order_completed = True`; otherwise projected.
- **D6. Expense order** (gap G3) — expense orders have **no status column**. Committed when approvals are met (D3, on `expense_order_approvers.approved` against `expense_orders.required_approvals`) or `completed_at IS NOT NULL` (the manager's and DAO's "complete" mark); otherwise projected. The columns `expense_orders.approved_at` / `approved_by` are **not** the mark: no code writes them (searched `app/`, 2026-11-10).
- **D7. Work order** — committed when its `status` is `IN_PROGRESS` or `COMPLETED` (starting requires approvals met), or it is `DRAFT` with at least one approver row and approvals met; any other `DRAFT` is projected. `VOIDED` is in none (D2).
- **D8.** Transfers carry no money and are not split. Counts and quantities (`order_count`, `line_count`, the per-kind counts, `total_quantity`, `purchase_qty`, `transfer_qty`, `sales_qty`) are not split: they count every non-voided, non-deleted order, committed or projected. Rankings use the total (D1). The stage is read as it is at call time, not as it was in the period.

**Notes for the test designer**
- Until BUG-2502 is fixed every call with a `factory_id` raises, so all factory-filter cases are expected-to-fail with that reason; `_filter_po_by_factory` and `_filter_transfer_by_factory` can be tested directly on a `db.query(PurchaseOrder.id)` / `db.query(TransferOrder.id)` already filtered by workspace (they pass today).
- Ties: create two rows with equal scores whose names sort opposite to their insertion order, to catch HR-6.

## Not specified
- `orders_overview_service` — module-level singleton, no logic.

---

## `_dec(value)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: `get_stats`, `_build_top_factories`)

**Purpose:** turn a database number (or nothing) into an exact `Decimal`.

**Rules:**
- **R1.** `None` → `Decimal(0)`.
- **R2.** Any other value → `Decimal(str(value))`: a `Decimal("12.50")` stays `Decimal("12.50")`; an int `3` → `Decimal("3")`; a float `0.1` → `Decimal("0.1")` (no binary noise). `0` → `Decimal("0")` (not the `None` path).

**Errors:** a value whose text is not a number (e.g. `"abc"`) raises `decimal.InvalidOperation`. Unreachable from the queries (numeric columns only).
**Side effects:** none.

---

## `OrdersOverviewService._po_report_date()`
**Shape:** helper · **Persistence:** pure (SQL expression) · **Visibility:** internal (used by: `get_stats`, `_build_top_factories`, `item_summary_service`)

**Rules:**
- **R1.** Gives the PO's report day: `order_date` when set, otherwise the date part of `created_at`. A PO with `order_date = 2026-05-10` and `created_at = 2026-11-10 05:40` has report day 2026-05-10; with `order_date = NULL` it is 2026-11-10 (verified).

---

## `OrdersOverviewService._in_date_range(column, from_date, to_date)`
**Shape:** helper · **Persistence:** pure (SQL expression) · **Visibility:** internal (used by: `get_stats`, `_build_top_factories`, `item_summary_service`)

**Rules:**
- **R1.** True when `from_date <= column <= to_date`, both ends included. A day equal to `from_date` or `to_date` is in; `from_date > to_date` matches nothing; a `NULL` column matches nothing.

---

## `OrdersOverviewService._filter_po_by_factory(query, factory_id)`
**Shape:** helper (filter) · **Persistence:** reads · **Visibility:** internal (used by: `get_stats` R5, R15)

**Purpose:** keep only purchase orders that go to the given factory.

**Rules:**
- **R1.** A PO is kept when its destination is `storage` or `damaged` with `destination_id = factory_id` (verified both).
- **R2.** A PO is kept when its destination is a `machine` whose `factory_id` is the factory (verified).
- **R2a.** [BUG-2504] A machine of another workspace never matches, even if its `factory_id` equals the given id. *(Today: the machine is joined by id only.)*
- **R3.** [BUG-2503] A PO is kept when its destination is a `project` **component** whose project's `factory_id` is the factory; a component of another workspace never matches. *(Today: `destination_id` is looked up as a project id — the PO matches when the project with that id, of any workspace, belongs to the factory; verified a PO to a component of a project in F1 did not match F1.)*
- **R4.** Any other PO (other factory, a machine / project of another factory, an unknown destination type, an id that matches no row) is dropped. Each kept PO appears once (each join finds at most one row).
- **R5.** The factory's own `is_deleted` / `is_active`, and the machine's / project's, are not looked at.

**Side effects:** none (returns a narrowed query).

---

## `OrdersOverviewService._filter_transfer_by_factory(query, factory_id)`
**Shape:** helper (filter) · **Persistence:** reads · **Visibility:** internal (used by: `get_stats` R12)

**Purpose:** keep only transfers that touch the given factory at either end.

**Rules:**
- **R1.** A transfer is kept when its destination **or** its source is `storage` / `damaged` with that location id = `factory_id`, or its destination or source is a `machine` of that factory (verified: a transfer from factory F2's storage to F1's machine matches both F1 and F2; one from F1's machine to F2's damaged stock matches both).
- **R2.** [BUG-2503] A transfer is kept when its destination is a `project` component whose project belongs to the factory. *(Today: looked up as a project id, as `_filter_po_by_factory` R3.)* A `project` **source** is never considered. [BUG-2504] Machines and components of another workspace never match. *(Today: joined by id only.)*
- **R3.** Any other transfer is dropped; each kept transfer appears once. Deleted / inactive locations are not looked at.

**Side effects:** none.

---

## `OrdersOverviewService._factory_from_location(location_type, location_id, machine_factory_id, project_factory_id)`
**Shape:** helper · **Persistence:** pure (SQL `CASE`) · **Visibility:** internal (used by: `_build_top_factories`)

**Purpose:** the factory a location belongs to.

**Rules:**
- **R1.** `storage` / `damaged` → the location id itself (taken as a factory id; not checked to exist).
- **R2.** `machine` → the joined machine's `factory_id`; `NULL` when no machine has that id.
- **R2a.** [BUG-2504] A machine of another workspace gives `NULL`. *(Today: its factory id is given.)*
- **R3.** [BUG-2503] `project` → the factory of the joined component's project; `NULL` when there is no such component in the workspace. *(Today: the factory of the project whose id equals the location id.)* For transfer **sources** the project value is always `NULL`.
- **R4.** Any other type → `NULL`.

---

## `OrdersOverviewService._accumulate_factory(factory_map, factory_id, amount, order_kind)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: `_build_top_factories`)

**Inputs (gap G2):** `factory_map` is a `collections.defaultdict` whose missing entries are created as the plain dict `{'order_count': 0, 'total_value': Decimal(0), 'purchase_count': 0, 'transfer_count': 0, 'sales_count': 0, 'work_count': 0}` (the factory is made by `_build_top_factories`; a test passes `defaultdict(lambda: {…those six keys…})`). A plain `dict` raises `KeyError` for a new factory id. Returns `None`; the map is changed in place. The entry shape is today's; the BUG-2480 / BUG-2481 fix adds keys (see `_build_top_factories` R7a) and is free to change this helper.

**Rules:**
- **R1.** `factory_id = None` → nothing changes (the order is not credited to any factory). `factory_id = 0` is credited (not the `None` path).
- **R2.** Otherwise the factory's entry (created at zero if new) gets `order_count + 1` and `total_value + amount`.
- **R3.** Its per-kind counter `+1`: `purchase` → `purchase_count`, `transfer` → `transfer_count`, `sales` → `sales_count`, `work` → `work_count`; any other kind raises no error and touches no per-kind counter (still R2).

---

## `OrdersOverviewService._build_top_factories(db, workspace_id, from_date, to_date, limit)`
**Shape:** compute (top-N) · **Persistence:** reads · **Visibility:** internal (used by: `get_stats` R21)

**Purpose:** rank the workspace's factories by how many orders of the period they had.

**Returns:** a list of at most `limit` `TopFactoryRow`.

**Rules:**
- **R1.** Only orders of `workspace_id` whose report day (Overview facts) is in `[from_date, to_date]` count.
- **R2.** Each purchase order counts once for the factory of its destination (`_factory_from_location`), adding its `total_amount` (purchase spend; committed or projected per D4 after BUG-2480). Every non-voided PO counts, whatever its stage.
- **R2a.** [BUG-2500] A voided PO (`voided = True`) counts nowhere. *(Today: counted, verified.)*
- **R3.** Each transfer order counts once, for the factory of its **destination**, or, when that gives none, of its **source**; it adds `0` to `total_value`. A transfer from F2's storage to F1's machine counts for F1 only (verified). A transfer neither end of which resolves counts nowhere.
- **R4.** Each sales order counts once for its own `factory_id`, adding its `total_amount` (sales revenue; D5 after BUG-2480), whatever its stage.
- **R5.** Each work order counts once for its own `factory_id`, adding its `cost` (`NULL` → 0) (work cost; D7 after BUG-2480). Every status counts except as R5a.
- **R5a.** [BUG-2500, BUG-2501] A work order with status `VOIDED` or with `is_deleted = True` counts nowhere. *(Today: both counted, verified.)*
- **R6.** Expense orders never count here.
- **R7.** `order_count` = POs + transfers + sales orders + work orders credited (every stage, D8).
- **R7a.** [BUG-2481, BUG-2480] A factory row carries three money measures, each kept apart and each split per D1: `purchase_spend` (PO totals, D4), `sales_revenue` (sales order totals, D5) and `work_cost` (work order costs, D7), with `…_committed` / `…_projected` for each; transfers add to none. `total_value` equals `purchase_spend` (purchases only), kept for the web app until it reads the new fields. *(Today: one `total_value` = PO totals + sales totals + work costs, all stages. Requires new fields on `TopFactoryRow`.)* Example: in May factory "Dhaka" has an approved PO of 10,000.00, a draft PO of 2,000.00 and a completed sales order of 12,000.00 → `purchase_spend` 12,000.00 (committed 10,000.00, projected 2,000.00), `sales_revenue` 12,000.00 (committed 12,000.00), `work_cost` 0, `total_value` 12,000.00. *(Today: `total_value` 24,000.00.)*
- **R8.** No order in range resolves to a factory → `[]`.
- **R8a.** [BUG-2504] A sales or work order whose `factory_id`, or a PO / transfer whose storage / damaged id, is another workspace's factory credits no factory. *(Today: that factory is a row, with its id and name — verified `OtherWsFactory`.)*
- **R8b.** [BUG-2504] A factory view whose `factory_id` is another workspace's factory (or no factory at all) answers 200 with every list empty (top items, vendors, customers, categories, factories) and every money figure 0.00 / count 0; no id or name of the other workspace appears. `factory_id` is a filter that narrows the caller's own workspace data, not a lookup: it is never refused with 404, and no W1 order may count for another workspace's factory (HR-16). *(decided by Claude under the reviewer's delegation (2026-11-10)) (Today: any `factory_id` gives a 500, BUG-2502; past that crash, W1 orders linking the foreign factory (invalid data) would be counted and its name shown, R8a.)*
- **R9.** A row's `factory_name` is the factory's name; when no factory row has that id (a storage id pointing nowhere) or the name is empty, it is `"Factory #<id>"`.
- **R9a.** [BUG-2506] A factory with `is_deleted = True` is not a row (HR-4); an inactive-but-live factory is. *(Today: listed.)*
- **R10.** A factory with orders of only some kinds shows 0 for the other counters (e.g. `purchase_count = 0`, `transfer_count = 1`).
- **R11.** Rows are sorted by `order_count` descending, then by the money tie-break descending, and cut to `limit`. [BUG-2481] The money tie-break is `purchase_spend` (total). *(Today: `total_value` as in R7, i.e. purchase + sales + work money.)* The sort is done **in Python** on the accumulated map (gap G4).
- **R11a.** [BUG-2505] Equal `order_count` and equal money tie-break are ordered by factory name case-insensitive ascending, then `factory_id` ascending, before the cut — in the same Python sort. *(Today: the order the factories were first credited in, i.e. query row order of the PO, transfer, sales and work queries.)*

**Side effects:** none.

---

## `OrdersOverviewService.get_stats(db, workspace_id, from_date, to_date, factory_id=None, limit=5)`
**Shape:** compute (leaderboards) · **Persistence:** reads · **Visibility:** public (`GET /orders/overview/stats`)

**Purpose:** the five leaderboards of the orders overview for a period, optionally for one factory.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | the caller's workspace; not checked |
| `from_date`, `to_date` | date | inclusive range of report days; no order check (`from > to` → all lists empty, verified) |
| `factory_id` | int \| None | `None` → whole workspace; any int → factory view (not checked to exist or to be in the workspace) |
| `limit` | int | clamped to 1…10 (the endpoint already refuses others with 422) |

**Returns:** `OrdersOverviewStatsResponse`, always all five keys.

**Rules:**
- **R1.** `limit` below 1 acts as 1, above 10 as 10 (verified `0` → 1 row, `50` → all rows when ≤ 10); every list has at most that many rows.
- **R2.** Only orders whose own `workspace_id` is `workspace_id` are read; another workspace's orders never count. Report days and the inclusive range as `_in_date_range` R1, per kind (Overview facts). Neither commits nor rolls back; pending changes in the session stay pending; any exception reaches the caller unchanged (as TC6, `base_service.spec.md`).

*Top items*
- **R3.** Built from PO lines, transfer lines and sales lines of the period's orders; a sales line with no `item_id` (free-text line) is not counted.
- **R4.** Every PO line of a non-voided PO counts, whatever the PO's stage, adding `quantity_ordered` to `total_quantity` and `purchase_qty` and `line_subtotal` (`NULL` → 0) to `total_spend`.
- **R4b.** [BUG-2480] An item's purchase spend is split per D1 by its PO's stage (D4): `total_spend_committed`, `total_spend_projected`, `total_spend`. *(Today: `total_spend` only. Requires new fields on `TopItemRow`.)*
- **R4a.** [BUG-2500] Lines of a voided PO count nowhere. *(Today: counted, verified 50 units / 1000.00.)*
- **R5.** With `factory_id`, only PO lines of POs kept by `_filter_po_by_factory` count, and only sales lines of sales orders whose `factory_id` is that factory.
- **R6.** Every transfer line adds `quantity` to `total_quantity` and `transfer_qty`, nothing to spend; every sales line adds `quantity_ordered` to `total_quantity` and `sales_qty`, `line_total` to `total_spend`. Each line adds 1 to `line_count`.
- **R6a.** [BUG-2504] A line whose item belongs to another workspace is left out. *(Today: shown with that item's id, name and unit, verified.)*
- **R12.** With `factory_id`, only transfer lines of transfers kept by `_filter_transfer_by_factory` count (a transfer between two factories counts in both factory views).
- **R7.** `total_quantity` = purchase + transfer + sales quantity (volume; unchanged by BUG-2481).
- **R7a.** [BUG-2481] `total_spend` = purchase line subtotals only. Sales line totals go to a separate `sales_revenue` (split per D1 by the sales order's stage, D5: `sales_revenue_committed`, `sales_revenue_projected`); transfer lines add to no money figure. *(Today: `total_spend` = purchase subtotals + sales line totals. Requires a new field on `TopItemRow`.)* Example: a bolt bought 10 for 50.00 and sold 3 for 300.00 → `total_spend` 50.00, `sales_revenue` 300.00. *(Today: `total_spend` 350.00.)*
- **R8.** `item_name` is the item's name, `"Item #<id>"` if empty; `item_unit` is the item's unit.
- **R8c.** An item whose `unit` is `""` (or `None`) gets `item_unit = None`: an empty unit is shown as no unit. Intended (decided by Claude under the reviewer's delegation (2026-11-10)). Applies to purchase, transfer and sales lines alike.
- **R9.** Items are sorted descending and cut to `limit`, **in Python** (gap G4). [BUG-2481] Sort key: `purchase_qty`, then `total_spend` (purchases only, R7a); items with no purchase in the period (`purchase_qty` 0) still compete and come after any purchased item. *(Today: `total_quantity`, then `total_spend` of R7 today.)* Example: bolt bought 5, sold 100; nut bought 20 → nut first. *(Today: bolt first, 105 > 20.)*
- **R9a.** [BUG-2505] Ties ordered by item name case-insensitive ascending, then `item_id` ascending, before the cut, in the same Python sort. *(Today: first-seen order — PO lines, then transfer lines, then sales lines, each in query row order.)*

*Top vendors*
- **R10.** Built from POs and expense orders of the period that have an `account_id`; orders without one are left out. Each order adds its `total_amount` to its account's `total_spend` and 1 to `order_count`; an account used on both POs and expense orders gets one row with both summed.
- **R11.** Every non-voided order counts, whatever its stage.
- **R11b.** [BUG-2480] A vendor's `total_spend` is split per D1: PO totals by D4, expense totals by D6 → `total_spend_committed`, `total_spend_projected`; `order_count` is not split (D8). *(Today: `total_spend` only. Requires new fields on `TopAccountRow`.)*
- **R11a.** [BUG-2500] Voided POs and voided expense orders count nowhere. *(Today: counted — verified 1000.00 + 300.00 in the vendor's spend.)*
- **R13.** `account_name` is the account's name, `"Account #<id>"` if empty. A soft-deleted account keeps its row and name.
- **R13a.** [BUG-2504] An order whose account belongs to another workspace is left out. *(Today: that account's id and name shown, verified.)*
- **R14.** Sorted by `total_spend` (the total, D1) descending, cut to `limit` — **in Python**, after merging PO and expense vendors (gap G4).
- **R14a.** [BUG-2505] Ties by account name case-insensitive ascending, then `account_id` ascending, in the same Python sort. *(Today: first-seen order: PO vendors, then expense-only vendors, each in query row order.)*
- **R15.** With `factory_id`, only POs kept by `_filter_po_by_factory` count and expense orders are not read at all.

*Top customers*
- **R16.** Built from the period's sales orders, grouped by account: `total_spend` = sum of `total_amount`, `order_count` = number of orders; name as R13. Every stage counts. [BUG-2504] An order whose account is another workspace's is left out. *(Today: shown.)*
- **R16a.** [BUG-2480] A customer's `total_spend` (sales revenue; the field name is today's) is split per D1 by each sales order's stage (D5) → `total_spend_committed`, `total_spend_projected`. *(Today: `total_spend` only.)*
- **R17.** Sorted by summed total descending, cut to `limit` — **in SQL** (`ORDER BY sum(total_amount) DESC LIMIT`, gap G4).
- **R17a.** [BUG-2505] Ties by account name case-insensitive ascending, then `account_id` ascending, as further `ORDER BY` terms before the `LIMIT` (the cut is in SQL, so the tie-break must be too). *(Today: no further term; tied rows come in the database's row order.)*
- **R18.** [BUG-2502] With `factory_id`, only sales orders of that factory count, filtered before the cut. *(Today: any `factory_id` raises `sqlalchemy.exc.InvalidRequestError` "Query.filter() being called on a Query which already has LIMIT or OFFSET applied…" and nothing is returned — verified, also for a factory with no orders.)*

*Top expense categories*
- **R19.** Without `factory_id`: the period's expense orders grouped by `expense_category`, `total_spend` = sum of `total_amount`, `order_count` = count, sorted by summed total descending, cut to `limit` — **in SQL** (`ORDER BY … LIMIT`, gap G4). Every stage counts; voided left out per R11a / BUG-2500.
- **R19a.** [BUG-2505] Ties by category text ascending, as a further `ORDER BY` term before the `LIMIT`. *(Today: database row order.)*
- **R19b.** [BUG-2480] A category's `total_spend` is split per D1 by each expense order's stage (D6) → `total_spend_committed`, `total_spend_projected`. *(Today: `total_spend` only. Requires new fields on `TopExpenseCategoryRow`.)*
- **R20.** With `factory_id`: `[]` (an expense allocated to that factory is not looked at).

*Top factories*
- **R21.** Without `factory_id`: as `_build_top_factories` with the clamped `limit`. With `factory_id`: `[]`.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| any `factory_id` (today; BUG-2502) | `sqlalchemy.exc.InvalidRequestError` | "Query.filter() being called on a Query which already has LIMIT or OFFSET applied.  Call filter() before limit() or offset() are applied." |

**Side effects:** none.

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 34–36 | `value is None` | `_dec` R1, R2 |
| 41 | `coalesce(order_date, created_at::date)` | `_po_report_date` R1 |
| 44 | `>= from and <= to` | `_in_date_range` R1 |
| 50–63 | machine / project outer joins (by id only) | `_filter_po_by_factory` R2, R2a, R3 |
| 65–72 | storage/damaged id, machine factory, project factory | `_filter_po_by_factory` R1–R4 |
| 81–101 | three outer joins | `_filter_transfer_by_factory` R1, R2 |
| 103–115 | five alternatives | `_filter_transfer_by_factory` R1–R3 |
| 127–132 | `case` per location type, `else NULL` | `_factory_from_location` R1–R4 |
| 141–142 | `factory_id is None` | `_accumulate_factory` R1 |
| 146–153 | kind `purchase` / `transfer` / `sales` / `work` / other | `_accumulate_factory` R3 |
| 182–205 | PO query, workspace + date, no voided filter | `_build_top_factories` R1, R2, R2a |
| 222 | `coalesce(dest_factory, src_factory)` | `_build_top_factories` R3 |
| 223–253 | transfer query, amount 0 | `_build_top_factories` R3 |
| 255–264 | sales query | `_build_top_factories` R4 |
| 266–275 | work query, no void / deleted filter | `_build_top_factories` R5, R5a |
| 277–278 | `not factory_map` | `_build_top_factories` R8 |
| 281–284 | names by id, no workspace / deleted filter | `_build_top_factories` R8a, R9, R9a |
| 286–290 | sort `(order_count, total_value)` desc, cut | `_build_top_factories` R11, R11a |
| 295 | `names.get(fid) or 'Factory #id'` | `_build_top_factories` R9 |
| 315 | clamp `limit` | `get_stats` R1 |
| 329–343 | PO lines query | `get_stats` R3, R4, R4a, R6a |
| 344–345 | `factory_id is not None` (PO lines) | `get_stats` R5 |
| 346–356 | loop over PO lines; `name or`, `unit or` | `get_stats` R4, R8 |
| 358–371 | transfer lines query | `get_stats` R6 |
| 372–373 | `factory_id is not None` (transfers) | `get_stats` R12 |
| 374–382 | loop over transfer lines | `get_stats` R6 |
| 384–398 | sales lines query, inner join item | `get_stats` R3, R6 |
| 399–400 | `factory_id is not None` (sales lines) | `get_stats` R5 (sales by `SalesOrder.factory_id`), R18 |
| 401–411 | loop over sales lines | `get_stats` R6, R7 |
| 413–417 | sort items, cut | `get_stats` R9, R9a |
| 421 | `item_name or 'Item #id'` | `get_stats` R8 |
| 435–449 | PO vendor query, `account_id IS NOT NULL` | `get_stats` R10, R11, R11a, R13a |
| 450–451 | `factory_id is not None` (PO vendors) | `get_stats` R15 |
| 452–455 | merge PO vendors; `name or`, `count or 0` | `get_stats` R10, R13 |
| 457–476 | `factory_id is None` → expense vendors | `get_stats` R10, R15 |
| 478 | sort vendors by spend, cut | `get_stats` R14, R14a |
| 482 | `name or 'Account #id'` | `get_stats` R13 |
| 489–504 | customers query, `ORDER BY sum DESC LIMIT` | `get_stats` R16, R17, R17a |
| 505–506 | `factory_id is not None` → filter after limit (raises) | `get_stats` R18 |
| 510–512 | `row[1] or`, `row[3] or 0` | `get_stats` R13, R16 |
| 518–540 | `factory_id is None` → categories | `get_stats` R19, R19a, R20 |
| 543–546 | `factory_id is None` → top factories | `get_stats` R21 |

## Gap log
Round 2026-11-10 (2), from `orders_overview_service.cases.md` `## Spec gaps`:
- G1 (cases gap G1) — Fact — Overview facts: line FKs `purchase_order_id` / `transfer_order_id` / `sales_order_id`; all three line tables have their own `workspace_id`, which the service never reads (lines are scoped through the order).
- G2 (cases gap G2) — Fact — `_accumulate_factory` Inputs: the `factory_map` entry is a plain dict with six keys (`order_count`, `total_value` `Decimal(0)`, four per-kind counts), created by a `defaultdict`; a plain `dict` raises `KeyError`; returns `None`.
- G3 (cases gap G3) — Intent, decided by the owner (OQ-29) and, for the per-kind definition, by Claude under the reviewer's delegation (2026-11-10) — Overview *Money stage* D1–D8: committed = approvals met (D3, with the BUG-755 family's "at least 1") or past approval (PO stage `Receiving` / `Complete`; sales `order_completed`; expense `completed_at`; work `IN_PROGRESS` / `COMPLETED` or an approved draft); expense orders have no status column and are marked by their approver rows and `completed_at` (D6), never by `approved_at`. New rules R4b, R7a, R11b, R16a, R19b, `_build_top_factories` R7a (BUG-2480, BUG-2481).
- G4 (cases gap G4) — Fact — where each ranking happens today: items, vendors and factories are sorted **in Python** (the BUG-2505 tie-break goes into the Python sort key); customers and expense categories are cut **in SQL** (the tie-break goes into further `ORDER BY` terms before `LIMIT`). Written into R9/R9a, R11/R11a, R14/R14a, R17/R17a, R19/R19a. No database uniqueness on item, account or factory names (Overview facts), so name ties can be built directly.
- G5 (cases gap G5) — Fact — Overview facts: account soft delete writes `is_deleted`, `is_active = False`, `deleted_at`, `deleted_by`; factory soft delete writes `is_deleted`, `deleted_at`, `deleted_by` (not `is_active`).
- G6 (cases gap G6) — Fact — `sales_orders.order_date` is NOT NULL (default `date.today`); the `NULL` case of `_in_date_range` R1 needs a nullable column such as `PurchaseOrder.order_date`. OOV-IR-01's sales row must change (the case designer re-runs).
- G7 (cases gap G7) — Fact — `_factory_from_location` is a `@staticmethod`; the other helpers are instance methods; `_dec` is a module function.
- G8 (cases gap 1, round 3) — Intent, decided by Claude under the reviewer's delegation (2026-11-10), consistent with HR-16 and `factory_id` as a filter — new rule `_build_top_factories` R8b [BUG-2504]: another workspace's `factory_id` → 200, all lists empty, nothing leaks, never 404.
- G9 (verifier gap, round 4; source lines 319, 350, 378, 405) — Intent, decided by Claude under the reviewer's delegation (2026-11-10) — `get_stats` R8c: empty `unit` → `item_unit = None` (today's behaviour, intended).
