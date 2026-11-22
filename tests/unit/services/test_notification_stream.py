"""Unit tests for app/services/notification_stream.py.

Implements tests/unit/services/notification_stream.cases.md (revision 3), one
test per case, in card order. No database and no `db` fixture: the generator
opens its own raw connection, so the tests patch only the module names the
Conventions list -- `ns.psycopg2`, `ns.select` and (R5a cards) `ns.time` with
`create=True` -- and nothing else.

No test can hang: `select` is always scripted with a finite list (a run ends on
the scripted STOP or the scripted error, and an exhausted script raises), and a
generator a test leaves suspended is closed at the end of the test.

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment; `# Then N` marks the checks of the card's Then line N.
"""
import itertools
import json
import types
from contextlib import ExitStack
from unittest.mock import MagicMock, call, patch

import pytest

from app.services import notification_stream as ns

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Frames (CONNECTED, PING, frame(n)) are written as the literal strings the
# cards give, so no helper hides an expected value.

BUG_1802 = "BUG-1802: A notification message that is JSON but not an object ends every open stream"
BUG_1803 = "BUG-1803: Notification stream leaves its database connection open when listening fails"
BUG_1804 = "BUG-1804: Keep-alive ping only when the whole platform is quiet"


# Convention "msg(d)"
def msg(d):
    return types.SimpleNamespace(payload=json.dumps(d))


# Convention "raw(s)"
def raw(s):
    return types.SimpleNamespace(payload=s)


# Convention "mine(n)"
def mine(n):
    return msg({"recipient_user_id": 7, "workspace_id": 3, "notification_id": n})


# --------------------------------------------------------------------------- #
# Conventions -> fakes (built in every test, active for the whole test, so
# around the Given's generator creation and the When)
# --------------------------------------------------------------------------- #

class Fakes:
    def __init__(self, stack):
        self._stack = stack
        self.conn = MagicMock()
        self.conn.notifies = []
        self.cur = self.conn.cursor.return_value
        self.fake_pg = MagicMock()
        self.fake_pg.connect.return_value = self.conn
        self.fake_sel = MagicMock()
        self.READY = ([self.conn], [], [])
        self.TIMEOUT = ([], [], [])
        self.STOP = OSError("stop")
        self.fake_time = None

    # Convention "script(a, b, ...)"
    def script(self, *steps):
        self.fake_sel.select.side_effect = list(steps)

    # Convention "polls(b1, b2, ...)"
    def polls(self, *batches):
        pending = list(batches)

        def _poll():
            if pending:
                self.conn.notifies.extend(pending.pop(0))

        self.conn.poll.side_effect = _poll

    # Convention "clock(r)": patch ns.time (create=True), monotonic scripted by r
    def clock(self, r):
        self.fake_time = self._stack.enter_context(patch.object(ns, "time", create=True))
        if callable(r):
            self.fake_time.monotonic.side_effect = r
        else:
            self.fake_time.monotonic.side_effect = lambda: next(r)
        return self.fake_time

    # Convention "closes": read from `conn.mock_calls`, which records calls on
    # `conn.cursor()`'s return value too. DISCREPANCY-1 (the card used to say
    # `conn.method_calls`) is closed: cases revision 3 writes `conn.mock_calls`.
    def closes(self):
        return [c[0] for c in self.conn.mock_calls if c[0] in ("cursor().close", "close")]

    # Call names on the connection, cursor calls included (`conn.mock_calls`, cases revision 3)
    def call_names(self):
        return [c[0] for c in self.conn.mock_calls]


# Convention "CLOCK31" / "CLOCK0"
def clock31():
    return itertools.count(0, 31)


def clock0():
    return itertools.repeat(0)


@pytest.fixture
def fx():
    with ExitStack() as stack:
        f = Fakes(stack)
        stack.enter_context(patch.object(ns, "psycopg2", f.fake_pg))
        stack.enter_context(patch.object(ns, "select", f.fake_sel))
        yield f


# Convention "collect(T)": returns (frames, excinfo)
def collect(gen, exc_type):
    frames = []
    with pytest.raises(exc_type) as exc:
        for f in gen:
            frames.append(f)  # noqa: PERF402  (list(gen) would lose the frames when gen raises)
    return frames, exc


# --------------------------------------------------------------------------- #
# notification_event_generator
# --------------------------------------------------------------------------- #

# [claude] NST-G-01
def test_nst_g_01__calling_opens_nothing(fx):
    """NST-G-01 — calling the function opens nothing.
    Rules: R1."""
    gen = ns.notification_event_generator(7, 3)
    # Then 1
    assert fx.fake_pg.connect.call_count == 0
    # Then 2
    assert fx.fake_sel.select.call_count == 0
    gen.close()


# [claude] NST-G-02
def test_nst_g_02__closed_before_first_next_never_connects(fx):
    """NST-G-02 — a generator closed before its first next() never connects.
    Rules: R1."""
    gen = ns.notification_event_generator(7, 3)
    gen.close()
    # Then 1
    assert fx.fake_pg.connect.call_count == 0
    # Then 2
    assert fx.conn.close.call_count == 0


# [claude] NST-G-03
def test_nst_g_03__first_next_connects_listens_and_yields_connected(fx):
    """NST-G-03 — the first next() connects, sets autocommit, listens, yields the connected frame.
    Rules: R2."""
    gen = ns.notification_event_generator(7, 3)
    first = next(gen)
    try:
        # Then 1
        assert first == "event: connected\ndata: {}\n\n"
        # Then 2
        assert fx.fake_pg.connect.call_args == call(ns.settings.DATABASE_URL)
        # Then 3
        assert fx.fake_pg.connect.call_count == 1
        # Then 4
        assert fx.conn.set_isolation_level.call_args == call(0)
        # Then 5
        assert fx.cur.execute.call_args_list == [call("LISTEN user_notifications;")]
        # Then 6
        assert fx.call_names()[:3] ==["set_isolation_level", "cursor", "cursor().execute"]
        # Then 7
        assert fx.fake_sel.select.call_count == 0
    finally:
        gen.close()


# [claude] NST-G-04
def test_nst_g_04__failing_connect_reaches_caller(fx):
    """NST-G-04 — a failing connect reaches the caller unchanged.
    Rules: R2; Errors row 1."""
    E = RuntimeError("down")
    fx.fake_pg.connect.side_effect = E
    gen = ns.notification_event_generator(7, 3)
    with pytest.raises(RuntimeError) as exc:
        next(gen)
    # Then 1
    assert exc.value is E
    # Then 2
    assert fx.fake_sel.select.call_count == 0


# [claude] NST-G-05
def test_nst_g_05__failing_listen_reaches_caller(fx):
    """NST-G-05 — a failing LISTEN reaches the caller unchanged.
    Rules: R2a [BUG-1803] (part that holds today); Errors row 2."""
    E = RuntimeError("listen failed")
    fx.cur.execute.side_effect = E
    gen = ns.notification_event_generator(7, 3)
    with pytest.raises(RuntimeError) as exc:
        next(gen)
    # Then 1
    assert exc.value is E
    # Then 2
    assert fx.fake_sel.select.call_count == 0


# [claude] NST-G-06
@pytest.mark.xfail(strict=True, reason=BUG_1803)
def test_nst_g_06__failing_autocommit_closes_connection(fx):
    """NST-G-06 — a failing autocommit switch closes the connection.
    Rules: R2a [BUG-1803]; Errors row 2."""
    E = RuntimeError("level failed")
    fx.conn.set_isolation_level.side_effect = E
    gen = ns.notification_event_generator(7, 3)
    with pytest.raises(RuntimeError) as exc:
        next(gen)
    # Then 1
    assert exc.value is E
    # Then 2
    assert fx.conn.close.call_count == 1


# [claude] NST-G-07
@pytest.mark.xfail(strict=True, reason=BUG_1803)
def test_nst_g_07__failing_cursor_closes_connection(fx):
    """NST-G-07 — a failing cursor() closes the connection.
    Rules: R2a [BUG-1803]; Errors row 2."""
    E = RuntimeError("cursor failed")
    fx.conn.cursor.side_effect = E
    gen = ns.notification_event_generator(7, 3)
    with pytest.raises(RuntimeError) as exc:
        next(gen)
    # Then 1
    assert exc.value is E
    # Then 2
    assert fx.conn.close.call_count == 1


# [claude] NST-G-08
@pytest.mark.xfail(strict=True, reason=BUG_1803)
def test_nst_g_08__failing_listen_closes_cursor_then_connection(fx):
    """NST-G-08 — a failing LISTEN closes the cursor, then the connection.
    Rules: R2a [BUG-1803]; Errors row 2."""
    E = RuntimeError("listen failed")
    fx.cur.execute.side_effect = E
    gen = ns.notification_event_generator(7, 3)
    with pytest.raises(RuntimeError) as exc:
        next(gen)
    # Then 1
    assert exc.value is E
    # Then 2
    assert fx.closes() == ["cursor().close", "close"]


# [claude] NST-G-09
def test_nst_g_09__each_round_waits_30_seconds(fx):
    """NST-G-09 — each round waits on the connection with a 30-second timeout.
    Rules: R3."""
    fx.script(fx.READY, fx.STOP)
    gen = ns.notification_event_generator(7, 3)
    frames, exc = collect(gen, OSError)
    # Then 1
    assert exc.value is fx.STOP
    # Then 2
    assert frames == ["event: connected\ndata: {}\n\n"]
    # Then 3
    assert fx.fake_sel.select.call_count == 2
    # Then 4
    assert fx.fake_sel.select.call_args_list[0] == call([fx.conn], [], [], 30)
    # Then 5
    assert fx.fake_sel.select.call_args_list[1] == call([fx.conn], [], [], 30)


# [claude] NST-G-10
def test_nst_g_10__each_timeout_with_30s_passed_yields_one_ping(fx):
    """NST-G-10 — each select timeout with 30 s passed yields exactly one ping and waits again.
    Rules: R5, R5a."""
    fx.script(fx.TIMEOUT, fx.TIMEOUT, fx.STOP)
    fx.clock(clock31())
    gen = ns.notification_event_generator(7, 3)
    frames, exc = collect(gen, OSError)
    # Then 1
    assert exc.value is fx.STOP
    # Then 2
    assert frames == ["event: connected\ndata: {}\n\n", ": ping\n\n", ": ping\n\n"]
    # Then 3
    assert fx.fake_sel.select.call_count == 3
    # Then 4
    assert fx.conn.poll.call_count == 0


# [claude] NST-G-11
@pytest.mark.xfail(strict=True, reason=BUG_1804)
def test_nst_g_11__others_traffic_does_not_starve_ping(fx):
    """NST-G-11 — others' traffic does not starve the ping: one ping per ready round once 30 s passed.
    Rules: R5, R5a [BUG-1804]."""
    other = msg({"recipient_user_id": 8, "workspace_id": 3, "notification_id": 90})
    fx.script(fx.READY, fx.READY, fx.READY, fx.STOP)
    fx.polls([other], [other], [other])
    fx.clock(clock31())
    gen = ns.notification_event_generator(7, 3)
    frames, exc = collect(gen, OSError)
    # Then 1
    assert exc.value is fx.STOP
    # Then 2
    assert frames == ["event: connected\ndata: {}\n\n", ": ping\n\n", ": ping\n\n", ": ping\n\n"]


# [claude] NST-G-12
def test_nst_g_12__ready_round_without_message_yields_nothing(fx):
    """NST-G-12 — a ready round with no message yields nothing.
    Rules: R4."""
    fx.script(fx.READY, fx.STOP)
    gen = ns.notification_event_generator(7, 3)
    frames, exc = collect(gen, OSError)
    # Then 1
    assert exc.value is fx.STOP
    # Then 2
    assert frames == ["event: connected\ndata: {}\n\n"]
    # Then 3
    assert fx.conn.poll.call_count == 1


# [claude] NST-G-13
def test_nst_g_13__queued_messages_oldest_first(fx):
    """NST-G-13 — queued messages are handled oldest first, before the next wait.
    Rules: R4, R9."""
    fx.script(fx.READY, fx.STOP)
    fx.polls([mine(9), mine(4)])
    gen = ns.notification_event_generator(7, 3)
    frames, exc = collect(gen, OSError)
    # Then 1
    assert exc.value is fx.STOP
    # Then 2
    assert frames == [
        "event: connected\ndata: {}\n\n",
        'event: notification\ndata: {"notification_id": 9}\n\n',
        'event: notification\ndata: {"notification_id": 4}\n\n',
    ]
    # Then 3
    assert fx.fake_sel.select.call_count == 2


# [claude] NST-G-14
def test_nst_g_14__handled_message_not_sent_again(fx):
    """NST-G-14 — a handled message is not sent again in the next round.
    Rules: R4, R9."""
    fx.script(fx.READY, fx.READY, fx.STOP)
    fx.polls([mine(1)], [mine(2)])
    gen = ns.notification_event_generator(7, 3)
    frames, exc = collect(gen, OSError)
    # Then 1
    assert exc.value is fx.STOP
    # Then 2
    assert frames == [
        "event: connected\ndata: {}\n\n",
        'event: notification\ndata: {"notification_id": 1}\n\n',
        'event: notification\ndata: {"notification_id": 2}\n\n',
    ]
    # Then 3
    assert fx.conn.poll.call_count == 2


# [claude] NST-G-15
def test_nst_g_15__non_json_message_skipped(fx):
    """NST-G-15 — a message that is not JSON is skipped and the stream goes on.
    Rules: R6."""
    fx.script(fx.READY, fx.STOP)
    fx.polls([raw("not json {"), mine(8)])
    gen = ns.notification_event_generator(7, 3)
    frames, exc = collect(gen, OSError)
    # Then 1
    assert exc.value is fx.STOP
    # Then 2
    assert frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 8}\n\n']


# [claude] NST-G-16
@pytest.mark.xfail(strict=True, reason=BUG_1802)
def test_nst_g_16__json_list_skipped(fx):
    """NST-G-16 — a JSON list is skipped and the stream goes on.
    Rules: R6 [BUG-1802]."""
    fx.script(fx.READY, fx.STOP)
    fx.polls([raw("[1, 2]"), mine(8)])
    gen = ns.notification_event_generator(7, 3)
    # Then 1 (collect(OSError) is the raises check)
    frames, exc = collect(gen, OSError)
    assert exc.value is fx.STOP
    # Then 2
    assert frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 8}\n\n']


# [claude] NST-G-17
@pytest.mark.xfail(strict=True, reason=BUG_1802)
def test_nst_g_17__json_null_skipped(fx):
    """NST-G-17 — a JSON null is skipped and the stream goes on.
    Rules: R6 [BUG-1802]."""
    fx.script(fx.READY, fx.STOP)
    fx.polls([raw("null"), mine(8)])
    gen = ns.notification_event_generator(7, 3)
    # Then 1 (collect(OSError) is the raises check)
    frames, exc = collect(gen, OSError)
    assert exc.value is fx.STOP
    # Then 2
    assert frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 8}\n\n']


# [claude] NST-G-18
def test_nst_g_18__other_user_skipped_both_sides(fx):
    """NST-G-18 — another user's message is skipped, on both sides of the user id.
    Rules: R7, R9."""
    fx.script(fx.READY, fx.STOP)
    fx.polls([
        msg({"recipient_user_id": 6, "workspace_id": 3, "notification_id": 61}),
        mine(5),
        msg({"recipient_user_id": 8, "workspace_id": 3, "notification_id": 81}),
    ])
    gen = ns.notification_event_generator(7, 3)
    frames, exc = collect(gen, OSError)
    # Then 1
    assert exc.value is fx.STOP
    # Then 2
    assert frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 5}\n\n']


# [claude] NST-G-19
def test_nst_g_19__other_workspace_skipped_both_sides(fx):
    """NST-G-19 — another workspace's message for the same user is skipped, on both sides.
    Rules: R7, R9."""
    fx.script(fx.READY, fx.STOP)
    fx.polls([
        msg({"recipient_user_id": 7, "workspace_id": 2, "notification_id": 21}),
        mine(5),
        msg({"recipient_user_id": 7, "workspace_id": 4, "notification_id": 41}),
    ])
    gen = ns.notification_event_generator(7, 3)
    frames, exc = collect(gen, OSError)
    # Then 1
    assert exc.value is fx.STOP
    # Then 2
    assert frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 5}\n\n']


# [claude] NST-G-20
def test_nst_g_20__user_and_workspace_swapped_do_not_match(fx):
    """NST-G-20 — user and workspace swapped do not match.
    Rules: R7."""
    fx.script(fx.READY, fx.STOP)
    fx.polls([msg({"recipient_user_id": 3, "workspace_id": 7, "notification_id": 37}), mine(5)])
    gen = ns.notification_event_generator(7, 3)
    frames, exc = collect(gen, OSError)
    # Then 1
    assert exc.value is fx.STOP
    # Then 2
    assert frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 5}\n\n']


# [claude] NST-G-21
def test_nst_g_21__missing_user_or_workspace_key_skipped(fx):
    """NST-G-21 — a message missing the user or the workspace key is skipped.
    Rules: R7."""
    fx.script(fx.READY, fx.STOP)
    fx.polls([
        msg({"workspace_id": 3, "notification_id": 31}),
        msg({"recipient_user_id": 7, "notification_id": 71}),
        mine(5),
    ])
    gen = ns.notification_event_generator(7, 3)
    frames, exc = collect(gen, OSError)
    # Then 1
    assert exc.value is fx.STOP
    # Then 2
    assert frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 5}\n\n']


# [claude] NST-G-22
def test_nst_g_22__string_ids_never_match(fx):
    """NST-G-22 — ids sent as strings never match.
    Rules: R7."""
    fx.script(fx.READY, fx.STOP)
    fx.polls([
        msg({"recipient_user_id": "7", "workspace_id": 3, "notification_id": 11}),
        msg({"recipient_user_id": 7, "workspace_id": "3", "notification_id": 12}),
        mine(5),
    ])
    gen = ns.notification_event_generator(7, 3)
    frames, exc = collect(gen, OSError)
    # Then 1
    assert exc.value is fx.STOP
    # Then 2
    assert frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 5}\n\n']


# [claude] NST-G-23
def test_nst_g_23__json_float_and_true_equal_user_1(fx):
    """NST-G-23 — JSON 1.0 and true equal the user id 1 (Python equality).
    Rules: R7."""
    fx.script(fx.READY, fx.STOP)
    fx.polls([
        msg({"recipient_user_id": 1.0, "workspace_id": 3, "notification_id": 14}),
        msg({"recipient_user_id": True, "workspace_id": 3.0, "notification_id": 15}),
    ])
    gen = ns.notification_event_generator(1, 3)
    frames, exc = collect(gen, OSError)
    # Then 1
    assert exc.value is fx.STOP
    # Then 2
    assert frames == [
        "event: connected\ndata: {}\n\n",
        'event: notification\ndata: {"notification_id": 14}\n\n',
        'event: notification\ndata: {"notification_id": 15}\n\n',
    ]


# [claude] NST-G-24
def test_nst_g_24__frame_carries_only_notification_id(fx):
    """NST-G-24 — the frame carries only notification_id.
    Rules: R8."""
    fx.script(fx.READY, fx.STOP)
    fx.polls([msg({
        "recipient_user_id": 7, "workspace_id": 3, "notification_id": 12,
        "title": "Payroll", "entity_id": 99,
    })])
    gen = ns.notification_event_generator(7, 3)
    frames, exc = collect(gen, OSError)
    # Then 1
    assert exc.value is fx.STOP
    # Then 2
    assert frames[1] == 'event: notification\ndata: {"notification_id": 12}\n\n'
    # Then 3
    assert len(frames) == 2


# [claude] NST-G-25
def test_nst_g_25__missing_notification_id_sent_as_null(fx):
    """NST-G-25 — a missing notification_id is sent as null.
    Rules: R8."""
    fx.script(fx.READY, fx.STOP)
    fx.polls([msg({"recipient_user_id": 7, "workspace_id": 3})])
    gen = ns.notification_event_generator(7, 3)
    frames, exc = collect(gen, OSError)
    # Then 1
    assert exc.value is fx.STOP
    # Then 2
    assert frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": null}\n\n']


# [claude] NST-G-26
def test_nst_g_26__close_after_connected_closes_cursor_then_connection(fx):
    """NST-G-26 — close() right after the connected frame closes the cursor, then the connection, once each.
    Rules: R10."""
    gen = ns.notification_event_generator(7, 3)
    first = next(gen)
    gen.close()
    # Then 1
    assert first == "event: connected\ndata: {}\n\n"
    # Then 2
    assert fx.closes() == ["cursor().close", "close"]
    # Then 3
    assert fx.fake_sel.select.call_count == 0


# [claude] NST-G-27
def test_nst_g_27__close_after_notification_closes_once_each(fx):
    """NST-G-27 — close() after a notification frame closes the cursor, then the connection, once each.
    Rules: R10."""
    fx.script(fx.READY, fx.STOP)
    fx.polls([mine(1), mine(2)])
    gen = ns.notification_event_generator(7, 3)
    next(gen)
    second = next(gen)
    gen.close()
    # Then 1
    assert second == 'event: notification\ndata: {"notification_id": 1}\n\n'
    # Then 2
    assert fx.closes() == ["cursor().close", "close"]
    # Then 3
    assert fx.fake_sel.select.call_count == 1


# [claude] NST-G-28
def test_nst_g_28__failing_select_ends_stream_cleaned_up(fx):
    """NST-G-28 — a failing select ends the stream with its exception, cleaned up once.
    Rules: R10; Errors row 3."""
    fx.script(fx.STOP)
    gen = ns.notification_event_generator(7, 3)
    frames, exc = collect(gen, OSError)
    # Then 1
    assert exc.value is fx.STOP
    # Then 2
    assert frames == ["event: connected\ndata: {}\n\n"]
    # Then 3
    assert fx.closes() == ["cursor().close", "close"]


# [claude] NST-G-29
def test_nst_g_29__failing_poll_ends_stream_cleaned_up(fx):
    """NST-G-29 — a failing poll ends the stream with its exception, cleaned up once.
    Rules: R10; Errors row 3."""
    fx.script(fx.READY, fx.STOP)
    E = RuntimeError("poll failed")
    fx.conn.poll.side_effect = E
    gen = ns.notification_event_generator(7, 3)
    frames, exc = collect(gen, RuntimeError)
    # Then 1
    assert exc.value is E
    # Then 2
    assert frames == ["event: connected\ndata: {}\n\n"]
    # Then 3
    assert fx.closes() == ["cursor().close", "close"]
    # Then 4
    assert fx.fake_sel.select.call_count == 1


# [claude] NST-G-30
def test_nst_g_30__close_after_cleanup_closes_nothing_more(fx):
    """NST-G-30 — after a cleanup, closing the generator again closes nothing more.
    Rules: R10."""
    fx.script(fx.STOP)
    gen = ns.notification_event_generator(7, 3)
    collect(gen, OSError)
    gen.close()
    # Then 1
    assert fx.closes() == ["cursor().close", "close"]


# [claude] NST-G-31
@pytest.mark.xfail(strict=True, reason=BUG_1804)
def test_nst_g_31__timeout_under_30s_yields_nothing(fx):
    """NST-G-31 — a timeout round with less than 30 s since the last frame yields nothing.
    Rules: R5a [BUG-1804]."""
    fx.script(fx.TIMEOUT, fx.STOP)
    fx.clock(clock0())
    gen = ns.notification_event_generator(7, 3)
    frames, exc = collect(gen, OSError)
    # Then 1
    assert exc.value is fx.STOP
    # Then 2
    assert frames == ["event: connected\ndata: {}\n\n"]


# [claude] NST-G-32
def test_nst_g_32__ready_round_no_time_passed_adds_no_ping(fx):
    """NST-G-32 — a ready round with a notification and no time passed adds no ping.
    Rules: R5a, R4."""
    fx.script(fx.READY, fx.STOP)
    fx.polls([mine(5)])
    fx.clock(clock0())
    gen = ns.notification_event_generator(7, 3)
    frames, exc = collect(gen, OSError)
    # Then 1
    assert exc.value is fx.STOP
    # Then 2
    assert frames == ["event: connected\ndata: {}\n\n", 'event: notification\ndata: {"notification_id": 5}\n\n']


# [claude] NST-G-33
@pytest.mark.xfail(strict=True, reason=BUG_1804)
def test_nst_g_33__ready_round_after_30s_yields_one_ping_after_notifications(fx):
    """NST-G-33 — a ready round ending 30 s or more after the last frame yields one ping after its notifications.
    Rules: R5a [BUG-1804]."""
    fx.script(fx.READY, fx.STOP)
    fx.polls([mine(5)])
    fx.clock(clock31())
    gen = ns.notification_event_generator(7, 3)
    frames, exc = collect(gen, OSError)
    # Then 1
    assert exc.value is fx.STOP
    # Then 2
    assert frames == [
        "event: connected\ndata: {}\n\n",
        'event: notification\ndata: {"notification_id": 5}\n\n',
        ": ping\n\n",
    ]


# [claude] NST-G-34
@pytest.mark.xfail(strict=True, reason=BUG_1804)
def test_nst_g_34__notification_restarts_30s_timeout_25s_later_yields_nothing(fx):
    """NST-G-34 — a notification frame restarts the 30 s: a timeout 25 s later yields nothing.
    Rules: R5a [BUG-1804]."""
    fx.script(fx.READY, fx.TIMEOUT, fx.READY, fx.STOP)
    fx.polls([mine(5)], [mine(6)])
    now = [0]
    fx.clock(lambda: now[0])
    gen = ns.notification_event_generator(7, 3)
    try:
        first = next(gen)
        now[0] = 20
        second = next(gen)
        now[0] = 45
        third = next(gen)
        # Then 1
        assert first == "event: connected\ndata: {}\n\n"
        # Then 2
        assert second == 'event: notification\ndata: {"notification_id": 5}\n\n'
        # Then 3
        assert third == 'event: notification\ndata: {"notification_id": 6}\n\n'
    finally:
        gen.close()


# [claude] NST-G-35
def test_nst_g_35__timeout_35s_after_notification_yields_one_ping(fx):
    """NST-G-35 — a timeout 35 s after the last notification frame yields one ping.
    Rules: R5, R5a."""
    fx.script(fx.READY, fx.TIMEOUT, fx.READY, fx.STOP)
    fx.polls([mine(5)], [mine(6)])
    now = [0]
    fx.clock(lambda: now[0])
    gen = ns.notification_event_generator(7, 3)
    try:
        next(gen)
        now[0] = 20
        second = next(gen)
        now[0] = 55
        third = next(gen)
        # Then 1
        assert second == 'event: notification\ndata: {"notification_id": 5}\n\n'
        # Then 2
        assert third == ": ping\n\n"
    finally:
        gen.close()
