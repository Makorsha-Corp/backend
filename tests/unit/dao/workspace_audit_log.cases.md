# Test cases — `app/dao/workspace_audit_log.py`

> **Spec:** `tests/unit/dao/workspace_audit_log.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). P1–P3 and Q1 were decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. Additive, from `workspace_audit_log.verify.md` (case-missing Finding 1; recipe R-1): R-1 → WAL-LA-22 (no `workspace_id`), WAL-LA-23 (no `user_id`). No existing card, Convention or ID changed; none retired.
> **Counts:** 23 cases · 20 expected-to-pass · 3 expected-to-fail (bugs) · 5 deferred

## Reviewer summary
- **Per callable:** `log_action` 23 (3 bug).
- **Revision 1:** R7's three required keywords each have a "left out" card (LA-19, LA-22, LA-23).
- **Depth:** lighter target (skill step 1a). One append-only insert; it writes no stock, money or order state. Every named length boundary has both sides (45/46, 100/101, 50/51).
- **Expected-to-fail:** BUG-1405 1 strict (WAL-LA-07, a 46-character IP is cut). BUG-1403 2 strict (WAL-LA-15 `Asia/Dhaka`, WAL-LA-16 `America/New_York`); WAL-LA-14 under `UTC` is the passing companion. All three are deterministic today.
- **Commit spy:** WAL-LA-20, the one writer: savepoint, call, raw read inside, roll back, gone, spy never called.
- **Notable design choices:**
  - Time-zone cards set `SET LOCAL TIME ZONE` themselves before the call, and read the moment back with `AT TIME ZONE 'UTC'` against a real UTC clock window of ±5 s (the default `utcnow` cannot be patched, per the spec).
  - WAL-LA-21 holds R6: one `INSERT`, and no `SELECT` of `workspaces` or `profiles` (nothing is checked beyond the foreign keys).
  - BUG-1404 (callers never pass IP and user agent) is the manager's and service's: a Deferred entry.
  - No `Author:` lines (caller's instruction). Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `WAL` = `app/dao/workspace_audit_log.py`. `LA` log_action.

**Actors and fixed values.**
- `dao` = the singleton `workspace_audit_log_dao` (`from app.dao.workspace_audit_log import workspace_audit_log_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword unless the card says "positional". `result` = what the When call returns.
- `WorkspaceAuditLog` = `app.models.workspace_audit_log.WorkspaceAuditLog`. `text` = `sqlalchemy.text`. `datetime`, `timedelta`, `timezone` = the `datetime` module's classes. `DataError`, `IntegrityError`, `StatementError` = from `sqlalchemy.exc`.
- MISSING = `999999999`. SLACK = `timedelta(seconds=5)`. IP45 = `"1" * 45`. IP46 = `"1" * 46`. UA5000 = `"u" * 5000`.

**Externals.** None. Nothing is mocked.

**Given rows.** Standing rows, in every test, no Given line: W1, W2 = two `workspaces` rows from `make_workspace(db)`; U1 = a `profiles` row from `make_profile(db)`. No `workspace_audit_logs` row exists unless the card's Given lists it. A Given line written as code is a step to run exactly as written, in order.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id.
- **nothing written** = the number of `workspace_audit_logs` rows stored (all workspaces) equals its value before the call.
- **clock window** = `before = datetime.now(timezone.utc).replace(tzinfo=None)` is the last step before the When; `after` = the same expression, the first step after it.
- **stamp(X)** = `db.execute(text("SELECT created_at AT TIME ZONE 'UTC' FROM workspace_audit_logs WHERE id = :id"), {"id": X.id}).scalar()` — a naive UTC value.
- `raises: <DB error>` = `with pytest.raises(<type>) as exc:` then `with db.begin_nested():` then the When; further `raises:` lines assert on `exc.value`, after the block. `raises: TypeError` = plain `pytest.raises(TypeError)`.
- **rolled back** = `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`. Write the call and the checks exactly as shown.

**Statement recorder.** The SQL statements the session sends during the When are recorded (a `before_cursor_execute` listener). `selects` = every recorded `SELECT`; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`.

**Race simulations.** None in this module.

## `WorkspaceAuditLogDAO.log_action`

### WAL-LA-01 — one row with exactly the given values, flushed
- **Rules:** `log_action` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no audit rows.

**When**
- `result = dao.log_action(db, workspace_id=W1.id, user_id=U1.id, action="member_added", resource_type="workspace_member", resource_id=42, metadata={"role": "admin", "n": 2}, ip_address="10.0.0.1", user_agent="Mozilla/5.0")`.

**Then**
1. returns: `isinstance(result, WorkspaceAuditLog)`.
2. returns: `result.id is not None`.
3. re-read result: `workspace_id == W1.id`, `user_id == U1.id`, `action == "member_added"`.
4. re-read result: `resource_type == "workspace_member"`, `resource_id == 42`.
5. re-read result: `metadata_json == {"role": "admin", "n": 2}`.
6. re-read result: `ip_address == "10.0.0.1"`, `user_agent == "Mozilla/5.0"`.
7. count: `workspace_audit_logs` has exactly 1 row with `workspace_id == W1.id`.

### WAL-LA-02 — optional values not given are stored NULL; an empty action is accepted
- **Rules:** `log_action` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no audit rows.

**When**
- `result = dao.log_action(db, workspace_id=W1.id, user_id=U1.id, action="")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `action == ""`.
3. re-read result: `resource_type is None`, `resource_id is None`, `metadata_json is None`.
4. re-read result: `ip_address is None`, `user_agent is None`.

### WAL-LA-03 — no workspace and no user are stored NULL
- **Rules:** `log_action` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No audit row with `action "system_check"`.

**When**
- `result = dao.log_action(db, workspace_id=None, user_id=None, action="system_check")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `workspace_id is None`, `user_id is None`, `action == "system_check"`.

### WAL-LA-04 — a list as metadata is stored
- **Rules:** `log_action` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no audit rows.

**When**
- `result = dao.log_action(db, workspace_id=W1.id, user_id=U1.id, action="bulk", metadata=[1, "two"])`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `metadata_json == [1, "two"]`.

### WAL-LA-05 — a 5 000-character user agent is stored whole
- **Rules:** `log_action` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no audit rows.

**When**
- `result = dao.log_action(db, workspace_id=W1.id, user_id=U1.id, action="login", user_agent=UA5000)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `user_agent == UA5000`.

### WAL-LA-06 — a 45-character IP address is stored whole
- **Rules:** `log_action` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no audit rows.

**When**
- `result = dao.log_action(db, workspace_id=W1.id, user_id=U1.id, action="login", ip_address=IP45)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `ip_address == IP45`.

### WAL-LA-07 — a 46-character IP address is cut to 45 and the row is written
- **Rules:** `log_action` R3 [BUG-1405]
- **Kind:** bug
- **Expect:** xfail BUG-1405
- **Fails today on:** Then 1 (the call raises DataError: 46 characters do not fit `VARCHAR(45)`)

**Given**
1. W1 has no audit rows.

**When**
- inside `with db.begin_nested():` — `result = dao.log_action(db, workspace_id=W1.id, user_id=U1.id, action="login", ip_address=IP46)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `ip_address == IP45`.
3. count: `workspace_audit_logs` has exactly 1 row with `workspace_id == W1.id`.

### WAL-LA-08 — an action of 100 and a resource type of 50 characters are stored whole
- **Rules:** `log_action` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no audit rows.

**When**
- `result = dao.log_action(db, workspace_id=W1.id, user_id=U1.id, action="a" * 100, resource_type="r" * 50)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `action == "a" * 100`, `resource_type == "r" * 50`.

### WAL-LA-09 — an action of 101 characters raises DataError and writes nothing
- **Rules:** `log_action` R4, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no audit rows.

**When**
- `dao.log_action(db, workspace_id=W1.id, user_id=U1.id, action="a" * 101)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "22001"`.
3. nothing written: nothing written.

### WAL-LA-10 — a resource type of 51 characters raises DataError and writes nothing
- **Rules:** `log_action` R4, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no audit rows.

**When**
- `dao.log_action(db, workspace_id=W1.id, user_id=U1.id, action="x", resource_type="r" * 51)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "22001"`.
3. nothing written: nothing written.

### WAL-LA-11 — metadata JSON cannot encode raises StatementError and writes nothing
- **Rules:** `log_action` R4, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no audit rows.

**When**
- `dao.log_action(db, workspace_id=W1.id, user_id=U1.id, action="x", metadata={"at": datetime(2026, 3, 5, 12, 0, 0)})`, inside the wrap of `raises: StatementError`.

**Then**
1. raises: `StatementError`.
2. raises: `isinstance(exc.value.orig, TypeError)`.
3. nothing written: nothing written.

### WAL-LA-12 — an unknown workspace raises IntegrityError 23503 and writes nothing
- **Rules:** `log_action` R4, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no audit rows.

**When**
- `dao.log_action(db, workspace_id=MISSING, user_id=U1.id, action="x")`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. nothing written: nothing written.

### WAL-LA-13 — an unknown user raises IntegrityError 23503 and writes nothing
- **Rules:** `log_action` R4, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no audit rows.

**When**
- `dao.log_action(db, workspace_id=W1.id, user_id=MISSING, action="x")`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. nothing written: nothing written.

### WAL-LA-14 — under a UTC session, created_at read as UTC is the moment of the call
- **Rules:** `log_action` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`
2. clock window: `before` is read here.

**When**
- `result = dao.log_action(db, workspace_id=W1.id, user_id=U1.id, action="tz")`, then `after` is read.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `stamp(result) >= before - SLACK`.
3. re-read result: `stamp(result) <= after + SLACK`.

### WAL-LA-15 — under Asia/Dhaka, created_at read as UTC is still the moment of the call
- **Rules:** `log_action` R5 [BUG-1403]
- **Kind:** bug
- **Expect:** xfail BUG-1403
- **Fails today on:** Then 2 (the naive UTC value is read as Dhaka time: 6 hours early)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`
2. clock window: `before` is read here.

**When**
- `result = dao.log_action(db, workspace_id=W1.id, user_id=U1.id, action="tz")`, then `after` is read.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `stamp(result) >= before - SLACK`.
3. re-read result: `stamp(result) <= after + SLACK`.

### WAL-LA-16 — under America/New_York, created_at read as UTC is still the moment of the call
- **Rules:** `log_action` R5 [BUG-1403]
- **Kind:** bug
- **Expect:** xfail BUG-1403
- **Fails today on:** Then 2 (the naive UTC value is read as New York time: 5 hours late)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))`
2. clock window: `before` is read here.

**When**
- `result = dao.log_action(db, workspace_id=W1.id, user_id=U1.id, action="tz")`, then `after` is read.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `stamp(result) <= after + SLACK`.
3. re-read result: `stamp(result) >= before - SLACK`.

### WAL-LA-17 — an identical earlier row does not stop a second one
- **Rules:** `log_action` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `E = WorkspaceAuditLog(workspace_id=W1.id, user_id=U1.id, action="member_added")`, `db.add(E)`, `db.flush()`.

**When**
- `result = dao.log_action(db, workspace_id=W1.id, user_id=U1.id, action="member_added")`.

**Then**
1. returns: `result.id != E.id`.
2. count: `workspace_audit_logs` has exactly 2 rows with `workspace_id == W1.id` and `action == "member_added"`.

### WAL-LA-18 — positional arguments raise TypeError
- **Rules:** `log_action` R7, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no audit rows.

**When**
- `dao.log_action(db, W1.id, U1.id, "x")` (positional), inside `raises: TypeError`.

**Then**
1. raises: `TypeError`.
2. nothing written: nothing written.

### WAL-LA-19 — leaving out action raises TypeError
- **Rules:** `log_action` R7, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no audit rows.

**When**
- `dao.log_action(db, workspace_id=W1.id, user_id=U1.id)`, inside `raises: TypeError`.

**Then**
1. raises: `TypeError`.
2. nothing written: nothing written.

### WAL-LA-20 — the row is flushed, not committed: visible in the session, gone after a rollback
- **Rules:** `log_action` R1, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no audit rows.
2. Savepoint and commit spy per **rolled back**.

**When**
- `result = dao.log_action(db, workspace_id=W1.id, user_id=U1.id, action="spy")`.

**Then**
1. returns: `result.id is not None`.
2. count: inside the savepoint, `workspace_audit_logs` has exactly 1 row with `workspace_id == W1.id` and `action == "spy"` (raw `SELECT count(*)`).
3. count: after the savepoint rollback, `workspace_audit_logs` has exactly 0 rows with `workspace_id == W1.id` and `action == "spy"`.
4. mock called: the `db.commit` spy was never called.

### WAL-LA-21 — one INSERT and nothing else: no existence check of workspace or user
- **Rules:** `log_action` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no audit rows.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.log_action(db, workspace_id=W1.id, user_id=U1.id, action="rec")`.

**Then**
1. returns: `result.id is not None`.
2. statement: `len(written) == 1`.
3. statement: `"INSERT INTO workspace_audit_logs" in written[0]`.
4. statement: `not any("FROM workspaces" in s for s in selects)`.
5. statement: `not any("FROM profiles" in s for s in selects)`.

### WAL-LA-22 — leaving out workspace_id raises TypeError
- **Rules:** `log_action` R7, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no audit rows.

**When**
- `dao.log_action(db, user_id=U1.id, action="x")` (no `workspace_id`), inside `raises: TypeError`.

**Then**
1. raises: `TypeError`.
2. nothing written: nothing written.

### WAL-LA-23 — leaving out user_id raises TypeError
- **Rules:** `log_action` R7, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no audit rows.

**When**
- `dao.log_action(db, workspace_id=W1.id, action="x")` (no `user_id`), inside `raises: TypeError`.

**Then**
1. raises: `TypeError`.
2. nothing written: nothing written.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| BUG-1404 (P2) — the client IP (trusted-proxy resolved) and user agent are passed into every `log_action` call | `WorkspaceManager` (six actions), `WorkspaceService`, workspace endpoints; BUG-1193 expense-order delete record | That every call passes both values. |
| BUG-1405 cut, once BUG-1404 lands | `WorkspaceManager` callers | That the action succeeds with a long forwarded address. |
| Q1 — no reader of this table | none (intended) | A reader is a future feature. |
| `WorkspaceAuditLogCreate` alias `metadata` → `metadata_json` | `tests/unit/dao/base.cases.md` / schema | Inherited `create`; not repeated. |
| Inherited `BaseDAO` methods and the singleton | `tests/unit/dao/base.cases.md` | No caller. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `log_action` R4 | "`StatementError` (cause `TypeError`)": whether the cause is reachable as `exc.value.orig` is not said. | WAL-LA-11 Then 2 uses `exc.value.orig`; if the executor finds it on `__cause__` instead, that is the same fact. |
| 2 | `log_action` R5 | The tolerance for "equals the UTC clock" is not given. | Cards use a window of ±5 s around the call. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `log_action` | Returns | WAL-LA-01 |
| `log_action` | R1 | WAL-LA-01, WAL-LA-04, WAL-LA-20 |
| `log_action` | R2 | WAL-LA-02, WAL-LA-03 |
| `log_action` | R3 | WAL-LA-05, WAL-LA-06 |
| `log_action` | R3 [BUG-1405] | WAL-LA-07 |
| `log_action` | R4 | WAL-LA-08, WAL-LA-09, WAL-LA-10, WAL-LA-11, WAL-LA-12, WAL-LA-13 |
| `log_action` | R5 | WAL-LA-14 |
| `log_action` | R5 [BUG-1403] | WAL-LA-15, WAL-LA-16 |
| `log_action` | R6 | WAL-LA-17, WAL-LA-21 |
| `log_action` | R7 | WAL-LA-18, WAL-LA-19, WAL-LA-22, WAL-LA-23 |
| `log_action` | Errors row 1 | WAL-LA-09, WAL-LA-10 |
| `log_action` | Errors row 2 | WAL-LA-12, WAL-LA-13 |
| `log_action` | Errors row 3 | WAL-LA-11 |
| `log_action` | Errors row 4 | WAL-LA-18, WAL-LA-19, WAL-LA-22, WAL-LA-23 |
| `log_action` | Side effects | WAL-LA-20 |
