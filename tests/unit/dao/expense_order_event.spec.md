# Spec — `app/dao/expense_order_event.py`

> **Status:** APPROVED (2026-11-01; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-01.** **Owner's answer (Q1):** bug. Deleting a not-completed order must leave a record of the order and who deleted it, so it does not vanish without trace. **Design, Claude's, not the owner's words:** the record is one row in `workspace_audit_logs`; why is in the Q1 Resolution. BUG-1193. Its rule belongs to the expense order manager spec, `tests/unit/managers/expense_order_manager.spec.md` `delete_expense_order` (its R5 changes), so no rule here carries that tag: the log itself still goes with the order (R4).

> **Family.** One of eight tiny event DAOs (`expense_order_event`, `transfer_order_event`, `work_order_event`, `project_event`, `purchase_order_event`, `sales_order_event`, `project_component_activity_event`, `payment_transaction_event`). They share one shape: one read of one parent's log, written elsewhere, with no write of its own. The shared behaviour was verified once, looped over all eight. This module matches the family, and its parent is hard-deleted (Q1).

> **Standing reviewer decisions applied here (not asked again):**
> 1. Physical row order and collation order are **not** an order: a missing `ORDER BY` is a bug, and no order recipe is called deterministic unless it ends in `id`.
> 2. Event logs are history (the owner's ledger ruling, 2026-10-30): the state of a soft-deleted parent never hides or trims them.
> 3. Raw lookups stay raw (HR-4 scope; base DAO spec). This DAO adds no soft-delete column of its own.
> 4. HR-16: a row linking to another workspace's row is invalid data, and no response shows another workspace's ids or names.
>
> **Verified by running** once for the whole family (throwaway scripts `ev_1.py` … `ev_3.py` with the harness `ev_h.py` in `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\evdao\`, each transaction rolled back against `marker_test`; nothing committed): for all eight modules the table's columns, nullability, defaults, constraints, indexes, no trigger, no table references it; the order with a timestamp tie, also after the lower-`id` tied row was updated; another parent; right parent with another workspace; a row of workspace B on a parent of A; unknown id and `0`; a positional call; an unflushed row; metadata unset and `None`; `performer`; a default `created_at`; one query, no join, no `FOR UPDATE`; 158 rows. Also run: the real delete method on a new order, after which the log is empty. **BUG-1192:** `create_pending_attachment` + `confirm_attachment` with B's order from A (`model_construct`, Cloudinary patched). Also run (`ev_4.py`): a `log_action` row with the order's id survives `delete_expense_order`. **Not run:** anything over HTTP; two concurrent transactions; the intended behavior of the bugs.

## Review
> All answered; applied 2026-11-01.

Checked and **not** a new line here: **HR-6** on `get_by_order` — ordered by `created_at` descending, then `id` descending. **HR-5, HR-8** — one query with equality filters, no `LIKE`. **HR-7** — the method does not page. **HR-4** — the table has no soft-delete column; the parent's state is standing decision 2. **HR-9, HR-10** — the DAO writes nothing and takes no lock. **HR-15** — no money is computed. **HR-1, HR-2, HR-3** — `event_type` is written by code, never typed by a user. **HR-16** — no response of this DAO is affected, see R2; the write side is BUG-1192 (FU-1).

### New questions

### Q1. Deleting an expense order erases its activity log — OWNER — 🐞 BUG-1193
**Background:** An expense order has no soft delete: `DELETE /expense-orders/{id}/` removes the row, and the database removes its activity log with it (`ON DELETE CASCADE`). The owner ruled that a ledger is history and stays complete when its parent is soft-deleted; that ruling did not cover a hard delete. A completed order is refused, and BUG-742 will also refuse one with a linked invoice. The approved expense order manager spec says this in passing (`delete_expense_order` R5: "the log is deleted with the order") and was not asked about it.
**What happens today:** Any order that is not completed can be deleted, approved or not, and then nothing shows it ever existed: every event goes, and no "deleted" event is written anywhere. Money: until BUG-742 is fixed, an order with a linked invoice can be deleted the same way. (Verified on a new order; the approved case is read from the code, which has no approval check.)
**Example:** Rahim creates expense order EO-41, two people approve it, and Rahim deletes it on Friday. On Monday `GET /expense-orders/<id>/events/` answers 404 and the database holds no row saying who approved or deleted it.
**Rules affected:** `get_by_order` R4
**Suggested answer:** `intended — once BUG-742 is fixed, a hard delete only reaches an order with no completion and no invoice, and the cascade on the foreign key is deliberate`. Alternative: `bug — an order that has been approved keeps its log` (a soft-delete column on the order, or a `void` instead of a delete), which also changes `delete_expense_order` R5 and the order lists.
**Answer:** bug — deleting a not-completed order must leave a record of the order and who deleted it, so it does not vanish without trace (owner, 2026-11-01)
**Resolution:** BUG-1193 (pattern `hard-delete-leaves-no-trace`). The delete writes one `workspace_audit_logs` row, through the existing `workspace_audit_log_dao.log_action`, in the same transaction: `workspace_id`; `user_id` = the deleter; `action` = `expense_order_deleted`; `resource_type` = `expense_order`; `resource_id` = the order id; `metadata` = `{"number": expense_number, "total_amount": "<2 decimals as text>", "created_by": <id>, "created_at": "<ISO>"}`. A refused delete writes nothing. **Design, Claude's:** this table is the smallest existing place: it has no foreign key to the order, so the row survives the delete (verified with an expense order); `log_action` exists; its `resource_type` comment already names `order`; no new table or column is needed. `financial_audit_logs` was not chosen because transfer orders have no money and one table should serve all three. **Needs:** `ExpenseOrderManager.delete_expense_order` gains a required `user_id`, and the `DELETE` endpoint, which has no current user today, passes it. **Limits of this design:** the order's events are not copied; no endpoint reads `workspace_audit_logs` today, so the record is in the database and no page shows it; `user_id` becomes `NULL` if that profile is ever removed. Rules: the expense order manager spec, `tests/unit/managers/expense_order_manager.spec.md` `delete_expense_order` (its R5 changes). `get_by_order` R4 here is unchanged.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1a | **the expense order manager spec, `tests/unit/managers/expense_order_manager.spec.md` `delete_expense_order` (its R5 changes)** | **BUG-1193, logged (Q1, owner):** the rule and the tag belong there: the row of the Q1 Resolution is written; a refused delete writes none; `user_id` is required. Design Claude's. | Q1 |
| FU-1 | **`ExpenseOrderManager.log_event`** (`app/managers/expense_order_manager.py`) | **BUG-1192 (HR-16), logged:** it stores any id under the caller's workspace. Signing and confirming an attachment on another workspace's expense order wrote `attachment_added` with the caller's `workspace_id` (verified at manager level). The row shows nowhere: the caller gets 404 and the owner of the expense order is filtered out by R2. The manager's spec must carry the rule and the tag: 404 `Expense order with ID <id> not found`, nothing written. | BUG-1091 note "other types not checked" |
| FU-2 | **`ExpenseOrderManager.list_events`** | Reads one profile per event with a performer, the pattern of BUG-1141 (read, not run). This list has no paging, so a long log costs one read per entry. Not logged here: it is the manager's. | BUG-1141 |
| FU-3 | **Expense order endpoint** (`GET` events) | The endpoint validates stored metadata with its schema (`ExpenseOrderEventMetadata`). Whether any writer stores a value of the wrong type, which would make the whole log a 500 as in machine FU-2 (b), was not checked here. | machine FU-2 |

## Overview
`ExpenseOrderEventDAO` reads `expense_order_events`, the activity log of a expense order: one row per thing that happened to it. It has one read: one expense order's log, newest first. All writes go through `ExpenseOrderManager.log_event`, not this DAO; attachments reach it too (`AttachmentManager._log_attachment_entity_events`). It is meant to protect workspace isolation. It never writes, never commits and takes no lock.

**Callables:** 1 specified · 2 not specified
**Externals to mock:** none. No method reads the clock.
**Integration-only behavior:** none.

**Model facts (table `expense_order_events`, class `app.models.expense_order_event.ExpenseOrderEvent`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `expense_order_id` | Integer NOT NULL, FK `expense_orders.id` ON DELETE CASCADE | — |
| `event_type` | String(50) NOT NULL, no check constraint | — |
| `description` | Text NOT NULL | — |
| `metadata` (attribute `metadata_json`) | generic `JSON` (Postgres `json`), nullable | `NULL` |
| `performed_by` | Integer nullable, FK `profiles.id` ON DELETE SET NULL | `NULL` |
| `created_at` | `timestamp without time zone` NOT NULL, naive UTC by convention | Python default `utcnow`, no database default |

- No soft-delete column, no `updated_at`. Indexes: primary key, `ix_expense_order_events_expense_order_id`, `ix_expense_order_events_workspace_id`. No unique or check constraint, no trigger; no table references this one.
- "Append-only" is a convention: nothing in the database enforces it, and no application code updates or deletes these rows.
- `expense_order_id` and `workspace_id` of a row are independent: the database does not require the expense order to belong to the row's workspace.
- Metadata set to Python `None` explicitly is stored as JSON `null`; left unset it is SQL `NULL`. Both read back as `None`.
- Relationship: `performer` (lazy, `Profile`).

**Notes for the test designer:**
- Use the module singleton `expense_order_event_dao` (`from app.dao.expense_order_event import expense_order_event_dao`). Every parameter after `db` is keyword-only (a positional call raises `TypeError`).
- Workspaces and profiles from `tests/unit/factories.py`. Parents built directly (add + flush): `ExpenseOrder(workspace_id, expense_number, expense_category, created_by)`. Events: `ExpenseOrderEvent(workspace_id, expense_order_id, event_type, description, created_at, metadata_json)`. The session runs with `autoflush=False`: flush before calling the DAO (base spec `get` R5).
- Always give `created_at` explicitly, with distinct values unless the case is about a tie. Column defaults cannot be frozen by patching `utcnow`.
- Test the shape once here; the base behaviour is in `tests/unit/dao/base.spec.md` and is not repeated.

## Not specified
- `expense_order_event_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — not overridden and with **no caller on this DAO**: the row is added directly by the writer. The base spec covers them.

The checklist (`docs/testing/unit-test-checklist-by-layer.md`) does not mark `get_by_order` as possibly unused.

---

## `ExpenseOrderEventDAO.get_by_order(db, *, expense_order_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ExpenseOrderManager.list_events` ← `GET /expense-orders/{id}/events/`)

**Purpose:** One expense order's activity log, newest first.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `expense_order_id` | int | equality on the row's `expense_order_id`; not validated |
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** a `list` of `ExpenseOrderEvent` instances (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `expense_order_id` and that `workspace_id`, of every event type. Rows of another expense order are never returned.
- **R2.** Workspace isolation follows the row: a call with the right expense order id and another workspace returns `[]`. Only the row's own `workspace_id` is compared, not the expense order's. A row with `workspace_id` = B on a expense order of workspace A is returned for B and not for A. (HR-16: that row is invalid data, and it cannot reach a response: the caller answers 404 for a expense order of another workspace before this method runs. The write side is BUG-1192.)
- **R3.** An unknown expense order id, `expense_order_id=0`, an unknown workspace, or a expense order with no events returns `[]`.
- **R4.** The expense order has no soft-delete column. A hard delete (`ExpenseOrderManager.delete_expense_order`) removes its rows too, through `ON DELETE CASCADE`: the call then returns `[]`. ✅ (Q1: the trace of the deleted order is BUG-1193, a rule of the manager, FU-1a.)
- **R5.** Rows are ordered by `created_at` descending, then `id` descending. Given 4 Mar, 5 Mar and two rows on 6 Mar, the result is the higher `id` of 6 Mar, the lower `id` of 6 Mar, 5 Mar, 4 Mar; updating the lower tied row does not change that.
- **R6.** Every matching row is returned: no `skip`, no `limit`, no cap. Given 158 rows, 158.
- **R7.** Rows come back as stored: `metadata_json` is the stored value, `None` for both SQL `NULL` and JSON `null`, and `performer` gives the profile, or `None` when `performed_by` is `None`. The call changes nothing.

**Errors:** none.

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 11–14 | keyword-only parameters | Notes for the test designer |
| 16–19 | parent AND workspace; no join to the parent | `get_by_order` R1, R2, R3, R4 |
| 20 | `created_at` desc, `id` desc | `get_by_order` R5 |
| 21 | no paging: all rows, as stored | `get_by_order` R6, R7 |
| 25 | module singleton | Not specified |
