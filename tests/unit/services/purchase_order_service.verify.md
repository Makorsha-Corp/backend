# Verification — `app/services/purchase_order_service.py`

> **Verdict:** NEEDS WORK
> Tests: 293 passed · 121 xfailed (reproduced ✅, 3 runs + coverage run, no XPASS) · coverage 99% branch (692 stmts, 192 branches; missed 382–383, 1312–1313, 1482 — as the notes say)
> Mutation: 646 mutants · 579 killed · 67 survived → score 92% (579 / 629, after excluding 12 equivalent, 3 dead, 2 bug-path; 50 case-missing)
> Source commit: e48a092 · Cases revision: 3

## Summary
The tests match their cards. Traceability is clean: 414 cards and 414 tests, every marker right, every bug ID in `bugs.md`. Every xfail fails on its card's named line. The lock, settlement (RX8a–m), HR-16 and error-mapping tests are faithful. Two gaps sit in the **cards**, not the tests:
1. **TC3 is not actually tested.** I removed the service's own rollback from one write method at a time, in-process. For 14 of the 17 write methods every test still passes. 30 TC3 cards check `x_gone` with a "committed:" line, so the test's own `db.rollback()` runs first and removes X whatever the service did. `_commit_transaction` already rolls back on a failing commit, so the TC4 cards cannot see it either. C-09 shows the right pattern: check in the same session, before any test-level rollback.
2. **50 surviving mutants are behaviour the cards never check.** These are boundaries and branches of the error mapper (IE1–IE4), signature defaults, the receive milestone, AO machine and component scopes, and held-today event texts. Those texts are checked only inside strict-xfail cards (DD-04, V-02), and `mutate.py` does not run xfail tests.

Nothing needs the executor or the describer. No new bug: the code is right, and the cards do not prove it.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing (TC3) | C-06, C-07, U-02, U-09, U-10, MC-02, RE-20, SR-06, SR-12, CR-07, CR-12, VR-05, X-02, AI-04, AI-05, UI-03, RI-03, SY-08, AA-03, RA-02, SA-02, V-05, V-10, CI-02, CI-05, RX-24, RX-29 (and the other "committed: x_gone" cards) | The "committed: x_gone" check runs after the test's own `db.rollback()` (Conventions: a "committed:" line rolls back first), so it holds even when the service never rolls back. TC3 (every pending change discarded on an error) is not observable. | Rollback-strip experiment (`tc3method.py`, one method at a time). **Undetected** (293 passed, 121 xfailed): `create_purchase_order`, `update_purchase_order`, `mark_order_complete`, `create_receive_event`, `start_return`, `complete_return`, `void_return`, `delete_purchase_order`, `add_item`, `update_item`, `add_approver`, `remove_approver`, `set_approval`, `void_purchase_order`. Detected only through `rb` spies: `remove_item` (RI-05), `sync_items` (SY-04, SY-10, SY-11, SY-13), `create_invoice_for_purchase_order` (CI-09). | **case designer**: on each error-path TC3 card check X in the same session **before** any test-level rollback, as C-09 does (`db.expire_all()`; `db.get(Workspace, X_ID) is None`). Or add a `rb.call_count >= 1` spy on one non-commit error path per write method. |
| 2 | case-missing (held-today checks only in xfail cards) | DD-04 Then 5, V-02 Then 1–3 | The `invoice_draft_deleted` description, the `invoice_voided` description and `changes` list, and the `po_voided` description and metadata hold today. They are checked only inside strict-xfail cards (BUG-3185), which the mutation run skips, so no passing card protects them. | Survivors L195 ×2, L1432–L1439 ×9, L1452 ×2, L1454 | **case designer**: add pass companions for the held-today parts; keep only the `invoice_id` metadata in the xfail cards. |
| 3 | wording (minor) | RX-47, RX-49 "Fails today on" | The card says the Given raises AttributeError. It actually raises ImportError: `RQ(...)` is evaluated as an argument before `svc.receive_replacements` is looked up. The xfail is still honest: it fails before any Then, on the missing new names. RX-44 and RX-62 already say "ImportError or AttributeError". | `--runxfail`: `ImportError: cannot import name 'PurchaseOrderReturnReplacementCreate'` at L8663, L8714 | **case designer** (wording only) |

All other surviving mutants are case-missing items, listed below (designer).

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | 79 | default `phase='items'` → `''` | equivalent | `phase` is only compared with `'invoice'` and printed in a log line; `''` acts like `'items'` | — |
| 2 | 85 | `f'{err} {orig_err}'` space → `''` | equivalent | `str(IntegrityError)` already contains `str(orig)`, and the join of the sqlalche.me URL tail and the message forms no keyword | — |
| 3 | 88 | `pgcode == '23514'` → `''` | case-missing | IE1: every check card's text also says "check constraint"; no card sends pgcode 23514 alone | case designer |
| 4–6 | 92 | `and`→`or`; `'ordered'`→`''`; `'received'`→`''` | case-missing | IE1 "both ordered and received": no check-violation text that contains only one of the two words | case designer |
| 7 | 108 | `pgcode == '23505'` → `''` | case-missing | IE2: every unique card's text also contains "duplicate" or "unique constraint" | case designer |
| 8 | 119 | `pgcode == '23502'` → `''` | case-missing | IE3: every not-null card's text also contains "null value" | case designer |
| 9 | 120 | `'financial_audit_logs'` → `''` | case-missing | IE3: no not-null card on `financial_audit_logs` in the items phase | case designer |
| 10 | 121 | `table and column` → `or` | case-missing | IE3 `{loc}` in the invoice branch with only one of table/column known | case designer |
| 11 | 138 | `'account_invoices'` → `''` (FK tables) | case-missing | IE4: no FK card on `account_invoices` in the items phase (IE-16 uses `financial_audit_logs`) | case designer |
| 12–13 | 195 | `'Draft invoice #'`, `' deleted'` → `''` | case-missing | DD2 description is checked only in DD-04 (xfail BUG-3185), see Finding 2 | case designer |
| 14 | 292 | reset reason `'Draft invoice changed after order update'` → `''` | case-missing | SD10 names the reason; no card checks where it lands | case designer |
| 15 | 297 | notification `entity_type 'purchase_order'` → `''` | case-missing | SD10 card checks `(recipient, type)` only; Overview says `entity_type = "purchase_order"` | case designer |
| 16 | 377:19 | `'po_number'` → `''` | equivalent | When reached, the condition is always true: the loop at 374 re-raises every other error | — |
| 17 | 377:41 | `'uq_po_workspace_number'` → `''` | equivalent | same argument (`'' in err` is true) | — |
| 18 | 377:41 | `in` → `not in` | case-missing | C rule: five collisions whose text names only `uq_po_workspace_number` → 409. The exhaustion card uses `po_number` text only | case designer |
| 19–21 | 382, 383, 385 | raise → pass; 500 text | dead | spec "Not specified": lines 382–386 dead (Q7) | — |
| 22 | 400:57 | `exclude_unset=False` | equivalent | every `PurchaseOrderUpdate` field defaults to `None`, so `exclude_none=True` drops the same keys | — |
| 23 | 400:76 | `exclude_none=False` | case-missing | U2 "fields sent and not null": no card sends a field as explicit `null` and expects no unconfirm | case designer |
| 24–25 | 521, 522 | default `skip 0→1`, `limit 50→51` | case-missing | the PG signature defaults are in the spec header; no card calls the page without `skip` / `limit` | case designer |
| 26–29 | 532, 533, 577, 578 | default `exclude_complete` / `exclude_voided` `False→True` (page, hub stats) | case-missing | no card relies on the defaults (complete / voided orders included when the flags are left out) | case designer |
| 30 | 682 | FINALIZE raise → pass | equivalent | falls through to line 684: `get_by_id_and_workspace(id=None)` is None and raises the identical 400 FINALIZE | — |
| 31 | 737 | dest label `'inventory'` → `''` | equivalent | unreachable: `lines_posted > 0` only for storage or machine (RE8: a project moves no stock) | — |
| 32–35 | 779 | `+`→`-`; `received or 0`→`or 1`; `refunded or 0` `or`→`and`; `refunded or 0`→`or 1` | case-missing | the RE "fully received" milestone has no card where refunded quantity completes a line, or where a line is exactly one unit short (or at 0 with ordered 1) | case designer |
| 36–37 | 887, 888 | `unit_price or Decimal(0)` → `Decimal(1)` | case-missing | credit-note lines from a return line priced 0 (or NULL) | case designer |
| 38 | 907 | `> 0` → `> 1` | case-missing | SR2 boundary: a line with 1 (or 0.5) received may be returned | case designer |
| 39 | 979 | `quantity_returned or 0` `or`→`and` | case-missing | CR: complete a return on a line that already has a returned quantity (adds to it, does not replace it) | case designer |
| 40 | 984 | `quantity_received or 0` → `or 1` | case-missing | CR on a line whose received was corrected to 0 after the return started | case designer |
| 41 | 986 | `quantity_refunded or 0` `or`→`and` | case-missing | CR refund on a line that already has a refunded quantity | case designer |
| 42–43 | 1087 | machine scope `dest_type` / `loc_type` `'machine'` → `''` | case-missing | AO machine scope: no card lists a machine-destination PO or a transfer touching the machine (AO-18 / AO-19 list work orders only) | case designer |
| 44 | 1098 | component scope `'project'` → `''` | case-missing | AO component scope: no card lists a project-destination PO for the component | case designer |
| 45 | 1126 | `len(seq) > 0` → `> 1` | case-missing | AO: a one-stage workflow (its only stage is the last one) is skipped | case designer |
| 46 | 1173 | `limit=1000` → `1001` | bug-path | AO-19, BUG-3166 (strict xfail) | — |
| 47 | 1294 | `phase='items'` → `''` | equivalent | as #1 | — |
| 48 | 1300 | `except Exception: raise` → pass (sync_items line phase) | case-missing | SY: a non-HTTP, non-Integrity error in the line phase is rolled back and re-raised (SY-13 covers only the invoice step) | case designer |
| 49 | 1313 | raise → pass | bug-path | reachable only once BUG-639 turns SY-04's refusal into an HTTPException (notes, coverage gaps) | — |
| 50 | 1401 | `reversed_count > 0` → `> 1` | case-missing | V: void with exactly one reversed posting logs `inventory_reversed` (V-20 reverses 2) | case designer |
| 51 | 1428 | reset reason `'Cleared approvals — PO voided'` → `''` | case-missing | no card checks the void's approval-reset reason | case designer |
| 52–60 | 1432–1439 | `invoice_voided` description and `changes` keys/values → `''` | case-missing | only in V-02 (xfail BUG-3185), see Finding 2 | case designer |
| 61–63 | 1452, 1454 | `po_voided` description / metadata key → `''` | case-missing | only in V-02 Then 3 (xfail), see Finding 2 | case designer |
| 64–65 | 1472 | `if` negated; `is`→`is not` | equivalent | `db.refresh(po)` just loaded every column; the re-get returns the same identity-map instance with the same values either way | — |
| 66–67 | 1482, 1484 | raise → pass; text → `''` | equivalent | unreachable: after a forced sync with a supplier, the order has an invoice or the sync raised (FORCE422 / SUPP422 / SD8). Not on the spec's dead list; the describer may add it to "Not specified" | — |

## Variant checks (coordinator list)
- **TC1–TC6:** TC1/TC2 commit cards re-read after a test-level rollback (`committed:`). TC4 failing-commit cards are fine, but they cannot see a missing service rollback, because `BaseService._commit_transaction` rolls back itself. TC5 is C-11. TC6 reads check no commit, no rollback, `X in db` and `not db.new`. **TC3: see Finding 1.**
- **Error mapping (IE-01 … IE-23):** I checked the tests text by text against the cards (exact detail, status, `__cause__ is err`, caplog). The gaps are in the cards (survivors #3–#11).
- **HR-16 W0/W2:** 17 cards build W0 rows and 34 build W2 rows, and every test builds them as the card says (script). RX-50, RX-51, RX-55 and RX-61 check that the foreign credit notes, lines and ledger are untouched, and that NOTFOUND is an exact string with no id.
- **Exact lock clauses:** `exact_lock_of` needs the statement to end with `FOR UPDATE OF purchase_orders` and to have no NOWAIT or SKIP LOCKED. `exact_lock` needs a trailing `FOR UPDATE` and no `OF`. The order read joins only `statuses`, so `lock("account_invoices")` cannot match the order read. **RX-63** checks the lock order order → return → credit note with `locked_before` on both pairs, plus the order before the items. RE-05, V-06 and CI-03 (BUG-3162) fail on Then 2, as their cards say.
- **OQ-63 / BUG-3176 RX8a–m:** all faithful:
  - Entry fields (RX-30): method, amount, `TODAY_UTC`, U2, W1, CN, and `WARN == []`.
  - Half-up rounding (RX-33): the expected 0.26 rules out both half-even (0.24) and rounding after the sum (0.25).
  - Return-line price (RX-32); partial receipt and its remainder (RX-36, RX-37).
  - Cap at outstanding (RX-38, and RX-39 at 0.01).
  - No entry: NOSETTLE (RX-40); VOIDW for a voided or draft credit note (RX-41, RX-53); NOTFOUND for a foreign or missing one (RX-51, RX-54, RX-55). All are exact-equality warnings, so no id can appear, and the credit note is `unchanged`.
  - Refusals: delete and edit refused with NODEL (RX-45 … RX-47); the API refuses the method on create and update with MANUAL (RX-56, RX-57). The pass companions RX-48 and RX-58 hold today.
- **BUG-2734** (V-07, V-08), **BUG-3162** (RE-05, V-06, CI-03), **BUG-3171** (RE-18) and **BUG-3181** (RX-26) are faithful and each fails on its card's named Then line.

## Traceability
cases 414 · tests 414 (HF-03 … HF-06 as `pytest.param` ids) · unmatched: none · duplicates: none · marker mismatches: none (293 pass without marker; 119 `xfail(strict=True)`, 2 `strict=False` = LR-03, BR-05 as the cards say; every reason names its card's BUG ids; every id exists in `docs/testing/bugs.md`) · `# Then N` numbering matches every card's Then list; no Then block without an assertion · patches: 17, each one prescribed by its card (SD-10, SD-16, SD-17, C-03, C-05 … C-07, U-10, AI-05, UI-05, RI-05, SY-10 … SY-13, CI-09, CI-10), plus `utcnow` and the `db` spies · no `try/except`, no `pytest.raises(Exception)` · ruff clean.

`--runxfail`: 121 failed, 293 passed. My checker maps each failing frame inside the test function to its `# Then N` block and compares it with the card's "Fails today on". 117 match the named Then line or the Given/When. RX-44 and RX-62 match the card's "ImportError or AttributeError". RX-47 and RX-49 fail in the Given with ImportError, where the card says AttributeError (Finding 3).

Not reproduced: the executor's reference plugin run (414 passed on `marker_poref_test`). Running it would mean running a script I did not write, which this stage may not do.

## Commands run
```
COVERAGE_FILE=…/svc3v/po/.coverage .venv/Scripts/python.exe -m pytest tests/unit/services/test_purchase_order_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.purchase_order_service --cov-branch --cov-report=term-missing
  → 293 passed, 121 xfailed, 38 warnings in 78.83s · 692 stmts, 5 miss, 192 branches, 3 partial, 99% (382-383, 1312-1313, 1482)
… -q -p no:cacheprovider -o addopts="" -rxX   (run 2) → 293 passed, 121 xfailed, 23 warnings in 55.39s
… -q -p no:cacheprovider -o addopts="" -rxX   (run 3) → 293 passed, 121 xfailed, 23 warnings in 77.92s
… -q -p no:cacheprovider -o addopts="" --runxfail -rf --tb=short → 121 failed, 293 passed, 23 warnings in 55.44s
.venv/Scripts/python.exe -m ruff check tests/unit/services/test_purchase_order_service.py → All checks passed!
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/purchase_order_service.py tests/unit/services/test_purchase_order_service.py --lines <range> --timeout 400 --json …/svc3v/po/mut_<i>.json
  12 parallel shards (1-109, 110-149, 150-254, 255-377, 378-605, 606-699, 700-784, 785-934, 935-1042, 1043-1169, 1170-1389, 1390-1505); each its own mkdtemp copy; all 12 finished
  → 646 mutants · 579 killed · 0 timeout · 67 survived
TC3 per method (17 runs): TC3_SVC=purchase_order_service TC3_METHOD=<m> PYTHONPATH=…/tc3audit pytest … -p tc3method
  → 14 methods 293 passed / 121 xfailed (undetected); remove_item 1 failed (RI-05); sync_items 4 failed (SY-04, SY-10, SY-11, SY-13); create_invoice_for_purchase_order 1 failed (CI-09)
```
Scratch (scripts, logs, JSON): `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3v\po\`.

## Round 2 — 2026-11-22

> **Verdict:** PASS
> Tests: 321 passed · 123 xfailed (reproduced ✅; 3 runs, one with coverage; no flaky outcome) · coverage 99% branch (692 stmts, 192 branches; missed 382–383, 1312–1313, 1482, unchanged)
> Mutation (targeted, source unchanged at e48a092, same line numbers): the 50 round-1 case-missing survivors, which include the 14 held-today ones that were checked only in xfail cards → **49 killed**, 1 reclassified as bug-path. Whole file: 646 mutants · 628 killed · 18 excluded (12 equivalent, 3 dead, 3 bug-path) → score **100%**
> Cases revision: 4a · Tests: 444

### What was checked
- **Traceability (whole file):** 444 cards and 444 tests; no unmatched or duplicate IDs; 0 marker problems. That is 321 tests without a marker, 121 `xfail(strict=True)` and 2 `strict=False` (LR-03, BR-05). Every reason names its card's BUG ids, and every id exists in `bugs.md`, including BUG-3186 (line 1059). `# Then N` numbering matches every card, and no Then block lacks an assertion. All patches are prescribed by their cards. HR-16: 17 W0 cards and 34 W2 cards, all built. Ruff is clean.
- **Fidelity of new and changed tests, each read against its Rev 4/4a card:**
  - **The 31 TC3 cards** (the 30 listed plus SY-14) all assert `X not in db` before any test-level rollback (script check).
  - **The 19 spy cards** (C-07, U-09, MC-02, RE-20, SR-06, CR-07, VR-05, X-02, AI-04, UI-03, RI-05, SY-10, AA-03, RA-02, SA-02, V-05, CI-05, CI-09, RX-24) all run inside `spies` and assert `rb.call_count >= 1`. C-07 and VR-05 were read line by line.
  - **New and rewritten cards read line by line** were all faithful:
    - IE-24 to IE-32;
    - C-12, U-12, PG-08, PG-09, HS-06;
    - RE-43 to RE-45, AR-08, SR-15;
    - CR-17 to CR-20;
    - AO-23 to AO-25, SY-14, V-22, SD-13;
    - DD-04 and V-02 (cut down to the BUG-3185 `invoice_id` part), and their pass companions DD-06 and V-21.
  - **V-22** re-dates its Given posting to T0. That is the executor's documented BUG-664 guard (notes; same as V-20); it does not weaken the test.
  - **RX-47 and RX-49:** the "Fails today on" wording is fixed (Given 2, ImportError), so round-1 Finding 3 is closed.
- **`--runxfail`:** 122 failed, 322 passed. The one that passed is BR-05, which is non-strict: tie order, passing by chance as documented. Each of the 122 failures falls on its card's named Then line or in the Given/When. RX-44 and RX-62 fail with ImportError in the When, which their cards allow ("ImportError or AttributeError").
- **TC3 strip** (`tc3method.py`) on the 14 methods that went undetected in round 1: each one now fails at least one test.

  | Method | Tests that fail when its rollback is stripped |
  |---|---|
  | create_purchase_order | C-06, C-07 |
  | update_purchase_order | U-02, U-09, U-10 |
  | mark_order_complete | MC-02 |
  | create_receive_event | RE-20 |
  | start_return | SR-06, SR-12 |
  | complete_return | CR-07, CR-12 |
  | void_return | VR-05 |
  | delete_purchase_order | X-02 |
  | add_item | AI-04, AI-05 |
  | update_item | UI-03 |
  | add_approver | AA-03 |
  | remove_approver | RA-02 |
  | set_approval | SA-02 |
  | void_purchase_order | V-05 |

  Together with round 1 (RI-05, SY-04/10/11/13, CI-09), all 17 write methods are covered. Round-1 Finding 1 is closed.
- **Round-1 Finding 2 (held-today checks only in xfail cards)** is closed: L195, L1428, L1432–L1439, L1452 and L1454 are all killed by DD-06, V-21 and SD-13.

### Remaining survivors in the targeted ranges (165 mutants, 158 killed)
| Line | Mutation | Class | Why |
|---|---|---|---|
| 79, 1294 | `phase='items'` → `''` | equivalent | as round 1, #1 and #47 |
| 85 | join space → `''` | equivalent | as round 1, #2 |
| 377:19, 377:41 | `'po_number'` / `'uq_…'` → `''` | equivalent | as round 1, #16 and #17 (377:41 `in`→`not in` is now killed by C-12) |
| 400:57 | `exclude_unset=False` | equivalent | as round 1, #22 |
| 984:85 | `quantity_received or 0` → `or 1` | **bug-path** (was case-missing) | Fires only when a line has 0 received at completion. That is the CR3a / BUG-3186 path, which only the strict xfails CR-18 and CR-19 reach; CR-20 starts at 4 received. After the fix, that state is refused before line 984. |

### Findings
None.

### Commands run (round 2)
```
… pytest tests/unit/services/test_purchase_order_service.py -q -p no:cacheprovider -o addopts="" -rxX --cov=app.services.purchase_order_service --cov-branch --cov-report=term-missing
  → 321 passed, 123 xfailed, 41 warnings in 103.49s · 99% (382-383, 1312-1313, 1482)
… (run 2) → 321 passed, 123 xfailed in 56.68s · (run 3) → 321 passed, 123 xfailed in 51.84s
… --runxfail -rf --tb=short → 122 failed, 322 passed in 49.64s (BR-05 non-strict passed)
mutate.py … --lines {79-92, 108-121, 138-138, 195-195, 292-297, 377-377, 400-400, 521-533, 577-578, 779-779, 887-907, 979-986, 1087-1126, 1294-1300, 1401-1401, 1428-1454} --timeout 400 (16 parallel shards, all finished)
  → 165 mutants · 158 killed · 7 survived (the 6 known equivalents + L984:85)
tc3method strip × 14 methods → each 1–3 failed (table above)
ruff check → All checks passed!
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3v\po\r2\`.
