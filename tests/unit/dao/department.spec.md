# Spec — `app/dao/department.py`

> **Status:** APPROVED (2026-11-02; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-02.** **Delegated:** P1, P2 and P3 accepted as suggested, decided by Claude under the reviewer's delegation (2026-11-02). None of these is the owner's own answer.

> **Family.** `department`, `delivery_method` and `work_order_type` have the same two methods on the same shape of table. The rules are written here once. `tests/unit/dao/delivery_method.spec.md` and `tests/unit/dao/work_order_type.spec.md` point here and list only what differs. Everything inherited is in `tests/unit/dao/base.spec.md`, which uses this DAO as its vehicle, and is not restated.
>
> **Standing decisions applied here (not asked again):** raw lookups stay raw (HR-4 scope). Things of a soft-deleted parent are hidden by the parent's state: departments have no child rows, so this does not arise. No read of its own here, so a missing `ORDER BY` cannot arise either.
>
> **Verified by running** (scripts `rd_h.py`, `rd_0.py`, `rd_1.py`, `rd_6.py` in `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\refdao\`, each transaction rolled back against `marker_test`; nothing committed; looped over all three DAOs): the table's columns, defaults, constraints, indexes, no trigger, no table references it; every field `soft_delete` and `restore` write and do not write; the patched clock; a row with `is_active = False`; deleting twice; restoring a live row; an unknown profile, `None`, a row of another workspace; savepoint rollback; the raw base reads after a delete; `deleted_at` against `created_at` under `Asia/Dhaka`; restoring next to a live row of the same name; creating a name held by a deleted row. **Not run:** anything over HTTP; two concurrent transactions.

## Review
> All answered 2026-11-02.

| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | "Restore a deleted department" works and nothing calls it | keep | Claude, delegated |
| P2 | A restore records nobody | intended for the DAO | Claude, delegated |
| P3 | A restore does not look whether the name was taken in the meantime | intended for the DAO; the database half is BUG-003 | Claude, delegated |

### House-rule violations — applied automatically

None new. **HR-2** (database half) reaches `restore` R6, and that is **BUG-003** (`python-only-uniqueness`), already logged: the same partial unique index is the fix, no new ID.

Checked and **not** a new line here: **HR-4** — both methods take the row they are given; the raw reads are the base's, and `get_department` is BUG-005. **HR-5, HR-6, HR-7, HR-8** — no query here. **HR-9** — neither method writes `updated_by`. **HR-10** — plain soft delete and restore need no lock. **HR-15** — no money. **HR-16** — no link written; `deleted_by` is a profile, and the caller passes the current user. **HR-1, HR-2, HR-3** — names are the manager's and the schema's (BUG-001 … BUG-004). `deleted_at` already comes from `utcnow()`, so BUG-1102 does not apply; `created_at` and `updated_at` follow the database clock, which is FU-3 of `tests/unit/dao/machine_maintenance_log.spec.md`.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation (2026-11-02))

### P1. "Restore a deleted department" is never called — ✅ keep
**Background:** `restore` brings a soft-deleted department back. No endpoint, service or manager method calls it. For machines the owner answered "keep restore" (machine DAO Q5, 2026-10-10), because a delete must be undoable once the feature exists; factories, sections and maintenance logs followed.
**What happens today:** The method works (verified) and nothing reaches it.
**Example:** A user deletes "Sales" by mistake. No button or API call brings it back.
**Rules affected:** `restore` (all)
**Answer:** intended — keep, per machine DAO Q5 precedent: specified in full below
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): kept, not on the dead-code list. Rules: `restore` all ✅.

### P2. A restore records nobody — ✅ intended
**Background:** `soft_delete` stamps who and when. `restore` has no "who" argument.
**What happens today:** After a restore `deleted_at` and `deleted_by` are empty and `updated_by` keeps its old value.
**Example:** Rahim deletes "Sales" on Monday, Karim restores it on Tuesday once the feature exists. The row shows neither.
**Rules affected:** `restore` R2
**Answer:** intended for the DAO — per machine DAO Q8 precedent: the manager method that will call `restore` records the user
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): rule unchanged. Rules: `restore` R2 ✅.

### P3. A restore does not look at the name — ✅ intended
**Background:** Names are unique among live departments, checked in the manager only (BUG-001, BUG-002, BUG-003). A deleted name can be reused (HR-2).
**What happens today:** Deleted "Dup", a new live "Dup", then `restore` of the old row: two live departments named "Dup", no error (verified).
**Example:** "Sales" is deleted and a new "Sales" is made. Once restore exists, restoring the old one gives two.
**Rules affected:** `restore` R6
**Answer:** intended for the DAO — per factory DAO P3 precedent: the future "restore" feature refuses it; the database half is BUG-003
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): the DAO adds no check, and `restore` R6 stays tagged BUG-003 for the index.

## Overview
`DAODepartment` is the base DAO plus the soft delete and restore of a department, a workspace's list of departments, also used as expense cost centers. Callers: `DepartmentManager` (`create`, `update`, `get_by_id_and_workspace`, `get_by_workspace`, `soft_delete`) and `ExpenseOrderManager` (`get_by_id_and_workspace`, to check a cost center). It never commits.

**Callables:** 2 specified · 2 not specified
**Externals to mock:** `utcnow` (`app.dao.department.utcnow`)
**Integration-only behavior:** none

**Model facts (table `departments`, class `app.models.department.Department`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `name` | String NOT NULL, no unique constraint | — |
| `created_at` | `timestamp without time zone` NOT NULL | database `now()` |
| `created_by`, `updated_by`, `deleted_by` | Integer nullable, FK `profiles.id` (no delete action; `departments_deleted_by_fkey` for the last) | `NULL` |
| `updated_at` | `timestamp without time zone` nullable | `onupdate` database `now()` |
| `is_active`, `is_deleted` | Boolean NOT NULL | Python only: `True`, `False` |
| `deleted_at` | `timestamp without time zone` nullable | `NULL` |

No table references `departments` (`cost_center_id` is a plain integer). No check constraint, no trigger.

**Notes for the test designer:**
- Use the module singleton `department_dao`. Every parameter after `db` is keyword-only.
- Workspaces and profiles from `tests/unit/factories.py`. Build rows with `Department(workspace_id=…, name=…)`, add and flush, and `db.refresh` after a write to read `updated_at`.
- `now()` is the transaction's start, so `updated_at` equals `created_at` inside one test: assert "not `None`", as the base spec says.
- Wrap a call expected to raise `IntegrityError` in `with db.begin_nested():` inside `pytest.raises(...)`.

## Not specified
- `department_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — not overridden; `tests/unit/dao/base.spec.md`. The file's header says they "automatically filter by workspace_id": `get`, `get_multi` and `remove` do not (base Q4). The class docstring lists `create_with_workspace()`, which does not exist. Nothing depends on either sentence.

The checklist (`docs/testing/unit-test-checklist-by-layer.md`) marks neither method possibly unused; `get_active_departments` was removed as dead code.

---

## `DAODepartment.soft_delete(db, *, db_obj, deleted_by)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `DepartmentManager.delete_department`, which has already refused a deleted row)

**Purpose:** Mark a department deleted, keeping the row.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `db_obj` | `Department` | the row; not checked in any way |
| `deleted_by` | int | stored in `deleted_by`; only the foreign key checks it |

**Returns:** the same instance, flushed, not committed.

**Rules:**
- **R1.** `is_deleted` becomes `True`, `deleted_at` the value of `utcnow()` (naive UTC, from Python, not the database clock), `deleted_by` the given id.
- **R2.** The same instance is returned; rolling back removes all three stamps.
- **R3.** Nothing else changes: `name`, `is_active`, `created_at`, `created_by`, `updated_by`. A row with `is_active = False` stays so, a row with `True` stays `True`. `updated_at`, `NULL` before, becomes non-null.
- **R4.** An already deleted row is deleted again with no error: `deleted_at` and `deleted_by` are overwritten by the second call.
- **R5.** No check of workspace: a row of any workspace is deleted, and `deleted_by` can be a profile with no link to it.
- **R6.** An unknown `deleted_by` makes the flush raise (see Errors).
- **R7.** `deleted_by=None` is stored: the row is deleted with `deleted_at` set and `deleted_by` `NULL`.
- **R8.** After the call the raw base reads still return the row: `get`, `get_by_id_and_workspace`, `get_by_workspace` (HR-4 scope).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `deleted_by` is no profile | `sqlalchemy.exc.IntegrityError`, `.orig.pgcode == "23503"` | Postgres, constraint `departments_deleted_by_fkey` |

**Side effects:** one row updated and flushed; no commit.

---

## `DAODepartment.restore(db, *, db_obj)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public, no caller (P1)

**Purpose:** Bring a soft-deleted department back.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `db_obj` | `Department` | the row; not checked in any way |

**Returns:** the same instance, flushed, not committed.

**Rules:**
- **R1.** `is_deleted` becomes `False`, `deleted_at` and `deleted_by` become `NULL`.
- **R2.** ✅ (P2) Nothing else changes: `name`, `is_active`, `created_by`, `updated_by`. `updated_at` becomes non-null, because the row changed. No trace of the delete or the restore stays on the row.
- **R3.** The same instance is returned; rolling back brings the deleted state back.
- **R4.** A live row is accepted with no error and no change: `updated_at` stays `NULL`.
- **R5.** No check of workspace: a row of any workspace is restored.
- **R6.** [BUG-003] (HR-2) Restoring a row whose name a live department of the workspace now carries makes the flush raise `IntegrityError`, nothing changed. *(Today: no error; two live departments with one name. Verified.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| R6, once BUG-003's index exists | `sqlalchemy.exc.IntegrityError` | Postgres |

**Side effects:** one row updated and flushed; no commit.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 25–27 | keyword-only parameters | Notes for the test designer |
| 39–41 | three stamps; no `is_active`; no state check | `soft_delete` R1, R3, R4, R5, R7 |
| 42–43 | add and flush: FK check; no commit | `soft_delete` R2, R6, Errors |
| 44 | same instance | `soft_delete` R2, R8 |
| 46–48 | keyword-only parameters | Notes for the test designer |
| 59–61 | three fields cleared; no state check | `restore` R1, R2, R4, R5 |
| 62–63 | add and flush; no commit; no name check | `restore` R3, R6 |
| 64 | same instance | `restore` R3 |
| 67 | module singleton | Not specified |
