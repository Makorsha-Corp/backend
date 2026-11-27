# Execution notes — `app/dao/financial_audit_log.py`

> Cases: `tests/unit/dao/financial_audit_log.cases.md` (revision 3) · Tests: `tests/unit/dao/test_financial_audit_log.py` · Source commit: e48a092
> Result (revision 3, 2026-11-09): 115 tests for 115 cases — 99 passed · 16 xfail (9 strict, 7 non-strict) · 0 discrepancies · 0 errors — branch coverage 100% (30 statements, 0 branches)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_financial_audit_log.py -q -p no:cacheprovider -o addopts="" --cov=app.dao.financial_audit_log --cov-branch --cov-report=term-missing` (private `COVERAGE_FILE`)

The result of the 7 non-strict tie cards (BE-16, BE-17, RL-17, AT-10, BU-06, DR-13, RC-09) varies between runs: their order among tied rows follows the heap, so any number of them may XPASS or xfail in a given run. Observed: 7 XPASS in each of this executor's plain runs, 5 xfailed in one coverage run, 6 of 7 failing (each in Then 2) in a `--runxfail` coverage run; the verifier saw 1, 0 and 1 XPASS. None of this turns a run red; the 9 strict cards are the stable proof.

## How the tests are built
- Normal mode (no local model); every test sits below `# [claude] <ID>`, in card order.
- **Standing rows:** one autouse fixture `st` with `W0, W1, W2, U1, U2, U3`, built in that order.
- **Given rows:** `log(db, st, performed_at, **cols)` and `pay(db, st, performed_at, **cols)` (payment row: `payment` 7, related `invoice` 10), each flushed. The `add_all` Givens build the models from the same default dicts (`_log_fields`, `_pay_fields`) and flush once in `many()`, which returns `newest` (reverse insertion order). `wn_setup` is the "writes-nothing setup" (B flushed in W2 then edited, P added and not flushed). `edit_lowest` is the tie Givens' "`A.description = "Edited"`, flush, `expire_all`".
- **Named checks:** `ids`, `snap` (columns straight from the table), `stored` (row count, all workspaces), `reread`, `StatementRecorder` (`before_cursor_execute` on the session's connection; `sql()` requires exactly one `SELECT`), `order_part_of` (after the first `ORDER BY`, cut at `LIMIT`).
- `zone(z)` is `SET LOCAL TIME ZONE '<z>'`, first step of its card, valid for the test's outer transaction.
- `raises: DataError` cards use `pytest.raises` around `db.begin_nested()`; the count is compared on the still-usable session. RC-12 records statements around the `TypeError` call: 0 sent.
- Nothing is patched.

## xfail location (`--runxfail`, own `failson` plugin: failing line → `# Then N`)
| Cards | Strict | Fails on | Failing check |
|---|---|---|---|
| BE-18, RL-18, AT-11, BU-07, DR-14, RC-10 | yes | Then 4 | `".id" in order_part` (order by `performed_at` alone) |
| DR-09 | yes | Then 1 | `ids == [A]` (X at 18:00 returned: bounds read as Dhaka time) |
| DR-10 | yes | Then 1 | `ids == [A]` (nothing found: bounds read as New York time) |
| N-02 | yes | Then 2 | `before <= performed_at <= after` (Dhaka `now()`) |
| BE-16, RL-17, AT-10, BU-06, DR-13, RC-09 | no | Then 2 when they fail | the id order among ties |
| BE-17 | no | Then 2 when it fails | page ids |

Every strict xfail fails on the Then line its card names.

**Reference plugin** (`<scratch>/dao/plugins/ref_fal.py`, in-process, nothing in `app/`): all six readers order by `performed_at DESC, id DESC`; `get_by_date_range` converts aware bounds to naive UTC; a `before_insert` mapper event fills `performed_at` from `utcnow()`. Under it with `--runxfail`: **115 passed**. With markers on: 99 passed, 7 xpassed, 9 failed (the 9 strict XPASS(strict) — the red run a fix must produce).

## Discrepancies
None.

## Coverage gaps
None — 100% line and branch coverage of `app/dao/financial_audit_log.py` (30 statements, no branches). `FinancialAuditLogCreate` is a schema without logic; the inherited `create` is measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Notes for maintainers
- `ruff check`: clean (file-level `noqa` for SIM117, DTZ001). LF line endings. 3 plain runs: `99 passed, 9 xfailed, 7 xpassed` each in this executor's runs (the non-strict count varies between runs, see above).
- When BUG-2370 is fixed: the six SQL-recorder cards XPASS (red) — remove their markers and the seven non-strict tie cards'. BUG-2371: DR-09, DR-10 (their passing companions DR-06…08 must stay green). BUG-2372: N-02.
- `get_recent_logs` takes no `skip` (RC-12): a caller passing it gets `TypeError`, not an empty page.

## Useful for the coming permissions / notifications / payments features
- **Permissions (OQ-23, owner 2026-11-07: deferred):** this DAO only scopes by `workspace_id`; who may read the financial log is decided in the endpoints. A role check added later belongs above the DAO — the readers need no change. `get_by_user` filters by `performed_by` only, so "my own actions" views are possible without a new query.
- **Payments:** the log records payment rows with `related_entity_type "invoice"`; `get_related_logs` follows one level only (an account does not see its invoices' payments). A subscription-payment audit trail built on this table would need the same `id` tie-break (BUG-2370) and naive-UTC timestamps (BUG-2372) to page reliably.
- **Notifications:** none here; the log is written by `audit_logger` (other spec).

## Revision history
- **2026-11-09 — Revision 2** (first execution): 115 cases → 99 passed · 16 xfail; no discrepancy.
- **2026-11-09 — Revision 3** (cases wording only, verify n1: Reviewer summary count). No test changed. Verify n2 fixed: the tie-card sentence now says their result varies between runs. Re-run: 99 passed · 9 xfailed · 7 xpassed, coverage 100%; `--runxfail` every strict xfail fails on its named Then (six SQL recorders Then 4, DR-09/10 Then 1, N-02 Then 2); reference plugin 115 passed; 3 plain runs identical; ruff clean; LF.
