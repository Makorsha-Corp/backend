# Verification — `app/managers/sales_manager.py`

> **Verdict:** PASS
> Tests: 252 passed · 78 xfailed (reproduced ✅ — all 78 fail under `--runxfail`, each on its designed "fails today on" assertion) · coverage 99% branch
> Mutation: 420 mutants · 405 killed · 15 survived → score 100% (405/405, after excluding 4 equivalent, 9 dead, 2 bug-path)
> Source commit: e48a092 · Cases revision: 7

Narrow re-verify after the fix round on the previous report (cases revision 6, one open finding: F5). Traceability and the runs were redone in full. Fidelity was read for the one new test, SM-UD-22. Mutation was re-run on source l.425–446 (17 mutants, covering the F5 mutant at l.435); all other mutant results are carried over.

## Summary
These tests can be trusted. The last open finding, F5, is closed: the new case SM-UD-22 is implemented faithfully and the mutant `exclude_unset=True -> False` at source l.435 is now killed.
Runs match the notes' Result line exactly (252 passed / 78 xfailed / 99% branch) and are stable over four runs.
Every one of the 15 remaining survivors is `equivalent`, `dead` or `bug-path`. Nothing is routed to any stage.
One cosmetic leftover, not a finding: the notes' "Stability" bullet (notes l.46) still says "251 passed"; the Result line (l.4) and the revision-7 history entry correctly say 252.

## Findings
No open findings. All previous findings are resolved.

| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| F1 | Dishonest xfail | SM-CD-38 | **RESOLVED** (revision 6). `SalesDeliveryCreate` is imported; the test fails on its designed assertion. | `--runxfail`: no `NameError` in the output. | — |
| F2 | Spec gap (unreachable precondition) | spec `create_delivery_with_items` R7, `fulfill_service_item` R4, `_recompute_is_fully_delivered` R1 | **RESOLVED** (revision 6). Spec Gap log G17 states that `quantity_refunded` is NOT NULL. | spec Gap log G17. | — |
| F3 | Case unreachable | SM-CD-42, SM-FSI-10, SM-RFD-07 | **RESOLVED** (revision 6). The three IDs are retired and their tests are gone. | Traceability: 330 cases, 330 tests, no unmatched test. | — |
| F4 | Spec contradiction | spec Notes vs `is_so_financially_locked` R3; source l.536 | **RESOLVED** (revision 6). Spec G18 declares `'locked'` a dead value. Survivor #5 below stays `dead`. | spec Gap log G18. | — |
| F5 | Case missing | `update_delivery` R3/R5/R6, source l.435 `exclude_unset=True`; SM-UD-22 (cases l.356, test l.3106–3126) | **RESOLVED** (revision 7). SM-UD-22 sends only `notes="Gate 3"` (the stored value) on an ad-hoc model whose unset `delivery_status` defaults to `"cancelled"`. The unset field alone now decides the outcome: today's code logs nothing; the mutant logs `"Delivery DEL-2026-004 updated ()"`. The test asserts no event, so it fails on the mutant. | Mutation re-run on l.425–446: `L435:49 const True -> False KILLED` (was SURVIVED in the previous report). | — |
| F6 | Missing assertion | SM-CD-01 | **RESOLVED** (revision 6). | — | — |
| F7 | Weakened assertion | SM-CD-23 | **RESOLVED** (revision 6). | — | — |
| F8 | Missing assertion | SM-CD-29 | **RESOLVED** (revision 6). | — | — |
| F9 | Missing assertion | SM-CPD-26 | **RESOLVED** (revision 6). | — | — |
| F10 | Missing assertion | SM-UD-04 | **RESOLVED** (revision 6). | — | — |
| F11 | Missing assertion | SM-SEC-01, SM-ROR-02, SM-AA-01, SM-RMA-01, SM-SA-01 | **RESOLVED** (revision 6). | — | — |
| F12 | Weakened assertion | SM-MOC-11, SM-MOC-12 | **RESOLVED** (revision 6). | — | — |

### Fidelity of SM-UD-22 (test l.3106–3126)
No finding.
- **Given:** `ud_setup` builds D1 planned with `scheduled_date` 2026-10-05, DM1, tracking "TRK-100", notes "Gate 3", `updated_by` U2, on the default delivery number `DEL-2026-004`. The setup writes no event for SO1.
- **When:** the ad-hoc model has `delivery_status: str = "cancelled"` and `notes: str | None = None`, built as `_AdHocData(notes="Gate 3")`, and the call is `(D1, W1, data, user_id=U1)` — exactly as the case states.
- **Then:** every item is asserted with `==` on re-read rows: return `result.id == d1.id`; `events_for(db, order) == []` (covers both "row count unchanged" and "no `delivery_updated` event" for SO1, since SO1 has no events before the call); `delivery_status == "planned"`, `notes == "Gate 3"`, `scheduled_date`, `delivery_method_id == dm1.id`, `tracking_number == "TRK-100"`, `updated_by == u2.id`.
- No mocks, no `try/except`, no xfail marker (Expect is `pass`).

## Surviving mutants
The l.425–446 range was re-run; the 13 survivors outside it are carried over from the previous report with unchanged classes.

| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | 27 | `'invoice_confirmed'` key → `''` | equivalent | `set_section_confirm` maps only `order_info`/`items`, so the `invoice_confirmed` entry of this module's `SECTION_CONFIRM_FIELDS` is never read. Other modules import `purchase_order_manager`'s dict, not this one. | — |
| 2 | 27 | `'invoice'` → `''` | equivalent | Same entry, never read. | — |
| 3 | 27 | `'Draft invoice'` → `''` | equivalent | Same entry, never read. | — |
| 4 | 435 | `exclude_none=True` → `False` | bug-path | Explicit `null` handling is BUG-732 (R3/R4). Only xfail UD-06/UD-07 target it, and they are excluded from the run. Re-run this round: still survives. | — |
| 5 | 536 | `'locked'` → `''` | dead | Spec R3 / G18: `'locked'` is never written in `app/`, so it is a dead value with no case. | — |
| 6 | 583 | `raise` → `pass` | dead | `account_id is None` check: dead code (spec Q17, deadcode-staging). | — |
| 7 | 583 | message const → `''` | dead | Same branch. | — |
| 8 | 585 | `raise` → `pass` | dead | `order_date is None` check: dead code (spec Q17). | — |
| 9 | 585 | message const → `''` | dead | Same branch. | — |
| 10 | 763 | `len(approvers) > 0` → `>= 0` | equivalent | With 0 approvers both branches give `required = 0` (`len([]) == 0`), so the result is identical. | — |
| 11 | 766 | `required = 0` → `1` | bug-path | Zero-approvers case is BUG-736. Only xfail AS-05 targets it. | — |
| 12 | 770 | `return …` → `return None` | dead | `approvals_met`: dead code (spec Q20). | — |
| 13 | 770 | index `2` → `3` | dead | Same method. | — |
| 14 | 791 | `'User #'` → `''` | dead | Missing-profile fallback unreachable (spec G8, deadcode-staging). | — |
| 15 | 806 | `'User #'` → `''` | dead | Same, `remove_approver` (spec G8). | — |

Previous survivor `l.435 exclude_unset=True → False` (was #4, `case-missing`) is now **killed** by SM-UD-22.

## Traceability
- **Counts:** 330 cases, 330 tests, 1:1. Every case ID matches exactly one `test_sm_<x>_<nn>__…` name and its docstring ID. No unmatched tests, no duplicates, no test without a case ID, no parametrized tests. Checked with an AST script.
- **Markers:** all 252 `pass` cases have no xfail marker. All 78 `xfail BUG-…` cases have `xfail(strict=True)` whose reason names exactly the listed BUG IDs. No skip markers.
- **BUG IDs:** all 20 IDs used (BUG-009, 021, 362, 720–726, 728–737) are in `docs/testing/bugs.md`.
- **Mocks:** none (no `monkeypatch`, `patch`, `MagicMock`). `SQLCapture` is an event listener (observation only).
- **Fix round completeness:** the cases file header says revision 7 and 330 cases (252 pass, 78 xfail); the notes and the test file header cite revision 7; the notes carry a "Cases rev 7" history entry; SM-UD-22 has its test directly after SM-UD-21.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_sales_manager.py -q -p no:cacheprovider --cov=app.managers.sales_manager --cov-branch --cov-report=term-missing
  app\managers\sales_manager.py  365  3  142  3  99%   355->357, 583, 585, 770
  252 passed, 78 xfailed, 254 warnings in 38.64s

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_sales_manager.py -q -p no:cacheprovider --runxfail -rf --tb=line
  78 failed, 252 passed, 239 warnings in 11.65s
  first error per failing test: 29 assertion mismatches · 46 DID NOT RAISE · 3 IntegrityError
  — the same split as the previous report (the 78 xfail tests are unchanged).
  no NameError / ImportError / TypeError / AttributeError / setup error / NotNullViolation.

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_sales_manager.py -q -p no:cacheprovider   # repeat 1
  252 passed, 78 xfailed, 239 warnings in 20.30s
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_sales_manager.py -q -p no:cacheprovider   # repeat 2
  252 passed, 78 xfailed, 239 warnings in 19.36s
  -> no flakiness; matches the notes' Result line (252 passed · 78 xfailed · 99% branch).

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/sales_manager.py tests/unit/managers/test_sales_manager.py --timeout 180 --lines 425-446 --json <tmp>/sm_mut_425_446.json
  Mutants: 17 · killed 16 · timeout 0 · survived 1 · score 94%
  [9/17]  L435:49 const True -> False   KILLED     (exclude_unset — the F5 mutant; SURVIVED in the previous report)
  [10/17] L435:68 const True -> False   SURVIVED   (exclude_none — bug-path, BUG-732)
  All other lines carried over from the previous runs: 420 mutants in total, now 405 killed · 15 survived.
```

---

## Round — 2026-11-19 (cases revision 9: OQ-48 refined, `has_open_return` / RP1–RP7, BUG-2790)

> **Current verdict:** NEEDS WORK — 2 case-missing findings (F13, F14) for the case designer. No fidelity finding, nothing for the executor or the describer.
> Tests: 261 passed · 84 xfailed (reproduced ✅) · coverage 99% branch (365 stmts / 142 branches; missed 355->357, 583, 585, 770, unchanged) · 3 plain runs identical (no flake)
> Mutation: carried over (420 · 405 killed · 15 survived → 100% after exclusions). Not re-run: `app/managers/sales_manager.py`, `sales_order_return_manager.py` and `dao/sales_order_return.py` are unchanged at e48a092, and revisions 8–9 only added or retargeted tests.
> Cases revision: 9 · Scope: SM-ROR-02..14, SM-MOC-14..16 (this also covers the revision-8 cards ROR-03..10, which no verify round had read yet). Traceability: 345 case ids, all present in the test file.

### Fidelity
All 16 tests match their cards, with Thens in card order (`# Then N`).
- **`hor()`** flushes, then calls `SalesOrderReturnManager().has_open_return(order.id, order.workspace_id)`, after the action, as HOR prescribes.
- **ROR-02:**
  - Given: pending return, a linked confirmed invoice, no events.
  - Thens: invoice → HOR True → `result is False` → stamps and `invoice_id` → 0 events → NW (counts plus full SO1 and return rows).
- **ROR-03, ROR-08, ROR-09, ROR-12:** `isinstance(result, bool)` plus every listed re-read and count. ROR-03 ends with HOR True; ROR-12 with returns count == 2.
- **ROR-04..07:** the W0/W2 guards are asserted; NW is checked.
- **ROR-10:** a commit spy (`wraps=db.commit`) inside a savepoint; 0 calls.
- **ROR-11, ROR-13, ROR-14:** HOR → `False` → stamps → return statuses → 0 events → NW.
- **MOC-14..16:** `moc_setup` with the completed stamps; return rows as in the Given; no events; `result.id`, HOR, stamps and `paid False`, 0 events, NW (counts plus full SO1 and return rows).

`--runxfail -k sm_ror`: the 6 BUG-2790 xfails (ROR-02, 06, 07, 11, 13, 14) each fail on their designed `result is False` line. For ROR-02 that is Then 3, at line 4459; its HOR line passes today, as the card says.

### Reference fix and hand variants
My plugin `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\invlockv\refsm.py` (in-process; app/ untouched) applies the reference fix: `reopen_for_return` returns `False` for a completed order and writes nothing.

| Run | Result |
|---|---|
| reference, full file | 267 passed, 78 xfailed |
| reference, markers kept | exactly the 6 BUG-2790 cards XPASS (strict) |

Hand variants (scope `-k "sm_ror or sm_moc"`):

| Variant | Killed by |
|---|---|
| reopen still happening (today's code) | ROR-02, 06, 07, 11, 13, 14 |
| reopen only when no return is open | ROR-06, 07, 14 |
| returns `False` but clears `completed_at` / logs `order_reopened` / returns `True` without writing | ROR-02, 06, 07, 11, 13, 14 (each) |
| `session.commit()` inside `reopen_for_return` | ROR-10 |
| `mark_order_complete` R2 runs R3–R5 on a completed order (then returns it unchanged) | MOC-03, MOC-14 |
| same, and completes it again (restamp + event) | MOC-03, MOC-14, MOC-15, MOC-16 |
| R5 open-return check ignores status (any return blocks) | MOC-11 |
| `has_open_return` ignores status | MOC-11, MOC-15, MOC-16, ROR-14 |
| R5 open-return check ignores **workspace** (`moc_r5_anyws`) | **survives** (F13) |
| `has_open_return` ignores **workspace** (`hor_anyws`) | **survives** (F13) |
| `session.commit()` inside `mark_order_complete` (`moc_commit`) | **survives** (F14) |

### Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| F13 | Case missing | `mark_order_complete` R5; spec RP2 ("this order's returns **in this workspace**"); MOC-10..12, MOC-14..16 | No card has a return row of another workspace pointing at SO1. A workspace-blind open-return check passes every card, whether it is in the manager's R5 or in `has_open_return` (the HOR flag). Such a check would block completion because of another workspace's data, and would show "return in progress" from it. | `moc_r5_anyws`, `hor_anyws`: 0 failures in `sm_ror or sm_moc`. | **case designer**: one MOC pass card. SO1 complete-able (default setup), plus a return row in W2 (and one in W0) with `sales_order_id = SO1.id`, `status 'pending'` → completes (R6, R8); a Then line with HOR(SO1) `is False`. |
| F14 | Case missing | `mark_order_complete` side effects "flush only" | ROR-10 spies on commit for `reopen_for_return` only. No MOC card checks that `mark_order_complete` never commits. | `moc_commit`: 0 failures. | **case designer**: a MOC commit-spy card like ROR-10 (default setup; spy on `session.commit` inside a savepoint; 0 calls). |

F1–F12 stay resolved. No new bug: `docs/testing/bugs.md` not touched.

```
pytest tests/unit/managers/test_sales_manager.py -q -p no:cacheprovider ×3           → 261 passed, 84 xfailed (×3)
pytest … --cov=app.managers.sales_manager --cov-branch --cov-report=term-missing   → 365 3 142 3 99% · 261 passed, 84 xfailed   (COVERAGE_FILE=…\invlockv\.coverage.sm)
pytest … --runxfail -k sm_ror --tb=line                                           → 6 failed (`assert True is False`), 8 passed
PYTHONPATH=…\invlockv REFSM=ref pytest … -p refsm                                  → 267 passed, 78 xfailed
REFSM=ref REFSM_KEEPX=1 …                                                         → 6 failed (XPASS strict), 261 passed, 78 xfailed
REFSM=<variant> pytest … -p refsm -k "sm_ror or sm_moc"                           → as in the table
git diff --quiet HEAD -- app/managers/sales_manager.py app/managers/sales_order_return_manager.py app/dao/sales_order_return.py → unchanged
```

---

## Round — 2026-11-19, later (cases revision 10: F13, F14)

> **Current verdict:** PASS
> Tests: 263 passed · 84 xfailed (reproduced ✅) · coverage 99% branch (365 / 142; missed 355->357, 583, 585, 770, unchanged) · 3 plain runs identical (no flake)
> Mutation: carried over (420 · 405 killed · 15 survived → 100% after exclusions); `app/managers/` unchanged at e48a092.
> Cases revision: 10 · Scope: SM-MOC-17, SM-MOC-18, `mk_return(ws=)` · Traceability: 347 case ids, all present.

**F13 and F14: RESOLVED.**
- **`mk_return(ws=)`** changes only `workspace_id`; the default is the order's workspace, so earlier tests are unaffected.
- **MOC-17 matches its card.**
  - Given: the default `moc_setup`, R0 and R2X `pending` with `ws=w0` / `ws=w2`, no W1 return, and the guard `w0 < w1 < w2`.
  - Thens 1–6 in order: `result.id`; `order_completed`, `completed_by`, `completed_at` in [T0, T1]; exactly 1 event `order_completed` / `'Order marked complete'` / U1; HOR False; R0 and R2X still `pending` with their workspaces.
- **MOC-18 matches its card:** a commit spy (`wraps=db.commit`) inside a savepoint; `result.id`; 0 calls; `order_completed True` re-read before `sp.rollback()`.
- **Variants re-run** (`refsm.py`, scope `sm_ror or sm_moc`):
  - `moc_r5_anyws` → killed by MOC-17.
  - `hor_anyws` → killed by MOC-17.
  - commit inside `mark_order_complete` → killed by MOC-18.
  - Reference fix on the full file: 269 passed, 78 xfailed.

No open findings. `bugs.md` not touched.
