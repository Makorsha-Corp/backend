# Execution notes — `app/dao/sales_order_event.py`

> Cases: `tests/unit/dao/sales_order_event.cases.md` (revision 1, READY, 21 cases; spec APPROVED 2026-11-01) · Tests: `tests/unit/dao/test_sales_order_event.py` · Source commit: e48a092
> Result: **21 tests for 21 cases — 21 passed · 0 xfailed · 0 discrepancies · 0 errors** — line and branch coverage 100% (9 statements, 0 branches).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_sales_order_event.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. Built in one batch with its seven siblings. The card bodies were transcribed by a throwaway parser of the cases file (not kept; `scratchpad\evx\`), so values are the card's own text. The standing rows and helpers were written by hand. A separate AST pass, reading the cards again, checked: each ID exactly once and in card order, `# Then 1..N` matches the card's Then count in order with a check under each, every backticked Then expression is present and in order, marker and bug match the Expect line, one builder call per Given row, no unused argument, no fixture used without being an argument.

## How the tests are built
- **Nothing is patched** (Conventions, Externals: None).
- **Constants:** `dao` (the singleton, a module-level name), `MISSING = 999999999`, `T1`, `T2`, `T3`.
- **Standing rows:** one fixture per Conventions row (`w1`, `w2`, `u1`, `f1`, `f9`, `st1`, `st9`, `ac1`, `ac9`, `o1`, `o2`, `o9`); the autouse `standing_rows` makes all of them exist in every test. Each test lists only those it names. `w2` depends on `w1`, so ids rise in Conventions order.
- **Builders (keyword-only fixtures, flush before returning):** `mk_event(created_at=, **columns)` = "event"; `metadata_json` and `performed_by` stay out of the constructor unless the card gives them, so `metadata_json=None` (JSON `null`) differs from no keyword (SQL `NULL`). `mk_log(count)` = the `add_all` Given of the long-log cards, returns `newest_first`.
- **Reading helpers (no expected values inside):** `ids`; `snap(db, row)` (every column, Core select, for "unchanged"; the check runs `db.expire_all()` first, as "re-read" says); `stored_count(db)` ("nothing written"); `stored_json(db, row)`.
- **Given rows no line names again** are built without a variable (F841).
- **U2, U3** (the id-against-other-columns cards) are local to their tests: `make_profile(db)` twice, first in the body, so they come after U1.
- **Row letters** of the cards are lower case in the code (`A` → `a`, `P` → `p`).
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener on the session's connection, around the When only. `recorder.sql()` is the one SELECT naming this table and fails loudly unless there is exactly one.

## Discrepancies
None. No card was changed and no marker was loosened.

## Coverage gaps
None — 100% line and branch coverage of `app/dao/sales_order_event.py` (9 statements, 0 branches, 0 missed). The inherited `BaseDAO` methods live in `app/dao/base.py` and are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
### Revision 1
8 runs, one process each, on the patched file: 3 default, 5 forced plans.

| Run | Result |
|---|---|
| Default, 3 runs | 21 passed |
| `PGOPTIONS="-c enable_seqscan=off"` | 21 passed |
| `PGOPTIONS="-c enable_seqscan=off -c enable_hashjoin=off -c enable_nestloop=off"` | 21 passed |
| `PGOPTIONS="-c enable_hashjoin=off"` | 21 passed |
| `PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off -c enable_indexonlyscan=off"` | 21 passed |
| The line above + `-c enable_hashjoin=off -c enable_mergejoin=off` | 21 passed |

`ruff check` on the patched file: all checks passed. Line endings: LF. Coverage unchanged: 100% line and branch, with a private `COVERAGE_FILE`.

### Revision 0
10 runs, one process each, on the final file. `PGOPTIONS` reaches the connection (`SHOW enable_seqscan` → `off`).

| Run | Result |
|---|---|
| Default, 5 runs | 18 passed |
| `PGOPTIONS="-c enable_seqscan=off"` | 18 passed |
| `PGOPTIONS="-c enable_seqscan=off -c enable_hashjoin=off -c enable_nestloop=off"` | 18 passed |
| `PGOPTIONS="-c enable_hashjoin=off"` | 18 passed |
| `PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off -c enable_indexonlyscan=off"` | 18 passed |
| The line above + `-c enable_hashjoin=off -c enable_mergejoin=off` | 18 passed |

`ruff check` on the file: all checks passed. Line endings: LF.

## Revision history
- **Revision 1 of the cases (`sales_order_event.verify.md`):** added SOE-G-19 ... G-21, all `pass`, each after the last card. SOE-G-18 gained Then 5, 6 and Then 10, its old Then 5 ... 7 are now 7 ... 9, and its Rules line changed.
- The file was patched, not regenerated (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\evx\patch.py`): a diff against the delivered file shows those lines and the additions only. The AST pass ran again over all cards: 0 problems.

## Notes for maintainers
- The raw `DELETE` of SOE-G-11 proves the database's cascade only, as cases Spec gap 3 says.
- `recorder.sql()` picks statements by the table name, so a second statement on this table during a When fails the test at that line, not at a Then.
- "Nothing written" counts committed rows of all workspaces too. A run beside something that commits to this table could break it; nothing did here.
- The file carries a `# ruff: noqa` line: the Conventions prescribe naive datetimes.
