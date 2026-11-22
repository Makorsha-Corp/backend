# Spec — `app/dao/project_component_item.py`

> **Status:** APPROVED (2026-11-02; no questions, house-rule lines pre-filled)
> **Source commit:** e48a092

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Things of a soft-deleted parent are hidden. HR-16: a row linking to another workspace's row is invalid data. Raw lookups stay raw (HR-4 scope).
>
> **Verified by running** (throwaway scripts `cat1.py`, `v3.py`, `v7.py`, harness `h.py`, `w.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns and constraints; no `ORDER BY`; the order changing after an update; 102 rows, the cap, `limit=0`, `skip` past the end, negative values; unknown ids; another workspace; the rows of a component of a soft-deleted project through `ProjectComponentItemService.get_items` and `get_by_id`. **Not run:** anything over HTTP; the intended behaviour of the bugs below.

## Review
> Nothing open. Overwrite a pre-filled answer only if the house rule should not apply here.

### House-rule violations — applied automatically

- **HR-6** `get_by_component` R3 — pages with no `ORDER BY`. Verified: three rows came back with the lowest `id` last once it was updated. Intended: `id` ascending, before `skip` / `limit` (BUG-906 precedent: the rows have no name).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1276 (pattern `unordered-pagination`). Rules: `get_by_component` R3.
- **HR-7** `get_by_component` R5 — `GET /project-component-items/` has no lower bound on `limit`. Intended: `limit >= 1`, 422 otherwise.
**Answer:** bug — per HR-7 (house rule)
**Resolution:** BUG-1277, with `GET /project-components/`. The DAO rule does not change.

Checked and **not** a new line here: **HR-5, HR-8** in this method — filters are in the query, no `LIKE`. **HR-4** — no soft-delete column here or on the component; the project is the soft-deleted parent, R7. **HR-9, HR-10** — the DAO only reads. **HR-15** — no money. **HR-16** — the read follows the row; a stored foreign item is BUG-1012.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Project component item service** (`app/services/project_component_item_service.py`, not yet specified) | (a) **BUG-1278, logged:** the rows under a soft-deleted project stay listed and can be opened (verified). (b) Without `project_component_id`, `get_items` pages first and filters by access after, as FU-1 (b) of `tests/unit/dao/project_component.spec.md` (read; same shape). (c) `if project_component_id:` means `0` lists the workspace (read). | standing decision, HR-5 |

## Overview
`DAOProjectComponentItem` adds one read to `BaseDAO`: the items planned for one project component. The rest comes from inherited `get_by_id_and_workspace`, `get_by_workspace`, `create`, `update` and `remove`, used by `ProjectComponentItemService`.

**Callables:** 1 specified · 2 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Model facts (table `project_component_items`):** `workspace_id` FK CASCADE, `project_component_id` FK (no action), `item_id` FK (no action), `qty` Integer, all NOT NULL. No soft delete, no unique constraint: one component can hold one item twice.

**Notes for the test designer:** `from app.dao.project_component_item import project_component_item_dao`. Parents: as `tests/unit/dao/project_component.spec.md`, plus `Item(workspace_id, name, unit, name_normalized)`. **BUG-1276:** three rows, update the lowest `id`, flush, `db.expire_all()`. The result rests on physical order: **non-strict** xfail, assertion not weakened. Wrap negative paging in `db.begin_nested()`.

## Not specified
- `project_component_item_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — covered by the base spec.

---

## `DAOProjectComponentItem.get_by_component(db, *, project_component_id, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProjectComponentItemService.get_items` when `project_component_id` is given ← `GET /project-component-items/?project_component_id=…`)

**Purpose:** The items of one component, a page at a time.

**Returns:** a `list` of `ProjectComponentItem` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `project_component_id` and that `workspace_id`. Another workspace returns `[]`; a row of workspace B on a component of A is returned only for B.
- **R2.** An unknown component, `0`, or a component with no items returns `[]`.
- **R3.** [BUG-1276] (HR-6) Ordered by `id` ascending, before `skip` / `limit`. *(Today: no `ORDER BY`.)*
- **R4.** With the defaults at most 100 rows: 102 give 100; `limit=1000` gives 102.
- **R5.** `limit=0` and `skip` past the end return `[]`.
- **R6.** Negative paging is refused by Postgres (see Errors).
- **R7.** The state of the component's project is not looked at: rows under a soft-deleted project are returned. The caller names the component, and hiding them is the caller's (BUG-1278).

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
| 17 | keyword-only parameters; defaults `skip=0`, `limit=100` | R4 |
| 34–37 | workspace AND component; no parent state | R1, R2, R7 |
| 32–41 | no `ORDER BY` (BUG-1276) | R3 |
| 38–39 | offset / limit; `0`; negative | R4, R5, R6 |
| 44 | module singleton | Not specified |
