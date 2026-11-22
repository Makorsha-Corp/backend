# Spec — `app/dao/access_control.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-03.** BUG-1408 and BUG-1409 stand from house rules; the order chosen for BUG-1408 (`id` ascending) was decided by Claude under the reviewer's delegation (2026-11-03). One owner item about who may change these rows is parked in `docs/testing/owner-questions.md` (OQ-4); it is about the endpoint, not a rule of this DAO, and does not block this spec.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. HR-16.
>
> **Verified by running** (throwaway scripts `facts.py`, `v_misc.py`, harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsdao\`, each in one transaction rolled back against `marker_test`; nothing committed): the table's columns and constraints, and the Postgres enum labels (`OWNER, FINANCE, GROUND_TEAM, GROUND_TEAM_MANAGER`; `PAGE, MANAGE_ORDER_STATUS, FEATURE`: the member **names** are stored); the SQL of both methods (no `ORDER BY`); role given as the enum, as `"owner"`, as `"OWNER"`, as `"nobody"`; rows of another workspace and with no workspace; `workspace_id=None`; a duplicate row; paging, `limit=0`, the default cap of 100 (101 rows); negative paging; positional arguments; the order under a forced sequential scan (`1, 2, 3, 0` after the first row was updated, and the same when paged one row at a time). **Not run:** anything over HTTP; the intended behaviour of the bug rules.

## Review
> All answered; nothing pending.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| — | No question of this DAO | — | — |

Decided by house rules: the two filtered lists have no sort order (BUG-1408, HR-6); the list endpoint accepts `limit=0` and negative limits (BUG-1409, HR-7).

### House-rule violations — applied automatically

- **HR-6** `get_by_role` R4, `get_by_type` R4 — no `ORDER BY` on these paged queries behind `GET /access-control/?role=…` and `?access_type=…`. Verified: four rows came back `1, 2, 3, 0` after the first was updated, also when paged one row at a time. Intended: `id` ascending, before `skip` / `limit`. Why not HR-6's name default: a row has no name (a `target` is a page path or feature key), and the same endpoint without a filter reads the base `get_by_workspace`, which BUG-100 orders by `id`; all three branches of one endpoint then share one order. Decided by Claude under the reviewer's delegation (2026-11-03).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1408 (pattern `unordered-pagination`). Rules: `get_by_role` R4, `get_by_type` R4.
- **HR-7** `get_by_role` R5, `get_by_type` R5 — `GET /access-control/` declares `limit: int = Query(100, le=100)` with no lower bound: `limit=0` answers `[]`, `limit=-1` reaches Postgres and fails with a 500 (verified at the DAO: `DataError`, pgcode `2201W`). `skip` already has `ge=0`.
**Answer:** bug — per HR-7 (house rule)
**Resolution:** BUG-1409 (pattern `missing-limit-lower-bound`; the fix is `ge=1` in `app/api/v1/endpoints/access_control.py`, so 422). At the DAO the parameters stay unvalidated; the rules here describe what the DAO does with them. Rules: `get_by_role` R5, `get_by_type` R5 (no tag: the DAO is unchanged).

Checked and **not** a new line here: **HR-4** — no soft-delete column. **HR-5** — both filters are in the query. **HR-8** — no `LIKE`. **HR-9** — no audit columns. **HR-10** — reads only. **HR-16** — every method of this file filters on the row's `workspace_id`; the service sets `workspace_id` from the current workspace on create, and `AccessControlUpdate` has no `workspace_id`.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Access-control endpoint / service** (`app/api/v1/endpoints/access_control.py`, `app/services/access_control_service.py`) — **OWNER, access** | (a) Create, update and delete require only an active membership: any member, `ground-team` included, can change the workspace's permission rows. (b) Nothing in the backend reads these rows to allow or refuse anything; if the frontend uses them to show pages, a member can grant themselves pages. Parked as OQ-4. (c) The same `type` + `target` + `role` can be stored twice (no uniqueness; verified). (d) `get_controls` uses `if role:` / `elif access_type:`; with both given, `access_type` is ignored. | Overview |

## Overview
`DAOAccessControl` reads `access_control`, the workspace's role-permission table: one row grants a `role` (`RoleEnum`) access to a `target` of some `type` (`page`, `manage-order-status`, `feature`). Callers: `AccessControlService` behind `GET /access-control/` (with `role` → `get_by_role`, else with `access_type` → `get_by_type`, else the base `get_by_workspace`), and the inherited `get_by_id_and_workspace`, `create`, `update`, `remove` for the single-row endpoints. It never commits.

**Callables:** 2 specified · 1 not specified (+ inherited, base spec)
**Externals to mock:** none
**Integration-only behavior:** none

**Model facts (table `access_control`):** `workspace_id` **nullable**, FK `workspaces` ON DELETE CASCADE, indexed; `type` Postgres enum `accesscontroltypeenum` NOT NULL; `target` VARCHAR NOT NULL (no length limit, `""` allowed); `role` Postgres enum `roleenum` NOT NULL. SQLAlchemy stores the enum member **name** (`OWNER`, `PAGE`). No unique constraint, no soft delete, no timestamps.

**Notes for the test designer:** `from app.dao.access_control import access_control_dao`; enums from `app.models.enums`. Build `AccessControl(workspace_id, type, target, role)` directly. Every parameter after `db` is keyword-only. **BUG-1408:** force a sequential scan, insert four rows, update the lowest `id`, flush, `db.expire_all()`; the result rests on physical order → **non-strict** xfail, assertion not weakened. Compare **sets** of ids elsewhere.

## Not specified
- `access_control_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — covered by the base spec. Used here: `get_by_workspace` (the unfiltered list; BUG-100 orders it by `id`), `get_by_id_and_workspace`, `create` with a dict carrying `workspace_id`, `update` with `AccessControlUpdate` (only fields set to a value change), `remove`.

---

## `DAOAccessControl.get_by_role(db, *, role, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `AccessControlService.get_controls` ← `GET /access-control/?role=…`, with the caller's `skip` / `limit`)

**Purpose:** The permission rows of one role in one workspace, a page at a time.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `role` | `RoleEnum` (or its value or name as a string) | equality; a string that is neither raises `DataError` |
| `workspace_id` | int | equality on the row's `workspace_id` |
| `skip` / `limit` | int, defaults `0` / `100` | not validated |

**Returns:** a `list` of `AccessControl` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `role` and that `workspace_id`, of every `type`. Rows of another workspace never appear, even when they would fit on the page. Duplicate rows are each returned.
- **R2.** The role may be passed as `RoleEnum.OWNER`, `"owner"` or `"OWNER"`: all three match the same rows. A string that is not a role (`"nobody"`) raises `DataError` (pgcode `22P02`, `InvalidTextRepresentation`).
- **R3.** Rows whose `workspace_id` is `NULL` are returned only when `workspace_id=None` is passed (the comparison becomes `IS NULL`); no caller does, because the workspace always comes from `get_current_workspace`.
- **R4.** [BUG-1408] (HR-6) Ordered by `id` ascending, before `skip` / `limit`, so consecutive pages neither repeat nor skip rows. *(Today: no `ORDER BY`.)*
- **R5.** At most `limit` rows after skipping `skip`; with the defaults at most 100 (101 matching rows give 100). `limit=0`, `skip` past the end, an unknown workspace or `0` give `[]`. A negative `limit` or `skip` raises `DataError` (pgcode `2201W` / `2201X`). (The API's lower bound is BUG-1409, in the endpoint.)

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| role string not in the enum | `sqlalchemy.exc.DataError`, pgcode `22P02` | — |
| negative `limit` / `skip` | `sqlalchemy.exc.DataError`, pgcode `2201W` / `2201X` | `LIMIT must not be negative` / `OFFSET must not be negative` |
| positional arguments | `TypeError` | — |

**Side effects:** none

---

## `DAOAccessControl.get_by_type(db, *, access_type, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `AccessControlService.get_controls` ← `GET /access-control/?access_type=…`, when no `role` is given)

**Purpose:** The permission rows of one type in one workspace, a page at a time.

**Returns:** a `list` of `AccessControl` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `type` and that `workspace_id`, of every role. Workspace isolation, `NULL` workspace and duplicates as `get_by_role` R1, R3.
- **R2.** The type may be passed as the enum, its value or its name; any other string raises `DataError` (as `get_by_role` R2).
- **R3.** Updating a row's `type` moves it between the results of this method (verified with `update`).
- **R4.** [BUG-1408] (HR-6) Ordered by `id` ascending, before `skip` / `limit`. *(Today: no `ORDER BY`.)*
- **R5.** Paging, defaults, empty results and negative values as `get_by_role` R5.

**Errors:** as `get_by_role`.

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 19–21, 50–52 | keyword-only; defaults `skip=0`, `limit=100` | `get_by_role` R5, Errors; `get_by_type` R5 |
| 39–44 | workspace AND role; enum coercion; `None` → `IS NULL` | `get_by_role` R1, R2, R3 |
| 45–47 | offset / limit, no `ORDER BY` (BUG-1408); `0`, negative, many | `get_by_role` R4, R5 |
| 69–74 | workspace AND type | `get_by_type` R1, R2, R3 |
| 75–77 | offset / limit, no `ORDER BY` (BUG-1408) | `get_by_type` R4, R5 |
| 81 | module singleton | Not specified |
