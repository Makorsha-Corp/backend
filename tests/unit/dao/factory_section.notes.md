# Execution notes — `app/dao/factory_section.py`

> **State: Step D finished; revision 2 (2026-10-16) added.** All 95 cards have a test; nothing is left to write.
> Cases: `tests/unit/dao/factory_section.cases.md` (revision 2, READY, 95 cases; the spec is APPROVED 2026-10-16) · Tests: `tests/unit/dao/test_factory_section.py` · Source commit: e48a092
> Result: 95 tests for 95 cases = 6 exemplars + 67 local + 22 Claude. **82 passed · 13 xfail-marked (8 strict, 5 non-strict) · 0 discrepancies · 0 errors** — every whole-file run so far printed `82 passed, 12 xfailed, 1 xpassed` (before revision 2: `79 passed, …`; the one xpass is the non-strict FSD-INH-18). Line and branch coverage 100%.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_factory_section.py -q -p no:cacheprovider`

## How the tests are built
- **Local-coder mode.** The scaffold and six exemplars are hand-written; tests under a `# [local-coder] <ID>` comment were written by the local model from one card each, with `factory_section.helpers.md` as its only view of the file; tests under a `# [claude] <ID>` comment are the 19 `Author: claude` cards, written by hand at finishing (Step D).
- **Clock.** The fixture `clock` puts a `MagicMock(return_value=NOW)` in place of `app.dao.factory_section.utcnow`; the autouse fixture `standing_rows` requests it, so it is patched in every test. It is a fixture of its own so that FSD-RS-05 can request `clock` and compare `clock.call_count` before and after the When. It is not named in the helper sheet. Nothing else is mocked; the commit spy of FSD-SD-08 / RS-10 wraps the real `db.commit` and does not replace it.
- **Constants:** `dao` (= `factory_section_dao`, a module-level name, not a fixture), `MISSING`, `T0`, `NOW`.
- **Fixtures (the nine standing rows), each depending on the one before it so the ids rise in the Conventions order:** `w1`, `w2`, `u1`, `u2` (from `tests/unit/factories.py`), `f1` ("Main Plant" / "MP", W1), `f2` ("North Yard" / "NY", W1), `f9` ("Far Depot" / "FR", W2), `fd` ("Old Plant" / "OP", W1, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`, `is_active True`), `fi` ("Idle Plant" / "IP", W1, `is_active False`). `standing_rows` (autouse) makes all nine present in every test. No section, machine or assignment is a standing row. The fixture names matter to the runner: its "a standing row the card names must be used" check maps `F1` → `f1` and so on (only names of the form letters + digits; `FD` and `FI` are not checked by it).
- **Builders (fixtures, keyword-only, flush before returning):**
  - `mk_section(*, name, deleted=False, **columns)` — the Conventions "section" (`workspace_id W1.id`, `factory_id F1.id`, `created_by U1.id`, `updated_by None`, `updated_at None`, `is_active True`, not deleted, `created_at` left to the database). `deleted=True` is the Conventions word "deleted" (`is_deleted True`, `deleted_at T0`, `deleted_by U1.id`; `is_active` untouched).
  - `mk_machine(*, of, name)` — "machine of F": workspace and factory id from the factory passed as `of`.
  - `mk_assignment(*, of, to)` — "assignment of M to S": workspace from the machine. (Unlike the machine module's builder it does not expire the session; these Conventions do not ask for it.)
  - `of` and `to` are the cards' own words, which the runner's keyword check needs.
- **Reading helpers (plain functions, no expected values inside):** `ids(result)`, `names(result)`, `by_id(result, row)`, `reread(db, row)` (expires, then SELECT by id; any of the four models, so also "re-read FD" / "re-read A1" / "re-read the returned row"), `snap(db, row)` (unchanged(X): every column straight from the table; section, factory, machine or assignment), `count_rows(db, "<table name>")`, `written(db)` (nothing written: the counts of `factory_sections`, `factories`, `machines`, `machine_section_assignments`).
- **Database-error cards** (`raises: DataError`, `raises: IntegrityError`) wrap the call in `db.begin_nested()` inside `pytest.raises(...) as exc`.
- **Added at Step D (for the `Author: claude` cards only). Three imports, no new helper function and no new fixture, so `factory_section.helpers.md` is unchanged:**
  - `from unittest.mock import patch` — the commit spy of "rolled back": `with patch.object(db, "commit", wraps=db.commit) as commit_spy:`, then `sp = db.begin_nested()` directly before the When call, the in-session checks, `sp.rollback()`, the "after the savepoint rollback" checks, and `commit_spy.call_count == 0` (FSD-SD-08, RS-10).
  - `from sqlalchemy import event` — the statement recorder, written inline as in FCD-GW-26: a `record` function appended to `statements`, `event.listen(db.get_bind(), "before_cursor_execute", record)` around the When only (`try` / `finally: event.remove(...)`). The `statement:` line is two asserts: exactly one recorded statement starts with `SELECT`, and it contains `ORDER BY` (FSD-GF-36, INH-19).
  - `from app.dao.machine import machine_dao` — the Conventions "Machine lookup" (FSD-RS-13).
  - "FD made live again" is written inline, on the standing row: `fd.is_deleted = False`, `fd.deleted_at = None`, `fd.deleted_by = None`, `db.flush()`. In FSD-GF-19 it is the last Given step (after the BEFORE snapshot of SH, before the "nothing written" counts); in FSD-RS-17 it stands under `# Then 3`, between the When and that line's assert, as the card orders.
  - Clock spy (FSD-RS-05): `calls_before = clock.call_count` after the Given row, `assert clock.call_count == calls_before` under Then 3.
  - Bulk rows are built with `mk_section` in a loop or a list comprehension that keeps the ids (`all_ids = [mk_section(name=f"N{k:03d}").id for k in range(1, 102)]`), one flush per row, in the order the card gives — no bulk helper.
  - "every column except `updated_at` equals BEFORE" (FSD-RS-18, RS-19): `before = snap(db, s1)` after the first Given row and before the Given `dao.soft_delete(...)`; after the call `reread`, then `snap` again and compare the two dicts without the key `updated_at`.
- **Exemplars (hand-written, 6, all printed verbatim in the sheet, none `Author: claude`):**

  | Card | Shape it shows |
  |---|---|
  | FSD-GF-04 | plain lookup; a section with two columns after "but" (`factory_id=f9.id, workspace_id=w2.id`); a Given row without a variable; `w2.id` asserted |
  | FSD-GF-10 | strict xfail BUG-905 (fails in Then 2, as the card says); `deleted=True` |
  | FSD-GF-30 | `raises: DataError` + `begin_nested`; nothing written; unchanged |
  | FSD-SD-06 | `soft_delete`; machine and assignment builders; unchanged of an assignment, a machine and the standing row F1; re-read of three different rows; two `count:` lines; two values on one re-read line; `u2.id` |
  | FSD-RS-02 | `restore`; `created_before`; `w1.id`, `u1.id`, `f1.id` asserted |
  | FSD-INH-09 | inherited `update` with a schema; `f2.id` |

  All six pass the runner's `static_check`. Every `raises:` card of this module has "nothing written" or "unchanged", so there is no error exemplar without a snapshot.
- **Helper sheet:** `factory_section.helpers.md`, 10,200 characters. A full prompt (system + sheet + Conventions + the longest trial card) is about 20,900 characters; the runner's own estimate stays far below n_ctx 16,384.

## Who wrote what (95)
| Author | Count | Cards |
|---|---|---|
| Hand-written exemplars (Steps A / B) | 6 | FSD-GF-04, GF-10, GF-30, SD-06, RS-02, INH-09 |
| Local model (Step C; the trial and the full run) | 67 | every card not named in the other two rows |
| Claude at finishing (Step D, `# [claude] <ID>`) | 19 | FSD-GF-11, GF-19, GF-22, GF-23, GF-32, GF-33, GF-34, GF-35, GF-36, SD-08, RS-05, RS-10, RS-13, RS-16, RS-17, RS-18, RS-19, INH-18, INH-19 |
| Claude, revision 2 (2026-10-16, `# [claude] <ID>`, added after verification) | 3 | FSD-GF-39, GF-40, GF-41 |

The 19 + 3 = 22 are the cards with an `- **Author:** claude` line in the cases file (checked by grep).

## Step D — the 19 `Author: claude` cards
All 19 are written as designed; none had to be bent and none is a discrepancy.

| Card | Shape | Outcome |
|---|---|---|
| FSD-GF-11 | 100 deleted sections + 1 live, default page; **strict** xfail BUG-905 | xfail; fails in Then 1: 100 ids against `[L.id]` |
| FSD-GF-19 | FD made live again in the Given; BEFORE snapshot of SH taken before that step | pass |
| FSD-GF-22 | 101 sections, default limit | pass |
| FSD-GF-23 | 101 sections, `limit=101` | pass |
| FSD-GF-32 | **non-strict** xfail BUG-903, four names | xfail; fails in Then 2 with the insertion order `['Zulu', 'bolt', 'apple', 'Banana']`, the value the card predicts |
| FSD-GF-33 | **non-strict** xfail BUG-903, five names with "bolt" / "Bolt" | xfail; fails in Then 2 with the ids in insertion order |
| FSD-GF-34 | **non-strict** xfail BUG-903, `skip=1, limit=2` | xfail; fails in Then 1 with `['bolt', 'apple']`, the value the card predicts |
| FSD-GF-35 | **non-strict** xfail BUG-903, `skip=0, limit=2` | xfail; fails in Then 1 with `['Zulu', 'bolt']`, the value the card predicts |
| FSD-GF-36 | statement recorder; **strict** xfail BUG-903 | xfail; fails in Then 2 on the `ORDER BY` assert (one SELECT was recorded, it ends `LIMIT … OFFSET …`) |
| FSD-SD-08 | savepoint, commit spy, follow-up `get_by_id_and_workspace` | pass |
| FSD-RS-05 | clock spy (`clock.call_count`) | pass |
| FSD-RS-10 | savepoint, commit spy, follow-up `get_by_factory` (`listed`) | pass |
| FSD-RS-13 | Given runs `dao.soft_delete`; BEFORE_M / BEFORE_A snapshots before it; follow-up `machine_dao.get_by_section` | pass |
| FSD-RS-16 | follow-up `get_by_factory` after the restore; **strict** xfail BUG-904 | xfail; fails in Then 3: one row against `[]` |
| FSD-RS-17 | FD made live again between the When and the Then 3 assert | pass |
| FSD-RS-18 | Given runs `dao.soft_delete`; BEFORE snapshot | pass |
| FSD-RS-19 | the same for an inactive section | pass |
| FSD-INH-18 | **non-strict** xfail BUG-100; Given `s1.updated_by = u2.id` + `db.flush()` | **xpass in every run** (see "Anything odd") |
| FSD-INH-19 | statement recorder on `get_by_workspace`; **strict** xfail BUG-100 | xfail; fails in Then 2 on the `ORDER BY` assert |

Placement: each sits in card order inside the full-run block of its section (GF-11 between GF-09 and GF-13; GF-19 after GF-18; GF-22 / GF-23 after GF-21; GF-32 … GF-36 after GF-31; SD-08 after SD-07; RS-05 after RS-04; RS-10 after RS-09; RS-13 after RS-11; RS-16 … RS-19 after RS-14; INH-18 / INH-19 after INH-16, at the end of the file). The exemplars and the 20 tests kept from the trial stay where they were, in front of that block.

## Local-coder run (Step C)
- Model: Qwen3.6-35B-A3B Q4_K_M (`Qwen_Qwen3.6-35B-A3B-Q4_K_M.gguf`), n_ctx 16,384, thinking off. Report: `factory_section.local-run.json` (totals: 2,334.6 s, 415,300 prompt tokens, 15,417 completion tokens). An as-delivered copy of the test file (`test_factory_section.asdelivered.py`) is kept in the session scratchpad for the verifier. Note that `--ids` takes one comma-separated value.
- **67 cases, including the 21 of the trial: 62 accepted on the first attempt (the tool's count), 5 on the second, 0 handed back (escalated).**
- The five second attempts, all rejected by the tool for a correct reason; root cause of all five: the model.

  | Card | Run | Rejection of the first attempt |
  |---|---|---|
  | FSD-GF-37 | trial | the test ran and failed (M1 assigned twice; the database refused it — unique `machine_id`); it must pass |
  | FSD-GF-38 | trial | fixture `u1` used but not in the argument list |
  | FSD-SD-02 | trial | `before` assigned but never used (a snapshot the card does not ask for) |
  | FSD-RS-08 | trial | `before` assigned but never used |
  | FSD-GF-17 | full run | "Then 5 lists 2 checks (`deleted_at is None`, `deleted_by is None`) but there is only 1 assert(s) after `# Then 5`." (the per-line assert count check, P21) |

- **FSD-GF-17 — unfaithful in the trial, caught by the tool in the full run.** In the trial the model's test for this card (ten Then lines, three of them re-reads of SH) asserted only the first of the two values of Then 5 (`deleted_at is None` without `deleted_by is None`). The tool accepted it: the Then block had an assertion and the line holds no quoted value. A sharpened sentence in the sheet ("A line with two values needs TWO asserts, never one: …") did not help — the re-run produced the same test. The unfaithful test was deleted from the file. The runner then got a check that counts, for every Then line, the checks the line lists against the asserts under its `# Then N` comment (**P21**). In the full run the model's first attempt for FSD-GF-17 made the same slip, **was rejected by that check**, and the second attempt was accepted. So the test now in the file is a full-run test; the trial's entry for the card is replaced in the report by this one (attempts 2).
- The other 20 trial tests were read against their cards after the trial and found faithful; the 47 tests of the full run were not read for fidelity at finishing (the verifier's job).
- No escalation, so no root-cause entry for one. Changes to the helper sheet along the way: the one sentence named above, after the trial (10,078 → 10,200 characters). Nothing was changed in the sheet during or after the full run.
- **Edits to local-written tests at finishing: one, cosmetic.** The blank line between the docstring and the first statement of FSD-INH-04 was removed. `ruff check` (project configuration), `ruff --select F,E9,F841,F811` and an AST pass found nothing else to clean; no local-written test was changed in what it builds or asserts (a diff against the as-delivered copy shows that one deleted blank line, the header / import lines, and the 19 inserted blocks — nothing else).

## xfail location check (`--runxfail -rf --tb=short`)
| Card | Author | Card says | Fails on | Verdict |
|---|---|---|---|---|
| FSD-GF-10 | exemplar | Then 2 | Then 2, `ids(result) == [s1.id]` got two ids | right line, right reason |
| FSD-GF-11 | claude | Then 1 | Then 1, `ids(result) == [late.id]` got 100 ids, the first of them D1 | right line, right reason |
| FSD-GF-12 | local | Then 1 | Then 1, `ids(result) == [l1.id]` got two (deleted) ids | right line, right reason |
| FSD-GF-13 | local | Then 1 | Then 1, `result == []` got one row | right line, right reason |
| FSD-GF-15 | local | Then 1 | Then 1, `result == []` got one row | right line, right reason |
| FSD-GF-32 | claude (non-strict) | Then 2 | Then 2, `['Zulu', 'bolt', 'apple', 'Banana'] == ['apple', 'Banana', 'bolt', 'Zulu']` | right line, right reason |
| FSD-GF-33 | claude (non-strict) | Then 2 | Then 2, ids in insertion order, differ at index 0 | right line, right reason |
| FSD-GF-34 | claude (non-strict) | Then 1 | Then 1, `['bolt', 'apple'] == ['Banana', 'bolt']` | right line, right reason |
| FSD-GF-35 | claude (non-strict) | Then 1 | Then 1, `['Zulu', 'bolt'] == ['apple', 'Banana']` | right line, right reason |
| FSD-GF-36 | claude | Then 2 | Then 2, `"ORDER BY" in selects[0].upper()` (the `len(selects) == 1` assert before it holds) | right line, right reason |
| FSD-RS-16 | claude | Then 3 | Then 3, `dao.get_by_factory(...) == []` got one row | right line, right reason |
| FSD-INH-19 | claude | Then 2 | Then 2, `"ORDER BY" in selects[0].upper()` | right line, right reason |
| FSD-INH-18 | claude (non-strict) | Then 2 | did not fail in any whole-file run; the verifier saw it fail on Then 2 (`[S2.id, S1.id] == [S1.id, S2.id]`) under a sequential scan | right line when it fails; fails under a sequential scan only (see "Anything odd") |

No xfail test fails on a line other than the one its card names. No local-written xfail test has a wrong location.

## Coverage
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_factory_section.py -q -p no:cacheprovider --cov=app.dao.factory_section --cov-branch --cov-report=term-missing

Name                         Stmts   Miss Branch BrPart  Cover   Missing
app\dao\factory_section.py      23      0      0      0   100%
```
### Coverage gaps
None — 100% line and branch coverage (23 statements, no branches in the module). No uncovered line to classify.

## Stability
The whole file was run 14 times one after the other (never in parallel): the first run after Step D, ten in a row, the coverage run, and two after the cosmetic edit. **Every run: `79 passed, 12 xfailed, 1 xpassed` — never red.** No strict xfail and no pass card flipped in any run. The one xpass is always FSD-INH-18 (non-strict). The four non-strict BUG-903 cards (FSD-GF-32 … GF-35) xfailed in every run. One further run with `--runxfail`: `12 failed, 80 passed`.

## Anything odd
- **FSD-INH-18 fails only under a sequential scan** (corrected 2026-10-16 from the verifier's finding 5; the earlier "never fails, also when run alone" was wrong). After `S1.updated_by = U2.id` + flush the updated row S1 sits physically behind S2. A sequential scan returns `[S2.id, S1.id]` and the test fails on Then 2 as designed; a bitmap or index scan on the `workspace_id` index returns the rows at their old places, `[S1.id, S2.id]`, and the non-strict test xpasses. Which plan Postgres picks depends on the size of the table file: in a whole-file run the bulk cards (about 300 rolled-back rows) have grown it, so the plan is a bitmap scan and the test xpasses every time; run alone it can go either way (the verifier saw 3 failures in a row right after autovacuum had shrunk the table, then 3 xpasses a few minutes later). Forcing a sequential scan for the whole file gives `79 passed, 13 xfailed` (before revision 2). The card stays non-strict on purpose and is kept: once BUG-100 is fixed it is the only card that tells `ORDER BY id` from another order. The strict alarm for BUG-100 on sections is FSD-INH-19 (statement recorder), which fails as designed in every run.
- FSD-RS-08 / RS-09: the cards' remark "(Without this step the call would issue an UPDATE.)" is not true for rows built by `mk_section` (see Scaffold checks). Not a discrepancy of a Then line.

## Mechanical checks
- `ruff check tests/unit/dao/test_factory_section.py` — all checks passed. `ruff check --select F,E9,F841,F811` — all checks passed (the import `InvalidRowCountInResultOffsetClause`, unused after the trial, is used by FSD-GF-31).
- AST pass over every `test_*` function: no unused fixture argument, no unused local name, `# Then N` comments numbered 1 … n in order in every test, every docstring starts with its case ID, 92 case IDs in the cases file = 92 tests, none missing, none twice. 19 `# [claude]` and 67 `# [local-coder]` markers.
- No test errors (setup or collection) in any run.

## Scaffold checks (throwaway probe in the session scratchpad, run through the `db` fixture; everything rolled back)
| Question | Result |
|---|---|
| Ids of the nine standing rows rise in the Conventions order; FD and FI have the stated columns | Yes. |
| Rows insertable with the Conventions columns only | Yes. Section snapshot has 12 columns, machine 16, assignment 8. `written` = sections, 5 factories, machines, assignments. |
| BUG-905 (FSD-GF-10, GF-11, GF-12, GF-13) | Deleted sections are returned and count toward `limit` / `skip`: GF-12 returns two deleted rows where `[L1.id]` is expected (fails in Then 1). |
| BUG-904 (FSD-GF-15, RS-16) | The live section of FD is returned (fails in Then 1 / Then 3). |
| FSD-GF-31 | `InvalidRowCountInResultOffsetClause`, pgcode `2201X`, "OFFSET must not be negative". |
| FSD-SD-02, SD-13 | `updated_at` is set by the delete, `updated_by` and `created_at` keep their values; `deleted_by None` is stored. |
| FSD-SD-12 | `IntegrityError`, `.orig` a `ForeignKeyViolation` naming `factory_sections_deleted_by_fkey`; after the savepoint rollback the row is unchanged, live, `updated_at None`. |
| FSD-INH-02 … INH-06 | `NotNullViolation` naming `"workspace_id"` / `"factory_id"` / `column "name"`; `ForeignKeyViolation` naming `factory_sections_factory_id_fkey` / `factory_sections_workspace_id_fkey`; nothing written, 0 sections. |
| FSD-INH-07 … INH-10 | As the cards say (a section of W1 pointing at F9 is saved; `name=None` in the schema leaves the name; the dict switches `is_active` off). |
| FSD-RS-14, RS-15 | Assignment, machine, FD and the counts are unchanged by the restore. |
| FSD-RS-08 / RS-09: does the call issue an UPDATE without the `db.refresh` line? | **No — not in this scaffold.** A section built by `mk_section`, flushed and passed straight to `restore` also keeps `updated_at None`. The tests run `db.refresh` as the card orders and pass; the line does not change the outcome. For the describer / designer. |

No card expectation probed disagrees with the code.

## Discrepancies
None.

## Factories added
None (`tests/unit/factories.py` is unchanged).

## Notes for maintainers
- A strict xfail that XPASSes (the run goes red) means the bug is fixed: BUG-905 → FSD-GF-10, GF-11, GF-12, GF-13; BUG-904 → FSD-GF-15, RS-16; BUG-903 → FSD-GF-36, and then remove the markers of the non-strict FSD-GF-32 … GF-35 too (they pass silently); BUG-100 → FSD-INH-19, and remove the marker of FSD-INH-18.
- The recorder cards assert only that the one SELECT has an `ORDER BY`, not its columns (the cases file defers that to the fix).
- The three bulk cards insert about 300 section rows per run (rolled back); the file takes about 3 s.
- FSD-SD-08 / RS-10 spy on `db.commit` with `wraps=`; if the DAO is ever changed to commit, the last Then line fails and the conftest rollback no longer protects the database for that test.
- FSD-RS-20 and FSD-GF-33 can no longer be set up once a unique index on live section names exists (cases file, Spec gaps 5 and 6).
- The cards rest on the answers P1 – P4, Q1, Q2 and the BUG-905 reading, all accepted on 2026-10-16 (decided by Claude under the reviewer's delegation); the cases file's Reviewer summary lists the cards behind each answer.
- FSD-GF-39 / GF-40 (section of W1 naming F9 of W2, R1a) must keep passing after the BUG-904 fix: the fix looks at the factory row for `is_deleted` only, not for its workspace. FSD-GF-41 (`limit=2` with three assignment rows) catches a join to the assignment rows that would use up places in the page.

## Revision history
- Steps A, B and the trial of Step C: scaffold, 6 exemplars, helper sheet, 21 trial cards sent, 20 kept (26 tests; `23 passed, 3 xfailed`). FSD-GF-17 unfaithful and deleted.
- Runner change P21 (per-line assert count check), then the Step C full run: 47 more local-written tests, FSD-GF-17 among them (73 tests; `69 passed, 4 xfailed`).
- Step D (this revision): the 19 `Author: claude` cards; imports `patch`, `event` and `machine_dao`; the header docstring mentions the `# [claude]` marker; one blank line removed in the local-written FSD-INH-04; no other edit to a local-written test or an exemplar; xfail location check, coverage, 14 stability runs (92 tests; `79 passed, 12 xfailed, 1 xpassed`).
- **Revision 2 (2026-10-16, review round delegated to Claude):** cases revision 2 — three new `Author: claude` cards written by hand under `# [claude] <ID>`: FSD-GF-39, GF-40 (`get_by_factory` R1a, new rule from fill-gaps) and FSD-GF-41 (verifier H1). All three pass. No existing test was touched — no local-written body, no exemplar, no marker. Notes corrected: the FSD-INH-18 paragraph in "Anything odd" and its row in the xfail location table (verifier finding 5). Five whole-file runs one after the other: `82 passed, 12 xfailed, 1 xpassed` each time (the xpass is FSD-INH-18); coverage run the same, 100% line and branch; `ruff check` passes.
