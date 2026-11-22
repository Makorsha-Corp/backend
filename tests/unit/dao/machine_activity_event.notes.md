# Execution notes — `app/dao/machine_activity_event.py`

> Cases: `tests/unit/dao/machine_activity_event.cases.md` (revision 1, READY, 81 cases; spec APPROVED 2026-10-31) · Tests: `tests/unit/dao/test_machine_activity_event.py` · Source commit: e48a092
> Result: **81 tests for 81 cases — 79 passed · 2 xfail (1 strict, 1 non-strict) · 0 discrepancies · 0 errors** — line and branch coverage 100% (25 statements, 8 branches). The non-strict MAE-LM-14 may XPASS without turning the run red (see Stability), so a default run reads either `79 passed, 2 xfailed` or `79 passed, 1 xfailed, 1 xpassed`. Only MAE-LM-15, the strict card, must always xfail.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine_activity_event.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file (not kept; `scratchpad\maex\`), so values are the card's own text. The fixtures and helpers were written by hand. An AST pass checked: each ID exactly once and in card order, `# Then 1..N` matches the card's Then count in order with a check under each, marker and bug match the Expect line, no unused argument, no fixture used without being an argument.

## How the tests are built
- **Nothing is patched** (Conventions, Externals: None).
- **Constants:** `dao` (= `machine_activity_event_dao`, a module-level name), `MISSING = 999999999`, `T1`, `T2`, `T3`.
- **Standing rows:** one fixture per Conventions row (`w1`, `w2`, `u1`, `f1`, `fd`, `f9`, `m1`, `m2`, `md`, `mf`, `m9`); the autouse `standing_rows` makes all of them exist in every test. Each test lists only those it names. `w2` depends on `w1`, so ids rise in Conventions order.
- **Builders (keyword-only fixtures, flush before returning):** `mk_event(created_at=, **columns)` = "event"; `metadata_json` and `performed_by` stay out of the constructor unless the card gives them, so `metadata_json=None` (JSON `null`) differs from no keyword (SQL `NULL`), which MAE-GM-43 reads. `mk_status(created_at=, **columns)` = "status row". `mk_log(count)` = the E1 … E101 `add_all` Given of GM-14 and GM-15, returns `newest_first`.
- **Reading helpers (no expected values inside):** `ids`; `snap(db, row)` (every column, Core select, for "unchanged"; the check runs `db.expire_all()` first, as "re-read" says); `stored_count(db)` ("nothing written"; not called `written`, which is the card's name for the recorder's list); `stored_json(db, row)`.
- **Given rows no line names again** are built without a variable (F841). That also avoids the names `L` and `O` of GM-41.
- **Row letters** of the cards are lower case in the code (`A` → `a`, `P` → `p`).
- **Database-error cards** (GM-23, GM-24): `with pytest.raises(DataError) as exc:` around `with db.begin_nested():`; that block is Then 1.
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener on the session's connection, around the When only. `recorder.sql()` is the one SELECT naming `machine_activity_events` and fails loudly unless there is exactly one. `recorder.selects()`, `recorder.written()`, `order_part_of(sql)` are the Conventions' `selects`, `written`, `order_part`.
- **MAE-GM-30:** `SET LOCAL TIME ZONE` is the first Given line, inside the test's outer transaction, so it ends with the test's rollback.
- **xfail markers:** `reason` is `BUG-1090: <bug title>`; the non-strict one adds why it cannot be strict.

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| MAE-LM-15 | yes | Then 2, every run on every plan | `assert 'ORDER BY' in 'SELECT machine_activity_events.id AS …'`: the statement has no `ORDER BY` anywhere. **It never XPASSED.** |
| MAE-LM-14 | no | Then 3, when it fails | `result[m1.id].id` is A's id, one below B's (`assert 106889 == 106890`; 111069 == 111070 with index and bitmap scans off). Then 1 and Then 2 hold. |

**Proof that the non-strict card can fail on its Then 3.** A scratch plugin (`scratchpad\maex\maex_order.py`, `-p maex_order`, a `before_cursor_execute` rewrite on the map's statement, nothing in `app/`) appended an explicit order. It rewrote all 17 statements of the file's calls to the map. An explicit order is a legal result for a query that asks for none, and it depends on neither plan nor heap.

| Explicit order | LM-14 | Whole file |
|---|---|---|
| `ORDER BY machine_activity_events.id DESC` (the wrong one: the dict keeps the lowest id) | **fails on Then 3**, `assert 110716 == 110717` | 79 passed, 2 xfailed |
| `ORDER BY machine_activity_events.id` (the dict keeps the highest id) | passes all four Then lines | 79 passed, 1 xfailed, 1 XPASS (LM-14) |

So no pass card depends on the order of the map's rows, MAE-LM-13 included. The recorder saw the original text in these runs (the rewrite comes after its listener), so LM-15 stayed on Then 2 here.

**Proof of the later Then lines and of the alarm.** A second scratch plugin (`maex_fix.py`) replaced `get_latest_status_map` in-process with the same query plus `.order_by(created_at, id)`. With `--runxfail`: **81 passed**, so LM-15's Then 3 and LM-14's Then 4 hold on a fixed method. With the markers on: LM-15 is `XPASS(strict)`, the red run the card is there for, and LM-14 XPASS. `1 failed, 79 passed, 1 xpassed`.

## Discrepancies
None. No card was changed and no marker was loosened.

Prose only, no test affected: LM-14's `Fails today on` and the spec's "Today the map then returned the lower id" say the updated lower-id row "usually" wins. On the default plan that did not hold: it XPASSED in 7 of 12 default runs (revision 0: 5 of 8; revision 1: 2 of 4). With index and bitmap scans off it failed in every run. See Stability.

## Coverage gaps
None — 100% line and branch coverage of `app/dao/machine_activity_event.py` (25 statements, 8 branches, 0 missed). The inherited `BaseDAO` methods live in `app/dao/base.py` and are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
**What is stable:** in every run below all pass cards passed, LM-15 xfailed and nothing was red. **What is not:** whether LM-14 XPASSES. It follows the plan and the heap, and it changed between runs with no change to the file.

Revision 1 runs (81 cases):

| Run | Result | LM-14 |
|---|---|---|
| Default, runs 1 and 2 of 3 | 79 passed, 2 xfailed | xfailed |
| Default, run 3 and the coverage run | 79 passed, 1 xfailed, 1 XPASS | XPASS |
| `PGOPTIONS="-c enable_seqscan=off"` | 79 passed, 1 xfailed, 1 XPASS | XPASS |
| `PGOPTIONS="-c enable_seqscan=off -c enable_hashjoin=off -c enable_nestloop=off"` | 79 passed, 1 xfailed, 1 XPASS | XPASS |
| `PGOPTIONS="-c enable_hashjoin=off"` | 79 passed, 1 xfailed, 1 XPASS | XPASS |
| `PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off -c enable_indexonlyscan=off"` | 79 passed, 2 xfailed | xfailed |
| The line above + `-c enable_hashjoin=off -c enable_mergejoin=off` | 79 passed, 2 xfailed | xfailed |

Revision 0 runs (78 cases):

| Run | Result | LM-14 |
|---|---|---|
| Default: first run, run 1 of the 5, last run | 76 passed, 2 xfailed | xfailed |
| Default, runs 2–5 and the coverage run | 76 passed, 1 xfailed, 1 XPASS | XPASS |
| `PGOPTIONS="-c enable_seqscan=off"` | 76 passed, 1 xfailed, 1 XPASS | XPASS |
| `PGOPTIONS="-c enable_seqscan=off -c enable_hashjoin=off -c enable_nestloop=off"` | 76 passed, 1 xfailed, 1 XPASS | XPASS |
| `PGOPTIONS="-c enable_hashjoin=off"` | 76 passed, 1 xfailed, 1 XPASS | XPASS |
| `PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off -c enable_indexonlyscan=off"` | 76 passed, 2 xfailed | xfailed, also in 4 more `--runxfail` runs (Then 3 each) |
| The line above + `-c enable_hashjoin=off -c enable_mergejoin=off` | 76 passed, 2 xfailed | xfailed |

`PGOPTIONS` reaches the connection (`SHOW enable_seqscan` → `off`). `ruff check` on the file: all checks passed. Line endings: LF.

## Revision history
- **Revision 1 of the cases (`machine_activity_event.verify.md` Findings 1, 2):** added MAE-GM-45, GM-46 and LS-16, all `pass`, each after the last card of its section. A diff against the delivered file shows additions only: no existing test, helper or marker changed.
- **The three cards close the verifier's five survivors.** Rebuilt from their definitions in a scratch plugin of this stage (`scratchpad\maex\maex_variant.py`, an in-memory text edit of the source, nothing in `app/`; the verifier's own scripts were not run). 3 runs on each of three plans: default, `enable_seqscan=off`, index and bitmap scans off. The outcome was the same in all 3 runs of each plan, and the unedited control ended as designed.

| Variant | Default | Index only | Sequential only |
|---|---|---|---|
| `ls_r2_no_id` | LS-03, LS-16 | LS-03, LS-16 | LS-16 |
| `ls_r2_ctid_asc` | LS-16 | LS-16 | LS-16 |
| `gm_r13_contains_esc` | GM-45, GM-46 | GM-45, GM-46 | GM-45, GM-46 |
| `gm_r13_endswith_esc` | GM-45 | GM-45 | GM-45 |
| `gm_r13_startswith_esc` | GM-46 | GM-46 | GM-46 |

`ls_r2_no_id` on the sequential plan is the one LS-03 misses, as Finding 1 says, and LS-16 now fails it. No other card failed under any variant.

## Notes for maintainers
- When BUG-1090 is fixed with an `ORDER BY`, LM-15 XPASSES and turns the run red: remove both markers. A fix with no `ORDER BY` (a `max(id)` subquery, a Python tie-break) leaves LM-15 xfailing and no alarm sounds, so rewrite that card with the fix (cases file, Spec gap 3).
- Never read an LM-14 XPASS as the bug being gone: it passes on the default plan most of the time with the bug present. The proof is LM-15 and the explicit order above.
- `recorder.sql()` picks statements by the table name, so a second statement on `machine_activity_events` during a When fails the test at that line, not at a Then.
- "Nothing written" counts committed rows of all workspaces too. A run beside something that commits to this table could break it; nothing did here.
- The file carries `# ruff: noqa: SIM117, DTZ001`: the Conventions prescribe the nested `with` and naive datetimes.
