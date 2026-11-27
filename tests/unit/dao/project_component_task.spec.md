# Spec — `app/dao/project_component_task.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-03.** No owner answer in this round. **Delegated:** P1 accepted as suggested, decided by Claude under the reviewer's delegation (2026-11-03). It is not the owner's own answer. The house-rule line stands.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Things of a soft-deleted parent are hidden by the parent's state, their own rows untouched. Raw lookups stay raw (HR-4 scope). HR-16: a row linking to another workspace's row is invalid data.
>
> **Verified by running** (throwaway scripts `cat1.py`, `v_proj.py` with the harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints and indexes; defaults; open and completed tasks and notes on one component, another component, a row of workspace B on a component of A; `is_note` `None` / `True` / `False` on `get_by_component`, default / `True` / `None` on `get_incomplete_tasks`; unknown component; order of "Zulu", "apple", "Banana" under a forced sequential scan before and after an update; 104 rows (100); a soft-deleted project. **Read, not run:** `app/services/project_component_task_service.py`, `app/services/project_component_note_service.py`, the two endpoints. **Not run:** anything over HTTP.

## Review
> All answered; applied 2026-11-03.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | The tasks of a component of a deleted project are still read here | intended at the DAO — the services' access guard hides them (BUG-1278) | Claude, delegated |

Decided by a house rule: no sort order on either list (BUG-1447).

### House-rule violations — applied automatically

- **HR-6** `get_by_component` R4, `get_incomplete_tasks` R4 — no `ORDER BY`. These are the DAO's own paged queries behind `GET /project-component-tasks/?project_component_id=…` and `GET /project-component-notes/?project_component_id=…`. Verified under a forced sequential scan: "Zulu", "apple", "Banana" came back in insertion order, then with "Zulu" last after an update of it. Intended: `name` case-insensitive ascending, then `id` ascending, before `skip` / `limit` (HR-6 default; BUG-1275 precedent for the components themselves).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1447 (pattern `unordered-pagination`; one bug for both methods). Rules: `get_by_component` R4, `get_incomplete_tasks` R4.

Checked and **not** a new line here: **HR-4** — tasks have no soft-delete column; components are hard-deleted; the project's state is P1. **HR-5** — every filter is in the query. **HR-7** — both endpoints declare `limit` with `le=100` and no lower bound (FU-1 (a)). **HR-8** — no `LIKE`. **HR-16** — both lists filter on the row's own `workspace_id` only (R1 of each); a row of workspace B on a component of A is listed for B, not for A; writers are the services (FU-1 (b)). **HR-9, HR-10** — the DAO writes nothing of its own. **HR-1, HR-2, HR-3, HR-15** — no names written here.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-03)

### P1. Tasks of a component of a deleted project are still read here — ✅ intended at the DAO
**Background:** A task or note belongs to a project component; the component belongs to a project; projects are soft-deleted. Both lists are called only after `ProjectManager.require_component_access`, whose project lookup is raw today; BUG-1278 already makes that guard answer 404 `Project with ID <id> not found` for a component of a deleted project. The project member and component DAOs kept their reads raw for the same reason (BUG-1278).
**What happens today:** Both lists return the tasks of a component of a soft-deleted project. (Verified.)
**Example:** Project "Line 3" is deleted. Its component "Conveyor" has 4 tasks; `GET /project-component-tasks/?project_component_id=<Conveyor>` lists them today. With BUG-1278 fixed the guard answers 404 first.
**Rules affected:** `get_by_component` R6, `get_incomplete_tasks` R6
**Answer:** intended at the DAO — per BUG-1278: the services' guard hides them; these reads stay raw
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): rules unchanged. Rules: `get_by_component` R6 ✅, `get_incomplete_tasks` R6 ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Project component task / note services and endpoints** (`app/services/project_component_task_service.py`, `app/services/project_component_note_service.py`, `app/api/v1/endpoints/project_component_tasks.py`, `…_notes.py`) | (a) **HR-7:** `limit` is `Query(100, le=100)` with no `ge=1` (BUG-642 pattern). (b) Without `project_component_id`, both services read the whole workspace (raw `get_by_workspace`, and a query of the note service's own with no order) and drop inaccessible rows in Python **after** paging (HR-5), one component and project lookup per row. (c) `if project_component_id:` treats `0` as "no filter" in the task service. | HR notes |

## Overview
`DAOProjectComponentTask` reads `project_component_tasks`, which holds both a component's tasks and its notes (`is_note`). Callers: `ProjectComponentTaskService.get_tasks` and `ProjectComponentNoteService.get_notes`, each after the component access guard. Writes and single lookups use the inherited `BaseDAO` methods. It is meant to protect workspace isolation through the row's `workspace_id`. It never commits and takes no lock.

**Callables:** 2 specified · 1 not specified (+ inherited `BaseDAO` methods, base spec)
**Externals to mock:** none.
**Integration-only behavior:** none.

**Model facts (table `project_component_tasks`, class `app.models.project_component_task.ProjectComponentTask`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `project_component_id` | Integer NOT NULL, FK `project_components.id` (no cascade) | — |
| `name` | String NOT NULL | — |
| `description` | Text NOT NULL | — |
| `is_completed` | Boolean NOT NULL | `False` (Python only) |
| `is_note` | Boolean NOT NULL | `False` (Python only) |
| `task_priority` | Postgres enum nullable | `NULL` |
| `created_at` | `timestamp` NOT NULL | Python `utcnow()` |

- Indexes: primary key, `ix_project_component_tasks_id`, `ix_project_component_tasks_workspace_id`. No unique constraint, no trigger.

**Notes for the test designer:**
- Use the singleton `project_component_task_dao`. Every parameter after `db` is keyword-only.
- Build factory, project, component and tasks directly (add + flush): `ProjectComponent(workspace_id, project_id, name)`, `ProjectComponentTask(workspace_id, project_component_id, name, description, is_note=…, is_completed=…)`.
- **BUG-1447:** names "Zulu", "apple", "Banana"; force a sequential scan (base spec note) and update "Zulu"; intended "apple", "Banana", "Zulu" → **non-strict** xfail. Every other case compares **sets** of ids.

## Not specified
- `project_component_task_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods (`get_by_workspace`, `get_by_id_and_workspace`, `create`, `update`, `remove` ← the two services) — base spec.

---

## `DAOProjectComponentTask.get_by_component(db, *, project_component_id, workspace_id, is_note=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProjectComponentTaskService.get_tasks` (component given, not `incomplete_only`; `is_note` from the request); `ProjectComponentNoteService.get_notes` (`is_note=True`))

**Purpose:** A component's tasks, notes, or both, one page at a time.

**Returns:** a `list` of `ProjectComponentTask` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `project_component_id` and that `workspace_id`; another component's never. Only the row's `workspace_id` is compared: a row of workspace B on a component of A is returned for B, not for A. An unknown component id or `0` returns `[]`.
- **R2.** `is_note=None` returns tasks and notes; `True` only notes; `False` only tasks.
- **R3.** Completed and open rows are both returned.
- **R4.** [BUG-1447] (HR-6) Ordered by `name` case-insensitive ascending, then `id` ascending, before `skip` / `limit`. *(Today: no ordering is requested.)*
- **R5.** At most `limit` rows after `skip`; defaults: 100 of 104. `limit=0` or `skip` past the end → `[]`; negative values raise `DataError`.
- **R6.** ✅ (P1) The component's project is not looked at: rows of a component of a soft-deleted project are returned.

**Errors:** `sqlalchemy.exc.DataError` for a negative `skip` / `limit`.

**Side effects:** none

---

## `DAOProjectComponentTask.get_incomplete_tasks(db, *, project_component_id, workspace_id, is_note=False, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProjectComponentTaskService.get_tasks` with `incomplete_only`; `is_note` = the request's value, or `False` when not given)

**Purpose:** A component's open tasks (or open notes), one page at a time.

**Returns:** a `list` of `ProjectComponentTask` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that component and workspace, `is_completed = False`, and `is_note` equal to the argument, as `get_by_component` R1 for component and workspace.
- **R2.** The default `is_note=False` gives open tasks; `True` gives open notes. `is_note=None` compares with SQL `NULL` and returns `[]` (the service never passes it).
- **R3.** Completed rows are never returned.
- **R4.** [BUG-1447] (HR-6) Ordered as `get_by_component` R4. *(Today: no ordering is requested.)*
- **R5.** Paging as `get_by_component` R5.
- **R6.** ✅ (P1) The component's project is not looked at, as `get_by_component` R6.

**Errors:** `DataError` for a negative `skip` / `limit`.

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 21–30, 44–45 | keyword-only parameters; defaults | Notes; `get_by_component` R5; `get_incomplete_tasks` R2 |
| 36–39 | workspace AND component; project not read | `get_by_component` R1, R3, R6 |
| 40–41 | `is_note is not None` → filter | `get_by_component` R2 |
| 42 | offset / limit, no `ORDER BY` (BUG-1447) | `get_by_component` R4, R5 |
| 62–67 | workspace, component, `is_completed == False`, `is_note == arg` (`None` → `IS NULL`) | `get_incomplete_tasks` R1, R2, R3, R6 |
| 68–70 | offset / limit, no `ORDER BY` (BUG-1447) | `get_incomplete_tasks` R4, R5 |
| 74 | singleton | Not specified |
