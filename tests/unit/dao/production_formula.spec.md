# Spec — `app/dao/production_formula.py`

> **Status:** APPROVED (2026-11-02; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-02.** **Delegated,** decided by Claude under the reviewer's delegation (2026-11-02): Q1 `intended`, Q2 `bug` (BUG-1329). None of these is the owner's own answer. The house-rule lines stand.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. HR-16: a row linking to another workspace's row is invalid data. Raw lookups stay raw (HR-4 scope).
>
> **Verified by running** (throwaway scripts `cat1.py`, `v_formula.py`, `v_prod.py`, harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\proddao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints, indexes and referencing tables, including that **no unique constraint or index exists on `formula_code`**; no `ORDER BY` in the four reads; the order changing after an update under a forced sequential scan; two rows with one code, and which one `get_by_formula_code` returns before and after an update; case, spaces, blank and another workspace; a deactivated formula's code refused for reuse; variants and whitespace-only values stored through `create_formula`; the default flag through `create_formula` and `update_formula`, including two live defaults; 101 rows, the cap, negative values; defaults through `create`; the `limit` schema of `GET /production-formulas/` from `app.openapi()`. **Not run:** anything over HTTP; two concurrent transactions; the intended behaviour of the bugs below.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically

- **HR-6** `get_by_workspace` R3 — no sort order. A line-for-line copy of `BaseDAO.get_by_workspace` that **shadows** it, so the BUG-100 fix does not reach it. Intended for this raw lookup: `id` ascending before `skip` / `limit`. The display order of `GET /production-formulas/` is the manager's (FU-1 (a)).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-100 (existing, pattern `unordered-pagination`) — no new ID; its Module cell now names this override too. Rules: `get_by_workspace` R3.
- **HR-6** `get_active_by_workspace` R3 — pages with no `ORDER BY`. Verified: "Zulu" moved from first to last after an update. Intended: `name` case-insensitive ascending, then `id` ascending, before `skip` / `limit`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1314 (pattern `unordered-pagination`). Rules: `get_active_by_workspace` R3.
- **Standing decision (missing `ORDER BY`)** `get_default_formulas` R4 — no sort order. Its only caller clears the flag on every row it gets, so nothing visible depends on it today. Intended: as `get_active_by_workspace` R3.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1315 (pattern `unordered-pagination`). Rules: `get_default_formulas` R4.
- **HR-2** `get_by_formula_code` R3, R4 — `formula_code` is unique only by a Python read before the insert. There is **no unique index** (verified: two rows with `YARN-1` are stored), the check is exact (`re-1` and ` RE-1 ` were accepted next to `RE-1`, verified), and on two rows the row returned changed after an update (verified). Precedent for codes: BUG-874 (account code), BUG-946 (SKU), BUG-895 (abbreviation). Intended: stored trimmed, compared trimmed and case-insensitively, enforced by a unique index per workspace over every row (Q1: an inactive formula counts, and the table has no soft-delete column); a violation surfaces as a refusal, never 500. **The index cannot be built while duplicates exist.** Whether real data holds any is unknown; this query tells: `SELECT workspace_id, lower(trim(formula_code)), count(*) FROM production_formulas GROUP BY 1, 2 HAVING count(*) > 1`.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** BUG-1316 (pattern `python-only-uniqueness`). Rules: `get_by_formula_code` R3, R4; inherited R3, R3a.
- **HR-1** `ProductionFormulaCreate` / `ProductionFormulaUpdate` — `name` and `formula_code` have `min_length=1` only: a formula with code `"   "` and name `"   "` was stored, and ` RE-1 ` kept its spaces (verified through `create_formula`). Intended: stored trimmed; blank or whitespace-only rejected by the schema (422), nothing written. The DAO rules do not change.
**Answer:** bug — per HR-1 (house rule)
**Resolution:** BUG-1317 (pattern `blank-name-accepted`). No rule of this DAO changes.
- **HR-7** `get_by_workspace` R6, `get_active_by_workspace` R5 — `GET /production-formulas/` has `limit: Query(100, le=100)` with no lower bound (verified in the OpenAPI schema: `maximum` 100, no `minimum`), so `0` gives an empty list and a negative value a database error. Intended: `limit >= 1`, 422 otherwise; the cap of 100 stays. The DAO rule does not change; the check belongs to the endpoint.
**Answer:** bug — per HR-7 (house rule)
**Resolution:** BUG-1318 (pattern `missing-limit-lower-bound`).

Checked and **not** a new line here: **HR-3** — no categorical free text. **HR-5** — every filter is in the query. **HR-8** — no `LIKE`. **HR-9, HR-10** — the DAO only reads. **HR-15** — no money. **HR-16** — the reads follow the row; the table has no link to another workspace-owned row besides its own children. `get_by_workspace` stays raw (HR-4 scope). A formula has no parent but the workspace, so the standing decision on soft-deleted parents has nothing to do here.

### New questions

### Q1. Is an inactive formula a deleted formula? — ✅ intended
**Background:** A formula has no `is_deleted`. `DELETE /production-formulas/{id}/` sets `is_active = False` and `is_default = False`, and the code calls that "soft delete". `PUT` can set `is_active` either way, so a "deleted" formula can be brought back. `POST` accepts `is_active: false`. `create_batch` refuses an inactive formula. The same question is open for production lines (`production_line.spec.md` Q1), and `production_formula_stage.spec.md` FU-1 says the stages follow the answer.
**What happens today:** Inactive formulas are in `GET /production-formulas/` by default, and `?active_only=true` drops them. `get_by_formula_code` finds them, so a deleted formula's code cannot be used again.
**Example:** Formula `YARN-1` is deleted. Creating a new `YARN-1` is refused with "Formula code 'YARN-1' already exists in this workspace" (verified), while the code stays taken for good unless the old one is switched back on.
**Rules affected:** `get_by_workspace` R2, `get_by_formula_code` R5, `get_by_id_and_workspace` R4
**Suggested answer:** `intended` — `is_active` is a switch, and an inactive formula is a normal, visible state, as suggested for lines; its code stays taken, so the live index of BUG-1316 covers every row. Batches keep a link to the formula, so old batches stay readable. Alternative: `bug — is_active = False is the deleted state`: the code is free again, lists hide the row by default, and an `include_inactive` option is added (BUG-878 precedent).
**Answer:** intended
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): an inactive formula is a normal, visible state and its code stays taken, so the BUG-1316 index covers every row. The stages follow: `production_formula_stage` R5 stands and its FU-1 (a) is answered. Rules: `get_by_workspace` R2 ✅, `get_by_formula_code` R5 ✅, `get_by_id_and_workspace` R4 ✅.

### Q2. A workspace can end up with two default formulas — 🐞 BUG-1329
**Background:** Setting a formula as default clears the flag on the others, through `get_default_formulas`, which looks only at **active** formulas. `DELETE` clears the flag, but `PUT` with `is_active: false` does not. No index stops two defaults. Nothing in the application reads `is_default` except this clearing step, so the flag has no effect on batches yet.
**What happens today:** A deactivated default keeps its flag and is invisible to the clearing step. When it is switched back on, there are two.
**Example:** D2 is the default. `PUT` sets it inactive. D3 is created as default. `PUT` sets D2 active. `get_default_formulas` returns D2 and D3 (verified).
**Rules affected:** `get_default_formulas` R2, R3
**Suggested answer:** `bug — deactivating a formula clears is_default, as DELETE already does`, in `update_formula`. Then an inactive formula can never hold the flag, and the DAO rules stand. `get_default_formulas` keeps its name and active filter.
**Answer:** bug — deactivating a formula clears `is_default`, as `DELETE` already does
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): 🐞 BUG-1329 (pattern `flag-survives-deactivation`). The fix is in `ProductionFormulaManager.update_formula` and is tested there (FU-1 (g)); the DAO's rules stand. Rules: `get_default_formulas` R2 ✅, R3 ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Production formula manager, service, endpoint** (`app/managers/production_formula_manager.py`, not yet specified) | (a) `get_formulas` needs a display order: `name` case-insensitive, then `id` (HR-6; BUG-100 only gives `id`). (b) BUG-1316: a lost race on `create_formula` is an `IntegrityError`; it must surface as the normal refusal, never 500. Today the duplicate is `ValueError` → `BusinessRuleError` (422). (c) `update_formula` and `delete_formula` read through `get` and use `does not belong to workspace`: BUG-1022, already logged. (d) `get_formula_items` lists a deactivated formula's lines, and `add_formula_item` adds to a deactivated formula: read `production_formula_item.spec.md`. (e) `update_formula` stamps `updated_by` when nothing changes (HR-9, read, not run). (f) `_clear_other_defaults` writes no `updated_by` on the formulas it changes. (g) **BUG-1329, logged:** `update_formula` with `is_active: false` must also set `is_default = False`; re-activating does not restore the flag. | HR-6, HR-2, Q1 |

## Overview
`ProductionFormulaDAO` reads `production_formulas`, the recipes of a workspace: a code, a name and a version, with the ingredients in `production_formula_items` and the route in `production_formula_stages`. Callers: `ProductionFormulaManager` (`/production-formulas/`) and `ProductionBatchManager` (`create_batch`, `update_batch`, which check a batch's formula). It protects workspace isolation on those reads. It validates nothing, writes nothing of its own, and never commits. `get_by_workspace` and `get_by_id_and_workspace` are line-for-line copies of the base methods: they are specified here because they are what runs.

**Callables:** 5 specified · 2 not specified
**Externals to mock:** `utcnow` (`app.utils.time`, through the model's `created_at` / `updated_at` defaults) only if a case asserts their value.
**Integration-only behavior:** none. (`skip >= 0`, `limit <= 100` are enforced by `GET /production-formulas/`, not here.)

**Model facts (table `production_formulas`, class `app.models.production_formula.ProductionFormula`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `formula_code` | String(50) NOT NULL, plain index | — |
| `name` | String(200) NOT NULL | — |
| `description` | Text nullable | `NULL` |
| `version` | Integer NOT NULL | `1` (Python default only) |
| `estimated_duration_minutes` | Integer nullable | `NULL` |
| `is_active` | Boolean NOT NULL | `True` (Python default only) |
| `is_default` | Boolean NOT NULL | `False` (Python default only) |
| `created_by`, `updated_by` | Integer nullable, FK `profiles.id` ON DELETE SET NULL | `NULL` |
| `created_at`, `updated_at` | DateTime NOT NULL | Python `utcnow`; `updated_at` also on update |

- No `is_deleted`, no unique constraint, no check constraint, no trigger.
- Referenced by `production_formula_items.formula_id`, `production_formula_stages.formula_id` (CASCADE) and `production_batches.formula_id` (SET NULL).
- Schemas (`app/schemas/production_formula.py`): `ProductionFormulaCreate` = `formula_code` (1–50), `name` (1–200), `description`, `version >= 1`, `estimated_duration_minutes >= 0`, `is_active = True`, `is_default = False` (no `workspace_id`). `ProductionFormulaUpdate` = `name`, `description`, `estimated_duration_minutes`, `is_active`, `is_default`, all optional. `formula_code` and `version` cannot be changed through the API.

**Notes for the test designer:**
- `from app.dao.production_formula import production_formula_dao`. Every parameter after `db` is keyword-only.
- Workspaces from `tests/unit/factories.py` (`make_workspace`). Build `ProductionFormula(workspace_id, formula_code, name)` directly. The session runs with `autoflush=False`.
- **Row order (BUG-100, BUG-1314, BUG-1315):** as `production_line.spec.md`: intended order, **non-strict** xfail, forced sequential scan. Every other case compares **sets** of ids.
- **Two rows for one key (BUG-1316, inherited R3, R3a):** the first row is built directly; the second goes through `create` or `update` inside `with db.begin_nested():` inside `pytest.raises(IntegrityError)`; assert `.orig.pgcode == "23505"`, not the index name. Today nothing is raised → **strict** xfail. Build no other case with two rows for one normalised code in one workspace: it would fail once the index exists.

## Not specified
- `production_formula_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods `get`, `get_multi`, `create`, `update`, `remove` — not overridden; covered by the base spec. Only what this model changes is under "Inherited `BaseDAO` methods on `ProductionFormula`".

---

## `ProductionFormulaDAO.get_by_workspace(db, *, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (override identical to `BaseDAO.get_by_workspace`. Used by: `ProductionFormulaManager.get_formulas` ← `GET /production-formulas/` without `active_only`)

**Purpose:** All formulas of a workspace, one page at a time.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | equality on the row's `workspace_id` |
| `skip` | int, default `0` | not validated |
| `limit` | int, default `100` | not validated |

**Returns:** a `list` of `ProductionFormula` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `workspace_id`. Rows of another workspace never appear.
- **R2.** ✅ (Q1) An inactive formula is returned and takes a place in the page.
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

## `ProductionFormulaDAO.get_by_formula_code(db, *, formula_code, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `ProductionFormulaManager.create_formula`, as the duplicate check: anything found → refusal)

**Purpose:** The formula with one code, if any.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `formula_code` | str | see R3; not validated |
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** the `ProductionFormula`, or `None`.

**Rules:**
- **R1.** Given a row with that code in that workspace, it is returned.
- **R2.** The same code in another workspace is not matched: each workspace has its own codes. No match, including `""`, returns `None`, with no error.
- **R3.** [BUG-1316] (HR-2) The code is compared trimmed and case-insensitively: `yarn-1` and ` YARN-1 ` both find `YARN-1`. *(Today: exact match; both return `None`.)*
- **R4.** With BUG-1316 a code has at most one row per workspace, so there is nothing to choose between and no order is needed. No case of its own: inherited R3 tests the index. *(Today: two rows are possible, and the row returned is whatever the database produces. Verified: the first row was returned, and after it was updated the second one was.)*
- **R5.** ✅ (Q1) An inactive formula is found, so its code stays taken.

**Errors:** none.

**Side effects:** none

---

## `ProductionFormulaDAO.get_active_by_workspace(db, *, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProductionFormulaManager.get_formulas` ← `GET /production-formulas/?active_only=true`)

**Purpose:** The active formulas of a workspace, one page at a time.

**Inputs:** as `get_by_workspace`.

**Returns:** a `list` of `ProductionFormula` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `workspace_id` and `is_active = True`. An inactive formula is not returned and takes no place in the page. Rows of another workspace never appear.
- **R2.** An unknown workspace, a workspace with no active formulas, `skip` past the end, or `limit=0` returns `[]`.
- **R3.** [BUG-1314] (HR-6) Rows are ordered by `name` case-insensitive ascending, then `id` ascending, before `skip` / `limit`: "Zulu", "apple", "Banana" come back "apple", "Banana", "Zulu". *(Today: no ordering is requested.)*
- **R4.** At most `limit` rows after skipping `skip`; with the defaults at most 100: given 101 active formulas, exactly 100. Consecutive windows partition the rows (relies on R3).
- **R5.** A negative `limit` or `skip` makes Postgres reject the query, as in `get_by_workspace`.

**Errors:** as `get_by_workspace`.

**Side effects:** none

---

## `ProductionFormulaDAO.get_default_formulas(db, *, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** internal (used by: `ProductionFormulaManager._clear_other_defaults`, which clears the flag on what it gets)

**Purpose:** The active formulas of a workspace flagged as default.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** a `list` of `ProductionFormula` (possibly empty). The docstring says "all default formulas"; only active ones are returned.

**Rules:**
- **R1.** Returns the rows with that `workspace_id`, `is_default = True` and `is_active = True`. A workspace with none returns `[]`. Rows of another workspace never appear.
- **R2.** ✅ (Q2) A formula with `is_default = True` and `is_active = False` is not returned. BUG-1329 stops the API from making such a row; here it is built directly.
- **R3.** ✅ (Q2) Every matching row is returned, with no paging and no cap: two defaults, built directly, give two rows.
- **R4.** [BUG-1315] Rows are ordered as `get_active_by_workspace` R3. *(Today: no ordering is requested.)*

**Errors:** none.

**Side effects:** none

---

## `ProductionFormulaDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (override identical to `BaseDAO.get_by_id_and_workspace`. Used by: `ProductionFormulaManager.get_formula`, `add_formula_item`, `get_formula_items`, stage methods; `ProductionBatchManager.create_batch`, `update_batch`)

**Purpose:** One formula by id, inside one workspace.

**Returns:** the `ProductionFormula`, or `None`.

**Rules:**
- **R1.** Given a row with that id in that workspace, it is returned.
- **R2.** Given a row with that id in another workspace, `None` is returned (indistinguishable from not found).
- **R3.** An unknown id or `id=0` returns `None`, with no error.
- **R4.** ✅ (Q1) An inactive formula is returned: `create_batch` needs the row to answer "is not active".

**Errors:** none.

**Side effects:** none

---

## Inherited `BaseDAO` methods on `ProductionFormula`
**Shape:** create / update / get
**Persistence:** writes / reads
**Visibility:** public (`create`, `update` with a dict, `get` ← `ProductionFormulaManager`; `get_multi`, `remove`: no caller on this DAO)

**Purpose:** `ProductionFormulaDAO` does not override these; the base spec applies. Only what this model changes is stated.

**Rules:**
- **R1.** `create` with a dict holding `workspace_id`, `formula_code`, `name` gives `version = 1`, `is_active = True`, `is_default = False`, and `created_at`, `updated_at` set.
- **R2.** `create` with a `ProductionFormulaCreate` always fails: the schema has no `workspace_id`, so the flush raises `IntegrityError` (`NotNullViolation`, pgcode `23502`) and nothing is saved.
- **R3.** [BUG-1316] (HR-2) A second row with the same trimmed, case-insensitive `formula_code` in one workspace is refused by the database: `create` raises `sqlalchemy.exc.IntegrityError` at the flush (pgcode `23505`), the DAO does not catch or translate it, nothing is saved. The same code under another workspace is accepted. *(Today: the second row is saved and no error is raised.)*
- **R3a.** [BUG-1316] The same applies to `update` moving a row onto a taken code. *(Today: the change is saved.)*

**Errors:** as in the base spec, plus R3.

**Side effects:** as in the base spec.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 19–20, 65–66 | keyword-only parameters; defaults `skip=0`, `limit=100` | Notes; `get_by_workspace` R4; `get_active_by_workspace` R4 |
| 34–40 | `workspace_id` filter only; no `ORDER BY` (BUG-100); `limit=0`; negative values; empty / many | `get_by_workspace` R1–R6, Errors |
| 56–63 | `workspace_id` AND exact `formula_code` (BUG-1316); `is_active` not read; `.first()` with no order: row / `None` | `get_by_formula_code` R1–R5 |
| 80–89 | `workspace_id` AND `is_active`; no `ORDER BY` (BUG-1314) | `get_active_by_workspace` R1–R5 |
| 104–112 | `workspace_id` AND `is_default` AND `is_active`; no paging, no `ORDER BY` (BUG-1315) | `get_default_formulas` R1–R4 |
| 128–135 | id AND `workspace_id`; `.first()` on the primary key: row / `None` | `get_by_id_and_workspace` R1–R4 |
| 137 | module singleton | Not specified |
| `base.py` 76–84 | `create`: dict / schema (no `workspace_id`); Python defaults; unique index (BUG-1316) | inherited R1, R2, R3 |
| `base.py` 108–119 | `update`: unique index (BUG-1316) | inherited R3a |
