# Execution notes — `app/managers/invoice_payment_manager.py`

> Cases: `tests/unit/managers/invoice_payment_manager.cases.md` (revision 5) · Tests: `tests/unit/managers/test_invoice_payment_manager.py` · Source commit: e48a092
> Result: 95 passed · 23 xfailed · 0 discrepancies · 0 errors — branch coverage 94% (3 of 52 branches missed)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_invoice_payment_manager.py -q -p no:cacheprovider --cov=app.managers.invoice_payment_manager --cov-branch --cov-report=term-missing`

This file implements all 117 cases of revision 4. The `create_payment` section
(CP-01..CP-29, 29 cases) was already present from an earlier run of this same
task and was left unchanged; this pass added `update_payment` (UP-01..UP-24),
`list_payments_by_invoice` (LP-01..LP-15), `delete_payment` (DP-01..DP-05),
`void_payment` (VP-01..VP-24) and `_sync_linked_order` (SY-01..SY-20) — 88
cases — then ran the whole file and reconciled.

## How the tests are built

**Time (Conventions "Time", NOW/T0).** A single autouse fixture `_frozen_time`
patches `app.utils.time.datetime` with a `_FrozenDatetime` subclass whose
`.now()` returns NOW; this is the one external the spec's Overview lists, and
it freezes `voided_at`, the audit logger's `performed_at`, and the
`invoice_events.created_at` column default all at once (all three resolve
`datetime.now()`/`utcnow()` from `app.utils.time` at call time — see spec G6).

**Actors/rows (W1/W2, U1/U2/U3, INV, PAY, PO/SO/PR/SR).** Local builders
`mk_account`, `mk_inv`, `mk_pay`/`mk_pa`, `mk_po`/`mk_so`/`mk_por`/`mk_sor`
insert rows directly with the Conventions-section defaults, one flush per row.
`reload_inv` gives a fresh `AccountInvoice` for the `_sync_linked_order` cases'
"I1 re-loaded from the DB" requirement. `reread` expires the session and
returns the same ORM objects re-queried. `d0()` builds the default
`InvoicePaymentCreate`; `build_update(**fields)` builds an `InvoicePaymentUpdate`
with exactly the given keys "set" (pydantic's `exclude_unset` tracks this, so
an explicit `None` still counts as set); `upd()` is the signature-adaptive
wrapper the cases file specifies for `update_payment`'s not-yet-added
`user_id` parameter (mirrors `po_return_inventory`'s approach per the spec).

**U3 substitution (cases.md revision 4).** `profiles.name` is `NOT NULL` in
the baseline schema, so the spec's "profile whose name is NULL" for U3 is
infeasible; the cases file already substitutes a normally-named U3 ("Nusrat
Jahan") and changes LP-01's expected name at that position from `None` to
U3's name (best-practice default, delegated by reviewer — recorded in the
cases file itself, not re-decided here).

**BUG-600 setup (LP-09/LP-10).** `reserve_payment_ids(db, n)` calls
`nextval('invoice_payments_id_seq')` n times without inserting rows, giving
ascending ids `a < b < c`; the test then inserts same-date rows with explicit
`id=` in order `c, a, b` so insertion order differs from the intended `id
desc` tie-break, per spec G7.

**Row locks (SQLCapture) and the void race (VoidRace).** `SQLCapture` is a
`before_cursor_execute` listener on the shared `engine` fixture recording every
statement run during the action (installed inside the `with` block, so setup
SQL is excluded); `locks_invoice()` checks for a captured `account_invoices`
`SELECT ... FOR UPDATE`, `selects_payment_after_lock()` checks a later
`invoice_payments` statement. `VoidRace` (VP-19 only) is the same kind of
listener: the first time it sees an `account_invoices ... FOR UPDATE`
statement on the connection, it runs a raw `UPDATE invoice_payments SET
is_voided = true, ...` through the same DBAPI connection first — simulating
the losing side of a concurrent void. Per the cases file's note (and
confirmed here), today's `void_payment` takes no lock at all, so in VP-18/VP-19
the hook's trigger condition is never met and the simulated race never fires;
both are xfail for that reason, exactly as designed.

**Database-error / N0 cases.** None of this module's passing cases hit a raw
`IntegrityError`/`DataError`, so no case here needs `db.begin_nested()`; "N0"
(nothing written) is checked with direct re-reads/re-queries instead
(`pay_snapshot`, `inv_snapshot`, `payment_exists`, `audit_rows`, `events_of`,
`po_events`, `so_events`).

**Audit snapshot money (Conventions "Audit snapshot values").** `money(v)`
wraps `Decimal(str(v))` so a numeric comparison passes whether
`extract_relevant_fields` produced a float (today, BUG-141) or a fixed-point
string (after that fix) — used for `changes["after"]["payment_amount"]` /
`changes["payment_voided"]["payment_amount"]`.

## Revision history

**Revision 5b (batch mode, verifier Finding 5).** Completed N0 assertions: VP-09 (snapshots of I1's PA/PB), VP-10 (full PA snapshot plus active PB unchanged), VP-11 (full `pay_snapshot(PI)`), and `so_events(db) == []` in DP-01, DP-02, DP-05. No expectation changed; result unchanged (95 passed, 23 xfailed).

**Revision 5 (this pass, batch mode).** Cases revision 5 added VP-25 (verify.md
Finding 1: pins `void_payment` R7's lower boundary — remaining active total
0.01 → `partial`, catching the `> 0` → `> 1` mutant). Added
`test_ipm_vp_25__remaining_total_just_above_zero_stays_partial` right after
VP-24, following the `mk_vp_default`-style setup the row specifies (I1
`paid_amount=250.01`/`partial`; PA active 250.00; PB active 0.01; default call
voids PA). Also applied verify.md Finding 3 (routed to the executor): the
listed cases checked only part of the Conventions "Nothing written (N0)"
definition. Each of CP-09, CP-10, CP-13..CP-18, UP-04, UP-07, UP-08, UP-09,
UP-23, UP-24, DP-01, DP-02, DP-04, DP-05, VP-08, VP-09, VP-10, VP-11 now
asserts the full N0 set it was missing: a before/after `pay_snapshot`/
`inv_snapshot` equality (not just the one or two fields previously checked),
`audit_rows(db) == []`, and `events_of(db, <invoice>.id) == []`; DP-01, DP-02
and DP-04/05's mk_dp_default setup also gained `po1.paid is False` +
`po_events(db) == []`. No existing assertion was removed or weakened — only
added to. Re-checked verify.md Findings 2 (`_sync_linked_order`'s `user_id`/
`performed_by`) and 4 (SY po_events/so_events pairing and setup PO1 re-reads)
against the file this pass started from: every SY test already called
`_sync_linked_order(..., user_id=u1.id)` and already asserted both
`po_events(db)` and `so_events(db)` (and re-read `po1` where relevant) — no
change was needed for those two findings.

## Discrepancies
None. Every case ended exactly as designed: 95 of 95 `pass`-designed cases
passed, 23 of 23 `xfail`-designed cases xfailed (strict), 0 cases flipped
outcome, 0 XPASS. Ran 3x to confirm no flakiness (same 95/23 split each time,
~5.0-5.4s).

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 227–237 | dead | `InvoicePaymentManager.get_payment` — reviewer decision (spec Q6): no caller in `app/` or `tests/`, logged to `invoice_payment_manager.deadcode-staging.md` as dead code to remove. Not specified in the spec's testable surface, so never called from this file. |
| 310 | unreachable | `delete_payment`'s old (today, pre-BUG-609) "invoice not found" branch — reachable only with inconsistent data (a payment whose `invoice_id` points at a row that no longer exists), since the payment's FK otherwise guarantees the invoice exists. The spec explicitly says not to design cases around the old recompute mechanics (Overview note, Q4 resolution), so none of DP-01..DP-05 construct that inconsistent state. |
| 330, 332 | spec-gap (by design) | `delete_payment`'s old (today) recompute branches setting `payment_status` to `'paid'` / `'partial'` after a hard delete. All three DP-03/04/05 cases do run this superseded body today (since no exception is ever raised, `delete_payment` falls through its entire old implementation before the `pytest.raises` assertion fails) — but each case's setup leaves exactly 0 remaining active payments after the delete, so the recompute always lands on the `else: 'unpaid'` branch. Reaching `'paid'`/`'partial'` would need a second active payment to survive the delete, which the spec instructs not to test ("the old recompute/audit mechanics … are not tested, as the spec instructs" — Reviewer summary; Overview note under "Once BUG-609 lands … Do not design cases around the old recompute/audit mechanics"). Not closed here on purpose; no case added beyond the 5 the cases file specifies. |

## Factories added
None. `tests/unit/factories.py` was not touched (batch mode). All of this
module's own rows (`Account`, `AccountInvoice`, `InvoicePayment`, `Status`,
`Factory`, `PurchaseOrder`, `SalesOrder`, `PurchaseOrderReturn`,
`SalesOrderReturn`) are built with local helpers in the test file
(`mk_account`, `mk_inv`, `mk_pay`/`mk_pa`, `mk_status`, `mk_factory`, `mk_po`,
`mk_so`, `mk_por`, `mk_sor`).

**Worth promoting later** (used identically by at least this module's six
sections, and likely reusable by `account_invoice_manager`,
`purchase_order_manager`, and `sales_manager` test files, which already have
their own near-duplicate local versions per their own notes):
- `mk_account(db, ws, name, **overrides)` — minimal `Account` row.
- `mk_status(db, ws)` / `mk_factory(db, ws)` — minimal `Status` / `Factory`
  rows, needed only to satisfy `PurchaseOrder.current_status_id` /
  `SalesOrder.current_status_id` / `.factory_id` NOT NULL FKs.
- `mk_po(db, ws, created_by_id, **overrides)` / `mk_so(...)` — minimal
  `PurchaseOrder` / `SalesOrder` rows with sane defaults for every NOT NULL
  column (`po_number`/`sales_order_number` from a counter, `destination_type`,
  `account_id`, `factory_id`, `current_status_id`).

## Notes for maintainers

- **Ordering assumption (LP-09/LP-10).** `reserve_payment_ids` depends on the
  Postgres identity sequence being named `invoice_payments_id_seq` (confirmed
  via `pg_get_serial_sequence('invoice_payments', 'id')` on the test
  database). If that sequence is ever renamed in a migration, these two tests'
  setup breaks at the `nextval` call, not silently.
- **When BUG-600 is fixed** (`list_payments_by_invoice` ordered `payment_date
  desc, id desc`): LP-09/LP-10's `xfail(strict=True)` will XPASS — remove the
  marker on both.
- **When BUG-601 is fixed** (`void_payment` takes `FOR UPDATE`): VP-18, VP-19,
  VP-24 will XPASS — remove the markers. VP-19's `VoidRace` hook will then
  actually fire (today it never does, since no lock statement is ever
  captured), so re-verify its assertions still hold once the lock lands.
- **When BUG-603 is fixed** (`ip_address`/`user_agent` added to
  `create_payment`/`void_payment`): CP-24 and VP-16 will XPASS.
- **When BUG-604 is fixed** (decimal/digit-cap validation on
  `InvoicePaymentCreate`/`InvoicePaymentUpdate.payment_amount`): CP-26, CP-29,
  UP-21 will XPASS.
- **When BUG-605 is fixed** (`VoidPaymentRequest.void_note` stripped/rejected
  blank-after-strip): VP-20, VP-21 will XPASS.
- **When BUG-606 is fixed** (`update_payment` rejects editing a voided
  payment): UP-09, UP-24 will XPASS.
- **When BUG-607 is fixed** (`update_payment` gains `user_id` and audits real
  changes): UP-17, UP-18, UP-19 will XPASS. Note the `upd()` wrapper already
  passes `user_id` once `update_payment`'s signature gains that parameter, so
  no test-file change is needed for that part of the fix.
- **When BUG-608 is fixed** (explicit `null` clears clearable fields): UP-12,
  UP-13, UP-17 will XPASS (UP-17 needs both 607 and 608; its reason string
  only cites 608 since that's the first assertion it fails on today).
- **When BUG-609 is fixed** (`delete_payment` always refuses): DP-03, DP-04,
  DP-05 will XPASS, and at that point the two coverage gaps at lines 330/332
  (and the old recompute block generally) become genuinely dead code worth a
  `dead-code-removal-checklist.md` entry (not added here — shared file,
  batch mode).
- **When BUG-611 is fixed** (amount-change message says "Void" not "Delete"):
  UP-04/UP-06's `startswith` assertions keep passing either way; UP-23 will
  XPASS.
- No float-precision fragility: all money assertions compare `Decimal` after
  a DB re-read, or use `money()` for audit-snapshot values that may still be
  floats (BUG-141).
