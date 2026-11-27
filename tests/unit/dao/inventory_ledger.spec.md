# Spec — `app/dao/inventory_ledger.py`

> **Status:** APPROVED
> **Source commit:** e48a092

> **Review note 2026-10-10:** the reviewer accepted every suggested answer as written, after the answers had first been applied to the rules as provisional defaults. House-rule lines stand (BUG-640, BUG-641, BUG-664). P1, P2 confirmed (BUG-655 existing, BUG-885). Q1 → `remove` (dead code), Q2 → `remove` (the override only; dead code). Q3, Q4, Q5 → `intended`. No rule was changed, renumbered, added or removed by this pass — only the provisional markers were replaced; no provisional default remains.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically
> All three lines stand (reviewer, 2026-10-10). All three defects were already recorded when the ledger manager and the stock-movement code were reviewed; the code to fix lives in this DAO, so the existing IDs are reused (no new ID).

- **HR-6** `get_by_workspace` R7a, `get_by_transaction_type` R4a, `get_by_date_range` R5a, `get_by_performer` R4a — the four ledger lists are ordered by `performed_at` (newest first) only; entries with the same timestamp come back in no fixed order, and paging can repeat or skip them. Intended: `performed_at` newest first, then `id` descending, before `skip`/`limit`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-640 (existing, logged against `app/managers/ledger_manager.py`; the fix is in these four `InventoryLedgerDAO` list methods) — no new ID. Rules: `get_by_workspace` R7a, `get_by_transaction_type` R4a, `get_by_date_range` R5a, `get_by_performer` R4a.
- **HR-6** `calculate_balance` R4a — the "latest entry" (top-1) of a bucket is picked by `performed_at` only; on a tie an arbitrary entry decides the balance. Intended: latest = greatest `performed_at`, ties broken by greatest `id`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-641 (existing, logged against `app/managers/ledger_manager.py`, fix in `InventoryLedgerDAO.calculate_balance`) — no new ID. Rules: `calculate_balance` R4a.
- **HR-6** `get_latest_entry` R3 — same top-1 tie problem in the lookup that every stock movement uses to re-sync the stock row. Intended: latest = greatest `performed_at`, ties broken by greatest `id`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-664 (existing, logged against `app/managers/inventory_movements.py`, fix in `InventoryLedgerDAO.get_latest_entry`; BUG-803 is the same fix seen from purchase returns) — no new ID. Rules: `get_latest_entry` R3.

### Precedent matches — all confirmed by the reviewer (2026-10-10)

### P1. The ledger balance of a bucket crashes as soon as the bucket has history — 🐞 BUG-655 (existing)
**Background:** The "balance" of one factory / item / type is read from its newest ledger entry. The inventory ledger stores, per entry, the quantity after the movement (`qty_after`) and the average price after it (`avg_price_after`). The balance code was copied from the machine ledger and reads a column `value_after` that the inventory ledger does not have.
**What happens today:** For a bucket with no ledger entry the balance is `(0, 0.00)`. For any bucket with at least one entry the lookup raises `AttributeError`; `GET /ledgers/inventory/balance/` and `POST /ledgers/inventory/reconcile/` answer 500.
**Example:** Factory 1 holds Bolt / STORAGE with one ledger entry "after: 20 @ 6.00". Asking for its balance gives a 500 error instead of "20, value 120.00".
**Rules affected:** `calculate_balance` R2, R4, R5
**Answer:** bug — per BUG-655 (already ruled by the reviewer in the ledger manager spec, Q12): balance = `(qty_after, qty_after × avg_price_after)` of the latest entry; an empty `avg_price_after` gives value `Decimal("0.00")` (reviewer accepted suggestion, 2026-10-10)
**Resolution:** referenced existing BUG-655 (no new ID). Rules: `calculate_balance` R2, R4, R5.

### P2. Factory filter `0` / item filter `0` mean "all" in the ledger lists — 🐞 BUG-885
**Background:** The ledger list accepts an optional factory filter and an optional item filter. Both are skipped whenever the value is "falsy", which includes the number `0`. `GET /ledgers/inventory/` accepts any integer for `factory_id` and `item_id`. For the stock list the reviewer already ruled that only "not given" skips a filter (BUG-880).
**What happens today:** `factory_id=0` (or `item_id=0`) returns the entries of every factory (every item) of the workspace instead of nothing.
**Example:** A client with no factory selected sends `GET /ledgers/inventory/?factory_id=0`. Instead of an empty list it receives the 100 newest ledger entries of all factories.
**Rules affected:** `get_by_workspace` R4a, R5a; `get_by_transaction_type` R3a; `get_by_date_range` R4a
**Answer:** bug — per BUG-880 precedent (also BUG-501 / BUG-707): only "not given" (`None`) skips the factory / item filter; `0` filters and matches no rows (reviewer accepted suggestion, 2026-10-10)
**Resolution:** 🐞 BUG-885 (pattern `falsy-zero-treated-as-missing`). Rules: `get_by_workspace` R4a, R5a; `get_by_transaction_type` R3a; `get_by_date_range` R4a.

### New questions

### Q1. "Ledger entries of one order" can never work and nobody calls it — 🗑️ remove (dead code)
**Background:** `get_by_order` is meant to return the ledger entries linked to an order. It filters on a column `order_id`, which the inventory ledger table does not have (entries are linked through `source_type` / `source_id` instead). Nothing in the application or its tests calls the method.
**What happens today:** Any call would raise `AttributeError` ("type object 'InventoryLedger' has no attribute 'order_id'") before a query is sent. No API request reaches it.
**Example:** No endpoint, background job or script lists ledger entries by order through this method; deleting it changes nothing a user can see.
**Rules affected:** `get_by_order` (all)
**Suggested answer:** `remove` — it is unreachable and broken; if "entries of one order" is ever needed it must be written against `source_type` / `source_id`.
**Answer:** remove (reviewer accepted suggestion, 2026-10-10)
**Resolution:** not specified; listed under **Not specified** and in `docs/testing/dead-code-removal-checklist.md` (`app/dao/inventory_ledger.py:105`). Not a bug — no BUG ID.

### Q2. The DAO's own "get one entry by id" is never called — 🗑️ remove (dead code)
**Background:** `InventoryLedgerDAO.get_by_id_and_workspace` re-implements, line for line, the generic lookup every DAO already inherits ("one row by id, only inside this workspace"). Nothing in the application or its tests asks the inventory ledger for a single entry by id — there is no "show one ledger entry" endpoint.
**What happens today:** The method can never run in production. Deleting the override leaves the identical inherited method in place.
**Example:** No API request reaches it; breaking it has no visible effect.
**Rules affected:** `get_by_id_and_workspace` (all)
**Suggested answer:** `remove` (the override only; the inherited generic method stays and is already tested in the base DAO spec).
**Answer:** remove — the override only (reviewer accepted suggestion, 2026-10-10)
**Resolution:** the override is not specified (the inherited `BaseDAO.get_by_id_and_workspace` stays); listed under **Not specified** and in `docs/testing/dead-code-removal-checklist.md` (`app/dao/inventory_ledger.py:44`). Not a bug — no BUG ID.

### Q3. Ledger lists still show the entries of a deleted factory — ✅ intended
**Background:** Factories are soft-deleted (`is_deleted = True`, the row stays). Every ledger entry points at its factory. The ledger lists never look at the factory row. On 2026-10-10 the reviewer ruled for the stock page: "Soft-deleted things should not show up. We keep the information, but it is not used for anything counted" (BUG-882). The ledger is different in kind: it is not a count of what exists now but the append-only history of what happened; each entry records "quantity before → quantity after".
**What happens today:** Entries booked in a soft-deleted factory are returned by the ledger list (`GET /ledgers/inventory/`), the item movement report, the item summary's "recent activity" and the per-user transaction list — with no factory filter and when that factory's id is given as the filter.
**Example:** Factory 9 "Old Plant" received 30 bolts in March and was deleted in June. The ledger page still lists "March: +30 bolts, factory 9". If such entries were hidden, the history of those 30 bolts (who booked them, when, at what cost) would no longer be visible anywhere, and a later transfer out of Factory 9 into Factory 1 would show only its "arrived in Factory 1" half.
**Rules affected:** `get_by_workspace` R11; `get_by_transaction_type` R6; `get_by_date_range` R7; `get_by_performer` R6
**Suggested answer:** `intended` — a ledger is history, not stock: nothing is counted from these lists, and the reviewer's own sentence says "we keep the information". Hiding entries would leave gaps in the audit trail. (If the page should label such entries "deleted factory", that is a display decision outside this DAO.)
**Answer:** intended (reviewer accepted suggestion, 2026-10-10)
**Resolution:** entries of a soft-deleted factory stay listed — the ledger is history, not a count. Rules: `get_by_workspace` R11 ✅; `get_by_transaction_type` R6 ✅; `get_by_date_range` R7 ✅; `get_by_performer` R6 ✅.

### Q4. Ledger lists still show the entries of an item removed from the catalog — ✅ intended
**Background:** Catalog items are removed by setting `is_active = False`; the row stays, and this is the only "deleted" state an item has. Every ledger entry points at its item. The ledger lists never look at the item row. For the stock page the reviewer ruled that stock of a removed item is hidden and not counted (BUG-883). As in Q3, the ledger is history, not a count.
**What happens today:** Entries of a removed item are returned by the ledger list, the item movement report, the per-user transaction list and — when that item's own summary page is opened — its "recent activity".
**Example:** Item "Old Gasket" was bought (+12) and partly used (−4) and then removed from the catalog. The ledger page still shows both movements; filtering the ledger by that item's id still shows them.
**Rules affected:** `get_by_workspace` R12; `get_by_transaction_type` R6; `get_by_date_range` R7; `get_by_performer` R6
**Suggested answer:** `intended` — same reasoning as Q3: past movements really happened and the purchase cost behind them is still real; history must stay complete. Whether the summary page of a removed item is shown at all is the item-summary service's decision, not this DAO's.
**Answer:** intended (reviewer accepted suggestion, 2026-10-10)
**Resolution:** entries of a removed item stay listed — the ledger is history, not a count. Rules: `get_by_workspace` R12 ✅; `get_by_transaction_type` R6 ✅; `get_by_date_range` R7 ✅; `get_by_performer` R6 ✅.

### Q5. The single-bucket lookups (balance, latest entry, "already posted?") ignore a deleted factory / removed item — ✅ intended
**Background:** Three lookups work on explicitly named things, not on lists: the ledger balance of one factory / item / type, the newest ledger entry of that bucket (used before every stock movement to re-sync the stock row — "the ledger wins"), and the guard "was this source document line already posted to the ledger?" that prevents double posting. None of them looks at the factory row or the item row. For the stock DAO the reviewer already accepted that single-row lookups stay raw (inventory DAO spec Q8, Q9).
**What happens today:** A bucket in a soft-deleted factory, or of a removed item, is answered exactly like any other: its balance and newest entry are returned, and an entry posted there still counts as "already posted".
**Example:** Factory 9 is deleted while its ledger says "Bolt / STORAGE: 30". `get_latest_entry` for that bucket still returns the "after: 30" entry; a second attempt to post the same receive line that created it is still recognised as a duplicate.
**Rules affected:** `calculate_balance` R5; `get_latest_entry` R6; `exists_for_source` R5
**Suggested answer:** `intended` — keep these lookups raw, as in inventory DAO Q8 / Q9. If the "already posted?" guard ignored such entries, a document could be posted twice; if the newest-entry lookup ignored them, the stock row would be reset to 0. Refusing to work on a deleted factory / removed item is the caller's job (stock postings already do: BUG-662, BUG-715).
**Answer:** intended (reviewer accepted suggestion, 2026-10-10)
**Resolution:** the lookups stay raw. Rules: `calculate_balance` R5 ✅; `get_latest_entry` R6 ✅; `exists_for_source` R5 ✅.

## Overview
`InventoryLedgerDAO` reads the unified inventory ledger table `inventory_ledger`: the append-only history of every stock movement, one row ("entry") per movement of one bucket (workspace × factory × catalog item × inventory type STORAGE / DAMAGED / WASTE / SCRAP), each recording the quantity and average price before and after. It serves the ledger page and reports (`LedgerManager.get_inventory_ledger`, `get_item_movement_summary`, `get_transactions_by_user`), the item summary's recent activity (`ItemSummaryService._recent_activity`), the per-bucket "current state from the ledger" lookups (`calculate_balance` for balance / reconcile, `get_latest_entry` for the "ledger wins" stock-row sync in `InventoryDAO.sync_snapshot_from_ledger` and for reconcile), and the idempotency guard `exists_for_source` used before stock is posted from purchase receives, purchase returns and transfer orders. Invariants it is meant to protect: workspace isolation (every query filters `workspace_id`), and one unambiguous "latest entry" per bucket. Every method specified here only reads; entries are written by managers through the inherited `create` (always with a dict — see Not specified).

**Callables:** 7 specified · 8 not specified
**Externals to mock:** none (`performed_at` is a Postgres `server_default now()`; tests set it explicitly)
**Integration-only behavior:** none. (`skip >= 0` and `limit <= 100` are enforced by `GET /ledgers/inventory/`; `limit >= 1` is not — BUG-642, logged against the endpoint.)

**Model facts (table `inventory_ledger`, class `app.models.inventory_ledger.InventoryLedger`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence `inventory_ledger_id_seq` |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` (ON DELETE CASCADE) | — |
| `inventory_type` | Postgres enum NOT NULL (`STORAGE`, `DAMAGED`, `WASTE`, `SCRAP`; `app.models.enums.InventoryTypeEnum`, a `str` enum) | — |
| `factory_id` | Integer NOT NULL, FK `factories.id` (ON DELETE RESTRICT) | — |
| `item_id` | Integer NOT NULL, FK `items.id` (ON DELETE RESTRICT) | — |
| `transaction_type` | String(50) NOT NULL — plain text, no enum, no check constraint | — |
| `quantity`, `qty_before`, `qty_after` | Integer NOT NULL | — |
| `unit_cost`, `total_cost`, `avg_price_before`, `avg_price_after` | Numeric(15, 2), nullable (Python `Decimal` or `None`) | `NULL` |
| `source_type` | String(50), nullable | `NULL` |
| `source_id` | Integer, nullable (no foreign key) | `NULL` |
| `transfer_source_type`, `transfer_destination_type` | String(50), nullable | `NULL` |
| `transfer_source_id`, `transfer_destination_id` | Integer, nullable | `NULL` |
| `notes` | Text, nullable | `NULL` |
| `performed_by` | Integer, nullable, FK `profiles.id` (ON DELETE SET NULL) | `NULL` |
| `performed_at` | DateTime (no time zone; Python naive `datetime`) NOT NULL | `now()` (server default) |

- The table has **no** `is_deleted`, `is_active`, `value_after` or `order_id` column and no unique constraint besides the primary key.
- Related rows: `Factory` (`app.models.factory.Factory`; NOT NULL `workspace_id`, `name`, `abbreviation`; `is_active` default `True`, `is_deleted` default `False`; soft delete = `is_deleted = True`, `is_active` left as it was) and `Item` (`app.models.item.Item`; NOT NULL `workspace_id`, `name`, `name_normalized`, `unit`; removed = `is_active = False`; the table has no `is_deleted` column).
- No method of this DAO joins or reads `factories`, `items` or `profiles`.

**Known neighbouring bugs (not rules of this spec):** BUG-680 — the "already posted?" check (`exists_for_source`) is not backed by a unique index (fix is a database index, logged against `po_receive_inventory`). BUG-341 / BUG-646 / BUG-648 — how `LedgerManager` chooses between the date, type and plain list (logged against the manager; their fix may merge the three list methods here).

**Notes for the test designer:**
- Use the module singleton: `from app.dao.inventory_ledger import inventory_ledger_dao`. All parameters after `db` are keyword-only.
- Workspaces and profiles come from `tests/unit/factories.py` (`make_workspace`, `make_profile`). Build `Factory`, `Item` and `InventoryLedger` rows directly (add + flush). Minimum ledger row: `workspace_id`, `factory_id`, `item_id`, `inventory_type`, `transaction_type` (e.g. `"manual_add"`), `quantity`, `qty_before`, `qty_after`. Factory and item must exist (foreign keys); they need not belong to the same workspace as the entry (not checked anywhere).
- Every query is workspace-scoped, so a fresh workspace per test isolates the test from any other row in the table.
- **Timestamps:** Postgres `now()` is the transaction start time and each test is one transaction, so entries inserted without an explicit `performed_at` all share one timestamp. Always set **explicit** `performed_at` values: distinct ones (e.g. `datetime(2026, 1, 1, 9, 0)`, `10:00`, `11:00`) whenever a case needs a definite order, identical ones only in the tie cases. Insert rows in an order different from their time order (e.g. 09:00, 11:00, 10:00) so that "newest first" cannot pass by accident.
- **Tie recipe (deterministic strict xfail; verified on the test database under four different query plans).** All three rows share one `performed_at` and all filter columns. Insert in this order, flushing after each: **B** (normal sequence id), then **C** with an **explicitly assigned `id` far above the table** — `max(current max id of inventory_ledger, last_value of inventory_ledger_id_seq) + 1_000_000` (an explicit id does not advance the sequence) — then **A** (normal sequence id, so `A.id = B.id + 1`). Then `C.id > A.id > B.id`.
  - *Latest entry* (`get_latest_entry` R3, `calculate_balance` R4a): intended winner **C**. Today the winner is **B** (plain / bitmap scan: first inserted) or **A** (backward index scan: last inserted) — never C. Give the three rows different `qty_after` (B 15, C 10, A 99) and assert on the returned row's `id` and `qty_after`.
  - *Lists* (BUG-640 rules): intended order `[C, A, B]` (`id` descending). Today `[B, C, A]` or `[A, C, B]` — never `[C, A, B]`.
  - Same recipe as the approved `inventory` / `inventory_movements` specs (case INV-SY-17). An additional, equally deterministic proof is the emitted SQL (statement recorder as in `test_ledger_manager.py`): today the ledger SELECT's `ORDER BY` is `inventory_ledger.performed_at DESC` (followed by `LIMIT`); intended it ends with `inventory_ledger.id DESC`.
- **BUG-885 cases (`0` filters):** the workspace must hold at least one entry, so that the intended result `[]` differs from today's (all entries of the workspace, newest first). Today's result is deterministic → strict xfail. Use distinct `performed_at` values so BUG-640 plays no part.
- **BUG-655 cases (`calculate_balance`):** today every call for a bucket with at least one entry raises `AttributeError("'InventoryLedger' object has no attribute 'value_after'")` (a plain Python error after the SELECT; the session stays usable) → strict xfail. R1 and R3 (no entry in the bucket) pass today.
- **Soft-deleted factory / removed item (Q3–Q5, reviewer: `intended`):** build the factory with `is_active=True, is_deleted=True` and the item with `is_active=False`. These cases pass today — no xfail. Keep one entry in a live factory / of an active item in the same case so the assertion is "both are returned".
- **Database errors:** a failing statement aborts the Postgres transaction. Wrap calls expected to raise `DataError` (negative `skip` / `limit`) in `with db.begin_nested():`. The `ArgumentError` of `get_by_date_range` R3 is raised in Python before any SQL is sent — no wrapping needed.
- Compare `Decimal` results by value (`Decimal("120.00") == Decimal("120")`), and types with `isinstance`.
- Lists return ORM instances; compare lists as `[row.id for row in result]`.
- For the 101-entry cases give each entry a distinct `performed_at` (e.g. one minute apart).

## Not specified
- Inherited `BaseDAO` methods `get`, `get_multi`, `create`, `update`, `remove` — not overridden here; specified in `tests/unit/dao/base.spec.md` (5 callables). Facts a caller needs: managers always call `create` with a **dict** that includes `workspace_id` (and `performed_by`); the schema `InventoryLedgerCreate` has no `workspace_id` field, so `create` with that schema fails with `IntegrityError` (NOT NULL `workspace_id`; base spec `create` R6, R8). Nothing in the application calls `update`, `remove`, `get` or `get_multi` on this DAO — the ledger's "immutable" status is a convention, not enforced here.
- `InventoryLedgerDAO.get_by_id_and_workspace` (override identical to the inherited one) — dead code, to be removed (reviewer; Q2). The inherited `BaseDAO.get_by_id_and_workspace` stays (base spec R1–R5).
- `InventoryLedgerDAO.get_by_order` — dead code, to be removed (reviewer; Q1)
- `inventory_ledger_dao` — module-level singleton `InventoryLedgerDAO(InventoryLedger)`, no logic

---

## `InventoryLedgerDAO.get_by_workspace(db, *, workspace_id, inventory_type=None, factory_id=None, item_id=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (override of `BaseDAO.get_by_workspace`, adding the three filters and an order. Used by: `LedgerManager.get_inventory_ledger` when neither a full date range nor a transaction type is given ← `GET /ledgers/inventory/`; `ItemSummaryService._recent_activity`, which passes only `item_id`, `skip=0` and a `limit` of at least 5)

**Purpose:** One page of a workspace's ledger entries, newest first, optionally narrowed to an inventory type, a factory and / or an item.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `workspace_id` | int | equality on `inventory_ledger.workspace_id`; always applied |
| `inventory_type` | `InventoryTypeEnum` \| `None` | `None` = all types |
| `factory_id` | int \| `None` | `None` = all factories (see R4a for `0`) |
| `item_id` | int \| `None` | `None` = all items (see R5a for `0`) |
| `skip` | int, default `0` | rows to skip; not validated |
| `limit` | int, default `100` | max rows; not validated |

**Returns:** a `list` of `InventoryLedger` instances (possibly empty).

**Rules:**
- **R1.** Only entries with `workspace_id` equal to the argument are returned; an entry of another workspace is never returned, whatever the other filters (also when its `factory_id` / `item_id` are given as filters). An unknown workspace id returns `[]`.
- **R2.** With no optional filter, entries of every inventory type, factory, item, transaction type and performer of the workspace are returned (subject to R8).
- **R3.** Given an `inventory_type`, only entries of exactly that type are returned; `None` applies no type filter.
- **R4.** Given a non-zero `factory_id`, only entries with that `factory_id` are returned; `None` applies no factory filter. A factory id with no entries in this workspace (unknown id, negative id, or a factory whose entries all belong to another workspace) returns `[]`.
- **R4a.** [BUG-885] (reviewer accepted suggestion; P2) `factory_id=0` filters like any other integer and returns `[]`. *(Today: `0` is treated like `None` — no factory filter — so the entries of every factory are returned.)*
- **R5.** Given a non-zero `item_id`, only entries with that `item_id` are returned; `None` applies no item filter. An item id with no entries in this workspace returns `[]`.
- **R5a.** [BUG-885] (reviewer accepted suggestion; P2) `item_id=0` filters like any other integer and returns `[]`. *(Today: `0` is treated like `None` — no item filter — so the entries of every item are returned.)*
- **R6.** All given filters combine with AND (e.g. `inventory_type=STORAGE` + `factory_id=F1` + `item_id=I1` returns only entries matching all three).
- **R7.** Entries are ordered by `performed_at` descending (newest first), independent of `id` and of insertion order. Example: entries inserted with times 09:00, 11:00, 10:00 come back 11:00, 10:00, 09:00.
- **R7a.** [BUG-640] Entries with the same `performed_at` are ordered by `id` descending (HR-6). *(Today: no second sort key; tied entries come back in a plan-dependent order — see the tie recipe.)*
- **R8.** `skip` and `limit` are applied after filtering and ordering: with entries at 09:00, 10:00, 11:00, `skip=1, limit=1` returns exactly the 10:00 entry; consecutive windows partition the result with no repeats or gaps. With defaults at most the 100 newest entries are returned — given 101 matching entries, exactly 100, and the oldest one is missing.
- **R9.** `limit=0` returns `[]`; `skip` at or past the number of matching entries returns `[]`.
- **R10.** A negative `limit` or `skip` makes Postgres reject the query (see Errors).
- **R11.** ✅ (reviewer accepted suggestion; Q3) The factory's state is not consulted: entries whose factory is soft-deleted (`factories.is_deleted = True`) are returned like any other, with no factory filter and with that factory's id as `factory_id`.
- **R12.** ✅ (reviewer accepted suggestion; Q4) The item's state is not consulted: entries whose item has been removed (`items.is_active = False`) are returned like any other, with no item filter and with that item's id as `item_id`.
- **R13.** The call changes nothing in the database.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInLimitClause`, `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInResultOffsetClause`, `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |

**Side effects:** none

---

## `InventoryLedgerDAO.get_by_transaction_type(db, *, transaction_type, workspace_id, inventory_type=None, factory_id=None, item_id=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `LedgerManager.get_inventory_ledger` when a non-empty transaction type is given and no full date range ← `GET /ledgers/inventory/`)

**Purpose:** One page of a workspace's ledger entries of one transaction type, newest first, with the same optional filters as `get_by_workspace`.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `transaction_type` | str | equality on `inventory_ledger.transaction_type`; not validated, not trimmed |
| `workspace_id`, `inventory_type`, `factory_id`, `item_id`, `skip`, `limit` | — | as in `get_by_workspace` |

**Returns:** a `list` of `InventoryLedger` instances (possibly empty).

**Rules:**
- **R1.** Only entries of the workspace (as `get_by_workspace` R1) whose `transaction_type` equals the argument **exactly** are returned: the comparison is case-sensitive, nothing is trimmed, and `%` / `_` are ordinary characters. With entries of type `"manual_add"` and `"sale"`: `"manual_add"` returns only the `manual_add` entries; `"MANUAL_ADD"`, `"manual_add "` (trailing space), `"manual%"` and an unknown type each return `[]`.
- **R2.** `transaction_type=""` and `transaction_type=None` return `[]` (no entry has an empty or missing type); no error is raised.
- **R3.** The optional filters narrow the result exactly as `get_by_workspace` R3, R4, R5 and combine with the transaction type and each other with AND (`get_by_workspace` R6).
- **R3a.** [BUG-885] (reviewer accepted suggestion; P2) `factory_id=0` returns `[]`, and `item_id=0` returns `[]`. *(Today: `0` is treated like `None`, so all entries of that transaction type in the workspace are returned.)*
- **R4.** Entries are ordered by `performed_at` descending (as `get_by_workspace` R7).
- **R4a.** [BUG-640] Entries with the same `performed_at` are ordered by `id` descending (HR-6). *(Today: no second sort key — as `get_by_workspace` R7a.)*
- **R5.** Paging and its errors are exactly as `get_by_workspace` R8, R9, R10 (default: the 100 newest entries of that type — given 101, exactly 100).
- **R6.** ✅ (reviewer accepted suggestion; Q3, Q4) The factory's and the item's state are not consulted: entries of a soft-deleted factory or of a removed item are returned like any other.

**Errors:** as `get_by_workspace` (negative `limit` / `skip`).

**Side effects:** none

---

## `InventoryLedgerDAO.get_by_date_range(db, *, workspace_id, start_date, end_date, inventory_type=None, factory_id=None, item_id=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `LedgerManager.get_inventory_ledger` when both dates are given ← `GET /ledgers/inventory/`; `LedgerManager.get_item_movement_summary` when both dates are given — it passes no other filter and the default `skip` / `limit`)

**Purpose:** One page of a workspace's ledger entries performed within a time window, newest first, with the same optional filters as `get_by_workspace`.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | as in `get_by_workspace` |
| `start_date` | naive `datetime` | lower bound, **inclusive**; required (see R3 for `None`) |
| `end_date` | naive `datetime` | upper bound, **inclusive**; required (see R3 for `None`) |
| `inventory_type`, `factory_id`, `item_id`, `skip`, `limit` | — | as in `get_by_workspace` |

(Time-zone-aware datetimes are not specified — do not use them in tests.)

**Returns:** a `list` of `InventoryLedger` instances (possibly empty).

**Rules:**
- **R1.** Only entries of the workspace (as `get_by_workspace` R1) with `start_date <= performed_at <= end_date` are returned; both bounds are inclusive and compared to the microsecond. Example — entries at 09:00:00, 10:00:00 and 11:00:00 on 2026-01-01: range 09:00:00 … 11:00:00 returns all three; range 09:00:00.000001 … 10:59:59.999999 returns only the 10:00 entry.
- **R2.** `start_date == end_date` returns exactly the entries performed at that instant (range 10:00:00 … 10:00:00 returns the 10:00 entry). `start_date` later than `end_date` returns `[]` (no error).
- **R3.** `start_date=None` or `end_date=None` raises `sqlalchemy.exc.ArgumentError` before any query is sent (see Errors); nothing is read or changed. (No caller does this: both callers call the method only when both dates are given.)
- **R4.** The optional filters narrow the result exactly as `get_by_workspace` R3, R4, R5 and combine with the date window and each other with AND (`get_by_workspace` R6).
- **R4a.** [BUG-885] (reviewer accepted suggestion; P2) `factory_id=0` returns `[]`, and `item_id=0` returns `[]`. *(Today: `0` is treated like `None`, so all entries of the workspace inside the window are returned.)*
- **R5.** Entries are ordered by `performed_at` descending (as `get_by_workspace` R7).
- **R5a.** [BUG-640] Entries with the same `performed_at` are ordered by `id` descending (HR-6). *(Today: no second sort key — as `get_by_workspace` R7a.)*
- **R6.** Paging and its errors are exactly as `get_by_workspace` R8, R9, R10 (default: the 100 newest entries inside the window — given 101, exactly 100).
- **R7.** ✅ (reviewer accepted suggestion; Q3, Q4) The factory's and the item's state are not consulted: entries of a soft-deleted factory or of a removed item are returned like any other.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `start_date` or `end_date` is `None` | `sqlalchemy.exc.ArgumentError` | starts with `Only '=', '!=', 'is_()', 'is_not()', 'is_distinct_from()', 'is_not_distinct_from()' operators can be used with None/True/False` |
| negative `limit` / `skip` | as `get_by_workspace` | as `get_by_workspace` |

**Side effects:** none

---

## `InventoryLedgerDAO.get_by_performer(db, *, performed_by, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (only caller: `LedgerManager.get_transactions_by_user` ← `GET /ledgers/reports/user-transactions/{user_id}/`; that report crashes today before it reaches this method — BUG-645, logged against the manager — and is intended to call it)

**Purpose:** One page of the ledger entries one user performed in a workspace, newest first.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `performed_by` | int | equality on `inventory_ledger.performed_by` (a profile id); existence not checked |
| `workspace_id` | int | equality on `inventory_ledger.workspace_id` |
| `skip`, `limit` | int | as in `get_by_workspace` |

**Returns:** a `list` of `InventoryLedger` instances (possibly empty).

**Rules:**
- **R1.** Returns the entries with that `workspace_id` and that `performed_by`, of every inventory type, factory, item and transaction type. Entries of the workspace performed by another user, and entries with no performer (`performed_by` `NULL`), are not returned.
- **R2.** Entries the same user performed in another workspace are never returned. A profile id with no entries in the workspace (unknown id, `0`) returns `[]`.
- **R3.** `performed_by=None` returns the workspace's entries that have **no** performer (`performed_by` `NULL`) and no others. (Not reachable from the API: the user id is a required path parameter.)
- **R4.** Entries are ordered by `performed_at` descending (as `get_by_workspace` R7).
- **R4a.** [BUG-640] Entries with the same `performed_at` are ordered by `id` descending (HR-6). *(Today: no second sort key — as `get_by_workspace` R7a.)*
- **R5.** Paging and its errors are exactly as `get_by_workspace` R8, R9, R10 (default: the user's 100 newest entries — given 101, exactly 100).
- **R6.** ✅ (reviewer accepted suggestion; Q3, Q4) The factory's and the item's state are not consulted: entries of a soft-deleted factory or of a removed item are returned like any other. The performer's own profile state is not consulted either.

**Errors:** as `get_by_workspace` (negative `limit` / `skip`).

**Side effects:** none

---

## `InventoryLedgerDAO.calculate_balance(db, *, factory_id, item_id, inventory_type, workspace_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `LedgerManager.get_inventory_balance` ← `GET /ledgers/inventory/balance/`; `LedgerManager.reconcile_inventory` ← `POST /ledgers/inventory/reconcile/`)

**Purpose:** The current quantity and total value of one bucket according to its latest ledger entry.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `factory_id` | int | equality on `factory_id`; existence not checked |
| `item_id` | int | equality on `item_id`; existence not checked |
| `inventory_type` | `InventoryTypeEnum` | equality on `inventory_type`; required — each type is its own bucket |
| `workspace_id` | int | equality on `workspace_id` |

**Returns:** a Python `tuple` of length 2: `(quantity, total_value)` — `quantity` is an `int`, `total_value` a `decimal.Decimal`.

**Definition — the bucket's latest entry:** among `inventory_ledger` rows whose `workspace_id`, `factory_id`, `item_id` and `inventory_type` all equal the arguments, the one with the greatest `performed_at` (ties: R4a).

**Rules:**
- **R1.** Given the bucket has no ledger entry, returns exactly `(0, Decimal("0.00"))`: a `tuple`, `quantity` the `int` `0`, `total_value` a `Decimal` equal to 0 (`str(total_value) == "0.00"`).
- **R2.** [BUG-655] (reviewer accepted suggestion; P1) Given the bucket has at least one entry, returns `(qty_after, qty_after × avg_price_after)` of the latest entry — `quantity` an `int`, `total_value` a `Decimal`. When the latest entry's `avg_price_after` is `NULL`, `total_value` is `Decimal("0.00")` and `quantity` is still its `qty_after`. Examples: single entry (`qty_after` 20, `avg_price_after` 6.00) → `(20, Decimal("120.00"))`; single entry (5, `NULL`) → `(5, Decimal("0.00"))`; single entry (0, 6.00) → `quantity == 0` and `total_value == Decimal("0")`. *(Today: raises `AttributeError` — `'InventoryLedger' object has no attribute 'value_after'` — for every bucket that has at least one entry.)*
- **R3.** Only entries of the exact bucket count: when the only entries that exist differ from the arguments in workspace, factory, item or inventory type (each one alone), the result is the empty result of R1.
- **R4.** [BUG-655] The balance comes from the entry with the greatest `performed_at`, independent of `id` and insertion order. Example: entries inserted as 09:00 (30 @ 7.00), 11:00 (20 @ 6.00), 10:00 (10 @ 4.00) → `(20, Decimal("120.00"))`; a newer entry of another bucket (other type / factory / item / workspace) does not change it. *(Today: `AttributeError`, as R2.)*
- **R4a.** [BUG-641] When several entries of the bucket share the greatest `performed_at`, the latest is the one with the greatest `id` (HR-6). With the tie recipe (B: 15, C: 10, A: 99, all @ 2.00) the result is `(10, Decimal("20.00"))`. *(Today: ordered by `performed_at` only — and the call raises `AttributeError` anyway, BUG-655.)*
- **R5.** [BUG-655] ✅ (reviewer accepted suggestion; Q5) The factory's and the item's state are not consulted: the balance of a bucket in a soft-deleted factory, or of a removed item, is returned exactly as R2. *(Today: `AttributeError`, as R2; a bucket without entries in a soft-deleted factory already returns R1.)*
- **R6.** The call changes nothing in the database.

**Errors:** none intended. *(Today, until BUG-655 is fixed: `AttributeError` — `'InventoryLedger' object has no attribute 'value_after'` — whenever the bucket has at least one entry.)*

**Side effects:** none

---

## `InventoryLedgerDAO.get_latest_entry(db, *, factory_id, item_id, inventory_type, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `InventoryDAO.sync_snapshot_from_ledger` — the "ledger wins" re-sync of a stock row before every stock movement; `LedgerManager.reconcile_inventory` — to read the latest average price)

**Purpose:** The most recent ledger entry of one bucket.

**Inputs:** as `calculate_balance`.

**Returns:** the `InventoryLedger` instance, or `None`.

**Rules:**
- **R1.** Given the bucket has no ledger entry, returns `None`.
- **R2.** Given entries with distinct `performed_at`, returns the one with the greatest `performed_at`, independent of `id` and insertion order. Example: entries inserted as 09:00 (`qty_after` 30), 11:00 (20), 10:00 (10) → the 11:00 entry (`qty_after == 20`). A single entry is returned as it is.
- **R3.** [BUG-664] When several entries of the bucket share the greatest `performed_at`, the one with the greatest `id` is returned (HR-6) — i.e. the entry written last. With the tie recipe (B, then C with the explicit high id, then A) the result is C. An older entry (smaller `performed_at`) never wins, whatever its `id`. *(Today: ordered by `performed_at` descending only, limited to one row; among tied entries the winner depends on the query plan — the first-inserted row B or the last-inserted row A — and is never chosen by `id`, so C is not returned.)*
- **R4.** Only entries of the exact bucket are considered: an entry that differs in workspace, factory, item or inventory type (each one alone) is never returned, even when it is newer; when only such entries exist the result is `None`.
- **R5.** The returned object is the full ledger row: `id`, `qty_after` (`int`) and `avg_price_after` (`Decimal`, or `None` when the column is `NULL`) are readable as stored.
- **R6.** ✅ (reviewer accepted suggestion; Q5) The factory's and the item's state are not consulted: the latest entry of a bucket in a soft-deleted factory, or of a removed item, is returned like any other.
- **R7.** The call changes nothing in the database.

**Errors:** none

**Side effects:** none

---

## `InventoryLedgerDAO.exists_for_source(db, *, workspace_id, source_type, source_id)`
**Shape:** helper (existence check)
**Persistence:** reads
**Visibility:** public (used by: `po_receive_inventory._storage_ledger_exists`, `po_return_inventory._storage_ledger_exists`, `to_inventory._line_already_posted` — the "already posted?" guards; all pass a non-empty string and an integer line id)

**Purpose:** Tell whether the workspace's ledger already holds an entry for one source document line (idempotency guard).

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | equality on `workspace_id` |
| `source_type` | str | equality on `source_type`; exact, case-sensitive, not validated |
| `source_id` | int | equality on `source_id` |

**Returns:** a `bool` (`True` or `False`, never `None` or a row).

**Rules:**
- **R1.** Returns `True` when at least one entry of the workspace has that `source_type` and that `source_id` — whatever its inventory type, factory, item, transaction type, quantity or performer, and whether one or several such entries exist.
- **R2.** Returns `False` when no such entry exists: an empty ledger, or entries that match only two of the three keys (same source in another workspace; same `source_id` with another `source_type`; same `source_type` with another `source_id`).
- **R3.** `source_type` is compared exactly and case-sensitively: with an entry `("po", 5)`, `source_type="PO"` returns `False`.
- **R4.** `None` is compared as "is empty": `source_id=None` matches only entries whose `source_id` is `NULL` (with entry `("po", NULL)` → `True`; with only `("po", 5)` → `False`), and `source_type=None, source_id=None` returns `True` as soon as the workspace has any entry with neither a source type nor a source id. (No caller passes `None`.)
- **R5.** ✅ (reviewer accepted suggestion; Q5) The factory's and the item's state are not consulted: an entry booked in a soft-deleted factory, or for a removed item, counts.
- **R6.** The call changes nothing in the database.

**Errors:** none

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 33–35 | always filter `workspace_id`; no join to `factories` / `items` | `get_by_workspace` R1, R2, R11, R12 |
| 36 | `if inventory_type:` — member (always truthy) / `None` | `get_by_workspace` R3 |
| 38 | `if factory_id:` — truthy / `None` / `0` (falsy → no filter, BUG-885) | `get_by_workspace` R4, R4a |
| 40 | `if item_id:` — truthy / `None` / `0` (falsy → no filter, BUG-885) | `get_by_workspace` R5, R5a, R6 |
| 42 | `ORDER BY performed_at DESC` only (BUG-640) | `get_by_workspace` R7, R7a |
| 30, 42 | defaults `skip=0`, `limit=100`; offset / limit after filter + order; `limit=0`; negative values; empty / one / many | `get_by_workspace` R8, R9, R10, R13, Errors |
| 44–51 | `id` AND `workspace_id` (override identical to base) | not specified — dead code (Q2) |
| 61–64 | always filter `workspace_id` and `transaction_type ==` (exact; `""` / `None` match nothing) | `get_by_transaction_type` R1, R2 |
| 65, 67, 69 | `if inventory_type:` / `if factory_id:` / `if item_id:` (falsy `0`, BUG-885) | `get_by_transaction_type` R3, R3a |
| 72 | `ORDER BY performed_at DESC` only (BUG-640) | `get_by_transaction_type` R4, R4a |
| 58, 73–75 | defaults, offset / limit, negative values | `get_by_transaction_type` R5 |
| 61–64 | no join to `factories` / `items` | `get_by_transaction_type` R6 |
| 87–91 | always filter `workspace_id`, `performed_at >= start_date`, `performed_at <= end_date` (inclusive; equal bounds; reversed bounds; `None` → `ArgumentError`) | `get_by_date_range` R1, R2, R3, Errors |
| 92, 94, 96 | `if inventory_type:` / `if factory_id:` / `if item_id:` (falsy `0`, BUG-885) | `get_by_date_range` R4, R4a |
| 99 | `ORDER BY performed_at DESC` only (BUG-640) | `get_by_date_range` R5, R5a |
| 84, 100–102 | defaults, offset / limit, negative values | `get_by_date_range` R6 |
| 87–91 | no join to `factories` / `items` | `get_by_date_range` R7 |
| 105–117 | filter on non-existent `InventoryLedger.order_id` → `AttributeError`; no caller | not specified — dead code (Q1) |
| 126–129 | `workspace_id` AND `performed_by ==` (`None` → `IS NULL`); no other filter, no join | `get_by_performer` R1, R2, R3, R6 |
| 130 | `ORDER BY performed_at DESC` only (BUG-640) | `get_by_performer` R4, R4a |
| 121, 131–133 | defaults, offset / limit, negative values | `get_by_performer` R5 |
| 147–152 | four-key bucket match; no join | `calculate_balance` Definition, R3, R5 |
| 153–154 | `ORDER BY performed_at DESC`, first row (BUG-641) | `calculate_balance` R4, R4a |
| 156 | `if entry:` found / not found | `calculate_balance` R1, R2 |
| 157 | `entry.value_after` (column does not exist → `AttributeError`, BUG-655); `or Decimal('0.00')` fallback (intended: `NULL` average price → `0.00`) | `calculate_balance` R2, R4, R5, Errors |
| 158 | no entry → `(0, Decimal('0.00'))` | `calculate_balance` R1, R3, R6 |
| 167–172 | four-key bucket match; no join; found / other bucket / none | `get_latest_entry` R1, R4, R5, R6, R7 |
| 173–174 | `ORDER BY performed_at DESC`, first row; ties unresolved (BUG-664) | `get_latest_entry` R2, R3 |
| 188–192 | `workspace_id` AND `source_type ==` AND `source_id ==` (`None` → `IS NULL`); no join | `exists_for_source` R1, R2, R3, R4, R5 |
| 193–194 | `.first() is not None` → `bool`; none / one / many | `exists_for_source` R1, R2, R6 |
