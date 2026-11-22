# Spec — `app/dao/project.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-03.** No owner answer in this round. **Delegated:** P1 accepted as suggested, decided by Claude under the reviewer's delegation (2026-11-03). It is not the owner's own answer. The house-rule lines stand.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Soft-deleted rows are kept but do not show up (owner, 2026-10-10); things of a soft-deleted parent are hidden by the parent's state, their own rows untouched ("hidden, not cascaded", 2026-10-11; factory manager Q2). Raw lookups stay raw (HR-4 scope). HR-16: a row linking to another workspace's row is invalid data.
>
> **Verified by running** (throwaway scripts `cat1.py`, `v_proj.py` with the harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints, indexes and the tables that reference it; defaults; both lists with a live, a soft-deleted, an inactive, a completed project, a project of another factory, a row of workspace B on a factory of A; unknown factory, `0`; status as the enum and as its name, and lowercase (`DataError`); a soft-deleted factory and an inactive one; order of "Zulu", "apple", "Banana" under a forced sequential scan before and after an update, with pages; 104 projects (100); `limit=0`; negative `skip`; no `ORDER BY` and no join in the SQL; a positional call. **Read, not run:** `ProjectManager.list_projects` and the other callers. **Not run:** anything over HTTP.

## Review
> All answered; applied 2026-11-03.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | The project list by status still shows projects of a deleted factory, and the list of a deleted factory still shows its projects | bug — hidden, rows untouched (BUG-1446) | Claude, delegated |

Decided by house rules: no sort order on either list (BUG-1444); deleted projects are listed (BUG-1445).

### House-rule violations — applied automatically

- **HR-6** `get_by_factory` R4, `get_by_status` R4 — no `ORDER BY`. These are the DAO's own paged queries behind `GET /projects/?factory_id=…` and `?status=…`. Verified under a forced sequential scan: "Zulu", "apple", "Banana" came back in insertion order, then with "Zulu" last after an update of it, moving it to page 2 of `limit=2`. Intended: `name` case-insensitive ascending, then `id` ascending, before `skip` / `limit` (HR-6 default; BUG-1275 precedent for components).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1444 (pattern `unordered-pagination`; one bug for both methods). Rules: `get_by_factory` R4, `get_by_status` R4.
- **HR-4** `get_by_factory` R2, `get_by_status` R2 — soft-deleted projects are returned and take places in the page. HR-4 scope: module-specific DAO query methods hide soft-deleted rows. Verified: a project with `is_deleted = True` is in both lists. Intended: never returned, never use up a place in the page (BUG-905 precedent).
**Answer:** bug — per HR-4 (house rule)
**Resolution:** BUG-1445 (pattern `get-returns-soft-deleted`). Rules: `get_by_factory` R2, `get_by_status` R2.

Checked and **not** a new line here: **HR-5** — every filter is in the query; the fixes must stay there. The project manager filters **access** in Python after paging, which is the manager's (FU-1 (a)). **HR-7** — `GET /projects/` already requires `skip >= 0` and `1 <= limit <= 1000`. **HR-8** — no `LIKE`. **HR-16** — both lists filter on the row's own `workspace_id` only: a row of workspace B on a factory of A is listed for B and not for A (R1); no writer of the API produces it (BUG-1010 … BUG-1023 cover project writes). **HR-9, HR-10** — the DAO writes nothing of its own. **HR-1, HR-2, HR-3, HR-15** — no names written; `budget` is not touched here.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-03)

### P1. Projects of a deleted factory are still listed — 🐞 BUG-1446
**Background:** Every project belongs to a factory. Factories are soft-deleted, and deleting one changes none of its projects; the reviewer's decision (factory manager Q2) is that everything in a deleted factory is hidden through the factory's state and comes back when the factory is restored. Machines and their stock got the same fix in their DAO lists (BUG-979, BUG-981).
**What happens today:** Neither list looks at the factory: `get_by_factory` of a deleted factory returns its projects, and `get_by_status` returns projects of deleted factories. (Verified.) An inactive (not deleted) factory hides nothing either, which is right.
**Example:** "Old Plant" is deleted with 3 projects in planning. `GET /projects/?status=PLANNING` still shows the 3, and `GET /projects/?factory_id=<Old Plant>` lists them too.
**Rules affected:** `get_by_factory` R3, R3a, `get_by_status` R3, R3a
**Answer:** bug — per BUG-979 precedent: projects whose factory is soft-deleted are not returned and take no place in the page; an inactive-but-live factory hides nothing; no row is changed, so they are back once the factory is live
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): 🐞 BUG-1446 (pattern `join-ignores-soft-deleted`). Rules: `get_by_factory` R3 (tagged), R3a (untagged), `get_by_status` R3 (tagged), R3a (untagged).

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Project manager** (`app/managers/project_manager.py`, `list_projects`, not yet specified) | (a) **HR-5:** for a member who is not privileged, private projects they cannot access are dropped in Python **after** paging, so pages come back short or empty. (b) Without `factory_id` and `status` the list reads the raw `get_by_workspace`: deleted projects, projects of deleted factories, and only `id` order (BUG-100). The three paths must give the same hiding (BUG-1445, BUG-1446) and the same order (BUG-1444). (c) `if factory_id:` treats `0` as "no filter", and `factory_id` wins over `status` when both are given (the status is ignored). `ProjectStatusEnum(status)` raises `ValueError` for an unknown status (read, not run). | HR lines, P1 |

## Overview
`DAOProject` reads `projects` through two filtered lists: by factory and by status. Callers: `ProjectManager.list_projects` (`GET /projects/` with `factory_id` or `status`). The project's own lookups and writes use the inherited `BaseDAO` methods (`get_by_id_and_workspace` from the project manager, the attachment manager and five project services; `create`, `update`, `get_by_workspace`). It is meant to protect workspace isolation through the row's `workspace_id`. It never commits and takes no lock.

**Callables:** 2 specified · 1 not specified (+ inherited `BaseDAO` methods, base spec)
**Externals to mock:** none.
**Integration-only behavior:** none.

**Model facts (table `projects`, class `app.models.project.Project`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `factory_id` | Integer NOT NULL, FK `factories.id` | — |
| `name` | String NOT NULL | — |
| `description` | Text NOT NULL | — |
| `status` | Postgres enum `projectstatusenum` NOT NULL | `PLANNING` (Python only); values `PLANNING`, `IN_PROGRESS`, `COMPLETED`, `ON_HOLD`, `CANCELLED` |
| `priority` | Postgres enum NOT NULL | `LOW` (Python only) |
| `visibility` | String(20) NOT NULL | `'workspace'` |
| `is_active` | Boolean NOT NULL | `True` (Python only) |
| `is_deleted` | Boolean NOT NULL | `False` (Python only) |
| `created_at` | `timestamp` NOT NULL | Python `utcnow()` |
| others | `budget` Numeric(15,2), dates, audit columns | `NULL` |

- Indexes: primary key, `ix_projects_id`, `ix_projects_workspace_id`. No unique constraint, no trigger. Referenced by `project_components`, `miscellaneous_project_costs` (no cascade), `project_members`, `project_events`, `project_attachments` (ON DELETE CASCADE).
- Factory (`app.models.factory.Factory`): soft delete = `is_deleted = True`, `is_active` unchanged; needs `workspace_id`, `name`, `abbreviation`.

**Notes for the test designer:**
- Use the singleton `project_dao`. Every parameter after `db` is keyword-only.
- Build factories and projects directly (add + flush): `Factory(workspace_id, name, abbreviation)`, `Project(workspace_id, factory_id, name, description, status=…)`.
- **BUG-1444:** names "Zulu", "apple", "Banana" inserted in that order; force a sequential scan (base spec note) and update "Zulu"; intended "apple", "Banana", "Zulu" → **non-strict** xfail. Every other case compares **sets** of ids.
- **BUG-1445 / BUG-1446:** keep a live project under a live factory in the same case so the intended result is "only that one"; today's result includes the hidden row deterministically → **strict** xfail, compared as sets. Soft-deleted project: `is_deleted=True, is_active=False`. Deleted factory: `is_deleted=True`.

## Not specified
- `project_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — not overridden; base spec.

---

## `DAOProject.get_by_factory(db, *, factory_id, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProjectManager.list_projects` ← `GET /projects/?factory_id=…`, with the caller's `skip` / `limit`)

**Purpose:** The projects of one factory, one page at a time.

**Returns:** a `list` of `Project` (possibly empty).

**Rules:**
- **R1.** Returns the projects with that `factory_id` and that `workspace_id`; projects of another factory never. Only the row's `workspace_id` is compared: a row of workspace B on a factory of A is returned for B, not for A. An unknown factory id or `0` returns `[]`.
- **R2.** [BUG-1445] (HR-4) A soft-deleted project (`is_deleted = True`) is not returned and takes no place in the page. *(Today: it is returned.)* An inactive project (`is_active = False`, not deleted) is returned, today and after the fix; so is a project in any status.
- **R3.** [BUG-1446] (P1) When the factory is soft-deleted, `[]` is returned. *(Today: its projects are returned.)*
- **R3a.** Holding today and after the fix: an inactive-but-live factory hides nothing; the call changes no row; once the factory is live again its projects are returned unchanged.
- **R4.** [BUG-1444] (HR-6) Ordered by `name` case-insensitive ascending, then `id` ascending, before `skip` / `limit`. *(Today: no ordering is requested.)*
- **R5.** At most `limit` rows after `skip`; defaults: 100 of 104. `limit=0` or `skip` past the end → `[]`. A negative `skip` / `limit` raises `DataError` (2201X / 2201W).

**Errors:** `sqlalchemy.exc.DataError` for a negative `skip` / `limit`.

**Side effects:** none

---

## `DAOProject.get_by_status(db, *, status, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProjectManager.list_projects` ← `GET /projects/?status=…` without `factory_id`)

**Purpose:** The projects in one status, one page at a time.

**Inputs:** `status` — a `ProjectStatusEnum`; its name as a string (`"PLANNING"`) works too; another spelling (`"planning"`) raises `DataError` (`InvalidTextRepresentation`, pgcode `22P02`).

**Returns:** a `list` of `Project` (possibly empty).

**Rules:**
- **R1.** Returns the projects with that status and that `workspace_id`, of every factory; other statuses never. Only the row's `workspace_id` is compared, as `get_by_factory` R1.
- **R2.** [BUG-1445] (HR-4) Soft-deleted projects are not returned, as `get_by_factory` R2. *(Today: returned.)*
- **R3.** [BUG-1446] (P1) Projects whose factory is soft-deleted are not returned; the others are. *(Today: returned.)*
- **R3a.** As `get_by_factory` R3a.
- **R4.** [BUG-1444] (HR-6) Ordered as `get_by_factory` R4. *(Today: no ordering is requested.)*
- **R5.** Paging as `get_by_factory` R5.

**Errors:** `DataError` for a status the enum does not know, or a negative `skip` / `limit`.

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 18–19, 45–46 | keyword-only parameters; defaults `0` / `100` | Notes; `get_by_factory` R5 |
| 34–39 | workspace AND factory; no `is_deleted` (BUG-1445), no factory state (BUG-1446) | `get_by_factory` R1, R2, R3, R3a |
| 40–42 | offset / limit, no `ORDER BY` (BUG-1444) | `get_by_factory` R4, R5 |
| 65–70 | workspace AND status (enum bind); same gaps | `get_by_status` R1, R2, R3, R3a, Inputs |
| 71–73 | offset / limit, no `ORDER BY` (BUG-1444) | `get_by_status` R4, R5 |
| 77 | singleton | Not specified |
