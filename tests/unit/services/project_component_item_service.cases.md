# Test cases — `app/services/project_component_item_service.py`

> **Spec:** `tests/unit/services/project_component_item_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 3 (2026-11-06) — from `project_component_item_service.verify.md`: Finding 1 → new PCIS-L-20 (spied successful one-component read); Finding 2 → new PCIS-U-13 (W0 line updated through W1 → `None`) and PCIS-D-05 (W2 line deleted through W1 → `False`), each with spies, a `session:` line before the re-read, the line unchanged and nothing written. The spec states this as today's behaviour (R1 of both writers: found as `get_by_id`, another workspace's → `None` / `False`); the 404 `Project component item not found` is the endpoint's (Deferred), so these are pass cards, not xfail. Also new PCIS-G-09 (spied successful one-row read, requested with the revision). No card changed or retired.
> Revision 2 (2026-11-05) — spec fill-gaps G1: the schema module is named in Conventions. No card changed, added or retired.
> **Counts:** 68 cases · 49 expected-to-pass · 19 expected-to-fail (bugs) · 2 deferred

## Reviewer summary
- **Per callable:** `get_items` 20 (6 bug) · `get_by_id` 9 (1 bug) · `create_component_item` 21 (8 bug) · `update_component_item` 13 (4 bug) · `delete_component_item` 5. `_guard_component` and `_filter_accessible_items` are internal and covered through these.
- **Depth:** lighter (skill step 1a): the spec's "Stock and money" section shows these rows are a plan figure only, writing no stock, ledger or money; one card checks that the stock and ledger tables stay untouched. One card per rule and Errors row, one negative per filter, one paging boundary per rule. Full depth on BUG-2308 (filter after paging): three hidden rows on a private project are built first, so they sort ahead by `id` (today's physical order and the intended `id` order): `limit=2` strict, `skip=1` non-strict (`Author: claude`).
- **BUG-1012 (owner, HR-16):** one card per shape: W0 item (lower id), W2 item (higher id), unknown id (today `IntegrityError`); BUG-2306: a deleted catalog item. The guard runs first: a private component with a foreign item answers 403 (passes today).
- **BUG-2307 (`qty`):** both sides of both bounds: 0 / 1 and 2147483647 / 2147483648 on create; 0 and 2147483648 on update; a negative on create. The passing sides are stored; the failing sides are schema xfails.
- **Transactions (I-TC1–I-TC6):** per writer a success card with spies, a guard refusal discarding an uncommitted extra row (one rollback), a failing commit and (create, update) a failing refresh; not-found update/delete and every read keep an unflushed pending row (no commit, no rollback).
- **Notable design choices:** PJ1, C1 and the catalog item I1 have explicit ids (XID) so an event's `project_id`, `component_id` and `item_id` (catalog id, not the row id) cannot be confused by chance. The workspace-wide order is base `get_by_workspace`'s (BUG-100, tested in `tests/unit/dao/base.cases.md`): no order card here.
- **Revision 3:** every read path, success included, now has a spy card; both writers are tested on another workspace's line (W0 for update, W2 for delete): the service answers `None` / `False` (spec R1), which the endpoint turns into 404.
- **Needs a decision:** None. Gap 1 closed (spec G1).

## Conventions for this module

**IDs.** `PCIS` = `app/services/project_component_item_service.py`. `L` get_items · `G` get_by_id · `C` create_component_item · `U` update_component_item · `D` delete_component_item.

**Actors and fixed values.**
- `svc` = `project_component_item_service` (`from app.services.project_component_item_service import ProjectComponentItemService, project_component_item_service`). `db` = the test's real session, first positional argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- Models from `app.models.<module>`: `factory.Factory`, `project.Project`, `project_component.ProjectComponent`, `project_component_item.ProjectComponentItem`, `item.Item`, `project_event.ProjectEvent`, `workspace_member.WorkspaceMember`, `project_member.ProjectMember`. `ProjectComponentItemCreate`, `ProjectComponentItemUpdate` (`app.schemas.project_component_item`). `HTTPException` (`fastapi`); `PydanticValidationError` = `pydantic.ValidationError`; `DataError`, `IntegrityError` (`sqlalchemy.exc`); `event`, `insert`, `select`, `func`, `text` (`sqlalchemy`); `patch` (`unittest.mock`); `os`, `datetime`.
- MISSING = `999999999`. T0 = `datetime(2025, 12, 1, 8, 0, 0)`. XID(k) = `800_000_000 + (os.getpid() % 1_000_000) * 10 + k`. MAXQ = `2147483647`.
- NOCOMP = `"Project component not found"`. NOACCESS = `"You do not have access to this project"`.

**Standing rows** (every test, built in this order, each added and flushed, no Given line):
- W0, W1, W2 = `make_workspace(db)` (so `W0.id < W1.id < W2.id`). U1 = `make_profile(db, name="Ana Rahman")`, U2 = `make_profile(db, name="Bilal Khan")`, UG = `make_profile(db, name="Mia Khan")`. In W1: `WorkspaceMember(workspace_id=W1.id, user_id=…, role=…, status="active")` for U1 `"ground-team"`, U2 `"owner"`, UG `"ground-team"`. U2 is privileged; UG is the plain caller.
- F0, F1, F9 = `Factory(workspace_id=W0.id / W1.id / W2.id, name="Factory Zero" / "Factory One" / "Factory Nine", abbreviation="F0" / "F1" / "F9")`.
- Projects, all `description="Main"`, `created_by=U1.id`: PJ0 = (W0, F0, `"Project Zero"`); PJ1 = (W1, F1, `"Project One"`, `id=XID(1)`); PJP = (W1, F1, `"Secret"`, `visibility="invited_only"`); PJD = (W1, F1, `"Gone"`, `is_deleted=True`, `deleted_at=T0`, `deleted_by=U1.id`); PJ9 = (W2, F9, `"Project Nine"`).
- Components `ProjectComponent(workspace_id, project_id, name)`: C0 = (W0, PJ0, `"Cellar"`); C1 = (W1, PJ1, `"Roof"`, `id=XID(5)`); C2 = (W1, PJ1, `"Wall"`); CP = (W1, PJP, `"Vault"`); CD = (W1, PJD, `"Floor"`); C9 = (W2, PJ9, `"Deck"`).
- Catalog items `Item(workspace_id, name, name_normalized, unit="pcs")`: I0 = (W0, `"Nut"`, `"nut"`); I1 = (W1, `"Bolt"`, `"bolt"`, `id=XID(8)`); I9 = (W2, `"Washer"`, `"washer"`); IDL = (W1, `"Old bolt"`, `"old bolt"`, `is_active=False`).
- No component item or event row exists unless the Given builds it.

**Given rows.** Built directly (never through `svc`), added and flushed one at a time in the order written, so ids rise in that order. After "but" a line names every other column that differs.
- **line(C, q)** = `ProjectComponentItem(workspace_id=C.workspace_id, project_component_id=C.id, item_id=I1.id, qty=q)`.
- **pmem(P, U)** = `ProjectMember(workspace_id=P.workspace_id, project_id=P.id, user_id=U.id, assigned_by=U1.id)`.
- **commit point** = after the last Given line the test runs `db.commit()` (releases a savepoint). Snapshots for `unchanged`, `nothing written` and `no stock` are taken there.
- **extra row X** (after the commit point) = `X = ProjectComponentItem(workspace_id=W2.id, project_component_id=C9.id, item_id=I9.id, qty=1)`, `db.add(X)`, `db.flush()`, `X_ID = X.id`; not committed.
- **pending P** (after the commit point) = `P = ProjectComponentItem(workspace_id=W2.id, project_component_id=C9.id, item_id=I9.id, qty=2)`, `db.add(P)`, **no flush**.
- A Given line written as code is a step run exactly as written.

**Externals.** None. Nothing is mocked except where a card says so.

**Named checks.**
- **re-read X** = `db.expire_all()`, then `db.get(<model>, X.id)`. **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **nothing written** = the numbers of `project_component_items` rows and of `project_events` rows (all workspaces) equal their values at the commit point.
- **no stock** = `db.execute(text("SELECT count(*) FROM <t>")).scalar()` for `t` in `inventory`, `machine_items`, `project_component_item_ledger` each equals its value at the commit point.
- **x_gone** = `db.scalar(select(func.count()).select_from(ProjectComponentItem).where(ProjectComponentItem.id == X_ID)) == 0`.
- **events(P, t)** = `db.expire_all()`, then the `ProjectEvent` rows with `project_id == P.id` and `event_type == t`, ordered by `id`. **all_events(P)** = the same without the type filter. "that event" = the one row just counted.
- **idset(r)** = `{x.id for x in r}`.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the call only (inside any `raises` block).
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the call. **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "refresh", side_effect=RuntimeError("boom")):` around the call.
- `raises: HTTPException` = plain `with pytest.raises(HTTPException) as exc:` around the call, **no** savepoint; then `exc.value.status_code`, `exc.value.detail`, one per line. `raises: DataError in a savepoint` = `with pytest.raises(DataError):` then `with db.begin_nested():` then the call. A `schema` card wraps only building the schema.
- `session:` lines check `db.new` / `db.dirty` / `db.deleted` right after the call, before any re-read or `expire_all`.
- `committed:` lines: before the first, the test runs `db.rollback()` once; each line then reads with a fresh query.
- **recorder** = a Given step: `stmts = []`, `event.listen(db.connection(), "before_cursor_execute", rec)` where `rec` appends `statement`; `event.remove` right after the When.

**xfail cards.** Strict unless the Expect line says `(non-strict)`: `pytest.mark.xfail(strict=True, reason="BUG-n")`. Write the call and checks exactly as shown, also when the call uses something that does not exist yet.

**Race simulations.** None.

## `ProjectComponentItemService.get_items`

### PCIS-L-01 — with a component: that component's lines only
- **Rules:** `get_items` R1; `_guard_component` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. LA = line(C1, 5).
2. LB = line(C1, 2).
3. LW = line(C2, 7).

**When**
- `result = svc.get_items(db, workspace_id=W1.id, user_id=UG.id, project_component_id=C1.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {LA.id, LB.id}`.

### PCIS-L-02 — component id 0 is a component id: 404
- **Rules:** `get_items` R1 [BUG-2309]
- **Kind:** bug
- **Expect:** xfail BUG-2309
- **Fails today on:** Then 1 (no error: the workspace-wide list is returned)

**Given**
1. LA = line(C1, 5).

**When**
- `svc.get_items(db, workspace_id=W1.id, user_id=U2.id, project_component_id=0)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.

### PCIS-L-03 — a private component the caller may not open is 403, with no rollback
- **Rules:** `get_items` R1, R5; I-TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. LP = line(CP, 3) (commit point after this line).
2. pending P.

**When**
- spies: `svc.get_items(db, workspace_id=W1.id, user_id=UG.id, project_component_id=CP.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOACCESS`.
4. mock called: `rb.call_count == 0`.
5. session: `P in db.new`.

### PCIS-L-04 — a W0 component is 404 in W1
- **Rules:** `get_items` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. L0 = `ProjectComponentItem(workspace_id=W0.id, project_component_id=C0.id, item_id=I0.id, qty=1)`.

**When**
- `svc.get_items(db, workspace_id=W1.id, user_id=U2.id, project_component_id=C0.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.

### PCIS-L-05 — a deleted project's component is 404 for the project (pass-through)
- **Rules:** `get_items` R1 (manager `require_component_access` R2 [BUG-1278])
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (no error: the lines are listed)

**Given**
1. LD = line(CD, 4).

**When**
- `svc.get_items(db, workspace_id=W1.id, user_id=U2.id, project_component_id=CD.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {PJD.id} not found"`.

### PCIS-L-06 — without a component: every W1 line a privileged caller may open, no other workspace
- **Rules:** `get_items` R2; `_filter_accessible_items` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. L0 = `ProjectComponentItem(workspace_id=W0.id, project_component_id=C0.id, item_id=I0.id, qty=1)`.
2. LA = line(C1, 5).
3. LP = line(CP, 3).
4. L9 = `ProjectComponentItem(workspace_id=W2.id, project_component_id=C9.id, item_id=I9.id, qty=1)`.

**When**
- `result = svc.get_items(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {LA.id, LP.id}`.

### PCIS-L-07 — without a component: a plain caller does not see a private project's lines
- **Rules:** `_filter_accessible_items` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. LP = line(CP, 3).
2. LA = line(C1, 5).

**When**
- `result = svc.get_items(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {LA.id}`.

### PCIS-L-08 — membership of another private project does not open this one
- **Rules:** `_filter_accessible_items` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. PJQ = `Project(workspace_id=W1.id, factory_id=F1.id, name="Other secret", description="Main", created_by=U1.id, visibility="invited_only")`.
2. CQ = `ProjectComponent(workspace_id=W1.id, project_id=PJQ.id, name="Annex")`.
3. pmem(PJQ, UG).
4. LQ = line(CQ, 6).
5. LP = line(CP, 3).

**When**
- `result = svc.get_items(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {LQ.id}`.

### PCIS-L-09 — a W1 line on a W2 component is left out
- **Rules:** `get_items` R6; `_filter_accessible_items` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. LA = line(C1, 5).
2. LX = line(C9, 1), but `workspace_id W1.id` (invalid data).

**When**
- `result = svc.get_items(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {LA.id}`.

### PCIS-L-10 — a line on a W1 component whose project is in W2 is left out
- **Rules:** `_filter_accessible_items` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. CX = `ProjectComponent(workspace_id=W1.id, project_id=PJ9.id, name="Stray")` (invalid data).
2. LA = line(C1, 5).
3. LO = line(CX, 1).

**When**
- `result = svc.get_items(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {LA.id}`.

### PCIS-L-11 — lines of a deleted project are not listed
- **Rules:** `get_items` R3; `_filter_accessible_items` R2 [BUG-1278]
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (LD is listed)

**Given**
1. LD = line(CD, 4).
2. LA = line(C1, 5).

**When**
- `result = svc.get_items(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {LA.id}`.

### PCIS-L-12 — hidden lines ahead of the page do not shorten it (limit)
- **Rules:** `get_items` R4 [BUG-2308]
- **Kind:** bug
- **Expect:** xfail BUG-2308
- **Fails today on:** Then 1 (the page is two hidden lines, filtered away: `[]`)

**Given**
1. H1 = line(CP, 1).
2. H2 = line(CP, 2).
3. H3 = line(CP, 3).
4. VD = line(C1, 4).
5. VE = line(C1, 5).

**When**
- `result = svc.get_items(db, workspace_id=W1.id, user_id=UG.id, skip=0, limit=2)`.

**Then**
1. returns: `idset(result) == {VD.id, VE.id}`.

### PCIS-L-13 — hidden lines ahead of the page do not shift it (skip)
- **Rules:** `get_items` R4 [BUG-2308]
- **Kind:** bug
- **Expect:** xfail BUG-2308 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (skip 1 removes a hidden line: VD and VE both come back)

**Given**
1. H1 = line(CP, 1).
2. H2 = line(CP, 2).
3. H3 = line(CP, 3).
4. VD = line(C1, 4).
5. VE = line(C1, 5).

**When**
- `result = svc.get_items(db, workspace_id=W1.id, user_id=UG.id, skip=1, limit=1000)`.

**Then**
1. returns: `idset(result) == {VE.id}`.

### PCIS-L-14 — the access filter does not read one component per row
- **Rules:** `get_items` R4 [BUG-2308]
- **Kind:** bug
- **Expect:** xfail BUG-2308
- **Fails today on:** Then 2 (one `project_components` read per line: 5)

**Given**
1. K1 … K5 = five `ProjectComponent(workspace_id=W1.id, project_id=PJ1.id, name=…)`, names `"K1"` … `"K5"`.
2. one line(Kn, 1) on each of K1 … K5.
3. recorder.

**When**
- `result = svc.get_items(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `len(result) == 5`.
2. statement: `sum(1 for s in stmts if "project_components" in s) <= 1`.

### PCIS-L-15 — limit 0 gives an empty list
- **Rules:** `get_items` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. LA = line(C1, 5).

**When**
- `result = svc.get_items(db, workspace_id=W1.id, user_id=U2.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PCIS-L-16 — the default limit is 100
- **Rules:** `get_items` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `db.execute(insert(ProjectComponentItem), [dict(workspace_id=W1.id, project_component_id=C1.id, item_id=I1.id, qty=1) for i in range(101)])`, then `db.expire_all()`.

**When**
- `result = svc.get_items(db, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `len(result) == 100`.

### PCIS-L-17 — a negative limit fails in the database
- **Rules:** `get_items` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. LA = line(C1, 5).

**When**
- `svc.get_items(db, workspace_id=W1.id, user_id=U2.id, limit=-1)`.

**Then**
1. raises: `DataError` in a savepoint.

### PCIS-L-18 — a negative skip fails in the database
- **Rules:** `get_items` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. LA = line(C1, 5).

**When**
- `svc.get_items(db, workspace_id=W1.id, user_id=U2.id, skip=-1)`.

**Then**
1. raises: `DataError` in a savepoint.

### PCIS-L-19 — the workspace-wide read neither commits nor rolls back
- **Rules:** `get_items` R5; I-TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. LA = line(C1, 5) (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.get_items(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {LA.id}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db.new`.

### PCIS-L-20 — a successful one-component read neither commits nor rolls back
- **Rules:** `get_items` R1, R5; I-TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. LA = line(C1, 5) (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.get_items(db, workspace_id=W1.id, user_id=UG.id, project_component_id=C1.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {LA.id}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db.new`.

## `ProjectComponentItemService.get_by_id`

### PCIS-G-01 — a line the caller may open is returned
- **Rules:** `get_by_id` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. LA = line(C1, 5).

**When**
- `result = svc.get_by_id(db, item_id=LA.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == LA.id`, `result.qty == 5`.

### PCIS-G-02 — an unknown id is None, with no commit and no rollback
- **Rules:** `get_by_id` R1, R3; I-TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. LA = line(C1, 5) (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.get_by_id(db, item_id=MISSING, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is None`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db.new`.

### PCIS-G-03 — id 0 is None
- **Rules:** `get_by_id` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. LA = line(C1, 5).

**When**
- `result = svc.get_by_id(db, item_id=0, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.

### PCIS-G-04 — a W0 line (lower id) is None in W1
- **Rules:** `get_by_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. L0 = `ProjectComponentItem(workspace_id=W0.id, project_component_id=C0.id, item_id=I0.id, qty=1)`.
2. LA = line(C1, 5).

**When**
- `result = svc.get_by_id(db, item_id=L0.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.

### PCIS-G-05 — a W2 line (higher id) is None in W1
- **Rules:** `get_by_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. LA = line(C1, 5).
2. L9 = `ProjectComponentItem(workspace_id=W2.id, project_component_id=C9.id, item_id=I9.id, qty=1)`.

**When**
- `result = svc.get_by_id(db, item_id=L9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.

### PCIS-G-06 — a private project's line is 403 for a plain caller, with no rollback
- **Rules:** `get_by_id` R2, R3
- **Kind:** error
- **Expect:** pass

**Given**
1. LP = line(CP, 3) (commit point after this line).
2. pending P.

**When**
- `svc.get_by_id(db, item_id=LP.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOACCESS`.
4. session: `P in db.new`.

### PCIS-G-07 — a privileged caller opens a private project's line
- **Rules:** `get_by_id` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. LP = line(CP, 3).

**When**
- `result = svc.get_by_id(db, item_id=LP.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == LP.id`.

### PCIS-G-08 — a deleted project's line is 404 (pass-through)
- **Rules:** `get_by_id` R2 (manager `require_component_access` R2 [BUG-1278])
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (no error: the line is returned)

**Given**
1. LD = line(CD, 4).

**When**
- `svc.get_by_id(db, item_id=LD.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {PJD.id} not found"`.

### PCIS-G-09 — a successful one-row read neither commits nor rolls back
- **Rules:** `get_by_id` R2, R3; I-TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. LA = line(C1, 5) (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.get_by_id(db, item_id=LA.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == LA.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db.new`.

## `ProjectComponentItemService.create_component_item`

### PCIS-C-01 — the line is stored, committed once and returned re-read; no stock moves
- **Rules:** `create_component_item` R5, R7; I-TC1, I-TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No component item in W1 (commit point after this line).

**When**
- spies: `result = svc.create_component_item(db, item_in=ProjectComponentItemCreate(project_component_id=C1.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id is not None`, `result.qty == 5`.
2. mock called: `cm.call_count == 1`.
3. mock called: `rb.call_count == 0`.
4. committed: the row `result.id` has `workspace_id == W1.id`, `project_component_id == C1.id`, `item_id == I1.id`, `qty == 5`.
5. unchanged: no stock.

### PCIS-C-02 — creating a line logs item_added with the catalog item id
- **Rules:** `create_component_item` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No component item in W1 (commit point after this line).

**When**
- `result = svc.create_component_item(db, item_in=ProjectComponentItemCreate(project_component_id=C1.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: events(PJ1, "item_added") has exactly 1 row.
3. event: that event `workspace_id == W1.id`, `performed_by == UG.id`, `description == "Added item to component (qty 5)"`.
4. event: that event `metadata_json == {"item_id": I1.id, "qty": "5", "component_id": C1.id, "component_name": "Roof"}`.
5. count: all_events(PJ1) has exactly 1 row.

### PCIS-C-03 — the same item may be planned twice on one component
- **Rules:** `create_component_item` R5 (D2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. LA = line(C1, 5) (commit point after this line).

**When**
- `result = svc.create_component_item(db, item_in=ProjectComponentItemCreate(project_component_id=C1.id, item_id=I1.id, qty=2), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id != LA.id`.
2. committed: C1 has exactly 2 `project_component_items` rows with `item_id == I1.id`.

### PCIS-C-04 — a private component: 403, rolled back once, pending changes discarded
- **Rules:** `create_component_item` R1; I-TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. No component item in W1 (commit point after this line).
2. extra row X.

**When**
- spies: `svc.create_component_item(db, item_in=ProjectComponentItemCreate(project_component_id=CP.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOACCESS`.
4. mock called: `rb.call_count == 1`.
5. session: `not db.new`.
6. count: x_gone.
7. nothing written.

### PCIS-C-05 — a private component with a foreign item answers 403: the guard runs first
- **Rules:** `create_component_item` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. No component item in W1 (commit point after this line).

**When**
- `svc.create_component_item(db, item_in=ProjectComponentItemCreate(project_component_id=CP.id, item_id=I9.id, qty=5), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOACCESS`.
4. nothing written.

### PCIS-C-06 — an unknown component is 404, nothing written
- **Rules:** `create_component_item` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. No component item in W1 (commit point after this line).

**When**
- `svc.create_component_item(db, item_in=ProjectComponentItemCreate(project_component_id=MISSING, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.
4. session: `not db.new`.
5. nothing written.

### PCIS-C-07 — a W2 component is 404 in W1
- **Rules:** `create_component_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No component item in W1 (commit point after this line).

**When**
- `svc.create_component_item(db, item_in=ProjectComponentItemCreate(project_component_id=C9.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.
4. nothing written.

### PCIS-C-08 — a deleted project's component is 404, nothing written (pass-through)
- **Rules:** `create_component_item` R1 (manager `require_component_access` R2 [BUG-1278])
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (no error: the line is created)

**Given**
1. No component item in W1 (commit point after this line).

**When**
- `svc.create_component_item(db, item_in=ProjectComponentItemCreate(project_component_id=CD.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {PJD.id} not found"`.
4. nothing written.

### PCIS-C-09 — a W2 item (higher id) is 404, nothing written
- **Rules:** `create_component_item` R3 [BUG-1012]
- **Kind:** bug
- **Expect:** xfail BUG-1012
- **Fails today on:** Then 1 (no error: the line is stored with the W2 item)

**Given**
1. No component item in W1 (commit point after this line).

**When**
- `svc.create_component_item(db, item_in=ProjectComponentItemCreate(project_component_id=C1.id, item_id=I9.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {I9.id} not found"`.
4. session: `not db.new`.
5. nothing written.

### PCIS-C-10 — a W0 item (lower id) is 404, nothing written
- **Rules:** `create_component_item` R3 [BUG-1012]
- **Kind:** bug
- **Expect:** xfail BUG-1012
- **Fails today on:** Then 1 (no error: the line is stored with the W0 item)

**Given**
1. No component item in W1 (commit point after this line).

**When**
- `svc.create_component_item(db, item_in=ProjectComponentItemCreate(project_component_id=C1.id, item_id=I0.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {I0.id} not found"`.
4. nothing written.

### PCIS-C-11 — an unknown item id is 404, not a database error
- **Rules:** `create_component_item` R3 [BUG-1012]
- **Kind:** bug
- **Expect:** xfail BUG-1012
- **Fails today on:** Then 1 (the call raises IntegrityError: the foreign key fails at the flush)

**Given**
1. No component item in W1 (commit point after this line).

**When**
- `svc.create_component_item(db, item_in=ProjectComponentItemCreate(project_component_id=C1.id, item_id=MISSING, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {MISSING} not found"`.
4. nothing written.

### PCIS-C-12 — an unknown item id today rolls back and nothing is saved
- **Rules:** `create_component_item` R7; I-TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. No component item in W1 (commit point after this line).
2. extra row X.

**When**
- spies: `svc.create_component_item(db, item_in=ProjectComponentItemCreate(project_component_id=C1.id, item_id=MISSING, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: an exception is raised (`pytest.raises(Exception)`; today `IntegrityError`, after BUG-1012 `HTTPException`).
2. mock called: `rb.call_count == 1`.
3. count: x_gone.
4. nothing written.

### PCIS-C-13 — a deleted catalog item is 404, nothing written
- **Rules:** `create_component_item` R3a [BUG-2306]
- **Kind:** bug
- **Expect:** xfail BUG-2306
- **Fails today on:** Then 1 (no error: the line is stored)

**Given**
1. No component item in W1 (commit point after this line).

**When**
- `svc.create_component_item(db, item_in=ProjectComponentItemCreate(project_component_id=C1.id, item_id=IDL.id, qty=5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {IDL.id} not found"`.
4. nothing written.

### PCIS-C-14 — qty 0 is refused by the schema
- **Rules:** `create_component_item` R4 [BUG-2307]
- **Kind:** bug
- **Expect:** xfail BUG-2307
- **Fails today on:** Then 1 (the schema accepts 0)

**Given**
1. No component item in W1.

**When**
- build `ProjectComponentItemCreate(project_component_id=C1.id, item_id=I1.id, qty=0)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCIS-C-15 — a negative qty is refused by the schema
- **Rules:** `create_component_item` R4 [BUG-2307]
- **Kind:** bug
- **Expect:** xfail BUG-2307
- **Fails today on:** Then 1 (the schema accepts -3)

**Given**
1. No component item in W1.

**When**
- build `ProjectComponentItemCreate(project_component_id=C1.id, item_id=I1.id, qty=-3)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCIS-C-16 — qty above the integer range is refused by the schema
- **Rules:** `create_component_item` R4 [BUG-2307]
- **Kind:** bug
- **Expect:** xfail BUG-2307
- **Fails today on:** Then 1 (the schema accepts 2147483648)

**Given**
1. No component item in W1.

**When**
- build `ProjectComponentItemCreate(project_component_id=C1.id, item_id=I1.id, qty=2147483648)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCIS-C-17 — qty 1 is stored
- **Rules:** `create_component_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No component item in W1 (commit point after this line).

**When**
- `result = svc.create_component_item(db, item_in=ProjectComponentItemCreate(project_component_id=C1.id, item_id=I1.id, qty=1), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.qty == 1`.
2. re-read the row `result.id`: `qty == 1`.

### PCIS-C-18 — qty 2147483647 is stored
- **Rules:** `create_component_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No component item in W1 (commit point after this line).

**When**
- `result = svc.create_component_item(db, item_in=ProjectComponentItemCreate(project_component_id=C1.id, item_id=I1.id, qty=MAXQ), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.qty == 2147483647`.
2. re-read the row `result.id`: `qty == 2147483647`.

### PCIS-C-19 — a failing commit rolls back once and nothing is saved
- **Rules:** `create_component_item` R7; I-TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. No component item in W1 (commit point after this line).

**When**
- failing commit: `svc.create_component_item(db, item_in=ProjectComponentItemCreate(project_component_id=C1.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count == 1`.
3. nothing written.

### PCIS-C-20 — a failing re-read after the commit leaves the line and its event saved
- **Rules:** `create_component_item` R7; I-TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. No component item in W1 (commit point after this line).

**When**
- failing refresh: `svc.create_component_item(db, item_in=ProjectComponentItemCreate(project_component_id=C1.id, item_id=I1.id, qty=5), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: C1 has exactly 1 `project_component_items` row, `qty == 5`.
3. committed: events(PJ1, "item_added") has exactly 1 row.

### PCIS-C-21 — a W1 item planned on a W1 component of a privileged caller's private project is stored
- **Rules:** `create_component_item` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. No component item in W1 (commit point after this line).

**When**
- `result = svc.create_component_item(db, item_in=ProjectComponentItemCreate(project_component_id=CP.id, item_id=I1.id, qty=3), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.item_id == I1.id`.
2. committed: the row `result.id` has `project_component_id == CP.id`, `qty == 3`.
3. committed: events(PJP, "item_added") has exactly 1 row.

## `ProjectComponentItemService.update_component_item`

### PCIS-U-01 — a new qty is stored, committed and returned; component and item stay
- **Rules:** `update_component_item` R2, R4; I-TC1, I-TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. LA = line(C1, 5) (commit point after this line).

**When**
- spies: `result = svc.update_component_item(db, item_id=LA.id, item_in=ProjectComponentItemUpdate(qty=7), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == LA.id`, `result.qty == 7`.
2. mock called: `cm.call_count == 1`.
3. committed: the row LA has `qty == 7`, `item_id == I1.id`, `project_component_id == C1.id`.
4. unchanged: no stock.

### PCIS-U-02 — a qty change logs item_updated
- **Rules:** `update_component_item` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. LA = line(C1, 5) (commit point after this line).

**When**
- `result = svc.update_component_item(db, item_id=LA.id, item_in=ProjectComponentItemUpdate(qty=7), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.qty == 7`.
2. event: events(PJ1, "item_updated") has exactly 1 row.
3. event: that event `performed_by == UG.id`, `description == "Updated component item (qty 7)"`.
4. event: that event `metadata_json == {"item_id": I1.id, "qty": "7", "component_id": C1.id, "component_name": "Roof"}`.

### PCIS-U-03 — a null qty leaves the qty
- **Rules:** `update_component_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. LA = line(C1, 5) (commit point after this line).

**When**
- `result = svc.update_component_item(db, item_id=LA.id, item_in=ProjectComponentItemUpdate(qty=None), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.qty == 5`.
2. re-read LA: `qty == 5`.

### PCIS-U-04 — the same qty writes no event
- **Rules:** `update_component_item` R3 [BUG-2310]
- **Kind:** bug
- **Expect:** xfail BUG-2310
- **Fails today on:** Then 2 (one `item_updated` event is written)

**Given**
1. LA = line(C1, 5) (commit point after this line).

**When**
- `result = svc.update_component_item(db, item_id=LA.id, item_in=ProjectComponentItemUpdate(qty=5), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.qty == 5`.
2. event: all_events(PJ1) has exactly 0 rows.

### PCIS-U-05 — an empty update writes no event
- **Rules:** `update_component_item` R3 [BUG-2310]
- **Kind:** bug
- **Expect:** xfail BUG-2310
- **Fails today on:** Then 2 (one `item_updated` event is written)

**Given**
1. LA = line(C1, 5) (commit point after this line).

**When**
- `result = svc.update_component_item(db, item_id=LA.id, item_in=ProjectComponentItemUpdate(), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == LA.id`.
2. event: all_events(PJ1) has exactly 0 rows.

### PCIS-U-06 — an unknown id returns None with no commit and no rollback
- **Rules:** `update_component_item` R1; I-TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. LA = line(C1, 5) (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.update_component_item(db, item_id=MISSING, item_in=ProjectComponentItemUpdate(qty=7), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is None`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db.new`.
5. session: `not db.dirty`.
6. unchanged: unchanged(LA).

### PCIS-U-07 — a private project's line: 403, rolled back once, pending changes discarded
- **Rules:** `update_component_item` R1; I-TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. LP = line(CP, 3) (commit point after this line).
2. extra row X.

**When**
- spies: `svc.update_component_item(db, item_id=LP.id, item_in=ProjectComponentItemUpdate(qty=7), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOACCESS`.
4. mock called: `rb.call_count == 1`.
5. session: `not db.dirty`.
6. count: x_gone.
7. unchanged: unchanged(LP).
8. nothing written.

### PCIS-U-08 — qty 0 is refused by the update schema
- **Rules:** `update_component_item` R2 [BUG-2307]
- **Kind:** bug
- **Expect:** xfail BUG-2307
- **Fails today on:** Then 1 (the schema accepts 0)

**Given**
1. No component item in W1.

**When**
- build `ProjectComponentItemUpdate(qty=0)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCIS-U-09 — qty above the integer range is refused by the update schema
- **Rules:** `update_component_item` R2 [BUG-2307]
- **Kind:** bug
- **Expect:** xfail BUG-2307
- **Fails today on:** Then 1 (the schema accepts 2147483648)

**Given**
1. No component item in W1.

**When**
- build `ProjectComponentItemUpdate(qty=2147483648)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCIS-U-10 — qty 1 is stored on update
- **Rules:** `update_component_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. LA = line(C1, 5) (commit point after this line).

**When**
- `result = svc.update_component_item(db, item_id=LA.id, item_in=ProjectComponentItemUpdate(qty=1), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.qty == 1`.
2. re-read LA: `qty == 1`.

### PCIS-U-11 — a failing commit rolls back once and the line is unchanged
- **Rules:** `update_component_item` R4; I-TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. LA = line(C1, 5) (commit point after this line).

**When**
- failing commit: `svc.update_component_item(db, item_id=LA.id, item_in=ProjectComponentItemUpdate(qty=7), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count == 1`.
3. unchanged: unchanged(LA).
4. nothing written.

### PCIS-U-12 — a failing re-read after the commit leaves the change saved
- **Rules:** `update_component_item` R4; I-TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. LA = line(C1, 5) (commit point after this line).

**When**
- failing refresh: `svc.update_component_item(db, item_id=LA.id, item_in=ProjectComponentItemUpdate(qty=7), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: the row LA has `qty == 7`.

### PCIS-U-13 — a W0 line (lower id) is not found in W1
- **Rules:** `update_component_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. L0 = `ProjectComponentItem(workspace_id=W0.id, project_component_id=C0.id, item_id=I0.id, qty=4)`.
2. LA = line(C1, 5) (commit point after this line).

**When**
- spies: `result = svc.update_component_item(db, item_id=L0.id, item_in=ProjectComponentItemUpdate(qty=7), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `not db.dirty`.
5. unchanged: unchanged(L0).
6. nothing written.

## `ProjectComponentItemService.delete_component_item`

### PCIS-D-01 — the line is deleted after its item_removed event, committed, True
- **Rules:** `delete_component_item` R2, R3; I-TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. LA = line(C1, 5).
2. LK = line(C1, 2) (commit point after this line).

**When**
- spies: `result = svc.delete_component_item(db, item_id=LA.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is True`.
2. mock called: `cm.call_count == 1`.
3. committed: no `project_component_items` row has id `LA.id`.
4. committed: the row LK exists.
5. committed: events(PJ1, "item_removed") has exactly 1 row, `performed_by == UG.id`, `description == "Removed item from component"`.
6. committed: that event `metadata_json == {"item_id": I1.id, "component_id": C1.id, "component_name": "Roof"}`.
7. unchanged: no stock.

### PCIS-D-02 — an unknown id returns False with no commit and no rollback
- **Rules:** `delete_component_item` R1; I-TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. LA = line(C1, 5) (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.delete_component_item(db, item_id=MISSING, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is False`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db.new`.
5. session: `not db.deleted`.
6. unchanged: unchanged(LA).

### PCIS-D-03 — a private project's line: 403, rolled back once, the line stays
- **Rules:** `delete_component_item` R1; I-TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. LP = line(CP, 3) (commit point after this line).
2. extra row X.

**When**
- spies: `svc.delete_component_item(db, item_id=LP.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOACCESS`.
4. mock called: `rb.call_count == 1`.
5. session: `not db.deleted`.
6. count: x_gone.
7. unchanged: unchanged(LP).
8. nothing written.

### PCIS-D-04 — a failing commit rolls back once; the line and no event remain
- **Rules:** `delete_component_item` R3; I-TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. LA = line(C1, 5) (commit point after this line).

**When**
- failing commit: `svc.delete_component_item(db, item_id=LA.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count == 1`.
3. unchanged: unchanged(LA).
4. nothing written.

### PCIS-D-05 — a W2 line (higher id) is not found in W1
- **Rules:** `delete_component_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. LA = line(C1, 5).
2. L9 = `ProjectComponentItem(workspace_id=W2.id, project_component_id=C9.id, item_id=I9.id, qty=4)` (commit point after this line).

**When**
- spies: `result = svc.delete_component_item(db, item_id=L9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is False`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `not db.deleted`.
5. unchanged: unchanged(L9).
6. nothing written.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_items` R7 [BUG-1277] | `GET /project-component-items/` | `limit=0` → 422; `limit=1` accepted |
| Integration-only | `/project-component-items/` endpoints | `None` / `False` → 404 `Project component item not found`; schema errors → 422 (BUG-461) |

## Spec gaps
None. Gap 1 closed by spec Gap log G1 (2026-11-04): schema module named.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_guard_component` | R1 | PCIS-L-03 … L-05, G-06, G-08, C-04 … C-08, U-07, D-03 |
| `_filter_accessible_items` | R1 | PCIS-L-06 … L-10 |
| `_filter_accessible_items` | R2 [BUG-1278] | PCIS-L-11 |
| `get_items` | R1 | PCIS-L-01, L-03, L-04; L-02 [BUG-2309]; L-05 [BUG-1278] |
| `get_items` | R2 | PCIS-L-06, L-07 |
| `get_items` | R3 [BUG-1278] | PCIS-L-11 |
| `get_items` | R4 [BUG-2308] | PCIS-L-12, L-13, L-14 |
| `get_items` | R5 / I-TC6 | PCIS-L-03, L-19, L-20 |
| `get_items` | R6 | PCIS-L-09 |
| `get_items` | R7 | PCIS-L-15 … L-18; endpoint part deferred |
| `get_by_id` | R1 | PCIS-G-02 … G-05 |
| `get_by_id` | R2 | PCIS-G-01, G-06, G-07; G-08 [BUG-1278] |
| `get_by_id` | R3 / I-TC6 | PCIS-G-02, G-06, G-09 |
| `create_component_item` | R1 | PCIS-C-04, C-06, C-07, C-21; C-08 [BUG-1278] |
| `create_component_item` | R2 | PCIS-C-05 |
| `create_component_item` | R3 [BUG-1012] | PCIS-C-09, C-10, C-11; own workspace C-21 |
| `create_component_item` | R3a [BUG-2306] | PCIS-C-13 |
| `create_component_item` | R4 [BUG-2307] | PCIS-C-14, C-15, C-16; in range C-17, C-18 |
| `create_component_item` | R5 | PCIS-C-01, C-03 |
| `create_component_item` | R6 | PCIS-C-02, C-21 |
| `create_component_item` | R7 / I-TC1–I-TC5 | PCIS-C-01, C-04, C-12, C-19, C-20 |
| `update_component_item` | R1 | PCIS-U-06, U-07, U-13 |
| `update_component_item` | R2 | PCIS-U-01, U-03, U-10; U-08, U-09 [BUG-2307] |
| `update_component_item` | R3 | PCIS-U-02; U-04, U-05 [BUG-2310] |
| `update_component_item` | R4 / I-TC1–I-TC5 | PCIS-U-01, U-07, U-11, U-12 |
| `delete_component_item` | R1 | PCIS-D-02, D-03, D-05 |
| `delete_component_item` | R2 | PCIS-D-01 |
| `delete_component_item` | R3 / I-TC1, I-TC3, I-TC4 | PCIS-D-01, D-03, D-04 |
