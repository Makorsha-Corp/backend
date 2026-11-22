# Verification — `app/managers/machine_maintenance_log_manager.py`

> **Verdict:** PASS (round 2, 2026-11-01) — the 3 new tests are faithful and findings 1 and 2 are closed. No test edited.
> Tests: 283 passed · 114 xfail (reproduced ✅) · coverage 100% branch
> Mutation: 69 / 69 = 100%, from round 1; not re-run, on the coordinator's instruction
> Source commit: e48a092 · Cases revision: 1 (397 cases; spec APPROVED)
> Round 1 is below, kept as written.

## Round 2 (2026-11-01) — scoped to L-136, L-137, U-121

- **Read:** the 3 tests against their cards. Each Given row, When call and numbered Then line matches, in order. All `# [claude]`, all `pass` with no marker.
- **Variants, each failing only the right card, with 397 collected:**

| Round 1 survivor | Now fails | How |
|---|---|---|
| `dl_nows_none` | L-136 T1 only | the W2 row is returned |
| `dl_nows_type` | L-137 T1 only | the W2 row is returned |
| `s_u_summary_limit` | U-121 only | `ValidationError` while the When builds `LU`, so before `# Then 1` |

- **Runs:** 3 without `--runxfail` gave 283 passed, 110 xfailed, 4 xpassed, including coverage at 100%. With it: 110 failed, 287 passed. The same 110 cards fail on the same Then lines as round 1. L-124 … L-127 stay non-strict and passed in these runs.
- **Reference:** my plugin, unchanged, passed 397 of 397 with `--runxfail`.
- **Comparison:** `rebuild.py`, unchanged, reports 397 cards, 397 tests, 0 unmodelled, and only the two cosmetic docstrings of L-73, L-74. Both counts match the cases header and the notes' Result line. `ruff check` passes. `git diff --stat app/managers/machine_maintenance_log_manager.py` is empty.
- **Accepted, not open:** finding 3 (optional, no verdict impact) and the three `[money]` readings under "Flagged, not decided". No order-workflow question.
- **Limits:** mutation and the other 282 variants were not re-run, and 3 added tests cannot lower a kill count. The 394 earlier tests were re-run and re-compared by script, not re-read; I kept no byte copy of round 1 to diff against. The selftest was not repeated, because `rebuild.py` did not change.

Only this report was written in the repo. No commit. No model server.

---

The sections below are round 1 (2026-10-31), kept as written.

> **Verdict:** NEEDS WORK (2026-10-31) — only the case designer has work: 3 small cards for 2 rule gaps. No test is wrong; no test-side finding, no test edited.
> Tests: 280 passed · 114 xfail (reproduced ✅; 106 strict, 8 non-strict) · coverage 100% branch (63 statements, 22 branches)
> Mutation: 71 mutants · 69 killed · 2 survived → score 100% (69 / 69, after excluding 1 equivalent, 0 dead, 1 bug-path)
> Fidelity: **0 of 394 unfaithful**
> Hand variants on my reference: 285 · 272 caught · 13 survived (3 `case-missing`, 9 equivalent, 1 accepted spec gap)
> Source commit: e48a092 · Cases: first revision (394 cases; spec APPROVED)

## Summary
- **The translated tests can be trusted as written.** My own script rebuilt the expected statements of every card from the card text alone and compared them with each test's syntax tree. It found no real difference in 394 tests. It finds 1 107 of 1 107 planted mistakes.
- **The unusual ones were read by hand:** 20 cards with savepoints, foreign keys, the plain-string type, the response schema, the Given calls to `M`, the direct event row and the tie cards. All match. The clock card D-19 and the sql_log card L-128 were read too.
- **A reference fix written from the spec passed 394 of 394 on its first run**, with `--runxfail`. A second, different fix (BUG-1101 in the manager, not the DAO) passes too, so the cards do not depend on one fix.
- **Why NEEDS WORK:** 3 hand variants break a written rule and no test notices. Two are a workspace leak on the no-filter and by-type lists. Scratch tests show 3 small cards close them.
- **No new owner question.** No order-workflow question arises. Money: see "Flagged, not decided".

Written by Claude (all 394 under `# [claude]`). No `machine_maintenance_log_manager.local-run.json` exists. Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 394.

## Findings
| # | Kind | Rule | What is wrong | Evidence (survives every test) | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing (isolation) | `list_logs` R1, R3: "the workspace's live logs" | No card builds a W2 row on a W1 machine on the **no-filter** or the **by-type** path. L-12, L-13 do it for the two machine paths, and U-12, G-23, D-10 for the one-row lookup. A BUG-1101 fix that swaps the log's `workspace_id` filter for "the machine is in this workspace" passes on these two paths, and W1 then lists a W2 row. Each path is its own query, which is why the file gives each path its own cards. | `dl_nows_none`, `dl_nows_type` | **case designer** (2 cards) |
| 2 | case-missing (low) | `update_log` Inputs "with the limits of `create_log`"; spec "`summary` has no length limit" | C-30 holds this on Create. No card sends a long `summary` on Update, though `cost`, `performed_by` and dates all have both sides. A limit on `MachineMaintenanceLogUpdate.summary` passes. | `s_u_summary_limit` (`max_length=99999`) | **case designer** (1 card) |
| 3 | card note (low, optional) | 44 cards, among them C-27 … C-29, U-104, U-105, U-114, U-115 | Their 78 `nothing written`, `unchanged` or `event` lines cannot fail on their own: the When only builds a schema and `M` is not called. The tests match their cards, so this is not a test fault. Same kind as `machine_manager` finding 11. | counted by script | **case designer**, optional |

No fidelity finding.

### Scratch tests that close the gaps
3 tests in `mmlmv\prop\test_prop_mmlm.py`, not in the repo. Each passes today and on the reference, and fails only on the variant shown.

| Scratch test | Fails on |
|---|---|
| no filter: a W2 row on a W1 machine does not appear | `dl_nows_none` |
| by type: a W2 row on a W1 machine does not appear | `dl_nows_type` |
| update with a summary of 100 000 characters is stored and copied into the entry | `s_u_summary_limit` |

## Flagged, not decided
**Order workflow:** none. Maintenance logs touch no order.

**Money:** no new question and no verdict impact. The cases file tags three readings `[money]`. Notes record 1 and 2 as accepted under delegation, so they are not the owner's own answers; the owner may want to look, as the owner's rule is to be asked on money.

| Cases gap | Reading the tests pin | Effect |
|---|---|---|
| 1 | `5.0010` refused, `10000000000000.00` refused, `9999999999999.990` accepted | Follows from "trailing zeros do not count" and 13 integer digits. Assumes `ge=0, max_digits=15, decimal_places=2`. |
| 2 | `-0` on update is accepted, stored `0.00`, entry `"0.00"` | R11 says it for create only. |
| 3 | `from_value` is not pinned on an unrefreshed instance | A fix that formats only `to_value` passes (`u_cost_fmt_to_only`). Not reachable: a row read from the database always has two decimals. |

Spec Q1 and Q2 are the owner's own answers, and the tests hold them. Nothing reads `cost` today, so these readings move no figure.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 50 | 101 | `exclude_unset` `True` → `False` | equivalent | `exclude_none` stays and every field defaults to `None`. Re-run with xfails visible: the same 110 fail on the same Then lines. | — |
| 51 | 101 | `exclude_none` `True` → `False` | bug-path (BUG-1153) | Re-run with xfails visible: U-31, U-32, U-33, U-34 pass, nothing else changes. Resolves with the fix. | — |

Score: 69 / (71 − 1 equivalent − 0 dead − 1 bug-path) = 69 / 69 = **100%**. Every kill's last line reports a real failure; none is an error-only kill.

## Hand variants
`mmlmv\plug\ref_mmlm.py` is my pytest plugin. It swaps the source of the schemas, the DAO and the manager in memory; nothing is written to `app/`. It fixes BUG-1100, BUG-1101, BUG-1102, BUG-1150 … BUG-1158. Each variant in `variants.py` is a text edit on it, asserted to apply, run with `--runxfail` on all 394. Every run counted here collected 394 tests, with no setup failure.

| Group | Variants | Caught | Survivors |
|---|---|---|---|
| Schemas: `ge`, digits, decimals, trailing zeros, trim, blank, 255, null per field, Create and Update apart, response stays open, no date bound, unknown keys | 54 | 53 | `s_u_summary_limit` (finding 2) |
| `create_log`: R1–R6, R14–R17, factory check on each state and order, commit, refresh, entry | 32 | 31 | `c_ws_of_machine` |
| `update_log`: R4–R12a, stamps, no-op, entry, `changes` order and form, labels, each field dropped, commit, refresh | 49 | 46 | `u_event_ws_of_row`, `u_noop_writes_values`, `u_cost_fmt_to_only` |
| `get_log`: flag, default, 400 or other detail, hidden parents, inactive, write | 12 | 12 | none |
| `list_logs` manager: `0`, `""`, 404, paging per path, defaults, clamps, commit | 25 | 23 | `l_zero_both`, `l_both_as_type` |
| DAO lists, per path: live, own machine, workspace, machine, type, hidden parents, inactive, order, tie, paging first | 72 | 68 | `dl_nows_none`, `dl_nows_type` (finding 1), `dl_page_first_own_mach`, `dl_page_first_own_both` |
| DAO lookup: machine, workspace, live only | 3 | 3 | none |
| `delete_log`: R2, R4–R11, hard delete, other rows, entry, each `soft_delete` column, clock | 26 | 24 | `d_event_ws_of_row`, `d_refresh` |
| BUG-1101 on one method only, 400 for 404, deleted checked first, off, skipped with the flag | 12 | 12 | none |

**Survivors that are not findings:**
| Variant | Class | Why |
|---|---|---|
| `c_ws_of_machine`, `u_event_ws_of_row`, `d_event_ws_of_row` | equivalent | The lookup already requires that workspace to equal the argument. |
| `u_noop_writes_values` | equivalent | The values equal the stored ones, so SQLAlchemy issues no UPDATE and nothing is stamped. |
| `d_refresh` | equivalent | The same instance, with database values. Delete has no "as given" rule. |
| `l_zero_both` | equivalent | `0` with a type falls to the machine path, which gives `[]` as well. |
| `l_both_as_type` | equivalent | The branch above already takes that case. |
| `dl_page_first_own_mach`, `dl_page_first_own_both` | equivalent | One machine's rows are all linked or all not. The cases file left these out for that reason. |
| `u_cost_fmt_to_only` | accepted spec gap 3 | Not reachable; see "Flagged". |

**Second reference.** `xm_clean` moves BUG-1101 into the manager on all three methods and passes 394 of 394. It is a control, not counted above.

**Only one card notices** (keep in mind when a card is edited): C-02, C-04, C-05, C-11, C-13, C-16, C-17, C-21, C-30, C-34, C-60, C-62, C-63, C-78; U-11, U-14 … U-17, U-35 … U-37, U-62, U-70, U-100, U-116, U-117, U-119; G-15 … G-19, G-24; L-13, L-30 … L-35, L-37 … L-39, L-42, L-43, L-48 … L-51, L-75; D-01, D-09, D-11 … D-15, D-19, D-20, D-24, D-34.

## Reproduced claims
- **The notes' Result line matches:** 280 passed, 114 xfail, 100% branch, no missed line.
- **Every xfail fails where and why its card says.** Of 110 that fail in the plain plan, 103 fail on the card's Then line, with the value in its parenthesis. 7 fail in the When on the `DataError`, `IntegrityError` or `TypeError` their cards name (C-38, U-54, U-55, U-113, G-11, G-12, D-32). None is a setup error.
- **L-124 … L-127 pass today in most plans and all fail with index scans off**, as the notes say. One passed in the `--runxfail` run with index scans off, so they move inside a plan too. Non-strict is right for them. On the reference they pass, and `dl_summary_tie_*` makes them fail, so the checks are live.
- **No flaky test.** 6 runs without `--runxfail` and 2 with it: the totals move only by L-124 … L-127.
- **All 190 Then lines after an xfail's failure point ran and passed on the reference.** 49 were also made to fail on their own line by a variant.
- Mocks: the card's clock patch on D-19 and the commit spies of C-81, U-120, D-34 only. No broad `pytest.raises`, no `try`, `if` or loop in a test body.

## Traceability
cases 394 · tests 394 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. `# Then N` numbers match in all 394. 280 `pass` cards have no marker; 114 xfail cards name exactly the card's bug, 106 strict, 8 non-strict (L-120 … L-127). All 12 BUG IDs in the cards are in `docs/testing/bugs.md`. All 78 rules of the spec appear on a card. The counts in the cases header match. `ruff check` passes.

The only text differences are the docstrings of L-73, L-74: `'REPAIR'` where the card title has `"REPAIR"`. Cosmetic, not counted.

## How the comparison was done
- **`rebuild.py`** is mine; I did not read the executor's script. It parses each card into Given, When and numbered Then lines, builds the expected Python, and compares canonical syntax trees: every Then block statement by statement and in order; the When exactly; each log's columns as a set; the snapshots after the last Given; pending rows after them; wrappers, marker, docstring, unused fixtures. It models all 1 162 Then lines, with 0 unmodelled.
- **Selftest (`selftest.py`):** 29 kinds of planted mistake, up to 40 of each, sampled from 3 420 sites: dropped or weakened assertions, changed values, wrong row, wrong Given, changed When, wrong marker, broad raises, a moved `# Then`. **1 107 planted, 1 107 found, each against the right card.**
- **Prose:** I listed every card line with its code removed, so nothing outside backticks went unread. The only such text is comments and the fixed phrases of Conventions.
- **Helpers and fixtures** were read once against Conventions.

## Limits of this round
- **The comparison shares one reading with the cards.** It proves test equals card, not that the card is right. The reference and variants cover that side.
- **Two of my own tools were wrong at first, both corrected.** The first comparison reported 21 false differences, because `ast.unparse` writes a bare string as a docstring. And 5 variants never ran: their edit did not apply, pytest collected 0 tests, and my driver showed them as survivors. `report.py` now checks that 394 were collected. 3 were repaired and re-run; 2 were replaced by the `xm_` group.
- **The 4 `x_1101_*` variants can be caught by spill-over** from the other methods, so the 8 `xm_` variants are the ones to rely on.
- **Mutation ran once.** My own checks ran beside it, and other agents may have been running. No error-only kill appears.
- **The variants did not cover every Then line of a pass card.** That side rests on mutation and the variants.
- **141 later Then lines were not forced on their own line.** Many are schema-only lines of finding 3. All ran and passed on the reference.
- Not exercised: service or HTTP level, a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/machine_maintenance_log_manager.py tests/unit/managers/test_machine_maintenance_log_manager.py --timeout 300 --json <scratch>/mut.json
  Mutants: 71 · killed 69 · timeout 0 · survived 2 · score 97%
  SURVIVED #50 L101:56, #51 L101:75

.venv/Scripts/python.exe -m pytest <test file> -q -p no:cacheprovider --cov=app.managers.machine_maintenance_log_manager --cov-branch --cov-report=term-missing -rX
  app\managers\machine_maintenance_log_manager.py   63  0  22  0  100%
  280 passed, 111 xfailed, 3 xpassed
.venv/Scripts/python.exe -m pytest <test file> -q -p no:cacheprovider --runxfail     110 failed, 284 passed
.venv/Scripts/python.exe -m pytest <test file> -q -p no:cacheprovider --tb=no        (twice) 280 passed, 110 xfailed, 4 xpassed
PGOPTIONS seqscan off                                280 passed, 110 xfailed, 4 xpassed
PGOPTIONS index and bitmap off                       280 passed, 114 xfailed
  same, --runxfail                                   113 failed, 281 passed
-W error                                             280 passed, 110 xfailed, 4 xpassed
MMLMREF=fix ... -p ref_mmlm --runxfail               394 passed   (twice)
MUT=50 / MUT=51 ... -p mut1 --runxfail               110 failed, 284 passed / 106 failed, 288 passed
rebuild.py                                           394 cards, 394 tests, 2 differences (the two docstrings), 0 unmodelled
selftest.py                                          1 107 planted, 1 107 found, 29 kinds
drive.py                                             286 runs: 285 variants and the control
.venv/Scripts/python.exe -m ruff check <test file>   All checks passed!
git diff --stat app/managers/machine_maintenance_log_manager.py      (empty)
```
Scratch, all under `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\mmlmv\`: `rebuild.py`, `selftest.py`, `selftest.log`, `xfcheck.py`, `show.py`, `resid.py`, `drive.py`, `drive.log`, `report.py`, `vr\`, `today.json`, `ref.json`, `m50.json`, `m51.json`, `mut.json`, `mut.log`, `plug\ref_mmlm.py`, `plug\variants.py`, `plug\xfloc.py`, `plug\mut1.py`, `prop\test_prop_mmlm.py`.

Only this report was written in the repo. Nothing under `app/`, the spec, the cases file, the notes or the test file was edited. No commit. No model server.

## Fix list
1. **Case designer:** add 3 cards, findings 1 and 2. The scratch tests above are the recipes. Finding 3 is optional.
2. **Executor,** after 1: implement them and send back for a scoped re-verification.
3. **Owner, optional:** look at the three `[money]` readings under "Flagged, not decided".
