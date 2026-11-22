# Verification — `app/services/expense_order_service.py`

> **Verdict:** NEEDS WORK
> Tests: 197 passed · 29 xfailed (reproduced ✅, 3 identical runs; all 29 fail on their card's "Fails today on" Then line under `--runxfail`) · coverage 100% branch (284 statements, 46 branches)
> Mutation: 207 mutants · 196 killed · 11 survived → score 96% (196 / 205, after excluding 2 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 3a (V-03 = `xfail BUG-3070`, Fails today on Then 4)

## Summary
The tests are faithful. All 226 cards have exactly one test, every Then line is asserted at the strength the card gives, the markers match, and no test mocks more than the Conventions allow. The runs reproduce the notes exactly, and every xfail fails on its named Then line. The tests catch nearly every hand-written variant: no commit, commit before the error, partial writes, a read that commits, error mapping, HR-16 W0/W2 reads, the lock forms (`FOR UPDATE` with or without `OF expense_orders` accepted; `NOWAIT`, `SKIP LOCKED`, `FOR SHARE`, `FOR NO KEY UPDATE`, a late lock and a joined read rejected), the P3 check order, the BUG-3065/3066/3067/3069/3070/3063/629 fixes (correct fixes accepted, wrong ones rejected) and R4/R4b.

The case designer must fix three gaps:
1. A missing `except: rollback` goes unseen in most methods (TC3).
2. The void's event texts are asserted only inside xfail cards.
3. The default page and stats filters are never checked.

No new bug was found.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing (TC3) | every `X (after the commit point)` / `committed: x_gone` card (E-02, U-07/08/13/14, X-03/04/06, C-*, V-*, I-*, AI-05/06, RI-*, AA-05/06/08, RA-04, AP-04, UA-02, T-04/05) and every failing-commit card | The "service rolled back" proof is empty. The `committed:` prefix makes the test run `db.rollback()` itself before `x_gone`, so X is gone whether or not the service rolled back. In the failing-commit cards, `rb.call_count >= 1` is satisfied by `BaseService._commit_transaction`, which rolls back itself. So deleting `self._rollback_transaction(db)` from an `except` block goes unseen, unless the error comes after a flushed write (void: V-09). | Variants: `tc3_create_no_rollback` gives 197 passed (E-02 and E-03 pass). `tc3_cif_no_rollback` gives 197 passed. `tc3_void_no_rollback` on the error cards only (V-06/07/21/22) gives 4 passed. | **case designer**: check X *before* any test-level rollback (a `session:` line such as `X not in db` / `db.get(Workspace, X_ID) is None` straight after the raise), or add a rollback spy on one error card per write method. Probably applies to every service cases file built on the `department_service` conventions. |
| 2 | case-missing | `void_expense_order` V7, V9 (lines 336, 343, 354, 355) | Only V-03 (xfail BUG-3070) and V-15 (xfail BUG-3067) assert these: the `approvals_reset` reason, the `invoice_voided` description, the `eo_voided` description and its `{"void_note": …}` metadata. Both are excluded from the passing run, so these intended texts are unchecked today. | 6 surviving mutants (#6–#11). Variant `aw_void_reset_wrong_reason` gives 197 passed. | **case designer**: assert them in a passing card, e.g. add them to V-10 (a voided invoice keeps the id, so its events are all correct today), or split V-03 so that only the metadata line is xfail BUG-3070. |
| 3 | case-missing | `list_expense_orders_page` P-1 / `get_expense_order_hub_stats` H-1 defaults (lines 145, 146, 188) | No card checks that, with no filter, completed and voided orders are listed (page) and voided orders are counted (stats). The L/P cards have no completed or voided order without an explicit filter. H-01 covers `exclude_complete` only. | 3 surviving mutants (#1–#3). Variant `am_page_default_excludes_completed` gives 197 passed. | **case designer**: one P card and one H card where a completed and a voided order appear under the defaults. If the designer finds the page/stats defaults unstated, route to the **describer** (fill-gaps: "the defaults are those of `_hub_filter_kwargs`"). |
| 4 | case-missing (minor) | EOS-V-13 (BUG-3069) Given | `pay(V, "10.00")` is added, but the invoice keeps `paid_amount 0.00` / `payment_status "unpaid"`. A wrong fix that refuses only an *unpaid* finalized invoice therefore passes V-13. | Variant `b3069_wrong_only_with_payments` (`… and not invoice.paid_amount`) was ACCEPTED by V-13 under `--runxfail`. | **case designer**: make V's payment state match the payment row (`paid_amount 10.00`, `payment_status "partial"`), or add a twin with no payment. |
| 5 | cosmetic (known) | EOS-V-03 marker reason; notes DISCREPANCY-3; module docstring | The marker reason still says "(DISCREPANCY-3: the card's Expect line still says pass)". The card now says `xfail BUG-3070` (rev 3a), so the marker itself is right. The module docstring still says "revision 2". This was already known (the coordinator is correcting V-03's card), so it is not counted against the verdict. | Card line 1731 vs. test line 2877 | **executor**: refresh the reason text, the docstring and the DISCREPANCY-3 row at the next touch |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | 145 | page `exclude_complete=False` → `True` | case-missing | Finding 3 | case designer |
| 2 | 146 | page `exclude_voided=False` → `True` | case-missing | Finding 3 | case designer |
| 3 | 188 | stats `exclude_voided=False` → `True` | case-missing | Finding 3 (line 187 is killed by H-01) | case designer |
| 4 | 62 | `getattr(record, '_approvals_reset', False)` default → `True` | equivalent | `ExpenseOrderManager.update_expense_order` always sets `_approvals_reset` on its only return path (manager line 278), so the default is never used | — |
| 5 | 301 | `action='confirmed'` → `''` | equivalent | `notify_invoice_action` checks only `action == "draft"`; any other value gives the same "confirmed" preview and title | — |
| 6 | 336 | reset reason `'Cleared approvals — …'` → `''` | case-missing | Finding 2 (only V-03 and V-15, both xfail) | case designer |
| 7 | 343 | `'Invoice unlinked — e…'` → `''` | case-missing | Finding 2 | case designer |
| 8 | 343 | `' voided'` → `''` | case-missing | Finding 2 | case designer |
| 9 | 354 | `'Expense order '` → `''` | case-missing | Finding 2 | case designer |
| 10 | 354 | `' voided. Reason: '` → `''` | case-missing | Finding 2 | case designer |
| 11 | 355 | metadata key `'void_note'` → `''` | case-missing | Finding 2 | case designer |

## Variants tried (own script, temp copy of the backend; app/ untouched)
99 variants. Every outcome was as intended, except those listed in Findings 1–4.
- **TC1 no commit** (void, remove_approver, remove_item, delete): all caught (V-01, RA-01, RI-01, X-01).
- **TC2 commit before the error** (update before the notice, add_item before the sync, complete between confirm and notice, template before the sync, add_approver before the notice): all caught (U-13, AI-06, C-19, T-05, AA-08).
- **TC3 missing rollback**: caught only for void (V-09). Not caught for create or create-invoice → Finding 1.
- **TC4 partial write / a flush-only helper that commits** (`_create_draft_invoice`, `_resync_draft_invoice`, `_sync_or_create_invoice`; void keeps the link; draft without lines; `updated_by` dropped or added): all caught.
- **TC6 a read that commits or rolls back** (get, page, stats, items, approvers, summary, events, C2 early return): all caught.
- **Error mapping** (400 mapped too, 404 not mapped, `from None`, other error swallowed, mapped to 400): all caught (D-06…D-09, AI-06).
- **HR-16** (an unscoped invoice read in complete / void / sync): caught (C-12, V-11, Y-05). An unscoped re-read of the line's own order in `update_item` was not caught. It is equivalent: the manager has already scoped the line to the workspace, so its order is the same one.
- **Lock (BUG-3062)**: plain `FOR UPDATE` and `FOR UPDATE OF expense_orders` ACCEPTED (C-21, V-24, I-15). `NOWAIT`, `SKIP LOCKED`, `FOR SHARE`, `FOR NO KEY UPDATE`, a late locked re-read and a read joined to approvers REJECTED. A locked read in the real code breaks no passing test.
- **P3 order (BUG-3065)**: voided checked first ACCEPTED (C and I cards). Voided after C2 → C-22 rejects. After the approvals check → C-06 rejects. After the 409 → I-08 rejects. Wrong text → I-05, I-06, I-08 reject.
- **BUG-3066**: the fix (sync in `remove_approver`) ACCEPTED, and the full run stays green. Drafting without the notice → RA-02 rejects.
- **BUG-3067**: the fix ACCEPTED. Wrong reason → V-15 rejects.
- **BUG-3069 (OQ-62)**: refusing a finalized invoice ACCEPTED (V-13, V-14), and the full run stays green. Wrong message → V-13 rejects. 409 → V-13 rejects. Voiding the bill instead (option b) → V-14 catches it in the passing run. Refusing only an unpaid bill → accepted (Finding 4).
- **BUG-3068**: not tried. U-11/U-12 can only pass once the manager's BUG-753 lets `null` through, so a service-only fix cannot be exercised.
- **BUG-3070 / 3063**: the fixes ACCEPTED (V-03, V-10; D cards).
- **R4/R4b**: the R4b fix (inactive → 400, `allow_invoices` false → 403) ACCEPTED (R-08, R-09, U-07, U-14), and the full run stays green. Inactive → 403 → R-08 rejects. Account copy dropped → U-14 catches. `None` account copied → R-11. Due date only when set → R-04. Empty description clears notes → R-06. One update per field → R-12. Update always called → R-01. Lines not resynced → U-05. Resyncing a confirmed invoice is not caught; this is equivalent, because `sync_items_from_list` and `update_invoice` leave a non-draft invoice alone (Y-03 stays unchanged).
- **Approvals wiped or met**: notice always / never → U-01 / U-02. A notice on a line edit → AI-01. Void without a reset → V-04. Met ignored in sync / complete / create-invoice → U-01, C-08, I-07. Unapprove runs the sync → UA-01. Add-approver runs the sync → AA-04. Approve without the sync → AP-02. Update without the sync → U-05. C2 skipped → C-04.

## Traceability
Cases: 226. Test IDs: 226 (194 functions, of which 8 are parametrized with `id=`). Unmatched IDs: none. Duplicates: none. Tests without an ID: none.

Marker mismatches: none. 29 strict xfails, and each names its BUG ID: 3062 ×3, 3063, 3064 ×3, 3065 ×6, 3066, 3067, 3068 ×2, 3069, 3070, 627, 628, 629 ×3, 639, 742, 755 ×2, 1193. Every ID exists in `docs/testing/bugs.md`. V-03 has the known stale reason text (Finding 5).

Each test's `# Then N` comments run 1…N in card order. A literal check of each Then line against its block left only f-string and parametrize false positives. Ruff is clean.

## Commands run
```
COVERAGE_FILE=<scratch>/.cov1 .venv/Scripts/python.exe -m pytest tests/unit/services/test_expense_order_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.expense_order_service --cov-branch --cov-report=term-missing
  → app\services\expense_order_service.py 284 0 46 0 100% · 197 passed, 29 xfailed
  (runs 2 and 3, same command without --cov) → 197 passed, 29 xfailed · 197 passed, 29 xfailed
.venv/Scripts/python.exe -m pytest tests/unit/services/test_expense_order_service.py -q -p no:cacheprovider -o addopts="" --runxfail -rf --tb=long
  → 29 failed, 197 passed; own checker (failing line → nearest `# Then N`): 29/29 match the card's "Fails today on"
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/expense_order_service.py tests/unit/services/test_expense_order_service.py --lines <shard> --timeout 240 --json <scratch>/mutN.json
  0-224   → 40 · killed 36 · survived 4
  225-309 → 42 · killed 41 · survived 1
  310-425 → 42 · killed 36 · survived 6
  426-518 → 42 · killed 42 · survived 0
  519-700 → 41 · killed 41 · survived 0
  total 207 · killed 196 · timeout 0 · survived 11 (all 5 shards finished before this verdict)
.venv/Scripts/python.exe <scratch>/variants.py  (3 parallel parts, own scratch script, temp copy) → 99 variants, outcomes above
.venv/Scripts/python.exe -m ruff check tests/unit/services/test_expense_order_service.py → All checks passed!
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2v2\expense_order_service\` (trace.py, xfcheck.py, side.txt, mut1–5.log/json, variants.py/json, var0–2.log).

## Round 2 — 2026-11-22

> **Verdict:** PASS
> Tests: 199 passed · 29 xfailed (reproduced ✅, 3 runs identical) · coverage 100% branch (284 statements, 46 branches)
> Mutation: 207 mutants · 205 killed · 2 survived → score 100% (205 / 205, after excluding 2 equivalent, 0 dead, 0 bug-path)
> Cases revision: 4

Narrow re-check of Round 1 findings 1–4 against cases Revision 4.

**Fidelity of new and changed tests.** No findings.
- Traceability: 228 cards. All of them map to a test name or a `pytest.param(id=…)`, and no test lacks a case ID.
- All 42 cards with an X line assert `x not in db` right after the `pytest.raises` block, before any `db.rollback()` or re-read (checked by script).
- The 14 named error cards (E-02, U-08, X-03, C-07, V-06, AI-05, UI-05, RI-03, I-02, AA-05, RA-04, AP-04, UA-02, T-04) run inside `spies(db)` and assert `rb.call_count >= 1`. The other 16 cards that check `rb.call_count` are failing-commit or failing-notice cards, which use their own rollback spy.
- V-10 asserts Then 1–10 in order, including the three event descriptions, both metadata dicts and the performers.
- V-13's Given has `paid_amount 10.00` and `payment_status "partial"`.
- P-09 and H-08 match their cards line by line.
- Cosmetic items: the docstring names revision 4, and V-03's marker and the DISCREPANCY-3 row are current.
- Ruff is clean.

**Former survivors.** All 9 case-missing survivors are now killed.
- Shard `--lines 140-190`: 7 mutants, 7 killed. L145, L146 and L188 are killed (L187 too).
- Shard `--lines 330-360`: 17 mutants, 17 killed. L336, L343 (×2), L354 (×2) and L355 are killed.
- The two Round 1 equivalents (L62, L301) are unchanged.

**Variants** (own script `r2var.py`, run on a temp copy of the backend).
- Removing `_rollback_transaction` was CAUGHT in each of the 14 write methods. The catching cards were:
  - create: E-02
  - update: U-08, U-13, U-14
  - delete: X-03, X-04
  - complete: 6 C cards
  - void: V-06, V-07, V-09, V-21
  - add_item: AI-05, AI-06
  - update_item: UI-05
  - remove_item: RI-03, RI-05
  - create invoice: I-02, I-09, I-10, I-12
  - add_approver: AA-05, AA-06, AA-08
  - remove_approver: RA-04
  - approve: AP-04
  - unapprove: UA-02
  - template: T-04, T-05
- A no-op `_rollback_transaction` was CAUGHT by 33 tests.
- BUG-3069: the correct fix was ACCEPTED (V-07, V-10, V-11, V-13, V-14). The wrong fix that refuses only unpaid bills was REJECTED by V-13.

**Runs.**
- Plain run: `199 passed, 29 xfailed` three times; coverage `TOTAL 284 0 46 0 100%`.
- `--runxfail -rf`: `29 failed, 199 passed`.
- `--runxfail -m xfail` with the line check: all 29 fail on their card's "Fails today on" Then line.

**Routed:** nothing. Round 1 findings 1–4 are closed.
