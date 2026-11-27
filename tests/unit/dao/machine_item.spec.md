# Spec — `app/dao/machine_item.py`

> **Status:** APPROVED (2026-10-30; nothing open)
> **Source commit:** e48a092

> **Review round 2026-10-30.** **The owner's own answer:** Q1 — bug, verbatim: *"write a scrip to clean up this data and going forward prevent duplicates"*: one row per workspace + machine + item, enforced by a unique index (BUG-983). The cleanup is `scripts/merge_duplicate_machine_items.py`. **Delegated:** every suggested answer accepted — P1–P7 (decided by Claude under the reviewer's delegation (2026-10-30)). None of these is the owner's own answer. How a violation surfaces at the DAO, and restating BUG-978, were also decided by Claude under the reviewer's delegation (2026-10-30). The house-rule lines stand.
>
> **Revision 2026-10-30, for the case designer:** `get_by_machine_and_item` R5 is no longer tagged and needs no case (BUG-978 is superseded by BUG-983). Inherited R4 is rewritten to the intended behavior; R4a and R4b are new. `get_by_machine` R10 and `get_by_item` R8 are restated and need no case. ✅ added to the rules of P5 and P6.

> **Standing reviewer decisions applied here (not asked again):**
> 1. Soft-deleted rows are kept but must not show up in lists or be counted (inventory DAO Q2, owner's words 2026-10-10: "Soft-deleted things should not show up. We keep the information, but it is not used for anything counted.").
> 2. Things of a soft-deleted parent are **hidden by the parent's state, their own rows untouched** ("hidden, not cascaded", 2026-10-11). `machine_items` has no soft-delete column of its own; its parents are the machine, the machine's factory and the catalog item. For an item, "removed" means `items.is_active = False` (items have no `is_deleted`).
> 3. Raw lookups stay raw (HR-4 scope; base DAO spec). A single-row lookup used for get-or-create or for a check must see the row whatever its parents' state (inventory DAO Q6 scope decision, Q8, Q9).
> 4. Physical row order and collation order are **not** an order: a missing `ORDER BY` is a bug, and no order recipe in this spec is called deterministic.
> 5. A stock row has no name of its own. The stock page's order (BUG-701) is item name case-insensitive, then row `id`; rows with no name to sort by use `id` ascending (BUG-906).
>
> **Verified by running** (throwaway scripts `mitem_h.py`, `mitem_p0.py`, `mitem_p1.py`, `mitem_p2.py` in the session scratchpad, each in one transaction rolled back against `marker_test`; nothing committed): every "Today:" note below; the table's columns, nullability, defaults (only `id` has a database default), constraints and indexes (primary key, four plain indexes, **no unique index on the machine + item pair**, no check constraint, no trigger, no table references `machine_items`); that the four list / pair queries carry no `ORDER BY` and no `FOR UPDATE`; defaults and caps (101 rows → 100 from `get_by_workspace` and `get_by_machine`; 501 rows → 500 from `get_by_item`, 501 with an explicit `limit=1000`); negative paging errors; `limit=0`; own / other / unknown workspace and id; rows of a soft-deleted machine, of a machine in a soft-deleted factory, of an inactive machine, of an inactive factory and of a removed item in all five methods; the item summary's output for those rows; two rows for one pair, including that the row returned changes after the first one is updated, and a real stock-out refused because of the split; inherited `create`, `update`, `remove`, `get`, `get_multi`; no extra query for `item_name` / `item_unit`; the foreign-key blocks on hard-deleting a machine or item. **Index trial** (`mitem_p3.py`; the DDL too was rolled back and no index was left behind): the unique index cannot be built while duplicates exist (`UniqueViolation`); after `merge_duplicates` from `scripts/merge_duplicate_machine_items.py` it builds; then `create` of a taken key and `update` moving a row onto a taken key raise `IntegrityError` with `UniqueViolation`, pgcode `23505`, and the moved row is unchanged; the same machine + item under another `workspace_id`, another item and another machine are all accepted; a failed insert with no savepoint of its own leaves the session unusable (`PendingRollbackError`). **Not run:** anything over HTTP; two concurrent transactions (commits are not allowed); the intended behavior of the other bug rules; the script's dry-run or `--apply` path against production data.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | Nothing stops two stock rows for the same machine and item. If it happens the stock is split, and every movement uses one of the two rows, whichever the database returns first | bug — one row per workspace + machine + item, unique index; existing duplicates merged by `scripts/merge_duplicate_machine_items.py` first (BUG-983) | **Owner**, 2026-10-30 |
| P1 | "Stock of this machine" still lists the stock of a deleted machine, or of a machine in a deleted factory | bug — hidden, rows untouched (BUG-979) | Claude, delegated |
| P2 | "Stock of this machine" still lists stock of an item removed from the catalog | bug — hidden, rows untouched (BUG-980) | Claude, delegated |
| P3 | The item summary still lists and counts placements on deleted machines and in deleted factories | bug — hidden, rows untouched (BUG-981) | Claude, delegated |
| P4 | The item summary silently stops at 500 machines | bug — no cap (BUG-982) | Claude, delegated |
| P5 | Looking up one stock row by id, or by machine + item, also finds rows of deleted parents | intended — raw lookups, stock posting needs them | Claude, delegated |
| P6 | The workspace-wide stock list has no hiding of its own | intended at the DAO; the machine item manager must hide (FU-1 (a)) | Claude, delegated |
| P7 | The paging options of "machines holding this item" are never used | remove, together with BUG-982 | Claude, delegated |

Decided by house rules: no sort order on three lists (BUG-100, BUG-976, BUG-977). The sort-order line on the machine + item lookup (BUG-978) is superseded by Q1: see that line.

### House-rule violations — applied automatically

- **HR-6** `get_by_workspace` R3 — no sort order; paging with `skip` / `limit` can repeat or skip stock rows. Intended for this raw lookup (HR-6: "generic `BaseDAO` lists only guarantee `id` ascending"): `id` ascending before `skip` / `limit`. This method is a line-for-line copy of `BaseDAO.get_by_workspace` and **shadows** it, so the BUG-100 fix in `app/dao/base.py` does not reach it: the same fix must be made here, or the copy deleted (same situation as `DAOFactory.get_by_workspace`). The display order of `GET /machine-items/` is the manager's (FU-1 (a)).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-100 (existing, pattern `unordered-pagination`) — no new ID; its Module cell now names this override too. Rules: `get_by_workspace` R3.
- **HR-6** `get_by_machine` R6 — no sort order. This is the DAO's own paged query behind `GET /machine-items/?machine_id=…`, so the order has to be in the query. Intended: item name case-insensitive ascending, then row `id` ascending, before `skip` / `limit` (the stock page's order, BUG-701).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-976 (pattern `unordered-pagination`; the fix is in `app/dao/machine_item.py`). Rules: `get_by_machine` R6.
- **HR-6** `get_by_item` R6 — no sort order. The rows are all of one item, and the only caller re-sorts everything it gets. Intended: row `id` ascending (BUG-906 precedent: no name to sort by).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-977 (pattern `unordered-pagination`; the fix is in `app/dao/machine_item.py`). Rules: `get_by_item` R6.
- **HR-6** `get_by_machine_and_item` R5 — a top-1 read with no sort order. Nothing prevents two rows for one pair today, and then the row returned is whatever the database produces. Verified: rows 4 and 6 of one pair; the first row is returned; after that row is updated, the second row is returned.
**Answer:** bug — per HR-6 (house rule); overtaken by the owner's answer to Q1
**Resolution:** BUG-978 (pattern `unordered-pagination`) is **superseded by BUG-983**: with the unique index a key has at most one row, so the lookup has nothing to order and no `ORDER BY` is needed. Its row in `docs/testing/bugs.md` stays with status `superseded by BUG-983`; no rule carries the tag. decided by Claude under the reviewer's delegation (2026-10-30). Rules: `get_by_machine_and_item` R5 (restated).

Checked and **not** a new line here: **HR-10** — `get_by_machine_and_item` reads the stock row without a lock, and three callers then change stock. That is already logged against the callers (BUG-661 `_machine_out` / `_machine_in`, BUG-643 `reconcile_machine_item`, BUG-820 transfer orders); the fix needs a locked variant of this read (FU-3 (a)). The plain read stays for callers that change nothing. **HR-4** — handled in P1–P3, P5, P6. **HR-5** — every filter here is in the query; the fixes of BUG-979, BUG-980, BUG-981 must stay in the query. **HR-7** — `GET /machine-items/` already requires `1 <= limit <= 1000` and `skip >= 0`. **HR-8** — no `LIKE`. **HR-1, HR-2, HR-3** — no names or free text. **HR-9** — the table has no audit columns.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-10-30)

### P1. "Stock of this machine" still lists stock of a deleted machine — 🐞 BUG-979
**Background:** `machine_items` holds the quantity of one catalog item on one machine. Machines and factories are soft-deleted (`is_deleted = True`, row stays). The owner ruled for factory stock that things in a soft-deleted factory must not show up or be counted (BUG-882), and for machines that they are hidden by the parent's state and never altered (BUG-890, BUG-891). `GET /machine-items/?machine_id=…` reads through `get_by_machine`. Today a machine with stock can be deleted (BUG-968 will refuse that), and a factory's delete leaves its machines' stock as it is.
**What happens today:** `get_by_machine` looks only at `machine_items`. The rows of a soft-deleted machine, or of a live machine in a soft-deleted factory, are returned. (Verified: both returned.)
**Example:** Machine "Press 4" holds 7 bearings and is deleted. `GET /machine-items/?machine_id=<Press 4>` still answers with the 7 bearings, although the machine is no longer on the machines page.
**Rules affected:** `get_by_machine` R4a, R4b, R4c
**Answer:** bug — per BUG-890 / BUG-882 precedent: the rows of a soft-deleted machine, or of a machine whose factory is soft-deleted, are not returned; an inactive-but-live machine or factory hides nothing; no row is changed, so they are back unchanged once the parent is live
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-30): 🐞 BUG-979 (pattern `join-ignores-soft-deleted`). Rules: `get_by_machine` R4a, R4b (tagged), R4c (untagged — what already holds).

### P2. "Stock of this machine" still lists stock of an item removed from the catalog — 🐞 BUG-980
**Background:** A catalog item is removed by setting `is_active = False`. For factory stock the same case was ruled a bug: stock of a removed item is left out of the list, with or without an `item_id` filter, and the row stays (BUG-883).
**What happens today:** `get_by_machine` returns the row of a removed item like any other, and it uses up a place in the page. (Verified.)
**Example:** Machine "Press 4" holds Bolt (5) and removed item "Old Gasket" (3). The machine's stock list shows both.
**Rules affected:** `get_by_machine` R5, R5a
**Answer:** bug — per BUG-883 precedent: a row whose item has `is_active = False` is not returned and takes no place in the page; the row is untouched
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-30): 🐞 BUG-980 (pattern `join-ignores-soft-deleted`). Rules: `get_by_machine` R5 (tagged), R5a (untagged — what already holds).

### P3. The item summary still lists and counts machines that were deleted — 🐞 BUG-981
**Background:** The item summary page lists the machines holding an item ("placements") and shows how many there are. It reads them through `get_by_item`, which looks only at `machine_items`. The same gap was ruled a bug for factory stock on this page (BUG-884).
**What happens today:** A row of a soft-deleted machine is returned, and the summary shows it as `Machine #<id>`, factory `—`, `factory_id` 0, and counts it in `machine_placement_count`. A row of a machine in a soft-deleted factory is shown with its full name and factory. (Verified through `ItemSummaryService._machine_placements`: 3 rows for one live machine, one deleted machine, one machine in a deleted factory.)
**Example:** "Bearing 6204" is on Press 1 (live) and Press 4 (deleted). The page says 2 machines and shows a row "Machine #4127" with factory "—".
**Rules affected:** `get_by_item` R3a, R3b, R3c
**Answer:** bug — per BUG-884 precedent: the rows of a soft-deleted machine, or of a machine whose factory is soft-deleted, are not returned; an inactive-but-live machine or factory hides nothing; no row is changed
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-30): 🐞 BUG-981 (pattern `join-ignores-soft-deleted`). Own ID, not an extension of BUG-979: different method, different API surface (same split as BUG-882 / BUG-884). Rules: `get_by_item` R3a, R3b (tagged), R3c (untagged — what already holds).

### P4. The item summary silently stops at 500 machines — 🐞 BUG-982
**Background:** `get_by_item` has a default `limit` of 500, and its only caller passes none. The rows have no order (BUG-977), so which machines survive is arbitrary. `InventoryDAO.get_by_item`, the sibling on the same page, has no cap. Hidden caps were ruled bugs before (BUG-342, BUG-709).
**What happens today:** Given 501 machines holding one item, 500 rows come back and the summary says 500. (Verified; `limit=1000` returns 501.)
**Example:** A consumable sits on 620 machines. The summary shows 500 and "500 machines", and a low-stock machine may be among the 120 left out, with nothing to tell the user the list is cut.
**Rules affected:** `get_by_item` R5
**Answer:** bug — per BUG-342 precedent: all matching rows are returned, no cap
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-30): 🐞 BUG-982 (pattern `silent-result-cap`). Rules: `get_by_item` R5.

### P5. Looking up one stock row also finds rows of deleted parents — ✅ intended
**Background:** `get_by_id_and_workspace` and `get_by_machine_and_item` do not look at the machine, the factory or the item. The second one is the "find the row" step of every machine stock movement (`ensure_machine_item`), of reconcile, of the work-order replace check and of the duplicate check on `POST /machine-items/`. On factory stock the same lookups were ruled raw: get-or-create must still see an existing row (inventory DAO Q6 scope decision, Q9).
**What happens today:** Both return the row whatever the state of its parents. (Verified.)
**Example:** Stock of a deleted machine is reconciled, or a stock movement names that machine: the existing row is found and used. If it were hidden, a second row would be created for the pair.
**Rules affected:** `get_by_id_and_workspace` R4, `get_by_machine_and_item` R4
**Answer:** intended — per HR-4 scope and inventory DAO Q6 / Q9 precedent: raw single-row lookups. What `GET /machine-items/{id}/`, update and delete do with such a row is the manager's decision (FU-1 (f))
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-30): rules unchanged. Rules: `get_by_id_and_workspace` R4 ✅, `get_by_machine_and_item` R4 ✅, `get_by_item` R4 ✅ (same scope decision).

### P6. The workspace-wide stock list has no hiding of its own — ✅ intended
**Background:** `GET /machine-items/` without `machine_id` reads through `get_by_workspace`. This method is a line-for-line copy of the base method, and HR-4 keeps `get_by_workspace` raw and says to flag the manager that exposes the result. BUG-924 did exactly that for sections. This list is the method's only caller, so nothing needs it to be raw; the choice is only where the fix lives.
**What happens today:** Rows of deleted machines, of machines in deleted factories and of removed items are all returned. (Verified.)
**Example:** `GET /machine-items/` lists the 7 bearings of deleted "Press 4". P1 fixes the same list only when `machine_id` is given.
**Rules affected:** `get_by_workspace` R2
**Answer:** intended at the DAO — per HR-4 scope and BUG-924 precedent: `get_by_workspace` stays raw; `MachineItemManager.list_machine_items` must hide these rows (HR-5: in the query, before paging), to be logged in that manager's spec (FU-1 (a))
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-30): rule unchanged; no bug is logged against this DAO. Rules: `get_by_workspace` R2 ✅.

### P7. The paging options of "machines holding this item" are never used — 🗑️ remove
**Background:** `get_by_item` has `skip` and `limit`. Its only caller, the item summary, passes neither (`tests/test_item_summary_empty.py` patches the whole method). With no cap (P4) they have no job left. The same case was ruled `remove` for the machine and inventory DAOs (machine DAO Q6, inventory DAO Q5).
**What happens today:** `skip` can never be anything but 0 and `limit` never anything but 500 in production.
**Example:** No API request or job can reach a second page.
**Rules affected:** `get_by_item` (the two parameters only)
**Answer:** remove — per machine DAO Q6 precedent: the two parameters and their `.offset` / `.limit`, in the same change as BUG-982
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-30): the two parameters are not specified (the method stays specified); listed under **Not specified** and in `docs/testing/dead-code-removal-checklist.md` (`app/dao/machine_item.py:64,73-74`). Not a bug — no BUG ID.

### New questions

### Q1. Two stock rows for the same machine and item — 🐞 BUG-983 (owner)
**Background:** Every lookup treats machine + item as one stock row, and `POST /machine-items/` answers 409 "This item already exists on this machine". That check is a Python read before the insert, and `ensure_machine_item` (used by every stock movement) is also read-then-insert. The table has **no unique index** on the pair, unlike factory stock, where one row per bucket is enforced. Two requests at the same moment can both find nothing and both insert.
**What happens today:** A second row for the pair is accepted. Lists then show the item twice, and each movement uses one row, whichever the database returns first (BUG-978). The stock is split and no single row shows the real quantity. (Verified: rows of 4 and 6 are stored.)
**Example:** Press 1 has two rows for Bearing 6204: 4 and 6, so 10 on the machine. A stock-out of 5 reads one row and answers 400 "Insufficient machine stock (4 available, 5 requested)" (verified), although 10 are there.
**Rules affected:** inherited R4, R4a, R4b; `get_by_machine_and_item` R5, `get_by_machine` R10, `get_by_item` R8 (restated)
**Suggested answer:** `bug — at most one row per workspace + machine + item, enforced by a unique index; POST /machine-items/ and ensure_machine_item turn a violation into the existing behavior (409, or re-read the row)`. **The owner must also decide what happens to duplicates already in the data**, because the index cannot be created while they exist. Suggestion: a migration merges each pair into its lowest-`id` row, adding up `qty` and `defective_qty`, keeping the lowest-`id` row's `req_qty` when it has one, then reconcile runs against the ledger. Whether production holds any duplicates is unknown; this query tells: `SELECT workspace_id, machine_id, item_id, count(*) FROM machine_items GROUP BY 1, 2, 3 HAVING count(*) > 1`. Alternative: `intended` — then BUG-978 keeps movements on the lowest-`id` row and the rest of a split stays unusable until someone merges it by hand.
**Answer:** bug — "write a scrip to clean up this data and going forward prevent duplicates" (owner, 2026-10-30): one row per workspace + machine + item, enforced by a unique index.
**Resolution:** 🐞 BUG-983 (pattern `python-only-uniqueness`). **Cleanup:** `scripts/merge_duplicate_machine_items.py`, dry run by default, `--apply` to commit. It keeps the lowest `id`, adds up `qty` and `defective_qty`, keeps that row's `req_qty` or the first one set on a later row, prints pairs whose merged `qty` differs from the ledger balance, and posts no adjustments. **The fix must run it before creating the index:** the index cannot be built while duplicates exist (verified). **At the DAO (decided by Claude under the reviewer's delegation (2026-10-30)):** a violation is not caught or translated: `create`, or `update` moving a row onto a taken key, raises `sqlalchemy.exc.IntegrityError` at the flush (`.orig` is `psycopg2.errors.UniqueViolation`, pgcode `23505`). This matches every other constraint on this DAO (inherited R3), and the DAO cannot know the right answer: `POST /machine-items/` must answer 409, a stock movement must carry on with the existing row. Those two belong to the BUG-983 fix and are tested in their own modules (FU-1 (h), FU-3 (c)). The index is not partial (the table has no soft-delete column) and includes `workspace_id`, so it matches the lookups' key. Rules: inherited R4, R4a (tagged), R4b (untagged — what stays allowed); `get_by_machine_and_item` R5, `get_by_machine` R10, `get_by_item` R8 (restated, no case).

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Machine item manager, service, endpoint** (`app/managers/machine_item_manager.py`, next in this group) | (a) `list_machine_items` without `machine_id` shows rows of deleted machines, of machines in deleted factories and of removed items (P6), and needs a display order before paging: item name case-insensitive, then `id` (BUG-701 precedent; BUG-100 only gives `id`). A filtered query is needed, which may replace the `get_by_workspace` copy. (b) `if machine_id:` treats `0` as "no filter": `GET /machine-items/?machine_id=0` lists the whole workspace (verified). (c) `create_machine_item` never checks the item: an item of **another workspace** is accepted and the response then shows that item's name and unit (verified at DAO level: the row's `item_name` is the other workspace's name), a removed item is accepted and then hidden (P2; same conflict as BUG-883 with `create_inventory`), an unknown id is a foreign-key error. (d) **OWNER, stock:** `MachineItemCreate` / `MachineItemUpdate` have no `ge=0`, so a negative `qty`, `req_qty` or `defective_qty` is stored (inherited R5; BUG-711 precedent for factory stock), and `qty` beyond 32 bits is a `DataError`. (e) `req_qty` and `defective_qty` cannot be cleared through the API (`null` = leave unchanged, inherited R7): a machine's target cannot be taken away once set. (f) `get_machine_item`, `update_machine_item`, `delete_machine_item` use the raw lookup: what they answer for a row of a deleted machine, a machine in a deleted factory or a removed item (BUG-966 precedent: 404 by default). (g) **HR-10, stock:** `update_machine_item` reads without a lock and writes an absolute `qty`; two adjustments at once, or an adjustment during a stock movement, lose a change and record a stale `qty_before`. (h) BUG-983: a lost race on the duplicate check must answer 409 `This item already exists on this machine. Update the existing record instead.`, never 500. | P1, P2, P5, P6, Q1 |
| FU-2 | **Item summary service** (`app/services/item_summary_service.py`) | (a) After BUG-981 the fallbacks `Machine #<id>`, `factory_id` 0 and `—` in `_machine_placements` can no longer be reached by a deleted machine: check whether anything still reaches them. (b) `_inventory_rows` skips rows with `qty <= 0`; `_machine_placements` keeps them, so `machine_placement_count` counts a machine holding none of the item. A zero row with a `req_qty` is a real "low stock" line, so this may be intended. (c) A removed item's own summary still lists its placements (`get_by_item` R4, by the inventory DAO Q6 scope decision). | P3 |
| FU-3 | **Stock movements and reconcile** (`app/managers/inventory_movements.py`, `app/managers/ledger_manager.py`) — specs already approved | (a) The fixes of BUG-661, BUG-643, BUG-820 need a locked read of the pair: a new option on `get_by_machine_and_item` or a query of their own. The default read here stays unlocked. (b) **Must be updated with the BUG-983 fix:** `ensure_machine_item` R4 ("one of them, unspecified") in `tests/unit/managers/inventory_movements.spec.md` becomes unreachable, and its case EMI-07 (`test_invm_emi_07__duplicate_rows_first_match_returned` in `tests/unit/managers/test_inventory_movements.py`) inserts two rows for a key, so it will fail once the index exists. (c) BUG-983: `ensure_machine_item` must carry on with the existing row when it loses the insert race. The insert needs its own savepoint or `ON CONFLICT DO NOTHING`: a bare failed insert leaves the whole stock movement's transaction unusable (verified: `PendingRollbackError`). | HR-10 line, Q1 |
| FU-4 | **Item manager, machine manager** (`delete_item` BUG-948, `delete_machine` BUG-968) | Both count a `machine_items` row with `qty ≠ 0` as a blocker whatever the state of its machine (owner, by id only). After P1–P3, a row of a deleted machine can block an item delete and appear in the refusal's `blockers` while no list shows it; `GET /machine-items/{id}/` still does (raw). **OWNER, stock**, if the blocker list should treat such rows differently. | P1, P3 |

## Overview
`DAOMachineItem` reads `machine_items`, the per-machine stock snapshot: one row per machine and catalog item, holding the quantity on the machine (`qty`), the wanted quantity (`req_qty`) and the defective count (`defective_qty`). The ledger (`machine_item_ledger`) is the record of movements; this row is the current figure. Callers: `MachineItemManager` (`GET`, `POST`, `PUT`, `DELETE /machine-items/`); `ensure_machine_item` in `app/managers/inventory_movements.py` (every machine stock movement: purchase receipts, transfers, work orders); `WorkOrderManager` (on-hand check on a `REPLACE` line); `LedgerManager.reconcile_machine_item`; `ItemSummaryService` (placements on the item summary page). It is meant to protect workspace isolation (every method of this file filters on the row's `workspace_id`). It validates nothing, writes nothing of its own, and never commits; writes come from the inherited `create`, `update`, `remove`, which flush. `get_by_workspace` and `get_by_id_and_workspace` are line-for-line copies of the base methods: they are specified here because they are what runs, and a fix made only in `app/dao/base.py` does not reach them.

**Callables:** 5 specified (+ 1 section on inherited `BaseDAO` behavior specific to this model) · 1 not specified
**Externals to mock:** none. No method reads the clock; the table has no timestamps.
**Integration-only behavior:** none. (`skip >= 0`, `1 <= limit <= 1000` are enforced by `GET /machine-items/`, not here. A row lock cannot be observed with one connection; there is no lock rule here.)

**Model facts (table `machine_items`, class `app.models.machine_item.MachineItem`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE (`machine_items_workspace_id_fkey`) | — |
| `machine_id` | Integer NOT NULL, FK `machines.id`, no cascade (`machine_items_machine_id_fkey`) | — |
| `item_id` | Integer NOT NULL, FK `items.id`, no cascade (`machine_items_item_id_fkey`) | — |
| `qty` | Integer NOT NULL, no check constraint | `0` (Python default only; no database default) |
| `req_qty` | Integer nullable | `NULL` |
| `defective_qty` | Integer nullable | `NULL` |

- No soft-delete column, no `is_active`, no timestamps, no audit columns. Deleting a stock row is a hard delete.
- Indexes: primary key, plain `ix_machine_items_id`, `ix_machine_items_workspace_id`, `ix_machine_items_machine_id`, `ix_machine_items_item_id`. **No unique constraint or index on the pair today** (BUG-983: unique index on `(workspace_id, machine_id, item_id)`, suggested name `uq_machine_items_workspace_machine_item`, tests assert the pgcode, not the name), no check constraint, no trigger. No table references `machine_items`.
- Relationships: `machine` (lazy) and `item` (`lazy="joined"`: every query here also reads the item through a `LEFT OUTER JOIN`). Properties `item_name` and `item_unit` read the loaded item.
- Parents, as used by the bug rules: `Machine` (`app.models.machine`): soft delete = `is_deleted = True` with `is_active = False`. `Factory` (`app.models.factory`): soft delete = `is_deleted = True`, `is_active` unchanged. `Item` (`app.models.item`): no `is_deleted`; removed = `is_active = False`.
- Schemas (`app/schemas/machine_item.py`): `MachineItemCreate` = `machine_id: int`, `item_id: int`, `qty: int = 0`, `req_qty: int | None = None`, `defective_qty: int | None = None` (no `workspace_id`). `MachineItemUpdate` = `qty`, `req_qty`, `defective_qty`, all `int | None = None`. No validators, no minimums. `MachineItemResponse` adds `id`, `workspace_id`, `item_name`, `item_unit`.
- Database collation of the test database: `English_United States.1252` (libc).

**Notes for the test designer:**
- Use the module singleton `machine_item_dao` (`from app.dao.machine_item import machine_item_dao`). Every parameter after `db` is keyword-only in the five methods of this file (a positional call raises `TypeError`).
- Workspaces from `tests/unit/factories.py` (`make_workspace`). Build the other rows directly (add + flush): `Factory(workspace_id, name, abbreviation)`, `Machine(workspace_id, factory_id, name)`, `Item(workspace_id, name, name_normalized, unit)`, `MachineItem(workspace_id, machine_id, item_id, qty)`. The session runs with `autoflush=False`: flush before calling the DAO.
- **Soft-deleted parents (BUG-979, BUG-980, BUG-981):** soft-deleted machine = `is_deleted=True, is_active=False`; soft-deleted factory = `is_active=True, is_deleted=True`, with a live machine in it; removed item = `is_active=False`; inactive-but-live machine or factory = `is_active=False, is_deleted=False`. Keep a row under live parents in the same case, so the intended result is "only that row". Today's result is deterministic (the row is included) → **strict** xfail, compared as **sets** of ids so the order bugs do not interfere. For "back once the parent is live", set the parent's flags directly on its row, flush, call the method; that holds today, so it is a plain pass case. Snapshot the stock row's columns before and compare after.
- **Row order is unspecified today** (BUG-100 here, BUG-976, BUG-977), and the physical order of the test database is **not** deterministic: today's result may even equal the intended one. Write order cases to the intended order and mark them **non-strict** xfail (`strict=False`); never weaken the assertion. Use plain ASCII letter names for BUG-976 (`"Zulu"`, `"apple"`, `"Banana"`, inserted in that order; today they came back in insertion order). Every other case compares **sets** of ids.
- **Two rows for one key (BUG-983, inherited R4, R4a):** the first row is built directly; the second goes through `create` (R4) or `update` (R4a) inside `with db.begin_nested():` inside `pytest.raises(IntegrityError)`; assert `.orig.pgcode == "23505"`, not the index name. Today nothing is raised, deterministically → **strict** xfail. R4b holds today and after the fix → plain pass cases. Build no other case with two rows for one key: it would fail once the index exists.
- **The cap (BUG-982):** 501 machines, one row each for one item; build with `add_all`. Today 500 → **strict** xfail.
- **Database errors:** wrap calls expected to raise `DataError` / `IntegrityError` in `with db.begin_nested():` inside `pytest.raises(...)` so the session stays usable.
- **Not committed:** `sp = db.begin_nested()`, call, `sp.rollback()`, then re-read.

## Not specified
- `machine_item_dao` — module-level singleton `DAOMachineItem(MachineItem)`, no logic
- (`get_by_item`'s `skip` and `limit` parameters — dead parameters, to be removed with BUG-982 (decided by Claude under the reviewer's delegation (2026-10-30); P7). The cap they cause is `get_by_item` R5.)
- Inherited `BaseDAO` methods `get`, `get_multi`, `create`, `update`, `remove` — not overridden; specified in `tests/unit/dao/base.spec.md`. Only what is specific to this model is stated below ("Inherited `BaseDAO` methods on `MachineItem`").

The checklist (`docs/testing/unit-test-checklist-by-layer.md`) marks none of the five methods as possibly unused, and each has a caller reachable from the API. `app/managers/po_machine_inventory.py` also calls `get_by_machine_and_item` and `create`, but that whole file is already on the dead-code list. Unit tests of other modules build `MachineItem` rows directly; `tests/test_item_summary_empty.py` patches `get_by_item`, which is the only existing test touching this DAO.

---

## `DAOMachineItem.get_by_workspace(db, *, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (override identical to `BaseDAO.get_by_workspace`. Used by: `MachineItemManager.list_machine_items` ← `GET /machine-items/` without `machine_id`, with the caller's `skip` / `limit`)

**Purpose:** All stock rows of a workspace, one page at a time.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `workspace_id` | int | equality on the row's `workspace_id` |
| `skip` | int, default `0` | rows to skip; not validated |
| `limit` | int, default `100` | max rows; not validated |

**Returns:** a `list` of `MachineItem` instances (possibly empty), each with its item loaded.

**Rules:**
- **R1.** Returns the rows with that `workspace_id`. Rows of another workspace never appear, even when they would fit on the page.
- **R2.** ✅ (P6) Every row of the workspace is returned whatever its quantities (`qty` of `0`, negative `qty`, `req_qty` / `defective_qty` empty) and whatever the state of its parents: rows of a soft-deleted machine, of a machine in a soft-deleted factory, and of a removed item are returned and take a place in the page.
- **R3.** [BUG-100] (HR-6) Rows are ordered by `id` ascending before `skip` / `limit`, so consecutive windows partition the workspace's rows with no repeats or gaps. *(Today: no ordering is requested; the order is whatever the database produces.)*
- **R4.** At most `limit` rows are returned after skipping `skip`; with the defaults at most 100: given 101 rows, exactly 100.
- **R5.** An unknown workspace, a workspace with no rows, `skip` at or past the number of rows, or `limit=0` returns `[]`.
- **R6.** A negative `limit` or `skip` makes Postgres reject the query (see Errors).
- **R7.** Each returned row carries its item's data: `item_name` and `item_unit` give the item's `name` and `unit`, also for a removed item, with no further query.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInLimitClause`, `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInResultOffsetClause`, `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |

**Side effects:** none

---

## `DAOMachineItem.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (override identical to `BaseDAO.get_by_id_and_workspace`. Used by: `MachineItemManager.get_machine_item`, `update_machine_item`, `delete_machine_item`, each answering 404 `Machine item not found` on `None`)

**Purpose:** One stock row by id, inside a workspace.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `id` | int | equality on the primary key |
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** the `MachineItem` instance (the one the session holds), or `None`.

**Rules:**
- **R1.** Given a row with that id in that workspace, it is returned.
- **R2.** Given a row with that id in another workspace, `None` is returned (indistinguishable from not found).
- **R3.** Given an unknown id or `id=0`, `None` is returned, with no error.
- **R4.** ✅ (P5) The state of the row's parents is not looked at: a row of a soft-deleted machine, of a machine in a soft-deleted factory, or of a removed item is returned like any other.

**Errors:** none.

**Side effects:** none

---

## `DAOMachineItem.get_by_machine(db, *, machine_id, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `MachineItemManager.list_machine_items` ← `GET /machine-items/?machine_id=…`, with the caller's `skip` / `limit`)

**Purpose:** The stock on one machine, one page at a time.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `machine_id` | int | equality on the row's `machine_id`; not validated |
| `workspace_id` | int | equality on the row's `workspace_id` |
| `skip` | int, default `0` | rows to skip; not validated |
| `limit` | int, default `100` | max rows; not validated |

**Returns:** a `list` of `MachineItem` instances (possibly empty), each with its item loaded.

**Rules:**
- **R1.** Returns the rows with that `machine_id` and that `workspace_id`. Rows of another machine are never returned.
- **R2.** Workspace isolation follows the row: a call with the right machine id and another workspace returns `[]`. Only the row's own `workspace_id` is compared, not the machine's or the item's: a row with `workspace_id` = B that points at a machine of workspace A is returned for B and not for A.
- **R3.** Rows are returned whatever their quantities (`qty` of `0`, negative, `req_qty` / `defective_qty` empty).
- **R4.** An unknown machine id, `machine_id=0`, or a machine with no rows returns `[]`.
- **R4a.** [BUG-979] (P1) When the machine is soft-deleted (`machines.is_deleted = True`), `[]` is returned. *(Today: its rows are returned.)*
- **R4b.** [BUG-979] (P1) When the machine is live but its factory is soft-deleted (`factories.is_deleted = True`), `[]` is returned. *(Today: its rows are returned.)*
- **R4c.** What surrounds R4a and R4b, holding today and after the fix: (1) the call changes nothing: the stock rows stay exactly as they were; (2) a machine with `is_active = False`, `is_deleted = False`, and a machine in a factory with `is_active = False`, `is_deleted = False`, hide nothing: the rows are returned; (3) once the machine and its factory are no longer deleted, the rows are returned again, unchanged, with nothing done to them.
- **R5.** [BUG-980] (P2) A row whose item is removed (`items.is_active = False`) is not returned and takes no place in the page; the machine's other rows are returned. Given Anvil (removed) and Bolt (active) on one machine, `limit=1` returns the Bolt row. *(Today: the row is returned and counts in the page.)*
- **R5a.** What surrounds R5, holding today and after the fix: the call changes nothing (the row of the removed item and the item stay as they were), and once the item's `is_active` is `True` again the row is returned, unchanged.
- **R6.** [BUG-976] (HR-6) Rows are ordered by item name case-insensitive ascending, then row `id` ascending, before `skip` / `limit`: items "Zulu", "apple", "Banana" come back "apple", "Banana", "Zulu", and items named "Bolt" and "bolt" come back lower row `id` first. *(Today: no ordering is requested; the order is whatever the database produces.)*
- **R7.** At most `limit` rows are returned after skipping `skip`; with the defaults at most 100: given 101 rows on the machine, exactly 100. Consecutive windows partition the machine's rows with no repeats or gaps (relies on R6).
- **R8.** `limit=0` returns `[]`; `skip` at or past the number of matching rows returns `[]`.
- **R9.** A negative `limit` or `skip` makes Postgres reject the query, as in `get_by_workspace`.
- **R10.** With BUG-983 a machine has at most one row per item of a workspace, so each item appears once. No case of its own: inherited R4 tests the index. *(Today: two rows are possible, and both are returned.)*
- **R11.** Each returned row carries its item's data, as `get_by_workspace` R7.

**Errors:** as `get_by_workspace`.

**Side effects:** none

---

## `DAOMachineItem.get_by_machine_and_item(db, *, machine_id, item_id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `ensure_machine_item` ← `_machine_out`, `_machine_in`, i.e. every machine stock movement; `MachineItemManager.create_machine_item`, as the duplicate check: anything found → 409; `WorkOrderManager` on a `REPLACE` line, as the on-hand figure: `None` counts as 0; `LedgerManager.reconcile_machine_item`, as the snapshot)

**Purpose:** The stock row of one item on one machine, if any.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `machine_id` | int | equality on the row's `machine_id`; not validated |
| `item_id` | int | equality on the row's `item_id`; not validated |
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** the `MachineItem` instance (the one the session holds), or `None`.

**Rules:**
- **R1.** Given a row with exactly that machine, item and workspace, it is returned.
- **R2.** All three must match: the same machine with another item, the same item on another machine, or the same pair in another workspace is not matched. Only the row's own `workspace_id` is compared (as `get_by_machine` R2): rows of workspaces A and B on one pair are each found only under their own workspace.
- **R3.** No match, including `machine_id=0` or `item_id=0`, returns `None`, with no error. No row is created.
- **R4.** ✅ (P5) The state of the row's parents is not looked at: a row of a soft-deleted machine, of a machine in a soft-deleted factory, or of a removed item is returned like any other.
- **R5.** With BUG-983 a key has at most one row, so there is nothing to choose between and no order is needed. No case of its own: inherited R4 tests the index. *(Today: two rows are possible, no ordering is requested, and the row returned is whatever the database produces. Verified: the first row was returned, and after it was updated the second one was. BUG-978, superseded by BUG-983.)*

**Errors:** none.

**Side effects:** none

---

## `DAOMachineItem.get_by_item(db, *, item_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ItemSummaryService._machine_placements` ← the item summary page, with no paging arguments)

**Purpose:** Every machine placement of one catalog item.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `item_id` | int | equality on the row's `item_id`; not validated |
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** a `list` of `MachineItem` instances (possibly empty), each with its item loaded.

**Rules:**
- **R1.** Returns the rows with that `item_id` and that `workspace_id`, whatever their quantities. Rows of another item are never returned.
- **R2.** Workspace isolation follows the row, as `get_by_machine` R2: a call with the right item id and another workspace returns `[]`.
- **R3.** An unknown item id, `item_id=0`, or an item with no rows returns `[]`.
- **R3a.** [BUG-981] (P3) A row whose machine is soft-deleted (`machines.is_deleted = True`) is not returned. Given the item on live Press 1 and on deleted Press 4, only the Press 1 row comes back; given it only on Press 4, `[]`. *(Today: both are returned; the summary shows the second as `Machine #<id>`, factory `—`, and counts it.)*
- **R3b.** [BUG-981] (P3) A row whose machine is live but whose factory is soft-deleted (`factories.is_deleted = True`) is not returned. *(Today: it is returned; the summary shows it with its name and factory.)*
- **R3c.** What surrounds R3a and R3b, holding today and after the fix: (1) the call changes nothing: the stock rows stay exactly as they were; (2) a machine with `is_active = False`, `is_deleted = False`, and a machine in a factory with `is_active = False`, `is_deleted = False`, hide nothing; (3) once the machine and its factory are no longer deleted, the row is returned again, unchanged, with nothing done to it.
- **R4.** ✅ (P5) The item's own state is not looked at: for a removed item (`items.is_active = False`) the rows are returned like any other (inventory DAO Q6 scope decision: the caller named this item; FU-2 (c)).
- **R5.** [BUG-982] (P4) All matching rows are returned: given 501 machines holding the item, 501 rows. *(Today: at most 500 rows. The caller passes no `limit`, so the default of 500 applies; with no order, which rows are left out is arbitrary.)*
- **R6.** [BUG-977] (HR-6) Rows are ordered by row `id` ascending. *(Today: no ordering is requested; the order is whatever the database produces.)*
- **R7.** Each returned row carries its item's data, as `get_by_workspace` R7.
- **R8.** With BUG-983 a machine has at most one row per item of a workspace, so each machine appears once. No case of its own: inherited R4 tests the index. *(Today: two rows are possible, both are returned, and the caller shows and counts the machine twice.)*

**Errors:** none. (Negative `skip` / `limit` belong to the parameters of P7, Not specified.)

**Side effects:** none

---

## Inherited `BaseDAO` methods on `MachineItem`
**Shape:** create / update / delete / get / list
**Persistence:** writes / reads
**Visibility:** public (used by: `create` with a dict ← `MachineItemManager.create_machine_item`, `ensure_machine_item`; `update` with a dict ← `MachineItemManager.update_machine_item`; `remove` ← `MachineItemManager.delete_machine_item`. `get` and `get_multi`: no caller on this DAO)

**Purpose:** `DAOMachineItem` does not override these; the base spec (`tests/unit/dao/base.spec.md`) applies. Only what this model and its schemas change is stated.

**Rules:**
- **R1.** `create` with a dict holding `workspace_id`, `machine_id`, `item_id` creates a row with `qty = 0`, `req_qty = None`, `defective_qty = None`. `qty=None` in the dict also gives `0` (the Python default). The row is flushed, not committed: rolling back a savepoint around the call removes it.
- **R2.** `create` with a `MachineItemCreate` always fails: the schema has no `workspace_id`, so the flush raises `IntegrityError` (`NotNullViolation` on `workspace_id`) and nothing is saved. A dict without `workspace_id` fails the same way.
- **R3.** `create` with an unknown `machine_id`, `item_id` or `workspace_id` raises `IntegrityError` (`ForeignKeyViolation`, constraints `machine_items_machine_id_fkey`, `machine_items_item_id_fkey`, `machine_items_workspace_id_fkey`). A key that is not an attribute of the model (e.g. `avg_price`) raises `TypeError` and nothing is added.
- **R4.** [BUG-983] (Q1) A second row for the same `workspace_id`, `machine_id` and `item_id` is refused by the database: `create` raises `sqlalchemy.exc.IntegrityError` at the flush (`.orig` is `psycopg2.errors.UniqueViolation`, pgcode `23505`), the DAO does not catch or translate it, nothing is saved and the first row is unchanged. *(Today: the second row is saved and no error is raised.)*
- **R4a.** [BUG-983] (Q1) The same applies to `update`: a dict moving a row onto a key another row holds (e.g. `{"machine_id": <other>}`) raises the same error at the flush; after `db.refresh(row)` it has its old values. *(Today: the move is saved and the key then has two rows.)*
- **R4b.** What stays allowed, today and after the fix: the same item on another machine, another item on the same machine, and the same machine + item under another `workspace_id` (the key includes the workspace; R6).
- **R5.** No range check: `qty`, `req_qty` and `defective_qty` store negative values (`-4` stays `-4`). A value beyond the 32-bit integer range raises `sqlalchemy.exc.DataError` (`.orig` is `psycopg2.errors.NumericValueOutOfRange`, pgcode `22003`).
- **R6.** `create` does not look at the parents' state or workspaces: a row is saved for a soft-deleted machine, for a removed item, and for an item of another workspace (then `item_name` gives that item's name).
- **R7.** `update` with a `MachineItemUpdate` applies only fields set to a value: `MachineItemUpdate(qty=6, req_qty=None)` changes `qty` and keeps `req_qty`; `qty=0` is applied. `req_qty` and `defective_qty` cannot be cleared through the schema (base spec `update` R2, R3).
- **R8.** `update` with a dict sets any attribute given: `{"req_qty": None}` clears it, `{"machine_id": <other>}` moves the row to another machine. `{"qty": None}` raises `IntegrityError` (`NotNullViolation` on `qty`) at the flush.
- **R9.** `remove` hard-deletes the row: a query in the same session no longer finds it and the deleted instance is returned. No table references it, so nothing else is deleted. [BUG-101] Given an id with no row, `None` is returned and nothing is deleted (base spec `remove` R3). *(Today: `sqlalchemy.orm.exc.UnmappedInstanceError`; the manager finds the row first, so the API does not reach this.)*
- **R10.** `get` returns a row of any workspace and `None` for an unknown id. `get_multi` is not scoped to a workspace. [BUG-100] It is ordered by `id` ascending (base spec `get_multi` R2). *(Today: no ordering is requested; the fix in `app/dao/base.py` reaches this method.)*
- **R11.** A hard delete of a machine or item that still has a stock row is refused by the database (`IntegrityError`, `ForeignKeyViolation`), so a row's machine and item always exist. A hard delete of the workspace removes its rows (`ON DELETE CASCADE`).
- **R12.** On an object not attached to any session and with no item loaded, `item_name` and `item_unit` are `None` (`MachineItem(item_id=1).item_name is None`). A saved row always has an item (R11), so this is reached only before saving.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `create` without `workspace_id` (any `MachineItemCreate`); `update` with `{"qty": None}` | `sqlalchemy.exc.IntegrityError`; `.orig` is `psycopg2.errors.NotNullViolation` (pgcode `23502`) | — (not asserted) |
| `create` with an unknown `machine_id`, `item_id`, `workspace_id` | `IntegrityError`; `.orig` is `psycopg2.errors.ForeignKeyViolation` (pgcode `23503`) | — |
| a quantity outside the 32-bit range | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.NumericValueOutOfRange` (pgcode `22003`) | — |
| `create` with an unknown key | `TypeError` | — |
| [BUG-983] `create` or `update` onto a taken `workspace_id` + `machine_id` + `item_id` (R4, R4a) | `IntegrityError`; `.orig` is `psycopg2.errors.UniqueViolation` (pgcode `23505`) | — (not asserted) |

**Side effects:** as in the base spec. No ledger row and no activity event: the callers write those.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 14, 24, 37, 50, 64 | keyword-only parameters; defaults `skip=0`, `limit=100` | Notes for the test designer; `get_by_workspace` R4; `get_by_machine` R7 |
| 17–19 | `workspace_id` filter only; no parent checked | `get_by_workspace` R1, R2, R5, R7 |
| 20 | offset / limit, no `ORDER BY` (BUG-100); `limit=0`; negative values; empty / many | `get_by_workspace` R3, R4, R5, R6, Errors |
| 27–32 | id AND `workspace_id`; no parent checked | `get_by_id_and_workspace` R1, R2, R3, R4 |
| 33 | `.first()` on the primary key: row / `None` | `get_by_id_and_workspace` R1, R2, R3 |
| 40–45 | `workspace_id` AND `machine_id`; no join to machines or factories (BUG-979), no item state (BUG-980) | `get_by_machine` R1, R2, R3, R4, R4a, R4b, R4c, R5, R5a, R10, R11 |
| 46 | offset / limit, no `ORDER BY` (BUG-976); `limit=0`; negative values; empty / many | `get_by_machine` R6, R7, R8, R9 |
| 53–59 | `workspace_id` AND `machine_id` AND `item_id`; no parent checked | `get_by_machine_and_item` R1, R2, R3, R4 |
| 60 | `.first()`: row / `None`; at most one row with BUG-983 (BUG-978 superseded) | `get_by_machine_and_item` R1, R3, R5 |
| 64 | defaults `skip=0`, `limit=500`; no caller passes them | `get_by_item` R5; parameters: Not specified (P7) |
| 67–72 | `workspace_id` AND `item_id`; no join to machines or factories (BUG-981); item state not read | `get_by_item` R1, R2, R3, R3a, R3b, R3c, R4, R7, R8 |
| 73–75 | offset, limit, no `ORDER BY` (BUG-977, BUG-982); empty / many | `get_by_item` R3, R5, R6 |
| 79 | module singleton | Not specified |
| `models/machine_item.py` 23 | `item` loaded with `lazy="joined"` | `get_by_workspace` R7 |
| `models/machine_item.py` 26–31 | `if self.item`: item loaded / none | `get_by_workspace` R7; inherited R12 |
| `base.py` 76–84 | `create`: dict / schema (no `workspace_id`); Python default for `qty`; FK, NOT NULL, range errors; no uniqueness check in Python, unique index (BUG-983) | inherited R1, R2, R3, R4, R4b, R5, R6 |
| `base.py` 108–119 | `update`: dict / schema (`exclude_unset`, `exclude_none`); `hasattr` true for every column; unique index (BUG-983) | inherited R4a, R7, R8 |
| `base.py` 136–139 | `remove`: found / not found (BUG-101) | inherited R9 |
| `base.py` 43, 59 | `get`, `get_multi`: no workspace filter, no order (BUG-100) | inherited R10 |
