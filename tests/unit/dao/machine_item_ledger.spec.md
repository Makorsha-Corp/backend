# Spec — `app/dao/machine_item_ledger.py`

> **Status:** APPROVED (2026-10-30). Stays APPROVED after fill-gaps (Gap log at the end).
> **Source commit:** e48a092

> **Review round 2026-10-30.** **The owner's own answers, relayed by the main session:** Q1 — "Keep the average": bug, keep the current average cost; `total_cost` = |change| × average, `value` = qty × average; a first entry with no history stays 0.00 (BUG-993, fix in `MachineItemManager._write_ledger_entry`, FU-1). The ledger question from the first round: the inventory ledger ruling stands, a ledger is history, so "hide children" does not reach ledgers (P1–P3). **Delegated:** P1–P3 and Q2–Q6 are accepted as suggested, decided by Claude under the reviewer's delegation (2026-10-30); none of these is the reviewer's own answer. The house-rule lines stand. The pilot-default markers were removed; no rule's behavior changed, and no rule was added. Q1 changes no rule of this DAO, which reads correctly what is stored.
>
> **Fill-gaps round 2026-10-30 (`machine_item_ledger.cases.md` gaps 1–11).** Gaps 1, 2, 3, 9, 10 are facts read from the code and verified by running (`p7.py`, rolled back). Gaps 4–8 and 11 are decided by Claude under the reviewer's delegation (2026-10-30), following the nearest precedent. No new bug in that round. One money point was raised there: FU-6, answered by the owner below. Rules added: `get_by_performer` R3, R4; inherited R1a, R1b; `GET /ledgers/machine/` R1a. Rules changed: `get_by_date_range` R3a (Today note); inherited R1, R2 (wording, no behavior). Notes, inherited Errors, the BUG-341 line and the Branch map updated.
>
> **Owner's answer on FU-6, 2026-10-30, relayed by the main session:** "Half up": all money rounds half away from zero everywhere (0.125 becomes 0.13), matching the database. BUG-1040 logged; no rule of this DAO changes.
>
> **Standing reviewer decisions applied here (not asked again):**
> 1. Physical row order and collation order are **not** an order; a missing `ORDER BY` is a bug. No order recipe in this spec is called deterministic.
> 2. Things of a soft-deleted parent are hidden by the parent's state, their own rows untouched ("hidden, not cascaded", 2026-10-11). **This does not reach ledgers** (owner, 2026-10-30): a ledger is history, not a count, and stays complete (inventory ledger DAO Q3, Q4, Q5, 2026-10-10). P1–P3 below follow that ruling.
> 3. Raw DAO lookups may return deleted rows; the manager decides what to hide (HR-4 scope). This table has no soft-delete column of its own.
> 4. A question touching money or the order workflow (purchase / sales / work / transfer orders, stock) was marked **OWNER**. Only Q1 carried the mark; the owner has answered it.
>
> **Verified by running** (throwaway scripts `h.py`, `p1.py` … `p6.py` against the test database, each in one transaction rolled back; nothing committed or dropped): every "Today:" note below; the table's columns, nullability, defaults, constraints, constraint names, indexes, triggers (none) and the database time zone (`America/New_York`); all seven methods for own workspace, other workspace, unknown id, `0`, `None`, each optional filter, exact matching of the transaction type (case, trailing space, `%`, `""`, `None`), both date bounds to the microsecond, equal and reversed bounds, `None` bounds, `limit=0`, `skip` past the end, negative `limit` / `skip` (error class, pgcode, text), 101 rows, unflushed rows, positional call; balance with `NULL`, `0` and negative stored values and its return types; the tie shape (three rows, one with an explicit high id) under three query plans, and the emitted SQL of every method; aware datetimes under three session time zones; 30 real `create` calls in a row (10 distinct timestamps on this Windows machine); `create` with the schema and with every FK / NOT NULL failure; `update` / `remove` on a ledger row; hard delete of a referenced profile, machine and item; `get_by_order` (facts in Q5); **over HTTP** with `TestClient` and overridden dependencies: `GET /api/v1/ledgers/machine/` with each transaction type the application writes, with date-only and `Z`-suffixed dates; `MachineItemLedgerResponse.model_validate` on stored rows; Q1's chain through `_machine_in`, `_write_ledger_entry`, `_machine_out`, `get_machine_unit_cost`. **Not run:** two concurrent transactions (commits are not allowed); the *intended* behavior of the bug rules; the same HTTP requests on `GET /ledgers/inventory/` and the other ledger endpoints (read, not run); a production database's time-zone setting.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list — nothing open
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | A manual stock change on a machine books value and average price 0.00, and the machine's cost is lost from then on | bug — keep the average (BUG-993, fix in the machine item manager) | **owner** |
| Q2 | The machine ledger page crashes (500) as soon as the page holds a return, a reversal or a work-order movement | bug — BUG-990 | delegation |
| Q3 | Picking an end date leaves that whole day out; picking one single day shows nothing | bug — BUG-991 | delegation |
| Q4 | A date sent with a time zone (`…Z`) is compared to stored UTC using the database's time-zone setting, so the result depends on the server | bug — BUG-992 | delegation |
| Q5 | "Ledger entries of one order" has no caller and the order columns are never filled | remove | delegation |
| Q6 | The transaction-type lookup can run without a machine, but no caller does that | intended | delegation |
| P1 | Lists still show entries of a deleted machine (or a machine of a deleted factory) | intended, per inventory ledger Q3 | delegation; ruling restated by the owner |
| P2 | Lists still show entries of an item removed from the catalog | intended, per inventory ledger Q4 | delegation; ruling restated by the owner |
| P3 | Balance and latest entry ignore a deleted machine / removed item | intended, per inventory ledger Q5 | delegation; ruling restated by the owner |

### House-rule violations — applied automatically
> All three defects were already recorded when the ledger manager and the stock-movement code were reviewed, and the code to fix is in this file. The existing IDs are reused; no new ID.

- **HR-6** `get_by_item` R4a, `get_by_machine_and_item` R3a, `get_by_transaction_type` R5a, `get_by_date_range` R5a, `get_by_machine` R3a — the five ledger lists are ordered by `performed_at` (newest first) only; entries with the same timestamp come back in no fixed order, and paging can repeat or skip them. Intended: `performed_at` newest first, then `id` descending, before `skip` / `limit`. (BUG-640 row names the manager methods; the fix is in these DAO methods. `get_by_item` is reached through the item summary, not the manager; same root cause, same fix, same precedent as `InventoryLedgerDAO.get_by_workspace`.)
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-640 (existing, no new ID). Rules: as listed.
- **HR-6** `calculate_balance` R4 — the "latest entry" of a machine and item is picked by `performed_at` only; on a tie an arbitrary entry decides the balance. Intended: latest = greatest `performed_at`, ties broken by greatest `id`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-641 (existing; its row names this file). Rules: `calculate_balance` R4.
- **HR-6** `get_latest_entry` R3 — same top-1 tie in the lookup that prices every machine stock movement. Intended: latest = greatest `performed_at`, ties broken by greatest `id`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-664 (existing; its row names `MachineItemLedgerDAO.get_latest_entry`). Rules: `get_latest_entry` R3.
- **HR-6** inherited `get_by_workspace` (inherited methods R6) — no sort order. Intended for this raw lookup: `id` ascending before `skip` / `limit`. This DAO does not override it, so the fix in `app/dao/base.py` reaches it. No caller on this DAO.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-100 (existing, no new ID). Rules: inherited methods R6.

Checked and **not** violated: **HR-4** — the table has no soft-delete column; deleted parents are P1–P3. **HR-5** — every filter is in the query before `skip` / `limit`. **HR-7** — the DAO does not validate paging (`limit=0` → `[]`, negative → error); `GET /ledgers/machine/` lacks the lower bound, which is **BUG-642** (existing, logged against the endpoints; R7 below records today's DAO behavior and is not tagged, same as the inventory ledger spec). **HR-8** — no `LIKE`; `%` in a transaction type is an ordinary character. **HR-9** — no "last changed by" column. **HR-10** — nothing here changes state; the lock belongs on `machine_items` in the writers (BUG-661, existing). **Falsy `0`** — unlike the inventory ledger (BUG-885), this file tests `is not None`, so `0` is a filter that matches nothing. Holds, no bug.

### Existing bugs that land in this file (no new ID)
- **BUG-645** — this DAO has no `get_by_performer`; `GET /ledgers/reports/user-transactions/{user_id}/` raises `AttributeError` (500) on it. Specified below as a method to add.
- **BUG-341** (manager spec P1, P3, P4) — its fix needs `get_by_date_range` to accept a transaction type and each bound alone; `get_by_date_range` R4 and Errors row 1 stop applying with that fix (a `None` bound becomes "no bound"), and R1 then covers one bound alone. R2, R3, R3a stay. `LedgerManager.get_item_movement_summary` passes no `item_id` although this method accepts it.
- **BUG-680** — "already posted?" guards read this table directly (`to_inventory`, `po_return_inventory`, `po_receive_inventory`), not through this DAO; no unique index backs them (see Model facts).

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation (2026-10-30))

### P1. Ledger lists still show entries of a deleted machine — ✅ intended
**Background:** Machines are soft-deleted (`is_deleted = True`, the row stays), and a machine of a soft-deleted factory is hidden everywhere (BUG-890, BUG-891). Every ledger entry points at its machine; no method here looks at the machine row. For the inventory ledger the reviewer ruled that a ledger is history, not a count: entries of a deleted factory stay listed (inventory ledger DAO Q3). The owner confirmed on 2026-10-30 that the later rule "things of a deleted parent are hidden" does not reach ledgers.
**What happens today:** Entries of a deleted machine, or of a live machine in a deleted factory, are returned by every list, with and without that machine's id as filter. (Verified.)
**Example:** Machine "Press 4" received 30 bolts in March and was deleted in June. The item's recent activity and the machine ledger still list "March: +30 bolts, Press 4".
**Rules affected:** `get_by_item` R8, `get_by_machine_and_item` R5, `get_by_transaction_type` R7, `get_by_date_range` R7, `get_by_machine` R5
**Answer:** intended — per inventory ledger DAO Q3 precedent: a ledger is history; hiding entries leaves gaps in the audit trail
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-30); rules unchanged. Rules: `get_by_item` R8 ✅, `get_by_machine_and_item` R5 ✅, `get_by_transaction_type` R7 ✅, `get_by_date_range` R7 ✅, `get_by_machine` R5 ✅.

### P2. Ledger lists still show entries of an item removed from the catalog — ✅ intended
**Background:** Items are removed by `is_active = False`; the row stays. Same reasoning as P1 (inventory ledger DAO Q4).
**What happens today:** Entries of a removed item are returned by every list, also with that item's id as filter. (Verified.)
**Example:** "Old Gasket" was installed (+12) and used (−4), then removed from the catalog. Both movements stay listed for that machine.
**Rules affected:** `get_by_item` R8, `get_by_machine_and_item` R5, `get_by_transaction_type` R7, `get_by_date_range` R7, `get_by_machine` R5
**Answer:** intended — per inventory ledger DAO Q4 precedent
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-30); rules unchanged. Rules: the same rules as P1 ✅.

### P3. Balance and latest entry ignore a deleted machine or removed item — ✅ intended
**Background:** These two lookups work on one explicitly named machine and item. `get_latest_entry` also supplies the unit cost of every machine stock movement. Inventory ledger DAO Q5 kept the same lookups raw: refusing to work on a deleted thing is the caller's job.
**What happens today:** A deleted machine's balance and latest entry are returned like any other. (Verified: `(4, 8)`.)
**Example:** Press 4 is deleted while its ledger says 30 bolts. `GET /ledgers/machine/balance/` for it answers 30. If the lookup hid it, a reconcile would see 0 and write a false adjustment.
**Rules affected:** `calculate_balance` R6, `get_latest_entry` R5
**Answer:** intended — per inventory ledger DAO Q5 precedent
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-30); rules unchanged. Rules: `calculate_balance` R6 ✅, `get_latest_entry` R5 ✅.

### New questions

### Q1. **OWNER** — A manual stock change wipes the machine's cost — 🐞 BUG-993
**Background:** A machine has no stored average price. Its cost lives only in the ledger: the newest entry's `avg_price_after` (and `value_after`). `get_latest_entry` reads it, `get_machine_unit_cost` turns it into the cost of the next movement, and `calculate_balance` reads the value for `GET /ledgers/machine/balance/`. When a user edits a machine's stock by hand (`MachineItemManager.create_machine_item`, `update_machine_item`, `delete_machine_item`), `_write_ledger_entry` always writes `unit_cost`, `total_cost`, `value_before`, `value_after`, `avg_price_before` and `avg_price_after` as `0.00`. This DAO reads correctly; the zeros are written elsewhere, and this is where they show. The machine item manager has no spec yet.
**What happens today:** The next entry after a manual change has lost the cost, and so does every later movement, because each copies the average from the entry before it. (Verified: receive 10 @ 5.00 → balance `(10, 50.00)`, unit cost 5.00; manual change to 12 → `(12, 0.00)`, unit cost 0.00; then consume 2 → priced 0.00, `(10, 0.00)`.)
**Example:** Press 4 holds 10 bearings worth 50.00. A storekeeper corrects the count to 12. The balance now says 12 bearings worth 0.00, and the 2 bearings a work order consumes next day are booked at no cost: the work order line's `unit_cost` and `total_cost` come from this figure, so its parts cost shows 0.00.
**Rules affected:** none in this DAO (`calculate_balance` R2, `get_latest_entry` R2 read what is stored). The fix is in `app/managers/machine_item_manager.py`.
**Suggested answer:** `bug — a manual change keeps the machine's current average price: unit_cost, avg_price_before and avg_price_after = the average from the latest entry; total_cost = |change| × average; value_before / value_after = qty × average. A first entry with no history stays at 0.00.` Alternative: `intended — a manual change resets the cost on purpose`; machine cost figures are then only meaningful until the first manual edit.
**Why the owner:** it decides what money value hand-corrected stock carries. Added units would be valued at the old average rather than at nothing.
**Answer:** bug — "Keep the average": keep the current average cost; `total_cost` = |change| × average, `value` = qty × average; a first entry with no history stays 0.00 (owner, 2026-10-30, relayed by the main session)
**Resolution:** 🐞 BUG-993 (pattern `manual-change-zeroes-cost`; the fix is in `MachineItemManager._write_ledger_entry`, routed by FU-1). No rule of this DAO changes. The intended rules belong in the machine item manager spec.

### Q2. The machine ledger page crashes on returns, reversals and work-order movements — 🐞 BUG-990
**Background:** `GET /ledgers/machine/` returns rows through `MachineItemLedgerResponse`, which inherits from `MachineItemLedgerBase` a pattern allowing only eight transaction types. FastAPI checks responses against that schema. The application writes more types than that to this table: `purchase_return`, `consumption_reversal`, `work_order_install`, `work_order_replace_out`, `work_order_replace_in`, `work_order_borrow_returned`. The database column has no such limit, and the inventory ledger's schema has no pattern at all.
**What happens today:** If the requested page holds even one such row, the endpoint answers 500 (`ResponseValidationError`). The DAO returns the rows correctly; a filter that leaves the row out (`transaction_type=manual_add`) answers 200. (Verified over HTTP for all six, plus `sale`.)
**Example:** A work order installs a bearing on Press 4. From then on, opening Press 4's ledger shows "Internal Server Error" until that entry falls past the page.
**Rules affected:** `GET /ledgers/machine/` R1
**Suggested answer:** `bug — the response schema accepts every stored transaction type (plain string, as the inventory ledger response does)`. `MachineItemLedgerResponse` must not inherit the pattern. Whether the input schema keeps one is irrelevant: nothing uses it (inherited methods R2).
**Answer:** bug — the response schema accepts every stored transaction type (plain string, as the inventory ledger response does)
**Resolution:** 🐞 BUG-990 (pattern `response-schema-narrower-than-stored-values`; fix in `app/schemas/machine_item_ledger.py`) — decided by Claude under the reviewer's delegation (2026-10-30). Rules: `GET /ledgers/machine/` R1.

### Q3. The end date leaves out that whole day — 🐞 BUG-991
**Background:** The ledger page uses plain date inputs, so it sends `end_date=2026-09-30` with no time. The API turns that into `2026-09-30 00:00:00`, and the DAO compares exactly (R1). Entries have a time of day. Other date filters of the application treat an end date as the whole day (`PurchaseOrderDAO`, `TransferOrderDAO`, machine activity events: `datetime.combine(date_to, time.max)`).
**What happens today:** Entries of the end day are missing; start = end returns nothing. (Verified over HTTP on the machine ledger: entries at 29 Sep 10:00 and 30 Sep 10:00; 29–30 Sep returns only the 29th; 30–30 Sep returns `[]`. With explicit times `…T23:59:59` both come back.) The other ledger endpoints and the factory overview's "last 7 days" feed, which sends today as the end date, take the same parameters and path (read, not run).
**Example:** A manager picks 1–30 September. Everything booked on the 30th is missing, and nothing says so.
**Rules affected:** `GET /ledgers/machine/` R2. `get_by_date_range` R1 stays: the DAO compares exactly what it is given.
**Suggested answer:** `bug — an end_date given as a date with no time means the end of that day (time.max), at the ledger endpoints; a value with a time stays exact`.
**Answer:** bug — an `end_date` given as a date with no time means the end of that day (`time.max`), at the ledger endpoints; a value with a time stays exact
**Resolution:** 🐞 BUG-991 (pattern `date-only-upper-bound-excludes-day`; fix in `app/api/v1/endpoints/ledgers.py`) — decided by Claude under the reviewer's delegation (2026-10-30). Integration-only: it needs the HTTP layer. Rules: `GET /ledgers/machine/` R2.

### Q4. A date with a time zone gives a result that depends on the server — 🐞 BUG-992
**Background:** `performed_at` holds UTC with no time-zone mark. The endpoint accepts dates with a time zone (`…Z`, `+06:00`) and passes them on as they are. Postgres then reads the stored UTC value in the session's time-zone setting before comparing. The application's own frontend sends plain dates today; any other API client can send `…Z`. The inventory ledger spec left this unspecified.
**What happens today:** The same request gives different rows depending on the database's `TimeZone`. (Verified: entry at 12:00 UTC, range 11:30Z–12:30Z: found under `UTC`; not found under `America/New_York` or `Asia/Dhaka`. The same range without `Z` is found under all three.)
**Example:** A report client asks for 11:30Z–12:30Z. On a server set to `Asia/Dhaka` the 12:00 entry is missing; on a server set to `UTC` it is there.
**Rules affected:** `get_by_date_range` R3a
**Suggested answer:** `bug — aware datetimes are converted to UTC and made naive before the comparison, so the result does not depend on the server`. Low urgency while only plain dates are sent. The same line exists in `InventoryLedgerDAO.get_by_date_range`.
**Answer:** bug — aware datetimes are converted to UTC and made naive before the comparison, so the result does not depend on the server
**Resolution:** 🐞 BUG-992 (pattern `aware-datetime-against-naive-column`; fix in this file, or in one shared helper) — decided by Claude under the reviewer's delegation (2026-10-30). Rules: `get_by_date_range` R3a.

### Q5. "Ledger entries of one order" has no caller, and its column is never filled — 🗑️ remove (dead code)
**Background:** `get_by_order` filters on `machine_item_ledger.order_id`. Nothing in `app/` or `tests/` calls it, and none of the four places that write this table sets `order_id`, `order_type` or `invoice_id`, so the columns are always empty. Entries link to their source through `source_type` / `source_id` instead, and the item summary's order link already works from those. The sibling method on the inventory ledger was removed for the same reason (inventory ledger DAO Q1), although that one also crashed; this one runs.
**What happens today:** Reachable by nobody. Verified facts, if it is kept: same-workspace rows with that `order_id`, oldest first by `performed_at` with no tie-break, no limit (101 of 101); `order_id=None` returns every row with an empty `order_id`, which is the whole workspace; it ignores `order_type`, so purchase order 500 and work order 500 are mixed.
**Example:** No endpoint, job or script lists ledger entries by order through this method; deleting it changes nothing a user can see.
**Rules affected:** `get_by_order` (all)
**Suggested answer:** `remove` (the method only; whether the three empty columns stay is a schema clean-up, not decided here). If kept: needs a section here, `performed_at` then `id`, and an `order_type` filter.
**Answer:** remove
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-30); not specified; listed under **Not specified** and in `docs/testing/dead-code-removal-checklist.md` (`app/dao/machine_item_ledger.py:91`). Not a bug, no BUG ID.

### Q6. The transaction-type lookup can run without a machine, but no caller does — ✅ intended
**Background:** `get_by_transaction_type` takes an optional `machine_id`. Its only caller, `LedgerManager.get_machine_ledger`, always passes one (required by `GET /ledgers/machine/`), so the "all machines of the workspace" side never runs. The sibling `get_by_date_range` does run without a machine (item movement report).
**What happens today:** Without `machine_id` the method returns matching entries of every machine. Not reachable from the API.
**Example:** No user can ask for "all consumption entries of the workspace" today.
**Rules affected:** `get_by_transaction_type` R3
**Suggested answer:** `intended` — keep the parameter: it mirrors `get_by_date_range`, and the BUG-341 fix (all filters combine) will rework these methods anyway. Answer `remove` to make `machine_id` required.
**Answer:** intended
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-30); rules unchanged. Rules: `get_by_transaction_type` R3 ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO. Whoever describes the named module must read this list first.

| # | Where | What | Came from |
|---|---|---|---|
| FU-1 | **Machine item manager** (`app/managers/machine_item_manager.py`) | **BUG-993 (owner, 2026-10-30): fix `_write_ledger_entry`.** It must write `unit_cost`, `avg_price_before`, `avg_price_after` = the current average from the latest entry, `total_cost` = \|change\| × average, `value_before` = `qty_before` × average, `value_after` = `qty_after` × average. A first entry with no history stays 0.00. Reached by `create_machine_item`, `update_machine_item`, `delete_machine_item`; write these as tagged rules there. `total_cost` rounds half up (FU-6). Details for that review: a latest entry with an empty `avg_price_after` (`get_machine_unit_cost` treats it as 0). **Open, undecided:** repair of stored data for machines already at 0.00 (recorded in BUG-993). | Q1 |
| FU-2 | **Ledger manager / endpoints** | BUG-991 has the same shape on `GET /ledgers/inventory/`, `/ledgers/attachments/`, `/ledgers/reports/item-movement/{item_id}/`, `/ledgers/reports/user-transactions/{user_id}/`. `get_transactions_by_user` also ignores its dates (BUG-341). | Q3 |
| FU-3 | **Project component item ledger** (`app/schemas/project_component_item_ledger.py:12`) | Same eight-type pattern on its response path as BUG-990. Latent: no code writes that ledger yet (manager spec Q11). Check when that DAO is described. | Q2 |
| FU-4 | **Machine ledger model** (`app/models/machine_item_ledger.py`) | Comments list eight transaction types and six source types; the application writes more of both. `order_id`, `order_type`, `invoice_id` are never written (Q5). | Q2, Q5 |
| FU-5 | **Profile / workspace deletion** | `performed_by` is `NOT NULL` with `ON DELETE SET NULL`, so hard-deleting a profile that has ledger entries fails with `NotNullViolation` (inherited R5). No code path hard-deletes a profile or workspace today, so nothing is reachable; it matters if one is added. | model check |
| FU-6 | **All code that rounds money** (fix routed by BUG-1040) | **Owner, 2026-10-30: "Half up": all money rounds half away from zero everywhere (0.125 → 0.13), matching the database.** The code does not follow it yet: `_machine_in` / `_machine_out` and the other `quantize` calls listed in BUG-1040 use Python's default, half to even. Verified: `_machine_in` with `unit_cost` 0.125, qty 1 stores `unit_cost` 0.13, `total_cost` 0.12, `value_after` 0.13. Fix: `ROUND_HALF_UP` at every place listed, best through one shared helper. The approved specs and tests of `inventory_movements` and `to_inventory` pin half to even and change with the fix (listed in BUG-1040). The BUG-993 fix (FU-1) uses half up for `total_cost`. Over-limit amounts (R1b) were run at the DAO only; what the API answers was not run. | gap 3 |

## Overview
`MachineItemLedgerDAO` reads `machine_item_ledger`: the history of every item movement on a machine, one row ("entry") per movement of one machine and item, each recording quantity, cost, value and average price before and after. It serves the machine ledger page and reconciliation (`LedgerManager`), the item movement report, the item summary's recent activity (`ItemSummaryService`), and the lookup that prices every machine stock movement (`inventory_movements.get_machine_unit_cost`, through `get_latest_entry`). Invariants: workspace isolation (every method here filters `workspace_id`) and one unambiguous "latest entry" per machine and item. Every method in this file only reads; entries are written through the inherited `create`, always with a dict.

**Callables:** 7 specified, 1 to add (`get_by_performer`, BUG-645), + inherited `BaseDAO` behavior and the `GET /ledgers/machine/` response path · 2 not specified
**Externals to mock:** none. (`performed_at` is filled by a Python column default, `app.utils.time.utcnow`, bound when the model module is imported; patching it does not change the stored value. Set `performed_at` explicitly.)
**Integration-only behavior:** `GET /ledgers/machine/` R2 (BUG-991) needs the HTTP layer. `skip >= 0` and `limit <= 100` are enforced by the endpoint; `limit >= 1` is not (BUG-642).

**Model facts (table `machine_item_ledger`, class `app.models.machine_item_ledger.MachineItemLedger`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence `machine_item_ledger_id_seq` |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE (`machine_item_ledger_workspace_id_fkey`) | — |
| `machine_id` | Integer NOT NULL, FK `machines.id` ON DELETE RESTRICT (`machine_item_ledger_machine_id_fkey`) | — |
| `item_id` | Integer NOT NULL, FK `items.id` ON DELETE RESTRICT (`machine_item_ledger_item_id_fkey`) | — |
| `transaction_type` | varchar(50) NOT NULL, plain text, no enum or check | — |
| `quantity`, `qty_before`, `qty_after` | Integer NOT NULL, no check (negative values can be stored) | — |
| `unit_cost`, `total_cost` | Numeric(15, 2) NOT NULL, no check | — |
| `value_before`, `value_after`, `avg_price_before`, `avg_price_after` | Numeric(15, 2) nullable | `NULL` |
| `source_type` | varchar(50) NOT NULL | — |
| `source_id`, `order_id`, `transfer_source_id`, `transfer_destination_id` | Integer nullable, no FK | `NULL` |
| `order_type` | varchar(30) nullable | `NULL` |
| `transfer_source_type`, `transfer_destination_type` | varchar(50) nullable | `NULL` |
| `invoice_id` | Integer nullable, FK `account_invoices.id` ON DELETE SET NULL (`machine_item_ledger_invoice_id_fkey`) | `NULL` |
| `notes` | text nullable | `NULL` |
| `performed_by` | Integer **NOT NULL**, FK `profiles.id` ON DELETE **SET NULL** (`machine_item_ledger_performed_by_fkey`) | — |
| `performed_at` | timestamp without time zone NOT NULL | Python `utcnow()` at flush (naive UTC); no database default |

- No `is_deleted`, `is_active` or `updated_*` column. No unique constraint or index besides the primary key; no check constraint; no trigger. Plain indexes on `id`, `workspace_id`, `machine_id`, `item_id`, `transaction_type`, `source_type`, `order_id`, `invoice_id`, `performed_by`, `performed_at`.
- Unlike `inventory_ledger` (whose `performed_at` is the transaction's `now()`), rows here take the Python clock at flush, so rows of one transaction usually differ. They can still tie: 30 `create` calls in a row gave 10 distinct timestamps on this Windows machine.
- Transaction types the application writes to this table: `purchase_order`, `purchase_return`, `manual_add`, `inventory_adjustment`, `transfer_in`, `transfer_out`, `consumption`, `consumption_reversal`, `work_order_install`, `work_order_replace_out`, `work_order_replace_in`, `work_order_borrow_returned`.
- The four writers: `inventory_movements._machine_out`, `_machine_in`, `LedgerManager.reconcile_machine_item`, `MachineItemManager._write_ledger_entry`. All pass a dict with `workspace_id` and `performed_by`, and none passes `performed_at`, `order_id`, `order_type` or `invoice_id`.
- Database time zone of the test database: `America/New_York`.

**Notes for the test designer:**
- Use the module singleton: `from app.dao.machine_item_ledger import machine_item_ledger_dao`. All parameters after `db` are keyword-only (a positional call raises `TypeError`); this stays a note, not a rule, and gets no card (gap 6, as in the item tag spec).
- Workspaces and profiles from `tests/unit/factories.py` (`make_workspace`, `make_profile`). Build rows directly (add + flush): `Factory(workspace_id, name, abbreviation)`, `Machine(workspace_id, factory_id, name)`, `Item(workspace_id, name, name_normalized, unit)`, and `MachineItemLedger` with `workspace_id`, `machine_id`, `item_id`, `transaction_type`, `quantity`, `unit_cost`, `total_cost`, `qty_before`, `qty_after`, `source_type`, `performed_by`. The foreign keys do not require machine and item to be in the entry's workspace, so one machine id can have entries in two workspaces. Use that for isolation cases. The session runs with `autoflush=False`: flush before calling the DAO.
- **Timestamps:** always set `performed_at` explicitly. Insert rows in an order different from their time order (09:00, 11:00, 10:00) so that "newest first" cannot pass by accident.
- **BUG-640 / BUG-641 / BUG-664 proof:** a data-level tie can pass by chance, so it may not back a strict xfail. Prove them from the emitted SQL with the statement recorder of `test_ledger_manager.py`: today each list ends `ORDER BY machine_item_ledger.performed_at DESC`, then `LIMIT` / `OFFSET`; the two latest-entry lookups the same with `LIMIT 1`. Intended, the clause ends with `, machine_item_ledger.id DESC`. Assertion on the SQL → strict xfail. Data-level tie cases are extra, **non-strict** xfail. Shape: rows B (normal id), C (explicit id above `max(max id, last_value of machine_item_ledger_id_seq) + 1_000_000`), A (normal id), one `performed_at`, `qty_after` 15, 10, 99: intended order `[C, A, B]`, intended latest C. Observed today under three plans: `[B, C, A]`, latest B; this is not a guarantee.
- **`get_by_performer` (BUG-645):** the method does not exist; every call raises `AttributeError` today → strict xfail.
- **Q4 / BUG-992:** set the session zone in the test with `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))`, and use an entry at 12:00 with bounds 11:30Z–12:30Z. Today `[]`, deterministic under that zone → strict xfail. Control: the same bounds without `tzinfo` pass.
- **Q2 / BUG-990:** test the schema directly: `MachineItemLedgerResponse.model_validate(row)`. Today `pydantic.ValidationError` (`string_pattern_mismatch` on `transaction_type`) → strict xfail, one case per type. The eight allowed types pass today.
- **Database errors:** wrap calls expected to raise in `with db.begin_nested():`. The `ArgumentError` of `get_by_date_range` R4 is raised in Python before SQL is sent.
- Compare `Decimal` by value. Stored `0` and the `NULL` fallback both equal `Decimal("0.00")`.
- Rows of the 101-entry cases need distinct `performed_at` values.

## Not specified
- `MachineItemLedgerDAO.get_by_order` — dead code, to be removed (Q5, decided by Claude under the reviewer's delegation (2026-10-30))
- `machine_item_ledger_dao` — module-level singleton `MachineItemLedgerDAO(MachineItemLedger)`, no logic
- Inherited `BaseDAO` methods are specified in `tests/unit/dao/base.spec.md`; what this model changes is under "Inherited `BaseDAO` methods on `MachineItemLedger`" below.

The checklist marks none of these methods possibly unused (`get_consumption_entries` was already deleted). `get_by_order` is unmarked there but has no caller (Q5).

---

## `MachineItemLedgerDAO.get_by_item(db, *, item_id, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ItemSummaryService._recent_activity`, with `skip=0` and a `limit` of at least 5)

**Purpose:** One page of a catalog item's ledger entries across all machines, newest first.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `item_id` | int | equality on `item_id`; existence not checked |
| `workspace_id` | int | equality on `workspace_id`; always applied |
| `skip` | int, default `0` | rows to skip; not validated |
| `limit` | int, default `100` | max rows; not validated |

**Returns:** a `list` of `MachineItemLedger` instances (possibly empty).

**Rules:**
- **R1.** Only entries with that `workspace_id` and that `item_id` are returned. An entry of another workspace is never returned, even with the same `item_id` and `machine_id`. An unknown workspace or item id returns `[]`.
- **R2.** Entries of every machine, transaction type and performer are returned.
- **R3.** `item_id=0` and `item_id=None` return `[]`; no error.
- **R4.** Entries are ordered by `performed_at` descending, independent of `id` and insertion order: inserted at 09:00, 11:00, 10:00, they come back 11:00, 10:00, 09:00.
- **R4a.** [BUG-640] Entries with the same `performed_at` are ordered by `id` descending (HR-6). *(Today: no second sort key; tied entries come back in no fixed order.)*
- **R5.** `skip` and `limit` apply after filtering and ordering: with entries at 09:00, 10:00, 11:00, `skip=1, limit=1` returns exactly the 10:00 entry. By default at most the 100 newest entries are returned: given 101, exactly 100, and the oldest is missing.
- **R6.** `limit=0` returns `[]`; `skip` at or past the number of matching entries returns `[]`.
- **R7.** A negative `limit` or `skip` makes Postgres reject the query (see Errors).
- **R8.** ✅ (P1, P2) The machine's, its factory's and the item's state are not consulted: entries of a soft-deleted machine, of a machine in a soft-deleted factory and of a removed item are returned like any other.
- **R9.** The call writes nothing. Rows not yet flushed are not seen.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInLimitClause`, pgcode `2201W` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInResultOffsetClause`, pgcode `2201X` | `OFFSET must not be negative` |

**Side effects:** none

---

## `MachineItemLedgerDAO.get_by_machine_and_item(db, *, machine_id, item_id, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `LedgerManager.get_machine_ledger` when `item_id` is given, with no full date range and no transaction type ← `GET /ledgers/machine/`)

**Purpose:** One page of the entries of one item on one machine, newest first.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `machine_id`, `item_id`, `workspace_id` | int | equality on each; always applied; existence not checked |
| `skip`, `limit` | int | as in `get_by_item` |

**Returns:** a `list` of `MachineItemLedger` instances (possibly empty).

**Rules:**
- **R1.** Only entries matching all three of workspace, machine and item are returned. An entry differing in any one of them is never returned. A machine and item that exist but have no entry together return `[]`.
- **R2.** `machine_id=0` or `item_id=0` returns `[]`.
- **R3.** Order as `get_by_item` R4.
- **R3a.** [BUG-640] Ties as `get_by_item` R4a. *(Today: no second sort key.)*
- **R4.** Paging and its errors as `get_by_item` R5, R6, R7.
- **R5.** ✅ (P1, P2) Parent state is not consulted, as `get_by_item` R8.
- **R6.** The call writes nothing.

**Errors:** as `get_by_item`.

**Side effects:** none

---

## `MachineItemLedgerDAO.get_by_transaction_type(db, *, transaction_type, workspace_id, machine_id=None, item_id=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `LedgerManager.get_machine_ledger` when a non-empty transaction type is given with no full date range ← `GET /ledgers/machine/`; always with `machine_id`)

**Purpose:** One page of a workspace's entries of one transaction type, newest first, optionally narrowed to a machine and an item.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `transaction_type` | str | exact equality; not validated, not trimmed |
| `workspace_id` | int | always applied |
| `machine_id`, `item_id` | int \| `None` | `None` = no filter; `0` filters like any integer |
| `skip`, `limit` | int | as in `get_by_item` |

**Returns:** a `list` of `MachineItemLedger` instances (possibly empty).

**Rules:**
- **R1.** Only entries of the workspace (as `get_by_item` R1) whose `transaction_type` equals the argument **exactly** are returned: case-sensitive, nothing trimmed, `%` an ordinary character. With `consumption` entries: `consumption` finds them; `CONSUMPTION`, `consumption ` (trailing space), `consum%` and an unknown type return `[]`.
- **R2.** `transaction_type=""` and `transaction_type=None` return `[]`; no error.
- **R3.** ✅ (Q6) With `machine_id=None` and `item_id=None`, matching entries of every machine and item of the workspace are returned.
- **R4.** A given `machine_id` narrows to that machine; a given `item_id` narrows to that item; both combine with AND.
- **R4a.** `machine_id=0` and `item_id=0` filter like any other integer and return `[]`.
- **R5.** Order as `get_by_item` R4.
- **R5a.** [BUG-640] Ties as `get_by_item` R4a. *(Today: no second sort key.)*
- **R6.** Paging and its errors as `get_by_item` R5, R6, R7.
- **R7.** ✅ (P1, P2) Parent state is not consulted, as `get_by_item` R8.
- **R8.** The call writes nothing.

**Errors:** as `get_by_item`.

**Side effects:** none

---

## `MachineItemLedgerDAO.get_by_date_range(db, *, workspace_id, start_date, end_date, machine_id=None, item_id=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `LedgerManager.get_machine_ledger` when both dates are given ← `GET /ledgers/machine/`; `LedgerManager.get_item_movement_summary` when both dates are given, with no other filter and the default paging ← `GET /ledgers/reports/item-movement/{item_id}/`)

**Purpose:** One page of a workspace's entries performed within a time window, newest first, optionally narrowed to a machine and an item.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | always applied |
| `start_date` | `datetime` | lower bound, inclusive; required (R4) |
| `end_date` | `datetime` | upper bound, inclusive; required (R4) |
| `machine_id`, `item_id` | int \| `None` | as in `get_by_transaction_type` |
| `skip`, `limit` | int | as in `get_by_item` |

**Returns:** a `list` of `MachineItemLedger` instances (possibly empty).

**Rules:**
- **R1.** Only entries of the workspace (as `get_by_item` R1) with `start_date <= performed_at <= end_date` are returned; both bounds are inclusive and exact to the microsecond. Entries at 09:00, 10:00, 11:00: range 09:00 … 11:00 returns all three; range 09:00:00.000001 … 10:59:59.999999 returns only 10:00.
- **R2.** `start_date == end_date` returns exactly the entries at that instant. `start_date` later than `end_date` returns `[]`; no error.
- **R3.** Naive bounds are compared as stored UTC whatever the session's time zone.
- **R3a.** [BUG-992] (Q4) A time-zone-aware bound is converted to UTC before the comparison, so the result does not depend on the session's time zone: entry at 12:00, bounds 11:30Z and 12:30Z, session zone `America/New_York` → the entry is returned. The same conversion keeps out an entry outside the window: entries at 07:00, 12:00 and 18:00, bounds 11:30Z and 12:30Z → only 12:00, under any session zone. A naive bound next to an aware one stays as given. *(Today the stored value is read in the session zone, so the window moves: under `UTC` → 12:00; under `America/New_York` → 07:00, and 12:00 goes missing; under `Asia/Dhaka` → 18:00, and 12:00 goes missing. Aware start with naive end under `America/New_York`: 12:00 and 07:00.)*
- **R4.** `start_date=None` or `end_date=None` raises `sqlalchemy.exc.ArgumentError` before any query is sent. No caller does this today; the BUG-341 fix (each bound on its own) changes this rule.
- **R5.** Order as `get_by_item` R4.
- **R5a.** [BUG-640] Ties as `get_by_item` R4a. *(Today: no second sort key.)*
- **R6.** A given `machine_id` / `item_id` narrows the result exactly as `get_by_transaction_type` R4, R4a; with neither, entries of every machine and item in the window are returned.
- **R6a.** Paging and its errors as `get_by_item` R5, R6, R7.
- **R7.** ✅ (P1, P2) Parent state is not consulted, as `get_by_item` R8.
- **R8.** The call writes nothing.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `start_date` or `end_date` is `None` | `sqlalchemy.exc.ArgumentError` | starts with `Only '=', '!=', 'is_()', 'is_not()', 'is_distinct_from()', 'is_not_distinct_from()' operators can be used with None/True/False` |
| negative `limit` / `skip` | as `get_by_item` | as `get_by_item` |

**Side effects:** none

---

## `MachineItemLedgerDAO.get_by_machine(db, *, machine_id, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `LedgerManager.get_machine_ledger` with no item, full date range or transaction type ← `GET /ledgers/machine/`)

**Purpose:** One page of a machine's entries for all items, newest first.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `machine_id`, `workspace_id` | int | equality on each; always applied; existence not checked |
| `skip`, `limit` | int | as in `get_by_item` |

**Returns:** a `list` of `MachineItemLedger` instances (possibly empty).

**Rules:**
- **R1.** Only entries of that machine in that workspace are returned, for every item and transaction type. An entry with that `machine_id` in another workspace is never returned.
- **R2.** `machine_id=0`, an unknown id and a machine with no entries return `[]`.
- **R3.** Order as `get_by_item` R4.
- **R3a.** [BUG-640] Ties as `get_by_item` R4a. *(Today: no second sort key.)*
- **R4.** Paging and its errors as `get_by_item` R5, R6, R7.
- **R5.** ✅ (P1, P2) Parent state is not consulted, as `get_by_item` R8.
- **R6.** The call writes nothing.

**Errors:** as `get_by_item`.

**Side effects:** none

---

## `MachineItemLedgerDAO.calculate_balance(db, *, machine_id, item_id, workspace_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `LedgerManager.get_machine_balance` ← `GET /ledgers/machine/balance/`; `LedgerManager.reconcile_machine_item` ← `POST /ledgers/machine/reconcile/`)

**Purpose:** The current quantity and total value of one item on one machine, as recorded by the latest entry. Despite the name nothing is summed; the running figures of one row are read.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `machine_id`, `item_id`, `workspace_id` | int | equality on each; existence not checked |

**Returns:** a Python `tuple` `(quantity: int, total_value: Decimal)`.

**Definition — latest entry:** among rows matching all three arguments, the one with the greatest `performed_at` (ties: R4).

**Rules:**
- **R1.** With no matching entry, returns exactly `(0, Decimal("0.00"))`; `str(total_value) == "0.00"`.
- **R2.** Otherwise returns the latest entry's `(qty_after, value_after)`. Nothing is summed: earlier entries do not affect the result. Entries at 09:00 (30, 210.00), 11:00 (20, 120.00), 10:00 (10, 40.00) → `(20, Decimal("120.00"))`. Negative stored values are returned as they are: `(-3, Decimal("-12.50"))`.
- **R3.** An empty (`NULL`) `value_after` gives value `Decimal("0.00")` and keeps `qty_after`: `(5, NULL)` → `(5, Decimal("0.00"))`. A stored `0` gives the same value.
- **R4.** [BUG-641] When several entries share the greatest `performed_at`, the latest is the one with the greatest `id` (HR-6). *(Today: no second sort key; an arbitrary entry decides.)*
- **R5.** Only entries of the exact machine, item and workspace count; an entry differing in any one of them does not change the result, even when newer. When only such entries exist the result is R1.
- **R6.** ✅ (P3) Parent state is not consulted: the balance of a soft-deleted machine or a removed item is returned as in R2.
- **R7.** The call writes nothing. A row not yet flushed is not seen; after the flush it is.

**Errors:** none

**Side effects:** none

---

## `MachineItemLedgerDAO.get_latest_entry(db, *, machine_id, item_id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `inventory_movements.get_machine_unit_cost`, which prices every machine stock movement; `LedgerManager.reconcile_machine_item`, for the adjustment price)

**Purpose:** The most recent entry of one item on one machine.

**Inputs:** as `calculate_balance`.

**Returns:** the `MachineItemLedger` instance, or `None`.

**Rules:**
- **R1.** With no matching entry, returns `None`.
- **R2.** With entries of distinct `performed_at`, returns the one with the greatest `performed_at`, independent of `id` and insertion order; the full row is returned, with `avg_price_after` and `value_after` as stored (`None` when empty).
- **R3.** [BUG-664] When several entries share the greatest `performed_at`, the one with the greatest `id` is returned (HR-6). An older entry never wins, whatever its `id`. *(Today: no second sort key; an arbitrary entry wins.)*
- **R4.** Only entries of the exact machine, item and workspace are considered, as `calculate_balance` R5; when only others exist the result is `None`.
- **R5.** ✅ (P3) Parent state is not consulted, as `calculate_balance` R6.
- **R6.** The call writes nothing.

**Errors:** none

**Side effects:** none

---

## `MachineItemLedgerDAO.get_by_performer(db, *, performed_by, workspace_id, skip=0, limit=100)` — does not exist yet
**Shape:** list
**Persistence:** reads
**Visibility:** public (to be used by: `LedgerManager.get_transactions_by_user` ← `GET /ledgers/reports/user-transactions/{user_id}/`, which already calls it)

**Purpose:** One page of the entries one user performed in a workspace, newest first. Matches the existing `InventoryLedgerDAO.get_by_performer`.

**Rules:**
- **R1.** [BUG-645] Returns the entries with that `workspace_id` and `performed_by`, of every machine, item and transaction type. Entries of another performer, and the same user's entries in another workspace, are not returned; an unknown or `0` profile id returns `[]`. *(Today: the method does not exist; every call raises `AttributeError`, `'MachineItemLedgerDAO' object has no attribute 'get_by_performer'`.)*
- **R2.** [BUG-645] Order: `performed_at` newest first, then `id` descending (as `get_by_item` R4, R4a). Paging and its errors as `get_by_item` R5, R6, R7.

- **R3.** [BUG-645] Parent state is not consulted, as `get_by_item` R8 (per `InventoryLedgerDAO.get_by_performer` R6 and P1, P2); the performer's own profile state is not consulted either. The call writes nothing. *(Today: the method does not exist.)*
- **R4.** [BUG-645] `performed_by=None` returns `[]`; no error. The column is `NOT NULL`, so no entry has an empty performer. Not reachable from the API: the user id is a required path parameter. *(Today: the method does not exist.)*

**Errors:** as `get_by_item`, once it exists.

**Side effects:** none

---

## Inherited `BaseDAO` methods on `MachineItemLedger`
**Shape:** create / update / delete / get / list
**Persistence:** writes / reads
**Visibility:** public (used by: `create` with a dict ← the four writers in Model facts. `update`, `remove`, `get`, `get_multi`, `get_by_workspace`, `get_by_id_and_workspace`: no caller on this DAO)

**Purpose:** The base spec (`tests/unit/dao/base.spec.md`) applies; only what this model and its schemas change is stated.

**Rules:**
- **R1.** `create` with a dict holding the required columns saves the row: `performed_at` is set to a naive UTC `datetime` at flush (not patchable; assert it is set, has no `tzinfo`, and is within 5 minutes of the current UTC time), and the nullable columns are `None`. The change is flushed, not committed. Nothing is computed or cross-checked: `total_cost`, `qty_after`, the values and the prices are stored as given, within the column limits of R1a and R1b.
- **R1a.** A money column (`Numeric(15, 2)`: `unit_cost`, `total_cost`, `value_before`, `value_after`, `avg_price_before`, `avg_price_after`) stores 2 decimals. Postgres rounds a third decimal half away from zero, with no error: `1.005` → `1.01`, `1.004` → `1.00`, `1.015` → `1.02`, `1.025` → `1.03`, `2.675` → `2.68`, `0.125` → `0.13`, `0.0049` → `0.00`, `-1.005` → `-1.01`. A Python `float` `1.005` gives the same `1.01`. The instance returned by `create` keeps the value it was given until it is refreshed; a fresh read shows the stored one. This is also the owner's rule for all money (FU-6).
- **R1b.** A money value must round to an absolute value below 10^13: `9999999999999.99` and `9999999999999.994` store `9999999999999.99`; `9999999999999.995`, `10000000000000` and `-10000000000000` raise `DataError` in every money column and nothing is saved. An integer column takes −2147483648 … 2147483647; `2147483648` or `-2147483649` raises `DataError`. See Errors.
- **R2.** `create` with `MachineItemLedgerCreate` always fails: the schema has no `workspace_id` or `performed_by`, so the flush raises `IntegrityError` (`NotNullViolation` on `workspace_id`) and nothing is saved. No caller does this. Fields of the schema: required `machine_id`, `item_id`, `transaction_type` (the eight-type pattern), `quantity`, `unit_cost`, `total_cost` (each `>= 0`), `qty_before`, `qty_after`, `source_type`; optional, default `None`, `value_before`, `value_after`, `avg_price_before`, `avg_price_after`, `source_id`, `order_id`, `invoice_id`, the four `transfer_*` fields and `notes`. Unknown arguments, `workspace_id` and `performed_by` included, are ignored silently, so passing them does not change the outcome. Whether this input schema keeps its eight-type pattern is not specified (Q2; a BUG-990 fix may lift it): no test on it.
- **R3.** Unknown `workspace_id`, `machine_id`, `item_id`, `performed_by` or `invoice_id` raises `IntegrityError` (`ForeignKeyViolation`, with the constraint names in Model facts). `performed_by=None`, a missing `transaction_type` and any other missing NOT NULL column raise `IntegrityError` (`NotNullViolation`).
- **R4.** The database checks no values: any string as `transaction_type`, and negative `quantity`, `unit_cost`, `total_cost`, are saved. The column limits still apply. Machine and item need not belong to the entry's workspace.
- **R5.** Hard-deleting a machine or an item that has entries fails with `IntegrityError` (`RestrictViolation`, `machine_item_ledger_machine_id_fkey` / `machine_item_ledger_item_id_fkey`). Hard-deleting a profile with entries fails with `IntegrityError` (`NotNullViolation` on `performed_by`), because the foreign key's `SET NULL` hits the `NOT NULL` column.
- **R6.** [BUG-100] (HR-6) `get_by_workspace` returns the workspace's entries ordered by `id` ascending before `skip` / `limit`. *(Today: no ordering is requested; the fix is in `app/dao/base.py`.)*
- **R7.** "Immutable" is a convention: `update` changes any column given in a dict (e.g. `qty_after`), `update` with `MachineItemLedgerUpdate` changes `notes`, and `remove` hard-deletes an entry. Nothing in the application calls either.
- **R8.** `get` returns an entry of any workspace; `get_by_id_and_workspace` returns `None` for an entry of another workspace (base spec).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| missing NOT NULL column, or any `MachineItemLedgerCreate` | `sqlalchemy.exc.IntegrityError`; `.orig` is `psycopg2.errors.NotNullViolation` | contains `column "<name>"`; the rest not asserted |
| unknown foreign key | `IntegrityError`; `.orig` is `psycopg2.errors.ForeignKeyViolation` | contains the constraint name; the rest not asserted |
| hard delete of a referenced machine or item | `IntegrityError`; `.orig` is `psycopg2.errors.RestrictViolation` | contains the constraint name; the rest not asserted |
| hard delete of a profile with entries | `IntegrityError`; `.orig` is `psycopg2.errors.NotNullViolation` | contains `column "performed_by"`; the rest not asserted |
| money value beyond R1b | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.NumericValueOutOfRange`, pgcode `22003` | `numeric field overflow` |
| integer value beyond R1b | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.NumericValueOutOfRange`, pgcode `22003` | `integer out of range` |

**Side effects:** as in the base spec.

---

## `GET /ledgers/machine/` — what this DAO's rows go through
**Shape:** mapper
**Persistence:** pure
**Visibility:** public (`app/api/v1/endpoints/ledgers.py`, with `response_model=list[MachineItemLedgerResponse]`)

**Purpose:** Not code of this file. Stated here because these two defects are invisible at the DAO: its rows and its comparison are correct, and the user-visible result is not.

**Rules:**
- **R1.** [BUG-990] (Q2) `MachineItemLedgerResponse` accepts every stored transaction type, so one row never fails a page: `model_validate` of a row of type `purchase_return`, `consumption_reversal`, `work_order_install`, `work_order_replace_out`, `work_order_replace_in` or `work_order_borrow_returned` succeeds and keeps the type. *(Today: `pydantic.ValidationError` `string_pattern_mismatch`, and over HTTP 500 for the whole page. The eight types `purchase_order`, `manual_add`, `transfer_in`, `transfer_out`, `consumption`, `damaged`, `inventory_adjustment`, `cost_adjustment` already pass.)*
- **R1a.** The other fields of the response hold today and stay: every field of `MachineItemLedgerCreate` (inherited R2), plus required `id`, `workspace_id`, `performed_by`, `performed_at`, read from attributes. `order_type` is not in the response. `quantity`, `unit_cost`, `total_cost` must be `>= 0`: a stored negative value raises `pydantic.ValidationError` `greater_than_equal` (no writer of the application stores one). Other columns have no limit: a negative `qty_before`, `qty_after`, `value_after` or `avg_price_after` and any `source_type` pass.
- **R2.** [BUG-991] (Q3) Integration-only: an `end_date` sent with no time covers that whole day: entries at 29 Sep 10:00 and 30 Sep 10:00, `start_date=2026-09-30&end_date=2026-09-30` returns the 30 Sep entry; an `end_date` with a time stays exact. *(Today: `[]`; a date with no time becomes midnight.)*

**Errors:** none intended. *(Today: `fastapi.exceptions.ResponseValidationError`, 500, under R1.)*

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 19, 35, 66, 116, 143, 172, 202 | keyword-only parameters | Notes for the test designer |
| 19, 36, 69, 119, 144 | defaults `skip=0`, `limit=100` | `get_by_item` R5; pointers in each list |
| 24–27 | `workspace_id` + `item_id` filter; no join; `None` / `0` match nothing | `get_by_item` R1, R2, R3, R8 |
| 28 | `ORDER BY performed_at DESC` only (BUG-640) | `get_by_item` R4, R4a |
| 29–31 | offset / limit after filter + order; `limit=0`; past the end; negative; empty / one / many | `get_by_item` R5, R6, R7, R9, Errors |
| 54–58 | three-key filter; no join | `get_by_machine_and_item` R1, R2, R5, R6 |
| 59 | `ORDER BY performed_at DESC` only (BUG-640) | `get_by_machine_and_item` R3, R3a |
| 60–62 | offset / limit | `get_by_machine_and_item` R4 |
| 76–79 | `workspace_id` + exact `transaction_type` (`""` / `None` match nothing); no join | `get_by_transaction_type` R1, R2, R7, R8 |
| 80 | `if machine_id is not None:` — given / `0` / `None` (`None` unreachable from the API, Q6) | `get_by_transaction_type` R3, R4, R4a |
| 82 | `if item_id is not None:` — given / `0` / `None` | `get_by_transaction_type` R3, R4, R4a |
| 85 | `ORDER BY performed_at DESC` only (BUG-640) | `get_by_transaction_type` R5, R5a |
| 86–88 | offset / limit | `get_by_transaction_type` R6 |
| 91–113 | `get_by_order`: no caller | not specified, dead code (Q5) |
| 126–130 | `workspace_id`, `>= start_date`, `<= end_date`: inclusive; equal; reversed; `None` → `ArgumentError`; aware bounds (BUG-992); no join | `get_by_date_range` R1, R2, R3, R3a, R4, R7, R8 |
| 131 | `if machine_id is not None:` — given / `0` / `None` | `get_by_date_range` R6 |
| 133 | `if item_id is not None:` — given / `0` / `None` | `get_by_date_range` R6 |
| 136 | `ORDER BY performed_at DESC` only (BUG-640) | `get_by_date_range` R5, R5a |
| 137–139 | offset / limit | `get_by_date_range` R6a |
| 161–164 | two-key filter; no join | `get_by_machine` R1, R2, R5, R6 |
| 165 | `ORDER BY performed_at DESC` only (BUG-640) | `get_by_machine` R3, R3a |
| 166–168 | offset / limit | `get_by_machine` R4 |
| 187–192 | three-key filter; no join | `calculate_balance` Definition, R5, R6, R7 |
| 193–194 | `ORDER BY performed_at DESC`, first row (BUG-641) | `calculate_balance` R2, R4 |
| 197 | `if entry:` found / not found | `calculate_balance` R1, R2 |
| 198 | `entry.value_after or Decimal('0.00')` — value / `0` / `NULL` | `calculate_balance` R2, R3 |
| 199 | no entry → `(0, Decimal('0.00'))` | `calculate_balance` R1 |
| 217–222 | three-key filter; no join; found / other / none | `get_latest_entry` R1, R2, R4, R5, R6 |
| 223–224 | `ORDER BY performed_at DESC`, first row (BUG-664) | `get_latest_entry` R2, R3 |
| 228 | module singleton | Not specified |
| — | `get_by_performer` missing (BUG-645) | `get_by_performer` R1, R2 |
| `base.py` 76–84 | `create`: dict / schema; Python default; FK and NOT NULL errors | inherited R1, R2, R3, R4 |
| `models/machine_item_ledger.py` 32–33, 39–40, 45–46; 27, 37–38 | `Numeric(15, 2)`: third decimal, over limit; `Integer` range | inherited R1a, R1b, Errors |
| `base.py` 108–119 | `update`: schema / dict | inherited R7 |
| `base.py` 136–139 | `remove`: hard delete | inherited R5, R7 |
| `base.py` 43, 187–194 | `get` / `get_by_id_and_workspace` raw | inherited R8 |
| `base.py` 161–167 | `get_by_workspace` no `ORDER BY` (BUG-100) | inherited R6 |
| `schemas/machine_item_ledger.py` 12 | pattern inherited by the response schema (BUG-990) | `GET /ledgers/machine/` R1 |
| `schemas/machine_item_ledger.py` 13–15 | `ge=0` on `quantity`, `unit_cost`, `total_cost` | `GET /ledgers/machine/` R1a |
| `endpoints/ledgers.py` 48–49 | `datetime` query parameters: a date with no time becomes midnight (BUG-991) | `GET /ledgers/machine/` R2 |

## Gap log
G1 (`machine_item_ledger.cases.md` gap 1) — Fact — inherited R2 lists the fields of `MachineItemLedgerCreate`; unknown arguments are ignored silently.
G2 (gap 2) — Fact — new `GET /ledgers/machine/` R1a: the response's other fields and limits.
G3 (gap 3) — Fact — new inherited R1a (third decimal), R1b (limits); two Errors rows; R1 reworded. Money choice raised in FU-6; the owner answered "Half up" the same day (BUG-1040).
G4 (gap 4) — Intent — new `get_by_performer` R3, per `InventoryLedgerDAO.get_by_performer` R6, P1, P2; decided by Claude under the reviewer's delegation (2026-10-30).
G5 (gap 5) — Intent — new `get_by_performer` R4; the inventory rule (`None` → `IS NULL`) gives `[]` here because the column is `NOT NULL`; decided by Claude under the reviewer's delegation (2026-10-30).
G6 (gap 6) — Test mechanics — the keyword-only note stays a note, no card, as in the item tag spec; decided by Claude under the reviewer's delegation (2026-10-30).
G7 (gap 7) — Intent — the loose checks are accepted: inherited Errors now say which text is contained, as the item tag cases do; decided by Claude under the reviewer's delegation (2026-10-30).
G8 (gap 8) — Intent — "close to now" = within 5 minutes, as the item tag cases; inherited R1; decided by Claude under the reviewer's delegation (2026-10-30).
G9 (gap 9) — Fact — `get_by_date_range` R3a covers an entry that wrongly appears; verified, and MIL-DR-19's reading is right.
G10 (gap 10) — Fact — the BUG-341 line pointed at stale rule numbers; corrected to R4 and Errors row 1.
G11 (gap 11) — Contradiction — inherited R2's sentence on the six types replaced: the input schema's pattern is not specified and gets no test; decided by Claude under the reviewer's delegation (2026-10-30).
