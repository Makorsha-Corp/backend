# Execution notes — `app/services/approval_notification_service.py`

> Cases: `tests/unit/services/approval_notification_service.cases.md` (revision 4) · Tests: `tests/unit/services/test_approval_notification_service.py` · Source commit: e48a092
> Result: 176 passed · 16 xfailed · 0 discrepancies · 0 errors — branch coverage 99% (186 statements, 98 branches; 1 branch arc missed)
> Run: `COVERAGE_FILE=<private> .venv/Scripts/python.exe -m pytest tests/unit/services/test_approval_notification_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.approval_notification_service --cov-branch --cov-report=term-missing`

## How the tests are built
- **Standing rows**: the autouse fixture `st` runs `SET LOCAL session_replication_role = replica` first, then builds W0, W1, W2, the ten profiles (UZ0 … UZ2, ids rising) and the nine memberships, in Conventions order, each flushed. Card names are attributes of `st` in lower case (`UA` → `st.ua`).
- **Given rows**: `po`, `ready_po`, `to_` (named with `_` so it does not clash with the `to(U)` check), `to_line`, `eo`, `eo_line`, `wo`, `so`, and `poa` / `toa` / `eoa` / `woa` / `soa`. Defaults are the Conventions columns; keyword arguments are the "but" columns; `ws=` gives "W2 x" / "W0 x"; `approved=True` sets `approved` and `approved_at = T(12)`.
- **GN(n)** = `f"{n}-{os.getpid()}"` (Conventions, Parallel runs): `to_` and `so` store `GN(n)` as `transfer_number` / `sales_order_number`. No Then line reads a stored number.
- **In-memory blanks** (RD-05, RD-12, RD-15, GP-12): the order is inserted with every NOT NULL column set, then the field is changed on the object, not flushed, before the call.
- **Named checks**: `notes(db)` (expire, then every notification by id), `to(db, U)`, `recips(db)` (a sorted list) and `note(db, U)` = `to(db, U)[0]`. **spies** = `spies(db)` gives the two `patch.object(..., wraps=...)` objects. **commit point** = `db.commit()` (releases the savepoint under the `db` fixture). On the `committed:` lines the test calls `db.rollback()` once and then counts. The `SET LOCAL` survives that rollback, because it ran before the commit point.
- **APN-NU-10**: sets `session_replication_role = origin`, then `pytest.raises(IntegrityError)` around `db.begin_nested()`, as Conventions say.
- **Parametrized cards** (same setup and asserts, one input differs): FR-01…06, NU-04…09, RD-02…04, RD-14/16, GP-01…04, GP-09…11, AS-06/07, SC-08…10, DS-01…07, IA-19…21. Each card ID is a param id. All 192 live IDs are collected exactly once (192 tests collected; AN-05 retired). RD-15 is its own test, placed after the RD-14/16 parametrized test.
- **xfail markers**: `BUG_1205`, `BUG_1202`, `BUG_1203`, `BUG_755`. All are strict, and each reason carries the bug title from `docs/testing/bugs.md`.
- Nothing is patched beyond the spies. The spec lists no externals.

## Verification runs
- 3 plain runs (revision 4): 176 passed, 16 xfailed each time.
- `--runxfail`: the 16 bug xfails fail on their Then 1 assertion: FR-07 (`'sales order #5'`), SU-07/08/09/20 (`(0, 0, True)`), SU-19 (`(0, 0, True)` vs `(1, 2, False)`), SU-21/22 (`DID NOT RAISE HTTPException`), BP-04 (`'Ready for review'`), PA-09 (`[]`), HA-05 (`False`), IA-17 (only UC), SR-01 (`False`), SR-03/04/05 (`None`).
- **Reference plugin** (scratch `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsupe\an\an_ref_fix.py`, loaded with `-p an_ref_fix` and `PYTHONPATH` pointing at that folder; `AN_FIX` selects bugs). It patches the module's attributes in-process, so the module's own callers pick up the fix:
  - BUG-1202, 1203 and 755: with `required_approvals` NULL and no approver rows, a PO / TO / EO summary is `(0, 1, False)`.
  - BUG-1205: `SO-<id>`. The sales summary looks the order up in the workspace (404 `"Sales order with ID <id> not found"`) and needs one approval when there are no approvers and no requirement (BUG-736). Readiness = `order_info_confirmed` and `items_confirmed`; the gap text uses "Order info" / "Order items"; the sales pending list; sales approvers on invoice notices.
  - All fixes with `--runxfail` (revision 4): 192 passed.
  - Each fix alone flips only its own cards and breaks no pass card: 1202 → SU-07, BP-04, HA-05; 1203 → SU-08; 755 → SU-09; 1205 → FR-07, SU-19…22, PA-09, IA-17, SR-01, SR-03…05.
- **Verifier survivors (revision 4)**: scratch plugin `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsupe\an\an_mut.py` (`-p an_mut`, `AN_MUT=<id>`) applies one mutant to a copy of the source and execs it into the loaded module (app/ is never written). Every mutant now fails at least one test: #149, #178 (L318) → IA-19, IA-20, IA-21; #191 (L318) → IA-19; #179, #192 (L325) → IA-20, IA-21; #197 (L325) → IA-20; #193, #198, #200 (L332) → IA-21; #199 (L461) → DS-09.
- `ruff check`: clean. LF only (0 CR bytes).
- Under `--cov` only, 15 SQLAlchemy "GenericFunction already registered" `SAWarning`s appear (as in other files). Plain runs are clean.

## Discrepancies
None. DISCREPANCY-1 … 4 (revision 2) were closed by cases revision 3: AN-05 retired; RD-12, RD-15 and GP-12 insert valid rows and blank the field in memory.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 332->340 | unreachable | `notify_invoice_action`: the `required > 0` block's last `elif entity_type == "work_order"` being false. `required > 0` happens only for the four order types (any other type gives `(0, 0, True)`), so one of the four arms always matches. |

## Factories added
None. All builders are local to the test file.

## Notes for maintainers
- `transfer_number` and `sales_order_number` are unique across **all** workspaces. Since revision 3 the builders store `GN(n)`, so parallel processes never insert the same number and never block on each other.
- **When BUG-1202 / 1203 / 755 are fixed**, these cards XPASS (strict → fail). Remove the marker: 1202 → SU-07, BP-04, HA-05; 1203 → SU-08; 755 → SU-09. No pass card depends on the vacuous `(0, 0, True)` of a PO / TO / EO with no approvers (checked with the reference plugin).
- **When BUG-1205 is fixed**, remove the marker from FR-07, SU-19…22, PA-09, IA-17, SR-01, SR-03…05. IA-16 and SR-02 already pass and must keep passing.
- **When BUG-758 is fixed**, retire APN-GP-08 (spec G2). It asserts today's fallback text for a quantity-0 expense line.
- Recipients are compared as sorted lists (`recips`), never in row order.

## Revision history
- **2026-11-10 — cases revision 2.** First implementation: 189 cases, 169 passed, 16 bug xfails, 4 discrepancy xfails (card rows violate NOT NULL columns), 99% branch.
- **2026-11-10 — cases revision 3.** AN-05 deleted (retired). RD-12, RD-15, GP-12 now insert the order with its defaults and set the field to None in memory (cards changed); their discrepancy markers removed, closing DISCREPANCY-1 … 4. `GN` helper added; `to_` and `so` store `GN(n)`. Result 172 passed, 16 xfailed; line 161 now covered (GP-12); 99% branch (only the unreachable 332->340 remains). `--runxfail`: the same 16 bug xfails fail on Then 1. Reference plugin, all fixes + `--runxfail`: 188 passed; per fix 1202 → 3, 1203 → 1, 755 → 1, 1205 → 11 cards, 172 pass cards unchanged.
- **2026-11-10 — cases revision 4** (verifier F1 and F2). New IA-19…21, one parametrized test (transfer, expense, work order with `required_approvals=2`, an approved W1 approver notified, an approved suspended approver and an approved W2 approver row not), and new DS-09 (an order without `invoice_confirmed` → false). No other test changed. Result 176 passed, 16 xfailed, 0 discrepancies; 3 plain runs stable; 99% branch, only the unreachable 332->340 left. `--runxfail`: the same 16 bug xfails fail on Then 1. Reference plugin, all fixes + `--runxfail`: 192 passed; per fix unchanged (1202 → 3, 1203 → 1, 755 → 1, 1205 → 11, all 176 pass cards green). The ten verifier survivors (#149, #178, #191, #179, #192, #197, #193, #198, #200, #199) are all killed (see Verification runs).
