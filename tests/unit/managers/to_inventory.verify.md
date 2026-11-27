# Verification — `app/managers/to_inventory.py`

> **Verdict:** PASS
> Tests: 100 passed · 26 xfailed (after the 2026-10-30 note below; the audit below ran at 102 passed · 24 xfailed, every xfail failing under `--runxfail` on its "fails today on" assertion) · coverage 100% branch (42 stmts, 16 branches)
> Mutation: 61 mutants · 57 killed · 4 survived → score 100% (after excluding 4 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 (`app/managers/to_inventory.py` unmodified in the working tree) · Cases revision: 4 (audit below ran at revision 3; see the 2026-10-30 note)
> Verify round: 4 (scoped re-verify after the executor's round-3 fix; supersedes round 3's NEEDS WORK)

## Summary
These tests can be trusted. The executor fixed all six round-3 findings by adding exactly the assertions each case's Then names. No case or spec row changed, so this round re-read only the ten edited tests. Traceability is still clean. The runs match the notes and give the same result on every repeat, and every xfail still fails on its intended assertion. The four surviving mutants are the same four equivalent mutants as before. No mutant changed coverage, since the fix only added assertions.

## Findings
None open.

Resolved from round 3:
| # | Kind | Case / line | What was wrong | Resolution | Status |
|---|---|---|---|---|---|
| 1 | Missing assertion | TOI-P-13 | `transaction_type == "transfer_out"` not asserted on the L1 row | L2357 `assert out_rows[0].transaction_type == "transfer_out"` | resolved |
| 2 | Missing assertion | TOI-P-14 | `transaction_type == "transfer_out"` not asserted | L2377 `assert out_rows[0].transaction_type == "transfer_out"` | resolved |
| 3 | Missing assertion | TOI-P-04 | F2 row `transaction_type == "transfer_in"` not asserted | L2137 `assert_fields(f2_row, transaction_type="transfer_in", unit_cost=0, avg_price_after=Decimal("2.00"))` | resolved |
| 4 | Missing assertion | TOI-P-05 | `factory_id`/`transaction_type` not asserted on DAMAGED row | L2155–2156 adds `transaction_type="transfer_in", factory_id=f2.id` | resolved |
| 5 | Missing assertion | TOI-P-03 | `factory_id == f2.id` not asserted on the transfer_in row | L2114 adds `factory_id=f2.id` | resolved |
| 6 | Weakened assertion | TOI-OUT-04, OUT-10, OUT-25, OUT-28, IN-05 | "no activity event" checked against one machine only | L896, L1013, L1268, L1314, L1498 now `db.scalar(select(func.count()).select_from(MachineActivityEvent)) == 0`. This checks the whole table and is stricter than a before/after delta. It matches P-06 | resolved |

Observation (not a finding, batch mode): BUG-820..BUG-826 are still not in `docs/testing/bugs.md`. They are staged in `tests/unit/managers/to_inventory.bugs-staging.md` for the batch merge agent. The xfail reasons name the right IDs.

Fidelity scope: the ten tests changed in notes round 3 (P-03, P-04, P-05, P-13, P-14, OUT-04, OUT-10, OUT-25, OUT-28, IN-05) were re-read in full against their cases. None of them adds a mock, a `try/except`, or a looser check. The other 111 tests and all case rows are unchanged since round 3's full audit (cases Revision 3; the file is dated 2026-09-30), so that audit still applies to them.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 19 | L73 | `raise` → `pass` (unsupported source type) | equivalent | `item_name()` only reads. `post_stock_out` (inventory_movements.py L405–408) then raises the identical 400 `"Unsupported source location type: {location_type}"` before any write | — |
| 23 | L118 | `raise` → `pass` (unsupported destination type) | equivalent | The L112 guard still catches 'project'. Any other type reaches `post_stock_in` (L468–471), which raises the identical 400 `"Unsupported destination location type: ..."` before any write | — |
| 34 | L92 | `activity_event_type='transfer_out'` → `''` | equivalent | `post_stock_out` passes `activity_event_type or transaction_type` (L402), so `''` falls back to `'transfer_out'` | — |
| 39 | L138 | `activity_event_type='transfer_in'` → `''` | equivalent | `post_stock_in` passes `activity_event_type or transaction_type` (L464), so `''` falls back to `'transfer_in'` | — |

The other 57 mutants were killed in round 3's full run. This round's fix only adds assertions and changes no code paths, so those results carry over.

## Traceability
- Cases: 121. Test functions: 121, collected as 126 pytest items because IN-29 and IN-35 are parametrized.
- Unmatched: none. Duplicates: none.
- Marker mismatches: none (AST check). All 24 xfail cases use `xfail(strict=True)` with a reason that names their BUG ID, and the 97 pass cases have no marker.
- BUG IDs used: 820, 822, 823, 824, 826. All are staged; none are in `bugs.md` yet (see the observation above).

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_to_inventory.py -q -p no:cacheprovider --cov=app.managers.to_inventory --cov-branch --cov-report=term-missing
  app\managers\to_inventory.py   42   0   16   0   100%
  102 passed, 24 xfailed, 15 warnings in 13.82s
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_to_inventory.py -q -p no:cacheprovider --runxfail -rf --tb=line
  24 failed, 102 passed in 5.01s
  (same 24 xfail tests, same failure points as round 3: Q-13..18 and IN-30..32/34/36..38/42 "DID NOT RAISE ValidationError";
   OUT-13/14/26/27 detail mismatch; OUT-16/29 no FOR UPDATE; OUT-19/32, IN-18/27 "DID NOT RAISE HTTPException")
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_to_inventory.py -q -p no:cacheprovider   (repeat)
  102 passed, 24 xfailed in 6.58s   (matches notes; no flakiness)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/to_inventory.py tests/unit/managers/test_to_inventory.py --lines 73-73 --timeout 180
  Mutants: 1 · killed 0 · survived 1 — L73:8 raise -> pass
  ... --lines 92-92    Mutants: 1 · survived 1 — L92:28 'transfer_out' -> ''
  ... --lines 118-118  Mutants: 1 · survived 1 — L118:8 raise -> pass
  ... --lines 138-138  Mutants: 1 · survived 1 — L138:28 'transfer_in' -> ''
```

## Note, 2026-10-30 — BUG-1040, not a new verify round
The owner ruled that all money rounds half away from zero (HR-15). Spec R5 split into R5 and R5a, R6a added, G2 updated; cases revision 4.
- TOI-IN-08 now expects `1.03` as a strict xfail BUG-1040. Under `--runxfail` it fails on `avg_price_after: expected Decimal('1.03'), got Decimal('1.02')`, the card's "fails today on".
- TOI-IN-39 now expects `total_cost 0.13` as a strict xfail BUG-1040. Under `--runxfail` it fails on `total_cost: expected Decimal('0.13'), got Decimal('0.12')`, the card's "fails today on".
- Counts: cases 121 (95 `pass` · 26 `xfail`) · test functions 121, collected as 126 pytest items (100 passed · 26 xfailed). Coverage 100% branch (42 stmts, 16 branches).
- Mutation was not re-run; the figures above predate this change. The rounding lives in `app/managers/inventory_movements.py`, not in the module mutated here.
- Commands: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_to_inventory.py -q -p no:cacheprovider --tb=no --cov=app.managers.to_inventory --cov-branch --cov-report=term-missing` → `100 passed, 26 xfailed`.
