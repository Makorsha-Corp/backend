# Verification — `app/managers/inventory_manager.py`

> **Verdict:** PASS
> Tests: 110 passed · 40 xfailed (reproduced ✅ — all 40 fail under `--runxfail` on the case's "fails today on" assertion) · 1 xpassed (INV-S-11, non-strict by design) · coverage 99% branch (44/44 branches; only miss L158 = dead `list_inventory`)
> Mutation: 169 mutants · 160 killed · 9 survived → score 100% (after excluding 4 equivalent, 3 dead, 2 bug-path)
> Source commit: e48a092 · Cases revision: 4
> Round: 2 (scoped re-verify after the executor's fix round; round 1 was NEEDS WORK with findings 1–7)

## Summary
These tests can be trusted. The executor applied all 7 round-1 fidelity findings, and each fix checks out against its case. The changes are:
- Ordered page comparisons.
- `len(rows) == 1` before every "one ledger row" check.
- `ws_counts` before/after around every raising read-only call.
- Field-by-field checks on every incoming-summary result.
- POs built with the default workflow `WF`.
- "Nothing written" checks on the U-20/22/23/24 schema cases.
- An updated header.

The runs reproduce the notes exactly and are stable. Every xfail still fails on its named assertion, including the 9 xfail tests whose bodies changed. Re-running mutation on the previously surviving lines gives the same 9 survivors, and all of them are equivalent, dead, or bug-path. No case, spec, or app change is needed.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | Weakened assertion (order) — **RESOLVED** | INV-P-04, INV-P-20, INV-P-21 | Was a `sorted(...) == sorted(...)` comparison. | Now `assert page_ids(res) == [a.id, b.id]` / `[h.id, n.id]` | — |
| 2 | Missing assertion (row count) — **RESOLVED** | INV-U-03, U-04, U-07, U-08, INV-D-02, D-04, D-05 | There was no "exactly one ledger row" check. | Each now has `assert len(rows) == 1` before `assert_fields(rows[0], …)` | — |
| 3 | Missing assertion (read-only "nothing changed") — **RESOLVED** | INV-G-05, G-06, G-07, G-08, INV-IF-05, INV-IS-03 | There was no `ws_counts` check. | Each now has `before = ws_counts(db, w1)` … `assert ws_counts(db, w1) == before` | — |
| 4 | Weakened assertion (incoming results) — **RESOLVED** | INV-IF-06..IF-21 (listed set), INV-IS-01, IS-04, IS-05 | Only a subset of the result fields was checked. | Every item now asserts `factory_id`, `item_id`, `total_pending_qty`, `order_count`, `len(orders)`, and each order's `order_kind`/`order_id`/`order_number`/`status_name`/`pending_qty`. IF-21 checks the order sequence as an ordered list, and IS-05 checks both factory entries in full. | — |
| 5 | Wrong setup (default WF) — **RESOLVED** | INV-IF-06, IF-07, IF-13, IF-14, IF-18, IF-19, IF-21, IF-23, INV-IS-01, IS-04, IS-05 | The W1 POs were built with `workflow=None`. | All W1 POs now use `workflow=wf`. IF-13's voided PO carries WF and still fails under `--runxfail` on `Decimal('9.00') == Decimal('3')`, which is the case's named failure (PO_1 included, total 9). | — |
| 6 | Missing assertion (schema "nothing written") — **RESOLVED** | INV-U-20, U-22, U-23, U-24 | There was no post-rejection DB check. | U-20 now checks that T is unchanged and the bucket has no ledger rows. U-22/23/24 check `inv_rows_for(...) == []` and `ledger_rows(...) == []`. All 4 still fail first on `DID NOT RAISE ValidationError` (L1188/1210/1220/1230). | — |
| 7 | Stale header — **RESOLVED** | test file L3 | The header said "revision 3". | Now `Implements tests/unit/managers/inventory_manager.cases.md (revision 4)` | — |

No open findings.

Not findings (checked this round):
- **INV-IF-05 builds its PO with `workflow=None`**, while the `PO(...)` default is WF. This test was touched this round but was not in round-1 finding 5. It cannot pass or fail for a different reason. The intended outcome is a factory-level 404 raised before any PO is read. The PO exists only to make "summary returned" observable today, and S_OPEN is non-terminal under both WF and no workflow. Under `--runxfail` the test fails on `DID NOT RAISE HTTPException` (L2174), which is the case's named failure.
- **W2 POs with `workflow=None`** (IF-07 `po4`, IS-05 `po5`). IF-07's Given says "no workflow" explicitly. For IS-05, `WF` is a W1 workflow, so attaching it to a W2 PO would build a cross-workspace row the case does not describe. Leaving the workflow off follows the IF-07/IS-07 pattern for other-workspace POs.
- **Changed xfail tests** fail on their named assertion under `--runxfail`:
  - G-06/G-07 fail on `TypeError … include_deleted` (L1404/1416).
  - G-08 fails on `DID NOT RAISE HTTPException` (L1427).
  - IF-05 fails on `DID NOT RAISE HTTPException` (L2174).
  - IF-13 fails on total `9.00 == 3` (L2358).
  - U-20/22/23/24 fail on `DID NOT RAISE ValidationError`.

  None of them fails on a newly added `ws_counts` or "nothing written" assertion.
- **Carried from round 1, still valid:**
  - INV-S-11 XPASS is the designed non-strict xfail.
  - INV-U-28's reason names BUG-713, as the Expect column lists.
  - The only mocks are RS-1's. There is no `try/except` and no `pytest.raises(Exception)`.
  - The executor's setup fixes (P-17 HD as DAMAGED, IF-15 `TR-0005`) are correct.
  - BUG-700..719 are in `inventory_manager.bugs-staging.md` (20 IDs) and are pending the batch merge into `docs/testing/bugs.md`.

## Surviving mutants
Re-run with `--lines` on each previously surviving line: L114, L155–158, L232, L331, L357, L397. That run had 11 mutants, 2 killed (L232 `Or→And`, L397 `0→1`), and 9 survived. The survivors are identical to round 1. The other 158 mutants were all killed in round 1. The fix round only added assertions and changed setup, and app/ is unchanged at e48a092, so those kills carry over.

| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 11 | L158 | `return` → `return None` in `list_inventory` | dead | The spec's "Not specified" section lists `list_inventory` as dead code (Q11), staged for removal. | — |
| 34 | L155 | `skip: int = 0` → `1` (`list_inventory`) | dead | Same dead method. | — |
| 35 | L155 | `limit: int = 100` → `101` (`list_inventory`) | dead | Same dead method. | — |
| 80 | L114 | `exclude_unset=True` → `False` | equivalent | Every `InventoryUpdate` field defaults to `None`, so unset fields dump as `None` and `exclude_none=True` drops them. The dict is identical. | — |
| 81 | L114 | `exclude_none=True` → `False` | bug-path | This is the BUG-713 change (explicit nulls reach the update). Only the xfail cases U-27/28/29 send non-no-op explicit nulls. U-31 (null on an already-NULL price) is a no-op either way. | — (resolves with BUG-713) |
| 109 | L397 | `limit=500` → `501` | bug-path | The 500-factory cap is BUG-709. Only the xfail case INV-IS-07 targets it. | — (resolves with BUG-709) |
| 140 | L331 | key `("purchase", po.id)` → `("", po.id)` | equivalent | This is an internal merge key only. `""` ≠ `"transfer"`, so PO and TR entries stay separate (IF-19 still passes). The output `order_kind` comes from a separate literal. | — |
| 142 | L357 | key `("transfer", tr.id)` → `("", tr.id)` | equivalent | Same argument, mirrored. | — |
| 168 | L232 | `int(unique_count or 0)` → `or 1` | equivalent | A `by_type` group exists only when at least one row matched. `item_id` is NOT NULL, so `count(distinct item_id)` ≥ 1 and the fallback is unreachable. | — |

## Traceability
- There are 151 cases and 151 tests, matched 1:1 by the first docstring case ID (AST script). There are no duplicates, no test lacks an ID, no case is unmatched, and there are no extras. INV-IF-20 is retired and correctly absent.
- Marker mismatches: none.
  - 110 `pass` cases have no marker.
  - 41 xfail rows: 40 carry `xfail(strict=True, reason=BUG_NNN)` naming the listed BUG.
  - INV-S-11 carries `xfail(strict=False, reason=BUG_719)`, as the cases file specifies.
- Every BUG ID used (700–719) exists in `inventory_manager.bugs-staging.md`, pending the batch merge into `docs/testing/bugs.md`.

## Fidelity scope (this round)
- **Cases file:** still revision 4. Revisions 3 and 4 changed no rows, so no case-driven re-check was needed.
- **Tests changed since round 1** (per the notes' Revision history) were all re-read against their cases:
  - P-04, P-20, P-21
  - U-03, U-04, U-07, U-08, U-20, U-22, U-23, U-24
  - D-02, D-04, D-05
  - G-05, G-06, G-07, G-08
  - IF-05 through IF-19, IF-21, IF-23
  - IS-01, IS-03, IS-04, IS-05
  - the module header

  No new findings.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_inventory_manager.py -q -p no:cacheprovider --cov=app.managers.inventory_manager --cov-branch --cov-report=term-missing
  app\managers\inventory_manager.py  139  1  44  0  99%  158
  110 passed, 40 xfailed, 1 xpassed, 15 warnings in 20.94s

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_inventory_manager.py -q -p no:cacheprovider --runxfail -rf
  40 failed, 111 passed in 9.29s   (the 40 = exactly the strict-xfail set)

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_inventory_manager.py -q -p no:cacheprovider --runxfail --tb=line -k "g_06 or g_07 or g_08 or if_05 or u_20 or u_22 or u_23 or u_24 or if_13"
  9 failed — each on its named assertion (see Findings 5/6 and "Not findings")

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_inventory_manager.py -q -p no:cacheprovider   (repeat)
  110 passed, 40 xfailed, 1 xpassed in 8.72s

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/inventory_manager.py tests/unit/managers/test_inventory_manager.py --lines <R> --timeout 180 --json <scratch>/inv_<R>.json
  --lines 114-114  Mutants: 2 · killed 0 · survived 2   (#80, #81)
  --lines 155-158  Mutants: 3 · killed 0 · survived 3   (#11, #34, #35)
  --lines 232-232  Mutants: 2 · killed 1 · survived 1   (#168)
  --lines 331-331  Mutants: 1 · killed 0 · survived 1   (#140)
  --lines 357-357  Mutants: 1 · killed 0 · survived 1   (#142)
  --lines 397-397  Mutants: 2 · killed 1 · survived 1   (#109)
  (round 1 full run: 169 mutants, 160 killed, 9 survived — classifications carried over)
```

## Decisions made
- INV-U-20 (round 1, still applied): the schema-case "nothing written" convention conflicts with Given T, so it is read as "T unchanged and zero ledger rows for the bucket" (best-practice default, delegated by reviewer).
- INV-IF-05 `workflow=None` is not a finding. The Then is a factory-level 404, so the PO's workflow cannot affect any asserted outcome (best-practice default, delegated by reviewer).
- W2 POs with no workflow (IF-07 `po4`, IS-05 `po5`) are accepted. The `WF` default is a W1 workflow and does not apply to other-workspace POs (best-practice default, delegated by reviewer).
