# Verification — `app/utils/order_catalog_items.py`

> **Verdict:** PASS
> Tests: 45 passed · 2 xfailed (reproduced ✅) · coverage 100% branch
> Mutation: 24 mutants · 24 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 4

## Summary
Re-verification against cases revision 4. The only new case since the last verification is OCI-M-24, which directly checks that another item's product is never applied. It is implemented as designed: the only product is `P(A, F1, 5)`, a B line of quantity 1 returns `None`, and the DB is unchanged, re-read through `snap()` after `expire_all()`. All 47 cases trace to tests. No assertions are weakened, missing or changed, and nothing is mocked. The two BUG-220 xfails are strict and fail on their documented assertions. Three runs gave the same result, and it matches the notes. The mutation tool killed all 24 mutants. These tests can be trusted, and nothing needs to change.

## Findings
None.

Informational, not a finding. BUG-220 is not yet in `docs/testing/bugs.md`. It is staged in `tests/unit/utils/order_catalog_items.bugs-staging.md` (status open), and batch mode merges it into the shared register later. I accepted the staged row as meeting the "BUG ID exists" check. This is a best-practice default, delegated by the reviewer: in batch mode, per-module agents must not edit shared registers. If the merge does not happen, the xfail reason would point to a missing ID. Whoever merges the bug registers should confirm BUG-220 lands.

## Surviving mutants
None (24/24 killed).

I also reasoned through mutants the tool does not generate. Each one is killed by an existing test:
| Line | Mutation | Killed by |
|---|---|---|
| L34 | drop `seen.add(item_id)` | OCI-U-07 (no 409 raised) |
| L66 | drop `product and` | OCI-M-07 (AttributeError on `None`) |
| L66 | drop `product.min_order_qty and` | OCI-M-15 (TypeError on `None`), OCI-M-16 (−1 < 0 raises) |
| L23 / L60 | `continue` → `break`/`return` | OCI-U-14 / OCI-M-23 (hand-verified in the previous round; tests unchanged) |

## Traceability
Cases: 47. Tests: 47. That is 46 test functions, because OCI-M-04 and OCI-M-05 are `pytest.param` ids of one parametrized test.
- Unmatched: none. Every case ID appears in exactly one test, and every test has a case ID. OCI-M-04 matched twice only because that one test names it in both its docstring and its param id.
- Marker mismatches: none. The 45 `pass` cases have no xfail marker. OCI-U-15 and OCI-D-06 carry `xfail(strict=True, reason="BUG-220: ...")`.

Fidelity: I compared every Then item with its test, including the sentinel and recorder checks (U-06, U-09, M-02, M-21, M-23), the "DB unchanged" snapshots (U-07, U-15, U-16, D-01, D-06, M-03, M-22, M-23, M-24), the cross-workspace isolation cases (U-12, U-13, D-04, D-05, M-09) and the exact 409/422 details. There is no `try/except`, and no `pytest.raises(Exception)`. OCI-M-22 uses `pytest.raises(TypeError)`, as the case specifies.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_order_catalog_items.py -q -p no:cacheprovider --cov=app.utils.order_catalog_items --cov-branch --cov-report=term-missing
  app\utils\order_catalog_items.py      31      0     12      0   100%
  45 passed, 2 xfailed, 10 warnings in 7.98s
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_order_catalog_items.py -q -p no:cacheprovider --runxfail -rf
  FAILED ...::test_oci_u_15__empty_name_falls_back_to_item_id  (assert ' appears mor...on this order' == 'Item #42502 ...on this order')
  FAILED ...::test_oci_d_06__empty_name_falls_back_to_item_id  (assert ' is already on this order' == 'Item #42508 ...on this order')
  2 failed, 45 passed, 10 warnings in 6.96s
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_order_catalog_items.py -q -p no:cacheprovider   (x2)
  45 passed, 2 xfailed, 10 warnings in 6.09s
  45 passed, 2 xfailed, 10 warnings in 7.25s
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/utils/order_catalog_items.py tests/unit/utils/test_order_catalog_items.py --timeout 180 --json %TEMP%/oci_mut.json
  Mutants: 24 · killed 24 · timeout 0 · survived 0 · score 100%
```
The result matches the notes: 45 passed · 2 xfailed, 100% branch coverage. The 10 warnings are Starlette's deprecation notice for `HTTP_422_UNPROCESSABLE_ENTITY`; the status value is still 422.
