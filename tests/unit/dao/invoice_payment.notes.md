# Execution notes — `app/dao/invoice_payment.py`

> Cases: `tests/unit/dao/invoice_payment.cases.md` (revision 2) · Tests: `tests/unit/dao/test_invoice_payment.py` · Source commit: e48a092
> Result: 74 passed · 8 xfailed · 0 discrepancies · 0 errors — branch coverage 96% (the one missed line is dead code)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_invoice_payment.py -q -p no:cacheprovider -o addopts="" --cov=app.dao.invoice_payment --cov-branch --cov-report=term-missing`

## How the tests are built
Built in normal mode (full Claude, no local model); every test sits below `# [claude] <ID>`, one test per card, in card order, `# Then N` before each numbered Then line. The docstring maps the Conventions to code.

- **Standing rows** — autouse fixture `st` (class `Standing`): W0 < W1 < W2 (`make_workspace`), U1 "Rahim", U2 "Karim", U3 "Salma" (`make_profile`), accounts AC0/AC1/AC2 named `Acme {TAG}`, invoices N0 (W0), NA, N1, NB (W1, ids rising), N9 (W2), each flushed in that order.
- **Given rows** — `st.payment(**cols)` (10.00 on N1 of W1, D2, by U1) and `st.voided(**cols)` (all four void fields); `st.pending(**cols)` is the unflushed payment P (7.00, D5 unless overridden); `add_101_payments` builds the 101-row Given of GI-23 / GI-24 (`Author: claude`). `new_payment(st, **overrides)` is the dict the CR Whens pass to `dao.create`.
- **Steps / checks** — `st.bump` (`UPDATE … SET notes = 'x'` + `expire_all`), `st.zone` (`SET LOCAL TimeZone`), `st.reread`, `st.counts()` ("nothing written": all `invoice_payments` and `account_invoices` rows), `tids` / `names`, `close_to_now(value, now)` with `now = utcnow()` read right after the When. `StatementRecorder` as in the payment-transaction file; `sql` is the one SELECT `FROM invoice_payments`.
- **GI-20 / GC-11** (`db.expire_all()` before the recorder): the ids passed to the call are read *before* `expire_all`, because touching `st.W1.id` on an expired object sends its own SELECT, which the recorder would count. The card's statement count is about the DAO's SQL; the setup now sends nothing during the When.
- **Commit spy** — `sp = db.begin_nested()` before the call; the new id is kept before `sp.rollback()`.
- Nothing is mocked and no clock is patched.

## Checks run
| Run | Passed | xfailed | xpassed (non-strict) | Not as designed |
|---|---|---|---|---|
| Default, runs 1–3 | 74 | 8 | 0 | 0 |
| `PGOPTIONS=-c enable_seqscan=off` | 74 | 8 | 0 | 0 |
| `-c enable_sort=off` | 74 | 5 | 3 (GI-16/17/18, non-strict tie cards) | 0 |
| database `TimeZone` `Asia/Dhaka` | 74 | 8 | 0 | 0 |
| `--runxfail` + `failson_a` | 74 | — | — | 8 failed, each on its card's line |
| `--runxfail` + reference plugin `ref_ip` | 82 of 82 | — | — | 0 |

**`--runxfail`:** GI-16/17/18 Then 2 (non-strict tie orders; failed on the default plan, i.e. the bug showed), GI-19 Then 4 (`"invoice_payments.id" in order_part`), CR-07 / CR-08 Then 2 and CR-09 / CR-10 Then 3 (close to now).

**Reference plugin** (`omde\A\ref_ip.py`, in-process only): `get_by_invoice` ordered `payment_date DESC, id DESC`; a `before_insert` listener fills `created_at = utcnow()` when the writer gives none (BUG-2400). With `--runxfail`: 82 / 82.

ruff check and ruff format clean (header `noqa` for SIM117, DTZ001 and FURB157: the standing invoice uses the Conventions' `Decimal("100")`). LF line endings.

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 76 (`get_by_date_range`) | dead | Date-range list of a workspace's payments, `payment_date` descending; no caller; ruled remove (spec Q1, `docs/testing/dead-code-removal-checklist.md`). |

Otherwise 100% line and branch coverage (private `COVERAGE_FILE`).

## Factories added
None (local builders only).

## Notes for maintainers
- When BUG-600 is fixed (here or in the manager), GI-19 XPASS (strict → fail): remove its marker and those of GI-16/17/18.
- When BUG-2400 is fixed (`created_at` from `utcnow()` plus a migration), CR-07 … CR-10 XPASS: remove the markers.
- GI-16/17/18 rest on physical order after `bump`; under `enable_sort=off` they pass by accident (non-strict for that reason).
- GI-22 pins that the invoice row is not read; HR-16 (another workspace's invoice) is the manager's check.
