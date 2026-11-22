# Spec — `app/dao/payment_transaction_event.py`

> **Status:** APPROVED (2026-11-01; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-01.** **Delegated:** Q1 intended, decided by Claude under the reviewer's delegation (2026-11-01). That is not the owner's own answer. BUG-1190 and BUG-1191 stand from the house rules.

> **Family.** One of eight tiny event DAOs (`expense_order_event`, `transfer_order_event`, `work_order_event`, `project_event`, `purchase_order_event`, `sales_order_event`, `project_component_activity_event`, `payment_transaction_event`). They share one shape: one read of one parent's log, written elsewhere, with no write of its own. The shared behaviour was verified once, looped over all eight. **This module differs from the family in four ways:** oldest first instead of newest first, no `id` tie-break, no `workspace_id` parameter, and the column is called `metadata_json`.

> **Standing reviewer decisions applied here (not asked again):**
> 1. Physical row order and collation order are **not** an order: a missing `ORDER BY` is a bug, and no order recipe is called deterministic unless it ends in `id`.
> 2. Event logs are history (the owner's ledger ruling, 2026-10-30): the state of a soft-deleted parent never hides or trims them.
> 3. Raw lookups stay raw (HR-4 scope; base DAO spec). This DAO adds no soft-delete column of its own.
> 4. HR-16: a row linking to another workspace's row is invalid data, and no response shows another workspace's ids or names.
>
> **Verified by running** once for the whole family (throwaway scripts `ev_1.py` … `ev_3.py` with the harness `ev_h.py` in `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\evdao\`, each transaction rolled back against `marker_test`; nothing committed): for all eight modules the table's columns, nullability, defaults, constraints, indexes, no trigger, no table references it; the order with a timestamp tie, also after the lower-`id` tied row was updated; another parent; right parent with another workspace; a row of workspace B on a parent of A; unknown id and `0`; a positional call; an unflushed row; metadata unset and `None`; `performer`; a default `created_at`; one query, no join, no `FOR UPDATE`; 158 rows. Also run: **BUG-1190:** two rows with one timestamp changed places after the lower-`id` row was updated; **BUG-1191:** a row of workspace A on a transaction of workspace B came back in B's `PaymentTransactionService.get_transaction_by_tran_id`, its metadata included; `_log_event` through a real call. **Not run:** anything over HTTP; two concurrent transactions; the intended behavior of the bugs.

## Review
> All answered; applied 2026-11-01.

### House-rule violations — applied automatically

- **HR-6** `get_by_payment_transaction` R6 — ordered by `created_at` alone: rows with one timestamp have no order, and physical row order is not an order. Verified: the two tied rows changed places after an update. Same root cause as BUG-638 and BUG-640. Intended: `created_at` ascending, then `id` ascending.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1190 (pattern `tied-timestamp-no-tiebreak`).
- **HR-16** `get_by_payment_transaction` R2 — the only DAO of the family with no `workspace_id`: a row of another workspace on a transaction shows in that transaction's detail response, metadata included. The write side is sound: `_log_event` copies `txn.workspace_id`, so only invalid data gets there, and attachments do not reach this log. Intended: required `workspace_id`, row filter.
**Answer:** bug — per HR-16 (house rule)
**Resolution:** BUG-1191 (pattern `missing-workspace-scope`, same root cause as BUG-035).

Checked and **not** a new line here: **HR-6** on R5 — the direction is Q1; the tie is BUG-1190. **HR-5, HR-8** — one query with equality filters, no `LIKE`. **HR-7** — the method does not page. **HR-4** — the table has no soft-delete column; the parent's state is standing decision 2. **HR-9, HR-10** — the DAO writes nothing and takes no lock. **HR-15** — no money is computed. **HR-1, HR-2, HR-3** — `event_type` is written by code, never typed by a user.

### New questions

### Q1. The payment log reads oldest first; every other log reads newest first — ✅ intended
**Background:** Every sibling log (orders, projects, components, machines) lists the newest event first. A payment's log is shown as a timeline of steps on the billing page, which draws the list as it arrives (`BillingTrialPage.tsx`, twice, no sorting).
**What happens today:** `GET /payments/{tran_id}/` lists events oldest first: `initiated`, then the callback and validation steps.
**Example:** A payment has `initiated` at 10:00, `ipn_received` at 10:02 and `validated_success` at 10:02. The billing page shows them top to bottom in that order, while a purchase order's log shows its newest entry at the top.
**Rules affected:** `get_by_payment_transaction` R5
**Suggested answer:** `intended — a payment reads as a sequence of steps, and the page is built for that order`. Not an OWNER item: it changes no figure and no status. Alternative: `bug — newest first like the other logs`, which must also change the frontend.
**Answer:** intended — a payment reads as a sequence of steps, and the page is built for that order
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-01): rule unchanged. Rules: `get_by_payment_transaction` R5 ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Payment service** (`PaymentTransactionService.get_transaction_by_tran_id`) | Must pass `workspace_id` once BUG-1191 is fixed. `PaymentTransactionEventResponse` has no `workspace_id` field, so only the row's own content shows. | BUG-1191 |

## Overview
`PaymentTransactionEventDAO` reads `payment_transaction_events`, the audit trail of a payment transaction: one row per gateway step. It has one read: one transaction's events, oldest first. Writes go through `PaymentTransactionManager._log_event`, through the inherited `create`. Caller: `PaymentTransactionService.get_transaction_by_tran_id` ← `GET /payments/{tran_id}/`, after the transaction was found in the workspace. It never commits and takes no lock. Unlike the rest of the family, nothing in the file says that queries must filter by workspace.

**Callables:** 1 specified · 2 not specified
**Externals to mock:** none. No method reads the clock.
**Integration-only behavior:** none.

**Model facts (table `payment_transaction_events`, class `app.models.payment_transaction_event.PaymentTransactionEvent`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `payment_transaction_id` | Integer NOT NULL, FK `payment_transactions.id` ON DELETE CASCADE | — |
| `event_type` | String(50) NOT NULL, no check constraint | — |
| `description` | Text NOT NULL | — |
| `metadata_json` | generic `JSON` (Postgres `json`), nullable | `NULL` |
| `performed_by` | Integer nullable, FK `profiles.id` ON DELETE SET NULL | `NULL` |
| `created_at` | `timestamp without time zone` NOT NULL, naive UTC by convention | Python default `utcnow`, plus a database default `now()` |

- No soft-delete column, no `updated_at`. Indexes: primary key, `ix_payment_transaction_events_payment_transaction_id`, `ix_payment_transaction_events_workspace_id`. No unique or check constraint, no trigger; no table references this one.
- "Append-only" is a convention: nothing in the database enforces it, and no application code updates or deletes these rows.
- `payment_transaction_id` and `workspace_id` of a row are independent: the database does not require the payment transaction to belong to the row's workspace.
- Metadata set to Python `None` explicitly is stored as JSON `null`; left unset it is SQL `NULL`. Both read back as `None`.
- Relationship: `performer` (lazy, `Profile`). Also `payment_transaction`, with the backref `PaymentTransaction.events`, which no code reads.
- The database default `now()` only fires for a raw `INSERT` without `created_at`, which no application code does; it gives the server's local time, not UTC (verified: 17:58 when UTC was 21:58).

**Notes for the test designer:**
- Use the module singleton `payment_transaction_event_dao` (`from app.dao.payment_transaction_event import payment_transaction_event_dao`). Every parameter after `db` is keyword-only (a positional call raises `TypeError`).
- Workspaces and profiles from `tests/unit/factories.py`. Parents built directly (add + flush): `PaymentTransaction(workspace_id, tran_id, amount, currency)`. Events: `PaymentTransactionEvent(workspace_id, payment_transaction_id, event_type, description, created_at, metadata_json)`. The session runs with `autoflush=False`: flush before calling the DAO (base spec `get` R5).
- Always give `created_at` explicitly, with distinct values unless the case is about a tie. Column defaults cannot be frozen by patching `utcnow`.
- Test the shape once here; the base behaviour is in `tests/unit/dao/base.spec.md` and is not repeated.
- **BUG-1191:** today's signature has only `payment_transaction_id`, so R1 and R3–R8 are written to that call. The R2 cases are xfail until the fix; the fix makes `workspace_id` required, and the other cases then gain the argument.
- **BUG-1190:** two rows with one `created_at`, then an `UPDATE` of the **lower**-`id` row's `description`, flushed, then `db.expire_all()`. Today that gave the higher `id` first (verified), but it rests on physical row order, which is not an order. Write the case to the intended result and mark it **non-strict** xfail (`strict=False`).

## Not specified
- `payment_transaction_event_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — not overridden. `create` is the only one called on this DAO (by `_log_event`, as a dict; base spec `create` R1, and the payment manager spec `_log_event` R1). The others have no caller.

The checklist (`docs/testing/unit-test-checklist-by-layer.md`) does not mark `get_by_payment_transaction` as possibly unused.

---

## `PaymentTransactionEventDAO.get_by_payment_transaction(db, *, payment_transaction_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `PaymentTransactionService.get_transaction_by_tran_id` ← `GET /payments/{tran_id}/`, after the transaction was found in the workspace)

**Purpose:** One transaction's event trail, oldest first.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `payment_transaction_id` | int | equality on the row's `payment_transaction_id`; not validated |
| `workspace_id` | int, required | [BUG-1191] equality on the row's `workspace_id`. *(Today: no such parameter.)* |

**Returns:** a `list` of `PaymentTransactionEvent` instances (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `payment_transaction_id`, of every event type. Rows of another transaction are never returned.
- **R2.** [BUG-1191] (HR-16) The method takes a required `workspace_id` and returns only rows with that `workspace_id`: a row of workspace A on a transaction of workspace B is not returned for B, and a call with another workspace returns `[]`. *(requires new parameter `workspace_id`; `PaymentTransactionService.get_transaction_by_tran_id` must pass it.)* *(Today: there is no such parameter and no filter. Verified: that row came back in B's `GET /payments/{tran_id}/` result, metadata included.)*
- **R3.** An unknown transaction id, `payment_transaction_id=0`, or a transaction with no events returns `[]`.
- **R4.** The transaction has no soft-delete column and the code has no way to delete one, so nothing hides or trims its rows (standing decision 2).
- **R5.** ✅ (Q1) Rows are ordered by `created_at` **ascending**, oldest first. Given 4 Mar, 5 Mar and 6 Mar, the result is 4 Mar, 5 Mar, 6 Mar.
- **R6.** [BUG-1190] (HR-6) On a `created_at` tie, rows are ordered by `id` ascending. *(Today: no ordering is requested among tied rows. Verified: two rows with one timestamp came back lower `id` first, and higher `id` first after the lower row was updated.)*
- **R7.** Every matching row is returned: no `skip`, no `limit`, no cap. Given 158 rows, 158.
- **R8.** Rows come back as stored: `metadata_json` is the stored value, `None` for both SQL `NULL` and JSON `null`, and `performer` gives the profile, or `None` when `performed_by` is `None`. The call changes nothing.

**Errors:** none.

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 10–13 | keyword-only parameter; no `workspace_id` (BUG-1191) | `get_by_payment_transaction` R2; Notes for the test designer |
| 15 | transaction id only; no join to the parent | `get_by_payment_transaction` R1, R2, R3, R4 |
| 16 | `created_at` ascending; no `id` (BUG-1190) | `get_by_payment_transaction` R5, R6 |
| 17 | no paging: all rows, as stored | `get_by_payment_transaction` R7, R8 |
| 21 | module singleton | Not specified |
