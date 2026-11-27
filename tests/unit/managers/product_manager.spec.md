# Spec — `app/managers/product_manager.py`

> **Status:** APPROVED (2026-11-17; owner answered OQ-50, OQ-51, OQ-52 — applied; case-designer gaps 1–6 closed, Gap log at the end)
> **Source commit:** e48a092

> **Review round 2026-11-14 (describe).** **Delegated:** every P and D item below was decided by Claude under the reviewer's delegation (2026-11-14). None of them is the owner's own answer. The house-rule lines stand. **Owner:** OQ-50 (production cost), OQ-51 (how finished goods become sellable), OQ-52 (cost of customer-returned goods) are stock / cost rules and are parked in `docs/testing/owner-questions.md`. Their rules are written to today's behaviour and marked *pending OQ-n*.

> **Review round 2026-11-17 (apply-review + fill-gaps).** **Owner, 2026-11-17:** OQ-50 intended for now (revisit after launch) — `apply_production_output` R5–R7 ✅; OQ-51 bug → BUG-2793 (`update_product` R9 rewritten, new callable `make_sellable`); OQ-52 bug → BUG-2794 (`apply_sale_return` R5, R6 rewritten). **Delegated (2026-11-17), decided by Claude, none of them the owner's own answer:** `create_product` check order (R0); avg-cost note text (`update_product` R7a); `make_sellable` details not fixed by the owner (messages, ledger labels, lock order, cost when the source has none). **Facts from the code:** gaps 1, 2, 3, 5, 6. Gap 1 needed no bug: the code tests `old_avg is not None`, not truthiness (the Branch map line was wrong and is fixed). Cards to revise: PRDM-U-21/27 (note text), PO-14/SR-13 (restore columns), SR cost cards (BUG-2794), U-40…43 (BUG-2793), new `make_sellable` cards.

> **Revision 2026-11-19 (owner in chat, BUG-2811).** `apply_production_output` R8: on a key with no row, the ledger records `avg_cost_before` NULL and `avg_cost_after` = `unit_cost`. Closes the executor's DISCREPANCY-1 on PRDM-PO-20. Still APPROVED. Cards to revise (`product_manager.cases.md`): PRDM-PO-20 — Then 4 `avg_cost_before is None` stays as written, now strict xfail BUG-2811 (the other Thens pass); any other card creating a new bucket with a `unit_cost` (check the R6 cards PO-21 … PO-23) gets the same Then and xfail when it asserts `avg_cost_before`.

> **Revision 2026-11-19 (verifier items).** `update_product` R10a (gap 7: R9's 400 before R10's 409); BUG-2770 fix note (`with_for_update(of=Product)`, HR-10 resolution, `apply_production_output` R10). Still APPROVED. Cards to revise: new card for R10a (stocked row onto a taken key → 400 R9, strict xfail BUG-2793).

> **Below this manager.** `tests/unit/dao/product.spec.md` and `tests/unit/dao/product_ledger.spec.md` (both APPROVED, verified PASS) are not restated. In particular: the bucket lookup `get_by_factory_item_available` (live rows only, `product.spec` R1–R4), the list `get_by_workspace` (BUG-1325 order, BUG-1327 deleted parents), `soft_delete` (BUG-1335 clock), the one-row-per-key unique constraint that **covers soft-deleted rows**, and the ledger's `performed_at` (BUG-1337). The DAO spec's **FU-1 (a)–(i)** is the checklist for this manager; each item is answered below. Inherited `BaseDAO.create` / `update` (`tests/unit/dao/base.spec.md`): `create` builds the row from the dict and flushes; `update` sets every key of the dict that is an attribute and flushes.
>
> **Standing decisions applied here (not asked again):** one stock row per key (BUG-983); things of a soft-deleted parent are hidden; a refused delete lists what blocks it (BUG-948 format); HR-16 — cross-workspace links are refused as "not found" (BUG-1011 is the item check of `create_product`); HR-15 — money rounds half up (BUG-1040 already names `apply_production_output` :218).
>
> **Verified:** not re-run for this spec. The facts the DAO spec verified by running (2026-11-02, `marker_test`, rolled back) through this manager are relied on: `create_product` / `apply_production_output` / `apply_sale_return` after a soft delete (23505), `delete_product` with stock, `update_product` onto a taken bucket (23505) and with a negative `qty`, negative money through `create_product`, a soft-deleted factory before `create_product`. **Read, not run:** this file in full; `app/services/product_service.py`; `app/api/v1/endpoints/products.py`; callers `ProductionBatchManager.complete_batch` (:437–462) and `post_outputs_to_finished_goods` (:700–757), `SalesManager.complete_delivery` (:330–350), `SalesService.complete_return` (:965–1000); `app/models/product.py`, `app/models/product_ledger.py`, `app/schemas/product.py`; `app/models/production_batch*.py` (no cost columns).

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| HR-10 | Stock moves read the product row without a lock and write an absolute quantity | bug (BUG-2770) | house rule |
| HR-9 | An edit that changes nothing still stamps `updated_by` | bug (BUG-2771) | house rule |
| HR-4 | Opening a deleted product by id returns it | bug (BUG-2772) | house rule |
| P1 | Opening a product of a deleted factory / removed item returns it | bug (BUG-2773) | Claude, delegated (BUG-966 precedent) |
| P2 | A product holding stock can be deleted; the units vanish with no ledger row | bug — refused with a blocker (BUG-2774) | Claude, delegated (BUG-948 precedent) |
| P3 | Negative quantity, cost, price, minimum order accepted | bug (BUG-2775) | Claude, delegated (BUG-711 precedent) |
| P4 | Cost / price with more than 2 decimals or too many digits accepted | bug (BUG-2776) | Claude, delegated (BUG-708 precedent) |
| P5 | An edit cannot clear cost, price, minimum order or note | bug (BUG-2777) | Claude, delegated (BUG-713 precedent) |
| P6 | Changing only the average cost writes no ledger row | bug (BUG-2778) | Claude, delegated (BUG-712 precedent) |
| P7 | A zero average cost records the ledger total as empty | bug (BUG-2779) | Claude, delegated (BUG-707 precedent) |
| P8 | A product can be created in a deleted factory or for a removed item | bug (BUG-2780) | Claude, delegated (BUG-715 precedent) |
| P9 | "Not enough sellable stock" names the item and factory by internal id | bug (BUG-2782) | Claude, delegated (BUG-802 precedent) |
| D1 | A taken bucket key reaches the database as a raw unique violation | bug (BUG-2781) | Claude, delegated |
| D2 | A customer-return ledger row is labelled as a return *item* and as goods going *to* the customer | bug (BUG-2783) | Claude, delegated |
| OQ-50 | Production adds finished goods with no cost | intended for now, revisit after launch | owner, 2026-11-17 |
| OQ-51 | Finished goods become sellable only by flipping the whole row | bug — "make N units sellable" move; flip refused on a row holding stock (BUG-2793) | owner, 2026-11-17 |
| OQ-52 | Customer-returned goods come back at today's average cost, or none | bug — average, else the latest sale's unit cost (BUG-2794) | owner, 2026-11-17 |

Already logged, no new ID: BUG-1011 (`create_product` item of another workspace), BUG-1336 (deleted key cannot be reused; `create_product` 409, stock paths restore), BUG-1040 (half-even `quantize` in `apply_production_output`), BUG-1325 / BUG-1327 (list order / deleted parents, in the DAO), BUG-1335 (delete clock, in the DAO).

### House-rule violations — applied automatically

- **HR-10** `update_product` R11, `apply_production_output` R10, `apply_sale_deduction` R7, `apply_sale_return` R9 — the product row is read with no lock, then an absolute `qty` (old + n, old − n, or the sent value) is written. Two movements on one bucket at once lose one; two deliveries can both pass the stock check and sell the same units. Two first movements on a key with no row both insert, and the second fails with 23505. Intended: the bucket row is read `SELECT … FOR UPDATE`; the loser sees the new quantity (a delivery then gets the normal 422); a get-or-create that loses the insert race re-reads the row (locked) and carries on, so both movements post.
**Answer:** bug — per HR-10 (house rule)
**Resolution:** BUG-2770 (pattern `hr-10-unlocked-state-transition`). **Fix note (verifier, 2026-11-19):** `Product.item` is joined-loaded (`lazy="joined"`), so a plain `.with_for_update()` puts `FOR UPDATE` on an outer join, which Postgres refuses (`FOR UPDATE cannot be applied to the nullable side of an outer join`); the locked read must use `.with_for_update(of=Product)`. Not unit-testable (two transactions); no case beyond "the read takes a lock" if the designer can observe it.
- **HR-9** `update_product` R5 — `updated_by` is written on every call, even an empty body or values equal to the stored ones (and `updated_at` moves with it). Intended: `updated_by` written only when at least one field actually changes value; otherwise the row is returned untouched.
**Answer:** bug — per HR-9 (house rule)
**Resolution:** BUG-2771 (pattern `audit-stamp-on-noop`).
- **HR-4** `get_product` R2 — a soft-deleted product is returned by id (`GET /products/{id}/`, 200). Intended: 404 `Product record with ID {prod_id} not found` by default; a new `include_deleted=True` parameter returns it. `update_product` and `delete_product` keep their own raw read and their 400s.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** BUG-2772 (pattern `get-returns-soft-deleted`). *(requires new parameter `include_deleted`, passed by the service and endpoint)*

Checked and **not** a new line here: **HR-1, HR-2, HR-3, HR-8** — no names, no grouping text, no `LIKE`; `note` is free text. **HR-5, HR-6, HR-7** — `list_products` passes through to the DAO (BUG-1325, BUG-1327 there); `GET /products/` already bounds `limit`. **HR-15** — BUG-1040 (existing) for the weighted average; the other money products (`avg_cost × qty`) are computed in Python unrounded and rounded half up by `Numeric(15,2)` on store, which agrees with HR-15 once P4 limits inputs to 2 decimals. **HR-16** — `create_product` checks the factory in the workspace; the item is BUG-1011. The `apply_*` methods take `factory_id` / `item_id` from their callers, which read them from the caller's own order or batch. **HR-11–14** — no externals.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-14)

### P1. A product of a deleted factory or removed item can still be opened — 🐞 BUG-2773
**Background:** The product list hides rows of a soft-deleted factory and of an item with `is_active = False` (BUG-1327). BUG-966 ruled the same for opening a machine of a deleted factory.
**What happens today:** `get_product` looks at the row alone: 200.
**Example:** Factory 3 is deleted. Its "Yarn (for sale)" row is gone from the product list, but `GET /products/41/` still opens it.
**Rules affected:** `get_product` R3
**Answer:** bug — per BUG-966 precedent: 404 `Product record with ID {prod_id} not found` by default; `include_deleted=True` (BUG-2772) returns it; an inactive-but-live factory hides nothing
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-14): 🐞 BUG-2773 (pattern `join-ignores-soft-deleted`).

### P2. A product holding stock can be deleted, and its units vanish — 🐞 BUG-2774
**Background:** Deleting a product soft-deletes the row; `qty` stays on it, no ledger row is written, and the row leaves every list. The owner ruled for items (BUG-948) that stock blocks a delete, and that a refused delete lists what blocks it. Factory stock solves the same with "clear stock" (an adjustment to 0).
**What happens today:** `DELETE /products/{id}/` with `qty` 4 → 200; the 4 units are in no list, and the ledger still says 4 (verified at the DAO).
**Example:** "Yarn (not for sale)" in Factory 1 holds 4 bales. A user deletes the row by mistake: the 4 bales disappear from finished goods with no trace, and the next batch output into that key fails until BUG-1336 is fixed.
**Rules affected:** `delete_product` R3
**Answer:** bug — per BUG-948 precedent: refused while `qty ≠ 0`, listing the blocker, nothing written; the user first sets the quantity to 0 (an adjustment row), then deletes
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-14): 🐞 BUG-2774 (pattern `delete-ignores-dependents`). Shape (BUG-1218 format): `app.core.exceptions.ValidationError("Product record still holds stock", errors=[{"type": "product_stock", "id": <row id>, "qty": <qty>}])`, 400 at the API. Frontend: show the blocker and offer "set quantity to 0" (frontend note BUG-2784 in bugs.md, no backend test).

### P3. Negative quantity, cost, price and minimum order are accepted — 🐞 BUG-2775
**Background:** `ProductCreate` / `ProductUpdate` have no minimums. Create writes an opening ledger row only for `qty > 0`. BUG-711 ruled this for factory stock.
**What happens today:** create with `qty` −5 stores −5 with no ledger row; update to −1 stores it with an adjustment; `avg_cost` −2.00, `selling_price` −1.00, `min_order_qty` −3 are stored (verified at the DAO for qty and money).
**Example:** A user types −5 bales by mistake. The product list shows −5 and the ledger has no record of where they came from.
**Rules affected:** `create_product` R5; `update_product` R4
**Answer:** bug — per BUG-711 precedent: `ProductCreate` / `ProductUpdate` reject `qty < 0`, `avg_cost < 0`, `selling_price < 0`, `min_order_qty < 0` with 422; nothing written
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-14): 🐞 BUG-2775 (pattern `unvalidated-numeric-range`). Fix in `app/schemas/product.py`.

### P4. Cost and price with more than 2 decimals or too many digits are accepted — 🐞 BUG-2776
**Background:** `avg_cost` and `selling_price` are `Numeric(15,2)`; the schemas accept any decimal. BUG-708 ruled this for factory stock.
**What happens today:** `avg_cost` 10.005 with `qty` 3 → the row stores 10.01 while the ledger `total_cost` is computed from 30.015 and stored 30.02 (not 30.03); a value ≥ 10^13 fails at flush.
**Example:** As above: the row says 3 × 10.01 = 30.03, the ledger says 30.02.
**Rules affected:** `create_product` R5; `update_product` R4
**Answer:** bug — per BUG-708 precedent: `avg_cost` and `selling_price` with more than 2 decimals or more than 13 integer digits → 422, nothing written
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-14): 🐞 BUG-2776 (pattern `unbounded-decimal-input`).

### P5. An edit cannot clear the cost, price, minimum order or note — 🐞 BUG-2777
**Background:** `update_product` drops every field sent as `null` (`exclude_none`). BUG-713 ruled this for factory stock.
**What happens today:** `{"note": null}` or `{"selling_price": null}` → 200, old value kept.
**Example:** A user empties the selling price of "Yarn (for sale)" and saves; the old 120.00 is still shown.
**Rules affected:** `update_product` R3
**Answer:** bug — per BUG-713 precedent: explicit `null` clears `avg_cost`, `selling_price`, `min_order_qty`, `note`; `null` for `qty` or `is_available_for_sale` → 422; omitted fields unchanged
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-14): 🐞 BUG-2777 (pattern `null-value-treated-as-absent`). Clearing `avg_cost` is a cost change and follows P6.

### P6. Changing only the average cost writes no ledger row — 🐞 BUG-2778
**Background:** The product ledger records `avg_cost_before` / `avg_cost_after` for every movement. BUG-712 ruled for factory stock that any cost change is a ledger row.
**What happens today:** A ledger row is written only when `qty` changes. Editing `avg_cost` alone (or creating with `qty` 0 and a cost) leaves no trace; the next movement's `avg_cost_before` shows the new value with no row explaining it.
**Example:** "Yarn" cost edited from 50.00 to 65.00 with 100 bales unchanged: the stock value jumps by 1,500.00 and the ledger shows nothing.
**Rules affected:** `create_product` R7; `update_product` R7
**Answer:** bug — per BUG-712 precedent: any change of `avg_cost` (including to/from `null`, P5) writes an `inventory_adjustment` row (`quantity` 0 when `qty` is unchanged, `qty_before = qty_after`, `avg_cost_before` / `avg_cost_after` set); a create with `qty` 0 and a cost writes a `manual_add` row with `quantity` 0
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-14): 🐞 BUG-2778 (pattern `unlogged-value-change`).

### P7. A zero average cost records the ledger total as empty — 🐞 BUG-2779
**Background:** `create_product` and `update_product` compute `total_cost` only when the cost is truthy; `apply_production_output` tests `is not None`. BUG-707 ruled this for factory stock.
**What happens today:** `avg_cost` 0.00, `qty` 5 → ledger `unit_cost` 0.00, `total_cost` NULL.
**Example:** Free samples booked at cost 0: the ledger total column shows "—" instead of 0.00.
**Rules affected:** `create_product` R6; `update_product` R8
**Answer:** bug — per BUG-707 precedent: `total_cost` computed whenever the cost is not `None`; 0 gives 0.00
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-14): 🐞 BUG-2779 (pattern `falsy-zero-treated-as-missing`).

### P8. A product can be created in a deleted factory or for a removed item — 🐞 BUG-2780
**Background:** The factory check finds soft-deleted factories too; the item is not checked at all (BUG-1011 is the other-workspace half). BUG-715 ruled the factory case for factory stock. A row made this way is hidden at once by BUG-1327.
**What happens today:** `factory_id` of a deleted factory → 201 (verified at the DAO). An item with `is_active = False` → 201 (read).
**Example:** Factory 9 "Old Plant" was deleted. `POST /products/` with `factory_id: 9` → 201, and the new row never appears in the list.
**Rules affected:** `create_product` R2, R2a
**Answer:** bug — per BUG-715 precedent: a soft-deleted factory → 404 `Factory with ID {factory_id} not found`; a removed item (`is_active = False`) → 404 `Item with ID {item_id} not found` (BUG-1011's message); nothing written; an inactive-but-live factory is accepted
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-14): 🐞 BUG-2780 (pattern `unvalidated-foreign-key-reference`).

### P9. "Not enough sellable stock" names the item and factory by internal id — 🐞 BUG-2782
**Background:** The message reaches the user when a delivery is completed. BUG-802 ruled that user messages name what the user sees, not internal ids.
**What happens today:** `Insufficient sellable stock for item 57 at factory 3: requested 10, available 4`.
**Example:** The sales user sees "item 57 at factory 3" and has to guess which product it is.
**Rules affected:** `apply_sale_deduction` R4
**Answer:** bug — per BUG-802 precedent: `Insufficient sellable stock for "{item name}" at {factory name}: requested {n}, available {m}`
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-14): 🐞 BUG-2782 (pattern `internal-id-in-user-message`). If the item or factory row cannot be read, fall back to `item {id}` / `factory {id}`.

### Decided under delegation (2026-11-14)

### D1. A taken bucket key reaches the database as a raw unique violation — 🐞 BUG-2781
**Background:** One bucket = workspace + item + factory + for-sale flag, unique in the database. `create_product` checks first (live rows only); `update_product` does not check at all when `is_available_for_sale` changes.
**What happens today:** `PUT` flipping `is_available_for_sale` onto a key that already has a row, or two `POST`s of one key at once, raise `IntegrityError` 23505 at flush; the API's generic handler answers its generic conflict text, which names nothing.
**Example:** Yarn in Factory 1 has both a for-sale and a not-for-sale row. Ticking "for sale" on the second gives a generic "already exists" error.
**Rules affected:** `update_product` R10; `create_product` R4a
**Answer:** bug — the manager checks the target key (live or deleted, BUG-1336's lookup) before writing and answers 409 `Product record already exists for this item/factory/availability combination`, nothing written; a create that loses the race gets the same 409, not the generic text
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-14; not a stock rule: the move itself is OQ-51): 🐞 BUG-2781 (pattern `unique-conflict-not-checked`).

### D2. A customer-return ledger row is mislabelled — 🐞 BUG-2783
**Background:** Ledger rows carry `source_type` / `source_id` (what caused the movement) and transfer source / destination. A sales delivery row says `source_type 'sales_delivery'`, `source_id` = delivery id, destination `customer`.
**What happens today:** a customer return writes `source_type 'sales_return_item'` with `source_id` = the **return's** id (not a return item's), and `transfer_destination_type 'customer'` / `transfer_destination_id` = account, although the goods come **from** the customer. Nothing in the backend reads `'sales_return_item'`.
**Example:** A return SR-2026-004 (id 12) of 3 units: the ledger row says "source: sales return item 12, destination: customer 8" — there is no return item 12, and the goods went the other way.
**Rules affected:** `apply_sale_return` R7
**Answer:** bug — `source_type 'sales_return'`, `source_id` = return id; `transfer_source_type 'customer'`, `transfer_source_id` = account id; destination fields empty
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-14; a label, not a quantity or cost): 🐞 BUG-2783 (pattern `ledger-movement-mislabelled`).

### OWNER questions — answered by the owner (2026-11-17), recorded in `docs/testing/owner-questions.md`

### OQ-50. OWNER, cost — Production adds finished goods with no cost — ✅ intended for now (revisit after launch)
**Background:** Finished goods carry an average cost (`avg_cost`) that sales use as cost of goods sold. `apply_production_output` can take a `unit_cost` and blends it into the average, but **neither caller passes one** (`complete_batch`, `post_outputs_to_finished_goods`), and production batches record no cost at all (no cost column on batches, batch items or formulas).
**What happens today:** every batch output adds quantity and keeps the bucket's average as it was (`None` for a new bucket); the ledger row has `unit_cost`, `total_cost` empty. The only way to give finished goods a cost is typing `avg_cost` on the product.
**Example:** Batch B-17 produces 200 bales of Yarn into an empty bucket. The bucket has 200 bales at cost "—"; when 50 are delivered, the sale row records no cost.
**Rules affected:** `apply_production_output` R5–R7 ✅ (revisit after launch)
**Suggested answer:** intended for now — finished goods cost is set by hand until production costing exists; revisit after launch. The unused `unit_cost` path stays as is.
**Answer:** owner, 2026-11-17: intended for now — production output has no cost, cost is set by hand; revisit after launch.
**Resolution:** no bug. Rules: `apply_production_output` R5 ✅, R6 ✅, R7 ✅ (revisit after launch). Gap 1 (an old average of 0.00 with stock) follows the code: it is weighted like any average (R5), also intended for now.

### OQ-51. OWNER, stock — Finished goods become sellable only by flipping the whole row — 🐞 BUG-2793
**Background:** Production posts into the **not-for-sale** bucket; deliveries take from the **for-sale** bucket of the same item and factory. There is no "move N units to sale" action. The product ledger has no for-sale column, so it cannot tell the two buckets apart.
**What happens today:** two ways only. (a) Tick "for sale" on the not-for-sale row: the whole quantity and cost move at once, with no ledger row; if a for-sale row already exists, it fails (D1). (b) Edit both quantities by hand: two `inventory_adjustment` rows, unlinked, at whatever cost each row has.
**Example:** 200 bales were produced (not for sale) and a for-sale row with 30 exists. To make 100 sellable the user must lower one row to 100 and raise the other to 130 — two edits, and if one fails the stock is wrong.
**Rules affected:** `update_product` R9 (tagged), R10; new `make_sellable`
**Suggested answer:** bug — add a "make sellable" action: move N units from the not-for-sale to the for-sale bucket of the same item and factory (created if missing), carrying the source's average cost, weighted into the target's average; two ledger rows (`transfer` out / in) linked to each other. Flipping `is_available_for_sale` on a row that holds stock is then refused (400, "use Make sellable"); a row at 0 may still be flipped.
**Alternatives:** (a) intended — flip and hand edits are enough. (b) keep the flip, but flipping onto an existing for-sale row merges into it (quantity added, average weighted) instead of failing.
**Answer:** owner, 2026-11-17: suggested answer (add a "make N units sellable" move with linked ledger rows; refuse flipping a row that holds stock). → BUG-2793
**Resolution:** 🐞 BUG-2793 (pattern `missing-stock-move`). New callable `make_sellable` M1–M9 *(requires new method)*; `update_product` R9 rewritten (flip refused while the row holds stock); R10 stays for a flip of an empty row onto a taken key. Details the owner did not fix (messages, ledger labels, lock order, a source with no cost) decided by Claude under the reviewer's delegation (2026-11-17).

### OQ-52. OWNER, cost — Customer-returned goods come back at today's average cost, or none — 🐞 BUG-2794
**Background:** When a customer return completes, the units go back into the for-sale bucket. A delivery took them out at the bucket's average at that time (recorded on the `sale` ledger row).
**What happens today:** the returned units are valued at the bucket's **current** average, which is left unchanged; if the bucket has no average (new or never costed) the return row has no cost. If the bucket was missing, it is created with `qty` 0 and no average first.
**Example:** 10 bales were sold at cost 50.00. Since then the bucket was emptied and its row deleted and recreated with no cost. The customer returns 4 bales: the bucket holds 4 bales at cost "—", and the next sale of them records no cost although they left at 50.00.
**Rules affected:** `apply_sale_return` R5 ✅, R6 ✅, R6a (tagged)
**Suggested answer:** intended while the bucket has an average (the standard weighted-average shortcut). When it has none, use the `unit_cost` of the latest `sale` ledger row of that item and factory and set the bucket's average to it.
**Alternatives:** (a) intended in every case. (b) always value returned units at the cost they left with (the order's delivery `sale` row) and weight it into the average.
**Answer:** owner, 2026-11-17: suggested answer (returned goods come back at today's average cost; if none, the latest sale's unit cost). → BUG-2794
**Resolution:** 🐞 BUG-2794 (pattern `missing-cost-fallback`). Rules: `apply_sale_return` R5 (unchanged part ✅), R6 (tagged), R6a (tagged). "Latest sale" = the `sale` ledger row of this workspace, factory and item with a `unit_cost`, by `performed_at` then `id` descending (decided by Claude under the reviewer's delegation, 2026-11-17).

## Follow-ups for other reviews
> Nothing below is a rule of this manager and no bug is logged for it here.

| # | Where | What | Came from |
|---|---|---|---|
| FU-1 | **Sales delivery entry** (`app/managers/sales_manager.py`, delivery lines) | A fractional delivery quantity on a catalog line is refused only when the delivery is completed (`apply_sale_deduction` R3), after the delivery is planned; BUG-824 precedent says refuse at entry. | `_quantity_to_int` |
| FU-2 | **Sales return entry** (`sales_order_return_manager`) | Same for a fractional return quantity on a catalog line: refused only at completion (`apply_sale_return` R3). | `_quantity_to_int` |
| FU-3 | **Production batch manager** | "Caller must enforce idempotent batch posting": `complete_batch` and `post_outputs_to_finished_goods` both post outputs of one batch; whether the second is refused (`exists_for_production_batch`) is theirs to specify. | docstring |
| FU-4 | **Permissions** | Anyone in the workspace can hand-edit finished goods quantity and cost through `PUT /products/{id}/`. Note for `docs/future/permissions.md`. | `update_product` |

## Overview
`ProductManager` keeps finished goods stock: one `products` row per item, factory and for-sale flag (the "bucket"), with quantity (whole units), average cost, selling price and minimum order. It is the manual CRUD behind `/products/` (via `ProductService`, which commits) and the stock movements that other flows call inside their own transaction: production output into the not-for-sale bucket (`ProductionBatchManager`), sales deduction from and customer returns into the for-sale bucket (`SalesManager.complete_delivery`, `SalesService.complete_return`). Every quantity change writes one `product_ledger` row with before/after quantity and cost. It never commits.

**Callables:** 9 specified · 2 not specified
**Externals to mock:** none (`product_ledger.performed_at` and `products.created_at` / `updated_at` are database defaults; `soft_delete`'s clock is the DAO's, BUG-1335).
**Integration-only behavior:** the API translation of errors (`ValueError` → 400 in the batch / sales endpoints; `IntegrityError` → the generic handler). Two-transaction races (BUG-2770, D1's race half).

**Model facts:** `products` — `tests/unit/dao/product.spec.md` Overview. `product_ledger` (`app.models.product_ledger.ProductLedger`): `workspace_id`, `factory_id`, `item_id` NOT NULL; `transaction_type` String(50) NOT NULL; `quantity`, `qty_before`, `qty_after` **Integer** NOT NULL; `unit_cost`, `total_cost`, `avg_cost_before`, `avg_cost_after` Numeric(15,2) nullable; `source_type` String(50), `source_id` Integer, `transfer_source_type/id`, `transfer_destination_type/id` nullable; `notes` Text; `performed_by` FK profiles nullable; `performed_at` NOT NULL, database `now()`. No for-sale column.

**Schemas** (`app/schemas/product.py`): `ProductCreate` — `item_id`, `factory_id` (int, required), `qty: int = 0`, `avg_cost`, `selling_price: Decimal | None`, `min_order_qty: int | None`, `is_available_for_sale: bool = False`, `note: str | None`. `ProductUpdate` — the same minus `item_id` / `factory_id`, all optional, default `None`. No validators (P3–P5 add them).

**Notes for the test designer:**
- `from app.managers.product_manager import product_manager, _quantity_to_int`. `apply_*` parameters after `session` are keyword-only.
- Build `Factory`, `Item`, `Product` directly; never two rows of one key (the unique constraint covers deleted rows). For a "missing bucket", use a key with no row.
- Read ledger rows back by `(workspace_id, factory_id, item_id, source_type, source_id)`; `performed_at` ties within a test, so order by `id`.
- `qty` is an Integer column: compare as `int`. `avg_cost` comes back as `Decimal` with 2 places after a refresh; before a refresh it is the Python value written.
- Calls that raise: wrap in `with session.begin_nested():`.

## Not specified
- `ProductManager.__init__` — wires `product_dao`, `product_ledger_dao`; no logic.
- `product_manager` — module singleton.

---

## `_quantity_to_int(quantity, *, label)`
**Shape:** validator
**Persistence:** pure
**Visibility:** internal (used by: `apply_sale_deduction`, `apply_sale_return`)

**Purpose:** Turn a line quantity into whole units, refusing fractions.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `quantity` | `Decimal` or `int` | Converted through `str`, so `Decimal("5.00")` and `5` are both 5. |
| `label` | str | Start of the error message. |

**Returns:** `int`.

**Rules:**
- **R1.** A whole value is returned as `int`: `Decimal("5.00")` → 5, `7` → 7, `Decimal("0")` → 0, `Decimal("-3")` → −3 (sign kept; callers refuse ≤ 0 first).
- **R2.** A fractional value → `HTTPException` 400 `{label} has a fractional quantity; stock requires whole units` (e.g. `Delivery line has a fractional quantity; stock requires whole units` for 2.5, and for 0.01).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| fractional | `HTTPException` 400 | `{label} has a fractional quantity; stock requires whole units` |

**Side effects:** none.

---

## `ProductManager.create_product(session, data, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `ProductService.create_product` ← `POST /products/`)

**Purpose:** Create a finished-goods bucket by hand, with an opening ledger row for its quantity.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `data` | `ProductCreate` | see Overview; nothing enforced beyond types today (P3, P4). |
| `workspace_id`, `user_id` | int | caller's workspace; `created_by` / `performed_by`. |

**Returns:** the new `Product`, flushed, not committed.

**Rules:**
- **R0.** (gap 4, decided by Claude under the reviewer's delegation, 2026-11-17) When several checks fail, the first in this order wins: schema (R5, 422, before the manager runs) → factory (R1, R2) → item (R2a) → key taken (R3, R4). Example: an unknown factory **and** a removed item → the factory 404. Today the factory check runs before the duplicate check (code order); the item check does not exist yet (BUG-1011, BUG-2780) and slots in between.
- **R1.** A `factory_id` with no factory in this workspace (unknown, or another workspace's) → 404 `Factory with ID {factory_id} not found`, nothing written.
- **R2.** [BUG-2780] A soft-deleted factory → the same 404, nothing written; an inactive-but-live factory is accepted. *(Today: accepted, 201.)*
- **R2a.** [BUG-2780] An item with `is_active = False` → 404 `Item with ID {item_id} not found`, nothing written. *(Today: accepted.)* An item of another workspace or unknown → the same 404 (BUG-1011, existing). *(Today: accepted; unknown fails the FK at flush.)*
- **R3.** A live row already holding this key (workspace, factory, item, `is_available_for_sale`) → 409 `Product record already exists for this item/factory/availability combination`, nothing written. Only the exact flag counts: a for-sale row does not block a not-for-sale create.
- **R4.** A soft-deleted row of this key → the same 409, nothing written (BUG-1336, owner 2026-11-02). *(Today: the check misses it and the insert fails with 23505.)*
- **R4a.** [BUG-2781] A create that loses a race to another create of the same key → the same 409. *(Today: `IntegrityError` 23505.)* Not unit-testable; no case.
- **R5.** [BUG-2775, BUG-2776] `qty < 0`, `avg_cost < 0`, `selling_price < 0`, `min_order_qty < 0`, or `avg_cost` / `selling_price` with more than 2 decimals or more than 13 integer digits → 422 (Pydantic `ValidationError` from `ProductCreate`), nothing written. *(Today: stored as given; money rounded half up by the column; ≥ 10^13 fails at flush.)* 0 is accepted everywhere.
- **R6.** The row is created with every `ProductCreate` field as given (gap 2 of the schema, from the code: only `item_id` and `factory_id` are required; `qty` int default 0, `avg_cost` / `selling_price` Decimal or `None` default `None`, `min_order_qty` int or `None`, `is_available_for_sale` bool default `False`, `note` str or `None`), `workspace_id`, `created_by = user_id`, `is_active = True`, `is_deleted = False`, `updated_by` NULL.
- **R7.** When `qty > 0`, exactly one ledger row: `transaction_type 'manual_add'`, `quantity = qty`, `unit_cost = avg_cost`, `qty_before 0`, `qty_after = qty`, `avg_cost_before` NULL, `avg_cost_after = avg_cost`, `source_type 'manual'`, `source_id` NULL, no transfer fields, `notes 'Initial product record created'`, `performed_by = user_id`, the row's workspace, factory, item. `total_cost = avg_cost × qty`; [BUG-2779] also when `avg_cost` is 0 (→ 0.00); NULL only when `avg_cost` is `None`. *(Today: NULL when `avg_cost` is 0.)*
- **R7a.** `qty` 0 and `avg_cost` `None` → no ledger row. [BUG-2778] `qty` 0 with an `avg_cost` → one `manual_add` row with `quantity` 0, `qty_before = qty_after = 0`, `avg_cost_after = avg_cost`, `total_cost` 0.00. *(Today: no ledger row.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| factory missing / other workspace / [BUG-2780] deleted | `HTTPException` 404 | `Factory with ID {factory_id} not found` |
| [BUG-1011, BUG-2780] item missing / other workspace / removed | `HTTPException` 404 | `Item with ID {item_id} not found` |
| key taken (live; [BUG-1336] deleted; [BUG-2781] race) | `HTTPException` 409 | `Product record already exists for this item/factory/availability combination` |
| [BUG-2775, BUG-2776] out-of-range input | `pydantic.ValidationError` (422) | Pydantic's |

**Side effects:** one `products` row; zero or one `product_ledger` row; flushed.

---

## `ProductManager.update_product(session, prod_id, data, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `ProductService.update_product` ← `PUT /products/{id}/`)

**Purpose:** Edit a bucket by hand; a quantity change is recorded as an adjustment.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `prod_id` | int | the row. |
| `data` | `ProductUpdate` | fields set and not `None` are applied (R3). |

**Returns:** the updated `Product`, flushed.

**Rules:**
- **R1.** No row with this id in this workspace (unknown, or another workspace's) → 404 `Product record with ID {prod_id} not found`.
- **R2.** A soft-deleted row → 400 `Cannot update a deleted product record`, nothing written. ✅ (same split as `delete_product`; `get_product` is HR-4)
- **R3.** [BUG-2777] A field sent as `null` clears `avg_cost`, `selling_price`, `min_order_qty`, `note`; `null` for `qty` or `is_available_for_sale` → 422; omitted fields are unchanged. *(Today: every `null` is dropped like an omitted field; nothing can be cleared.)*
- **R4.** [BUG-2775, BUG-2776] Out-of-range values as `create_product` R5 → 422 from `ProductUpdate`, nothing written. *(Today: stored, e.g. `qty` −1 with an adjustment row.)*
- **R5.** [BUG-2771] When no sent field differs from the stored value (empty body, or the same values), the row is returned unchanged: `updated_by` not written, no ledger row. *(Today: `updated_by = user_id` is always written.)* When something changes, `updated_by = user_id`.
- **R6.** Sent fields are stored as sent (`qty`, `avg_cost`, `selling_price`, `min_order_qty`, `is_available_for_sale`, `note`); `factory_id` / `item_id` cannot be changed (not in the schema).
- **R7.** When `qty` is sent and differs, exactly one ledger row: `transaction_type 'inventory_adjustment'`, `quantity = |new − old|`, `qty_before = old`, `qty_after = new`, `avg_cost_before` = old `avg_cost`, `avg_cost_after` = `unit_cost` = the `avg_cost` sent in the same call or else the old one, `source_type 'adjustment'`, `source_id` NULL, `notes 'Quantity adjusted from {old} to {new}'`, `performed_by = user_id`, the row's workspace, factory, item. [BUG-2778] When `qty` is unchanged or not sent but `avg_cost` changes (or is cleared, R3), one row of the same shape with `quantity` 0, `qty_before = qty_after` = the row's `qty`, and notes `Average cost adjusted from {old} to {new}` (text decided under delegation; formatting R7a). *(Today: no row unless `qty` changes.)*
- **R7a.** (gap 2) Note formatting is a plain Python f-string, as the existing quantity note (`f'Quantity adjusted from {old_qty} to {new_qty}'`, code fact): `qty` is an `Integer` column, so `Quantity adjusted from 5 to 8`. For the [BUG-2778] cost note (decided by Claude under the reviewer's delegation, 2026-11-17, same style): `{old}` is the stored value (`Numeric(15,2)`, so `10.00`), `{new}` is the value as sent in the request (`12` → `12`, `12.00` → `12.00`; schema BUG-2776 limits it to 2 decimals), and `None` prints `None`: `Average cost adjusted from 10.00 to None`, `Average cost adjusted from None to 12.00`.
- **R8.** That row's `total_cost = unit_cost × quantity` whenever `unit_cost` is not `None` (0 → 0.00) [BUG-2779]; NULL when `None`. *(Today: NULL also when the cost is 0.)*
- **R9.** [BUG-2793] Changing `is_available_for_sale` on a row whose stored `qty` is not 0 → 400 `Product record holds stock — use Make sellable to move units`, nothing written (either direction; the stored `qty` before this call decides, a `qty` sent in the same call does not help). A row whose stored `qty` is 0 is flipped as today: it moves to the other key with its `avg_cost`, no ledger row for the flip, and a `qty` sent in the same call is adjusted per R7. Units move between the two buckets only through `make_sellable`. *(Today: a row holding stock is flipped with its whole `qty` and `avg_cost`, no ledger row.)*
- **R10.** [BUG-2781] Changing `is_available_for_sale` onto a key that already has a row (live or deleted) → 409 `Product record already exists for this item/factory/availability combination`, nothing written.
- **R10a.** Check order (gap 7, decided by Claude under the reviewer's delegation, 2026-11-19): R9 before R10. A row that holds stock flipped onto a taken key gets the 400 of R9, not the 409: R9 reads only the row itself, and after BUG-2793 a stocked row can never be flipped, so the target key does not matter for it. R10 is reached only by a row at `qty 0`. *(Today: `IntegrityError` 23505 at flush.)*
- **R11.** [BUG-2770] The row is read `FOR UPDATE`, so a concurrent movement on it waits and the adjustment's `qty_before` is the quantity actually replaced. *(Today: no lock.)* Not unit-testable; no case.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| missing / other workspace | `HTTPException` 404 | `Product record with ID {prod_id} not found` |
| soft-deleted | `HTTPException` 400 | `Cannot update a deleted product record` |
| [BUG-2793] flag change on a row holding stock | `HTTPException` 400 | `Product record holds stock — use Make sellable to move units` |
| [BUG-2781] flag onto a taken key | `HTTPException` 409 | `Product record already exists for this item/factory/availability combination` |
| [BUG-2775, BUG-2776, BUG-2777] invalid input | `pydantic.ValidationError` (422) | Pydantic's |

**Side effects:** fields above, `updated_by`, `updated_at` (database `now()` on update); zero or one ledger row; flushed.

---

## `ProductManager.get_product(session, prod_id, workspace_id)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `ProductService.get_product` ← `GET /products/{id}/`)

**Rules:**
- **R1.** The workspace's row with this id is returned; unknown id or another workspace's row → 404 `Product record with ID {prod_id} not found`.
- **R2.** [BUG-2772] A soft-deleted row → the same 404 by default; with a new `include_deleted=True` it is returned. *(Today: returned.)*
- **R3.** [BUG-2773] A row of a soft-deleted factory or of an item with `is_active = False` → the same 404 by default; `include_deleted=True` returns it; an inactive-but-live factory hides nothing. *(Today: returned.)*

**Errors:** 404 as above. **Side effects:** none.

---

## `ProductManager.list_products(session, workspace_id, factory_id=None, is_available_for_sale=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProductService.list_products` ← `GET /products/`)

**Rules:**
- **R1.** Returns exactly `ProductDAO.get_by_workspace` with the same arguments — filters, soft-delete hiding, paging and order per `product.spec.md` `get_by_workspace` (R1–R6, BUG-1325, BUG-1327). Defaults `skip 0`, `limit 100`.

**Errors:** none. **Side effects:** none.

---

## `ProductManager.delete_product(session, prod_id, workspace_id, user_id)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `ProductService.delete_product` ← `DELETE /products/{id}/`)

**Rules:**
- **R1.** Unknown id or another workspace's row → 404 `Product record with ID {prod_id} not found`.
- **R2.** Already soft-deleted → 400 `Product record is already deleted`, nothing written.
- **R3.** [BUG-2774] A row with `qty ≠ 0` (positive or negative) → `app.core.exceptions.ValidationError("Product record still holds stock", errors=[{"type": "product_stock", "id": prod_id, "qty": qty}])` (400), nothing written. *(Today: deleted with its stock, no ledger row.)*
- **R4.** Otherwise the row is soft-deleted per `product.spec.md` `soft_delete` (`is_deleted`, `is_active False`, `deleted_at` [BUG-1335], `deleted_by = user_id`) and returned. `updated_by` is not written; `qty` and costs stay. No lock (plain soft delete, HR-10 exempt).

**Errors:** 404, 400 (R2), [BUG-2774] 400 with blockers.
**Side effects:** the row's soft-delete fields; flushed.

---

## `ProductManager.apply_production_output(session, *, workspace_id, user_id, factory_id, item_id, quantity, batch_id, unit_cost=None, notes=None)`
**Shape:** state-transition (stock in)
**Persistence:** writes
**Visibility:** internal (used by: `ProductionBatchManager.complete_batch` with `notes` = `SYSTEM - PRODUCTION BATCH COMPLETE | {batch_number}`; `post_outputs_to_finished_goods` with `unit_cost=None`, no notes). Neither passes `unit_cost`.

**Purpose:** Add a batch's output to the not-for-sale bucket of the factory and item.

**Inputs:** `quantity` — `int` from both callers (batch quantities are Integer columns); not converted or checked for fractions here. `unit_cost` — `Decimal | None`. `batch_id` — stored as the ledger `source_id`, not checked.

**Returns:** the bucket row, flushed.

**Rules:**
- **R1.** `quantity <= 0` → `ValueError("Production output quantity must be positive")`, nothing written.
- **R2.** The not-for-sale live row of the key is used. When none exists, one is created: `qty 0`, `avg_cost = unit_cost`, `is_available_for_sale False`, `created_by = user_id`, then R3–R9 apply to it (`qty_before 0`).
- **R2a.** A soft-deleted row of the key is restored and used with its kept `qty` (BUG-1336, owner 2026-11-02); no ledger row for the restore. The restore writes what `ProductDAO.restore` writes (gap 3, code fact, `product.spec` `restore` R1–R4): `is_active = True`, `is_deleted = False`, `deleted_at = NULL`, `deleted_by = NULL`; `updated_by = user_id` comes from R3, `updated_at` from the column's `onupdate`. Same id, kept `avg_cost`. *(Today: a new row is inserted and fails with 23505.)* The for-sale row of the key is never touched.
- **R3.** `qty` becomes old `qty` + `quantity`; `updated_by = user_id`.
- **R4.** `unit_cost` `None` → `avg_cost` unchanged (`None` stays `None`).
- **R5.** ✅ (OQ-50, intended for now — revisit after launch) `unit_cost` given, old `qty > 0` and old `avg_cost` not `None` (an average of `0.00` counts: 10 at 0.00 + 10 at 6.00 → 3.00; gap 1, code fact) → new average = (old qty × old avg + quantity × unit_cost) / new qty, rounded to 2 places — [BUG-1040] half up (0.125 → 0.13). *(Today: half to even, 0.125 → 0.12.)* Example: 10 at 5.00 + 10 at 6.00 → 5.50.
- **R6.** ✅ (OQ-50, revisit after launch) `unit_cost` given and old `qty ≤ 0` (zero or negative) or old `avg_cost` `None` → new average = `unit_cost` (the old units, if any, are revalued at it).
- **R7.** ✅ (OQ-50, revisit after launch) No caller passes `unit_cost`, so in production use only R4 runs.
- **R8.** One ledger row: `transaction_type 'production'`, `quantity`, `unit_cost`, `total_cost = unit_cost × quantity` when `unit_cost` is not `None` (0 → 0) else NULL, `qty_before`/`qty_after`, `avg_cost_before`/`avg_cost_after` (R4–R6; see R8a for a new bucket), `source_type 'production_batch'`, `source_id = batch_id`, no transfer fields, `notes` = `notes` if truthy else `SYSTEM - PRODUCTION BATCH COMPLETE | batch id {batch_id}` (`""` takes the default), `performed_by = user_id`.
- **R8a.** [BUG-2811] (owner in chat, 2026-11-19) When the bucket was created by this call (R2, no row for the key), the ledger row has `avg_cost_before = NULL` (no previous cost) and `avg_cost_after` = the bucket's average after the call (`unit_cost` when given, else `NULL`); `qty_before` 0. A restored soft-deleted row (R2a) is not new: its kept average is `avg_cost_before`. *(Today: R2 seeds the new row with `avg_cost = unit_cost` before the "before" value is read, so `avg_cost_before` = `unit_cost`, e.g. 6.00.)* Not reachable in production today (no caller passes `unit_cost`, R7); with `unit_cost=None` today's NULL / NULL already matches.
- **R9.** Calling it twice for one batch posts twice; idempotency is the caller's (FU-3).
- **R10.** [BUG-2770] The bucket row is read `FOR UPDATE` (`with_for_update(of=Product)`, see the HR-10 fix note); a create that loses the insert race re-reads and adds to the winner's row. *(Today: no lock; a lost update or 23505.)* Not unit-testable; no case.

**Errors:** `ValueError` (R1).
**Side effects:** bucket row created/restored/updated; one ledger row; flushed.

---

## `ProductManager.apply_sale_deduction(session, *, workspace_id, user_id, factory_id, item_id, quantity, delivery_id, account_id=None, notes=None)`
**Shape:** state-transition (stock out)
**Persistence:** writes
**Visibility:** internal (used by: `SalesManager.complete_delivery`, for delivery lines with a catalog item, with the order's factory and account, `notes` `Delivery {delivery_number} for SO-{number}`)

**Purpose:** Take delivered units out of the for-sale bucket, at its average cost.

**Rules:**
- **R1.** `quantity <= 0` → `ValueError("Sale deduction quantity must be positive")`, nothing written (checked before R2).
- **R2.** A whole quantity is used as `int` (`Decimal("3.00")` → 3).
- **R3.** A fractional quantity → 400 per `_quantity_to_int` R2 with label `Delivery line`, nothing written.
- **R4.** No live for-sale row of the key, or its `qty` < quantity → 422 [BUG-2782] `Insufficient sellable stock for "{item name}" at {factory name}: requested {quantity}, available {qty or 0}`, nothing written. *(Today: `…for item {item_id} at factory {factory_id}: …`.)* A soft-deleted row counts as missing (available 0), and is not restored. The not-for-sale row never counts. `qty` equal to the quantity is allowed (→ 0).
- **R5.** `qty` becomes old − quantity; `avg_cost` unchanged; `updated_by = user_id`.
- **R6.** One ledger row: `transaction_type 'sale'`, `quantity`, `unit_cost = avg_cost_before = avg_cost_after` = the bucket's average, `total_cost = avg × quantity` when the average is not `None` (0 → 0.00) else NULL, `qty_before`/`qty_after`, `source_type 'sales_delivery'`, `source_id = delivery_id`, `transfer_destination_type 'customer'`, `transfer_destination_id = account_id` (may be NULL), `notes` = `notes` if truthy else `SYSTEM - SALES DELIVERY | delivery id {delivery_id}`, `performed_by = user_id`.
- **R7.** [BUG-2770] The row is read `FOR UPDATE`; of two deliveries that together exceed the stock, the second gets the R4 422. *(Today: both can pass and the quantity goes negative or one deduction is lost.)* Not unit-testable; no case.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| quantity ≤ 0 | `ValueError` | `Sale deduction quantity must be positive` |
| fractional | `HTTPException` 400 | `Delivery line has a fractional quantity; stock requires whole units` |
| no / short bucket | `HTTPException` 422 | R4 |

**Side effects:** bucket `qty`, `updated_by`; one ledger row; flushed.

---

## `ProductManager.apply_sale_return(session, *, workspace_id, user_id, factory_id, item_id, quantity, return_id, account_id=None, notes=None)`
**Shape:** state-transition (stock in)
**Persistence:** writes
**Visibility:** internal (used by: `SalesService.complete_return`, for return lines with a catalog item, with the order's factory and account, `notes` `Return {return_number} for SO-{number}`)

**Purpose:** Put customer-returned units back into the for-sale bucket.

**Rules:**
- **R1.** `quantity <= 0` → `ValueError("Sale return quantity must be positive")`, nothing written. Checked before R3 (gap 6, code fact: line 344 before 346), so `Decimal("-0.5")` gives this `ValueError`, not the fraction 400.
- **R2.** A whole quantity is used as `int`.
- **R3.** A fractional quantity → 400 per `_quantity_to_int` R2 with label `Return line`, nothing written.
- **R4.** The live for-sale row of the key is used; when none exists, one is created with `qty 0`, `avg_cost None`, `is_available_for_sale True`, `created_by = user_id`. A soft-deleted row is restored and used with its kept `qty` (BUG-1336), with the same columns as `apply_production_output` R2a (gap 3). *(Today: insert, 23505.)*
- **R5.** ✅ (OQ-52) `qty` becomes old + quantity; `updated_by = user_id`. When the bucket has an average (not `None`; `0.00` counts), it is unchanged and the returned units carry it.
- **R6.** ✅ (OQ-52) Bucket with an average: the ledger row's `unit_cost = avg_cost_before = avg_cost_after` = that average; `total_cost = avg × quantity` (0 → 0.00).
- **R6a.** [BUG-2794] Bucket with no average (`None`; a new or restored-uncosted row included): the cost is the `unit_cost` of the latest `sale` ledger row of this workspace, factory and item that has a `unit_cost` (latest = `performed_at` descending, then `id` descending; decided under delegation). The bucket's `avg_cost` is set to it; the ledger row has `avg_cost_before` NULL, `avg_cost_after = unit_cost` = that cost, `total_cost` = cost × quantity. No such sale row (never sold with a cost, or only another workspace's / factory's / item's) → as today: `avg_cost` stays `None`, `unit_cost`, `total_cost`, `avg_cost_after` NULL. Example: last sale at 50.00, bucket recreated with no cost, 4 returned → bucket 4 at 50.00, ledger `total_cost` 200.00. *(Today: no fallback — the return carries no cost and the average stays `None`.)*
- **R7.** [BUG-2783] The ledger row has `transaction_type 'return'`, `quantity`, `qty_before`/`qty_after`, `source_type 'sales_return'`, `source_id = return_id`, `transfer_source_type 'customer'`, `transfer_source_id = account_id`, destination fields NULL, `notes` = `notes` if truthy else `SYSTEM - SALES RETURN | return id {return_id}`, `performed_by = user_id`. *(Today: `source_type 'sales_return_item'`, `transfer_destination_type 'customer'`, `transfer_destination_id = account_id`, source fields NULL.)*
- **R8.** Two lines of one item on one return give two ledger rows with the same source.
- **R9.** [BUG-2770] The row is read `FOR UPDATE`; a lost insert race re-reads. *(Today: no lock.)* Not unit-testable; no case.

**Errors:** `ValueError` (R1); 400 (R3).
**Side effects:** bucket row created/restored/updated; one ledger row; flushed.

---

## `ProductManager.make_sellable(session, prod_id, quantity, workspace_id, user_id)` *(requires new method — BUG-2793)*
**Shape:** state-transition (stock move)
**Persistence:** writes
**Visibility:** public (new; for a new endpoint such as `POST /products/{id}/make-sellable/`)

**Purpose:** Move N units of finished goods from the not-for-sale bucket to the for-sale bucket of the same item and factory (owner, OQ-51).

**Inputs:** `prod_id` — the not-for-sale row; `quantity` — whole units; `workspace_id`, `user_id`.

**Returns:** the for-sale (target) row, flushed, not committed.

**Rules** (all *requires new method*; owner fixed the move, the two linked ledger rows, cost carried and weighted, target created if missing; the rest decided by Claude under the reviewer's delegation, 2026-11-17):
- **M1.** No row with `prod_id` in this workspace → 404 `Product record with ID {prod_id} not found`; a soft-deleted row → 400 `Cannot update a deleted product record`; a for-sale row → 400 `Only a not-for-sale product record can be made sellable`. Nothing written.
- **M2.** `quantity` not a whole number ≥ 1 → 400 `Quantity must be a positive whole number`; more than the source's `qty` → 422 `Insufficient stock to make sellable: requested {quantity}, available {qty}`. Exactly the source's `qty` is allowed (source → 0). Nothing written on refusal. Order: M1, then M2.
- **M3.** Target = the for-sale row of the same workspace, factory and item. Missing → created (`qty 0`, `avg_cost None`, `is_available_for_sale True`, `created_by = user_id`); soft-deleted → restored as `apply_production_output` R2a (BUG-1336).
- **M4.** Source `qty` −= quantity, `avg_cost` unchanged; target `qty` += quantity; `updated_by = user_id` on both.
- **M5.** Target average: source average `None` → target average unchanged (the units carry no cost, as production R4). Source average set, and target old `qty > 0` with an average not `None` → (old target qty × target avg + quantity × source avg) / new target qty, rounded to 2 places half up (HR-15). Otherwise (target empty, or no average) → the source average.
- **M6.** Two ledger rows, `transaction_type 'transfer'`, both `source_type 'make_sellable'`, `performed_by = user_id`, same workspace, factory, item, `quantity`: **out** row — source's `qty_before`/`qty_after`, `unit_cost` = source average, `avg_cost_before = avg_cost_after` = source average, `transfer_destination_type 'product'`, `transfer_destination_id` = target row id, `source_id` = target row id; **in** row — target's `qty_before`/`qty_after`, `unit_cost` = source average, `avg_cost_before`/`avg_cost_after` = target's before / after (M5), `transfer_source_type 'product'`, `transfer_source_id` = source row id, `source_id` = source row id. `total_cost = unit_cost × quantity` when `unit_cost` is not `None` (0 → 0.00), else NULL. Notes on both: `Made sellable: {quantity} unit(s)`.
- **M7.** (HR-10) Both rows are read `FOR UPDATE`, lower id first (no deadlock between two moves); a concurrent movement waits and M2 is checked on the locked quantity. Not unit-testable; no case.
- **M8.** The sum of the two buckets' `qty` is unchanged by the move.
- **M9.** Flushed, not committed; on any refusal nothing is written.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| missing / other workspace | `HTTPException` 404 | `Product record with ID {prod_id} not found` |
| soft-deleted | `HTTPException` 400 | `Cannot update a deleted product record` |
| source is for sale | `HTTPException` 400 | `Only a not-for-sale product record can be made sellable` |
| bad quantity | `HTTPException` 400 | `Quantity must be a positive whole number` |
| more than held | `HTTPException` 422 | `Insufficient stock to make sellable: requested {quantity}, available {qty}` |

**Side effects:** two `products` rows updated (target maybe created / restored); two `product_ledger` rows; flushed.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 20 | fractional vs whole | `_quantity_to_int` R1, R2 |
| 44 | factory found | `create_product` R1, R2 |
| — (missing) | item checked | `create_product` R2a |
| 55 | live duplicate | `create_product` R3, R4, R4a |
| 68 | `qty > 0` | `create_product` R7, R7a |
| 76 | `avg_cost` truthy | `create_product` R7 |
| 97 | row found | `update_product` R1 |
| 102 | `is_deleted` | `update_product` R2 |
| 111 | `exclude_unset` / `exclude_none` | `update_product` R3, R6 |
| 112 | stamp always | `update_product` R5 |
| 114 | flag change onto taken key | `update_product` R9, R10 |
| 118 | qty sent and differs | `update_product` R7 |
| 119 | `avg_cost` sent vs old | `update_product` R7 |
| 127 | `new_avg` truthy | `update_product` R8 |
| 143 | row found | `get_product` R1–R3 |
| 154 | pass-through | `list_products` R1 |
| 164 | row found | `delete_product` R1 |
| 166 | already deleted | `delete_product` R2 |
| — (missing) | stock check | `delete_product` R3 |
| 188 | `quantity <= 0` | `apply_production_output` R1 |
| 198 | bucket missing | `apply_production_output` R2, R2a |
| 215 | `unit_cost` given | `apply_production_output` R4–R7 |
| 216 | `old_qty > 0 and old_avg is not None` (not truthiness: 0.00 is weighted) | `apply_production_output` R5, R6 |
| 218 | `quantize` rounding | `apply_production_output` R5 (BUG-1040) |
| 231 | `unit_cost is not None` | `apply_production_output` R8 |
| 238 | `notes or …` | `apply_production_output` R8 |
| 272 | `quantity <= 0` | `apply_sale_deduction` R1 |
| 274 | fractional | `apply_sale_deduction` R2, R3 |
| 283 | missing or short | `apply_sale_deduction` R4 |
| 284 | `record` for available | `apply_sale_deduction` R4 |
| 304 | `old_avg is not None` | `apply_sale_deduction` R6 |
| 313 | `notes or …` | `apply_sale_deduction` R6 |
| 344 | `quantity <= 0` | `apply_sale_return` R1 |
| 346 | fractional | `apply_sale_return` R2, R3 |
| 355 | bucket missing | `apply_sale_return` R4 |
| 378 | `old_avg is not None` | `apply_sale_return` R6; — (missing) sale-cost fallback R6a |
| 387 | `notes or …` | `apply_sale_return` R7 |
| 191, 276, 348, 94 | unlocked read | BUG-2770 rules (`update_product` R11, `apply_production_output` R10, `apply_sale_deduction` R7, `apply_sale_return` R9) |
| — (new method) | `make_sellable` checks and move | `make_sellable` M1–M9 |
| — (missing) | flag change on a row holding stock | `update_product` R9 |

## Gap log
- G1 (product_manager.cases.md gap 1) — fact — the code tests `old_qty > 0 and old_avg is not None` (line 216), so an old average of 0.00 with stock is weighted (R5: 10 @ 0.00 + 10 @ 6.00 → 3.00). Rule R5 was right; the Branch map line was wrong and is fixed. No bug (BUG-2795 not used); intended for now with OQ-50 (revisit after launch).
- G2 (gap 2) — fact + delegated — quantity note is a plain f-string of ints (code); the BUG-2778 cost note uses the same style: stored old value (`10.00`), new value as sent, `None` prints `None`. `update_product` R7a.
- G3 (gap 3) — fact — the BUG-1336 restore writes `is_active True`, `is_deleted False`, `deleted_at NULL`, `deleted_by NULL` (`ProductDAO.restore`); `updated_by` from the movement, `updated_at` by `onupdate`. `apply_production_output` R2a, `apply_sale_return` R4, `make_sellable` M3.
- G4 (gap 4) — delegated (2026-11-17) — `create_product` check order: schema → factory → item → key taken. `create_product` R0.
- G5 (gap 5) — fact — `app.core.exceptions.ValidationError(detail, errors=None)` subclasses `APIException(Exception)` and sets `status_code` (400), `error_type` (`"validation_error"`), `title` (`"Validation Error"`), `detail`, `errors`; `str(exc)` is the detail. The cards' `exc.value.detail`, `.status_code`, `.errors` are right (`delete_product` R3).
- G6 (gap 6) — fact — `apply_sale_return` checks `quantity <= 0` before the fraction (line 344 before 346): `Decimal("-0.5")` → `ValueError`. `apply_sale_return` R1.
- R1 (owner, 2026-11-17) — OQ-50 ✅ R5–R7 (revisit after launch); OQ-51 → BUG-2793, `update_product` R9, new `make_sellable` M1–M9; OQ-52 → BUG-2794, `apply_sale_return` R5, R6 ✅, R6a.
- G-PO20 (2026-11-19, executor DISCREPANCY-1 on PRDM-PO-20; owner in chat) — Intent — new `apply_production_output` R8a [BUG-2811]: on a new bucket `avg_cost_before` is NULL, `avg_cost_after` the unit cost.
- G7 (product_manager.cases.md gap 7) — Intent, decided by Claude under the reviewer's delegation (2026-11-19) — new `update_product` R10a: R9 (400) before R10 (409).
