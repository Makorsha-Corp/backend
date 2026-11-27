# Spec — `app/dao/delivery_method.py`

> **Status:** APPROVED (2026-11-02; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-02.** **Delegated:** P1 and P2 accepted as suggested, decided by Claude under the reviewer's delegation (2026-11-02). None of these is the owner's own answer.

> **Family.** Same code as `app/dao/department.py` with the model's name changed. **Read `tests/unit/dao/department.spec.md`:** its `soft_delete` R1–R8, `restore` R1–R6, Errors and Notes apply here with `Department` read as `DeliveryMethod`, and the rule numbers are the same. Only what differs is below. Base behaviour is in `tests/unit/dao/base.spec.md`.
>
> **Verified by running:** in the same scripts as the department spec, looped over this DAO (`rd_1.py`, `rd_6.py` in `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\refdao\`, rolled back against `marker_test`). **Not run:** anything over HTTP; two concurrent transactions.

## Review
> All answered 2026-11-02.

### House-rule violations — applied automatically

- **HR-2** (fourth bullet: enforce in the database too) `restore` R6 — `delivery_methods` has no unique index, so a restore, or two concurrent creates, leaves two live methods of one name (verified for the restore). Intended: partial unique index on live rows, normalised name; a violation at the API is 409.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** BUG-1219 (pattern `python-only-uniqueness`). Rules: `restore` R6 here, with this tag in place of BUG-003.

Checked and **not** a new line here: the same list as the department spec. The standing "hidden by the parent" decision does not reach deliveries: a delivery names its method, it does not belong to it, so `soft_delete` leaves them alone and `ON DELETE SET NULL` does not fire. Choosing a deleted method for a delivery is BUG-730. `delivery_method_manager` has the rest of the department bugs' shape: FU-1.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation (2026-11-02))

### P1. "Restore a deleted delivery method" is never called — ✅ keep
**Background:** as department spec P1.
**What happens today:** The method works (verified) and nothing reaches it.
**Example:** A user deletes "Courier" by mistake. No button or API call brings it back.
**Rules affected:** `restore` (all)
**Answer:** intended — keep, per machine DAO Q5 precedent
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): kept, not on the dead-code list. Rules: `restore` all ✅.

### P2. A restore records nobody — ✅ intended
**Background:** as department spec P2.
**What happens today:** After a restore `deleted_at` and `deleted_by` are empty and `updated_by` keeps its old value.
**Example:** Nobody can tell who brought "Courier" back.
**Rules affected:** `restore` R2
**Answer:** intended for the DAO — per machine DAO Q8 precedent
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): rule unchanged. Rules: `restore` R2 ✅.

## Overview
`DAODeliveryMethod` is the base DAO plus the soft delete and restore of a delivery method (Courier, Pickup, …). Callers: `DeliveryMethodManager` (`create`, `update`, `get_by_id_and_workspace`, `get_by_workspace`, `soft_delete`). It never commits.

**Callables:** 2 specified · 2 not specified
**Externals to mock:** `utcnow` (`app.dao.delivery_method.utcnow`)
**Integration-only behavior:** none

**What differs from the department spec:**
- Table `delivery_methods`, class `app.models.delivery_method.DeliveryMethod`, singleton `delivery_method_dao`.
- `is_active` and `is_deleted` also have database defaults (`true`, `false`).
- One table references it: `sales_deliveries.delivery_method_id`, `ON DELETE SET NULL`.
- The foreign key of `deleted_by` is `delivery_methods_deleted_by_fkey`, no delete action.
- No `ix_delivery_methods_id` index; the primary key's index serves.

## Not specified
- `delivery_method_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — `tests/unit/dao/base.spec.md`. The header's "automatically filter by workspace_id" is false for `get`, `get_multi` and `remove` (base Q4).

## Follow-ups for other reviews
> Nothing below is a rule of this DAO. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Delivery method manager** (`app/managers/delivery_method_manager.py`, not yet specified) | Read, not run: `search_delivery_methods` drops deleted rows and applies `search` in Python after `limit` (HR-5, as BUG-006, BUG-007); `_check_name_exists` scans the default 100 rows and compares with `==` (HR-2, as BUG-001, BUG-002); `DeliveryMethodCreate` has no trim or blank check (HR-1, as BUG-004); deleted rows reachable by id (HR-4 at the manager). `delete` looks at no delivery. | reading the callers |

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
| 42–43 | add and flush; no commit; no name check | `restore` R3, R6 |
| 44 | same instance | `restore` R3 |
| 47 | module singleton | Not specified |
