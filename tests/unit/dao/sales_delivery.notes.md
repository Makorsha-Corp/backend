# Execution notes — `app/dao/sales_delivery.py`

> Cases: `tests/unit/dao/sales_delivery.cases.md` (revision 3) · Tests: `tests/unit/dao/test_sales_delivery.py` · Source commit: e48a092
> Result: 71 passed · 12 xfailed · 0 discrepancies · 0 errors — branch coverage 96% (the one missed line is dead code)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_sales_delivery.py -q -p no:cacheprovider -o addopts=""`

## How the tests are built
- **Standing rows** → fixture `g` (a namespace with the Conventions names): W0, W1, W2, U1–U3, then per workspace ACk / Fk / Sk, orders SO0 (W0), SO1, SO2, SO3 (W1), SO9 (W2) numbered `f"SO-{TAG}-<k>"`, then DM1 (W1) and DM9 (W2), each flushed in that order. `g.TAG` is the per-test `uuid4().hex[:8]`.
- **delivery** → `mk_delivery(name, **but)`: W1, SO2, `f"DV-{TAG}-<name>"`, `"planned"`, U1; the "but" columns are keywords. The cards' `for k in ...: db.add(...)` loops → `add_many(db, g, numbers)`, one flush after the loop.
- **clock(L, U)** → context manager `clock(local, utc)`: patches `app.dao.sales_delivery.datetime` with a `datetime` subclass whose `now()` returns L, and `app.dao.sales_delivery.utcnow` (`create=True`) and `app.utils.time.utcnow` to return U. Every `CW` card runs under `DEFAULT_CLOCK` (2026-06-01 12:00 both) unless it has its own clock line; CW-11 and CW-12 ("no clock") patch nothing and check `created_at` against a real-time window.
- **seqscan**, **bump(X)**, **Dhaka** → helpers `seqscan(db)`, `bump(db, row)`, `dhaka(db)` (`SET LOCAL` / raw `UPDATE`, rolled back with the test). The ordering cards take the expected id list before `bump` + `expire_all`.
- **re-read** → `reread(db, id)`; **count(Wk)** → `count(db, ws)` (the carded raw SQL); **nothing written** → `counts(db, g)` before / after; **ids** / **idset** as carded.
- **Statement recorder** → `StatementRecorder` (`before_cursor_execute`); `sql` = the one SELECT from `sales_deliveries`, `order_part`, `lock_part`, `written`.
- `raises: IntegrityError` / `DataError` cards wrap the call in `pytest.raises` then `db.begin_nested()`. CW-05 / CW-06 have no wrap in the card; the call sits below `# Then 1`, so today's 23505 is reported at Then 1.
- CW-25's precondition (`DEL-2091-001` not stored anywhere) is a bare `assert` before the snapshot, as carded.
- Parametrized (identical setup, one input differs; each case keeps its own id): GN-03/04, CW-13/14, CW-17/18/19, SO-05/06/07, ST-02/03/04/06/07/08, ST-16/17, ST-19/20.

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 127 (`get_by_date_range`) | dead | Paged list by scheduled-date range; ruled remove (spec Not specified, Q1; dead-code removal checklist). |

Otherwise 100% line and branch coverage (private `COVERAGE_FILE`). Inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
| Run | Passed | xfailed | xpassed (non-strict) | Not as designed |
|---|---|---|---|---|
| Default, runs 1–3 (file alone) | 71 | 12 | 0 | 0 |
| `PGOPTIONS=-c TimeZone=Asia/Dhaka` | 71 | 12 | 0 | 0 |
| `PGOPTIONS=-c enable_seqscan=off` | 71 | 8 | 4 (SO-09, SO-10, ST-23, ST-24: index order) | 0 |
| `--runxfail` | 71 | — | — | the 12 xfails fail at their cards' Thens (below) |
| `--runxfail` with the reference plugin | 83 of 83 | — | — | 0 |
| Default, runs 1–3 (Revision 3) | 71 | 12 | 0 | 0 |
| `--runxfail` with the reference plugin (Revision 3) | 83 of 83 | — | — | 0 |

`--runxfail` failing lines (own plugin `failson_c.py`): CW-05 / CW-06 Then 1 (`IntegrityError` 23505 on `ix_sales_deliveries_delivery_number`); CW-08 Then 2 (`DEL-2027-001`); CW-09 Then 2 (`DEL-2026-001`); CW-13 / CW-14 Then 2 (`"shipped"` / `"delivered"` stored); SO-09, SO-10, ST-23 Then 2 (the bumped A comes last); ST-24 Then 2 (C is second); SO-11, ST-25 Then 2 (`"ORDER BY" in sql`). All as the cards' "Fails today on".

**Reference plugin** (`<scratch>/omde/C/ref_sdv.py`, `-p ref_sdv`): both lists with `ORDER BY sales_deliveries.id ASC` before `OFFSET` / `LIMIT` (BUG-2442, BUG-2443); `create_with_user` takes `app.utils.time.utcnow().year` (BUG-2440) and always stores `"planned"` (BUG-722); for CW-05 / CW-06 an autouse fixture swaps the global unique number index for a unique `(workspace_id, delivery_number)` index inside the test's own transaction (BUG-726). CW-07 still gets 23505 under it. Nothing in `app/` changes.

ruff check and ruff format clean (header `noqa`: SIM117, DTZ001). Line endings LF.

## Notes for maintainers
- When BUG-726, BUG-2440, BUG-722 are fixed, their strict cards XPASS and fail: remove the markers. SO-11 and ST-25 are the strict alarms for BUG-2442 / BUG-2443; SO-09, SO-10, ST-23, ST-24 are non-strict (physical row order) and pass by accident when sequential scans are off.
- CW-15 / CW-16 pin that the DAO stores another workspace's order / delivery method as given; the refusal belongs to `SalesManager` (HR-16, BUG-730; Deferred). SO-03 / SO-04 build a W2 row on W1's order on purpose (isolation of the filter), which HR-16 calls invalid data.
- Delivery numbers such as `DEL-2026-001` are globally unique today: a parallel run that inserts the same number in another, uncommitted transaction makes these inserts wait until that transaction ends.

## Revision history
- **Revision 3 (2026-11-10):** patched, not regenerated; verify finding 1 (convention). SDV-GN-14 now has two Thens: Then 2 `"FOR UPDATE" not in rec.sql` (was `… not in rec.sql.upper()`, now exactly as carded); the vacuous Then 3 `rec.lock_part == ""` is dropped. No card in this file needed a new `expunge_all`: the cards that read stored values already end their Given with `db.expire_all()` as carded. Every other test is unchanged; counts unchanged.
  - **Hand variants** (own plugin `<scratch>/omde/C/variants_c.py`, `VARIANT=… -p variants_c -m "not xfail"`): `lockall` and `lockall_of` (every ORM query on `SalesDelivery` from the DAO locked; `count()` over a locked subquery) each fail exactly GN-14, at Then 2 (70 passed, 1 failed). `fixed2026` fails exactly CW-10, at Then 2.
  - Re-run: 3 plain runs 71 passed / 12 xfailed each; `--runxfail` the 12 xfails fail at their cards' Thens (as listed above); reference plugin with `--runxfail` 83 / 83; coverage unchanged (96%, line 127 dead); ruff check and format clean; LF.
