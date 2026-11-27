# Verification — `app/managers/purchase_order_manager.py`

> **Verdict:** NEEDS WORK
> Tests: 351 passed · 104 xfailed (reproduced ✅ in run 1; runs 2 and 3: 351 passed · 103 xfailed · 1 xpassed, GI-04) · coverage 93% branch
> Mutation: 900 mutants · 732 killed · 168 survived → score 96.4% (after excluding 25 equivalent, 22 dead, 94 bug-path; 27 case-missing remain)
> Source commit: e48a092 · Cases revision: 3

## Summary
The tests can be trusted for what they cover. All 455 cards are present with the right markers. In every test, each Then line is asserted as the card writes it (checked mechanically, then read side by side), and no test is unfaithful to its card. Every strict xfail fails on the Then line its card names. 44 of 47 hand variants are killed (money, delete/invoice, Complete kept, workspace scoping, commits inside, `performed_by`, rounding, stage spelling, lock shape). Two things keep the verdict at NEEDS WORK. First, 27 surviving mutants and 3 surviving hand variants show rules with no card. All of these are case-designer work, mostly the event metadata in `sync_items` plus a few boundaries. Second, GI-04 flips between XFAIL and XPASS, against what the notes say.
Dead-code claims in the notes hold, with one exception. `update_item`'s receiving path (1152-1161, 1205-1286) is not dead: `PUT /purchase-orders/items/{id}/` still reaches it today, so it is a bug-path for BUG-2887.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | Flaky test | POM-GI-04 | The non-strict xfail XPASSes in 2 of 3 plain runs and in the `--runxfail` run. The notes say "today it fails (xfail) in every run seen". The card rests on physical row order, so it gives no signal; GI-05 already pins the ORDER BY. | run 1: `351 passed, 104 xfailed`; runs 2, 3: `351 passed, 103 xfailed, 1 xpassed` (XPASS test_pom_gi_04); `--runxfail`: 103 failed, GI-04 passed | case designer: make the order deterministic, or retire the card in favour of GI-05. Executor: update the notes' Result line and the GI-04 maintainer note. |
| 2 | Notes misclassification | notes "Coverage gaps", lines 1152-1161 and 1205-1286 | The notes call these lines "dead". The schema still accepts `quantity_received` and the endpoint passes it through (`purchase_orders.py:659-664` → `purchase_order_service.update_item` → manager), so the lines run today. They are a bug-path for BUG-2887, not dead code. | `PurchaseOrderItemUpdate.quantity_received: Decimal \| None = None` (`app/schemas/purchase_order.py:38`) | executor (notes) |
| 3 | case-missing | `update_purchase_order` R8 | No card asserts that an `order_date` change is logged in `details_updated` with label `Order date`. UP-32 and VC-05 change it but check only the row. CF-04 passes its own dict. | survivors L50 `'order_date'`→`''`, `'Order date'`→`''` | case designer |
| 4 | case-missing | `update_purchase_order` R7 (invoice section) | No card unconfirms `invoice_confirmed` on an unlocked order. That case should log `invoice_unconfirmed` / `Draft invoice unconfirmed` and reset approvals. | survivors L78 ×3 (`'invoice_confirmed'`, `'invoice'`, `'Draft invoice'` → `''`) | case designer |
| 5 | case-missing | `_format_field_value` R2 | FV-02 sends `"Project"`, which already equals its label, so the `project` → `Project` mapping is never exercised. Use `"project"` or `"PROJECT"`. | survivor L71 `'project'`→`''` | case designer |
| 6 | case-missing | `_format_field_value` R6 | No card sends `None` for an "other" field (expected `—`), e.g. a description changed from empty to "Urgent" logged with from_value `—`. | survivors L690 negate, `Eq`→`NotEq` (they give `All assigned` instead of `—`) | case designer |
| 7 | case-missing | `_validate_section_confirm` R2 ("after the update") | No card confirms details where the destination type or id arrives in the same update on a record that has none. Every card's record already has a destination. | survivors L857 `'destination_type'`→`''`, L858 `'destination_id'`→`''` | case designer |
| 8 | case-missing | `sync_items` R3, R5, R6 | Several event details have no card. Removal event metadata is unasserted (SY-01 checks the description only). The update event's description `Updated item: Bolt` and its metadata are unasserted (SY-17 checks types only). Addition metadata is unasserted. Two distinct additions numbered n+1, n+2 have no card, and neither do additions to an order with no lines (starting at line 1). | survivors L1384-1386, L1413 ×2, L1417, L1420-1422, L1428 `0`→`1`, L1451-1455, L1458 `1`→`2` (16 mutants) | case designer |
| 9 | case-missing | `approval_summary` R3 boundary | No card has exactly one approver and no threshold, which should give (·, 1, ·). AS-04 and AS-05 have 3 and 2 approvers. | survivor L1501 `> 0` → `> 1` | case designer |
| 10 | case-missing | `approval_summary` R2 ("0 included") | AS-03 tests threshold 0 only with no approvers, so treating 0 as "not set" passes. Missing: threshold 0 with unapproved approvers → `(0, 0, True)`. | hand variant V05 (`if po.required_approvals:`) survived, 351 passed | case designer |
| 11 | case-missing | RP5 (PO), `is_po_financially_locked` R1 | No pass card shows that a completed order (complete by V) stays financially locked. A variant that unlocks completed orders passes every test, yet RP5 relies on this lock to keep supplier, details and lines frozen. One example card: AI on complete-by-V → 400 `Confirmed after invoice creation` (holds today and after BUG-2885). | hand variant V36 (`… or po.order_completed: return False`) survived, 351 passed | case designer |

No fidelity findings: no missing, weakened or changed assertion, no wrong setup, no swallowed failure, no extra mocks. The only patches are `utcnow` (the cards' clock) and `ensure_po_workflow_record` (WF-05, WF-06 as their cards say). No dishonest xfail.

## Surviving mutants
Grouped; the full list is in scratch `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\ordersv\po\classified.json`.

| # | Line(s) | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | 1135, 1146-1148, 1152-1163, 1170-1171, 1205-1290 (85 mutants) | all kinds | bug-path | `update_item` receiving path. BUG-2887 refuses `quantity_received` at the schema, and no manager card sends it (SCH-21…23 are xfail). | — |
| 2 | 466, 467, 469 | event strings, `return True`→`False` | bug-path | `reopen_for_return` reopening is BUG-2789; RO-02 (xfail) pins the intended no-op. | — |
| 3 | 548:71, 1129:71 | `exclude_none` True→False | bug-path | Keeping explicit nulls is the BUG-2879 fix (UP-33…36, UI-15/16 xfail). | — |
| 4 | 1504 | `required = 0`→`1` | bug-path | BUG-1202 (AS-06 xfail expects 1). | — |
| 5 | 1102, 1445 | `'Item #'`→`''` | bug-path | Fallback name for an item outside the workspace, reachable only through BUG-1017 (AI-11, SY-21 xfail). | — |
| 6 | 58 ×2, 804 ×2 | STATUS_LOG_FIELDS, status branch strings | dead | `update_purchase_order` pops `current_status_id` (spec Q5, removal checklist). | — |
| 7 | 80 ×4 | `PO_STAGE_NAMES` strings | dead | The constant is never read (`grep` finds no reader in `app/`). | — |
| 8 | 632, 633 ×2 | `required_approvals` branch of `_format_scalar_value` | dead | Shadowed by `_format_field_value` R4 (spec Q5). | — |
| 9 | 934 ×2, 936 | `list_purchase_orders` | dead | No caller; the service's `list_purchase_orders` uses `list_purchase_orders_page`. | — |
| 10 | 1508 ×2 | `approvals_met` | dead | No caller (spec Q5). | — |
| 11 | 127, 1594 ×2, 1598, 1599, 1601 | `'locked'`, withdraw-locked check | dead | Invoice status `locked` is never written (BUG-2735, spec `set_approval` R4 "dead"). With it gone, the `invoice_id is not None` guard only feeds that dead check. | — |
| 12 | 630 ×4 | negate, `In`→`NotIn`, `'description'`, `'notes'` | equivalent | Every live path of `_format_scalar_value(None)` returns `—` whichever branch is taken (the `required_approvals` branch in between is dead, #8). | — |
| 13 | 690:20 | `'required_approvals'`→`''` | equivalent | The field then goes through `_format_scalar_value`, whose branch 632-633 gives the same `All assigned` and `str(n)`. | — |
| 14 | 548:52, 1129:52 | `exclude_unset` True→False | equivalent | Every field of both schemas defaults to `None`, which `exclude_none=True` then drops. | — |
| 15 | 162, 599 | `getattr(..., False)` default →`True` | equivalent | The attribute always exists on the model. | — |
| 16 | 1111, 1112, 1454:66, 1455:60 | the field argument of `_format_scalar_value` → `''` | equivalent | The field name matters only for `None` with description, notes or required_approvals; here it is quantity or price, whose `None` gives `—` either way. | — |
| 17 | 1180 | `update_dict['unit_price']`→`['']` | equivalent | The parsed price equals the schema's Decimal already stored under `unit_price`. | — |
| 18 | 1408 ×2, 1409 | legacy `quantity_received is None` | equivalent | `quantity_received` is NOT NULL and `session.refresh` reads it from the database. Writing the stored value back changes nothing. | — |
| 19 | 1191, 1313, 1369, 1374, 1413:69 | `'Item #'`→`''` | equivalent | `item_name` comes from `items` through a NOT NULL RESTRICT FK, so the fallback cannot run. | — |
| 20 | 1540, 1559 | `'User #'`→`''` | equivalent | `user_id` is a NOT NULL FK to `profiles` (CASCADE), so the profile always exists. | — |
| 21 | 1501:13 | `> 0`→`>= 0` | equivalent | With 0 approvers both arms give `required = 0`. | — |
| 22 | 50 ×2, 71, 78 ×3, 690:8, 690:11, 857, 858, 1384-1386, 1413:29, 1413:45, 1417, 1420-1422, 1428, 1451-1455:20, 1458, 1501:30 (27) | see Findings 3–9 | case-missing | Spec rules exist; no card checks them. | case designer |

### Hand variants (own scratch runner `…\ordersv\po\hv\run_variants.py`; temp copies only)
| Variant | Result | Killed by |
|---|---|---|
| `sync_po_stage` keeps Complete only when fully received (BUG-2810) | killed | SS-03 |
| `_recalc_totals` from qty×price / total not set / no flush | killed | SY-22 / AI-01, RT-01… / RT-01, SY-01… |
| HR-15: `_line_subtotal` ROUND_HALF_EVEN, ROUND_DOWN | killed (pass suite) | CR-07 (pass card), plus LS-04/05, CR-06 under `--runxfail` |
| HR-15: ROUND_HALF_UP (the fix) | LS-04/05, CR-06 pass; full pass suite 351/351 | — |
| delete refuses any linked invoice / blocks a confirmed invoice of any workspace / removes any linked invoice (BUG-2888) | killed | DL-14, DL-15 / DL-16 / DL-15, DL-16 |
| `is_po_financially_locked` off once complete (invoice freeze after completion) | **survived** | → Finding 11 |
| threshold 0 read as "not set" | **survived** | → Finding 10 |
| workspace scoping dropped: financial lock, stage name, ensure stage, resolve stage, storage/machine/account formatting, payment status, approver membership, approver position, duplicate-item name | all killed | FL-03/04, CS-02/03, ES-01, RS-…, FD-03/04, FD-08, FV-01, IP-03, AA-06/07, LA-01, EC-04 |
| `set_approval` approve reads the order without workspace | survived, equivalent | Only reachable through a W1 approver row on a foreign order, which is invalid cross-workspace data |
| `session.commit()` inside mark complete / sync / delete / log_event / update / set_approval | all killed | MC-16, SY-25, DL-20, 20 commit-spy cards, UP-44, SA-13 |
| `log_event` drops `performed_by`; update/complete skip `updated_by` | killed | 16 cards; UP-31; MC-01 |
| mark complete overwrites the delivery date; withdraw after completion allowed; paid on `partial` | killed | MC-02; SA-07; SP-02 |
| sync numbering from the original max; additions skip the duplicate check; stage sync skipped | killed | SY-01, SY-20; SY-18/19; SY-17 |
| receiving through the line edit: invoice check dropped / `quantity_received` structural (BUG-2887) | survived, bug-path | — |
| `reopen_for_return` keeps the delivery date (BUG-2789) | survived, bug-path | — |
| BUG-1881: `_is_po_complete_stage` lower+strip / lower only | CP-02, CP-05 pass / CP-05 fails | as designed |
| BUG-1881: `_ensure_po_stage_statuses` lower(trim) / lower only | ES-04/05 pass / ES-05 fails | as designed |
| BUG-1881: resolve stage lower only | RS-04 fails | as designed |
| BUG-2872: every order read `FOR UPDATE` | 9 lock cards pass under `--runxfail`; RM-10 still fails (remove_approver reads no order row: expected); pass suite 351/351 | — |
| BUG-2872: `FOR UPDATE SKIP LOCKED` / `NOWAIT` | all 10 lock cards fail | as designed |

## Traceability
cards 455 · tests 455 · unmatched: none · duplicate IDs: none. Every `# [claude] <ID>` matches the test name and its card. Marker mismatches: none. 351 pass cards carry no marker. 104 xfail cards carry `xfail(strict=True)` through `xf(X…)` with every listed BUG ID; GI-04 is non-strict as its card says. Every BUG ID exists in `docs/testing/bugs.md`. `# Then N` comments match each card's numbered Then lines (455/455), and every section asserts.
`--runxfail`: every strict xfail fails in the Then block its card's "Fails today on" names (my own plugin maps the failing line to its `# Then N`). DL-17 fails on the call (TypeError), as its card says. Exception types: 60 `DID NOT RAISE`, 41 AssertionError, 2 TypeError (DL-17/18); no setup or import errors.

## Commands run
```
COVERAGE_FILE=…\ordersv\po\.coverage
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_purchase_order_manager.py -q -p no:cacheprovider -o addopts="" --cov=app.managers.purchase_order_manager --cov-branch --cov-report=term-missing
  app\managers\purchase_order_manager.py  743  41  300  9  93%  633, 802, 936, 1117->1119, 1152-1161, 1187->1190, 1205-1286, 1319->1321, 1409, 1508, 1599
  351 passed, 104 xfailed, 22 warnings in 86.10s
.venv/Scripts/python.exe -m pytest … -o addopts="" -p vfails --runxfail -rf      (vfails = own scratch plugin)
  103 failed, 352 passed, 7 warnings in 51.61s   (the one extra pass: GI-04, non-strict)
.venv/Scripts/python.exe -m pytest … -o addopts="" -rxX     (run 2)
  351 passed, 103 xfailed, 1 xpassed (XPASS test_pom_gi_04)
.venv/Scripts/python.exe -m pytest … -o addopts="" -rxX     (run 3)
  351 passed, 103 xfailed, 1 xpassed (XPASS test_pom_gi_04)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/purchase_order_manager.py tests/unit/managers/test_purchase_order_manager.py --lines <range> --timeout 500 --json …\ordersv\po\mut[b]-<range>.json
  18 line-range shards (6 + 12 overlapping), merged by (line, col, operator, change): 900 unique mutants · 732 killed · 168 survived · 0 timeout, no inconsistent duplicates
```

## Round 2 — 2026-11-21

> **Verdict:** PASS
> Tests: 364 passed · 103 xfailed · 0 xpassed, identical in 3 runs (reproduced ✅) · Cases revision: 4 · Source commit: e48a092 (unchanged)
> Mutation (targeted): the 27 case-missing survivors re-run → 27 killed; hand variants V05 (threshold 0 read as unset) and V36 (lock dropped after completion) → killed. Score after Round 2: 759 / 759 = 100% (excluding 25 equivalent, 22 dead, 94 bug-path)

**Fidelity.** Traceability re-checked by script: 467 cards · 467 tests · markers match · `# Then N` matches every card. GI-04 card and test are both gone. Each new or changed test was read against its card: UP-50, UP-51, VC-12…14, FV-02 (now `"project"`), FV-09, FL-08, AI-17, SY-26…28, AS-07, AS-08. Each Given and every Then line is reproduced as written. No findings.

**Findings 1–11:** closed. Finding 1: GI-04 retired; the 3 runs show no XPASS. Finding 2: notes fixed, per the coordinator. Findings 3–11: every targeted mutant or variant is now killed:

| Survivor | Killed by |
|---|---|
| L50 ×2 | UP-50 |
| L71 | FV-02 |
| L78 ×3 | UP-51 |
| L690 ×2 | FV-09 |
| L857 | VC-12, VC-13 |
| L858 | VC-13 |
| L1384-1386, L1413 ×2, L1417, L1420-1422, L1451-1455 | SY-26 |
| L1453 | SY-26, SY-27 |
| L1428 | SY-28 |
| L1458 | SY-27, SY-28 |
| L1501 | AS-07 |
| V05 | AS-08 |
| V36 | FL-08, AI-17 |

**Commands:** 3 × `pytest tests/unit/managers/test_purchase_order_manager.py -q -p no:cacheprovider -o addopts="" -rxX` → `364 passed, 103 xfailed` each. Targeted mutants: own runner `…\ordersv\po\hv\r2.py`. It applies `mutate.py`'s own `_apply` to the 27 sites on a temp copy and runs `-m "not xfail"`.
