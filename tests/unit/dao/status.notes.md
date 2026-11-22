# Execution notes — `app/dao/status.py`

> Cases: `tests/unit/dao/status.cases.md` (READY, 12 cases) · Tests: `tests/unit/dao/test_status.py` · Source commit: e48a092
> Result: **12 tests for 12 cases — 10 passed · 2 xfail · 0 discrepancies · 0 errors** — branch coverage 100% line and branch (5 statements, 0 branches); the class is empty.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_status.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file (not kept in the repo; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refx\gen.py`), so values are the card's own text. The fixtures and helpers were written by hand from the Conventions. A separate audit script (`check.py`) checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matching the card's Then count, every quoted literal of the Given, When and Then lines present, marker and bug matching the Expect line, no unused argument, no fixture used without being an argument. LF only.

## How the tests are built
- **Nothing is patched** (Conventions, Externals: None).
- **Standing rows:** `w1`, `w2`, `u1`, through the autouse `standing_rows`.
- **Builders (flush before returning):** `mk_status(**columns)` = "status"; `mk_transfer(status)` = "transfer on S".
- **STS-RM-02's `F`** is written `_add(db, OrderWorkflow(...))`: its Given line says "added and flushed".
- **`count:` lines:** `count_rows(db, table, **filters)`, a `SELECT count(*)` through `db.scalar(text(...))`.
- **Row letters** of the cards are lower case in the code (`A` becomes `a`, `P` becomes `p`). A Given row no later line names is built without a variable (F841). Lines such as "W1 has no status" add no code.
- **Reading helpers (no expected values inside):** `snap(db, row)` is every column by a Core select, for "unchanged"; `reread(db, row)` is `db.expire_all()` then SELECT by id.

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| STS-CR-07 | yes | Then 1, every run | `Failed: DID NOT RAISE IntegrityError` |
| STS-CR-08 | yes | Then 1, every run | `Failed: DID NOT RAISE IntegrityError` |

**Proof of the lines past the failure point.** Plugin `refx_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refx` (`-p refx_plug`, `REFX_MODE=fix`), nothing in `app/`: a unique index on `(workspace_id, lower(btrim(name)))`, created in each test's own transaction and rolled back with it. With `--runxfail`, all 12 tests pass, so Then 2 to 4 of both cards hold, and no pass card breaks with the index. With the markers on, both cards are `XPASS(strict)`.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Spec gaps of the cases file, checked
All assumed paths held: `app.schemas.status.StatusCreate` (`name`, `comment`), `app.models.transfer_order.TransferOrder`, location type `"storage"`. STS-CR-04's reading of R2 holds: a missing `name` raises 23502 on `name`.

## Coverage gaps
None — 100% line and branch coverage.

Run with a private `COVERAGE_FILE`. Inherited `BaseDAO` methods live in `app/dao/base.py` and are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
5 default runs and 5 forced plans, each `10 passed, 2 xfailed`; the coverage run the same. All pass cards passed and every strict card xfailed in each. 20 more repeats of every test, in one process: nothing red. `PGOPTIONS` carried five forced plans: `enable_seqscan=off`; that plus hash join and nested loop off; `enable_hashjoin=off`; index, bitmap and index-only scans off; that plus hash and merge join off. `ruff check`: all checks passed.

## Revision history
- **No new card.** The file was rerun with the batch; nothing in it changed.
- **Rerun of the final text:** 3 default runs and 5 forced plans, as above, each `10 passed, 2 xfailed`; coverage with a private `COVERAGE_FILE` as in the Result line; `ruff check` passed. 20 repeats of every test in one process: nothing red. `REFX_MODE=fix` over the nine files: 252 passed with `--runxfail`; with the markers on, 14 strict `XPASS(strict)`, 233 passed, 5 xpassed.

## Notes for maintainers
- When BUG-1221's index lands, CR-07 and CR-08 turn the run red: remove their markers.
- `remove` emits `LegacyAPIWarning`; the Conventions accept it.
