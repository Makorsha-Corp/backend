# Spec — `app/services/notification_stream.py`

> **Status:** APPROVED (2026-11-04; P1, Q1, Q2 decided by Claude under the reviewer's delegation (2026-11-04); nothing open)
> **Source commit:** e48a092
> **Revision 2026-11-04 (fill-gaps, `notification_stream.cases.md` gaps 1–2):** the autocommit call is named (R2, Facts); BUG-1804's clock and patch target are fixed (R5, R5a, Externals, Notes) — decided by Claude under the reviewer's delegation (2026-11-04). No new question; stays APPROVED. See `## Gap log`.

> **Form.** As `tests/unit/services/department_service.spec.md`. One generator, no manager, no `BaseService`, no SQLAlchemy session: it opens its **own** raw `psycopg2` connection, `LISTEN`s on the channel `user_notifications`, and turns Postgres notifications into Server-Sent-Events text. The sender is the notification DAO's `create` (`tests/unit/dao/notification.spec.md`, APPROVED): after each new notification it runs `pg_notify('user_notifications', '{"recipient_user_id": …, "workspace_id": …, "notification_id": …}')`, delivered only when that transaction commits.
>
> **Unit tests use fakes, not the database.** A test patches the module's two collaborators and nothing else: the name **`psycopg2`** in `app.services.notification_stream` (so `psycopg2.connect` returns a fake connection) and the name **`select`** in the same module (so `select.select` returns "ready" or "timeout" as scripted). Patch the module's names, never `psycopg2.connect` on the real `psycopg2` package or the real `select.select`: the test database engine uses the real ones. Real `LISTEN`/`NOTIFY` delivery needs a committed `NOTIFY` and is integration-only.
>
> **Verified by running** (`v2_stream.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc4d\`, fakes only, no database): nothing connects before the first `next()`; the connected frame; `LISTEN user_notifications;`; isolation level `0` (autocommit); `select` on `[conn]` with timeout `30`; the ping frame on a timeout; no frame when the connection is ready but no notification arrives; a matching notification's frame; malformed JSON, another workspace and a string `"1"` user id skipped; a missing `notification_id` sent as `null`; JSON `1.0` and `true` both equal user `1`; a JSON list ends the stream with `AttributeError` (P1); cursor and connection closed on `close()` after the first frame and when `select` raises; a failing `LISTEN` leaves the connection open (Q1). **Not run:** real Postgres delivery; the intended behavior of BUG-1802 … BUG-1804.

## Review
> All answered; nothing pending.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | A notification message that is valid JSON but not an object ends every open stream | bug (BUG-1802) | Claude, delegated (precedent BUG-581) |
| Q1 | If listening fails right after connecting, the database connection is never closed | bug (BUG-1803) | Claude, delegated |
| Q2 | A quiet user gets no keep-alive while other people's notifications keep arriving | bug (BUG-1804) | Claude, delegated |

Checked and **not** violated: **HR-16** — a frame is sent only for a message naming this user **and** this workspace; the frame carries only the notification id. **HR-14** — a malformed message is skipped (except P1). **HR-1 … HR-13, HR-15** — no names, lists, money or audit.

**Permission checks:** none here. The endpoint `GET /me/notifications/stream` passes the caller's own profile id and the current workspace, both from the auth dependencies (membership checked there, integration-only). The generator never re-checks membership while the stream stays open.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation (2026-11-04))

### P1. A message that is JSON but not an object ends the stream — 🐞 BUG-1802
**Background:** Every open stream listens on one platform-wide channel and reads each message as JSON. Text that is not JSON is skipped. BUG-581 ruled that valid JSON of the wrong shape (`[1]`, `null`, `5`) is rejected like any malformed input, never a crash.
**What happens today:** a message `[1, 2]` (or `5`, `"x"`, `null`) raises `AttributeError` inside the generator; the stream ends and its connection is closed (verified). Because the channel is shared, one such message ends **every** open stream on the platform at once.
**Example:** someone with database access runs `NOTIFY user_notifications, '[]'`; every logged-in browser's notification stream drops and reconnects; a notification created during the reconnect gap is not pushed.
**Rules affected:** R6
**Answer:** bug — per BUG-581 precedent: a message that is not a JSON object is skipped like malformed JSON; the stream goes on
**Resolution:** 🐞 BUG-1802 (pattern `validator-raises-on-malformed-input`) — decided by Claude under the reviewer's delegation (2026-11-04). Rules: R6.

### New questions

### Q1. A failure while starting to listen leaves the connection open — 🐞 BUG-1803
**Background:** The generator opens its own Postgres connection, switches it to autocommit, opens a cursor and runs `LISTEN`; only after that does the cleanup (`finally`: close cursor, close connection) start to apply.
**What happens today:** if switching the isolation level, opening the cursor or `LISTEN` raises, the error reaches the caller and the connection stays open until garbage collection (verified: `close` not called).
**Example:** the database is briefly restarting; a browser retries the stream every few seconds; each failed attempt leaves one more server connection open until Python collects it, and the server can run out of connection slots.
**Rules affected:** R2a
**Suggested answer:** `bug — any failure after the connection is opened closes it (and the cursor, if opened) before the error reaches the caller.`
**Answer:** as suggested — decided by Claude under the reviewer's delegation (2026-11-04).
**Resolution:** 🐞 BUG-1803 (pattern `resource-leak-on-setup-error`). Rules: R2a.

### Q2. The keep-alive ping depends on the whole platform being quiet — 🐞 BUG-1804
**Background:** The stream sends `: ping` only when **no message at all** arrived on the channel for 30 seconds. The channel carries every workspace's notifications; messages for other people are dropped silently, and they restart the 30 seconds.
**What happens today:** while other people's notifications arrive at least every 30 seconds, this user's stream sends nothing at all (verified: ready-but-no-match yields no frame).
**Example:** on a busy afternoon messages arrive every 10 seconds for others; Ann has none for 5 minutes; the proxy in front of the API closes her idle connection after 60 seconds; her browser reconnects, and a notification created in that gap is not pushed to her.
**Rules affected:** R5
**Suggested answer:** `bug — a ping is sent whenever 30 seconds pass without any frame sent to this client, whatever arrives for others.` *(requires a clock in the module; tests patch it.)*
**Answer:** as suggested — decided by Claude under the reviewer's delegation (2026-11-04).
**Resolution:** 🐞 BUG-1804 (pattern `keepalive-starved-by-foreign-traffic`). Rules: R5.

## Overview
`notification_event_generator(user_id, workspace_id)` is the body of `GET /me/notifications/stream` (`StreamingResponse`, `text/event-stream`). It tells the browser "something new for you" by pushing the id of each new notification addressed to this user in this workspace; the browser then fetches the notification through the normal API. It protects one invariant: a client is told only about its own notifications in its current workspace.

**Callables:** 1 specified · 0 not specified
**Externals to mock:** `psycopg2` (module name `app.services.notification_stream.psycopg2`; its `connect`) and `select` (module name `app.services.notification_stream.select`; its `select`). For BUG-1804 also the module's clock: the module name **`time`** (`app.services.notification_stream.time`; its `monotonic`) — patch the module's name, never the real `time.monotonic`. Today the module has no `time` name, so the patch needs `create=True` (see Notes). No database, no `db` fixture.
**Integration-only behavior:** real `LISTEN`/`NOTIFY` delivery after a commit; the HTTP headers and media type of the endpoint; a client disconnect closing the generator (Starlette); one OS thread and one database connection held per open stream.

**Facts for the test designer**
- Import: `from app.services import notification_stream as ns`; call `ns.notification_event_generator(user_id, workspace_id)`; both positional ints. It is a plain (sync) generator.
- Constants: channel `ns.NOTIFICATION_CHANNEL == "user_notifications"`; the connect argument is `ns.settings.DATABASE_URL`; the autocommit level is `psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT` (`0`), imported into the module by name (not affected by patching `ns.psycopg2`). "Sets it to autocommit" is exactly one call on the connection: `conn.set_isolation_level(0)` (positional, the constant `ISOLATION_LEVEL_AUTOCOMMIT`); no `conn.autocommit = True` and no other isolation call.
- Exact frames: connected `"event: connected\ndata: {}\n\n"`; ping `": ping\n\n"`; notification `"event: notification\ndata: {\"notification_id\": <id>}\n\n"` with `json.dumps` spacing (`{"notification_id": 7}`, `{"notification_id": null}`).

**Notes for the test designer**
- **Fake connection:** a `MagicMock` with `notifies = []` (a real list) and `poll.side_effect` that appends objects with a `.payload` string (e.g. `types.SimpleNamespace(payload=json.dumps({...}))`) to `notifies`. `cursor()` returns a `MagicMock` cursor.
- **Scripting `select`:** `fake_select.select.side_effect = [([conn], [], []), ([], [], []), …, OSError("stop")]` — `([conn],…)` = ready, `([],…)` = timeout. End a scripted run with an exception or with `gen.close()`; never iterate past the script (the loop is endless).
- **Disconnect:** `gen.close()` after any frame runs the cleanup (GeneratorExit at the `yield`).
- **Clock (BUG-1804, R5/R5a):** `patch.object(ns, "time", create=True)` with a `MagicMock` whose `monotonic.side_effect` scripts the readings, active from the generator's creation through the When. `create=True` is required today (no `time` name in the module) and harmless after the fix. Script readings that are each **at least 30 s** after the previous one (e.g. `itertools.count(0, 31)`) to mean "30 s passed every round"; script a constant (e.g. `itertools.repeat(0)`) to mean "no time passed". Never assert how many times the clock is read. **Every card whose expected frames contain a ping patches the clock**; a card expecting no ping may leave the real clock (a test run lasts far less than 30 s) — this rule includes the timeout card (G-10, "each timeout yields one ping"), which takes the 31-s-per-reading patch; it then passes today (the patch is unused) and after the fix.

## Not specified
- nothing.

---

## `notification_event_generator(user_id, workspace_id)`
**Shape:** event stream · **Persistence:** reads (own connection, no session) · **Visibility:** public (used by: `GET /me/notifications/stream`, with the caller's profile id and current workspace id)

**Purpose:** Push a frame to the browser for each new notification of this user in this workspace, and keep the connection alive.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `user_id` | int | the recipient to match; not checked |
| `workspace_id` | int | the workspace to match; not checked |

**Returns:** an iterator of `str` frames; endless until closed or until an error.

**Rules:**
- **R1.** Calling the function does nothing: no connection is opened until the first `next()`. A generator closed before its first `next()` never connects.
- **R2.** The first `next()` opens one connection with `settings.DATABASE_URL`, sets it to autocommit (exactly one `conn.set_isolation_level(0)`, Facts), opens a cursor, runs exactly `LISTEN user_notifications;` and yields the connected frame. A failure of `connect` reaches the caller unchanged (nothing to close).
- **R2a.** [BUG-1803] (Q1) If setting autocommit, opening the cursor or `LISTEN` raises, the cursor (if opened) and the connection are closed, then the error reaches the caller unchanged. *(Today: the error reaches the caller and the connection is not closed. Verified.)*
- **R3.** After the connected frame, each round waits on the connection with `select` and a timeout of 30 seconds.
- **R4.** When the connection is ready, the connection is polled and every queued message is handled, oldest first, before the next wait. A ready round with no message yields nothing.
- **R5.** [BUG-1804] (Q2) Whenever 30 seconds pass without any frame yielded to this client, the ping frame is yielded, whether or not messages for other people arrived meanwhile. A round where `select` times out with nothing sent for 30 seconds yields exactly one ping and waits again. *(Today: a ping is yielded only when `select` times out, i.e. when no message at all arrived for 30 seconds; messages for others postpone it indefinitely. Verified.)* *(requires a clock in the module; tests patch it.)*
- **R5a.** [BUG-1804] (Q2; gap G2, decided by Claude under the reviewer's delegation (2026-11-04)) How the 30 seconds are measured: the clock is `time.monotonic()` read through the module-level name `time` (`import time` in `app/services/notification_stream.py`; tests patch `ns.time`). Any frame yielded to this client — connected, notification or ping — restarts the 30 seconds. After **every** round (a `select` timeout or a ready round, once its messages are handled), if the clock shows 30 s or more since the last frame, exactly one ping is yielded; never more than one ping per round. A `select` timeout by itself is **not** the trigger: a timeout round while the clock shows less than 30 s since the last frame yields nothing. The `select` timeout stays 30 s (R3 unchanged), so the longest gap without a frame stays under 60 s. *(Today: no clock; a timeout round always pings, a ready round never does.)*
- **R6.** A message whose text is not valid JSON is skipped. [BUG-1802] (P1) A message that is valid JSON but not an object (`[1, 2]`, `5`, `"x"`, `null`) is skipped too, and the stream goes on with the next message. *(Today: `AttributeError`; the stream ends and closes. Verified.)*
- **R7.** A message yields a notification frame only when its `recipient_user_id` equals `user_id` **and** its `workspace_id` equals `workspace_id`, by Python equality: a missing key, another user, another workspace, or a string `"1"` never match; JSON `1.0` and `true` equal `1` (the only sender writes ints).
- **R8.** The notification frame carries only `notification_id` from the message; a missing `notification_id` gives `null`. Nothing else of the message is sent.
- **R9.** Several matching messages in one round yield one frame each, in arrival order; non-matching ones in between are skipped.
- **R10.** Whenever the generator stops after R2 succeeded — `close()` by the client, an exception from `select` or `poll`, or (today) P1 — the cursor and then the connection are closed exactly once; the exception, if any, reaches the caller unchanged.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `connect` fails | its exception, unchanged | — |
| setup after connect fails | its exception, unchanged (connection closed: BUG-1803) | — |
| `select` / `poll` fails | its exception, unchanged; cleaned up (R10) | — |

**Side effects:** one Postgres connection per stream, `LISTEN` on it; closed on exit. Writes nothing.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 16 (generator) | body runs only on first `next()` | R1 |
| 17 | `connect` | R2 |
| 18–20 | autocommit, cursor, `LISTEN` — outside `try` (BUG-1803) | R2, R2a |
| 23 | connected frame | R2 |
| 25–26 | endless loop; `select` 30 s | R3 |
| 27–29 | not ready → ping (BUG-1804; intended trigger is the clock) | R5, R5a |
| 31–32 | poll; drain queue; empty → nothing | R4, R9 |
| 34–37 | JSON error → skip; non-object → crash (BUG-1802) | R6 |
| 39–42 | recipient and workspace match | R7 |
| 43–46 | frame with `notification_id` only | R8, R9 |
| 47–49 | `finally`: close cursor, connection | R10 |

## Gap log
- G1 (`notification_stream.cases.md` gap 1) — Fact — the autocommit step is exactly one `conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)` (= `0`, positional), source line 18; named in R2 and Facts. The designer's assumption (`conn.set_isolation_level`) is confirmed.
- G2 (`notification_stream.cases.md` gap 2) — Intent, decided by Claude under the reviewer's delegation (2026-11-04) (not money or order workflow) — new R5a: the clock is `time.monotonic()` through a module-level `import time`; patch target the module name `app.services.notification_stream.time` (`patch.object(ns, "time", create=True)`, its `monotonic`), never the real `time.monotonic`. Any yielded frame restarts the 30 s; the clock is checked after every round; at most one ping per round; a `select` timeout alone does not ping; `select` timeout stays 30 s. G-10 needs the clock patch too (31 s per reading); added to Externals and Notes. BUG-1804 row in `docs/testing/bugs.md` names the clock.

## Follow-ups for other reviews
> Nothing below is a rule of this module.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | Notification endpoint / deployment | Every open stream holds one worker thread and one database connection outside the pool, and receives every workspace's messages to filter them in Python. A capacity note for production (connection limit, thread pool), no rule. | reading |
| FU-2 | Notification endpoint | A member removed from the workspace keeps an open stream until it disconnects; it receives only ids of notifications addressed to them, which they can no longer fetch. No rule; noted for the access review. | reading |
