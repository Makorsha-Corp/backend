# Execution notes — `app/dao/factory.py`

> **Current state (2026-10-11, after Fix round 0 and verification PASS):** 110 tests = 7 exemplars + 88 local + 15 Claude · 100 passed · 10 xfailed (4 strict, 6 non-strict) · stable in 12 whole-file runs. The sections below up to "Fix round 0" describe the file as it was after Step D (108 tests, 8 xfailed, not stable) and are kept as the record of that step.

> Cases: `tests/unit/dao/factory.cases.md` (READY; the spec is APPROVED 2026-10-16 with every suggested answer accepted, so no card changed) · Tests: `tests/unit/dao/test_factory.py` · Source commit: e48a092
> Result: 108 tests for 108 cases. **As designed: 100 passed · 8 xfailed · 0 errors** (seen on the first run after Step D and on two later runs, 3 of 9) — **but not stable**: the three strict BUG-100 xfail tests (FCD-GW-22, GW-23, GW-24) XPASS in some runs, which strict xfail reports as failures (`2 failed, 100 passed, 6 xfailed` / `3 failed, 100 passed, 5 xfailed`). Recorded as DISCREPANCY-1 (kind `flaky`) below; nothing was changed to hide it. Branch coverage 100%.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_factory.py -q -p no:cacheprovider`

## How the tests are built
- **Local-coder mode.** The scaffold and seven exemplars are hand-written; tests under a `# [local-coder] <ID>` comment were written by the local model from one card each, with `factory.helpers.md` as its only view of the file; tests under a `# [claude] <ID>` comment are the 13 `Author: claude` cards, written by hand at finishing (Step D).
- **Clock.** The autouse fixture `standing_rows` patches `app.dao.factory.utcnow` to return `NOW` in every test (Conventions, Externals). Nothing else is mocked; the commit spy of FCD-SD-09 / RS-10 wraps the real `db.commit` and does not replace it.
- **Constants:** `dao` (= `factory_dao`, a module-level name, not a fixture), `MISSING`, `T0`, `NOW`.
- **Fixtures (standing rows):** `w1`, `w2`, `u1`, `u2` (from `tests/unit/factories.py`), each depending on the one before it; `standing_rows` (autouse) makes all four present in every test. No factory, machine or section is a standing row — every card lists its own.
- **Builders (fixtures, keyword-only, flush before returning):**
  - `mk_factory(*, name, abbreviation, deleted=False, **columns)` — the Conventions "factory" (`workspace_id W1.id`, `created_by U1.id`, `updated_by None`, `updated_at None`, `is_active True`, not deleted, `created_at` left to the database). `deleted=True` is the Conventions word "deleted" (`is_deleted True`, `deleted_at T0`, `deleted_by U1.id`; `is_active` untouched), so the model never expands it.
  - `mk_machine(*, of, name, **columns)` — "machine of F"; `mk_section(*, of, name, **columns)` — "section of F". Workspace and factory id come from the factory passed as `of`. `of` is the card's own word, which the tool's keyword check needs.
- **Reading helpers (plain functions):** `ids(result)`, `names(result)` (keep the returned order), `by_id(result, row)`, `reread(db, row)` (any of the three models; expires first), `snap(db, row)` (unchanged; reads the table directly), `count_rows(db, "<table name>")` (`factories`, `machines`, `factory_sections`), `written(db)` (the three counts of "nothing written").
- **Literal-code Given lines** are written as they stand: `f1.abbreviation = "ZX"` then `db.flush()` (BUG-100 recipe, FCD-GW-21 … GW-24); `db.refresh(f1)` (FCD-RS-08, RS-09). Snapshots are taken after them.
- **Database-error cards** (`raises: DataError`, `raises: IntegrityError`) wrap the call in `db.begin_nested()` inside `pytest.raises(...) as exc`.
- **Added at Step D (for the `Author: claude` cards only; no new helper function or fixture, `factory.helpers.md` is unchanged):**
  - `from unittest.mock import patch` — the commit spy of "rolled back": `with patch.object(db, "commit", wraps=db.commit) as commit_spy:`, then `sp = db.begin_nested()` directly before the When call, the in-session checks, `sp.rollback()`, the "after the savepoint rollback" checks, and `commit_spy.call_count == 0` (FCD-SD-09, RS-10).
  - `from app.dao.machine import machine_dao` — the Conventions "Machine lookup" (FCD-RS-14).
  - Bulk rows are built inline with `mk_factory` in a loop or a list comprehension that keeps the ids (`all_ids = [mk_factory(name=f"N{k:03d}", abbreviation=f"A{k:03d}").id for k in range(1, 102)]`), one flush per row, in the order the card gives — no bulk helper.
  - "every column except `updated_at` equals BEFORE" (FCD-RS-15, RS-16): `before = snap(db, f1)` after the first Given row and before the Given `dao.soft_delete(...)`; after the call `reread`, then `snap` again and compare the two dicts without the key `updated_at`.
- **Exemplars (hand-written, 7):**

  | Card | Shape it shows | In the sheet |
  |---|---|---|
  | FCD-GW-05 | plain lookup; `deleted=True`; `sorted(ids(...))`, `by_id` | yes |
  | FCD-GW-22 | strict xfail BUG-100; the recipe (literal-code Given line) | yes |
  | FCD-GA-22 | `raises: DataError` + `begin_nested`; nothing written; unchanged | yes |
  | FCD-SD-10 | `soft_delete`; `workspace_id=w2.id`; `NOW`, `u2.id`, `w2.id` asserted; two values on one re-read line; unchanged of another row | yes |
  | FCD-RS-02 | `restore`; `created_before`; `w1.id`, `u1.id` asserted | yes |
  | FCD-RS-08 | `restore` after `db.refresh`; unchanged; `updated_at is None`; a `count:` line | yes |
  | FCD-INH-06 | inherited `update` with a schema | **no** — written by hand because of a runner false rejection (see below) |

  Between them the printed exemplars assert on `w1.id`, `w2.id`, `u1.id` and `u2.id`. No error card without a snapshot exists in this module (every `raises:` card has "nothing written", "unchanged(X)" or both).
- **Helper sheet:** `factory.helpers.md`, 9,981 characters (10,029 bytes).

## Who wrote what (108)
| Author | Count | Cards |
|---|---|---|
| Hand-written exemplars (Steps A / B) | 7 | FCD-GW-05, GW-22, GA-22, SD-10, RS-02, RS-08, INH-06 |
| Local model (Step C; 17 in the trial + 71 in the full run) | 88 | every card not named in the other two rows |
| Claude at finishing (Step D, `# [claude] <ID>`) | 13 | FCD-GW-08, GW-11, GW-12, GA-13, GA-14, GA-15, GA-26, SD-09, RS-07, RS-10, RS-14, RS-15, RS-16 |

## Step D — the 13 `Author: claude` cards
All 13 are written as designed; none had to be bent and none is a discrepancy.

| Card | Shape | Outcome |
|---|---|---|
| FCD-GW-08 | 100 deleted rows + 1 live, default page | pass |
| FCD-GW-11 | 101 rows, default limit | pass |
| FCD-GW-12 | 101 rows, `limit=101` | pass |
| FCD-GA-13 | 100 deleted + 100 inactive + 1 live, default call | pass |
| FCD-GA-14 | 101 rows, default limit | pass |
| FCD-GA-15 | 101 rows, `limit=500` | pass |
| FCD-GA-26 | **non-strict** xfail BUG-706 (`strict=False`) | xfail; fails in Then 1 with `['bolt', 'apple'] == ['Banana', 'bolt']`, the value the card predicts |
| FCD-SD-09 | savepoint, commit spy, three follow-up lookups | pass |
| FCD-RS-07 | three follow-up lookups after the restore | pass |
| FCD-RS-10 | savepoint, commit spy, one follow-up lookup | pass |
| FCD-RS-14 | follow-up `machine_dao.get_by_factory`; unchanged(MA3) | pass |
| FCD-RS-15 | Given runs `dao.soft_delete`; BEFORE snapshot | pass |
| FCD-RS-16 | the same for an inactive factory | pass |

Placement: each sits in card order inside the full-run block of its section (GW-08 after GW-07, GW-11 / GW-12 after GW-10, GA-13 … GA-15 after GA-12, GA-26 after GA-24, SD-09 after SD-08, RS-07 / RS-10 after RS-06, RS-14 … RS-16 after RS-12). The 17 trial tests and the exemplars stay where they were, in front of that block.

## Tool observation — FCD-INH-06 was hand-written because of a runner false rejection
The card's When is `dao.update(db, db_obj=F1, obj_in=FactoryUpdate(name=None, abbreviation="U2"))`. The runner's check "every standing row the card names must be used" read the abbreviation text `"U2"` as the profile U2 and rejected the faithful test: *"The card names U2, but the test never uses `u2`."* (confirmed at the time by calling `static_check` on the hand-written test). The test was therefore written by hand as a seventh exemplar (not shown in the sheet); the tool skipped the card because its ID was already in the file. **The false rejection has since been fixed in the runner (P20)**, so a card of this shape no longer needs to be hand-written; the test stays as it is.

## Local-coder run (Step C)
- Model: Qwen3.6-35B-A3B Q4_K_M (`Qwen_Qwen3.6-35B-A3B-Q4_K_M.gguf`), n_ctx 16,384, thinking off. Report: `factory.local-run.json`. An as-delivered copy of the test file is kept in the session scratchpad for the verifier.
- **88 cases sent (17 in the trial, 71 in the full run): 79 accepted on the first attempt, 9 on the second, 0 handed back (escalated).**
- The nine second attempts, all rejected by the tool for a correct reason; root cause of all nine: the model.

  | Card | Rejection of the first attempt |
  |---|---|
  | FCD-GW-25 | fixture `u1` used but not in the argument list |
  | FCD-GW-01 | fixture `w2` used but not in the argument list |
  | FCD-GA-01 | fixture `w2` used but not in the argument list |
  | FCD-RS-13 | `written(db) == before` with both sides taken after the When call |
  | FCD-SD-03 | `before_f1` assigned but never used (a snapshot the card does not ask for) |
  | FCD-RS-06 | `before_fx` assigned but never used |
  | FCD-INH-05 | `before_f1` assigned but never used |
  | FCD-INH-07 | `before_f1` assigned but never used |
  | FCD-RS-18 | the test ran and failed; it must pass |

- No escalation, so no root-cause entry for one. The helper sheet was not changed during or after the run.
- The two shapes the designer flagged worked for the local model as they are: the BUG-100 recipe cards (GW-21, GW-23, GW-24) and the "loaded first" card (RS-09).
- **Edits to local-written tests at finishing: none.** `ruff check` (project configuration), `ruff --select F,E9,F841,F811` and an AST pass (unused fixture arguments, unused local names, `# Then N` numbering, one test per case ID) found nothing to clean, so not one character of a local-written test was changed. One cosmetic oddity was left in place: a blank line after the docstring of FCD-INH-01.

## xfail location check (`--runxfail -rf`)
| Card | Author | Card says | Fails on (when it fails) | Verdict |
|---|---|---|---|---|
| FCD-GW-22 | exemplar | Then 2 | Then 2, `ids(result) == [f1.id, f2.id]` got `[F2, F1]` | right line — **but does not fail in every run** (DISCREPANCY-1) |
| FCD-GW-23 | local | Then 2 | Then 2, `[F2] == [F1]` | right line — **but does not fail in every run** |
| FCD-GW-24 | local | Then 2 | Then 2, `[F1] == [F2]` | right line — **but does not fail in every run** |
| FCD-GA-24 | local | Then 2 | Then 2, `['Zulu', 'bolt', 'apple', 'Banana'] == ['apple', 'Banana', 'bolt', 'Zulu']` | right line, right reason |
| FCD-GA-25 | local | Then 2 | Then 2, ordered ids differ at index 0 | right line, right reason |
| FCD-GA-26 | claude | Then 1 | Then 1, `['bolt', 'apple'] == ['Banana', 'bolt']` | right line, right reason |
| FCD-RS-19 | local | Then 1 | Then 1, `DID NOT RAISE IntegrityError` (Then 2 – 5 have never executed) | right line, right reason |
| FCD-RS-20 | local | Then 1 | Then 1, `DID NOT RAISE IntegrityError` (Then 2 – 5 have never executed) | right line, right reason |

No xfail test fails on a line other than the one its card names.

## Discrepancies
| ID | Case | Designed | Actual | Evidence | Likely cause |
|---|---|---|---|---|---|
| DISCREPANCY-1 (`flaky`) | FCD-GW-22 (exemplar), GW-23, GW-24 (local) | strict xfail BUG-100, failing in Then 2 | xfail in some runs, **XPASS (strict → failed)** in others; the three do not always flip together | Nine whole-file runs after Step D: `100 passed, 8 xfailed` three times; `2 failed (GW-22, GW-24), 100 passed, 6 xfailed` twice; `3 failed, 100 passed, 5 xfailed` four times. With `--runxfail`: 6 failures once (GW-23 failing in Then 2), 5 failures four times (none of the three failing). The three tests alone (`-k "gw_21 or gw_22 or gw_23 or gw_24"`), six runs: all three XPASS every time. | The recipe needs the UPDATE of "Zulu" to put the new row version physically **behind** "apple". That holds only while the table is appended to. `pg_stat_user_tables` for `factories` in `marker_test` showed 0 live rows, 3,614 dead rows, 32 pages and an autovacuum during this session: every test's rows are rolled back and stay behind as dead rows, autovacuum frees them, and from then on new rows and new row versions are put into freed places, so "Zulu" can stay in front of "apple". The six bulk cards added at Step D (about 900 rolled-back factory rows per run) make the table reach that state much sooner than the 95 tests before them did, but the dependence is in the recipe, not in those tests. BUG-100 itself is still present (the code has no `ORDER BY`); what is unreliable is the proof. |

Nothing was changed for it: the three tests are not mine to edit (one exemplar that the sheet shows verbatim, two local-written), the cards' Expect lines belong to the designer, and loosening a strict xfail requires changing the card in the same step. **For the designer / reviewer:** either make the three cards non-strict (as FCD-GA-26 is, for the same reason), or replace the recipe with one that does not depend on where the database puts a row version. Until then the file can go red on these three tests without any change to the code. The same accident is possible in principle for the strict BUG-706 cards FCD-GA-24 and GA-25 (they need the physical order to differ from the name order); they failed as designed in every run here.

## Coverage
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_factory.py -q -p no:cacheprovider --cov=app.dao.factory --cov-branch --cov-report=term-missing

Name                 Stmts   Miss Branch BrPart  Cover   Missing
app\dao\factory.py      27      0      0      0   100%
```
None — 100% line and branch coverage (27 statements, no branches in the module). No uncovered line to classify.

## Mechanical checks
- `ruff check tests/unit/dao/test_factory.py` — all checks passed. `ruff check --select F,E9,F841,F811` — all checks passed (the import `InvalidRowCountInResultOffsetClause`, unused after the trial, is now used by FCD-GW-20 / GA-23).
- AST pass over every `test_*` function: no unused fixture argument, no unused local name, `# Then N` comments numbered 1 … n in order in every test, 108 case IDs in the cases file = 108 tests, none missing, none twice.
- No test errors (setup or collection) in any run.

## Scaffold checks (run once in a throwaway probe file in the session scratchpad; everything rolled back)
| Question | Result |
|---|---|
| Machine and section rows insertable with the Conventions columns only? | Yes. `created_by` of both is NULL; `snap` shows 16 machine columns and 12 section columns. `soft_delete` of the factory leaves both snapshots equal. |
| BUG-100 recipe (FCD-GW-21 … GW-24) | Held when the scaffold was written: after `f1.abbreviation = "ZX"` + flush the list was `[F2, F1]`. **No longer reliable** — see DISCREPANCY-1. |
| BUG-706 (FCD-GA-24, GA-25) | The five names come back in insertion order `['Zulu', 'bolt', 'apple', 'Bolt', 'Banana']`; GA-25 fails in Then 2. |
| BUG-895 (FCD-RS-19, RS-20) | `restore` of a deleted "Main Plant" next to a live "main plant" raises nothing; the test fails in Then 1 with `DID NOT RAISE IntegrityError`. |
| FCD-SD-12 (`deleted_by=MISSING`) | `IntegrityError`, `.orig` a `ForeignKeyViolation` naming `factories_deleted_by_fkey`; after the savepoint rollback the row is unchanged, live, `updated_at None`. |
| FCD-INH-02, INH-03, INH-04 | `NotNullViolation` naming `workspace_id` / `abbreviation`, `ForeignKeyViolation` naming `factories_workspace_id_fkey`; no factory saved. FCD-INH-01: `created_by None`, `updated_at None`, `is_active True`. |
| FCD-RS-08 / RS-09: does the call issue an UPDATE without the `db.refresh` line? | **No — not in this scaffold.** A factory built by `mk_factory`, flushed and passed straight to `restore` also keeps `updated_at None`. The cards' remark "(Without this step the call would issue an UPDATE.)" is not true for rows built this way; the tests run `db.refresh` as the card orders and pass, but the line does not change the outcome. For the describer / designer, not a discrepancy of a Then line. |

## Factories added
None (`tests/unit/factories.py` is unchanged).

## Notes for maintainers
- **DISCREPANCY-1 first**: a red run with only FCD-GW-22 / GW-23 / GW-24 as `XPASS(strict)` is the flaky recipe, not a fixed bug. Check `app/dao/factory.py` for an `ORDER BY` before removing a marker.
- When BUG-100 is really fixed, FCD-GW-22 … GW-24 XPASS in every run → remove the markers; BUG-706 → FCD-GA-24, GA-25 (GA-26 is non-strict and passes silently — remove its marker too); BUG-895 → FCD-RS-19, RS-20, and FCD-GA-25 can then no longer be set up (Spec gap 6 of the cases file). Then 2 – 5 of FCD-RS-19 / RS-20 have never run; read them against the cards when the bug is fixed.
- The bulk cards insert about 900 factory rows per run (rolled back). They take the file from about 2 s to about 3 s and leave dead rows behind in `marker_test`.
- FCD-SD-09 / RS-10 spy on `db.commit` with `wraps=`; if the DAO is ever changed to commit, Then 8 / Then 7 fail and the conftest rollback no longer protects the database for that test.
- The cards rest on the answers P1, P2, P3, Q1 – Q4, all accepted on 2026-10-16 (decided by Claude under the reviewer's delegation); the cases file's Reviewer summary lists the cards behind each.

## Revision history
- Steps A, B and the trial of Step C: scaffold, 7 exemplars, helper sheet, 17 trial cards (24 tests).
- Step C full run: 71 more local-written tests (95 tests; `88 passed, 7 xfailed`).
- Step D (this revision): the 13 `Author: claude` cards; imports `patch` and `machine_dao`; header docstring mentions the `# [claude]` marker; no edit to any local-written test or exemplar; xfail location check, coverage, three-plus stability runs; DISCREPANCY-1 recorded.

## Fix round 0 (main session, after Step D, before verification)
- DISCREPANCY-1 resolved by a card change, not by bending a test: the five order cards that rest on physical row order — FCD-GW-22, GW-23, GW-24 (BUG-100) and FCD-GA-24, GA-25 (BUG-706) — are now `xfail (non-strict)` in the cases file and in the tests, like GA-26. Only the markers changed; no test body was touched.
- Two strict cards added, both `Author: claude`, with tests: FCD-GW-26 and FCD-GA-28 record the SQL the session sends and assert the one SELECT has an `ORDER BY`. They do not depend on row order and are the alarm for the fix of BUG-100 / BUG-706. Both fail today on Then 2.
- Result now: 110 tests = 7 exemplars + 88 local + 15 Claude · 100 passed · 10 xfailed (4 strict, 6 non-strict; the non-strict ones may show as xpassed). Three whole-file runs: green each time (10 xfailed; 8 xfailed + 2 xpassed; 7 xfailed + 3 xpassed).
- When BUG-100 or BUG-706 is fixed, the strict recorder test XPASSes and fails the run: remove its marker and the markers of that bug's non-strict tests.

