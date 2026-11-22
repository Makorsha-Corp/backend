# Execution notes — `app/services/purchase_order_service.py`

> Cases: `tests/unit/services/purchase_order_service.cases.md` (revision 4a, 2026-11-22) · Tests: `tests/unit/services/test_purchase_order_service.py` · Source commit: e48a092
> Result: 444 of 444 cases implemented · 321 passed · 123 xfailed (121 strict, 2 non-strict: LR-03, BR-05) · 0 open discrepancies · 0 errors — branch coverage 99% (692 statements, 192 branches; 5 lines / 3 partial branches missed)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_purchase_order_service.py -q -p no:cacheprovider -o addopts=""`

## How the tests are built
Normal mode, no local model. One test per card in card order (444); HF-03 … HF-06 share one parametrized test (param ids = case ids). Each test has a `# Then N` comment before the checks of its card's Then line N; `# [claude]` marks the 35 `Author: claude` cards.

- **Standing rows:** fixture `s` (namespace): `W0 < W1 < W2`, `U1 … U4` with the cards' names and W1 memberships (U4 inactive), and per workspace `SDk SPk SRk SCk`, `WFk`, `Fk`, `Ak`, `Ik` (suffix `0`, `1`, `9`), plus `I1b`, `TAG`.
- **Time:** autouse fixture `clock` patches `app.services.purchase_order_service.utcnow` to NOW (naive, like the real helper). `date.today()` is not mocked (that is what SD-07 / AR-04 catch).
- **Given rows:** `po(db, s, n, k, **but)` with dicts `READY`, `PROJ`, `COMPLETE(s)`, `VOIDED(s)`; `poline`, `inv(..., k=, linked=)` (+ `FINALIZED`, `LOCKED_INV`, `VOIDED_INV`; `link` sets `invoice_confirmed` for a finalized invoice on a ready order), `invl`, `poappr(approved=)`, `ret` (+ `REPLACE`, `COMPLETED(s)`, `VOIDED_RET`), `rline`, `cn`, `cash`, `spay`, `ev`, `repl(k, o_but, l_but, r_but, rl_but, cn_but)` (REPL group); section bases `rcvbase`, `srbase`, `crbase`, `vbase`; `rev` / `revi`; `stock()` (BUG-664 guard: inventory row + one opening ledger row dated T0). Each builder flushes.
- **Named checks:** `commit_point` (commit + `counts()` snapshot of the 16 listed tables), `mk_x`, `snap` (raw row dict = `unchanged`), `reread`, `x_gone`, `count_where`, `rows_where`, `EV`, `types`, `itypes`, `LINES`, `PAYS`, `SETTLE`, `LEDGER`, `RCVLEDGER`, `STOCK`, `WARN`, `REVENTS`, `AUDIT`, `notes`, `recips`, `session_clean`, `loaded`, `spies`, `failing_commit`, `failing_refresh`, `Recorder` (`after_cursor_execute`: `lock`, `exact_lock`, `exact_lock_of`, `before`, `locked_before`, `first_insert`, `no_lock`). `committed:` lines run `db.rollback()` once before the first of them.
- **C-09** uses the marker row `Department(workspace_id=W1.id, name=f"Marker {TAG}")` (`app.models.department`; only `workspace_id` and `name` are required, the rest have defaults), flushed after the commit point; Then 3 and 4 run in the same session before any test-level rollback.
- **Names that do not exist yet** (`receive_replacements`, `PurchaseOrderReturnReplacementCreate` imported inside `RQ`, `PurchaseOrderReturnEvent` read with `getattr`, `quantity_replaced`, `has_open_return`, `warnings`, `update_payment(user_id=)`) are written as the cards show them; their tests are strict xfail.
- **Forced errors / race:** C-03 … C-07, U-10, AI-05, UI-05, CI-09, CI-10 patch the manager method or `svc._sync_draft_invoice_for_po`; SD-10 patches `aim.create_invoice`; SD-16 / SD-17 wrap `aim.update_invoice`.
- **BUG-664:** no Given posts stock except V-20 and V-22, whose cards prescribe `create_receive_event` Given steps; their ledger rows are re-dated into the past (T0, T0+1 min, in id order) so the void's reversals never read a tie. CR-18's Given receives on a project order (no stock).
- **TC3 (rev 4):** every write-method error card with X checks `X not in db` right after the raise, before any test rollback; one error card per write method runs the call inside `spies` and checks `rb.call_count >= 1`.
- **Rollback-strip check:** `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3e\po_svc\strip_rollback.py` (own plugin; `STRIP_METHOD=<method> PYTHONPATH=<folder> pytest -p strip_rollback`) recompiles one method with its rollback calls replaced by `None`, in the real module's globals, and sets it on the class; app/ is only read.
- **xfail mapping (`--runxfail`):** all 123 xfails fail on their card's named line; the RX cards, VR-08 and X-06 fail inside the When call ("the call raises"), RX-23 / RX-37 in the Given (no `quantity_replaced`), RX-47 / RX-49 in Given 2 with the `ImportError` their cards name. Checker: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3e\po_svc\check_runxfail.py`.
- **Reference plugin:** `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3e\po_svc\ref_plugin.py` (in-process patches, never app/). It needs a private database because it adds the new table `purchase_order_return_events` and the columns `quantity_replaced`, `invoice_payments.source_type / source_id`: `TEST_DATABASE_URL=…/marker_poref_test PYTHONPATH=<folder> pytest -p ref_plugin --runxfail` → **444 passed** (CR3a floor added for BUG-3186).

## Discrepancies
None open. All eleven of revision 2 are resolved by cases revision 3 (spec Gap log G13–G19):

| ID | Resolution in cases rev 3 | Test now |
|---|---|---|
| DISCREPANCY-1 | read cards check `X in db`; RF-07, AO-21 check `not db.new` | `# card:` comments removed; `len(db.new) == 0` → `not db.new` |
| DISCREPANCY-2 | the table is `inventory` everywhere | comment removed |
| DISCREPANCY-3 | IC-04 → xfail BUG-3184 | strict xfail, fails on Then 1 |
| DISCREPANCY-4 | DD-04, V-02 → xfail BUG-3185 | strict xfail, fail on Then 5 / Then 2 |
| DISCREPANCY-5 | DD-05, V-10 → xfail BUG-639, PAYHIST check added | strict xfail, both fail on Then 1 (raw `IntegrityError`, not `HTTPException`; card: Then 1–3) |
| DISCREPANCY-6 | C-09 rebuilt with the `Department` marker row and same-session checks | strict xfail BUG-3175, fails on Then 3 (the flushed order is still found) |
| DISCREPANCY-7 | G-01 reads `item_count` through `PurchaseOrderResponse`, checks the ORM order has none | pass |
| DISCREPANCY-8 | AR-05 → plain pass on the stored lines (BUG-3163 withdrawn) | pass |
| DISCREPANCY-9 | AO-11, AO-12 vary WF1's sequence | pass |
| DISCREPANCY-10 | X-01 → xfail BUG-2888; new pass companion X-08 | strict xfail, fails on Then 3 |
| DISCREPANCY-11 | PT-03, PT-04 read the tuple rows (PT2) | pass, plus the new tuple-shape checks |

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 382–383 | dead | create's re-raise / 500 after the retry loop (spec Not specified, Q7) |
| 1312–1313 | deferred to BUG-639's fix | `sync_items` phase 2 re-raises an `HTTPException` after rollback; SY-04's draft-delete refusal reaches it once BUG-639 makes it a 400 (today it is an `IntegrityError`, covered by 1309–1310) |
| 1482 | unreachable | "Could not create draft invoice": after a forced sync with a supplier the order always has an invoice or the sync raised |

## Factories added
None.

## Notes for maintainers
- When a BUG-n is fixed its strict xfails XPASS: remove the marker. BUG-2810 / BUG-3176 need, besides the method: model `PurchaseOrderReturnEvent`, columns `purchase_order_return_items.quantity_replaced`, `invoice_payments.source_type / source_id`, `warnings` on `PurchaseOrderReturnResponse`, `has_open_return` on `PurchaseOrderResponse`, and a `user_id` parameter on `InvoicePaymentManager.update_payment` (RX-46 / RX-57 pass it; it has none today).
- LR-03 and BR-05 are non-strict (heap / tie order); their strict SQL alarms are LR-04 and BR-04.
- Statement-recorder cards end their Given with `db.expunge_all()`; ids are taken before it.
- Three plain runs (rev 3): `293 passed, 120 xfailed, 1 xpassed`, then twice `293 passed, 121 xfailed`; the XPASS is one of the non-strict tie / heap-order cards (LR-03 / BR-05), which can pass by chance — that is why they are non-strict. Branch-coverage run: `293 passed, 121 xfailed`. ruff check clean; LF endings.

## Revision history
- **Revision 2 (2026-11-22).** First implementation of all 407 cards (11 discrepancies).
- **Revision 3 (2026-11-22).** Cases rev 3 resolve all 11 discrepancies; every `disc()` marker and the `_DISC` table removed. Markers now match the cards: IC-04 xfail BUG-3184; DD-04, V-02 xfail BUG-3185; DD-05, V-10 xfail BUG-639 (Then 3 PAYHIST added, V-10's later Thens renumbered); C-09 rebuilt (marker row `Department`, same-session checks), strict xfail BUG-3175; X-01 xfail BUG-2888. G-01, AR-05, AO-11, AO-12, PT-03, PT-04 rewritten to their new cards (pass). New tests: AO-22, X-08, RI-05, SY-10, SY-11, SY-12 (xfail BUG-3179), SY-13. Imports `Department`, `PurchaseOrderResponse`; bug titles 639, 3184, 3185. Reference plugin: no longer sets item-summary defaults on get (G-01 now expects none); `sync_items` keeps the phase of the step that failed (SY-11). Re-checked: `--runxfail` 121 failures, 0 mismatches against the cards' Fails-today lines; plugin 414 passed; branch coverage 99%; ruff clean; LF.
- **Revision 4 (2026-11-22).** Verifier findings (cases rev 4). TC3: 30 error cards (C-06, C-07, U-02, U-09, U-10, MC-02, RE-20, SR-06, SR-12, CR-07, CR-12, VR-05, X-02, AI-04, AI-05, UI-03, RI-03, RI-05, SY-08, SY-10, SY-12, AA-03, RA-02, SA-02, V-05, V-10, CI-02, CI-05, RX-24, RX-29) now check `X not in db` right after the raise; 16 of them newly run inside `spies` and check `rb.call_count >= 1` (RI-05, SY-10, CI-09 already did); later Then numbers shifted. DD-04 and V-02 cut to the BUG-3185 `invoice_id` (xfail, Then 1); new pass companions DD-06 and V-21. SD-13 adds Then 8 (reset reason) and Then 9 (notification `entity_type` / `entity_id`). SY-12 fails on Then 3 (`X not in db`). New pass tests: IE-24 … IE-32, C-12, U-12, PG-08, PG-09, HS-06, RE-43 … RE-45, AR-08, SR-15, CR-17, AO-23 … AO-25, SY-14, V-22. AO-22 moved before AO-21 (card order).
- **Revision 4a (2026-11-22).** New CR-18, CR-19 (strict xfail BUG-3186, fail on Then 1: no refusal today) and CR-20 (pass, a line ending at exactly 0). Reference plugin: CR3a floor (refuse with the 400 text before any write; received printed with 2 places). Re-checked: three plain runs `321 passed, 123 xfailed` (identical); `--runxfail` 123 failures, 0 mismatches; plugin 444 passed; branch coverage 99% (gaps unchanged: 382–383 dead, 1312–1313 after BUG-639, 1482 unreachable); ruff clean; LF.
- **Rollback-strip results (rev 4a).** Removing a method's rollback fails at least one test for every write method: create_purchase_order — C-06, C-07; update_purchase_order — U-02, U-09, U-10; mark_order_complete — MC-02; create_receive_event — RE-20; start_return — SR-06, SR-12; complete_return — CR-07, CR-12; void_return — VR-05; delete_purchase_order — X-02; add_item — AI-04, AI-05; update_item — UI-03; remove_item — RI-03, RI-05; sync_items — SY-04, SY-08, SY-10, SY-11, SY-13, SY-14; add_approver — AA-03; remove_approver — RA-02; set_approval — SA-02; void_purchase_order — V-05; create_invoice_for_purchase_order — CI-02, CI-05, CI-09.
