# Verification — `app/dao/machine_section_assignment.py`

> **Verdict:** PASS
> Tests: 69 passed · 8 xfail-marked (4 strict, 4 non-strict; printed as `4 xfailed, 4 xpassed`) (reproduced ✅) · coverage 100% branch (28 statements, 6 branches)
> Mutation: 14 mutants · 13 killed · 1 survived → score 100% (after excluding 0 equivalent, 0 dead, 1 bug-path)
> Source commit: e48a092 · Cases revision: none stated (READY, 77 cases; spec APPROVED 2026-10-16)

## Summary
These tests can be trusted. All 77 tests were read against their cards line by line: every Given row and column, the When call and each argument, every numbered Then line and every check a line lists. Nothing was sampled. As a second, independent check, a script rebuilt the expected body of each of the 63 vocabulary cards (56 local, 6 exemplars, and MSA-UP-19) from the card text and the helper sheet. It compared each body statement by statement, with the `# Then N` comments and the argument set: **0 differences**. The script reported 28 of 28 planted mistakes, among them S1/S2 and M2/M3 swaps in Given rows, an M1/M2 swap in the When, the second value of a two-value Then line dropped, and a `sorted()` dropped.

- **Local-model tests (56): functional findings in 0 / 56, so 56 of 56 (100%) are right as delivered.** Cosmetic findings in 16 / 56 (names cut by the tool at 70 characters). Two more had a stray blank line at delivery (MSA-GS-01, UP-10), already removed.
- **MSA-UP-19 was handed back, not delivered.** The model failed it 3 times (`# Then 1` misplaced, then missing), and Claude wrote it. It counts as one of the 21 Claude-written tests, not one of the 56.
- **Claude-written tests (21 = 6 exemplars + 15 `# [claude]`): functional findings in 0 / 21.** Cosmetic findings in 4 / 21 (names: exemplars MSA-GM-06 and UP-17 cut at 70 characters; UP-20 and CL-12 leave out "in the session").
- **The two edits after delivery are confirmed.** Against `test_msa.asdelivered.py`, 60 of the 62 delivered tests (54 local + 6 exemplars) are identical line for line. MSA-GS-01 and UP-10 differ by one deleted blank line each and nothing else. The 15 tests missing from the copy are exactly the 15 `# [claude]` ones. The scaffold differs only by the `patch`, `event` and `insert` imports plus `bulk_assigned_machines` and `StatementRecorder`. The order of the delivered tests is unchanged.
- **Stability:** 8 whole-file runs with today's code (6 plain, 1 with coverage, 1 with a read-only plan probe) all gave `69 passed, 4 xfailed, 4 xpassed`. There were also 3 runs with the planner forced to one scan type each. No run was red. No strict xfail and no pass card rests on row order: all 69 pass cards pass under every forced plan.
- **Order cards and recorder cards:** the four non-strict order cards fail as their cards predict, but only under a sequential scan. The default plan is a bitmap heap scan, and there they xpass. Keep them non-strict: they are the only tests that pin *which* order the fix uses. The strict recorder cards GS-22 and INH-07 fail today on the `ORDER BY` assertion of Then 2 and pass against a reference that adds an `ORDER BY`.
- **Then lines that never run:** MSA-UP-03 Then 4 – 5 (exemplar) and CL-06 Then 4 (claude). Read against their cards they are right, and against scratch references of BUG-909 and BUG-907 both tests pass in full. No local test is an xfail.
- **Mutation:** the one survivor is the 10 000 cap itself (BUG-907, bug-path); with markers on, even that mutant turns the run red through CL-06 XPASS(strict). 45 hand-made variants (the four reference fixes among them) were run as well: 38 turn the normal run red, 30 of them through a pass card and 8 only through a strict xfail flipping to XPASS. The 7 that do not are equivalent (bulk instead of row-by-row delete), bug-path (other caps, ids returned sorted), or one small gap: a cap of 2 or 3 rows. That gap is optional and does not block PASS.

## Findings
None functional. Cosmetic only — none blocks PASS, all optional:

| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | Naming (local) — COSMETIC | MSA-CL-05, CL-09, GM-05, GS-02, GS-08, GS-09, INH-01, INH-03, UP-04, UP-06, UP-12, UP-14, UP-15, UP-18, UP-21, UP-23 (16 tests) | The tool cut the test name at 70 characters, so the name does not carry the whole title. The docstring carries the full ID, title and rules in all 77 tests. The tool made this cut, not the model. | `test_msa_up_15__a_machine_whose_row_has_another_workspace_id_hits_the_one_row_per` | optional — tool (`tests/unit/_tools/local_coder.py`) |
| 2 | Layout (local) — COSMETIC | MSA-GS-01, UP-10 (as delivered) | There was a stray blank line between the Given rows and the snapshots (GS-01) and after the docstring (UP-10). Both are already removed and nothing else changed. | `delivered.py` diff: only `-''` lines | done (executor) |
| 3 | Naming (exemplar) — COSMETIC | MSA-GM-06, UP-17 | The name is cut at 70 characters. This repeats the tool's cut on hand-written tests. | `test_msa_up_17__a_factory_section_id_that_is_no_section_fails_on_flush_and_the` | optional — executor |
| 4 | Naming (claude) — COSMETIC | MSA-UP-20, CL-12 | The name leaves out "in the session" from the title. All other hand-written names are complete. | `test_msa_up_20__the_move_is_flushed_but_not_committed_visible_to_get_by_machine_undone_by_a_rollback` | optional — executor |
| 5 | Documentation — COSMETIC | `machine_section_assignment.cases.md`, "Fails today on" of MSA-GS-20, GS-21, CL-11, INH-06 | The cards say the updated row "usually comes back last". It does so only under a sequential scan. Under the default plan here (bitmap heap scan through an index) the order is the insertion order in every run. Those runs are 8 whole-file runs plus 3 runs of the four cards alone; the notes report 12 of 13. | section "Order cards" | optional — case designer |

Checked for and **not** found in any of the 56 local tests, both by reading and by the rebuild script:
- **Given rows:** no missing, extra or reordered row, and no wrong `of=` / `to=`. In particular, no swap with another row of the same kind:
  - GS-09 has O1 = M1→**S2**, O2 = **M9**→S1, A3 = **M2**, A4 = **M3**.
  - GM-09 points at **S3**, GM-10 at **S9**, GM-08 and GS-05 at **SX**, GM-07 and GS-04 use **MD**.
  - GS-02, GS-03, CL-02 and CL-03 have A9 = M9→**S1**; GS-08 and INH-08 have M9→**S9**.
  - UP-06 has A2 = **M2** (M1 has none), UP-16 has A2 = M2→S1.
  - CL-04 is MD→S1, CL-05 is M1→SX, INH-05 is M1→S1, M2→S2, M9→S9.
- **Extra keywords:** `workspace_id=w2.id` appears on exactly the three rows whose card says "but `workspace_id W2.id`" (GM-05, UP-15, and the exemplar GM-06). No row has a keyword its card does not list.
- **Code lines in the Given:** `a1_id = a1.id` (UP-02) and `_loaded = m1.factory_section_id` (UP-21, UP-23, CL-09) are at the card's place, after the rows. Both spellings follow the helper sheet.
- **When call:** no changed, dropped or added argument. This covers `workspace_id=w2.id` (GM-04, GS-03, CL-03), `machine_id=md.id` / `m9.id`, `factory_section_id=None` / `s3.id` / `sx.id` / `s9.id` / `MISSING`, `user_id=MISSING` (UP-06, UP-07, UP-18) and `user_id=None` (UP-25), `skip=0, limit=2`, `skip=2, limit=2`, `skip=1`, `skip=2`, `skip=5`, `limit=0`, `limit=-1`, `skip=-1`, the dict / schema arguments of `create`, and `dao.get(db, a9.id)`.
- **Then lines:**
  - None is skipped, and no assertion sits under the wrong `# Then N`.
  - **No two-value line has fewer asserts than values.** There are 10 such lines in the local cards (UP-02 Then 4 and 6, UP-04 Then 4, UP-10, UP-13, UP-14 Then 2, UP-15 Then 5, UP-18 Then 5, INH-02 Then 2 with three values and Then 4), and each has every assert.
  - No check is weaker than the card. `sorted(...)`, `set(...) <=`, `len`, `in [...]` occur only where the card writes them. `ids(result) == [x]` and `result == [m.id]` stay exact.
  - The raises lines keep the card's type and the full texts (`"LIMIT must not be negative"`, the constraint names).
- **Write cards:** every re-read goes through `reread(db, …)` or `rows_of(db, …)` of the row the line names. Every `unchanged` / `nothing written` snapshot is taken after the last Given line and before the call, and covers the row the Then line names. No test takes a snapshot its card does not ask for. The Q1 checks (UP-21 Then 2, UP-23 Then 2, CL-09 Then 2) read `m1.factory_section_id` on the same object, before any re-read, as the cards require.
- **Swallowed failures and extra mocks:** none. `pytest.raises` appears only on `raises:` cards (7 local), each with the card's type and around `db.begin_nested()`. No local test has a `try` or patches anything.

The 21 Claude-written tests were read the same way, with no functional finding:
- **Bulk rows.** GS-10 and GS-11 build `f"Unit {k:03d}"` for k = 1 … 501, and CL-06 builds `f"Bulk {k:05d}"` for 1 … 10 001. Each set is one multi-row insert of F1 / W1 machines (active, not deleted, not running) and their S1 assignments, `created_by U1`. GS-11 Then 2 compares against the sorted assignment ids.
- **Ordering Givens.** GS-20, GS-21 and INH-06 update `a1.created_by` after the last row and flush. CL-11 builds A1 = **M3**, A2 = M1, A3 = M2, as the card requires, so that row ids and machine ids rise in different orders.
- **Rollback cards.** UP-20 and CL-12 open the savepoint directly before the call. They run Then 1 – 2, including the follow-up DAO call, inside the savepoint and the rest after `sp.rollback()`. The `db.commit` spy uses `wraps=`.
- **Steps after the call.** UP-22 and CL-10 run `db.expire(m1)` under Then 2, before the assert. UP-24 renames M1 and flushes under Then 2.
- **Recorder cards.** GS-22 and INH-07 put the recorder around the When only. Then 2 is two asserts: one SELECT was sent, and it has `ORDER BY`.
- **UP-19.** It uses M2 in the When (A1 is M1's row), `workspace_id=MISSING`, `rows_of(M2) == 0`, unchanged(A1) and nothing written. All six Then lines are present, in order.

### xfail tests
| Card | Author | Marker | Fails on (`--runxfail`) | Then lines never executed today | Verdict |
|---|---|---|---|---|---|
| MSA-UP-03 | exemplar | strict BUG-909 | Then 3, line 350: `assert result.id == a1_id` (new id = old + 1) | Then 4 – 5 (lines 352 – 355) | right line, right reason |
| MSA-GS-22 | claude | strict BUG-906 | Then 2, line 1183: `'ORDER BY' in 'SELECT … WHERE … LIMIT … OFFSET …'`; `len(selects) == 1` holds | none | right line, right reason |
| MSA-CL-06 | claude | strict BUG-907 | Then 3, line 1572: `assert 10000 == 10001` | Then 4 (line 1574) | right line, right reason |
| MSA-INH-07 | claude | strict BUG-100 | Then 2, line 1756: no `ORDER BY` | none | right line, right reason |
| MSA-GS-20 | claude | non-strict BUG-906 | under a sequential scan only: Then 2, line 1144, `[A2, A3, A1] == [A1, A2, A3]` | — | right line, as predicted |
| MSA-GS-21 | claude | non-strict BUG-906 | under a sequential scan only: Then 1, line 1165, `[A3, A1] == [A2, A3]` | — | right line, as predicted |
| MSA-CL-11 | claude | non-strict BUG-906 | under a sequential scan only: Then 2, line 1649, `[M1, M2, M3] == [M3, M1, M2]` | — | right line, as predicted |
| MSA-INH-06 | claude | non-strict BUG-100 | under a sequential scan only: Then 2, line 1738, `[A2, A1] == [A1, A2]` | — | right line, as predicted |

No local-written test is an xfail.

**The never-executed lines, checked.** By reading: MSA-UP-03 Then 4 is `row = rows_of(db, m1)[0]; assert row.id == a1_id` and Then 5 is `row.created_by == u1.id`, as on the card. MSA-CL-06 Then 4 is `count_rows(…, factory_section_id=s1.id) == 0`, as on the card. Against scratch references (`DAOMachineSectionAssignment` patched in the test process by a pytest plugin in the scratchpad; `app/` untouched), both tests pass in full. That means every one of their lines runs and holds:

| Reference (`--runxfail`) | UP-03 | GS-22 | CL-06 | INH-07 | GS-20, GS-21, CL-11, INH-06 | the 69 pass cards |
|---|---|---|---|---|---|---|
| today's code (re-implemented by the plugin, as a control) | fails l. 350 | fails l. 1183 | fails l. 1572 | fails l. 1756 | pass | pass |
| BUG-909 fix: same section → existing row returned untouched | **passes** | fails | fails | fails | pass | pass |
| BUG-907 fix: no cap | fails | fails | **passes** | fails | pass | pass |
| BUG-906 fix: `get_by_section … ORDER BY id` | fails | **passes** | fails | fails | pass | pass |
| BUG-100 fix: `get_by_workspace … ORDER BY id` | fails | fails | fails | **passes** | pass | pass |
| all four fixes | pass | pass | pass | pass | pass | **77 passed** |
| one fix, markers on (normal run) | red through exactly that bug's strict test: UP-03 / CL-06 / GS-22 / INH-07 (`1 failed, 69 passed, 3 xfailed, 4 xpassed` each) | | | | | |

### Order cards (GS-20, GS-21, CL-11, INH-06): why they xpass, and whether to keep them
- **The plan.** A read-only probe (`msav/test_probe_plan.py`, the GS-20 Given, rolled back) shows that both queries run as a **Bitmap Heap Scan** through an index. The update of `created_by` changes no indexed column, so it is a HOT update. The index still points at the row's first place, and the rows come back in insertion order (`[A1, A2, A3]`). So the four cards xpass in every default run (8 whole-file runs and 3 runs of the four cards alone here).
- **Forcing the plan for the whole file** (`SET LOCAL enable_…scan`):
  - sequential scan → `69 passed, 8 xfailed`, and with `--runxfail` all four fail on the card's line with the card's predicted order (table above);
  - bitmap and index scan → `69 passed, 4 xfailed, 4 xpassed`.
- **Keep them, non-strict, bodies unchanged.** They are not the alarms; GS-22 and INH-07 are. They become useful with the fix, because they are the only tests that pin *which* order:
  - Against `get_by_section … ORDER BY id DESC`, GS-20, GS-21 and CL-11 fail, while GS-22 passes.
  - Against `ORDER BY machine_id`, only CL-11 fails: its Given makes row ids and machine ids rise in different orders.
  - Against `get_by_workspace … ORDER BY id DESC`, INH-06 fails, while INH-07 passes.

  Their markers must be removed in the same change as the strict one, as the notes already say. Only the "Fails today on" wording needs a change (finding 5). A Given that fails under every plan does not exist, so they must not become strict.

### Stability
Every whole-file run with today's code was green.

| Run | Outcome | xpassed |
|---|---|---|
| plain × 6 (in a row) | `69 passed, 4 xfailed, 4 xpassed` | GS-20, GS-21, CL-11, INH-06 |
| with coverage | `69 passed, 4 xfailed, 4 xpassed` | same |
| with the read-only plan probe (whole file + probe) | `70 passed, 4 xfailed, 4 xpassed` | same |
| planner forced to a sequential scan | `69 passed, 8 xfailed` | — |
| planner forced to a bitmap scan / an index scan | `69 passed, 4 xfailed, 4 xpassed` | same four |

`--runxfail`: `4 failed, 73 passed` plain and under the bitmap and index plans; `8 failed, 69 passed` under the sequential plan. **The 69 pass cards pass under every plan.**

Does anything that can turn the run red rest on physical row order?
- **Strict xfails (4):** none of them compares an order. UP-03 compares one id, CL-06 counts, and GS-22 / INH-07 look at the SQL text. All four failed under all three forced plans.
- **Pass cards:**
  - Each `ids(result) == [x]` or `result == [m.id]` has exactly one row to return: GS-02, GS-03, CL-02, CL-03, CL-05, CL-09, CL-10, and Then 1 of GS-22 / INH-07.
  - GS-01 `result[0]` is only `isinstance`.
  - The windows use `sorted`, `set <=` or `in`: GS-09 (`limit=2` with exactly two matching rows), GS-12, GS-13, GS-16, GS-10, GS-11.
  - `rows_of` sorts by id and is only used with one row.

No pass card and no strict xfail can flip on row order.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | 64 | `limit=10000` → `10001` | bug-path | The 10 000 cap is BUG-907 (`clear_for_section` R4; intended: no cap). Only MSA-CL-06 targets it, and that strict xfail is excluded from the mutation run. With a cap of 10 001, CL-06 passes in full, so in a normal run (markers on) this mutant turns the run red: `1 failed (CL-06 XPASS strict), 69 passed, 3 xfailed, 4 xpassed`. | — (resolves with the BUG-907 fix or the dead-code removal after BUG-908) |

Score: 13 killed / (14 − 1 bug-path) = 100%. The tool ran alone, with no pytest beside it. The 13 killed mutants are 5 × `return … → None`, 2 × negated `if`, `is None → is not None`, 4 × `== → !=` in the two lookups, and the `skip` / `limit` defaults `0 → 1` and `500 → 501`.

**Beyond the tool.** The tool does not delete or add statements, change a filter or an order, or add a commit. 45 hand-made variants were loaded through the scratch plugin and run against the 69 passing tests (`-m "not xfail"`, as `mutate.py` does). Unless noted, each was also run with markers on.

| Variant | Rule | Failed by |
|---|---|---|
| **`commit()` in `upsert_for_machine`** | R9 | UP-20 (commit spy), UP-21, UP-23 (the commit expires M1) |
| **`commit()` in `clear_for_section`** | R8 | CL-12 (commit spy), CL-09 |
| **`clear_for_section` without the cap** (= BUG-907 fix) | R4 | none of the pass cards. With markers on, CL-06 XPASS(strict) turns the run red |
| **cap 1** | R1 | CL-01, CL-04, CL-12 |
| **cap 2 / cap 3** | R1 | **none** (H1) |
| **cap 500 / 9 999 / 10 001** | R4 [BUG-907] | none of the pass cards. With markers on, cap 10 001 turns CL-06 XPASS(strict) → red; 500 and 9 999 leave CL-06 failing, so they are not visible |
| **move updates the row in place, `created_by` kept** (the "update in place" reading of the BUG-909 fix) | R2 (Q2), R3, R8, R10 | UP-02 (Then 2, l. 588: same id), UP-21 (Then 2, l. 699: the loaded M1 now says S2, because its very object was changed), UP-18 (Then 1, l. 1376: no `IntegrityError`, because `user_id` is not written). With markers on, UP-03 also flips to XPASS(strict): `4 failed` |
| the same, also `updated_by = user_id` | R2, R8 | UP-02, UP-21, UP-18 (Then 3, l. 1383: `updated_by_fkey`, not `created_by_fkey`), plus UP-03 XPASS |
| **BUG-909 fix proper** (same section → the existing row, untouched; a move still re-creates) | R3 | none of the pass cards (UP-04 holds before and after, as designed). UP-03 flips alone |
| **lookups hide deleted machines** (both) | P2: GM R2, GS R2, CL R3 | GM-07, GS-04, CL-04 |
| `get_by_machine` hides deleted machines / deleted sections | GM R2 | GM-07 / GM-08 |
| `get_by_section` hides deleted machines / a deleted section | GS R2, CL R3 | GS-04, CL-04 / GS-05, CL-05 |
| `get_by_machine` without workspace filter | GM R1, UP R7 | GM-04, GM-05, UP-15 |
| `get_by_machine` filters on the **machine's** workspace | GM R1 | GM-05, GM-06, UP-15 |
| `get_by_section` without workspace filter | GS R1, CL R2 | GS-02, GS-03, GS-08, GS-09, CL-02, CL-03 |
| `get_by_section` capped at 100 | GS R4 | GS-10, GS-11 |
| `get_by_section` ignores `skip` | GS R5 | GS-13, GS-15, GS-16, GS-17, GS-19 |
| `get_by_section` pages in Python (no SQL `LIMIT` / `OFFSET`) | GS Errors | GS-18, GS-19 |
| `get_by_section ORDER BY id DESC` / `ORDER BY machine_id` | GS R6 | none of the pass cards. With markers on, GS-22 XPASS(strict) → red. GS-20, GS-21, CL-11 / only CL-11 fail (non-strict) |
| `get_by_workspace ORDER BY id DESC` | inh. R3 | INH-07 XPASS(strict) → red; INH-06 fails (non-strict) |
| upsert without the final flush | R1, R9 | 13 (UP-01, UP-02, UP-04, UP-08, UP-10 … UP-14, UP-20 … UP-22, UP-25) |
| upsert without the flush after the delete | R2, R4 | 12 (UP-02, UP-04, UP-05, UP-07 … UP-09, UP-17, UP-18, UP-20 … UP-23) |
| `created_by` not written | R1, R2, R8 | UP-01, UP-02, UP-18 |
| new row stamped `updated_by` | R1, R2 | UP-01, UP-02 |
| new row gets the **machine's** workspace | R6 | UP-14, UP-19 |
| upsert refuses a deleted / foreign section | R6 | UP-11, UP-12, UP-17, UP-19 |
| upsert refuses a deleted / foreign machine | R6 | UP-13, UP-14, UP-16, UP-19 |
| upsert expires the machine (refreshes it) | R10 (Q1) | UP-21 |
| upsert issues an UPDATE on the machine | R5 | UP-08, UP-13 |
| `clear_for_section` without flush | R1, R8 | CL-01 … CL-05, CL-09, CL-10, CL-12 |
| returns row ids instead of machine ids | Returns | CL-01 … CL-05, CL-09, CL-10, CL-12 |
| expires the machines it unassigns (what the comment promises) | R6 (Q1) | CL-09 |
| deactivates the machines | R3 | CL-01, CL-04 |
| issues an UPDATE on the section | R3 | CL-01, CL-05 |
| upsert deletes with a bulk `query.delete()` | — | none (equivalent, see below) |
| clear deletes with a bulk `query.delete(synchronize_session="fetch")` | — | none (equivalent, see below) |
| clear returns `sorted(set(ids))` | R7 [BUG-906] | none of the pass cards; CL-11 only (non-strict) |

38 of 45 turn the normal run red: 30 through a pass card, and 8 only through a strict xfail flipping to XPASS (the BUG-906, 907, 909 and 100 fixes; a cap of 10 001, i.e. the tool's survivor; `get_by_section` ordered `id DESC` or by `machine_id`; `get_by_workspace` ordered `id DESC`). The 7 that do not:

| # | Variant | Class | Why no test notices | Fix by |
|---|---|---|---|---|
| H1 | `clear_for_section` with a cap of 2 or 3 (2 variants) | case-missing (small) | No pass card clears more than 2 rows of one section. CL-11 has 3 but is a non-strict xfail. A pass card "three rows of S1 → `sorted(result) == [M1, M2, M3]`, none left" (R1) would catch it. Low value: the method is on the dead-code list after BUG-908. | optional — case designer |
| H2 | cap 500 / 9 999 (2 variants) | bug-path | This is the BUG-907 cap itself. Only the strict CL-06 sees a change of the cap: it flips to XPASS (red) when the cap is gone or 10 001 or higher (`1 failed, 69 passed, 3 xfailed, 4 xpassed`), and stays xfail for any cap below 10 001. | — |
| H3 | `clear_for_section` returns the machine ids sorted | bug-path | Order is BUG-906 (R7). The SQL is unchanged, so GS-22 stays xfail. Only the non-strict CL-11 fails, and that becomes visible once its marker is removed with the fix. The same holds for which `ORDER BY` a fix uses: any `ORDER BY` turns GS-22 green, so the run goes red, while *which* order is pinned only by GS-20, GS-21 and CL-11 (see "Order cards"). | — |
| H4 | bulk `query.delete()` in upsert or clear (2 variants) | equivalent | No rule says how a row is deleted. R10 / R6 (the loaded machine keeps its old section; a later flush does not bring the row back) hold either way, as UP-21 … UP-24 and CL-09 / CL-10 show by passing. | — |

**A single point worth knowing when a card is edited.** UP-20 is the only test that notices a commit in `upsert_for_machine` *as a commit* (UP-21 and UP-23 notice only its expiry), and CL-12 is the same for `clear_for_section`. UP-21 alone notices a machine refreshed by upsert, and CL-09 alone one refreshed by clear. UP-18 is the one that a move updating in place without touching `created_by` breaks on its error line. CL-11 alone tells "order by row id" from "order by machine id".

## Spec coverage
Every rule and error row has at least one card and one test. This was checked against the spec itself, not only against the cases file's matrix:
- `get_by_machine`: R1 – R3, Returns.
- `get_by_section`: R1 – R7, both error rows.
- `upsert_for_machine`: R1 – R10, all five error rows, Returns, and the Inputs line "`None` is stored as `NULL`" (UP-25).
- `clear_for_section`: R1 – R8, Returns.
- Inherited: R1 – R3, both error rows.

**No rule is without a card.**

Parts of a rule without a card. The first three are declared by the designer, and none blocks:
- `get_by_section` R6, "consecutive windows partition the section's rows" (Spec gap 3): one full-order and one window card only, deferred to the fix.
- The spec note "every parameter after `db` is keyword-only" (Spec gap 2): a note, not a rule; no card.
- Inherited R3, "`get_multi` has no workspace filter": deferred to `base.cases.md` (Deferred table). `get` has MSA-INH-08.
- H1 above (R1 with more than two rows of a section).

## Traceability
cases 77 · tests 77 · unmatched: none (each case ID is in exactly one test name; all 77 docstrings equal "`<ID> — <card title>.` / `Rules: <card rules>`") · marker mismatches: none.
- **Markers.** The 69 `Expect: pass` cards have no marker. The 4 strict cards have `xfail(strict=True)` naming exactly the card's BUG id: UP-03 BUG-909, GS-22 BUG-906, CL-06 BUG-907, INH-07 BUG-100. The 4 "(non-strict)" cards have `xfail(strict=False)` naming the card's BUG id: GS-20, GS-21, CL-11 BUG-906; INH-06 BUG-100.
- **BUG ids used:** BUG-100, BUG-906, BUG-907, BUG-909, all in `docs/testing/bugs.md`.
- **Authorship**, from the file and `machine_section_assignment.local-run.json` (57 sent, 56 accepted, 50 on the first attempt, 6 after retries, 1 escalated):
  - 56 tests are under `# [local-coder] <ID>`.
  - 15 are under `# [claude] <ID>`: the 14 cards with an `Author: claude` line, plus MSA-UP-19 (the one escalated).
  - 6 are exemplars without a comment (MSA-GM-06, UP-01, UP-03, UP-17, CL-01, INH-04).
- **`# Then N` comments** are present, in order and equal in number to the card's Then lines in all 77. There is no unused argument, and the argument set equals the fixtures the body uses in all 63 rebuilt tests.
- **`try`, `patch` and the recorder.** No test has a `try`. `patch` appears only in UP-20 and CL-12 (the Conventions' commit spy, `wraps=`). The `StatementRecorder` appears only in GS-22 and INH-07.
- **As-delivered copy:** 60 tests identical; MSA-GS-01 and UP-10 have one blank line less each; 0 tests have another body.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine_section_assignment.py -q -p no:cacheprovider --cov=app.dao.machine_section_assignment --cov-branch --cov-report=term-missing -rxX
  app\dao\machine_section_assignment.py   28   0   6   0   100%
  69 passed, 4 xfailed, 4 xpassed in 11.35s          (xpassed: GS-20, GS-21, CL-11, INH-06)

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine_section_assignment.py -q -p no:cacheprovider --runxfail -rf --tb=short
  4 failed, 73 passed in 7.31s        (UP-03 l. 350, GS-22 l. 1183, CL-06 l. 1572, INH-07 l. 1756)

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine_section_assignment.py -q -p no:cacheprovider -rxX      (six times in a row)
  69 passed, 4 xfailed, 4 xpassed     (6 times; same four xpassed)

… -k "gs_20 or gs_21 or cl_11 or inh_06" -rxX      (three times)
  73 deselected, 4 xpassed

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/machine_section_assignment.py tests/unit/dao/test_machine_section_assignment.py --json <scratchpad>/msav/mut.json
  Mutants: 14 · killed 13 · timeout 0 · survived 1 · score 93%      (run alone, no pytest beside it)
  SURVIVED #10 L64:111 const: 10000 -> 10001                          (bug-path → 100% after exclusion)
```
These match the Result line of the notes: 77 tests · 69 passed · 8 xfail-marked, printed as `69 passed, 4 xfailed, 4 xpassed`; coverage 100%.

Extra checks, scratchpad only (`<scratchpad>/msav/`). Nothing in the repo was written except this report, and `app/` was not touched:
```
audit.py      cards ↔ tests ↔ markers ↔ docstrings ↔ `# Then N` ↔ arguments; expected body rebuilt from each of the
              63 vocabulary cards (Given rows and keywords, code lines, snapshots and their place, When call, every
              check of every Then line, raises shape) and compared statement by statement → 0 problems
selftest.py   28 planted mistakes in a copy of the test file → audit.py reports 28 of 28
delivered.py  every test against test_msa.asdelivered.py → 60 identical, GS-01 / UP-10 one blank line, scaffold diff
PYTHONPATH=<scratchpad>/msav/plug MSAREF=<variant> … -p ref_msa   (driver: drive.py pass | runx | plain <variants>)
  control `same` (today re-implemented): reproduces 69 / 4 / 4 and the four failing lines
  reference fixes fix906 / fix907 / fix909 / fix100 and all four, --runxfail and markers on → table under "xfail tests"
  force_seq / force_bitmap / force_index, markers on and --runxfail                         → "Order cards", "Stability"
  45 hand variants, -m "not xfail" (and markers on where it matters)                         → table under "Surviving mutants"
test_probe_plan.py   EXPLAIN + ctid of the GS-20 Given (read-only, rolled back): Bitmap Heap Scan, rows in id order
```

## Local-coder patterns
There is no functional mistake in the 56 delivered tests. All 56 are what their cards say.

| Pattern | Count | Example case IDs | Kind | What would prevent it |
|---|---|---|---|---|
| A value or row swapped with another of the same kind (S1/S2/S3/SX/S9, M1/M2/M3/MD/M9, W1/W2, U1/U2) | 0 in the 56 delivered tests | looked at in GS-09, GM-09, GM-10, CL-03, UP-06, UP-16, INH-05 | — (looked for, not found) | Still guarded only by reading and the runner's "named row is used" check. Tool: the rebuild-and-compare (`msav/audit.py` rebuilt 63 bodies with no false alarm and found 28 of 28 planted mistakes, swaps among them). For this vocabulary it is about 250 lines and could become the runner's acceptance check. |
| A Then line with two or more values and fewer asserts | 0 of 10 such lines | UP-02 Then 4 / 6, INH-02 Then 2 / 4 | — | The runner's per-line count works. Keep it. |
| `raises:` card: the `# Then 1` comment misplaced or missing before `with pytest.raises` | 1 test, 3 attempts → handed back | MSA-UP-19 | escalated | UP-16, UP-17 (exemplar) and UP-18 have the same shape and were right. The sheet's line "`raises:` → as MSA-UP-17" could say explicitly: "`# Then 1` stands on the line before `with pytest.raises`; the next comment is `# Then 2`". |
| First attempt rejected by the runner (all second / third attempts are faithful) | 6 | a Given row left out (GS-01); fixture not requested (UP-02 `mk_assignment`, UP-08 `f1`); `# Then N` missing or out of order (UP-15, UP-07, UP-12); an unused `before` snapshot (UP-07, UP-12) | caught by the tool | The checks exist and work. |
| Test name cut at 70 characters | 16 | MSA-UP-15, INH-03, CL-09 | cosmetic — tool, not model | Tool: raise the limit or cut at the title's last full word. This is already listed for the factory module. |
| Stray blank line (Given / snapshot, after the docstring) | 2 | MSA-GS-01, UP-10 | cosmetic, already removed | The tool could normalise blank lines when it inserts the test. |

Observations for `docs/testing/local-coder-improvements.md`:
- **Then lines after the failing line of an xfail test:** no local test is an xfail here, so nothing the model wrote goes unexecuted. The two such blocks (UP-03 Then 4 – 5, exemplar; CL-06 Then 4, claude) were run against the reference fixes and hold.
- **What worked:**
  - `mk_assignment(of=…, to=…)` with "but" keywords: 2 local rows with `workspace_id=w2.id` (GM-05, UP-15), both right, and none added where the card has none.
  - The `_loaded` spelling from the sheet, in all three local Q1 tests, at the right place.
  - "Re-read rows_of(M1)[0]" written as `rows_of(db, m1)[0]` and reused for later lines.
  - The `raises:` shape with `begin_nested`: 7 local tests, all right.
  - `count:` lines in all three forms: rows_of, the whole table, and a filtered table.
- **Runner fix P22 is still untested:** the sheet still maps `loaded =` to `_loaded`, so the exemption for card code lines was never exercised. This matches the notes.

**Still open (none blocks PASS) — numbered fix list:**
1. Optional, case designer: add a pass card for `clear_for_section` R1 with three rows of S1 (e.g. M1, M2, M3 → `sorted(result) == [M1.id, M2.id, M3.id]`, 0 rows of S1 left), so that a small cap cannot go unnoticed (H1). Skip it if the BUG-908 removal of `clear_for_section` is near.
2. Optional, case designer: reword "Fails today on" of MSA-GS-20, GS-21, CL-11 and INH-06. They fail only when the planner uses a sequential scan; under the default bitmap / index scan the updated row keeps its place (HOT update) and the order equals the intended one. Keep the cards non-strict and their bodies unchanged (finding 5).
3. Optional, tool (`tests/unit/_tools/local_coder.py`):
   - remove the 70-character name cut (finding 1);
   - normalise blank lines on insert (finding 2);
   - consider the rebuild-and-compare as the acceptance check;
   - make the sheet's `raises:` line say where `# Then 1` goes (the UP-19 hand-back).
4. Optional, executor: hand-written names MSA-GM-06 and UP-17 (cut), UP-20 and CL-12 (missing "in the session") (findings 3 – 4).
5. Not a test matter: when a bug is fixed, its strict test turns the run red:
   - BUG-909 → MSA-UP-03;
   - BUG-907 → CL-06;
   - BUG-906 → GS-22, and remove the markers of GS-20, GS-21, CL-11 in the same step;
   - BUG-100 → INH-07, and remove the marker of INH-06 in the same step.

   After the BUG-908 fix, GS-01 … GS-22 and CL-01 … CL-12 go with the dead code.
