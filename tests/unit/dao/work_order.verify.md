# Verification — `app/dao/work_order.py`

> **Current verdict (Round 2, 2026-11-14, cases Rev 3):** PASS — F1 closed by WKO-NN-27; 167 passed · 22 xfailed ×3, coverage 95% branch; `get_next_number` re-mutation 13/13 killed. See "Round 2" at the end.
> **Round 1 verdict:** PASS (one advisory case-missing item for the case designer, non-blocking: it adds a BUG-2676 xfail card and changes nothing that passes today)
> Tests: 167 passed · 21 xfailed (reproduced ✅; every xfail fails on its carded Then line) · coverage 95% branch (110 statements, 7 missed = dead `restore`, 38 branches, 0 partial)
> Mutation: 114 mutants · 110 killed · 4 survived → score 100% (after excluding 1 equivalent, 3 dead, 0 bug-path); raw 96%
> Source commit: e48a092 · Cases revision: 2

## Summary
These tests can be trusted. Traceability is clean (188 cases, 188 collected tests, every marker as carded), the scripted and manual fidelity read found no missing, weakened or changed assertion and no extra mock, and all three plain runs plus the coverage and `--runxfail` runs reproduce the notes exactly (167 / 21; every xfail fails on its carded Then line). Every non-dead, non-equivalent mutant is killed.
The dead-code claim holds: `restore` has no caller. One hand variant found an uncovered side of `get_next_number` R4: suffixes that Python's `int()` accepts but that are not all digits (`1_000`, ` 7`, `+9`, Arabic-Indic digits) are read as numbers today. This is inside BUG-2676 (R4 is already tagged), so it is not a new bug. It needs one more xfail card so the fix is pinned to "ASCII digits only" (F1).

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| F1 | case-missing (advisory) | `get_next_number` R4 / line 355 | No card stores a suffix that `int()` parses but that is not all digits. Today `WO-2031-1_000` alone → `WO-2031-1001`, `WO-2031- 7` → `-008`, `WO-2031-+9` → `-010`, and `WO-2031-٣` is read as 3. R4 (intended, BUG-2676) says such a suffix is ignored. Without a card, a fix that keeps `int()` (or `str.isdigit()`, which accepts `٣`) passes every BUG-2676 card. | hand variant `test_int_lenient_suffix_alone` (scratch) | **case designer**: add one strict xfail BUG-2676 card, e.g. `WO-2031-005` plus `WO-2031-1_000` → `WO-2031-006` (today `-1001`). Fix note for BUG-2676: match `^[0-9]+$`, not `int()` / `isdigit()`. |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 16 | 83 | `_sheet_base_query(exclude_completed: bool = False)` → `True` | equivalent | Both callers (`list_for_sheet` line 256, `count_for_sheet` line 293) always pass `exclude_completed=` explicitly, so the default is never read. The public defaults are pinned by LS-08 / CS-06. | — |
| 36 | 380 | `restore`: `return db_obj` → `return None` | dead | `restore` has no caller (spec Q4, Not specified) | — |
| 49 | 374 | `restore`: `is_active = True` → `False` | dead | same | — |
| 50 | 375 | `restore`: `is_deleted = False` → `True` | dead | same | — |

## Hand variants (verifier probes, scratch `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaov\wo\test_wo_hand.py`, nothing committed)
| Variant | Covered by cards? | Result today | Verdict |
|---|---|---|---|
| Voided / deleted rows in lists, counts, dots, `get_by_machine_date_type` | yes (SB-04, SB-06, GW-05, GW-10, FD-03/09, OR-02/08, MD-05/06/07, DC-03) | as spec | — |
| Open scope = every status except `VOIDED` (MD) / "planned" stage filter (SF-10 … 15, CS-04, DC-14) | yes | as spec; DC-14 strict xfail BUG-2675 | — |
| Numbering per workspace, not global (NN-13 … 16) | yes | as spec | — |
| Past 999: rows `-995` … `-1002` stored → next `WO-2031-1000`, which exists | yes (NN-05 … 07) | collision, BUG-2676 | known |
| Year from the local clock (NN-20, NN-21) | yes | BUG-2678 | known |
| Prefix case (NN-18), prefix elsewhere (NN-19) | yes | as spec | — |
| Text vs numeric order (NN-07, NN-08) | yes | BUG-2676 | known |
| `int()`-lenient suffixes alone: `WO-2031-1_000` → `-1001`, `WO-2031- 7` / `-7 ` → `-008`, `WO-2031-+9` → `-010`, Arabic-Indic `-٣` read as 3 | **no** | read as numbers; R4 says a suffix that is not all digits is ignored | case-missing (F1); part of BUG-2676 R4, no new bug |
| `%` / `_` / `\` in sheet search (SF-25 … 27), also on `assigned_to` (`"50%"` matched `"500 done"`) | yes (number / description); assignee not separately | BUG-2672 | known |
| Search on deleted parties | n/a (no party join in this DAO) | — | — |
| Tie-breaks: GW / MD (BUG-2670 / 2671), FD-10, OR-11, LS-01 | yes | as spec | — |
| Locks: `"FOR UPDATE"` in any SQL of `list_for_sheet`, `count_for_sheet`, `count_by_calendar_date_for_sheet`, `get_by_id_and_workspace`, `get_next_number` | yes (one card each) | none | — |
| W0 / W2 scoping on every read | yes | as spec | — |
| `get_by_machine_date_type(planned_date=None)` | no | returns an undated order (`= NULL` becomes `IS NULL`) | no caller passes `None` (both template generators pass a date); not a rule — noted only |
| Money: `cost` half up (GI-08 … 11, HR-15) | yes | as spec | — |

## Dead code
`restore` (lines 372–380): `grep -rn "\.restore(" app tests scripts` finds only `inventory.py`'s own `self.restore` and the work order **template** / type restores; nothing calls `work_order_dao.restore`. Confirmed dead (spec Q4). Its 7 lines are the only missed coverage, and its 3 mutants are `dead`.

## Traceability
cases 188 · tests 188 collected (176 functions; GI-08 … 11, NN-02/04/05/06/10/18/19 and NN-07/08/09/26 are `pytest.param(id="WKO-…")`) · unmatched: none · tests without a case ID: none · marker mismatches: none (19 strict `xfail` with every carded BUG ID in the reason, GW-28 and MD-16 non-strict as carded; every BUG ID exists in `bugs.md`).

Fidelity (scripted, then read): every Then expression of every card appears in its test after name normalisation (the only textual differences are `a_id` locals read before `expunge_all()`, `rec.` prefixes, and the When helpers `_future`, `_outside`, `_mdt`, whose keyword defaults equal the cards' When lines); every Given string, "but" column, state word (completed / voided / started / deleted), Dhaka, seqscan, dirty+pending and clock value matches the card; letter→row mapping in every `ids(...)` / `result.id` check matches the card. No `try/except`, no `pytest.raises(Exception)`, no patch beyond the Conventions' clocks and the SD-07 commit spy. NN-17 runs its When under `clockN(JUNE, JUNE)` (harmless: the Conventions put every NN card under it).

## Commands run
```
COVERAGE_FILE=C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaov\wo\.coverage
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_work_order.py -q -p no:cacheprovider -o addopts="" --cov=app.dao.work_order --cov-branch --cov-report=term-missing
  app\dao\work_order.py  110  7  38  0  95%  374-380
  167 passed, 21 xfailed in 21.34s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_work_order.py -q -p no:cacheprovider -o addopts="" --runxfail -rf -p failat_wo   (own plugin, scratch)
  21 failed, 167 passed — 21 of 21 fail on the card's "Fails today on" Then line (TypeError at the call for DC-12/13/14/17)
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_work_order.py -q -p no:cacheprovider -o addopts=""   (twice more)
  167 passed, 21 xfailed in 11.13s
  167 passed, 21 xfailed in 10.80s
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/work_order.py tests/unit/dao/test_work_order.py --timeout 300 --json C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaov\wo\mut.json
  Mutants: 114 · killed 110 · timeout 0 · survived 4 · score 96%  (survivors #16, #36, #49, #50)
.venv/Scripts/python.exe -m pytest C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaov\wo\test_wo_hand.py -q -p no:cacheprovider -o addopts="" -p tests.unit.conftest --rootdir . -s
  hand variants above
```
Scripts (own): `trace.py`, `dumpmarks_wo.py`, `fid.py` … `fid4.py`, `failat_wo.py`, `test_wo_hand.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaov\wo\`.

## Round 2 — 2026-11-14

> **Verdict:** PASS
> Tests: 167 passed · 22 xfailed (reproduced ✅, 3 runs) · coverage 95% branch (only 374-380, dead `restore`)
> Mutation (narrow, `get_next_number` L344-359): 13 mutants · 13 killed · 0 survived → 100%
> Source commit: e48a092 · Cases revision: 3 · Tests and notes: Revision 3

**What changed:** cases Rev 3 adds WKO-NN-27 (strict xfail BUG-2676, R4: `WO-2031-005` beside `WO-2031-1_000` → `WO-2031-006`), for round-1 F1. The executor added it as a fifth `pytest.param` of `test_wko_nn_numeric_highest_suffix`; no other test changed.

**Fidelity of NN-27:** faithful. Given 1–2 are built with `mk("WO-2031-005")` and `mk("WO-2031-1_000")` in W1. The When is `dao.get_next_number(db, workspace_id=g.W1.id)` under the convention clock (2031). `# Then 1` asserts `result.startswith("WO-2031-")` and `# Then 2` asserts `result == "WO-2031-006"`, both exact and in card order. The parametrized test's marker is `xfail(strict=True, reason=_BUG_2676)`, and the reason names BUG-2676. There are no extra mocks.

**F1 status:** closed. F1 was a gap, not a surviving mutant: no mutant reaches it, and the bug-path test is excluded from mutation. It is now pinned two ways:
- **Today:** with `--runxfail`, NN-27 fails on Then 2 with `'WO-2031-1001' == 'WO-2031-006'`, as the card's "Fails today on" says.
- **Intended fix:** I wrote my own reference plugin (`ref_nn.py`): only `[0-9]+` full-match suffixes, numerically highest. Under it, `-k test_wko_nn --runxfail` passes NN-07, 08, 09, 26 and 27. The only failures are NN-20 and NN-21, which are BUG-2678 (UTC year), deliberately not part of this probe.

Residual future note, unchanged from round 1: a fix using `str.isdigit()` would pass NN-27 but still accept Arabic-Indic digits; the fix should match `^[0-9]+$`.

**Traceability (whole file, collection-based):** 189 cards and 189 collected items, with nothing missing, extra or duplicated. There are 0 marker mismatches: 167 pass with no marker, 20 strict and 2 non-strict (GW-28, MD-16) as carded, and every BUG ID is in `bugs.md`. With `--runxfail`, all 22 fail on their carded Then line (or in the When for DC-12/13/14/17, `TypeError`, as carded).

**Findings:** none. **Routed:** nothing.

**Commands run:**
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_work_order.py -q -p no:cacheprovider -o addopts="" --collect-only -p dumpmarks_wo   → 189 tests collected
.venv/Scripts/python.exe r2/trace2.py …   → cards 189 items 189 · missing [] extra [] dups [] · marker mismatches []
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_work_order.py -q -p no:cacheprovider -o addopts=""   → 167 passed, 22 xfailed (run 1)
  (run 2)                                                                                                   → 167 passed, 22 xfailed
COVERAGE_FILE=…\wo\r2\.coverage … --cov=app.dao.work_order --cov-branch --cov-report=term-missing          → 167 passed, 22 xfailed · app\dao\work_order.py 110 7 38 0 95% 374-380
… --runxfail -p failat_wo                                                                                  → 22 failed, 167 passed (all on the carded line)
… --runxfail -p ref_nn -k test_wko_nn                                                                      → 25 passed, 2 failed (NN-20, NN-21: BUG-2678)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/work_order.py tests/unit/dao/test_work_order.py --lines 344-359 --json …\wo\r2\mut_nn.json
  Mutants: 13 · killed 13 · timeout 0 · survived 0 · score 100%
```
Round-2 scripts (own): `trace2.py`, `ref_nn.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaov\wo\r2\`.
