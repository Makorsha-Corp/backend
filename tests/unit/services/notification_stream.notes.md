# Execution notes — `app/services/notification_stream.py`

> Cases: `tests/unit/services/notification_stream.cases.md` (revision 3) · Tests: `tests/unit/services/test_notification_stream.py` · Source commit: e48a092
> Result: 26 passed · 9 xfailed · 0 open discrepancies (DISCREPANCY-1 closed by cases revision 3) · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_notification_stream.py -q -p no:cacheprovider`

## How the tests are built
- **No database.** The `db` fixture is not used. The fixture `fx` builds the Conventions fakes for every test (`fx.conn` with `notifies = []`, `fx.cur = conn.cursor.return_value`, `fx.fake_pg`, `fx.fake_sel`, `fx.READY`, `fx.TIMEOUT`, `fx.STOP`, one `OSError("stop")` per test). It patches `ns.psycopg2` and `ns.select` for the whole test (an `ExitStack`), so the patches cover the Given's generator creation and the When.
- **Patch targets:** only the module names `ns.psycopg2`, `ns.select` and, in the R5a cards, `ns.time` (`patch.object(ns, "time", create=True)`, entered by `fx.clock(r)` on the same stack). Nothing else is mocked.
- **Conventions → code:** `fx.script(...)` = script; `fx.polls(...)` = polls (the k-th `poll()` appends batch k, then nothing); `msg`, `raw`, `mine` as written; `collect(gen, T)` returns `(frames, exc)` with frames kept up to the exception; `fx.closes()` = closes; CLOCK31 = `clock31()` (`itertools.count(0, 31)`), CLOCK0 = `clock0()` (`itertools.repeat(0)`); stepped clock = `now = [0]` plus `fx.clock(lambda: now[0])`. Frames are written as the literal strings from the cards (no `frame()` helper hides an expected value).
- **No hangs:** every `select` script is a finite list that ends on STOP (an exhausted script would raise too, since `side_effect` is a list). Generators left suspended after `next()` (G-01, G-03, G-34, G-35) are closed in the test (`finally: gen.close()`), after the assertions.
- **xfail checks (`--runxfail`):** every strict xfail fails on the Then line its card names: G-06, G-07 Then 2 (`conn.close.call_count` 0 ≠ 1); G-08 Then 2 (`closes == []`); G-11 Then 2 (frames only the connected frame); G-16, G-17 Then 1 (`AttributeError` out of `collect(OSError)`: `'list'` / `'NoneType' object has no attribute 'get'`); G-31 Then 2 (an extra ping); G-33 Then 2 (no ping after the notification); G-34 Then 3 (`third` is the ping).
- **Reference fix plugin** (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc4e2\ns\ref_fix_plugin.py`, scratch only, never in app/): it execs a fixed `notification_event_generator` into `ns.__dict__` in-process, with each bug fix switched by `REF_FIX`. 1802 skips a non-dict payload; 1803 closes the cursor (if opened) and the connection when setup fails, then raises again; 1804 adds `import time` and pings at the end of any round once 30 s have passed since the last frame. Results with `--runxfail`: REF_FIX=1802 → G-16, G-17 pass (7 fail); 1803 → G-06…G-08 pass (6 fail); 1804 → G-11, G-31, G-33, G-34 pass (5 fail); all three → **35 passed**. Each fix flips exactly its own cards, so every line after each failure point runs and holds. No pass card breaks under any fix.
- **Stability:** 3 plain runs, each `26 passed, 9 xfailed`. ruff clean; file is LF.

## Discrepancies
None open. DISCREPANCY-1 below is **closed**: cases revision 3 (2026-11-04) changed the Conventions "closes" and NST-G-03 Then 6 to `conn.mock_calls`, which is what the tests already read.

| ID | Case | Designed | Actual | Evidence | Likely cause |
|---|---|---|---|---|---|
| DISCREPANCY-1 (closed) | Conventions "closes"; NST-G-03 Then 6 (used by G-08, G-26 … G-30) | `closes` and the call-order check read `conn.method_calls` | `MagicMock.method_calls` does not record calls made on a return value, so `conn.method_calls` never contains `cursor().execute` or `cursor().close`. Written literally, G-03, G-26 … G-30 failed for the source as it is today, which matches the spec (`['close'] != ['cursor().close', 'close']`). With all three reference fixes applied, G-08 could still never pass. | `MagicMock()`: after `c.cursor().close(); c.close()`, `method_calls` names are `['cursor', 'close']` and `mock_calls` names are `['cursor', 'cursor().close', 'close']` (checked by running it). | The case designer meant "the cursor's and the connection's close calls, in call order". The test reads `conn.mock_calls`, which records exactly those names. Expected values are unchanged and no test is marked. **Route to the designer:** change the Conventions "closes" and G-03 Then 6 to `conn.mock_calls`. |

## Coverage gaps
None — 100% branch coverage (33 statements, 6 branches).

## Factories added
None.

## Notes for maintainers
- When BUG-1803 is fixed, G-06 … G-08 XPASS: remove their markers. The same applies to G-16 and G-17 for BUG-1802, and to G-11, G-31, G-33 and G-34 for BUG-1804.
- G-10 and G-35 pass today without reading the clock. After the BUG-1804 fix they depend on the clock being read through `ns.time.monotonic`, as R5a says. A fix that imports `monotonic` by name would bypass the patch.
- The 1804 reference fix sets "last frame" time just before each yield. If it were set after the `yield` resumes, G-34 would read the stepped clock late and fail. A real fix should record the time at yield.
- New bugs: none (BUG-1850 … 1859 unused).

## Revision history
- **2026-11-04 — cases revision 3.** The designer accepted DISCREPANCY-1: "closes" and NST-G-03 Then 6 now read `conn.mock_calls`. The tests already did, so no test changed. The header, the test docstring (revision 3) and the comment above `Fakes.closes()` (DISCREPANCY-1 closed) were updated. Re-run: 26 passed, 9 xfailed; ruff clean; LF.
