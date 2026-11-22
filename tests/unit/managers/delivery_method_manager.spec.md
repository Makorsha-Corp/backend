# Spec — `app/managers/delivery_method_manager.py`

> **Status:** APPROVED (2026-11-04; no question — every item below is a house rule, logged)
> **Source commit:** e48a092

> **Family.** The code is `app/managers/department_manager.py` with the names changed: same checks, same order, same flow; only the messages differ ("Delivery method …"). The approved `tests/unit/managers/department_manager.spec.md` was the model for every rule below, and its reviewer answers are applied here as precedent (Q5 get hides deleted rows, Q8/Q12 order, Q11 blank names at the schema, Q13 the 409 shows the submitted name). The rules are restated in full so this spec stands alone.
>
> **Below the manager:** `tests/unit/dao/delivery_method.spec.md` (APPROVED; soft delete, restore, the table) and `tests/unit/dao/base.spec.md` (`create`, `update`, `get_by_id_and_workspace`, `get_by_workspace`). **Above it:** `tests/unit/services/delivery_method_service.spec.md` (APPROVED). This spec takes the IDs that spec reserved for the manager (BUG-1523) and answers its FU-1 and delivery method DAO FU-1.
>
> **Read, not run.** The service spec ran the same code paths (create, delete, get of a deleted method, list, search) against `marker_test`; its results are the "Today" notes below where they apply.

## Review

### House-rule violations — applied automatically
- **HR-2** `_check_name_exists` R5 — only the first 100 delivery methods of the workspace (deleted included, no order) are checked for a duplicate name. Intended: every live method.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-1700 (pattern `capped-uniqueness-scan`).
- **HR-2** `_check_name_exists` R4 — names are compared with exact `==`: "Courier", "courier" and "Courier " all count as different. Intended: case-insensitive after trimming.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-1701 (pattern `unnormalised-uniqueness-compare`).
- **HR-2** `create_delivery_method` R6, `update_delivery_method` R11 — no database constraint backs the name check. Intended: partial unique index on live rows and the normalised name; a violation is 409.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-1219, already logged at the DAO (pattern `python-only-uniqueness`); no new ID. The manager half (409, not a database error) is stated here as department `create_department` R6.
- **HR-1** `create_delivery_method` R4, `update_delivery_method` R5, R8 — `DeliveryMethodCreate` / `DeliveryMethodUpdate` accept `""` and `"   "` and keep outer spaces. Intended: trimmed, blank refused with 422 at the schema.
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-1702 (pattern `blank-name-accepted`); fix in `app/schemas/delivery_method.py`.
- **HR-4** `get_delivery_method` R3, R4 — a soft-deleted method is returned by id. Intended: 404 by default, new `include_deleted=True` returns it.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-1523, already logged by the service spec for this manager; no new ID.
- **HR-5** `search_delivery_methods` R2, R4, R6 — `skip` / `limit` are applied first and deleted rows and the search are applied afterwards in Python, to that page only: pages come back short or empty, and a match on a later page is not found. Intended: filter, then page.
**Answer:** bug — per HR-5 (house rule)
**Resolution:** 🐞 BUG-1703 (pattern `paginate-before-filter`). One ID for both filters: one query fixes both.
- **HR-8** `search_delivery_methods` R6a — search text must stay literal. Holds today (Python substring); the BUG-1703 fix moves the search into SQL, where `%` and `_` must be escaped. Same fix as BUG-1703, no new ID; its tests are regression guards, not expected-to-fail.
**Answer:** bug — per HR-8 (house rule)
**Resolution:** logged against BUG-1703.
- **HR-6** `search_delivery_methods` R3 — no sort order. Intended: name case-insensitive ascending, then `id` ascending, before paging.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-1704 (pattern `unordered-pagination`).
- **HR-9** `update_delivery_method` R9 — `updated_by` is written on every successful update, an empty or unchanged one included. Intended: only when the name actually changes.
**Answer:** bug — per HR-9 (house rule)
**Resolution:** 🐞 BUG-1705 (pattern `audit-stamp-on-noop`).

Reached here, fixed elsewhere: **HR-4** list flag unreachable from the API — 🐞 BUG-1522, the service's and endpoint's (`search_delivery_methods` R5 is right as it stands). Not reached: BUG-730 (a deleted or foreign method chosen on a sales delivery) is the sales manager's.

Checked and **not** violated: **HR-3** — a name is not categorical free text. **HR-7** — `GET /delivery-methods/` enforces `1 <= limit <= 1000`, `skip >= 0` (service spec). **HR-10** — a rename or soft delete racing another does no harm (department spec G6). **HR-11 … HR-15** — no external system, batch or money. **HR-16** — every lookup is by the caller's workspace; nothing links to another row.

No questions.

## Overview
Business rules for delivery methods, the workspace's list of ways a sales delivery is shipped (Courier, Pickup, Own Fleet). Called only by `DeliveryMethodService` (which commits / rolls back), which the `/delivery-methods/` endpoints call. It protects workspace isolation, unique live names per workspace, and soft-delete semantics (a deleted method cannot be edited or deleted again). The manager never commits; the DAO flushes. A delete looks at no delivery: deliveries that name the method keep it (service spec `delete_delivery_method` R1).

Table `delivery_methods` (DAO spec): `name` NOT NULL, no length limit; `created_by` / `updated_by` / `deleted_by` nullable FKs to global `profiles.id`, never checked against workspace membership; `created_at` server default, `updated_at` `onupdate=now()`; `is_active` (default true), `is_deleted` (default false). No unique constraint today.

**Callables:** 6 specified · 2 not specified
**Externals to mock:** `utcnow` (`app.dao.delivery_method.utcnow`, used for `deleted_at`)
**Integration-only behavior:** none

**Notes for the test designer:**
- Import: `from app.managers.delivery_method_manager import DeliveryMethodManager, delivery_method_manager`; schemas `from app.schemas.delivery_method import DeliveryMethodCreate, DeliveryMethodUpdate`. All parameters positional-or-keyword.
- Setup, the concurrency simulation (patch `_check_name_exists` → `False`), `begin_nested` around a call expected to hit the database constraint, and the "at most one live row per normalised name" constraint on setups: exactly as the Notes of `department_manager.spec.md`.
- BUG-1523 R4 and BUG-1700 … BUG-1705: strict xfail. BUG-1219 R6 / R11: strict xfail (today the duplicate is saved). R6a: passes today, plain test.

## Not specified
- `DeliveryMethodManager.__init__` — wires the model and the DAO, no logic
- `delivery_method_manager` — module-level singleton, no logic

---

## `DeliveryMethodManager.create_delivery_method(session, delivery_method_data, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `DeliveryMethodService.create_delivery_method`)

**Purpose:** Create a delivery method in a workspace, refusing a name a live method there already has.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | open session; not committed here |
| delivery_method_data | DeliveryMethodCreate | `name: str`, required; trimmed, at least 1 character after trimming [BUG-1702] *(Today: no check)* |
| workspace_id | int | workspace the method is created in |
| user_id | int | stored as `created_by` |

**Returns:** the new `DeliveryMethod`, flushed (has an `id`), not committed.

**Rules:**
- **R1.** Given no live method of the workspace has the name, a method is created with `name`, `workspace_id`, `created_by = user_id`.
- **R2.** Given a live method of the same workspace has the name, 409 `Delivery method with name '<name>' already exists` is raised and nothing is created. `<name>` is the submitted name as received (trimmed by the schema), not the existing method's (department Q13 precedent). Detection follows `_check_name_exists` R1–R6.
- **R3.** The same name in another workspace, or on a soft-deleted method of this workspace, does not block creation (verified by the service spec: no constraint covers deleted rows).
- **R4.** [BUG-1702] (HR-1) A blank name (`""`, `"   "`) is refused by `DeliveryMethodCreate` itself (Pydantic `ValidationError`, 422 at the API); the manager is not reached. Any other name is stored trimmed, case and inner spaces kept (`" Own Fleet "` → `"Own Fleet"`). *(Today: stored exactly as given; `""` and `"   "` accepted.)*
- **R5.** The new row has `is_deleted = False`, `is_active = True`, and `updated_by`, `deleted_at`, `deleted_by` `None`.
- **R6.** [BUG-1219] (HR-2) If a live duplicate (normalised, per BUG-1701) reaches the insert past the Python check (a concurrent request), the database refuses it and 409 with the R2 message is raised, not a database error; nothing is created. A soft-deleted method does not count. *(Today: no constraint; the duplicate is saved.)* *(Requires a partial unique index on live rows and mapping the violation to 409.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| live method with the same name in the workspace (Python check or [BUG-1219] constraint) | `HTTPException` 409 | `Delivery method with name '<name>' already exists` |
| [BUG-1702] blank name | Pydantic `ValidationError` building `DeliveryMethodCreate` | not asserted |

**Side effects:** one `delivery_methods` row inserted and flushed. No commit.

---

## `DeliveryMethodManager.update_delivery_method(session, delivery_method_id, delivery_method_data, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `DeliveryMethodService.update_delivery_method`)

**Purpose:** Rename a live delivery method of the workspace.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | open session; not committed here |
| delivery_method_id | int | method to update |
| delivery_method_data | DeliveryMethodUpdate | `name: str \| None = None`; when given, trimmed and non-blank [BUG-1702] |
| workspace_id | int | caller's workspace |
| user_id | int | stored as `updated_by` (R9) |

**Returns:** the same `DeliveryMethod` instance, flushed, not committed.

**Rules:**
- **R1.** Unknown id → 404 `Delivery method with ID <id> not found`.
- **R2.** A method of another workspace → the same 404 as R1.
- **R3.** A soft-deleted method → 400 `Cannot update deleted delivery method`, nothing changes, whatever the input.
- **R4.** A non-blank `name` different from the current one, not used by another live method of the workspace → the name is changed.
- **R5.** [BUG-1702] `name` equal to the current name (after the schema's trimming: `" Courier "` when the name is `"Courier"`), or `None` / omitted → no duplicate check (no 409 possible) and the name is unchanged. *(Today: `""` also skips the check; `" Courier "` counts as a different name.)*
- **R6.** A non-blank `name` different from the current one that another live method of the workspace has → 409 `Delivery method with name '<name>' already exists` (submitted name, as `create_delivery_method` R2), nothing changes. Detection follows `_check_name_exists` R1–R6 with this method excluded.
- **R7.** `name` omitted or `null` → the name is unchanged.
- **R8.** [BUG-1702] (HR-1) `name` `""` or whitespace-only is refused by `DeliveryMethodUpdate` itself (Pydantic `ValidationError`, 422); a non-blank name is stored trimmed. *(Today: `""` blanks the name and succeeds.)*
- **R9.** [BUG-1705] (HR-9) `updated_by` is set to `user_id` only when the name actually changes. An empty body, `name: null`, or the current name → success, `updated_by` keeps its previous value. *(Today: set on every successful update.)*
- **R10.** No other field changes (`workspace_id`, `created_by`, `is_deleted`, `is_active` …).
- **R11.** [BUG-1219] (HR-2) A rename onto a live duplicate that gets past the Python check is refused by the database: 409 with the R6 message, nothing changes. *(Today: the duplicate rename is saved.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / another workspace | `HTTPException` 404 | `Delivery method with ID <delivery_method_id> not found` |
| soft-deleted | `HTTPException` 400 | `Cannot update deleted delivery method` |
| name taken by another live method | `HTTPException` 409 | `Delivery method with name '<name>' already exists` |
| [BUG-1702] blank name | Pydantic `ValidationError` building `DeliveryMethodUpdate` | not asserted |

**Side effects:** `name` (R4) and, when it changed, `updated_by` (R9) set and flushed; `updated_at` set by the database on flush. On error nothing is written.

---

## `DeliveryMethodManager.get_delivery_method(session, delivery_method_id, workspace_id, include_deleted=False)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `DeliveryMethodService.get_delivery_method`)

**Purpose:** One delivery method of the workspace by id.

**Inputs:** `include_deleted` — [BUG-1523] new, default `False`. *(Does not exist today.)*

**Returns:** the `DeliveryMethod`.

**Rules:**
- **R1.** A live method of the workspace is returned.
- **R2.** Unknown id, `0`, or a method of another workspace → 404 `Delivery method with ID <id> not found`.
- **R3.** [BUG-1523] (HR-4) A soft-deleted method with `include_deleted=False` (default) → the R2 404. *(Today: returned, no error. Verified by the service spec.)*
- **R4.** [BUG-1523] With `include_deleted=True` a soft-deleted method is returned; another workspace's method stays 404. *(Requires the new parameter.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / another workspace / deleted without `include_deleted` | `HTTPException` 404 | `Delivery method with ID <delivery_method_id> not found` |

**Side effects:** none

---

## `DeliveryMethodManager.search_delivery_methods(session, workspace_id, search=None, skip=0, limit=100, include_deleted=False)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `DeliveryMethodService.get_delivery_methods`, which passes `search`, `skip`, `limit`, never `include_deleted` — BUG-1522)

**Purpose:** The workspace's delivery methods, optionally filtered by a name substring.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| workspace_id | int | workspace to list |
| search | str \| None | case-insensitive substring of the name; `None` / `""` = no filter; not trimmed |
| skip | int | matching methods to skip; default 0 |
| limit | int | maximum returned; default 100 |
| include_deleted | bool | default `False` |

**Returns:** a list of `DeliveryMethod`, possibly empty.

**Rules:**
- **R1.** Only methods of `workspace_id` are returned.
- **R2.** [BUG-1703] (HR-5) Filters (R4–R6) are applied to all of the workspace's methods first; then `skip` matching methods are skipped and at most `limit` returned. A page has exactly `limit` items whenever at least `skip + limit` methods match. *(Today: the page is cut first, counting deleted and non-matching rows, and filtered afterwards; pages come back short or empty.)*
- **R3.** [BUG-1704] (HR-6) Ordered by name case-insensitive ascending, then `id` ascending, before paging; consecutive pages neither repeat nor skip a method. *(Today: no order.)*
- **R4.** [BUG-1703] With `include_deleted=False`, soft-deleted methods are never returned and take no place counted by `skip` / `limit`. *(Today: removed after paging.)*
- **R5.** With `include_deleted=True`, soft-deleted methods are kept. (Reaching it from the API is BUG-1522, the service's; this rule holds today.)
- **R6.** [BUG-1703] A non-empty `search` keeps only methods whose name contains it case-insensitively, across the whole workspace (`"our"` and `"COUR"` both find "Courier"). Whitespace in `search` counts. *(Today: only within the loaded page.)*
- **R6a.** (HR-8) `%` and `_` in `search` match only themselves (`"%"` finds only names containing `%`). *(Holds today; must keep holding once the BUG-1703 fix moves the search into SQL. Plain test, not xfail.)*
- **R7.** `search` `None` or `""` → no name filter.
- **R8.** No methods, none matching, or `skip` past the last match → `[]`.

**Errors:** none. Negative `skip` / `limit` raise as base DAO `get_by_workspace` (the API refuses them first).

**Side effects:** none

---

## `DeliveryMethodManager.delete_delivery_method(session, delivery_method_id, workspace_id, user_id)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `DeliveryMethodService.delete_delivery_method`)

**Purpose:** Soft-delete a live delivery method of the workspace.

**Returns:** the same `DeliveryMethod`, soft-deleted and flushed, not committed.

**Rules:**
- **R1.** Unknown id or another workspace's method → 404 `Delivery method with ID <id> not found`.
- **R2.** Already soft-deleted → 400 `Delivery method is already deleted`; `deleted_at` / `deleted_by` unchanged.
- **R3.** A live method becomes `is_deleted = True`, `deleted_at` = `utcnow()` (naive), `deleted_by = user_id` (delivery method DAO spec → department DAO `soft_delete`).
- **R4.** The row stays; `name`, `is_active`, `updated_by` and the other fields are unchanged. Sales deliveries naming the method are not looked at and keep it.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / another workspace | `HTTPException` 404 | `Delivery method with ID <delivery_method_id> not found` |
| already soft-deleted | `HTTPException` 400 | `Delivery method is already deleted` |

**Side effects:** `is_deleted`, `deleted_at`, `deleted_by` set and flushed. No commit.

---

## `DeliveryMethodManager._check_name_exists(session, workspace_id, name, exclude_id=None)`
**Shape:** validator
**Persistence:** reads
**Visibility:** internal (used by: `create_delivery_method`, `update_delivery_method`)

**Purpose:** Whether a live method of the workspace already uses a name.

**Returns:** `True` if a matching live method exists, else `False`.

**Rules:**
- **R1.** A live method of the workspace whose name matches (R4) → `True`.
- **R2.** The same name in another workspace → not considered.
- **R3.** A soft-deleted method with the name is ignored (unless a live one also matches).
- **R4.** [BUG-1701] (HR-2) Names match regardless of case and outer whitespace: with live `"Courier"`, each of `"courier"`, `"COURIER"`, `"Courier "`, `" Courier"` → `True`; `"Courier Express"` → `False`. *(Today: exact `==`.)*
- **R5.** [BUG-1700] (HR-2) Every live method of the workspace is examined, however many rows the workspace has; a match beyond the 100th row is found. *(Today: only the first 100 rows, deleted included, unordered.)*
- **R6.** `exclude_id` is ignored even if its name matches; a match with a different id still gives `True`. `exclude_id=None` ignores nothing.
- **R7.** No methods in the workspace → `False`.

**Errors:** none. **Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 39–46 | name exists → 409 / not → create | `create_delivery_method` R1, R2 |
| 48–52 | dump name + workspace_id + created_by; no normalisation | `create_delivery_method` R1, R4, R5 |
| — (no unique index) | duplicate past the Python check | `create_delivery_method` R6, `update_delivery_method` R11 |
| 68–75 | not found (incl. other workspace) → 404 | `update_delivery_method` R1, R2 |
| 77–81 | is_deleted → 400 | `update_delivery_method` R3 |
| 83 | `name` truthy and differs → check; else skip (None / "" / same) | `update_delivery_method` R4, R5 |
| 87–91 | exists (excluding self) → 409 | `update_delivery_method` R6 |
| 93 | `exclude_unset` / `exclude_none` drop omitted / null; "" kept | `update_delivery_method` R7, R8 |
| 94 | `updated_by` always set | `update_delivery_method` R9 |
| BaseDAO.update | only present keys set | `update_delivery_method` R10 |
| 110–118 | not found (incl. other workspace) → 404; no is_deleted check | `get_delivery_method` R1–R4 |
| 132–134 / BaseDAO.get_by_workspace | workspace filter, offset/limit, no ORDER BY | `search_delivery_methods` R1, R2, R3 |
| 136–137 | `include_deleted` false → drop deleted | `search_delivery_methods` R4, R5 |
| 139–144 | `search` truthy → substring; None / "" → none | `search_delivery_methods` R6, R6a, R7 |
| 137 / 141 | empty / one / many | `search_delivery_methods` R8 |
| 164–168 | not found (incl. other workspace) → 404 | `delete_delivery_method` R1 |
| 170–174 | already deleted → 400 | `delete_delivery_method` R2 |
| DAODeliveryMethod.soft_delete 28–33 | stamps, flush | `delete_delivery_method` R3, R4 |
| 189 / BaseDAO.get_by_workspace | first 100 rows, deleted included, unordered | `_check_name_exists` R2, R5 |
| 190 | loop empty / one / many | `_check_name_exists` R1, R7 |
| 191–192 | deleted → continue | `_check_name_exists` R3 |
| 193 | exact `==`; `exclude_id is None` / `id != exclude_id` | `_check_name_exists` R1, R4, R6 |
| 194–195 | True on first match / False after loop | `_check_name_exists` R1, R7 |
