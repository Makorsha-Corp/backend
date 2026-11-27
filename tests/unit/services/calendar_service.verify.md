# Verification — `app/services/calendar_service.py`

> **Current verdict (round 4, 2026-11-04): PASS.** Cases revision 6: 128 tests, 105 passed, 23 strict xfail, 100% branch coverage. All are faithful. Every routed finding (round 1: 1–4; R2-1, R2-2, R3-1) is closed. Mutation is 205 / 205 (source unchanged). See `## Round 4 — 2026-11-04`.
>
> *Round 3 verdict line, kept:* **NEEDS WORK — one small card edit.** Cases revision 5: 128 tests, 105 passed, 23 strict xfail, 100% branch coverage. All are faithful. R2-1 is fixed, and R2-2 is fixed for 3 of its 4 shapes. One leftover (R3-1): in CAL-OQ5-11, the W1 membership is built before the other-workspace rows. See `## Round 3 — 2026-11-04`.
>
> *Round 2 verdict line, kept:* **NEEDS WORK — cases only.** Cases revision 4: 124 tests, 105 passed, 19 strict xfail, 100% branch coverage. All of them are faithful. Of the round-1 findings, 1, 2 and 4 are fixed; 3 is still open, because building rows in a different order does not change ids across two tables. The new BUG-1869 cards miss four too-loose access checks. See `## Round 2 — 2026-11-04` at the end. Round 1 below is kept as written.

> **Verdict:** NEEDS WORK (cases only: the tests are faithful, and mutation is 100%)
> Tests: 105 passed · 9 xfailed, all strict (reproduced ✅) · coverage 100% branch (123 statements, 44 branches)
> Mutation: 205 mutants · 205 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 114 unfaithful** (114 / 114 right; read by eye against cases revision 3)
> Hand variants: 152 · 109 caught by a pass card · 43 others: 31 equivalent, 12 case-missing
> Source commit: e48a092 · Cases revision: 3; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 114 match their cards. The `CC` mapping (`CC.sales is CalendarCategory.SALES`) is notation only, and cases revision 3 now states it. No expected value moves. The pending-owner cards (CAL-OQ5-01, CAL-OQ14-01/02, CAL-OQ15-01/02) are faithful to today's cards. OQ-5 is now answered, so they will change in a later revision. That is not judged here.
- **Every mutant is killed**, and most hand variants fail a pass card. That includes dropping any collector's category gate, querying before the gate (the recorder sees the SQL), any narrowed date edge in SQL or in `_date_in_range`, the project day bounds, and every sort-key change that alters order.
- **One real gap: workspace isolation is checked on one side only.** W2 is always created after W1, so every other-workspace row has a **higher** workspace id. Changing any collector's `X.workspace_id == workspace_id` to `<=` passes the whole file (9 of 9 collectors). The cards put other-workspace rows on both sides of the **record** id, not of the **workspace** id. The fix belongs to the case designer.
- Three smaller case gaps follow: a payment of another workspace linked to this workspace's invoice; a sort tie broken by record id; and a delivery status that is "cancelled" in another spelling.

Written by Claude (all 114 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 / 114. No `calendar_service.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | WO-05, PO-07, EO-05, SO-04, SD-05, IN-05, PY-06, PB-05, PJ-07 (lines 132, 177, 227, 275, 320, 365, 416, 459, 500) | Other-workspace rows exist only in W2, whose id is always above W1's. A workspace filter written `<=` keeps every isolation card green. `_collect_*` R1 says "another workspace's never appears", so other workspaces must sit on **both** sides of the workspace id, as the ns cards do for user and workspace ids (6 / 8, 2 / 4). | variants `ws_le_wo` … `ws_le_pj`: `105 passed, 9 xfailed` each. `ws_ge_*` and `ws_drop_*` are caught. | **case designer**: e.g. a standing W0 made **before** W1 (with the rows each builder needs), and a "W0 x" row next to B9 / C9 in each isolation card. GE-15 could take one too. |
| 2 | case-missing | `_collect_invoice_payments` R1, line 416 | No card has a W2 payment linked to a W1 invoice. If the collector filters on the **invoice's** workspace instead of the payment's, it lists such a payment. No pass card fails. Only PY-08 XPASSes, and that card is about the opposite link. | variant `ws_py_on_invoice`: `1 failed (PY-08 XPASS), 105 passed, 8 xfailed` | **case designer**: in PY-06, add a W2 payment with `invoice_id INX.id`. It must not appear. (Invalid data, but R1 is the guard against it. It also stays true after the BUG-1801 fix.) |
| 3 | case-missing | `get_events` R4, line 72 | R4: ties keep collection order (sales orders before deliveries, invoices before payments). GE-12 and GE-13 pass with an extra tie-break `-record_id`, only because the row ids happen to rise against the expected order. | variant `sort_add_record_id`: `105 passed, 9 xfailed` | **case designer**: in GE-12 and GE-13, build the pair so that the record ids fall the other way too. For example, add a second pair built in the opposite order and assert both. |
| 4 | case-missing | `_collect_sales_deliveries` R1, line 321 | R1 says "whose `delivery_status` is not **exactly** `"cancelled"`". No card holds a near spelling, so a case-insensitive filter passes. The column has no check constraint (`String(50)`). | variant `sd_status_ilike` (`notin_(["cancelled", "Cancelled"])`): `105 passed, 9 xfailed` | **case designer**: one delivery with `delivery_status "Cancelled"` is listed. Or, if that value is unreachable, the **describer** says so in Facts and the word "exactly" goes. The same wording sits on batches (`_collect_production_batches` R1). |

**Bookkeeping, not a finding (executor, next touch):** the notes header and the test module docstring say "cases revision 2". Revision 3 changed only the `CC` note, which the tests already follow.

## Surviving mutants
None. All 205 kills end in a plain `N failed` (checked in `mut_cal.json`, `killed_by`). None came from an error, and there were 0 timeouts. This includes every `>=`/`>` and `<=`/`<` swap on every SQL date bound and in `_date_in_range`, and every `==`/`!=` on the workspace filters.

## Hand variants
`plug\vplug.py` execs a variant of the module into `app.services.calendar_service` before collection. `drive.py` applies each edit (checked to apply exactly once) and runs the whole file in normal mode. `var_cal.py` holds the edits. The control variant gives `105 passed, 9 xfailed`.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| workspace filter dropped, per collector | 9 | 9 | WO-05, PO-07, EO-05, SO-04, SD-05, IN-05 (+GE-15), PY-06, PB-05, PJ-07 (+GE-15) | — |
| workspace filter `>=`, per collector | 9 | 9 | same as dropped | — |
| workspace filter `<=`, per collector | 9 | 0 | — | 9 × `ws_le_*` (Finding 1) |
| payment filtered on the invoice's workspace | 1 | 0 | — | `ws_py_on_invoice` (Finding 2) |
| category gate dropped, per collector | 9 | 9 | each collector's "another category allowed" card (WO-07 … PJ-08), most also GE-06 … GE-09 | — |
| query sent, then the gate (`[]` returned, SQL sent) | 9 | 9 | WO-07, PO-08, EO-06, SO-05, SD-06, IN-06, PY-07, PB-06, PJ-08 (the `stmts == []` line) | — |
| wrong gate category (deliveries on invoices, payments on sales); `types=[]` filters all; `types` ignored; `_category_allowed` only for one-item sets | 5 | 5 | GE-05 … GE-09, GE-12, GE-13, CA-02, isolation cards | — |
| `_date_in_range` start or end exclusive, `None` in; datetime not reduced | 4 | 4 | DR-02 / DR-03 / DR-06, XF-02 … XF-04, GE-02, GE-03, every edge card | — |
| SQL bound narrowed by a day, start and end, 15 date columns | 30 | 30 | each column's edge card (WO-02/03, PO-03 … 05, EO-02/03, SO-02/03, SD-02/03, IN-02/03, PY-03, PB-02) | — |
| SQL bound widened by a day, payments and batches (no Python filter) | 4 | 4 | PY-03, PB-02 | — |
| SQL bound widened by a day, 13 columns behind `_expand_date_fields` | 26 | 0 | — | 26 equivalent |
| project bounds (`>`/`<` per column, column dropped, end at 00:00, end at 23:59:59, start at 23:59:59.999999) | 12 | 12 | PJ-02 … PJ-04, GE-02, GE-04 … GE-10, PJ-05 … PJ-12 | — |
| project bounds widened (end = next day 00:00, start = previous day 23:59:59.999999) | 2 | 0 | — | 2 equivalent |
| sort (drop date / category / title, title before category, category first, reverse, by source type, no sort, ties reversed, collector order swapped ×2) | 11 | 11 | GE-10; GE-11 … GE-13 | — |
| sort by `category.name`, by the enum itself | 2 | 0 | — | 2 equivalent |
| sort tie broken by `-record_id` | 1 | 0 | — | Finding 3 |
| field order reversed; range guard after the reads; guard message | 3 | 3 | XF-01, XF-04, XF-06, GE-11, *-01 cards; GE-01 | — |
| subtitle 121, empty description → `""`, title only for `None`, payment date taken from `start` | 4 | 4 | PJ-05, PJ-06, IN-07, PY-01 / GE-13 | — |
| delivery status case-insensitive | 1 | 0 | — | Finding 4 |
| `meta or {}` → `meta if meta is not None else {}` | 1 | 0 | — | 1 equivalent |
| **Total** | **152** | **109** | | **43** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| 26 × `edge_*_lo_wide` / `edge_*_hi_wide` (work, purchase, expense, sales orders, deliveries, invoices) | **Equivalent.** These collectors pass every row through `_expand_date_fields`, which drops each value outside `[start, end]` (`_date_in_range`). A row fetched only because of a widened SQL bound gives no event, so the result is the same; only the rows read differ. Narrowing is caught on every column. |
| `pj_end_dt_next_day`, `pj_start_dt_prev_day` | **Equivalent**, for the same reason: `_dt_to_date` reduces to the day, and `_date_in_range` drops 06-01 / 04-30. |
| `sort_by_name`, `sort_by_enum` | **Equivalent.** `CalendarCategory` is a `str` enum, so comparing members compares values. The names are the values in upper case, and no pair changes order (`_` is the only non-letter, and no other name shares a prefix up to it). |
| `meta_shared_dict` | **Equivalent.** Every collector passes a non-empty dict or nothing. `meta={}` is never passed, which is the only input where the two forms differ. |

## xfail tests
`--runxfail --tb=short`: `9 failed, 105 passed`. Each fails on its card's **Then 1** line: GE-17 (line 795, `[] == [...]`), GE-18 (818), GE-19 (830), GE-20 (843), GE-21 (855), PY-08 (1580), PB-07 (1687), PJ-10 (1810), PJ-11 (1822). Each is an assertion, with no setup or import error. These match the notes. The bug fixes themselves were not rebuilt here. The executor's reference plugin already showed that each fix flips only its own cards.

## Reproduced claims
- **Result line of the notes holds:** `105 passed, 9 xfailed` in 3 of 3 default runs (the coverage run among them), plus the control variant. No flaky test. The runs shared the database with the parallel mutation run, so they waited on the shared `SO-X` row, but no outcome changed.
- **Mocks:** only the Conventions' spies on `db.commit` / `db.rollback` (GE-14) and the failing `db.query` (GE-16). No DAO and no session is replaced. `try/finally` appears only around the recorder in GE-01, so the listener is removed. There is no `try/except` and no broad `pytest.raises`.
- **The recorder works:** the 9 `gate_after_query_*` variants each fail only on their card's `stmts == []` line.
- **Checked against the brief:** isolation has other-workspace rows on both sides of the record id, and on only one side of the workspace id (Finding 1). Both date edges plus the day outside each end are covered for every column, and for projects the instants 23:59:59.999999 / 00:00. Every collector has a "no SQL sent" card. GE-10's keys don't rise together: title order ≠ category order ≠ id order (only the `-record_id` tie-break survives, Finding 3).

## Traceability
cases 114 · tests 114 (by test name, docstring or `pytest.param(id=…)`; DR-01 … DR-06, WO-02/03, PO-03 … 05, SD-02/03, IN-07/08 and PJ-02 … 04 are param ids) · unmatched: none · duplicates: none · marker mismatches: none. Every strict reason names its BUG (BUG-1800, 1801, 1805, 1806, 1807; BUG-1101 is cited in a docstring), and all are in `docs/testing/bugs.md`. Checked by my own `trace.py`. `ruff check` passes.

## Limits of this round
- **The variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated:** the mutation run, the variant driver and the plain runs shared `marker_test`. Every kill is a plain `N failed`.
- **Not exercised:** the HTTP layer (`ValueError` → 400), and the intended BUG-1805 maintenance collector beyond its xfail cards.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/calendar_service.py tests/unit/services/test_calendar_service.py --json <scratch>/mut_cal.json
  Mutants: 205 · killed 205 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe -m pytest tests/unit/services/test_calendar_service.py -q -p no:cacheprovider --cov=app.services.calendar_service --cov-branch --cov-report=term-missing
  105 passed, 9 xfailed · app\services\calendar_service.py 123 0 44 0 100%
.venv/Scripts/python.exe -m pytest tests/unit/services/test_calendar_service.py -q -p no:cacheprovider --runxfail --tb=short
  9 failed, 105 passed
pytest, default, 2 more runs                                               105 passed, 9 xfailed each
drive.py var_cal.py (153 runs, control included)                           as above
trace.py calendar_service.cases.md test_calendar_service.py CAL            cards 114 · test-ids 114 · 0 reports
.venv/Scripts/python.exe -m ruff check tests/unit/services/test_calendar_service.py   All checks passed!
git diff --stat -- app/services                                            (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc4v2\` (private `COVERAGE_FILE`). Only this report was written in the repo. No commit, and nothing added to `bugs.md` (no new bug). Nothing was killed.

## Round 2 — 2026-11-04

> **Verdict:** NEEDS WORK (only cases need work; the tests are faithful)
> Tests: 105 passed · 19 xfailed, all strict (reproduced ✅) · coverage 100% branch (123 statements, 44 branches; source unchanged)
> Mutation: not re-run. `app/services/calendar_service.py` is unchanged (`git diff` empty), so round 1 stands at 205 / 205.
> Fidelity: **0 of 124 unfaithful**. I read the changed and new tests by eye against cases revision 4.
> Variants this round: 41 · 4 reference fixes, which flip exactly their own cards · 5 too-loose access checks that no card catches · 1 routed round-1 variant still alive
> Cases revision: 4

### Summary
- **The changed and new tests match their cards.** They are: standing W0 built before W1 (`W0.id < W1.id < W2.id`) with W0 rows in the 9 isolation cards and GE-20; the W2 payment on W1's invoice in PY-06; the second tie pairs in GE-12 and GE-13; SD-07 and PB-08; OQ14-01/02; OQ15-01/02; WO-08; SO-06; and OQ5-01 … 07.
  - OQ5-03 and OQ5-04 share a test through param ids.
  - The marker `BUG_1869 = xfail(strict=True, raises=TypeError)` pins those xfails to the missing `user_id`.
- **The reference fixes flip exactly their own cards.** I wrote my own fixes (scratch only). Each one turns its own strict xfail tests into XPASS and breaks no pass test: BUG-1876 → OQ14-01; BUG-1877 → OQ15-01; BUG-1878 → OQ15-02; BUG-1869 → OQ5-01 … 07. With all four fixes and `--runxfail`, 115 pass, and the 9 that still fail are the older bugs (1800, 1801, 1805, 1806, 1807).
  - My BUG-1869 fix takes `user_id` with a default of `None` (no filtering), so the old calls still run. The spec makes `user_id` required. After the real fix, every other `get_events` call in the file needs `user_id`, as spec Notes say.
- **Round-1 routes:** a `<=` workspace filter is now caught in all 9 collectors. A payment filtered on the invoice's workspace is caught by PY-06. A case-insensitive "cancelled" is caught by SD-07 and PB-08. **The `-record_id` tie-break still survives** (Finding R2-1).
- **Visibility check:**
  - Too strict is always caught. Dropping the owner, role `owner`, role `ground-team-manager`, creator or project-member grant, hiding every private project, or hiding open projects each fails its own card.
  - Too loose is caught for the basic shapes: no check, any role, `ground-team` treated as privileged, inactive member allowed. Four more realistic too-loose checks pass every card (Finding R2-2).

### Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| R2-1 | case-missing (round-1 Finding 3, still open) | GE-12, GE-13; `get_events` R4, line 72 | The second pair is built in the opposite order, but the two records of a pair come from **different tables** with separate id sequences, so build order does not decide which id is larger. In all four pairs the record expected first has the larger id. A `-record_id` tie-break therefore passes. A `+record_id` tie-break is caught. | `r1_sort_add_record_id`: `105 passed, 19 xfailed`. `r1_sort_add_plus_record_id`: GE-12 and GE-13 fail. | **case designer**: make the ids decide in both directions, for example one pair whose sales order (or invoice) has a **smaller** id than its delivery (or payment). Set an explicit `id=` above the other table's current sequence value, or move the sequence forward before building. |
| R2-2 | case-missing | OQ5 cards; `_collect_projects` R6 and spec Facts "Who may open a private project" | No refused-caller card covers these shapes, so a fix with any of these mistakes passes every card: (a) a private project with `created_by None` is open to everyone (Facts: "open only to (1), (2), (4)"); (b) a caller with a `project_members` row on **another** project of the workspace; (c) a caller who owns **another** workspace; (d) a caller who is an active `ground-team-manager` in **another** workspace and a plain `ground-team` member here. All four are valid data. | With my BUG-1869 fix plus one edit, `--runxfail` gives 0 extra failures for `v1869_creator_none_open`, `v1869_pmember_any_project`, `v1869_owner_of_any_workspace`, `v1869_member_any_workspace`. | **case designer**: add four refused-caller cards (strict xfail BUG-1869, each expecting `recs(result) == [PW.id]`): a private project with no creator and a `ground-team` caller; a caller who is a project member of another private project; a caller who is W2's owner; a caller who is an active `ground-team-manager` in W2. |

Not routed:
- `v1869_pmember_any_workspace` (the project-member lookup ignores `workspace_id`) also passes every card. It only matters for a `project_members` row whose workspace differs from its project's, which is a cross-workspace link and therefore invalid data (house rule). So it is not a case gap.
- `v1876_lowercase` (`status != "voided"`) leaves OQ14-01 xfail. That fix does not work, and the strict xfail still shows it.

### Variants (round 2)
`var_cal2.py`, through `drive.py`. The edits are applied to today's source. The 1869 variants are applied on top of my BUG-1869 fix and judged with `--runxfail` against `fix_1869`. The control gives `105 passed, 19 xfailed`.

| Variant | Result | Cards that fail |
|---|---|---|
| `fix_1876` / `fix_1877` / `fix_1878` / `fix_1869` | each XPASSes (strict) only its own cards | OQ14-01 / OQ15-01 / OQ15-02 / OQ5-01 … 07 |
| `fix_all`, `--runxfail` | 115 passed, 9 failed | only GE-17 … 21, PY-08, PB-07, PJ-10, PJ-11 (older bugs) |
| 1869 too loose: no check · any role · `ground-team` privileged · inactive allowed | caught | OQ5-01 + OQ5-07 · OQ5-01 · OQ5-01 · OQ5-07 |
| 1869 too loose: creator `None` open · member of any project · owner of any workspace · member of any workspace | **not caught** | — (R2-2) |
| 1869 too loose: project member of any workspace | not caught | — (invalid data, not routed) |
| 1869 too strict: no owner · no role `owner` · no role `ground-team-manager` · no creator · no project member · hide all private · hide open projects too | caught | OQ5-02 · OQ5-03 · OQ5-04 · OQ5-05 · OQ5-06 · OQ5-02 … 06 · OQ5-01, 05, 06, 07 |
| 1876 too strict: also hide `COMPLETED` / `DRAFT` | caught | OQ14-02 / OQ14-02, WO-02 … 08, GE-04, GE-05, GE-10 |
| 1877 / 1878 too strict: also hide an inactive factory | caught | WO-08 / SO-06 |
| round 1: `<=` workspace filter ×9 | caught | WO-05, PO-07, EO-05, SO-04, SD-05, IN-05, PY-06, PB-05, PJ-07 |
| round 1: payment on the invoice's workspace | caught | PY-06 (and PY-08 XPASS) |
| round 1: case-insensitive "cancelled", deliveries / batches | caught | SD-07 / PB-08 |
| round 1: `-record_id` tie-break | **not caught** | — (R2-1). `+record_id`: GE-12, GE-13 |

### Reproduced claims
- **Result line of the notes holds:** `105 passed, 19 xfailed` in 3 of 3 runs (the coverage run among them), plus the control variant. No flaky test.
- `--runxfail --tb=short`: `19 failed, 105 passed`, each on its card's line:
  - Then 1: GE-17 … 21, OQ14-01, OQ15-01, OQ15-02, PY-08, PB-07, PJ-10, PJ-11.
  - The When call, raising `TypeError: … unexpected keyword argument 'user_id'`: OQ5-01 … 07, as their cards say.
- **Mocks:** nothing new is patched. The access rows (`WorkspaceMember`, `ProjectMember`, `W1.owner_user_id`) are real rows.
- **Traceability:** cases 124, tests 124, no unmatched IDs, no duplicates. `trace.py` reports `MARK` for the 7 OQ5 cards only because it does not follow the named decorator `@BUG_1869`. That decorator is `xfail(strict=True, raises=TypeError, reason="BUG-1869")`, which is correct. BUG-1869, 1876, 1877 and 1878 are in `docs/testing/bugs.md`. `ruff check` passes.

### Commands run (round 2)
```
pytest test_calendar_service.py --cov … --cov-branch                      105 passed, 19 xfailed · 123 0 44 0 100%
pytest test_calendar_service.py (×2 more)                                  105 passed, 19 xfailed each
pytest test_calendar_service.py --runxfail --tb=short                      19 failed, 105 passed
drive.py var_cal2.py (41 runs, control included); RUNXFAIL=1 drive.py … (fixes and v1869_*)   as above
trace.py calendar_service.cases.md test_calendar_service.py CAL            cards 124 · test-ids 124
ruff check tests/unit/services/test_calendar_service.py                    All checks passed!
git diff --stat -- app/services                                            (empty)
```
mutate.py was not re-run, because the source is unchanged. Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc4v2\` (`var_cal2.py`, `vcal2\`, `vcal2x\`). Only this file and the bookkeeping line in `notification_stream.verify.md` were written. No commit, no `bugs.md` change, nothing killed.

## Round 3 — 2026-11-04

> **Verdict:** NEEDS WORK (one small card edit)
> Tests: 105 passed · 23 xfailed, all strict (reproduced ✅) · coverage 100% branch (source unchanged; mutation not re-run, round 1 stands at 205 / 205)
> Fidelity: the 6 changed or new tests (GE-12, GE-13, OQ5-08 … 11) match cases revision 5. **0 unfaithful.**
> Cases revision: 5

### Checks
- **R2-1 is fixed.** GE-12 and GE-13 give every row an explicit id (`XID(k)`). The record expected first has the larger id in one pair and the smaller in the other. A `-record_id` tie-break now fails GE-12 and GE-13, and so does `+record_id`.
- **R2-2 is fixed for 3 of 4 shapes.** On top of my BUG-1869 reference fix (which turns all of OQ5-01 … 11 green under `--runxfail`, 116 passed), these too-loose variants are now caught:
  - creator `None` open to all → OQ5-08
  - project member of any project → OQ5-09 (dropping the project-member grant fails OQ5-06 and OQ5-09)
  - owner of any workspace → OQ5-10
  - a privileged active membership in **any** workspace (`exists` over the user's memberships), which I added this round → OQ5-11
- **One shape still passes (R3-1):** my round-2 variant `v1869_member_any_workspace` still passes every card. It reads the caller's membership with `.first()` and no workspace filter. In OQ5-11 the W1 `ground-team` row is built **first**, so the unordered `first()` returns it and the caller is refused, as intended, by luck of row order.
- **Not routed:** `v1869_pmember_any_workspace` still passes. It needs a cross-workspace `project_members` row, which is invalid data, as in round 2.
- **Docstrings:** the docstrings of GE-12 and GE-13 still say "whichever was built first", while the cards now say "whichever id is larger". This is cosmetic. Executor, next touch.

### Findings
| # | Kind | Case | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| R3-1 | case-missing (minor) | CAL-OQ5-11 | The W1 membership (`member(UX, "ground-team")`, Given 1) is built before the W2 `owner` and W0 `ground-team-manager` rows. A fix that takes the caller's membership with `first()` and no workspace filter returns the W1 row, so it passes. | `v1869_member_any_workspace`: 0 extra failures beyond `fix_1869` (`--runxfail`) | **case designer**: in OQ5-11, build the W2 and W0 membership rows **before** the W1 membership (move Given 1 after Given 3), so an unfiltered `first()` most likely meets a privileged row. Nothing else changes. |

### Runs
- 3 of 3 runs: `105 passed, 23 xfailed`, the coverage run among them (`123 0 44 0 100%`).
- `--runxfail`: OQ5-08 … 11 fail on the When call (`TypeError … 'user_id'`), as their cards say.
- `trace.py`: cards 128, tests 128, no unmatched IDs (OQ5 `MARK` lines are the named-decorator artefact noted in round 2).
- `ruff check` passes. `git diff --stat -- app/services` is empty.
- Variants: `var_cal3.py` (11 runs with `RUNXFAIL=1`, results in `vcal3x\`).

Only this file was written. No commit, no `bugs.md` change, nothing killed.

## Round 4 — 2026-11-04

> **Verdict:** PASS
> Tests: 105 passed · 23 xfailed, all strict (reproduced ✅) · coverage 100% branch (`123 0 44 0`; source unchanged, mutation 205 / 205 from round 1)
> Cases revision: 6

- **OQ5-11 matches its card.** The W2 `owner` row and the W0 `ground-team-manager` row are flushed first, then the W1 `ground-team` membership, then PV and PW. The When call and Then 1 (`recs(result) == [PW.id]`) are as written.
- **R3-1 is fixed.** On top of my BUG-1869 reference fix (`--runxfail`: 116 passed, the 12 failures being the other open bugs), `v1869_member_any_workspace` (`first()` with no workspace filter) now fails OQ5-11. So does `v1869_privileged_any_workspace`.
- **GE-12/13 docstrings** now carry the cards' titles ("whichever id is larger").
- **Runs:** 3 of 3 give `105 passed, 23 xfailed`, the coverage run among them. `ruff check` passes. `git diff --stat -- app/services` is empty.
- **Still not routed:** `v1869_pmember_any_workspace` needs a cross-workspace `project_members` row, which is invalid data per the house rule.

Only this file was written. No commit, no `bugs.md` change, nothing killed. Scratch results are in `vcal4x\`.
