# Spec — `app/services/project_component_note_service.py`

> **Status:** APPROVED (2026-11-04; nothing open. Every item is a house rule or was decided by Claude under the reviewer's delegation (2026-11-04); no money, stock or order flow is involved.)
> **Source commit:** e48a092

> **Revision 2026-11-04 (fill-gaps, `project_component_note_service.cases.md` gaps 1).** Schema module named. No new bug, no question; stays APPROVED. See the Gap log.

> **Form.** As `tests/unit/services/department_service.spec.md`. **Below:** `tests/unit/managers/project_manager.spec.md` (`require_component_access`, `can_access_project`, `log_for_component`, `log_event`; Facts "Who may open a private project"), `tests/unit/dao/project_component_task.spec.md` (`get_by_component`; Model facts: notes and tasks share `project_component_tasks`, told apart by `is_note`), `tests/unit/dao/project_component.spec.md`, `tests/unit/dao/base.spec.md` (`get_by_id_and_workspace`, `create`, `update`, `remove`: raw; BUG-101). All APPROVED; cited, not restated. This spec answers task DAO FU-1 for the note service.
>
> **Not a `BaseService`.** The class commits and rolls back with `db.commit()` / `db.rollback()` itself. Its own transaction rules are N-TC1 … N-TC6 below (same outcomes as TC1–TC6 of `tests/unit/services/base_service.spec.md`, differences named).
>
> **Standing decisions applied here (not asked again):** BUG-1278 (a component of a soft-deleted project answers 404 `Project with ID <id> not found` through `require_component_access`; workspace-wide lists leave its rows out). OQ-18 (owner): a private project the caller may not open answers 403 on these pages, kept. OQ-5 does not reach notes: they are part of the project's own pages, not a discussion, file or calendar entry.
>
> **Verified by running** (`v1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvc\forkB\`, one outer transaction rolled back against `marker_test`, private `COVERAGE_FILE`; nothing persisted): a note created logs `note_created`; the note service opens a **task** id (`is_note = False` returned) and renames it, logging `note_updated`; `project_component_id=0` → 404 `Project component not found`; `update_note` of an unknown id returns `None`; a note of a deleted project's component is still listed workspace-wide (shape shared with the task service, verified there). **Read, not run:** the endpoint.

## Review
> Nothing open. Overwrite a pre-filled answer only if the house rule or the delegated decision should not apply here.

### House-rule violations — applied automatically
- **HR-1** `create_note` R2, `update_note` R3 — `ProjectComponentNoteCreate.name` / `ProjectComponentNoteUpdate.name` are plain `str`: `""` and `"  "` are stored as typed. Intended: trimmed; blank refused by the schema (422).
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-2290 (pattern `blank-name-accepted`). Rules: `create_note` R2, `update_note` R3.
- **HR-6** `get_notes` R3 — without a component the service runs its own query with no `ORDER BY`. Intended: `name` case-insensitive, then `id`, before paging (as BUG-1447 for one component).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2292 (pattern `unordered-pagination`). Rules: `get_notes` R3.
- **HR-5** `get_notes` R4 — without a component, notes of projects the caller may not open are dropped in Python **after** `skip` / `limit`, one component and one project read per row (task DAO FU-1 (b)). Intended: the access filter is part of the query, before paging; the reads do not grow with the rows.
**Answer:** bug — per HR-5 (house rule)
**Resolution:** 🐞 BUG-2293 (pattern `paginate-before-filter`). Rules: `get_notes` R4.
- **HR-7** `get_notes` R6 — `GET /project-component-notes/` declares `limit: Query(100, le=100)` with no lower bound (task DAO FU-1 (a)). Intended: `limit >= 1`, 422 otherwise.
**Answer:** bug — per HR-7 (house rule)
**Resolution:** 🐞 BUG-2296 (pattern `missing-limit-lower-bound`; one bug with `GET /project-component-tasks/`). Endpoint rule; the service does not change.

### Decided by Claude under the reviewer's delegation (2026-11-04)

### D1. The note pages open, rename and delete tasks — 🐞 BUG-2291
**Background:** Notes and tasks are rows of one table, told apart by `is_note`. The web app uses `/project-component-notes/` for notes and `/project-component-tasks/` for tasks. The note service's single-row lookup never looks at `is_note`.
**What happens today:** `GET /project-component-notes/<task id>/` returns the task; `PUT` renames it and logs `note_updated` "Updated note …"; `DELETE` deletes it and logs `note_deleted` (verified for get and update).
**Example:** A client deletes "note" 85655, which is the task "Weld frame"; the task is gone and the activity log says a note was deleted.
**Rules affected:** `get_by_id_and_workspace` R2, `update_note` R1, `delete_note` R1
**Answer:** bug — the note service treats a row with `is_note = False` as not found: `None` (the endpoint's 404 `Project component note not found`), nothing written. The task service stays the general one (it lists both kinds on purpose, `is_note` "omit to return both").
**Resolution:** 🐞 BUG-2291 (pattern `discriminator-not-checked`).

### D2. Saving a note unchanged writes "Updated note" — 🐞 BUG-2295
**Background:** Every successful update writes one `note_updated` project event. Same root cause as BUG-632 / BUG-2118.
**What happens today:** `PUT {}` or the same name and description logs `Updated note "<name>"`.
**Example:** Rafi opens a note and presses Save without typing; the project's activity tab shows "Updated note 'Supplier call'".
**Rules affected:** `update_note` R4
**Answer:** bug — per BUG-632 precedent: an update that changes no value writes no event; the note is returned as usual.
**Resolution:** 🐞 BUG-2295 (pattern `audit-event-on-noop`).

### D3. Notes of a deleted project stay on the workspace-wide list — 🐞 BUG-2294
**Background:** BUG-1278 hides a deleted project's components, members and items; the guard answers 404 for one component. The workspace-wide note list does its own access filter with a raw project read, which a deleted project passes.
**What happens today:** `GET /project-component-notes/` without a component lists the notes of components of deleted projects (same code shape as the task service, verified there).
**Example:** Project "Line 3" is deleted; its 4 notes still appear on a workspace-wide notes view.
**Rules affected:** `get_notes` R5
**Answer:** bug — per BUG-1278 precedent: notes whose project is soft-deleted are not listed and take no place on the page; the rows stay.
**Resolution:** 🐞 BUG-2294 (pattern `join-ignores-soft-deleted`).

Checked and **not** violated: **HR-2** — note names need not be unique. **HR-3, HR-8** — no grouping, no `LIKE`. **HR-4** — notes have no soft delete (hard delete); the deleted project is BUG-1278 / D3. **HR-9** — the table has no audit stamps; events are D2. **HR-10** — no money, stock or decision. **HR-15** — no money. **HR-16** — the component is found in the caller's workspace (`require_component_access` R1); `ProjectComponentNoteUpdate` has no `project_component_id`, so a note cannot be moved; a stored note whose component is in another workspace is skipped by the workspace-wide list (R4) and answers 404 by id. `project_component_id=0` → 404 (checked with `is None`, so no falsy-zero issue here).

**Permission checks:** only `require_component_access` (who may open the project). Any such member may add, edit or delete any note, whoever wrote it (no author column). Recorded for the permissions feature, not asked.

## Overview
`ProjectComponentNoteService` is the transaction boundary for notes on a project component (rows of `project_component_tasks` with `is_note = True`). The `/project-component-notes/` endpoints call it. It checks access through `ProjectManager`, writes through the base DAO, logs one project event per write, and commits.

**Callables:** 7 specified · 1 not specified
**Externals to mock:** none (`created_at` is a Python column default: assert set).
**Integration-only behavior:** the endpoints' 404 `Project component note not found` for `None` / `False`; `skip >= 0`, `limit <= 100` (BUG-2296); schema validation (400 today, BUG-461; 422 intended).

### Transaction rules (N-TC) — this service's writes
`create_note`, `update_note`, `delete_note` run their whole body in one `try`: on success `db.commit()` (then `db.refresh` for create and update); any exception → `db.rollback()` and re-raise.
- **N-TC1.** A write that succeeds is committed: the change survives a later rollback of the same session.
- **N-TC2.** Create and update return the row re-read after the commit (`created_at` loaded, not expired). Delete returns `True`, no re-read.
- **N-TC3.** Any exception inside the `try` (the guard's `HTTPException` 403/404, `IntegrityError`, `DataError`, anything) rolls the session back **once** and reaches the caller as the same object; every uncommitted change pending in the session is discarded; the session is usable afterwards.
- **N-TC4.** If `commit` raises: one rollback, the commit's exception reaches the caller unchanged, nothing saved.
- **N-TC5.** If the re-read after commit raises: that exception reaches the caller and the change stays saved.
- **N-TC6.** Reads (`get_notes`, `get_by_id_and_workspace`) neither commit nor roll back; their exceptions reach the caller unchanged. **Differs from TC:** `update_note` and `delete_note` that find nothing return `None` / `False` with **no commit and no rollback** (pending changes stay pending).

**Facts for the test designer**
- Import: `from app.services.project_component_note_service import ProjectComponentNoteService, project_component_note_service`. No constructor arguments. All parameters positional-or-keyword; the endpoints pass `get_notes` by keyword, the others positionally.
- Errors from the guard are `fastapi.HTTPException`: 404 `Project component not found`, 404 `Project with ID <id> not found`, 403 `You do not have access to this project` (project manager `require_component_access` R1–R4).
- Event metadata: the service passes `{"note_id", "note_name"}`; `log_for_component` R2 adds `component_id`, `component_name`. Event `project_id` is the component's project.
- Schemas (gap 1): `from app.schemas.project_component_note import ProjectComponentNoteCreate, ProjectComponentNoteUpdate`. Notes are rows of `app.models.project_component_task.ProjectComponentTask` with `is_note = True`.

**Notes for the test designer**
- Session and commits as `department_service.spec.md` Notes; on every raising path commit the setup first.
- Build rows as `project_manager.spec.md` Notes; a note is `ProjectComponentTask(..., is_note=True)`.
- **BUG-2293:** non-privileged caller, 3 notes on a private project they may not open created first, then 2 on an open project; `limit=2` → intended the 2 visible ones; today `[]` → strict xfail.
- **BUG-2292:** names "Zulu", "apple", "Banana" in that order; intended "apple", "Banana", "Zulu" → **non-strict** xfail (today's order is physical).

## Not specified
- `project_component_note_service` — module-level singleton.

---

## `ProjectComponentNoteService._guard_component(db, component_id, workspace_id, user_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `get_notes`, `get_by_id_and_workspace`, `create_note`)

**Rules:**
- **R1.** Passes exactly when `ProjectManager.require_component_access` passes (R1–R4 there, with BUG-1278); otherwise its `HTTPException` reaches the caller unchanged. Returns `None`.

---

## `ProjectComponentNoteService._filter_accessible_notes(db, notes, workspace_id, user_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `get_notes` without a component)

**Returns:** the notes kept, in input order.

**Rules:**
- **R1.** A note whose component is not found in `workspace_id` (another workspace's, HR-16 invalid data) is dropped.
- **R2.** A note whose project is not found in the workspace is dropped; otherwise kept exactly when `can_access_project` is true (project manager R1–R3).
- **R3.** [BUG-2294] (D3) A note whose project is soft-deleted is dropped. *(Today: kept; the project read is raw.)*
- **R4.** An empty input gives `[]`.

---

## `ProjectComponentNoteService.get_notes(db, workspace_id, user_id, project_component_id=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /project-component-notes/`)

**Returns:** a `list` of `ProjectComponentTask` with `is_note = True`.

**Rules:**
- **R1.** With `project_component_id` not `None` (`0` included): the guard (R1) runs first, then the rows are task DAO `get_by_component(is_note=True)` R1–R6 for that component and workspace (order BUG-1447). `0` or an unknown id → 404 `Project component not found`.
- **R2.** With `project_component_id=None`: the notes of the whole workspace (`workspace_id` match, `is_note = True`; tasks never), then `_filter_accessible_notes`.
- **R3.** [BUG-2292] (HR-6) R2's rows are ordered by `name` case-insensitive, then `id`, before paging. *(Today: no `ORDER BY`.)*
- **R4.** [BUG-2293] (HR-5) R2's access filter (R1–R3 of the helper) is applied before `skip` / `limit`: a page is short only at the end, and the number of statements does not grow with the rows. *(Today: page first, then filter in Python with two reads per row.)*
- **R5.** [BUG-2294] R2 leaves out notes of deleted projects (helper R3).
- **R6.** Paging defaults `skip=0`, `limit=100`; `limit=0` → `[]`; negative values → `DataError`. The service sets no bound (endpoint, BUG-2296).
- **R7.** Read only (N-TC6).

---

## `ProjectComponentNoteService.get_by_id_and_workspace(db, note_id, workspace_id, user_id)`
**Shape:** get · **Persistence:** reads · **Visibility:** public (used by: `GET /project-component-notes/{id}/`; `update_note`, `delete_note`)

**Returns:** the row, or `None`.

**Rules:**
- **R1.** Unknown id, `0`, or another workspace's → `None` (the endpoint answers 404 `Project component note not found`); no access check runs.
- **R2.** [BUG-2291] (D1) A row with `is_note = False` (a task) → `None`, as not found. *(Today: returned, verified.)*
- **R3.** Found → the guard runs on its component (403 / 404 as `_guard_component` R1; a deleted project → 404, BUG-1278); passed → the note.
- **R4.** Read only (N-TC6).

---

## `ProjectComponentNoteService.create_note(db, note_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /project-component-notes/`, 201)

**Rules:**
- **R1.** The guard runs on `note_in.project_component_id` first; refused → its `HTTPException`, nothing saved (N-TC3). A component of a deleted project → 404 (BUG-1278; today the note is created).
- **R2.** [BUG-2290] (HR-1) `name` is stored trimmed; `""` or only spaces is refused by `ProjectComponentNoteCreate` (422), nothing written. *(Today: as typed.)* `description` is required and kept as typed (`""` accepted).
- **R3.** One row: `workspace_id`, `project_component_id`, `name`, `description` from the input, `is_note = True`, `is_completed = False`, `task_priority = NULL`, `created_at` set.
- **R4.** One project event `note_created`, description `Added note "<name>"`, performer `user_id`, metadata `{"note_id", "note_name", "component_id", "component_name"}`.
- **R5.** Committed and returned re-read (N-TC1, N-TC2); failures N-TC3–N-TC5.

**Errors:** the guard's `HTTPException`s; database errors unchanged.

---

## `ProjectComponentNoteService.update_note(db, note_id, note_in, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PUT /project-component-notes/{id}/`)

**Rules:**
- **R1.** The note is found as `get_by_id_and_workspace` R1–R3 (BUG-2291: a task id is not found). Not found → `None`, nothing written, no commit, no rollback (N-TC6); a guard refusal → its `HTTPException`, rolled back (N-TC3).
- **R2.** Only `name` and `description` sent with a non-`null` value are applied (base `update`); `null` or omitted fields are unchanged. `project_component_id`, `is_note` and `is_completed` cannot be changed here.
- **R3.** [BUG-2290] (HR-1) A sent `name` is stored trimmed; blank refused (422). *(Today: `""` stored.)*
- **R4.** One event `note_updated`, description `Updated note "<new name>"`, metadata as `create_note` R4. [BUG-2295] (D2) Only when at least one field changes value; otherwise no event. *(Today: always.)*
- **R5.** Committed, returned re-read (N-TC1, N-TC2); failures N-TC3–N-TC5.

---

## `ProjectComponentNoteService.delete_note(db, note_id, workspace_id, user_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /project-component-notes/{id}/`, 204)

**Returns:** `True` when deleted; `False` when not found.

**Rules:**
- **R1.** Found as `update_note` R1 (BUG-2291); not found → `False`, nothing written, no commit, no rollback.
- **R2.** One event `note_deleted`, `Deleted note "<name>"`, metadata as `create_note` R4, is written, then the row is hard-deleted. Nothing references a note, so nothing blocks.
- **R3.** Committed (N-TC1; the event stays, the note is gone); `True`; no re-read. Failures N-TC3, N-TC4.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 16–17 | guard | `_guard_component` R1 |
| 21–26 | component not in workspace → skip | `_filter_accessible_notes` R1 |
| 27–33 | project found and accessible (raw, BUG-2294) | `_filter_accessible_notes` R2, R3 |
| 45 | `project_component_id is None` | `get_notes` R1, R2 |
| 48–57 | own query, no order, page first (BUG-2292, BUG-2293) | `get_notes` R2–R4, R6 |
| 58 | filter after page | `get_notes` R4, R5 |
| 60–68 | guard; DAO `is_note=True` | `get_notes` R1 |
| 73–77 | not found → `None` (no `is_note` check, BUG-2291) | `get_by_id_and_workspace` R1, R2 |
| 78–79 | guard; return | `get_by_id_and_workspace` R3 |
| 89–95 | guard; dump; `is_note=True`; create | `create_note` R1–R3 |
| 96–104 | event | `create_note` R4 |
| 105–110 | commit, refresh / rollback | `create_note` R5; N-TC |
| 121–123 | find; `None` | `update_note` R1 |
| 124 | base update (`exclude_none`) | `update_note` R2, R3 |
| 125–133 | event always (BUG-2295) | `update_note` R4 |
| 134–139 | commit, refresh / rollback | `update_note` R5 |
| 143–145 | find; `False` | `delete_note` R1 |
| 146–155 | event; remove | `delete_note` R2 |
| 156–160 | commit, `True` / rollback | `delete_note` R3 |
| 163 | singleton | Not specified |

## Gap log
G1 (`project_component_note_service.cases.md` gap 1) — Fact — Facts: `app.schemas.project_component_note` (`ProjectComponentNoteCreate`, `ProjectComponentNoteUpdate`).
