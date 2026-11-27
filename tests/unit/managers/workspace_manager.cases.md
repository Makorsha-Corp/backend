# Test cases — `app/managers/workspace_manager.py`

> **Spec:** `tests/unit/managers/workspace_manager.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-04; nothing open). OQ-16 and OQ-17 (BUG-1989) are the owner's answers, both kept at today's behaviour in their own rules; BUG-1990 (who may remove members) is the owner's answer; the other decisions were Claude's under the reviewer's delegation.
> **Revision:** 3 (2026-11-04) — verifier (`workspace_manager.verify.md`): WSMG-AI-18 gains Then 3–4. Those lines check the superseded `invitation_cancelled` audit row and its email exactly as stored, `f"Ann.{TAG}@Acme.com"`, so a fix that lower-cases it fails. The card stays xfail BUG-1874 and still fails on Then 2. New: WSMG-RM-83, RM-84, RM-85, where a `manager`, `viewer` and `finance` remover each ask to remove the owner. R2 runs before any remover-role check, so they are pass. No ID retired.
> Revision 2 (2026-11-04) — spec fill-gaps G1–G10. Changed: G1 `returns: result is None` added to every passing success card of remove and cancel (WSMG-RM-01 … RM-07, RM-13, RM-57, RM-58, RM-59, RM-67, RM-75, RM-77, RM-80, RM-81, WSMG-XI-01, XI-02, XI-03, XI-25); G2 WSMG-CW-02 (five counters `0`, `last_usage_reset_at is not None`); G3 WSMG-RM-70 … RM-74 rewritten (column-level open and not-open orders per type, one not-open order per condition, event columns), RM-75 (column-level), RM-76, RM-78, RM-79 (event columns); G8 WSMG-CW-12 (patch target) and Conventions Race simulations; G9, G10 Conventions Externals. New: WSMG-XI-27 (G6, stored mixed-case email), WSMG-AI-26 (G7 R6a order today, pass), WSMG-AI-27 (R6a order with superseded rows, xfail BUG-1874), WSMG-AI-28 (R6a IP / user agent on every row, xfail BUG-1404). G4: no card. G5: already WSMG-CW-16 (`None`) and CW-17 (`""`), unchanged. No ID retired.
> **Counts:** 305 cases · 221 expected-to-pass · 84 expected-to-fail (bugs) · 10 deferred

## Reviewer summary
- **Per callable:** `create_workspace_with_owner` 34 (3 bug) · `add_member_to_workspace` 40 (7 bug) · `remove_member_from_workspace` 85 (44 bug) · `create_invitation` 60 (14 bug) · `validate_invitation_for_user` 22 (1 bug) · `accept_invitation` 28 (9 bug) · `cancel_invitation` 27 (6 bug) · pending P16 (OQ-16) 4 · pending P17 (OQ-17 / BUG-1989) 5.
- **Expected-to-fail by bug:** BUG-1990 34 · BUG-1404 7 · BUG-1201 5 · BUG-1873 5 · BUG-1982 4 · BUG-1860 3 · BUG-1872 3 · BUG-1874 4 · BUG-1983 3 · BUG-1986 3 · BUG-1871 2 · BUG-1883 2 · BUG-1980 2 · BUG-1981 2 · BUG-1985 2 · BUG-1280 1 · BUG-1984 1 · BUG-1987 1. All strict.
- **Depth:** full (skill step 1a). The cards are the reference for the SSLCommerz subscription portal, so seats get full depth. The limit is tested at, one below and one above (members only, members plus invitations, invitations only, the owner alone at a limit of 1). Negative limits (-1, -5) mean unlimited; these are strict xfail BUG-1871 / BUG-1872. An expired invitation frees its seat at exactly `expires_at == NOW` but not one microsecond before. Accepted and cancelled invitations hold no seat, and neither do suspended or removed members. Two invitations to one email hold two seats. Members and invitations of W0 (built before W1) and W2 count for nothing in W1. An inactive plan is still enforced. Accepting cancels the other pending invitations, expired ones included (BUG-1874), but not those of other workspaces, other emails, or other states.
- **Pending rules are fenced off.** OQ-16 (any active plan at creation) appears only in P16. `max_members = 0` appears only in P17. No other card passes the id of an active plan at creation (the R2 refusal cards pass unknown or inactive ids, which stand whatever the portal decides) or uses a limit of 0, so a portal decision changes only those 9 cards.
- **Member removal:** one card per pair of remover role and target role (WSMG-RM-01 … WSMG-RM-47): `owner`, `ground-team-manager`, `manager`, `ground-team`, `member`, `viewer`, `finance` against the six non-owner roles, plus `Owner`, `Manager`, `""`, `admin` and `"ground-team-manager "`. The owner as target is refused whoever asks, and that check comes first (WSMG-RM-48 … WSMG-RM-51, WSMG-RM-83 … WSMG-RM-85). Grants held in another workspace (WSMG-RM-61 … WSMG-RM-66, WSMG-XI-23, WSMG-XI-24): the caller is the owner or a manager of W0 or W2 but passes their W1 role. This guards a BUG-1990 fix that would read the role by user id alone.
- **Notable design choices:** one race simulation (WSMG-CW-12, the slug check). WSMG-CW-26 gives a workspace an explicit high id, so the seed's "already exists" check meets a workspace above the new one. The clean-up cards for BUG-1201, BUG-1280 and BUG-1883, the token spy and the race card are `Author: claude` (15 cards), because their setup goes beyond the Conventions vocabulary. Each bug-rule clean-up has a pass card for the rows that must stay. `add_member` R3 "after R2" cannot be built: a membership row needs an existing workspace. Only "after R1" is tested.
- **Needs a decision:** None. Spec gaps 1–10 are closed by the spec's Gap log (G1–G10, 2026-11-04). AI-28 carries BUG-1404 as its reason but also needs BUG-1874 fixed before it can pass.

## Conventions for this module

**IDs.** `WSMG` = `app/managers/workspace_manager.py`. `CW` create_workspace_with_owner · `AM` add_member_to_workspace · `RM` remove_member_from_workspace · `CI` create_invitation · `VI` validate_invitation_for_user · `AI` accept_invitation · `XI` cancel_invitation. Pending sections, kept apart so the portal decision changes only them: `P16` (OQ-16, `create_workspace_with_owner` R1) · `P17` (OQ-17 / BUG-1989, `max_members = 0`).

**Actors and fixed values.**
- `M` = the singleton `workspace_manager` (`from app.managers.workspace_manager import workspace_manager`). `db` = the test's real session, always the first positional argument; every other argument is passed by keyword. `result` = what the When call returns. The session does not autoflush.
- Classes: `Workspace`, `WorkspaceMember`, `WorkspaceInvitation`, `WorkspaceAuditLog`, `SubscriptionPlan`, `Profile`, `Status`, `OrderWorkflow`, `Department`, `ItemTag`, `AccountTag` = the model of the same name in `app.models.<snake_case name>`. `WorkspaceCreate` = `app.schemas.workspace.WorkspaceCreate`. `make_subscription_plan`, `make_workspace`, `make_profile` = `tests/unit/factories.py`. `IntegrityError` = `sqlalchemy.exc.IntegrityError`. `ValidationError` = `pydantic.ValidationError`. `patch` = `unittest.mock.patch`. `re`, `uuid`, `datetime`, `timedelta` = the standard ones.
- MISSING = `999999999`. NOW = `datetime(2026, 3, 5, 12, 0, 0)` (naive UTC). US = `timedelta(microseconds=1)`. DAY = `timedelta(days=1)`. T1 = `datetime(2026, 2, 1, 9, 0, 0)`. T2 = `datetime(2026, 2, 10, 9, 0, 0)`.
- TAG = `uuid.uuid4().hex[:8]`, computed once at the start of each test (lowercase hex). SL = `f"acme-{TAG}"`. EO = `f"own.{TAG}@acme.com"`, EA = `f"ann.{TAG}@acme.com"`, EB = `f"bob.{TAG}@acme.com"`, EC = `f"cat.{TAG}@acme.com"`, ED = `f"dan.{TAG}@acme.com"`, EE = `f"eve.{TAG}@acme.com"`. ED and EE belong to no profile.

**Externals.** Every When runs inside `with patch("app.managers.workspace_manager.utcnow", return_value=NOW), patch("app.dao.workspace_invitation.utcnow", return_value=NOW):` (the helper does it; a card never repeats it). Nothing else is mocked, except in cards marked `Author: claude` that say so. `invited_at`, `created_at` and `last_usage_reset_at` come from model defaults on the real clock and are only checked `is not None`. Every datetime column here is `timestamp without time zone` holding naive UTC: compare with the naive NOW. The one aware column, `workspace_audit_logs.created_at` (`timestamptz`), is never compared. Column names `item_tags.tag_code`, `account_tags.tag_code`, `order_workflows.type` are confirmed by the spec (R9).

**Standing rows.** In every test, built in this order, no Given line:
1. PL0, PL1, PL2 = three `make_subscription_plan(db, max_members=10)` (`is_default False`, `is_active True`).
2. W0 = `make_workspace(db, subscription_plan_id=PL0.id)`, then W1 the same with PL1, then W2 with PL2. So `W0.id < W1.id < W2.id`.
3. UO = `make_profile(db, email=EO, name="Olive Owner")`, then UA = `make_profile(db, email=EA, name="Ann Lee")`, UB = (EB, `"Bob Roy"`), UC = (EC, `"Cat Kim"`). So `UO.id < UA.id < UB.id < UC.id`.
4. MO = `WorkspaceMember(workspace_id=W1.id, user_id=UO.id, role="owner", status="active")`: W1's owner and, so far, its only member.
No other plan, member, invitation or audit row exists unless the card's Given lists it. No plan is `is_default True` unless the Given lists one.

**Given rows.** Inserted directly (never through `M`) and flushed one at a time in the order written, so ids rise in that order. After the word "but" a line lists every column that differs. A line written as code is a step to run exactly as written, at that place.
- **member(U)** = `WorkspaceMember(workspace_id=W1.id, user_id=U.id, role="member", status="active")`.
- **invitation X to e** = `WorkspaceInvitation(workspace_id=W1.id, email=e, role="member", token=f"tok-X-{TAG}", status="pending", expires_at=NOW + DAY, invited_by_user_id=UO.id)`, where X in the token is the row's own Given name (`f"tok-J-{TAG}"` for J).
- **limit n** = the code step `PL1.max_members = n; db.flush()` (W1's plan).
- **Pk** = `make_profile(db)` (an extra person; P1, P2, … in the order built).
- Plans for `create_workspace_with_owner`: **PD** = `make_subscription_plan(db, name=f"free-{TAG}", is_default=True, is_active=True, max_members=3)`. **PX** = `make_subscription_plan(db, name=f"pro-{TAG}", is_default=False, is_active=True, max_members=10)`. **PE** = `make_subscription_plan(db, name=f"enterprise-{TAG}", is_default=False, is_active=True, max_members=-1)`. **PI** = `make_subscription_plan(db, name=f"old-{TAG}", is_default=False, is_active=False, max_members=10)`.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id; values are database values. "the new workspace" = the `workspaces` row with `id == result.id`.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot after the last Given line, after `db.refresh(X)`). **unchanged(X) except `c`** = the same, leaving out the columns named.
- **nothing written** = the numbers of rows in `workspaces`, `workspace_members`, `workspace_invitations`, `workspace_audit_logs` (all workspaces) equal their values before the call.
- **nothing seeded** = the same for `statuses`, `order_workflows`, `departments`, `item_tags`, `account_tags`.
- **audit(W)** = `db.expire_all()`, then the `WorkspaceAuditLog` rows with `workspace_id == W.id`, ordered by `id`, as a list. **audit(W, a)** = the same, only `action == a`. "that row" = the one row just counted.
- **members(W, U)** = the `WorkspaceMember` rows with `workspace_id == W.id` and `user_id == U.id`. **invitations(W)** = the `WorkspaceInvitation` rows with `workspace_id == W.id`.
- `raises: ValueError` = plain `with pytest.raises(ValueError) as exc:` around the call (no savepoint); further `raises:` lines assert on `exc.value` after the block.
- `raises: IntegrityError on flush` = `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards.
- `raises: ValidationError` (target `schema`) = `pytest.raises` around building the schema object only; `M` is not called.
- **rolled back** = `sp = db.begin_nested()` directly before the call and `with patch.object(db, "commit", wraps=db.commit) as cm:` around it; the "inside" checks run first, then `sp.rollback()` and the "after" checks.
- `session:` lines check `db.new`, `db.dirty`, `db.deleted` directly after the call, before anything expires the session.

**xfail cards.** Write the call and the checks exactly as shown, also when the call uses a parameter that does not exist yet. `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`. Every xfail card here is strict.

**Race simulations.** WSMG-CW-12 only (`create_workspace_with_owner` R5): `monkeypatch.setattr(M.workspace_dao, "get_by_slug", lambda *a, **k: None)` (the manager reaches the lookup as `self.workspace_dao.get_by_slug`; the attribute is the `app.dao.workspace.workspace_dao` singleton), to put the code in the state "a concurrent request already passed the slug check". Nothing else may be patched for this.

## `WorkspaceManager.create_workspace_with_owner`

> No card in this section passes a truthy `subscription_plan_id`: that path is `create_workspace_with_owner` R1, pending the payment portal (OQ-16), and lives only in section P16. R2 refusals stay here: the spec says they stand whatever the portal decides.

### WSMG-CW-01 — create stores the workspace on the default plan, owned and created by the caller
- **Rules:** `create_workspace_with_owner` R3, R6, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. PD.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL, billing_email="billing@acme.com"), owner_user_id=UA.id)`.

**Then**
1. returns: `isinstance(result, Workspace)`.
2. returns: `result.id is not None`.
3. re-read the new workspace: `name == "Acme Tools"`, `slug == SL`, `billing_email == "billing@acme.com"`.
4. re-read the new workspace: `subscription_plan_id == PD.id`.
5. re-read the new workspace: `owner_user_id == UA.id`, `created_by_user_id == UA.id`.
6. count: `workspaces` with `slug == SL` has exactly 1 row.

### WSMG-CW-02 — a new workspace starts a 14-day trial with the model defaults, on the free default plan too
- **Rules:** `create_workspace_with_owner` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PD.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new workspace: `trial_ends_at == NOW + timedelta(days=14)`.
3. re-read the new workspace: `subscription_status == "trial"`, `current_members_count == 1`.
4. re-read the new workspace: `subscription_started_at is None`, `subscription_ends_at is None`, `billing_cycle is None`.
5. re-read the new workspace: `stripe_customer_id is None`, `stripe_subscription_id is None`.
6. re-read the new workspace: `billing_email is None`.
7. re-read the new workspace: `current_storage_mb == 0`, `current_orders_this_month == 0`, `current_factories_count == 0`, `current_machines_count == 0`, `current_projects_count == 0`.
8. re-read the new workspace: `last_usage_reset_at is not None` (model clock, not the patched NOW).

### WSMG-CW-03 — plan id 0 means the default plan
- **Rules:** `create_workspace_with_owner` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PX.
2. PD.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id, subscription_plan_id=0)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new workspace: `subscription_plan_id == PD.id`.
3. audit: audit(the new workspace) has exactly 1 row.
4. audit: that row: `metadata_json == {"plan": f"free-{TAG}"}`.

### WSMG-CW-04 — plan id None explicitly means the default plan, not another active plan
- **Rules:** `create_workspace_with_owner` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PD.
2. PX.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id, subscription_plan_id=None)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new workspace: `subscription_plan_id == PD.id`.

### WSMG-CW-05 — an inactive default plan is passed over for the active default
- **Rules:** `create_workspace_with_owner` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Q = `make_subscription_plan(db, name=f"retired-{TAG}", is_default=True, is_active=False, max_members=3)`.
2. PD.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new workspace: `subscription_plan_id == PD.id`.

### WSMG-CW-06 — no active default plan is refused and nothing is written
- **Rules:** `create_workspace_with_owner` R3; Errors row 2; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. Q = `make_subscription_plan(db, name=f"retired-{TAG}", is_default=True, is_active=False, max_members=3)`.
2. PX.

**When**
- `M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "No default subscription plan found"`.
3. nothing written.
4. nothing seeded.

### WSMG-CW-07 — an unknown plan id is refused and nothing is written
- **Rules:** `create_workspace_with_owner` R2; Errors row 1; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. PD.

**When**
- `M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id, subscription_plan_id=MISSING)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invalid subscription plan"`.
3. nothing written.
4. nothing seeded.

### WSMG-CW-08 — an inactive plan id is refused and nothing is written
- **Rules:** `create_workspace_with_owner` R2; Errors row 1; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. PD.
2. PI.

**When**
- `M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id, subscription_plan_id=PI.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invalid subscription plan"`.
3. nothing written.
4. nothing seeded.

### WSMG-CW-09 — a bad plan id with a taken slug gives the plan error
- **Rules:** `create_workspace_with_owner` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. PD.
2. X = `make_workspace(db, slug=SL)`.

**When**
- `M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id, subscription_plan_id=MISSING)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invalid subscription plan"`.
3. nothing written.

### WSMG-CW-10 — a slug taken by another owner's workspace is refused and nothing is written
- **Rules:** `create_workspace_with_owner` R5; Errors row 3; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. PD.
2. X = `make_workspace(db, slug=SL, owner_user_id=UB.id)`.

**When**
- `M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == f"Workspace slug '{SL}' is already taken. Please choose a different name."`.
3. unchanged: unchanged(X).
4. nothing written.
5. nothing seeded.

### WSMG-CW-11 — a longer slug that starts with the new one does not block it
- **Rules:** `create_workspace_with_owner` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PD.
2. X = `make_workspace(db, slug=f"acme-{TAG}-tools")`.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new workspace: `slug == SL`.

### WSMG-CW-12 — two creations racing past the slug check: the unique index refuses the second
- **Rules:** `create_workspace_with_owner` R5 (race)
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. PD.
2. X = `make_workspace(db, slug=SL)`.
3. `monkeypatch.setattr(M.workspace_dao, "get_by_slug", lambda *a, **k: None)` (Race simulations).

**When**
- `M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id)`, inside the wrap of `raises: IntegrityError on flush`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `workspaces` with `slug == SL` has exactly 1 row.
4. unchanged: unchanged(X).

### WSMG-CW-13 — a shorter slug that the new one starts with does not block it
- **Rules:** `create_workspace_with_owner` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PD.
2. X = `make_workspace(db, slug=SL)`.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=f"acme-{TAG}-tools"), owner_user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new workspace: `slug == f"acme-{TAG}-tools"`.

### WSMG-CW-14 — plan id and owner position inside workspace_data are ignored
- **Rules:** `create_workspace_with_owner` Inputs (`workspace_data`), R3, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PD.
2. PX.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL, subscription_plan_id=PX.id, owner_position="CEO"), owner_user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new workspace: `subscription_plan_id == PD.id`.
3. re-read the one row of members(the new workspace, UA): `position is None`.

### WSMG-CW-15 — the owner's timezone is copied into settings
- **Rules:** `create_workspace_with_owner` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PD.
2. Z = `make_profile(db, email=f"zed.{TAG}@acme.com", name="Zed", timezone="Asia/Dhaka")`.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=Z.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new workspace: `settings == {"timezone": "Asia/Dhaka"}`.

### WSMG-CW-16 — an owner without a timezone gives empty settings
- **Rules:** `create_workspace_with_owner` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PD.
2. Z = `make_profile(db, email=f"zed.{TAG}@acme.com", name="Zed", timezone=None)`.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=Z.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new workspace: `settings == {}`.

### WSMG-CW-17 — an owner with an empty-text timezone gives empty settings
- **Rules:** `create_workspace_with_owner` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PD.
2. Z = `make_profile(db, email=f"zed.{TAG}@acme.com", name="Zed", timezone="")`.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=Z.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new workspace: `settings == {}`.

### WSMG-CW-18 — the owner becomes the first, active member with the given position
- **Rules:** `create_workspace_with_owner` R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PD.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id, owner_position="Plant Head")`.

**Then**
1. returns: `result.id is not None`.
2. count: `workspace_members` with `workspace_id == result.id` has exactly 1 row.
3. re-read that row: `user_id == UA.id`, `role == "owner"`, `status == "active"`, `position == "Plant Head"`.
4. re-read that row: `joined_at == NOW`, `left_at is None`, `invited_by_user_id is None`, `invited_at is not None`.

### WSMG-CW-19 — no seat check is made for the owner
- **Rules:** `create_workspace_with_owner` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `PD = make_subscription_plan(db, name=f"free-{TAG}", is_default=True, is_active=True, max_members=-1)`.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `workspace_members` with `workspace_id == result.id` and `status == "active"` has exactly 1 row.

### WSMG-CW-20 — the new workspace gets its 13 statuses
- **Rules:** `create_workspace_with_owner` R9
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PD.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `statuses` with `workspace_id == result.id` has exactly 13 rows.
3. re-read those rows: `sorted(s.name for s in rows) == sorted(["Pending", "Office Approved", "Budget Approved", "Quotation Requested", "Quotation Received", "Purchased", "Received", "Completed", "Cancelled", "Draft", "Planning", "Receiving", "Complete"])`.

### WSMG-CW-21 — the new workspace gets its purchase order workflow
- **Rules:** `create_workspace_with_owner` R9
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PD.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `order_workflows` with `workspace_id == result.id` has exactly 1 row.
3. re-read that row: `name == "Purchase Order"`, `type == "purchase"`, `description == "Draft → Planning → Receiving → Complete"`, `allowed_reverts_json is None`.
4. re-read that row: `status_sequence == [d.id, p.id, r.id, c.id]`, where d, p, r, c are the `statuses` rows of `result.id` named `"Draft"`, `"Planning"`, `"Receiving"`, `"Complete"`.

### WSMG-CW-22 — the new workspace gets its 5 departments
- **Rules:** `create_workspace_with_owner` R9
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PD.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `departments` with `workspace_id == result.id` has exactly 5 rows.
3. re-read those rows: `sorted(d.name for d in rows) == ["Administration", "Maintenance", "Production", "Quality Control", "Warehouse"]`.

### WSMG-CW-23 — the new workspace gets its 6 system item tags
- **Rules:** `create_workspace_with_owner` R9
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PD.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `item_tags` with `workspace_id == result.id` has exactly 6 rows.
3. re-read those rows: `sorted(t.tag_code for t in rows) == ["consumable", "finished_good", "machine_part", "project_item", "raw_material", "tool"]`.
4. re-read those rows: `all(t.is_system_tag is True and t.is_active is True and t.usage_count == 0 for t in rows)`.
5. re-read those rows: `all(t.created_by == UA.id for t in rows)`.

### WSMG-CW-24 — the new workspace gets its 5 system account tags
- **Rules:** `create_workspace_with_owner` R9
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PD.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `account_tags` with `workspace_id == result.id` has exactly 5 rows.
3. re-read those rows: `sorted(t.tag_code for t in rows) == ["client", "payroll", "supplier", "utility", "vendor"]`.
4. re-read those rows: `all(t.is_system_tag is True and t.is_active is True and t.usage_count == 0 for t in rows)`.
5. re-read those rows: `all(t.created_by == UA.id for t in rows)`.

### WSMG-CW-25 — default data of an earlier workspace neither blocks the seed nor changes
- **Rules:** `create_workspace_with_owner` R9
- **Kind:** isolation
- **Expect:** pass

**Given**
1. PD.
2. `S0 = Status(workspace_id=W0.id, name="Draft", comment="old")`.
3. `D0 = Department(workspace_id=W0.id, name="Production")`.
4. `I0 = ItemTag(workspace_id=W0.id, name="Raw", tag_code="raw_material", is_system_tag=True, is_active=True, usage_count=4)`.
5. `A0 = AccountTag(workspace_id=W0.id, name="Supplier", tag_code="supplier", is_system_tag=True, is_active=True, usage_count=2)`.
6. `O0 = OrderWorkflow(workspace_id=W0.id, name="Purchase Order", type="purchase", status_sequence=[S0.id])`.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `statuses` with `workspace_id == result.id` has exactly 13 rows.
3. count: `departments` with `workspace_id == result.id` has exactly 5 rows.
4. count: `item_tags` with `workspace_id == result.id` has exactly 6 rows.
5. count: `account_tags` with `workspace_id == result.id` has exactly 5 rows.
6. count: `order_workflows` with `workspace_id == result.id` has exactly 1 row.
7. unchanged: unchanged(S0).
8. unchanged: unchanged(I0).
9. unchanged: unchanged(O0).
10. count: `statuses` with `workspace_id == W0.id` has exactly 1 row.

### WSMG-CW-26 — default data of a workspace with a higher id neither blocks the seed nor changes
- **Rules:** `create_workspace_with_owner` R9
- **Kind:** isolation
- **Expect:** pass

**Given**
1. PD.
2. WH = `make_workspace(db, id=990000000 + int(TAG, 16) % 9000000)` (an explicit id above any the sequence gives the new workspace; TAG keeps parallel runs apart).
3. `SH = Status(workspace_id=WH.id, name="Draft", comment="old")`.
4. `DH = Department(workspace_id=WH.id, name="Production")`.
5. `IH = ItemTag(workspace_id=WH.id, name="Raw", tag_code="raw_material", is_system_tag=True, is_active=True, usage_count=4)`.
6. `AH = AccountTag(workspace_id=WH.id, name="Supplier", tag_code="supplier", is_system_tag=True, is_active=True, usage_count=2)`.
7. `OH = OrderWorkflow(workspace_id=WH.id, name="Purchase Order", type="purchase", status_sequence=[SH.id])`.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id)`.

**Then**
1. returns: `result.id < WH.id`.
2. count: `statuses` with `workspace_id == result.id` has exactly 13 rows.
3. count: `departments` with `workspace_id == result.id` has exactly 5 rows.
4. count: `item_tags` with `workspace_id == result.id` has exactly 6 rows.
5. count: `account_tags` with `workspace_id == result.id` has exactly 5 rows.
6. count: `order_workflows` with `workspace_id == result.id` has exactly 1 row.
7. unchanged: unchanged(AH).
8. unchanged: unchanged(OH).
9. count: `departments` with `workspace_id == WH.id` has exactly 1 row.

### WSMG-CW-27 — one workspace_created audit row names the plan
- **Rules:** `create_workspace_with_owner` R10; A1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PD.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. audit: audit(the new workspace) has exactly 1 row.
3. audit: that row: `user_id == UA.id`, `action == "workspace_created"`, `metadata_json == {"plan": f"free-{TAG}"}`.
4. audit: that row: `resource_type is None`, `resource_id is None`, `ip_address is None`, `user_agent is None`.

### WSMG-CW-28 — an unknown owner fails at the member insert; the savepoint removes the workspace
- **Rules:** `create_workspace_with_owner` R11; Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. PD.

**When**
- `M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=MISSING)`, inside the wrap of `raises: IntegrityError on flush`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. count: `workspaces` with `slug == SL` has exactly 0 rows.
4. nothing written.

### WSMG-CW-29 — surrounding spaces are trimmed from the name, inner spaces kept
- **Rules:** `create_workspace_with_owner` R12 [BUG-1980]
- **Kind:** bug
- **Expect:** xfail BUG-1980
- **Fails today on:** Then 2 (the name is stored with its spaces)

**Given**
1. PD.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name=" Acme  Tools ", slug=SL), owner_user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new workspace: `name == "Acme  Tools"`.

### WSMG-CW-30 — a whitespace-only name is refused by the schema
- **Rules:** `create_workspace_with_owner` R12 [BUG-1980]
- **Kind:** bug
- **Expect:** xfail BUG-1980
- **Fails today on:** Then 1 (no error is raised: `"   "` passes `min_length=1`)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `WorkspaceCreate(name="   ", slug=SL)` (target `schema`).

**Then**
1. raises: `ValidationError`.

### WSMG-CW-31 — inner spaces and capitals are kept as typed
- **Rules:** `create_workspace_with_owner` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PD.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme  TOOLS", slug=SL), owner_user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new workspace: `name == "Acme  TOOLS"`.

### WSMG-CW-32 — an empty name is refused by the schema
- **Rules:** `create_workspace_with_owner` R12
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- build `WorkspaceCreate(name="", slug=SL)` (target `schema`).

**Then**
1. raises: `ValidationError`.

### WSMG-CW-33 — create flushes and never commits
- **Rules:** `create_workspace_with_owner` Returns; Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PD.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id)`, rolled back.

**Then**
1. returns: `result.id is not None` (inside).
2. count: `workspaces` with `slug == SL` has exactly 1 row (inside).
3. mock called: `cm.call_count == 0`.
4. count: `workspaces` with `slug == SL` has exactly 0 rows (after the savepoint rollback).

### WSMG-CW-34 — the audit row carries the request's IP address and user agent
- **Rules:** A2 [BUG-1404]; `create_workspace_with_owner` R10
- **Kind:** bug
- **Expect:** xfail BUG-1404
- **Fails today on:** Then 1 (the call raises TypeError: no `ip_address` parameter)

**Given**
1. PD.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id, ip_address="203.0.113.7", user_agent="Mozilla/5.0 Test")`.

**Then**
1. returns: `result.id is not None`.
2. audit: audit(the new workspace) has exactly 1 row.
3. audit: that row: `ip_address == "203.0.113.7"`, `user_agent == "Mozilla/5.0 Test"`.

## `WorkspaceManager.add_member_to_workspace`

> Seat cards use positive limits only. `max_members = 0` (pending, BUG-1989) lives only in section P17.

### WSMG-AM-01 — the user becomes an active member with the given role and position
- **Rules:** `add_member_to_workspace` R7, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. UA has no row in any workspace (standing rows only).

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id, position="Welder")`.

**Then**
1. returns: `isinstance(result, WorkspaceMember)`.
2. returns: `result.id is not None`.
3. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `role == "member"`, `position == "Welder"`, `status == "active"`.
4. re-read the returned row: `joined_at == NOW`, `left_at is None`, `invited_at is not None`.
5. count: `workspace_members` with `workspace_id == W1.id` and `status == "active"` has exactly 2 rows.

### WSMG-AM-02 — the role `manager` is accepted
- **Rules:** `add_member_to_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="manager", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `role == "manager"`, `status == "active"`.
3. count: members(W1, UA) has exactly 1 row.

### WSMG-AM-03 — the role `viewer` is accepted
- **Rules:** `add_member_to_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="viewer", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `role == "viewer"`, `status == "active"`.
3. count: members(W1, UA) has exactly 1 row.

### WSMG-AM-04 — the role `ground-team` is accepted
- **Rules:** `add_member_to_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="ground-team", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `role == "ground-team"`, `status == "active"`.
3. count: members(W1, UA) has exactly 1 row.

### WSMG-AM-05 — the role `owner` is accepted
- **Rules:** `add_member_to_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="owner", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `role == "owner"`, `status == "active"`.
3. count: members(W1, UA) has exactly 1 row.

### WSMG-AM-06 — `ground-team-manager` is refused and nothing is written
- **Rules:** `add_member_to_workspace` R1; Errors row 1; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="ground-team-manager", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invalid role. Must be one of: ground-team, manager, member, owner, viewer"`.
3. nothing written.

### WSMG-AM-07 — `finance` is refused and nothing is written
- **Rules:** `add_member_to_workspace` R1; Errors row 1; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="finance", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invalid role. Must be one of: ground-team, manager, member, owner, viewer"`.
3. nothing written.

### WSMG-AM-08 — `Owner` in capitals is refused and nothing is written
- **Rules:** `add_member_to_workspace` R1; Errors row 1; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="Owner", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invalid role. Must be one of: ground-team, manager, member, owner, viewer"`.
3. nothing written.

### WSMG-AM-09 — an empty role is refused and nothing is written
- **Rules:** `add_member_to_workspace` R1; Errors row 1; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invalid role. Must be one of: ground-team, manager, member, owner, viewer"`.
3. nothing written.

### WSMG-AM-10 — the role is checked before the workspace is looked up
- **Rules:** `add_member_to_workspace` R1, R3
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.add_member_to_workspace(db, workspace_id=MISSING, user_id=UA.id, role="finance", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invalid role. Must be one of: ground-team, manager, member, owner, viewer"`.
3. nothing written.

### WSMG-AM-11 — the role is checked before the existing row
- **Rules:** `add_member_to_workspace` R1, R2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = member(UA).

**When**
- `M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="finance", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invalid role. Must be one of: ground-team, manager, member, owner, viewer"`.
3. unchanged: unchanged(A).
4. nothing written.

### WSMG-AM-12 — a row with status `"active"` is refused as already a member
- **Rules:** `add_member_to_workspace` R2; Errors row 2; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = member(UA).

**When**
- `M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="manager", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "User is already a member of this workspace"`.
3. unchanged: unchanged(A).
4. nothing written.

### WSMG-AM-13 — a row with status `"suspended"` is refused as already a member
- **Rules:** `add_member_to_workspace` R2; Errors row 2; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = member(UA), but `status "suspended"`.

**When**
- `M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="manager", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "User is already a member of this workspace"`.
3. unchanged: unchanged(A).
4. nothing written.

### WSMG-AM-14 — a row with status `"Inactive"` is refused as already a member
- **Rules:** `add_member_to_workspace` R2; Errors row 2; A3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member(UA), but `status "Inactive"`.

**When**
- `M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="manager", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "User is already a member of this workspace"`.
3. unchanged: unchanged(A).
4. nothing written.

### WSMG-AM-15 — a row with status `" inactive"` is refused as already a member
- **Rules:** `add_member_to_workspace` R2; Errors row 2; A3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member(UA), but `status " inactive"`.

**When**
- `M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="manager", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "User is already a member of this workspace"`.
3. unchanged: unchanged(A).
4. nothing written.

### WSMG-AM-16 — the user's active row in an earlier workspace does not count
- **Rules:** `add_member_to_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = member(UA), but `workspace_id W0.id`.

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `role == "member"`, `status == "active"`.
3. count: members(W1, UA) has exactly 1 row.
4. unchanged: unchanged(Z).

### WSMG-AM-17 — the user's active row in a later workspace does not count
- **Rules:** `add_member_to_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = member(UA), but `workspace_id W2.id`.

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `role == "member"`, `status == "active"`.
3. count: members(W1, UA) has exactly 1 row.
4. unchanged: unchanged(Z).

### WSMG-AM-18 — rows of other users, one with a lower and one with a higher user id, do not count
- **Rules:** `add_member_to_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = member(UA).
2. C = member(UC).

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UB.id, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `user_id == UB.id`, `status == "active"`.
3. count: members(W1, UB) has exactly 1 row.

### WSMG-AM-19 — a removed (inactive) member is reactivated with the new role and position
- **Rules:** `add_member_to_workspace` R2a [BUG-1982]
- **Kind:** bug
- **Expect:** xfail BUG-1982
- **Fails today on:** Then 1 (the call raises ValueError "User is already a member of this workspace")

**Given**
1. A = member(UA), but `role "viewer"`, `position "Old"`, `status "inactive"`, `joined_at T1`, `left_at T2`.

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="manager", inviter_id=UO.id, position="Lead")`.

**Then**
1. returns: `result.id == A.id`.
2. re-read A: `status == "active"`, `role == "manager"`, `position == "Lead"`.
3. re-read A: `joined_at == NOW`, `left_at is None`.
4. count: members(W1, UA) has exactly 1 row.
5. audit: audit(W1, "member_added") has exactly 1 row.

### WSMG-AM-20 — reactivating a removed member is refused when the seats are full
- **Rules:** `add_member_to_workspace` R2a [BUG-1982], R5
- **Kind:** bug
- **Expect:** xfail BUG-1982
- **Fails today on:** Then 2 (today the message is "User is already a member of this workspace")

**Given**
1. limit 2
2. B = member(UB).
3. A = member(UA), but `status "inactive"`, `left_at T2`.

**When**
- `M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Workspace has reached maximum member limit (2). Upgrade subscription to add more members."`.
3. unchanged: unchanged(A).
4. nothing written.

### WSMG-AM-21 — a removed member's own inactive row does not take a seat when they come back
- **Rules:** `add_member_to_workspace` R2a [BUG-1982], R5
- **Kind:** bug
- **Expect:** xfail BUG-1982
- **Fails today on:** Then 1 (the call raises ValueError "User is already a member of this workspace")

**Given**
1. limit 3
2. B = member(UB).
3. A = member(UA), but `status "inactive"`, `left_at T2`.

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `result.id == A.id`.
2. re-read A: `status == "active"`.
3. count: `workspace_members` with `workspace_id == W1.id` and `status == "active"` has exactly 3 rows.

### WSMG-AM-22 — an unknown workspace is refused and nothing is written
- **Rules:** `add_member_to_workspace` R3; Errors row 3; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.add_member_to_workspace(db, workspace_id=MISSING, user_id=UA.id, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Workspace not found"`.
3. nothing written.

### WSMG-AM-23 — an inactive plan's limit is still enforced
- **Rules:** `add_member_to_workspace` R4, R5
- **Kind:** error
- **Expect:** pass

**Given**
1. limit 2
2. `PL1.is_active = False; db.flush()`
3. B = member(UB).

**When**
- `M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Workspace has reached maximum member limit (2). Upgrade subscription to add more members."`.
3. nothing written.

### WSMG-AM-24 — at the limit (3 active, owner included) the add is refused
- **Rules:** `add_member_to_workspace` R5; Errors row 4; A3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 3
2. B = member(UB).
3. C = member(UC).

**When**
- `M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Workspace has reached maximum member limit (3). Upgrade subscription to add more members."`.
3. count: members(W1, UA) has exactly 0 rows.
4. nothing written.

### WSMG-AM-25 — one seat below the limit the add succeeds
- **Rules:** `add_member_to_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 3
2. B = member(UB).

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `role == "member"`, `status == "active"`.
3. count: members(W1, UA) has exactly 1 row.
4. count: `workspace_members` with `workspace_id == W1.id` and `status == "active"` has exactly 3 rows.

### WSMG-AM-26 — above the limit (3 active on a limit of 2) the add is refused
- **Rules:** `add_member_to_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 2
2. B = member(UB).
3. C = member(UC).

**When**
- `M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Workspace has reached maximum member limit (2). Upgrade subscription to add more members."`.
3. nothing written.

### WSMG-AM-27 — the owner alone fills a limit of 1
- **Rules:** `add_member_to_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 1

**When**
- `M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Workspace has reached maximum member limit (1). Upgrade subscription to add more members."`.
3. nothing written.

### WSMG-AM-28 — pending invitations do not take a seat when adding
- **Rules:** `add_member_to_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 3
2. B = member(UB).
3. J = invitation J to ED.
4. K = invitation K to EE.

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `role == "member"`, `status == "active"`.
3. count: members(W1, UA) has exactly 1 row.

### WSMG-AM-29 — a suspended member does not take a seat
- **Rules:** `add_member_to_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 3
2. B = member(UB).
3. C = member(UC), but `status "suspended"`.

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `role == "member"`, `status == "active"`.
3. count: members(W1, UA) has exactly 1 row.

### WSMG-AM-30 — a removed (inactive) member does not take a seat
- **Rules:** `add_member_to_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 3
2. B = member(UB).
3. C = member(UC), but `status "inactive"`, `left_at T2`.

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `role == "member"`, `status == "active"`.
3. count: members(W1, UA) has exactly 1 row.

### WSMG-AM-31 — active members of an earlier workspace do not take W1's seats
- **Rules:** `add_member_to_workspace` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. limit 2
2. Z1 = member(UB), but `workspace_id W0.id`.
3. Z2 = member(UC), but `workspace_id W0.id`.
4. Z3 = member(UA), but `workspace_id W0.id`.

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `role == "member"`, `status == "active"`.
3. count: members(W1, UA) has exactly 1 row.

### WSMG-AM-32 — active members of a later workspace do not take W1's seats
- **Rules:** `add_member_to_workspace` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. limit 2
2. Z1 = member(UB), but `workspace_id W2.id`.
3. Z2 = member(UC), but `workspace_id W2.id`.
4. Z3 = member(UA), but `workspace_id W2.id`.

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `role == "member"`, `status == "active"`.
3. count: members(W1, UA) has exactly 1 row.

### WSMG-AM-33 — a limit of -1 means no limit
- **Rules:** `add_member_to_workspace` R5a [BUG-1872]
- **Kind:** bug
- **Expect:** xfail BUG-1872
- **Fails today on:** Then 1 (the call raises ValueError "…limit (-1)…")

**Given**
1. limit -1
2. B = member(UB).
3. C = member(UC).

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `role == "member"`, `status == "active"`.
3. count: members(W1, UA) has exactly 1 row.

### WSMG-AM-34 — a limit of -5 means no limit
- **Rules:** `add_member_to_workspace` R5a [BUG-1872]
- **Kind:** bug
- **Expect:** xfail BUG-1872
- **Fails today on:** Then 1 (the call raises ValueError "…limit (-5)…")

**Given**
1. limit -5
2. B = member(UB).

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `role == "member"`, `status == "active"`.
3. count: members(W1, UA) has exactly 1 row.

### WSMG-AM-35 — the new row records who invited the member
- **Rules:** `add_member_to_workspace` R8 [BUG-1985]
- **Kind:** bug
- **Expect:** xfail BUG-1985
- **Fails today on:** Then 2 (`invited_by_user_id` is NULL today)

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `invited_by_user_id == UO.id`.

### WSMG-AM-36 — with no inviter the row and the audit row carry no actor
- **Rules:** `add_member_to_workspace` R8, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=None)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `invited_by_user_id is None`.
3. audit: audit(W1) has exactly 1 row.
4. audit: that row: `user_id is None`, `action == "member_added"`.

### WSMG-AM-37 — one member_added audit row names the new member and role
- **Rules:** `add_member_to_workspace` R9; A1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="viewer", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. audit: audit(W1) has exactly 1 row.
3. audit: that row: `user_id == UO.id`, `action == "member_added"`, `metadata_json == {"new_member_id": UA.id, "role": "viewer"}`.
4. audit: that row: `resource_type is None`, `resource_id is None`, `ip_address is None`, `user_agent is None`.
5. audit: audit(W0) has exactly 0 rows.

### WSMG-AM-38 — an unknown user fails the insert with IntegrityError
- **Rules:** `add_member_to_workspace` R10
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.add_member_to_workspace(db, workspace_id=W1.id, user_id=MISSING, role="member", inviter_id=UO.id)`, inside the wrap of `raises: IntegrityError on flush`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. count: `workspace_members` with `workspace_id == W1.id` has exactly 1 row.

### WSMG-AM-39 — add flushes and never commits
- **Rules:** `add_member_to_workspace` Returns; Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id)`. Rolled back.

**Then**
1. returns: `result.id is not None` (inside).
2. count: members(W1, UA) has exactly 1 row (inside).
3. mock called: `cm.call_count == 0`.
4. count: members(W1, UA) has exactly 0 rows (after the savepoint rollback).

### WSMG-AM-40 — the audit row carries the request's IP address and user agent
- **Rules:** A2 [BUG-1404]; `add_member_to_workspace` R9
- **Kind:** bug
- **Expect:** xfail BUG-1404
- **Fails today on:** Then 1 (the call raises TypeError: no `ip_address` parameter)

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id, ip_address="203.0.113.7", user_agent="Mozilla/5.0 Test")`.

**Then**
1. returns: `result.id is not None`.
2. audit: audit(W1) has exactly 1 row.
3. audit: that row: `ip_address == "203.0.113.7"`, `user_agent == "Mozilla/5.0 Test"`.
## `WorkspaceManager.remove_member_from_workspace`

> One card per role pair: remover role × target role (RM-01 … RM-47), then the owner as target, the membership checks, grants held in another workspace, and the clean-up rules. The remover's own row carries the role passed in; the manager reads only `remover_role`.

### WSMG-RM-01 — the owner removes a target of role `manager`
- **Rules:** `remove_member_from_workspace` R5a, R6, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = member(UA), but `role "manager"`.

**When**
- `result = M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. re-read T: `status == "inactive"`, `left_at == NOW`.
2. re-read T: `role == "manager"`, `workspace_id == W1.id`, `user_id == UA.id`.
3. count: members(W1, UA) has exactly 1 row.
4. audit: audit(W1) has exactly 1 row.
5. audit: that row: `user_id == UO.id`, `action == "member_removed"`, `metadata_json == {"removed_member_id": UA.id}`.
6. returns: `result is None`.

### WSMG-RM-02 — the owner removes a target of role `member`
- **Rules:** `remove_member_from_workspace` R5a, R6, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = member(UA), but `role "member"`.

**When**
- `result = M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. re-read T: `status == "inactive"`, `left_at == NOW`.
2. re-read T: `role == "member"`, `workspace_id == W1.id`, `user_id == UA.id`.
3. count: members(W1, UA) has exactly 1 row.
4. audit: audit(W1) has exactly 1 row.
5. audit: that row: `user_id == UO.id`, `action == "member_removed"`, `metadata_json == {"removed_member_id": UA.id}`.
6. returns: `result is None`.

### WSMG-RM-03 — the owner removes a target of role `viewer`
- **Rules:** `remove_member_from_workspace` R5a, R6, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = member(UA), but `role "viewer"`.

**When**
- `result = M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. re-read T: `status == "inactive"`, `left_at == NOW`.
2. re-read T: `role == "viewer"`, `workspace_id == W1.id`, `user_id == UA.id`.
3. count: members(W1, UA) has exactly 1 row.
4. audit: audit(W1) has exactly 1 row.
5. audit: that row: `user_id == UO.id`, `action == "member_removed"`, `metadata_json == {"removed_member_id": UA.id}`.
6. returns: `result is None`.

### WSMG-RM-04 — the owner removes a target of role `ground-team`
- **Rules:** `remove_member_from_workspace` R5a, R6, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = member(UA), but `role "ground-team"`.

**When**
- `result = M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. re-read T: `status == "inactive"`, `left_at == NOW`.
2. re-read T: `role == "ground-team"`, `workspace_id == W1.id`, `user_id == UA.id`.
3. count: members(W1, UA) has exactly 1 row.
4. audit: audit(W1) has exactly 1 row.
5. audit: that row: `user_id == UO.id`, `action == "member_removed"`, `metadata_json == {"removed_member_id": UA.id}`.
6. returns: `result is None`.

### WSMG-RM-05 — the owner removes a target of role `ground-team-manager`
- **Rules:** `remove_member_from_workspace` R5a, R6, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = member(UA), but `role "ground-team-manager"`.

**When**
- `result = M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. re-read T: `status == "inactive"`, `left_at == NOW`.
2. re-read T: `role == "ground-team-manager"`, `workspace_id == W1.id`, `user_id == UA.id`.
3. count: members(W1, UA) has exactly 1 row.
4. audit: audit(W1) has exactly 1 row.
5. audit: that row: `user_id == UO.id`, `action == "member_removed"`, `metadata_json == {"removed_member_id": UA.id}`.
6. returns: `result is None`.

### WSMG-RM-06 — the owner removes a target of role `finance`
- **Rules:** `remove_member_from_workspace` R5a, R6, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = member(UA), but `role "finance"`.

**When**
- `result = M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. re-read T: `status == "inactive"`, `left_at == NOW`.
2. re-read T: `role == "finance"`, `workspace_id == W1.id`, `user_id == UA.id`.
3. count: members(W1, UA) has exactly 1 row.
4. audit: audit(W1) has exactly 1 row.
5. audit: that row: `user_id == UO.id`, `action == "member_removed"`, `metadata_json == {"removed_member_id": UA.id}`.
6. returns: `result is None`.

### WSMG-RM-07 — a `ground-team-manager` removes a target of role `ground-team`
- **Rules:** `remove_member_from_workspace` R4, R6, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = member(UA), but `role "ground-team"`.
2. R = member(UB), but `role "ground-team-manager"`.

**When**
- `result = M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="ground-team-manager")`.

**Then**
1. re-read T: `status == "inactive"`, `left_at == NOW`.
2. re-read T: `role == "ground-team"`, `workspace_id == W1.id`, `user_id == UA.id`.
3. count: members(W1, UA) has exactly 1 row.
4. audit: audit(W1) has exactly 1 row.
5. audit: that row: `user_id == UB.id`, `action == "member_removed"`, `metadata_json == {"removed_member_id": UA.id}`.
6. returns: `result is None`.

### WSMG-RM-08 — a `ground-team-manager` may not remove a target of role `manager`
- **Rules:** `remove_member_from_workspace` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. T = member(UA), but `role "manager"`.
2. R = member(UB), but `role "ground-team-manager"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="ground-team-manager")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Managers can only remove ground-team members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-09 — a `ground-team-manager` may not remove a target of role `member`
- **Rules:** `remove_member_from_workspace` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. T = member(UA), but `role "member"`.
2. R = member(UB), but `role "ground-team-manager"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="ground-team-manager")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Managers can only remove ground-team members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-10 — a `ground-team-manager` may not remove a target of role `viewer`
- **Rules:** `remove_member_from_workspace` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. T = member(UA), but `role "viewer"`.
2. R = member(UB), but `role "ground-team-manager"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="ground-team-manager")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Managers can only remove ground-team members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-11 — a `ground-team-manager` may not remove a target of role `ground-team-manager`
- **Rules:** `remove_member_from_workspace` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. T = member(UA), but `role "ground-team-manager"`.
2. R = member(UB), but `role "ground-team-manager"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="ground-team-manager")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Managers can only remove ground-team members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-12 — a `ground-team-manager` may not remove a target of role `finance`
- **Rules:** `remove_member_from_workspace` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. T = member(UA), but `role "finance"`.
2. R = member(UB), but `role "ground-team-manager"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="ground-team-manager")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Managers can only remove ground-team members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-13 — a `manager` removes a target of role `ground-team`
- **Rules:** `remove_member_from_workspace` R4a, R6, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = member(UA), but `role "ground-team"`.
2. R = member(UB), but `role "manager"`.

**When**
- `result = M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="manager")`.

**Then**
1. re-read T: `status == "inactive"`, `left_at == NOW`.
2. re-read T: `role == "ground-team"`, `workspace_id == W1.id`, `user_id == UA.id`.
3. count: members(W1, UA) has exactly 1 row.
4. audit: audit(W1) has exactly 1 row.
5. audit: that row: `user_id == UB.id`, `action == "member_removed"`, `metadata_json == {"removed_member_id": UA.id}`.
6. returns: `result is None`.

### WSMG-RM-14 — a `manager` may not remove a target of role `manager`
- **Rules:** `remove_member_from_workspace` R4b [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a manager may remove any non-owner member)

**Given**
1. T = member(UA), but `role "manager"`.
2. R = member(UB), but `role "manager"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="manager")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Managers can only remove ground-team members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-15 — a `manager` may not remove a target of role `member`
- **Rules:** `remove_member_from_workspace` R4b [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a manager may remove any non-owner member)

**Given**
1. T = member(UA), but `role "member"`.
2. R = member(UB), but `role "manager"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="manager")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Managers can only remove ground-team members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-16 — a `manager` may not remove a target of role `viewer`
- **Rules:** `remove_member_from_workspace` R4b [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a manager may remove any non-owner member)

**Given**
1. T = member(UA), but `role "viewer"`.
2. R = member(UB), but `role "manager"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="manager")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Managers can only remove ground-team members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-17 — a `manager` may not remove a target of role `ground-team-manager`
- **Rules:** `remove_member_from_workspace` R4b [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a manager may remove any non-owner member)

**Given**
1. T = member(UA), but `role "ground-team-manager"`.
2. R = member(UB), but `role "manager"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="manager")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Managers can only remove ground-team members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-18 — a `manager` may not remove a target of role `finance`
- **Rules:** `remove_member_from_workspace` R4b [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a manager may remove any non-owner member)

**Given**
1. T = member(UA), but `role "finance"`.
2. R = member(UB), but `role "manager"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="manager")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Managers can only remove ground-team members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-19 — a `ground-team` remover may not remove a target of role `manager`
- **Rules:** `remove_member_from_workspace` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = member(UA), but `role "manager"`.
2. R = member(UB), but `role "ground-team"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="ground-team")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-20 — a `ground-team` remover may not remove a target of role `member`
- **Rules:** `remove_member_from_workspace` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = member(UA), but `role "member"`.
2. R = member(UB), but `role "ground-team"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="ground-team")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-21 — a `ground-team` remover may not remove a target of role `viewer`
- **Rules:** `remove_member_from_workspace` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = member(UA), but `role "viewer"`.
2. R = member(UB), but `role "ground-team"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="ground-team")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-22 — a `ground-team` remover may not remove a target of role `ground-team`
- **Rules:** `remove_member_from_workspace` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = member(UA), but `role "ground-team"`.
2. R = member(UB), but `role "ground-team"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="ground-team")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-23 — a `ground-team` remover may not remove a target of role `ground-team-manager`
- **Rules:** `remove_member_from_workspace` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = member(UA), but `role "ground-team-manager"`.
2. R = member(UB), but `role "ground-team"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="ground-team")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-24 — a `ground-team` remover may not remove a target of role `finance`
- **Rules:** `remove_member_from_workspace` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = member(UA), but `role "finance"`.
2. R = member(UB), but `role "ground-team"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="ground-team")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-25 — a `member` remover may not remove a target of role `manager`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a member may remove any non-owner member)

**Given**
1. T = member(UA), but `role "manager"`.
2. R = member(UB), but `role "member"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="member")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-26 — a `member` remover may not remove a target of role `member`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a member may remove any non-owner member)

**Given**
1. T = member(UA), but `role "member"`.
2. R = member(UB), but `role "member"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="member")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-27 — a `member` remover may not remove a target of role `viewer`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a member may remove any non-owner member)

**Given**
1. T = member(UA), but `role "viewer"`.
2. R = member(UB), but `role "member"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="member")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-28 — a `member` remover may not remove a target of role `ground-team`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a member may remove any non-owner member)

**Given**
1. T = member(UA), but `role "ground-team"`.
2. R = member(UB), but `role "member"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="member")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-29 — a `member` remover may not remove a target of role `ground-team-manager`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a member may remove any non-owner member)

**Given**
1. T = member(UA), but `role "ground-team-manager"`.
2. R = member(UB), but `role "member"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="member")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-30 — a `member` remover may not remove a target of role `finance`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a member may remove any non-owner member)

**Given**
1. T = member(UA), but `role "finance"`.
2. R = member(UB), but `role "member"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="member")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-31 — a `viewer` remover may not remove a target of role `manager`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a viewer may remove any non-owner member)

**Given**
1. T = member(UA), but `role "manager"`.
2. R = member(UB), but `role "viewer"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="viewer")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-32 — a `viewer` remover may not remove a target of role `member`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a viewer may remove any non-owner member)

**Given**
1. T = member(UA), but `role "member"`.
2. R = member(UB), but `role "viewer"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="viewer")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-33 — a `viewer` remover may not remove a target of role `viewer`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a viewer may remove any non-owner member)

**Given**
1. T = member(UA), but `role "viewer"`.
2. R = member(UB), but `role "viewer"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="viewer")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-34 — a `viewer` remover may not remove a target of role `ground-team`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a viewer may remove any non-owner member)

**Given**
1. T = member(UA), but `role "ground-team"`.
2. R = member(UB), but `role "viewer"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="viewer")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-35 — a `viewer` remover may not remove a target of role `ground-team-manager`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a viewer may remove any non-owner member)

**Given**
1. T = member(UA), but `role "ground-team-manager"`.
2. R = member(UB), but `role "viewer"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="viewer")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-36 — a `viewer` remover may not remove a target of role `finance`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a viewer may remove any non-owner member)

**Given**
1. T = member(UA), but `role "finance"`.
2. R = member(UB), but `role "viewer"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="viewer")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-37 — a `finance` remover may not remove a target of role `manager`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a finance may remove any non-owner member)

**Given**
1. T = member(UA), but `role "manager"`.
2. R = member(UB), but `role "finance"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="finance")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-38 — a `finance` remover may not remove a target of role `member`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a finance may remove any non-owner member)

**Given**
1. T = member(UA), but `role "member"`.
2. R = member(UB), but `role "finance"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="finance")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-39 — a `finance` remover may not remove a target of role `viewer`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a finance may remove any non-owner member)

**Given**
1. T = member(UA), but `role "viewer"`.
2. R = member(UB), but `role "finance"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="finance")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-40 — a `finance` remover may not remove a target of role `ground-team`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a finance may remove any non-owner member)

**Given**
1. T = member(UA), but `role "ground-team"`.
2. R = member(UB), but `role "finance"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="finance")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-41 — a `finance` remover may not remove a target of role `ground-team-manager`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a finance may remove any non-owner member)

**Given**
1. T = member(UA), but `role "ground-team-manager"`.
2. R = member(UB), but `role "finance"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="finance")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-42 — a `finance` remover may not remove a target of role `finance`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a finance may remove any non-owner member)

**Given**
1. T = member(UA), but `role "finance"`.
2. R = member(UB), but `role "finance"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="finance")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-43 — the role `Owner` in capitals may not remove a target of role `member`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: any role other than ground-team and ground-team-manager may remove)

**Given**
1. T = member(UA), but `role "member"`.
2. R = member(UB), but `role "Owner"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="Owner")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-44 — the role `Manager` in capitals may not remove a target of role `ground-team`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: any role other than ground-team and ground-team-manager may remove)

**Given**
1. T = member(UA), but `role "ground-team"`.
2. R = member(UB), but `role "Manager"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="Manager")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-45 — `ground-team-manager` with a trailing space may not remove a target of role `ground-team`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: any role other than ground-team and ground-team-manager may remove)

**Given**
1. T = member(UA), but `role "ground-team"`.
2. R = member(UB), but `role "ground-team-manager "`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="ground-team-manager ")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-46 — an empty role may not remove a target of role `ground-team`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: any role other than ground-team and ground-team-manager may remove)

**Given**
1. T = member(UA), but `role "ground-team"`.
2. R = member(UB), but `role ""`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-47 — the unknown role `admin` may not remove a target of role `ground-team`
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: any role other than ground-team and ground-team-manager may remove)

**Given**
1. T = member(UA), but `role "ground-team"`.
2. R = member(UB), but `role "admin"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="admin")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-48 — the owner's own row cannot be removed, even by the owner
- **Rules:** `remove_member_from_workspace` R2; Errors row 2; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UO.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Cannot remove workspace owner. Transfer ownership first."`.
3. unchanged: unchanged(MO).
4. nothing written.

### WSMG-RM-49 — a `ground-team` remover asking to remove the owner gets the owner message first
- **Rules:** `remove_member_from_workspace` R2, R3
- **Kind:** error
- **Expect:** pass

**Given**
1. R = member(UB), but `role "ground-team"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UO.id, remover_id=UB.id, remover_role="ground-team")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Cannot remove workspace owner. Transfer ownership first."`.
3. unchanged: unchanged(MO).
4. nothing written.

### WSMG-RM-50 — a `ground-team-manager` remover asking to remove the owner gets the owner message first
- **Rules:** `remove_member_from_workspace` R2, R4
- **Kind:** error
- **Expect:** pass

**Given**
1. R = member(UB), but `role "ground-team-manager"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UO.id, remover_id=UB.id, remover_role="ground-team-manager")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Cannot remove workspace owner. Transfer ownership first."`.
3. unchanged: unchanged(MO).
4. nothing written.

### WSMG-RM-51 — a `member` remover asking to remove the owner gets the owner message first
- **Rules:** `remove_member_from_workspace` R2, R5
- **Kind:** error
- **Expect:** pass

**Given**
1. R = member(UB), but `role "member"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UO.id, remover_id=UB.id, remover_role="member")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Cannot remove workspace owner. Transfer ownership first."`.
3. unchanged: unchanged(MO).
4. nothing written.

### WSMG-RM-52 — a user with no row in the workspace is refused
- **Rules:** `remove_member_from_workspace` R1; Errors row 1; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "User is not a member of this workspace"`.
3. nothing written.

### WSMG-RM-53 — the user's row in an earlier workspace does not count
- **Rules:** `remove_member_from_workspace` R1 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = member(UA), but `workspace_id W0.id`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "User is not a member of this workspace"`.
3. unchanged: unchanged(Z).
4. nothing written.

### WSMG-RM-54 — the user's row in a later workspace does not count
- **Rules:** `remove_member_from_workspace` R1 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = member(UA), but `workspace_id W2.id`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "User is not a member of this workspace"`.
3. unchanged: unchanged(Z).
4. nothing written.

### WSMG-RM-55 — rows of other users, with a lower and a higher user id, do not count
- **Rules:** `remove_member_from_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = member(UA).
2. C = member(UC).

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UB.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "User is not a member of this workspace"`.
3. unchanged: unchanged(A).
4. unchanged: unchanged(C).
5. nothing written.

### WSMG-RM-56 — an already removed (inactive) member is refused and keeps their leaving date
- **Rules:** `remove_member_from_workspace` R1a [BUG-1984]; Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1984
- **Fails today on:** Then 1 (no error is raised today: the removal is repeated)

**Given**
1. T = member(UA), but `status "inactive"`, `joined_at T1`, `left_at T2`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "User is not a member of this workspace"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-57 — a suspended member can be removed
- **Rules:** `remove_member_from_workspace` R1, R1a, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = member(UA), but `status "suspended"`.

**When**
- `result = M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. re-read T: `status == "inactive"`, `left_at == NOW`.
2. audit: audit(W1) has exactly 1 row.
3. returns: `result is None`.

### WSMG-RM-58 — removal keeps the row, its role, position and joining date
- **Rules:** `remove_member_from_workspace` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = member(UA), but `role "viewer"`, `position "Welder"`, `joined_at T1`.

**When**
- `result = M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. re-read T: `status == "inactive"`, `left_at == NOW`.
2. re-read T: `role == "viewer"`, `position == "Welder"`, `joined_at == T1`.
3. count: members(W1, UA) has exactly 1 row.
4. unchanged: unchanged(MO).
5. returns: `result is None`.

### WSMG-RM-59 — the remover id is not checked: an owner role passed by someone with no row still removes
- **Rules:** `remove_member_from_workspace` R5a, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = member(UA).

**When**
- `result = M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UC.id, remover_role="owner")`.

**Then**
1. re-read T: `status == "inactive"`, `left_at == NOW`.
2. count: members(W1, UC) has exactly 0 rows.
3. audit: audit(W1) has exactly 1 row.
4. audit: that row: `user_id == UC.id`, `action == "member_removed"`, `metadata_json == {"removed_member_id": UA.id}`.
5. audit: that row: `resource_type is None`, `resource_id is None`, `ip_address is None`, `user_agent is None`.
6. returns: `result is None`.

### WSMG-RM-60 — a member cannot remove themselves
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a member may remove themselves)

**Given**
1. T = member(UA).

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UA.id, remover_role="member")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-61 — owner of an earlier workspace, member here: refused
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990] (grant held in another workspace)
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a member may remove)

**Given**
1. Z = member(UB), but `workspace_id W0.id`, `role "owner"`.
2. R = member(UB).
3. T = member(UA).

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="member")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-62 — owner of a later workspace, member here: refused
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990] (grant held in another workspace)
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a member may remove)

**Given**
1. R = member(UB).
2. T = member(UA).
3. Z = member(UB), but `workspace_id W2.id`, `role "owner"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="member")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-63 — ground-team-manager of an earlier workspace, viewer here: may not remove ground-team
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990] (grant held in another workspace)
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a viewer may remove)

**Given**
1. Z = member(UB), but `workspace_id W0.id`, `role "ground-team-manager"`.
2. R = member(UB), but `role "viewer"`.
3. T = member(UA), but `role "ground-team"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="viewer")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-64 — manager of a later workspace, viewer here: may not remove ground-team
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990] (grant held in another workspace)
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a viewer may remove)

**Given**
1. R = member(UB), but `role "viewer"`.
2. T = member(UA), but `role "ground-team"`.
3. Z = member(UB), but `workspace_id W2.id`, `role "manager"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="viewer")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-65 — owner of a later workspace, ground-team here: refused
- **Rules:** `remove_member_from_workspace` R3 (grant held in another workspace)
- **Kind:** error
- **Expect:** pass

**Given**
1. R = member(UB), but `role "ground-team"`.
2. T = member(UA).
3. Z = member(UB), but `workspace_id W2.id`, `role "owner"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="ground-team")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-66 — owner of an earlier workspace, ground-team-manager here: may not remove a member
- **Rules:** `remove_member_from_workspace` R4 (grant held in another workspace)
- **Kind:** error
- **Expect:** pass

**Given**
1. Z = member(UB), but `workspace_id W0.id`, `role "owner"`.
2. R = member(UB), but `role "ground-team-manager"`.
3. T = member(UA).

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="ground-team-manager")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Managers can only remove ground-team members"`.
3. unchanged: unchanged(T).
4. nothing written.

### WSMG-RM-67 — removal leaves invitations and the member's other workspaces alone
- **Rules:** `remove_member_from_workspace` R12, R11
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = member(UA).
2. Z = member(UA), but `workspace_id W2.id`.
3. J = invitation J to EA.

**When**
- `result = M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. re-read T: `status == "inactive"`.
2. unchanged: unchanged(Z).
3. unchanged: unchanged(J).
4. audit: audit(W2) has exactly 0 rows.
5. returns: `result is None`.

### WSMG-RM-68 — a refused removal touches no approver, project member or assignee row
- **Rules:** `remove_member_from_workspace` R3, R5, R8, R9, R10
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. T = member(UA).
2. R = member(UB), but `role "ground-team"`.
3. A W1 work order WO1 with status `DRAFT` (a `work_order_types` row of W1 as its type), and on it a `WorkOrderApprover` of UA with `approved False` and a `WorkOrderAssignee` of UA.
4. A W1 `Project` PR1 and a `ProjectMember` row of UA on PR1.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="ground-team")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. count: `work_order_approvers` with `user_id == UA.id` has exactly 1 row.
5. count: `work_order_assignees` with `user_id == UA.id` has exactly 1 row.
6. count: `project_members` with `user_id == UA.id` has exactly 1 row.
7. count: `work_order_events` with `work_order_id == WO1.id` has exactly 0 rows.

### WSMG-RM-69 — a refused member remover touches no approver, project member or assignee row
- **Rules:** `remove_member_from_workspace` R5 [BUG-1990]
- **Kind:** bug
- **Expect:** xfail BUG-1990
- **Fails today on:** Then 1 (no error is raised today: a member may remove)
- **Author:** claude

**Given**
1. T = member(UA).
2. R = member(UB).
3. A W1 work order WO1 with status `DRAFT`, and on it a `WorkOrderApprover` of UA with `approved False` and a `WorkOrderAssignee` of UA.
4. A W1 `Project` PR1 and a `ProjectMember` row of UA on PR1.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UB.id, remover_role="member")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "You do not have permission to remove members"`.
3. unchanged: unchanged(T).
4. count: `work_order_approvers` with `user_id == UA.id` has exactly 1 row.
5. count: `work_order_assignees` with `user_id == UA.id` has exactly 1 row.
6. count: `project_members` with `user_id == UA.id` has exactly 1 row.

### WSMG-RM-70 — removal deletes the member's pending approvals on open expense orders only, with one event per order
- **Rules:** `remove_member_from_workspace` R8 [BUG-1201]
- **Kind:** bug
- **Expect:** xfail BUG-1201
- **Fails today on:** Then 2 (no approver row is touched today)
- **Author:** claude

**Given**
1. T = member(UA).
2. OO = a W1 `ExpenseOrder`, open: `completed_at None`, `voided False`; with a `ExpenseOrderApprover` row AP_OO of UA, `approved False`.
3. OC1 = a W1 `ExpenseOrder`, not open: `completed_at T2`, `voided False`; with a `ExpenseOrderApprover` row AP_OC1 of UA, `approved False`.
4. OC2 = a W1 `ExpenseOrder`, not open: `completed_at None`, `voided True`; with a `ExpenseOrderApprover` row AP_OC2 of UA, `approved False`.
5. OA = a W1 `ExpenseOrder`, open: `completed_at None`, `voided False`; with a `ExpenseOrderApprover` row AY of UA, `approved True`, `approved_at T1`.

**When**
- `result = M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. re-read T: `status == "inactive"`.
2. count: `ExpenseOrderApprover` rows with `id == AP_OO.id` — exactly 0.
3. count: `ExpenseOrderEvent` rows with `expense_order_id == OO.id` and `event_type == "approver_removed"` — exactly 1.
4. event: that row: `workspace_id == W1.id`, `performed_by == UO.id`, `description == "Removed Ann Lee as approver"`, `metadata_json == {"user_id": UA.id, "user_name": "Ann Lee"}`.
5. count: `ExpenseOrderApprover` rows with `id == AP_OC1.id` — exactly 1.
6. count: `ExpenseOrderApprover` rows with `id == AP_OC2.id` — exactly 1.
7. count: `ExpenseOrderApprover` rows with `id == AY.id` — exactly 1.
8. count: `ExpenseOrderEvent` rows with `expense_order_id` in (OC1, OC2, OA) — exactly 0.

### WSMG-RM-71 — removal deletes the member's pending approvals on open purchase orders only, with one event per order
- **Rules:** `remove_member_from_workspace` R8 [BUG-1201]
- **Kind:** bug
- **Expect:** xfail BUG-1201
- **Fails today on:** Then 2 (no approver row is touched today)
- **Author:** claude

**Given**
1. T = member(UA).
2. SP = `Status(workspace_id=W1.id, name="Planning", comment="stage")`; SC = the same, `name "Complete"`.
3. OO = a W1 `PurchaseOrder`, open: `voided False`, `current_status_id SP.id`, `invoice_id None`; with a `PurchaseOrderApprover` row AP_OO of UA, `approved False`.
4. OO2 = a W1 `PurchaseOrder`, open: `voided False`, `current_status_id SP.id`, `invoice_id` = an invoice with `invoice_status "draft"`; with a `PurchaseOrderApprover` row AP_OO2 of UA, `approved False`.
5. OC1 = a W1 `PurchaseOrder`, not open: `voided True`, `current_status_id SP.id`, `invoice_id None`; with a `PurchaseOrderApprover` row AP_OC1 of UA, `approved False`.
6. OC2 = a W1 `PurchaseOrder`, not open: `voided False`, `current_status_id SC.id`, `invoice_id None`; with a `PurchaseOrderApprover` row AP_OC2 of UA, `approved False`.
7. OC3 = a W1 `PurchaseOrder`, not open: `voided False`, `current_status_id SP.id`, `invoice_id` = an invoice with `invoice_status "locked"`; with a `PurchaseOrderApprover` row AP_OC3 of UA, `approved False`.
8. OA = a W1 `PurchaseOrder`, open: `voided False`, `current_status_id SP.id`, `invoice_id None`; with a `PurchaseOrderApprover` row AY of UA, `approved True`, `approved_at T1`.

**When**
- `result = M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. re-read T: `status == "inactive"`.
2. count: `PurchaseOrderApprover` rows with `id == AP_OO.id` — exactly 0.
3. count: `PurchaseOrderApprover` rows with `id == AP_OO2.id` — exactly 0.
4. count: `PurchaseOrderEvent` rows with `purchase_order_id == OO.id` and `event_type == "approver_removed"` — exactly 1.
5. event: that row: `workspace_id == W1.id`, `performed_by == UO.id`, `description == "Removed Ann Lee as approver"`, `metadata_json == {"user_id": UA.id, "user_name": "Ann Lee"}`.
6. count: `PurchaseOrderEvent` rows with `purchase_order_id == OO2.id` and `event_type == "approver_removed"` — exactly 1.
7. event: that row: `workspace_id == W1.id`, `performed_by == UO.id`, `description == "Removed Ann Lee as approver"`, `metadata_json == {"user_id": UA.id, "user_name": "Ann Lee"}`.
8. count: `PurchaseOrderApprover` rows with `id == AP_OC1.id` — exactly 1.
9. count: `PurchaseOrderApprover` rows with `id == AP_OC2.id` — exactly 1.
10. count: `PurchaseOrderApprover` rows with `id == AP_OC3.id` — exactly 1.
11. count: `PurchaseOrderApprover` rows with `id == AY.id` — exactly 1.
12. count: `PurchaseOrderEvent` rows with `purchase_order_id` in (OC1, OC2, OC3, OA) — exactly 0.

### WSMG-RM-72 — removal deletes the member's pending approvals on open sales orders only, with one event per order
- **Rules:** `remove_member_from_workspace` R8 [BUG-1201]
- **Kind:** bug
- **Expect:** xfail BUG-1201
- **Fails today on:** Then 2 (no approver row is touched today)
- **Author:** claude

**Given**
1. T = member(UA).
2. OO = a W1 `SalesOrder`, open: `order_completed False`, `invoice_id None`; with a `SalesOrderApprover` row AP_OO of UA, `approved False`.
3. OO2 = a W1 `SalesOrder`, open: `order_completed False`, `invoice_id` = an invoice with `invoice_status "draft"`; with a `SalesOrderApprover` row AP_OO2 of UA, `approved False`.
4. OC1 = a W1 `SalesOrder`, not open: `order_completed True`, `invoice_id None`; with a `SalesOrderApprover` row AP_OC1 of UA, `approved False`.
5. OC2 = a W1 `SalesOrder`, not open: `order_completed False`, `invoice_id` = an invoice with `invoice_status "confirmed"`; with a `SalesOrderApprover` row AP_OC2 of UA, `approved False`.
6. OC3 = a W1 `SalesOrder`, not open: `order_completed False`, `invoice_id` = an invoice with `invoice_status "locked"`; with a `SalesOrderApprover` row AP_OC3 of UA, `approved False`.
7. OA = a W1 `SalesOrder`, open: `order_completed False`, `invoice_id None`; with a `SalesOrderApprover` row AY of UA, `approved True`, `approved_at T1`.

**When**
- `result = M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. re-read T: `status == "inactive"`.
2. count: `SalesOrderApprover` rows with `id == AP_OO.id` — exactly 0.
3. count: `SalesOrderApprover` rows with `id == AP_OO2.id` — exactly 0.
4. count: `SalesOrderEvent` rows with `sales_order_id == OO.id` and `event_type == "approver_removed"` — exactly 1.
5. event: that row: `workspace_id == W1.id`, `performed_by == UO.id`, `description == "Removed Ann Lee as approver"`, `metadata_json == {"user_id": UA.id, "user_name": "Ann Lee"}`.
6. count: `SalesOrderEvent` rows with `sales_order_id == OO2.id` and `event_type == "approver_removed"` — exactly 1.
7. event: that row: `workspace_id == W1.id`, `performed_by == UO.id`, `description == "Removed Ann Lee as approver"`, `metadata_json == {"user_id": UA.id, "user_name": "Ann Lee"}`.
8. count: `SalesOrderApprover` rows with `id == AP_OC1.id` — exactly 1.
9. count: `SalesOrderApprover` rows with `id == AP_OC2.id` — exactly 1.
10. count: `SalesOrderApprover` rows with `id == AP_OC3.id` — exactly 1.
11. count: `SalesOrderApprover` rows with `id == AY.id` — exactly 1.
12. count: `SalesOrderEvent` rows with `sales_order_id` in (OC1, OC2, OC3, OA) — exactly 0.

### WSMG-RM-73 — removal deletes the member's pending approvals on open transfer orders only, with one event per order
- **Rules:** `remove_member_from_workspace` R8 [BUG-1201]
- **Kind:** bug
- **Expect:** xfail BUG-1201
- **Fails today on:** Then 2 (no approver row is touched today)
- **Author:** claude

**Given**
1. T = member(UA).
2. OO = a W1 `TransferOrder`, open: `completed_at None`; with a `TransferOrderApprover` row AP_OO of UA, `approved False`.
3. OC1 = a W1 `TransferOrder`, not open: `completed_at T2`; with a `TransferOrderApprover` row AP_OC1 of UA, `approved False`.
4. OA = a W1 `TransferOrder`, open: `completed_at None`; with a `TransferOrderApprover` row AY of UA, `approved True`, `approved_at T1`.

**When**
- `result = M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. re-read T: `status == "inactive"`.
2. count: `TransferOrderApprover` rows with `id == AP_OO.id` — exactly 0.
3. count: `TransferOrderEvent` rows with `transfer_order_id == OO.id` and `event_type == "approver_removed"` — exactly 1.
4. event: that row: `workspace_id == W1.id`, `performed_by == UO.id`, `description == "Removed Ann Lee as approver"`, `metadata_json == {"user_id": UA.id, "user_name": "Ann Lee"}`.
5. count: `TransferOrderApprover` rows with `id == AP_OC1.id` — exactly 1.
6. count: `TransferOrderApprover` rows with `id == AY.id` — exactly 1.
7. count: `TransferOrderEvent` rows with `transfer_order_id` in (OC1, OA) — exactly 0.

### WSMG-RM-74 — removal deletes the member's pending approvals on open work orders only, with one event per order
- **Rules:** `remove_member_from_workspace` R8 [BUG-1201]
- **Kind:** bug
- **Expect:** xfail BUG-1201
- **Fails today on:** Then 2 (no approver row is touched today)
- **Author:** claude

**Given**
1. T = member(UA).
2. OO = a W1 `WorkOrder`, open: `status DRAFT`; with a `WorkOrderApprover` row AP_OO of UA, `approved False`.
3. OO2 = a W1 `WorkOrder`, open: `status IN_PROGRESS`; with a `WorkOrderApprover` row AP_OO2 of UA, `approved False`.
4. OC1 = a W1 `WorkOrder`, not open: `status COMPLETED`; with a `WorkOrderApprover` row AP_OC1 of UA, `approved False`.
5. OC2 = a W1 `WorkOrder`, not open: `status VOIDED`; with a `WorkOrderApprover` row AP_OC2 of UA, `approved False`.
6. OA = a W1 `WorkOrder`, open: `status DRAFT`; with a `WorkOrderApprover` row AY of UA, `approved True`, `approved_at T1`.

**When**
- `result = M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. re-read T: `status == "inactive"`.
2. count: `WorkOrderApprover` rows with `id == AP_OO.id` — exactly 0.
3. count: `WorkOrderApprover` rows with `id == AP_OO2.id` — exactly 0.
4. count: `WorkOrderEvent` rows with `work_order_id == OO.id` and `event_type == "approver_removed"` — exactly 1.
5. event: that row: `workspace_id == W1.id`, `performed_by == UO.id`, `description == "Removed Ann Lee as approver"`, `metadata_json == {"user_id": UA.id, "user_name": "Ann Lee"}`.
6. count: `WorkOrderEvent` rows with `work_order_id == OO2.id` and `event_type == "approver_removed"` — exactly 1.
7. event: that row: `workspace_id == W1.id`, `performed_by == UO.id`, `description == "Removed Ann Lee as approver"`, `metadata_json == {"user_id": UA.id, "user_name": "Ann Lee"}`.
8. count: `WorkOrderApprover` rows with `id == AP_OC1.id` — exactly 1.
9. count: `WorkOrderApprover` rows with `id == AP_OC2.id` — exactly 1.
10. count: `WorkOrderApprover` rows with `id == AY.id` — exactly 1.
11. count: `WorkOrderEvent` rows with `work_order_id` in (OC1, OC2, OA) — exactly 0.

### WSMG-RM-75 — approved rows, not-open orders and other workspaces keep their approver rows today and after
- **Rules:** `remove_member_from_workspace` R8, R11
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. T = member(UA).
2. For each order type, a W1 order that is **not open** with a `approved False` approver row of UA: `ExpenseOrder` `completed_at T2`; `PurchaseOrder` `voided True`; `SalesOrder` `order_completed True`; `TransferOrder` `completed_at T2`; `WorkOrder` `status COMPLETED`.
3. For each order type, a W1 order that is **open** with a `approved True`, `approved_at T1` approver row of UA: `ExpenseOrder` `completed_at None`, `voided False`; `PurchaseOrder` `voided False`, `invoice_id None`, `current_status_id` a W1 status `"Planning"`; `SalesOrder` `order_completed False`, `invoice_id None`; `TransferOrder` `completed_at None`; `WorkOrder` `status DRAFT`.
4. Z = member(UA), but `workspace_id W2.id`; a W2 `WorkOrder` W9 with `status DRAFT` and a `WorkOrderApprover` row of UA, `approved False`.

**When**
- `result = M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. re-read T: `status == "inactive"`.
2. count: every approver row built in the Given still exists (10 in W1, 1 in W2).
3. count: the five event tables hold 0 rows with `event_type == "approver_removed"` for any of these orders.
4. returns: `result is None`.

### WSMG-RM-76 — removal deletes the member's project memberships in this workspace, one event per project
- **Rules:** `remove_member_from_workspace` R9 [BUG-1280]
- **Kind:** bug
- **Expect:** xfail BUG-1280
- **Fails today on:** Then 2 (no project member row is touched today)
- **Author:** claude

**Given**
1. T = member(UA).
2. Two W1 `Project` rows PR1, PR2, each with a `ProjectMember` row of UA.
3. A W1 `Project` PR3 with a `ProjectMember` row of UB.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. re-read T: `status == "inactive"`.
2. count: `project_members` of UA on PR1 or PR2 — exactly 0.
3. count: `ProjectEvent` rows with `project_id == PR1.id` and `event_type == "member_removed"` — exactly 1.
4. event: that row: `workspace_id == W1.id`, `performed_by == UO.id`, `description == "Removed Ann Lee from the project"`, `metadata_json == {"user_id": UA.id, "user_name": "Ann Lee"}`.
5. count: `ProjectEvent` rows with `project_id == PR2.id` and `event_type == "member_removed"` — exactly 1.
6. count: `project_members` of UB on PR3 — exactly 1.

### WSMG-RM-77 — project memberships in another workspace stay
- **Rules:** `remove_member_from_workspace` R9, R11
- **Kind:** isolation
- **Expect:** pass
- **Author:** claude

**Given**
1. T = member(UA).
2. Z = member(UA), but `workspace_id W2.id`.
3. A W2 `Project` PR9 with a `ProjectMember` row PM9 of UA.

**When**
- `result = M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. re-read T: `status == "inactive"`.
2. count: `project_members` with `id == PM9.id` — exactly 1.
3. count: `ProjectEvent` rows of PR9 — exactly 0.
4. returns: `result is None`.

### WSMG-RM-78 — removal deletes the member's assignments on draft and in-progress work orders, one event per order
- **Rules:** `remove_member_from_workspace` R10 [BUG-1883]
- **Kind:** bug
- **Expect:** xfail BUG-1883
- **Fails today on:** Then 2 (no assignee row is touched today)
- **Author:** claude

**Given**
1. T = member(UA).
2. W1 work orders WD (status `DRAFT`) and WI (status `IN_PROGRESS`), each with a `WorkOrderAssignee` row of UA.
3. On WD also a `WorkOrderAssignee` row of UB.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. re-read T: `status == "inactive"`.
2. count: `work_order_assignees` of UA on WD or WI — exactly 0.
3. count: `WorkOrderEvent` rows with `work_order_id == WD.id` and `event_type == "assignee_removed"` — exactly 1.
4. event: that row: `workspace_id == W1.id`, `performed_by == UO.id`, `description == "Removed Ann Lee as assignee"`, `metadata_json == {"user_id": UA.id, "user_name": "Ann Lee"}`.
5. count: `WorkOrderEvent` rows with `work_order_id == WI.id` and `event_type == "assignee_removed"` — exactly 1.
6. count: `work_order_assignees` of UB on WD — exactly 1.

### WSMG-RM-79 — a soft-deleted draft work order loses the member's assignment too
- **Rules:** `remove_member_from_workspace` R10 [BUG-1883]
- **Kind:** bug
- **Expect:** xfail BUG-1883
- **Fails today on:** Then 2 (no assignee row is touched today)
- **Author:** claude

**Given**
1. T = member(UA).
2. A W1 work order WS with status `DRAFT`, `is_deleted True`, with a `WorkOrderAssignee` row of UA.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. re-read T: `status == "inactive"`.
2. count: `work_order_assignees` of UA on WS — exactly 0.
3. count: `WorkOrderEvent` rows with `work_order_id == WS.id` and `event_type == "assignee_removed"` — exactly 1.

### WSMG-RM-80 — completed and voided work orders, completers, other workspaces and the free-text assignee stay
- **Rules:** `remove_member_from_workspace` R10, R11
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. T = member(UA).
2. W1 work orders WC (status `COMPLETED`) and WV (status `VOIDED`), each with a `WorkOrderAssignee` row of UA.
3. A W1 work order WD (status `DRAFT`, `assigned_to "Ann Lee"`) with a `work_order_completers` row of UA.
4. Z = member(UA), but `workspace_id W2.id`; a W2 work order W9 (status `DRAFT`) with a `WorkOrderAssignee` row of UA.

**When**
- `result = M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`.

**Then**
1. re-read T: `status == "inactive"`.
2. count: `work_order_assignees` of UA on WC, WV and W9 — exactly 3.
3. count: `work_order_completers` of UA on WD — exactly 1.
4. re-read WD: `assigned_to == "Ann Lee"`.
5. count: `WorkOrderEvent` rows of WC, WV, WD and W9 together — exactly 0.
6. returns: `result is None`.

### WSMG-RM-81 — removal flushes and never commits
- **Rules:** `remove_member_from_workspace` R11; Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = member(UA).

**When**
- `result = M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner")`. Rolled back.

**Then**
1. re-read T: `status == "inactive"` (inside).
2. mock called: `cm.call_count == 0`.
3. re-read T: `status == "active"`, `left_at is None` (after the savepoint rollback).
4. returns: `result is None`.

### WSMG-RM-82 — the audit row carries the request's IP address and user agent
- **Rules:** A2 [BUG-1404]; `remove_member_from_workspace` R7
- **Kind:** bug
- **Expect:** xfail BUG-1404
- **Fails today on:** Then 1 (the call raises TypeError: no `ip_address` parameter)

**Given**
1. T = member(UA).

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UA.id, remover_id=UO.id, remover_role="owner", ip_address="203.0.113.7", user_agent="Mozilla/5.0 Test")`.

**Then**
1. audit: audit(W1) has exactly 1 row.
2. audit: that row: `ip_address == "203.0.113.7"`, `user_agent == "Mozilla/5.0 Test"`.
### WSMG-RM-83 — a `manager` remover asking to remove the owner gets the owner message
- **Rules:** `remove_member_from_workspace` R2; Errors row 2; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. R = member(UB), but `role "manager"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UO.id, remover_id=UB.id, remover_role="manager")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Cannot remove workspace owner. Transfer ownership first."`.
3. unchanged: unchanged(MO).
4. unchanged: unchanged(R).
5. nothing written.

### WSMG-RM-84 — a `viewer` remover asking to remove the owner gets the owner message
- **Rules:** `remove_member_from_workspace` R2; Errors row 2; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. R = member(UB), but `role "viewer"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UO.id, remover_id=UB.id, remover_role="viewer")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Cannot remove workspace owner. Transfer ownership first."`.
3. unchanged: unchanged(MO).
4. unchanged: unchanged(R).
5. nothing written.

### WSMG-RM-85 — a `finance` remover asking to remove the owner gets the owner message
- **Rules:** `remove_member_from_workspace` R2; Errors row 2; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. R = member(UB), but `role "finance"`.

**When**
- `M.remove_member_from_workspace(db, workspace_id=W1.id, user_id=UO.id, remover_id=UB.id, remover_role="finance")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Cannot remove workspace owner. Transfer ownership first."`.
3. unchanged: unchanged(MO).
4. unchanged: unchanged(R).
5. nothing written.

## `WorkspaceManager.create_invitation`

> Seat cards use positive limits only. `max_members = 0` (pending, BUG-1989) lives only in section P17. Seat count = active members of W1 (owner MO included) + W1 invitations with status exactly `pending` and `expires_at > NOW`. Seat cards invite EE, which no Given row uses, so BUG-1873 never fires in them.

### WSMG-CI-01 — the invitation is stored pending, with the inviter, position and a 3-day expiry
- **Rules:** `create_invitation` R10, R12, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=ED, role="member", inviter_id=UO.id, position="Driver")`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. returns: `result.id is not None`.
3. re-read the returned row: `workspace_id == W1.id`, `email == ED`, `role == "member"`, `position == "Driver"`.
4. re-read the returned row: `invited_by_user_id == UO.id`, `status == "pending"`, `invited_at is not None`.
5. re-read the returned row: `accepted_at is None`, `accepted_by_user_id is None`.
6. re-read the returned row: `expires_at == NOW + timedelta(days=3)`.
7. count: invitations(W1) has exactly 1 row.

### WSMG-CI-02 — the email is stored lower-cased
- **Rules:** `create_invitation` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=f"Dan.{TAG}@Acme.COM", role="member", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `email == f"dan.{TAG}@acme.com"`.

### WSMG-CI-03 — the token is a 43-character URL-safe string
- **Rules:** `create_invitation` R11
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=ED, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `len(token) == 43`.
3. re-read the returned row: `re.fullmatch(r"[A-Za-z0-9_-]{43}", token) is not None`.

### WSMG-CI-04 — the token comes from a fresh secrets.token_urlsafe(32) call
- **Rules:** `create_invitation` R11
- **Kind:** external
- **Expect:** pass
- **Author:** claude

**Given**
1. `secrets.token_urlsafe` is patched at `app.managers.workspace_manager.secrets.token_urlsafe` with `wraps=secrets.token_urlsafe` (spy `tk`).
2. J = invitation J to EE.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=ED, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. mock called: `tk.call_count == 1`.
3. mock called: `tk.call_args.args == (32,)`.
4. re-read the returned row: `token == tk.spy_return` (the value the spy returned).
5. re-read the returned row: `token != J.token`.

### WSMG-CI-05 — the role `manager` is accepted
- **Rules:** `create_invitation` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=ED, role="manager", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `role == "manager"`.

### WSMG-CI-06 — the role `viewer` is accepted
- **Rules:** `create_invitation` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=ED, role="viewer", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `role == "viewer"`.

### WSMG-CI-07 — the role `ground-team` is accepted
- **Rules:** `create_invitation` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=ED, role="ground-team", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `role == "ground-team"`.

### WSMG-CI-08 — `owner` is refused and nothing is written
- **Rules:** `create_invitation` R1; Errors row 1; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=ED, role="owner", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invalid role. Must be one of: ground-team, manager, member, viewer"`.
3. nothing written.

### WSMG-CI-09 — `ground-team-manager` is refused and nothing is written
- **Rules:** `create_invitation` R1; Errors row 1; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=ED, role="ground-team-manager", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invalid role. Must be one of: ground-team, manager, member, viewer"`.
3. nothing written.

### WSMG-CI-10 — `finance` is refused and nothing is written
- **Rules:** `create_invitation` R1; Errors row 1; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=ED, role="finance", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invalid role. Must be one of: ground-team, manager, member, viewer"`.
3. nothing written.

### WSMG-CI-11 — `Manager` in capitals is refused and nothing is written
- **Rules:** `create_invitation` R1; Errors row 1; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=ED, role="Manager", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invalid role. Must be one of: ground-team, manager, member, viewer"`.
3. nothing written.

### WSMG-CI-12 — an empty role is refused and nothing is written
- **Rules:** `create_invitation` R1; Errors row 1; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=ED, role="", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invalid role. Must be one of: ground-team, manager, member, viewer"`.
3. nothing written.

### WSMG-CI-13 — the role is checked before the workspace is looked up
- **Rules:** `create_invitation` R1, R5
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.create_invitation(db, workspace_id=MISSING, email=ED, role="finance", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invalid role. Must be one of: ground-team, manager, member, viewer"`.
3. nothing written.

### WSMG-CI-14 — an active member's email is refused and nothing is written
- **Rules:** `create_invitation` R3; Errors row 2; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = member(UA).

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=EA, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "User with this email is already a member of this workspace"`.
3. nothing written.

### WSMG-CI-15 — an account with no row in the workspace may be invited
- **Rules:** `create_invitation` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=EA, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. re-read the returned row: `workspace_id == W1.id`, `email == EA`, `status == "pending"`.
3. count: invitations(W1) with `status == "pending"` has exactly 1 rows.

### WSMG-CI-16 — an account active only in an earlier workspace may be invited
- **Rules:** `create_invitation` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = member(UA), but `workspace_id W0.id`.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=EA, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. re-read the returned row: `workspace_id == W1.id`, `email == EA`, `status == "pending"`.
3. count: invitations(W1) with `status == "pending"` has exactly 1 rows.

### WSMG-CI-17 — an account active only in a later workspace may be invited
- **Rules:** `create_invitation` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = member(UA), but `workspace_id W2.id`.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=EA, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. re-read the returned row: `workspace_id == W1.id`, `email == EA`, `status == "pending"`.
3. count: invitations(W1) with `status == "pending"` has exactly 1 rows.

### WSMG-CI-18 — part of a member's email is another address
- **Rules:** `create_invitation` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member(UA).

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=f"nn.{TAG}@acme.com", role="member", inviter_id=UO.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. re-read the returned row: `workspace_id == W1.id`, `email == f"nn.{TAG}@acme.com"`, `status == "pending"`.
3. count: invitations(W1) with `status == "pending"` has exactly 1 rows.

### WSMG-CI-19 — an underscore in a member's email is not a wildcard
- **Rules:** `create_invitation` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = `make_profile(db, email=f"a_n.{TAG}@acme.com")`.
2. A = member(P1).

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=f"abn.{TAG}@acme.com", role="member", inviter_id=UO.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. re-read the returned row: `workspace_id == W1.id`, `email == f"abn.{TAG}@acme.com"`, `status == "pending"`.
3. count: invitations(W1) with `status == "pending"` has exactly 1 rows.

### WSMG-CI-20 — a member's email in other capitals is recognised
- **Rules:** `create_invitation` R2 [BUG-1860], R3
- **Kind:** bug
- **Expect:** xfail BUG-1860
- **Fails today on:** Then 1 (no error is raised today: the exact lookup misses and the invitation is created)

**Given**
1. A = member(UA).

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=f"ANN.{TAG.upper()}@ACME.COM", role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "User with this email is already a member of this workspace"`.
3. nothing written.

### WSMG-CI-21 — a member's email with surrounding spaces is recognised
- **Rules:** `create_invitation` R2 [BUG-1860], R3
- **Kind:** bug
- **Expect:** xfail BUG-1860
- **Fails today on:** Then 1 (no error is raised today: the exact lookup misses)

**Given**
1. A = member(UA).

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=f"  {EA} ", role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "User with this email is already a member of this workspace"`.
3. nothing written.

### WSMG-CI-22 — an account stored in mixed case is found by its lower-case email
- **Rules:** `create_invitation` R2 [BUG-1860], R3
- **Kind:** bug
- **Expect:** xfail BUG-1860
- **Fails today on:** Then 1 (no error is raised today: the exact lookup misses)

**Given**
1. P1 = `make_profile(db, email=f"Zed.{TAG}@acme.com")`.
2. A = member(P1).

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=f"zed.{TAG}@acme.com", role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "User with this email is already a member of this workspace"`.
3. nothing written.

### WSMG-CI-23 — a member row with status `"suspended"` is refused like an active one
- **Rules:** `create_invitation` R3a [BUG-1983]
- **Kind:** bug
- **Expect:** xfail BUG-1983
- **Fails today on:** Then 1 (no error is raised today: only `active` is refused)

**Given**
1. A = member(UA), but `status "suspended"`.

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=EA, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "User with this email is already a member of this workspace"`.
3. nothing written.
4. unchanged: unchanged(A).

### WSMG-CI-24 — a member row with status `"invited"` is refused like an active one
- **Rules:** `create_invitation` R3a [BUG-1983]
- **Kind:** bug
- **Expect:** xfail BUG-1983
- **Fails today on:** Then 1 (no error is raised today: only `active` is refused)

**Given**
1. A = member(UA), but `status "invited"`.

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=EA, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "User with this email is already a member of this workspace"`.
3. nothing written.
4. unchanged: unchanged(A).

### WSMG-CI-25 — a member row with status `"Inactive"` is refused like an active one
- **Rules:** `create_invitation` R3a [BUG-1983]
- **Kind:** bug
- **Expect:** xfail BUG-1983
- **Fails today on:** Then 1 (no error is raised today: only `active` is refused)

**Given**
1. A = member(UA), but `status "Inactive"`.

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=EA, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "User with this email is already a member of this workspace"`.
3. nothing written.
4. unchanged: unchanged(A).

### WSMG-CI-26 — a removed (inactive) member may be invited back
- **Rules:** `create_invitation` R3a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member(UA), but `status "inactive"`, `left_at T2`.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=EA, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. re-read the returned row: `workspace_id == W1.id`, `email == EA`, `status == "pending"`.
3. count: invitations(W1) with `status == "pending"` has exactly 1 rows.
4. unchanged: unchanged(A).

### WSMG-CI-27 — a second pending invitation to the same email is refused
- **Rules:** `create_invitation` R4 [BUG-1873]; Errors row 3; A3
- **Kind:** bug
- **Expect:** xfail BUG-1873
- **Fails today on:** Then 1 (no error is raised today: a second invitation is created)

**Given**
1. J = invitation J to ED.

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=ED, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "This email is already invited to this workspace"`.
3. nothing written.
4. unchanged: unchanged(J).

### WSMG-CI-28 — the duplicate check ignores capitals in the new email
- **Rules:** `create_invitation` R4 [BUG-1873]
- **Kind:** bug
- **Expect:** xfail BUG-1873
- **Fails today on:** Then 1 (no error is raised today)

**Given**
1. J = invitation J to ED.

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=f"DAN.{TAG.upper()}@ACME.COM", role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "This email is already invited to this workspace"`.
3. nothing written.

### WSMG-CI-29 — the duplicate check trims and lower-cases the stored email
- **Rules:** `create_invitation` R4 [BUG-1873]
- **Kind:** bug
- **Expect:** xfail BUG-1873
- **Fails today on:** Then 1 (no error is raised today)

**Given**
1. J = invitation J to `f" Dan.{TAG}@Acme.com "`.

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=ED, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "This email is already invited to this workspace"`.
3. nothing written.

### WSMG-CI-30 — a pending invitation one microsecond from expiry still blocks
- **Rules:** `create_invitation` R4 [BUG-1873]
- **Kind:** bug
- **Expect:** xfail BUG-1873
- **Fails today on:** Then 1 (no error is raised today)

**Given**
1. J = invitation J to ED, but `expires_at NOW + US`.

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=ED, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "This email is already invited to this workspace"`.
3. nothing written.

### WSMG-CI-31 — a pending invitation expiring exactly now does not block
- **Rules:** `create_invitation` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. J = invitation J to ED, but `expires_at NOW`.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=ED, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. re-read the returned row: `workspace_id == W1.id`, `email == ED`, `status == "pending"`.
3. count: invitations(W1) has exactly 2 rows.
4. unchanged: unchanged(J).

### WSMG-CI-32 — an accepted invitation to the same email does not block
- **Rules:** `create_invitation` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. J = invitation J to ED, but `status "accepted"`.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=ED, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. re-read the returned row: `workspace_id == W1.id`, `email == ED`, `status == "pending"`.
3. count: invitations(W1) has exactly 2 rows.
4. unchanged: unchanged(J).

### WSMG-CI-33 — a cancelled invitation to the same email does not block
- **Rules:** `create_invitation` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. J = invitation J to ED, but `status "cancelled"`.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=ED, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. re-read the returned row: `workspace_id == W1.id`, `email == ED`, `status == "pending"`.
3. count: invitations(W1) has exactly 2 rows.
4. unchanged: unchanged(J).

### WSMG-CI-34 — a pending invitation to the same email in an earlier workspace does not block
- **Rules:** `create_invitation` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. J = invitation J to ED, but `workspace_id W0.id`.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=ED, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. re-read the returned row: `workspace_id == W1.id`, `email == ED`, `status == "pending"`.
3. count: invitations(W1) with `status == "pending"` has exactly 1 rows.
4. unchanged: unchanged(J).

### WSMG-CI-35 — a pending invitation to the same email in a later workspace does not block
- **Rules:** `create_invitation` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. J = invitation J to ED, but `workspace_id W2.id`.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=ED, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. re-read the returned row: `workspace_id == W1.id`, `email == ED`, `status == "pending"`.
3. count: invitations(W1) with `status == "pending"` has exactly 1 rows.
4. unchanged: unchanged(J).

### WSMG-CI-36 — an active member with a pending invitation gets the member message
- **Rules:** `create_invitation` R3, R4
- **Kind:** error
- **Expect:** pass

**Given**
1. A = member(UA).
2. J = invitation J to EA.

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=EA, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "User with this email is already a member of this workspace"`.
3. nothing written.

### WSMG-CI-37 — a duplicate invitation on a full workspace gets the duplicate message, not the seat message
- **Rules:** `create_invitation` R4 [BUG-1873], R7
- **Kind:** bug
- **Expect:** xfail BUG-1873
- **Fails today on:** Then 2 (today the message is "Workspace has reached maximum member limit (2). …")

**Given**
1. limit 2
2. J = invitation J to ED.

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=ED, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "This email is already invited to this workspace"`.
3. nothing written.

### WSMG-CI-38 — an unknown workspace is refused and nothing is written
- **Rules:** `create_invitation` R5; Errors row 4; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.create_invitation(db, workspace_id=MISSING, email=EE, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Workspace not found"`.
3. nothing written.

### WSMG-CI-39 — an inactive plan's limit is still enforced
- **Rules:** `create_invitation` R6, R7
- **Kind:** error
- **Expect:** pass

**Given**
1. limit 2
2. `PL1.is_active = False; db.flush()`
3. J = invitation J to ED.

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=EE, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Workspace has reached maximum member limit (2). Upgrade subscription to add more members."`.
3. nothing written.

### WSMG-CI-40 — at the limit with members only (3 active) the invitation is refused
- **Rules:** `create_invitation` R7; Errors row 5; A3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 3
2. B = member(UB).
3. C = member(UC).

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=EE, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Workspace has reached maximum member limit (3). Upgrade subscription to add more members."`.
3. nothing written.

### WSMG-CI-41 — at the limit with members and a pending invitation the invitation is refused
- **Rules:** `create_invitation` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 3
2. B = member(UB).
3. J = invitation J to ED.

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=EE, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Workspace has reached maximum member limit (3). Upgrade subscription to add more members."`.
3. nothing written.

### WSMG-CI-42 — pending invitations alone fill the seats beside the owner
- **Rules:** `create_invitation` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 3
2. J = invitation J to ED.
3. K = invitation K to f"fay.{TAG}@acme.com".

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=EE, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Workspace has reached maximum member limit (3). Upgrade subscription to add more members."`.
3. nothing written.

### WSMG-CI-43 — with one free seat the invitation is created
- **Rules:** `create_invitation` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 3
2. J = invitation J to ED.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=EE, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. re-read the returned row: `workspace_id == W1.id`, `email == EE`, `status == "pending"`.
3. count: invitations(W1) with `status == "pending"` has exactly 2 rows.

### WSMG-CI-44 — above the limit (3 active on a limit of 2) the invitation is refused
- **Rules:** `create_invitation` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 2
2. B = member(UB).
3. C = member(UC).

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=EE, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Workspace has reached maximum member limit (2). Upgrade subscription to add more members."`.
3. nothing written.

### WSMG-CI-45 — the owner alone fills a limit of 1
- **Rules:** `create_invitation` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 1

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=EE, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Workspace has reached maximum member limit (1). Upgrade subscription to add more members."`.
3. nothing written.

### WSMG-CI-46 — a pending invitation that expired exactly now frees its seat
- **Rules:** `create_invitation` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 3
2. J = invitation J to ED.
3. K = invitation K to f"fay.{TAG}@acme.com", but `expires_at NOW`.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=EE, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. re-read the returned row: `workspace_id == W1.id`, `email == EE`, `status == "pending"`.
3. count: invitations(W1) with `status == "pending"` has exactly 3 rows.

### WSMG-CI-47 — a pending invitation one microsecond from expiry still holds its seat
- **Rules:** `create_invitation` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 3
2. J = invitation J to ED.
3. K = invitation K to f"fay.{TAG}@acme.com", but `expires_at NOW + US`.

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=EE, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Workspace has reached maximum member limit (3). Upgrade subscription to add more members."`.
3. nothing written.

### WSMG-CI-48 — an accepted invitation holds no seat
- **Rules:** `create_invitation` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 3
2. J = invitation J to ED.
3. K = invitation K to f"fay.{TAG}@acme.com", but `status "accepted"`.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=EE, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. re-read the returned row: `workspace_id == W1.id`, `email == EE`, `status == "pending"`.
3. count: invitations(W1) with `status == "pending"` has exactly 2 rows.

### WSMG-CI-49 — a cancelled invitation holds no seat
- **Rules:** `create_invitation` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 3
2. J = invitation J to ED.
3. K = invitation K to f"fay.{TAG}@acme.com", but `status "cancelled"`.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=EE, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. re-read the returned row: `workspace_id == W1.id`, `email == EE`, `status == "pending"`.
3. count: invitations(W1) with `status == "pending"` has exactly 2 rows.

### WSMG-CI-50 — a suspended member holds no seat
- **Rules:** `create_invitation` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 3
2. B = member(UB), but `status "suspended"`.
3. J = invitation J to ED.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=EE, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. re-read the returned row: `workspace_id == W1.id`, `email == EE`, `status == "pending"`.
3. count: invitations(W1) with `status == "pending"` has exactly 2 rows.

### WSMG-CI-51 — a removed (inactive) member holds no seat
- **Rules:** `create_invitation` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 3
2. B = member(UB), but `status "inactive"`, `left_at T2`.
3. J = invitation J to ED.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=EE, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. re-read the returned row: `workspace_id == W1.id`, `email == EE`, `status == "pending"`.
3. count: invitations(W1) with `status == "pending"` has exactly 2 rows.

### WSMG-CI-52 — members and invitations of an earlier workspace hold none of W1's seats
- **Rules:** `create_invitation` R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. limit 2
2. Z1 = member(UB), but `workspace_id W0.id`.
3. Z2 = member(UC), but `workspace_id W0.id`.
4. J = invitation J to ED, but `workspace_id W0.id`.
5. K = invitation K to f"fay.{TAG}@acme.com", but `workspace_id W0.id`.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=EE, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. re-read the returned row: `workspace_id == W1.id`, `email == EE`, `status == "pending"`.
3. count: invitations(W1) with `status == "pending"` has exactly 1 rows.

### WSMG-CI-53 — members and invitations of a later workspace hold none of W1's seats
- **Rules:** `create_invitation` R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. limit 2
2. Z1 = member(UB), but `workspace_id W2.id`.
3. Z2 = member(UC), but `workspace_id W2.id`.
4. J = invitation J to ED, but `workspace_id W2.id`.
5. K = invitation K to f"fay.{TAG}@acme.com", but `workspace_id W2.id`.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=EE, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. re-read the returned row: `workspace_id == W1.id`, `email == EE`, `status == "pending"`.
3. count: invitations(W1) with `status == "pending"` has exactly 1 rows.

### WSMG-CI-54 — two pending invitations to one email hold two seats
- **Rules:** `create_invitation` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 3
2. J = invitation J to ED.
3. K = invitation K to ED.

**When**
- `M.create_invitation(db, workspace_id=W1.id, email=EE, role="member", inviter_id=UO.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Workspace has reached maximum member limit (3). Upgrade subscription to add more members."`.
3. nothing written.

### WSMG-CI-55 — a limit of -1 means no limit
- **Rules:** `create_invitation` R8 [BUG-1871]
- **Kind:** bug
- **Expect:** xfail BUG-1871
- **Fails today on:** Then 1 (the call raises ValueError "…limit (-1)…")

**Given**
1. limit -1
2. B = member(UB).
3. J = invitation J to ED.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=EE, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. re-read the returned row: `workspace_id == W1.id`, `email == EE`, `status == "pending"`.
3. count: invitations(W1) with `status == "pending"` has exactly 2 rows.

### WSMG-CI-56 — a limit of -5 means no limit
- **Rules:** `create_invitation` R8 [BUG-1871]
- **Kind:** bug
- **Expect:** xfail BUG-1871
- **Fails today on:** Then 1 (the call raises ValueError "…limit (-5)…")

**Given**
1. limit -5

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=EE, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. re-read the returned row: `workspace_id == W1.id`, `email == EE`, `status == "pending"`.
3. count: invitations(W1) with `status == "pending"` has exactly 1 rows.

### WSMG-CI-57 — one invitation_sent audit row carries the email as given
- **Rules:** `create_invitation` R13; A1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=f"Dan.{TAG}@Acme.COM", role="viewer", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. audit: audit(W1) has exactly 1 row.
3. audit: that row: `user_id == UO.id`, `action == "invitation_sent"`, `metadata_json == {"email": f"Dan.{TAG}@Acme.COM", "role": "viewer"}`.
4. audit: that row: `resource_type is None`, `resource_id is None`, `ip_address is None`, `user_agent is None`.

### WSMG-CI-58 — with no inviter the invitation and the audit row carry no actor
- **Rules:** `create_invitation` R10, R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=ED, role="member", inviter_id=None)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `invited_by_user_id is None`.
3. audit: audit(W1) has exactly 1 row.
4. audit: that row: `user_id is None`, `action == "invitation_sent"`.

### WSMG-CI-59 — create_invitation flushes and never commits
- **Rules:** `create_invitation` Returns; Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=ED, role="member", inviter_id=UO.id)`. Rolled back.

**Then**
1. returns: `result.id is not None` (inside).
2. count: invitations(W1) has exactly 1 row (inside).
3. mock called: `cm.call_count == 0`.
4. count: invitations(W1) has exactly 0 rows (after the savepoint rollback).

### WSMG-CI-60 — the audit row carries the request's IP address and user agent
- **Rules:** A2 [BUG-1404]; `create_invitation` R13
- **Kind:** bug
- **Expect:** xfail BUG-1404
- **Fails today on:** Then 1 (the call raises TypeError: no `ip_address` parameter)

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=ED, role="member", inviter_id=UO.id, ip_address="203.0.113.7", user_agent="Mozilla/5.0 Test")`.

**Then**
1. returns: `result.id is not None`.
2. audit: audit(W1) has exactly 1 row.
3. audit: that row: `ip_address == "203.0.113.7"`, `user_agent == "Mozilla/5.0 Test"`.
## `WorkspaceManager.validate_invitation_for_user`

### WSMG-VI-01 — a pending, unexpired invitation for this email is returned unchanged
- **Rules:** `validate_invitation_for_user` R1–R6, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. I = invitation I to EA.

**When**
- `result = M.validate_invitation_for_user(db, invitation_token=f"tok-I-{TAG}", user_email=EA)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. returns: `result.id == I.id`.
3. unchanged: unchanged(I).
4. nothing written.

### WSMG-VI-02 — validation writes nothing and leaves the caller's pending row alone
- **Rules:** `validate_invitation_for_user` R6; Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I = invitation I to EA.
2. `P = Department(workspace_id=W1.id, name="Spare")`; `db.add(P)` (not flushed).

**When**
- `result = M.validate_invitation_for_user(db, invitation_token=f"tok-I-{TAG}", user_email=EA)`.

**Then**
1. returns: `result.id == I.id`.
2. session: `len(db.new) == 1`.
3. session: `P in db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.

### WSMG-VI-03 — an unknown token is refused
- **Rules:** `validate_invitation_for_user` R1; Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to EA.

**When**
- `M.validate_invitation_for_user(db, invitation_token=f"tok-X-{TAG}", user_email=EA)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invalid invitation token"`.
3. unchanged: unchanged(I).

### WSMG-VI-04 — the token in capitals is unknown
- **Rules:** `validate_invitation_for_user` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I = invitation I to EA.

**When**
- `M.validate_invitation_for_user(db, invitation_token=f"tok-I-{TAG}".upper(), user_email=EA)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invalid invitation token"`.

### WSMG-VI-05 — the token with a leading space is unknown
- **Rules:** `validate_invitation_for_user` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I = invitation I to EA.

**When**
- `M.validate_invitation_for_user(db, invitation_token=" " + f"tok-I-{TAG}", user_email=EA)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invalid invitation token"`.

### WSMG-VI-06 — an invitation of another workspace is found by its token alone
- **Rules:** `validate_invitation_for_user` R1, R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `workspace_id W2.id`.

**When**
- `result = M.validate_invitation_for_user(db, invitation_token=f"tok-I-{TAG}", user_email=EA)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. returns: `result.id == I.id`.
3. returns: `result.workspace_id == W2.id`.

### WSMG-VI-07 — an invitation that expired a microsecond ago is refused
- **Rules:** `validate_invitation_for_user` R2; Errors row 2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `expires_at NOW - US`.

**When**
- `M.validate_invitation_for_user(db, invitation_token=f"tok-I-{TAG}", user_email=EA)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invitation has expired. Please request a new invitation."`.
3. unchanged: unchanged(I).

### WSMG-VI-08 — an invitation expiring exactly now is expired
- **Rules:** `validate_invitation_for_user` R2 [BUG-1987]
- **Kind:** bug
- **Expect:** xfail BUG-1987
- **Fails today on:** Then 1 (no error is raised today: only `expires_at < now` is refused)

**Given**
1. I = invitation I to EA, but `expires_at NOW`.

**When**
- `M.validate_invitation_for_user(db, invitation_token=f"tok-I-{TAG}", user_email=EA)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invitation has expired. Please request a new invitation."`.

### WSMG-VI-09 — an invitation expiring a microsecond from now passes
- **Rules:** `validate_invitation_for_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `expires_at NOW + US`.

**When**
- `result = M.validate_invitation_for_user(db, invitation_token=f"tok-I-{TAG}", user_email=EA)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. returns: `result.id == I.id`.

### WSMG-VI-10 — an accepted invitation that has also expired gets the expiry message
- **Rules:** `validate_invitation_for_user` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `status "accepted"`, `expires_at NOW - DAY`.

**When**
- `M.validate_invitation_for_user(db, invitation_token=f"tok-I-{TAG}", user_email=EA)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invitation has expired. Please request a new invitation."`.

### WSMG-VI-11 — a cancelled invitation that has also expired gets the expiry message
- **Rules:** `validate_invitation_for_user` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `status "cancelled"`, `expires_at NOW - DAY`.

**When**
- `M.validate_invitation_for_user(db, invitation_token=f"tok-I-{TAG}", user_email=EA)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invitation has expired. Please request a new invitation."`.

### WSMG-VI-12 — an unexpired invitation with status `"accepted"` is refused with its status
- **Rules:** `validate_invitation_for_user` R4; Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `status "accepted"`.

**When**
- `M.validate_invitation_for_user(db, invitation_token=f"tok-I-{TAG}", user_email=EA)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invitation has already been accepted"`.
3. unchanged: unchanged(I).

### WSMG-VI-13 — an unexpired invitation with status `"cancelled"` is refused with its status
- **Rules:** `validate_invitation_for_user` R4; Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `status "cancelled"`.

**When**
- `M.validate_invitation_for_user(db, invitation_token=f"tok-I-{TAG}", user_email=EA)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invitation has already been cancelled"`.
3. unchanged: unchanged(I).

### WSMG-VI-14 — an unexpired invitation with status `"expired"` is refused with its status
- **Rules:** `validate_invitation_for_user` R4; Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `status "expired"`.

**When**
- `M.validate_invitation_for_user(db, invitation_token=f"tok-I-{TAG}", user_email=EA)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invitation has already been expired"`.
3. unchanged: unchanged(I).

### WSMG-VI-15 — an unexpired invitation with status `"Pending"` is refused with its status
- **Rules:** `validate_invitation_for_user` R4; Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `status "Pending"`.

**When**
- `M.validate_invitation_for_user(db, invitation_token=f"tok-I-{TAG}", user_email=EA)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invitation has already been Pending"`.
3. unchanged: unchanged(I).

### WSMG-VI-16 — another person's email is refused, naming both emails
- **Rules:** `validate_invitation_for_user` R5; Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to EA.

**When**
- `M.validate_invitation_for_user(db, invitation_token=f"tok-I-{TAG}", user_email=EB)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == f"This invitation was sent to {EA}. You cannot accept it with {EB}."`.
3. unchanged: unchanged(I).

### WSMG-VI-17 — the same email in other capitals passes
- **Rules:** `validate_invitation_for_user` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I = invitation I to EA.

**When**
- `result = M.validate_invitation_for_user(db, invitation_token=f"tok-I-{TAG}", user_email=f"ANN.{TAG.upper()}@ACME.COM")`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. returns: `result.id == I.id`.

### WSMG-VI-18 — a stored email in mixed capitals matches the lower-case email
- **Rules:** `validate_invitation_for_user` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I = invitation I to `f"Ann.{TAG}@Acme.com"`.

**When**
- `result = M.validate_invitation_for_user(db, invitation_token=f"tok-I-{TAG}", user_email=EA)`.

**Then**
1. returns: `isinstance(result, WorkspaceInvitation)`.
2. returns: `result.id == I.id`.

### WSMG-VI-19 — surrounding spaces are not removed from the user's email
- **Rules:** `validate_invitation_for_user` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I = invitation I to EA.

**When**
- `M.validate_invitation_for_user(db, invitation_token=f"tok-I-{TAG}", user_email=" " + EA)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == f"This invitation was sent to {EA}. You cannot accept it with  {EA}."`.

### WSMG-VI-20 — part of the invited email does not match
- **Rules:** `validate_invitation_for_user` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I = invitation I to EA.

**When**
- `M.validate_invitation_for_user(db, invitation_token=f"tok-I-{TAG}", user_email=f"nn.{TAG}@acme.com")`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == f"This invitation was sent to {EA}. You cannot accept it with nn.{TAG}@acme.com."`.

### WSMG-VI-21 — the status is checked before the email
- **Rules:** `validate_invitation_for_user` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `status "accepted"`.

**When**
- `M.validate_invitation_for_user(db, invitation_token=f"tok-I-{TAG}", user_email=EB)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invitation has already been accepted"`.

### WSMG-VI-22 — expiry is checked before the email
- **Rules:** `validate_invitation_for_user` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `expires_at NOW - DAY`.

**When**
- `M.validate_invitation_for_user(db, invitation_token=f"tok-I-{TAG}", user_email=EB)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invitation has expired. Please request a new invitation."`.
## `WorkspaceManager.accept_invitation`

### WSMG-AI-01 — accepting makes the user a member with the invitation's role and position
- **Rules:** `accept_invitation` R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `role "manager"`, `position "Lead"`.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceMember)`.
2. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `status == "active"`.
3. re-read the returned row: `role == "manager"`, `position == "Lead"`, `joined_at == NOW`, `left_at is None`.
4. count: members(W1, UA) has exactly 1 row.

### WSMG-AI-02 — the invitation is marked accepted by the user, nothing else changes on it
- **Rules:** `accept_invitation` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `role "manager"`, `position "Lead"`.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read I: `status == "accepted"`, `accepted_at == NOW`, `accepted_by_user_id == UA.id`.
3. unchanged: unchanged(I) except `status`, `accepted_at`, `accepted_by_user_id`.

### WSMG-AI-03 — a successful accept writes member_added and invitation_accepted
- **Rules:** `accept_invitation` R3, R6; A1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `role "manager"`, `position "Lead"`.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. audit: audit(W1) has exactly 2 rows.
3. audit: audit(W1, "member_added") has exactly 1 row.
4. audit: that row: `user_id == UO.id`, `metadata_json == {"new_member_id": UA.id, "role": "manager"}`.
5. audit: audit(W1, "invitation_accepted") has exactly 1 row.
6. audit: that row: `user_id == UA.id`, `metadata_json == {"invitation_id": I.id}`.
7. audit: that row: `resource_type is None`, `resource_id is None`, `ip_address is None`, `user_agent is None`.

### WSMG-AI-04 — an unknown invitation id is refused and nothing is written
- **Rules:** `accept_invitation` R1; Errors row 1; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.accept_invitation(db, invitation_id=MISSING, user_id=UA.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invitation not found"`.
3. nothing written.

### WSMG-AI-05 — an already accepted invitation is not checked here and still adds the user
- **Rules:** `accept_invitation` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `status "accepted"`.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceMember)`.
2. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `status == "active"`.
3. re-read I: `status == "accepted"`, `accepted_by_user_id == UA.id`.

### WSMG-AI-06 — a cancelled invitation is not checked here and still adds the user
- **Rules:** `accept_invitation` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `status "cancelled"`.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceMember)`.
2. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `status == "active"`.
3. re-read I: `status == "accepted"`, `accepted_by_user_id == UA.id`.

### WSMG-AI-07 — an expired invitation is not checked here and still adds the user
- **Rules:** `accept_invitation` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `expires_at NOW - DAY`.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceMember)`.
2. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `status == "active"`.
3. re-read I: `status == "accepted"`, `accepted_by_user_id == UA.id`.

### WSMG-AI-08 — the member is added to the invitation's own workspace
- **Rules:** `accept_invitation` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `workspace_id W2.id`.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `result.workspace_id == W2.id`.
2. count: members(W2, UA) has exactly 1 row.
3. count: members(W1, UA) has exactly 0 rows.
4. audit: audit(W2) has exactly 2 rows.
5. audit: audit(W1) has exactly 0 rows.

### WSMG-AI-09 — an invitation with no inviter adds a member with no actor
- **Rules:** `accept_invitation` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I = invitation I to EA, but `invited_by_user_id None`.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceMember)`.
2. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `status == "active"`.
3. re-read the returned row: `invited_by_user_id is None`.
4. audit: audit(W1, "member_added") has exactly 1 row.
5. audit: that row: `user_id is None`.

### WSMG-AI-10 — the new member row records the invitation's inviter
- **Rules:** `accept_invitation` R3 [BUG-1985]
- **Kind:** bug
- **Expect:** xfail BUG-1985
- **Fails today on:** Then 2 (`invited_by_user_id` is NULL today)

**Given**
1. I = invitation I to EA.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `invited_by_user_id == UO.id`.

### WSMG-AI-11 — an active member cannot accept; the invitation is left unchanged
- **Rules:** `accept_invitation` R3; Errors row 2; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = member(UA).
2. I = invitation I to EA.

**When**
- `M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "User is already a member of this workspace"`.
3. unchanged: unchanged(I).
4. unchanged: unchanged(A).
5. nothing written.

### WSMG-AI-12 — a full workspace refuses the accept; the invitation is left unchanged
- **Rules:** `accept_invitation` R3; Errors row 2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 2
2. B = member(UB).
3. I = invitation I to EA.

**When**
- `M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Workspace has reached maximum member limit (2). Upgrade subscription to add more members."`.
3. unchanged: unchanged(I).
4. nothing written.

### WSMG-AI-13 — pending invitations do not take a seat at accept
- **Rules:** `accept_invitation` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 3
2. B = member(UB).
3. I = invitation I to EA.
4. J = invitation J to ED.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceMember)`.
2. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `status == "active"`.
3. count: `workspace_members` with `workspace_id == W1.id` and `status == "active"` has exactly 3 rows.
4. unchanged: unchanged(J).

### WSMG-AI-14 — a limit of -1 does not refuse the accept
- **Rules:** `accept_invitation` R3 [BUG-1872]
- **Kind:** bug
- **Expect:** xfail BUG-1872
- **Fails today on:** Then 1 (the call raises ValueError "…limit (-1)…")

**Given**
1. limit -1
2. B = member(UB).
3. C = member(UC).
4. I = invitation I to EA.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceMember)`.
2. re-read the returned row: `workspace_id == W1.id`, `user_id == UA.id`, `status == "active"`.

### WSMG-AI-15 — a removed member who accepts gets their old row back
- **Rules:** `accept_invitation` R3 [BUG-1982]
- **Kind:** bug
- **Expect:** xfail BUG-1982
- **Fails today on:** Then 1 (the call raises ValueError "User is already a member of this workspace")

**Given**
1. A = member(UA), but `role "viewer"`, `status "inactive"`, `joined_at T1`, `left_at T2`.
2. I = invitation I to EA, but `role "manager"`, `position "Lead"`.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `result.id == A.id`.
2. re-read A: `status == "active"`, `role == "manager"`, `position == "Lead"`, `left_at is None`.
3. count: members(W1, UA) has exactly 1 row.
4. re-read I: `status == "accepted"`.

### WSMG-AI-16 — another pending invitation to the same email is cancelled as superseded
- **Rules:** `accept_invitation` R5 [BUG-1874]
- **Kind:** bug
- **Expect:** xfail BUG-1874
- **Fails today on:** Then 2 (J stays pending today)

**Given**
1. J = invitation J to EA.
2. I = invitation I to EA.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read J: `status == "cancelled"`.
3. audit: audit(W1, "invitation_cancelled") has exactly 1 row.
4. audit: that row: `user_id == UA.id`, `metadata_json == {"invitation_id": J.id, "email": EA, "reason": "superseded"}`.
5. audit: audit(W1) has exactly 3 rows.

### WSMG-AI-17 — an expired pending invitation to the same email is cancelled too
- **Rules:** `accept_invitation` R5 [BUG-1874]
- **Kind:** bug
- **Expect:** xfail BUG-1874
- **Fails today on:** Then 2 (K stays pending today)

**Given**
1. I = invitation I to EA.
2. K = invitation K to EA, but `expires_at NOW - DAY`.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read K: `status == "cancelled"`.

### WSMG-AI-18 — a pending invitation to the same email in other capitals is cancelled
- **Rules:** `accept_invitation` R5 [BUG-1874]
- **Kind:** bug
- **Expect:** xfail BUG-1874
- **Fails today on:** Then 2 (K stays pending today)

**Given**
1. I = invitation I to EA.
2. K = invitation K to `f"Ann.{TAG}@Acme.com"`.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read K: `status == "cancelled"`.
3. audit: audit(W1, "invitation_cancelled") has exactly 1 row.
4. audit: that row: `user_id == UA.id`, `metadata_json == {"invitation_id": K.id, "email": f"Ann.{TAG}@Acme.com", "reason": "superseded"}`.

### WSMG-AI-19 — a pending invitation to the same email in an earlier workspace is not touched
- **Rules:** `accept_invitation` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. J = invitation J to EA, but `workspace_id W0.id`.
2. I = invitation I to EA.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. unchanged: unchanged(J).
3. audit: audit(W0) has exactly 0 rows.

### WSMG-AI-20 — a pending invitation to the same email in a later workspace is not touched
- **Rules:** `accept_invitation` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. J = invitation J to EA, but `workspace_id W2.id`.
2. I = invitation I to EA.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. unchanged: unchanged(J).
3. audit: audit(W2) has exactly 0 rows.

### WSMG-AI-21 — a pending invitation to another email is not touched
- **Rules:** `accept_invitation` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. J = invitation J to EB.
2. I = invitation I to EA.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. unchanged: unchanged(J).
3. audit: audit(W1, "invitation_cancelled") has exactly 0 rows.

### WSMG-AI-22 — accepted and cancelled invitations to the same email are not touched
- **Rules:** `accept_invitation` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. J = invitation J to EA, but `status "accepted"`.
2. K = invitation K to EA, but `status "cancelled"`.
3. I = invitation I to EA.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. unchanged: unchanged(J).
3. unchanged: unchanged(K).
4. audit: audit(W1, "invitation_cancelled") has exactly 0 rows.

### WSMG-AI-23 — an unknown user fails at the member insert; the invitation stays pending
- **Rules:** `accept_invitation` R3 (add R10)
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to EA.

**When**
- `M.accept_invitation(db, invitation_id=I.id, user_id=MISSING)`, inside the wrap of `raises: IntegrityError on flush`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. re-read I: `status == "pending"`, `accepted_at is None`, `accepted_by_user_id is None`.

### WSMG-AI-24 — accept flushes and never commits
- **Rules:** `accept_invitation` Returns; Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I = invitation I to EA.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`. Rolled back.

**Then**
1. returns: `result.id is not None` (inside).
2. count: members(W1, UA) has exactly 1 row (inside).
3. mock called: `cm.call_count == 0`.
4. count: members(W1, UA) has exactly 0 rows (after the savepoint rollback).
5. re-read I: `status == "pending"` (after the savepoint rollback).

### WSMG-AI-25 — both audit rows carry the request's IP address and user agent
- **Rules:** A2 [BUG-1404]; `accept_invitation` R6
- **Kind:** bug
- **Expect:** xfail BUG-1404
- **Fails today on:** Then 1 (the call raises TypeError: no `ip_address` parameter)

**Given**
1. I = invitation I to EA.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id, ip_address="203.0.113.7", user_agent="Mozilla/5.0 Test")`.

**Then**
1. returns: `result.id is not None`.
2. audit: audit(W1) has exactly 2 rows.
3. audit: every row of audit(W1): `ip_address == "203.0.113.7"`, `user_agent == "Mozilla/5.0 Test"`.

### WSMG-AI-26 — the accept writes member_added before invitation_accepted
- **Rules:** `accept_invitation` R6a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I = invitation I to EA.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. audit: `[r.action for r in audit(W1)] == ["member_added", "invitation_accepted"]`.

### WSMG-AI-27 — superseded invitations are logged after the acceptance, by ascending invitation id
- **Rules:** `accept_invitation` R6a, R5 [BUG-1874]
- **Kind:** bug
- **Expect:** xfail BUG-1874
- **Fails today on:** Then 2 (only the two standard rows are written today)

**Given**
1. J = invitation J to EA.
2. I = invitation I to EA.
3. K = invitation K to EA.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. audit: `[r.action for r in audit(W1)] == ["member_added", "invitation_accepted", "invitation_cancelled", "invitation_cancelled"]`.
3. audit: `[r.metadata_json["invitation_id"] for r in audit(W1, "invitation_cancelled")] == [J.id, K.id]`.

### WSMG-AI-28 — every audit row of an accept, the superseded ones included, carries IP address and user agent
- **Rules:** `accept_invitation` R6a; A2 [BUG-1404]; R5 [BUG-1874]
- **Kind:** bug
- **Expect:** xfail BUG-1404
- **Fails today on:** Then 1 (the call raises TypeError: no `ip_address` parameter; BUG-1874 must also be fixed for Then 2)

**Given**
1. I = invitation I to EA.
2. J = invitation J to EA.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id, ip_address="203.0.113.7", user_agent="Mozilla/5.0 Test")`.

**Then**
1. returns: `result.id is not None`.
2. audit: audit(W1) has exactly 3 rows.
3. audit: every row of audit(W1): `ip_address == "203.0.113.7"`, `user_agent == "Mozilla/5.0 Test"`.

## `WorkspaceManager.cancel_invitation`

### WSMG-XI-01 — the owner cancels a pending invitation; only its status changes
- **Rules:** `cancel_invitation` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. I = invitation I to ED.

**When**
- `result = M.cancel_invitation(db, invitation_id=I.id, canceller_id=UO.id, canceller_role="owner", workspace_id=W1.id)`.

**Then**
1. re-read I: `status == "cancelled"`.
2. unchanged: unchanged(I) except `status`.
3. returns: `result is None`.

### WSMG-XI-02 — one invitation_cancelled audit row names the invitation and its email
- **Rules:** `cancel_invitation` R6; A1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I = invitation I to ED.

**When**
- `result = M.cancel_invitation(db, invitation_id=I.id, canceller_id=UO.id, canceller_role="owner", workspace_id=W1.id)`.

**Then**
1. audit: audit(W1) has exactly 1 row.
2. audit: that row: `user_id == UO.id`, `action == "invitation_cancelled"`, `metadata_json == {"invitation_id": I.id, "email": ED}`.
3. audit: that row: `resource_type is None`, `resource_id is None`, `ip_address is None`, `user_agent is None`.
4. returns: `result is None`.

### WSMG-XI-03 — an expired pending invitation can still be cancelled
- **Rules:** `cancel_invitation` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I = invitation I to ED, but `expires_at NOW - DAY`.

**When**
- `result = M.cancel_invitation(db, invitation_id=I.id, canceller_id=UO.id, canceller_role="owner", workspace_id=W1.id)`.

**Then**
1. re-read I: `status == "cancelled"`.
2. audit: audit(W1) has exactly 1 row.
3. returns: `result is None`.

### WSMG-XI-04 — an invitation with status `"accepted"` cannot be cancelled
- **Rules:** `cancel_invitation` R3; Errors row 3; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to ED, but `status "accepted"`.

**When**
- `M.cancel_invitation(db, invitation_id=I.id, canceller_id=UO.id, canceller_role="owner", workspace_id=W1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Cannot cancel invitation that is accepted"`.
3. unchanged: unchanged(I).
4. nothing written.

### WSMG-XI-05 — an invitation with status `"cancelled"` cannot be cancelled
- **Rules:** `cancel_invitation` R3; Errors row 3; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to ED, but `status "cancelled"`.

**When**
- `M.cancel_invitation(db, invitation_id=I.id, canceller_id=UO.id, canceller_role="owner", workspace_id=W1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Cannot cancel invitation that is cancelled"`.
3. unchanged: unchanged(I).
4. nothing written.

### WSMG-XI-06 — an invitation with status `"Pending"` cannot be cancelled
- **Rules:** `cancel_invitation` R3; Errors row 3; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to ED, but `status "Pending"`.

**When**
- `M.cancel_invitation(db, invitation_id=I.id, canceller_id=UO.id, canceller_role="owner", workspace_id=W1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Cannot cancel invitation that is Pending"`.
3. unchanged: unchanged(I).
4. nothing written.

### WSMG-XI-07 — an unknown invitation id is refused
- **Rules:** `cancel_invitation` R2; Errors row 2; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to ED.

**When**
- `M.cancel_invitation(db, invitation_id=MISSING, canceller_id=UO.id, canceller_role="owner", workspace_id=W1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invitation not found"`.
3. unchanged: unchanged(I).
4. nothing written.

### WSMG-XI-08 — an invitation of a later workspace answers as not found
- **Rules:** `cancel_invitation` R2 [BUG-1981] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-1981
- **Fails today on:** Then 2 (today the message is "Invitation does not belong to this workspace")

**Given**
1. J = invitation J to ED, but `workspace_id W2.id`.

**When**
- `M.cancel_invitation(db, invitation_id=J.id, canceller_id=UO.id, canceller_role="owner", workspace_id=W1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invitation not found"`.
3. unchanged: unchanged(J).
4. nothing written.

### WSMG-XI-09 — an invitation of a later workspace is refused and left unchanged
- **Rules:** `cancel_invitation` R2 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. J = invitation J to ED, but `workspace_id W2.id`.

**When**
- `M.cancel_invitation(db, invitation_id=J.id, canceller_id=UO.id, canceller_role="owner", workspace_id=W1.id)`.

**Then**
1. raises: `ValueError` (the message is checked in the BUG-1981 card).
2. unchanged: unchanged(J).
3. nothing written.

### WSMG-XI-10 — an invitation of an earlier workspace answers as not found
- **Rules:** `cancel_invitation` R2 [BUG-1981] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-1981
- **Fails today on:** Then 2 (today the message is "Invitation does not belong to this workspace")

**Given**
1. J = invitation J to ED, but `workspace_id W0.id`.

**When**
- `M.cancel_invitation(db, invitation_id=J.id, canceller_id=UO.id, canceller_role="owner", workspace_id=W1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Invitation not found"`.
3. unchanged: unchanged(J).
4. nothing written.

### WSMG-XI-11 — an invitation of an earlier workspace is refused and left unchanged
- **Rules:** `cancel_invitation` R2 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. J = invitation J to ED, but `workspace_id W0.id`.

**When**
- `M.cancel_invitation(db, invitation_id=J.id, canceller_id=UO.id, canceller_role="owner", workspace_id=W1.id)`.

**Then**
1. raises: `ValueError` (the message is checked in the BUG-1981 card).
2. unchanged: unchanged(J).
3. nothing written.

### WSMG-XI-12 — the role `"manager"` may not cancel
- **Rules:** `cancel_invitation` R1; Errors row 1; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to ED.
2. R = member(UB), but `role "manager"`.

**When**
- `M.cancel_invitation(db, invitation_id=I.id, canceller_id=UB.id, canceller_role="manager", workspace_id=W1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Only the workspace owner can cancel invitations"`.
3. unchanged: unchanged(I).
4. nothing written.

### WSMG-XI-13 — the role `"member"` may not cancel
- **Rules:** `cancel_invitation` R1; Errors row 1; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to ED.
2. R = member(UB), but `role "member"`.

**When**
- `M.cancel_invitation(db, invitation_id=I.id, canceller_id=UB.id, canceller_role="member", workspace_id=W1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Only the workspace owner can cancel invitations"`.
3. unchanged: unchanged(I).
4. nothing written.

### WSMG-XI-14 — the role `"viewer"` may not cancel
- **Rules:** `cancel_invitation` R1; Errors row 1; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to ED.
2. R = member(UB), but `role "viewer"`.

**When**
- `M.cancel_invitation(db, invitation_id=I.id, canceller_id=UB.id, canceller_role="viewer", workspace_id=W1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Only the workspace owner can cancel invitations"`.
3. unchanged: unchanged(I).
4. nothing written.

### WSMG-XI-15 — the role `"ground-team"` may not cancel
- **Rules:** `cancel_invitation` R1; Errors row 1; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to ED.
2. R = member(UB), but `role "ground-team"`.

**When**
- `M.cancel_invitation(db, invitation_id=I.id, canceller_id=UB.id, canceller_role="ground-team", workspace_id=W1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Only the workspace owner can cancel invitations"`.
3. unchanged: unchanged(I).
4. nothing written.

### WSMG-XI-16 — the role `"ground-team-manager"` may not cancel
- **Rules:** `cancel_invitation` R1; Errors row 1; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to ED.
2. R = member(UB), but `role "ground-team-manager"`.

**When**
- `M.cancel_invitation(db, invitation_id=I.id, canceller_id=UB.id, canceller_role="ground-team-manager", workspace_id=W1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Only the workspace owner can cancel invitations"`.
3. unchanged: unchanged(I).
4. nothing written.

### WSMG-XI-17 — the role `"finance"` may not cancel
- **Rules:** `cancel_invitation` R1; Errors row 1; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to ED.
2. R = member(UB), but `role "finance"`.

**When**
- `M.cancel_invitation(db, invitation_id=I.id, canceller_id=UB.id, canceller_role="finance", workspace_id=W1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Only the workspace owner can cancel invitations"`.
3. unchanged: unchanged(I).
4. nothing written.

### WSMG-XI-18 — the role `"Owner"` may not cancel
- **Rules:** `cancel_invitation` R1; Errors row 1; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to ED.
2. R = member(UB), but `role "Owner"`.

**When**
- `M.cancel_invitation(db, invitation_id=I.id, canceller_id=UB.id, canceller_role="Owner", workspace_id=W1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Only the workspace owner can cancel invitations"`.
3. unchanged: unchanged(I).
4. nothing written.

### WSMG-XI-19 — the role `""` may not cancel
- **Rules:** `cancel_invitation` R1; Errors row 1; A3
- **Kind:** error
- **Expect:** pass

**Given**
1. I = invitation I to ED.
2. R = member(UB), but `role ""`.

**When**
- `M.cancel_invitation(db, invitation_id=I.id, canceller_id=UB.id, canceller_role="", workspace_id=W1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Only the workspace owner can cancel invitations"`.
3. unchanged: unchanged(I).
4. nothing written.

### WSMG-XI-20 — a non-owner asking about an unknown id gets the owner message
- **Rules:** `cancel_invitation` R1 [BUG-1986]
- **Kind:** bug
- **Expect:** xfail BUG-1986
- **Fails today on:** Then 2 (today the message is "Invitation not found")

**Given**
1. R = member(UB).

**When**
- `M.cancel_invitation(db, invitation_id=MISSING, canceller_id=UB.id, canceller_role="member", workspace_id=W1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Only the workspace owner can cancel invitations"`.
3. nothing written.

### WSMG-XI-21 — a non-owner asking about another workspace's invitation gets the owner message
- **Rules:** `cancel_invitation` R1 [BUG-1986]
- **Kind:** bug
- **Expect:** xfail BUG-1986
- **Fails today on:** Then 2 (today the message is "Invitation does not belong to this workspace")

**Given**
1. R = member(UB).
2. J = invitation J to ED, but `workspace_id W2.id`.

**When**
- `M.cancel_invitation(db, invitation_id=J.id, canceller_id=UB.id, canceller_role="member", workspace_id=W1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Only the workspace owner can cancel invitations"`.
3. unchanged: unchanged(J).
4. nothing written.

### WSMG-XI-22 — a non-owner asking about an accepted invitation gets the owner message
- **Rules:** `cancel_invitation` R1 [BUG-1986]
- **Kind:** bug
- **Expect:** xfail BUG-1986
- **Fails today on:** Then 2 (today the message is "Cannot cancel invitation that is accepted")

**Given**
1. R = member(UB).
2. I = invitation I to ED, but `status "accepted"`.

**When**
- `M.cancel_invitation(db, invitation_id=I.id, canceller_id=UB.id, canceller_role="member", workspace_id=W1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Only the workspace owner can cancel invitations"`.
3. unchanged: unchanged(I).
4. nothing written.

### WSMG-XI-23 — owner of an earlier workspace, member here: may not cancel
- **Rules:** `cancel_invitation` R1 (grant held in another workspace)
- **Kind:** error
- **Expect:** pass

**Given**
1. Z = member(UB), but `workspace_id W0.id`, `role "owner"`.
2. R = member(UB).
3. I = invitation I to ED.

**When**
- `M.cancel_invitation(db, invitation_id=I.id, canceller_id=UB.id, canceller_role="member", workspace_id=W1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Only the workspace owner can cancel invitations"`.
3. unchanged: unchanged(I).
4. nothing written.

### WSMG-XI-24 — owner of a later workspace, member here: may not cancel
- **Rules:** `cancel_invitation` R1 (grant held in another workspace)
- **Kind:** error
- **Expect:** pass

**Given**
1. R = member(UB).
2. I = invitation I to ED.
3. Z = member(UB), but `workspace_id W2.id`, `role "owner"`.

**When**
- `M.cancel_invitation(db, invitation_id=I.id, canceller_id=UB.id, canceller_role="member", workspace_id=W1.id)`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Only the workspace owner can cancel invitations"`.
3. unchanged: unchanged(I).
4. nothing written.

### WSMG-XI-25 — cancel flushes and never commits
- **Rules:** `cancel_invitation` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I = invitation I to ED.

**When**
- `result = M.cancel_invitation(db, invitation_id=I.id, canceller_id=UO.id, canceller_role="owner", workspace_id=W1.id)`. Rolled back.

**Then**
1. re-read I: `status == "cancelled"` (inside).
2. mock called: `cm.call_count == 0`.
3. re-read I: `status == "pending"` (after the savepoint rollback).
4. returns: `result is None`.

### WSMG-XI-26 — the audit row carries the request's IP address and user agent
- **Rules:** A2 [BUG-1404]; `cancel_invitation` R6
- **Kind:** bug
- **Expect:** xfail BUG-1404
- **Fails today on:** Then 1 (the call raises TypeError: no `ip_address` parameter)

**Given**
1. I = invitation I to ED.

**When**
- `M.cancel_invitation(db, invitation_id=I.id, canceller_id=UO.id, canceller_role="owner", workspace_id=W1.id, ip_address="203.0.113.7", user_agent="Mozilla/5.0 Test")`.

**Then**
1. audit: audit(W1) has exactly 1 row.
2. audit: that row: `ip_address == "203.0.113.7"`, `user_agent == "Mozilla/5.0 Test"`.

### WSMG-XI-27 — the audit row carries the invitation's email exactly as stored, capitals kept
- **Rules:** `cancel_invitation` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I = invitation I to `f"Dan.{TAG}@Acme.com"`.

**When**
- `result = M.cancel_invitation(db, invitation_id=I.id, canceller_id=UO.id, canceller_role="owner", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. re-read I: `status == "cancelled"`, `email == f"Dan.{TAG}@Acme.com"`.
3. audit: audit(W1) has exactly 1 row.
4. audit: that row: `metadata_json == {"invitation_id": I.id, "email": f"Dan.{TAG}@Acme.com"}`.

## Pending the payment portal — OQ-16 (`create_workspace_with_owner` R1)

> Today's behaviour, kept in its own cards: a new workspace may start on any active plan, unpaid. When the portal decides OQ-16, only the cards of this section change.

### WSMG-P16-01 — an active non-default plan asked for at creation is used, unpaid
- **Rules:** `create_workspace_with_owner` R1 (pending OQ-16)
- **Kind:** happy
- **Expect:** pass

**Given**
1. PD.
2. PX.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id, subscription_plan_id=PX.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new workspace: `subscription_plan_id == PX.id`.
3. audit: audit(the new workspace) has exactly 1 row.
4. audit: that row: `metadata_json == {"plan": f"pro-{TAG}"}`.

### WSMG-P16-02 — the unlimited enterprise plan can be picked at creation and still starts a trial
- **Rules:** `create_workspace_with_owner` R1 (pending OQ-16), R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. PD.
2. PE.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id, subscription_plan_id=PE.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new workspace: `subscription_plan_id == PE.id`.
3. re-read the new workspace: `subscription_status == "trial"`, `trial_ends_at == NOW + timedelta(days=14)`.

### WSMG-P16-03 — the default plan's own id given explicitly is used
- **Rules:** `create_workspace_with_owner` R1 (pending OQ-16)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PX.
2. PD.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id, subscription_plan_id=PD.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new workspace: `subscription_plan_id == PD.id`.

### WSMG-P16-04 — an explicit active plan works with no default plan at all
- **Rules:** `create_workspace_with_owner` R1 (pending OQ-16), R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PX.

**When**
- `result = M.create_workspace_with_owner(db, workspace_data=WorkspaceCreate(name="Acme Tools", slug=SL), owner_user_id=UA.id, subscription_plan_id=PX.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new workspace: `subscription_plan_id == PX.id`.
## Pending the plans/subscriptions design — OQ-17 / BUG-1989 (`max_members = 0`)

> Today's behaviour, kept in its own cards: `0` skips the seat check. These are ordinary passing tests now; when the portal design settles what `0` means, only the cards of this section change (no other card uses a limit of 0).

### WSMG-P17-01 — a limit of 0 today means no limit: the owner alone, one more is added
- **Rules:** `add_member_to_workspace` R6 (pending BUG-1989 / OQ-17)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 0

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `status == "active"`.
3. count: `workspace_members` with `workspace_id == W1.id` and `status == "active"` has exactly 2 rows.

### WSMG-P17-02 — a limit of 0 today means no limit: a fifth active member is added
- **Rules:** `add_member_to_workspace` R6 (pending BUG-1989 / OQ-17)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 0
2. B = member(UB).
3. C = member(UC).
4. P1.
5. Q = member(P1).

**When**
- `result = M.add_member_to_workspace(db, workspace_id=W1.id, user_id=UA.id, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `workspace_members` with `workspace_id == W1.id` and `status == "active"` has exactly 5 rows.

### WSMG-P17-03 — a limit of 0 today means no limit: the owner alone may invite
- **Rules:** `create_invitation` R9 (pending BUG-1989 / OQ-17)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 0

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=EE, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: invitations(W1) with `status == "pending"` has exactly 1 row.

### WSMG-P17-04 — a limit of 0 today means no limit: invited on top of members and pending invitations
- **Rules:** `create_invitation` R9 (pending BUG-1989 / OQ-17)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 0
2. B = member(UB).
3. C = member(UC).
4. J = invitation J to ED.
5. K = invitation K to `f"fay.{TAG}@acme.com"`.

**When**
- `result = M.create_invitation(db, workspace_id=W1.id, email=EE, role="member", inviter_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: invitations(W1) with `status == "pending"` has exactly 3 rows.

### WSMG-P17-05 — a limit of 0 today means no limit: an invitation is accepted
- **Rules:** `accept_invitation` R3; `add_member_to_workspace` R6 (pending BUG-1989 / OQ-17)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. limit 0
2. B = member(UB).
3. I = invitation I to EA.

**When**
- `result = M.accept_invitation(db, invitation_id=I.id, user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `workspace_members` with `workspace_id == W1.id` and `status == "active"` has exactly 3 rows.
3. re-read I: `status == "accepted"`.
## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Overview: `ValueError` → 400 in create, invite, accept; → 403 in remove, cancel | `WorkspaceService` | the status code and detail per method |
| FU-1 | `WorkspaceService.remove_member`, `cancel_invitation` | whether "not a member" / "Invitation not found" should be 404; same text for unknown and foreign ids (BUG-1981) |
| A2 / FU-2 (BUG-1404) | `WorkspaceService`, `app/api/v1/endpoints/workspaces.py` | the request's client IP and user agent are passed down to every method here |
| FU-3 | `AuthService._register_with_invitation` | validate, create profile, accept; the token decides the workspace |
| Visibility of `create_invitation`, list | `WorkspaceService._require_owner` | sending and listing invitations are owner-only |
| `validate_invitation_for_user` R6 (workspace not checked here) | `WorkspaceService.accept_invitation` | the invitation's workspace must equal the one in the URL |
| R12 [BUG-1980], `WorkspaceUpdate.name` | `app/schemas/workspace.py` (`WorkspaceUpdate`) / workspace update spec | the same trim and blank refusal on update |
| A2 ip over 45 characters (BUG-1405) | `tests/unit/dao/workspace_audit_log.spec.md` | cut to 45 by the DAO |
| `create_invitation` R14 | notifications feature (`docs/future/notifications.md`) | nothing is sent today; an invitation notice when designed |
| `create_workspace_with_owner` R9 (seed functions) | `app/db/seed_*.py` (no spec) | idempotence and "already exists" branches; here only the outcome for a new workspace is tested |

## Spec gaps
None open. Gaps 1–10 of revision 1 were closed by the spec's Gap log (2026-11-04):
- G1: remove and cancel return `None`. G2: counter and stripe column names. G3: "open" in columns for all five order types, and the event columns. G4: the `User #<id>` fallback is unreachable, so no card. G5: R7 is observed with `timezone` `None` / `""`.
- G6: the cancel audit email is logged as stored. G7: new R6a. G8: patch target `M.workspace_dao.get_by_slug`. G9: all naive timestamps except `workspace_audit_logs.created_at`. G10: `tag_code` and `type` confirmed.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| Audit rows | A1 | WSMG-CW-27, WSMG-AM-37, WSMG-RM-59, WSMG-CI-57, WSMG-AI-03, WSMG-XI-02 |
| Audit rows | A2 [BUG-1404] | WSMG-CW-34, WSMG-AM-40, WSMG-RM-82, WSMG-CI-60, WSMG-AI-25, WSMG-AI-28, WSMG-XI-26 |
| Audit rows | A3 | WSMG-CW-06 … WSMG-CW-10, WSMG-AM-06 … WSMG-AM-15, WSMG-AM-22 … WSMG-AM-24, RM refusal cards, CI refusal cards, WSMG-AI-04, WSMG-AI-11, WSMG-AI-12, WSMG-XI-04 … WSMG-XI-24 (every refusal asserts "nothing written") |
| `create_workspace_with_owner` | R1 (pending OQ-16) | WSMG-P16-01 … WSMG-P16-04 |
| | R2 / Errors 1 | WSMG-CW-07, WSMG-CW-08 |
| | R3 / Errors 2 | WSMG-CW-01, WSMG-CW-03, WSMG-CW-04, WSMG-CW-05, WSMG-CW-06, WSMG-CW-14 |
| | R4 | WSMG-CW-09 |
| | R5 / Errors 3 | WSMG-CW-10, WSMG-CW-11, WSMG-CW-12, WSMG-CW-13 |
| | R6 | WSMG-CW-01, WSMG-CW-02, WSMG-CW-14, WSMG-P16-02 |
| | R7 | WSMG-CW-15, WSMG-CW-16, WSMG-CW-17 (missing profile: only R11's failure, WSMG-CW-28) |
| | R8 | WSMG-CW-14, WSMG-CW-18, WSMG-CW-19 |
| | R9 | WSMG-CW-20 … WSMG-CW-26 |
| | R10 | WSMG-CW-03, WSMG-CW-27, WSMG-P16-01 |
| | R11 / Errors 4 | WSMG-CW-28 |
| | R12 [BUG-1980] | WSMG-CW-29, WSMG-CW-30 (xfail); WSMG-CW-31, WSMG-CW-32 (pass) |
| | Returns, no commit | WSMG-CW-01, WSMG-CW-33 |
| `add_member_to_workspace` | R1 / Errors 1 | WSMG-AM-02 … WSMG-AM-11 |
| | R2 / Errors 2 | WSMG-AM-12 … WSMG-AM-18 |
| | R2a [BUG-1982] | WSMG-AM-19, WSMG-AM-20, WSMG-AM-21; WSMG-AI-15 |
| | R3 / Errors 3 | WSMG-AM-22, WSMG-AM-10 |
| | R4 | WSMG-AM-23 |
| | R5 / Errors 4 | WSMG-AM-24 … WSMG-AM-32, WSMG-AI-12, WSMG-AI-13 |
| | R5a [BUG-1872] | WSMG-AM-33, WSMG-AM-34, WSMG-AI-14 |
| | R6 (pending BUG-1989) | WSMG-P17-01, WSMG-P17-02, WSMG-P17-05 |
| | R7 | WSMG-AM-01 |
| | R8 [BUG-1985] | WSMG-AM-35 (xfail), WSMG-AM-36 (pass, `None`); WSMG-AI-09, WSMG-AI-10 |
| | R9 | WSMG-AM-36, WSMG-AM-37 |
| | R10 | WSMG-AM-38, WSMG-AI-23 |
| | Returns, no commit | WSMG-AM-01, WSMG-AM-39 |
| `remove_member_from_workspace` | R1 / Errors 1 | WSMG-RM-52 … WSMG-RM-55 |
| | R1a [BUG-1984] | WSMG-RM-56 (xfail); WSMG-RM-57 (suspended, pass) |
| | R2 / Errors 2 | WSMG-RM-48 … WSMG-RM-51, WSMG-RM-83, WSMG-RM-84, WSMG-RM-85 |
| | R3 / Errors 3 | WSMG-RM-19 … WSMG-RM-24, WSMG-RM-49, WSMG-RM-65, WSMG-RM-68 |
| | R4 / Errors 4 | WSMG-RM-07 … WSMG-RM-12, WSMG-RM-50, WSMG-RM-66 |
| | R4a | WSMG-RM-13 |
| | R4b [BUG-1990] | WSMG-RM-14 … WSMG-RM-18 |
| | R5 [BUG-1990] / Errors 3 | WSMG-RM-25 … WSMG-RM-47, WSMG-RM-60 … WSMG-RM-64, WSMG-RM-69 |
| | R5a | WSMG-RM-01 … WSMG-RM-06, WSMG-RM-59 |
| | R6 | WSMG-RM-01 … WSMG-RM-07, WSMG-RM-13, WSMG-RM-57, WSMG-RM-58 |
| | R7 | WSMG-RM-01 … WSMG-RM-07, WSMG-RM-13, WSMG-RM-59 |
| | R8 [BUG-1201] | WSMG-RM-70 … WSMG-RM-74 (xfail); WSMG-RM-75 (pass) |
| | R9 [BUG-1280] | WSMG-RM-76 (xfail); WSMG-RM-77 (pass) |
| | R10 [BUG-1883] | WSMG-RM-78, WSMG-RM-79 (xfail); WSMG-RM-80 (pass) |
| | R11 | WSMG-RM-67, WSMG-RM-75, WSMG-RM-77, WSMG-RM-80, WSMG-RM-81 |
| | R12 | WSMG-RM-67 |
| | Returns `None`, no commit | WSMG-RM-01 … WSMG-RM-07, WSMG-RM-13, WSMG-RM-57 … WSMG-RM-59, WSMG-RM-67, WSMG-RM-75, WSMG-RM-77, WSMG-RM-80, WSMG-RM-81 |
| `create_invitation` | R1 / Errors 1 | WSMG-CI-05 … WSMG-CI-13 |
| | R2 [BUG-1860] | WSMG-CI-20, WSMG-CI-21, WSMG-CI-22 (xfail); WSMG-CI-18, WSMG-CI-19 (pass) |
| | R3 / Errors 2 | WSMG-CI-14 … WSMG-CI-19, WSMG-CI-36 |
| | R3a [BUG-1983] | WSMG-CI-23, WSMG-CI-24, WSMG-CI-25 (xfail); WSMG-CI-26 (pass) |
| | R4 [BUG-1873] / Errors 3 | WSMG-CI-27 … WSMG-CI-30, WSMG-CI-37 (xfail); WSMG-CI-31 … WSMG-CI-36 (pass) |
| | R5 / Errors 4 | WSMG-CI-38, WSMG-CI-13 |
| | R6 | WSMG-CI-39 |
| | R7 / Errors 5 | WSMG-CI-40 … WSMG-CI-54 |
| | R8 [BUG-1871] | WSMG-CI-55, WSMG-CI-56 |
| | R9 (pending BUG-1989) | WSMG-P17-03, WSMG-P17-04 |
| | R10 | WSMG-CI-01, WSMG-CI-02, WSMG-CI-58 |
| | R11 | WSMG-CI-03, WSMG-CI-04 |
| | R12 | WSMG-CI-01 |
| | R13 | WSMG-CI-57, WSMG-CI-58 |
| | R14 | deferred (nothing to observe; no external is called) |
| | Returns, no commit | WSMG-CI-01, WSMG-CI-59 |
| `validate_invitation_for_user` | R1 / Errors 1 | WSMG-VI-03 … WSMG-VI-06 |
| | R2 [BUG-1987] / Errors 2 | WSMG-VI-07, WSMG-VI-09 (pass); WSMG-VI-08 (xfail) |
| | R3 | WSMG-VI-10, WSMG-VI-11 |
| | R4 / Errors 3 | WSMG-VI-12 … WSMG-VI-15 |
| | R5 / Errors 4 | WSMG-VI-16 … WSMG-VI-20 |
| | R6, Side effects | WSMG-VI-01, WSMG-VI-02, WSMG-VI-06, WSMG-VI-21, WSMG-VI-22 |
| | Returns | WSMG-VI-01 |
| `accept_invitation` | R1 / Errors 1 | WSMG-AI-04 |
| | R2 | WSMG-AI-05, WSMG-AI-06, WSMG-AI-07 |
| | R3 / Errors 2 | WSMG-AI-01, WSMG-AI-08 … WSMG-AI-15, WSMG-AI-23, WSMG-P17-05 |
| | R4 | WSMG-AI-02, WSMG-AI-05 |
| | R5 [BUG-1874] | WSMG-AI-16, WSMG-AI-17, WSMG-AI-18 (xfail); WSMG-AI-19 … WSMG-AI-22 (pass) |
| | R6 | WSMG-AI-03, WSMG-AI-08 |
| | R6a | WSMG-AI-26 (pass); WSMG-AI-27 (xfail BUG-1874); WSMG-AI-28 (xfail BUG-1404) |
| | Returns, no commit | WSMG-AI-01, WSMG-AI-24 |
| `cancel_invitation` | R1 [BUG-1986] / Errors 1 | WSMG-XI-12 … WSMG-XI-19, WSMG-XI-23, WSMG-XI-24 (pass); WSMG-XI-20, WSMG-XI-21, WSMG-XI-22 (xfail) |
| | R2 [BUG-1981] / Errors 2 | WSMG-XI-07, WSMG-XI-09, WSMG-XI-11 (pass); WSMG-XI-08, WSMG-XI-10 (xfail) |
| | R3 / Errors 3 | WSMG-XI-04, WSMG-XI-05, WSMG-XI-06 |
| | R4 | WSMG-XI-03 |
| | R5 | WSMG-XI-01 |
| | R6 | WSMG-XI-02, WSMG-XI-03, WSMG-XI-27 |
| | Returns `None`, no commit | WSMG-XI-01, WSMG-XI-02, WSMG-XI-03, WSMG-XI-25, WSMG-XI-27 |
