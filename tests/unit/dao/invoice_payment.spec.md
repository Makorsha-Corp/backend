# Spec — `app/dao/invoice_payment.py`

> **Status:** APPROVED (2026-11-10; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-09.** No owner answer in this round. **Delegated:** P1 and Q1 accepted as suggested, decided by Claude under the reviewer's delegation (2026-11-09). None of them is the owner's own answer. The house-rule line reuses an existing bug.

> **Review round 2026-11-10 (fill-gaps).** One fact gap of `invoice_payment.cases.md` closed (Gap log at the end); no question.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated. This DAO overrides nothing.
>
> **Reference specs.** The money rules that use this DAO are in `tests/unit/managers/invoice_payment_manager.spec.md` (approved, PASS): what a payment may be, when the invoice's `paid_amount` / `payment_status` change, voiding, the refused delete (BUG-609). They are not re-described here; this spec states only what each read returns.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Raw lookups stay raw (HR-4 scope). HR-16: a row linking to another workspace's row is invalid data, and no response shows another workspace's ids or names. A voided payment is a visible state, not a soft delete (manager spec Notes).
>
> **Verified by running** (throwaway script `a2.py` with my own harness `ha.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omd\A\`, each transaction rolled back against `marker_test`, private `COVERAGE_FILE`; nothing committed): the table's columns, nullability, defaults, constraints, indexes, no trigger, database `TimeZone` (`America/New_York`); `created_at` of a new row (15:38 for 20:38 UTC); `get_by_invoice` with two active and one voided payment, a row of another workspace on the invoice, from the other workspace, another invoice, a page; four payments of one date after an update (came back `1st, 4th, 3rd, 2nd` by id); `get_by_id_and_workspace_with_creator` own / other workspace / unknown, a voided payment, no creator; `get_total_paid_for_invoice` with none, active + voided, all voided, another workspace, unknown invoice, a foreign-workspace row on the invoice, a `0.00` row, a negative row, an unflushed row with autoflush off, `1.005` / `-1.005` stored (→ `1.01` / `-1.01`), two rows of `9999999999999.99` (sum `19999999999999.98`, above the column's range); `get_by_date_range` one day. **Read, not run:** `app/managers/invoice_payment_manager.py`, `app/services/invoice_payment_service.py`, the endpoints. **Not run:** anything over HTTP; two concurrent transactions; the intended behaviour of the bug rules.

## Review
> All answered; applied 2026-11-09.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | A payment's "recorded at" time is the database's local clock, not UTC | bug — UTC (BUG-2400) | Claude, delegated |
| Q1 | "Payments between two dates" has no caller | remove | Claude, delegated |

Decided by house rules: payments of one date come back in no fixed order (existing BUG-600; its fix is in this file).

### House-rule violations — applied automatically

- **HR-6** `get_by_invoice` R3 — ordered by `payment_date` newest first only. Verified: four payments of one date came back `1st, 4th, 3rd, 2nd` by id after an update. This is the defect already logged as BUG-600 against `InvoicePaymentManager.list_payments_by_invoice` R4, whose only query is this method. Intended: `payment_date` descending, then `id` descending, before `skip` / `limit`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-600 (existing, no new ID; the fix is in this file). Rules: `get_by_invoice` R3.

Checked and **not** a new line here: **HR-4** — the table has no soft-delete column; voided payments are listed and returned on purpose (manager spec `list_payments_by_invoice` R3) and left out of the total (R2 below). **HR-5** — every filter is in the query before `skip` / `limit`. **HR-7** — the payment list endpoint requires `1 <= limit <= 1000` (manager spec Inputs). **HR-8** — no `LIKE`. **HR-9** — no "last changed by" column. **HR-10** — the reads take no lock; the manager locks the invoice row before it reads the total (`create_payment` R2, `void_payment` R9, BUG-601). **HR-15** — the total is an exact sum of `Numeric(15,2)` values; nothing is rounded here. **HR-16** — every method filters on the payment's own `workspace_id`; a payment of another workspace attached to this invoice (invalid data) is neither listed nor counted for this workspace (R of each).

### Precedent matches — accepted (decided by Claude under the reviewer's delegation, 2026-11-09)

### P1. A payment's "recorded at" time is the database's local clock — 🐞 BUG-2400
**Background:** `invoice_payments.created_at` has no Python default; the database fills it with `now()` on a `timestamp without time zone` column, which stores the local time of the session's `TimeZone`. Every other time in the application is naive UTC (`utcnow()`). The same was ruled a bug for product ledger entries (BUG-1337) and the financial audit log (BUG-2372).
**What happens today:** Every payment recorded through the API gets local time. Verified: a payment recorded at 20:38 UTC has `created_at` 15:38 under `America/New_York`; under `Asia/Dhaka` it would read 02:38 the next day. The value is in every payment response (`InvoicePaymentResponse.created_at`), and the payment's void time (`voided_at`, `utcnow()`) is UTC.
**Example:** A payment is recorded at 20:38 UTC and voided one minute later. The payment shows "recorded 15:38, voided 20:39": voided five hours after it was recorded, by the record.
**Rules affected:** Model facts (`created_at`); inherited `create` R1a
**Answer:** bug — per BUG-1337 precedent: `created_at` defaults to `utcnow()`, naive UTC
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-09): 🐞 BUG-2400 (pattern `database-clock-timestamp`; fix in `app/models/invoice_payment.py`, and the database default in a migration). Rules: inherited `create` R1a (tagged).

### New questions (decided by Claude under the reviewer's delegation, 2026-11-09)

### Q1. "Payments between two dates" has no caller — 🗑️ remove (dead code)
**Background:** `get_by_date_range` returns a workspace's payments with `payment_date` between two dates. Nothing in `app/`, `scripts/` or `tests/` calls it (grep), and the checklist does not mark it; its two siblings `get_by_payment_method` and `get_recent_payments` were already removed as dead code. The calendar reads invoice payments with its own query (`calendar_service._collect_invoice_payments`).
**What happens today:** Reachable by nobody. Verified facts, if it is kept: both bounds inclusive, voided payments included, newest date first with no tie-break (the same HR-6 defect as BUG-600), default 100 rows.
**Example:** No endpoint, report or job lists payments by date through this method; deleting it changes nothing a user can see.
**Rules affected:** `get_by_date_range` (all)
**Suggested answer:** `remove`. If a cash-flow report needs it later, it gets a section with `payment_date` then `id`, and a decision on voided payments.
**Answer:** remove
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-09); not specified; listed under **Not specified** and for `docs/testing/dead-code-removal-checklist.md` (`app/dao/invoice_payment.py:58`). Not a bug, no BUG ID.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Invoice payment service** (`app/services/invoice_payment_service.py`, not yet specified) | `_payment_response` re-reads the payment with `get_by_id_and_workspace_with_creator` only for the creator's name, and falls back to "no name" when it finds nothing. `delete_payment` reads the payment before calling the manager, which (after BUG-609) always refuses: that read stays only for the 404. | reading the callers |
| FU-2 | **Invoice payment schema** (`app/schemas/invoice_payment.py`) | The database stores a `0.00` or negative `payment_amount` (no check constraint, verified); only the schema's `> 0` keeps them out. A `CHECK (payment_amount > 0)` would make the rule hold for every writer; not decided here. | verified while checking the total |

## Overview
`InvoicePaymentDAO` reads `invoice_payments`, the individual payments recorded against account invoices (payables and receivables). Callers: `InvoicePaymentManager` (`get_by_invoice` for the list; `get_total_paid_for_invoice` when a payment is voided, or deleted before BUG-609, to recompute the invoice's `paid_amount`; inherited `create`, `get_by_id_and_workspace`, `update`, `remove`), `InvoicePaymentService` (`get_by_id_and_workspace_with_creator` for the detail, the delete check and the response's creator name). Every method filters on the payment's `workspace_id`. It never commits and takes no lock.

**Callables:** 3 specified · 2 not specified (+ inherited `BaseDAO` methods, base spec)
**Externals to mock:** none. No method reads the clock; `created_at` is the database's `now()` (BUG-2400).
**Integration-only behavior:** none.

**Model facts (table `invoice_payments`, class `app.models.invoice_payment.InvoicePayment`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK (also a plain index `ix_invoice_payments_id`) | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE, indexed | — |
| `invoice_id` | Integer NOT NULL, FK `account_invoices.id` ON DELETE CASCADE, indexed | — |
| `payment_amount` | Numeric(15,2) NOT NULL; no check constraint (`0.00` and negative are stored); extra decimals rounded half away from zero on write (`1.005` → `1.01`, `-1.005` → `-1.01`) | — |
| `payment_date` | Date NOT NULL, indexed | — |
| `payment_method` | String(50) nullable | `NULL` |
| `payment_reference`, `transaction_id` | String(100) nullable | `NULL` |
| `bank_name` | String(255) nullable | `NULL` |
| `notes`, `void_note` | Text nullable | `NULL` |
| `is_voided` | Boolean NOT NULL | Python `False`; no database default |
| `voided_at` | `timestamp without time zone` nullable | `NULL` |
| `voided_by`, `created_by` | Integer nullable, FK `profiles.id`, no delete action (a referenced profile cannot be deleted) | `NULL` |
| `created_at` | `timestamp without time zone` NOT NULL | database `now()`, local time (BUG-2400) |
- No trigger, no unique constraint besides the PK. Relationships `invoice` (backref `payments`), `creator`, `voider`.
- Profiles have no soft-delete column; `profiles.name` is NOT NULL, so a creator name is `None` only when `created_by` is `NULL`.

**Notes for the test designer:**
- Use the singleton `invoice_payment_dao`. Every parameter after `db` is keyword-only.
- Model modules: `from app.models.account import Account`, `from app.models.account_invoice import AccountInvoice`, `from app.models.invoice_payment import InvoicePayment` (checked against the model registry, 2026-11-10).
- An invoice needs an account: `Account(workspace_id=…, name=…)`, then `AccountInvoice(workspace_id=…, account_id=…, invoice_type="payable", invoice_amount=Decimal("100"), invoice_date=date(…))`. Payments: `InvoicePayment(workspace_id=…, invoice_id=…, payment_amount=Decimal(…), payment_date=date(…), created_by=…)`.
- The total reads flushed rows only: with the test session's `autoflush=False`, an added but unflushed payment is not counted (verified). Flush before reading.
- BUG-600 tie: four payments of one `payment_date`, then `UPDATE invoice_payments SET notes='x'` on the lowest id so physical order differs; **non-strict** xfail.
- BUG-2400: under `SET LOCAL TimeZone = 'Asia/Dhaka'`, a new payment's `created_at` is within a minute of `utcnow()`; strict xfail.

## Not specified
- `invoice_payment_dao` — module-level singleton, no logic.
- `InvoicePaymentDAO.get_by_date_range` — dead code, to be removed (Q1, decided by Claude under the reviewer's delegation).
- Inherited `BaseDAO` methods — base spec. Used: `create` with the schema (`create_payment`), `get_by_id_and_workspace` (update, void, delete), `update` with a dict (`update_payment`), `remove` (`delete_payment`; unreachable once BUG-609 is fixed, since a delete is then always refused).

---

## Inherited `create` (model facts a test of this table relies on)
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `InvoicePaymentManager.create_payment`)

**Rules:**
- **R1.** A new row gets `is_voided = False`, the void fields `NULL`, and `created_at` from the database. Flushed, not committed. An unknown `invoice_id`, `workspace_id` or `created_by` fails at flush with `IntegrityError` 23503.
- **R1a.** [BUG-2400] (P1) `created_at` is the current time in naive **UTC**, whatever the database session's `TimeZone`. *(Today: the database's `now()`, local time of the session's `TimeZone`: 15:38 for 20:38 UTC under `America/New_York`.)*

**Side effects:** one row inserted and flushed.

---

## `InvoicePaymentDAO.get_by_invoice(db, *, invoice_id, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `InvoicePaymentManager.list_payments_by_invoice` ← `GET` of an invoice's payments)

**Purpose:** An invoice's payments, newest date first, with the name of whoever recorded each.

**Inputs:** `invoice_id`, `workspace_id` — ints; `skip` default 0, `limit` default 100, not checked here.

**Returns:** a `list` of plain 2-tuples `(InvoicePayment, created_by_name)`.

**Rules:**
- **R1.** Only payments with this `invoice_id` **and** this `workspace_id`, voided ones included. An invoice with none, another invoice's payments, or an unknown invoice → `[]`. A payment of another workspace on this invoice (invalid data) is not listed for this workspace.
- **R2.** `created_by_name` is the recorder's profile `name`, or `None` when `created_by` is `NULL`.
- **R3.** Newest `payment_date` first. [BUG-600] Payments of one date follow by `id` descending, before `skip` / `limit`. *(Today: `payment_date` alone; payments of one date come back in physical order, which an update changes.)*
- **R4.** `skip` / `limit` apply after the order: at most `limit` tuples, starting after `skip`; `limit=0` → `[]`; negative values reach the database as `DataError` (unreachable from the API).
- **R5.** One query (the creator is joined, not read separately); no lock. The invoice's own status or existence is not checked here (the manager checks it first, manager spec R1).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` / `skip` | `DataError` (2201W / 2201X) | Postgres message (not asserted) |

**Side effects:** none.

---

## `InvoicePaymentDAO.get_by_id_and_workspace_with_creator(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `InvoicePaymentService.get_payment`, `delete_payment`, `_payment_response`)

**Purpose:** One payment of the workspace, with the recorder's name.

**Inputs:** `id`, `workspace_id` — ints.

**Returns:** a plain 2-tuple `(InvoicePayment, created_by_name)`, or `None`.

**Rules:**
- **R1.** Returns the pair when a payment has this `id` and this `workspace_id`, voided or not. The name follows `get_by_invoice` R2.
- **R2.** An id of another workspace, an unknown id, or `0` → `None` (the service answers 404 `Payment with ID {payment_id} not found`).
- **R3.** One query, no lock.

**Errors:** none.
**Side effects:** none.

---

## `InvoicePaymentDAO.get_total_paid_for_invoice(db, *, invoice_id, workspace_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `InvoicePaymentManager.void_payment`, `delete_payment`)

**Purpose:** The amount actually paid on an invoice: the sum of its payments that are not voided.

**Inputs:** `invoice_id`, `workspace_id` — ints.

**Returns:** a `Decimal` with two decimals.

**Rules:**
- **R1.** The sum of `payment_amount` over the payments with this `invoice_id` and this `workspace_id` whose `is_voided` is `False`. Example: `10.10` and `20.20` active, `5.00` voided → `Decimal('30.30')`.
- **R2.** Voided payments never count; when every payment is voided, or there are none, or the invoice is unknown → `Decimal('0.00')`.
- **R3.** A payment of another workspace on this invoice (invalid data, HR-16) is not counted: with a `1000.00` row of workspace B on workspace A's invoice, A's total stays `30.30`.
- **R4.** The sum is exact; nothing is rounded here (stored values already have two decimals). A sum of exactly zero (e.g. a single `0.00` row) is returned as `Decimal('0.00')`. Values the schema refuses but the database stores (a negative row) are summed as stored: `0.00` + `-5.00` → `Decimal('-5.00')`.
- **R5.** The sum is not capped at the column's range: two rows of `9999999999999.99` give `Decimal('19999999999999.98')` (it would not fit `paid_amount`; unreachable, since the manager never lets payments exceed the invoice amount, manager spec `create_payment` R5).
- **R6.** Only flushed rows count; no lock is taken (the manager holds the invoice row lock, BUG-601).

**Errors:** none.
**Side effects:** none.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 26–32 | outer join profile; workspace AND invoice | `get_by_invoice` R1, R2, R5 |
| 33 | `payment_date DESC` only (BUG-600) | `get_by_invoice` R3 |
| 34–38 | offset / limit; tuples | `get_by_invoice` R4 |
| 44–51 | outer join profile; id AND workspace | `get_by_id_and_workspace_with_creator` R1, R2 |
| 53–56 | `row is None` → `None`; else the pair | `get_by_id_and_workspace_with_creator` R1, R2 |
| 58–87 | no caller | Not specified (Q1, dead code) |
| 103–111 | `sum(payment_amount)`, workspace AND invoice AND not voided | `get_total_paid_for_invoice` R1, R3, R4, R5, R6 |
| 112 | `result if result else Decimal('0.00')` (`None` or zero → `0.00`) | `get_total_paid_for_invoice` R2, R4 |
| 114 | singleton | Not specified |
| model | `created_at` database `now()` (BUG-2400) | inherited `create` R1, R1a |

## Gap log
- G1 (invoice_payment.cases.md gap 1) — Fact — Notes for the test designer: `Account` is `app.models.account.Account`, `AccountInvoice` is `app.models.account_invoice.AccountInvoice` (the conventions' assumption is right).
