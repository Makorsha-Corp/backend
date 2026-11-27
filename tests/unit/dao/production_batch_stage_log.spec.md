# Spec — `app/dao/production_batch_stage_log.py`

> **Status:** APPROVED (2026-11-02; no questions)
> **Source commit:** e48a092

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Ledgers and logs are history. HR-16: a row linking to another workspace's row is invalid data. Raw lookups stay raw (HR-4 scope).
>
> **Verified by running** (throwaway scripts `cat1.py`, `v4.py`, `v6.py`, harness `h.py`, `w.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns and constraints; defaults; order with a `stage_order` tie after the lower `id` was updated; 101 rows; unknown ids; another workspace; a log whose formula stage was removed. **Not run:** anything over HTTP.

## Review
No questions.

Checked and **not** a new line here: **HR-6** — `stage_order` ascending, then `id` ascending, so the recipe ends in `id`; a tie held after an update. **HR-5, HR-7, HR-8** — no paging, no `LIKE`. **HR-4** — no soft-delete column here or on `production_batches`. **HR-9, HR-10** — the DAO only reads. **HR-15** — no money. **HR-16** — the read follows the row. A removed formula stage leaves the log with `formula_stage_id` `NULL` and its own copy of the name, which is what history should do.

## Overview
`ProductionBatchStageLogDAO` reads `production_batch_stage_logs`, the per-stage record of a batch, seeded from the formula's stages and then edited by hand. Callers: `ProductionBatchManager` (`get_batch_stage_logs`, `update_batch_stage_log`), reached through `/production-batches/{id}/stage-logs/` and `/production-batches/stage-logs/{id}/`.

**Callables:** 2 specified · 2 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Model facts (table `production_batch_stage_logs`):** `workspace_id`, `batch_id` FK CASCADE, `stage_name` String(200) NOT NULL; `stage_order` NOT NULL default `0`; `status` NOT NULL default `pending`; `created_at`, `updated_at` NOT NULL, Python default `utcnow`; `formula_stage_id`, `production_line_id`, `logged_by` FK SET NULL. No unique constraint, so one batch can hold several rows with one `stage_order`. No soft delete.

**Notes for the test designer:** `from app.dao.production_batch_stage_log import production_batch_stage_log_dao`. Parents: `Factory`, `ProductionLine(workspace_id, factory_id, name)`, `ProductionBatch(workspace_id, batch_number, production_line_id, batch_date, status)`.

## Not specified
- `production_batch_stage_log_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods not overridden — covered by the base spec.

---

## `ProductionBatchStageLogDAO.get_by_batch(db, *, batch_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProductionBatchManager.get_batch_stage_logs`)

**Purpose:** The stage records of one batch, in route order.

**Returns:** a `list` of `ProductionBatchStageLog` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `batch_id` and that `workspace_id`. Another workspace returns `[]`; a row of workspace B on a batch of A is returned only for B.
- **R2.** An unknown batch, `0`, or a batch with no logs returns `[]`.
- **R3.** Ordered by `stage_order` ascending, then `id` ascending. Given orders `2`, `1`, `1`, `0`, the result is the `0` row, the two `1` rows by `id`, then the `2` row; the tied pair keeps that order after the lower `id` is updated.
- **R4.** No paging and no cap: 101 logs give 101 rows.
- **R5.** A log whose formula stage was removed is still returned, with `formula_stage_id` `None` and its `stage_name` kept.

**Errors:** none of its own.

**Side effects:** none

---

## `ProductionBatchStageLogDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `ProductionBatchManager.update_batch_stage_log`)

**Purpose:** One stage log by id, inside one workspace.

**Returns:** the `ProductionBatchStageLog`, or `None`.

**Rules:**
- **R1.** An override with the same outcome as `BaseDAO.get_by_id_and_workspace` R1–R3: found, `None` for another workspace, `None` for an unknown id. The model has no `is_deleted`.

**Errors:** none.

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 21–24 | workspace AND batch | `get_by_batch` R1, R2, R5 |
| 25 | `stage_order`, then `id` | `get_by_batch` R3 |
| 26 | `.all()`: no cap; empty / many | `get_by_batch` R2, R4 |
| 34–35 | id AND workspace; `.first()`: row / `None` | `get_by_id_and_workspace` R1 |
| 39 | module singleton | Not specified |
