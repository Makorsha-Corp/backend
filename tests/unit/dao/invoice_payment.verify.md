# Verification — `app/dao/invoice_payment.py`

> **Verdict:** PASS
> Tests: 74 passed · 8 xfailed (reproduced ✅) · coverage 96% branch (line 76 missed: dead `get_by_date_range`)
> Mutation: 26 mutants · 18 killed · 8 survived → score 100% (after excluding 2 equivalent, 6 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
These tests can be trusted. Every one of the 82 cards has exactly one test, and the markers match the Expect lines. The setups, Whens and Thens follow the cards: the assertions are exact, rows are re-read from the database, there are no extra mocks and no swallowed errors. All three runs and the `--runxfail` run match the notes, and each xfail fails on its card's "Fails today on" line. Every mutant that survived is in dead code or equivalent. Of the 16 hand variants, all 16 were killed: no ORDER BY, ascending order, id-only order, no workspace filter, inner join, a row lock, joining on the voider, counting voided payments, no workspace filter on the total, a float total, a total of `0` with no decimals, `None`, and a whole-number total. Nothing to fix.

## Findings
None.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 4 | 76 | `return None` | dead | `get_by_date_range`: no caller in `app/`, `scripts/` or `tests/` (grep, verified); spec Q1 says remove; on the dead-code checklist | — |
| 9 | 60 | `skip` default 0 → 1 | dead | same method | — |
| 10 | 60 | `limit` default 100 → 101 | dead | same method | — |
| 22 | 79 | `==` → `!=` (workspace) | dead | same method | — |
| 23 | 80 | `>=` → `>` | dead | same method | — |
| 24 | 81 | `<=` → `<` | dead | same method | — |
| 19 | 45 | label `'created_by_name'` → `''` | equivalent | the label name is never read: the row is unpacked by position (`payment, name = row`), so an anonymous label returns the same tuple | — |
| 26 | 27 | label `'created_by_name'` → `''` | equivalent | same reason: `[(payment, name) for payment, name in rows]` reads by position | — |

Hand variants (own plugin `omdv\A\hv_a.py`, in-process, run with `-m "not xfail"`). All 16 were killed. The killing tests in brackets:
- **`get_by_invoice`:**
  - no ORDER BY (GI-01, 14, 15, 23–25, 28)
  - `payment_date` ascending (GI-01, 12, 14, …)
  - `id DESC` only (GI-01, 12, 14, …)
  - no workspace filter (GI-05, 06, 07, 11, 32)
  - inner join (GI-12, 20)
  - `FOR UPDATE OF` (GI-21)
  - joined on `voided_by` (GI-01, 02, 12, 13, 20)
- **`get_by_id_and_workspace_with_creator`:**
  - no workspace filter (GC-06, 07)
  - inner join (GC-04, 11)
  - joined on `voided_by` (GC-01 …)
- **`get_total_paid_for_invoice`:**
  - voided payments counted (TP-01, 03, 04, 22)
  - no workspace filter, so W0 and W2 rows sit on the invoice (TP-07, 08, 09)
  - float round trip (TP-01, 12, 15)
  - `Decimal("0")` with no decimals (TP-02, 03, 05, 11, 13)
  - `None` (TP-02, 03, 05, 06)
  - whole-number total (TP-01, 04, …)

## Traceability
82 cards · 82 tests (82 functions, none parametrized) · unmatched: none · tests without a card ID: none · marker mismatches: none. The 8 xfail tests are GI-16/17/18 (BUG-600, non-strict), GI-19 (BUG-600, strict) and CR-07 … CR-10 (BUG-2400, strict). Both bugs exist in `bugs.md`, and every reason names its bug.

`--runxfail` failing lines, each as the card says:
- GI-16/17/18 fail at Then 2.
- GI-19 fails at Then 4 (`"invoice_payments.id" in order_part`).
- CR-07 and CR-08 fail at Then 2.
- CR-09 and CR-10 fail at Then 3.

Not one of them is a setup or import error.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_invoice_payment.py -q -p no:cacheprovider -o addopts="" --cov=app.dao.invoice_payment --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  run 1: 74 passed, 8 xfailed in 7.32s · app\dao\invoice_payment.py 24 stmts 1 miss 2 branch 0 partial 96% Missing 76
  run 2: 74 passed, 8 xfailed in 7.27s
  run 3: 74 passed, 8 xfailed in 7.41s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_invoice_payment.py -q -p no:cacheprovider -o addopts="" --runxfail -rf --tb=line
  8 failed, 74 passed in 4.12s
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/invoice_payment.py tests/unit/dao/test_invoice_payment.py --json <scratch>/omdv/invoice_payment.mut.json
  Mutants: 26 · killed 18 · timeout 0 · survived 8 · score 69%
HV=<variant> .venv/Scripts/python.exe -m pytest tests/unit/dao/test_invoice_payment.py -q -p no:cacheprovider -o addopts="" -p hv_a -m "not xfail"   (PYTHONPATH=<scratch>/omdv/A)
  base 74 passed; 16 / 16 variants killed
grep for callers of get_by_date_range on invoice_payment_dao in app/ scripts/ tests/  → none (dead claim confirmed)
```
