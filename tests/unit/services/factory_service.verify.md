# Verification — `app/services/factory_service.py`

> **Verdict:** PASS
> Tests: 25 passed · 14 xfail, 11 strict + 3 non-strict (reproduced ✅) · coverage 100% branch (41 statements, 0 branches)
> Mutation: 10 mutants · 10 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 39 unfaithful** (read by eye, card against test)
> Hand variants: 20 · 18 caught by a pass card · 2 not caught (TC2 order on update / delete, by the cards' declared depth)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED

## Summary
- **The tests can be trusted as written.** Every one of the 39 tests matches its card: Given rows, the commit point, the uncommitted "Extra" row, every Then line with the card's exact values, and `db.rollback()` before the `committed:` lines.
- **Every mutant is killed**, and my hand variants of the transaction contract (drop the commit, drop or move the rollback, commit on error, drop the re-read, a read that commits / rolls back / flushes, a dropped `skip` / `search`) each fail a pass card, except a re-read moved before the commit on update and delete (see Hand variants; the cards test TC5 once, on create, by design).
- **The non-strict XPASS during the executor's parallel run.** C-08, L-08 and L-09 follow designer step 1b. None of them names one chosen row of an unordered page. C-08 checks a refusal. L-08 checks a page of size 2 with a set check (`ids()` is sorted). L-09 checks an order, so it is non-strict under the "missing sort order" rule. The order-independent strict alarms are the manager's statement recorders (FAC-CN-20 / CA-20 for BUG-893, FAC-S-52 / S-54 for BUG-898, FAC-S-53 for BUG-899), and the cards file defers to them. Today's outcome depends on heap order: C-08 passes if "Late" falls in the first 100 rows read, and L-08 passes if the deleted rows do not fill the 2-row page. That is exactly why they are non-strict, so a one-off XPASS is allowed. Not a finding. My 4 plain and 1 `--runxfail` runs gave 14 xfailed in each plain run.

No `factory_service.local-run.json`; all 39 tests are under `# [claude]`. Findings in local-written tests / local-written tests: 0 / 0. In others: 0 / 39.

## Findings
None.

## Surviving mutants
None. All 10 kills end in `N failed`.

## Hand variants
`hv.py` (my scratch) applies one text edit to today's source in a private copy of the backend. Each edit was checked to apply. It runs the pass cards (`-m "not xfail"`) without `-x`.

| Group | Variants | Caught | Cards that fail |
|---|---|---|---|
| TC1: commit → flush (create, update, delete) | 3 | 3 | C-01, C-04, C-05; U-01; D-01, D-07 |
| TC3: rollback dropped / commit on error | 6 | 6 | C-02, C-03, C-10; U-02; D-02, D-06 |
| TC2: refresh dropped | 3 | 3 | C-01, C-05; U-01; D-01 |
| TC2/TC5: refresh before the commit | 3 | 1 | C-05 (create only) |
| TC6: get commits / rolls back; list flushes | 3 | 3 | G-07; L-07 |
| arguments: `skip`, `search` dropped | 2 | 2 | L-04; L-01 |

**Not caught:** the refresh moved before the commit in `update_factory` and `delete_factory`. Only a failing refresh shows it, and the cards file says TC4/TC5 is tested once per service, on create ("Depth", skill step 1a). This is a declared depth choice, not a finding.

## xfail tests: fails-today check
`--runxfail` with my plugin `vfailmap.py`, which maps the failing line to its `# Then N`: 14 failed, 25 passed. Each card fails where its "Fails today on" says:
- Then 1 `DID NOT RAISE HTTPException`: C-07, C-08, C-09, G-04. D-05: `DID NOT RAISE ValidationError`.
- G-05, L-06: `TypeError` (`include_deleted`) in the When. G-06: the same `TypeError` inside Then 1's wrap.
- C-06: Then 2 `' Main Plant ' == 'Main Plant'`. U-05: Then 2 `updated_by` is U1. D-04: Then 1, the `ValueError` escapes.
- L-08: Then 1 `[] == [A, B]`. L-09: Then 2 insertion order. L-10: Then 1 `[] == [A, B, C]`.

## Reproduced claims
- The notes' Result line holds: `25 passed, 14 xfailed` in the coverage run and in 3 more plain runs. No flaky test.
- Patches are only those that Conventions name: the commit / refresh wraps (C-04, C-05), the race (C-09), the create patch (C-10) and the delete patch (D-04). No `try`, and no broad `pytest.raises`.
- `ruff check`: passes. `git diff -- app/services`: empty.

## Traceability
cases 39 · tests 39 · unmatched: none · duplicates: none · marker mismatches: none (my script `trace.py`: Expect ↔ marker, strictness, every BUG ID in the reason and in `docs/testing/bugs.md`). Card order equals file order.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/factory_service.py tests/unit/services/test_factory_service.py --json <scratch>/mut_factory_service.json
  Mutants: 10 · killed 10 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe -m pytest tests/unit/services/test_factory_service.py -q -p no:cacheprovider --cov=app.services.factory_service --cov-branch --cov-report=term-missing
  25 passed, 14 xfailed · app\services\factory_service.py 41 0 0 0 100%
.venv/Scripts/python.exe -m pytest tests/unit/services/test_factory_service.py -q -p no:cacheprovider --runxfail -rf     14 failed, 25 passed
pytest plain × 3                                                                                                     25 passed, 14 xfailed each
pytest --runxfail -p vfailmap (my plugin); hv.py factory_service (20 variants); trace.py; ruff check                  as above
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2v\` (private `COVERAGE_FILE`). Only this report was written in the repo. No commit. No process was killed.
