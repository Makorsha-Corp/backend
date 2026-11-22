# Test cases — `app/services/work_order_template_service.py`

> **Spec:** `tests/unit/services/work_order_template_service.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-07; nothing open). The owner answered OQ-19 (BUG-2345), OQ-20 (today's behaviour intended) and OQ-21 (BUG-2346); they reach this service as pass-through.
> **Revision:** 2 (2026-11-07) — spec revision 2026-11-07 and its Gap log. New: WTSV-C-09 (`create_template` R2a, BUG-2346), WTSV-U-06 (R2a on update, BUG-2346), WTSV-GD-08 (`generate_drafts` R1a, BUG-2345), all strict xfail; WTSV-GD-09, the passing companion of GD-08 (the not-due template's date stays). Changed: WTSV-GD-04's patch target (the `work_order_manager` singleton); Conventions name the model modules from the spec's Facts (G1); gap 2 closed by G2 with no card change. No card retired; Spec gaps closed.
> **Revision:** 3 (2026-11-09) — `work_order_template_service.verify.md` findings 1–2 and mutant #8. Finding 1: WTSV-L-01 gains a third matching row A0, so `limit=1` cuts a row; new WTSV-L-04 (101 templates, no `limit` → 100; mutant #8). Finding 2: new WTSV-GD-10, as GD-03 with a `RuntimeError` (any exception rolls back, R3). No card retired.
> **Counts:** 50 cases · 41 expected-to-pass · 9 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Per callable:** `create_template` 9 (4 bug) · `update_template` 6 (3 bug) · `get_template` 3 · `list_templates` 4 · `delete_template` 4 · `restore_template` 2 · `add_item` 3 · `update_item` 2 · `remove_item` 3 · `get_items` 2 · `get_approvers` 2 · `generate_drafts` 10 (2 bug).
- **Depth:** lighter (skill step 1a, the owner's setting for services): TC1 and TC3 once per write, TC2, TC4, TC5 once on `create_template`, TC4 again on the two writes with no re-read, TC6 once per read, TC5 once more on `generate_drafts` (its own re-read loop, R4). One pass-through card per cited bug: BUG-1228, BUG-2334, BUG-2335 (create, and the update that must undo its fields, R2), BUG-2340, BUG-2344, BUG-2345, BUG-2346 (create and update). Money: `cost` 0.125 → 0.13 and `quantity` 2.125 → 2.13 through the column (HR-15; half-to-even would give 0.12 and 2.12).
- **Owner answers (2026-11-07).** OQ-21 → BUG-2346: C-09 and U-06 are the only cards with `requires_approval: true` and no approver; every other such card also has an active approver. OQ-19 → BUG-2345: GD-08 (no draft) and its passing companion GD-09 (the date does not move, true today and after) are the only section runs over a recurring template that is not due. OQ-20 → intended: every due template here is due exactly on `target_date`, so the next date (2026-03-23) holds under either reading; the overdue case is the manager's.
- **Notable design choices:**
  - Commit point, extra row X and spies as `work_order_type_service.cases.md`; every refusal checks the session (`db.new`, `db.dirty`, `db.deleted` empty) before any re-read.
  - Another workspace's id at a lower id (W0's row) and at a higher id (W2's row), split across methods; `create_template` gets both (C-02, C-03).
  - `generate_drafts` R1 is proved per argument: a section run makes a draft from a non-recurring template only when `factory_section_id` arrives (GD-06); a factory run naming another factory makes none from a due template only when `factory_id` arrives (GD-07).
  - Four `Author: claude` cards: GD-03 and GD-10 (the manager is patched to write and then raise an `HTTPException` / a `RuntimeError`, TC3), GD-04 (BUG-2344, `create_work_order_from_template` patched on the `work_order_manager` singleton to fail for one template), GD-05 (refresh fails on the draft).
  - No permission check exists (`docs/future/permissions.md`): no grant cards.
- **Needs a decision:** None. Spec gaps 1–2 closed by the spec's Gap log (G1, G2).

## Conventions for this module

**IDs.** `WTSV` = `app/services/work_order_template_service.py`. `C` create_template · `U` update_template · `G` get_template · `L` list_templates · `D` delete_template · `S` restore_template · `A` add_item · `I` update_item · `R` remove_item · `N` get_items · `P` get_approvers · `GD` generate_drafts.

**Actors and fixed values.**
- `svc` = the singleton `work_order_template_service` (`from app.services.work_order_template_service import WorkOrderTemplateService, work_order_template_service`). `db` = the test's real session, first argument; every other argument by keyword. `result` = what the When call returns.
- Classes: `WorkOrderTemplate`, `WorkOrderTemplateItem`, `WorkOrderTemplateApprover`, `WorkOrderType`, `WorkOrder`, `WorkspaceMember`, `Item`, `Factory`, `FactorySection`, `Machine`, `MachineSectionAssignment` = the model of the same name in `app.models.<snake_case name>` (spec Facts: e.g. `app.models.work_order_template_approver.WorkOrderTemplateApprover`, `app.models.machine_section_assignment.MachineSectionAssignment`, `app.models.work_order.WorkOrder`). `work_order_manager` = the singleton in `app.managers.work_order_manager`. `WorkOrderTemplateCreate`, `WorkOrderTemplateUpdate`, `WorkOrderTemplateItemCreate`, `WorkOrderTemplateItemUpdate`, `GenerateWorkOrderDraftsRequest` (`app.schemas.work_order_template`). `HTTPException` (`fastapi`), `inspect`, `text`, `select`, `func` (`sqlalchemy`), `patch` (`unittest.mock`), `Decimal`, `date`, `datetime`.
- MISSING = `999999999`. T0, T1, T2, T3 = `datetime(2026, 3, 4, 9, 0, 0)` … `datetime(2026, 3, 4, 12, 0, 0)`. D16 = `date(2026, 3, 16)` (a Monday), D17 = `date(2026, 3, 17)`, D23 = `date(2026, 3, 23)`, D30 = `date(2026, 3, 30)`.
- **Standing rows** (every test, in this order, no Given line): W0, W1, W2 = `make_workspace(db)` ×3 (`W0.id < W1.id < W2.id`); U1, U2 = `make_profile(db)` ×2; MB1 = `WorkspaceMember(workspace_id=W1.id, user_id=U1.id, role="member", status="active")`, MB2 the same for U2; WT0, WT1, WT2 = `WorkOrderType(workspace_id=Wk.id, name="Service")` for W0, W1, W2; I1 = `Item(workspace_id=W1.id, name="Oil filter", name_normalized="oil filter", unit="pcs")`, I2 = the same with `"Belt"`, `"belt"`. U1 is the acting user; U2 made the Given rows.

**Externals.** None is mocked, except in `Author: claude` cards that say so. Timestamps from the model are checked only `is not None` or "loaded".

**Given rows.** Built directly (never through `svc`), flushed one at a time in the order written. The session does not autoflush. A Given line written as code is a step to run exactly as written.
- **template** = `WorkOrderTemplate(workspace_id=W1.id, template_name="Oil change", work_order_type_id=WT1.id, created_by=U2.id, created_at=T0)`; other columns at their defaults (`is_active` true, booleans false, `updated_by`, `updated_at` NULL). After "but" the card lists every column that differs. A W0 / W2 template also takes WT0 / WT2.
- **inactive** (after "but") = `is_active False`, `updated_by U2.id`, `updated_at T0`.
- **line on T** = `WorkOrderTemplateItem(workspace_id=W1.id, work_order_template_id=T.id, item_id=I1.id, quantity=Decimal("2.00"))`. **approver U on T** = `WorkOrderTemplateApprover(workspace_id=W1.id, work_order_template_id=T.id, user_id=U.id)`. After "but", differing columns.
- **plant** = four rows in this order: F1 = `Factory(workspace_id=W1.id, name="Plant", abbreviation="PL")`; S1 = `FactorySection(workspace_id=W1.id, factory_id=F1.id, name="Packing")`; M1 = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Press 1")`; `MachineSectionAssignment(workspace_id=W1.id, machine_id=M1.id, factory_section_id=S1.id)`.
- **recurring** (after "but") = `is_recurring True`, `recurrence_type "weekly"`, `next_generation_date D16`, `default_machine_id M1.id`.
- **commit point** = after the last Given line, `db.commit()` (a savepoint release under the `db` fixture). Snapshots for `unchanged` and `nothing written` are taken there.
- **extra row X** (after the commit point, only where listed) = `X = WorkOrderTemplate(workspace_id=W2.id, template_name="Extra", work_order_type_id=WT2.id, created_at=T0)`, `db.add(X)`, `db.flush()`; not committed. `X_ID = X.id`.

**Named checks.**
- **re-read X** = `db.expire_all()`, then `db.get(<class of X>, X.id)`. **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **nothing written** = the numbers of rows in `work_order_templates`, `work_order_template_items`, `work_order_template_approvers`, `work_orders` (all workspaces) equal their values at the commit point.
- **approvers(T)** = `{a.user_id for a in db.scalars(select(WorkOrderTemplateApprover).where(WorkOrderTemplateApprover.work_order_template_id == T.id))}` after `db.expire_all()`. **drafts(T)** = the number of `WorkOrder` rows with `work_order_template_id == T.id`, fresh query.
- **x_gone** = no `work_order_templates` row has `id == X_ID`; **x_kept** = exactly one has.
- `loaded:` lines run on the returned object first: each column named is not in `inspect(obj).unloaded` (column attributes only).
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads or counts with a fresh query.
- `session:` lines check `db` directly after the call, before anything re-reads: "clean" = `not db.new`, `not db.dirty`, `not db.deleted` (three asserts); "usable" = `db.execute(text("SELECT 1")).scalar() == 1`.
- `raises: HTTPException` = plain `with pytest.raises(HTTPException) as exc:` around the call, **no** savepoint. Further `raises:` lines assert on `exc.value` after the block.
- **failing commit** / **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` / `with patch.object(db, "refresh", side_effect=RuntimeError("boom")):` around the When. **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.

**xfail cards.** Write the call and checks as shown. All strict: `pytest.mark.xfail(strict=True, reason="BUG-NNN")`.

**Race simulations.** None.

## `WorkOrderTemplateService.create_template`

### WTSV-C-01 — the template, its line and its approver are committed; the template returned re-read
- **Rules:** `create_template` R1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no templates (commit point after this line).

**When**
- `result = svc.create_template(db, tpl_in=WorkOrderTemplateCreate(template_name="Oil change", work_order_type_id=WT1.id, cost=Decimal("12.50"), requires_approval=True, items=[WorkOrderTemplateItemCreate(item_id=I1.id, quantity=Decimal("2"))], approver_user_ids=[U2.id]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `created_at`, `template_name`, `work_order_type_id`, `cost`, `created_by`.
2. returns: `isinstance(result, WorkOrderTemplate)`, `result.id is not None`, `result.created_at is not None`.
3. returns: `result.template_name == "Oil change"`, `result.workspace_id == W1.id`, `result.created_by == U1.id`, `result.is_active is True`.
4. committed: the `work_order_templates` row with `id == result.id` exists: `cost == Decimal("12.50")`, `work_order_type_id == WT1.id`.
5. committed: exactly 1 `work_order_template_items` row with `work_order_template_id == result.id`: `item_id == I1.id`, `quantity == Decimal("2.00")`, `action_type == "CONSUME"`.
6. committed: the approver user ids of the template `== {U2.id}`.

### WTSV-C-02 — a type of another workspace (higher id): the 404 passes unchanged; no template, line or approver saved
- **Rules:** `create_template` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no templates (commit point after this line).
2. extra row X.

**When**
- `svc.create_template(db, tpl_in=WorkOrderTemplateCreate(template_name="Oil change", work_order_type_id=WT2.id, requires_approval=True, items=[WorkOrderTemplateItemCreate(item_id=I1.id)], approver_user_ids=[U2.id]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Work order type with ID {WT2.id} not found"`.
3. session: clean.
4. count: x_gone.
5. nothing written: nothing written.
6. session: usable.

### WTSV-C-03 — a type of another workspace (lower id): 404, nothing saved
- **Rules:** `create_template` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no templates (commit point after this line).

**When**
- `svc.create_template(db, tpl_in=WorkOrderTemplateCreate(template_name="Oil change", work_order_type_id=WT0.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Work order type with ID {WT0.id} not found"`.
3. session: clean.
4. nothing written: nothing written.

### WTSV-C-04 — a failing commit is rolled back and re-raised; nothing is saved
- **Rules:** `create_template` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no templates (commit point after this line).

**When**
- `svc.create_template(db, tpl_in=WorkOrderTemplateCreate(template_name="Oil change", work_order_type_id=WT1.id, items=[WorkOrderTemplateItemCreate(item_id=I1.id)]), workspace_id=W1.id, user_id=U1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `work_order_templates` rows of W1: exactly 0.
4. count: `work_order_template_items` rows of W1: exactly 0.

### WTSV-C-05 — a failing re-read after the commit leaves the template saved
- **Rules:** `create_template` R3; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no templates (commit point after this line).

**When**
- `svc.create_template(db, tpl_in=WorkOrderTemplateCreate(template_name="Oil change", work_order_type_id=WT1.id), workspace_id=W1.id, user_id=U1.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: W1 has exactly 1 `work_order_templates` row: `template_name == "Oil change"`, `created_by == U1.id`.

### WTSV-C-06 — pass-through BUG-1228: a deleted type of the workspace is refused
- **Rules:** `create_template` R2 [BUG-1228]
- **Kind:** bug
- **Expect:** xfail BUG-1228
- **Fails today on:** Then 1 (the call raises nothing: the deleted type is accepted)

**Given**
1. WTD = `WorkOrderType(workspace_id=W1.id, name="Old", is_deleted=True, deleted_at=T0, deleted_by=U2.id)` (commit point after this line).

**When**
- `svc.create_template(db, tpl_in=WorkOrderTemplateCreate(template_name="Oil change", work_order_type_id=WTD.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Work order type with ID {WTD.id} not found"`.
3. session: clean.
4. nothing written: nothing written.

### WTSV-C-07 — pass-through BUG-2335: a suspended approver refuses the whole create
- **Rules:** `create_template` R2 [BUG-2335]
- **Kind:** bug
- **Expect:** xfail BUG-2335
- **Fails today on:** Then 1 (the call raises nothing: the suspended member is dropped silently)

**Given**
1. U3 = `make_profile(db)`.
2. MB3 = `WorkspaceMember(workspace_id=W1.id, user_id=U3.id, role="member", status="suspended")` (commit point after this line).

**When**
- `svc.create_template(db, tpl_in=WorkOrderTemplateCreate(template_name="Oil change", work_order_type_id=WT1.id, requires_approval=True, items=[WorkOrderTemplateItemCreate(item_id=I1.id)], approver_user_ids=[U2.id, U3.id]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`, `exc.value.detail == "User is not an active member of this workspace"`.
3. session: clean.
4. nothing written: nothing written.

### WTSV-C-08 — pass-through BUG-2334: the name is stored trimmed
- **Rules:** `create_template` R1 [BUG-2334]
- **Kind:** bug
- **Expect:** xfail BUG-2334
- **Fails today on:** Then 2 (the name is stored as sent, with its spaces)

**Given**
1. W1 has no templates (commit point after this line).

**When**
- `result = svc.create_template(db, tpl_in=WorkOrderTemplateCreate(template_name="  Oil change ", work_order_type_id=WT1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. returns: `result.template_name == "Oil change"`.
3. committed: re-read the row with `id == result.id`: `template_name == "Oil change"`.

### WTSV-C-09 — pass-through BUG-2346: "requires approval" with no approver is refused; nothing saved
- **Rules:** `create_template` R2a [BUG-2346]
- **Kind:** bug
- **Expect:** xfail BUG-2346
- **Fails today on:** Then 1 (the call raises nothing: the template is created)

**Given**
1. W1 has no templates (commit point after this line).
2. extra row X.

**When**
- `svc.create_template(db, tpl_in=WorkOrderTemplateCreate(template_name="Oil change", work_order_type_id=WT1.id, requires_approval=True, items=[WorkOrderTemplateItemCreate(item_id=I1.id)]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`, `exc.value.detail == 'Choose at least one approver, or turn off "requires approval"'`.
3. session: clean.
4. count: x_gone.
5. nothing written: nothing written.

## `WorkOrderTemplateService.update_template`

### WTSV-U-01 — the change is committed and returned re-read; cost rounds half up in the column
- **Rules:** `update_template` R1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template (commit point after this line).

**When**
- `result = svc.update_template(db, tpl_id=T.id, tpl_in=WorkOrderTemplateUpdate(template_name="Belt check", cost=Decimal("0.125")), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `updated_at`, `template_name`, `cost`, `updated_by`.
2. returns: `result.id == T.id`, `result.template_name == "Belt check"`, `result.cost == Decimal("0.13")`.
3. returns: `result.updated_at is not None`, `result.updated_by == U1.id`.
4. committed: re-read T: `template_name == "Belt check"`, `cost == Decimal("0.13")`, `updated_by == U1.id`.

### WTSV-U-02 — another workspace's id (higher): the 404 passes unchanged; pending changes discarded
- **Rules:** `update_template` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.
2. Z = template, but `workspace_id W2.id`, `work_order_type_id WT2.id` (commit point after this line).
3. extra row X.

**When**
- `svc.update_template(db, tpl_id=Z.id, tpl_in=WorkOrderTemplateUpdate(template_name="Belt check"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Work order template with ID {Z.id} not found"`.
3. session: clean.
4. count: x_gone.
5. unchanged: unchanged(Z).
6. unchanged: unchanged(T).

### WTSV-U-03 — pass-through BUG-2335: an approver refusal undoes the fields already written
- **Rules:** `update_template` R2 [BUG-2335]
- **Kind:** bug
- **Expect:** xfail BUG-2335
- **Fails today on:** Then 1 (the call raises nothing: the suspended member is dropped silently)

**Given**
1. U3 = `make_profile(db)`.
2. MB3 = `WorkspaceMember(workspace_id=W1.id, user_id=U3.id, role="member", status="suspended")`.
3. T = template, but `requires_approval True`.
4. approver U2 on T (commit point after this line).

**When**
- `svc.update_template(db, tpl_id=T.id, tpl_in=WorkOrderTemplateUpdate(template_name="Belt check", approver_user_ids=[U2.id, U3.id]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`, `exc.value.detail == "User is not an active member of this workspace"`.
3. session: clean.
4. re-read T: `template_name == "Oil change"`, `updated_by is None`.
5. count: approvers(T) `== {U2.id}`.

### WTSV-U-04 — pass-through BUG-2340: an empty update leaves `updated_by` as it was
- **Rules:** `update_template` R3 [BUG-2340]
- **Kind:** bug
- **Expect:** xfail BUG-2340
- **Fails today on:** Then 2 (`updated_by` is stamped on every call: U1)

**Given**
1. T = template, but `updated_by U2.id`, `updated_at T0` (commit point after this line).

**When**
- `result = svc.update_template(db, tpl_id=T.id, tpl_in=WorkOrderTemplateUpdate(), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == T.id`.
2. committed: re-read T: `updated_by == U2.id`.
3. committed: re-read T: `updated_at == T0`.

### WTSV-U-05 — a new approver list replaces the old one and is committed
- **Rules:** `update_template` R1; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but `requires_approval True`.
2. approver U2 on T (commit point after this line).

**When**
- `result = svc.update_template(db, tpl_id=T.id, tpl_in=WorkOrderTemplateUpdate(approver_user_ids=[U1.id]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == T.id`.
2. committed: approvers(T) `== {U1.id}`.

### WTSV-U-06 — pass-through BUG-2346: turning on "requires approval" with no approver is refused; nothing saved
- **Rules:** `create_template` R2a (update) [BUG-2346]
- **Kind:** bug
- **Expect:** xfail BUG-2346
- **Fails today on:** Then 1 (the call raises nothing: the flag is set)

**Given**
1. T = template (commit point after this line).
2. extra row X.

**When**
- `svc.update_template(db, tpl_id=T.id, tpl_in=WorkOrderTemplateUpdate(requires_approval=True), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`, `exc.value.detail == 'Choose at least one approver, or turn off "requires approval"'`.
3. session: clean.
4. count: x_gone.
5. unchanged: unchanged(T).

## `WorkOrderTemplateService.get_template`

### WTSV-G-01 — an inactive template is returned; the read neither commits nor rolls back
- **Rules:** `get_template` R1, R2; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but inactive (commit point after this line).
2. extra row X.

**When**
- `result = svc.get_template(db, tpl_id=T.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. returns: `result.id == T.id`, `result.is_active is False`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: x_kept.

### WTSV-G-02 — another workspace's id (lower): the 404 passes unchanged, nothing rolled back
- **Rules:** `get_template` R1, R2; TC6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`, `work_order_type_id WT0.id`.
2. T = template (commit point after this line).
3. extra row X.

**When**
- `svc.get_template(db, tpl_id=Z.id, workspace_id=W1.id)`, inside **spies**, inside `with pytest.raises(HTTPException) as exc:`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Work order template with ID {Z.id} not found"`.
3. mock called: `rb.call_count == 0`.
4. count: x_kept.

### WTSV-G-03 — another workspace's id (higher): 404
- **Rules:** `get_template` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template.
2. Z = template, but `workspace_id W2.id`, `work_order_type_id WT2.id` (commit point after this line).

**When**
- `svc.get_template(db, tpl_id=Z.id, workspace_id=W1.id)`, inside `with pytest.raises(HTTPException) as exc:`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Work order template with ID {Z.id} not found"`.

## `WorkOrderTemplateService.list_templates`

### WTSV-L-01 — all five arguments reach the manager
- **Rules:** `list_templates` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. WTB = `WorkOrderType(workspace_id=W1.id, name="Repair")`.
2. A = template, but inactive, `created_at T1`.
3. B = template, but inactive, `template_name "Belt check"`, `created_at T2`.
4. C = template, but `template_name "Grease"`, `created_at T3`.
5. D = template, but inactive, `template_name "Paint"`, `work_order_type_id WTB.id`, `created_at T3`.
6. A0 = template, but inactive, `template_name "Valve"`, `created_at T0` (commit point after this line).

**When**
- `result = svc.list_templates(db, workspace_id=W1.id, is_active=False, work_order_type_id=WT1.id, skip=1, limit=1)`.

**Then**
1. returns: `[t.id for t in result] == [A.id]`.

### WTSV-L-02 — the default lists both states, of the workspace only
- **Rules:** `list_templates` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z0 = template, but `workspace_id W0.id`, `work_order_type_id WT0.id`, `created_at T3`.
2. A = template, but `created_at T1`.
3. B = template, but inactive, `template_name "Belt check"`, `created_at T2`.
4. Z2 = template, but `workspace_id W2.id`, `work_order_type_id WT2.id`, `created_at T3` (commit point after this line).

**When**
- `result = svc.list_templates(db, workspace_id=W1.id)`.

**Then**
1. returns: `{t.id for t in result} == {A.id, B.id}`.
2. returns: `len(result) == 2`.

### WTSV-L-03 — the list neither commits nor rolls back
- **Rules:** `list_templates` R2; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = template (commit point after this line).
2. extra row X.

**When**
- `result = svc.list_templates(db, workspace_id=W1.id)`, inside **spies**.

**Then**
1. returns: `[t.id for t in result] == [A.id]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: x_kept.

### WTSV-L-04 — with no limit, 101 templates give the newest 100
- **Rules:** `list_templates` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 templates E1 … E101, built with `add_all` and one flush: Ek = template, but `template_name` = `f"Oil change {k}"`, `created_at` = `T0 + timedelta(minutes=k)` (`timedelta` from `datetime`) (commit point after this line).
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = svc.list_templates(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `[t.id for t in result] == newest[:100]`.

## `WorkOrderTemplateService.delete_template`

### WTSV-D-01 — an active template is deactivated and committed; None; lines and approvers stay
- **Rules:** `delete_template` R1, Returns; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but `requires_approval True`.
2. L = line on T.
3. approver U2 on T (commit point after this line).

**When**
- `result = svc.delete_template(db, tpl_id=T.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result is None`.
2. committed: re-read T: `is_active is False`, `updated_by == U1.id`.
3. committed: re-read L: the row exists, `quantity == Decimal("2.00")`.
4. committed: approvers(T) `== {U2.id}`.

### WTSV-D-02 — an inactive template: None, nothing new committed
- **Rules:** `delete_template` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but inactive (commit point after this line).

**When**
- `result = svc.delete_template(db, tpl_id=T.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(T).
3. re-read T: `updated_by == U2.id`, `updated_at == T0`.

### WTSV-D-03 — another workspace's id (lower): the 404 passes unchanged after a rollback
- **Rules:** `delete_template` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`, `work_order_type_id WT0.id`.
2. T = template (commit point after this line).
3. extra row X.

**When**
- `svc.delete_template(db, tpl_id=Z.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Work order template with ID {Z.id} not found"`.
3. session: clean.
4. count: x_gone.
5. unchanged: unchanged(Z).

### WTSV-D-04 — a failing commit: rolled back, re-raised, the template stays active
- **Rules:** `delete_template` R2; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template (commit point after this line).

**When**
- `svc.delete_template(db, tpl_id=T.id, workspace_id=W1.id, user_id=U1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read T: `is_active is True`, `updated_by is None`.

## `WorkOrderTemplateService.restore_template`

### WTSV-S-01 — an inactive template is restored, committed and returned re-read
- **Rules:** `restore_template` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but inactive (commit point after this line).

**When**
- `result = svc.restore_template(db, tpl_id=T.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `is_active`, `updated_by`, `updated_at`.
2. returns: `result.id == T.id`, `result.is_active is True`, `result.updated_by == U1.id`.
3. committed: re-read T: `is_active is True`, `updated_by == U1.id`.

### WTSV-S-02 — another workspace's id (higher): 404 unchanged, nothing saved
- **Rules:** `restore_template` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. Z = template, but inactive, `workspace_id W2.id`, `work_order_type_id WT2.id` (commit point after this line).
2. extra row X.

**When**
- `svc.restore_template(db, tpl_id=Z.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Work order template with ID {Z.id} not found"`.
3. session: clean.
4. count: x_gone.
5. unchanged: unchanged(Z).

## `WorkOrderTemplateService.add_item`

### WTSV-A-01 — the new line is committed and returned re-read
- **Rules:** `add_item` R1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template (commit point after this line).

**When**
- `result = svc.add_item(db, tpl_id=T.id, item_in=WorkOrderTemplateItemCreate(item_id=I2.id, quantity=Decimal("3"), action_type="INSTALL"), workspace_id=W1.id)`.

**Then**
1. loaded: `quantity`, `action_type`, `item_id`.
2. returns: `isinstance(result, WorkOrderTemplateItem)`, `result.work_order_template_id == T.id`, `result.quantity == Decimal("3.00")`.
3. committed: the row with `id == result.id` exists: `item_id == I2.id`, `action_type == "INSTALL"`, `workspace_id == W1.id`.

### WTSV-A-02 — REPLACE with no replaced item: the 400 passes unchanged; nothing saved
- **Rules:** `add_item` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template (commit point after this line).
2. extra row X.

**When**
- `svc.add_item(db, tpl_id=T.id, item_in=WorkOrderTemplateItemCreate(item_id=I1.id, action_type="REPLACE"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`, `exc.value.detail == "Select the item being replaced"`.
3. session: clean.
4. count: x_gone.
5. nothing written: nothing written.

### WTSV-A-03 — another workspace's template (lower id): 404 `Work order template not found`
- **Rules:** `add_item` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`, `work_order_type_id WT0.id`.
2. T = template (commit point after this line).

**When**
- `svc.add_item(db, tpl_id=Z.id, item_in=WorkOrderTemplateItemCreate(item_id=I1.id), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Work order template not found"`.
3. session: clean.
4. nothing written: nothing written.

## `WorkOrderTemplateService.update_item`

### WTSV-I-01 — the changed line is committed; quantity rounds half up in the column
- **Rules:** `update_item` R1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.
2. L = line on T (commit point after this line).

**When**
- `result = svc.update_item(db, item_id=L.id, item_in=WorkOrderTemplateItemUpdate(quantity=Decimal("2.125"), notes="Check seal"), workspace_id=W1.id)`.

**Then**
1. loaded: `quantity`, `notes`.
2. returns: `result.id == L.id`, `result.quantity == Decimal("2.13")`, `result.notes == "Check seal"`.
3. committed: re-read L: `quantity == Decimal("2.13")`, `notes == "Check seal"`.

### WTSV-I-02 — a line of another workspace (higher id): the 404 passes unchanged
- **Rules:** `update_item` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.
2. L = line on T.
3. Z = template, but `workspace_id W2.id`, `work_order_type_id WT2.id`.
4. ZL = line on Z, but `workspace_id W2.id` (commit point after this line).
5. extra row X.

**When**
- `svc.update_item(db, item_id=ZL.id, item_in=WorkOrderTemplateItemUpdate(quantity=Decimal("5")), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Template item not found"`.
3. session: clean.
4. count: x_gone.
5. unchanged: unchanged(ZL).

## `WorkOrderTemplateService.remove_item`

### WTSV-R-01 — the delete is committed; the returned line stays readable; the other line stays
- **Rules:** `remove_item` R1, Returns; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.
2. L1 = line on T.
3. L2 = line on T, but `item_id I2.id` (commit point after this line).

**When**
- `result = svc.remove_item(db, item_id=L1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L1.id`, `result.quantity == Decimal("2.00")`.
2. committed: `work_order_template_items` rows with `id == L1.id`: exactly 0.
3. committed: re-read L2: `item_id == I2.id`.

### WTSV-R-02 — a line of another workspace (lower id): 404, nothing deleted
- **Rules:** `remove_item` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`, `work_order_type_id WT0.id`.
2. ZL = line on Z, but `workspace_id W0.id`.
3. T = template (commit point after this line).
4. extra row X.

**When**
- `svc.remove_item(db, item_id=ZL.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Template item not found"`.
3. session: clean.
4. count: x_gone.
5. nothing written: nothing written.

### WTSV-R-03 — a failing commit: rolled back, re-raised, the line is still there
- **Rules:** `remove_item` R2; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.
2. L = line on T (commit point after this line).

**When**
- `svc.remove_item(db, item_id=L.id, workspace_id=W1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `work_order_template_items` rows with `id == L.id`: exactly 1.

## `WorkOrderTemplateService.get_items`

### WTSV-N-01 — the template's lines are returned; the read neither commits nor rolls back
- **Rules:** `get_items` R1, R2; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.
2. A = line on T.
3. B = line on T, but `item_id I2.id` (commit point after this line).
4. extra row X.

**When**
- `result = svc.get_items(db, tpl_id=T.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. returns: `{r.id for r in result} == {A.id, B.id}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: x_kept.

### WTSV-N-02 — another workspace's template gives an empty list
- **Rules:** `get_items` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template.
2. Z = template, but `workspace_id W2.id`, `work_order_type_id WT2.id`.
3. ZL = line on Z, but `workspace_id W2.id` (commit point after this line).

**When**
- `result = svc.get_items(db, tpl_id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

## `WorkOrderTemplateService.get_approvers`

### WTSV-P-01 — the template's approvers are returned; the read neither commits nor rolls back
- **Rules:** `get_approvers` R1, R2; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but `requires_approval True`.
2. approver U2 on T.
3. approver U1 on T (commit point after this line).
4. extra row X.

**When**
- `result = svc.get_approvers(db, tpl_id=T.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. returns: `{a.user_id for a in result} == {U1.id, U2.id}`.
2. returns: `len(result) == 2`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. count: x_kept.

### WTSV-P-02 — another workspace's template gives an empty list
- **Rules:** `get_approvers` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`, `work_order_type_id WT0.id`, `requires_approval True`.
2. `db.add(WorkOrderTemplateApprover(workspace_id=W0.id, work_order_template_id=Z.id, user_id=U2.id))`, then `db.flush()`.
3. T = template (commit point after this line).

**When**
- `result = svc.get_approvers(db, tpl_id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

## `WorkOrderTemplateService.generate_drafts`

> Only GD-08 and GD-09 make a section run over a recurring template that is not due (BUG-2345, OQ-19). No card runs after a template's due date (OQ-20, intended; the manager's cards) or uses `requires_approval: true` with no approver.

### WTSV-GD-01 — a due template's draft and its moved date are committed together; the draft returned re-read
- **Rules:** `generate_drafts` R1, R2; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. plant.
2. T = template, but recurring (commit point after this line).

**When**
- `result = svc.generate_drafts(db, body=GenerateWorkOrderDraftsRequest(target_date=D16), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `planned_date`, `work_order_template_id`, `machine_id`, `created_by` (on `result[0]`).
2. returns: `len(result) == 1`.
3. returns: `result[0].work_order_template_id == T.id`, `result[0].planned_date == D16`, `result[0].machine_id == M1.id`.
4. returns: `result[0].workspace_id == W1.id`, `result[0].created_by == U1.id`.
5. committed: drafts(T) `== 1`.
6. committed: re-read T: `next_generation_date == D23`.

### WTSV-GD-02 — nothing due: an empty list, nothing new committed
- **Rules:** `generate_drafts` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. plant.
2. T = template, but recurring, `next_generation_date D17` (commit point after this line).

**When**
- `result = svc.generate_drafts(db, body=GenerateWorkOrderDraftsRequest(target_date=D16), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result == []`.
2. unchanged: unchanged(T).
3. nothing written: nothing written.

### WTSV-GD-03 — an exception from the manager rolls back the run's date change and reaches the caller as the same object
- **Rules:** `generate_drafts` R3; TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. plant.
2. T = template, but recurring (commit point after this line).
3. extra row X.
4. `E = HTTPException(status_code=400, detail="Template is inactive")`; `def boom(*a, **k): T.next_generation_date = D30; db.flush(); raise E`.

**When**
- `svc.generate_drafts(db, body=GenerateWorkOrderDraftsRequest(target_date=D16), workspace_id=W1.id, user_id=U1.id)`, inside `with patch.object(svc.manager, "generate_drafts", side_effect=boom):`, inside `with pytest.raises(HTTPException) as exc:`.

**Then**
1. raises: `exc.value is E`.
2. session: clean.
3. count: x_gone.
4. re-read T: `next_generation_date == D16`.
5. nothing written: nothing written.

### WTSV-GD-10 — any exception from the manager, not only an HTTPException, rolls the run back
- **Rules:** `generate_drafts` R3; TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. plant.
2. T = template, but recurring (commit point after this line).
3. extra row X.
4. `E = RuntimeError("boom")`; `def boom(*a, **k): T.next_generation_date = D30; db.flush(); raise E`.

**When**
- `svc.generate_drafts(db, body=GenerateWorkOrderDraftsRequest(target_date=D16), workspace_id=W1.id, user_id=U1.id)`, inside `with patch.object(svc.manager, "generate_drafts", side_effect=boom):`, inside `with pytest.raises(RuntimeError) as exc:`.

**Then**
1. raises: `exc.value is E`.
2. session: clean.
3. count: x_gone.
4. re-read T: `next_generation_date == D16`.
5. nothing written: nothing written.

### WTSV-GD-04 — pass-through BUG-2344: one failing template no longer undoes the other's draft
- **Rules:** `generate_drafts` R3 [BUG-2344]
- **Kind:** bug
- **Expect:** xfail BUG-2344
- **Author:** claude
- **Fails today on:** Then 1 (the call raises HTTPException: the manager lets the failure out and the service rolls back the whole run)

**Given**
1. plant.
2. M2 = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Press 2")`.
3. T1 = template, but recurring.
4. T2 = template, but recurring, `template_name "Belt check"`, `default_machine_id M2.id` (commit point after this line).
5. `real = work_order_manager.create_work_order_from_template`; `def flaky(*a, **k):` raise `HTTPException(status_code=400, detail="boom")` when the `template_id` argument (keyword, else second positional) equals `T2.id`, else `return real(*a, **k)`.

**When**
- `result = svc.generate_drafts(db, body=GenerateWorkOrderDraftsRequest(target_date=D16), workspace_id=W1.id, user_id=U1.id)`, inside `with patch.object(work_order_manager, "create_work_order_from_template", side_effect=flaky):`.

**Then**
1. returns: `[w.work_order_template_id for w in result] == [T1.id]`.
2. committed: drafts(T1) `== 1`.
3. committed: drafts(T2) `== 0`.
4. committed: re-read T1: `next_generation_date == D23`.
5. committed: re-read T2: `next_generation_date == D16`.

### WTSV-GD-05 — a failing re-read of a draft reaches the caller and the run stays committed
- **Rules:** `generate_drafts` R4; TC5
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. plant.
2. T = template, but recurring (commit point after this line).

**When**
- `svc.generate_drafts(db, body=GenerateWorkOrderDraftsRequest(target_date=D16), workspace_id=W1.id, user_id=U1.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: drafts(T) `== 1`.
3. committed: re-read T: `next_generation_date == D23`.

### WTSV-GD-06 — `factory_section_id` reaches the manager: a non-recurring template of the section gets a draft
- **Rules:** `generate_drafts` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. plant.
2. S2 = `FactorySection(workspace_id=W1.id, factory_id=F1.id, name="Paint")`.
3. N = template, but `default_factory_section_id S1.id`, `default_machine_id M1.id`.
4. N2 = template, but `template_name "Belt check"`, `default_factory_section_id S2.id`, `default_machine_id M1.id` (commit point after this line).

**When**
- `result = svc.generate_drafts(db, body=GenerateWorkOrderDraftsRequest(target_date=D16, factory_section_id=S1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `[w.work_order_template_id for w in result] == [N.id]`.
2. returns: `result[0].planned_date == D16`, `result[0].machine_id == M1.id`.
3. committed: drafts(N) `== 1`.
4. committed: drafts(N2) `== 0`.
5. committed: re-read N: `next_generation_date is None`.

### WTSV-GD-07 — `factory_id` reaches the manager: a due template of another factory's section gets nothing
- **Rules:** `generate_drafts` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. plant.
2. F2 = `Factory(workspace_id=W1.id, name="Annex", abbreviation="AN")`.
3. T = template, but recurring, `default_factory_section_id S1.id` (commit point after this line).

**When**
- `result = svc.generate_drafts(db, body=GenerateWorkOrderDraftsRequest(target_date=D16, factory_id=F2.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result == []`.
2. unchanged: unchanged(T).
3. nothing written: nothing written.

### WTSV-GD-08 — pass-through BUG-2345: a section run commits no draft for a recurring template that is not due
- **Rules:** `generate_drafts` R1a [BUG-2345]
- **Kind:** bug
- **Expect:** xfail BUG-2345
- **Fails today on:** Then 1 (a draft is made for the not-due template and returned)

**Given**
1. plant.
2. T = template, but recurring, `next_generation_date D23`, `default_factory_section_id S1.id` (commit point after this line).

**When**
- `result = svc.generate_drafts(db, body=GenerateWorkOrderDraftsRequest(target_date=D16, factory_section_id=S1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result == []`.
2. committed: drafts(T) `== 0`.
3. committed: re-read T: `next_generation_date == D23`.

### WTSV-GD-09 — a section run leaves a not-due recurring template's next date where it was
- **Rules:** `generate_drafts` R1a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. plant.
2. T = template, but recurring, `next_generation_date D23`, `default_factory_section_id S1.id` (commit point after this line).

**When**
- `result = svc.generate_drafts(db, body=GenerateWorkOrderDraftsRequest(target_date=D16, factory_section_id=S1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. committed: re-read T: `next_generation_date == D23`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| BUG-2345, BUG-2346 (OQ-19, OQ-21 answered), OQ-20 (intended) | `work_order_template_manager.cases.md` | Full shapes; here one pass-through card each (C-09, U-06, GD-08). |
| BUG-1015, BUG-2336 … BUG-2339, BUG-2341 … BUG-2343, BUG-360 … BUG-363 | `WorkOrderTemplateManager` / recurrence util | The refusals; here they pass like any exception (TC3 cards). |
| `get_approvers` order (BUG-2331), list order (BUG-2330) | `tests/unit/dao/work_order_template.spec.md` | Sort keys; compared as sets here. |
| HR-7 — `1 <= limit <= 1000`, `skip >= 0`; `is_active` default `True` | `GET /work-order-templates/` | Endpoint rule. |
| `user_name` on `GET …/approvers/`; 204 on the deletes | endpoints | Integration only. |
| `generate_drafts_for_anchored_range` | `WorkOrderManager` (no spec yet) | Not called by this service. |
| `__init__`, singleton | none (no logic) | — |

## Spec gaps
None open. Revision 1's gaps were closed by the spec's Gap log (2026-11-07):
- G1: the model modules are spec Facts; Conventions cite them.
- G2: the draft work order columns (`machine_id`, `planned_date`, `work_order_template_id`, `created_by`, `workspace_id`) are spec Facts; GD-01 and GD-06 unchanged.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_template` | R1, Returns | WTSV-C-01 |
| `create_template` | R2 | WTSV-C-02, WTSV-C-03 |
| `create_template` | R2 [BUG-1228] | WTSV-C-06 |
| `create_template` | R2 [BUG-2335] | WTSV-C-07 |
| `create_template` | [BUG-2334] (Review) | WTSV-C-08 |
| `create_template` | R2a [BUG-2346] | WTSV-C-09, WTSV-U-06 |
| `create_template` | R3 | WTSV-C-04, WTSV-C-05 |
| `update_template` | R1 | WTSV-U-01, WTSV-U-05 |
| `update_template` | R2 | WTSV-U-02 |
| `update_template` | R2 [BUG-2335] | WTSV-U-03 |
| `update_template` | R3 [BUG-2340] | WTSV-U-04 |
| `update_template` | R4 (TC4, TC5) | once on create: WTSV-C-04, WTSV-C-05 |
| `get_template` | R1 | WTSV-G-01, WTSV-G-02, WTSV-G-03 |
| `get_template` | R2 | WTSV-G-01, WTSV-G-02 |
| `list_templates` | R1 | WTSV-L-01, WTSV-L-02, WTSV-L-04 |
| `list_templates` | R2 | WTSV-L-03 |
| `delete_template` | R1, Returns | WTSV-D-01, WTSV-D-02 |
| `delete_template` | R2 | WTSV-D-03, WTSV-D-04 |
| `restore_template` | R1, Returns | WTSV-S-01 |
| `restore_template` | R2 | WTSV-S-02 (TC4, TC5 once on create) |
| `add_item` | R1 | WTSV-A-01 |
| `add_item` | R2 | WTSV-A-02, WTSV-A-03 |
| `update_item` | R1 | WTSV-I-01 |
| `update_item` | R2 | WTSV-I-02 |
| `remove_item` | R1, Returns | WTSV-R-01 |
| `remove_item` | R2 | WTSV-R-02, WTSV-R-03 |
| `get_items` | R1 | WTSV-N-01, WTSV-N-02 |
| `get_items` | R2 | WTSV-N-01 |
| `get_approvers` | R1 | WTSV-P-01, WTSV-P-02 |
| `get_approvers` | R2 | WTSV-P-01 |
| `generate_drafts` | R1 | WTSV-GD-01, WTSV-GD-06, WTSV-GD-07 |
| `generate_drafts` | R1a [BUG-2345] | WTSV-GD-08 |
| `generate_drafts` | R1a (date unchanged) | WTSV-GD-09 |
| `generate_drafts` | R2 | WTSV-GD-01, WTSV-GD-02 |
| `generate_drafts` | R3 | WTSV-GD-03, WTSV-GD-10 |
| `generate_drafts` | R3 [BUG-2344] | WTSV-GD-04 |
| `generate_drafts` | R4 | WTSV-GD-05 |
| TC1 | per write | C-01, U-01, D-01, S-01, A-01, I-01, R-01, GD-01 |
| TC2 | once | WTSV-C-01 (also U-01, S-01, A-01, I-01, GD-01) |
| TC3 | per write | C-02, U-02, D-03, S-02, A-02, I-02, R-02, GD-03 |
| TC4 | create; non-refreshing writes | WTSV-C-04, WTSV-D-04, WTSV-R-03 |
| TC5 | create; generate | WTSV-C-05, WTSV-GD-05 |
| TC6 | per read | WTSV-G-01, WTSV-G-02, WTSV-L-03, WTSV-N-01, WTSV-P-01 |
