"""Unit tests for app/core/notification_channels.py.

Implements tests/unit/core/notification_channels.cases.md, one test per case, in
card order. NCH-01 and NCH-02 use no database. NCH-03 opens two autocommit
psycopg2 connections to the test database, outside the test session, and writes
nothing to any table. Nothing is mocked (Conventions, Externals: None).

TEST_DSN (Spec gap 1) is the URL of the session's `engine` fixture (the engine
the test session's `db` is bound to), rendered with its password.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
import re
import select

import psycopg2
import pytest
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from app.core.notification_channels import NOTIFICATION_CHANNEL


# Convention "TEST_DSN": the URL the test session's engine uses, in a form psycopg2.connect accepts
@pytest.fixture
def dsn(engine):
    return engine.url.set(drivername="postgresql").render_as_string(hide_password=False)


# --------------------------------------------------------------------------- #
# NOTIFICATION_CHANNEL
# --------------------------------------------------------------------------- #


# [claude] NCH-01
def test_nch_01__the_value_is_exactly_user_notifications():
    """NCH-01 — the value is exactly "user_notifications".
    Rules: `NOTIFICATION_CHANNEL` R1"""
    value = NOTIFICATION_CHANNEL

    # Then 1
    assert value == "user_notifications"
    # Then 2
    assert len(value) == 18
    # Then 3
    assert type(value) is str


# [claude] NCH-02
def test_nch_02__the_value_is_a_valid_unquoted_postgresql_identifier_that_keeps_its_spelling():
    """NCH-02 — the value is a valid unquoted PostgreSQL identifier that keeps its spelling.
    Rules: `NOTIFICATION_CHANNEL` R2"""
    m = re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", NOTIFICATION_CHANNEL)

    # Then 1
    assert m is not None
    # Then 2
    assert len(NOTIFICATION_CHANNEL.encode("utf-8")) <= 63


# [claude] NCH-03
def test_nch_03__a_listener_on_the_channel_receives_a_notify_sent_to_it_channel_and_payload(dsn):
    """NCH-03 — a listener on the channel receives a notify sent to it, channel and payload unchanged.
    Rules: `NOTIFICATION_CHANNEL` R3"""
    listener = sender = None
    try:
        listener = psycopg2.connect(dsn)
        listener.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        sender = psycopg2.connect(dsn)
        sender.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        listener.cursor().execute("LISTEN " + NOTIFICATION_CHANNEL + ";")

        sender.cursor().execute("SELECT pg_notify(%s, %s)", (NOTIFICATION_CHANNEL, "probe-42"))

        # Then 1
        assert select.select([listener], [], [], 5) != ([], [], [])
        # Then 2
        listener.poll()
        assert len(listener.notifies) == 1
        # Then 3
        assert listener.notifies[0].channel == "user_notifications"
        # Then 4
        assert listener.notifies[0].payload == "probe-42"
    finally:
        for conn in (listener, sender):
            if conn is not None:
                conn.close()
