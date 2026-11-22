# Verification — `app/managers/work_order_template_manager.py`

> **Verdict:** PASS — round 3, 2026-11-09 (cases revision 5): GD-44 now catches the unscoped section run. Round 2: NEEDS WORK (GD-44 gap). Round 1: NEEDS WORK (cases only — the tests are faithful)
> Tests: 209 passed · 130 xfailed (reproduced ✅) · coverage 99% branch (156 stmts / 56 branches; line 261 missed, confirmed unreachable)
> Mutation: 126 mutants · 119 killed · 7 survived → score 100% (119/119, after excluding 3 equivalent, 0 dead, 4 bug-path)
> Hand variants: 43 (26 against the passing suite, 17 intended-fix variants under `--runxfail`) · 7 not caught: 2 equivalent, 1 bug-path, 4 case-missing
> Source commit: e48a092 · Cases revision: 3 (tests and notes at revision 3, 339 cases)

## Summary
These tests can be trusted for what they check. Traceability is clean: 339 cases map to 339 tests, every marker matches its card, and every xfail is strict. Every xfail fails on the Then line its card names. Three runs gave the same result. No test is weakened, swallows a failure or mocks too much. Every numbered Then line has its `# Then N` block. All mutate.py survivors are equivalent or on a bug path, and the scheduling, scoping and approval variants are all caught (month end, leap day, year end, end date inclusive, off-by-one advance, late run, flushes, every lookup made unscoped).

The gaps are in the cases. Four hand-written wrong fixes pass every card:
- a BUG-2345 due check one day off in a section run;
- a section run that ignores the workspace;
- BUG-2350 bounds one digit or one decimal off on the two **update** schemas (`TU.cost`, `IU.quantity`);
- reference checks run in the wrong order (`create_template` R10 is only partly covered).

All four go to the case designer. CT-26/CT-27 were turned into BUG-2350 refusals (revision 3, plus CT-55) while this run was going; the executor already ran revision 3 and it reproduces here, so there is no finding on them.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing (boundary) | `generate_drafts` R4 [BUG-2345]; Q19-01…06 | The section-run due check is tested only six days before the due date (Q19-01/02) and on the day (Q19-06). Nothing tests a recurring template of the section that is due **tomorrow**. An off-by-one fix passes every card. | Variant B02: (b) keeps a recurring template when `next_generation_date <= target_date + 1`. Under `--runxfail` it fixes the same 4 cards as the correct fix (Q19-01…04) and breaks nothing. Proposed card: weekly template of S1 with `next_generation_date D(17)`, section run on D(16) → `pairs(result) == []`, drafts(T) `== []`, T unchanged (xfail BUG-2345). | case designer |
| 2 | case-missing (isolation) | `generate_drafts` R1 / R13; GD-44 | GD-44 runs W1 with W2's section S9, but its Given has only W1 templates. A section run that loads the (b) candidates without the workspace filter passes every card. A W2 template of S9 would then be planned inside W1's run. | Variant A17: `all_active = session.query(WorkOrderTemplate).filter(is_active == True).all()` → 209 passed. Proposed: add Z9 = W2 template, `default_factory_section_id S9.id` (non-recurring) to GD-44's Given, with Then `pairs(result) == []`, unchanged(Z9), drafts(Z9) `== []`. The same row also guards the BUG-2342 SQL rewrite. | case designer |
| 3 | case-missing (money boundary) | `update_template` R5a, `update_item` R3a [BUG-2350]; UT-72/73/74/76, UI-19/20/21/23 | On update, only refusals (3 decimals, 14 integer digits) and `0` are tested. No card stores the largest value `9999999999999.99` or the smallest step `0.01` through `TU` / `IU`, so a bound that is too tight passes. Create is covered (CT-41/48, AI-24/27). | Variants B12 (`TU.cost` max_digits 14), B13 (`IU.quantity` max_digits 14), B14 (`IU.quantity` 1 decimal), B15 (`TU.cost` 1 decimal): under `--runxfail` each gives exactly the outcome of the correct fix B08 (the 19 BUG-2350 cards fixed, 0 broken). Proposed pass cards: UT cost `9999999999999.99` and `0.01` stored exactly; UI quantity `9999999999999.99` and `0.01` stored exactly. They hold today and after the fix. | case designer |
| 4 | case-missing (refusal order) | `create_template` R10; CT-50…54, CT-52, Q21-08 | R10 fixes the order type → account → section → machine → lines (each `item_id`, then `replaced_item_id`, then its line rules) → approvers → R6. The cards pin type<account (CT-52), account<machine (CT-50), section<machine (CT-51), line item<approver (CT-53), first line's rule<second line's item (CT-54), and approver<R6 (Q21-08). Five pairs are not pinned: account vs section; machine vs the line checks; a line's `item_id` vs its `replaced_item_id`; a line's item vs its own line rule (e.g. `REPLACE` with an `item_id` of W2). A fix that runs the lines before the links, or the section before the account, passes every card. | Read: no card sends two failing checks for any of these pairs. Proposed: one xfail card per missing adjacent pair, built like CT-50 (two bad values, exact detail of the first, `not db.new`, nothing written). | case designer |
| 5 | notes (minor) | `work_order_template_manager.notes.md` "Verification done" | The header says revision 3 (209 / 130). The body still reports the revision-2 runs (210 passed / 128 xfailed, "336 of 338 pass" under the reference plugin, CT-26/27 failing). | Notes lines 37 and 54. Nothing is wrong with the tests. | executor |

Fidelity was read in full for every `generate_drafts_for_anchored_range`, `generate_drafts`, Q19, Q20 and Q21 test, and for CT-01…06, CT-36…41/47/48, AI-18…27 and the loose-assertion hits (`in`, `>=`, `len(`, `is not None`, set compares). The rest was checked mechanically: each card's highest Then number against the test's `# Then N` markers (no gap), and markers and reasons against the cards. Every loose assertion found is exactly what its card writes (CT-25 `len`, UT-01 `updated_at is not None`, LT-05/07 membership, GA-01/05 sets, AR-22/GD-42 `len(locks) >= 1`). Only GD-43 and AR-25 patch anything, as their `Author: claude` cards allow. No `try/except` and no `pytest.raises(Exception)`.

## Surviving mutants (mutate.py)
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | 42 | `not member or member.status != 'active'` → `and` | bug-path | The line is BUG-2335's silent skip (`_replace_approvers` R3). The mutant accepts suspended members and raises AttributeError for non-members. Only strict-xfail cards (RA-06…12, CT-34, UT-65/78, Q21-08) send such ids. | — |
| 2 | 250 | `limit=1000` → `1001` | bug-path | The cap is BUG-2342 (`generate_drafts` R3). GD-40 (1000 rows) passes either way, and GD-41 (1001) is xfail BUG-2342. | — |
| 3 | 92 | `exclude_unset=True` → `False` | equivalent | Every `WorkOrderTemplateUpdate` field defaults to `None`, so `exclude_none=True` drops every unset field anyway. | — |
| 4 | 92 | `exclude_none=True` → `False` | bug-path | Only explicit `null` values change, which is BUG-2339 (`update_template` R5). Only the xfail BUG-2339 cards send them. `approver_user_ids` is excluded separately. | — |
| 5 | 92 | exclude `'approver_user_ids'` → `''` | equivalent | `BaseDAO.update` sets only attributes the model has (`hasattr`), and `WorkOrderTemplate` has no `approver_user_ids` attribute. | — |
| 6 | 154 | `exclude_unset=True` → `False` (`update_item`) | equivalent | Every `WorkOrderTemplateItemUpdate` field defaults to `None`, and `exclude_none` drops them. | — |
| 7 | 154 | `exclude_none=True` → `False` (`update_item`) | bug-path | Explicit `null` on a line is BUG-2339 (`update_item` R3). Only xfail cards send it. | — |

## Hand variants (verifier's own, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tplv\wotmgr\var\`)
In-memory plugin `variant_v.py`: string edits on a copy of the source, exec'd, methods rebound. Nothing in `app/` was touched.

**Against the passing suite (`-m "not xfail" -x`): 23 of 26 killed.**
| Variant | Caught by |
|---|---|
| A01 Plan-day advance from the day after the run (off by one) | GD-10 |
| A02 advance from the old `next_generation_date` (not the run's day) | Q20-01 |
| A03 anchored advance off by one day | AR-01 |
| A04 draft dated at the old next date | GD-34 |
| A05 BUG-2346 check on every update (too strict for old templates) | Q21-07 |
| A06 BUG-2346 counting only stored approvers still active | Q21-10 |
| A07 unscoped lookup in `get_template` / `update_template` / `delete_template` / `restore_template` / `add_item` / `update_item` / `remove_item` | GT-04 / UT-03 / DT-03 / RT-03 / AI-04 / UI-03 / RI-03 |
| A08 unscoped `get_items` / `get_approvers` | GI-03 / GA-03 |
| A10 no `updated_by` stamp | UT-01 |
| A11 no `created_by` | CT-01 |
| A12 old approvers not deleted | RA-01 |
| A13 no flush after the Plan-day advance | GD-01 |
| A14 no final flush in the anchored range | AR-01 |
| A15 approvers replaced only on a non-empty list | UT-63 |
| A16 section run includes inactive templates | GD-37 |
| A18 end-date skip removed | GD-39 |

Not caught:
- **A17**, section candidates across workspaces: case-missing, finding 2.
- **A09**, approver membership looked up in any workspace: bug-path. Today the line is BUG-2335's skip, and RA-10/11 (managers of W0/W2, strict xfail) refuse them once it is fixed.
- **A19**, de-dupe `continue` removed: equivalent. It confirms the executor's claim that line 261 is unreachable: `list_recurring_due` joins `FactorySection` many-to-one (one row per template), `section_templates` already leaves out every recurring id, and `get_by_workspace` has no join.

**Intended fixes under `--runxfail`, compared with the unmutated baseline (130 failing):**
| Variant | xfail cards now passing | Newly failing | Reading |
|---|---|---|---|
| B01 BUG-2345 correct (`not t.is_recurring` in (b)) | Q19-01…04 | 0 | cards honest |
| B02 BUG-2345, due one day early | Q19-01…04 | 0 | **not caught**, finding 1 |
| B03 BUG-2345, due check ignores the end date | Q19-01…04 | 0 | equivalent: the R5 guard (line 266) skips ended programs |
| B04 BUG-2346 correct (create and update, before writing, only when a field is sent) | Q21-01, 02, 04, 05, 12 | 0 | cards honest |
| B05 BUG-2346 update check after the write | Q21-01, 02 only | 0 | caught (Q21-04, 05, 12 stay red) |
| B06 BUG-2346 create check after the write | Q21-04, 05, 12 only | 0 | caught (Q21-01, 02 stay red) |
| B07 BUG-2346 update checks only `requires_approval` | Q21-01, 02, 05 only | 0 | caught (Q21-04, 12) |
| B08 BUG-2350 correct (`condecimal(15, 2)` on all four schemas) | the 19 BUG-2350 cards | 0 | cards honest |
| B09 BUG-2350, 14 integer digits allowed | 15 | 0 | caught (CT-47, AI-26, UI-23, UT-76) |
| B10 BUG-2350, 3 decimals allowed | 4 | 0 | caught |
| B11 BUG-2350, 12 integer digits (too tight) | 19 | CT-41, AI-24 | caught |
| B16 create cost, 14 integer digits | 18 | 0 | caught (CT-47) |
| B17 create line quantity, too tight | 19 | AI-24 | caught |
| B12 / B13 / B14 / B15 update cost or quantity, too tight or 1 decimal | 19 | 0 | **not caught**, finding 3 |

HR-15 (half-even against half-up): with BUG-2350 no valid input reaches the column's rounding, and no pass card sends a three-decimal value (revision 3 closed the last two). Rounding in Python would be invisible today and unreachable once the bug is fixed. By design, no finding. BUG-2347/2348/2349 and subtotals are not in this module.

## Traceability
- 339 cases (209 pass, 130 xfail) · 339 tests (`pytest.param` ids for the 24 parametrized groups) · unmatched: none · duplicates: none.
- Marker mismatches: none. Every xfail is `strict=True` and its reason names the card's bug. Every BUG ID used exists in `docs/testing/bugs.md`.
- `--runxfail`: all 130 fail. Each fails on the card's "Fails today on" Then line (checked by my own plugin `failson_v.py`, which maps the failing line to its `# Then N`). The five `IntegrityError` cards (CT-13, CT-20, UT-38, AI-15, UI-17) fail inside the Then 1 `pytest.raises`, as their cards state. GD-43 fails in its When (`RuntimeError`), as its card states.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_work_order_template_manager.py -q -p no:cacheprovider -o addopts="" --cov=app.managers.work_order_template_manager --cov-branch --cov-report=term-missing
  -> 209 passed, 130 xfailed, 15 warnings in 106.14s · 156 stmts, 1 miss (261), 56 branches, 1 partial · 99%
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_work_order_template_manager.py -q -p no:cacheprovider -o addopts="" --runxfail -rf -p failson_v
  -> 130 failed, 209 passed in 51.98s
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_work_order_template_manager.py -q -p no:cacheprovider -o addopts=""   (x2)
  -> 209 passed, 130 xfailed in 51.99s · 209 passed, 130 xfailed in 51.60s
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/work_order_template_manager.py tests/unit/managers/test_work_order_template_manager.py --lines {1-90|91-170|171-240|241-315} --timeout 400 --json <scratch>
  -> 32·31 killed / 65·60 / 11·11 / 18·17  =  126 mutants, 119 killed, 7 survived
hand variants: var/run_variants.sh A|B <names>   (A: -m "not xfail" -x; B: --runxfail --junitxml, diffed against B00_noop)
```
Every run used a private `COVERAGE_FILE` under `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tplv\wotmgr\`.

## For the future notes
- **Permissions:** no role check on template writes or on `generate_drafts`, and any active member can be picked as a default approver. This is already in `docs/future/permissions.md` (spec "Permission checks").
- **Notifications:** `created_from_template` events from both generators are the hook for a "drafts planned" notice. After BUG-2344, the per-template WARNING is the hook for "a template could not be planned". After FU-1 (a), an approver who is no longer active being dropped from a generated order is a candidate alert.

## Round 2 — 2026-11-09

> **Current verdict:** NEEDS WORK — round-1 findings 1, 3, 4 (cases) and 5 (executor) are closed; finding 2 (GD-44) is not: its new Z9 cannot show the unscoped section run. Fix by the case designer.
> Tests: 213 passed · 136 xfailed (reproduced ✅, 3 identical runs) · coverage 99% branch (line 261, unreachable as in round 1)
> Mutation: not re-run (no source change; the round-1 score of 100% stands) · Cases revision: 4 (349 cases)

### New and changed tests read against their cards
Q19-07, GD-44 (Then 4–5, Z9), UT-79/80, UI-25/26 and CT-56 … CT-60 are faithful.
- Every Given is built as written (Z9 through `tpl_w2`: W2, WT9, S9, non-recurring).
- Every Then is asserted in card order with exact values and re-read from the database. No extra mocks.
- The xfail markers are strict, and their reasons name BUG-2345 / BUG-1015.
- Traceability: 349 card IDs and 349 tests, none missing or duplicated.
- Under `--runxfail` all 136 xfails fail on their card's "Fails today on" line: Q19-07 on Then 2, and CT-56 … 60 on Then 1 (`DID NOT RAISE`). GD-43 fails in its When, as its card says (same as round 1).

### Round-1 survivors re-run
| Round-1 item | Variant | Now | Caught by |
|---|---|---|---|
| F1 BUG-2345 fix one day early | B02 (`--runxfail`, Q19 cards) | caught | Q19-07 (B01, the correct fix, passes all 7 Q19 cards) |
| F2 section run loads every workspace's templates | A17 (passing suite) | **not caught**: 213 passed | — |
| F3 update `cost` too tight (12 integer digits / 1 decimal) | B12, B15 | caught | UT-79; UT-79 + UT-80 |
| F3 update line `quantity` too tight | B13, B14 | caught | UI-25; UI-25 + UI-26 |
| F4 section checked before account | R01 | caught | CT-56 |
| F4 line item checked before machine | R02 | caught | CT-57 |
| F4 line rule checked before machine | R03 | caught | CT-58 (and CT-60) |
| F4 replaced item checked before line item | R04 | caught | CT-59 |
| F4 line rule checked before line item | R05 | caught | CT-60 |
| F5 notes still at revision 2 | — | closed | the notes' "Verification done" shows revision 4 |

I wrote the R variants myself.
- R00 is a reference BUG-1015 check block in `create_template`, in the R10 order. With it, CT-56 … 60 all pass.
- R01 … R05 each swap one pair of checks.
- B08 (correct BUG-2350 bounds) passes all 213 passing tests.

### Remaining finding
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| R2-1 | case-missing | WTMG-GD-44 (`generate_drafts` R13, R1) | Z9 has a section but no machine. Under A17 Z9 does become a candidate. But `resolve_template_machine_ids` looks up S9's machines with `workspace_id=W1` and finds none, so nothing is drafted and every Then holds. A section-only W2 template cannot show the leak. | A17: 213 passed. Scratch probe `tplv\wotmgr2\probe\test_probe_a17.py` adds `default_machine_id M9.id` to Z9. It passes on today's code. Under A17 it fails with `HTTPException 404: Work order template with ID … not found` from `create_work_order_from_template`. | **case designer**: give Z9 `default_machine_id M9.id` in GD-44, or add a card with it. Then **executor**. |

### Commands run (round 2)
```
pytest tests/unit/managers/test_work_order_template_manager.py -q -p no:cacheprovider -o addopts="" --cov=app.managers.work_order_template_manager --cov-branch --cov-report=term-missing
  -> 213 passed, 136 xfailed in 92.16s · 156 stmts, 1 miss (261), 56 branches, 1 partial · 99%
pytest … -q -p no:cacheprovider -o addopts=""   (x2)  -> 213 passed, 136 xfailed in 44.69s · 213 passed, 136 xfailed in 43.97s
pytest … --runxfail -p failson_v                   -> 136 failed, 213 passed in 35.35s (each on the card's line; GD-43 in its When)
variants (-p variant_v): R00…R05 and B01/B02 with --runxfail -k on the cards; A17, B08, B12…B15 with -m "not xfail"
  R00 5 passed · R01 CT-56 failed · R02 CT-57 · R03 CT-58, CT-60 · R04 CT-59 · R05 CT-60
  B01 7 passed · B02 Q19-07 failed · A17 213 passed · B08 213 passed · B12 UT-79 · B13 UI-25 · B14 UI-25, UI-26 · B15 UT-79, UT-80
probe (A17 with Z9 + M9): today passes; under A17 fails with the 404
```
The private `COVERAGE_FILE`s are under `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tplv\wotmgr2\`. The variant files are in `…\tplv\wotmgr\var\`; `make_r2.py` builds R00 … R05.

## Round 3 — 2026-11-09

> **Current verdict:** PASS — the last open round-1 finding (2, GD-44) is closed. Cases revision 5; nothing left for any stage.

- **GD-44 read against its card (revision 5):** faithful. Given 3 now builds Z9 with `default_machine_id=R.M9.id` (line 4879); Then 1–5 are asserted in card order with exact checks. No other test changed (notes: revision 5 touches only GD-44).
- **Unscoped section run (variant A17):** the `generate_drafts` section run loads active templates from every workspace. It now fails GD-44, at the `generate_drafts` call, line 4881: `HTTPException 404: Work order template with ID … not found` from `create_work_order_from_template` (manager line 104) → 1 failed, 212 passed. The no-op variant B00 gives 213 passed. The executor's own check (a `get_by_workspace` with no workspace filter) agrees.
- **Runs:** 3 plain runs, identical: 213 passed · 136 xfailed · 99% branch (156 stmts / 56 branches; only line 261 missed, still unreachable). Not flaky.
- **Mutation:** not re-run, because the source is unchanged; round 1's 100% (119/119) stands.

```
VARIANT_FILE=…/tplv/wotmgr/var/A17_gd_section_other_workspace.json PYTHONPATH=…/tplv/wotmgr/var COVERAGE_FILE=…/tplv/wotmgr3/.cov_a17 \
  .venv/Scripts/python.exe -m pytest tests/unit/managers/test_work_order_template_manager.py -q -p no:cacheprovider -m "not xfail" -o addopts="" -p variant_v -rf
  FAILED …::test_wtmg_gd_44__foreign_section_selects_nothing · 1 failed, 212 passed, 136 deselected
(B00 no-op, same command)  213 passed, 136 deselected
COVERAGE_FILE=…/tplv/wotmgr3/.cov{1,2,3} .venv/Scripts/python.exe -m pytest tests/unit/managers/test_work_order_template_manager.py -q -p no:cacheprovider -o addopts="" \
  --cov=app.managers.work_order_template_manager --cov-branch --cov-report=term-missing
  run1/2/3: 213 passed, 136 xfailed · work_order_template_manager.py 156 1 56 1 99% 261
```
