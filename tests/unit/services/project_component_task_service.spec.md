# Spec — `app/services/project_component_task_service.py`

> **Status:** APPROVED (2026-11-04; nothing open. Every item is a house rule or was decided by Claude under the reviewer's delegation (2026-11-04); no money, stock or order flow is involved.)
> **Source commit:** e48a092

> **Revision 2026-11-04 (fill-gaps, `project_component_task_service.cases.md` gaps 1–2).** Schema module and `TaskPriorityEnum` members named. No new bug, no question; stays APPROVED. See the Gap log.

> **Form.** As `tests/unit/services/department_service.spec.md`. **Below:** `tests/unit/managers/project_manager.spec.md` (`require_component_access`, `can_access_project`, `log_for_component`; Facts "Who may open a private project"), `tests/unit/dao/project_component_task.spec.md` (`get_by_component`, `get_incomplete_tasks`; Model facts), `tests/unit/dao/base.spec.md` (`get_by_workspace`: `id` order after BUG-100; `get_by_id_and_workspace`, `create`, `update`, `remove`: raw). All APPROVED; cited, not restated. This spec answers task DAO FU-1 (a)–(c) for the task service. The sibling `project_component_note_service.spec.md` handles the note pages.
>
> **Not a `BaseService`.** Own transaction rules T-TC1 … T-TC6 below (same outcomes as TC1–TC6 of `tests/unit/services/base_service.spec.md`, differences named).
>
> **Standing decisions applied here (not asked again):** BUG-1278 (a component of a deleted project → 404 through the guard; workspace-wide lists leave its rows out). OQ-18 (owner): 403 for a private project the caller may not open, kept.
>
> **Verified by running** (`v1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvc\forkB\`, one outer transaction rolled back against `marker_test`, private `COVERAGE_FILE`; nothing persisted): a task named `"  "` is created and logged `Added task "  "`; `PUT {}` logs `task_updated`; `{"task_priority": null}` leaves `HIGH` and logs `task_updated`; `{"is_note": true}` turns the task into a note with **no** event; `{"is_note": false}` back logs `task_updated`; `{"is_completed": true}` logs `task_completed`; the workspace-wide list with `incomplete_only=True, is_note=False` returned a note and a completed task; `project_component_id=0` listed the workspace; the task service deletes a note (no event); after the project's soft delete its task is still listed workspace-wide and a new task is created on its component. **Read, not run:** the endpoint.

## Review
> Nothing open. Overwrite a pre-filled answer only if the house rule or the delegated decision should not apply here.

### House-rule violations — applied automatically
- **HR-1** `create_task` R2, `update_task` R3 — `name` is plain `str` on create and update: `""` / `"  "` stored (verified). Intended: trimmed; blank refused by the schema (422).
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-2297 (pattern `blank-name-accepted`).
- **HR-5** `get_tasks` R5 — without a component, rows the caller may not see are dropped in Python **after** paging, two reads per row (task DAO FU-1 (b)). Intended: access filter in the query, before paging.
**Answer:** bug — per HR-5 (house rule)
**Resolution:** 🐞 BUG-2298 (pattern `paginate-before-filter`).
- **HR-6** `get_tasks` R4 — without a component the order is the base `id` order (BUG-100), while one component's list is by name (BUG-1447). Intended: `name` case-insensitive, then `id`, before paging.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2299 (pattern `hr-6-non-default-list-order`).
- **HR-7** `get_tasks` R8 — `GET /project-component-tasks/` declares `limit: Query(100, le=100)` with no lower bound (task DAO FU-1 (a)).
**Answer:** bug — per HR-7 (house rule)
**Resolution:** 🐞 BUG-2296 (pattern `missing-limit-lower-bound`; one bug with `GET /project-component-notes/`). Endpoint rule.

### Precedent matches — all applied (decided by Claude under the reviewer's delegation, 2026-11-04)

### P1. `project_component_id=0` lists the whole workspace — 🐞 BUG-2301
**Background:** `if project_component_id:` treats `0` like "no filter" (task DAO FU-1 (c)). Same as BUG-1959.
**What happens today:** `?project_component_id=0` returns the workspace-wide list (verified).
**Example:** A client sends `0` for "no component chosen" and gets every task of every visible project.
**Rules affected:** `get_tasks` R1
**Answer:** bug — per BUG-1959 precedent: only `None` means "no component"; `0` goes through the guard and answers 404 `Project component not found` (as the note service does today).
**Resolution:** 🐞 BUG-2301 (pattern `falsy-zero-treated-as-missing`).

### P2. Saving a task unchanged writes "Updated task" — 🐞 BUG-2303
**Background:** Every successful update of a task writes one project event. Same root cause as BUG-632 / BUG-2118.
**What happens today:** `PUT {}` and `{"task_priority": null}` log `task_updated` (verified).
**Example:** The task dialog is saved without edits; the activity tab shows "Updated task 'Weld frame'".
**Rules affected:** `update_task` R6
**Answer:** bug — per BUG-632 precedent: no value changed → no event; the task is returned as usual.
**Resolution:** 🐞 BUG-2303 (pattern `audit-event-on-noop`).

### P3. A task's priority cannot be cleared — 🐞 BUG-2304
**Background:** An update drops every `null` (`exclude_none`). Same root cause as BUG-942 / BUG-1953.
**What happens today:** `{"task_priority": null}` leaves `HIGH` (verified).
**Example:** Ana removes the priority of "Order bolts"; it still shows High.
**Rules affected:** `update_task` R2a
**Answer:** bug — per BUG-1953 precedent: explicit `null` clears `task_priority`; `null` for `name`, `description`, `is_completed`, `is_note` is refused by `ProjectComponentTaskUpdate` (422); omitted fields unchanged.
**Resolution:** 🐞 BUG-2304 (pattern `exclude-none-blocks-clear`).

### P4. Tasks of a deleted project stay on the workspace-wide list — 🐞 BUG-2302
**Background:** As note service D3; per BUG-1278.
**What happens today:** listed (verified).
**Example:** Project "Line 3" is deleted; its open tasks still appear on a workspace-wide task view.
**Rules affected:** `get_tasks` R6
**Answer:** bug — per BUG-1278 precedent: not listed, no place on the page; rows untouched.
**Resolution:** 🐞 BUG-2302 (pattern `join-ignores-soft-deleted`).

### New items

### D1. Without a component, "open only" and "notes / tasks" are ignored — 🐞 BUG-2300
**Background:** `incomplete_only` and `is_note` are applied only when a component is given.
**What happens today:** `GET /project-component-tasks/?incomplete_only=true&is_note=false` returned a note and a completed task (verified).
**Example:** A "my open tasks" view across projects shows finished tasks and notes.
**Rules affected:** `get_tasks` R3
**Answer:** bug — both filters apply on the workspace-wide list too, in the query, before paging, with the same meaning as for one component (`incomplete_only` with `is_note` omitted → open tasks only).
**Resolution:** 🐞 BUG-2300 (pattern `silently-ignored-input`, as BUG-1960).

### D2. Turning a task into a note leaves no trace in the activity log — 🐞 BUG-2305
**Background:** `is_note` may be changed by `PUT`. The event is chosen by the row's kind **after** the update, and notes are not logged here.
**What happens today:** `{"is_note": true}` writes no event; the task vanishes from the task list. `{"is_note": false}` writes `task_updated` (verified).
**Example:** A task "Inspect weld" is converted to a note by an API client; the project's log never shows it left the task list.
**Rules affected:** `update_task` R5
**Answer:** bug — an update of a row that was a task **before** the update is logged as for a task (`task_updated`, or `task_completed` / `task_reopened`), even when it becomes a note. A row that was and stays a note writes nothing here.
**Resolution:** 🐞 BUG-2305 (pattern `audit-event-missing-on-change`).

### D3. Notes created or deleted through the task pages are not logged — ✅ intended
**Background:** The task service writes events only for tasks (`if not task.is_note`), on purpose; notes are logged by the note service. The web app creates notes only through `/project-component-notes/`.
**What happens today:** `POST /project-component-tasks/` with `is_note: true` creates a note with no event; `DELETE` of a note id through the task pages deletes it with no event (verified).
**Answer:** intended — the task pages are the general endpoint and log tasks only (decided by Claude under the reviewer's delegation (2026-11-04)). Rules `create_task` R4 ✅, `delete_task` R2 ✅.

Checked and **not** violated: **HR-2** — task names need not be unique. **HR-3, HR-8** — no grouping, no `LIKE`. **HR-4** — tasks have no soft delete; deleted project: BUG-1278 / P4. **HR-9** — no audit stamps on the table; events: P2, D2. **HR-10** — completing a task is not money, stock or an approval. **HR-15** — no money. **HR-16** — the component is found in the caller's workspace (guard); `ProjectComponentTaskUpdate` has no `project_component_id`, so a task cannot be moved to another (or another workspace's, or a private project's) component; a stored row on another workspace's component is skipped by the workspace-wide list and answers 404 by id.

**Permission checks:** only `require_component_access`. Any member who may open the project may add, edit, complete, reopen and delete tasks. Recorded for the permissions feature, not asked.

## Overview
`ProjectComponentTaskService` is the transaction boundary for tasks (and, through the same table, notes) on a project component. The `/project-component-tasks/` endpoints call it. It checks access through `ProjectManager`, writes through the base DAO, logs project events for tasks, and commits.

**Callables:** 7 specified · 1 not specified
**Externals to mock:** none.
**Integration-only behavior:** the endpoints' 404 `Project component task not found` for `None` / `False`; query bounds (BUG-2296); schema validation (400 today, BUG-461).

### Transaction rules (T-TC) — this service's writes
As N-TC1–N-TC6 of `project_component_note_service.spec.md`, for `create_task`, `update_task`, `delete_task` and the reads `get_tasks`, `get_by_id`: committed on success (T-TC1); create and update re-read (T-TC2), delete returns `True` with no re-read; any exception in the `try` → one rollback, same object, pending changes discarded (T-TC3); failing commit → one rollback, its exception (T-TC4); failing re-read → saved (T-TC5); reads, and an update / delete that finds nothing (`None` / `False`), neither commit nor roll back (T-TC6).

**Facts for the test designer**
- Import: `from app.services.project_component_task_service import ProjectComponentTaskService, project_component_task_service`. No constructor arguments.
- Guard errors: project manager `require_component_access` R1–R4 (404 `Project component not found`, 404 `Project with ID <id> not found`, 403 `You do not have access to this project`).
- Event metadata: `{"task_id", "task_name"}` plus `component_id`, `component_name` (`log_for_component` R2). `TaskPriorityEnum` values: see `app/models/enums.py`.
- Schemas (gap 1): `from app.schemas.project_component_task import ProjectComponentTaskCreate, ProjectComponentTaskUpdate`. Model: `app.models.project_component_task.ProjectComponentTask`.
- `TaskPriorityEnum` (gap 2): `from app.models.enums import TaskPriorityEnum`, a `str` enum with exactly four members, in this order: `LOW = "LOW"`, `MEDIUM = "MEDIUM"`, `HIGH = "HIGH"`, `URGENT = "URGENT"`. The column `task_priority` is nullable with no default.

**Notes for the test designer**
- Session, commits and setup as `department_service.spec.md` Notes.
- **BUG-2298:** as note service Notes (BUG-2293), with tasks.
- **BUG-2299:** "Zulu", "apple", "Banana" across two open projects, workspace-wide; intended "apple", "Banana", "Zulu" → **non-strict** xfail (today's order is physical until BUG-100 is fixed).

## Not specified
- `project_component_task_service` — module-level singleton.

---

## `ProjectComponentTaskService._guard_component(db, component_id, workspace_id, user_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal

**Rules:**
- **R1.** As note service `_guard_component` R1.

---

## `ProjectComponentTaskService._filter_accessible_tasks(db, tasks, workspace_id, user_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `get_tasks` without a component)

**Rules:**
- **R1.** As note service `_filter_accessible_notes` R1, R2, R4, for any row (task or note).
- **R2.** [BUG-2302] (P4) A row whose project is soft-deleted is dropped. *(Today: kept.)*

---

## `ProjectComponentTaskService.get_tasks(db, workspace_id, user_id, project_component_id=None, incomplete_only=False, is_note=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /project-component-tasks/`; the web app sends `is_note=false`)

**Rules:**
- **R1.** A truthy `project_component_id` → the guard first (403/404). [BUG-2301] (P1) `0` is treated as a component id too: 404 `Project component not found`. *(Today: `0` → workspace-wide list, verified.)*
- **R2.** With a component: `incomplete_only=True` → task DAO `get_incomplete_tasks` R1–R6 with `is_note` = the argument, or `False` when `None` (open tasks); otherwise `get_by_component` R1–R6 with `is_note` as given (`None` → both kinds). Order BUG-1447.
- **R3.** Without a component: the workspace's rows (tasks **and** notes), then `_filter_accessible_tasks`. [BUG-2300] (D1) `incomplete_only` and `is_note` apply as in R2. *(Today: both ignored, verified.)*
- **R4.** [BUG-2299] (HR-6) R3's rows are ordered by `name` case-insensitive, then `id`, before paging. *(Today: base `get_by_workspace`, `id` order per BUG-100.)*
- **R5.** [BUG-2298] (HR-5) R3's access filter is applied before `skip` / `limit`; statements do not grow with the rows. *(Today: after paging, two reads per row.)*
- **R6.** [BUG-2302] R3 leaves out rows of deleted projects.
- **R7.** Read only (T-TC6).
- **R8.** Paging defaults `skip=0`, `limit=100`; `limit=0` → `[]`; negative → `DataError`; no bound in the service (endpoint, BUG-2296).

---

## `ProjectComponentTaskService.get_by_id(db, task_id, workspace_id, user_id)`
**Shape:** get · **Persistence:** reads · **Visibility:** public (used by: `GET /project-component-tasks/{id}/`; `update_task`, `delete_task`)

**Rules:**
- **R1.** Unknown id, `0`, another workspace's → `None` (endpoint 404 `Project component task not found`); no access check.
- **R2.** Found (task or note) → guard on its component (403 / 404; deleted project → 404, BUG-1278); passed → the row. A note id is returned (the task pages are the general endpoint, D3).
- **R3.** Read only (T-TC6).

---

## `ProjectComponentTaskService.create_task(db, task_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /project-component-tasks/`, 201)

**Rules:**
- **R1.** Guard on `task_in.project_component_id` first; refused → its `HTTPException`, nothing saved. A component of a deleted project → 404 (BUG-1278; today created, verified).
- **R2.** [BUG-2297] (HR-1) `name` stored trimmed; blank refused (422). *(Today: `"  "` stored, verified.)* `description` required, kept as typed.
- **R3.** One row with the input's `project_component_id`, `name`, `description`, `is_note` (default `False`), `task_priority` (default `NULL`), plus `workspace_id`, `is_completed = False`, `created_at` set.
- **R4.** A task (`is_note = False`) → one event `task_created`, `Added task "<name>"`, performer `user_id`, metadata as Facts. A note → no event. ✅ (D3)
- **R5.** Committed and re-read (T-TC1, T-TC2); failures T-TC3–T-TC5.

---

## `ProjectComponentTaskService.update_task(db, task_id, task_in, workspace_id, user_id)`
**Shape:** update / state-transition · **Persistence:** writes · **Visibility:** public (used by: `PUT /project-component-tasks/{id}/`)

**Rules:**
- **R1.** Found as `get_by_id` R1, R2; not found → `None`, nothing written, no commit or rollback; guard refusal → rolled back (T-TC3).
- **R2.** Only fields sent with a non-`null` value are applied: `name`, `description`, `is_completed`, `is_note`, `task_priority`. `project_component_id` cannot be changed.
- **R2a.** [BUG-2304] (P3) Explicit `null` clears `task_priority`; `null` for `name`, `description`, `is_completed`, `is_note` is refused (422), nothing written. *(Today: every `null` dropped; priority stays, verified.)*
- **R3.** [BUG-2297] (HR-1) A sent `name` stored trimmed; blank refused (422).
- **R4.** For a row that is a task after the update: `is_completed` sent and changed `False → True` → event `task_completed`, `Completed task "<name>"`; `True → False` → `task_reopened`, `Reopened task "<name>"`; otherwise `task_updated`, `Updated task "<name>"`. One event, metadata as Facts, name after the update. Completing and renaming at once gives only `task_completed`.
- **R5.** [BUG-2305] (D2) A row that was a task before the update and is a note after → one event as R4 (`task_updated` unless completion changed). A row that was a note and stays one → no event. *(Today: task → note writes nothing, verified.)* Note → task → R4 applies.
- **R6.** [BUG-2303] (P2) No field changed value → no event. *(Today: `task_updated` always, verified.)*
- **R7.** Committed, re-read (T-TC1, T-TC2); failures T-TC3–T-TC5.

---

## `ProjectComponentTaskService.delete_task(db, task_id, workspace_id, user_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /project-component-tasks/{id}/`, 204)

**Returns:** `True` / `False`.

**Rules:**
- **R1.** Found as `get_by_id`; not found → `False`, nothing written, no commit or rollback.
- **R2.** A task → event `task_deleted`, `Deleted task "<name>"`, metadata as Facts, then hard delete. A note → hard delete, no event ✅ (D3). Nothing references a task row; nothing blocks.
- **R3.** Committed, `True`, no re-read; failures T-TC3, T-TC4.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 16–17 | guard | `_guard_component` R1 |
| 21–26 | component not in workspace → skip | `_filter_accessible_tasks` R1 |
| 27–33 | project found and accessible (raw, BUG-2302) | `_filter_accessible_tasks` R1, R2 |
| 47 | `if project_component_id:` (0 → workspace, BUG-2301) | `get_tasks` R1 |
| 48 | guard | `get_tasks` R1 |
| 49–57 | `incomplete_only`; `is_note` `None` → `False` | `get_tasks` R2 |
| 58–65 | by component, `is_note` as given | `get_tasks` R2 |
| 67–70 | workspace page, filter after (BUG-2298, 2299, 2300) | `get_tasks` R3–R6, R8 |
| 73–77 | not found → `None` | `get_by_id` R1 |
| 78–79 | guard; return | `get_by_id` R2 |
| 89–94 | guard; dump; create | `create_task` R1–R3 |
| 95–104 | task → event; note → none | `create_task` R4 |
| 105–110 | commit, refresh / rollback | `create_task` R5 |
| 121–123 | find; `None` | `update_task` R1 |
| 124–126 | old completion; sent fields; base update (`exclude_none`, BUG-2304) | `update_task` R2, R2a, R3 |
| 127 | note after update → no event (BUG-2305) | `update_task` R5 |
| 128–134 | completion sent and changed → completed / reopened | `update_task` R4 |
| 135–137 | else `task_updated` (BUG-2303) | `update_task` R4, R6 |
| 138–146 | event | `update_task` R4 |
| 147–152 | commit, refresh / rollback | `update_task` R7 |
| 156–158 | find; `False` | `delete_task` R1 |
| 159–168 | task → event | `delete_task` R2 |
| 169–174 | remove; commit, `True` / rollback | `delete_task` R2, R3 |
| 177 | singleton | Not specified |

## Gap log
G1 (`project_component_task_service.cases.md` gap 1) — Fact — Facts: `app.schemas.project_component_task` (`ProjectComponentTaskCreate`, `ProjectComponentTaskUpdate`).
G2 (gap 2) — Fact — Facts: `TaskPriorityEnum` (`app.models.enums`) = `LOW`, `MEDIUM`, `HIGH`, `URGENT` (values equal names).
