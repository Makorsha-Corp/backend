# Verification — `app/services/factory_section_service.py`

> **Verdict:** PASS
> Tests: 27 passed · 24 xfail, 20 strict + 4 non-strict (reproduced ✅) · coverage 100% branch (41 statements, 0 branches)
> Mutation: 10 mutants · 10 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 51 unfaithful** (read by eye, card against test)
> Hand variants: 19 · 17 caught by a pass card · 2 not caught (TC2 order on update / delete, by the cards' declared depth)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 51 tests match their cards: the standing factories F1, F2, F9, FD, FI in Conventions order, sections with every default column, the "Extra" row of F2 after the commit point, and every Then line with the card's values.
- **Every mutant is killed.** Every hand variant of the transaction contract and of the passed-on arguments fails a pass card, except a re-read moved before the commit on update and delete. TC5 is carded once, on create, by the declared depth.
- **The non-strict cards follow designer step 1b.** C-10, L-09, L-11 and L-12 never name a chosen row of an unordered page: L-11 uses a 2-row page with a set check, and L-09 / L-12 are order checks. The strict statement recorders live in `factory_section_manager.cases.md` (CN-17, S-58, S-59, S-65, S-66), as the Deferred table says. The non-strict cards xfailed in all of my runs.

No `factory_section_service.local-run.json`; all 51 tests are under `# [claude]`. Findings in local-written tests / local-written tests: 0 / 0. In others: 0 / 51.

## Findings
None.

## Surviving mutants
None. All 10 kills end in `N failed`.

## Hand variants
Made with `hv.py`, as in `factory_service.verify.md`.

| Group | Variants | Caught | Cards that fail |
|---|---|---|---|
| TC1: commit → flush | 3 | 3 | C-01, C-06, C-07; U-01; D-01 |
| TC3: rollback dropped / commit on error | 6 | 6 | C-02, C-05; U-02; D-02 |
| TC2: refresh dropped | 3 | 3 | C-01, C-07; U-01; D-01 |
| TC2/TC5: refresh before the commit | 3 | 1 | C-07 (create only) |
| TC6: get commits; list rolls back | 2 | 2 | G-09; L-08 |
| arguments: `factory_id`, `search` dropped | 2 | 2 | L-01; L-02 |

The refresh moved before the commit on update and delete is not caught. As in the factory service, TC5 is carded once per service, on create, by declared depth. Not a finding.

## xfail tests: fails-today check
`--runxfail` with `vfailmap.py`: 24 failed, 27 passed. Each card fails on its "Fails today on" line:
- Then 1 `DID NOT RAISE HTTPException`: C-09, C-10, C-11, G-04, G-07, U-07, U-10, U-11, D-05.
- `TypeError` (`include_deleted`): G-05, G-08, L-07 in the When; G-06 inside Then 1's wrap.
- U-09: Then 1 `IntegrityError factory_sections_factory_id_fkey`. C-08: Then 2 `'  Paint ' == 'Paint'`. U-08: Then 2 `updated_by` is set. D-04: Then 3 `0 == 2`.
- L-10: Then 1 `[H] == []`. L-11: Then 1 `[A] == [A, B]`. L-09 / L-12: Then 2 insertion order. L-13: Then 1 `[] == [A, B]`. L-14: Then 1 `[A, B] == []`. L-15: Then 2 `[A, H] == [A]`.

## Reproduced claims
- The notes' Result line holds: `27 passed, 24 xfailed` in the coverage run and in 3 more plain runs. No flaky test.
- Patches are only the commit / refresh wraps (C-06, C-07) and the race (C-11). `ruff check` passes. `git diff -- app/services` is empty.

## Traceability
cases 51 · tests 51 · unmatched: none · duplicates: none · marker mismatches: none (`trace.py`). Every BUG ID is in `docs/testing/bugs.md`. Card order equals file order.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/factory_section_service.py tests/unit/services/test_factory_section_service.py --json <scratch>/mut_factory_section_service.json
  Mutants: 10 · killed 10 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe -m pytest tests/unit/services/test_factory_section_service.py -q -p no:cacheprovider --cov=app.services.factory_section_service --cov-branch --cov-report=term-missing
  27 passed, 24 xfailed · app\services\factory_section_service.py 41 0 0 0 100%
.venv/Scripts/python.exe -m pytest tests/unit/services/test_factory_section_service.py -q -p no:cacheprovider --runxfail -rf     24 failed, 27 passed
pytest plain × 3                                                                                                                     27 passed, 24 xfailed each
vfailmap.py; hv.py factory_section_service (19 variants); trace.py; ruff check                                                       as above
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2v\` (private `COVERAGE_FILE`). Only this report was written in the repo. No commit. No process was killed.
