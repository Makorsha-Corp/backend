# Execution notes — `app/managers/factory_section_manager.py`

> Cases: `tests/unit/managers/factory_section_manager.cases.md` (READY, spec APPROVED 2026-10-16, 207 cases) · Tests: `tests/unit/managers/test_factory_section_manager.py` · Source commit: e48a092
> Result: 139 passed · 68 xfailed · 0 discrepancies · 0 errors (207 tests) — branch coverage 100% (81 statements, 38 branches)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_factory_section_manager.py -q -p no:cacheprovider`

## Who wrote what
| Part | Tests | Pass | xfail | Marker in the file |
|---|---|---|---|---|
| Exemplars (hand-written, Step A) | 9 | 7 | 2 strict | none (top of the file) |
| Local model (Step C; 15 trial + 149 full run) | 164 | 122 | 42 strict | `# [local-coder] <ID>` |
| `Author: claude` cards (Step D) | 34 | 10 | 10 strict + 14 non-strict | `# [claude] <ID>` |
| **Total** | **207** | **139** | **68** (54 strict, 14 non-strict) | |

Every case ID of the cases file is in exactly one test. Test order: exemplars, then the 15 trial tests (in the order sent), then the rest in card order; each `# [claude]` test sits in card order next to the local tests of its section.

## How the tests are built
- **Clock.** The autouse fixture `standing_rows` patches `app.dao.factory_section.utcnow` to return `NOW` in every test (Conventions, Externals). Nothing else is mocked, except the three race cards below.
- **Constants (module-level names, not fixtures):** `M` (= the singleton `factory_section_manager`), `MISSING`, `T0`, `NOW`.
- **Standing-row fixtures (the nine rows of Conventions):** `w1`, `w2`, `u1`, `u2`, `f1`, `f2`, `f9`, `fd`, `fi`. Each depends on the one before it, so ids rise in Conventions order. F1 "Main Plant"/"MP" W1; F2 "North Yard"/"NY" W1; F9 "Far Depot"/"FR" W2; FD "Old Plant"/"OP" W1, deleted (`deleted_at T0`, `deleted_by U1.id`); FI "Idle Plant"/"IP" W1, `is_active False`; all `created_by U1.id`. `standing_rows` makes all nine present in every test, so a test requests only the ones it names. The fixture names equal the lower-case row names of the cards (the tool's "standing row named → must be used" check relies on it).
- **Builders (fixtures, keyword-only, flush before returning):**
  - `mk_section(*, name, deleted=False, **columns)` — Conventions "section"; `deleted=True` = Conventions "deleted" (`is_active` stays True).
  - `mk_machine(*, of, name, **columns)` — "machine of F". `mk_assignment(*, of, to)` — "assignment of MA to S". `of` / `to` are the cards' own words (the tool accepts a builder keyword only if it occurs in the card text).
- **Reading helpers (plain functions):** `reread(db, row)` (`db.expire_all()` then SELECT by id; any of the four models), `snap(db, row)` (every column straight from the table), `count_rows(db, "<table>")`, `written(db)` (the four counts of "nothing written"), `rows_of_section(db, s)`, `ids(result)`, `names(result)`.
- **Statement recorder (added in Step D; FSM-S-58, S-59, S-65, S-66, CN-17).** `recorded_sql(db)` — a context manager that listens to `before_cursor_execute` on `db.get_bind()` and yields the list of statements sent inside the block, lower-cased with whitespace collapsed; `section_selects(statements)` keeps the `SELECT`s that contain ` from factory_sections`; `where_clause(s)` implements the Conventions definition (text after the first ` where ` up to the next ` order by `, ` limit `, ` offset ` or the end). The checks: S-58 `factory_sections.is_deleted` in a WHERE clause; S-59 `like` in a WHERE clause (`ilike` contains it); S-65 / S-66 `name` in the text after ` order by `; CN-17 a SELECT with no ` limit ` or with `name` in its WHERE clause. Recorded in the helper sheet.
- **Race simulations (FSM-C-29, U-50, U-51).** `patch.object(FactorySectionManager, "_check_name_exists_in_factory", return_value=False)`; inside it `with pytest.raises(HTTPException) as exc:` then `with db.begin_nested():` then the call, as Conventions prescribe. U-51 is a move without a new name, so today the check is not even called; the patch is there as the card says.
- **Target `database` (FSM-C-25 … C-28).** The When is `db.add(FactorySection(...))` + `db.flush()` with exactly the card's keywords (not through `mk_section`); C-25 / C-26 wrap it in `pytest.raises(IntegrityError)` / `db.begin_nested()`.
- **Rolled back (FSM-C-31, U-58, D-11).** `patch.object(db, "commit", wraps=db.commit)` is the commit spy; `sp = db.begin_nested()` directly before the call; the checks before the rollback, `sp.rollback()`, the "after the savepoint rollback" checks, then `commit_spy.call_count == 0`.
- **FD made live again (FSM-S-24).** `before_sh = snap(db, sh)` first, then `fd.is_deleted = False`, `fd.deleted_at = None`, `fd.deleted_by = None`, `db.flush()` on the standing row.
- **Bulk setup (FSM-C-24, U-57, S-47, S-48, S-56, S-57, CN-14, CN-15, CN-16).** A plain loop over `mk_section` in the test (`for k in range(1, 101): mk_section(name=f"Bay {k:03d}")`, or `name=f"Old {k:03d}", deleted=True`); S-47 / S-48 keep the 101 rows in a list for Then 3. No bulk helper.
- **Follow-up calls (FSM-D-10).** Then 2–6 call `M` again after the When call, each under its own `# Then N`; the two `raises:` lines are a plain `pytest.raises(HTTPException) as exc` followed by the `detail` assert.
- **Error shapes.** `raises: HTTPException` → plain `pytest.raises(HTTPException) as exc`; `raises: ValidationError` → plain `pytest.raises(ValidationError)` around the schema; `raises: IntegrityError` / `DataError` → the call inside `db.begin_nested()` inside `pytest.raises(...) as exc`.
- **Given lines written as code** (`db.refresh(S1)`, `created_before = S1.created_at`, `loaded_section_id = MA1.factory_section_id`) are run verbatim at their place. FSM-D-09's `loaded_section_id` is never read afterwards; it carries `# noqa: F841` rather than being deleted.

### Exemplars
| Card | Shape it shows | In the sheet |
|---|---|---|
| FSM-C-01 | create, `re-read the returned row`, two values in one line, `w1.id` / `u2.id` / `f1.id` asserted, `count:` | printed |
| FSM-C-18 (xfail BUG-915) | target `schema`, `raises: ValidationError`, error without any snapshot, no Given row | printed |
| FSM-U-46 (xfail BUG-919) | update no-op `FactorySectionUpdate()`, builder keyword after "but" (`updated_by=u1.id`), Given code line `db.refresh(s1)`, a bug that fails an assertion (Then 2), not the call | printed |
| FSM-G-06 | get, a section of W2, `w2.id` asserted | printed |
| FSM-S-45 | search with factory filter and `limit`, `len(...)`, `set(ids(result)) <= {...}` | printed |
| FSM-D-06 | `raises: HTTPException` 400, `status_code` / `detail` on separate lines, `unchanged`, re-read with `T0` / `u1.id`, `nothing written` | printed |
| FSM-D-08 | delete keeping machines / factory / other section / its assignment, five `unchanged`, `count:` on `machines` | printed |
| FSM-U-03 | 404 for a W2 section, f-string detail | in the file only |
| FSM-U-14 | 409 on a move, two-value re-read, two `unchanged` | in the file only |

### Tool fit (checked before Step C with the tool's own functions, read-only)
- `fixture_names` sees `db`, `engine`, the nine standing rows, `standing_rows`, `mk_section`, `mk_machine`, `mk_assignment`; no card row name collides with a fixture. All 9 exemplars pass `static_check` against their own cards.
- **Helper sheet:** 10,677 characters now (10,361 during the run; the one line on the statement recorder was added in Step D). Largest local prompt (FSM-U-49): about 7,000 tokens plus 1,800 for the answer, of 16,384.

## Scaffold checks (probes before Step C, rolled back)
- Constraint names as Postgres reports them: `factory_sections_created_by_fkey` (C-30), `factory_sections_updated_by_fkey` (U-54), `factory_sections_deleted_by_fkey` (D-12); after the savepoint the row re-reads unchanged.
- Cards checked against today's code before the run, all as designed: D-02, D-07, D-09, U-43, U-24 (raises `IntegrityError` inside the `HTTPException` block — Spec gap 3), S-19, S-47.

## Local-coder run
- Model: Qwen3.6-35B-A3B Q4_K_M (`Qwen_Qwen3.6-35B-A3B-Q4_K_M.gguf`), n_ctx 16,384, thinking off. Server started and stopped around each run; it is off now. Report: `factory_section_manager.local-run.json` (covers trial and full run).
- **164 cases sent (15 trial + 149 full run) · 164 accepted · 157 on the first attempt · 7 after retries · 0 escalated / handed back.** 5,174.8 s in total, 1,085,920 prompt tokens, 33,545 completion tokens.
- The 7 retries, all root cause **model** (the sheet already states each rule; nothing changed in the sheet):

  | Card | Attempts | Rejected because |
  |---|---|---|
  | FSM-U-29 (trial) | 2 | `snap(a1) == snap(a1)`, both after the call |
  | FSM-C-11 | 3 | a missing `# Then N`; then an unused `before` |
  | FSM-C-19 | 3 | `count == before` instead of the card's `== 0`; then an unused `before` |
  | FSM-U-39 | 2 | `mk_section` used but not in the argument list |
  | FSM-G-07 | 2 | `result = M.get_factory_section(...)` inside `pytest.raises`, never used |
  | FSM-G-09 | 2 | the same |
  | FSM-G-11 | 3 | the same; then `snap(sh) == snap(sh)` both after the call |
- The 15 trial tests were read against their cards, every Then line: all faithful. The other 149 local tests were **not** read for fidelity (the verifier measures them as delivered).
- Nothing added to `docs/testing/local-coder-improvements.md`: every retry repeats a mistake the tool already catches.

## Step D (finishing)
- **Written by hand (34, `# [claude]`):** FSM-C-24, C-25, C-26, C-27, C-28, C-29, C-31, U-50, U-51, U-57, U-58, S-24, S-47, S-48, S-53, S-54, S-55, S-56, S-57, S-58, S-59, S-60, S-61, S-62, S-63, S-64, S-65, S-66, D-10, D-11, CN-14, CN-15, CN-16, CN-17. All ended as designed on the first run: 10 pass (C-27, C-28, C-31, U-58, S-24, S-47, S-48, D-10, D-11, CN-14), 10 strict xfail (C-25, C-26, C-29, U-50, U-51 BUG-913; S-58, S-59 BUG-917; S-65 BUG-918; S-66 BUG-903; CN-17 BUG-911), 14 non-strict xfail with a reason naming the row order (C-24, U-57, CN-15, CN-16 BUG-911; S-53 … S-57 BUG-917; S-60 … S-63 BUG-918; S-64 BUG-903). No card needed a change; no expected value differs from the card.
- **Edits to the local part of the file — cosmetic only:** the three `# noqa: F401` comments on the import blocks removed (every import is used now; ruff reported them as RUF100); `contextmanager`, `patch` and `event` imported for the Step D tests; `# noqa: F841` on FSM-D-09's Given line `loaded_section_id = …`. No local test body, marker or name was changed (diff against the as-delivered copy: 5 lines changed, all of them those import lines and the D-09 comment).
- **Checks:** `ruff check` on the file — clean. `ruff --select F841,F811` — clean. AST pass for fixture arguments a test never uses — none in 207 tests. No test errors in setup.
- **xfail location check** (`--runxfail -rf --tb=long`, 68 failed · 139 passed; each failing line mapped to the `# Then N` block it lies in, by script): 65 of 68 fail inside the Then line their card names, with the error the card describes. The other three — FSM-G-08, G-10, G-12 (local) — fail in the When call with `TypeError … unexpected keyword argument 'include_deleted'`, before `# Then 1`; their cards say "Then 1 (the call raises TypeError …)", so this is the designed failure. FSM-G-09 raises the same `TypeError` inside its `pytest.raises` block (Then 1); FSM-U-24 raises `IntegrityError` inside its `pytest.raises(HTTPException)` (Then 1), as its card says. Every one of the 24 Step D xfails fails on its card's Then line (strict: C-25, C-26, C-29, U-50, U-51 Then 1 `DID NOT RAISE`; S-58, S-59, S-65, S-66, CN-17 Then 2 `assert False`, Then 1 holds).
- **Stability:** 13 whole-file runs (1 plain, 1 `--runxfail`, 1 coverage, then 10 in a row), never red. In the 10-run series, run 1 was `139 passed, 67 xfailed, 1 xpassed`: **FSM-C-24 XPASSed** (non-strict, allowed) — the live "Late" row landed among the first 100 rows of the physical order, exactly the case its card names. The other 9 runs: `139 passed, 68 xfailed`. No strict xfail and no pass test flipped.

## Discrepancies
None.

## Coverage gaps
None — 100% line and branch coverage of `app/managers/factory_section_manager.py` (81 statements, 38 branches, 0 missed). The coverage run prints 15 `SAWarning`s ("GenericFunction … is already registered") from SQLAlchemy's Postgres dialect being imported a second time under coverage; they do not appear in a plain run and do not touch the module.

## Factories added
None (`tests/unit/factories.py` unchanged).

## Notes for maintainers
- When a bug is fixed its strict xfail tests XPASS and fail the run: remove the marker. Alarms by bug: BUG-911 → FSM-CN-17 (then also remove the non-strict C-24, U-57, CN-15, CN-16); BUG-913 → C-25, C-26, C-29, U-50, U-51; BUG-917 → S-58, S-59 (and the non-strict S-53 … S-57); BUG-918 → S-65 (and S-60 … S-63); BUG-903 → S-66 (and S-64). Non-strict tests do not announce a fix by themselves.
- CN-15 and S-56 also pass once BUG-905 alone is fixed (deleted rows out of the scan, cap kept); CN-16, C-24, U-57 carry the cap itself.
- When BUG-913 is fixed with a unique index, C-29 / U-50 / U-51 need the manager to turn the `IntegrityError` into a 409; their `db.begin_nested()` keeps the session usable for the later checks.
- Row order is real here, not theoretical: FSM-C-24 XPASSed once in 10 runs (other agents run tests against the same database, so autovacuum frees slots that a later insert fills). The 14 non-strict cards are exactly the ones that rest on physical order; no pass card and no strict card does. The pass cards S-47 / S-48 check only size and membership, CN-14 holds for any order (all 100 sections fit in the page).
- The statement-recorder checks depend on SQLAlchemy's rendering (`factory_sections.is_deleted`, ` order by `, ` limit `); a fix that filters through a subquery or a CTE still matches as long as some SELECT on `factory_sections` carries the condition.
- The bulk cards insert about 100 rows one flush at a time; the whole file still runs in about 7 s.
