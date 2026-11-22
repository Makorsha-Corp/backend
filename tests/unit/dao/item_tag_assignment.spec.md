# Spec — `app/dao/item_tag_assignment.py`

> **Status:** APPROVED (2026-10-17)
> **Source commit:** e48a092

> **Review round 2026-10-17.** The reviewer delegated every open decision of this spec to Claude. Decided by Claude under the reviewer's delegation (2026-10-17): every suggested answer is accepted — P1 (intended), P2 (bug, BUG-934), P3 (bug, BUG-935) and the house-rule lines BUG-932, BUG-933 and BUG-100, including the HR-6 default that an item's tag chips are **not** grouped "system tags first". None of these is the reviewer's own answer. The "(pilot default — awaiting reviewer)" markers were removed; no rule changed. Consequence of P2: once BUG-934 is fixed, `remove_all_tags_from_item` has no caller; it is listed in `docs/testing/dead-code-removal-checklist.md` as "remove together with the fix of BUG-934". It is reachable today, so its rules stay and are tested as it behaves today. BUG-934 and BUG-935 are fixed in the item manager, not in this file.

> **Pilot convention:** every question below carried a suggested answer, applied to the rules as a provisional default. All were accepted on 2026-10-17 (decided by Claude under the reviewer's delegation); nothing is provisional any more.

> **Standing reviewer decisions applied here (not asked again):**
> 1. Soft-deleted rows are kept but must not show up in lists or be counted (inventory DAO Q2, 2026-10-10). **For items and item tags "deleted" is `is_active = False`** (item DAO spec Q7 / Q8; item tag DAO spec standing decision 1): "delete item" and "delete tag" set `is_active = False` and nothing else; neither table has `is_deleted`. Link rows ("assignments") have no soft-delete column of their own.
> 2. Things of a soft-deleted parent are **hidden by the parent's state, their own rows untouched** ("hidden, not cascaded", 2026-10-11). A link row belongs to both its item and its tag: links of a deleted item and links to a deleted tag are kept, not erased, so that restoring the item or the tag brings them back (P3).
> 3. Raw DAO lookups returning rows of deleted parents are intended; the manager / service decides what to hide (base DAO spec, HR-4 scope). A method whose purpose is "the tags of item X" for display hides deleted tags (it does — HR-4 holds) and must have the house order (HR-6) — item tag DAO spec FU-3.
> 4. Missing or non-default `ORDER BY`: BUG-100 for inherited base methods, otherwise a new bug against this file; name order follows BUG-930's reasoning (name case-insensitive, then `id`). Physical row order and collation order are **not** deterministic across servers: no order recipe in this spec is called verified or deterministic.
> 5. Re-creating unchanged link rows is a bug (BUG-870, BUG-909 — HR-9). Tag counters change only through the item tag DAO (`increment_usage_count` / `decrement_usage_count`, BUG-931); this DAO never touches them.
>
> **Verified by running** (throwaway scripts `itda_probe.py`, `itda_probe2.py` against the test database, rolled back; nothing created or dropped): every "Today:" note below; the table's columns, nullability, defaults (none in the database except the `id` sequence), constraints and their names, indexes, no triggers; the database collation (`English_United States.1252`); `get_tags_for_items` with `[]`, `None`, an unknown id, an id repeated, an item of another workspace linked under this workspace, an item without tags, a deleted item, a deleted tag, a tag of another workspace linked under this workspace, a link recorded under another workspace, a not-yet-flushed link, two items sharing a tag (same object), today's order (`"alpha"` before `"Alpha"`, system tag not first, two tags named `Bolt` / `bolt`), positional call (`TypeError`); `get_tags_for_item` with the same situations and that its query has no `ORDER BY`; `assignment_exists` for a live link, a deleted tag, a deleted item, another workspace (both directions), no link, a tag of another workspace, a not-yet-flushed link; `count_active_items_per_tag` for both workspaces and an unknown one (deleted items left out, deleted tags and cross-workspace items counted); `remove_all_tags_from_item` (count returned, links to deleted tags removed, other items and the other workspace's link untouched, items / tags untouched, unknown item → 0, loaded link objects leave the session, a loaded `item.tag_assignments` collection is not refreshed, a flush of the item afterwards is fine, the same pair can be inserted again, savepoint roll-back, a not-yet-flushed link survives and is inserted by the method's flush); the inherited `create` (dict, `assigned_at` from Python and not changed by patching `app.utils.time.utcnow` or `app.models.item_tag_assignment.utcnow`, schema → `NotNullViolation` on `workspace_id`, duplicate pair in the same and in another workspace → `uq_item_tag`, four foreign-key violations with their constraint names). **Not run:** anything at the manager / service / HTTP level; the *intended* behavior of the bug rules.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list — all accepted (decided by Claude under the reviewer's delegation, 2026-10-17)
| # | What the code does today, in plain words | Answer (accepted) |
|---|---|---|
| P1 | The lookups of this file ("the tags of item X", "is tag T on item X", "how many items per tag") do not look at whether the item is deleted, and "is tag T on item X" and "how many items per tag" do not look at whether the tag is deleted | intended — these are raw lookups; the item screens decide what to hide (same decision as for every other DAO). The two "tags of item X" lookups already hide deleted tags, and "how many items per tag" already leaves deleted items out |
| P2 | Saving an item with its tag list throws away every tag link of the item and writes them again, even for tags that did not change: each unchanged tag gets a new link ("assigned by" = whoever saved, "assigned at" = now) and its item counter goes −1 then +1 | bug — tags that stay keep their link untouched; only removed tags lose their link, only new tags get one (same decision as account tags, BUG-870, and machine sections, BUG-909) — BUG-934, fixed in the item manager. "Remove every tag of an item" then has no caller and is to be removed with that fix |
| P3 | That same save also erases the item's links to deleted tags. If such a tag is restored later, it is back on the items nobody saved in the meantime and missing from the items that were saved | bug — a tag save leaves links to deleted tags alone; they stay hidden and come back with the tag (the "hidden, not cascaded" decision of 2026-10-11) — BUG-935, fixed in the item manager |

Already decided by house rules / existing bugs (kept as applied — decided by Claude under the reviewer's delegation, 2026-10-17):
- "the tags of item X" (item summary page) has **no sort order** → BUG-932 (new; fix in this file).
- "the tags of these items" (the tag chips of the item list) sorts by name the way the database's language setting sorts, with no tie-break: names differing only in capitals, or two tags with the same name, come back in an order that depends on the server → BUG-933 (new; fix in this file; same problem as BUG-930 for the tag list).
- "all links of a workspace" (the generic list, inherited, unused on this DAO) has no sort order → BUG-100 (already logged; the fix in `app/dao/base.py` reaches links, nothing to do in this file).

No new questions: everything else this file does is either decided by house rules / precedent or is a plain fact stated in the rules.

### House-rule violations — applied automatically
> All three lines kept as applied — decided by Claude under the reviewer's delegation (2026-10-17), including the HR-6 default that item chips are not grouped "system tags first".

- **HR-6** `get_tags_for_item` R4 — no sort order; the tag chips of the item summary (`GET /items/{id}/summary/`) come back in whatever order the database produces. Intended: name case-insensitive ascending, then `id` ascending — the HR-6 default; system tags are **not** grouped first (the "system tags first" grouping is the documented choice of the tag picker list `GET /item-tags/` only). This is the DAO's own query, so BUG-100 does not cover it (same situation as BUG-929, BUG-906). Not paged, but HR-6 is applied to every list shown to users (BUG-719 / account manager P7 precedent: an account's tags in no fixed order).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-932 (pattern `unordered-pagination`; the fix is in `app/dao/item_tag_assignment.py`) — decided by Claude under the reviewer's delegation (2026-10-17), including "system tags not grouped first" for item chips. Rules: `get_tags_for_item` R4.
- **HR-6** `get_tags_for_items` R6 — within each item, tags are ordered by `name` under the database collation and nothing else: no case-insensitive key and no `id` tie-break. Tag names are not unique (nothing checks them — item tag DAO FU-1 (c)), so two tags with one name on the same item are possible, and names differing only in case follow the collation's case rule (on the test database `"alpha"` before `"Alpha"`; under a `C` collation every capitalised name comes first). Intended: name case-insensitive ascending, then `id` ascending — the same order as `get_tags_for_item` (BUG-932), so an item shows its chips in the same order on the list and on its summary. Same root cause as BUG-930 / BUG-623.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-933 (pattern `hr-6-non-default-list-order`, per BUG-930; the fix is in `app/dao/item_tag_assignment.py`) — decided by Claude under the reviewer's delegation (2026-10-17). Rules: `get_tags_for_items` R6.
- **HR-6** inherited `get_by_workspace` (inherited methods R4) — no sort order. Intended for this raw lookup: `id` ascending before `skip` / `limit` (HR-6: "generic `BaseDAO` lists only guarantee `id` ascending"). `ItemTagAssignmentDAO` does not override it, so the BUG-100 fix in `app/dao/base.py` reaches links with nothing to change in this file. No caller on this DAO.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-100 (existing, pattern `unordered-pagination`, logged against `app/dao/base.py`) — no new ID; decided by Claude under the reviewer's delegation (2026-10-17). Rules: inherited methods R4.

Checked and **not** violated: **HR-4** — both "tags of item X" lookups join `item_tags` and leave deleted tags out; `count_active_items_per_tag` leaves deleted items out (its deleted-tag entries are never shown — P1); `assignment_exists` is a raw check (P1). **HR-5** — no method pages; nothing is filtered after a limit. **HR-7, HR-8** — no `limit`, no `LIKE`. **HR-9** — no method of this file writes an audit stamp; the re-stamping happens in the caller (P2). **HR-2** — "a tag is on an item once" is enforced in the database (`uq_item_tag`). **HR-10** — no money, stock or approval: no lock. **HR-14** — no batch job.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-10-17)

### P1. The lookups do not look at whether the item (or, for two of them, the tag) is deleted — ✅ intended
**Background:** Items and tags are soft-deleted: "delete" sets `is_active = False` and the row stays; their link rows stay too (standing decision 2). The reviewer decided for every DAO that raw lookups return rows of deleted parents and the caller decides what to hide (base DAO spec, HR-4 scope; machine section assignment DAO P2; item tag DAO P1 / P2).
**What happens today:** `get_tags_for_item` / `get_tags_for_items` return the active tags of a deleted item exactly as for a live one (they do hide deleted tags). `assignment_exists` answers `True` for a link to a deleted tag and for a link of a deleted item. `count_active_items_per_tag` leaves deleted items out but has an entry for a deleted tag that still has links to live items. (All verified.) Callers: the item list passes only live items; the item summary shows the item it was asked for; "delete item" and "save item" use "the tags of item X" to decide which counters to lower; "save item" uses `assignment_exists` to skip a tag already on the item; "list tags" looks counts up only for the active tags it lists.
**Example:** Item "Old Bolt" (deleted) is tagged "Steel". "The tags of Old Bolt" → ["Steel"]. Tag "Obsolete" (deleted) is on the live item "Nut": "is Obsolete on Nut?" → yes; "items per tag" → `{Obsolete: 1, …}`, but no screen shows "Obsolete".
**Rules affected:** `get_tags_for_items` R4, `get_tags_for_item` R3, `assignment_exists` R3, `count_active_items_per_tag` R5
**Answer:** intended — per base DAO precedent (HR-4 scope) and item tag DAO P1 / P2: raw lookups; hiding is the caller's decision. Whether the summary of a deleted item should be reachable at all is for the item manager / item summary review.
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-17); rules unchanged. Rules: `get_tags_for_items` R4 ✅, `get_tags_for_item` R3 ✅, `assignment_exists` R3 ✅, `count_active_items_per_tag` R5 ✅.

### P2. Saving an item's tags deletes and re-creates links that did not change — 🐞 BUG-934
**Background:** `PUT /items/{id}/` with `tag_ids` runs `ItemManager.update_item`: it lowers the counter of every active tag the item has, calls this DAO's `remove_all_tags_from_item` (every link of the item is **deleted**), and then attaches each requested tag again (new link row with `assigned_by` = the saving user, `assigned_at` = now; counter +1). The item edit form sends the item's full tag list on every save. The same root cause was ruled a bug for account tags (BUG-870, HR-9: staying tags keep their row) and machine sections (BUG-909).
**What happens today:** Every save with `tag_ids` gives every unchanged tag a new link: new `id`, `assigned_by` = whoever saved, `assigned_at` = now; nothing remembers who first tagged the item. Each unchanged tag's counter goes −1 then +1 (same value in the end, but two writes, each exposed to BUG-931). Verified at DAO level (all links removed, the same pair can be inserted again right after); the manager path itself is for the item manager review.
**Example:** Rahim tags "Bolt M8" with "Steel" in January. In March Karim fixes a typo in the item's description and saves; the form re-sends `tag_ids: [Steel]`. The link now reads "assigned by Karim, March".
**Rules affected:** none of this DAO — `remove_all_tags_from_item` does what its name says (R1–R6). The change is in its caller, `ItemManager.update_item`; to be tagged in the item manager spec (Follow-ups FU-1 (a)).
**Answer:** bug — per BUG-870 / BUG-909 precedent (`unchanged-rows-recreated`, HR-9): when `tag_ids` is sent, links to tags that stay are left untouched (same `id`, `assigned_by`, `assigned_at`) and their counters are not touched; only links to tags no longer in the list are removed (counter −1), only new tags get a link (counter +1). The fix is in `ItemManager.update_item`, which then no longer needs "remove every tag of an item": `remove_all_tags_from_item` loses its only caller and goes to the dead-code list, to be removed together with the fix.
**Resolution:** 🐞 BUG-934 (pattern `unchanged-rows-recreated`; logged against `app/managers/item_manager.py`, fix there) — decided by Claude under the reviewer's delegation (2026-10-17). No rule of this DAO changes: `remove_all_tags_from_item` is reachable today and stays specified and tested as it behaves today. Added to `docs/testing/dead-code-removal-checklist.md` as "remove together with the fix of BUG-934".

### P3. Saving an item's tags erases its links to deleted tags — 🐞 BUG-935
**Background:** A tag is deleted by setting `is_active = False`; its links stay and are hidden (lists of an item's tags skip deleted tags), so restoring the tag (`PUT /item-tags/{id}/` with `is_active: true` — item tag DAO FU-1 (f)) brings it back on its items (standing decision 2, "hidden, not cascaded"; BUG-908 precedent: a cascade that hard-deletes hidden rows is a bug). `ItemManager.update_item` with `tag_ids` calls `remove_all_tags_from_item`, which deletes **every** link of the item, including links to deleted tags (R2); the user cannot re-send a deleted tag because the form does not show it.
**What happens today:** After a save, the item has no link to any deleted tag. The deleted tag's counter is not lowered (only active tags are), so it now counts one item too many. Restoring the tag puts it back on the items that were not saved since its deletion and not on the ones that were. (DAO part verified: links to a deleted tag are removed by `remove_all_tags_from_item`.)
**Example:** Tag "Imported" is on 30 items and is deleted by mistake. During the week, 5 of those items are edited and saved. Support restores "Imported": it shows on 25 items, the 5 saved ones lost it, and its counter still says 30.
**Rules affected:** none of this DAO — `remove_all_tags_from_item` R2 does what the method says. The change is in `ItemManager.update_item` (Follow-ups FU-1 (b)).
**Answer:** bug — per standing decision 2 ("hidden, not cascaded", 2026-10-11) and BUG-908 precedent: a tag save touches only the item's links to **active** tags; links to deleted tags are left as they are (no counter change), stay hidden while the tag is deleted and show again once it is restored. Fix in `ItemManager.update_item` (together with BUG-934).
**Resolution:** 🐞 BUG-935 (pattern `replace-all-erases-hidden-rows`, new; logged against `app/managers/item_manager.py`, fix there) — decided by Claude under the reviewer's delegation (2026-10-17). No rule of this DAO changes.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here except where an ID is given. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Item manager** (`app/managers/item_manager.py`) | (a) `update_item` with `tag_ids`: BUG-934 — staying tags keep their link and counter; only removed / added tags change. Tag the "unchanged tags keep their link" rule with BUG-934. After the fix it no longer calls `remove_all_tags_from_item` (dead-code entry "remove together with the fix of BUG-934"). (b) BUG-935 — links to deleted tags are left untouched by a tag save (no counter change). (c) `update_item` lowers the counters of the item's **active** old tags only (`get_tags_for_item` hides deleted ones) — consistent with (b) once fixed; today a deleted tag's link is erased without its counter being lowered. (d) `delete_item` keeps the item's links (consistent with standing decision 2) and lowers only active tags' counters (item tag DAO FU-2 (c)). (e) `_assign_tags_to_item` uses `assignment_exists` (raw, P1): a requested tag that is already on the item — including a deleted tag whose link survives after BUG-935 — is skipped, and the same id twice in `tag_ids` is attached once (the first `create` flushes, so the second check sees it). It reads the tag with the raw `get` and compares the workspace itself, so link rows never cross workspaces through the API; it accepts deleted tags (item tag DAO FU-2 (a)). (f) `get_tags_for_item` / `get_tags_for_items` (manager) are pass-throughs: they inherit BUG-932 / BUG-933 and P1 (tags of a deleted item are returned). (g) Every counter change goes through the item tag DAO (BUG-931). | P2, P3, P1, HR-6 lines |
| FU-2 | **Item tag service** (`app/services/item_tag_service.py`) | `get_tags` replaces each active tag's `usage_count` with `count_active_items_per_tag` (live count of live items; tags without links → 0). The dict's entries for deleted tags are never read (P1). Same as item tag DAO FU-1 (e). | P1 |
| FU-3 | **Item summary service** (`app/services/item_summary_service.py`) | Shows `get_tags_for_item` on `GET /items/{id}/summary/` — inherits BUG-932 (order) and P1 (a deleted item's tags are shown if the summary of a deleted item is reachable — `ItemManager.get_item` does not check `is_active`). | HR-6 line, P1 |
| FU-4 | **Schemas** (`app/schemas/item_tag_assignment.py`) | `ItemWithTagsResponse` in this module has no user (the item list uses the class of the same name in `app/schemas/item.py`); `ItemTagAssignmentResponse` is used only as this DAO's update-schema type parameter (no caller updates links). Dead-code candidates for whoever describes the schemas; not added to the dead-code list here (not part of this file). | Not specified |

## Overview
`ItemTagAssignmentDAO` reads and deletes rows of `item_tag_assignments` — the links that put a tag on an item ("Bolt M8 is tagged Steel"), many-to-many inside one workspace. Callers: `ItemManager` (create / update / delete item: `assignment_exists`, the inherited `create`, `get_tags_for_item`, `remove_all_tags_from_item`; and the pass-throughs `get_tags_for_item` / `get_tags_for_items` used by the item summary service and the item list), and `ItemTagService.get_tags` (`count_active_items_per_tag`). It is meant to protect workspace isolation (every method filters on the link's own `workspace_id`), to keep deleted tags out of an item's tag lists and deleted items out of tag counts. It validates nothing, never touches tag counters and never commits; `remove_all_tags_from_item` (and the inherited `create`) flush.

**Callables:** 5 specified (+ 1 section on inherited `BaseDAO` behavior specific to this model) · 1 not specified
**Externals to mock:** none. (`assigned_at` is filled by a Python column default, `app.utils.time.utcnow`, bound when the model module is imported — patching `app.utils.time.utcnow` or `app.models.item_tag_assignment.utcnow` does not change it; no method of this file reads the clock.)
**Integration-only behavior:** none.

**Model facts (table `item_tag_assignments`, class `app.models.item_tag_assignment.ItemTagAssignment`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE (`item_tag_assignments_workspace_id_fkey`) | — |
| `item_id` | Integer NOT NULL, FK `items.id` ON DELETE CASCADE (`item_tag_assignments_item_id_fkey`) | — |
| `tag_id` | Integer NOT NULL, FK `item_tags.id` ON DELETE CASCADE (`item_tag_assignments_tag_id_fkey`) | — |
| `assigned_at` | timestamp without time zone NOT NULL | Python `utcnow()` at flush (naive UTC); no database default |
| `assigned_by` | Integer nullable, FK `profiles.id` (`item_tag_assignments_assigned_by_fkey`) | `NULL` |

- **No soft-delete column**: removing a tag from an item deletes the row. Unique `uq_item_tag (item_id, tag_id)` — **across workspaces** (the workspace is not part of it). Indexes: primary key, `uq_item_tag`, plain on `id`, `item_id`, `tag_id`, `workspace_id`. No check constraint, no trigger.
- Nothing in the database ties the link's `workspace_id` to the item's or the tag's workspace (item DAO spec G1): cross-workspace links can be inserted directly. Through the API they cannot be created (`ItemManager` checks the tag's workspace and the item's).
- Hard-deleting an item, a tag or a workspace deletes its links (`ON DELETE CASCADE`); the application never hard-deletes items or tags (both are soft-deleted).
- Relationships: `ItemTagAssignment.item` (backref `Item.tag_assignments`), `.tag` (backref `ItemTag.item_assignments`), `.assigner` (backref `Profile.item_tag_assignments`) — no cascade options; nothing in `app/` reads the backrefs.
- Schema `ItemTagAssignmentCreate` = `item_id: int`, `tag_id: int` — no `workspace_id`, no validators. The DAO's update-schema type is `ItemTagAssignmentResponse` (`id`, `workspace_id`, `item_id`, `tag_id`, `assigned_at`, `assigned_by`); no caller updates links.
- `Item`: NOT NULL `workspace_id`, `name`, `name_normalized`, `unit`; `is_active` (default `True`) is the soft-delete flag. `ItemTag`: NOT NULL `workspace_id`, `name`, `tag_code`; `is_active` (default `True`) is the soft-delete flag; `is_system_tag` (default `False`).
- Database collation of the test database: `English_United States.1252` (libc). `ORDER BY name` uses it.

**Notes for the test designer:**
- Use the module singleton `item_tag_assignment_dao` (`from app.dao.item_tag_assignment import item_tag_assignment_dao`). Every parameter after `db` is keyword-only in all five methods (a positional call raises `TypeError`).
- Workspaces and profiles from `tests/unit/factories.py` (`make_workspace`, `make_profile`). Build `Item` (with `name_normalized` and `unit`), `ItemTag` (with `tag_code`) and `ItemTagAssignment` rows directly (add + flush). The session runs with `autoflush=False`: flush before calling the DAO — a link added but not flushed is invisible to every lookup of this file (`get_tags_for_items` R7, `get_tags_for_item` R5, `assignment_exists` R4).
- **Row order is unspecified today** for `get_tags_for_item` (BUG-932) and for case variants / equal names in `get_tags_for_items` (BUG-933), and the physical order of the test database is **not** deterministic. Write order cases to the intended order and mark them **non-strict** xfail (`strict=False`); never weaken the assertion. Build them so today's result cannot match by accident: give the tags names whose intended order differs from both id-ascending and id-descending order (e.g. ids 1 "bravo", 2 "Alpha", 3 "alpha", 4 "Charlie" → intended 2, 3, 1, 4), and use plain ASCII letter names. The grouping by item and the key set / key order of `get_tags_for_items` (R2) hold today and are normal tests. Every other case compares tags as **sets** of ids.
- **Cross-workspace links** (rules about "a link of this workspace pointing at another workspace's item or tag") can only be built directly; they document what the DAO checks, not an API path.
- **Database errors** (inherited `create`): wrap the call in `with db.begin_nested():` inside `pytest.raises(...)`.
- **Not committed:** `sp = db.begin_nested()`, call, `sp.rollback()`, then re-select.
- **Looking at rows after `remove_all_tags_from_item`:** use a fresh `SELECT` (count of rows where `item_id == I.id`), not `item.tag_assignments` — that collection is not refreshed (R6).

## Not specified
- `item_tag_assignment_dao` — module-level singleton `ItemTagAssignmentDAO(ItemTagAssignment)`, no logic
- Inherited `BaseDAO` methods `get`, `get_multi`, `create`, `update`, `remove`, `get_by_workspace`, `get_by_id_and_workspace` — not overridden; specified in `tests/unit/dao/base.spec.md`. Only what is specific to this model is stated below ("Inherited `BaseDAO` methods on `ItemTagAssignment`").

All five methods of this file have a caller reachable from the API (`get_tags_for_items` ← `GET /items/`; `get_tags_for_item` ← `GET /items/{id}/summary/`, `PUT /items/{id}/`, `DELETE /items/{id}/`; `assignment_exists` ← `POST /items/`, `PUT /items/{id}/`; `count_active_items_per_tag` ← `GET /item-tags/`; `remove_all_tags_from_item` ← `PUT /items/{id}/` with `tag_ids`). The checklist (`docs/testing/unit-test-checklist-by-layer.md`) marks none of them as possibly unused (`get_items_with_tag`, `get_items_with_tags`, `remove_assignment` were already removed). P2 was accepted (2026-10-17, decided by Claude under the reviewer's delegation): `remove_all_tags_from_item` loses its only caller with the fix of BUG-934 and is on `docs/testing/dead-code-removal-checklist.md` as "remove together with the fix of BUG-934"; it is reachable today and is specified and tested as it behaves today. No legacy test calls this DAO (`tests/unit/dao/test_item.py` builds `ItemTagAssignment` rows directly; `tests/test_items_list_pagination.py` and `tests/test_item_summary_empty.py` patch the manager pass-throughs).

---

## `ItemTagAssignmentDAO.get_tags_for_items(db, *, item_ids, workspace_id)`
**Shape:** list (grouped)
**Persistence:** reads
**Visibility:** public (used by: `ItemManager.get_tags_for_items` ← `ItemService.get_items_page` ← `GET /items/`, with the ids of the items on the current page — the tag chips of the item list)

**Purpose:** The active tags of several items at once, grouped by item.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `item_ids` | list[int] | items to look up; not validated; any falsy value (`[]`, `None`) means "none" |
| `workspace_id` | int | equality on the **link's** `workspace_id` |

**Returns:** a `dict` mapping each requested item id to a `list` of `ItemTag` instances (possibly empty lists).

**Rules:**
- **R1.** Given `item_ids` empty (`[]`) or `None`, `{}` is returned and nothing is queried.
- **R2.** Otherwise the result has exactly one key per distinct id in `item_ids`, in the order of first appearance (an id given twice appears once); every id without a matching link — unknown id, item with no tags, item whose links are all in another workspace or all to deleted tags — maps to `[]`.
- **R3.** A tag is listed under an item when a link with that `item_id` and the given `workspace_id` points at it and the tag is active (`is_active = True`). Links recorded under another `workspace_id` are ignored; deleted tags never appear (HR-4 — holds today).
- **R4.** (P1) The item and the tag are not checked further: the active tags of a deleted item (`is_active = False`) are returned like those of a live one; a tag of another workspace, or an item of another workspace, reached through a link whose own `workspace_id` is the given one, is returned (such links cannot be created through the API). ✅
- **R5.** Each tag appears at most once per item (one link per item and tag — `uq_item_tag`). A tag on several requested items appears in each of their lists as the same object.
- **R6.** [BUG-933] (HR-6) Within each item, tags are ordered by `name` case-insensitive ascending, then `id` ascending — the same order as `get_tags_for_item` R4; system tags are not grouped first. E.g. tags "bravo" (id 1), "Alpha" (2), "alpha" (3), "Charlie" (4) come back 2, 3, 1, 4; two tags named "Bolt" come back lower id first. *(Today: ordered by `name` under the database collation with no further key — on the test database `"alpha"` came before `"Alpha"` and `"bolt"` before `"Bolt"` although the capitalised tag had the lower id; tags with the same name come back in an unspecified order.)*
- **R7.** No limit: all matching tags are returned. Only flushed links are seen. Nothing is written.

**Errors:** none.

**Side effects:** none

---

## `ItemTagAssignmentDAO.get_tags_for_item(db, *, item_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ItemManager.get_tags_for_item` ← `ItemSummaryService.get_summary` ← `GET /items/{id}/summary/` (the item's tag chips); `ItemManager.update_item` (when `tag_ids` is sent — the old tags whose counters are lowered) and `ItemManager.delete_item` (the tags whose counters are lowered) ← `PUT /items/{id}/`, `DELETE /items/{id}/`)

**Purpose:** The active tags of one item.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `item_id` | int | equality on the link's `item_id`; not validated |
| `workspace_id` | int | equality on the **link's** `workspace_id` |

**Returns:** a `list` of `ItemTag` instances (possibly empty).

**Rules:**
- **R1.** Returns every active tag (`is_active = True`) that a link with this `item_id` and `workspace_id` points at, each once. An item without links, an unknown item id, or a `workspace_id` other than the links' own returns `[]` (a link recorded under another workspace is never used).
- **R2.** Deleted tags (`is_active = False`) are never returned (HR-4 — holds today); system and user tags are returned alike.
- **R3.** (P1) The item and the tag are not checked further: the tags of a deleted item are returned like those of a live one; a tag of another workspace, or an item of another workspace, reached through a link whose own `workspace_id` is the given one, is returned. For the same item and workspace the result holds the same tags as `get_tags_for_items` gives for that item. ✅
- **R4.** [BUG-932] (HR-6) Ordered by `name` case-insensitive ascending, then `id` ascending; system tags are not grouped first (e.g. "bravo" (1), "Alpha" (2), "alpha" (3), "Charlie" (4) → 2, 3, 1, 4). *(Today: no ordering is requested; the order is whatever the database produces and is not specified.)*
- **R5.** No limit. Only flushed links are seen. Nothing is written.

**Errors:** none.

**Side effects:** none

---

## `ItemTagAssignmentDAO.assignment_exists(db, *, item_id, tag_id, workspace_id)`
**Shape:** get (existence check)
**Persistence:** reads
**Visibility:** public (used by: `ItemManager._assign_tags_to_item`, once per requested tag, to skip a tag already on the item ← `ItemManager.create_item` / `update_item` ← `POST /items/`, `PUT /items/{id}/`)

**Purpose:** Whether a tag is already on an item.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `item_id` | int | equality on the link's `item_id` |
| `tag_id` | int | equality on the link's `tag_id` |
| `workspace_id` | int | equality on the **link's** `workspace_id` |

**Returns:** `bool`.

**Rules:**
- **R1.** Returns `True` when a link with exactly this `item_id`, `tag_id` and `workspace_id` exists; otherwise `False` (no link, unknown ids).
- **R2.** A link recorded under another `workspace_id` does not count: given the pair linked only under workspace B, asking with workspace A gives `False` and asking with B gives `True`. (A link for the same pair in another workspace still blocks a new link through `uq_item_tag` — inherited methods R2.)
- **R3.** (P1) The item and tag rows are not looked at: `True` for a link to a deleted tag, a link of a deleted item, and a link (of this workspace) to a tag of another workspace. ✅
- **R4.** Only flushed links are seen: a link added to the session but not flushed gives `False`.
- **R5.** Nothing is written.

**Errors:** none.

**Side effects:** none

---

## `ItemTagAssignmentDAO.count_active_items_per_tag(db, *, workspace_id)`
**Shape:** compute (aggregate)
**Persistence:** reads
**Visibility:** public (used by: `ItemTagService.get_tags` ← `GET /item-tags/`, which shows each active tag's live item count — `usage_count` is replaced by `result.get(tag.id, 0)`)

**Purpose:** For each tag, the number of live items that carry it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `workspace_id` | int | equality on the **link's** `workspace_id` |

**Returns:** a `dict` `{tag_id: count}` (possibly empty); counts are ≥ 1.

**Rules:**
- **R1.** For every tag with at least one link of the workspace to a live item (`items.is_active = True`), the result holds the tag's id with the number of such links — equal to the number of distinct live items, since an item carries a tag at most once. E.g. "bravo" on 3 live items → `3`.
- **R2.** Links to deleted items (`is_active = False`) are not counted. A tag whose links all point at deleted items, and a tag without links, has **no entry** (not `0`).
- **R3.** Links recorded under another `workspace_id` are not counted. An unknown workspace, or one without links, returns `{}`.
- **R4.** Only the link's own workspace is checked: an item of another workspace linked under this workspace is counted (such links cannot be created through the API).
- **R5.** (P1) The tag's state is not looked at: a deleted tag with links to live items has an entry with its count; system and user tags alike; a tag of another workspace linked under this workspace has an entry. ✅
- **R6.** Only flushed rows are seen. Nothing is written. The dict has no meaningful order.

**Errors:** none.

**Side effects:** none

---

## `ItemTagAssignmentDAO.remove_all_tags_from_item(db, *, item_id, workspace_id)`
**Shape:** delete (bulk)
**Persistence:** writes
**Visibility:** public (used by: `ItemManager.update_item` when `tag_ids` is sent (including `[]`) ← `PUT /items/{id}/`, after lowering the counters of the item's active tags and before attaching the requested tags again — questioned in P2 / BUG-934 and P3 / BUG-935)

**Purpose:** Take every tag off an item and say how many links were removed.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `item_id` | int | item whose links are removed; not validated |
| `workspace_id` | int | only links with this `workspace_id` are removed |

**Returns:** `int` — the number of link rows deleted.

**Rules:**
- **R1.** Every link with this `item_id` and `workspace_id` is deleted (a real DELETE) and their number is returned; e.g. an item with 6 links → `6`, none left.
- **R2.** The tag's and the item's state do not matter: links to deleted tags and links of a deleted item are deleted and counted too (whether the caller should remove links to deleted tags is P3 / BUG-935 — not this method's rule).
- **R3.** Only that item's links of that workspace are touched: links of other items, and a link of the same item recorded under another `workspace_id`, stay. The item and tag rows are never written; no tag counter (`usage_count`) changes.
- **R4.** An item without links, or an unknown item id, returns `0` and deletes nothing.
- **R5.** The deletion is flushed, not committed: a fresh query in the same session finds no link of the item; rolling back a savepoint around the call brings every link back. The flush also writes any other pending change of the session — a link of the item that was added but not yet flushed is **not** deleted by the call and is inserted by its flush (returns `0`, the link exists afterwards).
- **R6.** Link objects of the item already loaded in the session leave it (they are deleted, not stale); a loaded `item.tag_assignments` collection is not refreshed and still lists them until the item is expired or reloaded. A later flush of the item (e.g. after a rename) does not bring the links back, and the same item / tag pair can be linked again right after the call (the update path).

**Errors:** none raised by the method itself (no foreign key points at the link table).

**Side effects:** all `item_tag_assignments` rows of the item in the workspace deleted and flushed (with any other pending change); no commit; no other table written.

---

## Inherited `BaseDAO` methods on `ItemTagAssignment`
**Shape:** create / update / get / list
**Persistence:** writes / reads
**Visibility:** public (used by: `create` with a dict holding `item_id`, `tag_id`, `workspace_id`, `assigned_by` ← `ItemManager._assign_tags_to_item`. `get`, `get_multi`, `update`, `remove`, `get_by_workspace`, `get_by_id_and_workspace`: no caller on this DAO)

**Purpose:** `ItemTagAssignmentDAO` overrides none of the generic methods; the base spec (`tests/unit/dao/base.spec.md`) applies. Only what the `ItemTagAssignment` model and its schemas change is stated.

**Rules:**
- **R1.** `create` with a dict holding `workspace_id`, `item_id`, `tag_id` creates a link with `assigned_at` set (a naive UTC `datetime` taken by Python at flush; not patchable — assert only that it is set and close to now) and `assigned_by` `None` unless given; with `assigned_by` it is stored.
- **R2.** `create` with an `ItemTagAssignmentCreate` always fails: the schema has no `workspace_id`, so the flush raises `IntegrityError` (`NotNullViolation` on `workspace_id`) and nothing is saved. A second link for the same item and tag raises `IntegrityError` (`UniqueViolation`, `uq_item_tag`) — also when the second one is given another `workspace_id`. An unknown `item_id`, `tag_id`, `workspace_id` or `assigned_by` raises `ForeignKeyViolation` (constraint names in the model facts).
- **R3.** `create` checks nothing else: a link to a deleted tag, of a deleted item, or between an item and a tag of different workspaces is saved.
- **R4.** [BUG-100] (HR-6) `get_by_workspace` returns the workspace's links ordered by `id` ascending before `skip` / `limit` (base spec `get_by_workspace` R3). *(Today: no ordering is requested; the fix is in `app/dao/base.py`.)*
- **R5.** `remove` hard-deletes one link (base spec). `update` with a dict sets the given columns (base spec); the model has no `updated_*` / `onupdate` column, so nothing else changes.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `create` without `workspace_id` (any `ItemTagAssignmentCreate`) | `sqlalchemy.exc.IntegrityError`; `.orig` is `psycopg2.errors.NotNullViolation` | — (not asserted) |
| `create` of a second link for the same item and tag (any workspace) | `IntegrityError`; `.orig` is `psycopg2.errors.UniqueViolation` (`uq_item_tag`) | — |
| `create` with an unknown `item_id` / `tag_id` / `workspace_id` / `assigned_by` | `IntegrityError`; `.orig` is `psycopg2.errors.ForeignKeyViolation` (`item_tag_assignments_item_id_fkey` / `_tag_id_fkey` / `_workspace_id_fkey` / `_assigned_by_fkey`) | — |

**Side effects:** as in the base spec.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 19–21, 48–50, 73–75, 98–100, 119–121 | keyword-only parameters | Notes for the test designer |
| 28–29 | `if not item_ids:` → `{}` (`[]`, `None`) / query | `get_tags_for_items` R1 |
| 31–38 | join `item_tags`; `item_id IN`, link `workspace_id`, `ItemTag.is_active`; no item / tag workspace / item state check | `get_tags_for_items` R3, R4, R5 |
| 39 | `ORDER BY item_id, name` — collation name, no tie-break (BUG-933) | `get_tags_for_items` R6 |
| 40 | `.all()` — no limit; flushed rows only | `get_tags_for_items` R7 |
| 43 | one key per distinct requested id, insertion order; unmatched → `[]` | `get_tags_for_items` R2 |
| 44–46 | loop over rows: zero / one / many; same tag object under several items | `get_tags_for_items` R2, R5 |
| 62–70 | join; link `item_id`, link `workspace_id`, `ItemTag.is_active`; no item / tag workspace / item state check; no `ORDER BY` (BUG-932); `.all()` no limit | `get_tags_for_item` R1, R2, R3, R4, R5 |
| 88–94 | link `item_id` + `tag_id` + `workspace_id` filter; no item / tag state check | `assignment_exists` R1, R2, R3 |
| 95–96 | `.first() is not None` → `True` / `False`; flushed rows only | `assignment_exists` R1, R4, R5 |
| 107–113 | join `items`; link `workspace_id`; `Item.is_active`; no tag state / item workspace check | `count_active_items_per_tag` R1, R2, R3, R4, R5 |
| 114–115 | `GROUP BY tag_id`, `count(id)` | `count_active_items_per_tag` R1, R2 |
| 117 | dict from rows: zero / many | `count_active_items_per_tag` R2, R3, R6 |
| 133–139 | bulk DELETE on link `item_id` + `workspace_id`; no tag / item state check; zero / many; loaded objects synchronised, collections not | `remove_all_tags_from_item` R1, R2, R3, R4, R6 |
| 141 | `db.flush()` — also flushes pending changes; no commit | `remove_all_tags_from_item` R5 |
| 142 | return count | `remove_all_tags_from_item` R1, R4 |
| 145 | module singleton | Not specified |
| `base.py` 76–84 | `create`: dict / schema without `workspace_id`; unique pair; FK errors; no other check | inherited R1, R2, R3 |
| `base.py` 108–119, 136–139 | `update` with dict; `remove` | inherited R5 |
| `base.py` 161–167 | `get_by_workspace` no `ORDER BY` (BUG-100) | inherited R4 |
