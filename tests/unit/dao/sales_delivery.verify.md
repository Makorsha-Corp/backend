# Verification — `app/dao/sales_delivery.py`

> **Current verdict: PASS (round 2, 2026-11-10, cases revision 3): finding 1 is closed. See "Round 2" at the end.**
>
> **Verdict:** NEEDS WORK (amended by the batch verifier, 2026-11-10: Finding 1, a case-designer item; the tests are faithful). It was PASS before the cross-module lock check.
> Tests: 71 passed · 12 xfailed (reproduced ✅) · coverage 96% branch (line 127 missed: dead `get_by_date_range`)
> Mutation: 23 mutants · 17 killed · 6 survived → score 100% (after excluding 0 equivalent, 6 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
These tests can be trusted. Every one of the 83 cards maps to exactly one test or `pytest.param` id; there are 70 functions, and 8 of them group cards that share a setup. Setups, Whens and Thens match the cards. The cards' raw `for k …` loops and the `create_with_user` calls go through small helpers that add nothing of their own. Only the clock named in the Conventions is patched. Writes are re-read from the database. All three runs and `--runxfail` match the notes.

Every surviving mutant is in the dead `get_by_date_range`. The hand variants below were tried. Each was killed, except the two lists sorted `id DESC`: their order is BUG-2442 / BUG-2443, which only the xfail cards check, so they are bug-path.
- **Numbering:**
  - counted across all workspaces (global)
  - `ILIKE` (case-insensitive prefix)
  - no dash after the year
  - highest number + 1 instead of a count (a taken number)
  - 4-digit padding
- **Year:**
  - from the real clock
  - a fixed 2026
- **Fields:**
  - `notes`, `scheduled_date` or `tracking_number` dropped
  - creator dropped
- **Lists:**
  - no workspace filter, with W0 and W2 rows on both sides
  - a cap on the order list
  - case-insensitive status
  - status list not paged

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing (convention) | the card at `sales_delivery.cases.md` line 290 (Then 3 `lock_part == ""`), and Conventions "lock_part" | `lock_part` is defined as the text of `sql` *after* `FOR UPDATE`. A plain `FOR UPDATE` is the last clause Postgres prints, so `lock_part == ""` holds whether or not a lock is taken: the no-lock check is vacuous. No other pass card catches a stray lock. Change the convention, or the Then line, to `"FOR UPDATE" not in sql`. Add it to every card of a read the spec says takes no lock. | Batch verifier's variant `omdv\PT\plug\lockall.py`: every ORM query on `SalesDelivery` gets `.with_for_update()` (plain, and `of=SalesDelivery`). **71 passed** both ways. Same finding as the sales_order_return, misc-cost and ledger verifies. | **case designer** |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 5 | 127 | `return None` | dead | `get_by_date_range`: no caller in `app/`, `scripts/` or `tests/` (grep, verified; `get_by_status` *is* called from `sales_service.py:810` and is tested); spec Q1 says remove | — |
| 9 | 123 | `skip` default 0 → 1 | dead | same method | — |
| 10 | 124 | `limit` default 100 → 101 | dead | same method | — |
| 21 | 130 | `==` → `!=` (workspace) | dead | same method | — |
| 22 | 131 | `>=` → `>` | dead | same method | — |
| 23 | 132 | `<=` → `<` | dead | same method | — |

Line 62 (`datetime.now().year`) has no operator for `mutate.py` to change, so it gets no mutant; the hand variants covered it. A real-clock year and a fixed year 2026 are both killed by CW-10, whose clocks are both in 2031.

Hand variants (own plugin `omdv\A\hv_a.py`, `-m "not xfail"`), with the killing tests:
- **`generate_delivery_number`:**
  - global count: GN-05, 06, 07, CW-04, CW-24
  - `ILIKE`: GN-12, GN-16
  - no separator: 21 tests
  - max + 1: GN-07, GN-11, CW-07
  - `04d` padding: 20 tests
- **`create_with_user`:**
  - real `datetime.utcnow()` year: CW-10
  - fixed 2026: CW-10
  - `notes` dropped: CW-01, CW-20
  - `scheduled_date` dropped: CW-01
  - `tracking_number` dropped: CW-01, CW-20
  - `created_by` None: 17 tests
- **`get_by_sales_order`:**
  - no workspace filter: SO-03, SO-04
  - paged at 100: SO-08
  - `id DESC`: survived, bug-path (BUG-2442; SO-09/10/11 are xfail)
- **`get_by_status`:**
  - `lower()` compare: ST-02, ST-05
  - no workspace filter: ST-11, 12, 22
  - not paged: 7 tests
  - `id DESC`: survived, bug-path (BUG-2443; ST-23/24/25 are xfail)

## Traceability
83 cards · 70 test functions, 83 case IDs (8 functions group cards with `pytest.param(id=…)`): GN-03/04, CW-13/14, CW-17/18/19, SO-05/06/07, ST-02/03/04/06/07/08, ST-16/17, ST-19/20. Unmatched: none. Marker mismatches: none.
- CW-13/14 are xfail BUG-722 through the decorator on the grouped function. That is right, because both cards are xfail.
- The other markers:
  - CW-05/06: BUG-726, strict
  - CW-08/09: BUG-2440, strict
  - SO-09/10: BUG-2442, non-strict
  - SO-11: BUG-2442, strict
  - ST-23/24: BUG-2443, non-strict
  - ST-25: BUG-2443, strict
- Every BUG ID is in `bugs.md`.

`--runxfail` (12 failed), each on its card's line:
- CW-05/06 fail at Then 1 with `IntegrityError` on `ix_sales_deliveries_delivery_number` (duplicate key).
- CW-08/09 fail at Then 2 on the year.
- CW-13/14 fail at Then 2 with `"shipped"` / `"delivered"` stored.
- SO-09, SO-10 and ST-23 fail at Then 2 (the bumped row comes last).
- ST-24 fails at Then 2.
- SO-11 and ST-25 fail at Then 2 (`"ORDER BY" in sql`).

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_sales_delivery.py -q -p no:cacheprovider -o addopts="" --cov=app.dao.sales_delivery --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  run 1: 71 passed, 12 xfailed in 10.18s · app\dao\sales_delivery.py 26 stmts 1 miss 0 branch 96% Missing 127
  run 2: 71 passed, 12 xfailed in 9.98s
  run 3: 71 passed, 12 xfailed in 10.16s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_sales_delivery.py -q -p no:cacheprovider -o addopts="" --runxfail -rf --tb=line
  12 failed, 71 passed in 4.61s
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/sales_delivery.py tests/unit/dao/test_sales_delivery.py --json <scratch>/omdv/sales_delivery.mut.json
  Mutants: 23 · killed 17 · timeout 0 · survived 6 · score 74%
HV=<variant> pytest … -p hv_a -m "not xfail"   base 71 passed; 18 variants, 16 killed, 2 bug-path
grep for callers of get_by_date_range on sales_delivery_dao in app/ scripts/ tests/  → none (dead claim confirmed)
```

## Round 2 — 2026-11-10
Narrow re-check of cases revision 3 (patched, not regenerated). **Verdict: PASS.**

**Changed cards:** SDV-GN-14: the no-lock line is now Then 2 `"FOR UPDATE" not in sql`, and the vacuous `lock_part == ""` is gone. No card needed `expunge_all`.

**Fidelity:** GN-14 matches its card exactly (two Thens). **0 unfaithful.**

**Runs:** 71 passed, 12 xfailed ×3 · coverage 96% branch (line 127, dead `get_by_date_range`) · `--runxfail` 12 failed, 71 passed. No flaky outcome. Runs (private `COVERAGE_FILE`, `omdv\R2\.cov`): `pytest <file> -q -p no:cacheprovider -o addopts=""` with `--cov=app.dao.<module> --cov-branch` once, plain twice, then `--runxfail` once.

**Variants:**
- Lock in `generate_delivery_number` (OF and plain): killed. GN-14 and 33 create cards fail, since every create calls it.
- Year hard-coded 2026 in `create_with_user`: killed by SDV-CW-10.
- Not a finding: a lock in `get_by_sales_order` or `get_by_status` survives (71 passed). The spec has no no-lock rule for those two: R5 "reads only and takes no lock" is on `generate_delivery_number` only, and HR-10 neither asks for a lock nor forbids one. If the describer ever states a no-lock rule for them (as the other DAOs' Overviews do), cards are needed then.

Variants: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\plug\r2var.py` (per-method `FOR UPDATE OF <table>` and plain `FOR UPDATE`; create's year hard-coded 2026, bypassing the tests' clock patch; a hidden `db.get` of the parent), driven by `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\run_r2.py` on the pass tests (`-m "not xfail"`); results in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\r2.txt`. `mutate.py` was not re-run: Revision 3 only adds assertions and one card, so no mutant killed in round 1 can survive now.

**Open items:** None. (Optional for the describer's next pass: say whether `get_by_sales_order` / `get_by_status` take no lock.)
