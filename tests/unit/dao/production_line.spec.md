# Spec — `app/dao/production_line.py`

> **Status:** APPROVED (2026-11-02; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-02.** **Delegated,** decided by Claude under the reviewer's delegation (2026-11-02): P1 `remove`, Q1 `intended`. None of these is the owner's own answer. The house-rule lines stand.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Things of a soft-deleted parent are hidden, their own rows untouched. HR-16: a row linking to another workspace's row is invalid data. Raw lookups stay raw (HR-4 scope).
>
> **Verified by running** (throwaway scripts `cat1.py`, `v_line.py`, harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\proddao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints, indexes and referencing tables; no `ORDER BY` in the four reads; the order changing after an update under a forced sequential scan; 101 rows, the cap, `limit=0`, `skip` past the end, negative values; unknown ids; another workspace; an inactive line; a line of a soft-deleted machine, of a soft-deleted factory, of an inactive factory; a line row of workspace B on a factory of A; `create` with the schema and with a dict; a hard-deleted machine; `get_production_lines` with `factory_id` and `active_only`; `delete_production_line`; re-activation by `update_production_line`; `null` for `machine_id`; a whitespace-only name through the schema. **Not run:** anything over HTTP; the intended behaviour of the bugs below.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically

- **HR-6** `get_by_workspace` R3 — no sort order. This method is a line-for-line copy of `BaseDAO.get_by_workspace` and **shadows** it, so the BUG-100 fix in `app/dao/base.py` does not reach it: the same fix must be made here, or the copy deleted. Intended for this raw lookup: `id` ascending before `skip` / `limit`. The display order of `GET /production-lines/` is the manager's (FU-1 (a)).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-100 (existing, pattern `unordered-pagination`) — no new ID; its Module cell now names this override too. Rules: `get_by_workspace` R3.
- **HR-6** `get_by_factory` R4 — pages with no `ORDER BY`. Verified under a forced sequential scan: "Zulu", "apple", "Banana" came back in that order, and after "Zulu" was updated it moved from first to last. Intended: `name` case-insensitive ascending, then `id` ascending, before `skip` / `limit`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1310 (pattern `unordered-pagination`). Rules: `get_by_factory` R4.
- **HR-6** `get_active_by_workspace` R4 — pages with no `ORDER BY`, same evidence. Intended: as `get_by_factory` R4.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1311 (pattern `unordered-pagination`). Rules: `get_active_by_workspace` R4.
- **Standing decision (soft-deleted parents hide children), HR-4** `get_by_factory` R3a, `get_active_by_workspace` R3a — a live line of a soft-deleted factory is returned by both (verified). Intended: not returned, the line untouched; an inactive-but-live factory hides nothing.
**Answer:** bug — per HR-4 and BUG-882 / BUG-979 precedent (standing decision)
**Resolution:** BUG-1312 (pattern `join-ignores-soft-deleted`). Rules: `get_by_factory` R3a, R3b; `get_active_by_workspace` R3a, R3b.
- **HR-1** `ProductionLineCreate` / `ProductionLineUpdate` — `name` has `min_length=1` only: `"   "` and `" a "` pass unchanged (verified). Intended: stored trimmed; blank or whitespace-only rejected by the schema (422), nothing written. The DAO rules do not change; the check belongs to the schema.
**Answer:** bug — per HR-1 (house rule)
**Resolution:** BUG-1313 (pattern `blank-name-accepted`). No rule of this DAO changes.

Checked and **not** a new line here: **HR-2** — line names are not meant to be unique: nothing checks them and two lines with one name are stored (verified). **HR-3** — no categorical free text. **HR-5** — every filter is in the query; the fix of BUG-1312 must stay in the query. **HR-7** — `GET /production-lines/` already requires `1 <= limit <= 1000` and `skip >= 0`. **HR-8** — no `LIKE`. **HR-9, HR-10** — the DAO only reads. **HR-15** — no money. **HR-16** — the reads follow the row; `create_production_line` and `update_production_line` check the factory and the machine against the workspace. A soft-deleted machine does not hide its line: the line belongs to a factory, the machine link is optional, and a hard delete of the machine detaches the line rather than removing it (`ON DELETE SET NULL`). `get_by_workspace` stays raw (HR-4 scope, machine item DAO P6): the hiding belongs to the manager (FU-1 (b)).

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation (2026-11-02))

### P1. "Lines on this machine" is never used — 🗑️ remove
**Background:** `get_by_machine` lists the lines attached to one machine. A search of `app/`, `scripts/` and `tests/` finds no caller. `machine.spec.md` Q4 ruled the same case `remove`.
**What happens today:** No API request, job or script reaches it.
**Example:** Deleting the method changes nothing a user can see.
**Rules affected:** `get_by_machine` (all)
**Answer:** remove — per machine DAO Q4 precedent: no caller anywhere
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): not specified; listed under **Not specified** and in `docs/testing/dead-code-removal-checklist.md` (`app/dao/production_line.py:66`). Not a bug — no BUG ID.

### New questions

### Q1. Is an inactive line a deleted line? — ✅ intended
**Background:** A production line has no `is_deleted`. `DELETE /production-lines/{id}/` only sets `is_active = False`, and the code calls that "soft delete". The same column can be set by hand: `PUT` with `is_active: false` gives the identical row, `PUT` with `is_active: true` brings a "deleted" line back (verified), and `POST` accepts `is_active: false`. `create_batch` refuses an inactive line. For catalog items the same state was ruled "deleted", because items have no separate deactivate action (inventory DAO Q6). Here there is one. `formula_stage` FU-1 left the same question open for formulas.
**What happens today:** Inactive lines are in `GET /production-lines/` by default, and `?active_only=true` drops them. `get_by_factory` and `get_by_machine` return them whatever is asked: `GET /production-lines/?factory_id=1&active_only=true` still lists them (verified: FU-1 (c)).
**Example:** "Line 3" is deleted. The list still shows it, marked inactive. It can be switched back on, which only works because the list shows it. If it counted as deleted, HR-4 would hide it by default, and switching it back on would need `include_deleted`.
**Rules affected:** `get_by_workspace` R2, `get_by_factory` R3, `get_by_id_and_workspace` R4
**Suggested answer:** `intended` — `is_active` is a switch that can be turned back, so an inactive line is a normal, visible state. Lists keep showing it, `active_only` narrows them, and the rules stand. `delete_production_line` is then a misnomer, and should stamp `updated_by` (FU-1 (d)). Alternative: `bug — is_active = False is the deleted state, as for items`: lists hide it by default, an `include_inactive` option is added (BUG-878 precedent), and `PUT` can no longer set the flag.
**Answer:** intended
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): `is_active` is a switch, an inactive line is a normal, visible state, and HR-4 does not treat it as deleted. Rules unchanged. Rules: `get_by_workspace` R2 ✅, `get_by_factory` R3 ✅, `get_by_id_and_workspace` R4 ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Production line manager, service, endpoint** (`app/managers/production_line_manager.py`, not yet specified) | (a) `get_production_lines` without filters needs a display order: `name` case-insensitive, then `id` (HR-6; BUG-100 only gives `id`). (b) The same list shows lines of a soft-deleted factory (verified through the DAO): the manager must hide them, in the query, before paging. (c) **Verified:** `factory_id` wins over `active_only`, so `active_only=true` with a factory returned an inactive line: pattern `silently-ignored-input`. (d) With Q1, `delete_production_line` is a deactivate. It writes no `updated_by` (verified: `None`), and has no check for open batches: lines with `draft` or `in_progress` batches can be deactivated. (e) **Verified:** `update_production_line` drops `machine_id: null`, so a line cannot be detached from its machine (pattern `exclude-none-blocks-clear`). (f) `update_production_line` stamps `updated_by` even when nothing changes (HR-9, read, not run). | HR-6, standing decision, Q1 |

## Overview
`ProductionLineDAO` reads `production_lines`, the physical lines of a factory, each optionally attached to one machine. Callers: `ProductionLineManager` (`/production-lines/`), `ProductionFormulaManager._validate_stage_refs`, and `ProductionBatchManager`, which reads a batch's line to find its factory before posting stock. It protects workspace isolation on those reads. It validates nothing, writes nothing of its own, and never commits. `get_by_workspace` and `get_by_id_and_workspace` are line-for-line copies of the base methods: they are specified here because they are what runs.

**Callables:** 4 specified · 3 not specified
**Externals to mock:** none. The table has no timestamps.
**Integration-only behavior:** none. (`skip >= 0`, `1 <= limit <= 1000` are enforced by `GET /production-lines/`, not here.)

**Model facts (table `production_lines`, class `app.models.production_line.ProductionLine`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `factory_id` | Integer NOT NULL, FK `factories.id` ON DELETE RESTRICT | — |
| `machine_id` | Integer nullable, FK `machines.id` ON DELETE SET NULL | `NULL` |
| `name` | String(200) NOT NULL | — |
| `description` | Text nullable | `NULL` |
| `is_active` | Boolean NOT NULL | `True` (Python default only) |
| `created_by`, `updated_by` | Integer nullable, FK `profiles.id` ON DELETE SET NULL | `NULL` |

- No `is_deleted`, no timestamps, no unique constraint, no check constraint, no trigger. Plain indexes on `id`, `workspace_id`, `factory_id`, `machine_id`.
- Referenced by `production_batches.production_line_id` (RESTRICT), `production_batch_stage_logs.production_line_id` and `production_formula_stages.production_line_id` (SET NULL).
- Parents, as used by the bug rules: `Factory` (`app.models.factory`): soft delete = `is_deleted = True`, `is_active` unchanged.
- Schemas (`app/schemas/production_line.py`): `ProductionLineCreate` = `factory_id: int`, `machine_id: int | None = None`, `name` (1–200), `description`, `is_active: bool = True` (no `workspace_id`). `ProductionLineUpdate` = `machine_id`, `name`, `description`, `is_active`, all optional.

**Notes for the test designer:**
- `from app.dao.production_line import production_line_dao`. Every parameter after `db` is keyword-only.
- Workspaces from `tests/unit/factories.py` (`make_workspace`). Build the rest directly (add + flush): `Factory(workspace_id, name, abbreviation)`, `Machine(workspace_id, factory_id, name)`, `ProductionLine(workspace_id, factory_id, name)`. The session runs with `autoflush=False`.
- **Row order (BUG-100, BUG-1310, BUG-1311):** physical order is not deterministic and today's result may equal the intended one, so write order cases to the intended order and mark them **non-strict** xfail. Force a sequential scan (`SET LOCAL enable_indexscan = off; SET LOCAL enable_bitmapscan = off; SET LOCAL enable_indexonlyscan = off`). Every other case compares **sets** of ids.
- **BUG-1312:** soft-deleted factory = `is_deleted=True`, with a live line in it, plus a line of a live factory in the same case. Today's result is deterministic → **strict** xfail. For "back once the factory is live", set the flag on the row, flush and call the method: that holds today, so it is a plain pass case.
- A row of workspace B on a factory of A is invalid data (HR-16) and is built directly. Wrap negative paging in `db.begin_nested()`.

## Not specified
- `production_line_dao` — module-level singleton, no logic.
- `ProductionLineDAO.get_by_machine` — dead code, to be removed (decided by Claude under the reviewer's delegation (2026-11-02); P1).
- Inherited `BaseDAO` methods `get`, `get_multi`, `create`, `update`, `remove` — not overridden; covered by the base spec. Only what this model changes is under "Inherited `BaseDAO` methods on `ProductionLine`".

---

## `ProductionLineDAO.get_by_workspace(db, *, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (override identical to `BaseDAO.get_by_workspace`. Used by: `ProductionLineManager.get_production_lines` ← `GET /production-lines/` with neither `factory_id` nor `active_only`)

**Purpose:** All lines of a workspace, one page at a time.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | equality on the row's `workspace_id` |
| `skip` | int, default `0` | not validated |
| `limit` | int, default `100` | not validated |

**Returns:** a `list` of `ProductionLine` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `workspace_id`. Rows of another workspace never appear.
- **R2.** ✅ (Q1) Every line of the workspace is returned whatever its own or its parents' state: inactive lines, lines of a soft-deleted machine, lines of a soft-deleted factory. *(Parents: raw, FU-1 (b).)*
- **R3.** [BUG-100] (HR-6) Rows are ordered by `id` ascending before `skip` / `limit`, so consecutive windows partition the rows with no repeats or gaps. *(Today: no ordering is requested.)*
- **R4.** At most `limit` rows after skipping `skip`; with the defaults at most 100: given 101 rows, exactly 100.
- **R5.** An unknown workspace, a workspace with no rows, `skip` at or past the number of rows, or `limit=0` returns `[]`.
- **R6.** A negative `limit` or `skip` makes Postgres reject the query (see Errors).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`, `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`, `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |

**Side effects:** none

---

## `ProductionLineDAO.get_by_factory(db, *, factory_id, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProductionLineManager.get_production_lines` ← `GET /production-lines/?factory_id=…`)

**Purpose:** The lines of one factory, one page at a time.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `factory_id` | int | equality on the row's `factory_id`; not validated |
| `workspace_id` | int | equality on the row's `workspace_id` |
| `skip` | int, default `0` | not validated |
| `limit` | int, default `100` | not validated |

**Returns:** a `list` of `ProductionLine` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `factory_id` and that `workspace_id`. Rows of another factory are never returned.
- **R2.** Workspace isolation follows the row: the right factory with another workspace returns `[]`. Only the row's own `workspace_id` is compared: a row of workspace B on a factory of A is returned for B and not for A.
- **R3.** ✅ (Q1) An inactive line is returned. An unknown factory, `factory_id=0`, or a factory with no lines returns `[]`.
- **R3a.** [BUG-1312] When the factory is soft-deleted (`factories.is_deleted = True`), `[]` is returned. *(Today: its lines are returned.)*
- **R3b.** What surrounds R3a, holding today and after the fix: (1) the call changes nothing; (2) a factory with `is_active = False`, `is_deleted = False` hides nothing; (3) once the factory is no longer deleted, the lines are returned again, unchanged.
- **R4.** [BUG-1310] (HR-6) Rows are ordered by `name` case-insensitive ascending, then `id` ascending, before `skip` / `limit`: "Zulu", "apple", "Banana" come back "apple", "Banana", "Zulu"; two lines named "Press" and "press" come back lower `id` first. *(Today: no ordering is requested.)*
- **R5.** At most `limit` rows after skipping `skip`; with the defaults at most 100: given 101 lines, exactly 100. Consecutive windows partition the rows (relies on R4).
- **R6.** `limit=0` or `skip` at or past the number of rows returns `[]`.
- **R7.** A negative `limit` or `skip` makes Postgres reject the query, as in `get_by_workspace`.

**Errors:** as `get_by_workspace`.

**Side effects:** none

---

## `ProductionLineDAO.get_active_by_workspace(db, *, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProductionLineManager.get_production_lines` ← `GET /production-lines/?active_only=true`, when no `factory_id` is given)

**Purpose:** The active lines of a workspace, one page at a time.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | equality on the row's `workspace_id` |
| `skip` | int, default `0` | not validated |
| `limit` | int, default `100` | not validated |

**Returns:** a `list` of `ProductionLine` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `workspace_id` and `is_active = True`. An inactive line is not returned and takes no place in the page. Rows of another workspace never appear.
- **R2.** A line of a soft-deleted machine is returned.
- **R3.** An unknown workspace, a workspace with no active lines, `skip` past the end, or `limit=0` returns `[]`.
- **R3a.** [BUG-1312] A line whose factory is soft-deleted is not returned and takes no place in the page. *(Today: it is returned.)*
- **R3b.** What surrounds R3a, as `get_by_factory` R3b.
- **R4.** [BUG-1311] (HR-6) Rows are ordered as `get_by_factory` R4. *(Today: no ordering is requested.)*
- **R5.** At most `limit` rows after skipping `skip`; with the defaults at most 100: given 101 active lines, exactly 100. Consecutive windows partition the rows (relies on R4).
- **R6.** A negative `limit` or `skip` makes Postgres reject the query, as in `get_by_workspace`.

**Errors:** as `get_by_workspace`.

**Side effects:** none

---

## `ProductionLineDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (override identical to `BaseDAO.get_by_id_and_workspace`. Used by: `ProductionLineManager.get_production_line`; `ProductionFormulaManager._validate_stage_refs`; `ProductionBatchManager.create_batch`, `start_batch`, `complete_batch`, `post_outputs_to_finished_goods`, `add_batch_stage_log`, `update_batch_stage_log`)

**Purpose:** One line by id, inside one workspace.

**Returns:** the `ProductionLine`, or `None`.

**Rules:**
- **R1.** Given a row with that id in that workspace, it is returned.
- **R2.** Given a row with that id in another workspace, `None` is returned (indistinguishable from not found).
- **R3.** An unknown id or `id=0` returns `None`, with no error.
- **R4.** ✅ (Q1) The state of the line and of its parents is not looked at: an inactive line, and a line of a soft-deleted factory or machine, are returned. A raw lookup: the batch manager needs the line of a running batch whatever happened to it since.

**Errors:** none.

**Side effects:** none

---

## Inherited `BaseDAO` methods on `ProductionLine`
**Shape:** create / update / get
**Persistence:** writes / reads
**Visibility:** public (`create`, `update` with a dict, `get` ← `ProductionLineManager`; `get_multi`, `remove`: no caller on this DAO)

**Purpose:** `ProductionLineDAO` does not override these; the base spec applies. Only what this model changes is stated.

**Rules:**
- **R1.** `create` with a dict holding `workspace_id`, `factory_id`, `name` gives `is_active = True`, `machine_id = None`.
- **R2.** `create` with a `ProductionLineCreate` always fails: the schema has no `workspace_id`, so the flush raises `IntegrityError` (`NotNullViolation`, pgcode `23502`) and nothing is saved.
- **R3.** Two lines with one name in one factory are both saved: nothing makes a name unique.
- **R4.** After a machine row is hard-deleted, the database sets the line's `machine_id` to `NULL` and the line stays.

**Errors:** as in the base spec.

**Side effects:** as in the base spec.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 16–17, 39–40, 89–90 | keyword-only parameters; defaults `skip=0`, `limit=100` | Notes; `get_by_workspace` R4; `get_by_factory` R5; `get_active_by_workspace` R5 |
| 31–37 | `workspace_id` filter only; no `ORDER BY` (BUG-100); `limit=0`; negative values; empty / many | `get_by_workspace` R1–R6, Errors |
| 55–64 | `workspace_id` AND `factory_id`; line and factory state not read (BUG-1312); no `ORDER BY` (BUG-1310) | `get_by_factory` R1–R7 |
| 104–113 | `workspace_id` AND `is_active`; factory state not read (BUG-1312); no `ORDER BY` (BUG-1311) | `get_active_by_workspace` R1–R6 |
| 129–136 | id AND `workspace_id`; `.first()` on the primary key: row / `None` | `get_by_id_and_workspace` R1–R4 |
| 139 | module singleton | Not specified |
| `base.py` 76–84 | `create`: dict / schema (no `workspace_id`); Python default for `is_active`; no uniqueness | inherited R1, R2, R3 |
| `models/production_line.py` 21 | `machine_id` `ON DELETE SET NULL` | inherited R4 |
