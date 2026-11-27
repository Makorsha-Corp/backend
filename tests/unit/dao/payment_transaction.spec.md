# Spec — `app/dao/payment_transaction.py`

> **Status:** APPROVED (2026-11-10; nothing open — OQ-25 deferred by the owner to the payment portal, `get_stuck_initiated` R7 keeps today's behaviour)
> **Source commit:** e48a092

> **Review round 2026-11-09.** No owner answer in this round. **Delegated:** P1 accepted as suggested, decided by Claude under the reviewer's delegation (2026-11-09). That is not the owner's own answer. The house-rule lines stand. **Raised to the owner:** OQ-25 (which rows the reconciliation sweep looks at), parked in `docs/testing/owner-questions.md`, not blocking.

> **Review round 2026-11-10 (apply-review + fill-gaps).** **Owner:** OQ-25 — "decide in the payment portal work" (owner, 2026-11-10); R7 keeps today's behaviour, marked deferred; no bug. **Gaps:** the three gaps of `payment_transaction.cases.md` closed (Gap log at the end); gaps 1–2 checked on `marker_test` (own script `g1.py` in `C:/Users/User/AppData/Local/Temp/makorsh-pipeline/omd/G/`, rolled back, private `COVERAGE_FILE`).

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated. This DAO overrides nothing.
>
> **Portal reference.** The owner wants these tests as the reference for the coming subscription payment portal. The rules below state the intended behaviour fully where it is clear; the manager rules they serve are in `tests/unit/managers/payment_transaction_manager.spec.md` (approved, PASS) and are not re-described here.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Raw lookups stay raw (HR-4 scope). HR-16: a row linking to another workspace's row is invalid data, and no response shows another workspace's ids or names. The unscoped `tran_id` lookups are unscoped **by design**: the public gateway callbacks carry no workspace, and the workspace is read from the row (file docstring, manager spec `finalize_from_gateway` R1).
>
> **Verified by running** (throwaway scripts `a1.py`, `a2.py` with my own harness `ha.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omd\A\`, each transaction rolled back against `marker_test`, private `COVERAGE_FILE`; nothing committed): the table's columns, nullability, defaults, constraints, indexes, no trigger, database `TimeZone` (`America/New_York`); `get_by_tran_id` own row, another workspace's row, unknown, `""`, upper-cased, trailing space, 40 characters; `get_by_tran_id_for_update` found (SQL ends `FOR UPDATE`) and unknown; both `…_with_initiator` lookups for own / other workspace / unknown / `0`, with and without an initiator, return type `Row` of two; a plain `FOR UPDATE` on the initiator join (fails, `FeatureNotSupported` 0A000) and `FOR UPDATE OF payment_transactions` (works); the list with four rows of one `created_at` and one newer under a forced sequential scan after two updates, a page, `limit=0`, negative `limit`, another workspace; `get_stuck_initiated` across two workspaces, the strict cutoff, `EXPIRED` / `INIT_FAILED` / `CANCELLED` / lowercase `initiated` left out, `limit` 2 / 0 / negative, an aware cutoff, four tied `initiated_at` rows (came back `2nd, 3rd, 4th, 1st` by id after an update), no lock clause; inherited `create` with a dict; a raw insert without the time columns under `Asia/Dhaka` (`a3.py`); negative `skip` (2201X); a duplicate `tran_id` in another workspace (23505), a 31-character `tran_id` (22001), any `status` text and a negative `amount` stored. **Read, not run:** `app/managers/payment_transaction_manager.py`, `app/services/payment_transaction_service.py`, `app/api/v1/endpoints/payments.py`, `scripts/reconcile_payments.py`. **Not run:** anything over HTTP; two concurrent transactions; the intended behaviour of the bug rules.

## Review
> All answered or parked; applied 2026-11-09.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | The database fills a missing payment time with its own local clock, not UTC | bug — UTC (BUG-2401) | Claude, delegated |
| OQ-25 | The sweep only re-checks payments still `INITIATED`; a payment wrongly closed by a browser redirect, or `EXPIRED`, is never asked about again | deferred to the payment portal (owner, 2026-11-10); today's behaviour stays, no bug | **owner** |

Decided by house rules: the payment ledger list puts payments of one creation time in no fixed order (BUG-2402); the sweep picks its batch of stuck payments in no fixed order when their start times tie (BUG-2403).

### House-rule violations — applied automatically

- **HR-6** `list_by_workspace_with_initiator` R4 — ordered by `created_at` newest first, nothing after it. Verified under a forced sequential scan: four rows of one `created_at` came back `3rd, 1st, 4th, 2nd` by id after two updates, not by id; a page of 2 after `skip=1` was `3rd, 1st`. The future-notes file already flagged it (`subscription-payments.md`, "ledger list … no `id` tie-break"). Intended: `created_at` newest first, then `id` descending, before `skip` / `limit` (BUG-1442 precedent).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-2402 (pattern `tied-timestamp-no-tiebreak`). Rules: `list_by_workspace_with_initiator` R4.
- **HR-6** `get_stuck_initiated` R3 — ordered by `initiated_at` oldest first, nothing after it, then cut at `limit` (a top-N). Verified: four rows of one `initiated_at` came back `2nd, 3rd, 4th, 1st` by id after one update. With more than `limit` stuck rows of one time, which ones this sweep handles is arbitrary. Intended: `initiated_at` oldest first, then `id` ascending, before `limit`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-2403 (pattern `tied-timestamp-no-tiebreak`). Rules: `get_stuck_initiated` R3.

Checked and **not** a new line here: **HR-4** — the table has no soft-delete column and profiles have none. **HR-5** — every filter is in the query before `skip` / `limit`. **HR-7** — `GET /payments/` requires `skip >= 0` and `1 <= limit <= 200`; the sweep's `limit` comes from the script (manager spec R1–R2, R9). **HR-8** — no `LIKE`. **HR-9** — no "last changed by" column; `updated_at` is the model's `onupdate`. **HR-10** — the DAO offers the lock (`get_by_tran_id_for_update`); the missing lock on risk resolution is the existing BUG-029, below. **HR-15** — the DAO computes no money. **HR-16** — the workspace lookups and the list filter on the row's own `workspace_id`; the `tran_id` lookups and the sweep are unscoped by design (standing decision above); every response built from them shows only the row's own workspace. **HR-11 / HR-12 / HR-13 / HR-14** — gateway outcomes are the manager's (BUG-019, BUG-023 … BUG-027, BUG-032).

### Existing bugs that land in this file (no new ID)
- **BUG-029** (manager spec Q11, `resolve_risk` R6a): risk resolution must read the row with a lock. Its only lookup is `get_by_id_and_workspace_with_initiator`, which joins the initiator's profile with an **outer** join. A plain `FOR UPDATE` on that query fails in Postgres (`FOR UPDATE cannot be applied to the nullable side of an outer join`, `FeatureNotSupported` 0A000, verified), so the fix must lock only the transaction row: `FOR UPDATE OF payment_transactions` (verified to work). Specified below as `get_by_id_and_workspace_with_initiator` R5 (new keyword `for_update`; shape decided by Claude under the reviewer's delegation, 2026-11-09).
- **BUG-026 / BUG-027** (manager spec Q8, Q9, Q16): after their fix, a `VALIDATED_FAILED` / `CANCELLED` row with `outcome_verified = false`, and every `EXPIRED` row, can still be replaced by a later verified result. `get_stuck_initiated` does not return them: only `INITIATED` rows are swept. Whether the sweep should also look at them is OQ-25.

### Precedent matches — accepted (decided by Claude under the reviewer's delegation, 2026-11-09)

### P1. The database fills a missing payment time with its own local clock — 🐞 BUG-2401
**Background:** The model fills `initiated_at`, `created_at` and `updated_at` from `utcnow()` (naive UTC) in Python. The database columns also carry their own default `now()` (added by the migration, not in the model), on `timestamp without time zone`. `now()` there is the local time of the session's `TimeZone` setting (`America/New_York` on the test database). The same drift was ruled a bug for the financial audit log (BUG-2372) and the product ledger (BUG-1337).
**What happens today:** Every write through the application passes the Python value, so the rows are UTC. A row written without those columns (a script, a manual repair, a future writer that bypasses the model) gets local time (verified: a raw insert under `SET LOCAL TimeZone = 'Asia/Dhaka'` got 02:41 the next day for 20:41 UTC in all three columns).
**Example:** A support script inserts a missed checkout by hand at 23:05 UTC. Its `initiated_at` reads 18:05. The sweep compares `initiated_at` with a UTC cutoff, so the row counts as five hours older than it is and is swept at once, before its customer finishes paying.
**Rules affected:** Model facts (`initiated_at`, `created_at`, `updated_at`); inherited `create` R1a
**Answer:** bug — per BUG-2372 precedent: the database default is UTC (`timezone('utc', now())`) or dropped, so a row written without the columns still holds naive UTC
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-09): 🐞 BUG-2401 (pattern `database-clock-timestamp`; fix in a migration). Rules: inherited `create` R1a (tagged).

### Raised to the owner

### OQ-25. The sweep only re-checks payments still `INITIATED` — ⏸ deferred to the payment portal (owner)
**Background:** The reconciliation sweep (`scripts/reconcile_payments.py`) asks the gateway about payments no callback resolved. Its candidates come from `get_stuck_initiated`: status exactly `INITIATED`, started before the cutoff. After BUG-026 / BUG-027 are fixed, three other kinds of row can still be corrected by a later gateway-verified result: `VALIDATED_FAILED` or `CANCELLED` set by an unverified browser redirect (`outcome_verified = false`), and `EXPIRED` set by the sweep itself. But the only thing that can bring that later result is the IPN webhook. If it never arrives, nothing asks again.
**What happens today:** Those rows are never returned (verified: `EXPIRED`, `CANCELLED`, `INIT_FAILED` rows of any age are left out). The customer's money and the ledger can stay apart for good.
**Example:** A customer pays 990 BDT, then presses "Cancel" in an old tab of the same checkout. The cancel redirect arrives first: the payment is `CANCELLED`, unverified. The IPN is lost. The sweep never looks at it again, so the ledger says cancelled although the gateway took the money, and the workspace never gets its plan.
**Rules affected:** `get_stuck_initiated` R7 (own rule, written to today's behaviour)
**Suggested answer:** bug — the sweep also re-checks rows with an unverified outcome (`EXPIRED`, and `VALIDATED_FAILED` / `CANCELLED` with `outcome_verified = false`) for 72 hours after `initiated_at`; each is asked at most once per sweep run, oldest first, inside the same `limit`. A verified answer replaces the outcome as `finalize_from_gateway` R3a/R3b already says; an answer that is not final leaves the row as it is (no second `expired` event).
**Alternatives:** (a) intended — only `INITIATED`; lost IPNs after an unverified outcome are fixed by hand. (b) re-check without a time limit.
**Answer:** owner, 2026-11-10: decide in the payment portal work. Today's behaviour stays in the tests (own cards).
**Resolution:** no bug. `get_stuck_initiated` R7 is marked *deferred to the payment portal (OQ-25)*; when the portal decides, only R7 (and its cards) change. Noted in `docs/future/subscription-payments.md`.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Payment manager** (`resolve_risk`, BUG-029 fix) | Call `get_by_id_and_workspace_with_initiator(…, for_update=True)` (R5). A plain `.with_for_update()` on that query raises 0A000 (500). | BUG-029 |
| FU-2 | **Payment service / endpoints** (`app/services/payment_transaction_service.py`, `app/api/v1/endpoints/payments.py`, not yet specified) | (a) `get_transaction_by_tran_id` turns `None` into 404 `Payment transaction {tran_id} not found` for an unknown or foreign `tran_id`; `list_transactions` passes `skip` / `limit` through. (b) The mock-gateway pages read a transaction by `tran_id` across workspaces and show its amount and currency to anyone holding the `tran_id` (mock only, TODO-001). (c) If OQ-25 is answered `bug`, the sweep needs a second DAO read (or a wider `get_stuck_initiated`) with the new candidate rule. | reading the callers |

## Overview
`PaymentTransactionDAO` reads `payment_transactions`, the ledger of SSLCommerz checkout attempts: one row per `tran_id`. Callers: `PaymentTransactionManager` (`get_by_tran_id` while generating a `tran_id`; `get_by_tran_id_for_update` in the callbacks and the sweep; `get_by_id_and_workspace_with_initiator` in risk resolution; `get_stuck_initiated` in the sweep; inherited `create` when a checkout starts), `PaymentTransactionService` (`get_by_tran_id_and_workspace_with_initiator` ← `GET /payments/{tran_id}/`; `list_by_workspace_with_initiator` ← `GET /payments/`), and the mock-gateway pages in `app/api/v1/endpoints/payments.py` (`get_by_tran_id`). Workspace lookups filter on the row's `workspace_id`; the `tran_id` lookups and the sweep read across workspaces on purpose. It never commits; only `get_by_tran_id_for_update` takes a lock.

**Callables:** 6 specified · 2 not specified (+ inherited `BaseDAO` methods, base spec)
**Externals to mock:** none. No method reads the clock; `older_than` is passed in. The model defaults call `app.models.payment_transaction.utcnow`.
**Integration-only behavior:** the blocking effect of the row lock needs two sessions; within one session the locked read behaves as a plain read. The lock clause itself is unit-testable (SQL capture).

**Model facts (table `payment_transactions`, class `app.models.payment_transaction.PaymentTransaction`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE, indexed | — |
| `tran_id` | String(30) NOT NULL, **unique across all workspaces** (`payment_transactions_tran_id_key`, plus a second unique index `ix_payment_transactions_tran_id`) | — |
| `status` | String(20) NOT NULL, indexed; no check constraint (any text is stored) | `'INITIATED'` (Python and database) |
| `amount` | Numeric(15,2) NOT NULL; no check constraint (a negative value is stored) | — |
| `currency` | String(3) NOT NULL | — |
| `cus_name`, `cus_email` | String(255) nullable | `NULL` |
| `cus_phone` | String(50) nullable | `NULL` |
| `value_a` … `value_d` | String(255) nullable | `NULL` |
| `session_key` | String(64) nullable | `NULL` |
| `gateway_page_url` | Text nullable | `NULL` |
| `val_id` | String(512) nullable, indexed | `NULL` |
| `risk_level` | Integer nullable | `NULL` |
| `risk_title`, `card_type` | String(50) nullable | `NULL` |
| `bank_tran_id` | String(100) nullable | `NULL` |
| `verify_sign` | String(255) nullable | `NULL` |
| `last_ipn_payload` | JSON nullable (no code writes it) | `NULL` |
| `risk_resolved_by`, `initiated_by` | Integer nullable, FK `profiles.id` ON DELETE SET NULL | `NULL` |
| `risk_resolved_at`, `validated_at` | `timestamp without time zone` nullable | `NULL` |
| `risk_resolution_note` | Text nullable | `NULL` |
| `initiated_at`, `created_at`, `updated_at` | `timestamp without time zone` NOT NULL | Python `utcnow()` (naive UTC); database `now()` (local time, BUG-2401); `updated_at` also `onupdate=utcnow` |
- No trigger. Indexes on `id` (PK), `tran_id` (two unique), `status`, `val_id`, `workspace_id`. Relationships `workspace`, `initiator`, `risk_resolver`.
- Status values used by the application: `INITIATED`, `VALIDATED_SUCCESS`, `VALIDATED_FAILED`, `CANCELLED`, `EXPIRED`, `RISK_HOLD`, and `INIT_FAILED` once BUG-019 is fixed. After BUG-026 a new column `outcome_verified` BOOLEAN NOT NULL default `false` (manager spec Q16).
- Profiles have no soft-delete column; `profiles.name` is NOT NULL, so an initiator name is `None` only when `initiated_by` is `NULL`.

**Notes for the test designer:**
- Use the singleton `payment_transaction_dao`. Every parameter after `db` is keyword-only.
- Workspaces from `make_workspace()`, profiles from `make_profile(name=…)`. Build rows with `PaymentTransaction(workspace_id=…, tran_id=…, amount=Decimal("10.00"), currency="BDT", …)`; `tran_id` must be unique in the whole database (use `secrets.token_hex(13)`), because the test database is shared and the uniqueness is global.
- `get_stuck_initiated` and the `tran_id` lookups are unscoped: assert only on the test's own rows (filter the result by the test's workspace ids).
- Lock clauses: capture SQL with a `before_cursor_execute` listener on the test engine; assert the `SELECT … FROM payment_transactions` ends in `FOR UPDATE` (R of `get_by_tran_id_for_update`) or contains `FOR UPDATE OF payment_transactions` (BUG-029 rule).
- Ties (BUG-2402, BUG-2403): give rows one explicit `created_at` / `initiated_at`, force a sequential scan (`SET LOCAL enable_indexscan = off`, `enable_bitmapscan = off`, `enable_indexonlyscan = off`), and update the lowest-`id` row by SQL so physical order differs from id order; **non-strict** xfail (the wrong order is likely, not certain).
- BUG-2401: insert with raw SQL leaving out `created_at`, under `SET LOCAL TimeZone = 'Asia/Dhaka'`, and compare with `utcnow()` within a minute; strict xfail.

## Not specified
- `payment_transaction_dao` — module-level singleton, no logic.
- `PaymentTransactionDAO` class docstring — no behaviour.
- Inherited `BaseDAO` methods — base spec. Used here: `create` with a dict (`initiate_payment`); attributes are changed on the loaded row, not through `update`. `get`, `get_by_id_and_workspace`, `get_by_workspace`, `get_multi`, `update`, `remove` have no caller. A payment row is never deleted by the application (only by the workspace cascade, see `subscription-payments.md` "Ledger retention").

---

## Inherited `create` (model facts that a test of this table relies on)
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `PaymentTransactionManager.initiate_payment`)

**Rules:**
- **R1.** A row created through the model with only `workspace_id`, `tran_id`, `amount`, `currency` gets `status = 'INITIATED'` and `initiated_at`, `created_at`, `updated_at` each set from `app.utils.time.utcnow()` (naive UTC); every other column `NULL`. Flushed, not committed. The three are **separate calls**, one per column default, not one value: each lies inside the call's time window, but a test must not assert they are equal (they came out equal 20/20 on this Windows machine only because its clock ticks about every 15 ms; on a finer clock they can differ by microseconds). No rule needs them equal. The defaults hold the function object itself, so patching `app.utils.time.utcnow` or `app.models.payment_transaction.utcnow` does **not** change them; to pin the times, pass them explicitly.
- **R1b.** `amount` is `Numeric(15,2)`: up to 13 integer digits fit (`9999999999999.99` is stored as is); more decimals round half up (HR-15). A value that needs 14 integer digits, including `9999999999999.995` (it rounds up to `10000000000000.00`) and `10000000000000`, fails at flush with `DataError` 22003 (numeric field overflow); nothing is saved. Real amounts are bounded long before this by the schema and the manager (manager spec `initiate_payment`). Verified on `marker_test` (2026-11-10).
- **R1a.** [BUG-2401] (P1) A row inserted without `initiated_at` / `created_at` / `updated_at` (raw SQL, bypassing the model) gets the current time in naive **UTC**, whatever the database session's `TimeZone`. *(Today: the database default `now()` stores local time of the session's `TimeZone`, e.g. 5 hours behind UTC under `America/New_York`.)*
- **R2.** A `tran_id` already used by any row, in any workspace, fails at flush with `IntegrityError` 23505 (`payment_transactions_tran_id_key`); a `tran_id` over 30 characters fails with `DataError` 22001. Nothing is saved.
- **R3.** The database stores any `status` text and any `amount`, negative included: valid values are the schema's and the manager's job (manager spec `initiate_payment` R9, R9a, R10a).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `tran_id` taken | `IntegrityError` (23505) at flush | Postgres message (not asserted) |
| `tran_id` > 30 chars | `DataError` (22001) at flush | Postgres message (not asserted) |
| `amount` needs 14+ integer digits | `DataError` (22003) at flush | Postgres message (not asserted) |

**Side effects:** one row inserted and flushed.

---

## `PaymentTransactionDAO.get_by_tran_id(db, *, tran_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `PaymentTransactionManager._generate_tran_id`; the mock-gateway pages `GET /payments/mock-gateway/{tran_id}` and `POST …/complete`)

**Purpose:** Find a checkout attempt by its gateway id, in any workspace.

**Inputs:** `tran_id` — `str`, any text; not trimmed, not lower-cased.

**Returns:** the `PaymentTransaction` or `None`.

**Rules:**
- **R1.** Returns the row whose `tran_id` equals the argument exactly, whatever its workspace or status.
- **R2.** Matching is exact: an upper-cased copy of a lowercase `tran_id`, the `tran_id` with a trailing space, `""`, or a string longer than 30 characters return `None` (no error).
- **R3.** Unscoped by design (gateway callbacks carry no workspace; `_generate_tran_id` needs global uniqueness, manager spec R1). It never locks and never writes.

**Errors:** none.
**Side effects:** none.

---

## `PaymentTransactionDAO.get_by_tran_id_for_update(db, *, tran_id)`
**Shape:** get
**Persistence:** reads (locks)
**Visibility:** public (used by: `PaymentTransactionManager.finalize_from_gateway`, `mark_terminal_without_validation`, `reconcile_stuck_transactions`)

**Purpose:** Find a checkout attempt by `tran_id` and lock it, so two gateway callbacks cannot both finalize it.

**Inputs:** `tran_id` — `str`, matched as in `get_by_tran_id` R1–R2.

**Returns:** the `PaymentTransaction` or `None`.

**Rules:**
- **R1.** Returns the same row as `get_by_tran_id` for the same argument (exact match, any workspace, any status), or `None`.
- **R2.** The row is read with `SELECT … FOR UPDATE`: the lock is held until the caller's transaction commits or rolls back. A concurrent locked read of the same row waits. (Clause unit-testable; the wait itself is integration-only.)
- **R3.** An unknown `tran_id` returns `None` and locks nothing.
- **R4.** At most one row can match (`tran_id` is unique), so the "more than one row" error of `one_or_none` cannot occur.

**Errors:** none.
**Side effects:** row lock on the matched row for the rest of the transaction.

---

## `PaymentTransactionDAO.get_by_id_and_workspace_with_initiator(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `PaymentTransactionManager.resolve_risk` ← `POST /payments/{transaction_id}/resolve-risk/`)

**Purpose:** Find a workspace's transaction by id, with the name of whoever started it.

**Inputs:** `id` — int; `workspace_id` — int; [BUG-029] `for_update` — bool, default `False` *(requires new parameter)*.

**Returns:** a pair `(PaymentTransaction, initiated_by_name)` (an SQLAlchemy `Row` that unpacks as two values), or `None`.

**Rules:**
- **R1.** Returns the pair when a row has this `id` and this `workspace_id`. `initiated_by_name` is the initiator's profile `name`.
- **R2.** `initiated_by_name` is `None` when `initiated_by` is `NULL` (never set, or the profile was deleted: `ON DELETE SET NULL`). The row is still returned.
- **R3.** Returns `None` for an id of another workspace, an unknown id, or `0`. Status does not matter.
- **R4.** One query (no separate profile read). Without `for_update`, no lock is taken.
- **R5.** [BUG-029] With `for_update=True` the transaction row is read with `FOR UPDATE OF payment_transactions` (only that row is locked; the profile is not), with the same result as R1–R3. *(Today: no such parameter; the row is read without a lock. A plain `FOR UPDATE` on this outer join is refused by Postgres with `FeatureNotSupported` 0A000, so the lock must name the table. Shape decided by Claude under the reviewer's delegation, 2026-11-09.)*

**Errors:** none.
**Side effects:** none (R5: row lock on the transaction row).

---

## `PaymentTransactionDAO.get_by_tran_id_and_workspace_with_initiator(db, *, tran_id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `PaymentTransactionService.get_transaction_by_tran_id` ← `GET /payments/{tran_id}/`)

**Purpose:** Find a workspace's transaction by `tran_id`, with the initiator's name, for the detail page.

**Inputs:** `tran_id` — `str` (matched exactly as `get_by_tran_id` R2); `workspace_id` — int.

**Returns:** a pair `(PaymentTransaction, initiated_by_name)` (`Row` of two), or `None`.

**Rules:**
- **R1.** Returns the pair when the row's `tran_id` equals the argument exactly and its `workspace_id` is this workspace. The name follows `get_by_id_and_workspace_with_initiator` R2.
- **R2.** Another workspace's `tran_id` returns `None` (HR-16: the caller answers 404 and shows nothing of it). Unknown, `""` or too long → `None`.
- **R3.** One query, no lock.

**Errors:** none.
**Side effects:** none.

---

## `PaymentTransactionDAO.list_by_workspace_with_initiator(db, *, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `PaymentTransactionService.list_transactions` ← `GET /payments/`, `skip >= 0`, `1 <= limit <= 200`)

**Purpose:** The workspace's payment ledger, newest first, with initiator names.

**Inputs:** `workspace_id` — int; `skip` — int, default 0; `limit` — int, default 100. Not checked here.

**Returns:** a `list` of plain 2-tuples `(PaymentTransaction, initiated_by_name)`.

**Rules:**
- **R1.** Only rows with this `workspace_id`, every status (`INITIATED`, `RISK_HOLD`, `EXPIRED`, `INIT_FAILED` …). Another workspace's rows never appear; a workspace with none gives `[]`.
- **R2.** Each name follows `get_by_id_and_workspace_with_initiator` R2.
- **R3.** Newest `created_at` first.
- **R4.** [BUG-2402] Rows of one `created_at` follow by `id` descending, so the full order is fixed and pages never repeat or skip a row. *(Today: `created_at` alone; tied rows come back in physical order, which an update changes.)*
- **R5.** `skip` / `limit` apply after the order of R3–R4: at most `limit` rows, starting after `skip`. `limit=0` → `[]`; a `skip` past the end → `[]`.
- **R6.** A negative `limit` or `skip` reaches the database: `DataError` (`InvalidRowCountInLimitClause` 2201W for `limit`). Unreachable from the API (HR-7 bounds on the endpoint).
- **R7.** One query, no lock.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` / `skip` | `DataError` (2201W / 2201X) | Postgres message (not asserted) |

**Side effects:** none.

---

## `PaymentTransactionDAO.get_stuck_initiated(db, *, older_than, limit=200)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `PaymentTransactionManager.reconcile_stuck_transactions` ← `scripts/reconcile_payments.py`)

**Purpose:** The candidates of the reconciliation sweep: checkouts still waiting for an outcome after the timeout, in all workspaces.

**Inputs:** `older_than` — `datetime`, the cutoff; the manager passes naive UTC (`utcnow() − older_than_minutes`). `limit` — int, default 200, not checked.

**Returns:** a `list` of `PaymentTransaction`.

**Rules:**
- **R1.** Only rows whose `status` is exactly `'INITIATED'` (case-sensitive: `'initiated'` is left out) and whose `initiated_at` is strictly earlier than `older_than`. A row started exactly at the cutoff is left out.
- **R2.** Rows of every workspace are returned together.
- **R3.** Oldest `initiated_at` first. [BUG-2403] Rows of one `initiated_at` follow by `id` ascending, before `limit`, so which rows fill a batch is fixed. *(Today: `initiated_at` alone; tied rows come back in physical order.)*
- **R4.** At most `limit` rows; `limit=0` → `[]`; a negative `limit` → `DataError` 2201W.
- **R5.** No lock is taken (the manager re-reads each candidate with `get_by_tran_id_for_update`, manager spec R3).
- **R6.** `older_than` is compared as given. A naive value is compared as stored (naive UTC). An aware value is converted by Postgres using the session's `TimeZone`, so its result depends on the server (not reached: the manager always passes naive).
- **R7.** (deferred to the payment portal (OQ-25), owner 2026-11-10) Rows whose outcome is unverified are not candidates: `EXPIRED`, `VALIDATED_FAILED` and `CANCELLED`, of any age, are never returned; nor are `INIT_FAILED` and `RISK_HOLD`. The selection is by `status` alone: `outcome_verified` does not exist until BUG-026 is fixed, and even then this rule ignores it, so the cards stay status-only. *(This is today's behaviour, kept in its own rule; the portal's decision changes only this rule.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `DataError` (2201W) | Postgres message (not asserted) |

**Side effects:** none.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 21–22 | exact `tran_id`, unscoped, `.first()` | `get_by_tran_id` R1, R2, R3 |
| 27–32 | exact `tran_id`, unscoped, `FOR UPDATE`, `one_or_none` | `get_by_tran_id_for_update` R1–R4 |
| 37–42 | outer join profile; id AND workspace; no lock (BUG-029) | `get_by_id_and_workspace_with_initiator` R1–R5 |
| 43–45 | `row is None` → `None`; else the row | `get_by_id_and_workspace_with_initiator` R1, R3 |
| 50–55 | outer join profile; `tran_id` AND workspace | `get_by_tran_id_and_workspace_with_initiator` R1, R2, R3 |
| 56–58 | `row is None` → `None`; else the row | `get_by_tran_id_and_workspace_with_initiator` R1, R2 |
| 63–66 | outer join profile; workspace filter | `list_by_workspace_with_initiator` R1, R2 |
| 67 | `created_at DESC` only (BUG-2402) | `list_by_workspace_with_initiator` R3, R4 |
| 68–70 | offset / limit after order | `list_by_workspace_with_initiator` R5, R6 |
| 72 | tuples | `list_by_workspace_with_initiator` Returns |
| 79 | `status == 'INITIATED'` AND `initiated_at < older_than`, unscoped | `get_stuck_initiated` R1, R2, R6, R7 |
| 80 | `initiated_at ASC` only (BUG-2403) | `get_stuck_initiated` R3 |
| 81 | limit | `get_stuck_initiated` R4 |
| 86 | singleton | Not specified |
| model | defaults, unique `tran_id`, no checks; database `now()` (BUG-2401) | inherited `create` R1–R3 |

## Gap log
- G1 (payment_transaction.cases.md gap 1) — Fact — inherited `create` R1: the three times are three separate `utcnow()` calls, not one value; no equality card (equal here only because of the Windows clock's ~15 ms tick, checked 2026-11-10); the defaults cannot be patched by module name.
- G2 (payment_transaction.cases.md gap 2) — Fact — new inherited `create` R1b + Errors row: 13 integer digits fit, 14 (including `…999.995` after rounding) fail with `DataError` 22003 at flush; verified on `marker_test`.
- G3 (payment_transaction.cases.md gap 3) — Test mechanics / owner — `get_stuck_initiated` R7 now says the selection is by status alone and the cards stay status-only; R7 is deferred to the payment portal (OQ-25, owner 2026-11-10), so no split by `outcome_verified` is due.
