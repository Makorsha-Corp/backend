# Verification — `app/services/approval_notification_service.py`

> **Current verdict (round 2, 2026-11-10):** PASS. Cases rev 4 · 176 passed · 16 xfailed · mutation 194 / 194 counted = 100% (7 equivalent excluded).
>
> **Verdict (round 1):** NEEDS WORK
> Tests: 172 passed · 16 xfailed (reproduced ✅) · coverage 99% branch (186 stmts, 98 branches, only 332->340 missed)
> Mutation: 201 mutants · 184 killed · 17 survived → score 95% (184 / 194, after excluding 7 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 3

## Summary
The tests can be trusted for what they cover. All 188 cards are implemented faithfully. Every Then line is asserted with the exact value the card gives. Nothing is mocked except the commit and rollback spies. Every xfail fails on its card's "Fails today on" line. Three plain runs and the `--runxfail` run reproduce the notes. My 14 hand variants were all killed: inactive members, other workspaces, actor handling, unchanged saves, dropped workspace filters, voided or deleted orders, tie order, and duplicate writes.

Two things still need work:
- **Case designer.** `notify_invoice_action` R3 adds approvers who already approved when `required > 0`. The cards test this for purchase orders only. The transfer, expense and work order arms (lines 318-338) can be broken without any test noticing.
- **Describer.** `detect_section_unconfirmed` treats an order that lacks the attribute as unconfirmed (the `getattr(..., False)` default). No rule states this.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `notify_invoice_action` R3, lines 318-338 | R3 ("only when `required` > 0, **every** approver row … approved ones too") is checked only for purchase orders (IA-01, IA-05, IA-06, IA-11). TO / EO / WO cards (IA-02, IA-04, IA-12) only have pending approvers, and pending approvers are already recipients by R2. No card has an approved TO / EO / WO approver with `required > 0`. | Survivors #149, #178, #191 (L318), #179, #192, #197 (L325), #193, #198, #200 (L332) | **case designer**: add one card per type (TO, EO, WO): an approved approver plus a pending one, `required_approvals` NULL or ≥1, and `recips()` includes the approved one. Optionally also add a TO / EO / WO card with `required_approvals 0`, where the approved approver is left out. |
| 2 | spec-gap | `detect_section_unconfirmed` R1/R2, line 461 | An order object that lacks one of the four confirm attributes counts as "not confirmed", so turning it off returns false. No rule says so. Every DS card passes all four attributes. | Survivor #199 L461:87 `getattr(order, confirm_field, False)` → `True` | **describer** (fill-gaps): state the missing-attribute outcome in R2. Then the **case designer** adds one card, e.g. `SimpleNamespace()` with `{"items_confirmed": False}` → `False`. |

No fidelity findings: no missing, weakened or changed assertion, no wrong setup, no swallowed failure, no extra mock, no dishonest xfail.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 99–105 | 467–473 | key strings of the module dict `approval_notification_service` → `""` | equivalent | The spec puts this dict under "Not specified": no code imports it, and callers import the functions. Renaming a key changes nothing anyone reads. | — |
| 149 | 318 | negate `elif entity_type == "transfer_order"` | case-missing | Approved TO / EO approvers are no longer added when required > 0. No card has one. | case designer (F1) |
| 178 | 318 | `==` → `!=` | case-missing | same | case designer (F1) |
| 191 | 318 | `"transfer_order"` → `""` | case-missing | same | case designer (F1) |
| 179 | 325 | negate `elif entity_type == "expense_order"` | case-missing | Approved EO / WO approvers are no longer added. | case designer (F1) |
| 192 | 325 | `==` → `!=` | case-missing | same | case designer (F1) |
| 197 | 325 | `"expense_order"` → `""` | case-missing | same | case designer (F1) |
| 193 | 332 | negate `elif entity_type == "work_order"` | case-missing | Approved WO approvers are no longer added. | case designer (F1) |
| 198 | 332 | `==` → `!=` | case-missing | same | case designer (F1) |
| 200 | 332 | `"work_order"` → `""` | case-missing | same | case designer (F1) |
| 199 | 461 | `getattr(order, confirm_field, False)` → `True` | spec-gap | Only an order without the attribute can see the difference. No rule or card covers it. | describer → case designer (F2) |

## Hand variants (verifier plugin `an_var.py`, pass cards only, `-m "not xfail"`)
| Variant | Killed by |
|---|---|
| inactive / suspended / invited members receive | AM-01, NU-03…05, AS-05, PE-05, SC-08, IA-09, IA-13, AD-04, OU-05, OU-07 (12) |
| active member of any workspace receives | AM-01…03, NU-06…08, AS-06/07, PE-06, SC-09/10, IA-10, OU-07 (13) |
| actor never notified | NU-11, AS-04, PE-02, PE-03, SC-07, IA-08, IA-11, AD-04, OU-06 (9) |
| `handle_add_approver` stops excluding actor and new approver | PE-04, AD-01, AD-02 |
| approver rows read without the workspace filter | PA-02, PA-07, PE-07, IA-11 |
| pending approvers sorted by user id (tie / order) | PA-01 |
| approved approvers counted as pending | PA-01, PE-01, PE-08, IA-05, AD-01 |
| order looked up in any workspace | SU-14, SU-17 |
| voided / deleted orders treated as not ready | RD-21, RD-22 |
| ready → ready save sends "approval pending" | OU-10 |
| not ready → not ready save re-sends gap text | OU-11 |
| reset notice sent with no approvers required | OU-02 |
| approved approvers included when required ≤ 0 | IA-05 |
| every recipient written twice | 44 cards |

All 14 were killed. With the plugin loaded and no variant selected, the run is unchanged (172 passed, 16 xfailed).

## Traceability
Cases 188 (AN-05 retired) · tests collected 188 · every card ID appears exactly once (as a test name or a `pytest.param` id), and no test is without an ID · marker mismatches: none. Every one of the 16 xfail cards has `xfail(strict=True)` with the right bug ID in the reason (BUG-1205 ×11, BUG-1202 ×3, BUG-1203, BUG-755), and all four IDs exist in `docs/testing/bugs.md`. No pass card has a marker. `ruff check` is clean.

`--runxfail`: each xfail fails on its card's Then 1, as the card says: FR-07 `'sales order #5'` · SU-07/08/09/20 `(0, 0, True)` · SU-19 `(0, 0, True)` vs `(1, 2, False)` · SU-21/22 `DID NOT RAISE HTTPException` · BP-04 `'Ready for review'` · PA-09 `[]` · HA-05 `False` · IA-17 only UC · SR-01 `False` · SR-03/04/05 `None`.

## Commands run
```
COVERAGE_FILE=<private> .venv/Scripts/python.exe -m pytest tests/unit/services/test_approval_notification_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.approval_notification_service --cov-branch --cov-report=term-missing
  app\services\approval_notification_service.py  186  0  98  1  99%  332->340
  172 passed, 16 xfailed, 15 warnings
.venv/Scripts/python.exe -m pytest <same file> -q -p no:cacheprovider -o addopts="" --runxfail -rf
  16 failed, 172 passed
.venv/Scripts/python.exe -m pytest <same file> -q -p no:cacheprovider -o addopts="" --runxfail -m xfail --tb=short   (failing line per xfail, above)
.venv/Scripts/python.exe -m pytest <same file> -q -p no:cacheprovider -o addopts=""   (×2 more)
  172 passed, 16 xfailed · 172 passed, 16 xfailed   (no flaky test)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/approval_notification_service.py tests/unit/services/test_approval_notification_service.py --json <scratch>/mut_an.json
  Mutants: 201 · killed 184 · timeout 0 · survived 17 · score 92% (raw)
PYTHONPATH=<scratch>/an AN_VAR=<variant> .venv/Scripts/python.exe -m pytest <same file> -q -p no:cacheprovider -o addopts="" -p an_var -m "not xfail"   (14 variants, above)
.venv/Scripts/ruff.exe check tests/unit/services/test_approval_notification_service.py
  All checks passed!
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsupv\an\` (`an_var.py`, `trace.py`, `map.py`, `var.out`); mutation JSON `…\lowsupv\mut_an.json`.

## Round 2 — 2026-11-10

> **Verdict:** PASS
> Tests: 176 passed · 16 xfailed (reproduced ✅, 3 identical runs) · coverage 99% branch (only the unreachable 332->340, as in round 1)
> Mutation, targeted re-run of the real-gap lines 318–332 and 461: 13 mutants · 13 killed · 0 survived. Whole module: 194 killed / 194 counted → **100%** (the 7 equivalent dict keys at L467–473 are unchanged).
> Cases revision: 4 · spec: `detect_section_unconfirmed` R2a added

**New tests read against their cards.**
- APN-IA-19, IA-20 and IA-21 are one parametrized test with ids `APN-IA-19/20/21`. The Given is the card's: `required_approvals=2`, created by UC, and three approved approvers (UB in W1, the suspended US, and UD stored under W2). The call is the card's (`action="confirmed"`, invoice 77).
  - Then 1 checks the exact sorted recipients `[UB, UC]`.
  - Then 2 re-reads all four fields of UB's note.
  - Then 3 checks the exact preview with the right prefix (TO / EXP / WO).
  - Then 4 and 5 check that US and UD got nothing.
- APN-DS-09 builds a `SimpleNamespace` without `invoice_confirmed` and asserts `result is False`, as the card says.
- No other test changed.
- Traceability: 192 cards · 192 IDs in the test file · no unmatched ID · markers unchanged.

**Round-1 survivors:**
| Round-1 mutants | Line | Round 2 |
|---|---|---|
| #149, #178, #191 | L318 (`transfer_order`) | killed |
| #179, #192, #197 | L325 (`expense_order`) | killed |
| #193, #198, #200 | L332 (`work_order`) | killed |
| #199 `getattr(..., False)`→`True` | L461 | killed (DS-09). The other three mutants on that line are also killed. |

**`--runxfail`:** the same 16 tests fail with the same messages as in round 1 (the diff is empty).

**Findings:** none.

**Commands:**
```
lowsupv/r2/runs.sh services approval_notification_service an  → 176 passed, 16 xfailed (x3); --runxfail 16 failed, 176 passed; 99% branch
mutate.py app/services/approval_notification_service.py tests/unit/services/test_approval_notification_service.py --lines {318-332 | 461-461} --json lowsupv/r2/mut_an_<range>.json
  318-332: 9/9 killed · 461: 4/4 killed
```
