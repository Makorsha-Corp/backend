# Test cases — `app/services/access_control_service.py`

> **Spec:** `tests/unit/services/access_control_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 5 (2026-11-06) — verifier findings (`access_control_service.verify.md`). Finding 1: new ACS-U-13 and ACS-D-10, the C-23 shape for update and delete (a non-owner refusal with a pending row: no commit, no rollback, the row survives, nothing written), strict xfail BUG-1875. Finding 2: ACS-C-24 gains Then 4–6, `user_id` has no default on each writer (`default is Parameter.empty`), so a fix with `user_id=None` that skips the check fails it.
> Revision 4 (2026-11-05) — executor discrepancies (`access_control_service.notes.md`). The re-read check in ACS-C-01 (Then 3) and ACS-U-01 (Then 2) now covers column attributes only: `not ({c.key for c in inspect(result).mapper.column_attrs} & inspect(result).expired_attributes)` (`db.refresh()` leaves lazy relationships expired; `AccessControl` has none, so the check is unchanged in effect). ACS-D-02 (DISCREPANCY-1): Then 6 "nothing written" counted the pending W2 row P added after the commit point; it now counts only the rows the call could delete, leaving P out: Then 6 W0 has exactly 1 row, new Then 7 W1 has exactly 1 row. Counts unchanged.
> Revision 3 (2026-11-05) — the write cards ACS-C-01 … C-05, U-01 … U-08, D-01 … D-05 are pass again: they call through the new Conventions helper `call_uid` (as `attachment_service.cases.md`) with the owner UO, so they hold today and after the BUG-1875 fix; their `Fails today on` lines are removed. New ACS-C-24: strict signature alarm (keyword-only `user_id` on the three writers). The BUG-1875 refusals stay strict xfail, passing `user_id=` directly. C-06, U-09, D-06 stay retired (identical to C-01, U-01, D-01 through `call_uid`).
> Revision 2 (2026-11-05) — spec fill-gaps G1–G3. G1: schema module from the spec (Conventions). G2: `user_id` is required and keyword-only, so every write card now passes `user_id=UO.id` (the owner); the former pass write cards ACS-C-01 … C-05, U-01 … U-08, D-01 … D-05 become strict xfail BUG-1875 (the call raises `TypeError` today); C-03 now makes the DAO fail (`Author: claude`), since an unknown workspace would now be refused by the owner check. G3: the 403 is raised before the `try`; new ACS-C-23 (a pending row survives, no commit, no rollback). Retired C-06, U-09, D-06 (now identical to C-01, U-01, D-01).
> **Counts:** 63 cases · 35 expected-to-pass · 28 expected-to-fail (bugs) · 3 deferred

## Reviewer summary
- **Per callable:** `get_controls` 13 (2 bug) · `get_by_id` 6 · `create_control` 23 (18 bug, C-24 the signature alarm for all three writers) · `update_control` 12 (4 bug) · `delete_control` 9 (4 bug).
- **Depth:** full on BUG-1875 (owner's OQ-4: only the workspace owner writes these rows); lighter (skill step 1a) for the rest: a thin DAO wrapper, no stock, money or order state.
- **BUG-1875 (26 strict cards: 25 refusals and the signature alarm ACS-C-24, which checks keyword-only and required):** on create, one card per refused role (`ground-team-manager`, `finance`, `ground-team`, `manager`, `member`, `viewer`), the exact-text roles `Owner` and `owner `, an `owner` row that is `inactive`, `suspended`, `invited` or `Active`, the owner of W0 (row built before the W1 row) and of W2 (row built after), the person named by `owner_user_id` with no membership row (the record lacking the field the grant reads), and an unknown user. Update and delete get the cross-workspace and "checked first" shapes (403 also for an id that would answer `None` / `False`) and one role, status and exact-text card each. Every refusal asserts type, 403, the exact message, a `session:` line before any re-read, and nothing written. Refusal cards pass `user_id=` directly (`TypeError` today). ACS-C-24 checks with `inspect.signature` that each writer has a keyword-only `user_id`: the alarm that goes off when the fix lands. ACS-C-23, U-13, D-10: the refusal leaves a pending row of the session in place (raised before the `try`).
- **Kept passing beside BUG-1875:** the reads, and every write path (commit, re-read, not-found `None` / `False`, DAO, commit and refresh failures): those 18 cards call through `call_uid` with the owner UO, which adds `user_id` only once the signature has it, so the write paths are protected today and after the fix.
- **BUG-2255 (2 strict):** role and type together; and the hidden `PAGE` row with the lowest id ahead of the skipped row (`skip=1` → intended 1 row, today 2).
- **Notable design choices:** the re-read check (TX2) covers column attributes only. ACS-D-02's "nothing deleted" counts W0 and W1 rows, not the pending W2 row P the card keeps on purpose. Pass cards compare sets or lengths, never an order (the role and type reads have no `ORDER BY` today, BUG-1408 is the DAO's alarm). ACS-C-03 patches the DAO's `create` to fail (the only way past the owner check to an error inside the `try`).
- **Needs a decision:** None. Gaps 1–3 closed by the spec's Gap log (G1–G3).

## Conventions for this module

**IDs.** `ACS` = `app/services/access_control_service.py`. `L` get_controls · `G` get_by_id · `C` create_control · `U` update_control · `D` delete_control.

**Actors and fixed values.**
- `svc` = `access_control_service` (`from app.services.access_control_service import AccessControlService, access_control_service`). `db` = the test's real session, first positional argument; every other argument by keyword. `result` = what the When returns.
- `AccessControl` (`app.models.access_control`), `WorkspaceMember` (`app.models.workspace_member`), `AccessControlCreate`, `AccessControlUpdate` (`app.schemas.access_control`), `RoleEnum`, `AccessControlTypeEnum` (`app.models.enums`), `PermissionDeniedError` (`app.core.exceptions`), `IntegrityError`, `DataError` (`sqlalchemy.exc`), `select`, `func`, `inspect` (`sqlalchemy`), `patch` (`unittest.mock`).
- OWNER = `RoleEnum.OWNER`, FINANCE = `RoleEnum.FINANCE`, GT = `RoleEnum.GROUND_TEAM` (value `"ground-team"`). PAGE = `AccessControlTypeEnum.PAGE`, FEATURE = `AccessControlTypeEnum.FEATURE`.
- MISSING = `999999999`. DENY = `"Only the workspace owner can change access control"`.

**Standing rows** (every test, in this order, each flushed, no Given line): W0, W1, W2 = `make_workspace(db)` (`W0.id < W1.id < W2.id`); profiles `make_profile(db, name=…)`: UA `"Ana"`, UO `"Omar"`, UZ `"Zara"` (`UA.id < UO.id < UZ.id`); MO = `WorkspaceMember(workspace_id=W1.id, user_id=UO.id, role="owner", status="active")`. No `owner_user_id` is set and no `access_control` row of W0, W1, W2 exists unless the Given says so.

**Given rows.** Inserted directly (never through `svc`), flushed one at a time in the order written, so ids rise in that order. After "but" a line lists every column that differs. A line written as code is a step run exactly.
- **rule** = `AccessControl(workspace_id=W1.id, type=PAGE, target="/orders", role=OWNER)`.
- **mem(U, role, status="active", ws=W1)** = `WorkspaceMember(workspace_id=ws.id, user_id=U.id, role=role, status=status)`.
- **commit point** = after the last Given line the test runs `db.commit()` (releases a savepoint under the `db` fixture). Snapshots for `unchanged` and `nothing written` are taken there.
- **extra row X** (after the commit point) = `X = AccessControl(workspace_id=W2.id, type=FEATURE, target="extra", role=FINANCE)`, `db.add(X)`, `db.flush()`; not committed. `X_ID = X.id`. **x_gone** = `db.scalar(select(func.count()).select_from(AccessControl).where(AccessControl.id == X_ID)) == 0`.
- **pending P** (after the commit point) = the same as X but `target "pending"`, named P; `P_ID = P.id`. **edit B** = `B.target = "/edited"` on the row B the card names, not flushed.

**Externals.** None mocked, except the failure patches below.

**Named checks.**
- **re-read X** = `db.expire_all()`, then `db.get(AccessControl, X.id)`.
- **unchanged(A)** = after re-read, `type`, `target`, `role`, `workspace_id` of A equal their values at the commit point.
- **nothing written** = the numbers of `access_control` rows with `workspace_id` W0, W1, W2 equal their values at the commit point.
- **idset(r)** = `{c.id for c in r}`.
- `raises: <Type>` = plain `with pytest.raises(<Type>) as exc:` around the call, no savepoint; further lines on `exc.value` after the block. `raises: DataError in a savepoint` = `with pytest.raises(DataError):` then `with db.begin_nested():` then the call.
- `session:` lines check `db.new`, `db.dirty`, `db.deleted` right after the call, before any re-read or `expire_all`.
- `committed:` lines: before the first, the test runs `db.rollback()` once; each line then re-reads with a fresh query.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = the same with `patch.object(db, "refresh", side_effect=RuntimeError("boom"))` and no rollback spy. **call_uid(fn, U, **kw)** = `fn(db, **kw, user_id=U.id)` when `"user_id" in signature(fn).parameters`, else `fn(db, **kw)` (`signature`, `Parameter` from the standard `inspect` module; `inspect` in Conventions stays SQLAlchemy's). **failing dao create** = `with pytest.raises(RuntimeError) as exc:` around `with patch("app.services.access_control_service.access_control_dao.create", side_effect=RuntimeError("dao boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`. All strict. Write the call exactly as shown, also with the `user_id` parameter that does not exist yet (required, keyword-only after the fix).

**Race simulations.** None.

## `AccessControlService.get_controls`

### ACS-L-01 — role only: that role's rows of the workspace, every type
- **Rules:** `get_controls` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A0 = rule, but `workspace_id W0.id`.
2. A1 = rule.
3. A2 = rule, but `type FEATURE`, `target "reports"`.
4. AF = rule, but `role FINANCE`.
5. A9 = rule, but `workspace_id W2.id`.

**When**
- `result = svc.get_controls(db, workspace_id=W1.id, role=OWNER, limit=1000)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `idset(result) == {A1.id, A2.id}`.

### ACS-L-02 — role and type together: only rows matching both
- **Rules:** `get_controls` R1 [BUG-2255]
- **Kind:** bug
- **Expect:** xfail BUG-2255
- **Fails today on:** Then 2 (the type is ignored: the OWNER PAGE row comes back too)

**Given**
1. AP = rule.
2. AF = rule, but `type FEATURE`, `target "reports"`.
3. FF = rule, but `type FEATURE`, `target "reports"`, `role FINANCE`.

**When**
- `result = svc.get_controls(db, workspace_id=W1.id, role=OWNER, access_type=FEATURE, limit=1000)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `idset(result) == {AF.id}`.

### ACS-L-03 — role and type together: a hidden row ahead of the skipped row takes no place
- **Rules:** `get_controls` R1 [BUG-2255]
- **Kind:** bug
- **Expect:** xfail BUG-2255
- **Fails today on:** Then 1 (type ignored: skip=1 of three OWNER rows leaves two)

**Given**
1. H = rule (OWNER PAGE, lowest id; first by id today and after the fix).
2. F1 = rule, but `type FEATURE`, `target "a"`.
3. F2 = rule, but `type FEATURE`, `target "b"`.

**When**
- `result = svc.get_controls(db, workspace_id=W1.id, role=OWNER, access_type=FEATURE, skip=1, limit=10)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `idset(result) == {F2.id}`.

### ACS-L-04 — type only: that type's rows of the workspace, every role
- **Rules:** `get_controls` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. F0 = rule, but `workspace_id W0.id`, `type FEATURE`.
2. FA = rule, but `type FEATURE`.
3. FB = rule, but `type FEATURE`, `role FINANCE`.
4. PA = rule.
5. F9 = rule, but `workspace_id W2.id`, `type FEATURE`.

**When**
- `result = svc.get_controls(db, workspace_id=W1.id, access_type=FEATURE, limit=1000)`.

**Then**
1. returns: `idset(result) == {FA.id, FB.id}`.

### ACS-L-05 — neither filter: every row of the workspace, not W0's or W2's
- **Rules:** `get_controls` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A0 = rule, but `workspace_id W0.id`.
2. A1 = rule.
3. A2 = rule, but `type FEATURE`, `role FINANCE`.
4. A9 = rule, but `workspace_id W2.id`.

**When**
- `result = svc.get_controls(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {A1.id, A2.id}`.

### ACS-L-06 — neither filter: the default limit is 100
- **Rules:** `get_controls` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rules in W1: `db.add_all([AccessControl(workspace_id=W1.id, type=PAGE, target=f"/p{i}", role=OWNER) for i in range(101)])`, `db.flush()`.

**When**
- `result = svc.get_controls(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### ACS-L-07 — role only: the default limit is 100
- **Rules:** `get_controls` R1, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rules in W1: `db.add_all([AccessControl(workspace_id=W1.id, type=PAGE, target=f"/p{i}", role=OWNER) for i in range(101)])`, `db.flush()`.

**When**
- `result = svc.get_controls(db, workspace_id=W1.id, role=OWNER)`.

**Then**
1. returns: `len(result) == 100`.

### ACS-L-08 — type only: the default limit is 100
- **Rules:** `get_controls` R2, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rules in W1: `db.add_all([AccessControl(workspace_id=W1.id, type=PAGE, target=f"/p{i}", role=OWNER) for i in range(101)])`, `db.flush()`.

**When**
- `result = svc.get_controls(db, workspace_id=W1.id, access_type=PAGE)`.

**Then**
1. returns: `len(result) == 100`.

### ACS-L-09 — skip and limit are passed on
- **Rules:** `get_controls` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = rule, but `target "/a"`.
2. B = rule, but `target "/b"`.
3. C = rule, but `target "/c"`.

**When**
- `result = svc.get_controls(db, workspace_id=W1.id, role=OWNER, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `idset(result) <= {A.id, B.id, C.id}`.

### ACS-L-10 — limit 1000 returns all 101
- **Rules:** `get_controls` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rules in W1: `db.add_all([AccessControl(workspace_id=W1.id, type=PAGE, target=f"/p{i}", role=OWNER) for i in range(101)])`, `db.flush()`.

**When**
- `result = svc.get_controls(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.

### ACS-L-11 — a negative skip fails in the database
- **Rules:** `get_controls` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. A = rule.

**When**
- `svc.get_controls(db, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: DataError in a savepoint.

### ACS-L-12 — a read neither commits nor rolls back; pending changes stay
- **Rules:** `get_controls` R5; TX5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. B = rule (commit point after this line).
2. pending P.
3. edit B.

**When**
- spies: `result = svc.get_controls(db, workspace_id=W1.id, role=OWNER, limit=1000)`.

**Then**
1. returns: `B.id in idset(result)`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `db.get(AccessControl, P_ID) is P`.
5. session: `B in db.dirty`.
6. session: `B.target == "/edited"`.

### ACS-L-13 — a workspace with no rows gives an empty list
- **Rules:** `get_controls` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A9 = rule, but `workspace_id W2.id`.

**When**
- `result = svc.get_controls(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

## `AccessControlService.get_by_id`

### ACS-G-01 — returns the workspace's row
- **Rules:** `get_by_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A0 = rule, but `workspace_id W0.id`.
2. A = rule.
3. A9 = rule, but `workspace_id W2.id`.

**When**
- `result = svc.get_by_id(db, control_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.target == "/orders"`.

### ACS-G-02 — W0's row (lower id) is None in W1
- **Rules:** `get_by_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A0 = rule, but `workspace_id W0.id`.
2. A = rule.

**When**
- `result = svc.get_by_id(db, control_id=A0.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ACS-G-03 — W2's row (higher id) is None in W1
- **Rules:** `get_by_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = rule.
2. A9 = rule, but `workspace_id W2.id`.

**When**
- `result = svc.get_by_id(db, control_id=A9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ACS-G-04 — an unknown id is None
- **Rules:** `get_by_id` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = rule.

**When**
- `result = svc.get_by_id(db, control_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ACS-G-05 — id 0 is None
- **Rules:** `get_by_id` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = rule.

**When**
- `result = svc.get_by_id(db, control_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ACS-G-06 — a get neither commits nor rolls back; pending changes stay
- **Rules:** `get_by_id` R2; TX5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. B = rule (commit point after this line).
2. pending P.
3. edit B.

**When**
- spies: `result = svc.get_by_id(db, control_id=B.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is B`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `db.get(AccessControl, P_ID) is P`.
5. session: `B in db.dirty`.
6. session: `B.target == "/edited"`.

## `AccessControlService.create_control`

### ACS-C-01 — creates the row in the given workspace, committed and re-read
- **Rules:** `create_control` R2, R3; TX1, TX2; R1 (caller UO through call_uid)
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rule in W1 (commit point after this line).

**When**
- `result = call_uid(svc.create_control, UO, control_in=AccessControlCreate(type=FEATURE, target="reports", role=FINANCE), workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. returns: `result.workspace_id == W1.id`, `result.target == "reports"`.
3. returns: `not ({c.key for c in inspect(result).mapper.column_attrs} & inspect(result).expired_attributes)`.
4. committed: the row with id `result.id` exists, `workspace_id == W1.id`, `type == FEATURE`, `target == "reports"`, `role == FINANCE`.
5. committed: W0 and W2 have 0 `access_control` rows.

### ACS-C-02 — an identical row and a blank target are both accepted
- **Rules:** `create_control` R2 (D2); R1 (caller UO through call_uid)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = rule, but `target ""` (commit point after this line).

**When**
- `result = call_uid(svc.create_control, UO, control_in=AccessControlCreate(type=PAGE, target="", role=OWNER), workspace_id=W1.id)`.

**Then**
1. returns: `result.id != A.id`.
2. committed: W1 has exactly 2 `access_control` rows with `type == PAGE`, `target == ""`, `role == OWNER`.

### ACS-C-03 — an error from the DAO rolls back, reaches the caller unchanged, and discards other pending changes
- **Rules:** `create_control` R3; TX3; R1 (caller UO through call_uid)
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. No rule in W1 (commit point after this line).
2. extra row X.

**When**
- failing dao create: `call_uid(svc.create_control, UO, control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER), workspace_id=W1.id)`.

**Then**
1. raises: `str(exc.value) == "dao boom"`.
2. mock called: `rb.call_count == 1`.
3. count: x_gone.
4. nothing written.
5. session: `db.scalar(select(func.count()).select_from(AccessControl).where(AccessControl.workspace_id == W1.id)) == 0` (the session is usable).

### ACS-C-04 — a failing commit rolls back and nothing is saved
- **Rules:** `create_control` R3; TX3; R1 (caller UO through call_uid)
- **Kind:** error
- **Expect:** pass

**Given**
1. No rule in W1 (commit point after this line).

**When**
- failing commit: `call_uid(svc.create_control, UO, control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER), workspace_id=W1.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count == 1`.
3. nothing written.

### ACS-C-05 — a failing re-read after the commit leaves the row saved
- **Rules:** `create_control` R3; TX3 (as TC5); R1 (caller UO through call_uid)
- **Kind:** error
- **Expect:** pass

**Given**
1. No rule in W1 (commit point after this line).

**When**
- failing refresh: `call_uid(svc.create_control, UO, control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER), workspace_id=W1.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: W1 has exactly 1 `access_control` row, `target == "/orders"`.

### ACS-C-07 — a ground-team-manager may not create
- **Rules:** `create_control` R1 [BUG-1875]
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UA, "ground-team-manager") (commit point after this line).

**When**
- `svc.create_control(db, control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.new`.
5. nothing written.

### ACS-C-08 — a finance member may not create
- **Rules:** `create_control` R1 [BUG-1875]
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UZ, "finance") (commit point after this line).

**When**
- `svc.create_control(db, control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER), workspace_id=W1.id, user_id=UZ.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.new`.
5. nothing written.

### ACS-C-09 — a ground-team member may not create
- **Rules:** `create_control` R1 [BUG-1875]
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UA, "ground-team") (commit point after this line).

**When**
- `svc.create_control(db, control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.new`.
5. nothing written.

### ACS-C-10 — a manager may not create
- **Rules:** `create_control` R1 [BUG-1875]
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UZ, "manager") (commit point after this line).

**When**
- `svc.create_control(db, control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER), workspace_id=W1.id, user_id=UZ.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.new`.
5. nothing written.

### ACS-C-11 — a plain member may not create
- **Rules:** `create_control` R1 [BUG-1875]
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UA, "member") (commit point after this line).

**When**
- `svc.create_control(db, control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.new`.
5. nothing written.

### ACS-C-12 — a viewer may not create
- **Rules:** `create_control` R1 [BUG-1875]
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UZ, "viewer") (commit point after this line).

**When**
- `svc.create_control(db, control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER), workspace_id=W1.id, user_id=UZ.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.new`.
5. nothing written.

### ACS-C-13 — role "Owner" (capital O) is not the owner
- **Rules:** `create_control` R1 [BUG-1875]
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UA, "Owner") (commit point after this line).

**When**
- `svc.create_control(db, control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.new`.
5. nothing written.

### ACS-C-14 — role "owner " (trailing space) is not the owner
- **Rules:** `create_control` R1 [BUG-1875]
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UZ, "owner ") (commit point after this line).

**When**
- `svc.create_control(db, control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER), workspace_id=W1.id, user_id=UZ.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.new`.
5. nothing written.

### ACS-C-15 — an inactive owner row is refused
- **Rules:** `create_control` R1 [BUG-1875]
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UA, "owner", status="inactive") (commit point after this line).

**When**
- `svc.create_control(db, control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.new`.
5. nothing written.

### ACS-C-16 — a suspended owner row is refused
- **Rules:** `create_control` R1 [BUG-1875]
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UZ, "owner", status="suspended") (commit point after this line).

**When**
- `svc.create_control(db, control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER), workspace_id=W1.id, user_id=UZ.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.new`.
5. nothing written.

### ACS-C-17 — an invited owner row is refused
- **Rules:** `create_control` R1 [BUG-1875]
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UA, "owner", status="invited") (commit point after this line).

**When**
- `svc.create_control(db, control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.new`.
5. nothing written.

### ACS-C-18 — status "Active" (capital A) is not active
- **Rules:** `create_control` R1 [BUG-1875]
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UZ, "owner", status="Active") (commit point after this line).

**When**
- `svc.create_control(db, control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER), workspace_id=W1.id, user_id=UZ.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.new`.
5. nothing written.

### ACS-C-19 — the owner of W0 (row built first) is a ground-team member in W1: refused
- **Rules:** `create_control` R1 [BUG-1875]
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UA, "owner", ws=W0) (flushed first).
2. mem(UA, "ground-team") (commit point after this line).

**When**
- `svc.create_control(db, control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.new`.
5. nothing written.

### ACS-C-20 — the owner of W2 (row built after) with no W1 membership: refused
- **Rules:** `create_control` R1 [BUG-1875]
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UA, "ground-team").
2. mem(UZ, "owner", ws=W2) (commit point after this line).

**When**
- `svc.create_control(db, control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER), workspace_id=W1.id, user_id=UZ.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.new`.
5. nothing written.

### ACS-C-21 — the person named by owner_user_id but with no membership row is refused
- **Rules:** `create_control` R1 [BUG-1875]
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. `W1.owner_user_id = UZ.id`; `db.flush()` (UZ has no `workspace_members` row; commit point after this line).

**When**
- `svc.create_control(db, control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER), workspace_id=W1.id, user_id=UZ.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.new`.
5. nothing written.

### ACS-C-22 — an unknown user is refused
- **Rules:** `create_control` R1 [BUG-1875]
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. No rule in W1 (commit point after this line).

**When**
- `svc.create_control(db, control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.new`.
5. nothing written.

### ACS-C-23 — a refusal neither commits nor rolls back: a pending row of the session survives
- **Rules:** `create_control` R1 [BUG-1875] (raised before the `try`)
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UA, "finance") (commit point after this line).
2. pending P.

**When**
- spies: `svc.create_control(db, control_in=AccessControlCreate(type=PAGE, target="/orders", role=OWNER), workspace_id=W1.id, user_id=UA.id)` (the `pytest.raises` block inside the spies).

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. mock called: `cm.call_count == 0`.
5. mock called: `rb.call_count == 0`.
6. session: `not db.new and not db.dirty and not db.deleted`.
7. session: `db.get(AccessControl, P_ID) is P`.
8. count: `db.scalar(select(func.count()).select_from(AccessControl).where(AccessControl.id == P_ID)) == 1`.
9. count: W1 has 0 `access_control` rows.

### ACS-C-24 — the three writers take a required keyword-only user_id (signature alarm)
- **Rules:** `create_control` R1, `update_control` R1, `delete_control` R1 [BUG-1875]
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (KeyError: `create_control` has no `user_id` parameter)

**Given**
1. No Given rows needed.

**When**
- `sigs = {name: signature(getattr(svc, name)).parameters for name in ("create_control", "update_control", "delete_control")}`.

**Then**
1. returns: `sigs["create_control"]["user_id"].kind == Parameter.KEYWORD_ONLY`.
2. returns: `sigs["update_control"]["user_id"].kind == Parameter.KEYWORD_ONLY`.
3. returns: `sigs["delete_control"]["user_id"].kind == Parameter.KEYWORD_ONLY`.
4. returns: `sigs["create_control"]["user_id"].default is Parameter.empty`.
5. returns: `sigs["update_control"]["user_id"].default is Parameter.empty`.
6. returns: `sigs["delete_control"]["user_id"].default is Parameter.empty`.

## `AccessControlService.update_control`

### ACS-U-01 — changes the sent field, keeps the others, committed and re-read
- **Rules:** `update_control` R3, R4; TX1, TX2; R1 (caller UO through call_uid)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = rule (commit point after this line).

**When**
- `result = call_uid(svc.update_control, UO, control_id=A.id, control_in=AccessControlUpdate(target="/sales"), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `not ({c.key for c in inspect(result).mapper.column_attrs} & inspect(result).expired_attributes)`.
3. committed: re-read A: `target == "/sales"`, `type == PAGE`, `role == OWNER`, `workspace_id == W1.id`.

### ACS-U-02 — a null field leaves the stored value
- **Rules:** `update_control` R3; R1 (caller UO through call_uid)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = rule (commit point after this line).

**When**
- `result = call_uid(svc.update_control, UO, control_id=A.id, control_in=AccessControlUpdate(target=None, role=FINANCE), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. committed: re-read A: `target == "/orders"`, `role == FINANCE`.

### ACS-U-03 — an empty update changes nothing and still commits
- **Rules:** `update_control` R3; R1 (caller UO through call_uid)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = rule (commit point after this line).

**When**
- spies: `result = call_uid(svc.update_control, UO, control_id=A.id, control_in=AccessControlUpdate(), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. mock called: `cm.call_count >= 1`.
3. unchanged: unchanged(A).

### ACS-U-04 — W0's row (lower id) answers None, no commit, no rollback
- **Rules:** `update_control` R2; TX4; R1 (caller UO through call_uid)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A0 = rule, but `workspace_id W0.id`.
2. A = rule (commit point after this line).
3. pending P.

**When**
- spies: `result = call_uid(svc.update_control, UO, control_id=A0.id, control_in=AccessControlUpdate(target="/sales"), workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `not db.dirty`.
5. session: `db.get(AccessControl, P_ID) is P`.
6. unchanged: unchanged(A0).

### ACS-U-05 — W2's row (higher id) answers None
- **Rules:** `update_control` R2; TX4; R1 (caller UO through call_uid)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = rule.
2. A9 = rule, but `workspace_id W2.id` (commit point after this line).

**When**
- `result = call_uid(svc.update_control, UO, control_id=A9.id, control_in=AccessControlUpdate(target="/sales"), workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. session: `not db.dirty`.
3. unchanged: unchanged(A9).

### ACS-U-06 — an unknown id answers None
- **Rules:** `update_control` R2; R1 (caller UO through call_uid)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = rule (commit point after this line).

**When**
- `result = call_uid(svc.update_control, UO, control_id=MISSING, control_in=AccessControlUpdate(target="/sales"), workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. session: `not db.dirty`.
3. unchanged: unchanged(A).

### ACS-U-07 — a failing commit rolls back, discards other pending changes, saves nothing
- **Rules:** `update_control` R4; TX3; R1 (caller UO through call_uid)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = rule (commit point after this line).
2. extra row X.

**When**
- failing commit: `call_uid(svc.update_control, UO, control_id=A.id, control_in=AccessControlUpdate(target="/sales"), workspace_id=W1.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count == 1`.
3. count: x_gone.
4. unchanged: unchanged(A).

### ACS-U-08 — a failing re-read after the commit leaves the change saved
- **Rules:** `update_control` R4; TX3 (as TC5); R1 (caller UO through call_uid)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = rule (commit point after this line).

**When**
- failing refresh: `call_uid(svc.update_control, UO, control_id=A.id, control_in=AccessControlUpdate(target="/sales"), workspace_id=W1.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: re-read A: `target == "/sales"`.

### ACS-U-10 — a ground-team-manager may not update
- **Rules:** `update_control` R1 [BUG-1875]
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UZ, "ground-team-manager").
2. A = rule (commit point after this line).

**When**
- `svc.update_control(db, control_id=A.id, control_in=AccessControlUpdate(target="/sales"), workspace_id=W1.id, user_id=UZ.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.dirty`.
5. unchanged: unchanged(A).

### ACS-U-11 — a non-owner is refused before the lookup: an unknown id is 403, not None
- **Rules:** `update_control` R1 [BUG-1875], R2
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UA, "finance").
2. A = rule (commit point after this line).

**When**
- `svc.update_control(db, control_id=MISSING, control_in=AccessControlUpdate(target="/sales"), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.dirty`.
5. nothing written.

### ACS-U-12 — the owner of W2 asking about W1's row is refused
- **Rules:** `update_control` R1 [BUG-1875]
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UZ, "ground-team").
2. mem(UZ, "owner", ws=W2).
3. A = rule (commit point after this line).

**When**
- `svc.update_control(db, control_id=A.id, control_in=AccessControlUpdate(target="/sales"), workspace_id=W1.id, user_id=UZ.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.dirty`.
5. unchanged: unchanged(A).

### ACS-U-13 — an update refusal neither commits nor rolls back: a pending row of the session survives
- **Rules:** `update_control` R1 [BUG-1875] (raised before the `try`)
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UA, "finance").
2. A = rule (commit point after this line).
3. pending P.

**When**
- spies: `svc.update_control(db, control_id=A.id, control_in=AccessControlUpdate(target="/sales"), workspace_id=W1.id, user_id=UA.id)` (the `pytest.raises` block inside the spies).

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. mock called: `cm.call_count == 0`.
5. mock called: `rb.call_count == 0`.
6. session: `not db.new and not db.dirty and not db.deleted`.
7. session: `db.get(AccessControl, P_ID) is P`.
8. count: `db.scalar(select(func.count()).select_from(AccessControl).where(AccessControl.id == P_ID)) == 1`.
9. unchanged: unchanged(A).

## `AccessControlService.delete_control`

### ACS-D-01 — deletes the row, committed, returns True
- **Rules:** `delete_control` R3; TX1, TX2; R1 (caller UO through call_uid)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = rule.
2. B = rule, but `target "/b"` (commit point after this line).

**When**
- `result = call_uid(svc.delete_control, UO, control_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. committed: no `access_control` row has id `A.id`.
3. committed: the row B still exists.

### ACS-D-02 — W0's row (lower id) answers False, no commit, no rollback
- **Rules:** `delete_control` R2; TX4; R1 (caller UO through call_uid)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A0 = rule, but `workspace_id W0.id`.
2. A = rule (commit point after this line).
3. pending P.

**When**
- spies: `result = call_uid(svc.delete_control, UO, control_id=A0.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `not db.deleted`.
5. session: `db.get(AccessControl, P_ID) is P`.
6. count: W0 has exactly 1 `access_control` row (A0 is not deleted).
7. count: W1 has exactly 1 `access_control` row (A).

### ACS-D-03 — W2's row (higher id) answers False
- **Rules:** `delete_control` R2; TX4; R1 (caller UO through call_uid)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = rule.
2. A9 = rule, but `workspace_id W2.id` (commit point after this line).

**When**
- `result = call_uid(svc.delete_control, UO, control_id=A9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.
2. session: `not db.deleted`.
3. nothing written.

### ACS-D-04 — an unknown id answers False
- **Rules:** `delete_control` R2; R1 (caller UO through call_uid)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = rule (commit point after this line).

**When**
- `result = call_uid(svc.delete_control, UO, control_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.
2. session: `not db.deleted`.
3. nothing written.

### ACS-D-05 — a failing commit rolls back; the row stays and pending changes are discarded
- **Rules:** `delete_control` R4; TX3; R1 (caller UO through call_uid)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = rule (commit point after this line).
2. extra row X.

**When**
- failing commit: `call_uid(svc.delete_control, UO, control_id=A.id, workspace_id=W1.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count == 1`.
3. count: x_gone.
4. re-read A: the row exists, `target == "/orders"`.

### ACS-D-07 — a ground-team member may not delete
- **Rules:** `delete_control` R1 [BUG-1875]
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UA, "ground-team").
2. A = rule (commit point after this line).

**When**
- `svc.delete_control(db, control_id=A.id, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.deleted`.
5. nothing written.

### ACS-D-08 — a viewer is refused before the lookup: an unknown id is 403, not False
- **Rules:** `delete_control` R1 [BUG-1875], R2
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UZ, "viewer").
2. A = rule (commit point after this line).

**When**
- `svc.delete_control(db, control_id=MISSING, workspace_id=W1.id, user_id=UZ.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.deleted`.
5. nothing written.

### ACS-D-09 — the owner of W0 (row built first) is refused in W1
- **Rules:** `delete_control` R1 [BUG-1875]
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UA, "owner", ws=W0).
2. mem(UA, "member").
3. A = rule (commit point after this line).

**When**
- `svc.delete_control(db, control_id=A.id, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. session: `not db.deleted`.
5. nothing written.

### ACS-D-10 — a delete refusal neither commits nor rolls back: a pending row of the session survives
- **Rules:** `delete_control` R1 [BUG-1875] (raised before the `try`)
- **Kind:** bug
- **Expect:** xfail BUG-1875
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. mem(UA, "finance").
2. A = rule (commit point after this line).
3. pending P.

**When**
- spies: `svc.delete_control(db, control_id=A.id, workspace_id=W1.id, user_id=UA.id)` (the `pytest.raises` block inside the spies).

**Then**
1. raises: `PermissionDeniedError`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENY`.
4. mock called: `cm.call_count == 0`.
5. mock called: `rb.call_count == 0`.
6. session: `not db.new and not db.dirty and not db.deleted`.
7. session: `db.get(AccessControl, P_ID) is P`.
8. count: `db.scalar(select(func.count()).select_from(AccessControl).where(AccessControl.id == P_ID)) == 1`.
9. count: W1 has exactly 1 `access_control` row (A).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_by_id` R1, `update_control` R2, `delete_control` R2 (404 `Access control not found`, 204) | `/access-control/` endpoints (integration) | `None` / `False` become 404 with that text; delete answers 204 |
| `get_controls` R4 (limit bounds, BUG-1409) | `GET /access-control/` | `limit=0` → 422 |
| `create_control` R1 (endpoint passes `current_user.id`) | `/access-control/` endpoints | a non-owner gets 403 through the API |

## Spec gaps
None. Gaps 1–3 of revision 1 closed by the spec's Gap log G1–G3 (2026-11-04).

## Retired IDs
- ACS-C-06 — the owner's create with `user_id`; identical to ACS-C-01 once every write passes `user_id`.
- ACS-U-09 — the owner's update with `user_id`; identical to ACS-U-01.
- ACS-D-06 — the owner's delete with `user_id`; identical to ACS-D-01.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_controls` | R1 | ACS-L-01, L-07, L-09 |
| `get_controls` | R1 [BUG-2255] | ACS-L-02, L-03 |
| `get_controls` | R2 | ACS-L-04, L-08 |
| `get_controls` | R3 | ACS-L-05, L-06, L-13 |
| `get_controls` | R4 | ACS-L-06 … L-11 |
| `get_controls` | R5; TX5 | ACS-L-12 |
| `get_by_id` | R1 | ACS-G-01 … G-05 |
| `get_by_id` | R2; TX5 | ACS-G-06 |
| `create_control` | R1 [BUG-1875] | ACS-C-07 … C-23; signature alarm ACS-C-24 |
| `create_control` | R2 | ACS-C-01, C-02 |
| `create_control` | R3; TX1, TX2 | ACS-C-01 |
| `create_control` | TX3 | ACS-C-03, C-04, C-05 |
| `update_control` | R1 [BUG-1875] | ACS-U-10 … U-13; signature alarm ACS-C-24 |
| `update_control` | R2; TX4 | ACS-U-04, U-05, U-06 |
| `update_control` | R3 | ACS-U-01, U-02, U-03 |
| `update_control` | R4; TX1, TX2, TX3 | ACS-U-01, U-07, U-08 |
| `delete_control` | R1 [BUG-1875] | ACS-D-07 … D-10; signature alarm ACS-C-24 |
| `delete_control` | R2; TX4 | ACS-D-02, D-03, D-04 |
| `delete_control` | R3; TX1 | ACS-D-01 |
| `delete_control` | R4; TX3 | ACS-D-05 |
