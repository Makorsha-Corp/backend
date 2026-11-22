# Verification — `app/services/ledger_service.py`

> **Verdict:** NEEDS WORK
> Tests: 80 passed · 24 xfailed (reproduced ✅, 3 identical runs) · coverage 99% branch (line 361 missed, dead)
> Mutation: 80 mutants · 76 killed · 4 survived → score 96% (76/79, after excluding 0 equivalent, 1 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
The tests can be trusted. All 104 tests match their cards: no missing, weakened or changed assertion, no extra mocks, and the Given rows are built as the cards say. Under `--runxfail` every one of the 24 strict xfails fails on the line its card names. Hand-written variants were tried for TC1/TC3/TC4/TC6, error mapping, Decimal vs float, workspace isolation (W0/W2) and the exact lock clauses. All of them are caught except one: a commit or rollback on the **success** path of `get_project_component_ledger`.

What must change is at the case designer only:
- three mutants survive because no card checks them (`inventory_type` as a plain string, the default `skip`/`limit` of `get_transactions_by_user`);
- one TC6 card is missing (the success path above).

Nothing is routed to the executor or the describer. No new bug was found.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_inventory_balance` R2, line 230; LSV-GIB-01 Then 3, LSV-GIB-04 Then 3 | R2 says the result is "the enum's value **string**". The cards only check `result["inventory_type"] == "DAMAGED"` / `"STORAGE"`. `InventoryTypeEnum` is a `str` enum, so returning the enum member itself also passes, even though `str()`/f-string output and `type()` differ. | Mutant #19 of shard 141–265 (`hasattr(inventory_type, 'value')` → `hasattr(inventory_type, '')`) SURVIVED. | case designer: add `type(result["inventory_type"]) is str` to GIB-01 Then 3 and GIB-04 Then 3 |
| 2 | case-missing | `get_transactions_by_user` R1 ("exactly these arguments"), lines 340–341 | No card checks that the default `skip=0` / `limit=100` reach the manager. TBU-03 patches the manager but never checks the call. TBU-01/02 (xfail BUG-645) use 1–2 rows, so this stays unchecked after BUG-645 is fixed too. | Mutants L340 `0 → 1` and L341 `100 → 101` SURVIVED. | case designer: add a patched-manager card asserting the call kwargs (`skip=0, limit=100, start_date=None, end_date=None`), or a 101-row default-limit card once BUG-645 is fixed |
| 3 | case-missing | `get_project_component_ledger` R3 (Read only, TC6) | The only TC6 card (PCL-09) covers the refusal path, which raises before the ledger read. Nothing checks that an **allowed** read neither commits nor rolls back. PCT-06 covers this for `get_project_component_total_cost`, but there is no PCL counterpart. | Variants `db.commit()` / `db.rollback()` inserted before `self.ledger_manager.get_project_component_ledger(` → 80 passed (survived). The same variant on the other 8 read methods is killed. | case designer: add a PCL success-path TC6 card (spies, pending Q, edit E(P1), allowed user U2 on C1). Projects are deferred: today's behaviour only |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | 361 | `return …get_transactions_by_order(...)` → `return None` | dead | Spec "Not specified": `get_transactions_by_order` is dead code (Q2, on the dead-code removal checklist). | — |
| 2 | 230 | `hasattr(inventory_type, 'value')` → `hasattr(inventory_type, '')` | case-missing | Finding 1. | case designer |
| 3 | 340 | default `skip: int = 0` → `1` | case-missing | Finding 2. | case designer |
| 4 | 341 | default `limit: int = 100` → `101` | case-missing | Finding 2. | case designer |

## Service-level variants (hand-written, scratch copy of the backend; `app/` untouched)
The runner and specs are in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1v\ledger\tools\`, and the full log is in `…\ledger\variants.log`. Each variant ran the full file with `-m "not xfail"`, except the money "fix" variants (full file, xfail included) and the lock variants (the lock card only, with `--runxfail`).

| Area | Variant | Result |
|---|---|---|
| TC1 | no commit (RMI / RINV) | killed: RMI-01,03,05,06,07,08,12 / RINV-01,03,04,07,09,10,14 |
| TC | commit before the message building, i.e. before the KeyError (RMI / RINV) | killed: RMI-11 / RINV-13 |
| TC3 | rollback removed from `except` (RMI / RINV) | killed: RMI-10, 11 / RINV-12, 13 |
| TC | partial write after failure: `commit` in `except` (RMI / RINV) | killed: RMI-10, 11 / RINV-12, 13 |
| Error | swallowed: `except` returns `({}, [])` (RMI / RINV) | killed: RMI-10,11,12 / RINV-12,13,14 |
| TC4 | commit moved outside the `try` | **equivalent**: `BaseService._commit_transaction` itself rolls back and re-raises when commit fails, so RMI-12 / RINV-14 behave the same |
| TC6 | `db.commit()` / `db.rollback()` before the manager call, in each of the 9 read methods | killed in 8 of 9 (GML-08/09, GMB-07, PCT-06, GIL-09, GIB-09, GAL-09, IMS-06, TBU-03). **Survived** in `get_project_component_ledger`: Finding 3 |
| Error mapping | component access refusal remapped to 400 (ledger) | killed: PCL-05…08 (5 tests) |
| Error mapping | refusal swallowed, returns `total_cost 0.0` | killed: PCT-03, 04, 05 |
| Money | machine / inventory `total_value` kept as `Decimal` (the BUG-3043 fix) | the pass cards still pass; GMB-02, GMB-04 / GIB-02, GIB-05 XPASS(strict) → the xfail markers come off cleanly when fixed |
| Money | `float(round(value, 0))`, `float(int(value))`, `str(value)` | killed (GMB-01 / GIB-04, …) |
| Money | `quantize(Decimal("0.1"), ROUND_HALF_UP)` on the machine value | survives on the pass cards. **Bug-path / covered**: every pass card uses `x.50` / `0.00` values (on purpose: a float equals `Decimal("1234.50")` exactly), and after BUG-3043 GMB-02 Then 3 (`"1234.50"`) catches it. See the future-work notes |
| Money | project `total_cost` kept `Decimal` / `int()` | killed: PCT-01, 02 / PCT-01 |
| HR-15 | — | not applicable: the service does no rounding (spec HR line). The only rounding-shaped variant is the quantize row above |
| HR-16 | service passes `workspace_id=None` to the balance call | killed: GMB-01 + 1 |
| HR-16 | DAO: machine ledger balance without the workspace filter | killed: GMB-05 (W2), GMB-06 (W0) |
| HR-16 | DAO: attachment ledger list without the workspace filter | killed: GAL-01 (W0 + W2 rows) |
| Lock | snapshot read unchanged (today) | RMI-13 / RINV-15 fail on Then 2 (as designed) |
| Lock | `with_for_update(of=MachineItem)` / `(of=Inventory)`, the intended clause | RMI-13 / RINV-15 **pass** |
| Lock | plain `FOR UPDATE`, `skip_locked`, `nowait`, `read` (FOR SHARE), `key_share` | all rejected by RMI-13 / RINV-15 |

## Traceability
104 cases · 104 tests · unmatched: none · duplicate IDs: none · marker mismatches: none. Every `xfail` is `strict=True`, and each reason names every BUG in the card's Expect line (RINV-17 names BUG-653 and BUG-3042; PCL-10 / PCT-07 name BUG-1278 and BUG-1954). Every BUG ID used is in `docs/testing/bugs.md`.

`--runxfail`: each of the 24 xfails fails on the line its card names.
- **Assertion failures:**
  - GML-10 T2 (`performed_at desc` ≠ `…, id desc`)
  - GML-11 T1
  - GMB-02 T2
  - GMB-04 T2
  - GMB-08 T2
  - RMI-09 T2
  - RMI-13 T2 (no lock clause, ends `limit %(param_1)s`)
  - PCL-10 T1 and PCT-07 T1 (DID NOT RAISE)
  - GIB-02 T2
  - GIB-05 T2
  - RINV-05 T2
  - RINV-11 T2
  - RINV-15 T2
  - RINV-17 T1
  - RINV-18 T2 (`updated_by` U1 ≠ U2)
  - IMS-02 T2
  - IMS-03 T2
- **"The call raises" cards, at the When call with the named type:**
  - RMI-14 TypeError (`int * NoneType`)
  - GIB-06 and RINV-16 AttributeError `value_after`
  - IMS-04 TypeError `skip`
  - TBU-01 and TBU-02 AttributeError `get_by_performer`

## Notes for future work
- **Once BUG-3043 is fixed**, add one pass card per balance with a value that is not `x.50` (e.g. `1234.56`). Today the cards use binary-exact values, so a precision-losing variant (quantize to 0.1) is caught only by GMB-02 Then 3. A value like `1234.56` would also guard HR-15-style rounding in a future refactor.
- **RINV-03 Then 6** counts **all** `machine_activity_events` rows (the executor's note). It holds only while no other suite commits events to the shared test DB.
- **RMI-13 / RINV-15** pin the exact clause from spec G2. The manager spec's R11 rows and the BUG-643/644 rows still say only "`FOR UPDATE`" (spec G2 log); that is the describer's follow-up for `ledger_manager.spec.md`, outside this module.

## Commands run
```
$env:COVERAGE_FILE=…\svc1v\ledger\.coverage   (every run below)
.venv/Scripts/python.exe -m pytest tests/unit/services/test_ledger_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.ledger_service --cov-branch --cov-report=term-missing
  app\services\ledger_service.py  76  1  12  0  99%  361
  80 passed, 24 xfailed, 17 warnings in 15.34s
.venv/Scripts/python.exe -m pytest tests/unit/services/test_ledger_service.py -q -p no:cacheprovider -o addopts="" --runxfail -rf --tb=long
  24 failed, 80 passed, 2 warnings in 9.45s
.venv/Scripts/python.exe -m pytest tests/unit/services/test_ledger_service.py -q -p no:cacheprovider -o addopts=""   (×2)
  80 passed, 24 xfailed, 2 warnings in 9.84s
  80 passed, 24 xfailed, 2 warnings in 9.60s
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/ledger_service.py tests/unit/services/test_ledger_service.py --lines 1-140   --timeout 180 --json …\mut-1-140.json
  Mutants: 34 · killed 34 · timeout 0 · survived 0 · score 100%
… --lines 141-265 …
  Mutants: 28 · killed 27 · timeout 0 · survived 1 · score 96%   (SURVIVED #19 L230:78 const 'value' -> '')
… --lines 266-400 …
  Mutants: 18 · killed 15 · timeout 0 · survived 3 · score 83%   (SURVIVED L361 return, L340 0->1, L341 100->101)
variants.py spec.json / spec2.json (scratch copy, UNIT_TESTS_SKIP_MIGRATE=1) — results in the variants table above
```

## Round 2 — 2026-11-22

> **Verdict:** PASS
> Tests: 82 passed · 24 xfailed (3 identical runs; `--runxfail`: 24 failed, 82 passed) · Cases revision: 3 · Source commit: e48a092
> Re-run survivors: 5 re-run (mutants L230, L340, L341; PCL allowed-path commit and rollback variants) → 5 killed

Narrow round: I checked only the changed and new tests and re-ran the earlier survivors. I did not run full mutation testing again.

**Fidelity (changed and new cards):**
- **LSV-GIB-01:** Then 4 asserts `type(result["inventory_type"]) is str`, and Then 5–6 are renumbered as in the card.
- **LSV-GIB-04:** Then 4 adds the same type check.
- **LSV-PCL-11:**
  - The Given matches the card: P1 at T(1) and P2 at T(2), then pending Q and edit E(P1) after the commit point.
  - The When call runs inside the spies.
  - All six Then lines are asserted, in order.
- **LSV-TBU-04:**
  - Only the patched manager is used, as the card says.
  - The test binds the call arguments to `_mgr_tbu_sig(session, user_id, workspace_id, start_date, end_date, skip, limit)`, which matches `LedgerManager.get_transactions_by_user`. Binding works whether the arguments are passed by position or by keyword.
  - Then 1–5 are asserted exactly.

No findings.

**Traceability:** 106 cases · 106 tests · 82 pass / 24 strict xfail · unmatched: none · duplicate IDs: none · marker mismatches: none.

**Re-run of the Round 1 survivors** (scratch copy, `variants.py` with `spec3.json`, private `COVERAGE_FILE`):

| Survivor | Killed by |
|---|---|
| L230 `hasattr(inventory_type, '')` | LSV-GIB-01, LSV-GIB-04 |
| L340 `skip` default `0 → 1` | LSV-TBU-04 |
| L341 `limit` default `100 → 101` | LSV-TBU-04 |
| `db.commit()` before the `get_project_component_ledger` manager call | LSV-PCL-11 |
| `db.rollback()` before the `get_project_component_ledger` manager call | LSV-PCL-11 |

**Mutation score:** the Round 1 run had 80 mutants. All of them are now killed, except L361, which is dead code. That gives 79/79 = 100% after excluding the dead mutant. Findings 1–3 from Round 1 are closed.

**Open items:** none. The Round 1 notes for future work still apply:
- add a balance card with a non-`.50` value once BUG-3043 is fixed;
- RINV-03 Then 6 counts every event row in the shared test database;
- the manager spec's lock wording (describer).
