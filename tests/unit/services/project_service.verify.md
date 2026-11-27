# Verification — `app/services/project_service.py`

> **Verdict:** PASS (round 2, 2026-11-06; round 1 was NEEDS WORK, see below)
> Tests: 62 passed · 15 xfailed (reproduced ✅) · coverage 100% branch (74 statements, no branches of its own)
> Mutation: 17 mutants · 17 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Hand variants: 47 · 40 killed · 2 survived (`case-missing`) · 5 inert (no observable change, see below)
> Source commit: e48a092 · Cases revision: 3

## Summary
The tests are faithful. Traceability is clean, every xfail fails on its card's Then line, three plain runs agree, and every `mutate.py` mutant is killed. What the service adds over the manager is the transaction, and that is well guarded. The hand variants removing the rollback from any writer's `except`, committing (flush only) nowhere, skipping a re-read, putting a stray commit or rollback on any of the four reads, dropping an argument of `list_projects`, deleting or adding an audit event, or remapping an error (403→404, 404→400, `HTTPException`→`None`) are all caught. One gap: `list_projects` is never tested with a status or factory filter **together with paging**. So a service that filters by status or factory in Python after the manager has paged passes all 62 cards. The case designer should add a pass card for each.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `list_projects` R1 ("returns manager `list_projects` for exactly these arguments"; filtering before paging is the HR-5 house rule) | L-05 (factory) and L-06 (status) use `limit=1000` with nothing to page, and L-02 … L-04 page without a filter. No pass card combines a filter with `skip` / `limit`, so filtering after paging in the service is not caught. Today the DAO filters factory-only and status-only in the query, so such a card passes today. | Hand variants `list-status-filtered-after-paging` (service passes `status=None`, then filters the page in Python) and `list-factory-filtered-after-paging` (same for `factory_id`): 62 passed, 15 deselected. | **case designer**: add two pass cards, e.g. AP1, AP2 (`PLANNING`, lowest ids) then AC (`COMPLETED`); `status="COMPLETED", limit=1` → `idset == {AC.id}`. Same shape for `factory_id=F2.id` with two F1 rows ahead |

No fidelity findings. Every Then line of every card is asserted as written, with exact values. `committed:` lines start with one `db.rollback()`. Snapshots are taken at the commit point, before X. The only patches are the clock, the spies and the failing commit / refresh. LM-05 … LM-07 call the endpoint function as spec G1 allows.

## Surviving mutants
None (17 of 17 killed; each kill is a real `1 failed`).

## Hand variants
Run with my own runner `hv.py` on a copy of the backend (`wpsvcv\A\hv_pjs\`), plain run with `-m "not xfail"`. Base: 62 passed.

| Variant | Result | Killed by |
|---|---|---|
| no rollback in the `except` of each of the 6 writers (TC3) | KILLED ×6 | C-02 …, U-02 …, D-02 …, AM-02 …, RM-02 …, SV-03 … |
| flush instead of commit, each of the 6 writers | KILLED ×6 | C-01, U-01, D-01, AM-01, RM-01, SV-01 (+ failing-commit cards) |
| no re-read, each of the 5 re-reading writers | KILLED ×5 | C-06, U-06, D-06, AM-08, SV-07 |
| stray rollback on `get_project` / `list_projects` / `list_events` / `list_members` (TC6) | KILLED ×4 | G-05 …, L-14 …, EV-04 …, LM-04 … |
| stray commit on the same four reads (TC6) | KILLED ×4 | G-05, L-13/L-14, EV-04, LM-04 |
| `list_projects` drops `factory_id` / `status` / `skip` / `limit` | KILLED ×4 | L-05 / L-06, L-13 / L-04 / L-03 |
| extra audit event on a no-change update / same-visibility call | KILLED ×2 | U-07, U-01 / SV-02, SV-01 |
| the action's audit event deleted before commit (6 writers) | KILLED ×6 | C-01, U-01, D-01, AM-01, RM-01, SV-01 |
| `HTTPException` swallowed to `None` (update) | KILLED | U-02 … U-04 |
| 404 remapped to 400 (add_member) / 403 remapped to 404 (get_project) | KILLED ×2 | AM-05 / G-02 |
| **status filtered after paging in the service** | **SURVIVED** | — Finding 1 |
| **factory filtered after paging in the service** | **SURVIVED** | — Finding 1 |
| inert: `expire_all()` after commit in `remove_member` | SURVIVED | equivalent: no re-read and no observable change (a real `db.refresh` of the `None` result would raise) |
| inert: expunge pending `ProjectEvent`s before commit (update, add, remove, delete) ×4 | SURVIVED | equivalent: the manager has already flushed the events, so `db.new` holds none and nothing changes. The effective form (delete the event rows) is in the table above and was killed every time |

Note (no action): Then 3 of C-01 / Then 2 of U-01 ("returned re-read") alone do not notice a missing `db.refresh` under the `db` fixture. The failing-refresh card of each writer pins it.

## Traceability
cases 77 · tests 77 · unmatched: none · marker mismatches: none. 15 strict xfail; reasons BUG-1951, 1952, 1953, 1954, 1955, 1957, 1958 ×2, 1959, 1960, 1964, 1278 ×3, 2271, all present in `bugs.md`. Checked with `wpsvcv\A\trace.py` (AST).

## Commands run
```
COVERAGE_FILE=wpsvcv/.cov.project_service.1 .venv/Scripts/python.exe -m pytest tests/unit/services/test_project_service.py -q -p no:cacheprovider -o addopts= --cov=app.services.project_service --cov-branch --cov-report=term-missing
  app\services\project_service.py 74 0 0 0 100%   ·   62 passed, 15 xfailed
PYTHONPATH=wpsvcv/A .venv/Scripts/python.exe -m pytest tests/unit/services/test_project_service.py -q -p no:cacheprovider -o addopts= -p thenwhere --runxfail -rf
  15 failed, 62 passed. All on their cards' lines: C-07 Then 2 ('  Line 3 refit '); G-04, LM-02, AM-06, RM-06 Then 1 DID NOT RAISE; L-07 Then 1 set(); L-08, L-09 Then 1 both rows; L-10 Then 1 [Zulu, apple, Banana]; L-11 Then 1 one row; L-12 Then 1 {AP, AC}; U-08 Then 2 updated_by set; U-09 Then 2 Decimal('1000.00'); EV-05 Then 2 6 <= 3; LM-05 Then 2 (14-1)-3 <= 2
plain runs 2 and 3: 62 passed, 15 xfailed (both); ruff check: clean
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/project_service.py tests/unit/services/test_project_service.py --json wpsvcv/mut_project_service.json
  Mutants: 17 · killed 17 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe wpsvcv/A/hv.py wpsvcv/A/v_pjs.py wpsvcv/A/hv_pjs   (results: wpsvcv/A/hv_pjs.txt, hv_pjs2.txt)
```
(`wpsvcv` = `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvcv`)

## For the future notes
Nothing new for permissions, notifications or payments. The project role check (manager FU-2) and the private-project 403 / 404 question (OQ-18 vs OQ-5) are already in `docs/future/permissions.md`.

## Round 2 — 2026-11-06
Cases revision 4 · tests 79 (64 passed / 15 xfail).

**What changed** (diffed against the round-1 copy of the test file): new PJS-L-15 (status filter with `limit=2`, two PLANNING rows ahead) and PJS-L-16 (factory filter with `limit=2`, two F1 rows ahead), both pass cards, from Finding 1. The header now says revision 4. No other test changed.

**Traceability:** 79 cards, 79 tests, 15 strict xfails, no mismatches.

**Fidelity:** L-15 and L-16 were read against their cards. The Given rows, names, statuses and factories are as written, the call is exact, and both Then lines are asserted with `==`. No findings.

**Runs** (private `COVERAGE_FILE` under `wpsvcv\A\r2\`):
```
plain ×3: 64 passed, 15 xfailed (6.93s, 7.46s, 7.35s): stable
--cov --cov-branch: app\services\project_service.py 74 0 0 0 100%; 64 passed, 15 xfailed
--runxfail -rf: 15 failed, 64 passed (the same 15 strict cards as round 1; their tests are unchanged)
```

**Round-1 survivors, re-run** (`wpsvcv\A\hv.py`, plain `-m "not xfail"`, fresh copy `hv_pjs_r2`):
| Variant | Result | Killed by |
|---|---|---|
| list-status-filtered-after-paging | KILLED | PJS-L-15 |
| list-factory-filtered-after-paging | KILLED | PJS-L-16 |

No `mutate.py` run: round 1 had 17 of 17 killed, and no source line changed.

**Current verdict:** PASS — the round-1 finding is closed: both filter-after-paging variants now fail a card. The tests are faithful and stable.
