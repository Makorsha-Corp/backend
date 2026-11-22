# Test cases — `app/services/notification_stream.py`

> **Spec:** `tests/unit/services/notification_stream.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 3 (2026-11-04) — executor DISCREPANCY-1: `conn.method_calls` does not record calls through a return value (`cursor().execute`, `cursor().close`); **closes** (Conventions) and NST-G-03 Then 6 now read `conn.mock_calls`, same expected names. Affects NST-G-03, G-08, G-26 … G-30 as written; no expected value changed, no card added or retired.
> **Revision:** 2 (2026-11-04) — spec fill-gaps G1 (autocommit is exactly `conn.set_isolation_level(0)`, as G-03 already assumed) and G2 (new R5a: clock `time.monotonic()` through the module name `time`; any frame restarts the 30 s; at most one ping per round; a timeout alone is not the trigger). Changed: Conventions (**clock** patch, CLOCK31, CLOCK0, **stepped clock**; the BUG-1804 note replaced), NST-G-10 (takes the CLOCK31 patch; still pass), NST-G-11 (follows R5a: exactly one ping per ready round). New: NST-G-31 … G-35 (R5a). Gaps 1–2 closed. No card retired.
> **Counts:** 35 cases · 26 expected-to-pass · 9 expected-to-fail (bugs) · 0 deferred

## Reviewer summary
- **Per callable:** `notification_event_generator` 35 (9 bug): start-up R1, R2 4 · setup failure R2a 4 (3 bug) · wait and ping R3, R5, R5a 8 (4 bug) · queue R4, R9 4 · parse R6 3 (2 bug) · match R7 6 · frame R8 2 · cleanup R10 4.
- **Depth:** lighter target (skill step 1a) — no stock, money or order — but R7 is the module's isolation invariant (a client hears only of its own user **and** workspace), so each non-matching shape has its own card, with the other user and workspace on both sides of the number (6 and 8, 2 and 4) so a `<=` / `>=` comparison fails.
- **Expected-to-fail:** BUG-1803 3 (G-06 … G-08), BUG-1804 4 (G-11, G-31, G-33, G-34), BUG-1802 2 (G-16, G-17). All strict.
- **Notable design choices:**
  - Only the module names `ns.psycopg2` and `ns.select` are patched (spec). No database, no `db` fixture.
  - Every run ends on a scripted `select` error (STOP) or `gen.close()`; frames are collected up to that point, so the loop never runs past the script.
  - Pass cards end on STOP, not on a timeout, so no ping is expected outside the R5 / R5a cards. Every card whose expected frames contain a ping patches the clock (spec Notes); the others keep the real clock (a test lasts far less than 30 s).
  - R5a cards never assert how many times the clock is read: CLOCK31 means "30 s passed at every reading", CLOCK0 "no time passed". G-34 and G-35 step a clock cell between `next()` calls to put a timeout 25 s or 35 s after a notification frame.
  - Regression split for BUG-1803: "the setup error reaches the caller unchanged" holds today and after the fix → pass card G-05; the closes are the xfail cards.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `NST` = `app/services/notification_stream.py`. `G` = `notification_event_generator` (the only callable).

**Imports.** `from app.services import notification_stream as ns`; `json`, `itertools`, `types` (`SimpleNamespace`); `MagicMock`, `patch`, `call` (`unittest.mock`).

**Fakes (built in every test, no Given line).**
- `conn = MagicMock()`; `conn.notifies = []` (a real list). `cur = conn.cursor.return_value`.
- `fake_pg = MagicMock()`; `fake_pg.connect.return_value = conn`. `fake_sel = MagicMock()`.
- Active around the Given's generator creation **and** the When: `patch.object(ns, "psycopg2", fake_pg)` and `patch.object(ns, "select", fake_sel)`.
- READY = `([conn], [], [])`. TIMEOUT = `([], [], [])`. STOP = `OSError("stop")` (one instance per test).
- **script(a, b, …)** = `fake_sel.select.side_effect = [a, b, …]`.
- **polls(b1, b2, …)** = `conn.poll.side_effect` is a function that on its k-th call appends every message of batch `bk` to `conn.notifies` (a call with no batch left appends nothing). No `polls` line = `poll` appends nothing.
- **msg(d)** = `types.SimpleNamespace(payload=json.dumps(d))`. **raw(s)** = `types.SimpleNamespace(payload=s)`.
- **mine(n)** = `msg({"recipient_user_id": 7, "workspace_id": 3, "notification_id": n})`.
- `gen = ns.notification_event_generator(7, 3)` unless the card writes another call.

**Frames (exact strings).** CONNECTED = `"event: connected\ndata: {}\n\n"`. PING = `": ping\n\n"`. **frame(n)** = `"event: notification\ndata: " + json.dumps({"notification_id": n}) + "\n\n"`; e.g. `frame(7) == 'event: notification\ndata: {"notification_id": 7}\n\n'`, `frame(None)` ends in `{"notification_id": null}`.

**Named steps and checks.**
- **collect(T)** = `frames = []`, then `with pytest.raises(T) as exc:` around `for f in gen: frames.append(f)`. The When of a card that says "collect(T)".
- **closes** = `[c[0] for c in conn.mock_calls if c[0] in ("cursor().close", "close")]` — the cursor's and the connection's `close` calls, in call order.
- `mock called:` lines check the fakes after the When.
- `raises:` lines check `exc.value`; "is X" means the same object.

**Clock (BUG-1804, R5a).** **clock(r)** = `patch.object(ns, "time", create=True)` as `fake_time`, with `fake_time.monotonic.side_effect = r`, active from the generator's creation through the When (`create=True`: the module has no `time` name today). CLOCK31 = `itertools.count(0, 31)` (each reading 31 s after the one before). CLOCK0 = `itertools.repeat(0)` (no time passes). **stepped clock** = `now = [0]`, then clock(`lambda: now[0]`); the card sets `now[0]` between `next()` calls. A card with no clock line keeps the real clock. Never assert how many times the clock is read.

**xfail cards.** Strict: `pytest.mark.xfail(strict=True, reason="BUG-NNN")`. Write the call and checks as shown.

**Race simulations.** None.

## `notification_event_generator`

### NST-G-01 — calling the function opens nothing
- **Rules:** R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Fakes as Conventions; `gen` is not created in the Given.

**When**
- `gen = ns.notification_event_generator(7, 3)`.

**Then**
1. mock called: `fake_pg.connect.call_count == 0`.
2. mock called: `fake_sel.select.call_count == 0`.

### NST-G-02 — a generator closed before its first next() never connects
- **Rules:** R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `gen = ns.notification_event_generator(7, 3)`.

**When**
- `gen.close()`.

**Then**
1. mock called: `fake_pg.connect.call_count == 0`.
2. mock called: `conn.close.call_count == 0`.

### NST-G-03 — the first next() connects, sets autocommit, listens, and yields the connected frame
- **Rules:** R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. `gen = ns.notification_event_generator(7, 3)`.

**When**
- `first = next(gen)`.

**Then**
1. returns: `first == "event: connected\ndata: {}\n\n"`.
2. mock called: `fake_pg.connect.call_args == call(ns.settings.DATABASE_URL)`.
3. mock called: `fake_pg.connect.call_count == 1`.
4. mock called: `conn.set_isolation_level.call_args == call(0)`.
5. mock called: `cur.execute.call_args_list == [call("LISTEN user_notifications;")]`.
6. mock called: `[c[0] for c in conn.mock_calls][:3] == ["set_isolation_level", "cursor", "cursor().execute"]`.
7. mock called: `fake_sel.select.call_count == 0`.

### NST-G-04 — a failing connect reaches the caller unchanged
- **Rules:** R2; Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. `E = RuntimeError("down")`; `fake_pg.connect.side_effect = E`.
2. `gen = ns.notification_event_generator(7, 3)`.

**When**
- `next(gen)` inside `with pytest.raises(RuntimeError) as exc:`.

**Then**
1. raises: `exc.value is E`.
2. mock called: `fake_sel.select.call_count == 0`.

### NST-G-05 — a failing LISTEN reaches the caller unchanged
- **Rules:** R2a [BUG-1803] (part that holds today); Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. `E = RuntimeError("listen failed")`; `cur.execute.side_effect = E`.
2. `gen = ns.notification_event_generator(7, 3)`.

**When**
- `next(gen)` inside `with pytest.raises(RuntimeError) as exc:`.

**Then**
1. raises: `exc.value is E`.
2. mock called: `fake_sel.select.call_count == 0`.

### NST-G-06 — a failing autocommit switch closes the connection
- **Rules:** R2a [BUG-1803]; Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1803
- **Fails today on:** Then 2 (the connection is not closed)

**Given**
1. `E = RuntimeError("level failed")`; `conn.set_isolation_level.side_effect = E`.
2. `gen = ns.notification_event_generator(7, 3)`.

**When**
- `next(gen)` inside `with pytest.raises(RuntimeError) as exc:`.

**Then**
1. raises: `exc.value is E`.
2. mock called: `conn.close.call_count == 1`.

### NST-G-07 — a failing cursor() closes the connection
- **Rules:** R2a [BUG-1803]; Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1803
- **Fails today on:** Then 2 (the connection is not closed)

**Given**
1. `E = RuntimeError("cursor failed")`; `conn.cursor.side_effect = E`.
2. `gen = ns.notification_event_generator(7, 3)`.

**When**
- `next(gen)` inside `with pytest.raises(RuntimeError) as exc:`.

**Then**
1. raises: `exc.value is E`.
2. mock called: `conn.close.call_count == 1`.

### NST-G-08 — a failing LISTEN closes the cursor, then the connection
- **Rules:** R2a [BUG-1803]; Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1803
- **Fails today on:** Then 2 (nothing is closed)

**Given**
1. `E = RuntimeError("listen failed")`; `cur.execute.side_effect = E`.
2. `gen = ns.notification_event_generator(7, 3)`.

**When**
- `next(gen)` inside `with pytest.raises(RuntimeError) as exc:`.

**Then**
1. raises: `exc.value is E`.
2. mock called: `closes == ["cursor().close", "close"]`.

### NST-G-09 — each round waits on the connection with a 30-second timeout
- **Rules:** R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. script(READY, STOP).
2. `gen = ns.notification_event_generator(7, 3)`.

**When**
- collect(OSError).

**Then**
1. raises: `exc.value is STOP`.
2. returns: `frames == ["event: connected\ndata: {}\n\n"]`.
3. mock called: `fake_sel.select.call_count == 2`.
4. mock called: `fake_sel.select.call_args_list[0] == call([conn], [], [], 30)`.
5. mock called: `fake_sel.select.call_args_list[1] == call([conn], [], [], 30)`.

### NST-G-10 — each select timeout with 30 s passed yields exactly one ping and waits again
- **Rules:** R5, R5a
- **Kind:** happy
- **Expect:** pass
- **Author:** claude

**Given**
1. script(TIMEOUT, TIMEOUT, STOP).
2. clock(CLOCK31).
3. `gen = ns.notification_event_generator(7, 3)`.

**When**
- collect(OSError).

**Then**
1. raises: `exc.value is STOP`.
2. returns: `frames == ["event: connected\ndata: {}\n\n", ": ping\n\n", ": ping\n\n"]`.
3. mock called: `fake_sel.select.call_count == 3`.
4. mock called: `conn.poll.call_count == 0`.

### NST-G-11 — others' traffic does not starve the ping: one ping per ready round once 30 s have passed
- **Rules:** R5, R5a [BUG-1804]
- **Kind:** bug
- **Expect:** xfail BUG-1804
- **Author:** claude
- **Fails today on:** Then 2 (no ping: a ready round never pings today)

**Given**
1. `other = msg({"recipient_user_id": 8, "workspace_id": 3, "notification_id": 90})`.
2. script(READY, READY, READY, STOP).
3. polls([other], [other], [other]).
4. clock(CLOCK31).
5. `gen = ns.notification_event_generator(7, 3)`.

**When**
- collect(OSError).

**Then**
1. raises: `exc.value is STOP`.
2. returns: `frames == ["event: connected\ndata: {}\n\n", ": ping\n\n", ": ping\n\n", ": ping\n\n"]`.

### NST-G-12 — a ready round with no message yields nothing
- **Rules:** R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. script(READY, STOP).
2. `gen = ns.notification_event_generator(7, 3)`.

**When**
- collect(OSError).

**Then**
1. raises: `exc.value is STOP`.
2. returns: `frames == ["event: connected\ndata: {}\n\n"]`.
3. mock called: `conn.poll.call_count == 1`.

### NST-G-13 — queued messages are handled oldest first, before the next wait
- **Rules:** R4, R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. script(READY, STOP).
2. polls([mine(9), mine(4)]).
3. `gen = ns.notification_event_generator(7, 3)`.

**When**
- collect(OSError).

**Then**
1. raises: `exc.value is STOP`.
2. returns: `frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 9}\n\n', 'event: notification\ndata: {"notification_id": 4}\n\n']`.
3. mock called: `fake_sel.select.call_count == 2`.

### NST-G-14 — a handled message is not sent again in the next round
- **Rules:** R4, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. script(READY, READY, STOP).
2. polls([mine(1)], [mine(2)]).
3. `gen = ns.notification_event_generator(7, 3)`.

**When**
- collect(OSError).

**Then**
1. raises: `exc.value is STOP`.
2. returns: `frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 1}\n\n', 'event: notification\ndata: {"notification_id": 2}\n\n']`.
3. mock called: `conn.poll.call_count == 2`.

### NST-G-15 — a message that is not JSON is skipped and the stream goes on
- **Rules:** R6
- **Kind:** error
- **Expect:** pass

**Given**
1. script(READY, STOP).
2. polls([raw("not json {"), mine(8)]).
3. `gen = ns.notification_event_generator(7, 3)`.

**When**
- collect(OSError).

**Then**
1. raises: `exc.value is STOP`.
2. returns: `frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 8}\n\n']`.

### NST-G-16 — a JSON list is skipped and the stream goes on
- **Rules:** R6 [BUG-1802]
- **Kind:** bug
- **Expect:** xfail BUG-1802
- **Fails today on:** Then 1 (the call raises AttributeError: a list has no `.get`, the stream ends)

**Given**
1. script(READY, STOP).
2. polls([raw("[1, 2]"), mine(8)]).
3. `gen = ns.notification_event_generator(7, 3)`.

**When**
- collect(OSError).

**Then**
1. raises: `exc.value is STOP`.
2. returns: `frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 8}\n\n']`.

### NST-G-17 — a JSON null is skipped and the stream goes on
- **Rules:** R6 [BUG-1802]
- **Kind:** bug
- **Expect:** xfail BUG-1802
- **Fails today on:** Then 1 (the call raises AttributeError: `None` has no `.get`, the stream ends)

**Given**
1. script(READY, STOP).
2. polls([raw("null"), mine(8)]).
3. `gen = ns.notification_event_generator(7, 3)`.

**When**
- collect(OSError).

**Then**
1. raises: `exc.value is STOP`.
2. returns: `frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 8}\n\n']`.

### NST-G-18 — another user's message is skipped, on both sides of the user id
- **Rules:** R7, R9
- **Kind:** isolation
- **Expect:** pass

**Given**
1. script(READY, STOP).
2. polls([msg({"recipient_user_id": 6, "workspace_id": 3, "notification_id": 61}), mine(5), msg({"recipient_user_id": 8, "workspace_id": 3, "notification_id": 81})]).
3. `gen = ns.notification_event_generator(7, 3)`.

**When**
- collect(OSError).

**Then**
1. raises: `exc.value is STOP`.
2. returns: `frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 5}\n\n']`.

### NST-G-19 — another workspace's message for the same user is skipped, on both sides of the workspace id
- **Rules:** R7, R9
- **Kind:** isolation
- **Expect:** pass

**Given**
1. script(READY, STOP).
2. polls([msg({"recipient_user_id": 7, "workspace_id": 2, "notification_id": 21}), mine(5), msg({"recipient_user_id": 7, "workspace_id": 4, "notification_id": 41})]).
3. `gen = ns.notification_event_generator(7, 3)`.

**When**
- collect(OSError).

**Then**
1. raises: `exc.value is STOP`.
2. returns: `frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 5}\n\n']`.

### NST-G-20 — user and workspace swapped do not match
- **Rules:** R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. script(READY, STOP).
2. polls([msg({"recipient_user_id": 3, "workspace_id": 7, "notification_id": 37}), mine(5)]).
3. `gen = ns.notification_event_generator(7, 3)`.

**When**
- collect(OSError).

**Then**
1. raises: `exc.value is STOP`.
2. returns: `frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 5}\n\n']`.

### NST-G-21 — a message missing the user or the workspace key is skipped
- **Rules:** R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. script(READY, STOP).
2. polls([msg({"workspace_id": 3, "notification_id": 31}), msg({"recipient_user_id": 7, "notification_id": 71}), mine(5)]).
3. `gen = ns.notification_event_generator(7, 3)`.

**When**
- collect(OSError).

**Then**
1. raises: `exc.value is STOP`.
2. returns: `frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 5}\n\n']`.

### NST-G-22 — ids sent as strings never match
- **Rules:** R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. script(READY, STOP).
2. polls([msg({"recipient_user_id": "7", "workspace_id": 3, "notification_id": 11}), msg({"recipient_user_id": 7, "workspace_id": "3", "notification_id": 12}), mine(5)]).
3. `gen = ns.notification_event_generator(7, 3)`.

**When**
- collect(OSError).

**Then**
1. raises: `exc.value is STOP`.
2. returns: `frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 5}\n\n']`.

### NST-G-23 — JSON 1.0 and true equal the user id 1 (Python equality)
- **Rules:** R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. script(READY, STOP).
2. polls([msg({"recipient_user_id": 1.0, "workspace_id": 3, "notification_id": 14}), msg({"recipient_user_id": True, "workspace_id": 3.0, "notification_id": 15})]).
3. `gen = ns.notification_event_generator(1, 3)`.

**When**
- collect(OSError).

**Then**
1. raises: `exc.value is STOP`.
2. returns: `frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 14}\n\n', 'event: notification\ndata: {"notification_id": 15}\n\n']`.

### NST-G-24 — the frame carries only notification_id
- **Rules:** R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. script(READY, STOP).
2. polls([msg({"recipient_user_id": 7, "workspace_id": 3, "notification_id": 12, "title": "Payroll", "entity_id": 99})]).
3. `gen = ns.notification_event_generator(7, 3)`.

**When**
- collect(OSError).

**Then**
1. raises: `exc.value is STOP`.
2. returns: `frames[1] == 'event: notification\ndata: {"notification_id": 12}\n\n'`.
3. returns: `len(frames) == 2`.

### NST-G-25 — a missing notification_id is sent as null
- **Rules:** R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. script(READY, STOP).
2. polls([msg({"recipient_user_id": 7, "workspace_id": 3})]).
3. `gen = ns.notification_event_generator(7, 3)`.

**When**
- collect(OSError).

**Then**
1. raises: `exc.value is STOP`.
2. returns: `frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": null}\n\n']`.

### NST-G-26 — close() right after the connected frame closes the cursor, then the connection, once each
- **Rules:** R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `gen = ns.notification_event_generator(7, 3)`.
2. `first = next(gen)`.

**When**
- `gen.close()`.

**Then**
1. returns: `first == "event: connected\ndata: {}\n\n"`.
2. mock called: `closes == ["cursor().close", "close"]`.
3. mock called: `fake_sel.select.call_count == 0`.

### NST-G-27 — close() after a notification frame closes the cursor, then the connection, once each
- **Rules:** R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. script(READY, STOP).
2. polls([mine(1), mine(2)]).
3. `gen = ns.notification_event_generator(7, 3)`.
4. `first = next(gen)`; `second = next(gen)`.

**When**
- `gen.close()`.

**Then**
1. returns: `second == 'event: notification\ndata: {"notification_id": 1}\n\n'`.
2. mock called: `closes == ["cursor().close", "close"]`.
3. mock called: `fake_sel.select.call_count == 1`.

### NST-G-28 — a failing select ends the stream with its exception, cleaned up once
- **Rules:** R10; Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. script(STOP).
2. `gen = ns.notification_event_generator(7, 3)`.

**When**
- collect(OSError).

**Then**
1. raises: `exc.value is STOP`.
2. returns: `frames == ["event: connected\ndata: {}\n\n"]`.
3. mock called: `closes == ["cursor().close", "close"]`.

### NST-G-29 — a failing poll ends the stream with its exception, cleaned up once
- **Rules:** R10; Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. script(READY, STOP).
2. `E = RuntimeError("poll failed")`; `conn.poll.side_effect = E`.
3. `gen = ns.notification_event_generator(7, 3)`.

**When**
- collect(RuntimeError).

**Then**
1. raises: `exc.value is E`.
2. returns: `frames == ["event: connected\ndata: {}\n\n"]`.
3. mock called: `closes == ["cursor().close", "close"]`.
4. mock called: `fake_sel.select.call_count == 1`.

### NST-G-30 — after a cleanup, closing the generator again closes nothing more
- **Rules:** R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. script(STOP).
2. `gen = ns.notification_event_generator(7, 3)`.
3. collect(OSError) (the stream has ended on STOP).

**When**
- `gen.close()`.

**Then**
1. mock called: `closes == ["cursor().close", "close"]`.

### NST-G-31 — a timeout round with less than 30 s since the last frame yields nothing
- **Rules:** R5a [BUG-1804]
- **Kind:** bug
- **Expect:** xfail BUG-1804
- **Author:** claude
- **Fails today on:** Then 2 (today every timeout yields a ping)

**Given**
1. script(TIMEOUT, STOP).
2. clock(CLOCK0).
3. `gen = ns.notification_event_generator(7, 3)`.

**When**
- collect(OSError).

**Then**
1. raises: `exc.value is STOP`.
2. returns: `frames == ["event: connected\ndata: {}\n\n"]`.

### NST-G-32 — a ready round with a notification and no time passed adds no ping
- **Rules:** R5a, R4
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. script(READY, STOP).
2. polls([mine(5)]).
3. clock(CLOCK0).
4. `gen = ns.notification_event_generator(7, 3)`.

**When**
- collect(OSError).

**Then**
1. raises: `exc.value is STOP`.
2. returns: `frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 5}\n\n']`.

### NST-G-33 — a ready round ending 30 s or more after the last frame yields one ping after its notifications
- **Rules:** R5a [BUG-1804]
- **Kind:** bug
- **Expect:** xfail BUG-1804
- **Author:** claude
- **Fails today on:** Then 2 (no ping: a ready round never pings today)

**Given**
1. script(READY, STOP).
2. polls([mine(5)]).
3. clock(CLOCK31).
4. `gen = ns.notification_event_generator(7, 3)`.

**When**
- collect(OSError).

**Then**
1. raises: `exc.value is STOP`.
2. returns: `frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 5}\n\n', ": ping\n\n"]`.

### NST-G-34 — a notification frame restarts the 30 s: a timeout 25 s later yields nothing
- **Rules:** R5a [BUG-1804]
- **Kind:** bug
- **Expect:** xfail BUG-1804
- **Author:** claude
- **Fails today on:** Then 3 (the timeout round yields a ping, so `third` is the ping)

**Given**
1. script(READY, TIMEOUT, READY, STOP).
2. polls([mine(5)], [mine(6)]).
3. stepped clock.
4. `gen = ns.notification_event_generator(7, 3)`.
5. `first = next(gen)` (with `now[0] == 0`).
6. `now[0] = 20`; `second = next(gen)`.
7. `now[0] = 45`.

**When**
- `third = next(gen)`.

**Then**
1. returns: `first == "event: connected\ndata: {}\n\n"`.
2. returns: `second == 'event: notification\ndata: {"notification_id": 5}\n\n'`.
3. returns: `third == 'event: notification\ndata: {"notification_id": 6}\n\n'`.

### NST-G-35 — a timeout 35 s after the last notification frame yields one ping
- **Rules:** R5, R5a
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. script(READY, TIMEOUT, READY, STOP).
2. polls([mine(5)], [mine(6)]).
3. stepped clock.
4. `gen = ns.notification_event_generator(7, 3)`.
5. `first = next(gen)` (with `now[0] == 0`).
6. `now[0] = 20`; `second = next(gen)`.
7. `now[0] = 55`.

**When**
- `third = next(gen)`.

**Then**
1. returns: `second == 'event: notification\ndata: {"notification_id": 5}\n\n'`.
2. returns: `third == ": ping\n\n"`.

## Deferred to other specs
None. (Real `LISTEN`/`NOTIFY` delivery, HTTP headers and a client disconnect are integration-only per the spec.)

## Spec gaps
None. Revision 1's gaps are closed by the spec's Gap log (2026-11-04): G1 — autocommit is exactly `conn.set_isolation_level(0)` (R2, Facts); G2 — the clock is `time.monotonic()` through the module name `time`, patched with `patch.object(ns, "time", create=True)` (R5a, Notes).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `notification_event_generator` | R1 | NST-G-01, NST-G-02 |
| `notification_event_generator` | R2 | NST-G-03, NST-G-04 |
| `notification_event_generator` | R2a [BUG-1803] | NST-G-05 (pass part), NST-G-06, NST-G-07, NST-G-08 |
| `notification_event_generator` | R3 | NST-G-09, NST-G-10 |
| `notification_event_generator` | R4 | NST-G-12, NST-G-13, NST-G-14 |
| `notification_event_generator` | R5 (today) | NST-G-10 |
| `notification_event_generator` | R5 [BUG-1804] | NST-G-11, NST-G-35 |
| `notification_event_generator` | R5a [BUG-1804] | NST-G-10, NST-G-32, NST-G-35 (pass); NST-G-11, NST-G-31, NST-G-33, NST-G-34 (xfail) |
| `notification_event_generator` | R6 | NST-G-15 |
| `notification_event_generator` | R6 [BUG-1802] | NST-G-16, NST-G-17 |
| `notification_event_generator` | R7 | NST-G-18, NST-G-19, NST-G-20, NST-G-21, NST-G-22, NST-G-23 |
| `notification_event_generator` | R8 | NST-G-24, NST-G-25 |
| `notification_event_generator` | R9 | NST-G-13, NST-G-14, NST-G-18, NST-G-19 |
| `notification_event_generator` | R10 | NST-G-26, NST-G-27, NST-G-28, NST-G-29, NST-G-30 |
| `notification_event_generator` | Errors row 1 (connect fails) | NST-G-04 |
| `notification_event_generator` | Errors row 2 (setup after connect fails) | NST-G-05, NST-G-06, NST-G-07, NST-G-08 |
| `notification_event_generator` | Errors row 3 (select / poll fails) | NST-G-28, NST-G-29 |
