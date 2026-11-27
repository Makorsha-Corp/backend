# Execution notes — `app/dao/app_settings.py`

> Cases: `tests/unit/dao/app_settings.cases.md` (Revision 1, READY, 23 cases) · Tests: `tests/unit/dao/test_app_settings.py` · Source commit: e48a092
> Result: **23 tests for 23 cases — 21 passed · 2 xfail · 0 discrepancies · 0 errors** — branch coverage 100% line and branch (9 statements, 0 branches).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_app_settings.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file (not kept in the repo; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refx\gen.py`), so values are the card's own text. The fixtures and helpers were written by hand from the Conventions. A separate audit script (`check.py`) checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matching the card's Then count, every quoted literal of the Given, When and Then lines present, marker and bug matching the Expect line, no unused argument, no fixture used without being an argument. LF only.

## How the tests are built
- **Nothing is patched.**
- **Standing rows:** `w1`, `w2`, through the autouse `standing_rows`.
- **Builder:** `mk_setting(**columns)` = "setting".
- **`stored_count(db)`** is "nothing written".
- **Database-error cards:** `with pytest.raises(...)` around `with db.begin_nested():`; that block is Then 1, and `as exc` is there only when a later line reads it.
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener on the session's connection, around the When only; `recorder.written()` is the card's `written`.
- **Row letters** of the cards are lower case in the code (`A` becomes `a`, `P` becomes `p`). A Given row no later line names is built without a variable (F841). Lines such as "W1 has no status" add no code.
- **Reading helpers (no expected values inside):** `snap(db, row)` is every column by a Core select, for "unchanged"; `reread(db, row)` is `db.expire_all()` then SELECT by id.

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| ASG-CR-01 | yes | Then 1, every run | `Failed: DID NOT RAISE IntegrityError` |
| ASG-CR-02 | yes | Then 1, every run | `Failed: DID NOT RAISE IntegrityError` |

**Proof of the lines past the failure point.** Plugin `refx_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refx` (`-p refx_plug`, `REFX_MODE=fix`), nothing in `app/`: a unique index on `(workspace_id, lower(btrim(name)))`, created in each test's own transaction. With `--runxfail`, all 17 tests pass, so Then 2 to 4 hold and no pass card breaks with the index. With the markers on, both cards are `XPASS(strict)`.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Spec gaps of the cases file, checked
None of the file's assumptions was wrong.

## Coverage gaps
None — 100% line and branch coverage.

Run with a private `COVERAGE_FILE`. Inherited `BaseDAO` methods live in `app/dao/base.py` and are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
5 default runs and 5 forced plans, each `15 passed, 2 xfailed`; the coverage run the same. All pass cards passed and every strict card xfailed in each. 20 more repeats of every test, in one process: nothing red. `PGOPTIONS` carried five forced plans: `enable_seqscan=off`; that plus hash join and nested loop off; `enable_hashjoin=off`; index, bitmap and index-only scans off; that plus hash and merge join off. `ruff check`: all checks passed.

## Revision history
- **Revision 1 of the cases (app_settings.verify.md, case-missing findings):** added ASG-GN-14 ... GN-19. The new tests were transcribed from the cards by the same parser and inserted at their card's place; no existing test changed. The audit script passed on every card of the file.
- **Rerun of the final text:** 3 default runs and 5 forced plans, as above, each `21 passed, 2 xfailed`; coverage with a private `COVERAGE_FILE` as in the Result line; `ruff check` passed. 20 repeats of every test in one process: nothing red. `REFX_MODE=fix` over the nine files: 252 passed with `--runxfail`; with the markers on, 14 strict `XPASS(strict)`, 233 passed, 5 xpassed.

**The verifier's named variants, rebuilt here** (`refx_var.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refx`, `-p refx_var`, `REFX_VAR=<name>`, in-process, nothing in `app/`; not the verifier's own files). The compare variants keep `==` for an empty or `None` argument, so the old cards do not catch them by accident. Each run on the default plan, markers on:

| Variant | Pass cards that fail |
|---|---|
| `txt_contains_auto` | ASG-GN-14, GN-15, GN-18 |
| `txt_startswith` | ASG-GN-14 |
| `txt_endswith` | ASG-GN-15, GN-18 |
| `txt_like_esc_pct` | ASG-GN-16 |
| `txt_lower_col` | ASG-GN-17 |
| `txt_trim_col` | ASG-GN-18 |
| `gn_w_expire` | ASG-GN-19 |
| `gn_w_dirty_hit` | ASG-GN-19, and GN-01, GN-02: it flips the row's one spare column, as the verifier says |

## Notes for maintainers
- When BUG-1225's index lands, CR-01 and CR-02 turn the run red: remove their markers.
