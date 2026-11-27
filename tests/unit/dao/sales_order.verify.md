# Verification — `app/dao/sales_order.py`

> **Current verdict: PASS (round 2, 2026-11-10, cases revision 3): findings 1 and 2 are closed. See "Round 2" at the end.**
>
> **Verdict:** NEEDS WORK
> Tests: 67 passed · 9 xfailed (reproduced ✅) · coverage 92% branch (lines 101, 122 missed: dead `get_by_factory` / `get_by_status`)
> Mutation: 22 mutants · 12 killed · 10 survived → score 100% (after excluding 0 equivalent, 10 dead, 0 bug-path); hand variants: 12 tried, 9 killed, 1 bug-path, **2 survived (case-missing)**
> Source commit: e48a092 · Cases revision: 2

## Summary
The tests are faithful. Every one of the 76 cards maps to one test or `pytest.param` id. Setups, Whens and Thens match the cards, money is compared as exact `Decimal`, writes are re-read, and only the Conventions' clock is patched. All three runs and `--runxfail` match the notes. Every `mutate.py` survivor is in dead code.

There is one hole, and it is a missing case. No passing card has a clock whose year is not 2026:
- SLO-CW-05 and the `DEFAULT_CLOCK` cards all use 2026.
- The cards that cross New Year (CW-06 … CW-08, CW-31) are xfail BUG-2440, so they are left out of the run.

So a `create_with_user` that ignores the clock and always uses 2026 passes every passing test. So does one that reads the real, unpatched clock: it is 2026 today, and those tests would only start to fail in January 2027. The delivery cards already cover this with SDV-CW-10 (both clocks in 2031 → `DEL-2031-001`). The order cards need the same card.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `create_with_user` R1 / R2 (source line 75) | Nothing that runs checks that the year comes from the clock: every pass card's clock is in 2026, and the cards with other years are xfail BUG-2440. Add a pass card like SDV-CW-10: clock(`datetime(2031, 1, 1, 0, 30)`, `datetime(2031, 1, 1, 0, 30)`), an order `SO-2026-001` already in W1 → `sales_order_number == "SO-2031-001"`. It holds both today and after the BUG-2440 fix. | hand variants `so_cw_fixed_year` (year always 2026) and `so_cw_utcnow_naive` (real `datetime.utcnow()`): both **67 passed**, nothing failed | **case designer** |
| 2 | case-missing (convention) | the cards at `sales_order.cases.md` lines 365 and 720 (`lock_part == ""`), and Conventions "lock_part" (added by the batch verifier, 2026-11-10) | `lock_part` is the text of `sql` *after* `FOR UPDATE`. A plain `FOR UPDATE` ends the statement, so `lock_part == ""` holds with a lock too: the no-lock check is vacuous. Change it to `"FOR UPDATE" not in sql` on those cards and on every card of a read the spec says takes no lock. | `omdv\PT\plug\lockall.py`: a plain `.with_for_update()` on every `SalesOrder` query passes all **67** tests. `FOR UPDATE OF sales_orders` is caught only by GI-18. | **case designer** |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 4 | 101 | `return None` | dead | `get_by_factory`: no caller of `sales_order_dao.get_by_factory` in `app/`, `scripts/` or `tests/` (grep, verified); spec Q1 says remove | — |
| 7 | 97 | `skip` default 0 → 1 | dead | same method | — |
| 8 | 98 | `limit` default 100 → 101 | dead | same method | — |
| 19 | 104 | `==` → `!=` (factory) | dead | same method | — |
| 20 | 105 | `==` → `!=` (workspace) | dead | same method | — |
| 5 | 122 | `return None` | dead | `get_by_status` of the **order** DAO: no caller (grep, verified; the only `.get_by_status(` call in `app/` is `sales_delivery_dao`'s, in `sales_service.py:810`); spec Q1 says remove | — |
| 9 | 118 | `skip` default 0 → 1 | dead | same method | — |
| 10 | 119 | `limit` default 100 → 101 | dead | same method | — |
| 21 | 125 | `==` → `!=` (status) | dead | same method | — |
| 22 | 126 | `==` → `!=` (workspace) | dead | same method | — |

Hand variants (own plugin `omdv\A\hv_a.py`, run in-process with `-m "not xfail"`), with the tests that killed them:
- **`generate_sales_order_number`:**
  - global count, with W0 and W2 orders on both sides: GN-07, 08, 09, CW-04
  - `ILIKE`: GN-17, GN-25
  - no dash after the year: 29 tests
  - highest number + 1 instead of the count (a taken number): GN-07, 08, 15, 16, 25, CW-22
  - `04d` padding: 28 tests
- **`create_with_user`:**
  - `created_by` None: 24 tests
  - `description` dropped: CW-01
  - `contact_name` dropped: CW-01
  - fixed year 2026: **survived** (finding 1)
  - real `datetime.utcnow()` year: **survived** (finding 1)
- **`get_by_invoice_id`:**
  - no workspace filter: GI-02, 03, 09, 15
  - `ORDER BY id DESC`: survived. This is bug-path: the order is BUG-2441, and only GI-11/12/13 check it, all xfail.

## Traceability
76 cards · 63 test functions, 76 case IDs. Grouped with `pytest.param(id=…)`: GN-03…06, GN-17/18/19/21, CW-10…14, CW-23…26. Unmatched: none. Marker mismatches: none.

The xfail tests:
- GI-11/12: BUG-2441, non-strict
- GI-13: BUG-2441, strict
- CW-06/07/08/31: BUG-2440, strict
- CW-20/21: BUG-726, strict

Every BUG ID is in `bugs.md`.

`--runxfail` (9 failed), each on its card's line:
- GI-11 and GI-12 fail at Then 2 (the wrong id).
- GI-13 fails at Then 2 (`"ORDER BY" in sql`).
- CW-06/07/08/31 fail at Then 2 (the year).
- CW-20/21 fail at Then 1: `IntegrityError` on `ix_sales_orders_sales_order_number` (duplicate key).

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_sales_order.py -q -p no:cacheprovider -o addopts="" --cov=app.dao.sales_order --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  run 1: 67 passed, 9 xfailed in 10.39s · app\dao\sales_order.py 26 stmts 2 miss 0 branch 92% Missing 101, 122
  run 2: 67 passed, 9 xfailed in 10.32s
  run 3: 67 passed, 9 xfailed in 10.56s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_sales_order.py -q -p no:cacheprovider -o addopts="" --runxfail -rf --tb=line
  9 failed, 67 passed in 4.71s
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/sales_order.py tests/unit/dao/test_sales_order.py --json <scratch>/omdv/sales_order.mut.json
  Mutants: 22 · killed 12 · timeout 0 · survived 10 · score 55%
HV=so_cw_fixed_year   pytest … -p hv_a -m "not xfail"  → 67 passed, 9 deselected   (survived)
HV=so_cw_utcnow_naive pytest … -p hv_a -m "not xfail"  → 67 passed, 9 deselected   (survived)
grep for callers of get_by_factory / get_by_status on sales_order_dao in app/ scripts/ tests/  → none (dead claims confirmed)
```

## Round 2 — 2026-11-10
Narrow re-check of cases revision 3 (patched, not regenerated). **Verdict: PASS.**

**Changed cards:** new SLO-CW-34 (both clocks 2031-01-01 00:30, `SO-2026-001` already in W1 → `SO-2031-001`); SLO-GI-18 and GN-23 no-lock lines are now `"FOR UPDATE" not in sql`.

**Fidelity:** CW-34, GI-18 and GN-23 match their cards line by line. CW-34 goes through the shared `create_w1` builder, which is the card's `SalesOrderCreate(…)` and nothing more. **0 unfaithful.**

**Runs:** 68 passed, 9 xfailed ×3 · coverage 92% branch (lines 101, 122, dead) · `--runxfail` 9 failed, 68 passed. No flaky outcome. Runs (private `COVERAGE_FILE`, `omdv\R2\.cov`): `pytest <file> -q -p no:cacheprovider -o addopts=""` with `--cov=app.dao.<module> --cov-branch` once, plain twice, then `--runxfail` once.

**Variants:**
- Year hard-coded 2026: **killed by SLO-CW-34** (the round-1 survivor). The real-clock variant is the same today (it is 2026), so CW-34 kills it too.
- Lock in `get_by_invoice_id` (OF and plain): **killed by GI-18** (plain used to survive). Lock in `generate_sales_order_number`: killed by GN-23 and 49 create cards.

Variants: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\plug\r2var.py` (per-method `FOR UPDATE OF <table>` and plain `FOR UPDATE`; create's year hard-coded 2026, bypassing the tests' clock patch; a hidden `db.get` of the parent), driven by `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\run_r2.py` on the pass tests (`-m "not xfail"`); results in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\r2.txt`. `mutate.py` was not re-run: Revision 3 only adds assertions and one card, so no mutant killed in round 1 can survive now.

**Open items:** None.
