# Execution notes — `app/dao/machine.py`

> Cases: `tests/unit/dao/machine.cases.md` (revision 1, READY, 245 cases) · Tests: `tests/unit/dao/test_machine.py` · Source commit: e48a092
> Result: 194 passed · 51 xfailed · 0 discrepancies · 0 errors — coverage 96% (67 statements, 2 missed; 22 branches, 2 partial). Same outcome in three consecutive coverage runs, all after the last edit. None of the six non-strict xfail tests passed in them.
> The sections below down to "Fix round 1" describe revision 0 (216 cases: 168 passed · 48 xfailed, 88%) and are kept as written; what revision 1 added and changed is in the last section, "Revision 1".
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine.py -q -p no:cacheprovider --cov=app.dao.machine --cov-branch --cov-report=term-missing`

## How the tests are built
- **Local-coder mode.** The scaffold, five exemplars and the 12 `Author: claude` cards are hand-written; the 199 tests under a `# [local-coder] <ID>` comment were written by the local model from one card each, with `machine.helpers.md` as its only view of the file.
- **Clock.** The autouse fixture `standing_rows` patches `app.dao.machine.utcnow` to return `NOW` in every test (Conventions, Externals). Nothing else is mocked; `db.commit` is only *wrapped* by a spy in MCH-SD-08.
- **Constants:** `dao` (module-level name, not a fixture), `IDLE` / `RUNNING` / `OFF` / `MAINTENANCE`, `MISSING`, `T0` … `T3`, `NOW`.
- **Fixtures:** `w1`, `w2`, `u1`, `u2` (from `tests/unit/factories.py`) and the eleven standing rows `f1`, `f2`, `f9`, `fd` (soft-deleted), `fi` (inactive), `s1`, `s2`, `s3`, `sx` (soft-deleted), `si` (inactive), `s9`. Each depends on the one before it, so ids rise in the order Conventions lists them. `standing_rows` (autouse) makes all of them present in every test, so a test requests only the ones it names.
- **Builders (fixtures, keyword-only, flush before returning):**
  - `mk_machine(*, name, deleted=False, **columns)` — the Conventions "machine". `deleted=True` is the Conventions word "deleted" (`is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`), so the model never expands it. `created_at` is left to the database unless given.
  - `mk_assignment(*, of, to)` — "assignment of M to S": `workspace_id` of the machine, then `db.expire_all()` right after the flush, as Conventions require.
  - `mk_event(*, of, created_at, metadata_json, **columns)` — "event of M": `event_type "status_updated"`, `description "status"`, `performed_by None`, `workspace_id` of the machine.
  - The keywords `of` / `to` are the card's own words ("assignment **of** M1 **to** S1", "event **of** M1"). The tool's keyword check accepts a builder keyword only if it occurs in the card text, and these two always do; `machine=` / `section=` would be rejected on cards that never use the word "section".
- **Hand-written tests only:** `mk_101(mk_machine, descending=False)` — the Given of the five 101-machine cards: Nk has `name f"M{k:03d}"`, inserted N1 … N101 (MCH-GF-15, GF-16, GS-17) or N101 … N1 with `descending=True` (MCH-SA-116, SA-117). Returns `{k: Nk}`. `commit_spy(db)` — `patch.object(db, "commit", wraps=db.commit)`, the Conventions "rolled back" spy (same helper as `test_base.py` / `test_inventory.py`).
- **Reading helpers (plain functions):** `ids(result)` and `names(result)` (keep the returned order), `by_id(result, row)`, `reread(db, row)` (any model), `snap(db, row)` (unchanged), `count_rows(db, "<table name>")` (the card's table name as a string: `machines`, `machine_section_assignments`, `machine_activity_events`, `factories`, `factory_sections`), `written(db)` (the five counts of "nothing written").
- **Database-error cards** (`raises: DataError`, `raises: IntegrityError`) wrap the call in `db.begin_nested()` inside `pytest.raises(...) as exc`; `raises: AttributeError` cards use a plain `pytest.raises(AttributeError)`.
- **MCH-SD-08** (savepoint + commit spy): `sp = db.begin_nested()` directly before the call, inside `with commit_spy(db) as spy:`; Then 1–2 run inside the savepoint, then `sp.rollback()`, then Then 3–4 on a fresh re-read; Then 5 (`spy.call_count == 0`) after the `with` block.
- **Non-strict xfail (BUG-343):** MCH-GF-20, GF-26, GF-27, GS-21, GS-27, GS-28 carry `xfail(strict=False, reason="BUG-343: …")`; the assertions are the cards' exact ordered lists.
- **Exemplars:** MCH-GS-05 (plain list; assignments; a W2 machine assigned to an F1 section; call for W2), MCH-SD-01 (`soft_delete` write with re-read lines, `NOW`, `u2.id`, a `count:` line), MCH-GF-24 (`DataError` + `begin_nested`, nothing written, unchanged), MCH-INH-13 (`AttributeError`, no `begin_nested`, **no "nothing written" snapshot**, re-read of an assignment), MCH-SA-72 (xfail BUG-886: the call itself raises today and is not wrapped; events).
- **No error card without any snapshot exists** in this module (every `raises:` card has "nothing written", "unchanged(X)" or both); MCH-INH-13 is the nearest (unchanged only).
- **File layout:** scaffold → exemplars → `Author: claude` cards (card order) → local-model tests (the 15 trial cards first, in card order, then the rest in cases-file order).

## Scaffold checks (experiments run once, in a temporary probe file that was deleted)
| Question | Result |
|---|---|
| Cross-wired Given rows insertable? (W2 machine with F1's id — GF-04, SA-05; W2 machine assigned to S1 — GS-04, GS-05, SA-06; F2 machine assigned to an F1 section — SA-30, SA-123; an event of a W1 machine with `workspace_id W2.id` — SA-82, SA-83) | Yes, all of them. The tables have only single-column foreign keys; nothing ties a machine's workspace to its factory's, or an assignment's section to the machine's factory. |
| MCH-SA-101 / SA-102 (identical names come back in id order; designed as pass) | Hold today: ascending `[M3, M1, M2]`, descending `[M1, M2, M3]`. The query orders by `name, id ASC`, so identical names are decided by id in both directions. The cards stay `pass`. |
| MCH-SA-40 (`search=" \t\n"`, xfail BUG-892) | Today the call returns `[]` (as for three spaces, SA-39), so the card fails on Then 1 as designed. Consistent with spec R8 if "whitespace-only" is read as Python `str.strip()`; the spec's only example is `"   "` and it does not define whitespace (Spec gap 2 of the cases file). |
| BUG-886 today | `AttributeError: Neither 'BinaryExpression' object nor 'Comparator' object has an attribute 'astext'`, raised while the query is built — no SQL is sent, the session stays usable. |
| MCH-SD-10 (`deleted_by=MISSING`) | `IntegrityError` with `.orig` a `ForeignKeyViolation` on flush; after the savepoint rollback the row is unchanged and re-reads as live. |
| MCH-INH-02 / INH-10 | `AttributeError` (the `factory_section_id` property has no setter); nothing is written. In INH-10 the in-memory `name` is already "B" when the error is raised — `snap` reads the table directly and `reread` expires first, so both show "Press". |

## Local-coder run
- Model: Qwen3.6-35B-A3B Q4_K_M, n_ctx 16,384, thinking off. Helper sheet 9,013 bytes. Largest single prompt (MCH-SA-123): 5,727 tokens. Report: `machine.local-run.json`.
- **199 cards sent, 199 accepted: 185 on the first attempt, 13 on the second, 1 on the third, 0 escalated.** 6,395.2 s in total (about 32 s per card), 1,163,816 prompt tokens, 39,086 completion tokens.
- Done in three sittings (the report is cumulative):

  | Sitting | Cards | Seconds | First try | Retried |
  |---|---|---|---|---|
  | Trial (MCH-GF-04 … SD-02 in the report's order) | 15 | 771.6 | 13 | 2 |
  | Second (MCH-GF-01 … SA-28) | 79 | 2,618.2 | 69 | 10 |
  | Third, after a machine restart (MCH-SA-29 … INH-18) | 105 | 3,005.4 | 103 | 2 |

- **Rejections: 15, on 14 cards, all made by the tool before the test was run; every one was corrected by the model on the next attempt.** Grouped by cause:

  | Cause | Rejections | Cards (fixture or detail) |
  |---|---|---|
  | A fixture is used but not in the argument list | 13 | MCH-GF-06 (`f1`), GF-14 (`f1`), GF-28 (`s1`), GS-09 (`s1`), GS-10 (`s1`), GS-19 (`w1`), GS-20 (`w1`), SD-02 (`f2`, `u1`, `w1`), SD-03 (`u1`), SA-03 (`f9`), SA-21 (`f1`), SA-27 (`s1`), INH-05 (`f1`) |
  | A `before…` variable assigned and never used (the card has no "unchanged" line) | 1 | MCH-SD-02 (second attempt: `before_m1 = snap(db, m1)`) |
  | A `count:` line asserted against a `before` value instead of the card's number | 1 | MCH-INH-03 (Then 3: `== before_count` instead of `== 0`) |

  Root cause of all 15: the model. The missing fixture is always one used only in the When call, in one `mk_assignment(to=…)` row or in one assert — the pattern the sheet's fixture line already names. 12 of the 13 fall in the trial and the second sitting (94 cards); the third sitting (105 cards) has one (MCH-INH-05) plus the INH-03 count.
- No escalation, so nothing was written by hand in place of the model.
- **Sheet change (after the trial only):** the fixture line now says "also one used only in the When call or in an assert (`f1`, `w1`, `u1`)". MCH-GF-14 and MCH-SD-02 were removed and re-run with it: the same rejections and attempt counts. The wording does not change the model's first attempt; the tool's rejection is what fixes it. The sheet and the scaffold were not changed after that.
- Trial read-through (done before the full run, kept for the record): the 15 trial tests were read against their cards line by line and found faithful. The other 184 were **not** read (see "Seen, left for verifier").
- Tool observations (tool not edited here; nothing new for `docs/testing/local-coder-improvements.md` — the fixture rejection is its P1, the name cut is already listed):
  - function names are cut at 70 characters by the tool; cosmetic, left as is;
  - `last_code` of an accepted case in the report is the last **rejected** attempt, not the accepted code (the accepted code is in the test file); `prompt_tokens` of a retried case is the sum over its attempts (MCH-SD-02: 17,893 over three attempts).

## Step D — what was done
1. **Written by hand (12):** MCH-GF-15, GF-16, GS-17, SA-116, SA-117 (101 rows via `mk_101`; pass), MCH-SD-08 (savepoint + commit spy; pass), MCH-GF-20, GF-26, GF-27, GS-21, GS-27, GS-28 (non-strict xfail BUG-343; all six fail today in Then 1).
2. **Changes to local-written tests — cosmetic only.**

   | Test | Change | Kind |
   |---|---|---|
   | MCH-INH-01, INH-02, INH-03, INH-04 | the blank line between the docstring and the first statement removed (cards without Given rows) | cosmetic |
   | MCH-GF-14 | block moved from the end of the trial group to after MCH-GF-04 (card order); text unchanged | cosmetic |
   | MCH-SD-02 | block moved from the end of the trial group to before MCH-SD-04 (card order); text unchanged | cosmetic |
   | MCH-GF-04, MCH-GS-29 | three blank lines after the test reduced to two; test text unchanged | cosmetic |

   **Functional changes to local-written tests: none.** Checked by script against the delivered copy: 195 of the 199 `# [local-coder]` blocks are byte-identical, the other four (INH-01 … INH-04) differ by exactly one removed blank line. No unused import, argument or binding was found in any local-written test (`ruff --select F`, plus an AST pass over arguments and local names), so nothing was removed there. The file as delivered is kept at `…\scratchpad\test_machine.asdelivered.py` of the executing session.
3. **Scaffold (hand-written part), cosmetic:** four `# noqa: F401` comments on imports removed (every imported name is used now); `from unittest.mock import patch` added for MCH-SD-08; two section comments added (above the `Author: claude` tests and above the local-model tests).
4. **Not done on purpose:** the local-written tests were not read against their cards and no functional repair was attempted — the verifier measures them as delivered. Ruff style findings that would change the prescribed shape were left: SIM117 (nested `with pytest.raises` / `with db.begin_nested()` is the Conventions form), DTZ001 (the cards use naive datetimes), RET501 / PLR1711 (`return None` of the `standing_rows` fixture).
5. **Mechanical checks (script, all clean):** 216 case IDs in the cases file, 216 tests, each ID exactly once, function name and docstring start with the ID; 199 tests carry a `# [local-coder]` comment = the 199 cases of the report, with the report's function names; the 12 `Author: claude` cards and the 5 exemplars carry none; every `Expect: pass` test (168) has no marker; every `Expect: xfail BUG-…` test (48) has exactly one `xfail` whose reason lists exactly the card's BUG ids, `strict=True` for 42 and `strict=False` for the six cards whose Expect says "(non-strict)"; every BUG id used (BUG-343, 886, 887, 888, 889, 890, 891, 892) has a row in `docs/testing/bugs.md`; no unused or unknown argument, no fixture used without being requested, no unused local binding; `# Then N` comments present, in order and equal in number to the card's Then lines in every test; `ruff --select F,E9,RUF100` clean.

## xfail location check (`--runxfail -rf`)
All 48 xfail tests fail under `--runxfail` (48 failed, 168 passed), each in the Then line its card names in "Fails today on", and each of the 41 local-written ones agrees with `fails_in_then` in the run report (MCH-SA-72 is an exemplar and the six BUG-343 tests are hand-written; they are not in the report). No non-strict test passes today.

| Cards | Card says | Fails today at |
|---|---|---|
| MCH-GF-12 (BUG-891) | Then 2 | Then 2, `assert result == []` — MD returned |
| MCH-GS-12 (BUG-891) | Then 3 | Then 3, `assert ids(result) == [m1.id]` — `[M1, MD]` returned |
| MCH-GS-15, SA-33 (BUG-889) | Then 2 | Then 2, `assert result == []` — M1 returned |
| MCH-SA-15, SA-16, SA-17, SA-18 (BUG-890) | Then 1 | Then 1 — `["Lathe", "Press"]`; `[Press]` instead of `[]`; `["Press"]` instead of `["Lathe"]`; `[M1, MD]` |
| MCH-SA-39, SA-40, SA-41, SA-42, SA-43 (BUG-892) | Then 1 | Then 1 — `[]` returned instead of the machine(s) |
| MCH-SA-55, SA-56, SA-58, SA-59 (BUG-888) | Then 1 | Then 1, `assert ids(result) == [m1.id]` — both machines returned |
| MCH-SA-60 (BUG-888) | Then 1 | Then 1, `assert ids(result) == [m1.id]` — the other machine (`[M2]`) returned |
| MCH-SA-99, SA-100 (BUG-887) | Then 1 | Then 1, `assert ids(result) == [m1.id, m2.id]` — `[M2, M1]` |
| MCH-SA-67 … SA-70, SA-72 … SA-89 (BUG-886, 22 tests) | Then 1 (the call raises AttributeError) | the When call itself, `AttributeError: Neither 'BinaryExpression' object nor 'Comparator' object has an attribute 'astext'`, not wrapped in `pytest.raises` (report: `fails_in_then` 0 = before the first Then) |
| MCH-GF-20, GS-21 (BUG-343, non-strict) | Then 1 | Then 1, `assert names(result) == ["Mango"]` — `["apple"]` |
| MCH-GF-26 (BUG-343, non-strict) | Then 1 | Then 1 — `["Banana", "Zulu", "apple"]` in the `--runxfail` run (not the insertion order the card predicts as usual; the card allows any order) |
| MCH-GS-27 (BUG-343, non-strict) | Then 1 | Then 1 — `["Zulu", "apple", "Banana"]` (insertion order) |
| MCH-GF-27, GS-28 (BUG-343, non-strict) | Then 1 | Then 1 — `[M1, M2, M3, M4]` (insertion order) instead of `[M4, M1, M3, M2]` |

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 35->37, 50->52 (partial branches) | dead | The `include_deleted=True` side of `if not include_deleted:` in `get_by_factory` / `get_by_section` (skips the `is_deleted == False` filter). Spec, Not specified: dead parameter, to be removed (Q6). No cards by design. |
| 58 | dead | Body of `get_active_by_workspace`. Spec, Not specified: dead code, to be removed (Q4). No cards by design. |
| 84-90 | dead | Body of `restore`. Spec, Not specified: dead code, to be removed (Q5). No cards by design. |
| 179 | unreachable (today, behind BUG-886) | The join of the machines to the latest-status subquery and the `status == latest_event_type.value` filter in `search_advanced`. Line 163 (`.astext`) raises `AttributeError` before it is reached. The 22 BUG-886 xfail tests (MCH-SA-67 … SA-70, SA-72 … SA-89) call this path and will cover it when the bug is fixed. |

Every other statement and branch is covered. No `spec-gap` or `deferred` line.

## Seen, left for verifier
- No functional mistake was noticed in the local-written tests — but 184 of them were deliberately **not** read against their cards, so this is not a finding of faithfulness (only the 15 trial tests were read, before the full run). All 199 are to be measured as delivered (apart from the four removed blank lines and the two moved blocks listed above).
- The mechanical checks above cannot see: a wrong row or value that still gives the designed outcome, an assertion weaker than the card's, a Then line implemented under the right comment with the wrong expression.
- The tool's keyword check cannot see a wrong `workspace_id=` / `factory_id=` / `is_running=` on a builder in `search_advanced` cards, because those words are always in the card's When call. Read the Given rows of those cards.
- Strings that are only whitespace (`"   "`, `" \t\n"`) are not checked by the tool (`value.strip()` is empty), and in the xfail cards MCH-SA-39 / SA-40 a wrong number of spaces would still fail on Then 1. Read these by eye.
- The 22 BUG-886 tests fail in the When call, so nothing after it has ever executed: their Given rows and expected lists are checked by no run at all.

## Factories added
None.

## Notes for maintainers
- `mk_assignment` expires the whole session. A test that holds an unflushed change across it would lose that change; no card does.
- When BUG-886 is fixed, the 22 `latest_event_type` xfail tests XPASS → remove the markers; their assertions have never run against working code. Line 179 becomes covered.
- When BUG-343 is fixed, the six non-strict tests pass silently (XPASS is not an error for `strict=False`) → remove the markers by hand. Until then they may XPASS at random if the database happens to answer in name order; this was not seen in four runs. MCH-GF-26 returned a non-insertion order in one run, so the order really is unstable.
- When the dead code (Q4, Q5, Q6) is removed, line 179 is the only uncovered line left.
- The five 101-row tests insert 101 machines each (MCH-GS-17 also 101 assignments, each with `db.expire_all()`); the whole file still runs in about 18 s.

## Fix round 1 (after verifier round 1)

- MCH-SA-32 (local, functional): Given row 2 built as `mk_assignment(of=m1, to=s3)`; the card says S1. Changed to `to=s1` and added `s1` to the arguments. Still passes.
- Cosmetic findings (argument order in 11 tests, variable names in 5, names cut at 70 characters) left as they are.
- Seen once after the fix: `168 passed, 47 xfailed, 1 xpassed`. The xpass is one of the six non-strict BUG-343 tests; the order of an unsorted query is not stable, which is why those cards are non-strict.

## Revision 1 (cases file revision 1: 216 → 245 cases)

> Result: 194 passed · 51 xfailed · 0 discrepancies · 0 errors — coverage 96%. Three consecutive coverage runs after the last edit, same outcome each time.

### What was added
- **29 tests** for the 29 new cards: MCH-RS-01 … RS-22 (`restore`), MCH-GF-30, GF-31, GS-30, GS-31, SA-128, SA-129, SA-130. No card retired, no existing test changed apart from the four docstring lines below.
- **Docstring `Rules:` lines of four existing tests** changed to the cards' new text (cosmetic): MCH-GF-13 `get_by_factory` R3a → R3b; MCH-GF-14 `get_by_factory` R3a, R1 → R3b, R1; MCH-GS-13 `get_by_section` R3a (the inactive-factory side is stated in `get_by_factory` R3a; see Spec gaps 1) → `get_by_section` R3b; MCH-GS-14 `get_by_section` R3a, R1 → R3b, R1. Test bodies untouched.
- **Scaffold:** one new helper, `fd_made_live_again(db, fd)` — the Conventions step "FD made live again" (`is_deleted False`, `deleted_at None`, `deleted_by None` set on the standing row, then `db.flush()`). Used by hand-written tests only (MCH-GF-30, GS-30, RS-19, SA-128, SA-129); no local-model card uses the step, so it is not in the helper sheet. "re-read FD" is the existing `reread(db, fd)`, "unchanged(FD)" the existing `snap(db, fd)`, the `factories` count the existing `count_rows`. `restore` needs no mock (it does not read the clock) and no new builder: a deleted machine is `mk_machine(..., deleted=True)`.
- **Restore exemplar: MCH-RS-01, written by hand.** None of the `Author: claude` restore cards shows the common shape (they are the savepoint card, the FD cards and the delete-then-restore cards), so the simplest restore card was taken instead. MCH-RS-01 is therefore **not a local-model test** (20 local cards in the cases file → 19 sent). It sits with the other exemplars but is **not printed in the helper sheet**: it has the shape of MCH-SD-01, which is printed, and the sheet is at its 9,000-character limit.
- **Helper sheet** (`machine.helpers.md`, 8,990 characters / 9,040 bytes): `ad` added to the local-variable names; one sentence added to the When line ("`restore` the same: `result = dao.restore(db, db_obj=md)`"); to make room, the example `assert row.updated_at is not None` was dropped from the re-read line (the cards write that expression themselves). Largest revision-1 prompt: 5,765 prompt tokens as counted by the server (the tool's own estimate before the run: 5,931, MCH-RS-02 / RS-22), plus 1,800 for the answer, of 16,384.
- **File layout:** RS-01 after the SA-72 exemplar; the nine `Author: claude` tests and MCH-SA-130 in a "Revision 1" block after MCH-SA-117; the 18 accepted local tests at the end of the file under a "Revision 1 — local-model tests" comment, in the order the tool wrote them (GF-31, GS-31, RS-02 … RS-22).

### Local-coder run (revision-1 cards only)
- Same model and settings as before (Qwen3.6-35B-A3B Q4_K_M, n_ctx 16,384, thinking off). One sitting, 1,026.5 s (54 s per card), 123,472 prompt tokens, 5,220 completion tokens.
- **19 cards sent: 17 accepted on the first attempt, 1 on the second, 1 handed back.**

  | Card | Attempts | Rejection message(s) from the report | Cause |
  |---|---|---|---|
  | MCH-GF-31 | 2, accepted | "You use the fixture(s) f1 but they are not in the function's argument list. Add them." | model (the known pattern: a fixture used only in the When call) — a correct rejection |
  | MCH-SA-130 | 3, handed back | 1. "The text '\tbolt\n' is not in the card. Use only the values the card gives, written exactly as in the card." 2. "The test ran and ended as `failed`. It must FAIL, because this case documents a known bug: today the code is wrong at Then 1 … Write the checks exactly as the card says." (pytest: `XPASS(strict)`) 3. the same message as 1 | **tool — a false rejection, twice** |

- **MCH-SA-130 in detail.** The model's first and third answers were the faithful test (`search="\tbolt\n"`; the third is `last_code` in the report and is, apart from the name cut, identical to the hand-written test now in the file). The tool's text check compares the *evaluated* string (a real tab and newline) with the card's source text, where the escape is written as backslash-t, so it can never be found. The second answer avoided the check with a text that is in the card but is not the card's value (the report keeps no code for it; a plain `"bolt"` would behave this way): the search then matches "Bolt cutter", the test passes, and the strict xfail turned it down. Checked by a read-only probe of `static_check` before the run: the faithful test is rejected, and the **wrong** raw-string form `r"\tbolt\n"` is let through and would have ended as xfail in Then 1 — i.e. accepted. That did not happen here, but the check steers towards it. The earlier whitespace cards (MCH-SA-39 … SA-43) were not hit because the check skips strings that are only whitespace. Logged as P19 in `docs/testing/local-coder-improvements.md`.
- **The new rejection (a standing row the card names must be used) fired on none of the 19 cards**, rightly or wrongly. Checked beforehand by script with the tool's own expressions: the rows it insists on per card are all rows the card really uses in Given, When or Then; the rows named only in bracketed remarks (`U1` in "(`deleted_at T0`, `deleted_by U1.id`.)", `F1` in "(Same factory F1; …)") are dropped by it as intended. No false rejection from that rule.
- **The rev-0 report is not lost.** The tool keeps the entries of cards it does not redo: `machine.local-run.json` now holds 218 cases — the 199 of revision 0, each identical to its entry in the copy taken before the run, plus the 19 new ones — and its totals are cumulative (218 cases, 217 accepted, 202 first try, 1 escalated, 7,421.7 s). Copies in the executing session's scratchpad: `machine.local-run.rev0.json` (before the run), `machine.local-run.rev1.json` (after). Both revisions together: 218 sent, 202 first try, 15 after a retry, 1 handed back.

### Step D — what was done
1. **Written by hand (11):** the exemplar MCH-RS-01; the nine `Author: claude` cards MCH-GF-30, GS-30, RS-12, RS-16, RS-19, RS-20, RS-21, SA-128, SA-129 (all pass); and the handed-back MCH-SA-130 (strict xfail BUG-892, fails in Then 1).
   - MCH-RS-12 follows MCH-SD-08: `sp = db.begin_nested()` inside `with commit_spy(db) as spy:`, Then 1–2 inside the savepoint, `sp.rollback()`, Then 3–5 on a fresh re-read, Then 6 after the `with` block.
   - MCH-RS-16: the deletion stamp is put on FD first (`deleted_at T0`, `deleted_by U1.id`, flush), the FD snapshot is taken after the last Given row.
   - MCH-RS-19: `after_md = snap(db, md)` and `fd_made_live_again(db, fd)` stand between the assertions of Then 2 and the `# Then 3` comment, as the card orders.
   - MCH-RS-20: Then 2 compares the before / after snapshots with the `updated_at` key left out of both. MCH-RS-20 / RS-21 run `dao.soft_delete(…, deleted_by=u2.id)` as a Given step.
   - MCH-GF-30, SA-128: the "nothing written" and "unchanged(MD)" snapshots are taken after the step "FD made live again" (the last Given row).
2. **Changes to the new local-written tests — cosmetic only:** a three-line section comment placed above the first of them (`# [local-coder] MCH-GF-31`). Nothing else: no block moved, no line changed. By script against the copy taken right after the run (`test_machine.rev1.asdelivered.py` in the scratchpad): all 217 `# [local-coder]` blocks, the 18 new ones included, are byte-identical to the delivered file. **Functional changes to local-written tests: none.**
3. **Other cosmetic edits:** the four docstring lines above; the comment on the `patch` import now names MCH-RS-12 too.
4. **Not done on purpose:** the 18 new local-written tests were not read against their cards and nothing in them was repaired.
5. **Mechanical checks (script, all clean):** 245 case IDs, 245 tests, each ID exactly once, name and docstring start with the ID; 217 tests carry a `# [local-coder]` comment = the 217 accepted cases of the report, with the report's function names; every `Expect: pass` test (194) has no marker; every xfail test (51) has exactly one marker with exactly the card's BUG ids, strict for 45, non-strict for the six BUG-343 cards; `# Then N` comments present, in order and equal in number to the card's Then lines in all 245; no unused or unknown argument, no fixture used without being requested, no unused binding; `ruff --select F,E9,RUF100` clean.

### xfail location check (`--runxfail -rf`)
51 failed, 194 passed: all 51 xfail tests fail, none of the pass tests does. The three new ones:

| Card | Card says | Fails today at |
|---|---|---|
| MCH-RS-17 (BUG-890, local) | Then 3 | Then 3, `assert names(dao.search_advanced(db, workspace_id=w1.id)) == ["Lathe"]` — `['Lathe', 'Press']`; report `fails_in_then` 3 |
| MCH-RS-18 (BUG-891, local) | Then 3 | Then 3, `assert dao.get_by_factory(db, factory_id=fd.id, workspace_id=w1.id) == []` — MD returned; report `fails_in_then` 3 |
| MCH-SA-130 (BUG-892, hand-written) | Then 1 | Then 1, `assert ids(result) == [m1.id]` — `[]` returned |

The 48 older ones fail in the same Then lines as recorded above.

### Coverage (three runs, identical)
`app\dao\machine.py  67 statements, 2 missed, 22 branches, 2 partial — 96%   Missing: 35->37, 50->52, 58, 179`

Lines 84–90 (`restore`) are now covered. What remains is unchanged from revision 0:

| Lines | Kind | What the code does there |
|---|---|---|
| 35->37, 50->52 (partial branches) | dead | the `include_deleted=True` side in `get_by_factory` / `get_by_section`; reviewer-confirmed dead parameter (Q6), no cards by design |
| 58 | dead | body of `get_active_by_workspace`; reviewer-confirmed dead code (Q4), no cards by design |
| 179 | unreachable today (behind BUG-886) | the join to the latest-status subquery; line 163 raises before it. The 22 BUG-886 xfail tests call this path |

The row "84-90 | dead" of the older "Coverage gaps" table above no longer applies.

### Discrepancies
None.

### Seen, left for verifier
- Nothing wrong was noticed in the 18 new local-written tests — and they were **not** read for fidelity, so this says nothing about them. They are in the file exactly as delivered.
- MCH-RS-17 and RS-18 fail in Then 3, so their Then 4 has never executed.
- The tool's keyword and row checks cannot see a wrong *value* (`factory_id=f2.id` where the card says another factory that the card also names elsewhere, `T0` / `T1`, `u1` / `u2` swapped when both are named). Cards where two such names occur: MCH-RS-02, RS-04, RS-13, RS-14, RS-15.
- MCH-RS-09 (R4, "no UPDATE") and the `updated_at is None` lines of RS-14, RS-15, RS-22 are the only checks that would notice a `restore` that writes when it should not, or touches a second row.
- For the hand-written MCH-RS-20, Then 2 leaves out `updated_at` by key name; every other column of the `machines` table is compared, whatever columns the table has.

### Notes for maintainers (additions)
- When BUG-890 / BUG-891 are fixed, MCH-RS-17 / RS-18 XPASS together with the older cards of those bugs → remove the markers. When BUG-892 is fixed, MCH-SA-130 too.
- If Q8 is answered differently (`restore` takes the acting user), every `dao.restore(db, db_obj=…)` call in the 22 RS tests gains an argument and MCH-RS-04, RS-05, RS-06 and Then 4 of RS-20 change. If Q9 is answered differently, MCH-RS-22 changes.
- `fd_made_live_again` changes a standing row inside the test's transaction; the row is back to deleted in the next test because every test is rolled back.
