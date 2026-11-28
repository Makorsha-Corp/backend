# Fix brief: dao-inventory_ledger

> **Round 2 (2026-11-28): scope widened.** This unit now also covers the inventory half of
> BUG-641, BUG-664 and BUG-803 (the "latest entry" tie-break in `calculate_balance` and
> `get_latest_entry`). See §7 "Scope change (round 2, 2026-11-28)" at the end. Where an earlier
> section said to leave those two methods' ordering alone, §7 replaces it; those lines are updated below.

## 1. Unit

| | |
|---|---|
| Slug | `dao-inventory_ledger` |
| Source file | `app/dao/inventory_ledger.py` |
| Worktree | `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-inventory_ledger` |
| Branch | `bugfix/dao-inventory_ledger` (from `origin/main`) |
| Risk | `normal` (stock and stock value, but the intended behaviour, including the value formula and the empty-price case, is fully settled by the bug rows and the reviewed spec; no owner question needed) |

## 2. Bugs

### BUG-655: Inventory balance and inventory reconcile crash whenever the bucket has history
- **Pattern:** `wrong-column-copied-from-sibling`
- **Where:** logged against `app/managers/ledger_manager.py` (`get_inventory_balance`, `reconcile_inventory`), **fix in** `app/dao/inventory_ledger.py` `InventoryLedgerDAO.calculate_balance`. Reached through `GET /ledgers/inventory/balance/` and `POST /ledgers/inventory/reconcile/`.
- **Today:** `calculate_balance` was copied from the machine ledger DAO and still reads `value_after`, a column the inventory ledger does not have; any bucket with at least one ledger entry raises `AttributeError` (500).
- **Intended:** Balance = latest entry's `(qty_after, qty_after × avg_price_after)`; empty `avg_price_after` → value `Decimal("0.00")` (reviewer accepted suggestion, 2026-10-10).
- **Example:** Factory 1 has received 50 × "Bolt" into STORAGE; the latest entry says "after: 50 @ 5.00". The balance endpoint answers 500 instead of "50 units, 250.00 taka"; reconcile answers 500 and the stock row is never corrected.

### BUG-885: Inventory ledger lists treat `factory_id=0` / `item_id=0` as "no filter"
- **Pattern:** `falsy-zero-treated-as-missing`
- **Where:** `InventoryLedgerDAO.get_by_workspace`, `get_by_transaction_type`, `get_by_date_range`; reached through `GET /ledgers/inventory/` (and the item summary's recent activity, which calls `get_by_workspace` with `item_id`).
- **Today:** `if factory_id:` / `if item_id:` — the value `0` applies no filter, so the ledger entries of every factory (every item) of the workspace are returned.
- **Intended:** Only `None` means "no filter"; `factory_id=0` and `item_id=0` filter like any other integer and match no rows (per BUG-880 precedent; reviewer accepted suggestion, 2026-10-10).
- **Example:** A client with no factory selected sends `GET /ledgers/inventory/?factory_id=0`. Instead of an empty list it receives the 100 newest ledger entries of all factories.

## 3. Intended behaviour (spec rules, copied)

Facts for the whole file:
- Table `inventory_ledger` (`app.models.inventory_ledger.InventoryLedger`): the append-only history of stock movements, one row ("entry") per movement of one **bucket** = workspace × factory × item × inventory type (`STORAGE` / `DAMAGED` / `WASTE` / `SCRAP`).
- Columns: `id` PK; `workspace_id`, `factory_id`, `item_id` Integer NOT NULL; `inventory_type` Postgres enum NOT NULL (`InventoryTypeEnum`, a `str` enum; every member is truthy); `transaction_type` String(50) NOT NULL; `quantity`, `qty_before`, `qty_after` Integer NOT NULL; `unit_cost`, `total_cost`, `avg_price_before`, `avg_price_after` Numeric(15, 2) **nullable** (Python `Decimal` or `None`); `source_type`, `source_id`, transfer fields, `notes` nullable; `performed_by` nullable; `performed_at` naive DateTime NOT NULL, server default `now()`.
- The table has **no** `is_deleted`, `is_active`, `value_after` or `order_id` column. No method here joins or reads `factories`, `items` or `profiles`.
- Every parameter after `db` is keyword-only. Every method specified here only reads; nothing is written, flushed or committed.
- `skip >= 0` and `limit <= 100` are enforced by `GET /ledgers/inventory/`, not here.

### `InventoryLedgerDAO.calculate_balance(db, *, factory_id, item_id, inventory_type, workspace_id)`
Used by `LedgerManager.get_inventory_balance` (← `GET /ledgers/inventory/balance/`, returns this tuple unchanged) and `LedgerManager.reconcile_inventory` (← `POST /ledgers/inventory/reconcile/`, uses the quantity as "ledger quantity"). Returns a Python `tuple` of length 2: `(quantity, total_value)`; `quantity` an `int`, `total_value` a `decimal.Decimal`.

**Definition, the bucket's latest entry:** among `inventory_ledger` rows whose `workspace_id`, `factory_id`, `item_id` and `inventory_type` all equal the arguments, the one with the greatest `performed_at` (ties: R4a).

- **R1.** Given the bucket has no ledger entry, returns exactly `(0, Decimal("0.00"))`: a `tuple`, `quantity` the `int` `0`, `total_value` a `Decimal` equal to 0 whose string form is `"0.00"`.
- **R2.** [BUG-655] Given the bucket has at least one entry, returns `(qty_after, qty_after × avg_price_after)` of the latest entry — `quantity` an `int`, `total_value` a `Decimal`. When the latest entry's `avg_price_after` is `NULL`, `total_value` is `Decimal("0.00")` and `quantity` is still its `qty_after`. Examples: single entry (`qty_after` 20, `avg_price_after` 6.00) → `(20, Decimal("120.00"))`; single entry (5, `NULL`) → `(5, Decimal("0.00"))`; single entry (0, 6.00) → quantity `0` and a total value equal to `Decimal("0")`. *(Today: raises `AttributeError` — `'InventoryLedger' object has no attribute 'value_after'` — for every bucket that has at least one entry.)*
- **R3.** Only entries of the exact bucket count: when the only entries that exist differ from the arguments in workspace, factory, item or inventory type (each one alone), the result is the empty result of R1.
- **R4.** [BUG-655] The balance comes from the entry with the greatest `performed_at`, independent of `id` and insertion order. Example: entries inserted as 09:00 (30 @ 7.00), 11:00 (20 @ 6.00), 10:00 (10 @ 4.00) → `(20, Decimal("120.00"))`; a newer entry of another bucket (other type / factory / item / workspace) does not change it. *(Today: `AttributeError`, as R2.)*
- **R4a.** [BUG-641, **in this unit since round 2**, see §7] When several entries of the bucket share the greatest `performed_at`, the latest is the one with the greatest `id` (HR-6). Example: three entries at the same time with `qty_after` 15, 10, 99, all @ 2.00, where the qty-10 entry has the highest id → `(10, Decimal("20.00"))`. *(Today: ordered by `performed_at` only.)*
- **R5.** [BUG-655] (reviewer: intended) The factory's and the item's state are not consulted: the balance of a bucket in a soft-deleted factory, or of a removed item (`is_active = False`), is returned exactly as R2. Do not add any join or filter on `factories` / `items`.
- **R6.** The call changes nothing in the database.

Errors: none intended. Side effects: none.

How the managers above read it (rule text of `ledger_manager`, for context; the manager is not in scope):
- `get_inventory_balance` R1: no entry for the bucket → `(0, Decimal("0.00"))`. R2 [BUG-655]: bucket has at least one entry → `(qty_after, qty_after × avg_price_after)` of the latest entry; empty `avg_price_after` → value `Decimal("0.00")`; entries of another inventory type, factory, item or workspace are ignored. Example: latest entry 50 @ 5.00 (an older one 20 @ 4.00) → `(50, Decimal("250.00"))`; latest entry 30 @ `NULL` → `(30, Decimal("0.00"))`.
- `reconcile_inventory` R1 [BUG-655]: ledger quantity = the `get_inventory_balance` quantity for the bucket. Today any bucket with at least one ledger entry raises `AttributeError` before the stock row is read; once fixed, buckets with history reach the rest of reconcile (balanced / adjusted / "snapshot missing" error), which is unchanged by this unit.

Money and rounding: `qty_after` is an integer and `avg_price_after` a two-decimal `Numeric(15, 2)`, so `qty_after × avg_price_after` is already exact to two decimals; no rounding step is needed. The value must stay a `Decimal` (never a `float`). If you do quantize, it must be to `Decimal("0.01")` with `ROUND_HALF_UP` (HR-15) and must not change the exact product. No special case for any `qty_after` value: the formula applies as written.

### `InventoryLedgerDAO.get_by_workspace(db, *, workspace_id, inventory_type=None, factory_id=None, item_id=None, skip=0, limit=100)`
Override of `BaseDAO.get_by_workspace`. Used by `LedgerManager.get_inventory_ledger` when neither a full date range nor a transaction type is given (← `GET /ledgers/inventory/`), and by `ItemSummaryService._recent_activity`, which passes only `item_id`, `skip=0` and a `limit` of at least 5. Returns a `list` of `InventoryLedger` (possibly empty).
- **R1.** Only entries with `workspace_id` equal to the argument are returned; an entry of another workspace is never returned, whatever the other filters (also when its `factory_id` / `item_id` are given as filters). An unknown workspace id returns `[]`.
- **R2.** With no optional filter, entries of every inventory type, factory, item, transaction type and performer of the workspace are returned (subject to R8).
- **R3.** Given an `inventory_type`, only entries of exactly that type are returned; `None` applies no type filter.
- **R4.** Given a non-zero `factory_id`, only entries with that `factory_id` are returned; `None` applies no factory filter. A factory id with no entries in this workspace (unknown id, negative id, or a factory whose entries all belong to another workspace) returns `[]`.
- **R4a.** [BUG-885] `factory_id=0` filters like any other integer and returns `[]`. *(Today: `0` is treated like `None` — no factory filter — so the entries of every factory are returned.)*
- **R5.** Given a non-zero `item_id`, only entries with that `item_id` are returned; `None` applies no item filter. An item id with no entries in this workspace returns `[]`.
- **R5a.** [BUG-885] `item_id=0` filters like any other integer and returns `[]`. *(Today: `0` is treated like `None` — no item filter — so the entries of every item are returned.)*
- **R6.** All given filters combine with AND (e.g. `inventory_type=STORAGE` + `factory_id=F1` + `item_id=I1` returns only entries matching all three).
- **R7.** Entries are ordered by `performed_at` descending (newest first), independent of `id` and of insertion order. Example: entries inserted with times 09:00, 11:00, 10:00 come back 11:00, 10:00, 09:00.
- **R7a.** [BUG-640, **not this unit**] Entries with the same `performed_at` are ordered by `id` descending (HR-6). Leave the ordering as it is; see §6.
- **R8.** `skip` and `limit` are applied after filtering and ordering: with entries at 09:00, 10:00, 11:00, `skip=1, limit=1` returns exactly the 10:00 entry; consecutive windows partition the result with no repeats or gaps. With defaults at most the 100 newest entries are returned — given 101 matching entries, exactly 100, and the oldest one is missing.
- **R9.** `limit=0` returns `[]`; `skip` at or past the number of matching entries returns `[]`.
- **R10.** A negative `limit` or `skip` makes Postgres reject the query: negative `limit` raises `sqlalchemy.exc.DataError` (`.orig.pgcode == "2201W"`, "LIMIT must not be negative"); negative `skip` raises `DataError` (`.orig.pgcode == "2201X"`, "OFFSET must not be negative").
- **R11.** (reviewer: intended) The factory's state is not consulted: entries whose factory is soft-deleted (`factories.is_deleted = True`) are returned like any other, with no factory filter and with that factory's id as `factory_id`.
- **R12.** (reviewer: intended) The item's state is not consulted: entries whose item has been removed (`items.is_active = False`) are returned like any other, with no item filter and with that item's id as `item_id`.
- **R13.** The call changes nothing in the database.

### `InventoryLedgerDAO.get_by_transaction_type(db, *, transaction_type, workspace_id, inventory_type=None, factory_id=None, item_id=None, skip=0, limit=100)`
Used by `LedgerManager.get_inventory_ledger` when a non-empty transaction type is given and no full date range (← `GET /ledgers/inventory/`). Returns a `list` of `InventoryLedger` (possibly empty).
- **R1.** Only entries of the workspace (as `get_by_workspace` R1) whose `transaction_type` equals the argument **exactly** are returned: the comparison is case-sensitive, nothing is trimmed, and `%` / `_` are ordinary characters. With entries of type `"manual_add"` and `"sale"`: `"manual_add"` returns only the `manual_add` entries; `"MANUAL_ADD"`, `"manual_add "` (trailing space), `"manual%"` and an unknown type each return `[]`.
- **R2.** `transaction_type=""` and `transaction_type=None` return `[]` (no entry has an empty or missing type); no error is raised.
- **R3.** The optional filters narrow the result exactly as `get_by_workspace` R3, R4, R5 and combine with the transaction type and each other with AND (`get_by_workspace` R6).
- **R3a.** [BUG-885] `factory_id=0` returns `[]`, and `item_id=0` returns `[]`. *(Today: `0` is treated like `None`, so all entries of that transaction type in the workspace are returned.)*
- **R4.** Entries are ordered by `performed_at` descending (as `get_by_workspace` R7).
- **R4a.** [BUG-640, **not this unit**] ties by `id` descending. Leave the ordering as it is.
- **R5.** Paging and its errors are exactly as `get_by_workspace` R8, R9, R10 (default: the 100 newest entries of that type — given 101, exactly 100).
- **R6.** (reviewer: intended) The factory's and the item's state are not consulted: entries of a soft-deleted factory or of a removed item are returned like any other.

### `InventoryLedgerDAO.get_by_date_range(db, *, workspace_id, start_date, end_date, inventory_type=None, factory_id=None, item_id=None, skip=0, limit=100)`
Used by `LedgerManager.get_inventory_ledger` when both dates are given (← `GET /ledgers/inventory/`) and by `LedgerManager.get_item_movement_summary` when both dates are given (it passes no other filter and the default `skip` / `limit`). Returns a `list` of `InventoryLedger` (possibly empty).
- **R1.** Only entries of the workspace (as `get_by_workspace` R1) with `start_date <= performed_at <= end_date` are returned; both bounds are inclusive and compared to the microsecond. Example — entries at 09:00:00, 10:00:00 and 11:00:00 on 2026-01-01: range 09:00:00 … 11:00:00 returns all three; range 09:00:00.000001 … 10:59:59.999999 returns only the 10:00 entry.
- **R2.** `start_date == end_date` returns exactly the entries performed at that instant. `start_date` later than `end_date` returns `[]` (no error).
- **R3.** `start_date=None` or `end_date=None` raises `sqlalchemy.exc.ArgumentError` before any query is sent (message starts with "Only '=', '!=', 'is_()', 'is_not()', 'is_distinct_from()', 'is_not_distinct_from()' operators can be used with None/True/False"); nothing is read or changed. (No caller does this.)
- **R4.** The optional filters narrow the result exactly as `get_by_workspace` R3, R4, R5 and combine with the date window and each other with AND (`get_by_workspace` R6).
- **R4a.** [BUG-885] `factory_id=0` returns `[]`, and `item_id=0` returns `[]`. *(Today: `0` is treated like `None`, so all entries of the workspace inside the window are returned.)*
- **R5.** Entries are ordered by `performed_at` descending (as `get_by_workspace` R7).
- **R5a.** [BUG-640, **not this unit**] ties by `id` descending. Leave the ordering as it is.
- **R6.** Paging and its errors are exactly as `get_by_workspace` R8, R9, R10 (default: the 100 newest entries inside the window — given 101, exactly 100).
- **R7.** (reviewer: intended) The factory's and the item's state are not consulted: entries of a soft-deleted factory or of a removed item are returned like any other.

Note on `inventory_type`: the `if inventory_type:` checks are not part of BUG-885 (every enum member is truthy, so only `None` skips the filter today). You may switch them to `is not None` for consistency, but it must not change any result.

### Methods of this file that must not change
- `get_by_performer(db, *, performed_by, workspace_id, skip=0, limit=100)`: unchanged (its missing tie order is BUG-640, not this unit).
- `get_latest_entry(db, *, factory_id, item_id, inventory_type, workspace_id)`: **no longer in this list since round 2.** Its tie order (BUG-664 / BUG-803) is now in scope; see §7 for its rules. Everything else about it (filters, return value, signature) stays as it is.
- `exists_for_source(...)`: unchanged (idempotency guard).
- `get_by_id_and_workspace`, `get_by_order`: dead code on the removal checklist; leave them (removal is not part of this unit).
- Inherited `BaseDAO` methods: leave them.

## 4. Rules that apply

- **HR-15. Money rounds half up.** All money rounds half away from zero, everywhere (0.125 → 0.13, -1.005 → -1.01), matching the database's `Numeric` columns. Python `quantize` passes `ROUND_HALF_UP`; its default, half to even, is a bug. (Here the value is exact, see "Money and rounding" above; HR-15 only matters if you add a quantize.)
- **HR-6. Every paged or top-N result has a stable order.** It is the rule behind BUG-640 / BUG-641 / BUG-664. Since round 2, the inventory half of BUG-641 and BUG-664 / BUG-803 is in this unit (the two "latest entry" lookups, §7). BUG-640 (the four list methods) is still **not** in this unit: do not change the `ORDER BY` of `get_by_workspace`, `get_by_transaction_type`, `get_by_date_range` or `get_by_performer`.
- **HR-16. Nothing links across workspaces.** Every query keeps its `inventory_ledger.workspace_id == workspace_id` filter; nothing in this fix may widen what is returned.
- **Precedent for BUG-885 (BUG-880, BUG-501, BUG-707):** only "not given" (`None`) skips an optional filter; `0` is an ordinary value and filters (matching no rows, since no factory or item has id 0).
- **"Ledger is history, not a count"** (reviewer, 2026-10-10): the ledger lists and the single-bucket lookups do not hide entries of a soft-deleted factory or a removed item (rules R11 / R12 / R6 / R7 / R5 above).
- No owner answer (OQ-n) touches these bugs.

## 5. Scope

- May change: `app/dao/inventory_ledger.py` only — `calculate_balance` (BUG-655, and since round 2 its tie order, BUG-641 inventory half), `get_latest_entry` (since round 2: its tie order, BUG-664 / BUG-803 inventory half) and the `factory_id` / `item_id` checks of `get_by_workspace`, `get_by_transaction_type`, `get_by_date_range` (BUG-885).
- BUG-655's row is logged against `app/managers/ledger_manager.py` but says "fix in `InventoryLedgerDAO.calculate_balance`": the manager passes the DAO's tuple through (`get_inventory_balance`) or uses only its quantity (`reconcile_inventory`), so **the manager needs no change and is not in scope**. `app/services/ledger_service.py` is not in scope either.
- `app/dao/inventory.py` imports this DAO but calls only `get_latest_entry`. Since round 2 that method's tie order changes (§7); `app/dao/inventory.py` itself needs no change and is not in scope.
- Signatures, defaults and return types of every method stay as they are. No migration, no schema change, no API shape change (the balance endpoint starts answering for buckets with history instead of failing with 500; `factory_id=0` / `item_id=0` now give an empty list).

## 6. Out of scope (leave alone)

- **BUG-640** (`tied-timestamp-no-tiebreak`, ledger lists ordered by `performed_at` only; fix includes the four list methods here): planned separately. Do not add `id` to the `ORDER BY` of the four list methods.
- **BUG-641 / BUG-664 machine halves** (`app/dao/machine_item_ledger.py` `calculate_balance` and `get_latest_entry`): out of scope; see §7. *(The inventory halves of BUG-641, BUG-664 and BUG-803 moved into this unit in round 2.)*
- **BUG-992** (`get_by_date_range` with a time-zone-aware bound; logged against `app/dao/machine_item_ledger.py`, same line here): leave the date comparison unchanged.
- **BUG-2529** (`performed_at` server default uses the database clock; model file).
- **BUG-680** (`exists_for_source` not backed by a unique index; database change in another unit).
- `app/managers/ledger_manager.py`: BUG-341, BUG-642, BUG-644, BUG-645 … BUG-654 (reconcile result when nothing to reconcile, empty average price in reconcile, adjustment row chain, `updated_by`, price-only mismatch, report filters and caps, and the others in that file).
- `app/services/ledger_service.py`: BUG-3042 (price-only correction message), BUG-3043 (balance endpoints return the value as a float).
- `app/managers/inventory_movements.py` and others: BUG-1040 (half-even rounding in stock movements).

## 7. Scope change (round 2, 2026-11-28)

**Why.** Once the BUG-655 crash is fixed, inventory reconcile can run for buckets with history. It
reads "the latest entry" of the bucket, and today that entry is chosen by `performed_at` alone. Every
ledger row written in one save gets the same `performed_at` (the transaction's start time), so ties are
ordinary, and on a tie the database may hand back an older row. Reconcile then "corrects" correct stock
to a stale value. Example: in one save, Factory 1 receives 50 bolts at ৳5.00 into STORAGE and sends 20
out. The stock is 30 bolts (৳150.00), and the stock row says 30. A user presses Reconcile; the balance
reads the stale "after: 50" row and sets the stock to 50 bolts (৳250.00): ৳100.00 of bolts that do not
exist. The same stale pick already happens today before every stock movement (the "ledger wins" re-sync
uses `get_latest_entry`). So this unit now also fixes the tie order of both "latest entry" lookups in
this file. The round-1 changes (BUG-655 value, BUG-885 zero filters) stay exactly as they are.

### 7.1 Added bugs (inventory half only)

#### BUG-641: "Latest entry" balance lookups pick an arbitrary row on a timestamp tie (inventory half)
- **Pattern:** `tied-timestamp-no-tiebreak`
- **Where:** logged against `app/managers/ledger_manager.py`, via `app/dao/machine_item_ledger.py` and `app/dao/inventory_ledger.py` `calculate_balance`. **This unit: only `InventoryLedgerDAO.calculate_balance`.** Reached through `GET /ledgers/inventory/balance/` and `POST /ledgers/inventory/reconcile/`.
- **Today:** `get_machine_balance` / `get_inventory_balance` (and `reconcile_machine_item` / `reconcile_inventory`, which read the balance through them) pick the "latest" entry by `performed_at` only; inventory ledger rows written in one transaction all get the same `now()`, so ties are common.
- **Intended:** Latest = highest `performed_at`, ties broken by highest `id` (HR-6).

#### BUG-664: "Latest ledger entry" picked by timestamp alone can pick a stale row (inventory half)
- **Pattern:** `ambiguous-latest-row-tiebreak`
- **Where:** logged against `app/managers/inventory_movements.py`, fix in `InventoryLedgerDAO.get_latest_entry` / `MachineItemLedgerDAO.get_latest_entry`. **This unit: only `InventoryLedgerDAO.get_latest_entry`.** Reached through `InventoryDAO.sync_snapshot_from_ledger` (the "ledger wins" re-sync of a stock row before every stock movement) and `LedgerManager.reconcile_inventory` (reads the latest average price).
- **Today:** Several ledger rows for the same bucket written in one save can share the identical `performed_at`; the DB returns any one of them as "latest", so stock/avg cost can be silently rolled back to an older row's values before the next movement is applied.
- **Intended:** "Latest" ordered by `performed_at` descending, then `id` descending, so the most recently inserted row always wins even when timestamps tie.

#### BUG-803: Return with 3+ lines of the same item can deduct from a stale stock snapshot
- **Pattern:** `ambiguous-latest-row-tiebreak`
- **Where:** logged against `app/managers/po_return_inventory.py`, fix in `InventoryLedgerDAO.get_latest_entry`, same fix as BUG-664.
- **Today:** Before each storage deduction the stock row is re-synced from the "latest" storage-ledger row, chosen by `performed_at` alone; rows written earlier in the same completion share one `performed_at` (transaction start), so the third line may re-sync from the first line's row and deduct from the wrong quantity (e.g. stock 10, three returns of 3 → final stock 4 instead of 1).
- **Intended:** "Latest" = `performed_at` descending, then `id` descending, so each line deducts from the stock left by the previous one (precedent BUG-664; best-practice default, delegated by reviewer).

### 7.2 Spec rules (copied; rule text only)

#### `InventoryLedgerDAO.calculate_balance(db, *, factory_id, item_id, inventory_type, workspace_id)`
All rules as listed in §3 (R1, R2, R3, R4, R4a, R5, R6, "Errors: none intended", "Side effects: none") still hold. R4a is now a target of this unit:
- **R4.** The balance comes from the entry with the greatest `performed_at`, independent of `id` and insertion order. Example: entries inserted as 09:00 (30 @ 7.00), 11:00 (20 @ 6.00), 10:00 (10 @ 4.00) → `(20, Decimal("120.00"))`; a newer entry of another bucket (other type / factory / item / workspace) does not change it.
- **R4a.** [BUG-641] When several entries of the bucket share the greatest `performed_at`, the latest is the one with the greatest `id` (HR-6). Example: three entries at the same time with `qty_after` 15, 10, 99, all @ 2.00, where the qty-10 entry has the highest id (it is not the last one inserted) → `(10, Decimal("20.00"))`. *(Today: ordered by `performed_at` only.)*
- An older entry (smaller `performed_at`) never wins, whatever its `id`: `id` only decides between entries that share the greatest `performed_at`.

#### `InventoryLedgerDAO.get_latest_entry(db, *, factory_id, item_id, inventory_type, workspace_id)`
Used by `InventoryDAO.sync_snapshot_from_ledger` (the "ledger wins" re-sync of a stock row before every stock movement) and by `LedgerManager.reconcile_inventory` (to read the latest average price). Inputs as `calculate_balance`. Returns the `InventoryLedger` instance, or `None`.
- **R1.** Given the bucket has no ledger entry, returns `None`.
- **R2.** Given entries with distinct `performed_at`, returns the one with the greatest `performed_at`, independent of `id` and insertion order. Example: entries inserted as 09:00 (`qty_after` 30), 11:00 (20), 10:00 (10) → the 11:00 entry (`qty_after` 20). A single entry is returned as it is.
- **R3.** [BUG-664] When several entries of the bucket share the greatest `performed_at`, the one with the greatest `id` is returned (HR-6), which in normal use is the entry written last, since ids grow with each insert. The `id` decides, not the physical insertion order. Example: three entries at the same time, where the second one inserted carries the highest id → that one is returned, not the first-inserted or the last-inserted one. An older entry (smaller `performed_at`) never wins, whatever its `id`. *(Today: ordered by `performed_at` descending only, limited to one row; among tied entries the winner depends on the query plan, and is never chosen by `id`.)*
- **R4.** Only entries of the exact bucket are considered: an entry that differs in workspace, factory, item or inventory type (each one alone) is never returned, even when it is newer; when only such entries exist the result is `None`.
- **R5.** The returned object is the full ledger row: `id`, `qty_after` (`int`) and `avg_price_after` (`Decimal`, or `None` when the column is `NULL`) are readable as stored.
- **R6.** (reviewer: intended) The factory's and the item's state are not consulted: the latest entry of a bucket in a soft-deleted factory, or of a removed item, is returned like any other.
- **R7.** The call changes nothing in the database.

Errors: none. Side effects: none.

How the callers read it (context; the callers are not in scope and need no change):
- Stock movements (`_storage_out`, `_storage_in` in `app/managers/inventory_movements.py`, through `InventoryDAO.sync_snapshot_from_ledger`): before a movement, the bucket's stock row `qty` and `avg_price` are set from the newest ledger row for that bucket (`qty_after`, `avg_price_after`), "newest" = greatest `performed_at`, ties broken by greatest `id` [BUG-664].
- Purchase returns (`post_purchase_return_inventory`, R15a [BUG-803]): with three return lines of the same item in one completion (stock 10, three returns of 3), each line deducts from the stock left by the previous line: 10 → 7 → 4 → 1.
- `get_inventory_balance` R3 [BUG-641]: on a tie, the balance is the one of the entry with the highest `id`.

### 7.3 Rules that apply

- **HR-6. Every paged or top-N result has a stable order.** (house rule, copied) "Default: name case-insensitive ascending, then `id` ascending. Score-ranked results break ties the same way. Generic `BaseDAO` lists only guarantee `id` ascending (stable paging); choosing a display order is the manager's job." For the two ledger "latest entry" lookups the bug rows above settle the order: `performed_at` descending, then `id` descending (top-1).
- HR-16 still applies: both queries keep their `workspace_id` filter and the other three bucket filters.
- No owner answer (OQ-n) touches these bugs; the intended order is settled by the bug rows and HR-6.

### 7.4 Scope (round 2)

- May change, in `app/dao/inventory_ledger.py`: the ordering of `calculate_balance` and `get_latest_entry` (add `id` descending after `performed_at` descending). Keep the round-1 changes as they are.
- Nothing else changes: filters, signatures, return values, the no-entry results, and the `ORDER BY` of the four list methods (BUG-640) stay as they are. No migration, no index, no API shape change.
- If you share one query between `calculate_balance` and `get_latest_entry`, both must keep every rule above.

### 7.5 Out of scope (round 2)

- **BUG-641, machine half:** `app/dao/machine_item_ledger.py` `MachineItemLedgerDAO.calculate_balance` (machine balance and machine reconcile). Leave that file alone.
- **BUG-664, machine half:** `app/dao/machine_item_ledger.py` `MachineItemLedgerDAO.get_latest_entry` (machine unit cost, machine stock re-sync). Leave that file alone.
- **BUG-2463:** the same tie in `app/dao/project_component_item_ledger.py` (projects deferred until after launch).
- **BUG-640:** the four list methods' tie order (unchanged, see §6).
- Everything else listed in §6.
