# Execution notes — `app/dao/expense_order.py`

> Cases: `tests/unit/dao/expense_order.cases.md` (revision 3) · Tests: `tests/unit/dao/test_expense_order.py` · Source commit: e48a092
> Result: 203 passed · 47 xfailed · 2 xpassed (non-strict) · 0 discrepancies · 0 errors — branch coverage 99%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_expense_order.py -q -p no:cacheprovider -o addopts=""`

## How the tests are built
- **One test per case**, in card order, each below a `# [claude] <ID>` comment (normal mode, no local model). Cases that share setup and assertions and differ in one input are parametrized with the case ID as the param id: CL-01 … 08, DB-01 … 07, DW-02 … 06, HF-27/28, HF-45/46, UP-08/09, NX-02 … 06 + 08, NX-07/09, NX-10 … 12, NX-14 … 18, GO-03/04. 252 collected items = 252 case IDs, each exactly once.
- **Standing rows** → fixture `g` (W0, W1, W2 via `make_workspace`; U1 … U3 via `make_profile`; accounts A0, K1, K2, K3, A2 with the carded names, each flushed). Every test requests `g`, also the pure-function ones (the Conventions say every test has them).
- **Given rows** → fixtures `order(N, k=1, completed=False, voided=False, **but)` (stores `GN(N)`), `numbered(N, …)` (exact number, `NX` cards), `row(N, …)` (unflushed, for the "flushing once after the loop" Givens), `inv(k, amount, state=None|"confirmed"|"locked"|"invvoid", **but)`, `deleted_account(name)` (all four soft-delete columns), `line(O, n, **but)`. `completed` / `voided` / `invvoid` write exactly the Conventions' columns. Each builder flushes.
- **GN(n)** = `f"{n}-{os.getpid()}"`; expense numbers are globally unique today (BUG-749), so parallel runs never clash. Only `NX` cards store exact `EXP-2031-…` / `EXP-2032-…` numbers; no other fork's module writes `expense_orders`.
- **Clocks**: `clockN(L, U)` patches `datetime.datetime` with a subclass whose `now()` returns L (the DAO imports `datetime` inside `get_next_number`) and `app.dao.expense_order.utcnow`; every `NX` When runs under it (default JUNE, JUNE), also NX-25/26/27. `clockD(U)` patches `app.dao.expense_order.utcnow` only, default NOWX, around every `DW`, `SA`, `UP`, `OQ43`, `OQ44` When. `app.utils.time` binds its own `datetime`, so row defaults are unaffected by clockN.
- **Statement recorder**: `before_cursor_execute` on the session's connection; `sql` = the one SELECT naming `expense_orders` (or `expense_order_items` for `GO` / `II`); `order_part` = text after the first `ORDER BY`, before `LIMIT`. SF-07 / SF-13 pick the SELECT that contains `GROUP BY expense_orders.expense_category` / `GROUP BY expense_orders.account_id`; UP-07 takes the first SELECT naming `account_invoices` (card text).
- **seqscan** cards (GW-15, RC-07, SF-06, SF-12, SF-23, UP-06, GO-07) set the three `enable_*scan = off` and `db.expire_all()` as carded; ids are captured before the expire. `HIGH_ID(table)` = `GREATEST(MAX(id), last_value of <table>_id_seq) + 1000001`.
- **IntegrityError** (NX-26): `pytest.raises` around `db.begin_nested()` then `pgcode == "23505"`.

## Expected-to-fail check (`--runxfail`, `-p thenmap`, a scratch plugin that maps each failure to its `# Then N` block)
47 failed, 205 passed (Revision 3). Every strict xfail fails on the Then line named in its "Fails today on". The one that fails before any Then is **EXO-NX-27**: the `flush` in the When raises `IntegrityError` 23505 on `ix_expense_orders_expense_number`. The card itself says this: "Fails today on: Then 1 (the call raises IntegrityError …)". The non-strict GW-15, RC-07, SF-12, UP-06 and GO-07 fail on Then 1. Under `--runxfail`, SF-06 and SF-23 passed (see Stability).

## Reference plugin
`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaoe\eo\ref_eo.py` (`PYTHONPATH=<that folder> … -p ref_eo`). It replaces the following in process, and nothing in `app/` changes:
- the hub filter: escaped `ILIKE` (BUG-745); the account join requires the same workspace and `is_deleted = false` (BUG-2714, BUG-2715);
- `get_by_workspace`: sorts by `created_at DESC, id DESC` (BUG-2711);
- `list_recent_for_hub`: sorts by `COALESCE(updated_at, created_at) DESC, id DESC` (BUG-746);
- `aggregate_hub_stats`: leaves voided orders out of the money figures and the open figures (BUG-2717);
- `aggregate_financial_snapshot_filtered`: leaves voided orders out; sorts ties by category, then by `lower(name)` and account id; joins only accounts of the same workspace (BUG-2717, 2712, 747, 2714);
- `aggregate_financial_snapshot_actionable`:
  - pipeline: orders completed or not, with a confirmed or locked invoice of the same workspace, sorted by outstanding `DESC`, then `expense_orders.id ASC` (BUG-2718, 2714, 748);
  - timeline: orders completed or not, at what is still to pay; an order with nothing left to pay, or with a paid invoice, is left out (BUG-2719);
- `get_next_number`: the year comes from `utcnow()`, and the next number is the numeric maximum of the all-digit suffixes plus one (BUG-2710, 749);
- `get_by_order`: sorts by `line_number, id` (BUG-2713).

For EXO-NX-27 an autouse fixture swaps the global unique index for a non-unique one inside the test's own transaction (undone by the rollback). With `--runxfail`: **252 passed** (Revision 3; the plugin needed no change for the new cards).

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 466 (`if status not in unpaid_buckets: continue`) | unreachable | The SQL already restricts `payment_status` to `unpaid` / `partial` / `overdue`, which are exactly the bucket keys, so the guard can never be true. |

Branch coverage 99% (187 statements, 1 missed; 70 branches, 1 partial). Inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None (all builders are local).

## Stability
| Run | Passed | xfailed | xpassed (non-strict) | Not as designed |
|---|---|---|---|---|
| plain 1 | 203 | 47 | 2 | 0 |
| plain 2 | 203 | 47 | 2 | 0 |
| plain 3 | 203 | 47 | 2 | 0 |
| coverage run | 203 | 47 | 2 | 0 |
| `--runxfail` | 205 | — | — | 47 failed, each on its named Then (NX-27 in the When, as carded) |
| `--runxfail` with the reference plugin | 252 of 252 | — | — | 0 |

The two non-strict XPASSes are SF-06 (BUG-2712) and SF-23 (BUG-747). The physical order of these rows happens to give the intended order today. They were stable across all runs and are allowed by `strict=False`. `ruff check` and `ruff format --check` are clean (the header `noqa` adds FURB157 for the `Decimal("0")` the cards prescribe). Line endings are LF.

## Notes for maintainers
- When BUG-745, 2714, 2715, 2717, 2718, 2719, 2710 and 749 are fixed, their strict cards XPASS and fail: remove those markers. BUG-749's NX-27 also needs the migration that drops `ix_expense_orders_expense_number`. After that, `GN()` is no longer needed for parallel safety.
- When BUG-2711, 746, 747, 748, 2712 and 2713 are fixed, the strict SQL-alarm cards (GW-16, RC-08, SF-07, SF-13, UP-07, GO-08) XPASS: remove their markers, together with the non-strict tie cards (GW-15, RC-07, SF-06, SF-12, SF-23, UP-06, GO-07).
- clockN patches `datetime.datetime` process-wide for the duration of the When only. Keep it tight around the call.
- `count_for_hub`'s siblings print `SAWarning: Coercing Subquery object into a select()`. The spec notes this as harmless.

## Revision history
- **Revision 2 (2026-11-14):** first execution of this cases file: 245 cases, 197 passed, 46 xfailed and 2 non-strict xpassed (SF-06, SF-23). 99% branch coverage. Reference plugin with `--runxfail`: 245 / 245.
- **Revision 3 (2026-11-14):** cases revision 3, from verify findings 1–5 (`case-missing`). Seven tests were added in card order: HF-50 after HF-49; SF-24 and SF-25 after SF-23; SA-13 after SA-12; UP-13 and UP-14 after UP-12; and OQ44-10 after OQ44-09 (strict xfail BUG-2719, fails on Then 1). The existing tests are unchanged; only the header comment now cites revision 3. No ID was retired.
  - 3 plain runs: 203 passed · 47 xfailed · 2 xpassed (non-strict SF-06, SF-23) each time.
  - `--runxfail`: 47 failed, each on its named Then (NX-27 in the When, as carded).
  - Reference plugin `ref_eo.py` with `--runxfail`: 252 / 252. It was unchanged, because its BUG-2719 timeline already counts a voided invoice at the order total.
  - Coverage: 99% branch, the same unreachable line 466.
  - ruff check and format clean; LF.
