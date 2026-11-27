# Verification — `app/services/sales_service.py`

> **Verdict:** NEEDS WORK
> Tests: 217 passed · 130 xfailed (reproduced ✅; 129 strict + SS-A-07b non-strict) · coverage 99% branch (line 60 only, dead)
> Mutation: 297 mutants · 282 killed · 15 survived → score 97.9% (282 / 288, after excluding 0 equivalent, 2 dead, 7 bug-path)
> Source commit: e48a092 · Cases revision: 3

## Summary
The tests are faithful to the cards. Traceability is clean: 347 cards and 347 tests, and every marker matches. All 130 xfail tests fail on the card's "Fails today on" line. Mutation testing finds very little.

Two kinds of gap remain:
1. **TC3 missing rollback is not detected for 14 of the 17 write methods.** I removed each method's own `_rollback_transaction` in-process and the suite still passed. The `committed: x_gone` check runs after the test's own `db.rollback()`, so it proves nothing about the service. This is the same cross-cutting gap that `expense_order_service.verify.md` reported.
2. **Six survivors in the return paths.** RK4 adds to quantities that are already non-zero, and RC3 builds credit-note lines with a zero price or no name. No card covers either case.

Both gaps are for the case designer. No test is unfaithful, and no new app bug was found.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing (TC3) | Every `X (after the commit point)` + `committed: x_gone` card (I-10, I-13, DV-12, RS-13, RS-19, SR-31, SC-05 …) and every failing-commit card | A method that does not roll back goes unseen. `committed:` makes the test call `db.rollback()` before `x_gone`, and `rb.call_count >= 1` is satisfied by `BaseService._commit_transaction`'s own rollback. | Per-method strip (tc3audit `tc3method.py`, `-m "not xfail"`): 217 passed, nothing caught, for `create_invoice_for_sales_order`, `finalize_sales_order_invoice`, `create_sales_order_from_dict`, `update_sales_order`, `create_delivery`, `cancel_delivery`, `update_delivery`, `fulfill_service_item`, `complete_return`, `void_return`, `mark_order_complete`, `add_approver`, `remove_approver`, `set_approval`. Caught only where a flushed write is re-read before the test's rollback: `complete_delivery` (DV-12, DV-13), `start_return` (RS-13…16), `set_section_confirm` (SC-05, SC-08). | **case designer**: on one error card per write method, check X *before* any test-level rollback. A `session:` line straight after the raise, such as `db.get(Workspace, X_ID) is None`, would do. Alternatively, re-read a flushed write before rolling back. This is a Conventions-level change. |
| 2 | case-missing | RK4 (L980, L987) | No completion card starts from a line that already has `quantity_returned` / `quantity_refunded` > 0. Because `x or 0` is the same for 0.00, `+=` cannot be told from `=`. | Survivors L980 `or → and`, L987 `or → and` | **case designer**: complete a second refund return on a line with `quantity_returned 1.00`, `quantity_refunded 1.00`, and expect 2.00 / 2.00 |
| 3 | case-missing | RK4 (L985) | No card completes a return line whose order line shows `quantity_delivered 0.00`. That state is reachable only through invalid data or two returns over the same units. | Survivor L985 `0 → 1` in `(quantity_delivered or 0)` | **case designer**: add an invalid-data card (`quantity_delivered 0.00` → `-q`). If you rule the state unreachable, record that in the spec so the mutant can be classed equivalent. |
| 4 | case-missing | RC3 (L888, L889) | No return line has unit price 0.00. The spec calls only `None` unreachable, but a 0.00 price is valid (free item, or a `unit_price` given as 0 on the return). `0 or Decimal(1)` would price that line at 1. | Survivors L888 / L889 `0 → 1` | **case designer**: start a return of a 0.00-priced line; its credit-note line has `unit_price 0.00`, `line_subtotal 0.00`, amount 0.00 |
| 5 | case-missing | RC3 (L882) | The "`Item <item_id>` when empty" fallback for credit-note lines has no card. The A-03 twin exists only for the auto-draft. | Survivor L882 `'Item ' → ''` | **case designer**: an RS card with a free-text line whose description is empty |

None of these are fidelity findings. `pytest.raises(Exception)` and the RV-08 `try/except HTTPException: pass` are exactly what the cards say. The DD-08/DD-09 `sp.is_active` wording is known and not re-reported.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | 60 | `raise` → `pass` | dead | A1 `account_id is None` cannot happen: the column is NOT NULL, and the spec lists it as dead (Q9) | — |
| 2 | 62 | message → `''` | dead | Same block | — |
| 3 | 348 | `raise ValueError` → `pass` | bug-path | Unknown order. The exact cards (G-03/04/05, I-09, F-14, U-26, RS-17, RK-21, RL-02) are xfail BUG-3197 (404). The pass companions accept any exception. | — |
| 4 | 348 | `'Sales order '` → `''` | bug-path | Same; the text changes with BUG-3197 | — |
| 5 | 348 | `' not found'` → `''` | bug-path | Same | — |
| 6 | 785 | `'Delivery '` → `''` | bug-path | GV-02/03 are xfail BUG-3197 | — |
| 7 | 785 | `' not found'` → `''` | bug-path | Same | — |
| 8 | 882 | `'Item '` → `''` | case-missing | Finding 5 | case designer |
| 9 | 888 | `Decimal(0)` → `Decimal(1)` (unit_price) | case-missing | Finding 4 | case designer |
| 10 | 889 | `Decimal(0)` → `Decimal(1)` (subtotal) | case-missing | Finding 4 | case designer |
| 11 | 980 | `quantity_returned or 0` → `and` | case-missing | Finding 2 | case designer |
| 12 | 985 | `quantity_delivered or 0` → `or 1` | case-missing | Finding 3 | case designer |
| 13 | 987 | `quantity_refunded or 0` → `and` | case-missing | Finding 2 | case designer |
| 14 | 998 | `'Return '` → `''` (ledger note) | bug-path | The note is RK5a [BUG-3202]; only RK-06 (xfail) checks it | — |
| 15 | 998 | `' for SO-'` → `''` | bug-path | Same | — |

## Variant checks (coordinator list)
| Topic | Cards | Result |
|---|---|---|
| TC1/TC2 commit + re-read, TC4 failing commit, TC5 (C-04), TC6 read spies | per callable | present and faithful. TC3: Finding 1 |
| Error mapping | DV-11 (BUG-3198 ValueError→400), DV-12/13 (422 passes unchanged), DC/DX/DU ValueError→400, 11× BUG-3197, A-15/A-16 (404→422 / others pass) | faithful. The ValueError texts are bug-path (survivors 3–7) |
| HR-16 W0/W2 | 41 cards (A-04/05/09/10, DD-04/05, DV-09/10, F-11/15/16, PS-04/05, RS-08/16/19/20, RV-07/08, SR-15…19/38/39/41/43, U-27, Y-08 …) | faithful; foreign rows are snapshot-compared |
| Exact lock clauses | I-11, F-12 (BUG-3192), RK-16, RV-10 (BUG-2764): single-table, plain `FOR UPDATE$`, no `OF` / `SKIP LOCKED` / `NOWAIT`, as the spec's Row locks table says. SR-51 credit note locked before its payments are read; SR-52 locked in return id order | faithful; each xfail fails on Then 2. The sales spec has no order→return→credit-note lock order (that is PO RX1a) |
| OQ-64 / BUG-3217 SR1–SR9 | entry fields SR-01 (amount, method, UTC date, actor, `DEL-…` reference, notes); half-up SR-07 (0.13); partial redelivery settles nothing SR-08 (pass) and the last gap settles SR-09; cap SR-20…24 (already-refunded warning with two-place text, nothing written; a voided refund → full 3000.00); voided note SR-13/37/40/42; draft note SR-14; foreign note SR-15/16/38/39/41/43 (id-free `could not be found`, never locked); edit/delete refused SR-53…56; method refused SR-57/58; void SR-59; trail SR-44/45; link SR-48/49; 0.00 note SR-50 | all 59 cards faithful; the 36 xfail fail on the named Then line |
| BUG-2790 / 2791 restock | OR-04/05, RS-10 (order stays completed), RK-03 (no stock back for a directly fulfilled line), RK-04 pass companion | faithful |
| BUG-3192 finalize / create locks | I-11, F-12 | faithful |
| BUG-3218 id-free texts | F-15/16, RS-19/20 (`str(id) not in detail`), F-11/RS-16 pass companions | faithful |

## Traceability
Cases 347 · tests 347 (341 functions; U-18…21, SR-15/16, SR-17/18, SR-38/39 parametrized with the case ID as the param id). Unmatched: none. Marker mismatches: none. Every xfail reason names its BUG IDs, and every BUG ID exists in `bugs.md`. Every card Then line N has a `# Then N` block with an assertion, and the cards' literal values (Decimals, status codes, exact strings, `is True/False/None`) appear in the matching block (script check, 1154 Then lines). Mocks are only those the Conventions name. `ruff check` is clean.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/services/test_sales_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.sales_service --cov-branch --cov-report=term-missing
  app\services\sales_service.py  406 1 78 1  99%  60
  217 passed, 129 xfailed, 1 xpassed          (run 1: the xpass is SS-A-07b, non-strict by design)
.venv/Scripts/python.exe -m pytest tests/unit/services/test_sales_service.py -q -p no:cacheprovider -o addopts=""   ×2
  217 passed, 130 xfailed  /  217 passed, 130 xfailed
.venv/Scripts/python.exe -m pytest tests/unit/services/test_sales_service.py -q -p no:cacheprovider -o addopts="" --runxfail -rf [-p vthen]
  130 failed, 217 passed. Own plugin vthen.py: each failure's last line in the test sits in the card's "Fails today on" block: 130/130
TC3_SVC=sales_service TC3_METHOD=<m> PYTHONPATH=<tc3audit> pytest … -m "not xfail" -p tc3method   (17 methods; see Finding 1)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/sales_service.py tests/unit/services/test_sales_service.py --lines <r> --timeout 400 --json …
  10 shards (1-119 … 1026-1200), each on its own throwaway DB marker_ssv<N>_test (dropped afterwards); all 10 finished
  Mutants 297 · killed 282 · timeout 0 · survived 15
.venv/Scripts/python.exe -m ruff check tests/unit/services/test_sales_service.py   All checks passed!
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3v\sales\` (`mut_*.json/log`, `tc3/*.txt`, `vthen.json`, `trace.py`, `thencount.py`, `literals.py`).

## Notes for future work
- **Shared-DB contention (harness / executor).** No committed `statuses` row with id 10 exists in `marker_test`, so every test inserts one inside its own transaction. Parallel runs of this file, and any other suite that does the same, then queue on that primary key; `pg_stat_activity` showed eight sessions waiting on `INSERT INTO statuses (id …) VALUES (10 …)`. Mutation shards on the shared DB ran at about 10 min per mutant, so I re-ran them on private databases. Suggestion: seed status 10 once in the harness or migration, or have mutation runs default to a private DB.
- SR-15/16/17/18/38/39/41/43 count `invoice_payments` across all workspaces. A committed payment row left on the shared DB by any run would break them (the executor's notes say the same).
- Once BUG-3197 / BUG-3202 are fixed, survivors 3–7 and 14–15 should die. Re-run mutation then.

## Round 2 — 2026-11-22

> **Verdict:** PASS
> Tests: 219 passed · 133 xfailed (reproduced ✅; 132 strict + SS-A-07b non-strict) · coverage 99% branch (line 60, dead)
> Mutation (targeted re-run of the round-1 case-missing lines): 16 mutants · 15 killed · 1 survived (L985, equivalent per spec RK4a / G19). Whole file: 297 mutants → 287 killed, 10 excluded (2 dead, 7 bug-path, 1 equivalent) → score 100%
> Source commit: e48a092 · Cases revision: 4a (tests) / 4b (wording only, DISCREPANCY-5)

### Summary
All five round-1 findings are closed.
- **TC3 rollback:** with each method's own rollback removed in-process, every one of the 17 write methods now fails at least one test. The new **X not in db** check runs right after the raise, and the spy cards check `rb.call_count >= 1`.
- **RK4 / RC3 survivors:** RK-22 kills L980 and L987; RS-24 kills L888 and L889; RS-25 and RS-26 kill L882.
- **L985:** survives, but is now equivalent. RK4a says a line's delivered quantity is always at least its pending returned quantity, so `quantity_delivered` cannot be 0.00 when a pending return line is completed (SS-RK-23 retired).

No unfaithful tests. No new bug: BUG-3220 already exists in `bugs.md`.

### Findings
None. The DD-08/09 / SR-53…58 savepoint wording (DISCREPANCY-5, cases Rev 4b) is known and not a finding.

### Checks
- **Traceability:** 352 cards and 352 tests; no unmatched IDs; markers all match. SS-RK-23 is gone from the cards (Retired IDs only) and from the tests. A-03, RS-26 and RS-27 are `xfail(strict=True)` with reasons naming BUG-3220, and BUG-3220 exists in `bugs.md` (`blank-display-name-no-fallback`).
- **Fidelity of new and changed tests vs Rev 4/4a:**
  - A-03 (`Line 1`), RK-22 (1.00 → 2.00 / 2.00, delivered 2.00, no stock), RS-24 (0.00 line, 3000.00 line, amount), RS-25 (`Item <I3.id>`, unit, subtotal), RS-26 (`Line 1`, no "None"), RS-27 (trimmed `Crate`; spaces → `Line <n>`, keyed by `source_order_item_id`): every Then item is asserted exactly.
  - Script check over all 31 **X not in db** cards: the assertion sits in the named Then block, with no re-read or test rollback before it.
  - All 17 spy cards (I-06, F-02, C-03, U-27, DC-02, DV-08, DX-04, DU-04, FS-03, RS-07, RK-12, RV-04, MC-03, SC-05, AA-02, AR-02, AP-02) run inside `spies(db)` and assert `rb.call_count >= 1`.
  - Then-block, assertion and literal checks across 1215 Then lines are clean, and ruff is clean.
- **Runs:** 3 plain runs gave `219 passed, 132 xfailed, 1 xpassed` (with coverage), `219 passed, 132 xfailed, 1 xpassed`, and `219 passed, 133 xfailed`. The xpass is SS-A-07b, which is non-strict by design; a strict xpass would have failed the run. `--runxfail` gave 133 failed / 219 passed, and my `vthen` plugin confirms 133 of 133 fail inside the card's "Fails today on" block.
- **TC3 per-method strip** (tc3audit `tc3method.py`, `-m "not xfail"`), test(s) that catch it:

| Method | Caught by |
|---|---|
| `create_invoice_for_sales_order` | I-06, I-10, I-13 |
| `finalize_sales_order_invoice` | F-02 |
| `create_sales_order_from_dict` | C-03 |
| `update_sales_order` | U-27 |
| `create_delivery` | DC-02 |
| `complete_delivery` | DV-08, DV-12, DV-13 |
| `cancel_delivery` | DX-02, DX-04 |
| `update_delivery` | DU-02, DU-04 |
| `fulfill_service_item` | FS-03 |
| `start_return` | RS-07, RS-13…16 |
| `complete_return` | RK-12, RK-17 |
| `void_return` | RV-04, RV-11 |
| `mark_order_complete` | MC-03 |
| `set_section_confirm` | SC-05, SC-08 |
| `add_approver` | AA-02 |
| `remove_approver` | AR-02 |
| `set_approval` | AP-02 |

- **Mutation:** `mutate.py … --lines 882-882 | 888-889 | 980-980 | 985-985 | 987-987`, each shard on its own throwaway DB (`marker_ssv21…25_test`, dropped afterwards); all five shards finished. Only L985 `0 → 1` survives. The rest of the file was not re-run (the source is unchanged, and the tests only gained cards and checks).
- Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3v\sales\r2\`.
