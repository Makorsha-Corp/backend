# Spec — `app/managers/work_order_type_manager.py`

> **Status:** APPROVED (2026-11-04; no question — every item below is a house rule, logged)
> **Source commit:** e48a092

> **Family.** The code is `app/managers/department_manager.py` with the names changed: same checks, same order, same flow; only the messages differ ("Work order type …"). The approved `tests/unit/managers/department_manager.spec.md` was the model for every rule below, and its reviewer answers are applied here as precedent (Q5 get hides deleted rows, Q8/Q12 order, Q11 blank names at the schema, Q13 the 409 shows the submitted name). The rules are restated in full so this spec stands alone. **One real difference:** the table has a unique constraint, `uq_wo_type_workspace_name` on `(workspace_id, name)` over all rows, deleted included, case-sensitive (BUG-1214).
>
> **Below the manager:** `tests/unit/dao/work_order_type.spec.md` (APPROVED; soft delete, restore, the constraint, N1–N3) and `tests/unit/dao/base.spec.md`. **Above it:** `tests/unit/services/work_order_type_service.spec.md` (APPROVED). This spec takes the ID that spec reserved for the manager (BUG-1521) and answers its FU-1 and work order type DAO FU-1.
>
> **Order workflow.** A work order type is a reference table: a label on work orders and templates, and nothing here moves an order's state. Nothing below changes order workflow. Whether a deleted type may be chosen on new work orders is the owner's answered BUG-1228 (refused on new orders; existing orders keep theirs), a rule of the work order managers, not reached here.
>
> **Read, not run.** The service spec and the DAO spec ran these paths (create, duplicate 409, the deleted name's `IntegrityError`, delete, get of a deleted type, search) against `marker_test`; their results are the "Today" notes below where they apply.

## Review

### House-rule violations — applied automatically
- **HR-2** `_check_name_exists` R5 — only the first 100 types of the workspace (deleted included, no order) are checked for a duplicate name. Intended: every live type.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-1706 (pattern `capped-uniqueness-scan`).
- **HR-2** `_check_name_exists` R4 — names are compared with exact `==`: "Repair", "repair", "Repair " count as different (and the case-sensitive constraint stores them). Intended: case-insensitive after trimming.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-1707 (pattern `unnormalised-uniqueness-compare`).
- **HR-2** `create_work_order_type` R3, R6a, `update_work_order_type` R6a, R11 — the constraint counts soft-deleted rows and compares case-sensitively.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-1214, already logged at the DAO (pattern `unique-index-counts-soft-deleted`); no new ID.
- **HR-1** `create_work_order_type` R4, `update_work_order_type` R5, R8 — `WorkOrderTypeCreate` / `WorkOrderTypeUpdate` accept `""` and `"   "` and keep outer spaces. Intended: trimmed, blank refused with 422 at the schema.
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-1708 (pattern `blank-name-accepted`); fix in `app/schemas/work_order_type.py`.
- **HR-4** `get_work_order_type` R3, R4 — a soft-deleted type is returned by id. Intended: 404 by default, new `include_deleted=True` returns it.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-1521, already logged by the service spec for this manager; no new ID.
- **HR-5** `search_work_order_types` R2, R4, R6 — `skip` / `limit` first, then deleted rows and the search are dropped in Python from that page: short or empty pages, matches on later pages missed. Intended: filter, then page.
**Answer:** bug — per HR-5 (house rule)
**Resolution:** 🐞 BUG-1709 (pattern `paginate-before-filter`). One ID for both filters.
- **HR-8** `search_work_order_types` R6a — search text must stay literal. Holds today; the BUG-1709 fix moves it into SQL, where `%` and `_` must be escaped. Same fix, no new ID; regression guard, not expected-to-fail.
**Answer:** bug — per HR-8 (house rule)
**Resolution:** logged against BUG-1709.
- **HR-6** `search_work_order_types` R3 — no sort order. Intended: name case-insensitive ascending, then `id` ascending, before paging.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-1710 (pattern `unordered-pagination`).
- **HR-9** `update_work_order_type` R9 — `updated_by` is written on every successful update, an empty or unchanged one included. Intended: only when the name actually changes.
**Answer:** bug — per HR-9 (house rule)
**Resolution:** 🐞 BUG-1711 (pattern `audit-stamp-on-noop`).

Reached here, fixed elsewhere: **HR-4** list flag unreachable from the API — 🐞 BUG-1520, the service's and endpoint's (`search_work_order_types` R5 is right as it stands).

Checked and **not** violated: **HR-2** "409, never 500" — the constraint's violation already answers 409 at the API through the global `IntegrityError` handler, so `create_work_order_type` R6 keeps today's database error at the manager (unlike the delivery method manager, which has no constraint and takes department R6 with BUG-1219). **HR-3** — a name is not categorical free text. **HR-7** — `GET /work-order-types/` enforces `1 <= limit <= 1000`, `skip >= 0`. **HR-10** — a rename or soft delete racing another does no harm (department spec G6). **HR-11 … HR-15** — no external system, batch or money. **HR-16** — every lookup is by the caller's workspace.

No questions.

## Overview
Business rules for work order types, the user-defined kinds of work order of a workspace ("Repair", "Inspection"). Called only by `WorkOrderTypeService` (which commits / rolls back), which the `/work-order-types/` endpoints call. Work order and template managers read types through the DAO, not through this manager. It protects workspace isolation, unique live names per workspace, and soft-delete semantics. The manager never commits; the DAO flushes. A delete looks at no work order or template: those keep the type (`work_orders` and `work_order_templates` reference it `ON DELETE RESTRICT`, which a soft delete never triggers).

Table `work_order_types` (DAO spec): `name` NOT NULL, no length limit; `uq_wo_type_workspace_name` (above; not declared on the model); `created_by` / `updated_by` / `deleted_by` nullable FKs to global `profiles.id`; `created_at` server default, `updated_at` `onupdate=now()`; `is_active` (default true), `is_deleted` (default false).

**Callables:** 6 specified · 2 not specified
**Externals to mock:** `utcnow` (`app.dao.work_order_type.utcnow`, used for `deleted_at`)
**Integration-only behavior:** the global `IntegrityError` handler's 409 "This resource already exists".

**Notes for the test designer:**
- Import: `from app.managers.work_order_type_manager import WorkOrderTypeManager, work_order_type_manager`; schemas `from app.schemas.work_order_type import WorkOrderTypeCreate, WorkOrderTypeUpdate`. All parameters positional-or-keyword.
- Setup, the concurrency simulation (patch `_check_name_exists` → `False`) and `begin_nested` around a call that hits the constraint: as the Notes of `department_manager.spec.md`. A constraint violation is `sqlalchemy.exc.IntegrityError`, `.orig.pgcode == "23505"`, constraint `uq_wo_type_workspace_name`.
- **Setups with equal names:** today the constraint forbids two rows of one workspace with the exact same name, deleted or not. Setups needing "a deleted type named X and a live type named X" can only be built after BUG-1214; use different case or another workspace where a rule allows it, otherwise the case belongs to the BUG-1214 xfail.
- BUG-1521 R4 and BUG-1706 … BUG-1711: strict xfail. BUG-1214 rules: strict xfail (today `IntegrityError` or the case variant is stored). R6a: plain test.

## Not specified
- `WorkOrderTypeManager.__init__` — wires the model and the DAO, no logic
- `work_order_type_manager` — module-level singleton, no logic

---

## `WorkOrderTypeManager.create_work_order_type(session, type_data, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `WorkOrderTypeService.create_work_order_type`)

**Purpose:** Create a work order type in a workspace, refusing a name a live type there already has.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | open session; not committed here |
| type_data | WorkOrderTypeCreate | `name: str`, required; trimmed, at least 1 character after trimming [BUG-1708] *(Today: no check)* |
| workspace_id | int | workspace the type is created in |
| user_id | int | stored as `created_by` |

**Returns:** the new `WorkOrderType`, flushed (has an `id`), not committed.

**Rules:**
- **R1.** Given no live type of the workspace has the name, a type is created with `name`, `workspace_id`, `created_by = user_id`.
- **R2.** Given a live type of the same workspace has the name, 409 `Work order type '<name>' already exists` is raised and nothing is created. `<name>` is the submitted name as received (trimmed by the schema), not the existing type's (department Q13 precedent). Detection follows `_check_name_exists` R1–R6. (Verified by the service spec.)
- **R3.** [BUG-1214] (HR-2) A name carried only by soft-deleted types of the workspace can be used again: the type is created. *(Today: the Python check passes, then the insert raises `IntegrityError` 23505 on `uq_wo_type_workspace_name`. Verified.)*
- **R3a.** The same name in another workspace does not block creation.
- **R4.** [BUG-1708] (HR-1) A blank name (`""`, `"   "`) is refused by `WorkOrderTypeCreate` itself (Pydantic `ValidationError`, 422); the manager is not reached. Any other name is stored trimmed, case and inner spaces kept (`" Field Repair "` → `"Field Repair"`). *(Today: stored as given; `""` accepted once per workspace, then the constraint refuses a second `""`.)*
- **R5.** The new row has `is_deleted = False`, `is_active = True`, and `updated_by`, `deleted_at`, `deleted_by` `None`.
- **R6.** A live type of the exact same name that gets past the Python check (a concurrent request) is refused by the database: `IntegrityError` 23505 on `uq_wo_type_workspace_name`, nothing created; the API answers 409 through the global handler.
- **R6a.** [BUG-1214] (HR-2) The database also refuses a live name that differs only in case or outer spaces (`"Repair"` live, `"repair"` past the Python check) with the R6 error. *(Today: stored; the constraint is case-sensitive.)* Once BUG-1707 is fixed the Python check catches these first (R2); this rule is reached only past it.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| live type with the same name (Python check) | `HTTPException` 409 | `Work order type '<name>' already exists` |
| duplicate past the Python check (R6, R6a) | `sqlalchemy.exc.IntegrityError`, pgcode `23505` | constraint `uq_wo_type_workspace_name` |
| [BUG-1708] blank name | Pydantic `ValidationError` building `WorkOrderTypeCreate` | not asserted |

**Side effects:** one `work_order_types` row inserted and flushed. No commit.

---

## `WorkOrderTypeManager.update_work_order_type(session, type_id, type_data, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `WorkOrderTypeService.update_work_order_type`)

**Purpose:** Rename a live work order type of the workspace.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | open session; not committed here |
| type_id | int | type to update |
| type_data | WorkOrderTypeUpdate | `name: str \| None = None`; when given, trimmed and non-blank [BUG-1708] |
| workspace_id | int | caller's workspace |
| user_id | int | stored as `updated_by` (R9) |

**Returns:** the same `WorkOrderType` instance, flushed, not committed.

**Rules:**
- **R1.** Unknown id → 404 `Work order type with ID <type_id> not found`.
- **R2.** A type of another workspace → the same 404 as R1.
- **R3.** A soft-deleted type → 400 `Cannot update a deleted work order type`, nothing changes, whatever the input.
- **R4.** A non-blank `name` different from the current one, not used by another live type of the workspace → the name is changed. Work orders and templates of the type show the new name (they reference the row).
- **R5.** [BUG-1708] `name` equal to the current name (after the schema's trimming), or `None` / omitted → no duplicate check and the name is unchanged. *(Today: `""` also skips the check; `" Repair "` counts as a different name.)*
- **R6.** A non-blank `name` different from the current one that another live type of the workspace has → 409 `Work order type '<name>' already exists` (submitted name), nothing changes. Detection follows `_check_name_exists` R1–R6 with this type excluded.
- **R6a.** [BUG-1214] (HR-2) A name carried only by soft-deleted types of the workspace can be taken by a rename. *(Today: `IntegrityError` 23505 on flush.)*
- **R7.** `name` omitted or `null` → the name is unchanged.
- **R8.** [BUG-1708] (HR-1) `name` `""` or whitespace-only is refused by `WorkOrderTypeUpdate` itself (Pydantic `ValidationError`, 422); a non-blank name is stored trimmed. *(Today: `""` passes the manager and is stored unless another row of the workspace already has `""`.)*
- **R9.** [BUG-1711] (HR-9) `updated_by` is set to `user_id` only when the name actually changes. An empty body, `name: null`, or the current name → success, `updated_by` unchanged. *(Today: set on every successful update.)*
- **R10.** No other field changes.
- **R11.** A rename onto a live duplicate that gets past the Python check is refused by the database as `create_work_order_type` R6 / R6a (R6a's case variants only after BUG-1214), nothing changes.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / another workspace | `HTTPException` 404 | `Work order type with ID <type_id> not found` |
| soft-deleted | `HTTPException` 400 | `Cannot update a deleted work order type` |
| name taken by another live type | `HTTPException` 409 | `Work order type '<name>' already exists` |
| duplicate past the Python check | `IntegrityError` 23505 | `uq_wo_type_workspace_name` |
| [BUG-1708] blank name | Pydantic `ValidationError` building `WorkOrderTypeUpdate` | not asserted |

**Side effects:** `name` (R4) and, when it changed, `updated_by` (R9) set and flushed; `updated_at` set by the database. On error nothing is written.

---

## `WorkOrderTypeManager.get_work_order_type(session, type_id, workspace_id, include_deleted=False)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `WorkOrderTypeService.get_work_order_type`)

**Purpose:** One work order type of the workspace by id.

**Inputs:** `include_deleted` — [BUG-1521] new, default `False`. *(Does not exist today.)*

**Rules:**
- **R1.** A live type of the workspace is returned.
- **R2.** Unknown id, `0`, or a type of another workspace → 404 `Work order type with ID <type_id> not found`.
- **R3.** [BUG-1521] (HR-4) A soft-deleted type with `include_deleted=False` (default) → the R2 404. *(Today: returned. Verified by the service spec.)*
- **R4.** [BUG-1521] With `include_deleted=True` a soft-deleted type is returned; another workspace's type stays 404. *(Requires the new parameter.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / another workspace / deleted without `include_deleted` | `HTTPException` 404 | `Work order type with ID <type_id> not found` |

**Side effects:** none

---

## `WorkOrderTypeManager.search_work_order_types(session, workspace_id, search=None, skip=0, limit=100, include_deleted=False)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `WorkOrderTypeService.get_work_order_types`, which never passes `include_deleted` — BUG-1520)

**Purpose:** The workspace's work order types, optionally filtered by a name substring.

**Inputs:** as `DeliveryMethodManager.search_delivery_methods` (`search` case-insensitive substring, `None` / `""` = none, not trimmed; `skip` 0; `limit` 100; `include_deleted` `False`).

**Returns:** a list of `WorkOrderType`, possibly empty.

**Rules:**
- **R1.** Only types of `workspace_id` are returned.
- **R2.** [BUG-1709] (HR-5) Filters (R4–R6) are applied to all of the workspace's types first; then `skip` matching types are skipped and at most `limit` returned. A page has exactly `limit` items whenever at least `skip + limit` types match. *(Today: page cut first, filtered afterwards.)*
- **R3.** [BUG-1710] (HR-6) Ordered by name case-insensitive ascending, then `id` ascending, before paging. *(Today: no order.)*
- **R4.** [BUG-1709] With `include_deleted=False`, soft-deleted types are never returned and take no place counted by `skip` / `limit`. *(Today: removed after paging.)*
- **R5.** With `include_deleted=True`, soft-deleted types are kept. (Holds today; API reach is BUG-1520.)
- **R6.** [BUG-1709] A non-empty `search` keeps only types whose name contains it case-insensitively, across the whole workspace (`"pair"` and `"REPAIR"` find "Repair"; verified on a page). Whitespace in `search` counts. *(Today: only within the loaded page.)*
- **R6a.** (HR-8) `%` and `_` in `search` match only themselves (`"%"` finds nothing when no name contains `%`; verified). *(Holds today; must keep holding after the BUG-1709 fix. Plain test.)*
- **R7.** `search` `None` or `""` → no name filter.
- **R8.** No types, none matching, or `skip` past the last match → `[]`.

**Errors:** none. **Side effects:** none

---

## `WorkOrderTypeManager.delete_work_order_type(session, type_id, workspace_id, user_id)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `WorkOrderTypeService.delete_work_order_type`)

**Purpose:** Soft-delete a live work order type of the workspace.

**Returns:** the same `WorkOrderType`, soft-deleted and flushed, not committed.

**Rules:**
- **R1.** Unknown id or another workspace's type → 404 `Work order type with ID <type_id> not found`.
- **R2.** Already soft-deleted → 400 `Work order type is already deleted`; `deleted_at` / `deleted_by` unchanged.
- **R3.** A live type becomes `is_deleted = True`, `deleted_at` = `utcnow()` (naive), `deleted_by = user_id` (work order type DAO spec → department DAO `soft_delete`).
- **R4.** The row stays; `name`, `is_active`, `updated_by` and the other fields are unchanged. Work orders and templates of the type are not looked at and keep it; a type in use is deleted like any other (owner, BUG-1228: existing orders keep theirs).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / another workspace | `HTTPException` 404 | `Work order type with ID <type_id> not found` |
| already soft-deleted | `HTTPException` 400 | `Work order type is already deleted` |

**Side effects:** `is_deleted`, `deleted_at`, `deleted_by` set and flushed. No commit.

---

## `WorkOrderTypeManager._check_name_exists(session, workspace_id, name, exclude_id=None)`
**Shape:** validator
**Persistence:** reads
**Visibility:** internal (used by: `create_work_order_type`, `update_work_order_type`)

**Purpose:** Whether a live type of the workspace already uses a name.

**Returns:** `True` if a matching live type exists, else `False`.

**Rules:**
- **R1.** A live type of the workspace whose name matches (R4) → `True`.
- **R2.** The same name in another workspace → not considered.
- **R3.** A soft-deleted type with the name is ignored → `False` (unless a live one matches). (After BUG-1214 a live and a deleted row may share a name; before it, build the deleted row with a different case to test this.)
- **R4.** [BUG-1707] (HR-2) Names match regardless of case and outer whitespace: with live `"Repair"`, each of `"repair"`, `"REPAIR"`, `"Repair "`, `" Repair"` → `True`; `"Repair Urgent"` → `False`. *(Today: exact `==`.)*
- **R5.** [BUG-1706] (HR-2) Every live type of the workspace is examined, however many rows the workspace has; a match beyond the 100th row is found. *(Today: only the first 100 rows, deleted included, unordered.)*
- **R6.** `exclude_id` is ignored even if its name matches; a match with a different id still gives `True`. `exclude_id=None` ignores nothing.
- **R7.** No types in the workspace → `False`.

**Errors:** none. **Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 35–42 | name exists → 409 / not → create | `create_work_order_type` R1, R2, R3a |
| 44–48 | dump name + workspace_id + created_by; no normalisation | `create_work_order_type` R1, R4, R5 |
| constraint `uq_wo_type_workspace_name` | all rows, case-sensitive | `create_work_order_type` R3, R6, R6a; `update_work_order_type` R6a, R11 |
| 59–66 | not found (incl. other workspace) → 404 | `update_work_order_type` R1, R2 |
| 67–71 | is_deleted → 400 | `update_work_order_type` R3 |
| 73 | `name` truthy and differs → check; else skip | `update_work_order_type` R4, R5 |
| 77–81 | exists (excluding self) → 409 | `update_work_order_type` R6 |
| 83 | `exclude_unset` / `exclude_none`; "" kept | `update_work_order_type` R7, R8 |
| 84 | `updated_by` always set | `update_work_order_type` R9 |
| BaseDAO.update | only present keys set | `update_work_order_type` R10 |
| 91–98 | not found → 404; no is_deleted check | `get_work_order_type` R1–R4 |
| 111–113 / BaseDAO.get_by_workspace | workspace, offset/limit, no ORDER BY | `search_work_order_types` R1, R2, R3 |
| 114–115 | `include_deleted` false → drop deleted | `search_work_order_types` R4, R5 |
| 116–118 | `search` truthy → substring; None / "" → none | `search_work_order_types` R6, R6a, R7 |
| 115 / 118 | empty / one / many | `search_work_order_types` R8 |
| 125–132 | not found → 404 | `delete_work_order_type` R1 |
| 133–137 | already deleted → 400 | `delete_work_order_type` R2 |
| 138 / DAOWorkOrderType.soft_delete | stamps, flush | `delete_work_order_type` R3, R4 |
| 150 / BaseDAO.get_by_workspace | first 100 rows, deleted included, unordered | `_check_name_exists` R2, R5 |
| 151 | loop empty / one / many | `_check_name_exists` R1, R7 |
| 152–153 | deleted → continue | `_check_name_exists` R3 |
| 154 | exact `==`; `exclude_id` | `_check_name_exists` R1, R4, R6 |
| 155–156 | True on first match / False after loop | `_check_name_exists` R1, R7 |
