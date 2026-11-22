# Spec — `app/services/invoice_payment_service.py`

> **Status:** APPROVED (2026-11-21; fill-gaps 2026-11-21: 6 gaps closed, see Gap log; everything decided by Claude under the reviewer's delegation (2026-11-21); **OQ-IP-1** answered by the owner as **OQ-61** (2026-11-21): option A, a one-time code per payment form → 🐞 BUG-3002, `create_payment` R9–R9e)
> **Source commit:** e48a092

> **Form.** As `tests/unit/services/department_service.spec.md` / `account_tag_service.spec.md`. Held to the **Transaction contract TC1–TC6** of `tests/unit/services/base_service.spec.md`, with the departures stated per callable (the writes return a response schema, not the row; `delete_payment` re-reads nothing). Below it: `tests/unit/managers/invoice_payment_manager.spec.md` (APPROVED) and `tests/unit/dao/invoice_payment.spec.md` (APPROVED). **The manager's rules are not repeated here**: every refusal, lock, recompute, audit row, invoice event and order sync is the manager's and is cited by rule. This spec adds only what the service does: the commit / rollback, the creator-name read, the two 404s it raises itself, and the parameters it must pass through for the manager's fixes.
>
> **Routed here and written as rules:** invoice payment DAO **FU-1** (the creator-name re-read and the redundant pre-read in `delete_payment`) → `_payment_response` R1–R3, `delete_payment` R1–R3. Manager bugs whose fix needs this service: **BUG-603** (IP address / user agent passed endpoint → service → manager; per BUG-140) → `create_payment` R6, `void_payment` R5; **BUG-607** (`update_payment` gains `user_id`) → `update_payment` R4; **BUG-609** (payments are never deleted) → `delete_payment` R2. No new bug ID is needed for any of these: the fix is the same fix, it only has to cross this layer.
>
> **Standing decisions applied here (not asked again):** owner O1 / F7 (2026-11-14, "Invoice lock after completion"): payments may still be recorded and voided on an invoice whose order is completed — nothing here checks the order (`account_invoice_manager.spec.md` F7). Voiding is the only way to reverse a payment (BUG-609). Payments have no soft delete; voided is a visible state (manager Overview notes). HR-16: another workspace's payment or invoice is "not found".
>
> **Verified by running** (`v1_ips.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1desc\invoice_payment_service\`, one outer transaction on `marker_test`, rolled back; session as the unit-test `db` fixture; nothing persisted): `create_payment` returns `InvoicePaymentResponse` with `created_by_name` = the recorder's profile name and DB-set `created_at`, emits one `SELECT … FROM account_invoices … FOR UPDATE`, and survives a test-level `db.rollback()` (invoice `paid_amount` 100.00 too); `get_payment` / `update_payment` / `delete_payment` with another workspace → 404 `Payment with ID {id} not found`; `list_payments_by_invoice` with another workspace → 404 `Invoice with ID {id} not found`; a different amount on update → 400 `Cannot change payment amount. Delete and re-create payment instead.`; an overpayment → 400 and a **flushed, uncommitted** account added before the call was gone afterwards (TC3); `void_payment` → `is_voided` true, `void_note` stored, `created_by_name` = the **recorder's** name (not the voider's), persisted through a test rollback, invoice back to 0.00 / `unpaid`; a second void → 400 `Payment is already voided`; a voided payment's notes are editable today (BUG-606); `delete_payment` today removes the row, commits, and returns the payment as it was (all fields readable after the commit), invoice `paid_amount` recomputed; a draft invoice → 400 `Payments can only be recorded against confirmed invoices (current status: 'draft').`

## Review
> All decided 2026-11-21: P1–P3, Q1, Q2 by Claude under the reviewer's delegation (2026-11-21); Q3 by the owner (OQ-61, 2026-11-21).

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | The service cannot pass the caller's IP / browser to the payment audit rows | bug — per BUG-603 (same fix, crosses this layer) | precedent (BUG-140 / BUG-603) |
| P2 | An edit of a payment cannot say who made it | bug — per BUG-607 (same fix, crosses this layer) | precedent (BUG-607) |
| P3 | `DELETE` erases a payment and answers 200 | bug — per BUG-609 (same fix; the service answers 404 or 400 only) | precedent (BUG-609) |
| Q1 | The creator-name re-read has a "not found" fallback that cannot happen | intended — defensive, kept; no case | delegation |
| Q2 | `delete_payment` reads the payment itself before the manager does | intended — keeps the 404, harmless | delegation |
| Q3 | **OWNER (OQ-IP-1 = OQ-61)** — sending the same payment twice (double click, retry after a timeout) records it twice | bug — option A, idempotency key → 🐞 BUG-3002 | owner (2026-11-21) |

### House-rule violations — applied automatically
None in this file. The house-rule violations reached through it are the manager's and DAO's, cited, one pass-through case each: **BUG-600** (HR-6, list order), **BUG-601** (HR-10, void lock), **BUG-2400** (`created_at` on the database clock, DAO).

Checked and **not** violated here: **HR-1, HR-3** — no names (void reason trimming is BUG-605, schema). **HR-2** — no uniqueness. **HR-4** — no soft delete on payments or invoices. **HR-5, HR-7** — `skip`/`limit` are passed to the DAO, which pages after filtering; `limit ≥ 1` is enforced by the endpoint (`Query(100, ge=1, le=1000)`). **HR-8** — no search. **HR-9** — no "last changed by" column on payments (BUG-607 adds an audit row, not a stamp). **HR-10** — the service takes no lock itself; `create_payment`'s invoice lock (manager R2) is held until this service's commit or rollback. **HR-11 … HR-14** — no external system. **HR-15** — the service rounds nothing (amount precision is BUG-604, schema). **HR-16** — every read is by the caller's workspace; another workspace's id is 404, identical to an unknown one (verified).

**Permission checks:** none in the service. Every endpoint needs only a workspace member (`get_current_workspace`); create, void and delete also take `get_current_active_user`; `PUT` takes no user at all (BUG-607 adds it). Any member may record, edit and void any payment. See the report's permissions note.

### Precedent matches — confirmed (ok)

### P1. The service cannot pass the caller's IP address or browser to the audit rows — 🐞 BUG-603 (existing)
**Background:** recording and voiding a payment each write a financial audit row, which has `ip_address` and `user_agent` columns. BUG-140 / BUG-603 decided they must be filled, passed endpoint → service → manager.
**What happens today:** `create_payment` and `void_payment` here take no such parameters, so the manager can never receive them; both columns are always empty.
**Example:** a user voids payment 12 from a browser; the audit row for that void has no IP and no browser, so nobody can tell later where it came from.
**Rules affected:** `create_payment` R6, `void_payment` R5
**Answer:** bug — per BUG-603 precedent: `create_payment` and `void_payment` gain `ip_address: str | None = None` and `user_agent: str | None = None` and pass them to the manager unchanged (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** 🐞 BUG-603 (pattern `flag-unreachable-from-api`; no new ID — the same fix crossing this layer). Rules: `create_payment` R6, `void_payment` R5.

### P2. An edit of a payment cannot say who made it — 🐞 BUG-607 (existing)
**Background:** BUG-607 decided that a real edit of a payment writes an audit row and an invoice event naming the editor; the manager's `update_payment` gains a required `user_id`.
**What happens today:** the service's `update_payment` has no `user_id`, and the `PUT` endpoint does not even look up the current user.
**Example:** a user changes payment 12's cheque number; there is no way for the service to tell the manager who did it.
**Rules affected:** `update_payment` R4
**Answer:** bug — per BUG-607: the service's `update_payment` gains a required `user_id` and passes it to the manager (the endpoint passes `current_user.id`) (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** 🐞 BUG-607 (pattern `update-without-audit-trail`; no new ID). Rules: `update_payment` R4.

### P3. `DELETE` erases a payment and answers 200 — 🐞 BUG-609 (existing)
**Background:** BUG-609 decided payments are accounting records and are never hard-deleted; the manager refuses every delete with 400 "Payments cannot be deleted — void them instead".
**What happens today:** the service removes the payment through the manager, commits, and answers 200 with the payment as it was.
**Example:** invoice 40 (10,000.00 taka) has a 4,000.00 bank transfer; `DELETE /invoice-payments/{id}/` answers 200, the payment is gone and the invoice is back to unpaid.
**Rules affected:** `delete_payment` R2, R3
**Answer:** bug — per BUG-609: after the 404 check the service passes on the manager's 400 and rolls back; nothing changes, nothing is returned (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** 🐞 BUG-609 (pattern `hard-delete-of-immutable-record`; no new ID). Rules: `delete_payment` R2, R3.

### New questions

### Q1. The creator-name re-read has a "not found" fallback that cannot happen — ✅ intended
**Background:** after each successful write the service reads the payment again, joined to the recorder's profile, only to put the recorder's name on the response. If that read finds nothing, it answers with no name instead of failing.
**What happens today:** the read always finds the payment: it was just written, or just found, in the same workspace. The fallback never runs through any public method.
**Example:** a user records a payment; the answer always carries their name (or none, if their profile has no name).
**Rules affected:** `_payment_response` R2
**Answer:** intended — a defensive fallback, kept; the case designer does not need a case for it, since it is reachable only by breaking a first-party DAO (decided by Claude under the reviewer's delegation (2026-11-21))

### Q2. `delete_payment` reads the payment itself before the manager does — ✅ intended
**Background:** the service looks the payment up (with the recorder's name) before calling the manager, which looks it up again. Once BUG-609 lands the manager always refuses, so the service's read only produces the 404.
**What happens today:** a missing or other-workspace id gets the service's 404; the manager's identical 404 is never reached.
**Example:** `DELETE /invoice-payments/999/` → 404 `Payment with ID 999 not found` either way.
**Rules affected:** `delete_payment` R1
**Answer:** intended — same message as the manager's, harmless; whether to drop the read is a clean-up for whoever fixes BUG-609 (decided by Claude under the reviewer's delegation (2026-11-21))

### Q3. **OWNER (OQ-IP-1 = OQ-61)** — The same payment sent twice is recorded twice — 🐞 BUG-3002
**Background:** recording a payment is one request. Nothing in the request identifies "this one payment I am entering": no key, no reference that must be unique. The only guard is that the total may not go above what the invoice still owes. If the answer to a request is lost (slow network, a timeout, the user clicks "Save" twice, the browser retries), the user cannot tell whether it was saved. Payments cannot be deleted (BUG-609); a wrong one must be voided by hand.
**What happens today:** two identical requests make two payments, as long as the second still fits in what is owed. The invoice's paid amount and status move twice, the linked order may be marked paid, two audit rows and two "Payment recorded" entries are written.
**Example:** invoice 40 is for 10,000.00 taka. The accountant records a 4,000.00 cash payment; the network stalls and they press "Save" again. Two payments of 4,000.00 are saved: the invoice shows 8,000.00 paid and 2,000.00 still owed, although only 4,000.00 was received. Someone has to notice and void one.
**Rules affected:** `create_payment` R9
**Answer:** bug — option A (owner, OQ-61 in `docs/testing/owner-questions.md`, 2026-11-21): a one-time code per payment form — a client idempotency key plus a unique index. Sending the same form twice keeps only the first payment; two separate forms are both kept. The same pattern applies to starting a gateway checkout and to the future subscription portal.
**Resolution:** 🐞 BUG-3002 (pattern `missing-idempotency-key`, shared with BUG-3023). Rules: `create_payment` R9 (no key — today's behaviour, kept), R9a–R9i (the key). **2026-11-21 (fill-gaps):** the caller is part of the key's identity — another member reusing a key gets 409, as BUG-3023 (coordinator decision); "same body" is a normalised fingerprint (R9f); replay rolls back (R9h). The fix spans the endpoint (header), the schema / model / Alembic migration (column + partial unique index), the manager (`create_payment` looks up the key under the invoice lock and stores it) and this service (parameter; `IntegrityError` on the index → replay or 409). The intended behaviour, as recommended to the owner:
**Intended (option A):** bug — `POST /invoice-payments/` accepts an optional `Idempotency-Key` header (1–100 characters). The key is stored on the payment with a unique index on `(workspace_id, idempotency_key)` over non-null keys. A repeat of the same key with the same body returns the first payment (same id, same response, status 201) and writes nothing; the same key with a different body → 409 `This idempotency key was already used for a different payment`. A lost race on the unique index surfaces as the first payment or 409, never 500. No key → today's behaviour. The web app sends a fresh key per "Save" form. *(Requires a new column, index, header and service parameter — the same pattern the SSLCommerz portal needs for its checkout.)*
**Option texts for the owner:**
- **A — a "receipt number" for every Save (recommended).** Each time someone opens the payment form, the app gives that form a hidden one-time code. If the same form is sent twice — a double click, a slow network, a retry — the server sees the same code and keeps only the first payment. Example: the accountant enters a 4,000.00 taka cash payment against a 10,000.00 taka invoice and clicks Save twice; only one 4,000.00 payment is saved, the invoice shows 4,000.00 paid and 6,000.00 owed. Two genuinely separate 4,000.00 payments entered through two separate forms are still both saved. This is also how the online subscription payments will work.
- **B — refuse a payment that looks like a recent copy.** The server refuses a payment with the same invoice, amount, date, method and reference as one saved in the last few minutes, saying it looks like a duplicate; the user can confirm to save it anyway. Example: a 4,000.00 taka payment saved twice within a minute — the second is refused with "looks like a duplicate". But if a customer really pays two instalments of 4,000.00 taka in cash on the same day, the second one needs an extra confirmation, and two people entering the same payment ten minutes apart are not caught.
- **C — keep it as it is.** Every Save is a new payment. Example: a double click on a 4,000.00 taka payment saves 8,000.00 taka against the invoice; someone must spot it and void one payment by hand. The total can never go above what the invoice owes, so a duplicate on a nearly-paid invoice is refused, but on a mostly-unpaid one it goes through.

## Overview
`InvoicePaymentService` is the transaction boundary for the individual payments recorded against account invoices (payables and receivables). It is called only by `app/api/v1/endpoints/invoice_payments.py` (`/invoice-payments/…`). Each write calls one `InvoicePaymentManager` method, commits, re-reads the payment with its recorder's name, and returns an `InvoicePaymentResponse`; any exception rolls everything back and is passed on unchanged. Reads never commit or roll back. The invariants it protects are the manager's (payments only on confirmed, unlocked invoices; never above what is owed; invoice totals equal to the non-voided payments; payments are voided, never removed): the service's job is that each of those changes is saved **whole or not at all**, together with its audit row, invoice event and linked-order sync.

**Callables:** 8 specified · 2 not specified
**Externals to mock:** none in this file. The manager's `utcnow` (void time, audit `performed_at`) — patch as the manager spec's notes say when a test asserts it. No email, notification, gateway or Cloudinary call is made.
**Integration-only behavior:** the real two-connection race on the invoice row lock (manager `create_payment` R2, `void_payment` R9 / BUG-601), and the double-submit race on one idempotency key (BUG-3002, `create_payment` R9e). HTTP-level: the endpoint's 201 / 200 codes, `limit` bounds, and which endpoint passes `current_user`.

**Notes for the test designer**
- Session and commits: as `department_service.spec.md` Notes and `base_service.spec.md`. Under the `db` fixture `commit()` only releases a savepoint. "Committed" = still there after a test-level `db.rollback()`; "nothing saved" = re-select finds nothing / unchanged. On error paths build the setup and `db.commit()` it first, or the service's rollback discards the setup too (TC3, verified).
- Fixtures (no factory exists beyond workspace / profile / plan): `Account(workspace_id, name)`; `AccountInvoice(workspace_id, account_id, invoice_type="payable", invoice_status="confirmed", invoice_amount=Decimal("1000.00"), paid_amount=Decimal("0"), invoice_date=…)`; profiles via `make_profile(db)` (its `name` is `User <n>`).
- TC4 / TC5: `patch.object(db, "commit", side_effect=RuntimeError("boom"))` / `patch.object(db, "refresh", side_effect=RuntimeError("boom"))`. `delete_payment` calls no `refresh`, so it has no TC5 case.
- Pass-through cases: one per manager / DAO bug reached, xfail exactly as in `tests/unit/managers/invoice_payment_manager.cases.md` (strict unless the manager's card says otherwise). Do not re-test the manager's edge cases here.
- New parameters (BUG-603 `ip_address`/`user_agent`, BUG-607 `user_id` on `update_payment`, BUG-3002 `idempotency_key` on `create_payment`) do not exist today: calling with them raises `TypeError` → strict xfail. Assert the outcome in the database (the audit row's columns), not the call.
- The lock is observed as in the manager spec: a `before_cursor_execute` listener on the test connection; `create_payment` emits `SELECT … FROM account_invoices … FOR UPDATE` (verified).
- The service holds its manager as `self.invoice_payment_manager` (set in `__init__` to the module singleton `invoice_payment_manager`) — patch that attribute on the service instance for the index-race simulation (R9e).
- Fingerprint (R9f): compute the expected value in the test with `hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()`; `profile_id`, `invoice_id` are JSON integers, every other value a string or `null`.
- Index (R9g): assert with `SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_invoice_payments_workspace_idempotency_key'`, equal to the text in R9g.
- `invoice_payments.created_at` is the database's local clock today (BUG-2400) — never assert it exactly; assert it is not `None` on the response (TC2).

## Not specified
- `InvoicePaymentService.__init__` — wires the manager singleton, no logic.
- `invoice_payment_service` — module singleton.

---

## `to_payment_response(payment, created_by_name=None)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** internal (used by: `_payment_response`, `get_payment`, `list_payments_by_invoice`, `delete_payment`)

**Purpose:** Turn a payment row and its recorder's name into the API response.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `payment` | `InvoicePayment` | any loaded payment row (voided or not) |
| `created_by_name` | `str \| None` | the recorder's display name; default `None` |

**Returns:** `InvoicePaymentResponse`.

**Rules:**
- **M1.** The response carries every column of the payment — `id`, `workspace_id`, `invoice_id`, `payment_amount`, `payment_date`, `payment_method`, `payment_reference`, `bank_name`, `transaction_id`, `notes`, `is_voided`, `voided_at`, `voided_by`, `void_note`, `created_at`, `created_by` — with the stored values, plus `created_by_name` = the argument (`None` when not given).
- **M2.** A stored row that the response schema refuses (e.g. a `payment_amount` of `0.00` or below, possible only by writing the database directly — DAO FU-2; or a `payment_method` over 50 characters, impossible through the column) raises `pydantic.ValidationError`. *(The response inherits the input limits of `InvoicePaymentBase`; no API path stores such a row, so no case beyond the `0.00` one is needed.)*

**Errors:** `pydantic.ValidationError` per M2. **Side effects:** none.

---

## `InvoicePaymentService._payment_response(db, payment, workspace_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `create_payment`, `update_payment`, `void_payment`)

**Purpose:** Build the response for a payment just written, with its recorder's name.

**Returns:** `InvoicePaymentResponse`.

**Rules:**
- **R1.** The payment is looked up again by its id within `workspace_id`, joined to the recorder's profile; the response is the **passed-in** payment object (M1) with `created_by_name` = that profile's `name` — `None` when `created_by` is null or the profile has no name (DAO `get_by_id_and_workspace_with_creator` R1, `get_by_invoice` R2). The name is always the **recorder's**, also after a void (the voider appears only as `voided_by`).
- **R2.** If that lookup finds nothing, the response is built with `created_by_name = None` and no error. Unreachable through the public methods (Q1, intended; no case).
- **R3.** It takes no lock and writes nothing.

**Errors:** none of its own. **Side effects:** one read.

---

## `InvoicePaymentService.create_payment(db, payment_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /invoice-payments/`, 201)

**Purpose:** Record a payment against a confirmed invoice and save it together with everything the manager updates.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `payment_in` | `InvoicePaymentCreate` | as manager `create_payment` Inputs (`payment_amount > 0`; BUG-604 precision limit) |
| `workspace_id` | int | caller's workspace |
| `user_id` | int | recorder (`created_by`) |
| `ip_address`, `user_agent` | `str \| None`, default `None` | [BUG-603] see R6. *(Requires new parameters — today not accepted.)* |
| `idempotency_key` | `str \| None`, default `None` | [BUG-3002] from the `Idempotency-Key` request header; 1–100 characters, compared exactly (no trimming, case-sensitive); `None` = no key. See R9–R9i (format: R9i). *(Requires a new parameter, header, column and index — today not accepted.)* |

**Returns:** `InvoicePaymentResponse` of the new payment, committed, re-read (TC2): `id` and the database-set `created_at` are filled; `created_by_name` per `_payment_response` R1.

**Rules:**
- **R1.** On success the payment, the invoice's new `paid_amount` / `payment_status`, the financial audit row, the `payment_recorded` invoice event and any linked order / return `paid` change (manager `create_payment` R6–R13) are **all** committed: each survives a later rollback of the session (TC1).
- **R2.** The returned object is an `InvoicePaymentResponse`, not the ORM row, built after the commit and re-read (TC2 in this form): `created_at` is not `None`; `created_by` = `user_id`; `created_by_name` = that user's profile name; `is_voided` false.
- **R3.** Every refusal of the manager reaches the caller as the same exception (TC3): 404 `Invoice with ID {id} not found` (unknown or another workspace's invoice, HR-16), 400 not confirmed, 403 payments locked, 400 above what is owed (manager `create_payment` R1, R3–R5). Nothing is saved — no payment, no invoice change, no audit row, no event — and every other uncommitted change pending in the session is discarded too (verified).
- **R4.** A commit that fails rolls back and passes the commit's exception on; nothing saved (TC4). A re-read that fails after the commit passes its exception on, and the payment **stays saved** (TC5) — the caller sees an error for a payment that was recorded; a retry with the same idempotency key then gets that payment back (R9b).
- **R5.** The invoice row lock taken by the manager (`create_payment` R2) is held until this method's commit or rollback, so a second payment on the same invoice waits until the first is saved or undone, then sees the new `paid_amount`. *(The real race is integration-only; in a unit test observe the `FOR UPDATE` statement.)*
- **R6.** [BUG-603] The caller's `ip_address` and `user_agent` are passed to the manager unchanged and end up on the payment's `created` audit row (manager `create_payment` R10a); `None` when not given. *(Today: the method has no such parameters; both columns are always `NULL`.)*
- **R7.** A payment may be recorded on a confirmed invoice whose linked order is completed (owner O1 / F7): the order's state is not read. *(Today's behaviour, intended; one case.)* "Completed" is as `account_invoice_manager.spec.md` F1–F2: the order's own `invoice_id` points at the invoice, and — purchase order: the `statuses.name` of `current_status_id` is exactly `"Complete"`; sales order: `order_completed = True`; expense order: `completed_at IS NOT NULL`; work order: `status = "COMPLETED"`. One case with any one kind is enough (the simplest: an expense order with `invoice_id` = the invoice and `completed_at` set). *(Gap 5.)*
- **R8.** Nothing outside the database is called: no email, notification or gateway; nothing happens after the commit except the re-read.
- **R9.** Without an idempotency key (`None`), two identical calls are two payments: the second is saved like the first as long as it still fits in what is owed (manager R5); a second call that no longer fits gets the manager's 400. *(Today's behaviour, intended for calls without a key — OQ-61; today every call is in this case.)*
- **R9a.** [BUG-3002] A payment created with a key stores it, with its fingerprint (`idempotency_key` and `idempotency_fingerprint` on the payment row, R9f–R9g, committed with it). Two different keys on the same invoice make two payments, each subject to manager R5. *(Today: no key is accepted or stored.)*
- **R9b.** [BUG-3002] A second call in the same workspace with a key already stored and the **same request** — same fingerprint (R9f): same caller (`user_id`) and the same normalised `invoice_id`, `payment_amount`, `payment_date`, `payment_method`, `payment_reference`, `bank_name`, `transaction_id`, `notes` — returns the **first** payment's response — same `id`, same fields, `created_by_name` per `_payment_response` R1 — and writes nothing (R9h): no new payment, no change to the invoice's `paid_amount` / `payment_status`, no audit row, no invoice event, no order / return change, no `updated_at` change on any row. It succeeds even when the invoice is now fully paid, has `allow_payments` false, or is no longer `confirmed`, or the first payment has since been voided (the response then shows `is_voided` true): the replay reports what was recorded, it does not record again. *(Today: a second payment is saved, or the manager's 400 if it no longer fits.)* *(Revised 2026-11-21, gap 1: the caller is part of the request — coordinator decision, one rule with BUG-3023.)*
- **R9c.** [BUG-3002] The same key with a **different request** — any normalised field of R9b differs, **or another member of the workspace sends it** (the key belongs to the member who first used it) → 409 `This idempotency key was already used for a different payment`; nothing is saved, the session is rolled back (TC3). The 409 shows nothing of the first payment. *(Today: no 409 exists.)*
- **R9f.** [BUG-3002] **The fingerprint.** "Same request" is decided by comparing a fingerprint stored on the payment, never the raw text. Fingerprint = SHA-256, as 64 lowercase hex characters, of the canonical JSON (keys sorted, no spaces: `json.dumps(obj, sort_keys=True, separators=(",", ":"))`) of an object with exactly these keys: `profile_id` (the caller's `user_id`), `invoice_id`, `payment_amount` (the Decimal by value, written `format(amount.normalize(), "f")`: `400`, `400.0`, `400.00` all give `"400"`; `400.01` gives `"400.01"`), `payment_date` (ISO `YYYY-MM-DD`), and `payment_method`, `payment_reference`, `bank_name`, `transaction_id`, `notes` (each trimmed at both ends; an omitted field, `null`, `""` or whitespace-only all give JSON `null`; inner text and case kept as sent). So `400` equals `400.00`, an omitted `notes` equals `notes: null` equals `notes: "  "`, while `"Cash"` and `"cash"` differ. Stored in column `invoice_payments.idempotency_fingerprint` `String(64)`, nullable: `NULL` exactly when `idempotency_key` is `NULL`, set together with the key in R9a. The stored payment's own field values are not re-read for the comparison (a later edit of its notes through `update_payment` does not change the fingerprint). *(Decided by the coordinator, 2026-11-21, shared with BUG-3023.)*
- **R9g.** [BUG-3002] **Key column, index, lookup.** The key is stored in `invoice_payments.idempotency_key` `String(100)`, nullable. The database has the partial unique index `ix_invoice_payments_workspace_idempotency_key` — `CREATE UNIQUE INDEX ix_invoice_payments_workspace_idempotency_key ON invoice_payments (workspace_id, idempotency_key) WHERE idempotency_key IS NOT NULL` (as `pg_indexes.indexdef`: `CREATE UNIQUE INDEX ix_invoice_payments_workspace_idempotency_key ON public.invoice_payments USING btree (workspace_id, idempotency_key) WHERE (idempotency_key IS NOT NULL)`). The lookup is by `(workspace_id, idempotency_key)` exactly, voided payments included. It runs inside the manager's `create_payment` **after** the invoice row is read and locked (plain `SELECT … FROM account_invoices … FOR UPDATE`, manager R2; no join, so no `OF` clause) and **before** the status, payment-lock and amount checks (manager R3–R5) — so a replay is answered whatever the invoice's state now (R9b). The lookup itself takes no lock of its own: the invoice lock serialises calls on the same invoice, and the unique index catches the rest (R9e). Consequences: a key reused with a different `invoice_id` that does not exist (or is another workspace's) gets the manager's 404 before the lookup; with a different existing invoice it gets 409 (R9c).
- **R9h.** [BUG-3002] **A replay ends the transaction without a commit.** The response is built from the stored payment (and its recorder's name), then the service **rolls back** — nothing is committed, and the invoice lock is released. As in TC3, any other uncommitted change pending in the session before the call is discarded. No `db.refresh` failure can arise on this path (TC5 does not apply). *(Decided by Claude under the reviewer's delegation (2026-11-21): the coordinator's "a replay writes and commits nothing"; the rollback is what releases the lock.)*
- **R9i.** [BUG-3002] **Key format.** The endpoint takes the header as `Header(None, alias="Idempotency-Key", min_length=1, max_length=100)`: an empty or 101-character header → 422 before the service runs (HTTP-level, integration-only). The service does not re-check: called directly, `""` is an ordinary key (stored and replayed like any other), and a 101-character key fails on the column (`DataError`), is rolled back and reaches the caller unchanged (TC3), nothing saved. Keys are compared exactly: no trimming, case-sensitive (`"abc"` and `"ABC"` are two keys). *(Decided by Claude under the reviewer's delegation (2026-11-21); same as `payment_transaction_service` `initiate_payment` Inputs.)*
- **R9d.** [BUG-3002] Keys are per workspace: the same key used in another workspace is a different key and creates that workspace's payment normally; the reply never shows the other workspace's payment (HR-16). The database enforces it with the partial unique index of R9g, so payments without a key are never blocked.
- **R9e.** [BUG-3002] Two concurrent calls with the same key and body leave **exactly one** payment: the loser either waits on the invoice lock (manager `create_payment` R2) and then finds the key (R9b), or hits the unique index; an `IntegrityError` on `ix_invoice_payments_workspace_idempotency_key` is rolled back, the stored row is read again, and the call is answered as R9b (same fingerprint; then as R9h: nothing committed) or R9c (different fingerprint), never as 500. An `IntegrityError` on any other constraint is not translated (TC3). *(The two-connection race is integration-only; in a unit test, a payment already committed with the key plus a second call covers R9b / R9c, and a row with the key inserted directly just before the manager's write covers the index path.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| any manager refusal (R3) | the manager's `HTTPException`, unchanged | as manager `create_payment` Errors |
| commit fails | the commit's exception | — |
| re-read after commit fails | that exception (payment stays saved) | — |
| [BUG-3002] key already used with a different request (other fields, or another member) | `HTTPException` 409 | `This idempotency key was already used for a different payment` |
| [BUG-3002] key over 100 characters (direct call only) | `sqlalchemy.exc.DataError`, unchanged | — |

**Side effects:** per manager `create_payment` Side effects, then one commit; on any exception, one rollback of the whole session.

---

## `InvoicePaymentService.get_payment(db, payment_id, workspace_id)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (`GET /invoice-payments/{payment_id}/`)

**Purpose:** One payment of the workspace, with its recorder's name.

**Returns:** `InvoicePaymentResponse` (M1) with `created_by_name` per `_payment_response` R1.

**Rules:**
- **R1.** A payment of this workspace is returned, voided or not (voided ones with their void fields).
- **R2.** An unknown id, or a payment of another workspace (HR-16), → 404 `Payment with ID {payment_id} not found`. The service raises this itself; no other workspace's data is shown.
- **R3.** Neither commits nor rolls back: changes pending in the session stay pending (TC6).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| no such payment in the workspace | `HTTPException` 404 | `Payment with ID {payment_id} not found` |

**Side effects:** none.

---

## `InvoicePaymentService.list_payments_by_invoice(db, invoice_id, workspace_id, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /invoice-payments/invoice/{invoice_id}/`; the endpoint always passes `skip ≥ 0` and `1 ≤ limit ≤ 1000`)

**Purpose:** An invoice's payments, newest payment date first, each with its recorder's name.

**Returns:** list of `InvoicePaymentResponse`, in the manager's order.

**Rules:**
- **R1.** The result is the manager's list (`list_payments_by_invoice` R1–R6: 404 for an unknown or other-workspace invoice, voided payments included, order [BUG-600] `payment_date` descending then `id` descending, `skip`/`limit` after ordering), each pair mapped by M1 with its `created_by_name`. One pass-through case for BUG-600.
- **R2.** An existing invoice with no payments → `[]`.
- **R3.** Neither commits nor rolls back (TC6); the manager's 404 reaches the caller unchanged.

**Errors:** manager's 404 `Invoice with ID {invoice_id} not found`. **Side effects:** none.

---

## `InvoicePaymentService.update_payment(db, payment_id, payment_in, workspace_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (`PUT /invoice-payments/{payment_id}/`)

**Purpose:** Edit a payment's details other than its amount, and save it.

**Inputs:** `payment_id: int`, `payment_in: InvoicePaymentUpdate` (as manager `update_payment` Inputs), `workspace_id: int`; [BUG-607] `user_id: int` (R4).

**Returns:** `InvoicePaymentResponse` of the payment, committed and re-read (TC2), `created_by_name` per `_payment_response` R1.

**Rules:**
- **R1.** On success the edited fields (manager `update_payment` R4, R5 [BUG-608]) and, after BUG-607, the `updated` audit row and `payment_updated` event (manager R6a) are committed (TC1). The invoice is untouched (manager R6).
- **R2.** Every refusal of the manager reaches the caller unchanged, nothing saved, other pending changes discarded (TC3): 404 `Payment with ID {id} not found` (unknown or other workspace), 400 amount change (manager R2 / [BUG-611] message), [BUG-606] 400 `Voided payments cannot be edited` (manager R3, R3a). One pass-through case each for BUG-606, BUG-608, BUG-611.
- **R3.** TC4 and TC5 as `create_payment` R4 (a failed re-read leaves the edit saved).
- **R4.** [BUG-607] The method takes a required `user_id` (the editor) and passes it to the manager; the audit row and event of a real change name that user as `performed_by`. *(Today: no `user_id` parameter here or on the endpoint; the edit leaves no record of who made it.)*
- **R5.** An empty update `{}` still commits and returns the payment unchanged (no error).

**Errors:** the manager's `HTTPException`s, unchanged; commit / re-read exceptions per R3. **Side effects:** per manager `update_payment`; one commit, or one rollback on any exception.

---

## `InvoicePaymentService.delete_payment(db, payment_id, workspace_id, user_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (`DELETE /invoice-payments/{payment_id}/`)

**Purpose:** [BUG-609] Refuse to remove a payment — void it instead. *(Today: removes it and answers with the payment as it was.)*

**Returns:** [BUG-609] never returns normally. *(Today: an `InvoicePaymentResponse` built from the payment as read before the delete, with its recorder's name.)*

**Rules:**
- **R1.** The payment is first looked up by id within `workspace_id`, with its recorder's name. An unknown id, or another workspace's payment (HR-16), → 404 `Payment with ID {payment_id} not found` raised by the service; the session is rolled back and nothing is written (Q2, intended).
- **R2.** [BUG-609] A payment that exists — active or voided, on any invoice — gets the manager's 400 `Payments cannot be deleted — void them instead` (manager `delete_payment` R2) unchanged; the session is rolled back; the payment, the invoice's `paid_amount` / `payment_status`, the audit log, the invoice events and any linked order / return are all unchanged, and other uncommitted changes in the session are discarded (TC3). *(Today: the manager removes the payment and recomputes the invoice; the service commits that.)*
- **R3.** [BUG-609] No response is ever built: the 200 answer of today goes away. *(Today: after the commit the service answers with the payment as it was read in R1 — every field, including `id` and `created_by_name` — although the row no longer exists; verified. There is no re-read, so TC5 does not apply.)*
- **R4.** A failing commit (today's path only) rolls back and passes the exception on (TC4).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| no such payment in the workspace | `HTTPException` 404 (service) | `Payment with ID {payment_id} not found` |
| payment exists [BUG-609] | `HTTPException` 400 (manager) | `Payments cannot be deleted — void them instead` |

**Side effects:** [BUG-609] none but one rollback. *(Today: as manager `delete_payment` R2's Today note, then one commit.)*

---

## `InvoicePaymentService.void_payment(db, payment_id, workspace_id, user_id, void_note)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /invoice-payments/{payment_id}/void/`)

**Purpose:** Void a payment (kept as a record, out of the invoice's totals) and save it with everything the manager updates.

**Inputs:** `payment_id: int`, `workspace_id: int`, `user_id: int` (the voider), `void_note: str` (from `VoidPaymentRequest`; trimmed and non-blank per BUG-605, schema); [BUG-603] `ip_address`, `user_agent` (R5).

**Returns:** `InvoicePaymentResponse` of the voided payment, committed and re-read (TC2): `is_voided` true, `voided_at`, `voided_by` = `user_id`, `void_note` as sent; `created_by_name` = the **recorder's** name (`_payment_response` R1, verified).

**Rules:**
- **R1.** On success the payment's void fields, the invoice's recomputed `paid_amount` / `payment_status`, the `voided` audit row, the `payment_voided` event and any linked order / return `paid` change (manager `void_payment` R5–R14) are all committed (TC1). A payment on a confirmed invoice of a completed order can be voided (owner O1 / F7; one case; "completed" as `create_payment` R7).
- **R2.** Every refusal of the manager reaches the caller unchanged, nothing saved, other pending changes discarded (TC3): 404 `Payment with ID {id} not found` (unknown or other workspace), 400 `Payment is already voided`, 404 invoice missing (inconsistent data only).
- **R3.** TC4 and TC5 as `create_payment` R4 (a failed re-read leaves the void saved).
- **R4.** [BUG-601] The invoice row lock the manager takes is held until this method's commit or rollback; a second void of the same payment waits, then gets 400 `Payment is already voided`. One pass-through case (SQL capture, as the manager's).
- **R5.** [BUG-603] The caller's `ip_address` and `user_agent` are passed to the manager unchanged and end up on the `voided` audit row (manager `void_payment` R12); `None` when not given. *(Today: no such parameters; both columns always `NULL`.)*
- **R6.** Voiding twice is not idempotent in the "same answer" sense: the second call is a 400, not a repeat of the first answer, and writes nothing. *(Intended: a void is a decision, and the loser of a race must see the new state — HR-10. Decided by Claude under the reviewer's delegation (2026-11-21).)*
- **R7.** Nothing outside the database is called.

**Errors:** the manager's `HTTPException`s, unchanged; commit / re-read exceptions per R3. **Side effects:** per manager `void_payment`; one commit, or one rollback on any exception.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 22–23 | map row + name (schema may refuse a stored row) | M1, M2 |
| 46–48 | re-read with creator, by id + workspace | `_payment_response` R1, R3 |
| 49–50 | re-read finds nothing → no name | `_payment_response` R2 |
| 51–52 | found → recorder's name | `_payment_response` R1 |
| 61–67 | manager create (refusals, lock) | `create_payment` R1, R3, R5, R7, R9 |
| 68 | commit (fails → rollback, re-raise) | `create_payment` R1, R4 |
| 69 | refresh (fails after commit) | `create_payment` R2, R4 |
| 70 | build response | `create_payment` R2 |
| 71–73 | any exception → rollback, re-raise | `create_payment` R3, R4 |
| new parameters | `ip_address` / `user_agent` passed through [BUG-603] | `create_payment` R6, `void_payment` R5 |
| new parameter | no key → today's path | `create_payment` R9 |
| fix location [BUG-3002] | key stored / replayed / 409 / per workspace / index race | `create_payment` R9a–R9e |
| fix location [BUG-3002] | fingerprint built; lookup after invoice lock, before checks; replay → rollback; key format | `create_payment` R9f–R9i |
| 81–83 | read by id + workspace | `get_payment` R1, R3 |
| 84–88 | not found → 404 | `get_payment` R2 |
| 100–107 | manager list → map each pair | `list_payments_by_invoice` R1–R3 |
| 117–122 | manager update (refusals) | `update_payment` R1, R2, R5 |
| new parameter | `user_id` passed through [BUG-607] | `update_payment` R4 |
| 123–125 | commit, refresh, response | `update_payment` R1, R3 |
| 126–128 | exception → rollback, re-raise | `update_payment` R2, R3 |
| 138–140 | pre-read by id + workspace | `delete_payment` R1 |
| 141–145 | not found → 404 | `delete_payment` R1 |
| 147–152 | manager delete (refused per BUG-609) | `delete_payment` R2 |
| 153 | commit (today's path) | `delete_payment` R3, R4 |
| 154 | response from the pre-read (today) | `delete_payment` R3 |
| 155–157 | exception → rollback, re-raise | `delete_payment` R1, R2, R4 |
| 168–174 | manager void (refusals, lock) | `void_payment` R1, R2, R4, R6 |
| 175–177 | commit, refresh, response | `void_payment` R1, R3 |
| 178–180 | exception → rollback, re-raise | `void_payment` R2, R3 |

## Gap log
- G1 (`invoice_payment_service.cases.md` gap 1) — contradiction (with BUG-3023) — coordinator decision: the caller's profile id is part of the request; `create_payment` R9b, R9c rewritten (another member → 409), fingerprint R9f added. Cards: K-05 becomes a 409 card (another member, same key and body → 409, nothing written, first payment unchanged); new card: same member, same key and body → replay.
- G2 (gap 2) — intent, decided by the coordinator — normalised comparison and the fingerprint's exact form, column `idempotency_fingerprint` `String(64)` NULL iff no key: `create_payment` R9f. New cards: `400` then `400.00` → replay; `notes` omitted then `"  "` → replay; `"Cash"` then `"cash"` → 409; stored fingerprint equals the expected SHA-256; a later notes edit does not change it.
- G3 (gap 3) — intent, decided under delegation — endpoint enforces 1–100 (422, integration-only); service does not re-check: `""` is an ordinary key, 101 characters → `DataError` rolled back: `create_payment` R9i, Errors row. New cards: direct `""` key stored and replayed; 101-character key → `DataError`, nothing saved; `"abc"` vs `"ABC"` → two payments.
- G4 (gap 4) — intent, decided (coordinator + delegation) — a replay commits nothing and ends with a rollback (lock released, other pending changes discarded): `create_payment` R9h. Cards K-04 … K-08 gain an X: a flushed, uncommitted row added before the call is gone afterwards, and `commit` is not called (patch with a wrapper that counts).
- G5 (gap 5) — fact — "completed" per kind from `account_invoice_manager.spec.md` F1–F2: `create_payment` R7, `void_payment` R1. Cards C-03 and V-03: set the linked order completed (expense order, `completed_at` set, its `invoice_id` = the invoice).
- G6 (gap 6) — fact / test mechanics — manager attribute `self.invoice_payment_manager`; index name and `indexdef` text; lookup placement after the plain invoice `FOR UPDATE` and before manager R3–R5: Notes, `create_payment` R9g. K-33 checks the full `indexdef`; new card: replay on an invoice now `allow_payments` false / fully paid / voided-payment → still replay (lookup before checks); new card: key reused with an unknown `invoice_id` → 404.
