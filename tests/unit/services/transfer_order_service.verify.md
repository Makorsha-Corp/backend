# Verification — `app/services/transfer_order_service.py`

> **Verdict:** PASS (Round 2, cases Revision 4; Round 1 was NEEDS WORK, see below)
> Round 1 — Tests: 101 passed · 8 xfailed (reproduced ✅) · coverage 100% branch (137 statements; coverage.py counts no branch arcs in this file)
> Mutation (`mutate.py`, 3 shards, all finished): 59 mutants · 58 killed · 1 survived → score 98% (0 equivalent, 0 dead, 0 bug-path excluded)
> Hand variants (verifier's own `hand.py`, 107 on a temp copy): 94 killed · 13 survived (3 equivalent, 10 case-missing) → score 90% (94 / 104). Lock variants (`lock.py`, 7): 6 detected as designed, 1 partly missed (U-13).
> Source commit: e48a092 · Cases revision: 2

## Summary
The tests are faithful to the cards. Every card has exactly one test, every Then line has its assertion, there are no extra mocks, and every strict xfail fails on the Then line its card names. Three runs give identical results, matching the notes. The transaction contract holds up well against mutation: missing commits, missing refreshes, reads that commit or roll back, commits moved before notifying, partial commits, swallowed or translated errors, duplicate, skipped or swallowed notifications, and a wrong readiness snapshot are all caught. The open problems are in the case design, not the tests:
1. The TC3 "x_gone" check can never fail, because the convention makes the test run `db.rollback()` first. Five write methods can drop their rollback unnoticed.
2. HR-16 is tested only on the W2 (higher id) side for `get_transfer_order` and `approval_summary_for`.
3. No case passes `"all"` as the destination type.
4. The machine-involved count's filter reaching the DAO is not visible, because HS-02's filter equals the DAO default.
5. U-13's looped order lets a lock placed *after* the readiness snapshot pass.

All five go to the case designer. Nothing goes to the executor, and nothing to the describer.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing (TC3) | Conventions "committed: x_gone"; D-02, D-03, UI-02, UI-03, RI-03, RI-04, RA-03, SA-03, SA-04 (and every TC3 card) | `x_gone` is checked only after the test's own `db.rollback()`, which discards X whatever the service did. A refusal raised before any flush therefore leaves no trace of a missing service rollback. TC3 ("every other uncommitted change pending in that session is discarded") is untested for 5 methods. | Hand variants `self._rollback_transaction(db)` → `pass` SURVIVED at L218 (delete), L274 (update_item), L283 (remove_item), L333 (remove_approver), L345 (set_approval). | **case designer**: add a `session:` line before any test rollback, e.g. `X not in db` (the mirror of AS-02's `X in db`), or `x_gone` without the leading rollback, to the TC3 refusal cards. |
| 2 | case-missing (HR-16) | `get_transfer_order` (G-02 is W2 only); `approval_summary_for` (AS-02 is W2 only) | A lower-id (W0) foreign order is never requested. A scope that leaks only lower workspaces passes. | Hand variants "return the row if `workspace_id <= caller`" in `get_transfer_order` L70 and `approval_summary_for` L298 SURVIVED. The `>=` twins were killed by G-02 / AS-02. | **case designer**: add W0 (order O0) 404 cards for `get_transfer_order` and `approval_summary_for`, as U-01 / AI-06 do. |
| 3 | case-missing | `_hub_filter_kwargs` R2; HF-03 | `destination_location_type="all"` is never passed. HF-03 sends `""` for the destination, and LP-04 / HS-05 filter the source only. | mutate.py #25 L102:74 `'all' -> ''` SURVIVED. | **case designer**: HF-03 (or a new card) with `destination_location_type="all"` → `None`. Ideally also `source_location_type=""`. |
| 4 | case-missing | `get_transfer_order_hub_stats` R1; HS-02 | HS-02 filters `exclude_complete=True`, which is also the DAO's own default (spec D2). Dropping `**filters` from `count_transfer_orders_machine_involved_for_hub` therefore gives the same 1. | Hand variant L182 `**filters` dropped SURVIVED. The same drop on the stats, recent, pending, count and list reads was killed. | **case designer**: a machine-count case where the filter differs from the DAO default, e.g. default `exclude_complete=False` with a completed machine order (expect 2), or a `source_location_type` filter that excludes a machine order. |
| 5 | case-missing (BUG-3142) | TOS-U-13 Given 1 "order O, but looped" | On a looped order `_ready_for_approval` returns at `_route_valid` without reading `transfer_order_items`. "Lock first" is then met by a lock taken anywhere before the manager's first items read: *after* the snapshot, or the manager's own BUG-2892 lock. U-13 could XPASS without BUG-3142 being fixed. AI-11 (routed order) does not have this hole. | `lock.py` LV3 (correct clause, inserted after the snapshot): U-13 **passed**, AI-11 failed. LV1 (correct, before the snapshot) passed both and kept all 101 pass cards green. LV2 (bare), LV4 (NOWAIT), LV5 (SKIP LOCKED), LV6 (FOR SHARE), LV7 (FOR NO KEY UPDATE) failed both on Then 2. | **case designer**: give U-13 a routed order with a line (e.g. a description edit, ready → ready), so the snapshot reads the items. |
| 6 | case-missing (low) | `update_transfer_order` R1, `add_item` R1 | The pre-read 404 is tested only with foreign orders, never with an unknown id (spec R1: "missing or another workspace's → 404"). An unscoped pre-read (`db.get`) is invisible for foreign orders, because the manager refuses later with the same 404. For a missing id it would raise `AttributeError`. | Hand variants "pre-read via `db.get(TransferOrder, to_id)`" at L47 and L241 SURVIVED. | **case designer**: a MISSING-id 404 card for `update_transfer_order` and `add_item`. |
| 7 | card wording (known DISCREPANCY-1) | TOS-HF-01 … HF-04 When | The card calls `TransferOrderService._hub_filter_kwargs(...)` on the class, but it is an instance method. The tests pass `svc` as `self`, and that is correct. | `app/services/transfer_order_service.py:81`; notes DISCREPANCY-1. | **case designer** (When → `svc._hub_filter_kwargs(...)`); the spec header signature should also show `self` (**describer**, cosmetic). |

No fidelity findings: no missing, weakened or changed assertions, no wrong setup, no in-memory-only write checks, no swallowed failures, no extra mocks, and no dishonest xfails.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| M25 | L102:74 | `'all' -> ''` (destination) | case-missing | finding 3 | case designer |
| H1–H5 | L218, L274, L283, L333, L345 | service rollback dropped in delete / update_item / remove_item / remove_approver / set_approval | case-missing | finding 1 | case designer |
| H6 | L70 | `get_transfer_order` leaks rows of lower-id workspaces | case-missing | finding 2 | case designer |
| H7 | L298 | `approval_summary_for` leaks rows of lower-id workspaces | case-missing | finding 2 | case designer |
| H8 | L182 | machine-involved count without `**filters` | case-missing | finding 4 | case designer |
| H9 | L47 | update pre-read unscoped (`db.get`) | case-missing | finding 6 | case designer |
| H10 | L241 | add_item pre-read unscoped (`db.get`) | case-missing | finding 6 | case designer |
| H11 | L306 | add_approver re-read unscoped (`db.get`) | equivalent | the manager's `add_approver` has already found this id in `workspace_id`, so the same row comes back | — |
| H12 | L254 | add_item notifies with `to_before` instead of `to_after` | equivalent | both are the same identity-mapped ORM instance of one session; readiness reads lines from the DB | — |
| H13 | L216 | `db.flush()` before the delete commit | equivalent | `commit()` flushes first anyway | — |
| LV3 | L47–48 | lock clause after the readiness snapshot | case-missing | finding 5: U-13 passes, AI-11 catches it | case designer |

Killed hand variants:
- **TC1:** no commit, all 10 writes.
- **TC2:** no refresh, all 7.
- **TC3:** no rollback is killed for create, update, mark_order_complete, add_item and add_approver.
- **TC6:** a read that commits or rolls back, all 7 reads × 2.
- **Commit order:** commit before notifying (update, add_item, add_approver), a commit before the manager runs (complete), and a partial commit between the manager and notifying (×3).
- **Error mapping:** swallowed (`return None`) and translated (`RuntimeError`) errors, all 10 writes.
- **Notifications:**
  - notice sent twice, skipped, or its error swallowed (×3 each);
  - readiness snapshot taken after the change (×2);
  - wrong actor (×2);
  - wrong approver record.
- **HR-16:** W2 leaks and fully unscoped get / summary.
- **Hub:** recent limit 11, and filters dropped from count, list, stats, recent and pending.
- **Defaults and filter text:** list default limit and skip, `exclude_complete` defaults (×3), and the `lower()` / `strip()` `"all"` comparisons.

## Traceability
Cases 109 · tests 109 · unmatched: none · tests without an ID: none · duplicate IDs: none. Marker mismatches: none. All 101 `pass` cards are unmarked. All 8 xfail cards (U-12 BUG-2899, U-13 BUG-3142, U-14 BUG-2903, D-05 / D-06 BUG-1194, AI-11 BUG-3142, AA-08 / RA-05 BUG-2897) carry `xfail(strict=True)` with a reason constant naming their BUG ID, and every ID exists in `docs/testing/bugs.md`.

`--runxfail` failure points, all on the card's named Then line:
- U-12: L1139 `DID NOT RAISE` (Then 1)
- U-13: L1173 `locked_before_items` (Then 2)
- U-14: L1197 `True is False` (Then 2)
- D-05: L1806 `TypeError … 'user_id'` (Then 1)
- D-06: L1837 `'user_id' in params` (Then 1)
- AI-11: L2368 (Then 2)
- AA-08: L2943 (Then 1)
- RA-05: L3127 (Then 1)

## Commands run
Each run had its own `COVERAGE_FILE` under `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2v\transfer\`.
```
.venv/Scripts/python.exe -m pytest tests/unit/services/test_transfer_order_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.transfer_order_service --cov-branch --cov-report=term-missing
  → 137 stmts, 0 miss, 100% · 101 passed, 8 xfailed
(same, plain) ×2 → 101 passed, 8 xfailed · 101 passed, 8 xfailed
.venv/Scripts/python.exe -m pytest tests/unit/services/test_transfer_order_service.py -q -p no:cacheprovider -o addopts="" --runxfail -rf --tb=short
  → 8 failed, 101 passed
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/transfer_order_service.py tests/unit/services/test_transfer_order_service.py --lines {1-105 | 106-230 | 231-400} --json …/mut_<range>.json
  → 25: 24 killed, 1 survived · 16: 16 killed · 18: 18 killed
.venv/Scripts/python.exe …/svc2v/transfer/hand.py (SHARD 0/3, 1/3, 2/3)   → 107 variants: 94 killed, 13 survived
.venv/Scripts/python.exe …/svc2v/transfer/lock.py                         → LV1 2 passed (+101 pass cards green); LV2, LV4–LV7 2 failed; LV3 1 failed, 1 passed
```

## Round 2 — 2026-11-22

> **Verdict:** PASS
> Tests: 106 passed · 8 xfailed (reproduced ✅, 3 runs identical) · coverage 100% (137 statements) · Cases revision: 4 · Source commit: e48a092
> Re-run of the Round 1 survivors: 10 hand variants + 1 `mutate.py` mutant, all 11 now killed. Lock variants: 7 of 7 behave as designed.

**Scope.** A narrow round. I checked the Revision 4 changes and re-ran only the Round 1 survivors.
- New tests U-19, AI-14, G-03, AS-03 and HF-05.
- Changed tests U-13 and HS-02.
- The nine refusal tests that gained `X not in db`: D-02, D-03, UI-02, UI-03, RI-03, RI-04, RA-03, SA-03 and SA-04.

**Fidelity.** All the new and changed tests match their Revision 4 cards, Then line by Then line, in card order.
- U-19 / AI-14 use MISSING and check `X not in db` (Then 4) before the test's own rollback.
- G-03 / AS-03 use O0 and check the spies and `X in db`.
- HF-05 is `svc._hub_filter_kwargs(source_location_type="", destination_location_type="all")`.
- HS-02 uses `exclude_complete=False`, with (2, 1, 1), machine count 2 and recent {A, C}.
- U-13 uses a routed order with a line and a description edit, and has the new Then 3 (an items SELECT was recorded).
- In the nine refusal tests, `assert x not in db` is Then 4, right after the `pytest.raises` block, before any re-read or rollback.

Traceability: 114 cards · 114 tests · unmatched none · marker mismatches none. No findings.

**Round 1 survivors, re-run targeted on a temp copy:**
| Round 1 # | Variant | Round 2 |
|---|---|---|
| H1–H5 | service rollback dropped in delete L218, update_item L274, remove_item L283, remove_approver L333, set_approval L345 | KILLED ×5 (`X not in db`) |
| H6 | `get_transfer_order` leaks lower-id workspaces | KILLED (G-03) |
| H7 | `approval_summary_for` leaks lower-id workspaces | KILLED (AS-03) |
| H8 | machine-involved count without `**filters` | KILLED (HS-02) |
| H9 / H10 | update / add_item pre-read unscoped | KILLED (U-19 / AI-14) |
| M25 | L102:74 `'all' -> ''` (with the other two L102 mutants) | KILLED 3/3 (HF-05) |
| LV3 | correct lock clause placed after the snapshot | KILLED: U-13 and AI-11 both fail |

H11–H13 remain equivalent, as argued in Round 1.

**Lock variants (`lock.py`).**
- LV1 (correct `FOR UPDATE OF transfer_orders` before the snapshot): U-13 and AI-11 pass, and all 106 pass cards stay green.
- LV2 bare, LV3 after the snapshot, LV4 NOWAIT, LV5 SKIP LOCKED, LV6 FOR SHARE and LV7 FOR NO KEY UPDATE: both tests fail.

**`--runxfail`.** 8 failed, 106 passed. Each xfail fails on its card's named line:
- U-12: L1165 (Then 1)
- U-13: L1199 `locked_before_items` (Then 2)
- U-14: L1225 (Then 2)
- D-05: L1874 (Then 1)
- D-06: L1905 (Then 1)
- AI-11: L2460 (Then 2)
- AA-08: L3069 (Then 1)
- RA-05: L3255 (Then 1)

**Commands** (each run had its own `COVERAGE_FILE` under `…\svc2v\transfer\`):
```
pytest … --cov=app.services.transfer_order_service --cov-branch   → 100% · 106 passed, 8 xfailed
pytest … (plain) ×2                                                → 106 passed, 8 xfailed · 106 passed, 8 xfailed
pytest … --runxfail --tb=line                                      → 8 failed, 106 passed
hand.py "TC3 no-rollback (delete|update_item|remove_item|remove_approver|set_approval)|HR16 W0-only|HUB machine|HR16 (update|add_item) pre-read unscoped"  → 10/10 KILLED
lock.py                                                            → LV1 2 passed (+106 green); LV2–LV7 2 failed each
mutate.py … --lines 102-102                                        → 3 mutants, 3 killed
```

Nothing is open for any stage. The only remaining note is the cosmetic spec-header signature (`self`) for the describer, carried over from Round 1, finding 7.
