# Verification — `app/managers/po_storage_inventory.py`

> **Verdict:** PASS
> Tests: 1 passed · 0 xfailed (reproduced ✅ — none expected) · coverage 20% branch (100% of reachable code; lines 10-24, 33-38 are spec-listed dead code)
> Mutation: 32 mutants · 1 killed · 31 survived → score 100% (after excluding 0 equivalent, 31 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 1 (READY, source commit e48a092)

## Summary
Re-verified independently on 2026-10-02 (fresh pytest x3, --runxfail, full mutation run with --timeout 180, and a fresh grep of every caller under app/ and tests/). The results are identical to the 2026-09-30 and 2026-10-01 verifications: the same 32 mutants, with the same one killed and the same 31 surviving. The `_quantity_to_int` imports in `tests/unit/managers/test_to_inventory.py` and `test_po_return_inventory.py` come from those modules' own copies, not from this one.
The module's only reachable member is the constant `PO_INVENTORY_SOURCE_TYPE`, and
its single test (POSI-K-01) checks the exact value and exact `str` type; the only
mutant of the constant (`'purchase_order' -> ''`) is killed. All 31 survivors sit
inside `_quantity_to_int` and `_weighted_avg_price`, which the approved spec lists
under "Not specified" as dead code (reviewer answered "remove" on Q1/Q2). I checked
this independently: no module under `app/` imports either helper. The files that call
a `_quantity_to_int` (`to_inventory`, `po_return_inventory`, `product_manager`) each
define their own. The tests can be trusted, and nothing needs to change. The survivors
will go away once the helpers are deleted per `po_storage_inventory.deadcode-staging.md`.

## Findings
None.

## Surviving mutants
All 31 survivors are in lines 10-24 (`_quantity_to_int`) or 33-38 (`_weighted_avg_price`),
the two functions the spec lists as dead code (Q1, Q2 → "remove").

| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 2 | L10 | negate if-condition | dead | `_quantity_to_int`, spec Not specified (Q1) | — |
| 3 | L19 | negate if-condition | dead | `_quantity_to_int` (Q1) | — |
| 4 | L24 | return → None | dead | `_quantity_to_int` (Q1) | — |
| 5 | L33 | negate if-condition | dead | `_weighted_avg_price`, spec Not specified (Q2) | — |
| 6 | L35 | negate if-condition | dead | `_weighted_avg_price` (Q2) | — |
| 7 | L38 | return → None | dead | `_weighted_avg_price` (Q2) | — |
| 8 | L10 | NotEq → Eq | dead | `_quantity_to_int` (Q1) | — |
| 9 | L11 | raise → pass | dead | `_quantity_to_int` (Q1) | — |
| 10 | L19 | LtE → Lt | dead | `_quantity_to_int` (Q1) | — |
| 11 | L20 | raise → pass | dead | `_quantity_to_int` (Q1) | — |
| 12 | L33 | LtE → Lt | dead | `_weighted_avg_price` (Q2) | — |
| 13 | L34 | return → None | dead | `_weighted_avg_price` (Q2) | — |
| 14 | L35 | And → Or | dead | `_weighted_avg_price` (Q2) | — |
| 15 | L37 | return → None | dead | `_weighted_avg_price` (Q2) | — |
| 16 | L19 | const 0 → 1 | dead | `_quantity_to_int` (Q1) | — |
| 17 | L33 | const 0 → 1 | dead | `_weighted_avg_price` (Q2) | — |
| 18 | L34 | Or → And | dead | `_weighted_avg_price` (Q2) | — |
| 19 | L35 | Gt → GtE | dead | `_weighted_avg_price` (Q2) | — |
| 20 | L35 | IsNot → Is | dead | `_weighted_avg_price` (Q2) | — |
| 21 | L36 | Add → Sub | dead | `_weighted_avg_price` (Q2) | — |
| 22 | L35 | const 0 → 1 | dead | `_weighted_avg_price` (Q2) | — |
| 23 | L36 | Mult → Div | dead | `_weighted_avg_price` (Q2) | — |
| 24 | L36 | Mult → Div | dead | `_weighted_avg_price` (Q2) | — |
| 25 | L34 | const 0 → 1 | dead | `_weighted_avg_price` (Q2) | — |
| 26 | L37 | Div → Mult | dead | `_weighted_avg_price` (Q2) | — |
| 27 | L37 | const '0.01' → '' | dead | `_weighted_avg_price` (Q2) | — |
| 28 | L14 | const 'Line ' → '' | dead | `_quantity_to_int` (Q1) | — |
| 29 | L14 | const ' has a fractional re…' → '' | dead | `_quantity_to_int` (Q1) | — |
| 30 | L22 | const 'Line ' → '' | dead | `_quantity_to_int` (Q1) | — |
| 31 | L22 | const ' has no received qua…' → '' | dead | `_quantity_to_int` (Q1) | — |
| 32 | L37 | Add → Sub | dead | `_weighted_avg_price` (Q2) | — |

Killed: #1 L6 const `'purchase_order' -> ''` (caught by POSI-K-01).

## Traceability
cases 1 · tests 1 · unmatched: none · marker mismatches: none (POSI-K-01 is Expect `pass`, and the test has no xfail marker). No BUG IDs are used.
Fidelity: POSI-K-01 asserts `== "purchase_order"` and `type(...) is str`. These are exactly the case's two Then items, with nothing weakened. There are no mocks, try/except blocks or DB setup, which matches the case's Given ("nothing").

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_po_storage_inventory.py -q -p no:cacheprovider --cov=app.managers.po_storage_inventory --cov-branch --cov-report=term-missing
  app\managers\po_storage_inventory.py  17  12  8  0  20%  10-24, 33-38
  1 passed, 15 warnings in 2.40s      (run 2: 1 passed in 2.49s; run 3: 1 passed in 2.50s — stable)
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_po_storage_inventory.py -q -p no:cacheprovider --runxfail -rf
  1 passed in 0.59s                   (no xfail tests)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/po_storage_inventory.py tests/unit/managers/test_po_storage_inventory.py --timeout 180 --json <session scratchpad>/mut_psi.json
  Mutants: 32 · killed 1 · timeout 0 · survived 31 · score 3% (raw; 100% after excluding 31 dead)
grep -rn "_quantity_to_int\|_weighted_avg_price" app tests   → callers in to_inventory, po_return_inventory, product_manager each use their own local `def`; po_machine_inventory has its own copies; no import of this module's helpers, no test references
grep -rn "po_storage_inventory\|PO_INVENTORY_SOURCE_TYPE" app tests   → only po_receive_inventory.py imports the constant (as PO_LEGACY_LINE_SOURCE)
```
The results match the Result line in the notes: 1 passed · 0 xfailed · 20% branch, with lines 10-24 and 33-38 listed as dead.
