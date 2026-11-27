# Execution notes — `app/dao/machine_section_assignment.py`

> **State: Step D finished.** All 77 cards have a test; nothing is left to write.
> Cases: `tests/unit/dao/machine_section_assignment.cases.md` (READY, 77 cases; spec APPROVED 2026-10-16) · Tests: `tests/unit/dao/test_machine_section_assignment.py` · Source commit: e48a092
> Result: 77 tests for 77 cases = 6 exemplars + 56 local + 15 Claude. **69 passed · 8 xfail-marked (4 strict, 4 non-strict) · 0 discrepancies · 0 errors.** The usual whole-file output is `69 passed, 4 xfailed, 4 xpassed`. The four xpasses are the non-strict order cards. Line and branch coverage 100%.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine_section_assignment.py -q -p no:cacheprovider`

## How the tests are built
- **Local-coder mode.** The scaffold and six exemplars are hand-written. Tests under a `# [local-coder] <ID>` comment were written by the local model from one card each, with `machine_section_assignment.helpers.md` as its only view of the file. Tests under a `# [claude] <ID>` comment were written by hand at Step D. That covers the 14 `Author: claude` cards and MSA-UP-19, which the local model handed back.
- **Nothing is patched** (Externals: None). There is no clock fixture. `updated_at` comes from the model's `onupdate=func.now()`, and the cards only check it with `is None` / `is not None`. The commit spy of UP-20 and CL-12 wraps the real `db.commit`; it does not replace it.
- **Constants:** `dao` (= `machine_section_assignment_dao`, a module-level name, not a fixture) and `MISSING = 999999999`.
- **Standing-row fixtures.** Each fixture depends on the one before it, so the ids rise in Conventions order:
  - `w1`, `w2`, `u1`, `u2` come from `tests/unit/factories.py`.
  - Factories: `f1` ("Main Plant"/"MP", W1), `f2` ("North Yard"/"NY", W1), `f9` ("Far Depot"/"FR", W2).
  - Sections: `s1` "Cutting", `s2` "Paint", `s3` "Welding" (F2), `sx` "Old Line" (`is_deleted True`), `s9` "Packing" (F9, W2).
  - Machines: `m1` "Lathe", `m2` "Press", `m3` "Drill", `md` "Old Saw" (`is_deleted True`), `m9` "Grinder" (F9, W2).
  - Each section and machine takes its workspace from its factory. Machines are `is_active True` and `is_running False`.
  - The autouse fixture `standing_rows` makes all of them present in every test.
- **Builder:** `mk_assignment(*, of, to, **columns)` builds "assignment of M to S".
  - It sets `workspace_id` from the machine, `created_by U1.id`, and `updated_by` / `updated_at` None. `created_at` is left to the database.
  - A column after "but" is one more keyword (`workspace_id=w2.id`).
  - It flushes and does not expire the session.
- **Reading helpers** (plain functions with no expected values inside):
  - `ids(result)`.
  - `reread(db, row)` expires, then selects by id. It works for any of the four models.
  - `snap(db, row)` reads every column straight from the table.
  - `rows_of(db, machine)` expires, then selects the machine's assignments in any workspace, ordered by id.
  - `count_rows(db, "<table>", **where)`.
  - `written(db)` returns the counts of the four tables.
- **Database-error cards** wrap the call in `db.begin_nested()` inside `pytest.raises(...) as exc`. The `raises:` Then 1 is that block, under `# Then 1`.
- **"Re-created"** is only seen through `id` (`a1_id` taken in the Given) and `created_by` (U1 writes the Given rows, U2 calls). `created_at` is never compared.
- **The Given line "`loaded = M1.factory_section_id`"** (UP-21 … UP-24, CL-09, CL-10) is written `_loaded = m1.factory_section_id` in all six tests. It is the same statement; the leading underscore keeps ruff F841 quiet. The helper sheet still shows this spelling. The faithful spelling `loaded` is accepted by the runner since fix P22 (see below).
- **Added at Step D, for the Claude cards only.** The helper sheet is unchanged; the model never needs any of these.
  - Imports: `from unittest.mock import patch`, plus `event` and `insert` from `sqlalchemy`.
  - `bulk_assigned_machines(db, *, names, factory, section, created_by)` builds the Given rows of GS-10, GS-11 (501) and CL-06 (10 001). It makes one machine per name ("M1 but `name`": F1, W1, active, not deleted, not running) and one assignment of each to the section (Conventions defaults, `created_by U1.id`).
    - Each of the two sets is a single multi-row Core `insert(...).returning(id, sort_by_parameter_order=True)`, so the ids come back in list order.
    - It returns `(machine_ids, assignment_ids)`.
    - CL-06 takes about 3 s in all: the insert, then `clear_for_section` loading and deleting 10 000 ORM rows. GS-10 and GS-11 take about 0.05 s each.
  - `StatementRecorder(db)` is the Conventions "statement recorder" (GS-22, INH-07). It is a context manager that runs `event.listen(db.get_bind(), "before_cursor_execute", …)` around the When only and removes the listener on exit. `selects()` returns the recorded statements that start with `SELECT`.
    - A `statement:` line is two asserts: exactly one `SELECT` was sent, and it contains `ORDER BY`. This is the same check as FSD-GF-36 / INH-19 in the factory_section tests.
  - "Rolled back" (UP-20, CL-12) is written as follows:
    1. `with patch.object(db, "commit", wraps=db.commit) as commit_spy:` opens the block.
    2. `sp = db.begin_nested()` comes directly before the When.
    3. The in-session Then lines follow, including the follow-up DAO call.
    4. Then `sp.rollback()`.
    5. Then the "after the savepoint rollback" lines.
    6. Last, `commit_spy.call_count == 0`.
  - A step that a Then line puts between the When and its check stands under that `# Then N`, before the assert:
    - `db.expire(m1)` in UP-22 and CL-10;
    - `m1.name = "Renamed Unit"` + `db.flush()` in UP-24.
  - The Given step "`A1.created_by = U2.id`, then `db.flush()`" (GS-20, GS-21, CL-11, INH-06) is written inline on the row returned by `mk_assignment`.
- **Exemplars** (hand-written, 6, all printed verbatim in the sheet): MSA-GM-06, UP-01, UP-03 (strict xfail BUG-909), UP-17, CL-01, INH-04.

## Who wrote what (77)
| Author | Count | Cards |
|---|---|---|
| Hand-written exemplars (Steps A / B) | 6 | MSA-GM-06, UP-01, UP-03, UP-17, CL-01, INH-04 |
| Local model (Step C; 18 trial + 38 full run) | 56 | every card not named in the other two rows |
| Claude at finishing (Step D, `# [claude] <ID>`) | 15 | the 14 `Author: claude` cards MSA-GS-10, GS-11, GS-20, GS-21, GS-22, UP-20, UP-22, UP-24, CL-06, CL-10, CL-11, CL-12, INH-06, INH-07 (checked by grep: exactly these 14 carry the line) + MSA-UP-19, handed back by the local model |

Each Claude test is placed in card order inside its section, among the full-run local tests. The 18 trial tests stay in their block after the exemplars.

## Step D — the 15 Claude tests
All 15 are written as designed. None had to be bent, and none is a discrepancy.

| Card | Shape | Outcome |
|---|---|---|
| MSA-GS-10 | 501 bulk machines + assignments, default limit | pass |
| MSA-GS-11 | 501 bulk, `limit=501`; Then 2 against the sorted assignment ids | pass |
| MSA-GS-20 | A1 updated after A3; full order; non-strict BUG-906 | usually xpass (see Stability) |
| MSA-GS-21 | same Given; window `skip=1, limit=2`; non-strict BUG-906 | xpass in every run |
| MSA-GS-22 | statement recorder; **strict** BUG-906 | xfail; fails in Then 2 (the one SELECT has no `ORDER BY`; it ends `LIMIT … OFFSET …`) |
| MSA-UP-19 | `raises: IntegrityError` + `begin_nested`, `workspace_id=MISSING`; rows_of(M2) = 0; unchanged(A1); nothing written | pass |
| MSA-UP-20 | rolled back + commit spy; follow-up `get_by_machine` inside the savepoint | pass |
| MSA-UP-22 | `_loaded`, upsert to S2, `db.expire(m1)` under Then 2 | pass |
| MSA-UP-24 | `_loaded`, clear via `None`, rename M1 + flush under Then 2 | pass (the deleted row does not come back) |
| MSA-CL-06 | 10 001 bulk; **strict** BUG-907 | xfail; fails in Then 3: `assert 10000 == 10001` |
| MSA-CL-10 | `_loaded`, clear, `db.expire(m1)` under Then 2 | pass |
| MSA-CL-11 | A1 = M3 (row and machine ids in different orders), A1 updated; non-strict BUG-906 | xpass in every run |
| MSA-CL-12 | rolled back + commit spy; follow-up `get_by_section` inside the savepoint | pass |
| MSA-INH-06 | A1 updated after A2; `get_by_workspace` order; non-strict BUG-100 | xpass in every run |
| MSA-INH-07 | statement recorder on `get_by_workspace`; **strict** BUG-100 | xfail; fails in Then 2 (no `ORDER BY`) |

## xfail location check (`--runxfail -rf`)
| Card | Marker | Card's "Fails today on" | Actual failing assert | OK |
|---|---|---|---|---|
| MSA-UP-03 (exemplar) | strict BUG-909 | Then 3 (row id) | `assert result.id == a1_id` (new id = old + 1) under `# Then 3` | yes |
| MSA-GS-22 | strict BUG-906 | Then 2 | `assert "ORDER BY" in selects[0].upper()` | yes |
| MSA-CL-06 | strict BUG-907 | Then 3 | `assert len(result) == 10001` → 10000 | yes |
| MSA-INH-07 | strict BUG-100 | Then 2 | `assert "ORDER BY" in selects[0].upper()` | yes |
| MSA-GS-20, GS-21, CL-11, INH-06 | non-strict | Then 2 / 1 / 2 / 2 | not reached in the `--runxfail` run (passed) | allowed (non-strict) |

No local-model test is an xfail. The local run held no xfail card: the only other xfail card, UP-03, is an exemplar.

## Coverage
```
Name                                    Stmts   Miss Branch BrPart  Cover   Missing
app\dao\machine_section_assignment.py      28      0      6      0   100%
```
No coverage gaps: 100% line and branch coverage.

## Stability
- 13 whole-file runs. Every run was green (no failure, no error), and every strict xfail failed and every pass card passed in every run.
- In 12 of the 13 runs the output was `69 passed, 4 xfailed, 4 xpassed`: all four non-strict order cards passed.
- In 1 run (the first), MSA-GS-20 xfailed, giving `69 passed, 5 xfailed, 3 xpassed`.
- The non-strict cards exist for exactly this. Today's order is the order the database happens to produce, and here it mostly equals the intended order even after the row was updated. That is likely because the update of `created_by` is a HOT update and the planner reads through an index, which keeps the original tuple position. So these four cards rarely show BUG-906 / BUG-100. The strict statement-recorder cards GS-22 and INH-07 are the reliable alarms.
- Durations: whole file about 5–7 s. CL-06 takes about 2.9 s and the standing-row setup about 1.4 s once.

## Mechanical checks
- `ruff check` on the file: clean. `--select F841,F811`: clean.
- An AST pass for unused test arguments (`scratchpad/unused_args.py`) found none.
- The F401 noted at the scaffold stage (`InvalidRowCountInLimitClause`) is gone; MSA-GS-18 uses it now.

## Local-coder run
- **Model:** Qwen3.6-35B-A3B Q4_K_M (`Qwen_Qwen3.6-35B-A3B-Q4_K_M.gguf`), n_ctx 16,384, thinking off. The server was started and stopped around each run. It is off now.
- **Totals (`machine_section_assignment.local-run.json`):**
  - 57 cases sent (18 trial + 39 full run).
  - **50 accepted on the first try, 6 after retries, 1 handed back (MSA-UP-19).**
  - 2,129 s, 384,352 prompt tokens, 14,165 completion tokens.
- **Accepted after retry (6), all model slips that the runner caught correctly:**

  | Card | Attempts | Rejection |
  |---|---|---|
  | GS-01 | 2 | a Given row left out ("card names S2, the test never uses `s2`") |
  | UP-02 | 2 | `mk_assignment` not requested |
  | UP-08 | 2 | `f1` not requested |
  | UP-15 | 2 | `# Then N` comments missing or out of order |
  | UP-07 | 3 | `# Then N` comments; then an unused `before` |
  | UP-12 | 3 | `# Then N` comments; then an unused `before` |

- **Handed back: MSA-UP-19.** Root cause: the model.
  - Attempt 1 numbered the `raises:` line wrongly. It put `# Then 1` after the `with pytest.raises` block, on `isinstance(exc.value.orig, IntegrityError)`, which fails because `.orig` is the psycopg2 error. The test ran and failed.
  - Attempts 2 and 3 had five `# Then` comments for six Then lines, because the `pytest.raises` block had no `# Then 1` before it. The runner rejected both, correctly.
  - The card and the sheet are fine: the exemplar UP-17 shows the exact shape, and the full-run cards UP-16 and UP-18 with the same shape were accepted first try.
  - Written by Claude as `# [claude] MSA-UP-19 (handed back by the local model)`. It passes.
- **Local tests at Step D:** not read for fidelity (that is the verifier's job). None errors.
  - Two cosmetic edits, no change to what any test builds or asserts: a blank line between the Given rows and the snapshots in MSA-GS-01 was removed, and a blank line after the docstring in MSA-UP-10 was removed.
- **Helper sheet:** unchanged during the full run and at Step D.
- **Runner fix P22** (`docs/testing/local-coder-improvements.md`): since the full run, a Given code line such as `loaded = M1.factory_section_id` is no longer rejected as "assigned but never used". An assignment whose name appears in the card as a code line `` `name = …` `` is exempt. This run did not exercise the fix: the sheet still maps the line to `_loaded`, and UP-21, UP-23 and CL-09 were accepted with that spelling. The fix stays "fixed, untested" there.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage.

## Factories added
None (`tests/unit/factories.py` is unchanged).

## Notes for maintainers
- **When BUG-906 is fixed** (`ORDER BY id` in `get_by_section`): GS-22 will XPASS → remove its marker; also remove the non-strict markers of GS-20, GS-21, CL-11. Per the cases file, `get_by_section` and `clear_for_section` are on the dead-code list "remove together with the fix of BUG-908". With them, MSA-GS-01 … GS-22 and MSA-CL-01 … CL-12 are deleted, and BUG-906 / BUG-907 are closed.
- **When BUG-907 is fixed** (no 10 000 cap): CL-06 XPASSes → remove the marker.
- **When BUG-909 is fixed:** UP-03 XPASSes → remove the marker. UP-04 holds before and after.
- **When BUG-100 is fixed** (BaseDAO order): INH-07 XPASSes → remove the marker; also remove the non-strict marker of INH-06.
- The bulk helper uses Core inserts and so bypasses the ORM. Rows it creates are not in the identity map. That is fine for GS-10, GS-11 and CL-06, which only read ids and counts.
