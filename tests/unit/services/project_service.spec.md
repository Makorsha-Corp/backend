# Spec — `app/services/project_service.py`

> **Status:** APPROVED (2026-11-04; nothing open. Both new items decided by Claude under the reviewer's delegation (2026-11-04), as precedent matches.)
> **Source commit:** e48a092

> **Revision 2026-11-04 (fill-gaps, `project_service.cases.md` gaps 1).** BUG-2271's endpoint named with module, signature and response. No new bug, no question; stays APPROVED. See the Gap log.

> **Form.** As `tests/unit/services/department_service.spec.md`. The **Transaction contract TC1–TC6** is the one of `tests/unit/services/base_service.spec.md`, cited, not restated. What the manager decides is **cited, not restated**: `tests/unit/managers/project_manager.spec.md` (APPROVED), and below it the project, project member, project event, workspace member, factory and base DAO specs.
>
> **Routed here:** project manager FU-1 (a)–(d). (a) BUG-1961 is the endpoint's query type, cited. (b) and (c) are confirmed in `app/api/v1/endpoints/projects.py` and logged here (D1, D2); the fixes live in the endpoint, so they are written as rules of the endpoint's behaviour around this service, and the test designer tests them at the service where possible (D2) or as integration-only (D1). (d) BUG-1954's `include_deleted` stays without an API caller (manager `get_project` R2): this service passes no such argument today and the spec adds none.
>
> **Standing decisions applied here (not asked again):** OQ-18 (owner): a private project answers 403 on its own pages; this service passes that on unchanged. OQ-5 does not reach this service (discussions, files and calendar are other services). Plan limits other than members are not enforced (manager `create_project` R6).
>
> **Verified by running:** nothing new beyond the manager spec's runs (`mgr6d\v1.py`); the service is a thin `BaseService` wrapper read line by line. The transaction outcomes were verified for `BaseService` itself (`base_service.spec.md`) and for a sibling wrapper (`department_service.spec.md`). **Read, not run:** the endpoint's catch-all (D1) and the per-member reads (D2).

## Review
> Nothing open. Both items below were decided by Claude under the reviewer's delegation (2026-11-04); overwrite an answer to change it.

### Precedent matches — all applied (decided by Claude under the reviewer's delegation, 2026-11-04)

### D1. Creating a project shows the database's own error text — 🐞 BUG-2270
**Background:** `POST /projects/` wraps the service call: an `HTTPException` passes, and **any other exception** is turned into 400 with `detail = str(e)`. Same root cause as BUG-037 (login).
**What happens today:** A database error during create (for example `budget: 1e20`, which overflows `Numeric(15,2)` at the flush, manager `create_project` R5) answers 400 with the full driver message, including the SQL statement and parameters. The global handler, which would answer a generic 500 (or 409 for an integrity error), is never reached. (Read.)
**Example:** A client sends a budget of `1e20`. The answer is 400 `(psycopg2.errors.NumericValueOutOfRange) numeric field overflow … [SQL: INSERT INTO projects (…) VALUES (…)]`, showing table and column names.
**Rules affected:** `create_project` R4
**Answer:** bug — per BUG-037 precedent: `POST /projects/` drops its catch-all; unexpected errors reach the global handlers (generic 500; integrity errors 409 as everywhere), the details only in the server log. `HTTPException`s pass as today.
**Resolution:** 🐞 BUG-2270 (pattern `internal-error-leak`). Fix in `app/api/v1/endpoints/projects.py`. Rules: `create_project` R4.

### D2. The project members list reads two rows per member — 🐞 BUG-2271
**Background:** `GET /projects/{id}/members/` takes the members from this service, then for each one reads the profile (name, email) and the workspace membership (position), one query each. Same root cause as BUG-1964 (the project log) and BUG-1141.
**What happens today:** 30 members take 60 extra statements after the list. (Read.)
**Example:** A big project's Members tab makes 60+ small database reads where three would do. The page looks the same.
**Rules affected:** `list_members` R3
**Answer:** bug — per BUG-1964 precedent: profiles and memberships of the listed members are read together, at most two statements after the member list whatever its length; the response is unchanged.
**Resolution:** 🐞 BUG-2271 (pattern `n-plus-one-read`). Fix in the endpoint, or in this service returning the enriched rows. Rules: `list_members` R3.

Reached through the manager and cited, one pass-through case each where the cases file needs it: BUG-1192, BUG-1278, BUG-1951 … BUG-1964 (manager spec). No new ID for them.

Checked and **not** violated: **HR-1 … HR-6, HR-8, HR-9, HR-15, HR-16** — all decided in the manager (cited). **HR-7** — `GET /projects/` requires `skip >= 0`, `1 <= limit <= 1000`. **HR-10** — no harmful state (manager spec). **HR-11 … HR-14** — no external system or batch.

**Permission checks:** none of its own. Who may open, edit, delete, change visibility and manage members is the manager's (`require_project_access`; no role check beyond it, manager FU-2, already in `docs/future/permissions.md`).

## Overview
`ProjectService` is the transaction boundary for projects. The `/projects/` endpoints call it; it calls `ProjectManager` and commits, rolls back and re-reads around it. It adds no check, no translation and no shaping: every refusal is the manager's `HTTPException`, passed on unchanged. Reads are passed straight through.

**Callables:** 10 specified · 2 not specified
**Externals to mock:** `utcnow` as imported in `app.managers.project_manager` (manager spec); the service adds no clock.
**Integration-only behavior:** HTTP status mapping of the passed-on `HTTPException`; `POST /projects/`'s catch-all (D1, BUG-2270); the endpoint's `project_status` type (BUG-1961); `skip`/`limit` bounds; the members endpoint's profile and position fields (D2's response shape).

**Facts for the test designer**
- Import: `from app.services.project_service import ProjectService, project_service`. `ProjectService()` takes no arguments; its manager is the attribute `project_manager`, the module singleton of `app.managers.project_manager`. All parameters positional-or-keyword; the endpoints pass everything after `db` by keyword.
- Write methods: `create_project`, `update_project`, `delete_project`, `add_member`, `set_visibility` commit and re-read; `remove_member` commits and returns `None` (no re-read). Reads: `get_project`, `list_projects`, `list_events`, `list_members`.
- The manager's rules, errors and messages: `tests/unit/managers/project_manager.spec.md`.
- **BUG-2271's endpoint (gap 1):** `from app.api.v1.endpoints.projects import list_project_members`; route `GET /projects/{project_id}/members/`. Signature `list_project_members(project_id: int, workspace: Workspace, current_user: Profile, db: Session)` (the last three are FastAPI `Depends` defaults; a unit card calls it directly with keyword arguments: the `Workspace` row, the caller's `Profile`, the `db` session). It calls `project_service.list_members(db, project_id=…, workspace_id=workspace.id, user_id=current_user.id)`, then per member `profile_dao.get` and `workspace_member_dao.get_by_workspace_and_user`, and returns `ProjectMembersListResponse(members=[ProjectMemberResponse, …])` (`app/schemas/project.py`): each member has `id`, `workspace_id`, `project_id`, `user_id`, `user_name`, `user_email`, `user_position` (the workspace membership's `position`, `None` without one), `assigned_by`, and `assigned_at`. Errors from the service pass unchanged (`HTTPException` 404 / 403). It is a plain function: calling it needs no HTTP client.

**Notes for the test designer**
- Session, commits, TC3–TC6 mechanics: as the Notes of `department_service.spec.md` (commit setup before an error path; patch `commit` / `refresh`).
- **Pass-through cases:** one per manager bug a method reaches, to the intended behaviour, strict or non-strict exactly as in the manager's cases file. Do not re-test the manager's edge cases.
- **BUG-2271:** call `project_service.list_members` and then, per row, what the endpoint reads — or better, test the endpoint function `list_project_members` directly with a statement counter (`before_cursor_execute`) and 5 members: intended ≤ 2 statements after the member list → strict xfail.
- **BUG-2270:** integration-only (needs the endpoint); one HTTP case if the integration suite exists.

## Not specified
- `ProjectService.__init__` — stores the manager, no logic.
- `project_service` — module-level singleton.

---

## `ProjectService.create_project(db, project_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /projects/`, 201)

**Purpose:** Create a project (with its creator as member and a `created` event) and save it.

**Returns:** the new `Project`, committed and re-read (TC1, TC2).

**Rules:**
- **R1.** The project, the creator's `project_members` row and the `created` event are made exactly as manager `create_project` R1–R6 (BUG-1951, BUG-1962, BUG-1963) and committed together (TC1); the project is returned re-read, `id` and `created_at` set (TC2).
- **R2.** The manager's refusals reach the caller unchanged, nothing saved (TC3): 404 `Factory with ID <factory_id> not found`, 400 `Cannot create project for deleted factory`.
- **R3.** Commit and re-read failures follow TC4, TC5.
- **R4.** [BUG-2270] (D1) Through `POST /projects/`, an exception that is not an `HTTPException` reaches the application's global handlers (generic 500, `IntegrityError` 409), never a 400 carrying `str(e)`. *(Today: 400 with the exception text. Read.)* The service itself re-raises unchanged (TC3) today and after the fix.

**Errors:** R2; database errors unchanged.

**Side effects:** one `projects`, one `project_members`, one `project_events` row, committed. On any error: rolled back.

---

## `ProjectService.get_project(db, project_id, workspace_id, user_id)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (used by: `GET /projects/{id}/`)

**Rules:**
- **R1.** Returns manager `get_project` for these arguments: 404 `Project with ID <id> not found` (missing, other workspace; [BUG-1954] soft-deleted), 403 `You do not have access to this project` (private, OQ-18), passed on unchanged.
- **R2.** No `include_deleted` argument (FU-1 (d)); read only (TC6).

---

## `ProjectService.list_projects(db, workspace_id, user_id, factory_id=None, status=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /projects/`, always with every argument; `status` is the query's `project_status`)

**Rules:**
- **R1.** Returns manager `list_projects` for exactly these arguments; with nothing after `user_id` the manager gets `factory_id=None`, `status=None`, `skip=0`, `limit=100`. Filtering, order, paging and the access filter are manager R1–R7 (BUG-1955 … BUG-1961), not repeated.
- **R2.** Read only (TC6). The manager's `ValueError` for an unknown status (BUG-1961) reaches the caller unchanged.

---

## `ProjectService.update_project(db, project_id, project_in, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PUT /projects/{id}/`)

**Returns:** the `Project`, committed and re-read (TC1, TC2): `updated_at` loaded.

**Rules:**
- **R1.** The project is changed and its events written exactly as manager `update_project` R1–R9 (BUG-1951 … BUG-1953, BUG-1962, BUG-1963); committed (TC1); returned re-read (TC2).
- **R2.** The manager's refusals reach the caller unchanged, nothing saved (TC3): 404, 403, 400 `Cannot update deleted project`.
- **R3.** Commit and re-read failures follow TC4, TC5.

---

## `ProjectService.delete_project(db, project_id, workspace_id, user_id)`
**Shape:** soft-delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /projects/{id}/`, 200 with the row)

**Returns:** the soft-deleted `Project`, committed and re-read (`is_deleted = True`, `deleted_at`, `deleted_by` set).

**Rules:**
- **R1.** Soft delete and `deleted` event exactly as manager `delete_project` R1–R3; committed (TC1); re-read (TC2).
- **R2.** Refusals unchanged, nothing saved (TC3): 404, 403, 400 `Project is already deleted`.
- **R3.** Commit and re-read failures follow TC4, TC5.

---

## `ProjectService.list_events(db, project_id, workspace_id, user_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /projects/{id}/events/`)

**Rules:**
- **R1.** Returns manager `list_events` (pairs of event and profile) unchanged: R1–R4 there (BUG-1964). A deleted project's log is still answered.
- **R2.** Read only (TC6).

---

## `ProjectService.list_members(db, project_id, workspace_id, user_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /projects/{id}/members/`)

**Rules:**
- **R1.** Returns manager `list_members` unchanged: R1, R2 there (BUG-1278: a deleted project → 404).
- **R2.** Read only (TC6).
- **R3.** [BUG-2271] (D2) The endpoint's enrichment (each member's profile name and email, and the position of their workspace membership, `None` when either is missing) is read in at most two statements after the member list, whatever the number of members; the response is unchanged. *(Today: two statements per member. Read.)*

---

## `ProjectService.add_member(db, project_id, member_user_id, workspace_id, assigned_by)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /projects/{id}/members/`, 201)

**Returns:** the new `ProjectMember`, committed and re-read.

**Rules:**
- **R1.** The row and the `member_added` event exactly as manager `add_member` R1–R4; committed (TC1); re-read (TC2), `assigned_at` loaded.
- **R2.** Refusals unchanged, nothing saved (TC3): 404 (missing, other workspace, [BUG-1278] deleted project), 403, 400 `User is not an active member of this workspace`, 409 `User is already a member of this project`.
- **R3.** Commit and re-read failures follow TC4, TC5.

---

## `ProjectService.remove_member(db, project_id, member_user_id, workspace_id, performed_by)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /projects/{id}/members/{user_id}/`, 204)

**Returns:** `None`. Nothing is re-read.

**Rules:**
- **R1.** The row is deleted and the `member_removed` event written exactly as manager `remove_member` R1–R4; committed (TC1).
- **R2.** Refusals unchanged, nothing saved (TC3): 404 (project; [BUG-1278] deleted project), 403, 400 `Cannot remove the project creator from members`, 404 `Project member not found`.
- **R3.** A failing commit follows TC4. TC2 and TC5 do not apply (no re-read).

---

## `ProjectService.set_visibility(db, project_id, visibility, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `PATCH /projects/{id}/visibility/`)

**Returns:** the `Project`, committed and re-read.

**Rules:**
- **R1.** As manager `set_visibility` R1–R4 (same visibility → unchanged, no event, and the commit still runs and saves nothing new); committed (TC1); re-read (TC2).
- **R2.** Refusals unchanged, nothing saved (TC3): 404, 403, 400 `Cannot update deleted project`.
- **R3.** Commit and re-read failures follow TC4, TC5.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| `base_service.py` 26–30, 39 | commit / commit raises / rollback | TC1, TC3, TC4 |
| 33–42 | create: manager → commit → refresh → return | `create_project` R1, TC1, TC2 |
| 43–45 | create: any exception → rollback, re-raise | `create_project` R2, R3; endpoint catch-all R4 (BUG-2270) |
| 54–59 | get: manager, no `include_deleted` | `get_project` R1, R2 |
| 71–79 | list: manager with every argument | `list_projects` R1, R2 |
| 89–102 | update: try / commit / refresh / except | `update_project` R1–R3 |
| 111–123 | delete: try / commit / refresh / except | `delete_project` R1–R3 |
| 132–137 | events: manager | `list_events` R1, R2 |
| 146–151 | members: manager (endpoint reads per row, BUG-2271) | `list_members` R1–R3 |
| 161–174 | add member: try / commit / refresh / except | `add_member` R1–R3 |
| 184–195 | remove member: try / commit (no refresh) / except | `remove_member` R1–R3 |
| 205–218 | visibility: try / commit / refresh / except | `set_visibility` R1–R3 |
| 221 | module singleton | Not specified |

## Gap log
G1 (`project_service.cases.md` gap 1) — Fact — Facts: `app.api.v1.endpoints.projects.list_project_members(project_id, workspace, current_user, db)`, `GET /projects/{project_id}/members/`, returns `ProjectMembersListResponse` (`app/schemas/project.py`); callable directly in a unit card.
