# Verification — `app/services/account_invoice_service.py`

> **Verdict:** NEEDS WORK
> Tests: 99 passed · 43 xfailed (reproduced ✅, 3 runs identical, `--runxfail` 43/43 fail on the card's named Then line) · coverage 98% branch (151 stmts, 3 missed: 198, 399–400; 30 branches, 0 partial)
> Mutation (mutate.py, full file, 4 shards, all finished): 139 mutants · 106 killed · 33 survived → score 100% (after excluding 1 equivalent, 9 dead, 23 bug-path)
> Hand mutants (my own, on a copy): 84 kill-mode variants · 76 killed · **8 survived** (all `case-missing`); 52 reference-fix / wrong-fix variants · 51 as expected · 1 needs a second bug ID (K-35)
> Source commit: e48a092 · Cases revision: 2a

## Summary
The tests are faithful to the cards. Every card has exactly one test, every Then line is asserted with the card's exact values, and each strict xfail fails on the Then line its card names. mutate.py finds no weak test: every survivor is in dead code (hub page, the Q7 PO-total write) or on a bug path (the sales/work-order resync branch, the expense-order notification of K8).
Hand mutants turned up **four gaps in the cases**, all for the case designer. (1) A missing rollback is not caught on `create`, `update` and `revert`, or on a non-HTTP error in `void`. The TC3 cards check `x_gone` only *after* the test's own `db.rollback()`, as the executor's notes warned. (2) Nothing checks that `delete_invoice` and `resync_items` commit exactly once. A commit between the delete and the PO unlink survives. (3) No card covers another workspace's PO on `void_invoice` or `delete_invoice`; `confirm` has K-16 and K-17. (4) K-35 cannot pass without BUG-1205 as well as BUG-2965, so its Expect line has to name both.
Locks were tested hard: all 30 lock variants behave as the cards intend (exact clause, `OF <lines>`, SKIP LOCKED / NOWAIT / FOR SHARE / JOIN refused, and the order order row → lines → invoice). Reference fixes for BUG-2962/2963/2964/2966/2967/2968/2969/2732 turn their xfails green without breaking a passing test. Each wrong fix I tried fails the intended card.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing (TC3 missing rollback) | C-02, C-03, U-03, V-02 (and every error card's `x_gone`) | `x_gone` runs after the test's own `db.rollback()`, which discards X whether or not the service rolled back. For `create_invoice`, `update_invoice` and `revert_to_draft` the refusal comes before any write, so `nothing written` and `session clean` cannot see the missing rollback either | Hand mutants NR-create_invoice, NR-update_invoice, NR-revert_to_draft (`self._rollback_transaction(db)` → `pass`) **survive** | **case designer**: add a check right after the call, before any `committed:` line, e.g. `session: X not in db` (the service's rollback expunges the pending X) or a rollback spy `rb.call_count == 1` on one error card per write |
| 2 | case-missing (TC3, non-HTTP error) | `void_invoice` X6 / TC3 | No void card raises a non-`HTTPException` before the commit (X-10's failing commit is rolled back by `_commit_transaction` itself), so `except Exception` → `except HTTPException` goes unnoticed | Hand mutant EM-http-only-rollback-void **survives** (the same mutant on resync is killed by S-06) | **case designer**: one void card with a database error after a write (e.g. an `IntegrityError` or forced error from an internal collaborator, as K-13 does) checking nothing written |
| 3 | case-missing (TC1 commit count) | `delete_invoice` D2, `resync_items` S4 | Only `update_invoice` has a "commits exactly once" card (U-05). An extra commit between the manager delete and the PO unlink, or a double commit in resync, passes every test | Hand mutants CB-delete-after-manager, CB-resync-after-sync **survive** | **case designer**: a spies card `cm.call_count == 1`, `rb.call_count == 0` for delete (with a PO) and resync (as U-05). If delete + unlink must be atomic, it is not stated as a rule (confirm K5 and void X6 say "committed together"); ask the describer only if a card needs it |
| 4 | case-missing (HR-16) | `void_invoice` X1 / Overview "The PO's invoice"; `delete_invoice` D1/D4 | No card puts another workspace's PO pointing at the invoice on void or delete (confirm has K-16/K-17). An unscoped PO lookup (lowest id, any workspace) survives on both | Hand mutants LG-void-po-unscoped, LG-delete-po-unscoped **survive** (LG-confirm-po-unscoped killed by K-16) | **case designer**: X-xx and D-xx isolation cards with a W0 PO (lower id) `invoice_id V.id`: it is untouched, no event, and the W1 void/delete proceeds |
| 5 | marker / card Expect | AIS-K-35 | Fixing BUG-2965 in the service alone cannot make K-35 pass: `notify_invoice_action` has no `sales_order` approvers branch and `ORDER_PREFIX` has no `sales_order` (BUG-1205). The test is strict xfail with reason BUG-2965 only, so after the BUG-2965 fix it stays xfailed for an unlisted reason | My reference fix F-2965-ok: K-30…K-34 pass, K-35 fails `assert [U1] == [U1, U4]` (approver not notified) | **case designer**: K-35 `Expect: xfail BUG-2965, BUG-1205`; then **executor** updates the marker reason |

Fidelity (read every test against its card): **no findings.** No weakened or missing assertion, no changed value, no wrong setup, no swallowed failure, no extra mocks (only the Conventions spies, failing commit/refresh, and K-13's `notify_invoice_action` patch). X-09's step 6 adds a flush (recorded in the notes; the card's literal step fails NOT NULL in one flush). The end state is identical, so it is not counted as a finding; see Notes.

## Surviving mutants (mutate.py)
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1-6 | 198 | return None | dead | `list_accounts_hub_page`, spec "Not specified" / Q8 remove | — |
| 1-17,18,19 | 193, 195, 196 | defaults `'overview'`→'', 0→1, 50→51 | dead | same dead method | — |
| 2-11,13,15 | 396 | negate / `==`→`!=` / `'sales_order'`→'' | bug-path | Only xfail cards S-17…S-24 (BUG-2963/2964) reach the sales / work-order / unknown-type branches; no passing card resyncs any type other than PO or expense | — |
| 3-14,17-29,34,35 (16) | 399–410 | all | bug-path | Unreachable today (line 398 always raises AttributeError, BUG-2963); S-17 covers it after the fix (my reference fix F-2963-4-ok passes S-17) | — |
| 3-7,12,13 | 443 | negate / `!=` / `'draft'`→'' | dead | Q7: the PO-total write is overwritten by the manager's line sum (K4) and is listed as a dead write for clean-up; on a confirmed invoice the manager then raises and the write is rolled back | — |
| 3-16,33 | 444 | `or`→`and`, `0`→`1` | dead | same Q7 dead write | — |
| 4-14 | 469 | action `'confirmed'`→'' | equivalent | `notify_invoice_action` only branches on `action == "draft"`; '' takes the same non-draft path and writes identical rows (title_hint is fixed) | — |
| 4-15,16,22,23 | 474, 477, 481, 485 | expense-order notification (`limit`, `[0]`, `'expense_order'`, `'confirmed'`) | bug-path | K8 [BUG-2969]: today's notification is the buggy path. Only xfail K-18 targets it; K-24/K-25 (pass) cover the foreign-workspace side and kill the unscoped variant (LG-confirm-eo-unscoped) | — |

Score: 106 killed / (139 − 1 − 9 − 23) = 106 / 106 = **100%**.

## Hand mutants (variants the operators cannot make)
Applied to a copy of the backend in my scratch folder (`hand.py`). Mode *kill* runs the passing suite. Mode *ref* appends a reference or wrong fix and runs the named cards with `--runxfail`.

**Transaction contract.**
- **TC1, no commit:** killed on all 7 writes (C-01, U-01, D-01, V-01, S-01, K-01, X-01).
- **TC2, `db.refresh` removed:** killed on all 6 (`loaded()`).
- **TC3, missing rollback:** killed for delete (D-08), resync (S-06), confirm (K-12) and void (X-09). **Survived** for create, update and revert (finding 1).
- **TC6, a read that commits:** killed on all 8 reads. A read that rolls back on its 404 is killed too (G-04, L-13).
- **Commit before the error / partial writes:**
  - Confirm: a commit after the manager confirm, after the PO-total flush, after `apply_post_invoice_confirms`, or before notify is killed (K-12, K-13).
  - Void: a commit after the manager void, after `reset_approvals`, or before unconfirm is killed (X-09).
  - Delete: a commit between the delete and the unlink **survived** (finding 3).
  - Resync: a double commit **survived** (finding 3).

**Error mapping.**
- The service's own 400s changed to 409 (resync ×2, confirm ×2, void): all killed.
- The approval-count text swapped: killed (K-06).
- Every error re-raised as HTTP 500, or swallowed (returning None), on each of the 7 writes: all killed.
- Only `HTTPException` rolled back: killed on resync (S-06), **survived** on void (finding 2).

**Service checks.**
- Killed: approvals checked before sections (K-10); `any`→`all` on received lines (X-04).
- Killed: received guard moved after the manager void (X-05); `reset_approvals`, unlink or unconfirm dropped (X-02); void reason dropped (X-03).
- Killed: PO looked up after the delete (D-03); resync S3 checked before S2 (S-09).
- Killed: expense `or` fallbacks and line order (S-14, S-28).
- Killed: notify actor, event metadata, stage sync or post-confirms dropped, and follow-ups run before the manager confirm (K-02, K-03).
- Workspace scope: unscoped PO killed on confirm (K-16), **survived** on void and delete (finding 4). Unscoped PO lines killed (X-06); unscoped expense order killed (K-24).

**Exact lock clauses and lock order (BUG-2962).** All 30 variants behaved as the cards intend:
- **S-25:** passes with `FOR UPDATE` and with `OF account_invoices`. It fails with SKIP LOCKED, NOWAIT, FOR SHARE, a lock through a JOIN, or a lock taken after the order read.
- **K-15:** passes with `FOR UPDATE`, with `OF purchase_orders`, and with the PO locked before the invoice. It fails with SKIP LOCKED, a lock taken after the approvals read, or the invoice locked first.
- **X-08:** passes with the PO row, then lines `FOR UPDATE OF purchase_order_items`, then the invoice. It fails with plain `FOR UPDATE` on the lines (Postgres refuses the outer join), lines locked before the row, the invoice locked between row and lines, or no line lock.
- **X-25:** passes with the SO row, then `FOR UPDATE OF sales_order_items`. It fails with plain `FOR UPDATE` on the lines, NOWAIT, or the invoice locked first.
- **K-38:** passes with the SO row locked before the approvers. It fails with the approvers read first, or SKIP LOCKED.

**Bug fixes (reference fix → xfails pass, whole passing suite still passes; each wrong fix fails its card):**
- **BUG-2969 (K10):** K-18…K-23 pass; K-24/K-25 still pass. Wrong fixes caught:
  - no workspace scope → K-24/K-25;
  - work order named first → K-22;
  - voided expense orders ignored → K-20;
  - soft-deleted work orders ignored → K-21;
  - refused only on drafts → K-23;
  - 409 instead of 400 → all six.
- **BUG-2963/2964 (resync):** S-17…S-24 pass. Wrong fixes caught:
  - description taken before the item name → S-17;
  - sales lines newest first → S-17;
  - unscoped sales order → S-19;
  - soft-deleted work order found → S-22;
  - an unknown type still wipes the lines → S-24;
  - a `None` cost copied → S-21.
- **BUG-2965 (sales finalize):** K-30…K-34 pass, but **K-35 fails** (finding 5). Wrong fixes caught:
  - only one section checked → K-30;
  - checks after the confirm → K-32;
  - no event metadata → K-33;
  - no notification → K-35.
- **BUG-2966/2967 (void):** X-15, X-17, X-18, X-20, X-23, X-24 pass; X-16, X-19, X-21 still pass. Wrong fixes caught:
  - returned quantity subtracted → X-24;
  - only delivery lines checked → X-23;
  - expense approvals reset → X-18 and X-19;
  - sales sections kept → X-17.
- **BUG-2968/2732 (delete):** D-04, D-10…D-12 pass; D-03, D-13, D-14 still pass. Wrong fix caught: `is_invoiced` kept → D-10.
- **Freeze O1/F1–F7 and void R3a–R3c:** not implemented in the manager today (no `Invoice is locked …` text in `account_invoice_manager.py`). Their cards (D-09, V-05, X-13, X-14, V-06) are strict xfails that fail on Then 1/3 as named. There is no service-side code to mutate. Re-verify when the manager fix lands.

## Traceability
cases 142 · tests 142 · unmatched: none · duplicates: none. Marker mismatches: none: the 99 `pass` cards carry no marker, and the 43 `xfail BUG-n` cards use `xfail(n)` = `pytest.mark.xfail(strict=True, reason="BUG-n: …")` naming the card's bug. Every BUG ID used is in `docs/testing/bugs.md` (626, 639, 1202, 2730, 2731, 2732, 2733, 2736, 2788, 2962–2969). `--runxfail`: 43/43 fail inside the `# Then N` block their card's "Fails today on" names (my plugin `thenmap.py`). ruff check / format: clean.

## Commands run
```
COVERAGE_FILE=<scratch>/.cov1 .venv/Scripts/python.exe -m pytest tests/unit/services/test_account_invoice_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.account_invoice_service --cov-branch --cov-report=term-missing
  → app\services\account_invoice_service.py 151 3 30 0 98%  Missing 198, 399-400 · 99 passed, 43 xfailed
.venv/Scripts/python.exe -m pytest … -o addopts="" --runxfail -rf -p thenmap   (PYTHONPATH=<scratch>)
  → 43 failed, 99 passed; 43/43 on the named Then line
.venv/Scripts/python.exe -m pytest … -o addopts=""   (runs 2 and 3)
  → 99 passed, 43 xfailed · 99 passed, 43 xfailed
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/account_invoice_service.py tests/unit/services/test_account_invoice_service.py --lines {1-365|366-398|399-454|455-545} --timeout 300 --json <scratch>/mut_<range>.json
  → 35·31·4 | 35·32·3 | 35·14·21 | 34·29·5  (mutants·killed·survived; no timeouts)
.venv/Scripts/python.exe <scratch>/hand.py kill   → 84 · 76 killed · 8 survived
.venv/Scripts/python.exe <scratch>/hand.py ref    → 52 · 51 as expected · F-2965-ok: K-35 fails (BUG-1205)
.venv/Scripts/python.exe -m ruff check / ruff format --check tests/unit/services/test_account_invoice_service.py → clean
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1v2\account_invoice\` (logs, JSON, `hand.py`, `thenmap.py`); private COVERAGE_FILE per run.

## Notes (non-blocking, for the stages named)
- **Case designer:**
  - X-09 step 6 cannot run as written (one flush nulls `current_status_id` through the `Status.purchase_orders` backref). Write it as two steps: set `current_status_id` and flush, then delete SP1/SR1/SC1 and flush.
  - The lock vocabulary's "before U" is vacuously true when U is never read. K-38 alone would pass a fix that locks the sales order but never reads its approvers, so it relies on K-31 for the read.
- **Executor (when bugs are fixed):** remove the markers per the notes' list. After the BUG-2965 fix K-35 stays xfail until BUG-1205 is fixed too (finding 5).
- **Coverage:** line 198 is dead (Q8, dead-code checklist). Lines 399–400 run only after BUG-2963 is fixed. Line 443's write is dead (Q7).

## Round 2 — 2026-11-22

> **Verdict:** NEEDS WORK (one small fidelity fix for the executor: S-29 Then 4)
> Tests: 106 passed · 43 xfailed (reproduced ✅, 3 runs identical; `--runxfail` 43/43 fail on the card's named Then line) · coverage 98% branch (151 stmts, missed 198, 399–400; 0 partial) · ruff clean
> Cases revision: 3 · Source commit: e48a092 (unchanged)

**Scope.** A narrow re-verify of cases rev 3:
- new cards D-16, D-17, D-18, S-29, X-26, X-27, X-28;
- changed cards C-02, C-03, U-03, V-02 (`X not in db`), K-31, K-35, K-38 and X-09;
- `Recorder.before`, which now needs U to be read, plus the new `Recorder.reads`.

**Traceability.** 149 cards and 149 tests, with no unmatched or duplicate IDs. 106 cards are pass with no marker and 43 are strict xfail. K-35 is `@xfail(2965, 1205)`, so its reason names `BUG-2965` and `BUG-1205`, as the card's `Expect: xfail BUG-2965, BUG-1205` asks. BUG-1205 is in `bugs.md`.

**Fidelity of the new and changed tests.** All are faithful except the finding below. I checked:
- `X not in db` is asserted right after the call and before the test's rollback in C-02, C-03, U-03, V-02 and X-26.
- X-26 builds "failing unconfirm" exactly as the card's Forced errors entry: a patch on `app.services.account_invoice_service.purchase_order_manager`, the rollback spy, and `exc.value is E`.
- The D-17, D-18, X-27 and X-28 setups match their cards. Each has the foreign PO, its received line and approver, and all Then lines.
- K-31 has one approved and one pending approver and expects `Requires 2 approval(s); 1 so far`.
- K-38 has two approved approvers, and Then 4 is `rec.reads("sales_order_approvers")`.
- X-09 has two flushes.
- `before()` now returns False when U is never read.

| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| R2-1 | in-memory only (Conventions `committed:`) | AIS-S-29 Then 4 | The card's Then 4 is a `committed:` line. The test asserts `len(LINES(db, vid)) == 1` without the one `db.rollback()` that Conventions require before the first `committed:` line, unlike D-16. Harmless today, because Then 2's `cm.call_count == 1` already catches a missing commit, but it does not follow the card | `test_ais_s_29__resync_commits_once`: `# Then 3` … `# Then 4` with no `db.rollback()` in between | **executor** (add `db.rollback()` before Then 4) |

**The 8 round-1 survivors, re-run against the rev 3 files (targeted, `hand.py kill <ids>`).** All are now killed:

| Variant | Round 1 | Round 2 | Killed by |
|---|---|---|---|
| NR-create_invoice | survived | KILLED | C-02 |
| NR-update_invoice | survived | KILLED | U-03 |
| NR-revert_to_draft | survived | KILLED | V-02 |
| CB-delete-after-manager | survived | KILLED | D-16 |
| CB-resync-after-sync | survived | KILLED | S-29 |
| EM-http-only-rollback-void | survived | KILLED | X-26 |
| LG-void-po-unscoped | survived | KILLED | X-27 |
| LG-delete-po-unscoped | survived | KILLED | D-17 |

**Variants touching the changed cards:**
- **X-09:** NR-void_invoice, CB-void-after-manager, PW-void-after-reset and PW-void-after-unlink are all still killed by X-09. NR-delete_invoice is still killed by D-08 and NR-resync_items by S-06.
- **K-38:** L-K9b-ok passes. The new variant L-K9b-noread (sales order locked, approvers never read) now fails K-38, which closes the round-1 vacuous-`before` note. L-K9b-late and L-K9b-skip fail as intended.
- **K-31 and K-35:** under my BUG-2965-only reference fix, K-30…K-34 pass and K-35 still fails. That is now by design, because its marker needs BUG-1205 too. All four wrong fixes still fail their cards.

**Commands run (round 2):**
```
COVERAGE_FILE=<scratch>/.r2c1 pytest tests/unit/services/test_account_invoice_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.account_invoice_service --cov-branch --cov-report=term-missing → 98% (198, 399-400) · 106 passed, 43 xfailed
COVERAGE_FILE=<scratch>/.r2c2|.r2c3 pytest … -o addopts=""                              → 106 passed, 43 xfailed (×2)
pytest … -o addopts="" --runxfail -p thenmap (PYTHONPATH=<scratch>)                    → 43 failed, 106 passed; 43/43 on the named Then line
python <scratch>/hand.py kill <14 ids> r2   → 14/14 killed
python <scratch>/hand.py ref L-K9b,F-2965 r2 → as expected (K-35 needs BUG-1205 as well)
ruff check / ruff format --check            → clean
```

**Still open:** R2-1 (executor). The round-1 notes on freeze cards and BUG-1205 still stand.

## Round 3 — 2026-11-22

> **Verdict:** PASS
> Tests: 106 passed · 43 xfailed · coverage 98% branch (151 stmts, missed 198, 399–400; 0 partial) · Source commit e48a092 · Cases revision 3

- **R2-1 closed:** `test_ais_s_29__resync_commits_once` now matches its card. Then 1–3 check the result id, `cm.call_count == 1` and `rb.call_count == 0`. Then the test runs one `db.rollback()` and Then 4 checks the committed `len(LINES(db, vid)) == 1`.
- **Run:** `COVERAGE_FILE=<scratch>/.r3c1 pytest tests/unit/services/test_account_invoice_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.account_invoice_service --cov-branch --cov-report=term-missing` gives 106 passed, 43 xfailed, 98%.
- **Hand variant:** `hand.py kill CB-resync-after-sync r3` (a double commit in `resync_items`, on a temp copy) is KILLED by S-29.
- **Still open:** nothing for this module. The round-1 notes on the freeze cards (re-verify when the manager freeze lands) and on BUG-1205 (K-35) still stand as future-work notes.
