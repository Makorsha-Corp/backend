# Local-coder improvements log

Tracks how well the local model does as the stage-4 test writer, what went
wrong in each run, and what was changed because of it.

- **Local model:** Qwen3.6-35B-A3B (Q4_K_M) on llama-server, 16,384-token context, thinking off.
- **Runner:** `tests/unit/_tools/local_coder.py` — one case card per request, two repair attempts.
- **Quality gate:** the Claude executor's finishing step, then the verifier.

How to use this file: after each module, add a row to "Runs", add any new
mistake pattern to "Problems and fixes", and update the status of older ones
(`open` → `fixed, untested` → `confirmed` once a later run shows it gone, or
`still happening`).

## Runs

| # | Date | Module | Cards sent | Accepted 1st try | Accepted after retry | Handed back | Accepted tests later found wrong | Verifier |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-10-10 | `app/managers/account_manager.py` | 185 | 168 | 15 | 2 | **47 of 183** — 16 found by the finishing step (10 xfail failing for the wrong reason, 6 hollow "unchanged" checks) + 31 found by the verifier (35 deviations) | Round 1: NEEDS WORK on fidelity only (mutation score 100%). Round 2, after a Claude fix round (12 findings + 20 more tests from its sweep): **PASS**, 0 findings in 189 tests |
| 2 | 2026-10-10 | `app/dao/inventory.py` | 178 | 153 | 25 (23 on the 2nd attempt, 2 on the 3rd) | 0 | **2 of 178 functionally wrong** (INV-ST-13 wrong factory in a shorthand row, INV-EN-13 count asserted relative to a snapshot) — both found by the verifier, 0 by the finishing step; plus 9 cosmetic (2 copied name slugs, 1 stray comments, 6 docstring full stops) and 474 unused arguments / bindings removed by script | Round 1: NEEDS WORK for those 2 + cosmetics only (mutation score 100%). Round 2, after two one-line fixes: **PASS**, 0 findings in 191 tests |
| 3 | 2026-10-10 | `app/dao/inventory_ledger.py` | 161 (12 trial + 149 full run) | 160 | 1 (LED-BAL-01: fixtures named only in the When call were not requested; the tool's rejection fixed it) | 0 | **0 of 161 functionally wrong** — verifier read all 161 against their cards and also rebuilt each expected body by script: 0 differences. 22 cosmetic (21 names cut at 70 characters by the tool, 2 of them mid-word from the trial; 1 argument order) and 16 unused builder bindings in 8 trial tests removed by the finishing step | Round 1: **PASS**, 0 functional findings in 170 tests; mutation 65 mutants, 56 killed, 9 survivors (6 dead, 3 bug-path), score 100% |
| 4 | 2026-10-10 | `app/dao/machine.py` | 199 (15 trial + 79 + 105; the run was stopped once for low memory and resumed) | 185 | 14 (13: fixture used but not requested; 1: `count:` asserted against a snapshot) | 0 | **1 of 199 functionally wrong** (MCH-SA-32: "assignment of M1 to S1" built with `to=s3`) — found by the verifier, 0 by the finishing step. Cosmetic: 16 by the model (argument order 11, variable names 5), 53 names cut at 70 characters by the tool | Round 1: NEEDS WORK for MCH-SA-32 only; mutation 91 mutants, 64 killed, 27 survivors (9 dead, 15 bug-path, 3 equivalent), score 100%. The verifier also ran the 22 BUG-886 tests against a scratch reference implementation: all 22 pass. Round 2, after the one-line fix: **PASS**, 0 findings to fix in 216 tests |
| 4b | 2026-10-10 | `app/dao/machine.py`, cases revision 1 (`restore` kept after review, +29 cards) | 19 | 17 | 1 (fixture not requested) | 1 (MCH-SA-130: false rejection by the runner's text check on an escaped literal, P19; written by Claude) | **0 of 18 functionally wrong**; cosmetic: 6 by the model (argument order 3, variable names 2, blank line 1), 10 names cut by the tool | Round 3: **PASS**, 245 tests; mutation 91 mutants, 67 killed, 24 survivors (6 dead, 15 bug-path, 3 equivalent), score 100%; the 3 `restore` mutants are now killed |
| 5 | 2026-10-11 | `app/managers/factory_manager.py` (first manager since run 1) | 172 (21 trial + 65 + 86; stopped once for low memory and resumed) | 169 | 3 (FAC-G-03, G-04, G-08: unused `result =` inside `pytest.raises`) | 0 | **0 of 172 functionally wrong** — verifier read all 172 against their cards and rebuilt each expected body by script; no value or row swapped in the 98 cards that build two or more rows. Cosmetic: 5 by the model (variable names), 45 names cut at 70 characters by the tool | Round 1: NEEDS WORK on paperwork only (FAC-S-49, S-50, S-51 loosened to non-strict at finishing while the cards still said strict); mutation 85 mutants, 82 killed, 3 survivors (1 equivalent, 2 bug-path), score 100%; all 201 tests pass against a scratch reference fix of BUG-893 … 902. One case gap found by hand variants: no card checked "no commit" for create / update — two Claude cards added (FAC-C-36, FAC-U-52). Round 2: see `factory_manager.verify.md` |
| 6 | 2026-10-11 | `app/dao/factory.py` | 88 (17 trial + 71) | 79 | 9 (3 fixtures not requested, 4 unasked snapshots, 1 snapshot taken after the call, 1 ran and failed) | 0 (FCD-INH-06 was hand-written as an exemplar after a false rejection by the runner, P20) | **0 of 88 functionally wrong** — verifier read all 88 and rebuilt 95 expected bodies by script: 0 differences. Cosmetic: 4 by the model (3 variable names, 1 blank line), 17 names cut by the tool | Round 1: **PASS**; mutation 19 mutants, 19 killed; 34 hand variants, 33 caught (the other is equivalent in effect). Before verification the finishing step found three strict order xfails passing by accident in 6 of 9 runs (physical row order): five order cards were made non-strict and two strict statement-recorder cards added |
| 7 | 2026-10-12 | `app/dao/factory_section.py` | 67 (21 trial + 46) | 62 | 5 (FSD-GF-37 duplicate assignment refused by the database, GF-38 fixture not requested, SD-02 and RS-08 unused snapshot, GF-17 rejected by the new P21 check) | 0 | **0 of 67 functionally wrong as delivered** — verifier read all 67 and rebuilt 73 expected bodies by script: 0 differences; all 32 two-value Then lines fully asserted. In the trial, before P21, FSD-GF-17 was accepted twice with one assert missing; that test was deleted and re-run. Cosmetic: 7 tests by the model (variable names, repeated re-reads), 27 names cut by the tool | Round 1: **PASS**; mutation 9 mutants, 9 killed; 54 hand variants, 52 caught (the 2 missed are small case / spec gaps: an outer join eating page places, and filtering on the factory's workspace instead of the section's). 12 whole-file runs under forced sequential, bitmap and index scans: never red |
| 8 | 2026-10-16 | `app/dao/machine_section_assignment.py` (first module of the factory-section group, worked bottom-up) | 57 (18 trial + 39) | 50 | 6 (model slips caught by the runner: Given row left out, fixture not requested, `# Then N` missing or out of order) | 1 (MSA-UP-19: the model put `# Then 1` after the `pytest.raises` block; the runner refused all 3 attempts; written by Claude) | **0 of 56 delivered tests functionally wrong** — verifier read all 56 and rebuilt 63 expected bodies by script (28 of 28 planted mistakes caught): 0 differences. Cosmetic: 2 stray blank lines by the model, 16 names cut by the tool | Round 1: **PASS**; mutation 14 mutants, 13 killed, 1 bug-path (the BUG-907 cap itself); 45 hand variants, 38 caught, the rest bug-path or equivalent plus one small gap (a cap of 2 or 3). Server started and stopped by the pipeline for the first time (`llm_server.py`) |
| 9 | 2026-10-16 | `app/managers/machine_section_assignment_manager.py` | 40 (16 trial + 24) | 34 | 4 (builder not requested ×2, a dropped `created_by` check, a wrong Then numbering) | 2 (MSM-SET-26: kept adding a 'nothing written' line the card does not have; MSM-CLR-02: `unchanged(AD)` for the card's `unchanged(MD)` — a swapped row, refused because the test failed; both written by Claude) | **0 of 38 delivered tests functionally wrong** — verifier read all 38, rebuilt 46 bodies by script (40 of 40 planted mistakes caught): 0 differences; no swapped row got through. Cosmetic: 19 names cut by the tool | Round 1: **PASS**; mutation 19 mutants, 19 killed; 25 hand variants, 22 caught (3 equivalent or bug-path). P22 exercised: the `loaded = …` Given lines were kept verbatim in all six tests |
| 10 | 2026-10-17 | `app/managers/factory_section_manager.py` (339 lines; the group's last and largest module, 207 cards) | 164 (15 trial + 149) | 157 | 7 (model slips caught by the runner, e.g. a snapshot taken after the call) | 0 | **0 of 164 functionally wrong** — verifier read all 164, rebuilt 173 bodies by script (53 of 53 planted mistakes caught incl. row and value swaps); all 207 tests pass against a reference with the 21 bugs fixed, 12 wrong fixes each caught. Cosmetic: 3 by the model (repeated re-reads, one variable name), 38 names cut by the tool | Round 1: **PASS**; mutation 81 mutants, 79 killed, 1 equivalent, 1 bug-path; 42 hand variants, all behaviour changes caught except a commit inside the two readers (no card, as for the factory manager) |
| 11 | 2026-10-17 | `app/dao/item_tag.py` (item group, first module) | 70 (25 trial + 45) | 62 | 8 (`w1` not requested ×6, an unused snapshot, a syntax error) | 0 in the end (INH-07 handed back once in the trial, accepted on re-run) | **0 of 70 functionally wrong** — verifier read all 70, rebuilt 76 bodies by script (32 of 32 planted mistakes caught): 0 differences | Round 1: **PASS**; mutation 22 mutants, 22 killed; 28 hand variants, all caught except 1 equivalent and 1 bug-path; with the four bugs fixed in a scratch reference all 92 tests pass |
| 12 | 2026-10-18 | `app/dao/item_tag_assignment.py` | 68 (18 trial + 50) | 58 | 10 (fixture not requested, `count:` against a snapshot instead of the card's number, unused snapshot) | 0 | **0 of 68 delivered tests functionally wrong** — verifier read all 68, rebuilt 75 bodies by script (43 of 43 planted mistakes caught, incl. the trial's extra `workspace_id`). In the trial ITA-INH-13 was accepted with an extra builder keyword (P23); it was deleted and re-run before delivery. Cosmetic: 1 variable name by the model, 17 names cut by the tool, 5 blank lines after a docstring | Round 1: **PASS**; mutation 27 mutants, 27 killed; 19 hand variants, all caught; with the three order fixes in a scratch reference all 88 pass |
| 13 | 2026-10-18 | `app/managers/item_manager.py` (item group; 187 cards, 9 of them `Author: claude`, 9 exemplars) | 169 (trial and full run together) | 143 | 22 (17 on the 2nd attempt, 5 on the 3rd) | 4 (ITM-FS-11: `DataError` call without `db.begin_nested()`, then `db.rollback()`, which wiped the Given rows; D-17: Given row MC1 left out, the factory passed as the machine (FK error in setup); D-33: WT1 built as `mk_wo.__globals__['mk_wo']("Repair")` instead of `mk_wt1()`; D-47: stock built as a raw `Inventory(...)` without `workspace_id` instead of `mk_stock`. All four are model faults: the cards are right and the sheet showed each builder / pattern; written by Claude) | **1 of 165 functionally wrong as delivered** (ITM-D-43: an extra Given row `mk_stage("IN_PROGRESS")` the card does not list — the work order's `status` also built as a stage; harmless to the outcome) — found by the verifier, 0 by the finishing step (mechanical sweep). Verifier read all 165, rebuilt 178 bodies by script (324 of 324 planted mistakes caught). Cosmetic, model: 3 unused `as exc` (L-08, U-05, D-04; P28), 2 "but" columns set by attribute + flush after the builder (D-23, D-34, which also names a WO line `pol`), 2 plain items built from recipe I1 with both names overridden (FS-06, FS-07), 2 parenthetical defaults written as `usage_count=0` (U-35, U-36); 20 names cut by the tool | Round 2: **PASS** — ITM-L-09 and FS-12 added by Claude, #36/#37 killed; score 77 of 77 counted. Round 1: **NEEDS WORK** — D-43 and the cosmetic forms fixed by the verifier (test file only, re-run); open: 2 `case-missing` survivors for the case designer (default `limit` of `list_items_filtered` 100 and of `find_similar_items` 5). Mutation 91 mutants, 75 killed, 16 survivors (6 dead, 2 equivalent, 6 bug-path, 2 case-missing), score 97%. All 187 tests pass against a scratch reference with the bugs fixed (165 Then lines after xfail failing lines run, 142 of them in local tests); 20 wrong references and 20 R9 / R9b blocker-list variants each caught; commit spies catch a commit in every writer |

"Accepted tests later found wrong" is the number that matters: it counts
tests the runner kept that a later stage had to repair.

## Problems and fixes

| # | Found in run | Problem | Count | Root cause | Fix | Where | Status |
|---|---|---|---|---|---|---|---|
| P1 | 1 | xfail test fails for the wrong reason: a fixture is used but not requested, so the test dies in setup | 8 | Runner accepted any failure of an xfail test | Reject before running when a fixture name is used but missing from the arguments; "called directly" / `FixtureFunctionDefinition` count as setup errors; an xfail with no failure line is never accepted | runner | **confirmed in run 2** |
| P2 | 1 | "Fails today on: … raises `TypeError`" turned into `with pytest.raises(TypeError)`, inverting the test (ACC-S-02, ACC-UN-12) | 2 | The line was shown to the model and read as an instruction | The line is no longer sent to the model; `pytest.raises(X)` is rejected unless the card has a Then line naming X; new prompt rule 13 | runner, prompt | **confirmed in run 2** |
| P3 | 1 | xfail test could fail on any line and still be kept | — (the cause behind P1, P2) | No link between the failing line and the card | Model writes `# Then N` before each Then line's assertions; runner maps the failing line to a Then number and compares it with the card's "Fails today on: Then N" | runner, prompt, case-designer skill | **confirmed in run 2** |
| P4 | 1 | "unchanged" check with the snapshot taken after the call — compares a row with itself (ACC-C-33, U-48, D-17, D-18, UN-14) | 5 | Nothing checked snapshot order | Reject an assert that compares two results of the same helper when both are taken after the When call; prompt rule 14 | runner, prompt | **confirmed in run 2** |
| P5 | 1 | Snapshot taken and never compared (ACC-D-03) | 1 | Nothing checked unused variables | Reject a variable assigned from a helper and never used | runner | **confirmed in run 2** |
| P6 | 1 | One half of a two-part Then line skipped: the global `financial_audit_logs` count (ACC-U-40, D-06, A-11) | 3 of 4 such lines | Only the end result (pass / xfail) was checked | Every numbered Then line needs its `# Then N` comment with at least one assertion under it | runner, prompt; cards: one obligation per numbered line | **confirmed in run 2** |
| P7 | 1 | Wrong actor copied from an exemplar: `u2.id` where the card says U1 (ACC-U-16, handed back) | 1 | The only exemplar asserting `assigned_by` used `u2` | Exemplars must use each actor of a pair at least once in an assertion | executor skill | fixed, untested |
| P8 | 1 | Invalid expression copied from a card: `SNAP(**FILLED, bank_details=…)` repeats a keyword (ACC-U-41) | 1 | Card text looked like code but was not valid code | Cards must not write convention calls with a repeated keyword; helper sheet shows the valid form; that `TypeError` now counts as a setup error | case-designer skill, executor skill, runner | fixed, untested |
| P9 | 1 | Unused fixture arguments and unused `aN = …` bindings (cosmetic) | 74 signatures | Model requests every fixture it has seen | Removed in the finishing step by script; not rejected by the runner (it would cost retries for no gain in correctness) | executor skill | run 2: 474 removals; now stripped by the runner at acceptance (`tidy_args`) — fixed, untested |
| P10 | 1 | "in particular …" literal values after `unchanged(X)` not asserted — snapshot only (ACC-A-10, U-17, AT-03, D-13, U-49 …) | 17 | A numbered line carrying two obligations gets one statement; the helper sheet already said it and was ignored | Cards put the literals on their own numbered line; runner rejects a test that never writes a quoted value from a Then line; prompt rule 15 | case-designer skill, runner, prompt | **confirmed in run 2** |
| P11 | 1 | Helper-sheet example copied whole: "A1, but deleted" built as `mk_account(deleted=True, account_code="SUP-001")` | 8 | The sheet's only "deleted" example carried a second change | Sheet examples show exactly one change; runner rejects a builder keyword the card does not mention (unless a Conventions name the card uses implies it); prompt rule 16 | executor skill, runner, prompt | **confirmed in run 2** |
| P12 | 1 | Given not built as written: qualifier dropped (ACC-G-06: "A9, but deleted" built live), extra column carried over from the previous card (U-25), rows inserted in the wrong order (UN-01) | 3 | Nothing checked the Given | Extra columns: covered by P11's check. Dropped qualifier and row order: **no automatic check yet** — verifier only | runner (partly) | open |
| P13 | 1 | Literal replaced by a derived value (`usage_count == before_t3_usage`, an f-string instead of the card's text) or listed numbers left out (ACC-AT-09, A-11, U-36) | 3 | Model prefers computing to copying | Prompt rule 15; quoted-value check (catches A-11); numbers are not checked | prompt, runner (partly) | partly fixed, untested |
| P14 | 2 | A row the test builds itself (`ia`, `fa`) also listed as a test argument | 13 retries (never a wrong accept) | Sheet said "the only possible arguments"; model lists every name it uses | Runner drops such arguments before checking (`tidy_args`) | runner | fixed, untested |
| P15 | 2 | Unused `before = written(db)` copied from the error exemplar into cards with no "nothing written" line | 6 retries; 1 wrong accept where the copied snapshot was used for a `count:` line (INV-EN-13) | One exemplar carried the pattern | Runner: a `count:` line saying "has exactly N rows" must have `== N` under its `# Then`; exemplars should include an error case without "nothing written" | runner, executor skill | fixed, untested |
| P16 | 2 | Shorthand row expanded with a wrong positional argument: "S9" (stock of I9 in F9) built in `f2` (INV-ST-13) | 1 | The model expands a Conventions shorthand by hand; positional arguments are not checked | Scaffold gives every Conventions shorthand row its own builder (`mk_s9()`), so nothing is expanded | executor skill | fixed, untested |
| P17 | 2 | Function-name slug copied from an exemplar (2), stray `# Given` / `# When` comments (1), docstring without full stop (6) | 9 cosmetic | Model copies the exemplar's surface | Runner builds the function name and docstring from the card and removes comments other than `# Then N` (`normalize`) | runner | fixed, untested |
| P18 | 4 | A Given row built with a different standing row than the card names: "assignment of M1 to S1" written as `to=s3` (MCH-SA-32) | 1 | The value of a builder keyword is not checked, and the test still ended as designed | Runner rejects a test that never uses a standing row the card names | runner | fixed, untested — run 4 revision 1 (19 cards): fired on none, no false rejection |
| P19 | 4 (revision 1) | A faithful test is rejected when a card value contains an escape sequence: `search="\tbolt\n"` → "The text '\tbolt\n' is not in the card" (MCH-SA-130, rejected twice, handed back; Claude wrote it). The wrong raw-string form `r"\tbolt\n"` passes the same check and, on an xfail card, would have been accepted | 1 handed back (never a wrong accept) | The text check compares the evaluated string (real tab / newline) with the card's source text (backslash-t). Whitespace-only strings are skipped, which is why MCH-SA-39 … SA-43 were not hit | Not done (runner not edited by the executor). Idea: also accept a literal whose source spelling (`ast.get_source_segment`, or `value.encode("unicode_escape")`) is in the card, and reject raw strings whose text contains a backslash escape the card writes in a normal string. **Done after revision 1:** a literal containing a backslash is compared by its source spelling, and a raw string is rejected. Probe on MCH-SA-130: the faithful test passes the check, the raw-string form is rejected; replay over 760 tests: no new rejection | runner | fixed; held in runs 5 and 6 (no false rejection) |
| P20 | 6 (trial) | A faithful test is rejected when a card value looks like a row name: `FactoryUpdate(name=None, abbreviation="U2")` → "The card names U2, but the test never uses `u2`" (FCD-INH-06; found by the scaffold step calling the check on its own exemplar) | 1 | P18 collects row names from the whole card body, including text inside quotes | **Done during run 6:** quoted text is blanked before row names are collected. FCD-INH-06 now passes the check; replay over the inventory, ledger, machine and factory-manager modules (746 tests): no rejection | runner | fixed, untested |
| P21 | 7 (trial) | A Then line with two values is asserted only for the first: `deleted_at is None`, `deleted_by is None` → one assert (FSD-GF-17, ten Then lines; produced identically on a second run after a helper-sheet sentence was added). Found by the scaffold step reading the trial, not by the runner | 1 | The runner checked only that each `# Then N` block has at least one assert | **Done before the full run of run 7:** the runner counts the checks a Then line lists in backticks and rejects a block with fewer asserts. Replay over six modules (862 tests): no rejection, which also shows no earlier accepted test had this slip | runner | fixed; worked in the full run of run 7 (GF-17 first attempt rejected, second faithful) |
| P22 | 8 (scaffold) | A faithful test is rejected when the card has a Given line written as code whose value is not used: `loaded = M1.factory_section_id` (loads the attribute so the later check sees the old value) → "variable `loaded` is assigned but never used" (MSA-UP-21 … UP-24, CL-09, CL-10; found by the scaffold step calling the check on a faithful test; the helper sheet worked around it with `_loaded`) | 0 (caught before the run) | The unused-variable check did not know Given code lines | **Done before the full run of run 8:** an assignment whose name appears in the card as a code line `` `name = …` `` is exempt. Both spellings now pass; replay over seven modules (927 tests): no rejection | runner | fixed; worked in run 9's trial (MSM-SET-31 accepted with the verbatim `loaded = …` line) |
| P23 | 11 (trial, `item_tag_assignment`) | Extra builder keyword accepted: "L9 = link of I9 to T9. (A link of W2.)" built as `mk_link(of=i9, to=t9, workspace_id=w2.id)` (ITA-INH-13). Same value as the default here, so the test still checked the right thing, but the row was not built as written. Found by the scaffold step reading the trial | 1 | The P11 keyword check tests `k.arg not in card` as a substring of the whole card, and `workspace_id` occurs in every card's When line, so any `workspace_id=` passes; the remark "(A link of W2.)" invited it | Helper sheet: a definition row for L9 saying a link already takes its item's workspace; test deleted and re-run. Runner idea, not done: look for the keyword only in the card's Given lines (or in a "but" clause of the row being built) **Done during run 12:** the builder-keyword check accepts only keywords named in the card's Given rows (before **When**), no longer anywhere in the card; and a helper-sheet definition row implies only the keywords in its code, not those in a remark after it (the sheet's own warning "write `workspace_id=` only after but" had re-allowed the keyword). Probe: the faithful ITA-INH-13 passes, the trial's `workspace_id=w2.id` version is rejected; replay over 11 modules (1,286 tests): no rejection | runner | fixed, untested |
| P24 | 11 (`item_tag`) | The model leaves out a fixture it uses only inside a dict or call (`{"workspace_id": w1.id}`) — 6 retries in `item_tag` and more in `item_tag_assignment`, even after a helper-sheet line | many (retries only, never a wrong accept) | The runner rejected the test and asked for a repair round | **Done before run 12's full run:** `tidy_args` adds any fixture the body reads but the argument list lacks, in order of first use. Replay over 3 recent modules: no rejection | runner | fixed, untested |
| P25 | 12 | A blank line after the docstring in delivered tests (5 in `item_tag_assignment`, 1–2 in most modules); cosmetic, removed by hand at finishing every time | many | `normalize` rebuilt the head but kept the body's leading blank line | **Done after run 12:** `normalize` drops blank lines right after the docstring. (The 70-character name cut stays on purpose: it keeps the `def` line short; verifiers keep reporting it as cosmetic only.) | runner | fixed, untested |
| P26 | 13 (trial, `item_manager`) | A faithful test is rejected: a `count:` line with two filters ("`items` with `workspace_id == W1.id` and `name == \"Bolt M8\"` has exactly 2 rows") was read by P21 as two checks needing two asserts (ITM-C-19, handed back) | 1 | P21 counted every backticked comparison, also the filters of one count | **Done before run 13's full run:** P21 skips `count:` lines. ITM-C-19 goes back to the local model | runner | fixed, untested |
| P27 | 13 (trial, `item_manager`) | An unfaithful test is accepted: `links_of(ix)` for the helper `links_of(db, item)` on a Then line after an xfail's failing line (ITM-U-08). It never runs today, so the test 'ended as designed'; it would crash once BUG-938 is fixed. Found by the scaffold step reading the trial | 1 | Lines after an xfail's failing line are never executed, and nothing checked helper calls statically | **Done before run 13's full run:** the runner reads the test file's module-level helpers and rejects a call with too few or too many positional arguments. Replay over every test file (5,221 tests): 0 hits; probe: `links_of(ix)` rejected, `links_of(db, ix)` accepted | runner | fixed, untested |
| P28 | 13 (`item_manager`) | `with pytest.raises(X) as exc:` where no later line reads `exc` (ITM-L-08, U-05, D-04: a card with a single `raises:` line); ruff F841, cosmetic, removed at finishing | 3 | The model copies `as exc` from the exemplars, which all go on to check the message; the unused-variable check looks only at helper results | Runner: drop `as exc` when nothing reads `exc` (in `tidy_args`), or say in the sheet that a card with no further `raises:` line takes no `as exc` | runner (or helper sheet) | open |

## Changes made, by date

### 2026-10-10 — after run 1

Runner (`tests/unit/_tools/local_coder.py`):
- New static checks before a test is run, each sent back to the model with a
  specific correction: fixture used but not requested; `# Then N` comments
  missing, repeated or out of order; a Then block with no assertion;
  `pytest.raises(X)` that the card does not ask for; a helper result assigned
  and never used; a before/after comparison with both sides taken after the
  call.
- xfail acceptance: the test must fail on a check inside the Then line the
  card names (or in the call itself when the card says the call raises). No
  failure line, or a fixture / duplicate-keyword error, is a rejection.
- The "Fails today on" line is removed from the prompt; it is quoted to the
  model only in repair feedback.
- Prompt rules 12–14 added (Then comments; write the correct behaviour, no
  uninvited `pytest.raises`; request every fixture, snapshot before the call,
  no unused variables).
- Report gains `fails_in_then` per xfail case.
- After the verifier's report: three more static checks — a builder keyword
  the card does not mention; a string that is in neither the card nor
  Conventions; a quoted value from a Then line that the test never writes —
  and prompt rules 15–16. Replayed over the 189 existing tests these flag 17
  of the verifier's 31 faulty tests and none of the 158 good ones.

Skills:
- `test-case-designer`: one obligation per numbered Then line (no "in
  particular" tails, no two counts in one line); expected values are literals;
  a Given names every column that differs from the default. "Fails today on" must start with `Then N` and name one
  line, with "raises" when the call itself fails; every numbered Then line
  must be checkable on its own; anything written as code must be valid code.
- `test-executor`: helper-sheet table split into definition rows and one-change
  example rows (the tool reads them). Exemplars must carry `# Then N` comments, use every actor
  of a pair, and take snapshots before the call; three lines every helper
  sheet must contain; finishing step checks the failing assertion (not just
  the Then number) and runs unused-variable checks; root cause recorded per
  escalation; tool-level lessons are added to this file.
- `test-verifier`: `# Then N` comments explained; report ends with a
  "Local-coder patterns" section that feeds this file.

### 2026-10-10 — after run 2

Runner:
- `tidy_args`: unused arguments, and non-fixture arguments the body assigns
  itself, are removed before the test is checked and run (P9, P14).
- `normalize`: function name, docstring title and `Rules:` line are built from
  the card; comment lines other than `# Then N` are removed (P17).
- A non-fixture name in the argument list is rejected (backstop for P14).
- `count:` lines: "has exactly N rows" requires `== N` under that `# Then`
  (P15).
- Every rejection message is stored per card in `local-run.json`
  (`rejections`); bug titles in xfail reasons are cut at a word boundary.
- Cards marked `- **Author:** claude` are skipped (mocks, races, non-strict
  xfail, bulk setup).
- Replayed over both existing test files (380 tests): no false rejection.

Skills:
- `test-executor`: every Conventions shorthand row gets its own builder; one
  error exemplar must not carry a "nothing written" snapshot.

### 2026-10-10 — during and after run 3

Runner (made after the 12-card trial, before the full run):
- `tidy_args`: a never-read `name = mk_…(…)` binding becomes the bare call.
  Confirmed: the 149 full-run tests have none; only the 12 trial tests did.
- `normalize`: the name slug is cut at a `_` boundary, not mid-word.
  Confirmed in the full run (the two mid-word names are trial tests).

Nothing else changed after run 3: there was no functional finding to act on.

Caveats on run 3 (from the verifier):
- The module is read-only and its cards are very regular; the clean result
  does not carry over to modules with writes, mocks or free-form Then lines.
- Nine BUG-655 tests fail inside the call today, so their assertions have not
  yet run against working code.

### 2026-10-10 — after run 4

Runner:
- New rejection (P18): every standing row the card names in Given / When /
  Then (`S1` → fixture `s1`) must be used in the test. Bracketed remarks and
  Given lines that state an absence ("W1 has no accounts") are ignored.
  Replayed: rejects MCH-SA-32 as delivered; 0 false rejections in the three
  DAO modules (551 tests); 2 in the 189 older, looser `account_manager` cards
  (ACC-A-14, ACC-S-15), where a row is named in prose only.

Right as delivered so far: run 1 74% · run 2 98.9% · run 3 100% · run 4 99.5%
(216 of 217 with revision 1 included).

Still unguarded (verifier, round 3): a value swapped between two rows of the
same kind that the card both names; Then lines after an xfail test's failing
line are executed by nothing until the bug is fixed (the verifier ran them once
against a scratch reference fix).

### 2026-10-11 — after run 5

Run 5 was the first manager since run 1 (`account_manager`, 74% right as delivered). `factory_manager` came out at 172 of 172 (100%), so the card and runner changes made on the DAOs carry over to a manager of this size (7 callables, 66 rules, real database, one patched clock).

- No runner or skill change was needed during the run. P19 (escaped literals) held: no false rejection.
- P18 (every named row must be used) did not fire, and the verifier found no swapped row or value.
- Found by the verifier's hand variants, not by the mutation tool: a `commit()` added to a writer passed every test, because only `delete_factory` had a commit card. Designer habit to keep: one commit-spy card per writing callable when the spec says "No commit".
- A strict xfail that rests on physical row order was loosened at finishing (FAC-S-49, S-50, S-51). The cases file must be changed in the same step, otherwise the verifier reports a card/test mismatch.
- Caveat on the comparison with run 1: `factory_manager` is a simpler manager than `account_manager` (no money arithmetic, no cross-manager calls). A larger manager is still the real test.

### 2026-10-11 — during and after run 6

- **P20 (runner):** quoted card values are no longer read as row names (see the table).
- **Row order is never deterministic.** The spec's "verified" recipe for a missing `ORDER BY` (insert two rows, update the first so it moves behind the second) held in the describer's probe and in the trial, then failed in 6 of 9 whole-file runs after autovacuum freed row places. This was a card-design fault, not a local-model fault: the tests were faithful. Designer skill changed: order comparisons on an unordered query are non-strict xfail, plus one strict card per query that records the SQL and asserts an `ORDER BY`. The four markers of such a bug come off together when it is fixed.
- **Open, same cause:** `factory_manager` FAC-S-11 … S-14 (strict, BUG-898) rest on the same assumption and have not been changed.
- **Verifier suggestions for the tool, not done:** stop cutting test names at 70 characters, strip a blank line after the docstring, a rebuild-and-compare acceptance check, and listing never-executed Then lines of xfail tests in the run report.

### 2026-10-12 — during and after run 7

- **P21 (runner):** a Then line that lists several checks needs that many asserts. This was the first functional slip by the model since run 4, and the first one a helper-sheet sentence did not fix; the runner check did.
- **Row-order rule held from the start.** With order cards non-strict and one strict statement-recorder card per unordered query, the file never went red in 26 whole-file runs (14 at finishing, 12 at verification, three of them with the planner forced to a scan type).
- **A non-strict order card can stop showing the bug.** FSD-INH-18 fails only under a sequential scan; once the bulk cards grew the table the planner switched to a bitmap scan and it xpassed every time. Kept, because after the fix it is the only card that tells `ORDER BY id` from other orders.
- **Verifier suggestions for the tool, not done:** the 70-character name cut; a rebuild-and-compare acceptance check; extend the "named standing row must be used" check to rows named with letters only (FD, FI).

## What run 2 says overall

| | Run 1 (`account_manager`) | Run 2 (`dao/inventory`) |
|---|---|---|
| Local tests accepted | 183 | 178 |
| Functionally wrong as delivered | 47 (26%) | 2 (1.1%) |
| Right as delivered | 74% | **98.9%** |
| Found by the finishing step / by the verifier | 16 / 31 | 0 / 2 |
| Claude repair rounds needed | finishing step + 1 fix round + sweep | 2 one-line fixes |
| Handed back to Claude | 2 | 0 (9 cards reserved for Claude by design) |

- Target (90% right as delivered) met. The gain came from three things together:
  one obligation per card line, one-change examples in the helper sheet, and
  runner checks that reject instead of accept.
- Caveat: one module each. A DAO has simpler cards than a manager (fewer side
  effects per call), so part of the gain may be the module. The next manager
  run is the like-for-like comparison.
- What the runner still cannot see: a wrong positional argument, a dropped
  Given qualifier, wrong row order, a bare number inside a non-count line.
  The verifier stays mandatory.

## What run 1 says overall

- The acceptance count (183 of 185) overstated quality: 47 accepted tests
  needed repair, i.e. about **74% of local-written tests were right as
  delivered**. None of the faults let a mutant survive, so they were fidelity
  faults (a test weaker or different than its card), not blind tests.
- Claude-written tests in the same file: 0 of 7 with findings.
- The faults are one family — a line with more than one obligation gets one
  statement, and examples are copied whole. Both are addressed at the source
  (card and sheet format) and by runner checks.
- Target for run 2: at least 90% right as delivered, measured the same way.

## Ideas not done yet

- Check for a dropped Given qualifier ("deleted", "inactive", "in W2" in the
  card requires the matching builder keyword) — needs a per-module mapping in
  the helper sheet.
- Check bare numbers and column names of Then lines, not only quoted strings.

- Have the runner write the docstring's `Rules:` line from the card instead of
  trusting the model to copy it (one docstring in run 1 dropped part of it).
- Strip unused fixture arguments automatically at acceptance time instead of
  in the finishing step.
- A second, cheap pass where the model is shown its accepted test next to the
  card and asked only "which Then value is not asserted?" — to catch dropped
  values inside a line, which the `# Then N` check cannot see.
