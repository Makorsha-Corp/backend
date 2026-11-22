# Spec — `app/services/account_tag_service.py`

> **Status:** APPROVED (2026-11-04: P1–P4 confirmed, Q1, Q2 answered — decided by Claude under the reviewer's delegation (2026-11-04); BUG-1688 … BUG-1693). Stays APPROVED after fill-gaps 2026-11-04 (Gap log at the end; decided by Claude under the reviewer's delegation (2026-11-04)).
> **Source commit:** e48a092

> **Form.** As `tests/unit/services/item_tag_service.spec.md`, whose code this file copies almost line for line. This service has **no manager** and does **not** inherit `BaseService`: it holds the tag rules itself, calls `account_tag_dao` directly, and commits and rolls back itself. Its writes have the outcomes of **TC1–TC5** of `department_service.spec.md` with one difference (S3: refusals do not roll back), its reads **TC6**. Below it: `tests/unit/dao/account_tag.spec.md` (APPROVED) and `tests/unit/dao/base.spec.md`.

> **Routed here and written as rules:** account tag DAO FU-1 (a) → BUG-1683; (b) → BUG-1684; (c) → BUG-1682 and P2; (d) → Q1, Q2; (e) → BUG-1685; (f) `GET /account-tags/system/` — the web app does not call it (searched), it stays specified. Item tag service FU-2: BUG-1526 … BUG-1533 are precedents here (P1–P4 and the four house-rule lines).
>
> **Standing decisions applied here (not asked again):** for account tags "deleted" is `is_active = False` (account tag DAO standing decisions); raw DAO lookups stay raw and the caller decides what to hide (HR-4 scope); input limits go on the input schemas, never on a response schema that stored rows must still pass (BUG-915).
>
> **Verified by running** (`h.py`, `v1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3d\`, one outer transaction rolled back against `marker_test`, session as the `db` fixture; nothing persisted): derived codes `"Café"` → `café` (passes `AccountTagResponse`), `"কাঁচামাল"` → `কচমল`, `"   "` → `___`, `"!!!"` → `""` (stored; `AccountTagResponse` refuses it), 60 × `a` → `DataError` 22001 at the flush, rolled back, nothing saved; an explicit `tag_code="Supplier X"` stored as sent; `PUT {"tag_code": "vendor_x"}` onto another live tag's code → stored (two tags, one code); `{"color": null, "description": null}` → unchanged; a second live `"Vendor X"` with another code → stored; a deleted tag deleted again (`None`) and restored by `{"is_active": true}`; a deleted tag's code → 409 `Tag with code 'vendor_x' already exists`; another workspace's id → 404 `Tag not found`; a system tag → 403 on update and delete; a 409 leaves an uncommitted setup row of the session in place. **Not run:** anything over HTTP; two concurrent creates; the intended behavior of any bug rule.

## Review
> All answered 2026-11-04 (decided by Claude under the reviewer's delegation (2026-11-04)). None touches money, stock, an order workflow, or who may see or do what — no OWNER item.

### Quick list
| # | What the code does today, in plain words | Decided |
|---|---|---|
| P1 | A tag's colour, icon and description cannot be cleared | bug, per BUG-1530 → 🐞 BUG-1688 |
| P2 | Two live account tags can have the same name | bug, per BUG-1531 → 🐞 BUG-1689 |
| P3 | A name of symbols only, or over 50 characters, breaks the create or the whole tag list | bug, per BUG-1532 → 🐞 BUG-1690 |
| P4 | Two names that derive one code: the second is refused with a code the user never typed | bug, per BUG-1533 → 🐞 BUG-1691 |
| Q1 | A tag's code can be changed by an edit, onto another tag's code, with no check | bug — the code is fixed at create → 🐞 BUG-1692 |
| Q2 | A code sent by the client has no format: `"Supplier X"` is stored | bug — same format as item tag codes → 🐞 BUG-1693 |

### House-rule violations — applied automatically

- **HR-1** `create_tag` R9, `update_tag` R8 — names are stored as typed: `"   "` is accepted (code `___`, verified). Intended: `AccountTagCreate` and `AccountTagUpdate` trim `name` and refuse a blank one (422), nothing written; not on `AccountTagBase`, which the response inherits.
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-1682 (pattern `blank-name-accepted`; per BUG-1526). Rules: `create_tag` R9, `update_tag` R8.
- **HR-2** `create_tag` R5 — the code check counts deleted tags: a deleted tag's code can never be used again (verified: 409). Intended: only live tags (`is_active = True`) of the workspace block a code.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-1683 (pattern `uniqueness-check-counts-soft-deleted`; per BUG-1527). Rules: `create_tag` R5.
- **HR-2** `create_tag` R6 — `account_tags` has no unique index: code uniqueness is checked only in Python, so two creates at once both pass. Intended: a partial unique index on `(workspace_id, tag_code)` over live tags; a lost race reaches the caller as 409 `Tag with code '<code>' already exists`, never 500.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-1684 (pattern `python-only-uniqueness`; per BUG-1528). Rules: `create_tag` R6.
- **HR-4** `update_tag` R2, `delete_tag` R2 — a deleted tag is found by id like a live one: it is edited, deleted again, and brought back by `PUT {"is_active": true}` (verified). Intended: a deleted tag is 404 `Tag not found`, nothing written.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-1685 (pattern `mutation-on-soft-deleted`; per BUG-1529). Rules: `update_tag` R2, `delete_tag` R2.

Reached through the DAO and cited, one pass-through case each: **BUG-1482** (both lists' order), **BUG-1483** (system list shows deleted system tags), **BUG-1485** (active list capped at 100). **BUG-1484** (counter race) is reached through accounts, not here.

Checked and **not** violated: **HR-3** — the backend does not group by code here; the account filter by code is BUG-861 (account manager). **HR-5, HR-7** — no paging from the API. **HR-8** — no `LIKE`. **HR-9** — no "last changed by" column. **HR-10** — a tag delete is a plain soft delete. **HR-11 … HR-15** — none applies. **HR-16** — every lookup is by the caller's workspace; another workspace's id is 404, identical to an unknown one (verified).

**Permission checks:** none; any active member may create, edit and delete user tags (as `item_tag_service.spec.md`). System tags are refused to everyone (403). **No screen** creates, edits or deletes account tags: the web app only reads `GET /account-tags/` (the account forms' tag picker), so every write rule here is reached by a direct API call today.

### Precedent matches — confirmed (ok)

### P1. A tag's colour, icon and description cannot be cleared — 🐞 BUG-1688
**Background:** The update applies only fields sent with a value; an explicit `null` is dropped. Same root cause as BUG-1530 (item tags) and BUG-942.
**What happens today:** `{"color": null, "description": null}` → 200, both stay (verified).
**Example:** A client clears the description of tag "Vendor X"; the answer still shows the old description.
**Rules affected:** `update_tag` R5
**Answer:** ok — bug per BUG-1530 precedent: explicit `null` clears `color`, `icon`, `description`; `null` for `name` or `is_active` is refused by `AccountTagUpdate` (422); omitted fields stay unchanged — decided by Claude under the reviewer's delegation (2026-11-04)
**Resolution:** 🐞 BUG-1688 (pattern `exclude-none-blocks-clear`). Adapted to Q1: `AccountTagUpdate` no longer has `tag_code` (BUG-1692), so a `tag_code` in the body, `null` or not, is ignored rather than refused. Rules: `update_tag` R5.

### P2. Two live account tags can have the same name — 🐞 BUG-1689
**Background:** Only the code is checked, only on create. Users pick account tags by the name on the chip. BUG-1531 ruled tag names unique for item tags.
**What happens today:** A second live `"Vendor X"` with another code is stored (verified); a rename onto another tag's name is accepted.
**Example:** The account form's tag picker shows two "Vendor X" chips; half the accounts carry each.
**Rules affected:** `create_tag` R8, `update_tag` R6
**Answer:** bug — per BUG-1531 precedent: names unique among the workspace's live tags (system tags included), case-insensitive after trimming, on create and rename, 409 `Tag with name '<name>' already exists` (trimmed submitted name), backed by a partial unique index; a deleted tag's name can be reused — confirmed (ok), decided by Claude under the reviewer's delegation (2026-11-04)
**Resolution:** 🐞 BUG-1689 (pattern `python-only-uniqueness`). Rules: `create_tag` R8, `update_tag` R6.

### P3. Some names break the create or the whole tag list — 🐞 BUG-1690
**Background:** With no code sent, the code is derived from the name (lower-case, spaces to `_`, other non-letter / non-digit characters dropped). The column holds 50 characters; `AccountTagResponse` requires a code of 1–50 characters (no pattern, unlike item tags).
**What happens today:** `"!!!"` → code `""`: stored, and the response refuses it — the create answers 500 with the tag saved, and from then on `GET /account-tags/` answers 500 for the whole workspace. A name of 51+ letters → `DataError` at the flush, 500, nothing saved. `"Café"` → `café` and Bengali names are stored and listed (verified).
**Example:** Someone creates the tag "???" through the API; every account form's tag picker in the workspace stops loading.
**Rules affected:** `create_tag` R3, `get_tags` R3
**Answer:** bug — per BUG-1532 precedent: (a) a derived code always matches `^[a-z0-9_]+$` and has 1–50 characters (trimmed name, lower-cased, spaces → `_`, everything outside ASCII `a-z`, `0-9`, `_` dropped, cut to 50, `tag` if nothing is left); (b) `AccountTagResponse` does not apply the input length to `tag_code`, so stored rows list again — confirmed (ok), decided by Claude under the reviewer's delegation (2026-11-04)
**Resolution:** 🐞 BUG-1690 (pattern `derived-value-violates-schema`). Rules: `create_tag` R3, `get_tags` R3.

### P4. Different names that derive one code are refused — 🐞 BUG-1691
**Background:** As P3. `"Steel-Bar"` and `"SteelBar"` both derive `steelbar`; after P3 every Bengali name derives `tag`.
**What happens today:** the second create is 409 `Tag with code '<code>' already exists`, naming a code the user never typed.
**Example:** After a Bengali tag exists, a second Bengali tag is refused with "Tag with code 'tag' already exists".
**Rules affected:** `create_tag` R7
**Answer:** bug — per BUG-1533 precedent: a derived code that a live tag of the workspace already has becomes the first free `<code>_2`, `<code>_3`, … (base cut so the whole stays within 50); an explicit taken code stays 409 — confirmed (ok), decided by Claude under the reviewer's delegation (2026-11-04)
**Resolution:** 🐞 BUG-1691 (pattern `derived-key-collision-refused`). Rules: `create_tag` R7.

### New questions

### Q1. A tag's code can be changed by an edit, onto another tag's code — 🐞 BUG-1692
**Background:** Unlike item tags, `AccountTagUpdate` has `tag_code`. The code is the key the API filters accounts by (`GET /accounts/?tag_code=supplier`); the create checks it for duplicates, the update checks nothing. System tags (the seeded `supplier`, `vendor`, `client`, `utility`) cannot be edited (403).
**What happens today:** `PUT {"tag_code": "vendor_x"}` on tag "Other" while "Vendor X" has `vendor_x` → 200; two live tags share the code, and the account filter by `vendor_x` returns the accounts of both (verified the duplicate; the filter read, not run).
**Example:** A client renames the code of "Other" to `vendor_x`; a report built on `?tag_code=vendor_x` now mixes "Other" accounts in with "Vendor X" ones.
**Rules affected:** `update_tag` R4, R4a
**Suggested answer:** `bug — the code is fixed at create, as for item tags: AccountTagUpdate has no tag_code, and a tag_code in the body is ignored`. Alternative: `bug — editable, but a code used by another live tag of the workspace is 409 "Tag with code '<code>' already exists", and the format of Q2 applies`.
**Answer:** bug — the code is fixed at create, as for item tags; `tag_code` is dropped from `AccountTagUpdate`, so a PUT cannot change it — decided by Claude under the reviewer's delegation (2026-11-04)
**Resolution:** 🐞 BUG-1692 (pattern `identity-key-editable`). Fix in `app/schemas/account_tag.py`. A `tag_code` in a PUT body is ignored (the schema's default for unknown fields), the rest of the update applies. Rules: `update_tag` R4, R4a, R5.

### Q2. A code sent by the client has no format — 🐞 BUG-1693
**Background:** `AccountTagCreate.tag_code` (and `AccountTagUpdate.tag_code`) only require 1–50 characters; the item tag twin requires `^[a-z0-9_]+$`. The account filter compares codes exactly today; BUG-861 makes it case-insensitive after trimming.
**What happens today:** `tag_code="Supplier X"` is stored as sent (verified); so are `" supplier"` and `"SUPPLIER"`. After BUG-861, `?tag_code=supplier` matches both `SUPPLIER` and the seeded `supplier`.
**Example:** A client creates "Big suppliers" with code `SUPPLIER`; once BUG-861 is fixed, filtering by the system tag "Supplier" also returns the "Big suppliers" accounts.
**Rules affected:** `create_tag` R1a
**Suggested answer:** `bug — a sent tag_code must match ^[a-z0-9_]+$ (1–50), as item tag codes; otherwise AccountTagCreate refuses it (422), nothing written`. With P3 every code then has one format. Alternative: `intended` — codes are free text.
**Answer:** bug — a client-sent code must match `^[a-z0-9_]+$`, 1–50 characters, as item tag codes do — decided by Claude under the reviewer's delegation (2026-11-04)
**Resolution:** 🐞 BUG-1693 (pattern `unvalidated-code-input`). Fix on `AccountTagCreate` only (after BUG-1692 `AccountTagUpdate` has no code), not on `AccountTagBase` (BUG-915; P3 (b)). No trimming or lower-casing: a code outside the format is refused, not repaired. Rules: `create_tag` R1, R1a.

## Overview
`AccountTagService` manages the labels that say what an account is (Supplier, Client, Vendor, Utility are seeded system tags; users add their own) within a workspace. The `/account-tags/` endpoints call it. It is the business layer for tags itself: it derives codes, refuses duplicate codes on create, protects system tags (403), and soft-deletes by setting `is_active = False`. It commits and rolls back around its writes. Tag links on accounts and the stored `usage_count` are written by the account code, not here; unlike item tags, the list shows the **stored** counter.

**Callables:** 5 specified · 1 not specified
**Externals to mock:** none. (`created_at` is the model's Python default `utcnow`, bound at import: assert set / not set.)
**Integration-only behavior:** the HTTP status of the `HTTPException`s; the response schema's validation of each returned tag (`AccountTagResponse`; P3 (b)); schema validation (400 today, BUG-461; 422 intended); BUG-1684's index violation through the global handler or the service.

**Facts for the test designer**
- Import: `from app.services.account_tag_service import AccountTagService, account_tag_service`. `AccountTagService()` takes no arguments. Parameters are positional-or-keyword; the endpoints pass all after `db` by keyword.
- `HTTPException` is `fastapi.HTTPException`: assert `.status_code` and `.detail`.
- Schemas (`app/schemas/account_tag.py`): `AccountTagCreate(name 1–100, tag_code: optional 1–50, color: optional ^#[0-9A-Fa-f]{6}$, icon: optional ≤ 50, description: optional)`. `AccountTagUpdate(name, tag_code, color, icon, description, is_active)`, all optional, same limits — after BUG-1692 without `tag_code`; after BUG-1693 `AccountTagCreate.tag_code` adds the pattern `^[a-z0-9_]+$`. `AccountTagResponse` inherits `AccountTagBase` (`tag_code` 1–50, no pattern).
- Table `account_tags`: account tag DAO spec, Model facts (no unique index; `tag_code` varchar(50)).

**Notes for the test designer**
- Session and commits: as the Notes of `item_tag_service.spec.md` — the 409, 404 and 403 refusals are raised **before** the `try` and do **not** roll back (S3, verified); only errors inside the write roll back (S2).
- **BUG-1692:** today `AccountTagUpdate(tag_code="vendor_x")` is accepted and the service stores it → strict xfail on "the stored code is unchanged". **BUG-1693:** `AccountTagCreate(name="X", tag_code="Supplier X")` → intended `pydantic.ValidationError`, today accepted → strict xfail. **BUG-1688:** `AccountTagUpdate(name=None)` explicitly → intended `pydantic.ValidationError`, today accepted → strict xfail.
- **P3 (b) / BUG-1690:** assert `AccountTagResponse.model_validate(row)` on a stored row with code `""` (built directly) → today `pydantic.ValidationError` → strict xfail. The 51-letter name today raises `DataError` 22001 inside the write (S2): nothing saved.
- **BUG-1684:** insert a second live row with the same code directly inside `with db.begin_nested():` → intended `IntegrityError` 23505 → strict xfail. Lost race through the service: `patch.object(app.dao.account_tag.account_tag_dao, "get_by_tag_code_in_workspace", return_value=None)` (as item tags).
- **BUG-1685:** build the deleted tag with `is_active=False` directly, commit, then call → today 200 / `None` → strict xfail.
- Strict xfail for every new bug here (deterministic today). BUG-1482 pass-through non-strict (physical order), BUG-1483 and BUG-1485 strict (as the account tag DAO cases).

## Not specified
- `account_tag_service` — module-level singleton, no logic.

---

### Transaction rules of this service (S)
- **S1.** A write that succeeds is committed (TC1); `create_tag` and `update_tag` return the row re-read (TC2).
- **S2.** An exception inside the write (the DAO call, the flush, the commit, the re-read) rolls the session back and reaches the caller unchanged; nothing saved, other uncommitted changes of the session discarded (TC3, TC4). If only the re-read after a successful commit fails, the change stays saved (TC5).
- **S3.** A refusal (`HTTPException` 409, 404, 403) is raised before anything is written and **without** a rollback: other uncommitted changes in the session stay pending (verified).
- **S4.** The two lists neither commit nor roll back (TC6).

---

## `AccountTagService.get_tags(db, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /account-tags/`, the tag picker of the account forms)

**Rules:**
- **R1.** The tags are the DAO's `get_active_tags_in_workspace` for the workspace, unchanged: live tags only, system and user, every one (BUG-1485), system tags first, then name, then `id` (BUG-1482). Another workspace's never.
- **R2.** `usage_count` is the stored counter (not recounted).
- **R3.** [BUG-1690] (P3 (b)) A stored tag whose code is `""` or otherwise outside the input format is still returned and passes `AccountTagResponse`. *(Today: the response refuses a `""` code, and the whole list answers 500.)*
- **R4.** Read only (S4).

**Errors:** none of its own. **Side effects:** none

---

## `AccountTagService.get_system_tags(db, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /account-tags/system/`; the web app does not call it)

**Rules:**
- **R1.** The tags are the DAO's `get_system_tags_in_workspace` for the workspace, unchanged (DAO rules, BUG-1482, BUG-1483); stored `usage_count`.
- **R2.** Read only (S4).

**Errors:** none. **Side effects:** none

---

## `AccountTagService.create_tag(db, tag_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /account-tags/`, 201; no screen calls it)

**Returns:** the new `AccountTag`, committed and re-read.

**Rules:**
- **R1.** A sent `tag_code` that matches the format of R1a is used as sent (`"supplier_x"` → `supplier_x`).
- **R1a.** [BUG-1693] (Q2) A sent `tag_code` must match `^[a-z0-9_]+$` and have 1–50 characters, as item tag codes; otherwise `AccountTagCreate` refuses it (`pydantic.ValidationError`; 422 at the API), nothing written. It is not trimmed or lower-cased: `"Supplier X"`, `"SUPPLIER"`, `" supplier"`, `"supplier-x"`, `"café"` are all refused; `""` and 51 characters stay refused as today. *(Today: any 1–50 characters are accepted and stored as sent — `"Supplier X"`, verified.)*
- **R2.** With no `tag_code` (omitted or `null`), the code is derived from the name: lower-cased, each space becomes `_`, every other character that is not a letter, digit or `_` is dropped. `"Steel Bar"` → `steel_bar`, `"Steel-Bar"` → `steelbar`, `"Café"` → `café`.
- **R3.** [BUG-1690] (P3 (a)) A derived code always matches `^[a-z0-9_]+$` and has 1–50 characters: trimmed name, lower-cased, spaces → `_`, everything outside ASCII `a-z`, `0-9`, `_` dropped, cut to 50, `tag` if empty. `"Café"` → `caf`, `"!!!"` → `tag`, 60 × `a` → 50 × `a`, `" Bolt "` → `bolt`. *(Today: `café`; `""` stored, then 500 at the response; 60 letters → `DataError` 22001, rolled back, nothing saved; `_bolt_`. Verified.)*
- **R4.** A **sent** `tag_code` already carried by a tag of the workspace → 409 `Tag with code '<code>' already exists`; nothing written. Another workspace's tag with that code does not block. *(Today a derived code that is taken gets the same 409 — P4, R7.)*
- **R5.** [BUG-1683] (HR-2) Only live tags block a code: a deleted tag's code can be used again. *(Today: 409. Verified.)*
- **R6.** [BUG-1684] (HR-2) The database refuses a second live tag with one code in a workspace (partial unique index); a create that loses a race reaches the caller as 409 `Tag with code '<code>' already exists`, never 500, nothing saved. *(Today: no index; both saved.)*
- **R7.** [BUG-1691] (P4) When the code was derived and R4 would refuse it, the first free of `<code>_2`, `<code>_3`, … is used (base cut to stay within 50); no 409. *(Today: 409 naming the derived code.)*
- **R8.** [BUG-1689] (P2) A name used by a live tag of the workspace (system tags included), case-insensitive after trimming → 409 `Tag with name '<name>' already exists` (`<name>` = the trimmed submitted name, original case kept; P2), checked before the code, nothing written; a deleted tag's or another workspace's name does not block; backed by a partial unique index. *(Today: names are not checked; verified a second "Vendor X" stored.)*
- **R9.** [BUG-1682] (HR-1) The name is stored trimmed; a blank name is refused by `AccountTagCreate` (`pydantic.ValidationError`; 422), nothing written. *(Today: `"   "` stored with code `___`. Verified.)*
- **R10.** The new tag has the workspace, `name`, `tag_code`, `color`, `icon`, `description` as given, `created_by = user_id`, `is_system_tag = False`, `usage_count = 0`, `is_active = True`, `created_at` set. A client cannot make a system tag. Committed (S1), returned re-read.
- **R11.** Refusals follow S3; errors inside the write S2.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| [BUG-1689] live tag with that name | `HTTPException` 409 | `Tag with name '<name>' already exists` |
| sent code taken ([BUG-1683] live tags only; [BUG-1684] also the index) | `HTTPException` 409 | `Tag with code '<code>' already exists` |
| [BUG-1682] blank name; [BUG-1693] sent code outside `^[a-z0-9_]+$` | `pydantic.ValidationError` (schema) | — |

**Side effects:** one `account_tags` row, committed; on error inside the write, rolled back.

---

## `AccountTagService.update_tag(db, tag_id, tag_in, workspace_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PUT /account-tags/{id}/`; no screen calls it)

**Returns:** the `AccountTag`, committed and re-read.

**Rules:**
- **R1.** Unknown id, `0`, another workspace's id → 404 `Tag not found`, nothing written (verified).
- **R2.** [BUG-1685] (HR-4) A deleted tag → 404 `Tag not found`, nothing written; `{"is_active": true}` cannot bring it back. *(Today: edited; `is_active: true` restores it. Verified.)*
- **R3.** A system tag → 403 `System tags cannot be modified`, whatever is sent, nothing written; checked after R1, R2 (verified).
- **R4.** Every field sent with a value is written (`name`, `color`, `icon`, `description`, `is_active`); omitted fields stay.
- **R4a.** [BUG-1692] (Q1) An update never changes `tag_code`: `AccountTagUpdate` has no `tag_code` field, so a `tag_code` in the body (a value or `null`) is ignored — the tag keeps its code, the other fields sent are applied as R4, no error. A body with only `tag_code` changes nothing. *(Today: `tag_code` is written with no check; onto another live tag's code it is stored, two live tags share one code. Verified.)*
- **R5.** [BUG-1688] (P1) An explicit `null` clears `color`, `icon`, `description`; `null` for `name` or `is_active` is refused by `AccountTagUpdate` (`pydantic.ValidationError`; 422), nothing written. *(Today: every `null` is dropped, 200. Verified.)*
- **R6.** [BUG-1689] (P2) A new name used by another live tag of the workspace (case-insensitive, trimmed) → 409 `Tag with name '<name>' already exists`, where `<name>` is the **trimmed submitted name** (as typed in the request, outer spaces removed, original case kept; not the other tag's stored name), as `create_tag` R8 (P2 answer, gap G1); the tag's own name in another case is accepted. *(Today: accepted.)*
- **R7.** `{"is_active": false}` on a live user tag hides it exactly as `delete_tag` R4.
- **R8.** [BUG-1682] (HR-1) A new name is stored trimmed; blank is refused by `AccountTagUpdate`.
- **R9.** Committed (S1), returned re-read. Refusals follow S3; errors inside the write S2.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / other workspace; [BUG-1685] deleted | `HTTPException` 404 | `Tag not found` |
| system tag | `HTTPException` 403 | `System tags cannot be modified` |
| [BUG-1689] name taken | `HTTPException` 409 | `Tag with name '<name>' already exists` |
| [BUG-1688] `null` for `name` or `is_active` | `pydantic.ValidationError` (schema) | — |

**Side effects:** the changed fields, committed. No audit column.

---

## `AccountTagService.delete_tag(db, tag_id, workspace_id)`
**Shape:** soft-delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /account-tags/{id}/`, 204; no screen calls it)

**Returns:** `None`.

**Rules:**
- **R1.** Unknown id, `0`, another workspace's id → 404 `Tag not found`, nothing written.
- **R2.** [BUG-1685] (HR-4) An already deleted tag → 404 `Tag not found`. *(Today: `None`, 204. Verified.)*
- **R3.** A system tag → 403 `System tags cannot be deleted`, nothing written (verified).
- **R4.** A live user tag gets `is_active = False` and nothing else: `usage_count`, its links to accounts and every other field stay; committed (S1). It then leaves `get_tags`.
- **R5.** Refusals follow S3; errors inside the write S2.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / other workspace; [BUG-1685] deleted | `HTTPException` 404 | `Tag not found` |
| system tag | `HTTPException` 403 | `System tags cannot be deleted` |

**Side effects:** `is_active` set to `False`, committed.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 14 | active tags (DAO) | `get_tags` R1–R4 |
| 18 | system tags (DAO) | `get_system_tags` R1, R2 |
| 22–25 | `if not tag_code` (`None`; `""` is refused by the schema) → derive (BUG-1690, BUG-1691); sent → as is (format: BUG-1693) | `create_tag` R1, R1a, R2, R3, R7 |
| 27–32 | code found among all the workspace's tags → 409, before the `try`, no rollback (BUG-1683); no name check (BUG-1689) | `create_tag` R4, R5, R8; S3 |
| 34–44 | build row, create, commit, refresh, return | `create_tag` R10; S1 |
| 45–46 | `except HTTPException: raise` — unreachable: nothing in the `try` raises one | `create_tag` R11 |
| 47–49 | any other exception → rollback, re-raise; no index (BUG-1684) | `create_tag` R3, R6, R11; S2 |
| 53–55 | not found / other workspace → 404; deleted found (BUG-1685) | `update_tag` R1, R2 |
| 56–57 | system → 403 | `update_tag` R3 |
| 58–62 | DAO update (drops `null`s, BUG-1688; writes `tag_code`, BUG-1692; no name check, BUG-1689), commit, refresh | `update_tag` R4, R4a, R5–R9 |
| 63–64 | `except HTTPException: raise` — unreachable | `update_tag` R9 |
| 65–67 | any other exception → rollback, re-raise | `update_tag` R9; S2 |
| 71–73 | not found / other workspace → 404; deleted found (BUG-1685) | `delete_tag` R1, R2 |
| 74–75 | system → 403 | `delete_tag` R3 |
| 76–78 | `is_active = False`, commit | `delete_tag` R4 |
| 79–80 | `except HTTPException: raise` — unreachable | `delete_tag` R5 |
| 81–83 | any other exception → rollback, re-raise | `delete_tag` R5; S2 |
| 86 | module singleton | Not specified |

## Gap log
G1 (account_tag_service.cases.md gap 1) — Fact (recorded decision) — `update_tag` R6 now states what P2's answer already said for both create and rename: the 409's `<name>` is the trimmed submitted name, original case kept (precedent: messages show the trimmed name; decided by Claude under the reviewer's delegation (2026-11-04)). The same words added to `create_tag` R8, which also lacked them. No rule renumbered.

## Follow-ups for other reviews
> Nothing below is a rule of this service.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Schemas** (`app/schemas/account_tag.py`) | BUG-1682, BUG-1688 go on `AccountTagCreate` / `AccountTagUpdate`; BUG-1692 removes `tag_code` from `AccountTagUpdate`; BUG-1693 adds the code pattern to `AccountTagCreate`; BUG-1690 (b) removes the length from the `tag_code` of what `AccountTagResponse` inherits. | HR-1, P1, P3, Q1, Q2 |
| FU-2 | **Dead code** | The three `except HTTPException: raise` clauses are unreachable (as item tags FU-3); branches, not callables: remove with the fixes. | Branch map |
