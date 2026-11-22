# Spec — `app/services/item_service.py`

> **Status:** APPROVED (2026-11-04; nothing open). Stays APPROVED after fill-gaps (Gap log at the end; decided by Claude under the reviewer's delegation (2026-11-04)).
> **Source commit:** e48a092
> **Revision (2026-11-04):** fill-gaps from `item_service.verify.md` Finding 3 (surviving mutant `limit` 5 → 6): new rule `get_similar_items` R1a (default `limit`). No existing rule changed.

> **Form.** As `tests/unit/services/department_service.spec.md`: this spec covers only what the service adds. The **Transaction contract TC1–TC6 is defined there** and cited here, not restated. Below the service: `tests/unit/managers/item_manager.spec.md` (APPROVED), `tests/unit/dao/item.spec.md`, `tests/unit/dao/item_tag_assignment.spec.md`, `tests/unit/dao/base.spec.md`.

> **Routed here and written as rules:** item manager FU-1 in full: the translation of every manager `ValueError` (BUG-940 not found / already deleted, BUG-944 unknown tag, BUG-943 deleted tag, BUG-946 SKU taken, BUG-948 item in use with its blockers in the 400 body); `include_deleted` on `GET /items/{id}/` (BUG-937); the dead branch `if not item` in `update_item` (D3, `remove`); the docstring "ConflictError: if item with same name/SKU exists" (names are not unique, item manager Q1; SKU is BUG-946); `limit` lower bound (BUG-016) and `exclude_item_id` (BUG-011) cited. No new ID for any of them; the register rows of BUG-937, BUG-940, BUG-948 name this service.
>
> **Decided by Claude under the reviewer's delegation (2026-11-04):** Q1 (BUG-1573), D1 (error classes and texts), D2 (blockers pass through without display fields), D3 (`remove` the dead branch), D4 (default `limit` of `get_similar_items` as a rule, fill-gaps). None is the owner's answer. D2 touches what a refused delete shows, but not who may see or do what: the owner's rule (a refused delete lists what blocks it) is kept as the manager builds the list; only optional extra fields are left out.
>
> **Standing decisions applied here (not asked again):** HR-4. For items "deleted" is `is_active = False` (item manager standing decision 1). A refused delete lists what blocks it (owner, item manager Q2). The service raises the application's RFC 7807 errors (`app.core.exceptions`), as `get_item` and `delete_item` already do today.
>
> **Verified by running** (`h.py`, `v3_item.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2\`, one outer transaction rolled back against `marker_test`, session as the `db` fixture; HTTP through `TestClient` with overridden dependencies; nothing persisted): create commits and re-reads; the list page with a `service` item shows **`item_type: "physical"`** (service and HTTP) while `GET /items/{id}/` shows `"service"`; tag dicts carry `id`, `name`, `tag_code`, `color`, `icon`, `is_system_tag`; `total`, `has_more` with `limit=1`, `limit=0` (`has_more: true`, HTTP 200), `skip` past the end; units; similar names echo the query untrimmed and normalise it (`"  BOLT "` → `bolt`; `"!!"` → `""`, no matches); `update_item` of a missing id and of another workspace's item raise `ValueError` (`Item <id> not found`, `Item <id> does not belong to workspace <ws>`), **500** over HTTP; `delete_item` of a missing or another workspace's id raises `NotFoundError` 404 `Item with ID <id> not found` (RFC 7807 body); delete returns `None` and is committed; a second delete raises `ValueError` `Item <id> is already deleted`, **500** over HTTP; a deleted item is returned by `get_item` (HTTP 200); `include_deleted=` raises `TypeError`; a deleted item can be updated; an unknown tag id on create is skipped; a patched in-use `ValueError` on delete answers **500**. **Not run:** two concurrent requests; the intended behavior of the bug rules.

## Review
> All answered; nothing pending.

### Q1. The catalog list shows every item as "physical" — 🐞 BUG-1573 (decided by Claude under the reviewer's delegation (2026-11-04))
**Background:** Items have an `item_type`, `physical` or `service` (item manager R2). `GET /items/` builds each row by hand and leaves `item_type` out; the response schema then fills its default, `"physical"`.
**What happens today:** A service item ("Repair", `item_type = "service"`) is listed as `"physical"`; `GET /items/{id}/` shows `"service"` (verified).
**Example:** The catalog lists "Machine calibration" (a service) as physical; a screen that hides stock columns for services shows them for it.
**Rules affected:** `get_items_page` R3
**Suggested answer:** `bug — each listed item carries its stored item_type`. Alternative: `intended` (the list never shows the type) — but then the field should not be in the list's schema at all.
**Answer:** bug — as suggested.
**Resolution:** 🐞 BUG-1573 (pattern `response-field-defaulted`). Rules: `get_items_page` R3.

### D1. Which error each manager refusal becomes — decided by Claude under the reviewer's delegation (2026-11-04)
**Background:** The manager reports every refusal as a plain `ValueError`; the application has no handler for it, so each is a 500 today. The statuses were decided in the manager review (FU-1); the error classes and texts were left here.
**Answer:** the service raises the application's errors from `app.core.exceptions`, as `get_item` already does: `NotFoundError` (404), `ValidationError` (400), `ConflictError` (409). Texts: a not-found item reads `Item with ID <id> not found`, the same as `get_item` and the delete pre-check; every other text is the manager's message verbatim. Only the manager's known messages are translated; any other `ValueError` stays as it is (a 500), so a programming error is not dressed up as a user error (`machine_item_service.spec.md` Q1). Rules: `create_item` R2, `update_item` R2, `delete_item` R3, R4.

### D2. Blockers carry no display fields — decided by Claude under the reviewer's delegation (2026-11-04)
**Background:** Item manager FU-1 allowed the service to add display fields (factory name and quantity, order number, stage) to each blocker.
**Answer:** not added. The `errors` list is the manager's, unchanged (`type`, `id`; `{"type": "other_workspace"}` alone). Adding fields would mean a second set of reads per blocker type and a new place where another workspace's data could leak (HR-16); the frontend note BUG-949 can show the type and id, and link to them. Revisit if the frontend asks. Rules: `delete_item` R4.

### D3. `update_item`'s "item not found" check can never fire — remove (decided by Claude under the reviewer's delegation (2026-11-04))
**Background:** After the manager's `update_item`, the service checks `if not item: raise NotFoundError`. The manager either raises or returns the item it loaded (item manager `update_item` Returns), so the check is never true, and its own `except NotFoundError` clause only catches that raise.
**Answer:** remove — logged in `docs/testing/dead-code-removal-checklist.md`. Not a bug, no ID. Not specified, not tested.

### D4. The default number of similar items is a rule — decided by Claude under the reviewer's delegation (2026-11-04)
**Background:** `get_similar_items` has its own default `limit=5`. `GET /items/similar/` always passes `limit` (`Query(5)`), so the default is reached only by direct callers; the verifier found no rule for it (`item_service.verify.md` Finding 3).
**Answer:** written as a rule, following the `app_settings_service` precedent (default limit as a rule, card ASV-L-09): a caller who omits `limit` gets at most 5 matches, the first 5 of the manager's order. Read from the source (line 203); not a bug, no ID. Rules: `get_similar_items` R1a.

Existing bugs written as rules here, no new ID: **BUG-937** `get_item` R2, R3, `delete_item` R2; **BUG-940** `update_item` R2, `delete_item` R3; **BUG-941** (texts reach the caller through D1); **BUG-943**, **BUG-944**, **BUG-946** `create_item` R2, `update_item` R2; **BUG-948** `delete_item` R4. Reached through the manager and DAOs and cited, one pass-through case each, strict or non-strict exactly as in `item_manager.cases.md`: BUG-011 … BUG-018, BUG-033, BUG-034, BUG-931 … BUG-936, BUG-938, BUG-939, BUG-942, BUG-945, BUG-947. BUG-949 is the frontend's.

Checked and **not** violated: **HR-1 … HR-3** — the manager's and the schemas' (BUG-936, BUG-017). **HR-5, HR-6, HR-8** — the item DAO's (BUG-013, BUG-018, BUG-033). **HR-7** — `GET /items/` has no lower bound on `limit`: BUG-016 (cited). **HR-9** — BUG-939 (manager). **HR-10** — no lock needed (item manager). **HR-16** — every read is by the caller's workspace; the 400's blockers are the manager's, with one generic entry for another workspace.

**Permission checks:** none; any active member may create, edit and delete items (as `department_service.spec.md`).

## Overview
`ItemService` is the transaction boundary for the item catalog. The `/items/` endpoints call it; it calls `ItemManager`, commits and rolls back, and shapes two answers itself: the catalog page (items with their tags, a total and "has more"), and the similar-name check. Intended (BUG-940, BUG-943, BUG-944, BUG-946, BUG-948), it also turns the manager's `ValueError`s into the application's 404 / 400 / 409, the in-use refusal carrying its blocker list.

**Callables:** 7 specified · 3 not specified (plus one dead branch)
**Externals to mock:** none.
**Integration-only behavior:** as `department_service.spec.md`; the RFC 7807 body of `app.core.exceptions` errors (`tests/unit/core/exceptions.spec.md`); the `include_deleted` query parameter on `GET /items/{id}/`; `GET /items/` `limit <= 100` (no lower bound, BUG-016), `skip >= 0`; `GET /items/similar/` `name` min length 1, `1 <= limit <= 10`, no `exclude_item_id` (BUG-011); `DELETE` answers 204.

**Facts for the test designer**
- Import: `from app.services.item_service import ItemService, item_service`. `ItemService()` takes no arguments; its manager is the attribute `item_manager` (singleton of `app.managers.item_manager`). Parameters are positional-or-keyword; the endpoints pass `get_item`, `create_item`, `update_item`, `delete_item` arguments positionally (workspace as keyword on `get_item`) and the rest by keyword.
- Errors: `from app.core.exceptions import NotFoundError, ValidationError, ConflictError`; assert `.status_code`, `.detail`, and `.errors` for the in-use refusal.
- `ItemListResponse` = `items` (`ItemWithTagsResponse`), `total`, `skip`, `limit`, `has_more`. `ItemWithTagsResponse` inherits `ItemBase`, so `item_type` defaults to `"physical"` when not given. `SimilarItemsResponse` = `query`, `normalized_query`, `matches` (`SimilarItemMatch`).

**Notes for the test designer**
- Transaction mechanics (TC1–TC6): exactly as `department_service.spec.md` Notes.
- **Translation cases (D1):** the manager raises none of the tag / SKU / in-use errors today, so cases with real rows are strict xfail by those bugs. To isolate the translation, also patch `item_service.item_manager.<method>` with `side_effect=ValueError(<the manager's text>)` (and the two-arg form for the in-use refusal): today the `ValueError` comes out unchanged → strict xfail by the bug of that message. One case with a `ValueError("something else")` that must come out unchanged passes today.
- **BUG-937:** `include_deleted=` raises `TypeError` today → strict xfail.
- **BUG-1573:** create an item with `item_type="service"` and read it through `get_items_page` → strict xfail.
- **Pass-through cases:** one per bug reached, as the manager's cases file marks them.

## Not specified
- `ItemService.__init__` — stores the manager, no logic.
- `item_service` — module-level singleton, no logic.
- `ItemService.get_items` — dead code, already on `docs/testing/dead-code-removal-checklist.md` (item DAO spec Q4); it calls the dead `ItemManager.search_items`.
- The `if not item:` branch of `update_item` and its `except NotFoundError` clause — dead code (D3).

---

## `ItemService.create_item(db, item_in, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `POST /items/`, 201)

**Purpose:** Create a catalog item with its tags and save it.

**Returns:** the new `Item`, committed and re-read (TC1, TC2). Verified.

**Rules:**
- **R1.** The item is created exactly as `ItemManager.create_item` creates it (manager spec R1–R11: tags and counters, BUG-017, BUG-931, BUG-936, BUG-943, BUG-944, BUG-946); everything it flushed is committed.
- **R2.** (D1) A manager refusal is rolled back (TC3) and translated: [BUG-944] `Item tag <id> not found` → `NotFoundError`, 404, same text; [BUG-943] `Item tag <id> is not active` → `ValidationError`, 400, same text; [BUG-946] `Item with SKU '<sku>' already exists` → `ConflictError`, 409, same text. *(Today: the manager raises none of them: unknown tags are skipped, verified; and the service translates nothing.)*
- **R3.** Any other exception reaches the caller unchanged after the rollback, including a `ValueError` with another text; commit and re-read failures follow TC4, TC5.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| [BUG-944] unknown tag | `NotFoundError` (404) | `Item tag <id> not found` |
| [BUG-943] deleted tag | `ValidationError` (400) | `Item tag <id> is not active` |
| [BUG-946] SKU taken | `ConflictError` (409) | `Item with SKU '<sku>' already exists` |
| database error | the same `sqlalchemy.exc` error | — |

**Side effects:** the item, its links and counters, committed. On any error: rolled back.

---

## `ItemService.get_item(db, item_id, workspace_id, include_deleted=False)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `GET /items/{id}/`)

**Purpose:** One item by id.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `include_deleted` | bool, default `False` | [BUG-937] new; passed to the manager; reachable from the API |

**Returns:** the `Item`.

**Rules:**
- **R1.** The manager's `get_item` result is returned when it is an item; when it is `None` (unknown id, `0`, another workspace's item) the service raises `NotFoundError` 404 `Item with ID <item_id> not found`. Verified.
- **R2.** [BUG-937] (HR-4) A deleted item (`is_active = False`) → the same 404 by default. *(Today: returned, HTTP 200. Verified.)*
- **R3.** [BUG-937] With `include_deleted=True` a deleted item of the workspace is returned; another workspace's is still 404. *(Today: `TypeError`. Verified.)*
- **R4.** Read only (TC6).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / other workspace; [BUG-937] deleted | `NotFoundError` (404) | `Item with ID <item_id> not found` |

**Side effects:** none

---

## `ItemService.get_items_page(db, workspace_id, search=None, skip=0, limit=100, unit=None, tag_ids=None)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `GET /items/`)

**Purpose:** One page of the catalog with each item's tags and the total.

**Returns:** an `ItemListResponse`.

**Rules:**
- **R1.** `items` are, in order, `ItemManager.list_items_filtered(workspace_id, skip, limit, search, unit, tag_ids)` (manager R1: live items only, the DAO's filters, order and bugs); `total` is `count_items_filtered` with the same `search`, `unit`, `tag_ids` (manager R1). `skip` and `limit` in the answer are the arguments as given.
- **R2.** Each item's `tags` are the manager's `get_tags_for_items` for the page's ids (assignment DAO `get_tags_for_items`: active tags only, BUG-932 / BUG-933 order), each as a dict with exactly `id`, `name`, `tag_code`, `color`, `icon`, `is_system_tag` (verified); an item without tags has `[]`.
- **R3.** Each item carries `id`, `workspace_id`, `name`, `description`, `unit`, `sku`, `is_active`, `created_at`, `updated_at`, `created_by`, `updated_by` from the row, and [BUG-1573] (Q1) its stored `item_type`. *(Today: `item_type` is left out and reads `"physical"` for every item, a `service` item included. Verified.)*
- **R4.** `has_more` is `skip + (number of items on the page) < total`: 2 items, `limit=1` → `True`; `skip` past the end → `False`, `items` `[]`. With `limit=0` the page is empty and `has_more` is `True` whenever `total > 0` (verified; the API allows it today, BUG-016).
- **R5.** Read only (TC6).

**Errors:** as the manager (negative `skip` / `limit` → `DataError` when called directly).

**Side effects:** none

---

## `ItemService.get_distinct_units(db, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `GET /items/units/`)

**Rules:**
- **R1.** Returns `ItemManager.distinct_units(db, workspace_id)` unchanged (manager R1, BUG-017). Read only.

**Errors:** none. **Side effects:** none

---

## `ItemService.get_similar_items(db, workspace_id, name, limit=5, exclude_item_id=None)`
**Shape:** search
**Persistence:** reads
**Visibility:** public (used by: `GET /items/similar/`, which never passes `exclude_item_id`, BUG-011)

**Purpose:** The duplicate warning before creating an item.

**Returns:** a `SimilarItemsResponse`.

**Rules:**
- **R1.** `matches` are `ItemManager.find_similar_items` for these arguments, unchanged and in its order (manager R1–R5).
- **R1a.** (D4) A caller who omits `limit` gets at most **5** matches: with 6 live items of the workspace that all match the name (e.g. 6 items whose normalized name equals the query's) and no `limit` given, exactly 5 come back, the first 5 of the manager's order. The service's own default is 5, independent of the manager's.
- **R2.** `query` is `name` exactly as given, untrimmed (`"  BOLT "` stays `"  BOLT "`); `normalized_query` is `normalize_item_name(name)` (`"  BOLT "` → `"bolt"`, `"!!"` → `""`). Verified.
- **R3.** Read only.

**Errors:** as the manager (negative `limit` → `DataError` when called directly).

**Side effects:** none

---

## `ItemService.update_item(db, item_id, item_in, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `PUT /items/{id}/`)

**Purpose:** Edit an item and its tags and save it.

**Returns:** the `Item`, committed and re-read (TC1, TC2).

**Rules:**
- **R1.** The item is changed exactly as `ItemManager.update_item` changes it (manager spec R1–R20); everything it flushed is committed.
- **R2.** (D1) A manager refusal is rolled back (TC3) and translated: [BUG-940] `Item <item_id> not found` (missing; [BUG-941] another workspace; [BUG-938] deleted) → `NotFoundError` 404 `Item with ID <item_id> not found`; [BUG-944] → 404, [BUG-943] → 400, [BUG-946] → 409, texts as `create_item` R2. *(Today: every one is a plain `ValueError`, a 500 over HTTP; another workspace's item gives `Item <id> does not belong to workspace <ws>`, and a deleted item is updated. Verified.)*
- **R3.** Any other exception reaches the caller unchanged after the rollback; commit and re-read failures follow TC4, TC5.

**Errors:** as `create_item` plus not found (R2).

**Side effects:** the manager's writes, committed. On any error: rolled back.

---

## `ItemService.delete_item(db, item_id, workspace_id, user_id)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `DELETE /items/{id}/`, 204)

**Purpose:** Soft-delete an item and save it, or tell the user what stops it.

**Returns:** `None`. Nothing is re-read.

**Rules:**
- **R1.** First the item is looked up with the manager's `get_item` (default arguments). `None` (unknown id, `0`, another workspace's item) → the session is rolled back and `NotFoundError` 404 `Item with ID <item_id> not found` is raised; the manager's `delete_item` is not called (verified for missing and another workspace).
- **R2.** [BUG-937] Once deleted items are hidden by `get_item`, a deleted item gets R1's 404 too. *(Today: a deleted item passes the lookup and reaches the manager: R3.)*
- **R3.** [BUG-940] (D1) The manager's `Item <item_id> is already deleted` (reachable only in a race once BUG-937 is fixed) → `ValidationError` 400 with that text; its `Item <item_id> not found` → R1's 404. *(Today: `ValueError`, a 500 over HTTP on a second delete. Verified.)*
- **R4.** [BUG-948] (D1, D2) The manager's `ValueError("Item has stock or open orders", blockers)` → after the rollback, `ValidationError` with `status_code == 400`, `detail == "Item has stock or open orders"`, `errors` == the blockers unchanged (item manager R9b: each `{"type", "id"}`, at most one `{"type": "other_workspace"}`, last). *(Today: no refusal, and a `ValueError` would be a 500. Verified with a patched manager.)*
- **R5.** Otherwise the soft delete the manager made (manager R4–R13) is committed (verified: `is_active = False` after a later rollback).
- **R6.** Any other exception reaches the caller unchanged after the rollback; a failing commit follows TC4.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / other workspace; [BUG-937] deleted | `NotFoundError` (404) | `Item with ID <item_id> not found` |
| [BUG-940] already deleted (race) | `ValidationError` (400) | `Item <item_id> is already deleted` |
| [BUG-948] in use | `ValidationError` (400) | `Item has stock or open orders`; `.errors` = blockers |

**Side effects:** the item's `is_active`, `updated_by`, `updated_at` and its tags' counters, committed. On any error: rolled back.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| `base_service.py` 26–30 | commit; commit raises → rollback, re-raise | TC1, TC4 |
| `base_service.py` 39 | rollback | TC3 |
| 50–63 | create: manager → commit → refresh → return | `create_item` R1 |
| 65–67 | create: any exception → rollback, re-raise; no translation | `create_item` R2, R3 |
| 89–92 | get: manager positional (no `include_deleted`, BUG-937); `not item` → `NotFoundError` | `get_item` R1–R4 |
| 94–121 | `get_items` → dead `search_items` | Not specified |
| 133–148 | page: list and count with the same filters | `get_items_page` R1 |
| 150–155 | tags for the page's ids | `get_items_page` R2 |
| 157–185 | row dicts, `item_type` left out (BUG-1573); `tags_by_item.get(id, [])` | `get_items_page` R2, R3 |
| 187–193 | response; `has_more = skip + len < total` | `get_items_page` R4 |
| 195–196 | units pass-through | `get_distinct_units` R1 |
| 203 | similar: default `limit=5` | `get_similar_items` R1a |
| 207–218 | similar: manager; `query`, `normalized_query` | `get_similar_items` R1–R3 |
| 244–261 | update: manager → (dead `if not item`, D3) → commit → refresh → return | `update_item` R1 |
| 263–268 | update: `NotFoundError` (dead) / any exception → rollback, re-raise; no translation | `update_item` R2, R3 |
| 289–293 | delete: pre-check `get_item`; `not item` → `NotFoundError` | `delete_item` R1, R2 |
| 296–304 | delete: manager → commit; returns `None` | `delete_item` R5 |
| 306–311 | delete: `NotFoundError` / any exception → rollback, re-raise; no translation | `delete_item` R1, R3, R4, R6 |
| 315 | module singleton | Not specified |

## Gap log
G1 (item_service.verify.md Finding 3) — Fact — the default `limit=5` of `get_similar_items` written as rule R1a (D4, decided by Claude under the reviewer's delegation (2026-11-04), app_settings precedent ASV-L-09); Branch-map row 203 added. No other rule changed.
