# Execution notes — `app/dao/subscription_plan.py`

> Cases: `tests/unit/dao/subscription_plan.cases.md` (Revision 1, READY, 12 cases) · Tests: `tests/unit/dao/test_subscription_plan.py` · Source commit: e48a092
> Result: **12 tests for 12 cases — 11 passed · 1 xfail · 0 discrepancies · 0 errors** — branch coverage 90% (10 statements, 1 missed, 0 branches).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_subscription_plan.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file (not kept in the repo; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refx\gen.py`), so values are the card's own text. The fixtures and helpers were written by hand from the Conventions. A separate audit script (`check.py`) checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matching the card's Then count, every quoted literal of the Given, When and Then lines present, marker and bug matching the Expect line, no unused argument, no fixture used without being an argument. LF only.

## How the tests are built
- **Nothing is patched.**
- **No standing rows.** "plan" is `make_subscription_plan(db, name=...)` called directly, with the card's columns.
- **SBP-GD-05** counts the whole table: `subscription_plans` held no committed rows in any run.
- **`stored_count(db)`** is "nothing written".
- **Database-error cards:** `with pytest.raises(...)` around `with db.begin_nested():`; that block is Then 1, and `as exc` is there only when a later line reads it.
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener on the session's connection, around the When only; `recorder.written()` is the card's `written`.
- **Row letters** of the cards are lower case in the code (`A` becomes `a`, `P` becomes `p`). A Given row no later line names is built without a variable (F841). Lines such as "W1 has no status" add no code.
- **Reading helpers (no expected values inside):** `snap(db, row)` is every column by a Core select, for "unchanged"; `reread(db, row)` is `db.expire_all()` then SELECT by id.

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| SBP-GD-07 | yes | Then 1, every run | `Failed: DID NOT RAISE IntegrityError` |

**Proof of the lines past the failure point.** Plugin `refx_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refx` (`-p refx_plug`, `REFX_MODE=fix`), nothing in `app/`: a partial unique index on `is_default WHERE is_default AND is_active`, created in each test's own transaction. With `--runxfail`, all 11 tests pass, so Then 2 to 4 hold and GD-08, GD-09 stay green with the index. With the markers on, GD-07 is `XPASS(strict)`.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Spec gaps of the cases file, checked
None of the file's assumptions was wrong.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 15 | `dead` | `SubscriptionPlanDAO.get_by_name`: listed under Not specified, to be removed (on `docs/testing/dead-code-removal-checklist.md`). |


Run with a private `COVERAGE_FILE`. Inherited `BaseDAO` methods live in `app/dao/base.py` and are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
5 default runs and 5 forced plans, each `10 passed, 1 xfailed`; the coverage run the same. All pass cards passed and every strict card xfailed in each. 20 more repeats of every test, in one process: nothing red. `PGOPTIONS` carried five forced plans: `enable_seqscan=off`; that plus hash join and nested loop off; `enable_hashjoin=off`; index, bitmap and index-only scans off; that plus hash and merge join off. `ruff check`: all checks passed.

## Revision history
- **Revision 1 of the cases (subscription_plan.verify.md, case-missing findings):** added SBP-GD-12. The new tests were transcribed from the cards by the same parser and inserted at their card's place; no existing test changed. The audit script passed on every card of the file.
- **Rerun of the final text:** 3 default runs and 5 forced plans, as above, each `11 passed, 1 xfailed`; coverage with a private `COVERAGE_FILE` as in the Result line; `ruff check` passed. 20 repeats of every test in one process: nothing red. `REFX_MODE=fix` over the nine files: 252 passed with `--runxfail`; with the markers on, 14 strict `XPASS(strict)`, 233 passed, 5 xpassed.

**The verifier's named variants, rebuilt here** (`refx_var.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refx`, `-p refx_var`, `REFX_VAR=<name>`, in-process, nothing in `app/`; not the verifier's own files). The compare variants keep `==` for an empty or `None` argument, so the old cards do not catch them by accident. Each run on the default plan, markers on:

| Variant | Pass cards that fail |
|---|---|
| `gd_w_dirty_hit` | SBP-GD-12 |
| `gd_w_expire` | SBP-GD-12 |

## Notes for maintainers
- When BUG-1224's index lands, GD-07 turns the run red: remove the marker.
- A committed plan in `marker_test` fails GD-05 loudly, as the card intends.
