# Spec — `app/managers/item_manager.py`

> **Status:** APPROVED (2026-10-18). No open review question: the former open point Q2 (d) — open sales orders — was answered by the owner on 2026-10-18 (see Q2): a line on a not-completed sales order blocks, and the refusal names every blocker (`delete_item` R9 (d), R9b). Stays APPROVED after fill-gaps of 2026-10-30 (gaps 4, 5, 6 — see Gap log). Finished-goods stock and open production batches, raised that day, were answered by the owner the same day: both block (`delete_item` R9 (g), (h)). Four history tables remain **not decided** (`delete_item` R9a, last paragraph). They hold up no rule: nothing is tested for them.
> **Source commit:** e48a092

> **Review round 2026-10-18.** Decided by Claude under the reviewer's delegation (2026-10-18): every suggested answer is accepted — P1–P8 (bug: BUG-940 … BUG-947), P9 (`remove`, two dead-branch entries), Q1 (`intended`: item names are not unique — warn, don't block, as account names; names are still trimmed and never blank, BUG-936) and every house-rule / reused-bug line (BUG-936 … BUG-939; BUG-017, BUG-931, BUG-934, BUG-935 cited, no new ID). None of these is the reviewer's own answer. **Q2 is the reviewer's own answer (the owner, 2026-10-18), verbatim choice "Refuse while in use"** → `bug`, 🐞 BUG-948 (pattern `delete-ignores-dependents`, as BUG-876 for accounts with open invoices); `delete_item` R9 rewritten to the intended behavior with the per-order-type facts read from the models and order managers, R9a added (what does not block). One sub-point of it — open sales orders, R9 (d) — does not map onto "completed, cancelled or voided" and is left to the owner (above). The "(pilot default — awaiting reviewer)" markers were removed; no other rule changed. BUG-936 … BUG-947 and the two P9 dead-code entries now carry the delegation wording; BUG-948 is logged in `docs/testing/bugs.md`.

> **Review round 2026-10-18 (second owner answer, Q2 (d)).** The owner's words, verbatim: *"show user that hey these are things that are stopping you from blocking, its a frontend thing but just make notes in the bugs"*. **Reading by the main session (not the owner's words)**, together with the earlier answer "Refuse while in use": when the delete is refused, the user must be shown exactly which things stop it. So (1) R9 (d): a line on a not-completed sales order blocks like the other order types — an abandoned sales order no longer blocks "forever" in practice, because the refusal names it and the user can complete it; (2) `replaced_item_id` on a work-order line keeps counting (R9 (e) unchanged — the refusal names the work order); (3) new R9b: the refusal carries the full list of blockers (BUG-948); (4) showing that list is a frontend change — BUG-949 (FU-8); turning it into the 400 body is `ItemService`'s (FU-1). Rules changed: `delete_item` R9 (d), R9 intro, R9b (new), Errors row 4.

> **Review round 2026-10-30 (owner's answers to cases gaps 5 and 6; fill-gaps).** The owner's words, verbatim: *"go with your suggesting"* — accepting the suggestions put to them, recorded here as the owner's answers. **Gap 5 (superseded the same day, see the correction below):** any stock or order row that points at the item blocks the delete, whatever its `workspace_id`; blocking is by item id only. **Gap 6 (owner's answer):** yes, cover R9a's "does not block" rows, with the concrete tables, classes, import paths and NOT NULL columns given to the designer and checked by running. **Gap 4 — Claude's reading of the owner's answer, not the owner's words** (the owner gave no separate wording): the in-use refusal wins over the unknown-user error, because the R9 check runs first and raises before any write, so no foreign-key error occurs. Rules changed: `delete_item` R9 intro, R9a, R9b, R10, R10a (new), Errors row 5; Notes for the test designer (two new entries); FU-1 (one sentence). No new bug: everything that differs from today is BUG-948.

> **Review round 2026-10-30 (owner's answer on finished goods and batches).** The owner's choice, verbatim: *"Both block"*: finished-goods stock and open production batches stop an item being deleted. Rules changed: `delete_item` R9 (g), (h) (new), R9 intro, R9b, R9a (last paragraph), Errors row 4; Notes for the test designer (one new entry). No new bug: BUG-948. **Applied by Claude, not the owner's words:** in (g) a soft-deleted `products` row does not block (standing decision 1, as `inventory` in R9 (a)); the `type` strings and their sort position.

> **Review round 2026-10-30 (owner's correction of gap 5).** The owner's words, verbatim: *"we don't want to allow cross workspace"* and *"it should block from happening"*. The earlier answer treated such rows as normal, which the owner never meant. Now: a stock, order or batch row linking across workspaces is invalid data and creating one must be refused (other modules' specs; a separate audit logs those paths). `delete_item` still refuses when such a row exists, but exposes nothing of the other workspace: one generic entry `{"type": "other_workspace"}`, no id, once however many rows, sorted last. That entry was Claude's recommendation; **the owner approved it on 2026-10-30, verbatim: *"yeah i agree with your recommendations"***. A delete of an item of another workspace stays as it is (R2, no leak). **Claude's reading, not the owner's words:** which rows count as cross-workspace (the row, and for a line its order or batch; not the factory, machine, stage or production line it points at), and lines judged one at a time. R9a, the sort of normal rows and every other rule for normal rows are unchanged. Rules changed: `delete_item` R9 intro, R9b, Errors (new row 5); Notes entry "Cross-workspace rows"; FU-1, FU-5, FU-8. No new bug: BUG-948.

> **Review round 2026-10-30 (owner's answer to `machine_item_manager` Q5).** Stock on a deleted machine does not block `delete_item`, because no list shows it and the user cannot clear it. **Claude's reading, not the owner's words:** this includes a machine of a deleted factory, and "deleted" is `is_deleted`, not `is_active`. A cross-workspace row follows the same state rule (R9 intro). R9 (a) and (g) are unchanged: stock held in a deleted factory still blocks (*superseded by the next note*). Rules changed: `delete_item` R9 (b), R9a, R9b; Notes (one new entry, one widened). No new bug: BUG-948.

> **Review round 2026-10-31 (owner's answer on deleted factories).** Stock held directly in a deleted factory also does not block `delete_item`: the same rule for R9 (a) `inventory` and (g) `products`, and the rows stay. These are the owner's own words, so the factory part of R9 (b) is no longer only Claude's reading. "Deleted" remains `is_deleted`: `is_active` alone is not deleted (*Claude's reading, carried over*). Cross-workspace rows follow the same state rule. Orders and batches are unchanged. Rules changed: `delete_item` R9 (a), (b), (g), R9a, R9b; Notes entries "Stock with a deleted parent" and "Cross-workspace rows". No new bug: BUG-948.

> **Pilot convention:** every question below carried a suggested answer, applied to the rules as a provisional default. All were accepted on 2026-10-18 (decided by Claude under the reviewer's delegation), except Q2, which the owner answered; nothing is provisional any more.
>
> **Standing reviewer decisions applied here (not asked again):**
> 1. Soft-deleted rows are kept but must not show up in lists or be counted (inventory DAO Q2, 2026-10-10). **For items and item tags "deleted" is `is_active = False`** (item DAO spec Q7 / Q8; item tag DAO standing decision 1): neither table has `is_deleted`; `delete_item` sets `is_active = False` and nothing else on the item.
> 2. Things of a soft-deleted parent are **hidden by the parent's state, their own rows untouched** ("hidden, not cascaded", 2026-10-11). A tag link belongs to its item and its tag: links of a deleted item and links to a deleted tag are kept (BUG-935; `delete_item` R5 holds today).
> 3. **BUG-934** (accepted 2026-10-17, item tag assignment DAO P2): `update_item` with `tag_ids` keeps the links and counters of tags that stay; only removed tags lose a link, only new tags get one. After the fix `update_item` no longer calls `ItemTagAssignmentDAO.remove_all_tags_from_item` (already on the dead-code list, "remove together with the fix of BUG-934"). Tagged here with BUG-934 — no new ID.
> 4. **BUG-935** (accepted 2026-10-17, assignment DAO P3): a tag save leaves links to deleted tags alone. Tagged here — no new ID.
> 5. **BUG-931** (accepted 2026-10-17, item tag DAO Q1): every counter change goes through `item_tag_dao.increment_usage_count` / `decrement_usage_count` and inherits it. Cited, not repeated.
> 6. Precedents for tags (item tag DAO FU-2, assignment DAO FU-1): attaching a deleted tag is refused (BUG-629 precedent → P4); unknown tag ids reject the call (BUG-871 precedent → P5); a deleted tag must not keep counting deleted items (BUG-877 precedent → P6).
> 7. Names: trimmed, never blank (HR-1). Whether item names must also be **unique** (HR-2) is asked in Q1, because the code and the item screen deliberately allow a duplicate after a warning — see Q1 before overriding.
> 8. "Whitespace" means what Python's `str.strip()` removes. Physical row order and collation order are **not** deterministic: no order recipe in this spec is called verified or deterministic.
>
> **Verified by running** (throwaway scripts `im_probe.py`, `im_probe2.py` against the test database, rolled back; nothing created or dropped): every "Today:" note below; the `items` table's indexes (primary key, `ix_items_id`, `ix_items_workspace_id`, `ix_items_workspace_active`, the trigram index `ix_items_name_normalized_trgm` — **no unique index**), constraints and their names, database defaults (only `id` and `item_type`), no trigger; create with padded / `""` / whitespace-only name and unit, a duplicate name and SKU, `item_type="service"`, an `ItemBase` input, `tag_ids` holding a valid id twice, an unknown id, `0`, `-1`, a tag of another workspace and a deleted tag; unknown user / workspace (constraint names); savepoint roll-back of a create; `get_item` own / other workspace / missing / deleted; every `update_item` and `delete_item` error message; update of a deleted item (fields and tags, counter raised); rename (`name_normalized` recomputed), `""` name, a stale `name_normalized` kept, `null` description / SKU ignored; `{}` by the user already stamped (nothing written) and by another user (stamped), an unchanged value by another user (stamped); `tag_ids` = same list (links re-created, new ids, `assigned_by` = saver, link to a deleted tag erased, its counter unchanged), `[A, 999]`, `[999]`, a deleted tag and a tag at counter 0 added, `None`, `[]`; `is_active: false` / `true` through update (counters untouched), delete → `is_active: true` → counter left at 0; delete (active tag −1, deleted tag unchanged, counter 0 stays 0, links kept), delete again, missing, other workspace, unknown user (counters untouched); the tag pass-throughs; `find_similar_items` exact match, short name, exclusion, rounding (7/19 → `0.3684`; 7/20 excluded today, BUG-034), `limit=0`. **Not run:** anything at the service / HTTP level; two concurrent transactions; the *intended* behavior of the bug rules.
>
> **Verified by running on 2026-10-30** (throwaway script `im_probe_gaps.py` against the test database, each scenario in a savepoint, everything rolled back; nothing created or dropped; today's code): with one row of each R9a table pointing at the item (returns `pending`, `completed` and `voided`; template line by `item_id` and by `replaced_item_id`), and with one row each of `products` (`qty` 7), `product_ledger`, `project_component_item_ledger`, `sales_delivery_items` and `production_batch_items` (batch `in_progress`), the row can be built and `delete_item` succeeds with every such row unchanged. Stock and open-order rows with `workspace_id` of another workspace (inventory, machine stock, purchase / sales / work / transfer order with its line and parents in that workspace; a W2 line on a W1 purchase order; a W1 purchase order on a W2 stage row) can be built and today's delete succeeds. An item in use deleted by an unknown user gives `IntegrityError` / `ForeignKeyViolation` `items_updated_by_fkey` today and the item stays live. Foreign keys to `items` and required columns read from the test database, not only from the models.
>
> **Also verified on 2026-10-30** (throwaway script `im_probe_gh.py`, same conditions, today's code): `products` rows with `qty` 7, −3 and 0, `is_deleted = True`, `is_active = False`, two rows for one factory with `is_available_for_sale` `True` and `False`, and a row of another workspace; `production_batch_items` lines on batches `draft`, `in_progress`, `completed` and `cancelled`, in the roles `input`, `output`, `waste` and `byproduct`, two lines on one batch, and a batch of another workspace. Every row builds and today's delete succeeds with it, rows unchanged. No check constraint or trigger on `products`, `production_lines`, `production_batches`, `production_batch_items`.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list — all accepted (decided by Claude under the reviewer's delegation, 2026-10-18; Q2 answered by the owner)
| # | What the code does today, in plain words | Answer (accepted) |
|---|---|---|
| P1 | Editing an item that does not exist, or deleting an item twice, gives "internal server error" | bug — answer "not found" (404) / "already deleted" (400), never 500 — BUG-940 |
| P2 | Editing or deleting an item of another workspace says "item N does not belong to workspace M", which tells the caller the item exists | bug — same "Item N not found" as for a missing item — BUG-941 |
| P3 | Clearing an item's description or SKU in the edit form does nothing: the old text stays | bug — sending empty (`null`) clears them; `null` for name, unit or type is refused — BUG-942 |
| P4 | A deleted tag can be put on an item, and its item count goes up | bug — refused with "Item tag N is not active" — BUG-943 |
| P5 | A tag id that does not exist is silently skipped; on edit the item's other tags are already gone by then | bug — the whole save is refused with "Item tag N not found", nothing changes — BUG-944 |
| P6 | Deleting an item lowers the item count of its active tags but not of its deleted tags | bug — every tag on the item counts one item less — BUG-945 |
| P7 | Two items can have the same SKU; the code's description promises a conflict error | bug — a SKU is unique per workspace among live items (ignoring case and outer spaces), backed by the database; empty SKU = no SKU — BUG-946 |
| P8 | The edit request can switch an item off or on (`is_active`): switching off skips the tag-count update a real delete does; switching on brings a deleted item back with its tag counts left too low | bug — remove `is_active` from the edit request; delete only through "delete item"; "restore item" is a feature to build — BUG-947 |
| P9 | Two "does the input have a tag list?" checks can never be false | remove — dead code (same as accounts) |
| Q1 | Item names are not checked for duplicates at all: "Bolt", "bolt " and "BOLT" can all exist; the item screen warns about similar names and offers "Create anyway" | intended — warn, don't block (as account names); names are still trimmed and never blank (BUG-936). Deliberately differs from the factory / section rule (unique names, HR-2), because the add-item screen offers "Create anyway" |
| Q2 | An item that still has stock or is on open purchase / sales / work / transfer orders can be deleted; its stock and order lines are not touched | **owner's answer (2026-10-18): "Refuse while in use"** — bug — refuse with 400 "Item has stock or open orders" — BUG-948. Sub-point (open sales orders) answered by the owner the same day: not-completed sales orders block too, and the refusal lists every blocker so the user can clear them (R9b; frontend part BUG-949) |

Already decided by house rules / existing bugs (kept as applied — decided by Claude under the reviewer's delegation, 2026-10-18):
- names stored with their spaces; blank names and blank units accepted → BUG-936 (HR-1; as BUG-896 / BUG-915);
- opening a deleted item by id still works → BUG-937 (HR-4; as BUG-897 / BUG-916);
- a deleted item can still be edited and tagged (its tags' counts go up) → BUG-938 (HR-4; as BUG-863);
- saving an item without changing anything can still record "last changed by" → BUG-939 (HR-9; as BUG-900 / BUG-919);
- units stored with their spaces → BUG-017 (cited, no new ID; the "trim on write" part of it lives here);
- saving an item's tags re-creates unchanged links → BUG-934; erases links to deleted tags → BUG-935; counters can lose concurrent changes → BUG-931 (all cited, no new ID);
- the catalog list / count / unit list / similar-name pass-throughs inherit the item DAO's bugs (BUG-011 … BUG-018, BUG-033, BUG-034) and the tag pass-throughs inherit BUG-932 / BUG-933 (cited, no new ID).

Needs the owner: Q2 (d) answered 2026-10-18; cases gaps 5 and 6, finished-goods stock and open production batches answered 2026-10-30. Not decided: four history tables (`delete_item` R9a, last paragraph). Nothing in this manager touches money.

### House-rule violations — applied automatically
> All kept as applied — decided by Claude under the reviewer's delegation (2026-10-18).

- **HR-1** `create_item` R3, `update_item` R6 — item names are stored exactly as typed (`"  Steel  Rod 22 m "` keeps its spaces); `""` and `"   "` are accepted as names on create and on update; a blank unit (`""`, `"  "`) is accepted too (units are labels — HR-1 covers "names/labels"). Intended: names stored trimmed; blank / whitespace-only name or unit rejected by `ItemCreate` / `ItemUpdate` (422), nothing written. Fix in `app/schemas/item.py` on the create / update schemas, not on `ItemBase`, which `ItemResponse` / `ItemWithTagsResponse` inherit. Trimming the unit on write is BUG-017 (cited).
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-936 (pattern `blank-name-accepted`; precedent BUG-896 / BUG-915). Rules: `create_item` R3, `update_item` R6. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-18).
- **HR-4** `get_item` R3, R4 — a deleted item (`is_active = False`) is returned by id (`GET /items/{id}/`, the item summary and the item's order list answer 200) although the catalog list hides it. Intended: `None` by default (404 at the API); a new `include_deleted=True` parameter returns it. Whether the summary / order pages of a deleted item must stay reachable (links from old orders) is a follow-up for those services (FU-3) — they would pass `include_deleted=True`.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-937 (pattern `get-returns-soft-deleted`; precedent BUG-897 / BUG-916). Rules: `get_item` R3, R4. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-18).
- **HR-4** `update_item` R3 — a deleted item can be edited: fields, tags and tag counters (verified: tagging a deleted item raised the tag's counter from 5 to 6, counting a deleted item). Intended: a deleted item is treated as not found — `ValueError("Item {id} not found")`, nothing written (per BUG-863 precedent, `mutation-on-soft-deleted`).
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-938 (pattern `mutation-on-soft-deleted`; precedent BUG-863). Rules: `update_item` R3. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-18).
- **HR-9** `update_item` R9 — `updated_by` is set on every successful update, so `{}`, `null` fields and unchanged values are stamped whenever the saver is not the user already stamped (verified: unchanged unit saved by another user → `updated_by` and `updated_at` changed). Intended: `updated_by` (and with it `updated_at`) written only when a field value or the item's set of active tags actually changes.
**Answer:** bug — per HR-9 (house rule)
**Resolution:** 🐞 BUG-939 (pattern `audit-stamp-on-noop`; precedent BUG-900 / BUG-919). Rules: `update_item` R9. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-18).

Checked and **not** violated: **HR-2** — not applied: see Q1 (names) and P7 (SKU). **HR-3** — units: BUG-017 already holds the intended behavior (trimmed on write here; grouped / filtered case-insensitively in the item DAO). **HR-5, HR-6, HR-7, HR-8** — this manager pages, orders and searches nothing itself; the pass-throughs inherit the item DAO's rules and bugs (BUG-013, BUG-016, BUG-018, BUG-033) and the tag pass-throughs BUG-932 / BUG-933. **HR-10** — item delete / edit and tag counters are not money, stock, approvals or external side effects: no lock. **HR-11 … HR-14** — no external system, no batch.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-10-18)

### P1. Editing a missing item, or deleting an item twice, answers 500 — 🐞 BUG-940
**Background:** The manager reports problems with a plain Python `ValueError`. `ItemService.update_item` / `delete_item` do not translate it, and the app has no `ValueError` handler, so it becomes the generic 500. `ItemService.delete_item` first calls `get_item` and answers 404 itself for a missing / other-workspace item, but `get_item` returns deleted items, so a second delete reaches the manager. Same root cause as BUG-124 (account manager P1).
**What happens today:** `PUT /items/{id}/` for an id that does not exist or belongs to another workspace → 500. `DELETE /items/{id}/` on an already-deleted item → 500 (`Item N is already deleted`). (Manager messages verified; the HTTP status follows from the handlers.)
**Example:** A user has an item open in two tabs, deletes it in one and presses Delete again in the other: "internal server error".
**Rules affected:** `update_item` R2a, `delete_item` R3a
**Answer:** bug — per BUG-124 precedent: these rejections reach the client as 4xx, never 500 — not found → 404 `Item with ID {id} not found`, already deleted → 400; the manager keeps raising `ValueError`, `ItemService` translates it (integration-only)
**Resolution:** 🐞 BUG-940 (pattern `wrong-error-type-uncaught`; precedent BUG-124) — decided by Claude under the reviewer's delegation (2026-10-18): the suggested precedent answer is accepted. Rules: `update_item` R2a, `delete_item` R3a (integration-only).

### P2. The "other workspace" message reveals that the item exists — 🐞 BUG-941
**Background:** `get_item` deliberately answers "nothing" for an item of another workspace ("don't leak existence"). `update_item` and `delete_item` use a different message for that case than for a missing id. Same root cause as BUG-440 (account manager P2).
**What happens today:** For an id of another workspace they raise `Item {id} does not belong to workspace {workspace_id}`; for a missing id `Item {id} not found`. (Through `DELETE` the service's pre-check hides it; through `PUT` it is hidden behind P1's 500 today and visible once P1 is fixed.)
**Example:** Workspace 5 sends `PUT /items/812/`: the text confirms item 812 exists in another workspace.
**Rules affected:** `update_item` R2, `delete_item` R2
**Answer:** bug — per BUG-440 precedent: an item of another workspace gets exactly the same error as a missing one, `Item {id} not found`
**Resolution:** 🐞 BUG-941 (pattern `existence-disclosure-403-vs-404`; precedent BUG-440) — decided by Claude under the reviewer's delegation (2026-10-18): the suggested precedent answer is accepted. Rules: `update_item` R2, `delete_item` R2.

### P3. Description and SKU cannot be cleared — 🐞 BUG-942
**Background:** The update drops every field sent as `null` (`exclude_none`). The item edit form sends `description: null` / `sku: null` when the user empties those boxes (`EditItemDialog.tsx`). Same root cause as BUG-608 / account manager P4.
**What happens today:** Once set, `description` and `sku` can only be replaced, never removed; the response is 200 as if it worked (verified: `null` → old value kept).
**Example:** An item's SKU "OLD-12" is retired. The user empties the SKU box and saves: 200, the item still shows "OLD-12".
**Rules affected:** `update_item` R7
**Answer:** bug — per BUG-608 precedent: an explicit `null` clears `description` and `sku`; `null` for `name`, `unit` or `item_type` is rejected with 422 by `ItemUpdate`; omitted fields stay unchanged; `tag_ids: null` keeps meaning "leave tags unchanged"
**Resolution:** 🐞 BUG-942 (pattern `exclude-none-blocks-clear`; precedent BUG-608) — decided by Claude under the reviewer's delegation (2026-10-18): the suggested precedent answer is accepted. Rules: `update_item` R7.

### P4. A deleted tag can be put on an item — 🐞 BUG-943
**Background:** Tags are soft-deleted (`is_active = False`); the tag picker and every tag list hide them. `_assign_tags_to_item` checks that the tag exists in the workspace but not that it is active (item tag DAO FU-2 (a)). For account tags the same gap was ruled a bug (BUG-629 precedent applied as account manager P8).
**What happens today:** A deleted tag's id in `tag_ids` is linked and its counter goes up (verified: 5 → 6), on create and on update. The link is invisible (deleted tags are hidden).
**Example:** Tag 7 "Obsolete" was deleted. A stale client sends `POST /items/` with `tag_ids: [7]`: the item is created, tagged "Obsolete" invisibly, and tag 7 now counts it.
**Rules affected:** `_assign_tags_to_item` R3, `create_item` R9, `update_item` R15
**Answer:** bug — per BUG-629 / account manager P8 precedent: a deleted tag being newly added is refused with `ValueError("Item tag {id} is not active")` (400 at the API), nothing written; a deleted tag the item already carries is not rechecked (its link stays — BUG-935)
**Resolution:** 🐞 BUG-943 (pattern `unvalidated-stored-reference` — a soft-deleted referenced row accepted, as BUG-822; decision per BUG-629 / account manager P8) — decided by Claude under the reviewer's delegation (2026-10-18): the suggested precedent answer is accepted. Rules: `_assign_tags_to_item` R3, `create_item` R9, `update_item` R13, R15.

### P5. Unknown tag ids are silently skipped — 🐞 BUG-944
**Background:** `tag_ids` may contain ids that do not exist or belong to another workspace. The helper skips them without an error. On update, every old link is removed *before* the new list is processed. Same root cause as BUG-871 (account manager Q1).
**What happens today:** The call succeeds and the bad ids are ignored (verified: `[A, 999]` → only A; on update `[999]` → the item has no tags left, 200; `0` and `-1` skipped too).
**Example:** An item has tags [Steel]. A client sends `tag_ids: [999]` (a typo) → 200 and the item has no tags at all; nobody learns 999 was ignored.
**Rules affected:** `_assign_tags_to_item` R2, R4, `create_item` R9, `update_item` R15
**Answer:** bug — per BUG-871 precedent: a tag id that does not exist in the workspace (also `0`, negative, another workspace's) rejects the whole create / update with `ValueError("Item tag {id} not found")` (404 at the API); all ids are checked before anything is written — no item, link, field or counter change
**Resolution:** 🐞 BUG-944 (pattern `silently-ignored-input`; precedent BUG-871) — decided by Claude under the reviewer's delegation (2026-10-18): the suggested precedent answer is accepted. Rules: `_assign_tags_to_item` R2, R4, `create_item` R9, `update_item` R15.

### P6. Deleting an item leaves its deleted tags counting it — 🐞 BUG-945
**Background:** Each tag's `usage_count` means "number of items with this tag". `delete_item` lowers the counter of the item's tags found by `get_tags_for_item`, which hides deleted tags (assignment DAO `get_tags_for_item` R2). Standing decision 1: deleted items must not be counted. For accounts the reviewer ruled that deleting the owner lowers each tag's count (BUG-877).
**What happens today:** Active tags −1 (floor 0); a deleted tag on the item keeps its count (verified: 9 stays 9). If the tag is restored later its counter is too high by one per item deleted meanwhile.
**Example:** Tag "Imported" (counter 30) is deleted by mistake; 4 of its items are then deleted; the tag is restored: it shows 30 although 26 live items carry it.
**Rules affected:** `delete_item` R7
**Answer:** bug — per BUG-877 precedent: deleting an item lowers by 1 (never below 0) the counter of **every** tag linked to it in the workspace, deleted tags included; the links are kept
**Resolution:** 🐞 BUG-945 (pattern `stale-usage-count`; precedent BUG-877) — decided by Claude under the reviewer's delegation (2026-10-18): the suggested precedent answer is accepted. Rules: `delete_item` R7.

### P7. Two items can share a SKU — 🐞 BUG-946
**Background:** `sku` is the item's "stock keeping unit / part number" (model comment), optional free text. `ItemService.create_item`'s docstring says it raises a conflict "if item with same name/SKU exists", but nothing checks it and the table has no unique index (verified). For account codes the reviewer ruled the same gap a bug (BUG-874: non-empty code unique per workspace among live rows, trimmed, case-insensitive, partial unique index, 409; blank = no code). (The name half of the docstring is Q1.)
**What happens today:** Any number of live items carry the same SKU (verified: two items "S1"); SKUs are stored as typed (`"  "` stored as `"  "`).
**Example:** "Bolt M8" has SKU `B-M8`. A user creates "Hex bolt M8" with SKU `b-m8 `: 201; scanning or searching `B-M8` now finds two items.
**Rules affected:** `create_item` R7, `update_item` R18
**Answer:** bug — per BUG-874 precedent: a SKU is stored trimmed, an empty / whitespace-only SKU is stored as `NULL` (no SKU); a non-empty SKU is unique per workspace among live items, compared trimmed and case-insensitively, checked by the manager (`ValueError("Item with SKU '{sku}' already exists")`, 409 at the API) and backed by a partial unique index on live rows; a database violation also surfaces as 409, never 500; a deleted item's SKU can be reused
**Resolution:** 🐞 BUG-946 (pattern `python-only-uniqueness`; precedent BUG-874) — decided by Claude under the reviewer's delegation (2026-10-18): the suggested precedent answer is accepted. Rules: `create_item` R7, `update_item` R18.

### P8. The edit request can delete or restore an item, bypassing the tag counters — 🐞 BUG-947
**Background:** `ItemUpdate` has an `is_active` field, and `is_active` is the item's soft-delete flag. "Delete item" (`DELETE /items/{id}/`) also lowers the item's tag counters; the edit path does not. There is no "restore item" feature; the item edit form never sends `is_active` (`EditItemDialog.tsx`). Same root cause as BUG-751 (a client-writable field that only a system path should set).
**What happens today:** `PUT` with `is_active: false` deletes the item without lowering any counter (verified: 7 stays 7). `PUT` with `is_active: true` brings a deleted item back but does not raise the counters "delete item" lowered (verified: create → 1, delete → 0, restore → 0 while the item carries the tag).
**Example:** An integration "archives" items with `PUT {is_active: false}`: tag "Steel" still counts 40 items although the catalog shows 25.
**Rules affected:** `update_item` R8
**Answer:** bug — per BUG-751 precedent: `is_active` is removed from `ItemUpdate` (a sent `is_active` is ignored like any unknown field); items are deleted only through `delete_item`; "restore item" is a feature to build (FU-4), not this method
**Resolution:** 🐞 BUG-947 (pattern `client-writable-internal-field`; precedent BUG-751) — decided by Claude under the reviewer's delegation (2026-10-18): the suggested precedent answer is accepted. Rules: `update_item` R8. Follow-up FU-4.

### P9. "Input has no tag list" checks can never be true — remove
**Background:** `create_item` and `update_item` test `hasattr(item_data, 'tag_ids')` before reading it. Their inputs are always `ItemCreate` / `ItemUpdate`, which always have that field. The same checks in `AccountManager` were ruled dead code (account manager Q11).
**What happens today:** The "no attribute" side is never taken from the API; in a unit test it can only be reached by passing another class (e.g. `ItemBase`, which then creates an item without tags — verified).
**Example:** No request can reach it; the checks only add an untestable branch.
**Rules affected:** `create_item` R8, `update_item` R11
**Answer:** remove — per account manager Q11 precedent — decided by Claude under the reviewer's delegation (2026-10-18). Logged in `docs/testing/dead-code-removal-checklist.md` (two branch entries). Not a bug — no BUG ID.

### New questions

### Q1. Must item names be unique? — ✅ intended
**Background:** HR-2 applies "where names must be unique". Nothing in the item code checks names: no Python check, no index (verified). Instead the product has a duplicate *warning*: before creating, the item screen calls `GET /items/similar/` (normalized names: case, spacing and punctuation ignored, `"22 m"` = `"22m"`), shows exact and close matches, and offers **"Use existing item"** or **"Create anyway"** (`AddItemDialog.tsx`, `ItemSimilarMatchDialog.tsx`). Account names were ruled "duplicates allowed" (account manager Q5). The main session's instructions for this review say "names … unique per workspace (HR-1, HR-2)"; applying that here would remove the "Create anyway" choice and need a data clean-up before the unique index can be built — so it is asked, not applied.
**What happens today:** "Bolt", "bolt " and "BOLT" can all be live items of one workspace (verified: "Bolt" and "bolt " created). The only obstacle is the warning dialog, which the user can pass.
**Example:** A user types "Steel Rod 22 m"; the dialog shows "Steel rod 22m — Exact match"; the user presses "Create anyway": a second item with the same normalized name exists.
**Rules affected:** `create_item` R6, `update_item` R19
**Suggested answer:** `intended` — item names are not unique; warn, don't block (the similar-name check and "Create anyway" are the deliberate design, as for account names). Names are still trimmed and never blank (HR-1, BUG-936). Alternative: `bug — per HR-2: unique per workspace among live items` — then say which key: (a) HR-2's lower-case of the trimmed name ("Bolt" = " bolt ", but "Bolt-M8" ≠ "Bolt M8"), or (b) the stored `name_normalized` ("Bolt-M8" = "Bolt M8" = "bolt m8"); 409 on a clash, partial unique index on live rows, and the "Create anyway" button must go.
**Answer:** intended — warn, don't block, as for account names; names are still trimmed and never blank (BUG-936). Decided by Claude under the reviewer's delegation (2026-10-18).
**Resolution:** item names are not unique: `create_item` R6 ✅, `update_item` R19 ✅ unchanged. This **deliberately differs from the factory / section rule** (names unique per workspace / factory, HR-2 — BUG-893 … BUG-895, BUG-911 … BUG-914): the add-item screen runs the similar-name check and offers **"Create anyway"**, so a duplicate item name is a product choice the user makes after a warning. HR-2 does not apply to item names; HR-1 does (BUG-936).

### Q2. An item with stock or open orders can be deleted — 🐞 BUG-948 (owner's answer; sub-point (d) answered too — frontend part BUG-949)
**Background:** Deleting an item is a soft delete (`is_active = False`); its rows elsewhere stay. Stock rows (`inventory`), ledger rows and order lines of purchase, sales, work and transfer orders point at items. `delete_item` looks at none of them and changes none of them. Outside the item DAO and this manager no code reads `Item.is_active` (searched `app/`): stock lists, order screens and order creation keep working with a deleted item. For factories the reviewer decided "intended — hidden, not cascaded; nothing blocks the delete" (factory manager Q2); for accounts with open invoices "refuse the delete" (BUG-876). This touches stock and order workflow, so it is the owner's call.
**What happens today:** Any live item is deleted, whatever stock or orders it has (verified: the manager never queries them). Its stock quantity and order lines are unchanged.
**Example:** "Copper wire 2.5 mm" has 400 m in stock (stock value 120 000) and is on an open purchase order for 1 000 m. A user deletes it: 204. The item vanishes from the catalog and the item pickers; the 400 m and the open order line remain, and receiving the order still books stock for the deleted item.
**Rules affected:** `delete_item` R9
**Suggested answer:** `intended` — follow the factory decision: nothing is cascaded and nothing blocks the delete, so that a restore brings everything back as it was. Alternative: `bug — refuse with 400 ("Item has stock or open orders") while the item has a non-zero stock quantity in any factory / machine, or is on a purchase / sales / work / transfer order that is not completed, cancelled or voided`. Not applied — `delete_item` R9 states today's behavior until the owner answers.
**Answer:** bug — refuse with 400 ("Item has stock or open orders") while the item has a non-zero stock quantity in any factory / machine, or is on a purchase / sales / work / transfer order that is not completed, cancelled or voided. **The reviewer's own answer (the owner, 2026-10-18), verbatim choice: "Refuse while in use".**
**Resolution:** 🐞 BUG-948 (pattern `delete-ignores-dependents`, as BUG-876 for accounts with open invoices). Rules: `delete_item` R9 (rewritten to the intended behavior, tagged), R9a (new, untagged — what does not block; holds today). The answer was made testable from the models and the order managers (re-read 2026-10-18): stock = `inventory.qty` per factory and `machine_items.qty` per machine; "not completed, cancelled or voided" per order type = purchase: `voided = False` and stage name ≠ `Complete`; work: `status` `DRAFT` / `IN_PROGRESS` on a live order and live line; transfer: `completed_at` NULL; sales: `order_completed = False` (see below). The manager raises `ValueError("Item has stock or open orders", <blockers>)` (R9b); the 400 is `ItemService`'s translation (FU-1), like every other error of this manager.
**Sub-point (R9 (d), open sales orders) — was open, now answered:** sales orders do not map onto "completed, cancelled or voided". What exists: `sales_orders.order_completed` (boolean, default `False`; set `True` by "mark complete", which requires every line delivered / fulfilled and no open return; set back to `False` when a return starts on a completed order). There is **no** cancelled or voided state and **no** delete for a sales order (`current_status_id` is still a NOT NULL column but no longer read or written by the sales flow). Read literally, every line on a not-completed sales order blocks — so an abandoned sales order that can never be completed would keep the item from being deleted for good. **Question for the owner:** does a line on a sales order with `order_completed = False` block the delete (literal reading), or only under some further condition (e.g. undelivered quantity remaining)? A line on a completed sales order (`order_completed = True`) does not block either way — that part is decided.
**Owner's answer to the sub-point (2026-10-18), verbatim:** "show user that hey these are things that are stopping you from blocking, its a frontend thing but just make notes in the bugs".
**Reading (by the main session, not the owner's words), with the earlier "Refuse while in use":** when the delete is refused the user must be shown exactly which things stop it. (1) A line on a sales order with `order_completed = False` **blocks** (literal reading, like the other order types); an abandoned sales order no longer blocks "forever" in practice, because the refusal names the order and the user can complete it. (2) `replaced_item_id` on a work-order line keeps counting (R9 (e) as written — the refusal names the work order, so the user knows why). (3) The refusal carries **every** blocker, not only the first (R9b, BUG-948). (4) Showing that list is a frontend change — BUG-949, FU-8; the 400 body is `ItemService`'s — FU-1.
**Resolution (sub-point):** `delete_item` R9 (d) rewritten (tagged BUG-948), R9b added (tagged BUG-948), Errors row 4 updated. The open point is closed.
**Owner's answers to the case designer's gaps (2026-10-30), verbatim "go with your suggesting":** (gap 5, superseded below) any stock or order row that points at the item blocks the delete, whatever its `workspace_id` — blocking is by item id only; (gap 6) cover R9a's "does not block" rows, with the concrete rows given to the designer.
**Reading of the same answer (by Claude, not the owner's words), gap 4:** the in-use refusal wins over the unknown-user error — the R9 check runs first and raises before any write, so no foreign-key error occurs.
**Resolution (gaps):** `delete_item` R9 intro, R9a, R9b, R10, R10a (new), Errors row 5. No new bug ID (BUG-948).
**Owner's answer on finished goods and batches (2026-10-30), verbatim choice "Both block":** finished-goods stock and open production batches stop an item being deleted. **Resolution:** `delete_item` R9 (g), (h) (new); R9b gains the types `product_stock` and `production_batch`. No new bug ID (BUG-948).
**Owner's correction of gap 5 (2026-10-30), verbatim:** "we don't want to allow cross workspace", "it should block from happening". **Owner's approval of the generic entry (2026-10-30), verbatim:** "yeah i agree with your recommendations". **Resolution:** a row linking across workspaces is invalid data, creating one must be refused, and `delete_item` still refuses but shows only one `{"type": "other_workspace"}` entry, last (R9 intro, R9b). No new bug ID (BUG-948).

## Follow-ups for other reviews
> Nothing below is a rule of this manager and no bug is logged for it here except where an ID is given. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Item service / endpoints** (`app/services/item_service.py`, `app/api/v1/endpoints/items.py`) | Translate the manager's `ValueError`s: not found → 404, already deleted → 400 (BUG-940), unknown tag → 404 and deleted tag → 400 (BUG-944, BUG-943), duplicate SKU → 409 (BUG-946), item in use (`Item has stock or open orders`) → 400 (BUG-948) **whose body carries the message and the blockers**: raise the existing `app.core.exceptions.ValidationError(detail=exc.args[0], errors=exc.args[1])` — `APIException` already has an `errors: list[dict]` field that `api_exception_handler` emits as the RFC 7807 `errors` member, so the body is `{"type": …/validation_error, "title": "Validation Error", "status": 400, "detail": "Item has stock or open orders", …, "errors": [{"type": "factory_stock", "id": 7}, …]}` (R9b). The service may add display fields to each entry (factory name and quantity, order number, stage) so the UI can say "400 m in stock at Main Plant" / "Purchase order PO-12 (Receiving)" without more requests — decide in the service review; keep `type` and `id`. The entry `{"type": "other_workspace"}` passes through as it is, with no id and no display fields (`delete_item` R9b). Expose `include_deleted` on `GET /items/{id}/` (BUG-937). `ItemService.update_item`'s `if not item: raise NotFoundError` can never fire (the manager raises or returns the item) — dead branch for the service review. Docstring "ConflictError: if item with same name/SKU exists" (Q1, P7). `GET /items/` `limit` lower bound is BUG-016; `exclude_item_id` on `GET /items/similar/` is BUG-011. | P1, P5, P4, P7, HR-4 line |
| FU-2 | **Schemas** (`app/schemas/item.py`) | All schema-side fixes go on `ItemCreate` / `ItemUpdate`, not `ItemBase` (inherited by the responses): trim + non-blank `name` / `unit` (BUG-936; unit trim BUG-017), `null` handling (BUG-942), `is_active` removed (BUG-947), SKU trimmed / blank → `NULL` (BUG-946). | HR-1 line, P3, P7, P8 |
| FU-3 | **Item summary service** (`app/services/item_summary_service.py`) and **item orders service** (`app/services/item_orders_service.py`) | Both open the item through `get_item`; after BUG-937 a deleted item answers 404 there unless they pass `include_deleted=True`. Decide whether the summary / order history of a deleted item stays reachable (old orders link to it). The summary also shows `get_tags_for_item` (inherits BUG-932, assignment DAO P1). | HR-4 line |
| FU-4 | **"Restore item" feature** (to build; no method exists) | After BUG-947 nothing can bring a deleted item back. The future method must: refuse a missing / other-workspace / live item; set `is_active = True` and stamp `updated_by`; raise by 1 the counter of every tag linked to the item (deleted tags included — mirror of BUG-945); re-check the SKU (BUG-946) — and the name if Q1 is answered `bug`. | P8, P6 |
| FU-5 | **Managers that take an item id** (purchase / sales / work / transfer order managers, inventory and machine-item managers) | No code outside the item DAO / this manager reads `Item.is_active`: a deleted item can still be ordered, received or stocked. Whether each refuses a deleted item is for those reviews (workspace checks already logged: BUG-666, BUG-710, BUG-728). Order workflow → owner. Q2 answered by the owner (2026-10-18): a deleted item can no longer have stock or open order lines at the moment of deletion (BUG-948); whether those managers must also refuse a deleted item afterwards is still for those reviews. R9 (d) answered 2026-10-18: not-completed sales orders block too. Owner 2026-10-30: creating a stock, order or batch row that links across workspaces must be refused; each creation path is for that module's spec, and a separate audit logs them. | Q2, gap 5 |
| FU-6 | **Frontend** (`frontend/src/components/newcomponents/customui/EditItemDialog.tsx`) | The edit form sends `tag_ids: undefined` when no tag is selected, so the last tag of an item can never be removed from the UI (the backend handles `[]` correctly — `update_item` R14). | `update_item` R14 |
| FU-7 | **Item tag service** (`app/services/item_tag_service.py`) | Stored counter vs. live count (item tag DAO FU-1 (e)) — with BUG-943 / BUG-945 / BUG-947 fixed and FU-4 built, the stored counter equals the number of live items linked to the tag. | P4, P6, P8 |
| FU-8 | **Frontend item delete flow** (`frontend/src/pages/newpages/ItemsPage.tsx` `handleDelete`, via `useDeleteItemMutation` in `frontend/src/features/items/itemsApi.ts`) | 🐞 BUG-949: when the delete is refused, show the blocker list (R9b, carried in the 400 body's `errors` — FU-1), not only the message; today the catch shows `data.detail` (a string) in a toast. The list can hold `{"type": "other_workspace"}`, with no id: show a plain line for it, with no link. No test here. | Q2 (d), owner 2026-10-18; gap 5 |

## Overview
`ItemManager` owns the item catalog of a workspace — materials, parts, supplies and services — and the tag links of each item ("Bolt M8" tagged "Steel"). It is called only by services: `ItemService` (create, get, update, delete, the catalog list / count / units / similar names, the tag chips) behind `/items/`, `ItemSummaryService` (`get_item`, `get_tags_for_item`) behind `GET /items/{id}/summary/`, and `ItemOrdersService` (`get_item`) behind `GET /items/{id}/orders/`. It is meant to protect workspace isolation (an item and the tags it gets belong to the caller's workspace), soft-delete semantics (a deleted item is hidden and cannot be edited), and each tag's `usage_count` = the number of live items carrying it. It never commits; the DAOs flush. Every write path changes tag counters only through the item tag DAO (BUG-931).

The class docstring says "Manages: Item entity only (no children)" and "Operations: CRUD, search" — out of date: it also manages tag links and tag counters. The code wins.

**Callables:** 11 specified · 3 not specified
**Externals to mock:** none. (`created_at` and `updated_at` are filled by Python column defaults / `onupdate` bound to `app.utils.time.utcnow` at import — patching does not change them; assert set / not set only. A tag link's `assigned_at` likewise.)
**Integration-only behavior:** the HTTP status of the manager's `ValueError`s (BUG-940 and the tag / SKU errors — FU-1); `ItemCreate` / `ItemUpdate` validation becoming 422; the `GET /items/` and `GET /items/similar/` query bounds; the service's commit / rollback and `db.refresh`.

**Facts for the test designer**
- Import: `from app.managers.item_manager import ItemManager, item_manager`. `ItemManager()` takes no arguments; the singleton holds no per-call state. All parameters are positional-or-keyword except `list_items_filtered` / `count_items_filtered` (everything after `workspace_id` keyword-only). Services call `get_item(db, item_id, workspace_id)` and `distinct_units(db, workspace_id)` positionally, the rest by keyword.
- Errors are plain `ValueError` (assert `str(exc)`) — except the intended in-use refusal of `delete_item` (R9b), which has two args: assert `exc.args[0]` (message) and `exc.args[1]` (blocker list), never `str(exc)`; database errors are `sqlalchemy.exc.IntegrityError` with `.orig` a `psycopg2` error class; schema errors are `pydantic.ValidationError`.
- Table `items` (`app.models.item.Item`): `id` PK; `workspace_id` NOT NULL FK `workspaces.id` ON DELETE CASCADE (`items_workspace_id_fkey`); `name`, `name_normalized`, `unit` varchar NOT NULL, no length limit; `description`, `sku` nullable; `created_by` / `updated_by` nullable FK `profiles.id` (`items_created_by_fkey` / `items_updated_by_fkey`); `is_active` boolean NOT NULL, Python default `True` — **the soft-delete flag**; `item_type` varchar(20) NOT NULL, default `'physical'` (Python and database); `created_at` NOT NULL (Python default), `updated_at` nullable (Python `onupdate` — set whenever an UPDATE of the row is emitted). Indexes: primary key, `ix_items_id`, `ix_items_workspace_id`, `ix_items_workspace_active (workspace_id, is_active)`, GIN trigram `ix_items_name_normalized_trgm` — **no unique index**. No trigger, no check constraint.
- `item_type` (`"physical"` / `"service"`) is stored and returned; no server code branches on it (only the `SalesOrderItem.item_type` display property reads it live).
- Schemas (`app/schemas/item.py`): `ItemCreate` = `name: str`, `unit: str` (required), `description`, `sku` (`str | None = None`), `item_type` (`Literal["physical","service"]`, default `"physical"`), `tag_ids: list[int] = []`. `ItemUpdate` = `name`, `description`, `unit`, `sku`, `item_type`, `is_active`, `tag_ids`, all optional `None`. No validators; unknown fields are ignored (`workspace_id`, `is_active` on create).
- `normalize_item_name(name)` (`app/utils/item_name_normalize.py`): empty → `""`; lower-case, trim, collapse whitespace, glue a number to a following 1–4 letter word (`"22 m"` → `"22m"`), replace every non-word, non-space character by a space, collapse and trim again (`"  Steel  Rod 22 m "` → `"steel rod 22m"`, `"New  Name-2"` → `"new name 2"`, `"!!!"` → `""`). Its own edge cases belong to the utility's spec.
- Tags: `ItemTag` (`workspace_id`, `name`, `tag_code` NOT NULL; `is_active` default `True` = not deleted; `usage_count` default `0`, no check constraint). Links: `ItemTagAssignment` (`workspace_id`, `item_id`, `tag_id` NOT NULL; `assigned_by` nullable; unique `uq_item_tag (item_id, tag_id)`; no soft-delete column). Model facts in `tests/unit/dao/item_tag.spec.md` and `tests/unit/dao/item_tag_assignment.spec.md`.
- Collaborator rules cited (not repeated): item DAO `tests/unit/dao/item.spec.md`; item tag DAO `increment_usage_count` R1–R6, `decrement_usage_count` R1–R7 (floor 0, `None` for a foreign / unknown tag, works on deleted tags, BUG-931); assignment DAO `get_tags_for_item` R1–R5, `get_tags_for_items` R1–R7, `assignment_exists` R1–R5, `remove_all_tags_from_item` R1–R6, inherited `create` R1–R3.

**Notes for the test designer**
- Workspaces and profiles from `tests/unit/factories.py` (`make_workspace`, `make_profile`). Build tags (`ItemTag` with `tag_code`, explicit `usage_count`) and, where a case needs an existing item / link, `Item` (with `name_normalized`, `unit`) and `ItemTagAssignment` rows directly (add + flush). `autoflush=False`: flush before calling the manager.
- **Reading counters and links:** after a call, read `usage_count` and the link rows with a fresh `SELECT` (`text("select usage_count from item_tags where id=:i")`; links by `item_id`), not through loaded objects or `item.tag_assignments`. Compare link `id`, `assigned_by`, `assigned_at` before / after for BUG-934.
- **"Nothing written" (BUG-939, BUG-944, BUG-943, BUG-938):** `db.refresh(item)` before the call, then compare every column and every counter / link after it. For HR-9, set `updated_by` / `updated_at` to `NULL` with a SQL `UPDATE` and `db.expire(item)` first; note that today a call by the user already in `updated_by` with no change writes nothing (verified), so the HR-9 cases must use a **different** user than the stamped one to fail today.
- **Refusals** (`ValueError`) for missing / other-workspace / deleted rows happen before anything is written. Intended tag refusals (BUG-943, BUG-944) and the SKU refusal (BUG-946) must also leave nothing written — today the item is created / updated before tags are looked at, so those cases fail today (strict xfail). **Database errors** (foreign keys, the intended SKU index) abort the transaction: wrap the call in `with db.begin_nested():` inside `pytest.raises(...)`.
- **Database-level 409 (BUG-946):** simulate the race by inserting a second live item with the same SKU directly (expect `IntegrityError` on flush once the index exists), and by patching the manager's SKU check to report "free" (expect the manager's `ValueError` / 409 path, not a raw database error).
- **Schema rejections (BUG-936, BUG-942):** assert `pydantic.ValidationError` when constructing `ItemCreate` / `ItemUpdate`; the manager is never reached.
- **Order:** `find_similar_items` keeps the DAO's order (BUG-018 for ties); compare everything else as **sets** of ids. Tag pass-through order cases belong to the assignment DAO (BUG-932 / BUG-933), not here.
- Strict xfail (outcome does not depend on row order): BUG-934, BUG-935, BUG-936, BUG-937, BUG-938, BUG-939, BUG-941, BUG-942, BUG-943, BUG-944, BUG-945, BUG-946, BUG-947, BUG-948, BUG-017 (unit trim on write). BUG-940 is integration-only (service translation). BUG-931 cases belong to the item tag DAO.
- **Rows for BUG-948 (`delete_item` R9).** Build them directly (add + flush), all in the item's workspace. NOT NULL columns without a default (from the models): `inventory` — `workspace_id`, `item_id`, `inventory_type` (`InventoryTypeEnum` from `app.models.enums`), `factory_id`; `qty` defaults to 0, `is_deleted` to `False`; one row per (workspace, item, type, factory) (unique constraint `uq_inventory_workspace_item_type_factory`). `factories` — `workspace_id`, `name`, `abbreviation`. `machines` — `workspace_id`, `name`, `factory_id`. `machine_items` — `workspace_id`, `machine_id`, `item_id`; `qty` defaults to 0. `statuses` — `workspace_id`, `name`, `comment`. `purchase_orders` — `workspace_id`, `po_number`, `destination_type` (e.g. `'storage'`), `destination_id` (a factory id; not a foreign key), `current_status_id` (a `statuses` row named `Draft` / `Planning` / `Receiving` / `Complete`), `created_by`; `voided` defaults to `False`. `purchase_order_items` — `workspace_id`, `purchase_order_id`, `line_number`, `item_id`, `quantity_ordered`. `accounts` — `workspace_id`, `name`. `sales_orders` — `workspace_id`, `sales_order_number` (unique across all workspaces), `account_id`, `factory_id`, `current_status_id` (any `statuses` row; not read), `created_by`; `order_completed` defaults to `False`. `sales_order_items` — `workspace_id`, `sales_order_id`, `item_id`, `quantity_ordered`, `unit_price`, `line_total`. `work_order_types` — `workspace_id`, `name`. `work_orders` — `workspace_id`, `work_order_number`, `work_order_type_id`, `title`, `factory_id`; `status` defaults to `'DRAFT'`, `is_deleted` to `False`. `work_order_items` — `workspace_id`, `work_order_id`, `item_id`, `quantity`; `replaced_item_id` optional (another item for a line where the item under test is the replaced one); `is_deleted` defaults to `False`. `transfer_orders` — `workspace_id`, `transfer_number` (unique across all workspaces), `source_location_type` / `destination_location_type` (e.g. `'storage'`), `source_location_id` / `destination_location_id` (factory ids; not foreign keys), `current_status_id`, `created_by`; `completed_at` NULL = not completed. `transfer_order_items` — `workspace_id`, `transfer_order_id`, `line_number`, `item_id`, `quantity`. For "nothing written" read `items.is_active` / `updated_by` and the tag counters with a fresh `SELECT`; the stock / order rows must also be unchanged.
- **Rows for `delete_item` R9 (g), (h).** Add + flush. All built on 2026-10-30.
  | Table | Class, import | Required columns | Good to know |
  |---|---|---|---|
  | `products` | `Product`, `app.models.product` | `workspace_id`, `item_id`, `factory_id` | `qty` defaults to 0, `is_available_for_sale` to `False`, `is_active` to `True`, `is_deleted` to `False`. Unique `uq_product_workspace_item_factory_available` `(workspace_id, item_id, factory_id, is_available_for_sale)`: two rows of one item in one factory need different `is_available_for_sale`; the constraint ignores `is_deleted` |
  | `production_lines` | `ProductionLine`, `app.models.production_line` | `workspace_id`, `factory_id`, `name` | parent of a batch; `is_active` defaults to `True` |
  | `production_batches` | `ProductionBatch`, `app.models.production_batch` | `workspace_id`, `batch_number` (unique per workspace, `uq_batch_workspace_number`), `production_line_id`, `batch_date` (a date) | `status` defaults to `'draft'`; `formula_id` is optional; no soft-delete column |
  | `production_batch_items` | `ProductionBatchItem`, `app.models.production_batch_item` | `workspace_id`, `batch_id`, `item_id`, `item_role` (`'input'`, `'output'`, `'waste'`, `'byproduct'`) | quantities are optional; no soft-delete column |
- **Cross-workspace rows (`delete_item` R9, R9b, gap 5).** These are invalid data, not a normal state: a test builds one directly, because the creation paths must refuse it (other modules' specs, separate audit). No foreign key compares a row's workspace with the item's. Verified buildable, each with today's delete succeeding:
  - **Generic entry only:** `inventory`, `machine_items` and `products` with `workspace_id` W2, on parents of W2 or of W1; each order type, and a production batch, with order and line in W2 on parents of W2 (factory, machine, account, work-order type, stage, production line); a W2 line on an order of W1 (built for a purchase order; the shapes for the other orders and for a batch come from the existing cards); a W1 line on a W2 purchase, sales, work or transfer order or W2 batch (sales, work and transfer: verifier round 6, re-run 2026-10-31 with `im_probe_m.py`).
  - **Normal entry, not cross-workspace:** a W1 purchase order and W1 line on a stage row of W2; W1 stock on a factory of W2 (the row's own `id` is the caller's).
  - In a cross-workspace case, check `args[1]` by exact equality, so that an `id` or extra key fails. A cross-workspace row in a non-blocking state (order at stage `Complete`, `qty = 0`, a deleted machine or factory) gives no entry and the item is deleted.
- **Stock with a deleted parent (`delete_item` R9 (a), (b), (g), R9a).** Set `is_deleted = True` on the `machines` or `factories` row directly (`is_active` on its own means nothing here; the real machine delete sets both, the real factory delete sets only `is_deleted`). Built, with today's delete succeeding, `qty` 5 for machine stock: W1 row on a deleted W1 machine; W1 row on a live machine of a deleted W1 factory; W2 row on a deleted W2 machine; W2 row on a deleted W1 machine; W1 row on a deleted W2 machine; W2 row, and W1 row, on a live W2 machine of a deleted W2 factory. `qty` 7 for `inventory` and for `products` (`im_probe_f.py`, 2026-10-31): W1 row in a deleted W1 factory; W2 row in a deleted W2 factory; W2 row in a deleted W1 factory; W1 row in a deleted W2 factory.
- **Rows for `delete_item` R9a (gap 6).** Add + flush, on a live item of W1. "Required" = NOT NULL with no default (read from the test database and the models; none of these tables has a check constraint). All built and deleted-with on 2026-10-30.
  | Table | Class, import | Required columns | Good to know |
  |---|---|---|---|
  | `inventory_ledger` | `InventoryLedger`, `app.models.inventory_ledger` | `workspace_id`, `inventory_type` (`InventoryTypeEnum`), `factory_id`, `item_id`, `transaction_type` (free text, e.g. `'manual_add'`), `quantity`, `qty_before`, `qty_after` | `performed_at` has a database default. No link to `inventory`: a ledger row alone is a valid state |
  | `machine_item_ledger` | `MachineItemLedger`, `app.models.machine_item_ledger` | `workspace_id`, `machine_id`, `item_id`, `transaction_type`, `quantity`, `unit_cost`, `total_cost`, `qty_before`, `qty_after`, `source_type` (e.g. `'manual'`), `performed_by` (a `profiles` id) | `performed_at` has a Python default |
  | `purchase_order_returns` | `PurchaseOrderReturn`, `app.models.purchase_order_return` | `workspace_id`, `purchase_order_id`, `return_number` (unique across all workspaces), `created_by` | `status` defaults to `'pending'`; `return_type` to `'refund'`; `paid` to `False` |
  | `purchase_order_return_items` | `PurchaseOrderReturnItem`, same module | `workspace_id`, `return_id`, `po_item_id` (a `purchase_order_items` id), `item_id`, `quantity_returned` | needs a purchase-order line, see below |
  | `sales_order_returns` | `SalesOrderReturn`, `app.models.sales_order_return` | `workspace_id`, `sales_order_id`, `return_number` (unique across all workspaces), `created_by` | defaults as for purchase returns |
  | `sales_order_return_items` | `SalesOrderReturnItem`, same module | `workspace_id`, `return_id`, `so_item_id` (a `sales_order_items` id), `quantity_returned` | `item_id` is nullable (free-text lines); set it. Needs a sales-order line, see below |
  | `work_order_templates` | `WorkOrderTemplate`, `app.models.work_order_template` | `workspace_id`, `template_name`, `work_order_type_id` | parent of the next row |
  | `work_order_template_items` | `WorkOrderTemplateItem`, `app.models.work_order_template_item` | `workspace_id`, `work_order_template_id`, `item_id` | `quantity` defaults to 1, `action_type` to `'CONSUME'`; `replaced_item_id` optional (a second item with the item under test as the replaced one) |
  | `production_formulas` | `ProductionFormula`, `app.models.production_formula` | `workspace_id`, `formula_code`, `name` | parent of the next two rows; no unique constraint |
  | `production_formula_items` | `ProductionFormulaItem`, `app.models.production_formula_item` | `workspace_id`, `formula_id`, `item_id`, `item_role` (`'input'`, `'output'`, `'waste'`, `'byproduct'`), `quantity` | `is_optional` defaults to `False` |
  | `production_formula_stages` | `ProductionFormulaStage`, `app.models.production_formula_stage` | `workspace_id`, `formula_id`, `stage_order`, `name` | points at the item through `expected_output_item_id` (nullable); unique `(formula_id, stage_order)` |
  | `projects` | `Project`, `app.models.project` | `workspace_id`, `factory_id`, `name`, `description` | parent; other columns have defaults |
  | `project_components` | `ProjectComponent`, `app.models.project_component` | `workspace_id`, `project_id`, `name` | parent |
  | `project_component_items` | `ProjectComponentItem`, `app.models.project_component_item` | `workspace_id`, `project_component_id`, `item_id`, `qty` | |

  **Returns need an order line.** A return line must point at an order line, and that line names the item, so it can block by R9 (c) / (d) on its own. To show the return itself does not block, put the line on an order that does not block: a purchase order on stage `Complete` (or `voided = True`), a sales order with `order_completed = True`. The product's flows reopen an order when a return starts (purchase order back to `Receiving`, sales order to `order_completed = False`), so with a reopened order it is the order line that blocks, by R9, not the return. A `pending` return is the strongest state to build: it is the most open one and its `status` is not read.
  **`order_templates` / `order_template_items` have no row to build:** neither has an item column (`app.models.order_template_item` holds free-text expense lines). Nothing in those tables can point at an item.
- `find_similar_items` needs the `pg_trgm` extension (created by the baseline migration).

## Not specified
- `ItemManager.__init__` — stores the model and `item_dao`, no logic
- `ItemManager.search_items` — dead code, to be removed (item DAO spec Q4; already on `docs/testing/dead-code-removal-checklist.md`)
- `item_manager` — module-level singleton, no logic

Dead branches (P9, decided by Claude under the reviewer's delegation (2026-10-18)): the `hasattr(item_data, 'tag_ids')` checks in `create_item` (line 52) and `update_item` (line 112) — logged on the dead-code list. `ItemTagAssignmentDAO.remove_all_tags_from_item` loses its only caller with the BUG-934 fix (already listed). The checklist (`docs/testing/unit-test-checklist-by-layer.md`) marks nothing of this file as possibly unused. Legacy tests outside `tests/unit/` (`tests/test_items_list_pagination.py`, `tests/test_item_summary_empty.py`) only patch `list_items_filtered`, `count_items_filtered`, `get_tags_for_items`, `get_tags_for_item`, `get_item`.

---

## `ItemManager.create_item(session, item_data, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `ItemService.create_item` ← `POST /items/`)

**Purpose:** Create an item in the workspace's catalog and put the requested tags on it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session; not committed here |
| `item_data` | `ItemCreate` | `name`, `unit` (intended: trimmed, non-blank — BUG-936), `description`, `sku`, `item_type`, `tag_ids` (default `[]`) |
| `workspace_id` | int | caller's workspace; stored on the item and its links |
| `user_id` | int | creator; `created_by` and each link's `assigned_by` (FK `profiles.id`) |

**Returns:** the new `Item`, flushed (has an `id`), not committed.

**Rules:**
- **R1.** One item is created with `name`, `description`, `unit`, `sku`, `item_type` from the input, `workspace_id` = the argument, `created_by = user_id`, `is_active = True`, `created_at` set, and `updated_at`, `updated_by` `None`. `description` and `sku` are stored as given (`None` stays `None`; `""` stays `""` — SKU blank handling changes with BUG-946, R7).
- **R2.** `item_type` defaults to `"physical"`; `"service"` is stored as sent.
- **R3.** [BUG-936] (HR-1) The name is stored with leading / trailing whitespace removed (`"  Steel  Rod 22 m "` → `"Steel  Rod 22 m"`; inner whitespace and case kept); a blank or whitespace-only `name` or `unit` (`""`, `"   "`, `"\t"`) is rejected by `ItemCreate` itself (`ValidationError`, 422 at the API); nothing created. *(Today: stored as typed; `""` and `"   "` names and units are created.)*
- **R4.** [BUG-017] The unit is stored trimmed, case kept (`" Kg "` → `"Kg"`). *(Today: stored as typed — `" kg "` stays `" kg "`.)*
- **R5.** `name_normalized` = `normalize_item_name` of the stored name (`"  Steel  Rod 22 m "` → `"steel rod 22m"`; a name of only punctuation → `""`).
- **R6.** (Q1 — `intended`) Names are not checked for duplicates: a live item with the same name, a case / spacing variant, or the same `name_normalized` does not block the create (deliberately unlike factories / sections — Q1). ✅
- **R7.** [BUG-946] (P7) A sent SKU is stored trimmed; an empty / whitespace-only SKU is stored as `None`. A non-empty SKU already used by a live item of the workspace (compared trimmed, case-insensitively: `"B-M8"` = `" b-m8 "`) → `ValueError("Item with SKU '<sku>' already exists")` (`<sku>` = the trimmed value sent); nothing created. A deleted item's SKU, another workspace's SKU and `None` never block. The database refuses a second live item with the same normalised SKU in a workspace (partial unique index); when that is reached through the manager (concurrent request) the same `ValueError` is raised, not a database error. *(Today: no check, no index; SKUs stored as typed; two live items "S1" exist.)*
- **R8.** Given `tag_ids`, the tags are put on the item as `_assign_tags_to_item` R1–R8 describe; `tag_ids=[]` creates the item with no links. (P9 — `remove`: the "input without `tag_ids`" path is dead code and not tested.)
- **R9.** [BUG-944] [BUG-943] (P5, P4) If any requested tag is rejected (`_assign_tags_to_item` R2, R3), the create fails with that `ValueError` and **nothing** is created: no item, no link, no counter change. *(Today: the item is created; unknown / other-workspace / `0` / negative ids are skipped and a deleted tag is linked and counted.)*
- **R10.** Unknown `user_id` → `IntegrityError` (`ForeignKeyViolation`, `items_created_by_fkey`); unknown `workspace_id` → `IntegrityError` (`items_workspace_id_fkey`), before any tag is touched; nothing saved.
- **R11.** The item, its links and the counter changes are flushed, not committed: rolling back a savepoint around the call removes the item and restores the counters.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| blank name / unit [BUG-936] | `pydantic.ValidationError` building `ItemCreate` | not asserted |
| SKU taken by a live item [BUG-946] | `ValueError` | `Item with SKU '<sku>' already exists` |
| unknown / other-workspace / `0` / negative tag id [BUG-944] | `ValueError` | `Item tag <id> not found` |
| deleted tag [BUG-943] | `ValueError` | `Item tag <id> is not active` |
| unknown `user_id` / `workspace_id` | `IntegrityError` / `ForeignKeyViolation` | — |

**Side effects:** one `items` row inserted; one `item_tag_assignments` row per newly linked tag; each such tag's `usage_count` +1; all flushed. No commit. Nothing on any error (intended).

---

## `ItemManager.update_item(session, item_id, item_data, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `ItemService.update_item` ← `PUT /items/{id}/`; the item edit form sends `name`, `description`, `unit`, `sku` and `tag_ids` — `undefined` when no tag is selected, FU-6)

**Purpose:** Change a live item's fields and, when a tag list is sent, its set of tags, and record who edited it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session; not committed here |
| `item_id` | int | item to change |
| `item_data` | `ItemUpdate` | all fields optional; omitted = keep; `tag_ids`: `None` = leave tags alone, a list = the item's wanted set of active tags |
| `workspace_id` | int | caller's workspace |
| `user_id` | int | editor; `updated_by`, and `assigned_by` of new links |

**Returns:** the same `Item` instance that was read, modified and flushed, not committed.

**Rules:**
- **R1.** No item with that id → `ValueError("Item <item_id> not found")`; nothing written.
- **R2.** [BUG-941] (P2) An item of another workspace → the same `ValueError("Item <item_id> not found")`; nothing written. *(Today: `ValueError("Item <item_id> does not belong to workspace <workspace_id>")`.)*
- **R2a.** [BUG-940] (P1) At the API these refusals answer 404 `Item with ID <id> not found`, never 500 — the translation belongs in `ItemService` (integration-only). *(Today: 500.)*
- **R3.** [BUG-938] (HR-4) A deleted item (`is_active = False`) → `ValueError("Item <item_id> not found")`, whatever the request; nothing written — no field, link or counter change. *(Today: the item is updated; tags sent are linked and their counters raised although the item is deleted.)*
- **R4.** Each of `name`, `description`, `unit`, `sku`, `item_type` sent with a value is written; a field not sent keeps its value.
- **R5.** Whenever `name` is sent, `name_normalized` is recomputed from the stored (trimmed) name (`"New  Name-2"` → `"new name 2"`), also when the name equals the current one (a stale `name_normalized` is repaired). When `name` is not sent, `name_normalized` is not touched, even if stale (verified: `'stale'` kept after a unit change).
- **R6.** [BUG-936] (HR-1) A sent `name` is stored trimmed; a blank / whitespace-only `name` or `unit` is rejected by `ItemUpdate` (`ValidationError`), nothing written. *(Today: stored as typed; `""` is written and gives `name_normalized = ""`.)*
- **R6a.** [BUG-017] A sent `unit` is stored trimmed, case kept. *(Today: as typed.)*
- **R7.** [BUG-942] (P3) An explicit `null` clears `description` and `sku` (stored `None`); `null` for `name`, `unit` or `item_type` is rejected by `ItemUpdate` (`ValidationError`); `tag_ids: null` means "leave tags alone" (R11). *(Today: every `null` is dropped — `description` / `sku` keep their old values.)*
- **R8.** [BUG-947] (P8) `ItemUpdate` has no `is_active`: a sent `is_active` (either value) is ignored and the item's state does not change. *(Today: `is_active: false` deletes the item without lowering any tag counter; `is_active: true` brings a deleted item back without raising them — verified: counter left at 0 for a live item carrying the tag.)*
- **R9.** [BUG-939] (HR-9) `updated_by` is set to `user_id` only when the call actually changes a stored field value (`name`, `description`, `unit`, `sku`, `item_type`) or the item's set of active tags (R12). Given `{}`, only `null` / omitted fields, values equal to the current ones, or the current tag set, the call succeeds, returns the item, and `updated_by` / `updated_at` keep their values. A repair of a stale `name_normalized` alone (R5) does not count as a change. *(Today: `updated_by` is assigned on every call; it is written — and `updated_at` with it — whenever it differs from the stored value, e.g. an unchanged unit saved by another user is stamped. A call by the user already stamped that changes nothing writes nothing.)*
- **R10.** On a real change `updated_at` is set. Nothing else on the row changes: `workspace_id`, `created_by`, `created_at`, `is_active` keep their values.
- **R11.** `tag_ids` not sent or `null` → links and counters untouched (verified). (P9 — `remove`: the "input without `tag_ids`" part of the check is dead code.)
- **R12.** [BUG-934] Given a `tag_ids` list: links to **active** tags that stay in the list are left untouched (same `id`, `assigned_by`, `assigned_at`) and their counters do not change; each active tag no longer in the list loses its link (row deleted) and its counter goes down by 1 (floor 0 — item tag DAO `decrement_usage_count` R1–R3); each tag in the list not yet on the item is linked as `_assign_tags_to_item` describes (+1). *(Today: every link of the item is deleted and every requested tag linked again — staying tags get a new row with `assigned_by` = the saver and go −1 then +1; verified: link ids 4239/4240 replaced by 4242/4243.)*
- **R13.** [BUG-935] Links to **deleted** tags are left untouched by a tag save, whether or not the deleted tag's id is in the list, and no counter changes for them; they stay hidden and show again once the tag is restored. A deleted tag already on the item that is sent again is not refused (not "newly added" — R15). *(Today: they are erased with the rest; the deleted tag's counter is not lowered — verified 7 stays 7.)*
- **R14.** `tag_ids=[]` removes every link to an active tag (−1 each) and keeps links to deleted tags (R13). (Holds today for active tags; the deleted-tag part is BUG-935.)
- **R15.** [BUG-944] [BUG-943] (P5, P4) If any newly added tag id is rejected (`_assign_tags_to_item` R2, R3), the whole update fails with that `ValueError` and **nothing** is written: fields, `updated_by`, links and counters stay as they were. *(Today: fields are written first, all old links removed, bad ids skipped — `tag_ids: [999]` leaves the item with no tags, success; a deleted tag is linked and counted.)*
- **R16.** Unknown `user_id` (with a change that stamps it) → `IntegrityError` (`ForeignKeyViolation`, `items_updated_by_fkey`); nothing saved.
- **R17.** All writes are flushed, not committed; a savepoint roll-back around the call restores the row, the links and the counters.
- **R18.** [BUG-946] (P7) A sent SKU is checked like on create (`create_item` R7) with the item itself excluded: keeping its own SKU, or changing only its case / outer spaces, never conflicts; a SKU used by another live item → `ValueError("Item with SKU '<sku>' already exists")`, nothing written; `sku: null` / blank clears it (R7, stored `None`). *(Today: no check.)*
- **R19.** (Q1 — `intended`) A rename is never refused for a duplicate name. ✅
- **R20.** Counter changes go through the item tag DAO and inherit BUG-931 (cited, item tag DAO `increment_usage_count` R5, `decrement_usage_count` R6).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| missing; [BUG-941] other workspace; [BUG-938] deleted | `ValueError` | `Item <item_id> not found` |
| (today) other workspace | `ValueError` | `Item <item_id> does not belong to workspace <workspace_id>` |
| blank name / unit, `null` name / unit / type [BUG-936, BUG-942] | `ValidationError` building `ItemUpdate` | not asserted |
| SKU taken [BUG-946] | `ValueError` | `Item with SKU '<sku>' already exists` |
| bad / deleted tag newly added [BUG-944, BUG-943] | `ValueError` | `Item tag <id> not found` / `Item tag <id> is not active` |
| unknown `user_id` | `IntegrityError` / `ForeignKeyViolation` | — |

**Side effects:** on a real change: the item's changed fields, `updated_by`, `updated_at`; links of removed active tags deleted (−1 each), links of added tags inserted (+1 each); flushed. On a no-op: nothing (intended, BUG-939). No commit. Nothing on any error (intended).

---

## `ItemManager.get_item(session, item_id, workspace_id, include_deleted=False)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `ItemService.get_item` ← `GET /items/{id}/` (None → 404 `Item with ID <id> not found`); `ItemService.delete_item` (pre-check, None → 404); `ItemSummaryService.get_summary` ← `GET /items/{id}/summary/`; `ItemOrdersService` ← `GET /items/{id}/orders/`)

**Purpose:** One visible item of the caller's workspace by id, or `None`.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `item_id` | int | item to fetch |
| `workspace_id` | int | caller's workspace |
| `include_deleted` | bool, default `False` | *(requires new parameter — BUG-937)* `True` also returns a deleted item. Today the parameter does not exist (`TypeError`). |

**Returns:** the `Item` (the session's instance) or `None`.

**Rules:**
- **R1.** A live item of the workspace is returned.
- **R2.** No item with that id, or an item of another workspace → `None` (no error; existence not revealed — holds today).
- **R3.** [BUG-937] (HR-4) A deleted item → `None` by default. *(Today: returned.)*
- **R4.** [BUG-937] With `include_deleted=True` a deleted item of the workspace is returned; another workspace still gives `None`. *(Requires the new parameter.)*
- **R5.** Nothing is written.

**Errors:** none

**Side effects:** none

---

## `ItemManager.list_items_filtered(session, workspace_id, *, skip=0, limit=100, search=None, unit=None, tag_ids=None)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ItemService.get_items_page` ← `GET /items/`)

**Purpose:** One page of the item catalog with the catalog filters.

**Rules:**
- **R1.** Returns exactly what item DAO `list_active_items_filtered` returns for the same arguments (its R1–R7 and `_apply_item_catalog_filters` R1–R13, including BUG-012 … BUG-017, BUG-033), passed through unchanged; defaults `skip=0`, `limit=100`. One pass-through case is enough here (e.g. two live items and one deleted item → the two live ones; another workspace's item absent). Nothing is written.

**Errors:** as the DAO (negative `limit` / `skip` → `sqlalchemy.exc.DataError`).

**Side effects:** none

---

## `ItemManager.count_items_filtered(session, workspace_id, *, search=None, unit=None, tag_ids=None)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `ItemService.get_items_page` ← `GET /items/`, as `total`)

**Purpose:** The number of catalog items matching the filters.

**Rules:**
- **R1.** Returns exactly item DAO `count_active_items_filtered` for the same arguments (its R1–R4), an `int`; equals the length of `list_items_filtered` with the same filters and a large enough `limit`. Nothing is written.

**Errors:** none

**Side effects:** none

---

## `ItemManager.distinct_units(session, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ItemService.get_distinct_units` ← `GET /items/units/`)

**Purpose:** The units in use by the workspace's live items.

**Rules:**
- **R1.** Returns exactly item DAO `distinct_units_in_workspace` (its R1–R6, BUG-017: one lowercase entry per unit, trimmed, blank never listed, sorted). Nothing is written.

**Errors:** none

**Side effects:** none

---

## `ItemManager.find_similar_items(session, workspace_id, name, limit=5, exclude_item_id=None)`
**Shape:** search
**Persistence:** reads
**Visibility:** public (used by: `ItemService.get_similar_items` ← `GET /items/similar/`, which enforces `name` min length 1 and `1 <= limit <= 10` and never passes `exclude_item_id` — BUG-011)

**Purpose:** Live items whose names look like a proposed name, as plain dicts for the duplicate warning.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `workspace_id` | int | workspace |
| `name` | str | proposed name |
| `limit` | int, default `5` | max matches |
| `exclude_item_id` | int or `None` | item to leave out |

**Returns:** a `list` of `dict`, one per match.

**Rules:**
- **R1.** Which items are returned, and in which order, is exactly item DAO `find_similar_by_name_in_workspace` R1–R10 (short normalized name → `[]`; live items of the workspace only; exact normalized match or score ≥ 0.35 — BUG-034; `exclude_item_id` — BUG-011; order — BUG-018; `limit=0` → `[]`, negative → `DataError`).
- **R2.** Each dict has exactly the keys `id`, `name`, `unit`, `sku`, `similarity_score`, `match_type`; `name`, `unit`, `sku` are the stored values (e.g. an untrimmed stored name comes back untrimmed).
- **R3.** `similarity_score` is the DAO score as a Python `float`, rounded to 4 decimals with `round()`: an exact match → `1.0`; 7/19 → `0.3684`; a score of 7/20 (`0.3499999940…`, included once BUG-034 is fixed) → `0.35`.
- **R4.** `match_type` is `"exact_normalized"` when the item's **stored** `name_normalized` equals `normalize_item_name(name)`, otherwise `"fuzzy"` (verified: `"steel rod 22 M"` against a stored `"steel rod 22m"` → exact, score 1.0). An item with a stale `name_normalized` is judged by the stored value.
- **R5.** Nothing is written.

**Errors:** negative `limit` → `sqlalchemy.exc.DataError` (from the DAO).

**Side effects:** none

---

## `ItemManager.delete_item(session, item_id, workspace_id, user_id)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `ItemService.delete_item` ← `DELETE /items/{id}/` (204), after its own `get_item` pre-check)

**Purpose:** Soft-delete a live item and stop its tags from counting it, keeping its links.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session; not committed here |
| `item_id` | int | item to delete |
| `workspace_id` | int | caller's workspace |
| `user_id` | int | deleter; stored as `updated_by` |

**Returns:** the same `Item` instance, deleted and flushed, not committed.

**Rules:**
- **R1.** No item with that id → `ValueError("Item <item_id> not found")`; nothing written.
- **R2.** [BUG-941] (P2) An item of another workspace → the same `ValueError("Item <item_id> not found")`. *(Today: `ValueError("Item <item_id> does not belong to workspace <workspace_id>")`.)*
- **R3.** Already deleted → `ValueError("Item <item_id> is already deleted")`; nothing written (counters and `updated_by` unchanged).
- **R3a.** [BUG-940] (P1) At the API a delete of a missing, other-workspace or deleted item answers 4xx, never 500 (404 from the service's pre-check, which hides deleted items once BUG-937 is fixed; otherwise 400 for "already deleted") — integration-only. *(Today: the already-deleted case answers 500.)*
- **R4.** Given a live item: `is_active = False`, `updated_by = user_id`, `updated_at` set; nothing else on the row changes (`name`, `name_normalized`, `unit`, `sku`, `description`, `item_type`, `created_*`, `workspace_id`).
- **R5.** Every link of the item is kept, unchanged (standing decision 2 — holds today).
- **R6.** Each **active** tag linked to the item (link of this workspace) has its counter lowered by 1, never below 0 (counter 0 stays 0 — item tag DAO `decrement_usage_count` R2). (Holds today.)
- **R7.** [BUG-945] (P6) Each **deleted** tag linked to the item has its counter lowered the same way (−1, floor 0). *(Today: unchanged — verified 9 stays 9.)*
- **R8.** An item without links is deleted with no counter change.
- **R9.** [BUG-948] (Q2 — owner's answer) A live item that is **in use** is not deleted: `ValueError` with message `"Item has stock or open orders"` and the list of blockers (exact form in R9b; 400 at the API — the translation belongs in `ItemService`, FU-1); nothing written — `is_active`, `updated_by`, `updated_at`, every tag counter and link stay as they were. Checked after R1–R3 (a missing / other-workspace / already-deleted item gets those errors) and before any write (R10a). **A row linking across workspaces is invalid data** (owner's correction 2026-10-30, cases gap 5: *"we don't want to allow cross workspace"*, *"it should block from happening"*). A **cross-workspace row** is a row of (a)–(h) whose own `workspace_id` differs from the item's, or, for (c)–(f) and (h), a line whose order or batch has a `workspace_id` that differs from the item's. Creating one must be refused; those creation paths belong to other modules' specs (FU-5) and a separate audit logs them. `delete_item` still refuses when such a row exists, so a bad row cannot lead to deleting something in use, but it exposes nothing of the other workspace: the row is reported only as the generic entry of R9b. The states are the same for every row: a cross-workspace row blocks and does not block in exactly the states (a)–(h) below. The factory, machine, stage or production line a row points at is not part of this test (*Claude's reading, not the owner's words*): a row of the item's workspace on a stage of another workspace is judged by that stage's name as usual and listed with its own `type` and `id`, which are the caller's own. *(Today: such rows are not looked at, like all others. They can exist: no foreign key ties them to the item's workspace — verified.)* The item is in use when **at least one** of these holds (one is enough; the message is the same for every reason, the blocker list names each one — R9b):
  - **(a) Stock in a factory:** an `inventory` row with `item_id` = the item, `is_deleted = False` and `qty ≠ 0` (negative counts too) — any `inventory_type` (`STORAGE`, `DAMAGED`, `WASTE`, `SCRAP`), in a factory that is not deleted. Does **not** block: a row with `qty = 0`; a soft-deleted row (`is_deleted = True`) whatever its `qty` (standing decision 1); a row in a deleted factory (`factories.is_deleted = True`) whatever its `qty` (owner's answer 2026-10-31); the row stays. Deleted means `is_deleted`: `is_active` of the factory is not looked at, so a factory that is only deactivated still blocks. `inventory.is_active` is not looked at. A cross-workspace row follows the same state rule (R9 intro): in a deleted factory it does not block and gets no generic entry. The factory is followed by id; its `workspace_id` is not compared.
  - **(b) Stock on a machine:** a `machine_items` row with `item_id` = the item and `qty ≠ 0`, on a machine that is not deleted, in a factory that is not deleted. Does **not** block: `qty = 0` (whatever `req_qty` / `defective_qty` hold — those are a target and a defect count, not stock); a row on a deleted machine (`machines.is_deleted = True`) whatever its `qty` (owner's answer 2026-10-30, `machine_item_manager` Q5: no list shows such stock and the user cannot clear it); a row on a machine whose factory is deleted (`factories.is_deleted = True`) whatever its `qty` and the machine's own state (owner's answer 2026-10-31: stock in a deleted factory does not block). The row stays. Deleted means `is_deleted`: `is_active` of the machine or factory is not looked at, so a machine that is only deactivated still blocks. `machine_items` has no soft-delete column of its own. A cross-workspace row follows the same state rule (R9 intro): on a deleted machine, or a machine of a deleted factory, it does not block and gets no generic entry. The machine and its factory are followed by id; their `workspace_id` is not compared.
  - **(c) Purchase order:** a `purchase_order_items` line with `item_id` = the item, on a purchase order (`purchase_orders`) with `voided = False` whose current stage (`current_status_id` → `statuses.name`) is not `Complete`. Purchase-order stages are `Draft`, `Planning`, `Receiving`, `Complete` (status rows, matched by exact name; the stage's `workspace_id` is not compared, per the R9 intro); there is no "cancelled" stage — a purchase order is voided (`voided = True`) or, without receiving history, deleted outright with its lines. Does **not** block: stage `Complete`; `voided = True` at any stage.
  - **(d) Sales order:** a `sales_order_items` line with `item_id` = the item (free-text lines have `item_id` NULL and never concern an item), on a sales order (`sales_orders`) with `order_completed = False`. Does **not** block: a line on a sales order with `order_completed = True`. `current_status_id` is not looked at. Sales orders have no cancelled / voided state and no delete, so an abandoned sales order blocks until it is completed — the refusal names it (R9b), so the user can find and complete it (owner's answer 2026-10-18, see Q2).
  - **(e) Work order:** a live line (`work_order_items.is_deleted = False`) whose `item_id` = the item **or** whose `replaced_item_id` = the item (the item a `REPLACE` line takes off the machine when the order completes — the open order will still move it), on a live work order (`work_orders.is_deleted = False`) with `status` `DRAFT` or `IN_PROGRESS`. Work-order statuses are exactly `DRAFT`, `IN_PROGRESS`, `COMPLETED`, `VOIDED`. Does **not** block: `status` `COMPLETED` or `VOIDED`; a soft-deleted work order (`is_deleted = True`) whatever its status; a removed / voided line (`work_order_items.is_deleted = True`).
  - **(f) Transfer order:** a `transfer_order_items` line with `item_id` = the item, on a transfer order (`transfer_orders`) with `completed_at` NULL. Does **not** block: `completed_at` set (completed). Transfer orders have no cancelled or voided state; a not-completed transfer order is cancelled by deleting it (order and lines removed), so no other state exists.
  - **(g) Finished-goods stock:** a `products` row with `item_id` = the item, `is_deleted = False` and `qty ≠ 0` (negative counts too), in a factory that is not deleted, with `is_available_for_sale` `True` or `False` (owner's answer 2026-10-30, "Both block"). Does **not** block: a row with `qty = 0`; a soft-deleted row (`is_deleted = True`) whatever its `qty` (standing decision 1, as (a)); a row in a deleted factory (`factories.is_deleted = True`) whatever its `qty` (owner's answer 2026-10-31, as (a)); the row stays. `products.is_active` is not looked at, and neither is `is_active` of the factory, so a factory that is only deactivated still blocks. A cross-workspace row follows the same state rule, as in (a).
  - **(h) Production batch:** a `production_batch_items` line with `item_id` = the item, in any `item_role`, on a production batch (`production_batches`) with `status` `draft` or `in_progress` (owner's answer 2026-10-30, "Both block"). Batch statuses are exactly `draft`, `in_progress`, `completed`, `cancelled`. Does **not** block: `status` `completed` or `cancelled`. Neither table has a soft-delete column; a line taken off a batch is removed outright. Quantities on the line are not looked at.

  *(Today: none of this is looked at — an item with stock or open order lines is deleted like any other, and those rows are not read or changed.)*
- **R9b.** [BUG-948] (Q2 (d) — owner's answer, main session's reading) **The refusal lists every blocker**, not only the first. The `ValueError` has exactly two args: `args[0]` = the message `"Item has stock or open orders"`; `args[1]` = a `list` of blockers, each a `dict` with exactly the keys `"type"` and `"id"`, except the generic entry below, which has only `"type"`:
  - `"type"` is one of `"factory_stock"` (R9 (a)), `"machine_stock"` (b), `"purchase_order"` (c), `"sales_order"` (d), `"work_order"` (e), `"transfer_order"` (f), `"product_stock"` (g), `"production_batch"` (h), or `"other_workspace"` (any cross-workspace row, below);
  - `"id"` is the `inventory` row id for `factory_stock`, the `machine_items` row id for `machine_stock`, the `products` row id for `product_stock`, the **order** id (`purchase_orders.id`, `sales_orders.id`, `work_orders.id`, `transfer_orders.id`) for the order types, and the **batch** id (`production_batches.id`) for `production_batch` — never a line id.
  - One entry per distinct blocking row (stock) or order / batch: an order or batch with two or more blocking lines naming the item (including a work-order line by `item_id` and another by `replaced_item_id`) appears once; two blocking stock rows (e.g. `STORAGE` and `DAMAGED` in one factory, or two `products` rows of one factory with different `is_available_for_sale`) are two entries.
  - Sorted by `"type"` in the order listed above (`factory_stock` first, then `machine_stock`, `purchase_order`, `sales_order`, `work_order`, `transfer_order`, `product_stock`, `production_batch`, and the generic entry last), then by `"id"` ascending.
  - Only blocking rows are listed (the "does not block" rows of R9 and the rows of R9a never appear, also not as the generic entry: an `inventory`, `products` or `machine_items` row with a deleted parent, R9 (a), (b), (g), gets no entry of its own type and no `other_workspace` entry); the list is never empty when the refusal is raised.
  - **Cross-workspace rows (R9, gap 5):** every blocking cross-workspace row, of whatever type, is covered by **one** entry, exactly `{"type": "other_workspace"}`, with no `"id"` and no other key: once however many such rows exist, always last. It carries nothing of the other workspace. An item whose only blockers are such rows gets `[{"type": "other_workspace"}]`. (Claude's recommendation; the owner approved it on 2026-10-30, verbatim: *"yeah i agree with your recommendations"*.)
  - Lines are judged one at a time (*Claude's reading, not the owner's words*): an order of the item's workspace with one normal blocking line and one cross-workspace blocking line gives its normal entry and the generic entry.
  - Nothing is written (R9).
  *(Today: no refusal at all. Requires the manager to collect every blocker before raising.)*
- **R9a.** (Owner's answer 2026-10-30, cases gap 6) These rows never block, in any state, and the delete leaves them unchanged: an item whose only other rows are ones R9 says do not block, or the rows below, is deleted as R4–R8 describe, and none of them appears in a blocker list. (Holds today — verified; after the fix too. Columns: Notes for the test designer.)
  - **Ledger rows:** `inventory_ledger`, `machine_item_ledger`, any `transaction_type`.
  - **Returns:** `purchase_order_return_items`, `sales_order_return_items`, whatever the return's `status` (`pending`, `completed`, `voided`). The return is not read. The order line a return points at still counts under R9 (c) / (d) in its own right.
  - **Work-order templates:** `work_order_template_items` by `item_id` or by `replaced_item_id`.
  - **Order templates:** `order_templates` / `order_template_items` have no item column, so they can never point at an item. Nothing to test.
  - **Production formulas:** `production_formula_items` in any `item_role`; `production_formula_stages.expected_output_item_id`.
  - **Project component items:** `project_component_items`, any `qty`.
  - **Stock with a deleted parent:** `inventory` and `products` in a deleted factory, `machine_items` on a deleted machine or a machine of a deleted factory, any `qty`, any workspace (R9 (a), (b), (g); owner's answers 2026-10-30, `machine_item_manager` Q5, and 2026-10-31). The row stays, so it comes back with its parents. A parent that is only deactivated (`is_active = False`, `is_deleted = False`) is not deleted: its stock blocks. Open orders and batches are not covered by this: a line on an order or batch tied to a deleted factory blocks as (c)–(f), (h) say.

  The delete never changes stock rows or order lines (holds today; after the fix the rows above are only read).

  **Not decided — no case.** No owner answer names the history rows `product_ledger`, `project_component_item_ledger`, `sales_delivery_items` and `invoice_items.item_id` (a plain column, no foreign key). They are not in R9, so they do not block as written, and the first three do not block today (verified; `invoice_items` not run). They touch ledgers, invoices and orders, so Claude does not decide them under the reviewer's delegation. The designer writes no case for them, so that no test pins an undecided behavior.
- **R10.** Unknown `user_id` on an item that is **not in use** → `IntegrityError` (`ForeignKeyViolation`, `items_updated_by_fkey`); the item stays live and no counter changes (verified).
- **R10a.** [BUG-948] (cases gap 4 — Claude's reading of the owner's answer, not the owner's words) Unknown `user_id` on an item that **is in use** → the R9 refusal, not a database error: the R9 check runs first and raises before any write, so no foreign-key error occurs. Same `ValueError` and blocker list as R9b; the item stays live and nothing is written. The transaction stays usable. *(Today: `IntegrityError` / `ForeignKeyViolation`, `items_updated_by_fkey`; the item stays live — verified.)*
- **R11.** Flushed, not committed: a savepoint roll-back around the call makes the item live again and restores the counters.
- **R12.** After the delete, in the same session: `get_item` follows its R3 / R4; the catalog list / count no longer include the item (item DAO R2); `update_item` refuses it (R3 there, BUG-938); a second delete gives R3.
- **R13.** Counter changes inherit BUG-931 (cited).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| missing; [BUG-941] other workspace | `ValueError` | `Item <item_id> not found` |
| (today) other workspace | `ValueError` | `Item <item_id> does not belong to workspace <workspace_id>` |
| already deleted | `ValueError` | `Item <item_id> is already deleted` |
| [BUG-948] item in use: stock, open order line or open batch line (R9 (a)–(h)); also with an unknown `user_id` (R10a) | `ValueError` (two args, R9b) | `args[0] == "Item has stock or open orders"`; `args[1]` = blocker list (R9b) |
| [BUG-948] a cross-workspace row in a blocking state (R9 intro), alone or with normal blockers | `ValueError` (two args, R9b) | same `args[0]`; `args[1]` ends with one `{"type": "other_workspace"}`, nothing of the other workspace in it |
| unknown `user_id`, item not in use (R10) | `IntegrityError` / `ForeignKeyViolation` | — |

**Side effects:** nothing when the item is in use (R9, intended). Otherwise: the item's `is_active`, `updated_by`, `updated_at`; each linked tag's `usage_count` −1 (floor 0; today active tags only); flushed. No link written or removed. No commit.

---

## `ItemManager._assign_tags_to_item(session, item_id, tag_ids, workspace_id, user_id)`
**Shape:** helper
**Persistence:** writes
**Visibility:** internal (used by: `create_item`, `update_item` — only with a non-empty list)

**Purpose:** Link the requested tags of the workspace to an item and count it for each newly linked tag.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `item_id` | int | item to link (not checked here) |
| `tag_ids` | list[int] | tags to link, in order; may repeat |
| `workspace_id` | int | the tags must belong to it; stored on each link |
| `user_id` | int | `assigned_by` of new links |

**Returns:** `None`.

**Rules:**
- **R1.** Each requested id that is an active tag of the workspace and not yet linked to the item gets one link (`item_id`, `tag_id`, `workspace_id`, `assigned_by = user_id`, `assigned_at` set) and its counter goes up by 1 (item tag DAO `increment_usage_count` R1).
- **R2.** [BUG-944] (P5) An id that is not a tag of the workspace — unknown, `0`, negative, or a tag of another workspace — → `ValueError("Item tag <id> not found")`. *(Today: skipped silently; a tag of another workspace is never linked — holds.)*
- **R3.** [BUG-943] (P4) An id of a deleted tag (`is_active = False`) not yet linked to the item → `ValueError("Item tag <id> is not active")`. *(Today: linked and counted — verified 5 → 6.)*
- **R4.** [BUG-944] All ids are checked (R2, R3) before any link or counter is written; ids are checked in list order and the error names the first rejected id; if any id is rejected, no link is created and no counter changes — valid ids in the same list are not linked. *(Today: each id is handled on its own; valid ids are linked while bad ones are skipped.)*
- **R5.** An id already linked to the item (a link of this workspace — assignment DAO `assignment_exists` R1–R4) is skipped: no new link, no counter change, no error — also when that tag is deleted.
- **R6.** The same id twice in the list is linked once and counted once (holds today: the first link is flushed before the second check).
- **R7.** Links and counter changes are flushed (no commit).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not a tag of the workspace [BUG-944] | `ValueError` | `Item tag <id> not found` |
| deleted tag, not yet linked [BUG-943] | `ValueError` | `Item tag <id> is not active` |

**Side effects:** `item_tag_assignments` rows inserted; `item_tags.usage_count` +1 per new link; flushed.

---

## `ItemManager.get_tags_for_item(session, item_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ItemSummaryService.get_summary` ← `GET /items/{id}/summary/`)

**Purpose:** The active tags of one item.

**Rules:**
- **R1.** Returns exactly assignment DAO `get_tags_for_item` for the same arguments (its R1–R5: active tags only, links of this workspace, a deleted item's tags returned (P1), order BUG-932). One pass-through case is enough here. Nothing is written.

**Errors:** none

**Side effects:** none

---

## `ItemManager.get_tags_for_items(session, item_ids, workspace_id)`
**Shape:** list (grouped)
**Persistence:** reads
**Visibility:** public (used by: `ItemService.get_items_page` ← `GET /items/`, the tag chips of the page's items)

**Purpose:** The active tags of several items, grouped by item.

**Rules:**
- **R1.** Returns exactly assignment DAO `get_tags_for_items` for the same arguments (its R1–R7: `[]` → `{}`, one key per requested id, unmatched → `[]`, order BUG-933). One pass-through case is enough here. Nothing is written.

**Errors:** none

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 25–27 | `__init__` | Not specified |
| 52 | `hasattr(item_data, 'tag_ids')` — always true for `ItemCreate` (dead, P9) / else `[]` | `create_item` R8 |
| 55–58 | dump without `tag_ids`; add `workspace_id`, `created_by`, `name_normalized`; no trim (BUG-936, BUG-017); no SKU / name check (BUG-946, Q1) | `create_item` R1, R2, R3, R4, R5, R6, R7 |
| 61 / `dao/base.py` 76–84 | insert + flush; FK errors | `create_item` R1, R10, R11 |
| 64 | `if tag_ids:` — `[]` → no links / list → assign; item written before tags are checked (BUG-943, BUG-944) | `create_item` R8, R9 |
| 102 / `dao/base.py` 43 | raw `get` by id (any workspace, deleted included) | `update_item` R1, R2, R3 |
| 103–104 | not found → `ValueError` | `update_item` R1, R2a |
| 107–108 | other workspace → `ValueError` "does not belong" (BUG-941) | `update_item` R2, R2a |
| — (no check) | item deleted (BUG-938) | `update_item` R3 |
| 112–113 | `hasattr` (dead, P9) and `tag_ids is not None` → tag update / `None` → none | `update_item` R11 |
| 116 | `exclude_unset` + `exclude_none` — `null` dropped (BUG-942); `is_active` kept (BUG-947); no trim | `update_item` R4, R6, R6a, R7, R8 |
| 117 | `updated_by` always assigned (BUG-939); written only when it differs or another column changes | `update_item` R9, R10 |
| 118–119 | `'name' in item_dict` → recompute `name_normalized` / else keep (stale kept) | `update_item` R5 |
| 122 / `dao/base.py` 108–119 | setattr + flush; FK error; `updated_at` by `onupdate` | `update_item` R4, R10, R16, R17 |
| 125 | `if tag_ids is not None:` | `update_item` R11, R12 |
| 126–128 / assignment DAO 62–70 | old tags = active tags only (links to deleted tags not seen) | `update_item` R12, R13 |
| 129–132 / item tag DAO 116–120 | decrement every active old tag (−1 / +1 churn, BUG-934); floor 0; BUG-931 | `update_item` R12, R20 |
| 133–135 / assignment DAO 133–142 | delete **all** links, deleted tags' too (BUG-934, BUG-935) | `update_item` R12, R13, R14 |
| 137 | `if tag_ids:` — `[]` → none / list → assign | `update_item` R14, R12 |
| 168 / `dao/base.py` 43 | raw `get` by id | `get_item` R1, R2, R3 |
| 169–171 | item of another workspace → `None` | `get_item` R2 |
| — (no check) | deleted item returned (BUG-937) | `get_item` R3, R4 |
| 174–209 | `search_items` | Not specified (dead code) |
| 222–230 / `dao/item.py` | pass-through, keyword defaults | `list_items_filtered` R1 |
| 241–247 / `dao/item.py` | pass-through | `count_items_filtered` R1 |
| 250 / `dao/item.py` | pass-through | `distinct_units` R1 |
| 261 | normalize the proposed name | `find_similar_items` R4 |
| 262–268 / `dao/item.py` 186–220 | DAO rows (empty / one / many; short name, exclude, limit) | `find_similar_items` R1 |
| 271–287 | loop: `float`, `round(…, 4)`, exact vs fuzzy on stored `name_normalized`, dict keys | `find_similar_items` R2, R3, R4 |
| 302 / `dao/base.py` 43 | raw `get` | `delete_item` R1, R2 |
| 303–304 | not found → `ValueError` | `delete_item` R1, R3a |
| 306–307 | other workspace → `ValueError` "does not belong" (BUG-941) | `delete_item` R2, R3a |
| 309–310 | `not item.is_active` → already deleted | `delete_item` R3, R3a |
| — (no check) | stock / open orders / finished-goods stock / open batches of the item (Q2, BUG-948); cross-workspace rows collapse to one generic entry (gap 5); every blocker collected and listed; before the write of line 315, so it wins over the FK error (gap 4) | `delete_item` R9, R9a, R9b, R10a |
| 312–314 / assignment DAO 62–70 | linked tags = active tags only (BUG-945) | `delete_item` R6, R7, R8 |
| 315–318 / `dao/base.py` 108–119 | `is_active=False`, `updated_by`; flush (FK error before any decrement) | `delete_item` R4, R10, R11 |
| 319–322 / item tag DAO 116–120 | decrement each active tag; floor 0; empty list | `delete_item` R6, R8, R13 |
| — | links never touched | `delete_item` R5 |
| 323 | return the instance | `delete_item` R4 |
| 346 | loop over the list (one / many / repeats) | `_assign_tags_to_item` R1, R6 |
| 348 / `dao/base.py` 43 | raw `get` of the tag (any workspace, deleted included) | `_assign_tags_to_item` R2, R3 |
| 349–350 | not found / other workspace → `continue` (BUG-944); deleted not checked (BUG-943) | `_assign_tags_to_item` R2, R3, R4 |
| 353–356 / assignment DAO 88–96 | already linked → `continue` | `_assign_tags_to_item` R5, R6 |
| 359–365 / `dao/base.py` 76–84 | create link + flush | `_assign_tags_to_item` R1, R7 |
| 368 / item tag DAO 96–100 | increment (BUG-931) | `_assign_tags_to_item` R1, R7 |
| 387–389 | pass-through | `get_tags_for_item` R1 |
| 398–400 | pass-through | `get_tags_for_items` R1 |
| 404 | module singleton | Not specified |

## Gap log
G4 (`item_manager.cases.md` gap 4) — Intent, answered — Claude's reading of the owner's answer of 2026-10-30, not the owner's words: the in-use refusal wins over the unknown-user error. `delete_item` R9 intro ("before any write"), R10 narrowed to an item not in use, R10a new (BUG-948), Errors rows 4 and 5, Branch map.
G5 (`item_manager.cases.md` gap 5) — Intent, answered and corrected — first answer 2026-10-30 ("by item id only, whatever the row's `workspace_id`") superseded the same day by the owner's correction ("we don't want to allow cross workspace", "it should block from happening"): a cross-workspace row is invalid data and creating one must be refused (FU-5); `delete_item` still refuses, showing one `{"type": "other_workspace"}` entry with no id, last (owner approved 2026-10-30, "yeah i agree with your recommendations"). `delete_item` R9 intro, R9b, Errors row 5 (new), Notes entry "Cross-workspace rows" (BUG-948); FU-1's question on what a foreign blocker may show removed; FU-8 note added. Which rows count, and lines judged one at a time, are Claude's reading.
G6 (`item_manager.cases.md` gap 6) — Fact, plus owner's answer 2026-10-30 to cover them — `delete_item` R9a rewritten as a list of tables (untagged, holds today), Notes entry "Rows for `delete_item` R9a" with classes, imports and required columns, checked by running. Correction found on the way: `order_templates` have no item column, so that part of the old R9a could never apply.
Raised by this describer (not a cases gap) — Intent, answered — owner's answer 2026-10-30, "Both block": `delete_item` R9 (g) `products` and (h) `production_batch_items` added (BUG-948), R9b types `product_stock` and `production_batch` added after `transfer_order` in the sort, R9a's "Not decided" paragraph narrowed, Notes entry "Rows for `delete_item` R9 (g), (h)".
Raised from `machine_item_manager` Q5 (not a cases gap) — Intent, answered — owner's answer 2026-10-30: a `machine_items` row on a deleted machine does not block; a machine of a deleted factory is Claude's reading. `delete_item` R9 (b) (BUG-948), R9a, R9b, Notes entry "Machine stock with a deleted parent". Cross-workspace rows follow the same state rule. Notes "Cross-workspace rows" widened with the W1 line on a W2 sales, work or transfer order (verifier round 6).
Follow-up to the Q5 line (not a cases gap) — Intent, answered — owner's answer 2026-10-31: stock held directly in a deleted factory does not block either. `delete_item` R9 (a), (g) (BUG-948), R9 (b)'s factory part now the owner's, R9a, R9b, Notes entry renamed "Stock with a deleted parent". Cross-workspace rows follow the same state rule; `is_active` alone is not deleted.
Still not closed (not a cases gap): `product_ledger`, `project_component_item_ledger`, `sales_delivery_items`, `invoice_items.item_id` are named by no owner answer (R9a, last paragraph). No review question added, as instructed for this run; the spec stays APPROVED and no case is written for them.
