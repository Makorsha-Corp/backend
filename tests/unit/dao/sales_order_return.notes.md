# Execution notes — `app/dao/sales_order_return.py`

> Cases: `tests/unit/dao/sales_order_return.cases.md` (Revision 3, READY, 86 cases) · Tests: `tests/unit/dao/test_sales_order_return.py` · Source commit: e48a092
> Result: **86 tests for 86 cases — 74 passed · 12 xfailed (8 strict, 4 non-strict) · 0 discrepancies · 0 errors** — line and branch coverage 100% (27 statements, 0 branches).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_sales_order_return.py -q -p no:cacheprovider -o addopts=""`

## Who wrote what
Normal mode, no local model (full Claude): every test sits below a `# [claude] <ID>` comment, in card order. The `Author: claude` cards (BS-09, BS-10, OP-07, RI-07) use the Conventions' tie recipe as written: `seqscan` (index, bitmap and index-only scans off with `SET LOCAL`), then `bump` / `bumpL` of the lowest id, which moves that row to the end of the heap.

## How the tests are built
- **Standing rows:** one fixture `s` builds Conventions rows 1–5 in their order (W0, W1, W2; U1–U3; AC/F/S per workspace; SO0, SO1, SO2, SO3, SO9; IT1, L1; INV1–INV3), each added and flushed, and returns them as a namespace (`s.W1`, `s.SO2`, …). TAG is made once per test.
- **Builders:** `mk_return(db, s, N, of=None, **but)` = "return N" (`of="W0"` / `of="W2"` = "of W0" / "of W2"); `mk_line(db, s, R, **but)` = "line on R". The columns after "but" are passed as keywords, exactly as carded.
- **Clock:** `clock(L, U)` patches `app.dao.sales_order_return.datetime` (a `datetime` subclass whose `now()` returns L), `app.dao.sales_order_return.utcnow` (`create=True`) and `app.utils.time.utcnow` (both return U). Every `CW` card without a clock line runs under `clock(JUNE, JUNE)`; CW-07 and CW-08 patch nothing ("no clock").
- **Reading helpers (no expected values inside):** `reread` (expire, then SELECT by id), `snap` (every mapped column of the re-read row, for "unchanged"), `n(W)`, `totals` ("nothing written": counts of both tables), `ids`, `idset`.
- **Statement recorder:** a `before_cursor_execute` listener on the session's connection, around the When only. `sql` is the one SELECT sent (it fails loudly if there is not exactly one); `order_part` / `lock_part` / `written` as the Conventions define them. The no-lock Then lines use `"FOR UPDATE" not in sql` (Revision 3); `lock_part` is kept for the Conventions but no test asserts on it.
- **Errors:** `pytest.raises(IntegrityError)` around `db.begin_nested()`, so the session stays usable for the counts and re-reads afterwards.
- **Cards whose Then 1 is the When itself** (CW-12, CW-13, CW-14: "the call raises IntegrityError 23505"): the `# Then 1` comment sits directly above the call, so the failure point maps to Then 1.

## xfail location (`--runxfail`)
Plugin `failson.py` (`-p failson`, scratch `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omde\B\`) records the failing test line and its `# Then N`. Result: 12 failed, 74 passed. Each xfail fails on the Then line its card names:

| Card | Strict | Card says | Fails on | Actual |
|---|---|---|---|---|
| CW-09 | yes | Then 2 | Then 2 | `'SR-2027-001' == 'SR-2026-001'` (local year) |
| CW-10 | yes | Then 2 | Then 2 | `'SR-2026-002' == 'SR-2027-001'` (local year, so A counts) |
| CW-12 | yes | Then 1 | Then 1 | `UniqueViolation` on `sales_order_returns_return_number_key` |
| CW-13 | yes | Then 1 | Then 1 | the same |
| CW-14 | yes | Then 1 | Then 1 | `UniqueViolation`: the count gives -004, which C holds |
| BS-09 | no | Then 2 | Then 2 | `[D, B, C, A]` vs `[D, C, B, A]` |
| BS-10 | no | Then 2 | Then 2 | `[B, C, A]` vs `[C, B, A]` |
| BS-11 | yes | Then 4 | Then 4 | `'.id' in ' sales_order_returns.created_at DESC'` |
| OP-07 | no | Then 2 | Then 2 | `[B, C, A]` vs `[A, B, C]` |
| OP-08 | yes | Then 2 | Then 2 | no `ORDER BY` |
| RI-07 | no | Then 2 | Then 2 | `[A, C, B]` vs `[A, B, C]` |
| RI-08 | yes | Then 2 | Then 2 | no `ORDER BY` |

**Reference plugin** `ref_srt.py` (same folder, `-p ref_srt`) replaces the methods in-process with the intended behaviour: year from `utcnow()` (BUG-2422); skip a number already taken in the workspace (BUG-2421 R3a); `ORDER BY created_at DESC, id DESC` (BUG-2423); `ORDER BY id` for open returns and lines (BUG-2424, BUG-2425). For BUG-2420 its autouse fixture drops `sales_order_returns_return_number_key` and creates a unique index on `(workspace_id, return_number)` inside each test's own transaction, which the rollback undoes. With `--runxfail`: **86 passed**, so every Then past a failure point holds on fixed code, and CW-21 (same-workspace 23505) holds under the per-workspace index. Nothing in `app/` changes.

## Discrepancies
None.

## Coverage gaps
None — 100% line and branch coverage (private `COVERAGE_FILE`). Inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None (all builders are local).

## Stability
| Run | Passed | xfailed | xpassed (non-strict) | Not as designed |
|---|---|---|---|---|
| Default, runs 1–3 | 74 | 12 | 0 | 0 |
| Database `TimeZone` `America/New_York` | 74 | 12 | 0 | 0 |
| Database `TimeZone` `Asia/Dhaka` | 74 | 12 | 0 | 0 |
| `enable_seqscan=off` | 74 | 11 | 1 (OP-07) | 0 |
| `enable_sort=off` | 74 | 12 | 0 | 0 |
| index and bitmap scans off | 74 | 12 | 0 | 0 |
| `--runxfail` | 74 | — | — | 12 failed, each at its card's Then |
| `--runxfail` with the reference plugin | 86 of 86 | — | — | 0 |

`PGOPTIONS` carried the session settings. `ruff check`: all checks passed; `ruff format`: formatted. Line endings: LF. The header `noqa` covers SIM117 (the Conventions' nested `with pytest.raises` / `with db.begin_nested()`) and DTZ001 (naive datetimes).

## Notes for maintainers
- When BUG-2420, 2421 (R3a), 2422 are fixed, CW-09, CW-10, CW-12, CW-13, CW-14 XPASS and fail strict: remove their markers. BUG-2420 needs a migration (per-workspace unique index). CW-21 stays true under either fix.
- When BUG-2423/2424/2425 are fixed, BS-11, OP-08 and RI-08 XPASS (strict): remove their markers. Remove the non-strict markers of BS-09, BS-10, OP-07 and RI-07 at the same time; they then pass on every plan.
- `SalesOrderReturnItem.item` is `lazy="joined"`, so the `get_by_return` SELECT carries a `LEFT OUTER JOIN items`. RI-10 only checks that `sales_order_returns` is not read.
- Return numbers in the cards are fixed strings, and the unique index is global today. Two sessions running these tests at the same moment would wait on each other's uncommitted numbers (never fail, since both roll back).

## Revision history
- **Revision 2 (2026-11-10):** first execution of this cases file (the file was written fresh against Revision 2; no earlier test file existed).
- **Revision 3 (2026-11-10):** patched, not regenerated (verify finding 1, convention). SRT-GN-16, BS-14, OP-10, IV-09, RI-10: the no-lock line `rec.lock_part == ""` became `"FOR UPDATE" not in rec.sql`; nothing else changed (the cards' Givens add no `expunge_all`, so none was added). Re-run: 3 plain runs 74 passed / 12 xfailed each; `--runxfail` 12 failed on the same Thens as Revision 2; reference plugin `ref_srt.py` with `--runxfail` 86 / 86; coverage 100%; ruff check and format clean; LF. Lock-everything variant (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omde\B\var_b.py`, `VARIANT=lockall`: every read gets `.with_for_update()`, the count inside a locked subquery, `OF` the queried table): exactly the five no-lock lines fail (5 failed, 69 passed, 12 xfailed); under Revision 2 this variant survived. Hard-coded-2026 variant (`VARIANT=year2026`): SRT-CW-11 fails at Then 2 (and strict CW-09 XPASSes, since that bug case wants 2026).
