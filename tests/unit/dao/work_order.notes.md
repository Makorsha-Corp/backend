# Execution notes — `app/dao/work_order.py`

> Cases: `tests/unit/dao/work_order.cases.md` (Revision 3, READY, 189 cases) · Tests: `tests/unit/dao/test_work_order.py` · Source commit: e48a092
> Result: **189 tests for 189 cases — 167 passed · 22 xfailed (20 strict, 2 non-strict) · 0 discrepancies · 0 errors** — branch coverage 95% (110 statements, 7 missed, 38 branches, 0 partial; the 7 lines are the dead `restore`).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_work_order.py -q -p no:cacheprovider -o addopts=""`

## Who wrote what
Normal mode, no local model (full Claude): every test sits below a `# [claude] <ID>` comment, in card order. The two `Author: claude` cards (GW-28, MD-16, both non-strict) use the Conventions' recipe as written: two rows flushed in one transaction (same `created_at`), then `seqscan`.

## How the tests are built
- **Standing rows:** fixture `g` builds, in the Conventions' order and each flushed, W0, W1, W2 (`make_workspace`), U1–U3 (`make_profile`), W0's F0/T0/M0/P0, W1's FA < F1 < FB, TA < T1 < TB, MA < M1 < MB, MX, MY, PA < P1 < PB, then W2's F2/T2/M2/P2. `g.completed`, `g.voided`, `g.started`, `g.deleted` hold the column sets of the Conventions' **completed** / **voided** / **started** / **deleted** (what a real complete / void / start / soft delete writes); a card's "but completed" is `**g.completed`.
- **Builders:** `mk(N, k=1, **but)` = "order N" (`k=0` / `k=2` = "order of W0 / W2", with that workspace's T, F, M); `draft(d, N, **but)` = "draft of P1 on d, number N" (later "but" columns override the template and date); `mk_orders(k, prefix, n)` = "orders(W, prefix, n)" (one flush after the loop); `_row(g, N, …)` builds without adding, for the loops of FD-11, OR-12, DC-11 and the pending / duplicate rows; `dirty_pending(db, g, O1)` = "dirty+pending". `id=XID(1)` is passed straight to the builder (`800_000_000 + (pid % 1_000_000) * 10 + 1`), so concurrent runs never pick the same explicit id.
- **Uniqueness across concurrent runs:** every test makes its own workspaces (`make_workspace` counts from the pid), and work order numbers are unique only per workspace (`uq_wo_workspace_number`), so numbers are stored exactly as carded. Nothing is committed.
- **Clocks:** `clockN(L, U)` patches `datetime.datetime` (a subclass whose `now()` returns L; the DAO imports `datetime` inside `get_next_number`, so the module attribute is read at call time), `app.utils.time.utcnow` and `app.dao.work_order.utcnow` (`create=True`). Every `NN` card without a clock line runs its When under `clockN(JUNE, JUNE)` (2031-06-01 12:00); NN-16 runs its Given call under it, as carded. `clockD(L, U)` patches `app.dao.work_order.date` (a subclass whose `today()` returns L) and both `utcnow`s; every `status_scope="planned"` card names one. SD-08 patches only the two `utcnow`s. `Dhaka` = `SET LOCAL TimeZone = 'Asia/Dhaka'`.
- **Statement recorder:** `before_cursor_execute` listener; `selects`, `written`, `sql` (fails loudly unless exactly one SELECT reads `work_orders`), `order_part` (text after the first `ORDER BY`, cut at `LIMIT` / `OFFSET`, whitespace-stripped). One-query cards end the Given with `db.expunge_all()` and read the ids they need into locals first, so no lazy reload shows up inside the When.
- **Reading helpers (no expected values inside):** `ids`, `idset`, `reread` (expire, then SELECT by id).
- **Parametrized cards** (identical setup and checks, one input differs): GI-08 … GI-11 (stored / read-back cost); NN-02, 04, 05, 06, 10, 18, 19 (stored numbers / expected next); NN-07, 08, 09, 26, 27 (strict xfail BUG-2676). Each case is its own param id.
- **Cards whose failing "Then 1" is the When itself** (DC-12, DC-13, DC-14, DC-17: the call raises TypeError today): the `# Then 1` comment sits directly above the call, as in the purchase order return precedent. NN-17's and NN-25's `raises:` Then 1 sits above the `pytest.raises` line.
- **NN-17:** `with pytest.raises(IntegrityError)` around `with db.begin_nested()`; W1's id is read before, so the count after the rolled-back savepoint needs no reload.
- **SD-07:** `sp = db.begin_nested()` before the call, `patch.object(db, "commit", wraps=db.commit)` around it, `cm.call_count == 0`, then `sp.rollback()` and the re-read.

## xfail location (`--runxfail`)
Plugin `failson_wo.py` (`-p failson_wo`, scratch `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaoe\wo\`). Result: 22 failed, 167 passed. Each xfail fails on the Then line its card names:

| Card | Strict | Card says | Fails on | Actual |
|---|---|---|---|---|
| SF-12 | yes | Then 2 | Then 2 | `{A, B} == {B}` (local 10 Nov used) |
| SF-13 | yes | Then 2 | Then 2 | `{B} == {A, B}` (local 11 Nov used) |
| SF-25 | yes | Then 2 | Then 2 | `{A, B} == {A}` (`_` wildcard) |
| SF-26 | yes | Then 2 | Then 2 | `{A, B} == {A}` (`%` wildcard) |
| SF-27 | yes | Then 1 | Then 1 | `{B} == {A}` (`\t` read as `t`) |
| GW-27 | yes | Then 2 | Then 2 | `'work_orders.id DESC' in 'work_orders.created_at DESC'` |
| GW-28 | no | Then 1 | Then 1 | `[A, B] == [B, A]` |
| MD-16 | no | Then 1 | Then 1 | lower id returned |
| MD-17 | yes | Then 3 | Then 3 | `'work_orders.id DESC' in 'work_orders.created_at DESC'` |
| DC-12 | yes | Then 1 | Then 1 (call) | `TypeError: … unexpected keyword argument 'exclude_completed'` |
| DC-13 | yes | Then 1 | Then 1 (call) | `TypeError: … 'search'` |
| DC-14 | yes | Then 1 | Then 1 (call) | `TypeError: … 'status_scope'` |
| DC-17 | yes | Then 1 | Then 1 (call) | `TypeError: … 'status_scope'` |
| NN-07 | yes | Then 2 | Then 2 | `'WO-2031-1000' == 'WO-2031-1001'` |
| NN-08 | yes | Then 2 | Then 2 | `'WO-2031-006' == 'WO-2031-011'` |
| NN-09 | yes | Then 2 | Then 2 | `'WO-2031-001' == 'WO-2031-006'` |
| NN-26 | yes | Then 2 | Then 2 | `'WO-2031-003' == 'WO-2031-006'` |
| NN-27 | yes | Then 2 | Then 2 | `'WO-2031-1001' == 'WO-2031-006'` (`int("1_000")` is 1000) |
| NN-20 | yes | Then 2 | Then 2 | `'WO-2032-001' == 'WO-2031-008'` |
| NN-21 | yes | Then 2 | Then 2 | `'WO-2031-008' == 'WO-2032-001'` |
| SD-08 | yes | Then 3 | Then 3 | `deleted_at` = the database's `now()` in Dhaka time, not SDT |
| SD-09 | yes | Then 3 | Then 3 | `deleted_at` six hours after the UTC window |

**Reference plugin** `ref_wo.py` (same folder, `-p ref_wo`, loaded through `PYTHONPATH`): `get_by_workspace` and `get_by_machine_date_type` order by `created_at DESC, id DESC` (BUG-2670, BUG-2671); sheet search escapes `\`, `%`, `_` with `ESCAPE '\'` (BUG-2672); "planned" compares with `utcnow().date()` (BUG-2673); `count_by_calendar_date_for_sheet` takes `status_scope=None`, `exclude_completed=False`, `search=None` and applies the list's filters (BUG-2675); `get_next_number` takes the year from `utcnow()` and the numerically highest all-ASCII-digit suffix + 1, padded to 3 (`[0-9]+` full match, so `1_000` is ignored; BUG-2676, BUG-2678); `soft_delete` stamps `utcnow()` (BUG-2679). With `--runxfail -p ref_wo`: **189 passed**. Nothing in `app/` changes.

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 374–380 | dead | `restore` — no caller; the spec's Q4 decides it is removed (`dead-code-removal-checklist`). |

Run with a private `COVERAGE_FILE` (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaoe\wo\.coverage`): `--cov=app.dao.work_order --cov-branch --cov-report=term-missing` → 110 statements, 7 missed, 38 branches, 0 partial, 95%. Inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None (all builders are local).

## Stability
| Run | Passed | xfailed | xpassed (non-strict) | Not as designed |
|---|---|---|---|---|
| plain 1 | 167 | 22 | 0 | 0 |
| plain 2 | 167 | 22 | 0 | 0 |
| plain 3 | 167 | 22 | 0 | 0 |
| `--runxfail` | 167 | — | — | 22 failed, each on its carded Then |
| `--runxfail` with the reference plugin | 189 of 189 | — | — | 0 |

`ruff check`: all checks passed (file-level `noqa: SIM117, DTZ001`, as the sales order and purchase order return files); `ruff format`: formatted. Line endings: LF.

## Notes for maintainers
- When BUG-2672 / 2673 / 2675 / 2676 / 2678 / 2679 are fixed, their strict xfail tests XPASS and fail: remove the markers. BUG-2670 / 2671: GW-27 and MD-17 XPASS (strict) — remove their markers and the non-strict ones of GW-28 and MD-16 at the same time.
- BUG-2675's fix adds keywords to `count_by_calendar_date_for_sheet`; DC-16 (no keyword) must keep passing.
- `clockN` patches `datetime.datetime` process-wide for the duration of the call; a fix that does `from datetime import datetime` at module level instead (or `utcnow()`) changes which patch takes effect — both are already patched.
- `created_at` is the database's `now()` (transaction start): rows of one test without an explicit stamp tie, which is what GW-28 / MD-15 / MD-16 rely on.
- `restore` (dead, spec Q4): remove it with the dead-code sweep; the 7 missed lines go with it.

## Revision history
- **Revision 2 (2026-11-14):** first execution of this cases file (no earlier test file existed).
- **Revision 3 (2026-11-14):** patched, not regenerated (cases Revision 3, from `work_order.verify.md` F1). Added WKO-NN-27 (strict xfail BUG-2676: `WO-2031-005` beside `WO-2031-1_000` → `WO-2031-006`) as a fifth param id of the BUG-2676 parametrized test, after NN-26; that test's comment and docstring name it. Other tests unchanged. `ref_wo.py` already reads suffixes as a `[0-9]+` full match (a comment now says so); no logic change. Re-run: 3 plain runs 167 passed / 22 xfailed each; `--runxfail` 22 failed, NN-27 on Then 2 (`'WO-2031-1001' == 'WO-2031-006'`); reference plugin with `--runxfail` 189 / 189; coverage 95% (only `restore`, dead); ruff check and format clean; LF.
