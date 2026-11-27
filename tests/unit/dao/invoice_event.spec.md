# Spec — `app/dao/invoice_event.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-03.** No owner answer in this round. **Delegated:** P1 decided by Claude under the reviewer's delegation (2026-11-03); it is not the owner's own answer. The house-rule line reuses BUG-638, decided in the approved account invoice manager spec (Q15).

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Event logs are history (the owner's ledger ruling, 2026-10-30): the state of the invoice or the performer never hides or trims them. Raw lookups stay raw. HR-16: a row linking to another workspace's row is invalid data.
>
> **Verified by running** (throwaway scripts `v_inv.py`, `schema.py` with the harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\acctdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints and indexes; `create_event` with and without `performed_by` / `metadata` (dict, list), the stored form of `metadata=None` (JSON `null`, not SQL `NULL`), `created_at` against the database's UTC clock, an empty description, a 51-character `event_type` (22001), `description=None` (23502), unknown invoice / performer / workspace (23503), a `Decimal` in `metadata` (`StatementError` wrapping `TypeError`); a row stored under another workspace; `get_by_invoice` keys, newest first, performer name, another invoice, another workspace, an unknown invoice, a performer deleted (`performed_by` becomes `NULL`); three events of one `created_at` under a forced sequential scan, `42368, 42369, 42370` → `42369, 42370, 42368` after an update; of 30 events written in a row only 11 distinct `created_at` values; deleting the invoice deletes its events; a positional call (`TypeError`). **Read, not run:** `AccountInvoiceManager._log_event` / `get_events` and the other callers of `_log_event`. **Not run:** anything over HTTP.

## Review
> All answered; applied 2026-11-03.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | The history of an invoice is read whatever the invoice's state, and a person's name is shown as long as their profile exists | intended — logs are history | Claude, delegated |

Decided by a house rule: events of one time come back in no fixed order (BUG-638, existing).

### House-rule violations — applied automatically

- **HR-6** `get_by_invoice` R3 — ordered by `created_at` newest first, nothing after it. `created_at` comes from a coarse clock (30 events in a row: 11 distinct times); verified three events of one time reordered after an update. Intended: `created_at` newest first, then `id` descending.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-638 (existing; account invoice manager Q15, which ruled exactly this order for `get_events`). Its Module cell now names this file as the line to fix. Rules: `get_by_invoice` R3.

Checked and **not** a new line here: **HR-4** — no soft-delete column; invoices are voided or (drafts) hard-deleted, P1. **HR-5, HR-7, HR-8** — no paging, no `LIKE`; the whole history is returned (no cap). **HR-9, HR-10** — append-only; a log row needs no lock. **HR-15** — no money is computed; callers put amounts in `metadata` as strings. **HR-16** — `get_by_invoice` filters on the event's own `workspace_id`; `create_event` stores what the caller gives, and `_log_event` passes the invoice's own workspace. **HR-1–HR-3** — `event_type` and `description` are written by code.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-03)

### P1. An invoice's history is read whatever its state — ✅ intended
**Background:** Invoices are voided (terminal) or, as drafts, hard-deleted; a hard delete deletes the events (cascade). The only reader (`AccountInvoiceManager.get_events`) answers 404 first for an invoice not in the workspace. Profiles are referenced with `ON DELETE SET NULL`.
**What happens today:** Events of a voided invoice are returned. The performer's name comes from the profile at read time; if the profile row is deleted, `performed_by` and `performed_by_name` are `None`. (Verified.)
**Example:** A voided invoice still shows "Invoice created — Rahim", "Payment recorded — Karim", "Invoice voided — Rahim".
**Rules affected:** `get_by_invoice` R4, R5
**Answer:** intended — per the ledger ruling: logs are history; nothing is hidden by the invoice's state.
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): rules unchanged (R4 ✅, R5 ✅).

## Overview
`InvoiceEventDAO` writes and reads `invoice_events`, the append-only activity log of an account invoice (created, confirmed, reverted to draft, voided, items synced, payment recorded / voided, admin changes). Writers: `AccountInvoiceManager._log_event`, called by the invoice manager, the invoice payment manager, the invoice items endpoint and the attachment manager. Reader: `AccountInvoiceManager.get_events` ← `GET /account-invoices/{id}/events/`. It protects workspace isolation through the row's `workspace_id`. It flushes, never commits, never updates or deletes a row.

**Callables:** 2 specified · 2 not specified
**Externals to mock:** none needed. `created_at` defaults to `app.utils.time.utcnow` bound at import (patching does not reach it); to control times, set them by SQL after creating.
**Integration-only behavior:** none.

**Model facts (table `invoice_events`, class `app.models.invoice_event.InvoiceEvent`):** `id` PK; `workspace_id` NOT NULL → `workspaces` ON DELETE CASCADE; `invoice_id` NOT NULL → `account_invoices` ON DELETE CASCADE; `event_type` varchar(50) NOT NULL; `description` text NOT NULL; `metadata_json` `json` (not `jsonb`) nullable; `performed_by` → `profiles` ON DELETE SET NULL; `created_at` NOT NULL — Python `utcnow()` (naive UTC), the database also has `DEFAULT now()`, which the model never leaves to it. Indexes: primary key, `invoice_id`, `workspace_id`. No check constraint, no trigger.

**Notes for the test designer:**
- Use the singleton `invoice_event_dao`; every parameter after `db` is keyword-only.
- An invoice needs an account: `Account(workspace_id, name)`, then `AccountInvoice(workspace_id, account_id, invoice_type="payable", invoice_amount=100, invoice_date=date(…))`; `make_workspace`, `make_profile` from `tests/unit/factories.py`.
- **BUG-638:** create three events, `UPDATE invoice_events SET created_at = :t WHERE id = ANY(:ids)`, force a sequential scan (base spec note), update the lowest-`id` row's `description`; verified to move it last. Intended: highest `id` first among equals; **non-strict** xfail.
- **Database errors:** wrap in `with db.begin_nested():` inside `pytest.raises(...)`.

## Not specified
- `invoice_event_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — no caller on this DAO; base spec.

---

## `InvoiceEventDAO.create_event(db, *, workspace_id, invoice_id, event_type, description, performed_by=None, metadata=None)`
**Shape:** event-log · **Persistence:** writes · **Visibility:** public (used by: `AccountInvoiceManager._log_event`)

**Purpose:** Append one entry to an invoice's history.

**Returns:** the new `InvoiceEvent`, flushed (has an `id`), not committed.

**Rules:**
- **R1.** A row is created with the given `workspace_id`, `invoice_id`, `event_type`, `description`, `performed_by`; `metadata` is stored in `metadata_json`. `created_at` is `utcnow()` at the flush (naive UTC, within a second of the database's `now() AT TIME ZONE 'UTC'`).
- **R2.** `performed_by` defaults to `None`. `metadata` defaults to `None`, stored as the JSON value `null` (`metadata_json IS NULL` is false; it reads back as `None`); a dict or a list is stored and read back as given.
- **R3.** Nothing is validated: an empty `event_type` or `description` is stored, any `event_type` up to 50 characters is accepted, and the invoice's own workspace is not compared with `workspace_id` (a row can be stored under another workspace; HR-16, the caller passes the invoice's).
- **R4.** Database refusals: `event_type` over 50 characters → `DataError` (22001); `description=None` → `IntegrityError` (23502); unknown `invoice_id`, `performed_by` or `workspace_id` → `IntegrityError` (23503). A `metadata` value that is not JSON-serialisable (e.g. a `Decimal`) → `sqlalchemy.exc.StatementError` wrapping `TypeError` at the flush; nothing is saved.
- **R5.** Flushed, not committed: rolling back a savepoint removes the row.

**Errors:** as in R4.

**Side effects:** one row inserted and flushed.

---

## `InvoiceEventDAO.get_by_invoice(db, *, invoice_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `AccountInvoiceManager.get_events`)

**Purpose:** The whole history of one invoice, newest first, with the performer's name.

**Returns:** a `list` of `dict`, each with exactly the keys `id`, `workspace_id`, `invoice_id`, `event_type`, `description`, `metadata_json`, `performed_by`, `performed_by_name`, `created_at`.

**Rules:**
- **R1.** Returns the events with that `invoice_id` and that `workspace_id`; another invoice's never. An event stored under another workspace is returned only when asking with that workspace. Unknown invoice or `0` → `[]`.
- **R2.** Every matching event is returned (no cap, no paging).
- **R3.** [BUG-638] (HR-6) Ordered by `created_at` newest first, then `id` descending: events of one time come back highest `id` first, also after one of them was updated. *(Today: `created_at` only; verified `42368, 42369, 42370` → `42369, 42370, 42368` after an update.)*
- **R4.** ✅ (P1) `performed_by_name` is the performer's current profile `name`; `None` when `performed_by` is `None` (including after the profile was deleted, which sets `performed_by` to `NULL`).
- **R5.** ✅ (P1) The invoice's state is not looked at (voided, draft, confirmed alike).
- **R6.** Each dict carries the stored values unchanged (`metadata_json` as stored, `created_at` naive).

**Errors:** none

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 12–22 | keyword-only; defaults `performed_by=None`, `metadata=None` | Notes; `create_event` R2 |
| 23–30 | row from the arguments, unvalidated | `create_event` R1, R2, R3, R4 |
| 31–33 | add, flush, return | `create_event` R1, R4, R5 |
| 36–38 | outer join profile (missing → `None`) | `get_by_invoice` R4 |
| 39–42 | invoice AND event workspace; invoice state not read | `get_by_invoice` R1, R5 |
| 43 | `created_at DESC` only (BUG-638) | `get_by_invoice` R3 |
| 44 | `.all()`, no limit | `get_by_invoice` R2 |
| 46–59 | dict per row; zero / many | `get_by_invoice` R1, R6 |
| 62 | singleton | Not specified |
| `models/invoice_event.py` 33 | `created_at` Python default | `create_event` R1 |
