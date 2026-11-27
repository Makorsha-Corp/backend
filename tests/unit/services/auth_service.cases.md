# Test cases — `app/services/auth_service.py`

> **Spec:** `tests/unit/services/auth_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 5 (2026-11-22) — TC3 audit (removing the method's own rollback went unnoticed in `login_user` and `switch_workspace`: LI-11 and SW-13 fail at the commit, where `_commit_transaction` rolls back itself). New AUTH-LI-13 and AUTH-SW-14 (pass, `Author: claude`): a step before the commit raises (the **failing issue** external: the access-token clock raises inside the issue), a pending extra row X is gone straight after the call, commit never called, one rollback. No card changed or retired.
> Revision 4 (2026-11-10) — verifier routing (case-missing, `login_user` R2): new AUTH-LI-12, an owner with an active membership logs in and gets no `workspace_id` claim and a refresh row with no workspace (pass: R2 is today's behaviour). No card changed or retired.
> Revision 3 (2026-11-10) — executor notes, decided under delegation: DISCREPANCY-2 (a failing commit rolls back twice, `_commit_transaction` then the method's `except`; TC4 asks only "rolled back") → `rb.call_count >= 1` in AUTH-RG-22, LI-11, SW-13, RF-16, LO-12, AR-27, ME-31, other Then lines kept; DISCREPANCY-1 → Conventions name the autouse **default_lifetimes** fixture (15 minutes, 14 days); card-text slips fixed in Race simulations (RG-11…13, RF-15 recorder, RF-14 replay). No card added or retired.
> Revision 2 (2026-11-10) — spec Fill-gaps 2026-11-10 (Gap log G1–G7). G1–G3, G7: Conventions now name `TokenPair.access_token`, `ProfileMeUpdate` from `app.schemas.profile`, `ActionMessage` (`type`, `message`) for **msgs**, the audit columns and `departments` from the spec; no card changed. G4 (`_issue_token_pair` R1a): new AUTH-TP-12 (`workspace_id=0` → `IntegrityError` 23503 at the flush, no pair) and AUTH-TP-13 (the `0 is present` claim, with the spec's fake `refresh_token_dao`, `Author: claude`). G5 (`refresh_access_token` R2a): new AUTH-RF-17 (an unrelated pending row is committed with the family revocation). G6: `login_user` R3's second sentence gets no case, as decided. No ID retired. All gaps closed.
> **Counts:** 220 cases · 183 expected-to-pass · 37 expected-to-fail (bugs) · 12 deferred

## Reviewer summary
- **Per callable:** `_issue_token_pair` 13 · `register_user` 23 (6 bug) · `_register_user_only` 6 · `_register_with_invitation` 17 (3 bug) · `_register_with_new_workspace` 20 (9 bug) · `login_user` 13 (1 bug) · `switch_workspace` 14 · `refresh_access_token` 17 (1 bug) · `logout_session` 12 · `request_password_reset` 4 (1 bug) · `reset_password` 1 · `reset_password_by_admin` 27 (1 bug) + **3 pending OQ-34** · `validate_invitation_token` 15 (1 bug) · `update_current_user` 35 (14 bug).
- **Depth:** full (security-critical: who gets a session, refresh tokens usable once, who may reset a password, which stamp is saved). Every refusal is one card per shape: each membership status (`inactive`, `suspended`, `invited`, `Active`), each refused role, owners of W0 (lower id) and W2 (higher id), each token state (unknown, empty, revoked, rotated-and-replayed, expired at exactly now, one microsecond before). TC1/TC3/TC4 once per committing writer, TC5 where a re-read follows the commit; one flush-only spy per non-committing writer.
- **Expected-to-fail (all strict):** BUG-2566 5 · BUG-1860 5 · BUG-1864 5 · BUG-1406 3 · BUG-2567 3 · BUG-1865 2 · BUG-2562 2 · BUG-2563 2 · BUG-1861, 1862, 1866, 1874, 1987, 2560, 2561, 2564, 2568, 2569 1 each.
- **Owner reset, pending OQ-34:** R7 has its own section (AUTH-P34-01 … 03: the caller themself, another owner-role member, a platform admin who owns another workspace). No other card uses such a target, so an OQ-34 answer changes only those three.
- **Races:** BUG-2564 is a race simulation (RACE-EMAIL patches `DAOProfile.get_by_email` to `None`): RG-11 strict xfail (normal refusal), RG-12 passing recorder (one `INSERT INTO profiles` reaches the index, nothing stays), RG-13 the case variant (BUG-1862). BUG-2560 is a recorder card (RF-15: `FOR UPDATE` on the lookup) plus the sequential replay RF-14 (pass). Both `Author: claude`.
- **Notable design choices:** the client address is stored as given, including a raw forwarded list (TP-03); BUG-2565 itself is the endpoint's (deferred). Stamps use the minted form `development/profiles/<id>/stamp-<32 hex>`; the server-built url is BUG-1866 only (no pass card asserts today's client url). Removed and suspended members still refresh (D11, RF-05, RF-06) but cannot switch (SW-04, SW-05) or be reset (AR-17, AR-18). Seat-limit refusal is checked through `register_user` (RG-21), since only the caller rolls the account back. Slug cards carry TAG so parallel runs never share a slug; "!!!" accepts `workspace` or `workspace-<n>`.
- **Needs a decision:** None. All seven gaps of Revision 1 are closed by the spec's Gap log (G1–G7).

## Conventions for this module

**IDs.** `AUTH` = `app/services/auth_service.py`. `TP` _issue_token_pair · `RG` register_user · `RU` _register_user_only · `RI` _register_with_invitation · `RW` _register_with_new_workspace · `LI` login_user · `SW` switch_workspace · `RF` refresh_access_token · `LO` logout_session · `FP` request_password_reset · `RP` reset_password · `AR` reset_password_by_admin · `VI` validate_invitation_token · `ME` update_current_user · **`P34`** = `reset_password_by_admin` R7, *pending OQ-34*, kept in its own section.

**Actors and fixed values.**
- `svc` = `auth_service` (`from app.services.auth_service import auth_service, AuthService, TokenPair`). `db` = the test's real session, first positional argument; every other argument by keyword. The session does not autoflush.
- Models from `app.models.<snake_case>`: `Profile`, `RefreshToken`, `Workspace`, `WorkspaceMember`, `WorkspaceInvitation`, `WorkspaceAuditLog`. `hash_refresh_token`, `get_password_hash`, `verify_password` (`app.core.security`). `settings` (`app.core.config`). `jwt` (PyJWT). `DAOProfile` (`app.dao.profile`). `ProfileMeUpdate` (`app.schemas.profile`). `ActionMessage` (`app.schemas.response`). `PydanticValidationError` = `pydantic.ValidationError`. `IntegrityError` (`sqlalchemy.exc`). `select`, `func`, `text`, `event`, `inspect as sa_inspect` (`sqlalchemy`). `patch` (`unittest.mock`). `uuid`, `re`, `datetime`, `timedelta`, `timezone`. `make_subscription_plan`, `make_workspace`, `make_profile` (`tests/unit/factories.py`).
- MISSING = `999999999`. NOW = `datetime(2026, 3, 5, 12, 0, 0)`. US = `timedelta(microseconds=1)`. DAY = `timedelta(days=1)`. PAST = `NOW - DAY`. EARLY = `datetime(2026, 3, 1, 8, 0, 0)`. LATER = `NOW + timedelta(days=10)`. FAR = `datetime(2099, 1, 1, 0, 0, 0)`. NOW14 = `NOW + timedelta(days=14)`. EXP15 = `int(datetime(2026, 3, 5, 12, 15, 0, tzinfo=timezone.utc).timestamp())`.
- TAG = `uuid.uuid4().hex[:8]`, once per test. E0 = `f"zed.{TAG}@acme.com"`, EO = `f"own.{TAG}@acme.com"`, EA = `f"ann.{TAG}@acme.com"`, EB = `f"bob.{TAG}@acme.com"`, EC = `f"cat.{TAG}@acme.com"`, E2 = `f"two.{TAG}@acme.com"`, EQ = `f"qin.{TAG}@acme.com"`. EN = `f"new.{TAG}@acme.com"` (no profile). LOWER = `f"ann.lee.{TAG}@example.com"`, MIXED = `f"Ann.Lee.{TAG}@example.com"`, UPPER = `f"ANN.LEE.{TAG.upper()}@EXAMPLE.COM"`.
- PW = `"Correct-Horse-9"`, PW2 = `"Battery-Staple-7"`. HPW = `get_password_hash(PW)`, computed once in a test that uses it. AGENT = `"Mozilla/5.0 Test"`, IP = `"203.0.113.7"`.
- RAW1 … RAW6 = `f"raw-{k}-{TAG}"` (k = 1 … 6). FAM1, FAM2 = `uuid.uuid4().hex`, each once per test. HEX32 = `r"[0-9a-f]{32}"`.
- WSNAME = `f"Acme Steel {TAG}"`, SL = `f"acme-steel-{TAG}"`. NOTMEM = `"You are not a member of this workspace"`. TAKEN = `"An account with this email already exists. Try logging in instead."`. BADLOGIN = `"Invalid email or password"`. EXPIRED_INV = `"Invitation has expired. Please request a new invitation."`.
- Stamps: TOKEN = `"0123456789abcdef0123456789abcdef"`, TOKEN2 = `"fedcba9876543210fedcba9876543210"`. OWN(U) = `f"development/profiles/{U.id}/stamp-{TOKEN}"`, OWN2(U) = the same with TOKEN2. ATT = `"ws-12/9f2c" + TOKEN`. IMG(pid) = `{"kind": "image", "public_id": pid, "url": "https://tracker.example/p.png", "width": 10, "height": 10}` (a fresh dict each time). VEC = `{"kind": "vector", "strokes": [{"color": "#000000", "width": 0.5, "points": []}], "viewBox": {"width": 100, "height": 50}}`. SRV = `"https://res.cloudinary.com/demo-cloud/image/authenticated/"`. FOREIGN = `"saved_stamp.public_id is not a stamp of this user"`. KIND_MSG = `"saved_stamp.kind must be 'vector' or 'image'."`.

**Standing rows** (every test, in this order, each flushed, no Given line):
1. PL0, PL1, PL2 = `make_subscription_plan(db, max_members=10)` (not default, active).
2. `make_profile(db, email=…, name=…)`: U0 (E0, `"Zara Zero"`), UO (EO, `"Olive Owner"`), UA (EA, `"Ann Lee"`), UB (EB, `"Bob Roy"`), UC (EC, `"Cat Kim"`), U2 (E2, `"Tom Two"`), UQ (EQ, `"Quinn Extra"`). Ids rise in this order. Every `hashed_password` is `"not-a-real-hash"`.
3. W0 = `make_workspace(db, subscription_plan_id=PL0.id, owner_user_id=U0.id)`; W1 = `make_workspace(db, name="Acme Works", subscription_plan_id=PL1.id, owner_user_id=UO.id)`; W2 = `make_workspace(db, name="Tom Works", subscription_plan_id=PL2.id, owner_user_id=U2.id)`. `W0.id < W1.id < W2.id`.
4. Owner rows `WorkspaceMember(workspace_id=…, user_id=…, role="owner", status="active")`: M0 (W0, U0), MO (W1, UO), M2 (W2, U2).
No other plan, member, invitation, audit row or refresh token exists unless the Given builds it.

**Given rows.** Built directly (never through `svc` unless a line says so), flushed one at a time in the order written. After "but" a line names every column that differs. A line written as code is a step run exactly as written.
- **member(U, role, status="active", ws=W1)** = `WorkspaceMember(workspace_id=ws.id, user_id=U.id, role=role, status=status)`.
- **token K (R)** = `K = RefreshToken(user_id=UA.id, token_hash=hash_refresh_token(R), family_id=FAM1, workspace_id=None, expires_at=LATER)`.
- **invitation J to e** = `J = WorkspaceInvitation(workspace_id=W1.id, email=e, role="member", position=None, token=f"inv-J-{TAG}", status="pending", expires_at=FAR, invited_by_user_id=UO.id)` (J = the row's Given name).
- **PD** = `make_subscription_plan(db, name=f"free-{TAG}", is_default=True, is_active=True, max_members=3)`.
- **limit n** = `PL1.max_members = n; db.flush()`.
- **commit point** = after the last Given line the test runs `db.commit()` (releases a savepoint). Snapshots for `unchanged` and `nothing written` are taken there.
- **extra row X** (after the commit point) = `X = WorkspaceMember(workspace_id=W2.id, user_id=UQ.id, role="viewer", status="active")`, `db.add(X)`, `db.flush()`, `X_ID = X.id`; not committed.

**Externals.** **clock** = every When (and every Given step that calls `svc`) runs inside `patch("app.services.auth_service.utcnow", return_value=NOW)`, `patch("app.core.security.utcnow", return_value=NOW)`, `patch("app.dao.refresh_token.utcnow", return_value=NOW)`, `patch("app.managers.workspace_manager.utcnow", return_value=NOW)`. **dr** (every `ME` card) = `patch("app.managers.profile_stamp_manager.destroy_resource", return_value={"result": "ok"})`; plus `monkeypatch.setattr(settings, …)`: `CLOUDINARY_UPLOAD_ENV "development"`, `ENVIRONMENT "development"`, `CLOUDINARY_CLOUD_NAME "demo-cloud"`, `CLOUDINARY_API_KEY "123456"`, `CLOUDINARY_API_SECRET "s3cret"`. **default_lifetimes** (autouse, every test) = `monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 15)` and `monkeypatch.setattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 14)`: the spec defaults, pinned because the dev `.env` sets other values (as `security.cases.md` pins its settings); a card that sets them itself (AUTH-TP-09) overrides it. No email, notification or network call exists in this module; nothing else is mocked unless a card says so. **failing issue** (AUTH-LI-13, AUTH-SW-14 only; TC3 before the commit) = clock, except that `patch("app.core.security.utcnow", side_effect=RuntimeError("clock down"))` replaces its `return_value=NOW` patch: minting the access token inside the issue raises, before any refresh row or commit. **fake row write** (AUTH-TP-13 only, `_issue_token_pair` R1a) = `fake = SimpleNamespace(create=lambda *a, **k: None)` (`types.SimpleNamespace`), `monkeypatch.setattr(auth_service, "refresh_token_dao", fake)`.

**Named checks.**
- **claims(t)** = `jwt.decode(t, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_exp": False})`. A pair's fields: `access_token`, `refresh_token`, `expires_in`, `refresh_expires_in`.
- **row_of(p)** = `db.expire_all()`, then `db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(p.refresh_token)))`.
- **tokens(U)** = number of `RefreshToken` rows with `user_id == U.id`; **live(U)** = the same with `revoked_at IS NULL`.
- **msgs(m)** = `[(x.type.value, x.message) for x in m]` for the list `m` of `ActionMessage` objects, in order; the kinds used are `"success"` and `"info"`.
- **re-read X** = `db.expire_all()`, then `db.get(<Model>, X.id)`. **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **nothing written** = the numbers of rows of `profiles`, `workspaces`, `workspace_members`, `workspace_invitations`, `workspace_audit_logs`, `refresh_tokens` (all workspaces) equal their values at the commit point.
- **audit(W, a)** = `db.expire_all()`, then the `WorkspaceAuditLog` rows with `workspace_id == W.id` and `action == a`, ordered by `id`; metadata is `metadata_json`.
- **profile(e)** = `db.scalar(select(Profile).where(Profile.email == e))` after `db.expire_all()`; **count_ci(e)** = number of profiles with `func.lower(Profile.email) == e.lower()`.
- **not_expired(o)** = `not (sa_inspect(o).expired_attributes & {c.key for c in sa_inspect(type(o)).mapper.column_attrs})`.
- **x_kept** = `db.scalar(select(func.count()).select_from(WorkspaceMember).where(WorkspaceMember.id == X_ID)) == 1`; **x_gone** = the same `== 0`.
- `raises: <Type>` = `with pytest.raises(<Type>) as exc:` around the call, no savepoint; `str(exc.value)` compared with `==`. Target `schema` = only the schema is built.
- `raises: IntegrityError on flush` = `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the When; `pgcode` = `exc.value.orig.pgcode`.
- `session:` lines check `db.new` / `db.dirty` / `db.deleted` right after the call, before any re-read.
- `committed:` lines: before the first, the test runs `db.rollback()` once; each line then reads with a fresh query.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When (inside any `raises` block).
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = the same with `patch.object(db, "refresh", side_effect=RuntimeError("boom"))` and no `rb`.
- **flush only** (commit spy of a non-committing writer) = `sp = db.begin_nested()` directly before the When, which runs inside `patch.object(db, "commit", wraps=db.commit) as cm`; the "inside" lines run first, then `sp.rollback()` and the "after" lines.
- **recorder** = a Given step run last: `stmts = []`, `event.listen(db.connection(), "before_cursor_execute", rec)` where `rec(conn, cursor, statement, params, context, executemany)` appends `statement`; `event.remove` right after the When. `inserts(t)` = the recorded statements starting with `INSERT INTO {t}`.

**xfail cards.** Strict: `pytest.mark.xfail(strict=True, reason="BUG-n")`. Write the call and checks exactly as shown, also with a parameter that does not exist yet.

**Race simulations** (the only patches of the target's own code):
- **RACE-EMAIL** = `patch.object(DAOProfile, "get_by_email", return_value=None)` around the When: the "already registered" check passes for an email that exists, as when two registrations of one email run at once. Serves `register_user` R1b [BUG-2564] and R1a [BUG-1862] (AUTH-RG-11, RG-12, RG-13).
- The refresh lock [BUG-2560] is not simulated: one session cannot hold a lock against itself. It is a **recorder** card (AUTH-RF-15) plus the sequential replay (AUTH-RF-14).

## `AuthService._issue_token_pair`

### AUTH-TP-01 — the access token names the user, the email and the workspace
- **Rules:** `_issue_token_pair` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No refresh token exists (standing rows only).

**When**
- `pair = svc._issue_token_pair(db, user=UA, workspace_id=W1.id, family_id=None, user_agent=AGENT, ip_address=IP)` under clock.

**Then**
1. returns: `isinstance(pair, TokenPair)`.
2. returns: `claims(pair.access_token)["sub"] == str(UA.id)`.
3. returns: `claims(pair.access_token)["email"] == EA`.
4. returns: `claims(pair.access_token)["workspace_id"] == W1.id`.
5. returns: `claims(pair.access_token)["exp"] == EXP15`.

### AUTH-TP-02 — no workspace gives no workspace_id claim
- **Rules:** `_issue_token_pair` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No refresh token exists (standing rows only).

**When**
- `pair = svc._issue_token_pair(db, user=UA, workspace_id=None, family_id=None, user_agent=AGENT, ip_address=IP)` under clock.

**Then**
1. returns: `"workspace_id" not in claims(pair.access_token)`.
2. returns: `claims(pair.access_token)["sub"] == str(UA.id)`.
3. re-read: `row_of(pair).workspace_id is None`.

### AUTH-TP-03 — one refresh row stores the hash and the diagnostics as given
- **Rules:** `_issue_token_pair` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No refresh token exists (standing rows only).

**When**
- `pair = svc._issue_token_pair(db, user=UA, workspace_id=W1.id, family_id=None, user_agent=AGENT, ip_address="203.0.113.7, 10.0.0.1")` under clock.

**Then**
1. returns: `isinstance(pair.refresh_token, str)`.
2. re-read: `row_of(pair)` is not None, `row_of(pair).user_id == UA.id`, `row_of(pair).workspace_id == W1.id`.
3. re-read: `row_of(pair).expires_at == NOW14`.
4. re-read: `row_of(pair).user_agent == "Mozilla/5.0 Test"`, `row_of(pair).ip_address == "203.0.113.7, 10.0.0.1"`.
5. re-read: `row_of(pair).revoked_at is None`, `row_of(pair).replaced_by_id is None`.
6. count: `tokens(UA) == 1`.

### AUTH-TP-04 — a given family is joined
- **Rules:** `_issue_token_pair` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. No refresh token exists (standing rows only).

**When**
- `pair = svc._issue_token_pair(db, user=UA, workspace_id=None, family_id=FAM1, user_agent=None, ip_address=None)` under clock.

**Then**
1. returns: `isinstance(pair, TokenPair)`.
2. re-read: `row_of(pair).family_id == FAM1`.
3. re-read: `row_of(pair).user_agent is None`, `row_of(pair).ip_address is None`.

### AUTH-TP-05 — family None starts a new 32-hex family
- **Rules:** `_issue_token_pair` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No refresh token exists (standing rows only).

**When**
- `pair = svc._issue_token_pair(db, user=UA, workspace_id=None, family_id=None, user_agent=None, ip_address=None)` under clock.

**Then**
1. returns: `isinstance(pair, TokenPair)`.
2. re-read: `re.fullmatch(HEX32, row_of(pair).family_id) is not None`.

### AUTH-TP-06 — an empty family starts a new family too
- **Rules:** `_issue_token_pair` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No refresh token exists (standing rows only).

**When**
- `pair = svc._issue_token_pair(db, user=UA, workspace_id=None, family_id="", user_agent=None, ip_address=None)` under clock.

**Then**
1. returns: `isinstance(pair, TokenPair)`.
2. re-read: `re.fullmatch(HEX32, row_of(pair).family_id) is not None`.

### AUTH-TP-07 — two calls give two tokens, two rows and two families
- **Rules:** `_issue_token_pair` R3, R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `first = svc._issue_token_pair(db, user=UA, workspace_id=None, family_id=None, user_agent=None, ip_address=None)` under clock.

**When**
- `pair = svc._issue_token_pair(db, user=UA, workspace_id=None, family_id=None, user_agent=None, ip_address=None)` under clock.

**Then**
1. returns: `pair.refresh_token != first.refresh_token`.
2. count: `tokens(UA) == 2`.
3. re-read: `row_of(pair).family_id != row_of(first).family_id`.

### AUTH-TP-08 — the lifetimes are 900 and 1 209 600 seconds
- **Rules:** `_issue_token_pair` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. No refresh token exists (standing rows only).

**When**
- `pair = svc._issue_token_pair(db, user=UA, workspace_id=None, family_id=None, user_agent=None, ip_address=None)` under clock.

**Then**
1. returns: `pair.expires_in == 900`.
2. returns: `pair.refresh_expires_in == 1209600`.

### AUTH-TP-09 — the lifetimes are read from the settings at call time
- **Rules:** `_issue_token_pair` R2, R4; R1 (`exp`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 30)`.
2. `monkeypatch.setattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 7)`.

**When**
- `pair = svc._issue_token_pair(db, user=UA, workspace_id=None, family_id=None, user_agent=None, ip_address=None)` under clock.

**Then**
1. returns: `pair.expires_in == 1800`.
2. returns: `pair.refresh_expires_in == 604800`.
3. returns: `claims(pair.access_token)["exp"] == int(datetime(2026, 3, 5, 12, 30, 0, tzinfo=timezone.utc).timestamp())`.
4. re-read: `row_of(pair).expires_at == NOW + timedelta(days=7)`.

### AUTH-TP-10 — the raw refresh token is stored nowhere
- **Rules:** `_issue_token_pair` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No refresh token exists (standing rows only).

**When**
- `pair = svc._issue_token_pair(db, user=UA, workspace_id=W1.id, family_id=None, user_agent=AGENT, ip_address=IP)` under clock.

**Then**
1. returns: `len(pair.refresh_token) > 0`.
2. re-read: `row_of(pair).token_hash == hash_refresh_token(pair.refresh_token)`.
3. re-read: `pair.refresh_token not in [str(getattr(row_of(pair), c.key)) for c in sa_inspect(RefreshToken).mapper.column_attrs]`.

### AUTH-TP-11 — the refresh row is flushed, never committed
- **Rules:** `_issue_token_pair` Returns
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No refresh token exists (standing rows only).

**When**
- flush only: `pair = svc._issue_token_pair(db, user=UA, workspace_id=None, family_id=None, user_agent=None, ip_address=None)` under clock.

**Then**
1. returns (inside): `tokens(UA) == 1`.
2. mock called (inside): `cm.call_count == 0`.
3. count (after `sp.rollback()`): `tokens(UA) == 0`.

### AUTH-TP-12 — workspace id 0 fails at the flush and returns no pair
- **Rules:** `_issue_token_pair` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No refresh token exists (standing rows only).

**When**
- `pair = svc._issue_token_pair(db, user=UA, workspace_id=0, family_id=None, user_agent=None, ip_address=None)` under clock.

**Then**
1. raises: `IntegrityError` on flush, `pgcode == "23503"`.
2. count: `tokens(UA) == 0`.

### AUTH-TP-13 — workspace id 0 is present in the claims
- **Rules:** `_issue_token_pair` R1, R1a (the `0 is present` boundary)
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. fake row write.

**When**
- `pair = svc._issue_token_pair(db, user=UA, workspace_id=0, family_id=None, user_agent=None, ip_address=None)` under clock.

**Then**
1. returns: `"workspace_id" in claims(pair.access_token)`.
2. returns: `claims(pair.access_token)["workspace_id"] == 0`.

## `AuthService.register_user`

### AUTH-RG-01 — a workspace name creates the account, the workspace and the session
- **Rules:** `register_user` R3, R6; `_register_with_new_workspace` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. PD (commit point after this line).

**When**
- `user, ws, pair, messages = svc.register_user(db, name="Nia New", email=EN, password=PW, workspace_name=WSNAME, invitation_token=None, timezone="Asia/Dhaka", user_agent=AGENT, ip_address=IP)` under clock.

**Then**
1. returns: `user.email == EN`, `user.name == "Nia New"`.
2. returns: `ws.name == WSNAME`, `ws.slug == SL`.
3. committed: `profile(EN)` is not None and `profile(EN).timezone == "Asia/Dhaka"`.
4. committed: one `Workspace` row with `slug == SL`, `owner_user_id == user.id`.
5. committed: one `WorkspaceMember` row with `workspace_id == ws.id`, `user_id == user.id`, `role == "owner"`, `status == "active"`.
6. committed: `tokens(user) == 1`.

### AUTH-RG-02 — new-workspace messages, then the welcome message
- **Rules:** `register_user` R5; `_register_with_new_workspace` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. PD (commit point after this line).

**When**
- `user, ws, pair, messages = svc.register_user(db, name="Nia New", email=EN, password=PW, workspace_name=WSNAME, timezone=None)` under clock.

**Then**
1. returns: `msgs(messages) == [("success", "User profile created"), ("success", f"Workspace '{WSNAME}' created successfully with 14-day trial"), ("success", "Welcome Nia New! Your account has been created successfully.")]`.

### AUTH-RG-03 — one commit, and the returned rows are re-read
- **Rules:** `register_user` R6 (TC1, TC2)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PD (commit point after this line).

**When**
- spies: `user, ws, pair, messages = svc.register_user(db, name="Nia New", email=EN, password=PW, workspace_name=WSNAME)` under clock.

**Then**
1. returns: `not_expired(user)`.
2. returns: `not_expired(ws)`.
3. mock called: `cm.call_count == 1`.
4. mock called: `rb.call_count == 0`.

### AUTH-RG-04 — a taken email is refused, rolled back, and pending changes are discarded
- **Rules:** `register_user` R1, R7 (TC3)
- **Kind:** error
- **Expect:** pass

**Given**
1. PD (commit point after this line).
2. extra row X.

**When**
- spies: `svc.register_user(db, name="Ann Again", email=EA, password=PW, workspace_name=WSNAME)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == TAKEN`.
2. mock called: `rb.call_count == 1`.
3. count: x_gone.
4. nothing written.
5. count: `count_ci(EA) == 1`.

### AUTH-RG-05 — an email in other capitals is the same account
- **Rules:** `register_user` R1a [BUG-1860]
- **Kind:** bug
- **Expect:** xfail BUG-1860
- **Fails today on:** Then 1 (no ValueError: a second account is created)

**Given**
1. `make_profile(db, email=MIXED, name="Ann Mixed")` (commit point after this line).

**When**
- `svc.register_user(db, name="Ann Again", email=LOWER, password=PW)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == TAKEN`.
2. count: `count_ci(LOWER) == 1`.

### AUTH-RG-06 — capitals on the argument side find a lower-case account
- **Rules:** `register_user` R1a [BUG-1860]
- **Kind:** bug
- **Expect:** xfail BUG-1860
- **Fails today on:** Then 1 (no ValueError: a second account is created)

**Given**
1. `make_profile(db, email=LOWER, name="Ann Lower")` (commit point after this line).

**When**
- `svc.register_user(db, name="Ann Again", email=UPPER, password=PW)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == TAKEN`.
2. count: `count_ci(LOWER) == 1`.

### AUTH-RG-07 — outer spaces around a taken email are ignored
- **Rules:** `register_user` R1a [BUG-1860]
- **Kind:** bug
- **Expect:** xfail BUG-1860
- **Author:** claude
- **Fails today on:** Then 1 (no ValueError with TAKEN: today the account is created or the insert fails on the exact unique index)

**Given**
1. `make_profile(db, email=LOWER, name="Ann Lower")` (commit point after this line).

**When**
- `svc.register_user(db, name="Ann Again", email=f"  {LOWER} ", password=PW)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == TAKEN`.
2. count: `count_ci(LOWER) == 1`.

### AUTH-RG-08 — a different inner text is not taken
- **Rules:** `register_user` R1, R1a (inner text still counts)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `make_profile(db, email=LOWER, name="Ann Lower")` (commit point after this line).

**When**
- `user, ws, pair, messages = svc.register_user(db, name="Ann Lea", email=f"ann.lea.{TAG}@example.com", password=PW)` under clock.

**Then**
1. returns: `user.email == f"ann.lea.{TAG}@example.com"`.
2. committed: `count_ci(LOWER) == 1`.
3. committed: `count_ci(f"ann.lea.{TAG}@example.com") == 1`.

### AUTH-RG-09 — a new account's email is stored lower-cased
- **Rules:** `register_user` R1a [BUG-1861]
- **Kind:** bug
- **Expect:** xfail BUG-1861
- **Fails today on:** Then 2 (the email is stored as typed)

**Given**
1. No profile with TAG in the email other than the standing ones (commit point after this line).

**When**
- `user, ws, pair, messages = svc.register_user(db, name="Ann Lee", email=MIXED, password=PW)` under clock.

**Then**
1. committed: `count_ci(MIXED) == 1`.
2. committed: `profile(LOWER)` is not None.

### AUTH-RG-10 — a mixed-case email registers one account
- **Rules:** `register_user` R1a (part independent of BUG-1861), R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. No profile with TAG in the email other than the standing ones (commit point after this line).

**When**
- `user, ws, pair, messages = svc.register_user(db, name="Ann Lee", email=MIXED, password=PW)` under clock.

**Then**
1. returns: `user.email.lower() == LOWER`.
2. committed: `count_ci(MIXED) == 1`.

### AUTH-RG-11 — two registrations at once: the loser gets the normal refusal
- **Rules:** `register_user` R1b [BUG-2564]
- **Kind:** bug
- **Expect:** xfail BUG-2564
- **Author:** claude
- **Fails today on:** Then 1 (the call raises IntegrityError: the unique email index fires and is not mapped)

**Given**
1. PD (commit point after this line).
2. extra row X.

**When**
- RACE-EMAIL, spies: `svc.register_user(db, name="Ann Again", email=EA, password=PW, workspace_name=WSNAME)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == TAKEN`.
2. mock called: `rb.call_count == 1`.
3. count: x_gone.
4. nothing written.

### AUTH-RG-12 — under the race, the insert reaches the index and nothing stays
- **Rules:** `register_user` R1b, R7 (holds today and after BUG-2564)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. PD (commit point after this line).
2. recorder.

**When**
- RACE-EMAIL: `with pytest.raises(Exception):` around `svc.register_user(db, name="Ann Again", email=EA, password=PW, workspace_name=WSNAME)` under clock.

**Then**
1. count: `len(inserts("profiles")) == 1`.
2. count: `count_ci(EA) == 1`.
3. count: no `Workspace` row with `slug == SL`.
4. nothing written.

### AUTH-RG-13 — a case variant past the check is refused by the database, as a normal refusal
- **Rules:** `register_user` R1a [BUG-1862], R1b [BUG-2564]
- **Kind:** bug
- **Expect:** xfail BUG-1862
- **Author:** claude
- **Fails today on:** Then 1 (no error: the exact unique index lets a second account in)

**Given**
1. `make_profile(db, email=MIXED, name="Ann Mixed")` (commit point after this line).

**When**
- RACE-EMAIL: `svc.register_user(db, name="Ann Again", email=LOWER, password=PW)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == TAKEN`.
2. count: `count_ci(LOWER) == 1`.

### AUTH-RG-14 — a token and a workspace name: the token wins
- **Rules:** `register_user` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. PD.
2. invitation I to EN (commit point after this line).

**When**
- `user, ws, pair, messages = svc.register_user(db, name="Nia New", email=EN, password=PW, workspace_name=WSNAME, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. returns: `ws.id == W1.id`.
2. committed: no `Workspace` row with `slug == SL`.
3. committed: one `WorkspaceMember` row with `workspace_id == W1.id`, `user_id == user.id`, `role == "member"`, `status == "active"`.

### AUTH-RG-15 — an empty token with a workspace name takes the workspace path
- **Rules:** `register_user` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PD (commit point after this line).

**When**
- `user, ws, pair, messages = svc.register_user(db, name="Nia New", email=EN, password=PW, workspace_name=WSNAME, invitation_token="")` under clock.

**Then**
1. returns: `ws.slug == SL`.
2. committed: one `Workspace` row with `slug == SL`.

### AUTH-RG-16 — neither a token nor a name: an account without a workspace
- **Rules:** `register_user` R4, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. No profile with email EN (commit point after this line).

**When**
- `user, ws, pair, messages = svc.register_user(db, name="Nia New", email=EN, password=PW, workspace_name=None, invitation_token=None)` under clock.

**Then**
1. returns: `ws is None`.
2. returns: `msgs(messages) == [("success", "User profile created"), ("success", "Welcome Nia New! Your account has been created successfully.")]`.
3. committed: `profile(EN)` is not None.
4. count: number of `workspaces` rows equals its value at the commit point.
5. count: no `WorkspaceMember` row with `user_id == user.id`.

### AUTH-RG-17 — empty strings for both take the account-only path
- **Rules:** `register_user` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No profile with email EN (commit point after this line).

**When**
- `user, ws, pair, messages = svc.register_user(db, name="Nia New", email=EN, password=PW, workspace_name="", invitation_token="")` under clock.

**Then**
1. returns: `ws is None`.
2. count: number of `workspaces` rows equals its value at the commit point.

### AUTH-RG-18 — invitation messages, then the welcome message
- **Rules:** `register_user` R5; `_register_with_invitation` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. invitation I to EN (commit point after this line).

**When**
- `user, ws, pair, messages = svc.register_user(db, name="Nia New", email=EN, password=PW, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. returns: `msgs(messages) == [("info", "Valid invitation found for workspace: Acme Works"), ("success", "User profile created"), ("success", "You've been added to workspace 'Acme Works' with role 'member'"), ("success", "Welcome Nia New! Your account has been created successfully.")]`.

### AUTH-RG-19 — no default plan: refused, the account is rolled back, pending changes discarded
- **Rules:** `register_user` R7 (TC3); `_register_with_new_workspace` R4, Errors "no default plan"
- **Kind:** error
- **Expect:** pass

**Given**
1. No default plan (standing rows only; commit point after this line).
2. extra row X.

**When**
- spies: `svc.register_user(db, name="Nia New", email=EN, password=PW, workspace_name=WSNAME)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "No default subscription plan found"`.
2. mock called: `rb.call_count == 1`.
3. count: x_gone.
4. nothing written.

### AUTH-RG-20 — an invalid time zone is a validation error and nothing stays
- **Rules:** `register_user` R7 (TC3); `_register_user_only` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. PD (commit point after this line).
2. extra row X.

**When**
- `svc.register_user(db, name="Nia New", email=EN, password=PW, workspace_name=WSNAME, timezone="Mars/Base")` under clock.

**Then**
1. raises: `PydanticValidationError`.
2. count: x_gone.
3. nothing written.

### AUTH-RG-21 — a full workspace refuses the invited registration and removes the account
- **Rules:** `register_user` R7; `_register_with_invitation` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. limit 1.
2. invitation I to EN (commit point after this line).

**When**
- `svc.register_user(db, name="Nia New", email=EN, password=PW, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Workspace has reached maximum member limit (1). Upgrade subscription to add more members."`.
2. count: `profile(EN) is None`.
3. re-read I: `status == "pending"`.
4. nothing written.

### AUTH-RG-22 — a failing commit saves nothing
- **Rules:** `register_user` R7 (TC4)
- **Kind:** error
- **Expect:** pass

**Given**
1. PD (commit point after this line).

**When**
- failing commit: `svc.register_user(db, name="Nia New", email=EN, password=PW, workspace_name=WSNAME)` under clock.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `profile(EN) is None`.
4. nothing written.

### AUTH-RG-23 — a failing re-read after the commit keeps the account
- **Rules:** `register_user` R7 (TC5)
- **Kind:** error
- **Expect:** pass

**Given**
1. PD (commit point after this line).

**When**
- failing refresh: `svc.register_user(db, name="Nia New", email=EN, password=PW, workspace_name=WSNAME)` under clock.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: `profile(EN)` is not None.
3. committed: one `Workspace` row with `slug == SL`.

## `AuthService._register_user_only`

### AUTH-RU-01 — the account is created with a hashed password and the email as user_id
- **Rules:** `_register_user_only` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. No profile with email EN (standing rows only).

**When**
- `user, ws, pair, messages = svc._register_user_only(db, name="Nia New", email=EN, password=PW, timezone="Asia/Dhaka", user_agent=AGENT, ip_address=IP)` under clock.

**Then**
1. returns: `ws is None`.
2. returns: `msgs(messages) == [("success", "User profile created")]`.
3. re-read user: `email == EN`, `name == "Nia New"`, `timezone == "Asia/Dhaka"`, `user_id == EN`.
4. re-read user: `verify_password(PW, user.hashed_password) is True`.

### AUTH-RU-02 — the session has no workspace and a new family
- **Rules:** `_register_user_only` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No profile with email EN (standing rows only).

**When**
- `user, ws, pair, messages = svc._register_user_only(db, name="Nia New", email=EN, password=PW, timezone=None, user_agent=AGENT, ip_address=IP)` under clock.

**Then**
1. returns: `"workspace_id" not in claims(pair.access_token)`.
2. returns: `claims(pair.access_token)["sub"] == str(user.id)`.
3. re-read: `row_of(pair).workspace_id is None`, `row_of(pair).user_agent == "Mozilla/5.0 Test"`, `row_of(pair).ip_address == "203.0.113.7"`.
4. re-read: `re.fullmatch(HEX32, row_of(pair).family_id) is not None`.

### AUTH-RU-03 — no workspace, membership or audit row is written
- **Rules:** `_register_user_only` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No profile with email EN (commit point after this line).

**When**
- `user, ws, pair, messages = svc._register_user_only(db, name="Nia New", email=EN, password=PW)` under clock.

**Then**
1. returns: `ws is None`.
2. count: the numbers of `workspaces`, `workspace_members`, `workspace_audit_logs` rows equal their values at the commit point.
3. count: `tokens(user) == 1`.

### AUTH-RU-04 — a whitespace time zone is stored as None
- **Rules:** `_register_user_only` R1 (inputs: blank time zone → `None`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No profile with email EN (standing rows only).

**When**
- `user, ws, pair, messages = svc._register_user_only(db, name="Nia New", email=EN, password=PW, timezone="   ")` under clock.

**Then**
1. returns: `user.email == EN`.
2. re-read user: `timezone is None`.

### AUTH-RU-05 — an invalid time zone raises before anything is written
- **Rules:** `_register_user_only` R1, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No profile with email EN (commit point after this line).

**When**
- `svc._register_user_only(db, name="Nia New", email=EN, password=PW, timezone="Mars/Base")` under clock.

**Then**
1. raises: `PydanticValidationError`.
2. session: `not db.new`.
3. nothing written.

### AUTH-RU-06 — flushed, never committed
- **Rules:** `_register_user_only` Returns (flushed)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No profile with email EN (standing rows only).

**When**
- flush only: `user, ws, pair, messages = svc._register_user_only(db, name="Nia New", email=EN, password=PW)` under clock.

**Then**
1. returns (inside): `profile(EN)` is not None.
2. mock called (inside): `cm.call_count == 0`.
3. count (after `sp.rollback()`): `profile(EN) is None`.

## `AuthService._register_with_invitation`

### AUTH-RI-01 — the invited account joins with the invitation's role and position
- **Rules:** `_register_with_invitation` R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. invitation I to EN, but `role "viewer"`, `position "Supervisor"`.

**When**
- `user, ws, pair, messages = svc._register_with_invitation(db, name="Nia New", email=EN, password=PW, invitation_token=f"inv-I-{TAG}", user_agent=AGENT, ip_address=IP)` under clock.

**Then**
1. returns: `ws.id == W1.id`, `user.email == EN`.
2. count: one `WorkspaceMember` row with `workspace_id == W1.id`, `user_id == user.id`.
3. re-read that row: `role == "viewer"`, `position == "Supervisor"`, `status == "active"`.
4. re-read I: `status == "accepted"`, `accepted_by_user_id == user.id`, `accepted_at == NOW`.

### AUTH-RI-02 — messages: invitation found, profile, added with the role
- **Rules:** `_register_with_invitation` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. invitation I to EN, but `role "viewer"`.

**When**
- `user, ws, pair, messages = svc._register_with_invitation(db, name="Nia New", email=EN, password=PW, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. returns: `msgs(messages) == [("info", "Valid invitation found for workspace: Acme Works"), ("success", "User profile created"), ("success", "You've been added to workspace 'Acme Works' with role 'viewer'")]`.

### AUTH-RI-03 — the session is for the invitation's workspace, in a new family
- **Rules:** `_register_with_invitation` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. invitation I to EN.

**When**
- `user, ws, pair, messages = svc._register_with_invitation(db, name="Nia New", email=EN, password=PW, invitation_token=f"inv-I-{TAG}", user_agent=AGENT, ip_address=IP)` under clock.

**Then**
1. returns: `claims(pair.access_token)["workspace_id"] == W1.id`.
2. re-read: `row_of(pair).workspace_id == W1.id`, `row_of(pair).user_id == user.id`.
3. re-read: `re.fullmatch(HEX32, row_of(pair).family_id) is not None`.

### AUTH-RI-04 — the accept writes member_added and invitation_accepted
- **Rules:** `_register_with_invitation` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. invitation I to EN, but `role "viewer"`.

**When**
- `user, ws, pair, messages = svc._register_with_invitation(db, name="Nia New", email=EN, password=PW, invitation_token=f"inv-I-{TAG}", user_agent=AGENT, ip_address=IP)` under clock.

**Then**
1. returns: `ws.id == W1.id`.
2. audit: audit(W1, "member_added") has exactly 1 row.
3. audit: that row `user_id == UO.id`, `metadata_json == {"new_member_id": user.id, "role": "viewer"}`.
4. audit: audit(W1, "invitation_accepted") has exactly 1 row.
5. audit: that row `user_id == user.id`, `metadata_json == {"invitation_id": I.id}`.

### AUTH-RI-05 — the accept's audit rows carry the client's address and browser
- **Rules:** `_register_with_invitation` R4 [BUG-2563]
- **Kind:** bug
- **Expect:** xfail BUG-2563
- **Fails today on:** Then 3 (both columns are NULL)

**Given**
1. invitation I to EN.

**When**
- `user, ws, pair, messages = svc._register_with_invitation(db, name="Nia New", email=EN, password=PW, invitation_token=f"inv-I-{TAG}", user_agent=AGENT, ip_address=IP)` under clock.

**Then**
1. returns: `ws.id == W1.id`.
2. audit: audit(W1, "member_added") has exactly 1 row.
3. audit: that row `ip_address == "203.0.113.7"`, `user_agent == "Mozilla/5.0 Test"`.
4. audit: the audit(W1, "invitation_accepted") row `ip_address == "203.0.113.7"`, `user_agent == "Mozilla/5.0 Test"`.

### AUTH-RI-06 — an unknown token is refused before anything is written
- **Rules:** `_register_with_invitation` R1, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. invitation I to EN (commit point after this line).

**When**
- `svc._register_with_invitation(db, name="Nia New", email=EN, password=PW, invitation_token=f"inv-Z-{TAG}")` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Invalid invitation token"`.
2. session: `not db.new and not db.dirty`.
3. nothing written.

### AUTH-RI-07 — the token in capitals is unknown
- **Rules:** `_register_with_invitation` R1 (exact token)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. invitation I to EN (commit point after this line).

**When**
- `svc._register_with_invitation(db, name="Nia New", email=EN, password=PW, invitation_token=f"INV-I-{TAG.upper()}")` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Invalid invitation token"`.
2. nothing written.

### AUTH-RI-08 — the token with a leading space is unknown
- **Rules:** `_register_with_invitation` R1 (exact token)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. invitation I to EN (commit point after this line).

**When**
- `svc._register_with_invitation(db, name="Nia New", email=EN, password=PW, invitation_token=f" inv-I-{TAG}")` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Invalid invitation token"`.
2. nothing written.

### AUTH-RI-09 — an expired invitation is refused
- **Rules:** `_register_with_invitation` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. invitation I to EN, but `expires_at NOW - US` (commit point after this line).

**When**
- `svc._register_with_invitation(db, name="Nia New", email=EN, password=PW, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == EXPIRED_INV`.
2. nothing written.

### AUTH-RI-10 — an invitation expiring exactly now is expired
- **Rules:** `_register_with_invitation` R1 (BUG-1987 of the manager)
- **Kind:** bug
- **Expect:** xfail BUG-1987
- **Fails today on:** Then 1 (no error: at exactly `expires_at` the invitation is accepted)

**Given**
1. invitation I to EN, but `expires_at NOW` (commit point after this line).

**When**
- `svc._register_with_invitation(db, name="Nia New", email=EN, password=PW, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == EXPIRED_INV`.
2. nothing written.

### AUTH-RI-11 — an invitation one microsecond from expiry is accepted
- **Rules:** `_register_with_invitation` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. invitation I to EN, but `expires_at NOW + US`.

**When**
- `user, ws, pair, messages = svc._register_with_invitation(db, name="Nia New", email=EN, password=PW, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. returns: `ws.id == W1.id`.
2. re-read I: `status == "accepted"`.

### AUTH-RI-12 — an accepted invitation cannot be used again
- **Rules:** `_register_with_invitation` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. invitation I to EN, but `status "accepted"` (commit point after this line).

**When**
- `svc._register_with_invitation(db, name="Nia New", email=EN, password=PW, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Invitation has already been accepted"`.
2. nothing written.

### AUTH-RI-13 — a cancelled invitation is refused
- **Rules:** `_register_with_invitation` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. invitation I to EN, but `status "cancelled"` (commit point after this line).

**When**
- `svc._register_with_invitation(db, name="Nia New", email=EN, password=PW, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Invitation has already been cancelled"`.
2. nothing written.

### AUTH-RI-14 — an invitation sent to another email is refused
- **Rules:** `_register_with_invitation` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. invitation I to `f"other.{TAG}@acme.com"` (commit point after this line).

**When**
- `svc._register_with_invitation(db, name="Nia New", email=EN, password=PW, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == f"This invitation was sent to other.{TAG}@acme.com. You cannot accept it with {EN}."`.
2. nothing written.

### AUTH-RI-15 — the invited email in other capitals is accepted
- **Rules:** `_register_with_invitation` R1 (email ignoring capitals)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. invitation I to EN.

**When**
- `user, ws, pair, messages = svc._register_with_invitation(db, name="Nia New", email=f"New.{TAG}@acme.com", password=PW, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. returns: `ws.id == W1.id`.
2. count: one `WorkspaceMember` row with `workspace_id == W1.id`, `user_id == user.id`.

### AUTH-RI-16 — other pending invitations to the same email are cancelled
- **Rules:** `_register_with_invitation` R3 (BUG-1874 of the manager)
- **Kind:** bug
- **Expect:** xfail BUG-1874
- **Fails today on:** Then 2 (the other invitation stays pending)

**Given**
1. invitation I to EN.
2. invitation J to EN, but `role "viewer"`.

**When**
- `user, ws, pair, messages = svc._register_with_invitation(db, name="Nia New", email=EN, password=PW, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. re-read I: `status == "accepted"`.
2. re-read J: `status == "cancelled"`.

### AUTH-RI-17 — flushed, never committed
- **Rules:** `_register_with_invitation` Returns (flushed)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. invitation I to EN (commit point after this line).

**When**
- flush only: `user, ws, pair, messages = svc._register_with_invitation(db, name="Nia New", email=EN, password=PW, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. returns (inside): `profile(EN)` is not None.
2. mock called (inside): `cm.call_count == 0`.
3. count (after `sp.rollback()`): `profile(EN) is None`.
4. re-read I (after `sp.rollback()`): `status == "pending"`.

## `AuthService._register_with_new_workspace`

### AUTH-RW-01 — the workspace uses the default plan and the email for billing
- **Rules:** `_register_with_new_workspace` R3, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. PD.

**When**
- `user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=EN, password=PW, workspace_name=WSNAME, user_agent=AGENT, ip_address=IP)` under clock.

**Then**
1. returns: `ws.slug == SL`, `ws.name == WSNAME`.
2. re-read ws: `subscription_plan_id == PD.id`, `billing_email == EN`, `owner_user_id == user.id`.
3. count: one `WorkspaceMember` row with `workspace_id == ws.id`.
4. re-read that row: `user_id == user.id`, `role == "owner"`, `status == "active"`, `position is None`.

### AUTH-RW-02 — one workspace_created audit row names the plan
- **Rules:** `_register_with_new_workspace` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PD.

**When**
- `user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=EN, password=PW, workspace_name=WSNAME, user_agent=AGENT, ip_address=IP)` under clock.

**Then**
1. returns: `ws.slug == SL`.
2. audit: audit(ws, "workspace_created") has exactly 1 row.
3. audit: that row `user_id == user.id`, `metadata_json == {"plan": f"free-{TAG}"}`.

### AUTH-RW-03 — the workspace_created row carries the client's address and browser
- **Rules:** `_register_with_new_workspace` R5 [BUG-2563]
- **Kind:** bug
- **Expect:** xfail BUG-2563
- **Fails today on:** Then 3 (both columns are NULL)

**Given**
1. PD.

**When**
- `user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=EN, password=PW, workspace_name=WSNAME, user_agent=AGENT, ip_address=IP)` under clock.

**Then**
1. returns: `ws.slug == SL`.
2. audit: audit(ws, "workspace_created") has exactly 1 row.
3. audit: that row `ip_address == "203.0.113.7"`, `user_agent == "Mozilla/5.0 Test"`.

### AUTH-RW-04 — messages: profile, then workspace with the name as passed
- **Rules:** `_register_with_new_workspace` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. PD.

**When**
- `user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=EN, password=PW, workspace_name=f"R&D Ltd. {TAG}")` under clock.

**Then**
1. returns: `msgs(messages) == [("success", "User profile created"), ("success", f"Workspace 'R&D Ltd. {TAG}' created successfully with 14-day trial")]`.

### AUTH-RW-05 — the session is for the new workspace
- **Rules:** `_register_with_new_workspace` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PD.

**When**
- `user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=EN, password=PW, workspace_name=WSNAME, user_agent=AGENT, ip_address=IP)` under clock.

**Then**
1. returns: `claims(pair.access_token)["workspace_id"] == ws.id`.
2. re-read: `row_of(pair).workspace_id == ws.id`, `row_of(pair).user_id == user.id`.
3. re-read: `re.fullmatch(HEX32, row_of(pair).family_id) is not None`.

### AUTH-RW-06 — the new workspace gets its seeded departments
- **Rules:** `_register_with_new_workspace` R4 (seeded data, manager R9)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PD.

**When**
- `user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=EN, password=PW, workspace_name=WSNAME)` under clock.

**Then**
1. returns: `ws.id is not None`.
2. count: `db.scalar(text("SELECT count(*) FROM departments WHERE workspace_id = :w"), {"w": ws.id}) == 5`.

### AUTH-RW-07 — spaces and underscores become dashes
- **Rules:** `_register_with_new_workspace` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. PD.

**When**
- `user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=EN, password=PW, workspace_name=f"Acme Steel_Works {TAG}")` under clock.

**Then**
1. returns: `ws.slug == f"acme-steel-works-{TAG}"`.

### AUTH-RW-08 — runs of dashes collapse and outer dashes go
- **Rules:** `_register_with_new_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PD.

**When**
- `user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=EN, password=PW, workspace_name=f"  A -- B {TAG}  ")` under clock.

**Then**
1. returns: `ws.slug == f"a-b-{TAG}"`.
2. re-read ws: `name == f"  A -- B {TAG}  "`.

### AUTH-RW-09 — symbols are dropped, the name is stored as typed
- **Rules:** `_register_with_new_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PD.

**When**
- `user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=EN, password=PW, workspace_name=f"R&D Ltd. {TAG}")` under clock.

**Then**
1. returns: `ws.slug == f"rd-ltd-{TAG}"`.
2. re-read ws: `name == f"R&D Ltd. {TAG}"`.

### AUTH-RW-10 — a name of exactly 100 slug characters keeps them all
- **Rules:** `_register_with_new_workspace` R2a (the edge that holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PD.

**When**
- `user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=EN, password=PW, workspace_name=TAG + "y" * 92)` under clock.

**Then**
1. returns: `ws.slug == TAG + "y" * 92`.
2. returns: `len(ws.slug) == 100`.

### AUTH-RW-11 — a non-ASCII digit acts as a separator
- **Rules:** `_register_with_new_workspace` R2a [BUG-2566]
- **Kind:** bug
- **Expect:** xfail BUG-2566
- **Fails today on:** Then 1 (the call raises ValidationError: `²` is kept and breaks the slug pattern)

**Given**
1. PD.

**When**
- `user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=EN, password=PW, workspace_name=f"Plant² Two {TAG}")` under clock.

**Then**
1. returns: `ws.slug == f"plant-two-{TAG}"`.
2. re-read ws: `name == f"Plant² Two {TAG}"`.

### AUTH-RW-12 — Bengali letters act as separators
- **Rules:** `_register_with_new_workspace` R2a [BUG-2566]
- **Kind:** bug
- **Expect:** xfail BUG-2566
- **Fails today on:** Then 1 (the call raises ValidationError: Bengali letters are kept)

**Given**
1. PD.

**When**
- `user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=EN, password=PW, workspace_name=f"কারখানা {TAG}")` under clock.

**Then**
1. returns: `ws.slug == TAG`.

### AUTH-RW-13 — a name with no ASCII letter or digit gets the slug "workspace"
- **Rules:** `_register_with_new_workspace` R2a [BUG-2566]
- **Kind:** bug
- **Expect:** xfail BUG-2566
- **Fails today on:** Then 1 (the call raises ValidationError: the slug is empty)

**Given**
1. PD.

**When**
- `user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=EN, password=PW, workspace_name="!!!")` under clock.

**Then**
1. returns: `re.fullmatch(r"workspace(-[0-9]+)?", ws.slug) is not None`.
2. re-read ws: `name == "!!!"`.

### AUTH-RW-14 — a long name is cut to 100 characters
- **Rules:** `_register_with_new_workspace` R2a [BUG-2566]
- **Kind:** bug
- **Expect:** xfail BUG-2566
- **Fails today on:** Then 1 (the call raises ValidationError: 150 characters)

**Given**
1. PD.

**When**
- `user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=EN, password=PW, workspace_name=TAG + "y" * 142)` under clock.

**Then**
1. returns: `ws.slug == TAG + "y" * 92`.

### AUTH-RW-15 — the cut leaves no trailing dash
- **Rules:** `_register_with_new_workspace` R2a [BUG-2566]
- **Kind:** bug
- **Expect:** xfail BUG-2566
- **Fails today on:** Then 1 (the call raises ValidationError: 150 characters)

**Given**
1. PD.

**When**
- `user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=EN, password=PW, workspace_name=TAG + "y" * 91 + " " + "z" * 50)` under clock.

**Then**
1. returns: `ws.slug == TAG + "y" * 91`.

### AUTH-RW-16 — a taken slug gets -2
- **Rules:** `_register_with_new_workspace` R3a [BUG-2567]
- **Kind:** bug
- **Expect:** xfail BUG-2567
- **Fails today on:** Then 1 (the call raises ValueError: slug already taken)

**Given**
1. PD.
2. W3 = `make_workspace(db, slug=SL)`.

**When**
- `user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=EN, password=PW, workspace_name=WSNAME)` under clock.

**Then**
1. returns: `ws.slug == f"{SL}-2"`.
2. re-read W3: `slug == SL`.

### AUTH-RW-17 — with -2 taken too, -3 is used
- **Rules:** `_register_with_new_workspace` R3a [BUG-2567]
- **Kind:** bug
- **Expect:** xfail BUG-2567
- **Fails today on:** Then 1 (the call raises ValueError: slug already taken)

**Given**
1. PD.
2. W3 = `make_workspace(db, slug=SL)`.
3. W4 = `make_workspace(db, slug=f"{SL}-2")`.

**When**
- `user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=EN, password=PW, workspace_name=WSNAME)` under clock.

**Then**
1. returns: `ws.slug == f"{SL}-3"`.

### AUTH-RW-18 — a taken 100-character slug is cut so that the suffix fits
- **Rules:** `_register_with_new_workspace` R3a [BUG-2567]
- **Kind:** bug
- **Expect:** xfail BUG-2567
- **Fails today on:** Then 1 (the call raises ValueError: slug already taken)

**Given**
1. PD.
2. W3 = `make_workspace(db, slug=TAG + "y" * 92)`.

**When**
- `user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=EN, password=PW, workspace_name=TAG + "y" * 92)` under clock.

**Then**
1. returns: `ws.slug == TAG + "y" * 90 + "-2"`.
2. returns: `len(ws.slug) == 100`.

### AUTH-RW-19 — only the exact slug counts as taken
- **Rules:** `_register_with_new_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PD.
2. W3 = `make_workspace(db, slug=f"{SL}-2")`.

**When**
- `user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=EN, password=PW, workspace_name=WSNAME)` under clock.

**Then**
1. returns: `ws.slug == SL`.

### AUTH-RW-20 — flushed, never committed
- **Rules:** `_register_with_new_workspace` Returns (flushed)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PD.

**When**
- flush only: `user, ws, pair, messages = svc._register_with_new_workspace(db, name="Nia New", email=EN, password=PW, workspace_name=WSNAME)` under clock.

**Then**
1. returns (inside): `db.scalar(select(func.count()).select_from(Workspace).where(Workspace.slug == SL)) == 1`.
2. mock called (inside): `cm.call_count == 0`.
3. count (after `sp.rollback()`): `db.scalar(select(func.count()).select_from(Workspace).where(Workspace.slug == SL)) == 0`.

## `AuthService.login_user`

### AUTH-LI-01 — the right password signs the user in
- **Rules:** `login_user` R1, R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. `UA.hashed_password = HPW; db.flush()` (commit point after this line).

**When**
- `user, pair, messages = svc.login_user(db, email=EA, password=PW, user_agent=AGENT, ip_address=IP)` under clock.

**Then**
1. returns: `user.id == UA.id`.
2. returns: `msgs(messages) == [("success", "Welcome back, Ann Lee!")]`.
3. returns: `isinstance(pair, TokenPair)`.

### AUTH-LI-02 — the login session has no workspace and a new family
- **Rules:** `login_user` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `UA.hashed_password = HPW; db.flush()` (commit point after this line).

**When**
- `user, pair, messages = svc.login_user(db, email=EA, password=PW, user_agent=AGENT, ip_address=IP)` under clock.

**Then**
1. returns: `"workspace_id" not in claims(pair.access_token)`.
2. returns: `claims(pair.access_token)["sub"] == str(UA.id)`, `claims(pair.access_token)["email"] == EA`, `claims(pair.access_token)["exp"] == EXP15`.
3. re-read: `row_of(pair).workspace_id is None`, `row_of(pair).user_agent == "Mozilla/5.0 Test"`, `row_of(pair).ip_address == "203.0.113.7"`.
4. re-read: `re.fullmatch(HEX32, row_of(pair).family_id) is not None`.

### AUTH-LI-03 — the session is committed once
- **Rules:** `login_user` R2 (TC1)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `UA.hashed_password = HPW; db.flush()` (commit point after this line).

**When**
- spies: `user, pair, messages = svc.login_user(db, email=EA, password=PW)` under clock.

**Then**
1. returns: `user.id == UA.id`.
2. mock called: `cm.call_count == 1`.
3. mock called: `rb.call_count == 0`.
4. committed: `tokens(UA) == 1`.

### AUTH-LI-04 — earlier sessions are not touched
- **Rules:** `login_user` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `UA.hashed_password = HPW; db.flush()`.
2. token K (RAW1) (commit point after this line).

**When**
- `user, pair, messages = svc.login_user(db, email=EA, password=PW)` under clock.

**Then**
1. returns: `user.id == UA.id`.
2. unchanged: unchanged(K).
3. count: `tokens(UA) == 2`.
4. count: `live(UA) == 2`.

### AUTH-LI-05 — the email of the user is used, not a neighbour's with the same password
- **Rules:** `login_user` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `UA.hashed_password = HPW; UB.hashed_password = HPW; db.flush()` (commit point after this line).

**When**
- `user, pair, messages = svc.login_user(db, email=EB, password=PW)` under clock.

**Then**
1. returns: `user.id == UB.id`.
2. returns: `claims(pair.access_token)["sub"] == str(UB.id)`.
3. count: `tokens(UA) == 0`.

### AUTH-LI-06 — an unknown email: the generic refusal, no write, no rollback
- **Rules:** `login_user` R1, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. `UA.hashed_password = HPW; db.flush()` (commit point after this line).
2. extra row X.

**When**
- spies: `svc.login_user(db, email=EN, password=PW)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == BADLOGIN`.
2. mock called: `rb.call_count == 0`.
3. mock called: `cm.call_count == 0`.
4. session: `X in db`.
5. count: x_kept.
6. count: the number of `refresh_tokens` rows equals its value at the commit point.

### AUTH-LI-07 — a wrong password: the same refusal
- **Rules:** `login_user` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. `UA.hashed_password = HPW; db.flush()` (commit point after this line).

**When**
- `svc.login_user(db, email=EA, password=PW2)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == BADLOGIN`.
2. count: `tokens(UA) == 0`.

### AUTH-LI-08 — an empty stored hash: the same refusal
- **Rules:** `login_user` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. `UA.hashed_password = ""; db.flush()` (commit point after this line).

**When**
- `svc.login_user(db, email=EA, password=PW)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == BADLOGIN`.
2. count: `tokens(UA) == 0`.

### AUTH-LI-09 — a malformed stored hash: the same refusal
- **Rules:** `login_user` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. UA's standing `hashed_password` `"not-a-real-hash"` (commit point after this line).

**When**
- `svc.login_user(db, email=EA, password=PW)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == BADLOGIN`.
2. count: `tokens(UA) == 0`.

### AUTH-LI-10 — the email in other capitals finds the account
- **Rules:** `login_user` R1 [BUG-1860]
- **Kind:** bug
- **Expect:** xfail BUG-1860
- **Fails today on:** Then 1 (the call raises ValueError: the lookup is exact)

**Given**
1. P = `make_profile(db, email=MIXED, name="Ann Mixed", hashed_password=HPW)` (commit point after this line).

**When**
- `user, pair, messages = svc.login_user(db, email=LOWER, password=PW)` under clock.

**Then**
1. returns: `user.id == P.id`.
2. count: `tokens(P) == 1`.

### AUTH-LI-11 — a failing commit rolls back and keeps no session
- **Rules:** `login_user` R3 (TC4)
- **Kind:** error
- **Expect:** pass

**Given**
1. `UA.hashed_password = HPW; db.flush()` (commit point after this line).

**When**
- failing commit: `svc.login_user(db, email=EA, password=PW)` under clock.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `tokens(UA) == 0`.

### AUTH-LI-12 — a user with an active membership still gets a session with no workspace
- **Rules:** `login_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UO.hashed_password = HPW; db.flush()` (UO's standing owner row MO in W1 is active; commit point after this line).

**When**
- `user, pair, messages = svc.login_user(db, email=EO, password=PW)` under clock.

**Then**
1. returns: `user.id == UO.id`.
2. returns: `"workspace_id" not in claims(pair.access_token)`.
3. re-read: `row_of(pair).workspace_id is None`.

### AUTH-LI-13 — a failing issue rolls back and discards pending changes, without a commit
- **Rules:** `login_user` R3 (TC3)
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. `UA.hashed_password = HPW; db.flush()` (commit point after this line).
2. extra row X.

**When**
- spies: `svc.login_user(db, email=EA, password=PW)` under failing issue, inside `with pytest.raises(RuntimeError) as exc:`.

**Then**
1. raises: `str(exc.value) == "clock down"`.
2. count: x_gone (straight after the call, before any rollback by the test).
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 1`.
5. count: `tokens(UA) == 0`.

## `AuthService.switch_workspace`

### AUTH-SW-01 — an active member gets a session for that workspace
- **Rules:** `switch_workspace` R1, R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. MA = member(UA, "viewer") (commit point after this line).

**When**
- `ws, pair, messages = svc.switch_workspace(db, user_id=UA.id, workspace_id=W1.id, user_agent=AGENT, ip_address=IP)` under clock.

**Then**
1. returns: `ws.id == W1.id`.
2. returns: `msgs(messages) == [("success", "Switched to workspace: Acme Works")]`.
3. returns: `claims(pair.access_token)["workspace_id"] == W1.id`, `claims(pair.access_token)["sub"] == str(UA.id)`.
4. re-read: `row_of(pair).workspace_id == W1.id`, `row_of(pair).user_agent == "Mozilla/5.0 Test"`, `row_of(pair).ip_address == "203.0.113.7"`.
5. re-read: `re.fullmatch(HEX32, row_of(pair).family_id) is not None`.

### AUTH-SW-02 — the switch is committed once
- **Rules:** `switch_workspace` R3 (TC1)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MA = member(UA, "viewer") (commit point after this line).

**When**
- spies: `ws, pair, messages = svc.switch_workspace(db, user_id=UA.id, workspace_id=W1.id)` under clock.

**Then**
1. returns: `ws.id == W1.id`.
2. mock called: `cm.call_count == 1`.
3. mock called: `rb.call_count == 0`.
4. committed: `tokens(UA) == 1`.

### AUTH-SW-03 — no membership: refused, nothing written, no rollback
- **Rules:** `switch_workspace` R1, R6, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No member row of UA (standing rows only; commit point after this line).
2. extra row X.

**When**
- spies: `svc.switch_workspace(db, user_id=UA.id, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == NOTMEM`.
2. mock called: `rb.call_count == 0`.
3. session: `X in db`.
4. count: x_kept.
5. count: `tokens(UA) == 0`.

### AUTH-SW-04 — an inactive (removed) member is refused
- **Rules:** `switch_workspace` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. MA = member(UA, "viewer", status="inactive") (commit point after this line).

**When**
- `svc.switch_workspace(db, user_id=UA.id, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == NOTMEM`.
2. count: `tokens(UA) == 0`.

### AUTH-SW-05 — a suspended member is refused
- **Rules:** `switch_workspace` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. MA = member(UA, "viewer", status="suspended") (commit point after this line).

**When**
- `svc.switch_workspace(db, user_id=UA.id, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == NOTMEM`.
2. count: `tokens(UA) == 0`.

### AUTH-SW-06 — an invited (not yet active) member is refused
- **Rules:** `switch_workspace` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. MA = member(UA, "viewer", status="invited") (commit point after this line).

**When**
- `svc.switch_workspace(db, user_id=UA.id, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == NOTMEM`.
2. count: `tokens(UA) == 0`.

### AUTH-SW-07 — status "Active" in capitals is not active
- **Rules:** `switch_workspace` R1 (exact compare)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA = member(UA, "viewer", status="Active") (commit point after this line).

**When**
- `svc.switch_workspace(db, user_id=UA.id, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == NOTMEM`.
2. count: `tokens(UA) == 0`.

### AUTH-SW-08 — an unknown workspace gets the same message
- **Rules:** `switch_workspace` R1 (HR-16)
- **Kind:** error
- **Expect:** pass

**Given**
1. MA = member(UA, "viewer") (commit point after this line).

**When**
- `svc.switch_workspace(db, user_id=UA.id, workspace_id=MISSING)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == NOTMEM`.
2. count: `tokens(UA) == 0`.

### AUTH-SW-09 — active rows in W0 and W2 do not open W1
- **Rules:** `switch_workspace` R1 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. member(UA, "viewer", ws=W0).
2. member(UA, "viewer", ws=W2) (commit point after this line).

**When**
- `svc.switch_workspace(db, user_id=UA.id, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == NOTMEM`.
2. count: `tokens(UA) == 0`.

### AUTH-SW-10 — W1's member row does not belong to another user
- **Rules:** `switch_workspace` R1 (by workspace and user together)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. member(UA, "viewer").
2. member(UC, "viewer") (commit point after this line).

**When**
- `svc.switch_workspace(db, user_id=UB.id, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == NOTMEM`.
2. count: `tokens(UB) == 0`.

### AUTH-SW-11 — the role is not checked: a finance member may switch
- **Rules:** `switch_workspace` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. MA = member(UA, "finance") (commit point after this line).

**When**
- `ws, pair, messages = svc.switch_workspace(db, user_id=UA.id, workspace_id=W1.id)` under clock.

**Then**
1. returns: `ws.id == W1.id`.
2. committed: `tokens(UA) == 1`.

### AUTH-SW-12 — earlier refresh tokens are not revoked
- **Rules:** `switch_workspace` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MA = member(UA, "viewer").
2. token K (RAW1), but `workspace_id W2.id` (commit point after this line).

**When**
- `ws, pair, messages = svc.switch_workspace(db, user_id=UA.id, workspace_id=W1.id)` under clock.

**Then**
1. returns: `ws.id == W1.id`.
2. unchanged: unchanged(K).
3. count: `live(UA) == 2`.

### AUTH-SW-13 — a failing commit rolls back and keeps no session
- **Rules:** `switch_workspace` R6 (TC4)
- **Kind:** error
- **Expect:** pass

**Given**
1. MA = member(UA, "viewer") (commit point after this line).

**When**
- failing commit: `svc.switch_workspace(db, user_id=UA.id, workspace_id=W1.id)` under clock.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `tokens(UA) == 0`.

### AUTH-SW-14 — a failing issue rolls back and discards pending changes, without a commit
- **Rules:** `switch_workspace` R6 (TC3)
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. MA = member(UA, "viewer") (commit point after this line).
2. extra row X.

**When**
- spies: `svc.switch_workspace(db, user_id=UA.id, workspace_id=W1.id)` under failing issue, inside `with pytest.raises(RuntimeError) as exc:`.

**Then**
1. raises: `str(exc.value) == "clock down"`.
2. count: x_gone (straight after the call, before any rollback by the test).
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 1`.
5. count: `tokens(UA) == 0`.

## `AuthService.refresh_access_token`

### AUTH-RF-01 — a live token is exchanged for a new pair in the same family
- **Rules:** `refresh_access_token` R6, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. token K (RAW1), but `workspace_id W1.id` (commit point after this line).

**When**
- `pair, messages = svc.refresh_access_token(db, raw_refresh_token=RAW1, user_agent=AGENT, ip_address=IP)` under clock.

**Then**
1. returns: `messages == []`.
2. returns: `pair.refresh_token != RAW1`.
3. re-read: `row_of(pair).family_id == FAM1`, `row_of(pair).workspace_id == W1.id`, `row_of(pair).user_id == UA.id`.
4. re-read: `row_of(pair).user_agent == "Mozilla/5.0 Test"`, `row_of(pair).ip_address == "203.0.113.7"`, `row_of(pair).expires_at == NOW14`.
5. returns: `claims(pair.access_token)["workspace_id"] == W1.id`, `claims(pair.access_token)["sub"] == str(UA.id)`.

### AUTH-RF-02 — the old row is revoked, linked to its successor and touched
- **Rules:** `refresh_access_token` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. token K (RAW1) (commit point after this line).

**When**
- `pair, messages = svc.refresh_access_token(db, raw_refresh_token=RAW1)` under clock.

**Then**
1. returns: `messages == []`.
2. re-read K: `revoked_at == NOW`, `replaced_by_id == row_of(pair).id`, `last_used_at == NOW`.

### AUTH-RF-03 — a session without a workspace stays without one
- **Rules:** `refresh_access_token` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. token K (RAW1) (commit point after this line).

**When**
- `pair, messages = svc.refresh_access_token(db, raw_refresh_token=RAW1)` under clock.

**Then**
1. returns: `"workspace_id" not in claims(pair.access_token)`.
2. re-read: `row_of(pair).workspace_id is None`.

### AUTH-RF-04 — the rotation is committed once
- **Rules:** `refresh_access_token` R6 (TC1)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. token K (RAW1) (commit point after this line).

**When**
- spies: `pair, messages = svc.refresh_access_token(db, raw_refresh_token=RAW1)` under clock.

**Then**
1. returns: `messages == []`.
2. mock called: `cm.call_count == 1`.
3. mock called: `rb.call_count == 0`.
4. committed: `tokens(UA) == 2`.
5. committed: K's `revoked_at == NOW`.

### AUTH-RF-05 — a removed member can still refresh (membership is not re-checked)
- **Rules:** `refresh_access_token` R6 (D11)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. member(UA, "viewer", status="inactive").
2. token K (RAW1), but `workspace_id W1.id` (commit point after this line).

**When**
- `pair, messages = svc.refresh_access_token(db, raw_refresh_token=RAW1)` under clock.

**Then**
1. returns: `claims(pair.access_token)["workspace_id"] == W1.id`.
2. re-read: `row_of(pair).workspace_id == W1.id`.

### AUTH-RF-06 — a suspended member can still refresh
- **Rules:** `refresh_access_token` R6 (D11)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. member(UA, "viewer", status="suspended").
2. token K (RAW1), but `workspace_id W1.id` (commit point after this line).

**When**
- `pair, messages = svc.refresh_access_token(db, raw_refresh_token=RAW1)` under clock.

**Then**
1. returns: `claims(pair.access_token)["workspace_id"] == W1.id`.
2. re-read K: `revoked_at == NOW`.

### AUTH-RF-07 — an unknown token: refused, rolled back, pending changes discarded
- **Rules:** `refresh_access_token` R1, R8 (TC3), Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. token K (RAW1) (commit point after this line).
2. extra row X.

**When**
- spies: `svc.refresh_access_token(db, raw_refresh_token=f"nope-{TAG}")` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Invalid refresh token"`.
2. mock called: `rb.call_count == 1`.
3. count: x_gone.
4. unchanged: unchanged(K).
5. nothing written.

### AUTH-RF-08 — an empty token is unknown
- **Rules:** `refresh_access_token` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. token K (RAW1) (commit point after this line).

**When**
- `svc.refresh_access_token(db, raw_refresh_token="")` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Invalid refresh token"`.
2. nothing written.

### AUTH-RF-09 — a replayed rotated token revokes its whole family, committed
- **Rules:** `refresh_access_token` R2, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. S = `RefreshToken(user_id=UA.id, token_hash=hash_refresh_token(RAW2), family_id=FAM1, workspace_id=None, expires_at=LATER)`.
2. token K (RAW1), but `revoked_at EARLY`, `replaced_by_id S.id`.
3. T = `RefreshToken(user_id=UA.id, token_hash=hash_refresh_token(RAW3), family_id=FAM2, workspace_id=None, expires_at=LATER)`.
4. V = `RefreshToken(user_id=UB.id, token_hash=hash_refresh_token(RAW4), family_id=FAM2, workspace_id=None, expires_at=LATER)` (commit point after this line).

**When**
- spies: `svc.refresh_access_token(db, raw_refresh_token=RAW1)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Refresh token reuse detected; all sessions for this login have been revoked"`.
2. mock called: `cm.call_count == 1`.
3. committed: S's `revoked_at == NOW`.
4. committed: K's `revoked_at == EARLY`.
5. committed: T's `revoked_at is None`.
6. committed: V's `revoked_at is None`.
7. committed: the number of `refresh_tokens` rows equals its value at the commit point.

### AUTH-RF-10 — reuse is checked before expiry
- **Rules:** `refresh_access_token` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = `RefreshToken(user_id=UA.id, token_hash=hash_refresh_token(RAW2), family_id=FAM1, workspace_id=None, expires_at=LATER)`.
2. token K (RAW1), but `expires_at PAST`, `revoked_at EARLY`, `replaced_by_id S.id` (commit point after this line).

**When**
- `svc.refresh_access_token(db, raw_refresh_token=RAW1)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Refresh token reuse detected; all sessions for this login have been revoked"`.
2. committed: S's `revoked_at == NOW`.

### AUTH-RF-11 — a revoked token without successor is refused and nothing changes
- **Rules:** `refresh_access_token` R4, R8, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. S = `RefreshToken(user_id=UA.id, token_hash=hash_refresh_token(RAW2), family_id=FAM1, workspace_id=None, expires_at=LATER)`.
2. token K (RAW1), but `revoked_at EARLY` (commit point after this line).

**When**
- spies: `svc.refresh_access_token(db, raw_refresh_token=RAW1)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Refresh token has been revoked"`.
2. mock called: `rb.call_count == 1`.
3. unchanged: unchanged(K).
4. unchanged: unchanged(S).
5. nothing written.

### AUTH-RF-12 — a token expiring exactly now is expired
- **Rules:** `refresh_access_token` R4, Errors
- **Kind:** boundary
- **Expect:** pass

**Given**
1. token K (RAW1), but `expires_at NOW` (commit point after this line).

**When**
- `svc.refresh_access_token(db, raw_refresh_token=RAW1)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Refresh token has expired"`.
2. unchanged: unchanged(K).
3. nothing written.

### AUTH-RF-13 — a token one microsecond from expiry still refreshes
- **Rules:** `refresh_access_token` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. token K (RAW1), but `expires_at NOW + US` (commit point after this line).

**When**
- `pair, messages = svc.refresh_access_token(db, raw_refresh_token=RAW1)` under clock.

**Then**
1. returns: `messages == []`.
2. re-read K: `revoked_at == NOW`.

### AUTH-RF-14 — the same token presented twice in turn: the second is reuse
- **Rules:** `refresh_access_token` R6, R7 (the sequential replay), R2
- **Kind:** error
- **Expect:** pass

**Given**
1. token K (RAW1) (commit point after this line).
2. `first, _ = svc.refresh_access_token(db, raw_refresh_token=RAW1)` under clock.

**When**
- `svc.refresh_access_token(db, raw_refresh_token=RAW1)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Refresh token reuse detected; all sessions for this login have been revoked"`.
2. committed: `row_of(first).revoked_at == NOW`.
3. committed: `live(UA) == 0`.
4. committed: `tokens(UA) == 2`.

### AUTH-RF-15 — the presented row is read with a row lock
- **Rules:** `refresh_access_token` R7 [BUG-2560]
- **Kind:** bug
- **Expect:** xfail BUG-2560
- **Fails today on:** Then 2 (no `FOR UPDATE` on the lookup)

**Given**
1. token K (RAW1) (commit point after this line).
2. recorder.

**When**
- `pair, messages = svc.refresh_access_token(db, raw_refresh_token=RAW1)` under clock.

**Then**
1. returns: exactly one recorded `SELECT` contains `FROM refresh_tokens` and `token_hash` and comes before the first `INSERT INTO refresh_tokens`; call it `sql`.
2. returns: `"FOR UPDATE" in sql.upper()`.

### AUTH-RF-16 — a failing commit leaves the old token live and no successor
- **Rules:** `refresh_access_token` R8 (TC4)
- **Kind:** error
- **Expect:** pass

**Given**
1. token K (RAW1) (commit point after this line).

**When**
- failing commit: `svc.refresh_access_token(db, raw_refresh_token=RAW1)` under clock.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(K).
4. count: `tokens(UA) == 1`.

### AUTH-RF-17 — the reuse commit also commits other pending changes
- **Rules:** `refresh_access_token` R2a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S = `RefreshToken(user_id=UA.id, token_hash=hash_refresh_token(RAW2), family_id=FAM1, workspace_id=None, expires_at=LATER)`.
2. token K (RAW1), but `revoked_at EARLY`, `replaced_by_id S.id` (commit point after this line).
3. extra row X.

**When**
- `svc.refresh_access_token(db, raw_refresh_token=RAW1)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Refresh token reuse detected; all sessions for this login have been revoked"`.
2. committed: x_kept.
3. committed: S's `revoked_at == NOW`.

## `AuthService.logout_session`

### AUTH-LO-01 — a live token is revoked alone, with no successor
- **Rules:** `logout_session` R4, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. token K (RAW1).
2. S = `RefreshToken(user_id=UA.id, token_hash=hash_refresh_token(RAW2), family_id=FAM1, workspace_id=None, expires_at=LATER)` (commit point after this line).

**When**
- `messages = svc.logout_session(db, raw_refresh_token=RAW1)` under clock.

**Then**
1. returns: `msgs(messages) == [("success", "Logged out.")]`.
2. re-read K: `revoked_at == NOW`, `replaced_by_id is None`, `last_used_at is None`.
3. unchanged: unchanged(S).

### AUTH-LO-02 — the logout is committed
- **Rules:** `logout_session` R6 (TC1)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. token K (RAW1) (commit point after this line).

**When**
- spies: `messages = svc.logout_session(db, raw_refresh_token=RAW1)` under clock.

**Then**
1. returns: `msgs(messages) == [("success", "Logged out.")]`.
2. mock called: `cm.call_count == 1`.
3. mock called: `rb.call_count == 0`.
4. committed: K's `revoked_at == NOW`.

### AUTH-LO-03 — an unknown token is no error and changes nothing
- **Rules:** `logout_session` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. token K (RAW1) (commit point after this line).

**When**
- `messages = svc.logout_session(db, raw_refresh_token=f"nope-{TAG}")` under clock.

**Then**
1. returns: `msgs(messages) == [("success", "Logged out.")]`.
2. unchanged: unchanged(K).
3. nothing written.

### AUTH-LO-04 — an already revoked token keeps its first stamp
- **Rules:** `logout_session` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. token K (RAW1), but `revoked_at EARLY` (commit point after this line).

**When**
- `messages = svc.logout_session(db, raw_refresh_token=RAW1)` under clock.

**Then**
1. returns: `msgs(messages) == [("success", "Logged out.")]`.
2. re-read K: `revoked_at == EARLY`.

### AUTH-LO-05 — an expired, unrevoked token is revoked
- **Rules:** `logout_session` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. token K (RAW1), but `expires_at PAST` (commit point after this line).

**When**
- `messages = svc.logout_session(db, raw_refresh_token=RAW1)` under clock.

**Then**
1. returns: `msgs(messages) == [("success", "Logged out.")]`.
2. re-read K: `revoked_at == NOW`.

### AUTH-LO-06 — no token: info message, and the session is still committed
- **Rules:** `logout_session` R5, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. token K (RAW1) (commit point after this line).
2. extra row X.

**When**
- spies: `messages = svc.logout_session(db, raw_refresh_token=None)` under clock.

**Then**
1. returns: `msgs(messages) == [("info", "No refresh token provided; nothing to revoke.")]`.
2. mock called: `cm.call_count == 1`.
3. committed: x_kept.
4. committed: K's `revoked_at is None`.

### AUTH-LO-07 — an empty token is "no token"
- **Rules:** `logout_session` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. token K (RAW1) (commit point after this line).

**When**
- `messages = svc.logout_session(db, raw_refresh_token="")` under clock.

**Then**
1. returns: `msgs(messages) == [("info", "No refresh token provided; nothing to revoke.")]`.
2. unchanged: unchanged(K).

### AUTH-LO-08 — all devices: every unrevoked row of the user, in every family and workspace
- **Rules:** `logout_session` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T0 = `RefreshToken(user_id=U0.id, token_hash=hash_refresh_token(RAW5), family_id=FAM2, workspace_id=None, expires_at=LATER)`.
2. token K (RAW1), but `workspace_id W1.id`.
3. K2 = `RefreshToken(user_id=UA.id, token_hash=hash_refresh_token(RAW2), family_id=FAM2, workspace_id=W2.id, expires_at=LATER)`.
4. K3 = `RefreshToken(user_id=UA.id, token_hash=hash_refresh_token(RAW3), family_id=FAM2, workspace_id=None, expires_at=PAST)`.
5. K4 = `RefreshToken(user_id=UA.id, token_hash=hash_refresh_token(RAW4), family_id=FAM1, workspace_id=None, expires_at=LATER, revoked_at=EARLY)`.
6. TB = `RefreshToken(user_id=UB.id, token_hash=hash_refresh_token(RAW6), family_id=FAM1, workspace_id=None, expires_at=LATER)` (commit point after this line).

**When**
- `messages = svc.logout_session(db, raw_refresh_token=None, user_id=UA.id, all_devices=True)` under clock.

**Then**
1. returns: `msgs(messages) == [("success", "Revoked 3 active session(s).")]`.
2. re-read K, K2, K3: each `revoked_at == NOW`.
3. re-read K4: `revoked_at == EARLY`.
4. unchanged: unchanged(T0).
5. unchanged: unchanged(TB).

### AUTH-LO-09 — all devices ignores the token presented
- **Rules:** `logout_session` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. token K (RAW1).
2. TB = `RefreshToken(user_id=UB.id, token_hash=hash_refresh_token(RAW6), family_id=FAM2, workspace_id=None, expires_at=LATER)` (commit point after this line).

**When**
- `messages = svc.logout_session(db, raw_refresh_token=RAW6, user_id=UA.id, all_devices=True)` under clock.

**Then**
1. returns: `msgs(messages) == [("success", "Revoked 1 active session(s).")]`.
2. re-read K: `revoked_at == NOW`.
3. unchanged: unchanged(TB).

### AUTH-LO-10 — all devices with no session left says 0
- **Rules:** `logout_session` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No refresh token of UA (standing rows only; commit point after this line).

**When**
- spies: `messages = svc.logout_session(db, raw_refresh_token=None, user_id=UA.id, all_devices=True)` under clock.

**Then**
1. returns: `msgs(messages) == [("success", "Revoked 0 active session(s).")]`.
2. mock called: `cm.call_count == 1`.

### AUTH-LO-11 — all devices without a user: refused, rolled back, nothing changed
- **Rules:** `logout_session` R2, R6, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. token K (RAW1) (commit point after this line).
2. extra row X.

**When**
- spies: `svc.logout_session(db, raw_refresh_token=RAW1, user_id=None, all_devices=True)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Cannot logout all devices without an authenticated user"`.
2. mock called: `rb.call_count == 1`.
3. count: x_gone.
4. unchanged: unchanged(K).

### AUTH-LO-12 — a failing commit leaves the token live
- **Rules:** `logout_session` R6 (TC4)
- **Kind:** error
- **Expect:** pass

**Given**
1. token K (RAW1) (commit point after this line).

**When**
- failing commit: `svc.logout_session(db, raw_refresh_token=RAW1)` under clock.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read K: `revoked_at is None`.

## `AuthService.request_password_reset`

### AUTH-FP-01 — an unknown email gets a token and the generic message
- **Rules:** `request_password_reset` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No profile with email EN (standing rows only).

**When**
- `token, expires_at, messages = svc.request_password_reset(db, email=EN)` under clock.

**Then**
1. returns: `re.fullmatch(r"[A-Za-z0-9_-]{43}", token) is not None`.
2. returns: `expires_at == NOW + timedelta(hours=1)`.
3. returns: `msgs(messages) == [("info", "If an account with that email exists, a password reset link has been sent.")]`.

### AUTH-FP-02 — an account gets a token and the placeholder messages, with the email as passed
- **Rules:** `request_password_reset` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = `make_profile(db, email=MIXED, name="Ann Mixed")`.

**When**
- `token, expires_at, messages = svc.request_password_reset(db, email=MIXED)` under clock.

**Then**
1. returns: `re.fullmatch(r"[A-Za-z0-9_-]{43}", token) is not None`.
2. returns: `expires_at == NOW + timedelta(hours=1)`.
3. returns: `msgs(messages) == [("success", f"Password reset token generated for {MIXED}. Token expires in 1 hour."), ("info", "NOTE: Token storage not yet implemented. Store this token securely and validate on reset.")]`.

### AUTH-FP-03 — the email in other capitals finds the account
- **Rules:** `request_password_reset` R1 [BUG-1860]
- **Kind:** bug
- **Expect:** xfail BUG-1860
- **Fails today on:** Then 2 (the generic message is returned: the lookup is exact)

**Given**
1. P = `make_profile(db, email=MIXED, name="Ann Mixed")`.

**When**
- `token, expires_at, messages = svc.request_password_reset(db, email=LOWER)` under clock.

**Then**
1. returns: `expires_at == NOW + timedelta(hours=1)`.
2. returns: `msgs(messages)[0] == ("success", f"Password reset token generated for {LOWER}. Token expires in 1 hour.")`.

### AUTH-FP-04 — nothing is stored, committed or rolled back
- **Rules:** `request_password_reset` R4 (TC6)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Standing rows only (commit point after this line).
2. extra row X.

**When**
- spies: `token, expires_at, messages = svc.request_password_reset(db, email=EA)` under clock.

**Then**
1. returns: `len(token) == 43`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.
5. unchanged: unchanged(UA).

## `AuthService.reset_password`

### AUTH-RP-01 — any input is refused as not implemented, nothing changes
- **Rules:** `reset_password` R1, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only (commit point after this line).

**When**
- spies: `svc.reset_password(db, reset_token="anything", new_password=PW2)`.

**Then**
1. raises: `NotImplementedError`, `str(exc.value) == "Password reset requires a password_reset_tokens table. Please implement password_reset model, DAO, and schema first."`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. unchanged: unchanged(UA).

## `AuthService.reset_password_by_admin`

> In every card of this section the target is a plain member of W1 only, never the caller, never an owner-role member, never a platform admin, and never a member of another workspace. Those targets are the *pending OQ-34* cards of the next section.

### AUTH-AR-01 — the owner sets a member's new password
- **Rules:** `reset_password_by_admin` R6, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. member(UB, "ground-team").
2. `UB.hashed_password = HPW; db.flush()` (commit point after this line).

**When**
- `user, messages = svc.reset_password_by_admin(db, admin_user_id=UO.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. returns: `user.id == UB.id`.
2. re-read UB: `verify_password(PW2, hashed_password) is True`.
3. re-read UB: `verify_password(PW, hashed_password) is False`.

### AUTH-AR-02 — every unrevoked session of the target is revoked, and the messages say how many
- **Rules:** `reset_password_by_admin` R8, R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. member(UB, "ground-team").
2. B1 = `RefreshToken(user_id=UB.id, token_hash=hash_refresh_token(RAW1), family_id=FAM1, workspace_id=W1.id, expires_at=LATER)`.
3. B2 = `RefreshToken(user_id=UB.id, token_hash=hash_refresh_token(RAW2), family_id=FAM2, workspace_id=W2.id, expires_at=LATER)`.
4. B3 = `RefreshToken(user_id=UB.id, token_hash=hash_refresh_token(RAW3), family_id=FAM2, workspace_id=None, expires_at=PAST)`.
5. B4 = `RefreshToken(user_id=UB.id, token_hash=hash_refresh_token(RAW4), family_id=FAM1, workspace_id=None, expires_at=LATER, revoked_at=EARLY)`.
6. A1 = `RefreshToken(user_id=UA.id, token_hash=hash_refresh_token(RAW5), family_id=FAM2, workspace_id=W1.id, expires_at=LATER)`.
7. O1 = `RefreshToken(user_id=UO.id, token_hash=hash_refresh_token(RAW6), family_id=FAM1, workspace_id=W1.id, expires_at=LATER)` (commit point after this line).

**When**
- `user, messages = svc.reset_password_by_admin(db, admin_user_id=UO.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. returns: `msgs(messages) == [("success", f"Password reset successfully for user: {EB}"), ("info", "Revoked 3 active session(s); user must log in again."), ("info", "User should be notified of password change via email.")]`.
2. re-read B1, B2, B3: each `revoked_at == NOW`.
3. re-read B4: `revoked_at == EARLY`.
4. unchanged: unchanged(A1).
5. unchanged: unchanged(O1).

### AUTH-AR-03 — with no session to revoke, the count line is left out
- **Rules:** `reset_password_by_admin` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. member(UB, "ground-team") (commit point after this line).

**When**
- `user, messages = svc.reset_password_by_admin(db, admin_user_id=UO.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. returns: `msgs(messages) == [("success", f"Password reset successfully for user: {EB}"), ("info", "User should be notified of password change via email.")]`.

### AUTH-AR-04 — the reset is committed once
- **Rules:** `reset_password_by_admin` R10 (TC1)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. member(UB, "ground-team") (commit point after this line).

**When**
- spies: `user, messages = svc.reset_password_by_admin(db, admin_user_id=UO.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. returns: `user.id == UB.id`.
2. mock called: `cm.call_count == 1`.
3. mock called: `rb.call_count == 0`.
4. committed: `verify_password(PW2, profile(EB).hashed_password) is True`.

### AUTH-AR-05 — a caller with no membership: refused, rolled back, nothing changed
- **Rules:** `reset_password_by_admin` R1, R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UB, "ground-team").
2. B1 = `RefreshToken(user_id=UB.id, token_hash=hash_refresh_token(RAW1), family_id=FAM1, workspace_id=W1.id, expires_at=LATER)` (commit point after this line).
3. extra row X.

**When**
- spies: `svc.reset_password_by_admin(db, admin_user_id=UA.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Admin is not a member of this workspace"`.
2. mock called: `rb.call_count == 1`.
3. count: x_gone.
4. unchanged: unchanged(UB).
5. unchanged: unchanged(B1).

### AUTH-AR-06 — an inactive owner row is not a membership
- **Rules:** `reset_password_by_admin` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UA, "owner", status="inactive").
2. member(UB, "ground-team") (commit point after this line).

**When**
- `svc.reset_password_by_admin(db, admin_user_id=UA.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Admin is not a member of this workspace"`.
2. unchanged: unchanged(UB).

### AUTH-AR-07 — a suspended owner row is not a membership
- **Rules:** `reset_password_by_admin` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UA, "owner", status="suspended").
2. member(UB, "ground-team") (commit point after this line).

**When**
- `svc.reset_password_by_admin(db, admin_user_id=UA.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Admin is not a member of this workspace"`.
2. unchanged: unchanged(UB).

### AUTH-AR-08 — the owner of W0 (lower id) has no grant in W1
- **Rules:** `reset_password_by_admin` R1 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. member(UB, "ground-team") (commit point after this line).

**When**
- `svc.reset_password_by_admin(db, admin_user_id=U0.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Admin is not a member of this workspace"`.
2. unchanged: unchanged(UB).

### AUTH-AR-09 — the owner of W2 (higher id) has no grant in W1
- **Rules:** `reset_password_by_admin` R1 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. member(UB, "ground-team") (commit point after this line).

**When**
- `svc.reset_password_by_admin(db, admin_user_id=U2.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Admin is not a member of this workspace"`.
2. unchanged: unchanged(UB).

### AUTH-AR-10 — a manager may not reset passwords
- **Rules:** `reset_password_by_admin` R2, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UA, "manager").
2. member(UB, "ground-team") (commit point after this line).
3. extra row X.

**When**
- spies: `svc.reset_password_by_admin(db, admin_user_id=UA.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Only workspace owners can reset user passwords"`.
2. mock called: `rb.call_count == 1`.
3. count: x_gone.
4. unchanged: unchanged(UB).

### AUTH-AR-11 — role "Owner" in capitals is not owner
- **Rules:** `reset_password_by_admin` R2 (exact compare)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. member(UA, "Owner").
2. member(UB, "ground-team") (commit point after this line).

**When**
- `svc.reset_password_by_admin(db, admin_user_id=UA.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Only workspace owners can reset user passwords"`.
2. unchanged: unchanged(UB).

### AUTH-AR-12 — a ground-team-manager may not reset passwords
- **Rules:** `reset_password_by_admin` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UA, "ground-team-manager").
2. member(UB, "ground-team") (commit point after this line).

**When**
- `svc.reset_password_by_admin(db, admin_user_id=UA.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Only workspace owners can reset user passwords"`.
2. unchanged: unchanged(UB).

### AUTH-AR-13 — a finance member may not reset passwords
- **Rules:** `reset_password_by_admin` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UA, "finance").
2. member(UB, "ground-team") (commit point after this line).

**When**
- `svc.reset_password_by_admin(db, admin_user_id=UA.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Only workspace owners can reset user passwords"`.
2. unchanged: unchanged(UB).

### AUTH-AR-14 — being named owner_user_id does not count, only the member role
- **Rules:** `reset_password_by_admin` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `W1.owner_user_id = UA.id; db.flush()`.
2. member(UA, "manager").
3. member(UB, "ground-team") (commit point after this line).

**When**
- `svc.reset_password_by_admin(db, admin_user_id=UA.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Only workspace owners can reset user passwords"`.
2. unchanged: unchanged(UB).

### AUTH-AR-15 — a platform admin with a manager role gets no exception
- **Rules:** `reset_password_by_admin` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UA.is_platform_admin = True; db.flush()`.
2. member(UA, "manager").
3. member(UB, "ground-team") (commit point after this line).

**When**
- `svc.reset_password_by_admin(db, admin_user_id=UA.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Only workspace owners can reset user passwords"`.
2. unchanged: unchanged(UB).

### AUTH-AR-16 — a target with no membership: refused, nothing changed
- **Rules:** `reset_password_by_admin` R3, R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UB, "ground-team") (commit point after this line).
2. extra row X.

**When**
- spies: `svc.reset_password_by_admin(db, admin_user_id=UO.id, target_user_id=UC.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Target user is not a member of this workspace"`.
2. mock called: `rb.call_count == 1`.
3. count: x_gone.
4. unchanged: unchanged(UC).

### AUTH-AR-17 — a suspended target is refused
- **Rules:** `reset_password_by_admin` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UB, "ground-team", status="suspended") (commit point after this line).

**When**
- `svc.reset_password_by_admin(db, admin_user_id=UO.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Target user is not a member of this workspace"`.
2. unchanged: unchanged(UB).

### AUTH-AR-18 — a removed (inactive) target is refused
- **Rules:** `reset_password_by_admin` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UB, "ground-team", status="inactive") (commit point after this line).

**When**
- `svc.reset_password_by_admin(db, admin_user_id=UO.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Target user is not a member of this workspace"`.
2. unchanged: unchanged(UB).

### AUTH-AR-19 — a target who is a member of W0 only is refused
- **Rules:** `reset_password_by_admin` R3 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. member(UB, "ground-team", ws=W0) (commit point after this line).

**When**
- `svc.reset_password_by_admin(db, admin_user_id=UO.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Target user is not a member of this workspace"`.
2. unchanged: unchanged(UB).

### AUTH-AR-20 — a target who is a member of W2 only is refused
- **Rules:** `reset_password_by_admin` R3 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. member(UB, "ground-team", ws=W2) (commit point after this line).

**When**
- `svc.reset_password_by_admin(db, admin_user_id=UO.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Target user is not a member of this workspace"`.
2. unchanged: unchanged(UB).

### AUTH-AR-21 — an unknown target id is refused as not a member
- **Rules:** `reset_password_by_admin` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UB, "ground-team") (commit point after this line).

**When**
- `svc.reset_password_by_admin(db, admin_user_id=UO.id, target_user_id=MISSING, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Target user is not a member of this workspace"`.
2. nothing written.

### AUTH-AR-22 — the caller is checked before the target
- **Rules:** `reset_password_by_admin` R5 (R1 before R3)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only (commit point after this line).

**When**
- `svc.reset_password_by_admin(db, admin_user_id=UA.id, target_user_id=UC.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Admin is not a member of this workspace"`.
2. nothing written.

### AUTH-AR-23 — the role is checked before the target
- **Rules:** `reset_password_by_admin` R5 (R2 before R3)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. member(UA, "manager") (commit point after this line).

**When**
- `svc.reset_password_by_admin(db, admin_user_id=UA.id, target_user_id=UC.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Only workspace owners can reset user passwords"`.
2. nothing written.

### AUTH-AR-24 — a password over 72 bytes is refused and no session is revoked
- **Rules:** `reset_password_by_admin` R6, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UB, "ground-team").
2. `UB.hashed_password = HPW; db.flush()`.
3. B1 = `RefreshToken(user_id=UB.id, token_hash=hash_refresh_token(RAW1), family_id=FAM1, workspace_id=W1.id, expires_at=LATER)` (commit point after this line).

**When**
- spies: `svc.reset_password_by_admin(db, admin_user_id=UO.id, target_user_id=UB.id, new_password="a" * 73, workspace_id=W1.id)` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Password exceeds bcrypt's 72-byte limit"`.
2. mock called: `rb.call_count == 1`.
3. unchanged: unchanged(UB).
4. unchanged: unchanged(B1).

### AUTH-AR-25 — a password of exactly 72 bytes is accepted
- **Rules:** `reset_password_by_admin` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. member(UB, "ground-team") (commit point after this line).

**When**
- `user, messages = svc.reset_password_by_admin(db, admin_user_id=UO.id, target_user_id=UB.id, new_password="a" * 72, workspace_id=W1.id)` under clock.

**Then**
1. returns: `user.id == UB.id`.
2. re-read UB: `verify_password("a" * 72, hashed_password) is True`.

### AUTH-AR-26 — the reset leaves one audit row with no password in it
- **Rules:** `reset_password_by_admin` R9 [BUG-2569]
- **Kind:** bug
- **Expect:** xfail BUG-2569
- **Fails today on:** Then 2 (no audit row is written)

**Given**
1. member(UB, "ground-team").
2. B1 = `RefreshToken(user_id=UB.id, token_hash=hash_refresh_token(RAW1), family_id=FAM1, workspace_id=W1.id, expires_at=LATER)` (commit point after this line).

**When**
- `user, messages = svc.reset_password_by_admin(db, admin_user_id=UO.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. returns: `user.id == UB.id`.
2. audit: audit(W1, "member_password_reset") has exactly 1 row.
3. audit: that row `user_id == UO.id`, `metadata_json == {"target_user_id": UB.id, "sessions_revoked": 1}`.
4. audit: `PW2 not in str(that row.metadata_json)`.
5. audit: `profile(EB).hashed_password not in str(that row.metadata_json)`.

### AUTH-AR-27 — a failing commit keeps the old password and the sessions
- **Rules:** `reset_password_by_admin` R10 (TC4)
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UB, "ground-team").
2. `UB.hashed_password = HPW; db.flush()`.
3. B1 = `RefreshToken(user_id=UB.id, token_hash=hash_refresh_token(RAW1), family_id=FAM1, workspace_id=W1.id, expires_at=LATER)` (commit point after this line).

**When**
- failing commit: `svc.reset_password_by_admin(db, admin_user_id=UO.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read UB: `verify_password(PW, hashed_password) is True`.
4. unchanged: unchanged(B1).

## `AuthService.reset_password_by_admin` — pending OQ-34 (R7, today's behaviour)

> These three cards describe today's behaviour of R7, which the owner deferred to the permissions work (OQ-34). They are the only cards whose target is the caller, an owner-role member, a platform admin, or a member of another workspace. If OQ-34 is answered "bug", only these cards change. Each test's docstring carries `pending OQ-34`.

### AUTH-P34-01 — an owner may reset their own password without the old one
- **Rules:** `reset_password_by_admin` R7 (pending OQ-34)
- **Kind:** happy
- **Expect:** pass

**Given**
1. `UO.hashed_password = HPW; db.flush()` (commit point after this line).

**When**
- `user, messages = svc.reset_password_by_admin(db, admin_user_id=UO.id, target_user_id=UO.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. returns: `user.id == UO.id`.
2. committed: `verify_password(PW2, profile(EO).hashed_password) is True`.

### AUTH-P34-02 — an owner may reset another owner-role member
- **Rules:** `reset_password_by_admin` R7 (pending OQ-34)
- **Kind:** happy
- **Expect:** pass

**Given**
1. member(UA, "owner") (commit point after this line).

**When**
- `user, messages = svc.reset_password_by_admin(db, admin_user_id=UO.id, target_user_id=UA.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. returns: `user.id == UA.id`.
2. committed: `verify_password(PW2, profile(EA).hashed_password) is True`.

### AUTH-P34-03 — a platform admin who owns another workspace can be reset; the password is global
- **Rules:** `reset_password_by_admin` R7 (pending OQ-34)
- **Kind:** happy
- **Expect:** pass

**Given**
1. `UB.is_platform_admin = True; UB.hashed_password = HPW; db.flush()`.
2. member(UB, "ground-team").
3. W3 = `make_workspace(db, subscription_plan_id=PL2.id, owner_user_id=UB.id)`.
4. MB3 = member(UB, "owner", ws=W3) (commit point after this line).

**When**
- `user, messages = svc.reset_password_by_admin(db, admin_user_id=UO.id, target_user_id=UB.id, new_password=PW2, workspace_id=W1.id)` under clock.

**Then**
1. returns: `user.id == UB.id`.
2. committed: `verify_password(PW2, profile(EB).hashed_password) is True`.
3. committed: `profile(EB).is_platform_admin is True`.
4. unchanged: unchanged(MB3).

## `AuthService.validate_invitation_token`

### AUTH-VI-01 — a valid token shows exactly what the invitation offers
- **Rules:** `validate_invitation_token` R5, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. invitation I to `f"inv.{TAG}@acme.com"`, but `role "viewer"`, `position "Supervisor"`.

**When**
- `details, messages = svc.validate_invitation_token(db, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. returns: `details == {"invitation_id": I.id, "email": f"inv.{TAG}@acme.com", "role": "viewer", "position": "Supervisor", "workspace_id": W1.id, "workspace_name": "Acme Works", "expires_at": "2099-01-01T00:00:00"}`.
2. returns: `msgs(messages) == [("success", "Valid invitation to join 'Acme Works' as viewer")]`.

### AUTH-VI-02 — no position shows None
- **Rules:** `validate_invitation_token` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. invitation I to `f"inv.{TAG}@acme.com"`.

**When**
- `details, messages = svc.validate_invitation_token(db, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. returns: `details["position"] is None`.
2. returns: `details["role"] == "member"`.

### AUTH-VI-03 — the token decides the workspace: W2's invitation shows W2
- **Rules:** `validate_invitation_token` R1, R5 (any workspace)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. invitation I to `f"inv.{TAG}@acme.com"`.
2. invitation J to `f"inv.{TAG}@acme.com"`, but `workspace_id W2.id`, `invited_by_user_id U2.id`.

**When**
- `details, messages = svc.validate_invitation_token(db, invitation_token=f"inv-J-{TAG}")` under clock.

**Then**
1. returns: `details["invitation_id"] == J.id`.
2. returns: `details["workspace_id"] == W2.id`, `details["workspace_name"] == "Tom Works"`.

### AUTH-VI-04 — an unknown token is refused
- **Rules:** `validate_invitation_token` R1, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. invitation I to `f"inv.{TAG}@acme.com"`.

**When**
- `svc.validate_invitation_token(db, invitation_token=f"inv-Z-{TAG}")` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Invalid invitation token"`.

### AUTH-VI-05 — the token in capitals is unknown
- **Rules:** `validate_invitation_token` R1 (exact)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. invitation I to `f"inv.{TAG}@acme.com"`.

**When**
- `svc.validate_invitation_token(db, invitation_token=f"INV-I-{TAG.upper()}")` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Invalid invitation token"`.

### AUTH-VI-06 — a part of the token is unknown
- **Rules:** `validate_invitation_token` R1 (exact)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. invitation I to `f"inv.{TAG}@acme.com"`.

**When**
- `svc.validate_invitation_token(db, invitation_token=f"inv-I-{TAG}"[:-1])` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Invalid invitation token"`.

### AUTH-VI-07 — an invitation expiring exactly now is expired
- **Rules:** `validate_invitation_token` R2 [BUG-2561]
- **Kind:** bug
- **Expect:** xfail BUG-2561
- **Fails today on:** Then 1 (no error: at exactly `expires_at` the preview says valid)

**Given**
1. invitation I to `f"inv.{TAG}@acme.com"`, but `expires_at NOW`.

**When**
- `svc.validate_invitation_token(db, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == EXPIRED_INV`.

### AUTH-VI-08 — one microsecond past expiry is expired
- **Rules:** `validate_invitation_token` R2, Errors
- **Kind:** boundary
- **Expect:** pass

**Given**
1. invitation I to `f"inv.{TAG}@acme.com"`, but `expires_at NOW - US`.

**When**
- `svc.validate_invitation_token(db, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == EXPIRED_INV`.

### AUTH-VI-09 — one microsecond before expiry is valid
- **Rules:** `validate_invitation_token` R2, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. invitation I to `f"inv.{TAG}@acme.com"`, but `expires_at NOW + US`.

**When**
- `details, messages = svc.validate_invitation_token(db, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. returns: `details["expires_at"] == "2026-03-05T12:00:00.000001"`.

### AUTH-VI-10 — expiry is checked before status
- **Rules:** `validate_invitation_token` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. invitation I to `f"inv.{TAG}@acme.com"`, but `status "accepted"`, `expires_at PAST`.

**When**
- `svc.validate_invitation_token(db, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == EXPIRED_INV`.

### AUTH-VI-11 — an accepted invitation says so
- **Rules:** `validate_invitation_token` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. invitation I to `f"inv.{TAG}@acme.com"`, but `status "accepted"`.

**When**
- `svc.validate_invitation_token(db, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Invitation has already been accepted"`.

### AUTH-VI-12 — a cancelled invitation says so
- **Rules:** `validate_invitation_token` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. invitation I to `f"inv.{TAG}@acme.com"`, but `status "cancelled"`.

**When**
- `svc.validate_invitation_token(db, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Invitation has already been cancelled"`.

### AUTH-VI-13 — status "Pending" in capitals is not pending
- **Rules:** `validate_invitation_token` R4 (exact)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. invitation I to `f"inv.{TAG}@acme.com"`, but `status "Pending"`.

**When**
- `svc.validate_invitation_token(db, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Invitation has already been Pending"`.

### AUTH-VI-14 — the preview writes, commits and rolls back nothing
- **Rules:** `validate_invitation_token` R6 (TC6)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. invitation I to `f"inv.{TAG}@acme.com"` (commit point after this line).
2. extra row X.

**When**
- spies: `details, messages = svc.validate_invitation_token(db, invitation_token=f"inv-I-{TAG}")` under clock.

**Then**
1. returns: `details["invitation_id"] == I.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.
5. unchanged: unchanged(I).

### AUTH-VI-15 — a refusal does not roll back either
- **Rules:** `validate_invitation_token` R6 (TC6)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. invitation I to `f"inv.{TAG}@acme.com"` (commit point after this line).
2. extra row X.

**When**
- spies: `svc.validate_invitation_token(db, invitation_token=f"inv-Z-{TAG}")` under clock.

**Then**
1. raises: `ValueError`, `str(exc.value) == "Invalid invitation token"`.
2. mock called: `rb.call_count == 0`.
3. session: `X in db`.

## `AuthService.update_current_user`

> Every card here runs with **dr** and the stamp settings of Conventions. `UA` is the signed-in user, loaded in `db`. "UA stamp S" in a Given = `UA.saved_stamp = S; db.flush()`.

### AUTH-ME-01 — nothing sent: the same user, no commit, no rollback, no Cloudinary call
- **Rules:** `update_current_user` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. UA stamp IMG(OWN(UA)) (commit point after this line).
2. extra row X.

**When**
- spies: `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate())`.

**Then**
1. returns: `result is UA`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. mock called: `dr.call_count == 0`.
5. session: `X in db`.

### AUTH-ME-02 — a new name is saved, other fields stay
- **Rules:** `update_current_user` R2, R3, R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. `UA.timezone = "Asia/Dhaka"; db.flush()`.
2. UA stamp VEC (commit point after this line).

**When**
- spies: `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(name="Ann Smith"))`.

**Then**
1. returns: `result.id == UA.id`, `result.name == "Ann Smith"`.
2. returns: `not_expired(result)`.
3. mock called: `cm.call_count == 1`.
4. committed: UA's `name == "Ann Smith"`, `timezone == "Asia/Dhaka"`, `saved_stamp == VEC`.

### AUTH-ME-03 — name null leaves the name as it is
- **Rules:** `update_current_user` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. UA's standing name `"Ann Lee"` (commit point after this line).

**When**
- `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(name=None))`.

**Then**
1. returns: `result.id == UA.id`.
2. re-read UA: `name == "Ann Lee"`.

### AUTH-ME-04 — a whitespace-only name is refused by the schema
- **Rules:** `update_current_user` R3a [BUG-1406]
- **Kind:** bug
- **Expect:** xfail BUG-1406
- **Fails today on:** Then 1 (no error: the schema accepts it)

**Given**
1. Nothing (target `schema`).

**When**
- build `ProfileMeUpdate(name="   ")`.

**Then**
1. raises: `PydanticValidationError`.

### AUTH-ME-05 — an empty name is refused by the schema
- **Rules:** `update_current_user` R3a [BUG-1406]
- **Kind:** bug
- **Expect:** xfail BUG-1406
- **Fails today on:** Then 1 (no error: the schema accepts it)

**Given**
1. Nothing (target `schema`).

**When**
- build `ProfileMeUpdate(name="")`.

**Then**
1. raises: `PydanticValidationError`.

### AUTH-ME-06 — the name is stored trimmed, inner spaces kept
- **Rules:** `update_current_user` R3a [BUG-1406]
- **Kind:** bug
- **Expect:** xfail BUG-1406
- **Fails today on:** Then 2 (the name is stored with its outer spaces)

**Given**
1. UA's standing name `"Ann Lee"` (commit point after this line).

**When**
- `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(name="  Ann  Smith  "))`.

**Then**
1. returns: `result.id == UA.id`.
2. re-read UA: `name == "Ann  Smith"`.

### AUTH-ME-07 — a new time zone is saved, the name stays
- **Rules:** `update_current_user` R2, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. `UA.timezone = "Asia/Dhaka"; db.flush()` (commit point after this line).

**When**
- `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(timezone="Europe/London"))`.

**Then**
1. returns: `result.timezone == "Europe/London"`.
2. committed: UA's `timezone == "Europe/London"`, `name == "Ann Lee"`.

### AUTH-ME-08 — time zone null clears it
- **Rules:** `update_current_user` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UA.timezone = "Asia/Dhaka"; db.flush()` (commit point after this line).

**When**
- `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(timezone=None))`.

**Then**
1. returns: `result.timezone is None`.
2. committed: UA's `timezone is None`.

### AUTH-ME-09 — an empty time zone clears it
- **Rules:** `update_current_user` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UA.timezone = "Asia/Dhaka"; db.flush()` (commit point after this line).

**When**
- `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(timezone=""))`.

**Then**
1. returns: `result.timezone is None`.
2. committed: UA's `timezone is None`.

### AUTH-ME-10 — a whitespace time zone clears it
- **Rules:** `update_current_user` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UA.timezone = "Asia/Dhaka"; db.flush()` (commit point after this line).

**When**
- `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(timezone="   "))`.

**Then**
1. returns: `result.timezone is None`.
2. committed: UA's `timezone is None`.

### AUTH-ME-11 — removing an image stamp clears it and deletes the user's picture
- **Rules:** `update_current_user` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. UA stamp IMG(OWN(UA)) (commit point after this line).

**When**
- `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp=None))`.

**Then**
1. returns: `result.saved_stamp is None`.
2. committed: UA's `saved_stamp is None`.
3. mock called: `dr.call_count == 1`.
4. mock called: `dr.call_args.kwargs["public_id"] == OWN(UA)`.

### AUTH-ME-12 — removing a vector stamp deletes nothing in Cloudinary
- **Rules:** `update_current_user` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. UA stamp VEC (commit point after this line).

**When**
- `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp=None))`.

**Then**
1. returns: `result.saved_stamp is None`.
2. committed: UA's `saved_stamp is None`.
3. mock called: `dr.call_count == 0`.

### AUTH-ME-13 — removing when there is no stamp deletes nothing
- **Rules:** `update_current_user` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. UA's standing `saved_stamp` is None (commit point after this line).

**When**
- `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp=None))`.

**Then**
1. returns: `result.saved_stamp is None`.
2. mock called: `dr.call_count == 0`.

### AUTH-ME-14 — a vector stamp is stored in its cleaned form
- **Rules:** `update_current_user` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. UA's standing `saved_stamp` is None (commit point after this line).

**When**
- `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp={"kind": "vector", "extra": 1, "strokes": [{"color": "#000000", "width": 0.5, "points": [], "junk": "x"}], "viewBox": {"width": 100, "height": 50}}))`.

**Then**
1. returns: `result.saved_stamp == VEC`.
2. committed: UA's `saved_stamp == VEC`.
3. mock called: `dr.call_count == 0`.

### AUTH-ME-15 — the user's own minted image stamp is stored
- **Rules:** `update_current_user` R6, R6a (the form that stays accepted)
- **Kind:** happy
- **Expect:** pass

**Given**
1. UA's standing `saved_stamp` is None (commit point after this line).

**When**
- `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp=IMG(OWN(UA))))`.

**Then**
1. returns: `set(result.saved_stamp) == {"kind", "public_id", "url", "width", "height"}`.
2. committed: UA's `saved_stamp["kind"] == "image"`, `saved_stamp["public_id"] == OWN(UA)`, `saved_stamp["width"] == 10`, `saved_stamp["height"] == 10`.
3. mock called: `dr.call_count == 0`.

### AUTH-ME-16 — the stored url is the one the server builds
- **Rules:** `update_current_user` R8 [BUG-1866]
- **Kind:** bug
- **Expect:** xfail BUG-1866
- **Fails today on:** Then 2 (the client's url is stored)

**Given**
1. UA's standing `saved_stamp` is None (commit point after this line).

**When**
- `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp=IMG(OWN(UA))))`.

**Then**
1. returns: `result.saved_stamp["public_id"] == OWN(UA)`.
2. returns: `result.saved_stamp["url"].startswith(SRV)`.
3. committed: UA's `saved_stamp["url"].startswith(SRV)`.
4. committed: `OWN(UA) in UA's saved_stamp["url"]`.
5. committed: `"https://tracker.example/p.png" not in str(UA's saved_stamp)`.

### AUTH-ME-17 — an invalid stamp kind is refused and the name sent with it is not saved
- **Rules:** `update_current_user` R6, R9 (TC3), Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. UA stamp IMG(OWN(UA)) (commit point after this line).
2. extra row X.

**When**
- spies: `svc.update_current_user(db, user=UA, update=ProfileMeUpdate(name="Ann Smith", saved_stamp={"kind": "sticker"}))`.

**Then**
1. raises: `ValueError`, `str(exc.value) == KIND_MSG`.
2. mock called: `rb.call_count == 1`.
3. mock called: `dr.call_count == 0`.
4. count: x_gone.
5. unchanged: unchanged(UA).

### AUTH-ME-18 — an image stamp of width 0 is a validation error and nothing is saved
- **Rules:** `update_current_user` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. UA's standing `saved_stamp` is None (commit point after this line).

**When**
- `svc.update_current_user(db, user=UA, update=ProfileMeUpdate(timezone="Europe/London", saved_stamp={"kind": "image", "public_id": OWN(UA), "url": "https://tracker.example/p.png", "width": 0, "height": 10}))`.

**Then**
1. raises: `PydanticValidationError`.
2. mock called: `dr.call_count == 0`.
3. unchanged: unchanged(UA).

### AUTH-ME-19 — another (higher-id) user's stamp id is refused
- **Rules:** `update_current_user` R6a [BUG-1864]
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (no error: any public_id is stored)

**Given**
1. UA's standing `saved_stamp` is None (commit point after this line).

**When**
- `svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp=IMG(OWN(UB))))`.

**Then**
1. raises: `ValueError`, `str(exc.value) == FOREIGN`.
2. unchanged: unchanged(UA).

### AUTH-ME-20 — another (lower-id) user's stamp id is refused
- **Rules:** `update_current_user` R6a [BUG-1864]
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (no error: any public_id is stored)

**Given**
1. UA's standing `saved_stamp` is None (commit point after this line).

**When**
- `svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp=IMG(OWN(U0))))`.

**Then**
1. raises: `ValueError`, `str(exc.value) == FOREIGN`.
2. unchanged: unchanged(UA).

### AUTH-ME-21 — an attachment's id is refused
- **Rules:** `update_current_user` R6a [BUG-1864]
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (no error: any public_id is stored)

**Given**
1. UA's standing `saved_stamp` is None (commit point after this line).

**When**
- `svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp=IMG(ATT)))`.

**Then**
1. raises: `ValueError`, `str(exc.value) == FOREIGN`.
2. unchanged: unchanged(UA).

### AUTH-ME-22 — the production form is foreign in development
- **Rules:** `update_current_user` R6a [BUG-1864]
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (no error: any public_id is stored)

**Given**
1. UA's standing `saved_stamp` is None (commit point after this line).

**When**
- `svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp=IMG(f"profiles/{UA.id}/stamp-{TOKEN}")))`.

**Then**
1. raises: `ValueError`, `str(exc.value) == FOREIGN`.
2. unchanged: unchanged(UA).

### AUTH-ME-23 — the own id with a trailing newline is refused
- **Rules:** `update_current_user` R6a [BUG-1864]
- **Kind:** bug
- **Expect:** xfail BUG-1864
- **Fails today on:** Then 1 (no error: any public_id is stored)

**Given**
1. UA's standing `saved_stamp` is None (commit point after this line).

**When**
- `svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp=IMG(OWN(UA) + "\n")))`.

**Then**
1. raises: `ValueError`, `str(exc.value) == FOREIGN`.
2. unchanged: unchanged(UA).

### AUTH-ME-24 — replacing an image with another image deletes the old picture
- **Rules:** `update_current_user` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. UA stamp IMG(OWN(UA)) (commit point after this line).

**When**
- `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp=IMG(OWN2(UA))))`.

**Then**
1. returns: `result.saved_stamp["public_id"] == OWN2(UA)`.
2. committed: UA's `saved_stamp["public_id"] == OWN2(UA)`.
3. mock called: `dr.call_count == 1`.
4. mock called: `dr.call_args.kwargs["public_id"] == OWN(UA)`.

### AUTH-ME-25 — the same image again deletes nothing
- **Rules:** `update_current_user` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. UA stamp IMG(OWN(UA)) (commit point after this line).

**When**
- `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp=IMG(OWN(UA))))`.

**Then**
1. returns: `result.saved_stamp["public_id"] == OWN(UA)`.
2. mock called: `dr.call_count == 0`.

### AUTH-ME-26 — replacing an image with a drawing saves the drawing
- **Rules:** `update_current_user` R6, R7b (part independent of BUG-2568)
- **Kind:** happy
- **Expect:** pass

**Given**
1. UA stamp IMG(OWN(UA)) (commit point after this line).

**When**
- `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp=VEC))`.

**Then**
1. returns: `result.saved_stamp == VEC`.
2. committed: UA's `saved_stamp == VEC`.

### AUTH-ME-27 — replacing an image with a drawing deletes the old picture
- **Rules:** `update_current_user` R7b [BUG-2568]
- **Kind:** bug
- **Expect:** xfail BUG-2568
- **Fails today on:** Then 2 (no delete: the picture is orphaned)

**Given**
1. UA stamp IMG(OWN(UA)) (commit point after this line).

**When**
- `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp=VEC))`.

**Then**
1. returns: `result.saved_stamp == VEC`.
2. mock called: `dr.call_count == 1`.
3. mock called: `dr.call_args.kwargs["public_id"] == OWN(UA)`.

### AUTH-ME-28 — removing a stamp that names another user's picture still clears it
- **Rules:** `update_current_user` R5, R7a (part independent of BUG-1865)
- **Kind:** happy
- **Expect:** pass

**Given**
1. UA stamp IMG(OWN(UB)) (commit point after this line).

**When**
- `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp=None))`.

**Then**
1. returns: `result.saved_stamp is None`.
2. committed: UA's `saved_stamp is None`.

### AUTH-ME-29 — another user's picture named by an old stamp is never deleted
- **Rules:** `update_current_user` R7a [BUG-1865]
- **Kind:** bug
- **Expect:** xfail BUG-1865
- **Fails today on:** Then 2 (the other user's picture is deleted)

**Given**
1. UA stamp IMG(OWN(UB)) (commit point after this line).

**When**
- `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp=None))`.

**Then**
1. returns: `result.saved_stamp is None`.
2. mock called: `dr.call_count == 0`.

### AUTH-ME-30 — an attachment named by an old stamp is not deleted on replace
- **Rules:** `update_current_user` R7, R7a [BUG-1865]
- **Kind:** bug
- **Expect:** xfail BUG-1865
- **Fails today on:** Then 2 (the attachment's file is deleted)

**Given**
1. UA stamp IMG(ATT) (commit point after this line).

**When**
- `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp=IMG(OWN(UA))))`.

**Then**
1. returns: `result.saved_stamp["public_id"] == OWN(UA)`.
2. mock called: `dr.call_count == 0`.

### AUTH-ME-31 — a failing commit keeps the old stamp
- **Rules:** `update_current_user` R9 (TC4)
- **Kind:** error
- **Expect:** pass

**Given**
1. UA stamp IMG(OWN(UA)) (commit point after this line).

**When**
- failing commit: `svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp=None))`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read UA: `saved_stamp == IMG(OWN(UA))`.

### AUTH-ME-32 — a failing commit deletes no picture
- **Rules:** `update_current_user` R10 [BUG-2562]
- **Kind:** bug
- **Expect:** xfail BUG-2562
- **Fails today on:** Then 3 (the picture was deleted before the commit)

**Given**
1. UA stamp IMG(OWN(UA)) (commit point after this line).

**When**
- failing commit: `svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp=None))`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. re-read UA: `saved_stamp == IMG(OWN(UA))`.
3. mock called: `dr.call_count == 0`.

### AUTH-ME-33 — the picture is deleted after the commit
- **Rules:** `update_current_user` R10 [BUG-2562]
- **Kind:** bug
- **Expect:** xfail BUG-2562
- **Author:** claude
- **Fails today on:** Then 2 (the delete comes before the commit)

**Given**
1. UA stamp IMG(OWN(UA)) (commit point after this line).
2. `order = []`; `dr.side_effect = lambda *a, **k: order.append("destroy") or {"result": "ok"}`; a `wraps` spy on `db.commit` that appends `"commit"` to `order` before calling the real commit.

**When**
- `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp=None))`.

**Then**
1. returns: `result.saved_stamp is None`.
2. mock called: `order == ["commit", "destroy"]`.

### AUTH-ME-34 — a failed Cloudinary delete never fails the change
- **Rules:** `update_current_user` R10 (BUG-1713 rule, holds today)
- **Kind:** external
- **Expect:** pass

**Given**
1. UA stamp IMG(OWN(UA)) (commit point after this line).
2. `dr.side_effect = RuntimeError("network down")`.

**When**
- `result = svc.update_current_user(db, user=UA, update=ProfileMeUpdate(saved_stamp=None))`.

**Then**
1. returns: `result.saved_stamp is None`.
2. committed: UA's `saved_stamp is None`.
3. mock called: `dr.call_count == 1`.

### AUTH-ME-35 — a failing re-read after the commit keeps the change
- **Rules:** `update_current_user` R9 (TC5)
- **Kind:** error
- **Expect:** pass

**Given**
1. `UA.timezone = "Asia/Dhaka"; db.flush()` (commit point after this line).

**When**
- failing refresh: `svc.update_current_user(db, user=UA, update=ProfileMeUpdate(timezone="Europe/London"))`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: UA's `timezone == "Europe/London"`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| BUG-2565 (P5; `_issue_token_pair` R4 stores what it is given) | `POST /auth/login/`, `/register/`, `/refresh/`, `/switch-workspace/` (`_client_context`) | a request with `X-Forwarded-For: 10.0.0.1` stores `request.client.host` on the refresh row (and, after BUG-2563, on the audit rows), never the header value |
| BUG-2570 (D5; `logout_session` R2 unchanged) | `POST /auth/logout/` | `all_devices: true` with an unknown, revoked or expired token → 200 info "No active session found; nothing to revoke.", nothing revoked; a live token revokes all |
| BUG-037 | every auth endpoint | an unexpected error answers 500 without the exception text |
| Status mapping | `app/api/v1/endpoints/auth.py` | `ValueError` → 400 / 401 / 403 per endpoint; `NotImplementedError` → 501; FU-1 (a) taken email is 400, not 409 |
| Rate limits (OQ-7) | `tests/unit/core/limiter.cases.md` | register 5, login 10, forgot-password 5, validate-invitation 20 per minute |
| `login_user` R1 [BUG-038], [BUG-500]; R3 second sentence | `tests/unit/dao/profile.cases.md` (PRF-AU-04, AU-09) | timing; over-long password. The no-rollback path of R3 exists only through BUG-500; no case (spec G6) |
| BUG-1407 | `tests/unit/dao/refresh_token.cases.md` (RT-CR-11 … 13) | over-long user agent / address cut, not failing |
| BUG-1862 index | `tests/unit/dao/profile.cases.md` (PRF-CR-17) | the unique index on `lower(email)`; here only RG-13 |
| Seeded data, plan, seat counting, BUG-1871, BUG-1874 detail | `tests/unit/managers/workspace_manager.cases.md` | 13 statuses, workflow, 11 tags; unlimited plans; superseded invitations' audit rows |
| `reset_password_by_admin` R7 decision (OQ-34) | permissions work (`docs/future/permissions.md`) | whatever the owner decides replaces AUTH-P34-01 … 03 |
| D9 placeholder flow | notifications work (`docs/future/notifications.md`) | a stored, mailed, single-use reset token |
| `GET /auth/me/`, `POST /auth/me/stamp-image/sign` | endpoint / `profile_stamp_manager.cases.md` | do not use this service |

## Spec gaps
None. Gaps 1–7 of Revision 1 are closed by the spec's Gap log (G1–G7, 2026-11-10).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_issue_token_pair` | R1 | AUTH-TP-01, TP-02, TP-09, TP-13 |
| | R1a | TP-12, TP-13 |
| | R2 | TP-03, TP-09 |
| | R3 | TP-04, TP-05, TP-06, TP-07 |
| | R4 | TP-07, TP-08, TP-09 |
| | R5 | TP-10 |
| | flushed (Returns) | TP-11 |
| `register_user` | R1 | RG-04, RG-08 |
| | R1a [BUG-1860] | RG-05, RG-06, RG-07 (xfail); RG-08 (pass) |
| | R1a [BUG-1861] | RG-09 (xfail); RG-10 (pass) |
| | R1a [BUG-1862] | RG-13 (xfail) |
| | R1b [BUG-2564] | RG-11 (xfail); RG-12 (pass) |
| | R2 | RG-14, RG-15 |
| | R3 | RG-01, RG-15 |
| | R4 | RG-16, RG-17, RG-10 |
| | R5 | RG-02, RG-16, RG-18 |
| | R6 (TC1, TC2) | RG-01, RG-03 |
| | R7 (TC3, TC4, TC5) | RG-04, RG-19, RG-20, RG-21, RG-22, RG-23 |
| `_register_user_only` | R1 | RU-01, RU-04, RU-05; RG-20 |
| | R2 | RU-02 |
| | R3 | RU-03 |
| | flushed | RU-06 |
| `_register_with_invitation` | R1 | RI-06 … RI-15 (RI-10 xfail BUG-1987) |
| | R2 | RI-02; RG-18 |
| | R3 | RI-01, RI-04, RI-16 (xfail BUG-1874) |
| | R4 [BUG-2563] | RI-05 (xfail); RI-04 (pass) |
| | R5 | RI-03 |
| | R6 | RG-21 |
| | flushed | RI-17 |
| `_register_with_new_workspace` | R1 | RW-04; RG-02 |
| | R2 | RW-07, RW-08, RW-09 |
| | R2a [BUG-2566] | RW-11 … RW-15 (xfail); RW-10 (pass) |
| | R3 | RW-01, RW-19 |
| | R3a [BUG-2567] | RW-16, RW-17, RW-18 (xfail) |
| | R4 | RW-01, RW-02, RW-06 |
| | R5 [BUG-2563] | RW-03 (xfail); RW-02 (pass) |
| | R6 | RW-05 |
| | Errors: slug invalid / slug taken (today) | bug paths, covered by the intended cards above |
| | Errors: no default plan | RG-19 |
| | flushed | RW-20 |
| `login_user` | R1 | LI-05 … LI-09; [BUG-1860] LI-10 (xfail); [BUG-038], [BUG-500] deferred |
| | R2 | LI-01 … LI-04, LI-12 |
| | R3 | LI-13 (TC3), LI-11 (TC4); second sentence: no case (spec G6, BUG-500 path only) |
| `switch_workspace` | R1, Errors "no active membership" | SW-03 … SW-10 |
| | R2, Errors "workspace missing" | unreachable (foreign key cascade): no card |
| | R3 | SW-01, SW-02 |
| | R4 | SW-11, SW-01 |
| | R5 | SW-12 |
| | R6 | SW-03 (no rollback), SW-14 (TC3), SW-13 (TC4) |
| `refresh_access_token` | R1, Errors "unknown" | RF-07, RF-08 |
| | R2, Errors "reuse" | RF-09, RF-14 |
| | R2a | RF-17 |
| | R3 | RF-10 |
| | R4, Errors "revoked", "expired" | RF-11, RF-12, RF-13 |
| | R5, Errors "user gone" | unreachable (foreign key cascade): no card |
| | R6 | RF-01 … RF-06 |
| | R7 [BUG-2560] | RF-15 (xfail); RF-14 (pass, sequential replay) |
| | R8 (TC3, TC4) | RF-07, RF-11, RF-16 |
| `logout_session` | R1 | LO-09 |
| | R2, Errors | LO-11 |
| | R3 | LO-08, LO-09, LO-10 |
| | R4 | LO-01, LO-03, LO-04, LO-05 |
| | R5 | LO-06, LO-07 |
| | R6 | LO-02, LO-06, LO-11, LO-12 |
| `request_password_reset` | R1 | FP-02; [BUG-1860] FP-03 (xfail) |
| | R2 | FP-01 |
| | R3 | FP-02 |
| | R4 | FP-04 |
| `reset_password` | R1, Errors | RP-01 |
| `reset_password_by_admin` | R1, Errors "caller not active" | AR-05 … AR-09 |
| | R2, Errors "caller not owner" | AR-10 … AR-15 |
| | R3, Errors "target not active" | AR-16 … AR-21 |
| | R4, Errors "target profile gone" | unreachable (foreign key cascade): no card |
| | R5 | AR-05, AR-10, AR-16, AR-22, AR-23 |
| | R6, Errors "over 72 bytes" | AR-01, AR-24, AR-25 |
| | R7 *(pending OQ-34)* | AUTH-P34-01, P34-02, P34-03 |
| | R8 | AR-02 |
| | R9 [BUG-2569] | AR-26 (xfail) |
| | R10 | AR-02, AR-03, AR-04, AR-27 |
| `validate_invitation_token` | R1, Errors | VI-03, VI-04, VI-05, VI-06, VI-15 |
| | R2 [BUG-2561], Errors | VI-07 (xfail); VI-08, VI-09 (pass) |
| | R3 | VI-10 |
| | R4, Errors | VI-11, VI-12, VI-13 |
| | R5 | VI-01, VI-02, VI-03, VI-09 |
| | R6 | VI-14, VI-15 |
| `update_current_user` | R1 | ME-01 |
| | R2 | ME-02, ME-07 |
| | R3 | ME-02, ME-03 |
| | R3a [BUG-1406] | ME-04, ME-05, ME-06 (xfail); ME-02 (pass) |
| | R4 | ME-07 … ME-10 |
| | R5 | ME-11, ME-12, ME-13, ME-28 |
| | R6, Errors | ME-14, ME-15, ME-17, ME-18 |
| | R6a [BUG-1864] | ME-19 … ME-23 (xfail); ME-15 (pass) |
| | R7 | ME-24, ME-25 |
| | R7a [BUG-1865] | ME-29, ME-30 (xfail); ME-28 (pass) |
| | R7b [BUG-2568] | ME-27 (xfail); ME-26 (pass) |
| | R8 [BUG-1866] | ME-16 (xfail) |
| | R9 (TC1–TC5) | ME-02, ME-17, ME-31, ME-35 |
| | R10 [BUG-2562] | ME-32, ME-33 (xfail); ME-31, ME-34 (pass) |
