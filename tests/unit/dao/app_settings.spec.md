# Spec — `app/dao/app_settings.py`

> **Status:** APPROVED (2026-11-02; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-02.** **Delegated:** Q1 accepted as suggested, decided by Claude under the reviewer's delegation (2026-11-02); not the owner's own answer. BUG-1225 supersedes BUG-1213, since the index leaves one candidate. Added by running (`ar_1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refdao\`, rolled back): a temporary normalised unique index gives 23505 for the same name and for `" feat "` against `Feat`, and allows the same name in another workspace.

> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Base behaviour is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Verified by running** (scripts `rd_h.py`, `rd_0.py`, `rd_3.py`, `rd_4b.py` in `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\refdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints, indexes, no trigger; `AppSettingsService` create, update and delete, including another workspace's id and a blank name; two rows of one name; **the row returned for that name: with an index scan it stayed the lower `id`; with sequential scans forced it moved to the higher `id` after the lower row was updated**; every name below; the default of `enabled`. **Not run:** anything over HTTP; the intended behavior of BUG-1213.

## Review
> Answered 2026-11-02.

| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | One workspace can hold two settings of one name, with different values | bug — per HR-2 | Claude, delegated |

### House-rule violations — applied automatically

- **HR-6** `get_by_name` R4 — a top-1 with no `ORDER BY`: with two rows of one name, the row returned follows physical row order. Intended: the lowest `id`, until Q1's constraint leaves one row.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1213 (pattern `unordered-pagination`), **superseded by BUG-1225**: Q1's index leaves one candidate, so `.first()` needs no order. Rules: `get_by_name` R4.

Checked and **not** a new line here: **HR-4** — no soft-delete column. **HR-7** — `GET /app-settings/` has no lower bound on `limit`: BUG-1217, not this DAO's. **HR-8** — exact match, no `LIKE`. **HR-9, HR-10** — the table has no audit columns, and a flag is no harmful state. **HR-15** — no money. **HR-16** — the query compares the row's own `workspace_id`; nothing links out.

### New questions

### Q1. One workspace can hold two settings of one name — 🐞 BUG-1225
**Background:** An app setting is a named on/off flag of a workspace. `GET /app-settings/name/{name}/` finds one by name, so the name works as its key. `POST /app-settings/` has no duplicate check and the table has no unique constraint. No backend code and no frontend page reads these flags today, so nothing changes in the product for now.
**What happens today:** Two `POST`s of `{"name": "feat", ...}` store two rows, one on and one off, and the by-name lookup returns one of them. (Verified.)
**Example:** `feat` is created on, then again off. `GET /app-settings/name/feat/` says on; a client that lists all settings sees both.
**Rules affected:** `get_by_name` R4
**Suggested answer:** `bug — per HR-2: names are unique per workspace, case-insensitive after trimming, with a unique index; a duplicate is 409`. A setting has no soft delete, so the index covers every row. Not a house-rule line, because HR-2 applies "where names must be unique" and the code never says so; the by-name lookup is the reason to say it. Alternative: `intended`, since nothing reads the flags.
**Answer:** bug — per HR-2: names are unique per workspace, case-insensitive after trimming, with a unique index; a duplicate is 409
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): 🐞 BUG-1225 (pattern `python-only-uniqueness`). Rows that already repeat a name must be cleaned up before the index. Rules: `get_by_name` R4, `create` N1, N2.

## Overview
`DAOAppSettings` is the base DAO plus a lookup of one workspace's flag by name. Callers: `AppSettingsService` only, reached by `/app-settings/`. It never commits.

**Callables:** 1 specified · 2 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Model facts (table `app_settings`, class `app.models.app_settings.AppSettings`):** `id` Integer PK. `workspace_id` Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE. `name` String NOT NULL, no unique constraint today (BUG-1225 adds one). `enabled` Boolean NOT NULL, Python default `False`. Nothing references it. No trigger, no soft-delete column, no audit columns.

**Notes for the test designer:**
- Use the module singleton `app_settings_dao`. Every parameter after `db` is keyword-only. Workspaces from `tests/unit/factories.py`; build `AppSettings(workspace_id, name, enabled)` directly.
- N1 and N2 are written to the index: strict xfail on BUG-1225. Call in `with db.begin_nested():`.

## Not specified
- `app_settings_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — `tests/unit/dao/base.spec.md`. `AppSettingsService` calls `get_by_workspace`, `get_by_id_and_workspace`, `create`, `update`, `remove`.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **App settings service and schema** (`app/services/app_settings_service.py`, `app/schemas/app_settings.py`) | Verified: a name of `"   "` is stored (HR-1, as BUG-004). Read: `GET /app-settings/` is `id` order only after BUG-100, so HR-6's display order is the service's. BUG-1217 for `limit`. | reading the callers |

---

## `DAOAppSettings.get_by_name(db, *, name, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `AppSettingsService.get_by_name` ← `GET /app-settings/name/{name}/`, passing the current workspace)

**Purpose:** One workspace's flag, by name.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `name` | str | exact compare |
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** the row, or `None`.

**Rules:**
- **R1.** The row of that workspace with exactly that name is returned.
- **R2.** Workspace isolation: a row of the same name in another workspace is never returned; a call with another workspace, or `0`, returns `None`.
- **R3.** The compare is exact: `"FEAT"`, `" feat"`, `"feat "` and `"fe%"` find nothing for `feat`. `""` and `None` return `None`, with no error.
- **R4.** [BUG-1225] (Q1, HR-2) At most one row of a workspace can carry a name, so the query has one candidate (`create` N1, N2). The lookup itself stays exact, R3. *(Today: two rows can match, and the row returned follows physical row order. Verified.)*

**Errors:** none. **Side effects:** none

---

## Inherited `BaseDAO.create` on this table
- **N1.** [BUG-1225] (Q1, HR-2) A second row with the same workspace and name raises `IntegrityError`, `.orig.pgcode == "23505"`, nothing stored. The same name in another workspace is stored. *(Today: stored. Verified.)*
- **N2.** [BUG-1225] (Q1, HR-2) The compare is case-insensitive after trimming: `" feat "` collides with `Feat`. *(Today: both stored.)*

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 19–21 | keyword-only parameters | Notes for the test designer |
| 33–37 | workspace AND exact name | R1, R2, R3 |
| 38 | `.first()`: row / `None` | R1, R3, R4 |
| 41 | module singleton | Not specified |
