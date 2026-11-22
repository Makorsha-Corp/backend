# Execution notes — `app/services/invoice_payment_service.py`

> Cases: `tests/unit/services/invoice_payment_service.cases.md` (revision 3, 2026-11-22) · Tests: `tests/unit/services/test_invoice_payment_service.py` · Source commit: e48a092
> Result: 66 passed · 53 xfailed · 0 discrepancies · 0 errors — branch coverage 97%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_invoice_payment_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.invoice_payment_service --cov-branch --cov-report=term-missing`

## How the tests are built
- **Standing rows** (W0, W1, W2, U1, U2, A0, A1, A2) are attributes of the fixture namespace `s`, built in the Conventions order. `inv(db, s, n, **but)` = INV(Wn); `tw(db, s, I, voided=, keyed=, flush=, **but)` = TW(I) with the "voided" and "keyed K" conventions. "keyed" sets `idempotency_key` / `idempotency_fingerprint` as plain attributes after building and before `db.add` (ignored by the mapper today). `eo1` = EO1 (`app.models.expense_order.ExpenseOrder`, `expense_category="other"`, `completed_at=T0`), `po1` = PO1 (with its own `Status` row), `mk_x` = X, `x_count` = the "Pending extra" count.
- **Call values:** `body(invoice_id, **but)` = BODY; `fp(uid, d)` / `fp_of(P)` = fp / FP exactly as Conventions; `col(db, P, c)` = the column query; `upd(db, s, pid, data)` passes `user_id` only if the signature has it.
- **Named checks:** `counts` (nothing written: four tables, all workspaces), `snap_inv` (unchanged(I): four columns), `snap_pay` (unchanged(P): every column of the table row), `reread`, `audit`, `events`, `po_events`, `usable`. Snapshots are taken right after the commit point, before X.
- **Commit point** = `db.commit()` after the last Given line. Four cards hold a Given step that must not be flushed or committed, so the commit point comes before that step: M-04 (the in-memory `payment_amount = 0.00`), K-30, K-31, K-32 (the row "db.add-ed, not flushed": committing after it would flush it and the When `db.flush()` would be a no-op). PR-01 already says "after the commit point".
- **committed:** lines: one `db.rollback()` before the first; the fixture's commit only releases a savepoint, so a rollback after the service's commit discards only later work.
- **Time:** `app.utils.time.datetime` frozen to NOW (autouse), as the manager tests do.
- **Statement recorder:** a `before_cursor_execute` listener on `db.connection()`, around the When only (the cards' "Statement recorder on" in Given). `lock_stmts` = statements with `FROM account_invoices` and `FOR UPDATE`. K-27's "key-lookup statement" = a statement from `invoice_payments` whose WHERE part mentions `idempotency_key` (after the fix every payment SELECT lists the column, so the WHERE part is what marks a lookup).
- **Race simulation** (K-28, K-29 only): `patch.object(svc.invoice_payment_manager, "create_payment", side_effect=dup)`; `dup` inserts TW(I1) but `created_by U1`, keyed KEY, and flushes.
- **xfail markers:** strict. Cards whose "Fails today on" is a TypeError from a parameter that does not exist yet (C-14, V-12, U-09, the K cards) carry `raises=TypeError`, so they stay xfailed only for that cause. Parametrized: K-11 … K-16 (one body field differs → 409) and K-18 … K-20 (key compared exactly); each case keeps its own param id.

### Two facts confirmed for the cards (no spec change)
1. `ExpenseOrder` is imported from `app.models.expense_order` (C-03, V-03 pass; columns `workspace_id`, `invoice_id`, `completed_at` exist; required: `expense_number`, `expense_category`, `created_by`).
2. An unknown `user_id` fails with `IntegrityError`, `orig.pgcode == "23503"`: the payment row's `created_by` foreign key to `profiles`, at the DAO's flush (C-17 passes today; K-46 passes under the reference plugin).

### Verification done at execution
- `--runxfail`: all 53 strict xfails fail, each inside the Then line the card names (checked with a scratch plugin mapping the failing line of the test function to its `# Then N` block; the TypeError cards fail at the call, before Then 1, which is what their "Then 1 (the call raises TypeError)" describes).
- Reference plugin (scratch, in-process, nothing under app/): implements BUG-600, 601, 603, 606, 607, 608, 609, 611, 2400 and 3002 (idempotency columns added to the mapper and, per test, `ALTER TABLE` + the partial unique index inside the test's own transaction). Under it with `--runxfail`: 118 passed. K-36's literal SHA-256 matches the R9f recipe.
- 3 runs: 66 passed / 53 xfailed each time (rev 3). ruff check and ruff format clean, LF endings.

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 50 | unreachable | `_payment_response`: the creator re-read finds no row → response with `created_by_name None`. Spec R2 / Q1: intended, unreachable through the public methods (the payment was just written in the same workspace); no case. |

## Factories added
None.

## Notes for maintainers
- When BUG-3002 is fixed, every K xfail XPASSes → remove the markers. The keyed Given rows then really store key and fingerprint; K-31/K-32 keep passing.
- L-02 (BUG-600) relies on Postgres returning same-date rows in insertion order (c, a, b) today; stable over the runs here, but a sort could in principle return c, b, a and XPASS. If it ever flips, it is this card, not a regression.
- C-15 (BUG-2400) depends on the database clock differing from the frozen NOW — always true (NOW is 2026-09-27).
- D-07 holds on both sides of BUG-609 (RuntimeError today, 400 after).
- IPS-U-10 / U-01 use `upd`, so after BUG-607 they pass `user_id`; U-10's empty update should then write no audit row (not asserted by the card).
- New bugs: none (BUG-2974, BUG-2975 unused).

## Revision history
- 2026-11-22 — cases rev 3: new IPS-G-08 (found payment: no commit, no rollback; the unflushed `Account` Y stays in `db.new`, the renamed A1 stays in `db.dirty`). Result: 3 runs 66 passed / 53 xfailed, 97% branch (gap unchanged); `--runxfail` 53/53 on the named Then line; reference plugin + `--runxfail` 119 passed; ruff clean, LF.
