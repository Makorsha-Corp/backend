# Verification — `app/services/work_order_service.py`

> **Verdict:** NEEDS WORK
> Tests: 225 passed · 39 xfailed (reproduced ✅, 3 runs identical) · coverage 100% branch (318 statements, 66 branches)
> Mutation: 184 mutants · 178 killed · 6 survived → score 98.9% (178 / 180, after excluding 2 equivalent, 0 dead, 2 bug-path)
> Source commit: e48a092 · Cases revision: 3 · Verified 2026-11-22 (stage 5)

## Summary
The tests are faithful to the cards. All 264 case IDs are traced, every marker matches its Expect line, and none of the tests is weakened, swallowed or mocked beyond what its card asks for. Every xfail fails on the Then line its card names, and the lock cards tell the exact clause apart (experiment below). Two things still need work:
- **The TC3 "X is gone" check proves nothing.** The convention runs `committed: x_gone` after the test's own `db.rollback()`, and that rollback drops X whether or not the service rolled back. With each method's rollback stripped in-process, **9 of the 18 write methods still pass the whole file**.
- **Two small rules have no card.** The default `exclude_completed=False` of `list_sheet_bundles` and the frozen `_WorkOrderEnrichment`.

Both go to the case designer. No new app bug was found, so `bugs.md` is unchanged.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-design (TC3 check is vacuous) | Conventions "`committed:` lines" + "x_gone"; every card with `committed: x_gone` (E-02, T-03, B-04, X-02, RA-02, AP-02, UA-02, UI-03, RI-02, and others) | `x_gone` is always checked after the test-level `db.rollback()`. That rollback is a savepoint rollback, and it removes the pending X whether the service rolled back or not. So TC3's "every other uncommitted change pending in that session is discarded" is never really tested. Missing rollbacks are caught only by chance, when some write was flushed before the error and an `unchanged` / `nothing written` line is read before the test's rollback. | tc3method experiment (`svc3v/wo/tc3/*.txt`): with the rollback stripped, these still give **225 passed**: `create_work_order`, `create_work_order_from_template`, `bulk_delete_future_recurrence_drafts`, `delete_work_order`, `remove_approver`, `approve_as_me`, `unapprove_as_me`, `update_item`, `remove_item`. Caught: `update_work_order` (U-08), `add_approver` (AA-09), `add_item` (AI-04), `start_work_order` (S-02), `sheet_entry` (SE-04), `complete_work_order` (C-16, C-22), `complete_work_order_as_planned` (P-08, P-14, P-16, P-17), `void_work_order` (V-05, V-13), `create_invoice_for_work_order` (I-36). | **case designer**: change the convention so the X check runs right after the raise, before any test-level rollback (e.g. `session: db.get(Workspace, X_ID) is None`, or `X not in db`, as a non-`committed:` line). Then the executor re-implements. |
| 2 | case-missing | SB1 (`list_sheet_bundles` default filters) | No card calls `list_sheet_bundles` without `exclude_completed` while a completed order exists, so a wrong default is not noticed. | Survivor L265 `exclude_completed: bool = False → True`. | **case designer** |
| 3 | case-missing | Facts G4 (`_WorkOrderEnrichment` is `@dataclass(frozen=True)`) | No card checks that the enrichment is frozen (assigning a field raises `FrozenInstanceError`). | Survivor L52 `frozen=True → False`. | **case designer** (low priority) |

Known, not findings (card wording, as briefed): S-02 Then 7 names the column `quantity`, but the model's column is `qty` (notes DISCREPANCY-8; the test reads `qty`, same values). This goes to the **case designer** as a wording fix.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | L52 | `frozen=True → False` | case-missing | See finding 3. | case designer |
| 2 | L265 | `exclude_completed=False → True` | case-missing | See finding 2. | case designer |
| 3 | L415 | `action='confirmed' → ''` (complete) | equivalent | `notify_invoice_action` branches only on `action == "draft"`; any other value gives the same "confirmed" preview and recipients (approval_notification_service.py L301–306). C-03 checks the preview. | — |
| 4 | L463 | `action='confirmed' → ''` (as planned) | equivalent | Same as #3. P-02 checks the preview. | — |
| 5 | L553 | `Decimal(0) → Decimal(1)` (`unit_price` fallback) | bug-path | Reached only when cost is None or 0, which is BUG-3228 / OQ-65 (I4a: refuse with 422). Only the xfail cards I-20…I-22 drive it. | — (goes away with the fix) |
| 6 | L554 | `Decimal(0) → Decimal(1)` (`line_subtotal` fallback) | bug-path | Same as #5. | — |

## Variants checked
- **TC1–TC6 / TC3 per method.** Done with the tc3audit plugin (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tc3audit\tc3method.py`), on all 18 write methods; results are in finding 1. Failing commits are covered anyway, because `_commit_transaction` rolls back by itself. TC6 (no commit, no rollback, `X in db`) holds on every read card.
- **Error mapping.** I-28 and I-29 check the 422 `ACC404` text, with `__cause__` being the 404. I-25, I-26 and I-27 check that other errors pass unchanged (400, 400, 403). Every mutant on L532–538 was killed.
- **HR-16 W0/W2.** Both sides are covered for the enrichment (LE-03/04, LE-07), get (G-04/05), complete (C-09/10), void (V-07/08), delete (X-12/13), bulk (B-11/13) and the invoice account (I-28/29). Complete-as-planned (P-10) and the re-plan (SE-10) have the W2 side only; that is acceptable, since the code path is the same as C-09/10 and B-13.
- **Lock clauses (BUG-2916 completion lock C-27; BUG-3222 on P-21, V-18, I-37).** Checked with my own in-process plugin `svc3v/wo/lockplug.py`, which wraps `get_work_order`:
  - plain `FOR UPDATE` and `FOR UPDATE OF work_orders`: all 4 pass.
  - `NOWAIT`, `FOR SHARE` and `FOR KEY SHARE`: all 4 fail on Then 2.
  - A lock taken after reading `account_invoices`: all 4 fail on Then 3 (lock first).
  - With the plain lock, the whole file shows only the 4 strict XPASS, and no other test breaks.
- **OQ-62 void refusal (BUG-3224).** V-09 checks the 400 `FINAL`, a clean session, the order, approver, invoice and payment unchanged, nothing written, and X. V-12 and V-14 check the refusal comes before any `account_invoices` statement. Companions: V-10, V-11, V-13.
- **OQ-65 cost required (BUG-3228).** I-20…I-22 check the 422 `NOCOST` for cost None, 0.00 and −5.00. I-23 (0.01 is enough) and I-24 (account error first) are the companions.
- **BUG-3225, invoice on a voided or completed order.** I-12, I-13, I-15 and I-16 check the 400 texts, including the precedence over the 409. I-14 and I-17 make sure a second invoice is never created.

## Traceability
Cases 264 · collected tests 264 (259 functions; C-18…21, V-07/08 and I-21/22 are parametrized with ids) · unmatched: none · duplicated: none.

Marker mismatches: none.
- Every `pass` card has no marker.
- Every `xfail BUG-n` card has `xfail(strict=True)`, and its reason names exactly the card's BUG IDs (39 / 39).
- All BUG IDs are in `docs/testing/bugs.md`.

Every card's numbered Then lines appear as `# Then N` in the test, in order. Fidelity was read card by card for all 264 cards (side-by-side dumps in scratch): no missing, weakened or changed assertion, no wrong setup, no swallowed failure and no extra mock.
- The `try/except HTTPException`, `pytest.raises(Exception)`, `in (400, 409)` and `rb.call_count >= 1` forms all come from the cards' own wording.
- The extra patches are only the ones the cards list: U-06, B-04, SB-02, I-31, I-30, RI-01, the failing notify cards, and the clock.

`ruff check`: clean.

## Commands run
```
COVERAGE_FILE=<scratch>/.cov1 .venv/Scripts/python.exe -m pytest tests/unit/services/test_work_order_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.work_order_service --cov-branch --cov-report=term-missing
  → 318 stmts · 0 miss · 66 branches · 0 partial · 100% ; 225 passed, 39 xfailed
(same, runs 2 and 3) → 225 passed, 39 xfailed · 225 passed, 39 xfailed
.venv/Scripts/python.exe -m pytest … --runxfail -rf → 39 failed, 225 passed
PYTHONPATH=<scratch> … --runxfail -p thenplug → 39/39 fail inside the card's "Fails today on" Then line
  (V-04: the plugin's last test-file frame is the `_void` helper; the failing call sits under `# Then 1`, IntegrityError as the card says)
PYTHONPATH=<scratch> … --collect-only -p markplug + markcheck.py → 264 items, 0 marker mismatches
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/work_order_service.py tests/unit/services/test_work_order_service.py --lines {1-199|200-439|440-534|535-700} --timeout 300 --json <scratch>/mut_<range>.json
  → 41/40 killed · 48/46 · 49/48 · 46/44 = 184 mutants, 178 killed, 6 survived
TC3_SVC=work_order_service TC3_METHOD=<m> PYTHONPATH=<tc3audit> … -p tc3method (18 methods) → see finding 1
LOCKMODE={plain,of,nowait,share,nokey,late} PYTHONPATH=<scratch> … -p lockplug --runxfail -k "c_27 or v_18 or p_21 or i_37" → 4 pass / 4 pass / 4 fail T2 / 4 fail T2 / 4 fail T2 / 4 fail T3
.venv/Scripts/python.exe -m ruff check tests/unit/services/test_work_order_service.py → All checks passed
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3v\wo\`, with a private COVERAGE_FILE for every run.

## Notes for future work
- The vacuous `committed: x_gone` placement most likely comes from a shared convention, so other service cases files that put X after a test-level rollback probably have the same blind spot. A quick check of earlier modules with tc3method would tell. This is pipeline-wide, for the case designer's skill or helper sheet.
- When BUG-3228 is fixed, the `wo.cost or Decimal(0)` fallback becomes dead code for new drafts; the two L553/L554 survivors then go away.
- The equivalence of L415 and L463 depends on `notify_invoice_action` treating every non-"draft" action as "confirmed". If that function gains more actions, a card that checks the value of `action` will be needed.

## Round 2 — 2026-11-22

> **Verdict:** PASS
> Tests: 228 passed · 39 xfailed (3 runs identical; `--runxfail` 39 failed, each on its card's Then line) · coverage 100% branch (318 statements, 66 branches)
> Mutation: the round-1 survivors L52 and L265 (line numbers unchanged, source still e48a092) are now **killed** (`--lines 52-52`, `--lines 265-265`). The remaining 4 survivors keep their round-1 class (2 equivalent, 2 bug-path), so the score is 180 / 180 = 100% after exclusions.
> Cases revision: 4 · notes: 228 / 39, 0 discrepancies

**Findings:** none. Round-1 findings 1–3 are closed.
- **Finding 1 (TC3).**
  - The fix: all 43 cards with X now check `assert X not in db` right after the raise. A script confirmed this comes before any re-read, snapshot, count or test-level `db.rollback()`.
  - The 18 spy cards (E-02, T-03, U-09, B-04, SE-03, X-02, S-02, C-16, P-14, V-11, I-18, AA-04, RA-02, AP-02, UA-02, AI-03, UI-03, RI-02): I read each one against its card. The spies sit inside `pytest.raises`, and each card's Then lines are asserted in order.
  - Re-run of the tc3method rollback strip on the 9 methods that used to survive: **every one is now killed**, each failing on `assert X not in db`.

    | Stripped method | Failing test |
    |---|---|
    | create_work_order | E-02 |
    | create_work_order_from_template | T-03 |
    | bulk_delete_future_recurrence_drafts | B-04 |
    | delete_work_order | X-02 |
    | remove_approver | RA-02 |
    | approve_as_me | AP-02 |
    | unapprove_as_me | UA-02 |
    | update_item | UI-03 |
    | remove_item | RI-02 |

- **Findings 2–3.** SB-13 (default: a completed order is counted and listed), SB-14 (`exclude_completed=True` is passed through) and LE-14 (field order, `FrozenInstanceError`, value unchanged, positional construction gives an equal value) are faithful to their cards.
- **Wording.** S-02 Then 9 now names `qty`, and the test reads `qty == 10` / `qty == 2`.

**Traceability (full file):**
- Cases and collected tests: 267 / 267. No case is unmatched or duplicated.
- Markers: 0 mismatches. 39 strict xfails, reasons equal to the cards' BUG IDs, all in the register.
- Every card's `# Then N` lines appear in order.
- `ruff check` is clean.

**Commands run (scratch `svc3v\wo\r2\`, private COVERAGE_FILE):**
- The plain run with `--cov … --cov-branch`, plus 2 more plain runs, gave 228 passed and 39 xfailed each time.
- `--runxfail -p thenplug` → 39 failed and 228 passed. Every failure is on its card's line. V-04 is the same helper-frame artefact as in round 1; it fails under `# Then 1`.
- `--collect-only -p markplug` → 267 tests collected, 0 marker mismatches.
- `TC3_SVC=work_order_service TC3_METHOD=<m> … -p tc3method` on the 9 methods → each gives 1 failed and 227 passed.
- `mutate.py … --lines 52-52` and `--lines 265-265` → 1 / 1 killed each.
