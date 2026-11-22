# Test cases — `app/services/workspace_service.py`

> **Spec:** `tests/unit/services/workspace_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 5 (2026-11-06) — `workspace_service.verify.md` Findings 1–4 and spec TX1a / R4a (G7, G8). Finding 1 (case-missing): WSS-LI-01, LI-02, LI-03, LI-04, LI-05 give each W1 invitation its own inviter (UO, UA, UB, `None`) and LI-01, LI-02, LI-03, LI-05 assert the `{invitation id: inviter id}` map, so "the first invitation's inviter for every row" fails. Finding 2 (case-missing): WSS-MI-01 now has three listed invitations with inviters UO, U2 and `None` (new I5 in W0) and asserts the map. Finding 3 / TX1a: the TC3 path before the commit of `remove_member`, `cancel_invitation`, `update_member_role` is not unit-testable; no card, marked in the Coverage matrix. Finding 4 / R4a (BUG-2258): new WSS-MR-31 (owner sets own position with `new_role=None`, strict xfail, the audit line also needs BUG-2253), MR-32 (role + position for the owner still 403, nothing stored, pass; MR-11 had the role only), MR-33 (`new_role=None` on another member keeps the role, strict xfail, `Author: claude`). No ID retired.
> Revision 4 (2026-11-05) — executor discrepancies (`workspace_service.notes.md`) and spec G6. (1) DISCREPANCY-1: the re-read check in WSS-C-01, U-01, MR-01, SI-01, AI-01 now compares only column attributes (`refresh()` leaves lazy relationships expired). (2) WSS-LW-07 counted 7 statements against the card's 6: the card was wrong, not the code — the When's arguments (`UA.id`) were read after the recorder's `expire_all()`, so the test's own reload of an expired profile was counted (spec R4: one membership read plus one workspace read per membership = 6). Fixed in Conventions (**recorder** now evaluates the When's arguments before `expire_all()`), which also keeps the ≤ 3 budget of LW-07, LM-07, LI-06 free of test reloads; LW-07's Fails-today note restated. (3) G6, `update_member_role` R5a / BUG-2257: WSS-MR-04 keeps its ID and input (owner promotes a member to "owner") and becomes a strict xfail (400, nothing changed, pending row kept); new WSS-MR-26 (no row), MR-27 (inactive row), MR-28 (the owner's own row) strict xfail; MR-29 ("Owner" is stored, exact compare) and MR-30 (non-owner asks for "owner": R2's 403 first) pass. No ID retired.
> Revision 3 (2026-11-05) — spec Gap log G5 (gap 4: modules and fields of the request schemas). Changed: WSS-MR-24, MR-25 use `RoleChangeRequest(new_role="manager", …)` from `app.schemas.workspace_member`, no longer `Author: claude`. New BUG-2256 schema pairs (256 strict xfail / 255 pass): WSS-SI-14 / SI-15 (`InviteUserRequest.position`), WSS-AI-19 / AI-20 (`AcceptInvitationRequest.position`), WSS-C-13 / C-14 (`WorkspaceCreate.billing_email`). Spec gaps closed. No ID retired.
> Revision 2 (2026-11-05) — spec fill-gaps G1–G4 (Gap log). G1: WSS-RO-01 now asserts the returned row (`_require_owner` R3). G2: new WSS-U-27 (TC3: `billing_email` of 256 characters built with `WorkspaceUpdate.model_construct`, `DataError` inside the `try`) and WSS-MR-23 (TC4 path: `position` of 256 characters passed straight to the service, `DataError` at the commit). G3: WSS-G-02 unchanged, `is_active` confirmed. G4 (`update_workspace` R5a, BUG-2256): new schema cards WSS-U-28 / U-29 (`billing_email`, `WorkspaceUpdate`), WSS-C-11 / C-12 (`owner_position`, `WorkspaceCreate`), WSS-MR-24 / MR-25 (`position`, `RoleChangeRequest`). Gaps 1–3 closed; new gap 4 (module and role field of `RoleChangeRequest`). No ID retired.
> **Counts:** 202 cases · 134 expected-to-pass · 68 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `_require_active_membership` 13 · `_require_owner` 8 · `list_user_workspaces` 8 (2 bug) · `create_workspace` 14 (4 bug) · `get_workspace_with_plan` 5 · `update_workspace` 29 (14 bug) · `list_members` 8 (2 bug) · `update_member_role` 33 (15 bug) · `remove_member` 19 (8 bug) · `send_invitation` 15 (4 bug) · `list_invitations` 7 (2 bug) · `accept_invitation` 20 (7 bug) · `cancel_invitation` 16 (7 bug) · `get_my_invitations` 7 (3 bug).
- **Expected-to-fail by bug (all strict):** BUG-2250 13 · BUG-2251 9 · BUG-2253 5 · BUG-1404 5 · BUG-2252 4 · BUG-2256 6 · BUG-2257 4 · BUG-2258 2 · BUG-1980 3 · BUG-1400 2 · BUG-1401 2 · BUG-1990 2 · BUG-2254, BUG-1280, BUG-1402, BUG-1871, BUG-1872, BUG-1873, BUG-1874, BUG-1982, BUG-1985, BUG-1986, BUG-1987 1 each.
- **Depth:** full on who may call (both helpers, BUG-2250 on `update_workspace` / `update_member_role`) and on the error mapping (TX1, BUG-2251). Lighter on the reads and on the manager's own rules: those are `workspace_manager.cases.md`'s; here each manager bug reached gets one or two pass-through cards, strict as there. TC1–TC5 once per writer (TC3 / TC4 on the two update methods through over-long values that bypass the schema, so they stay reachable after BUG-2256), TC6 once per read, BUG-2256 at 255 (pass) and 256 (strict xfail) for each capped field on each schema that takes it (`billing_email` on `WorkspaceCreate` and `WorkspaceUpdate`, `owner_position` on `WorkspaceCreate`, `position` on `RoleChangeRequest`, `InviteUserRequest`, `AcceptInvitationRequest`), TX2 (pre-`try` refusal leaves the session's pending rows pending) once per method that has such a refusal, TX3 (no re-read on remove / cancel) with a failing `refresh` that must not fire.
- **BUG-2250 (strict, 13 cards):** one shape per card on each of the two methods: unknown id, id `0` (edit only), the owner of W0 and the owner of W2 (ids below and above W1, each holding a full grant in their own workspace), the user named by `owner_user_id` with no member row, with an `inactive` row, with a `suspended` row (edit only), and a plain non-member (edit only). Each starts with a `session:` line before any re-read. Passing companions: the owner succeeds; an active non-owner member gets today's owner message.
- **BUG-2251 (strict, 9 cards):** remove: target with no row, target only in W0, only in W2, target `inactive` (also needs BUG-1984); cancel: unknown id, `accepted`, `cancelled`, an invitation of W0 / W2 (also BUG-1981). The 403s that stay (owner target, remover role, non-owner canceller) are passing cards, and one passing card per mapped message checks only the text on the common base `APIException`, which holds before and after the fix.
- **Notable design choices:** BUG-2252 counts statements after `db.expire_all()`, so an identity-map hit cannot make today's per-row reads silent, with the call's arguments read before it so the test's own reloads are not counted; BUG-2257 (no "owner" by role change) has one card per target shape (active, no row, inactive, the owner) plus pass cards for "Owner" and for R2 coming first; 5 related rows, intended ≤ 3. The four lists are compared as sets; their order is the DAOs' (BUG-1400, BUG-1401) and gets one strict "ORDER BY present" card per list. Refusals before the `try` keep an uncommitted extra row X pending (TX2); refusals inside it discard X (TC3). The `remove_member` clean-up bugs BUG-1201 / BUG-1883 are not repeated (deferred to the manager file); BUG-1280 gets one `Author: claude` card.
- **Needs a decision:** None blocking. Gaps 1–4 closed by the spec's Gap log (G1–G5). Gap 5: today's outcome of `new_role=None` for a non-owner target (WSS-MR-33 is `Author: claude`). Lists with inviters (LI, MI) assert each invitation's own inviter, with distinct non-null inviters and one `None`.

## Conventions for this module

**IDs.** `WSS` = `app/services/workspace_service.py`. `AM` _require_active_membership · `RO` _require_owner · `LW` list_user_workspaces · `C` create_workspace · `G` get_workspace_with_plan · `U` update_workspace · `LM` list_members · `MR` update_member_role · `RM` remove_member · `SI` send_invitation · `LI` list_invitations · `AI` accept_invitation · `XI` cancel_invitation · `MI` get_my_invitations.

**Actors and fixed values.**
- `svc` = `workspace_service` (`from app.services.workspace_service import WorkspaceService, workspace_service`). `db` = the test's real session, first positional argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- `APIException`, `NotFoundError`, `PermissionDeniedError`, `ValidationError` (`app.core.exceptions`). `PydanticValidationError` = `pydantic.ValidationError`. `IntegrityError`, `DataError` (`sqlalchemy.exc`). `RoleChangeRequest` (`app.schemas.workspace_member`). `InviteUserRequest`, `AcceptInvitationRequest` (`app.schemas.workspace_invitation`). `select`, `func`, `event`, `inspect as sa_inspect` (`sqlalchemy`). Models `Workspace`, `WorkspaceMember`, `WorkspaceInvitation`, `WorkspaceAuditLog`, `SubscriptionPlan`, `Profile`, `Project`, `ProjectMember` from `app.models.<snake_case>`. `WorkspaceCreate`, `WorkspaceUpdate` (`app.schemas.workspace`). `make_subscription_plan`, `make_workspace`, `make_profile` (`tests/unit/factories.py`). `patch` (`unittest.mock`). `uuid`, `datetime`, `timedelta`.
- MISSING = `999999999`. NOW = `datetime(2026, 3, 5, 12, 0, 0)` (naive UTC). DAY = `timedelta(days=1)`. TAG = `uuid.uuid4().hex[:8]`, once per test. SL = `f"acme-{TAG}"`.
- E0 = `f"zed.{TAG}@acme.com"`, EO = `f"own.{TAG}@acme.com"`, EA = `f"ann.{TAG}@acme.com"`, EB = `f"bob.{TAG}@acme.com"`, EC = `f"cat.{TAG}@acme.com"`, E2 = `f"two.{TAG}@acme.com"`, EQ = `f"qin.{TAG}@acme.com"`, ED = `f"dan.{TAG}@acme.com"` (ED has no profile).
- NOTMEM = `"You are not a member of this workspace"`. OWNONLY = `"Only the workspace owner can perform this action"`.

**Standing rows** (every test, built in this order, each flushed, no Given line):
1. PL0, PL1, PL2 = `make_subscription_plan(db, max_members=10)` (not default, active).
2. Profiles by `make_profile(db, email=…, name=…)`: U0 (E0, `"Zara Zero"`), UO (EO, `"Olive Owner"`), UA (EA, `"Ann Lee"`), UB (EB, `"Bob Roy"`), UC (EC, `"Cat Kim"`), U2 (E2, `"Tom Two"`), UQ (EQ, `"Quinn Extra"`). So `U0.id < UO.id < UA.id < UB.id < UC.id < U2.id < UQ.id`.
3. W0 = `make_workspace(db, subscription_plan_id=PL0.id, owner_user_id=U0.id)`, W1 the same with PL1, UO; W2 with PL2, U2. So `W0.id < W1.id < W2.id`.
4. Owner rows `WorkspaceMember(workspace_id=…, user_id=…, role="owner", status="active")`: M0 (W0, U0), MO (W1, UO), M2 (W2, U2).
No other plan, member, invitation, audit row or workspace exists unless the Given builds it.

**Given rows.** Inserted directly (never through `svc`), flushed one at a time in the order written. After "but" a line lists every column that differs. A line written as code is a step run exactly as written.
- **member(U, role, status="active", ws=W1)** = `WorkspaceMember(workspace_id=ws.id, user_id=U.id, role=role, status=status)`.
- **invitation J to e** = `WorkspaceInvitation(workspace_id=W1.id, email=e, role="member", token=f"tok-J-{TAG}", status="pending", expires_at=NOW + DAY, invited_by_user_id=UO.id)` (J = the row's own Given name).
- **limit n** = `PL1.max_members = n; db.flush()`.
- **PD** = `make_subscription_plan(db, name=f"free-{TAG}", is_default=True, is_active=True, max_members=3)`. **PX** = `make_subscription_plan(db, name=f"pro-{TAG}", is_default=False, is_active=True, max_members=10)`.
- **W3, W4** = `make_workspace(db)` (only where a Given lists them).
- **commit point** = after the last Given line the test runs `db.commit()` (releases a savepoint). Snapshots for `unchanged` and `nothing written` are taken there.
- **extra row X** (after the commit point, only where listed) = `X = WorkspaceMember(workspace_id=W2.id, user_id=UQ.id, role="viewer", status="active")`, `db.add(X)`, `db.flush()`, `X_ID = X.id`; not committed.

**Externals.** Every When runs inside `patch("app.managers.workspace_manager.utcnow", return_value=NOW)` and `patch("app.dao.workspace_invitation.utcnow", return_value=NOW)` (the helper does it). Nothing else is mocked unless a card says so.

**Named checks.**
- **re-read X** = `db.expire_all()`, then `db.get(<Model>, X.id)`; database values. **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **nothing written** = the numbers of rows of `workspaces`, `workspace_members`, `workspace_invitations`, `workspace_audit_logs` (all workspaces) equal their values at the commit point.
- **audit(W, a)** = `db.expire_all()`, then the `WorkspaceAuditLog` rows with `workspace_id == W.id` and `action == a`, ordered by `id`. Metadata is the attribute `metadata_json`.
- **x_kept** = `db.scalar(select(func.count()).select_from(WorkspaceMember).where(WorkspaceMember.id == X_ID)) == 1`. **x_gone** = the same `== 0`.
- **wsids(r)** = `{p[0].id for p in r}`; **ids0(r)** = `{p[0].id for p in r}` for triples/pairs whose first item is the row asked for; **uids(r)** = `{p[0].user_id for p in r}`.
- `raises: <Type>` = `with pytest.raises(<Type>) as exc:` around the call, no savepoint; later lines on `exc.value` after the block (`.status_code`, `.detail`, `.__context__`). Target `schema` = only the schema is built.
- `session:` lines check `db.new`, `db.dirty`, `db.deleted` right after the call, before any re-read.
- `committed:` lines: before the first, the test runs `db.rollback()` once; each line then reads with a fresh query.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = the same with `patch.object(db, "refresh", side_effect=RuntimeError("boom"))` and no `rb`. **refresh trap** = `with patch.object(db, "refresh", side_effect=RuntimeError("boom")) as rf:` around the When, no `pytest.raises`.
- **recorder** = a Given step run last, after the commit point: first the When's keyword arguments are evaluated into a dict `kw` (so `W1.id`, `UA.id` … are read before anything is expired) and the When is run as `svc.<method>(db, **kw)`; then `db.expire_all()`, `stmts = []`, `event.listen(db.connection(), "before_cursor_execute", rec)` with `rec(conn, cursor, statement, params, context, executemany)` appending `statement`; `event.remove` right after the When.

**xfail cards.** Strict: `pytest.mark.xfail(strict=True, reason="BUG-n")`. Write the call and checks exactly as shown, also with a parameter that does not exist yet.

**Race simulations.** None.

## `WorkspaceService._require_active_membership`

### WSS-AM-01 — an active member's row is returned
- **Rules:** `_require_active_membership` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. MA = member(UA, "viewer").

**When**
- `result = svc._require_active_membership(db, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result.id == MA.id`.
2. session: `not db.new and not db.dirty and not db.deleted`.

### WSS-AM-02 — an unknown workspace is refused as "not a member"
- **Rules:** `_require_active_membership` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. MA = member(UA, "viewer").

**When**
- `svc._require_active_membership(db, workspace_id=MISSING, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOTMEM`.

### WSS-AM-03 — workspace id 0 is refused
- **Rules:** `_require_active_membership` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA = member(UA, "viewer").

**When**
- `svc._require_active_membership(db, workspace_id=0, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.

### WSS-AM-04 — the owner of W0 (lower id) is not a member of W1
- **Rules:** `_require_active_membership` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No member row of U0 in W1 (standing rows only).

**When**
- `svc._require_active_membership(db, workspace_id=W1.id, user_id=U0.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.

### WSS-AM-05 — the owner of W2 (higher id) is not a member of W1
- **Rules:** `_require_active_membership` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No member row of U2 in W1 (standing rows only).

**When**
- `svc._require_active_membership(db, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.

### WSS-AM-06 — an inactive row in W1 is refused even with active rows in W0 and W2
- **Rules:** `_require_active_membership` R1, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. member(UA, "owner", ws=W0).
2. member(UA, "manager", status="inactive").
3. member(UA, "owner", ws=W2).

**When**
- `svc._require_active_membership(db, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.

### WSS-AM-07 — an unknown user is refused
- **Rules:** `_require_active_membership` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. No extra row (standing rows only).

**When**
- `svc._require_active_membership(db, workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.

### WSS-AM-08 — status "suspended" is refused
- **Rules:** `_require_active_membership` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UA, "viewer", status="suspended").

**When**
- `svc._require_active_membership(db, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.

### WSS-AM-09 — status "invited" is refused
- **Rules:** `_require_active_membership` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UA, "viewer", status="invited").

**When**
- `svc._require_active_membership(db, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.

### WSS-AM-10 — status "Active" (capital) is refused
- **Rules:** `_require_active_membership` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. member(UA, "viewer", status="Active").

**When**
- `svc._require_active_membership(db, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.

### WSS-AM-11 — status " active" (leading space) is refused
- **Rules:** `_require_active_membership` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. member(UA, "viewer", status=" active").

**When**
- `svc._require_active_membership(db, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.

### WSS-AM-12 — any role passes, an empty role included
- **Rules:** `_require_active_membership` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA = member(UA, "").

**When**
- `result = svc._require_active_membership(db, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result.id == MA.id`.

### WSS-AM-13 — a platform admin who is not a member is refused
- **Rules:** `_require_active_membership` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. `UA.is_platform_admin = True; db.flush()`.

**When**
- `svc._require_active_membership(db, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.

## `WorkspaceService._require_owner`

### WSS-RO-01 — an active member whose stored role is "owner" passes, whoever `owner_user_id` names, and gets their own row
- **Rules:** `_require_owner` R1, R2 (D6), R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. MA = member(UA, "owner").

**When**
- `result = svc._require_owner(db, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceMember)`, `result.id == MA.id`, `result.user_id == UA.id`.
2. session: `not db.new and not db.dirty and not db.deleted`.

### WSS-RO-02 — an active "manager" is refused
- **Rules:** `_require_owner` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UA, "manager").

**When**
- `svc._require_owner(db, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == OWNONLY`.

### WSS-RO-03 — role "Owner" (capital) is refused
- **Rules:** `_require_owner` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. member(UA, "Owner").

**When**
- `svc._require_owner(db, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == OWNONLY`.

### WSS-RO-04 — role "owner " (trailing space) is refused
- **Rules:** `_require_owner` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. member(UA, "owner ").

**When**
- `svc._require_owner(db, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == OWNONLY`.

### WSS-RO-05 — the owner of W0 is only a "member" in W1 and is refused
- **Rules:** `_require_owner` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. member(U0, "member").

**When**
- `svc._require_owner(db, workspace_id=W1.id, user_id=U0.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == OWNONLY`.

### WSS-RO-06 — the owner of W2 is only a "member" in W1 and is refused
- **Rules:** `_require_owner` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. member(U2, "member").

**When**
- `svc._require_owner(db, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == OWNONLY`.

### WSS-RO-07 — an inactive "owner" row gets the membership message first
- **Rules:** `_require_owner` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UA, "owner", status="inactive").

**When**
- `svc._require_owner(db, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.

### WSS-RO-08 — the user named by `owner_user_id` without a member row is refused
- **Rules:** `_require_owner` R1, R2 (D6)
- **Kind:** error
- **Expect:** pass

**Given**
1. `W1.owner_user_id = UA.id; db.flush()` (UA has no row in W1).

**When**
- `svc._require_owner(db, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.

## `WorkspaceService.list_user_workspaces`

### WSS-LW-01 — one pair per active membership, every workspace
- **Rules:** `list_user_workspaces` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. member(UA, "viewer", ws=W2).
2. member(UA, "manager", ws=W0).
3. member(UA, "member").
4. member(UB, "member").

**When**
- `result = svc.list_user_workspaces(db, user_id=UA.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `wsids(result) == {W0.id, W1.id, W2.id}`.
3. returns: `all(m.user_id == UA.id and m.workspace_id == w.id for (w, m) in result)`.

### WSS-LW-02 — inactive and "Active" memberships are left out
- **Rules:** `list_user_workspaces` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. member(UA, "viewer", status="inactive", ws=W0).
2. member(UA, "member").
3. member(UA, "viewer", status="Active", ws=W2).

**When**
- `result = svc.list_user_workspaces(db, user_id=UA.id)`.

**Then**
1. returns: `wsids(result) == {W1.id}`.

### WSS-LW-03 — "suspended" and " active" memberships are left out
- **Rules:** `list_user_workspaces` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. member(UA, "viewer", status="suspended", ws=W0).
2. member(UA, "member").
3. member(UA, "viewer", status=" active", ws=W2).

**When**
- `result = svc.list_user_workspaces(db, user_id=UA.id)`.

**Then**
1. returns: `wsids(result) == {W1.id}`.

### WSS-LW-04 — an unknown user gets an empty list
- **Rules:** `list_user_workspaces` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No extra row.

**When**
- `result = svc.list_user_workspaces(db, user_id=MISSING)`.

**Then**
1. returns: `result == []`.

### WSS-LW-05 — a user with only an inactive membership gets an empty list
- **Rules:** `list_user_workspaces` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. member(UA, "viewer", status="inactive").

**When**
- `result = svc.list_user_workspaces(db, user_id=UA.id)`.

**Then**
1. returns: `result == []`.

### WSS-LW-06 — the read neither commits nor rolls back
- **Rules:** `list_user_workspaces` R5; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. member(UA, "member") (commit point after this line).
2. extra row X.

**When**
- spies: `result = svc.list_user_workspaces(db, user_id=UA.id)`.

**Then**
1. returns: `wsids(result) == {W1.id}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: x_kept.
5. committed: x_gone.

### WSS-LW-07 — the workspaces are read together
- **Rules:** `list_user_workspaces` R4 [BUG-2252]
- **Kind:** bug
- **Expect:** xfail BUG-2252
- **Fails today on:** Then 2 (the membership read plus one workspace read per membership: 6 statements)

**Given**
1. W3, W4.
2. member(UA, "member", ws=W0); member(UA, "member"); member(UA, "member", ws=W2); member(UA, "member", ws=W3); member(UA, "member", ws=W4) (commit point after this line).
3. recorder.

**When**
- `result = svc.list_user_workspaces(db, user_id=UA.id)`.

**Then**
1. returns: `wsids(result) == {W0.id, W1.id, W2.id, W3.id, W4.id}`.
2. count: `len(stmts) <= 3`.

### WSS-LW-08 — the membership query is ordered (pass-through)
- **Rules:** `list_user_workspaces` R2 [BUG-1400]
- **Kind:** bug
- **Expect:** xfail BUG-1400
- **Fails today on:** Then 2 (no `ORDER BY` in the `workspace_members` SELECT)

**Given**
1. member(UA, "member") (commit point after this line).
2. recorder.

**When**
- `result = svc.list_user_workspaces(db, user_id=UA.id)`.

**Then**
1. returns: `wsids(result) == {W1.id}`.
2. count: `any("workspace_members" in s and "ORDER BY" in s.upper() for s in stmts)`.

## `WorkspaceService.create_workspace`

### WSS-C-01 — the workspace is created on the default plan, committed and re-read
- **Rules:** `create_workspace` R1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. PD (commit point after this line).

**When**
- `result = svc.create_workspace(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id)`.

**Then**
1. returns: `isinstance(result, Workspace)`.
2. returns: `result.created_at is not None`, `not ({c.key for c in sa_inspect(result).mapper.column_attrs} & sa_inspect(result).expired_attributes)`.
3. committed: the `workspaces` row with `slug == SL` exists, `name == "Acme Tools"`, `owner_user_id == UA.id`, `subscription_plan_id == PD.id`.
4. committed: the `workspace_members` row with `workspace_id == result.id`, `user_id == UA.id` has `role == "owner"`, `status == "active"`.
5. committed: `workspace_audit_logs` with `workspace_id == result.id` and `action == "workspace_created"` has exactly 1 row.

### WSS-C-02 — plan id and owner position come from the request body
- **Rules:** `create_workspace` R1 (manager R1, pending OQ-16)
- **Kind:** happy
- **Expect:** pass

**Given**
1. PD; PX (commit point after this line).

**When**
- `result = svc.create_workspace(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL, subscription_plan_id=PX.id, owner_position="CEO"), owner_user_id=UA.id)`.

**Then**
1. returns: `result.subscription_plan_id == PX.id`.
2. committed: the `workspace_members` row with `workspace_id == result.id`, `user_id == UA.id` has `position == "CEO"`.

### WSS-C-03 — no default plan: 400 with the manager's text, everything pending discarded
- **Rules:** `create_workspace` R2, Errors row 1; TX1, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. No default plan (commit point after this line).
2. extra row X.

**When**
- `svc.create_workspace(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "No default subscription plan found"`.
4. raises: `isinstance(exc.value.__context__, ValueError)`.
5. count: x_gone.
6. nothing written.

### WSS-C-04 — an unknown plan id: 400 "Invalid subscription plan"
- **Rules:** `create_workspace` R2; TX1
- **Kind:** error
- **Expect:** pass

**Given**
1. PD (commit point after this line).

**When**
- `svc.create_workspace(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL, subscription_plan_id=MISSING), owner_user_id=UA.id)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.detail == "Invalid subscription plan"`.
3. nothing written.

### WSS-C-05 — a taken slug: 400 with the slug in the text
- **Rules:** `create_workspace` R2; TX1
- **Kind:** error
- **Expect:** pass

**Given**
1. PD; `S = W1.slug` (commit point after this line).

**When**
- `svc.create_workspace(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=S), owner_user_id=UA.id)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.detail == f"Workspace slug '{S}' is already taken. Please choose a different name."`.
3. nothing written.

### WSS-C-06 — an unknown owner: the IntegrityError passes unchanged, nothing saved
- **Rules:** `create_workspace` R3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. PD (commit point after this line).
2. extra row X.

**When**
- `svc.create_workspace(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. count: x_gone.
3. nothing written.
4. count: the session is usable: `db.execute(select(func.count()).select_from(Workspace)).scalar() >= 3`.

### WSS-C-07 — a failing commit rolls back, nothing saved
- **Rules:** `create_workspace` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. PD (commit point after this line).

**When**
- failing commit: `svc.create_workspace(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. nothing written.

### WSS-C-08 — a failing re-read leaves the workspace saved
- **Rules:** `create_workspace` R3; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. PD (commit point after this line).

**When**
- failing refresh: `svc.create_workspace(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: `workspaces` with `slug == SL` has exactly 1 row.

### WSS-C-09 — IP and user agent reach the `workspace_created` audit row
- **Rules:** `create_workspace` R4 [BUG-1404]
- **Kind:** bug
- **Expect:** xfail BUG-1404
- **Fails today on:** Then 1 (the call raises TypeError: no `ip_address` parameter)

**Given**
1. PD (commit point after this line).

**When**
- `result = svc.create_workspace(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id, ip_address="203.0.113.7", user_agent="Mozilla/5.0 Test")`.

**Then**
1. returns: `isinstance(result, Workspace)`.
2. audit: audit(result, "workspace_created") has exactly 1 row.
3. audit: that row: `ip_address == "203.0.113.7"`, `user_agent == "Mozilla/5.0 Test"`.

### WSS-C-10 — the name is stored trimmed (pass-through)
- **Rules:** `create_workspace` R1 (manager R12) [BUG-1980]
- **Kind:** bug
- **Expect:** xfail BUG-1980
- **Fails today on:** Then 2 (stored `" Acme "`)

**Given**
1. PD (commit point after this line).

**When**
- `result = svc.create_workspace(db, workspace_data=WorkspaceCreate(name=" Acme ", slug=SL), owner_user_id=UA.id)`.

**Then**
1. returns: `isinstance(result, Workspace)`.
2. committed: the `workspaces` row with `slug == SL` has `name == "Acme"`.

### WSS-C-11 — an owner position of 256 characters is refused by the schema
- **Rules:** `update_workspace` R5a [BUG-2256] (`WorkspaceCreate.owner_position`)
- **Kind:** bug
- **Expect:** xfail BUG-2256
- **Fails today on:** Then 1 (the schema accepts 256 characters)

**Given**
1. No extra row.

**When**
- build `WorkspaceCreate(name="Acme Tools", slug=SL, owner_position="p" * 256)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### WSS-C-12 — an owner position of 255 characters is accepted by the schema
- **Rules:** `update_workspace` R5a (`WorkspaceCreate.owner_position`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No extra row.

**When**
- `result = WorkspaceCreate(name="Acme Tools", slug=SL, owner_position="p" * 255)` (target `schema`).

**Then**
1. returns: `result.owner_position == "p" * 255`.

### WSS-C-13 — a billing email of 256 characters is refused by `WorkspaceCreate`
- **Rules:** `update_workspace` R5a [BUG-2256] (`WorkspaceCreate.billing_email`)
- **Kind:** bug
- **Expect:** xfail BUG-2256
- **Fails today on:** Then 1 (the schema accepts 256 characters)

**Given**
1. No extra row.

**When**
- build `WorkspaceCreate(name="Acme Tools", slug=SL, billing_email="a" * 256)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### WSS-C-14 — a billing email of 255 characters is accepted by `WorkspaceCreate`
- **Rules:** `update_workspace` R5a (`WorkspaceCreate.billing_email`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No extra row.

**When**
- `result = WorkspaceCreate(name="Acme Tools", slug=SL, billing_email="a" * 255)` (target `schema`).

**Then**
1. returns: `result.billing_email == "a" * 255`.

## `WorkspaceService.get_workspace_with_plan`

### WSS-G-01 — a member gets the workspace and its plan
- **Rules:** `get_workspace_with_plan` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. member(UA, "viewer").

**When**
- `result = svc.get_workspace_with_plan(db, workspace_id=W1.id, requesting_user_id=UA.id)`.

**Then**
1. returns: `result[0].id == W1.id`.
2. returns: `result[1].id == PL1.id`.

### WSS-G-02 — an inactive plan is returned as it is
- **Rules:** `get_workspace_with_plan` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `PL1.is_active = False; db.flush()`.
2. member(UA, "viewer").

**When**
- `result = svc.get_workspace_with_plan(db, workspace_id=W1.id, requesting_user_id=UA.id)`.

**Then**
1. returns: `result[1].id == PL1.id`.
2. returns: `result[1].is_active is False`.

### WSS-G-03 — an unknown id answers 403, not 404
- **Rules:** `get_workspace_with_plan` R1, R3
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UA, "viewer").

**When**
- `svc.get_workspace_with_plan(db, workspace_id=MISSING, requesting_user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOTMEM`.

### WSS-G-04 — the owner of W2 cannot read W1
- **Rules:** `get_workspace_with_plan` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No member row of U2 in W1.

**When**
- `svc.get_workspace_with_plan(db, workspace_id=W1.id, requesting_user_id=U2.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.

### WSS-G-05 — the read neither commits nor rolls back
- **Rules:** `get_workspace_with_plan` R4; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. member(UA, "viewer") (commit point after this line).
2. extra row X.

**When**
- spies: `result = svc.get_workspace_with_plan(db, workspace_id=W1.id, requesting_user_id=UA.id)`.

**Then**
1. returns: `result[0].id == W1.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: x_kept.
5. committed: x_gone.

## `WorkspaceService.update_workspace`

### WSS-U-01 — the owner renames the workspace; committed, re-read, nothing else changes
- **Rules:** `update_workspace` R2, R3, R7; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. `W1.billing_email = "pay@acme.com"; W1.settings = {"timezone": "Asia/Dhaka"}; db.flush()` (commit point after this line).

**When**
- `result = svc.update_workspace(db, workspace_id=W1.id, current_user_id=UO.id, workspace_update=WorkspaceUpdate(name="Acme Renamed"))`.

**Then**
1. returns: `result.id == W1.id`, `result.name == "Acme Renamed"`.
2. returns: `result.updated_at is not None`, `not ({c.key for c in sa_inspect(result).mapper.column_attrs} & sa_inspect(result).expired_attributes)`.
3. committed: re-read W1: `name == "Acme Renamed"`.
4. committed: re-read W1: `billing_email == "pay@acme.com"`, `settings == {"timezone": "Asia/Dhaka"}`.
5. committed: re-read W1: `subscription_plan_id == PL1.id`, `owner_user_id == UO.id`.

### WSS-U-02 — `name: null` leaves the name; billing email is any string
- **Rules:** `update_workspace` R3, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `N = W1.name` (commit point after this line).

**When**
- `result = svc.update_workspace(db, workspace_id=W1.id, current_user_id=UO.id, workspace_update=WorkspaceUpdate(name=None, billing_email="not an email"))`.

**Then**
1. returns: `result.billing_email == "not an email"`.
2. committed: re-read W1: `name == N`, `billing_email == "not an email"`.

### WSS-U-03 — settings replace the stored object whole
- **Rules:** `update_workspace` R5 (D9)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `W1.settings = {"timezone": "Asia/Dhaka"}; db.flush()` (commit point after this line).

**When**
- `result = svc.update_workspace(db, workspace_id=W1.id, current_user_id=UO.id, workspace_update=WorkspaceUpdate(settings={"foo": 1}))`.

**Then**
1. returns: `result.settings == {"foo": 1}`.
2. committed: re-read W1: `settings == {"foo": 1}`.

### WSS-U-04 — an invalid IANA timezone is refused by the schema
- **Rules:** `update_workspace` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. No extra row.

**When**
- build `WorkspaceUpdate(settings={"timezone": "Mars/Base"})` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.
2. raises: `"Invalid IANA timezone in workspace settings" in str(exc.value)` (contains).

### WSS-U-05 — a blank timezone passes the schema
- **Rules:** `update_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No extra row.

**When**
- `result = WorkspaceUpdate(settings={"timezone": ""})` (target `schema`).

**Then**
1. returns: `result.settings == {"timezone": ""}`.

### WSS-U-06 — a 256-character name is refused by the schema
- **Rules:** `update_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No extra row.

**When**
- build `WorkspaceUpdate(name="a" * 256)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### WSS-U-07 — a 255-character name is stored
- **Rules:** `update_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No extra row (commit point after this line).

**When**
- `result = svc.update_workspace(db, workspace_id=W1.id, current_user_id=UO.id, workspace_update=WorkspaceUpdate(name="a" * 255))`.

**Then**
1. returns: `result.name == "a" * 255`.
2. committed: re-read W1: `name == "a" * 255`.

### WSS-U-08 — an empty name is refused by the schema
- **Rules:** `update_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No extra row.

**When**
- build `WorkspaceUpdate(name="")` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### WSS-U-09 — the name is stored trimmed
- **Rules:** `update_workspace` R4 [BUG-1980]
- **Kind:** bug
- **Expect:** xfail BUG-1980
- **Fails today on:** Then 2 (stored `"  Acme  "`)

**Given**
1. No extra row (commit point after this line).

**When**
- `result = svc.update_workspace(db, workspace_id=W1.id, current_user_id=UO.id, workspace_update=WorkspaceUpdate(name="  Acme  "))`.

**Then**
1. returns: `result.id == W1.id`.
2. committed: re-read W1: `name == "Acme"`.

### WSS-U-10 — a whitespace-only name is refused by the schema
- **Rules:** `update_workspace` R4 [BUG-1980]
- **Kind:** bug
- **Expect:** xfail BUG-1980
- **Fails today on:** Then 1 (the schema accepts `"   "`)

**Given**
1. No extra row.

**When**
- build `WorkspaceUpdate(name="   ")` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### WSS-U-11 — an active member who is not the owner is refused; pending changes stay pending
- **Rules:** `update_workspace` R2, Errors row 3; TX2
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UA, "manager") (commit point after this line).
2. extra row X.

**When**
- `svc.update_workspace(db, workspace_id=W1.id, current_user_id=UA.id, workspace_update=WorkspaceUpdate(name="Hacked"))`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "Only workspace owner can update workspace"`.
4. session: `not db.dirty and not db.new and not db.deleted`.
5. count: x_kept.
6. unchanged: unchanged(W1).
7. committed: x_gone.
8. nothing written.

### WSS-U-12 — a member whose stored role is "owner" but who is not `owner_user_id` is refused
- **Rules:** `update_workspace` R2 (D6)
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UA, "owner") (commit point after this line).

**When**
- `svc.update_workspace(db, workspace_id=W1.id, current_user_id=UA.id, workspace_update=WorkspaceUpdate(name="Hacked"))`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == "Only workspace owner can update workspace"`.
3. session: `not db.dirty and not db.new`.
4. unchanged: unchanged(W1).

### WSS-U-13 — an unknown workspace answers "not a member"
- **Rules:** `update_workspace` R1 [BUG-2250], Errors rows 1–2
- **Kind:** bug
- **Expect:** xfail BUG-2250
- **Fails today on:** Then 1 (the call raises NotFoundError "Workspace not found")

**Given**
1. No extra row (commit point after this line).

**When**
- `svc.update_workspace(db, workspace_id=MISSING, current_user_id=UO.id, workspace_update=WorkspaceUpdate(name="Hacked"))`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOTMEM`.
4. session: `not db.dirty and not db.new`.
5. nothing written.

### WSS-U-14 — workspace id 0 answers "not a member"
- **Rules:** `update_workspace` R1 [BUG-2250]
- **Kind:** bug
- **Expect:** xfail BUG-2250
- **Fails today on:** Then 1 (the call raises NotFoundError "Workspace not found")

**Given**
1. No extra row (commit point after this line).

**When**
- `svc.update_workspace(db, workspace_id=0, current_user_id=UO.id, workspace_update=WorkspaceUpdate(name="Hacked"))`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.
3. session: `not db.dirty and not db.new`.
4. nothing written.

### WSS-U-15 — the owner of W0 (lower id) gets "not a member" on W1
- **Rules:** `update_workspace` R1 [BUG-2250]
- **Kind:** bug
- **Expect:** xfail BUG-2250
- **Fails today on:** Then 3 (today's detail is "Only workspace owner can update workspace")

**Given**
1. No member row of U0 in W1 (commit point after this line).

**When**
- `svc.update_workspace(db, workspace_id=W1.id, current_user_id=U0.id, workspace_update=WorkspaceUpdate(name="Hacked"))`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOTMEM`.
4. session: `not db.dirty and not db.new`.
5. unchanged: unchanged(W1).

### WSS-U-16 — the owner of W2 (higher id) gets "not a member" on W1
- **Rules:** `update_workspace` R1 [BUG-2250]
- **Kind:** bug
- **Expect:** xfail BUG-2250
- **Fails today on:** Then 3 (today's detail is "Only workspace owner can update workspace")

**Given**
1. No member row of U2 in W1 (commit point after this line).

**When**
- `svc.update_workspace(db, workspace_id=W1.id, current_user_id=U2.id, workspace_update=WorkspaceUpdate(name="Hacked"))`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOTMEM`.
4. session: `not db.dirty and not db.new`.
5. unchanged: unchanged(W1).

### WSS-U-17 — a person with no membership anywhere gets "not a member"
- **Rules:** `update_workspace` R1 [BUG-2250]
- **Kind:** bug
- **Expect:** xfail BUG-2250
- **Fails today on:** Then 2 (today's detail is "Only workspace owner can update workspace")

**Given**
1. UB has no row in any workspace (commit point after this line).

**When**
- `svc.update_workspace(db, workspace_id=W1.id, current_user_id=UB.id, workspace_update=WorkspaceUpdate(name="Hacked"))`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.
3. session: `not db.dirty and not db.new`.
4. unchanged: unchanged(W1).

### WSS-U-18 — `owner_user_id` without a member row is refused
- **Rules:** `update_workspace` R1 [BUG-2250]
- **Kind:** bug
- **Expect:** xfail BUG-2250
- **Fails today on:** Then 1 (no error: the edit is saved)

**Given**
1. `W1.owner_user_id = UA.id; db.flush()` (UA has no row in W1; commit point after this line).

**When**
- `svc.update_workspace(db, workspace_id=W1.id, current_user_id=UA.id, workspace_update=WorkspaceUpdate(name="Hacked"))`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.
3. session: `not db.dirty and not db.new`.
4. unchanged: unchanged(W1).
5. nothing written.

### WSS-U-19 — `owner_user_id` with an inactive row is refused
- **Rules:** `update_workspace` R1 [BUG-2250]
- **Kind:** bug
- **Expect:** xfail BUG-2250
- **Fails today on:** Then 1 (no error: the edit is saved)

**Given**
1. `W1.owner_user_id = UA.id; db.flush()`.
2. member(UA, "owner", status="inactive") (commit point after this line).

**When**
- `svc.update_workspace(db, workspace_id=W1.id, current_user_id=UA.id, workspace_update=WorkspaceUpdate(name="Hacked"))`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.
3. session: `not db.dirty and not db.new`.
4. unchanged: unchanged(W1).

### WSS-U-20 — `owner_user_id` with a suspended row is refused
- **Rules:** `update_workspace` R1 [BUG-2250]
- **Kind:** bug
- **Expect:** xfail BUG-2250
- **Fails today on:** Then 1 (no error: the edit is saved)

**Given**
1. `W1.owner_user_id = UA.id; db.flush()`.
2. member(UA, "owner", status="suspended") (commit point after this line).

**When**
- `svc.update_workspace(db, workspace_id=W1.id, current_user_id=UA.id, workspace_update=WorkspaceUpdate(name="Hacked"))`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.
3. session: `not db.dirty and not db.new`.
4. unchanged: unchanged(W1).

### WSS-U-21 — a name change writes one `workspace_updated` audit row
- **Rules:** `update_workspace` R6 [BUG-2253]
- **Kind:** bug
- **Expect:** xfail BUG-2253
- **Fails today on:** Then 2 (no audit row is written)

**Given**
1. No extra row (commit point after this line).

**When**
- `result = svc.update_workspace(db, workspace_id=W1.id, current_user_id=UO.id, workspace_update=WorkspaceUpdate(name="Acme Renamed"))`.

**Then**
1. returns: `result.name == "Acme Renamed"`.
2. audit: audit(W1, "workspace_updated") has exactly 1 row.
3. audit: that row: `user_id == UO.id`, `metadata_json == {"fields": ["name"]}`.

### WSS-U-22 — the audit row lists every changed field in the order name, billing_email, settings
- **Rules:** `update_workspace` R6 [BUG-2253]
- **Kind:** bug
- **Expect:** xfail BUG-2253
- **Fails today on:** Then 2 (no audit row is written)

**Given**
1. `W1.settings = {"timezone": "Asia/Dhaka"}; db.flush()` (commit point after this line).

**When**
- `result = svc.update_workspace(db, workspace_id=W1.id, current_user_id=UO.id, workspace_update=WorkspaceUpdate(settings={"timezone": "UTC"}, billing_email="pay@acme.com", name="Acme Renamed"))`.

**Then**
1. returns: `result.name == "Acme Renamed"`.
2. audit: audit(W1, "workspace_updated") has exactly 1 row.
3. audit: that row: `metadata_json == {"fields": ["name", "billing_email", "settings"]}`.

### WSS-U-23 — the same value again: no audit row, `updated_at` kept
- **Rules:** `update_workspace` R6, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `N = W1.name` (commit point after this line); then `T = W1.updated_at`.

**When**
- `result = svc.update_workspace(db, workspace_id=W1.id, current_user_id=UO.id, workspace_update=WorkspaceUpdate(name=N))`.

**Then**
1. returns: `result.name == N`.
2. audit: audit(W1, "workspace_updated") has exactly 0 rows.
3. committed: re-read W1: `updated_at == T`.

### WSS-U-24 — the `workspace_updated` row carries IP and user agent
- **Rules:** `update_workspace` R6 [BUG-2253] [BUG-1404]
- **Kind:** bug
- **Expect:** xfail BUG-2253
- **Fails today on:** Then 1 (the call raises TypeError: no `ip_address` parameter)

**Given**
1. No extra row (commit point after this line).

**When**
- `result = svc.update_workspace(db, workspace_id=W1.id, current_user_id=UO.id, workspace_update=WorkspaceUpdate(name="Acme Renamed"), ip_address="203.0.113.7", user_agent="Mozilla/5.0 Test")`.

**Then**
1. returns: `result.name == "Acme Renamed"`.
2. audit: audit(W1, "workspace_updated") has exactly 1 row.
3. audit: that row: `ip_address == "203.0.113.7"`, `user_agent == "Mozilla/5.0 Test"`.

### WSS-U-25 — a failing commit rolls back, the name is unchanged
- **Rules:** `update_workspace` R7; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. No extra row (commit point after this line).

**When**
- failing commit: `svc.update_workspace(db, workspace_id=W1.id, current_user_id=UO.id, workspace_update=WorkspaceUpdate(name="Acme Renamed"))`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(W1).

### WSS-U-26 — a failing re-read leaves the change saved
- **Rules:** `update_workspace` R7; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. No extra row (commit point after this line).

**When**
- failing refresh: `svc.update_workspace(db, workspace_id=W1.id, current_user_id=UO.id, workspace_update=WorkspaceUpdate(name="Acme Renamed"))`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: re-read W1: `name == "Acme Renamed"`.

### WSS-U-27 — an error inside the `try` rolls back and discards pending changes
- **Rules:** `update_workspace` R7; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. No extra row (commit point after this line).
2. extra row X.

**When**
- `svc.update_workspace(db, workspace_id=W1.id, current_user_id=UO.id, workspace_update=WorkspaceUpdate.model_construct(billing_email="a" * 256))` (built without validation, so the card stays valid after BUG-2256).

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "22001"`.
3. count: x_gone.
4. unchanged: unchanged(W1).
5. nothing written.
6. count: the session is usable: `db.execute(select(func.count()).select_from(Workspace)).scalar() >= 3`.

### WSS-U-28 — a billing email of 256 characters is refused by the schema
- **Rules:** `update_workspace` R5a [BUG-2256]
- **Kind:** bug
- **Expect:** xfail BUG-2256
- **Fails today on:** Then 1 (the schema accepts 256 characters)

**Given**
1. No extra row.

**When**
- build `WorkspaceUpdate(billing_email="a" * 256)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### WSS-U-29 — a billing email of 255 characters is accepted by the schema
- **Rules:** `update_workspace` R5a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No extra row.

**When**
- `result = WorkspaceUpdate(billing_email="a" * 255)` (target `schema`).

**Then**
1. returns: `result.billing_email == "a" * 255`.

## `WorkspaceService.list_members`

### WSS-LM-01 — a ground-team member lists the active members with their profiles
- **Rules:** `list_members` R1, R2, R3, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. member(UA, "ground-team").
2. member(UB, "member", status="inactive").
3. member(UC, "viewer", status="suspended").
4. member(UB, "member", ws=W0).
5. member(UC, "member", ws=W2).

**When**
- `result = svc.list_members(db, workspace_id=W1.id, requesting_user_id=UA.id)`.

**Then**
1. returns: `uids(result) == {UO.id, UA.id}`.
2. returns: `all(m.workspace_id == W1.id for (m, p) in result)`.
3. returns: `all(p.id == m.user_id for (m, p) in result)`.

### WSS-LM-02 — `include_inactive` returns every row of the workspace
- **Rules:** `list_members` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. member(UA, "ground-team").
2. member(UB, "member", status="inactive").
3. member(UC, "viewer", status="suspended").
4. member(UQ, "member", ws=W0).
5. member(UQ, "member", ws=W2).

**When**
- `result = svc.list_members(db, workspace_id=W1.id, requesting_user_id=UA.id, include_inactive=True)`.

**Then**
1. returns: `uids(result) == {UO.id, UA.id, UB.id, UC.id}`.

### WSS-LM-03 — "Active" is not "active" by default
- **Rules:** `list_members` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. member(UA, "member").
2. member(UB, "member", status="Active").

**When**
- `result = svc.list_members(db, workspace_id=W1.id, requesting_user_id=UA.id)`.

**Then**
1. returns: `uids(result) == {UO.id, UA.id}`.

### WSS-LM-04 — the owner of W0 cannot list W1
- **Rules:** `list_members` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No member row of U0 in W1.

**When**
- `svc.list_members(db, workspace_id=W1.id, requesting_user_id=U0.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.

### WSS-LM-05 — an inactive caller is refused, also with `include_inactive`
- **Rules:** `list_members` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UA, "manager", status="inactive").

**When**
- `svc.list_members(db, workspace_id=W1.id, requesting_user_id=UA.id, include_inactive=True)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.

### WSS-LM-06 — the read neither commits nor rolls back
- **Rules:** `list_members` R6; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. member(UA, "member") (commit point after this line).
2. extra row X.

**When**
- spies: `result = svc.list_members(db, workspace_id=W1.id, requesting_user_id=UA.id)`.

**Then**
1. returns: `uids(result) == {UO.id, UA.id}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: x_kept.
5. committed: x_gone.

### WSS-LM-07 — profiles are read together
- **Rules:** `list_members` R5 [BUG-2252]
- **Kind:** bug
- **Expect:** xfail BUG-2252
- **Fails today on:** Then 2 (one profile read per member: at least 7 statements)

**Given**
1. member(UA, "member"); member(UB, "member"); member(UC, "member"); member(UQ, "member") (commit point after this line).
2. recorder.

**When**
- `result = svc.list_members(db, workspace_id=W1.id, requesting_user_id=UA.id)`.

**Then**
1. returns: `uids(result) == {UO.id, UA.id, UB.id, UC.id, UQ.id}`.
2. count: `len(stmts) <= 3`.

### WSS-LM-08 — the member query is ordered (pass-through)
- **Rules:** `list_members` R2 [BUG-1400]
- **Kind:** bug
- **Expect:** xfail BUG-1400
- **Fails today on:** Then 2 (no `ORDER BY` in any `workspace_members` SELECT)

**Given**
1. member(UA, "member") (commit point after this line).
2. recorder.

**When**
- `result = svc.list_members(db, workspace_id=W1.id, requesting_user_id=UA.id)`.

**Then**
1. returns: `uids(result) == {UO.id, UA.id}`.
2. count: `any("workspace_members" in s and "ORDER BY" in s.upper() for s in stmts)`.

## `WorkspaceService.update_member_role`

### WSS-MR-01 — the owner changes a member's role and position; committed and re-read
- **Rules:** `update_member_role` R2, R3, R5; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. MA = member(UA, "viewer") (commit point after this line).

**When**
- `result = svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UA.id, new_role="manager", position="Lead")`.

**Then**
1. returns: `result.id == MA.id`, `result.role == "manager"`.
2. returns: `not ({c.key for c in sa_inspect(result).mapper.column_attrs} & sa_inspect(result).expired_attributes)`.
3. committed: re-read MA: `role == "manager"`, `position == "Lead"`, `status == "active"`.

### WSS-MR-02 — `position=None` leaves the position
- **Rules:** `update_member_role` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA = member(UA, "viewer"), but `position "Clerk"` (commit point after this line).

**When**
- `result = svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UA.id, new_role="member", position=None)`.

**Then**
1. returns: `result.role == "member"`.
2. committed: re-read MA: `position == "Clerk"`.

### WSS-MR-03 — `position=""` stores an empty position
- **Rules:** `update_member_role` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA = member(UA, "viewer"), but `position "Clerk"` (commit point after this line).

**When**
- `result = svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UA.id, new_role="viewer", position="")`.

**Then**
1. returns: `result.position == ""`.
2. committed: re-read MA: `position == ""`.

### WSS-MR-04 — the owner cannot promote an active member to "owner"
- **Rules:** `update_member_role` R5a [BUG-2257]; TX2
- **Kind:** bug
- **Expect:** xfail BUG-2257
- **Fails today on:** Then 1 (no error: "owner" is stored)

**Given**
1. MA = member(UA, "viewer") (commit point after this line).
2. extra row X.

**When**
- `svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UA.id, new_role="owner")`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "The owner role cannot be assigned. Ownership transfer is not available."`.
4. session: `not db.dirty and not db.new and not db.deleted`.
5. count: x_kept.
6. unchanged: unchanged(MA).
7. committed: x_gone.
8. nothing written.

### WSS-MR-05 — a suspended member's role can be changed
- **Rules:** `update_member_role` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA = member(UA, "viewer", status="suspended") (commit point after this line).

**When**
- `result = svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UA.id, new_role="member")`.

**Then**
1. returns: `result.role == "member"`.
2. committed: re-read MA: `role == "member"`, `status == "suspended"`.

### WSS-MR-06 — the same person's rows in other workspaces are not touched
- **Rules:** `update_member_role` R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A0 = member(UA, "viewer", ws=W0).
2. MA = member(UA, "viewer").
3. A2 = member(UA, "viewer", ws=W2) (commit point after this line).

**When**
- `result = svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UA.id, new_role="manager", position="Lead")`.

**Then**
1. returns: `result.id == MA.id`.
2. unchanged: unchanged(A0).
3. unchanged: unchanged(A2).

### WSS-MR-07 — a target with no row: 404, pending changes stay pending
- **Rules:** `update_member_role` R3; TX2
- **Kind:** error
- **Expect:** pass

**Given**
1. UB has no row in W1 (commit point after this line).
2. extra row X.

**When**
- `svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UB.id, new_role="manager")`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Member not found"`.
4. session: `not db.dirty and not db.new and not db.deleted`.
5. count: x_kept.
6. committed: x_gone.
7. nothing written.

### WSS-MR-08 — a target who is a member of W0 only: 404
- **Rules:** `update_member_role` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A0 = member(UA, "viewer", ws=W0) (commit point after this line).

**When**
- `svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UA.id, new_role="manager")`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == "Member not found"`.
3. session: `not db.dirty and not db.new`.
4. unchanged: unchanged(A0).

### WSS-MR-09 — a target who is a member of W2 only: 404
- **Rules:** `update_member_role` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A2 = member(UA, "viewer", ws=W2) (commit point after this line).

**When**
- `svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UA.id, new_role="manager")`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == "Member not found"`.
3. session: `not db.dirty and not db.new`.
4. unchanged: unchanged(A2).

### WSS-MR-10 — a removed (inactive) member answers "Member not found"
- **Rules:** `update_member_role` R3 [BUG-2254]
- **Kind:** bug
- **Expect:** xfail BUG-2254
- **Fails today on:** Then 1 (no error: the role is changed)

**Given**
1. MA = member(UA, "viewer", status="inactive") (commit point after this line).

**When**
- `svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UA.id, new_role="manager")`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == "Member not found"`.
3. session: `not db.dirty and not db.new`.
4. unchanged: unchanged(MA).

### WSS-MR-11 — the owner's own role cannot be changed
- **Rules:** `update_member_role` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. No extra row (commit point after this line).

**When**
- `svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UO.id, new_role="viewer")`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "Cannot change workspace owner's role"`.
4. session: `not db.dirty and not db.new`.
5. unchanged: unchanged(MO).

### WSS-MR-12 — an active manager who is not the owner is refused, pending changes stay pending
- **Rules:** `update_member_role` R2; TX2
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UA, "manager").
2. MB = member(UB, "viewer") (commit point after this line).
3. extra row X.

**When**
- `svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UA.id, target_user_id=UB.id, new_role="member")`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "Only workspace owner can change member roles"`.
4. session: `not db.dirty and not db.new and not db.deleted`.
5. count: x_kept.
6. unchanged: unchanged(MB).

### WSS-MR-13 — an unknown workspace answers "not a member"
- **Rules:** `update_member_role` R1 [BUG-2250]
- **Kind:** bug
- **Expect:** xfail BUG-2250
- **Fails today on:** Then 1 (the call raises NotFoundError "Workspace not found")

**Given**
1. No extra row (commit point after this line).

**When**
- `svc.update_member_role(db, workspace_id=MISSING, owner_user_id=UO.id, target_user_id=UA.id, new_role="member")`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOTMEM`.
4. session: `not db.dirty and not db.new`.
5. nothing written.

### WSS-MR-14 — the owner of W0 (lower id) gets "not a member" on W1
- **Rules:** `update_member_role` R1 [BUG-2250]
- **Kind:** bug
- **Expect:** xfail BUG-2250
- **Fails today on:** Then 3 (today's detail is "Only workspace owner can change member roles")

**Given**
1. MB = member(UB, "viewer") (commit point after this line).

**When**
- `svc.update_member_role(db, workspace_id=W1.id, owner_user_id=U0.id, target_user_id=UB.id, new_role="member")`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOTMEM`.
4. session: `not db.dirty and not db.new`.
5. unchanged: unchanged(MB).

### WSS-MR-15 — the owner of W2 (higher id) gets "not a member" on W1
- **Rules:** `update_member_role` R1 [BUG-2250]
- **Kind:** bug
- **Expect:** xfail BUG-2250
- **Fails today on:** Then 3 (today's detail is "Only workspace owner can change member roles")

**Given**
1. MB = member(UB, "viewer") (commit point after this line).

**When**
- `svc.update_member_role(db, workspace_id=W1.id, owner_user_id=U2.id, target_user_id=UB.id, new_role="member")`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOTMEM`.
4. session: `not db.dirty and not db.new`.
5. unchanged: unchanged(MB).

### WSS-MR-16 — `owner_user_id` without a member row is refused
- **Rules:** `update_member_role` R1 [BUG-2250]
- **Kind:** bug
- **Expect:** xfail BUG-2250
- **Fails today on:** Then 1 (no error: the role is changed)

**Given**
1. `W1.owner_user_id = UA.id; db.flush()` (UA has no row in W1).
2. MB = member(UB, "viewer") (commit point after this line).

**When**
- `svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UA.id, target_user_id=UB.id, new_role="member")`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.
3. session: `not db.dirty and not db.new`.
4. unchanged: unchanged(MB).

### WSS-MR-17 — `owner_user_id` with an inactive row is refused
- **Rules:** `update_member_role` R1 [BUG-2250]
- **Kind:** bug
- **Expect:** xfail BUG-2250
- **Fails today on:** Then 1 (no error: the role is changed)

**Given**
1. `W1.owner_user_id = UA.id; db.flush()`.
2. member(UA, "owner", status="inactive").
3. MB = member(UB, "viewer") (commit point after this line).

**When**
- `svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UA.id, target_user_id=UB.id, new_role="member")`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.
3. session: `not db.dirty and not db.new`.
4. unchanged: unchanged(MB).

### WSS-MR-18 — a role change writes one `member_role_changed` audit row
- **Rules:** `update_member_role` R6 [BUG-2253]
- **Kind:** bug
- **Expect:** xfail BUG-2253
- **Fails today on:** Then 2 (no audit row is written)

**Given**
1. member(UA, "viewer"), but `position "Clerk"` (commit point after this line).

**When**
- `result = svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UA.id, new_role="manager", position="Lead")`.

**Then**
1. returns: `result.role == "manager"`.
2. audit: audit(W1, "member_role_changed") has exactly 1 row.
3. audit: that row: `user_id == UO.id`.
4. audit: that row: `metadata_json == {"member_id": UA.id, "from_role": "viewer", "to_role": "manager", "from_position": "Clerk", "to_position": "Lead"}`.

### WSS-MR-19 — the same role and no position: no audit row
- **Rules:** `update_member_role` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. member(UA, "viewer"), but `position "Clerk"` (commit point after this line).

**When**
- `result = svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UA.id, new_role="viewer")`.

**Then**
1. returns: `result.role == "viewer"`.
2. audit: audit(W1, "member_role_changed") has exactly 0 rows.

### WSS-MR-20 — the `member_role_changed` row carries IP and user agent
- **Rules:** `update_member_role` R6 [BUG-2253] [BUG-1404]
- **Kind:** bug
- **Expect:** xfail BUG-2253
- **Fails today on:** Then 1 (the call raises TypeError: no `ip_address` parameter)

**Given**
1. member(UA, "viewer") (commit point after this line).

**When**
- `result = svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UA.id, new_role="manager", ip_address="203.0.113.7", user_agent="Mozilla/5.0 Test")`.

**Then**
1. returns: `result.role == "manager"`.
2. audit: audit(W1, "member_role_changed") has exactly 1 row.
3. audit: that row: `ip_address == "203.0.113.7"`, `user_agent == "Mozilla/5.0 Test"`.

### WSS-MR-21 — a failing commit rolls back, the role is unchanged
- **Rules:** `update_member_role` R5; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. MA = member(UA, "viewer") (commit point after this line).

**When**
- failing commit: `svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UA.id, new_role="manager")`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(MA).

### WSS-MR-22 — a failing re-read leaves the role saved
- **Rules:** `update_member_role` R5; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. MA = member(UA, "viewer") (commit point after this line).

**When**
- failing refresh: `svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UA.id, new_role="manager")`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: re-read MA: `role == "manager"`.

### WSS-MR-23 — a position too long for its column fails at the commit: rolled back, pending changes discarded
- **Rules:** `update_member_role` R5; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. MA = member(UA, "viewer"), but `position "Clerk"` (commit point after this line).
2. extra row X.

**When**
- `svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UA.id, new_role="manager", position="p" * 256)` (passed straight to the service, no schema).

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "22001"`.
3. count: x_gone.
4. unchanged: unchanged(MA).
5. nothing written.

### WSS-MR-24 — a position of 256 characters is refused by `RoleChangeRequest`
- **Rules:** `update_workspace` R5a [BUG-2256] (`RoleChangeRequest.position`)
- **Kind:** bug
- **Expect:** xfail BUG-2256
- **Fails today on:** Then 1 (the schema accepts 256 characters)

**Given**
1. No extra row.

**When**
- build `RoleChangeRequest(new_role="manager", position="p" * 256)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### WSS-MR-25 — a position of 255 characters is accepted by `RoleChangeRequest`
- **Rules:** `update_workspace` R5a (`RoleChangeRequest.position`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No extra row.

**When**
- `result = RoleChangeRequest(new_role="manager", position="p" * 255)` (target `schema`).

**Then**
1. returns: `result.position == "p" * 255`.

### WSS-MR-26 — "owner" for a target with no row: the owner-role refusal comes before "Member not found"
- **Rules:** `update_member_role` R5a [BUG-2257] (before R3); TX2
- **Kind:** bug
- **Expect:** xfail BUG-2257
- **Fails today on:** Then 1 (the call raises NotFoundError "Member not found")

**Given**
1. UB has no row in W1 (commit point after this line).
2. extra row X.

**When**
- `svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UB.id, new_role="owner")`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "The owner role cannot be assigned. Ownership transfer is not available."`.
4. session: `not db.dirty and not db.new and not db.deleted`.
5. count: x_kept.
6. committed: x_gone.
7. nothing written.

### WSS-MR-27 — "owner" for a removed (inactive) member is refused
- **Rules:** `update_member_role` R5a [BUG-2257] (before R3); TX2
- **Kind:** bug
- **Expect:** xfail BUG-2257
- **Fails today on:** Then 1 (no error: "owner" is stored)

**Given**
1. MA = member(UA, "viewer", status="inactive") (commit point after this line).
2. extra row X.

**When**
- `svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UA.id, new_role="owner")`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "The owner role cannot be assigned. Ownership transfer is not available."`.
4. session: `not db.dirty and not db.new and not db.deleted`.
5. count: x_kept.
6. unchanged: unchanged(MA).
7. committed: x_gone.
8. nothing written.

### WSS-MR-28 — "owner" for the owner's own row: the owner-role refusal comes before R4
- **Rules:** `update_member_role` R5a [BUG-2257] (before R3, R4); TX2
- **Kind:** bug
- **Expect:** xfail BUG-2257
- **Fails today on:** Then 1 (the call raises PermissionDeniedError "Cannot change workspace owner's role")

**Given**
1. No extra member (commit point after this line).
2. extra row X.

**When**
- `svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UO.id, new_role="owner")`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "The owner role cannot be assigned. Ownership transfer is not available."`.
4. session: `not db.dirty and not db.new and not db.deleted`.
5. count: x_kept.
6. unchanged: unchanged(MO).
7. committed: x_gone.
8. nothing written.

### WSS-MR-29 — only exactly "owner" is refused: "Owner" is stored as given
- **Rules:** `update_member_role` R5, R5a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA = member(UA, "viewer") (commit point after this line).

**When**
- `result = svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UA.id, new_role="Owner")`.

**Then**
1. returns: `result.role == "Owner"`.
2. committed: re-read MA: `role == "Owner"`.

### WSS-MR-30 — a non-owner asking for "owner" gets the owner message first (R2 before R5a)
- **Rules:** `update_member_role` R2, R5a; TX2
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UA, "manager").
2. MB = member(UB, "viewer") (commit point after this line).
3. extra row X.

**When**
- `svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UA.id, target_user_id=UB.id, new_role="owner")`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "Only workspace owner can change member roles"`.
4. session: `not db.dirty and not db.new and not db.deleted`.
5. count: x_kept.
6. unchanged: unchanged(MB).
7. committed: x_gone.
8. nothing written.

### WSS-MR-31 — the owner changes their own position with no role
- **Rules:** `update_member_role` R4a [BUG-2258], R5, R6 (BUG-2253's row; the last line also needs BUG-2253)
- **Kind:** bug
- **Expect:** xfail BUG-2258
- **Fails today on:** Then 1 (the call raises PermissionDeniedError "Cannot change workspace owner's role")

**Given**
1. `MO.position = "Founder"; db.flush()` (commit point after this line).

**When**
- `result = svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UO.id, new_role=None, position="Director")`.

**Then**
1. returns: `result.id == MO.id`, `result.position == "Director"`.
2. committed: re-read MO: `position == "Director"`, `role == "owner"`, `status == "active"`.
3. committed: audit(W1, "member_role_changed") has exactly 1 row.
4. committed: that row: `metadata_json == {"member_id": UO.id, "from_role": "owner", "to_role": "owner", "from_position": "Founder", "to_position": "Director"}`.

### WSS-MR-32 — the owner's role with a position is still refused, and the position is not stored either
- **Rules:** `update_member_role` R4, R4a
- **Kind:** error
- **Expect:** pass

**Given**
1. `MO.position = "Founder"; db.flush()` (commit point after this line).
2. extra row X.

**When**
- `svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UO.id, new_role="manager", position="Director")`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "Cannot change workspace owner's role"`.
4. session: `not db.dirty and not db.new and not db.deleted`.
5. count: x_kept.
6. unchanged: unchanged(MO).
7. committed: x_gone.
8. nothing written.

### WSS-MR-33 — `new_role=None` keeps another member's role and applies only the position
- **Rules:** `update_member_role` R4a [BUG-2258]
- **Kind:** bug
- **Expect:** xfail BUG-2258
- **Author:** claude
- **Fails today on:** Then 1 (today the role is set to `None`: either the call raises at the commit or `result.role` is `None`)

**Given**
1. MA = member(UA, "viewer"), but `position "Clerk"` (commit point after this line).

**When**
- `result = svc.update_member_role(db, workspace_id=W1.id, owner_user_id=UO.id, target_user_id=UA.id, new_role=None, position="Lead")`.

**Then**
1. returns: `result.role == "viewer"`, `result.position == "Lead"`.
2. committed: re-read MA: `role == "viewer"`, `position == "Lead"`.

## `WorkspaceService.remove_member`

### WSS-RM-01 — the owner removes a member; committed, `None` returned
- **Rules:** `remove_member` R1, R2; TC1, TX3
- **Kind:** happy
- **Expect:** pass

**Given**
1. MA = member(UA, "member") (commit point after this line).

**When**
- `result = svc.remove_member(db, workspace_id=W1.id, remover_user_id=UO.id, target_user_id=UA.id)`.

**Then**
1. returns: `result is None`.
2. committed: re-read MA: `status == "inactive"`, `left_at == NOW`, `role == "member"`.
3. committed: audit(W1, "member_removed") has exactly 1 row.
4. committed: that row: `user_id == UO.id`, `metadata_json == {"removed_member_id": UA.id}`.

### WSS-RM-02 — the remover's stored role is used: a ground-team-manager removes ground-team
- **Rules:** `remove_member` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. member(UB, "ground-team-manager").
2. MA = member(UA, "ground-team") (commit point after this line).

**When**
- `result = svc.remove_member(db, workspace_id=W1.id, remover_user_id=UB.id, target_user_id=UA.id)`.

**Then**
1. returns: `result is None`.
2. committed: re-read MA: `status == "inactive"`.

### WSS-RM-03 — no re-read after the commit
- **Rules:** `remove_member` R2; TX3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MA = member(UA, "member") (commit point after this line).

**When**
- refresh trap: `result = svc.remove_member(db, workspace_id=W1.id, remover_user_id=UO.id, target_user_id=UA.id)`.

**Then**
1. returns: `result is None`.
2. mock called: `rf.call_count == 0`.
3. committed: re-read MA: `status == "inactive"`.

### WSS-RM-04 — a caller who is not a member is refused first; pending changes stay pending
- **Rules:** `remove_member` R1; TX2
- **Kind:** error
- **Expect:** pass

**Given**
1. MA = member(UA, "member") (commit point after this line).
2. extra row X.

**When**
- `svc.remove_member(db, workspace_id=W1.id, remover_user_id=U2.id, target_user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOTMEM`.
4. session: `not db.dirty and not db.new and not db.deleted`.
5. count: x_kept.
6. unchanged: unchanged(MA).

### WSS-RM-05 — an inactive caller is refused
- **Rules:** `remove_member` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UB, "owner", status="inactive").
2. MA = member(UA, "member") (commit point after this line).

**When**
- `svc.remove_member(db, workspace_id=W1.id, remover_user_id=UB.id, target_user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.
3. session: `not db.dirty and not db.new`.
4. unchanged: unchanged(MA).

### WSS-RM-06 — an "owner" role held in W0 does not count: ground-team in W1 is refused
- **Rules:** `remove_member` R2, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. member(UB, "owner", ws=W0).
2. member(UB, "ground-team").
3. MA = member(UA, "member") (commit point after this line).

**When**
- `svc.remove_member(db, workspace_id=W1.id, remover_user_id=UB.id, target_user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == "You do not have permission to remove members"`.
3. session: `not db.dirty and not db.new`.
4. unchanged: unchanged(MA).

### WSS-RM-07 — an "owner" role held in W2 does not count: ground-team in W1 is refused
- **Rules:** `remove_member` R2, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. member(UB, "ground-team").
2. member(UB, "owner", ws=W2).
3. MA = member(UA, "member") (commit point after this line).

**When**
- `svc.remove_member(db, workspace_id=W1.id, remover_user_id=UB.id, target_user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == "You do not have permission to remove members"`.
3. session: `not db.dirty and not db.new`.
4. unchanged: unchanged(MA).

### WSS-RM-08 — removing the owner stays 403; the rollback discards pending changes
- **Rules:** `remove_member` R3; TX1, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. No extra member (commit point after this line).
2. extra row X.

**When**
- `svc.remove_member(db, workspace_id=W1.id, remover_user_id=UO.id, target_user_id=UO.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "Cannot remove workspace owner. Transfer ownership first."`.
4. raises: `isinstance(exc.value.__context__, ValueError)`.
5. count: x_gone.
6. unchanged: unchanged(MO).
7. nothing written.

### WSS-RM-09 — a ground-team-manager removing a "member" stays 403
- **Rules:** `remove_member` R3 (manager R4)
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UB, "ground-team-manager").
2. MA = member(UA, "member") (commit point after this line).

**When**
- `svc.remove_member(db, workspace_id=W1.id, remover_user_id=UB.id, target_user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "Managers can only remove ground-team members"`.
4. unchanged: unchanged(MA).
5. nothing written.

### WSS-RM-10 — "not a member" text reaches the caller (holds before and after BUG-2251)
- **Rules:** `remove_member` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. UC has no row in W1 (commit point after this line).
2. extra row X.

**When**
- `svc.remove_member(db, workspace_id=W1.id, remover_user_id=UO.id, target_user_id=UC.id)`.

**Then**
1. raises: `APIException`.
2. raises: `exc.value.detail == "User is not a member of this workspace"`.
3. count: x_gone.
4. nothing written.

### WSS-RM-11 — a target with no row answers 404
- **Rules:** `remove_member` R3 [BUG-2251]
- **Kind:** bug
- **Expect:** xfail BUG-2251
- **Fails today on:** Then 1 (the call raises PermissionDeniedError)

**Given**
1. UC has no row in W1 (commit point after this line).

**When**
- `svc.remove_member(db, workspace_id=W1.id, remover_user_id=UO.id, target_user_id=UC.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "User is not a member of this workspace"`.
4. session: `not db.dirty and not db.new`.
5. nothing written.

### WSS-RM-12 — a target who is a member of W0 only answers 404
- **Rules:** `remove_member` R3 [BUG-2251]
- **Kind:** bug
- **Expect:** xfail BUG-2251
- **Fails today on:** Then 1 (the call raises PermissionDeniedError)

**Given**
1. A0 = member(UA, "member", ws=W0) (commit point after this line).

**When**
- `svc.remove_member(db, workspace_id=W1.id, remover_user_id=UO.id, target_user_id=UA.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "User is not a member of this workspace"`.
4. session: `not db.dirty and not db.new`.
5. unchanged: unchanged(A0).

### WSS-RM-13 — a target who is a member of W2 only answers 404
- **Rules:** `remove_member` R3 [BUG-2251]
- **Kind:** bug
- **Expect:** xfail BUG-2251
- **Fails today on:** Then 1 (the call raises PermissionDeniedError)

**Given**
1. A2 = member(UA, "member", ws=W2) (commit point after this line).

**When**
- `svc.remove_member(db, workspace_id=W1.id, remover_user_id=UO.id, target_user_id=UA.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "User is not a member of this workspace"`.
4. session: `not db.dirty and not db.new`.
5. unchanged: unchanged(A2).

### WSS-RM-14 — an already removed target answers 404 and stays as it was
- **Rules:** `remove_member` R3 [BUG-2251] (manager R1a, BUG-1984: both must be fixed)
- **Kind:** bug
- **Expect:** xfail BUG-2251
- **Fails today on:** Then 1 (no error: the removal is repeated)

**Given**
1. MA = member(UA, "member", status="inactive"), but `left_at datetime(2026, 2, 1, 9, 0, 0)` (commit point after this line).

**When**
- `svc.remove_member(db, workspace_id=W1.id, remover_user_id=UO.id, target_user_id=UA.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == "User is not a member of this workspace"`.
3. session: `not db.dirty and not db.new`.
4. unchanged: unchanged(MA).
5. nothing written.

### WSS-RM-15 — a "manager" may not remove a "member" (pass-through)
- **Rules:** `remove_member` R2 (manager R4b) [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error: the member is removed)

**Given**
1. member(UB, "manager").
2. MA = member(UA, "member") (commit point after this line).

**When**
- `svc.remove_member(db, workspace_id=W1.id, remover_user_id=UB.id, target_user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == "Managers can only remove ground-team members"`.
3. unchanged: unchanged(MA).

### WSS-RM-16 — a "viewer" may not remove anyone (pass-through)
- **Rules:** `remove_member` R2 (manager R5) [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error: the member is removed)

**Given**
1. member(UB, "viewer").
2. MA = member(UA, "member") (commit point after this line).

**When**
- `svc.remove_member(db, workspace_id=W1.id, remover_user_id=UB.id, target_user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == "You do not have permission to remove members"`.
3. unchanged: unchanged(MA).

### WSS-RM-17 — the removed person's project memberships go with them (pass-through)
- **Rules:** `remove_member` R2 (manager R9) [BUG-1280]
- **Kind:** bug
- **Expect:** xfail BUG-1280
- **Author:** claude
- **Fails today on:** Then 2 (the project member row stays)

**Given**
1. MA = member(UA, "member").
2. A project P of W1 with every required column set (factory of W1 if required), and `ProjectMember(workspace_id=W1.id, project_id=P.id, user_id=UA.id, assigned_by=UO.id)` (commit point after this line).

**When**
- `result = svc.remove_member(db, workspace_id=W1.id, remover_user_id=UO.id, target_user_id=UA.id)`.

**Then**
1. returns: `result is None`.
2. committed: `project_members` with `project_id == P.id` and `user_id == UA.id` has exactly 0 rows.

### WSS-RM-18 — IP and user agent reach the `member_removed` row
- **Rules:** `remove_member` R4 [BUG-1404]
- **Kind:** bug
- **Expect:** xfail BUG-1404
- **Fails today on:** Then 1 (the call raises TypeError: no `ip_address` parameter)

**Given**
1. member(UA, "member") (commit point after this line).

**When**
- `result = svc.remove_member(db, workspace_id=W1.id, remover_user_id=UO.id, target_user_id=UA.id, ip_address="203.0.113.7", user_agent="Mozilla/5.0 Test")`.

**Then**
1. returns: `result is None`.
2. audit: audit(W1, "member_removed") has exactly 1 row.
3. audit: that row: `ip_address == "203.0.113.7"`, `user_agent == "Mozilla/5.0 Test"`.

### WSS-RM-19 — a failing commit rolls back, the member stays active
- **Rules:** `remove_member` R5; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. MA = member(UA, "member") (commit point after this line).

**When**
- failing commit: `svc.remove_member(db, workspace_id=W1.id, remover_user_id=UO.id, target_user_id=UA.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(MA).
4. nothing written.

## `WorkspaceService.send_invitation`

### WSS-SI-01 — the owner invites an email; committed and re-read
- **Rules:** `send_invitation` R1, R2; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No invitation (commit point after this line).

**When**
- `result = svc.send_invitation(db, workspace_id=W1.id, inviter_user_id=UO.id, email=ED, role="member", position="Tech")`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. returns: `len(result.token) == 43`, `not ({c.key for c in sa_inspect(result).mapper.column_attrs} & sa_inspect(result).expired_attributes)`.
3. committed: re-read the invitation `result.id`: `workspace_id == W1.id`, `email == ED`, `role == "member"`, `position == "Tech"`.
4. committed: re-read the invitation `result.id`: `status == "pending"`, `expires_at == NOW + timedelta(days=3)`, `invited_by_user_id == UO.id`.
5. committed: audit(W1, "invitation_sent") has exactly 1 row.

### WSS-SI-02 — a member whose stored role is "owner" may invite, whoever `owner_user_id` names
- **Rules:** `send_invitation` R1 (D6)
- **Kind:** happy
- **Expect:** pass

**Given**
1. member(UA, "owner") (commit point after this line).

**When**
- `result = svc.send_invitation(db, workspace_id=W1.id, inviter_user_id=UA.id, email=ED, role="viewer")`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. committed: re-read the invitation `result.id`: `invited_by_user_id == UA.id`.

### WSS-SI-03 — an active manager is refused before anything; pending changes stay pending
- **Rules:** `send_invitation` R1; TX2
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UA, "manager") (commit point after this line).
2. extra row X.

**When**
- `svc.send_invitation(db, workspace_id=W1.id, inviter_user_id=UA.id, email=ED, role="member")`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == OWNONLY`.
4. session: `not db.dirty and not db.new and not db.deleted`.
5. count: x_kept.
6. committed: x_gone.
7. nothing written.

### WSS-SI-04 — the owner of W2, a "member" in W1, is refused
- **Rules:** `send_invitation` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. member(U2, "member") (commit point after this line).

**When**
- `svc.send_invitation(db, workspace_id=W1.id, inviter_user_id=U2.id, email=ED, role="member")`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == OWNONLY`.
3. session: `not db.dirty and not db.new`.
4. nothing written.

### WSS-SI-05 — a non-member is refused with the membership message
- **Rules:** `send_invitation` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. No member row of U0 in W1 (commit point after this line).

**When**
- `svc.send_invitation(db, workspace_id=W1.id, inviter_user_id=U0.id, email=ED, role="member")`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.
3. session: `not db.dirty and not db.new`.
4. nothing written.

### WSS-SI-06 — an invalid role: 400 with the manager's text; pending changes discarded
- **Rules:** `send_invitation` R3; TX1, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. No invitation (commit point after this line).
2. extra row X.

**When**
- `svc.send_invitation(db, workspace_id=W1.id, inviter_user_id=UO.id, email=ED, role="owner")`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Invalid role. Must be one of: ground-team, manager, member, viewer"`.
4. raises: `isinstance(exc.value.__context__, ValueError)`.
5. count: x_gone.
6. nothing written.

### WSS-SI-07 — an email that is already a member: 400
- **Rules:** `send_invitation` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UA, "member") (commit point after this line).

**When**
- `svc.send_invitation(db, workspace_id=W1.id, inviter_user_id=UO.id, email=EA, role="member")`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.detail == "User with this email is already a member of this workspace"`.
3. nothing written.

### WSS-SI-08 — seats full: 400 with the limit in the text
- **Rules:** `send_invitation` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. limit 1 (commit point after this line).

**When**
- `svc.send_invitation(db, workspace_id=W1.id, inviter_user_id=UO.id, email=ED, role="member")`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.detail == "Workspace has reached maximum member limit (1). Upgrade subscription to add more members."`.
3. nothing written.

### WSS-SI-09 — a second pending invitation to the same email is refused (pass-through)
- **Rules:** `send_invitation` R2 (manager R4) [BUG-1873]
- **Kind:** bug
- **Expect:** xfail BUG-1873
- **Fails today on:** Then 1 (no error: a second invitation is created)

**Given**
1. invitation J to ED (commit point after this line).

**When**
- `svc.send_invitation(db, workspace_id=W1.id, inviter_user_id=UO.id, email=ED, role="member")`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.detail == "This email is already invited to this workspace"`.
3. nothing written.

### WSS-SI-10 — a negative limit means no limit (pass-through)
- **Rules:** `send_invitation` R2 (manager R8) [BUG-1871]
- **Kind:** bug
- **Expect:** xfail BUG-1871
- **Fails today on:** Then 1 (the call raises ValidationError "…limit (-1)…")

**Given**
1. limit -1 (commit point after this line).

**When**
- `result = svc.send_invitation(db, workspace_id=W1.id, inviter_user_id=UO.id, email=ED, role="member")`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. committed: `workspace_invitations` with `workspace_id == W1.id` and `email == ED` has exactly 1 row.

### WSS-SI-11 — IP and user agent reach the `invitation_sent` row
- **Rules:** `send_invitation` R4 [BUG-1404]
- **Kind:** bug
- **Expect:** xfail BUG-1404
- **Fails today on:** Then 1 (the call raises TypeError: no `ip_address` parameter)

**Given**
1. No invitation (commit point after this line).

**When**
- `result = svc.send_invitation(db, workspace_id=W1.id, inviter_user_id=UO.id, email=ED, role="member", ip_address="203.0.113.7", user_agent="Mozilla/5.0 Test")`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. audit: audit(W1, "invitation_sent") has exactly 1 row.
3. audit: that row: `ip_address == "203.0.113.7"`, `user_agent == "Mozilla/5.0 Test"`.

### WSS-SI-12 — a failing commit rolls back, nothing saved
- **Rules:** `send_invitation` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. No invitation (commit point after this line).

**When**
- failing commit: `svc.send_invitation(db, workspace_id=W1.id, inviter_user_id=UO.id, email=ED, role="member")`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. nothing written.

### WSS-SI-13 — a failing re-read leaves the invitation saved
- **Rules:** `send_invitation` R2; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. No invitation (commit point after this line).

**When**
- failing refresh: `svc.send_invitation(db, workspace_id=W1.id, inviter_user_id=UO.id, email=ED, role="member")`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: `workspace_invitations` with `workspace_id == W1.id` and `email == ED` has exactly 1 row.

### WSS-SI-14 — a position of 256 characters is refused by `InviteUserRequest`
- **Rules:** `update_workspace` R5a [BUG-2256] (`InviteUserRequest.position`)
- **Kind:** bug
- **Expect:** xfail BUG-2256
- **Fails today on:** Then 1 (the schema accepts 256 characters)

**Given**
1. No extra row.

**When**
- build `InviteUserRequest(email=ED, role="member", position="p" * 256)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### WSS-SI-15 — a position of 255 characters is accepted by `InviteUserRequest`
- **Rules:** `update_workspace` R5a (`InviteUserRequest.position`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No extra row.

**When**
- `result = InviteUserRequest(email=ED, role="member", position="p" * 255)` (target `schema`).

**Then**
1. returns: `result.position == "p" * 255`.

## `WorkspaceService.list_invitations`

### WSS-LI-01 — by default only pending, unexpired invitations of the workspace
- **Rules:** `list_invitations` R1, R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1 = invitation I1 to EA.
2. I2 = invitation I2 to EB, but `expires_at NOW - DAY`, `invited_by_user_id UA.id`.
3. I3 = invitation I3 to EC, but `status "accepted"`, `invited_by_user_id UB.id`.
4. I4 = invitation I4 to ED, but `status "cancelled"`, `invited_by_user_id None`.
5. I0 = invitation I0 to EA, but `workspace_id W0.id`, `invited_by_user_id U0.id`.
6. I9 = invitation I9 to EA, but `workspace_id W2.id`, `invited_by_user_id U2.id`.

**When**
- `result = svc.list_invitations(db, workspace_id=W1.id, requesting_user_id=UO.id)`.

**Then**
1. returns: `ids0(result) == {I1.id}`.
2. returns: `result[0][1].id == W1.id`.
3. returns: `{i.id: (p.id if p else None) for (i, w, p) in result} == {I1.id: UO.id}`.

### WSS-LI-02 — `include_expired` returns every invitation of the workspace, any status
- **Rules:** `list_invitations` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1 = invitation I1 to EA.
2. I2 = invitation I2 to EB, but `expires_at NOW - DAY`, `invited_by_user_id UA.id`.
3. I3 = invitation I3 to EC, but `status "accepted"`, `invited_by_user_id UB.id`.
4. I4 = invitation I4 to ED, but `status "cancelled"`, `invited_by_user_id None`.
5. I0 = invitation I0 to EA, but `workspace_id W0.id`, `invited_by_user_id U0.id`.
6. I9 = invitation I9 to EA, but `workspace_id W2.id`, `invited_by_user_id U2.id`.

**When**
- `result = svc.list_invitations(db, workspace_id=W1.id, requesting_user_id=UO.id, include_expired=True)`.

**Then**
1. returns: `ids0(result) == {I1.id, I2.id, I3.id, I4.id}`.
2. returns: `all(w.id == W1.id for (i, w, p) in result)`.
3. returns: `{i.id: (p.id if p else None) for (i, w, p) in result} == {I1.id: UO.id, I2.id: UA.id, I3.id: UB.id, I4.id: None}`.

### WSS-LI-03 — an invitation without an inviter is paired with None
- **Rules:** `list_invitations` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1 = invitation I1 to EA, but `invited_by_user_id None`.
2. I2 = invitation I2 to EB, but `invited_by_user_id UA.id`.
3. I3 = invitation I3 to EC.

**When**
- `result = svc.list_invitations(db, workspace_id=W1.id, requesting_user_id=UO.id)`.

**Then**
1. returns: `ids0(result) == {I1.id, I2.id, I3.id}`.
2. returns: `{i.id: (p.id if p else None) for (i, w, p) in result} == {I1.id: None, I2.id: UA.id, I3.id: UO.id}`.

### WSS-LI-04 — an active manager may not list invitations
- **Rules:** `list_invitations` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UA, "manager").
2. invitation I1 to EB, but `invited_by_user_id UB.id`.

**When**
- `svc.list_invitations(db, workspace_id=W1.id, requesting_user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == OWNONLY`.

### WSS-LI-05 — the read neither commits nor rolls back
- **Rules:** `list_invitations` R6; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I1 = invitation I1 to EA.
2. I2 = invitation I2 to EB, but `invited_by_user_id UA.id` (commit point after this line).
3. extra row X.

**When**
- spies: `result = svc.list_invitations(db, workspace_id=W1.id, requesting_user_id=UO.id)`.

**Then**
1. returns: `{i.id: (p.id if p else None) for (i, w, p) in result} == {I1.id: UO.id, I2.id: UA.id}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: x_kept.
5. committed: x_gone.

### WSS-LI-06 — inviters are read together
- **Rules:** `list_invitations` R5 [BUG-2252]
- **Kind:** bug
- **Expect:** xfail BUG-2252
- **Fails today on:** Then 2 (one profile read per invitation)

**Given**
1. member(UA, "member"); member(UB, "member"); member(UC, "member"); member(UQ, "member").
2. invitation J1 to ED; invitation J2 to ED, but `invited_by_user_id UA.id`; invitation J3 to ED, but `invited_by_user_id UB.id`; invitation J4 to ED, but `invited_by_user_id UC.id`; invitation J5 to ED, but `invited_by_user_id UQ.id` (commit point after this line).
3. recorder.

**When**
- `result = svc.list_invitations(db, workspace_id=W1.id, requesting_user_id=UO.id)`.

**Then**
1. returns: `len(result) == 5`.
2. count: `len(stmts) <= 3`.

### WSS-LI-07 — the invitation query is ordered (pass-through)
- **Rules:** `list_invitations` R4 [BUG-1401]
- **Kind:** bug
- **Expect:** xfail BUG-1401
- **Fails today on:** Then 2 (no `ORDER BY` in the invitations SELECT)

**Given**
1. invitation I1 to EA (commit point after this line).
2. recorder.

**When**
- `result = svc.list_invitations(db, workspace_id=W1.id, requesting_user_id=UO.id)`.

**Then**
1. returns: `len(result) == 1`.
2. count: `any("workspace_invitations" in s and "ORDER BY" in s.upper() for s in stmts)`.

## `WorkspaceService.accept_invitation`

### WSS-AI-01 — accepting makes the user a member with the invitation's role and position
- **Rules:** `accept_invitation` R1, R4, R7; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `role "manager"`, `position "Lead"` (commit point after this line).

**When**
- `result = svc.accept_invitation(db, workspace_id=W1.id, token=f"tok-I-{TAG}", current_user_id=UA.id, current_user_email=EA)`.

**Then**
1. returns: `isinstance(result, WorkspaceMember)`, `not ({c.key for c in sa_inspect(result).mapper.column_attrs} & sa_inspect(result).expired_attributes)`.
2. committed: re-read the member `result.id`: `workspace_id == W1.id`, `user_id == UA.id`, `status == "active"`, `role == "manager"`, `position == "Lead"`.
3. committed: re-read I: `status == "accepted"`, `accepted_by_user_id == UA.id`.
4. committed: audit(W1, "invitation_accepted") has exactly 1 row.

### WSS-AI-02 — a given position replaces the invitation's
- **Rules:** `accept_invitation` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `position "Lead"` (commit point after this line).

**When**
- `result = svc.accept_invitation(db, workspace_id=W1.id, token=f"tok-I-{TAG}", current_user_id=UA.id, current_user_email=EA, position="Chief")`.

**Then**
1. returns: `result.position == "Chief"`.
2. committed: re-read the member `result.id`: `position == "Chief"`.

### WSS-AI-03 — an empty position replaces the invitation's too
- **Rules:** `accept_invitation` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `position "Lead"` (commit point after this line).

**When**
- `result = svc.accept_invitation(db, workspace_id=W1.id, token=f"tok-I-{TAG}", current_user_id=UA.id, current_user_email=EA, position="")`.

**Then**
1. returns: `result.position == ""`.
2. committed: re-read the member `result.id`: `position == ""`.

### WSS-AI-04 — a valid invitation of W2 used under W1: 400, nothing changed
- **Rules:** `accept_invitation` R2, R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `workspace_id W2.id`, `invited_by_user_id U2.id` (commit point after this line).
2. extra row X.

**When**
- `svc.accept_invitation(db, workspace_id=W1.id, token=f"tok-I-{TAG}", current_user_id=UA.id, current_user_email=EA, position="Chief")`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Invitation does not belong to this workspace"`.
4. count: x_gone.
5. unchanged: unchanged(I).
6. nothing written.

### WSS-AI-05 — a valid invitation of W0 used under W1: 400
- **Rules:** `accept_invitation` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `workspace_id W0.id`, `invited_by_user_id U0.id` (commit point after this line).

**When**
- `svc.accept_invitation(db, workspace_id=W1.id, token=f"tok-I-{TAG}", current_user_id=UA.id, current_user_email=EA)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.detail == "Invitation does not belong to this workspace"`.
3. unchanged: unchanged(I).
4. nothing written.

### WSS-AI-06 — an expired invitation of another workspace gets the expiry message
- **Rules:** `accept_invitation` R1, R2
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `workspace_id W2.id`, `expires_at NOW - DAY` (commit point after this line).

**When**
- `svc.accept_invitation(db, workspace_id=W1.id, token=f"tok-I-{TAG}", current_user_id=UA.id, current_user_email=EA)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.detail == "Invitation has expired. Please request a new invitation."`.
3. nothing written.

### WSS-AI-07 — an unknown token: 400, pending changes discarded
- **Rules:** `accept_invitation` R1; TX1, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. No invitation (commit point after this line).
2. extra row X.

**When**
- `svc.accept_invitation(db, workspace_id=W1.id, token=f"tok-NONE-{TAG}", current_user_id=UA.id, current_user_email=EA)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Invalid invitation token"`.
4. raises: `isinstance(exc.value.__context__, ValueError)`.
5. count: x_gone.
6. nothing written.

### WSS-AI-08 — another email: 400 naming both emails
- **Rules:** `accept_invitation` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to EA (commit point after this line).

**When**
- `svc.accept_invitation(db, workspace_id=W1.id, token=f"tok-I-{TAG}", current_user_id=UB.id, current_user_email=EB)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.detail == f"This invitation was sent to {EA}. You cannot accept it with {EB}."`.
3. unchanged: unchanged(I).
4. nothing written.

### WSS-AI-09 — already a member: 400, and the position override is rolled back
- **Rules:** `accept_invitation` R4, R5
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UA, "viewer").
2. I = invitation I to EA, but `position "Lead"` (commit point after this line).

**When**
- `svc.accept_invitation(db, workspace_id=W1.id, token=f"tok-I-{TAG}", current_user_id=UA.id, current_user_email=EA, position="Chief")`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.detail == "User is already a member of this workspace"`.
3. re-read I: `position == "Lead"`, `status == "pending"`.
4. nothing written.

### WSS-AI-10 — seats full at accept: 400
- **Rules:** `accept_invitation` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. limit 1.
2. I = invitation I to EA (commit point after this line).

**When**
- `svc.accept_invitation(db, workspace_id=W1.id, token=f"tok-I-{TAG}", current_user_id=UA.id, current_user_email=EA)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.detail == "Workspace has reached maximum member limit (1). Upgrade subscription to add more members."`.
3. unchanged: unchanged(I).
4. nothing written.

### WSS-AI-11 — a failing commit rolls back: no member, invitation still pending
- **Rules:** `accept_invitation` R5, R7; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to EA (commit point after this line).

**When**
- failing commit: `svc.accept_invitation(db, workspace_id=W1.id, token=f"tok-I-{TAG}", current_user_id=UA.id, current_user_email=EA)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(I).
4. nothing written.

### WSS-AI-12 — a failing re-read leaves the membership saved
- **Rules:** `accept_invitation` R7; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to EA (commit point after this line).

**When**
- failing refresh: `svc.accept_invitation(db, workspace_id=W1.id, token=f"tok-I-{TAG}", current_user_id=UA.id, current_user_email=EA)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: `workspace_members` with `workspace_id == W1.id`, `user_id == UA.id`, `status == "active"` has exactly 1 row.

### WSS-AI-13 — a removed member comes back on the same row (pass-through)
- **Rules:** `accept_invitation` R4 (manager R2a) [BUG-1982]
- **Kind:** bug
- **Expect:** xfail BUG-1982
- **Fails today on:** Then 1 (the call raises ValidationError "User is already a member of this workspace")

**Given**
1. MA = member(UA, "viewer", status="inactive").
2. I = invitation I to EA, but `role "manager"` (commit point after this line).

**When**
- `result = svc.accept_invitation(db, workspace_id=W1.id, token=f"tok-I-{TAG}", current_user_id=UA.id, current_user_email=EA)`.

**Then**
1. returns: `result.id == MA.id`.
2. committed: re-read MA: `status == "active"`, `role == "manager"`, `left_at is None`.

### WSS-AI-14 — other pending invitations to the same email are cancelled (pass-through)
- **Rules:** `accept_invitation` R4 (manager R5) [BUG-1874]
- **Kind:** bug
- **Expect:** xfail BUG-1874
- **Fails today on:** Then 2 (J stays `pending`)

**Given**
1. I = invitation I to EA.
2. J = invitation J to EA (commit point after this line).

**When**
- `result = svc.accept_invitation(db, workspace_id=W1.id, token=f"tok-I-{TAG}", current_user_id=UA.id, current_user_email=EA)`.

**Then**
1. returns: `isinstance(result, WorkspaceMember)`.
2. committed: re-read J: `status == "cancelled"`.

### WSS-AI-15 — an invitation expiring exactly now is refused (pass-through)
- **Rules:** `accept_invitation` R1 (manager validate R2) [BUG-1987]
- **Kind:** bug
- **Expect:** xfail BUG-1987
- **Fails today on:** Then 1 (no error: the invitation is accepted)

**Given**
1. I = invitation I to EA, but `expires_at NOW` (commit point after this line).

**When**
- `svc.accept_invitation(db, workspace_id=W1.id, token=f"tok-I-{TAG}", current_user_id=UA.id, current_user_email=EA)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.detail == "Invitation has expired. Please request a new invitation."`.
3. unchanged: unchanged(I).

### WSS-AI-16 — a negative limit means no limit at accept (pass-through)
- **Rules:** `accept_invitation` R4 (manager add R5a) [BUG-1872]
- **Kind:** bug
- **Expect:** xfail BUG-1872
- **Fails today on:** Then 1 (the call raises ValidationError "…limit (-1)…")

**Given**
1. limit -1.
2. I = invitation I to EA (commit point after this line).

**When**
- `result = svc.accept_invitation(db, workspace_id=W1.id, token=f"tok-I-{TAG}", current_user_id=UA.id, current_user_email=EA)`.

**Then**
1. returns: `isinstance(result, WorkspaceMember)`.
2. committed: re-read the member `result.id`: `status == "active"`.

### WSS-AI-17 — the new member records who invited them (pass-through)
- **Rules:** `accept_invitation` R4 (manager add R8) [BUG-1985]
- **Kind:** bug
- **Expect:** xfail BUG-1985
- **Fails today on:** Then 2 (`invited_by_user_id` is NULL)

**Given**
1. I = invitation I to EA (commit point after this line).

**When**
- `result = svc.accept_invitation(db, workspace_id=W1.id, token=f"tok-I-{TAG}", current_user_id=UA.id, current_user_email=EA)`.

**Then**
1. returns: `isinstance(result, WorkspaceMember)`.
2. committed: re-read the member `result.id`: `invited_by_user_id == UO.id`.

### WSS-AI-18 — IP and user agent reach the `invitation_accepted` row
- **Rules:** `accept_invitation` R6 [BUG-1404]
- **Kind:** bug
- **Expect:** xfail BUG-1404
- **Fails today on:** Then 1 (the call raises TypeError: no `ip_address` parameter)

**Given**
1. I = invitation I to EA (commit point after this line).

**When**
- `result = svc.accept_invitation(db, workspace_id=W1.id, token=f"tok-I-{TAG}", current_user_id=UA.id, current_user_email=EA, ip_address="203.0.113.7", user_agent="Mozilla/5.0 Test")`.

**Then**
1. returns: `isinstance(result, WorkspaceMember)`.
2. audit: audit(W1, "invitation_accepted") has exactly 1 row.
3. audit: that row: `ip_address == "203.0.113.7"`, `user_agent == "Mozilla/5.0 Test"`.

### WSS-AI-19 — a position of 256 characters is refused by `AcceptInvitationRequest`
- **Rules:** `update_workspace` R5a [BUG-2256] (`AcceptInvitationRequest.position`)
- **Kind:** bug
- **Expect:** xfail BUG-2256
- **Fails today on:** Then 1 (the schema accepts 256 characters)

**Given**
1. No extra row.

**When**
- build `AcceptInvitationRequest(token=f"tok-I-{TAG}", position="p" * 256)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### WSS-AI-20 — a position of 255 characters is accepted by `AcceptInvitationRequest`
- **Rules:** `update_workspace` R5a (`AcceptInvitationRequest.position`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No extra row.

**When**
- `result = AcceptInvitationRequest(token=f"tok-I-{TAG}", position="p" * 255)` (target `schema`).

**Then**
1. returns: `result.position == "p" * 255`.

## `WorkspaceService.cancel_invitation`

### WSS-XI-01 — the owner cancels a pending invitation; committed, `None` returned
- **Rules:** `cancel_invitation` R1, R2; TC1, TX3
- **Kind:** happy
- **Expect:** pass

**Given**
1. I = invitation I to EA (commit point after this line).

**When**
- `result = svc.cancel_invitation(db, workspace_id=W1.id, invitation_id=I.id, canceller_user_id=UO.id)`.

**Then**
1. returns: `result is None`.
2. committed: re-read I: `status == "cancelled"`.
3. committed: audit(W1, "invitation_cancelled") has exactly 1 row.
4. committed: that row: `user_id == UO.id`, `metadata_json == {"invitation_id": I.id, "email": EA}`.

### WSS-XI-02 — no re-read after the commit
- **Rules:** `cancel_invitation` R2; TX3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I = invitation I to EA (commit point after this line).

**When**
- refresh trap: `result = svc.cancel_invitation(db, workspace_id=W1.id, invitation_id=I.id, canceller_user_id=UO.id)`.

**Then**
1. returns: `result is None`.
2. mock called: `rf.call_count == 0`.
3. committed: re-read I: `status == "cancelled"`.

### WSS-XI-03 — a non-member is refused first; pending changes stay pending
- **Rules:** `cancel_invitation` R1; TX2
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to EA (commit point after this line).
2. extra row X.

**When**
- `svc.cancel_invitation(db, workspace_id=W1.id, invitation_id=I.id, canceller_user_id=U0.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == NOTMEM`.
3. session: `not db.dirty and not db.new and not db.deleted`.
4. count: x_kept.
5. unchanged: unchanged(I).

### WSS-XI-04 — a manager cancelling stays 403; the rollback discards pending changes
- **Rules:** `cancel_invitation` R3; TX1, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. member(UA, "manager").
2. I = invitation I to EB (commit point after this line).
3. extra row X.

**When**
- `svc.cancel_invitation(db, workspace_id=W1.id, invitation_id=I.id, canceller_user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "Only the workspace owner can cancel invitations"`.
4. raises: `isinstance(exc.value.__context__, ValueError)`.
5. count: x_gone.
6. unchanged: unchanged(I).
7. nothing written.

### WSS-XI-05 — the owner of W2, a "member" in W1, cannot cancel W1's invitation
- **Rules:** `cancel_invitation` R2, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. member(U2, "member").
2. I = invitation I to EA (commit point after this line).

**When**
- `svc.cancel_invitation(db, workspace_id=W1.id, invitation_id=I.id, canceller_user_id=U2.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == "Only the workspace owner can cancel invitations"`.
3. unchanged: unchanged(I).

### WSS-XI-06 — "Invitation not found" text reaches the caller (holds before and after BUG-2251)
- **Rules:** `cancel_invitation` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. No invitation (commit point after this line).

**When**
- `svc.cancel_invitation(db, workspace_id=W1.id, invitation_id=MISSING, canceller_user_id=UO.id)`.

**Then**
1. raises: `APIException`.
2. raises: `exc.value.detail == "Invitation not found"`.
3. nothing written.

### WSS-XI-07 — "Cannot cancel … accepted" text reaches the caller (holds before and after BUG-2251)
- **Rules:** `cancel_invitation` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `status "accepted"` (commit point after this line).

**When**
- `svc.cancel_invitation(db, workspace_id=W1.id, invitation_id=I.id, canceller_user_id=UO.id)`.

**Then**
1. raises: `APIException`.
2. raises: `exc.value.detail == "Cannot cancel invitation that is accepted"`.
3. unchanged: unchanged(I).
4. nothing written.

### WSS-XI-08 — an unknown invitation answers 404
- **Rules:** `cancel_invitation` R3 [BUG-2251]
- **Kind:** bug
- **Expect:** xfail BUG-2251
- **Fails today on:** Then 1 (the call raises PermissionDeniedError)

**Given**
1. No invitation (commit point after this line).

**When**
- `svc.cancel_invitation(db, workspace_id=W1.id, invitation_id=MISSING, canceller_user_id=UO.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Invitation not found"`.
4. session: `not db.dirty and not db.new`.
5. nothing written.

### WSS-XI-09 — an accepted invitation answers 400
- **Rules:** `cancel_invitation` R3 [BUG-2251]
- **Kind:** bug
- **Expect:** xfail BUG-2251
- **Fails today on:** Then 1 (the call raises PermissionDeniedError)

**Given**
1. I = invitation I to EA, but `status "accepted"` (commit point after this line).

**When**
- `svc.cancel_invitation(db, workspace_id=W1.id, invitation_id=I.id, canceller_user_id=UO.id)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot cancel invitation that is accepted"`.
4. session: `not db.dirty and not db.new`.
5. unchanged: unchanged(I).

### WSS-XI-10 — a cancelled invitation answers 400
- **Rules:** `cancel_invitation` R3 [BUG-2251]
- **Kind:** bug
- **Expect:** xfail BUG-2251
- **Fails today on:** Then 1 (the call raises PermissionDeniedError)

**Given**
1. I = invitation I to EA, but `status "cancelled"` (commit point after this line).

**When**
- `svc.cancel_invitation(db, workspace_id=W1.id, invitation_id=I.id, canceller_user_id=UO.id)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot cancel invitation that is cancelled"`.
4. session: `not db.dirty and not db.new`.
5. unchanged: unchanged(I).

### WSS-XI-11 — an invitation of W0 answers 404 "Invitation not found"
- **Rules:** `cancel_invitation` R3 [BUG-2251] (manager R2, BUG-1981: both must be fixed)
- **Kind:** bug
- **Expect:** xfail BUG-2251
- **Fails today on:** Then 1 (the call raises PermissionDeniedError)

**Given**
1. I = invitation I to EA, but `workspace_id W0.id`, `invited_by_user_id U0.id` (commit point after this line).

**When**
- `svc.cancel_invitation(db, workspace_id=W1.id, invitation_id=I.id, canceller_user_id=UO.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == "Invitation not found"`.
3. session: `not db.dirty and not db.new`.
4. unchanged: unchanged(I).

### WSS-XI-12 — an invitation of W2 answers 404 "Invitation not found"
- **Rules:** `cancel_invitation` R3 [BUG-2251] (manager R2, BUG-1981: both must be fixed)
- **Kind:** bug
- **Expect:** xfail BUG-2251
- **Fails today on:** Then 1 (the call raises PermissionDeniedError)

**Given**
1. I = invitation I to EA, but `workspace_id W2.id`, `invited_by_user_id U2.id` (commit point after this line).

**When**
- `svc.cancel_invitation(db, workspace_id=W1.id, invitation_id=I.id, canceller_user_id=UO.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == "Invitation not found"`.
3. session: `not db.dirty and not db.new`.
4. unchanged: unchanged(I).

### WSS-XI-13 — a non-owner gets the owner message first, even for an unknown id (pass-through)
- **Rules:** `cancel_invitation` R2 (manager R1) [BUG-1986]
- **Kind:** bug
- **Expect:** xfail BUG-1986
- **Fails today on:** Then 2 (today's detail is "Invitation not found")

**Given**
1. member(UA, "manager") (commit point after this line).

**When**
- `svc.cancel_invitation(db, workspace_id=W1.id, invitation_id=MISSING, canceller_user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.detail == "Only the workspace owner can cancel invitations"`.
3. nothing written.

### WSS-XI-14 — IP and user agent reach the `invitation_cancelled` row
- **Rules:** `cancel_invitation` R4 [BUG-1404]
- **Kind:** bug
- **Expect:** xfail BUG-1404
- **Fails today on:** Then 1 (the call raises TypeError: no `ip_address` parameter)

**Given**
1. I = invitation I to EA (commit point after this line).

**When**
- `result = svc.cancel_invitation(db, workspace_id=W1.id, invitation_id=I.id, canceller_user_id=UO.id, ip_address="203.0.113.7", user_agent="Mozilla/5.0 Test")`.

**Then**
1. returns: `result is None`.
2. audit: audit(W1, "invitation_cancelled") has exactly 1 row.
3. audit: that row: `ip_address == "203.0.113.7"`, `user_agent == "Mozilla/5.0 Test"`.

### WSS-XI-15 — a failing commit rolls back, the invitation stays pending
- **Rules:** `cancel_invitation` R2; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to EA (commit point after this line).

**When**
- failing commit: `svc.cancel_invitation(db, workspace_id=W1.id, invitation_id=I.id, canceller_user_id=UO.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(I).
4. nothing written.

### WSS-XI-16 — "Cannot cancel … cancelled" text reaches the caller (holds before and after BUG-2251)
- **Rules:** `cancel_invitation` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `status "cancelled"` (commit point after this line).

**When**
- `svc.cancel_invitation(db, workspace_id=W1.id, invitation_id=I.id, canceller_user_id=UO.id)`.

**Then**
1. raises: `APIException`.
2. raises: `exc.value.detail == "Cannot cancel invitation that is cancelled"`.
3. unchanged: unchanged(I).
4. nothing written.

## `WorkspaceService.get_my_invitations`

### WSS-MI-01 — pending, unexpired invitations to the email in every workspace, with workspace and inviter
- **Rules:** `get_my_invitations` R1, R2, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1 = invitation I1 to EA.
2. I2 = invitation I2 to EA, but `workspace_id W2.id`, `invited_by_user_id U2.id`.
3. I5 = invitation I5 to EA, but `workspace_id W0.id`, `invited_by_user_id None`.
4. I0 = invitation I0 to EA, but `workspace_id W0.id`, `expires_at NOW - DAY`, `invited_by_user_id U0.id`.
5. I3 = invitation I3 to EA, but `status "accepted"`, `invited_by_user_id UB.id`.
6. I4 = invitation I4 to EB, but `invited_by_user_id UC.id`.

**When**
- `result = svc.get_my_invitations(db, user_email=EA)`.

**Then**
1. returns: `ids0(result) == {I1.id, I2.id, I5.id}`.
2. returns: `{i.id: (w.id, p.id if p else None) for (i, w, p) in result} == {I1.id: (W1.id, UO.id), I2.id: (W2.id, U2.id), I5.id: (W0.id, None)}`.

### WSS-MI-02 — an invitation to a workspace the user already belongs to is listed
- **Rules:** `get_my_invitations` R3 (D8)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. member(UA, "viewer").
2. I1 = invitation I1 to EA.

**When**
- `result = svc.get_my_invitations(db, user_email=EA)`.

**Then**
1. returns: `ids0(result) == {I1.id}`.

### WSS-MI-03 — an email with no invitation gets an empty list
- **Rules:** `get_my_invitations` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. invitation I1 to EB.

**When**
- `result = svc.get_my_invitations(db, user_email=ED)`.

**Then**
1. returns: `result == []`.

### WSS-MI-04 — the email matches ignoring capitals (pass-through)
- **Rules:** `get_my_invitations` R1 [BUG-1402]
- **Kind:** bug
- **Expect:** xfail BUG-1402
- **Fails today on:** Then 1 (exact match: `[]`)

**Given**
1. I1 = invitation I1 to EA.

**When**
- `result = svc.get_my_invitations(db, user_email=f"Ann.{TAG}@Acme.com")`.

**Then**
1. returns: `ids0(result) == {I1.id}`.

### WSS-MI-05 — the read neither commits nor rolls back
- **Rules:** `get_my_invitations` R5; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I1 = invitation I1 to EA (commit point after this line).
2. extra row X.

**When**
- spies: `result = svc.get_my_invitations(db, user_email=EA)`.

**Then**
1. returns: `ids0(result) == {I1.id}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: x_kept.
5. committed: x_gone.

### WSS-MI-06 — workspaces and inviters are read together
- **Rules:** `get_my_invitations` R4 [BUG-2252]
- **Kind:** bug
- **Expect:** xfail BUG-2252
- **Fails today on:** Then 2 (one or two reads per invitation)

**Given**
1. W3, W4.
2. invitation J0 to EA, but `workspace_id W0.id`, `invited_by_user_id U0.id`; invitation J1 to EA; invitation J2 to EA, but `workspace_id W2.id`, `invited_by_user_id U2.id`; invitation J3 to EA, but `workspace_id W3.id`, `invited_by_user_id UB.id`; invitation J4 to EA, but `workspace_id W4.id`, `invited_by_user_id UC.id` (commit point after this line).
3. recorder.

**When**
- `result = svc.get_my_invitations(db, user_email=EA)`.

**Then**
1. returns: `len(result) == 5`.
2. count: `len(stmts) <= 3`.

### WSS-MI-07 — the invitation query is ordered (pass-through)
- **Rules:** `get_my_invitations` R1 [BUG-1401]
- **Kind:** bug
- **Expect:** xfail BUG-1401
- **Fails today on:** Then 2 (no `ORDER BY` in the invitations SELECT)

**Given**
1. invitation I1 to EA (commit point after this line).
2. recorder.

**When**
- `result = svc.get_my_invitations(db, user_email=EA)`.

**Then**
1. returns: `len(result) == 1`.
2. count: `any("workspace_invitations" in s and "ORDER BY" in s.upper() for s in stmts)`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Response shaping (`is_owner`, plan fields, member name / email, invitation details) | `/workspaces/` endpoints (integration) | the response bodies |
| `RoleChangeRequest` role list, `InviteUserRequest` `EmailStr`, `WorkspaceCreate` | schema / integration | 422 on `owner` as a new role and on a bad email |
| HTTP status of `APIException`, global `IntegrityError` handler | integration | 400 / 403 / 404 / 409 bodies |
| `remove_member` R2: BUG-1201 (approver clean-up), BUG-1883 (assignee clean-up) | `workspace_manager.cases.md` | per order type; the service only passes the call through (BUG-1280's pass-through card WSS-RM-17 stands for the group) |
| Manager matrices (seat limits, role pairs, expiry boundaries, R6a audit order) | `workspace_manager.cases.md` | not repeated here |
| Endpoint passes the client address and `User-Agent` (BUG-1404) | `/workspaces/` endpoints (integration) | the values reach the service |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 5 | `update_member_role` R4a [BUG-2258] | The "Today" note covers only an `owner` target; what `new_role=None` does today for another member (role stored NULL, or a failure at the commit) is not stated. | WSS-MR-33 names Then 1 with both outcomes and is `Author: claude`. |

Gaps 1–4 were closed by the spec's Gap log (G1–G5; G4 added BUG-2256).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_require_active_membership` | R1 | WSS-AM-01, AM-06, AM-12 |
| | R2 | WSS-AM-02, AM-03, AM-04, AM-05, AM-07 |
| | R3 | WSS-AM-06, AM-08, AM-09, AM-10, AM-11 |
| | R4 | WSS-AM-12, AM-13 |
| `_require_owner` | R1 | WSS-RO-07, RO-08 |
| | R2 | WSS-RO-01 … RO-06 |
| | R3 | WSS-RO-01 |
| `list_user_workspaces` | R1 | WSS-LW-01, LW-02, LW-03 |
| | R2 [BUG-1400] | WSS-LW-01, LW-08 |
| | R3 | not testable (FK cascade, spec says unreachable) |
| | R4 [BUG-2252] | WSS-LW-07 |
| | R5; TC6 | WSS-LW-04, LW-05, LW-06 |
| `create_workspace` | R1 | WSS-C-01, C-02, C-10 [BUG-1980] |
| | R2 / Errors row 1; TX1 | WSS-C-03, C-04, C-05 |
| | R3 / Errors row 2; TC3, TC4, TC5 | WSS-C-06, C-07, C-08 |
| | R4 [BUG-1404] | WSS-C-09 |
| | TC1, TC2 | WSS-C-01 |
| `get_workspace_with_plan` | R1 | WSS-G-03, G-04 |
| | R2 | WSS-G-01, G-02 |
| | R3 | WSS-G-03 (unreachable 404; unknown id is 403) |
| | R4; TC6 | WSS-G-05 |
| `update_workspace` | R1 [BUG-2250] / Errors rows 1–2 | WSS-U-13 … U-20 |
| | R2 / Errors row 3; TX2 | WSS-U-11, U-12 |
| | R3 | WSS-U-01, U-02 |
| | R4 [BUG-1980] | WSS-U-06, U-07, U-08, U-09, U-10 |
| | R5 | WSS-U-02, U-03, U-04, U-05 |
| | R6 [BUG-2253] | WSS-U-21, U-22, U-23, U-24 |
| | R5a [BUG-2256] | WSS-U-28, U-29, C-11, C-12, C-13, C-14, MR-24, MR-25, SI-14, SI-15, AI-19, AI-20 |
| | R7; TC1, TC2, TC3, TC4, TC5 | WSS-U-01, U-23, U-27, U-25, U-26 |
| `list_members` | R1 | WSS-LM-01, LM-04, LM-05 |
| | R2 [BUG-1400] | WSS-LM-01, LM-08 |
| | R3 | WSS-LM-01, LM-02, LM-03 |
| | R4 | WSS-LM-01 |
| | R5 [BUG-2252] | WSS-LM-07 |
| | R6; TC6 | WSS-LM-06 |
| `update_member_role` | R1 [BUG-2250] | WSS-MR-13 … MR-17 |
| | R2; TX2 | WSS-MR-12, MR-30 |
| | R3 [BUG-2254]; TX2 | WSS-MR-05, MR-07, MR-08, MR-09, MR-10 |
| | R4 | WSS-MR-11, MR-32 |
| | R4a [BUG-2258] | WSS-MR-31, MR-32, MR-33 |
| | R5; TC1, TC2, TC4, TC5 | WSS-MR-01, MR-02, MR-03, MR-29, MR-21, MR-23, MR-22; TC3 before the commit: not unit-testable (spec TX1a), no card |
| | R5a [BUG-2257]; TX2 | WSS-MR-04, MR-26, MR-27, MR-28, MR-29, MR-30 |
| | R6 [BUG-2253] | WSS-MR-18, MR-19, MR-20 |
| | R7 | WSS-MR-06 |
| `remove_member` | R1; TX2 | WSS-RM-04, RM-05 |
| | R2 [BUG-1990] [BUG-1280] | WSS-RM-01, RM-02, RM-06, RM-07, RM-15, RM-16, RM-17 |
| | R3 [BUG-2251]; TX1, TC3 | WSS-RM-08, RM-09, RM-10, RM-11 … RM-14 |
| | R4 [BUG-1404] | WSS-RM-18 |
| | R5; TC4 | WSS-RM-19; TC3 other-exception path: not unit-testable (spec TX1a), no card |
| | TX3 | WSS-RM-01, RM-03 |
| `send_invitation` | R1; TX2 | WSS-SI-02, SI-03, SI-04, SI-05 |
| | R2 [BUG-1873] [BUG-1871] | WSS-SI-01, SI-09, SI-10 |
| | R3; TX1, TC3 | WSS-SI-06, SI-07, SI-08 |
| | R4 [BUG-1404] | WSS-SI-11 |
| | TC1, TC2, TC4, TC5 | WSS-SI-01, SI-12, SI-13 |
| `list_invitations` | R1 | WSS-LI-01, LI-04 |
| | R2 | WSS-LI-01, LI-02 |
| | R3 | WSS-LI-01, LI-02, LI-03, LI-05 (each invitation's own inviter) |
| | R4 [BUG-1401] | WSS-LI-07 |
| | R5 [BUG-2252] | WSS-LI-06 |
| | R6; TC6 | WSS-LI-05 |
| `accept_invitation` | R1 [BUG-1987]; TX1 | WSS-AI-06, AI-07, AI-08, AI-15 |
| | R2 | WSS-AI-04, AI-05, AI-06 |
| | R3 | WSS-AI-02, AI-03, AI-09 |
| | R4 [BUG-1982] [BUG-1874] [BUG-1872] [BUG-1985] | WSS-AI-01, AI-09, AI-10, AI-13, AI-14, AI-16, AI-17 |
| | R5; TC3 | WSS-AI-04, AI-07, AI-09 |
| | R6 [BUG-1404] | WSS-AI-18 |
| | R7; TC1, TC2, TC4, TC5 | WSS-AI-01, AI-11, AI-12 |
| `cancel_invitation` | R1; TX2 | WSS-XI-03 |
| | R2 [BUG-1986] | WSS-XI-01, XI-05, XI-13 |
| | R3 [BUG-2251]; TX1, TC3 | WSS-XI-04, XI-06, XI-07, XI-16, XI-08 … XI-12 |
| | R4 [BUG-1404] | WSS-XI-14 |
| | TC1, TC4; TX3 | WSS-XI-01, XI-02, XI-15; TC3 other-exception path: not unit-testable (spec TX1a), no card |
| `get_my_invitations` | R1 [BUG-1402] [BUG-1401] | WSS-MI-01, MI-03, MI-04, MI-07 |
| | R2 | WSS-MI-01 (each invitation's own workspace and inviter) |
| | R3 | WSS-MI-02 |
| | R4 [BUG-2252] | WSS-MI-06 |
| | R5; TC6 | WSS-MI-01, MI-05 |
