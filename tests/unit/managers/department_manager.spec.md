# Spec — `app/managers/department_manager.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically
- **HR-8** `search_departments` R6a — search text must be literal (`%` and `_` match themselves). Today compliant (the filter is a Python substring test), but the BUG-007 fix moves the search into SQL (`ILIKE`), where the text must be escaped. Same fix as BUG-007 — log against it, no new ID.
**Answer:** bug — per HR-8 (house rule)
**Resolution:** logged against BUG-007 (same fix; Intended column now cites HR-8). `search_departments` R6a states the literal-search behavior; it holds today, so its tests are regression guards for the BUG-007 fix, not expected-to-fail.

### Q1. Duplicate-name check only looks at the first 100 departments — 🐞 BUG-001
**Background:** Before creating or renaming a department, the code loads the workspace's departments and checks their names in Python. The load is capped at 100 rows, has no sort order, and the 100 includes soft-deleted departments (deleting a department only sets `is_deleted = True`; the row stays).
**What happens today:** A name that belongs to a live department outside those first 100 rows is not detected, so a duplicate is created.
**Example:** Workspace has 120 departments (including 30 deleted ones). "Logistics" is row 110. A user creates another department named "Logistics" and gets 201 Created; the workspace now has two live "Logistics" departments.
**Rules affected:** `_check_name_exists` R5
**Answer:** bug
**Resolution:** duplicate detection must cover all live departments of the workspace. Rules: `_check_name_exists` R5.

### Q2. Duplicate-name check is case- and whitespace-sensitive — 🐞 BUG-002
**Background:** Names are compared with exact string equality. Names are not trimmed or normalised anywhere (schema or manager).
**What happens today:** "Sales", "sales" and "Sales " (trailing space) are all treated as different names.
**Example:** Workspace has a live department "Sales". A user creates "sales" and then "Sales " — both succeed; the dropdown now shows three departments that look like "Sales".
**Rules affected:** `_check_name_exists` R4
**Answer:** bug
**Resolution:** names are compared case-insensitively after trimming leading/trailing whitespace. Rules: `_check_name_exists` R4.

### Q3. Name uniqueness is not enforced by the database — 🐞 BUG-003
**Background:** The `departments` table has no unique constraint on `(workspace_id, name)`; uniqueness exists only as the Python check before insert.
**What happens today:** Two requests creating the same name at the same moment can both pass the check and both be saved.
**Example:** Two admins click "Create department: Finance" at the same time in the same workspace. Both get 201 Created; two live "Finance" departments exist.
**Rules affected:** `create_department` R2, `update_department` R6
**Answer:** bug
**Resolution:** the database enforces one live department per (normalised) name per workspace; a violation surfaces as 409. Rules: `create_department` R6 (new), `update_department` R11 (new).

### Q4. Blank department names are accepted — 🐞 BUG-004
**Background:** The create/update schemas declare `name: str` with no minimum length or trimming. On update, an empty string `""` is treated as "no name given" by the duplicate check, but it is still written to the row.
**What happens today:** Create accepts `""` and `"   "` as names. Update with `{"name": ""}` skips the duplicate check and sets the department's name to the empty string.
**Example:** A user sends `PUT /departments/5/ {"name": ""}`. Response is 200 with `"name": ""`; the department now shows as a blank entry in lists. Doing the same for a second department also succeeds, giving two departments both named "".
**Rules affected:** `create_department` R4, `update_department` R5, R8
**Answer:** bug
**Resolution:** blank and whitespace-only names are rejected by the `DepartmentCreate` / `DepartmentUpdate` schemas (validation error → 422 at the API), so the manager never receives one; names are stored trimmed (per Q11). Rules: `create_department` R4, `update_department` R5, R8.

### Q5. Getting a department by ID returns soft-deleted departments — 🐞 BUG-005
**Background:** Departments are soft-deleted (`is_deleted = True`, row stays). Update and delete reject a deleted department with 400; the list endpoint hides deleted departments.
**What happens today:** `get_department` returns a deleted department normally, with no indication beyond the model field (which the API response schema does not expose).
**Example:** Department 7 "Legacy" was deleted. `GET /departments/7/` returns 200 `{"id": 7, "name": "Legacy"}`, although it no longer appears in `GET /departments/` and `PUT /departments/7/` returns 400 "Cannot update deleted department".
**Rules affected:** `get_department` R3
**Answer:** bug — return only live departments by default (deleted → 404); add an `include_deleted` flag that returns soft-deleted ones when explicitly requested
**Resolution:** by default a soft-deleted department is reported as not found (404); with new parameter `include_deleted=True` it is returned. Rules: `get_department` R3, R4 (new).

### Q6. Deleted departments are removed from the list after paging, so pages come back short — 🐞 BUG-006
**Background:** The list loads one page (`skip`/`limit`) of all the workspace's departments — deleted ones included — and only afterwards drops the deleted ones in Python.
**What happens today:** A page can contain fewer than `limit` items, or none, even though more live departments exist on later pages.
**Example:** Workspace has 100 deleted departments (created first) and 10 live ones. `GET /departments/?limit=100` returns `[]`; the user sees "no departments" although 10 live ones exist.
**Rules affected:** `search_departments` R4
**Answer:** bug
**Resolution:** deleted departments are excluded before paging; `skip`/`limit` count only departments that can be returned. Rules: `search_departments` R2, R4.

### Q7. Name search only searches within the current page — 🐞 BUG-007
**Background:** Same mechanism as Q6: the search text is applied in Python to the one page already loaded, not to the whole workspace.
**What happens today:** A department whose name matches is not found if it is not in the loaded page.
**Example:** Workspace has 150 live departments; "Warehouse" is row 130. `GET /departments/?search=ware` (default limit 100) returns `[]`. With `skip=100` it would be found.
**Rules affected:** `search_departments` R6
**Answer:** bug
**Resolution:** the name search is applied across the whole workspace before paging. Rules: `search_departments` R2, R6.

### Q8. Department list has no sort order — 🐞 BUG-008
**Background:** The query that loads departments has no `ORDER BY`. Postgres returns rows in whatever order is convenient, which can change after updates.
**What happens today:** The order of the list, and which departments land on which page, is not guaranteed; paging with `skip` can repeat or skip departments.
**Example:** A user views page 1 (`skip=0, limit=50`), someone renames a department, the user fetches page 2 (`skip=50`) — one department appears on both pages and another on neither.
**Rules affected:** `search_departments` R3
**Answer:** bug
**Resolution:** the list is ordered by name, case-insensitive alphabetical, with `id` ascending as tie-breaker (per Q12). Rules: `search_departments` R3.

### Q9. Update records "updated by" even when nothing changed — 🐞 BUG-009
**Background:** `updated_by` is the audit field for the last editor.
**What happens today:** Every successful update sets `updated_by` to the caller — including an empty body `{}`, `{"name": null}`, or sending the current name unchanged. No field other than `updated_by` changes in those cases.
**Example:** User 42 opens department 5 "HR" and saves without edits (`{"name": "HR"}`). Response is 200; `updated_by` is now 42 although nothing was changed.
**Rules affected:** `update_department` R9
**Answer:** bug
**Resolution:** `updated_by` is set only when a field actually changes. Rules: `update_department` R9.

### Q10. The "include deleted" option on the list is unreachable — 🐞 BUG-010
**Background:** `search_departments` has an `include_deleted` flag (default off). The service and the API endpoint never pass it.
**What happens today:** No API caller can list deleted departments; the flag is only reachable from code.
**Example:** An admin wanting to see or restore deleted departments has no endpoint for it; `GET /departments/` always hides them.
**Rules affected:** `search_departments` R5
**Answer:** bug — expose `include_deleted` on the list API (service + endpoint), consistent with the `include_deleted` flag on get (Q5)
**Resolution:** the manager already behaves correctly; the fix belongs in `DepartmentService` and the `GET /departments/` endpoint, which must accept and pass `include_deleted`. Rules: `search_departments` R5 (manager rule unchanged; tagged for traceability).

### Q11. Blank names: where is the rejection, and what error? (follow-up to Q4) — 🐞 BUG-004
**Background:** You confirmed blank names (`""`, `"   "`) are a bug. There are two reasonable fixes with different observable errors: (a) validate in the Pydantic schemas (`DepartmentCreate` / `DepartmentUpdate`, e.g. strip whitespace + `min_length=1`) — the API returns **422** and the manager is never reached with a blank name; or (b) validate in the manager — it raises `HTTPException` **400** (e.g. "Department name cannot be blank"). A related choice: should names be stored trimmed (`" Sales "` saved as `"Sales"`)?
**Example:** `POST /departments/ {"name": "   "}` → with (a) a 422 validation error from FastAPI; with (b) 400 "Department name cannot be blank". Either way no department is created. Please answer (a) or (b), and whether names are stored trimmed.
**Rules affected:** `create_department` R4, `update_department` R5, R8
**Answer:** (a) — validate in the Pydantic schemas (422) so every entry point gets it; names are stored trimmed
**Resolution:** `DepartmentCreate.name` and `DepartmentUpdate.name` strip leading/trailing whitespace and require at least 1 character after stripping; blank input raises a Pydantic `ValidationError` (422 at the API). Names reach the manager, and are stored, trimmed. Fix belongs in `app/schemas/department.py` (not `DepartmentBase`, which `DepartmentResponse` also inherits). Rules: `create_department` R4, `update_department` R5, R8.

### Q12. Which sort order should the department list use? (follow-up to Q8) — 🐞 BUG-008
**Background:** You confirmed the list needs a defined order. Options: by `name` (alphabetical, case-insensitive, `id` as tie-breaker — friendliest for dropdowns), by `id` ascending (creation order, fully stable), or by `created_at` descending (newest first, `id` as tie-breaker).
**Example:** Departments created in order "Sales" (id 1), "Accounting" (id 2), "HR" (id 3): by name → Accounting, HR, Sales; by id → Sales, Accounting, HR; newest first → HR, Accounting, Sales.
**Rules affected:** `search_departments` R3
**Answer:** by name — alphabetical, case-insensitive, `id` as tie-breaker
**Resolution:** order by `lower(name)` ascending, then `id` ascending. Rules: `search_departments` R3.

### New questions

### Q13. Which name does the "already exists" message show when the match is only by case/spacing? — ✅ intended
**Background:** Per Q2 (BUG-002), duplicate detection ignores case and leading/trailing spaces, and per Q11 the submitted name is trimmed by the schema before it reaches the manager. The 409 message has the form `Department with name '<name>' already exists`. Today the code puts the *submitted* name into the message.
**What happens today:** Case-only matches are not detected at all (BUG-002), so no message is shown. Once fixed, the message would show the submitted (trimmed) name, not the name of the department that already exists.
**Example:** Workspace has a live department "Sales". A user creates `" sales "`. After the fixes, they get 409 with either (a) `Department with name 'sales' already exists` (what they typed, trimmed) or (b) `Department with name 'Sales' already exists` (the existing department's name, which is what they will find in the list).
**Suggested answer:** (a) — the submitted name after trimming; it is what the code does today and needs no extra lookup. The same applies to rename (409 on update) and to the database-level 409 (BUG-003), where the existing name is not at hand.
**Rules affected:** `create_department` R2, R6; `update_department` R6, R11; Errors tables of both
**Answer:** intended — the message shows the submitted name after trimming (e.g. `Department with name 'sales' already exists`), as today
**Resolution:** the 409 detail shows the submitted name as received by the manager (trimmed by the schema), never the existing department's name — for the Python check and the database-level 409 alike. Rules: `create_department` R2, R6; `update_department` R6, R11; Errors tables of both.

## Overview
Business rules for departments, the organisational units of a workspace. Called only by `DepartmentService` (which commits/rolls back), which is called by the `/departments` endpoints. It is meant to protect: workspace isolation (a department is only visible/editable from its own workspace), unique live department names per workspace, and soft-delete semantics (deleted departments cannot be edited or deleted again). The manager never commits; the DAO flushes.

`created_by`, `updated_by` and `deleted_by` are nullable foreign keys to `profiles.id`. Profiles are global (not workspace-scoped; workspace membership lives in the separate `workspace_members` table), and the manager never checks that the user belongs to the workspace — any existing profile id satisfies the constraint. `workspace_id` is a non-null foreign key to `workspaces.id`.

**Notes for the test designer:**
- Setup needs real `profiles` rows for every user id written to `created_by`/`updated_by`/`deleted_by` (FK); `workspace_members` rows are not needed by this manager.
- To simulate a concurrent request that passed the Python duplicate check (`create_department` R6, `update_department` R11), patch `DepartmentManager._check_name_exists` to return `False`; this is the accepted way to reach the database constraint from a unit test.
- A direct duplicate insert/rename that violates the intended unique index raises `sqlalchemy.exc.IntegrityError` on flush.
- For cases where the manager is expected to raise 409 from the database constraint, wrap the manager call itself in `session.begin_nested()` inside the test (`with pytest.raises(HTTPException): with session.begin_nested(): ...`), so the session is usable for the "nothing created/changed" re-read regardless of whether the fix uses its own savepoint. Do not assert on the session's state as left by the manager after the error.
- Two live departments with the same normalised name in one workspace cannot exist once BUG-003 is fixed; setups needing equal names must make all but one of them soft-deleted.

**Callables:** 6 specified · 1 not specified
**Externals to mock:** `utcnow` (`app.dao.department.utcnow`, used for `deleted_at`)
**Integration-only behavior:** none (the `updated_at` `onupdate=now()` and `created_at` `server_default` are set by the database on flush and are observable in tests)

## Not specified
- `DepartmentManager.__init__` — wires the `Department` model and the department DAO, no logic

---

## `DepartmentManager.create_department(session, department_data, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public

**Purpose:** Create a department in a workspace, rejecting a name already used by a live department there.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | Open DB session; not committed here |
| department_data | DepartmentCreate | `name: str`, required; stripped of leading/trailing whitespace, min length 1 after stripping [BUG-004] *(Today: no length, blank, or trim validation)* |
| workspace_id | int | Workspace the department is created in |
| user_id | int | Creator; stored as `created_by` (FK to `profiles.id`; not checked against workspace membership) |

**Returns:** The new `Department`, added to the session and flushed (has an `id`), not committed.

**Rules:**
- **R1.** Given no live department in the workspace has this name, a department is created with `name` = the given name, `workspace_id` = the given workspace, `created_by` = `user_id`.
- **R2.** Given a live department in the same workspace has the same name, 409 `Department with name '<name>' already exists` is raised (`<name>` = the submitted name as received, i.e. trimmed by the schema — not the existing department's name) and nothing is created — duplicate detection follows `_check_name_exists` R1–R6. ✅
- **R3.** A department with the same name in another workspace, or a soft-deleted one in the same workspace, does not block creation (see `_check_name_exists` R2, R3).
- **R4.** [BUG-004] A blank name (empty string `""` or whitespace-only such as `"   "`) is rejected by `DepartmentCreate` itself: constructing it raises a Pydantic `ValidationError` (422 at the API), so the manager is never reached and nothing is created. Any other name has leading/trailing whitespace stripped by the schema and is stored trimmed, without case change (`" Sales "` → stored `"Sales"`; inner whitespace kept). *(Today: the name is stored exactly as given and `""` / `"   "` are accepted.)* *(Fix belongs in `DepartmentCreate` in `app/schemas/department.py`.)*
- **R5.** The new row has `is_deleted = False`, `is_active = True` (model defaults applied on flush), and `updated_by`, `deleted_at`, `deleted_by` unset (`None`).
- **R6.** [BUG-003] The database itself rejects a second live department with the same (normalised, per BUG-002) name in the same workspace; if such a duplicate reaches the insert (the Python check was passed, e.g. by a concurrent request), 409 `Department with name '<name>' already exists` is raised rather than an unhandled database error, and nothing is created. A soft-deleted department does not count. *(Today: no database constraint exists; a duplicate that passes the Python check is saved.)* *(Requires a new partial unique index on live rows and mapping of the integrity error to 409.)* `<name>` is the submitted (trimmed) name, as in R2. ✅

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Live department with the same name exists in workspace | `HTTPException` 409 | `Department with name '<name>' already exists` — `<name>` is the submitted name (trimmed by the schema), not the existing department's name (Q13); same message for the database-level violation [BUG-003] |
| Blank / whitespace-only name [BUG-004] | Pydantic `ValidationError` when building `DepartmentCreate` (422 at the API); manager not reached | Pydantic's message (not asserted) |

**Side effects:** One `departments` row inserted and flushed with the fields in R1/R5. No commit.

---

## `DepartmentManager.update_department(session, department_id, department_data, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public

**Purpose:** Rename a live department of the workspace and record who edited it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | Open DB session; not committed here |
| department_id | int | Department to update |
| department_data | DepartmentUpdate | `name: str \| None = None`; when given, stripped of leading/trailing whitespace, min length 1 after stripping [BUG-004] *(Today: no length/blank/trim validation)* |
| workspace_id | int | Caller's workspace; department must belong to it |
| user_id | int | Editor; stored as `updated_by` (FK to `profiles.id`; not checked against workspace membership) |

**Returns:** The same `Department` instance, modified and flushed, not committed.

**Rules:**
- **R1.** Given no department with this id exists, 404 is raised.
- **R2.** Given the department exists but belongs to another workspace, 404 is raised (same as not existing).
- **R3.** Given the department is soft-deleted, 400 "Cannot update deleted department" is raised and nothing changes, regardless of the input.
- **R4.** Given a non-blank `name` different from the current name, and no other live department in the workspace has that name, the name is changed to it.
- **R5.** [BUG-004] Given `name` equal to the current name (after the schema's trimming, e.g. `" HR "` when the current name is `"HR"`), or `None`/omitted, no duplicate check is performed (so no 409 is possible) and the name is unchanged. A blank `name` never reaches the manager (R8). *(Today: `""` also skips the duplicate check and is accepted; untrimmed input such as `" HR "` is treated as a different name.)*
- **R6.** Given a non-blank `name` different from the current name that another live department in the workspace already has, 409 `Department with name '<name>' already exists` is raised (`<name>` = the submitted name as received, i.e. trimmed by the schema — not the existing department's name) and nothing changes — duplicate detection follows `_check_name_exists` R1–R6 (the department itself is excluded). ✅
- **R7.** Given `name` omitted or explicitly `null`, the name is left unchanged.
- **R8.** [BUG-004] Given `name` = `""` or a whitespace-only string, `DepartmentUpdate` itself rejects it: constructing it raises a Pydantic `ValidationError` (422 at the API), the manager is never reached and nothing changes. A non-blank `name` is stripped of leading/trailing whitespace by the schema and stored trimmed (`" Ops "` → `"Ops"`). *(Today: `""` sets the name to the empty string and the update succeeds; names are stored untrimmed.)* *(Fix belongs in `DepartmentUpdate` in `app/schemas/department.py`.)*
- **R9.** [BUG-009] `updated_by` is set to `user_id` only when the update actually changes a field (i.e. `name` is given and differs from the current name). Given an empty body, `name` = `null`, or `name` equal to the current name, the update succeeds and `updated_by` keeps its previous value. *(Today: `updated_by` is set to `user_id` on every successful update, including no-op ones.)*
- **R10.** No other fields (`workspace_id`, `created_by`, `is_deleted`, etc.) are modified.
- **R11.** [BUG-003] Renaming to a name that another live department in the workspace already has is rejected by the database as well; if such a duplicate reaches the flush (the Python check was passed, e.g. by a concurrent request), 409 `Department with name '<name>' already exists` is raised rather than an unhandled database error, and nothing changes. *(Today: no database constraint exists; the duplicate rename is saved.)* *(Requires a new partial unique index on live rows and mapping of the integrity error to 409.)* `<name>` is the submitted (trimmed) name, as in R6. ✅

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Not found / other workspace | `HTTPException` 404 | `Department with ID <department_id> not found` |
| Department is soft-deleted | `HTTPException` 400 | `Cannot update deleted department` |
| New name taken by another live department | `HTTPException` 409 | `Department with name '<name>' already exists` — `<name>` is the submitted name (trimmed by the schema), not the existing department's name (Q13); same message for the database-level violation [BUG-003] |
| Blank / whitespace-only name [BUG-004] | Pydantic `ValidationError` when building `DepartmentUpdate` (422 at the API); manager not reached | Pydantic's message (not asserted) |

**Side effects:** On success the row's `name` (per R4/R7) and, when something changed, `updated_by` (R9) are set and flushed. No commit. On error, nothing is written.

---

## `DepartmentManager.get_department(session, department_id, workspace_id, include_deleted=False)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public

**Purpose:** Fetch one department of the workspace by id.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | Open DB session |
| department_id | int | Department to fetch |
| workspace_id | int | Caller's workspace |
| include_deleted | bool | [BUG-005] Default `False`; `True` also returns soft-deleted departments. *(Does not exist today — requires new parameter `include_deleted`.)* |

**Returns:** The `Department`.

**Rules:**
- **R1.** Given a live department with this id in the workspace, it is returned.
- **R2.** Given no department with this id, or it belongs to another workspace, 404 is raised.
- **R3.** [BUG-005] Given the department is soft-deleted and `include_deleted` is `False` (default), 404 `Department with ID <department_id> not found` is raised. *(Today: the soft-deleted department is returned with no error.)*
- **R4.** [BUG-005] Given the department is soft-deleted and `include_deleted` is `True`, it is returned. A department of another workspace still raises 404 regardless of `include_deleted`. *(Requires new parameter `include_deleted`.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Not found / other workspace / soft-deleted without `include_deleted` | `HTTPException` 404 | `Department with ID <department_id> not found` |

**Side effects:** none

---

## `DepartmentManager.search_departments(session, workspace_id, search=None, skip=0, limit=100, include_deleted=False)`
**Shape:** list
**Persistence:** reads
**Visibility:** public

**Purpose:** List the workspace's departments, optionally filtered by a name substring.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | Open DB session |
| workspace_id | int | Workspace to list |
| search | str \| None | Case-insensitive substring of the name; `None` or `""` = no filter; not trimmed |
| skip | int | Number of matching departments to skip before the page; default 0 (API enforces ≥ 0) |
| limit | int | Maximum number of departments returned; default 100 (API enforces 1–1000) |
| include_deleted | bool | Default `False`; must be exposed by the service/API [BUG-010] (today never passed) |

**Returns:** A list of `Department` (possibly empty).

**Rules:**
- **R1.** Only departments of `workspace_id` are returned; departments of other workspaces never appear.
- **R2.** [BUG-006][BUG-007] Filtering (R4–R6) is applied to all of the workspace's departments first; then the first `skip` matching departments are skipped and at most `limit` are returned. A page therefore has exactly `limit` items whenever at least `skip + limit` matching departments exist. *(Today: a page of `limit` rows is taken after skipping `skip`, counting deleted and non-matching departments alike, and filtering is applied only to that page, so results can be short or empty.)*
- **R3.** [BUG-008] Results are ordered by name, case-insensitive alphabetical, then by `id` ascending for equal names (ignoring case); ordering is applied before `skip`/`limit`, so consecutive pages neither repeat nor skip departments. Example with `include_deleted=True`: deleted "sales" (id 1), live "Accounting" (id 2), live "HR" (id 3), live "Sales" (id 4) → Accounting, HR, sales (1), Sales (4). (Equal names ignoring case can only coexist when at most one is live — BUG-003.) *(Today: no sort key; order is undefined.)*
- **R4.** [BUG-006] Given `include_deleted` is `False` (default), soft-deleted departments are never returned and do not occupy positions counted by `skip`/`limit`. *(Today: they are removed only after paging.)*
- **R5.** [BUG-010] Given `include_deleted` is `True`, soft-deleted departments are kept. This must be reachable from the list API (`DepartmentService` + `GET /departments/`); the manager behavior itself is correct. *(Today: the service and endpoint never pass the flag.)*
- **R6.** [BUG-007] Given a non-empty `search`, only departments whose name contains `search` case-insensitively are returned, searched across the whole workspace (e.g. `"ale"` matches `"Sales"`; `"SALES"` matches `"sales team"`). Whitespace in `search` is significant. *(Today: the search is applied only within the already-loaded page.)*
- **R6a.** (HR-8) Search text is literal: `%` and `_` in `search` match only those characters (e.g. `search="%"` returns only departments whose name contains `%`; `search="_"` only those containing `_`). *(Today: holds — the filter is a Python substring test. It must keep holding when the BUG-007 fix moves the search into SQL `ILIKE`, which needs escaping. Tests for this rule pass today; they are regression guards for the BUG-007 fix, not expected-to-fail.)*
- **R7.** Given `search` is `None` or `""`, no name filter is applied.
- **R8.** Given the workspace has no departments, or none match the filters (or `skip` is past the last match), an empty list is returned.

**Errors:** none

**Side effects:** none

---

## `DepartmentManager.delete_department(session, department_id, workspace_id, user_id)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public

**Purpose:** Soft-delete a live department of the workspace.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | Open DB session; not committed here |
| department_id | int | Department to delete |
| workspace_id | int | Caller's workspace |
| user_id | int | Deleter; stored as `deleted_by` (FK to `profiles.id`; not checked against workspace membership) |

**Returns:** The same `Department` instance, soft-deleted and flushed, not committed.

**Rules:**
- **R1.** Given no department with this id, or it belongs to another workspace, 404 is raised.
- **R2.** Given the department is already soft-deleted, 400 "Department is already deleted" is raised and its `deleted_at`/`deleted_by` are unchanged.
- **R3.** Given a live department, it becomes `is_deleted = True`, `deleted_at` = current UTC time (naive datetime, from `utcnow`), `deleted_by` = `user_id`.
- **R4.** The row is not removed; `name`, `updated_by`, `is_active` and other fields are unchanged.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Not found / other workspace | `HTTPException` 404 | `Department with ID <department_id> not found` |
| Already soft-deleted | `HTTPException` 400 | `Department is already deleted` |

**Side effects:** Sets `is_deleted`, `deleted_at`, `deleted_by` on the row and flushes. No commit.

---

## `DepartmentManager._check_name_exists(session, workspace_id, name, exclude_id=None)`
**Shape:** validator
**Persistence:** reads
**Visibility:** internal (used by: `create_department`, `update_department`)

**Purpose:** Tell whether a live department in the workspace already uses a name.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| session | Session | Open DB session |
| workspace_id | int | Workspace to check |
| name | str | Name to look for; compared case-insensitively, ignoring leading/trailing whitespace [BUG-002] |
| exclude_id | int \| None | Department id to ignore (the one being renamed); `None` = ignore none |

**Returns:** `True` if a matching live department exists, else `False`.

**Rules:**
- **R1.** Given a live department in the workspace whose name equals `name` (per R4), returns `True`.
- **R2.** A department with the same name in another workspace is not considered → `False`.
- **R3.** A soft-deleted department with the same name is ignored → `False` (unless another live one matches).
- **R4.** [BUG-002] Names match regardless of case and leading/trailing whitespace: with a live `"Sales"`, each of `"sales"`, `"SALES"`, `"Sales "`, `" Sales"` → `True`. Inner differences still do not match (`"Sales Team"` vs `"Sales"` → `False`). *(Today: comparison is exact; any case or whitespace difference → `False`.)*
- **R5.** [BUG-001] Every live department of the workspace is examined, however many departments (live or deleted) the workspace has; a matching live department is found even when the workspace has more than 100 departments. *(Today: only the first 100 departments of the workspace, deleted included and in undefined order, are examined; a match outside them → `False`.)*
- **R6.** Given `exclude_id`, the department with that id is ignored even if its name matches; if the matching live department has a different id than `exclude_id`, the result is still `True`. With `exclude_id = None`, no department is ignored. (Only one live department per normalised name can exist per workspace — BUG-003 — so "still `True`" is tested with an `exclude_id` of some other department.)
- **R7.** Given the workspace has no departments, returns `False`.

**Errors:** none

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 53 | name exists → 409 / not → create | `create_department` R1, R2 |
| 60–62 | dump of name + workspace_id + created_by (no normalisation) | `create_department` R1, R4, R5 |
| — (no DB unique constraint) | duplicate past Python check | `create_department` R6, `update_department` R11 |
| 95 | department not found (incl. other workspace) → 404 | `update_department` R1, R2 |
| 102 | department is_deleted → 400 | `update_department` R3 |
| 109 | `name` truthy and differs from current → check; else skip (None / "" / same) | `update_department` R4, R5 |
| 113 | name exists (excluding self) → 409 | `update_department` R6 |
| 120 | `exclude_unset` / `exclude_none` drop omitted or null name; "" kept | `update_department` R7, R8 |
| 121 | `updated_by` always set | `update_department` R9 |
| BaseDAO.update 113–115 | only keys present are set (`hasattr`) | `update_department` R10 |
| 150 | department not found (incl. other workspace) → 404 | `get_department` R1, R2 |
| — (no is_deleted check) | deleted department returned | `get_department` R3, R4 |
| 182 / BaseDAO.get_by_workspace 161–167 | workspace filter, offset/limit, no ORDER BY | `search_departments` R1, R2, R3 |
| 187 | `include_deleted` false → drop deleted | `search_departments` R4, R5 |
| 191 | `search` truthy → substring filter; None/"" → none | `search_departments` R6, R6a, R7 |
| 188 / 193 | comprehension over empty / one / many | `search_departments` R8 |
| 226 | department not found (incl. other workspace) → 404 | `delete_department` R1 |
| 233 | already deleted → 400 | `delete_department` R2 |
| DAODepartment.soft_delete 39–43 | sets is_deleted, deleted_at, deleted_by; flush | `delete_department` R3, R4 |
| 264 / BaseDAO.get_by_workspace | only first 100 of workspace, deleted included, unordered | `_check_name_exists` R2, R5 |
| 265 | loop over empty / one / many | `_check_name_exists` R7, R1 |
| 267 | deleted → continue | `_check_name_exists` R3 |
| 269 | exact `==` name match | `_check_name_exists` R1, R4 |
| 269 | `exclude_id is None` vs `department.id != exclude_id` | `_check_name_exists` R6 |
| 270 / 271 | return True on first match / False after loop | `_check_name_exists` R1, R7 |

## Gap log
- G1 (department_manager.cases.md gap 1) — Fact — Overview and `user_id` Inputs: `created_by`/`updated_by`/`deleted_by` are nullable FKs to global `profiles.id`; no workspace-membership check; setup note for the test designer.
- G2 (department_manager.cases.md gap 2) — Test mechanics — Notes for the test designer: patch `_check_name_exists` → `False` to simulate a concurrent request; constraint violation is `sqlalchemy.exc.IntegrityError`; wrap the manager call in `session.begin_nested()` so the re-read works regardless of the fix's savepoint handling.
- G3 (department_manager.cases.md gap 3) — Intent — new question Q13 (which name the 409 detail shows); Errors tables note the suggested answer (submitted, trimmed name) as pending.
- G4 (department_manager.cases.md gap 4) — Contradiction — `_check_name_exists` R6 reworded (the other match has a different id, not a second live same-name row); `search_departments` R3 example now uses a deleted "sales" with `include_deleted=True`; Notes for the test designer state the at-most-one-live-per-normalised-name constraint.
- G5 (department_manager.cases.md gap 5) — House rule not applied — new `search_departments` R6a (HR-8, literal `%`/`_`), Branch map updated, House-rule violation line added (pre-filled, same fix as BUG-007; passes today, regression guard for the fix).
- G6 (department_manager.cases.md revision 2 gap 6) — Intent (reviewer) — HR-10 does not apply: `update_department` and `delete_department` check `is_deleted` then change the row without a lock, and that is intended. HR-10 was narrowed to races that cause real harm (money, stock, approvals, duplicate side effects); a racing rename/soft delete can at worst overwrite an audit stamp. No lock rule, no case needed.
