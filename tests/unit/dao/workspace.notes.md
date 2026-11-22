# Execution notes — `app/dao/workspace.py`

> Cases: `tests/unit/dao/workspace.cases.md` (Revision 2, READY, 23 cases) · Tests: `tests/unit/dao/test_workspace.py` · Source commit: e48a092
> Result: **23 tests for 23 cases — 23 passed · 0 xfail · 0 open discrepancies (DISCREPANCY-1 closed) · 0 errors** — branch coverage 100% line and branch (8 statements, 0 branches).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_workspace.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file (not kept in the repo; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refx\gen.py`), so values are the card's own text. The fixtures and helpers were written by hand from the Conventions. A separate audit script (`check.py`) checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matching the card's Then count, every quoted literal of the Given, When and Then lines present, marker and bug matching the Expect line, no unused argument, no fixture used without being an argument. LF only.

## How the tests are built
- **Nothing is patched.** `created_at`, `updated_at` use the model's own `utcnow`.
- **No standing rows:** "No workspace exists in a test unless its Given lists it". `W(s)` is `make_workspace(db, slug=s)`.
- **`stored_count(db)`** is "nothing written"; `without(columns, *names)` is "unchanged(X) except ...".
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener on the session's connection, around the When only; `recorder.written()` is the card's `written`.
- **Row letters** of the cards are lower case in the code (`A` becomes `a`, `P` becomes `p`). A Given row no later line names is built without a variable (F841). Lines such as "W1 has no status" add no code.
- **Reading helpers (no expected values inside):** `snap(db, row)` is every column by a Core select, for "unchanged"; `reread(db, row)` is `db.expire_all()` then SELECT by id.

## xfail location (`--runxfail`, reading the failing value)
No expected-to-fail card.

**Proof of the lines past the failure point.** Not needed: no xfail card.

## Discrepancies
| ID | Case | Designed | Actual | Evidence | Likely cause |
|---|---|---|---|---|---|
| DISCREPANCY-1 (kind `flaky`) | WSP-IN-04 | pass, Then 3 `updated_at != U0` on every run | Fails on Then 3 about 1 run in 400 | Repeated by a scratch plugin: 1 of 300, then 6, 12 and 4 of 3,000 each (23 of 9,300, 0.25%). The failing line: `assert datetime(2026, 11, 2, 19, 40, 19, 250962) != datetime(2026, 11, 2, 19, 40, 19, 250962)`. It passed all 10 matrix runs and 20 repeats. | The card's reasoning is that the column comes from Python's `utcnow`, but `datetime.now` moves in clock ticks on Windows under Python 3.12, so the insert and the update can land in one tick. The code is right; the card assumes a clock it does not control. |

**Closed.** WSP-IN-04 now waits in its Given, as revision 1 of the card says (Given 4): `while utcnow() <= U0: pass`, in the test `while utcnow() <= u0:`, before the snapshot `before_a`. No assertion changed. Spec N3's "later than `created_at` inside one test" has the same clock assumption.

Result: 0 of 6,000 failed (three runs of 2,000), against 23 of 9,300 before. Then 4 is safe by the same wait: `updated_at` is past `U0`, and `U0` is not earlier than `created_at`.

## Spec gaps of the cases file, checked
All assumed paths held: `WorkspaceCreate`, `WorkspaceUpdate` are in `app.schemas.workspace`; `name`, `slug`, `billing_email` are accepted; `"cancelled"` is stored.

## Coverage gaps
None — 100% line and branch coverage.

Run with a private `COVERAGE_FILE`. Inherited `BaseDAO` methods live in `app/dao/base.py` and are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
5 default runs and 5 forced plans, each `20 passed`; the coverage run the same. All pass cards passed and every strict card xfailed in each. 20 more repeats of every test, in one process: nothing red. `PGOPTIONS` carried five forced plans: `enable_seqscan=off`; that plus hash join and nested loop off; `enable_hashjoin=off`; index, bitmap and index-only scans off; that plus hash and merge join off. `ruff check`: all checks passed.

After the wait was added: 5 more default runs and the coverage run, each `20 passed`, 100%; `ruff check` passed. The forced plans were not rerun: the change touches no query.

## Revision history
- **Revision 2 of the cases (workspace.verify.md, case-missing findings):** added WSP-GS-17, GS-18, GS-19. The new tests were transcribed from the cards by the same parser and inserted at their card's place; no existing test changed except that WSP-IN-04, revision 1, has its snapshot after the wait, as "after the last Given line" says. The audit script passed on every card of the file.
- **Rerun of the final text:** 3 default runs and 5 forced plans, as above, each `23 passed`; coverage with a private `COVERAGE_FILE` as in the Result line; `ruff check` passed. 20 repeats of every test in one process: nothing red. `REFX_MODE=fix` over the nine files: 252 passed with `--runxfail`; with the markers on, 14 strict `XPASS(strict)`, 233 passed, 5 xpassed.

**The verifier's named variants, rebuilt here** (`refx_var.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refx`, `-p refx_var`, `REFX_VAR=<name>`, in-process, nothing in `app/`; not the verifier's own files). The compare variants keep `==` for an empty or `None` argument, so the old cards do not catch them by accident. Each run on the default plan, markers on:

| Variant | Pass cards that fail |
|---|---|
| `txt_contains_auto` | WSP-GS-17, GS-18 |
| `txt_startswith` | WSP-GS-17 |
| `txt_endswith` | WSP-GS-18 |
| `gs_w_dirty_hit` | WSP-GS-19 |
| `gs_w_expire` | WSP-GS-19 |

## Notes for maintainers
- WSP-IN-04 is the only card of the nine DAO files that compares two real-clock stamps. Its wait is what makes that safe on Windows; do not remove it.
- WSP-IN-01's message is pinned to `owner_position`, the first field of `WorkspaceCreate` the model does not have.
