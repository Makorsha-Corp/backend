# Spec — `app/managers/project_manager.py`

> **Status:** APPROVED (2026-11-04; nothing open). Q1 answered by the owner (2026-11-04), OQ-18: 403 intended, no bug, BUG-1965 unused. Q2 decided by Claude under the reviewer's delegation (BUG-1960).
> **Source commit:** e48a092

> **Below.** `tests/unit/dao/project.spec.md` (`get_by_factory`, `get_by_status`; Model facts), `project_member.spec.md`, `project_event.spec.md`, `project_component.spec.md`, `workspace_member.spec.md` (`get_by_workspace_and_user` R1–R3), `factory.spec.md` (`get_by_id_and_workspace`), `base.spec.md` (`get`, `get_by_id_and_workspace`, `get_by_workspace`, `create`, `update`: raw, BUG-100). All APPROVED; their rules are **cited, not restated**. This spec answers project DAO FU-1, project member DAO FU-1, project event DAO FU-1 / FU-2, and factory manager FU-5 for projects.
>
> **Above.** `ProjectService` (every public method; no spec yet). The rule "who may open a private project" (`can_access_project`) is also cited by `tests/unit/services/discussion_service.spec.md` (BUG-1867) and `calendar_service.spec.md` (BUG-1869), both APPROVED with OQ-5 applied, and by BUG-1870 (attachments). This spec writes the rule exactly as those specs state it (Facts "Who may open a private project"); nothing here changes it.
>
> **Standing decisions applied here (not asked again):** BUG-1278 (a soft-deleted project's members and components answer 404; `list_events` keeps answering; `delete_project` keeps its 400). BUG-1192 / HR-16 (`log_event` refuses a project not in the workspace). OQ-5 (owner: records follow the project's visibility, and a member who may not open it gets 404) applies to discussions, attachments and calendar; the project pages themselves keep 403 (owner, OQ-18, Q1). Plan limits other than members are not enforced, intended for now (factory manager Q4; `docs/future/subscription-payments.md`).
>
> **Verified by running** (`v1.py` with harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\mgr6d\`, one outer transaction rolled back against `marker_test`, private `COVERAGE_FILE`; nothing persisted): create with name `"  "` and `description ""` accepted; budget `-5` accepted; `list_projects(factory_id=F1, status="PLANNING")` returned F1's `COMPLETED` project too; `status="planning"` raises `ValueError`; `factory_id=0` lists every project; a `ground-team` member gets 403 "You do not have access to this project" on another's private project and does not see it in the list; `update_project({"name": <same>})` set `updated_by` and `updated_at` with no event; `{"budget": null}` left the budget at 100; `log_event` on another workspace's project wrote a row under the caller's workspace; `log_event` without metadata stores JSON `null`; `get_project` returns a deleted project; the default list includes it; update and set visibility of a deleted project → 400 "Cannot update deleted project"; removing the creator → 400. **Read, not run:** the rest.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically
- **HR-1** `create_project` R4, `update_project` R7 — `ProjectCreate.name` / `ProjectUpdate.name` are plain `str`: `""` and `"  "` are accepted, and names are stored untrimmed (verified). Intended: trimmed; blank refused by the schema (422).
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-1951 (pattern `blank-name-accepted`). Rules: `create_project` R4, `update_project` R7.
- **HR-9** `update_project` R9 — every successful update writes `updated_by` and `updated_at`, even when no field changes (verified). The edit dialog sends every field on each save, so every save stamps. Intended: stamped only when at least one field changes value.
**Answer:** bug — per HR-9 (house rule)
**Resolution:** 🐞 BUG-1952 (pattern `audit-stamp-on-noop`). Rules: `update_project` R9.
- **HR-4** `get_project` R2 — a soft-deleted project is returned by id (verified). Intended: 404 `Project with ID <id> not found` by default; an `include_deleted` option returns it.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-1954 (pattern `get-returns-soft-deleted`). Rules: `get_project` R2, `require_project_access` R3.
- **HR-4** `list_projects` R3 — without `factory_id` and `status` the list reads the raw `get_by_workspace`: deleted projects are listed and use places on the page (verified; the web page does not filter them). Intended: never listed, no place on the page (the filtered paths: BUG-1445).
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-1955 (pattern `list-returns-soft-deleted`). Rules: `list_projects` R3.
- **HR-6** `list_projects` R5 — the unfiltered path is ordered by `id` only (base BUG-100). Intended: `name` case-insensitive, then `id`, before paging, the same as the filtered paths (BUG-1444).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-1957 (pattern `hr-6-non-default-list-order`). Rules: `list_projects` R5.
- **HR-5** `list_projects` R7 — for a caller who is not privileged, private projects they may not open are dropped in Python **after** `skip` / `limit` (project DAO FU-1 (a)): pages come back short or empty though more visible projects exist. Intended: the access filter is part of the query, before paging.
**Answer:** bug — per HR-5 (house rule)
**Resolution:** 🐞 BUG-1958 (pattern `paginate-before-filter`). Rules: `list_projects` R7.
- **HR-16** `log_event` R2 — the project is not checked against the workspace (verified). Already logged from the project event DAO's FU-1.
**Answer:** bug — per HR-16 (house rule)
**Resolution:** 🐞 BUG-1192 (existing; no new ID). Rules: `log_event` R2.

### Precedent matches — all applied (decided by Claude under the reviewer's delegation, 2026-11-04)

### P1. Budget, deadline and dates cannot be cleared — 🐞 BUG-1953
**Background:** An update reads only the fields sent and drops every `null` (`exclude_none`). Same root cause as BUG-942 (items) and BUG-962 (machines).
**What happens today:** `PUT {"budget": null}` leaves the budget as it was, 200 (verified). The edit dialog sends `null` for an emptied budget, deadline, start date or end date.
**Example:** A manager empties the deadline of "Line 3 refit" and saves; the dialog closes, and the old deadline is still there.
**Rules affected:** `update_project` R2, R2a
**Answer:** bug — per BUG-942 precedent: explicit `null` clears `budget`, `deadline`, `start_date`, `end_date`; `null` for `name`, `description`, `priority`, `status` is refused by `ProjectUpdate` (422); omitted fields are unchanged.
**Resolution:** 🐞 BUG-1953 (pattern `exclude-none-blocks-clear`). Rules: `update_project` R2 (untagged part), R2a (tagged).

### P2. Projects of a deleted factory stay on the unfiltered list — 🐞 BUG-1956
**Background:** A factory's soft delete hides what belongs to it ("hidden, not cascaded"). The filtered lists will hide them (BUG-1446); the unfiltered one does not look at the factory.
**What happens today:** `GET /projects/` with no filter lists projects of deleted factories (read; the same raw read as the deleted projects, verified).
**Example:** "Old Plant" is deleted. Its 3 projects disappear when the page is filtered by status, and come back under "All statuses".
**Rules affected:** `list_projects` R4
**Answer:** bug — per BUG-1446 precedent: projects whose factory is soft-deleted are not listed and take no place on the page; an inactive-but-live factory hides nothing; no row changes.
**Resolution:** 🐞 BUG-1956 (pattern `join-ignores-soft-deleted`). Rules: `list_projects` R4.

### P3. `factory_id=0` lists every project — 🐞 BUG-1959
**Background:** `if factory_id:` treats `0` like "no filter". Same as BUG-880, BUG-922.
**What happens today:** `factory_id=0` returns every project of the workspace (verified: 4 of 4).
**Example:** A client sends `?factory_id=0` and gets every factory's projects instead of none.
**Rules affected:** `list_projects` R1
**Answer:** bug — per BUG-880 precedent: only `None` means "no factory filter"; `0` filters like any id and matches nothing.
**Resolution:** 🐞 BUG-1959 (pattern `falsy-zero-treated-as-missing`). Rules: `list_projects` R1.

### P4. An unknown status filter is a server error — 🐞 BUG-1961
**Background:** `project_status` is a free string in the endpoint and is turned into `ProjectStatusEnum` here. Same root cause as BUG-1570 (machines list filters).
**What happens today:** `?project_status=planning` (lower case) or `bogus` raises `ValueError` (verified), which the API answers as 500.
**Example:** A client builds the filter from the label "Planning" and the projects page fails with "Internal server error".
**Rules affected:** `list_projects` R2
**Answer:** bug — per BUG-1570 precedent: only the `ProjectStatusEnum` values are accepted, refused by request validation (422; 400 today per BUG-461); the manager keeps its conversion.
**Resolution:** 🐞 BUG-1961 (pattern `unvalidated-code-input`). Fix in `app/api/v1/endpoints/projects.py` (type the query parameter). Rules: `list_projects` R2.

### P5. A negative budget is accepted — 🐞 BUG-1962
**Background:** `budget` is money (`Numeric(15,2)`). Negative amounts on entry were ruled out for stock values and maintenance costs (BUG-1079, owner; BUG-1158, owner).
**What happens today:** `budget: -5` is stored on create (verified) and on update.
**Example:** A typo gives "Line 3 refit" a budget of −50 000, which then feeds any budget-versus-cost view.
**Rules affected:** `create_project` R5, `update_project` R8
**Answer:** bug — per BUG-1158 precedent: `ge=0` on `budget` of `ProjectCreate` and `ProjectUpdate` only (not on the response, so stored negatives stay readable); `0` and `null` accepted; nothing written.
**Resolution:** 🐞 BUG-1962 (pattern `unvalidated-numeric-range`). Rules: `create_project` R5, `update_project` R8.

### P6. A budget with more than 2 decimals is rounded silently and logged as typed — 🐞 BUG-1963
**Background:** The column keeps 2 decimals and Postgres rounds half up on store (HR-15 holds). Same root cause as BUG-1157 (maintenance cost, owner).
**What happens today:** `1000.005` is stored `1000.01`; `1e20` fails at the flush (500). On update the change entry records the typed value: `1000.00 → 1000.5`, `1000.00 → 1000.005` (read).
**Example:** A budget typed as `2500.505` is saved as `2500.51`, and the activity log says it was set to `2500.505`.
**Rules affected:** `create_project` R5, `update_project` R8, `_format_field_value` R2
**Answer:** bug — per BUG-1157 precedent: `ProjectCreate` / `ProjectUpdate` refuse a budget with more than 2 decimal places or more than 13 integer digits (422), nothing written; the change entry records the stored form with two decimals (`1000.00 → 1000.50`).
**Resolution:** 🐞 BUG-1963 (pattern `unbounded-decimal-input`). Rules: `create_project` R5, `update_project` R8.

### P7. The activity log reads one profile per entry — 🐞 BUG-1964
**Background:** Each entry comes with the profile of whoever did it. `list_events` reads that profile entry by entry, the same person again each time (project event DAO FU-2). Same root cause as BUG-1141, BUG-1712.
**What happens today:** 200 entries by one person take 202 reads, plus the access check (read). The log is not paged.
**Example:** A two-year project's activity tab makes several hundred database reads where three would do. The page looks the same.
**Rules affected:** `list_events` R4
**Answer:** bug — per BUG-1141 precedent: performers read together, at most three reads after the access check; the result unchanged.
**Resolution:** 🐞 BUG-1964 (pattern `n-plus-one-read`). Rules: `list_events` R4.

### New questions

### Q1. OWNER — A private project answers "no access" (403), while its discussions and files answer "not found" (404) — ✅ intended (answered by the owner (2026-11-04), OQ-18)
**Background:** A project set to `invited_only` opens only for the workspace owner, an active `owner` / `ground-team-manager`, its creator and its project members. For anyone else, every project page (details, members, activity, visibility, edit, delete, and every component page through its project) answers **403 "You do not have access to this project"**. A missing project, or another workspace's, answers **404 "Project with ID <id> not found"**. For the same private project, the owner's OQ-5 answer gives **404** on its discussions (BUG-1867), attachments (BUG-1870) and calendar (BUG-1869), so that a hidden record cannot be told from a missing one. The workspace switch made the same choice: a non-member gets the same 404 as for a missing workspace (BUG-440). This is about who learns what exists, so it is the owner's call.
**What happens today:** A `ground-team` member opening project 42, private and not theirs, gets 403 (verified). Opening project 43, which does not exist, gets 404. So ids reveal which private projects exist, and the project page and its discussion disagree about the same project.
**Example:** Mia (ground team) follows a link to `/projects/42`. The page says "You do not have access to this project". The discussion panel for the same project says "Record not found". Mia now knows a private project 42 exists, and the two messages contradict each other.
**Rules affected:** `require_project_access` R2, `require_component_access` R3
**Suggested answer:** `bug — a project the caller may not open answers exactly as a missing one: 404 "Project with ID <id> not found"; a component of such a project answers 404 "Project component not found", as a missing component (so the component id does not reveal its project's id)`. One rule for every page of a private project, matching OQ-5 and BUG-440. Help tickets are not part of this: OQ-8 already set 403 for them.
**Alternatives:** (a) `intended` — keep 403 on the project pages (it tells a member to ask for access) and accept that the discussion, file and calendar answers differ. (b) 404 for projects **and** help tickets, one rule for every record with its own visibility.
**Answer:** intended — keep 403 on project pages; discussions, files and calendar entries still answer 404 under OQ-5 (answered by the owner (2026-11-04), OQ-18).
**Resolution:** no bug; reserved BUG-1965 is unused. Rules `require_project_access` R2 ✅ and `require_component_access` R3 ✅ unchanged (403).

### Q2. Choosing a factory and a status shows every status of that factory — 🐞 BUG-1960 (decided by Claude under the reviewer's delegation, 2026-11-04)
**Background:** The projects page has a factory picker and a status picker and sends both. The manager uses the factory filter when one is given and then ignores the status. No money, stock or order flow is involved.
**What happens today:** `list_projects(factory_id=F1, status="PLANNING")` returned F1's `COMPLETED` project too (verified).
**Example:** On the Projects page, Ana picks "Dhaka Plant" and "Planning". The list also shows the plant's completed and cancelled projects, and the status picker seems broken.
**Rules affected:** `list_projects` R1a
**Answer:** bug — when both are given, both filters apply (factory AND status), in the query, before paging; either alone as today.
**Resolution:** 🐞 BUG-1960 (pattern `silently-ignored-input`). Fix in `list_projects` (and a DAO read that takes both, or one filtered query). Rules: `list_projects` R1a.

Checked and **not** violated: **HR-2** — project names need not be unique. **HR-3** — nothing grouped by free text. **HR-7** — `GET /projects/` requires `1 <= limit <= 1000`, `skip >= 0`. **HR-8** — no `LIKE`. **HR-10** — soft delete, visibility and membership changes are plain changes. A double `add_member` race ends at the unique constraint (`IntegrityError`), harmless. **HR-15** — the database rounds `budget` half up; no Python rounding. **HR-16** — `create_project` finds the factory in the workspace (another workspace's → 404, as missing); `add_member` requires an active membership of the workspace; `require_component_access` finds the component in the workspace. **HR-4 / standing decision** on `update_project`, `set_visibility`, `delete_project`: their explicit 400s for a deleted project stay (BUG-1278 keeps `delete_project`'s; the other two are the same kind of refusal, decided by Claude under the reviewer's delegation, 2026-11-04).

## Follow-ups for other reviews
| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Project service / endpoint** (`app/services/project_service.py`, `app/api/v1/endpoints/projects.py`; no spec yet) | (a) BUG-1961's fix is the endpoint's query type. (b) `POST /projects/` catches every non-HTTP exception and answers 400 with `str(e)`: a database error's text reaches the client (pattern `internal-error-leak`, BUG-037), to be logged by that spec. (c) The members endpoint reads each member's profile and membership one by one (pattern `n-plus-one-read`). (d) BUG-1954's `include_deleted` has no API caller until someone needs it. | reading the callers |
| FU-2 | **Permissions feature** (`docs/future/permissions.md`, Added during the sweep) | Anyone who may open a project may also edit it, delete it, change its visibility, and add or remove members (no role check). A `ground-team` member of a workspace-visible project can make it private and lock out everyone but privileged roles, its creator and its members. Recorded there, not asked. | reading the code |
| FU-3 | **Notifications feature** (`docs/future/notifications.md`, Added during the sweep) | Adding someone to a project, removing them, or making a project private notifies nobody. Recorded there. | reading the code |

## Overview
`ProjectManager` holds the business rules for projects (planned jobs of a factory): who may open a project (`visibility` `workspace` or `invited_only`), create / edit / soft-delete, project members, and the project activity log (`project_events`). Callers: `ProjectService` (every public method), the project component, component item / note / task, miscellaneous cost and ledger services (`require_project_access`, `require_component_access`, `can_access_project`, `log_event`, `log_for_component`), and `AttachmentManager` (`log_event`). It never commits. Errors are `fastapi.HTTPException`. It protects workspace isolation, the private-project rule, and a complete activity log.

**Callables:** 21 specified · 3 not specified
**Externals to mock:** `utcnow` as imported in `app.managers.project_manager` (`updated_at`, `deleted_at`). `created_at` of projects and events and `assigned_at` of members are Python column defaults: assert they are set, not their value.
**Integration-only behavior:** the HTTP status mapping of `HTTPException`; the endpoint's query validation (BUG-1961); `POST /projects/`'s catch-all (FU-1 (b)).

**Facts for the test designer**
- Import: `from app.managers.project_manager import ProjectManager, project_manager, PRIVILEGED_ROLES, PROJECT_LOG_FIELDS`. All parameters positional-or-keyword, in the order of each signature below. `ProjectManager()` takes no argument.
- `PRIVILEGED_ROLES == {"owner", "ground-team-manager"}`.
- `PROJECT_LOG_FIELDS` (order matters for the change list): `name` "Name", `description` "Description", `budget` "Budget", `deadline` "Deadline", `start_date` "Start date", `end_date` "End date", `priority` "Priority", `status` "Status", `factory_id` "Factory", `visibility` "Visibility". `ProjectUpdate` has no `factory_id` and no `visibility` field, so those two labels are unreachable from `update_project` (only through `_collect_field_changes` directly).
- Visibility values (`ProjectVisibilityEnum`): `"workspace"` (every member) and `"invited_only"` (private). There is no `"private"`.
- **Who may open a private project** (`can_access_project`, as cited by the discussion and calendar specs): (1) the workspace owner (`workspaces.owner_user_id`), (2) an `active` member of the workspace with role `owner` or `ground-team-manager`, (3) the project's `created_by`, (4) anyone with a `project_members` row for that project in that workspace (raw: their workspace status is not looked at). Platform admins are not in the list.
- Model facts: project DAO spec (table `projects`; `updated_at` also has a Python `onupdate=utcnow`; `start_date`, `end_date`, `deadline`, `created_at`, `deleted_at` are `timestamp without time zone`). `project_members`: project member DAO spec (unique `(project_id, user_id)`). `project_events`: project event DAO spec (`metadata` attribute `metadata_json`; Python `None` passed explicitly is stored as JSON `null`, read back `None`; `event_type` `String(50)`).
- `HTTPException` is `fastapi.HTTPException`: assert `.status_code` and `.detail`.

**Notes for the test designer**
- Build directly (add + flush): `Factory(workspace_id, name, abbreviation)`, `Project(workspace_id, factory_id, name, description, visibility=…, created_by=…)`, `WorkspaceMember(workspace_id, user_id, role, status="active")`, `ProjectMember(workspace_id, project_id, user_id)`, `ProjectComponent(workspace_id, project_id, name)`. Set `workspace.owner_user_id`. `autoflush=False`: flush before calling.
- For list assertions compare **sets** of ids except in the ordering cases (BUG-1957: names "Zulu", "apple", "Banana" inserted in that order; intended "apple", "Banana", "Zulu" → strict xfail, since the `id` order today is deterministic).
- **BUG-1958:** a non-privileged caller, 3 private projects they may not open created first, then 2 they may; `limit=2` → intended both visible ones; today `[]` → strict xfail.
- **BUG-1964:** count statements with an SQLAlchemy `before_cursor_execute` listener; 5 events by one person; intended ≤ 3 statements after the access check → strict xfail.
- **BUG-1192:** `log_event` with another workspace's project id → intended 404 and no row → strict xfail.
- **Q1 (answered, OQ-18):** the 403 rules are intended; plain cases, no xfail.

## Not specified
- `ProjectManager.__init__` — wires `project_dao`, `factory_dao`, `project_event_dao` (`event_dao`), `project_member_dao` (`member_dao`); no logic.
- `project_manager` — module-level singleton.
- `PRIVILEGED_ROLES`, `PROJECT_LOG_FIELDS` — constants (Facts).

---

## `ProjectManager._visibility_value(project)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: `can_access_project`, `set_visibility`)

**Rules:**
- **R1.** `project.visibility` `None` → `"workspace"`; a `ProjectVisibilityEnum` → its value; any other value → `str(value)` as stored (`"invited_only"`, or any other text, unchanged).

---

## `ProjectManager._is_workspace_owner(session, user_id, workspace_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `_is_privileged`)

**Rules:**
- **R1.** `True` exactly when the workspace exists (base `get`, raw) and its `owner_user_id` equals `user_id`; `False` for an unknown workspace, an owner-less workspace, or another user. The owner's membership row is not looked at.

---

## `ProjectManager._is_privileged(session, user_id, workspace_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `can_access_project`, `list_projects`)

**Rules:**
- **R1.** `True` for the workspace owner (`_is_workspace_owner` R1).
- **R2.** Otherwise `True` exactly when the user's membership of that workspace (workspace member DAO `get_by_workspace_and_user` R1–R3) has `status == "active"` and `role` in `PRIVILEGED_ROLES`, both compared exactly. `suspended`, `invited`, `inactive`, `"Active"`, `"Owner"`, `"manager"`, `"finance"`, `"ground-team"`, or no membership → `False`.

---

## `ProjectManager.can_access_project(session, project, user_id, workspace_id)`
**Shape:** compute · **Persistence:** reads
**Visibility:** public (used by: `require_project_access`, `list_projects`; the component, item, note and task services and the miscellaneous cost service for their workspace-wide lists)

**Purpose:** Whether a user may open a project.

**Rules:**
- **R1.** A project whose visibility (`_visibility_value`) is `"workspace"` may be opened by anyone (the caller has passed the workspace gate). No further read.
- **R2.** Any other visibility is private: allowed when `_is_privileged` is true, or `project.created_by == user_id`, or a `project_members` row exists for (project, user, `workspace_id`) (project member DAO `get_by_project_and_user` R1–R4: raw; a member who left the workspace still counts, BUG-1280 is the workspace manager's). Otherwise `False`.
- **R3.** The project's own `workspace_id` and `is_deleted` are not looked at here; a private project with `created_by` `None` is open to privileged users and members only.

---

## `ProjectManager._get_project_or_404(session, project_id, workspace_id)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** internal (used by: `require_project_access`, `remove_member`)

**Rules:**
- **R1.** Returns the project with that id in that workspace (base `get_by_id_and_workspace`: raw, a soft-deleted project included). Unknown id, `0`, or another workspace's → `HTTPException(404, "Project with ID <project_id> not found")`.

---

## `ProjectManager.require_project_access(session, project_id, workspace_id, user_id)`
**Shape:** get-or-404 · **Persistence:** reads
**Visibility:** public (used by: every project method below except `create_project`, `list_projects`, `log_*`; the component / item / note / task / miscellaneous cost / ledger services)

**Purpose:** The project, if it exists in the workspace and the user may open it.

**Rules:**
- **R1.** Not in the workspace → `_get_project_or_404` R1 (404), before any access check.
- **R2.** Found, and `can_access_project` false → `HTTPException(403, "You do not have access to this project")`. ✅ (Q1, owner, OQ-18: intended; the project's discussions, files and calendar entries answer 404 instead, under OQ-5.)
- **R3.** [BUG-1278, BUG-1954] A soft-deleted project → 404 `Project with ID <project_id> not found`, as a missing one, for its members (`list_members`, `add_member`, `remove_member`), its components (through `require_component_access` and the component services) and `get_project`. *(Today: it passes, and is returned.)* `list_events`, `update_project`, `set_visibility` and `delete_project` still receive it (history; their own 400s). *(Requires a new option, e.g. `include_deleted`.)*
- **R4.** Otherwise the project is returned.

**Errors:** R1, R2, R3.

---

## `ProjectManager.require_component_access(session, component_id, workspace_id, user_id)`
**Shape:** get-or-404 · **Persistence:** reads
**Visibility:** public (used by: component, item, note, task, miscellaneous cost and ledger services)

**Returns:** the component's `project_id`.

**Rules:**
- **R1.** The component is found in the workspace (base `get_by_id_and_workspace`; components have no soft delete). Unknown id, `0`, or another workspace's → `HTTPException(404, "Project component not found")`.
- **R2.** Then its project passes `require_project_access` R1–R4 with the same user: a component of a deleted project → 404 `Project with ID <project_id> not found` (BUG-1278, as R3 there).
- **R3.** A component of a private project the user may not open → 403 as `require_project_access` R2. ✅ (Q1, owner, OQ-18.)
- **R4.** A component whose stored `project_id` is not a project of the workspace (invalid data, HR-16; writes refused by BUG-1012 / BUG-1013) → 404 `Project with ID <that id> not found`.

---

## `ProjectManager._format_field_value(value)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: `_collect_field_changes`)

**Rules:**
- **R1.** `None` → `None`. Anything with a `value` attribute (an enum) → `str(value.value)` (`ProjectStatusEnum.COMPLETED` → `"COMPLETED"`). A `datetime` → its date only, `YYYY-MM-DD`.
- **R2.** Anything else → `str(value)`: `Decimal("1000.00")` → `"1000.00"`, `Decimal("1000.5")` → `"1000.5"`, `"Line 3"` → `"Line 3"`, `7` → `"7"`. (BUG-1963 makes the logged budget the stored two-decimal form; the formatter itself may stay.)

---

## `ProjectManager._collect_field_changes(record, update_dict, fields)`
**Shape:** compute · **Persistence:** pure · **Visibility:** internal (used by: `update_project`)

**Returns:** a `list` of `{"field", "label", "from_value", "to_value"}`.

**Rules:**
- **R1.** One entry per key of `fields`, in `fields`' order, that is present in `update_dict` and whose new value differs (`!=`) from the record's current attribute; keys of `update_dict` not in `fields` are ignored; equal values give no entry; empty `update_dict` → `[]`.
- **R2.** `from_value` / `to_value` are `_format_field_value` of the old and new values. Values compare as Python values: `Decimal("1000.00") == Decimal("1000")` (no entry); a deadline moved by hours within one day **is** an entry, logged as the same date on both sides (`"2026-03-01"` → `"2026-03-01"`).

---

## `ProjectManager.log_for_component(session, component_id, workspace_id, event_type, description, performed_by=None, metadata=None)`
**Shape:** event-log · **Persistence:** writes
**Visibility:** public (used by: component, item, note, task and miscellaneous cost services, after their access checks)

**Purpose:** Write a project event about one of its components.

**Returns:** the new `ProjectEvent`, or `None`.

**Rules:**
- **R1.** A component not found in the workspace (unknown, `0`, another workspace's) → returns `None`, writes nothing, raises nothing.
- **R2.** Otherwise one event is written as `log_event` on the component's `project_id`, with metadata = a copy of `metadata` (or `{}`) plus `component_id` and `component_name` (the component's `id` and `name`) **unless the caller's metadata already has those keys** (the caller's values win). The caller's dict is not changed. Even with no caller metadata the stored metadata is a dict, never `null`.

---

## `ProjectManager.log_event(session, project_id, workspace_id, event_type, description, performed_by=None, metadata=None)`
**Shape:** event-log · **Persistence:** writes
**Visibility:** public (used by: this manager, `log_for_component`, the component services, the miscellaneous cost service, `AttachmentManager`)

**Returns:** the new `ProjectEvent`, flushed.

**Rules:**
- **R1.** One `project_events` row with exactly the given `workspace_id`, `project_id`, `event_type`, `description`, `performed_by`, and `metadata_json = metadata` (`None` → JSON `null`, read back `None`); `created_at` set by the column default. Flushed, not committed.
- **R2.** [BUG-1192] (HR-16) A `project_id` that is not a project of `workspace_id` (unknown, `0`, another workspace's) → `HTTPException(404, "Project with ID <project_id> not found")`, nothing written. *(Today: written under the caller's workspace, verified; an unknown id fails at the flush with `IntegrityError`.)*
- **R3.** A soft-deleted project of the workspace is logged to (history; `delete_project` logs its own event on it).
- **R4.** An `event_type` longer than 50 characters fails at the flush (`DataError`); callers pass fixed codes.

---

## `ProjectManager.list_events(session, project_id, workspace_id, user_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `ProjectService.list_events` ← `GET /projects/{id}/events/`)

**Returns:** a `list` of `(ProjectEvent, Profile | None)`.

**Rules:**
- **R1.** Access as `require_project_access` R1, R2 (404 / 403).
- **R2.** A soft-deleted project's log is still answered (standing decision; BUG-1278 leaves this open).
- **R3.** The events are project event DAO `get_by_project` R1–R7 (newest first, `id` tie-break, no paging), each paired with the profile of `performed_by`, or `None` when `performed_by` is `None` (or the profile is gone).
- **R4.** [BUG-1964] (P7) Performers are read together: at most three statements after the access check, whatever the number of entries; the result is unchanged. *(Today: one profile read per entry with a performer.)*

---

## `ProjectManager.list_members(session, project_id, workspace_id, user_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `ProjectService.list_members`)

**Rules:**
- **R1.** Access as `require_project_access` R1–R3 (a deleted project → 404, BUG-1278).
- **R2.** The members are project member DAO `get_by_project` R1–R7 (BUG-1274 order).

---

## `ProjectManager.add_member(session, project_id, member_user_id, workspace_id, assigned_by)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `ProjectService.add_member`)

**Returns:** the new `ProjectMember`, flushed.

**Rules:**
- **R1.** `assigned_by` must pass `require_project_access` R1–R3 (a deleted project → 404, BUG-1278). Anyone who may open the project may add members, whatever their role (FU-2).
- **R2.** The person must have a membership of the workspace with `status == "active"` exactly: none (an unknown user, a member of another workspace only), `suspended`, `invited`, `inactive` → `HTTPException(400, "User is not an active member of this workspace")`, nothing written.
- **R3.** Already a project member (any row for project, user, workspace) → `HTTPException(409, "User is already a member of this project")`, nothing written. The creator is a member from `create_project`, so adding them again is 409.
- **R4.** Otherwise one `project_members` row (`workspace_id`, `project_id`, `user_id = member_user_id`, `assigned_by`, `assigned_at` default) is flushed, then one event `member_added`, description `Added <name> to the project`, performer `assigned_by`, metadata `{"user_id": member_user_id, "user_name": <name>}`, where `<name>` is the profile's `name` (`User #<id>` if no profile, unreachable while the membership exists). Works the same on a workspace-visible project.

---

## `ProjectManager.remove_member(session, project_id, member_user_id, workspace_id, performed_by)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (used by: `ProjectService.remove_member`)

**Rules:**
- **R1.** `performed_by` must pass `require_project_access` R1–R3 (deleted → 404, BUG-1278). Anyone who may open it may remove anyone, themselves included (FU-2).
- **R2.** `member_user_id` equal to the project's `created_by` → `HTTPException(400, "Cannot remove the project creator from members")`, checked before the membership lookup; nothing deleted.
- **R3.** No `project_members` row for that person → `HTTPException(404, "Project member not found")`.
- **R4.** Otherwise the row is deleted (hard) and flushed, then one event `member_removed`, `Removed <name> from the project`, performer `performed_by`, metadata `{"user_id", "user_name"}` as `add_member` R4. A person who left the workspace can be removed. Returns `None`.

---

## `ProjectManager.set_visibility(session, project_id, visibility, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `ProjectService.set_visibility` ← `PATCH /projects/{id}/visibility/`)

**Rules:**
- **R1.** Access as `require_project_access` R1, R2. Anyone who may open it may change it (FU-2).
- **R2.** A soft-deleted project → `HTTPException(400, "Cannot update deleted project")`, even when the visibility would not change.
- **R3.** Same visibility as now → the project is returned unchanged: no stamp, no event.
- **R4.** Otherwise `visibility` = the new value, `updated_by = user_id`, `updated_at = utcnow()`, flushed; then one event `visibility_updated`, description `Changed visibility from <old> to <new>` (values such as `workspace`, `invited_only`), performer `user_id`, metadata `{"changes": [{"field": "visibility", "label": "Visibility", "from_value": <old>, "to_value": <new>}]}`. Returns the project.

---

## `ProjectManager.create_project(session, project_data, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `ProjectService.create_project` ← `POST /projects/`)

**Returns:** the new `Project`, flushed.

**Rules:**
- **R1.** The factory must be found in the workspace (factory DAO `get_by_id_and_workspace`, raw): unknown, `0`, or another workspace's → `HTTPException(404, "Factory with ID <factory_id> not found")`, nothing written.
- **R2.** A soft-deleted factory → `HTTPException(400, "Cannot create project for deleted factory")`; an inactive but live factory is accepted.
- **R3.** The project row gets every `ProjectCreate` field (`factory_id`, `name`, `description`, `budget`, `deadline`, `priority` default `LOW`, `status` default `PLANNING`, any status allowed, `COMPLETED` included), plus `workspace_id`, `created_by = user_id`, `is_active = True`, `is_deleted = False`, `visibility = "workspace"`; `start_date`, `end_date`, `updated_*`, `deleted_*` empty; `created_at` set.
- **R3a.** The creator gets a `project_members` row (`assigned_by = user_id`), and one event `created`, description `Created project "<name>"`, performer `user_id`, metadata `null`, is written. All flushed, not committed.
- **R4.** [BUG-1951] (HR-1) `name` is stored trimmed; `""` or only spaces is refused by `ProjectCreate` (422), nothing written. *(Today: stored as typed; `"  "` accepted, verified.)* `description` is kept as typed (`""` accepted).
- **R5.** [BUG-1962] `budget < 0` is refused by `ProjectCreate` (422); `0` and `null` accepted. [BUG-1963] more than 2 decimal places or more than 13 integer digits refused (422). *(Today: `-5` stored, verified; `1000.005` stored `1000.01`; `1e20` fails at the flush.)*
- **R6.** ✅ The plan's `max_projects` is not checked (intended for now; factory manager Q4).

---

## `ProjectManager.get_project(session, project_id, workspace_id, user_id)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (used by: `ProjectService.get_project`)

**Rules:**
- **R1.** As `require_project_access` R1, R2, R4.
- **R2.** [BUG-1954] (HR-4) A soft-deleted project → 404 `Project with ID <id> not found`; an `include_deleted=True` option returns it *(requires a new parameter; no API caller yet)*. *(Today: returned, verified.)*

---

## `ProjectManager.list_projects(session, workspace_id, user_id, factory_id=None, status=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `ProjectService.list_projects` ← `GET /projects/`)

**Returns:** a `list` of `Project`.

**Rules:**
- **R1.** With `factory_id` the rows are project DAO `get_by_factory` R1–R5 (BUG-1444, 1445, 1446). [BUG-1959] (P3) only `None` means no factory filter; `0` filters and returns `[]`. *(Today: `0` → no filter, verified.)*
- **R1a.** [BUG-1960] (Q2) `factory_id` and `status` together apply both (AND), before paging. *(Today: the status is ignored, verified.)*
- **R2.** With `status` (and no `factory_id`) the rows are DAO `get_by_status` R1–R5, the string converted by `ProjectStatusEnum(status)`: `"PLANNING"` works; `""` means no filter. [BUG-1961] (P4) a value that is not one of the five is refused before the manager by request validation (422). *(Today: `ValueError` from the manager, 500 at the API; verified.)*
- **R3.** [BUG-1955] (HR-4) Without either filter, soft-deleted projects are not listed and take no place on the page. *(Today: listed, verified.)* Inactive projects are listed.
- **R4.** [BUG-1956] (P2) Without either filter, projects whose factory is soft-deleted are not listed. *(Today: listed.)*
- **R5.** [BUG-1957] (HR-6) Without either filter, ordered by `name` case-insensitive, then `id`, before paging. *(Today: `id` order.)* Paging as base `get_by_workspace` R2, R5, R6 (default 100; negative → `DataError`).
- **R6.** A privileged caller (`_is_privileged`) gets the page as read, private projects included.
- **R7.** Any other caller gets only the projects `can_access_project` allows. [BUG-1958] (HR-5) That filter is applied before `skip` / `limit`, so a page is short only at the end. *(Today: after paging, in Python; a page of private projects comes back `[]` though visible ones follow.)*

---

## `ProjectManager.update_project(session, project_id, project_data, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `ProjectService.update_project` ← `PUT /projects/{id}/`)

**Returns:** the project, flushed.

**Rules:**
- **R1.** Access as `require_project_access` R1, R2; anyone who may open it may edit it (FU-2). A soft-deleted project → `HTTPException(400, "Cannot update deleted project")`, nothing written.
- **R2.** Only fields sent with a value are applied (DAO `update` with a dict). Fields not sent are unchanged.
- **R2a.** [BUG-1953] (P1) An explicit `null` clears `budget`, `deadline`, `start_date`, `end_date`; `null` for `name`, `description`, `priority`, `status` is refused by `ProjectUpdate` (422), nothing written. *(Today: every `null` is dropped and the old value stays, verified for `budget`.)*
- **R3.** Any status may follow any status (`CANCELLED` → `IN_PROGRESS` included); dates are not checked against each other.
- **R4.** Changes are computed before writing, by `_collect_field_changes` over `PROJECT_LOG_FIELDS`. If the status changed: one event `status_updated`, `Changed project status`, metadata `{"changes": [<the status entry>]}`. If any other field changed: one event `updated`, `Updated project details`, metadata `{"changes": [<the other entries, in PROJECT_LOG_FIELDS order>]}`. Both changed → both events, status first. Performer `user_id`. Nothing changed → no event.
- **R5.** `factory_id` and `visibility` cannot be changed here (not in `ProjectUpdate`).
- **R6.** Returns the project with the new values.
- **R7.** [BUG-1951] (HR-1) A sent `name` is stored trimmed; blank refused (422). *(Today: as typed.)*
- **R8.** [BUG-1962, BUG-1963] `budget` as `create_project` R5; the change entry shows the stored form with two decimals (`"1000.00"` → `"1000.50"`). *(Today: negatives stored; entry shows the typed form `"1000.5"`.)*
- **R9.** [BUG-1952] (HR-9) `updated_by = user_id` and `updated_at = utcnow()` are written only when at least one field changes value. *(Today: always, even for `{}` or the same values, verified.)*

---

## `ProjectManager.delete_project(session, project_id, workspace_id, user_id)`
**Shape:** soft-delete · **Persistence:** writes · **Visibility:** public (used by: `ProjectService.delete_project` ← `DELETE /projects/{id}/`)

**Rules:**
- **R1.** Access as `require_project_access` R1, R2; anyone who may open it may delete it (FU-2).
- **R2.** Already deleted → `HTTPException(400, "Project is already deleted")`.
- **R3.** Otherwise `is_deleted = True`, `deleted_at = utcnow()`, `deleted_by = user_id`, flushed; `is_active`, members, components and events untouched; then one event `deleted`, description `Deactivated project "<name>"`, performer `user_id`, metadata `null`. Returns the project. Nothing is refused because of components, costs or orders (hidden, not cascaded).

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 27, 29–40 | constants | Facts |
| 55–56 | visibility `None` | `_visibility_value` R1 |
| 57–59 | enum → value; else `str` | `_visibility_value` R1 |
| 62–63 | workspace exists and owner matches | `_is_workspace_owner` R1 |
| 66–67 | owner → true | `_is_privileged` R1 |
| 68–71 | membership; `active`; role in set | `_is_privileged` R2 |
| 80–81 | `"workspace"` → true | `can_access_project` R1 |
| 82–85 | privileged; creator | `can_access_project` R2, R3 |
| 86–93 | project member row | `can_access_project` R2 |
| 101–109 | raw lookup; falsy → 404 | `_get_project_or_404` R1; `require_project_access` R3 (BUG-1278, BUG-1954) |
| 118 | find | `require_project_access` R1 |
| 119–124 | access refused → 403 (Q1); else return | `require_project_access` R2, R4 |
| 135–142 | component not found → 404 | `require_component_access` R1 |
| 143–146 | project access; return `project_id` | `require_component_access` R2, R3, R4 |
| 149–150 | `None` | `_format_field_value` R1 |
| 151–152 | has `value` | `_format_field_value` R1 |
| 153–155 | `datetime` → date; else `str` | `_format_field_value` R1, R2 |
| 164–166 | each field; not in dict → skip | `_collect_field_changes` R1 |
| 167–170 | equal → skip | `_collect_field_changes` R1, R2 |
| 171–177 | entry | `_collect_field_changes` R2 |
| 191–195 | component not found → `None` | `log_for_component` R1 |
| 196–207 | metadata copy; `setdefault`; `log_event` | `log_for_component` R2 |
| 219–229 | row; flush (no project check, BUG-1192) | `log_event` R1–R4 |
| 238 | access | `list_events` R1, R2 |
| 239–245 | events; profile per event if performer (BUG-1964) | `list_events` R3, R4 |
| 254–257 | access; members | `list_members` R1, R2 |
| 267 | access | `add_member` R1 |
| 268–275 | not member / not `active` → 400 | `add_member` R2 |
| 276–286 | existing → 409 | `add_member` R3 |
| 287–306 | row; profile name / fallback; event | `add_member` R4 |
| 316–317 | access; re-read | `remove_member` R1 |
| 318–322 | creator → 400 | `remove_member` R2 |
| 323–333 | no row → 404 | `remove_member` R3 |
| 334–346 | name; delete; event | `remove_member` R4 |
| 356 | access | `set_visibility` R1 |
| 357–361 | deleted → 400 | `set_visibility` R2 |
| 362–363 | same → return | `set_visibility` R3 |
| 364–386 | write; event | `set_visibility` R4 |
| 395–402 | factory not found → 404 | `create_project` R1 |
| 403–407 | deleted factory → 400 | `create_project` R2 |
| 409–416 | dump; fixed fields; create (no trim, BUG-1951; no budget bounds, BUG-1962/1963; no plan limit) | `create_project` R3–R6 |
| 418–434 | creator member; event | `create_project` R3a |
| 443 | access | `get_project` R1, R2 |
| 455–462 | `if factory_id:` (0 → no filter, BUG-1959) | `list_projects` R1 |
| 463–471 | `elif status:`; enum (ValueError, BUG-1961); status ignored with factory (BUG-1960) | `list_projects` R1a, R2 |
| 472–475 | raw `get_by_workspace` (BUG-1955, 1956, 1957) | `list_projects` R3–R5 |
| 477–478 | privileged → page | `list_projects` R6 |
| 480–483 | per-project filter after paging (BUG-1958) | `list_projects` R7 |
| 493–499 | access; deleted → 400 | `update_project` R1 |
| 501 | `exclude_unset`, `exclude_none` (BUG-1953) | `update_project` R2, R2a, R5 |
| 502 | changes | `update_project` R4 |
| 503–508 | stamps always (BUG-1952); update | `update_project` R6, R9 |
| 510–532 | changes? status / other events | `update_project` R4 |
| 543–549 | access; already deleted → 400 | `delete_project` R1, R2 |
| 551–565 | stamp; event | `delete_project` R3 |
| 568 | singleton | Not specified |
