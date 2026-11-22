# Verification — `app/services/project_component_note_service.py`

> **Verdict:** PASS (round 2, 2026-11-06; round 1: NEEDS WORK)
> Tests: 41 passed · 20 xfailed (reproduced ✅) · coverage 100% branch
> Mutation: 48 mutants · 48 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
The tests are faithful to the cards: every case has exactly one test, every Then line is asserted with the exact value, and every xfail fails on the line its card names. All 48 mutants are killed. What the service adds over its manager (the `try`/rollback around each writer, the events, `is_note = True`, the workspace-wide query and the access filter) holds up under hand-made variants, with two exceptions. These variants survived:
(1) a stray `db.commit()` on the **component** path of `get_notes`, because no success-path read card spies on commit/rollback; and (2) dropping the `workspace_id` filter from the workspace-wide query, because the access filter hides other workspaces' rows and no card pages across them.
Both are missing cases. The tests themselves need no change.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_notes` R1, R7 / N-TC6; line 60–68 | No card checks that a **successful** one-component read neither commits nor rolls back. L-02 and L-03 spy only on paths where the guard raises before any commit could happen. | Hand variant "stray commit component list" (`db.commit()` after the guard) → 41 passed. | case designer: add a spied `get_notes(..., project_component_id=C1.id)` success card with a pending P (`cm == 0`, `rb == 0`, `P in db.new`). |
| 2 | case-missing | `get_notes` R2 ("`workspace_id` match"); line 51 | The workspace filter of the workspace-wide query has no card that can see it. The component check in `_filter_accessible_notes` drops other workspaces' notes after paging, so removing the filter changes only how full the page is. Every card uses `limit=1000` or puts W1 notes only. | Hand variant "no workspace filter in ws query" → 41 passed. | case designer: add a card where W0/W2 notes are created first, then `limit=1` (or `limit=k`) → intended (and today's) page is the W1 note(s). |

## Surviving mutants
None.

## Hand variants
Run on a private copy of the backend (`wpsvcv\C\hv_note`, `-m "not xfail"`, script `wpsvcv\C\hv\handvar.py`, specs `mkspecs.py`).
| Variant | Result | Killed by |
|---|---|---|
| guard 404→403 / 403→404 / 404→400 / 403→400 | killed ×4 | L-02, L-04, C-04, C-05 / L-03, G-07, C-03, U-06, D-04 |
| no rollback in create / update / delete | killed ×3 | C-03, C-12 / U-06, U-11 / D-04, D-05 |
| double rollback in create / update / delete | killed ×3 | same cards (`rb.call_count == 1`) |
| no access filter (workspace list) | killed | L-07, L-08, L-09, L-10 |
| **no workspace filter in workspace query** | **survived** | — (Finding 2) |
| no `is_note` filter in workspace query | killed | L-06 |
| `0` treated as "no component" | killed | L-02 |
| stray commit in `get_by_id_and_workspace` | killed | U-01, D-01 |
| stray rollback in workspace list | killed | L-06 … L-10, L-21 |
| **stray commit in component list** | **survived** | — (Finding 1) |
| rollback on update not-found / commit on delete not-found | killed ×2 | U-04 / D-02 |
| no audit on create / update / delete | killed ×3 | C-02, C-13 / U-02 / D-01 |
| commit before the audit (create) | killed | C-01 |
| guard after the insert (create) | killed | C-04 |
| no refresh after the update | killed | U-12 |
Filtering after paging (BUG-2293) is today's behaviour, and the strict xfails L-12 and L-14 cover it (the executor's reference plugin turns them green). An audit row written when nothing changed is today's behaviour too, covered by U-07 and U-08 (BUG-2295).

## Traceability
cases 61 · tests 61 · unmatched: none · marker mismatches: none (20 xfail: 17 strict + 3 non-strict L-13, L-15, L-16, as their Expect lines say; every reason names its BUG ID; BUG-1278, BUG-2290 … BUG-2295 exist in `bugs.md`). All tests are `# [claude]`; no `local-run.json`.
`--runxfail`: all 20 fail on the card's "Fails today on" line (own mapper `wpsvcv\C\thenline.py`): L-05, G-09, C-06, C-07, C-08, U-10 on Then 1 (DID NOT RAISE); L-11, L-12, L-13, L-15, L-16, G-06, U-05, D-03 on Then 1; L-14, L-17, C-09, U-07, U-08, U-09 on Then 2.

## Commands run
```
COVERAGE_FILE=wpsvcv/.cov.project_component_note_service.1 .venv/Scripts/python.exe -m pytest tests/unit/services/test_project_component_note_service.py -q -p no:cacheprovider -o addopts= --cov=app.services.project_component_note_service --cov-branch --cov-report=term-missing
  → app\services\project_component_note_service.py 71 0 14 0 100% · 41 passed, 20 xfailed
... --runxfail -rf            → 20 failed, 41 passed
... --runxfail --tb=native    → mapped with thenline.py (above)
plain runs 2 and 3            → 41 passed, 20 xfailed each (no flaky test)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/project_component_note_service.py tests/unit/services/test_project_component_note_service.py --json wpsvcv/mut_project_component_note_service.json
  → Mutants: 48 · killed 48 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe -I wpsvcv/C/hv/handvar.py note.json wpsvcv/C/hv_note res_note.json → 25 variants, 23 killed, 2 survived
```

## For the future notes
- Permissions: any member who may open the project can add, edit or delete any note, whoever wrote it. There is no author column (spec "Permission checks").

## Round 2 — 2026-11-06
**Current verdict:** PASS — the round-1 findings are closed by cases revision 3. Every round-1 survivor now fails a card. No fidelity findings, and the runs reproduce the notes.

**What changed:** cases revision 3, executor notes revision 3. New cards and tests: PCNS-L-22 (spied one-component read); PCNS-L-23 (W0 and W2 notes ahead of a `limit=2` page); PCNS-G-10 (spied one-row read). No existing card or test changed. No card was retired, and no new xfail was added.

**Traceability:** cards 64 · tests 64 · unmatched: none · marker mismatches: none (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvcv\C\trace.py`).

**Fidelity:** I read every new test against its card. Every Given is built as written: the commit point, the pending P after it, and for L-23 the W0 and W2 notes ahead of the page. Every Then line is asserted with the card's exact value and in the card's order. The spies are around the call only, and the `session:` checks come before any re-read. Snapshots are taken at the commit point. No mocks beyond the Conventions. No findings.

**Runs** (private `COVERAGE_FILE` under `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvcv\C\r2\`):
```
plain ×3: 44 passed, 20 xfailed (each run)
--cov=app.services.project_component_note_service --cov-branch: 71 stmts, 14 branches, 100%; 44 passed, 20 xfailed
--runxfail -rf: 20 failed, 44 passed
```
The same 20 tests fail as in round 1. Each one fails on its card's "Fails today on" Then line: 0 mismatches, mapped with `thenline.py` on a `--tb=native` run against the current file.

**Mutation:** 48 / 48 killed in round 1; no survivor, so `mutate.py` was not re-run.

**Hand variants** (round-1 survivors and their neighbours, on a fresh copy of the backend at `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvcv\C\r2\hv_note`, `-m "not xfail"`; results in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvcv\C\hv\res_r2_note.json`):

| Variant | Result | Killed by |
|---|---|---|
| no workspace filter in the workspace-wide query (round-1 survivor) | KILLED | L-23 |
| stray `db.commit()` on the one-component read (round-1 survivor) | KILLED | L-22 |
| stray `db.rollback()` on the one-component read | KILLED | L-01, L-22 |
| stray `db.commit()` on the one-row read | KILLED | G-10, U-01, D-01 |
| stray `db.rollback()` on the one-row read | KILLED | G-10, U-11, D-05 |

**Routed:** nothing.
