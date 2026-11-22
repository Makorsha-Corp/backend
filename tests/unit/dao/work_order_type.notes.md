# Execution notes — `app/dao/work_order_type.py`

> Cases: `tests/unit/dao/work_order_type.cases.md` (Revision 1, READY, 30 cases) · Tests: `tests/unit/dao/test_work_order_type.py` · Source commit: e48a092
> Result: **30 tests for 30 cases — 26 passed · 4 xfail · 0 discrepancies · 0 errors** — branch coverage 100% line and branch (21 statements, 0 branches).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_work_order_type.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file (not kept in the repo; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refx\gen.py`), so values are the card's own text. The fixtures and helpers were written by hand from the Conventions. A separate audit script (`check.py`) checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matching the card's Then count, every quoted literal of the Given, When and Then lines present, marker and bug matching the Expect line, no unused argument, no fixture used without being an argument. LF only.

## How the tests are built
- **Patch:** `app.dao.work_order_type.utcnow` returns NOW in every test, through the autouse fixture `clock`. Nothing else is mocked.
- **Constants:** `dao`, `MISSING`, `T0`, `NOW`.
- **Standing rows:** `w1`, `w2`, `u1`, `u2`, `u3`, each depending on the one before so ids rise; the autouse `standing_rows` makes all of them exist in every test.
- **Builder:** `mk_row(gone=False, **columns)` = "row"; `gone=True` adds `is_deleted`, `deleted_at T0`, `deleted_by U1.id` and leaves `is_active` and `updated_at` alone.
- **Rolled back:** `sp = db.begin_nested()`, then `patch.object(db, "commit", wraps=db.commit)` around the When; the checks named "inside the savepoint" run first, then `sp.rollback()`, `db.refresh(a)`.
- **`A0`:** `a0 = snap(db, a)` after the last Given line.
- **Row letters** of the cards are lower case in the code (`A` becomes `a`, `P` becomes `p`). A Given row no later line names is built without a variable (F841). Lines such as "W1 has no status" add no code.
- **Reading helpers (no expected values inside):** `snap(db, row)` is every column by a Core select, for "unchanged"; `reread(db, row)` is `db.expire_all()` then SELECT by id.

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| WOT-RS-10 | yes | Then 1, every run | `Failed: DID NOT RAISE IntegrityError` |
| WOT-IN-02 | yes | The When, before Then 1, every run | `IntegrityError`: `duplicate key value violates unique constraint "uq_wo_type_workspace_name"`, as the card says |
| WOT-IN-03 | yes | Then 1, every run | `Failed: DID NOT RAISE IntegrityError` |
| WOT-IN-04 | yes | Then 1, every run | `Failed: DID NOT RAISE IntegrityError` |

**Proof of the lines past the failure point.** Plugin `refx_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refx` (`-p refx_plug`, `REFX_MODE=fix`), nothing in `app/`: `uq_wo_type_workspace_name` dropped and a transaction-local partial unique index on `(workspace_id, lower(btrim(name))) WHERE NOT is_deleted`, created by a plugin fixture in each test's own transaction and rolled back with it. With `--runxfail`, all 28 tests of the file pass, so every line past the failure point holds on the fixed table, and the pass cards stay green with it. With the markers on, the strict cards are `XPASS(strict)`: the red run they are there for.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Spec gaps of the cases file, checked
Gap 3 holds: with `Dup` and `dup`, RS-10 fails in the restore and not in its Given. The constraint is named `uq_wo_type_workspace_name` in the database, as the card says.

## Coverage gaps
None — 100% line and branch coverage.

Run with a private `COVERAGE_FILE`. Inherited `BaseDAO` methods live in `app/dao/base.py` and are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
5 default runs and 5 forced plans, each `24 passed, 4 xfailed`; the coverage run the same. All pass cards passed and every strict card xfailed in each. 20 more repeats of every test, in one process: nothing red. `PGOPTIONS` carried five forced plans: `enable_seqscan=off`; that plus hash join and nested loop off; `enable_hashjoin=off`; index, bitmap and index-only scans off; that plus hash and merge join off. `ruff check`: all checks passed.

## Revision history
- **Revision 1 of the cases (work_order_type.verify.md, case-missing findings):** added WOT-SD-12, WOT-RS-12. The new tests were transcribed from the cards by the same parser and inserted at their card's place; no existing test changed. The audit script passed on every card of the file.
- **Rerun of the final text:** 3 default runs and 5 forced plans, as above, each `26 passed, 4 xfailed`; coverage with a private `COVERAGE_FILE` as in the Result line; `ruff check` passed. 20 repeats of every test in one process: nothing red. `REFX_MODE=fix` over the nine files: 252 passed with `--runxfail`; with the markers on, 14 strict `XPASS(strict)`, 233 passed, 5 xpassed.

**The verifier's named variants, rebuilt here** (`refx_var.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refx`, `-p refx_var`, `REFX_VAR=<name>`, in-process, nothing in `app/`; not the verifier's own files). The compare variants keep `==` for an empty or `None` argument, so the old cards do not catch them by accident. Each run on the default plan, markers on:

| Variant | Pass cards that fail |
|---|---|
| `sd_r4_by_only_if_given` | WOT-SD-12 |
| `rs_r6_refuse_deleted_twin_ci` | WOT-RS-12 |

`rs_r6_refuse_deleted_twin`, the exact-name shape, was not built: as `work_order_type.verify.md` says, two deleted rows of one exact name cannot exist until the constraint goes, so no card can catch it today.

## Notes for maintainers
- The clock is patched to NOW by the autouse `clock`; `updated_at` is the database's `now()`, so no card compares it with NOW.
- `db.refresh(row)` follows a failed write before each read, as the Conventions say.
- When BUG-1214 is fixed, the four cards turn the run red: remove the markers.
- IN-01 stays green across the fix: it asserts `23505` only (Spec gap 2).
