# Verification — `app/services/project_component_service.py`

> **Verdict:** PASS (round 2, 2026-11-06, cases revision 4; round 1 was NEEDS WORK, case designer only)
> Tests: 79 passed · 47 xfailed (reproduced ✅, 3 plain runs identical; `--runxfail`: 47/47 fail on their card's Then line) · coverage 94% branch (101, 135 dead, spec D1)
> Mutation: 33 mutants · 31 killed · 2 survived → score 100% (after excluding 0 equivalent, 2 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 3

## Summary
These tests can be trusted. All 126 cards are implemented one-to-one, with every Then line asserted as written and the strict markers correct. Every mutant on live code is killed. 49 hand-written variants test the service's own behaviour: rollback, reads that must not commit, error mapping, the access filter, audit rows, paging and the BUG-1196 blocker list. Every one is killed except two equivalents, three reference fixes, and the two blocker variants in Finding 1. The two dead-line survivors are the unreachable `return False` the spec removes (D1).

One gap is left, in the BUG-1196 cards, and the case designer must fix it. The spec (G5) says `"attachment_added "` and `"attachment_add"` block, but the cases test only `"Attachment_added"`. A fix that trims the value, or matches on the prefix `attachment`, would pass every card. A smaller gap: no card checks CT6 on the success path of `get_components` with `project_id`. A stray commit there is caught only by chance, through L-40.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `delete_component` R3 (spec G5); D-26 | The exact-compare exclusion is checked only for case (`"Attachment_added"`). The spec also names `"attachment_added "` (trailing space) and `"attachment_add"` as blocking. No card covers them. | Hand variants with the BUG-1196 fix in place, run with `--runxfail` on the D cards: `func.trim(event_type).notin_(…)` → all blocker cards pass. `~event_type.like("attachment%")` → all pass. | **case designer**: add 2 strict xfail BUG-1196 cards, `act(CR, "attachment_added ")` and `act(CR, "attachment_add")` → `errors == [{"type": "activity_event", "id": A1.id}]` |
| 2 | case-missing | `get_components` R7 (CT6), `project_id` given, success path | L-41 checks CT6 only without `project_id`, and L-42 only on the refusal. A `db.commit()` or `db.rollback()` before `get_by_project` is caught only because L-40 runs inside `begin_nested()`. That card is about a different rule (a negative `skip`). | Variants `stray_commit_project_list` / `stray_rollback_project_list`: only `pcs_l_40` fails | **case designer**: add a pass card like L-41, but with `project_id=PA.id` (pending Q and edit E stay, `cm.call_count == 0`, `rb.call_count == 0`) |

No fidelity findings: no missing, weakened or changed assertion, wrong setup, swallowed failure, extra mock or dishonest xfail. L-38's `<=` comes from the card itself (order is not specified for that card).

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 18 | 135 | `return False` → `return None` | dead | `if not component: return False` repeats the guard's lookup (`require_component_access` runs the same `get_by_id_and_workspace` in the same session, and that has already returned 404). Spec D1 lists it for removal. | — |
| 24 | 135 | `False` → `True` | dead | same line | — |

### Executor's coverage-gap claim (lines 101, 135)
Confirmed **dead**. `require_component_access` (`project_manager.py` 135–142) runs `project_component_dao.get_by_id_and_workspace(id, workspace_id)` and raises 404 on `None`. The service then repeats the same query in the same transaction. It could only return `None` if another transaction committed a delete between the two statements (READ COMMITTED). The spec (D1, decided 2026-11-04) chose to remove the branches instead of specifying them, so no case is owed. Line 101 has no mutant (a bare `return None` is not mutated).

## Hand variants
All were run in a private copy (`wpsvcv\B\hv_base`, script `hv.py`) with `-m "not xfail"`. The `blk_*` variants add a reference BUG-1196 fix and run the D cards with `--runxfail`. D-06 is left out (BUG-2262), and D-11 always fails (BUG-1278 is not fixed in the variant).

| Variant | Result | Killed by |
|---|---|---|
| no rollback in create / update / delete | killed ×3 | C-04, C-07, C-21 / U-05, U-07, U-23 / D-07, D-09, D-25 |
| double rollback (delete); commit instead of rollback in `except` (create) | killed | D-07, D-25 / C-04, C-07, C-21 |
| stray commit / rollback, workspace-wide list | killed | L-41 |
| stray commit / rollback, project list (success path) | killed, but only by L-40 | Finding 2 |
| stray rollback on refusal (project list; get_by_id) | killed | L-42; G-11 |
| stray commit in get_by_id | killed | G-10 |
| 403→404 (update), 404→403 (create, delete), any→400 `ValidationError` (delete) | killed | U-08; C-04…C-07; D-07, D-08, D-09, D-12 (+D-10) |
| guard after the write (create; update) | killed | C-04, C-05; U-05…U-07 |
| list without access filter | killed | L-02, L-07…L-16 |
| list looks up the project in any workspace | killed | L-17, L-18 |
| list checks access in `project.workspace_id` | survived: **equivalent** (the project was loaded by `workspace_id`, so they are equal) | — |
| list ignores paging / project list ignores `project_id` / drops `skip` | killed | L-24 / L-29 / L-40 |
| filter-then-page fix (BUG-2277 shape) | passing cards still pass; L-20, L-21 XPASS | the xfail cards tell the fix from today's code |
| create: no event / two events / wrong performer | killed | C-02, C-22 / C-02 |
| update: no event / old name / wrong performer | killed | U-02, U-03 / U-02 |
| update: event only on change (BUG-2276 fix) | U-16, U-17 XPASS; U-02, U-03, U-15 pass | (U-24 failure is an artefact of the variant's own `refresh`) |
| delete: no event / event after remove / returns `None` | killed | D-02 / D-02 / D-01…D-05 |
| BUG-1196 reference fix | D-13…D-24, D-26 pass | — |
| blockers: case-insensitive compare | killed | D-26 |
| blockers: trimmed compare; prefix `attachment%` | **survived** | Finding 1 |
| blockers: attachment events block | killed | D-03, D-04, D-20 |
| blockers: one `other_workspace` per row / shows ids / ignored / placed first | killed | D-23 / D-22, D-23 / D-22, D-23 / D-23 |
| blockers: sorted by id only / ids descending | killed | D-21 |
| blockers: wrong detail; work orders not checked | killed | D-13; D-13, D-14, D-21 |
| blockers: check placed after the event write | survived: **equivalent** (the event is flushed and then rolled back by CT3; the outcome is the same, D-24 still sees one rollback and no commit) | — |

BUG-1012 (item lines from another workspace) does not reach this module.

## Traceability
cases 126 · tests 126 · unmatched: none · duplicate: none · marker mismatches: none. The helper `xfail(bug, strict=True)` defaults to strict, and L-27 alone is `strict=False`, as its card says. Every reason names its card's BUG ID. All IDs (1196, 1275, 1278, 2262, 2272–2279) exist in `bugs.md`. Every card's Then numbers match the test's `# Then N` markers. Every test has a `# [claude]` tag (no local-coder tests, no `local-run.json`).

## For the future notes
- Permissions: already recorded in `docs/future/permissions.md` (2026-11-04: anyone who may open the project may add, edit and hard-delete components). Nothing new.
- Notifications, payments: nothing. Component `budget` is money (BUG-2273/2274 already cover it).

## Commands run
```
COVERAGE_FILE=wpsvcv/.cov.pcs.1 .venv/Scripts/python.exe -m pytest tests/unit/services/test_project_component_service.py -q -p no:cacheprovider -o addopts= --cov=app.services.project_component_service --cov-branch --cov-report=term-missing
  app\services\project_component_service.py  60 2 10 2  94%  101, 135
  79 passed, 47 xfailed
COVERAGE_FILE=wpsvcv/.cov.pcs.2 VTHEN_OUT=… PYTHONPATH=wpsvcv/B .venv/Scripts/python.exe -m pytest … --runxfail -rf -p vthen
  47 failed, 79 passed   → fto.py: 47/47 on the card's "Fails today on" Then line, mismatches 0
(two more plain runs, COVERAGE_FILE .cov.pcs.3/.4)
  79 passed, 47 xfailed  ×2
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/project_component_service.py tests/unit/services/test_project_component_service.py --json wpsvcv/mut_project_component_service.json
  Mutants: 33 · killed 31 · timeout 0 · survived 2 · score 94%   (SURVIVED #18 L135 return None; #24 L135 False -> True)
.venv/Scripts/python.exe -I wpsvcv/B/hv.py   (49 hand variants, results in wpsvcv/B/hv_results.txt)
.venv/Scripts/python.exe wpsvcv/B/trace.py …  (traceability)  ·  wpsvcv/B/thenpair.py …  (Then-line pairing)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvcv\B\` (`trace.py`, `thenpair.py`, `pairs.txt`, `vthen.py`, `fto.py`, `hv.py`, `hv_results.txt`, `hv_base\`).

## Round 2 — 2026-11-06

**Current verdict:** PASS — both round-1 findings are closed by cases revision 4. The three new tests match their cards, the runs reproduce the notes with no flaky test, and both round-1 survivors now fail a card. No new survivor.

**What changed:** cases revision 4 added three cards and tests. PCS-L-43 is CT6 on the `project_id` path: spies, a pending Q and an edited CA kept, no commit, no rollback; it is expected to pass. PCS-D-27 (`"attachment_added "`, trailing space) and PCS-D-28 (`"attachment_add"`) are strict xfail BUG-1196. No other card or test changed and no ID was retired (checked against the notes' revision history).

**Traceability:** cases 129 · tests 129 · unmatched: none. The 49 xfail cards each use the module's `xfail(bug)` helper, which is `pytest.mark.xfail(strict=True, reason=bug)`. The one exception is L-27, which its card marks non-strict. Every BUG ID exists in `bugs.md`.

**Fidelity (new tests):**
- L-43: Given and When as on the card (`project_id=PA.id`, `limit=1000`). Then 1–5 are asserted exactly: `idset == {CA.id}`, `Q in db.new and len == 1`, `CA in db.dirty and len == 1`, `not db.deleted`, and both spy counts `== 0`.
- D-27, D-28: copies of the D-26 shape with the card's event type. Then 1 is `ValidationError`. Then 2 is the exact `errors` list. Then 3 is `not db.deleted and not db.dirty`. Then 4 re-reads A1's `event_type`. Then 5 is `unchanged(CR)`.
- Findings: none.

**Runs:**
```
plain ×3: 80 passed, 49 xfailed (15.07s, 14.88s, 16.10s)
--cov --cov-branch: app\services\project_component_service.py  60  2  10  2  94%  101, 135   (80 passed, 49 xfailed)
--runxfail -rf: 49 failed, 80 passed. The new cards D-26, D-27, D-28 each fail on Then 1, "DID NOT RAISE ValidationError", as their cards say.
```
Scratch: `wpsvcv\B\r2\` (private `COVERAGE_FILE` per run).

**Round-1 survivors re-run** (`wpsvcv\B\hv.py`, `hv_base` with the current tests):

| Variant | Round 1 | Round 2 | Killed by |
|---|---|---|---|
| BUG-1196 reference fix (baseline, `--runxfail -k "pcs_d_ and not pcs_d_06"`) | D-11 only (BUG-1278, not part of the fix) | D-11 only | — |
| fix that trims the event type before comparing | survived | **KILLED** | PCS-D-27 |
| fix that matches any `attachment%` prefix | survived | **KILLED** | PCS-D-27, PCS-D-28 |
| stray `db.commit()` on `get_components` with `project_id` | killed only by L-40, a negative-`skip` card, by chance | **KILLED** | PCS-L-43 (and L-40) |
| stray `db.rollback()` on the same path | killed only by L-40 | **KILLED** | PCS-L-43 (and L-40) |

`mutate.py` was not re-run: both round-1 survivors (#18, #24) are on dead line 135.

**Routed:** nothing.
