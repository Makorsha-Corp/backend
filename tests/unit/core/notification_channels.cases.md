# Test cases — `app/core/notification_channels.py`

> **Spec:** `tests/unit/core/notification_channels.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; no questions).
> **Counts:** 3 cases · 3 expected-to-pass · 0 expected-to-fail (bugs) · 1 deferred

## Reviewer summary
- **Per callable:** `NOTIFICATION_CHANNEL` 3 (no bug).
- **Depth:** lighter target (skill step 1a). One constant; no data, no stock, money or order state.
- **Notable design choices:**
  - R3 is marked integration-only in the spec, but the spec's Notes give a self-contained recipe that writes nothing to any table, so it gets one card (NCH-03) using two autocommit `psycopg2` connections outside the test session. Both connections are closed in a `finally`.
  - The connection URL for NCH-03 is the test database's own URL, which the spec does not name (Spec gap 1).
- **Needs a decision:** None blocking. See Spec gap 1.

## Conventions for this module

**IDs.** `NCH` = `app/core/notification_channels.py`. One callable; ids `NCH-NN`.

**Names.**
- `NOTIFICATION_CHANNEL` = `from app.core.notification_channels import NOTIFICATION_CHANNEL`. `re`, `select`, `psycopg2` = the standard / installed modules. `ISOLATION_LEVEL_AUTOCOMMIT` = `psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT`.
- **TEST_DSN** = the connection URL of the test database, the one the test session's engine uses (Spec gap 1), in a form `psycopg2.connect` accepts.
- No database session and no table are used by NCH-01, NCH-02.

**Externals.** None. Nothing is mocked. **Race simulations.** None.

## `NOTIFICATION_CHANNEL`

### NCH-01 — the value is exactly "user_notifications"
- **Rules:** `NOTIFICATION_CHANNEL` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond Conventions.

**When**
- `value = NOTIFICATION_CHANNEL`.

**Then**
1. returns: `value == "user_notifications"`.
2. returns: `len(value) == 18`.
3. returns: `type(value) is str`.

### NCH-02 — the value is a valid unquoted PostgreSQL identifier that keeps its spelling
- **Rules:** `NOTIFICATION_CHANNEL` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond Conventions.

**When**
- `m = re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", NOTIFICATION_CHANNEL)`.

**Then**
1. returns: `m is not None`.
2. returns: `len(NOTIFICATION_CHANNEL.encode("utf-8")) <= 63`.

### NCH-03 — a listener on the channel receives a notify sent to it, channel and payload unchanged
- **Rules:** `NOTIFICATION_CHANNEL` R3
- **Kind:** external
- **Expect:** pass

**Given**
1. `listener = psycopg2.connect(TEST_DSN)`, then `listener.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)`.
2. `sender = psycopg2.connect(TEST_DSN)`, then `sender.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)`.
3. `listener.cursor().execute("LISTEN " + NOTIFICATION_CHANNEL + ";")` (the name pasted unquoted, as the stream does).
4. Both connections are closed in a `finally` after the Then checks.

**When**
- `sender.cursor().execute("SELECT pg_notify(%s, %s)", (NOTIFICATION_CHANNEL, "probe-42"))`.

**Then**
1. returns: `select.select([listener], [], [], 5) != ([], [], [])` (something arrived within 5 seconds).
2. returns: after `listener.poll()`, `len(listener.notifies) == 1`.
3. returns: `listener.notifies[0].channel == "user_notifications"`.
4. returns: `listener.notifies[0].payload == "probe-42"`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Overview — `NotificationDAO.create` sends to this channel after an insert, and the server-sent-events stream listens on it | `tests/unit/dao/notification.spec.md` / `notification_stream` service spec / integration tests | Here only the channel name and one raw notify are checked. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Notes for the test designer (R3 recipe: "two `psycopg2` connections to the test database") | Where the test database's connection URL comes from is not named (setting, environment variable or fixture). | NCH-03 uses TEST_DSN = "the URL the test session's engine uses"; the executor picks the source. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `NOTIFICATION_CHANNEL` | R1 | NCH-01 |
| `NOTIFICATION_CHANNEL` | R2 | NCH-02 |
| `NOTIFICATION_CHANNEL` | R3 | NCH-03 |
