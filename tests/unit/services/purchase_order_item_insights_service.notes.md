# Execution notes — `app/services/purchase_order_item_insights_service.py`

> Cases: `tests/unit/services/purchase_order_item_insights_service.cases.md` (revision 4) · Tests: `tests/unit/services/test_purchase_order_item_insights_service.py` · Source commit: e48a092
> Result: 62 passed · 12 xfailed · 0 discrepancies · 0 errors — branch coverage 95% (every gap is dead or deferred-unreachable)
> Run: `COVERAGE_FILE=<private> .venv/Scripts/python.exe -m pytest tests/unit/services/test_purchase_order_item_insights_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.purchase_order_item_insights_service --cov-branch --cov-report=term-missing`

## How the tests are built
- **Standing rows**: the fixture `st` builds them in Conventions order, with one flush each: W0, W1, W2, U1, S0/S1/S9, I0, I1, I2, I3, I9, then AC0, AC1, AC2, AC9. Every DB card requests it. The helper cards (D, R, L, M, A) use no database.
- **Given rows**:
  - `po(st, number, ws=1|0|2, voided=False, **cols)` is "po", "W0 po" or "W2 po". `voided=True` writes all four void columns (`voided`, `void_note "Void"`, `voided_at T0`, `voided_by U1`).
  - `ln(st, P, item, unit_price, **cols)` is "ln of P". The line's `workspace_id` defaults to `P.workspace_id`; a card's "but `workspace_id` …" overrides it.
  - Both builders flush, so ids rise in card order.
- **HL** is the Conventions helper, verbatim.
- **Call wrappers**: `insights(db, st, P)` and `fetch(db, st, item_ids, exclude_po_id=MISSING)` are thin, always with `workspace_id=W1.id`. G-01 calls the service directly with `po_id=MISSING`.
- **Clocks**:
  - `clock(local, utc)` patches `mod.date` with a `date` subclass whose `today()` is fixed. It also patches `app.services.purchase_order_item_insights_service.utcnow` with `create=True`.
  - `CLOCK()` and `SKEW()` are the two Conventions clocks. Only the cards that name a clock use one: G-08, G-18…20 and G-22.
- **Spies, commit point, nothing written**: as Conventions. `counts(db)` counts the `purchase_orders` and `purchase_order_items` rows.
- **Lint-driven spellings**:
  - G-01 combines `spies` and `pytest.raises` in one `with` (ruff SIM117), with `# Then 1` on that line.
  - The `{l.… for l in …}` comprehensions in `ids()` and the cards use `x` as the loop variable (ruff E741). A-09 keeps the card's variable name `l`.
- **PO numbers**: `po_number` is unique per workspace (`uq_po_workspace_number`), and every test makes fresh workspaces. The fixed numbers (`PO-1` …) never collide, even when runs overlap.

## Verification runs
- 3 plain runs: 62 passed and 12 xfailed each time (revision 4).
- `--runxfail`: 12 failed, 62 passed. Each failure is on the card's "Fails today on" Then line, checked through the `# Then` comment above the failing line:
  - G-12 Then 2 and G-13 Then 2: the foreign item gets a row.
  - G-14 Then 1: the foreign item gets a row.
  - G-15 Then 3: AC9 wins the average. G-16 Then 2: AC0 wins it.
  - G-22 Then 2: the local-today window picks HB.
  - F-09 Then 2 and F-10 Then 2: LX is returned.
  - F-13 Then 2 and F-14 Then 2: the foreign `account_id` is returned.
  - A-10 Then 2: account 11 "Beta" wins. A-11 Then 2: account 22 wins.
- **Reference plugin** (scratch `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsupe\poi\poi_ref.py`, loaded with `-p poi_ref`; `POI_FIX` selects bugs):
  - BUG-2540: filters on the line's own `workspace_id`, and outer-joins the account on id and workspace.
  - BUG-2541: keeps only the PO lines whose item is in the workspace.
  - BUG-2542: "today" is the module's `utcnow().date()`.
  - BUG-2543: breaks a tie on average and order count by casefolded supplier name, then `account_id`.
  - With all fixes and `--runxfail`: **74 passed**.
  - Each fix on its own flips exactly its own cards and breaks no pass card (62 passed every time):
    - 2540 → F-09, F-10, F-13, F-14, G-15, G-16
    - 2541 → G-12, G-13, G-14
    - 2542 → G-22
    - 2543 → A-10, A-11
- `ruff check`: clean. LF only (0 CR bytes).

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 65 | dead | `if not po: raise 404`. `get_purchase_order` already raises the same 404 (spec FU-1). |
| 233->235 | dead | The false arm of `if ln.account_name:`. A supplier line from the query always has a name (`accounts.name` is NOT NULL), and the bucket's name is never returned (spec R3 note, FU-1). |
| 247 | deferred | Total weight ≤ 0 → `continue`. Unreachable: weights are always ≥ 1 (`_pick_avg_supplier_lowest` R7, cases "Deferred"). |
| 260 | deferred | `best_account_id is None` → `None`. Unreachable for the same reason (R7). |

## Factories added
None. The builders are local.

## Notes for maintainers
- When BUG-2540, 2541, 2542 or 2543 is fixed, its cards XPASS (strict → fail). Remove the markers per the mapping above.
- The BUG-2542 fix must import `utcnow` **by name** in the module (`from app.utils.time import utcnow`), because the clock patch targets `app.services.purchase_order_item_insights_service.utcnow`. After the fix, `create=True` can be dropped so that a missing name fails loudly.
- The CLOCK cards patch both clocks to the same day, so they pass both before and after the BUG-2542 fix.
- `_fetch_history_lines` has no `ORDER BY`. Every card either compares sets or goes through a picker that breaks its own ties.

## Revision history
- **2026-11-10 — cases revision 2.** First implementation: 70 cases, 58 passed, 12 xfailed, 95% branch.
- **2026-11-10 — cases revision 3.** Only the Conventions changed (a Parallel runs note). This module builds only purchase orders, whose `po_number` is unique per workspace, so no card uses `GN` and no helper was added. Only the header revision changed in the test file. Re-checked: 3 plain runs gave 58 passed and 12 xfailed each time. `--runxfail` gave 12 failed and 58 passed, on the same Then lines. The reference plugin with all fixes and `--runxfail` gave 70 passed. Branch coverage is 95%, with the same gaps. ruff is clean and the file is LF only.
- **2026-11-10 — cases revision 4** (verifier F1–F3). Added A-12, A-13, A-14 (`_pick_avg_supplier_lowest` R3/R4, hand-made `HL` lines) and DC-01 (a `_HistoryLine` field set raises `dataclasses.FrozenInstanceError`, the value is unchanged). No other test changed. Result: 62 passed, 12 xfailed, 0 discrepancies; branch coverage 95% with the same gaps. 3 plain runs gave 62 passed and 12 xfailed each time. `--runxfail` fails the same 12 cards on the same Then lines. The reference plugin with all fixes and `--runxfail` gives 74 passed; each fix alone flips only its own cards (2540: 6, 2541: 3, 2542: 1, 2543: 2). Survivors re-checked with a scratch in-process mutation plugin (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsupe\poi\poi_mut.py`, `POI_MUT` picks the mutant; it recompiles the service source with one line changed and sets the mutated method on the live class): #51 (L252 `<` → `<=`) fails A-13; #52 (L253 `and` → `or`) fails A-12 and A-13; #68 (L236 `> 0` → `> 1`) fails A-14. (Under #51 and #52 the strict xfails A-10/A-11 also XPASS, as the tie order flips.) ruff is clean and the file is LF only.
