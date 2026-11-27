# Spec — `app/services/item_tag_service.py`

> **Status:** APPROVED (2026-11-03; nothing open). Stays APPROVED after fill-gaps (Gap log at the end; decided by Claude under the reviewer's delegation (2026-11-03)).
> **Source commit:** e48a092

> **Form.** As `tests/unit/services/department_service.spec.md`. This service has **no manager** and does **not** inherit `BaseService`: it holds the tag rules itself, calls `item_tag_dao` and `item_tag_assignment_dao` directly, and commits and rolls back itself. Its transaction rules are written out below (S1–S4). Below it: `tests/unit/dao/item_tag.spec.md`, `tests/unit/dao/item_tag_assignment.spec.md` (APPROVED), `tests/unit/dao/base.spec.md`.

> **Routed here and written as rules:** item tag DAO FU-1 (a) BUG-1527, (b) BUG-1528, (c) BUG-1526 and Q1, (d) Q2 and Q3, (e) Q4, (f) BUG-1529, (g) `get_system_tags` is reachable, not dead code; item tag assignment DAO FU-2 (`get_tags` R2).
>
> **Review round 2026-11-03.** **Decided by Claude under the reviewer's delegation (2026-11-03):** P1, Q1, Q2, Q3, Q4. None is the owner's own answer; none touches money, stock, an order workflow, or who may see or do what. House-rule lines: BUG-1526 … BUG-1529. New bugs: BUG-1526 … BUG-1533.
>
> **Standing decisions applied here (not asked again):** for tags "deleted" is `is_active = False` (item tag DAO standing decision 1); things of a deleted tag are hidden by the tag's state, the links stay (assignment DAO standing decision 2); raw DAO lookups stay raw, and the caller decides what to hide (HR-4 scope). Input limits go on the input schemas, never on a response schema that stored rows must still pass (machine item manager FU-2, BUG-915).
>
> **Verified by running** (`h.py`, `v2_tag.py`, `v3_http.py`, `v5_tag2.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1\`, one outer transaction rolled back against `marker_test`, session as the `db` fixture, HTTP through `TestClient` with overridden dependencies; nothing persisted): every "Today:" note below. Derived codes: `"Café"` → `café`, `"!!!"` → `""`, `" Bolt "` → `_bolt_`, `"Steel Bar"` → `steel_bar`, `"Steel-Bar"` → `steelbar`, `"কাঁচামাল"` → `কচমল`, `"   "` → `___`, 60 letters → 60 characters; `ItemTagResponse` refuses `café`, `""`, the Bengali code and the 60-character code; over HTTP `POST {"name": "Café"}` answers **500 with the row saved**, and from then on `GET /item-tags/` answers **500** for the whole workspace while `GET /item-tags/system/` still answers 200. `"???"` after `"!!!"` → 409 `Tag with code '' already exists`; an explicit code taken → 409; `"Paint"` twice and `"PAINT"` with other codes → stored; rename to another tag's name → accepted; rename to `"  "` → stored; `color: null`, `description: null` → unchanged; the same code in another workspace → stored; a deleted tag's code → 409; a deleted tag edited (200), deleted again (`None`), restored by `PUT {"is_active": true}`; `PUT {"is_active": false}` hides a live tag; another workspace's id or `0` → 404 `Tag not found`; a system tag → 403 on update and delete; `get_tags` replaces the counter with the live count (stored 9 → shown 1 for one active and one deleted item; a tag with no links shows 0) and leaves the objects changed in the session, so a later flush in the same session saves the live count; a 409 leaves an uncommitted setup row of the session in place (no rollback). **Not run:** two concurrent creates; the intended behavior of any bug rule.

## Review
> All answered; nothing pending.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | A tag's colour, icon and description cannot be cleared | bug (BUG-1530) | Claude, delegated |
| Q1 | Two live tags can have the same name | bug — names unique per HR-2 (BUG-1531) | Claude, delegated |
| Q2 | A name with accents, Bengali letters, symbols only, or over 50 characters breaks the tag list | bug — derived codes always valid; responses never refuse a stored code (BUG-1532) | Claude, delegated |
| Q3 | Two different names that derive one code: the second is refused with a code the user never typed | bug — a derived code takes the first free `_2`, `_3`… (BUG-1533) | Claude, delegated |
| Q4 | The tag list shows a live usage count; every other answer shows the stored counter | intended | Claude, delegated |

### House-rule violations — applied automatically

- **HR-1** `create_tag` R9, `update_tag` R7 — tag names are stored as typed: `"   "` (code `___`) and `" Bolt "` are accepted on create, `"  "` on rename (verified). Intended: `ItemTagCreate` and `ItemTagUpdate` trim the name and refuse a blank one (422 at the API), nothing written; not on `ItemTagBase`, which `ItemTagResponse` inherits.
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-1526 (pattern `blank-name-accepted`; per BUG-915). Rules: `create_tag` R9, `update_tag` R7.
- **HR-2** `create_tag` R5 — the code check counts deleted tags, so a deleted tag's code can never be used again (verified: 409). Intended: deleted tags (`is_active = False`) do not count; only live tags of the workspace block a code.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-1527 (pattern `uniqueness-check-counts-soft-deleted`; the Python-side twin of BUG-1214). Rules: `create_tag` R5.
- **HR-2** `create_tag` R6 — `item_tags` has no unique index: code uniqueness is checked only in Python, so two creates at once can both pass (item tag DAO FU-1 (b)). Intended: a partial unique index on `(workspace_id, tag_code)` over live tags; a violation reaches the user as 409 `Tag with code '<code>' already exists`, never 500.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-1528 (pattern `python-only-uniqueness`; per BUG-895, BUG-913). Rules: `create_tag` R6.
- **HR-4** `update_tag` R2, `delete_tag` R2 — a deleted tag is found by id like a live one: it can be edited, deleted again (204), and brought back with `PUT {"is_active": true}` (verified). Intended: a deleted tag is treated as not found, 404 `Tag not found`, nothing written (per BUG-863, BUG-938). Bringing a tag back becomes a feature to build, as for departments and machines.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-1529 (pattern `mutation-on-soft-deleted`). Rules: `update_tag` R2, `delete_tag` R2.

Reached through the DAOs and cited, one pass-through case each: **BUG-929** (`get_system_tags` order), **BUG-930** (`get_tags` order). BUG-931 (counter race) is reached through items, not here.

Checked and **not** violated: **HR-3** — the code is not filtered or grouped by the backend; the frontend's tag search lower-cases what it compares. **HR-5, HR-7** — no paging. **HR-8** — no `LIKE`. **HR-9** — `item_tags` has no "last changed by" column. **HR-10** — a tag delete is a plain soft delete. **HR-11 … HR-15** — none applies. **HR-16** — every lookup is by the caller's workspace; another workspace's id is 404, identical to an unknown one (verified).

**Permission checks:** none; any active member may create, edit and delete user tags (as `department_service.spec.md`). System tags are refused to everyone (403), which is the service's only access rule.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation (2026-11-03))

### P1. A tag's colour, icon and description cannot be cleared — 🐞 BUG-1530
**Background:** `PUT /item-tags/{id}/` drops every field sent as `null` (the DAO update applies only fields set to a value). The tag dialog sends `description: description.trim() || null` and `color: color || null`, so emptying a box sends `null`. Same root cause as BUG-942 (item description and SKU) and BUG-1075.
**What happens today:** `{"color": null, "description": null}` answers 200 and both stay (verified).
**Example:** A user clears the description "old supplier" of the tag "Steel" and saves: "Tag updated", and the description is still there.
**Rules affected:** `update_tag` R5
**Answer:** bug — per BUG-942 precedent: explicit `null` clears `color`, `icon`, `description`; `null` for `name` or `is_active` is refused by `ItemTagUpdate` (422); omitted fields stay unchanged
**Resolution:** 🐞 BUG-1530 (pattern `exclude-none-blocks-clear`) — decided by Claude under the reviewer's delegation (2026-11-03). Rules: `update_tag` R5.

### New questions

### Q1. Two live tags can have the same name — 🐞 BUG-1531
**Background:** A tag has a display name and an internal code (`raw_material`). Only the code is checked for duplicates, and only on create. The web app never sends a code: it is derived from the name, and users pick tags by the name on the chip (the tag picker also matches codes and descriptions when searching, but shows names). Codes are read by nothing but the seed of the six system tags. HR-2 says how uniqueness works "where names must be unique"; whether tag names must be is this question (item tag DAO FU-1 (c)).
**What happens today:** `"Paint"` with code `paint1`, `"Paint"` with `paint2` and `"PAINT"` with `paint3` are all stored, and a tag can be renamed to another tag's name (verified). Through the web app, names that derive the same code are refused, so `"Steel Bar"` twice is 409, but `"Steel Bar"` and `"Steel-Bar"` both pass (codes `steel_bar`, `steelbar`).
**Example:** The tag picker shows two "Steel Bar" chips; half the items carry one, half the other, and filtering by either shows only half.
**Rules affected:** `create_tag` R8, `update_tag` R6
**Suggested answer:** `bug — HR-2 applies to tag names: unique among the workspace's live tags (system tags included), case-insensitive after trimming, checked on create and on rename, 409 "Tag with name '<name>' already exists" with the trimmed submitted name; a partial unique index on live tags backs it; a deleted tag's name can be reused.` Existing duplicates must be merged or renamed before the index. Alternative: `intended` — the code is the key, names are labels.
**Answer:** as suggested — decided by Claude under the reviewer's delegation (2026-11-03).
**Resolution:** 🐞 BUG-1531 (pattern `python-only-uniqueness`; per BUG-1225: a name that works as the key gets HR-2). Rules: `create_tag` R8, `update_tag` R6.

### Q2. Some names break the whole tag list — 🐞 BUG-1532
**Background:** When no code is sent (always, from the web app), the code is made from the name: lower-cased, spaces turned into `_`, every other character dropped unless Python counts it as a letter or digit, which includes accented and Bengali letters. Nothing checks the result. The response schema requires codes of 1–50 characters from `a-z`, `0-9`, `_`. A stored row that fails the response schema makes the answer a 500.
**What happens today:** `"Café"` is stored with code `café`; the create answers 500 although the tag is saved, and from then on `GET /item-tags/` answers 500 for the whole workspace. The same for a Bengali name, a name of symbols only (code `""`), and a name over 50 characters. (All verified.)
**Example:** A storekeeper creates the tag "কাঁচামাল" (raw material). The app says "Failed to save tag"; she tries again and gets "Tag with code 'কচমল' already exists"; every screen with the tag picker now fails to load tags.
**Rules affected:** `create_tag` R3; `get_tags` R4
**Suggested answer:** `bug — (a) a derived code always matches ^[a-z0-9_]+$ and has 1–50 characters: from the trimmed name, lower-cased, spaces become "_", every character outside ASCII a-z, 0-9 and "_" is dropped, the result is cut to 50, and if nothing is left the code is "tag"; (b) ItemTagResponse does not apply the input pattern or length to tag_code, so rows already stored are listed again without a repair.` An explicit code keeps the schema's check. Alternative for (b): a one-off script that re-derives the stored codes; it is not needed once (b) holds, and codes are read by nothing.
**Answer:** as suggested — decided by Claude under the reviewer's delegation (2026-11-03).
**Resolution:** 🐞 BUG-1532 (pattern `derived-value-violates-schema`; the response half per BUG-990, `response-schema-narrower-than-stored-values`). Rules: `create_tag` R3, `get_tags` R4.

### Q3. Different names that derive one code are refused — 🐞 BUG-1533
**Background:** As Q2, the web app never sends a code. Once Q2 drops non-ASCII letters, every Bengali name derives `tag`, and names such as "Steel-Bar" and "SteelBar" derive `steelbar`.
**What happens today:** the second create is refused with 409 `Tag with code 'steelbar' already exists` (verified with `steel_bar`), naming a code the user never typed or saw.
**Example:** After "কাঁচামাল" exists, creating "যন্ত্রাংশ" (machine part) is refused with "Tag with code 'tag' already exists".
**Rules affected:** `create_tag` R7
**Suggested answer:** `bug — when the code is derived and a live tag of the workspace already has it, the first free of "<code>_2", "<code>_3", … is used (the base cut so the whole stays within 50 characters); an explicit code that is taken stays 409.` Duplicate **names** are caught first by Q1. Alternative: refuse and ask for a code (the web app has no code field).
**Answer:** as suggested — decided by Claude under the reviewer's delegation (2026-11-03).
**Resolution:** 🐞 BUG-1533 (pattern `derived-key-collision-refused`). Rules: `create_tag` R7.

### Q4. The tag list shows a live usage count; other answers show the stored counter — ✅ intended
**Background:** Each tag stores `usage_count`, kept by the item code (+1 / −1). `GET /item-tags/` replaces it in its answer with a live count of active items carrying the tag. `GET /item-tags/system/`, create and update return the stored counter. Nothing in the web app shows `usage_count` (searched).
**What happens today:** a tag with stored 9, one active and one deleted item shows 1 in the list and 9 in the system list (verified).
**Example:** An API client compares the two lists and sees two numbers for one tag.
**Rules affected:** `get_tags` R2, `get_system_tags` R2
**Suggested answer:** `intended` — no screen shows it, and the stored counter keeps its own rules (BUG-931). Alternative: every answer shows the live count.
**Answer:** intended — decided by Claude under the reviewer's delegation (2026-11-03).
**Resolution:** rules unchanged. Rules: `get_tags` R2 ✅, `get_system_tags` R2 ✅.

## Overview
`ItemTagService` manages the labels that categorise catalog items ("Raw Material", "Steel") within a workspace. The `/item-tags/` endpoints call it. It is the business layer for tags itself: it derives codes, refuses duplicates, protects the six seeded system tags (403), and soft-deletes by setting `is_active = False`. It commits and rolls back around its writes. Tag links on items and the stored counters are written by the item code, not here.

**Callables:** 5 specified · 1 not specified
**Externals to mock:** none. (`created_at` is the model's Python default `utcnow`, bound at import: assert set / not set.)
**Integration-only behavior:** the HTTP status of the `HTTPException`s; the response schema's validation of each returned tag (`ItemTagResponse`; Q2 (b)); schema validation (400 today, BUG-461; 422 intended); the 409 of BUG-1528's index through the global handler or the service.

**Facts for the test designer**
- Import: `from app.services.item_tag_service import ItemTagService, item_tag_service`. `ItemTagService()` takes no arguments. Parameters are positional-or-keyword; the endpoints pass all after `db` by keyword.
- `HTTPException` is `fastapi.HTTPException`: assert `.status_code` and `.detail`.
- Schemas (`app/schemas/item_tag.py`): `ItemTagCreate(name 1–100, tag_code: optional, 1–50, ^[a-z0-9_]+$, color: optional ^#[0-9A-Fa-f]{6}$, icon: optional ≤ 50, description: optional)`. `ItemTagUpdate(name, color, icon, description, is_active)`, all optional; no `tag_code`. `ItemTagResponse` inherits `ItemTagBase`, whose `tag_code` carries the pattern and length today.
- Table `item_tags` and the counters: item tag DAO spec, Model facts. `item_tag_assignments`: assignment DAO spec. Items need `name_normalized` (NOT NULL) when built directly.

**Notes for the test designer**
- Session and commits: as the Notes of `department_service.spec.md` (the `db` fixture makes `db.commit()` a savepoint release). **Difference:** the 409, 404 and 403 refusals here are raised **before** the `try`, so they do **not** roll back: an uncommitted setup row survives them (verified). Only errors inside the write roll back (S2). Test both: one refusal with an uncommitted extra row that is still there, one patched failing commit after which it is gone.
- **Response schema (Q2 (b)):** assert with `ItemTagResponse.model_validate(row)` on the returned row; today it raises `pydantic.ValidationError` for `café` → strict xfail.
- **Live count (`get_tags` R2, R3):** build one active and one deleted item (`is_active=False`) with links to one tag whose stored `usage_count = 9`; commit; call; assert the shown 1, then read the stored value with a plain `SELECT` **without flushing** (9). R3 is today's behavior and passes: after the call `tag in db.dirty` is `True`.
- **BUG-1528, BUG-1531 (index):** assert by inserting a second live row with the same code (name) directly and flushing inside `with db.begin_nested():` → `IntegrityError` 23505 → strict xfail. **Lost race through the service (R6):** a live tag with code `steel` committed; `unittest.mock.patch.object(app.dao.item_tag.item_tag_dao, "get_by_code_in_workspace", return_value=None)`; `create_tag` with `tag_code="steel"` and another name: intended 409 `Tag with code 'steel' already exists`, one row; today a second row is saved → strict xfail. The name race (R8) has no lookup to patch today (names are not checked); it is covered by the index case alone until the fix names its lookup.
- **BUG-1529:** build the deleted tag with `is_active=False` directly, commit, then call update / delete → today 200 / `None` → strict xfail.
- **BUG-1533:** names `"Steel-Bar"` then `"SteelBar"`; intended codes `steelbar`, `steelbar_2`; and with the Q2 fix, two Bengali names: `tag`, `tag_2`. Strict xfail.
- Strict xfail for every new bug here (BUG-1526 … BUG-1533): today's outcome is deterministic. BUG-929, BUG-930 pass-through: as the item tag DAO cases (order rests on physical order → non-strict).

## Not specified
- `item_tag_service` — module-level singleton, no logic.

---

### Transaction rules of this service (S)
- **S1.** A write that succeeds is committed: the change survives a later rollback of the session.
- **S2.** An exception inside the write (the DAO call, the commit, the re-read) rolls the session back and reaches the caller unchanged; nothing the call wrote is saved, and other uncommitted changes in the session are discarded too. If only the re-read after a successful commit fails, the change stays saved.
- **S3.** A refusal (`HTTPException` 409, 404, 403) is raised before anything is written and **without** a rollback: other uncommitted changes in the session stay pending.
- **S4.** The two lists neither commit nor roll back.

---

## `ItemTagService.get_tags(db, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /item-tags/`, the tag list of the item screens)

**Purpose:** The workspace's live tags, each with how many active items carry it.

**Returns:** a list of `ItemTag`.

**Rules:**
- **R1.** The tags are the item tag DAO's `get_active_tags_in_workspace` for the workspace, in its order: live tags only, system tags first (DAO rules, BUG-930).
- **R2.** ✅ (Q4) Each returned tag's `usage_count` is the number of active items (`items.is_active = True`) linked to it in the workspace (assignment DAO `count_active_items_per_tag`); a tag with no such link shows `0`. Links to deleted items are not counted.
- **R3.** The live count is not saved by this call and not committed. It is set on the session's objects, which stay changed: a later flush in the same session would store it (verified). No API path flushes after it.
- **R4.** [BUG-1532] (Q2 (b)) A stored tag whose code does not match `^[a-z0-9_]+$` or is outside 1–50 characters is still returned and passes `ItemTagResponse`. *(Today: the response refuses it, and the whole list answers 500. Verified.)*
- **R5.** Another workspace's tags never appear. Read only (S4).

**Errors:** none of its own. **Side effects:** none saved (R3).

---

## `ItemTagService.get_system_tags(db, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /item-tags/system/`; the web app does not call it)

**Rules:**
- **R1.** The tags are the item tag DAO's `get_system_tags_in_workspace` for the workspace, unchanged (DAO rules, BUG-929).
- **R2.** ✅ (Q4) `usage_count` is the stored counter.
- **R3.** Read only (S4).

**Errors:** none. **Side effects:** none

---

## `ItemTagService.create_tag(db, tag_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /item-tags/`, 201; the web app sends `name`, `color`, `description`, never `tag_code`)

**Purpose:** Create a user tag.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `tag_in` | `ItemTagCreate` | see Facts |
| `workspace_id` | int | the tag's workspace |
| `user_id` | int | stored as `created_by` |

**Returns:** the new `ItemTag`, committed and re-read.

**Rules:**
- **R1.** A sent `tag_code` is used as sent.
- **R2.** With no `tag_code`, the code is derived from the name: lower-cased, each space becomes `_`, and every other character that is not a letter, digit or `_` is dropped. `"Steel Bar"` → `steel_bar`, `"Steel-Bar"` → `steelbar`, `"Raw Material 2"` → `raw_material_2`.
- **R3.** [BUG-1532] (Q2 (a)) A derived code always matches `^[a-z0-9_]+$` and has 1–50 characters: the name is trimmed first (BUG-1526), every character outside ASCII `a-z`, `0-9`, `_` is dropped after lower-casing, the result is cut to 50, and if nothing is left the code is `tag`. `"Café"` → `caf`, `"!!!"` → `tag`, `"কাঁচামাল"` → `tag`, 60 × `a` → 50 × `a`, `" Bolt "` → `bolt`. *(Today: `café`, `""`, `কচমল`, 60 characters, `_bolt_`; the create answers 500 with the tag saved. Verified.)*
- **R4.** A **sent** `tag_code` already carried by a tag of the workspace → 409 `Tag with code '<code>' already exists`; nothing written. A tag of another workspace with that code does not block (verified). A **derived** code never gets this 409: R7. *(Today: a derived code that is taken gets the same 409, with the derived code in the message; that is BUG-1533, R7's today note.)*
- **R5.** [BUG-1527] (HR-2) Only live tags block a code: a deleted tag's code (`is_active = False`) can be used again. *(Today: 409. Verified.)*
- **R6.** [BUG-1528] (HR-2) The database refuses a second live tag with the same code in a workspace (partial unique index on live tags); a create that loses a race reaches the caller as 409 `Tag with code '<code>' already exists`, never 500, nothing saved. *(Today: no index; both are saved.)*
- **R7.** [BUG-1533] (Q3) When the code was derived (R2, R3) and R4 would refuse it, the first free of `<code>_2`, `<code>_3`, … is used instead, the base cut so the whole has at most 50 characters; no 409. An explicit `tag_code` that is taken stays R4. *(Today: 409 for the derived code. Verified.)*
- **R8.** [BUG-1531] (Q1, HR-2) A name already used by a live tag of the workspace (system tags included), compared case-insensitively after trimming, → 409 `Tag with name '<name>' already exists` (the trimmed submitted name), checked before the code, nothing written. A deleted tag's name, or another workspace's, does not block. The database backs it with a partial unique index on live tags; a lost race is the same 409. *(Today: names are not checked. Verified.)*
- **R9.** [BUG-1526] (HR-1) The name is stored trimmed; a blank or whitespace-only name is refused by `ItemTagCreate` (`pydantic.ValidationError`; 422 at the API), nothing written. *(Today: `"   "` is stored with code `___`; `" Bolt "` keeps its spaces. Verified.)*
- **R10.** The new tag has the workspace, `name`, `tag_code`, `color`, `icon`, `description` as given, `created_by = user_id`, `is_system_tag = False`, `usage_count = 0`, `is_active = True`, `created_at` set. A client cannot make a system tag. It is committed (S1) and returned re-read.
- **R11.** Refusals follow S3 (no rollback); errors inside the write follow S2.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| [BUG-1531] live tag with that name | `HTTPException` 409 | `Tag with name '<name>' already exists` |
| code taken (explicit; [BUG-1527] live tags only; [BUG-1528] also the index) | `HTTPException` 409 | `Tag with code '<code>' already exists` |
| [BUG-1526] blank name | `pydantic.ValidationError` (schema) | — |

**Side effects:** one `item_tags` row, committed; on error inside the write, rolled back.

---

## `ItemTagService.update_tag(db, tag_id, tag_in, workspace_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PUT /item-tags/{id}/`; the web app sends `name`, `color`, `description`)

**Returns:** the `ItemTag`, committed and re-read.

**Rules:**
- **R1.** Unknown id, `0`, another workspace's id → 404 `Tag not found`, nothing written.
- **R2.** [BUG-1529] (HR-4) A deleted tag → 404 `Tag not found`, nothing written; `{"is_active": true}` cannot bring it back. *(Today: edited, 200; `is_active: true` restores it. Verified.)*
- **R3.** A system tag → 403 `System tags cannot be modified`, whatever is sent, nothing written; checked after R1, R2.
- **R4.** Every field sent with a value is written (`name`, `color`, `icon`, `description`, `is_active`); omitted fields stay. The code never changes, also on a rename.
- **R5.** [BUG-1530] (P1) An explicit `null` clears `color`, `icon`, `description`; `null` for `name` or `is_active` is refused by `ItemTagUpdate`. *(Today: every `null` is dropped and the old value stays, 200. Verified.)*
- **R6.** [BUG-1531] (Q1) A new name used by another live tag of the workspace (case-insensitive, trimmed) → 409 `Tag with name '<name>' already exists`, nothing written; the tag's own name in another case or with spaces is accepted. *(Today: accepted. Verified.)*
- **R7.** [BUG-1526] (HR-1) The new name is stored trimmed; blank is refused by `ItemTagUpdate`. *(Today: `"  "` is stored. Verified.)*
- **R8.** `{"is_active": false}` on a live user tag hides it exactly as `delete_tag` R4; `{"is_active": true}` on a live tag changes nothing.
- **R9.** Committed (S1); returned re-read. Refusals follow S3; errors inside the write S2.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / other workspace; [BUG-1529] deleted | `HTTPException` 404 | `Tag not found` |
| system tag | `HTTPException` 403 | `System tags cannot be modified` |
| [BUG-1531] name taken | `HTTPException` 409 | `Tag with name '<name>' already exists` |

**Side effects:** the changed fields, committed. No audit column exists.

---

## `ItemTagService.delete_tag(db, tag_id, workspace_id)`
**Shape:** soft-delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /item-tags/{id}/`, 204)

**Returns:** `None`.

**Rules:**
- **R1.** Unknown id, `0`, another workspace's id → 404 `Tag not found`, nothing written.
- **R2.** [BUG-1529] (HR-4) An already deleted tag → 404 `Tag not found`. *(Today: deleted again, `None`, 204. Verified.)*
- **R3.** A system tag → 403 `System tags cannot be deleted`, nothing written.
- **R4.** A live user tag gets `is_active = False` and nothing else: `usage_count`, its links to items and every other field stay; it is committed (S1). The tag then leaves `get_tags`, and its links are hidden by its state.
- **R5.** Refusals follow S3; errors inside the write S2.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / other workspace; [BUG-1529] deleted | `HTTPException` 404 | `Tag not found` |
| system tag | `HTTPException` 403 | `System tags cannot be deleted` |

**Side effects:** `is_active` set to `False`, committed.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 15 | active tags of the workspace (DAO) | `get_tags` R1, R5 |
| 16–18 | live counts of active items (assignment DAO) | `get_tags` R2 |
| 19–20 | loop over tags; `.get(id, 0)` → 0 without links; set on the object | `get_tags` R2, R3 |
| 21 | returned list validated by the response schema (BUG-1532) | `get_tags` R4 |
| 25 | system tags (DAO) | `get_system_tags` R1–R3 |
| 29–32 | `if not tag_code` → derive (BUG-1532, BUG-1533); sent → as is | `create_tag` R1, R2, R3, R7 |
| 34–39 | code found among all the workspace's tags → 409 (BUG-1527); no name check (BUG-1531) | `create_tag` R4, R5, R8; S3 |
| 41–51 | build row, create, commit, refresh, return | `create_tag` R10; S1 |
| 52–53 | `except HTTPException: raise` — unreachable: nothing in the `try` raises one | `create_tag` R11 |
| 54–56 | any other exception → rollback, re-raise; no index (BUG-1528) | `create_tag` R6, R11; S2 |
| 60–62 | not found / other workspace → 404; deleted found (BUG-1529) | `update_tag` R1, R2 |
| 63–64 | system → 403 | `update_tag` R3 |
| 65–69 | DAO update (`exclude_none`, BUG-1530; no name check, BUG-1531), commit, refresh | `update_tag` R4–R9 |
| 70–71 | `except HTTPException: raise` — unreachable | `update_tag` R9 |
| 72–74 | any other exception → rollback, re-raise | `update_tag` R9; S2 |
| 78–80 | not found / other workspace → 404; deleted found (BUG-1529) | `delete_tag` R1, R2 |
| 81–82 | system → 403 | `delete_tag` R3 |
| 83–85 | `is_active = False`, commit | `delete_tag` R4 |
| 86–87 | `except HTTPException: raise` — unreachable | `delete_tag` R5 |
| 88–90 | any other exception → rollback, re-raise | `delete_tag` R5; S2 |
| 93 | module singleton | Not specified |

## Follow-ups for other reviews
> Nothing below is a rule of this service.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Schemas** (`app/schemas/item_tag.py`) | BUG-1526 and BUG-1530 go on `ItemTagCreate` / `ItemTagUpdate`; BUG-1532 (b) removes the pattern and length from the `tag_code` of what `ItemTagResponse` inherits (split `ItemTagBase` or override the field). | HR-1, P1, Q2 |
| FU-2 | **Account tag service** (`app/services/account_tag_service.py`, not yet described) | Same code shape as this one (account tag DAO FU-1): BUG-1527 … BUG-1533 are precedents for it. | all |
| FU-3 | **Dead code** | The three `except HTTPException: raise` clauses are unreachable. Not added to the dead-code list: they are branches, not callables; remove with the fixes above. | Branch map |

## Gap log
G1 (item_tag_service.cases.md gap 1) — Contradiction, delegated — R4 now covers sent codes only; a derived code goes to R7 (BUG-1533), with today's 409 as R4's today note. `create_tag` R4.
G2 (gap 2) — Test mechanics — race simulated by patching `item_tag_dao.get_by_code_in_workspace` to `None`; the name race stays index-only. Notes.
