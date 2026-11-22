# Verification — `app/managers/factory_section_manager.py`

> **Verdict:** PASS
> Tests: 139 passed · 68 xfailed (reproduced ✅) · coverage 100% branch (81 statements, 38 branches, 0 missed)
> Mutation: 81 mutants · 79 killed · 2 survived → score 100% (after excluding 1 equivalent, 0 dead, 1 bug-path)
> Source commit: e48a092 · Cases revision: none stated (READY, spec APPROVED 2026-10-16, 207 cases)

## Summary
- All 207 tests were read against their cards, line by line: every Given row and its columns, the When call and each argument, every numbered Then line (check, type, value, `# Then N` placement). Nothing was sampled. As a second, independent check a script rebuilt the expected body of each of the 173 vocabulary cards (164 local + 9 exemplars) from the card text and the helper sheet and compared it with the test, statement by statement. Read and script agree: **0 functional differences**; 2 tests repeat a re-read (cosmetic). The script was proved on 53 planted mistakes (swapped rows, swapped values, extra and dropped lines, weakened checks, markers): **53 of 53 reported**.
- **Local-model tests (164): functional findings in 0 / 164 — 164 of 164 (100%) are right as delivered.** Cosmetic findings in 41 / 164 (38 names cut by the tool at 70 characters; 3 the model's own: a repeated re-read in FSM-U-10 and U-44, the variable name `row_a1` in D-07). Counting only what the model itself wrote: 3 / 164.
- **Claude-written tests (43 = 9 exemplars + 34 `# [claude]`): functional findings in 0 / 43.** Cosmetic: 26 / 43 names cut at 70 characters.
- "As delivered" was checked against the delivered copy: all 164 local and 9 exemplar test functions are identical to `test_fsm.asdelivered.py`, except the `# noqa: F841` comment on FSM-D-09's Given line. The only other differences are the three `# noqa: F401` removed from the import blocks, three imports added (`contextmanager`, `patch`, `event`), the statement-recorder helpers and the 34 `# [claude]` tests, as the notes say. So the 164 / 164 figure is about the local model's own output.
- All 68 xfail tests fail under `--runxfail` where their cards say. 40 of them (30 local, 10 Claude/exemplar) have 99 Then lines after the failing line that no normal run executes. They were run once against a scratch reference implementation of the intended behaviour (all 21 bugs, BUG-903 … BUG-928, fixed in memory, plus the intended unique index created inside each test's transaction): **207 of 207 pass**. Twelve deliberately wrong references are each caught, several only on a later Then line (see table).
- Mutation: 2 survivors, 1 equivalent and 1 bug-path (BUG-914). Beyond the tool, 42 hand variants were run. Every removed check, every reordered check that changes behaviour, a `commit()` in each of the three writers, and the BUG-908 / BUG-912 / BUG-921 fixes are all caught. Only a commit inside the two readers goes unnoticed (optional, as for the factory manager).
- Stable: 13 whole-file runs (plain, coverage, and with the planner forced to sequential, index and bitmap scans) plus 4 `--runxfail` runs. None was red. No XPASS, no strict xfail or pass card that depends on row order.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | Redundant re-read (local) — COSMETIC | FSM-U-10 Then 3; FSM-U-44 Then 3 and 4 | Card: `re-read SF:` / `re-read S1:` on consecutive Then lines; the sheet says later lines reuse `row`. The test calls `row = reread(db, sf)` again (U-44: twice more). Each assertion still checks the card's value on a fresh re-read of the right row, so nothing is weaker. | `# Then 3\n    row = reread(db, sf)\n    assert row.updated_by == u2.id` | optional — tool check / none |
| 2 | Naming (local) — COSMETIC | FSM-D-07 Then 5 | Re-read of the second row named `row_a1` (the sheet gives no name; FSM-D-08 and the factory tests use `row`). Assigned from `reread(db, a1)` and used in the three right assertions. | `row_a1 = reread(db, a1)` | optional — none |
| 3 | Naming (local) — COSMETIC | 38 tests: FSM-C-02, C-03, C-10, C-13, C-22, C-23, U-05, U-06, U-08, U-09, U-15, U-23, U-25, U-26, U-27, U-30, U-31, U-32, U-35, U-52, U-54, U-55, U-56, G-09, G-11, S-12, S-15, S-16, S-17, S-21, S-22, S-25, S-40, D-01, D-09, D-12, D-15, CN-01 | Test name cut at 70 characters (word boundary). Every docstring has the full ID and title. The tool did this, not the model. | `test_fsm_u_08__a_section_of_a_soft_deleted_factory_is_refused_also_when_its_own` | optional — tool |
| 4 | Naming (claude) — COSMETIC | 26 tests: exemplars FSM-C-01, U-14, D-06, D-08; FSM-C-24 … C-29, C-31, U-50, U-51, U-57, U-58, S-24, S-47, S-48, S-54, S-56, S-57, S-58, S-59, S-63, D-10, D-11 | The same cut in hand-written tests. | `test_fsm_d_11__the_delete_is_flushed_but_not_committed_a_rollback_makes_the_section` | optional — executor |
| 5 | Structure — COSMETIC | file order | The 15 trial tests (FSM-C-05, C-16, C-30, U-24, U-29, U-41, U-49, G-08, G-13, S-17, S-37, S-51, D-07, D-09, CN-11) sit between the exemplars and FSM-C-02, out of card order. The pipeline did this. | line 467 `# [local-coder] FSM-C-05` | optional — executor |

No FUNCTIONAL finding. Looked for in all 164 local tests by reading, and by the rebuild script where marked ✓:
- **Given rows** ✓: no row missing, extra or reordered; every column after "but" present with its value (`factory_id` F2 / F9 / FD / FI, `workspace_id W2.id`, `updated_by U1.id`, `is_active False`, `is_deleted True` on MD, `deleted`). No `deleted=True` on a row the card calls live, and none missing where the card says "deleted" (C-14, U-04 … U-06, U-27, U-52, S-12 … S-18, S-39, S-40, D-06, D-15, CN-06, CN-07, G-07 … G-09).
- **Swaps between rows of one kind** ✓, checked in each of the 63 local cards that build two or more rows:
  - factories F1 / F2 / F9 / FD / FI (U-09 move from FD to F1, U-23 SH in FD with target FD, U-25 / U-26 / U-27 / U-33 S3 in F2, S-19 … S-23 SH in FD and SF in FI, D-14 SF in FI, D-15 SXH in FD);
  - sections S1 / S2 / S3 / S9 / SX / SH (U-13 and U-55 / U-56 act on S2 with S1's name, U-15 S2 in F1 against U-16 S3 in F2, U-59 / D-17 act on S9 in W2);
  - machines and assignments (U-49 A1 of MA1 to **S2**, D-07 A1 of MA1 / A2 of MA2, both to S1, U-29 MD `is_deleted True`, U-28 … U-33 machine of F1);
  - users U1 / U2 (U-48, D-02 `updated_by U1` in the Given with U2 acting, D-06 `deleted_by == U1`, U-49 / D-02 `created_by == U1`);
  - T0 / NOW (D-01, D-17 `NOW`; D-06 `T0`).
- **Text values** ✓ (compared as Python source): `"  Paint "`, `"spray  BAY"`, `"   "`, `"\t"`, `"Paint "`, `" Spray "`, `" Paint "`, `"Paint\n"`, `"Pa int"`, `"Paint 2"`, `"main  hall"`, `"n h"`, `"%"`, `"_"`, `" hall "`, `"HALL"`, `"utt"`, `"plant"`. No raw string, no dropped or added space.
- **When call** ✓: no argument changed, dropped or added. Explicit `None`, `0`, `-1`, `MISSING`, `include_deleted=False`, `exclude_id=None`, `FactorySectionUpdate()`, `name=None` / `factory_id=None` are all kept. G-13 stays positional. The not-yet-existing `include_deleted` on `get_factory_section` is passed unwrapped (G-08, G-10, G-12) and inside `pytest.raises` only where the card has `raises:` (G-09).
- **Then lines** ✓: no line skipped, no assertion under the wrong `# Then N`, none weaker than the card, and none extra (no assert the card does not have). `sorted(…)`, `set(…) <=`, `len(…)` and `"…" in str(exc.value.orig)` appear only where the card writes them; `is True` / `is False` are kept in all 21 CN cards; f-string details stay f-strings with the right row (`{f9.id}`, `{s9.id}`, `{sx.id}`, `{sx9.id}`, `{sh.id}`). FSM-D-09 Then 2 reads `ma1.factory_section_id` on the object without a re-read, as the card says.
- **Snapshots** ✓: every `before…` is taken after the last Given line (after `db.refresh` / `created_before =`) and before the call, and only where the card has `unchanged` / `nothing written`.
- **Error shapes and mocks**: no `try`; `pytest.raises` only on `raises:` cards, with the card's type; `begin_nested` exactly for `IntegrityError` / `DataError`; nothing patched in any local test.

The 43 Claude-written tests were read the same way:
- Bulk loops give exactly the card's rows: `range(1, 101)` → 100, `range(1, 100)` → 99, `range(1, 102)` → 101, with names `f"Bay {k:03d}"` / `f"Old {k:03d}"`, and `deleted=True` only on the "deleted" loops.
- The four direct inserts carry exactly the card's keywords (C-27 with `is_deleted=True, deleted_at=T0, deleted_by=u1.id`; C-28 `factory_id=f2.id`).
- The three race cards patch only `_check_name_exists_in_factory`, with `begin_nested` inside `pytest.raises(HTTPException)`.
- The three rollback cards take the savepoint directly before the call, run the "before" checks, then `sp.rollback()`, then the "after" checks, then the spy count.
- The four recorder checks follow the Conventions definition: S-58 `factory_sections.is_deleted` in a WHERE clause, S-59 `like` in a WHERE clause, S-65 / S-66 `name` after ` order by `, CN-17 "no ` limit ` or `name` in the WHERE clause".
- S-24 takes the snapshot before FD is made live again. D-10 makes its four follow-up calls in the card's order. Every non-strict marker is on exactly the 14 cards Conventions list.

### xfail tests against a reference fix (scratch only)
`fsmv/plug/ref_fsm.py` replaces the six manager methods in memory with the intended rules:
- BUG-911, BUG-912: an existence query over all live rows, normalised.
- BUG-913: 409 on the index violation.
- BUG-914 move check, BUG-919 no-op, BUG-923 `is not None`, BUG-926 / BUG-927 deleted factory, BUG-928 assignments, BUG-908 no clearing.
- BUG-916 / BUG-925: `include_deleted` on get.
- BUG-903 / 904 / 917 / 918 / 921 / 922 / 924: search in SQL with escaped `ILIKE`, ordered by `lower(name), id`.

It also gives the test module trimming, non-blank `FactorySectionCreate` / `FactorySectionUpdate` and creates `UNIQUE (factory_id, lower(btrim(name))) WHERE NOT is_deleted` inside each test's own transaction. Nothing in the repo is edited.

| Reference | Result with `--runxfail` (failing Then line) |
|---|---|
| all bugs fixed | **207 passed**. All 68 xfail tests pass in full, so every Given, call and later Then line agrees with the intended behaviour. No pass test pins a bug, and no Given breaks the intended index. |
| conflict answered with 400 | 14 failed on **Then 2**: C-12, C-22, C-23, C-24, C-29, U-13, U-14, U-25, U-26, U-50, U-51, U-55, U-56, U-57 |
| 409 message shows the existing row's spelling | 11 failed on **Then 3**: C-12, C-22, C-23, C-24, U-13, U-14, U-25, U-26, U-55, U-56, U-57 |
| duplicate saved, then 409 (no index) | failed on **Then 4** (count / nothing written): C-12, C-22, C-23, C-24 |
| no-op update still touches `updated_at` | U-46 **Then 3**, U-43 / U-44 / U-45 **Then 4** |
| list ordered by id only | S-60 … S-64 Then 1, S-65 / S-66 Then 2 |
| no unique index | C-25, C-26, C-29, U-50, U-51 Then 1 |
| move clears the assignments instead of refusing | U-28, U-29 Then 1, U-33 Then 2 |
| hidden section answered 400 instead of 404 | G-07, G-11 **Then 2** |
| delete in a deleted factory answered 404 (alternative not taken) | D-13 **Then 2** |
| delete still clears assignments (BUG-908 open) | D-07 **Then 3**, D-09 Then 2 |
| search pattern not escaped | S-30, S-31, S-32 (pass cards, HR-8) |
| `include_deleted=True` still hides sections of a deleted factory | S-21, S-22 |

Then lines after the failing line (never run today; all ran in the first row of the table):
- C-18 … C-20 (2), C-22, C-23 (2–5), C-24 (2–4), C-25, C-26 (2), C-29 (2–5);
- U-07 (2–5), U-08 (2–4), U-09 (2–5), U-24 (2–4), U-25, U-26, U-28, U-29 (2–5), U-33 (2–4), U-39, U-40 (2), U-43 … U-45 (4), U-46 (3), U-50, U-51, U-55, U-56 (2–5), U-57 (2–4);
- G-07 (2–4), G-08 (2), G-09 (2–3), G-10 (2), G-11 (2–4), G-12 (2);
- S-19 (3), S-20 (2), S-55 (2), D-07 (4–6), D-13 (2–5).

That is 76 lines in 30 local tests and 23 in 10 others.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 55 | 168 | `exclude_unset=True` → `False` | equivalent | `exclude_none=True` stays, and both fields of `FactorySectionUpdate` default to `None`, so a field that was not sent is dropped either way. Re-run as hand variant `mut55`: 139 passed, 68 xfailed, identical to today, xfails included. | — |
| 30 | 153 | `section_data.name and section_data.name != section.name` → `or` | bug-path (BUG-914; also BUG-913 / BUG-915) | The mutant runs the name check whenever a name is sent, also the current one. Re-run with xfails visible (`mut30`): no pass test changes, and the strict xfail **FSM-U-26** (move re-sending the current name into a factory where it is taken, BUG-914) XPASSes. Otherwise it differs only when two live sections already share a name (BUG-913) or for `name=""` (BUG-915), states the spec forbids as Given. Once BUG-914 is fixed the check must run on every move, and the mutant becomes part of the fix. | — (resolves with BUG-914) |

Score: 79 killed / (81 − 1 equivalent − 0 dead − 1 bug-path) = 79 / 79 = **100%**. No `test-weakness`, `case-missing` or `spec-gap` survivor. No dead code is specified for this module (the assignment-manager import goes with the BUG-908 fix, FU-5).

**Beyond the tool.** 42 hand variants of today's code (`fsmv/plug/var_fsm.py`: module source with one text replacement, exec'd in memory and installed on the class) were run against the whole file. Strict-xfail XPASSes count as failures.

| Variant | Failed by |
|---|---|
| create: 404 check removed | C-04 … C-08 |
| create: deleted-factory check removed | C-09, C-10 |
| create: duplicate check removed | C-12 only |
| create: duplicate before deleted-factory check | C-10 only |
| create: `created_by` not set | C-01, C-14, C-30 |
| create: **commits** | C-31 |
| update: section 404 removed / deleted check removed | U-02, U-03 / U-04, U-05, U-06, D-10 |
| update: target 404 removed / target deleted removed | U-18, U-19, U-20, U-32 / U-22, U-23, U-31 |
| update: duplicate check removed | U-13, U-14 |
| update: deleted check moved after the move / name checks | U-05, U-06 |
| update: name check before the factory checks | U-23 only |
| update: target always the current factory | U-14, U-15 |
| update: `updated_by` not set | U-01, U-10, U-12, U-17, U-48, U-54 (+ U-43 … U-46 flip) |
| update: `exclude_none` dropped / unset fields included | U-34, U-35 / 19 tests |
| update: **commits** | U-58 |
| update: `exclude_id=None` in the name check | none today (equivalent: with exact compare the section never matches its own different name). With the BUG-912 fix it is caught by **U-12** (variant `fix912_no_exclude`). |
| get: 404 removed | G-04, G-05 |
| search: deleted filter removed | S-12, S-13, S-14, S-18, S-39, D-10 |
| search: text filter removed / not lower-cased | 10 tests / S-25 only |
| search: `skip` / `limit` not passed on | S-42 … S-46, S-49 … S-52 |
| search: text filter before deleted filter | none (equivalent: the two filters commute) |
| delete: 404 removed / already-deleted removed | D-04, D-05 / D-06, D-10, D-15 |
| delete: already-deleted before 404 | none (equivalent: same outcome for every input) |
| delete: assignments cleared before the soft delete | none (equivalent today; BUG-908 path) |
| delete: **commits** | D-11 |
| check: deleted rows not skipped / `exclude_id` ignored / workspace ignored | C-14, U-52, D-10, CN-06 / CN-18 only / CN-04, CN-17 |
| get / search: **commits** | **none** (open note 1) |
| **BUG-908 fixed** (no `clear_for_section`) | flips **D-07, D-09** (strict, BUG-908). Nothing else changes; D-08 and D-11 still pass. |
| **BUG-912 fixed** (compare `strip().lower()`) | flips **C-22, U-55, CN-08, CN-09, CN-10, CN-11** (exactly the 6 BUG-912 cards). C-23 and U-56 (BUG-915) stay xfailed: their message must also show the trimmed name. U-12 (own name in another case) still passes. |
| **BUG-921 fixed** (search trimmed, whitespace-only means none) | flips **S-36, S-37, S-38** (the 3 BUG-921 cards) |
| the unchanged source (`none`) | 139 passed, 68 xfailed |

Single points to keep in mind when a card is edited (each is the only test that notices its variant): FSM-C-12, C-10, U-23, S-25, CN-18, C-31, U-58, D-11.

## Spec coverage
Every rule of every specified callable has at least one card and one test (script: each card's `Rules:` line against the spec's rule list):

| Callable | Rules | Errors rows |
|---|---|---|
| `create_factory_section` | 10 | 5 |
| `update_factory_section` | 19 | 8 |
| `get_factory_section` | 5 | 1 |
| `search_factory_sections` | 13 | 2 |
| `delete_factory_section` | 12 | 4 |
| `_check_name_exists_in_factory` | 7 | — |

**66 rules, none without a card**; every Errors row has a card; no card cites a rule the spec does not have.
- Rules whose only cards are xfail (never run in a normal run today; all ran against the reference): `update_factory_section` R8a, R15; `get_factory_section` R3, R4; `search_factory_sections` R2a, R3, R4; `delete_factory_section` R5a, R5b.
- Not specified and without cards, as the spec says: `__init__` and the module singleton. `include_deleted` reachability (R6, BUG-920) is integration-only: no xfail card, and the manager rule holds today (S-15, S-16).

## Traceability
cases 207 · tests 207 · unmatched: none (each case ID in exactly one test name; all 207 docstrings equal "`<ID> — <card title>.` / `Rules: <card rules>`") · marker mismatches: none.
- **Markers.** 139 `Expect: pass` cards have no marker. 54 strict and 14 non-strict `xfail` markers match the cards' `Expect` lines; each reason names exactly the card's bug.
- **By bug:** BUG-903 2 · 904 1 · 908 2 · 911 5 · 912 6 · 913 5 · 914 2 · 915 10 · 916 4 · 917 7 · 918 5 · 919 4 · 921 3 · 922 1 · 923 1 · 924 1 · 925 2 · 926 3 · 927 1 · 928 3 = 68, as the cases file states. All 21 bug IDs of the spec (BUG-920 included) are in `docs/testing/bugs.md`.
- **Authorship**, from the file and `factory_section_manager.local-run.json`:
  - 164 tests under `# [local-coder] <ID>`. The report has 164 entries, all `accepted`, and their function names equal the file's. 157 were accepted on the first attempt, 7 on a retry (U-29, U-39, G-07, G-09 on the 2nd; C-11, C-19, G-11 on the 3rd).
  - 34 under `# [claude] <ID>` = the 34 `Author: claude` cards.
  - 9 exemplars without a comment.
- **Test bodies.** `# Then N` comments are present, in order and equal in number to the card's Then lines in all 207. No fixture is requested and left unused, and none is used without being requested.
- **Mocks:** `app.dao.factory_section.utcnow` (autouse; the spec's one external); `patch.object` only in FSM-C-29, U-50, U-51 (race) and C-31, U-58, D-11 (commit spy). No `try`, no broad `pytest.raises`.
- **xfail location** (`--runxfail`, script `xfloc.py`): 68 failed, each where its card says.
  - G-08, G-10, G-12 fail in the When call with `TypeError … 'include_deleted'`; their cards say "Then 1 (the call raises TypeError …)".
  - G-09 raises the same `TypeError` inside its `pytest.raises` block; U-24 raises `IntegrityError` (`factory_sections_factory_id_fkey`) inside its `pytest.raises(HTTPException)`. Both are as their cards say.
  - C-16, U-37, U-38, U-46, D-09 fail on Then 2; U-43 … U-45 and D-07 on Then 3; S-19, S-58, S-59, S-65, S-66 and CN-17 on Then 2; all others on Then 1.

## Stability and row order
- Plain runs: coverage run + 6 runs → `139 passed, 68 xfailed` each, no XPASS.
- `PGOPTIONS` forcing the planner (verified to take effect: `EXPLAIN` under `enable_seqscan=off` shows an index plan), 2 runs + 1 `--runxfail` each:

  | Planner | Plain runs | `--runxfail` |
  |---|---|---|
  | sequential (index / bitmap / index-only off) | `139 passed, 68 xfailed` | `68 failed, 139 passed` |
  | index (seq / bitmap off) | `139 passed, 68 xfailed` | `68 failed, 139 passed` |
  | bitmap (seq / index off) | `139 passed, 68 xfailed` | `68 failed, 139 passed` |

  Never red; none of the 14 non-strict tests XPASSed here (the notes saw FSM-C-24 XPASS once in 10 runs; allowed).
- **Judgement.** No pass card and no strict xfail rests on row order:
  - Every pass card that returns several rows compares `sorted(ids)` or a set / `len`. S-44 / S-45 accept either row. S-47 / S-48 check size and membership only. CN-14 fits its 100 rows into one page. The single-row `ids(...) == [x]` checks have only one candidate.
  - The strict xfails fail on an exception, a boolean, a recorder check or a list that is wrong in every order. S-19's `[S1.id]` is wrong today in any order, because SH is listed too.
  - Every card that depends on which rows form a page is among the 14 non-strict ones.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/factory_section_manager.py tests/unit/managers/test_factory_section_manager.py --json <scratchpad>/fsmv/mut.json
  Mutants: 81 · killed 79 · timeout 0 · survived 2 · score 98%      (raw; run alone from this side, no other pytest of mine beside it)
  SURVIVED #30 L153:11 bool: And -> Or · #55 L168:60 const: True -> False

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_factory_section_manager.py -q -p no:cacheprovider --cov=app.managers.factory_section_manager --cov-branch --cov-report=term-missing -rX
  app\managers\factory_section_manager.py      81      0     38      0   100%
  139 passed, 68 xfailed, 15 warnings in 15.23s

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_factory_section_manager.py -q -p no:cacheprovider -rX      (6 times)
  139 passed, 68 xfailed in 7.26–7.51s       (no XPASS)

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_factory_section_manager.py -q -p no:cacheprovider --runxfail -rf
  68 failed, 139 passed in 7.4s

PGOPTIONS="<seq | index | bitmap settings>" … (2 plain + 1 --runxfail each)  → as under "Stability"
```
These match the notes' Result line (139 passed · 68 xfailed · branch coverage 100%, 81 statements, 38 branches). There is no flaky test.

Extra checks, scratchpad only (`<scratchpad>/fsmv/`; nothing in the repo written except this report):
```
audit.py      cards ↔ tests ↔ markers ↔ bugs.md ↔ docstrings ↔ `# Then N` ↔ arguments ↔ delivered copy; rebuild of 173 vocabulary
              cards → 2 differences (U-10, U-44: repeated re-read), 1 variable name (D-07)
selftest.py   53 planted mistakes (row / value swaps, extra and dropped lines, weakened checks, markers, snapshots) → 53 reported
listing.txt   card-next-to-test listing of all 207 tests, used for the read
xfloc.py      failing line of each --runxfail failure mapped to its `# Then N` → 65 on the card's Then line, 3 in the When as designed
PYTHONPATH=<scratchpad>/fsmv/plug FSMREF=fix[+<bad>] … -p ref_fsm --runxfail      → reference table above
PYTHONPATH=<scratchpad>/fsmv/plug FSMVAR=<variant> … -p var_fsm -rfX              → hand-variant table above
```

## Fix list
Nothing is required. Verdict PASS.
1. **Optional — case designer.** A commit inside `get_factory_section` / `search_factory_sections` is noticed by no test. Their Side effects are "none"; the three writers are covered (C-31, U-58, D-11). Same open note as the factory manager.
2. **Optional — tool / executor.** Cosmetic findings 1–5: repeated re-reads (U-10, U-44), `row_a1` (D-07), names cut at 70 characters (38 local, 26 Claude-written), trial tests out of card order.
3. **Not a test matter.** When a bug is fixed, its strict markers come off by hand; the 14 non-strict tests do not announce their fixes (notes, "Notes for maintainers"). The BUG-914 fix will also absorb surviving mutant #30.

## Local-coder patterns
No functional mistake in 164 tests: all 164 were accepted as designed, and all 164 are what their cards say, as delivered, with no repair.

| Pattern | Count | Example case IDs | Kind | What would prevent it |
|---|---|---|---|---|
| A row or value swapped between two rows of a kind (factory, section, machine / assignment, user, time) | 0 in the 63 local cards that build two or more rows | U-49, D-07, U-13, U-55, U-23, U-09, D-02 | — (looked for, not found) | Only the read and the verifier's rebuild-and-compare guard this; the tool's own checks would not see it. The rebuild (builder calls with every keyword and value, call arguments, one block per Then) ran over 173 cards here with no false alarm and caught 53 / 53 planted mistakes. Worth moving into the tool. |
| The same row re-read again on a later Then line instead of reusing `row` | 2 | FSM-U-10, U-44 | cosmetic | Tool: flag `row = reread(db, X)` when `row` already holds X; or a sheet line "never re-read a row that `row` already holds". |
| A second re-read row given its own name | 1 | FSM-D-07 (`row_a1`) | cosmetic | Nothing needed; for uniformity a sheet line "re-read of a second row: `row_<name>`". |
| `result = …` inside `pytest.raises`; `snap(x) == snap(x)` both after the call; `count == before` instead of the card's number; a builder used but not requested | 7 retries (all caught by the tool; right on the 2nd or 3rd attempt) | G-07, G-09, G-11; U-29, G-11; C-19; C-11; U-39 | caught before acceptance | Already caught by the tool. The `snap` pair could become a sheet line ("the `before_…` line goes before the When call"). |
| Test name cut at 70 characters | 38 | U-08, S-17, D-09 | cosmetic — tool, not model | Tool: raise the limit or leave as is; the docstring carries the full title. |

Observations for `docs/testing/local-coder-improvements.md`:
- **Then lines after an xfail's failing line are checked by nothing in the pipeline.** Here that is 76 lines in 30 local tests (and 23 in 10 others). All were right: a scratch reference (about 230 lines, schemas and the unique index included) ran them, and 12 wrong references were each caught. The tool could list "never executed: <ID> Then N…" in its report.
- **What worked:**
  - `deleted=True` as one keyword: 32 local "deleted" rows, none expanded by hand, none on a live row.
  - "but `factory_id …`, `workspace_id …`, deleted" as three keywords (S-17, G-09).
  - Given code lines run in place (`db.refresh`, `created_before`, `loaded_section_id`).
  - The `IntegrityError` / `DataError` sheet snippet: 7 of 7 right.
  - `include_deleted` on `get` passed as the card writes it: 4 of 4.
  - Every whitespace, tab, newline, `%` and `_` literal exact.
- **Single-point checks to keep in mind when a card is edited** (each is the only test that notices its variant): FSM-C-10, C-12, U-23, S-25, CN-18, C-31, U-58, D-11.
