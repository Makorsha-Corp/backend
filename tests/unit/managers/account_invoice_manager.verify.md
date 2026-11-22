# Verification — `app/managers/account_invoice_manager.py`

> **Verdict:** PASS
> Tests: 204 passed · 86 xfailed (reproduced ✅) · coverage 100% branch (198 stmts / 60 branches, 0 missed)
> Mutation: 249 mutants · 238 killed · 11 survived → score 100% (238/238, after excluding 8 equivalent, 2 dead, 1 bug-path) — carried over, not re-run
> Source commit: e48a092 · Cases revision: 6
> Scope: re-verify after revision 6, fix round 2. Traceability ran in full. Fidelity: full for the 25 tests the notes list as changed (U-23, U-24, U-25, U-38, U-40, U-41, U-43, U-44, U-45, U-59, CF-09, RV-11, VD-07, RS-08, C-02, C-05, C-06, C-07, C-08, SUM-03, U-28, CF-06, RV-07, SY-06, SY-07), plus a complete pass over all 290 cases for two patterns: a "returns …" Then with no assertion on the return value, and an "unchanged" / "nothing written" Then checked on a few columns only. The reproduce runs were full. Mutation was not re-run: the source is unchanged at e48a092 and the fix round only added assertions.

## Summary
The three findings left open last time (11, 12, 13) are closed, and no new finding was raised. The two weaknesses that kept coming back are now absent from the whole file: all 104 cases whose Then says "returns …" assert on the returned value, and every invoice "unchanged" Then compares the full 23-column snapshot. The three "nothing written" cases count invoices and events in both workspaces. Runs match the notes exactly (204 passed, 86 xfailed, 100% branch) and three runs gave the same outcome. Each of the 13 xfail tests that gained a return assertion still fails on its designed "fails today on" line, one line after the new assertion. These tests can be trusted as they stand.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | Wrong setup (call shape) — **RESOLVED** | SY-01..SY-11 · `synccall` | Was: the wrapper always passed `is_manual=False`, so the default was never exercised. | `return M.sync_items_from_list(db, inv_row, items, user_id)`. Mutant `L553 False -> True` is KILLED. | — |
| 2 | Missing assertion — **RESOLVED** | U-13, U-14, U-15, U-16, U-21, U-27, U-42, CF-02, CF-03, RV-02, RV-03, VD-02, VD-09, RS-02, RS-03, RS-04 | Was: the return value was dropped. | Each test has `result = …` and `assert result.id == <row>.id`. | — |
| 3 | Weakened assertion — **RESOLVED** | RV-08 | Was: only `invoice_status` was re-read. | `assert snap_inv(db, vi.id) == before` (line 3548). | — |
| 4 | Wrong setup (minor) — **RESOLVED** | DEL-06, DEL-07, RV-03 | Was: `voided_by = U2`. | All three call `mk_pay(..., voided=True, created_by=u1.id)`. | — |
| 5 | Spec gap — **RESOLVED** | spec R9d / Notes G14; cases Conventions; C-14, U-37, U-50 | Was: a non-live PO was described as `is_deleted=True`. | Spec R9d defines "live" per type; the cases use `voided=True`. | — |
| 6 | Weakened assertion — **RESOLVED** | U-03, U-19, U-22, U-33, U-34, U-39, U-49, U-50, U-55, CF-10, RV-12, VD-08, RS-09 | Was: "returns the invoice" was checked only with `result is not None`. | All 13 assert `result.id == <row>.id`. A grep for `result is not None` returns nothing. | — |
| 7 | Spec gap — **RESOLVED** | spec `update_invoice` Inputs row, R2a, R2b, Errors row, Gap log G15 | Was: the spec did not say `order_type` can be sent on update. | R2b states the field, its normalisation, the 422, and that it counts as a sent field. | — |
| 8 | Wrong setup / dishonest xfail — **RESOLVED** | U-03 · `test_u_03__locks_invoice` (line 2314) | Was: the test ran on the confirmed `ci` fixture. | The test uses the draft `di` fixture and asserts `result.id == di.id` (line 2319). `--runxfail` fails on `locks_invoice()`, the designed assertion. | — |
| 9 | Wrong setup (changed action) — **RESOLVED** | U-49 · `test_u_49__order_id_resent_unchanged` (line 2935) | Was: `order_type` was left out of the update. | The update sends `order_type="purchase_order"`, `order_id=p1.id`, `description="New desc"`. | — |
| 10 | Case missing (new spec rule) — **RESOLVED** | spec `update_invoice` R2b; cases revision 6 | Was: no case cited R2b. | Cases U-56..U-60 exist and are implemented. | — |
| 11 | Weakened assertion — **RESOLVED** | U-59 · `test_u_59__confirmed_order_type_same_value_noop` (lines 3082–3096) | Was: "CI unchanged" was checked on four columns only. | Line 3087 `before = snap_inv(db, c.id)`; line 3090 `assert snap_inv(db, c.id) == before`. The four explicit checks stay (lines 3092–3095), and `assert_no_events` at line 3096. Passes. | — |
| 12 | Missing assertion — **RESOLVED** | U-23 (2550), U-24 (2559), U-25 (2568), U-38 (2774), U-40 (2803), U-41 (2812), U-43 (2838), U-44 (2847), U-45 (2860), CF-09 (3418), RV-11 (3573), VD-07 (3697), RS-08 (3839) | Was: the 13 xfail tests dropped the return value. | Each has `result = …` then `assert result.id == <row>.id` (lines 2554, 2563, 2573, 2782, 2807, 2816, 2842, 2851, 2869, 3423, 3577, 3701, 3843). `--runxfail`: each fails on the line after it, the designed assertion (see "Reproduce — touched xfails"). | — |
| 13 | Notes out of date — **RESOLVED** | `account_invoice_manager.notes.md` lines 7–9 and 277–285; test file lines 9 and 2277 | Was: revision-5 counts, an out-of-date BUG-625 maintainer note, and "G14" comments. | Notes lines 7–9: "All 290 cases … 290 items from 284 `def test_*` functions". The maintainer note lists U-38, U-45, U-53, U-56, U-57, then U-46 / U-60, then U-58 with BUG-631, and says U-59 must keep passing. A grep for `G14` in the test file returns nothing. The remaining "G14" mentions in the notes are in the Revision 4 / Revision 5 history, which is correct for those revisions. | — |

No open findings.

## Fidelity — changed tests (full)
- **U-23, U-24, U-25, U-40, U-44** (xfail BUG-632): Given and When as designed; `result.id` then `assert_no_events`. Both Then items asserted.
- **U-41** (xfail BUG-632): `result.id`, `len(rows) == 1`, `rows[0].metadata_json == {"notes": "New notes"}`. Exact.
- **U-43** (xfail BUG-620): `result.id`, re-read `updated_by is None`.
- **U-38, U-45** (xfail BUG-625, G15): the link is set on DI and flushed; `result.id`; re-read `order_type`, `order_id`, `updated_by`; exact event list with exact metadata. The marker reasons name BUG-625.
- **CF-09, RV-11, VD-07, RS-08** (xfail BUG-633): `result.id`, re-read `updated_by == u2.id`. CF-09 has the ITEM(DI, 100.00) the case requires.
- **U-59** (pass): see finding 11.
- **C-02, C-08** (pass): `assert created.id is not None`, and the row is then re-read **by `created.id`** with every listed column asserted exactly (C-02 also asserts the exact event list). The returned object is therefore tied to the row the case describes. This is the same check the cases file itself writes for C-01, C-25, C-26 and C-27 ("returns an invoice with `id` not None"); a create has no earlier row to compare an id with. Decision: accepted as a faithful "returns the invoice" check (best-practice default, delegated by reviewer).
- **SUM-03** (pass): `result == (0, 0, 0, 0)`, then `result[0] == 0` and `result[1..3] == Decimal("0")`. `None == 0` is false, so "not None" is covered.
- **C-05, C-06, C-07** (pass): status, exact detail, then `count_invoices` and `count_events` equal 0 for both `w1` and `w2`. This is the Conventions' "nothing written" (there is no pre-existing invoice row in these cases).
- **U-28** (pass): `snap_inv` before/after (line 2620, 2625), plus `account_id`, `updated_by` and `assert_no_events`.
- **CF-06** (pass): ITEM(VI, 100.00) set up before the snapshot; `snap_inv` before/after (3373, 3378), plus amount 1000.00, status voided, 0 events.
- **RV-07** (pass): `snap_inv` before/after (3528, 3533), plus status draft, `updated_by is None`, 0 events.
- **SY-06** (pass): the Given is now CI with `invoice_amount=Decimal("400.00")` and ITEM(CI, 400.00), as the case says. `result is None`, `snap_inv` before/after (3983, 3986), items `== [k.id]`, `invoice_amount == Decimal("400.00")`, `last_synced_at is None`, 0 events.
- **SY-07** (pass): `result is None`, `snap_inv` before/after (3999, 4002), items `== [k.id]`, amount 1000.00, 0 events.
- Extra mocks: none. Only `app.managers.account_invoice_manager.utcnow` is patched (line 96). No `try/except` in any test; the four `pytest.raises(Exception)` (lines 627, 2980, 3207, 3242) are LOG-05, U-52, DEL-07 and DEL-10, whose cases say "any `Exception` subclass".

## Fidelity — complete pass for the two recurring patterns (all 290 cases)
Method: a script parsed the Then column of every case and the AST of its test.

**(a) "returns …" Thens.** 104 cases have "returns" in the Then column. For each, the script looked for a name bound to the result of the manager call (`M.<method>(…)` or one of the wrappers `upd`, `delcall`, `cfcall`, `rvcall`, `vdcall`, `rscall`, `synccall`, `open_page`, `lpage`, `summarize`, `hub_summary`, `hub_page`) and for an `assert` that uses that name. Result: 104 of 104 assert on the returned value, and no test has a bare (unbound) manager call where the case names a return. I then read the first assertions of all 104:
- "returns the invoice [with `id == X.id`]" (61 cases across G4, GI, U, DEL, CF, RV, VD, RS): each asserts `result.id == <row>.id`.
- "returns `None`" (25 cases: LOG-01..03, RPS-01..07, RIA-01..04, RS-06, RS-07, SY-01..09): each asserts `result is None`.
- "returns `<tuple>`" (HS-01..04, SUM-01, SUM-02, SUM-03, SUM-06): each asserts `result == <the exact tuple>`.
- "returns an invoice with `id` not None" / "returns the invoice" on create (C-01, C-02, C-08, C-25, C-26, C-27): `created.id is not None` and a re-read by that id (decision above).
- L-42, EV-01, EV-02, IT-01: length / exact id list on the returned list.
The list and page cases written "→ […]" assert the returned ids by construction. Remaining instances: **none**.

**(b) "unchanged" / "nothing written" Thens.** 36 cases match `unchanged | nothing written | still | untouched | no new`. I read every one:
- Invoice row "unchanged" (14 cases: G4-01, G4-05, U-02, U-04, U-20, U-21, U-28, U-29, U-30, U-59, CF-06, RV-07, RV-08, SY-06) and SY-07 (same pattern, worded "same"): each takes `before = snap_inv(…)` before the action and asserts `snap_inv(…) == before` after it. `snap_inv` re-reads after `db.expire_all()` and compares `INV_COLS`, which is exactly the 23 columns of the Conventions' INV defaults (lines 410–417 against cases line 39).
- "nothing written" (C-05, C-06, C-07): invoices and events counted in W1 and W2.
- "still exists / still draft / still confirmed / still 1000.00" (RIA-02, DEL-03..07, DEL-09..13, CF-05, RV-10, VD-04, VD-06, RS-03, RS-04) and L-46: these Thens name one specific fact, not "unchanged", and the test asserts that fact after a re-read. Not instances of the pattern.
- VD-01 "PC unchanged (`voided_at == V0`, `voided_by=U1.id`, `void_note="manual void"`)": PC is a payment row. The Conventions define "Unchanged" only for invoice rows (the INV column list); for a payment row the parenthesis is the case's own list of what to check. The test asserts all three values exactly after `db.expire_all()` (lines 3626–3629), and the exact event metadata `payments_voided == 2` proves PC was not voided again. Decision: faithful to the case, not a finding (best-practice default, delegated by reviewer).
- SY-06 "items of CI == exactly [K] (unchanged)": the id list is asserted exactly, and the invoice has the full snapshot.
Remaining instances: **none**.

## Reproduce — touched xfails (`--runxfail`)
Each fails on the designed "fails today on" assertion, never on the added `result.id` line (which passes today):

| Case | Fails at | Failure |
|---|---|---|
| U-23 | line 2555 `assert_no_events` | 1 event present |
| U-24 | line 2564 `assert_no_events` | 1 event present |
| U-25 | line 2574 `assert_no_events` | 1 event present |
| U-38 | line 2784 | `assert 'purchase_order' is None` |
| U-40 | line 2808 `assert_no_events` | 1 event present |
| U-41 | line 2819 | metadata also contains `'description': 'Old desc'` |
| U-43 | line 2843 | `assert <U2 id> is None` (`updated_by`) |
| U-44 | line 2852 `assert_no_events` | 1 event present |
| U-45 | line 2871 | `assert 'purchase_order' == 'expense_order'` |
| CF-09 | line 3424 | `assert None == <U2 id>` (`updated_by`) |
| RV-11 | line 3578 | `assert None == <U2 id>` |
| VD-07 | line 3702 | `assert None == <U2 id>` |
| RS-08 | line 3844 | `assert None == <U2 id>` |

`--runxfail` gave exactly 86 failures, which is the xfail set, with 0 errors: none fails at setup or import.

## Surviving mutants
Carried over from the previous report (last full run plus the re-run of every surviving line). The source file is unchanged at e48a092 (`git diff HEAD` is empty for it). The fix round added assertions to the 25 listed tests and removed none. Its one setup change is SY-06 (CI amount 400.00 instead of 1000.00): this cannot turn a killed mutant into a survivor, because any mutant that lets `sync_items_from_list` run on a confirmed invoice (the `invoice_status != "draft"` guard, line 560) deletes item K, so `ids_list(items_of(...)) == [k.id]` and `assert_no_events` fail whatever the amount; SY-07 covers the same guard with amount 1000.00. The fidelity pass gave no reason to re-run.

| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 58 | L247 | `section="overview"` → `""` | equivalent | The DAO treats every value other than `"payable"`/`"receivable"` as overview (spec `list_accounts_hub_page` R5; AH-14 proves `"bogus"` behaves the same). | — |
| 117 | L366 | `"invoice_status"` → `""` in protected-pop list | equivalent | Not an `AccountInvoiceUpdate` field (pinned by U-11), so the pop is a no-op either way. | — |
| 118 | L366 | `"paid_amount"` → `""` | equivalent | Same reason: not a schema field (U-11). | — |
| 119 | L366 | `"void_note"` → `""` | equivalent | Same reason: not a schema field (U-11). | — |
| 120 | L366 | `"invoice_amount"` → `""` | bug-path (BUG-630) | Today's silent drop is the "Today" behavior of BUG-630 / R2a. Its only case (U-10) is xfail BUG-630 and is excluded. Once the fix lands, this pop is unreachable. | — (resolves when BUG-630 is fixed) |
| 121 | L366 | `"receiving_started"` → `""` | equivalent | Not a schema field (U-11). | — |
| 146 | L577 | `"item_manually_updated"` → `""` | dead | Inside the `is_manual=True` branch, which the spec (Q14 / Not specified) and deadcode-staging mark as dead. | — |
| 148 | L579 | `"Items updated"` → `""` | dead | Same dead `is_manual=True` branch. | — |
| 153 | L107 | `model_dump(exclude_none=True)` → `False` | equivalent | Every `AccountInvoiceCreate` field that can be `None` maps to a nullable column with no default. Fields that have column defaults are non-optional and never `None`. | — |
| 213 | L321 | `k != "updated_by"` → `k != ""` | equivalent | This only widens the `if changed:` guard. The body checks only `allow_payments` / `payment_locked_reason`, so no extra event is possible. | — |
| 232 | L332 | `k != "due_date"` → `k != ""` | equivalent | Same argument as #213. The due-date event is not duplicated. | — |

## Traceability
cases 290 · tests 290 collected (284 `def test_*` + RPS-01..07 as `pytest.param(id=…)` under one function; 204 passed + 86 xfailed) · unmatched: none · tests without a case ID: none · case IDs on more than one test: none · marker mismatches: none. Every `xfail BUG-NNN` case carries `xfail(strict=True)` whose reason names every listed BUG ID (U-58 names both BUG-625 and BUG-631), and no `pass` case carries an xfail marker. Every BUG ID used is present in `docs/testing/bugs.md`. Every test's docstring carries its case ID.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_account_invoice_manager.py -q -p no:cacheprovider --cov=app.managers.account_invoice_manager --cov-branch --cov-report=term-missing
  app\managers\account_invoice_manager.py     198      0     60      0   100%
  204 passed, 86 xfailed, 24 warnings in 23.48s

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_account_invoice_manager.py -q -p no:cacheprovider --runxfail -rf --tb=short
  86 failed, 204 passed, 9 warnings in 11.51s   (the 86 failures = exactly the xfail set; 0 errors)

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_account_invoice_manager.py -q -p no:cacheprovider   (repeat 1)
  204 passed, 86 xfailed, 9 warnings in 11.48s
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_account_invoice_manager.py -q -p no:cacheprovider   (repeat 2)
  204 passed, 86 xfailed, 9 warnings in 11.42s

audit script (AST over the test file + the cases table), modes:
  trace     → cases 290 · test ids 290 · funcs 284 · missing [] · extra [] · dups [] · no-case [] · pass 204 · xfail 86 · marker mismatches: none
  returns   → 104 cases with "returns" in Then · 104 with an assert on the bound result · 0 bare manager calls
  unchanged → 36 cases matched · read one by one (see the fidelity section) · 0 partial checks

git diff --quiet HEAD -- app/managers/account_invoice_manager.py   → no difference (source unchanged at e48a092)

tests/unit/_tools/mutate.py — not re-run (source unchanged; results carried over from the previous report)
```
Result line in the notes ("204 passed · 86 xfailed · 0 discrepancies · 0 errors — branch coverage 100% (198 stmts / 60 branches, 0 missed)") is reproduced exactly. Three runs gave the same outcome for every test, so there is no flaky test.

---

## 2026-11-14 — scoped round, cases revision 7 (completed-order freeze, O1 / F1–F7)

> **Current verdict:** NEEDS WORK — 2 case-missing findings for the case designer (F5 kind priority; freeze edges checked on one method only). No fidelity finding, no executor or describer item.
> Tests: 238 passed · 114 xfailed (reproduced ✅) · coverage 100% branch (198 stmts / 60 branches, 0 missed)
> Mutation: 249 mutants · 238 killed · 11 survived → score 100% (238/238, after excluding 8 equivalent, 2 dead, 1 bug-path). Full re-run on a temp copy.
> Hand variants of the O1 fix: 46 behaviour variants + 23 wrong kind-order permutations. 6 behaviour variants and 2 permutations survive (see below).
> Source commit: e48a092 (source unchanged) · Cases revision: 7 · Scope: DEL-01, DEL-11, DEL-14..24, RV-05, RV-06, RV-13..46, VD-14..28, U-61, U-62. Traceability, the reproduce runs and mutation ran over the whole file.

### Summary
All 64 new or changed tests match their cards. Every Then line is asserted, with exact LOCK/CNTXT/RCVTXT texts, the three session-clean checks right after the raise, full `snap_inv` comparisons and payment re-reads. The Givens are as designed, including W0 < W1 < W2, ST stages and CN/OI wiring. No extra mocks, and no `try/except`.

I wrote my own reference fix. With it, all 28 new strict xfails pass and all 238 pass cards still pass. With the markers kept, exactly those 28 XPASS. Most wrong fixes are caught: too-loose, too-strict, wrong check order, writing before the refusal, voiding payments despite the refusal. Two gaps remain:
- The F5 priority between expense orders and the other kinds is never tested.
- Several freeze edges are tested on one method only, so a fix with a separate check per method can get them wrong in delete or void and stay green.

### Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 14 | Case missing | F5 kind priority; RV-28..31 | The four cards cover the pairs (PO, SO), (SO, WO) and (EO, WO). They never cover (SO, EO) or (PO, EO). So two wrong priorities pass every card: `purchase, expense, sales, work` and `expense, purchase, sales, work`. | Reference with `REFV_KORDER=P,E,S,W` and `E,P,S,W`: 91 passed, 0 failed (scope `-k "del_ or rv_ or vd_ or u_61 or u_62"`). All other 22 permutations are killed by RV-29, RV-30 or RV-31. | **case designer**: add two strict xfail BUG-2730 cards. (a) Completed SO and completed EO both point at CI → `LOCK("sales order")`. (b) Completed PO and completed EO → `LOCK("purchase order")`. |
| 15 | Case missing | F1/F2/F3/F6 edges, delete and void | The shared freeze rules are stated once (F1–F7), but some edges are tested on only one method. A fix with a separate check per method can get them wrong in delete or void and stay green. Surviving variants: (a) **void** treats a POR/SOR of another workspace as a credit note, so a frozen invoice is voided and its payments are cancelled. Only RV-45/46 test this, on revert. (b) PO stage matched case-insensitively (`lower(name) == "complete"`) in delete only, or in void only. (c) Stage trimmed in void only. (d) Stage `LIKE 'Complete%'` in delete only. (e) A voided PO skipped (F3) in delete only. Only VD-24 tests F3. | Variants `cn_anyws_void`, `ci_lower_del`, `ci_lower_void`, `trim_void`, `prefix_del`, `skip_voided_del`: each 91 passed, 0 failed. The same variants applied to all methods are killed (RV-25..27, VD-24, RV-45/46). | **case designer**: at minimum (a), because money is at stake. Add a VD strict xfail BUG-2731 card: CI frozen by a completed W1 SO, plus POR(W0) and SOR(W2) with `invoice_id=C` → `LOCK("sales order")`, payment not voided. Optionally add one near-miss PO stage card (e.g. `complete`) for delete and for void, and a delete F3 card (completed PO with `voided=True` → LOCK). |

Earlier findings 1–13 stay resolved.

### Fidelity — new and changed tests (full read against the cards)
- **DEL-01, DEL-11** (changed Givens): P1 is built with `stage="Draft"`. E1 has `completed_at=None`, S1 `order_completed=False`, Wo1 `status="DRAFT"`. All Thens asserted (DEL-01 also checks 0 events in W1).
- **DEL-14..17**: exact LOCK(kind), session clean, `snap_inv == before`, item ids `== [item.id]`, order `invoice_id == D`, 0 events.
- **DEL-18..21**: return id, row gone, every referrer re-read with `invoice_id is None` (DEL-21 also checks `order_completed is True`). DEL-19/20 assert `w0.id < w1.id < w2.id`.
- **DEL-22**: R2 text exact. **DEL-23**: hand-opened savepoint; session clean before `sp.rollback()`, then re-read, as the card orders. **DEL-24**: `pytest.raises(Exception)`, which the card allows ("any `Exception`").
- **RV-05/06** (changed): `startswith` + `"receiv"` (RV-06: `"active payments" not in`), session clean, snapshot / status / paid / `updated_by`, 0 events. This is the card's own deliberate looseness; the exact text is in RV-13/14.
- **RV-13..18, RV-28..31, RV-33, RV-35, RV-37..40, RV-42**: exact text, session clean, full snapshot, 0 events. RV-35 and RV-42 also check `PA.is_voided is False`. RV-15 and RV-37 also check status and `updated_by`.
- **RV-19..27, RV-45/46**: return id + status draft (RV-19 also checks the exact event). RV-23/24 and RV-25..27 are param groups with the case ids.
- **RV-32, RV-34, RV-36, RV-41, RV-43, RV-44**: as their cards.
- **VD-14**: CI snapshot plus explicit status / paid / payment_status / void_note / updated_by; PA's four fields asserted to be None or False. **VD-15..17**: snapshot, PA `is_voided` / `voided_at`, 0 events. **VD-18..28**: as their cards (VD-26 checks the exact event and that OI stays confirmed).
- **U-61**: event set compared on (type, description, performed_by, metadata), which is stronger than the card. **U-62**: 3 events, exact type set.
- `--runxfail`: 114 failed, 238 passed, 0 errors. Each of the 28 new xfails fails on its designed line:
  - "DID NOT RAISE HTTPException": DEL-14..17, RV-15..18, RV-28..31, RV-37..39, VD-14..17, VD-24/25.
  - DEL-23: the not-null `invoice_payments.invoice_id` IntegrityError inside `pytest.raises(HTTPException)`.
  - RV-13/14: `detail == RCVTXT` against the old text.
  - RV-33 and RV-35: `== LOCK(...)` against the receiving and payments texts.
  - RV-40 and RV-42: `== CNTXT` against the receiving and payments texts.

### Reference fix and hand variants
`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\invlockv\refv.py` (my own, loaded with `-p refv`, never written to app/) wraps `delete_invoice`, `revert_to_draft` and `void_invoice` in-process. It applies:
- **Freeze**: an order of the same workspace whose `invoice_id` is this invoice and that is completed (PO `statuses.name == "Complete"`, SO `order_completed`, EO `completed_at IS NOT NULL`, WO `status == "COMPLETED"`; void/delete flags ignored). The kind follows the F5 order.
- **Credit note**: a POR/SOR row of the same workspace with this `invoice_id`.
- **Check order**: delete R2 → R2a → today. Revert R2 → R2a CNTXT → R2b LOCK → R3 RCVTXT → R4 → today. Void R2/R3 → R3a unless the invoice is a credit note → today.

It removes only the xfail markers whose reason is X2730/X2731/X2733/X2736.

| Run | Result |
|---|---|
| reference, full file | 266 passed, 86 xfailed (= the 238 pass cards plus the 28 O1 cards; the other bugs untouched) |
| reference, markers kept | 28 failed (all XPASS strict = exactly the 28 O1 cards), 238 passed, 86 xfailed |

Hand variants (scope: `-k "del_ or rv_ or vd_ or u_61 or u_62"`, 100 tests):

| Group | Variant | Killed by |
|---|---|---|
| too loose | PO `Receiving` counted complete (all methods / delete only) | DEL-18, RV-19, VD-18 / DEL-18 |
| too loose | stage `lower()=="complete"`, `trim()`, `LIKE 'Complete%'` (all methods) | RV-25..27 |
| too loose | stage near-miss in delete only or void only | **survive** (finding 15 b–d) |
| too loose | orders of any workspace (all / void only) | DEL-19/20, RV-20/21, VD-19/20 / VD-19/20 |
| too loose | invoice linked by `order_type`/`order_id` counted | DEL-21, RV-22, VD-21 |
| too loose | credit notes of any workspace (all / void only) | RV-45/46 / **survives** (finding 15 a) |
| too loose | voided PO skipped (all / delete only) | VD-24 / **survives** (finding 15 e) |
| too strict | freeze on `update_invoice` R3b edits | U-61, U-62 |
| too strict | credit note not exempt on void | VD-28 |
| check order | freeze before R2: delete / revert / void | DEL-22 / RV-32, RV-39 / VD-22, VD-23 |
| check order | credit-note check before R2 | RV-44 |
| check order | delete freeze after an R4 payment-history check | DEL-23 |
| check order | revert freeze after R3 / after R4 | RV-33 / RV-33, RV-35 |
| check order | revert freeze before credit note | RV-39 |
| check order | credit note after R3 / after R4 | RV-39, RV-40 / RV-39, RV-40, RV-42 |
| check order | receiving after payments | RV-06, RV-14 |
| kind text | kind of the first linked order (any state) | RV-28 |
| kind text | F5 order, 23 wrong permutations | 21 killed by RV-29/30/31; **`P,E,S,W` and `E,P,S,W` survive** (finding 14) |
| payments | payments voided (flushed / unflushed) before the LOCK refusal | VD-14..17 (+VD-01 when flushed) |
| writes first | `updated_by` flushed / event logged / column dirtied before the refusal (delete, revert, void each) | DEL-14..17 (dirty also DEL-23); RV-15..18, 28..31, 33..43; VD-14..17, 24, 25 |
| writes first | row deleted and flushed, then the refusal | DEL-14..17, DEL-23 |
| missing parts | no credit-note rule / no revert freeze / no delete freeze / old receiving text | RV-37..40, 42 / RV-15..18, 28..31, 33, 35 / DEL-14..17, 23 / RV-13, RV-14 |

### Surviving mutants (full re-run)
The same 11 survivors as before, same lines and mutations: #58 L247, #117–#121 L366, #146 L577, #148 L579, #153 L107, #213 L321, #232 L332. The classification above is unchanged: 8 equivalent, 2 dead, 1 bug-path (BUG-630). The 238 non-survivors are all KILLED, with 0 timeouts.

### Traceability
cases 352 · test ids 352 (param groups RPS-01..07, RV-23/24, RV-25..27) · missing none · extra none · duplicates none · tests without a case id none. 238 pass cases carry no xfail marker; 114 xfail cases carry `xfail(strict=True)` whose reason names every listed BUG id, and every id is in `docs/testing/bugs.md` (BUG-2730/2731/2733/2736 present).

### Commands run
```
mutate.py app/managers/account_invoice_manager.py tests/unit/managers/test_account_invoice_manager.py --json …\invlockv\mut.json   (TMP/TEMP = …\invlockv\tmp, private COVERAGE_FILE)
  Mutants: 249 · killed 238 · timeout 0 · survived 11 · score 96%   → 238/238 after exclusions
pytest <file> -q -p no:cacheprovider --cov=app.managers.account_invoice_manager --cov-branch --cov-report=term-missing   (COVERAGE_FILE=…\invlockv\.coverage)
  app\managers\account_invoice_manager.py  198  0  60  0  100%  ·  238 passed, 114 xfailed
pytest <file> -q -p no:cacheprovider --runxfail -rf --tb=line
  114 failed, 238 passed (0 errors)
pytest <file> -q -p no:cacheprovider  ×3
  238 passed, 114 xfailed · 238 passed, 114 xfailed · 238 passed, 114 xfailed   (no flaky test)
PYTHONPATH=…\invlockv REFV=ref pytest <file> -p refv            → 266 passed, 86 xfailed
PYTHONPATH=…\invlockv REFV=ref REFV_KEEPX=1 pytest <file> -p refv → 28 failed (XPASS strict), 238 passed, 86 xfailed
REFV=<variant> / REFV_KORDER=<perm> pytest <file> -p refv -k "del_ or rv_ or vd_ or u_61 or u_62"   (results: …\invlockv\variants.txt, korder.txt)
trace_v.py (AST + cases table)  → cases 352 · found 352 · pass 238 · xfail 114 · mismatches []
ruff check <file>               → All checks passed!
git status app/managers/account_invoice_manager.py → unchanged at e48a092
```
The notes' Result line ("238 passed · 114 xfailed · 0 discrepancies · 0 errors — branch coverage 100% (198 stmts / 60 branches, 0 missed)") is reproduced exactly. No new bug: BUG-2737..2749 unused; `docs/testing/bugs.md` not touched.

---

## Round 2 — 2026-11-14 (cases revision 8: findings 14 and 15)

> **Current verdict:** PASS
> Tests: 244 passed · 118 xfailed (reproduced ✅) · coverage 100% branch (198 stmts / 60 branches, 0 missed) · 3 plain runs identical (no flake)
> Mutation: carried over from the round above (249 · 238 killed · 11 survived → 100% after 8 equivalent, 2 dead, 1 bug-path). Not re-run: the source is unchanged at e48a092, and revision 8 only added tests.
> Cases revision: 8 · Scope: RV-47, RV-48, VD-29, DEL-25..28, VD-30..32

**Findings 14 and 15: RESOLVED.**
- **Fidelity.** All 10 new tests match their cards: Given, exact LOCK text, session clean, `snap_inv`, payment fields, item ids, order `invoice_id` and 0 events. DEL-25..27 and VD-30..32 are param groups with their case ids. VD-29 asserts `w0.id < w1.id < w2.id`.
- **`--runxfail`.** RV-47, RV-48, VD-29 and DEL-28 each fail on "DID NOT RAISE HTTPException", their designed line.
- **Traceability.** Cases 362, found 362, 244 pass and 118 xfail, no mismatches.

Re-run of the surviving variants against `refv.py`. Each one now fails a card:

| Variant | Killed by |
|---|---|
| F5 order `P,E,S,W` | RV-47 |
| F5 order `E,P,S,W` | RV-47, RV-48 |
| void credit-note check ignores workspace (`cn_anyws_void`) | VD-29 |
| delete stage `lower()` (`ci_lower_del`) | DEL-25 |
| delete stage `LIKE 'Complete%'` (`prefix_del`) | DEL-27 |
| void stage `lower()` (`ci_lower_void`) | VD-30 |
| void stage `trim()` (`trim_void`) | VD-31 |
| delete skips a voided PO (`skip_voided_del`) | DEL-28 |

The correct order `P,S,E,W` passes every card. The reference fix on the full file gives 276 passed and 86 xfailed (244 pass cards plus the 32 O1 cards). No new bug was found.

```
pytest <file> -q -p no:cacheprovider ×3                  → 244 passed, 118 xfailed (×3)
pytest <file> --cov=… --cov-branch                       → 198 0 60 0 100% · 244 passed, 118 xfailed
pytest <file> --runxfail -k "rv_47 or rv_48 or vd_29 or del_28" → 4 failed (DID NOT RAISE)
REFV=ref pytest <file> -p refv                           → 276 passed, 86 xfailed
REFV=<variant> / REFV_KORDER=<perm> pytest <file> -p refv  → as in the table
trace_v.py                                               → 362/362, mismatches []
```

---

## Round 3 — 2026-11-17 (cases revision 9: `void_invoice` R3c, BUG-2788)

> **Current verdict:** NEEDS WORK — 1 case-missing finding (16) for the case designer. No fidelity finding, nothing for the executor or the describer.
> Tests: 250 passed · 127 xfailed (reproduced ✅) · coverage 100% branch (198 stmts / 60 branches, 0 missed) · 3 plain runs identical (no flake)
> Mutation: carried over (249 · 238 killed · 11 survived → 100% after exclusions). Not re-run: the source is unchanged at e48a092, and revision 9 only added or tightened tests.
> Cases revision: 9 · Scope: VD-12, VD-26..28 (changed), VD-33..47 (new), POR/SOR default `status "pending"`, `paid False`

### Fidelity
All new and changed tests match their cards.
- **Builders:** `mk_por` / `mk_sor` now default to `status="pending"`, `paid=False`.
- **Changed cards:** VD-26..28 pin `status="pending"`; their invoice-side Thens are unchanged. VD-12 changed its docstring only (Errors row 6).
- **VD-33/34:** invoice voided, `paid_amount` 0.00, payment voided, return `status == "voided"` and `paid is False`.
- **VD-35/36:** exact RETTXT, session clean, `snap_inv`, payment fields, return `completed` / `paid True`, 0 events.
- **VD-37:** return unchanged and the exact event. **VD-38:** return unchanged.
- **VD-39/40:** RETTXT, not LOCK. VD-40 also snapshots OI.
- **VD-41/42:** the R2 / R3 text, with the return still `completed`.
- **VD-43:** the return is voided.
- **VD-44/45:** `w0 < w1 < w2`, and both foreign returns are unchanged.
- **VD-46/47:** `cap.locks_table(...)`, which needs a SELECT on that table with `FOR UPDATE`.

`--runxfail`: each of the 9 new xfails fails on its designed line:
- VD-33, VD-34, VD-43: return `'pending' == 'voided'`.
- VD-35, VD-36, VD-39, VD-40: "DID NOT RAISE HTTPException".
- VD-46, VD-47: `locks_table` is False.

Traceability: 377 of 377 cases found, 250 pass and 127 xfail, no mismatches. BUG-2788 is in `bugs.md`.

### Reference fix (R3c)
`refv.py` now adds R3c to `void_invoice`, after R2 / R3 and after the freeze check, for a credit note only. It reads the return row of this workspace `FOR UPDATE`.
- Return `completed` → 400 RETTXT, nothing written.
- Return `pending` → the normal void, then the return gets `status = "voided"` and the return manager's `sync_return_paid` sets `paid = False`. Flushed.
- Return `voided` → the normal void, return untouched.

| Run | Result |
|---|---|
| reference, full file | 291 passed, 86 xfailed (= the 250 pass cards plus 32 O1 and 9 R3c cards) |
| reference, markers kept | 41 failed (all XPASS strict), 250 passed, 86 xfailed |
| reference with R3c switched off | exactly the 9 R3c cards fail |

### Hand variants (scope `del_ or rv_ or vd_`)
| Variant | Killed by |
|---|---|
| return check ignores workspace, both for credit-note detection and for the return lookup | VD-44, VD-45 |
| return **lookup** ignores workspace; credit-note detection stays correct | **survives** (finding 16) |
| completed return voided anyway (void goes ahead, return left as is) | VD-35, VD-36, VD-39, VD-40 |
| completed return voided anyway, and the return set to `voided` | VD-35, VD-36, VD-39, VD-40 |
| pending return not cancelled | VD-33, VD-34, VD-43 |
| pending return: status set but `paid` not reset | VD-33, VD-34 |
| R3c before R2 / before R3 | VD-41, VD-42 / VD-42 |
| no `FOR UPDATE` on the return | VD-46, VD-47 |
| freeze checked on credit notes before R3c | VD-28, VD-39, VD-43 |
| payments voided, or an event logged, before the RETTXT refusal | VD-35, VD-36 / VD-35, VD-36, VD-39, VD-40 |

### Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 16 | Case missing | `void_invoice` R3c ("the return row … **of this workspace**"); VD-44/45 | VD-44/45 only cover an invoice that is not a credit note in W1. No card has a real W1 credit note that another workspace's return row also points at. So a fix that detects the credit note correctly but picks its return without the workspace filter stays green. Such a fix can refuse on another workspace's completed return, or void that workspace's pending return. | Variant `r3c_lookup_anyws`: 0 failures in `del_ or rv_ or vd_`. | **case designer**: add a strict xfail BUG-2788 card. CN for P1/S1 with its own R = SOR(W1) `pending`, plus POR(W0) `completed` and POR(W2) `pending`, both with `invoice_id=CN.id` → void goes ahead, R `status == "voided"`, POR(W0) still `completed`, POR(W2) still `pending`. |

Findings 1–15 stay resolved. No new bug: `docs/testing/bugs.md` not touched.

```
pytest <file> -q -p no:cacheprovider ×3                → 250 passed, 127 xfailed (×3)
pytest <file> --cov=… --cov-branch                     → 198 0 60 0 100% · 250 passed, 127 xfailed
pytest <file> --runxfail -k "<the 9 R3c xfails>"       → 9 failed on the designed lines
REFV=ref pytest <file> -p refv                         → 291 passed, 86 xfailed
REFV=ref REFV_KEEPX=1 …                                → 41 failed (XPASS strict), 250 passed, 86 xfailed
REFV=ref REFV_R3C=0 … -k vd_                           → exactly VD-33..36, 39, 40, 43, 46, 47 fail
REFV=<variant> … -k "del_ or rv_ or vd_"               → as in the table
trace_v.py                                             → 377/377, mismatches []
```

---

## Round 4 — 2026-11-19 (cases revision 10: VD-48)

> **Current verdict:** NEEDS WORK — finding 16 is only partly closed; new finding 17 (VD-48 setup order) for the case designer. No fidelity finding.
> Tests: 250 passed · 128 xfailed (reproduced ✅) · coverage 100% branch (198 / 60, 0 missed) · 3 plain runs identical (no flake)
> Mutation: carried over (source unchanged at e48a092; revision 10 only adds a test).
> Cases revision: 10 · Scope: VD-48. Traceability: 378 of 378 found, 250 pass / 128 xfail, no mismatches.

**Fidelity — VD-48:** matches its card.
- Given: OI, P1 `Draft` with OI, CN, R = POR(W1) `pending` / `paid False`, R0 = POR(W0) `completed`, RY = POR(W2) `pending`, and `w0 < w1 < w2` asserted.
- Thens: no exception; `result.id == CN.id`; CN voided; R0 `completed`; RY `pending` with `paid False`; R `voided` with `paid False`.
- `--runxfail`: it fails on the designed line, `assert 'pending' == 'voided'` (R).
- Reference fix on the full file: 292 passed, 86 xfailed.

**No-workspace-filter variants of R3c:**

| Variant | Result |
|---|---|
| return lookup ignores workspace, takes the **first row by id** (`r3c_lookup_anyws`) | **survives** |
| same, takes the last row by id (`r3c_lookup_anyws_desc`) | killed by VD-48 |
| all rows of any workspace: refuse if any is completed (`r3c_lookup_anyws_any`) | killed by VD-48 |
| credit-note detection and lookup both unfiltered (`r3c_anyws`) | killed by VD-44, VD-45 |

| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 16 | Case missing — **partly resolved** | VD-48 | VD-48 now exists and kills two of the three unfiltered lookups. See 17 for the one that still passes. | above | — |
| 17 | Case missing (setup order) | VD-48 Given | R (W1) is inserted before R0 and RY, so it has the lowest id. A lookup with no workspace filter that takes the first matching row (by id, or plain `.first()` in physical order) still picks R and passes. That is the most likely shape of the bug. The card does not fix the insert order, so the executor is faithful. | `r3c_lookup_anyws`: 0 failures in `-k vd_`. | **case designer**: make VD-48's Given insert R0 = POR(W0) `completed` **before** R, and RY after R (R0 → R → RY, each flushed). Then an unfiltered first-row lookup hits R0 and wrongly refuses, and a last-row one hits RY. Optionally also put a SOR(W0) `completed` on the CN, so a lookup that checks the other return table first is caught too. |

```
pytest <file> -q -p no:cacheprovider ×3            → 250 passed, 128 xfailed (×3)
pytest <file> --cov=… --cov-branch                 → 198 0 60 0 100%
pytest <file> --runxfail -k vd_48                  → 1 failed at line 5220 ('pending' == 'voided')
REFV=ref pytest <file> -p refv                     → 292 passed, 86 xfailed
REFV=r3c_lookup_anyws[_desc|_any] / r3c_anyws … -k vd_  → as in the table
trace_v.py                                         → 378/378, mismatches []
```

---

## Round 5 — 2026-11-19 (cases revision 11: VD-48 build order, finding 17)

> **Current verdict:** PASS
> Tests: 250 passed · 128 xfailed (reproduced ✅) · coverage 100% branch (198 / 60, 0 missed) · 3 plain runs identical (no flake)
> Mutation: carried over (249 · 238 killed · 11 survived → 100% after exclusions); `app/managers/` unchanged at e48a092.
> Cases revision: 11 · Scope: VD-48 · Traceability 378/378, 250 pass / 128 xfail, no mismatches.

**Findings 16 and 17: RESOLVED.**
- **VD-48 matches its card.** The Given builds R0 (W0, `completed`), then R (W1, `pending`, `paid False`), then RY (W2, `pending`), one `mk_por` each, and each one flushes. It asserts `r0.id < r.id < ry.id` and `w0 < w1 < w2`. The Thens are unchanged and exact.
- **`--runxfail`:** VD-48 fails on its designed line 5222 (`'pending' == 'voided'` on R).
- **Reference fix:** 292 passed, 86 xfailed.
- **No-workspace-filter variants are now all killed by VD-48:** first match by id (`r3c_lookup_anyws`), last match (`_desc`), and refuse-if-any-completed (`_any`).

No open findings. `bugs.md` not touched.
