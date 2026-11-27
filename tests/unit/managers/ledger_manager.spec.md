# Spec — `app/managers/ledger_manager.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically

- **HR-6** `get_machine_ledger` R8 — ordered by `performed_at` only; entries with the same timestamp come back in no fixed order and paging can repeat/skip them. Intended: `performed_at` newest first, then `id` descending. — 🐞 BUG-640
**Answer:** bug — per HR-6 (house rule)
**Resolution:** list ordered `performed_at` newest first, then `id` descending, so ties no longer reorder across pages. Rules: `get_machine_ledger` R8.
- **HR-6** `get_project_component_ledger` R4 — same as above. Intended: `performed_at` newest first, then `id` descending. — 🐞 BUG-640
**Answer:** bug — per HR-6 (house rule)
**Resolution:** same fix, same bug. Rules: `get_project_component_ledger` R4.
- **HR-6** `get_inventory_ledger` R8 — same as above. Intended: `performed_at` newest first, then `id` descending. — 🐞 BUG-640
**Answer:** bug — per HR-6 (house rule)
**Resolution:** same fix, same bug. Rules: `get_inventory_ledger` R8.
- **HR-6** `get_attachment_ledger` R5 — same as above. Intended: `performed_at` newest first, then `id` descending. — 🐞 BUG-640
**Answer:** bug — per HR-6 (house rule)
**Resolution:** same fix, same bug. Rules: `get_attachment_ledger` R5.
- **HR-6** `get_item_movement_summary` R4 — same as above for the `machine` and `inventory` lists. Intended: `performed_at` newest first, then `id` descending. — 🐞 BUG-640
**Answer:** bug — per HR-6 (house rule)
**Resolution:** same fix, same bug (the ordering part of R4 only — the 100-entry cap in the same rule is a separate bug, see Q4 / BUG-648). Rules: `get_item_movement_summary` R4.
- **HR-6** `get_transactions_by_user` R3 — intended lists ordered `performed_at` newest first, then `id` descending. — 🐞 BUG-640
**Answer:** bug — per HR-6 (house rule)
**Resolution:** same fix, same bug. Rules: `get_transactions_by_user` R3.
- **HR-6** `get_machine_balance` R3 — the "latest entry" (top-1) is picked by `performed_at` only; with two entries at the same timestamp an arbitrary one decides the balance. Intended: latest = highest `performed_at`, ties broken by highest `id`. — 🐞 BUG-641
**Answer:** bug — per HR-6 (house rule)
**Resolution:** latest-entry lookups (a different code shape from list ordering — single-row "top-1" selection, not a paged list) now break ties by highest `id`. Rules: `get_machine_balance` R3.
- **HR-6** `get_inventory_balance` R3 — same top-1 tie problem; inventory ledger rows get `performed_at` from the database clock at **transaction start**, so every row written in one transaction ties. Intended: latest = highest `performed_at`, then highest `id`. — 🐞 BUG-641
**Answer:** bug — per HR-6 (house rule)
**Resolution:** same fix, same bug as `get_machine_balance` R3 (same tie-break shape). Rules: `get_inventory_balance` R3.
- **HR-6** `reconcile_machine_item` R2, R7 — ledger quantity and average price come from the same tie-prone "latest entry". Intended: latest = highest `performed_at`, then highest `id`. — 🐞 BUG-641
**Answer:** bug — per HR-6 (house rule)
**Resolution:** `reconcile_machine_item` R1 already points to `get_machine_balance` R1–R3 for ledger quantity, and R7's "latest ledger entry" is the same lookup; fixed by the BUG-641 fix in `get_machine_balance` — no separate rule text to tag here.
- **HR-6** `reconcile_inventory` R2, R7 — same. Intended: latest = highest `performed_at`, then highest `id`. — 🐞 BUG-641
**Answer:** bug — per HR-6 (house rule)
**Resolution:** same as above via `get_inventory_balance` R3 — no separate rule text to tag here.
- **HR-7** `get_machine_ledger` R9 — `limit` ≤ 0 accepted (`0` → empty list, negative → database error / 500). Intended: `limit >= 1`, 422 otherwise (fix in `GET /ledgers/machine/`). — 🐞 BUG-642
**Answer:** bug — per HR-7 (house rule)
**Resolution:** `limit >= 1` enforced by the API (422 otherwise); the manager rule states the intended contract. Rules: `get_machine_ledger` R9.
- **HR-7** `get_project_component_ledger` R5 — same (fix in `GET /ledgers/project-component/`). — 🐞 BUG-642
**Answer:** bug — per HR-7 (house rule)
**Resolution:** same fix, same bug. Rules: `get_project_component_ledger` R5.
- **HR-7** `get_inventory_ledger` R9 — same (fix in `GET /ledgers/inventory/`). — 🐞 BUG-642
**Answer:** bug — per HR-7 (house rule)
**Resolution:** same fix, same bug. Rules: `get_inventory_ledger` R9.
- **HR-7** `get_attachment_ledger` R6 — same (fix in `GET /ledgers/attachments/`). — 🐞 BUG-642
**Answer:** bug — per HR-7 (house rule)
**Resolution:** same fix, same bug. Rules: `get_attachment_ledger` R6.
- **HR-7** `get_transactions_by_user` R4 — same (fix in `GET /ledgers/reports/user-transactions/{user_id}/`). — 🐞 BUG-642
**Answer:** bug — per HR-7 (house rule)
**Resolution:** same fix, same bug. Rules: `get_transactions_by_user` R4.
- **HR-10** `reconcile_machine_item` R11 — snapshot read without a row lock; two concurrent reconciles both write an adjustment row and an activity event. Intended: snapshot read `FOR UPDATE OF machine_items`; the second reconcile sees the corrected snapshot and returns `balanced`. — 🐞 BUG-643
**Answer:** bug — per HR-10 (house rule)
**Resolution:** `machine_items` snapshot row read with `FOR UPDATE OF machine_items`; a losing concurrent reconcile sees the corrected snapshot and returns `balanced` without writing. Rules: `reconcile_machine_item` R11.
- **HR-10** `reconcile_inventory` R11 — same; duplicate adjustment rows. Intended: snapshot read `FOR UPDATE OF inventory`; the second reconcile returns `balanced`. — 🐞 BUG-644
**Answer:** bug — per HR-10 (house rule)
**Resolution:** `inventory` snapshot row read with `FOR UPDATE OF inventory` (separate code path/table from the machine-item snapshot, so its own bug). Rules: `reconcile_inventory` R11.

### Precedent matches — confirm all with ok

### P1. Item movement report ignores the item — 🐞 BUG-341 (existing)
**Background:** The "item movement" report (`GET /ledgers/reports/item-movement/{item_id}/`) is meant to show one item's journey across the machine, project and inventory ledgers.
**What happens today:** The `item_id` is accepted but never used as a filter: with a date range, the report returns every machine-ledger and inventory-ledger entry of the workspace in that range, for all items.
**Example:** Workspace has entries for "Bolt" (id 7) and "Nut" (id 8) this week. `GET …/item-movement/7/?start_date=…&end_date=…` returns Nut's entries too.
**Rules affected:** `get_item_movement_summary` R2, R3
**Answer:** bug — per BUG-341 precedent: the report's lists contain only entries whose `item_id` equals the requested item (precedent — confirmed: ok)
**Resolution:** referenced against the existing BUG-341 (same root cause: a scope filter accepted but not applied) — no new bug ID. `machine`/`inventory` lists filter by `item_id`. Rules: `get_item_movement_summary` R2, R3.

### P2. User transaction report ignores the date range — 🐞 BUG-341 (existing)
**Background:** `GET /ledgers/reports/user-transactions/{user_id}/` accepts `start_date` / `end_date`.
**What happens today:** The dates are accepted but never applied (and see Q1: the method currently crashes before returning anything).
**Example:** Auditor asks for user 12's transactions for March; once Q1 is fixed they would get entries from every month.
**Rules affected:** `get_transactions_by_user` R2
**Answer:** bug — per BUG-341 precedent: when given, `start_date` (inclusive) and `end_date` (inclusive) restrict every ledger list by `performed_at`, applied before paging (precedent — confirmed: ok)
**Resolution:** referenced against BUG-341 — no new bug ID. `start_date`/`end_date`, when given, restrict every list by `performed_at` (inclusive), applied before paging. Rules: `get_transactions_by_user` R2.

### P3. Transaction-type filter silently dropped when a date range is given — 🐞 BUG-341 (existing)
**Background:** Machine and inventory ledger lists accept `start_date`, `end_date` and `transaction_type`; the code picks one query path: date range first, else transaction type.
**What happens today:** When both a full date range and `transaction_type` are sent, the transaction type is ignored.
**Example:** `GET /ledgers/machine/?machine_id=3&start_date=2026-09-01&end_date=2026-09-30&transaction_type=consumption` returns all September entries of machine 3, including `transfer_in` and `purchase_order` rows.
**Rules affected:** `get_machine_ledger` R2, `get_inventory_ledger` R2
**Answer:** bug — per BUG-341 precedent: all given filters combine (date range AND transaction type AND item/scope filters) (precedent — confirmed: ok)
**Resolution:** referenced against BUG-341 — no new bug ID. All given filters combine (AND) instead of the code choosing one path. Rules: `get_machine_ledger` R2, `get_inventory_ledger` R2.

### P4. A single date bound is silently ignored — 🐞 BUG-341 (existing)
**Background:** Same lists as P3. The attachment ledger list (`get_attachment_ledger`) already applies `start_date` and `end_date` independently.
**What happens today:** The date filter is used only when **both** `start_date` and `end_date` are given; only one of them → no date filtering at all.
**Example:** `GET /ledgers/inventory/?start_date=2026-09-01` returns entries from every date, including 2025.
**Rules affected:** `get_machine_ledger` R3, `get_inventory_ledger` R3
**Answer:** bug — per BUG-341 precedent: each given bound applies on its own (`performed_at >= start_date`, `performed_at <= end_date`), as the attachment ledger does (precedent — confirmed: ok)
**Resolution:** referenced against BUG-341 — no new bug ID. Each given bound applies on its own, as `get_attachment_ledger` already does. Rules: `get_machine_ledger` R3, `get_inventory_ledger` R3.

### New questions

### Q1. User transaction report always crashes — 🐞 BUG-645
**Background:** The report is meant to list, per ledger (machine, project, inventory), what one user did. It asks each ledger's data-access object for "entries performed by user X", but only the inventory ledger has that lookup; the machine and project ledgers do not.
**What happens today:** Every call raises `AttributeError` (`'MachineItemLedgerDAO' object has no attribute 'get_by_performer'`) before any query runs; the endpoint answers 500.
**Example:** A manager opens `GET /ledgers/reports/user-transactions/12/` to audit user 12 and gets a 500 "Internal Server Error", whatever the data.
**Rules affected:** `get_transactions_by_user` R1
**Suggested answer:** bug — returns `{"machine": [...], "project": [...], "inventory": [...]}`, each the user's entries in the workspace, paged by `skip`/`limit` (add `get_by_performer` to the machine and project ledger DAOs)
**Answer:** bug — return {machine, project, inventory} lists of the user's entries in the workspace, paged by skip/limit (add get_by_performer to the machine and project ledger DAOs) (reviewer accepted suggestion)
**Resolution:** each ledger DAO gets a `get_by_performer` lookup (workspace + `performed_by`, newest-first order, `skip`/`limit`); the report returns `{"machine": [...], "project": [...], "inventory": [...]}` instead of crashing. Rules: `get_transactions_by_user` R1.

### Q2. Item movement report is empty unless both dates are given — 🐞 BUG-646
**Background:** `start_date` and `end_date` are optional on `GET /ledgers/reports/item-movement/{item_id}/`.
**What happens today:** Without **both** dates the report returns `{"machine": [], "project": [], "inventory": []}` — no query is made.
**Example:** A user opens the movement report for "Bolt" without picking dates and sees "no movements", although Bolt has 40 ledger entries.
**Rules affected:** `get_item_movement_summary` R1
**Suggested answer:** bug — missing bounds mean "unbounded"; the report returns the item's entries (each given bound applied on its own)
**Answer:** bug — a missing bound means unbounded; the report returns the item's entries, and each given bound applies on its own (reviewer accepted suggestion)
**Resolution:** a missing `start_date`/`end_date` means unbounded on that side (each given bound applied on its own, as P4); the report always runs, never short-circuits to empty lists just because a date is missing. Rules: `get_item_movement_summary` R1.

### Q3. Item movement report never shows project consumption — 🐞 BUG-647
**Background:** Project components consume items; those movements live in the project component item ledger.
**What happens today:** The `project` list is always `[]`, with or without dates.
**Example:** 25 bolts were consumed by project component "Frame A" last week; the Bolt movement report for last week shows an empty `project` list.
**Rules affected:** `get_item_movement_summary` R5
**Suggested answer:** bug — `project` lists the item's project-component ledger entries with the same date filters as the other lists
**Answer:** bug — the project list shows the item's project-component ledger entries, with the same date filters as the other lists (reviewer accepted suggestion)
**Resolution:** `project` lists the item's project-component ledger entries (item id + workspace, same date bounds as `machine`/`inventory`), instead of always `[]`. Rules: `get_item_movement_summary` R5.

### Q4. Item movement report silently stops at 100 entries per ledger — 🐞 BUG-648
**Background:** The report has no `skip`/`limit` parameters.
**What happens today:** Each list holds at most the 100 newest entries in the range; older entries are cut off with no indication and no way to page.
**Example:** A year-long report for a busy item with 350 machine movements shows only the last 100; the user has no way to see the other 250.
**Rules affected:** `get_item_movement_summary` R4
**Suggested answer:** bug — the report accepts `skip` / `limit` (limit 1–100, default 100) applied to each list, so every entry in range is reachable
**Answer:** bug — the report accepts skip/limit (limit 1-100, default 100), applied to each list (reviewer accepted suggestion)
**Resolution:** the report gains `skip`/`limit` parameters (default 0/100, `limit >= 1`, same shape as the other list methods), applied per list; every entry in range becomes reachable by paging instead of a silent 100-row cap. Rules: `get_item_movement_summary` R4a (new).

### Q5. Reconcile reports an error when there is nothing to reconcile — 🐞 BUG-649
**Background:** Reconcile compares the stock "snapshot" row (current quantity per machine+item, or per factory+item+inventory type) with the ledger (history of movements). A bucket with no ledger entries has ledger quantity 0.
**What happens today:** If no snapshot row exists, the result is `status: "error"` with message "Snapshot missing for item with ledger transactions" — even when the ledger has no entries (quantity 0) or the machine/item does not exist at all.
**Example:** A user reconciles machine 3 / item 9, which were never linked. They see the warning "Reconciliation issue: Snapshot missing for item with ledger transactions" although there are no transactions.
**Rules affected:** `reconcile_machine_item` R4, `reconcile_inventory` R4
**Suggested answer:** bug — no snapshot and ledger quantity 0 → `status: "balanced"` (ledger_qty 0, snapshot_qty 0, discrepancy 0, no adjustment); the error stays for a missing snapshot with non-zero ledger quantity
**Answer:** bug — no snapshot and ledger quantity 0 returns 'balanced' with no adjustment; the error stays only when the ledger quantity is not zero (reviewer accepted suggestion)
**Resolution:** no snapshot row and ledger quantity 0 → `{"status": "balanced", "ledger_qty": 0, "snapshot_qty": 0, "discrepancy": 0, "adjustment_created": False}`, nothing written; the `"error"` result is now reached only when no snapshot exists **and** the ledger quantity is non-zero. Rules: `reconcile_machine_item` R4, `reconcile_inventory` R4.

### Q6. Reconcile does not create a missing snapshot when the ledger holds stock — ✅ intended
**Background:** Same as Q5. The method's docstring says "Ledger is source of truth … update snapshot to match ledger".
**What happens today:** When the snapshot row is missing but the ledger shows stock, the result is `status: "error"`; no snapshot row and no adjustment are created.
**Example:** The ledger says machine 3 holds 12 × item 9, but the machine-item row was removed. Reconcile answers "Snapshot missing…" and the machine's item list still does not show the 12 units.
**Rules affected:** `reconcile_machine_item` R5, `reconcile_inventory` R5
**Suggested answer:** intended
**Answer:** intended (reviewer accepted suggestion)

### Q7. Reconcile crashes when the latest ledger entry has no average price — 🐞 BUG-650
**Background:** Ledger rows have an optional "average price after" column (may be empty). Reconcile prices the adjustment at the latest entry's average price, or 0.00 when there is no entry at all.
**What happens today:** If a latest entry exists but its average price is empty, reconcile fails with a `TypeError` (500) and nothing is corrected.
**Example:** The last ledger row for machine 3 / item 9 was written without `avg_price_after`; snapshot says 10, ledger says 12. Reconcile answers 500 instead of fixing the snapshot.
**Rules affected:** `reconcile_machine_item` R8, `reconcile_inventory` R8
**Suggested answer:** bug — an empty average price is treated as 0.00 (same as no entry), and the reconcile completes
**Answer:** bug — treat an empty average price as 0.00, as when there is no entry, and complete the reconcile (reviewer accepted suggestion)
**Resolution:** an empty `avg_price_after` on the latest entry is treated as `Decimal("0.00")`, same as no entry at all; reconcile completes instead of raising `TypeError`. Rules: `reconcile_machine_item` R8, `reconcile_inventory` R8.

### Q8. The reconciliation ledger row breaks the ledger's running balance — 🐞 BUG-651
**Background:** Every ledger row records `qty_before` → `qty_after`, so the rows form a continuous chain (each row's `qty_before` = the previous row's `qty_after`). Reconcile only corrects the snapshot; the ledger itself already holds the true quantity.
**What happens today:** The adjustment row is written with `qty_before` = the **snapshot's** old quantity and `quantity` = the difference, while the previous ledger row already ended at the ledger quantity. The chain now shows a movement that never happened in the ledger.
**Example:** Ledger last row ends at 15; snapshot said 10. Reconcile adds `inventory_adjustment` quantity 5, 10 → 15. Anyone summing movements (or reading the history) sees 5 extra units appear, and the chain jumps 15 → 10 → 15.
**Rules affected:** `reconcile_machine_item` R9, `reconcile_inventory` R9
**Suggested answer:** bug — the adjustment row keeps the chain continuous: `quantity` 0, `qty_before` = `qty_after` = ledger quantity (values/prices likewise unchanged); the snapshot's old quantity and the discrepancy are recorded in `notes` only
**Answer:** bug — the adjustment row has quantity 0 and qty_before = qty_after = the ledger quantity (values and prices unchanged); the snapshot's old quantity and the discrepancy go in notes only (reviewer accepted suggestion)
**Resolution:** the adjustment row keeps the ledger chain continuous: `quantity = 0`, `qty_before = qty_after` = the ledger quantity (values/prices unchanged accordingly); the snapshot's old quantity and the discrepancy move into `notes` only (inventory notes also record the old/new average price — exact format best-practice default, delegated by reviewer). Rules: `reconcile_machine_item` R9a, `reconcile_inventory` R9a, R9b (R9 of each holds the fields already correct today).

### Q9. Inventory reconcile does not record who changed the stock row — 🐞 BUG-652
**Background:** Inventory snapshot rows have `updated_by` ("last changed by"). HR-9 says it is written only when something changes — here the quantity does change.
**What happens today:** Reconcile changes `qty` (and `avg_price`) but leaves `updated_by` as it was (the database refreshes `updated_at`).
**Example:** Alice created the stock row; Bob's reconcile changes it from 10 to 15. The row still says "last changed by Alice".
**Rules affected:** `reconcile_inventory` R10
**Suggested answer:** bug — `updated_by` = the reconciling user whenever reconcile changes the snapshot
**Answer:** bug — set updated_by to the reconciling user whenever reconcile changes the snapshot (reviewer accepted suggestion)
**Resolution:** `updated_by` is set to the reconciling `user_id` whenever reconcile changes the snapshot (HR-9: the stamp now tracks the change that actually happened). Rules: `reconcile_inventory` R10.

### Q10. Inventory reconcile ignores a wrong average price when quantities match — 🐞 BUG-653
**Background:** The inventory stock row stores both quantity and average price; reconcile compares only quantity. On a quantity mismatch it overwrites the average price with the ledger's.
**What happens today:** Quantity equal but average price different → `status: "balanced"`, price left wrong.
**Example:** Stock row: 10 units at 5.00; ledger: 10 units at 6.50. Reconcile says "Inventory is balanced at 10 units"; stock valuation stays 50.00 instead of 65.00.
**Rules affected:** `reconcile_inventory` R6
**Suggested answer:** bug — an average-price difference is also corrected (snapshot `avg_price` set to the ledger's latest average price) and reported as `adjusted`
**Answer:** bug — also correct avg_price to the ledger's latest average price and report the result as 'adjusted' (reviewer accepted suggestion)
**Resolution:** equal quantities but a different `avg_price` no longer count as `balanced`: the snapshot's `avg_price` is set to the ledger's latest `avg_price_after` and the result is `adjusted`. Rules: `reconcile_inventory` R6.

### Q11. Project component total cost adds outgoing movements instead of subtracting them — 🐞 BUG-654
**Background:** Project ledger rows always store a positive `quantity` and `total_cost`; the direction is given by `transaction_type` (`transfer_out`, `damaged` … are outgoing). Note: no code in the app currently writes project ledger rows, so this is latent.
**What happens today:** The total is the plain sum of `total_cost` over all rows of the component, whatever the type.
**Example:** Component receives items worth 1,000.00 (`transfer_in`) and returns 300.00 to storage (`transfer_out`). Total cost shows 1,300.00 instead of 700.00.
**Rules affected:** `calculate_project_component_total_cost` R1
**Suggested answer:** bug — outgoing types (`transfer_out`, returns) are subtracted; the total is the net cost consumed by the component
**Answer:** bug — subtract outgoing types (transfer_out, returns) so the total is the net cost consumed (reviewer accepted suggestion)
**Resolution:** `total_cost` of outgoing transaction types (`transfer_out` and returns) is subtracted instead of added; the result is the net cost consumed by the component. Rules: `calculate_project_component_total_cost` R1.

### Q12. Inventory balance and inventory reconcile crash whenever the bucket has history — 🐞 BUG-655
**Background:** Machine ledger rows store a running "value after"; inventory ledger rows do not have that column (only quantity and average price). The inventory balance lookup was copied from the machine one and still reads "value after".
**What happens today:** For any (factory, item, inventory type) bucket with at least one ledger entry, `GET /ledgers/inventory/balance/` and `POST /ledgers/inventory/reconcile/` fail with `AttributeError` (500). Only empty buckets work (balance 0, 0.00).
**Example:** Factory 1 has received 50 × "Bolt" into STORAGE. The balance endpoint answers 500 instead of "50 units, 250.00"; reconcile answers 500 and the snapshot is never corrected.
**Rules affected:** `get_inventory_balance` R2, `reconcile_inventory` R1
**Suggested answer:** bug — balance = latest entry's `(qty_after, qty_after × avg_price_after)` (`avg_price_after` empty → value 0.00); fix in `InventoryLedgerDAO.calculate_balance`
**Answer:** bug — balance = (qty_after, qty_after × avg_price_after), with an empty avg price giving value 0.00; fix in InventoryLedgerDAO.calculate_balance (reviewer accepted suggestion)
**Resolution:** `InventoryLedgerDAO.calculate_balance` reads the columns the inventory ledger actually has: balance = `(qty_after, qty_after × avg_price_after)`, empty `avg_price_after` → value `Decimal("0.00")`; both `get_inventory_balance` and `reconcile_inventory` (which calls it for R1) work for buckets with history instead of raising `AttributeError`. Rules: `get_inventory_balance` R2, `reconcile_inventory` R1.

## Overview
Read and reconciliation layer over the stock ledgers (immutable movement
histories): machine item ledger, project component item ledger, unified
inventory ledger (STORAGE / DAMAGED / WASTE / SCRAP) and attachment ledger. It
lists entries with filters, reads current balances from the latest ledger row,
reconciles stock snapshots (`machine_items`, `inventory`) to the ledger by
writing an `inventory_adjustment` ledger row, and serves two cross-ledger
reports. Called only by `LedgerService` (`app/services/ledger_service.py`),
which commits; this module flushes but never commits. Invariants: every read
and write is scoped to one workspace; the ledger is the source of truth for
quantities.

**Callables:** 11 specified · 1 not specified
**Externals to mock:** none (`performed_at` of machine/project ledger rows defaults to `app.utils.time.utcnow`; inventory ledger `performed_at` is the database `now()`)
**Integration-only behavior:** none

**Notes for the test designer:**
- "Latest entry" / balance = the row with the greatest `performed_at` for the bucket. Inventory ledger rows inserted in the same transaction without an explicit `performed_at` all get the same timestamp (Postgres `now()` = transaction start) — set `performed_at` explicitly when a test needs a definite latest row.
- `limit`/`skip` are passed straight through; API endpoints cap `limit` at 100 (`le=100`) and require `skip >= 0`, but have no lower bound on `limit` (until BUG-642 is fixed — intended rules require `limit >= 1`).
- Project-component access checks (`require_component_access`) live in the service, not here.
- Several rules describe intended behavior that needs code the module does not have yet: `get_item_movement_summary` gains `skip`/`limit` parameters (BUG-648) and applies `item_id`/date filters (BUG-341, requires no new parameter, just using the existing ones); `get_transactions_by_user` needs a `get_by_performer` DAO method on the machine and project ledger DAOs (BUG-645, matching the existing one on `InventoryLedgerDAO`). Tests for these rules are written to the intended behavior and are expected to fail (`xfail(strict=True)`) until the code changes exist.
- `reconcile_inventory`'s "correction" (R3/R6/R6a) generalizes "discrepancy": a quantity mismatch, an avg_price-only mismatch (BUG-653), or both trigger R9/R10; `reconcile_machine_item` has no avg_price-only case (the `machine_items` snapshot does not store `avg_price`).
- **Column types / valid values (gap 5):** every ledger's `transaction_type` is a plain `VARCHAR` (no DB enum, no check constraint) — machine/project/inventory `String(50)`, attachment `String(16)` — so any string can be stored and an unknown or case-mismatched filter value simply returns `[]` (never raises). Values the app writes: inventory/machine ledgers `purchase_order`, `purchase_return`, `manual_add`, `inventory_adjustment`, `transfer_in`, `transfer_out`, `consumption`, `consumption_reversal`, `damaged`, `production`, `sale`, `return`, `work_order_install`, `work_order_replace_out`; attachment ledger `pending`, `ready`, `failed`, `deleted` (lowercase, `AttachmentLedgerTransactionTypeEnum`). Attachment `entity_type` is a nullable plain `String(64)`; the app writes the lowercase values of `AttachmentEntityTypeEnum` (`purchase_order`, `sales_order`, `expense_order`, `transfer_order`, `work_order`, `project`, `project_component`, `item`, `machine`, `account_invoice`, `support_ticket`, `scratch`). Only `inventory_ledger.inventory_type` is a Postgres enum (`InventoryTypeEnum`: `STORAGE`/`DAMAGED`/`WASTE`/`SCRAP`); pass the Python enum member. Attachment ledger rows need an `attachments` row (FK `attachment_id`, `ON DELETE RESTRICT`) and non-null `file_name`, `mime_type`, `file_size`.
- **Tie ordering today (gap 7, corrected by verify finding 2):** today the list queries emit `ORDER BY <ledger>.performed_at DESC` with **no** second sort key, and the "latest entry" lookups (`calculate_balance` and `get_latest_entry` on the machine and inventory ledger DAOs) emit `ORDER BY <ledger>.performed_at DESC LIMIT 1`. Postgres gives **no** order guarantee among rows with equal `performed_at`: the order of tied rows today is **undefined** — it may happen to match descending id in some runs and not in others (observed: 2–3 tied rows usually ascending, but under concurrent load the order varies run to run). The data order of tied rows is therefore **not** a reliable failure signal and must not back a `strict=True` xfail. **Prove BUG-640/BUG-641 deterministically from the emitted SQL (best-practice default, delegated by reviewer):** record the statements executed during the call (the same engine-level statement recorder used for the `FOR UPDATE` checks, `reconcile_machine_item` R11 / `reconcile_inventory` R11) and assert on the `ORDER BY` of the ledger SELECT: intended for lists = `performed_at DESC, id DESC` (id is the last sort key, descending); intended for the latest-entry lookup = `performed_at DESC, id DESC` followed by `LIMIT 1`. Today the clause ends at `performed_at DESC`, so these assertions fail every run (`xfail(strict=True)` is safe). A data-level tie case (tied rows → expect descending id) may be kept as extra documentation, but only as `xfail(strict=False)` because it can pass by chance today.
- To test BUG-652/BUG-653/BUG-655 with history, insert inventory ledger rows through the model directly (not through a real write path, since none exists in the app yet per the Overview) and set `performed_at` explicitly.

## Not specified
- `LedgerManager.__init__` — wires DAO singletons, no logic

---

## `LedgerManager.get_machine_ledger(session, machine_id, workspace_id, item_id=None, start_date=None, end_date=None, transaction_type=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public

**Purpose:** List one machine's item-ledger entries with optional item, date and transaction-type filters.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| machine_id | int | Always applied. Existence not checked (unknown id → `[]`). |
| workspace_id | int | Always applied. |
| item_id | int \| None | Applied when not `None` (see R2–R6). |
| start_date, end_date | datetime \| None | Used only when both are given; inclusive on `performed_at`. |
| transaction_type | str \| None | Exact, case-sensitive match; `""` treated as absent. |
| skip, limit | int | Offset / max rows, default 0 / 100; no validation here. |

**Returns:** list of `MachineItemLedger` rows (possibly empty).

**Rules:**
- **R1.** Only entries of the given workspace and the given machine are returned; an entry of the same machine id in another workspace is never returned.
- **R2.** [BUG-341] All given filters combine (AND): a full date range (`start_date <= performed_at <= end_date`, both inclusive), `transaction_type` (exact match) and `item_id` all narrow the result together when given. *(Today: a full date range makes the code ignore `transaction_type` — see P3.)*
- **R3.** [BUG-341] Each given date bound applies on its own: `start_date` alone → `performed_at >= start_date`; `end_date` alone → `performed_at <= end_date`. *(Today: only one of `start_date`/`end_date` given → no date filtering at all — see P4.)*
- **R4.** No full date range and non-empty `transaction_type` → entries whose `transaction_type` equals it exactly (case-sensitive), narrowed by `item_id` when given.
- **R5.** No full date range, no/empty `transaction_type`, `item_id` given → entries of that machine and item.
- **R6.** No filters (or `transaction_type=""`) and `item_id` `None` → all entries of the machine.
- **R7.** `start_date` later than `end_date` → `[]`.
- **R8.** [BUG-640] Order: `performed_at` newest first, then `id` descending. *(Today: `performed_at` only; ties in no fixed order.)*
- **R9.** [BUG-642] `skip` rows are skipped and at most `limit` rows returned, after filtering and ordering. `limit` must be ≥ 1 (422 at the API). *(Today: `limit=0` → `[]`; negative `limit` → database error.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` or `skip` (today, until BUG-642 is fixed at the API) | SQLAlchemy `DataError` from Postgres | — |

**Side effects:** none

---

## `LedgerManager.get_machine_balance(session, machine_id, item_id, workspace_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public

**Purpose:** Current quantity and value of one item on one machine, as recorded by the latest ledger entry.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| machine_id, item_id, workspace_id | int | Identify the bucket; existence not checked. |

**Returns:** tuple `(quantity: int, total_value: Decimal)`.

**Rules:**
- **R1.** No ledger entry for (workspace, machine, item) → `(0, Decimal("0.00"))`.
- **R2.** Otherwise → the latest entry's `(qty_after, value_after)`; `value_after` empty (`NULL`) → `Decimal("0.00")`. Entries of other machines, items or workspaces are ignored.
- **R3.** [BUG-641] Latest = greatest `performed_at`, ties broken by greatest `id`. *(Today: ties resolved arbitrarily.)*

**Errors:** none

**Side effects:** none

---

## `LedgerManager.reconcile_machine_item(session, machine_id, item_id, workspace_id, user_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public

**Purpose:** Make the `machine_items` snapshot quantity match the machine ledger, recording an adjustment when they differ.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| machine_id, item_id, workspace_id | int | Identify the bucket; existence not checked. |
| user_id | int | Stored as `performed_by` on the adjustment row and the activity event. |

**Returns:** dict with keys `status`, `ledger_qty`, `snapshot_qty`, `discrepancy`, `adjustment_created` (+ `error` on the error path). Changes flushed, not committed.

**Rules:**
- **R1.** Ledger quantity = `get_machine_balance` quantity for the bucket (R1–R3 there: 0 when no entries; R3's tie-break fix is BUG-641).
- **R2.** Snapshot = the `machine_items` row for (workspace, machine, item); a row in another workspace is not found. (Latest-entry tie rule: see `get_machine_balance` R3, BUG-641.)
- **R3.** Discrepancy = ledger quantity − snapshot quantity (signed).
- **R4.** [BUG-649] No snapshot row and ledger quantity is 0 → returns `{"status": "balanced", "ledger_qty": 0, "snapshot_qty": 0, "discrepancy": 0, "adjustment_created": False}`; nothing written, no event. *(Today: same result as R5 below — `"status": "error"` — even with nothing to reconcile.)*
- **R5.** No snapshot row and ledger quantity ≠ 0 → `{"status": "error", "ledger_qty": <ledger qty>, "snapshot_qty": 0, "discrepancy": <ledger qty>, "adjustment_created": False, "error": "Snapshot missing for item with ledger transactions"}`; no snapshot row is created (see Q6). ✅
- **R6.** Snapshot quantity equals ledger quantity → `{"status": "balanced", "ledger_qty": q, "snapshot_qty": q, "discrepancy": 0, "adjustment_created": False}`. Nothing written, no event.
- **R7.** On a discrepancy, the adjustment price `avg_price` = latest ledger entry's `avg_price_after`; no ledger entry → `Decimal("0.00")`.
- **R8.** [BUG-650] Latest entry exists with an empty `avg_price_after` → treated as `Decimal("0.00")` (same as no entry); the reconcile completes. *(Today: `TypeError`, nothing corrected.)*
- **R9.** On a discrepancy, exactly one `machine_item_ledger` row is created. The fields that are already correct today: `workspace_id`, `machine_id`, `item_id` as given; `transaction_type "inventory_adjustment"`; `unit_cost = avg_price`; `qty_after` = the ledger quantity; `value_after` = ledger quantity × `avg_price`; `avg_price_before = avg_price_after = avg_price`; `source_type "reconciliation"`; `source_id`, `order_*`, `invoice_id`, transfer fields `NULL`; `notes = "Reconciliation adjustment: Snapshot was <snapshot qty>, ledger shows <ledger qty>. Discrepancy: <discrepancy>"` exactly (integers, signed discrepancy, e.g. `"Reconciliation adjustment: Snapshot was 15, ledger shows 10. Discrepancy: -5"`) — the snapshot's old quantity and the discrepancy live in `notes`; `performed_by = user_id`; `performed_at` = now (`utcnow`).
- **R9a.** [BUG-651] The same row keeps the ledger's running chain continuous: `quantity = 0`; `total_cost = Decimal("0.00")`; `qty_before` = the ledger quantity (so `qty_before = qty_after`); `value_before` = ledger quantity × `avg_price` (so `value_before = value_after`). *(Today: `quantity = |discrepancy|`; `total_cost = |discrepancy| × avg_price`; `qty_before` = the snapshot's old quantity; `value_before` = snapshot's old quantity × `avg_price` — breaks the chain, which already ended at the ledger quantity on the previous row.)*
- **R10.** On a discrepancy, the snapshot's `qty` is set to the ledger quantity (other snapshot fields unchanged) and flushed. Result: `{"status": "adjusted", "ledger_qty": L, "snapshot_qty": <old snapshot qty>, "discrepancy": L − old, "adjustment_created": True}`. A negative discrepancy (snapshot higher than ledger) works the same way: the response `"discrepancy"` is negative (e.g. snapshot 15, ledger 10 → `-5`) and the ledger row follows R9/R9a (`quantity = 0`; the signed discrepancy appears only in `notes`). *(The response dict is unaffected by the BUG-651 fix.)*
- **R10a.** On a discrepancy, one machine activity event is written: `event_type "ledger_reconciled"`, `machine_id`, `workspace_id`, `performed_by = user_id`, `description = "Ledger reconciled for <item name>: snapshot <old> → <ledger qty>"`, metadata `{"item_id": item_id, "item_name": <item name>, "changes": [{"field": "qty", "label": "Quantity", "from_value": "<old>", "to_value": "<ledger qty>"}]}` (values as strings). Item name = the catalog item's `name` in this workspace (inactive items included); item not found in the workspace → `"Item #<item_id>"`.
- **R11.** [BUG-643] The snapshot row is read with a row lock, exactly `FOR UPDATE OF machine_items` — the lookup eager-joins `items` (`MachineItem.item` is `lazy="joined"`), so Postgres refuses a plain `FOR UPDATE` (BUG-029 restriction); no `SKIP LOCKED`, no `NOWAIT`, no lock on `items`; held until the caller's commit or rollback. A second concurrent reconcile waits, then sees the corrected snapshot and returns `balanced` without writing. *(Today: no lock; both write an adjustment row and an event.)*

**Errors:** none (until BUG-650 is fixed, an empty `avg_price_after` on the latest entry with a non-zero discrepancy raises `TypeError` today).

**Side effects:** on discrepancy only: 1 ledger row, snapshot `qty` updated, 1 `machine_activity_events` row; flushed, not committed.

---

## `LedgerManager.get_project_component_ledger(session, project_component_id, workspace_id, item_id=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public

**Purpose:** List a project component's item-ledger entries, optionally for one item.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| project_component_id, workspace_id | int | Always applied; existence not checked here. |
| item_id | int \| None | Applied when truthy (`None`/`0` → no item filter). |
| skip, limit | int | Default 0 / 100. |

**Returns:** list of `ProjectComponentItemLedger` rows.

**Rules:**
- **R1.** Only entries of the given workspace and component; same component id in another workspace never returned.
- **R2.** `item_id` given → only entries of that item.
- **R3.** `item_id` `None` → all entries of the component.
- **R4.** [BUG-640] Order: `performed_at` newest first, then `id` descending. *(Today: `performed_at` only.)*
- **R5.** [BUG-642] `skip`/`limit` applied after filtering and ordering; `limit >= 1` (422 at API). *(Today: `0` → `[]`, negative → database error.)*

**Errors:** as `get_machine_ledger` (negative limit/skip today, until BUG-642 is fixed).

**Side effects:** none

---

## `LedgerManager.calculate_project_component_total_cost(session, project_component_id, workspace_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public

**Purpose:** Total item cost booked to a project component.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| project_component_id, workspace_id | int | Scope; existence not checked. |

**Returns:** `Decimal`.

**Rules:**
- **R1.** [BUG-654] Result = net cost consumed by the component: `total_cost` of incoming rows (`purchase_order`, `manual_add`, `transfer_in`, `consumption`, `inventory_adjustment`, `cost_adjustment`) added, `total_cost` of outgoing rows (`transfer_out`, `damaged`) subtracted (outgoing set per the reviewed examples; any future transaction type defaults to incoming — best-practice default, delegated by reviewer). Rows of other components/workspaces ignored. *(Today: every transaction type added positively, so a returned/damaged row inflates the total instead of reducing it.)*
- **R2.** No rows, or a sum of exactly 0 → `Decimal("0.00")`.

**Errors:** none

**Side effects:** none

---

## `LedgerManager.get_inventory_ledger(session, workspace_id, inventory_type=None, factory_id=None, item_id=None, start_date=None, end_date=None, transaction_type=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public

**Purpose:** List unified inventory ledger entries of a workspace with optional scope, date and type filters.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| workspace_id | int | Always applied. |
| inventory_type | InventoryTypeEnum \| None | Applied when given (`STORAGE`/`DAMAGED`/`WASTE`/`SCRAP`). |
| factory_id, item_id | int \| None | Applied when truthy. |
| start_date, end_date | datetime \| None | Used only when both given; inclusive. |
| transaction_type | str \| None | Exact, case-sensitive; `""` = absent. |
| skip, limit | int | Default 0 / 100. |

**Returns:** list of `InventoryLedger` rows.

**Rules:**
- **R1.** Only entries of the given workspace; `inventory_type`, `factory_id`, `item_id` each narrow the result when given, in every path below.
- **R2.** [BUG-341] All given filters combine (AND): a full date range (`start_date <= performed_at <= end_date`), `transaction_type` (exact match) and the scope filters all narrow the result together when given. *(Today: a full date range makes the code ignore `transaction_type` — see P3.)*
- **R3.** [BUG-341] Each given date bound applies on its own: `start_date` alone → `performed_at >= start_date`; `end_date` alone → `performed_at <= end_date`. *(Today: only one date given → no date filtering at all — see P4.)*
- **R4.** No full date range, non-empty `transaction_type` → exact type match plus scope filters.
- **R5.** Otherwise → all entries matching the scope filters.
- **R6.** No scope filters → every inventory ledger entry of the workspace (all types, factories, items).
- **R7.** `start_date` later than `end_date` → `[]`.
- **R8.** [BUG-640] Order: `performed_at` newest first, then `id` descending. *(Today: `performed_at` only.)*
- **R9.** [BUG-642] `skip`/`limit` applied after filtering and ordering; `limit >= 1` (422 at API). *(Today: `0` → `[]`, negative → database error.)*

**Errors:** as `get_machine_ledger` (negative limit/skip today, until BUG-642 is fixed).

**Side effects:** none

---

## `LedgerManager.get_inventory_balance(session, factory_id, item_id, inventory_type, workspace_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public

**Purpose:** Current quantity and value of one (factory, item, inventory type) bucket from its latest ledger entry.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| factory_id, item_id, workspace_id | int | Bucket; existence not checked. |
| inventory_type | InventoryTypeEnum | Each type is its own bucket. |

**Returns:** `(quantity: int, total_value: Decimal)`.

**Rules:**
- **R1.** No entry for the bucket → `(0, Decimal("0.00"))`.
- **R2.** [BUG-655] Bucket has at least one entry → `(qty_after, qty_after × avg_price_after)` of the latest entry; empty `avg_price_after` → value `Decimal("0.00")`. Entries of another inventory type, factory, item or workspace are ignored (a bucket whose only entries are of another type/factory/item/workspace takes the R1 path). *(Today: raises `AttributeError` — `'InventoryLedger' object has no attribute 'value_after'` — because the inventory ledger has no `value_after` column but the balance lookup reads it.)*
- **R3.** [BUG-641] Latest = greatest `performed_at`, then greatest `id`. *(Today: ties arbitrary.)*

**Errors:** none (until BUG-655 is fixed, a bucket with ≥ 1 ledger entry raises `AttributeError`: `'InventoryLedger' object has no attribute 'value_after'`).

**Side effects:** none

---

## `LedgerManager.reconcile_inventory(session, factory_id, item_id, inventory_type, workspace_id, user_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public

**Purpose:** Make one inventory snapshot bucket's quantity match the inventory ledger, recording an adjustment when they differ.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| factory_id, item_id, workspace_id | int | Bucket; existence not checked. |
| inventory_type | InventoryTypeEnum | Bucket type. |
| user_id | int | `performed_by` of the adjustment row. |

**Returns:** dict as `reconcile_machine_item`. Flushed, not committed.

**Rules:**
- **R1.** [BUG-655] Ledger quantity = `get_inventory_balance` quantity for the bucket (fixed alongside `get_inventory_balance` R2 — same bug). *(Today: any bucket with at least one ledger entry raises `AttributeError` before the snapshot is read; only buckets with no ledger entries reach R2–R11.)*
- **R2.** Snapshot = the live (`is_deleted = False`) `inventory` row for (workspace, factory, item, type); a soft-deleted row counts as missing; rows of other workspaces/types not found. (Latest-entry tie rule: see `get_inventory_balance` R3, BUG-641.)
- **R3.** Quantity discrepancy = ledger quantity − snapshot quantity. A correction is needed when the quantity discrepancy is non-zero **or** (BUG-653) the snapshot's `avg_price` differs from the latest ledger entry's `avg_price_after` (R7).
- **R4.** [BUG-649] No live snapshot and ledger quantity is 0 → returns `{"status": "balanced", "ledger_qty": 0, "snapshot_qty": 0, "discrepancy": 0, "adjustment_created": False}`; nothing written. *(Today: same result as R5 below — `"status": "error"` — even with nothing to reconcile.)*
- **R5.** No live snapshot and ledger quantity ≠ 0 → same error dict as `reconcile_machine_item` R4 (same message); no snapshot created or restored. ✅
- **R6.** Quantities equal **and** the snapshot's `avg_price` equals the latest entry's `avg_price_after` → `balanced` dict (as `reconcile_machine_item` R6); nothing written.
- **R6a.** [BUG-653] Quantities equal but the snapshot's `avg_price` differs from the ledger's avg_price → treated as a correction (R3): reported as `adjusted` (`discrepancy: 0`) and `avg_price` corrected per R10. *(Today: reported `balanced`, price left wrong.)* The ledger's avg_price used in this comparison is exactly the R7/R8 value: the latest entry's `avg_price_after`, or `Decimal("0.00")` when the bucket has no ledger entry or that value is empty. A snapshot `avg_price` that is empty (`NULL`) compares as `0.00`. So: ledger empty, snapshot qty 0 @ 5.00 → `adjusted`, snapshot `avg_price` becomes `0.00`; ledger empty, snapshot qty 0 @ `NULL` or 0.00 → `balanced`, nothing written. (Comparison base and `NULL` handling: best-practice default, delegated by reviewer — the ledger is the source of truth, and one "ledger price" value is used everywhere in the method.)
- **R7.** `avg_price` = latest entry's `avg_price_after`; no entry → `Decimal("0.00")`.
- **R8.** [BUG-650] Latest entry exists with an empty `avg_price_after` → treated as `Decimal("0.00")` (same as no entry); the reconcile completes. *(Today: `TypeError`, nothing corrected.)*
- **R9.** On a correction (R3), exactly one `inventory_ledger` row is created. The fields that are already correct today (for a quantity discrepancy): `workspace_id`, `inventory_type`, `factory_id`, `item_id` as given; `transaction_type "inventory_adjustment"`; `unit_cost = avg_price`; `qty_after` = the ledger quantity; `avg_price_before = avg_price_after = avg_price`; `source_type "reconciliation"`; `source_id` and transfer fields `NULL`; `notes` **starts with** `"Reconciliation adjustment: Snapshot was <snapshot qty>, ledger shows <ledger qty>. Discrepancy: <discrepancy>"` (same text as `reconcile_machine_item` R9; integers, signed discrepancy); `performed_by = user_id`; `performed_at` = database now. *(Writing a ledger row for an avg_price-only correction is a best-practice default, delegated by reviewer, for symmetry with the quantity-discrepancy case and to keep every snapshot change auditable.)*
- **R9a.** [BUG-651] The same row keeps the ledger's running chain continuous: `quantity = 0`; `total_cost = Decimal("0.00")`; `qty_before` = the ledger quantity (so `qty_before = qty_after`). *(Today: `quantity = |discrepancy|`; `total_cost = |discrepancy| × avg_price`; `qty_before` = the snapshot's old quantity.)*
- **R9b.** [BUG-651] The row's `notes` is exactly `"Reconciliation adjustment: Snapshot was <snapshot qty>, ledger shows <ledger qty>. Discrepancy: <discrepancy>. Avg price: snapshot was <old snapshot avg_price>, ledger shows <avg_price>"` — i.e. the R9 sentence followed by `". Avg price: snapshot was X, ledger shows Y"`, always present (also when the prices are equal and only the quantity differs). Prices are written with exactly two decimals (e.g. `5.00`, `6.50`); an empty (`NULL`) snapshot `avg_price` is written as `0.00`. Example: snapshot 10 @ 5.00, ledger 12 @ 6.50 → `"Reconciliation adjustment: Snapshot was 10, ledger shows 12. Discrepancy: 2. Avg price: snapshot was 5.00, ledger shows 6.50"`. An avg_price-only correction (R6a) uses the same text with `Discrepancy: 0`. (Exact format: best-practice default, delegated by reviewer — keeps today's quantity sentence unchanged and records the old price the snapshot loses in R10.) *(Today: notes end after `Discrepancy: <discrepancy>`; the old avg_price is not recorded anywhere.)*
- **R10.** [BUG-652] On a correction (R3), the snapshot's `qty` = ledger quantity (no-op when already equal, R6a) and `avg_price` = `avg_price` (R7, so `0.00` when the ledger is empty); `updated_by` = `user_id`; `updated_at` refreshed by the database; flushed. Returns the `adjusted` dict as `reconcile_machine_item` R10. No activity event is written. *(Today: `updated_by` left unchanged.)*
- **R11.** [BUG-644] Snapshot read with exactly `FOR UPDATE OF inventory` (`Inventory.item` is `lazy="joined"`, so a plain `FOR UPDATE` is refused — BUG-029 restriction; no `SKIP LOCKED` / `NOWAIT`, no lock on `items`); a second concurrent reconcile returns `balanced` without writing. *(Today: no lock.)*

**Errors:** none (until BUG-650 is fixed, an empty `avg_price_after` on the latest entry with a correction due raises `TypeError` today; until BUG-655 is fixed, any bucket with ≥ 1 ledger entry raises `AttributeError` at R1).

**Side effects:** on a correction only (R3): 1 inventory ledger row; snapshot `qty`, `avg_price`, `updated_by` updated; flushed, not committed.

---

## `LedgerManager.get_attachment_ledger(session, workspace_id, attachment_id=None, entity_type=None, start_date=None, end_date=None, transaction_type=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public

**Purpose:** List attachment lifecycle ledger entries of a workspace with optional filters.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| workspace_id | int | Always applied. |
| attachment_id | int \| None | Applied when not `None`. |
| entity_type, transaction_type | str \| None | Exact, case-sensitive; `""` = absent. |
| start_date, end_date | datetime \| None | Each applied independently when not `None`, inclusive. |
| skip, limit | int | Default 0 / 100. |

**Returns:** list of `AttachmentLedger` rows.

**Rules:**
- **R1.** Only entries of the given workspace.
- **R2.** `attachment_id`, `entity_type`, `transaction_type` each narrow the result when given; all given filters combine (AND).
- **R3.** `start_date` alone → `performed_at >= start_date`; `end_date` alone → `performed_at <= end_date`; both → inclusive range. ✅
- **R4.** No filters → all entries of the workspace.
- **R5.** [BUG-640] Order: `performed_at` newest first, then `id` descending. *(Today: `performed_at` only.)*
- **R6.** [BUG-642] `skip`/`limit` after filtering and ordering; `limit >= 1` (422 at API). *(Today: `0` → `[]`, negative → database error.)*

**Errors:** as `get_machine_ledger` (negative limit/skip today, until BUG-642 is fixed).

**Side effects:** none

---

## `LedgerManager.get_item_movement_summary(session, item_id, workspace_id, start_date=None, end_date=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public

**Purpose:** Report of one item's movements across ledgers.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| item_id | int | [BUG-341] Not used today (see P1). |
| workspace_id | int | Applied. |
| start_date, end_date | datetime \| None | Inclusive on `performed_at`. [BUG-646] Each given bound applies on its own; unbounded when omitted. *(Today: queries run only when both are given — see Q2.)* |
| skip, limit | int | [BUG-648] Default 0 / 100, `limit >= 1` (422 at API), applied to each of `machine`/`project`/`inventory`. *(Does not exist today — requires new parameters `skip`, `limit`.)* |

**Returns:** dict with exactly keys `machine`, `project`, `inventory`, each a list.

**Rules:**
- **R1.** [BUG-646] The report always runs (never short-circuits to empty lists just because a date is missing). Date bounds are inclusive on `performed_at`, in every list: `start_date` → `performed_at >= start_date`, `end_date` → `performed_at <= end_date` (an entry exactly at either bound is included; the underlying date-range queries already use `>=`/`<=` today). *(Today: not both dates given → `{"machine": [], "project": [], "inventory": []}`, no query made — see Q2.)*
- **R2.** [BUG-341] `machine` = machine ledger entries of the workspace filtered by `item_id`, narrowed by each given date bound (R1), for all machines. *(Today: `item_id` never applied and both dates required — see P1, Q2.)*
- **R3.** [BUG-341] `inventory` = inventory ledger entries of the workspace filtered by `item_id`, narrowed by each given date bound (R1), all types/factories. *(Today: `item_id` never applied and both dates required — see P1, Q2.)*
- **R4.** [BUG-640] Order: `performed_at` newest first, then `id` descending, for `machine`/`project`/`inventory`. *(Today: `performed_at` only, ties arbitrary.)*
- **R4a.** [BUG-648] `skip`/`limit` (new parameters — see Inputs) applied to each of `machine`/`project`/`inventory` independently, after filtering and ordering; every entry in range is reachable by paging. *(Today: each of `machine`/`inventory` silently capped at the first 100 entries, no way to page; `project` is unaffected since it is always empty — see Q4.)*
- **R5.** [BUG-647] `project` = the item's project-component ledger entries (item id + workspace), narrowed by each given date bound (R1) and `skip`/`limit` (R4a), same ordering (R4). *(Today: always `[]` — see Q3.)*
- **R6.** Entries of other workspaces never appear.

**Errors:** none

**Side effects:** none

---

## `LedgerManager.get_transactions_by_user(session, user_id, workspace_id, start_date=None, end_date=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public

**Purpose:** Audit report of the ledger entries one user performed, per ledger.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| user_id, workspace_id | int | Scope. |
| start_date, end_date | datetime \| None | [BUG-341] Each given bound restricts every list by `performed_at` (inclusive), applied before paging. *(Today: not used at all — see P2.)* |
| skip, limit | int | [BUG-642] Passed to each ledger query; `limit >= 1` (422 at API). |

**Returns:** dict `{"machine": [...], "project": [...], "inventory": [...]}`.

**Rules:**
- **R1.** [BUG-645] Each ledger DAO's `get_by_performer` lookup (workspace + `performed_by`, newest-first order, `skip`/`limit`) is queried; machine and project ledgers gain this lookup (only inventory has it today). *(Today: every call raises `AttributeError` — `'MachineItemLedgerDAO' object has no attribute 'get_by_performer'` — before any query runs; nothing is returned.)*
- **R2.** [BUG-341] `start_date` / `end_date`, when given, restrict every list by `performed_at` (inclusive), applied before paging. *(Today: have no effect at all.)*
- **R3.** [BUG-640] Each list ordered `performed_at` newest first, then `id` descending. *(Today: inventory part orders by `performed_at` only; machine/project parts do not exist — R1.)*
- **R4.** [BUG-642] `skip`/`limit` applied per ledger; `limit >= 1` (422 at API). *(Today: `0` → `[]`, negative → database error.)*

**Errors:** none (until BUG-645 is fixed, every call raises `AttributeError`: `'MachineItemLedgerDAO' object has no attribute 'get_by_performer'`).

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 71 | `start_date and end_date` both truthy | `get_machine_ledger` R2, R3 |
| dao/machine_item_ledger.py 131–134 | `machine_id` / `item_id` not None in date-range query | `get_machine_ledger` R1, R2 |
| 82 | `transaction_type` truthy (`""` falsy) | `get_machine_ledger` R4, R6 |
| dao/machine_item_ledger.py 80–83 | `machine_id` / `item_id` not None in type query | `get_machine_ledger` R4 |
| 92 | `item_id is not None` | `get_machine_ledger` R5, R6 |
| dao (all list methods) offset/limit | pagination | `get_machine_ledger` R9, `get_project_component_ledger` R5, `get_inventory_ledger` R9, `get_attachment_ledger` R6 |
| dao/machine_item_ledger.py 195 | `if entry` in `calculate_balance` | `get_machine_balance` R1, R2 |
| dao/machine_item_ledger.py 196 | `value_after or 0.00` | `get_machine_balance` R2 |
| 181 | `not snapshot` | `reconcile_machine_item` R4, R5 |
| 194 | `discrepancy == 0` | `reconcile_machine_item` R6 |
| 211 | `latest_entry` truthy | `reconcile_machine_item` R7, R8 |
| 223 | `abs(discrepancy) * avg_price` with `None` | `reconcile_machine_item` R8 |
| 244 | `catalog_item` found | `reconcile_machine_item` R10a |
| 301 | `item_id` truthy | `get_project_component_ledger` R2, R3 |
| dao/project_component_item_ledger.py 244 | `result if result else 0.00` | `calculate_project_component_total_cost` R2 |
| 385 | `start_date and end_date` | `get_inventory_ledger` R2, R3 |
| 397 | `transaction_type` truthy | `get_inventory_ledger` R4, R5 |
| dao/inventory_ledger.py 36–41, 67–72, 93–98 | `inventory_type` / `factory_id` / `item_id` truthy | `get_inventory_ledger` R1, R6 |
| dao/inventory_ledger.py 155 | `if entry` / `value_after or 0.00` | `get_inventory_balance` R1, R2 |
| dao/inventory.py 182 | `is_deleted == False` in snapshot lookup | `reconcile_inventory` R2 |
| 491 | `not snapshot` | `reconcile_inventory` R4, R5 |
| 504 | `discrepancy == 0` | `reconcile_inventory` R6 |
| 521 | `latest_entry` truthy | `reconcile_inventory` R7, R8 |
| dao/attachment_ledger.py 29 | `attachment_id is not None` | `get_attachment_ledger` R2 |
| dao/attachment_ledger.py 31, 33 | `entity_type` / `transaction_type` truthy | `get_attachment_ledger` R2, R4 |
| dao/attachment_ledger.py 35, 37 | `start_date` / `end_date` not None | `get_attachment_ledger` R3 |
| 621 | `start_date and end_date` (machine) | `get_item_movement_summary` R1, R2 |
| 632 | project always `[]` | `get_item_movement_summary` R5 |
| 635 | `start_date and end_date` (inventory) | `get_item_movement_summary` R1, R3 |
| 680 | missing `get_by_performer` on machine DAO | `get_transactions_by_user` R1 |

## Gap log
- G1 (ledger_manager.cases.md gap 1) — Intent, decided (best-practice default, delegated by reviewer) — `reconcile_inventory` notes now have an exact format: today's quantity sentence (R9, untagged) followed by `. Avg price: snapshot was <old>, ledger shows <new>` (new R9b [BUG-651]), two-decimal prices, `NULL` snapshot price written `0.00`, always present.
- G2 (ledger_manager.cases.md gap 2) — Contradiction — `reconcile_machine_item` R10 no longer says the negative discrepancy is "stored as the absolute value"; the ledger row follows R9/R9a (`quantity = 0`), the signed discrepancy appears in the response and `notes` only.
- G3 (ledger_manager.cases.md gap 3) — Intent, decided (best-practice default, delegated by reviewer) — `reconcile_inventory` R6a compares the snapshot `avg_price` with the R7/R8 value (latest `avg_price_after`, or `0.00` when no entry / empty); a `NULL` snapshot `avg_price` compares as `0.00`; examples added.
- G4 (ledger_manager.cases.md gap 4) — Fact — `reconcile_machine_item` R9 split: R9 (untagged) lists the fields correct today (incl. `value_after`, `unit_cost`, avg prices, exact `notes`); new R9a [BUG-651] holds the broken ones with Today values (`quantity = |d|`, `total_cost = |d| × avg`, `qty_before` = old snapshot qty, `value_before` = old snapshot qty × avg). `reconcile_inventory` R9 split the same way (R9 / R9a / R9b).
- G5 (ledger_manager.cases.md gap 5) — Fact — Notes for the test designer list the column types and app-written values: all `transaction_type`/`entity_type` columns are plain VARCHAR (mismatch → `[]`, never an error); only `inventory_type` is a Postgres enum; attachment rows need an `attachments` FK row.
- G6 (ledger_manager.cases.md gap 6) — Fact — `get_item_movement_summary` date bounds are inclusive (`>=`/`<=`, as the underlying date-range queries already are); added to Inputs and R1.
- G7 (ledger_manager.cases.md gap 7) — Fact (verified on the test DB) + test mechanics — today 2–3 tied rows come back in ascending id order (5+ scrambled); Notes tell the designer to use 2–3 tied rows inserted in ascending id order so BUG-640 strict xfails fail reliably today; latest-entry ties return the first-inserted row (insert the intended-latest row last). **Superseded by G8.**
- G8 (ledger_manager.verify.md finding 2) — Fact correction + test mechanics — G7's "reliably ascending id" claim is false under concurrent load (5 of 8 verifier runs XPASSed strict tie xfails). Notes now say tie order today is undefined, give the exact `ORDER BY` emitted today (lists: `performed_at DESC`; latest lookup: `performed_at DESC LIMIT 1`) and intended (`performed_at DESC, id DESC`), and direct the designer to prove BUG-640/BUG-641 from the recorded SQL `ORDER BY` with `strict=True`; data-level tie cases allowed only as `strict=False` (best-practice default, delegated by reviewer). Rules unchanged; no new bug.
- C1 (2026-11-22, routed by the `ledger_service` verifier; decided under the reviewer's delegation) — Fact (lock clause) — `reconcile_machine_item` R11 and `reconcile_inventory` R11 (and the HR-10 lines) now state the exact clauses `FOR UPDATE OF machine_items` / `FOR UPDATE OF inventory`, as `ledger_service.spec.md` R9 / R7 do (query shapes compiled for the PostgreSQL dialect in the ledger_service fill-gaps). BUG-643 / BUG-644 rows already say so. LED-RMI-16 / LED-RINV-17 should assert the exact clause, not just `FOR UPDATE`.
