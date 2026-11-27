# Verification — `app/services/project_component_item_service.py`

> **Verdict:** PASS (round 2, 2026-11-06; round 1: NEEDS WORK)
> Tests: 45 passed · 19 xfailed (reproduced ✅) · coverage 100% branch
> Mutation: 40 mutants · 40 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
The tests are faithful to the cards, stable over three runs, and kill every mutant. Every xfail fails on its card's line. The BUG-1012 cards (items from another workspace) were tested against eight shapes of a future fix. They accept a correct fix: item checked after the guard, 404 `Item with ID … not found`. They reject every wrong one: no workspace check, no `is_active` check, unknown id not checked, check before the guard, 400 or 403, check after the insert, check outside the `try`. Two hand variants survived; both point to missing cases.
- A stray commit on the one-component read is not seen, as in the note and task services.
- If `update_component_item` looks the row up without the workspace, a W2 line read through W1 gives a 404 from the guard instead of `None`. No card updates or deletes another workspace's line, though the note and task suites have one (U-13 / U-20).

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_items` R1, R5 / I-TC6; line 45–53 | No card checks that a **successful** one-component read neither commits nor rolls back. L-03 spies only on a path where the guard raises before any commit could happen. | Hand variant "stray commit component list" → 45 passed. | case designer: add a spied `get_items(..., project_component_id=C1.id)` success card with a pending P. |
| 2 | case-missing | `update_component_item` R1, `delete_component_item` R1 ("another workspace's → `None` / `False`") | No card updates or deletes a W0/W2 line through W1. `get_by_id` is covered by G-04 and G-05, but the writers are not, so a writer that looks the row up without the workspace goes unseen. | Hand variant "update lookup ignores workspace" (`dao.get` + guard) → 45 passed. The delete variant was killed only by chance, because it also skipped the guard (D-03). | case designer: add U-/D- cards "a W2 line is not found in W1": `None` / `False`, the line unchanged, nothing written (as note U-13, task U-20). |

## Surviving mutants
None.

## Hand variants
Private copy `wpsvcv\C\hv_item`. The base variants ran with `-m "not xfail"`. The FIX-1012 variants ran with `--runxfail` on the create cards C-01 … C-21, leaving out C-08 (BUG-1278) and C-14 … C-16 (schema, BUG-2307).
| Variant | Result | Killed by |
|---|---|---|
| guard 404→403 / 403→404 / 404→400 / 403→400 | killed ×4 | L-04, C-06, C-07 / L-03, G-06, C-04, C-05, U-07, D-03 |
| no rollback / double rollback in create, update, delete | killed ×6 | C-04, C-12 / U-07, U-11 / D-03, D-04 |
| no access filter (workspace list) | killed | L-07 … L-10 |
| stray commit in `get_by_id` | killed | U-01, D-01 |
| stray rollback in workspace list | killed | L-06 … L-10, L-19 |
| **stray commit in component list** | **survived** | — (Finding 1) |
| rollback on update not-found / commit on delete not-found | killed ×2 | U-06 / D-02 |
| no audit on create / update / delete | killed ×3 | C-02, C-20 / U-02 / D-01 |
| event metadata carries the row id, not the catalog item id | killed | C-02 |
| **update looks the row up without the workspace** | **survived** | — (Finding 2) |
| delete looks the row up without the workspace (no guard) | killed | D-03 |
| FIX-1012 reference (check after guard: same workspace, active, exists → else 404) | all 17 pass | — (cards accept a correct fix) |
| FIX-1012 without workspace check | rejected | C-09, C-10 |
| FIX-1012 without `is_active` check | rejected | C-13 |
| FIX-1012 unknown id not checked | rejected | C-11 |
| FIX-1012 item check before the guard | rejected | C-05 |
| FIX-1012 answers 400 / 403 | rejected ×2 | C-09, C-10, C-11, C-13 |
| FIX-1012 check after the insert | rejected | C-11 |
| FIX-1012 check outside the `try` (no rollback) | rejected | C-05, C-12 |
Filtering after paging (BUG-2308) and an audit row on no change (BUG-2310) are today's behaviour, covered by the strict xfails L-12, L-14, U-04 and U-05.

## Traceability
cases 64 · tests 64 · unmatched: none · marker mismatches: none (19 xfail: 18 strict + non-strict L-13; reasons name BUG-1012, BUG-1278, BUG-2306 … BUG-2310, all in `bugs.md`). C-12's `pytest.raises(Exception)` is what its card prescribes (any exception, today `IntegrityError`); not a finding. All `# [claude]`; no `local-run.json`.
`--runxfail`: all 19 fail on the card's line. Then 1: L-02, L-05, L-11 … L-13, G-08, C-08 … C-10, C-13 … C-16, U-08, U-09. C-11 fails on Then 1 with `IntegrityError` (FK), as its card says. Then 2: L-14, U-04, U-05.

## Commands run
```
COVERAGE_FILE=wpsvcv/.cov.project_component_item_service.1 .venv/Scripts/python.exe -m pytest tests/unit/services/test_project_component_item_service.py -q -p no:cacheprovider -o addopts= --cov=app.services.project_component_item_service --cov-branch --cov-report=term-missing
  → app\services\project_component_item_service.py 69 0 14 0 100% · 45 passed, 19 xfailed
... --runxfail -rf            → 19 failed, 45 passed
plain runs 2 and 3            → 45 passed, 19 xfailed each (no flaky test)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/project_component_item_service.py tests/unit/services/test_project_component_item_service.py --json wpsvcv/mut_project_component_item_service.json
  → Mutants: 40 · killed 40 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe -I wpsvcv/C/hv/handvar.py item.json  wpsvcv/C/hv_item res_item.json  → 29 variants (1 reference), 27 killed/rejected, 1 survived
.venv/Scripts/python.exe -I wpsvcv/C/hv/handvar.py item2.json wpsvcv/C/hv_item res_item2.json → 2 variants, 1 killed, 1 survived
```

## For the future notes
- Permissions: any member who may open the project may plan, change and remove item lines.
- Payments / stock: today `qty` is a plan figure only. No stock, ledger or money row is written, and C-01, U-01 and D-01 assert that. If a later feature turns these rows into stock reservations or cost, revisit spec D1/D2 (BUG-2307's range; one item planned twice is allowed).

## Round 2 — 2026-11-06
**Current verdict:** PASS — the round-1 findings are closed by cases revision 3. Every round-1 survivor now fails a card. No fidelity findings, and the runs reproduce the notes.

**What changed:** cases revision 3, executor notes revision 3. New cards and tests: PCIS-L-20 (spied one-component read); PCIS-G-09 (spied one-row read); PCIS-U-13 (W0 line updated through W1 → `None`); PCIS-D-05 (W2 line deleted through W1 → `False`). No existing card or test changed. No card was retired, and no new xfail was added.

**Traceability:** cards 68 · tests 68 · unmatched: none · marker mismatches: none (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvcv\C\trace.py`).

**Fidelity:** I read every new test against its card. Every Given is built as written: the commit point, the pending P after it, and the other-workspace row with qty 4 where the card says so. Every Then line is asserted with the card's exact value and in the card's order. The spies are around the call only, and the `session:` checks come before any re-read. Snapshots are taken at the commit point. No mocks beyond the Conventions. No findings.

**Runs** (private `COVERAGE_FILE` under `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvcv\C\r2\`):
```
plain ×3: 49 passed, 19 xfailed (each run)
--cov=app.services.project_component_item_service --cov-branch: 69 stmts, 14 branches, 100%; 49 passed, 19 xfailed
--runxfail -rf: 19 failed, 49 passed
```
The same 19 tests fail as in round 1. Each one fails on its card's "Fails today on" Then line: 0 mismatches, mapped with `thenline.py` on a `--tb=native` run against the current file.

**Mutation:** 40 / 40 killed in round 1; no survivor, so `mutate.py` was not re-run.

**Hand variants** (round-1 survivors and their neighbours, on a fresh copy of the backend at `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvcv\C\r2\hv_item`, `-m "not xfail"`; results in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvcv\C\hv\res_r2_item.json`):

| Variant | Result | Killed by |
|---|---|---|
| update looks the line up without the workspace, then guards its component (round-1 survivor) | KILLED | U-13 |
| delete looks the line up without the workspace, then guards its component | KILLED | D-05 |
| update looks the line up without the workspace, no guard | KILLED | U-07, U-13 |
| delete looks the line up without the workspace, no guard | KILLED | D-03, D-05 |
| update answers another workspace's line with a 404 inside the service | KILLED | U-06, U-13 |
| stray `db.commit()` on the one-component read (round-1 survivor) | KILLED | L-20 |
| stray `db.rollback()` on the one-component read | KILLED | L-01, L-20 |
| stray `db.commit()` on the one-row read | KILLED | G-09, U-01, D-01 |
| stray `db.rollback()` on the one-row read | KILLED | G-09, U-11, D-04 |

### Coordinator's question: U-13 and D-05 assert `None` / `False`, not a 404
That is right at the service layer. Spec `update_component_item` R1 says: found as `get_by_id`; not found → `None`, nothing written, no commit or rollback. `delete_component_item` R1 says the same with `False`. `get_by_id` uses `get_by_id_and_workspace`, so another workspace's line is "not found". The service code returns `None` / `False` there (`app/services/project_component_item_service.py`, the `if not item:` returns in both writers). The 404 `Project component item not found` is the endpoint's mapping, which the cases file lists as Deferred (integration). The cards are also strong enough. Each wrong shape fails them: an unscoped lookup (with or without the component guard), and a fix that moves the 404 into the service.

**Routed:** nothing.
