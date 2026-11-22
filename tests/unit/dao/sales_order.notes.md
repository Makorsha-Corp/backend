# Execution notes — `app/dao/sales_order.py`

> Cases: `tests/unit/dao/sales_order.cases.md` (revision 3) · Tests: `tests/unit/dao/test_sales_order.py` · Source commit: e48a092
> Result: 68 passed · 9 xfailed · 0 discrepancies · 0 errors — branch coverage 92% (the two missed lines are dead code)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_sales_order.py -q -p no:cacheprovider -o addopts=""`

## How the tests are built
- **Standing rows** → fixture `g` (a namespace with the Conventions names): W0, W1, W2 (`make_workspace` three times, so `W0.id < W1.id < W2.id`), U1–U3 (`make_profile`), then per workspace Ak / Fk / Sk, then invoices V0, V1, V2, V3, V9 in that order, each flushed. `g.TAG` is the per-test `uuid4().hex[:8]`.
- **order** → `mk_order(number, k=1, **but)`; `k=0` / `k=2` = "of W0" / "of W2" (uses that workspace's account, factory and status). **orders(W, prefix, n)** → `mk_orders(k, prefix, n)`, one flush after the loop.
- **clock(L, U)** → context manager `clock(local, utc)`: patches `app.dao.sales_order.datetime` with a `datetime` subclass whose `now()` returns L, and `app.dao.sales_order.utcnow` (`create=True`) and `app.utils.time.utcnow` to return U. Every `CW` card without a clock line runs under `DEFAULT_CLOCK` (2026-06-01 12:00 both). `GI` / `GN` cards patch nothing. The model's `created_at` default (`app.models.sales_order.utcnow`) is not patched (spec G2); CW-18 / CW-19 check a real-time window.
- **seqscan**, **Dhaka**, **HIGH_ID** → helpers `seqscan(db)`, `dhaka(db)`, `high_id(db)` (`SET LOCAL`, rolled back with the test).
- **re-read** → `reread(db, id)` (`expire_all` + SELECT). **count(W)** → `count(db, ws)`; **nothing written** → `counts(db, g)` before / after. **unchanged(O1)** (CW-30) → `snap(db, row)`, every column from the table.
- **Statement recorder** → `StatementRecorder` (`before_cursor_execute`); `sql` = the one SELECT from `sales_orders`, `order_part` = after the first `ORDER BY`, before `LIMIT`; `lock_part`; `written`.
- `raises: IntegrityError` cards wrap the call in `pytest.raises` then `db.begin_nested()`. CW-20 / CW-21 wrap the call in `db.begin_nested()` with `# Then 1` above it, so today's 23505 is reported at Then 1.
- **commit spy** (CW-29) as carded: `sp = db.begin_nested()`, `patch.object(db, "commit", wraps=db.commit)`, inside-savepoint count, `sp.rollback()`, after-rollback count.
- Parametrized (identical setup, one input differs; each case keeps its own id): GN-03…06, GN-17/18/19/21, CW-10…14, CW-23…26.

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 101 (`get_by_factory`) | dead | Paged list by factory; ruled remove (spec Not specified, Q1; dead-code removal checklist). |
| 122 (`get_by_status`) | dead | Paged list by status; ruled remove (same). |

Otherwise 100% line and branch coverage (private `COVERAGE_FILE`). Inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
| Run | Passed | xfailed | xpassed (non-strict) | Not as designed |
|---|---|---|---|---|
| Default, runs 1–3 (file alone, Revision 2) | 67 | 9 | 0 | 0 |
| Default, runs 1–3 (file alone, Revision 3) | 68 | 9 | 0 | 0 |
| `PGOPTIONS=-c TimeZone=Asia/Dhaka` | 67 | 9 | 0 | 0 |
| `PGOPTIONS=-c enable_seqscan=off` | 67 | 8 | 1 (GI-11, index order) | 0 |
| `--runxfail` | 67 | — | — | the 9 xfails fail at their cards' Thens (below) |
| `--runxfail` with the reference plugin (Revision 2) | 76 of 76 | — | — | 0 |
| `--runxfail` (Revision 3) | 68 | — | — | the 9 xfails fail at the same Thens as before |
| `--runxfail` with the reference plugin (Revision 3) | 77 of 77 | — | — | 0 |

`--runxfail` failing lines (own plugin `failson_c.py`, failing line → `# Then N`): GI-11 Then 2 (`result.id == OA.id`, got OB), GI-12 Then 2 (got the HIGH_ID row), GI-13 Then 2 (`"ORDER BY" in sql`), CW-06 Then 2 (`SO-2027-001`), CW-07 Then 2 (`SO-2026-001`), CW-08 Then 2 (`SO-2027-001`), CW-31 Then 2 (`SO-2026-003`), CW-20 / CW-21 Then 1 (`IntegrityError` 23505 on `ix_sales_orders_sales_order_number`). All as the cards' "Fails today on".

**Reference plugin** (`<scratch>/omde/C/ref_so.py`, `-p ref_so`): `get_by_invoice_id` with `ORDER BY sales_orders.id ASC` (BUG-2441); `create_with_user` takes `app.utils.time.utcnow().year` (BUG-2440); for CW-20 / CW-21 an autouse fixture swaps the global unique index for a unique `(workspace_id, sales_order_number)` index inside the test's own transaction (BUG-726). CW-22 still gets 23505 under it. Nothing in `app/` changes.

ruff check and ruff format clean (header `noqa`: SIM117, DTZ001, FURB157 for the carded nested `with`, naive datetimes and Decimal strings). Line endings LF.

## Notes for maintainers
- When BUG-2440 / BUG-726 are fixed, their strict cards XPASS and fail: remove the markers. BUG-2441's GI-13 is the strict alarm; GI-11 / GI-12 are non-strict because they rest on physical row order (GI-11 passes by accident when sequential scans are off).
- CW-22 pins today's count rule (spec R4); revisit it with the BUG-727 fix (counter or retry).
- Sales order numbers such as `SO-2026-001` are globally unique today: a parallel test run that inserts the same number in another, uncommitted transaction makes these inserts wait until that transaction ends (no failure, just a delay).
- CW-09 passes: `model_dump()` sends `total_amount=None`, and the stored value is `0.00` (the model default fills it).

## Revision history
- **Revision 3 (2026-11-10):** patched, not regenerated; verify findings 1–2. Added SLO-CW-34 (both clocks in 2031, an `SO-2026-001` in W1 → `SO-2031-001`), after CW-33. GI-18 and GN-23 Then 2 now check `"FOR UPDATE" not in rec.sql` instead of the vacuous `rec.lock_part == ""` (the `lock_part` helper stays, as in Conventions; no test uses it now). No card in this file needed a new `expunge_all` (the "Clear the session" Conventions bullet): the cards that read stored values already end their Given with `db.expire_all()` as carded. Every other test is unchanged.
  - **Encoding repair:** the Revision 2 file had 63 lines whose `—`, `→` and `…` had been encoded twice (UTF-8 read as cp1252 and saved again; `â€”` in docstrings). They were decoded back to the real characters (own script `<scratch>/omde/C/demoji.py`); no code changed.
  - **Hand variants** (own plugin `<scratch>/omde/C/variants_c.py`, `VARIANT=… -p variants_c -m "not xfail"`): `lockall` (every ORM query on `SalesOrder` from the DAO gets `.with_for_update()`; `count()` counts a locked subquery, because Postgres refuses `FOR UPDATE` next to an aggregate, 0A000) and `lockall_of` (`of=SalesOrder`) each fail exactly GI-18 and GN-23, both at Then 2 (66 passed, 2 failed). `fixed2026` (`create_with_user` always takes year 2026) fails exactly CW-34, at Then 2 (`SO-2026-002` for `SO-2031-001`; 67 passed, 1 failed). Before Revision 3 all three variants passed every pass card.
  - Re-run: 3 plain runs 68 passed / 9 xfailed each; `--runxfail` the 9 xfails fail at their cards' Thens (as listed above); reference plugin with `--runxfail` 77 / 77 (CW-34 holds under the UTC-year fix); coverage unchanged (92%, lines 101 and 122 dead); ruff check and format clean; LF.
