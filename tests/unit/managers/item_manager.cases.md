# Test cases — `app/managers/item_manager.py`

> **Spec:** `tests/unit/managers/item_manager.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-10-18; stays APPROVED after the fill-gaps of 2026-10-30). Four history tables are not decided and have no card (Spec gap 8). P1–P9, Q1 and the house-rule / reused-bug lines were decided by Claude under the reviewer's delegation (2026-10-18); Q2 (BUG-948, "Refuse while in use") and its sub-point (d) are the owner's own answers, as are gaps 5 and 6, "Both block", the correction of gap 5 (2026-10-30) and "stock with a deleted parent does not block" (2026-10-30, 2026-10-31); gap 4, which rows count as cross-workspace, lines judged one at a time and "deleted means `is_deleted`" are Claude's reading, not the owner's words.
> **Revision:** 8 (2026-10-31) — two sources. **Owner's answer:** stock with a deleted parent does not block (`delete_item` R9 (a), (b), (g), R9a, R9b). **Verification round 6:** its 7 `case-missing` findings. **Changed card: D-86** — now `Expect: pass` and `soft-delete`, same Given, retitled, `result =` in the When, Then rewritten, Rules changed, `Fails today` removed. No other existing card changed. Added ITM-D-99 … D-102 (deleted parent, W1, pass), D-103 (only deactivated parents still block, xfail), D-104 … D-114 (deleted parent with cross-workspace rows, one shape per card, pass), D-115 (beside a live blocker, xfail), D-116 (open lines tied to a deleted factory, xfail), D-117 … D-119 (finding 1, xfail), D-120 … D-122 (finding 2, xfail), D-123 … D-126 (finding 3, pass), D-127 (finding 4, xfail), D-128 … D-131 (finding 5, xfail), D-132 (finding 6, xfail), D-133 (finding 7, xfail). All 35 are `Author: claude`, and every xfail is strict BUG-948.
> Revision 7 (2026-10-30) — closes the limit recorded in revision 6: every row of D-80 and D-81 gave the same single entry, so a fix dropping one shape went unnoticed. Added ITM-D-92 … D-94 (W2 stock, machine and `products` row on a W1 parent), D-95 … D-97 (W2 line on a W1 sales, work and transfer order), D-98 (W2 line on a W1 batch), one shape per card, all strict xfail BUG-948, `Author: claude`. No existing card changed; D-80 and D-81 stay, for "one entry however many rows".
> Revision 6 (2026-10-30) — the owner corrected gap 5: a row linking across workspaces is invalid data, refused at creation, and `delete_item` still refuses but shows it only as one `{"type": "other_workspace"}` entry, no id, last (`delete_item` R9 intro, R9b, Errors new row 5; unknown user is now row 6). **Changed cards:** D-49 … D-54, D-69, D-73, D-80, D-81 (title, Rules, Then 3 now the generic entry; still xfail BUG-948), D-81 also Given (no W2 stage; lines renumbered), D-56 (title, Rules, Then 3: normal entries, then the generic one), D-55, D-82 (Rules only), D-11 (Rules: Errors row 6). Added ITM-D-87, D-88 (W1 line on a W2 order, on a W2 batch), D-89 (one W1 and one W2 line on a W1 order), D-90 (W1 rows on a W2 stage and a W2 factory get normal entries) (all xfail BUG-948), D-91 (W2 row at `qty 0`, pass); all 5 `Author: claude`.
> Revision 5 (2026-10-30, after verification rounds 3 and 4; round 4 changed D-86 Given 2 to add `is_active False`) — closes the six `case-missing` findings of `item_manager.verify.md`, all rules already in the spec. Added ITM-D-80, D-81 (mixed shapes, xfail BUG-948), D-82 (W1 order on a W2 stage "Complete", pass), D-83 (other-workspace item in use, pass), D-84 (returns on orders that block, xfail BUG-948), D-85 (waste and byproduct lines at quantity 0, xfail BUG-948), D-86 (soft-deleted factory and machine, xfail BUG-948). All 7 are `Author: claude`. **Changed card: D-48** — two new Then lines 4 and 5 (`I1 not in db.dirty`, `db.flush()`) before the re-reads; the old Then 4 … 8 are now Then 6 … 10; finding 6. Reviewer summary: the sentence about D-49 … D-54 and "any workspace check" corrected (finding 1). New Spec gap 9.
> Revision 4 (2026-10-30) — spec fill-gaps of `delete_item` R9, R9a, R9b, R10, R10a and Notes (Spec gaps 4, 5, 6), and the owner's "Both block": R9 (g) `products`, R9 (h) production batches, R9b types `product_stock`, `production_batch`. Added ITM-D-48 (item in use + unknown user, xfail BUG-948), D-49 … D-54 (a W2 row blocks, one per R9 (a)–(f), xfail BUG-948), D-55 (a W2 purchase order at its own stage "Complete" does not block, pass), D-56 (W1 and W2 blockers sorted together, xfail BUG-948), D-57 … D-65 (one pass card per R9a row type), D-66 … D-75 (R9 (g), (h) blocking, W2 variants, entries and sort, xfail BUG-948), D-76 … D-79 (R9 (g), (h) not blocking, pass). All 32 are `Author: claude`. No existing card changed: none is wrong under the revised rules (D-11 stays the not-in-use case). Conventions: rows may now change `workspace_id` with "but", recipes F9, MC9, AC9, WT9, PL9, PL1, finished stock, batch, batch line, and how R9a rows are written. Reviewer summary: per-callable numbers and the `Author: claude` count corrected for L-09 and FS-12, which revision 3 left out.
> Revision 3 (2026-10-18, after verification) — added ITM-L-09 and ITM-FS-12 (`Author: claude`), the default `limit` of `list_items_filtered` (100) and `find_similar_items` (5); mutation survivors #36 and #37.
> Revision 2 — owner answered Q2 (d) (2026-10-18): `delete_item` R9 (d) a not-completed sales order line blocks; new R9b the refusal lists every blocker (`args[0]` message, `args[1]` blocker list). Added ITM-D-39 … D-47 (all xfail BUG-948); D-14 … D-24 Then 2 now check `args[0]` instead of `str(exc.value)`; D-30 Rules line updated; Spec gap 1 marked closed.
> **Counts:** 275 cases · 143 expected-to-pass · 132 expected-to-fail (bugs) · 12 deferred

## Reviewer summary
- **Per callable:** `create_item` 40 (18 bug) · `update_item` 51 (30 bug) · `get_item` 8 (4 bug) · `list_items_filtered` 9 · `count_items_filtered` 3 · `distinct_units` 2 · `find_similar_items` 12 (1 bug) · `delete_item` 133 (71 bug) · `_assign_tags_to_item` 13 (8 bug) · `get_tags_for_item` 2 · `get_tags_for_items` 2.
- **Expected-to-fail by bug (all strict):** BUG-934 2 · BUG-935 3 · BUG-936 11 · BUG-937 4 · BUG-938 3 · BUG-939 4 · BUG-941 2 · BUG-942 5 · BUG-943 4 · BUG-944 9 · BUG-945 1 · BUG-946 10 · BUG-947 2 · BUG-948 69 · BUG-017 2 · BUG-034 1 (DAO bug, seen through `find_similar_items` R3). BUG-940 and BUG-931 have no card here (deferred).
- **Owner's answer Q2 / BUG-948:** one blocking reason per card, strict xfail — factory stock (D-14 STORAGE with a tag count, D-15 DAMAGED, D-16 negative), machine stock (D-17), purchase order at Draft / Planning / Receiving (D-18, D-19, D-20), work order DRAFT / IN_PROGRESS (D-21, D-22), replaced item of an open work-order line (D-23), transfer order not completed (D-24), sales order not completed (D-39, owner's answer to (d)). D-14 … D-24 check the message as `args[0]` (the refusal now has two args). R9b, the blocker list: one blocker of each type gives exactly that one entry (D-39 sales, D-40 … D-44 the other five types), two types come in the fixed type order (D-45), an order with two lines of the item is listed once (D-46), two stock rows are two entries by id (D-47). One pass card per state that does not block: stock 0 (D-25), soft-deleted stock (D-26), machine stock 0 (D-27), purchase order Complete (D-28), voided (D-29), sales order completed (D-30), work order COMPLETED / VOIDED / soft-deleted / removed line (D-31 … D-34), transfer order completed (D-35); plus "already deleted" wins (D-36) and other items' rows never block (D-37, D-38).
- **Revision 4 (spec gaps 4, 5, 6):** an item in use deleted by an unknown user gets the refusal, not a database error (D-48; Claude's reading, not the owner's words). Gap 5, as the owner corrected it (revision 6): a row linking across workspaces is invalid data; it blocks in the same states as a normal row but shows only as one generic entry, last: one card per R9 (a)–(h) (D-49 … D-54, D-69, D-73), W2 rows on W1 parents (D-92 … D-98, one shape per card; D-80, D-81 combined), W1 lines on W2 parents (D-87, D-88), one normal and one W2 line (D-89), normal blockers before the generic entry (D-56). Not blocking: D-55, D-91. W1 rows on a W2 stage or factory stay normal (D-82, D-90). Owner's answer: R9a's rows are covered, one pass card per row type (D-57 … D-65), template lines by `item_id` and by `replaced_item_id`, formula lines and stages. Owner's choice "Both block": finished-goods stock (D-66; negative D-67; inactive row D-68; W2 D-69; two rows, two entries D-70) and open production batches (draft D-71, in progress D-72, W2 D-73, two lines, one entry D-74) block; D-75 checks the sort across `transfer_order`, `product_stock`, `production_batch`; quantity 0, soft-deleted, `completed` and `cancelled` do not block (D-76 … D-79). That a soft-deleted `products` row does not block, and the `type` strings and their position, are Claude's application, not the owner's words.
- **Revision 8:** owner's answer: stock in a deleted factory, on a deleted machine or on a machine of a deleted factory does not block and stays (D-86, D-99 … D-102), in any workspace, with no generic entry (D-104 … D-114). "Deleted" means `is_deleted`; a parent that is only deactivated still blocks (D-103; Claude's reading). Such stock beside a live blocker is left out of the list (D-115). Open orders and batches tied to a deleted factory still block (D-116). Round 6: W1 line on a W2 sales, work, transfer order (D-117 … D-119); `replaced_item_id` lines (D-120 … D-122); cross-workspace rows in non-blocking states (D-123 … D-126); W1 rows on W2 parents (D-127); lines one at a time per type (D-128 … D-131); generic entry last with a normal work and transfer order (D-132); unknown user with only a cross-workspace blocker (D-133).
- **Delegated answers and the cards that rest on them:** P2 / BUG-941 — U-06, D-05 (pass neighbours U-05, D-04). P3 / BUG-942 — U-18 … U-22. P4 / BUG-943 — C-37, U-43, A-06, A-09. P5 / BUG-944 — C-35, C-36, U-42, A-02 … A-05, A-07, A-08. P6 / BUG-945 — D-09. P7 / BUG-946 — C-21 … C-25, C-29, C-30, C-32, U-46, U-50 (pass neighbours C-26 … C-28, C-31, U-47 … U-49). P8 / BUG-947 — U-23, U-24. Q1 (`intended`, names not unique) — C-19, C-20, U-51 (pass).
- **Notable design choices:**
  - Row order: no card depends on physical row order or collation — every list result is compared as sorted ids, so there are no non-strict xfails and no statement recorders (the tag pass-through orders BUG-932 / BUG-933 and the similar-items order BUG-018 belong to the DAO cards).
  - BUG-934: the staying tag keeps its link (same `id`, `assigned_by`, `assigned_at` — U-34) and its count (U-35, at 0); the parts that already hold (removed tag −1, new tag +1, final set) are the pass card U-33. BUG-935: the link to a deleted tag survives a tag save (U-38, U-40, U-41); its unchanged count holds today (U-39).
  - BUG-939: the no-op cards use U2 against an item with `updated_by None`, so they fail today; U-30 (same user already stamped → nothing written) holds today. U-28 needs BUG-934 and BUG-939 fixed; it is tagged BUG-939 (the line that fails).
  - Stock and order rows are described in domain terms with one recipe per table in Conventions; the builders come from the helper file.
  - D-48 has no savepoint around the call, although it fails on flush today: a savepoint would undo a write made before the refusal and hide it, and R10a says the transaction stays usable. Then 4 and 5 prove it: nothing pending on the item and a flush that works, both before any re-read, because `expire_all()` would throw a pending change away. A check after the re-read alone would not.
  - D-55 uses stage "Complete" in W2 with no such stage in W1, so a fix that looks up the stage in the item's workspace wrongly blocks. D-56 builds the W2 stock row first (lower id): "W1 first" is now the right order, so a plain sort by id, or a W2 row listed with its own type, fails, and two cross-workspace rows give one entry. D-49 … D-54, D-69, D-73 put a row and its parents in W2; the mixed shapes are D-92 … D-98 (one W2 row on a W1 parent per card), D-87, D-88 (W1 lines on W2 parents), D-89 (one line of each; also the only one-shape card for a W2 line on a W1 purchase order). The stage or factory a row points at is not part of the test, so D-82 and D-90 expect normal behavior; D-90 fails if a W1 row on a W2 parent is hidden behind the generic entry; D-127 does the same for machine, factory, account, work-order type, stage and production line. D-56 no longer guards the order of work and transfer orders, because its transfer order is W2; D-132 does.
  - D-80 and D-81 can no longer notice a dropped shape: every row in them gives the same single entry, so the other rows hide it. D-92 … D-98 and D-89 do that job. D-80 and D-81 stay for one thing only: several cross-workspace rows of different types give one entry, not one per type or per row. D-56 checks that for two rows; these two check it for four.
  - D-83 is a pass card, not xfail BUG-941. Its point is that no blocker list reaches the caller, and that holds today and after both fixes. As an xfail it could not notice a BUG-948 fix that checks blockers first while BUG-941 is still open. The exact "not found" message stays with D-05.
  - D-85 checks several rules in one list: dropping either role changes the list. D-86 is now a pass card: any of its three rows that blocks fails the call, so it combines them, but it uses both flags on the parents. D-99 … D-102 set only `is_deleted`, and each isolates one row and one parent.
  - One card per shape where a shape could hide: every card that expects only the generic entry holds one shape (D-117 … D-122), and D-128 … D-131 hold one type each, because a generic entry from another type would hide a missing one. Rows are combined where each gives its own entry (D-103, D-115, D-116, D-127, D-132) or in pass cards, where any row that wrongly blocks fails the call (D-123 … D-126).
  - D-104 … D-114 are one shape per card as asked, though pass cards cannot hide a shape; D-113, D-114 add the machine of a deleted factory, which the spec's Notes list.
  - D-115 also holds a W2 row in a deleted W2 factory: exact equality fails if it gets a generic entry. D-116 covers all five order and batch types against the same deleted factory.
  - D-59, D-60: a `pending` return on an order that does not block, as the spec's Notes say, so the card tests the return and not the order line. The product's flows would reopen such an order; the state is built on purpose. The return statuses `completed` and `voided` have no card of their own (the status is not read).
  - D-75 builds in the reverse of the expected order and would fail an alphabetical type order. D-67 and D-68 go beyond the requested list: the spec names a negative quantity and "`products.is_active` is not looked at", and without them neither rule has a card.
  - Cards marked `Author: claude` (97): direct insert as the When — C-29, C-30, C-31; race simulation — C-32; savepoint rollback and commit spy, one per writer — C-40, U-45, D-12, A-13; rows built in a loop — L-09, FS-12; follow-up calls after the When — D-13; unknown user with no savepoint — D-48; rows outside the helper sheet — D-49 … D-133, with D-133 also unknown user with no savepoint.
- **Needs a decision:** Spec gap 8: do the history rows `product_ledger`, `project_component_item_ledger`, `sales_delivery_items` and `invoice_items.item_id` block the delete? Not decided by the owner, so no card. Worth a look: gap 3 (name of the SKU check the race card patches).


## Conventions for this module

**IDs.** `ITM` = `app/managers/item_manager.py`. `C` create_item · `U` update_item · `G` get_item · `L` list_items_filtered · `N` count_items_filtered · `UN` distinct_units · `FS` find_similar_items · `D` delete_item · `A` _assign_tags_to_item · `TI` get_tags_for_item · `TS` get_tags_for_items.

**Actors and fixed values.**
- `M` = the singleton `item_manager` (`from app.managers.item_manager import ItemManager, item_manager`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword, except where a card writes a positional call. `result` = what the When call returns. The session does not autoflush.
- W1, W2 = two `workspaces` rows. U1, U2 = two `profiles` rows: U1 is `created_by` / `assigned_by` of every Given row, U2 is the acting user of the calls. These four rows exist in every test and need no Given line. No other row exists unless the card's Given lists it.
- `Item` = `app.models.item.Item`; `ItemTag` = `app.models.item_tag.ItemTag`; `ItemTagAssignment` = `app.models.item_tag_assignment.ItemTagAssignment`; `ItemCreate`, `ItemUpdate` = the schemas of `app.schemas.item`. `select`, `text` = `sqlalchemy.select`, `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has. T0 = `datetime(2025, 12, 1, 8, 0, 0)` (naive).
- Text values are Python literals: `"\t"` is one tab. Copy them exactly, as plain strings (never raw strings).

**Externals.** None. Nothing is mocked (only the cards listed under Race simulations patch something). `created_at`, `updated_at`, `assigned_at` are asserted only as `is None` / `is not None` or against a value read before the call.

**Given rows.** Rows are inserted directly (never through `M`) and flushed one at a time in the order written, so ids rise in that order. A Given line names a recipe below, then after the word "but" every column that differs.
- **item** = `items` row built with `Item`: `workspace_id W1.id`, `unit "pcs"`, `description None`, `sku None`, `item_type "physical"`, `is_active True`, `created_by U1.id`, `updated_by None`, `updated_at None`; the recipe or card gives `name` and `name_normalized`. Item recipes: **I1** = item, `name "Bolt M8"`, `name_normalized "bolt m8"`. **I2** = item, `name "Washer Ten"`, `name_normalized "washer ten"`. **IX** = item, `name "Old Rivet"`, `name_normalized "old rivet"`, `is_active False` (the deleted item). **I9** = item, `name "Far Spring"`, `name_normalized "far spring"`, `workspace_id W2.id`.
- **tag** = `item_tags` row built with `ItemTag`: `workspace_id W1.id`, `is_system_tag False`, `is_active True`, `usage_count 0`, `created_by None`. Tag recipes: **T1** = tag, `name "Spare Part"`, `tag_code "spare_part"`. **T2** = tag, `name "Galvanized"`, `tag_code "galvanized"`. **K3** = tag, `name "Zinc Coat"`, `tag_code "zinc_coat"`. **TD** = tag, `name "Obsolete"`, `tag_code "obsolete"`, `is_active False` (the deleted tag). **T9** = tag, `name "Far Crate"`, `tag_code "far_crate"`, `workspace_id W2.id`.
- **link of I to T** = `item_tag_assignments` row built with `ItemTagAssignment`: `workspace_id` = I's `workspace_id`, `item_id I.id`, `tag_id T.id`, `assigned_by U1.id`; `assigned_at` left to the model default.
- **Stock and order rows** (`delete_item` cards only), each built with the model class of its table, `workspace_id W1.id` (a card changes it with "but" for a row of W2; such a row keeps the item of W1):
  - **F1** = `factories` row: `name "Main Plant"`, `abbreviation "MP"`, `created_by U1.id`. **MC1** = `machines` row: `name "Lathe"`, `factory_id F1.id`.
  - **stock of I** = `inventory` row: `item_id I.id`, `factory_id F1.id`, `inventory_type InventoryTypeEnum.STORAGE` (`app.models.enums`), `is_deleted False`, `created_by U1.id`; the card gives `qty`.
  - **machine stock of I** = `machine_items` row: `machine_id MC1.id`, `item_id I.id`, `req_qty None`, `defective_qty None`; the card gives `qty`.
  - **stage "X"** = `statuses` row: `name "X"`, `comment "stage"`.
  - **purchase order** = `purchase_orders` row: `po_number "PO-ITM-1"`, `destination_type "storage"`, `destination_id F1.id`, `created_by U1.id`, `voided False`; the card gives `current_status_id`. **PO line of I** = `purchase_order_items` row: `purchase_order_id` = that order's id, `line_number 1`, `item_id I.id`, `quantity_ordered 5`.
  - **AC1** = `accounts` row: `name "Acme Buyer"`. **sales order** = `sales_orders` row: `sales_order_number "SO-ITM-1"`, `account_id AC1.id`, `factory_id F1.id`, `created_by U1.id`, `order_completed False`; the card gives `current_status_id`. **SO line of I** = `sales_order_items` row: `sales_order_id` = that order's id, `item_id I.id`, `quantity_ordered 5`, `unit_price 10`, `line_total 50`.
  - **WT1** = `work_order_types` row: `name "Repair"`. **work order** = `work_orders` row: `work_order_number "WO-ITM-1"`, `work_order_type_id WT1.id`, `title "Fix press"`, `factory_id F1.id`, `is_deleted False`; the card gives `status`. **WO line of I** = `work_order_items` row: `work_order_id` = that order's id, `item_id I.id`, `quantity 2`, `replaced_item_id None`, `is_deleted False`.
  - **transfer order** = `transfer_orders` row: `transfer_number "TR-ITM-1"`, `source_location_type "storage"`, `source_location_id F1.id`, `destination_location_type "storage"`, `destination_location_id F1.id`, `created_by U1.id`, `completed_at None`; the card gives `current_status_id`. **TO line of I** = `transfer_order_items` row: `transfer_order_id` = that order's id, `line_number 1`, `item_id I.id`, `quantity 3`.
  - **finished stock of I** = `products` row built with `Product` (`app.models.product`): `item_id I.id`, `factory_id F1.id`, `is_available_for_sale False`, `is_active True`, `is_deleted False`; the card gives `qty`.
  - **PL1** = `production_lines` row built with `ProductionLine` (`app.models.production_line`): `factory_id F1.id`, `name "Line One"`. **batch** = `production_batches` row built with `ProductionBatch` (`app.models.production_batch`): `batch_number "PB-ITM-1"`, `production_line_id PL1.id`, `batch_date date(2025, 12, 1)` (`date` from `datetime`); the card gives `status`. **batch line of I** = `production_batch_items` row built with `ProductionBatchItem` (`app.models.production_batch_item`): `batch_id` = the id of the last batch built before it, `item_id I.id`, `item_role "input"`.
  - **Parents of W2:** **F9** = F1, but `workspace_id W2.id`, `name "Far Plant"`, `abbreviation "FP"`. **MC9** = MC1, but `workspace_id W2.id`, `factory_id F9.id`. **AC9** = AC1, but `workspace_id W2.id`, `name "Far Buyer"`. **WT9** = WT1, but `workspace_id W2.id`, `name "Far Repair"`. **PL9** = PL1, but `workspace_id W2.id`, `factory_id F9.id`, `name "Far Line"`.
  - **R9a row** = a row of a table without a recipe: the Given line names the table, the class with its import path, and every column to set; import the class in the test. Other columns keep their defaults.
- A Given line written as code (`l1_id = L1.id`) is a step to run exactly as written, at that place in the order.

**Named checks.**
- **stored_count(T)** = `db.scalar(text("select usage_count from item_tags where id = :i"), {"i": T.id})`.
- **links_of(I)** = `db.expire_all()`, then SELECT every `item_tag_assignments` row with `item_id == I.id` (any workspace), ordered by `id`, as a list. **tag_ids_of(I)** = `sorted(l.tag_id for l in links_of(I))`. "the link of I to T" in a Then line = the one row of links_of(I) with `tag_id == T.id`.
- **ids(x)** = `sorted(r.id for r in x)` — order is never part of a check in this module; the right-hand ids are written in Given order (ascending).
- **re-read X** = `db.expire_all()`, then SELECT X by id from its own table; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot after the last Given line). X may be any Given row.
- **nothing written** = the numbers of rows in `items`, `item_tags` and `item_tag_assignments` (all workspaces) equal their values before the call.
- `count:` lines count rows of the named table in all workspaces, with the filter stated.
- `raises: ValueError`: plain `with pytest.raises(ValueError) as exc:` around the call — no savepoint; the message is checked as `str(exc.value) == "…"`. Exception: the "in use" refusal of `delete_item` has two args — message `exc.value.args[0]`, blocker list `exc.value.args[1]` (a list of dicts `{"type": …, "id": …}`, compared with `==` to the literal list in the card, order included; the generic entry `{"type": "other_workspace"}` has no `"id"`).
- `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`, `raises: DataError` = `sqlalchemy.exc.DataError`: wrap as `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards. `ForeignKeyViolation` = `psycopg2.errors.ForeignKeyViolation`.
- `raises: ValidationError` = `pydantic.ValidationError`: plain `with pytest.raises(ValidationError):` around the construction of the schema object.
- Further `raises:` lines of a card are assertions on `exc.value`, after the `with` block, one `assert` per line.

**Targets.** "target `schema`" = the When only builds the schema object; `M` is not called. "target `database`" (Author: claude cards only) = the When inserts one row directly with `db.add(...)` and `db.flush()`; an expected `IntegrityError` is wrapped as above.

**xfail cards.** Write the call and the checks exactly as shown — also when the call uses a parameter that does not exist yet (`include_deleted` on `get_item`); the harness adds the marker. Every xfail in this module is **strict** (`pytest.mark.xfail(strict=True, reason="BUG-NNN")`); no card depends on physical row order or collation, so there are no non-strict cards and no statement recorders.

**Rolled back** (Author: claude cards only). `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.

**Race simulations** (Author: claude cards only). ITM-C-32 patches the manager's own SKU-existence check to report "free", to put the code in the state "a concurrent request already passed the Python check" (`create_item` R7). The check does not exist yet; its name is not in the spec (Spec gap 3): patch `ItemManager._check_sku_exists` with `create=True`, and revise the card with the fix. Nothing else may be patched.

## `ItemManager.create_item`

### ITM-C-01 — create stores the item with the values sent, in the caller's workspace, by the caller
- **Rules:** `create_item` R1, R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. No items exist.

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", description="Zinc plated", sku="B-M8"), workspace_id=W1.id, user_id=U2.id)`. `item_type` and `tag_ids` are not sent.

**Then**
1. returns: `isinstance(result, Item)`.
2. returns: `result.id is not None`.
3. re-read the returned row: `name == "Bolt M8"`, `unit == "pcs"`.
4. re-read the returned row: `description == "Zinc plated"`, `sku == "B-M8"`.
5. re-read the returned row: `item_type == "physical"`.
6. re-read the returned row: `workspace_id == W1.id`, `created_by == U2.id`.
7. count: `items` has exactly 1 row.

### ITM-C-02 — a new item is live and carries no update stamp
- **Rules:** `create_item` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No items exist.

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `is_active is True`.
3. re-read the returned row: `created_at is not None`.
4. re-read the returned row: `updated_at is None`, `updated_by is None`.

### ITM-C-03 — description and SKU not sent are stored as None
- **Rules:** `create_item` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No items exist.

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=W1.id, user_id=U2.id)`. `description` and `sku` are not sent.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `description is None`.
3. re-read the returned row: `sku is None`.

### ITM-C-04 — an empty description is stored as an empty string
- **Rules:** `create_item` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No items exist.

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", description=""), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `description == ""`.

### ITM-C-05 — item type "service" is stored as sent
- **Rules:** `create_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No items exist.

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="Fitting Labour", unit="hour", item_type="service"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `item_type == "service"`.
3. re-read the returned row: `name == "Fitting Labour"`, `unit == "hour"`.

### ITM-C-06 — the normalized name is computed from the name
- **Rules:** `create_item` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. No items exist.

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="Steel Rod 22 m", unit="pcs"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `name_normalized == "steel rod 22m"`.

### ITM-C-07 — a name of only punctuation gets an empty normalized name
- **Rules:** `create_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No items exist.

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="!!!", unit="pcs"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `name_normalized == ""`.
3. re-read the returned row: `name == "!!!"`.

### ITM-C-08 — a padded name still gets the trimmed, collapsed normalized name
- **Rules:** `create_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No items exist.

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="  Steel  Rod 22 m ", unit="pcs"), workspace_id=W1.id, user_id=U2.id)`. The name has two spaces before, two between "Steel" and "Rod", one after.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `name_normalized == "steel rod 22m"`.

### ITM-C-09 — the name is stored trimmed, inner spaces kept
- **Rules:** `create_item` R3 [BUG-936]
- **Kind:** bug
- **Expect:** xfail BUG-936
- **Fails today on:** Then 2 (the name is stored as typed, with the outer spaces)

**Given**
1. No items exist.

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="  Steel  Rod 22 m ", unit="pcs"), workspace_id=W1.id, user_id=U2.id)`. The name has two spaces before, two between "Steel" and "Rod", one after.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `name == "Steel  Rod 22 m"`.

### ITM-C-10 — inner whitespace and case of the name are kept
- **Rules:** `create_item` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No items exist.

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="steel  ROD", unit="pcs"), workspace_id=W1.id, user_id=U2.id)`. Two spaces between the words, none outside.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `name == "steel  ROD"`.

### ITM-C-11 — an empty name is rejected by ItemCreate
- **Rules:** `create_item` R3 [BUG-936], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-936
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. No items exist.

**When**
- `ItemCreate(name="", unit="pcs")` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. count: `items` has exactly 0 rows.

### ITM-C-12 — a name of three spaces is rejected by ItemCreate
- **Rules:** `create_item` R3 [BUG-936], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-936
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. No items exist.

**When**
- `ItemCreate(name="   ", unit="pcs")` (target `schema`; M is not called). The name is three spaces.

**Then**
1. raises: `ValidationError`.
2. count: `items` has exactly 0 rows.

### ITM-C-13 — a name of one tab is rejected by ItemCreate
- **Rules:** `create_item` R3 [BUG-936], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-936
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. No items exist.

**When**
- `ItemCreate(name="\t", unit="pcs")` (target `schema`; M is not called). The name is the Python literal `"\t"` (one tab).

**Then**
1. raises: `ValidationError`.
2. count: `items` has exactly 0 rows.

### ITM-C-14 — an empty unit is rejected by ItemCreate
- **Rules:** `create_item` R3 [BUG-936], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-936
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. No items exist.

**When**
- `ItemCreate(name="Bolt M8", unit="")` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. count: `items` has exactly 0 rows.

### ITM-C-15 — a unit of two spaces is rejected by ItemCreate
- **Rules:** `create_item` R3 [BUG-936], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-936
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. No items exist.

**When**
- `ItemCreate(name="Bolt M8", unit="  ")` (target `schema`; M is not called). The unit is two spaces.

**Then**
1. raises: `ValidationError`.
2. count: `items` has exactly 0 rows.

### ITM-C-16 — a one-character name and unit are accepted by ItemCreate
- **Rules:** `create_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No items exist.

**When**
- `result = ItemCreate(name="a", unit="m")` (target `schema`; M is not called).

**Then**
1. returns: `result.name == "a"`.
2. returns: `result.unit == "m"`.

### ITM-C-17 — the unit is stored trimmed, case kept
- **Rules:** `create_item` R4 [BUG-017]
- **Kind:** bug
- **Expect:** xfail BUG-017
- **Fails today on:** Then 2 (the unit is stored as typed, with the outer spaces)

**Given**
1. No items exist.

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit=" Kg "), workspace_id=W1.id, user_id=U2.id)`. One space before and after "Kg".

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `unit == "Kg"`.

### ITM-C-18 — the case of the unit is kept
- **Rules:** `create_item` R1, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No items exist.

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="Kg"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `unit == "Kg"`.

### ITM-C-19 — the exact name of a live item does not block the create
- **Rules:** `create_item` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. returns: `result.id != I1.id`.
3. re-read the returned row: `name == "Bolt M8"`.
4. count: `items` with `workspace_id == W1.id` and `name == "Bolt M8"` has exactly 2 rows.
5. unchanged: unchanged(I1).

### ITM-C-20 — a name with the same normalized form as a live item does not block the create
- **Rules:** `create_item` R5, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="BOLT-m8", unit="pcs"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `name == "BOLT-m8"`, `name_normalized == "bolt m8"`.
3. count: `items` with `name_normalized == "bolt m8"` has exactly 2 rows.
4. unchanged: unchanged(I1).

### ITM-C-21 — the SKU is stored trimmed
- **Rules:** `create_item` R7 [BUG-946]
- **Kind:** bug
- **Expect:** xfail BUG-946
- **Fails today on:** Then 2 (the SKU is stored as typed, with the outer spaces)

**Given**
1. No items exist.

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", sku=" B-M8 "), workspace_id=W1.id, user_id=U2.id)`. One space before and after "B-M8".

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `sku == "B-M8"`.

### ITM-C-22 — an empty SKU is stored as None
- **Rules:** `create_item` R7 [BUG-946]
- **Kind:** bug
- **Expect:** xfail BUG-946
- **Fails today on:** Then 2 (the empty string is stored)

**Given**
1. No items exist.

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", sku=""), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `sku is None`.

### ITM-C-23 — a SKU of three spaces is stored as None
- **Rules:** `create_item` R7 [BUG-946]
- **Kind:** bug
- **Expect:** xfail BUG-946
- **Fails today on:** Then 2 (the three spaces are stored)

**Given**
1. No items exist.

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", sku="   "), workspace_id=W1.id, user_id=U2.id)`. The SKU is three spaces.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `sku is None`.

### ITM-C-24 — a SKU used by a live item of the workspace is refused
- **Rules:** `create_item` R7 [BUG-946], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-946
- **Fails today on:** Then 1 (no error is raised: SKUs are not checked, so a second item "B-M8" is created)

**Given**
1. I1, but `sku "B-M8"`.

**When**
- `M.create_item(db, item_data=ItemCreate(name="Hex Screw", unit="pcs", sku="B-M8"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Item with SKU 'B-M8' already exists"`.
3. count: `items` has exactly 1 row.
4. unchanged: unchanged(I1).

### ITM-C-25 — a SKU that differs only in case and outer spaces is refused, with the trimmed value in the message
- **Rules:** `create_item` R7 [BUG-946], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-946
- **Fails today on:** Then 1 (no error is raised: SKUs are not checked)

**Given**
1. I1, but `sku "B-M8"`.

**When**
- `M.create_item(db, item_data=ItemCreate(name="Hex Screw", unit="pcs", sku=" b-m8 "), workspace_id=W1.id, user_id=U2.id)`. One space before and after "b-m8".

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Item with SKU 'b-m8' already exists"`.
3. count: `items` has exactly 1 row.
4. unchanged: unchanged(I1).

### ITM-C-26 — the SKU of a deleted item can be used again
- **Rules:** `create_item` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. IX, but `sku "B-M8"`.

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="Hex Screw", unit="pcs", sku="B-M8"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `sku == "B-M8"`, `is_active is True`.
3. count: `items` has exactly 2 rows.
4. unchanged: unchanged(IX).

### ITM-C-27 — the SKU of another workspace's item does not block the create
- **Rules:** `create_item` R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I9, but `sku "B-M8"`.

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="Hex Screw", unit="pcs", sku="B-M8"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `sku == "B-M8"`, `workspace_id == W1.id`.
3. unchanged: unchanged(I9).

### ITM-C-28 — two items without a SKU can exist
- **Rules:** `create_item` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1. (`sku None`.)

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="Hex Screw", unit="pcs"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `sku is None`.
3. count: `items` with `sku` NULL has exactly 2 rows.

### ITM-C-29 — the database refuses a second live item with the same SKU in a workspace
- **Rules:** `create_item` R7 [BUG-946]
- **Kind:** bug
- **Expect:** xfail BUG-946
- **Fails today on:** Then 1 (no error is raised: the table has no unique index, so the row is saved)
- **Author:** claude — target `database`: the When is a direct insert, not a manager call

**Given**
1. I1, but `sku "B-M8"`.

**When**
- insert directly (target `database`; M is not called): `db.add(Item(workspace_id=W1.id, name="Hex Screw", name_normalized="hex screw", unit="pcs", sku="B-M8", created_by=U1.id))`, then `db.flush()`.

**Then**
1. raises: `IntegrityError` on flush.
2. count: `items` has exactly 1 row.

### ITM-C-30 — the database refuses a second live item whose SKU differs only in case and outer spaces
- **Rules:** `create_item` R7 [BUG-946]
- **Kind:** bug
- **Expect:** xfail BUG-946
- **Fails today on:** Then 1 (no error is raised: the table has no unique index, so the row is saved)
- **Author:** claude — target `database`: the When is a direct insert, not a manager call

**Given**
1. I1, but `sku "B-M8"`.

**When**
- insert directly (target `database`; M is not called): `db.add(Item(workspace_id=W1.id, name="Hex Screw", name_normalized="hex screw", unit="pcs", sku="b-m8 ", created_by=U1.id))`, then `db.flush()`. The SKU ends with one space.

**Then**
1. raises: `IntegrityError` on flush.
2. count: `items` has exactly 1 row.

### ITM-C-31 — the database accepts a deleted item with the SKU of a live one
- **Rules:** `create_item` R7
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — target `database`: the When is a direct insert, not a manager call

**Given**
1. I1, but `sku "B-M8"`.

**When**
- insert directly (target `database`; M is not called): `db.add(Item(workspace_id=W1.id, name="Hex Screw", name_normalized="hex screw", unit="pcs", sku="B-M8", is_active=False, created_by=U1.id))`, then `db.flush()`.

**Then**
1. count: `items` has exactly 2 rows.
2. unchanged: unchanged(I1).

### ITM-C-32 — a duplicate SKU that passed the Python check is answered with the manager's error, not a database error
- **Rules:** `create_item` R7 [BUG-946], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-946
- **Fails today on:** Then 1 (no error is raised: there is no index, so the duplicate is saved)
- **Author:** claude — race simulation (patches the manager's own SKU check) and a savepoint around the call

**Given**
1. I1, but `sku "B-M8"`.
2. Race simulation: the manager's SKU-existence check is patched to report "free" (Conventions, Race simulations).

**When**
- `M.create_item(db, item_data=ItemCreate(name="Hex Screw", unit="pcs", sku="B-M8"), workspace_id=W1.id, user_id=U2.id)`, wrapped as `with pytest.raises(ValueError) as exc:` then `with db.begin_nested():` then the call.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Item with SKU 'B-M8' already exists"`.
3. count: `items` has exactly 1 row.
4. unchanged: unchanged(I1).

### ITM-C-33 — the tags sent are linked to the new item and counted once each
- **Rules:** `create_item` R8; `_assign_tags_to_item` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1, but `usage_count 3`.
2. T2.

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", tag_ids=[T1.id, T2.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read: `tag_ids_of(result) == [T1.id, T2.id]`.
3. re-read: every row of `links_of(result)` has `workspace_id == W1.id` and `assigned_by == U2.id`.
4. re-read: `stored_count(T1) == 4`.
5. re-read: `stored_count(T2) == 1`.

### ITM-C-34 — an empty tag list creates the item without links
- **Rules:** `create_item` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1, but `usage_count 3`.

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", tag_ids=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read: `links_of(result) == []`.
3. re-read: `stored_count(T1) == 3`.

### ITM-C-35 — an unknown tag id refuses the whole create and nothing is written
- **Rules:** `create_item` R9 [BUG-944], Errors row 3; `_assign_tags_to_item` R2, R4
- **Kind:** bug
- **Expect:** xfail BUG-944
- **Fails today on:** Then 1 (no error is raised: the unknown id is skipped and the item is created with T1)

**Given**
1. T1, but `usage_count 3`.

**When**
- `M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", tag_ids=[T1.id, MISSING]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Item tag 999999999 not found"`.
3. count: `items` has exactly 0 rows.
4. count: `item_tag_assignments` has exactly 0 rows.
5. re-read: `stored_count(T1) == 3`.

### ITM-C-36 — a tag of another workspace refuses the create as not found
- **Rules:** `create_item` R9 [BUG-944], Errors row 3; `_assign_tags_to_item` R2
- **Kind:** bug
- **Expect:** xfail BUG-944
- **Fails today on:** Then 1 (no error is raised: the foreign tag is skipped and the item is created)

**Given**
1. T9, but `usage_count 2`.

**When**
- `M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", tag_ids=[T9.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == f"Item tag {T9.id} not found"`.
3. count: `items` has exactly 0 rows.
4. count: `item_tag_assignments` has exactly 0 rows.
5. unchanged: unchanged(T9).

### ITM-C-37 — a deleted tag refuses the create
- **Rules:** `create_item` R9 [BUG-943], Errors row 4; `_assign_tags_to_item` R3
- **Kind:** bug
- **Expect:** xfail BUG-943
- **Fails today on:** Then 1 (no error is raised: the deleted tag is linked and counted)

**Given**
1. TD, but `usage_count 5`.

**When**
- `M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", tag_ids=[TD.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == f"Item tag {TD.id} is not active"`.
3. count: `items` has exactly 0 rows.
4. count: `item_tag_assignments` has exactly 0 rows.
5. re-read: `stored_count(TD) == 5`.

### ITM-C-38 — a user_id that is no profile id fails on flush before any tag is touched
- **Rules:** `create_item` R10, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. T1, but `usage_count 3`.

**When**
- `M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", tag_ids=[T1.id]), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"items_created_by_fkey" in str(exc.value.orig)`.
4. count: `items` has exactly 0 rows.
5. count: `item_tag_assignments` has exactly 0 rows.
6. re-read: `stored_count(T1) == 3`.

### ITM-C-39 — a workspace_id that is no workspace id fails on flush
- **Rules:** `create_item` R10, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. No items exist.

**When**
- `M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=MISSING, user_id=U2.id)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"items_workspace_id_fkey" in str(exc.value.orig)`.
4. count: `items` has exactly 0 rows.

### ITM-C-40 — the create is flushed but not committed: a rollback removes the item, its link and the count
- **Rules:** `create_item` R11, Returns, Side effects
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. T1, but `usage_count 3`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", tag_ids=[T1.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. count: `items` has exactly 1 row.
2. re-read: `stored_count(T1) == 4`.
3. count after the savepoint rollback: `items` has exactly 0 rows.
4. count after the savepoint rollback: `item_tag_assignments` has exactly 0 rows.
5. re-read after the savepoint rollback: `stored_count(T1) == 3`.
6. mock called: the `db.commit` spy was never called.

## `ItemManager.update_item`

### ITM-U-01 — a new name is stored, normalized again, and the editor is recorded
- **Rules:** `update_item` R4, R5, R9, R10, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(name="Lock Nut"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `name == "Lock Nut"`, `name_normalized == "lock nut"`.
3. re-read I1: `updated_by == U2.id`.
4. re-read I1: `updated_at is not None`.
5. count: `items` has exactly 1 row.

### ITM-U-02 — fields not sent and the creation and state columns keep their values
- **Rules:** `update_item` R4, R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I1, but `description "Zinc plated"`, `sku "B-M8"`.
2. `created_before = I1.created_at`

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(unit="box"), workspace_id=W1.id, user_id=U2.id)`. Only `unit` is sent.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `unit == "box"`.
3. re-read I1: `name == "Bolt M8"`, `name_normalized == "bolt m8"`.
4. re-read I1: `description == "Zinc plated"`, `sku == "B-M8"`, `item_type == "physical"`.
5. re-read I1: `workspace_id == W1.id`, `created_by == U1.id`.
6. re-read I1: `created_at == created_before`.
7. re-read I1: `is_active is True`.

### ITM-U-03 — description, SKU and item type sent with values are written
- **Rules:** `update_item` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1, but `description "Zinc plated"`, `sku "B-M8"`.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(description="Hot dipped", sku="HD-1", item_type="service"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `description == "Hot dipped"`.
3. re-read I1: `sku == "HD-1"`.
4. re-read I1: `item_type == "service"`.
5. re-read I1: `name == "Bolt M8"`, `unit == "pcs"`.

### ITM-U-04 — an id that no item has is refused and nothing is written
- **Rules:** `update_item` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. I1.

**When**
- `M.update_item(db, item_id=MISSING, item_data=ItemUpdate(name="Lock Nut"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Item 999999999 not found"`.
3. nothing written: nothing written.
4. unchanged: unchanged(I1).

### ITM-U-05 — an item of another workspace is refused and not changed
- **Rules:** `update_item` R2 (the side that holds today)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I9.

**When**
- `M.update_item(db, item_id=I9.id, item_data=ItemUpdate(name="Lock Nut"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. unchanged: unchanged(I9).
3. re-read I9: `name == "Far Spring"`, `updated_by is None`.

### ITM-U-06 — an item of another workspace gets the same message as a missing one
- **Rules:** `update_item` R2 [BUG-941], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-941
- **Fails today on:** Then 2 (the message says the item does not belong to the workspace)

**Given**
1. I9.

**When**
- `M.update_item(db, item_id=I9.id, item_data=ItemUpdate(name="Lock Nut"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == f"Item {I9.id} not found"`.
3. unchanged: unchanged(I9).

### ITM-U-07 — a deleted item is refused as not found and not changed
- **Rules:** `update_item` R3 [BUG-938], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-938
- **Fails today on:** Then 1 (no error is raised: the deleted item is renamed)

**Given**
1. IX.

**When**
- `M.update_item(db, item_id=IX.id, item_data=ItemUpdate(name="Lock Nut"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == f"Item {IX.id} not found"`.
3. unchanged: unchanged(IX).
4. re-read IX: `name == "Old Rivet"`, `updated_by is None`.

### ITM-U-08 — tags sent for a deleted item are neither linked nor counted
- **Rules:** `update_item` R3 [BUG-938]
- **Kind:** bug
- **Expect:** xfail BUG-938
- **Fails today on:** Then 1 (no error is raised: T1 is linked to the deleted item and its count goes up)

**Given**
1. IX.
2. T1, but `usage_count 3`.

**When**
- `M.update_item(db, item_id=IX.id, item_data=ItemUpdate(tag_ids=[T1.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == f"Item {IX.id} not found"`.
3. re-read: `links_of(IX) == []`.
4. re-read: `stored_count(T1) == 3`.
5. unchanged: unchanged(IX).

### ITM-U-09 — sending the current name repairs a stale normalized name
- **Rules:** `update_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1, but `name_normalized "stale"`.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(name="Bolt M8"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `name == "Bolt M8"`.
3. re-read I1: `name_normalized == "bolt m8"`.

### ITM-U-10 — a stale normalized name is kept when the name is not sent
- **Rules:** `update_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1, but `name_normalized "stale"`.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(unit="box"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `unit == "box"`.
3. re-read I1: `name_normalized == "stale"`.

### ITM-U-11 — inner spaces and punctuation of a new name are kept; the normalized name collapses them
- **Rules:** `update_item` R4, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(name="New  Name-2"), workspace_id=W1.id, user_id=U2.id)`. Two spaces between "New" and "Name".

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `name == "New  Name-2"`.
3. re-read I1: `name_normalized == "new name 2"`.

### ITM-U-12 — a sent name is stored trimmed
- **Rules:** `update_item` R6 [BUG-936], R5
- **Kind:** bug
- **Expect:** xfail BUG-936
- **Fails today on:** Then 3 (the name is stored as typed, with the outer spaces)

**Given**
1. I1.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(name="  Lock Nut "), workspace_id=W1.id, user_id=U2.id)`. Two spaces before, one after.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `name_normalized == "lock nut"`.
3. re-read I1: `name == "Lock Nut"`.

### ITM-U-13 — an empty name is rejected by ItemUpdate
- **Rules:** `update_item` R6 [BUG-936], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-936
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. I1.

**When**
- `ItemUpdate(name="")` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(I1).

### ITM-U-14 — a name of three spaces is rejected by ItemUpdate
- **Rules:** `update_item` R6 [BUG-936], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-936
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. I1.

**When**
- `ItemUpdate(name="   ")` (target `schema`; M is not called). The name is three spaces.

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(I1).

### ITM-U-15 — an empty unit is rejected by ItemUpdate
- **Rules:** `update_item` R6 [BUG-936], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-936
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. I1.

**When**
- `ItemUpdate(unit="")` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(I1).

### ITM-U-16 — a unit of one tab is rejected by ItemUpdate
- **Rules:** `update_item` R6 [BUG-936], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-936
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. I1.

**When**
- `ItemUpdate(unit="\t")` (target `schema`; M is not called). The unit is the Python literal `"\t"` (one tab).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(I1).

### ITM-U-17 — a sent unit is stored trimmed, case kept
- **Rules:** `update_item` R6a [BUG-017]
- **Kind:** bug
- **Expect:** xfail BUG-017
- **Fails today on:** Then 2 (the unit is stored as typed, with the outer spaces)

**Given**
1. I1.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(unit=" Kg "), workspace_id=W1.id, user_id=U2.id)`. One space before and after "Kg".

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `unit == "Kg"`.

### ITM-U-18 — an explicit null clears the description
- **Rules:** `update_item` R7 [BUG-942]
- **Kind:** bug
- **Expect:** xfail BUG-942
- **Fails today on:** Then 2 (the null is dropped and the old description stays)

**Given**
1. I1, but `description "Zinc plated"`.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(description=None), workspace_id=W1.id, user_id=U2.id)`. `description` is sent explicitly as `None`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `description is None`.

### ITM-U-19 — an explicit null clears the SKU
- **Rules:** `update_item` R7 [BUG-942], R18
- **Kind:** bug
- **Expect:** xfail BUG-942
- **Fails today on:** Then 2 (the null is dropped and the old SKU stays)

**Given**
1. I1, but `sku "OLD-12"`.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(sku=None), workspace_id=W1.id, user_id=U2.id)`. `sku` is sent explicitly as `None`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `sku is None`.

### ITM-U-20 — an explicit null name is rejected by ItemUpdate
- **Rules:** `update_item` R7 [BUG-942], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-942
- **Fails today on:** Then 1 (no error is raised; the schema accepts `None`)

**Given**
1. I1.

**When**
- `ItemUpdate(name=None)` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(I1).

### ITM-U-21 — an explicit null unit is rejected by ItemUpdate
- **Rules:** `update_item` R7 [BUG-942], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-942
- **Fails today on:** Then 1 (no error is raised; the schema accepts `None`)

**Given**
1. I1.

**When**
- `ItemUpdate(unit=None)` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(I1).

### ITM-U-22 — an explicit null item type is rejected by ItemUpdate
- **Rules:** `update_item` R7 [BUG-942], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-942
- **Fails today on:** Then 1 (no error is raised; the schema accepts `None`)

**Given**
1. I1.

**When**
- `ItemUpdate(item_type=None)` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(I1).

### ITM-U-23 — is_active sent with the edit is ignored: the item stays live
- **Rules:** `update_item` R8 [BUG-947]
- **Kind:** bug
- **Expect:** xfail BUG-947
- **Fails today on:** Then 3 (`is_active: false` is written and the item is deleted)

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. link of I1 to T1.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(name="Lock Nut", is_active=False), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `name == "Lock Nut"`.
3. re-read I1: `is_active is True`.
4. re-read: `stored_count(T1) == 4`.

### ITM-U-24 — ItemUpdate has no is_active field: a sent value is dropped
- **Rules:** `update_item` R8 [BUG-947]
- **Kind:** bug
- **Expect:** xfail BUG-947
- **Fails today on:** Then 1 (`ItemUpdate` has an `is_active` field and keeps the value)

**Given**
1. No items exist.

**When**
- `result = ItemUpdate(is_active=False)` (target `schema`; M is not called).

**Then**
1. returns: `hasattr(result, "is_active") is False`.

### ITM-U-25 — is_active true does not bring a deleted item back
- **Rules:** `update_item` R3 [BUG-938], R8 [BUG-947]
- **Kind:** bug
- **Expect:** xfail BUG-938
- **Fails today on:** Then 1 (no error is raised: `is_active: true` restores the deleted item)

**Given**
1. IX.

**When**
- `M.update_item(db, item_id=IX.id, item_data=ItemUpdate(is_active=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == f"Item {IX.id} not found"`.
3. re-read IX: `is_active is False`.

### ITM-U-26 — an empty update writes nothing and leaves the stamp empty
- **Rules:** `update_item` R9 [BUG-939]
- **Kind:** bug
- **Expect:** xfail BUG-939
- **Fails today on:** Then 2 (`updated_by` is set to U2 although nothing changed)

**Given**
1. I1. (`updated_by None`, `updated_at None`.)

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(), workspace_id=W1.id, user_id=U2.id)`. No field is sent.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `updated_by is None`.
3. re-read I1: `updated_at is None`.

### ITM-U-27 — values equal to the current ones do not stamp the item
- **Rules:** `update_item` R9 [BUG-939]
- **Kind:** bug
- **Expect:** xfail BUG-939
- **Fails today on:** Then 3 (`updated_by` is set to U2 although nothing changed)

**Given**
1. I1. (`updated_by None`, `updated_at None`.)

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(name="Bolt M8", unit="pcs"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `name == "Bolt M8"`, `unit == "pcs"`.
3. re-read I1: `updated_by is None`.
4. re-read I1: `updated_at is None`.

### ITM-U-28 — re-sending the current tag set does not stamp the item
- **Rules:** `update_item` R9 [BUG-939], R12
- **Kind:** bug
- **Expect:** xfail BUG-939
- **Fails today on:** Then 3 (`updated_by` is set to U2 although the tag set did not change)

**Given**
1. I1. (`updated_by None`, `updated_at None`.)
2. T1, but `usage_count 4`.
3. link of I1 to T1.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(tag_ids=[T1.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read: `tag_ids_of(I1) == [T1.id]`.
3. re-read I1: `updated_by is None`.
4. re-read I1: `updated_at is None`.

### ITM-U-29 — repairing a stale normalized name alone does not stamp the item
- **Rules:** `update_item` R9 [BUG-939], R5
- **Kind:** bug
- **Expect:** xfail BUG-939
- **Fails today on:** Then 3 (`updated_by` is set to U2)

**Given**
1. I1, but `name_normalized "stale"`. (`updated_by None`, `updated_at None`.)

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(name="Bolt M8"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `name_normalized == "bolt m8"`.
3. re-read I1: `updated_by is None`.

### ITM-U-30 — an empty update by the user already stamped writes nothing
- **Rules:** `update_item` R9 (the side that holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1, but `updated_by U2.id`, `updated_at T0`.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(), workspace_id=W1.id, user_id=U2.id)`. No field is sent.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `updated_by == U2.id`.
3. re-read I1: `updated_at == T0`.
4. re-read I1: `name == "Bolt M8"`.

### ITM-U-31 — tag_ids not sent leaves the links and counts alone
- **Rules:** `update_item` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. L1 = link of I1 to T1.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(unit="box"), workspace_id=W1.id, user_id=U2.id)`. `tag_ids` is not sent.

**Then**
1. returns: `result is I1` (the very object that was read).
2. unchanged: unchanged(L1).
3. re-read: `tag_ids_of(I1) == [T1.id]`.
4. re-read: `stored_count(T1) == 4`.

### ITM-U-32 — tag_ids sent as null leaves the links and counts alone
- **Rules:** `update_item` R11, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. L1 = link of I1 to T1.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(unit="box", tag_ids=None), workspace_id=W1.id, user_id=U2.id)`. `tag_ids` is sent explicitly as `None`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. unchanged: unchanged(L1).
3. re-read: `stored_count(T1) == 4`.

### ITM-U-33 — a new tag list: the removed tag loses its link and one count, the new tag gains both
- **Rules:** `update_item` R12 (the parts that hold today); `_assign_tags_to_item` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. T2, but `usage_count 6`.
4. K3.
5. link of I1 to T1.
6. link of I1 to T2.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(tag_ids=[T1.id, K3.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read: `tag_ids_of(I1) == [T1.id, K3.id]`.
3. re-read: `stored_count(T2) == 5`.
4. re-read: `stored_count(K3) == 1`.
5. re-read: `stored_count(T1) == 4`.
6. re-read: the link of I1 to K3 has `assigned_by == U2.id`, `workspace_id == W1.id`.

### ITM-U-34 — a tag that stays keeps its link: same id, same assigning user, same time
- **Rules:** `update_item` R12 [BUG-934]
- **Kind:** bug
- **Expect:** xfail BUG-934
- **Fails today on:** Then 3 (every link is deleted and T1 is linked again with a new id)

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. T2, but `usage_count 6`.
4. K3.
5. L1 = link of I1 to T1.
6. link of I1 to T2.
7. `l1_id = L1.id`
8. `l1_at = L1.assigned_at`

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(tag_ids=[T1.id, K3.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read: `tag_ids_of(I1) == [T1.id, K3.id]`.
3. re-read: the link of I1 to T1 has `id == l1_id`.
4. re-read: the link of I1 to T1 has `assigned_by == U1.id`.
5. re-read: the link of I1 to T1 has `assigned_at == l1_at`.

### ITM-U-35 — a staying tag whose count is 0 keeps the count 0
- **Rules:** `update_item` R12 [BUG-934]
- **Kind:** bug
- **Expect:** xfail BUG-934
- **Fails today on:** Then 2 (the count goes −1 (floor 0) then +1 and ends at 1)

**Given**
1. I1.
2. T1. (`usage_count 0`.)
3. link of I1 to T1.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(tag_ids=[T1.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read: `stored_count(T1) == 0`.
3. re-read: `tag_ids_of(I1) == [T1.id]`.

### ITM-U-36 — a removed tag whose count is 0 stays at 0
- **Rules:** `update_item` R12, R14
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.
2. T1. (`usage_count 0`.)
3. link of I1 to T1.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(tag_ids=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read: `links_of(I1) == []`.
3. re-read: `stored_count(T1) == 0`.

### ITM-U-37 — an empty tag list removes every link to an active tag and counts each one less
- **Rules:** `update_item` R14
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. T2, but `usage_count 6`.
4. link of I1 to T1.
5. link of I1 to T2.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(tag_ids=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read: `links_of(I1) == []`.
3. re-read: `stored_count(T1) == 3`.
4. re-read: `stored_count(T2) == 5`.

### ITM-U-38 — a tag save keeps the item's link to a deleted tag
- **Rules:** `update_item` R13 [BUG-935]
- **Kind:** bug
- **Expect:** xfail BUG-935
- **Fails today on:** Then 2 (the link to the deleted tag is erased with the others)

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. TD, but `usage_count 7`.
4. link of I1 to T1.
5. L2 = link of I1 to TD.
6. `l2_id = L2.id`

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(tag_ids=[T1.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read: `tag_ids_of(I1) == [T1.id, TD.id]`.
3. re-read: the link of I1 to TD has `id == l2_id`, `assigned_by == U1.id`.

### ITM-U-39 — a tag save does not change the count of a deleted tag on the item
- **Rules:** `update_item` R13 (the side that holds today)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. TD, but `usage_count 7`.
4. link of I1 to T1.
5. link of I1 to TD.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(tag_ids=[T1.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read: `stored_count(TD) == 7`.
3. re-read: `stored_count(T1) == 4`.

### ITM-U-40 — re-sending a deleted tag the item already carries is not refused and changes nothing for it
- **Rules:** `update_item` R13 [BUG-935], R15
- **Kind:** bug
- **Expect:** xfail BUG-935
- **Fails today on:** Then 2 (the link to TD is erased and created again with a new id)

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. TD, but `usage_count 7`.
4. link of I1 to T1.
5. L2 = link of I1 to TD.
6. `l2_id = L2.id`

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(tag_ids=[T1.id, TD.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read: the link of I1 to TD has `id == l2_id`.
3. re-read: `stored_count(TD) == 7`.

### ITM-U-41 — an empty tag list keeps the link to a deleted tag
- **Rules:** `update_item` R14 [BUG-935]
- **Kind:** bug
- **Expect:** xfail BUG-935
- **Fails today on:** Then 2 (the link to the deleted tag is erased)

**Given**
1. I1.
2. TD, but `usage_count 7`.
3. link of I1 to TD.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(tag_ids=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read: `tag_ids_of(I1) == [TD.id]`.
3. re-read: `stored_count(TD) == 7`.

### ITM-U-42 — an unknown tag id refuses the whole update: fields, links and counts stay
- **Rules:** `update_item` R15 [BUG-944], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-944
- **Fails today on:** Then 1 (no error is raised: the name is written, T1's link removed and the unknown id skipped)

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. L1 = link of I1 to T1.

**When**
- `M.update_item(db, item_id=I1.id, item_data=ItemUpdate(name="Lock Nut", tag_ids=[MISSING]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Item tag 999999999 not found"`.
3. re-read I1: `name == "Bolt M8"`, `updated_by is None`.
4. unchanged: unchanged(L1).
5. re-read: `stored_count(T1) == 4`.

### ITM-U-43 — a deleted tag newly added refuses the whole update
- **Rules:** `update_item` R15 [BUG-943], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-943
- **Fails today on:** Then 1 (no error is raised: TD is linked and counted)

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. TD, but `usage_count 7`.
4. L1 = link of I1 to T1.

**When**
- `M.update_item(db, item_id=I1.id, item_data=ItemUpdate(tag_ids=[T1.id, TD.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == f"Item tag {TD.id} is not active"`.
3. unchanged: unchanged(L1).
4. re-read: `tag_ids_of(I1) == [T1.id]`.
5. re-read: `stored_count(TD) == 7`.
6. re-read: `stored_count(T1) == 4`.

### ITM-U-44 — a user_id that is no profile id fails on flush and the item keeps its name
- **Rules:** `update_item` R16, Errors row 6
- **Kind:** error
- **Expect:** pass

**Given**
1. I1.

**When**
- `M.update_item(db, item_id=I1.id, item_data=ItemUpdate(name="Lock Nut"), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"items_updated_by_fkey" in str(exc.value.orig)`.
4. re-read I1: `name == "Bolt M8"`, `updated_by is None`.

### ITM-U-45 — the update is flushed but not committed: a rollback restores the row, the links and the counts
- **Rules:** `update_item` R17, Returns, Side effects
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. K3.
4. link of I1 to T1.
5. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(name="Lock Nut", tag_ids=[K3.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `name == "Lock Nut"`.
3. re-read: `tag_ids_of(I1) == [K3.id]`.
4. re-read I1 after the savepoint rollback: `name == "Bolt M8"`, `updated_by is None`.
5. re-read after the savepoint rollback: `tag_ids_of(I1) == [T1.id]`.
6. re-read after the savepoint rollback: `stored_count(T1) == 4`, `stored_count(K3) == 0`.
7. mock called: the `db.commit` spy was never called.

### ITM-U-46 — a SKU used by another live item is refused
- **Rules:** `update_item` R18 [BUG-946], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-946
- **Fails today on:** Then 1 (no error is raised: SKUs are not checked)

**Given**
1. I1, but `sku "B-M8"`.
2. I2, but `sku "W-10"`.

**When**
- `M.update_item(db, item_id=I2.id, item_data=ItemUpdate(sku="B-M8"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Item with SKU 'B-M8' already exists"`.
3. re-read I2: `sku == "W-10"`, `updated_by is None`.
4. unchanged: unchanged(I1).

### ITM-U-47 — re-sending the item's own SKU never conflicts
- **Rules:** `update_item` R18
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1, but `sku "B-M8"`.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(sku="B-M8", unit="box"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `sku == "B-M8"`, `unit == "box"`.

### ITM-U-48 — changing only the case of the item's own SKU is stored
- **Rules:** `update_item` R18
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1, but `sku "B-M8"`.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(sku="b-m8"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `sku == "b-m8"`.

### ITM-U-49 — the SKU of a deleted item can be taken by an update
- **Rules:** `update_item` R18
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. IX, but `sku "B-M8"`.
2. I1.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(sku="B-M8"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `sku == "B-M8"`.
3. unchanged: unchanged(IX).

### ITM-U-50 — a SKU of three spaces clears the SKU
- **Rules:** `update_item` R18 [BUG-946]
- **Kind:** bug
- **Expect:** xfail BUG-946
- **Fails today on:** Then 2 (the three spaces are stored)

**Given**
1. I1, but `sku "B-M8"`.

**When**
- `result = M.update_item(db, item_id=I1.id, item_data=ItemUpdate(sku="   "), workspace_id=W1.id, user_id=U2.id)`. The SKU is three spaces.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `sku is None`.

### ITM-U-51 — a rename to the name of another live item is accepted
- **Rules:** `update_item` R19
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.
2. I2.

**When**
- `result = M.update_item(db, item_id=I2.id, item_data=ItemUpdate(name="Bolt M8"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I2` (the very object that was read).
2. re-read I2: `name == "Bolt M8"`, `name_normalized == "bolt m8"`.
3. unchanged: unchanged(I1).

## `ItemManager.get_item`

### ITM-G-01 — a live item of the workspace is returned and nothing is written
- **Rules:** `get_item` R1, R5, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.
2. I2.

**When**
- `result = M.get_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is I1` (the session's instance).
2. nothing written: nothing written.
3. unchanged: unchanged(I1).

### ITM-G-02 — the positional call the services use returns the item
- **Rules:** `get_item` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.

**When**
- `result = M.get_item(db, I1.id, W1.id)` (positional, as `ItemService` calls it).

**Then**
1. returns: `result is I1` (the session's instance).

### ITM-G-03 — an id that no item has gives None
- **Rules:** `get_item` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. I1.

**When**
- `result = M.get_item(db, item_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### ITM-G-04 — an item of another workspace gives None
- **Rules:** `get_item` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I9.

**When**
- `result = M.get_item(db, item_id=I9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(I9).

### ITM-G-05 — a deleted item gives None by default
- **Rules:** `get_item` R3 [BUG-937]
- **Kind:** bug
- **Expect:** xfail BUG-937
- **Fails today on:** Then 1 (the deleted item is returned)

**Given**
1. IX.

**When**
- `result = M.get_item(db, item_id=IX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(IX).

### ITM-G-06 — include_deleted=True returns a deleted item of the workspace
- **Rules:** `get_item` R4 [BUG-937]
- **Kind:** bug
- **Expect:** xfail BUG-937
- **Fails today on:** Then 1 (the call raises TypeError: `get_item` has no `include_deleted` parameter)

**Given**
1. IX.

**When**
- `result = M.get_item(db, item_id=IX.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result is IX` (the session's instance).
2. re-read IX: `is_active is False`.

### ITM-G-07 — include_deleted=True still gives None for another workspace's item
- **Rules:** `get_item` R4 [BUG-937]
- **Kind:** bug
- **Expect:** xfail BUG-937
- **Fails today on:** Then 1 (the call raises TypeError: `get_item` has no `include_deleted` parameter)

**Given**
1. I9, but `is_active False`.

**When**
- `result = M.get_item(db, item_id=I9.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result is None`.

### ITM-G-08 — include_deleted=True returns a live item too
- **Rules:** `get_item` R4 [BUG-937], R1
- **Kind:** bug
- **Expect:** xfail BUG-937
- **Fails today on:** Then 1 (the call raises TypeError: `get_item` has no `include_deleted` parameter)

**Given**
1. I1.

**When**
- `result = M.get_item(db, item_id=I1.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result is I1` (the session's instance).


## `ItemManager.list_items_filtered`

### ITM-L-01 — the default page holds the workspace's live items only
- **Rules:** `list_items_filtered` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.
2. I2.
3. IX.
4. I9.

**When**
- `result = M.list_items_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [I1.id, I2.id]`.
2. nothing written: nothing written.

### ITM-L-02 — the search filter is passed through
- **Rules:** `list_items_filtered` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.
2. I2.

**When**
- `result = M.list_items_filtered(db, workspace_id=W1.id, search="Washer")`.

**Then**
1. returns: `ids(result) == [I2.id]`.

### ITM-L-03 — the unit filter is passed through
- **Rules:** `list_items_filtered` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1. (`unit "pcs"`.)
2. I2, but `unit "kg"`.

**When**
- `result = M.list_items_filtered(db, workspace_id=W1.id, unit="kg")`.

**Then**
1. returns: `ids(result) == [I2.id]`.

### ITM-L-04 — the tag filter is passed through
- **Rules:** `list_items_filtered` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.
2. I2.
3. T1.
4. link of I1 to T1.

**When**
- `result = M.list_items_filtered(db, workspace_id=W1.id, tag_ids=[T1.id])`.

**Then**
1. returns: `ids(result) == [I1.id]`.

### ITM-L-05 — limit is passed through
- **Rules:** `list_items_filtered` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.
2. I2.

**When**
- `result = M.list_items_filtered(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in (I1.id, I2.id)`.

### ITM-L-06 — skip is passed through
- **Rules:** `list_items_filtered` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.
2. I2.

**When**
- `result = M.list_items_filtered(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### ITM-L-07 — the filters after the workspace are keyword-only
- **Rules:** `list_items_filtered` signature (Facts for the test designer)
- **Kind:** error
- **Expect:** pass

**Given**
1. I1.

**When**
- `M.list_items_filtered(db, W1.id, 0)` (the third argument positional).

**Then**
1. raises: `TypeError` (plain `with pytest.raises(TypeError):` around the call).

### ITM-L-08 — a negative limit is refused by the database
- **Rules:** `list_items_filtered` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. I1.

**When**
- `M.list_items_filtered(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. re-read I1: `name == "Bolt M8"`, `is_active is True`.


### ITM-L-09 — without a limit the page holds 100 items
- **Rules:** `list_items_filtered` R1 (default `limit=100`)
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — 101 rows built in a loop; added 2026-10-18 after verification (mutation survivor #36)

**Given**
1. 101 items, `name "Part 000"` … `"Part 100"` (`name_normalized` the same in lower case).

**When**
- `result = M.list_items_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

## `ItemManager.count_items_filtered`

### ITM-N-01 — the count covers the workspace's live items only
- **Rules:** `count_items_filtered` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.
2. I2.
3. IX.
4. I9.

**When**
- `result = M.count_items_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, int)`.
2. returns: `result == 2`.
3. nothing written: nothing written.

### ITM-N-02 — the search filter is passed through to the count
- **Rules:** `count_items_filtered` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.
2. I2.

**When**
- `result = M.count_items_filtered(db, workspace_id=W1.id, search="Washer")`.

**Then**
1. returns: `result == 1`.

### ITM-N-03 — the unit and tag filters are passed through to the count
- **Rules:** `count_items_filtered` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1, but `unit "kg"`.
2. I2, but `unit "kg"`.
3. T1.
4. link of I1 to T1.

**When**
- `result = M.count_items_filtered(db, workspace_id=W1.id, unit="kg", tag_ids=[T1.id])`.

**Then**
1. returns: `result == 1`.


## `ItemManager.distinct_units`

### ITM-UN-01 — the units of the workspace's live items, once each, sorted
- **Rules:** `distinct_units` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1. (`unit "pcs"`.)
2. I2, but `unit "kg"`.
3. IX, but `unit "box"`.
4. I9, but `unit "ton"`.
5. item, `name "Hex Screw"`, `name_normalized "hex screw"`. (`unit "pcs"`.)

**When**
- `result = M.distinct_units(db, W1.id)` (positional, as `ItemService` calls it).

**Then**
1. returns: `result == ["kg", "pcs"]`.
2. nothing written: nothing written.

### ITM-UN-02 — a workspace without items gives an empty list
- **Rules:** `distinct_units` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.

**When**
- `result = M.distinct_units(db, W2.id)`.

**Then**
1. returns: `result == []`.


## `ItemManager.find_similar_items`

### ITM-FS-01 — an exact normalized match comes back as a dict with score 1.0 and type exact
- **Rules:** `find_similar_items` R1, R2, R3, R4, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. item, `name "Steel Rod 22m"`, `name_normalized "steel rod 22m"`, but `unit "m"`, `sku "SR-22"`.

**When**
- `result = M.find_similar_items(db, workspace_id=W1.id, name="steel rod 22 M")`.

**Then**
1. returns: `isinstance(result, list)`, `len(result) == 1`.
2. returns: `set(result[0].keys()) == {"id", "name", "unit", "sku", "similarity_score", "match_type"}`.
3. returns: `result[0]["name"] == "Steel Rod 22m"`, `result[0]["unit"] == "m"`, `result[0]["sku"] == "SR-22"`.
4. returns: `isinstance(result[0]["similarity_score"], float)`, `result[0]["similarity_score"] == 1.0`.
5. returns: `result[0]["match_type"] == "exact_normalized"`.
6. nothing written: nothing written.

### ITM-FS-02 — the id key holds the item's id
- **Rules:** `find_similar_items` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = item, `name "Steel Rod 22m"`, `name_normalized "steel rod 22m"`.

**When**
- `result = M.find_similar_items(db, workspace_id=W1.id, name="Steel Rod 22m")`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["id"] == S1.id`.

### ITM-FS-03 — a fuzzy score of 7/19 is rounded to 4 decimals and typed fuzzy
- **Rules:** `find_similar_items` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = item, `name "Pa"`, `name_normalized "abcdefghijklmnopq"`.

**When**
- `result = M.find_similar_items(db, workspace_id=W1.id, name="abcdefg")`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["id"] == P.id`.
3. returns: `result[0]["similarity_score"] == 0.3684`.
4. returns: `result[0]["match_type"] == "fuzzy"`.

### ITM-FS-04 — a score of 7/20 is included and rounded to 0.35
- **Rules:** `find_similar_items` R3; item DAO `find_similar_by_name_in_workspace` [BUG-034]
- **Kind:** bug
- **Expect:** xfail BUG-034
- **Fails today on:** Then 1 (the DAO compares the float4 score 0.3499999940… with 0.35 and drops the item)

**Given**
1. Q = item, `name "Qa"`, `name_normalized "abcdefghijklmnopqr"`.

**When**
- `result = M.find_similar_items(db, workspace_id=W1.id, name="abcdefg")`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["similarity_score"] == 0.35`.
3. returns: `result[0]["match_type"] == "fuzzy"`.

### ITM-FS-05 — a stale normalized name is judged by the stored value: not equal means fuzzy
- **Rules:** `find_similar_items` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. item, `name "Steel Rod"`, `name_normalized "steel rods"`.

**When**
- `result = M.find_similar_items(db, workspace_id=W1.id, name="Steel Rod")`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["match_type"] == "fuzzy"`.
3. returns: `result[0]["similarity_score"] < 1.0`.

### ITM-FS-06 — the stored name comes back untrimmed
- **Rules:** `find_similar_items` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. item, `name "  Steel Rod 22m "`, `name_normalized "steel rod 22m"`. Two spaces before, one after.

**When**
- `result = M.find_similar_items(db, workspace_id=W1.id, name="Steel Rod 22m")`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["name"] == "  Steel Rod 22m "`.

### ITM-FS-07 — a proposed name shorter than 3 normalized characters gives an empty list
- **Rules:** `find_similar_items` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. item, `name "AB"`, `name_normalized "ab"`.

**When**
- `result = M.find_similar_items(db, workspace_id=W1.id, name="ab")`.

**Then**
1. returns: `result == []`.

### ITM-FS-08 — the excluded item is left out
- **Rules:** `find_similar_items` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.

**When**
- `result = M.find_similar_items(db, workspace_id=W1.id, name="Bolt M8", exclude_item_id=I1.id)`.

**Then**
1. returns: `result == []`.

### ITM-FS-09 — deleted items and items of another workspace are not matched
- **Rules:** `find_similar_items` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. IX, but `name "Bolt M8"`, `name_normalized "bolt m8"`.
2. I9, but `name "Bolt M8"`, `name_normalized "bolt m8"`.

**When**
- `result = M.find_similar_items(db, workspace_id=W1.id, name="Bolt M8")`.

**Then**
1. returns: `result == []`.

### ITM-FS-10 — limit 0 gives an empty list
- **Rules:** `find_similar_items` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.

**When**
- `result = M.find_similar_items(db, workspace_id=W1.id, name="Bolt M8", limit=0)`.

**Then**
1. returns: `result == []`.

### ITM-FS-11 — a negative limit is refused by the database
- **Rules:** `find_similar_items` R1, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. I1.

**When**
- `M.find_similar_items(db, workspace_id=W1.id, name="Bolt M8", limit=-1)`.

**Then**
1. raises: `DataError`.
2. re-read I1: `name == "Bolt M8"`.

### ITM-FS-12 — without a limit at most 5 matches come back
- **Rules:** `find_similar_items` R1 (default `limit=5`)
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — 6 rows built in a loop; added 2026-10-18 after verification (mutation survivor #37)

**Given**
1. 6 items, each `name "Bolt M8"`, `name_normalized "bolt m8"`.

**When**
- `result = M.find_similar_items(db, workspace_id=W1.id, name="Bolt M8")`.

**Then**
1. returns: `len(result) == 5`.

## `ItemManager.delete_item`

### ITM-D-01 — a live item is marked deleted by the acting user
- **Rules:** `delete_item` R4, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`.
3. re-read I1: `updated_by == U2.id`.
4. re-read I1: `updated_at is not None`.
5. count: `items` has exactly 1 row.

### ITM-D-02 — no other column of the item is changed by the delete
- **Rules:** `delete_item` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I1, but `description "Zinc plated"`, `sku "B-M8"`, `item_type "service"`.
2. `created_before = I1.created_at`

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `name == "Bolt M8"`, `name_normalized == "bolt m8"`, `unit == "pcs"`.
3. re-read I1: `description == "Zinc plated"`, `sku == "B-M8"`, `item_type == "service"`.
4. re-read I1: `workspace_id == W1.id`, `created_by == U1.id`.
5. re-read I1: `created_at == created_before`.

### ITM-D-03 — an id that no item has is refused and nothing is written
- **Rules:** `delete_item` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. I1.

**When**
- `M.delete_item(db, item_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Item 999999999 not found"`.
3. nothing written: nothing written.
4. unchanged: unchanged(I1).

### ITM-D-04 — an item of another workspace is refused and stays live
- **Rules:** `delete_item` R2 (the side that holds today)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I9.

**When**
- `M.delete_item(db, item_id=I9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. unchanged: unchanged(I9).
3. re-read I9: `is_active is True`, `updated_by is None`.

### ITM-D-05 — an item of another workspace gets the same message as a missing one
- **Rules:** `delete_item` R2 [BUG-941], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-941
- **Fails today on:** Then 2 (the message says the item does not belong to the workspace)

**Given**
1. I9.

**When**
- `M.delete_item(db, item_id=I9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == f"Item {I9.id} not found"`.
3. unchanged: unchanged(I9).

### ITM-D-06 — an already deleted item is refused; its tag count and stamp stay
- **Rules:** `delete_item` R3, Errors row 3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. IX.
2. T1, but `usage_count 3`.
3. link of IX to T1.

**When**
- `M.delete_item(db, item_id=IX.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == f"Item {IX.id} is already deleted"`.
3. re-read: `stored_count(T1) == 3`.
4. unchanged: unchanged(IX).
5. re-read IX: `updated_by is None`.

### ITM-D-07 — the item's tag links are kept, unchanged
- **Rules:** `delete_item` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. T2, but `usage_count 6`.
4. L1 = link of I1 to T1.
5. L2 = link of I1 to T2.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. unchanged: unchanged(L1).
3. unchanged: unchanged(L2).
4. re-read: `tag_ids_of(I1) == [T1.id, T2.id]`.

### ITM-D-08 — each active tag on the item counts one item less, never below 0
- **Rules:** `delete_item` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. T2. (`usage_count 0`.)
4. link of I1 to T1.
5. link of I1 to T2.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read: `stored_count(T1) == 3`.
3. re-read: `stored_count(T2) == 0`.

### ITM-D-09 — a deleted tag on the item also counts one item less
- **Rules:** `delete_item` R7 [BUG-945]
- **Kind:** bug
- **Expect:** xfail BUG-945
- **Fails today on:** Then 2 (only active tags are lowered; TD stays at 9)

**Given**
1. I1.
2. TD, but `usage_count 9`.
3. link of I1 to TD.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read: `stored_count(TD) == 8`.
3. re-read: `tag_ids_of(I1) == [TD.id]`.

### ITM-D-10 — an item without links is deleted and no count changes
- **Rules:** `delete_item` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.
2. T1, but `usage_count 3`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`.
3. re-read: `stored_count(T1) == 3`.

### ITM-D-11 — a user_id that is no profile id fails on flush; the item stays live and no count changes
- **Rules:** `delete_item` R10, Errors row 6
- **Kind:** error
- **Expect:** pass

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. link of I1 to T1.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"items_updated_by_fkey" in str(exc.value.orig)`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. re-read: `stored_count(T1) == 4`.

### ITM-D-12 — the delete is flushed but not committed: a rollback makes the item live again and restores the count
- **Rules:** `delete_item` R11, Returns
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. link of I1 to T1.
4. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`.
3. re-read: `stored_count(T1) == 3`.
4. re-read I1 after the savepoint rollback: `is_active is True`, `updated_by is None`.
5. re-read after the savepoint rollback: `stored_count(T1) == 4`.
6. mock called: the `db.commit` spy was never called.

### ITM-D-13 — after the delete the item leaves the catalog list and count, and a second delete is refused
- **Rules:** `delete_item` R12, R3; `list_items_filtered` R1; `count_items_filtered` R1
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — follow-up manager calls after the When call, one of them expected to raise

**Given**
1. I1.
2. I2.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. returns: after the call, `ids(M.list_items_filtered(db, workspace_id=W1.id)) == [I2.id]`.
3. returns: after the call, `M.count_items_filtered(db, workspace_id=W1.id) == 1`.
4. raises: after that, `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)` raises `ValueError` with `str(exc.value) == f"Item {I1.id} is already deleted"`.

### ITM-D-14 — stock in a factory blocks the delete and nothing is written
- **Rules:** `delete_item` R9 (a) [BUG-948], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: stock is not looked at and the item is deleted)

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. link of I1 to T1.
4. F1.
5. SK = stock of I1, `qty 400`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. re-read I1: `is_active is True`, `updated_by is None`.
4. re-read I1: `updated_at is None`.
5. re-read: `stored_count(T1) == 4`.
6. unchanged: unchanged(SK).
7. nothing written: nothing written.

### ITM-D-15 — damaged stock in a factory also blocks the delete
- **Rules:** `delete_item` R9 (a) [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: stock is not looked at and the item is deleted)

**Given**
1. I1.
2. F1.
3. SK = stock of I1, `qty 3`, but `inventory_type InventoryTypeEnum.DAMAGED`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. re-read I1: `is_active is True`, `updated_by is None`.
4. unchanged: unchanged(SK).

### ITM-D-16 — a negative stock quantity also blocks the delete
- **Rules:** `delete_item` R9 (a) [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: stock is not looked at and the item is deleted)

**Given**
1. I1.
2. F1.
3. SK = stock of I1, `qty -2`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. re-read I1: `is_active is True`, `updated_by is None`.
4. unchanged: unchanged(SK).

### ITM-D-17 — stock on a machine blocks the delete
- **Rules:** `delete_item` R9 (b) [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: machine stock is not looked at and the item is deleted)

**Given**
1. I1.
2. F1.
3. MC1.
4. MS = machine stock of I1, `qty 5`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. re-read I1: `is_active is True`, `updated_by is None`.
4. unchanged: unchanged(MS).

### ITM-D-18 — a line on a purchase order at stage "Draft" blocks the delete
- **Rules:** `delete_item` R9 (c) [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)

**Given**
1. I1.
2. F1.
3. ST = stage "Draft".
4. PO = purchase order, `current_status_id ST.id`.
5. POL = PO line of I1.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. re-read I1: `is_active is True`, `updated_by is None`.
4. unchanged: unchanged(POL).

### ITM-D-19 — a line on a purchase order at stage "Planning" blocks the delete
- **Rules:** `delete_item` R9 (c) [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)

**Given**
1. I1.
2. F1.
3. ST = stage "Planning".
4. PO = purchase order, `current_status_id ST.id`.
5. POL = PO line of I1.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. re-read I1: `is_active is True`, `updated_by is None`.
4. unchanged: unchanged(POL).

### ITM-D-20 — a line on a purchase order at stage "Receiving" blocks the delete
- **Rules:** `delete_item` R9 (c) [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)

**Given**
1. I1.
2. F1.
3. ST = stage "Receiving".
4. PO = purchase order, `current_status_id ST.id`.
5. POL = PO line of I1.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. re-read I1: `is_active is True`, `updated_by is None`.
4. unchanged: unchanged(PO).
5. unchanged: unchanged(POL).

### ITM-D-21 — a line on a work order in status DRAFT blocks the delete
- **Rules:** `delete_item` R9 (e) [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)

**Given**
1. I1.
2. F1.
3. WT1.
4. WO = work order, `status "DRAFT"`.
5. WOL = WO line of I1.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. re-read I1: `is_active is True`, `updated_by is None`.
4. unchanged: unchanged(WOL).

### ITM-D-22 — a line on a work order in status IN_PROGRESS blocks the delete
- **Rules:** `delete_item` R9 (e) [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)

**Given**
1. I1.
2. F1.
3. WT1.
4. WO = work order, `status "IN_PROGRESS"`.
5. WOL = WO line of I1.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. re-read I1: `is_active is True`, `updated_by is None`.
4. unchanged: unchanged(WO).
5. unchanged: unchanged(WOL).

### ITM-D-23 — being the replaced item of a line on an open work order blocks the delete
- **Rules:** `delete_item` R9 (e) [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)

**Given**
1. I1.
2. I2.
3. F1.
4. WT1.
5. WO = work order, `status "IN_PROGRESS"`.
6. WOL = WO line of I2, but `replaced_item_id I1.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. re-read I1: `is_active is True`, `updated_by is None`.
4. unchanged: unchanged(WOL).

### ITM-D-24 — a line on a transfer order that is not completed blocks the delete
- **Rules:** `delete_item` R9 (f) [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)

**Given**
1. I1.
2. F1.
3. ST = stage "Open".
4. TO = transfer order, `current_status_id ST.id`. (`completed_at None`.)
5. TOL = TO line of I1.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. re-read I1: `is_active is True`, `updated_by is None`.
4. unchanged: unchanged(TOL).

### ITM-D-25 — a factory stock row with quantity 0 does not block the delete
- **Rules:** `delete_item` R9 (a), R9a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.
2. F1.
3. SK = stock of I1, `qty 0`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(SK).

### ITM-D-26 — a soft-deleted factory stock row does not block the delete, whatever its quantity
- **Rules:** `delete_item` R9 (a), R9a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. I1.
2. F1.
3. SK = stock of I1, `qty 400`, but `is_deleted True`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(SK).

### ITM-D-27 — machine stock with quantity 0 does not block the delete, whatever the required and defective quantities
- **Rules:** `delete_item` R9 (b), R9a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.
2. F1.
3. MC1.
4. MS = machine stock of I1, `qty 0`, but `req_qty 10`, `defective_qty 2`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(MS).

### ITM-D-28 — a line on a purchase order at stage "Complete" does not block the delete
- **Rules:** `delete_item` R9 (c), R9a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.
2. F1.
3. ST = stage "Complete".
4. PO = purchase order, `current_status_id ST.id`.
5. POL = PO line of I1.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(POL).

### ITM-D-29 — a line on a voided purchase order does not block the delete, even at stage "Receiving"
- **Rules:** `delete_item` R9 (c), R9a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.
2. F1.
3. ST = stage "Receiving".
4. PO = purchase order, `current_status_id ST.id`, but `voided True`.
5. POL = PO line of I1.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(PO).
4. unchanged: unchanged(POL).

### ITM-D-30 — a line on a completed sales order does not block the delete
- **Rules:** `delete_item` R9 (d), R9a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.
2. F1.
3. AC1.
4. ST = stage "Open".
5. SO = sales order, `current_status_id ST.id`, but `order_completed True`.
6. SOL = SO line of I1.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(SOL).

### ITM-D-31 — a line on a COMPLETED work order does not block the delete
- **Rules:** `delete_item` R9 (e), R9a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.
2. F1.
3. WT1.
4. WO = work order, `status "COMPLETED"`.
5. WOL = WO line of I1.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(WOL).

### ITM-D-32 — a line on a VOIDED work order does not block the delete
- **Rules:** `delete_item` R9 (e), R9a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.
2. F1.
3. WT1.
4. WO = work order, `status "VOIDED"`.
5. WOL = WO line of I1.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(WOL).

### ITM-D-33 — a line on a soft-deleted DRAFT work order does not block the delete
- **Rules:** `delete_item` R9 (e), R9a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. I1.
2. F1.
3. WT1.
4. WO = work order, `status "DRAFT"`, but `is_deleted True`.
5. WOL = WO line of I1.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(WO).
4. unchanged: unchanged(WOL).

### ITM-D-34 — a removed line on a DRAFT work order does not block the delete
- **Rules:** `delete_item` R9 (e), R9a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. I1.
2. F1.
3. WT1.
4. WO = work order, `status "DRAFT"`.
5. WOL = WO line of I1, but `is_deleted True`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(WOL).

### ITM-D-35 — a line on a completed transfer order does not block the delete
- **Rules:** `delete_item` R9 (f), R9a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.
2. F1.
3. ST = stage "Open".
4. TO = transfer order, `current_status_id ST.id`, but `completed_at T0`.
5. TOL = TO line of I1.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(TO).
4. unchanged: unchanged(TOL).

### ITM-D-36 — an already deleted item with stock gets the "already deleted" message
- **Rules:** `delete_item` R9 (checked after R3), R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. IX.
2. F1.
3. SK = stock of IX, `qty 5`.

**When**
- `M.delete_item(db, item_id=IX.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == f"Item {IX.id} is already deleted"`.
3. unchanged: unchanged(IX).
4. unchanged: unchanged(SK).

### ITM-D-37 — stock of another item does not block the delete
- **Rules:** `delete_item` R9 (a), R9a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I1.
2. I2.
3. F1.
4. SK = stock of I2, `qty 400`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(I2).
4. unchanged: unchanged(SK).

### ITM-D-38 — an open purchase order line of another item does not block the delete
- **Rules:** `delete_item` R9 (c), R9a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I1.
2. I2.
3. F1.
4. ST = stage "Draft".
5. PO = purchase order, `current_status_id ST.id`.
6. POL = PO line of I2.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(POL).

### ITM-D-39 — a line on a sales order that is not completed blocks the delete and names the order
- **Rules:** `delete_item` R9 (d) [BUG-948], R9b [BUG-948], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. link of I1 to T1.
4. F1.
5. AC1.
6. ST = stage "Open".
7. SO = sales order, `current_status_id ST.id`. (`order_completed False`.)
8. SOL = SO line of I1.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "sales_order", "id": SO.id}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. re-read I1: `updated_at is None`.
6. re-read: `stored_count(T1) == 4`.
7. unchanged: unchanged(SO).
8. unchanged: unchanged(SOL).
9. nothing written: nothing written.

### ITM-D-40 — the refusal for factory stock lists exactly that stock row
- **Rules:** `delete_item` R9b [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: stock is not looked at and the item is deleted)

**Given**
1. I1.
2. F1.
3. SK = stock of I1, `qty 400`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 2`.
3. raises: `exc.value.args[1] == [{"type": "factory_stock", "id": SK.id}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.

### ITM-D-41 — the refusal for machine stock lists exactly that machine row
- **Rules:** `delete_item` R9b [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: machine stock is not looked at and the item is deleted)

**Given**
1. I1.
2. F1.
3. MC1.
4. MS = machine stock of I1, `qty 5`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[1] == [{"type": "machine_stock", "id": MS.id}]`.
3. re-read I1: `is_active is True`, `updated_by is None`.

### ITM-D-42 — the refusal for an open purchase order lists the order, not the line
- **Rules:** `delete_item` R9b [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)

**Given**
1. I1.
2. F1.
3. ST = stage "Receiving".
4. PO = purchase order, `current_status_id ST.id`.
5. POL = PO line of I1.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[1] == [{"type": "purchase_order", "id": PO.id}]`.
3. re-read I1: `is_active is True`, `updated_by is None`.

### ITM-D-43 — the refusal for an open work order lists the order, not the line
- **Rules:** `delete_item` R9b [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)

**Given**
1. I1.
2. F1.
3. WT1.
4. WO = work order, `status "IN_PROGRESS"`.
5. WOL = WO line of I1.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[1] == [{"type": "work_order", "id": WO.id}]`.
3. re-read I1: `is_active is True`, `updated_by is None`.

### ITM-D-44 — the refusal for an open transfer order lists the order, not the line
- **Rules:** `delete_item` R9b [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)

**Given**
1. I1.
2. F1.
3. ST = stage "Open".
4. TO = transfer order, `current_status_id ST.id`. (`completed_at None`.)
5. TOL = TO line of I1.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO.id}]`.
3. re-read I1: `is_active is True`, `updated_by is None`.

### ITM-D-45 — two blockers of different types are both listed, factory stock before transfer order
- **Rules:** `delete_item` R9b [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: stock and orders are not looked at and the item is deleted)

**Given**
1. I1.
2. F1.
3. ST = stage "Open".
4. TO = transfer order, `current_status_id ST.id`. (`completed_at None`.)
5. TOL = TO line of I1.
6. SK = stock of I1, `qty 400`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "factory_stock", "id": SK.id}, {"type": "transfer_order", "id": TO.id}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(SK).
6. unchanged: unchanged(TOL).

### ITM-D-46 — a purchase order with two lines of the item is listed once
- **Rules:** `delete_item` R9b [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)

**Given**
1. I1.
2. F1.
3. ST = stage "Draft".
4. PO = purchase order, `current_status_id ST.id`.
5. POL1 = PO line of I1.
6. POL2 = PO line of I1, but `line_number 2`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[1] == [{"type": "purchase_order", "id": PO.id}]`.
3. re-read I1: `is_active is True`, `updated_by is None`.
4. unchanged: unchanged(POL1).
5. unchanged: unchanged(POL2).

### ITM-D-47 — two blocking stock rows in one factory are two entries, by id
- **Rules:** `delete_item` R9b [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: stock is not looked at and the item is deleted)

**Given**
1. I1.
2. F1.
3. SK1 = stock of I1, `qty 400`.
4. SK2 = stock of I1, `qty 3`, but `inventory_type InventoryTypeEnum.DAMAGED`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[1] == [{"type": "factory_stock", "id": SK1.id}, {"type": "factory_stock", "id": SK2.id}]`.
3. re-read I1: `is_active is True`, `updated_by is None`.
4. unchanged: unchanged(SK1).
5. unchanged: unchanged(SK2).

### ITM-D-48 — an item in use deleted by an unknown user gets the refusal with its blockers, not a database error
- **Rules:** `delete_item` R10a [BUG-948], R9b [BUG-948], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (the call raises IntegrityError: stock is not looked at, so the flush fails on `items_updated_by_fkey`)
- **Author:** claude — the call fails on flush today and must have no savepoint around it: the checks after it also prove the transaction stays usable (R10a)

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. link of I1 to T1.
4. F1.
5. SK = stock of I1, `qty 400`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=MISSING)`, in a plain `with pytest.raises(ValueError) as exc:`, no `db.begin_nested()`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "factory_stock", "id": SK.id}]`.
4. returns: `I1 not in db.dirty` (checked before any re-read: `expire_all()` would throw a pending change away).
5. returns: `db.flush() is None` (the flush runs with no error, before any re-read).
6. re-read I1: `is_active is True`, `updated_by is None`.
7. re-read I1: `updated_at is None`.
8. re-read: `stored_count(T1) == 4`.
9. unchanged: unchanged(SK).
10. nothing written: nothing written.

### ITM-D-49 — factory stock of another workspace blocks the delete, shown only as the generic entry
- **Rules:** `delete_item` R9 (a) [BUG-948], R9 intro: cross-workspace row [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: stock is not looked at and the item is deleted)
- **Author:** claude — rows of W2, outside the helper sheet

**Given**
1. I1.
2. F9.
3. SK = stock of I1, `qty 400`, but `workspace_id W2.id`, `factory_id F9.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(SK).

### ITM-D-50 — machine stock of another workspace blocks the delete, shown only as the generic entry
- **Rules:** `delete_item` R9 (b) [BUG-948], R9 intro: cross-workspace row [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: machine stock is not looked at and the item is deleted)
- **Author:** claude — rows of W2, outside the helper sheet

**Given**
1. I1.
2. F9.
3. MC9.
4. MS = machine stock of I1, `qty 5`, but `workspace_id W2.id`, `machine_id MC9.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(MS).

### ITM-D-51 — an open purchase order of another workspace blocks the delete, shown only as the generic entry
- **Rules:** `delete_item` R9 (c) [BUG-948], R9 intro: cross-workspace row [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)
- **Author:** claude — rows of W2, outside the helper sheet

**Given**
1. I1.
2. F9.
3. ST9 = stage "Receiving", but `workspace_id W2.id`.
4. PO = purchase order, `current_status_id ST9.id`, but `workspace_id W2.id`, `destination_id F9.id`.
5. POL = PO line of I1, but `workspace_id W2.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(POL).

### ITM-D-52 — a sales order of another workspace that is not completed blocks the delete, shown only as the generic entry
- **Rules:** `delete_item` R9 (d) [BUG-948], R9 intro: cross-workspace row [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)
- **Author:** claude — rows of W2, outside the helper sheet

**Given**
1. I1.
2. F9.
3. AC9.
4. ST9 = stage "Open", but `workspace_id W2.id`.
5. SO = sales order, `current_status_id ST9.id`, but `workspace_id W2.id`, `account_id AC9.id`, `factory_id F9.id`. (`order_completed False`.)
6. SOL = SO line of I1, but `workspace_id W2.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(SOL).

### ITM-D-53 — an open work order of another workspace blocks the delete, shown only as the generic entry
- **Rules:** `delete_item` R9 (e) [BUG-948], R9 intro: cross-workspace row [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)
- **Author:** claude — rows of W2, outside the helper sheet

**Given**
1. I1.
2. F9.
3. WT9.
4. WO = work order, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
5. WOL = WO line of I1, but `workspace_id W2.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(WOL).

### ITM-D-54 — a transfer order of another workspace that is not completed blocks the delete, shown only as the generic entry
- **Rules:** `delete_item` R9 (f) [BUG-948], R9 intro: cross-workspace row [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)
- **Author:** claude — rows of W2, outside the helper sheet

**Given**
1. I1.
2. F9.
3. ST9 = stage "Open", but `workspace_id W2.id`.
4. TO = transfer order, `current_status_id ST9.id`, but `workspace_id W2.id`, `source_location_id F9.id`, `destination_location_id F9.id`. (`completed_at None`.)
5. TOL = TO line of I1, but `workspace_id W2.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(TOL).

### ITM-D-55 — a purchase order of another workspace at its own stage "Complete" does not block the delete
- **Rules:** `delete_item` R9 (c), R9 intro: cross-workspace row, not blocking, R9a
- **Kind:** isolation
- **Expect:** pass
- **Author:** claude — rows of W2, outside the helper sheet

**Given**
1. I1.
2. F9.
3. ST9 = stage "Complete", but `workspace_id W2.id`.
4. PO = purchase order, `current_status_id ST9.id`, but `workspace_id W2.id`, `destination_id F9.id`.
5. POL = PO line of I1, but `workspace_id W2.id`.
6. W1 has no stage named "Complete".

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(PO).
4. unchanged: unchanged(POL).

### ITM-D-56 — normal blockers come first, by type and id; blockers of another workspace are one generic entry, last
- **Rules:** `delete_item` R9b [BUG-948], R9 intro: cross-workspace row [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: stock and orders are not looked at and the item is deleted)
- **Author:** claude — rows of W2, outside the helper sheet

**Given**
1. I1.
2. F1.
3. F9.
4. SK9 = stock of I1, `qty 7`, but `workspace_id W2.id`, `factory_id F9.id`. (Built first, so it has the lower stock id.)
5. SK1 = stock of I1, `qty 400`.
6. ST9 = stage "Open", but `workspace_id W2.id`.
7. TO9 = transfer order, `current_status_id ST9.id`, but `workspace_id W2.id`, `source_location_id F9.id`, `destination_location_id F9.id`. (`completed_at None`.)
8. TOL9 = TO line of I1, but `workspace_id W2.id`.
9. WT1.
10. WO = work order, `status "DRAFT"`.
11. WOL = WO line of I1.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "factory_stock", "id": SK1.id}, {"type": "work_order", "id": WO.id}, {"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(SK9).
6. unchanged: unchanged(SK1).

### ITM-D-57 — an inventory ledger row does not block the delete and stays unchanged
- **Rules:** `delete_item` R9a
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — row of an R9a table, outside the helper sheet

**Given**
1. I1.
2. F1.
3. LG = `inventory_ledger` row (R9a row), `InventoryLedger` from `app.models.inventory_ledger`: `workspace_id W1.id`, `inventory_type InventoryTypeEnum.STORAGE`, `factory_id F1.id`, `item_id I1.id`, `transaction_type "manual_add"`, `quantity 400`, `qty_before 0`, `qty_after 400`.
4. I1 has no `inventory` row.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(LG).

### ITM-D-58 — a machine item ledger row does not block the delete and stays unchanged
- **Rules:** `delete_item` R9a
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — row of an R9a table, outside the helper sheet

**Given**
1. I1.
2. F1.
3. MC1.
4. LG = `machine_item_ledger` row (R9a row), `MachineItemLedger` from `app.models.machine_item_ledger`: `workspace_id W1.id`, `machine_id MC1.id`, `item_id I1.id`, `transaction_type "manual_add"`, `quantity 5`, `unit_cost 10`, `total_cost 50`, `qty_before 0`, `qty_after 5`, `source_type "manual"`, `performed_by U1.id`.
5. I1 has no `machine_items` row.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(LG).

### ITM-D-59 — a pending purchase return line on a completed purchase order does not block the delete and stays unchanged
- **Rules:** `delete_item` R9a
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — rows of R9a tables, outside the helper sheet

**Given**
1. I1.
2. F1.
3. ST = stage "Complete".
4. PO = purchase order, `current_status_id ST.id`. (The order is one that does not block, so that only the return is under test.)
5. POL = PO line of I1.
6. RT = `purchase_order_returns` row (R9a row), `PurchaseOrderReturn` from `app.models.purchase_order_return`: `workspace_id W1.id`, `purchase_order_id PO.id`, `return_number "PR-ITM-1"`, `created_by U1.id`, `status "pending"`.
7. RL = `purchase_order_return_items` row (R9a row), `PurchaseOrderReturnItem` from `app.models.purchase_order_return`: `workspace_id W1.id`, `return_id RT.id`, `po_item_id POL.id`, `item_id I1.id`, `quantity_returned 2`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(RL).
4. unchanged: unchanged(RT).
5. unchanged: unchanged(POL).

### ITM-D-60 — a pending sales return line on a completed sales order does not block the delete and stays unchanged
- **Rules:** `delete_item` R9a
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — rows of R9a tables, outside the helper sheet

**Given**
1. I1.
2. F1.
3. AC1.
4. ST = stage "Open".
5. SO = sales order, `current_status_id ST.id`, but `order_completed True`. (The order is one that does not block, so that only the return is under test.)
6. SOL = SO line of I1.
7. RT = `sales_order_returns` row (R9a row), `SalesOrderReturn` from `app.models.sales_order_return`: `workspace_id W1.id`, `sales_order_id SO.id`, `return_number "SR-ITM-1"`, `created_by U1.id`, `status "pending"`.
8. RL = `sales_order_return_items` row (R9a row), `SalesOrderReturnItem` from `app.models.sales_order_return`: `workspace_id W1.id`, `return_id RT.id`, `so_item_id SOL.id`, `item_id I1.id`, `quantity_returned 2`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(RL).
4. unchanged: unchanged(RT).
5. unchanged: unchanged(SOL).

### ITM-D-61 — a work-order template line of the item does not block the delete and stays unchanged
- **Rules:** `delete_item` R9a
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — rows of R9a tables, outside the helper sheet

**Given**
1. I1.
2. WT1.
3. TP = `work_order_templates` row (R9a row), `WorkOrderTemplate` from `app.models.work_order_template`: `workspace_id W1.id`, `template_name "Press service"`, `work_order_type_id WT1.id`.
4. TL = `work_order_template_items` row (R9a row), `WorkOrderTemplateItem` from `app.models.work_order_template_item`: `workspace_id W1.id`, `work_order_template_id TP.id`, `item_id I1.id`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(TL).

### ITM-D-62 — being the replaced item of a work-order template line does not block the delete, and the line stays unchanged
- **Rules:** `delete_item` R9a
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — rows of R9a tables, outside the helper sheet

**Given**
1. I1.
2. I2.
3. WT1.
4. TP = `work_order_templates` row (R9a row), `WorkOrderTemplate` from `app.models.work_order_template`: `workspace_id W1.id`, `template_name "Press service"`, `work_order_type_id WT1.id`.
5. TL = `work_order_template_items` row (R9a row), `WorkOrderTemplateItem` from `app.models.work_order_template_item`: `workspace_id W1.id`, `work_order_template_id TP.id`, `item_id I2.id`, `replaced_item_id I1.id`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(TL).
4. unchanged: unchanged(I2).

### ITM-D-63 — a production formula line of the item does not block the delete and stays unchanged
- **Rules:** `delete_item` R9a
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — rows of R9a tables, outside the helper sheet

**Given**
1. I1.
2. FM = `production_formulas` row (R9a row), `ProductionFormula` from `app.models.production_formula`: `workspace_id W1.id`, `formula_code "FM-ITM-1"`, `name "Zinc mix"`.
3. FL = `production_formula_items` row (R9a row), `ProductionFormulaItem` from `app.models.production_formula_item`: `workspace_id W1.id`, `formula_id FM.id`, `item_id I1.id`, `item_role "input"`, `quantity 3`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(FL).

### ITM-D-64 — being the expected output of a production formula stage does not block the delete, and the stage stays unchanged
- **Rules:** `delete_item` R9a
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — rows of R9a tables, outside the helper sheet

**Given**
1. I1.
2. FM = `production_formulas` row (R9a row), `ProductionFormula` from `app.models.production_formula`: `workspace_id W1.id`, `formula_code "FM-ITM-1"`, `name "Zinc mix"`.
3. FS = `production_formula_stages` row (R9a row), `ProductionFormulaStage` from `app.models.production_formula_stage`: `workspace_id W1.id`, `formula_id FM.id`, `stage_order 1`, `name "Blend"`, `expected_output_item_id I1.id`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(FS).

### ITM-D-65 — a project component item row does not block the delete and stays unchanged
- **Rules:** `delete_item` R9a
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — rows of R9a tables, outside the helper sheet

**Given**
1. I1.
2. F1.
3. PJ = `projects` row (R9a row), `Project` from `app.models.project`: `workspace_id W1.id`, `factory_id F1.id`, `name "Line upgrade"`, `description "New press line"`.
4. PC = `project_components` row (R9a row), `ProjectComponent` from `app.models.project_component`: `workspace_id W1.id`, `project_id PJ.id`, `name "Frame"`.
5. PI = `project_component_items` row (R9a row), `ProjectComponentItem` from `app.models.project_component_item`: `workspace_id W1.id`, `project_component_id PC.id`, `item_id I1.id`, `qty 12`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(PI).

### ITM-D-66 — finished-goods stock blocks the delete, is listed, and nothing is written
- **Rules:** `delete_item` R9 (g) [BUG-948], R9b [BUG-948], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: finished-goods stock is not looked at and the item is deleted)
- **Author:** claude — `products` row, outside the helper sheet

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. link of I1 to T1.
4. F1.
5. PR = finished stock of I1, `qty 7`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "product_stock", "id": PR.id}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. re-read I1: `updated_at is None`.
6. re-read: `stored_count(T1) == 4`.
7. unchanged: unchanged(PR).
8. nothing written: nothing written.

### ITM-D-67 — a negative finished-goods quantity also blocks the delete
- **Rules:** `delete_item` R9 (g) [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: finished-goods stock is not looked at and the item is deleted)
- **Author:** claude — `products` row, outside the helper sheet

**Given**
1. I1.
2. F1.
3. PR = finished stock of I1, `qty -3`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[1] == [{"type": "product_stock", "id": PR.id}]`.
3. re-read I1: `is_active is True`, `updated_by is None`.
4. unchanged: unchanged(PR).

### ITM-D-68 — finished-goods stock blocks the delete even when the products row is inactive
- **Rules:** `delete_item` R9 (g) [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: finished-goods stock is not looked at and the item is deleted)
- **Author:** claude — `products` row, outside the helper sheet

**Given**
1. I1.
2. F1.
3. PR = finished stock of I1, `qty 7`, but `is_active False`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[1] == [{"type": "product_stock", "id": PR.id}]`.
3. re-read I1: `is_active is True`, `updated_by is None`.
4. unchanged: unchanged(PR).

### ITM-D-69 — finished-goods stock of another workspace blocks the delete, shown only as the generic entry
- **Rules:** `delete_item` R9 (g) [BUG-948], R9 intro: cross-workspace row [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: finished-goods stock is not looked at and the item is deleted)
- **Author:** claude — rows of W2, outside the helper sheet

**Given**
1. I1.
2. F9.
3. PR = finished stock of I1, `qty 7`, but `workspace_id W2.id`, `factory_id F9.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(PR).

### ITM-D-70 — two blocking products rows in one factory are two entries, by id
- **Rules:** `delete_item` R9 (g) [BUG-948], R9b [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: finished-goods stock is not looked at and the item is deleted)
- **Author:** claude — `products` rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. PR1 = finished stock of I1, `qty 7`.
4. PR2 = finished stock of I1, `qty 2`, but `is_available_for_sale True`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[1] == [{"type": "product_stock", "id": PR1.id}, {"type": "product_stock", "id": PR2.id}]`.
3. re-read I1: `is_active is True`, `updated_by is None`.
4. unchanged: unchanged(PR1).
5. unchanged: unchanged(PR2).

### ITM-D-71 — a line on a draft production batch blocks the delete, names the batch, and nothing is written
- **Rules:** `delete_item` R9 (h) [BUG-948], R9b [BUG-948], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: production batches are not looked at and the item is deleted)
- **Author:** claude — batch rows, outside the helper sheet

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. link of I1 to T1.
4. F1.
5. PL1.
6. BT = batch, `status "draft"`.
7. BL = batch line of I1.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "production_batch", "id": BT.id}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. re-read I1: `updated_at is None`.
6. re-read: `stored_count(T1) == 4`.
7. unchanged: unchanged(BT).
8. unchanged: unchanged(BL).
9. nothing written: nothing written.

### ITM-D-72 — an output line on an in-progress production batch blocks the delete
- **Rules:** `delete_item` R9 (h) [BUG-948], R9b [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: production batches are not looked at and the item is deleted)
- **Author:** claude — batch rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. PL1.
4. BT = batch, `status "in_progress"`.
5. BL = batch line of I1, but `item_role "output"`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[1] == [{"type": "production_batch", "id": BT.id}]`.
3. re-read I1: `is_active is True`, `updated_by is None`.
4. unchanged: unchanged(BL).

### ITM-D-73 — an open production batch of another workspace blocks the delete, shown only as the generic entry
- **Rules:** `delete_item` R9 (h) [BUG-948], R9 intro: cross-workspace row [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: production batches are not looked at and the item is deleted)
- **Author:** claude — rows of W2, outside the helper sheet

**Given**
1. I1.
2. F9.
3. PL9.
4. BT = batch, `status "in_progress"`, but `workspace_id W2.id`, `production_line_id PL9.id`.
5. BL = batch line of I1, but `workspace_id W2.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(BL).

### ITM-D-74 — a production batch with two lines of the item is listed once
- **Rules:** `delete_item` R9b [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: production batches are not looked at and the item is deleted)
- **Author:** claude — batch rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. PL1.
4. BT = batch, `status "draft"`.
5. BL1 = batch line of I1.
6. BL2 = batch line of I1, but `item_role "output"`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[1] == [{"type": "production_batch", "id": BT.id}]`.
3. re-read I1: `is_active is True`, `updated_by is None`.
4. unchanged: unchanged(BL1).
5. unchanged: unchanged(BL2).

### ITM-D-75 — transfer order, finished-goods stock and production batches are sorted in that order, batches by id
- **Rules:** `delete_item` R9b [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders, finished-goods stock and batches are not looked at and the item is deleted)
- **Author:** claude — `products` and batch rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. PL1.
4. BT1 = batch, `status "draft"`.
5. BL1 = batch line of I1.
6. BT2 = batch, `status "in_progress"`, but `batch_number "PB-ITM-2"`.
7. BL2 = batch line of I1. (On BT2.)
8. PR = finished stock of I1, `qty 7`.
9. ST = stage "Open".
10. TO = transfer order, `current_status_id ST.id`. (`completed_at None`.)
11. TOL = TO line of I1.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO.id}, {"type": "product_stock", "id": PR.id}, {"type": "production_batch", "id": BT1.id}, {"type": "production_batch", "id": BT2.id}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(PR).

### ITM-D-76 — a products row with quantity 0 does not block the delete
- **Rules:** `delete_item` R9 (g), R9a
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — `products` row, outside the helper sheet

**Given**
1. I1.
2. F1.
3. PR = finished stock of I1, `qty 0`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(PR).

### ITM-D-77 — a soft-deleted products row does not block the delete, whatever its quantity
- **Rules:** `delete_item` R9 (g), R9a
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — `products` row, outside the helper sheet

**Given**
1. I1.
2. F1.
3. PR = finished stock of I1, `qty 7`, but `is_deleted True`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(PR).

### ITM-D-78 — a line on a completed production batch does not block the delete
- **Rules:** `delete_item` R9 (h), R9a
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — batch rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. PL1.
4. BT = batch, `status "completed"`.
5. BL = batch line of I1.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(BT).
4. unchanged: unchanged(BL).

### ITM-D-79 — a line on a cancelled production batch does not block the delete
- **Rules:** `delete_item` R9 (h), R9a
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — batch rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. PL1.
4. BT = batch, `status "cancelled"`.
5. BL = batch line of I1.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(BT).
4. unchanged: unchanged(BL).

### ITM-D-80 — stock rows and a batch line of W2 on parents of W1 block the delete, shown only as one generic entry
- **Rules:** `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (a), (b), (g), (h) [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: stock and batches are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. MC1.
4. SK = stock of I1, `qty 400`, but `workspace_id W2.id`. (`factory_id F1.id`: a factory of W1.)
5. MS = machine stock of I1, `qty 5`, but `workspace_id W2.id`. (`machine_id MC1.id`: a machine of W1.)
6. PR = finished stock of I1, `qty 7`, but `workspace_id W2.id`. (`factory_id F1.id`.)
7. PL1.
8. BT = batch, `status "draft"`.
9. BL = batch line of I1, but `workspace_id W2.id`. (On BT, a batch of W1.)

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(BL).

### ITM-D-81 — order lines of W2 on orders of W1 block the delete, shown only as one generic entry
- **Rules:** `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (c), (d), (e), (f) [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. ST = stage "Draft".
4. PO = purchase order, `current_status_id ST.id`. (An order of W1.)
5. POL = PO line of I1, but `workspace_id W2.id`.
6. AC1.
7. SO = sales order, `current_status_id ST.id`. (`order_completed False`.)
8. SOL = SO line of I1, but `workspace_id W2.id`.
9. WT1.
10. WO = work order, `status "DRAFT"`.
11. WOL = WO line of I1, but `workspace_id W2.id`.
12. TO = transfer order, `current_status_id ST.id`. (`completed_at None`.)
13. TOL = TO line of I1, but `workspace_id W2.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(POL).

### ITM-D-82 — a purchase order of W1 on a stage "Complete" of W2 does not block the delete
- **Rules:** `delete_item` R9 intro: the stage is not part of the cross-workspace test, R9 (c), R9a
- **Kind:** isolation
- **Expect:** pass
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. ST9 = stage "Complete", but `workspace_id W2.id`.
4. PO = purchase order, `current_status_id ST9.id`. (An order of W1.)
5. POL = PO line of I1.
6. W1 has no stage named "Complete".

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(PO).
4. unchanged: unchanged(POL).

### ITM-D-83 — an item of another workspace that is in use is refused without its blockers
- **Rules:** `delete_item` R9 (checked after R1–R3), R2
- **Kind:** isolation
- **Expect:** pass
- **Author:** claude — rows of W2, outside the helper sheet

**Given**
1. I9.
2. F9.
3. SK = stock of I9, `qty 400`, but `workspace_id W2.id`, `factory_id F9.id`.

**When**
- `M.delete_item(db, item_id=I9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `len(exc.value.args) == 1` (no blocker list reaches the caller).
3. raises: `exc.value.args[0] != "Item has stock or open orders"`.
4. unchanged: unchanged(I9).
5. unchanged: unchanged(SK).

### ITM-D-84 — a pending return does not free an order line that blocks: the orders are listed, not the returns
- **Rules:** `delete_item` R9a (the order line still counts), R9 (c), (d) [BUG-948], R9b [BUG-948], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)
- **Author:** claude — rows of R9a tables, outside the helper sheet

**Given**
1. I1.
2. F1.
3. ST1 = stage "Receiving".
4. PO = purchase order, `current_status_id ST1.id`.
5. POL = PO line of I1.
6. PRT = `purchase_order_returns` row (R9a row), `PurchaseOrderReturn` from `app.models.purchase_order_return`: `workspace_id W1.id`, `purchase_order_id PO.id`, `return_number "PR-ITM-1"`, `created_by U1.id`, `status "pending"`.
7. PRL = `purchase_order_return_items` row (R9a row), `PurchaseOrderReturnItem` from `app.models.purchase_order_return`: `workspace_id W1.id`, `return_id PRT.id`, `po_item_id POL.id`, `item_id I1.id`, `quantity_returned 2`.
8. AC1.
9. ST2 = stage "Open".
10. SO = sales order, `current_status_id ST2.id`. (`order_completed False`.)
11. SOL = SO line of I1.
12. SRT = `sales_order_returns` row (R9a row), `SalesOrderReturn` from `app.models.sales_order_return`: `workspace_id W1.id`, `sales_order_id SO.id`, `return_number "SR-ITM-1"`, `created_by U1.id`, `status "pending"`.
13. SRL = `sales_order_return_items` row (R9a row), `SalesOrderReturnItem` from `app.models.sales_order_return`: `workspace_id W1.id`, `return_id SRT.id`, `so_item_id SOL.id`, `item_id I1.id`, `quantity_returned 2`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "purchase_order", "id": PO.id}, {"type": "sales_order", "id": SO.id}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(PRL).
6. unchanged: unchanged(SRL).

### ITM-D-85 — waste and byproduct lines with quantity 0 on open batches block the delete
- **Rules:** `delete_item` R9 (h) [BUG-948], R9b [BUG-948]
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: production batches are not looked at and the item is deleted)
- **Author:** claude — batch rows; the spec does not name the quantity columns (Spec gap 9): read them from the model

**Given**
1. I1.
2. F1.
3. PL1.
4. BT1 = batch, `status "draft"`.
5. BL1 = batch line of I1, but `item_role "waste"`, and every quantity column of `production_batch_items` set to 0.
6. BT2 = batch, `status "in_progress"`, but `batch_number "PB-ITM-2"`.
7. BL2 = batch line of I1, but `item_role "byproduct"`, and every quantity column of `production_batch_items` set to 0.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[1] == [{"type": "production_batch", "id": BT1.id}, {"type": "production_batch", "id": BT2.id}]`.
3. re-read I1: `is_active is True`, `updated_by is None`.
4. unchanged: unchanged(BL1).
5. unchanged: unchanged(BL2).

### ITM-D-86 — stock on a soft-deleted factory and machine does not block the delete
- **Rules:** `delete_item` R9 (a), (b), (g), R9a, R9b
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — soft-deleted parents and a `products` row, outside the helper sheet

**Given**
1. I1.
2. F1, but `is_deleted True`, `is_active False`.
3. MC1, but `is_deleted True`, `is_active False`.
4. SK = stock of I1, `qty 400`.
5. MS = machine stock of I1, `qty 5`.
6. PR = finished stock of I1, `qty 7`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(SK).
4. unchanged: unchanged(MS).
5. unchanged: unchanged(PR).

### ITM-D-87 — a W1 line on a purchase order of W2 blocks the delete, shown only as the generic entry
- **Rules:** `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (c) [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F9.
3. ST9 = stage "Draft", but `workspace_id W2.id`.
4. PO = purchase order, `current_status_id ST9.id`, but `workspace_id W2.id`, `destination_id F9.id`.
5. POL = PO line of I1. (A line of W1.)

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(POL).

### ITM-D-88 — a W1 line on a production batch of W2 blocks the delete, shown only as the generic entry
- **Rules:** `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (h) [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: production batches are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F9.
3. PL9.
4. BT = batch, `status "draft"`, but `workspace_id W2.id`, `production_line_id PL9.id`.
5. BL = batch line of I1. (A line of W1.)

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(BL).

### ITM-D-89 — a W1 order with one W1 line and one W2 line gives its normal entry and the generic entry
- **Rules:** `delete_item` R9b: lines judged one at a time [BUG-948], R9 intro: cross-workspace row [BUG-948], R9 (c) [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. ST = stage "Draft".
4. PO = purchase order, `current_status_id ST.id`.
5. POL1 = PO line of I1.
6. POL2 = PO line of I1, but `line_number 2`, `workspace_id W2.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "purchase_order", "id": PO.id}, {"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(POL1).
6. unchanged: unchanged(POL2).

### ITM-D-90 — W1 rows that point at a stage or factory of W2 get their normal entries, not the generic one
- **Rules:** `delete_item` R9 intro: the stage or factory is not part of the cross-workspace test [BUG-948], R9 (a), (c) [BUG-948], R9b [BUG-948], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: stock and orders are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. F9.
4. ST9 = stage "Draft", but `workspace_id W2.id`.
5. PO = purchase order, `current_status_id ST9.id`. (An order of W1.)
6. POL = PO line of I1. (A line of W1.)
7. SK = stock of I1, `qty 400`, but `factory_id F9.id`. (A stock row of W1.)

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "factory_stock", "id": SK.id}, {"type": "purchase_order", "id": PO.id}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(SK).
6. unchanged: unchanged(POL).

### ITM-D-91 — a factory stock row of W2 with quantity 0 does not block the delete
- **Rules:** `delete_item` R9 intro: cross-workspace row, not blocking, R9 (a), R9a
- **Kind:** isolation
- **Expect:** pass
- **Author:** claude — rows of W2, outside the helper sheet

**Given**
1. I1.
2. F9.
3. SK = stock of I1, `qty 0`, but `workspace_id W2.id`, `factory_id F9.id`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(SK).

### ITM-D-92 — a factory stock row of W2 on a factory of W1 blocks the delete, shown only as the generic entry
- **Rules:** `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (a) [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: stock is not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. SK = stock of I1, `qty 400`, but `workspace_id W2.id`. (`factory_id F1.id`: a factory of W1.)

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(SK).

### ITM-D-93 — a machine stock row of W2 on a machine of W1 blocks the delete, shown only as the generic entry
- **Rules:** `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (b) [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: machine stock is not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. MC1.
4. MS = machine stock of I1, `qty 5`, but `workspace_id W2.id`. (`machine_id MC1.id`: a machine of W1.)

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(MS).

### ITM-D-94 — a products row of W2 on a factory of W1 blocks the delete, shown only as the generic entry
- **Rules:** `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (g) [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: finished-goods stock is not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. PR = finished stock of I1, `qty 7`, but `workspace_id W2.id`. (`factory_id F1.id`: a factory of W1.)

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(PR).

### ITM-D-95 — a W2 line on a sales order of W1 blocks the delete, shown only as the generic entry
- **Rules:** `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (d) [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. AC1.
4. ST = stage "Open".
5. SO = sales order, `current_status_id ST.id`. (`order_completed False`; an order of W1.)
6. SOL = SO line of I1, but `workspace_id W2.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(SOL).

### ITM-D-96 — a W2 line on a work order of W1 blocks the delete, shown only as the generic entry
- **Rules:** `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (e) [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. WT1.
4. WO = work order, `status "DRAFT"`. (An order of W1.)
5. WOL = WO line of I1, but `workspace_id W2.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(WOL).

### ITM-D-97 — a W2 line on a transfer order of W1 blocks the delete, shown only as the generic entry
- **Rules:** `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (f) [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. ST = stage "Open".
4. TO = transfer order, `current_status_id ST.id`. (`completed_at None`; an order of W1.)
5. TOL = TO line of I1, but `workspace_id W2.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(TOL).

### ITM-D-98 — a W2 line on a production batch of W1 blocks the delete, shown only as the generic entry
- **Rules:** `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (h) [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: production batches are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. PL1.
4. BT = batch, `status "draft"`. (A batch of W1.)
5. BL = batch line of I1, but `workspace_id W2.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(BL).

### ITM-D-99 — factory stock in a factory with only `is_deleted True` does not block the delete
- **Rules:** `delete_item` R9 (a), R9a, R9b
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — soft-deleted parent, outside the helper sheet

**Given**
1. I1.
2. F1, but `is_deleted True`. (`is_active` stays True.)
3. SK = stock of I1, `qty 7`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(SK).

### ITM-D-100 — a products row in a factory with only `is_deleted True` does not block the delete
- **Rules:** `delete_item` R9 (g), R9a, R9b
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — soft-deleted parent, outside the helper sheet

**Given**
1. I1.
2. F1, but `is_deleted True`. (`is_active` stays True.)
3. PR = finished stock of I1, `qty 7`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(PR).

### ITM-D-101 — machine stock on a deleted machine in a live factory does not block the delete
- **Rules:** `delete_item` R9 (b), R9a, R9b
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — soft-deleted parent, outside the helper sheet

**Given**
1. I1.
2. F1.
3. MC1, but `is_deleted True`. (`is_active` stays True.)
4. MS = machine stock of I1, `qty 5`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(MS).

### ITM-D-102 — machine stock on a live machine of a deleted factory does not block the delete
- **Rules:** `delete_item` R9 (b), R9a, R9b
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — soft-deleted parent, outside the helper sheet

**Given**
1. I1.
2. F1, but `is_deleted True`. (`is_active` stays True.)
3. MC1. (A live machine.)
4. MS = machine stock of I1, `qty 5`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(MS).

### ITM-D-103 — stock of a machine and factory that are only deactivated still blocks the delete and is listed
- **Rules:** `delete_item` R9 (a), (b), (g) [BUG-948], R9b [BUG-948], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: stock is not looked at and the item is deleted)
- **Author:** claude — deactivated parents and a `products` row, outside the helper sheet

**Given**
1. I1.
2. F1, but `is_active False`. (`is_deleted False`.)
3. MC1, but `is_active False`. (`is_deleted False`.)
4. SK = stock of I1, `qty 400`.
5. MS = machine stock of I1, `qty 5`.
6. PR = finished stock of I1, `qty 7`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "factory_stock", "id": SK.id}, {"type": "machine_stock", "id": MS.id}, {"type": "product_stock", "id": PR.id}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(SK).
6. unchanged: unchanged(MS).
7. unchanged: unchanged(PR).

### ITM-D-104 — a W2 stock row in a deleted W2 factory does not block the delete and gets no generic entry
- **Rules:** `delete_item` R9 (a), R9a, R9b, R9 intro: a cross-workspace row follows the same states
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — soft-deleted parent, outside the helper sheet

**Given**
1. I1.
2. F9, but `is_deleted True`.
3. SK = stock of I1, `qty 7`, but `workspace_id W2.id`, `factory_id F9.id`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(SK).

### ITM-D-105 — a W2 stock row in a deleted W1 factory does not block the delete and gets no generic entry
- **Rules:** `delete_item` R9 (a), R9a, R9b, R9 intro: a cross-workspace row follows the same states
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — soft-deleted parent, outside the helper sheet

**Given**
1. I1.
2. F1, but `is_deleted True`. (`is_active` stays True.)
3. SK = stock of I1, `qty 7`, but `workspace_id W2.id`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(SK).

### ITM-D-106 — a W1 stock row in a deleted W2 factory does not block the delete
- **Rules:** `delete_item` R9 (a), R9a, R9b, R9 intro: a cross-workspace row follows the same states
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — soft-deleted parent, outside the helper sheet

**Given**
1. I1.
2. F9, but `is_deleted True`.
3. SK = stock of I1, `qty 7`, but `factory_id F9.id`. (A stock row of W1.)

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(SK).

### ITM-D-107 — a W2 products row in a deleted W2 factory does not block the delete and gets no generic entry
- **Rules:** `delete_item` R9 (g), R9a, R9b, R9 intro: a cross-workspace row follows the same states
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — soft-deleted parent, outside the helper sheet

**Given**
1. I1.
2. F9, but `is_deleted True`.
3. PR = finished stock of I1, `qty 7`, but `workspace_id W2.id`, `factory_id F9.id`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(PR).

### ITM-D-108 — a W2 products row in a deleted W1 factory does not block the delete and gets no generic entry
- **Rules:** `delete_item` R9 (g), R9a, R9b, R9 intro: a cross-workspace row follows the same states
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — soft-deleted parent, outside the helper sheet

**Given**
1. I1.
2. F1, but `is_deleted True`. (`is_active` stays True.)
3. PR = finished stock of I1, `qty 7`, but `workspace_id W2.id`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(PR).

### ITM-D-109 — a W1 products row in a deleted W2 factory does not block the delete
- **Rules:** `delete_item` R9 (g), R9a, R9b, R9 intro: a cross-workspace row follows the same states
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — soft-deleted parent, outside the helper sheet

**Given**
1. I1.
2. F9, but `is_deleted True`.
3. PR = finished stock of I1, `qty 7`, but `factory_id F9.id`. (A row of W1.)

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(PR).

### ITM-D-110 — a W2 machine row on a deleted W2 machine does not block the delete and gets no generic entry
- **Rules:** `delete_item` R9 (b), R9a, R9b, R9 intro: a cross-workspace row follows the same states
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — soft-deleted parent, outside the helper sheet

**Given**
1. I1.
2. F9.
3. MC9, but `is_deleted True`.
4. MS = machine stock of I1, `qty 5`, but `workspace_id W2.id`, `machine_id MC9.id`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(MS).

### ITM-D-111 — a W2 machine row on a deleted W1 machine does not block the delete and gets no generic entry
- **Rules:** `delete_item` R9 (b), R9a, R9b, R9 intro: a cross-workspace row follows the same states
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — soft-deleted parent, outside the helper sheet

**Given**
1. I1.
2. F1.
3. MC1, but `is_deleted True`.
4. MS = machine stock of I1, `qty 5`, but `workspace_id W2.id`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(MS).

### ITM-D-112 — a W1 machine row on a deleted W2 machine does not block the delete
- **Rules:** `delete_item` R9 (b), R9a, R9b, R9 intro: a cross-workspace row follows the same states
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — soft-deleted parent, outside the helper sheet

**Given**
1. I1.
2. F9.
3. MC9, but `is_deleted True`.
4. MS = machine stock of I1, `qty 5`, but `machine_id MC9.id`. (A row of W1.)

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(MS).

### ITM-D-113 — a W2 machine row on a live W2 machine of a deleted W2 factory does not block the delete
- **Rules:** `delete_item` R9 (b), R9a, R9b, R9 intro: a cross-workspace row follows the same states
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — soft-deleted parent, outside the helper sheet

**Given**
1. I1.
2. F9, but `is_deleted True`.
3. MC9. (A live machine.)
4. MS = machine stock of I1, `qty 5`, but `workspace_id W2.id`, `machine_id MC9.id`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(MS).

### ITM-D-114 — a W1 machine row on a live W2 machine of a deleted W2 factory does not block the delete
- **Rules:** `delete_item` R9 (b), R9a, R9b, R9 intro: a cross-workspace row follows the same states
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — soft-deleted parent, outside the helper sheet

**Given**
1. I1.
2. F9, but `is_deleted True`.
3. MC9. (A live machine.)
4. MS = machine stock of I1, `qty 5`, but `machine_id MC9.id`. (A row of W1.)

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(MS).

### ITM-D-115 — stock with a deleted parent beside a live blocker: only the live one is listed
- **Rules:** `delete_item` R9 (a), (b), (g) [BUG-948], R9a, R9b [BUG-948], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: stock is not looked at and the item is deleted)
- **Author:** claude — soft-deleted parent, outside the helper sheet

**Given**
1. I1.
2. F1, but `is_deleted True`. (`is_active` stays True.)
3. F2 = F1, but `name "Side Plant"`, `abbreviation "SP"`, `is_deleted False`. (A live factory of W1.)
4. MC1. (`factory_id F1.id`: a live machine of the deleted factory.)
5. SK = stock of I1, `qty 400`.
6. MS = machine stock of I1, `qty 5`.
7. PR = finished stock of I1, `qty 7`.
8. F9, but `is_deleted True`.
9. SK9 = stock of I1, `qty 9`, but `workspace_id W2.id`, `factory_id F9.id`.
10. LV = stock of I1, `qty 3`, but `factory_id F2.id`. (The live blocker.)

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "factory_stock", "id": LV.id}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(SK).
6. unchanged: unchanged(MS).
7. unchanged: unchanged(PR).
8. unchanged: unchanged(SK9).
9. unchanged: unchanged(LV).

### ITM-D-116 — open order and batch lines tied to a deleted factory still block the delete and are listed
- **Rules:** `delete_item` R9a (orders and batches not covered), R9 (c), (d), (e), (f), (h) [BUG-948], R9b [BUG-948], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders and batches are not looked at and the item is deleted)
- **Author:** claude — soft-deleted parent, outside the helper sheet

**Given**
1. I1.
2. F1, but `is_deleted True`.
3. ST = stage "Draft".
4. PO = purchase order, `current_status_id ST.id`.
5. POL = PO line of I1.
6. AC1.
7. SO = sales order, `current_status_id ST.id`. (`order_completed False`.)
8. SOL = SO line of I1.
9. WT1.
10. WO = work order, `status "DRAFT"`.
11. WOL = WO line of I1.
12. TO = transfer order, `current_status_id ST.id`. (`completed_at None`.)
13. TOL = TO line of I1.
14. PL1.
15. BT = batch, `status "draft"`.
16. BL = batch line of I1.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "purchase_order", "id": PO.id}, {"type": "sales_order", "id": SO.id}, {"type": "work_order", "id": WO.id}, {"type": "transfer_order", "id": TO.id}, {"type": "production_batch", "id": BT.id}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(POL).
6. unchanged: unchanged(SOL).
7. unchanged: unchanged(WOL).
8. unchanged: unchanged(TOL).
9. unchanged: unchanged(BL).

### ITM-D-117 — a W1 line on a sales order of W2 blocks the delete, shown only as the generic entry
- **Rules:** `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (d) [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F9.
3. AC9.
4. ST9 = stage "Open", but `workspace_id W2.id`.
5. SO = sales order, `current_status_id ST9.id`, but `workspace_id W2.id`, `account_id AC9.id`, `factory_id F9.id`. (`order_completed False`.)
6. SOL = SO line of I1. (A line of W1.)

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(SOL).

### ITM-D-118 — a W1 line on a work order of W2 blocks the delete, shown only as the generic entry
- **Rules:** `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (e) [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F9.
3. WT9.
4. WO = work order, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
5. WOL = WO line of I1. (A line of W1.)

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(WOL).

### ITM-D-119 — a W1 line on a transfer order of W2 blocks the delete, shown only as the generic entry
- **Rules:** `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (f) [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F9.
3. ST9 = stage "Open", but `workspace_id W2.id`.
4. TO = transfer order, `current_status_id ST9.id`, but `workspace_id W2.id`, `source_location_id F9.id`, `destination_location_id F9.id`. (`completed_at None`.)
5. TOL = TO line of I1. (A line of W1.)

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(TOL).

### ITM-D-120 — a W2 line on a work order of W1 that replaces the item is shown only as the generic entry
- **Rules:** `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (e) by `replaced_item_id` [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. I2.
3. F1.
4. WT1.
5. WO = work order, `status "DRAFT"`. (An order of W1.)
6. WOL = WO line of I2, but `replaced_item_id I1.id`, `workspace_id W2.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(WOL).

### ITM-D-121 — a W1 line on a work order of W2 that replaces the item is shown only as the generic entry
- **Rules:** `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (e) by `replaced_item_id` [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. I2.
3. F9.
4. WT9.
5. WO = work order, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
6. WOL = WO line of I2, but `replaced_item_id I1.id`. (A line of W1.)

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(WOL).

### ITM-D-122 — a W2 line on a work order of W2 that replaces the item is shown only as the generic entry
- **Rules:** `delete_item` R9 intro: cross-workspace row [BUG-948], R9 (e) by `replaced_item_id` [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. I2.
3. F9.
4. WT9.
5. WO = work order, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
6. WOL = WO line of I2, but `replaced_item_id I1.id`, `workspace_id W2.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(WOL).

### ITM-D-123 — W2 stock rows in their non-blocking states do not block the delete
- **Rules:** `delete_item` R9 intro: a cross-workspace row blocks and does not block in exactly the states (a)–(h), R9 (a), (b), (g), R9a
- **Kind:** isolation
- **Expect:** pass
- **Author:** claude — rows of W2, outside the helper sheet

**Given**
1. I1.
2. F9.
3. MC9.
4. SK = stock of I1, `qty 7`, but `workspace_id W2.id`, `factory_id F9.id`, `is_deleted True`.
5. MS = machine stock of I1, `qty 0`, but `workspace_id W2.id`, `machine_id MC9.id`.
6. PR1 = finished stock of I1, `qty 0`, but `workspace_id W2.id`, `factory_id F9.id`.
7. PR2 = finished stock of I1, `qty 7`, but `workspace_id W2.id`, `factory_id F9.id`, `is_deleted True`, `is_available_for_sale True`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(SK).
4. unchanged: unchanged(MS).
5. unchanged: unchanged(PR1).
6. unchanged: unchanged(PR2).

### ITM-D-124 — W2 purchase, sales and transfer orders in their non-blocking states do not block the delete
- **Rules:** `delete_item` R9 intro: a cross-workspace row blocks and does not block in exactly the states (a)–(h), R9 (c), (d), (f), R9a
- **Kind:** isolation
- **Expect:** pass
- **Author:** claude — rows of W2, outside the helper sheet

**Given**
1. I1.
2. F9.
3. AC9.
4. ST9 = stage "Open", but `workspace_id W2.id`.
5. PO = purchase order, `current_status_id ST9.id`, but `workspace_id W2.id`, `destination_id F9.id`, `voided True`.
6. POL = PO line of I1, but `workspace_id W2.id`.
7. SO = sales order, `current_status_id ST9.id`, but `workspace_id W2.id`, `account_id AC9.id`, `factory_id F9.id`, `order_completed True`.
8. SOL = SO line of I1, but `workspace_id W2.id`.
9. TO = transfer order, `current_status_id ST9.id`, but `workspace_id W2.id`, `source_location_id F9.id`, `destination_location_id F9.id`, `completed_at T0`.
10. TOL = TO line of I1, but `workspace_id W2.id`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(POL).
4. unchanged: unchanged(SOL).
5. unchanged: unchanged(TOL).

### ITM-D-125 — W2 work orders in their non-blocking states do not block the delete
- **Rules:** `delete_item` R9 intro: a cross-workspace row blocks and does not block in exactly the states (a)–(h), R9 (e), R9a
- **Kind:** isolation
- **Expect:** pass
- **Author:** claude — rows of W2, outside the helper sheet

**Given**
1. I1.
2. F9.
3. WT9.
4. WO1 = work order, `status "COMPLETED"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`.
5. WOL1 = WO line of I1, but `workspace_id W2.id`. (On WO1.)
6. WO2 = work order, `status "VOIDED"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `work_order_number "WO-ITM-2"`.
7. WOL2 = WO line of I1, but `workspace_id W2.id`. (On WO2.)
8. WO3 = work order, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `work_order_number "WO-ITM-3"`, `is_deleted True`.
9. WOL3 = WO line of I1, but `workspace_id W2.id`. (On WO3.)
10. WO4 = work order, `status "DRAFT"`, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `work_order_number "WO-ITM-4"`.
11. WOL4 = WO line of I1, but `workspace_id W2.id`, `is_deleted True`. (On WO4.)

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(WOL1).
4. unchanged: unchanged(WOL2).
5. unchanged: unchanged(WOL3).
6. unchanged: unchanged(WOL4).

### ITM-D-126 — W2 batches `completed` and `cancelled` do not block the delete
- **Rules:** `delete_item` R9 intro: a cross-workspace row blocks and does not block in exactly the states (a)–(h), R9 (h), R9a
- **Kind:** isolation
- **Expect:** pass
- **Author:** claude — rows of W2, outside the helper sheet

**Given**
1. I1.
2. F9.
3. PL9.
4. BT1 = batch, `status "completed"`, but `workspace_id W2.id`, `production_line_id PL9.id`.
5. BL1 = batch line of I1, but `workspace_id W2.id`.
6. BT2 = batch, `status "cancelled"`, but `workspace_id W2.id`, `production_line_id PL9.id`, `batch_number "PB-ITM-2"`.
7. BL2 = batch line of I1, but `workspace_id W2.id`.

**When**
- `result = M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is I1` (the very object that was read).
2. re-read I1: `is_active is False`, `updated_by == U2.id`.
3. unchanged: unchanged(BL1).
4. unchanged: unchanged(BL2).

### ITM-D-127 — W1 rows on W2 machines, factories, accounts, types, stages and production lines get their normal entries
- **Rules:** `delete_item` R9 intro: the factory, machine, stage or production line is not part of the cross-workspace test [BUG-948], R9 (b), (d), (e), (f), (g), (h) [BUG-948], R9b [BUG-948], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: stock, orders and batches are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F9.
3. MC9.
4. MS = machine stock of I1, `qty 5`, but `machine_id MC9.id`. (A row of W1.)
5. AC9.
6. ST9 = stage "Open", but `workspace_id W2.id`.
7. SO = sales order, `current_status_id ST9.id`, but `account_id AC9.id`, `factory_id F9.id`. (An order of W1.)
8. SOL = SO line of I1.
9. WT9.
10. WO = work order, `status "DRAFT"`, but `work_order_type_id WT9.id`, `factory_id F9.id`. (An order of W1.)
11. WOL = WO line of I1.
12. TO = transfer order, `current_status_id ST9.id`, but `source_location_id F9.id`, `destination_location_id F9.id`. (An order of W1.)
13. TOL = TO line of I1.
14. PR = finished stock of I1, `qty 7`, but `factory_id F9.id`. (A row of W1.)
15. PL9.
16. BT = batch, `status "draft"`, but `production_line_id PL9.id`. (A batch of W1.)
17. BL = batch line of I1.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "machine_stock", "id": MS.id}, {"type": "sales_order", "id": SO.id}, {"type": "work_order", "id": WO.id}, {"type": "transfer_order", "id": TO.id}, {"type": "product_stock", "id": PR.id}, {"type": "production_batch", "id": BT.id}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(MS).
6. unchanged: unchanged(PR).

### ITM-D-128 — a W1 sales order with one W1 line and one W2 line gives its normal entry and the generic entry
- **Rules:** `delete_item` R9b: lines judged one at a time [BUG-948], R9 intro: cross-workspace row [BUG-948], R9 (d) [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. AC1.
4. ST = stage "Open".
5. SO = sales order, `current_status_id ST.id`.
6. SOL1 = SO line of I1.
7. SOL2 = SO line of I1, but `workspace_id W2.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "sales_order", "id": SO.id}, {"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(SOL1).
6. unchanged: unchanged(SOL2).

### ITM-D-129 — a W1 work order with one W1 line and one W2 line gives its normal entry and the generic entry
- **Rules:** `delete_item` R9b: lines judged one at a time [BUG-948], R9 intro: cross-workspace row [BUG-948], R9 (e) [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. WT1.
4. WO = work order, `status "DRAFT"`.
5. WOL1 = WO line of I1.
6. WOL2 = WO line of I1, but `workspace_id W2.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "work_order", "id": WO.id}, {"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(WOL1).
6. unchanged: unchanged(WOL2).

### ITM-D-130 — a W1 transfer order with one W1 line and one W2 line gives its normal entry and the generic entry
- **Rules:** `delete_item` R9b: lines judged one at a time [BUG-948], R9 intro: cross-workspace row [BUG-948], R9 (f) [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: orders are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. ST = stage "Open".
4. TO = transfer order, `current_status_id ST.id`.
5. TOL1 = TO line of I1.
6. TOL2 = TO line of I1, but `line_number 2`, `workspace_id W2.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "transfer_order", "id": TO.id}, {"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(TOL1).
6. unchanged: unchanged(TOL2).

### ITM-D-131 — a W1 batch with one W1 line and one W2 line gives its normal entry and the generic entry
- **Rules:** `delete_item` R9b: lines judged one at a time [BUG-948], R9 intro: cross-workspace row [BUG-948], R9 (h) [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: production batches are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. PL1.
4. BT = batch, `status "draft"`.
5. BL1 = batch line of I1.
6. BL2 = batch line of I1, but `item_role "output"`, `workspace_id W2.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "production_batch", "id": BT.id}, {"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(BL1).
6. unchanged: unchanged(BL2).

### ITM-D-132 — work order, transfer order, finished-goods stock and batch keep their order, and the generic entry stays last
- **Rules:** `delete_item` R9b [BUG-948], R9 intro: cross-workspace row [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: stock, orders and batches are not looked at and the item is deleted)
- **Author:** claude — mixed-workspace rows, outside the helper sheet

**Given**
1. I1.
2. F1.
3. F9.
4. SK9 = stock of I1, `qty 4`, but `workspace_id W2.id`, `factory_id F9.id`. (Built first.)
5. PL1.
6. BT = batch, `status "draft"`.
7. BL = batch line of I1.
8. PR = finished stock of I1, `qty 7`.
9. ST = stage "Open".
10. TO = transfer order, `current_status_id ST.id`.
11. TOL = TO line of I1.
12. WT1.
13. WO = work order, `status "DRAFT"`.
14. WOL = WO line of I1.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "work_order", "id": WO.id}, {"type": "transfer_order", "id": TO.id}, {"type": "product_stock", "id": PR.id}, {"type": "production_batch", "id": BT.id}, {"type": "other_workspace"}]`.
4. re-read I1: `is_active is True`, `updated_by is None`.
5. unchanged: unchanged(SK9).
6. unchanged: unchanged(PR).

### ITM-D-133 — an item whose only blocker is cross-workspace, deleted by an unknown user, gets the refusal, not a database error
- **Rules:** `delete_item` R10a [BUG-948], R9 intro: cross-workspace row [BUG-948], R9b [BUG-948], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (the call raises IntegrityError: stock is not looked at, so the flush fails on `items_updated_by_fkey`)
- **Author:** claude — the call fails on flush today and must have no savepoint around it, and a row of W2

**Given**
1. I1.
2. F9.
3. SK = stock of I1, `qty 400`, but `workspace_id W2.id`, `factory_id F9.id`.

**When**
- `M.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=MISSING)`, in a plain `with pytest.raises(ValueError) as exc:`, no `db.begin_nested()`.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value.args[0] == "Item has stock or open orders"`.
3. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
4. returns: `I1 not in db.dirty` (checked before any re-read: `expire_all()` would throw a pending change away).
5. returns: `db.flush() is None` (the flush runs with no error, before any re-read).
6. re-read I1: `is_active is True`, `updated_by is None`.
7. unchanged: unchanged(SK).

## `ItemManager._assign_tags_to_item`

### ITM-A-01 — each requested active tag is linked by the acting user and counted once
- **Rules:** `_assign_tags_to_item` R1, R7, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.
2. T1, but `usage_count 3`.
3. T2.

**When**
- `result = M._assign_tags_to_item(db, item_id=I1.id, tag_ids=[T1.id, T2.id], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. re-read: `tag_ids_of(I1) == [T1.id, T2.id]`.
3. re-read: every row of `links_of(I1)` has `workspace_id == W1.id`, `assigned_by == U2.id`.
4. re-read: every row of `links_of(I1)` has `assigned_at is not None`.
5. re-read: `stored_count(T1) == 4`.
6. re-read: `stored_count(T2) == 1`.

### ITM-A-02 — an unknown tag id is refused as not found
- **Rules:** `_assign_tags_to_item` R2 [BUG-944], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-944
- **Fails today on:** Then 1 (no error is raised: the unknown id is skipped)

**Given**
1. I1.

**When**
- `M._assign_tags_to_item(db, item_id=I1.id, tag_ids=[MISSING], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Item tag 999999999 not found"`.
3. re-read: `links_of(I1) == []`.

### ITM-A-03 — tag id 0 is refused as not found
- **Rules:** `_assign_tags_to_item` R2 [BUG-944], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-944
- **Fails today on:** Then 1 (no error is raised: the id is skipped)

**Given**
1. I1.

**When**
- `M._assign_tags_to_item(db, item_id=I1.id, tag_ids=[0], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Item tag 0 not found"`.
3. re-read: `links_of(I1) == []`.

### ITM-A-04 — a negative tag id is refused as not found
- **Rules:** `_assign_tags_to_item` R2 [BUG-944], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-944
- **Fails today on:** Then 1 (no error is raised: the id is skipped)

**Given**
1. I1.

**When**
- `M._assign_tags_to_item(db, item_id=I1.id, tag_ids=[-1], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Item tag -1 not found"`.
3. re-read: `links_of(I1) == []`.

### ITM-A-05 — a tag of another workspace is refused as not found and stays uncounted
- **Rules:** `_assign_tags_to_item` R2 [BUG-944], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-944
- **Fails today on:** Then 1 (no error is raised: the foreign tag is skipped)

**Given**
1. I1.
2. T9, but `usage_count 2`.

**When**
- `M._assign_tags_to_item(db, item_id=I1.id, tag_ids=[T9.id], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == f"Item tag {T9.id} not found"`.
3. re-read: `links_of(I1) == []`.
4. re-read: `stored_count(T9) == 2`.

### ITM-A-06 — a deleted tag not yet on the item is refused
- **Rules:** `_assign_tags_to_item` R3 [BUG-943], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-943
- **Fails today on:** Then 1 (no error is raised: the deleted tag is linked and counted)

**Given**
1. I1.
2. TD, but `usage_count 5`.

**When**
- `M._assign_tags_to_item(db, item_id=I1.id, tag_ids=[TD.id], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == f"Item tag {TD.id} is not active"`.
3. re-read: `links_of(I1) == []`.
4. re-read: `stored_count(TD) == 5`.

### ITM-A-07 — one bad id in the list stops every link: valid ids before and after it are not linked
- **Rules:** `_assign_tags_to_item` R4 [BUG-944]
- **Kind:** bug
- **Expect:** xfail BUG-944
- **Fails today on:** Then 1 (no error is raised: T1 and T2 are linked and the unknown id is skipped)

**Given**
1. I1.
2. T1, but `usage_count 3`.
3. T2, but `usage_count 6`.

**When**
- `M._assign_tags_to_item(db, item_id=I1.id, tag_ids=[T1.id, MISSING, T2.id], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Item tag 999999999 not found"`.
3. re-read: `links_of(I1) == []`.
4. re-read: `stored_count(T1) == 3`.
5. re-read: `stored_count(T2) == 6`.

### ITM-A-08 — the error names the first rejected id: unknown before deleted
- **Rules:** `_assign_tags_to_item` R4 [BUG-944]
- **Kind:** bug
- **Expect:** xfail BUG-944
- **Fails today on:** Then 1 (no error is raised: the unknown id is skipped and the deleted tag is linked)

**Given**
1. I1.
2. TD, but `usage_count 5`.

**When**
- `M._assign_tags_to_item(db, item_id=I1.id, tag_ids=[MISSING, TD.id], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Item tag 999999999 not found"`.
3. re-read: `links_of(I1) == []`.
4. re-read: `stored_count(TD) == 5`.

### ITM-A-09 — the error names the first rejected id: deleted before unknown
- **Rules:** `_assign_tags_to_item` R4 [BUG-943]
- **Kind:** bug
- **Expect:** xfail BUG-943
- **Fails today on:** Then 1 (no error is raised: the deleted tag is linked and the unknown id is skipped)

**Given**
1. I1.
2. TD, but `usage_count 5`.

**When**
- `M._assign_tags_to_item(db, item_id=I1.id, tag_ids=[TD.id, MISSING], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == f"Item tag {TD.id} is not active"`.
3. re-read: `links_of(I1) == []`.
4. re-read: `stored_count(TD) == 5`.

### ITM-A-10 — a tag already on the item is skipped: no new link, no count change
- **Rules:** `_assign_tags_to_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. T2.
4. L1 = link of I1 to T1.

**When**
- `result = M._assign_tags_to_item(db, item_id=I1.id, tag_ids=[T1.id, T2.id], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(L1).
3. re-read: `tag_ids_of(I1) == [T1.id, T2.id]`.
4. re-read: `stored_count(T1) == 4`.
5. re-read: `stored_count(T2) == 1`.

### ITM-A-11 — a deleted tag already on the item is skipped without an error
- **Rules:** `_assign_tags_to_item` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. I1.
2. TD, but `usage_count 7`.
3. L2 = link of I1 to TD.

**When**
- `result = M._assign_tags_to_item(db, item_id=I1.id, tag_ids=[TD.id], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(L2).
3. re-read: `tag_ids_of(I1) == [TD.id]`.
4. re-read: `stored_count(TD) == 7`.

### ITM-A-12 — the same id twice is linked once and counted once
- **Rules:** `_assign_tags_to_item` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.
2. T1, but `usage_count 3`.

**When**
- `result = M._assign_tags_to_item(db, item_id=I1.id, tag_ids=[T1.id, T1.id], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. re-read: `tag_ids_of(I1) == [T1.id]`.
3. re-read: `stored_count(T1) == 4`.

### ITM-A-13 — links and counts are flushed but not committed
- **Rules:** `_assign_tags_to_item` R7
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. I1.
2. T1, but `usage_count 3`.
3. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = M._assign_tags_to_item(db, item_id=I1.id, tag_ids=[T1.id], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. re-read: `tag_ids_of(I1) == [T1.id]`.
3. re-read: `stored_count(T1) == 4`.
4. re-read after the savepoint rollback: `links_of(I1) == []`.
5. re-read after the savepoint rollback: `stored_count(T1) == 3`.
6. mock called: the `db.commit` spy was never called.


## `ItemManager.get_tags_for_item`

### ITM-TI-01 — the item's active tags of the workspace are returned
- **Rules:** `get_tags_for_item` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.
2. I2.
3. T1.
4. T2.
5. TD.
6. link of I1 to T1.
7. link of I1 to TD.
8. link of I2 to T2.

**When**
- `result = M.get_tags_for_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T1.id]`.
2. nothing written: nothing written.

### ITM-TI-02 — a deleted item's tags are still returned
- **Rules:** `get_tags_for_item` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. IX.
2. T1.
3. link of IX to T1.

**When**
- `result = M.get_tags_for_item(db, item_id=IX.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T1.id]`.


## `ItemManager.get_tags_for_items`

### ITM-TS-01 — one key per requested item, each with its active tags; an unmatched id gets an empty list
- **Rules:** `get_tags_for_items` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.
2. I2.
3. T1.
4. T2.
5. TD.
6. link of I1 to T1.
7. link of I1 to TD.
8. link of I2 to T2.

**When**
- `result = M.get_tags_for_items(db, item_ids=[I1.id, I2.id, MISSING], workspace_id=W1.id)`.

**Then**
1. returns: `set(result.keys()) == {I1.id, I2.id, MISSING}`.
2. returns: `ids(result[I1.id]) == [T1.id]`.
3. returns: `ids(result[I2.id]) == [T2.id]`.
4. returns: `result[MISSING] == []`.
5. nothing written: nothing written.

### ITM-TS-02 — an empty id list gives an empty dict
- **Rules:** `get_tags_for_items` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.

**When**
- `result = M.get_tags_for_items(db, item_ids=[], workspace_id=W1.id)`.

**Then**
1. returns: `result == {}`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `update_item` R2a, `delete_item` R3a [BUG-940] | `ItemService.update_item` / `delete_item`; `PUT` / `DELETE /items/{id}/` | Not found → 404 `Item with ID <id> not found`, already deleted → 400; never 500. |
| FU-1 — HTTP status of the manager's other `ValueError`s | `ItemService`; `/items/` endpoints | Unknown tag → 404, deleted tag → 400 (BUG-944, BUG-943); duplicate SKU → 409 (BUG-946); item in use `Item has stock or open orders` → 400 whose body carries the message as `detail` and the blocker list as `errors` (`ValidationError(detail, errors=…)`, BUG-948, R9b). Here only the `ValueError`, its message and its blocker list. |
| `create_item` R3, `update_item` R6, R7 [BUG-936, BUG-942] — the 422 a schema `ValidationError` becomes | `POST /items/`, `PUT /items/{id}/` | Status 422 and nothing written. Here the schema is built directly. |
| Returns / Side effects of the writers — "not committed"; commit, rollback, `db.refresh` | `ItemService` | Commit on success, rollback on error. Here one savepoint-and-spy card per writer (ITM-C-40, U-45, D-12, A-13). |
| `get_item` R4 [BUG-937] — `include_deleted` reachable from the API (FU-3) | `ItemService.get_item`, `ItemSummaryService`, `ItemOrdersService` | Which pages of a deleted item stay reachable; 404 by default at `GET /items/{id}/`. |
| `update_item` R20, `delete_item` R13 [BUG-931] | item tag DAO spec (`increment_usage_count` R5, `decrement_usage_count` R6) | Lost concurrent counter changes. |
| `list_items_filtered` R1, `count_items_filtered` R1, `distinct_units` R1, `find_similar_items` R1 — the DAO's own rules and bugs (BUG-011 … BUG-018, BUG-033, BUG-034) | item DAO spec / `tests/unit/dao/item.cases.md` | Filters, paging, order, unit grouping, similarity threshold and order. Here one pass-through card per argument (and FS-04 for the rounding of BUG-034). |
| `get_tags_for_item` R1, `get_tags_for_items` R1 — order (BUG-932, BUG-933) | assignment DAO spec / `tests/unit/dao/item_tag_assignment.cases.md` | Tag order. Here results are compared as sorted ids. |
| FU-4 — "restore item" feature | future manager / service | Re-raise tag counts (deleted tags included), re-check SKU. |
| FU-5 — other managers taking an item id | purchase / sales / work / transfer order, inventory and machine-item manager specs | Whether each refuses a deleted item. Refusing to create a row that links across workspaces (`delete_item` R9, gap 5). |
| FU-6 — edit form never sends `tag_ids: []` | frontend `EditItemDialog.tsx` | Removing an item's last tag from the UI. |
| FU-8 — refused delete must show its blockers [BUG-949] | frontend item delete flow (`ItemsPage.tsx` `handleDelete`) | The user sees what stops the delete (stock per factory / machine, each open order, and the generic `other_workspace` entry) so they can clear it. No backend test. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `delete_item` R9 (d) | **Closed (revision 2):** the owner answered 2026-10-18 — a line on a not-completed sales order blocks. | Now covered: ITM-D-39 (blocks, xfail) and ITM-D-30 (completed, pass). |
| 2 | Overview, `delete_item` R9 | The spec names the stock / order tables and their NOT NULL columns but not their model classes or import paths. | Not blocking: Conventions describe each row by table and columns ("built with the model class of its table"); the helper file supplies the builders. |
| 3 | `create_item` R7 [BUG-946] × Notes (race) | The name of the manager's SKU-existence check that the race card patches does not exist yet and is not given. | ITM-C-32 patches `ItemManager._check_sku_exists` with `create=True`; if the fix uses another name the patch is a no-op (the real check then raises the same `ValueError`, so the card passes without proving the database fallback) — revise the card with the fix. |
| 4 | `delete_item` R9 × R10 | **Closed (revision 4):** R10a — the in-use refusal wins over the unknown-user error (Claude's reading of the owner's answer of 2026-10-30, not the owner's words). | Now covered: ITM-D-48 (in use, xfail); ITM-D-11 stays the not-in-use case. |
| 5 | `delete_item` R9 | **Closed (revision 6):** the first answer ("by item id only") was superseded by the owner's correction of 2026-10-30: a cross-workspace row is invalid data, refused at creation, and `delete_item` still refuses, showing one `{"type": "other_workspace"}` entry, last. Which rows count, and lines judged one at a time, are Claude's reading, not the owner's words. | Now covered: ITM-D-49 … D-54, D-69, D-73, D-80, D-81, D-87, D-88, D-92 … D-98 (generic entry only, xfail), D-117 … D-122, D-133 (generic entry only, xfail), D-56, D-89, D-128 … D-132 (with normal entries, xfail), D-90, D-127 (normal entries, xfail), D-55, D-82, D-91, D-104 … D-114, D-123 … D-126 (not blocking, pass). Creation paths: FU-5, other modules. |
| 6 | `delete_item` R9a | **Closed (revision 4):** the owner answered 2026-10-30 — cover them; the spec's Notes now give tables, classes, import paths and required columns. | Now covered: ITM-D-57 … D-65 (one per row type, pass), with ITM-D-25 … D-35, D-37, D-38 for the not-blocking states of R9. |
| 7 | `delete_item` R12 | The follow-up behaviors after a delete (`get_item` → `None`, `update_item` refuses) are bug rules of other callables. | Covered directly by ITM-G-05 (BUG-937) and ITM-U-07 (BUG-938) on a deleted item rather than as follow-up calls; ITM-D-13 checks only what holds today (list, count, second delete). |
| 8 | `delete_item` R9a, last paragraph | **Not decided:** whether the history rows `product_ledger`, `project_component_item_ledger`, `sales_delivery_items` and `invoice_items.item_id` block the delete. No owner answer names them. (`products` and production batches, raised with them, were answered "Both block": R9 (g), (h).) | No card, as the spec says, so that no test pins an undecided behavior. If the owner decides they block, they need R9 / R9b rules (type names included) and new cards. |
| 9 | `delete_item` Notes, `production_batch_items` | The spec says "quantities are optional" and R9 (h) that they are not looked at, but it does not name the quantity columns. (The soft-delete columns of `factories` and `machines`, part of this gap until revision 8, are now in the Notes entry "Stock with a deleted parent".) | Not blocking. ITM-D-85 is `Author: claude`: the executor reads the quantity columns from the model; if the fix or the table changes them, revise the card. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_item` | R1 | ITM-C-01, C-02, C-03, C-04, C-10 |
| `create_item` | R2 | ITM-C-01, C-05 |
| `create_item` | R3 [BUG-936] | ITM-C-09 (xfail), C-10, C-11 (xfail), C-12 (xfail), C-13 (xfail), C-14 (xfail), C-15 (xfail), C-16 |
| `create_item` | R4 [BUG-017] | ITM-C-17 (xfail), C-18 |
| `create_item` | R5 | ITM-C-06, C-07, C-08, C-20 |
| `create_item` | R6 (Q1 intended) | ITM-C-19, C-20 |
| `create_item` | R7 [BUG-946] | ITM-C-21 (xfail), C-22 (xfail), C-23 (xfail), C-24 (xfail), C-25 (xfail), C-26, C-27, C-28, C-29 (xfail), C-30 (xfail), C-31, C-32 (xfail) |
| `create_item` | R8 | ITM-C-33, C-34 |
| `create_item` | R9 [BUG-944, BUG-943] | ITM-C-35 (xfail), C-36 (xfail), C-37 (xfail) |
| `create_item` | R10 | ITM-C-38, C-39 |
| `create_item` | R11 | ITM-C-40 |
| `create_item` | Errors row 1 (blank name / unit) [BUG-936] | ITM-C-11 … C-15 (xfail) |
| `create_item` | Errors row 2 (SKU taken) [BUG-946] | ITM-C-24, C-25, C-32 (xfail) |
| `create_item` | Errors row 3 (tag not found) [BUG-944] | ITM-C-35, C-36 (xfail) |
| `create_item` | Errors row 4 (tag not active) [BUG-943] | ITM-C-37 (xfail) |
| `create_item` | Errors row 5 (unknown user / workspace) | ITM-C-38, C-39 |
| `create_item` | Returns, Side effects | ITM-C-01, C-33, C-40 |
| `update_item` | R1 | ITM-U-04 |
| `update_item` | R2 [BUG-941] | ITM-U-05, U-06 (xfail) |
| `update_item` | R2a [BUG-940] | Deferred |
| `update_item` | R3 [BUG-938] | ITM-U-07 (xfail), U-08 (xfail), U-25 (xfail) |
| `update_item` | R4 | ITM-U-01, U-02, U-03, U-11 |
| `update_item` | R5 | ITM-U-01, U-09, U-10, U-11, U-12, U-29 |
| `update_item` | R6 [BUG-936] | ITM-U-12 (xfail), U-13 (xfail), U-14 (xfail), U-15 (xfail), U-16 (xfail) |
| `update_item` | R6a [BUG-017] | ITM-U-17 (xfail) |
| `update_item` | R7 [BUG-942] | ITM-U-18 (xfail), U-19 (xfail), U-20 (xfail), U-21 (xfail), U-22 (xfail), U-32 |
| `update_item` | R8 [BUG-947] | ITM-U-23 (xfail), U-24 (xfail), U-25 (xfail) |
| `update_item` | R9 [BUG-939] | ITM-U-01, U-26 (xfail), U-27 (xfail), U-28 (xfail), U-29 (xfail), U-30 |
| `update_item` | R10 | ITM-U-01, U-02 |
| `update_item` | R11 | ITM-U-31, U-32 |
| `update_item` | R12 [BUG-934] | ITM-U-33, U-34 (xfail), U-35 (xfail), U-36 |
| `update_item` | R13 [BUG-935] | ITM-U-38 (xfail), U-39, U-40 (xfail) |
| `update_item` | R14 | ITM-U-36, U-37, U-41 (xfail BUG-935) |
| `update_item` | R15 [BUG-944, BUG-943] | ITM-U-42 (xfail), U-43 (xfail), U-40 (xfail — re-sent deleted tag not refused) |
| `update_item` | R16 | ITM-U-44 |
| `update_item` | R17 | ITM-U-45 |
| `update_item` | R18 [BUG-946] | ITM-U-19 (xfail BUG-942), U-46 (xfail), U-47, U-48, U-49, U-50 (xfail) |
| `update_item` | R19 (Q1 intended) | ITM-U-51 |
| `update_item` | R20 [BUG-931] | Deferred |
| `update_item` | Errors rows 1–2 (not found / other workspace / deleted) | ITM-U-04, U-05, U-06 (xfail), U-07 (xfail) |
| `update_item` | Errors row 3 (schema) [BUG-936, BUG-942] | ITM-U-13 … U-16, U-20 … U-22 (xfail) |
| `update_item` | Errors row 4 (SKU taken) [BUG-946] | ITM-U-46 (xfail) |
| `update_item` | Errors row 5 (bad / deleted tag) [BUG-944, BUG-943] | ITM-U-42, U-43 (xfail) |
| `update_item` | Errors row 6 (unknown user) | ITM-U-44 |
| `update_item` | Returns, Side effects | ITM-U-01, U-26 (xfail), U-45 |
| `get_item` | R1 | ITM-G-01, G-02, G-08 (xfail) |
| `get_item` | R2 | ITM-G-03, G-04 |
| `get_item` | R3 [BUG-937] | ITM-G-05 (xfail) |
| `get_item` | R4 [BUG-937] | ITM-G-06 (xfail), G-07 (xfail), G-08 (xfail) |
| `get_item` | R5 | ITM-G-01, G-03 |
| `list_items_filtered` | R1 | ITM-L-01 … L-06, L-09, D-13 |
| `list_items_filtered` | keyword-only signature | ITM-L-07 |
| `list_items_filtered` | Errors (negative limit) | ITM-L-08 |
| `count_items_filtered` | R1 | ITM-N-01, N-02, N-03, D-13 |
| `distinct_units` | R1 | ITM-UN-01, UN-02 |
| `find_similar_items` | R1 | ITM-FS-01, FS-07, FS-08, FS-09, FS-10, FS-11, FS-12 |
| `find_similar_items` | R2 | ITM-FS-01, FS-02, FS-06 |
| `find_similar_items` | R3 | ITM-FS-01, FS-03, FS-04 (xfail BUG-034) |
| `find_similar_items` | R4 | ITM-FS-01, FS-03, FS-05 |
| `find_similar_items` | R5 | ITM-FS-01 |
| `find_similar_items` | Errors (negative limit) | ITM-FS-11 |
| `delete_item` | R1 | ITM-D-03 |
| `delete_item` | R2 [BUG-941] | ITM-D-04, D-05 (xfail), D-83 (in use) |
| `delete_item` | R3 | ITM-D-06, D-13, D-36 |
| `delete_item` | R3a [BUG-940] | Deferred |
| `delete_item` | R4 | ITM-D-01, D-02 |
| `delete_item` | R5 | ITM-D-07 |
| `delete_item` | R6 | ITM-D-08 |
| `delete_item` | R7 [BUG-945] | ITM-D-09 (xfail) |
| `delete_item` | R8 | ITM-D-10 |
| `delete_item` | R9 (a) [BUG-948] | ITM-D-14, D-15, D-16, D-49, D-80, D-90, D-92, D-103, D-115 (xfail), D-25, D-26, D-36, D-37, D-86, D-91, D-99, D-104, D-105, D-106, D-123 |
| `delete_item` | R9 (b) [BUG-948] | ITM-D-17, D-50, D-80, D-93, D-103, D-115, D-127 (xfail), D-27, D-86, D-101, D-102, D-110 … D-114, D-123 |
| `delete_item` | R9 (c) [BUG-948] | ITM-D-18, D-19, D-20, D-51, D-81, D-84, D-87, D-89, D-90, D-116 (xfail), D-28, D-29, D-38, D-55, D-82, D-124 |
| `delete_item` | R9 (d) [BUG-948] | ITM-D-39, D-52, D-81, D-84, D-95, D-116, D-117, D-127, D-128 (xfail), D-30, D-124 |
| `delete_item` | R9 (e) [BUG-948] | ITM-D-21, D-22, D-23, D-53, D-81, D-96, D-116, D-118, D-120, D-121, D-122 (`replaced_item_id`), D-127, D-129 (xfail), D-31, D-32, D-33, D-34, D-125 |
| `delete_item` | R9 (f) [BUG-948] | ITM-D-24, D-54, D-81, D-97, D-116, D-119, D-127, D-130 (xfail), D-35, D-124 |
| `delete_item` | R9 (g) [BUG-948] | ITM-D-66, D-67, D-68, D-69, D-70, D-75, D-80, D-94, D-103, D-115, D-127 (xfail), D-76, D-77, D-86, D-100, D-107, D-108, D-109, D-123 |
| `delete_item` | R9 (h) [BUG-948] | ITM-D-71, D-72, D-73, D-74, D-75, D-80, D-85, D-88, D-98, D-116, D-127, D-131 (xfail: D-85 waste, byproduct, quantity 0), D-78, D-79, D-126 |
| `delete_item` | R9 intro: cross-workspace row blocks, shown only as the generic entry [BUG-948] | ITM-D-49 … D-54, D-69, D-73 (row and parents in W2), D-92 … D-98 (one W2 row on a W1 parent per card), D-80, D-81 (the same shapes combined), D-87, D-88, D-117, D-118, D-119 (W1 lines on W2 parents), D-120, D-121, D-122 (`replaced_item_id`), D-133 (unknown user), D-56, D-89, D-128 … D-132 (with normal entries) (all xfail) |
| `delete_item` | R9 intro: cross-workspace row in a non-blocking state | ITM-D-55, D-91, D-123 … D-126; deleted parent: D-104 … D-114 |
| `delete_item` | R9 intro: factory, machine, stage, production line not part of the test [BUG-948] | ITM-D-90, D-127 (xfail), D-82 |
| `delete_item` | R9 intro: checked after R1–R3 | ITM-D-36 (already deleted), D-83 (other workspace) |
| `delete_item` | R9 (a), (b), (g), R9a: stock with a deleted parent does not block; the row stays | ITM-D-86, D-99 … D-102, D-104 … D-114; D-115 (xfail, beside a live blocker) |
| `delete_item` | R9 (a), (b), (g): `is_active` of the factory or machine is not looked at, only deactivated still blocks [BUG-948] | ITM-D-103 (xfail) |
| `delete_item` | R9a: orders and batches tied to a deleted factory still block [BUG-948] | ITM-D-116 (xfail) |
| `delete_item` | R9b [BUG-948] | ITM-D-39, D-40, D-41, D-42, D-43, D-44, D-66, D-71 (one blocker per type), D-45 (type order), D-46, D-74 (one entry per order / batch), D-47, D-70 (one entry per stock row, by id), D-48 (with an unknown user), D-49 … D-54, D-69, D-73, D-87, D-88, D-92 … D-98 (generic entry alone, exact), D-56, D-80, D-81 (several rows, one generic entry), D-56 (normal entries, then the generic one, last; work order before transfer order), D-89 (lines judged one at a time), D-75 (transfer order, product stock, production batch; batches by id), D-84, D-85, D-90, D-103, D-116, D-127 (several blockers, in order), D-115 (blockers with a deleted parent left out), D-117 … D-122, D-133 (generic entry alone, exact), D-128 … D-131 (lines judged one at a time, per type), D-132 (normal work and transfer order; generic entry last) (all xfail) |
| `delete_item` | R9a | ITM-D-57, D-58 (ledgers), D-59, D-60 (returns), D-61, D-62 (work-order template, by `item_id` and `replaced_item_id`), D-63, D-64 (formula line and stage), D-65 (project component); D-86, D-99 … D-102, D-104 … D-114 (stock with a deleted parent); ITM-D-25 … D-35, D-37, D-38 (not-blocking states of R9, rows unchanged); D-84 (xfail BUG-948: the order line of a return still counts). Order templates have no item column: nothing to test |
| `delete_item` | R9a, last paragraph (not decided) | No case; Spec gap 8 |
| `delete_item` | R10 | ITM-D-11 |
| `delete_item` | R10a [BUG-948] | ITM-D-48, D-133 (xfail) |
| `delete_item` | R11 | ITM-D-12 |
| `delete_item` | R12 | ITM-D-13; ITM-G-05, U-07 (on a deleted item) |
| `delete_item` | R13 [BUG-931] | Deferred |
| `delete_item` | Errors row 1–2 (missing / other workspace) | ITM-D-03, D-04, D-05 (xfail) |
| `delete_item` | Errors row 3 (already deleted) | ITM-D-06, D-36 |
| `delete_item` | Errors row 4 (in use, also with an unknown user) [BUG-948] | ITM-D-14 … D-24, D-39, D-45, D-48, D-66, D-71, D-84, D-90, D-103, D-115, D-116, D-127 (xfail) |
| `delete_item` | Errors row 5 (cross-workspace row, alone or with normal blockers) [BUG-948] | ITM-D-49 … D-54, D-56, D-69, D-73, D-80, D-81, D-87, D-88, D-89, D-92 … D-98, D-117 … D-122, D-128 … D-133 (xfail) |
| `delete_item` | Errors row 6 (unknown user, item not in use) | ITM-D-11 |
| `delete_item` | Returns, Side effects | ITM-D-01, D-12, D-14, D-39, D-66, D-71 (xfail) |
| `_assign_tags_to_item` | R1 | ITM-A-01, C-33, U-33 |
| `_assign_tags_to_item` | R2 [BUG-944] | ITM-A-02, A-03, A-04, A-05 (xfail) |
| `_assign_tags_to_item` | R3 [BUG-943] | ITM-A-06 (xfail) |
| `_assign_tags_to_item` | R4 [BUG-944] | ITM-A-07, A-08, A-09 (xfail) |
| `_assign_tags_to_item` | R5 | ITM-A-10, A-11 |
| `_assign_tags_to_item` | R6 | ITM-A-12 |
| `_assign_tags_to_item` | R7 | ITM-A-01, A-13 |
| `_assign_tags_to_item` | Errors rows 1–2 | ITM-A-02 … A-06, A-09 (xfail) |
| `get_tags_for_item` | R1 | ITM-TI-01, TI-02 |
| `get_tags_for_items` | R1 | ITM-TS-01, TS-02 |
