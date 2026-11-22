# Spec — `app/dao/base.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically
> `BaseDAO` is inherited by ~93 DAOs, so each fix below changes the default for every subclass. Overwrite an answer with `intended — <reason>` if the rule should be enforced in managers instead of in the base DAO.

- **HR-4** `get` R3 — a soft-deleted row is returned by id. — ✅ intended (reviewer override)
**Answer:** intended — reviewer override: BaseDAO stays a raw, neutral data-access layer that returns soft-deleted rows; HR-4 is enforced in managers / module-specific DAO methods (e.g. department BUG-005/006), because callers such as delete-already-deleted checks and restore must see deleted rows
**Resolution:** BaseDAO returns soft-deleted rows by design (HR-4 scope already records this). Rules: `get` R3 ✅.
- **HR-4** `get_by_id_and_workspace` R4 — a soft-deleted row is returned by id + workspace. — ✅ intended (reviewer override)
**Answer:** intended — reviewer override: BaseDAO stays a raw, neutral data-access layer that returns soft-deleted rows; HR-4 is enforced in managers / module-specific DAO methods (e.g. department BUG-005/006), because callers such as delete-already-deleted checks and restore must see deleted rows
**Resolution:** as above. Rules: `get_by_id_and_workspace` R4 ✅.
- **HR-4 / HR-5** `get_by_workspace` R4 — soft-deleted rows are included in the page, so callers that drop them afterwards get short or empty pages (the department list, BUG-006, is one such caller). — ✅ intended (reviewer override)
**Answer:** intended — reviewer override: BaseDAO stays a raw, neutral data-access layer that returns soft-deleted rows; HR-4 is enforced in managers / module-specific DAO methods (e.g. department BUG-005/006), because callers such as delete-already-deleted checks and restore must see deleted rows
**Resolution:** as above; managers that must hide deleted rows need their own filtered query (HR-5 is checked against those managers, not the base). Rules: `get_by_workspace` R4 ✅.
- **HR-4 / HR-5** `get_multi` R3 — same as the `get_by_workspace` line above, for the unscoped list. — ✅ intended (reviewer override)
**Answer:** intended — reviewer override: BaseDAO stays a raw, neutral data-access layer that returns soft-deleted rows; HR-4 is enforced in managers / module-specific DAO methods (e.g. department BUG-005/006), because callers such as delete-already-deleted checks and restore must see deleted rows
**Resolution:** as above. Rules: `get_multi` R3 ✅.
- **HR-6** `get_by_workspace` R3 — no sort order; paging with `skip` can repeat or skip rows. — 🐞 BUG-100
**Answer:** bug — narrowed by reviewer: BaseDAO list methods order by `id` ascending before `skip`/`limit` (stable paging, no repeats/skips); display order (name) is the manager's responsibility per HR-6
**Resolution:** `get_by_workspace` orders by `id` ascending before `skip`/`limit`; no name ordering in the base class. Rules: `get_by_workspace` R3.
- **HR-6** `get_multi` R2 — no sort order. — 🐞 BUG-100
**Answer:** bug — narrowed by reviewer: BaseDAO list methods order by `id` ascending before `skip`/`limit` (stable paging, no repeats/skips); display order (name) is the manager's responsibility per HR-6
**Resolution:** `get_multi` orders by `id` ascending before `skip`/`limit` (same fix as `get_by_workspace`, same bug). Rules: `get_multi` R2.

### New questions

### Q1. A schema-based update can never clear a field — ✅ intended
**Background:** `update` accepts either a Pydantic update schema (what the API sends) or a plain dict (what managers build internally). From a schema it keeps only fields the client actually sent **and** that are not `null`. From a dict it applies every key, including `None`.
**What happens today:** A client that sends `null` to empty an optional field (e.g. `{"description": null}`) gets a successful response, but the field keeps its old value. Only internal code passing a dict can set a column to `NULL`.
**Example:** An item has description "old text". The user clears the description box and saves; the frontend sends `{"description": null}`. The API returns 200 and the item still shows "old text".
**Rules affected:** `update` R3
**Suggested answer:** `intended` — across the API, `null` means "leave unchanged" (the approved department spec already relies on this: `update_department` R7). Clearing a field would need an explicit per-module mechanism. Answering `bug` would change all ~93 DAOs and contradict that approved rule.
**Answer:** intended

### Q2. `update` silently ignores unknown field names, `create` rejects them — ✅ intended
**Background:** `create` builds a new row from the given fields; `update` copies the given fields onto an existing row.
**What happens today:** `create` with a field the model does not have fails with a `TypeError` ("'x' is an invalid keyword argument for Department"), which becomes a 500 at the API. `update` with the same unknown field silently skips it and succeeds. Conversely, `update` also sets anything the row object happens to have as an attribute — including relationships (e.g. `creator`) and non-column attributes.
**Example:** A manager passes `{"nmae": "Ops"}` (typo) to update department 7: the call succeeds, nothing changes, no error. The same dict passed to create raises `TypeError`.
**Rules affected:** `create` R5, `update` R4, R5
**Suggested answer:** `intended` — callers build the data from their own schemas, so unknown keys only come from programming mistakes; lenient update is the long-standing contract relied on by ~93 DAOs.
**Answer:** intended

### Q3. Removing an id that does not exist crashes — 🐞 BUG-101
**Background:** `remove` hard-deletes a row by primary key. It does not check that the row exists. All 10 current callers look the row up first (and return 404 themselves), so no API request reaches this case today.
**What happens today:** For an id with no row, `remove` raises SQLAlchemy's `UnmappedInstanceError` ("Class 'builtins.NoneType' is not mapped") — a 500 if it ever reaches the API — instead of a clear "not found" result.
**Example:** A new endpoint calls `status_dao.remove(db, id=999)` without checking first; the user deleting an already-deleted status gets a 500 server error instead of a 404.
**Rules affected:** `remove` R3
**Suggested answer:** `bug — when no row has that id, return None and delete nothing` (matching `get`, so callers can turn `None` into 404).
**Answer:** bug — removing an id that does not exist returns `None` and deletes nothing (no 500)
**Resolution:** `remove` returns `None` for a missing primary key, deletes nothing and raises nothing. Rules: `remove` R3. Return annotation becomes `ModelType | None` (best-practice default, delegated by reviewer).

### Q4. Unscoped `get` / `get_multi` / `remove` are used on a workspace-scoped model — ✅ intended (BaseDAO) · caller leak 🐞 BUG-035
**Background:** `get`, `get_multi` and `remove` look rows up by id (or list everything) without any workspace filter — they are meant for global models such as workspaces and profiles. The workspace-aware methods (`get_by_workspace`, `get_by_id_and_workspace`) exist for workspace-owned models. The only caller of `get_multi` is the statuses API (`GET /statuses/`), and statuses belong to a workspace (`statuses.workspace_id`). The statuses get/update/delete endpoints also use the unscoped `get`/`remove`.
**What happens today:** The base methods do exactly what they say. But through the statuses API, a user of workspace A sees, and can edit or delete, the statuses of every workspace.
**Example:** Workspaces A and B each have 3 statuses. A member of A calls `GET /statuses/` and receives all 6; `DELETE /statuses/{id}` with an id from B deletes B's status.
**Rules affected:** `get` R4, `get_multi` R4, `remove` R5
**Suggested answer:** `intended` for `BaseDAO` (unscoped primitives are needed for global models); log the leak as a bug against `app/services/status_service.py` + `app/api/v1/endpoints/statuses.py`: scope every statuses operation to the current workspace (`get_by_workspace` / `get_by_id_and_workspace`).
**Answer:** intended for BaseDAO — but log a separate HIGH-PRIORITY bug: the statuses service/endpoint (`app/services/status_service.py`, `app/api/v1/endpoints/statuses.py`) do not scope by workspace, so statuses of every workspace can be listed, updated and deleted by any user (cross-workspace data leak); also `StatusCreate` lacks `workspace_id` so create likely 500s
**Resolution:** BaseDAO rules unchanged (`get` R4 ✅, `get_multi` R4 ✅, `remove` R5 ✅). The leak is already logged as BUG-035 (`missing-workspace-scope`, HIGH) against the statuses service/endpoint; it is tested in the statuses specs, not here.

## Overview
`BaseDAO` is the generic data-access layer inherited by ~93 DAO classes. It provides get-by-id, list, create, update and hard-delete primitives plus two workspace-scoped reads that are meant to be used for every workspace-owned model so one workspace cannot see another's data. It never commits: writes are flushed (so ids, defaults and constraint violations appear immediately) and the service layer commits or rolls back. By design it is a raw layer: it knows nothing about soft delete or audit fields (managers enforce HR-4/HR-9). Its list methods guarantee only a stable `id`-ascending order (BUG-100); display order is the manager's job.

**Callables:** 7 specified · 1 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Notes for the test designer:**
- Test the base class **once**, through a real concrete model; per-DAO specs then only cover overrides and custom methods. Recommended vehicle: `Department` via `department_dao` (`app.dao.department`) or a bare `BaseDAO(Department)` — it has `id`, `workspace_id` (NOT NULL FK to `workspaces`), `name` (NOT NULL, no unique constraint), nullable `created_by`/`updated_by`/`deleted_by` (FKs to `profiles`), `is_active` (default `True`), `is_deleted` (default `False`), `created_at` (`server_default now()`), `updated_at` (`onupdate now()`), and `DAODepartment` overrides none of the base methods. Workspaces come from `tests/unit/factories.py` (`make_workspace`).
- `DepartmentCreate` has only `name`, so it cannot create a department (no `workspace_id`); use a dict for create, or define a small ad-hoc Pydantic schema in the test (any `BaseModel` works, including one with a field `alias` to exercise `by_alias`).
- Model features each method depends on:
  | Method | Needs on the model | Without it |
  |---|---|---|
  | `get` | an `id` attribute | `AttributeError` (every current model has `id`) |
  | `get_multi` | nothing today; after BUG-100 an `id` column to order by | — |
  | `create` | every given key must be a model attribute; NOT NULL columns without default must be given | `TypeError` / `IntegrityError` |
  | `update` | nothing (unknown keys skipped) | — |
  | `remove` | a single-column primary key (looked up by **primary key**, not by the `id` attribute name) | — |
  | `get_by_workspace`, `get_by_id_and_workspace` | a `workspace_id` column | `AttributeError` at call time — applies to `Profile`, `Workspace`, `SubscriptionPlan`, `WaitlistSignup` |
  | soft delete (`is_deleted`) | ignored by every method, by design | — |
  | ordering | `id` ascending after BUG-100; never by `name` | — |
- To prove ordering (BUG-100): assert the returned `id`s are strictly ascending and that consecutive pages (`skip=0,limit=2` then `skip=2,limit=2`) concatenate to the full `id`-ascending list with no repeats; also give names out of alphabetical order (e.g. id order "Zeta", "Alpha") to show the base does **not** sort by name.
- Postgres `now()` is the transaction start time and each test is one transaction, so `created_at` and `updated_at` set in the same test are equal; assert `updated_at` became non-null rather than "later than `created_at`".
- `remove` emits SQLAlchemy's `LegacyAPIWarning` (it uses the legacy `Query.get`); do not treat warnings as errors for that call.
- `get` Errors row (model without `id`): no real model lacks `id`. Use a test-local mapped class (e.g. `NoIdThing` on its own `DeclarativeBase`/`MetaData`, a single-column primary key not named `id`); the error is raised when the query is built, so its table never needs to exist. (best-practice default, delegated by reviewer)
- `remove` R4 (FK behavior): no model in `app/models` has a foreign key to `departments.id`. Create temporary child tables inside the test transaction (e.g. `CREATE TEMP TABLE … (dept_id int REFERENCES departments(id) ON DELETE RESTRICT)` and one with `ON DELETE CASCADE`); they vanish on rollback. (best-practice default, delegated by reviewer)
- `get_multi` runs unscoped over a database shared with concurrently running tests (each in its own rolled-back transaction, so only committed rows are visible). Write its assertions relative to `N0` = the row count visible at test start and page past existing rows with `skip=N0`; the "no rows at all" part of R5 is covered through `get_by_workspace` R5 (empty workspace) instead. (best-practice default, delegated by reviewer)
- BUG-100 xfail cases (today's behavior, no ORDER BY): to keep the strict xfail deterministic, force a sequential scan inside the test transaction (`SET LOCAL enable_indexscan = off; SET LOCAL enable_bitmapscan = off; SET LOCAL enable_indexonlyscan = off`) and create rows so that heap order differs from `id` order (e.g. update an earlier row so its new tuple version lands after later ones). (best-practice default, delegated by reviewer)

## Not specified
- `BaseDAO.__init__` — stores the model class, no logic

---

## `BaseDAO.get(db, id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (29 direct callers, e.g. `core/deps.py` workspace lookup, `profile_dao.get` in endpoints, statuses service)

**Purpose:** Fetch one row of the model by id, regardless of workspace or soft delete.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `id` | any | compared with the model's `id` column; no validation |

**Returns:** the model instance, or `None`.

**Rules:**
- **R1.** Given a row with that id exists, it is returned.
- **R2.** Given no row has that id, returns `None` (no error).
- **R3.** Given the row is soft-deleted (`is_deleted = True`), it is still returned — BaseDAO does not filter soft-deleted rows. ✅
- **R4.** No workspace filter: a row belonging to any workspace is returned. ✅
- **R5.** Rows added to the session (`db.add`) but not yet flushed are **not** found — `get` returns `None` for them, because the session runs with `autoflush=False` (app `SessionLocal` and the test harness alike) and `get` always queries the database. Once the row is flushed (every BaseDAO write — `create`, `update`, `remove` — flushes explicitly, which is the supported way to make rows visible), the same `get` returns it. No bug: `autoflush=False` is a deliberate session setting. (best-practice default, delegated by reviewer)

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| model has no `id` attribute | `AttributeError` | — |

**Side effects:** none

---

## `BaseDAO.get_multi(db, *, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (only caller: `StatusService.get_statuses` ← `GET /statuses/`)

**Purpose:** Page through all rows of the model, across all workspaces.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `skip` | int, default `0` | rows to skip; not validated (negative → Postgres error) |
| `limit` | int, default `100` | max rows; not validated (`0` → empty list, negative → Postgres error) |

**Returns:** list of model instances (possibly empty).

**Rules:**
- **R1.** Returns at most `limit` rows, skipping the first `skip`; with defaults, at most 100 rows. Given more than 100 rows and no arguments, exactly 100 are returned.
- **R2.** [BUG-100] Rows are ordered by `id` ascending, applied before `skip`/`limit`; consecutive pages never repeat or skip rows. No name ordering (a row named "Zeta" with a lower id comes before "Alpha"). *(Today: no ORDER BY — order is unspecified.)*
- **R3.** Soft-deleted rows are included and counted by `skip`/`limit` — BaseDAO does not filter them. ✅
- **R4.** No workspace filter: rows from every workspace are returned. ✅
- **R5.** Given `skip` at or past the number of rows, or `limit = 0`, or no rows, returns `[]`.
- **R6.** Given a negative `skip` or `limit`, Postgres rejects the query (`sqlalchemy.exc.DataError`).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `skip` or `limit` | `sqlalchemy.exc.DataError` | Postgres "OFFSET/LIMIT must not be negative" |

**Side effects:** none

---

## `BaseDAO.create(db, *, obj_in)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by most managers)

**Purpose:** Insert a new row from a schema or dict, flushed but not committed.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `obj_in` | Pydantic `BaseModel` or `dict` | field values; a dict is used as-is; a schema is dumped with `by_alias=True` including **all** fields (unset ones at their schema default, `None` included) |

**Returns:** the new instance, flushed (has `id` and defaults), not committed.

**Rules:**
- **R1.** Given a dict, a row is created with exactly those column values; after the call the instance has a database-assigned `id` and the row is visible to queries in the same session.
- **R2.** Given a schema, every schema field is passed to the model — including fields the caller never set (at their schema default) — under the field's **alias** when one is defined.
- **R3.** Columns not given take their model default / server default (Department: `is_active = True`, `is_deleted = False`, `created_at` = transaction time, `updated_at` = `NULL`). A column given explicitly as `None` that has a default or server default also takes the default; a column given as `None` without a default is stored `NULL`.
- **R4.** The row is not committed: rolling back the session removes it.
- **R5.** Given a key that is not an attribute of the model, a `TypeError` is raised and nothing is added. ✅
- **R6.** Given data violating a database constraint (missing NOT NULL column such as `workspace_id`, unknown foreign key), the flush raises `sqlalchemy.exc.IntegrityError`.
- **R7.** Nested schemas are dumped to plain dicts/lists, so a schema with a nested-model field cannot be passed to a relationship attribute: the model constructor raises `AttributeError` (`'dict' object has no attribute '_sa_instance_state'`, or `'list' …` for a list field) before anything is added to the session — no row is created.
- **R8.** No workspace is added automatically: the caller must include `workspace_id` in the data.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| unknown key | `TypeError` | `'<key>' is an invalid keyword argument for <Model>` |
| nested-model / list value for a relationship attribute | `AttributeError` | `'dict' object has no attribute '_sa_instance_state'` |
| constraint violated at flush | `sqlalchemy.exc.IntegrityError` | Postgres message |

**Side effects:** one row inserted and flushed; no commit.

---

## `BaseDAO.update(db, *, db_obj, obj_in)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by most managers)

**Purpose:** Copy the given field values onto an existing row, flushed but not committed.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db_obj` | model instance | the row to change; not checked for workspace or soft delete |
| `obj_in` | Pydantic `BaseModel` or `dict` | dict used as-is (all keys, `None` included); schema dumped with `exclude_unset=True, exclude_none=True, by_alias=True` |

**Returns:** the same `db_obj`, flushed, not committed.

**Rules:**
- **R1.** Given a dict, every key that is an attribute of the row is set to the given value, including `None` (stored `NULL`).
- **R2.** Given a schema, only fields the caller explicitly set are applied, under their alias when one is defined.
- **R3.** Given a schema field set explicitly to `None`, it is not applied: the column keeps its value (across the API `null` means "leave unchanged"). ✅
- **R4.** Keys that are not attributes of the row are silently ignored; no error, the other keys are still applied. ✅
- **R5.** Any attribute the row has is assignable, not only columns — e.g. `id`, `workspace_id`, `is_deleted`, relationships such as `creator` — so the data can move a row to another workspace or change audit fields if the caller includes them. ✅
- **R6.** Given an empty dict or a schema with nothing set, nothing changes and no error is raised; the row is returned.
- **R7.** When at least one column value actually changes, `onupdate` columns are refreshed (Department: `updated_at` becomes non-null). When every given value equals the current one (row loaded in the session), no UPDATE is issued and `updated_at` is left unchanged.
- **R8.** The change is flushed (visible to queries in the same session) but not committed: rolling back restores the old values.
- **R9.** Given a value violating a database constraint (e.g. `None` for a NOT NULL column via dict, unknown foreign key), the flush raises `sqlalchemy.exc.IntegrityError`.
- **R10.** No audit fields (`updated_by` etc.) are written unless present in the data.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| constraint violated at flush | `sqlalchemy.exc.IntegrityError` | Postgres message |

**Side effects:** row updated and flushed; no commit.

---

## `BaseDAO.remove(db, *, id)`
**Shape:** delete
**Persistence:** writes
**Visibility:** public (10 callers: statuses, access controls, app settings, order workflows, miscellaneous project costs, project components/items/tasks/notes services, invoice-items endpoint — all look the row up first)

**Purpose:** Hard-delete one row by primary key, flushed but not committed.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `id` | int | primary-key value; not validated |

**Returns:** the deleted instance (deleted state), not committed; or `None` when no row has that primary key (BUG-101).

**Rules:**
- **R1.** Given a row with that primary key exists, it is physically deleted: after the call a query in the same session no longer finds it, and the deleted instance is returned.
- **R2.** The row is deleted even if the model has `is_deleted` (no soft delete). Rolling back the session restores it (not committed).
- **R3.** [BUG-101] Given no row with that primary key, returns `None`, deletes nothing (other rows of the model are untouched) and raises no error. *(Today: `sqlalchemy.orm.exc.UnmappedInstanceError` "Class 'builtins.NoneType' is not mapped" is raised.)*
- **R4.** Given other rows reference it through a foreign key without `ON DELETE CASCADE`/`SET NULL`, the flush raises `sqlalchemy.exc.IntegrityError`; with `CASCADE`, the referencing rows are deleted by the database.
- **R5.** No workspace check: a row of any workspace is deleted. ✅

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| referenced by non-cascading FK | `sqlalchemy.exc.IntegrityError` | Postgres message |

**Side effects:** one row deleted and flushed (none when the id does not exist); emits `LegacyAPIWarning`; no commit.

---

## `BaseDAO.get_by_workspace(db, *, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (43 call sites)

**Purpose:** Page through the rows owned by one workspace.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | equality filter on `workspace_id` |
| `skip` | int, default `0` | not validated (negative → Postgres error) |
| `limit` | int, default `100` | not validated (`0` → empty, negative → Postgres error) |

**Returns:** list of model instances (possibly empty).

**Rules:**
- **R1.** Only rows with that `workspace_id` are returned; rows of other workspaces never appear, even when they would fit on the page.
- **R2.** At most `limit` rows are returned after skipping `skip`; with defaults at most 100 — given 101 rows in the workspace, exactly 100 are returned.
- **R3.** [BUG-100] Ordered by `id` ascending, applied before `skip`/`limit`; consecutive pages never repeat or skip rows. No name ordering. *(Today: no ORDER BY.)*
- **R4.** Soft-deleted rows of the workspace are returned and counted by `skip`/`limit` — BaseDAO does not filter them. ✅
- **R5.** Given a workspace with no rows, a non-existent workspace id, `skip` past the end, or `limit = 0`, returns `[]`.
- **R6.** Given a negative `skip` or `limit`, raises `sqlalchemy.exc.DataError`.
- **R7.** On a model without a `workspace_id` column, raises `AttributeError` without querying.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| model has no `workspace_id` | `AttributeError` | `type object '<Model>' has no attribute 'workspace_id'` |
| negative `skip`/`limit` | `sqlalchemy.exc.DataError` | Postgres message |

**Side effects:** none

---

## `BaseDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (268 call sites; the standard lookup behind "404 not found" in managers and endpoints)

**Purpose:** Fetch one row by id only if it belongs to the given workspace.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `id` | int | equality on `id` |
| `workspace_id` | int | equality on `workspace_id` |

**Returns:** the model instance, or `None`.

**Rules:**
- **R1.** Given a row with that id in that workspace, it is returned.
- **R2.** Given the id exists but belongs to another workspace, returns `None` (indistinguishable from not found).
- **R3.** Given no row has that id, returns `None`.
- **R4.** Given the row is soft-deleted, it is still returned — BaseDAO does not filter soft-deleted rows. ✅
- **R5.** On a model without a `workspace_id` column, raises `AttributeError`.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| model has no `workspace_id` | `AttributeError` | `type object '<Model>' has no attribute 'workspace_id'` |

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 43 | row with id found / not found | `get` R1, R2 |
| 43 | no `is_deleted` filter (by design) | `get` R3 |
| 43 | no workspace filter | `get` R4 |
| 43 | `self.model.id` missing | `get` Errors |
| 43 | query hits the DB with autoflush off: pending (unflushed) row not found / flushed row found | `get` R5 |
| 59 | offset/limit, defaults 0/100 | `get_multi` R1, R5, R6 |
| 59 | no ORDER BY (BUG-100: `id` asc) | `get_multi` R2 |
| 59 | no `is_deleted` filter (by design) | `get_multi` R3 |
| 59 | no workspace filter | `get_multi` R4 |
| 76 | `obj_in` is dict → used as-is | `create` R1 |
| 78–79 | else schema → `model_dump(by_alias=True)` (all fields, nested → dicts) | `create` R2, R7 |
| 81 | model constructor rejects unknown key | `create` R5 |
| 81–83 | defaults / `None` on defaulted column; flush constraint errors | `create` R3, R6, R8 |
| 83 | flush, no commit | `create` R1, R4 |
| 108 | `obj_in` is dict → all keys incl. `None` | `update` R1 |
| 110–111 | else schema → `exclude_unset`, `exclude_none`, `by_alias` | `update` R2, R3 |
| 113 | loop over empty / one / many fields | `update` R6, R1 |
| 114 | `hasattr` true → set (any attribute) / false → skip | `update` R4, R5 |
| 118 | flush: changed vs unchanged values, `onupdate`, constraint errors | `update` R7, R9 |
| 118 | flush, no commit | `update` R8 |
| — | no audit fields written | `update` R10 |
| 136 | `Query.get` by primary key: found / not found | `remove` R1, R3 |
| 137 | `db.delete(None)` → `UnmappedInstanceError` today (BUG-101: return `None`) | `remove` R3 |
| 137 | hard delete regardless of `is_deleted` | `remove` R2 |
| 138 | flush: FK restrict / cascade | `remove` R4 |
| 136 | no workspace filter | `remove` R5 |
| 163 | `workspace_id` filter (missing column → `AttributeError`) | `get_by_workspace` R1, R7 |
| 164–165 | offset/limit, defaults 0/100 | `get_by_workspace` R2, R5, R6 |
| 161–166 | no ORDER BY (BUG-100: `id` asc) | `get_by_workspace` R3 |
| 161–166 | no `is_deleted` filter (by design) | `get_by_workspace` R4 |
| 190–191 | id AND workspace_id match / other workspace / missing (missing column → `AttributeError`) | `get_by_id_and_workspace` R1, R2, R3, R5 |
| 187–194 | no `is_deleted` filter (by design) | `get_by_id_and_workspace` R4 |

## Gap log
- G1 (base.cases.md gap G1) — test mechanics — Notes for the test designer: `get` no-`id` error row uses a test-local mapped class (best-practice default, delegated by reviewer).
- G2 (base.cases.md gap G2) — fact + test mechanics — confirmed no model has an FK to `departments.id`; Notes: temporary RESTRICT / CASCADE child tables inside the test transaction (best-practice default, delegated by reviewer).
- G3 (base.cases.md gap G3) — fact — `create` R7 now names the exception: `AttributeError` at model construction, nothing added; row added to `create` Errors.
- G4 (base.cases.md gap G4) — test mechanics — Notes: `get_multi` assertions relative to `N0` rows visible at test start, `skip=N0`; empty-table sub-case of R5 covered via `get_by_workspace` R5 (best-practice default, delegated by reviewer).
- G5 (base.cases.md gap G5) — test mechanics — Notes: BUG-100 xfails force a sequential scan with `SET LOCAL` and arrange heap order ≠ `id` order (best-practice default, delegated by reviewer).
- G6 (base.verify.md finding 1, DISCREPANCY-1) — contradiction / fact — `get` R5 was wrong (claimed autoflush finds unflushed rows); `app/db/session.py:11` and `tests/unit/conftest.py` both use `autoflush=False`. R5 rewritten: pending rows are not found (`None`), the same row is found after an explicit flush; Branch map row added. No bug logged (deliberate session setting) (best-practice default, delegated by reviewer).
