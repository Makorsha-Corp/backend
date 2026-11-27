# Verification — `app/services/project_component_task_service.py`

> **Verdict:** PASS (round 2, 2026-11-06; round 1: NEEDS WORK)
> Tests: 59 passed · 27 xfailed (reproduced ✅) · coverage 100% branch
> Mutation: 65 mutants · 64 killed · 1 survived → score 100% (after excluding 1 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
The tests are faithful to the cards. They reproduce the notes, are stable over three runs, and every xfail fails on its card's line. The one surviving mutant is equivalent. The service's own logic holds under hand variants: the event choice (completed / reopened / updated, note vs task), the default "open tasks only" kind, rollback once, and the access filter. One variant survived, as in the note service: a stray `db.commit()` on the one-component read. No card spies on a successful one-component read. That is a missing case; the tests need no change.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_tasks` R2, R7 / T-TC6; line 48–65 | No card checks that a **successful** one-component read neither commits nor rolls back. L-06 spies only on a path where the guard raises before any commit could happen. | Hand variant "stray commit component list" → 59 passed. | case designer: add a spied `get_tasks(..., project_component_id=C1.id)` success card with a pending P. |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 40 | 125 | `exclude_unset=True` → `False` | equivalent | `update_fields` is used only in `'is_completed' in update_fields and task.is_completed != was_completed`. The base `update` applies only sent, non-null fields, so `is_completed` can change only when it was sent; the second operand alone decides. The hand variant that drops the "sent" check also survives, for the same reason. | — |

## Hand variants
Private copy `wpsvcv\C\hv_task`, `-m "not xfail"`.
| Variant | Result | Killed by |
|---|---|---|
| guard 404→403 / 403→404 / 404→400 / 403→400 | killed ×4 | L-07, C-06, C-07 / L-06, G-07, C-05, U-19, D-04 |
| no rollback / double rollback in create, update, delete | killed ×6 | C-05, C-14 / U-19, U-23 / D-04, D-05 |
| no access filter (workspace list) | killed | L-10, L-11, L-12, L-13 |
| open-only passes `is_note=None` through (notes come back) | killed | L-03 |
| open-only ignored | killed | L-03, L-04 |
| stray commit in `get_by_id` | killed | U-01, D-01 |
| stray rollback in workspace list | killed | L-09 … L-13, L-27, L-28 |
| **stray commit in component list** | **survived** | — (Finding 1) |
| rollback on update not-found / commit on delete not-found | killed ×2 | U-18 / D-03 |
| `was_completed` read after the update | killed | U-03, U-04, U-05, U-24 |
| "completion sent" check dropped | survived (equivalent, as mutant #40) | — |
| "completion changed" check dropped | killed | U-06 |
| no audit on create / update / delete | killed ×3 | C-02, C-15 / U-02 … / D-01 |
| notes logged on create too | killed | C-04 |
| guard after the insert (create) | killed | C-06 |
Filtering after paging (BUG-2298), filters ignored without a component (BUG-2300), `0` as "no component" (BUG-2301) and an audit row on no change (BUG-2303) are today's behaviour. Strict xfails cover them: L-17 and L-19, L-15 and L-16, L-05, U-12 and U-13.

## Traceability
cases 86 · tests 86 · unmatched: none · marker mismatches: none (27 xfail: 24 strict + 3 non-strict L-18, L-20, L-21 as the cards say; reasons name BUG-1278, BUG-2297 … BUG-2305, all in `bugs.md`). All `# [claude]`; no `local-run.json`.
`--runxfail`: all 27 fail on the card's line. Then 1: L-05, L-08, L-14 … L-18, L-20, L-21, G-09, C-08 … C-10, U-10, U-11, U-22, U-25, D-06. Then 2: L-19, L-22, C-11, U-08, U-12, U-13, U-15, U-21, U-27.

## Commands run
```
COVERAGE_FILE=wpsvcv/.cov.project_component_task_service.1 .venv/Scripts/python.exe -m pytest tests/unit/services/test_project_component_task_service.py -q -p no:cacheprovider -o addopts= --cov=app.services.project_component_task_service --cov-branch --cov-report=term-missing
  → app\services\project_component_task_service.py 81 0 24 0 100% · 59 passed, 27 xfailed
... --runxfail -rf            → 27 failed, 59 passed
plain runs 2 and 3            → 59 passed, 27 xfailed each (no flaky test)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/project_component_task_service.py tests/unit/services/test_project_component_task_service.py --json wpsvcv/mut_project_component_task_service.json
  → Mutants: 65 · killed 64 · timeout 0 · survived 1 · score 98%  (SURVIVED #40 L125:61 const True -> False)
.venv/Scripts/python.exe -I wpsvcv/C/hv/handvar.py task.json wpsvcv/C/hv_task res_task.json → 26 variants, 24 killed, 2 survived (1 equivalent)
```

## For the future notes
- Permissions: any member who may open the project may add, edit, complete, reopen and delete any task.
- Notifications: completing and reopening a task are logged as project events (`task_completed` / `task_reopened`). They are natural notification triggers, but nothing notifies today.

## Round 2 — 2026-11-06
**Current verdict:** PASS — the round-1 findings are closed by cases revision 3. Every round-1 survivor now fails a card. No fidelity findings, and the runs reproduce the notes.

**What changed:** cases revision 3, executor notes revision 3. New cards and tests: PCTS-L-29 (spied one-component read); PCTS-G-10 (spied one-row read). No existing card or test changed. No card was retired, and no new xfail was added.

**Traceability:** cards 88 · tests 88 · unmatched: none · marker mismatches: none (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvcv\C\trace.py`).

**Fidelity:** I read every new test against its card. Every Given is built as written: the commit point and the pending P after it. Every Then line is asserted with the card's exact value and in the card's order. The spies are around the call only, and the `session:` checks come before any re-read. Snapshots are taken at the commit point. No mocks beyond the Conventions. No findings.

**Runs** (private `COVERAGE_FILE` under `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvcv\C\r2\`):
```
plain ×3: 61 passed, 27 xfailed (each run)
--cov=app.services.project_component_task_service --cov-branch: 81 stmts, 24 branches, 100%; 61 passed, 27 xfailed
--runxfail -rf: 27 failed, 61 passed
```
The same 27 tests fail as in round 1. Each one fails on its card's "Fails today on" Then line: 0 mismatches, mapped with `thenline.py` on a `--tb=native` run against the current file.

**Mutation:** 64 / 65 killed in round 1; the one survivor (#40, line 125) is equivalent, so `mutate.py` was not re-run.

**Hand variants** (round-1 survivors and their neighbours, on a fresh copy of the backend at `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvcv\C\r2\hv_task`, `-m "not xfail"`; results in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvcv\C\hv\res_r2_task.json`):

| Variant | Result | Killed by |
|---|---|---|
| stray `db.commit()` on the one-component read (round-1 survivor) | KILLED | L-29 |
| stray `db.rollback()` on the one-component read | KILLED | L-01 … L-04, L-29 |
| stray `db.commit()` on the one-row read | KILLED | G-10, U-01, D-01 |
| stray `db.rollback()` on the one-row read | KILLED | G-10, U-23, D-05 |

**Routed:** nothing.
