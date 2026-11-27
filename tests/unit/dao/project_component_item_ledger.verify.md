# Verification — `app/dao/project_component_item_ledger.py`

> **Current verdict: PASS (round 2, 2026-11-10, cases revision 3): finding 1 is closed. See "Round 2" at the end. Still *revisit after launch* (OQ-27).**
>
> **Verdict:** NEEDS WORK (one small case-designer item; the tests themselves are faithful)
> Tests: 208 passed · 51 xfailed (reproduced ✅, 3 of 3 runs, also under `TimeZone` America/New_York and Asia/Dhaka) · coverage 97% branch (line 121, dead `get_by_order`)
> Mutation: 43 mutants · 40 killed · 3 survived → score 100% (after excluding 0 equivalent, 3 dead, 0 bug-path). Hand variants: 75 · 67 killed · 8 survived (6 bug-path / intended fix, 2 case-missing)
> Source commit: e48a092 · Cases revision: 2
> **Revisit after launch** (owner, 2026-11-10, OQ-27): nothing writes this ledger today; every card builds its own rows. The 32 xfail cards of BUG-640, 2462, 2463, 2464 and 654 carry the tag and were checked like the others.

## Summary
These tests can be trusted. All 259 cards are implemented, one test or param id each, with every Then line asserted as carded and every xfail failing on the card's "Fails today on" line. mutate.py's survivors are all in dead `get_by_order`. Of my 75 hand variants (workspace scoping with W0 and W2 on both sides, filters, unordered and reversed lists, tie-breaks, paging, case-insensitive and partial type matching, local-clock and tz-stripped bounds, balance and total arithmetic, rounding, float and int fallbacks, joins and parent filters, flushes, locks), every wrong one is caught except one: adding `FOR UPDATE` to the lists or to the latest-entry lookup. The spec says these reads take no lock, but only the xfail PF-17 checks for one. The case designer needs to add one `"FOR UPDATE" not in sql` Then line to six existing cards. It must not be `lock_part == ""`, which is vacuous for a plain lock (see Finding 1).

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | CI-22, CO-22, TT-22, DR-22, BAL-32, LE-26 (spec Overview "nothing flushes, commits or locks"; Side effects: none) | No pass card checks that the read takes no row lock. Only PF-17 (xfail BUG-645) has `lock_part == ""`. | Hand variants `lock_lists` (`.with_for_update()` before `.offset` in all four lists) and `lock_latest` (`.with_for_update().first()` in `calculate_balance` and `get_latest_entry`): 208 passed, 51 xfailed. `lock_total` is caught only because Postgres rejects `FOR UPDATE` with an aggregate. | **case designer**: add `statement: "FOR UPDATE" not in sql` to those six cards, then the executor implements them. Correction by the batch verifier (2026-11-10): **not** `lock_part == ""`. Here `lock_part` is the text after `FOR UPDATE`, which is empty for a plain lock too, so that line would be vacuous (`test_…py` line 274). Fix PF-17's line the same way. |

No fidelity findings: no missing, weakened or changed assertions, no wrong setup, no swallowed failures, no mocks, no dishonest xfails. Notes on choices I checked and accept:
- Four lists share one parametrized body for cards 01–16 and 18–22. My script diffed the CI, CO, TT and DR cards: they differ only in the When call, which `list_call` reproduces.
- BAL-11 … 14 add `db.expire_all()` before the When. This is setup only and the notes record it. Without it the identity map would return the unrounded Python value, so the card would not check what is stored.
- DR-34 / 35 leave out `as exc`. Nothing later reads `exc`.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 4 | 121 | `return` → `return None` (`get_by_order`) | dead | Spec Q2 / Not specified: remove. I grepped `app/`, `scripts/` and `tests/`: `project_component_item_ledger_dao` is used only by `LedgerManager` (`get_by_component_and_item`, `get_by_component`, `calculate_total_cost_for_component`, `get_by_performer`), never `get_by_order`. | — |
| 26 | 124 | `workspace_id ==` → `!=` (`get_by_order`) | dead | as #4 | — |
| 27 | 125 | `order_id ==` → `!=` (`get_by_order`) | dead | as #4 | — |

Hand variants that survived the pass tests (in-process plugin `omdv\C\variant_c.py`, which rebuilds the DAO class from patched source; `app/` is never written):
| Variant | Class | Why | Fix by |
|---|---|---|---|
| `tie_fix_iddesc` (`…, id DESC` everywhere) | bug-path (intended fix) | With `--runxfail`, the 6 strict order alarms (CI/CO/TT/DR-21, BAL-17, LE-10) XPASS and the 10 non-strict tie cards pass. BUG-640 / 2462 / 2463. | — |
| `tie_idasc`, `tie_notes`, `tie_qty_desc` (wrong second key) | bug-path | Ties are unspecified until the fix. All 51 xfail cards stay failing, so once a fix is written the strict alarms reject a wrong tie-break. | — |
| `dr_fix_utc` (aware bounds → UTC, naive) | bug-path (intended fix) | Exactly DR-38 … 41 and DR-46 … 49 XPASS (8 strict). BUG-2464. Wrong conversions are caught: `dr_strip_tz` by DR-43, `dr_local_clock` by DR-42 … 44 / 50 / 51. | — |
| `tc_net_exact` (subtract `transfer_out` / `damaged`, exact) | bug-path (intended fix) | Exactly TC-09 … 14, 28, 29 XPASS (8 strict). BUG-654. The case-insensitive / trimmed variant `tc_net_ci_trim` is caught by TC-24 … 27. | — |
| `lock_lists`, `lock_latest` | case-missing | Finding 1 | **case designer** |

Variants that were caught (67), by group:
- **Workspace scoping:** drop all filters, drop TT or DR only, also match W−1 or W+1, `>=`, `<=`.
- **Component and item filters:** drop or loosen to `>=` / `<=`.
- **Lists:** order asc, no order, id-only order. Latest by id or unordered.
- **Paging:** no offset, no limit, cap 100, floor 1, skip floor 0, limit+1.
- **Type matching:** ilike, like, lower, contains, startswith, trim.
- **Dates:** tz stripped, local clock, naive bound read as local, midnight end widened to the whole day, microseconds truncated, `None` taken as an open bound, reversed range swapped.
- **Balance:** `value_before`, `qty_before`, `or 0`, `or 0.0`, float, `None` value, quantize to 1 decimal place, list instead of tuple, oldest entry, empty result as `None` / `(0, 0)` / `(0, 0.0)`.
- **Total:** `unit_cost`, float, `0`, `0.0`, `None`, quantize to an integer, `abs`, `max`, float sum, component dropped, workspace dropped.
- **Side effects and parents:** `db.flush()` first, a join on a live project, a filter on active items, a subquery on live projects.

Numbering, year-from-clock, taken-number, prefix and void-column variants do not apply: this table has no number, no prefix, no void columns, and nothing reads the clock. `performed_at` is always set by the caller.

## Traceability
cases 259 · tests 259 (collected items; each is one card ID, by test name or `pytest.param(id=…)`) · unmatched: none · duplicated: none · marker mismatches: none. 208 `pass` cards have no marker. 40 strict and 11 non-strict xfail cards match their Expect lines. Every reason names its BUG ID. BUG-640, 2462, 2463, 2464 and 654 reasons carry "revisit after launch (owner 2026-11-10)". BUG-645 and BUG-100 reasons are plain, as carded. Every BUG ID used (100, 640, 645, 654, 2462, 2463, 2464) exists in `docs/testing/bugs.md`. No `local-run.json`: all tests are `# [claude]`.

`--runxfail`: 51 failed. Each failure was mapped to its `# Then N` comment by my script `omdv\C\failson_c.py`:
- Order alarms fail at Then 4: CI / CO / TT / DR-21, BAL-17, LE-10.
- Non-strict tie cards fail at Then 2: list 19 / 20, BAL-16, LE-09, INH-02.
- INH-03 fails at Then 2.
- DR-38 … 41 and DR-46 … 49 fail at Then 1.
- TC-09 … 14, 28, 29 fail at Then 2.
- The 17 PF cards fail with `AttributeError` on the `get_by_performer` call, as their cards say. PF-11 / 12 fail inside Then 1's `raises` block.

None fails on setup or import.

## Commands run
```
COVERAGE_FILE=omdv\C\.cov{1,2,3} .venv/Scripts/python.exe -m pytest tests/unit/dao/test_project_component_item_ledger.py -q -p no:cacheprovider -o addopts="" --cov=app.dao.project_component_item_ledger --cov-branch --cov-report=term-missing
  app\dao\project_component_item_ledger.py  29  1  2  0  97%  121
  208 passed, 51 xfailed   (×3: 19.89s, 18.28s, 17.87s)
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_project_component_item_ledger.py -q -p no:cacheprovider -o addopts="" --runxfail -rf
  51 failed, 208 passed
PGOPTIONS="-c TimeZone=America/New_York" … / "-c TimeZone=Asia/Dhaka" …
  208 passed, 51 xfailed (both)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/project_component_item_ledger.py tests/unit/dao/test_project_component_item_ledger.py --json omdv\project_component_item_ledger.mut.json
  Mutants: 43 · killed 40 · timeout 0 · survived 3 · score 93%  (survivors #4, #26, #27, all in get_by_order)
VARIANT=<name> PYTHONPATH=omdv\C .venv/Scripts/python.exe -m pytest … -p variant_c -m "not xfail"   (omdv\C\runvariants.py, 75 variants)
  67 killed · 8 survived (tie ×4, dr_fix_utc, tc_net_exact, lock_lists, lock_latest)
VARIANT=<survivor> … -p variant_c -rX   (full file)
  tie_fix_iddesc: 6 failed (strict XPASS), 10 xpassed · dr_fix_utc: 8 failed (strict XPASS) · tc_net_exact: 8 failed (strict XPASS) · others: 208 passed, 51 xfailed
grep -rn "project_component_item_ledger_dao|ProjectComponentItemLedgerDAO|project_ledger_dao" app/ scripts/ tests/
  callers: LedgerManager lines 302, 311, 340, 689 only — get_by_order has none
```
Scripts (mine): `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\C\` — `trace.py`, `trace2.py`, `dumpmarks_c.py`, `cmpfam.py`, `failson_c.py`, `variant_c.py`, `mkvariants.py`, `runvariants.py`.

## Round 2 — 2026-11-10
Narrow re-check of cases revision 3 (patched, not regenerated). **Verdict: PASS.**

**Changed cards:** PCIL-CI-22, CO-22, TT-22, DR-22 (one parametrized test, Then 10), BAL-32 and LE-26 (Then 9) add `"FOR UPDATE" not in sql`; PF-17 Then 8 replaces the vacuous `lock_part == ""`.

**Fidelity:** The four list cards share one parametrized test (`pcil_list_22`), which asserts the new line for each param. BAL-32 and LE-26 assert it as their last Then. PF-17 is still xfail BUG-645 and stops at the call, its card's line. **0 unfaithful.**

**Runs:** 208 passed, 51 xfailed ×3 · coverage 97% branch (line 121, dead `get_by_order`) · `--runxfail` 51 failed, 208 passed. No flaky outcome. Runs (private `COVERAGE_FILE`, `omdv\R2\.cov`): `pytest <file> -q -p no:cacheprovider -o addopts=""` with `--cov=app.dao.<module> --cov-branch` once, plain twice, then `--runxfail` once.

**Variants:**
- Lock per method on the six live reads, OF and plain: all 12 **killed**. The four lists are caught by `pcil_list_22`, `calculate_balance` by BAL-32, `get_latest_entry` by LE-26. `lock_lists` and `lock_latest` used to survive.

Variants: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\plug\r2var.py` (per-method `FOR UPDATE OF <table>` and plain `FOR UPDATE`; create's year hard-coded 2026, bypassing the tests' clock patch; a hidden `db.get` of the parent), driven by `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\run_r2.py` on the pass tests (`-m "not xfail"`); results in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omdv\PT\r2.txt`. `mutate.py` was not re-run: Revision 3 only adds assertions and one card, so no mutant killed in round 1 can survive now.

**Open items:** None.
