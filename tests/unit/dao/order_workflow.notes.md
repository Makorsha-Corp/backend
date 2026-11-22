# Execution notes — `app/dao/order_workflow.py`

> Cases: `tests/unit/dao/order_workflow.cases.md` (Revision 2, READY, 31 cases) · Tests: `tests/unit/dao/test_order_workflow.py` · Source commit: e48a092
> Result: **31 tests for 31 cases — 29 passed · 2 xfail · 0 discrepancies · 0 errors** — branch coverage 100% line and branch (8 statements, 0 branches).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_order_workflow.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file (not kept in the repo; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refx\gen.py`), so values are the card's own text. The fixtures and helpers were written by hand from the Conventions. A separate audit script (`check.py`) checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matching the card's Then count, every quoted literal of the Given, When and Then lines present, marker and bug matching the Expect line, no unused argument, no fixture used without being an argument. LF only.

## How the tests are built
- **Nothing is patched.**
- **Standing rows:** `w1`, `w2`, `u1`, through the autouse `standing_rows`.
- **Builders:** `mk_workflow(**columns)` = "workflow"; `mk_order(workflow)` = "order on F": the status, flushed, then the purchase order.
- **OWF-GT-02** calls the real `seed_po_workflow`.
- **`stored_count(db)`** is "nothing written"; `count_rows` is the `count:` lines.
- **Database-error cards:** `with pytest.raises(...)` around `with db.begin_nested():`; that block is Then 1, and `as exc` is there only when a later line reads it.
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener on the session's connection, around the When only; `recorder.written()` is the card's `written`.
- **Row letters** of the cards are lower case in the code (`A` becomes `a`, `P` becomes `p`). A Given row no later line names is built without a variable (F841). Lines such as "W1 has no status" add no code.
- **Reading helpers (no expected values inside):** `snap(db, row)` is every column by a Core select, for "unchanged"; `reread(db, row)` is `db.expire_all()` then SELECT by id.

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| OWF-IN-05 | yes | Then 1, every run | `Failed: DID NOT RAISE IntegrityError` |
| OWF-IN-07 | yes | Then 1, every run | `assert [1, 2] == [1, 2, 3]`: nothing raised, nothing saved |

**Proof of the lines past the failure point.** Plugin `refx_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refx` (`-p refx_plug`, `REFX_MODE=fix`), nothing in `app/`: `passive_deletes="all"` set in-process on `OrderWorkflow.purchase_orders` and its dependency processor, the fix BUG-1222 names. With `--runxfail`, all 25 tests pass, so IN-05's 23001, its count and `order_workflow_id == F.id` hold. With the markers on, IN-05 is `XPASS(strict)`.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Spec gaps of the cases file, checked
All assumed paths held: `app.models.purchase_order.PurchaseOrder`, `"storage"`. Gap 4's open point: `seed_po_workflow` flushes its statuses itself; the card's own `db.flush()` stays as written.

## Coverage gaps
None — 100% line and branch coverage.

Run with a private `COVERAGE_FILE`. Inherited `BaseDAO` methods live in `app/dao/base.py` and are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
5 default runs and 5 forced plans, each `24 passed, 1 xfailed`; the coverage run the same. All pass cards passed and every strict card xfailed in each. 20 more repeats of every test, in one process: nothing red. `PGOPTIONS` carried five forced plans: `enable_seqscan=off`; that plus hash join and nested loop off; `enable_hashjoin=off`; index, bitmap and index-only scans off; that plus hash and merge join off. `ruff check`: all checks passed.

## Revision history
- **Revision 1 of the cases (order_workflow.verify.md, case-missing findings):** added OWF-GT-20 ... GT-24. The new tests were transcribed from the cards by the same parser and inserted at their card's place; no existing test changed. The audit script passed on every card of the file.
- **Rerun of the final text:** 3 default runs and 5 forced plans, as above, each `29 passed, 1 xfailed`; coverage with a private `COVERAGE_FILE` as in the Result line; `ruff check` passed. 20 repeats of every test in one process: nothing red. `REFX_MODE=fix` over the nine files: 252 passed with `--runxfail`; with the markers on, 14 strict `XPASS(strict)`, 233 passed, 5 xpassed.

**The verifier's named variants, rebuilt here** (`refx_var.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refx`, `-p refx_var`, `REFX_VAR=<name>`, in-process, nothing in `app/`; not the verifier's own files). The compare variants keep `==` for an empty or `None` argument, so the old cards do not catch them by accident. Each run on the default plan, markers on:

| Variant | Pass cards that fail |
|---|---|
| `txt_contains_auto` | OWF-GT-20, GT-21, GT-23 |
| `txt_startswith` | OWF-GT-20 |
| `txt_endswith` | OWF-GT-21, GT-23 |
| `txt_like_esc_pct` | OWF-GT-22 |
| `txt_trim_col` | OWF-GT-23 |
| `gt_w_dirty_hit` | OWF-GT-24 |
| `gt_w_expire` | OWF-GT-24 |

- **Revision 2 of the cases (spec N4, BUG-1227):** added OWF-IN-07 by hand at the end of the file, its When being two calls; no existing test changed. `--runxfail` today: fails on Then 1, as the table above shows. Plugin, `REFX_MODE=fix`, now also calls `MutableList.associate_with_attribute(OrderWorkflow.status_sequence)` in-process: with `--runxfail`, 31 passed, so the card and every pass card hold on the fixed column; with the markers on, IN-05 and IN-07 are `XPASS(strict)`, 29 passed. 3 default runs, each `29 passed, 2 xfailed`; coverage 100%; `ruff check` passed; the audit passed. The forced plans were not rerun for this card: it reads one row by id.

## Notes for maintainers
- When BUG-1227 is fixed on the column, IN-07 turns the run red: remove the marker.
- When BUG-1222 is fixed on the relationship, IN-05 turns the run red: remove the marker.
- `remove` emits `LegacyAPIWarning`; the Conventions accept it.
