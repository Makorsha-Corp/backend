# Verification — `app/dao/expense_order.py`

> **Current verdict (Round 2, 2026-11-14): PASS.** Cases Rev 3 · 203 passed · 47 xfailed · 2 xpassed (non-strict SF-06, SF-23), the same in 3 runs · every round-1 routed survivor is now killed by a named card · no unfaithful tests. See "Round 2 — 2026-11-14" at the end.

> **Verdict:** NEEDS WORK (five missing cards for the case designer; the tests themselves are faithful)
> Tests: 197 passed · 46 xfailed · 2 xpassed (non-strict SF-06, SF-23) (reproduced ✅) · coverage 99% branch (187 statements, 1 missed: line 466, unreachable; 70 branches, 1 partial)
> Mutation: mutate.py 313 mutants · 285 killed · 28 survived → score 97% (285 / 294, after excluding 19 equivalent, 0 dead, 0 bug-path). Hand variants 70 · 57 killed · 13 survived → score 95% (57 / 60, after excluding 5 equivalent, 5 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
The 245 tests are faithful to their cards. Every case ID appears exactly once. Every Then line is asserted as written and in card order, with no extra mocks. Every strict xfail names its bug and fails on the card's "Fails today on" line. Three plain runs and the coverage run all give 197 / 46 / 2. Owner answers OQ-42, OQ-43 and OQ-44 (BUG-2717, BUG-2718, BUG-2719) are pinned as strict xfails, and their pass halves are in place, including SA-12: an open order with a draft or a voided invoice counts the full order total.

The survivors expose five missing cards. All five are money or dashboard figures:
- A figure that sums to exactly 0.00 shows as 1. No card has a category, stage, account, timeline bucket or invoice whose total is 0.00. Each `Decimal(str(x or 0))` mutated to `or 1` survives.
- The unpaid samples can be sorted by invoice amount instead of by what is still owed. No card has two invoices in one bucket where those two orders differ.
- An account-less order can take one of the five open-by-account slots.
- Search on a category outside the three labels has no card.
- One card is missing after BUG-2719: a completed order whose invoice is voided.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `aggregate_financial_snapshot_filtered` R1, R5, R6; `aggregate_financial_snapshot_actionable` R5, R6, R9 (lines 318, 352, 383, 424, 431, 467) | No card has a money figure that is exactly 0.00. `Decimal("0.00")` is falsy, so `x or 0` → `x or 1` turns a 0.00 total into 1 and goes unnoticed. HS-04 covers this for hub stats only (line 281 mutant killed). | mutate.py #246 (L318), #276 (L352:66), #279 (L383), #256 (L424), #303 (L431), #284 (L467) SURVIVED | **case designer**: add cards where (a) one category, (b) one stage, (c) one open account total exactly `Decimal("0.00")` (e.g. one 0.00 order, or +5.00 and −5.00); (d) a timeline bucket holds a 0.00 order (bucket `total_value` and the sample's `total_value` == `Decimal("0.00")`); (e) the pipeline holds a confirmed 0.00 invoice with 0.00 paid (outstanding `Decimal("0.00")`). |
| 2 | case-missing | `aggregate_financial_snapshot_actionable` R11 (line 449) | Samples are sorted by outstanding, but in every pipeline card the sort by outstanding and the sort by invoice amount agree: UP-05 has nothing paid, and UP-01 puts each invoice in its own bucket. | mutate.py #262 (`invoice_amount + paid_amount`) and hand variant `up-order-amount` (`desc(invoice_amount)`) SURVIVED | **case designer**: in one bucket (`partial`): VA 100.00 paid 90.00 (10 left), VB 50.00 paid 10.00 (40 left) → samples `[OB, OA]`. |
| 3 | case-missing | `aggregate_financial_snapshot_filtered` R7 + R8 (line 366) | R7 says an order with no account is left out. SF-10 checks this, but with only two accounts. No card shows that an account-less order cannot take one of the five slots. | Hand variant `oba-outerjoin` (outer join; Python then drops the `None` row after `LIMIT 5`) SURVIVED | **case designer**: five accounts with open orders, plus an account-less open order with a larger total → all five accounts listed. |
| 4 | case-missing | `_apply_expense_order_hub_filters` R10, category substring (line 170) | Every search card uses `factory`, `department` or `other`. For those, the label match already finds the same orders, so the category `ILIKE` is never needed. | mutate.py #233, #234 (`'%'` → `''`) and hand variant `search-cat-off` SURVIVED | **case designer**: an order with `expense_category "office_rent"` (the DAO accepts it; SF-03 uses such categories), search `"FICE"` → found; with no `_` in the term (BUG-745). |
| 5 | case-missing | `aggregate_financial_snapshot_actionable` R4, R5 [BUG-2719] | The voided-invoice rule (the order counts at its full total, confirmed by the owner) has a card only for an **open** order (SA-12, pass). No card covers a **completed** order whose invoice is voided, so a fix that brings completed orders in through confirmed or locked invoices only would pass every card. | Card review (OQ44-01 … 09: none combines completed with invvoid) | **case designer**: strict xfail BUG-2719, completed order 70.00, invvoid invoice, due tomorrow → `due_this_week` count 1, `total_value` `Decimal("70.00")`. |

No fidelity findings. Nothing for the executor or the describer. No new bug.

**SF-06 and SF-23 (non-strict, XPASS).** Non-strict is what their cards say (`Expect: xfail … (non-strict)`, `Author: claude`): the result depends on the physical row and plan order, which can match the intended order today. Each test asserts its one Then line exactly, as carded, after `seqscan` and `expire_all`. They XPASS in every run (3 plain runs, coverage run, `--runxfail`). The bug itself is guarded by the strict SQL alarms SF-07 (BUG-2712) and SF-13 (BUG-747), which fail today on their Then 2. Accepted.

**NX-27** fails in the When (the `flush` raises `IntegrityError` 23505 on `ix_expense_orders_expense_number`), before Then 1. Its card predicts exactly this ("Then 1 (the call raises IntegrityError …)"), so the xfail is honest.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 125 | 165 | `in … or startswith` → `and` | equivalent | For the three known slugs the label is the slug title-cased. Any text inside a label is also inside the slug, so the category `ILIKE` (case-insensitive) already matches every order the label filter adds. | — |
| 150–155 | 161–163 | label tuple strings → `""` | equivalent | Same argument: the label filters are a subset of the category `ILIKE` match. | — |
| 233, 234 | 170 | category `ILIKE` `'%'` → `''` | case-missing | Finding 4 | **case designer** |
| 246 | 318 | category `total or 0` → `or 1` | case-missing | Finding 1 (a) | **case designer** |
| 251 | 329 | `int(count or 0)` → `or 1` (merged other) | equivalent | A grouped row's count is ≥ 1 | — |
| 252 | 352:40 | stage `int(row[1] or 0)` → `or 1` | equivalent | A grouped row's count is ≥ 1 | — |
| 254 | 382 | account `int(count or 0)` → `or 1` | equivalent | A grouped row's count is ≥ 1 | — |
| 256 | 424 | timeline `total_amount or 0` → `or 1` | case-missing | Finding 1 (d) | **case designer** |
| 262 | 449 | `invoice_amount - paid_amount` → `+` in ORDER BY | case-missing | Finding 2 | **case designer** |
| 273, 302 | 311, 374 | `ORDER BY coalesce(sum, 0)` → `1` | equivalent | `total_amount` is NOT NULL, so a group's sum is never NULL | — |
| 276 | 352:66 | stage `row[2] or 0` → `or 1` | case-missing | Finding 1 (b) | **case designer** |
| 278, 296 | 359, 358 | unused half of the `(0, Decimal(0))` default | equivalent | Line 358 reads `[0]` and line 359 reads `[1]`; the other half of the default is never used | — |
| 279 | 383 | account `total or 0` → `or 1` | case-missing | Finding 1 (c) | **case designer** |
| 284 | 467 | `invoice_amount or 0` → `or 1` | case-missing | Finding 1 (e) | **case designer** |
| 292 | 324 | category `int(count or 0)` → `or 1` | equivalent | count ≥ 1 | — |
| 293 | 344 | `.label("stage_key")` → `""` | equivalent | The label is never read; grouping uses the expression | — |
| 294, 309, 312 | 346, 308, 371 | `SELECT coalesce(sum, 0)` → `1` | equivalent | A group's sum of a NOT NULL column is never NULL | — |
| 303 | 431 | sample `total_amount or 0` → `or 1` | case-missing | Finding 1 (d) | **case designer** |

Hand variants — survivors:
| Variant | Line | Class | Why | Fix by |
|---|---|---|---|---|
| `search-cat-off` (drop category `ILIKE`) | 170 | case-missing | Finding 4 | **case designer** |
| `search-nolabels` (drop label filters) | 172 | equivalent | Subset argument above | — |
| `search-label-startswith-only` | 165 | equivalent | Subset argument above | — |
| `count-nodistinct` | 230 | equivalent | The only join is an outer join on `accounts.id` (PK), so each order appears at most once | — |
| `oba-outerjoin` | 366 | case-missing | Finding 3 | **case designer** |
| `tl-nulls-first` | 408 | equivalent | `NULL` due dates exist only in the `no_due_date` bucket, where all are NULL; samples are per bucket | — |
| `up-incl-paid` (`IN` + `paid`) | 447 | equivalent | Line 465 skips any status that is not a bucket | — |
| `up-order-amount` | 449 | case-missing | Finding 2 | **case designer** |
| `tl-incl-completed`, `up-incl-completed` | 406, 444 | bug-path | BUG-2719 / BUG-2718 fix direction; only the OQ43 / OQ44 xfail cards separate it | — |
| `nx-year-utc` | 502 | bug-path | BUG-2710 fix; only NX-21 / NX-22 (xfail) separate the clocks | — |
| `stage-voided-excluded`, `stats-voided-total-fix` | 343, 273 | bug-path | BUG-2717 fix direction (OQ42-01 … 07 xfail) | — |

## Hand variants — what was tried (all KILLED unless listed above)
70 variants (verifier's own script `hand.py`, temp copy):
- **Workspace scoping (with W0 / W2 rows):** dropping the workspace filter from the hub filter, the timeline, the pipeline, `get_next_number`, both `get_by_id_and_workspace` and `get_by_order`.
- **Hub filter defaults:** `exclude_voided` / `exclude_complete` defaults flipped.
- **Search:** `like` instead of `ilike` (number, account), no trim, inner join, prefix-only match.
- **Stage filter:** draft without the invoice check; invoiced including completed orders.
- **Hub stats:** open value including completed orders; `subtotal` instead of `total_amount`.
- **Category breakdown:** keep 7.
- **Filtered snapshot:** the search join kept on (SF-18).
- **Open by account:** including completed orders; `limit(6)`.
- **Due timeline:** voided orders included (OQ44-02); `subtotal`; four samples; number sorted descending.
- **Unpaid pipeline:** voided invoice or voided order included (UP-03, OQ43-04); `overdue` dropped; sorted ascending; outstanding = invoice amount; sample = order total.
- **Numbering:** `ilike` prefix (NX-15), `%prefix%`, no dash, lower-case prefix, pad 4 / no pad, year hard-coded 2031 (NX-20), text-ascending "highest".
- **Other reads:** `get_by_workspace` with `account_id is not None` (GW-08), ascending, no offset; list without the `id` tie-break, no offset; recent without a limit; `get_by_order` descending; Sunday week end +1; category label without the `_` replacement.
- **Locks:** `.with_for_update()` on `get_by_workspace`, `list_recent_for_hub`, hub stats, `count_for_hub`, timeline, pipeline, `get_next_number` and `get_by_order` — each killed by its no-lock card, or by a Postgres error for the aggregate `count_for_hub`. A lock cannot be added to `count_for_hub` (COUNT / DISTINCT) without an error, so its missing no-lock card is not a gap.

Hand-variant topics from the brief that do not apply here: received vs refunded and the transfer "Planned" filter (not in this DAO). Payable and receivable combined: the pipeline does not filter on `invoice_type`, but a receivable invoice can only be linked through BUG-751 (client-writable `invoice_id`). Not a new bug; noted for the future.

## Traceability
cases 245 · tests 212 functions / 245 collected items (44 `pytest.param` ids) · unmatched: none · duplicates: none · marker mismatches: none.
- Every strict / non-strict flag matches the card.
- Every reason is a `BUG_n` constant whose text starts with `BUG-n`; HF-47 names BUG-2715 inline.
- Every BUG ID used is in `docs/testing/bugs.md`.

`--runxfail` map (verifier's plugin `vfails.py`): 45 of 46 fail inside the card's "Fails today on" Then block; NX-27 fails in the When, as its card says.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_expense_order.py -q -p no:cacheprovider -o addopts="" --cov=app.dao.expense_order --cov-branch --cov-report=term-missing
  app\dao\expense_order.py  187  1  70  1  99%  466
  197 passed, 46 xfailed, 2 xpassed, 39 warnings
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_expense_order.py -q -p no:cacheprovider -o addopts="" --runxfail -rf
  46 failed, 199 passed, 39 warnings
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_expense_order.py -q -p no:cacheprovider -o addopts=""   (×2)
  197 passed, 46 xfailed, 2 xpassed  /  197 passed, 46 xfailed, 2 xpassed
PYTHONPATH=<scratch> … --runxfail -p vfails           → 46 failed, 199 passed (map above)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/expense_order.py tests/unit/dao/test_expense_order.py --timeout 300 --json <scratch>/mut.json
  Mutants: 313 · killed 285 · timeout 0 · survived 28 · score 91% (raw)
.venv/Scripts/python.exe <scratch>/hand.py            → 70 variants · 57 killed · 13 survived
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaov\eo\` (private `COVERAGE_FILE`s, `trace.py`, `fid.py`, `lit.py`, `vfails.py`, `hand.py`, `variants.json`, `mut.json`, `hand.json`).

## Future notes
- Unpaid pipeline and `invoice_type`: once BUG-751 is fixed (only the system links invoices), an expense order can only carry a payable invoice. Until then, a linked receivable invoice would count as money we owe. If BUG-751 stays open past launch, consider an `invoice_type = 'payable'` filter on the pipeline join.

## Round 2 — 2026-11-14
**Verdict: PASS.** This was a narrow re-check of the five round-1 findings against cases Revision 3. The source is unchanged (e48a092, `app/dao/expense_order.py` not modified).

**New cards read against their tests (all faithful).** Each one's Given is built as written, and each Then line is asserted exactly, in card order. There are no new mocks.

| Finding | Card | Expect | Test |
|---|---|---|---|
| 1 (a–c) | SF-24 (0.00 order: category, stage and open-account totals) | pass | `test_exo_sf_24__zero_order_exact_zero`: the three Then lines are full-list `==` with `Decimal("0.00")` / `Decimal("0")` as carded |
| 1 (d) | SA-13 (0.00 timeline bucket and sample) | pass | `test_exo_sa_13__zero_order_exact_zero`: count, total and the full sample dict, under `clockD()` |
| 1 (e) | UP-13 (confirmed 0.00 invoice) | pass | `test_exo_up_13__zero_invoice_exact_zero`: count, outstanding and the full sample dict |
| 2 | UP-14 (samples by what is owed) | pass | `test_exo_up_14__samples_by_what_is_owed`: outstanding 50.00, ids `[OB, OA]`, values `[40.00, 10.00]` |
| 3 | SF-25 (five accounts beside an account-less 100.00 order) | pass | `test_exo_sf_25__five_accounts_beside_accountless_order`: ordered id list and value list |
| 4 | HF-50 (`office_rent` found by `"FICE"`) | pass | `test_exo_hf_50__search_category_slug_middle`: `idset == {OA.id}` |
| 5 | OQ44-10 (completed order, voided invoice → 70.00 due this week) | xfail BUG-2719 | `xfail(strict=True, reason=BUG_2719)`. Under `--runxfail` it fails at Then 1 (`assert 0 == 1`, line 5193), as the card says |

**Traceability (whole file):**
- 252 cards and 252 collected items (219 functions plus 44 param ids). Nothing is missing, extra or duplicated.
- The markers match the Expect lines.
- Every xfail reason constant names its BUG ID.
- The other 46 xfails fail on the same Then block as in round 1 (`vfails.py` map unchanged).

**Survivors routed in round 1 — all killed now.** The "Killing test" column is from `killers.py`: each mutant was re-applied on a temp copy and the expected-to-pass tests were run against it.

| Round-1 survivor | Line | Killing test |
|---|---|---|
| #233, #234 category `ILIKE` `'%'` dropped | 170 | HF-50 (both sides) |
| hand `search-cat-off` | 170 | HF-50 |
| #246 category `total or 1` | 318 | SF-24 |
| #276 stage `row[2] or 1` | 352:66 | SF-24 |
| #279 account `total or 1` | 383 | SF-24 |
| #256 timeline `total_amount or 1` | 424 | SA-13 |
| #303 sample `total_amount or 1` | 431 | SA-13 |
| #262 `invoice_amount + paid_amount` | 449 | UP-14 |
| hand `up-order-amount` | 449 | UP-14 |
| #284 `invoice_amount or 1` | 467 | UP-13 |
| hand `oba-outerjoin` | 366 | SF-25 |

The targeted mutate.py runs on lines 170, 318, 352, 383, 424–431, 449 and 467 produced 31 mutants: 30 killed and 1 survived. The survivor is L352:40, the stage `int(row[1] or 0)` → `or 1`. This is round-1 #252, already classed `equivalent` (a grouped row's count is ≥ 1). That makes the score 100% on these lines (30 of 30, after excluding 1 equivalent). Finding 5 is behaviour of the BUG-2719 fix, so no mutant targets it today; OQ44-10 now pins it.

**Runs (cases Rev 3; the notes' Result line is "203 passed · 47 xfailed · 2 xpassed"):**
```
pytest … -o addopts="" --cov=app.dao.expense_order --cov-branch   → 203 passed, 47 xfailed, 2 xpassed · 99% (187 st, 1 miss: 466; 70 br, 1 partial)
pytest … -o addopts=""  (run 2)                                   → 203 passed, 47 xfailed, 2 xpassed
pytest … -o addopts=""  (run 3)                                   → 203 passed, 47 xfailed, 2 xpassed
pytest … -o addopts="" --runxfail -rf  (+ -p vfails)              → 47 failed, 205 passed (each on its card's line)
mutate.py … --lines 170-170 | 318-318 | 352-352 | 383-383 | 424-431 | 449-449 | 467-467
                                                                  → 2/2 · 2/2 · 6/7 · 3/3 · 13/13 · 1/1 · 3/3 killed
hand.py search-cat-off oba-outerjoin up-order-amount              → 3 KILLED (HF-50, SF-25, UP-14)
```
SF-06 and SF-23 still XPASS (non-strict, as carded). No flaky outcome.

**Routed:** nothing. The round-1 future note (unpaid pipeline and `invoice_type`, BUG-751) still stands. The scratch files for this round are in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaov\eo\r2\` (private `COVERAGE_FILE`).
