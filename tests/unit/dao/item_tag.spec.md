# Spec — `app/dao/item_tag.py`

> **Status:** APPROVED (2026-10-17)
> **Source commit:** e48a092

> **Review round 2026-10-17.** The reviewer delegated every open decision of this spec to Claude. Decided by Claude under the reviewer's delegation (2026-10-17): every suggested answer is accepted — P1 (intended), P2 (intended), Q1 (bug, BUG-931), Q2 (intended) and the house-rule lines BUG-929, BUG-930 and BUG-100. None of these is the reviewer's own answer. The "(pilot default — awaiting reviewer)" markers were removed; no rule changed.
>
> **Pilot convention:** every question below carried a suggested answer, applied to the rules as a provisional default. All were accepted on 2026-10-17 (decided by Claude under the reviewer's delegation); nothing is provisional any more.

> **Standing reviewer decisions applied here (not asked again):**
> 1. Soft-deleted rows are kept but must not show up in lists or be counted (inventory DAO Q2, 2026-10-10). **For item tags "deleted" is `is_active = False`**: the model calls the column "Soft delete", `ItemTagService.delete_tag` sets it to `False` and nothing else, and there is no `is_deleted` column (same reading as the item DAO spec, Q7 / Q8). There is no "inactive but live" state for a tag.
> 2. Things of a soft-deleted parent are hidden by the parent's state, their own rows untouched ("hidden, not cascaded", 2026-10-11). A tag has no parent other than its workspace; the rule matters for the tag's assignments (item tag assignment DAO, item manager — Follow-ups).
> 3. "Whitespace" means what `str.strip()` removes. Names are trimmed, never blank, unique per scope ignoring case and outer whitespace, backed by a partial unique index on live rows (HR-1, HR-2; precedents BUG-893 … BUG-896, BUG-911 … BUG-915). No method of this DAO writes or checks a name; where this applies to tags is recorded for the item tag service (Follow-ups FU-1).
> 4. Raw DAO lookups returning deleted rows are intended; the manager / service decides what to hide (base DAO spec, HR-4 scope). Applied in P1 and P2.
> 5. A missing `ORDER BY` in a list query is BUG-100 for inherited base methods, otherwise a new bug against this file. The physical row order of the test database is **not** deterministic: no order recipe in this spec is called verified or deterministic.
> 6. Account tags are the sibling model (`app/dao/account_tag.py` is a near copy of this file). Their decisions — BUG-870 (unchanged assignments deleted and re-created, counts −1 / +1), BUG-871 (unknown tag ids silently dropped), BUG-629 precedent applied as account manager P8 (deleted tag accepted on create / update), BUG-877 (deleting the owner lowers the counts), BUG-864 / BUG-865 (deleted tags ignored by filters / lists) — concern the item manager and the assignment DAO, not this file; they are listed in Follow-ups for those reviews.
>
> **Verified by running** (throwaway script `itag_probe.py` against the test database, rolled back; nothing created or dropped): every "Today:" note below; the table's columns, nullability, defaults (none in the database — every default is applied by Python), constraints, constraint names and indexes (primary key, plain indexes on `id` and `workspace_id`; **no unique index**, no check constraint, no trigger); the database collation (`English_United States.1252`, libc provider); `get_by_code_in_workspace` for the own workspace, another workspace, an unknown workspace, a deleted tag, case and whitespace variants, a prefix, `%`, `""` (stored empty code found), `None`, two tags with one code, positional call (`TypeError`); `get_system_tags_in_workspace` filtering (non-system, deleted system tag, other workspace, unknown workspace); `get_active_tags_in_workspace` filtering and that system tags come first; that on the test database `'alpha' < 'Alpha'` is true, so `"alpha"` sorted before `"Alpha"` although `"Alpha"` had the lower id; both counters: own workspace, other workspace, unknown id, deleted tag, `0`, negative stored value, the returned object, flush (including that it also writes another pending change of the session, and that a decrement at `0` does not), savepoint roll-back, and the loaded-object cases of Q1 (stored 10 / loaded 3 → increment writes 4; stored 0 / loaded 3 → decrement writes 2; after `expire` → 11); the inherited `create` (dict defaults, `created_at` from Python and not changed by patching `app.utils.time.utcnow` or `app.models.item_tag.utcnow`, schema → `NotNullViolation` on `workspace_id`, missing `tag_code`, unknown workspace / profile with constraint names, `color` of 8 and `icon` of 51 characters → `StringDataRightTruncation`, a 500-character name accepted, a duplicate code accepted), `update` with the schema (`None` does not clear) and with a dict, `get` / `get_by_id_and_workspace` / `get_by_workspace` on deleted tags. **Not run:** anything at the service / HTTP level; two concurrent transactions (commits are not allowed — Q1 is shown through a stale loaded object instead); the *intended* behavior of the bug rules.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list — all accepted (decided by Claude under the reviewer's delegation, 2026-10-17)
| # | What the code does today, in plain words | Answer (accepted) |
|---|---|---|
| P1 | "Find the tag with code X" also finds a deleted tag | intended — it is a raw lookup; whoever uses it decides what to do with a deleted tag (same decision as for every other DAO). The effect on "create tag" (a deleted tag's code can never be used again) is for the item tag service review |
| P2 | "Count one more / one less item for this tag" also works on a deleted tag | intended — raw write; the item screens must stop attaching deleted tags (item manager review, same decision as for account tags) |
| Q1 | The tag's item counter is changed from the number the server last read, not from the number stored at that moment. Two people saving items with the same tag at the same moment can lose one of the changes, and the counter stays wrong | bug — the counter is changed in the database in one step ("stored value + 1", "stored value − 1 but never below 0"), so no change is lost; no lock needed — BUG-931 |
| Q2 | Asking to count for a tag that does not exist (or is in another workspace) silently does nothing; the code's own description promises a tag back | intended — "nothing to count" is not an error here; callers check the tag first. Only the description is wrong |

Already decided by house rules / existing bugs (kept as applied — decided by Claude under the reviewer's delegation, 2026-10-17):
- "the system tags of a workspace" (`GET /item-tags/system/`) has **no sort order** → BUG-929 (new; fix in this file).
- "the active tags of a workspace" (`GET /item-tags/`) puts system tags first, then sorts by name the way the database's language setting sorts, with no tie-break: two tags with the same name, or names differing only in capitals, come back in an order that depends on the server → BUG-930 (new; fix in this file).
- "all tags of a workspace" (the generic list, inherited, unused on this DAO) has no sort order → BUG-100 (already logged; the fix in `app/dao/base.py` reaches tags, nothing to do in this file).

### House-rule violations — applied automatically
> All three lines kept as applied — decided by Claude under the reviewer's delegation (2026-10-17).

- **HR-6** `get_system_tags_in_workspace` R3 — no sort order; `GET /item-tags/system/` returns the system tags in whatever order the database produces. Intended: name case-insensitive ascending, then `id` ascending. This is the DAO's own query, so BUG-100 does not cover it (same situation as BUG-903, BUG-906). Not paged, but HR-6 is applied to every list shown to users (BUG-719, BUG-706 precedent).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-929 (pattern `unordered-pagination`; the fix is in `app/dao/item_tag.py`) — decided by Claude under the reviewer's delegation (2026-10-17). Rules: `get_system_tags_in_workspace` R3.
- **HR-6** `get_active_tags_in_workspace` R4 — after "system tags first" (a documented product choice of `GET /item-tags/`, kept), tags are ordered by `name` under the database's collation and nothing else: no case-insensitive key and no `id` tie-break. Tag names are not unique (nothing checks them), so two tags with one name are a normal case and their order is unspecified; names differing only in case are ordered by the collation's case rule (on the test database `"alpha"` before `"Alpha"`; under a `C` collation every capitalised name would come before every lower-case one). Intended: system tags first, then name case-insensitive ascending, then `id` ascending. Same root cause as BUG-623 (name ordered case-sensitively / without the house order).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-930 (pattern `hr-6-non-default-list-order`, per BUG-623; the fix is in `app/dao/item_tag.py`) — decided by Claude under the reviewer's delegation (2026-10-17). Rules: `get_active_tags_in_workspace` R4.
- **HR-6** inherited `get_by_workspace` (inherited methods R5) — no sort order. Intended for this raw lookup: `id` ascending before `skip` / `limit` (HR-6: "generic `BaseDAO` lists only guarantee `id` ascending"). `ItemTagDAO` does not override it, so the BUG-100 fix in `app/dao/base.py` reaches tags with nothing to change in this file. No caller on this DAO.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-100 (existing, pattern `unordered-pagination`, logged against `app/dao/base.py`) — no new ID; decided by Claude under the reviewer's delegation (2026-10-17). Rules: inherited methods R5.

Checked and **not** violated: **HR-4** — both lists of this file (`get_system_tags_in_workspace`, `get_active_tags_in_workspace`) already leave deleted tags out; `get_by_code_in_workspace` and the counters are raw lookups / writes (P1, P2). **HR-5** — no method pages; nothing is filtered after a limit. **HR-7, HR-8** — no `limit`, no `LIKE`. **HR-9** — `item_tags` has no "last changed by" column; the counters stamp nothing. **HR-10** — a usage counter is not money, stock, an approval or a side effect: no row lock is required (Q1 asks for a one-statement update, not a lock). **HR-1 / HR-2** — no method of this DAO writes a name or decides uniqueness; `get_by_code_in_workspace` is the lookup the service's duplicate-code check uses. Codes the application writes are always lower-case with no spaces (schema pattern `^[a-z0-9_]+$`, or derived by lower-casing and dropping every character that is not a letter, digit or `_`), so the exact comparison of R2 does not miss a case / whitespace duplicate of an application-written code. That the table has **no unique index** on the code or the name, that the duplicate check counts deleted tags, and that names are never checked or trimmed are item tag service matters (FU-1).

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-10-17)

### P1. "Find the tag with code X" also finds a deleted tag — ✅ intended
**Background:** Tags are soft-deleted: "delete tag" sets `is_active = False` and the row stays. `get_by_code_in_workspace` is used only by `ItemTagService.create_tag`, which refuses a new tag with 409 `Tag with code '<code>' already exists` when the lookup finds anything. The reviewer decided for every DAO that raw lookups return deleted rows and the caller decides what to hide (base DAO spec, HR-4 scope; factory section DAO P2; machine section assignment DAO P2).
**What happens today:** A deleted tag is found by its code exactly like an active one. Through the service: a deleted tag's code can never be used again by "create tag" (409), although HR-2 says deleted rows do not count. (Verified at DAO level.)
**Example:** Tag "Spare Part" (`spare_part`) is deleted. Creating a new tag "Spare Part" answers 409 "Tag with code 'spare_part' already exists"; the user sees no such tag in the list.
**Rules affected:** `get_by_code_in_workspace` R3
**Answer:** intended — per base DAO precedent (HR-4 scope): a raw lookup; whether a deleted tag's code may be reused (HR-2) — or the deleted tag should be restored instead — is decided in the item tag service review (FU-1 (a)).
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-17); rules unchanged. Rules: `get_by_code_in_workspace` R3 ✅.

### P2. The item counter of a deleted tag still goes up and down — ✅ intended
**Background:** `increment_usage_count` / `decrement_usage_count` find the tag with the raw `get_by_id_and_workspace`, which returns deleted tags. Their only callers are in `ItemManager`: increment when a tag is attached to an item (create / update item), decrement for each of an item's **active** tags when the item is updated with `tag_ids` or deleted. `ItemManager._assign_tags_to_item` checks that the tag exists in the workspace but not that it is active, so a deleted tag can be attached and counted today. For account tags the same gap was ruled a bug in the manager (account manager P8, BUG-629 precedent: a deleted tag is refused on create / update).
**What happens today:** The counter of a deleted tag changes like any other (verified: 2 → 3 on increment, 3 → 2 on decrement).
**Example:** Tag 7 "Obsolete" is deleted. An item is created with `tag_ids: [7]`; the item is tagged "Obsolete" (invisible, since lists hide deleted tags) and tag 7's stored counter goes from 40 to 41.
**Rules affected:** `increment_usage_count` R3, `decrement_usage_count` R5
**Answer:** intended — per base DAO precedent: raw write, the DAO does what it is told; refusing deleted tags belongs in `ItemManager` (FU-2 (a), per BUG-629 / account manager P8 precedent).
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-17); rules unchanged. Rules: `increment_usage_count` R3 ✅, `decrement_usage_count` R5 ✅.

### New questions

### Q1. The tag's item counter can lose changes made at the same time — 🐞 BUG-931
**Background:** Each tag stores `usage_count`, "number of items with this tag". `increment_usage_count` reads the tag through the session, adds 1 **in Python** and writes the result back (`UPDATE … SET usage_count = <number>`); `decrement_usage_count` does the same with −1, and its "never below 0" check also looks at the number in memory. If the tag object was already loaded (earlier in the same request, or by a concurrent request that read it before the other committed), the number written is based on an old value. Two "create item with tag Bolt" requests at the same moment can both read 5 and both write 6. HR-10 does not require a lock for a counter (no money, stock or approval); the question is only whether a lost change is acceptable. The stored counter is shown by `GET /item-tags/system/` and by the create / update tag responses; `GET /item-tags/` replaces it with a live count before answering (item tag service).
**What happens today:** The counter written is "the loaded number ± 1", not "the stored number ± 1". Verified in one transaction: tag loaded with 3, stored value then changed to 10 → increment stores 4 (not 11); tag loaded with 3, stored value then changed to 0 → decrement stores 2 (not 0). A lost change is never repaired.
**Example:** Two users each create an item tagged "Bolt" (counter 5) at the same second. Both requests read 5 and write 6. Two items have the tag; the counter says 6 instead of 7, for ever.
**Rules affected:** `increment_usage_count` R5, `decrement_usage_count` R6 (both tagged)
**Suggested answer:** `bug — the counter is changed in the database in one statement relative to the stored value (usage_count = usage_count + 1; usage_count = usage_count − 1 only where usage_count > 0), and the returned tag shows the stored result`. Alternative: `intended — the stored counter is approximate; screens that need an exact number count live` — then R5 / R6 become "today" rules and no bug is logged. Whether the stored counter should exist at all next to the live count is for the item tag service review (FU-1 (e)).
**Answer:** bug — the counter is changed in the database relative to the stored value, never from a number held in memory; decrement never goes below 0 on the stored value; the returned tag shows the stored result. No row lock needed.
**Resolution:** 🐞 BUG-931 (pattern `non-atomic-counter-update`, new; the fix is in `app/dao/item_tag.py`) — decided by Claude under the reviewer's delegation (2026-10-17): the suggested answer is accepted. Rules: `increment_usage_count` R5, `decrement_usage_count` R6.

### Q2. Counting for a tag that does not exist does nothing, silently — ✅ intended
**Background:** Both counter methods are documented as returning "Updated tag" (annotated `-> ItemTag`). When no tag with that id exists in the workspace they return `None`, write nothing and raise nothing. Their callers in `ItemManager` only pass ids of tags they have just found in the same workspace (an assignment's tag, or a tag checked by `_assign_tags_to_item`), so the `None` path is not reached through the API today.
**What happens today:** `increment_usage_count(tag_id=<unknown or other workspace>)` → `None`, no error, nothing written; the same for decrement. (Verified.)
**Example:** A developer calls `increment_usage_count` with a tag id of another workspace; no error, no counter changes, and code that uses the returned tag fails later with `'NoneType' object has no attribute …`.
**Rules affected:** `increment_usage_count` R2, `decrement_usage_count` R4
**Suggested answer:** `intended` — "nothing to count" is not an error at this level; callers validate the tag first. The annotation / docstring should say `ItemTag | None` when the file is next touched (no bug, no ID). Answer `bug — raise <error>` if a wrong id must never pass silently.
**Answer:** intended
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-17): the suggested answer is accepted; the annotation / docstring is to say `ItemTag | None` when the file is next touched; no bug, no ID. Rules: `increment_usage_count` R2 ✅, `decrement_usage_count` R4 ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here except where an ID is given. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Item tag service** (`app/services/item_tag_service.py`) — not in the item group; to be described separately | (a) `create_tag`'s duplicate-code check uses the raw `get_by_code_in_workspace` (P1): a deleted tag's code blocks reuse for ever (HR-2 "soft-deleted rows do not count"); if reuse is allowed, the lookup can then find two rows with one code and returns either (R4) — the service needs a live-only lookup (new parameter here, or its own query). (b) `item_tags` has **no unique index** (only primary key + plain indexes on `id`, `workspace_id`): code uniqueness is Python-only, two simultaneous creates can both pass (HR-2, BUG-895 / BUG-913 precedent `python-only-uniqueness`). (c) Tag **names** are never checked for duplicates (only the code, and a rename via `update_tag` is not checked at all), and are stored untrimmed; `"   "` passes `min_length=1` (HR-1 / HR-2, BUG-896 / BUG-915 precedent). Whether names or codes are the unique key is that review's question. (d) The code derived from the name keeps any Unicode letter (`str.isalnum`), so it can break the schema's own pattern `^[a-z0-9_]+$` (`"Café"` → `café`), turns outer spaces into `_` (`" Bolt "` → `_bolt_`), and can be empty (`"!!!"` → `""`, stored — R2 shows `""` is then found). (e) `get_tags` overwrites each loaded tag's `usage_count` with a live count of active items (not saved — no commit on GET), while `get_system_tags` and the create / update responses show the stored counter: two different numbers for the same field; whether the stored counter (and Q1 / BUG-931) is needed at all. (f) `update_tag` / `delete_tag` find the tag with the raw `get_by_id_and_workspace`: a deleted tag can be edited, deleted again (204), or brought back with `is_active: true` (BUG-863 precedent `mutation-on-soft-deleted`; restoring through `PUT` may be the intended "restore"). (g) `get_system_tags` (`GET /item-tags/system/`) is not used by the frontend (`useGetSystemTagsQuery` is exported but never called); it is reachable, so not dead code. | P1, Q1, HR-2 check line |
| FU-2 | **Item manager** (`app/managers/item_manager.py`) | (a) `_assign_tags_to_item` reads the tag with the raw `get` (any workspace) and compares the workspace in Python — equivalent to `get_by_id_and_workspace`; it does not check `is_active`, so a deleted tag is attached and counted (P2; BUG-629 / account manager P8 precedent → refuse with "Item tag {id} is not active"); unknown ids are skipped silently (BUG-871 precedent → reject the whole call). (b) `update_item` with `tag_ids` decrements every active old tag, deletes **all** assignments (including assignments to deleted tags) and re-creates the requested ones, incrementing again: unchanged tags get new rows and −1 / +1 (BUG-870 precedent `unchanged-rows-recreated`, HR-9); deleting the assignments of a deleted tag conflicts with "hidden, not cascaded". (c) `delete_item` decrements only **active** tags (the assignment DAO's `get_tags_for_item` hides deleted ones): a deleted tag keeps counting a deleted item, and is off by that much if it is brought back (BUG-877 precedent: deleting lowers each tag's count). (d) All counter changes go through this DAO and inherit Q1 / BUG-931. (e) Cite this spec for: counters never go below 0 (`decrement_usage_count` R2, R3), `None` on a foreign / unknown tag (Q2), counters work on deleted tags (P2). | P2, Q1, Q2 |
| FU-3 | **Item tag assignment DAO** (`app/dao/item_tag_assignment.py`) | `get_tags_for_item` and `get_tags_for_items` join `item_tags` and hide deleted tags (HR-4 — holds); `get_tags_for_item` has no `ORDER BY` (check HR-6); `get_tags_for_items` orders by tag `name` only, the same collation / tie-break issue as BUG-930 (check HR-6, BUG-623 precedent); `count_active_items_per_tag` counts assignments of deleted tags too (only items are filtered) — harmless for `get_tags` since deleted tags are not listed. | BUG-930 |

## Overview
`ItemTagDAO` reads and writes rows of `item_tags` — the labels that categorise items ("Raw Material", "Machine Part", user-made tags) inside one workspace. Six system tags are seeded per workspace by `seed_default_tags` (its own queries, not this DAO). Callers: `ItemTagService` (behind `/item-tags/`: list, system list, create, update, delete) uses the three lookups and the inherited `create` / `update` / `get_by_id_and_workspace`; `ItemManager` uses the two counters and the inherited `get`. It is meant to protect workspace isolation (every method of this file filters by `workspace_id`) and to keep deleted tags out of the two tag lists. It validates nothing, makes no uniqueness check and never commits; the counters flush.

**Callables:** 5 specified (+ 1 section on inherited `BaseDAO` behavior specific to this model) · 1 not specified
**Externals to mock:** none. (`created_at` is filled by a Python column default, `app.utils.time.utcnow`, bound when the model module is imported — patching `app.utils.time.utcnow` or `app.models.item_tag.utcnow` does not change it; no method of this file reads the clock.)
**Integration-only behavior:** none.

**Model facts (table `item_tags`, class `app.models.item_tag.ItemTag`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE (`item_tags_workspace_id_fkey`) | — |
| `name` | varchar (no length limit in the database) NOT NULL | — |
| `tag_code` | varchar (no length limit) NOT NULL | — |
| `color` | varchar(7) nullable | `NULL` |
| `icon` | varchar(50) nullable | `NULL` |
| `description` | text nullable | `NULL` |
| `is_system_tag` | boolean NOT NULL | `False` (Python default) |
| `is_active` | boolean NOT NULL — **the soft-delete flag** (`False` = deleted) | `True` (Python default) |
| `usage_count` | integer NOT NULL, no check constraint (negative values can be stored directly) | `0` (Python default) |
| `created_at` | timestamp without time zone NOT NULL | Python `utcnow()` at flush (naive UTC) |
| `created_by` | Integer nullable, FK `profiles.id` (`item_tags_created_by_fkey`) | `NULL` |

- No `updated_at` / `updated_by`, no `is_deleted`, no `deleted_at`.
- Indexes: primary key, plain `ix_item_tags_id`, plain `ix_item_tags_workspace_id`. **No unique constraint or index** on `tag_code` or `name`; no check constraint; no trigger. Every default is Python-side (the columns have no database default): a row inserted with raw SQL must give every NOT NULL column.
- `item_tag_assignments.tag_id` → `item_tags.id` ON DELETE CASCADE: hard-deleting a tag removes its assignments.
- Schemas: `ItemTagCreate` = `name` (1–100), `tag_code` optional (1–50, `^[a-z0-9_]+$`), `color` (`^#[0-9A-Fa-f]{6}$`), `icon` (≤ 50), `description` — no `workspace_id`, no validators beyond these; `ItemTagUpdate` = `name`, `color`, `icon`, `description`, `is_active`, all optional. Nothing trims.
- Database collation of the test database: `English_United States.1252` (libc). `ORDER BY name` uses it.

**Notes for the test designer:**
- Use the module singleton `item_tag_dao` (`from app.dao.item_tag import item_tag_dao`). Every parameter after `db` is keyword-only in all five methods (a positional call raises `TypeError`).
- Workspaces and profiles from `tests/unit/factories.py` (`make_workspace`, `make_profile`). Build `ItemTag` rows directly (add + flush) with `workspace_id`, `name`, `tag_code`; set `is_system_tag`, `is_active`, `usage_count` explicitly where the case is about them. The session runs with `autoflush=False`: flush before calling the DAO.
- **Reading the stored counter:** after a counter call, read the database value with a fresh query (`db.execute(text("select usage_count from item_tags where id=:i"), …)` or `db.scalar(select(ItemTag.usage_count)…)`), not only the returned object.
- **Q1 / BUG-931 (stale loaded object):** create and flush the tag with `usage_count=3` (so the object is loaded with 3), then change the stored value with a SQL `UPDATE` in the same transaction (`update item_tags set usage_count = 10 …`) **without** expiring the object; call the counter. Intended: increment stores 11 (decrement 9; stored 0 → stays 0) and the returned tag shows it. Today: 4 (decrement 2). Deterministic → **strict** xfail. A control case that expires the object first (`db.expire(tag)`) passes today (11).
- **Row order is unspecified today** for `get_system_tags_in_workspace` (BUG-929) and for ties / case variants of `get_active_tags_in_workspace` (BUG-930), and the physical order of the test database is **not** deterministic. Write order cases to the intended order and mark them **non-strict** xfail (`strict=False`). Use plain ASCII letter names (punctuation and accented letters sort by collation rules). The "system tags first" part of `get_active_tags_in_workspace` (R3) holds today and is a normal test. Every other case compares results as **sets** of ids.
- **Database errors** (inherited `create` / `update`): wrap the call in `with db.begin_nested():` inside `pytest.raises(...)`.
- **Not committed:** `sp = db.begin_nested()`, call, `sp.rollback()`, then re-read.

## Not specified
- `item_tag_dao` — module-level singleton `ItemTagDAO(ItemTag)`, no logic
- Inherited `BaseDAO` methods `get`, `get_multi`, `create`, `update`, `remove`, `get_by_workspace`, `get_by_id_and_workspace` — not overridden; specified in `tests/unit/dao/base.spec.md`. Only what is specific to this model is stated below ("Inherited `BaseDAO` methods on `ItemTag`").

All five methods of this file have a caller reachable from the API (`get_by_code_in_workspace` ← `POST /item-tags/`; `get_system_tags_in_workspace` ← `GET /item-tags/system/`; `get_active_tags_in_workspace` ← `GET /item-tags/`; the counters ← `POST /items/`, `PUT /items/{id}/`, `DELETE /items/{id}/` through `ItemManager`). The checklist (`docs/testing/unit-test-checklist-by-layer.md`) marks none as possibly unused (`get_user_tags_in_workspace` was already removed). No dead code; nothing added to `docs/testing/dead-code-removal-checklist.md`. No legacy test calls this DAO (`tests/unit/dao/test_item.py` builds `ItemTag` rows directly).

---

## `ItemTagDAO.get_by_code_in_workspace(db, *, workspace_id, tag_code)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `ItemTagService.create_tag` ← `POST /item-tags/`, as the duplicate-code check: anything found → 409)

**Purpose:** The tag of a workspace that has a given code, if any.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `workspace_id` | int | equality on the tag's `workspace_id` |
| `tag_code` | str | exact equality on `tag_code`; not validated, not trimmed, not lower-cased |

**Returns:** the `ItemTag` instance, or `None`.

**Rules:**
- **R1.** Given a tag of the workspace with exactly that code, it is returned. A tag of another workspace with the same code is never returned; an unknown workspace id returns `None`.
- **R2.** The comparison is exact: given a stored `raw_material`, the codes `Raw_Material`, `RAW_MATERIAL`, `" raw_material"`, `"raw_material "`, `raw`, `raw_material_` and `raw%` all return `None` (no case folding, no trimming, no prefix or pattern match). `""` finds a tag stored with an empty code; `None` returns `None`.
- **R3.** ✅ (P1) A deleted tag (`is_active = False`) is returned exactly like an active one; `is_system_tag` does not matter.
- **R4.** Given two or more tags of the workspace with the same code (possible: nothing in the database prevents it), one of them is returned; which one is not specified (no ordering). Tests only assert that the result is one of them.
- **R5.** Nothing is written.

**Errors:** none.

**Side effects:** none

---

## `ItemTagDAO.get_system_tags_in_workspace(db, *, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ItemTagService.get_system_tags` ← `GET /item-tags/system/`; not called by the frontend)

**Purpose:** The system (seeded, not user-made) tags of a workspace that are not deleted.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `workspace_id` | int | equality on the tag's `workspace_id` |

**Returns:** a `list` of `ItemTag` instances (possibly empty).

**Rules:**
- **R1.** Returns every tag of the workspace with `is_system_tag = True` and `is_active = True`. User tags (`is_system_tag = False`), deleted system tags and tags of other workspaces are never returned. An unknown workspace, or one without system tags, returns `[]`.
- **R2.** No limit: all matching tags are returned.
- **R3.** [BUG-929] (HR-6) Ordered by `name` case-insensitive ascending, then `id` ascending (e.g. system tags named "Tool", "consumable", "Bolt" come back "Bolt", "consumable", "Tool"). *(Today: no ordering is requested; the order is whatever the database produces and is not specified.)*
- **R4.** Nothing is written.

**Errors:** none.

**Side effects:** none

---

## `ItemTagDAO.get_active_tags_in_workspace(db, *, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ItemTagService.get_tags` ← `GET /item-tags/`, the tag list of the item screens; the service then replaces each tag's `usage_count` with a live count)

**Purpose:** All tags of a workspace that are not deleted, system tags first.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `workspace_id` | int | equality on the tag's `workspace_id` |

**Returns:** a `list` of `ItemTag` instances (possibly empty).

**Rules:**
- **R1.** Returns every tag of the workspace with `is_active = True`, system and user tags alike. Deleted tags (system or not) and tags of other workspaces are never returned. An unknown or empty workspace returns `[]`.
- **R2.** No limit: all matching tags are returned.
- **R3.** Every system tag comes before every user tag (holds today).
- **R4.** [BUG-930] (HR-6) Within each group, tags are ordered by `name` case-insensitive ascending, then `id` ascending: user tags "bravo", "Alpha" (id 1), "alpha" (id 2), "Charlie" come back "Alpha" (1), "alpha" (2), "bravo", "Charlie"; two tags both named "Bolt" come back lower id first. *(Today: ordered by `is_system_tag` descending, then `name` under the database collation, with no further key — names differing only in case follow the collation's case rule (on the test database `"alpha"` before `"Alpha"`), and tags with the same name come back in an unspecified order.)*
- **R5.** Nothing is written.

**Errors:** none.

**Side effects:** none

---

## `ItemTagDAO.increment_usage_count(db, *, tag_id, workspace_id)`
**Shape:** update (counter)
**Persistence:** writes
**Visibility:** public (used by: `ItemManager._assign_tags_to_item`, once per tag newly attached to an item ← `ItemManager.create_item` / `update_item` ← `POST /items/`, `PUT /items/{id}/`; the manager has already found the tag in the workspace)

**Purpose:** Count one more item for a tag.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `tag_id` | int | the tag; looked up with `get_by_id_and_workspace` (base spec) |
| `workspace_id` | int | the tag must have this `workspace_id` |

**Returns:** the `ItemTag` (the session's instance, flushed, not committed), or `None` when no tag with that id exists in the workspace.

**Rules:**
- **R1.** Given a tag with that id in that workspace, its stored `usage_count` goes up by exactly 1 and the tag is returned (the same instance the session holds); e.g. 2 → 3.
- **R2.** ✅ (Q2) Given an id that does not exist, or a tag of another workspace, `None` is returned, nothing is written and no error is raised.
- **R3.** ✅ (P2) A deleted tag (`is_active = False`) and a system tag are counted like any other.
- **R4.** There is no upper bound and no sign check: a stored negative value (only possible by a direct write) goes up by one (−2 → −1).
- **R5.** [BUG-931] (Q1) The increase is applied to the value stored in the database at that moment, not to a value held in memory: given a tag whose loaded object says 3 while the stored value is 10, the stored value becomes 11 and the returned tag shows 11. *(Today: the loaded value is used — 4 is stored and returned, the other change is lost. With a freshly loaded or expired object the result is already correct: 11.)*
- **R6.** The change is flushed, not committed: a fresh query in the same session sees the new value; rolling back a savepoint around the call restores the old one. The flush also writes any other pending change of the session (e.g. an unflushed rename of the same tag is saved with it).

**Errors:** none raised by the method itself.

**Side effects:** at most one `item_tags` row's `usage_count` changed, flushed (together with whatever else was pending in the session); no commit; no other column or table written.

---

## `ItemTagDAO.decrement_usage_count(db, *, tag_id, workspace_id)`
**Shape:** update (counter)
**Persistence:** writes
**Visibility:** public (used by: `ItemManager.update_item` — once per **active** tag of the item when `tag_ids` is sent, before all its assignments are removed — and `ItemManager.delete_item` — once per active tag of the item ← `PUT /items/{id}/`, `DELETE /items/{id}/`)

**Purpose:** Count one item less for a tag, never going below zero.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `tag_id` | int | the tag; looked up with `get_by_id_and_workspace` (base spec) |
| `workspace_id` | int | the tag must have this `workspace_id` |

**Returns:** the `ItemTag` (the session's instance), or `None` when no tag with that id exists in the workspace.

**Rules:**
- **R1.** Given a tag of the workspace with `usage_count` above 0, its stored `usage_count` goes down by exactly 1 and the tag is returned; e.g. 3 → 2, 1 → 0.
- **R2.** Given a tag with `usage_count = 0`, nothing is written: the value stays 0 and the tag is returned. This call flushes nothing (another pending change of the session stays unflushed).
- **R3.** Given a tag with a negative stored `usage_count` (only possible by a direct write), nothing is written and the tag is returned with its value unchanged (−2 stays −2).
- **R4.** ✅ (Q2) Given an id that does not exist, or a tag of another workspace, `None` is returned, nothing is written and no error is raised.
- **R5.** ✅ (P2) A deleted tag (`is_active = False`) and a system tag are decremented like any other.
- **R6.** [BUG-931] (Q1) The decrease and the "not below 0" check are applied to the value stored in the database at that moment, not to a value held in memory: loaded object 3 / stored 10 → stored 9, returned tag shows 9; loaded object 3 / stored 0 → stays 0, returned tag shows 0. *(Today: the loaded value is used — 2 is stored in both cases.)*
- **R7.** When a value is written it is flushed, not committed: a fresh query in the same session sees it; rolling back a savepoint around the call restores the old one. As in `increment_usage_count` R6, the flush also writes other pending changes of the session.

**Errors:** none raised by the method itself.

**Side effects:** at most one `item_tags` row's `usage_count` changed, flushed when changed; no commit; no other column or table written.

---

## Inherited `BaseDAO` methods on `ItemTag`
**Shape:** create / update / get / list
**Persistence:** writes / reads
**Visibility:** public (used by: `create` with a dict ← `ItemTagService.create_tag`; `update` with an `ItemTagUpdate` ← `ItemTagService.update_tag` and with `{"is_active": False}` ← `ItemTagService.delete_tag`; `get_by_id_and_workspace` ← `ItemTagService.update_tag` / `delete_tag` and this DAO's two counters; `get` ← `ItemManager._assign_tags_to_item` (the manager compares the workspace itself). `get_by_workspace`, `get_multi`, `remove`: no caller on this DAO)

**Purpose:** `ItemTagDAO` overrides none of the generic methods; the base spec (`tests/unit/dao/base.spec.md`) applies. Only what the `ItemTag` model and its schemas change is stated.

**Rules:**
- **R1.** `create` with a dict holding `workspace_id`, `name`, `tag_code` creates a tag with `is_system_tag = False`, `is_active = True`, `usage_count = 0`, `created_at` set (a naive UTC `datetime` taken by Python at flush; not patchable — assert only that it is set and close to now), and `created_by`, `color`, `icon`, `description` `None`.
- **R2.** `create` with an `ItemTagCreate` always fails: the schema has no `workspace_id`, so the flush raises `IntegrityError` (`NotNullViolation` on `workspace_id`) and nothing is saved. A dict without `tag_code` fails the same way on `tag_code`. An unknown `workspace_id` raises `ForeignKeyViolation` (`item_tags_workspace_id_fkey`); an unknown `created_by`, `ForeignKeyViolation` (`item_tags_created_by_fkey`). A `color` longer than 7 or an `icon` longer than 50 characters raises `sqlalchemy.exc.DataError` (`.orig` `StringDataRightTruncation`, pgcode `22001`). `name` and `tag_code` have no length limit in the database (a 500-character name is saved; the 100 / 50 limits exist only in the schemas).
- **R3.** `create` checks no uniqueness: a second tag of the workspace with the same `tag_code` and / or the same `name` is saved (no unique index — FU-1 (b)).
- **R4.** `update` with an `ItemTagUpdate` applies only fields set to a value: `ItemTagUpdate(name="B", color=None)` changes the name and keeps the colour — `color`, `icon`, `description` cannot be cleared through the schema (base spec `update` R2, R3 ✅). `update` with a dict sets any column given, including `{"is_active": False}` (the service's delete), `{"is_active": True}` and `{"color": None}`.
- **R5.** [BUG-100] (HR-6) `get_by_workspace` returns the workspace's tags ordered by `id` ascending before `skip` / `limit` (base spec `get_by_workspace` R3). *(Today: no ordering is requested; the fix is in `app/dao/base.py`.)*
- **R6.** The raw lookups stay raw (HR-4 scope): `get`, `get_by_id_and_workspace` and `get_by_workspace` return deleted tags like active ones; `get` returns a tag of any workspace; `get_by_id_and_workspace` returns `None` for a tag of another workspace (base spec).
- **R7.** `remove` hard-deletes the tag and, through `ON DELETE CASCADE`, its `item_tag_assignments` rows (base spec `remove` R4). No caller.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `create` without `workspace_id` (any `ItemTagCreate`) or without `tag_code` / `name` | `sqlalchemy.exc.IntegrityError`; `.orig` is `psycopg2.errors.NotNullViolation` | — (not asserted) |
| `create` with an unknown `workspace_id` or `created_by` | `IntegrityError`; `.orig` is `psycopg2.errors.ForeignKeyViolation` | — |
| `create` with `color` > 7 or `icon` > 50 characters | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.StringDataRightTruncation` | — |

**Side effects:** as in the base spec.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 14, 37, 60, 83, 103 | keyword-only parameters | Notes for the test designer |
| 27–32 | `workspace_id` + exact `tag_code` filter; no `is_active` filter | `get_by_code_in_workspace` R1, R2, R3 |
| 33 | `.first()` without `ORDER BY` → row / `None`; duplicates → either | `get_by_code_in_workspace` R1, R4, R5 |
| 50–55 | `workspace_id` + `is_system_tag` + `is_active` filter | `get_system_tags_in_workspace` R1 |
| 56 | `.all()` — no limit, no `ORDER BY` (BUG-929); empty / many | `get_system_tags_in_workspace` R1, R2, R3, R4 |
| 73–77 | `workspace_id` + `is_active` filter | `get_active_tags_in_workspace` R1 |
| 78 | `ORDER BY is_system_tag DESC, name` — system first; collation name order, no tie-break (BUG-930) | `get_active_tags_in_workspace` R3, R4 |
| 79 | `.all()` — no limit; empty / many | `get_active_tags_in_workspace` R1, R2, R5 |
| 96 (+ `base.py` `get_by_id_and_workspace`) | raw lookup in the workspace: found / other workspace / unknown; deleted tag found | `increment_usage_count` R1, R2, R3 |
| 97 | `if tag:` → increment / return `None` | `increment_usage_count` R1, R2 |
| 98 | `+= 1` on the loaded value (BUG-931); no bound | `increment_usage_count` R4, R5 |
| 99–100 | flush (all pending changes), return the instance | `increment_usage_count` R6 |
| 116 (+ `base.py` `get_by_id_and_workspace`) | raw lookup in the workspace; deleted tag found | `decrement_usage_count` R4, R5 |
| 117 | `if tag and tag.usage_count > 0:` — not found / `0` / negative / positive; check on the loaded value (BUG-931) | `decrement_usage_count` R1, R2, R3, R4, R6 |
| 118–119 | `-= 1` on the loaded value, flush | `decrement_usage_count` R1, R6, R7 |
| 120 | return tag or `None` | `decrement_usage_count` R1, R2, R3, R4 |
| 123 | module singleton | Not specified |
| `base.py` 76–84 | `create`: schema lacks `workspace_id`; dict; Python defaults; length / FK errors; no uniqueness | inherited R1, R2, R3 |
| `base.py` 108–119 | `update` with schema (`exclude_none`) / dict | inherited R4 |
| `base.py` 161–167 | `get_by_workspace` no `ORDER BY` (BUG-100) | inherited R5 |
| `base.py` 43, 186–194 | `get` / `get_by_id_and_workspace` raw | inherited R6 |
| `base.py` 136–139 | `remove` hard delete, cascade to assignments | inherited R7 |
