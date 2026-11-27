# Test cases — `app/dao/workspace_invitation.py`

> **Spec:** `tests/unit/dao/workspace_invitation.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). Q1 (BUG-1402) and the order of BUG-1401 were decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. Additive, from `workspace_invitation.verify.md` (case-missing Findings 1 … 4; recipes R-1 … R-4): R-1 → WSI-UI-12; R-2 → WSI-CP-05; R-3 → WSI-GP-09, WSI-CP-06, WSI-GA-08; R-4 → WSI-UI-13 (strict xfail BUG-1402; its holds-today line comes first, as in UI-02 … UI-04, so it fails on Then 2). No existing card, Convention or ID changed; none retired.
> **Counts:** 43 cases · 33 expected-to-pass · 10 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `get_by_token` 7 · `get_pending_invitations` 9 (2 bug) · `get_user_invitations` 13 (6 bug) · `count_pending_invitations` 6 · `get_all_invitations` 8 (2 bug).
- **Revision 1:** each of the three queries now has its own status shapes (UI-12, CP-05) and an other-workspace row at the lower id (GP-09, CP-06, GA-08). UI-13 stores a padded email, so a BUG-1402 fix that trims only the argument fails. Not changed (verifier: not required): the tied order cards GP-06, UI-08, GA-05 use tokens that rise with id; the strict SQL cards cover a wrong tie-break.
- **Depth:** lighter target (skill step 1a). Five plain filtered reads; nothing here writes stock, money or order state.
- **Expected-to-fail:** BUG-1401 6: GP-06, UI-08, GA-05 non-strict (the order itself), GP-07, UI-09, GA-06 strict (the SQL recorder). BUG-1402 3, all strict (today's result is deterministic): UI-02, UI-03, UI-04.
- **Commit spies:** none. Every method only reads.
- **Notable design choices:**
  - `utcnow` is patched to NOW around every When; expiry is set relative to NOW. The boundary card GP-02 holds three rows: `== NOW`, `NOW + 1 µs`, a day past.
  - Order cards give `invited_at` values that do not rise with `id`, plus a tie on `invited_at` broken by `id`. Pass cards compare sets.
  - Tokens carry a per-test `TAG`, so concurrent tests never wait on each other's unique index.
  - `get_user_invitations`: capitals and spaces are BUG-1402 (they must match after the fix); a part of the email and `_` are R2a pass cards (they must never match, also after the fix — an unescaped `ILIKE` fix would fail UI-06).
  - "Writes nothing": one card per query; `get_pending_invitations` and `count_pending_invitations` share a filter but not a query, so each has one.
  - No `Author:` lines (caller's instruction). Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `WSI` = `app/dao/workspace_invitation.py`. `GT` get_by_token · `GP` get_pending_invitations · `UI` get_user_invitations · `CP` count_pending_invitations · `GA` get_all_invitations.

**Actors and fixed values.**
- `dao` = the singleton `workspace_invitation_dao` (`from app.dao.workspace_invitation import workspace_invitation_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `WorkspaceInvitation` = `app.models.workspace_invitation.WorkspaceInvitation`. `datetime`, `timedelta` = the `datetime` module's classes. `patch` = `unittest.mock.patch`.
- MISSING = `999999999`. NOW = `datetime(2026, 3, 5, 12, 0, 0)` (naive). US = `timedelta(microseconds=1)`. DAY = `timedelta(days=1)`. T1, T2, T3 = `datetime(2026, 3, 1, 9, 0, 0)`, `datetime(2026, 3, 2, 9, 0, 0)`, `datetime(2026, 3, 3, 9, 0, 0)`.
- TAG = `uuid.uuid4().hex[:12]`, computed once at the start of each test.

**Externals.** `app.dao.workspace_invitation.utcnow`: every When runs inside `with patch("app.dao.workspace_invitation.utcnow", return_value=NOW) as clock:`.

**Given rows.** Rows are inserted directly (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush.
- Standing rows, no Given line: W1, W2 = two `workspaces` rows from `make_workspace(db)`. No `workspace_invitations` row exists unless the card's Given lists it.
- **invitation X** = `WorkspaceInvitation(workspace_id=W1.id, email="a@x.com", role="member", token=f"tok-X-{TAG}", status="pending", expires_at=NOW + DAY)`, where `X` in the token is the row's own name (`f"tok-A-{TAG}"` for A). In a loop, row `Ek` has `token=f"tok-{k}-{TAG}"`. After the word "but" the card lists every column that differs.
- A Given line written as code is a step to run exactly as written. `db.add(...)` without `db.flush()` leaves the row pending; an attribute set "(not flushed)" stays an unflushed edit.

**Named checks.**
- **idset(result)** = `{r.id for r in result}`. **ids(result)** = `[r.id for r in result]` (order is part of the check).
- **re-read X** = `db.expire_all()`, then SELECT X by id.
- `pending:` / `session:` lines check `db.new`, `db.dirty`, `db.deleted` after the call, before anything expires the session.

**xfail cards.** Write the call and the checks exactly as shown. `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`. The assertion of a non-strict card is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded (a `before_cursor_execute` listener). `sql` = the text of the one `SELECT` from `workspace_invitations`; `order_part` = the text of `sql` after its first `ORDER BY` (`""` when there is none); `written` = every recorded `INSERT`, `UPDATE` or `DELETE`.

**Race simulations.** None in this module.

## `WorkspaceInvitationDAO.get_by_token`

### WSI-GT-01 — the row with that token is returned, whatever its state and workspace
- **Rules:** `get_by_token` R1, R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = invitation B.
2. A = invitation A, but `workspace_id W2.id`, `status "accepted"`, `expires_at NOW - DAY`.

**When**
- `result = dao.get_by_token(db, token=f"tok-A-{TAG}")`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. returns: `result.id == A.id`.
3. returns: `result.status == "accepted"`, `result.workspace_id == W2.id`.

### WSI-GT-02 — the token in capitals gives None
- **Rules:** `get_by_token` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = invitation A.

**When**
- `result = dao.get_by_token(db, token=f"tok-A-{TAG}".upper())`.

**Then**
1. returns: `result is None`.

### WSI-GT-03 — the token with a leading space gives None
- **Rules:** `get_by_token` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = invitation A.

**When**
- `result = dao.get_by_token(db, token=f" tok-A-{TAG}")`.

**Then**
1. returns: `result is None`.

### WSI-GT-04 — the start of a token gives None
- **Rules:** `get_by_token` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = invitation A.

**When**
- `result = dao.get_by_token(db, token="tok-A-")`.

**Then**
1. returns: `result is None`.

### WSI-GT-05 — _ is no wildcard in a token
- **Rules:** `get_by_token` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = invitation A.

**When**
- `result = dao.get_by_token(db, token=f"tok_A-{TAG}")`.

**Then**
1. returns: `result is None`.

### WSI-GT-06 — a stored token with a leading space is not found without it
- **Rules:** `get_by_token` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = invitation A, but `token f" tok-A-{TAG}"`.

**When**
- `result = dao.get_by_token(db, token=f"tok-A-{TAG}")`.

**Then**
1. returns: `result is None`.

### WSI-GT-07 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_token` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = invitation A.
2. B = invitation B, but `workspace_id W2.id`.
3. `P = WorkspaceInvitation(workspace_id=W1.id, email="p@x.com", role="member", token=f"tok-P-{TAG}", status="pending", expires_at=NOW + DAY)`
4. `db.add(P)` (not flushed).
5. `B.role = "admin"` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_token(db, token=f"tok-A-{TAG}")`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. session: `not db.deleted`.
7. statement: `written == []`.

## `WorkspaceInvitationDAO.get_pending_invitations`

### WSI-GP-01 — only rows with status exactly 'pending', not expired, of that workspace
- **Rules:** `get_pending_invitations` R1, R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = invitation A.
2. B = invitation B, but `status "Pending"`.
3. C = invitation C, but `status " pending"`.
4. D = invitation D, but `status "accepted"`.
5. E = invitation E, but `status "cancelled"`.
6. Z = invitation Z, but `workspace_id W2.id`.

**When**
- `result = dao.get_pending_invitations(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `idset(result) == {A.id}`.

### WSI-GP-02 — expiry: equal to now or earlier is left out, one microsecond later is kept
- **Rules:** `get_pending_invitations` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = invitation E, but `expires_at NOW`.
2. F = invitation F, but `expires_at NOW + US`.
3. G = invitation G, but `expires_at NOW - DAY`.

**When**
- `result = dao.get_pending_invitations(db, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {F.id}`.
2. re-read G: `status == "pending"`.

### WSI-GP-03 — workspace id 0 gives an empty list
- **Rules:** `get_pending_invitations` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = invitation A.

**When**
- `result = dao.get_pending_invitations(db, workspace_id=0)`.

**Then**
1. returns: `result == []`.

### WSI-GP-04 — no cap: 101 pending invitations give 101 rows
- **Rules:** `get_pending_invitations` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 invitations E1 … E101, built with `add_all`: Ek = invitation, `token f"tok-{k}-{TAG}"`.

**When**
- `result = dao.get_pending_invitations(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `idset(result) == {E1.id, …, E101.id}`.

### WSI-GP-05 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_pending_invitations` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = invitation A.
2. B = invitation B, but `workspace_id W2.id`.
3. `P = WorkspaceInvitation(workspace_id=W1.id, email="p@x.com", role="member", token=f"tok-P-{TAG}", status="pending", expires_at=NOW + DAY)`
4. `db.add(P)` (not flushed).
5. `B.role = "admin"` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_pending_invitations(db, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. session: `B in db.dirty`.
6. session: `len(db.dirty) == 1`.
7. session: `not db.deleted`.
8. statement: `written == []`.

### WSI-GP-06 — newest invitation first, and on a tie the higher id first
- **Rules:** `get_pending_invitations` R4 [BUG-1401]
- **Kind:** bug
- **Expect:** xfail BUG-1401 (non-strict)
- **Fails today on:** Then 2 (no `ORDER BY`; physical order is id order)

**Given**
1. A = invitation A, but `invited_at T2`.
2. B = invitation B, but `invited_at T3`.
3. C = invitation C, but `invited_at T1`.
4. D = invitation D, but `invited_at T3`.
5. `db.expire_all()`

**When**
- `result = dao.get_pending_invitations(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [D.id, B.id, A.id, C.id]`.

### WSI-GP-07 — the query orders by invited_at, then id, both descending
- **Rules:** `get_pending_invitations` R4 [BUG-1401]
- **Kind:** bug
- **Expect:** xfail BUG-1401
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = invitation A.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_pending_invitations(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"invited_at" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("invited_at") < order_part.index(".id")`.
6. statement: `order_part.upper().count("DESC") == 2`.
7. statement: `order_part.count(",") == 1`.

### WSI-GP-08 — rows past now are not kept by an expiry check in Python after the read
- **Rules:** `get_pending_invitations` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = invitation A, but `expires_at NOW + US`.
2. B = invitation B, but `expires_at NOW - US`.

**When**
- `result = dao.get_pending_invitations(db, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.
2. mock called: `clock.called is True`.

### WSI-GP-09 — a row of a workspace with a lower id is not returned
- **Rules:** `get_pending_invitations` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = invitation Z.
2. A = invitation A, but `workspace_id W2.id`.

**When**
- `result = dao.get_pending_invitations(db, workspace_id=W2.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.

## `WorkspaceInvitationDAO.get_user_invitations`

### WSI-UI-01 — pending, unexpired rows of that email from every workspace
- **Rules:** `get_user_invitations` R1, R2a, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = invitation A.
2. B = invitation B, but `workspace_id W2.id`.
3. C = invitation C, but `status "accepted"`.
4. D = invitation D, but `expires_at NOW`.
5. E = invitation E, but `email "a@y.com"`.
6. F = invitation F, but `expires_at NOW + US`.

**When**
- `result = dao.get_user_invitations(db, email="a@x.com")`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `idset(result) == {A.id, B.id, F.id}`.

### WSI-UI-02 — the email is matched ignoring case on the argument side
- **Rules:** `get_user_invitations` R2 [BUG-1402]
- **Kind:** bug
- **Expect:** xfail BUG-1402
- **Fails today on:** Then 2 (exact match: nothing is found)

**Given**
1. A = invitation A, but `email "john.doe@example.com"`.

**When**
- `result = dao.get_user_invitations(db, email="John.Doe@example.com")`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id]`.

### WSI-UI-03 — the email is matched ignoring surrounding spaces on the argument side
- **Rules:** `get_user_invitations` R2 [BUG-1402]
- **Kind:** bug
- **Expect:** xfail BUG-1402
- **Fails today on:** Then 2 (exact match: nothing is found)

**Given**
1. A = invitation A, but `email "john.doe@example.com"`.

**When**
- `result = dao.get_user_invitations(db, email=" john.doe@example.com ")`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id]`.

### WSI-UI-04 — a stored email with capitals is found by the lower-case one
- **Rules:** `get_user_invitations` R2 [BUG-1402]
- **Kind:** bug
- **Expect:** xfail BUG-1402
- **Fails today on:** Then 2 (exact match: nothing is found)

**Given**
1. A = invitation A, but `email "John.Doe@Example.com"`.

**When**
- `result = dao.get_user_invitations(db, email="john.doe@example.com")`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id]`.

### WSI-UI-05 — part of an email finds nothing
- **Rules:** `get_user_invitations` R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = invitation A, but `email "john.doe@example.com"`.

**When**
- `result = dao.get_user_invitations(db, email="doe@example.com")`.

**Then**
1. returns: `result == []`.

### WSI-UI-06 — _ is no wildcard in an email
- **Rules:** `get_user_invitations` R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = invitation A, but `email "john.doe@example.com"`.

**When**
- `result = dao.get_user_invitations(db, email="john_doe@example.com")`.

**Then**
1. returns: `result == []`.

### WSI-UI-07 — no cap: 101 invitations to one email give 101 rows
- **Rules:** `get_user_invitations` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 invitations E1 … E101, built with `add_all`: Ek = invitation, `token f"tok-{k}-{TAG}"`.

**When**
- `result = dao.get_user_invitations(db, email="a@x.com")`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `idset(result) == {E1.id, …, E101.id}`.

### WSI-UI-08 — newest invitation first, and on a tie the higher id first
- **Rules:** `get_user_invitations` R4 [BUG-1401]
- **Kind:** bug
- **Expect:** xfail BUG-1401 (non-strict)
- **Fails today on:** Then 2 (no `ORDER BY`; physical order is id order)

**Given**
1. A = invitation A, but `invited_at T2`.
2. B = invitation B, but `workspace_id W2.id`, `invited_at T3`.
3. C = invitation C, but `invited_at T1`.
4. D = invitation D, but `invited_at T3`.
5. `db.expire_all()`

**When**
- `result = dao.get_user_invitations(db, email="a@x.com")`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [D.id, B.id, A.id, C.id]`.

### WSI-UI-09 — the query orders by invited_at, then id, both descending
- **Rules:** `get_user_invitations` R4 [BUG-1401]
- **Kind:** bug
- **Expect:** xfail BUG-1401
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = invitation A.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_user_invitations(db, email="a@x.com")`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"invited_at" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("invited_at") < order_part.index(".id")`.
6. statement: `order_part.upper().count("DESC") == 2`.
7. statement: `order_part.count(",") == 1`.

### WSI-UI-10 — an email of no invitation gives an empty list
- **Rules:** `get_user_invitations` R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = invitation A.

**When**
- `result = dao.get_user_invitations(db, email="nobody@x.com")`.

**Then**
1. returns: `result == []`.

### WSI-UI-11 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_user_invitations` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = invitation A.
2. B = invitation B, but `email "b@x.com"`.
3. `P = WorkspaceInvitation(workspace_id=W1.id, email="a@x.com", role="member", token=f"tok-P-{TAG}", status="pending", expires_at=NOW + DAY)`
4. `db.add(P)` (not flushed).
5. `B.role = "admin"` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_user_invitations(db, email="a@x.com")`.

**Then**
1. returns: `idset(result) == {A.id}`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. session: `B in db.dirty`.
6. session: `len(db.dirty) == 1`.
7. session: `not db.deleted`.
8. statement: `written == []`.

### WSI-UI-12 — only status exactly 'pending': 'Pending', ' pending' and 'cancelled' are left out
- **Rules:** `get_user_invitations` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = invitation A.
2. B = invitation B, but `status "Pending"`.
3. C = invitation C, but `status " pending"`.
4. D = invitation D, but `status "cancelled"`.

**When**
- `result = dao.get_user_invitations(db, email="a@x.com")`.

**Then**
1. returns: `idset(result) == {A.id}`.

### WSI-UI-13 — a stored email with a leading space is found by the plain one
- **Rules:** `get_user_invitations` R2 [BUG-1402]
- **Kind:** bug
- **Expect:** xfail BUG-1402
- **Fails today on:** Then 2 (exact match: nothing is found)

**Given**
1. A = invitation A, but `email " john.doe@example.com"`.

**When**
- `result = dao.get_user_invitations(db, email="john.doe@example.com")`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id]`.

## `WorkspaceInvitationDAO.count_pending_invitations`

### WSI-CP-01 — counts the pending, unexpired rows of the workspace, one per row
- **Rules:** `count_pending_invitations` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = invitation A.
2. B = invitation B.
3. C = invitation C, but `status "Pending"`.
4. D = invitation D, but `status "accepted"`.
5. E = invitation E, but `expires_at NOW`.
6. F = invitation F, but `email "b@x.com"`, `expires_at NOW + US`.
7. Z = invitation Z, but `workspace_id W2.id`.

**When**
- `result = dao.count_pending_invitations(db, workspace_id=W1.id)`.

**Then**
1. returns: `type(result) is int`.
2. returns: `result == 3`.

### WSI-CP-02 — none pending gives 0
- **Rules:** `count_pending_invitations` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. D = invitation D, but `status "accepted"`.
2. E = invitation E, but `expires_at NOW - DAY`.

**When**
- `result = dao.count_pending_invitations(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 0`.

### WSI-CP-03 — workspace id 0 gives 0
- **Rules:** `count_pending_invitations` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = invitation A.

**When**
- `result = dao.count_pending_invitations(db, workspace_id=0)`.

**Then**
1. returns: `result == 0`.

### WSI-CP-04 — writes nothing: a pending row stays pending and is not counted
- **Rules:** `count_pending_invitations` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = invitation A.
2. B = invitation B, but `workspace_id W2.id`.
3. `P = WorkspaceInvitation(workspace_id=W1.id, email="p@x.com", role="member", token=f"tok-P-{TAG}", status="pending", expires_at=NOW + DAY)`
4. `db.add(P)` (not flushed).
5. `B.role = "admin"` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.count_pending_invitations(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 1`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. statement: `written == []`.

### WSI-CP-05 — a status with a leading space is not counted
- **Rules:** `count_pending_invitations` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = invitation A.
2. C = invitation C, but `status " pending"`.

**When**
- `result = dao.count_pending_invitations(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 1`.

### WSI-CP-06 — a row of a workspace with a lower id is not counted
- **Rules:** `count_pending_invitations` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = invitation Z.
2. A = invitation A, but `workspace_id W2.id`.

**When**
- `result = dao.count_pending_invitations(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == 1`.

## `WorkspaceInvitationDAO.get_all_invitations`

### WSI-GA-01 — every row of the workspace whatever its state, none of another
- **Rules:** `get_all_invitations` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = invitation A.
2. B = invitation B, but `expires_at NOW - DAY`.
3. C = invitation C, but `status "accepted"`.
4. D = invitation D, but `status "cancelled"`.
5. E = invitation E, but `status "whatever"`.
6. Z = invitation Z, but `workspace_id W2.id`.

**When**
- `result = dao.get_all_invitations(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `idset(result) == {A.id, B.id, C.id, D.id, E.id}`.

### WSI-GA-02 — the clock is not read
- **Rules:** `get_all_invitations` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = invitation A, but `expires_at NOW - DAY`.

**When**
- `result = dao.get_all_invitations(db, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.
2. mock called: `clock.called is False`.

### WSI-GA-03 — workspace id 0 gives an empty list
- **Rules:** `get_all_invitations` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = invitation A.

**When**
- `result = dao.get_all_invitations(db, workspace_id=0)`.

**Then**
1. returns: `result == []`.

### WSI-GA-04 — no cap: 101 invitations give 101 rows
- **Rules:** `get_all_invitations` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 invitations E1 … E101, built with `add_all`: Ek = invitation, `token f"tok-{k}-{TAG}"`, `status "accepted"`.

**When**
- `result = dao.get_all_invitations(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `idset(result) == {E1.id, …, E101.id}`.

### WSI-GA-05 — newest invitation first, and on a tie the higher id first
- **Rules:** `get_all_invitations` R3 [BUG-1401]
- **Kind:** bug
- **Expect:** xfail BUG-1401 (non-strict)
- **Fails today on:** Then 2 (no `ORDER BY`; physical order is id order)

**Given**
1. A = invitation A, but `invited_at T2`, `status "accepted"`.
2. B = invitation B, but `invited_at T3`.
3. C = invitation C, but `invited_at T1`, `expires_at NOW - DAY`.
4. D = invitation D, but `invited_at T3`, `status "cancelled"`.
5. `db.expire_all()`

**When**
- `result = dao.get_all_invitations(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [D.id, B.id, A.id, C.id]`.

### WSI-GA-06 — the query orders by invited_at, then id, both descending
- **Rules:** `get_all_invitations` R3 [BUG-1401]
- **Kind:** bug
- **Expect:** xfail BUG-1401
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = invitation A.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_all_invitations(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"invited_at" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("invited_at") < order_part.index(".id")`.
6. statement: `order_part.upper().count("DESC") == 2`.
7. statement: `order_part.count(",") == 1`.

### WSI-GA-07 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_all_invitations` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = invitation A.
2. B = invitation B, but `workspace_id W2.id`.
3. `P = WorkspaceInvitation(workspace_id=W1.id, email="p@x.com", role="member", token=f"tok-P-{TAG}", status="pending", expires_at=NOW + DAY)`
4. `db.add(P)` (not flushed).
5. `B.role = "admin"` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_all_invitations(db, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. session: `not db.deleted`.
7. statement: `written == []`.

### WSI-GA-08 — a row of a workspace with a lower id is not returned
- **Rules:** `get_all_invitations` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = invitation Z.
2. A = invitation A, but `workspace_id W2.id`.

**When**
- `result = dao.get_all_invitations(db, workspace_id=W2.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| FU-1 — two pending invitations to one email take two seats (OQ-3) | `WorkspaceManager.create_invitation` | Owner question; CP-01 holds today's DAO count of 2 for one email. |
| FU-2 — accept uses `expires_at < now`, the lists `<=` | `WorkspaceManager.validate_invitation_for_user` | The one-microsecond difference, noted. |
| FU-3 — lists invitations to workspaces the user already belongs to | `WorkspaceService.get_my_invitations` | That review's call. |
| Lower-casing the email on create | `WorkspaceManager.create_invitation` | `email.lower()` is the manager's. |
| Whether account emails are case-insensitive (OQ-1) | profile DAO / owner | Not a dependency of BUG-1402. |
| Inherited `BaseDAO` methods and the singleton (`create`, unique `token`, `get`) | `tests/unit/dao/base.cases.md` | Not repeated here (step 1a). |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Model facts | `role` is free text; no typical value. | Conventions use `"member"`, `"admin"`. |
| 2 | `get_pending_invitations` R1 | Whether `utcnow()` is called once per query or not at all when there are no rows is not said. | WSI-GP-08 only checks the clock was read (`clock.called is True`), not how often. |
| 3 | Model facts: `invited_at` default | Whether the patched `app.dao.workspace_invitation.utcnow` reaches the model default is not said. | Order cards give `invited_at` explicitly; no card relies on the default. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_token` | Returns | WSI-GT-01 |
| `get_by_token` | R1 | WSI-GT-01 |
| `get_by_token` | R2 | WSI-GT-01, WSI-GT-02, WSI-GT-03, WSI-GT-04, WSI-GT-05, WSI-GT-06 |
| `get_by_token` | Side effects | WSI-GT-07 |
| `get_pending_invitations` | Returns | WSI-GP-01 |
| `get_pending_invitations` | R1 | WSI-GP-01, WSI-GP-08 |
| `get_pending_invitations` | R2 | WSI-GP-02 |
| `get_pending_invitations` | R3 | WSI-GP-01, WSI-GP-03, WSI-GP-04, WSI-GP-09 |
| `get_pending_invitations` | R4 [BUG-1401] | WSI-GP-06, WSI-GP-07 |
| `get_pending_invitations` | Side effects | WSI-GP-05 |
| `get_user_invitations` | Returns | WSI-UI-01 |
| `get_user_invitations` | R1 | WSI-UI-01, WSI-UI-12 |
| `get_user_invitations` | R2 [BUG-1402] | WSI-UI-02, WSI-UI-03, WSI-UI-04, WSI-UI-13 |
| `get_user_invitations` | R2a | WSI-UI-01, WSI-UI-05, WSI-UI-06, WSI-UI-10 |
| `get_user_invitations` | R3 | WSI-UI-07 |
| `get_user_invitations` | R4 [BUG-1401] | WSI-UI-08, WSI-UI-09 |
| `get_user_invitations` | Side effects | WSI-UI-11 |
| `count_pending_invitations` | Returns | WSI-CP-01 |
| `count_pending_invitations` | R1 | WSI-CP-01, WSI-CP-05, WSI-CP-06 |
| `count_pending_invitations` | R2 | WSI-CP-02, WSI-CP-03 |
| `count_pending_invitations` | Side effects | WSI-CP-04 |
| `get_all_invitations` | Returns | WSI-GA-01 |
| `get_all_invitations` | R1 | WSI-GA-01, WSI-GA-03, WSI-GA-08 |
| `get_all_invitations` | R2 | WSI-GA-02, WSI-GA-04 |
| `get_all_invitations` | R3 [BUG-1401] | WSI-GA-05, WSI-GA-06 |
| `get_all_invitations` | Side effects | WSI-GA-07 |
