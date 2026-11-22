# Spec — `app/dao/work_order_type.py`

> **Status:** APPROVED (2026-11-02; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-02.** **Delegated:** P1 and P2 accepted as suggested, decided by Claude under the reviewer's delegation (2026-11-02). None of these is the owner's own answer.

> **Family.** Same code as `app/dao/department.py` with the model's name changed. **Read `tests/unit/dao/department.spec.md`:** its `soft_delete` R1–R8, `restore` R1–R5, Errors and Notes apply here with `Department` read as `WorkOrderType`, and the rule numbers are the same. `restore` R6 and the rules for a name are replaced below. Base behaviour is in `tests/unit/dao/base.spec.md`.
>
> **Verified by running:** in the same scripts as the department spec, looped over this DAO, plus the constraint below through `create` and `WorkOrderTypeManager` (`rd_0.py`, `rd_1.py`, `rd_6.py` in `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\refdao\`, rolled back against `marker_test`). **Not run:** anything over HTTP; two concurrent transactions; the intended behavior of BUG-1214.

## Review
> All answered 2026-11-02.

### House-rule violations — applied automatically

- **HR-2** `create` N2, `restore` R6 — the table has a unique constraint `uq_wo_type_workspace_name` on `(workspace_id, name)` over **all** rows, soft-deleted ones included, and it compares case-sensitively. HR-2 says a soft-deleted row's name can be reused, the index is on live rows, and the compare is normalised. The manager's own check skips deleted rows, so it passes and the insert then fails: `POST /work-order-types/` for a deleted name answers 409 "This resource already exists", and no list shows the row that blocks it. The model does not declare the constraint at all; it comes from the baseline SQL. Verified through `WorkOrderTypeManager.create_work_order_type`.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** BUG-1214 (pattern `unique-index-counts-soft-deleted`). The migration replaces the constraint with a partial unique index on live rows and the normalised name, and the model declares it. Rules: `create` N2, N3, `restore` R6.

Checked and **not** a new line here: the same list as the department spec, except **HR-2**, above. No `python-only-uniqueness` bug here: the database half exists, in the wrong form.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation (2026-11-02))

### P1. "Restore a deleted work order type" is never called — ✅ keep
**Background:** as department spec P1.
**What happens today:** The method works (verified) and nothing reaches it.
**Example:** A user deletes "Repair" by mistake. No button or API call brings it back, and BUG-1214 stops them making it again.
**Rules affected:** `restore` (all)
**Answer:** intended — keep, per machine DAO Q5 precedent
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): kept, not on the dead-code list. Rules: `restore` all ✅.

### P2. A restore records nobody — ✅ intended
**Background:** as department spec P2.
**What happens today:** After a restore `deleted_at` and `deleted_by` are empty and `updated_by` keeps its old value.
**Example:** Nobody can tell who brought "Repair" back.
**Rules affected:** `restore` R2
**Answer:** intended for the DAO — per machine DAO Q8 precedent
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): rule unchanged. Rules: `restore` R2 ✅.

## Overview
`DAOWorkOrderType` is the base DAO plus the soft delete and restore of a work order type. Callers: `WorkOrderTypeManager` (`create`, `update`, `get_by_id_and_workspace`, `get_by_workspace`, `soft_delete`), and `WorkOrderManager` and `WorkOrderTemplateManager` (`get_by_id_and_workspace`). It never commits.

**Callables:** 2 specified · 2 not specified
**Externals to mock:** `utcnow` (`app.dao.work_order_type.utcnow`)
**Integration-only behavior:** none

**What differs from the department spec:**
- Table `work_order_types`, class `app.models.work_order_type.WorkOrderType`, singleton `work_order_type_dao`.
- `uq_wo_type_workspace_name`, above. **The model does not declare it**, and the database's foreign keys differ from the model: `created_by`, `updated_by`, `deleted_by` are `ON DELETE SET NULL` in the table, with no delete action on the model. Tests see the table.
- `is_active` and `is_deleted` also have database defaults (`true`, `false`).
- Two tables reference it, both `ON DELETE RESTRICT`: `work_orders`, `work_order_templates`.
- The foreign key of `deleted_by` is `work_order_types_deleted_by_fkey`.
- No `ix_work_order_types_id` index.

**Notes for the test designer:** N2 and N3 are written to the partial index. Mark them strict xfail on BUG-1214.

## Not specified
- `work_order_type_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — `tests/unit/dao/base.spec.md`, apart from N1–N3. The header's "automatically filter by workspace_id" is false for `get`, `get_multi` and `remove` (base Q4).

## Follow-ups for other reviews
> Nothing below is a rule of this DAO. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Work order type manager** (`app/managers/work_order_type_manager.py`, not yet specified) | Read, not run: `search_work_order_types` filters after `limit` (HR-5, as BUG-006, BUG-007); `_check_name_exists` scans the default 100 rows and compares with `==` (HR-2, as BUG-001, BUG-002); the schema has no trim or blank check (HR-1, as BUG-004). | reading the callers |
| FU-2 | **Work order manager, work order template manager** (`app/managers/work_order_manager.py`, `app/managers/work_order_template_manager.py`; no spec yet) | **BUG-1228, logged; the owner's answer 2026-11-02:** a soft-deleted type is refused on new work orders and templates, and existing orders keep theirs. Both managers look the type up raw and test only for `None` (`work_order_manager.py` lines 254, 430, 1555; `work_order_template_manager.py` lines 52, 86). Verified through the managers, rolled back (`ar_2.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refdao\`): `create_work_order`, `create_template` and a move by `update_work_order` all store a deleted type. Each manager's spec must carry the rules, with this DAO's lookup staying raw (HR-4 scope). | reading the callers; owner |

---

## Inherited `BaseDAO.create` on this table
- **N1.** A second live row with the same workspace and the same name raises `IntegrityError`, `.orig.pgcode == "23505"`, constraint `uq_wo_type_workspace_name`.
- **N2.** [BUG-1214] (HR-2) A name carried only by soft-deleted rows of the workspace can be used again: the new row is created. *(Today: 23505 as in N1. Verified.)*
- **N3.** [BUG-1214] (HR-2) Names that differ only in case or outer spaces collide among live rows: `"Same"` then `"same"` raises as in N1. *(Today: both stored. Verified.)*

## `restore`, in place of department spec R6
- **R6.** [BUG-1214] (HR-2) Restoring a row whose name a live type of the workspace now carries raises `IntegrityError`, nothing changed. *(Today this cannot be reached: N2 stops the second row from existing.)*

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 24–26 | keyword-only parameters | department Notes |
| 28–30 | three stamps; no `is_active`; no state check | `soft_delete` R1, R3, R4, R5, R7 |
| 31–32 | add and flush: FK check; no commit | `soft_delete` R2, R6, Errors |
| 33 | same instance | `soft_delete` R2, R8 |
| 35–37 | keyword-only parameters | department Notes |
| 39–41 | three fields cleared; no state check | `restore` R1, R2, R4, R5 |
| 42–43 | add and flush; no commit; name constraint | `restore` R3, R6 |
| 44 | same instance | `restore` R3 |
| 47 | module singleton | Not specified |
