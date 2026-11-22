# Verification — `app/managers/transfer_order_manager.py`

> **Verdict:** PASS
> Tests: 281 passed · 82 xfailed (reproduced ✅) · coverage 98% branch
> Mutation: 367 mutants · 347 killed · 20 survived → score 100% (after excluding 3 equivalent, 5 dead, 12 bug-path)
> Source commit: e48a092 · Cases revision: 2b

## Summary
These tests can be trusted. All 363 cards map one-to-one to tests, and every marker matches its card's Expect line. Every strict xfail fails on the Then block its card names. Three plain runs gave identical results. Every mutant that `mutate.py` left alive is equivalent, dead or on a bug path.

I also tried 101 hand variants:
- the workspace filter dropped in every lookup;
- OQ-55 wipes;
- approval edge cases;
- each lock style;
- completion order;
- a commit inside each method;
- a missing event, or a wrong `performed_by`, on each event;
- delete cascades.

All were caught except the ones listed under "Hand variants", which are equivalent or on a bug path. Two invalid-data corners are not covered by the spec, and the describer can close them optionally (Findings 3–4). The only test-side items are cosmetic revision labels (Findings 1–2). No new bug was found.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | cosmetic | TOM-D-02, test line 2380 | The name, docstring title and Rules still use the rev-2a wording. The test says "goes with the database cascade" and "R4". The card says "is removed with the order" and "R4 [BUG-2890] (HR-16)". The body and the `xfail("BUG-2890")` marker match 2b. | `test_tom_d_02__foreign_line_goes_with_cascade` | executor (non-blocking) |
| 2 | cosmetic | test module docstring (line 8); notes header | Both say "revision 2a"; the cases file is revision 2b. | — | executor (non-blocking) |
| 3 | spec-gap (invalid data) | `add_item` R4, line 514 | The next line number counts only lines in the workspace. Nothing pins this for a line from another workspace stored on the order (invalid under HR-16). If the filter is dropped, every test still passes. | hand variant `ws-ai-existing` SURVIVED | describer (fill-gaps, optional; low priority) |
| 4 | spec-gap (invalid data) | `add_approver` R3, line 645 | The duplicate check is scoped to the workspace. Nothing pins this for an approver row from another workspace for the same user on the order. Today that row gives an `IntegrityError` from `uq_to_approver_to_user`; without the filter it gives a 409. | hand variant `ws-aa-existing` SURVIVED | describer (fill-gaps, optional; low priority) |

There are no fidelity findings. All 363 cards were read against their tests, with nothing missing, weakened or changed: no bad setup, no in-memory-only checks, no swallowed failures, no extra mocks, and no dishonest xfails. D-09 and MC-19 read `S.W1.id` and `S.U2.id` after `expunge_all()` rather than copying them to locals first. This is harmless: the ids are already loaded, so no SQL is sent.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 61 | 352 | return None | dead | `list_transfer_orders` has no caller (spec Q3, dead-code list) | — |
| 156 | 350 | skip 0 → 1 | dead | same dead method | — |
| 157 | 350 | limit 100 → 101 | dead | same dead method | — |
| 80 | 556 | negate if | bug-path | the `approved` stamping block goes away with BUG-2896 (UI-19); no pass card by design | — |
| 243 | 556 | drop `not` | bug-path | same block (BUG-2896) | — |
| 281 | 556 | `'approved'` → `''` | bug-path | same block (BUG-2896) | — |
| 282 | 556 | `'approved'` → `''` | bug-path | same block (BUG-2896) | — |
| 283 | 558 | `'approved_by'` → `''` | bug-path | same block (BUG-2896) | — |
| 284 | 559 | `'approved_at'` → `''` | bug-path | same block (BUG-2896) | — |
| 248 | 624 | `> 0` → `>= 0` | equivalent | with 0 approvers, `len(approvers)` is 0, the same `required` as the `else` branch | — |
| 269 | 326 | `exclude_unset` True → False | equivalent | every `TransferOrderUpdate` field defaults to None and `exclude_none=True` drops them, so the dict is identical | — |
| 278 | 544 | `exclude_unset` True → False | equivalent | same for `TransferOrderItemUpdate` (all defaults None) | — |
| 270 | 326 | `exclude_none` True → False | bug-path | keeping sent nulls is the BUG-2895 fix (U-07 … U-12, U-25 xfail) | — |
| 279 | 544 | `exclude_none` True → False | bug-path | BUG-2895 for lines (UI-16 … UI-18 xfail) | — |
| 291 | 627 | `required = 0` → 1 | bug-path | 0 approvers needing 1 is the BUG-1203 fix (AS-08, MC-15 xfail) | — |
| 294 | 663 | `'User #'` → `''` | dead | profile fallback is unreachable (spec `add_approver` R4a, G4) | — |
| 297 | 682 | `'User #'` → `''` | dead | same fallback in `remove_approver`: the approver's NOT NULL FK to `profiles` guarantees a profile (G4) | — |
| 360 | 573 | `'transfer_cleared'` → `''` | bug-path | reachable only after BUG-2895 (UI-16 xfail) | — |
| 366 | 574 | `'Item #'` → `''` | bug-path | same (BUG-2895) | — |
| 367 | 574 | `' transfer cleared'` → `''` | bug-path | same (BUG-2895) | — |

## Hand variants
101 variants were run on a private copy of the backend (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tov\variants.py`). Kill mode runs the pass tests with `-m "not xfail" -x`. Runxfail mode runs the named cards with `--runxfail`, to prove that a correct fix passes and a wrong fix fails.

**Workspace — killed (22 of 25)**
- Each filter, when dropped, is caught by the named test:
  - the order lookup in update, get and delete (U-04, G-01, D-04);
  - `_order_items` (OI-02), `_has_any_approval` (HAA-04);
  - the factory, machine and component labels (FLI-15, FLI-17, FLI-19);
  - ECI lines (ECI-05), the update_item and remove_item lookups (UI-04, RI-03), `get_items` (GI-01);
  - `list_approvers` rows and membership (LA-04, LA-03), `approval_summary` (AS-06), add_approver membership (AA-05);
  - remove_approver and set_approval lookups (RA-04, SA-04), `list_events` (LEV-02);
  - the hub workspace (HUB-01).
- **Survived:**
  - `ws-delete-lines`: equivalent, because dropping the filter is the BUG-2890 fix, and D-02 passes with it.
  - `ws-ai-existing` and `ws-aa-existing`: Findings 3–4.

**HR-16 route check**
- Implemented with the workspace check: all 12 of C-13 … C-20 and U-34 … U-37 pass.
- Implemented as an existence check only (no workspace): C-13, C-14, C-17, C-18, U-34 and U-35 still fail, so foreign factories and machines are caught both ways.

**OQ-55**
- Real-change wipe in R6c order: U-23, U-24 and U-26 pass. U-25 still fails, as it should, because it also needs BUG-2895. The pass cards U-22, U-27, U-28, U-29, U-31 and U-45 stay green.
- These broken wipes are killed:
  - wiping on the same value, killed by U-29;
  - wiping on any update, killed by U-29.
- A wipe written before the `updated` event survives the pass run (bug-path), but U-23, U-24 and U-26 fail on it under `--runxfail`.

**Approvals**
- These variants are killed:

  | Variant | Killed by |
  |---|---|
  | 0 required treated as None | U-45 |
  | 0 required treated as "not met" | U-45 |
  | `approvals_met` rewritten | AM-02 |
  | readiness check skipped | SA-07 |
  | stamp kept on withdraw | SA-02 |
  | flag kept on withdraw | SA-02 |

- `-1` treated as None survives. This is bug-path: BUG-2901 refuses `-1` in the schema, so it can never be stored.
- The double-approve fix (no-op when the state is unchanged) passes SA-11 and SA-13.

**Locks (lock cards U-44, D-09, MC-19, AI-12, UI-23, RI-08, AA-11, RA-08, SA-16)**
- Correct `FOR UPDATE` at the public methods: all 9 pass. Putting the lock inside `get_transfer_order` is rejected by G-05 (a plain read must not lock).
- All 9 fail for each wrong lock:
  - `SKIP LOCKED`;
  - `NOWAIT`;
  - `FOR SHARE`;
  - `FOR NO KEY UPDATE`.
- MC-19 also fails when the lock comes after the first write, or is taken on the items table.

**Completion**
- The same-route check (R4a) placed before writes passes MC-16. Placed after the line stamps, it fails MC-16.
- The duplicate check moved before any write (BUG-2889) passes C-11.
- These broken versions are killed:

  | Variant | Killed by |
  |---|---|
  | duplicate check moved after the lines | C-10 |
  | duplicate check dropped | C-10 |
  | unmet approvals allowed | MC-11 |
  | recorded stamp overwritten | MC-04 |

- Posting before the line stamps survives, and is equivalent: the poster is mocked, the real `post_transfer_order_inventory` never reads `transferred_at`, and on error the caller rolls back.

**Commit inside**
- All 11 are killed, each by its own commit-spy card: C-33, U-43, D-10, MC-20, AI-13, UI-24, RI-07, AA-10, RA-07, SA-17, plus `log_event` (caught by C-33).

**Events**
- A missing event is killed in all 11 places:

  | Missing event | Killed by |
  |---|---|
  | created | C-04 |
  | updated | U-01 |
  | MC transfer_recorded, inventory_posted, order_completed | MC-02 |
  | item_added | AI-03 |
  | update_item transfer_recorded | UI-11 |
  | item_removed | RI-01 |
  | approver_added | AA-01 |
  | approver_removed | RA-01 |
  | approved / approval_withdrawn | SA-01 |

- A wrong `performed_by` or stamp is killed in all 16 places, including `log_event` dropping `performed_by` (LFC-02), `completed_by` and `updated_by` (MC-01, U-01), `assigned_by` (AA-01), and the creator's approver row being dropped (C-03).

**Delete**
- These variants are killed:

  | Variant | Killed by |
  |---|---|
  | no explicit line delete | D-01 |
  | deleting every line of the workspace | D-01 |
  | also deleting other orders | D-01 |
  | soft delete | D-01 |
  | completed order deletable | D-06 |

- Explicitly deleting approvers of any workspace survives, and is equivalent: the database cascade removes the same rows.
- The BUG-2890 fix (every line of the order deleted explicitly) passes D-02.

## Traceability
- cases 363, tests 363 (functions plus `pytest.param` ids); TOM-C-12 is retired.
- Unmatched: none. Duplicates: none.
- Marker mismatches: none. 281 pass cards have no marker. 82 xfail cards use `xfail()`, which builds `pytest.mark.xfail(strict=True, reason=…)` and names every BUG ID on the card; U-25 carries both BUG-2903 and BUG-2895.
- Every BUG ID used exists in `docs/testing/bugs.md`.
- `--runxfail`: all 82 xfail tests fail inside the card's "Fails today on" block (81 on the named Then N; D-02 in the When, as its card says).
- Recorded by my own plugin, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tov\vplug.py`, which logs the failing test-file line and the `# Then N` block around it. Compared by `cmpfail.py`: 0 mismatches.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_transfer_order_manager.py -q -p no:cacheprovider -o addopts="" --cov=app.managers.transfer_order_manager --cov-branch --cov-report=term-missing
  app\managers\transfer_order_manager.py  332  5  122  2  98%   352, 557-559, 572
  281 passed, 82 xfailed, 19 warnings in 46.65s
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_transfer_order_manager.py -q -p no:cacheprovider -o addopts="" --runxfail -p vplug
  82 failed, 281 passed, 4 warnings in 22.70s
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_transfer_order_manager.py -q -p no:cacheprovider -o addopts=""   (×2)
  281 passed, 82 xfailed, 4 warnings in 25.36s
  281 passed, 82 xfailed, 4 warnings in 24.61s
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/transfer_order_manager.py tests/unit/managers/test_transfer_order_manager.py --json C:/Users/User/AppData/Local/Temp/makorsh-pipeline/tov/mut.json
  Mutants: 367 · killed 347 · timeout 0 · survived 20 · score 95%  (raw; 100% after classification)
.venv/Scripts/python.exe C:/Users/User/AppData/Local/Temp/makorsh-pipeline/tov/variants.py <variants.json | variants3.json | variants4.json>
  101 hand variants; results in C:/Users/User/AppData/Local/Temp/makorsh-pipeline/tov/variants.log
```
All runs used a private `COVERAGE_FILE` under `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tov\`. The results match the notes' Result line: 281 / 82, 98% branch, 5 missed statements, 2 partial branches.
