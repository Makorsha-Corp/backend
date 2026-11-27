# Test cases — `app/dao/refresh_token.py`

> **Spec:** `tests/unit/dao/refresh_token.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). P1, Q1–Q3 were decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. Additive, from `refresh_token.verify.md` (case-missing Findings 1, 2; recipes R-1, R-2): R-1 → RT-RA-07 (the other user at the lower id); R-2 → RT-TL-03 (an unrevoked row stays unrevoked). The two surviving mutants are on `get_by_id`, dead code (Q3): no card. No existing card, Convention or ID changed; none retired.
> **Counts:** 51 cases · 49 expected-to-pass · 2 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Per callable:** `get_by_hash` 8 · `create` 15 (2 bug) · `revoke` 9 · `revoke_family` 9 · `revoke_all_for_user` 7 · `touch_last_used` 3.
- **Revision 1:** "revoke all" is held against an earlier user's sessions too (RA-07, security); `touch_last_used` never revokes (TL-03).
- **Depth:** lighter target (skill step 1a) on the reads and the plain writes; it writes no stock, money or order state. `revoke` carries the one real decision (stamp once, successor always) and has a card for each side of it.
- **Expected-to-fail:** BUG-1407 2, both strict (deterministic today): CR-11 (user agent 513 → 512), CR-12 (IP 65 → 64). CR-13 is the passing companion at exactly 512 / 64.
- **Commit spies:** one per writer — CR-15, RV-09, RF-09, RA-06, TL-02. Each reads the change with raw SQL inside a savepoint, rolls back, and checks the spy.
- **Notable design choices:**
  - `utcnow` is patched to NOW around every When; `issued_at` (model default, not patchable) is checked against a real clock window of ±5 s. The columns are `timestamp without time zone`, so no card depends on the session time zone.
  - Hashes and families carry a per-test value, so concurrent tests never wait on the unique hash index.
  - RV-06, RF-08, RA-05 hold the stale-copy rules: the session's loaded copy keeps its old `revoked_at`, and `revoke` writes over the database's stamp. These describe today's behaviour as a rule (FU-1 (b) in the auth service).
  - Exact compare of the hash: argument side (capitals, leading space, a part, `_`) and stored side (leading space). On `revoke_family`, capitals and a part only (the family is a random UUID; step 1a).
  - No `Author:` lines (caller's instruction). Race simulations: none (the HR-10 race is the auth service's, FU-1 (a)).
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `RT` = `app/dao/refresh_token.py`. `GH` get_by_hash · `CR` create · `RV` revoke · `RF` revoke_family · `RA` revoke_all_for_user · `TL` touch_last_used.

**Actors and fixed values.**
- `dao` = the singleton `refresh_token_dao` (`from app.dao.refresh_token import refresh_token_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword unless the card says "positional". `result` = what the When call returns.
- `RefreshToken` = `app.models.refresh_token.RefreshToken`. `text` = `sqlalchemy.text`. `datetime`, `timedelta`, `timezone` = the `datetime` module's classes. `DataError`, `IntegrityError` = from `sqlalchemy.exc`. `patch` = `unittest.mock.patch`.
- MISSING = `999999999`. NOW = `datetime(2026, 3, 5, 12, 0, 0)`. EARLY = `datetime(2026, 3, 1, 8, 0, 0)`. PAST = `datetime(2026, 3, 4, 12, 0, 0)`. LATER = `datetime(2026, 4, 5, 12, 0, 0)`. SLACK = `timedelta(seconds=5)`.
- TAG = `uuid.uuid4().hex`, once per test. H1 … H9 = `f"a{k}" + (TAG + TAG)[:62]` for k = 1 … 9: 64-character lower-case hashes, unique per test. FAM1, FAM2 = `str(uuid.uuid4())` each, once per test.

**Externals.** `app.dao.refresh_token.utcnow`: every When runs inside `with patch("app.dao.refresh_token.utcnow", return_value=NOW):`.

**Given rows.** Rows are inserted directly (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush.
- Standing rows, no Given line: W1, W2 = two `workspaces` rows from `make_workspace(db)`; U1, U2 = two `profiles` rows from `make_profile(db)`. No `refresh_tokens` row exists unless the card's Given lists it; no `workspace_members` row exists.
- **token** = `RefreshToken(user_id=U1.id, token_hash=…, family_id=FAM1, expires_at=LATER)`; the card always gives `token_hash`; after the word "but" it lists every other column that differs.
- A Given line written as code is a step to run exactly as written. `db.add(...)` without `db.flush()` leaves the row pending; an attribute set "(not flushed)" stays an unflushed edit.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id.
- **raw(X, col)** = `db.execute(text(f"SELECT {col} FROM refresh_tokens WHERE id = :id"), {"id": X.id}).scalar()` — the database value, without touching the session.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot after the last Given line). **unchanged(X) except `c`** = the same, leaving out column `c`.
- **nothing written** = the number of `refresh_tokens` rows stored equals its value before the call.
- **clock window** = `before = datetime.now(timezone.utc).replace(tzinfo=None)` is the last step before the When; `after` = the same expression, the first step after it.
- `raises: <DB error>` = `with pytest.raises(<type>) as exc:` then `with db.begin_nested():` then the When; further `raises:` lines assert on `exc.value`, after the block. `raises: TypeError` = plain `pytest.raises(TypeError)`.
- **rolled back** = `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.
- `pending:` / `session:` lines check `db.new`, `db.dirty`, `db.deleted` or an attribute of a loaded object, after the call, before anything expires or refreshes the session; keep the card's order.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`. Write the call and the checks exactly as shown.

**Statement recorder.** The SQL statements the session sends during the When are recorded (a `before_cursor_execute` listener). `written` = every recorded `INSERT`, `UPDATE` or `DELETE`.

**Race simulations.** None in this module.

## `RefreshTokenDAO.get_by_hash`

### RT-GH-01 — the row with that hash is returned, whatever its state and user
- **Rules:** `get_by_hash` R1, R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = token, `token_hash H2`.
2. A = token, `token_hash H1`, but `user_id U2.id`, `workspace_id W2.id`, `expires_at PAST`, `revoked_at EARLY`, `replaced_by_id B.id`.

**When**
- `result = dao.get_by_hash(db, token_hash=H1)`.

**Then**
1. returns: `isinstance(result, RefreshToken)`.
2. returns: `result.id == A.id`.
3. returns: `result.user_id == U2.id`, `result.revoked_at == EARLY`, `result.replaced_by_id == B.id`.

### RT-GH-02 — the hash in capitals gives None
- **Rules:** `get_by_hash` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.

**When**
- `result = dao.get_by_hash(db, token_hash=H1.upper())`.

**Then**
1. returns: `result is None`.

### RT-GH-03 — an empty hash gives None
- **Rules:** `get_by_hash` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.

**When**
- `result = dao.get_by_hash(db, token_hash="")`.

**Then**
1. returns: `result is None`.

### RT-GH-04 — the first 63 characters of a hash give None
- **Rules:** `get_by_hash` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.

**When**
- `result = dao.get_by_hash(db, token_hash=H1[:63])`.

**Then**
1. returns: `result is None`.

### RT-GH-05 — the hash with a leading space gives None
- **Rules:** `get_by_hash` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.

**When**
- `result = dao.get_by_hash(db, token_hash=" " + H1)`.

**Then**
1. returns: `result is None`.

### RT-GH-06 — _ is no wildcard in a hash
- **Rules:** `get_by_hash` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.

**When**
- `result = dao.get_by_hash(db, token_hash=H1[:5] + "_" + H1[6:])`.

**Then**
1. returns: `result is None`.

### RT-GH-07 — a stored hash with a leading space is not found without it
- **Rules:** `get_by_hash` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = token, `token_hash " " + H1[:63]`.

**When**
- `result = dao.get_by_hash(db, token_hash=H1[:63])`.

**Then**
1. returns: `result is None`.

### RT-GH-08 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_hash` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.
2. B = token, `token_hash H2`.
3. `P = RefreshToken(user_id=U1.id, token_hash=H3, family_id=FAM1, expires_at=LATER)`
4. `db.add(P)` (not flushed).
5. `B.user_agent = "edited"` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_hash(db, token_hash=H1)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. session: `not db.deleted`.
7. statement: `written == []`.

## `RefreshTokenDAO.create`

### RT-CR-01 — one row with the given values; issued_at now; revoked, successor and last use empty
- **Rules:** `create` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. clock window: `before` is read here.

**When**
- `result = dao.create(db, user_id=U1.id, token_hash=H1, family_id=FAM1, expires_at=LATER, workspace_id=W1.id, user_agent="Mozilla/5.0", ip_address="10.0.0.1")`, then `after` is read.

**Then**
1. returns: `isinstance(result, RefreshToken)`.
2. returns: `result.id is not None`.
3. re-read result: `user_id == U1.id`, `token_hash == H1`, `family_id == FAM1`, `expires_at == LATER`.
4. re-read result: `workspace_id == W1.id`, `user_agent == "Mozilla/5.0"`, `ip_address == "10.0.0.1"`.
5. re-read result: `revoked_at is None`, `replaced_by_id is None`, `last_used_at is None`.
6. re-read result: `before - SLACK <= issued_at <= after + SLACK`.

### RT-CR-02 — optional values not given are stored NULL
- **Rules:** `create` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No `refresh_tokens` row.

**When**
- `result = dao.create(db, user_id=U1.id, token_hash=H1, family_id=FAM1, expires_at=LATER)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `workspace_id is None`, `user_agent is None`, `ip_address is None`.

### RT-CR-03 — a past expiry and a workspace the user is not a member of are stored
- **Rules:** `create` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. U1 has no `workspace_members` row.

**When**
- `result = dao.create(db, user_id=U1.id, token_hash=H1, family_id=FAM1, expires_at=PAST, workspace_id=W2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `expires_at == PAST`, `workspace_id == W2.id`.

### RT-CR-04 — a taken hash raises IntegrityError 23505 and writes nothing
- **Rules:** `create` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.

**When**
- `dao.create(db, user_id=U2.id, token_hash=H1, family_id=FAM2, expires_at=LATER)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. nothing written: nothing written.

### RT-CR-05 — a 65-character hash raises DataError 22001
- **Rules:** `create` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No `refresh_tokens` row.

**When**
- `dao.create(db, user_id=U1.id, token_hash=H1 + "b", family_id=FAM1, expires_at=LATER)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "22001"`.
3. nothing written: nothing written.

### RT-CR-06 — a 37-character family raises DataError 22001
- **Rules:** `create` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No `refresh_tokens` row.

**When**
- `dao.create(db, user_id=U1.id, token_hash=H1, family_id=FAM1 + "x", expires_at=LATER)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "22001"`.
3. nothing written: nothing written.

### RT-CR-07 — an unknown user raises IntegrityError 23503
- **Rules:** `create` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No `refresh_tokens` row.

**When**
- `dao.create(db, user_id=MISSING, token_hash=H1, family_id=FAM1, expires_at=LATER)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. nothing written: nothing written.

### RT-CR-08 — an unknown workspace raises IntegrityError 23503
- **Rules:** `create` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No `refresh_tokens` row.

**When**
- `dao.create(db, user_id=U1.id, token_hash=H1, family_id=FAM1, expires_at=LATER, workspace_id=MISSING)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. nothing written: nothing written.

### RT-CR-09 — expires_at=None raises IntegrityError 23502
- **Rules:** `create` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No `refresh_tokens` row.

**When**
- `dao.create(db, user_id=U1.id, token_hash=H1, family_id=FAM1, expires_at=None)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23502"`.
3. nothing written: nothing written.

### RT-CR-10 — positional arguments raise TypeError
- **Rules:** `create` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No `refresh_tokens` row.

**When**
- `dao.create(db, U1.id, H1, FAM1, LATER)` (positional), inside `raises: TypeError`.

**Then**
1. raises: `TypeError`.
2. nothing written: nothing written.

### RT-CR-11 — a user agent of 513 characters is cut to 512 and the row is written
- **Rules:** `create` R4 [BUG-1407]
- **Kind:** bug
- **Expect:** xfail BUG-1407
- **Fails today on:** Then 1 (the call raises DataError: 513 characters do not fit `VARCHAR(512)`)

**Given**
1. No `refresh_tokens` row.

**When**
- inside `with db.begin_nested():` — `result = dao.create(db, user_id=U1.id, token_hash=H1, family_id=FAM1, expires_at=LATER, user_agent="u" * 513)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `user_agent == "u" * 512`.

### RT-CR-12 — an IP address of 65 characters is cut to 64 and the row is written
- **Rules:** `create` R4 [BUG-1407]
- **Kind:** bug
- **Expect:** xfail BUG-1407
- **Fails today on:** Then 1 (the call raises DataError: 65 characters do not fit `VARCHAR(64)`)

**Given**
1. No `refresh_tokens` row.

**When**
- inside `with db.begin_nested():` — `result = dao.create(db, user_id=U1.id, token_hash=H1, family_id=FAM1, expires_at=LATER, ip_address="1" * 65)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `ip_address == "1" * 64`.

### RT-CR-13 — a user agent of exactly 512 and an IP of exactly 64 characters are stored whole
- **Rules:** `create` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No `refresh_tokens` row.

**When**
- `result = dao.create(db, user_id=U1.id, token_hash=H1, family_id=FAM1, expires_at=LATER, user_agent="u" * 512, ip_address="1" * 64)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `user_agent == "u" * 512`, `ip_address == "1" * 64`.

### RT-CR-14 — two creates in one family both stand
- **Rules:** `create` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.

**When**
- `result = dao.create(db, user_id=U1.id, token_hash=H2, family_id=FAM1, expires_at=LATER)`.

**Then**
1. returns: `result.id != A.id`.
2. count: `refresh_tokens` has exactly 2 rows with `family_id == FAM1`.
3. unchanged: unchanged(A).

### RT-CR-15 — the row is flushed, not committed
- **Rules:** `create` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No `refresh_tokens` row.
2. Savepoint and commit spy per **rolled back**.

**When**
- `result = dao.create(db, user_id=U1.id, token_hash=H1, family_id=FAM1, expires_at=LATER)`.

**Then**
1. returns: `result.id is not None`.
2. count: inside the savepoint, `refresh_tokens` has exactly 1 row with `token_hash == H1` (raw `SELECT count(*)`).
3. count: after the savepoint rollback, `refresh_tokens` has exactly 0 rows with `token_hash == H1`.
4. mock called: the `db.commit` spy was never called.

## `RefreshTokenDAO.revoke`

### RT-RV-01 — an unrevoked row is stamped now; with no successor given, replaced_by_id stays empty
- **Rules:** `revoke` R1, R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.

**When**
- `result = dao.revoke(db, row=A)`.

**Then**
1. returns: `result is None`.
2. re-read A: `revoked_at == NOW`, `replaced_by_id is None`.

### RT-RV-02 — a row already revoked keeps its first stamp
- **Rules:** `revoke` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`, but `revoked_at EARLY`.

**When**
- `result = dao.revoke(db, row=A)`.

**Then**
1. returns: `result is None`.
2. re-read A: `revoked_at == EARLY`.

### RT-RV-03 — a successor given is written
- **Rules:** `revoke` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.
2. B = token, `token_hash H2`.

**When**
- `result = dao.revoke(db, row=A, replaced_by_id=B.id)`.

**Then**
1. returns: `result is None`.
2. re-read A: `revoked_at == NOW`, `replaced_by_id == B.id`.
3. unchanged: unchanged(B).

### RT-RV-04 — on a row already revoked, a new successor replaces the first; the stamp stays
- **Rules:** `revoke` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. B = token, `token_hash H2`.
2. C = token, `token_hash H3`.
3. A = token, `token_hash H1`, but `revoked_at EARLY`, `replaced_by_id B.id`.

**When**
- `result = dao.revoke(db, row=A, replaced_by_id=C.id)`.

**Then**
1. returns: `result is None`.
2. re-read A: `replaced_by_id == C.id`, `revoked_at == EARLY`.

### RT-RV-05 — replaced_by_id=None leaves an existing successor in place
- **Rules:** `revoke` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. B = token, `token_hash H2`.
2. A = token, `token_hash H1`, but `replaced_by_id B.id`.

**When**
- `result = dao.revoke(db, row=A, replaced_by_id=None)`.

**Then**
1. returns: `result is None`.
2. re-read A: `replaced_by_id == B.id`, `revoked_at == NOW`.

### RT-RV-06 — a stale session copy: the database's stamp is overwritten
- **Rules:** `revoke` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.
2. `db.execute(text("UPDATE refresh_tokens SET revoked_at = :t WHERE id = :id"), {"t": EARLY, "id": A.id})` (the session copy of A is not expired).

**When**
- `result = dao.revoke(db, row=A)`.

**Then**
1. returns: `result is None`.
2. re-read A: `revoked_at == NOW`.

### RT-RV-07 — an unknown successor raises IntegrityError 23503 and the row keeps no stamp
- **Rules:** `revoke` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.

**When**
- `dao.revoke(db, row=A, replaced_by_id=MISSING)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. re-read A: `revoked_at is None`, `replaced_by_id is None`.

### RT-RV-08 — deleting the successor later sets replaced_by_id to NULL
- **Rules:** `revoke` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. B = token, `token_hash H2`.
2. A = token, `token_hash H1`, but `revoked_at EARLY`, `replaced_by_id B.id`.

**When**
- `db.execute(text("DELETE FROM refresh_tokens WHERE id = :id"), {"id": B.id})`.

**Then**
1. count: `refresh_tokens` has exactly 0 rows with `id == B.id`.
2. re-read A: `replaced_by_id is None`, `revoked_at == EARLY`.

### RT-RV-09 — the change is flushed, not committed
- **Rules:** `revoke` R4, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.
2. B = token, `token_hash H2`.
3. Savepoint and commit spy per **rolled back**.

**When**
- `result = dao.revoke(db, row=A, replaced_by_id=B.id)`.

**Then**
1. returns: `result is None`.
2. re-read A: inside the savepoint, `raw(A, "revoked_at") == NOW`.
3. re-read A: inside the savepoint, `raw(A, "replaced_by_id") == B.id`.
4. re-read A: after the savepoint rollback, `raw(A, "revoked_at") is None`.
5. mock called: the `db.commit` spy was never called.

## `RefreshTokenDAO.revoke_family`

### RT-RF-01 — every unrevoked row of the family is stamped, expired ones too; revoked ones keep theirs
- **Rules:** `revoke_family` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.
2. B = token, `token_hash H2`, but `expires_at PAST`.
3. C = token, `token_hash H3`, but `revoked_at EARLY`.

**When**
- `result = dao.revoke_family(db, family_id=FAM1)`.

**Then**
1. returns: `result == 2`.
2. re-read A: `revoked_at == NOW`.
3. re-read B: `revoked_at == NOW`.
4. re-read C: `revoked_at == EARLY`.

### RT-RF-02 — rows of every user in the family are stamped; other families are untouched
- **Rules:** `revoke_family` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E = token, `token_hash H5`, but `family_id FAM2`.
2. A = token, `token_hash H1`.
3. D = token, `token_hash H4`, but `user_id U2.id`.

**When**
- `result = dao.revoke_family(db, family_id=FAM1)`.

**Then**
1. returns: `result == 2`.
2. re-read A: `revoked_at == NOW`.
3. re-read D: `revoked_at == NOW`.
4. unchanged: unchanged(E).

### RT-RF-03 — an unknown family gives 0
- **Rules:** `revoke_family` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.

**When**
- `result = dao.revoke_family(db, family_id=FAM2)`.

**Then**
1. returns: `result == 0`.
2. unchanged: unchanged(A).

### RT-RF-04 — an empty family gives 0
- **Rules:** `revoke_family` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.

**When**
- `result = dao.revoke_family(db, family_id="")`.

**Then**
1. returns: `result == 0`.
2. unchanged: unchanged(A).

### RT-RF-05 — a family with nothing left to revoke gives 0, as a second call would
- **Rules:** `revoke_family` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`, but `revoked_at EARLY`.
2. B = token, `token_hash H2`, but `revoked_at EARLY`.

**When**
- `result = dao.revoke_family(db, family_id=FAM1)`.

**Then**
1. returns: `result == 0`.
2. re-read A: `revoked_at == EARLY`.
3. re-read B: `revoked_at == EARLY`.

### RT-RF-06 — the family in capitals matches nothing
- **Rules:** `revoke_family` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.

**When**
- `result = dao.revoke_family(db, family_id=FAM1.upper())`.

**Then**
1. returns: `result == 0`.
2. unchanged: unchanged(A).

### RT-RF-07 — part of a family matches nothing
- **Rules:** `revoke_family` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.

**When**
- `result = dao.revoke_family(db, family_id=FAM1[:8])`.

**Then**
1. returns: `result == 0`.
2. unchanged: unchanged(A).

### RT-RF-08 — a row loaded in the session keeps its old revoked_at until refreshed
- **Rules:** `revoke_family` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.

**When**
- `result = dao.revoke_family(db, family_id=FAM1)`.

**Then**
1. returns: `result == 1`.
2. session: `A.revoked_at is None` (read without refreshing).
3. re-read A: `revoked_at == NOW`.

### RT-RF-09 — the update is flushed, not committed
- **Rules:** `revoke_family` R4, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.
2. Savepoint and commit spy per **rolled back**.

**When**
- `result = dao.revoke_family(db, family_id=FAM1)`.

**Then**
1. returns: `result == 1`.
2. re-read A: inside the savepoint, `raw(A, "revoked_at") == NOW`.
3. re-read A: after the savepoint rollback, `raw(A, "revoked_at") is None`.
4. mock called: the `db.commit` spy was never called.

## `RefreshTokenDAO.revoke_all_for_user`

### RT-RA-01 — every unrevoked row of the user is stamped, whatever family, workspace or expiry
- **Rules:** `revoke_all_for_user` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.
2. B = token, `token_hash H2`, but `family_id FAM2`, `workspace_id W2.id`.
3. C = token, `token_hash H3`, but `expires_at PAST`.
4. D = token, `token_hash H4`, but `revoked_at EARLY`.

**When**
- `result = dao.revoke_all_for_user(db, user_id=U1.id)`.

**Then**
1. returns: `result == 3`.
2. re-read A: `revoked_at == NOW`.
3. re-read B: `revoked_at == NOW`.
4. re-read C: `revoked_at == NOW`.
5. re-read D: `revoked_at == EARLY`.

### RT-RA-02 — rows of another user are untouched
- **Rules:** `revoke_all_for_user` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = token, `token_hash H5`, but `user_id U2.id`.
2. A = token, `token_hash H1`.

**When**
- `result = dao.revoke_all_for_user(db, user_id=U1.id)`.

**Then**
1. returns: `result == 1`.
2. re-read A: `revoked_at == NOW`.
3. unchanged: unchanged(X).

### RT-RA-03 — user id 0 gives 0
- **Rules:** `revoke_all_for_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.

**When**
- `result = dao.revoke_all_for_user(db, user_id=0)`.

**Then**
1. returns: `result == 0`.
2. unchanged: unchanged(A).

### RT-RA-04 — nothing left to revoke gives 0
- **Rules:** `revoke_all_for_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`, but `revoked_at EARLY`.

**When**
- `result = dao.revoke_all_for_user(db, user_id=U1.id)`.

**Then**
1. returns: `result == 0`.
2. re-read A: `revoked_at == EARLY`.

### RT-RA-05 — a row loaded in the session keeps its old revoked_at until refreshed
- **Rules:** `revoke_all_for_user` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.

**When**
- `result = dao.revoke_all_for_user(db, user_id=U1.id)`.

**Then**
1. returns: `result == 1`.
2. session: `A.revoked_at is None` (read without refreshing).
3. re-read A: `revoked_at == NOW`.

### RT-RA-06 — the update is flushed, not committed
- **Rules:** `revoke_all_for_user` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.
2. Savepoint and commit spy per **rolled back**.

**When**
- `result = dao.revoke_all_for_user(db, user_id=U1.id)`.

**Then**
1. returns: `result == 1`.
2. re-read A: inside the savepoint, `raw(A, "revoked_at") == NOW`.
3. re-read A: after the savepoint rollback, `raw(A, "revoked_at") is None`.
4. mock called: the `db.commit` spy was never called.

### RT-RA-07 — rows of another user with a lower id are untouched
- **Rules:** `revoke_all_for_user` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = token, `token_hash H5`.
2. A = token, `token_hash H1`, but `user_id U2.id`.

**When**
- `result = dao.revoke_all_for_user(db, user_id=U2.id)`.

**Then**
1. returns: `result == 1`.
2. re-read A: `revoked_at == NOW`.
3. unchanged: unchanged(X).

## `RefreshTokenDAO.touch_last_used`

### RT-TL-01 — last_used_at is replaced by now; a revoked row stays revoked; nothing else changes
- **Rules:** `touch_last_used` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`, but `revoked_at EARLY`, `last_used_at EARLY`, `user_agent "Mozilla/5.0"`.

**When**
- `result = dao.touch_last_used(db, row=A)`.

**Then**
1. returns: `result is None`.
2. re-read A: `last_used_at == NOW`.
3. unchanged: unchanged(A) except `last_used_at`.
4. re-read A: `revoked_at == EARLY`.

### RT-TL-02 — the change is flushed, not committed
- **Rules:** `touch_last_used` R1, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`.
2. Savepoint and commit spy per **rolled back**.

**When**
- `result = dao.touch_last_used(db, row=A)`.

**Then**
1. returns: `result is None`.
2. re-read A: inside the savepoint, `raw(A, "last_used_at") == NOW`.
3. re-read A: after the savepoint rollback, `raw(A, "last_used_at") is None`.
4. mock called: the `db.commit` spy was never called.

### RT-TL-03 — an unrevoked row stays unrevoked; only last_used_at changes
- **Rules:** `touch_last_used` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = token, `token_hash H1`, but `user_agent "Mozilla/5.0"`.

**When**
- `result = dao.touch_last_used(db, row=A)`.

**Then**
1. returns: `result is None`.
2. re-read A: `last_used_at == NOW`.
3. unchanged: unchanged(A) except `last_used_at`.
4. re-read A: `revoked_at is None`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| FU-1 (a) — HR-10: `refresh_access_token` reads the presented row with a lock; a second refresh sees it revoked | `AuthService.refresh_access_token` | Security; not observable with one connection here. |
| FU-1 (b) — bulk revokes do not refresh loaded rows; a later `revoke` on a stale copy overwrites the stamp | `AuthService` | Here RV-06, RF-08, RA-05 hold the DAO side. |
| FU-1 (c) — the logout message counts expired rows as "active" (Q1) | `AuthService.logout_session` / `POST /auth/logout/` | Wording. |
| FU-1 (d) — `/auth/logout/` with `all_devices` accepts a revoked or expired token | `POST /auth/logout/` | Endpoint rule. |
| BUG-1407 at the caller — a long `User-Agent` or forwarded address no longer fails login | `AuthService._issue_token_pair` / login endpoints | After the DAO fix. |
| Q3 — `get_by_id` is dead code, to be removed | `docs/testing/dead-code-removal-checklist.md` | No card. |
| Module comment "every query scopes to a user" is wrong (Q2) | doc change | No card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `create` R1 | How close `issued_at` must be to the clock is not given. | RT-CR-01 uses ±5 s around the call. |
| 2 | `revoke` R4 | "If the successor row is deleted later" is a database fact about the foreign key, not something `revoke` does. | RT-RV-08 deletes with raw SQL in its When; no DAO call. |
| 3 | Overview "every method flushes"; `revoke_family` R4, `revoke_all_for_user` R3 | Whether the bulk revokes call `db.flush()` (and so store the caller's pending rows and unflushed edits) or only run the `UPDATE` is not said. | No "pending row stays pending" card on any writer here; the commit-spy cards read the database with raw SQL, which holds either way. |
| 4 | `revoke_family` R1 | "one value for all" — with `utcnow` patched every value is NOW, so a per-row clock read cannot be told apart. | No card can show it; RF-01 checks every stamp is NOW. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_hash` | Returns | RT-GH-01 |
| `get_by_hash` | R1 | RT-GH-01 |
| `get_by_hash` | R2 | RT-GH-01, RT-GH-02, RT-GH-03, RT-GH-04, RT-GH-05, RT-GH-06, RT-GH-07 |
| `get_by_hash` | Side effects | RT-GH-08 |
| `create` | Returns | RT-CR-01 |
| `create` | R1 | RT-CR-01, RT-CR-02 |
| `create` | R2 | RT-CR-03, RT-CR-14 |
| `create` | R3 | RT-CR-04, RT-CR-05, RT-CR-06, RT-CR-07, RT-CR-08, RT-CR-09 |
| `create` | R4 | RT-CR-13 |
| `create` | R4 [BUG-1407] | RT-CR-11, RT-CR-12 |
| `create` | R5 | RT-CR-10 |
| `create` | Errors | RT-CR-04, RT-CR-05, RT-CR-06, RT-CR-07, RT-CR-08, RT-CR-09, RT-CR-10 |
| `create` | Side effects | RT-CR-15 |
| `revoke` | Returns | RT-RV-01 |
| `revoke` | R1 | RT-RV-01, RT-RV-02, RT-RV-04 |
| `revoke` | R2 | RT-RV-01, RT-RV-03, RT-RV-04, RT-RV-05 |
| `revoke` | R3 | RT-RV-06 |
| `revoke` | R4 | RT-RV-07, RT-RV-08, RT-RV-09 |
| `revoke` | Errors | RT-RV-07 |
| `revoke` | Side effects | RT-RV-09 |
| `revoke_family` | Returns | RT-RF-01 |
| `revoke_family` | R1 | RT-RF-01 |
| `revoke_family` | R2 | RT-RF-02, RT-RF-06, RT-RF-07 |
| `revoke_family` | R3 | RT-RF-03, RT-RF-04, RT-RF-05 |
| `revoke_family` | R4 | RT-RF-08, RT-RF-09 |
| `revoke_family` | Side effects | RT-RF-09 |
| `revoke_all_for_user` | Returns | RT-RA-01 |
| `revoke_all_for_user` | R1 | RT-RA-01 |
| `revoke_all_for_user` | R2 | RT-RA-02, RT-RA-03, RT-RA-04, RT-RA-07 |
| `revoke_all_for_user` | R3 | RT-RA-05 |
| `revoke_all_for_user` | Side effects | RT-RA-06 |
| `touch_last_used` | Returns | RT-TL-01 |
| `touch_last_used` | R1 | RT-TL-01, RT-TL-02, RT-TL-03 |
| `touch_last_used` | Side effects | RT-TL-02 |
