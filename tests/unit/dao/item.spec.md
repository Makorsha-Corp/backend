# Spec — `app/dao/item.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically
> Added in fill-gaps (case-designer gaps 4 and 5). Overwrite an answer only if the house rule should NOT apply here.

- **HR-8** `_apply_item_catalog_filters` R9, R12 — a backslash `\` in the search text acts as the `ILIKE` escape character instead of matching literally (search `a\b` finds "ab", not "a\b"). Intended: backslash matched literally, like `%` and `_`. Same fix as BUG-013 (escaping the search text) — log against BUG-013, no new ID.
**Answer:** bug — per HR-8 (house rule)
**Resolution:** 🐞 BUG-013 (extended, no new ID) — backslash matched literally like `%` and `_`. Rules: `_apply_item_catalog_filters` R9, R12.
- **HR-6** `list_active_items_filtered` R3, R4 — the catalog page is ordered by `id` ascending, not by the house default. Intended: name case-insensitive ascending, then `id` ascending, applied before `skip`/`limit`. (Overwrite with `intended — <reason>` if id/creation order is a deliberate product choice for the catalog.)
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-033 — catalog page ordered by name case-insensitive ascending, then `id` ascending, before `skip`/`limit`. Rules: `list_active_items_filtered` R3, R4.

### Precedent matches — confirm all with ok

### Q1. Name search of items has no sort order — ⏭️ superseded by Q4 (method removed)
**Background:** `search_by_name_in_workspace` pages through matching items with `skip`/`limit` but the query has no `ORDER BY`; Postgres may return rows in any order, and that order can change after updates.
**What happens today:** Which items land on which page is not guaranteed; paging with `skip` can repeat or skip items.
**Example:** 150 active items contain "bolt". Page 1 (`skip=0, limit=100`) is loaded, someone edits an item, page 2 (`skip=100`) is loaded — one item appears on both pages and another on neither.
**Rules affected:** `search_by_name_in_workspace` R5
**Answer:** bug — per BUG-008 precedent: apply a defined order before paging — name case-insensitive ascending, `id` ascending as tie-breaker (precedent — confirmed: ok)
**Resolution:** no bug logged — Q4 ruled `search_by_name_in_workspace` dead code to be removed, so there is no behavior left to fix or test.

### Q2. Active-items list has no sort order — ⏭️ superseded by Q4 (method removed)
**Background:** Same mechanism as Q1, in `get_active_items_in_workspace` (all active items of a workspace, paged).
**What happens today:** Page contents and order are not guaranteed; paging can repeat or skip items.
**Example:** 250 active items; fetching `skip=0`, `skip=100`, `skip=200` with `limit=100` does not guarantee every item is seen exactly once.
**Rules affected:** `get_active_items_in_workspace` R3
**Answer:** bug — per BUG-008 precedent: apply a defined order before paging — name case-insensitive ascending, `id` ascending as tie-breaker (precedent — confirmed: ok)
**Resolution:** no bug logged — Q4 ruled `get_active_items_in_workspace` dead code to be removed.

### Q3. "Exclude this item" option of similar-name lookup is unreachable from the API — 🐞 BUG-011
**Background:** The similar-name lookup (used before creating an item, to warn about duplicates) accepts `exclude_item_id` to leave one item out of the results — e.g. the item being renamed. `ItemService.get_similar_items` accepts it, but the `GET /items/similar/` endpoint never passes it.
**What happens today:** No API caller can exclude an item; when editing an item, the item itself always shows up as its own "similar" match.
**Example:** Item 12 "Steel Rod 22m" is opened for renaming; the frontend calls `GET /items/similar/?name=Steel Rod 22m` and gets item 12 back as an exact match, warning the user about a duplicate of itself.
**Rules affected:** `find_similar_by_name_in_workspace` R8
**Answer:** bug — per BUG-010 precedent: expose `exclude_item_id` on `GET /items/similar/` (endpoint passes it through to the service) (precedent — confirmed: ok)
**Resolution:** `GET /items/similar/` must accept `exclude_item_id` and pass it through; DAO behavior is already correct. Rules: `find_similar_by_name_in_workspace` R8.

### New questions

### Q4. Two list methods are not reachable from any endpoint — 🗑️ removed
**Background:** `search_by_name_in_workspace` and `get_active_items_in_workspace` are only called by `ItemManager.search_items`, which is only called by `ItemService.get_items`. Nothing calls `ItemService.get_items`: the `GET /items/` endpoint uses the newer catalog list (`list_active_items_filtered` + `count_active_items_filtered`) instead.
**What happens today:** Both methods (and the manager/service methods above them) run only if called from code; no user action reaches them.
**Example:** A user searching the item catalog for "bolt" goes through the catalog list, which also searches description, SKU, unit, id and tag names — never through `search_by_name_in_workspace`, which searches name only.
**Rules affected:** `search_by_name_in_workspace` (all), `get_active_items_in_workspace` (all)
**Answer:** remove
**Resolution:** both methods moved to Not specified as dead code; sections and Branch-map rows deleted; logged in `docs/testing/dead-code-removal-checklist.md` together with the now-orphaned `ItemManager.search_items` and `ItemService.get_items`.

### Q5. Searching with certain digit characters crashes the item list — 🐞 BUG-012
**Background:** When the catalog search text consists only of digits, the item's `id` is also matched. The "is it digits" check accepts any Unicode digit character, including superscripts like `²` and `³`, but converting such text to a number fails.
**What happens today:** A search text like `²` or `2²` raises an unhandled `ValueError`; the API returns a 500 server error instead of results. (Other scripts' digits such as Arabic-Indic `١٢` convert fine and match id 12.)
**Example:** A user types `²` into the catalog search box (e.g. meaning to find "Sheet 2 m²"). `GET /items/?search=²` returns 500; the list does not load.
**Rules affected:** `_apply_item_catalog_filters` R11
**Answer:** bug — a search made only of non-ASCII digit characters (e.g. `²`) must not error; only plain ASCII digits `0-9` also match the item id, anything else is searched as text only
**Resolution:** only ASCII `0-9` search text adds the id match; any other digit characters are text-only and never raise. Rules: `_apply_item_catalog_filters` R11; `list_active_items_filtered` R6; `count_active_items_filtered` R4.

### Q6. `%` and `_` in the catalog search act as wildcards — 🐞 BUG-013
**Background:** The search text is placed inside a SQL `ILIKE '%text%'` pattern without escaping. In that pattern `%` means "any characters" and `_` means "any single character".
**What happens today:** A search containing `%` or `_` matches more than the literal text; a search of just `_` or `%` matches every item.
**Example:** Workspace has SKUs "AB_12" and "ABX12". Searching `AB_12` returns both. Searching `50%` returns "50 kg bag", "500 ml bottle", etc., not only items containing "50%".
**Rules affected:** `_apply_item_catalog_filters` R9
**Answer:** bug — `%` and `_` in the search text are matched literally (escaped), not as wildcards
**Resolution:** `%` and `_` are matched literally in every text alternative of the search. Rules: `_apply_item_catalog_filters` R9, R12.

### Q7. Filtering by a deleted tag still returns items — 🐞 BUG-014
**Background:** Deleting a tag is a soft delete: the tag's `is_active` becomes `False`, and its assignments to items are kept. The item list hides deleted tags from each item's tag chips.
**What happens today:** Filtering the catalog by a deleted tag's id still returns every item that had that tag, even though none of them shows the tag.
**Example:** Tag 7 "Obsolete" is deleted. `GET /items/?tag_ids=7` returns the 40 items that were tagged "Obsolete"; none of them displays an "Obsolete" chip.
**Rules affected:** `_apply_item_catalog_filters` R6
**Answer:** bug — filtering by a deleted tag (`is_active = False`) matches no items through that tag
**Resolution:** assignments to deleted tags are ignored by the tag filter. Rules: `_apply_item_catalog_filters` R6.

### Q8. Search matches the names of deleted tags — 🐞 BUG-015
**Background:** Same mechanism as Q7. The catalog search also matches items through the names of tags assigned to them.
**What happens today:** Searching for text found only in a deleted tag's name still returns the items that had that tag.
**Example:** Tag "Obsolete" is deleted. Searching `obsol` returns the 40 formerly-tagged items; the user sees items whose name, SKU, description and visible tags contain no "obsol".
**Rules affected:** `_apply_item_catalog_filters` R12
**Answer:** bug — deleted tags (`is_active = False`) are ignored by the tag-name search
**Resolution:** tag-name search considers only active tags. Rules: `_apply_item_catalog_filters` R12.

### Q9. A negative page size crashes the item list; zero returns an empty page — 🐞 BUG-016
**Background:** The `GET /items/` endpoint caps `limit` at 100 but sets no minimum. This module passes `limit` straight to the database.
**What happens today:** `limit=-1` makes Postgres reject the query ("LIMIT must not be negative") and the API returns 500. `limit=0` returns no items while `total` is non-zero and `has_more` is `true`, forever.
**Example:** A client sends `GET /items/?limit=-1` and gets 500. A client sends `limit=0` and gets `{"items": [], "total": 120, "has_more": true}` on every page.
**Rules affected:** `list_active_items_filtered` R5
**Answer:** bug — the API requires `limit >= 1` (422 otherwise), same for any list endpoint feeding this DAO
**Resolution:** fix belongs in the `GET /items/` endpoint (`limit` gets `ge=1`); `GET /items/similar/` already enforces `1 <= limit <= 10`, and no other endpoint reaches this DAO's paged methods. DAO behavior itself is unchanged. Rules: `list_active_items_filtered` R5, R7.

### Q10. Unit list shows each spelling of a unit separately — 🐞 BUG-017
**Background:** Item units are free text and are stored exactly as typed (no trimming or case change). The unit dropdown lists the distinct stored values; filtering by unit is an exact, case-sensitive match.
**What happens today:** "kg", "KG" and "kg " (trailing space) appear as three separate units, and choosing one shows only the items spelled exactly that way.
**Example:** 30 items use "kg", 5 use "Kg". The dropdown shows "Kg" and "kg"; picking "kg" shows 30 items, not 35.
**Rules affected:** `distinct_units_in_workspace` R4, `_apply_item_catalog_filters` R4
**Answer:** bug — units are stored trimmed, and unit listing and unit filtering compare case-insensitively (same normalisation as the department-name decision, BUG-002/BUG-004); the unit list shows one entry per unit
**Resolution:** unit filter is case-insensitive; unit list has one entry per case-insensitive unit; trimming on write belongs in the item create/update path (schema/manager), not this DAO. Rules: `_apply_item_catalog_filters` R4; `distinct_units_in_workspace` R4, R5. The `unit` filter value is itself trimmed (proposed fix confirmed `ok` in second review round). Display spelling of the merged entry: resolved by Q12 (lowercase).

### Q11. Similar-name suggestions with equal scores come back in no fixed order — 🐞 BUG-018
**Background:** The similar-name lookup returns the top N matches (default 5, API allows 1–10) sorted by similarity score. There is no second sort key.
**What happens today:** When more items tie on score than fit in N, which of them are shown — and in what order — is not guaranteed and can differ between calls.
**Example:** Workspace has 7 items all normalized to "steel rod 22m" (score 1.0). `GET /items/similar/?name=Steel Rod 22 m&limit=5` returns 5 of the 7; a repeat call may return a different 5.
**Rules affected:** `find_similar_by_name_in_workspace` R9
**Answer:** bug — ties on score are broken by name case-insensitive ascending, then `id` ascending
**Resolution:** order is score descending, then name case-insensitive ascending, then `id` ascending, applied before the `limit` cut. Rules: `find_similar_by_name_in_workspace` R9.

### Q12. Which spelling does a merged unit show in the unit list? (follow-up to Q10) — 🐞 BUG-017
**Background:** Per Q10, "kg", "Kg" and "KG" become one entry in the unit dropdown. Units are still stored as the user typed them (only trimmed), so the three items keep their own spelling; the list must pick one string to show for the merged entry.
**What happens today:** Not applicable — each spelling is its own entry.
**Example:** 30 items use "kg", 5 use "Kg", 1 uses "KG". The dropdown shows one entry. Options: (a) lowercase `"kg"` always; (b) the most-used spelling (`"kg"`, ties broken by …); (c) the alphabetically first stored spelling (`"KG"` under byte ordering). Whatever is shown, picking it must return all 36 items (guaranteed by the case-insensitive filter).
**Rules affected:** `distinct_units_in_workspace` R4, R5
**Answer:** lowercase — the unit list always shows the lowercase form (e.g. "kg")
**Resolution:** part of BUG-017 (no new bug): each merged entry is shown in lowercase, whatever spellings are stored. Rules: `distinct_units_in_workspace` R1, R4, R5.

### Q13. A similarity score of exactly 0.35 is left out, although the threshold is "0.35 or more" — 🐞 BUG-034
**Background:** The similar-name lookup keeps items whose trigram similarity score is at least 0.35. Postgres computes the score as a low-precision number (`real`, ~7 significant digits); a score that is mathematically 0.35 (e.g. 7 shared trigrams out of 20) is stored as 0.3499999940…. The code compares that against 0.35 in full (double) precision, so it counts as *below* the threshold. The API rounds scores to 4 decimals, so such an item would be shown as `0.35` if it were returned.
**What happens today:** An item whose score is exactly 0.35 (to the precision users ever see) is not suggested; the threshold is effectively "more than 0.35".
**Example:** Stored item normalized "abcdefghijklmnopqr"; the user types "abcdefg" (score 7/20 = 0.35). The suggestion list is empty. Change the stored name so the score is 7/19 ≈ 0.3684 and it is suggested.
**Rules affected:** `find_similar_by_name_in_workspace` R4
**Suggested answer:** `bug — compare in the score's own precision (threshold as real, e.g. score >= 0.35::real), so a score that is 0.35 is included`. (Alternative: `intended` — then R4's boundary becomes "a score of 7/20 is excluded" and "exactly 0.35 is included" is dropped.)
**Answer:** bug — a score of exactly 0.35 is included (compare in the score's own `real` precision)
**Resolution:** the threshold is compared in `real` precision, so a score of 7/20 (0.35 as `real`) is included. Rules: `find_similar_by_name_in_workspace` R4a.

### Q14. Units stored before the trimming fix (e.g. "kg ") — merged with "kg" or not? — 🐞 BUG-017
**Background:** Per BUG-017 (Q10/Q12), units will be stored trimmed from now on, and the unit filter and unit list compare case-insensitively. Rows saved before that fix may still hold untrimmed units such as `"kg "` or `" "`. Nothing decided yet says whether the list/filter must cope with them, or whether existing rows get cleaned up once.
**What happens today:** `"kg "` is its own unit-list entry and is matched only by the exact filter value `"kg "`.
**Example:** 30 items have unit `"kg"`, 4 old items have `"kg "`. After the BUG-017 fix, if only new writes are trimmed: the dropdown shows `"kg"` and `"kg "` (two entries that look identical) and choosing `"kg"` shows 30 items, not 34. A whitespace-only legacy unit `" "` also still appears as a blank-looking entry.
**Rules affected:** `_apply_item_catalog_filters` R4; `distinct_units_in_workspace` R3, R4
**Suggested answer:** `bug — the DAO compares and groups on the trimmed, lowercased unit (so "kg " matches unit="kg" and merges into the "kg" entry; a stored whitespace-only unit counts as "" and is never listed); a one-off data migration trimming existing units is optional`.
**Answer:** bug — the DAO filters and groups on the trimmed, lowercased unit, so legacy untrimmed values merge with clean ones
**Resolution:** part of BUG-017 (no new bug; register row extended): the unit filter and unit list work on each stored unit trimmed and lowercased, so `"kg "` matches `unit="kg"` and merges into the `"kg"` entry; a stored whitespace-only unit counts as `""` and is never listed. No data migration required. Rules: `_apply_item_catalog_filters` R4; `distinct_units_in_workspace` R3a, R4.

## Overview
Read-only queries over the item catalog (materials, parts, supplies, services) of a workspace. Called only by `ItemManager` (`list_items_filtered`, `count_items_filtered`, `distinct_units`, `find_similar_items`), which is called by `ItemService`, which backs `GET /items/`, `GET /items/units/` and `GET /items/similar/`. Invariants it is meant to protect: workspace isolation (an item is never returned for another workspace) and soft-delete visibility (items with `is_active = False` are deleted and never returned by any method here; soft-deleted tags do not make an item match). Nothing here writes; nothing flushes or commits.

**Callables:** 5 specified · 9 not specified
**Externals to mock:** none
**Integration-only behavior:** `list_active_items_filtered` R7 (the `limit >= 1` validation lives in the `GET /items/` endpoint and is only observable through HTTP). Note: `find_similar_by_name_in_workspace` uses the Postgres `pg_trgm` extension's `similarity()` function; the test database must have `pg_trgm` installed (the baseline migration creates it; a schema built only with `Base.metadata.create_all` will not have it).

**Fixture notes for the test designer:** `Item.name`, `Item.name_normalized`, `Item.unit`, `Item.workspace_id` are NOT NULL. This DAO never derives `name_normalized` — fixtures must set it explicitly (normally `ItemManager` sets it to the normalized form of `name`, see `normalize_item_name` below). `is_active` defaults to `True`. Tags: `ItemTag` (`workspace_id`, `name`, `tag_code` NOT NULL; `is_active` default `True`) linked to items through `ItemTagAssignment` (`workspace_id`, `item_id`, `tag_id` NOT NULL; unique per `(item_id, tag_id)`). No constraint or trigger ties an assignment's `workspace_id` to its item's or tag's workspace (the table has only its primary key, `uq_item_tag`, and foreign keys to `workspaces`, `items`, `item_tags`, `profiles`), so an assignment whose `workspace_id` differs from its item's and/or tag's workspace can be inserted directly. Per BUG-017, units are intended to be stored trimmed, but the DAO must also cope with untrimmed legacy values (Q14); fixtures may insert untrimmed units such as `"kg "` directly to test that.

**Name normalization (collaborator `normalize_item_name`, used by `find_similar_by_name_in_workspace`):** empty/`None` → `""`; otherwise lowercase, trim, collapse runs of whitespace to one space, glue a number to a following 1–4 letter word (`"22 m"` → `"22m"`), replace every character that is not a letter, digit, underscore or whitespace with a space, collapse whitespace again and trim. Examples: `"Steel  Rod 22 m"` → `"steel rod 22m"`; `"Bolt-M8"` → `"bolt m8"`; `"!!!"` → `""`. Constants: minimum normalized length `3`, similarity threshold `0.35`. Its own edge cases belong to the `app/utils/item_name_normalize.py` spec.

**Similarity score facts:** `pg_trgm`'s `similarity()` returns `real` (float4). The threshold `0.35` is bound from Python (psycopg2 sends it as a numeric literal), and Postgres resolves `real >= numeric` to the `real >= double precision` operator, so the comparison happens in double precision. A score of 7/20 is `real` 0.3499999940395355 and is therefore excluded today (see Q13; intended to be included — BUG-034). The score returned to Python is that `real` widened to a `float` (e.g. `0.3499999940395355`, `0.3684210479259491`).

**Notes for the test designer:**
- A negative `limit`/`skip` aborts the current Postgres transaction; run such calls inside a savepoint (`db.begin_nested()`) and roll it back before re-reading.
- Cross-workspace assignment rows (for `_apply_item_catalog_filters` R7, R12) can be inserted directly — see Fixture notes.

## Not specified
- Inherited `BaseDAO` methods (`get`, `get_multi`, `create`, `update`, `remove`, `get_by_workspace`, `get_by_id_and_workspace`) — not overridden here; specified with `app/dao/base.py` (7 callables)
- `ItemDAO.search_by_name_in_workspace` — dead code, to be removed (reviewer)
- `ItemDAO.get_active_items_in_workspace` — dead code, to be removed (reviewer)
- `item_dao` — module-level singleton `ItemDAO(Item)`, no logic
- (`get_by_sku_in_workspace` listed in the checklist has been deleted as dead code and no longer exists)

---

## `_apply_item_catalog_filters(query, *, workspace_id, search=None, unit=None, tag_ids=None)`
**Shape:** helper
**Persistence:** pure (builds a query; executes nothing)
**Visibility:** internal (used by: `list_active_items_filtered`, `count_active_items_filtered`)

**Purpose:** Apply the item catalog's filters — workspace, active only, unit, tags, free-text search — to a query over items.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| query | Query | A query selecting from `items` (whole `Item` or `Item.id`); must be bound to a session |
| workspace_id | int | Workspace to restrict to |
| search | str \| None | Free text; `None`, `""` and whitespace-only mean "no search"; otherwise trimmed of leading/trailing whitespace |
| unit | str \| None | Unit; `None` and `""` mean "no unit filter"; compared case-insensitively (BUG-017) |
| tag_ids | list[int] \| None | Any-of tag filter; `None` and `[]` mean "no tag filter" |

**Returns:** The filtered query (not executed). Outcomes below are what executing it yields, via the two public callers.

**Rules:**
- **R1.** Only items of `workspace_id` are matched; an item in another workspace is never matched, whatever the other filters (including a search equal to its id).
- **R2.** Only items with `is_active = True` are matched; soft-deleted items (`is_active = False`) are never matched.
- **R3.** With no `search`, `unit` or `tag_ids`, every active item of the workspace is matched.
- **R4.** [BUG-017] Given a non-empty `unit`, only items whose stored `unit`, trimmed, equals the trimmed `unit` value case-insensitively are matched (`unit="kg"` matches items with `"kg"`, `"Kg"`, `"KG"` and legacy untrimmed `"kg "` / `" KG"`; it does not match `"kgs"`). `unit=""` applies no unit filter. `unit="kg "` behaves like `unit="kg"`, and a whitespace-only `unit` applies no unit filter. *(Today: exact, case-sensitive match with no trimming on either side — `"kg"` does not match stored `"KG"` or `"kg "`; a whitespace-only `unit` matches only items with that exact unit.)* Storing units trimmed is a separate fix in the item create/update path (schema/manager), not in this DAO.
- **R5.** Given a non-empty `tag_ids`, only items having at least one assignment (in this workspace) to any of those tag ids are matched. `tag_ids=[]` applies no tag filter.
- **R6.** [BUG-014] An assignment to a deleted tag (`is_active = False`) does not make the item match the tag filter: filtering only by a deleted tag's id matches no items through that tag; an item carrying both a deleted requested tag and an active requested tag still matches through the active one. *(Today: the tag's `is_active` is ignored and items assigned to a deleted tag still match.)*
- **R7.** Tag ids assigned only in another workspace do not match (the assignment's `workspace_id` must equal `workspace_id`); an unknown tag id matches nothing, so the result is empty when it is the only id given.
- **R8.** An item carrying several of the requested tags can appear more than once in the raw query result; the two public callers de-duplicate (see their rules).
- **R9.** [BUG-013] Given a search with non-whitespace content, the trimmed text is matched case-insensitively as a literal substring of the item's `name`, `description`, `sku` or `unit`; an item matches if any one of them contains it. `%` and `_` in the text are matched literally, not as wildcards: `AB_12` matches SKU `"AB_12"` but not `"ABX12"`; `50%` matches only text containing `"50%"`; a search of just `_` or `%` matches only items containing that character. Per HR-8, a backslash `\` is matched literally too: `a\b` matches text containing `"a\b"` and not `"ab"`; `\` alone matches only items containing a backslash; a search ending in `\` (e.g. `abc\`) matches text containing `"abc\"` anywhere and never raises. Inner whitespace is kept as typed. *(Today: `%` and `_` are not escaped and act as SQL wildcards — `_` alone or `%` alone matches every item; `\` is `ILIKE`'s default escape character, so `a\b` matches `"ab"` but not `"a\b"`, `\` alone matches only text ending in `%`, and `abc\` matches only text ending in `"abc%"`.)* The backslash part is the same fix as BUG-013 (HR-8).
- **R10.** Items whose `description` or `sku` is `NULL` can still match through the other fields.
- **R11.** [BUG-012] If the trimmed search text consists only of ASCII digits `0-9`, an item whose `id` equals that number also matches (e.g. `"12"` matches item 12 even if "12" appears in none of its text fields). Any other digit characters (superscripts `"²"`, `"2²"`, Arabic-Indic `"١٢"`, …) never raise and never match by id — they are searched as text only. `"12a"` does not match by id; `" 12 "` (trimmed to `"12"`) does. *(Today: any Unicode digit string adds the id match — `"١٢"` matches id 12 — and a digit string `int()` cannot convert, such as `"²"`, raises `ValueError`.)*
- **R12.** [BUG-015] An item also matches the search if it has an assignment (in this workspace) to an active tag (`is_active = True`) whose `name` contains the text case-insensitively (literal match per R9 [BUG-013], including `%`, `_` and `\` — HR-8); deleted tags are ignored. *(Today: deleted tags' names also match.)*
- **R13.** `search`, `unit` and `tag_ids` combine with AND; within the search, the alternatives (fields, id, tag name) combine with OR.

**Errors:** none. *(Today: an all-digit search `int()` cannot convert, e.g. `"²"`, raises `ValueError: invalid literal for int() with base 10: '²'` — BUG-012.)*

**Side effects:** none

---

## `ItemDAO.list_active_items_filtered(db, *, workspace_id, skip=0, limit=100, search=None, unit=None, tag_ids=None)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ItemManager.list_items_filtered` ← `ItemService.get_items_page` ← `GET /items/`; endpoint enforces `skip >= 0`, `limit <= 100`, no minimum on `limit` today — see R7)

**Purpose:** One page of the item catalog, with the catalog filters applied.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| db | Session | Open session |
| workspace_id | int | Workspace |
| skip | int | Rows to skip, default `0` |
| limit | int | Max rows, default `100` |
| search, unit, tag_ids | — | As in `_apply_item_catalog_filters` |

**Returns:** List of `Item`, each at most once, ordered by `name` case-insensitive ascending, then `id` ascending (HR-6, BUG-033; today `id` ascending).

**Rules:**
- **R1.** Returns exactly the items matched by `_apply_item_catalog_filters` (R1–R13) for the given filters, paged.
- **R2.** Each item appears at most once, even when it carries several of the requested `tag_ids` or matches the search through several tags.
- **R3.** [BUG-033] Results are ordered by `name` case-insensitive ascending, then `id` ascending (e.g. items inserted as "Zulu", "Mike", "alpha" come back "alpha", "Mike", "Zulu"; two items both named "Bolt"/"bolt" come back lower id first); `skip`/`limit` are applied after filtering, de-duplication and ordering, so consecutive windows partition the matching set with no repeats or gaps. *(Today: ordered by `id` ascending only.)*
- **R4.** [BUG-033] With defaults, at most the first 100 matching items in R3's order. *(Today: the 100 lowest ids.)*
- **R5.** Called directly, `limit=0` returns `[]`, and a negative `limit` or `skip` makes Postgres reject the query with `sqlalchemy.exc.DataError` (see Errors). Nothing is changed in the database. (The API is intended never to send these — see R7.)
- **R6.** [BUG-012] No search text raises; unconvertible digit characters are searched as text (see `_apply_item_catalog_filters` R11). *(Today: e.g. `"²"` raises `ValueError`.)*
- **R7.** [BUG-016] `GET /items/` rejects `limit < 1` (`0`, `-1`) with 422 before this DAO is reached; the fix belongs in the endpoint's `limit` query parameter (`ge=1`). Integration-only. *(Today: `limit=0` returns an empty page with non-zero `total` and `has_more: true`; `limit=-1` returns 500.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Negative `limit` (direct call) | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInLimitClause` (a `psycopg2.DataError`), `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| Negative `skip` (direct call) | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInResultOffsetClause`, `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |

**Side effects:** none

---

## `ItemDAO.count_active_items_filtered(db, *, workspace_id, search=None, unit=None, tag_ids=None)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `ItemManager.count_items_filtered` ← `ItemService.get_items_page` ← `GET /items/`, as `total`)

**Purpose:** Count the items the catalog list would return across all pages for the same filters.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| db | Session | Open session |
| workspace_id | int | Workspace |
| search, unit, tag_ids | — | As in `_apply_item_catalog_filters` |

**Returns:** `int` ≥ 0.

**Rules:**
- **R1.** Returns the number of distinct items matched by `_apply_item_catalog_filters` for the given filters — equal to the length of `list_active_items_filtered` with the same filters and a `limit` large enough to return everything.
- **R2.** An item carrying several requested tags, or matching the search through several tags, is counted once.
- **R3.** Returns `0` (an `int`, not `None`) when nothing matches, including for an empty workspace or an unknown workspace id.
- **R4.** [BUG-012] No search text raises; unconvertible digit characters are searched as text (see `_apply_item_catalog_filters` R11). *(Today: e.g. `"²"` raises `ValueError`.)*

**Errors:** none

**Side effects:** none

---

## `ItemDAO.distinct_units_in_workspace(db, *, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ItemManager.distinct_units` ← `ItemService.get_distinct_units` ← `GET /items/units/`)

**Purpose:** The set of units in use by the workspace's active items, for the catalog's unit filter.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| db | Session | Open session |
| workspace_id | int | Workspace |

**Returns:** `list[str]`, each unit once (lowercase, per BUG-017), sorted.

**Rules:**
- **R1.** Returns each distinct unit used by at least one active item of `workspace_id`, once (distinctness and spelling per R4).
- **R2.** Units used only by soft-deleted items, or only by items of other workspaces, are not returned.
- **R3.** The empty string `""` is never returned. The stored empty unit `""` is not listed (works today).
- **R3a.** [BUG-017] A stored whitespace-only unit (e.g. legacy `" "`) counts as `""` after trimming and is never listed; a workspace whose only units are `""` and `" "` returns `[]`. *(Today: `" "` is returned as its own entry.)*
- **R4.** [BUG-017] Units are grouped on their trimmed, lowercased value: units that differ only in letter case or in leading/trailing whitespace are one entry, and every entry is returned trimmed and in lowercase. Items with `"kg"`, `"Kg"`, `"KG"` and legacy `"kg "` produce the single entry `"kg"`; a workspace whose only unit spelling is `"PCS"` returns `["pcs"]`. *(Today: values are returned exactly as stored — `"kg"`, `"KG"` and `"kg "` are three separate entries, and `"PCS"` is returned as `"PCS"`.)*
- **R5.** Results (the lowercase entries of R4) are sorted ascending, e.g. stored `"PCS"`, `"kg"`, `"Ltr"` → `["kg", "ltr", "pcs"]`. Ordering among entries with non-letter characters is collation-dependent; tests should use plain lowercase-letter units.
- **R6.** No limit: all distinct units are returned. An empty or unknown workspace returns `[]`.

**Errors:** none

**Side effects:** none

---

## `ItemDAO.find_similar_by_name_in_workspace(db, *, workspace_id, name, limit=5, exclude_item_id=None)`
**Shape:** search
**Persistence:** reads
**Visibility:** public (used by: `ItemManager.find_similar_items` ← `ItemService.get_similar_items` ← `GET /items/similar/`; endpoint enforces `name` min length 1 and `1 <= limit <= 10`, and today never passes `exclude_item_id` — see R8)

**Purpose:** Find active items of the workspace whose names look like a proposed name, to warn about duplicates before creating an item.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| db | Session | Open session |
| workspace_id | int | Workspace |
| name | str | Proposed name; normalized before comparison (see Overview) |
| limit | int | Max results, default `5` |
| exclude_item_id | int \| None | Item id to leave out; `None` = exclude nothing |

**Returns:** a plain Python `list` of SQLAlchemy `sqlalchemy.engine.Row` objects (annotated `list[tuple[Item, float]]`, but the rows are **not** `tuple` instances — `isinstance(row, tuple)` is `False`). Each row is tuple-like, of length 2: `row[0]` is the `Item` and `row[1]` is its similarity score as a Python `float` (0.0–1.0) between the item's stored `name_normalized` and the normalized `name`; it unpacks as `item, score = row`. Highest score first. See R10.

**Rules:**
- **R1.** If the normalized `name` is shorter than 3 characters, returns `[]` without consulting the database. Boundary: normalized length exactly 3 (e.g. `"a b"`, `"22 m"` → `"22m"`) proceeds; `"ab"`, `"  AB  "`, `""`, `"!!!"` (normalizes to `""`) return `[]`.
- **R2.** Compares against each item's stored `name_normalized` column, not its `name` (an item whose `name_normalized` is stale or differs from the normalized `name` is judged by `name_normalized`).
- **R3.** An active item whose `name_normalized` equals the normalized `name` exactly is always returned, whatever its score.
- **R4.** Otherwise an active item is returned only if its trigram similarity score (Postgres `pg_trgm` `similarity()`) to the normalized `name` is ≥ 0.35; items below 0.35 without an exact normalized match are not returned (e.g. 7/19 ≈ 0.3684 included, 7/21 ≈ 0.3333 excluded).
- **R4a.** [BUG-034] A score of exactly 0.35 is included: the threshold is compared in the score's own `real` precision, so an item scoring 7/20 (stored normalized `"abcdefghijklmnopqr"`, proposed `"abcdefg"`) is returned, with score ≈ 0.35 (`0.3499999940395355` as a Python float). *(Today: the `real` score 0.3499999940… is compared against 0.35 in double precision and the item is excluded.)*
- **R5.** Spacing, case and punctuation variants that normalize identically are exact matches (e.g. proposed `"Steel Rod 22 m"` matches stored `name_normalized = "steel rod 22m"`, score 1.0).
- **R6.** Only active items of `workspace_id` are considered; items of other workspaces and soft-deleted items are never returned, even with an identical normalized name.
- **R7.** At most `limit` rows are returned. `limit=0` returns `[]`; a negative `limit` makes Postgres reject the query with `sqlalchemy.exc.DataError` (see Errors).
- **R8.** [BUG-011] Given `exclude_item_id`, that item is never returned, even as an exact match; an id that doesn't exist or isn't a candidate has no effect. `exclude_item_id=None` excludes nothing. (Note `exclude_item_id=0` is honoured — it is compared against `None`, not truthiness — but excludes nothing since ids start at 1.) The DAO already behaves this way; the bug is that `GET /items/similar/` must accept an `exclude_item_id` query parameter and pass it through to the service (fix in the endpoint; integration-only). *(Today: the endpoint never passes it, so API callers cannot exclude an item.)*
- **R9.** [BUG-018] Rows are ordered by score, highest first; equal scores are ordered by `name` case-insensitive ascending, then `id` ascending. This order is applied before the `limit` cut, so which rows survive the cut is deterministic (e.g. 7 items tied at 1.0 with `limit=5` → the 5 first by name, then id). *(Today: no tie-breaker; among equal scores the order and the rows surviving the `limit` cut are undefined.)*
- **R10.** The result is a `list`. Each element is a SQLAlchemy `Row` (`sqlalchemy.engine.Row`), not a `tuple` (`isinstance(row, tuple)` is `False`): it has `len(row) == 2`, supports indexing (`row[0]` is the `Item` instance, `row[1]` is the score as a `float`) and unpacking (`item, score = row`). Callers rely only on these tuple-like properties; tests should assert them rather than `isinstance(row, tuple)`. The short-name early return (R1) is an empty `list` `[]`.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Negative `limit` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInLimitClause`, `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 27–30 | Always filter workspace + `is_active` | `_apply_item_catalog_filters` R1, R2, R3 |
| 32 | `if unit:` truthy vs `None`/`""` | `_apply_item_catalog_filters` R4 |
| 33 | exact `==` on unit (case/whitespace-sensitive) | `_apply_item_catalog_filters` R4; `distinct_units_in_workspace` R4 |
| 35 | `if tag_ids:` non-empty vs `None`/`[]` | `_apply_item_catalog_filters` R5 |
| 36–42 | join assignments; assignment workspace; tag id in list; no tag `is_active` check; multi-tag duplicates | `_apply_item_catalog_filters` R5, R6, R7, R8 |
| 44 | `if search and search.strip():` — `None`/`""`/whitespace skip | `_apply_item_catalog_filters` R3, R9 |
| 45–51 | trimmed term, ILIKE on name/description/sku/unit, unescaped wildcards and backslash (default escape char), NULL fields | `_apply_item_catalog_filters` R9, R10 |
| 52 | `if term.isdigit():` — id clause added / not | `_apply_item_catalog_filters` R11 |
| 53 | `int(term)` raises for non-ASCII-convertible digits | `_apply_item_catalog_filters` R11, Errors |
| 56–64 | tag-name subquery, assignment workspace, no tag `is_active` check | `_apply_item_catalog_filters` R12 |
| 65 | OR of alternatives; AND with other filters | `_apply_item_catalog_filters` R13 |
| 133–136 | defaults `skip=0`, `limit=100`, filters `None` | `list_active_items_filtered` R4, R1 |
| 146 | `DISTINCT ON (id)` + `ORDER BY id` (not HR-6 order) then offset/limit; limit 0 / negative | `list_active_items_filtered` R2, R3, R4, R5 |
| 165–166 | `.distinct()` on ids before counting | `count_active_items_filtered` R2 |
| 168 | `scalar() or 0` | `count_active_items_filtered` R3 |
| 173–179 | workspace + active, distinct (exact, case-sensitive), ORDER BY unit, no limit | `distinct_units_in_workspace` R1, R2, R4, R5, R6 |
| 181 | `if row[0]` drops `""` (whitespace kept) | `distinct_units_in_workspace` R3, R3a |
| 189–190 | defaults `limit=5`, `exclude_item_id=None` | `find_similar_by_name_in_workspace` R7, R8 |
| 197 (+ `normalize_item_name` L20 `if not name`) | normalization; empty name → `""` | `find_similar_by_name_in_workspace` R1, R5 |
| 198 | `len(normalized) < 3` → `[]` | `find_similar_by_name_in_workspace` R1 |
| 201 | score on stored `name_normalized` | `find_similar_by_name_in_workspace` R2 |
| 206–207 | workspace + active | `find_similar_by_name_in_workspace` R6 |
| 208–211 | exact normalized match OR score ≥ 0.35 (`real` score vs double-precision threshold) | `find_similar_by_name_in_workspace` R3, R4, R4a |
| 215 | `if exclude_item_id is not None` | `find_similar_by_name_in_workspace` R8 |
| 219–220 | ORDER BY score desc (no tie-breaker), LIMIT; `.all()` returns `Row` objects | `find_similar_by_name_in_workspace` R7, R9, R10 |

## Gap log
- G1 (item.cases.md gap 1) — Fact — Fixture notes: no constraint/trigger ties an assignment's `workspace_id` to its item's or tag's workspace (only PK, `uq_item_tag`, FKs); cross-workspace assignment rows can be inserted. Test-designer note added.
- G2 (item.cases.md gap 2) — Intent — Overview gains "Similarity score facts" (`similarity()` is `real`; comparison runs in double precision; 7/20 is excluded today); R4 gets a pending note; new question Q13 (suggested: include, compare in `real`).
- G3 (item.cases.md gap 3) — Fact — Errors tables of `list_active_items_filtered` and `find_similar_by_name_in_workspace` now name `sqlalchemy.exc.DataError` with `.orig` class and SQLSTATE (`2201W` LIMIT, `2201X` OFFSET); R5/R7 point to them; savepoint note added.
- G4 (item.cases.md gap 4) — House rule not applied — HR-8: `_apply_item_catalog_filters` R9/R12 now state backslash is matched literally (with today's escape-character behavior); violation line added, to be logged against BUG-013 (same fix).
- G5 (item.cases.md gap 5) — House rule not applied — HR-6: `list_active_items_filtered` R3/R4/Returns rewritten to name case-insensitive, then `id` order (today `id` only); violation line added (reviewer may override if id order is deliberate); new bug on apply.
- G6 (item.cases.md gap 6) — Intent — new question Q14 on legacy untrimmed stored units (suggested: DAO filters/groups on trimmed lowercased unit); pointers added to `_apply_item_catalog_filters` R4 and `distinct_units_in_workspace` R3.
- G7 (item.verify.md finding 4) — Fact — `find_similar_by_name_in_workspace` Returns line rewritten and new R10 added: result is a `list` of SQLAlchemy `sqlalchemy.engine.Row` objects, not `tuple` instances (`isinstance(row, tuple)` is `False`); each row has length 2, `row[0]` is the `Item`, `row[1]` the score as a `float`, and unpacks as `item, score`; early return is `[]`. Branch map row 219–220 points to R10. (Findings 1–3 are routed to the case designer — not handled here.)
