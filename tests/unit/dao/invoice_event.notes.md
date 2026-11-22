# Execution notes — `app/dao/invoice_event.py`

> Cases: `tests/unit/dao/invoice_event.cases.md` (READY, 29 cases; spec APPROVED 2026-11-03) · Tests: `tests/unit/dao/test_invoice_event.py` · Source commit: e48a092
> Result: **29 tests for 29 cases — 27 passed · 2 xfailed (1 strict, 1 non-strict) · 0 discrepancies · 0 errors** — branch coverage 100% (14 statements, 0 branches)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_invoice_event.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The scratch audit (`acctx\audit.py`) found 0 problems.

## How the tests are built
- **Nothing is patched.** `created_at` is the model's Python default (`utcnow`); IEV-CE-02 sets the session time zone to `Asia/Dhaka` and compares with `clock_timestamp() AT TIME ZONE 'UTC'` read after the call. IEV-CE-14 uses the `db.commit` spy and a savepoint per **rolled back**. Path of Spec gap 3 is the real one (`app.models.account_invoice.AccountInvoice`).
- **Standing rows:** `w1`, `w2`, `u1` ("Rahim"), `u2` ("Karim"), `ac1`, `ac9`, `inv1`, `inv2`, `inv9`, each fixture depending on the one before (flushed in Conventions order); autouse `standing_rows`.
- **Given rows:** `mk_event(created_at=..., **columns)` (W1, INV1, "created", "Invoice created", no performer, no metadata); IEV-GI-11 builds 201 `_event(...)` objects with `add_all` and one flush. `bump_e`, `seqscan` as in the Conventions. IEV-GI-13 runs the card's `UPDATE profiles` / `DELETE FROM profiles` then `expire_all`.
- **Reading helpers:** `ids` (`r["id"]`), `reread`, `stored_json`, `is_sql_null`, `utc_clock`, `written_count` (`invoice_events` rows), `count_rows`.
- **Statement recorder** around the When only; `sql()` = the one SELECT `FROM invoice_events`; `order_part_of` = after `ORDER BY`.

## xfail check (`--runxfail`, failing value read)
| Case | Strict | Fails on | Value read under `--runxfail` |
|---|---|---|---|
| IEV-GI-09 | non-strict | Then 2 | `assert [42668, 42665, 42667, 42666] == [42668, 42667, 42666, 42665]` (the updated lowest id moved) |
| IEV-GI-10 | strict | Then 3 | `assert 'invoice_events.id' in ' invoice_events.created_at DESC'` (Then 2 held) |

## Explicit wrong order (non-strict proof)
`acctx\wrong.py` keeps `created_at DESC` and adds a tie-break: `id ASC` (wrong) fails IEV-GI-09 at Then 2; `id DESC` (the intended one) passes it. IEV-GI-08 (pass, distinct times) passes under every rewrite; no pass card fails.

**Reference plugin** (`acctx\ref.py`: `ORDER BY created_at DESC, id DESC`): with `--runxfail`, **29 of 29 pass**; IEV-GI-10's Then 4 (`created_at` before `id`) and Then 5 (two `DESC`) hold under the fix.

## Discrepancies
None.

## Coverage gaps
None — 100% line coverage (no branches; private `COVERAGE_FILE`).

## Factories added
None.

## Stability
5 default runs, the forced plans (`enable_seqscan=off`; with hash join and nested loop off; `enable_hashjoin=off`; index/bitmap/index-only scans off; with hash and merge join off; `enable_sort=off`) and database time zones `Asia/Dhaka`, `America/New_York`: 27 passed, 2 xfailed in every run; IEV-GI-09 never passed by accident.

**Clock:** IEV-CE-02 compares two real-clock stamps (`created_at` vs `clock_timestamp()`, within 5 s). It was run 3000 times, each in its own rolled-back test (scratch `acctx\rep_clock_test.py`): 3000 passed in 40 s.

`ruff check`: all checks passed. Line endings: LF.

## Notes for maintainers
- When BUG-638 is fixed in `get_by_invoice`, IEV-GI-10 XPASSes and fails: remove its marker; IEV-GI-09 then passes every time: remove its marker too.
