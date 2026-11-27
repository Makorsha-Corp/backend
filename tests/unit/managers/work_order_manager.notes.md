# Execution notes — `app/managers/work_order_manager.py`

> Cases: `tests/unit/managers/work_order_manager.cases.md` (revision 5, 2026-11-21) · Tests: `tests/unit/managers/test_work_order_manager.py` · Source commit: e48a092
> Result: 470 passed · 101 xfailed (all strict) · 0 open discrepancies (DISCREPANCY-1, -2 resolved in revision 3) · 0 errors — branch coverage 99.5% (788 statements, 1 missed; 346 branches, 5 partial)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_work_order_manager.py -q -p no:cacheprovider -o addopts=""`

## How the tests are built
- I built this in normal mode, without the local model. Every test sits below a `# [claude] <ID>` comment, in card order. There are 571 case IDs (GI-05 retired in revision 4). Most cards are their own test. A few groups of cards with the same setup and assertions are one parametrized test with one `pytest.param(id="WOM-…")` per card: U-15 … U-21, U-25 … U-27, CI-07/08, ADJ-04 … 06, AIC-02 … 04, EAM-02/03, CAP-06 … 08, CAP-09 … 11, AI-05 … 11 + AI-13 + AI-17, AI-14/15, AI-27 … 30, SE-05/06. A scratch check confirms that each ID appears exactly once and that the Expect markers match the cards: 470 pass, 101 strict.
- **Standing rows** come from the autouse fixture `s` (a SimpleNamespace). It holds TAG, Y and NEW, the workspaces W0 < W1 < W2, U1 … U5 (with names), the six memberships, WT0/1/2/9, F0/1/2/9, M0/1/2/3/9, I0/1/2/3/9, A0/1/9/2, PJ1/PJ9 and PC1/PC9. Each row is flushed in the order the Conventions give. Tests that use neither `db` nor `s` do not take them as arguments, but they still get the rows because the fixture is autouse.
- **Time**: the autouse fixture `_clock` patches `app.managers.work_order_manager.utcnow` to return NOW. Column defaults and the database `now()` keep the real clock, as the Conventions say.
- **Given rows** are built by these helpers:
  - `mk_order(db, s, "N", **but)`, plus the dicts `STAMPED(s)`, `STARTED(s)` (which includes stamped), `COMPLETED(s)`, `VOIDED(s)` and `GONE(s)`. For "this date replaces the one in started", the dicts are merged with `{**STARTED(s), "planned_date": …}`.
  - `mk_line(db, s, O, I, "q", **but)`, plus `CONSUMED(s, "t")` and `LINE_GONE(s)`.
  - `mk_approver` with `APPROVED`, `mk_assignee`, `mk_event`, `mk_status_row`.
  - `mk_S` / `mk_SD` / `mk_MS`. Each writes one bucket row plus one opening ledger row at T0, the same shape as in `inventory_movements`.
  - `mk_template` with `WEEKLY`, `mk_tline`, `mk_tapprover`, `mk_invoice`, `mk_type`.
  - `GONE_FT` (factory, type) and `GONE_MA` (machine, account).
- **BUG-664 guard**: no Given posts stock. Consumed, started and adjusted states are written straight into the rows, as the cards ask. CAP-03 is the only When that posts twice to one bucket.
- **Named checks**:
  - `mark(db)` takes the highest id of the five event and ledger tables.
  - `ev`, `evrow` and `evrows` read the order's events. `acts`, `actrows` and `stat` read machine activities. `led`, `mled`, `qty`, `mqty` and `pcacts` read stock.
  - `reread`, and `snap` for unchanged(X), which reads every mapped column after an expire. `snap` is always taken at the end of the Given.
  - `counts` covers the 13 tables in all workspaces, for "nothing written". "Session clean" is three plain asserts.
- **Requests**: `CR`, `CREATE`, `FROM`, `UP`, `ITEM`, `ADD`, `UIT`, `SHEET`, `ENTRY` and `FIN` follow the Conventions. Each helper imports its schema at call time, so the schemas are imported inside the tests.
- **Statement recorder**: the class `Recorder` adds a `before_cursor_execute` listener on the engine. Since revision 4 it implements the tightened Conventions. `_names(st, t)` tells whether a SELECT names t in its FROM / JOIN part. `_covers(st, t)` checks for `FOR UPDATE` with no `OF`, or an `OF` that lists t, and no `SKIP LOCKED` / `NOWAIT`. `locks_first(t)` requires the first SELECT naming t to carry a covering lock and to come before the first UPDATE / INSERT / DELETE; it is used by AA-11, RMA-09, SA-14, ST-18, CAP-13, V-15, AI-37, UI-22 and RI-09. `locks(t)` means some covering SELECT comes before the first write; it is used only for the line row in UI-22 and RI-09. `order_part(t)` returns the ORDER BY text of the first SELECT naming t (LA-05).
- **Commit spy**: `patch.object(db, "commit", wraps=db.commit)` wraps `begin_nested()` and the call. The "inside" lines run first, then `sp.rollback()`, then the "after" lines.
- **Externals patched**: `utcnow` (always), `settings` through `PROD(b)` for D-04 … D-07, and `datetime.date` through the `_Today9` subclass for BD-03/04. The commit-spy wraps are not mocks. CT-22 patches `work_order_template_manager.get_approvers` exactly as its Given line says.
- Cards whose When raises today fail at the call, directly after `# Then 1`. These are G-04 and GI-03 (`TypeError`, no `include_deleted`) and LE-05 (`IntegrityError` inside `db.begin_nested()`).

## Checks done
- **3 plain runs**: identical, `470 passed, 101 xfailed` each time (revision 5). Logs are in scratch: `run1.log` … `run3.log`.
- **`--runxfail` check**: I ran it with my own probe plugin, scratch `then_probe.py`. It maps the failing line of each test to its `# Then N` block. 101 tests fail (revision 5). All 101 strict xfail cards fail inside their card's "Fails today on" Then block, with 0 mismatches. I also read each failure message against the card: the right field and value fail, for example `DID NOT RAISE` for the Then 1 cards, `Decimal('2.62') == Decimal('2.63')` for ADJ-09, and `locks_first('work_orders')` False for the lock cards. LA-05 fails on Then 2, because the ORDER BY has `assigned_at` only.
- **Reference plugin**: scratch `ref_plugin.py`, built from `make_ref.py`, which writes `ref_wom.py`. It works in-process and never touches `app/`.
  - It rebinds every `WorkOrderManager` method to a copy of the manager with the intended behaviour of all 34 bugs applied (the two discrepancy edits were removed in revision 3). The rebinding keeps the original module globals, so the tests' patches still apply.
  - It also swaps in validated schema subclasses for BUG-2912, 2913, 2918 and 2926.
  - Run with `PYTHONPATH=<scratch> pytest … --runxfail -p ref_plugin`, the result was **571 passed** (revision 5). So every card can be met.
- **Lint**: `ruff check` is clean. The header has `noqa: DTZ001, DTZ005, FURB157`, because the Conventions prescribe naive datetimes, `datetime.now().year` and `Decimal("q")` literals. `ruff --select F,ARG001` is also clean: no unused variables and no unused test arguments.
- The file uses LF line endings.

## Discrepancies
| ID | Case | Designed | Actual | Evidence | Likely cause |
|---|---|---|---|---|---|
| DISCREPANCY-1 (**resolved**, rev 3: spec G16, AIC-10 now expects no activity; new AIC-11 covers the machine source; marker removed) | WOM-AIC-10 | pass | was strict xfail: Then 3 fails, `acts(M1) == []` | The storage stock goes back (Then 1, 2 pass). `post_stock_in` writes a machine activity only for `location_type == "machine"`, and this Borrow line's source is storage, so no `item_borrowed_returned` row is written on M1, or anywhere. | Spec `_apply_item_completion` R8 says "per `post_stock_in` … activity `item_borrowed_returned`", but `post_stock_in` logs no activity for a storage source. The describer should decide whether a storage-source Borrow return should log on the order's machine (the reference plugin does that), or whether the card should expect no activity. |
| DISCREPANCY-2 (**resolved**, rev 3: spec G17, AI-01 now expects `Added 2 Bolt`; marker removed) | WOM-AI-01 | pass | was strict xfail: Then 4 fails, `("item_added", "Added 2 Bolt")` | `add_item` renders `item.quantity` from the object built from the request (`Decimal("2")`). Nothing refreshes it after the flush. | Spec `add_item` R9 says "quantity as stored, e.g. `2.00`", but the code prints the request's Decimal: `Decimal("2")` gives `2`, and `Decimal("2.00")` gives `2.00`. The fix is either the spec text (as sent) or the code (quantize or refresh). This is for the describer and the owner. |

No new bugs. BUG-2942 … 2951 were not used.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 153->155 | unreachable | `if variance:` is False only when `_variance_vs_planned` returns None. That needs a missing planned date or actual time, and both are already present inside `if wo.planned_date`. |
| 974->exit | unreachable | An action type other than CONSUME/INSTALL/REPLACE/BORROW. The `Literal` in the schema refuses it (422), so it is reachable only through invalid stored rows. |
| 1399->1401 | unreachable | In `add_item`, a status that is neither DRAFT nor IN_PROGRESS. `_guard_item_mutations` has already refused COMPLETED and VOIDED. |
| 1456->1458 | unreachable | The same branch in `update_item`. |
| 1468 | unreachable | The COMPLETED/VOIDED refusal in `remove_item` repeats `_guard_item_mutations`, which always raises first. It is dead duplicate code. |

## Factories added
None. All builders are local to the test file. `make_profile` and `make_workspace` come from `tests/unit/factories.py`.

## Notes for maintainers
- When a bug is fixed, its strict xfails will XPASS. Remove those markers:
  - BUG-381: RCW-06
  - BUG-665: CI-12, CI-13
  - BUG-1000: SMS-06
  - BUG-1016: C-27, C-28, C-29, U-59, U-60, U-61, AI-36
  - BUG-1040: ADJ-09, ADJ-15
  - BUG-1192: LE-03, LE-04, LE-05
  - BUG-1200: LA-05
  - BUG-1204: RMA-06
  - BUG-1206: CT-22, ASL-05, SE-14
  - BUG-1228: C-18, U-28, SE-09
  - BUG-1272: GI-04
  - BUG-1273: GI-03
  - BUG-1279: G-03, G-04, ST-17
  - BUG-1884: CI-16, ST-19, FC-19
  - BUG-2670: L-03
  - BUG-2912: C-34, U-30, U-31, AI-19, AI-20, UI-11, SE-17, SE-18
  - BUG-2913: C-36, C-37, U-32, AI-21, UI-12
  - BUG-2914: AI-23, AI-33, UI-14, UI-15
  - BUG-2915: U-39, U-74, UI-20
  - BUG-2916: AA-11, RMA-09, SA-14, ST-18, CAP-13, V-15, AI-37, UI-22, RI-09
  - BUG-2917: SA-12, SA-13
  - BUG-2918: V-12, V-13
  - BUG-2919: U-68, U-69, U-70
  - BUG-2920: C-13, C-21, C-30, CT-11, U-29, SE-07
  - BUG-2921: C-22, U-57
  - BUG-2922: CT-18
  - BUG-2924: U-13
  - BUG-2925: BD-03
  - BUG-2926: C-31, U-34, U-35
  - BUG-2927: AI-27, AI-28, AI-29, AI-30, UI-10
  - BUG-2928: SE-12
  - BUG-2929: U-42, U-43, U-44
  - BUG-2930: U-51, U-52, U-53
  - BUG-2931: U-22, U-23, AA-05, RMA-04, SA-09, SA-10
- No non-strict xfail is left: GI-05 was retired, and LA-05 is now a statement check.
- Fix hints found while building the reference plugin:
  - The BUG-2916 locks must select a column (`query(WorkOrder.id)…with_for_update()`). Selecting the entity fails, because joined eager loads put the row on the nullable side of an outer join, and Postgres refuses `FOR UPDATE` there.
  - The BUG-2915 no-op check must come after the in-progress lock check, because U-15 wants the current description refused while the order is in progress. It must also keep the assignee re-sync, for U-71.
  - The BUG-1204 fix (set `required_approvals = 1` when the last approver is removed) must leave AS-05 alone: an order that never had approvers stays 0 of 0, met.
- The PO fork works on `purchase_order_manager` in the same folder. I touched none of its files.

## Revision history
- **Revision 3 (2026-11-21)**: cases rev 3 (spec G16, G17).
  - AIC-10 rewritten: Borrow from storage, Then 3 is now "no machine activity" (`_new_count(MachineActivityEvent) == 0`). The DISCREPANCY-1 marker is removed.
  - AIC-11 added: Borrow from a machine source (MS(M2, I1, 3, 4.00)), with the activity on M2 and none on M1.
  - AI-01 now expects `Added 2 Bolt`. The DISCREPANCY-2 marker is removed.
  - V-17 added: voiding a started order skips a live, never-consumed line. This covers branch 1318->1317 and closes that coverage gap.
  - Reference plugin: the two discrepancy edits were removed from `make_ref.py`.
  - No other test changed. Result: 445 passed, 102 xfailed; `--runxfail` 0 mismatches; reference plugin 547 passed.
- **Revision 5 (2026-11-21)**: cases rev 4 and 5 (verifier findings; spec G18, G19).
  - Retired: GI-05, test removed.
  - LA-05 rewritten as a strict statement check: the ORDER BY of the approver query must contain `work_order_approvers.id`.
  - The `Recorder` now implements "locks first `work_orders`" and the "lock clause covers t" rule. All nine lock cards now call `locks_first`.
  - Changed cards, with extra or pinned Then lines:
    - ADJ-07, RIC-01, AIC-05: ledger source and performer.
    - ADJ-11, AIC-10, AIC-11: full notes.
    - AIC-06, AIC-08: Replace activity texts and notes.
    - CAP-02: Then 5, the started text.
    - SMS-01: Then 5, the status row's performer.
  - New pass cards:
    - ADJ-16 … ADJ-22
    - U-77 … U-80
    - UI-24, RI-11, CT-24, CAP-15, L-06, SH-09
    - AIC-12 … AIC-15
    - ST-22, CAP-16, FC-24, V-18
  - BUG-664 guard: every new card seeds stock with S / SD / MS only, and builds the uncosted and re-averaged lines directly as rows.
  - Reference plugin: `list_approvers` now uses its own query, ordered by `assigned_at, id`.
  - Result: 470 passed, 101 xfailed; `--runxfail` 101 failed, 0 mismatches; reference plugin 571 passed; 3 identical runs; ruff clean; LF line endings.
  - Coverage: 99.5% (788 statements, 1 missed; 346 branches, 5 partial; the gaps are the unreachable ones listed above).
  - No discrepancies and no new bugs.
