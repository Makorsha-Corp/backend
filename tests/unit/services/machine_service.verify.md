# Verification — `app/services/machine_service.py`

> **Current verdict (round 2, 2026-11-04): PASS.** All three round-1 findings are fixed; see "Round 2" at the end. The round-1 header below is kept as it was.

> **Verdict:** NEEDS WORK (no unfaithful test; two default values are unguarded and one Expect line is incomplete. The fixes go to the designer and the describer)
> Tests: 73 passed · 39 xfail, 37 strict + 2 non-strict; L-21 XPASSes non-strict, as the notes say (reproduced ✅) · coverage 100% branch (78 statements, 4 branches)
> Mutation: 34 mutants · 30 killed · 4 survived → score 94% (30 / 32, after excluding 2 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 112 unfaithful** (read by eye, card against test)
> Hand variants: 34 · 29 caught by a pass card · 5 not caught (1 bug-path, 4 by declared TC2 depth)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED

## Summary
- **The tests are faithful.** All 112 match their cards: the standing rows in Conventions order, the M1 … MZ recipes, `bulk()`, the `sql_log` (started after the commit point, with arguments read before it; the notes explain why, and the cards still hold), and every Then line with exact values and order.
- **The service's own logic is well guarded.** These variants all fail pass cards: the response shaping (the map lookup ignored, the map path that reads anyway, `latest_status_at` dropped, the map read for only one id), the upcoming-work window (end −1 day, start yesterday, `factory_id` dropped), the activity filters, the metadata truthiness, `performer_name`, and every TC variant on create / delete / event.
- **What is missing:** the default `maintenance_window="all"` is never observed (designer). The default `limit=100` of `get_machine_activity` has no rule (describer). The L-20 Expect line names only BUG-957, although the card fails today on BUG-956 (designer).
- **L-20 (BUG-957 vs BUG-956).** The test is honest. It fails in the When on BUG-956's `TypeError`, which is exactly what the card's "Fails today on" line says. Its reason names both bugs. The card's Expect line names only BUG-957, so the register cannot see that this card waits on BUG-956 too (Finding 1).
- **L-21 XPASS (BUG-1090).** It is non-strict, the card allows it, and the strict `ORDER BY` alarm is `machine_activity_manager.cases.md` SM-14. It XPASSed in every run. Not a finding.
- **The DTZ001 / DTZ011 header silence** covers only the naive T0 … T3 and `date.today()`, which Conventions prescribe (no clock patch, `D(n)` read in the test). It is justified.

No `machine_service.local-run.json`; all 112 tests are under `# [claude]`. Findings in local-written tests / local-written tests: 0 / 0. In others: 0 / 112.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | marker / card text | MCS-L-20 | The Expect line is `xfail BUG-957`, but the card can pass only when BUG-956 (`include_deleted` on `get_machines`) is fixed too. The test's reason rightly names both IDs; the card should match it: `xfail BUG-956, BUG-957`. | `--runxfail`: When `TypeError … unexpected keyword argument 'include_deleted'`; `trace.py`: the reason has an extra BUG-956 | case designer |
| 2 | case-missing | `get_machines` R1 ("with no arguments … the defaults shown in the signature"), source line 175 | No card can tell `maintenance_window="all"` from any other unknown value. Mutant `'all' → ''` survives. `''` sends the manager down the work-semantics path: it reads work orders, loads at most 10 000 machines and pages in Python. That path gives different results past 10 000 machines and different SQL. Suggested: a Then line on L-23 (already logged with `sql_log`): no recorded statement reads `work_orders`. Or a 10 001-machine card with `skip=10000`. | mutant #13 survived | case designer |
| 3 | spec-gap | `get_machine_activity` signature `limit=100` (source line 383) | No rule says what the default `limit` is. The endpoint always passes `limit` (`Query(100)`), so the service default is reached only by direct callers. Mutant `100 → 101` survives. Either write the default as a rule (then the designer adds one card with 101 entries and no `limit`) or list it under Not specified as unreachable. | mutant #25 survived | describer (fill-gaps) |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 13 | 175 | `'all'` → `''` | case-missing | See Finding 2. Not equivalent: `''` takes the manager's 10 000-cap work path (machine manager lines 252, 270–283, 335). | case designer |
| 14 | 183 | `'name'` → `''` | equivalent | The manager passes `sort_by` to the DAO, where `sort_field_map.get('', Machine.name)` falls back to name. `== "maintenance_date"` is false for both values. This fallback is intended (machine DAO Q2, manager P8). | — |
| 15 | 185 | `'asc'` → `''` | equivalent | The DAO tests `sort_dir == "desc"`, and the manager tests `== "desc"` only. `''` and `'asc'` both sort ascending. | — |
| 25 | 383 | `limit` 100 → 101 | spec-gap | See Finding 3. | describer |

## Hand variants
Made with `hv.py`. Each is one text edit to today's source in a private copy, run on the pass cards without `-x`.

| Group | Variants | Caught | Cards that fail |
|---|---|---|---|
| TC1: commit → flush (create, update, delete, event) | 4 | 4 | C-01, C-06, C-07, C-08; U-01, U-07; D-01, D-06; E-01 |
| TC3: rollback dropped / commit on error | 7 | 7 | C-02, C-04, C-05; U-02, U-06; D-02; E-02 |
| TC2: refresh dropped / before the commit | 6 | 2 | C-07 (create only) |
| shaping: map ignored, map path reads, `latest_status_at` dropped, map for one id | 4 | 4 | R-04, R-05, RS-02, L-01, L-23, G-01, D-01 … |
| list arguments: section, `is_running`, `has_manufacturer` dropped | 3 | 3 | L-06 |
| list argument: `latest_event_type` dropped | 1 | 0 | — (bug-path: only L-12, xfail BUG-886, reaches it) |
| upcoming work: end −1, start −1, `factory_id` dropped | 3 | 3 | W-01, W-02; W-09 |
| activity: from / to / type dropped, metadata `is not None`, performer `None` | 5 | 5 | A-02; A-06; A-01 |
| TC6: get commits, activity flushes, upcoming rolls back | 3 | 3 | G-09; A-11; W-14 |

Not caught by declared depth: a dropped or moved refresh on update and delete. The cards file says TC2 cannot be read off a `MachineResponse` and is covered through C-07 on create only. Not a finding.

## xfail tests: fails-today check
`--runxfail` with `vfailmap.py`: 38 failed, 74 passed (L-21 passes). Each card fails on its "Fails today on" line:
- Then 1 `DID NOT RAISE`: C-10, C-12, C-13, G-04, G-07, U-08, U-12, D-07, E-06 (`HTTPException`); C-14 (pydantic); D-05 (`AppValidationError`).
- In the When: G-05, G-08, L-10, L-20 (`TypeError include_deleted`); L-12 (`AttributeError 'astext'`); U-09 (`IntegrityError machines_updated_by_fkey`); U-14 (`HTTPException 400`). G-06: the `TypeError` inside Then 1's wrap. U-10: Then 1 `IntegrityError machines_factory_id_fkey`. D-04: Then 1, the `ValueError` escapes.
- Then 1 values: C-15 `100 == 101`; L-13 `['bolt', 'Bolt']`; L-14 / L-19 `['Alpha', 'Zenith']`; L-15 `[Alpha]`; L-16 `['Alpha', 'Kiln']`; L-17, L-18 `[]`; W-12 `[M9, M1]`; W-13 `[MF, M1]`.
- Then 2: C-09, C-11 (untrimmed), U-11 `'L-200' is None`, E-05 `0 >= 1`, A-13 `7 <= 3`. Then 3: U-13 `1 == 0`, U-15 (the order keeps F1).

## Reproduced claims
- The notes' Result line holds: `73 passed, 38 xfailed, 1 xpassed` in the coverage run and in 3 more plain runs. No flaky test.
- Patches are only those that Conventions name: the commit / refresh wraps, the shaping patch (C-08), the manager patch (D-04) and the race (C-12). `ruff check` passes. `git diff -- app/services` is empty.

## Traceability
cases 112 · tests 112 · unmatched: none · duplicates: none · marker mismatches: L-20 only (an extra BUG-956 in the reason; Finding 1). Every BUG ID is in `docs/testing/bugs.md`. Card order equals file order.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/machine_service.py tests/unit/services/test_machine_service.py --json <scratch>/mut_machine_service.json
  Mutants: 34 · killed 30 · timeout 0 · survived 4 · score 88% (raw)
.venv/Scripts/python.exe -m pytest tests/unit/services/test_machine_service.py -q -p no:cacheprovider --cov=app.services.machine_service --cov-branch --cov-report=term-missing
  73 passed, 38 xfailed, 1 xpassed · app\services\machine_service.py 78 0 4 0 100%
.venv/Scripts/python.exe -m pytest tests/unit/services/test_machine_service.py -q -p no:cacheprovider --runxfail -rf     38 failed, 74 passed
pytest plain × 3                                                                                                     73 passed, 38 xfailed, 1 xpassed each
vfailmap.py; hv.py machine_service (34 variants); trace.py; ruff check                                               as above
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2v\` (private `COVERAGE_FILE`). Only this report was written in the repo. No commit. No process was killed.

## Round 2 — 2026-11-04
**Verdict: PASS.** Cases revision 2, spec R1a. 74 passed · 39 xfail (37 strict + 2 non-strict; L-21 XPASSes as before) · coverage 100% branch.

- **The changed and new tests are faithful to their cards.**
  - MCS-L-20: the Expect line is now `xfail BUG-956, BUG-957`; the reason names both and the Rules line matches. With `--runxfail` it still fails in the call on the `TypeError`, as the card says.
  - MCS-L-23: Then 4 is `not any("work_orders" in s for s in sql_log)`, as the card says.
  - MCS-A-14 (new): 100 events at T0 + k minutes, then O at T0 flushed last; Then 1–3 are as the card says.
- **The routed variants are now caught** (my `hv2.py`, pass cards, without `-x`):

| Variant | Round 1 | Round 2 |
|---|---|---|
| `maintenance_window` default `'all'` → `''` | 73 passed | L-23 fails |
| `get_machine_activity` default `limit` 100 → 101 | 73 passed | A-14 fails |

- **Mutation, only on the lines of the round-1 survivors** (`--lines 175-185`, `--lines 383-383`): 4 mutants, 2 killed (`'all'` → `''` by L-23; `100 → 101` by A-14), 2 survived. The survivors are `'name'` → `''` and `'asc'` → `''`, both equivalent as in round 1. Module score: 32 / 32 non-equivalent = **100%**.
- **Runs:** coverage run plus 3 plain runs each give `74 passed, 38 xfailed, 1 xpassed`; `--runxfail` gives `38 failed, 75 passed`. No flaky test. `trace.py`: 113 cards, 113 tests, no marker mismatch. `ruff check` passes. `app/services` is unchanged.
- **Findings:** none.
