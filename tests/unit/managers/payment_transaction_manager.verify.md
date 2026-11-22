# Verification — `app/managers/payment_transaction_manager.py`

> **Current verdict: PASS** (round 3, 2026-10-31, revision 5, 172 cases; lighter than an independent round). See "Round 3" at the end. The rest of this block is round 1.

> **Round 1 verdict:** NEEDS WORK
> Tests: 101 passed · 64 xfailed (reproduced ✅) · coverage 100% branch (132 stmts, 34 branches)
> Mutation: 166 mutants · 157 killed · 9 survived → score 98.1% (157/160, after excluding 0 equivalent, 0 dead, 6 bug-path)
> Source commit: e48a092 · Cases revision: 3

## Summary
The tests can mostly be trusted. Traceability is clean: all 165 cases map 1:1 to tests. Every test matches its case, with no weakened assertions, extra mocks or swallowed errors. The runs reproduce the notes exactly and are stable across 3 runs. Every xfail fails because of its own bug.
6 of the 9 surviving mutants are on bug-tagged paths (BUG-019 refusal/502, BUG-023 mismatch status/type), so they are expected.
The other 3 survivors show a real gap. No case checks that `_apply_validation_result` **returns the transaction** on the three `VALIDATED_FAILED` outcomes (status failure, amount mismatch, currency mismatch). Replacing those `return txn` with `return None` goes unnoticed. `finalize_from_gateway` then returns `None` to the service. The case designer must add return-value checks.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `_apply_validation_result` R4 / L149 (AVR-12, FIN-25) | The spec says the helper "Returns: The same `txn` object", and `finalize_from_gateway` returns that value to the service. No case asserts the return value on the R4 (status ≠ VALID) path. | Mutant #27 `return txn` → `return None` at L149 survived | case designer |
| 2 | case-missing | `_apply_validation_result` R5 / L158 (AVR-17, REC-11) | Same gap on the amount-mismatch path. | Mutant #29 L158 `return None` survived | case designer |
| 3 | case-missing | `_apply_validation_result` R7 / L167 (AVR-21) | Same gap on the currency-mismatch path. | Mutant #31 L167 `return None` survived | case designer |

Only AVR-01 (R10), AVR-32 (R1), FIN-01 (success) and FIN-07/FIN-13 (duplicate) assert `returns T`. Suggested fix: add "returns the same object (`is T`)" to AVR-12, AVR-17 and AVR-21. Also add "returns T" to FIN-25, so the public `finalize_from_gateway` contract is checked on a failure outcome.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 23 | 86 | `raise HTTPException(502…)` → `pass` | bug-path | A refused session start is `initiate_payment` R3 [BUG-019], a whole-tagged rule. Only the xfail cases INIT-09..12 and INIT-15 reach this branch, and xfail cases are excluded from the run. | — |
| 158 | 88 | 502 detail prefix `'SSLCommerz session i…'` → `''` | bug-path | Today's 502 message is the BUG-019 behavior that the spec replaces. No untagged rule covers it. | — |
| 165 | 88 | `failed_reason or 'unknown error'` → `and` | bug-path | Same 502 detail string (BUG-019). The intended `unknown error` fallback is tested by the xfail cases INIT-10 and INIT-11. | — |
| 166 | 88 | `'unknown error'` → `''` | bug-path | Same as #165 (BUG-019). | — |
| 57 | 125 | `'VALIDATED_FAILED'` → `''` (tran_id mismatch status) | bug-path | The status after a tran_id mismatch belongs to R1a [BUG-023], which says the status should stay unchanged. The untagged R1 cases (AVR-32..35, FIN-26, REC-26) deliberately assert only "not in {VALIDATED_SUCCESS, RISK_HOLD}". | — |
| 78 | 128 | `'validated_failed'` → `''` (mismatch event type) | bug-path | The event type is `validation_rejected` under R1a [BUG-023]. The untagged R1 cases deliberately do not assert the type. | — |
| 27 | 149 | `return txn` → `return None` | case-missing | See Finding 1 | case designer |
| 29 | 158 | `return txn` → `return None` | case-missing | See Finding 2 | case designer |
| 31 | 167 | `return txn` → `return None` | case-missing | See Finding 3 | case designer |

## Traceability
cases 165 · tests 165 · unmatched: none · duplicate IDs: none · tests without a case ID: none.
Marker mismatches: none. Every `pass` case has no marker. Every `xfail BUG-NNN` case has `xfail(strict=True)` whose reason names each listed BUG ID. All 14 BUG IDs used (BUG-019..BUG-032) exist in `docs/testing/bugs.md`.
Informational: the reasons for AVR-41 and AVR-43 also name BUG-023, and the reason for REC-14 also names BUG-025. This is a superset of the Expect column. It matches the cases file's "(needs BUG-0xx too)" notes, so it is not a finding.

Fidelity: all 165 tests were read against their Given/When/Then. There is no missing, weakened or changed assertion. There is no wrong setup, no in-memory-only write check and no swallowed failure. Only the three patch targets allowed by the spec (`utcnow`, `get_sslcommerz_client`, `secrets.token_hex`) are mocked, plus the REC-07 race side effect from the cases file. The session and the DAOs are never mocked.
xfail honesty (`--runxfail`): all 64 fail because of their own bug. Most fail on the exact "fails today on" assertion:
- INIT-09..12 and INIT-15 fail on the 502 at L86.
- INIT-18, 19 and 23 fail with DID NOT RAISE.
- The BUG-026 insert cases fail with a TypeError on `outcome_verified`, and the BUG-026 read cases with an AttributeError.
- RR-08 fails on the FOR UPDATE check.
- REC-09 fails on `call(..., val_id_hint=None) != call(A26)`.
- REC-21, 22, 28 and 29 fail on the propagated error or DataError.

FIN-15, FIN-19 and FIN-21 fail one assertion earlier (`validate` called 0 times), from the same root cause. The notes already record this.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_payment_transaction_manager.py -q -p no:cacheprovider --cov=app.managers.payment_transaction_manager --cov-branch --cov-report=term-missing
  app\managers\payment_transaction_manager.py  132  0  34  0  100%
  101 passed, 64 xfailed, 15 warnings in 15.87s

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_payment_transaction_manager.py -q -p no:cacheprovider --runxfail -rf
  64 failed, 101 passed in 7.24s   (failed set == the 64 xfail cases; reasons checked with --tb=line)

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_payment_transaction_manager.py -q -p no:cacheprovider   (repeat 2)
  101 passed, 64 xfailed in 7.42s
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_payment_transaction_manager.py -q -p no:cacheprovider   (repeat 3)
  101 passed, 64 xfailed in 7.79s

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/payment_transaction_manager.py tests/unit/managers/test_payment_transaction_manager.py --json <scratch>/mut_payment.json
  (pre-run by caller; results reused) 166 mutants · 157 killed · 9 survived · raw score 94.6%

Traceability: AST/regex script over cases.md, test file and bugs.md: 0 mismatches.
```

## Round 2 — 2026-10-31 (cases revision 4, narrow)

> **Verdict:** PASS
> Tests: 101 passed · 64 xfailed (reproduced ✅) · coverage 100% branch (132 statements, 34 branches)
> Mutation: 166 mutants · 160 killed · 6 survived → score 100% (160/160, after excluding 0 equivalent, 0 dead, 6 bug-path)
> Source commit: e48a092 · Cases revision: 4

### Summary
Findings 1–3 are closed and mutants #27, #29 and #31 are killed. **No card was added in this round.** Cases revision 4 had already done what round 1 suggested, by adding the return check to AVR-12, AVR-17, AVR-21 and FIN-25 (round 1 reports revision 3). The fix belonged in those existing cards, so the cases file, its Counts, Revision and matrix are unchanged at 165 cases (101 pass, 64 xfail). No finding needed a spec change or touched money behaviour: the gap was in the tests, and `app/` was not read for expected values.

**How much this round is worth.** It is lighter than an independent round. One agent did all of it: it decided that no card was missing, made the comment edits and checked the result. It added no cards, so it did not check cards of its own. The cards it relies on came from earlier sessions (revision 4) and no independent verifier has audited them. It read only the tests named under Fidelity against their cards, not every test as round 1 did.

### Findings
None.

| Round 1 finding | Now |
|---|---|
| 1 — `_apply_validation_result` R4, return value on status failure | Closed by AVR-12 (`ret is t`) and FIN-25 (`ret is t2`). Mutant #27 L149 KILLED. |
| 2 — R5, amount mismatch | Closed by AVR-17. Mutant #29 L158 KILLED. |
| 3 — R7, currency mismatch | Closed by AVR-21. Mutant #31 L167 KILLED. |

### Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 23 | 86 | `raise HTTPException(502…)` → `pass` | bug-path | BUG-019, as in round 1. | — |
| 158 | 88 | 502 detail prefix → `''` | bug-path | BUG-019. | — |
| 165 | 88 | `failed_reason or 'unknown error'` → `and` | bug-path | BUG-019. | — |
| 166 | 88 | `'unknown error'` → `''` | bug-path | BUG-019. | — |
| 57 | 125 | `'VALIDATED_FAILED'` → `''` | bug-path | BUG-023. | — |
| 78 | 128 | `'validated_failed'` → `''` | bug-path | BUG-023. | — |

These six stay alive until BUG-019 and BUG-023 are fixed. They are money paths, but nothing was decided about them here: both bugs are already recorded and their intended behaviour is in the spec.

### Fidelity (partial)
Read against their cards: AVR-12, AVR-17, AVR-21, FIN-25. No missing, weakened or changed assertion. Revision 4 also touched 105 other tests. Those were not read one by one: a loose text match found a return assertion in every card that opens with a `returns` line, and every `return → None` mutant in the file is killed.

### Traceability
Cases 165 · tests 165 · unmatched: none · duplicates: none. Checked on the collected pytest items, not on source text: every `xfail` card has exactly one `strict=True` mark whose reason names each listed BUG ID, every `pass` card has no mark, and every BUG ID exists in `bugs.md`. `--runxfail` failed set == the 64 xfail cases. Which assertion each xfail fails on was not re-read in this round.

### Stability
8 whole-file runs, 4 of them after the comment edit, on the same three forced plans as the department round (`SHOW` confirmed `PGOPTIONS` reaches the connection). Identical every time; no XPASS.

### Test-file change
Comments only, to make ruff clean: `# ruff: noqa: SIM117, FURB157, C408` at the top and `# noqa: DTZ001` on NOW, V0 and UPD0. No test body changed, so the file is still `Decimal("...")` and `dict(...)` as the cards have them. The full mutation run was made before this edit; the mutants on L145-170 were re-run after it.

### Left open (outside the Findings table)
- The file has no commit-spy cards, although the spec says "No commit" for the writers and the current designer skill asks for one per writer. The pilot predates that rule. Unlike the department module, this one writes money state, so it is the more useful of the two to close.

### Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_payment_transaction_manager.py -q -p no:cacheprovider --cov=app.managers.payment_transaction_manager --cov-branch --cov-report=term-missing
  app\managers\payment_transaction_manager.py     132      0     34      0   100%
  101 passed, 64 xfailed, 15 warnings
... --runxfail -rf                                   64 failed, 101 passed (failed set == xfail set)
PGOPTIONS="-c enable_seqscan=off"                    101 passed, 64 xfailed
PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off"   101 passed, 64 xfailed
PGOPTIONS="-c enable_seqscan=off -c enable_bitmapscan=off"     101 passed, 64 xfailed (before the comment edit)
.venv/Scripts/python.exe -m ruff check tests/unit/managers/test_payment_transaction_manager.py     All checks passed!   (27 errors before the edit)
.venv/Scripts/python.exe -m ruff check --select F841,F811 ...                                      All checks passed!
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/payment_transaction_manager.py tests/unit/managers/test_payment_transaction_manager.py --json <scratch>/mut_payment.json
  Mutants: 166 · killed 160 · timeout 0 · survived 6 · score 96%
... --lines 145-170  (after the comment edit)        Mutants: 27 · killed 27 · survived 0
```

## Round 3 — 2026-10-31 (cases revision 5, narrow)

> **Verdict:** PASS
> Tests: 108 passed · 64 xfailed (reproduced ✅) · coverage 100% branch (132 statements, 34 branches)
> Mutation: not re-run this round. Round 2 stands: 166 mutants · 160 killed · 6 bug-path, on the same source; this round only added tests.
> Source commit: e48a092 · Cases revision: 5

### Summary
Closes the gap round 2 left open. Added 7 commit-spy cards, one per writer: LOG-05, INIT-32, AVR-44, FIN-28, MTW-16, RR-12, REC-30. Counts went from 165 to 172 cases (108 pass, 64 xfail). No writer commits, so there is no discrepancy and no money question to decide.

**How much this round is worth.** The same agent wrote these cards, wrote their tests and checked them, so this is lighter than an independent round. No independent verifier has audited revision 5. The negative control below is the only evidence here that does not rest on that agent reading its own work.

### Findings
None.

### Checks on the new cards
- **Negative control:** a scratch pytest plugin wrapped all seven writers in memory to call `session.commit()` after running (nothing under `app/` changed). All seven cards went red. The failure line was not inspected card by card.
- **Paths covered:** each card runs one success path. A commit on another path of the same writer, such as a refused start or a rejected `val_id`, would not be seen; those paths today sit under BUG-019 and BUG-023.

### Traceability
Cases 172 · tests 172 · marker check on collected items: 0 problems. `--runxfail` failed set == the 64 xfail cases.

### Stability
Plain runs 3, with no change. Forced plans `enable_seqscan=off`; `enable_indexscan=off` + `enable_bitmapscan=off`; seq + bitmap off: 108 passed, 64 xfailed on each, no XPASS.

### Commands run
```
... test_payment_transaction_manager.py --cov=app.managers.payment_transaction_manager --cov-branch      108 passed, 64 xfailed; 100%
... --runxfail -rf                                                                                       64 failed, 108 passed (failed set == xfail set)
PGOPTIONS (3 forced plans)                                                                               108 passed, 64 xfailed each
.venv/Scripts/python.exe -m ruff check tests/unit/managers/test_payment_transaction_manager.py           All checks passed!
```
