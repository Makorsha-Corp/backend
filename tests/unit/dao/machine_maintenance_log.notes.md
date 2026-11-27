# Execution notes — `app/dao/machine_maintenance_log.py`

> Cases: `tests/unit/dao/machine_maintenance_log.cases.md` (revision 1, READY, 183 cases: 165 pass, 18 xfail; spec APPROVED 2026-10-31) · Tests: `tests/unit/dao/test_machine_maintenance_log.py` · Source commit: e48a092
> Result: **183 tests for 183 cases — 165 passed · 18 xfailed (13 strict, 5 non-strict) · 0 XPASS · 0 discrepancies open (DISCREPANCY-1 closed) · 0 errors** — line and branch coverage 100% (35 statements, 0 branches).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine_maintenance_log.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file (session scratchpad, not kept), which stops on any line it does not know, so values are the card's own text. Fixtures and helpers were written by hand. The 15 revision 1 cards came from the same parser and were inserted at their card positions: the diff against the file before them is 229 lines added, 0 removed. An AST pass checked all 183: each ID exactly once, `# Then 1..N` matches the card's Then count in order, marker and bug match the Expect line, no unused or missing fixture, every quoted Then value is in the test.

## How the tests are built
- **One patch:** the autouse fixture `clock` is `patch("app.dao.machine_maintenance_log.utcnow", create=True, return_value=NOW)`. Nothing else is mocked. The commit spy wraps the real `db.commit` (`patch.object(db, "commit", wraps=db.commit)`).
- **Constants:** `dao`, `MISSING`, `D1` … `D5`, `T0`, `NOW`. `NEW` is the fixture `new`, because it holds `W1.id` and `M1.id`.
- **Standing rows:** one fixture per Conventions row (`w1`, `w2`, `p1`, `p2`, `f1`, `fd`, `fi`, `f9`, `m1`, `m2`, `md`, `mi`, `mf`, `mg`, `m9`); the autouse `standing_rows` makes all of them exist in every test. `w2` depends on `w1` and `p2` on `p1`, so ids rise in Conventions order.
- **Builders (fixtures, flush before returning):** `mk_log(gone=False, **columns)` = "log"; `gone=True` = "gone", and a column named beside it replaces that value (INH-43). `mk_dated_logs(count)` = the 101 logs built with `add_all` (GW-12, GW-13, GM-12, GM-25, GT-15, GT-24, GP-19, GP-27).
- **Reading helpers (no expected values inside):** `ids`; `reread(db, row)`; `snap(db, row)` (every column of any table, Core select); `without(snapshot, *columns)` ("unchanged except"); `count_rows(db, where, **params)`, `count_activity(db, where, **params)` (the same count on `machine_activity_events`, SD-13 and RS-10) and `written(db)`, all `db.scalar(text(...))` as the Conventions ask. The spec does not name that table yet; the model does (`app/models/machine_activity_event.py`, column `machine_id`).
- **Database-error cards:** `with pytest.raises(X) as exc:` around `with db.begin_nested():`; that block is Then 1. SD-10 and INH-35 call `db.refresh(a)` right after it (Conventions, "after a failed write"). INH-06 and INH-21 use a plain `pytest.raises`.
- **Rolled back:** `sp = db.begin_nested()` directly before the call, inside the spy's `with`; `sp.rollback()` and, where the row still exists, `db.refresh(a)` open the first "after the savepoint rollback" Then.
- **Statement recorder:** `StatementRecorder(db)`, as in `test_machine_item.py`, around the When only. `[sql] = recorder.selects()` fails loudly unless exactly one SELECT was sent. RS-03 reads `recorder.statements`, after the Given's `db.refresh(a)`.
- **Given rows no line names again** are built without a variable.
- **Probe:** `machine_maintenance_logs` has 0 committed rows in `marker_test`, so the absolute count of `summary = 'Pending'` holds.
- **`# noqa`:** the repo's ruff asks to change three things the cards write literally: `DTZ001` (naive `T0`, `NOW`), `RUF017` (GW-11 Then 2), `FURB157` (`Decimal("0")`, `Decimal("10000000000000")`). They stay as the cards wrote them.

## xfail location (`--runxfail`, reading the failing value)
Every bug card fails on the Then its `Fails today on` names, checked by script from the traceback line.

| Cards | Strict | Fails on | Actual |
|---|---|---|---|
| GW-10, GM-11, GT-13, GP-16 | yes | Then 4 | `order_part` = ` machine_maintenance_logs.maintenance_date DESC \n LIMIT ... OFFSET ...`: no `id` key |
| GW-24, GT-22 | yes | Then 3 | `[A.id, X.id]`, not `[A.id]` |
| GW-25, GT-25 | yes | Then 3 | one row left after `skip=1`, not `[]` |
| GM-20, GP-25 | yes | Then 3 | `[X]`, not `[]` |
| GI-09 | yes | Then 2 | X returned, not `None` |
| SD-02, SD-05 | yes | Then 3 | `deleted_at` = the database's `now()` (`2026-10-31 16:30:12…`), not NOW (`2031-05-06 07:08:09`) |
| GW-09, GM-10, GT-12, GP-15 | no | Then 2 | `[A.id, B.id, C.id]`, not `[C.id, B.id, A.id]`, in the revision 1 run; GM-10 read `[B.id, C.id, A.id]` in the first round |
| GW-11 | no | Then 2 | ids shown, sorted: A twice, B never |

**Proof that the non-strict cards can fail on Then 2.** An explicit wrong `ORDER BY` is a legal result for a query that asks for no tie-break and depends on neither plan nor heap. Done in a scratch pytest plugin (a `before_cursor_execute` rewrite, nothing in `app/`), under `--runxfail`:

| Explicit order | Non-strict cards failing on Then 2 | Other failures |
|---|---|---|
| ties by `id` ascending in every window | GW-09, GM-10, GT-12, GP-15 | GW-11 fails on Then 3, not 2: a fixed order pages cleanly. The 13 strict cards |
| ties by `id` ascending for `skip < 2`, descending from `skip = 2` | all 5: GW-09, GM-10, GT-12, GP-15, GW-11 (GW-11 sorted: `[A, A, B, B, C]`) | the 13 strict cards |

The second row is the proof for all five. Each row is 18 failed, 165 passed: no pass card failed.

**Proof of the later Then lines.** With an in-process simulation of the three fixes (`ORDER BY maintenance_date DESC, id DESC`; a correlated `EXISTS` comparing the machine's `workspace_id` to the log's in all five reads; `deleted_at = utcnow()`), in a scratch pytest plugin, `--runxfail` gives **183 passed**. So every Then after a failing one is reachable and right, GM-21 and the "writes nothing" cards hold with the fix, and no pass card depends on a bug.

## Gap variants (`machine_maintenance_log.verify.md` Findings 1–6)
Each variant ran on the fix simulation under `--runxfail`, in my own scratch plugin, rewritten from the verifier's definitions (its scripts were read, not run). With no variant: 183 passed. Each variant gives **1 failed, 182 passed**, the card shown, by assertion.

| Variant | Card | Failing value |
|---|---|---|
| `get_by_workspace:page_del` | GW-26 | `[B.id, C.id]`, not `[C.id]` |
| `get_by_machine:page_del` | GM-24 | the same |
| `get_by_type:page_del` | GT-23 | the same |
| `get_by_machine_and_type:page_del` | GP-26 | the same |
| `get_by_type:page_link` | GT-25 | one row, not `[]` |
| `get_by_machine:cap100` | GM-25 | `100 == 101` |
| `get_by_type:cap100` | GT-24 | `100 == 101` |
| `get_by_machine_and_type:cap100` | GP-27 | `100 == 101` |
| `sd:stamp_updated_by` | SD-12 | `updated_by` = P1, not P2 |
| `sd:activity` | SD-13 | `1 == 0` |
| `rs:activity` | RS-10 | `1 == 0` |
| `cost:py_round_update` | INH-45 | `Decimal("0.13")`, not `Decimal("0.125")` |

The 12 Finding survivors are closed. The three `factory_active` shapes the verifier named as its own call are closed the same way: `get_by_id_and_workspace` → GI-10 (`None`), `get_by_machine` → GM-26 (`[]`), `get_by_machine_and_type` → GP-28 (`[]`), each 1 failed, 182 passed.

## Discrepancies
None open. No card was changed by the executor and no marker was loosened.

| ID | Case | Designed | Actual | Evidence | Outcome |
|---|---|---|---|---|---|
| DISCREPANCY-1 (closed) | MML-RS-03 | pass: no UPDATE, `updated_at` stays `None` | In the first round, a strict xfail failing on Then 2: one `UPDATE machine_maintenance_logs SET updated_at=now(), deleted_at=%(deleted_at)s, deleted_by=%(deleted_by)s WHERE ...` | Probe of `dao.restore` on the same row held three ways. Flushed only (the old Given): `deleted_at`, `deleted_by`, `updated_at` and others are unloaded, the UPDATE is sent, `updated_at` is stamped. After `db.refresh(A)`: no statement, `updated_at` `None`. After `dao.get_by_id_and_workspace` on an expired session: no statement, `updated_at` `None`. | **Card, not code.** Setting `None` over an unloaded column is a change to SQLAlchemy. Spec R3 is right for any log read from the database. The main session added `db.refresh(A)` to the Given and removed the marker; the card now passes. Not a defect, so `docs/testing/bugs.md` has no entry. |

Prose only, no test affected:
- **"this usually moves A physically behind them" (GW-09, GW-11, GM-10, GT-12, GP-15):** only GM-10 showed that picture, once, in the first round. In the revision 1 run it came back in ascending id, as GW-09, GT-12 and GP-15 did both times. All five still failed on Then 2.
- **"can match by accident":** no non-strict card XPASSed in any run (see Stability). They stay non-strict as designed.

## Workspace cascade card (MML-INH-44, inherited R14; Spec gap 3)
The card **passes as designed.** The raw `DELETE` on W3 removes one workspace, the cascade removes log A, and B and M1 stay. `make_workspace` rows do not block it (its subscription plan is a parent row).

Probe beyond the card, every step rolled back, for the spec's open question:
- All 98 foreign keys to `workspaces` are `ON DELETE CASCADE`. `workspaces` and `machine_maintenance_logs` have no trigger.
- A workspace with factories, machines and its own logs is deleted: W2 with a factory and a machine, W1 with those and a log.
- **One block found:** a log of another workspace sitting on one of its machines (the HR-16 shape) refuses the delete, `machine_maintenance_logs_machine_id_fkey`, because `machine_id` has no cascade. So a BUG-1101 row can block a workspace delete. No card covers it; the spec could note it under inherited R14.

## Coverage gaps
None — 100% line and branch coverage of `app/dao/machine_maintenance_log.py` (35 statements, 0 branches). Inherited `create`, `update`, `remove`, `get`, `get_multi` live in `app/dao/base.py` and are measured by `tests/unit/dao/test_base.py`.

Command: `COVERAGE_FILE=<private path> .venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine_maintenance_log.py -q -p no:cacheprovider --cov=app.dao.machine_maintenance_log --cov-branch --cov-report=term-missing`

## Factories added
None.

## Stability
| Run | Result | XPASS |
|---|---|---|
| Default, 3 runs + the coverage run + the last run | 165 passed, 18 xfailed each | 0 |
| `PGOPTIONS="-c enable_seqscan=off"`, 2 runs | 165 passed, 18 xfailed | 0 |
| `PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off"`, 2 runs | 165 passed, 18 xfailed | 0 |
| The line above + `-c enable_sort=off`, 2 runs | 165 passed, 18 xfailed | 0 |
| `PGOPTIONS="-c enable_seqscan=off -c enable_bitmapscan=off"`, 2 runs | 165 passed, 18 xfailed | 0 |

These are the revision 1 runs, and they are the runs made, not a promise: which ties fail depends on plan and heap, so a non-strict card may XPASS later without turning the run red. The proof that they can fail is the explicit wrong `ORDER BY` above. `tests/unit/dao/test_base.py` with this file: 227 passed, 21 xfailed. `ruff check` on the file: all checks passed. The file has LF line endings.

## Notes for maintainers
- BUG-1100 fixed: GW-10, GM-11, GT-13, GP-16 XPASS strict and turn the run red, the five non-strict cards may XPASS quietly; remove all nine markers. A fix that wraps the query in a subquery or alias needs those recorder lines changed (Spec gap 5).
- BUG-1101 fixed: GW-24, GW-25, GI-09, GM-20, GT-22, GT-25, GP-25 XPASS strict. The X rows in GW-02, GI-02, GM-02, GT-02, GP-02 and the Then lines counting them should still pass.
- BUG-1102 fixed: SD-02, SD-05 XPASS strict. The fix imports `utcnow` into the module, and the `create=True` of the `clock` fixture then does nothing.
- `remove` emits a `LegacyAPIWarning` (`Query.get`, `app/dao/base.py:136`): two warnings in each run, from INH-39 and INH-40.
- A row built by `mk_log` holds only the columns it was given until it is refreshed. A card that sets `None` on it and expects no UPDATE needs a refresh first (DISCREPANCY-1).

## Revision history
- **First round (168 cases):** 150 passed, 18 xfailed, DISCREPANCY-1 on MML-RS-03.
- **After stage 4, main session (2026-10-31):** DISCREPANCY-1 closed. MML-RS-03's Given reads A back with `db.refresh(A)`, as a real caller's row would be, and the marker is gone: 151 passed, 17 xfailed. Seen beyond the cards: a BUG-1101 row refuses a workspace delete (see the cascade section).
- **Revision 1 of the cases (`machine_maintenance_log.verify.md` Findings 1–7 and the `factory_active` call):** added MML-GW-26, GI-10, GM-24, GM-25, GM-26, GT-23, GT-24, GT-25, GP-26, GP-27, GP-28, SD-12, SD-13, RS-10, INH-45 (14 pass, GT-25 strict BUG-1101), each at its card position. No existing test changed. One helper added, `count_activity`. These notes corrected throughout (Finding 7): 165 passed, 18 xfailed.
