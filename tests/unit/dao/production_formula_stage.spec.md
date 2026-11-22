# Spec — `app/dao/production_formula_stage.py`

> **Status:** APPROVED (2026-11-02; no questions)
> **Source commit:** e48a092

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. HR-16: a row linking to another workspace's row is invalid data. Raw lookups stay raw (HR-4 scope).
>
> **Verified by running** (throwaway scripts `cat1.py`, `v4.py`, `v6.py`, harness `h.py`, `w.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns and constraints; order with negative, zero and positive `stage_order`; 101 rows; unknown ids; another workspace; `uq_formula_stage_order` across workspaces; a deactivated formula through the DAO and `get_formula_stages`. **Not run:** anything over HTTP; two concurrent transactions.

## Review
No questions.

Checked and **not** a new line here: **HR-6** on `get_by_formula` — ordered by `stage_order` alone, but `uq_formula_stage_order` makes it unique per formula, so there is no tie. **HR-5, HR-7, HR-8** — no paging, no `LIKE`. **HR-4** — the table has no soft-delete column, and the raw read of a deactivated formula is FU-1. **HR-9, HR-10** — the DAO only reads. **HR-15** — no money. **HR-16** — the read follows the row; the manager checks line, machine and item against the workspace in `_validate_stage_refs`.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Production formula manager** (`app/managers/production_formula_manager.py`, not yet specified) | (a) `delete_formula` is a soft delete by `is_active = False`. `get_formula` and `get_formula_stages` still answer for a deactivated formula (verified for stages). Whether a deactivated formula counts as deleted for HR-4 is the manager's question. Its stages follow the answer. (b) `stage_order` uniqueness is checked in Python first; on a race `uq_formula_stage_order` is an `IntegrityError` unless the manager maps it (read, not run). | reading the callers |

## Overview
`ProductionFormulaStageDAO` reads `production_formula_stages`, the ordered route of a production formula. Callers: `ProductionFormulaManager` (list, uniqueness check, get) and `ProductionBatchManager._seed_stage_logs_from_formula`, reached through `/production-formulas/{id}/stages/`, `/production-formulas/stages/{id}/` and batch creation.

**Callables:** 2 specified · 2 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Model facts (table `production_formula_stages`):** `workspace_id`, `formula_id` FK CASCADE, `stage_order`, `name` String(200) are NOT NULL. `production_line_id`, `machine_id`, `expected_output_item_id` FK SET NULL, nullable. `uq_formula_stage_order` on `(formula_id, stage_order)`, refused even under another workspace. No soft delete. `production_batch_stage_logs.formula_stage_id` references it with SET NULL.

**Notes for the test designer:** `from app.dao.production_formula_stage import production_formula_stage_dao`. Parent: `ProductionFormula(workspace_id, formula_code, name, version)`. A row of workspace B on a formula of A is built directly.

## Not specified
- `production_formula_stage_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods not overridden — covered by the base spec.

---

## `ProductionFormulaStageDAO.get_by_formula(db, *, formula_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `get_formula_stages`, `add_formula_stage`, `update_formula_stage`, `_seed_stage_logs_from_formula`)

**Purpose:** The stages of one formula, in route order.

**Returns:** a `list` of `ProductionFormulaStage` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `formula_id` and that `workspace_id`. Another workspace returns `[]`; a row of workspace B on a formula of A is returned only for B.
- **R2.** An unknown formula, `0`, or a formula with no stages returns `[]`.
- **R3.** Ordered by `stage_order` ascending, whatever the insert order: `-1`, `0`, `3`.
- **R4.** No paging and no cap: 101 stages give 101 rows.
- **R5.** The formula's state is not looked at: the stages of a deactivated formula are returned.

**Errors:** none of its own.

**Side effects:** none

---

## `ProductionFormulaStageDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `update_formula_stage`, `remove_formula_stage`)

**Purpose:** One stage by id, inside one workspace.

**Returns:** the `ProductionFormulaStage`, or `None`.

**Rules:**
- **R1.** An override with the same outcome as `BaseDAO.get_by_id_and_workspace` R1–R3: found, `None` for another workspace, `None` for an unknown id. The model has no `is_deleted`.

**Errors:** none.

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 21–24 | workspace AND formula; no formula state | `get_by_formula` R1, R2, R5 |
| 25 | `stage_order` ascending | `get_by_formula` R3 |
| 26 | `.all()`: no cap; empty / many | `get_by_formula` R2, R4 |
| 34–35 | id AND workspace; `.first()`: row / `None` | `get_by_id_and_workspace` R1 |
| 38 | module singleton | Not specified |
