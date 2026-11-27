# Verification — `app/services/order_workflow_service.py`

> **Verdict:** PASS (round 2, 2026-11-09; round 1 was NEEDS WORK)
> Tests: 48 passed · 37 xfailed (reproduced ✅) · coverage 100% branch (45 statements, 4 branches)
> Mutation: 19 mutants · 19 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Hand variants: 23 · 21 caught · 2 not caught (both to fix)
> Source commit: e48a092 · Cases revision: 2

## Summary
The tests are faithful to their cards: all 85 cards are implemented once, in card order, with every Then line asserted at the exact value. The only patches are the Conventions' commit / rollback / refresh wraps and the two `Author: claude` DAO patches. Every strict xfail fails inside the card's "Fails today on" line. All 19 tool mutants are killed. Workspace scoping on every callable is pinned, and so are commit and rollback on every write. All six BUG-2348 fix variants were checked (purchase check after the duplicate check, after the status check, only when the row is missing, case-insensitive, trimmed): each one fails a card.

The weak spot is `get_workflows`. The spec states id order as today's behavior (R1, ✅ Q1, "after BUG-100"), but BUG-100 is open and `get_by_workspace` has no `ORDER BY`. GL-01…03 pass only because fresh rows come back in heap order, which here is insertion order, which here is id order. A probe shows that after an ordinary UPDATE of an earlier row the list comes back as `[B, A]`, and paging with `limit=1` skips that row entirely. GL-03 also failed once in about 56 full-file runs. The other gap: `loaded(result)` in C-01 / U-01 comes after an attribute read, so it cannot see a missing re-read.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | spec-gap (wrong fact) | `get_workflows` R1, Q1, Branch map line 11–13 | R1 is marked ✅ "in `id` ascending order (base DAO `get_by_workspace`, BUG-100)", as if BUG-100 were fixed. BUG-100 is **open**: `app/dao/base.py` `get_by_workspace` has no `ORDER BY`. Id order is BUG-100's *intended* behavior, not today's. The Q1 verification ("list order on three rows was id order") hit the same luck. R1's order half should be tagged `[BUG-100]`, with today's behavior stated: heap order, so a row updated after later rows were inserted moves to the end, and `skip`/`limit` can skip or repeat it. The rest of R1 (workspace filter, skip/limit passed) stays ✅. | Probe `…\tplv\owsvc\probe\test_probe_order.py` (mine), today's code: A, B inserted, A updated → `get_workflows` returns `[B.id, A.id]`. A, B, C inserted, A updated → page 1 (`limit=1`) `[B]`, page 2 `[C]`; A on neither page. | describer (fill-gaps) |
| 2 | case-missing | OWFS-GL-01, GL-02, GL-03 | After finding 1, the order checks in these cards pass by luck: the Given inserts rows in id order and never updates them, so heap order = id order and the setup cannot tell id order from no order. No card checks order with a discriminating setup. Needed: a card that updates an earlier row (e.g. `A.description = "x"`, flush) before the read and expects `[A.id, B.id]` (and a paging variant), **strict xfail BUG-100**. The insert-only checks in GL-01…03 can stay as pass cards for the workspace filter and skip/limit. Also give rows names that run against id order: today every Given name is `"Flow"`, or `"Flow"` < `"Sales"` in id order, so ordering by name instead of by id (HR-6's usual order) is not caught either. | Probe as finding 1. Hand variant `list_by_name` (`ORDER BY name`): 48 passed. | case designer |
| 3 | flaky | OWFS-GL-03 | GL-03 failed once in about 56 full-file runs (during hand-variant run `upd_no_rollback`, whose plugin does not touch `get_workflows`). It did not come back in 45 further runs, so the failure message was not captured. Likely cause is the one in finding 1: 101 rows with no `ORDER BY`, while other test runs churn the same table (free-space reuse can place a later insert on an earlier page). Executor's maintainer note already predicts this. Resolves with findings 1–2. Re-run the file after the cards change. | 3 baseline + 25 stress + 8 targeted + 20 variant runs clean. One `upd_no_rollback` run listed `test_owfs_gl_03__default_limit_100_no_commit` as FAILED beside U-28 / U-29. | case designer (via 2), then executor |
| 4 | case-missing | OWFS-C-01 Then 3, OWFS-U-01 Then 2 (`loaded(result)`) | Then 1/2 read `result.id` / `result.workspace_id` first. On the expired object that read reloads every column, so `loaded(result)` is always true by the time it runs. The TC2 re-read is therefore unchecked on update, and on create it is caught only by C-16 (failing refresh). The test follows the card order, so the card has to change: put `loaded(result)` as Then 1, before any attribute read. | Hand variant `upd_no_refresh` (no `db.refresh` in update): 48 passed. `cr_no_refresh`: only C-16 fails, C-01 passes. | case designer |
| 5 | case-missing | `update_workflow` R8 × R6 (refusal order on `purchase`) | R8 refuses a sent `status_sequence` on `purchase` "any value", which implies the 400 STEPS comes before R6's 404 for a foreign or unknown status id. No card sends a foreign id to the purchase row (U-21…24 use own ids or `[]`), so a fix that checks statuses first goes unnoticed. Needed: purchase workflow + `status_sequence=[T2.id]` → 400 STEPS, strict xfail BUG-1223 (as Q24-04 does for create). | Read; the Q24-04 analogue for create was checked (`p_after_status` caught). | case designer |

## Surviving mutants
None (19/19 killed).

## Hand variants
Plugin `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tplv\owsvc\hv_owsvc.py` (mine; replaces `OrderWorkflowService` methods in `pytest_configure`, chosen by `VARIANT`). Runs used `-m "not xfail"`, except the BUG-2348 fix variants, which used `--runxfail -k "q24 or c_1"`. In those, C-10…13 fail on every variant except the two that also check statuses: they are BUG-1215 cards, so that is expected.

| Variant | Result |
|---|---|
| `get_workflows` without workspace filter (`get_multi`) | caught: GL-01 |
| `get_workflows` id descending | caught: GL-01, GL-02 |
| `get_workflows` `ORDER BY name` | **not caught** (finding 2) |
| `get_by_id` without workspace (`db.get`) | caught: GI-02, GI-03 |
| `get_by_type` case-insensitive (`ilike`) | caught: GT-02 |
| update / delete lookup without workspace | caught: U-07, U-08 / D-02, D-03 |
| update / delete / create without rollback | caught: U-28, U-29 / D-14, D-20 / Q24-07 |
| update / delete without commit | caught: 8 / 6 tests |
| update without refresh | **not caught** (finding 4) |
| create without refresh | caught: C-16 only |
| create stores another workspace id | caught: 6 tests |
| delete rolls back on not-found | caught: D-05 |
| BUG-2348 fix, correct (check first) | Q24-01…07 pass |
| BUG-2348 fix, check after the duplicate (after flush) | caught: Q24-03 |
| BUG-2348 fix, only when W1 has no purchase row | caught: Q24-03 |
| BUG-2348 fix, after the BUG-1215 status check | caught: Q24-04 |
| BUG-2348 fix, `type.lower() == "purchase"` | caught: Q24-05 |
| BUG-2348 fix, `type.strip() == "purchase"` | caught: Q24-06 |
| BUG-2348 + BUG-1215 fix, both in spec order | Q24 and C-10…13 all pass |

## Traceability
Cases 85 · tests 85 · every case ID in exactly one test (`# [claude] <ID>` and docstring) · no test without a case ID · unmatched: none · marker mismatches: none. All 37 xfails are `strict=True`, and their `reason` constants (`BUG_1215`, `BUG_1222`, `BUG_1223`, `BUG_2348`, `BUG_2385`, `BUG_2386`) name the card's BUG ID; every ID is in `docs/testing/bugs.md`. No `local-run.json`; no local-written tests. Script: `…\tplv\owsvc\trace.py` (mine).

Fidelity: no missing, weakened or changed assertions. Givens are built as written (standing rows in order, direct inserts, one flush each). Every write case re-reads after `db.rollback()` or through a Core `select`. No swallowed failures. The only patches are the Conventions' and the two `Author: claude` DAO patches (G1). The skill has no "step 1b"; GL-01…03 were judged against R1's wording and the source (findings 1–3).

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/services/test_order_workflow_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.order_workflow_service --cov-branch --cov-report=term-missing
  → app\services\order_workflow_service.py 45 0 4 0 100% · 48 passed, 37 xfailed
.venv/Scripts/python.exe -m pytest tests/unit/services/test_order_workflow_service.py -q -p no:cacheprovider -o addopts="" --runxfail -rf
  → 37 failed, 48 passed (the 37 strict xfails; each fails on the card's Then line)
.venv/Scripts/python.exe -m pytest tests/unit/services/test_order_workflow_service.py -q -p no:cacheprovider -o addopts=""   (×2, then ×25 with -m "not xfail")
  → 48 passed, 37 xfailed each; stress 0/25 failing
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/order_workflow_service.py tests/unit/services/test_order_workflow_service.py --json …\tplv\owsvc\mut.json
  → Mutants: 19 · killed 19 · timeout 0 · survived 0 · score 100%
VARIANT=<v> PYTHONPATH=…\tplv\owsvc .venv/Scripts/python.exe -m pytest <test file> -q -p no:cacheprovider -o addopts="" -p hv_owsvc -m "not xfail"   (23 variants, table above)
.venv/Scripts/python.exe -m pytest …\tplv\owsvc\probe\test_probe_order.py -q -p no:cacheprovider -o addopts="" --rootdir=. -p tests.unit.conftest -s
  → got [35621, 35620] for ids 35620, 35621; paging p1 [35623] p2 [35624] for ids 35622–35624 (2 failed: order not id order today)
```
All runs used a private `COVERAGE_FILE` under `…\tplv\owsvc\`.

## Round 2 — 2026-11-09

> **Current verdict:** PASS — cases revision 3, tests 49 passed · 41 xfailed (39 strict, 2 non-strict) · coverage 100% branch. All five round-1 findings closed.

**Re-read against the cards (revision 3).** Traceability: 90 cards · 90 tests, IDs match one to one; 39 `strict=True` + 2 `strict=False` (GL-04, GL-05) = 41 xfail, as the Counts line says. Changed and new tests read line by line against their cards: GL-01 (set + size), GL-02 (4 rows, `skip=1, limit=2`, 2 distinct of the four), GL-07 (`skip=2` of 3 → 1), GL-03 (100 distinct of 101, spies, X), GL-04, GL-05, GL-06 (statement recorder), C-01 and U-01 (`loaded(result)` now Then 1, before any attribute read; `rid` kept after it), U-30. Every Then line asserted at the card's value; no new mocks. GL-04 / GL-05 non-strict is allowed: their Expect lines say `xfail BUG-100 (non-strict)` and spec R1a says "Non-strict xfail (physical order)". No fidelity findings.

**Executor's claims reproduced.** Three plain runs: 49 passed · 41 xfailed each (no XPASS in my three; the notes' 20-run tally shows GL-04 / GL-05 XPASS now and then, which the non-strict cards allow). `--runxfail`: 41 failed, 49 passed; the new ones fail where their cards say — GL-04 Then 2 (`[B, A] == [A, B]`, line 374), GL-05 Then 2 (`[B, C, A]`, line 394), GL-06 Then 2 (`'ORDER BY' in 'SELECT … LIMIT … OFFSET …'`, line 411), U-30 Then 1 (`DID NOT RAISE HTTPException`, line 1561).

**Round-1 items, each checked with a variant** (my plugin `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tplv\owsvc2\hv2_owsvc.py`; list variants run with `--runxfail -k gl_`):

| Round-1 item | Variant | Result |
|---|---|---|
| 1–3 GL order (reference fix) | `ORDER BY id` | GL-01…07 all pass; plain run of the file 49 passed — the cards accept the fix |
| 2 GL order | `ORDER BY name` | caught: GL-04, GL-05, GL-06 fail |
| 2 GL order | `ORDER BY name, id` | caught: GL-04, GL-05, GL-06 fail |
| 2 GL order | `ORDER BY id DESC` | caught by GL-04, GL-05 (GL-06 passes: `.id` is in the order part) |
| 2 GL order | no `ORDER BY` (today) | caught by the strict alarm GL-06 (GL-04 / GL-05 passed by physical order in this run, as designed) |
| 4 `loaded` check | update without `db.refresh` | caught: U-01 (was 48 passed in round 1) |
| 4 `loaded` check | create without `db.refresh` | caught: C-01 and C-16 (round 1: C-16 only) |
| 5 BUG-1223 refusal order | purchase check first, then status check (reference) | U-21…U-30 pass (`--runxfail -k "u_2 or u_30"`; U-20 fails as it is a BUG-2385/2386 schema card the variant does not fix) |
| 5 BUG-1223 refusal order | status check (404) before the purchase check | caught: U-30 fails |

Note (no finding): an `ORDER BY id DESC` fix would show as "xfailed" for GL-04 / GL-05 while their markers are non-strict, but GL-06 would XPASS (strict → red) at the same time, and the notes say to remove all three markers then, after which GL-04 / GL-05 fail it. That is the designed sequence.

**Flakiness.** 3 runs plus the `--runxfail` run and 10 variant runs: GL-01, GL-02, GL-03, GL-07 always passed. The round-1 GL-03 flake had its cause removed (no row named from an unordered query any more).

**Mutation.** Not re-run (round 1: 19/19 killed; the source is unchanged at e48a092 and no passing card was weakened).

**Remaining (wording only, no effect on the verdict).** Executor: the test file's module docstring still says "cases.md (revision 2)" (line 3); revision 3 is what it implements.

### Round 2 commands
```
COVERAGE_FILE=…\tplv\owsvc2\.cov .venv/Scripts/python.exe -m pytest tests/unit/services/test_order_workflow_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.order_workflow_service --cov-branch --cov-report=term-missing
  → 100% (45 statements, 4 branches) · 49 passed, 41 xfailed
(same, without --cov) ×2 → 49 passed, 41 xfailed · 49 passed, 41 xfailed
… --runxfail -rf → 41 failed, 49 passed
… --runxfail -k "gl_04 or gl_05 or gl_06 or u_30" --tb=line → lines 374, 394, 411, 1561 as above
VARIANT=<v> PYTHONPATH=…\tplv\owsvc2 … -p hv2_owsvc (--runxfail -k gl_ | --runxfail -k "u_2 or u_30" | -m "not xfail") → table above
```
