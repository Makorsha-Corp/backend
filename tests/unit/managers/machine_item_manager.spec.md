# Spec — `app/managers/machine_item_manager.py`

> **Status:** APPROVED (2026-10-31). Nothing is open: the owner answered Q2a. Stays APPROVED after fill-gaps (Gap log at the end).
> **Source commit:** e48a092

> **Review round 2026-10-31.** **The owner's own answers (2026-10-30/31, relayed by the main session):** Q1, the one-off script as suggested, named `scripts/repair_machine_zero_average.py`; Q2, "Restate them", over leaving them, accepting it may not find every row (what that can mean is in Q2, and Q2a is open); Q3, `ge=0` on the input schemas, not on `MachineItemBase`; Q4, a final adjustment on any `qty ≠ 0`; Q5, stock on a deleted machine does not block `delete_item`; Q6, refuse the four cases and list the blockers, with the generic `other_workspace` entry, the row's own `qty` not blocking; Q7, Q8, bug, 400 with the suggested messages; Q9, bug, 400; Q10, intended; Q12, intended. **Claude's reading, not the owner's words:** in Q5, a machine of a deleted factory counts too, because both are hidden the same way (BUG-979). **Delegated:** P1–P5 and Q13 accepted as suggested, and Q11, settled by HR-16: not found everywhere; all decided by Claude under the reviewer's delegation (2026-10-31). New bugs: BUG-1074 … BUG-1086.
>
> **Owner's answer on Q2a, 2026-10-31, relayed by the main session:** "Found rows only": correct only the found rows' own columns; later rows and current averages stay. **This is the one approved in-place ledger edit.** The two one-off scripts are written: `scripts/repair_machine_zero_average.py` (Q1), `scripts/restate_half_even_averages.py` (Q2a). Tested on `marker_test` only, in one rolled-back transaction, dry run and `--apply`, through `main()`; never run on another database.

> **Routed here and written as rules:** machine item DAO FU-1 (a), (b), (c), (e), (f), (g), (h), BUG-983; machine item ledger DAO FU-1 and FU-6, BUG-993, BUG-1040; BUG-1010; machine manager FU-7 (the `machine_items` part). Machine item DAO FU-1 (d) and FU-4 are owner questions below (Q3, Q5).
>
> **Fill-gaps round 2026-10-31 (`machine_item_manager.cases.md` gaps 1–9).** **The owner's own answers (2026-10-31, relayed by the main session):** first, a consumed `REPLACE` line does not block (gap 4) and a pending return on a voided purchase order does not block (gap 5); **both are superseded, see the correction below.** **Owner's answer applied by Claude:** gap 3, the `delete_machine` G12 answer. **Relayed from the main session:** gap 5, other stages; gap 6, HR-15. **Delegated:** gap 1, decided by Claude under the reviewer's delegation (2026-10-31). Gaps 2, 7, 8, 9 are facts, verified by running (`p9.py`, `p10.py`, rolled back). Rules changed: `delete_machine_item` R5 (b), (d), intro, R5a, R5b; `_write_ledger_entry` R4; Notes; FU-10. BUG-1081 updated; no new bug.
>
> **Correction 2026-10-31 (owner's answers, relayed by the main session).** The question on gaps 4 and 5 rested on a wrong premise (that the part may already be off the machine, and that a voided order's return is finished). Given the facts, the owner reversed both and added a third: (1) a `REPLACE` line with `uses_inventory = True` on an open order blocks, consumed or not; (2) a pending return blocks whatever the purchase order's state, voided included, because it can still be completed; (3) a `REPLACE` line with `uses_inventory = False` does not block, since it moves no stock. Rules changed: `delete_machine_item` R5 (b), (d), R5b; Notes; FU-10; Gap log G4, G5. BUG-1081 updated; no new bug.
>
> **Standing decisions applied here (not asked again):**
> 1. Refuse while in use, and a refusal lists every blocker (`item_manager.spec.md` `delete_item` R9, R9b, with the generic `{"type": "other_workspace"}` entry; HR-16). What counts as "in use" for a stock row is new: Q6.
> 2. Things of a soft-deleted parent are hidden by the parent's state, their own rows untouched. A stock row's parents are its machine, the machine's factory and its catalog item. "Removed" for an item means `items.is_active = False`.
> 3. A ledger is history: entries of hidden parents stay, and a hard delete of a stock row leaves its ledger rows.
> 4. A missing `ORDER BY` is a bug; physical row order and collation order are not an order.
> 5. One stock row per workspace + machine + item (BUG-983). `scripts/merge_duplicate_machine_items.py` runs before the index.
> 6. Money rounds half up (HR-15). Nothing links across workspaces (HR-16).
>
> **Verified by running** (throwaway scripts `h.py`, `p1.py` … `p7.py`, `p5b.py` in the scratchpad folder `mim`, each in one transaction rolled back against `marker_test`; nothing committed; `p8.py` for the search in Q2): every "Today:" note below; `get_machine_item` own / other workspace / unknown / `0` and every hidden-parent state; `list_machine_items` with `machine_id` `None`, `0`, `-1`, unknown, another workspace's, a deleted machine's; paging, `limit=0`, negative values (error class and pgcode), 101 rows on both paths, the emitted SQL of both paths (no `ORDER BY`); create with unknown / `0` / other-workspace / deleted / inactive machine, machine in a deleted and an inactive factory, unknown / `0` / other-workspace / removed item, `qty` `0`, `5`, `-3`, `2**31 - 1`, `2**31`, negative `req_qty` / `defective_qty`, a duplicate, the same pair under another `workspace_id`, a lost race (lookup patched), unknown user with `qty` 0 and 5, savepoint roll-back; update with `{}`, all `null`, same values, each field alone, `qty` up / down / to 0 / negative, all three together, `2**31`, unknown user (three paths), hidden parents, a stored row with another workspace's item; delete with `qty` above, at and below 0, unknown user (two paths), hidden parents, a stored row with another workspace's item, an open work order line, savepoint roll-back; every ledger and event field of those paths; `_item_name` in all states; the BUG-993 chain through `_machine_in`, `update_machine_item`, `_machine_out`, `delete_machine_item`, `create_machine_item`; a re-created row; an empty latest `avg_price_after`; an average of `0.125` before and after expiry; `reconcile_machine_item` and a stock-out after a delete; that `update_machine_item` and `delete_machine_item` emit no `FOR UPDATE`; that a plain `FOR UPDATE` on this model raises `FeatureNotSupported` and `FOR UPDATE OF machine_items` works. **Over HTTP** (`TestClient`, overridden dependencies, rolled back): unknown item (409 generic), another workspace's item (201, name returned), negative quantities (201), a duplicate (409), `null` `req_qty` (200, unchanged), `qty: 2.5` (400, BUG-461), `machine_id=0` (200, whole workspace), `qty` `2**31` on `POST` and `PUT` (500), delete (204), get after delete (404). **Not run:** two concurrent transactions (commits are not allowed); the intended behavior of any bug rule; production data, so how many machines are affected by Q1 and Q2 is unknown.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list — nothing open
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | Machines already at 0.00 stay at 0.00 after BUG-993 | one-off script, appended entries only | **owner** |
| Q2 | Stored rows off by 0.01 from half-even rounding | "Restate them", as Q2a limits it | **owner** |
| Q2a | What a restate may write, given that | found rows only; later rows and current averages stay | **owner** |
| Q3 | Negative quantities are stored | bug — refused on the input schemas (BUG-1079) | **owner** |
| Q4 | Removing a negative stock row leaves the ledger negative | bug — final adjustment on any `qty ≠ 0` (BUG-1080) | **owner** |
| Q5 | A row on a deleted machine blocks an item delete, and no list shows it | it does not block (BUG-948; `delete_item` R9 (b)) | **owner**; deleted factory: Claude's reading |
| Q6 | A stock row is removed while open orders still need it | bug — refused in four cases, blockers listed (BUG-1081, frontend BUG-1082) | **owner** |
| Q7 | Stock on a deleted machine can still be edited | bug — 400 (BUG-1083) | **owner** |
| Q8 | Stock on a deleted machine can still be removed | bug — 400 (BUG-1084) | **owner** |
| Q9 | A removed catalog item can be added to a machine, and the row is then invisible | bug — 400 (BUG-1085) | **owner** |
| Q10 | Stock of a removed item can still be edited or removed by id | intended | **owner** |
| Q12 | Stock added by hand after the machine held none is valued at the old average | intended | **owner** |
| P1 | `machine_id=0` lists the whole workspace's stock | bug (BUG-1074) | Claude, delegated |
| P2 | A machine's target and defect count cannot be cleared | bug (BUG-1075) | Claude, delegated |
| P3 | Stock can be added to a machine of a deleted factory | bug (BUG-1076) | Claude, delegated |
| P4 | A hidden stock row still opens by id | bug (BUG-1077) | Claude, delegated |
| P5 | A quantity beyond 32 bits crashes (500) | bug (BUG-1078) | Claude, delegated |
| Q11 | A stored row with another workspace's item shows that item's name and id | bug — not found everywhere, per HR-16 (BUG-1086) | Claude, delegated |
| Q13 | A quantity edit writes two activity entries | intended | Claude, delegated |

### House-rule violations — applied automatically

- **HR-4 / HR-5** `list_machine_items` R7 — without `machine_id` the list shows rows of soft-deleted machines, of machines in soft-deleted factories and of removed items. Intended: those rows are left out in the query, before `skip` / `limit` (machine item DAO P6, FU-1 (a)).
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-1070 (pattern `join-ignores-soft-deleted`; per BUG-924, BUG-979, BUG-980). Rules: `list_machine_items` R7, R7a.
- **HR-6** `list_machine_items` R8 — without `machine_id` the display order is whatever the database produces. BUG-100 gives `id` only, at the DAO. Intended: item name case-insensitive ascending, then row `id` ascending, before `skip` / `limit` (BUG-701, the same order as BUG-976).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-1071 (pattern `unordered-pagination`). Rules: `list_machine_items` R8.
- **HR-10** `update_machine_item` R4 — a stock quantity is read and then an absolute value written without a row lock. Two edits at once, or an edit during a stock movement, lose a change and record a stale `qty_before`. Intended: the row is read `FOR UPDATE`.
**Answer:** bug — per HR-10 (house rule)
**Resolution:** 🐞 BUG-1072 (pattern `hr-10-unlocked-state-transition`; per BUG-643, BUG-661). Rules: `update_machine_item` R4.
- **HR-10** `delete_machine_item` R4 — the quantity booked in the final adjustment is read without a row lock, so a stock movement at the same moment is lost from the ledger's last entry. Intended: the row is read `FOR UPDATE`.
**Answer:** bug — per HR-10 (house rule)
**Resolution:** 🐞 BUG-1073 (pattern `hr-10-unlocked-state-transition`; per BUG-643, BUG-661). Rules: `delete_machine_item` R4.

Existing bugs written as rules here, no new ID: **BUG-983** `create_machine_item` R8; **BUG-993** `_write_ledger_entry` R2–R5, R9; **BUG-1010** `create_machine_item` R5; **BUG-1040 / HR-15** `_write_ledger_entry` R3. Reached through this manager and cited: BUG-100, BUG-976, BUG-979, BUG-980 (machine item DAO), BUG-664 (ledger DAO).

Checked and **not** violated: **HR-1, HR-2, HR-3, HR-8** — no names or free text. **HR-5, HR-6** on the `machine_id` path — the DAO's rules (BUG-976, BUG-979, BUG-980). **HR-7** — `GET /machine-items/` enforces `1 <= limit <= 1000`, `skip >= 0`. **HR-9** — `machine_items` has no audit columns; events and ledger rows are written only on a real change. **HR-11 … HR-14** — no external system, no batch. **HR-16** on the machine link — `create_machine_item` refuses another workspace's machine exactly as a missing one.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation (2026-10-31))

### P1. `machine_id=0` lists the whole workspace — 🐞 BUG-1074
**Background:** `GET /machine-items/` takes an optional `machine_id`. The code tests it for truthiness, so `0` means "no filter". Same root cause as BUG-885 and BUG-923.
**What happens today:** `GET /machine-items/?machine_id=0` answers 200 with every row of the workspace (verified). The DAO itself returns `[]` for `0`.
**Example:** A client with an unset machine id sends `0` and believes it sees one machine's stock; it sees all of it.
**Rules affected:** `list_machine_items` R3
**Answer:** bug — per BUG-885 precedent: only `None` means "no filter"; `machine_id=0` returns `[]`
**Resolution:** 🐞 BUG-1074 (pattern `falsy-zero-treated-as-missing`) — decided by Claude under the reviewer's delegation (2026-10-31): the suggested precedent answer is accepted. Rules: `list_machine_items` R3.

### P2. A machine's target and defect count cannot be cleared — 🐞 BUG-1075
**Background:** `req_qty` is the wanted quantity on the machine and `defective_qty` a defect count; both are optional. The edit drops every field sent as `null`. Same root cause as BUG-942 and BUG-962. The web forms also send `reqQty ?? undefined`, which omits the field (FU-4).
**What happens today:** `PUT` with `req_qty: null` answers 200 and the old value stays (verified over HTTP).
**Example:** A target of 7 is no longer wanted. A client sends `req_qty: null`: 200, and the target is still 7.
**Rules affected:** `update_machine_item` R6
**Answer:** bug — per BUG-962 precedent: explicit `null` clears `req_qty` and `defective_qty`, and the `item_updated` entry records `to_value: null`; `qty: null` is rejected by `MachineItemUpdate`; omitted fields stay unchanged
**Resolution:** 🐞 BUG-1075 (pattern `exclude-none-blocks-clear`) — decided by Claude under the reviewer's delegation (2026-10-31): the suggested precedent answer is accepted. Rules: `update_machine_item` R6, R7. Frontend: FU-4 (a).

### P3. Stock can be added to a machine of a deleted factory — 🐞 BUG-1076
**Background:** A machine of a soft-deleted factory is hidden everywhere (BUG-890, BUG-979). `create_machine_item` looks only at the machine's own flag. For machines the same gap was ruled a bug (BUG-963, BUG-964).
**What happens today:** 201, the row is written and the machine's activity log gets an entry (verified), for a machine nobody can see.
**Example:** "Old Plant" was deleted. A stale form adds 3 bearings to "Press 4" of that plant: 201, and they appear nowhere.
**Rules affected:** `create_machine_item` R3
**Answer:** bug — per BUG-964 precedent: refused like a deleted machine, 400 `Cannot add items to a deleted machine`, checked right after the machine's own flag, nothing written; an inactive-but-live machine or factory is not refused
**Resolution:** 🐞 BUG-1076 (pattern `write-to-soft-deleted-related-row`) — decided by Claude under the reviewer's delegation (2026-10-31): the suggested precedent answer is accepted. Rules: `create_machine_item` R3.

### P4. A hidden stock row still opens by id — 🐞 BUG-1077
**Background:** After BUG-979, BUG-980 and BUG-1070 no list shows a row of a deleted machine, a machine of a deleted factory or a removed item. `GET /machine-items/{id}/` uses the raw lookup (machine item DAO P5 kept it raw and left the answer to this manager). The frontend defines this lookup. For machines: BUG-966; `include_deleted` is what would let the refusal of an item delete (Q5) be inspected.
**What happens today:** 200 in all three states (verified).
**Example:** A bookmark to the 7 bearings of deleted "Press 4" still opens them.
**Rules affected:** `get_machine_item` R3
**Answer:** bug — per BUG-966 precedent: 404 `Machine item not found` by default; a new `include_deleted=True` returns the row, reachable from the API (HR-4); an inactive-but-live machine or factory hides nothing
**Resolution:** 🐞 BUG-1077 (pattern `join-ignores-soft-deleted`) — decided by Claude under the reviewer's delegation (2026-10-31): the suggested precedent answer is accepted. Rules: `get_machine_item` R3, R3a.

### P5. A quantity beyond 32 bits crashes — 🐞 BUG-1078
**Background:** The three quantity columns are 32-bit integers; the schemas set no limit. For text columns the same gap was ruled a bug (BUG-972).
**What happens today:** `qty` of `2147483648` raises `DataError` at the flush: a 500 on both `POST` and `PUT` (verified). `2147483647` is stored.
**Example:** A typing slip of eleven digits gives "internal server error" instead of a validation message.
**Rules affected:** `create_machine_item` R14, `update_machine_item` R14
**Answer:** bug — per BUG-972 precedent: `le=2147483647` on the three fields of `MachineItemCreate` / `MachineItemUpdate`, rejected by the schema, nothing written
**Resolution:** 🐞 BUG-1078 (pattern `unvalidated-numeric-range`) — decided by Claude under the reviewer's delegation (2026-10-31): the suggested precedent answer is accepted. Rules: `create_machine_item` R14, `update_machine_item` R14.

### Questions — answered

### Q1. Machines already at 0.00 stay at 0.00 after BUG-993 — ✅ script (owner's answer)
**Background:** You decided a manual change keeps the machine's average (BUG-993). The fix stops new damage only. A machine's average lives in its newest ledger entry, so every machine edited by hand before the fix has 0.00 there, and the fix keeps "the current average", which is that 0.00. The old average is still in older entries. A later receipt may have blended 0.00 into a new non-zero average.
**What happens today:** Verified: 10 @ 5.00, edited to 12: 12 worth 0.00. Consume 2: priced 0.00. Receive 10 @ 3.00: average 1.50, not the 4.00 or so it would have been.
**Example:** Press 4 holds 12 bearings worth 0.00 since last year. After the fix they stay at 0.00, and the next work order's parts cost shows 0.00.
**Rules affected:** `_write_ledger_entry` R7
**Suggested answer:** `bug — a one-off script, dry run by default, --apply to commit (as the duplicate merge): for each machine + item whose latest average is 0.00 and an earlier entry has a non-zero one, append one inventory_adjustment entry with quantity 0, qty unchanged, the last non-zero average, value = qty × average; nothing already written is edited, because a ledger is history.` Work orders already costed at 0.00 stay as they are. A blended average (the 1.50 above) cannot be told from a real one, so it is left. Alternative: `intended` — leave the data, the costs recover as stock is received. This query counts the machines: the latest row per `(workspace_id, machine_id, item_id)` of `machine_item_ledger` with `avg_price_after = 0` and `qty_after <> 0`, where an earlier row has `avg_price_after > 0`.
**Answer:** one-off script as suggested: dry run first, appends a quantity-0 entry at the last non-zero average, edits nothing; blended averages stay. **The owner's own answer (2026-10-31).**
**Resolution:** no rule of this manager changes and no new ID; recorded in BUG-993. **`scripts/repair_machine_zero_average.py`**. Dry run by default, `--apply` to commit. Target: the latest entry of a workspace + machine + item has `avg_price_after = 0` and `qty_after <> 0`, an earlier entry has `avg_price_after > 0`, and the zero came from a manual change: the first entry after the last non-zero average has `source_type` `manual` or `adjustment`. That last condition is added by Claude: a receipt at 0.00 onto an empty machine also leaves a real 0.00 average, which is not BUG-993. Printed and left alone: such a real zero, a pair with no stock row or two of them, an entry that arrived during the run. Each target gets one appended `machine_item_ledger` row: `transaction_type = "inventory_adjustment"`, `quantity = 0`, `qty_before = qty_after` = the latest entry's `qty_after`, `unit_cost` = `avg_price_after` = the latest earlier non-zero average, `avg_price_before = 0.00`, `total_cost = 0.00`, `value_before = 0.00`, `value_after` = `qty_after` × that average. `performed_by` is `NOT NULL`, so the script needs a profile id as an argument; `source_type = "repair"`. No existing row is edited, no `machine_items` row changes. Work orders already costed at 0.00 stay. Once the entry is there, `_write_ledger_entry` R2 reads it like any other. Rules: `_write_ledger_entry` R7.

### Q2. Stored rows off by 0.01 from half-even rounding — ✅ restated, found rows only (owner's answer)
**Background:** You decided money rounds half up (HR-15, BUG-1040). The fix changes new rows. Rows already written were rounded half to even by Python in `total_cost`, and half up by the database in the other columns, so one row can disagree with itself.
**What happens today:** Verified: `unit_cost` 0.125, qty 1 is stored as `unit_cost` 0.13, `total_cost` 0.12, `value_after` 0.13.
**Example:** A receipt line shows 0.12 where the new code would show 0.13.
**Rules affected:** none here. `_write_ledger_entry` writes no such rows today (all 0.00), and with BUG-993 its product is exact (R3).
**Suggested answer:** `intended — leave stored rows.` The difference is at most 0.01 per row, a ledger is history, and the running value does not depend on `total_cost`. The affected rows also cannot be found exactly: `unit_cost` was rounded when stored, so `quantity × unit_cost <> total_cost` also matches correct rows (3 @ 1.335 is stored as 1.34, total 4.00).
**Answer:** "Restate them": the owner chose this over leaving them, accepting it may not find every row. **The owner's own answer (2026-10-31).**
**Resolution:** recorded in BUG-1040; no rule here changes. What can and cannot be done, read from every site BUG-1040 lists:
- **`total_cost` (`_machine_in`, `_machine_out`, `_storage_in`, `_storage_out`, `work_order_manager` :762, :859, :883):** no row to restate is expected. Every `unit_cost` reaching them comes from a two-decimal column (`purchase_order_items.unit_price`, `work_order_items.unit_cost`, a stored average) and `qty` is an integer, so the product is exact and `quantize` changes nothing. The 0.125 example of BUG-1040 needs a direct call (read, not run). A row where `total_cost <> quantity * unit_cost` would show otherwise; `total_cost` in such a row **cannot be restated without guessing**: `unit_cost` was rounded when stored, the source columns are rounded too, and the original price is stored nowhere.
- **Averages (`weighted_avg_price`, `product_manager` :218) and the unit cost of a work order line (`work_order_manager` :860):** these divide, so half-even really differed, and such rows **can be found exactly** from their own columns. With `n = qty_before * avg_price_before + quantity * unit_cost` and `d = qty_before + quantity`, over rows with `qty_before > 0`, `quantity > 0`, `avg_price_before` set: `MOD(n * 200, d) = 0 AND MOD((n * 200) / d, 2) = 1 AND avg_price_after <> ROUND(n / d, 2)`. Verified on `machine_item_ledger` and `inventory_ledger` with rows from real movements: 1 @ 0.01 + 1 @ 0.04 is found (0.02, half up 0.03); a midpoint that already agrees (0.015), a non-midpoint, a first entry and a stock-out are not. `product_ledger`: the same test on `avg_cost_before` / `avg_cost_after`, where `unit_cost` is set (read, not run). `work_order_items`: `total_cost / quantity` an exact midpoint and `unit_cost <> ROUND(total_cost / quantity, 2)` (read, not run). The correction is always +0.01. Stored prices are not negative, so no other direction arises.
- **What a restate writes to the found row is computable:** `avg_price_after` (or `avg_cost_after`, or the line's `unit_cost`) = the half-up value, and on `machine_item_ledger` `value_after` = `qty_after` × that value.
- **What follows it is not computable without guessing.** Every later entry of that location and item read the old average: the next `avg_price_before`, each stock-out's `unit_cost`, `total_cost` and values, later blended averages, `inventory.avg_price`, `products.avg_cost`, the price a transfer carries to another location, and the cost of work order lines. Replaying needs one unbroken chain, and there is none to rely on: a price can change with no ledger entry (BUG-712), manual changes zeroed the average (BUG-993), and ties make the order of entries unknown (BUG-640, BUG-664; verified in `p8.py`: within one transaction the next storage entry read 0.01 after an entry of 0.02). No method for this part is written here: see Q2a.

### Q2a. What a restate may write — ✅ found rows only (owner's answer)
**Background:** Q2 above. A restate can correct the found row's own columns, but not what later rows copied from it. It would also be the first edit of a stored ledger row: a ledger is history, and Q1 was chosen to edit nothing.
**What happens today:** Nothing has been restated. How many rows match is unknown (production data was not read).
**Example:** Entry 40 stored an average of 0.02; half up says 0.03. Entries 41–60 used 0.02. Restated alone, entry 40 says 0.03 and entry 41 still says it started from 0.02.
**Rules affected:** none.
**Suggested answer:** `(a) restate only the found rows' own columns, in a one-off dry-run script, and leave everything after them.` The ledger then disagrees with itself by 0.01 at each such row, in exchange for each row's own arithmetic being right. Alternatives: (b) as (a), and where the found row is still the latest, also append a quantity-0 entry at the corrected average as in Q1, so the next movement uses it; (c) append only, editing nothing, which corrects the current average and leaves the old rows as they are; (d) leave them after all.
**Answer:** "Found rows only": correct only the found rows' own columns; later rows and current averages stay. **The owner's own answer (2026-10-31).**
**Resolution:** no rule changes; recorded in BUG-1040. **This is the one approved in-place ledger edit**; "a ledger is history" otherwise stands. `scripts/restate_half_even_averages.py`, dry run by default, `--apply` to commit:
- **A row is found** by the Q2 test, tightened so that only a row the blend wrote can match: the stored value must equal the half-even value of `n / d` where half up differs, and `n > 0`.
- **Looked at:** every `machine_item_ledger` entry; `inventory_ledger` except `source_type` `manual` / `adjustment`, where a user set the price; `product_ledger` with `transaction_type = 'production'`; consumed `work_order_items`.
- **Written:** `avg_price_after`, and `value_after` on the machine ledger; `avg_cost_after`; a line's `unit_cost`. The line's `updated_at` stamps itself; `total_cost` stays. Nothing else: no later row, no `inventory.avg_price`, no `products.avg_cost`.
- **Left alone and printed:** a found row that is the **latest** entry of its machine + item, or of its factory + item + stock type. The average in use is read from that entry (`get_latest_entry`, `sync_snapshot_from_ledger`), so the owner's two clauses collide there, and "current averages stay" wins. Such a row is corrected by a later run, once a newer entry exists. A found `product_ledger` row is corrected even when latest: `products.avg_cost` is not read from the ledger.
- **Order of the two scripts:** repair first, then restate. Otherwise the repair could carry a corrected average forward and change a current average.

### Q3. Negative quantities are stored — 🐞 BUG-1079 (owner's answer)
**Background:** Nothing in `MachineItemCreate` / `MachineItemUpdate` sets a minimum, and the table has no check. Stock-outs refuse to go below zero ("Insufficient machine stock"), so in normal use only this manager writes a negative. For factory stock the same gap was ruled a bug (BUG-711).
**What happens today:** All verified. `POST` with `qty: -3` answers 201, stores `-3` and writes **no** ledger entry, so the ledger still says 0, and a later reconcile silently resets the row to 0. `PUT` with `qty: -3` from 5 stores it and writes an adjustment of 8 with `qty_after = -3`. `req_qty` and `defective_qty` store negatives on both.
**Example:** A storekeeper enters `-3` to mean "3 fewer". The machine now shows −3 bearings, and the next stock-out is refused with "-3 available".
**Rules affected:** `create_machine_item` R12, R13; `update_machine_item` R13
**Suggested answer:** `bug — per BUG-711: ge=0 on qty, req_qty and defective_qty of MachineItemCreate and MachineItemUpdate, rejected by the schema, nothing written.` Rows already negative stay until edited; such an edit is an ordinary adjustment (`qty_before` negative, with Q4 for removing them). Alternative: `intended` — negative stock means a debt on the machine; then a negative create must write a ledger entry too.
**Answer:** bug — `ge=0` on the input schemas (`MachineItemCreate`, `MachineItemUpdate`), not on `MachineItemBase`. **The owner's own answer (2026-10-31).**
**Resolution:** 🐞 BUG-1079 (pattern `unvalidated-numeric-range`; per BUG-711). `MachineItemResponse` inherits `MachineItemBase`, so the base stays open and a row already negative can still be read (FU-2). Rules: `create_machine_item` R12, R13; `update_machine_item` R13.

### Q4. Removing a negative stock row leaves the ledger negative — 🐞 BUG-1080 (owner's answer)
**Background:** Removing a stock row writes a final adjustment to zero only when `qty > 0`. A negative row can exist (Q3). The item and machine delete rules count any `qty ≠ 0` as stock.
**What happens today:** Verified: a row edited to `-3` is deleted with no ledger entry. The ledger's balance stays `-3`, and `reconcile_machine_item` answers `status: "error"`, `Snapshot missing for item with ledger transactions`, with no way to clear it through this API.
**Example:** A −3 row of Bolt is removed from Press 4. The machine's stock page shows nothing, and its ledger balance says −3 for good.
**Rules affected:** `delete_machine_item` R8
**Suggested answer:** `bug — the final adjustment is written for any qty ≠ 0, so the ledger always ends at 0`. Needed whatever Q3 decides, because rows already negative stay.
**Answer:** bug — a delete writes a final adjustment on any `qty ≠ 0`. **The owner's own answer (2026-10-31).**
**Resolution:** 🐞 BUG-1080 (pattern `unlogged-value-change`). `quantity` is the size of the change, so a negative row gives `quantity` = |`qty`|. Rules: `delete_machine_item` R6, R8.

### Q5. A row on a deleted machine blocks an item delete, and no list shows it — ✅ does not block (owner's answer)
**Background:** You decided an item with stock cannot be deleted, and that this counts `machine_items` rows by item id whatever the machine's state (`delete_item` R9 (b)). You also decided stock of a deleted machine is hidden (BUG-979, BUG-981). `delete_machine` now refuses a machine with stock, but older rows exist, and deleting a factory leaves its machines' stock as it is. "Restore machine" is not built yet (machine manager FU-4), and Q7, Q8 would refuse fixing such a row.
**What happens today:** No refusal exists yet (BUG-948 is open). Once it does, the refusal names a row that no page shows and that cannot be cleared.
**Example:** "Bearing" sits 3 times on deleted "Press 4". Deleting "Bearing" gets "Item has stock or open orders", machine stock row 812. The user cannot find row 812, and cannot zero it. The item can never be deleted.
**Rules affected:** none here; `item_manager.spec.md` `delete_item` R9 (b), R9b
**Suggested answer:** `bug — in delete_item, a row of a soft-deleted machine, or of a machine in a soft-deleted factory, does not block.` Nothing is lost: an item delete only hides the item, the row stays, and both come back if the parents do. Alternative: keep the block and let `update_machine_item` zero a hidden row as the one exception to Q7. Alternative: keep it as it is, and clean up with a script.
**Answer:** stock on a deleted machine does not block `delete_item`. **The owner's own answer (2026-10-30).** A machine of a deleted factory counts too, because both are hidden the same way (BUG-979): **Claude's reading, not the owner's words.**
**Resolution:** no new ID, no rule here. Routed to `item_manager.spec.md` `delete_item` R9 (b) and BUG-948, where it is already recorded (FU-5).

### Q6. A stock row is removed while open orders still need it — 🐞 BUG-1081 (owner's answer)
**Background:** You ruled "refuse while in use, and list the blockers" for items and machines. That applies to a stock row too, but different rows depend on it, so the list is yours to set. Removing a row is a hard delete. With `qty > 0` the code books a final adjustment to 0, so it is a recorded write-off (this is the "Remove this item from the machine?" button). What each open order does after the delete (verified or read in `work_order_manager`):
- a work order line taking the item from this machine: at posting, 400 `Insufficient machine stock (0 available, 2 requested)`;
- a `REPLACE` line taking the old part off this machine: nothing removed, the order logs `item_replace_degraded` and carries on;
- a transfer order out of this machine, or a pending return of a purchase order delivered to it: fails at completion the same way (read, not run);
- a purchase order or a transfer into this machine: the row is simply re-created, no harm.
**What happens today:** Nothing is looked at; a row with stock and an open work order line sourcing from it is deleted (verified).
**Example:** Press 4 holds 10 bearings, and a draft work order will take 2 of them. A user removes the row: 204. Starting the order then fails with "0 available".
**Rules affected:** `delete_machine_item` R5
**Suggested answer:** `bug — refused with ValueError("Machine item has open orders", blockers), nothing written, while (a) a live DRAFT / IN_PROGRESS work order has a live line with uses_inventory = True, consumed_at empty, source machine = this machine and this item; (b) a live DRAFT / IN_PROGRESS work order on this machine has a live REPLACE line with replaced_item_id = this item; (c) a not-completed transfer order out of this machine has a line for this item; (d) a pending return of a purchase order delivered to this machine has a line for this item. Blockers as delete_item R9b: types work_order, transfer_order, purchase_return, then one other_workspace entry last. Does not block: the row's own qty (the delete stays a recorded write-off, and blocking it would only add one edit to 0), req_qty, defective_qty, purchase orders and transfers into the machine, ledger rows, activity.` Say so if stock itself should block. The defect count and target vanish with the row and no record keeps them; say so if that matters.
**Answer:** refuse the four cases and list the blockers, with the generic `other_workspace` entry per HR-16; the row's own `qty` does not block. **The owner's own answer (2026-10-31).**
**Resolution:** 🐞 BUG-1081 (pattern `delete-ignores-dependents`; per BUG-948, BUG-968), frontend note BUG-1082 (`refusal-reason-not-shown`). Rules: `delete_machine_item` R5, R5a, R5b. Service translation: FU-1 (a). **Refined by the owner, 2026-10-31:** a `REPLACE` line blocks only with `uses_inventory = True`, consumed or not; a pending return blocks whatever the purchase order's state, voided included. (The first answers, the reverse on both, are superseded: see the correction at the top.)

### Q7. Stock on a deleted machine can still be edited — 🐞 BUG-1083 (owner's answer)
**Background:** For a machine in a deleted factory the decision was "refuse like a deleted machine" (BUG-964), because a change made while hidden means a restore does not bring back what was hidden. This is a stock write, and it interacts with Q5: refusing leaves such a row with no way to change it until "restore machine" exists.
**What happens today:** `PUT` succeeds and writes a ledger entry and activity (verified), for a soft-deleted machine and for a machine of a soft-deleted factory.
**Example:** A stale tab changes the 7 bearings of deleted "Press 4" to 2: 200.
**Rules affected:** `update_machine_item` R2
**Suggested answer:** `bug — 400 Cannot update items of a deleted machine, nothing written, right after the row is found; an inactive-but-live machine or factory is not refused`.
**Answer:** bug — 400 `Cannot update items of a deleted machine`, as suggested. **The owner's own answer (2026-10-31).**
**Resolution:** 🐞 BUG-1083 (pattern `write-to-soft-deleted-related-row`). Rules: `update_machine_item` R2.

### Q8. Stock on a deleted machine can still be removed — 🐞 BUG-1084 (owner's answer)
**Background:** As Q7; for machines BUG-965. Removing is a hard delete, so it cannot come back when the machine does.
**What happens today:** `DELETE` answers 204 and books the final adjustment (verified).
**Example:** A stale tab removes the 7 bearings of deleted "Press 4". If the machine comes back, they are gone.
**Rules affected:** `delete_machine_item` R2
**Suggested answer:** `bug — 400 Cannot remove items from a deleted machine, nothing written, right after the row is found; an inactive-but-live machine or factory is not refused`.
**Answer:** bug — 400 `Cannot remove items from a deleted machine`, as suggested. **The owner's own answer (2026-10-31).**
**Resolution:** 🐞 BUG-1084 (pattern `write-to-soft-deleted-related-row`). Rules: `delete_machine_item` R2.

### Q9. A removed catalog item can be added to a machine, and the row is then invisible — 🐞 BUG-1085 (owner's answer)
**Background:** BUG-1010 makes the item check real, but a removed item (`is_active = False`) is still "in the workspace". Stock of a removed item is hidden (BUG-980, BUG-1070). So accepting it creates a row nobody can see. The inventory manager has the same conflict open: `create_inventory` R3a accepts an inactive item (FU-6).
**What happens today:** 201, with a ledger entry and activity; the row is then left out of the machine's list once BUG-980 is fixed (verified, without the fix).
**Example:** "Old Gasket" was removed from the catalog. A stale form adds 3 to Press 4: 201, and the list does not show them.
**Rules affected:** `create_machine_item` R6
**Suggested answer:** `bug — 400 Cannot add a removed item to a machine, after the item check, before the duplicate check, nothing written`.
**Answer:** bug — 400 `Cannot add a removed item to a machine`, as suggested. **The owner's own answer (2026-10-31).**
**Resolution:** 🐞 BUG-1085 (pattern `write-to-soft-deleted-related-row`). Rules: `create_machine_item` R6. FU-6.

### Q10. Stock of a removed item can still be edited or removed by id — ✅ intended (owner's answer)
**Background:** An item with non-zero stock cannot be removed (BUG-948), so a row of a removed item normally has `qty = 0` and at most a target. Older rows may hold stock. Unlike a deleted machine, the parts are physically there, and the rows still move in stock postings.
**What happens today:** `PUT` and `DELETE` both succeed (verified).
**Example:** Press 4 still holds 3 "Old Gasket" from before the rule. A storekeeper clears the row through its id.
**Rules affected:** `update_machine_item` R3, `delete_machine_item` R3
**Suggested answer:** `intended` — the reasoning of `create_inventory` R3a: removing a catalog entry does not erase parts, and this is the only way left to correct such a row. Alternative: `bug — refused as Q7, Q8`.
**Answer:** intended. **The owner's own answer (2026-10-31).**
**Resolution:** rules unchanged. Rules: `update_machine_item` R3 ✅, `delete_machine_item` R3 ✅.

### Q11. A stored row with another workspace's item shows that item's name and id — 🐞 BUG-1086
**Background:** HR-16 says such a row is invalid data and that no response shows another workspace's ids or names. BUG-1010 stops new rows, but rows already written stay. `MachineItemResponse` returns `item_id`, and `item_name` / `item_unit` read the linked item whatever its workspace. `_item_name` does check the workspace and falls back to `Item #<id>`, which is the other workspace's id. `scripts/find_cross_workspace_rows.py` finds these rows and changes nothing. HR-16 decides that they must not show; it does not say what the user gets instead.
**What happens today:** `GET`, the lists and `PUT` return the other workspace's `item_id`, `item_name`, `item_unit`, and the activity log stores `Item #<id>` (verified).
**Example:** Workspace A holds a row linked to workspace B's "Secret Alloy". A's machine page shows "Secret Alloy".
**Rules affected:** `_item_name` R3, `get_machine_item` R6, `list_machine_items` R9, `update_machine_item` R15, `delete_machine_item` R11
**Suggested answer:** `bug — such a row is treated as not found: left out of both lists in the query, 404 Machine item not found on get, update and delete, whatever include_deleted says.` The row stays for a one-off clean-up after the audit script, and `delete_item` keeps counting it as `other_workspace`. `_item_name`'s fallback then has no caller left: remove it with the fix. Alternative: keep the row visible with `item_name` and `item_unit` empty; that still shows the id.
**Answer:** bug — per HR-16: such a row is treated as not found everywhere — decided by Claude under the reviewer's delegation (2026-10-31).
**Resolution:** 🐞 BUG-1086 (pattern `cross-workspace-row-exposed`). The test is the item's own `workspace_id` against the row's. The machine link needs no such test: `create_machine_item` and the stock movements read the machine by workspace, so they do not write one. The `_item_name` fallback goes on the dead-code list. Rules: `_item_name` R3, `get_machine_item` R6, `list_machine_items` R9, `update_machine_item` R15, `delete_machine_item` R11.

### Q12. Stock added by hand after the machine held none is valued at the old average — ✅ intended (owner's answer)
**Background:** You decided a manual change keeps "the current average" and that "a first entry with no history stays 0.00". A row removed and added again, or an edit from 0 to 5, has history. The manual forms take no price. Receipts behave differently: at `qty_before = 0` a receipt ignores the old average and uses its own price.
**What happens today:** Everything is 0.00 (BUG-993). After the fix, as worded, the old average carries over.
**Example:** Press 4 ran out of bearings two years ago at an average of 5.00. A storekeeper adds 4 by hand: valued 20.00, although bearings cost 9.00 now.
**Rules affected:** `_write_ledger_entry` R2 (the sentence on zero stock), `create_machine_item` R10
**Suggested answer:** `intended` — it is what BUG-993 says, and a stale price beats 0.00, which would dilute the next receipt (verified: 10 @ 0.00 + 10 @ 3.00 averages 1.50).
**Answer:** intended. **The owner's own answer (2026-10-31).**
**Resolution:** rules unchanged. Rules: `_write_ledger_entry` R2 ✅, `create_machine_item` R10 ✅.

### Q13. A quantity edit writes two activity entries — ✅ intended
**Background:** The machine's activity log has `inventory_adjusted` ("Inventory adjusted on Bolt: 5 → 12") and `item_updated` ("Item updated: Bolt"). A `qty` change goes through both. Removing a row with stock also writes two, but those say different things.
**What happens today:** One edit of `qty` gives both entries, each listing the same `qty` change (verified). No ledger or stock effect.
**Example:** A storekeeper corrects a count. The activity panel shows two lines for one edit.
**Rules affected:** `update_machine_item` R11
**Suggested answer:** `intended` — cosmetic, and the `item_updated` entry carries the row id and any target change. Answer `bug — item_updated leaves out qty, and is not written when qty is all that changed` to remove the repeat.
**Answer:** intended — decided by Claude under the reviewer's delegation (2026-10-31).
**Resolution:** rule unchanged. Rules: `update_machine_item` R11 ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this manager. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Machine item service / endpoint** (`app/services/machine_item_service.py`, `app/api/v1/endpoints/machine_items.py`) | (a) BUG-1081: translate the `ValueError` into `app.core.exceptions.ValidationError(detail=exc.args[0], errors=exc.args[1])`, or it is a 500; every other refusal here is an `HTTPException`. (b) BUG-1077: expose `include_deleted` on `GET /machine-items/{id}/`. (c) Until BUG-1010 is fixed an unknown item answers 409 `Referenced resource does not exist.` through the global `IntegrityError` handler. A lost BUG-983 race would today give that handler's generic 409, not a 500; the exact message is `create_machine_item` R8. (d) `DataError` has no handler: 500 (BUG-1078 removes the path here). | P4, P5, Q6 |
| FU-2 | **Schemas** (`app/schemas/machine_item.py`) | All schema-side fixes go on `MachineItemCreate` / `MachineItemUpdate`: `null` handling (P2), `ge=0` (Q3), `le=2147483647` (P5). `MachineItemResponse` inherits `MachineItemBase`: a `ge=0` on the base also fails the **response** for a row already negative, so the limits go on the input schemas only. | P2, P5, Q3 |
| FU-3 | **Stock movements, ledger manager, transfer orders** (BUG-661, BUG-643, BUG-820, and BUG-1072, BUG-1073 here); machine item DAO FU-3 (a) | `MachineItem.item` is `lazy="joined"`, so every query on this model carries a `LEFT OUTER JOIN items`. A plain `with_for_update()` then fails: `FeatureNotSupported`, pgcode `0A000`, `FOR UPDATE cannot be applied to the nullable side of an outer join` (verified). The lock must be `with_for_update(of=MachineItem)`: `FOR UPDATE OF machine_items` works (verified). | HR-10 lines |
| FU-4 | **Frontend** (`frontend/src/components/newcomponents/customui/MachineDetailBody.tsx`, `MachineDetailPanel.tsx`, `EditMachineDialog.tsx`) | (a) `req_qty: reqQty ?? undefined` omits an emptied box, so it can never clear the value even after P2: it must send `null`. (b) BUG-1082: `handleDeleteItem` must show the blockers. (c) The activity filter's "Inventory" option sends only `item_added`, so `item_updated`, `item_removed` and `inventory_adjusted` are not under it. | P2, Q6, Q13 |
| FU-5 | **Item manager** (`tests/unit/managers/item_manager.spec.md`) | Q5 is applied there: `delete_item` R9 (b), R9a, BUG-948. Nothing left to route. | Q5 |
| FU-6 | **Inventory manager** (`tests/unit/managers/inventory_manager.spec.md`) | `create_inventory` R3a still accepts a removed item although BUG-883 hides its stock. The owner's Q9 answer refuses it here; that spec should follow. | Q9 |
| FU-8 | **Machine item DAO** (`tests/unit/dao/machine_item.spec.md`) | BUG-1086 needs the item's workspace compared on the `machine_id` path, so `get_by_machine` gains a filter or the manager replaces it; `get_by_machine` R1, R11 change with that. BUG-1070 needs a filtered workspace query (`get_by_workspace` R2 stays raw or the copy goes). | Q11 |
| FU-9 | **`machine_item_ledger.spec.md` FU-1** | Still calls the repair of stored data open: answered, Q1 here and BUG-993. | Q1 |
| FU-10 | **Work order and purchase order services** (not yet specified) | The facts behind the owner's correction, for those reviews. (a) `_apply_item_completion` takes the old part off only for a line with `uses_inventory = True` and `consumed_at` set, so a consumed `REPLACE` line on an open order still removes it at completion; with no stock row it logs `item_replace_degraded` and installs without removing anything. A line with `uses_inventory = False` returns early and moves no stock. (b) `complete_return` reads neither `po.voided` nor the stage, and `void_purchase_order` does not stop for an open return, so a pending return on a voided order can still be completed. Whether either should is for those reviews. Read, not run. | gaps 4, 5 |
| FU-7 | **Ledger DAO / all readers of cost** | With BUG-993 a manual entry's value can exceed `Numeric(15, 2)` only at absurd figures (`qty` near `2**31` × an average near 10 000): `DataError`, as for every other writer. No rule here. | BUG-993 |

Answered here: machine item DAO FU-1 (a) BUG-1070, BUG-1071; (b) P1; (c) BUG-1010, Q9; (d) Q3; (e) P2; (f) P4, Q7, Q8, Q10; (g) BUG-1072, BUG-1073; (h) BUG-983 `create_machine_item` R8. Machine item DAO FU-4: Q5. Ledger DAO FU-1: `_write_ledger_entry` R2–R7, Q1. Ledger DAO FU-6: `_write_ledger_entry` R3, Q2. Machine manager FU-7: `create_machine_item` R1, R5.

## Overview
`MachineItemManager` is the manual side of a machine's stock: a user adds an item to a machine, corrects its quantities, or removes it. Each row of `machine_items` is the current figure of one item on one machine; the ledger (`machine_item_ledger`) is the record of movements and holds the machine's average cost, because a machine has no stored average. Called only by `MachineItemService` behind `/machine-items/`. It is meant to protect workspace isolation, one row per machine and item, and a ledger entry for every manual change of a stock quantity, carrying the current average. It never commits; DAOs and the activity manager flush. Every refusal is an `HTTPException`, except the in-use refusal of `delete_machine_item` (R5a, a `ValueError`).

**Callables:** 7 specified · 2 not specified
**Externals to mock:** none. No code here reads the clock. (`performed_at` and `created_at` are Python column defaults bound at import: patching `utcnow` does not change them. Assert set / not set.)
**Integration-only behavior:** the HTTP status of the refusals; schema validation at the API (400 today, BUG-461; 422 intended); `skip >= 0`, `1 <= limit <= 1000`; the global `IntegrityError` handler; the service's commit, rollback and `db.refresh`. Two real concurrent transactions.

**Facts for the test designer**
- Import: `from app.managers.machine_item_manager import MachineItemManager, machine_item_manager`. `MachineItemManager()` takes no arguments and holds no per-call state. `_write_ledger_entry`'s parameters after `session` are keyword-only; the others are positional-or-keyword. The service calls `get_machine_item` positionally and the rest by keyword.
- `HTTPException` is `fastapi.HTTPException`: assert `.status_code` and `.detail` (a plain string). Database errors are `sqlalchemy.exc.IntegrityError` / `DataError` with `.orig` a `psycopg2` error class. Schema errors are `pydantic.ValidationError`.
- Table `machine_items`, its constraints, relationships and the schemas: machine item DAO spec, **Model facts**. Table `machine_item_ledger`: ledger DAO spec, **Model facts**.
- `machine_activity_events`: `workspace_id`, `machine_id`, `event_type`, `description`, `metadata_json` (column `metadata`, JSON), `performed_by`, `created_at`. FK `machine_activity_events_performed_by_fkey`. The activity manager's `log_event` adds one row and flushes.
- `MACHINE_ITEM_LOG_FIELDS`, in order: `qty` "Quantity", `req_qty` "Required quantity", `defective_qty` "Defective quantity". A `changes` entry is `{"field", "label", "from_value", "to_value"}`; values are strings (`"5"`) or `None`.
- Collaborator rules cited, not repeated: machine item DAO `get_by_workspace`, `get_by_id_and_workspace`, `get_by_machine`, `get_by_machine_and_item`, inherited R1–R12 (`tests/unit/dao/machine_item.spec.md`); ledger DAO `get_latest_entry` (`tests/unit/dao/machine_item_ledger.spec.md`); `get_machine_unit_cost` (`tests/unit/managers/inventory_movements.spec.md`).

**Notes for the test designer**
- Workspaces and profiles from `tests/unit/factories.py`. Build `Factory`, `Machine`, `Item`, `MachineItem`, `MachineItemLedger` rows directly (add + flush; column lists in the DAO specs' Notes). `autoflush=False`: flush before calling the manager.
- **Reading rows:** assert ledger and activity rows with a fresh `SELECT`. Compare `metadata_json` as a whole dict, order of `changes` included. Compare `Decimal` by value.
- **Hidden parents:** as machine item DAO Notes: soft-deleted machine = `is_deleted=True, is_active=False`; soft-deleted factory = `is_active=True, is_deleted=True` with a live machine in it; removed item = `is_active=False`; inactive-but-live = `is_active=False, is_deleted=False`.
- **Ledger history for BUG-993:** build earlier `MachineItemLedger` rows directly with an explicit past `performed_at`; the manager's own entry takes the clock at flush, so it is newest against those rows. Two entries stamped by the real clock can tie (ledger DAO Model facts: 30 `create` calls gave 10 distinct timestamps), and the order among them is then BUG-664's. Where a case needs one real-clock entry after another, give each a rising explicit past `performed_at` after writing it, and flush, before the next step. For the chain (R9) go through `_machine_in` / `_machine_out` of `app.managers.inventory_movements`, as in `tests/unit/managers/test_inventory_movements.py`.
- **Half up (BUG-1040) on `total_cost`:** a stored average has two decimals and `qty` is an integer, so the product is exact and nothing rounds. It is observable only while an unexpired instance holds more decimals. Build the latest entry with `avg_price_after=Decimal("0.125")`, flush, **do not** refresh or expire it, change `qty` by 1: intended `total_cost` `0.13`. Verified: `get_machine_unit_cost` returns `0.125` before expiry and `0.13` after.
- **BUG-1072, BUG-1073 (lock):** setup rows are uncommitted, so a second connection cannot see them. Capture statements with a `before_cursor_execute` listener on the session's connection and assert the `SELECT` on `machine_items` carries `FOR UPDATE`. Today none does (verified) → strict xfail. Do not require the exact `OF` clause in the assertion text beyond `FOR UPDATE`.
- **BUG-983 (lost race):** `unittest.mock.patch.object(machine_item_manager.machine_item_dao, "get_by_machine_and_item", return_value=None)`. The manager's attribute and the module's name are the same DAO object (verified), and the manager calls it through `self.machine_item_dao`, so patch the method on that object, not the name, with a row already there; wrap in `db.begin_nested()` inside `pytest.raises(HTTPException)`. Today a second row is saved → strict xfail. Build no other case with two rows for one key.
- **BUG-1010:** the item of another workspace is built with W2's `workspace_id`; assert the row count is unchanged. Today 201 for that one and `IntegrityError` for a missing id → strict xfail, each one.
- **BUG-1070:** compare **sets** of ids → strict xfail, with a row under live parents in the same case. **BUG-1071:** physical order is not an order → **non-strict** xfail; names `"Zulu"`, `"apple"`, `"Banana"`, inserted in that order (today they came back in insertion order). Never weaken the assertion.
- BUG-993 → strict xfail; today's zeros are deterministic. R5–R8 of `_write_ledger_entry` pass today.
- **`action_type`:** `CONSUME` (the default), `INSTALL`, `REPLACE`, `BORROW` are the application's values (`app/schemas/work_order.py`). The column is `varchar(20)` with no check; all four insert. R5 (a) does not read it: `_consume_item` posts the same stock-out for all four (verified: `p11.py`).
- **BUG-1081 rows:** columns as machine manager Notes ("Classes", "BUG-968 rows"). A blocking source line and a blocking `REPLACE` line must set `uses_inventory=True` (the column defaults `False`). A `REPLACE` line: `action_type="REPLACE"`, `replaced_item_id` = the item, the order's `machine_id` = the machine. Returns: `PurchaseOrderReturn` (`workspace_id`, `purchase_order_id`, `return_number`, `created_by`, all NOT NULL with no default; `status` defaults `pending`; verified to insert) and `PurchaseOrderReturnItem` (`workspace_id`, `return_id`, `po_item_id`, `item_id`, `quantity_returned`) from `app.models.purchase_order_return`, on a `PurchaseOrder` with `destination_type="machine"`. Assert `exc.args[0]` and `exc.args[1]`, never `str(exc)`. A row in W2 gives `{"type": "other_workspace"}`: assert no W2 id appears in `exc.value.args`.
- **BUG-1086 rows:** a `MachineItem` of W with an item of W2, built directly. BUG-1010 refuses it through the manager, so never build it with `create_machine_item`.
- **Schema rules (BUG-1075 `null`, BUG-1078, BUG-1079):** build the schema inside `pytest.raises(pydantic.ValidationError)`. Assert `MachineItemBase(machine_id=1, item_id=1, qty=-1)` stays valid.
- Strict xfail, outcome deterministic today: BUG-1074, BUG-1075, BUG-1076, BUG-1077, BUG-1078, BUG-1079, BUG-1080, BUG-1081, BUG-1083, BUG-1084, BUG-1085, BUG-1086. BUG-1082 is frontend: no case here.
- **Refusals after a flush:** none today: every refusal comes before the first write. **Database errors** abort the transaction: `with db.begin_nested():` inside `pytest.raises(...)`. **Not committed:** `sp = db.begin_nested()`, call, `sp.rollback()`, re-read.
- Inherited DAO bugs here get one pass-through case each, written to the intended behavior and marked xfail with that bug's ID: strict for BUG-979, BUG-980; non-strict for BUG-976.

## Not specified
- `MachineItemManager.__init__` — stores the DAOs, no logic
- `machine_item_manager` — module-level singleton, no logic

The checklist (`docs/testing/unit-test-checklist-by-layer.md`) marks nothing of this file as possibly unused, and every public method is reachable from the API. (`_item_name`'s fallback is reached only by the invalid rows of Q11; it goes with BUG-1086 and is on the dead-code list.) No legacy test calls this manager.

---

## `MachineItemManager._item_name(session, item_id, workspace_id)`
**Shape:** helper
**Persistence:** reads
**Visibility:** internal (used by: `_write_ledger_entry`, `create_machine_item`, `update_machine_item`, `delete_machine_item`)

**Purpose:** The text used for an item in activity entries.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `item_id` | int | looked up inside the workspace |
| `workspace_id` | int | the row's workspace |

**Returns:** a `str`.

**Rules:**
- **R1.** An item of that workspace → its `name`.
- **R2.** A removed item (`is_active = False`) of that workspace → its `name`, like any other.
- **R3.** [BUG-1086] (Q11, HR-16) No activity entry shows another workspace's id: a stored row with such an item is refused before this helper is reached (`update_machine_item` R15, `delete_machine_item` R11), and `create_machine_item` never links one (R5). The fallback `Item #<item_id>` goes with the fix, so this rule gets no direct case. *(Today: an item of another workspace, an unknown id or `0` gives `Item #<item_id>`, no error.)*

**Errors:** none.

**Side effects:** none

---

## `MachineItemManager.get_machine_item(session, machine_item_id, workspace_id, include_deleted=False)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `MachineItemService.get_machine_item` ← `GET /machine-items/{id}/`)

**Purpose:** One stock row by id, inside a workspace.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `machine_item_id` | int | primary key |
| `workspace_id` | int | caller's workspace; compared with the row's own `workspace_id` |
| `include_deleted` | bool, default `False` | [BUG-1077] new parameter, reachable from the API |

**Returns:** the `MachineItem`, with its item loaded.

**Rules:**
- **R1.** A row of that workspace is returned.
- **R2.** A row of another workspace, an unknown id or `0` → 404 `Machine item not found`; the three answers are identical.
- **R3.** [BUG-1077] (P4, HR-4) A row of a soft-deleted machine, of a machine in a soft-deleted factory, or of a removed item → 404 `Machine item not found`. *(Today: returned.)*
- **R3a.** [BUG-1077] With `include_deleted=True` those rows are returned. *(Today: the parameter does not exist.)*
- **R4.** A machine or factory with `is_active = False`, `is_deleted = False` hides nothing.
- **R5.** The call writes nothing.
- **R6.** [BUG-1086] (Q11, HR-16) A stored row whose item belongs to another workspace → 404 `Machine item not found`, also with `include_deleted=True`. *(Today: returned, and `item_name`, `item_unit` give that item's values.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / other workspace; [BUG-1077] hidden row; [BUG-1086] another workspace's item | `HTTPException` 404 | `Machine item not found` |

**Side effects:** none

---

## `MachineItemManager.list_machine_items(session, workspace_id, machine_id=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `MachineItemService.get_machine_items` ← `GET /machine-items/`, always with `skip`, `limit`)

**Purpose:** The stock rows of a workspace, or of one machine, one page at a time.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `workspace_id` | int | caller's workspace |
| `machine_id` | int \| `None` | optional filter; only `None` means "no filter" [BUG-1074]; existence not checked |
| `skip`, `limit` | int | defaults `0`, `100`; not validated here |

**Returns:** a `list` of `MachineItem`, each with its item loaded (possibly empty).

**Rules:**
- **R1.** With a `machine_id`, the result follows machine item DAO `get_by_machine` R1–R11, including [BUG-976] order, [BUG-979] deleted machine or factory, [BUG-980] removed item. One pass-through case each.
- **R2.** A `machine_id` of another workspace, an unknown one or a negative one returns `[]`, no error.
- **R3.** [BUG-1074] (P1) `machine_id=0` filters like any integer and returns `[]`. *(Today: every row of the workspace, as with `None`.)*
- **R4.** Without a `machine_id`, only rows with that `workspace_id` are returned; an unknown or empty workspace gives `[]`.
- **R5.** At most `limit` rows after skipping `skip`, on both paths; by default at most 100: given 101 rows, exactly 100. Consecutive windows partition the rows, with no repeats or gaps (relies on R8 and BUG-976). `limit=0` or `skip` at or past the end gives `[]`.
- **R6.** A negative `limit` or `skip` raises `DataError`, as machine item DAO `get_by_workspace` R6, on both paths.
- **R7.** [BUG-1070] (HR-4, HR-5) Without a `machine_id`, a row of a soft-deleted machine, of a machine in a soft-deleted factory, or of a removed item is not returned and takes no place in the page: given Anvil (removed) and Bolt (active), `limit=1` returns Bolt. *(Today: all are returned and counted in the page. Requires a filtered query: machine item DAO `get_by_workspace` stays raw or goes.)*
- **R7a.** What surrounds R7, holding today and after the fix: an inactive-but-live machine or factory hides nothing, the call changes nothing, and a parent made live again brings the row back unchanged.
- **R8.** [BUG-1071] (HR-6) Without a `machine_id`, rows are ordered by item name case-insensitive ascending, then row `id` ascending, before `skip` / `limit`: "Zulu", "apple", "Banana" come back "apple", "Banana", "Zulu"; items "Bolt" and "bolt" come back lower row `id` first. *(Today: no ordering is requested; the order is whatever the database produces.)*
- **R9.** [BUG-1086] (Q11, HR-16) A stored row whose item belongs to another workspace is left out on both paths, in the query, and takes no place in the page. *(Today: listed with that item's name.)*
- **R10.** Rows are returned whatever their quantities (`0`, negative, empty `req_qty`). The call writes nothing.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `DataError`; `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| negative `skip` | `DataError`; `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |

**Side effects:** none

---

## `MachineItemManager._write_ledger_entry(session, *, workspace_id, machine_id, item_id, transaction_type, quantity, qty_before, qty_after, user_id, notes, source_type="manual")`
**Shape:** event-log
**Persistence:** writes
**Visibility:** internal (used by: `create_machine_item`, `update_machine_item`, `delete_machine_item`)

**Purpose:** Book one manual stock change in the machine's ledger, and log it when it is an adjustment.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id`, `machine_id`, `item_id` | int | stored as given; not validated |
| `transaction_type` | str | `manual_add` or `inventory_adjustment` from the callers |
| `quantity` | int | size of the change, always positive from the callers |
| `qty_before`, `qty_after` | int | stored as given |
| `user_id` | int | `performed_by`, and the event's `performed_by` |
| `notes` | str | stored as given |
| `source_type` | str, default `"manual"` | `adjustment` from update and delete |

**Returns:** `None`.

**Definition — current average:** `avg_price_after` of the latest entry of this workspace, machine and item (ledger DAO `get_latest_entry` R2–R5, BUG-664 on a tie), read before this entry is written. An empty value counts as 0.

**Rules:**
- **R1.** One `machine_item_ledger` row is written with the arguments as given, `performed_by = user_id`, `performed_at` set; `source_id`, `order_id`, `order_type`, `invoice_id` and the `transfer_*` columns stay `None`.
- **R2.** ✅ (Q12) [BUG-993] `unit_cost`, `avg_price_before` and `avg_price_after` = the current average: with an average of 5.00 all three are 5.00. It applies whatever the stock was: also when `qty_before` is 0, or the machine's row was removed and added again (Q12). *(Today: all 0.00.)*
- **R3.** [BUG-993] [BUG-1040] `total_cost` = |`quantity`| × the current average, rounded half up to two decimals (HR-15): 2 × 5.00 = 10.00; 1 × 0.125 = 0.13 (see Notes). *(Today: 0.00.)*
- **R4.** [BUG-993] [BUG-1040] `value_before` = `qty_before` × the average; `value_after` = `qty_after` × the average, as `_machine_out` computes them: 10 → 12 at 5.00 gives 50.00, 60.00. Both round half up to two decimals (HR-15): at an unexpired average of `0.125` (Notes), 1 → 2 gives `value_before` 0.13, `value_after` 0.25. A stored negative quantity gives a negative value. *(Today: both 0.00.)*
- **R5.** With no ledger entry for this workspace, machine and item, all six cost fields are `0.00`, even when another machine, another item or another workspace has entries with a non-zero average (owner, BUG-993: a first entry with no history stays 0.00). Holds today and after the fix.
- **R6.** A latest entry with an empty `avg_price_after` counts as 0: all six cost fields are `0.00`, whatever `value_after` holds. Holds today and after the fix.
- **R7.** A latest entry with `avg_price_after = 0.00` stays at 0.00, even when older entries have a non-zero average: the older ones are not read. Holds today and after the fix. Stored data is repaired by appending entries (Q1, `scripts/repair_machine_zero_average.py`), not here.
- **R8.** [BUG-993] Only the latest entry counts: entries at 09:00 (avg 3.00), 11:00 (avg 5.00), 10:00 (avg 4.00), and a newer entry of another machine at 9.00, give 5.00. *(Today: 0.00.)*
- **R9.** [BUG-993] The next movement sees the average. Receive 10 @ 5.00, change to 12 by hand: `calculate_balance` gives `(12, Decimal("60.00"))`, `get_machine_unit_cost` 5.00; a consumption of 2 is priced 5.00, and the balance is `(10, 50.00)`. *(Today: `(12, 0.00)`, 0.00, priced 0.00, `(10, 0.00)`.)*
- **R10.** When `transaction_type` is `inventory_adjustment`, one activity entry is written: `event_type = "inventory_adjusted"`, `description = "Inventory adjusted on <name>: <qty_before> → <qty_after>"` (`<name>` from `_item_name`), `performed_by = user_id`, the arguments' workspace and machine, `metadata_json = {"item_id", "item_name", "quantity", "changes": [{"field": "qty", "label": "Quantity", "from_value": "<qty_before>", "to_value": "<qty_after>"}]}`.
- **R11.** For any other `transaction_type` (`manual_add`), no activity entry is written here.
- **R12.** An unknown `user_id` raises `IntegrityError` (`ForeignKeyViolation`, `machine_item_ledger_performed_by_fkey`).
- **R13.** Flushed, not committed: rolling back a savepoint around the call removes the entry and the event.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| unknown `user_id` | `IntegrityError` / `ForeignKeyViolation` | — |

**Side effects:** one `machine_item_ledger` row; for an adjustment, one `machine_activity_events` row. Both flushed. No commit.

---

## `MachineItemManager.create_machine_item(session, item_data, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `MachineItemService.create_machine_item` ← `POST /machine-items/`)

**Purpose:** Put a catalog item on a machine, with its opening quantity booked in the ledger.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session; not committed here |
| `item_data` | `MachineItemCreate` | `machine_id`, `item_id` required; `qty` default `0`; `req_qty`, `defective_qty` default `None`; no range |
| `workspace_id` | int | caller's workspace |
| `user_id` | int | `performed_by` of the ledger entry and the event |

**Returns:** the new `MachineItem`, flushed, not committed.

**Rules:**
- **R1.** A machine that is missing, of another workspace, or `0` → 404 `Machine not found in this workspace`; the answers are identical; nothing written.
- **R2.** A soft-deleted machine → 400 `Cannot add items to a deleted machine`; nothing written.
- **R3.** [BUG-1076] (P3) A live machine in a soft-deleted factory is refused like a deleted machine: 400 `Cannot add items to a deleted machine`, right after R2; nothing written. *(Today: accepted.)*
- **R4.** A machine with `is_active = False`, `is_deleted = False`, or in a factory with `is_active = False`, `is_deleted = False`, is accepted.
- **R5.** [BUG-1010] (HR-16) The item must exist in the caller's workspace: a missing id, `0`, or an item of another workspace → 404 `Item with ID <item_id> not found`, the same answer for all three, after the machine checks and before the duplicate check; nothing written. *(Today: another workspace's item is saved, with a ledger entry, and its name is returned; a missing id or `0` raises `IntegrityError` on `machine_items_item_id_fkey`, a generic 409 at the API.)*
- **R6.** [BUG-1085] (Q9) A removed item of the workspace → 400 `Cannot add a removed item to a machine`, after R5 and before R7; nothing written. *(Today: accepted, with a ledger entry and activity.)*
- **R7.** A row for this machine and item in this workspace → 409 `This item already exists on this machine. Update the existing record instead.`; nothing written. The lookup is raw (machine item DAO `get_by_machine_and_item`). A row of the same machine and item under another `workspace_id` does not block.
- **R8.** [BUG-983] When two requests race past R7, the database refuses the second row and the manager gives the same 409 as R7, not a database error; nothing is saved for that request. *(Today: no index, and the second row is saved.)*
- **R9.** One row is created with `machine_id`, `item_id`, `qty`, `req_qty`, `defective_qty` from the input and `workspace_id` = the argument. The returned row's `item_name` and `item_unit` read the item.
- **R10.** ✅ (Q12) `qty > 0`: one ledger entry through `_write_ledger_entry`: `transaction_type = "manual_add"`, `quantity = qty`, `qty_before = 0`, `qty_after = qty`, `source_type = "manual"`, `notes = "Initial machine inventory record created"`. `qty_before` is 0 whatever the ledger holds. Costs follow that method's R2–R7.
- **R11.** `qty = 0` (also by default): no ledger entry.
- **R12.** [BUG-1079] (Q3) `qty < 0` is rejected by `MachineItemCreate` (`pydantic.ValidationError`, at the API a validation error); `0` is accepted; nothing written. `MachineItemBase` has no minimum. *(Today: stored, with no ledger entry.)*
- **R13.** [BUG-1079] (Q3) A negative `req_qty` or `defective_qty` is rejected the same way; `0` and `None` are accepted. *(Today: stored.)*
- **R14.** [BUG-1078] (P5) A quantity above `2147483647` is rejected by `MachineItemCreate` (`ValidationError`); `2147483647` is accepted and stored. *(Today: `DataError`, `NumericValueOutOfRange`, pgcode `22003`, at the flush; a 500 at the API.)*
- **R15.** One activity entry whatever the `qty`: `event_type = "item_added"`, `description = "Item added: <name>"` (`<name>` from `_item_name`), `performed_by = user_id`, `workspace_id` = the argument, `metadata_json = {"item_id", "item_name", "machine_item_id", "quantity": qty}`.
- **R16.** Unknown `user_id` → `IntegrityError` (`ForeignKeyViolation`): with `qty > 0` on `machine_item_ledger_performed_by_fkey`, with `qty = 0` on `machine_activity_events_performed_by_fkey`. Nothing saved once the transaction rolls back.
- **R17.** Flushed, not committed: rolling back a savepoint around the call removes the row, the entry and the event.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| machine missing / other workspace / `0` | `HTTPException` 404 | `Machine not found in this workspace` |
| machine soft-deleted; [BUG-1076] its factory soft-deleted | `HTTPException` 400 | `Cannot add items to a deleted machine` |
| [BUG-1010] item missing / other workspace / `0` | `HTTPException` 404 | `Item with ID <item_id> not found` |
| [BUG-1085] item removed | `HTTPException` 400 | `Cannot add a removed item to a machine` |
| duplicate; [BUG-983] the same for the database violation | `HTTPException` 409 | `This item already exists on this machine. Update the existing record instead.` |
| [BUG-1079] negative quantity; [BUG-1078] above `2147483647` | `pydantic.ValidationError` building `MachineItemCreate` | not asserted |
| unknown `user_id` | `IntegrityError` / `ForeignKeyViolation` | — |

**Side effects:** one `machine_items` row; a ledger row when `qty > 0`; one `machine_activity_events` row; all flushed. No commit.

---

## `MachineItemManager.update_machine_item(session, machine_item_id, item_data, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `MachineItemService.update_machine_item` ← `PUT /machine-items/{id}/`)

**Purpose:** Correct a row's quantity, target or defect count, booking a quantity change in the ledger.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session; not committed here |
| `machine_item_id` | int | primary key |
| `item_data` | `MachineItemUpdate` | `qty`, `req_qty`, `defective_qty`, all `int \| None = None`; `0` … `2147483647` (BUG-1078, BUG-1079). Machine and item cannot be changed: other fields are ignored |
| `workspace_id` | int | caller's workspace |
| `user_id` | int | `performed_by` of the ledger entry and the events |

**Returns:** the same `MachineItem` instance, flushed, not committed.

**Rules:**
- **R1.** A row of another workspace, an unknown id or `0` → 404 `Machine item not found`; nothing written.
- **R2.** [BUG-1083] (Q7) A row of a soft-deleted machine, or of a machine in a soft-deleted factory → 400 `Cannot update items of a deleted machine`, right after the row is found; nothing written. An inactive-but-live machine or factory is not refused. *(Today: updated, with a ledger entry and activity.)*
- **R3.** ✅ (Q10) A row of a removed item is updated like any other.
- **R4.** [BUG-1072] (HR-10) The row is read `FOR UPDATE` before its quantity is used. *(Today: read without a lock.)*
- **R5.** Each of `qty`, `req_qty`, `defective_qty` sent with a value is written. `0` is a value: `qty = 0` and `defective_qty = 0` are applied.
- **R6.** [BUG-1075] (P2) An explicit `null` clears `req_qty` or `defective_qty`, and `item_updated` records `"to_value": None`. `qty: null` is rejected by `MachineItemUpdate` (`ValidationError`); an omitted field stays unchanged; `{}` changes nothing. *(Today: `null` is ignored on all three, 200.)*
- **R7.** When no field changes value (`{}`, the same values, or `null` on a field already empty), no ledger entry and no activity entry are written, and an unknown `user_id` raises nothing.
- **R8.** A `qty` that changes gives one ledger entry through `_write_ledger_entry`: `transaction_type = "inventory_adjustment"`, `quantity` = |new − old| (5 → 12 and 12 → 5 both give 7), `qty_before` = old, `qty_after` = new, `source_type = "adjustment"`, `notes = "Manual machine inventory adjustment: <old> -> <new>"`. Costs follow that method's R2–R7. A change to `0` counts.
- **R9.** `qty` sent unchanged next to another changed field: no ledger entry.
- **R10.** A change of `req_qty` or `defective_qty` alone gives no ledger entry; there is no ledger for those two.
- **R11.** ✅ (Q13) A `qty` change gives two activity entries: `inventory_adjusted` (`_write_ledger_entry` R10) and `item_updated` (R12).
- **R12.** Any changed field gives one `item_updated` entry: `description = "Item updated: <name>"`, `performed_by = user_id`, `metadata_json = {"item_id", "item_name", "machine_item_id", "changes": [...]}`. `changes` lists only fields whose value changed, in the order `qty`, `req_qty`, `defective_qty`, with old and new as strings, and `None` for an empty old value: `req_qty` from empty to 3 gives `"from_value": None, "to_value": "3"`.
- **R13.** [BUG-1079] (Q3) A negative `qty`, `req_qty` or `defective_qty` is rejected by `MachineItemUpdate`; `0` is accepted. A row already negative is edited to `0` or above as R8: −3 → 2 gives `quantity = 5`. *(Today: stored; 5 → −3 gives `quantity = 8`, `qty_after = -3`.)*
- **R14.** [BUG-1078] (P5) A quantity above `2147483647` is rejected by `MachineItemUpdate`; `2147483647` is accepted. *(Today: `DataError` at the flush; a 500 at the API.)*
- **R15.** [BUG-1086] (Q11, HR-16) A stored row whose item belongs to another workspace → 404 `Machine item not found`; nothing written. *(Today: updated, and its activity entries say `Item #<item_id>`.)*
- **R16.** Unknown `user_id` → `IntegrityError` (`ForeignKeyViolation`): with a `qty` change on `machine_item_ledger_performed_by_fkey`, with only another field changed on `machine_activity_events_performed_by_fkey`.
- **R17.** Flushed, not committed: rolling back a savepoint around the call restores the row and removes the entry and the events.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / other workspace; [BUG-1086] another workspace's item | `HTTPException` 404 | `Machine item not found` |
| [BUG-1083] deleted machine or factory | `HTTPException` 400 | `Cannot update items of a deleted machine` |
| [BUG-1079] negative; [BUG-1078] above `2147483647`; [BUG-1075] `qty: null` | `pydantic.ValidationError` building `MachineItemUpdate` | not asserted |
| unknown `user_id` | `IntegrityError` / `ForeignKeyViolation` | — |

**Side effects:** the row's changed fields; a ledger row when `qty` changes; up to two `machine_activity_events` rows; all flushed. No commit.

---

## `MachineItemManager.delete_machine_item(session, machine_item_id, workspace_id, user_id)`
**Shape:** delete
**Persistence:** writes
**Visibility:** public (used by: `MachineItemService.delete_machine_item` ← `DELETE /machine-items/{id}/`)

**Purpose:** Take an item off a machine: hard-delete its stock row, booking any stock left as a final adjustment.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session; not committed here |
| `machine_item_id` | int | primary key |
| `workspace_id` | int | caller's workspace |
| `user_id` | int | `performed_by` of the ledger entry and the events |

**Returns:** `None`.

**Rules:**
- **R1.** A row of another workspace, an unknown id or `0` → 404 `Machine item not found`; nothing written.
- **R2.** [BUG-1084] (Q8) A row of a soft-deleted machine, or of a machine in a soft-deleted factory → 400 `Cannot remove items from a deleted machine`, right after the row is found; nothing written. An inactive-but-live machine or factory is not refused. *(Today: deleted, with the final adjustment.)*
- **R3.** ✅ (Q10) A row of a removed item is deleted like any other.
- **R4.** [BUG-1073] (HR-10) The row is read `FOR UPDATE` before its quantity is used. *(Today: read without a lock.)*
- **R5.** [BUG-1081] (Q6, owner) A row still needed by an open order is not deleted: `ValueError`, nothing written, checked after R1 and R2 and before any write. It is needed when, for this row's machine and item:
  - **(a)** a live `DRAFT` / `IN_PROGRESS` work order has a live line with `item_id` = the item, `uses_inventory = True`, `consumed_at` empty, `source_location_type = 'machine'`, `source_location_id` = the machine, whatever its `action_type`: `CONSUME`, `INSTALL`, `REPLACE` and `BORROW` all draw the line's `item_id` from the source when consumed, so a `REPLACE` line that sources this item here blocks under (a) as well as any block under (b);
  - **(b)** a live `DRAFT` / `IN_PROGRESS` work order with `machine_id` = the machine has a live line with `action_type = 'REPLACE'`, `replaced_item_id` = the item and `uses_inventory = True`, whether `consumed_at` is set or not (owner, 2026-10-31, correction);
  - **(c)** a transfer order with `completed_at` NULL, `source_location_type = 'machine'`, `source_location_id` = the machine, has a line with `item_id` = the item;
  - **(d)** a purchase order return with `status = 'pending'`, on a purchase order with `destination_type = 'machine'`, `destination_id` = the machine, has a line with `item_id` = the item. The purchase order's state is not read: `Draft`, `Planning`, `Receiving`, `Complete` and `voided = True` all block, because the return can still be completed (owner, 2026-10-31, correction).

  A blocker counts whatever the state of the order's factory, of a transfer's destination, or, in (a), of the order's own machine (another machine, none, soft-deleted): soft-deleted or inactive makes no difference (**the owner's `delete_machine` G12 answer, applied here by Claude**).

  *(Today: none of this is looked at; the row is deleted.)*
- **R5a.** [BUG-1081] The `ValueError` has exactly two args: `args[0]` = `"Machine item has open orders"`; `args[1]` = a `list` of blockers, every blocker listed, as `delete_item` R9b: `{"type", "id"}` with `"type"` one of `"work_order"` (R5 (a), (b)), `"transfer_order"` (c), `"purchase_return"` (d), and `"id"` the order's or return's id, never a line id. One entry per order or return; sorted in that type order, then by `"id"` ascending. Every cross-workspace row of R5 (`workspace_id` differs from the stock row's, on the work order, transfer order, purchase order, return or line of R5) is covered by **one** entry, exactly `{"type": "other_workspace"}`, last, with nothing of the other workspace (HR-16). So a W1 return and line on a W2 purchase order give the generic entry, not `purchase_return` (decided by Claude under the reviewer's delegation (2026-10-31)). The `purchase_order_items` line behind a return line and the stage's `statuses` row are not read: their workspace changes nothing. The service turns it into a 400 (FU-1 (a)). *(Today: no refusal.)*
- **R5b.** What does not block, today and after the fix: the row's own `qty`, `req_qty`, `defective_qty`; under R5 (a) a line with `uses_inventory = False`, a consumed line, or a line with another source; under R5 (b) a line with `uses_inventory = False`, which moves no stock (owner, 2026-10-31, correction); a soft-deleted work order or line; a `COMPLETED` / `VOIDED` work order; a transfer with `completed_at` set; a transfer or purchase order into the machine; a `completed` / `voided` return; ledger rows and activity. Transfers and returns have no other state: `transfer_orders`, `transfer_order_items`, `purchase_order_returns` and `purchase_order_return_items` have no soft-delete column, a not-completed transfer is cancelled by deleting it with its lines, and `current_status_id` of a transfer is not read.
- **R6.** `qty > 0`: one ledger entry through `_write_ledger_entry`: `transaction_type = "inventory_adjustment"`, `quantity = qty`, `qty_before = qty`, `qty_after = 0`, `source_type = "adjustment"`, `notes = "Machine inventory record deleted"`, plus its `inventory_adjusted` entry. Costs follow that method's R2–R7: 5 at 3.00 gives `total_cost` 15.00, `value_before` 15.00, `value_after` 0.00.
- **R7.** `qty = 0`: no ledger entry.
- **R8.** [BUG-1080] (Q4) `qty < 0`: the same final adjustment as R6, with `quantity` = |`qty`|, `qty_before = qty`, `qty_after = 0`, and its `inventory_adjusted` entry, so the ledger ends at 0: −3 gives `quantity = 3`, balance `(0, 0.00)`. *(Today: no ledger entry; the balance stays −3.)*
- **R9.** One activity entry whatever the `qty`: `event_type = "item_removed"`, `description = "Item removed: <name>"`, `performed_by = user_id`, `metadata_json = {"item_id", "item_name", "machine_item_id"}`. It records neither the quantity nor `req_qty` nor `defective_qty`.
- **R10.** The row is hard-deleted, and its `req_qty` and `defective_qty` go with it. Earlier ledger entries and activity entries stay. A later `create_machine_item` for the pair gets a new row id.
- **R11.** [BUG-1086] (Q11, HR-16) A stored row whose item belongs to another workspace → 404 `Machine item not found`; nothing written. *(Today: deleted, and its activity entries say `Item #<item_id>`.)*
- **R12.** Unknown `user_id` → `IntegrityError` (`ForeignKeyViolation`): with `qty ≠ 0` (`qty > 0` today) on `machine_item_ledger_performed_by_fkey`, otherwise on `machine_activity_events_performed_by_fkey`. The row is not deleted.
- **R13.** Flushed, not committed: rolling back a savepoint around the call restores the row and removes the entry and the events.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / other workspace; [BUG-1086] another workspace's item | `HTTPException` 404 | `Machine item not found` |
| [BUG-1084] deleted machine or factory | `HTTPException` 400 | `Cannot remove items from a deleted machine` |
| [BUG-1081] still needed by an open order | `ValueError` (two args, R5a) | `Machine item has open orders` |
| unknown `user_id` | `IntegrityError` / `ForeignKeyViolation` | — |

**Side effects:** one `machine_items` row deleted; a ledger row when `qty ≠ 0`; one or two `machine_activity_events` rows; all flushed. No commit.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 30–32 | item lookup inside the workspace; removed item not looked at | `_item_name` R1, R2, R3 |
| 33 | item found / not found | `_item_name` R1, R3 |
| 39–41 | raw row lookup; parents not read (BUG-1077, BUG-1086) | `get_machine_item` R1, R3, R3a, R4, R6 |
| 42–43 | row found / not found | `get_machine_item` R1, R2 |
| 49 | defaults `skip=0`, `limit=100` | `list_machine_items` R5 |
| 52 | `if machine_id:` — value / `None` / `0` (BUG-1074) | `list_machine_items` R1, R3, R4 |
| 53–56 | DAO `get_by_machine`: filters, order, paging | `list_machine_items` R1, R2, R5, R6, R9, R10 |
| 57–59 | DAO `get_by_workspace`: no hiding (BUG-1070), no display order (BUG-1071) | `list_machine_items` R4, R5, R6, R7, R7a, R8, R9, R10 |
| 74 | default `source_type="manual"` | `_write_ledger_entry` R1 |
| 82–100 | the payload; every cost field is `zero` (BUG-993) | `_write_ledger_entry` R1–R9 |
| 101 | ledger row flushed; FK on `performed_by` | `_write_ledger_entry` R1, R12, R13 |
| 103 | `inventory_adjustment` / other type | `_write_ledger_entry` R10, R11 |
| 134–136 | raw machine lookup; factory not read (BUG-1076); inactive not read | `create_machine_item` R3, R4 |
| 137–138 | machine found / not found | `create_machine_item` R1 |
| 139–140 | machine soft-deleted | `create_machine_item` R2 |
| — (no item check) | BUG-1010, BUG-1085 | `create_machine_item` R5, R6 |
| 142–145 | raw lookup of the pair | `create_machine_item` R7 |
| 146–150 | existing row → 409 | `create_machine_item` R7 |
| 152–154 | create: flush; FK, range, unique index (BUG-983) | `create_machine_item` R5, R8, R9, R12, R13, R14 |
| 156 | name for the event | `create_machine_item` R15 |
| 159 | `record.qty > 0` / `0` / negative | `create_machine_item` R10, R11, R12 |
| 173–186 | `item_added`, always | `create_machine_item` R15, R16, R17 |
| 198–200 | raw row lookup; parents not read (BUG-1083, BUG-1086); no lock (BUG-1072) | `update_machine_item` R2, R3, R4, R15 |
| 201–202 | row found / not found | `update_machine_item` R1 |
| 205 | `exclude_unset`, `exclude_none`: `null` dropped (BUG-1075) | `update_machine_item` R5, R6 |
| `machine_activity_manager.py` 57–59 | `field not in update_dict` | `update_machine_item` R12 |
| `machine_activity_manager.py` 62–63 | same value skipped | `update_machine_item` R7, R12 |
| `machine_activity_manager.py` 40–48 | `format_field_value`: `None` / int (the `hasattr`, `datetime` and `date` branches are not reached by these fields) | `update_machine_item` R12 |
| 209 | update: flush; range error | `update_machine_item` R5, R13, R14 |
| 212 | `new_qty is not None and new_qty != old_qty` | `update_machine_item` R7, R8, R9, R10 |
| 219 | `abs(new_qty - old_qty)` | `update_machine_item` R8, R13 |
| 227 | `if changes:` | `update_machine_item` R7, R11, R12, R16 |
| 253–255 | raw row lookup; parents and orders not read (BUG-1084, BUG-1081, BUG-1086); no lock (BUG-1073) | `delete_machine_item` R2, R3, R4, R5, R5a, R5b, R11 |
| 256–257 | row found / not found | `delete_machine_item` R1 |
| 259 | `item.qty > 0` / `0` / negative (BUG-1080) | `delete_machine_item` R6, R7, R8 |
| 274–287 | `item_removed`, always | `delete_machine_item` R9, R12 |
| 289 | hard delete: flush | `delete_machine_item` R10, R13 |
| `base.py` 136–139 | `remove`: the row exists here, found just above | `delete_machine_item` R10 |
| `inventory_movements.py` 195–201 | latest entry / none / empty average (the reading BUG-993 reuses) | `_write_ledger_entry` R2, R5, R6 |

## Gap log
G1 (`machine_item_manager.cases.md` gap 1) — Contradiction, delegated — a W1 return and line on a W2 purchase order are cross-workspace (HR-16): the generic entry. `delete_machine_item` R5a. Decided by Claude under the reviewer's delegation (2026-10-31).
G2 (gap 2) — Fact — verified: `transfer_orders`, `transfer_order_items`, `purchase_order_returns`, `purchase_order_return_items` have no soft-delete, void or cancel column; a return's `status` is `pending`, `completed` or `voided`, with no check constraint; `delete_transfer_order` hard-deletes a not-completed transfer and its lines; a return has no delete of its own. Every workspace is seeded with a `Cancelled` status, but it is not a transfer state: `PUT` refuses `current_status_id` ("Status is derived from workflow state"), and `mark_order_complete` does not read it. No workflow choice remains. `delete_machine_item` R5b.
G3 (gap 3) — Intent — the owner's `delete_machine` G12 answer, applied here by Claude: a blocker counts whatever the state of the order's factory, order machine or transfer destination. `delete_machine_item` R5.
G4 (gap 4) — Intent, answered, corrected — **superseded first answer** (owner, 2026-10-31, on a wrong premise): a consumed `REPLACE` line does not block. **Current answer** (owner, 2026-10-31, given the facts): a `REPLACE` line on an open order blocks when `uses_inventory = True`, consumed or not; with `uses_inventory = False` it does not block, since it moves no stock. `delete_machine_item` R5 (b), R5b. Facts: FU-10 (a).
G5 (gap 5) — Intent, answered, corrected — **superseded first answer** (owner, 2026-10-31, on a wrong premise): a pending return on a voided purchase order does not block. **Current answer** (owner, 2026-10-31, given the facts): a pending return blocks whatever the purchase order's state, voided included, because it can still be completed. The stages (main session) stand. `delete_machine_item` R5 (d), R5b. Facts: FU-10 (b).
G6 (gap 6) — House rule not applied — `value_before` and `value_after` round half up (HR-15). `_write_ledger_entry` R4, tagged BUG-1040.
G7 (gap 7) — Fact — `purchase_order_returns.created_by` is NOT NULL with no default; a row without it raises `NotNullViolation` (verified). The return and return line columns insert (verified), so the cards' `Executor confirm` can go. Notes.
G8 (gap 8) — Fact — `action_type` values: `CONSUME`, `INSTALL`, `REPLACE`, `BORROW`. `INSTALL` is valid. Notes.
G9 (gap 9) — Fact — the patch target is the method on the DAO object `machine_item_manager.machine_item_dao`. Notes.
G10 (verifier finding, R5 (a)) — Fact — `_consume_item` has no `action_type` branch: with `uses_inventory = True` and a machine source, all four types take the line's `item_id` off the source (`consumption`, 5 → 3) and refuse with `Insufficient machine stock (0 available, 2 requested)` when the row is gone (verified: `p11.py`). `delete_machine_item` R5 (a) names them. No workflow choice. Ledger Note fixed: real-clock entries can tie.
