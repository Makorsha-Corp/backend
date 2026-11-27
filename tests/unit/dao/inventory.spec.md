# Spec — `app/dao/inventory.py`

> **Status:** APPROVED
> **Source commit:** e48a092

> **Review note (history):** the suggested answers were first applied to the rules as provisional defaults before any reviewer answer; all of them have since been answered by the reviewer (see the two rounds below) — no provisional default remains.
>
> **Review round 2026-10-10 (1):** the reviewer answered **Q2** (overriding the suggested `intended`): stock in a soft-deleted factory must not show up or be counted → 🐞 BUG-882, rules `_filtered_query` R11a, `list_filtered` R1a, `count_filtered` R1a, `stats_filtered` R1a / R5a. Applying the same principle raised four follow-up questions, **Q6–Q9**.
>
> **Review note 2026-10-10 (2):** the reviewer accepted every remaining suggested answer as written. House-rule lines stand (BUG-701, BUG-702). P1–P4 confirmed (BUG-664, BUG-719, BUG-880, BUG-881). Q3, Q4, Q5 → `remove` (dead code). **Q6** → `bug`, 🐞 BUG-883: stock of a catalog item with `is_active = False` is excluded from list, count, statistics and search — rules `_filtered_query` R11 (rewritten), R11c (new), `list_filtered` R1b, `count_filtered` R1b, `stats_filtered` R1b / R5b (new); **Q1 is superseded by Q6** (its provisional default `intended` is withdrawn). **Q7** → `bug`, 🐞 BUG-884: `get_by_item` must not return rows held in a soft-deleted factory — rules `get_by_item` R1 (split), R1a (new, tagged), R1b (new), R6 (narrowed). **Q8, Q9** → `intended`. No question is pending.
>
> **⚠️ Cross-spec conflict to resolve in the manager spec's own pass (not edited here):** BUG-883 (Q6) conflicts with the approved `tests/unit/managers/inventory_manager.spec.md`, `create_inventory` **R3a** ("an inactive item (`is_active = False`) of the workspace is accepted like an active one … deactivating a catalog item does not erase stock that may still exist" — a best-practice default delegated by the reviewer, not an explicit reviewer answer). After Q6, stock created for a removed item would be accepted and then be invisible on the stock page and in every count. The manager spec needs a follow-up question / rewrite of R3a (most likely: a removed item is refused for new stock, like a soft-deleted factory in BUG-715). Until that pass, the two specs disagree and this spec (the later, explicit reviewer decision) takes precedence for the DAO.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically
> Both lines stand (reviewer, 2026-10-10). Both defects were already recorded when the inventory manager was reviewed; the code to fix lives in this DAO, so the existing IDs are reused (no new ID).

- **HR-6** `list_filtered` R2 — the inventory page is ordered by item name using the database's default text ordering (case handling depends on the database collation), then inventory `id`. Intended: item name case-insensitive ascending, then inventory `id` ascending, before `skip`/`limit`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-701 (existing, logged against `app/managers/inventory_manager.py`; fix is in `InventoryDAO.list_filtered`) — no new ID. Rules: `list_filtered` R2.
- **HR-8** `_filtered_query` R9 — the search text is put into `ILIKE '%…%'` unescaped: `%` or `_` alone matches every stock row, and `\` acts as an escape character. Intended: `%`, `_` and `\` match literally in both item name and item unit.
**Answer:** bug — per HR-8 (house rule)
**Resolution:** 🐞 BUG-702 (existing, logged against `app/managers/inventory_manager.py`; fix is in `InventoryDAO._filtered_query`) — no new ID. Rules: `_filtered_query` R9.

### Precedent matches — all confirmed by the reviewer (2026-10-10)

### P1. "Latest ledger entry" is chosen by timestamp alone — 🐞 BUG-664 (existing)
**Background:** Before stock is moved, the stock row (quantity + average price) is overwritten with the values of the newest ledger entry of that factory / item / type ("ledger wins"). "Newest" is decided only by the entry's `performed_at` time. Entries written within one save all get the same time.
**What happens today:** When two or more entries share the newest time, any one of them may be used, so the stock row can be set to an older entry's quantity.
**Example:** One save writes two entries for Bolt / STORAGE / Factory 1 at 10:00:00 — first "after: 15", then "after: 10". The next sync may set the stock row to 15 instead of 10.
**Rules affected:** `sync_snapshot_from_ledger` R12
**Answer:** bug — per BUG-664 precedent: newest = greatest `performed_at`, ties broken by greatest `id` (fix in `InventoryLedgerDAO.get_latest_entry`) (reviewer accepted suggestion, 2026-10-10)
**Resolution:** referenced existing BUG-664 (no new ID). Rules: `sync_snapshot_from_ledger` R12.

### P2. Per-type breakdown of the stock statistics has no fixed order — 🐞 BUG-719 (existing)
**Background:** The statistics include one row per inventory type that has matching stock (STORAGE, DAMAGED, WASTE, SCRAP). The query groups by type without sorting.
**What happens today:** The rows come back in whatever order the database produces; it can differ between calls.
**Example:** Two calls of `GET /inventory/stats/` return `by_type` as `[STORAGE, SCRAP]` and then `[SCRAP, STORAGE]`.
**Rules affected:** `stats_filtered` R6
**Answer:** bug — per BUG-719 precedent: rows ordered by inventory type in enum order STORAGE, DAMAGED, WASTE, SCRAP (fix in `InventoryDAO.stats_filtered`) (reviewer accepted suggestion, 2026-10-10)
**Resolution:** referenced existing BUG-719 (no new ID). Rules: `stats_filtered` R6.

### P3. Factory filter `0` means "all factories" — 🐞 BUG-880
**Background:** The stock list, its total and the statistics accept an optional factory filter and an optional item filter. The item filter is skipped only when it is not given. The factory filter is skipped whenever its value is "falsy", which includes the number `0`. `GET /inventory/` and `GET /inventory/stats/` accept any integer for `factory_id`.
**What happens today:** `factory_id=0` returns and counts the stock of every factory, whereas `item_id=0` correctly returns nothing.
**Example:** A client with no factory selected sends `GET /inventory/?factory_id=0`. Instead of an empty list it receives all 240 stock rows of all factories, and the KPI tiles show the whole workspace's totals as if they belonged to "factory 0".
**Rules affected:** `_filtered_query` R5
**Answer:** bug — per BUG-501 / BUG-707 precedent: only "not given" (`None`) skips the factory filter; `factory_id=0` filters and matches no rows, exactly like `item_id=0` (reviewer accepted suggestion, 2026-10-10)
**Resolution:** 🐞 BUG-880 (pattern `falsy-zero-treated-as-missing`). Rules: `_filtered_query` R5.

### P4. Restoring a deleted stock row does not record who restored it — 🐞 BUG-881
**Background:** Stock rows can be soft-deleted (`is_deleted = True`, row stays). When stock is posted to a factory / item / type whose row is soft-deleted, the row is brought back instead of creating a second one. `updated_by` ("last changed by") is only written by the ledger sync that follows, and only when the sync changes the quantity or the average price.
**What happens today:** If the restored row's quantity and price already equal the ledger's, the row comes back to life with its old `updated_by` (or none). Nothing shows who restored it.
**Example:** Row 40 (Bolt / STORAGE / Factory 2, qty 4, last changed by Alice) was soft-deleted. Bob posts stock to it; the ledger also ends at 4. Row 40 is live again, `updated_by` is still Alice.
**Rules affected:** `ensure_for_factory_item_type` R4
**Answer:** bug — per BUG-652 precedent (HR-9: a change records who made it): a restored row always gets `updated_by` = the acting user, whether or not quantity / price change (reviewer accepted suggestion, 2026-10-10)
**Resolution:** 🐞 BUG-881 (pattern `audit-stamp-missing-on-change`). Rules: `ensure_for_factory_item_type` R4.

### New questions

### Q1. Stock of a deleted catalog item is still listed, counted and searchable — ⏭️ superseded by Q6 (🐞 BUG-883)
**Background:** Catalog items are soft-deleted by setting `is_active = False`; the item row stays. Stock rows point at their item. House rule HR-4 says lists and searches normally ignore soft-deleted related rows (e.g. a deleted tag no longer matches a search).
**What happens today:** A stock row whose item was deleted is still returned by the stock list, counted in the total and the statistics (quantity and value), and found when searching for the deleted item's name or unit.
**Example:** Item "Old Gasket" is deleted from the catalog while Factory 1 still holds 12 of them. `GET /inventory/?search=gasket` still shows "Old Gasket — 12", and the stock value KPI still includes it.
**Rules affected:** `_filtered_query` R11
**Suggested answer:** `intended` — physical stock does not disappear when its catalog entry is deactivated; hiding it would understate stock quantity and value. (Matches the already-approved decision that an inactive item is still accepted for stock: inventory manager spec `create_inventory` R3a.)
**Answer:** superseded by Q6 — the provisional default `intended` was never accepted by the reviewer and is withdrawn (2026-10-10)
**Resolution:** superseded by Q6 / 🐞 BUG-883: the same state (item `is_active = False`) was put to the reviewer again as Q6 after the Q2 decision and answered `bug` — such stock is excluded from list, count, statistics and search. Nothing in the rules follows Q1 any more. Rules: `_filtered_query` R11 (see Q6).

### Q2. Stock held in a deleted factory is still listed and counted — 🐞 BUG-882
**Background:** Factories are soft-deleted (`is_deleted = True`, row stays). Stock rows point at their factory. The stock queries never look at the factory row.
**What happens today:** Stock rows of a deleted factory are returned by the stock list and included in the totals and statistics — both when no factory filter is given and when that factory's id is given.
**Example:** Factory 9 "Old Plant" is deleted while it still holds 30 bolts. The workspace stock list (no factory filter) still shows the 30 bolts with factory id 9, and the stock value KPI includes them; the UI has no factory named "Old Plant" any more.
**Rules affected:** `_filtered_query` R11a (split out of R11), `list_filtered` R1a, `count_filtered` R1a, `stats_filtered` R1a, R5a
**Suggested answer (overridden by the reviewer):** `intended` — the stock still physically exists and must stay in the valuation; silently dropping it would lose stock. The proper fix for the confusing display is elsewhere (refuse to delete a factory that still holds stock — a factory-manager decision, not this DAO).
**Answer:** bug — "Soft-deleted things should not show up. We keep the information, but it is not used for anything counted." (reviewer decision 2026-10-10)
**Resolution:** 🐞 BUG-882 (pattern `join-ignores-soft-deleted`, HR-4 third bullet). A stock row whose factory is soft-deleted (`factories.is_deleted = True`) stays in the database untouched but is excluded from the filtered list, the count and every part of the statistics (totals and per-type breakdown), with or without a `factory_id` filter; an inactive-but-live factory still counts. Rules: `_filtered_query` R11a (new, tagged; R11 keeps only the item half, which belongs to Q1), R11b (new, untagged — what already holds), `list_filtered` R1a, `count_filtered` R1a, `stats_filtered` R1a and R5a (new, tagged). Follow-ups raised by the same principle: Q6–Q9 (all answered 2026-10-10; R11's item half now belongs to Q6 / BUG-883).

### Q3. The DAO's own "list by workspace" method is not reachable — 🗑️ remove (dead code)
**Background:** `InventoryDAO.get_by_workspace` (list with optional type / factory filter, zero-quantity rows included) is called only by `InventoryManager.list_inventory`. That manager method was already ruled dead code (inventory manager spec Q11): `GET /inventory/` uses the paginated list instead.
**What happens today:** The method can never run in production.
**Example:** No API request reaches it; breaking it has no visible effect.
**Rules affected:** `get_by_workspace` (all)
**Suggested answer:** `remove`
**Answer:** remove (reviewer accepted suggestion, 2026-10-10)
**Resolution:** not specified; listed under **Not specified** and in `docs/testing/dead-code-removal-checklist.md` (`app/dao/inventory.py:146`). Not a bug — no BUG ID.

### Q4. The stock-row soft-delete method is never called — 🗑️ remove (dead code)
**Background:** `InventoryDAO.soft_delete` marks a stock row deleted. `DELETE /inventory/{id}/` does not use it: "clear stock" sets the quantity to zero and keeps the row. Nothing else in the application or its tests calls it. (Soft-deleted stock rows only exist as legacy data; the method that brings them back, `restore`, is still used.)
**What happens today:** The method can never run in production.
**Example:** No API request, background job or script soft-deletes a stock row.
**Rules affected:** `soft_delete` (all)
**Suggested answer:** `remove`
**Answer:** remove (reviewer accepted suggestion, 2026-10-10)
**Resolution:** not specified; listed under **Not specified** and in `docs/testing/dead-code-removal-checklist.md` (`app/dao/inventory.py:309`). `restore` stays specified. Not a bug — no BUG ID.

### Q5. "Stock rows of one item" has a type filter nobody uses — 🗑️ remove (dead parameter)
**Background:** `get_by_item` returns all stock rows of one catalog item. It has an optional `inventory_type` filter. Its only caller (the item summary page) never passes it.
**What happens today:** The filter code can never run in production.
**Example:** The item summary always loads the item's rows of all four types and groups them itself.
**Rules affected:** `get_by_item` (the `inventory_type` parameter only)
**Suggested answer:** `remove` (the parameter and its filter; the method stays)
**Answer:** remove — the `inventory_type` parameter and its filter only (reviewer accepted suggestion, 2026-10-10)
**Resolution:** the parameter and its `if inventory_type:` filter are not specified (the method `get_by_item` itself stays specified); listed under **Not specified** and in `docs/testing/dead-code-removal-checklist.md` (`app/dao/inventory.py:297,305-306`). Not a bug — no BUG ID.

### Follow-up questions (raised by the Q2 decision of 2026-10-10)
> The reviewer ruled on Q2: "Soft-deleted things should not show up. We keep the information, but it is not used for anything counted." The four questions below asked how far that sentence reaches in this module. All four were answered on 2026-10-10 (suggested answers accepted as written) and are applied to the rules.

### Q6. A catalog item removed from the catalog: its stock still shows up and is counted — 🐞 BUG-883
**Background:** Catalog items have **no** `is_deleted` column. The only way an item is removed is "delete item", which sets `is_active = False` and keeps the row (the code itself calls this "soft delete"; a second delete answers "already deleted"). There is no separate "deactivate" action for items. So for items, "deactivated" and "soft-deleted" are one and the same state. Q1 above asks about exactly this state and currently carries the provisional default `intended` (the stock stays visible and counted) — the opposite of what the reviewer has now decided for factories in Q2.
**What happens today:** A stock row whose item was removed from the catalog is still listed, counted in the total and the statistics, and found by a search for the removed item's name or unit (`_filtered_query` R11).
**Example:** Item "Old Gasket" is deleted from the catalog while Factory 1 still holds 12 of them at 5.00. The stock page still shows "Old Gasket — 12", `total` includes it, and the stock value KPI includes its 60.00. Under the Q2 principle it would disappear from all three, while the stock row itself stays in the database.
**Rules affected:** `_filtered_query` R11 (and Q1, which this answer would settle)
**Suggested answer:** `bug — stock of a catalog item with is_active = False is excluded from the list, the count and the statistics, and its name/unit no longer match a search; the stock row is kept` — read literally, the reviewer's sentence covers it, because `is_active = False` is the only "deleted" an item has. (Counter-argument, the reason for Q1's provisional default: the approved inventory manager spec, `create_inventory` R3a, still accepts an inactive item for new stock; if this is answered `bug`, that rule should be revisited too.)
**Answer:** bug — stock of a catalog item with `is_active = False` is excluded from the list, the count and the statistics, and its name/unit no longer match a search; the stock row is kept (reviewer accepted suggestion, 2026-10-10)
**Resolution:** 🐞 BUG-883 (pattern `join-ignores-soft-deleted`, HR-4 third bullet; same principle as BUG-882). A stock row whose item has `is_active = False` (the item's only "removed" state) stays in the database untouched but is excluded from the filtered list, the count and every part of the statistics (totals and per-type breakdown) — with no filter, with that item's own id as `item_id`, and for a search on its name or unit. **Supersedes Q1.** Rules: `_filtered_query` R11 (rewritten, tagged), R11c (new, untagged — what already holds), `list_filtered` R1b, `count_filtered` R1b, `stats_filtered` R1b and R5b (new, tagged).
- **Conflict with an approved spec (not edited here):** `tests/unit/managers/inventory_manager.spec.md` `create_inventory` R3a still accepts an inactive item for new stock. That rule needs a follow-up in the manager spec's own pass (see the note at the top of this file).
- **Scope decision (best-practice default, delegated by reviewer):** the Q6 answer names list, count, statistics and search — i.e. `_filtered_query` and its three callers. The single-row and single-item lookups (`get_by_id_and_workspace`, `get_by_factory_item_type`, `_get_any_by_factory_item_type`, `ensure_for_factory_item_type`, `get_by_item`) keep ignoring the item's `is_active`: they are raw lookups (HR-4 scope; same reasoning the reviewer accepted in Q8 / Q9), "get or create the bucket" must still see an existing bucket of a removed item or it would hit the one-row-per-bucket constraint, and `get_by_item` is called for one explicitly named item — whether the summary page of a removed item is shown at all is the item-summary service's decision, not this DAO's. Rules: `get_by_item` R3 (states it explicitly).

### Q7. The item summary page still shows stock held in a deleted factory — 🐞 BUG-884
**Background:** The item summary page lists one catalog item's stock per factory and type and adds up a storage total. It loads the rows with "all live stock rows of this item" (`get_by_item`), which never looks at the factory row. Factories are soft-deleted (`is_deleted = True`, row stays).
**What happens today:** Stock rows of the item that sit in a soft-deleted factory are returned, so the page lists them and includes them in the item's storage total.
**Example:** "Bolt" has 5 in Factory 1 and 30 in Factory 9 "Old Plant", which was deleted. The item summary shows two stock lines and "storage total 35"; after the Q2 decision the stock page shows only 5 for the same item.
**Rules affected:** `get_by_item` R1, R3
**Suggested answer:** `bug — rows whose factory is soft-deleted are not returned (same principle and same fix pattern as BUG-882); the rows stay in the database`
**Answer:** bug — rows whose factory is soft-deleted are not returned (same principle and same fix pattern as BUG-882); the rows stay in the database (reviewer accepted suggestion, 2026-10-10)
**Resolution:** 🐞 BUG-884 (pattern `join-ignores-soft-deleted`, HR-4 third bullet). Logged as its own ID rather than as an extension of BUG-882: different method, different query, different API surface (item summary page instead of the stock page), so it is a separate code fix and needs its own xfail reason. `get_by_item` must not return a stock row whose factory has `factories.is_deleted = True`; an inactive-but-live factory still counts; the stock rows stay in the database untouched. Rules: `get_by_item` R1 (now limited to live factories), R1a (new, tagged), R1b (new, untagged — what already holds), R6 (narrowed).

### Q8. "Find the stock row of one factory / item / type" still finds it when the factory is deleted — ✅ intended
**Background:** `get_by_factory_item_type` returns the live stock row of one bucket. It is used for stock-availability checks in production batches, by ledger reconciliation, as the duplicate check when a stock row is created by hand, and inside "get or create the bucket" (`ensure_for_factory_item_type`). It never looks at the factory row. The database allows only one row per bucket, deleted factory or not.
**What happens today:** The row is returned even when its factory is soft-deleted, so the stock in a deleted factory still counts as available to those callers.
**Example:** Factory 9 is deleted while holding 30 bolts. A production batch that names Factory 9 as its source still sees "30 available".
**Rules affected:** `get_by_factory_item_type` R1 (and `ensure_for_factory_item_type` R1, which relies on it)
**Suggested answer:** `intended` — keep this lookup raw. If it hid the row, "get or create" and the duplicate check would no longer see an existing bucket and could run into the one-row-per-bucket constraint. The right place to refuse a deleted factory is the caller: stock postings and manual creation already do (BUG-662, BUG-715); the production-batch and reconciliation callers should get the same check in their own reviews.
**Answer:** intended (reviewer accepted suggestion, 2026-10-10)
**Resolution:** the lookup stays raw — a bucket row in a soft-deleted factory is still found. Rules: `get_by_factory_item_type` R1 ✅, R5 ✅ (new — states the accepted behavior explicitly so it gets a case), `ensure_for_factory_item_type` R1 ✅.

### Q9. Fetching one stock row by id still returns it when its factory is deleted — ✅ intended
**Background:** `get_by_id_and_workspace` fetches one stock row by its id for "show", "adjust" and "clear stock". It is a raw lookup by design: it even returns soft-deleted stock rows, and the manager decides what to do with them (HR-4 scope). It never looks at the factory row.
**What happens today:** A stock row whose factory is soft-deleted is returned like any other.
**Example:** Stock row 40 is 30 bolts in deleted Factory 9. It no longer appears on the stock page (Q2), but `GET /inventory/40/` still shows it and it can still be adjusted or cleared.
**Rules affected:** `get_by_id_and_workspace` R1, R4
**Suggested answer:** `intended` — the DAO lookup stays raw (HR-4 scope; "we keep the information"). Whether show / adjust / clear should answer 404 for stock in a deleted factory is a decision for the inventory manager spec (`get_inventory`, `update_inventory`, `delete_inventory`), not this DAO.
**Answer:** intended (reviewer accepted suggestion, 2026-10-10)
**Resolution:** the lookup stays raw — a stock row in a soft-deleted factory is still returned by id. Rules: `get_by_id_and_workspace` R1 ✅, R4 ✅, R5 ✅ (new — states the accepted behavior explicitly so it gets a case).

## Overview
`InventoryDAO` reads and maintains the stock snapshot table `inventory`: one row ("bucket") per workspace × catalog item × inventory type (STORAGE, DAMAGED, WASTE, SCRAP) × factory, holding the current quantity and average price. It serves the stock page (`GET /inventory/` list + total, `GET /inventory/stats/` KPIs, through `InventoryManager`), single-bucket lookups (stock availability checks in production batches and reconciliation), the item summary page (`get_by_item`), and "get or create the bucket and align it with the ledger" for every factory stock movement (`ensure_for_factory_item_type`, used by `inventory_movements` and `ProductionBatchManager`). Invariants it is meant to protect: workspace isolation, at most one row per bucket (soft-deleted rows included), and "the ledger wins" — a bucket's quantity / average price always equal the newest ledger entry before stock is moved. It never commits; writes are flushed.

**Callables:** 11 specified · 8 not specified
**Externals to mock:** none (`created_at`, ledger `performed_at` are Postgres `server_default now()`; `updated_at` is `onupdate now()`)
**Integration-only behavior:** none. (`limit >= 1` for the list is already enforced by `GET /inventory/`: `skip >= 0`, `1 <= limit <= 1000`.)

**Model facts (table `inventory`, class `app.models.inventory.Inventory`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` | — |
| `item_id` | Integer NOT NULL, FK `items.id` | — |
| `inventory_type` | Postgres enum `InventoryTypeEnum` NOT NULL (`STORAGE`, `DAMAGED`, `WASTE`, `SCRAP`; `app.models.enums.InventoryTypeEnum`, a `str` enum) | — |
| `factory_id` | Integer NOT NULL, FK `factories.id` | — |
| `qty` | Integer NOT NULL | `0` |
| `avg_price` | Numeric(15, 2), nullable (Python `Decimal` or `None`) | `NULL` |
| `note` | Text, nullable | `NULL` |
| `created_at` | DateTime NOT NULL | `now()` (server default) |
| `created_by`, `updated_by`, `deleted_by` | Integer nullable, FK `profiles.id` | `NULL` |
| `updated_at` | DateTime nullable | `NULL`; set to `now()` by the database whenever an UPDATE is issued |
| `is_active` | Boolean NOT NULL | `True` |
| `is_deleted` | Boolean NOT NULL | `False` |
| `deleted_at` | DateTime nullable | `NULL` |

- Unique constraint `uq_inventory_workspace_item_type_factory` on `(workspace_id, item_id, inventory_type, factory_id)` — it covers soft-deleted rows too.
- `Inventory.item` is loaded together with the row (joined); `inventory.item_name` / `inventory.item_unit` are read-only properties returning the item's `name` / `unit`.
- Soft delete of a stock row = `is_deleted = True` (with `is_active = False`, `deleted_at`, `deleted_by`). Every lookup here looks only at `is_deleted`; **`is_active` is never consulted by any method of this DAO.**
- Ledger table `inventory_ledger` (class `app.models.inventory_ledger.InventoryLedger`): NOT NULL columns `workspace_id`, `inventory_type`, `factory_id`, `item_id`, `transaction_type` (string ≤ 50), `quantity` (int), `qty_before` (int), `qty_after` (int); nullable `avg_price_before`, `avg_price_after` (Numeric(15, 2)), `unit_cost`, `total_cost`, `source_type`, `source_id`, `notes`, `performed_by`; `performed_at` DateTime NOT NULL, server default `now()`. The ledger has no soft-delete column.
- Related rows: `Item` (`app.models.item.Item`; NOT NULL `workspace_id`, `name`, `name_normalized`, `unit`; soft delete = `is_active = False` — the table has **no** `is_deleted` column, so "deactivated" and "deleted" are the same state for an item) and `Factory` (`app.models.factory.Factory`; NOT NULL `workspace_id`, `name`, `abbreviation`; has both `is_active` (default `True`) and `is_deleted` (default `False`); soft delete = `is_deleted = True` with `deleted_at` / `deleted_by`, `is_active` left as it was).

**Notes for the test designer:**
- Use the module singleton `inventory_dao` (`from app.dao.inventory import inventory_dao`). All parameters after `db` are keyword-only.
- Workspaces and profiles come from `tests/unit/factories.py` (`make_workspace`, `make_profile`). Build `Factory`, `Item`, `Inventory` and `InventoryLedger` rows directly (add + flush) with the NOT NULL columns listed above; for a ledger row any `transaction_type` string works (e.g. `"manual_add"`) and `quantity`, `qty_before` can be any integers — only `qty_after`, `avg_price_after`, `performed_at`, `id` and the four bucket columns matter to this DAO.
- **Ledger timestamps:** Postgres `now()` is the transaction start time and each test is one transaction, so ledger rows inserted without an explicit `performed_at` all share the same timestamp. Whenever a case needs a definite "newest" entry, set **explicit, distinct** `performed_at` values (e.g. `datetime(2026, 1, 1, 10, 0)`, `11:00`, …).
- **Ledger ties (BUG-664, `sync_snapshot_from_ledger` R12):** today's winner among rows sharing the newest `performed_at` is plan-dependent (physically first-inserted or highest TID). Required setup for a strict xfail: all rows share one `performed_at`; insert **B** (wrong values) first, then **C** (the intended latest, distinct values) with an **explicitly assigned `id` far above the table's sequence** (e.g. current max id + 1 000 000), then **A** (wrong values) with a normal sequence id. Only `ORDER BY performed_at DESC, id DESC` returns C. (Same recipe as the approved `inventory_movements` spec.)
- **Ordering (BUG-701, `list_filtered` R2):** the test database's collation is `English_United States.1252`, which already sorts "apple, Banana, cherry, Zulu" case-insensitively but breaks a case-only tie lowercase-first regardless of id (`bolt` before `Bolt`). So the intended order fails today only on a case-only tie where the row whose item name is upper-cased has the **lower inventory `id`**: create the stock row for item "Bolt" first, then the stock row for item "bolt" (two different items) — intended `["Bolt", "bolt"]`, today `["bolt", "Bolt"]`.
- **Soft-deleted factory (BUG-882, `_filtered_query` R11a and the `R1a` / `R5a` rules of its three callers):** build the factory row directly with `is_deleted=True` (optionally `deleted_at`, `deleted_by`); deleting a factory sets only `is_deleted` — `is_active` stays `True` — so use `is_active=True, is_deleted=True` for the deleted factory and `is_active=False, is_deleted=False` for the "inactive but live" factory of R11b. The stock row in the deleted factory must itself be live (`is_deleted=False`) with `qty > 0`, otherwise `_filtered_query` R2 / R7 already hide it and the case passes today. Always keep at least one stock row in a live factory of the same workspace in the same case, so the intended result is "only that row" rather than "nothing". Today's results are deterministic (the row is simply included), so these cases are **strict** xfail. The per-type case (`stats_filtered` R5a) compares `by_type_rows` as a set, or uses a single remaining type, so it does not depend on BUG-719. In every BUG-882 case all items must be **active** (`is_active=True`), so the case fails for BUG-882 alone and not also for BUG-883.
- **Removed catalog item (BUG-883, `_filtered_query` R11 and the `R1b` / `R5b` rules of its three callers):** build the item row directly with `is_active=False` (items have no `is_deleted` column — this is the item's only "removed" state; `Item.is_active` defaults to `True`). Its stock row must itself be live (`is_deleted=False`) with `qty > 0`, otherwise `_filtered_query` R2 / R7 already hide it and the case passes today. Always keep at least one stock row of an **active** item of the same workspace in the same case, so the intended result is "only that row" rather than "nothing". Every factory in a BUG-883 case must be **live** (`is_deleted=False`), so the case fails for BUG-883 alone and not also for BUG-882. Today's results are deterministic (the row is simply included), so these cases are **strict** xfail. Use clearly different item names ("Bolt" / "Old Gasket"; "Anvil" / "Bolt" for the `limit=1` case) so the list order does not depend on BUG-701, and make the search term match only the removed item (`"gasket"`). The per-type case (`stats_filtered` R5b) compares `by_type_rows` as a set, or uses a single remaining type, so it does not depend on BUG-719. R11c (the stock row and the item row are left untouched) passes today — no xfail.
- **Soft-deleted factory on the item summary lookup (BUG-884, `get_by_item` R1a):** same factory setup as BUG-882 (`is_active=True, is_deleted=True` for the deleted factory; `is_active=False, is_deleted=False` for the inactive-but-live factory of R1b). The stock row in the deleted factory must be live (`is_deleted=False`); its `qty` may be anything (`get_by_item` has no quantity filter — use `qty > 0` for clarity). Keep one stock row of the same item in a live factory in the main case so the intended result is "only that row"; compare results as sets of ids (`get_by_item` R5). Today's result is deterministic (the row is included) → **strict** xfail. The item is active in these cases.
- **`by_type` order (BUG-719, `stats_filtered` R6):** `inventory_type` is a native Postgres enum declared STORAGE, DAMAGED, WASTE, SCRAP; a sort-based GROUP BY already returns that order, so the intended-order case may XPASS today. Design the case to the intended order with a **non-strict** xfail; never weaken the assertion.
- **Database errors:** a failing statement aborts the Postgres transaction. Wrap calls expected to raise `DataError` (negative `skip` / `limit`) in `with db.begin_nested():` so the session stays usable. `ensure_for_factory_item_type` already runs its insert inside its own savepoint, so after its `IntegrityError` the session is usable without extra wrapping.
- **Race simulation (`ensure_for_factory_item_type` R9, R10):** the insert can only hit the unique constraint if both pre-insert lookups miss an existing row, which needs a second transaction. Simulate it in one session with `unittest.mock.patch.object(inventory_dao, "get_by_factory_item_type", return_value=None)` plus `patch.object(inventory_dao, "_get_any_by_factory_item_type", side_effect=...)` where the side effect returns `None` on the first call and delegates to the real method afterwards (R9), or `return_value=None` always (R10), with a row for the bucket already present.
- `updated_at`: assert `None` → not `None` (or unchanged), never "later than"; all `now()` values in one test are equal.
- Equality of `avg_price` / `estimated_value`: compare as `Decimal` values (`Decimal("6.00") == Decimal("6")`), not as strings.

## Not specified
- Inherited `BaseDAO` methods `get`, `get_multi`, `create`, `update`, `remove` — not overridden here; specified in `tests/unit/dao/base.spec.md` (5 callables). `create` is used by `ensure_for_factory_item_type` with a dict (base spec `create` R1, R3, R6).
- `InventoryDAO.get_by_workspace` (override) — dead code, to be removed (reviewer; Q3)
- `InventoryDAO.soft_delete` — dead code, to be removed (reviewer; Q4)
- `inventory_dao` — module-level singleton `InventoryDAO(Inventory)`, no logic
- (`get_by_item`'s `inventory_type` parameter — dead parameter, to be removed (reviewer; Q5). The method itself is specified.)

---

## `InventoryDAO._filtered_query(db, *, workspace_id, inventory_type=None, factory_id=None, item_id=None, search=None, include_zero_qty=False)`
**Shape:** helper
**Persistence:** pure (builds a query; executes nothing)
**Visibility:** internal (used by: `list_filtered`, `count_filtered`, `stats_filtered`)

**Purpose:** Select the stock rows of a workspace that match the stock page's filters.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `workspace_id` | int | workspace to restrict to (compared with `inventory.workspace_id`) |
| `inventory_type` | `InventoryTypeEnum` \| `None` | `None` = all types |
| `factory_id` | int \| `None` | `None` = all factories (see R5 for `0`) |
| `item_id` | int \| `None` | `None` = all items; any integer (including `0`) filters |
| `search` | str \| `None` | free text; `None`, `""` and whitespace-only = no search; otherwise trimmed of leading / trailing whitespace |
| `include_zero_qty` | bool, default `False` | `False` = only rows with `qty > 0` |

**Returns:** the filtered query over `Inventory` joined to its `Item` (not executed). The rules below describe which rows executing it yields, observable through the three public callers.

**Rules:**
- **R1.** Only rows with `inventory.workspace_id == workspace_id` are matched; a row of another workspace is never matched, whatever the other filters. The item's own workspace is not checked: a stock row of this workspace that points at an item of another workspace is matched (and searchable by that item's name).
- **R2.** Rows with `is_deleted = True` are never matched. `is_active` is not consulted: a row with `is_active = False`, `is_deleted = False` is matched.
- **R3.** With no optional filter and `include_zero_qty=False`, every live row of the workspace with `qty > 0` is matched.
- **R4.** Given an `inventory_type`, only rows of exactly that type are matched; `None` applies no type filter.
- **R5.** [BUG-880] (reviewer accepted suggestion) Given any integer `factory_id`, only rows with that `factory_id` are matched; `factory_id=0` matches no rows; only `None` applies no factory filter. A factory id that does not exist, or whose stock rows all belong to another workspace, matches nothing. *(Today: the filter is skipped for any falsy value, so `factory_id=0` behaves like `None` and matches the rows of every factory.)*
- **R6.** Given any integer `item_id` (compared with `is not None`), only rows with that `item_id` are matched; `item_id=0` matches no rows; `None` applies no item filter.
- **R7.** With `include_zero_qty=False`, rows with `qty = 0` **and rows with negative `qty`** are excluded (only `qty > 0` matches; boundary: `qty = 1` is matched, `qty = 0` is not). With `include_zero_qty=True`, rows of every quantity (positive, zero, negative) are matched.
- **R8.** `search=None`, `search=""` and a whitespace-only `search` (e.g. `"   "`) apply no search filter.
- **R9.** [BUG-702] Given a search with non-whitespace content, the text is trimmed and matched case-insensitively as a **literal** substring of the item's `name` or the item's `unit`; a row matches if either contains it (`" BOLT "` matches items named "bolt" and "Bolt"; `"PC"` matches every row whose item unit is "pcs"). `%`, `_` and `\` are matched literally (HR-8): `%` alone matches only rows whose item name or unit contains `%` (e.g. "50%"), `_` alone only those containing `_` (e.g. "_x"), `a\b` matches item name `a\b` and not `ab`. Inner whitespace is kept as typed. The stock row's `note`, the item's description / SKU and the factory name are not searched. *(Today: `%` and `_` are not escaped and act as SQL wildcards — `%` alone or `_` alone matches every row; `\` is the `ILIKE` escape character, so `a\b` matches item name "ab" and not "a\b".)*
- **R10.** All given filters combine with AND; the two search alternatives (name, unit) combine with OR.
- **R11.** [BUG-883] (reviewer accepted suggestion; Q6, supersedes Q1) A stock row whose catalog item has been removed (`items.is_active = False` — the only "removed" state an item has; `items` has no `is_deleted` column) should never be matched: not without an `item_id` filter, not when that item's own id is given as `item_id`, not by a `search` for that item's name or unit, and whatever the other filters (`inventory_type`, `factory_id`, `include_zero_qty=True`). Stock rows of live items (`is_active = True`) in the same factory are unaffected. Example: one live factory; item "Bolt" active with STORAGE qty 5, item "Old Gasket" with `is_active = False` and STORAGE qty 12, same workspace → with no filter only the Bolt row should match; with `item_id` = Old Gasket's id nothing should match; with `search="gasket"` nothing should match. *(Today: the item's `is_active` is never looked at — the query joins `items` only for the name / unit search and the ordering — so the Old Gasket row is matched exactly like the Bolt row: both rows match with no filter, and the Old Gasket row alone matches with `item_id` = Old Gasket's id and with `search="gasket"`.)* *(The factory half of the original R11 moved to R11a / R11b on 2026-10-10.)*
- **R11a.** [BUG-882] (reviewer decision 2026-10-10) A stock row whose factory is soft-deleted (`factories.is_deleted = True`) should never be matched: not without a `factory_id` filter, not when that factory's own id is given as `factory_id`, and whatever the other filters (`inventory_type`, `item_id`, `search`, `include_zero_qty=True`). Stock rows of the same item in a live factory are unaffected. Example: Factory A live, Factory B soft-deleted, same workspace; Bolt STORAGE qty 5 in A and Bolt STORAGE qty 30 in B → with no factory filter only the A row should match; with `factory_id` = B nothing should match. *(Today: the factory row is never looked at — the query has no join to `factories` — so the B row is matched exactly like the A row: both rows match with no factory filter, and the B row matches with `factory_id` = B.)*
- **R11b.** What does not hide a row (holds today and after the BUG-882 fix): a stock row whose factory is live but inactive (`factories.is_active = False`, `is_deleted = False`) is matched like any other — only the factory's `is_deleted` matters. And matching never changes anything: the stock row of a soft-deleted factory stays in the `inventory` table as it was (`is_deleted = False`, same `qty`, `avg_price`, `factory_id`), visible to a direct query of the table.
- **R11c.** What the BUG-883 exclusion does not touch (holds today and after the fix): matching never changes anything — the stock row of a removed item stays in the `inventory` table as it was (`is_deleted = False`, same `qty`, `avg_price`, `item_id`), visible to a direct query of the table, and the item row itself is not modified. The stock row's own `is_active` still plays no part (R2): a stock row with `inventory.is_active = False` whose **item** is active is matched.
- **R12.** Each matched stock row appears exactly once (the join to the item never duplicates a row).

**Errors:** none

**Side effects:** none

---

## `InventoryDAO.list_filtered(db, *, workspace_id, inventory_type=None, factory_id=None, item_id=None, search=None, include_zero_qty=False, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `InventoryManager.get_inventory_page` ← `InventoryService.get_inventory_page` ← `GET /inventory/`; the endpoint enforces `skip >= 0`, `1 <= limit <= 1000` and passes `limit=50` by default)

**Purpose:** One page of the stock list, with the stock page's filters applied.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `workspace_id`, `inventory_type`, `factory_id`, `item_id`, `search`, `include_zero_qty` | — | as in `_filtered_query` |
| `skip` | int, default `0` | rows to skip; not validated |
| `limit` | int, default `100` | max rows; not validated |

**Returns:** a `list` of `Inventory` instances (possibly empty), each with its `item` loaded (`item_name` / `item_unit` usable).

**Rules:**
- **R1.** Returns exactly the rows matched by `_filtered_query` R1–R12 for the given filters, paged. (Two parts do not hold today and are stated separately: the soft-deleted-factory exclusion, `_filtered_query` R11a → R1a; the removed-item exclusion, `_filtered_query` R11 → R1b.)
- **R1a.** [BUG-882] (reviewer decision 2026-10-10) A stock row whose factory is soft-deleted should not be in the returned list (`_filtered_query` R11a), and should not use up a place in the page: with Bolt qty 5 in live Factory A and Bolt qty 30 in soft-deleted Factory B, the list should hold only the A row; with `factory_id` = B it should be `[]`; with `limit=1` and no factory filter the single returned row should be the A row whichever of the two stock rows has the lower `id`. *(Today: both rows are returned — `len == 2` — ordered as R2; with `factory_id` = B the B row is returned; with `limit=1` the returned row is the B row whenever it sorts first.)*
- **R1b.** [BUG-883] (reviewer accepted suggestion; Q6) A stock row whose item has been removed (`items.is_active = False`) should not be in the returned list (`_filtered_query` R11), and should not use up a place in the page: with active item "Bolt" (STORAGE qty 5) and removed item "Old Gasket" (STORAGE qty 12) in one live factory, the list should hold only the Bolt row; with `item_id` = Old Gasket's id it should be `[]`; with `search="gasket"` it should be `[]`; and with a removed item named "Anvil" (qty 12) next to active "Bolt" (qty 5), `limit=1` with no other filter should return the Bolt row. *(Today: both rows are returned — `len == 2`, Bolt first, then Old Gasket (item-name order); with `item_id` = Old Gasket's id, and with `search="gasket"`, the Old Gasket row is returned (`len == 1`); in the Anvil / Bolt setup `limit=1` returns the Anvil row, because it sorts first by item name.)*
- **R2.** [BUG-701] Rows are ordered by the item's `name` case-insensitive ascending, then by the stock row's `id` ascending (HR-6). Example: stock rows whose items are named "Zulu", "apple", "Banana" come back "apple", "Banana", "Zulu"; two stock rows of the same item (two factories) come back lower `id` first; stock rows for two items named "Bolt" and "bolt" come back in stock-row `id` order, whichever case. *(Today: ordered by item `name` with the database's default collation, then `id` — a case-only difference is decided by the collation, not by `id`: on the test database "bolt" always precedes "Bolt".)*
- **R3.** `skip` and `limit` are applied after filtering and ordering, so consecutive windows (`skip=0, limit=2`, `skip=2, limit=2`, …) partition the matching rows with no repeats or gaps. With defaults, at most the first 100 rows are returned — given 101 matching rows, exactly 100.
- **R4.** `limit=0` returns `[]`; `skip` at or past the number of matching rows returns `[]`; a workspace with no matching rows, or an unknown workspace id, returns `[]`.
- **R5.** A negative `limit` or `skip` makes Postgres reject the query (see Errors); nothing is changed in the database.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInLimitClause`, `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInResultOffsetClause`, `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |

**Side effects:** none

---

## `InventoryDAO.count_filtered(db, *, workspace_id, inventory_type=None, factory_id=None, item_id=None, search=None, include_zero_qty=False)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `InventoryManager.get_inventory_page` ← `GET /inventory/`, as `total`)

**Purpose:** Number of stock rows the list would return across all pages for the same filters.

**Inputs:** as `_filtered_query`.

**Returns:** `int` ≥ 0.

**Rules:**
- **R1.** Returns the number of stock rows matched by `_filtered_query` R1–R12 for the given filters — equal to `len(list_filtered(...))` with the same filters and a `limit` large enough to return everything. It counts stock rows, not distinct items (one item stocked in two factories counts 2). (The soft-deleted-factory exclusion is stated separately as R1a, the removed-item exclusion as R1b.)
- **R1a.** [BUG-882] (reviewer decision 2026-10-10) Stock rows whose factory is soft-deleted should not be counted (`_filtered_query` R11a): with Bolt qty 5 in live Factory A and Bolt qty 30 in soft-deleted Factory B the count should be `1`; with `factory_id` = B it should be `0`. *(Today: `2` and `1` — the row of the deleted factory is counted.)*
- **R1b.** [BUG-883] (reviewer accepted suggestion; Q6) Stock rows whose item has been removed (`items.is_active = False`) should not be counted (`_filtered_query` R11): with active item "Bolt" (STORAGE qty 5) and removed item "Old Gasket" (STORAGE qty 12) in one live factory the count should be `1`; with `item_id` = Old Gasket's id it should be `0`; with `search="gasket"` it should be `0`. *(Today: `2`, `1` and `1` — the row of the removed item is counted.)*
- **R2.** Returns `0` (an `int`, not `None`) when nothing matches, including an empty or unknown workspace.

**Errors:** none

**Side effects:** none

---

## `InventoryDAO.stats_filtered(db, *, workspace_id, inventory_type=None, factory_id=None, item_id=None, search=None, include_zero_qty=False)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `InventoryManager.get_inventory_stats` ← `InventoryService.get_inventory_stats` ← `GET /inventory/stats/`)

**Purpose:** KPI figures for the stock rows matching the stock page's filters: row count, total quantity, estimated value, and a per-type breakdown.

**Inputs:** as `_filtered_query`.

**Returns:** a Python `tuple` of length 4: `(records, total_qty, estimated_value, by_type_rows)`.
- `records` — `int`.
- `total_qty` — `int`.
- `estimated_value` — `decimal.Decimal`.
- `by_type_rows` — a `list` of SQLAlchemy `sqlalchemy.engine.Row` objects (tuple-like, **not** `tuple` instances: `isinstance(row, tuple)` is `False`). Each row has length 3, supports indexing and unpacking: `row[0]` is an `InventoryTypeEnum` member, `row[1]` an `int` (distinct item count), `row[2]` an `int` (total quantity of that type).

**Rules:**
- **R1.** All four parts are computed over exactly the rows matched by `_filtered_query` R1–R12 for the given filters (so every filter, the workspace scope, the soft-delete exclusion and `include_zero_qty` apply to each part identically). (Two parts do not hold today: the soft-deleted-factory exclusion — R1a for the totals, R5a for the per-type breakdown — and the removed-item exclusion — R1b for the totals, R5b for the per-type breakdown.)
- **R1a.** [BUG-882] (reviewer decision 2026-10-10) Stock rows whose factory is soft-deleted should contribute nothing to `records`, `total_qty` or `estimated_value` (`_filtered_query` R11a). Example: Bolt STORAGE qty 5 @ 2.00 in live Factory A, Bolt STORAGE qty 30 @ 1.00 in soft-deleted Factory B → should be `records = 1`, `total_qty = 5`, `estimated_value == Decimal("10.00")`; with `factory_id` = B the result should be exactly the empty result of R7, `(0, 0, Decimal("0"), [])`. *(Today: `records = 2`, `total_qty = 35`, `estimated_value == Decimal("40.00")`; with `factory_id` = B: `records = 1`, `total_qty = 30`, `estimated_value == Decimal("30.00")`, `by_type_rows == [(STORAGE, 1, 30)]`.)*
- **R1b.** [BUG-883] (reviewer accepted suggestion; Q6) Stock rows whose item has been removed (`items.is_active = False`) should contribute nothing to `records`, `total_qty` or `estimated_value` (`_filtered_query` R11). Example (one live factory): active item "Bolt" STORAGE qty 5 @ 2.00, removed item "Old Gasket" STORAGE qty 12 @ 5.00 → should be `records = 1`, `total_qty = 5`, `estimated_value == Decimal("10.00")`; with `item_id` = Old Gasket's id (and likewise with `search="gasket"`) the result should be exactly the empty result of R7, `(0, 0, Decimal("0"), [])`. *(Today: `records = 2`, `total_qty = 17`, `estimated_value == Decimal("70.00")`; with `item_id` = Old Gasket's id or `search="gasket"`: `records = 1`, `total_qty = 12`, `estimated_value == Decimal("60.00")`, `by_type_rows == [(STORAGE, 1, 12)]`.)*
- **R2.** `records` equals `count_filtered` with the same filters.
- **R3.** `total_qty` is the sum of `qty` over the matched rows. With `include_zero_qty=True`, negative quantities reduce the sum (rows 5, 0, −2 → `3`).
- **R4.** `estimated_value` is the sum of `qty × avg_price` over the matched rows whose `avg_price` is not `NULL`; rows with `avg_price = NULL` contribute nothing (they still count in `records` and `total_qty`). Example: rows (qty 5 @ 2.50), (qty 4 @ 3.33), (qty 8 @ `NULL`) → `records = 3`, `total_qty = 17`, `estimated_value == Decimal("25.82")`. With `include_zero_qty=True` a negative-quantity row subtracts (qty −2 @ 1.00 → −2.00).
- **R5.** `by_type_rows` has one row per inventory type that has at least one matched row; types with no matched row are absent. For each type: `row[1]` = the number of **distinct `item_id`s** among the matched rows of that type (one item stocked as STORAGE in two factories counts `1`), `row[2]` = the sum of `qty` over those rows. Example: Bolt STORAGE Factory 1 qty 5, Bolt STORAGE Factory 2 qty 4, Nut STORAGE Factory 1 qty 1, Bolt SCRAP Factory 1 qty 3 → rows `(STORAGE, 2, 10)` and `(SCRAP, 1, 3)`. With `include_zero_qty=True`, a type whose only row has `qty = 0` appears as `(DAMAGED, 1, 0)`.
- **R5a.** [BUG-882] (reviewer decision 2026-10-10) Stock rows whose factory is soft-deleted should not appear in the per-type breakdown (`_filtered_query` R11a): they add nothing to a type's quantity, an item stocked only in a soft-deleted factory is not counted among the type's distinct items, and a type whose only matched rows sit in a soft-deleted factory is absent. Example (no factory filter): Bolt STORAGE qty 5 in live Factory A; in soft-deleted Factory B: Bolt STORAGE qty 30, Nut STORAGE qty 2, Bolt SCRAP qty 3 → `by_type_rows` should be exactly `[(STORAGE, 1, 5)]`. *(Today: the rows are `(STORAGE, 2, 37)` and `(SCRAP, 1, 3)` — compare as a set, the order is BUG-719.)*
- **R5b.** [BUG-883] (reviewer accepted suggestion; Q6) Stock rows whose item has been removed (`items.is_active = False`) should not appear in the per-type breakdown (`_filtered_query` R11): they add nothing to a type's quantity, a removed item is not counted among a type's distinct items, and a type whose only matched rows belong to removed items is absent. Example (one live factory, no filter): active item "Bolt" STORAGE qty 5; removed item "Old Gasket" STORAGE qty 12 and SCRAP qty 3 → `by_type_rows` should be exactly `[(STORAGE, 1, 5)]`. *(Today: the rows are `(STORAGE, 2, 17)` and `(SCRAP, 1, 3)` — compare as a set, the order is BUG-719.)*
- **R6.** [BUG-719] (reviewer accepted suggestion) `by_type_rows` is ordered by inventory type in enum declaration order: STORAGE, DAMAGED, WASTE, SCRAP (types without rows simply missing). *(Today: no ordering is requested; the order is whatever the database's grouping produces.)*
- **R7.** When nothing matches (empty or unknown workspace, filters matching no row), returns exactly `(0, 0, Decimal("0"), [])` — `records` and `total_qty` are `int` `0`, `estimated_value` is a `Decimal` equal to 0 (not `None`), `by_type_rows` is an empty `list`.
- **R8.** When rows match but every matched row has `avg_price = NULL`, `estimated_value` is a `Decimal` equal to 0 (not `None`).

**Errors:** none

**Side effects:** none

---

## `InventoryDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `InventoryManager.update_inventory`, `get_inventory`, `delete_inventory`)

**Purpose:** Fetch one stock row by id only if it belongs to the given workspace. (An override that behaves exactly like the inherited `BaseDAO.get_by_id_and_workspace` — base spec R1–R4.)

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `id` | int | equality on `inventory.id` |
| `workspace_id` | int | equality on `inventory.workspace_id` |

**Returns:** the `Inventory` instance, or `None`.

**Rules:**
- **R1.** Given a row with that id in that workspace, it is returned. ✅
- **R2.** Given the id exists but belongs to another workspace, returns `None`.
- **R3.** Given no row has that id, returns `None`.
- **R4.** A soft-deleted row (`is_deleted = True`) is still returned, and a row with `qty` 0 or negative is returned — this lookup is raw by design (HR-4 scope: the manager decides; its callers need deleted rows to answer "Cannot update a deleted inventory record"). ✅
- **R5.** ✅ (reviewer accepted suggestion; Q9) The related rows' state is not consulted: a stock row whose factory is soft-deleted (`factories.is_deleted = True`), or whose item has been removed (`items.is_active = False`), is returned like any other — although `list_filtered` no longer shows it (BUG-882, BUG-883). Whether show / adjust / clear should refuse such a row is the manager's decision. (Item half: best-practice default, delegated by reviewer — Q6 scope decision.)

**Errors:** none

**Side effects:** none

---

## `InventoryDAO.get_by_factory_item_type(db, *, factory_id, item_id, inventory_type, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `InventoryManager.create_inventory` (duplicate check), `LedgerManager.reconcile_inventory`, `ProductionBatchManager` (stock availability checks), and internally by `ensure_for_factory_item_type`)

**Purpose:** Find the live stock row of one bucket (workspace + factory + item + type).

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `factory_id` | int | equality on `factory_id` |
| `item_id` | int | equality on `item_id` |
| `inventory_type` | `InventoryTypeEnum` | equality on `inventory_type` |
| `workspace_id` | int | equality on `workspace_id` |

**Returns:** the `Inventory` instance, or `None`. (At most one row can exist per bucket — unique constraint.)

**Rules:**
- **R1.** Given a row with `is_deleted = False` whose `workspace_id`, `factory_id`, `item_id` and `inventory_type` all equal the arguments, it is returned. ✅
- **R2.** Returns `None` when no such row exists — including when a row matches three of the four keys but differs in the fourth (same factory / item / type in another workspace; another factory; another item; another type).
- **R3.** Given the bucket's row is soft-deleted (`is_deleted = True`), returns `None`.
- **R4.** `is_active` and `qty` are not consulted: a live row with `is_active = False`, or with `qty` 0 or negative, is returned.
- **R5.** ✅ (reviewer accepted suggestion; Q8) The related rows' state is not consulted: the bucket's live stock row is returned even when its factory is soft-deleted (`factories.is_deleted = True`) or its item has been removed (`items.is_active = False`) — the lookup is raw by design, so that "get or create the bucket" and the duplicate check still see the existing row; refusing a deleted factory / removed item is the caller's job. (Item half: best-practice default, delegated by reviewer — Q6 scope decision.)

**Errors:** none

**Side effects:** none

---

## `InventoryDAO._get_any_by_factory_item_type(db, *, factory_id, item_id, inventory_type, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** internal (used by: `ensure_for_factory_item_type`)

**Purpose:** Find the stock row of one bucket whether or not it is soft-deleted.

**Inputs:** as `get_by_factory_item_type`.

**Returns:** the `Inventory` instance, or `None`.

**Rules:**
- **R1.** Given a row whose `workspace_id`, `factory_id`, `item_id` and `inventory_type` all equal the arguments, it is returned — whether `is_deleted` is `False` or `True`.
- **R2.** Returns `None` when no row exists for the bucket, including when a row differs in any one of the four keys (another workspace, factory, item or type).

**Errors:** none

**Side effects:** none

---

## `InventoryDAO.sync_snapshot_from_ledger(db, *, inv, workspace_id, updated_by=None)`
**Shape:** update
**Persistence:** writes
**Visibility:** public by name; in practice internal (only caller: `ensure_for_factory_item_type`, which always passes the row's own workspace and a user id)

**Purpose:** Make a stock row's quantity and average price equal to the newest ledger entry of its bucket ("ledger wins").

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `inv` | `Inventory` | the stock row to align; not checked for workspace, `is_deleted` or `is_active` |
| `workspace_id` | int | workspace in which the ledger is searched (the argument is used, not `inv.workspace_id`) |
| `updated_by` | int \| `None`, default `None` | profile id to stamp when something changes; `None` = do not stamp |

**Returns:** the same `inv` instance; flushed if changed, never committed.

**Definition — the bucket's newest ledger entry:** among `inventory_ledger` rows with `workspace_id` = the `workspace_id` argument, `factory_id = inv.factory_id`, `item_id = inv.item_id`, `inventory_type = inv.inventory_type`, the one with the greatest `performed_at` (ties: R12). The **ledger values** are that entry's `qty_after` and `avg_price_after`; if the bucket has no ledger entry they are `0` and `None`.

**Rules:**
- **R1.** Given a newest ledger entry whose `qty_after` or `avg_price_after` differs from the row's `qty` / `avg_price`, the row's `qty` is set to `qty_after` and its `avg_price` to `avg_price_after`. Example: row (7, 5.00); entries at 09:00 (30, 7.00), 10:00 (10, 4.00), 11:00 (20, 6.00) → row becomes (20, 6.00).
- **R2.** `avg_price_after = NULL` on the newest entry is copied as-is: the row's `avg_price` becomes `None` (row (20, 6.00), newest entry (5, `NULL`) → row (5, `None`)).
- **R3.** Given the bucket has no ledger entry at all, the ledger values are `0` / `None`: a row holding (7, 5.00) becomes (0, `None`); a row already at (0, `None`) is left untouched (R6).
- **R4.** A difference in only one of the two values is enough: both columns are then written with the ledger values (row (20, 5.00), ledger (20, 6.00) → (20, 6.00); row (7, 6.00), ledger (20, 6.00) → (20, 6.00)).
- **R5.** When the row is changed (R1–R4) and `updated_by` is not `None`, the row's `updated_by` is set to it; `updated_at` becomes non-null (database `onupdate`). When the row is changed and `updated_by` is `None`, `updated_by` keeps its previous value (it is not cleared).
- **R6.** When the row's `qty` and `avg_price` already equal the ledger values (prices compared by numeric value: `Decimal("6.00")` equals `Decimal("6")`; `None` equals `None`), nothing is written: `qty`, `avg_price`, `updated_by` (even when an `updated_by` argument is given) and `updated_at` are unchanged (HR-9).
- **R7.** Only ledger entries of the row's own bucket are considered: entries of another inventory type, another factory, another item, or another workspace are ignored, even when they are newer.
- **R8.** No other column of the row is touched: `note`, `created_by`, `created_at`, `is_active`, `is_deleted`, `deleted_at`, `deleted_by` stay as they were.
- **R9.** The row's soft-delete state is not checked: a soft-deleted row is aligned exactly like a live one and stays soft-deleted.
- **R10.** The ledger is searched in the `workspace_id` argument, not in the row's own workspace: called with another workspace's id, the row is aligned to that workspace's ledger entries for the same factory / item / type ids (or to `0` / `None` if it has none). No caller does this.
- **R11.** The change is flushed (visible to queries in the same session) and not committed: rolling back restores the previous values. The returned object is the very instance passed in (`result is inv`).
- **R12.** [BUG-664] (reviewer accepted suggestion) When several ledger entries of the bucket share the greatest `performed_at`, the newest is the one with the greatest `id`. *(Today: ordered by `performed_at` only; among tied entries any one may be used. Fix belongs in `InventoryLedgerDAO.get_latest_entry`.)*

**Errors:** none

**Side effects:** at most one `inventory` row updated (`qty`, `avg_price`, optionally `updated_by`; `updated_at` by the database) and flushed; no ledger row is ever written; no commit.

---

## `InventoryDAO.ensure_for_factory_item_type(db, *, factory_id, item_id, inventory_type, workspace_id, created_by)`
**Shape:** create (get-or-create)
**Persistence:** writes
**Visibility:** public (used by: `inventory_movements` `_storage_out` / `_storage_in`, `ProductionBatchManager` (waste → DAMAGED stock))

**Purpose:** Return the live stock row of a bucket — reusing the live row, restoring a soft-deleted one, or creating an empty one — with its quantity and average price aligned to the ledger.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `factory_id` | int | bucket key; only the foreign key is enforced (factory must exist in some workspace) |
| `item_id` | int | bucket key; only the foreign key is enforced (item must exist in some workspace) |
| `inventory_type` | `InventoryTypeEnum` | bucket key |
| `workspace_id` | int | bucket key; workspace of the row and of the ledger lookup |
| `created_by` | int | the acting user's profile id: becomes `created_by` of a newly created row, and is the `updated_by` stamp on an existing row that the sync changes |

**Returns:** the bucket's `Inventory` row, live (`is_deleted = False`), flushed, not committed, with `qty` / `avg_price` equal to the bucket's ledger values (`sync_snapshot_from_ledger` definition).

**Rules:**
- **R1.** Given a live row exists for the bucket, that row is returned (same `id`); no row is created. Its `qty` / `avg_price` are aligned to the ledger exactly as `sync_snapshot_from_ledger` R1–R12, in `workspace_id`, with the stamp `updated_by = created_by` applied only when the alignment changes something (`sync_snapshot_from_ledger` R5, R6). Its own `created_by` is not changed. The factory's and the item's state are not consulted (`get_by_factory_item_type` R5): the live row of a bucket in a soft-deleted factory is reused the same way. ✅
- **R2.** A live row with `is_active = False` is treated as the live row of R1 and returned without changing `is_active`.
- **R3.** Given no live row but a soft-deleted row exists for the bucket, that row is restored exactly as `restore` R1–R2 (`is_deleted = False`, `is_active = True`, `deleted_at = None`, `deleted_by = None`), then aligned to the ledger as in R1, and returned (same `id`); no row is created; `note`, `created_by`, `created_at` are kept.
- **R4.** [BUG-881] (reviewer accepted suggestion) A row restored per R3 always gets `updated_by = created_by` (the acting user), whether or not the ledger alignment changes its quantity or price. *(Today: `updated_by` is written only when the alignment changes `qty` or `avg_price`; a restored row whose values already equal the ledger keeps its previous `updated_by` — e.g. `None` — although `updated_at` becomes non-null.)*
- **R5.** Given no row at all exists for the bucket, a new row is inserted with `workspace_id`, `inventory_type`, `factory_id`, `item_id` = the arguments, `qty = 0`, `avg_price = None`, `created_by` = the argument, `note = None`, `is_active = True`, `is_deleted = False`, `created_at` set by the database. If the bucket has no ledger entry, the row is returned like that, with `updated_by = None` and `updated_at = None`.
- **R6.** If the bucket has ledger entries but had no row (R5), the new row is aligned right away: `qty` / `avg_price` = the newest entry's `qty_after` / `avg_price_after`, and — when those differ from `0` / `None` — `updated_by = created_by` and `updated_at` non-null.
- **R7.** Only the exact bucket is reused: a row that differs in workspace, factory, item or inventory type is neither returned nor modified — a new row is created next to it. Calling the method twice with the same arguments returns the same row `id`, and exactly one row exists for the bucket afterwards.
- **R8.** The factory and the item are not checked against the workspace: an `item_id` or `factory_id` that belongs to another workspace is accepted and a row is created with `workspace_id` = the argument (callers are responsible for validating them — BUG-666 / BUG-710 are logged against the managers). An id that does not exist at all (`item_id`, `factory_id`, `workspace_id` or `created_by`) makes the insert fail with `sqlalchemy.exc.IntegrityError` (foreign key, see Errors); no row is created, and the session stays usable — rows written earlier in the same transaction are still there.
- **R9.** If the insert of R5 hits the bucket's unique constraint (another transaction created the row in between), no error is raised: the existing row is fetched, restored if it is soft-deleted (as R3), aligned to the ledger (as R1) and returned; no second row exists.
- **R10.** If the insert fails with an `IntegrityError` and no row can be found for the bucket afterwards, the original `IntegrityError` is re-raised.
- **R11.** Everything is flushed and nothing is committed: rolling back the session removes a created row and undoes a restore / alignment.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `item_id` does not exist | `sqlalchemy.exc.IntegrityError`; `.orig` is `psycopg2.errors.ForeignKeyViolation`, `.orig.pgcode == "23503"` | `… violates foreign key constraint "inventory_item_id_fkey"` |
| `factory_id` does not exist | same | `… "inventory_factory_id_fkey"` |
| `created_by` does not exist | same | `… "inventory_created_by_fkey"` |
| `workspace_id` does not exist | same | `… "inventory_workspace_id_fkey"` |
| unique-constraint violation and the bucket's row still cannot be found (R10; simulated only) | `sqlalchemy.exc.IntegrityError`; `.orig` is `psycopg2.errors.UniqueViolation`, `.orig.pgcode == "23505"` | `duplicate key value violates unique constraint "uq_inventory_workspace_item_type_factory"` |

**Side effects:** at most one `inventory` row created, or restored, and/or updated (`qty`, `avg_price`, `updated_by`); flushed; no ledger row written; no commit.

---

## `InventoryDAO.get_by_item(db, *, item_id, workspace_id)`
*(Source signature also has `inventory_type=None` — dead parameter, to be removed (reviewer), not specified: Q5. Never pass it in a test.)*
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ItemSummaryService._inventory_rows` — the item summary page; it skips rows with `qty <= 0` and sorts the result itself)

**Purpose:** All live stock rows of one catalog item in a workspace, across live factories and inventory types.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `item_id` | int | equality on `item_id` |
| `workspace_id` | int | equality on `workspace_id` |

**Returns:** a `list` of `Inventory` instances (possibly empty), in no guaranteed order.

**Rules:**
- **R1.** Returns every row with that `item_id` and `workspace_id` and `is_deleted = False` whose factory is live (`factories.is_deleted = False`) — all such factories, all four inventory types. (This part holds today; the exclusion of soft-deleted factories does not — R1a.)
- **R1a.** [BUG-884] (reviewer accepted suggestion; Q7) A stock row whose factory is soft-deleted (`factories.is_deleted = True`) should not be returned, whatever its inventory type or quantity. Example: item "Bolt" has STORAGE qty 5 in live Factory A and STORAGE qty 30 in soft-deleted Factory B, same workspace → the result should hold exactly the A row (`len == 1`). When the item's only live stock rows sit in soft-deleted factories (only the B row exists), the result should be `[]`. *(Today: the factory row is never looked at — the query has no join to `factories` — so the B row is returned like the A row: the result holds both rows (`len == 2`, ids `{A row, B row}`), and with only the B row it is `[B row]`.)*
- **R1b.** What does not hide a row (holds today and after the BUG-884 fix): a stock row whose factory is live but inactive (`factories.is_active = False`, `is_deleted = False`) is returned like any other — only the factory's `is_deleted` matters. And the call never changes anything: the stock row of a soft-deleted factory stays in the `inventory` table as it was (`is_deleted = False`, same `qty`, `avg_price`, `factory_id`).
- **R2.** Rows with `qty = 0` or negative `qty` are included (no quantity filter).
- **R3.** Soft-deleted stock rows (`inventory.is_deleted = True`) are excluded; the stock row's `is_active` is not consulted (a live row with `is_active = False` is included). The **item's** own `is_active` is not consulted either: called with the id of a removed item (`items.is_active = False`), its live stock rows are returned as for an active item (best-practice default, delegated by reviewer — Q6 scope decision: BUG-883 covers the stock page's list / count / statistics / search, not this single-item lookup).
- **R4.** Rows of the same `item_id` in another workspace, and rows of other items, are never returned.
- **R5.** There is no `skip` / `limit`: all matching rows are returned. No sort order is applied — tests must compare the result as a set of ids, not as a sequence.
- **R6.** Returns `[]` when the item has no live stock row in the workspace (unknown item id, unknown workspace id, or only soft-deleted stock rows). (The fourth empty case — only rows in soft-deleted factories — is R1a and does not hold today.)

**Errors:** none

**Side effects:** none

---

## `InventoryDAO.restore(db, *, db_obj)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public by name; in practice internal (only caller: `ensure_for_factory_item_type`)

**Purpose:** Bring a soft-deleted stock row back to life.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db_obj` | `Inventory` | the row to restore; not checked for workspace or current state |

**Returns:** the same `db_obj` instance, flushed, not committed.

**Rules:**
- **R1.** Given a soft-deleted row (`is_deleted = True`, `is_active = False`, `deleted_at` and `deleted_by` set), after the call `is_active = True`, `is_deleted = False`, `deleted_at = None`, `deleted_by = None`; the row is found again by `get_by_factory_item_type`.
- **R2.** No other column is changed by the method: `qty`, `avg_price`, `note`, `created_by`, `created_at`, `updated_by` keep their values (no user is stamped — the method has no user argument; see `ensure_for_factory_item_type` R4). `updated_at` becomes non-null because the database sets it on the UPDATE.
- **R3.** Given a row that is already live and active, nothing changes and no error is raised (`updated_at` stays as it was). Given a live row with `is_active = False`, `is_active` becomes `True`.
- **R4.** The change is flushed (visible to queries in the same session) and not committed: rolling back makes the row soft-deleted again. The returned object is the very instance passed in.

**Errors:** none

**Side effects:** one `inventory` row updated (`is_active`, `is_deleted`, `deleted_at`, `deleted_by`; `updated_at` by the database) and flushed; no commit.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 33–40 | inner join to `Item`; always filter `workspace_id` and `is_deleted == False`; no `is_active`, no item state check (`items.is_active` ignored — BUG-883); no join to `factories`, so no factory state check (BUG-882) | `_filtered_query` R1, R2, R3, R11, R11a, R11b, R11c, R12; `list_filtered` R1a, R1b; `count_filtered` R1a, R1b; `stats_filtered` R1a, R1b, R5a, R5b |
| 41 | `if inventory_type:` — member (always truthy) / `None` | `_filtered_query` R4 |
| 43 | `if factory_id:` — truthy / `None` / `0` (falsy → no filter, BUG-880) | `_filtered_query` R5 |
| 45 | `if item_id is not None:` — given (incl. `0`) / `None` | `_filtered_query` R6 |
| 47 | `if not include_zero_qty:` → `qty > 0` / no quantity filter | `_filtered_query` R7 |
| 49 | `if search:` — `None` / `""` skip | `_filtered_query` R8 |
| 50–51 | `term = search.strip()`; `if term:` — whitespace-only skips | `_filtered_query` R8, R9 |
| 52–57 | `ILIKE` on `Item.name` OR `Item.unit`, unescaped (BUG-702) | `_filtered_query` R9, R10 |
| 70–71 | defaults `skip=0`, `limit=100` | `list_filtered` R3 |
| 83 | `ORDER BY items.name ASC, inventory.id ASC` (collation-dependent case handling, BUG-701) | `list_filtered` R2 |
| 84–86 | offset / limit after filter + order; `limit=0`; negative values | `list_filtered` R3, R4, R5, Errors |
| 100–108 | `.count()` over the filtered query; none → `0` | `count_filtered` R1, R2 |
| 121–130 | same filtered query for all parts; `records = count` | `stats_filtered` R1, R2 |
| 131–134 | `coalesce(sum(qty), 0)`, `coalesce(sum(qty * avg_price), 0)` — NULL `avg_price` skipped; no rows → 0 | `stats_filtered` R3, R4, R7, R8 |
| 135–143 | per-type `count(distinct item_id)`, `sum(qty)`, `GROUP BY inventory_type`, no `ORDER BY` (BUG-719); zero / one / many types | `stats_filtered` R5, R6, R7 |
| 144 | `int(records)`, `int(total_qty or 0)`, raw `estimated_value`, raw rows | `stats_filtered` Returns, R7 |
| 167–170 | `id` AND `workspace_id`; no `is_deleted` filter; no factory / item state check; found / other workspace / missing | `get_by_id_and_workspace` R1, R2, R3, R4, R5 |
| 177–183 | four-key match AND `is_deleted == False`; found / key differs / soft-deleted; `is_active`, `qty`, factory / item state ignored | `get_by_factory_item_type` R1, R2, R3, R4, R5 |
| 190–195 | four-key match, no `is_deleted` filter; found (live or deleted) / none | `_get_any_by_factory_item_type` R1, R2 |
| 206–212 (+ `inventory_ledger.py` 165–175) | newest ledger entry of the bucket in the `workspace_id` argument; `ORDER BY performed_at DESC` only (BUG-664) | `sync_snapshot_from_ledger` Definition, R7, R10, R12 |
| 213–218 | `if latest:` ledger values / `else:` `0`, `None` | `sync_snapshot_from_ledger` R1, R2, R3 |
| 220 | `inv.qty != ledger_qty or inv.avg_price != ledger_avg` — qty differs / price differs / both / neither | `sync_snapshot_from_ledger` R1, R4, R6 |
| 221–222 | both columns assigned; nothing else | `sync_snapshot_from_ledger` R4, R8, R9 |
| 223 | `if updated_by is not None:` stamp / keep | `sync_snapshot_from_ledger` R5 |
| 225–227 | add + flush only when changed; return same instance | `sync_snapshot_from_ledger` R6, R11 |
| 240–250 | `if active:` live row found → sync and return | `ensure_for_factory_item_type` R1, R2 |
| 252–259 | `if existing:` a row exists that the live lookup did not return | `ensure_for_factory_item_type` R3 |
| 260–261 | `if existing.is_deleted:` → restore. (The `False` side needs a row that became live between the two lookups — a concurrent transaction; not reachable in a single session, no rule.) | `ensure_for_factory_item_type` R3, R4 |
| 262–264 | sync after restore with `updated_by=created_by` (stamp only if values change — BUG-881) | `ensure_for_factory_item_type` R3, R4 |
| 266–277 (+ `base.py` 76–84) | create payload (qty 0, avg `None`, `created_by`) inserted inside a savepoint | `ensure_for_factory_item_type` R5, R7, R8 |
| 278–285 | `except IntegrityError:` re-lookup of the bucket | `ensure_for_factory_item_type` R8, R9, R10 |
| 286–287 | `if not row: raise` (FK violation, or row vanished) | `ensure_for_factory_item_type` R8, R10, Errors |
| 288–289 | `if row.is_deleted:` restore / already live | `ensure_for_factory_item_type` R9 |
| 291–293 | final sync of the created (or raced) row | `ensure_for_factory_item_type` R5, R6, R9 |
| — | no commit anywhere | `ensure_for_factory_item_type` R11 |
| 300–304 | `workspace_id` AND `item_id` AND `is_deleted == False`; no quantity filter; no join to `factories` (BUG-884) or `items`, so no factory / item state check | `get_by_item` R1, R1a, R1b, R2, R3, R4 |
| 307 | `.all()` — no order, no limit; none / one / many | `get_by_item` R5, R6 |
| 322–325 | four fields reset unconditionally (already-live row → no change) | `restore` R1, R2, R3 |
| 326–328 | add + flush, return same instance, no commit | `restore` R2, R4 |
