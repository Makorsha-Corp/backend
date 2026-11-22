# Verification — `app/dao/factory_section.py`

> **Verdict:** PASS
> Tests: 79 passed · 13 xfail-marked (8 strict, 5 non-strict; printed as `12 xfailed, 1 xpassed`) (reproduced ✅) · coverage 100% branch (23 statements, no branches)
> Mutation: 9 mutants · 9 killed · 0 survived → score 100% (nothing excluded)
> Source commit: e48a092 · Cases revision: none stated (READY on pilot defaults, 92 cases; spec still IN REVIEW)
> **Review round 2026-10-16 (delegated — decided by Claude under the reviewer's delegation):** spec APPROVED (P1–P4, Q1, Q2 and the BUG-905 reading accepted; BUG-905 stays a bug) plus fill-gaps rule `get_by_factory` R1a (filters on the section's own workspace, today and after BUG-904; not a bug, no new ID). Cases revision 2: new cards FSD-GF-39, GF-40 (R1a — closes H2) and FSD-GF-41 (H1: Given of GF-37 with `limit=2`), all `Author: claude`, tests written by Claude, all pass; FSD-INH-18 "Fails today on" reworded (finding 6); notes paragraph on FSD-INH-18 corrected (finding 5); Spec gap 16 records that no second R6 tie-break card is possible. No local-written test body and no marker touched. Five whole-file runs: `82 passed, 12 xfailed, 1 xpassed` each (xpass = non-strict FSD-INH-18).

## Summary
These tests can be trusted. All 92 tests were read against their cards line by line — every Given row and column, the When call and each argument, every numbered Then line and every check a line lists. Nothing was sampled. As a second, independent check a script rebuilt the expected body of each of the 73 vocabulary cards (67 local + 6 exemplars) from the card text and compared it with the test: **0 differences**. The script was shown to report 22 of 22 planted mistakes, the FSD-GF-17 trial slip (second value of a two-value Then line dropped) among them.

- **Local-model tests (67): functional findings in 0 / 67 — 67 of 67 (100%) are right as delivered · cosmetic findings in 29 / 67 tests** (27 names cut by the tool at 70 characters; 3 variable names other than the card's; 4 tests that re-read a row `row` already holds). Counting only what the model itself wrote: 7 / 67 (FSD-RS-04, RS-06, RS-07, RS-09, RS-15, RS-20, RS-22).
- **Claude-written tests (25 = 6 exemplars + 19 `# [claude]`): functional findings in 0 / 25 · cosmetic findings in 4 / 25** (names: FSD-SD-06, RS-13 cut; SD-08, RS-10 reworded).
- **The one edit after delivery — confirmed.** Against `test_factory_section.asdelivered.py`: 66 of the 67 local tests and all 6 exemplars are identical line for line (comment, decorators, signature, docstring, body); FSD-INH-04 differs by one deleted blank line after the docstring and nothing else. The 19 tests not in the copy are exactly the 19 `# [claude]` ones; the scaffold differs by the header docstring and three imports (`patch`, `event`, `machine_dao`); the order of the delivered tests is unchanged.
- **Stability:** 11 whole-file runs with today's code (6 plain, 1 with coverage, 1 with a read-only probe, 3 with the planner forced to one scan type each), plus one last plain run: never red. No strict xfail and no pass card rests on physical row order (argued per card below, and shown by the three forced-plan runs).
- **FSD-INH-18** does fail today — when the planner reads the table with a sequential scan. In a whole-file run it never does, for a reason that is now known (see "FSD-INH-18" below). Keep the card; reword two sentences of it.
- **Recorder cards:** FSD-GF-36 / INH-19 fail today on the `ORDER BY` assertion of Then 2 (the `len(selects) == 1` assert before it holds) and pass against a scratch reference that adds an `ORDER BY`. With the markers on, that reference turns the run red through exactly these two, so the alarm works.
- **Never-executed Then lines:** there are none in this module — each of the 13 xfail cards fails on its last Then line. All 13 were still run in full against scratch references of the four bugs: 13 pass, each bug's cards only with that bug's fix.
- **Hand-made variants** of the code (54, things the mutation tool does not make): 52 caught, among them a `commit()` in `soft_delete` (FSD-SD-08 alone) and in `restore` (FSD-RS-10 alone), the clock read in `restore` (FSD-RS-05 alone), and a cascade to assignments or machines from either writer. The two not caught are small gaps with no card (fix list 1 and 2); neither is a mutant of the tool and neither blocks PASS.

Limit of this verdict: the spec is IN REVIEW on pilot defaults. If the reviewer changes P1 – P4, Q1, Q2 or the BUG-905 reading, the cards listed in the cases file's Reviewer summary change with them.

## Findings
None functional. Cosmetic only — none blocks PASS, all optional:

| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | Naming (local) — COSMETIC | FSD-GF-03, GF-16, GF-17, GF-20, GF-37, SD-01, SD-10, SD-12, RS-07, RS-08, RS-09, RS-14, RS-15, RS-20, RS-21, RS-22, INH-01 … INH-08, INH-14, INH-16, INH-17 (27 tests) | Test name cut at 70 characters, so it does not carry the whole title. The docstring carries the full ID and title in all 92 tests. Made by the tool, not by the model. | `test_fsd_rs_15__a_deleted_section_of_a_soft_deleted_factory_is_restored_and_the` | optional — tool (`tests/unit/_tools/local_coder.py`) |
| 2 | Naming (local) — COSMETIC | FSD-RS-07 (`sx` for the card's SXI), FSD-RS-15 (`sh` for SHX), FSD-RS-09 (`before` for the sheet's `before_si`) | Variable names other than the card's / the helper sheet's. Each is assigned from the right builder or `snap(db, …)` at the right place and used in the right assertions. | `sh = mk_section(name="Old Line", factory_id=fd.id, deleted=True)` | optional — executor |
| 3 | Style (local) — COSMETIC | FSD-RS-04 (twice), RS-06, RS-20 (twice), RS-22 | `row = reread(db, sx)` repeated under a later Then line although `row` already holds that row (the sheet says later lines reuse `row`). Same row, same values; one extra SELECT each. | lines 1606, 1609, 1647, 1913, 1922, 1970 | optional — executor |
| 4 | Naming (claude) — COSMETIC | FSD-SD-06 (exemplar), RS-13: cut at 70 characters. FSD-SD-08, RS-10: name says "visible in the session", the title "visible to the by-id lookup / the by-factory list in the session" | Four hand-written names do not carry the title; the other hand-written names are complete (up to 112 characters), so the file is not uniform. | `test_fsd_sd_08__…_visible_in_the_session_undone_by_a_rollback` | optional — executor |
| 5 | Documentation (claude) — COSMETIC | `factory_section.notes.md`, "Anything odd" and the xfail location table | "FSD-INH-18 never fails today … and when run alone" is true only while the table is large enough for the planner to choose a bitmap scan. Run alone here it failed three times in a row (Then 2, `[S2.id, S1.id]`) and xpassed three times a few minutes later. "The cause was not looked into" — it is given below. | section "FSD-INH-18" | optional — executor |
| 6 | Documentation — COSMETIC | `factory_section.cases.md`, FSD-INH-18 | The Given remark "(This usually moves S1 physically behind S2 in the table.)" is true, but the conclusion in "Fails today on" ("the updated row S1 usually comes back after S2") holds only under a sequential scan; in a whole-file run the list is `[S1.id, S2.id]` every time. | section "FSD-INH-18" | optional — case designer |

Checked for and **not** found, in all 67 local tests (by reading and by the rebuild script):
- a missing, extra or reordered Given row; a wrong or missing column — `factory_id=f2.id` / `f9.id` / `fd.id` / `fi.id`, `workspace_id=w2.id`, `is_active=False`, `updated_by=u1.id` / `u2.id`, `deleted=True` (never expanded by hand, never added to a live row, never left off a deleted one); a wrong `of=` / `to=` on a machine or assignment; a wrong name (compared as Python values);
- **a value or row swapped with another of the same kind** — looked at in particular on the cards that name two factories, two workspaces or two users: FSD-GF-01, GF-02, GF-03, GF-05, GF-15, GF-16, GF-17 (both sections in FD, the second inactive), GF-18 (FI, not FD), GF-20, GF-21, GF-38, SD-02 (`updated_by U1`, `deleted_by U2`), SD-09, SD-10 (`deleted_by == u2.id` on SH, `== u1.id` on FD), SD-11, RS-03 (`updated_by U2`, asserted `u2.id`), RS-11, RS-12 (SX4 in F2), RS-15, RS-22, INH-07 (W1 with F9), INH-11, INH-16, INH-17: none;
- the standing rows: no test builds a factory, workspace or user; each test requests exactly the standing rows it uses (no unused argument in any of the 92 tests);
- literal-code Given lines: `db.refresh(s1)` / `db.refresh(si)` (FSD-RS-08, RS-09) stand directly after the row and before the snapshot;
- a changed, dropped or added When argument (`skip=0`, `limit=0`, `limit=-1`, `skip=-1`, `skip=5`, `factory_id=0`, `MISSING`, `deleted_by=None`, `deleted_by=MISSING`, the dict and schema arguments of the inherited calls, `dao.get(db, <id>)` positional);
- a skipped Then line, **a Then line with two (or three) values and fewer asserts** (32 such lines in the local cards, FSD-GF-17 Then 4, 5, 8 among them; FSD-INH-01 Then 2 has its three), an assertion under the wrong `# Then N`, or one weaker than the card: `sorted(...)`, `set(...) <=`, `len`, `in [...]` occur only where the card itself writes them; `updated_at` is asserted only as `is None` / `is not None`, on the side the card says;
- write cards: every re-read goes through `reread(db, …)` of the row the line names (expires first; the session has `autoflush=False`, so a missing flush shows — see the `no flush` variants); every "unchanged" / "nothing written" snapshot is taken after the last Given line and before the call, and of the row the Then line names; no snapshot the card does not ask for;
- swallowed failures or extra mocks: `pytest.raises` only on `raises:` cards (7 local), with the card's type, around `db.begin_nested()`; no `try`, nothing patched in any local test.

The 25 Claude-written tests were read the same way: no functional finding. Points checked: the bulk loops build exactly the card's names, counts and order (FSD-GF-11 `f"Old {k:03d}"` for 1 … 100, all deleted, then "Late"; GF-22 / GF-23 `f"N{k:03d}"` for 1 … 101, ids kept in order); FSD-GF-19 takes BEFORE after the two rows and before "FD made live again", and the "nothing written" counts after it; FSD-RS-17 makes FD live between the When and the Then 3 assert and re-reads SHX again for Then 4; FSD-SD-08 / RS-10 open the savepoint directly before the call, run the in-session checks before `sp.rollback()` and the others after it, and wrap `db.commit` with `wraps=` (it stays callable); FSD-RS-05 notes `clock.call_count` after the Given row and compares after the call; FSD-RS-13, RS-18, RS-19 take their snapshots before the Given `dao.soft_delete(...)`; RS-18 / RS-19 compare every column except `updated_at`; the `try / finally` of FSD-GF-36 / INH-19 only removes the listener and swallows nothing.

### xfail tests
| Card | Author | Marker | Fails on (`--runxfail`) | Verdict |
|---|---|---|---|---|
| FSD-GF-10 | exemplar | strict BUG-905 | Then 2, `[S1, SX] == [S1]` | right line, right reason |
| FSD-GF-11 | claude | strict BUG-905 | Then 1, 100 ids `== [L.id]` | right line, right reason |
| FSD-GF-12 | local | strict BUG-905 | Then 1, two (deleted) ids `== [L1.id]` | right line, right reason |
| FSD-GF-13 | local | strict BUG-905 | Then 1, one row `== []` | right line, right reason |
| FSD-GF-15 | local | strict BUG-904 | Then 1, one row `== []` | right line, right reason |
| FSD-RS-16 | claude | strict BUG-904 | Then 3, one row `== []` | right line, right reason |
| FSD-GF-32, GF-33 | claude | non-strict BUG-903 | Then 2 (`['Zulu', 'bolt', 'apple', 'Banana'] == ['apple', 'Banana', 'bolt', 'Zulu']`; ids differ at index 0) | right line, right reason |
| FSD-GF-34, GF-35 | claude | non-strict BUG-903 | Then 1 (`['bolt', 'apple'] == ['Banana', 'bolt']`; `['Zulu', 'bolt'] == ['apple', 'Banana']`) | right line, right reason |
| FSD-GF-36 | claude | strict BUG-903 | Then 2, `'ORDER BY' in 'SELECT … FROM FACTORY_SECTIONS WHERE … LIMIT … OFFSET …'` | right line, right reason; `len(selects) == 1` holds |
| FSD-INH-18 | claude | non-strict BUG-100 | Then 2 when it fails, `[S2.id, S1.id] == [S1.id, S2.id]` (line 2177) | right line; fails under a sequential scan only |
| FSD-INH-19 | claude | strict BUG-100 | Then 2, the `ORDER BY` assertion | right line, right reason |

No local-written xfail test fails on a line other than its card's.

**Against scratch references** (`DAOFactorySection` patched in the test process by a pytest plugin in the scratchpad; `app/` untouched). The 13 xfail tests, `--runxfail`:

| Reference | BUG-905: GF-10 … GF-13 | BUG-904: GF-15, RS-16 | BUG-903: GF-32 … GF-35 | GF-36 | INH-18 | INH-19 |
|---|---|---|---|---|---|---|
| today's code | fail | fail | fail | fails | passes (bitmap scan) / fails (sequential scan) | fails |
| `is_deleted = false` in the query | **pass** | fail | fail | fails | — | fails |
| join to `factories`, `factories.is_deleted = false` | fail | **pass** | fail | fails | — | fails |
| `ORDER BY lower(name), id` | fail | fail | **pass** | **passes** | — | fails |
| `get_by_workspace` with `ORDER BY id` | fail | fail | fail | fails | **passes** | **passes** |
| all four fixes | pass | pass | pass | passes | passes | passes |
| all four fixes, whole file | 92 passed — every pass card still passes, so no Given collides with a fix | | | | | |
| all four fixes, markers left on (normal run) | the 8 strict tests `XPASS(strict)` → run red; the 5 non-strict xpassed | | | | | |
| one fix, markers on | red through exactly that bug's strict tests: GF-10 … GF-13 / GF-15 + RS-16 / GF-36 / INH-19 | | | | | |
| by-factory list `ORDER BY id`, by name descending, or case-sensitive (collation C) | — | — | all four fail | passes | — | — |
| by-factory list `lower(name), id DESC` (wrong tie-break) | — | — | only GF-33 fails | passes | — | — |
| workspace list `ORDER BY id DESC` or by name | — | — | — | — | **fails** | passes |
| deleted rows dropped in Python after paging (not the fix) | only GF-10 passes; GF-11, GF-12, GF-13 fail | | | | | |

So FSD-GF-36 / INH-19 fail for the right reason and pass once an `ORDER BY` is there — any `ORDER BY`, as their cards say. Which order it is, is pinned by the non-strict cards, and those report a wrong order only once their markers are off. The notes already tell maintainers to remove a bug's non-strict markers together with the strict one; that step is what makes a wrong `ORDER BY` visible. FSD-GF-33 is the only test for the `id` tie-break of the by-factory list. The last row shows that FSD-GF-11 … GF-13 tell a real fix (filter in the query) from the manager's present habit (filter after paging).

### FSD-INH-18 — why it never failed, and whether to keep it
Measured with a read-only probe in the scratch plugin (`EXPLAIN` and `ctid` of the rows, inside the test's transaction):

- The Given does what the card says: after `S1.updated_by = U2.id` + flush the new version of S1 lies physically behind S2 (run alone: apple at `(1,30)`, Zulu at `(1,31)`; whole file: Zulu at `(4,141)`, apple at `(4,140)`).
- What comes back depends on the **plan**, not on the rows. Sequential scan → physical order → `[S2.id, S1.id]` → the test fails on Then 2, as the card predicts. Bitmap or index scan through `ix_factory_sections_workspace_id` → the index still points at the old place of S1 (the update changed no indexed column, so the new version hangs on the old one) → `[S1.id, S2.id]` → the test passes.
- The plan depends on the size of the table file. In a whole-file run the three bulk cards (about 300 rows, rolled back but still in the file) run before FSD-INH-18, the last test, so the planner chooses the bitmap scan every time: **xpass in every whole-file run**. Run alone shortly after autovacuum had shrunk the table, the plan was a sequential scan and the test failed (3 of 3 here); a few minutes later, the table grown again, it xpassed (3 of 3).
- Shown directly by forcing the plan for the whole file (`SET LOCAL enable_…scan`, gone with each test's rollback): sequential scan → `79 passed, 13 xfailed` (INH-18 fails on line 2177 with `[S2.id, S1.id]`); bitmap scan and index scan → `79 passed, 12 xfailed, 1 xpassed`.

Is the card worth keeping as it is? **Keep it, non-strict, body unchanged.** It is not the alarm for BUG-100 — FSD-INH-19 is, and it works. Its use starts with the fix: against a workspace list ordered by `id DESC` or by name it fails, while FSD-INH-19 passes with either; nothing else in this file pins "`id` ascending, not name order" for sections. Two things to change around it, neither in the test: the card's "Fails today on" sentence (finding 6) and the notes' "never fails" paragraph (finding 5). A recipe that fails under every plan does not exist (the spec says so), so the card should not be made strict.

### Stability
Twelve whole-file runs with today's code: green every time.

| Run | Outcome | xpassed |
|---|---|---|
| plain × 7 (six in a row, one at the end) | `79 passed, 12 xfailed, 1 xpassed` | FSD-INH-18 |
| with coverage | `79 passed, 12 xfailed, 1 xpassed` | FSD-INH-18 |
| with the read-only probe | `79 passed, 12 xfailed, 1 xpassed` | FSD-INH-18 |
| planner forced to a sequential scan | `79 passed, 13 xfailed` | — |
| planner forced to a bitmap scan | `79 passed, 12 xfailed, 1 xpassed` | FSD-INH-18 |
| planner forced to an index scan | `79 passed, 12 xfailed, 1 xpassed` | FSD-INH-18 |

`--runxfail`: `12 failed, 80 passed` (plain, bitmap, index) and `13 failed, 79 passed` (sequential) — the 79 pass cards pass under every plan.

Does anything that can turn the run red rest on physical row order?
- **Strict xfails (8):** FSD-GF-36 / INH-19 look at the SQL text, not at rows. FSD-GF-10 fails because two rows come back where one is expected (its Then 1, `S1.id in ids(result)`, holds for any order). FSD-GF-11: 100 rows against one. FSD-GF-12: four rows match and `limit=2`, so two rows come back whatever the order, against one expected. FSD-GF-13: two rows match and `skip=1`, so one row is left, against `[]`. FSD-GF-15 / RS-16: one row against `[]`. None compares an order; none can flip. All eight failed under all three forced plans.
- **Pass cards with a window:** FSD-GF-20 (`limit=2` with exactly two matching rows, sorted), GF-21 (`skip=1` with one matching row), GF-22 (100 of 101: size, distinct, subset), GF-23 (all 101, sorted), GF-24 (size, distinct, subset), GF-25 / GF-28 (one row, `in [...]`), GF-26, GF-27, GF-29 (`[]`).
- **Every `ids(result) == [...]` and every `result[0]` in a pass card** has exactly one row to return (FSD-GF-02, GF-04, GF-16, GF-18, GF-19, RS-17 Then 3), or is `isinstance(result[0], FactorySection)` (GF-01). The other list checks are `sorted(...)`, `set(...) <=`, `in` or `by_id` (GF-01, GF-14, GF-17, GF-37, GF-38, RS-10, INH-17).
- **Non-strict (5):** FSD-GF-32 … GF-35 failed in every run and under every plan here (no row is updated, so heap order is insertion order unless a freed place is reused); FSD-INH-18 as described. Whatever they do, the run stays green.

No pass card and no strict xfail can flip on row order.

## Surviving mutants
None — 9 mutants, 9 killed (3 `return … → None`, 2 default `skip` / `limit` constants, 2 boolean constants, 2 `==` → `!=`).

| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| — | — | — | — | no survivor | — |

Score: 9 killed / (9 − 0 excluded) = 100%. Run alone, no pytest beside it.

**Beyond the tool.** The tool makes two mutants in each of `soft_delete` / `restore` (it does not delete statements, add statements or mutate `None`) and cannot add a filter, a join or an order. 54 hand-made variants were loaded through the scratch plugin and run against the 79 passing tests (`-m "not xfail"`):

| Variant | Rule | Failed by |
|---|---|---|
| `soft_delete` **commits** | R5 | FSD-SD-08 |
| `soft_delete` without flush | R1, R5 | SD-01 … SD-11, SD-13, RS-18 (13) |
| `deleted_at` not set / set from another clock | R1 | SD-01, SD-05, SD-07, SD-09, SD-10, SD-13 |
| `deleted_by` not set | R1 | SD-01, SD-05, SD-07, SD-09, SD-10, SD-12 |
| also sets `is_active = False` | R2a | SD-04, RS-18 |
| stamps `updated_by` | R2 | SD-02, SD-03, RS-18, RS-19 |
| **deletes the section's assignment rows** (what the manager does today) | R3 | SD-06, RS-13 |
| soft-deletes / deactivates the assigned machines | R3 | SD-06, RS-13 |
| changes the section's factory | R3 | SD-06, SD-10 |
| does nothing / raises when already deleted | R4 | SD-07 |
| refuses `deleted_by=None` | R8 | SD-13 |
| refuses a section of a soft-deleted factory | R6 | SD-10 |
| deletes every live section of the factory / re-stamps the deleted ones | R6 | SD-11 |
| `restore` **commits** | R5 | FSD-RS-10 |
| `restore` without flush / `is_deleted` not reset | R1, R5 | RS-01 … RS-07, RS-10 … RS-15, RS-17 … RS-22 (19) |
| `deleted_at` / `deleted_by` not cleared | R1 | RS-01, RS-07, RS-11, RS-15, RS-17, RS-18, RS-19 (+ RS-05 / RS-04) |
| sets `is_active = True` | R3 | RS-07, RS-09, RS-19 |
| stamps / clears `updated_by` | R2a | RS-03, RS-04, RS-18, RS-19 / RS-03, RS-18, RS-19 |
| an UPDATE although nothing changes | R4 | RS-08, RS-09 |
| **reads the clock** (value discarded) | R2a | FSD-RS-05 |
| raises for a section that is not deleted | R4 | RS-08, RS-09 |
| refuses a section of a soft-deleted factory | R7b | RS-15, RS-17 |
| refuses when a live section of the factory has the name | R9 | RS-20 |
| refuses when a section of the factory in any state has the name | R9 | RS-20, RS-21 |
| refuses when a live section of any factory of the workspace has the name | R9 | RS-20, RS-22 |
| **deletes the section's assignment rows** | R7 | RS-13, RS-14 |
| issues an UPDATE on / deactivates the assigned machines | R7 | RS-13, RS-14 |
| makes the section's factory live | R7b | RS-15 |
| restores every deleted section of the factory / of the workspace | R6 | RS-12, RS-21 |
| issues an UPDATE on the other sections of the factory | R6 | RS-12, RS-20, RS-21 |
| `get_by_factory` hides inactive sections / the sections of an inactive factory | R2a / R3b (2) | GF-14 / GF-18 |
| `get_by_factory` returns only sections that have a machine (inner join) | R7 | GF-37 and 16 others |
| `limit` capped at 100 | R4 | GF-23 |
| `skip` ignored / `limit` ignored | R4, R5 | GF-21, GF-25, GF-27, GF-28, GF-29, GF-31 / GF-23, GF-24, GF-26, GF-30 |
| `get_by_factory` issues an UPDATE on the rows it returns | R7 | GF-17, GF-19, GF-37, GF-38 |
| inherited `get_by_workspace` hides deleted sections / sections of a deleted factory | inherited R4 | INH-17 |
| inherited `get_by_id_and_workspace` hides them | inherited R4 | INH-14, SD-08 / INH-15 |
| inherited `get` hides them | inherited R4 | INH-12 / INH-13 |
| `get_by_factory` with an **outer join to the assignment rows** | R7 × R4 | **none** |
| `get_by_factory` filters on the **factory's** workspace instead of the section's | Inputs, `workspace_id` | **none** |

52 of 54 caught. The two that are not:

| # | Variant | Class | Why no test notices | Missing card | Fix by |
|---|---|---|---|---|---|
| H1 | outer join to `machine_section_assignments` | case-missing (small) | The SQL then yields one line per assigned machine. `Query` folds equal sections together, so FSD-GF-37 (default `limit`) still sees two sections — but the extra lines use up places in the page. Confirmed with a scratch test: FSD-GF-37's Given with `limit=2` returns `[S1.id]` instead of both sections under the variant, and both today. | "a section's machines do not use up places in the page": the Given of FSD-GF-37, When with `limit=2`, Then `sorted(ids(result)) == [S1.id, S2.id]` (`get_by_factory` R7, R4) | optional — case designer |
| H2 | workspace taken from the factory row | spec-gap (declared: cases Spec gap 3) | No card has a section whose factory belongs to another workspace and then lists it. Confirmed with a scratch test: a section of W1 that points at F9 is listed today for `(F9.id, W1.id)` and not for `(F9.id, W2.id)`; under the variant it is the other way round. The spec states this in the Inputs table only ("the section's own; the factory's workspace is not looked at"), not as a numbered rule, and does not say what holds after the BUG-904 fix. | none until the spec has the rule | optional — describer (fill-gaps), then case designer |

Single points worth knowing when a card is edited: FSD-SD-08 is the only test that notices a commit in `soft_delete`, FSD-RS-10 the only one for `restore`, FSD-RS-05 the only one for the clock read; SD-07 for the overwritten stamp; SD-13 for `deleted_by=None`; SD-11 for other sections at delete; GF-23 for a hidden cap; GF-14 / GF-18 for a filter on `is_active`; RS-20 for a name check among live sections (and it cannot be set up once a unique index exists — cases Spec gap 6); GF-33 for the `id` tie-break. (The remark in the notes that `db.refresh` does not change the outcome of FSD-RS-08 / RS-09 does not weaken them: the "UPDATE although nothing changes" variant is failed by both.)

## Spec coverage
Every rule and error row of every callable has at least one card and one test (checked against the spec, not only against the cases file's matrix): `get_by_factory` Returns, R1, R2, R2a, R3, R3a, R3b (1) – (3), R4 – R7, both error rows; `soft_delete` R1, R2, R2a, R3 – R8, error row; `restore` R1, R2, R2a (the clock sentence included: FSD-RS-05), R3 – R7, R7b, R7c, R8, R9; inherited R1, R2, R2a, R3 – R5, both error rows. **No rule without a card.**

Parts of a rule without a card — the first four declared by the designer, none blocking:
- `get_by_factory` R6, "consecutive windows partition the list with no repeats or gaps" (Spec gap 10) — two single-window cards only, deferred to the fix.
- `soft_delete` R3 / `restore` R7, `work_order_templates.default_factory_section_id` rows (Spec gap 2) — deferred to integration tests; machines, assignment rows and the factory are covered.
- Inherited R3, "such a section is still returned by `get_by_factory`" (Spec gap 12) — composition of FSD-INH-10 and FSD-GF-14.
- Spec note "every parameter after `db` is keyword-only" (Spec gap 9) — a note, not a rule; no card.
- H1 and H2 above.

Things to plan for: FSD-GF-33 is the only test of the R6 tie-break and FSD-RS-20 the only one that a name check among live sections fails; neither Given can be built once a unique index on live section names exists (cases Spec gaps 5 and 6). FSD-GF-33 is non-strict, so it would then xfail on a setup error without anyone seeing it.

## Traceability
cases 92 · tests 92 · unmatched: none (each case ID is in exactly one test name; all 92 docstrings equal "`<ID> — <card title>.` / `Rules: <card rules>`") · marker mismatches: none.
- 79 `Expect: pass` cards → no marker. 8 strict xfail cards → `xfail(strict=True)` naming exactly the card's BUG id (FSD-GF-10, GF-11, GF-12, GF-13 BUG-905; GF-15, RS-16 BUG-904; GF-36 BUG-903; INH-19 BUG-100). 5 "(non-strict)" cards → `xfail(strict=False)` naming the card's BUG id (FSD-GF-32 … GF-35 BUG-903; INH-18 BUG-100), as the Conventions prescribe.
- BUG ids used: BUG-100, BUG-903, BUG-904, BUG-905 — all in `docs/testing/bugs.md`.
- Authorship, from the file and `factory_section.local-run.json` (67 entries, 67 accepted, 62 on the first attempt, 5 on the second, 0 escalated): 67 tests under `# [local-coder] <ID>`, 19 under `# [claude] <ID>` — exactly the 19 cards with an `Author: claude` line — and 6 exemplars without a comment (FSD-GF-04, GF-10, GF-30, SD-06, RS-02, INH-09).
- `# Then N` comments: present, in order and equal in number to the card's Then lines in all 92. No unused argument. `try` only in FSD-GF-36 / INH-19 (`finally` removes the listener); `patch` only in FSD-SD-08 / RS-10 (the Conventions' commit spy); the clock mock is touched only by FSD-RS-05.
- As-delivered copy: 66 local tests and 6 exemplars identical, FSD-INH-04 one blank line less, 0 with another body.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_factory_section.py -q -p no:cacheprovider --cov=app.dao.factory_section --cov-branch --cov-report=term-missing -rxX
  app\dao\factory_section.py   23   0   0   0   100%
  79 passed, 12 xfailed, 1 xpassed in 5.88s          (xpassed: FSD-INH-18)

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_factory_section.py -q -p no:cacheprovider --runxfail -rf --tb=short
  12 failed, 80 passed in 3.23s        (the 12 failures on the lines in the xfail table; FSD-INH-18 passed)

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_factory_section.py -q -p no:cacheprovider      (seven times: six in a row, one at the end)
  79 passed, 12 xfailed, 1 xpassed     (7 times; xpassed: FSD-INH-18)

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_factory_section.py -q -p no:cacheprovider -k inh_18 -rxX      (three times, after the whole-file runs)
  91 deselected, 1 xpassed             (3 times; with the probe, earlier: 1 failed, 3 times)

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/factory_section.py tests/unit/dao/test_factory_section.py --json <scratchpad>/fsv/mut.json
  Mutants: 9 · killed 9 · timeout 0 · survived 0 · score 100%      (run alone, no pytest beside it)
```
Matches the Result line of the notes (92 tests · 79 passed · 13 xfail-marked, printed as `12 xfailed, 1 xpassed`; coverage 100%).

Extra checks, scratchpad only (`<scratchpad>/fsv/`; nothing in the repo written except this report; `app/` not touched):
```
audit.py      cards ↔ tests ↔ markers ↔ docstrings ↔ `# Then N` ↔ arguments; expected body rebuilt from each of the
              73 vocabulary cards (Given rows and keywords, When call, every check of every Then line, snapshot
              placement) and compared with the test → 0 problems
selftest.py   22 planted mistakes in a copy of the test file → audit.py reports each
delivered.py  every test against the as-delivered copy; repeated re-reads; snapshot names → findings 2 – 3
PYTHONPATH=<scratchpad>/fsv/plug FSDREF=<variant> .venv/Scripts/python.exe -m pytest tests/unit/dao/test_factory_section.py -q -p no:cacheprovider -p ref_fsd …
  reference fixes and wrong orders (19 runs)        → the table under "xfail tests"
  explain (probe), force_seq / force_bitmap / force_index, with and without --runxfail → "FSD-INH-18", "Stability"
  54 hand variants, -m "not xfail"                  → the table under "Surviving mutants"
… -m pytest <scratchpad>/fsv/test_extra.py -p tests.unit.conftest -p ref_fsd -k test_x_
  today: 2 passed · outer-join variant: the `limit=2` test fails · factory-workspace variant: the F9 test fails   → H1, H2
```

## Local-coder patterns
No functional mistake in 67 tests. All 67 were accepted as designed and all 67 are what their cards say.

| Pattern | Count | Example case IDs | Kind | What would prevent it |
|---|---|---|---|---|
| A Then line with two values and only one assert (the trial slip) | 0 of 32 such lines in the delivered tests; 1 first attempt (FSD-GF-17) rejected by the runner's per-line count (P21), the second attempt is right | FSD-GF-17 Then 5 | caught by the tool | The check exists and works; the sheet sentence alone had not helped. Keep the check. |
| A value or row swapped with another of the same kind (factory F1 / F2 / F9 / FD / FI, workspace, user) | 0 of the 24 cards at risk listed under Findings | FSD-GF-18, SD-10, RS-12, INH-07 | — (looked for, not found) | Still guarded by the read only. The runner checks that a named standing row is *used*, and only for names of the form letters + digits — `FD` and `FI` are not covered, and "used" is not "used in the right place". Tool: the rebuild-and-compare of builder calls and Then expressions (`fsv/audit.py` did it for 73 cards with no false alarm and found 22 of 22 planted mistakes, an FI → FD swap among them). |
| Test name cut at 70 characters | 27 | FSD-RS-15, SD-10, INH-02 … INH-08 | cosmetic — tool, not model | Tool: raise the limit or cut on the title's last full phrase. Already listed for the factory module. |
| `row = reread(db, x)` repeated under each Then line of the same row | 4 tests (6 lines) | FSD-RS-04, RS-06, RS-20, RS-22 | cosmetic | The sheet says "later `re-read SX:` lines reuse `row`"; the model follows it in 27 other tests. Tool: strip a `reread` whose target equals the previous one with no write in between, or leave it. |
| Variable named differently from the card's row / the sheet's snapshot | 3 | FSD-RS-07 (`sx` for SXI), RS-15 (`sh` for SHX), RS-09 (`before`) | cosmetic | The three card names (SXI, SHX, SI) are not in the sheet's "Card says → write" list, which stops at `sx`, `sh`, `si`, `sx9`. Sheet: "any other row name is written the same way, lower-case". |
| First attempt rejected by the tool (from the run report; all five second attempts are faithful) | 5 | ran and failed (M1 assigned twice): FSD-GF-37 · fixture used but not requested: GF-38 · a snapshot the card does not ask for: SD-02, RS-08 · one assert for two values: GF-17 | caught by the tool | The checks exist and work. |

Observations for `docs/testing/local-coder-improvements.md`:
- **Then lines after the failing line of an xfail test:** none in this module — every xfail card fails on its last Then line, so nothing the model wrote went unexecuted. The three local xfail tests (FSD-GF-12, GF-13, GF-15) were run against the reference fixes and pass. Designing bug cards so that the failing line is the last one removes the blind spot altogether.
- **A non-strict order card can pass for a reason other than chance.** FSD-INH-18 passes in every whole-file run because the planner switches to a bitmap scan once the bulk cards have grown the table, and an index scan returns an updated row at its old place. "Update a row to move it" is therefore not a recipe for a wrong order on an indexed filter. The statement-recorder card is the stable form; the order card is worth having only for after the fix.
- **What worked:** `deleted=True` as one keyword (25 local "deleted" rows, all right); `of=` / `to=` for machines and assignments; the `raises:` shape with `begin_nested` (7 local tests, all with the right wrapping and type); Then lines written as ready expressions; "(the very object that was passed in)" → `result is x` in all 24 local `soft_delete` / `restore` tests that return; the literal-code Given line `db.refresh(S1)` placed before the snapshot in both cards; `re-read the returned row` → `reread(db, result)`.

**Still open (none blocks PASS) — numbered fix list:**
1. Optional, case designer: add the card for H1 — the Given of FSD-GF-37 with `limit=2`, expecting both sections (`get_by_factory` R7, R4), so that a join to the assignment rows cannot use up places in the page unnoticed.
2. Optional, describer (fill-gaps), then case designer: state as a rule whose workspace `get_by_factory` filters on when a section points at a factory of another workspace — today and after BUG-904 (H2; cases Spec gap 3) — then one card.
3. Optional, case designer: reword FSD-INH-18's "Fails today on" sentence (it fails under a sequential scan only; in a whole-file run the list is `[S1.id, S2.id]`); keep the card, non-strict (finding 6).
4. Optional, executor: correct the "FSD-INH-18 never fails today" paragraph and the "location not observable" row of `factory_section.notes.md` with the cause and the failing line given here (finding 5).
5. Optional, case designer: decide FSD-GF-33 and FSD-RS-20 before a unique index on live section names is added — FSD-GF-33 is non-strict and would xfail on a setup error unseen, leaving the `id` tie-break of R6 without a test (cases Spec gaps 5, 6).
6. Optional, tool (`tests/unit/_tools/local_coder.py`): the 70-character name cut (finding 1); the rebuild-and-compare acceptance check; extend "a standing row the card names must be used" to `FD` / `FI`.
7. Optional, executor: variable names in FSD-RS-07, RS-09, RS-15; the repeated re-reads in FSD-RS-04, RS-06, RS-20, RS-22; the four hand-written names (findings 2 – 4).
8. Not a test matter: the spec is IN REVIEW. When a bug is fixed the strict tests turn the run red — BUG-905 → FSD-GF-10 … GF-13; BUG-904 → FSD-GF-15, RS-16; BUG-903 → FSD-GF-36, and remove the markers of FSD-GF-32 … GF-35 in the same step; BUG-100 → FSD-INH-19, and remove the marker of FSD-INH-18 in the same step.
