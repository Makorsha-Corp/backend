# Execution notes — `app/dao/payment_transaction.py`

> Cases: `tests/unit/dao/payment_transaction.cases.md` (revision 3) · Tests: `tests/unit/dao/test_payment_transaction.py` · Source commit: e48a092
> Result: 125 passed · 18 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_payment_transaction.py -q -p no:cacheprovider -o addopts="" --cov=app.dao.payment_transaction --cov-branch --cov-report=term-missing`

## How the tests are built
Built in normal mode (full Claude, no local model); every test sits below `# [claude] <ID>`, one test per card, in card order, with a `# Then N` comment before each numbered Then line. The file is written as the owner's reference for the SSLCommerz subscription portal: its docstring has a "card says -> code" table, and there is one section per DAO method with a line saying what the method is for (callbacks, sweep, risk resolution, ledger).

- **Standing rows** — autouse fixture `st` (class `Standing`): W0, W1, W2 via `make_workspace`, U1 "Rahim", U2 "Karim" via `make_profile`, and a fresh `TAG` per test. `st.tid(k)` is the 27-character tran_id.
- **Given rows** — `st.txn(k, **cols)` builds the Conventions' `txn(k)` (W1, U1, 990.00 BDT, T1 times) and flushes; "but" columns are keywords; `**PAID` is the "paid" column set. `st.pending(k)` is the unflushed row P of the writes-nothing cards. The 101-row and 201-row Givens are `add_101_ledger_rows` / `add_201_stuck_rows` (one flush, as the cards say).
- **Steps** — `st.raw_insert`, `st.zone` (`SET LOCAL TimeZone`), `st.seqscan` (index, bitmap and index-only scans off), `st.bump` (no-op UPDATE + `expire_all`), `st.clean2001` (precondition assert, first line of every SI / OQ25 test).
- **Checks** — `st.reread` (`expire_all` + `db.get`), `st.counts()` (rows of W0/W1/W2 and all profiles: "nothing written"), `st.count_tid`, `st.count_ws`, `near_utc`, `ids` / `idset` / `pairs`. `StatementRecorder` listens to `before_cursor_execute` on `db.get_bind()` only around the When; `sql` is the one SELECT reading `payment_transactions`, `order_part` / `lock_part` as the Conventions define.
- **Commit spy** — `sp = db.begin_nested()`, `patch.object(db, "commit", wraps=db.commit)`; "inside" Thens run before `sp.rollback()`.
- **Database errors** — `pytest.raises(E)` around `db.begin_nested()`; the session stays usable for the counts.
- Nothing is mocked and no clock is patched (Conventions: Externals none). "W1 has no payment transaction" Givens are asserted as preconditions.
- **BUG-029 cards (IW-13 … IW-18)** fail in the When call with `TypeError: unexpected keyword argument 'for_update'`, which is what "Fails today on: Then 1 (the call raises TypeError)" describes; a `# Fails today here` comment sits on the call. The call is not wrapped in `pytest.raises`.

## Checks run
| Run | Passed | xfailed | xpassed (non-strict) | Not as designed |
|---|---|---|---|---|
| Default, runs 1–3 | 125 | 18 | 0 | 0 |
| `PGOPTIONS=-c enable_seqscan=off` | 125 | 15 | 3 (LW-09/10/11 or SI-11/12/13 tie cards) | 0 |
| `-c enable_sort=off` | 125 | 18 | 0 | 0 |
| database `TimeZone` `Asia/Dhaka` / `America/New_York` | 125 | 18 | 0 | 0 |
| `--runxfail` + `failson_a` | 125 | — | — | 18 failed, each on its card's line |
| `--runxfail` + reference plugin `ref_pt` | 143 of 143 | — | — | 0 |

**`--runxfail` (where each xfail fails):** CR-18/19/20/21 Then 2 (`near_utc` of the raw insert's time); IW-13 … IW-18 in the call, `TypeError` (card: Then 1, "the call raises TypeError"); LW-12 and SI-14 Then 4 (`"payment_transactions.id" in order_part`); the six non-strict tie cards (LW-09/10/11, SI-11/12/13) Then 2 — on the default plan they failed every run, i.e. the bug showed.

**Reference plugin** (`omde\A\ref_pt.py`, `-p ref_pt`, in-process only): `for_update` keyword with `with_for_update(of=PaymentTransaction)` (SQL `… LIMIT … FOR UPDATE OF payment_transactions`); list ordered `created_at DESC, id DESC`; sweep ordered `initiated_at ASC, id ASC`; for the raw-insert cards CR-16 … CR-21 the three time defaults are set to `timezone('utc', now())` by `ALTER TABLE` inside the test's own transaction (rolled back with it). With `--runxfail`: 143 / 143.

ruff check and ruff format clean (header `noqa` for SIM117, DTZ001 and FURB157: the cards write `Decimal("990")`, `Decimal("-5")`, `Decimal("10000000000000")` and those literals are kept). LF line endings.

## Discrepancies
None.

## Coverage gaps
None — 100% line and branch coverage (27 statements, 4 branches; private `COVERAGE_FILE`). Inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None (local builders only).

## Notes for maintainers
- When BUG-029 is fixed (a `for_update` keyword), IW-13 … IW-18 XPASS (strict → fail): remove the markers. The fix must lock `OF payment_transactions` only — Postgres refuses `FOR UPDATE` on the nullable side of the outer join, and IW-14 checks that the outer join is kept.
- When BUG-2402 / BUG-2403 are fixed, LW-12 and SI-14 XPASS (strict); remove their markers and those of the non-strict tie cards, which then pass every time.
- When BUG-2401 is fixed by a migration, CR-18 … CR-21 XPASS; CR-17 is the control under UTC and holds both before and after.
- The non-strict tie cards rest on physical row order; under `enable_seqscan=off` some pass by accident (they are non-strict for that reason).
- The six `PTX-OQ25-*` tests pin today's sweep (status `INITIATED` only). When the payment portal decides OQ-25, only those tests change.
- `clean2001` asserts that no committed row of another workspace has an `initiated_at` before 2002; if a dev seed ever commits such rows into `marker_test`, the SI tests stop at that precondition (not at a Then).

## Revision history
- **Revision 3 (2026-11-10):** patched, not regenerated (verify findings 1-2). PTX-IW-13 gains Then 6, `rec.lock_part.strip() == "FOR UPDATE OF payment_transactions"`. PTX-IW-11, TW-15 and LW-21 run `db.expunge_all()` before the statement recorder (Conventions: clear the session before a one-query check). Every other test unchanged. Re-run: 3 plain runs (125 passed, 18 xfailed each). `--runxfail`: the 18 xfails fail as before; IW-13 still stops in the When with `TypeError` (card: Then 1), and Then 6 sits behind it. Reference plugin `ref_pt.py` with `--runxfail`: 143 / 143. Variants `omde\A\var_pt.py` (the reference fix plus `SKIP LOCKED`, or plus `NOWAIT`) with `--runxfail` on the IW section: each fails IW-13 only, at Then 6 (17 passed, 1 failed each). Branch coverage 100%. ruff check and format clean; LF.
