# Verification — `app/dao/factory.py`

> **Verdict:** PASS
> Tests: 100 passed · 10 xfailed (reproduced ✅; up to 3 of the 6 non-strict xfails show as xpassed) · coverage 100% branch (27 statements, no branches)
> Mutation: 19 mutants · 19 killed · 0 survived → score 100% (nothing excluded)
> Source commit: e48a092 · Cases revision: none stated (READY on pilot defaults, 110 cases, changed after finishing on 2026-10-11; spec still IN REVIEW)
> **Review round 2026-10-16 (delegated — decided by Claude under the reviewer's delegation):** spec APPROVED with P1, P2, P3, Q1–Q4 accepted as suggested; no rule changed. Cases revision 2: Status READY, wording only — FCD-GW-21…24 "physically behind" / "Fails today on" now say it holds only under some query plans (non-strict), the BUG-100 / BUG-706 coverage rows list FCD-GW-26 / GA-28, Spec gap 1 closed, Spec gap 13 added (the `get_active_factories` R6 `id` tie-break cannot be observed without a case-only name pair; no new card). No card and no test changed — no local-written test body and no marker touched. Re-run: `100 passed, 10 xfailed`.

## Summary
These tests can be trusted. All 110 tests were read against their cards line by line — every Given row and column, the When call and each argument, every numbered Then line. Nothing was sampled. As a second, independent check a script rebuilt the expected body of each of the 95 vocabulary cards (88 local + 7 exemplars) and compared it with the test: **0 differences**; the script was shown to notice eight planted mistakes (swapped workspace, wrong user, weakened assertion, dropped `deleted=True`, re-read of the wrong row, changed When argument, snapshot of the wrong row, `" mp"` → `"mp"`).

- **Local-model tests (88): functional findings in 0 / 88 tests — 88 of 88 (100%) are right as delivered · cosmetic findings in 18 / 88 tests** (17 names cut by the tool at 70 characters; 3 with variable names other than the helper sheet's; 1 blank line after a docstring). Counting only what the model itself wrote: 4 / 88 (FCD-RS-12, RS-17, RS-18, INH-01).
- **Claude-written tests (22 = 7 exemplars + 15 `# [claude]`): functional findings in 0 / 22 · cosmetic findings in 5 / 22** (names cut: FCD-GW-22, RS-08, GA-13, SD-09, RS-10).
- **No local test body was changed after delivery — confirmed.** Against `test_factory.asdelivered.py`: 84 of the 88 local tests are byte-identical (comment line, decorators, signature, docstring, body); FCD-GW-23, GW-24, GA-24, GA-25 differ by the marker only (`strict=True` → `strict=False` plus the longer reason). The exemplar FCD-GW-22 likewise differs by its marker only. "Right as delivered" is said of the bodies: with the strict markers the cards then prescribed, GW-23 / GW-24 made the file go red in some runs — a property of the card's recipe (physical row order), not of anything the model wrote.
- **Stability:** 9 whole-file runs, never red. FCD-GW-22, GW-23, GW-24 xpassed together in 7 of 9 runs and xfailed together in 2; FCD-GA-24, GA-25, GA-26 never xpassed. No strict xfail and no pass card rests on physical row order (argued per card below).
- **Recorder cards:** FCD-GW-26 / GA-28 fail today on the `ORDER BY` assertion of Then 2 (not on the count of SELECTs) and pass against a scratch reference that adds the `ORDER BY`. With the markers on, that reference turns the run red through exactly these two (`XPASS(strict)`), so the alarm works.
- **Never-executed Then lines:** Then 2 – 5 of FCD-RS-19 / RS-20 were executed against a scratch reference of BUG-895 (the two partial unique indexes, created inside the test's transaction): both pass; with only the name index RS-20 fails on Then 1, with only the abbreviation index RS-19 does.
- **Hand-made variants** of the code (34, things the mutation tool does not make): 33 caught, among them a `commit()` in `soft_delete` (FCD-SD-09 alone) and in `restore` (FCD-RS-10 alone). The one not caught — `restore` calls the clock and discards the value — changes nothing observable; it is the cases file's own Spec gap 3.

Limit of this verdict: the spec is IN REVIEW on pilot defaults. If the reviewer changes P1 – P3 or Q1 – Q4, the cards listed in the cases file's Reviewer summary change with them.

## Findings
None functional. Cosmetic only — none blocks PASS, all optional:

| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | Naming (local) — COSMETIC | FCD-GW-21, GA-08, GA-09, GA-27, SD-01, SD-12, RS-06, RS-09, RS-13, RS-17, RS-18, RS-19, RS-20, INH-01, INH-03, INH-04, INH-05 (17 tests) | Test name cut at 70 characters, so it does not carry the whole title. The docstring carries the full ID and title in all 110 tests. Made by the tool, not by the model. | `test_fcd_rs_19__the_database_refuses_a_restore_whose_name_is_used_by_another_live` | optional — tool (`tests/unit/_tools/local_coder.py`) |
| 2 | Naming (local) — COSMETIC | FCD-RS-12 (`row_fd`, `row_fd2`, `row_f3`, `before_written`), FCD-RS-17 (`row2`), FCD-RS-18 (`row_fd`, `row_f9`) | Variable names other than the helper sheet's `row` / `before`. Each is assigned from the right `reread(db, …)` / `written(db)` at the right place and used in the right assertions. | `row_fd2 = reread(db, fd2)`, `before_written = written(db)` | optional — executor |
| 3 | Style (local) — COSMETIC | FCD-INH-01 | A blank line between the docstring and the When call (already noted by the executor). | line 764 | optional — executor |
| 4 | Naming (claude) — COSMETIC | FCD-GW-22, RS-08 (exemplars), FCD-GA-13, SD-09, RS-10 | Same 70-character cut in five hand-written names (the longest hand-written name in the file has 102 characters, so the file is not uniform). | `test_fcd_rs_08__…_loaded_from_the_database_is_left` | optional — executor |
| 5 | Documentation (claude) — COSMETIC | `factory.notes.md` | The header still describes the state before fix round 0: "108 tests for 108 cases", "100 passed · 8 xfailed", "not stable", "Who wrote what (108)", "13 `Author: claude` cards". The xfail location table has no row for FCD-GW-26 / GA-28 and still calls GW-22 … GW-24 a discrepancy. Only the last section ("Fix round 0") gives today's result, and that one is reproduced. | notes line 4 vs. line 154 | optional — executor |
| 6 | Documentation — COSMETIC | `factory.cases.md` | (a) The last rows of the coverage matrix ("BUG-100", "BUG-706") list three cards each and omit FCD-GW-26 / GA-28. (b) The Given sentence "(This moves F1 physically behind F2 in the table.)" of FCD-GW-21 … GW-24 and the "Fails today on" lines of GW-22 … GW-24 hold in a minority of runs only (the three xpassed in 7 of 9 runs here). | cases lines 2128 – 2129; card FCD-GW-22 | optional — case designer |

Checked for and **not** found, in all 88 local tests (by reading and by the rebuild script):
- a missing, extra or reordered Given row; a wrong or missing column — `workspace_id=w2.id`, `is_active=False`, `updated_by=u1.id` / `u2.id`, `deleted=True` (never expanded by hand, never added to a live row, never left off a deleted one); a wrong `of=` on a machine or section; a wrong name or abbreviation (compared as Python values, including `" mp"` with its leading space in FCD-RS-20, `"main plant"` / `"XX"` in RS-19, `"bolt"` / `"Bolt"` in GA-25);
- **a value swapped with another row of the same kind** — looked at in particular on the cards that name two workspaces or two users: FCD-GW-01, GW-02, GA-01, GA-02, GI-03, GI-04, GI-05, GI-10, SD-02 (`updated_by U1`, `deleted_by U2`), SD-08, SD-11, RS-03 (`updated_by U2`, asserted `u2.id`), RS-11, RS-12, RS-18, INH-08, INH-10: none;
- literal-code Given lines: `f1.abbreviation = "ZX"` then `db.flush()` (FCD-GW-21, GW-23, GW-24) and `db.refresh(fi)` (RS-09) stand at the card's place, before the snapshot;
- a changed, dropped or added When argument (`skip=0`, `limit=0`, `limit=-1`, `skip=-1`, `id=0`, `MISSING`, `deleted_by=None`, the dict and schema arguments of the inherited calls, `dao.get(db, <id>)` positional);
- a skipped Then line, an assertion under the wrong `# Then N`, or one weaker than the card: `sorted(...)`, `set(...) <=`, `len`, `in [...]`, `>= 1` occur only where the card itself writes them; ordered lists are compared with `==` in the card's order; `updated_at` is asserted only as `is None` / `is not None`, on the side the card says;
- write cards: every re-read goes through `reread(db, …)` (expires first; the session has `autoflush=False`, so a missing flush shows — see the `no flush` variants); every "unchanged" / "nothing written" snapshot is taken after the last Given line and before the call, and of the row the Then line names; no snapshot the card does not ask for;
- swallowed failures or extra mocks: `pytest.raises` only on `raises:` cards, with the card's type, around `db.begin_nested()`; no `try`, nothing patched in any local test.

The 22 Claude-written tests were read the same way: no functional finding. Points checked: the bulk loops build exactly the card's names, abbreviations, counts and order (FCD-GW-08, GW-11, GW-12, GA-13, GA-14, GA-15); FCD-SD-09 / RS-10 open the savepoint directly before the call, run the in-session checks before `sp.rollback()` and the others after it, and wrap `db.commit` with `wraps=` (it stays callable); FCD-RS-15 / RS-16 take BEFORE after the first Given row and before the Given `dao.soft_delete(...)`; FCD-RS-14 builds MA3 with `is_deleted=True, is_active=False`; the `try / finally` of FCD-GW-26 / GA-28 only removes the listener and swallows nothing.

### xfail tests
| Card | Author | Marker | Fails on (`--runxfail`) | Verdict |
|---|---|---|---|---|
| FCD-GW-22, GW-23, GW-24 | exemplar, local, local | non-strict BUG-100 | Then 2 when they fail (`[F2, F1] == [F1, F2]`, `[F2] == [F1]`, `[F1] == [F2]`) | right line; fail in a minority of runs only — by design after fix round 0 |
| FCD-GW-26 | claude | strict BUG-100 | Then 2, `'ORDER BY' in 'SELECT … FROM FACTORIES WHERE … LIMIT … OFFSET …'` | right line, right reason; `len(selects) == 1` holds |
| FCD-GA-24, GA-25 | local | non-strict BUG-706 | Then 2 (`['Zulu', 'bolt', 'apple', 'Banana'] == ['apple', 'Banana', 'bolt', 'Zulu']`; ids differ at index 0) | right line, right reason |
| FCD-GA-26 | claude | non-strict BUG-706 | Then 1, `['bolt', 'apple'] == ['Banana', 'bolt']` | right line, right reason |
| FCD-GA-28 | claude | strict BUG-706 | Then 2, the `ORDER BY` assertion | right line, right reason |
| FCD-RS-19, RS-20 | local | strict BUG-895 | Then 1, `DID NOT RAISE IntegrityError` | right line, right reason |

**The recorder cards against scratch references** (`DAOFactory` patched in the test process by a pytest plugin in the scratchpad; `app/` untouched):

| Reference | FCD-GW-26 | FCD-GW-22 … GW-24 | FCD-GA-28 | FCD-GA-24 … GA-26 |
|---|---|---|---|---|
| today's code | fails | fail or pass by accident | fails | fail |
| `ORDER BY id` / `ORDER BY lower(name), id` (the fix) | **passes** | pass | **passes** | pass |
| the fix, markers left on (normal run) | **XPASS(strict) → run red** | xpassed | **XPASS(strict) → run red** | xpassed |
| raw list ordered by name, or by `id` descending | passes | all three fail | — | — |
| active list ordered by `id`, by name descending, or by name case-sensitive (collation C) | — | — | passes | all three fail |
| active list `lower(name), id DESC` (wrong tie-break) | — | — | passes | only GA-25 fails |

So FCD-GW-26 / GA-28 fail for the right reason and pass once an `ORDER BY` is there — any `ORDER BY`, as their cards say. Which order it is, is pinned by the non-strict cards, and those report a wrong order only once their markers are off. The notes already tell maintainers to remove the markers of all four tests of a bug together; that step is what makes a wrong `ORDER BY` visible. FCD-GA-25 is the only test for the `id` tie-break.

**FCD-RS-19 / RS-20 against a reference of BUG-895** (an autouse fixture in the scratch plugin creates the two partial unique indexes on `(workspace_id, lower(btrim(name)))` / `…(abbreviation)` `WHERE is_deleted = false` inside the test's transaction):
- both indexes: RS-19 and RS-20 **pass**, Then 2 – 5 executed (`UniqueViolation`; FD still deleted with `T0` / `U1.id`; unchanged(F2)); the passing neighbours RS-17 and RS-18 still pass.
- name index only: RS-20 fails on Then 1; abbreviation index only: RS-19 fails on Then 1 — each card tests its own field.
- Then 3 – 5 are the cards' text exactly. Note that they follow from the test's own savepoint once Then 1 holds (the failed flush is rolled back by `db.begin_nested()`), so they cannot fail on their own unless the DAO commits.
- Whole file with both indexes (`--runxfail`): every pass card still passes, so no Given collides with the future indexes — except FCD-GA-25, whose Given ("bolt" and "Bolt") then fails with `UniqueViolation` (cases Spec gap 6). In that run FCD-GA-24 and GA-26 **passed** without any `ORDER BY`: the planner read through the new index, which happens to be in name order. That confirms the non-strict markers were the right call, and means GA-24 / GA-26 may xpass silently once BUG-895 is fixed; GA-28 stays the alarm for BUG-706.

### Stability
Nine whole-file runs (one with coverage, eight plain): green every time.

| Outcome | Runs | xpassed |
|---|---|---|
| `100 passed, 10 xfailed` | 2 | — |
| `100 passed, 7 xfailed, 3 xpassed` | 7 | FCD-GW-22, GW-23, GW-24 (always the three together) |

FCD-GA-24, GA-25, GA-26: 0 xpasses in 9 runs. Under `--runxfail` the three BUG-100 tests failed or passed in varying combinations (first run: GW-22 and GW-24 passed, GW-23 failed) — the instability the non-strict markers absorb. It is recorded here and not raised as a finding: no run changed between green and red, and the variation is the bug the cards document.

Does anything that can turn the run red still rest on physical row order?
- **Strict xfails (4):** FCD-GW-26 / GA-28 look at the SQL text, not at rows; FCD-RS-19 / RS-20 fail because nothing is raised. None can flip.
- **FCD-GW-21** (pass companion): `len == 2`, `sorted(ids)`, `by_id(result, F1).abbreviation == "ZX"` — no order.
- **FCD-GW-08** ("at least 99 deleted"): 100 deleted + 1 live, page of 100 — any 100 of the 101 rows hold at least 99 deleted ones; `len == 100` and the subset check hold for any order.
- **Bulk and window cards:** FCD-GW-11 / GA-14 (100 of 101: size, distinct, subset), GW-12 / GA-15 (all 101, sorted), GA-13 (exactly one matching row), GW-06 (2 of {deleted, deleted, live}: at least one deleted in any pair), GW-07, GW-13, GW-14, GW-17, GA-16, GA-17, GA-20 (size, distinct, membership), GA-10 / GA-11 (`limit=2` with exactly two matching rows), GA-12 (`skip=1` with one matching row).
- **Every `ids(result) == [...]` in a pass card** has exactly one row on the right (FCD-GW-02, GA-02, GA-05 … GA-08, GA-13, SD-09 Then 3, RS-07 Then 5).

No pass card and no strict xfail can flip on row order.

## Surviving mutants
None — 19 mutants, 19 killed (5 `return … → None`, 4 default `skip` / `limit` constants, 6 `==` → `!=`, 4 boolean constants).

| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| — | — | — | — | no survivor | — |

Score: 19 killed / (19 − 0 excluded) = 100%.

**Beyond the tool.** The tool makes five mutants in `soft_delete` / `restore` (it does not delete statements, add statements or mutate `None`) and cannot add a filter or an order. 34 hand-made variants were loaded through the scratch plugin and run against the 100 passing tests (`-m "not xfail"`):

| Variant | Rule | Failed by |
|---|---|---|
| `soft_delete` **commits** | R5 | FCD-SD-09 |
| `soft_delete` without flush | R1, R5 | SD-01 … SD-11, SD-13, RS-15 (13) |
| `deleted_at` not set / set from another clock | R1 | SD-01, SD-05, SD-08, SD-10, SD-13 |
| `deleted_by` not set | R1 | SD-01, SD-05, SD-08, SD-10, SD-12 |
| also sets `is_active = False` | R2a | SD-04, RS-15 |
| stamps `updated_by` | R2 | SD-02, SD-03, RS-15, RS-16 |
| soft-deletes the factory's machines / sections | R3 | SD-06 / SD-07 |
| does nothing when already deleted | R4 | SD-08 |
| refuses `deleted_by=None` | R8 | SD-13 |
| deletes every live factory of the workspace | R6 | SD-09, SD-11 |
| `restore` **commits** | R5 | FCD-RS-10 |
| `restore` without flush | R1, R5 | RS-01 … RS-07, RS-10 … RS-18 (16) |
| `deleted_at` / `deleted_by` not cleared | R1 | RS-01, RS-06, RS-11, RS-15, RS-16 (+ RS-04) |
| sets `is_active = True` | R3 | RS-06, RS-07, RS-09, RS-16 |
| stamps / clears `updated_by` | R2a | RS-03, RS-04, RS-15, RS-16 / RS-03, RS-15, RS-16 |
| an UPDATE although nothing changes | R4 | RS-08, RS-09 |
| restores every deleted factory of the workspace | R6 | RS-12, RS-17 |
| issues an UPDATE on the other factories | R6 | RS-12, RS-17 |
| makes the factory's deleted machine live | R7 | RS-14 |
| issues an UPDATE on the machines / sections | R7 | RS-13, RS-14 / RS-13 |
| refuses when another factory (any state) has the name | R9 | RS-17 |
| refuses when a live factory of any workspace has the name | R9 | RS-18 |
| `get_by_workspace` hides deleted / inactive rows | R4 / R5 | GW-05, GW-06, GW-07, GW-08, GW-10, GW-25, SD-09 / GW-09, GW-10, RS-07 |
| `get_by_id_and_workspace` hides deleted / inactive rows | R4 / R5 | GI-09, GI-12, GI-13, SD-09 / GI-11, GI-12, RS-07 |
| `limit` capped at 100 in `get_by_workspace` / `get_active_factories` | R2 / R4 | GW-12 / GA-15 |
| `restore` reads the clock and discards the value | R2a (last sentence) | **none** |

33 of 34 caught. The last one is **equivalent in effect**: an unused read of the clock changes no row, no return value and no statement, and any *use* of the value is caught (`deleted_at is None` in FCD-RS-01, RS-06, RS-11; "every column equals BEFORE" in RS-15, RS-16). The cases file declares it itself (Spec gap 3: "the clock is not read — no card of its own"). See Spec coverage.

Single points worth knowing when a card is edited: FCD-SD-09 is the only test that notices a commit in `soft_delete`, FCD-RS-10 the only one for `restore`; SD-06 / SD-07 the only ones for a cascade to machines / sections; SD-08 for the overwritten stamp; SD-13 for `deleted_by=None`; GW-12 / GA-15 for a hidden cap; RS-18 for a cross-workspace name check; GA-25 for the `id` tie-break of the active list. (The remark in the notes that `db.refresh` does not change the outcome of FCD-RS-08 / RS-09 is true, and the two tests still do their job: the "UPDATE although nothing changes" variant is failed by both.)

## Spec coverage
Every rule and error row of every callable has at least one card and one test (checked against the spec, not only against the cases file's matrix): `get_by_workspace` Returns, R1 – R6, both error rows; `get_by_id_and_workspace` R1 – R5; `get_active_factories` Returns, R1, R1a, R2 – R7, both error rows; `soft_delete` R1, R2, R2a, R3 – R8, error row; `restore` R1, R2, R2a, R3 – R9, R9a, error row; inherited R1 – R4, both error rows. No rule without a card.

Parts of a rule without a card — all three declared by the designer, none blocking:
- `restore` R2a, last sentence "The clock is not read" (Spec gap 3) — no card; the hand variant above is not noticed. A card with a spy on `app.dao.factory.utcnow` would pin it; it needs an `Author: claude` card because the Conventions forbid a card to patch the clock.
- `soft_delete` R3 / `restore` R7, "stock" rows (`inventory`) and the seven other tables that point at a factory (Spec gap 2) — deferred to integration tests; machines and sections are covered.
- Spec note "every parameter after `db` is keyword-only" (Spec gap 12) — a note, not a rule; no card.

One thing to plan for: FCD-GA-25 is the only test of the R6 tie-break ("bolt" before "Bolt" by id), and its Given cannot be built once the BUG-895 name index exists (confirmed with the reference above). Being non-strict, it will then xfail on a setup error without anyone seeing it, and the tie-break will have no test.

## Traceability
cases 110 · tests 110 · unmatched: none (each case ID is in exactly one test name; all 110 docstrings equal "`<ID> — <card title>.` / `Rules: <card rules>`") · marker mismatches: none.
- 100 `Expect: pass` cards → no marker. 4 strict xfail cards → `xfail(strict=True)` naming exactly the card's BUG id (FCD-GW-26 BUG-100, GA-28 BUG-706, RS-19 and RS-20 BUG-895). 6 "(non-strict)" cards → `xfail(strict=False)` naming the card's BUG id (FCD-GW-22, GW-23, GW-24 BUG-100; GA-24, GA-25, GA-26 BUG-706), as the Conventions prescribe.
- BUG ids used: BUG-100, BUG-706, BUG-895 — all in `docs/testing/bugs.md`.
- Authorship, from the file and `factory.local-run.json` (88 entries, 88 accepted, 79 on the first attempt, 9 on the second, 0 escalated): 88 tests under `# [local-coder] <ID>`, 15 under `# [claude] <ID>` (FCD-GW-08, GW-11, GW-12, GW-26, GA-13, GA-14, GA-15, GA-26, GA-28, SD-09, RS-07, RS-10, RS-14, RS-15, RS-16), 7 exemplars without a comment (FCD-GW-05, GW-22, GA-22, SD-10, RS-02, RS-08, INH-06).
- `# Then N` comments: present, in order and equal in number to the card's Then lines in all 110. No unused argument. `try` only in FCD-GW-26 / GA-28 (`finally` removes the listener); `patch` only in FCD-SD-09 / RS-10 (the Conventions' commit spy).
- As-delivered copy: 84 local tests identical, 4 marker-only, 0 with another body; scaffold differs by the header docstring and three imports (`patch`, `event`, `machine_dao`); the 15 tests not in the copy are the 15 `# [claude]` ones.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_factory.py -q -p no:cacheprovider --cov=app.dao.factory --cov-branch --cov-report=term-missing -rxX
  app\dao\factory.py   27   0   0   0   100%
  100 passed, 10 xfailed in 6.06s

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_factory.py -q -p no:cacheprovider --runxfail -rf
  8 failed, 102 passed in 3.27s        (FCD-GW-22 and GW-24 passed in this run; the 8 failures on the lines in the xfail table)

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_factory.py -q -p no:cacheprovider -rfEX      (eight more times)
  100 passed, 7 xfailed, 3 xpassed     (7 times; xpassed: FCD-GW-22, GW-23, GW-24)
  100 passed, 10 xfailed               (once)

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/factory.py tests/unit/dao/test_factory.py --json <scratchpad>/fv/mut.json
  Mutants: 19 · killed 19 · timeout 0 · survived 0 · score 100%      (run alone, no pytest beside it)
```
Matches the "Fix round 0" result of the notes (110 tests · 100 passed · 10 xfailed, non-strict ones may show as xpassed; coverage 100%). The notes' header line is older (finding 5).

Extra checks, scratchpad only (`<scratchpad>/fv/`; nothing in the repo written except this report):
```
sbs.py        cards ↔ tests ↔ markers ↔ docstrings ↔ `# Then N` ↔ arguments ↔ as-delivered copy; side-by-side listing used for the read → 0 problems
rebuild.py    expected body rebuilt from each of the 95 vocabulary cards and compared with the test → 0 differences
selftest.py   eight planted mistakes in a copy of the test file → rebuild.py reports each
cos.py        names, argument order, variable names → findings 1 – 4
PYTHONPATH=<scratchpad>/fv/plug FCDREF=<variant> .venv/Scripts/python.exe -m pytest tests/unit/dao/test_factory.py -q -p no:cacheprovider -p ref_fcd …
  order references (12 runs)   → the table under "xfail tests"
  idx / idx_name / idx_abbr    → FCD-RS-19 / RS-20 pass; each fails on Then 1 without its own index
  34 hand variants, -m "not xfail" → the table under "Surviving mutants"
```

## Local-coder patterns
No functional mistake in 88 tests. All 88 were accepted as designed and all 88 are what their cards say.

| Pattern | Count | Example case IDs | Kind | What would prevent it |
|---|---|---|---|---|
| A value swapped between two rows of a kind the card names (workspace, user, the two factories of a collision) | 0 of the 17 cards at risk listed under Findings | FCD-SD-02, RS-03, RS-12, RS-18, GI-04 | — (looked for, not found) | Still guarded by the read only. Tool: the rebuild-and-compare of builder calls (function, every keyword and value) — `fv/rebuild.py` did it for 95 cards with no false alarm and found all eight planted mistakes. |
| A `"…"` value with leading whitespace or differing only in case | 0 of 3 | FCD-RS-19 (`"main plant"`), RS-20 (`" mp"`), GA-25 (`"bolt"` / `"Bolt"`) | — (looked for, not found) | Nothing needed; the card's remark in words ("one space followed by lower-case mp") next to the literal worked. |
| Test name cut at 70 characters | 17 | FCD-RS-19, RS-20, INH-03, INH-04 | cosmetic — tool, not model | Tool: raise the limit or cut on the title's last full phrase. Already listed. |
| Variable names other than the sheet's when several rows are re-read | 3 | FCD-RS-12, RS-17, RS-18 | cosmetic | Nothing needed (the distinct names keep the rows apart). For uniformity: a sheet line "re-read of a second row: `row_<name>`". |
| A blank line after the docstring | 1 | FCD-INH-01 | cosmetic | Tool: strip it on acceptance. |
| First attempt rejected by the tool (from the run report; all nine second attempts are faithful) | 9 | fixture used but not requested: FCD-GW-25, GW-01, GA-01 · a snapshot the card does not ask for: SD-03, RS-06, INH-05, INH-07 · both sides of "nothing written" taken after the call: RS-13 · ran and failed: RS-18 | caught by the tool | The checks exist and work. The four unasked snapshots are one habit ("write card → take a snapshot"); a sheet line "take a snapshot only for a Then line that says unchanged / nothing written" may save the retry. |

Observations for `docs/testing/local-coder-improvements.md`:
- **Then lines after the failing line of an xfail test** (FCD-RS-19, RS-20 Then 2 – 5): right in both. A database-side bug can be given a reference fix as well: one autouse fixture in a scratch plugin that creates the missing indexes inside the test's transaction (rolled back with it) was enough to run them. The tool knows `fails_in_then`; listing "never executed: <ID> Then N…" in its report would tell stage 5 where to do this.
- **Strict xfail on a row order is a card problem, not a model problem.** The two local tests that turned the file red after delivery (FCD-GW-23, GW-24) are the card word for word. A statement-recorder card (FCD-GW-26 / GA-28) is the stable form of "there is an `ORDER BY`"; order cards on physical row order should be non-strict from the start.
- **A non-strict order card says nothing until its marker is off.** FCD-GW-22 … GW-24 xpassed in 7 of 9 runs with the bug present, and FCD-GA-24 / GA-26 passed without any `ORDER BY` as soon as an index on the name existed. When BUG-100 / BUG-706 is fixed, all four markers of that bug must come off together, or a wrong `ORDER BY` stays hidden.
- **What worked:** `deleted=True` as one keyword (37 local "deleted" rows, all right); `of=` for machines and sections; the `raises:` shape with `begin_nested` (9 local tests, all with the right wrapping and type); Then lines written as ready expressions; "(the very object that was passed in)" → `result is x` in all 21 local `soft_delete` / `restore` tests that return; the literal-code Given lines of the BUG-100 recipe and of `db.refresh`.

**Still open (none blocks PASS) — numbered fix list:**
1. Optional, executor: bring the header and the older sections of `factory.notes.md` in line with fix round 0 (finding 5).
2. Optional, case designer: add FCD-GW-26 / GA-28 to the two BUG rows of the coverage matrix; reword the recipe sentence and the "Fails today on" lines of FCD-GW-22 … GW-24, which hold in a minority of runs (finding 6).
3. Optional, case designer: decide FCD-GA-25 before BUG-895 is fixed — with the name index its Given fails and, being non-strict, it will xfail unseen; the `id` tie-break of `get_active_factories` R6 then has no test (Spec gap 6).
4. Optional, case designer / describer: `restore` R2a "the clock is not read" has no card (Spec gap 3) — either an `Author: claude` card with a spy on `utcnow`, or drop the sentence from the rule.
5. Optional, tool (`tests/unit/_tools/local_coder.py`): the 70-character name cut (finding 1); strip a blank line after the docstring; the rebuild-and-compare acceptance check; the never-executed-Then list.
6. Optional, executor: variable names in FCD-RS-12, RS-17, RS-18, the blank line in FCD-INH-01, the five cut hand-written names (findings 2 – 4).
7. Not a test matter: the spec is IN REVIEW; when BUG-100 / BUG-706 is fixed the strict recorder test turns the run red — remove its marker **and** the markers of that bug's three non-strict tests in the same step; BUG-895 → FCD-RS-19, RS-20.
