# Execution notes — `app/managers/machine_section_assignment_manager.py`

> Cases: `tests/unit/managers/machine_section_assignment_manager.cases.md` (READY, 51 cases; spec APPROVED 2026-10-16) · Tests: `tests/unit/managers/test_machine_section_assignment_manager.py` · Source commit: e48a092
> Result: 51 tests for 51 cases = 6 exemplars + 38 local + 7 Claude. **47 passed · 4 xfail-marked (3 strict, 1 non-strict) · 0 discrepancies · 0 errors.** The whole-file output is `47 passed, 3 xfailed, 1 xpassed` in every run so far; the xpass is the non-strict order card MSM-CLR-13. Line coverage 100%, branch coverage 98% (the one missed branch is unreachable, see Coverage gaps).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_machine_section_assignment_manager.py -q -p no:cacheprovider`

## How the tests are built
- **Local-coder mode.**
  - The scaffold and six exemplars are hand-written.
  - Tests under a `# [local-coder] <ID>` comment were written by the local model, one card each. Its only view of the file is `machine_section_assignment_manager.helpers.md`.
  - Tests under a `# [claude] <ID>` comment were written at Step D: the five `Author: claude` cards and the two cards the local model handed back (marked "(handed back by the local model)").
- **Who wrote what:**

  | Author | Tests | Cards |
  |---|---|---|
  | Claude, exemplars (Step A) | 6 | MSM-SET-01, SET-08, SET-13, SET-15, SET-29, CLR-01 |
  | Local model (Step C) | 38 | the other 38 non-claude cards except SET-26 and CLR-02 |
  | Claude at finishing (Step D) | 7 | the 5 `Author: claude` cards MSM-SET-34, SET-35, CLR-09, CLR-13, CLR-14 (checked by grep: exactly these 5 carry the line) + MSM-SET-26 and CLR-02, handed back by the local model |

- **File order.** Exemplars first, then the 16 trial tests in trial order, then the full run in card order within each section; the Claude tests sit at their card's place in that last block (SET-26 after SET-25, SET-34 and SET-35 after SET-33, CLR-02 before CLR-03, CLR-09, CLR-13, CLR-14 after CLR-08).
- **Nothing is patched** (Externals: None). The only mock is the `db.commit` spy of the two "rolled back" cards (`patch.object(db, "commit", wraps=db.commit)`, still callable, `call_count == 0` asserted).
- **Constants:**
  - `mgr` = `machine_section_assignment_manager`, a module-level name and not a fixture. The cards call it `mgr`.
  - `MISSING = 999999999`.
- **Standing-row fixtures.** Each one depends on the one before it, so ids rise in Conventions order:
  - `w1`, `w2`, `u1`, `u2` (from `tests/unit/factories.py`);
  - factories `f1`, `f2`, `f9`, `fd` ("Closed Mill"/"CM", W1, `is_deleted True`);
  - sections `s1`, `s2`, `s3`, `sx`, `s9`, `sf` ("Boiler Room", of FD);
  - machines `m1`, `m2`, `m3`, `md`, `m9`, `mf` ("Kiln", of FD).

  Sections and machines take their workspace from their factory. The autouse fixture `standing_rows` makes all 20 rows present in every test. The rows are copied from the assignment DAO's test file; FD, SF and MF are the additions.
- **Builders** (fixtures, keyword-only, flush):
  - `mk_assignment(of=, to=, **columns)` — "assignment of M to S": workspace of the machine, `created_by U1`, `updated_*` None.
  - `mk_factory(name=, abbreviation=, **columns)` — "extra factory": W1, active, live.
  - `mk_section(of=, name=, **columns)` — "section of F".
  - `mk_machine(of=, name=)` — "machine of F".
- **Bulk helper** `bulk_assigned_machines(db, names=, factory=, section=, created_by=)` (MSM-CLR-09 only; copied from `tests/unit/dao/test_machine_section_assignment.py`, not in the helper sheet): one multi-row `insert(...).returning(id, sort_by_parameter_order=True)` for the 10 001 machines (M1's columns, `name` "Bulk 00001" … "Bulk 10001") and one for their 10 001 assignments to S1 (`created_by U1`). Returns the ids in insertion order. The whole file runs in about 7.5 s; most of that is this test, mostly the manager's 10 000 `session.get(Machine, …)` calls.
- **Reading helpers** (no expected values inside), the same as the DAO file: `reread`, `snap`, `rows_of` (any workspace, ordered by id), `count_rows(db, table, **equality filters)`, and `written` (counts of the four tables).
- **Error cards:**
  - `HTTPException` cards use plain `pytest.raises`, with no savepoint.
  - `IntegrityError` cards put the call in `db.begin_nested()` inside `pytest.raises`.
- **"Rolled back" cards** (SET-35, CLR-14): `sp = db.begin_nested()` directly before the call, inside the commit spy's `with`; the "inside the savepoint" checks, then `sp.rollback()`, then the "after the savepoint rollback" checks (each re-read via `rows_of` / `reread` / `count_rows`, which expire first).
- **Given code lines are run verbatim.** Examples: `loaded = m1.factory_section_id`, `mn.name = "Edge Trimmer"`, `db.expunge_all()`, the tuple line of CLR-12, and `a1.created_by = u2.id; db.flush()` of CLR-13. ruff F841 is turned off file-wide in the header for the `loaded…` lines; `ruff --select F841 --ignore-noqa` lists exactly those 8 lines and nothing else.
- **SET-34:** the card's step `db.expire(M1)` is written inside Then 2, directly before its assertion (as in the DAO's MSA-UP-22).

## Local-coder run
- Model: Qwen3.6-35B-A3B Q4_K_M (`Qwen_Qwen3.6-35B-A3B-Q4_K_M.gguf`), n_ctx 16,384, thinking off.
- **40 cases** sent (46 non-claude cards minus 6 exemplars), including the 16 of the trial. `local-run.json` totals: 1,702.9 s, 282,561 prompt tokens, 11,570 completion tokens.
- **34 accepted on the first attempt, 4 after a retry, 2 handed back after 3 attempts.**

  | Card | Outcome | Rejection(s) | Root cause |
  |---|---|---|---|
  | SET-19 | accepted, attempt 2 | `mk_section` used but not in the argument list | model (sheet example was then extended to name `mk_section`) |
  | SET-23 | accepted, attempt 2 | same | model |
  | SET-28 | accepted, attempt 2 | card names U1, test never used `u1` | model (dropped the `created_by == U1.id` check, restored on retry) |
  | CLR-03 | accepted, attempt 2 | `before` assigned and never used | model (added an unasked "nothing written" snapshot) |
  | SET-26 | **handed back** | 3 × "the card has 3 Then lines" | model: kept adding a fourth Then line ("nothing written") the card does not have |
  | CLR-02 | **handed back** | failed / unused `before_ad` / failed | model: wrote `unchanged(AD)` where the card says `unchanged(MD)`; AD is the deleted link, so the snapshot compare fails |

  Neither hand-back points at the card, the spec or the sheet: both cards are plain and were written from them as designed (see Step D). Both are the model copying a habit ("nothing written" after a call; snapshot of the row named in the Given) over the card's literal Then line.
- **Accepted xfail check.** SET-19: `fails_on` `Failed: DID NOT RAISE HTTPException`, `fails_in_then` 1 = the card's "Fails today on: Then 1". Confirmed again with `--runxfail` (below).
- **Helper sheet:** 10,391 characters (over the 9,000 guideline; five of the six exemplars printed). Only change during the run: the argument-list rule's example now names `mk_section`.

## Step D (finishing)
- **Written by Claude:** MSM-SET-26, SET-34, SET-35, CLR-02, CLR-09, CLR-13, CLR-14. Each follows its card: Given rows in order, one When call, a `# Then N` comment before each numbered Then line and one `assert` per listed check.
- **Markers:** CLR-09 `xfail(strict=True, reason='BUG-907: "Unassign every machine of a section" stops at 10 000')`; CLR-13 `xfail(strict=False, reason="BUG-906: … (non-strict: today's order is the physical row order, which can match by accident)")`.
- **Local tests:** not read for fidelity and not changed. Cosmetic edits only to the file header: the import block (added `patch`, `insert`; dropped a no-longer-needed `# noqa: F401`; ruff I001 wrap of the manager import) and one docstring sentence naming the handed-back cards. A diff against the as-delivered copy shows only those lines changed plus the 7 added tests and the bulk helper. No local test errors.
- **Mechanical checks:** `ruff check` clean. `ruff --select F841,F811 --ignore-noqa`: only the 8 Given `loaded…` lines. AST pass for unused test arguments: none.

### xfail location check (`--runxfail -rf`)
| Card | Marker | Card's "Fails today on" | Fails with `--runxfail` on | Verdict |
|---|---|---|---|---|
| MSM-SET-08 | strict BUG-909 | Then 3 (new id) | Then 3: `assert result.id == a1_id` (`752895 == 752894`) | correct |
| MSM-SET-19 | strict BUG-910 | Then 1 (no error) | Then 1: `DID NOT RAISE HTTPException` | correct |
| MSM-CLR-09 | strict BUG-907 | Then 3 (10 000 ids) | Then 3: `assert 10000 == 10001` | correct |
| MSM-CLR-13 | non-strict BUG-906 | Then 2 | not reached: passes (row order happened to match) | allowed (non-strict) |

Output: `3 failed, 48 passed`.

## Stability
10 whole-file runs after finishing, every one `47 passed, 3 xfailed, 1 xpassed` (7.5–7.9 s). Never red. No strict xfail and no pass card flipped. MSM-CLR-13 xpassed in all 10 runs, as the DAO's MSA-CL-11 does: the update of A1 (`created_by`) does not move it behind A3 in the order the query returns, so the result is `[M3, M1, M2]` by accident. The marker stays non-strict; it is not loosened or removed.

## Discrepancies
None.

## Coverage
`--cov=app.managers.machine_section_assignment_manager --cov-branch --cov-report=term-missing`:

```
Name                                                 Stmts   Miss Branch BrPart  Cover   Missing
app\managers\machine_section_assignment_manager.py      28      0     12      1    98%   62->60
```

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 62->60 | unreachable | In `clear_for_section`, `if machine is not None:` after `session.get(Machine, machine_id)`. The ids come from links the DAO just deleted, and `machine_section_assignments.machine_id` is a foreign key to `machines`, so every returned id names an existing machine and the "None → next id" branch is never taken. The spec and the cases file (Coverage gaps, deliberate) say the same; no card. |

## Factories added
None. All builders are local to the test file.

## Notes for maintainers
- **When BUG-909 is fixed:** SET-08 XPASSes → remove the marker. SET-09 holds before and after.
- **When BUG-910 is fixed:** SET-19 XPASSes → remove the marker.
- **When BUG-907 is fixed:** CLR-09 XPASSes → remove the marker.
- **When BUG-906 is fixed** (`ORDER BY id` in the DAO's query): remove CLR-13's non-strict marker.
- **When BUG-908 is fixed:** `clear_for_section` is on the dead-code list "remove together with the fix of BUG-908". MSM-CLR-01 … CLR-14 are deleted with it, and with them BUG-906's and BUG-907's markers here.
- CLR-09 inserts 10 001 machines and links into the rolled-back test transaction; it relies on the 10 000 cap of the DAO to fail on Then 3, so other data in S1 of W1 would change it (none exists: the standing rows are per test).
- Other agents run other test files against the same database; this file's tests only count rows by filters on per-test ids, except the whole-table counts (`count_rows(db, "machine_section_assignments")`, `written`), which see only this transaction's uncommitted rows plus committed data. They have stayed stable across 10 runs while other files ran.
