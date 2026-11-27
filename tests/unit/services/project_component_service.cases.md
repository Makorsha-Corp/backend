# Test cases — `app/services/project_component_service.py`

> **Spec:** `tests/unit/services/project_component_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 4 (2026-11-06) — verifier (`project_component_service.verify.md`), both findings `case-missing`. Finding 1: new PCS-D-27 (`"attachment_added "`, trailing space) and PCS-D-28 (`"attachment_add"`), each blocks the delete (spec G5 exact compare, strict xfail BUG-1196), so a trimming or prefix match fails. Finding 2: new PCS-L-43, CT6 on the success path with `project_id` (spies, no commit, no rollback, pending changes kept). No card changed, no ID retired.
> Revision 3 (2026-11-05) — executor discrepancies (`project_component_service.notes.md`). DISCREPANCY-1: PCS-D-06 is now strict xfail BUG-2262 on the spec's new `delete_component` R5a (an attachment link row makes the delete fail with `IntegrityError` today; intended: the link rows go with the component, the delete succeeds as R6a). D-06 now also checks that the `Attachment` row and another component's link row stay, and the `component_deleted` event. Its other checks (returns `True`, component gone) stay covered by the passing PCS-D-01. PCS-D-15: duplicate "Then 5" renumbered to 5, 6; `Fails today on` unchanged (Then 1). No `expired_attributes` check in the file, nothing to change. No ID retired.
> Revision 2 (2026-11-05) — spec fill-gaps G1–G5 (Gap log, 2026-11-04). G1: model and schema modules named in Conventions. G2: blocker-table columns given; PCS-D-06, D-15, D-19 rewritten with the builders att / ledger / misc, `Author: claude` dropped. G3: dates are naive datetimes; PCS-U-04 now checks the stored dates exactly (no card used another type). G4: new PCS-U-25 (`update_component` R3b, a sent `project_id` is ignored, pass). G5: new PCS-D-26 (`Attachment_added` blocks, exact compare, xfail BUG-1196). Spec gaps section closed. No ID retired.
> **Counts:** 129 cases · 80 expected-to-pass · 49 expected-to-fail (bugs) · 5 deferred

## Reviewer summary
- **Per callable:** `get_components` 43 (12 bug) · `get_by_id` 11 (1 bug) · `create_component` 22 (7 bug) · `update_component` 25 (12 bug) · `delete_component` 28 (17 bug). By bug: BUG-1196 15 · BUG-2262 1 · BUG-1278 7 · BUG-2272 5 · BUG-2275 5 · BUG-2279 4 (1 non-strict) · BUG-2277 3 · BUG-2273 2 · BUG-2274 3 · BUG-2276 2 · BUG-2278 1 · BUG-1275 1.
- **Depth:** full on who may see a component (the workspace-wide list filters by `can_access_project` in this service) and on the paging bugs; full on the BUG-1196 delete refusal (one card per blocker type, per non-blocking row, per cross-workspace shape). Lighter on the rest (no stock, money flow or order state; `budget` gets its boundaries once per writer). The manager's own access matrix (`project_manager.cases.md` PRJM-CA, PV) is not repeated: on the by-id paths there is one 403 and one granted card per method.
- **Access grants on the workspace-wide list (L-01 … L-18):** each grant once (workspace owner, active `owner`, active `ground-team-manager`, creator, project member); each refusal shape of step 1b: membership of another private project with a lower and a higher id, owner of W0 and of W2, privileged in W0 and in W2, a project-member row filed under W2, a private project with no creator, an inactive manager, role `manager`, and the HR-16 rows (a W1 component whose project is in W0 or W2). These all pass today (the Python filter is correct on a full page).
- **BUG-2277 (filter after paging):** L-20 (`limit=2`, three hidden rows ahead) and L-21 (`skip=1`, the hidden row ahead of the skipped one). The hidden rows come first both by insertion / id (today's physical order) and by name (BUG-2279's order), so each fails strictly whatever order the fix picks. L-22 does the same for BUG-1278's deleted project. L-23 counts statements.
- **Order:** BUG-2279 strict on names `Zulu`, `apple`, `Banana` (L-25) and before paging (L-26); the case-only tie is non-strict, `Author: claude` (L-27); L-28 is the strict `ORDER BY name` recorder. BUG-1275 one pass-through card (L-39).
- **Transactions:** every writer has a success card with commit / rollback spies (CT1, CT2), a refusal that discards an uncommitted extra row with exactly one rollback (CT3), a failing commit (CT4, exactly one rollback) and, for create and update, a failing refresh (CT5). Each reader has a TC6 card (an unflushed new row and an edited row survive; no commit, no rollback) and a refused read that keeps them.
- **Notable design choices:** components carry explicit ids XID(k) so a component id never equals a project id. The attachment card (D-06, xfail BUG-2262: today the ORM nulls the link's NOT NULL key, so the delete fails) builds its `Attachment` row with the builder of `attachment_manager.cases.md`, since the spec only says one is needed. BUG-2277 L-20 relies on today's physical order for its strict failure, as the spec's Notes ask.
- **Needs a decision:** None. Spec gaps 1–5 are closed by the spec's Gap log (G1–G5).

## Conventions for this module

**IDs.** `PCS` = `app/services/project_component_service.py`. `L` get_components · `G` get_by_id · `C` create_component · `U` update_component · `D` delete_component.

**Imports.** `from app.services.project_component_service import ProjectComponentService, project_component_service`. Models from `app.models.<module>`: `factory.Factory`, `project.Project`, `project_member.ProjectMember`, `project_event.ProjectEvent`, `project_component.ProjectComponent`, `workspace_member.WorkspaceMember`, `work_order_type.WorkOrderType`, `work_order.WorkOrder`, `item.Item`, `project_component_item.ProjectComponentItem`, `project_component_task.ProjectComponentTask`, `project_component_activity_event.ProjectComponentActivityEvent`, `project_component_item_ledger.ProjectComponentItemLedger`, `miscellaneous_project_cost.MiscellaneousProjectCost`, `project_component_attachment.ProjectComponentAttachment`, `attachment.Attachment`. `ProjectComponentCreate`, `ProjectComponentUpdate` (`app.schemas.project_component`). `ProjectStatusEnum` (`app.models.enums`). `HTTPException` (`fastapi`). `ValidationError` = `app.core.exceptions.ValidationError`; `PydanticValidationError` = `pydantic.ValidationError`. `DataError` (`sqlalchemy.exc`); `event`, `insert`, `select`, `func` (`sqlalchemy`); `Decimal`; `datetime`; `patch` (`unittest.mock`); `os`.

**Fixed values.** `svc` = `project_component_service`. `db` = the test's real session, first positional argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush. MISSING = `999999999`. T0 = `datetime(2025, 12, 1, 8, 0, 0)`, T1 = `datetime(2026, 1, 1, 9, 0, 0)`. **XID(k)** = `800_000_000 + (os.getpid() % 1_000_000) * 10 + k`. NOACCESS = `"You do not have access to this project"`. NOCOMP = `"Project component not found"`. NOPROJ(x) = `f"Project with ID {x} not found"`.

**Externals.** None mocked. `created_at` of components and events is asserted `is not None`.

**Standing rows** (every test, no Given line; built in this order, each flushed):
- W0, W1, W2 = `make_workspace(db)` in that order (`W0.id < W1.id < W2.id`); no `owner_user_id`.
- U1 = `make_profile(db, name="Ana Rahman")`, U2 = `make_profile(db, name="Bilal Khan")`, UG = `make_profile(db, name="Mia Khan")`. W1 memberships: member(U1, "ground-team"), member(U2, "owner"), member(UG, "ground-team").
- F0 = `Factory(workspace_id=W0.id, name="Factory Zero", abbreviation="F0")`, F1 = the same in W1 (`"Factory One"`, `"F1"`), F9 = the same in W2 (`"Factory Nine"`, `"F9"`).
- Projects, in this order: P0 = `Project(workspace_id=W0.id, factory_id=F0.id, name="Zero", description="Main", created_by=U1.id, visibility="workspace")`; PA = the same in W1 with F1, `name "Alpha"`; PB = PA but `name "Bravo"`, `visibility "invited_only"` (private, creator U1); P9 = the same in W2 with F9, `name "Nine"`, `visibility "workspace"`. So `P0.id < PA.id < PB.id < P9.id`.
- No component, project member, event or work order exists unless the Given builds it.

**Given rows.** Built directly (never through `svc`), added and flushed one at a time in the order written. After "but" a line lists every column that differs. A line written as code is a step run exactly as written.
- **comp(P, "N", k)** = `ProjectComponent(id=XID(k), workspace_id=P.workspace_id, project_id=P.id, name="N")`.
- **member(U, role, status="active", ws=W1)** = `WorkspaceMember(workspace_id=ws.id, user_id=U.id, role=role, status=status)`. **UM** = `make_profile(db, name="Omar Ali")`.
- **pmem(P, U)** = `ProjectMember(workspace_id=P.workspace_id, project_id=P.id, user_id=U.id, assigned_by=U1.id)`. **set_owner(W, U)** = `W.owner_user_id = U.id`, then `db.flush()`.
- **proj "N"** = `Project(workspace_id=W1.id, factory_id=F1.id, name="N", description="Main", created_by=U1.id, visibility="workspace")`; **private** = `visibility "invited_only"`; **deleted** = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.
- **bulk(n, P)** = `db.execute(insert(ProjectComponent), [{"workspace_id": P.workspace_id, "project_id": P.id, "name": f"C{i:05d}"} for i in range(n)])`, then `db.expire_all()`.
- **WT1** = `WorkOrderType(workspace_id=W1.id, name="Repair")`. **wo(C, "N")** = `WorkOrder(workspace_id=W1.id, work_order_number="N", title="Fix press", factory_id=F1.id, work_order_type_id=WT1.id, created_by=U1.id, project_component_id=C.id)`; deleted wo = `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`.
- **I1** = `Item(workspace_id=W1.id, name="Bolt", name_normalized="bolt", unit="pcs")`. **line(C)** = `ProjectComponentItem(workspace_id=W1.id, project_component_id=C.id, item_id=I1.id, qty=1)`.
- **task(C, "N")** = `ProjectComponentTask(workspace_id=W1.id, project_component_id=C.id, name="N", description="Do it")`; **note** = task but `is_note True`.
- **act(C, "t")** = `ProjectComponentActivityEvent(workspace_id=W1.id, project_component_id=C.id, event_type="t", description="Logged", created_at=T1)`.
- **ledger(C)** = `ProjectComponentItemLedger(workspace_id=W1.id, project_component_id=C.id, item_id=I1.id, transaction_type="consume", quantity=1, unit_cost=5, total_cost=5, qty_before=1, qty_after=0, source_type="manual", performed_by=U1.id)` (needs I1). **misc(C)** = `MiscellaneousProjectCost(workspace_id=W1.id, name="Crane hire", amount=50, project_id=PA.id, project_component_id=C.id)`.
- **AT0** = `Attachment(workspace_id=W1.id, file_name="file.png", mime_type="image/png", file_size=100, uploaded_by=U1.id, upload_status="ready")`. **att(C)** = `ProjectComponentAttachment(workspace_id=W1.id, project_component_id=C.id, attachment_id=AT0.id, attached_by=U1.id)` (needs AT0).
- Dates (`deadline`, `start_date`, `end_date`) are naive datetimes, stored and read back as given.
- **pev(P)** = `ProjectEvent(workspace_id=P.workspace_id, project_id=P.id, event_type="project_updated", description="seed", performed_by=U1.id, created_at=T1, metadata_json=None)`.
- **commit point** = after the last Given line, in every card, the test runs `db.commit()` (releases a savepoint). Snapshots for `unchanged` / `nothing written` are taken there (`db.refresh(X)` first).
- **extra row X** (after the commit point, only where listed) = `X = ProjectComponent(workspace_id=W2.id, project_id=P9.id, name="Extra")`, `db.add(X)`, `db.flush()`, `X_ID = X.id`. **pending Q** (after the commit point) = `Q = ProjectComponent(workspace_id=W2.id, project_id=P9.id, name="Pending")`, `db.add(Q)`, not flushed. **edit E(C)** = `C.name = "Edited"`, not flushed.

**Named checks.**
- **re-read X** = `db.expire_all()`, then `db.get(<Model>, X.id)`. **unchanged(X)** = after re-read, every column of X equals its snapshot. **gone(C)** = `db.expire_all()`, then `db.get(ProjectComponent, C.id) is None`.
- **nothing written** = row counts of `project_components` and `project_events` (all workspaces) equal their values at the commit point. **x_gone** = `db.scalar(select(func.count()).select_from(ProjectComponent).where(ProjectComponent.id == X_ID)) == 0`.
- **evs(P, t)** = `db.expire_all()`, then the `ProjectEvent` rows with `project_id == P.id` and `event_type == t`, ordered by `id`. `metadata_json` compared as a whole dict.
- **idset(r)** = `{c.id for c in r}`. **names(r)** = `[c.name for c in r]`, order checked.
- `raises: <Type>` = plain `with pytest.raises(<Type>) as exc:` around the call, no savepoint; then `exc.value.status_code`, `exc.value.detail`, `exc.value.errors`, one per line. `raises: DataError in a savepoint` = `with pytest.raises(DataError):` then `with db.begin_nested():` then the call. Target `schema` = the When only builds the schema object.
- `session:` lines check `db.new`, `db.dirty`, `db.deleted` right after the call, before any re-read or `expire_all`.
- `committed:` lines: before the first, the test runs `db.rollback()` once; each line re-reads with a fresh query.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When (inside any `pytest.raises`).
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = the same with `patch.object(db, "refresh", side_effect=RuntimeError("boom"))` and the `rb` spy.
- **recorder** = `stmts = []`, `event.listen(db.connection(), "before_cursor_execute", rec)` where `rec(conn, cursor, statement, params, context, executemany)` appends `statement`; set up after the commit point, removed with `event.remove` right after the When.

**xfail cards.** Strict: `pytest.mark.xfail(strict=True, reason="BUG-NNN")`; `(non-strict)` = `strict=False`. Write the call and the checks as shown.

**Race simulations.** None.

## `ProjectComponentService.get_components` — workspace-wide (no `project_id`)

### PCS-L-01 — a privileged member sees every component of W1, private projects included, not W0's or W2's
- **Rules:** `get_components` R3, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. C0 = comp(P0, "Zero part", 11).
2. CA = comp(PA, "Arm", 12).
3. CB = comp(PB, "Base", 13).
4. C9 = comp(P9, "Nine part", 14).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `all(isinstance(c, ProjectComponent) for c in result)`.
2. returns: `idset(result) == {CA.id, CB.id}`.

### PCS-L-02 — a plain member does not see a private project's components
- **Rules:** `get_components` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. C0 = comp(P0, "Zero part", 11).
2. CA = comp(PA, "Arm", 12).
3. CB = comp(PB, "Base", 13).
4. C9 = comp(P9, "Nine part", 14).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {CA.id}`.

### PCS-L-03 — the workspace owner (owner_user_id) sees the private components
- **Rules:** `get_components` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. set_owner(W1, UG).
2. CA = comp(PA, "Arm", 12).
3. CB = comp(PB, "Base", 13).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {CA.id, CB.id}`.

### PCS-L-04 — an active ground-team-manager sees the private components
- **Rules:** `get_components` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. UM.
2. member(UM, "ground-team-manager").
3. CA = comp(PA, "Arm", 12).
4. CB = comp(PB, "Base", 13).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=UM.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {CA.id, CB.id}`.

### PCS-L-05 — the private project's creator sees its components
- **Rules:** `get_components` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. CA = comp(PA, "Arm", 12).
2. CB = comp(PB, "Base", 13).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=U1.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {CA.id, CB.id}`.

### PCS-L-06 — a project member sees the private project's components
- **Rules:** `get_components` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. pmem(PB, UG).
2. CA = comp(PA, "Arm", 12).
3. CB = comp(PB, "Base", 13).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {CA.id, CB.id}`.

### PCS-L-07 — membership of a later private project does not open an earlier one
- **Rules:** `get_components` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. PC = private proj "Charlie" (id above PB's).
2. pmem(PC, UG).
3. CA = comp(PA, "Arm", 12).
4. CB = comp(PB, "Base", 13).
5. CC = comp(PC, "Cap", 14).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {CA.id, CC.id}`.

### PCS-L-08 — membership of an earlier private project does not open a later one
- **Rules:** `get_components` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. PC = private proj "Charlie" (id above PB's).
2. pmem(PB, UG).
3. CA = comp(PA, "Arm", 12).
4. CB = comp(PB, "Base", 13).
5. CC = comp(PC, "Cap", 14).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {CA.id, CB.id}`.

### PCS-L-09 — owning W0 opens nothing private in W1
- **Rules:** `get_components` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. set_owner(W0, UG).
2. CA = comp(PA, "Arm", 12).
3. CB = comp(PB, "Base", 13).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {CA.id}`.

### PCS-L-10 — owning W2 opens nothing private in W1
- **Rules:** `get_components` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. set_owner(W2, UG).
2. CA = comp(PA, "Arm", 12).
3. CB = comp(PB, "Base", 13).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {CA.id}`.

### PCS-L-11 — the owner role in W0 opens nothing private in W1
- **Rules:** `get_components` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. member(UG, "owner", ws=W0).
2. CA = comp(PA, "Arm", 12).
3. CB = comp(PB, "Base", 13).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {CA.id}`.

### PCS-L-12 — ground-team-manager in W2 opens nothing private in W1
- **Rules:** `get_components` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. member(UG, "ground-team-manager", ws=W2).
2. CA = comp(PA, "Arm", 12).
3. CB = comp(PB, "Base", 13).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {CA.id}`.

### PCS-L-13 — a project-member row filed under W2 does not open the W1 project
- **Rules:** `get_components` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `ProjectMember(workspace_id=W2.id, project_id=PB.id, user_id=UG.id, assigned_by=U1.id)` (added, flushed).
2. CA = comp(PA, "Arm", 12).
3. CB = comp(PB, "Base", 13).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {CA.id}`.

### PCS-L-14 — a private project with no creator is not opened by another project's creator
- **Rules:** `get_components` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. PN = private proj "November", but `created_by None`.
2. CA = comp(PA, "Arm", 12).
3. CB = comp(PB, "Base", 13).
4. CN = comp(PN, "Nut", 14).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=U1.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {CA.id, CB.id}`.

### PCS-L-15 — an inactive ground-team-manager is not privileged (pass-through)
- **Rules:** `get_components` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. UM.
2. member(UM, "ground-team-manager", status="inactive").
3. CA = comp(PA, "Arm", 12).
4. CB = comp(PB, "Base", 13).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=UM.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {CA.id}`.

### PCS-L-16 — role "manager" is not privileged (pass-through)
- **Rules:** `get_components` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. UM.
2. member(UM, "manager").
3. CA = comp(PA, "Arm", 12).
4. CB = comp(PB, "Base", 13).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=UM.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {CA.id}`.

### PCS-L-17 — a W1 component whose project is in W2 is left out (HR-16)
- **Rules:** `get_components` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. CA = comp(PA, "Arm", 12).
2. CB = comp(PB, "Base", 13).
3. CX = comp(P9, "Stray", 14), but `workspace_id W1.id`.

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {CA.id, CB.id}`.

### PCS-L-18 — a W1 component whose project is in W0 is left out (HR-16)
- **Rules:** `get_components` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. CX = comp(P0, "Stray", 11), but `workspace_id W1.id`.
2. CA = comp(PA, "Arm", 12).
3. CB = comp(PB, "Base", 13).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {CA.id, CB.id}`.

### PCS-L-19 — components of a soft-deleted project are left out
- **Rules:** `get_components` R4 [BUG-1278]
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (CD is listed)

**Given**
1. PD = proj "Delta", deleted.
2. CA = comp(PA, "Arm", 12).
3. CD = comp(PD, "Door", 13).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {CA.id}`.

### PCS-L-20 — hidden components ahead of the page do not empty it
- **Rules:** `get_components` R5 [BUG-2277]
- **Kind:** bug
- **Expect:** xfail BUG-2277
- **Fails today on:** Then 1 (today `[]`: the first page holds only hidden rows)

**Given**
1. H1 = comp(PB, "Aa", 11).
2. H2 = comp(PB, "Ab", 12).
3. H3 = comp(PB, "Ac", 13).
4. V1 = comp(PA, "Ba", 14).
5. V2 = comp(PA, "Bb", 15).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=UG.id, skip=0, limit=2)`.

**Then**
1. returns: `idset(result) == {V1.id, V2.id}`.

### PCS-L-21 — a hidden component does not take the place of the skipped one
- **Rules:** `get_components` R5 [BUG-2277]
- **Kind:** bug
- **Expect:** xfail BUG-2277
- **Fails today on:** Then 1 (today V1 and V2: the skip consumed the hidden row)

**Given**
1. H = comp(PB, "Aa", 11).
2. V1 = comp(PA, "Ba", 12).
3. V2 = comp(PA, "Bb", 13).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=UG.id, skip=1, limit=1000)`.

**Then**
1. returns: `idset(result) == {V2.id}`.

### PCS-L-22 — a deleted project's components take no place on the page
- **Rules:** `get_components` R4, R5 [BUG-1278]
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (today the page holds D1)

**Given**
1. PD = proj "Delta", deleted.
2. D1 = comp(PD, "Aa", 11).
3. V1 = comp(PA, "Ba", 12).
4. V2 = comp(PA, "Bb", 13).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=U2.id, skip=0, limit=2)`.

**Then**
1. returns: `idset(result) == {V1.id, V2.id}`.

### PCS-L-23 — the number of statements does not grow with the components
- **Rules:** `get_components` R5 [BUG-2277]
- **Kind:** bug
- **Expect:** xfail BUG-2277
- **Fails today on:** Then 2 (two reads per component: about 11)

**Given**
1. comp(PB, "Aa", 11), comp(PB, "Ab", 12), comp(PA, "Ba", 13), comp(PA, "Bb", 14), comp(PA, "Bc", 15), in that order.
2. recorder (after the commit point).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `len(result) == 3`.
2. count: `len(stmts) <= 3`.

### PCS-L-24 — the default page is 100
- **Rules:** `get_components` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(101, PA).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `len(result) == 100`.

### PCS-L-25 — the list is ordered by name, case-insensitive
- **Rules:** `get_components` R6 [BUG-2279]
- **Kind:** bug
- **Expect:** xfail BUG-2279
- **Fails today on:** Then 1 (today `["Zulu", "apple", "Banana"]`)

**Given**
1. comp(PA, "Zulu", 11).
2. comp(PA, "apple", 12).
3. comp(PB, "Banana", 13).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `names(result) == ["apple", "Banana", "Zulu"]`.

### PCS-L-26 — the order is applied before paging
- **Rules:** `get_components` R6 [BUG-2279]
- **Kind:** bug
- **Expect:** xfail BUG-2279
- **Fails today on:** Then 1 (today `["Zulu"]`)

**Given**
1. comp(PA, "Zulu", 11).
2. comp(PA, "apple", 12).
3. comp(PA, "Banana", 13).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=U2.id, skip=0, limit=1)`.

**Then**
1. returns: `names(result) == ["apple"]`.

### PCS-L-27 — names equal but for case are ordered by id
- **Rules:** `get_components` R6 [BUG-2279]
- **Kind:** bug
- **Expect:** xfail BUG-2279 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (no order: physical order puts XID(12) first)

**Given**
1. GH = comp(PA, "gear", 12).
2. GL = comp(PA, "Gear", 11) (built second, lower id).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `[c.id for c in result] == [GL.id, GH.id]`.

### PCS-L-28 — the component query orders by name (recorder)
- **Rules:** `get_components` R6 [BUG-2279]
- **Kind:** bug
- **Expect:** xfail BUG-2279
- **Fails today on:** Then 2 (no `ORDER BY` on the component read)

**Given**
1. comp(PA, "Arm", 12).
2. recorder (after the commit point).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `len(result) == 1`.
2. count: `any("FROM project_components" in s and "ORDER BY" in s and "project_components.name" in s.split("ORDER BY", 1)[1] for s in stmts)` is True.

## `ProjectComponentService.get_components` — one project (`project_id` given)

### PCS-L-29 — a project's components only, not another project's or workspace's
- **Rules:** `get_components` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. PC = proj "Charlie".
2. C0 = comp(P0, "Zero part", 10).
3. CB = comp(PB, "Base", 11).
4. CA1 = comp(PA, "Arm", 12).
5. CA2 = comp(PA, "Axle", 13).
6. CC = comp(PC, "Cap", 14).
7. C9 = comp(P9, "Nine part", 15).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=UG.id, project_id=PA.id, limit=1000)`.

**Then**
1. returns: `all(isinstance(c, ProjectComponent) for c in result)`.
2. returns: `idset(result) == {CA1.id, CA2.id}`.

### PCS-L-30 — an unknown project answers 404
- **Rules:** `get_components` R1, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. CA = comp(PA, "Arm", 12).

**When**
- `svc.get_components(db, workspace_id=W1.id, user_id=U2.id, project_id=MISSING)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project with ID 999999999 not found"`.

### PCS-L-31 — W0's project answers 404 as missing
- **Rules:** `get_components` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. C0 = comp(P0, "Zero part", 11).

**When**
- `svc.get_components(db, workspace_id=W1.id, user_id=U2.id, project_id=P0.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOPROJ(P0.id)`.

### PCS-L-32 — W2's project answers 404 as missing
- **Rules:** `get_components` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. C9 = comp(P9, "Nine part", 11).

**When**
- `svc.get_components(db, workspace_id=W1.id, user_id=U2.id, project_id=P9.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOPROJ(P9.id)`.

### PCS-L-33 — a private project the caller may not open answers 403
- **Rules:** `get_components` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. CB = comp(PB, "Base", 11).

**When**
- `svc.get_components(db, workspace_id=W1.id, user_id=UG.id, project_id=PB.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOACCESS`.

### PCS-L-34 — a project member lists the private project's components
- **Rules:** `get_components` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. pmem(PB, UG).
2. CB = comp(PB, "Base", 11).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=UG.id, project_id=PB.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {CB.id}`.

### PCS-L-35 — a soft-deleted project answers 404
- **Rules:** `get_components` R2 [BUG-1278]
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (the call returns CD)

**Given**
1. PD = proj "Delta", deleted.
2. CD = comp(PD, "Door", 11).

**When**
- `svc.get_components(db, workspace_id=W1.id, user_id=U2.id, project_id=PD.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOPROJ(PD.id)`.

### PCS-L-36 — project_id 0 is looked up, not "no filter"
- **Rules:** `get_components` R1 [BUG-2278]
- **Kind:** bug
- **Expect:** xfail BUG-2278
- **Fails today on:** Then 1 (the call returns the workspace's components)

**Given**
1. CA = comp(PA, "Arm", 12).

**When**
- `svc.get_components(db, workspace_id=W1.id, user_id=U2.id, project_id=0)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project with ID 0 not found"`.

### PCS-L-37 — the default page of one project is 100
- **Rules:** `get_components` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(101, PA).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=U2.id, project_id=PA.id)`.

**Then**
1. returns: `len(result) == 100`.

### PCS-L-38 — skip and limit reach the project read
- **Rules:** `get_components` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CA1 = comp(PA, "Arm", 12).
2. CA2 = comp(PA, "Axle", 13).
3. CA3 = comp(PA, "Axis", 14).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=U2.id, project_id=PA.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `idset(result) <= {CA1.id, CA2.id, CA3.id}`.

### PCS-L-39 — one project's list is ordered by name (pass-through)
- **Rules:** `get_components` R1 (DAO `get_by_project` R3 [BUG-1275])
- **Kind:** bug
- **Expect:** xfail BUG-1275
- **Fails today on:** Then 1 (no order: `["Beta", "alpha", "Gamma"]`)

**Given**
1. comp(PA, "Beta", 11).
2. comp(PA, "alpha", 12).
3. comp(PA, "Gamma", 13).

**When**
- `result = svc.get_components(db, workspace_id=W1.id, user_id=U2.id, project_id=PA.id, limit=1000)`.

**Then**
1. returns: `names(result) == ["alpha", "Beta", "Gamma"]`.

### PCS-L-40 — a negative skip is a database error
- **Rules:** `get_components` Errors
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CA = comp(PA, "Arm", 12).

**When**
- `svc.get_components(db, workspace_id=W1.id, user_id=U2.id, project_id=PA.id, skip=-1, limit=10)`.

**Then**
1. raises: `DataError` in a savepoint.
2. session: `db.execute(select(1)).scalar() == 1` (the session stays usable).

### PCS-L-41 — a read keeps the caller's pending changes and neither commits nor rolls back
- **Rules:** `get_components` R7 (CT6)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CA = comp(PA, "Arm", 12).
2. pending Q (after the commit point).
3. edit E(CA) (after the commit point).

**When**
- spies: `result = svc.get_components(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `CA.id in idset(result)`.
2. session: `Q in db.new and len(db.new) == 1`.
3. session: `CA in db.dirty and len(db.dirty) == 1`.
4. session: `not db.deleted`.
5. mock called: `cm.call_count == 0`, `rb.call_count == 0`.

### PCS-L-42 — a refused read keeps the caller's pending changes
- **Rules:** `get_components` R7 (CT6)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CA = comp(PA, "Arm", 12).
2. pending Q (after the commit point).
3. edit E(CA) (after the commit point).

**When**
- spies: `svc.get_components(db, workspace_id=W1.id, user_id=UG.id, project_id=PB.id)`.

**Then**
1. raises: `HTTPException` (spies inside the `pytest.raises`).
2. raises: `exc.value.status_code == 403`.
3. session: `Q in db.new and len(db.new) == 1`.
4. session: `CA in db.dirty`.
5. mock called: `cm.call_count == 0`, `rb.call_count == 0`.

### PCS-L-43 — one project's list keeps pending changes and neither commits nor rolls back
- **Rules:** `get_components` R1, R7 (CT6)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CA = comp(PA, "Arm", 12).
2. pending Q (after the commit point).
3. edit E(CA) (after the commit point).

**When**
- spies: `result = svc.get_components(db, workspace_id=W1.id, user_id=U2.id, project_id=PA.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {CA.id}`.
2. session: `Q in db.new and len(db.new) == 1`.
3. session: `CA in db.dirty and len(db.dirty) == 1`.
4. session: `not db.deleted`.
5. mock called: `cm.call_count == 0`, `rb.call_count == 0`.

## `ProjectComponentService.get_by_id`

### PCS-G-01 — returns the asked component among lower and higher ids
- **Rules:** `get_by_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. C1 = comp(PA, "Arm", 11).
2. C2 = comp(PA, "Axle", 12).
3. C3 = comp(PA, "Axis", 13).

**When**
- `result = svc.get_by_id(db, component_id=C2.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `isinstance(result, ProjectComponent)`.
2. returns: `result.id == C2.id`, `result.name == "Axle"`, `result.project_id == PA.id`.

### PCS-G-02 — an unknown id answers 404
- **Rules:** `get_by_id` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. C1 = comp(PA, "Arm", 11).

**When**
- `svc.get_by_id(db, component_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.

### PCS-G-03 — id 0 answers 404
- **Rules:** `get_by_id` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. C1 = comp(PA, "Arm", 11).

**When**
- `svc.get_by_id(db, component_id=0, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.

### PCS-G-04 — W0's component answers 404
- **Rules:** `get_by_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. C0 = comp(P0, "Zero part", 11).
2. C1 = comp(PA, "Arm", 12).

**When**
- `svc.get_by_id(db, component_id=C0.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.

### PCS-G-05 — W2's component answers 404
- **Rules:** `get_by_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. C1 = comp(PA, "Arm", 11).
2. C9 = comp(P9, "Nine part", 12).

**When**
- `svc.get_by_id(db, component_id=C9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.

### PCS-G-06 — a component of a private project the caller may not open answers 403
- **Rules:** `get_by_id` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. CB = comp(PB, "Base", 11).

**When**
- `svc.get_by_id(db, component_id=CB.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOACCESS`.

### PCS-G-07 — the private project's creator opens its component
- **Rules:** `get_by_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. CB = comp(PB, "Base", 11).

**When**
- `result = svc.get_by_id(db, component_id=CB.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == CB.id`.

### PCS-G-08 — a component of a soft-deleted project answers 404
- **Rules:** `get_by_id` R2 [BUG-1278]
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (the component is returned)

**Given**
1. PD = proj "Delta", deleted.
2. CD = comp(PD, "Door", 11).

**When**
- `svc.get_by_id(db, component_id=CD.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOPROJ(PD.id)`.

### PCS-G-09 — a W1 component whose project is in W2 answers the project's 404 (pass-through)
- **Rules:** `get_by_id` R1 (manager `require_component_access` R4)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. CX = comp(P9, "Stray", 11), but `workspace_id W1.id`.

**When**
- `svc.get_by_id(db, component_id=CX.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOPROJ(P9.id)`.

### PCS-G-10 — a read keeps the caller's pending changes and neither commits nor rolls back
- **Rules:** `get_by_id` R3 (CT6)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CA = comp(PA, "Arm", 12).
2. pending Q (after the commit point).
3. edit E(CA) (after the commit point).

**When**
- spies: `result = svc.get_by_id(db, component_id=CA.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == CA.id`.
2. session: `Q in db.new and len(db.new) == 1`.
3. session: `CA in db.dirty and len(db.dirty) == 1`.
4. mock called: `cm.call_count == 0`, `rb.call_count == 0`.

### PCS-G-11 — a refused read keeps the caller's pending changes
- **Rules:** `get_by_id` R3 (CT6)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CA = comp(PA, "Arm", 12).
2. pending Q (after the commit point).

**When**
- spies: `svc.get_by_id(db, component_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException` (spies inside the `pytest.raises`).
2. raises: `exc.value.status_code == 404`.
3. session: `Q in db.new and len(db.new) == 1`.
4. mock called: `cm.call_count == 0`, `rb.call_count == 0`.

## `ProjectComponentService.create_component`

### PCS-C-01 — the component is created, committed and returned re-read
- **Rules:** `create_component` R3, CT1, CT2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No component (commit point only).

**When**
- spies: `result = svc.create_component(db, component_in=ProjectComponentCreate(project_id=PA.id, name="Roof", description="Top part", budget=1500.5), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `isinstance(result, ProjectComponent)`, `result.id is not None`.
2. returns: `result.created_at is not None`, `result.status == ProjectStatusEnum.PLANNING`.
3. mock called: `cm.call_count == 1`, `rb.call_count == 0`.
4. committed: the row `result.id`: `workspace_id == W1.id`, `project_id == PA.id`, `name == "Roof"`, `description == "Top part"`.
5. committed: the row `result.id`: `budget == Decimal("1500.50")`, `start_date is None`, `end_date is None`, `deadline is None`.

### PCS-C-02 — creating writes one component_created project event, committed
- **Rules:** `create_component` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No component (commit point only).

**When**
- `result = svc.create_component(db, component_in=ProjectComponentCreate(project_id=PA.id, name="Roof"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: evs(PA, "component_created") has exactly 1 row.
3. committed: that row: `workspace_id == W1.id`, `performed_by == UG.id`, `description == 'Added component "Roof"'`.
4. committed: that row: `metadata_json == {"component_id": result.id, "component_name": "Roof"}`, `created_at is not None`.

### PCS-C-03 — any status may be given at creation
- **Rules:** `create_component` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No component (commit point only).

**When**
- `result = svc.create_component(db, component_in=ProjectComponentCreate(project_id=PA.id, name="Roof", status=ProjectStatusEnum.COMPLETED), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.status == ProjectStatusEnum.COMPLETED`.
2. committed: the row `result.id`: `status == ProjectStatusEnum.COMPLETED`.

### PCS-C-04 — an unknown project answers 404, rolled back once, nothing written
- **Rules:** `create_component` R1, Errors, CT3
- **Kind:** error
- **Expect:** pass

**Given**
1. No component (commit point only).

**When**
- spies: `svc.create_component(db, component_in=ProjectComponentCreate(project_id=MISSING, name="Roof"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException` (spies inside the `pytest.raises`).
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project with ID 999999999 not found"`.
4. session: `not db.new and not db.dirty`.
5. mock called: `rb.call_count == 1`, `cm.call_count == 0`.
6. nothing written.

### PCS-C-05 — project_id 0 answers 404
- **Rules:** `create_component` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No component (commit point only).

**When**
- `svc.create_component(db, component_in=ProjectComponentCreate(project_id=0, name="Roof"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project with ID 0 not found"`.
4. session: `not db.new and not db.dirty`.
5. nothing written.

### PCS-C-06 — W0's project answers 404 as missing
- **Rules:** `create_component` R1 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No component (commit point only).

**When**
- `svc.create_component(db, component_in=ProjectComponentCreate(project_id=P0.id, name="Roof"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOPROJ(P0.id)`.
4. session: `not db.new and not db.dirty`.
5. nothing written.

### PCS-C-07 — W2's project answers 404 and an uncommitted row of the session is discarded
- **Rules:** `create_component` R1 (HR-16), CT3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No component (commit point after this line).
2. extra row X.

**When**
- `svc.create_component(db, component_in=ProjectComponentCreate(project_id=P9.id, name="Roof"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOPROJ(P9.id)`.
4. session: `not db.new and not db.dirty`.
5. count: x_gone.
6. nothing written.

### PCS-C-08 — a private project the caller may not open answers 403, nothing written
- **Rules:** `create_component` R1, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No component (commit point only).

**When**
- `svc.create_component(db, component_in=ProjectComponentCreate(project_id=PB.id, name="Roof"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOACCESS`.
4. session: `not db.new and not db.dirty`.
5. nothing written.

### PCS-C-09 — a project member may add to a private project
- **Rules:** `create_component` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. pmem(PB, UG).

**When**
- `result = svc.create_component(db, component_in=ProjectComponentCreate(project_id=PB.id, name="Roof"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.project_id == PB.id`.
2. committed: the row `result.id` exists, `project_id == PB.id`.

### PCS-C-10 — a soft-deleted project answers 404, nothing written
- **Rules:** `create_component` R2 [BUG-1278]
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (the component is created)

**Given**
1. PD = proj "Delta", deleted.

**When**
- `svc.create_component(db, component_in=ProjectComponentCreate(project_id=PD.id, name="Roof"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOPROJ(PD.id)`.
4. nothing written.

### PCS-C-11 — the name is stored trimmed
- **Rules:** `create_component` R5 [BUG-2272]
- **Kind:** bug
- **Expect:** xfail BUG-2272
- **Fails today on:** Then 2 (stored `"  Roof  "`)

**Given**
1. No component (commit point only).

**When**
- `result = svc.create_component(db, component_in=ProjectComponentCreate(project_id=PA.id, name="  Roof  "), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the row `result.id`: `name == "Roof"`.

### PCS-C-12 — an empty name is refused by the schema
- **Rules:** `create_component` R5 [BUG-2272]
- **Kind:** bug
- **Expect:** xfail BUG-2272
- **Fails today on:** Then 1 (the schema accepts `""`)

**Given**
1. Nothing.

**When**
- build `ProjectComponentCreate(project_id=PA.id, name="")` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCS-C-13 — a whitespace-only name is refused by the schema
- **Rules:** `create_component` R5 [BUG-2272]
- **Kind:** bug
- **Expect:** xfail BUG-2272
- **Fails today on:** Then 1 (the schema accepts `"   "`)

**Given**
1. Nothing.

**When**
- build `ProjectComponentCreate(project_id=PA.id, name="   ")` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCS-C-14 — inner spaces and capitals are kept; the description is kept as typed
- **Rules:** `create_component` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No component (commit point only).

**When**
- `result = svc.create_component(db, component_in=ProjectComponentCreate(project_id=PA.id, name="Roof  DECK", description="  Top part  "), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.name == "Roof  DECK"`.
2. re-read the row `result.id`: `name == "Roof  DECK"`, `description == "  Top part  "`.

### PCS-C-15 — a budget of 0 is accepted
- **Rules:** `create_component` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No component (commit point only).

**When**
- `result = svc.create_component(db, component_in=ProjectComponentCreate(project_id=PA.id, name="Roof", budget=0), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the row `result.id`: `budget == Decimal("0.00")`.

### PCS-C-16 — no budget is accepted
- **Rules:** `create_component` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No component (commit point only).

**When**
- `result = svc.create_component(db, component_in=ProjectComponentCreate(project_id=PA.id, name="Roof", budget=None), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the row `result.id`: `budget is None`.

### PCS-C-17 — 13 integer digits and 2 decimals are accepted
- **Rules:** `create_component` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No component (commit point only).

**When**
- `result = svc.create_component(db, component_in=ProjectComponentCreate(project_id=PA.id, name="Roof", budget=9999999999999.99), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the row `result.id`: `budget == Decimal("9999999999999.99")`.

### PCS-C-18 — a negative budget is refused by the schema
- **Rules:** `create_component` R6 [BUG-2273]
- **Kind:** bug
- **Expect:** xfail BUG-2273
- **Fails today on:** Then 1 (the schema accepts `-0.01`)

**Given**
1. Nothing.

**When**
- build `ProjectComponentCreate(project_id=PA.id, name="Roof", budget=-0.01)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCS-C-19 — a budget with three decimals is refused by the schema
- **Rules:** `create_component` R6 [BUG-2274]
- **Kind:** bug
- **Expect:** xfail BUG-2274
- **Fails today on:** Then 1 (the schema accepts `1000.005`)

**Given**
1. Nothing.

**When**
- build `ProjectComponentCreate(project_id=PA.id, name="Roof", budget=1000.005)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCS-C-20 — a budget with 14 integer digits is refused by the schema
- **Rules:** `create_component` R6 [BUG-2274]
- **Kind:** bug
- **Expect:** xfail BUG-2274
- **Fails today on:** Then 1 (the schema accepts `10000000000000`)

**Given**
1. Nothing.

**When**
- build `ProjectComponentCreate(project_id=PA.id, name="Roof", budget=10000000000000)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCS-C-21 — a failing commit rolls back once and nothing is saved
- **Rules:** `create_component` R7, CT4
- **Kind:** error
- **Expect:** pass

**Given**
1. No component (commit point only).

**When**
- failing commit: `svc.create_component(db, component_in=ProjectComponentCreate(project_id=PA.id, name="Roof"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count == 1`.
3. nothing written.

### PCS-C-22 — a failing re-read leaves the component and its event saved
- **Rules:** `create_component` R7, CT5
- **Kind:** error
- **Expect:** pass

**Given**
1. No component (commit point only).

**When**
- failing refresh: `svc.create_component(db, component_in=ProjectComponentCreate(project_id=PA.id, name="Roof"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: `project_components` with `project_id == PA.id` and `name == "Roof"` has exactly 1 row.
3. committed: evs(PA, "component_created") has exactly 1 row.

## `ProjectComponentService.update_component`

> In this section **CR** = comp(PA, "Roof", 12), but `description "Top"`, `budget 100`, `status ProjectStatusEnum.PLANNING`, unless the card says otherwise.

### PCS-U-01 — a sent field is changed, the others stay, committed and re-read
- **Rules:** `update_component` R3, R7, CT1, CT2
- **Kind:** happy
- **Expect:** pass

**Given**
1. CR.

**When**
- spies: `result = svc.update_component(db, component_id=CR.id, component_in=ProjectComponentUpdate(name="Roof deck"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `isinstance(result, ProjectComponent)`, `result.id == CR.id`, `result.name == "Roof deck"`.
2. mock called: `cm.call_count == 1`, `rb.call_count == 0`.
3. committed: the row CR: `name == "Roof deck"`, `description == "Top"`, `budget == Decimal("100.00")`.
4. committed: the row CR: `project_id == PA.id`, `workspace_id == W1.id`, `status == ProjectStatusEnum.PLANNING`.

### PCS-U-02 — a change writes one component_updated event with the new name
- **Rules:** `update_component` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CR.

**When**
- `result = svc.update_component(db, component_id=CR.id, component_in=ProjectComponentUpdate(name="Roof deck"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.name == "Roof deck"`.
2. committed: evs(PA, "component_updated") has exactly 1 row.
3. committed: that row: `workspace_id == W1.id`, `performed_by == UG.id`, `description == 'Updated component "Roof deck"'`.
4. committed: that row: `metadata_json == {"component_id": CR.id, "component_name": "Roof deck"}`.

### PCS-U-03 — a budget-only change logs the current name
- **Rules:** `update_component` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CR.

**When**
- `result = svc.update_component(db, component_id=CR.id, component_in=ProjectComponentUpdate(budget=250.5), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.budget == Decimal("250.50")`.
2. committed: evs(PA, "component_updated") has exactly 1 row.
3. committed: that row: `description == 'Updated component "Roof"'`, `performed_by == U2.id`.

### PCS-U-04 — any status may follow any status; dates are not compared
- **Rules:** `update_component` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CR, but `status ProjectStatusEnum.COMPLETED`.

**When**
- `result = svc.update_component(db, component_id=CR.id, component_in=ProjectComponentUpdate(status=ProjectStatusEnum.PLANNING, start_date=datetime(2026, 5, 1, 0, 0), end_date=datetime(2026, 4, 1, 0, 0)), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.status == ProjectStatusEnum.PLANNING`.
2. committed: the row CR: `status == ProjectStatusEnum.PLANNING`.
3. committed: the row CR: `start_date == datetime(2026, 5, 1, 0, 0)`, `end_date == datetime(2026, 4, 1, 0, 0)`.

### PCS-U-05 — an unknown id answers 404, rolled back once, nothing written
- **Rules:** `update_component` R1, CT3
- **Kind:** error
- **Expect:** pass

**Given**
1. CR.

**When**
- spies: `svc.update_component(db, component_id=MISSING, component_in=ProjectComponentUpdate(name="New"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException` (spies inside the `pytest.raises`).
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.
4. session: `not db.new and not db.dirty`.
5. mock called: `rb.call_count == 1`, `cm.call_count == 0`.
6. unchanged: unchanged(CR).
7. nothing written.

### PCS-U-06 — W0's component answers 404
- **Rules:** `update_component` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. C0 = comp(P0, "Zero part", 11).
2. CR.

**When**
- `svc.update_component(db, component_id=C0.id, component_in=ProjectComponentUpdate(name="New"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.
4. session: `not db.dirty`.
5. unchanged: unchanged(C0).
6. nothing written.

### PCS-U-07 — W2's component answers 404 and an uncommitted row of the session is discarded
- **Rules:** `update_component` R1, CT3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. CR.
2. C9 = comp(P9, "Nine part", 13) (commit point after this line).
3. extra row X.

**When**
- `svc.update_component(db, component_id=C9.id, component_in=ProjectComponentUpdate(name="New"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.
4. session: `not db.new and not db.dirty`.
5. count: x_gone.
6. unchanged: unchanged(C9).
7. nothing written.

### PCS-U-08 — a component of a private project the caller may not open answers 403
- **Rules:** `update_component` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. CB = comp(PB, "Base", 11).

**When**
- `svc.update_component(db, component_id=CB.id, component_in=ProjectComponentUpdate(name="New"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOACCESS`.
4. session: `not db.dirty`.
5. unchanged: unchanged(CB).
6. nothing written.

### PCS-U-09 — a component of a soft-deleted project answers 404, nothing written
- **Rules:** `update_component` R2 [BUG-1278]
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (the update succeeds)

**Given**
1. PD = proj "Delta", deleted.
2. CD = comp(PD, "Door", 11).

**When**
- `svc.update_component(db, component_id=CD.id, component_in=ProjectComponentUpdate(name="New"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOPROJ(PD.id)`.
4. unchanged: unchanged(CD).
5. nothing written.

### PCS-U-10 — an explicit null clears the description
- **Rules:** `update_component` R3a [BUG-2275]
- **Kind:** bug
- **Expect:** xfail BUG-2275
- **Fails today on:** Then 2 (the old description stays)

**Given**
1. CR.

**When**
- `result = svc.update_component(db, component_id=CR.id, component_in=ProjectComponentUpdate(description=None), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == CR.id`.
2. re-read CR: `description is None`.
3. re-read CR: `name == "Roof"`, `budget == Decimal("100.00")`.

### PCS-U-11 — an explicit null clears the budget
- **Rules:** `update_component` R3a [BUG-2275]
- **Kind:** bug
- **Expect:** xfail BUG-2275
- **Fails today on:** Then 2 (the budget stays 100.00)

**Given**
1. CR.

**When**
- `result = svc.update_component(db, component_id=CR.id, component_in=ProjectComponentUpdate(budget=None), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == CR.id`.
2. re-read CR: `budget is None`.

### PCS-U-12 — explicit nulls clear the deadline and the dates
- **Rules:** `update_component` R3a [BUG-2275]
- **Kind:** bug
- **Expect:** xfail BUG-2275
- **Fails today on:** Then 2 (the deadline stays)

**Given**
1. CR, but `deadline datetime(2026, 6, 1, 0, 0)`, `start_date datetime(2026, 5, 1, 0, 0)`, `end_date datetime(2026, 7, 1, 0, 0)`.

**When**
- `result = svc.update_component(db, component_id=CR.id, component_in=ProjectComponentUpdate(deadline=None, start_date=None, end_date=None), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == CR.id`.
2. re-read CR: `deadline is None`.
3. re-read CR: `start_date is None`.
4. re-read CR: `end_date is None`.

### PCS-U-13 — a null name is refused by the schema
- **Rules:** `update_component` R3a [BUG-2275]
- **Kind:** bug
- **Expect:** xfail BUG-2275
- **Fails today on:** Then 1 (the schema accepts `name=None`)

**Given**
1. Nothing.

**When**
- build `ProjectComponentUpdate(name=None)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCS-U-14 — a null status is refused by the schema
- **Rules:** `update_component` R3a [BUG-2275]
- **Kind:** bug
- **Expect:** xfail BUG-2275
- **Fails today on:** Then 1 (the schema accepts `status=None`)

**Given**
1. Nothing.

**When**
- build `ProjectComponentUpdate(status=None)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCS-U-15 — an empty update returns the component unchanged
- **Rules:** `update_component` R3, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CR.

**When**
- `result = svc.update_component(db, component_id=CR.id, component_in=ProjectComponentUpdate(), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == CR.id`, `result.name == "Roof"`.
2. unchanged: unchanged(CR).

### PCS-U-16 — an empty update writes no event
- **Rules:** `update_component` R4 [BUG-2276]
- **Kind:** bug
- **Expect:** xfail BUG-2276
- **Fails today on:** Then 2 (one `component_updated` event is written)

**Given**
1. CR.

**When**
- `result = svc.update_component(db, component_id=CR.id, component_in=ProjectComponentUpdate(), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == CR.id`.
2. count: evs(PA, "component_updated") has exactly 0 rows.

### PCS-U-17 — sending the same values writes no event
- **Rules:** `update_component` R4 [BUG-2276]
- **Kind:** bug
- **Expect:** xfail BUG-2276
- **Fails today on:** Then 2 (one `component_updated` event is written)

**Given**
1. CR.

**When**
- `result = svc.update_component(db, component_id=CR.id, component_in=ProjectComponentUpdate(name="Roof", description="Top", budget=100), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == CR.id`.
2. count: evs(PA, "component_updated") has exactly 0 rows.

### PCS-U-18 — a sent name is stored trimmed
- **Rules:** `update_component` R5 [BUG-2272]
- **Kind:** bug
- **Expect:** xfail BUG-2272
- **Fails today on:** Then 2 (stored `"  Roof deck  "`)

**Given**
1. CR.

**When**
- `result = svc.update_component(db, component_id=CR.id, component_in=ProjectComponentUpdate(name="  Roof deck  "), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == CR.id`.
2. re-read CR: `name == "Roof deck"`.

### PCS-U-19 — a whitespace-only name is refused by the update schema
- **Rules:** `update_component` R5 [BUG-2272]
- **Kind:** bug
- **Expect:** xfail BUG-2272
- **Fails today on:** Then 1 (the schema accepts `"   "`)

**Given**
1. Nothing.

**When**
- build `ProjectComponentUpdate(name="   ")` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCS-U-20 — a budget of 0 is accepted on update
- **Rules:** `update_component` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CR.

**When**
- `result = svc.update_component(db, component_id=CR.id, component_in=ProjectComponentUpdate(budget=0), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == CR.id`.
2. re-read CR: `budget == Decimal("0.00")`.

### PCS-U-21 — a negative budget is refused by the update schema
- **Rules:** `update_component` R6 [BUG-2273]
- **Kind:** bug
- **Expect:** xfail BUG-2273
- **Fails today on:** Then 1 (the schema accepts `-0.01`)

**Given**
1. Nothing.

**When**
- build `ProjectComponentUpdate(budget=-0.01)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCS-U-22 — a budget with three decimals is refused by the update schema
- **Rules:** `update_component` R6 [BUG-2274]
- **Kind:** bug
- **Expect:** xfail BUG-2274
- **Fails today on:** Then 1 (the schema accepts `1000.005`)

**Given**
1. Nothing.

**When**
- build `ProjectComponentUpdate(budget=1000.005)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCS-U-23 — a failing commit rolls back once and nothing is saved
- **Rules:** `update_component` R7, CT4
- **Kind:** error
- **Expect:** pass

**Given**
1. CR.

**When**
- failing commit: `svc.update_component(db, component_id=CR.id, component_in=ProjectComponentUpdate(name="Roof deck"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count == 1`.
3. unchanged: unchanged(CR).
4. nothing written.

### PCS-U-24 — a failing re-read leaves the change saved
- **Rules:** `update_component` R7, CT5
- **Kind:** error
- **Expect:** pass

**Given**
1. CR.

**When**
- failing refresh: `svc.update_component(db, component_id=CR.id, component_in=ProjectComponentUpdate(name="Roof deck"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: the row CR: `name == "Roof deck"`.

### PCS-U-25 — a sent project_id is ignored; the other fields are applied
- **Rules:** `update_component` R3b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CR.

**When**
- `result = svc.update_component(db, component_id=CR.id, component_in=ProjectComponentUpdate(project_id=PB.id, name="Roof deck", deadline=datetime(2026, 6, 1, 14, 30)), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.project_id == PA.id`, `result.name == "Roof deck"`.
2. committed: the row CR: `project_id == PA.id`.
3. committed: the row CR: `name == "Roof deck"`, `deadline == datetime(2026, 6, 1, 14, 30)`.
4. committed: evs(PB, "component_updated") has exactly 0 rows.

## `ProjectComponentService.delete_component`

> In this section **CR** = comp(PA, "Roof", 12), unless the card says otherwise. Blocker cards are BUG-1196, strict; each asserts the exact blocker list.

### PCS-D-01 — a component without history is deleted, committed, and True is returned
- **Rules:** `delete_component` R6a, CT1
- **Kind:** happy
- **Expect:** pass

**Given**
1. CR.
2. C2 = comp(PA, "Axle", 13).

**When**
- spies: `result = svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is True`.
2. mock called: `cm.call_count == 1`, `rb.call_count == 0`.
3. committed: `db.get(ProjectComponent, CR.id) is None`.
4. committed: `db.get(ProjectComponent, C2.id) is not None`.

### PCS-D-02 — deleting writes one component_deleted event that stays
- **Rules:** `delete_component` R6a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CR.

**When**
- `result = svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is True`.
2. committed: evs(PA, "component_deleted") has exactly 1 row.
3. committed: that row: `workspace_id == W1.id`, `performed_by == UG.id`, `description == 'Deleted component "Roof"'`.
4. committed: that row: `metadata_json == {"component_id": CR.id, "component_name": "Roof"}`.

### PCS-D-03 — an attachment_added log row does not block and goes with the component
- **Rules:** `delete_component` R5, R6a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CR.
2. A1 = act(CR, "attachment_added").

**When**
- `result = svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is True`.
2. committed: `db.get(ProjectComponent, CR.id) is None`.
3. committed: `db.get(ProjectComponentActivityEvent, A1.id) is None`.

### PCS-D-04 — an attachment_removed log row does not block and goes with the component
- **Rules:** `delete_component` R5, R6a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CR.
2. A1 = act(CR, "attachment_removed").

**When**
- `result = svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is True`.
2. committed: `db.get(ProjectComponent, CR.id) is None`.
3. committed: `db.get(ProjectComponentActivityEvent, A1.id) is None`.

### PCS-D-05 — the project's own events do not block and stay
- **Rules:** `delete_component` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CR.
2. E1 = pev(PA).

**When**
- `result = svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is True`.
2. committed: `db.get(ProjectComponent, CR.id) is None`.
3. committed: `db.get(ProjectEvent, E1.id) is not None`.

### PCS-D-06 — attachment-link rows do not block and are removed with the component
- **Rules:** `delete_component` R5a [BUG-2262], R6a
- **Kind:** bug
- **Expect:** xfail BUG-2262
- **Fails today on:** Then 1 (the call raises IntegrityError: the ORM nulls the link row's NOT NULL `project_component_id` before the delete)

**Given**
1. CR.
2. C2 = comp(PA, "Axle", 13).
3. AT0.
4. LK = att(CR).
5. LK2 = att(C2).

**When**
- `result = svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is True`.
2. committed: `db.get(ProjectComponent, CR.id) is None`.
3. committed: `db.get(ProjectComponentAttachment, LK.id) is None`.
4. committed: `db.get(Attachment, AT0.id) is not None`.
5. committed: `db.get(ProjectComponentAttachment, LK2.id) is not None`, its `project_component_id == C2.id`.
6. committed: `db.get(ProjectComponent, C2.id) is not None`.
7. committed: evs(PA, "component_deleted") has exactly 1 row.
8. committed: that row: `description == 'Deleted component "Roof"'`, `metadata_json == {"component_id": CR.id, "component_name": "Roof"}`.

### PCS-D-07 — an unknown id answers 404, rolled back once
- **Rules:** `delete_component` R1, Errors, CT3
- **Kind:** error
- **Expect:** pass

**Given**
1. CR.

**When**
- spies: `svc.delete_component(db, component_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException` (spies inside the `pytest.raises`).
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.
4. session: `not db.deleted and not db.new`.
5. mock called: `rb.call_count == 1`, `cm.call_count == 0`.
6. nothing written.

### PCS-D-08 — W0's component answers 404 and stays
- **Rules:** `delete_component` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. C0 = comp(P0, "Zero part", 11).
2. CR.

**When**
- `svc.delete_component(db, component_id=C0.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.
4. session: `not db.deleted and not db.new`.
5. nothing written.

### PCS-D-09 — W2's component answers 404 and an uncommitted row of the session is discarded
- **Rules:** `delete_component` R1, CT3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. CR.
2. C9 = comp(P9, "Nine part", 13) (commit point after this line).
3. extra row X.

**When**
- `svc.delete_component(db, component_id=C9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.
4. session: `not db.deleted and not db.new`.
5. count: x_gone.
6. nothing written.

### PCS-D-10 — a component of a private project the caller may not open answers 403
- **Rules:** `delete_component` R1, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. CB = comp(PB, "Base", 11).

**When**
- `svc.delete_component(db, component_id=CB.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOACCESS`.
4. session: `not db.deleted and not db.new`.
5. nothing written.

### PCS-D-11 — a component of a soft-deleted project answers 404 and stays
- **Rules:** `delete_component` R1 [BUG-1278], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (the component is deleted)

**Given**
1. PD = proj "Delta", deleted.
2. CD = comp(PD, "Door", 11).

**When**
- `svc.delete_component(db, component_id=CD.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOPROJ(PD.id)`.
4. nothing written.

### PCS-D-12 — a W1 component whose project is in W2 answers the project's 404 (pass-through)
- **Rules:** `delete_component` R1 (manager `require_component_access` R4)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. CX = comp(P9, "Stray", 11), but `workspace_id W1.id`.

**When**
- `svc.delete_component(db, component_id=CX.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOPROJ(P9.id)`.
4. nothing written.

### PCS-D-13 — a live work order blocks the delete
- **Rules:** `delete_component` R2, R3 [BUG-1196]
- **Kind:** bug
- **Expect:** xfail BUG-1196
- **Fails today on:** Then 1 (no error: the delete succeeds and clears the link)

**Given**
1. CR.
2. WT1.
3. O1 = wo(CR, "WO-1").

**When**
- `svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.status_code == 400`, `exc.value.detail == "Component has history"`.
3. raises: `exc.value.errors == [{"type": "work_order", "id": O1.id}]`.
4. session: `not db.deleted and not db.dirty`.
5. re-read O1: `project_component_id == CR.id`.
6. unchanged: unchanged(CR).
7. count: evs(PA, "component_deleted") has exactly 0 rows.

### PCS-D-14 — a soft-deleted work order still blocks
- **Rules:** `delete_component` R3 [BUG-1196]
- **Kind:** bug
- **Expect:** xfail BUG-1196
- **Fails today on:** Then 1 (no error: the delete succeeds)

**Given**
1. CR.
2. WT1.
3. O1 = wo(CR, "WO-1"), deleted wo.

**When**
- `svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.errors == [{"type": "work_order", "id": O1.id}]`.
3. session: `not db.deleted and not db.dirty`.
4. unchanged: unchanged(CR).
5. count: evs(PA, "component_deleted") has exactly 0 rows.

### PCS-D-15 — a ledger row blocks the delete
- **Rules:** `delete_component` R3 [BUG-1196]
- **Kind:** bug
- **Expect:** xfail BUG-1196
- **Fails today on:** Then 1 (the call raises IntegrityError at the flush)

**Given**
1. CR.
2. I1.
3. LG = ledger(CR).

**When**
- `svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.errors == [{"type": "ledger_entry", "id": LG.id}]`.
3. session: `not db.deleted and not db.dirty`.
4. re-read LG: `project_component_id == CR.id`.
5. unchanged: unchanged(CR).
6. count: evs(PA, "component_deleted") has exactly 0 rows.

### PCS-D-16 — an item line blocks the delete
- **Rules:** `delete_component` R3 [BUG-1196]
- **Kind:** bug
- **Expect:** xfail BUG-1196
- **Fails today on:** Then 1 (the call raises IntegrityError at the flush)

**Given**
1. CR.
2. I1.
3. L1 = line(CR).

**When**
- `svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.errors == [{"type": "component_item", "id": L1.id}]`.
3. session: `not db.deleted and not db.dirty`.
4. re-read L1: `project_component_id == CR.id`.
5. unchanged: unchanged(CR).

### PCS-D-17 — a task blocks the delete
- **Rules:** `delete_component` R3 [BUG-1196]
- **Kind:** bug
- **Expect:** xfail BUG-1196
- **Fails today on:** Then 1 (the call raises IntegrityError at the flush)

**Given**
1. CR.
2. T1 = task(CR, "Paint").

**When**
- `svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.errors == [{"type": "task", "id": T1.id}]`.
3. session: `not db.deleted and not db.dirty`.
4. re-read T1: `project_component_id == CR.id`.
5. unchanged: unchanged(CR).

### PCS-D-18 — a note blocks the delete as a task
- **Rules:** `delete_component` R3 [BUG-1196]
- **Kind:** bug
- **Expect:** xfail BUG-1196
- **Fails today on:** Then 1 (the call raises IntegrityError at the flush)

**Given**
1. CR.
2. N1 = note(CR, "Remember").

**When**
- `svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.errors == [{"type": "task", "id": N1.id}]`.
3. session: `not db.deleted and not db.dirty`.
4. unchanged: unchanged(CR).

### PCS-D-19 — a miscellaneous cost blocks the delete
- **Rules:** `delete_component` R3 [BUG-1196]
- **Kind:** bug
- **Expect:** xfail BUG-1196
- **Fails today on:** Then 1 (no error: the delete succeeds and clears the link)

**Given**
1. CR.
2. MC = misc(CR).

**When**
- `svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.errors == [{"type": "misc_cost", "id": MC.id}]`.
3. session: `not db.deleted and not db.dirty`.
4. re-read MC: `project_component_id == CR.id`.
5. unchanged: unchanged(CR).

### PCS-D-20 — an activity event other than an attachment one blocks the delete
- **Rules:** `delete_component` R3 [BUG-1196]
- **Kind:** bug
- **Expect:** xfail BUG-1196
- **Fails today on:** Then 1 (no error: the delete succeeds, the log row goes by cascade)

**Given**
1. CR.
2. A1 = act(CR, "work_order_item_used").
3. A2 = act(CR, "attachment_added").

**When**
- `svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.errors == [{"type": "activity_event", "id": A1.id}]`.
3. session: `not db.deleted and not db.dirty`.
4. re-read A1: `project_component_id == CR.id`.
5. unchanged: unchanged(CR).

### PCS-D-21 — blockers are sorted by type, then id
- **Rules:** `delete_component` R3 [BUG-1196]
- **Kind:** bug
- **Expect:** xfail BUG-1196
- **Fails today on:** Then 1 (the call raises IntegrityError at the flush)

**Given**
1. CR.
2. A1 = act(CR, "work_order_item_used").
3. TB = task(CR, "Sand"), but `id XID(2)`.
4. TA = task(CR, "Paint"), but `id XID(1)` (built after TB, lower id).
5. WT1.
6. O1 = wo(CR, "WO-1").

**When**
- `svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.errors == [{"type": "work_order", "id": O1.id}, {"type": "task", "id": TA.id}, {"type": "task", "id": TB.id}, {"type": "activity_event", "id": A1.id}]`.
3. unchanged: unchanged(CR).

### PCS-D-22 — a linked row of another workspace alone refuses, shown as one generic entry
- **Rules:** `delete_component` R4 [BUG-1196]
- **Kind:** bug
- **Expect:** xfail BUG-1196
- **Fails today on:** Then 1 (the call raises IntegrityError at the flush)

**Given**
1. CR.
2. T9 = task(CR, "Paint"), but `workspace_id W2.id`.

**When**
- `svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.errors == [{"type": "other_workspace"}]`.
3. session: `not db.deleted and not db.dirty`.
4. unchanged: unchanged(CR).

### PCS-D-23 — rows of W0 and W2 give one other_workspace entry, last
- **Rules:** `delete_component` R3, R4 [BUG-1196]
- **Kind:** bug
- **Expect:** xfail BUG-1196
- **Fails today on:** Then 1 (the call raises IntegrityError at the flush)

**Given**
1. CR.
2. T0 = task(CR, "Prime"), but `workspace_id W0.id`.
3. T1 = task(CR, "Paint").
4. T9 = task(CR, "Sand"), but `workspace_id W2.id`.

**When**
- `svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.errors == [{"type": "task", "id": T1.id}, {"type": "other_workspace"}]`.
3. unchanged: unchanged(CR).

### PCS-D-24 — a refused delete rolls back once and discards the session's other changes
- **Rules:** `delete_component` R2 [BUG-1196], CT3
- **Kind:** bug
- **Expect:** xfail BUG-1196
- **Fails today on:** Then 1 (the call raises IntegrityError, not ValidationError)

**Given**
1. CR.
2. T1 = task(CR, "Paint") (commit point after this line).
3. extra row X.

**When**
- spies: `svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `ValidationError` (spies inside the `pytest.raises`).
2. mock called: `rb.call_count == 1`, `cm.call_count == 0`.
3. count: x_gone.
4. unchanged: unchanged(CR).
5. nothing written.

### PCS-D-25 — a failing commit rolls back once and the component stays
- **Rules:** `delete_component` R7, CT4
- **Kind:** error
- **Expect:** pass

**Given**
1. CR.

**When**
- failing commit: `svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count == 1`.
3. unchanged: unchanged(CR).
4. nothing written.

### PCS-D-26 — an activity event spelled "Attachment_added" blocks (exact compare)
- **Rules:** `delete_component` R3 [BUG-1196]
- **Kind:** bug
- **Expect:** xfail BUG-1196
- **Fails today on:** Then 1 (no error: the delete succeeds, the log row goes by cascade)

**Given**
1. CR.
2. A1 = act(CR, "Attachment_added").

**When**
- `svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.errors == [{"type": "activity_event", "id": A1.id}]`.
3. session: `not db.deleted and not db.dirty`.
4. re-read A1: `event_type == "Attachment_added"`.
5. unchanged: unchanged(CR).

### PCS-D-27 — an activity event spelled "attachment_added " (trailing space) blocks (exact compare)
- **Rules:** `delete_component` R3 [BUG-1196]
- **Kind:** bug
- **Expect:** xfail BUG-1196
- **Fails today on:** Then 1 (no error: the delete succeeds, the log row goes by cascade)

**Given**
1. CR.
2. A1 = act(CR, "attachment_added ").

**When**
- `svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.errors == [{"type": "activity_event", "id": A1.id}]`.
3. session: `not db.deleted and not db.dirty`.
4. re-read A1: `event_type == "attachment_added "`.
5. unchanged: unchanged(CR).

### PCS-D-28 — an activity event spelled "attachment_add" blocks (exact compare)
- **Rules:** `delete_component` R3 [BUG-1196]
- **Kind:** bug
- **Expect:** xfail BUG-1196
- **Fails today on:** Then 1 (no error: the delete succeeds, the log row goes by cascade)

**Given**
1. CR.
2. A1 = act(CR, "attachment_add").

**When**
- `svc.delete_component(db, component_id=CR.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.errors == [{"type": "activity_event", "id": A1.id}]`.
3. session: `not db.deleted and not db.dirty`.
4. re-read A1: `event_type == "attachment_add"`.
5. unchanged: unchanged(CR).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| BUG-1277 (endpoint `limit`) | `GET /project-components/` | `limit >= 1` (422), cap 100 |
| schema refusals → HTTP 422 (BUG-461) | endpoints | status code of a `ProjectComponentCreate` / `Update` refusal |
| D1 dead branches | dead-code checklist | the endpoints' three `if not …: 404` and service lines 100–101, 134–135 removed |
| BUG-1197 | frontend | the blocker list of a refused delete is shown |
| BUG-1198 | the new activity read method | not specified until it exists |

## Spec gaps
None. Gaps 1–5 of revision 1 are closed by the spec's Gap log G1–G5 (2026-11-04).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_components` | R1 | PCS-L-29 … L-34, L-37, L-38 |
| `get_components` | R1 [BUG-2278] | PCS-L-36 |
| `get_components` | R1 (DAO BUG-1275 pass-through) | PCS-L-39 |
| `get_components` | R2 [BUG-1278] | PCS-L-35 |
| `get_components` | R3 | PCS-L-01 … L-18 |
| `get_components` | R4 [BUG-1278] | PCS-L-19, L-22 |
| `get_components` | R5 [BUG-2277] | PCS-L-20, L-21, L-23 |
| `get_components` | R6 default page | PCS-L-24 |
| `get_components` | R6 [BUG-2279] | PCS-L-25, L-26, L-27, L-28 |
| `get_components` | R7 / CT6 | PCS-L-41, L-42, L-43 |
| `get_components` | Errors (HTTPException; negative skip DataError) | PCS-L-30 … L-33, L-40 |
| `get_by_id` | R1 | PCS-G-01 … G-07, G-09 |
| `get_by_id` | R2 [BUG-1278] | PCS-G-08 |
| `get_by_id` | R3 / CT6 | PCS-G-10, G-11 |
| `create_component` | R1 / Errors 404, 403 | PCS-C-04 … C-09 |
| `create_component` | R2 [BUG-1278] | PCS-C-10 |
| `create_component` | R3, CT1, CT2 | PCS-C-01, C-02 |
| `create_component` | R4 | PCS-C-03 |
| `create_component` | R5 [BUG-2272] | PCS-C-11, C-12, C-13; untagged part C-14 |
| `create_component` | R6 [BUG-2273, BUG-2274] | PCS-C-18, C-19, C-20; accepted C-15, C-16, C-17 |
| `create_component` | R7, CT3, CT4, CT5 / Errors database | PCS-C-04, C-07, C-21, C-22 |
| `update_component` | R1 | PCS-U-05 … U-08 |
| `update_component` | R2 [BUG-1278] | PCS-U-09 |
| `update_component` | R3 | PCS-U-01, U-04, U-15 |
| `update_component` | R3b | PCS-U-25 |
| `update_component` | R3a [BUG-2275] | PCS-U-10 … U-14 |
| `update_component` | R4 | PCS-U-02, U-03 |
| `update_component` | R4 [BUG-2276] | PCS-U-16, U-17 |
| `update_component` | R5 [BUG-2272] | PCS-U-18, U-19 |
| `update_component` | R6 [BUG-2273, BUG-2274] | PCS-U-21, U-22; accepted U-20 |
| `update_component` | R7, CT1–CT5 | PCS-U-01, U-05, U-07, U-23, U-24 |
| `delete_component` | R1 / Errors 404, 403 | PCS-D-07 … D-10, D-12 |
| `delete_component` | R1 [BUG-1278] | PCS-D-11 |
| `delete_component` | R2 [BUG-1196] / Errors 400 | PCS-D-13 … D-24, D-26 … D-28 |
| `delete_component` | R3 [BUG-1196] | PCS-D-13 … D-21, D-23, D-26, D-27, D-28 (exact compare) |
| `delete_component` | R4 [BUG-1196] | PCS-D-22, D-23 |
| `delete_component` | R5 | PCS-D-03 … D-05 |
| `delete_component` | R5a [BUG-2262] | PCS-D-06 |
| `delete_component` | R6 (today, record) | Fails-today lines of PCS-D-13 … D-24 |
| `delete_component` | R6a, CT1 | PCS-D-01, D-02 |
| `delete_component` | R7, CT3, CT4 | PCS-D-07, D-09, D-24, D-25 |
