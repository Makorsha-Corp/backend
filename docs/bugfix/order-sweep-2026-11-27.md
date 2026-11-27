# Order sweep, 2026-11-27 (improvements C4)

**Question.** After WOM-GI-01 (BUG-1272) failed on Linux CI, are there other "pass" tests whose expected row order only holds because Postgres happens to return rows in physical order? The missing `ORDER BY` or tie-break behind that luck is an open bug. House convention: such a test is a **non-strict** xfail for that bug, and the bug's strict proof lives in another card.

## Method

I did not grep the 117 open ordering bugs one by one. Instead I ran the whole suite under a forced order and compared:

- **Patch.** A scratch pytest plugin (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\order_sweep\plug\order_perturb.py`, not in the repo) hooks `Session.do_orm_execute`. It appends a primary-key tie-break to every ORM entity `SELECT`.
- **Why the patch is fair.** Every order it produces is one the current query already allows. Rows that tie on the existing sort key, or a whole list with no `ORDER BY`, come back in a forced order. Rows that differ on the sort key keep their order. So a test that fails under the patch is relying on unspecified order.
- **Two runs.** `ORDER_PERTURB=desc` (ids reversed, like a different physical order) and `ORDER_PERTURB=asc` (catches tests that expect "newest id first" ties). Each run used its own databases (`ordsweepdesc_test`, `ordsweepasc_test`) with `-n 4`.
- **Baseline.** I stopped the baseline run to save time. Instead I re-ran each candidate without the plugin (all green; CI is green on main).
- **Not covered.** The patch skips column-only and aggregate selects, `GROUP BY` / `DISTINCT ON`, aliased entities and raw SQL text.

## Counts

| | count |
|---|---|
| Tests run (each mode) | 24,131 |
| Failures under `desc` / under `asc` | 132 / 106 |
| Distinct tests failing in at least one mode | 197 |
| Strict xfails of an ordering bug that **xpassed** (the patch "fixes" the bug, as expected; not candidates) | 178 |
| Strict xfails of a **non-ordering** bug that xpassed (see "Unsure / follow-up") | 8 |
| SQL-text checks broken by the extra `ORDER BY` term (patch side effect, not candidates) | 7 |
| **Real order dependence in a pass test** | **4** |
| Changed | **3** (+1 resolved by a fix merged during the sweep) |

## Candidates examined

| Test id | File | Bug | Verdict | Changed | How confirmed |
|---|---|---|---|---|---|
| PRJM-L-11 | `tests/unit/managers/test_project_manager.py` | BUG-100 (base `get_by_workspace`, no `ORDER BY`; the unfiltered `list_projects` path) | candidate. The page of 2 is {H1, H2} only in physical order. Same reason PRJM-L-10 is already non-strict. Projects: revisit after launch. | yes: `pytest.mark.xfail(strict=False, reason="BUG-100: …")`; card revised | failed under `desc`; xfailed under the patch after the change; xpasses normally |
| POS-AR-02 | `tests/unit/services/test_purchase_order_service.py` | BUG-2431 (`DAOPurchaseOrderReturnItem.get_by_return`, no `ORDER BY`; credit-note line numbering follows it) | candidate | yes: `@xfail(2431, strict=False)`; `_BUGS[2431]` added; card revised (strict proof: PRT-RI-10) | failed under `desc` (`[(1, L2), (2, L)]`); xfailed under the patch after the change |
| POS-AR-08 | same | BUG-2431 | candidate | yes: same as POS-AR-02 | same |
| WOM-CT-16 | `tests/unit/managers/test_work_order_manager.py` | BUG-2331 (template approvers read with no order) | candidate when the sweep ran. **BUG-2331 was fixed by PR #8, which was merged into this branch during the sweep** (`get_by_template` now has `ORDER BY id`). Order is now determined. | no (marker added, then reverted) | failed under `desc` on the old code; passes under `desc` on the current code |
| AIV-AH-27, AIV-PF-18 | `tests/unit/dao/test_account_invoice.py` | n/a | patch side effect (they read the SQL text: "ends in id") | no | failure message is about the SQL text |
| OTP-GT-10, OTP-GW-20 | `tests/unit/dao/test_order_template.py` | n/a | patch side effect (they count or inspect `ORDER BY` terms) | no | same |
| PBL-G-12 | `tests/unit/dao/test_production_batch_stage_log.py` | n/a | patch side effect | no | same |
| PUO-LH-04 | `tests/unit/dao/test_purchase_order.py` | n/a | patch side effect | no | same |
| TRO-LH-03 | `tests/unit/dao/test_transfer_order.py` | n/a | patch side effect | no | same |

The changed cards follow the WOM-GI-01 pattern:

- the title gets "*(revised 2026-11-27, order sweep)*";
- the Rules line gets `[BUG-n]`;
- the Expect line becomes "xfail BUG-n (non-strict): …" and says why, and which card is the strict proof.

## Run after the change

`test_project_manager.py`, `test_purchase_order_service.py` and `test_work_order_manager.py` (`-n 4`): 1021 passed, 269 xfailed, 5 xpassed (the three new non-strict ones, WOM-GI-01 and POS-LR-03), 0 failed.

## Unsure / follow-up

1. **The reverse case: strict xfails that fail today only by physical order.** *Resolved, see the next section.* These 8 tests are strict xfails for `paginate-before-filter` bugs, all in project areas. They **xpassed** under `desc`: when the hidden rows sort after the page, the bug does not show. So their "fails today" depends on physical order. On another machine they could xpass, and a strict xpass breaks CI, which is the mirror image of WOM-GI-01. PRJM-L-10 and PRJM-L-09 (by factory) were already made non-strict for this reason. I did not change these 8, because they are outside the brief (the brief is about pass tests). Consider the same non-strict treatment, or making the Given independent of order:
   - PRJM-L-07 (BUG-1958)
   - PJS-L-07 (BUG-1958)
   - PCS-L-20 (BUG-2277)
   - PCS-L-22 (BUG-1278)
   - PCNS-L-12 (BUG-2293)
   - PCTS-L-17 (BUG-2298)
   - PCIS-L-12 (BUG-2308)
   - MPCSV-L-12 (BUG-2611)
2. **The code changed during the sweep.** PRs #7 (attachment_link) and #8 (work_order_template) were merged into this branch while the runs were in progress. Fixes only add ordering, so they can remove candidates but cannot add new ones. WOM-CT-16 is the only one affected.
3. **Fair-patch assumption.** The patch assumes every legal order counts. Postgres on Linux could in principle produce orders other than id ascending or descending (for example after `UPDATE`s move rows). A test with 3+ tied rows whose assertion holds for both id orders would not be caught. I saw no such shape among the hits.
4. **Uncommitted changes by someone else.** `docs/testing/bugs.md`, `docs/bugfix/{improvements,questions,state}.md` and the new `docs/bugfix/units/*` and `wrong-tests.md` are modified or untracked in the working tree. Those are not from this sweep. Nothing was committed.

## Follow-up: 8 strict xfails made non-strict

**Decision.** Decided by Claude under the reviewer's delegation (2026-11-27), following the PRJM-L-09/L-10 precedent.

**The 8 tests.** These are strict xfails for "paging happens before the filter" bugs, in project areas. They xpassed under the `desc` patch: they fail today only because physical order puts the filtered-out row on the page.

**What changed.** For each one:
- the marker is now `strict=False` with the same bug reason;
- the card title gets "*(revised 2026-11-27, order sweep)*";
- the Expect line becomes "xfail BUG-n (non-strict): fails only when physical order puts the filtered-out row on the page; strict proof is …".

I found the remaining strict proofs by collecting every xfail marker in `tests/unit` and filtering by bug id.

| Test id | Test file | Bug | Strict proof that remains |
|---|---|---|---|
| PRJM-L-07 | `tests/unit/managers/test_project_manager.py` | BUG-1958 | PRJM-L-08 (skip case; stayed xfail under both patch runs) |
| PJS-L-07 | `tests/unit/services/test_project_service.py` | BUG-1958 | PJS-L-08 (skip case) |
| PCS-L-20 | `tests/unit/services/test_project_component_service.py` | BUG-2277 | PCS-L-21 (skip case); also PCS-L-23 (statement count) |
| PCS-L-22 | `tests/unit/services/test_project_component_service.py` | BUG-1278 | PCS-L-19 and about 30 other strict BUG-1278 cards |
| PCNS-L-12 | `tests/unit/services/test_project_component_note_service.py` | BUG-2293 | PCNS-L-14, statement count only (L-13 was already non-strict) |
| PCTS-L-17 | `tests/unit/services/test_project_component_task_service.py` | BUG-2298 | PCTS-L-19, statement count only (L-18 was already non-strict) |
| PCIS-L-12 | `tests/unit/services/test_project_component_item_service.py` | BUG-2308 | PCIS-L-14, statement count only (L-13 was already non-strict) |
| MPCSV-L-12 | `tests/unit/services/test_miscellaneous_project_cost_service.py` | BUG-2611 | MPCSV-L-13, statement count only |

**Bugs left without a strict proof.** None of these bugs is left with no strict card at all.

**Partial gap.** BUG-2293, BUG-2298, BUG-2308 and BUG-2611 still have a strict card, but it only checks the statement count (one read per row). It does not check the paging itself. A fix that removes the extra reads but still filters after paging would keep CI green. Those four bugs need an order-independent paging card later, for example a skip case like PRJM-L-08 or PCS-L-21. Projects: revisit after launch.

**Run.** The 8 changed test files (the 7 above plus `test_purchase_order_service.py`), `-n 4`: 911 passed, 327 xfailed, 3 xpassed, 0 failed.

## Plugin artefacts, not findings

These 7 tests failed only because the patch adds an `ORDER BY` term to the SQL they inspect. They are a plugin artefact, not a finding.

- AIV-AH-27 and AIV-PF-18 (`tests/unit/dao/test_account_invoice.py`)
- OTP-GT-10 and OTP-GW-20 (`tests/unit/dao/test_order_template.py`)
- PBL-G-12 (`tests/unit/dao/test_production_batch_stage_log.py`)
- PUO-LH-04 (`tests/unit/dao/test_purchase_order.py`)
- TRO-LH-03 (`tests/unit/dao/test_transfer_order.py`)
