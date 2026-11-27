# Execution notes — `app/dao/attachment_markup.py`

> Cases: `tests/unit/dao/attachment_markup.cases.md` (READY, 41 cases) · Tests: `tests/unit/dao/test_attachment_markup.py` · Source commit: e48a092
> Result: **41 tests for 41 cases — 39 passed · 2 xfailed · 0 discrepancies · 0 errors** — branch coverage 100% line and branch (24 statements, 4 branches). The non-strict AMK-GF-10 may XPASS without turning the run red (seen once in 20 repeats and under `enable_hashjoin=off` with `--runxfail`).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_attachment_markup.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment, written by hand from the cards. An audit script of my own (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\B\audit.py`) checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matching the card's Then count, the `[claude]` tag, marker and strictness matching the Expect line, every quoted literal of the card present, no unused argument. LF only.

## How the tests are built
- **Nothing is patched.** `updated_at` comes from the database.
- **Constants:** `dao`, `MISSING`.
- **Standing rows:** `w1`, `w2`, `u1`, `u2`, `u3`, `at1`, `at2`, `atd`, `at9`, through the autouse `standing_rows`; each fixture depends on the one before, so ids rise in the Conventions' order. `atd` has no `deleted_at` (the Convention names none).
- **Builders / Given steps:** `mk_layer(**columns)` = "layer"; `hour_older(db, X)`, `bump(db, X)`, `seqscan(db)` run the Conventions' SQL verbatim.
- **Reading helpers (no expected values inside):** `ids`, `reread` (expire, then SELECT by id), `now_db`, `snap` (every column by a Core select, for "unchanged"), `stored_json`, `layers`, `stored_count` (markups and markup events, all workspaces: "nothing written"), `events_of`.
- **Statement recorder:** `StatementRecorder(db)` (a `before_cursor_execute` listener) around the When only; `recorder.sql()` is the one SELECT `FROM attachment_markups`; `order_part_of` is the text after the first `ORDER BY` (no LIMIT cut, as the Convention says).
- **Database-error cards:** `with pytest.raises(...)` around `with db.begin_nested():`; that block is Then 1.
- **rolled back:** `sp = db.begin_nested()`, then `patch.object(db, "commit", wraps=db.commit)` around the When; inside checks, `sp.rollback()`, after checks, then the spy's `call_count == 0`.
- "unchanged" snapshots are taken after the last Given line, before the When.

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| AMK-GF-10 | no | Then 2, default, UTC, Asia/Dhaka, `enable_seqscan=off`; passed once under `enable_hashjoin=off` | `assert [1301, 1302, 1300] == [1300, 1301, 1302]`: the bumped lowest id moves last, as the card says |
| AMK-GF-11 | yes | Then 3, every run | `assert '.id' in ' attachment_markups.updated_at ASC'` |

**Proof plugin** `attxb_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\B` (`PYTHONPATH` there, `-p attxb_plug`, `ATTXB_MODE=<mode>`), which replaces `get_for_attachment` in-process; nothing in `app/`.

| Mode | `get_for_attachment` order | `--runxfail` | Markers on |
|---|---|---|---|
| `fix` (intended) | `updated_at, id` | all 41 pass, so Then 4, 5 of GF-11 hold | GF-11 `XPASS(strict)`, GF-10 XPASS |
| `wrong1` | `updated_at, id DESC` | GF-10 Then 2 (`[272, 271, 270] == [270, 271, 272]`); GF-11 Then 5 | 39 passed, 2 xfailed |
| `wrong2` | `updated_at, user_id DESC` | GF-10 Then 2 (`[388, 387, 386]`); GF-11 Then 3 | 39 passed, 2 xfailed |
| `wrong3` | `updated_at, id DESC, user_id` | GF-10 Then 2 (`[504, 503, 502]`); GF-11 Then 5 | 39 passed, 2 xfailed |

So the non-strict card can fail on its Then 2 under an explicit wrong order, and no pass card depends on the order among ties.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Spec gaps of the cases file, checked
Neither gap names a guessed path or column. The models' module paths (`app.models.attachment_markup`, `app.models.attachment`) and every column the cards use exist as written.

## Coverage gaps
None — 100% line and branch coverage. Run with a private `COVERAGE_FILE`. Inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
5 default runs, 5 forced plans (`PGOPTIONS`: `enable_seqscan=off`; that plus hash join and nested loop off; `enable_hashjoin=off`; index, bitmap and index-only scans off; that plus hash and merge join off) and the database time zones `UTC` and `Asia/Dhaka` (default `America/New_York`): each `39 passed, 2 xfailed` (with the event file: `60 passed, 5 xfailed`). 20 repeats of every test in one process (`attxb_repeat.py`): nothing red, one GF-10 XPASS (non-strict). `AMK-UP-01` and `UP-07` compare with the transaction's `now()`, not a real clock. `ruff check`: all checks passed.

## Notes for maintainers
- When BUG-1435 is fixed, GF-11 turns the run red (`XPASS(strict)`): remove both markers.
- Never read a GF-10 XPASS as the bug being gone; GF-11 is the proof.
