# Verification — `app/dao/account_invoice.py`

> **Current verdict (Round 2, 2026-11-14):** PASS — cases Rev 4 · 177 passed · 42 xfailed · the 4 routed survivors are killed
> **Round 1 verdict:** NEEDS WORK (4 case-missing survivors; no fidelity or traceability finding)
> Tests: 174 passed · 42 xfailed (reproduced ✅, every xfail fails on its card's line) · coverage 99% branch (134 stmts, 46 branches; miss line 472 = dead `get_by_order`)
> Mutation: 185 mutants · 166 killed · 19 survived → score 97.6% (166 / 170, after excluding 8 equivalent, 3 dead, 4 bug-path)
> Source commit: e48a092 · Cases revision: 3

## Summary
The tests can be trusted. All 216 cards trace to exactly one test, in card order. Every Then line is asserted at the card's strength. Nothing is mocked beyond the UP-25 commit spy, and every xfail fails where its card says. The three Revision-3 card fixes (AIV-ES-01, ES-02, ST-03) are in. The notes record them (notes 18:01:06, test file 17:59:08, cases 17:58:26), and the three tests assert the Rev 3 values with no marker and pass. Mutation found four real gaps. Each is a boundary or default the spec states but no card checks, so they go to the **case designer**:
- the `open_balance_only=False` default of `list_invoices_page_filtered`
- the receivable side of the hub `> 0` section filter
- the `> 0` boundary of `update_paid_amount` R4

No new code bug: 12 hand variants (below) all behaved as the spec says.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `list_invoices_page_filtered` R1/R12, L366 (default `open_balance_only=False`) | No card calls `list_invoices_page_filtered` without `open_balance_only` on a paid, voided or draft invoice, so the default is never observed. `list_invoices_page` always passes it explicitly. The real caller (`GET /accounts/{id}/invoices/`) relies on the default. Flipping it would hide every paid invoice there. | mutant #57 `False -> True` survived | case designer |
| 2 | case-missing | `list_accounts_hub_page` R3, L277 (receivable `> 0`) | AH-18 pins the 0.00 / 0.01 boundary for `section="payable"` only. AH-14 uses a 10.00 receivable, so both `>=` and `> 1` pass. A receivable twin of AH-18 is needed: a 0.00 receivable account is left out, a 0.01 one is kept. | mutants #118 `Gt -> GtE`, #135 `0 -> 1` survived | case designer |
| 3 | case-missing | `update_paid_amount` R4, L491 (`paid_amount > 0`) | R4 is checked only with sums ≥ 2.12 (and 0 / negative for R5). No card sums to a value in (0, 1], e.g. a 0.01 payment on an unpaid invoice → `partial`. | mutant #128 `0 -> 1` survived | case designer |
| 4 | cosmetic | test file docstring, line 3 | The module docstring still says "Implements … cases.md (revision 2)". The cases are Revision 3. | `grep revision test_account_invoice.py` | executor (when next touching the file) |

Not findings (checked):
- HS-13 / SI-13 check `all("FOR UPDATE" not in s for s in rec.sqls(...))`. A bare `all()` passes on an empty list. My hand variant h10 confirms the lists hold 4 and 2 statements, so the check is not vacuous. The card says "the SELECT" because the methods send several (noted by the executor).

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 33 | 472 | `return …` → `return None` | dead | `get_by_order`: spec Not specified / Q1; in `dead-code-removal-checklist.md`; no caller (grep of `app/`, `scripts/`, `tests/`: every other `get_by_order` hit is another DAO) | — |
| 126 | 475 | `==` → `!=` | dead | `get_by_order` | — |
| 127 | 476 | `==` → `!=` | dead | `get_by_order` | — |
| 49 | 249 | default `section "overview"` → `""` | equivalent | `""` takes the same `else` (no balance filter) as `"overview"`, and `section` is read nowhere else | — |
| 122 | 398 | priority `else_=1` → `2` | equivalent | every non-prioritised row gets the same value, still sorted after `0`; the order inside the group is unchanged | — |
| 173 | 301 | `row[start + 1] is not None` → `row[start + 2]` | equivalent | positions 2 and 3 come from the same outer-joined sub-select row. When it exists, `outstanding_total` (coalesced) and `open_count` (count) are both non-NULL; when it does not, both are NULL | — |
| 174 | 302 | `row[start + 2] is not None` → `row[start + 3]` | equivalent | same argument: `open_count` and `has_overdue` (`max(case …)` over ≥ 1 row) are NULL together | — |
| 179 | 227 | label `"open_count"` → `""` | equivalent | sub-select columns are read by position in `_reshape_accounts_hub_row`; the outer query names only `.account_id` and `.outstanding_total` | — |
| 180 | 230 | label `"has_overdue"` → `""` | equivalent | same: read by position only | — |
| 181 | 224 | `coalesce(sum(…), 0)` → `coalesce(…, 1)` in the sub-select | equivalent | a grouped row has ≥ 1 invoice and both amount columns are NOT NULL, so the sum is never NULL | — |
| 183 | 229 | `case(… , 1)` → `2` | equivalent | `_reshape_accounts_hub_row` applies `bool()`; 1 and 2 both give `True` | — |
| 134 | 148 | `'overdue'` → `''` in `open_balance_only` `IN` | bug-path | BUG-634 / BUG-635: `overdue` is never stored, and the intended R12 is confirmed + `unpaid`/`partial` only | — |
| 172 | 238 | `'overdue'` → `''` in the sub-select `IN` | bug-path | same, `_open_balance_subquery` R1 [BUG-634] | — |
| 185 | 229 | `'overdue'` → `''` in `has_overdue` | bug-path | `_open_balance_subquery` R2 [BUG-635]; only AH-03 / AH-33 / AH-34 (xfail) target it | — |
| 145 | 326 | `'overdue'` → `''` in `overdue_count` | bug-path | `summarize_open_hub_type` R3 [BUG-635]; only HS-08 / HS-14 (xfail) target it | — |
| 57 | 366 | default `open_balance_only False` → `True` | case-missing | Finding 1 | case designer |
| 118 | 277 | receivable `> 0` → `>= 0` | case-missing | Finding 2 | case designer |
| 135 | 277 | receivable `> 0` → `> 1` | case-missing | Finding 2 | case designer |
| 128 | 491 | `paid_amount > 0` → `> 1` | case-missing | Finding 3 | case designer |

A second run over lines 21–35 (the escaping helpers, after the Rev 3 test fix): 14 mutants, 14 killed.

## Hand variants (verifier's own, scratch `test_hand_ai.py`; all 12 passed; no new bug)
| # | Variant | Result |
|---|---|---|
| h01 | HR-16 reverse shape: a W0 invoice on a W1 account | not in W1's hub row, hub KPI, account count or list ✅ |
| h02 | voided invoice with a legacy non-zero paid amount (hub money) | open 0 on the hub, summary money 0, KPI 0 ✅ |
| h03 | overpaid "paid" invoice (open / outstanding scope) | not in `section="payable"` ✅ |
| h04 | name search on a closed account (list and hub) | nothing found ✅ |
| h05 | `%` in an order-number search (order side) | literal ✅ |
| h06 | 25-digit ASCII search (past bigint) | no error, empty ✅ |
| h07 | leading zeros `00<id>` | matches the id numerically (R10 "equals that number") ✅ |
| h08 | tie-break: three same-name accounts, `section="payable"`, paged 2 + 2 | id order, no row lost or repeated ✅ |
| h09 | no-lock on `count_accounts_with_any_open_balance` and `list_invoices_page` | no `FOR UPDATE`, nothing written ✅ |
| h10 | HS-13 / SI-13 statement lists non-empty | 4 and 2 SELECTs ✅ |
| h11 | prioritised PO id that exists only on a W2 invoice | W1 page unchanged, total 1 ✅ |
| h12 | payable 1,000.00 + receivable 200.00 paid 50.00 (received vs owed on the hub) | payable 1000.00, receivable 150.00, kept apart ✅ |

Not applicable to this DAO: numbering (it numbers nothing), transfer stages, the expense timeline. Payable + receivable added together in `summarize_invoices` is BUG-2692, already pinned by OQ41-01…07.

## Traceability
Cases 216 · tests 216 · unmatched: none · duplicates: none · marker mismatches: none. 174 pass cards, none marked. 42 `xfail BUG-n` cards are all `strict=True`, and each reason names its card's BUG ID. BUG-622, 623, 634, 635, 636, 637, 2690, 2691 and 2692 are all in `docs/testing/bugs.md`. No DISCREPANCY markers are left.

`--runxfail` locator (own plugin `failat_v.py` + `check_v.py`): 42 / 42 fail where the card says.
- 34 fail on the named Then line.
- FQ-19, FQ-44, AH-03, AH-33, AH-34, HS-08, HS-14 fail in the When call with `TypeError: … got an unexpected keyword argument 'today'`, as their cards say.
- FQ-36 fails in the When call with `ValueError` (`int("²")`), as its card says.

Revision 3 fixes: ES-01 asserts `r"a\%b\_c\\d"`, ES-02 `r"\\\%\\\_"`, ST-03 `r"%Ab\_c\\D%"`, with no marker. All three pass and are recorded in the notes. File mtimes seen: cases 17:58:26, test 17:59:08, notes 18:01:06 (2026-11-14). Every run below is after 17:59:08.

## Commands run
```
COVERAGE_FILE=…/bigdaov/ai/.coverage .venv/Scripts/python.exe -m pytest tests/unit/dao/test_account_invoice.py -q -p no:cacheprovider -o addopts="" --cov=app.dao.account_invoice --cov-branch --cov-report=term-missing
  app\dao\account_invoice.py  134  1  46  0  99%  472  ·  174 passed, 42 xfailed in 22.45s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_account_invoice.py -q -p no:cacheprovider -o addopts="" --runxfail -rf
  42 failed, 174 passed in 10.84s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_account_invoice.py -q -p no:cacheprovider -o addopts=""   (×2)
  174 passed, 42 xfailed in 10.98s · 174 passed, 42 xfailed in 10.66s   (stable)
FAILAT_OUT=… PYTHONPATH=…/bigdaov/ai .venv/Scripts/python.exe -m pytest … --runxfail -p failat_v ; check_v.py
  42 / 42 on the designed line (8 in the When call with the card's TypeError / ValueError)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/account_invoice.py tests/unit/dao/test_account_invoice.py --timeout 300 --json …/bigdaov/ai/mut.json
  Mutants: 185 · killed 166 · timeout 0 · survived 19 · score 90% (raw)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/account_invoice.py tests/unit/dao/test_account_invoice.py --lines 21-35
  Mutants: 14 · killed 14 · survived 0
PYTHONPATH=. .venv/Scripts/python.exe -m pytest …/bigdaov/ai/test_hand_ai.py -q -p no:cacheprovider -o addopts="" -p tests.unit.conftest --rootdir=.
  12 passed
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaov\ai\` (trace.py, failat_v.py, check_v.py, test_hand_ai.py, mut.json, mut_21_35.json, .coverage).

The notes' Result line (174 / 42, 99%, line 472) matches these runs.

## Round 2 — 2026-11-14

> **Current verdict:** PASS
> Tests: 177 passed · 42 xfailed (3 identical runs) · coverage 99% branch (134 stmts, 46 branches; miss line 472 = dead `get_by_order`)
> Mutation (survivor lines only): 6 mutants · 6 killed · 0 survived. Full-module score now 170 / 170 = 100% after excluding 8 equivalent, 3 dead, 4 bug-path.
> Files read: cases Rev 4 (18:23:15) · test file (18:26:05) · notes (18:27:40)

**New cards vs tests.** Cases Rev 4 adds AIV-PF-19, AIV-AH-35 and AIV-UP-26, retires no ID, and changes no other card. I read each test against its card:
- **PF-19:** builds N1 plain, N2 paid, N3 voided, N4 draft. It calls without `open_balance_only` and asserts `ids(result[0]) == [n4, n3, n2, n1]` and `result[1] == 4`.
- **AH-35:** `hubclean`, then AZ with a receivable 0.00 and AO with a receivable 0.01, on `section="receivable"`. It asserts `hids == [AO]`, `result[1] == 1`, and `outstanding_total == Decimal("0.01")`.
- **UP-26:** a 0.01 payment on an unpaid invoice. It asserts `result.id`, `payment_status == "partial"`, and a re-read of `paid_amount == 0.01` with `payment_status == "partial"`.

All three are faithful: every Then line is asserted at the card's strength, with no marker and no mock. The round-1 executor nit is fixed (the module docstring now says "Revision 4"). Traceability over the whole file: 219 cards, 219 tests, no unmatched ID and no marker mismatch.

**Routed survivors.** The cases Rev 4 header names each card's target mutant. Every kill below was "1 failed". The only tests added since round 1 are these three cards, and the earlier tests passed against the same mutants in round 1, so the one failing test is the new card.

| R1 # | Line | Mutation | Round 2 | Killed by |
|---|---|---|---|---|
| 57 | 366 | default `open_balance_only` False → True | KILLED | AIV-PF-19 |
| 118 | 277 | receivable `> 0` → `>= 0` | KILLED | AIV-AH-35 (Then 1–2: AZ at 0.00 is excluded) |
| 135 | 277 | receivable `> 0` → `> 1` | KILLED | AIV-AH-35 (Then 1–3: AO at 0.01 is kept) |
| 128 | 491 | `paid_amount > 0` → `> 1` | KILLED | AIV-UP-26 |

The other two mutants on line 491 (negated `if`, `>` → `>=`) were already killed in round 1 and are killed again.

**Findings:** none. **Routed:** nothing.

### Round 2 commands
```
.venv/Scripts/python.exe …/bigdaov/ai/trace.py tests/unit/dao/account_invoice.cases.md tests/unit/dao/test_account_invoice.py docs/testing/bugs.md
  cards 219 · tests 219 (no mismatch)
COVERAGE_FILE=…/bigdaov/ai/r2/.coverage .venv/Scripts/python.exe -m pytest tests/unit/dao/test_account_invoice.py -q -p no:cacheprovider -o addopts="" --cov=app.dao.account_invoice --cov-branch --cov-report=term-missing
  app\dao\account_invoice.py  134  1  46  0  99%  472  ·  177 passed, 42 xfailed in 21.47s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_account_invoice.py -q -p no:cacheprovider -o addopts=""   (×2)
  177 passed, 42 xfailed in 10.91s · 177 passed, 42 xfailed in 10.99s   (stable)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/account_invoice.py tests/unit/dao/test_account_invoice.py --lines 277-277 --json …/r2/mut_277.json
  Mutants: 2 · killed 2 · survived 0
… --lines 366-366 --json …/r2/mut_366.json
  Mutants: 1 · killed 1 · survived 0
… --lines 491-491 --json …/r2/mut_491.json
  Mutants: 3 · killed 3 · survived 0
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaov\ai\r2\`.
