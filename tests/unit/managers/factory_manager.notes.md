# Execution notes — `app/managers/factory_manager.py`

> Cases: `tests/unit/managers/factory_manager.cases.md` (revision 4, READY, spec APPROVED again 2026-11-02, 233 cases) · Tests: `tests/unit/managers/test_factory_manager.py` · Source commit: e48a092
> Result: 145 passed · 88 xfailed · 0 discrepancies · 0 errors (233 tests after the flake fix, 2026-11-02) — branch coverage 100% (78 statements, 38 branches)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_factory_manager.py -q -p no:cacheprovider`

## How the tests are built
- **Local-coder mode.** 201 tests, one per card: 6 hand-written exemplars, 172 written by the local model (under a `# [local-coder] <ID>` comment, from one card each, with `factory_manager.helpers.md` as its only view of the file), 23 `Author: claude` cards written by hand in Step D (under a `# [claude] <ID>` comment, placed in card order between the local tests).
- **Clock.** The autouse fixture `standing_rows` patches `app.dao.factory.utcnow` to return `NOW` in every test (Conventions, Externals). Nothing else is mocked, except in the five cards below.
- **Race simulations (FAC-C-31, C-32, U-50, U-51).** `patch.object(FactoryManager, "_check_name_exists", return_value=False)` (or `_check_abbreviation_exists`) around the call; inside it `with pytest.raises(HTTPException) as exc:` then `with db.begin_nested():` then the call, as Conventions prescribe. Today nothing is raised (no unique index), so all four fail on Then 1.
- **Target `database` (FAC-C-27 … C-30).** The When is `db.add(Factory(...))` + `db.flush()` with exactly the card's keywords (not through `mk_factory`); the two xfail cards wrap it in `pytest.raises(IntegrityError)` / `db.begin_nested()`.
- **Rolled back (FAC-D-14).** `patch.object(db, "commit", wraps=db.commit)` is the commit spy; `sp = db.begin_nested()` directly before the call; Then 1–2 inside the savepoint, `sp.rollback()`, then Then 3–4, then `commit_spy.call_count == 0`.
- **Bulk setup (13 cards).** A plain loop over `mk_factory` in the test (`for k in range(1, 101): mk_factory(name=f"Old {k:03d}", abbreviation=f"O{k:03d}", deleted=True)`); no new helper was added, and `factory_manager.helpers.md` is unchanged.
- **Constants (module-level names, not fixtures):** `M` (= the singleton `factory_manager`), `MISSING`, `T0`, `NOW`.
- **Fixtures:** `w1`, `w2`, `w3`, `u1`, `u2`. Each depends on the one before it, so ids rise in that order. `w3` = `make_workspace(db, subscription_plan_id=make_subscription_plan(db, max_factories=1).id)`. `standing_rows` (autouse) makes all five present in every test, so a test requests only the ones it names.
- **Builders (fixtures, keyword-only, flush before returning):**
  - `mk_factory(*, name, abbreviation, deleted=False, **columns)` — the Conventions "factory" (`workspace_id W1.id`, `created_by U1.id`, `updated_by None`, `updated_at None`, `is_active True`, `is_deleted False`, `deleted_at None`, `deleted_by None`, `created_at` left to the database). `deleted=True` is the Conventions word "deleted" (`is_deleted True`, `deleted_at T0`, `deleted_by U1.id`; `is_active` stays True), so the model never expands it.
  - `mk_machine(*, of, name, **columns)` — "machine of F": `workspace_id` and `factory_id` of the factory, `is_active True`, `is_deleted False`.
  - `mk_section(*, of, name, **columns)` — "section of F", same shape with `FactorySection`.
  - The keyword `of` is the card's own word ("machine **of** F1"); the tool accepts a builder keyword only if it occurs in the card text.
- **Reading helpers (plain functions):** `ids(result)`, `names(result)` (keep the returned order), `reread(db, row)` (any of the three models; `db.expire_all()` then SELECT by id), `snap(db, row)` (unchanged: every column, straight from the table), `count_rows(db, "<table name>")` (`factories`, `machines`, `factory_sections`), `written(db)` (the three counts of "nothing written").
- **Error shapes.** `raises: HTTPException` → plain `pytest.raises(HTTPException) as exc`; `raises: ValidationError` → plain `pytest.raises(ValidationError)` around the schema construction; `raises: IntegrityError` / `DataError` → the call inside `db.begin_nested()` inside `pytest.raises(...) as exc`.
- **Private checks** are called on the singleton exactly as the cards write them: `M._check_name_exists(db, workspace_id=w1.id, name="Main Plant", exclude_id=f1.id)`.
- **Exemplars (in the file and printed in the helper sheet):**

  | Card | Shape it shows |
  |---|---|
  | FAC-C-01 | create, `re-read the returned row`, two values in one line, who-stamp `u2.id`, `w1.id`, a `count:` line |
  | FAC-C-18 (xfail BUG-896) | target `schema`, `raises: ValidationError`, **error without any snapshot**, no Given row, `count … == 0` |
  | FAC-U-34 (xfail BUG-900) | update with `FactoryUpdate()`, a builder keyword after "but" (`updated_by=u1.id`), **a bug that makes an assertion fail (Then 2), not the call**, `u1.id` in an assertion |
  | FAC-U-43 | update happy path on a W2 row (`workspace_id=w2.id`), `result is f9`, `w2.id` / `u2.id` in assertions, `unchanged(F1)` |
  | FAC-S-38 | search with `include_deleted=True`, `deleted=True`, a Given row without a variable, `sorted(ids(result))` |
  | FAC-D-08 | `raises: HTTPException`, `status_code` / `detail` on separate Then lines, `unchanged`, re-read with `T0` and `u1.id`, "nothing written" |

  Every actor of a pair is used in an assertion at least once (`u1.id`, `u2.id`, `w1.id`, `w2.id`). No exemplar shows `IntegrityError` / `DataError`; the sheet carries a five-line snippet for it instead (six cards: FAC-C-34, C-35, U-41, D-16, S-45, S-46).
- **Helper sheet:** 9,891 characters (9,937 bytes) — about 900 over the skill's 9,000 guideline, because it prints six exemplars. Largest prompt (FAC-U-38): about 6,130 tokens by the tool's estimate, plus 1,800 for the answer, of 16,384.
- **Tool fit, checked by script before the trial** (the tool's own functions, read-only): fixtures detected = `db`, `engine`, `w1`, `w2`, `w3`, `u1`, `u2`, `mk_factory`, `mk_machine`, `mk_section`, `standing_rows`; none collides with a row name of the cards (`F1`, `FD9`, `D1`, `MA1`, `SC1` … are local variables). The six exemplars pass `static_check` against their own cards and carry exactly the names `normalize` would give them. The rule "a standing row the card names must be used" asks, per card, only for rows the card really uses in Given / When / Then (no row is named in prose only). The sheet's definition rows imply only `name` and `abbreviation`. No module string constant is needed.

## Scaffold checks (experiments run once; the probe files were deleted / live in the session scratchpad)

### (a) The five strict BUG-899 order cards (FAC-S-47 … S-51)
- **Normal runs:** each setup was run 8 times in the cards' insertion order through the manager. All 40 runs returned insertion order, so all five fail today on Then 1 as designed.
- **They are not all safe as strict.** Today's order is the physical order of the rows in the table, and that equals insertion order only as long as no VACUUM frees earlier space while the test is running. Probe (`wrap_probe2.py`, nothing committed): dead rows of an earlier rolled-back test at the start of the page, the first k Given rows inserted, `VACUUM factories` from a second connection (what autovacuum does), the remaining rows inserted — they are put into the freed slots, i.e. physically *before* the first k rows, and the list comes back rotated:

  | Card | Rotations tried (VACUUM after row k) | Result |
  |---|---|---|
  | FAC-S-47 | k = 1, 2, 3, 4 | fails in all four (the intended order is no rotation of the insertion order) — **safe as strict** |
  | FAC-S-48 | k = 1, 2, 3 | fails in all three — **safe as strict** |
  | FAC-S-49 | k = 1, 2, 3, 4 | **passes for k = 2** (`["Bravo", "charlie"]` returned) |
  | FAC-S-50 | k = 1, 2, 3, 4 | **passes for k = 3** (`["echo"]` returned) |
  | FAC-S-51 | k = 1, 2, 3 | **passes for k = 1** (`["alpha plant", "Mid Plant", "Zinc Plant"]` returned) |

  The window is narrow (an autovacuum must finish between two Given inserts of that very test), so this was never seen in a normal run here; the machine DAO notes record one such rotated result (MCH-GF-26). For the main session: FAC-S-49, S-50, S-51 can pass today and should become non-strict + `Author: claude` (a cards change), or get an insertion order whose rotations all differ from the expected page. S-47 and S-48 can stay strict.
- **Same mechanism, other strict cards (not asked, found by the same probe):** the four small BUG-898 cards pass today when a VACUUM lands after their first Given row — FAC-S-11, S-12 (also after the second row), S-13, S-14. The 101-row cards pass when it lands late in the loop (tried: after row 100 of 101 → FAC-S-15, S-16 and the direct checks of CN-14, CA-14 pass; after row 10 or row 60 they still fail); FAC-C-25, C-26, U-48, U-49 rest on the same row order. A page boundary alone does not reorder rows (`wrap_probe.py`: the next page is a higher one).

### (b) Designer inferences
| Card | Question | Today |
|---|---|---|
| FAC-U-09 | update of a soft-deleted factory of another workspace → 404? | 404, `"Factory with ID {id} not found"`, row unchanged — the workspace lookup comes first. Card holds. |
| FAC-D-07 | delete of the same → 404? | 404, row unchanged, `deleted_at T0` / `deleted_by U1.id` kept. Card holds. |
| FAC-U-38 | an inactive factory is renamed like any other | Yes: all nine Then lines hold (`is_active` stays False, `created_at` unchanged, F2 untouched). |
| FAC-D-04 | an inactive factory is deleted like any other | Yes: `is_deleted True`, `is_active False`, `deleted_at NOW`, `deleted_by U2.id`. |
| FAC-U-42 | empty update by an unknown `user_id` | The call raises `IntegrityError` (`ForeignKeyViolation` on `factories_updated_by_fkey`) on flush, because `updated_by` is stamped on every call. The card's "Fails today on: Then 1 (the call raises IntegrityError …)" holds; the test fails in the When call, before `# Then 1`, which the tool accepts because the line says "raises". |

### (c) Constraints
Nothing a card needs is forbidden by the database. Checked: W3 with a plan of `max_factories 1` (and three factories in it, FAC-C-33); `MISSING` is no id in `workspaces`, `profiles`, `factories`, `machines`, `factory_sections`; factories with `workspace_id W2.id` / `W3.id`, `is_active False`, `updated_by U1.id` with `updated_at None`, deleted; two factories with the same name or the same abbreviation in one workspace, one of them deleted (FAC-CN-06, CA-06) — and, there being no unique index today, also two live ones; names with `%`, `_` and a backslash; machines and sections of a factory, with `is_active False`. The error cards behave as written: `factories_created_by_fkey` (FAC-C-34), `factories_workspace_id_fkey` (C-35), `ForeignKeyViolation` for U-41 and D-16 with the row unchanged after the savepoint, `LIMIT must not be negative` / `OFFSET must not be negative` (S-45, S-46). A delete sets `updated_at` (the UPDATE statement) and leaves `updated_by` (FAC-D-02, D-03).

## Local-coder trial (Step C, small batch only)
- Model: Qwen3.6-35B-A3B Q4_K_M, n_ctx 16,384, thinking off. Server-counted prompt size 5,372 – 5,579 tokens per card (FAC-U-38 largest), plus up to 1,800 for the answer.
- **21 cards sent, 21 accepted on the first attempt, 0 rejections, 0 escalated.** 881.5 s (42 s per card), 114,114 prompt tokens, 4,637 completion tokens. Report: `factory_manager.local-run.json`.
- Cards: FAC-C-02, C-04, C-15 (xfail), C-34, U-01, U-06, U-31 (xfail), U-38, U-44 (xfail), G-01, G-07 (xfail), S-01, S-08, S-09, S-36 (xfail), S-45, D-01, D-09, D-12, CN-01, CA-10 (xfail).
- **All 21 were read against their cards line by line: all faithful** — every Given row with exactly the card's columns and order, the When call with exactly the card's arguments, every Then value asserted under its own `# Then N`, snapshots taken before the call, no extra check. Shapes that had no exemplar and came out right: `IntegrityError` / `DataError` with `db.begin_nested()` (C-34, S-45), `created_before` (U-38), two rows re-read in one test (U-38, D-09), "two things after but" (S-09: `workspace_id=w2.id, deleted=True`), the private checks as When and inside a Then line (CN-01, CA-10, D-12), the not-yet-existing `include_deleted` on `get_factory` left unwrapped (G-07), escaped literals `"\tPLANT\n"` and `"MP\n"` as plain strings (S-36, CA-10; the P19 fix let them through), three spaces (C-15).
- xfail locations from the report: C-15 Then 1 (`DID NOT RAISE ValidationError`), U-31 Then 3 (`updated_by` is U2's id), U-44 Then 1 (`DID NOT RAISE HTTPException`), G-07 in the When call (`TypeError … unexpected keyword argument 'include_deleted'`), S-36 Then 1 (`[]`), CA-10 Then 1 (`False`) — each as its card's "Fails today on" says.
- No change to the scaffold or the sheet after the trial; no tool or sheet problem seen. Whole file after the trial: 19 passed, 8 xfailed (6 exemplars + 21 trial tests).
- Not exercised by the trial: `mk_section` (FAC-D-10), W3 (FAC-C-33), the backslash cards FAC-S-29 and CN-10, `names(result)` (S-47 … S-51).

## Local-coder run (full run, Step C)
- Model: Qwen3.6-35B-A3B Q4_K_M, n_ctx 16,384, thinking off. Report: `factory_manager.local-run.json` (it covers the trial cards as well).
- **172 cards sent · 172 accepted · 169 on the first attempt · 3 after one retry · 0 escalated / handed back.** 6,075.6 s (about 35 s per card), 948,411 prompt tokens, 33,748 completion tokens.
- The three retries (FAC-G-03, G-04, G-08) had one cause: the model wrote `result = M.get_factory(...)` inside `pytest.raises` and the tool rejected the never-used `result`; the second attempt dropped the assignment. Root cause: model (the sheet's `raises:` exemplars show the call without an assignment).
- Nothing was changed in the helper sheet during or after the run, and nothing was added to `docs/testing/local-coder-improvements.md`.

## Step D (finishing)
- **Written by hand (23):** FAC-C-25, C-26, C-27, C-28, C-29, C-30, C-31, C-32, U-48, U-49, U-50, U-51, S-15, S-16, S-17, S-18, S-19, D-13, D-14, CN-13, CN-14, CA-13, CA-14. All 23 ended as designed on the first run (9 pass, 14 strict xfail); none needed a change of an expected value.
- **Local tests were not read against their cards** (the verifier measures them as delivered). Edits to them: none to any test body. The only behavioural edit is the marker of FAC-S-49, S-50, S-51 (below).
- **Cosmetic edits to the file:** the four `# noqa: F401` on imports removed (every import is used now); `# noqa: DTZ001` on `T0` / `NOW` (Conventions make them naive); the useless `return None` of `standing_rows` removed; a file-level `# ruff: noqa: SIM117` (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`, 12 places); the module docstring names the `# [claude]` tests. `ruff check` on the file: clean. `ruff --select F841,F811`: clean. AST pass for fixture arguments a test never uses: none in 201 tests.
- **FAC-S-49, S-50, S-51 → `strict=False`.** Their BUG-899 marker now reads `xfail(strict=False, reason="BUG-899: Factory list has no sort order (non-strict: today's order is the physical row order, which can match by accident)")`. Reason: Scaffold check (a) — a VACUUM between two Given inserts rotates the physical order into exactly the expected page. The cards still say "strict" (Conventions, xfail cards); the cases file was not edited. S-47 and S-48 stay strict.
- **xfail location check** (`--runxfail -rf --tb=short`, 68 failed · 133 passed): every one of the 68 fails inside the Then line its card names in "Fails today on", with the message the card describes. Three fail in the When call before `# Then 1`, as their cards say ("the call raises …"): FAC-G-07 and G-09 (`TypeError … unexpected keyword argument 'include_deleted'`), FAC-U-42 (`IntegrityError`, `ForeignKeyViolation` on `updated_by`). FAC-G-08 raises the same `TypeError` inside its `pytest.raises(HTTPException)` block, i.e. in Then 1. No test errors in setup.
- **Stability:** three consecutive runs, each `133 passed, 68 xfailed`.

## Discrepancies
None.

## Coverage gaps
None — 100% line and branch coverage of `app/managers/factory_manager.py` (78 statements, 38 branches, 0 missed).

## Factories added
None (`tests/unit/factories.py` unchanged).

## Notes for maintainers
- When a bug is fixed its strict xfail tests XPASS and fail the run: remove the marker. BUG-893: FAC-C-25, C-26, U-48, U-49, CN-14, CA-14. BUG-895: FAC-C-27, C-30, C-31, C-32, U-50, U-51. BUG-898: FAC-S-15, S-16, S-52 — and remove the markers of the non-strict FAC-S-11 … S-14 in the same step (they pass silently). The three non-strict BUG-899 tests (FAC-S-49, S-50, S-51) will not announce the fix by themselves — remove their marker together with S-47 / S-48.
- When BUG-895 is fixed with a unique index, FAC-C-31 / C-32 / U-50 / U-51 need the manager to turn the `IntegrityError` into a 409; their savepoint (`db.begin_nested()`) is what keeps the session usable for Then 4 onwards.
- Row-order fragility (Scaffold check (a)): the BUG-898 cards FAC-S-11 … S-14 (non-strict since 2026-10-16, so an accidental pass no longer turns the run red) and, far less likely, the strict 101-row cards (FAC-C-25, C-26, U-48, U-49, S-15, S-16, CN-14, CA-14) rest on "physical order = insertion order" and could XPASS if an autovacuum lands between two Given inserts. Not seen in any run here. BUG-898's order-independent strict alarm is FAC-S-52 (statement recorder: some SELECT on `factories` must have `is_deleted` after its `WHERE`); it fails today in every plan and passes once the soft-delete filter is in the query. FAC-S-17, CN-13, CA-13 (100th row, pass cards) rest on the same order and could fail the same way.
- The 13 bulk cards insert about 100 rows one flush at a time; the whole file still runs in about 8 s.

## Fix round 1 (after verification round 1, main session)
- Verification round 1 found no functional fault in any test (172 of 172 local tests right as delivered). Two items were applied:
  - Cases file reconciled with the tests: FAC-S-49, S-50, S-51 are `xfail BUG-899 (non-strict)`; the "all strict" sentences were corrected.
  - Two cards added, both `Author: claude`, shaped like FAC-D-14: FAC-C-36 (create is flushed, not committed) and FAC-U-52 (update is flushed, not committed), with tests under `# [claude]`. Before them a `session.commit()` added to `create_factory` or `update_factory` passed every test.
- Not done, by choice: no commit card for the two readers (`get_factory`, `search_factories`); the FAC-S-11 … S-14 row-order caveat stays as recorded under Notes for maintainers.
- Counts now: 203 tests = 6 exemplars + 172 local + 25 Claude.

## Review round 2026-10-16 (delegated — decided by Claude under the reviewer's delegation)
- **BUG-898 is a "deleted / non-matching rows take page places" bug, not an ordering bug** — but with no `ORDER BY` (BUG-899) the database decides which rows form today's page. For FAC-S-11 … S-14 every Given has a physical order that puts the live / matching rows first, and then today's result equals the intended one; no one-call size or membership check avoids that (if the deleted rows always fall inside the page, there are fewer live rows than the page holds, and today's and the intended result can coincide). So their failing Then line depends on row order: **markers changed** from `strict=True` to `strict=False` (reason extended with "non-strict: …"); the four test bodies, all written by the local model, were **not** touched; their cards now say `xfail BUG-898 (non-strict)` with `Author: claude — non-strict xfail …`.
- FAC-S-15, S-16 (100 deleted + 1 live, default page) stay **strict**: today they pass only if the live row inserted last lands physically ahead of one of the 100 deleted rows; never seen.
- **New card and test FAC-S-52** (strict BUG-898, `# [claude] FAC-S-52`): a statement recorder on `search_factories` — Then 2 asserts that a SELECT on `factories` has `is_deleted` after its `WHERE`. Checked with `--runxfail`: it fails on Then 2 (`assert False`; the only WHERE condition today is `workspace_id`), Then 1 holds. Import `event` added from `sqlalchemy`.
- Five whole-file runs one after the other: `135 passed, 69 xfailed` every time, no XPASS; coverage run the same, 100% line and branch; `ruff check` passes.
- Counts now: 204 tests = 6 exemplars + 172 local + 26 Claude.
- Not changed, for the record: FAC-S-47 and S-48 (BUG-899) are still strict order cards; under the designer's "Missing sort order" rule they would be non-strict with one statement-recorder card for the missing `ORDER BY`. Left as they are because the task covered BUG-898 only.

## Review round 2026-10-16 (2), main session
- FAC-S-47 and S-48 (BUG-899, local-written) were the last strict order cards: their markers are now `strict=False` (bodies unchanged) and their cards say `xfail BUG-899 (non-strict)`, per the designer skill's "Missing sort order" rule.
- New strict card and test FAC-S-53 (`Author: claude`): a statement recorder requiring a `SELECT` on `factories` to carry an `ORDER BY`. It is the alarm for the fix of BUG-899; when it XPASSes, remove the markers of FAC-S-47 … S-51 in the same step.
- Counts now: 205 tests · 135 passed · 70 xfailed.

## BUG-1331 round 2026-11-02 (one agent)
**This was one agent, lighter than an independent round.** The same agent rewrote the spec rule, designed the cards and wrote the tests, with `app/` already read, so the cards are not black-box and no separate verifier read them. Details are in `factory_manager.verify.md`.
- **Added:** cards and tests FAC-D-18 … D-42 (25: 15 strict `xfail BUG-1331`, 10 pass), all under `# [claude]`. No existing test body changed. Scaffold: builders `mk_line`, `mk_batch`; `_TABLES` gained `production_lines` and `production_batches`, so `written()` counts five tables in every test that uses it. Counts now: 230 tests · 145 passed · 85 xfailed.
- **`--runxfail`, today's code:** 15 failed, 27 passed among the 42 delete cards. All 15 fail in Then 1: 14 `DID NOT RAISE ValueError`, and FAC-D-27 on `IntegrityError` from the flush, as its card says.
- **Reference plugin** (scratch, `FACMODE=fix`, replaces `delete_factory` from a pytest plugin; `app/` untouched): the 42 delete cards pass under `--runxfail`, so every line past Then 1 ran; whole file 160 passed and 70 failed, the 70 being the older bugs' xfails. With the markers on, the 15 are strict `XPASS`, so they will announce the fix.
- **Wrong fixes:** 40 variants, 39 caught. Among them: one status only, closed status blocks, no sort, sort by number, date, line, status, text or descending, cap of 100 before or after the filter, foreign ids listed, cross rows dropped, repeated, first or sorted in by id, batch-only and line-only workspace tests, refusal before the 404 or the 400, write then raise, savepoint, stamp in memory, flush, commit or rollback on refusal, `HTTPException`, one arg, wrong message, tuple, subclass, inactive lines skipped. `savepoint_hides_write` passes every re-read and `written()` check and is caught only by FAC-D-25, D-26 and D-27.
- **Survivor, one:** `status NOT IN (completed, cancelled)`. It equals the rule on the four valid statuses; the two differ only on a status that is not valid, so it has no card.
- **Forced plans** (`PGOPTIONS`, the usual five): the reference passes all 42 delete cards in each, and the no-sort variant is caught by FAC-D-21 in each.
- **Repeats, not clean, older cards only:** 60 whole-file runs (10 rounds of the five plans and the default): 53 ended `145 passed, 85 xfailed`; 7 had one strict XPASS, on FAC-C-25, S-15, U-49 or CA-14. Baseline without the 25 new tests: 30 default runs, 3 red the same way (U-48, U-49, CA-14). So the rate is about the same with and without them, and no BUG-1331 card was off design in any run. Two earlier forced-plan runs in the first matrix also had one failure, whose test was not captured. These are the strict 101-row cards named under Notes for maintainers as resting on physical row order; the cause was not re-proved here. They were left as they are, being outside this task. They now do go red in repeated runs, which they had not before.
- **Mutation tool: not run** in this round. Coverage 100%, `ruff check` passed, no unused fixture arguments in the delete cards. Traceability: 230 cards, 230 tests, each ID once.
- **When BUG-1331 is fixed:** remove the 15 markers in one step. `FactoryService` needs its 400 (spec FU-6), or the refusal is a 500.

## Flake fix 2026-11-02 (same agent, cases revision 4)
- **Proved order-dependent:** the eight strict 100-row cards FAC-C-25, C-26, U-48, U-49, S-15, S-16, CN-14, CA-14. Forced row orders (a scratch plugin re-executes today's capped `SELECT … FROM factories … LIMIT` with an `ORDER BY` added after any recorder has seen it): under id descending, newest row first, newest two first, live first and a hash order, all eight strict XPASS; under id ascending (the control) nothing changes. No other card changes outcome under any order, apart from the already non-strict S-11 … S-14 and S-50. A real `VACUUM factories` from a second connection between Given inserts reproduces it: 24 whole-file runs with VACUUM after insert 100, 99/100, 50/100, 25/50/75/100 or every tenth insert, and every run had 3 to 8 of the eight red, nothing else. VACUUM after every insert reproduced nothing, which is also why a normal run is usually green.
- **Change:** their markers are now `strict=False` with the reason extended ("non-strict: the first 100 rows are taken in physical row order, which a VACUUM can rotate so the live row is among them"); bodies unchanged; cards say `(non-strict)`.
- **New strict alarms** (statement recorder, `# [claude]`): FAC-CN-20 and CA-20 (BUG-893: some `SELECT` on `factories` has `name` / `abbreviation` in its WHERE clause, before any `ORDER BY` or `LIMIT`, or none has a `LIMIT`), FAC-S-54 (BUG-898: the search reaches the WHERE clause; with S-52). A fix that only adds a sort keeps them red. `--runxfail`: all three fail in Then 2 today; a reference plugin (filtered `EXISTS`-style checks, search in SQL) passes them and the eight. Under the forced orders none of the three moves.
- **Counts now:** 233 tests · 145 passed · 88 xfailed (71 strict, 17 non-strict). Three default runs `145 passed, 88 xfailed`; `ruff` clean; cards and markers agree.
- **When BUG-893 / BUG-898 is fixed:** CN-20 / CA-20 / S-54 XPASS and turn the run red; remove the non-strict markers of the cards they name in the same step, as they pass silently.
