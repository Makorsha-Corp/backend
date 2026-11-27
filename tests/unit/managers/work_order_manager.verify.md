# Verification — `app/managers/work_order_manager.py`

> **Verdict:** NEEDS WORK
> Tests: 445 passed · 102 xfailed (reproduced ✅ run 1; runs 2–3 the two non-strict cards XPASS, see F-1) · coverage 99.5% branch (788 stmts, 1 missed; 346 branches, 5 partial — matches the notes)
> Mutation: 989 mutants · 904 killed · 85 survived → score 93% (904 / 971, after excluding 16 equivalent, 2 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 3

## Summary
The tests are faithful: every one of the 547 cards has exactly one test, every marker matches its Expect line, every strict xfail fails on its card's "Fails today on" Then line, and I found no weakened, missing or swallowed assertion in the cards I read (all hand-variant areas plus the CI/RIC/ADJ/AIC/FC/V/SA/AS/RAS sections, and a script check of every Then line). The BUG-664 setup rules hold. The bug cards for BUG-2929, 2930 and 2931 tell a right fix from a wrong one. Five wrong fixes of each kind were all caught.
What must change is the cases, not the tests. 56 surviving mutants and 3 hand variants show behaviour the spec states but no card checks. Most of it is in stock and money paths: re-averaging with a change of more than 1, adjusting a line drawn from a machine, Replace / Borrow texts, which factory's damaged stock, and the `updated` log for account changes. Another 11 survivors, plus 7 hand variants, show behaviour the spec does not state: who is recorded as the performer of lifecycle events and stock rows, and the `source_type` / fallback cost of the completion postings. The two non-strict cards give a different result from run to run.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| F-1 | flaky (non-strict xfail) | WOM-LA-05, WOM-GI-05 | They depend on physical row order, which changes under concurrent load, so their outcome is not stable and they carry no signal. | run 1: 102 xfailed; run 2: 101 xfailed + 1 XPASS (LA-05); run 3: 100 xfailed + 2 XPASS; `--runxfail`: GI-05 passed. GI-04 already pins the `ORDER BY` by statement. | case designer: make LA-05 a statement check (`ORDER BY … id`) like GI-04, and retire or restate GI-05 |
| F-2 | case-missing (lock definition) | Conventions "locks t"; ST-18 and every lock card | "Some SELECT naming t contains FOR UPDATE" accepts `FOR UPDATE OF work_order_items` on a join that names `work_orders` (variant F18 passes ST-18). It also accepts a lock taken after the state check, before the first write (variant F20 passes ST-18), although spec R9 says "before R2". | hv logs `F18_lock_other_table_of`, `F20_lock_after_state_check` | case designer: require the `FOR UPDATE` (no `OF`, or `OF work_orders`) on the first SELECT of `work_orders` in the When |
| F-3 | case-missing | `_apply_item_completion` R6 | Damaged stock must go to the **order's** factory, but every Replace card has the line's source and the machine's factory equal to the order's F1. | variants B01 (`location_id=item.source_location_id`) and B34 (the machine's factory) both pass | case designer: a Replace card whose line is sourced from F2 (or whose machine sits in F2) and asserts `led(F1, I2, DAMAGED)` |
| F-4 | case-missing | `_adjust_consumed_item_quantity` R7 | A decrease after a re-averaged increase is not tested, so `total = unit_cost × new qty` cannot be told from `old total − unit_cost × d`. | variant B22 passes. Example: 4 @ 2.88 (total 11.50) → 3 gives 8.64 vs 8.62 | case designer |
| F-5 | spec-gap | start R7, complete-as-planned R8, finalize R6/R9, void R8, `_consume_item` R4, `_reverse_item_consumption` R2, `_apply_item_completion` R2–R8 | The spec never says who is recorded as `performed_by` on the started / completed / voided events, the machine `work_order_completed` activity, or the ledger rows of reversal and completion. A wrong actor goes unnoticed. | variants B10, B11, B12, B13, B15, B29, B30 all pass (actor replaced by `wo.created_by` or `None`) | describer (fill-gaps), then case designer |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1–2 | 67 | `'machine_id'` / `'project_component_id'` → `''` in `DETAILS_FIELDS` | equivalent | R4 always puts both keys into `update_dict` together, so the other key keeps every intersection true | — |
| 3–7 | 75, 79, 81 | `'project_component_id'`, `'account_id'` keys and the `Project component` / `Account` / `Required approvals` labels → `''` | case-missing | Overview lists these logged fields and labels; no CFC/U card logs a change of account, component or required approvals | case designer |
| 8–9 | 138 | `delta < 0` → `<= 0` / `< 1` | equivalent | `delta == 0` returns earlier; `delta` is an int ≠ 0 | — |
| 10 | 370 | `getattr(a, 'approver_slot')` → `''` | case-missing | CT R7 "added … with its slot"; no template approver with a slot | case designer |
| 11 | 393 | `exclude_none=True` → `False` | case-missing | U R4 "fields sent as null are dropped" — no card sends null for an ordinary field (e.g. `description=None`) | case designer |
| 12–13 | 402, 404 | `project_component_id` key → `''` in the machine/component exclusivity | case-missing (revisit after launch) | U R4: setting a machine clears a stored component and vice versa; no card has an order with a component | case designer |
| 14–15 | 483 | `'machine_id'` / `'project_component_id'` → `''` | equivalent | same pairing as #1–2 | — |
| 16 | 505 | `and` → `or` (`assigned_to` re-match) | case-missing | U R17 tested only where `assigned_to` is sent; not "not sent → assignees untouched" with rows out of step with the text | case designer |
| 17 | 527 | default `limit` 100 → 101 | case-missing | signature default; no list call without `limit` over 100 rows (low) | case designer |
| 18–19 | 675, 694 | `'User #'` → `''` | equivalent | an approver row always has a profile (FK, membership checked), so the fallback cannot run | — |
| 20 | 715 | fallback `'Order is not ready for approval'` → `''` | equivalent | `approvability_gap_reason` is not None exactly when `is_approvable` is False | — |
| 21 | 756 | `activity_event_type='consumption'` → `''` | equivalent | `post_stock_out` falls back to `transaction_type`, also `consumption` | — |
| 22–28 | 777 ×3, 778 ×4 | component activity description / metadata keys | case-missing (revisit after launch) | `_consume_item` R7 "the same entry"; CI-15 checks only the type | case designer |
| 29 | 794 | reverse `source_type='work_order'` → `''` | spec-gap | `_reverse_item_consumption` R2 does not state `source_type` / `source_id` | describer |
| 30 | 828 | `new_int <= 0` → `<= 1` | case-missing | ADJ R3 boundary: no card adjusts to 1 (only to 0) | case designer |
| 31–32 | 837 ×2 | source label `machine #` | case-missing | ADJ R8 `(<source>)`; only a storage source is tested | case designer |
| 33 | 840 | `delta > 0` → `>= 0` | equivalent | `old == new` returns at R1, so `delta ≠ 0` | — |
| 34 | 848 | adjust-up `source_type` | spec-gap | ADJ R4 does not state it | describer |
| 35 | 853 | `'consumption'` → `''` | equivalent | falls back to `transaction_type` `consumption` | — |
| 36–39 | 855 ×4 | `Additional <d> <name> consumed … (qty adjustment)` | case-missing | ADJ R4 activity text; no machine-source adjust card | case designer |
| 40 | 858 | `total_cost or Decimal(0)` → `Decimal(1)` | case-missing | ADJ R6 "old total (or 0)"; no increase on a line without a total | case designer |
| 41 | 859 | `unit_cost * d` → `/ d` | case-missing | every increase card has d = 1; R6 needs a d > 1 card (money) | case designer |
| 42 | 870 | decrease `unit_cost or Decimal(0)` → `Decimal(1)` | case-missing | ADJ-12 (no unit cost) does not check the reversal row's `unit_cost` | case designer |
| 43 | 872 | adjust-down `source_type` | spec-gap | ADJ R5 does not state it | describer |
| 44 | 874 | notes `' — '` | case-missing | ADJ-11 pins only `endswith(" qty reduced by 1")`; the spec elides the prefix as well | case designer (and describer for the full text) |
| 45 | 877 | `'consumption_reversed'` → `''` | case-missing | falls back to `consumption_reversal`; ADJ R5 activity type with a machine source is not tested | case designer |
| 46–49 | 879 ×4 | `Returned <d> <name> — work order <n> line qty adjusted` | case-missing | ADJ R5 activity text, machine source | case designer |
| 50 | 912 | `'CONSUME'` → `''` | equivalent | a CONSUME line then matches none of the `elif` branches: still a no-op | — |
| 51, 54 | 922, 966 | `unit_cost or Decimal(0)` → `Decimal(1)` (Install, Replace-in) | spec-gap | R2/R7 say "at the line's unit cost"; the cost for a consumed line with no `unit_cost` is not stated | describer |
| 52–53, 55–56 | 923, 941, 951, 967 | `source_type='work_order'` of the completion postings | spec-gap | AIC R2–R7 do not state `source_type` / `source_id` | describer |
| 57–63 | 942 ×2, 945 ×3, 952 ×2 | Replace-out notes and activity text, damaged notes | case-missing | AIC R4/R6 texts; AIC-06 checks only the transaction types | case designer |
| 64–68 | 968 ×2, 971 ×3 | Replace-in notes and activity text | case-missing | AIC R7 text | case designer |
| 69–70 | 979, 980 | Borrow fallback cost / `source_type` | spec-gap | AIC R8 as #51–56 | describer |
| 71–72 | 981 ×2 | Borrow notes `<n> — <name> returned` | case-missing | AIC-10/11 do not pin the ledger notes | case designer |
| 73–75 | 1187 ×2, 1201 | complete-as-planned `started` description | case-missing | CAP R8 "as start R7"; CAP-02 checks types and metadata, not the text | case designer |
| 76 | 1283 | component completed metadata `work_order_id` | case-missing (revisit after launch) | FC R8 | case designer |
| 77 | 1412 | `update_item` `exclude_none=True` → `False` | case-missing | UI R3 "null fields are dropped"; no card sends null | case designer |
| 78 | 1426 | `and` → `or` | equivalent | quantity sent and equal reaches the adjust, which returns at R1 | — |
| 79–80 | 1468, 1470 | duplicate locked refusal in `remove_item` | dead | spec R1: dead code (Q8), on the removal list | — |
| 81 | 1476 | `and` → `or` | equivalent | `_reverse_item_consumption` returns for a line not consumed; consumed lines exist only on started orders | — |
| 82 | 1488 | `and` → `or` | case-missing | RI R6 "DRAFT with recorded approvals → reset"; no in-progress removal with an approved approver | case designer |
| 83 | 1587 | `model_dump(mode='json')` → `mode=''` | equivalent | `_apply_sheet_entry_lines` rebuilds `Decimal(str(q))` either way | — |
| 84–85 | 1722, 1756 | default `exclude_completed` False → True | case-missing | signature default of the sheet list and count; SH cards always pass it (low) | case designer |

**Hand variants** (my plugin re-executes a text-edited copy of the module in place; `app/` untouched; scratch `…\ordersv\wo\hv\`). 36 break variants (B*) run against the pass cards, and 20 fix variants (F*) run with `--runxfail`. Two of them, B08 and B35, were badly built and are not counted; their replacements are B08b and F20.
- **Caught:** damaged at cost 0 (B02, B27), reversal / adjust / install / replace-in / borrow costs (B03, B04, B31–B33), Borrow return place (B05), status restore at finalize / void (B06, B07, B09, B28), chosen status ignored (B08b: CAP-12, FC-13), `consumed_by` (B14), workspace filters in get / update_item / remove_item / set_approval (B16–B19), ADJ rounding down / delta-only cost (B20, B21), qty rounding (B23), a commit in start / void / add_item (B24–B26).
- **Fix-direction:** the correct fixes for BUG-2929, 2930, 2931 and 1040, and the correct lock, each turn exactly their cards green with no pass card red. These wrong fixes are caught: 2929 blocks a voided invoice (U-45), cost only (U-43/44 stay red), blocks the same value (U-46); 2930 counts deleted lines (U-56), counts CONSUME lines (U-55), blocks any machine change (U-54), misses the component path (U-52 stays red); 2931 checked before the 403 (SA-04, SA-11), also on drafts (about 30 pass cards); `SKIP LOCKED`, `NOWAIT`, `FOR SHARE`, lock after the first write (ST-18 stays red).
- **Not caught:** B01, B34 (F-3); B22 (F-4); B10–B13, B15, B29, B30 (F-5); F18, F20 (F-2).

## Traceability
Cases 547 · tests 547 collected (516 `# [claude]` blocks, parametrized groups as listed in the notes) · unmatched: none · marker mismatches: none (445 pass without a marker, 100 `strict=True`, 2 `strict=False` LA-05 / GI-05). Every reason names the card's BUG IDs, and every BUG ID exists in `bugs.md`. Checked from the collected items' markers (scratch `trace2.py`, `trace3.py`).
`--runxfail`, my own probe (scratch `probe.py`, `cmp.py`): all 100 strict xfails fail inside the card's "Fails today on" Then block, with 0 mismatches, 0 setup errors and the expected message (e.g. `DID NOT RAISE`, `Decimal('2.62') == Decimal('2.63')`, `locks('work_orders')` False). Of the non-strict cards, LA-05 failed on Then 1 and GI-05 passed (F-1).
**Externals:** only `utcnow`, `settings` (PROD), `datetime.date` (BD) and CT-22's `get_approvers`, all as the cards prescribe. No session or DAO mock.
**BUG-664 guard:** holds. Every bucket is seeded by `mk_S` / `mk_SD` / `mk_MS` with one ledger row at T0, and no Given calls a posting method. Consumed, started and adjusted states are written as rows. CAP-03 is the only When that posts twice to one bucket, and each of its postings reads one unique newest row.
**Coverage gaps in the notes:** checked by reading. All 5 are unreachable or dead as claimed.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_work_order_manager.py -q -p no:cacheprovider -o addopts="" --cov=app.managers.work_order_manager --cov-branch --cov-report=term-missing
  → 445 passed, 102 xfailed in 110.12s; 788 stmts 1 miss, 346 branches 5 partial, 99% (153->155, 974->exit, 1399->1401, 1456->1458, 1468)
PYTHONPATH=<scratch> … -o addopts="" --runxfail -rf -p probe
  → 101 failed, 446 passed in 69.20s (GI-05 passed)
… -o addopts=""   (run 2) → 445 passed, 101 xfailed, 1 xpassed in 97.94s
… -o addopts=""   (run 3) → 445 passed, 100 xfailed, 2 xpassed in 84.61s
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/work_order_manager.py tests/unit/managers/test_work_order_manager.py --lines <8 shards 1-232 … 1419-1823> --timeout 400 --json <scratch>\mut_<n>.json
  → shard totals 123/123/124/124/124/122/124/125 mutants; killed 904, survived 85, timeout 0
PYTHONPATH=<scratch>\hv WOV=<variant>.json … -p wovar -m "not xfail" | --runxfail   (56 variants, logs in hv\)
```
COVERAGE_FILE was private for every run (`…\ordersv\wo\.coverage*`). Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\ordersv\wo\`.

## Round 2 — 2026-11-21

> **Verdict:** PASS (with the component survivors deferred, as the owner rule says: "revisit after launch")
> Tests: 470 passed · 101 xfailed (all strict) in 3 of 3 runs, with no XPASS · cases Revision 5, 571 cards · `--runxfail`: 101 failed, each on its card's "Fails today on" Then line (0 mismatches)
> Targeted mutation: the 67 non-equivalent survivors of Round 1 → 54 killed, 2 reclassified equivalent, 10 deferred (component, revisit after launch), 1 open (low) → score 99% (958 / 969 non-excluded mutants of the full Round 1 run)

**Scope.** I read the new and changed cards against their tests:
- RIC-01, ADJ-07, ADJ-11, ADJ-16 … ADJ-22;
- AIC-05/06/08/10/11, AIC-12 … AIC-15;
- SMS-01, CT-24, U-77 … U-80, L-06, LA-05, ST-18, RMA-09, ST-22;
- CAP-02/15/16, FC-24, V-18, UI-24, RI-11, SH-09;
- the new `Recorder.locks_first`, `_covers` and `_names`.

All of them are faithful, and all 9 lock cards now call `locks_first("work_orders")`. Traceability is clean: 571 cards, 571 tests, no unmatched IDs, markers match, and no non-strict xfail is left. F-1 is closed: GI-05 is retired and LA-05 is a strict statement check.

**Hand variants re-run against the new file.**

| Variant | Round 1 | Round 2 |
|---|---|---|
| F18 (`FOR UPDATE OF work_order_items` on a join) | passed ST-18 | ST-18 stays red ✅ (F-2) |
| F20 (lock taken after the state check) | passed ST-18 | ST-18 stays red ✅ (F-2) |
| F13 (correct lock) | turned ST-18 green | still turns only ST-18 green, no pass card red ✅ |
| F14 (`SKIP LOCKED`) | stayed red | stays red ✅ |
| B01, B34 (damaged stock goes to the line's source / the machine's factory) | survived | killed by AIC-12 ✅ (F-3) |
| B22 (decrease total computed from the prior total) | survived | killed by ADJ-16 ✅ (F-4) |
| B10, B11, B12, B13, B15, B29, B30 (wrong performer) | survived | killed by ST-22, CAP-16, FC-24, V-18, RIC-01 ✅ (F-5) |

**Targeted mutants.** I ran `mutate.py --lines L-L` on each of the 44 lines that had a non-equivalent survivor. It made 98 mutants: 84 killed and 14 survived. Of the 67 Round 1 survivors:
- **Killed (54).** These cover the logged labels and keys (75/79/81), the template slot (370), the list and sheet defaults (527, 1722, 1756), and every adjust money path (828 … 879). They also cover the completion texts, sources and fallback costs (922 … 981), the complete-as-planned started text (1187/1201), and removing a line from a started order (1488).
- **Reclassified equivalent (2), my Round 1 error.** 393:52 and 1412:52 mutate `exclude_unset`, not `exclude_none`. Every field of `WorkOrderUpdate` / `WorkOrderItemUpdate` defaults to `None`, so `exclude_none=True` drops the same keys either way. The `exclude_none` mutants (col 71) are killed by U-77 and UI-24.
- **Deferred, revisit after launch (10).** These are component paths, which are outside the launch scope:
  - 402:24 and 404:24, the machine/component exclusivity when a component is cleared or replaced;
  - 777 ×3 and 778 ×4, the component activity text and metadata in `_consume_item`;
  - 1283, the metadata of the component completion entry.
- **Open, low (1).** 505:11 `and` → `or`. It is observable only on an update that changes nothing, does not send `assigned_to`, and has assignee rows out of step with the stored text: today the rows stay, and the mutant re-matches them. U-78 has a real change, so it cannot tell. A card for this would pass today and stay valid once BUG-2915 is fixed. **Fix by:** case designer, optional.

**Commands.**
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_work_order_manager.py -q -p no:cacheprovider -o addopts=""   ×3
  → 470 passed, 101 xfailed in 55.71s / 54.69s / 54.07s
… --runxfail -p probe → 101 failed, 470 passed (cmp: 0 mismatches)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/work_order_manager.py tests/unit/managers/test_work_order_manager.py --lines L-L --timeout 400 --json <scratch>\r2\L<L>.json   (44 lines)
PYTHONPATH=<scratch>\hv WOV=<variant>.json … -p wovar   (14 variants; logs in hv\, Round 1 logs moved to hv\r1\)
```
