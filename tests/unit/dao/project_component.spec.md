# Spec — `app/dao/project_component.py`

> **Status:** APPROVED (2026-11-02; no questions, house-rule lines pre-filled)
> **Source commit:** e48a092

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Things of a soft-deleted parent are hidden. HR-16: a row linking to another workspace's row is invalid data. Raw lookups stay raw (HR-4 scope).
>
> **Verified by running** (throwaway scripts `cat1.py`, `v3.py`, `v5.py`, `v7.py`, harness `h.py`, `w.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints, referencing tables; no `ORDER BY`; the order changing after an update under a forced sequential scan; 103 rows, the cap, `limit=0`, `skip` past the end, negative values; unknown ids; another workspace; a soft-deleted project through both service reads, `get_by_id` and `create_component`; paging before the access filter; `project_id=0` through the service. **Not run:** anything over HTTP; the intended behaviour of the bugs below.

## Review
> Nothing open. Overwrite a pre-filled answer only if the house rule should not apply here.

### House-rule violations — applied automatically

- **HR-6** `get_by_project` R3 — pages with no `ORDER BY`. Verified under a forced sequential scan: an update moved the row with the lowest `id` from first to last, onto page 2 of `limit=2`. Intended: `name` case-insensitive ascending, then `id` ascending, before `skip` / `limit`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1275 (pattern `unordered-pagination`). Rules: `get_by_project` R3.
- **HR-7** `get_by_project` R5 — `GET /project-components/` has `limit: Query(100, le=100)` with no lower bound, so `0` gives an empty list and a negative value a database error. Intended: `limit >= 1`, 422 otherwise; the cap of 100 stays.
**Answer:** bug — per HR-7 (house rule)
**Resolution:** BUG-1277 (pattern `missing-limit-lower-bound`, as BUG-1217), one bug with `GET /project-component-items/`. The DAO rule does not change; the check belongs to the endpoint.

Checked and **not** a new line here: **HR-5, HR-8** in this method — filters are in the query, no `LIKE`. **HR-4** — the table has no soft-delete column. A component is hard-deleted (BUG-1196); the project is soft-deleted, FU-1. **HR-9, HR-10** — the DAO only reads. **HR-15** — no money. **HR-16** — the read follows the row. Stored cross-workspace ids are BUG-1012, BUG-1013 and BUG-1016.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Project component service** (`app/services/project_component_service.py`, not yet specified) | (a) **BUG-1278, logged:** the components of a soft-deleted project stay listed, can be opened, and `create_component` adds one (verified). (b) **HR-5, verified, not logged:** without `project_id`, `get_components` pages all components, then drops the ones the user cannot see: a user with 3 visible rows got 0 with `limit=2`. The service's spec must log it with `paginate-before-filter`. (c) `if project_id:` means `project_id=0` lists the whole workspace (verified): pattern `falsy-zero-treated-as-missing`. (d) The workspace list goes through inherited `get_by_workspace`, so it has only `id` order. | standing decision, HR-5 |

## Overview
`DAOProjectComponent` adds one read to `BaseDAO`: the components of one project. Inherited `get_by_id_and_workspace`, `get_by_workspace`, `create`, `update` and `remove` carry most of the use, from `ProjectComponentService`, `ProjectManager`, the attachment manager and the order managers. It protects workspace isolation on that read.

**Callables:** 1 specified · 2 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Model facts (table `project_components`):** `workspace_id` FK CASCADE, `project_id` FK (no action, no index), `name`, `status` (native enum, Python default `PLANNING`), `created_at` (Python default `utcnow`) are NOT NULL. No soft delete, no unique constraint on the name. Seven tables reference it.

**Notes for the test designer:** `from app.dao.project_component import project_component_dao`. Parents: `Factory`, `Project(workspace_id, factory_id, name, description)`. **BUG-1275:** names out of `id` order in mixed case (`"Beta"`, `"alpha"`, `"Gamma"`). This case fails on the name order whatever the physical order, so it can be strict; a pure tie on the name needs a sequential scan and a **non-strict** xfail. Wrap negative paging in `db.begin_nested()`.

## Not specified
- `project_component_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — covered by the base spec.

---

## `DAOProjectComponent.get_by_project(db, *, project_id, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProjectComponentService.get_components` when `project_id` is given ← `GET /project-components/?project_id=…`)

**Purpose:** The components of one project, a page at a time.

**Returns:** a `list` of `ProjectComponent` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `project_id` and that `workspace_id`. Another workspace returns `[]`; a row of workspace B on a project of A is returned only for B.
- **R2.** An unknown project, `0`, or a project with no components returns `[]`.
- **R3.** [BUG-1275] (HR-6) Ordered by `name` case-insensitive ascending, then `id` ascending, before `skip` / `limit`. *(Today: no `ORDER BY`.)*
- **R4.** With the defaults at most 100 rows: 103 give 100; `limit=1000` gives 103.
- **R5.** `limit=0` and `skip` past the end return `[]`.
- **R6.** Negative paging is refused by Postgres (see Errors).
- **R7.** The state of the project is not looked at: the components of a soft-deleted project are returned. The caller names the project, and hiding it is the caller's (BUG-1278).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`, `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`, `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 14 | keyword-only parameters; defaults `skip=0`, `limit=100` | R4 |
| 31–34 | workspace AND project; no parent state | R1, R2, R7 |
| 29–38 | no `ORDER BY` (BUG-1275) | R3 |
| 35–36 | offset / limit; `0`; negative | R4, R5, R6 |
| 41 | module singleton | Not specified |
