# Verification — `app/managers/po_return_inventory.py`

> **Verdict:** PASS
> Tests: 65 passed · 3 xfailed (reproduced ✅) · coverage 100% branch (40 stmts, 14 branches, 0 partial)
> Mutation: 48 mutants · 48 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path). Carried over from round 2; no mutation re-run was needed in round 3 (see Commands run).
> Source commit: e48a092 · Cases revision: 3 · Verify round: 3 (scoped re-check after executor fix round 2)

## Summary
These tests can be trusted. The only open finding from round 2 was the missing row-count check in PRI-P-10. It is fixed: the test now asserts `len(rows) == 1` before it checks `factory_id` and `quantity`. Traceability is clean (68 cases ↔ 68 tests). The runs match the notes' Result line exactly, and a repeat run gives the same outcome. Every xfail fails on its designed "fails today on" assertion. Round 2 had no surviving mutants, and this fix round changed no source coverage, so the round-2 mutation result (48/48 killed) still holds. No findings are open.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | Missing assertion — **RESOLVED (round 3)** | PRI-P-10 (test lines 825–828) | Round 2: the test never asserted that RI1 has exactly one ledger row. | Now `rows = inv_rows_for(db, ri1)`, then `assert len(rows) == 1`, then `rows[0].factory_id == f1d.id` and `rows[0].quantity == 3`. All three Then items are asserted. | executor (done) |
| R1-1 | Weakened assertion (self-referential constant) — **RESOLVED (round 2)** | PRI-P-01, PRI-P-25 | The tests used the module constant instead of the literal `'purchase_return_item'`. | Both now use the literal. The L15 mutant is killed. | executor (done) |
| R1-2 | Missing assertion — **RESOLVED (round 2)** | PRI-P-33 | The status code was not asserted. | `exc.value.status_code == 400` | executor (done) |

No findings are open.

Observations carried over from round 2 (not findings, no action required):
- The MLE/SLE helper tests pass `PO_RETURN_ITEM_SOURCE` as a parameter. This is harmless: P-01 and P-25 pin the constant's value.
- PRI-LOC-03/04 and PRI-QTI-01/04 loop over their values instead of using `pytest.param`. Every value is still asserted exactly.
- The setup seeds for PRI-P-21 and P-27 are inconsistent, but the outcome cannot change because the function never reads those rows.
- BUG-802 and BUG-803 are still only in `po_return_inventory.bugs-staging.md`. They are waiting for the batch merge into `docs/testing/bugs.md`, which batch mode forbids editing here. The xfail reasons already name the right IDs.

## Fidelity (scoped)
- The cases file is unchanged since round 2 (Revision 3), so no case rows changed.
- PRI-P-10 is the only test that changed since the last verify (notes, "Fix round 2"). I re-read it against the case:
  - Given: the PO goes to storage F1d (soft-deleted), S(F1d,I1) is 10 @ 12.50, and RI1 has qty 3 with PL2. All of this is reproduced.
  - When: the call is `[(RI1, PL2)]`.
  - Then: returns 1 ✅; S(F1d,I1) re-read gives qty 7 ✅; exactly one ledger row for RI1 ✅, on F1d ✅, with quantity 3 ✅.
  - No mocks and no try/except.

## Surviving mutants
None. All 48 mutants were killed in round 2. This round re-tests no lines: there were no previous survivors, and fix round 2 changed only a test assertion, so source coverage is unchanged at 100% line and branch.

| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

## Traceability
- Counts: 68 cases (65 pass, 3 xfail) · 68 `def test_` functions · 68 unique docstring IDs.
- Unmatched: none. The case ID set equals the test docstring ID set, with no duplicates.
- Marker mismatches: none.
  - PRI-QTI-05: `xfail(strict=True, reason=BUG_802)` ✅
  - PRI-P-32: `xfail(strict=True, reason=BUG_802)` ✅
  - PRI-P-47: `xfail(strict=False, reason=BUG_803)` ✅ (the case and spec R15a direct `strict=False`)
- No `patch`, `monkeypatch`, `try/except` or `pytest.raises(Exception)` in the file. The only matches for "except" are in docstring text ("without exception").

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_po_return_inventory.py -q -p no:cacheprovider --cov=app.managers.po_return_inventory --cov-branch --cov-report=term-missing
  app\managers\po_return_inventory.py  40  0  14  0  100%
  65 passed, 3 xfailed, 50 warnings in 7.18s

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_po_return_inventory.py -q -p no:cacheprovider --runxfail -rf
  FAILED test_pri_qti_05 -> TypeError: _quantity_to_int() got an unexpected keyword argument 'line_number'  (designed)
  FAILED test_pri_p_32   -> detail text assertion (PO item id vs line number)                               (designed)
  FAILED test_pri_p_47   -> qty_before: expected 4, got 7                                                   (designed, BUG-803)
  3 failed, 65 passed, 35 warnings in 3.57s

(repeat) .venv/Scripts/python.exe -m pytest tests/unit/managers/test_po_return_inventory.py -q -p no:cacheprovider
  65 passed, 3 xfailed, 35 warnings in 3.68s

mutate.py: not re-run. The scope is the lines of previous survivors (none) plus lines whose coverage the fix round changed (none). The round-2 result is carried over:
  Mutants: 48 · killed 48 · timeout 0 · survived 0 · score 100%
```
