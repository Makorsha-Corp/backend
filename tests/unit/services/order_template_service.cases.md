# Test cases — `app/services/order_template_service.py`

> **Spec:** `tests/unit/services/order_template_service.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-06; revised 2026-11-07, nothing open). OQ-22 was answered by the owner (BUG-2347); it reaches this service as a pass-through refusal (R2a).
> **Revision:** 2 (2026-11-07) — spec revision 2026-11-07 and its Gap log. G1 (`create_template` R3a): OTSV-C-04 now sends a priced line and re-selects it after the failed re-read (`line_number`, `line_subtotal`). G2: the line model's module is a spec Fact (Conventions unchanged). New: OTSV-C-06 (R2a, pass-through BUG-2347, strict xfail). No card retired; Spec gaps closed.
> **Revision:** 3 (2026-11-09) — `order_template_service.verify.md` findings 1–3. Finding 1: OTSV-L-02 gains a third matching row A0, so `limit=1` cuts a row and a dropped `limit` fails. Finding 3 (spec R1a, the service's defaults): new OTSV-L-04 (101 templates, no `limit` → 100). Finding 2: new OTSV-GI-03, strict xfail BUG-2366 (another workspace's template → 404), which pins the caller's workspace on `get_items` once the bug is fixed. No card retired.
> **Counts:** 33 cases · 30 expected-to-pass · 3 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `create_template` 6 (1 bug) · `update_template` 3 · `get_template` 3 · `list_templates` 4 · `delete_template` 4 · `add_item` 3 · `update_item` 4 (1 bug) · `remove_item` 3 · `get_items` 3 (1 bug).
- **Depth:** lighter (skill step 1a, as the owner set for services): a transaction wrapper. TC1 and TC3 once per write, TC2, TC4, TC5 once on `create_template`, TC4 also on the two writes that do not re-read (`delete_template`, `remove_item`), TC6 once per read. Money is the manager's; one card per money pass-through: the HR-15 column rounding (0.50 × 0.25 = 0.125 → 0.13, where half-to-even would give 0.12; inputs keep 2 decimals so BUG-2363's fix does not refuse them) in OTSV-C-01 and OTSV-I-01, and BUG-1226.
- **Expected-to-fail:** BUG-1226 1 (OTSV-I-03, strict). Its price part (0.00 stored) holds today and has its own pass card, OTSV-I-04. Pass-through BUG-2366 1 (OTSV-GI-03, strict): no passing card on today's `[]` for another workspace's template (the buggy path). Pass-through BUG-2347 1 (OTSV-C-06, strict): a non-owner's template that skips approval gets the manager's 403 and nothing is saved; the owner-allowed side is the manager's (`order_template_manager.cases.md`, Q22 section).
- **Notable design choices:**
  - Same commit point, uncommitted extra row X and spies as `work_order_type_service.cases.md`; a refusal runs with no savepoint, so a write the rollback fails to undo stays visible, and every refusal checks the session (`db.new`, `db.dirty`, `db.deleted` empty) before any re-read.
  - The `create_template` refusal (TC3) uses an unknown `user_id` (`created_by` FK, `IntegrityError` at flush), which stays the same after every bug fix. The spec's own example (a 256-character name, `DataError`) becomes a 422 at the schema with BUG-2365, so no card uses it.
  - Another workspace's id is tried at a lower id (W0's row, built first) on `get_template`, `delete_template`, `update_item` and at a higher id (W2's row) on `get_template`, `update_template`, `add_item`, `remove_item`.
  - The service has no permission check of its own; the manager's BUG-2347 role check is passed through once (C-06). Every other card keeps the defaults `requires_approval=True`, `auto_approve=False` and sends neither flag to `update_template`, so no other card needs a role.
- **Needs a decision:** None. Spec gaps 1–2 closed by the spec's Gap log (G1, G2).

## Conventions for this module

**IDs.** `OTSV` = `app/services/order_template_service.py`. `C` create_template · `U` update_template · `G` get_template · `L` list_templates · `D` delete_template · `A` add_item · `I` update_item · `R` remove_item · `GI` get_items.

**Actors and fixed values.**
- `svc` = the singleton `order_template_service` (`from app.services.order_template_service import OrderTemplateService, order_template_service`). `db` = the test's real session, always the first argument; every other argument by keyword. `result` = what the When call returns.
- `OrderTemplate` (`app.models.order_template`), `OrderTemplateItem` (`app.models.order_template_item`), `OrderTemplateCreate`, `OrderTemplateUpdate`, `OrderTemplateItemCreate`, `OrderTemplateItemUpdate` (`app.schemas.order_template`), `HTTPException` (`fastapi`), `IntegrityError` (`sqlalchemy.exc`), `inspect`, `text`, `select`, `func` (`sqlalchemy`), `patch` (`unittest.mock`), `Decimal` (`decimal`), `datetime` (`datetime`).
- **Standing rows** (every test, in this order, no Given line): W0, W1, W2 = `make_workspace(db)` three times, so `W0.id < W1.id < W2.id`; U1, U2 = `make_profile(db)` twice. U1 is the acting user; U2 made the Given rows. No template exists unless the Given builds it.
- MISSING = `999999999`. T0, T1, T2, T3 = `datetime(2026, 3, 4, 9, 0, 0)` … `datetime(2026, 3, 4, 12, 0, 0)` (naive).

**Externals.** None is mocked. `created_at`, `updated_at` come from the model's clock and are checked only `is not None` or "loaded".

**Given rows.** Built directly (never through `svc`), flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A Given line written as code is a step to run exactly as written.
- **template** = `OrderTemplate(workspace_id=W1.id, template_name="Rent", requires_approval=True, auto_approve=False, created_by=U2.id, created_at=T0)`; `is_active` left to `True`; `updated_by`, `updated_at` NULL. After "but" the card lists every column that differs.
- **inactive** (after "but") = `is_active False`, `updated_by U2.id`, `updated_at T0` (what a real delete leaves).
- **line n on T** = `OrderTemplateItem(workspace_id=W1.id, order_template_id=T.id, line_number=n, description="Line", quantity=Decimal("2.00"), unit_price=Decimal("10.00"), line_subtotal=Decimal("20.00"))`. After "but" the card lists every column that differs.
- **commit point** = after the last Given line the test runs `db.commit()` (a savepoint release under the `db` fixture). Snapshots for `unchanged` and `nothing written` are taken there.
- **extra row X** (only where a card lists it; after the commit point) = `X = OrderTemplate(workspace_id=W2.id, template_name="Extra", requires_approval=True, auto_approve=False, created_at=T0)`, `db.add(X)`, `db.flush()`; not committed. `X_ID = X.id`.

**Named checks.**
- **re-read X** = `db.expire_all()`, then `db.get(<class of X>, X.id)`; database values. **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **nothing written** = the numbers of `order_templates` rows and of `order_template_items` rows (all workspaces) equal their values at the commit point.
- **x_gone** = `db.scalar(select(func.count()).select_from(OrderTemplate).where(OrderTemplate.id == X_ID)) == 0`. **x_kept** = the same count `== 1`.
- `loaded:` lines run on the returned object first, before any other Then line: each column named is not in `inspect(result).unloaded` (column attributes only; relationships are never checked).
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads or counts with a fresh query.
- `session:` lines check `db` directly after the call, before anything re-reads: "clean" = `not db.new`, `not db.dirty`, `not db.deleted` (three asserts); "usable" = `db.execute(text("SELECT 1")).scalar() == 1`.
- `raises: HTTPException`, `raises: IntegrityError` = plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint (the service rolls back itself). Further `raises:` lines assert on `exc.value` after the block.
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "refresh", side_effect=RuntimeError("boom")):` around the When. Checks after the block run with the patches gone.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.

**xfail cards.** Write the call and checks as shown. All strict: `pytest.mark.xfail(strict=True, reason="BUG-NNN")`.

**Race simulations.** None in this module.

## `OrderTemplateService.create_template`

### OTSV-C-01 — a template with its lines is committed and returned re-read; the column rounds half up
- **Rules:** `create_template` R1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no templates (commit point after this line).

**When**
- `result = svc.create_template(db, tpl_in=OrderTemplateCreate(template_name="Rent", items=[OrderTemplateItemCreate(description="Desk", quantity=Decimal("1.50"), unit_price=Decimal("0.25")), OrderTemplateItemCreate(description="Fee", quantity=Decimal("0.50"), unit_price=Decimal("0.25"))]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `created_at`, `template_name`, `workspace_id`, `created_by`, `is_active`.
2. returns: `isinstance(result, OrderTemplate)`.
3. returns: `result.id is not None`, `result.created_at is not None`.
4. returns: `result.template_name == "Rent"`, `result.workspace_id == W1.id`, `result.created_by == U1.id`, `result.is_active is True`.
5. committed: the `order_templates` row with `id == result.id` exists: `template_name == "Rent"`, `created_by == U1.id`.
6. committed: the `order_template_items` rows with `order_template_id == result.id`, ordered by `line_number`, are exactly 2.
7. committed: line 1 has `description == "Desk"`, `quantity == Decimal("1.50")`, `unit_price == Decimal("0.25")`, `line_subtotal == Decimal("0.38")`.
8. committed: line 2 has `description == "Fee"`, `quantity == Decimal("0.50")`, `unit_price == Decimal("0.25")`, `line_subtotal == Decimal("0.13")`.

### OTSV-C-02 — a database error rolls back, reaches the caller unchanged, and discards other pending changes
- **Rules:** `create_template` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no templates (commit point after this line).
2. extra row X.

**When**
- `svc.create_template(db, tpl_in=OrderTemplateCreate(template_name="Rent", items=[OrderTemplateItemCreate(description="Desk")]), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. session: clean.
3. count: x_gone.
4. nothing written: nothing written.
5. count: `order_templates` rows of W1 with `template_name == "Rent"`: exactly 0.
6. session: usable.

### OTSV-C-03 — a failing commit is rolled back and re-raised; nothing is saved
- **Rules:** `create_template` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no templates (commit point after this line).

**When**
- `svc.create_template(db, tpl_in=OrderTemplateCreate(template_name="Rent", items=[OrderTemplateItemCreate(description="Desk")]), workspace_id=W1.id, user_id=U1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `order_templates` rows of W1: exactly 0.
4. count: `order_template_items` rows of W1: exactly 0.

### OTSV-C-04 — a failing re-read after the commit leaves the template and its line saved
- **Rules:** `create_template` R3, R3a; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no templates (commit point after this line).

**When**
- `svc.create_template(db, tpl_in=OrderTemplateCreate(template_name="Rent", items=[OrderTemplateItemCreate(description="Desk", quantity=Decimal("2"), unit_price=Decimal("3.00"))]), workspace_id=W1.id, user_id=U1.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: W1 has exactly 1 `order_templates` row, `template_name == "Rent"`, `created_by == U1.id`.
3. committed: W1 has exactly 1 `order_template_items` row, `description == "Desk"`, `order_template_id` == the id of that template.
4. committed: that line has `line_number == 1`, `line_subtotal == Decimal("6.00")`.

### OTSV-C-05 — a template with no lines is committed with none
- **Rules:** `create_template` R1; TC1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no templates (commit point after this line).

**When**
- `result = svc.create_template(db, tpl_in=OrderTemplateCreate(template_name="Rent", items=[]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: the `order_templates` row with `id == result.id` exists.
3. committed: `order_template_items` rows with `order_template_id == result.id`: exactly 0.

### OTSV-C-06 — pass-through BUG-2347: a non-owner's template that skips approval is refused with 403; nothing saved
- **Rules:** `create_template` R2a [BUG-2347]
- **Kind:** bug
- **Expect:** xfail BUG-2347
- **Fails today on:** Then 1 (the call raises nothing: the flag is stored for anyone)

**Given**
1. `W1.owner_user_id = U2.id`, then `db.flush()`.
2. `db.add(WorkspaceMember(workspace_id=W1.id, user_id=U1.id, role="member", status="active"))`, then `db.flush()` (`WorkspaceMember` from `app.models.workspace_member`) (commit point after this line).
3. extra row X.

**When**
- `svc.create_template(db, tpl_in=OrderTemplateCreate(template_name="Rent", requires_approval=False, items=[OrderTemplateItemCreate(description="Desk")]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`, `exc.value.detail == "Only the workspace owner can skip approval on a template"`.
3. session: clean.
4. count: x_gone.
5. nothing written: nothing written.

## `OrderTemplateService.update_template`

### OTSV-U-01 — the change is committed and the template returned re-read
- **Rules:** `update_template` R1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template (commit point after this line).

**When**
- `result = svc.update_template(db, tpl_id=T.id, tpl_in=OrderTemplateUpdate(template_name="Lease"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `updated_at`, `template_name`, `updated_by`.
2. returns: `result.id == T.id`, `result.template_name == "Lease"`, `result.updated_by == U1.id`.
3. returns: `result.updated_at is not None`.
4. committed: re-read T: `template_name == "Lease"`, `updated_by == U1.id`.

### OTSV-U-02 — another workspace's id (higher): the manager's 404 passes unchanged, pending changes discarded
- **Rules:** `update_template` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.
2. Z = template, but `workspace_id W2.id` (commit point after this line).
3. extra row X.

**When**
- `svc.update_template(db, tpl_id=Z.id, tpl_in=OrderTemplateUpdate(template_name="Lease"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Order template with ID {Z.id} not found"`.
4. session: clean.
5. count: x_gone.
6. unchanged: unchanged(Z).
7. unchanged: unchanged(T).
8. nothing written: nothing written.

### OTSV-U-03 — an unknown id: 404, nothing saved
- **Rules:** `update_template` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template (commit point after this line).

**When**
- `svc.update_template(db, tpl_id=MISSING, tpl_in=OrderTemplateUpdate(template_name="Lease"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Order template with ID 999999999 not found"`.
3. session: clean.
4. unchanged: unchanged(T).

## `OrderTemplateService.get_template`

### OTSV-G-01 — an inactive template is returned; the read neither commits nor rolls back
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

### OTSV-G-02 — another workspace's id (lower): the 404 passes unchanged and nothing is rolled back
- **Rules:** `get_template` R1, R2; TC6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`.
2. T = template (commit point after this line).
3. extra row X.

**When**
- `svc.get_template(db, tpl_id=Z.id, workspace_id=W1.id)`, inside **spies**, inside `with pytest.raises(HTTPException) as exc:`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Order template with ID {Z.id} not found"`.
3. mock called: `rb.call_count == 0`.
4. mock called: `cm.call_count == 0`.
5. count: x_kept.

### OTSV-G-03 — another workspace's id (higher): 404
- **Rules:** `get_template` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template.
2. Z = template, but `workspace_id W2.id` (commit point after this line).

**When**
- `svc.get_template(db, tpl_id=Z.id, workspace_id=W1.id)`, inside `with pytest.raises(HTTPException) as exc:`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Order template with ID {Z.id} not found"`.

## `OrderTemplateService.list_templates`

### OTSV-L-01 — the default lists active and inactive templates of the workspace only
- **Rules:** `list_templates` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z0 = template, but `workspace_id W0.id`, `created_at T3`.
2. A = template, but `created_at T1`.
3. B = template, but inactive, `template_name "Lease"`, `created_at T2`.
4. Z2 = template, but `workspace_id W2.id`, `created_at T3` (commit point after this line).

**When**
- `result = svc.list_templates(db, workspace_id=W1.id)`.

**Then**
1. returns: `{t.id for t in result} == {A.id, B.id}`.
2. returns: `len(result) == 2`.

### OTSV-L-02 — all five arguments reach the manager
- **Rules:** `list_templates` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = template, but inactive, `expense_category "factory"`, `created_at T1`.
2. B = template, but inactive, `template_name "Lease"`, `expense_category "factory"`, `created_at T2`.
3. C = template, but `template_name "Power"`, `expense_category "factory"`, `created_at T3`.
4. D = template, but inactive, `template_name "Misc"`, `expense_category "department"`, `created_at T3`.
5. A0 = template, but inactive, `template_name "Water"`, `expense_category "factory"`, `created_at T0` (commit point after this line).

**When**
- `result = svc.list_templates(db, workspace_id=W1.id, is_active=False, expense_category="factory", skip=1, limit=1)`.

**Then**
1. returns: `[t.id for t in result] == [A.id]`.

### OTSV-L-03 — the list neither commits nor rolls back
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

### OTSV-L-04 — with no limit, 101 templates give the newest 100
- **Rules:** `list_templates` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 templates E1 … E101, built with `add_all` and one flush: Ek = template, but `template_name` = `f"Rent {k}"`, `created_at` = `T0 + timedelta(minutes=k)` (`timedelta` from `datetime`) (commit point after this line).
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = svc.list_templates(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `[t.id for t in result] == newest[:100]`.

## `OrderTemplateService.delete_template`

### OTSV-D-01 — an active template is deactivated and committed; None is returned
- **Rules:** `delete_template` R1, Returns; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T (commit point after this line).

**When**
- `result = svc.delete_template(db, tpl_id=T.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result is None`.
2. committed: re-read T: `is_active is False`, `updated_by == U1.id`.
3. committed: re-read L: the row exists, `line_number == 1`.

### OTSV-D-02 — an already inactive template: None, nothing new committed
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

### OTSV-D-03 — another workspace's id (lower): the 404 passes unchanged after a rollback
- **Rules:** `delete_template` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`.
2. T = template (commit point after this line).
3. extra row X.

**When**
- `svc.delete_template(db, tpl_id=Z.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Order template with ID {Z.id} not found"`.
3. session: clean.
4. count: x_gone.
5. unchanged: unchanged(Z).
6. unchanged: unchanged(T).

### OTSV-D-04 — a failing commit: rolled back, re-raised, the template stays active
- **Rules:** `delete_template` R3; TC4
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

## `OrderTemplateService.add_item`

### OTSV-A-01 — the new line is committed and returned re-read
- **Rules:** `add_item` R1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.
2. L1 = line 1 on T.
3. L2 = line 2 on T (commit point after this line).

**When**
- `result = svc.add_item(db, tpl_id=T.id, item_in=OrderTemplateItemCreate(description="Water", quantity=Decimal("4"), unit_price=Decimal("2.50")), workspace_id=W1.id)`.

**Then**
1. loaded: `line_number`, `line_subtotal`, `quantity`, `unit_price`.
2. returns: `isinstance(result, OrderTemplateItem)`, `result.order_template_id == T.id`.
3. returns: `result.line_number == 3`, `result.line_subtotal == Decimal("10.00")`.
4. committed: the `order_template_items` row with `id == result.id` exists: `description == "Water"`, `line_number == 3`, `line_subtotal == Decimal("10.00")`, `workspace_id == W1.id`.

### OTSV-A-02 — another workspace's template (higher id): the 404 passes unchanged; nothing saved
- **Rules:** `add_item` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.
2. Z = template, but `workspace_id W2.id` (commit point after this line).
3. extra row X.

**When**
- `svc.add_item(db, tpl_id=Z.id, item_in=OrderTemplateItemCreate(description="Water"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Order template not found"`.
3. session: clean.
4. count: x_gone.
5. nothing written: nothing written.

### OTSV-A-03 — a line on an inactive template is committed
- **Rules:** `add_item` R1; TC1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but inactive (commit point after this line).

**When**
- `result = svc.add_item(db, tpl_id=T.id, item_in=OrderTemplateItemCreate(description="Water"), workspace_id=W1.id)`.

**Then**
1. returns: `result.line_number == 1`.
2. committed: the `order_template_items` row with `id == result.id` exists, `order_template_id == T.id`.

## `OrderTemplateService.update_item`

### OTSV-I-01 — the changed line is committed with the manager's subtotal, rounded half up by the column
- **Rules:** `update_item` R1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T (commit point after this line).

**When**
- `result = svc.update_item(db, item_id=L.id, item_in=OrderTemplateItemUpdate(quantity=Decimal("0.50"), unit_price=Decimal("0.25")), workspace_id=W1.id)`.

**Then**
1. loaded: `line_subtotal`, `quantity`, `unit_price`.
2. returns: `result.id == L.id`, `result.line_subtotal == Decimal("0.13")`.
3. committed: re-read L: `quantity == Decimal("0.50")`, `unit_price == Decimal("0.25")`, `line_subtotal == Decimal("0.13")`.

### OTSV-I-02 — a line of another workspace (lower id): the 404 passes unchanged
- **Rules:** `update_item` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`.
2. ZL = line 1 on Z, but `workspace_id W0.id`.
3. T = template.
4. L = line 1 on T (commit point after this line).
5. extra row X.

**When**
- `svc.update_item(db, item_id=ZL.id, item_in=OrderTemplateItemUpdate(quantity=Decimal("5")), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Template item not found"`.
3. session: clean.
4. count: x_gone.
5. unchanged: unchanged(ZL).
6. unchanged: unchanged(L).

### OTSV-I-03 — pass-through BUG-1226: a price of 0 gives a subtotal of 0
- **Rules:** `update_item` R3 [BUG-1226]
- **Kind:** bug
- **Expect:** xfail BUG-1226
- **Fails today on:** Then 3 (the stored price 10.00 is used for the subtotal: 20.00)

**Given**
1. T = template.
2. L = line 1 on T (commit point after this line).

**When**
- `result = svc.update_item(db, item_id=L.id, item_in=OrderTemplateItemUpdate(unit_price=Decimal("0")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. returns: `result.unit_price == Decimal("0.00")`.
3. returns: `result.line_subtotal == Decimal("0.00")`.
4. committed: re-read L: `line_subtotal == Decimal("0.00")`.

### OTSV-I-04 — a price of 0 is stored and committed
- **Rules:** `update_item` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T (commit point after this line).

**When**
- `result = svc.update_item(db, item_id=L.id, item_in=OrderTemplateItemUpdate(unit_price=Decimal("0")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`, `result.unit_price == Decimal("0.00")`.
2. committed: re-read L: `unit_price == Decimal("0.00")`, `quantity == Decimal("2.00")`.

## `OrderTemplateService.remove_item`

### OTSV-R-01 — the delete is committed; the returned line stays readable; the other line keeps its number
- **Rules:** `remove_item` R1, Returns; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.
2. L1 = line 1 on T.
3. L2 = line 2 on T, but `description "Second"` (commit point after this line).

**When**
- `result = svc.remove_item(db, item_id=L1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L1.id`, `result.quantity == Decimal("2.00")`, `result.description == "Line"`.
2. committed: `order_template_items` rows with `id == L1.id`: exactly 0.
3. committed: re-read L2: `line_number == 2`, `description == "Second"`.

### OTSV-R-02 — a line of another workspace (higher id): the 404 passes unchanged, nothing deleted
- **Rules:** `remove_item` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T.
3. Z = template, but `workspace_id W2.id`.
4. ZL = line 1 on Z, but `workspace_id W2.id` (commit point after this line).
5. extra row X.

**When**
- `svc.remove_item(db, item_id=ZL.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Template item not found"`.
3. session: clean.
4. count: x_gone.
5. nothing written: nothing written.
6. unchanged: unchanged(ZL).

### OTSV-R-03 — a failing commit: rolled back, re-raised, the line is still there
- **Rules:** `remove_item` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T (commit point after this line).

**When**
- `svc.remove_item(db, item_id=L.id, workspace_id=W1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `order_template_items` rows with `id == L.id`: exactly 1.

## `OrderTemplateService.get_items`

### OTSV-GI-01 — the lines of an inactive template come back in line order; the read neither commits nor rolls back
- **Rules:** `get_items` R1, R2; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but inactive.
2. B = line 2 on T.
3. A = line 1 on T, but `description "First"` (commit point after this line).
4. extra row X.

**When**
- `result = svc.get_items(db, tpl_id=T.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. returns: `[r.id for r in result] == [A.id, B.id]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: x_kept.

### OTSV-GI-02 — a line of another workspace's template is not returned
- **Rules:** `get_items` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`.
2. ZL = line 1 on Z, but `workspace_id W0.id`.
3. T = template.
4. A = line 1 on T (commit point after this line).

**When**
- `result = svc.get_items(db, tpl_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [A.id]`.

### OTSV-GI-03 — pass-through BUG-2366: another workspace's template answers 404, not its lines
- **Rules:** `get_items` R1 [BUG-2366]
- **Kind:** bug
- **Expect:** xfail BUG-2366
- **Fails today on:** Then 1 (the call raises nothing: it returns `[]`)

**Given**
1. T = template.
2. A = line 1 on T.
3. Z = template, but `workspace_id W2.id`.
4. ZL = line 1 on Z, but `workspace_id W2.id` (commit point after this line).

**When**
- `svc.get_items(db, tpl_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Order template with ID {Z.id} not found"`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_items` R1 — BUG-2366's 404 for an unknown template | `OrderTemplateManager.get_items` R2 | The full shapes; here one pass-through card on another workspace's template (OTSV-GI-03). |
| Manager bugs BUG-1014, BUG-1216, BUG-2355 … BUG-2365 | `order_template_manager.cases.md` | Each refusal; the service passes them like any other exception (TC3 cards here). |
| BUG-2347 (OQ-22 answered) — owner-only skip of approval; owner-allowed creates and switches; BUG-2349 overflow | `OrderTemplateManager.create_template` / `update_template` R9, R8a; `update_item` R4a | The role check both ways; here only the 403 pass-through (C-06). |
| HR-7 — `1 <= limit <= 1000`, `skip >= 0`; `is_active` default `True` | `GET /order-templates/` | Endpoint rule. |
| 204 responses of the two deletes | `DELETE /order-templates/{id}/`, `DELETE /order-templates/items/{item_id}/` | Integration only. |
| `__init__`, singleton | none (no logic) | — |

## Spec gaps
None open. Revision 1's gaps were closed by the spec's Gap log (2026-11-07):
- G1: `create_template` R3a — the lines are committed with the template when the re-read fails; OTSV-C-04 re-selects them.
- G2: `OrderTemplateItem` lives in `app.models.order_template_item` (spec Facts); Conventions already used it.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_template` | R1 | OTSV-C-01, OTSV-C-05 |
| `create_template` | R2 | OTSV-C-02 |
| `create_template` | R2a [BUG-2347] | OTSV-C-06 |
| `create_template` | R3 | OTSV-C-03, OTSV-C-04 |
| `create_template` | R3a | OTSV-C-04 |
| `update_template` | R1 | OTSV-U-01 |
| `update_template` | R2 | OTSV-U-02, OTSV-U-03 |
| `update_template` | R3 (TC4, TC5) | covered once on create (spec Notes): OTSV-C-03, OTSV-C-04 |
| `get_template` | R1 | OTSV-G-01, OTSV-G-02, OTSV-G-03 |
| `get_template` | R2 | OTSV-G-01, OTSV-G-02 |
| `list_templates` | R1 | OTSV-L-01, OTSV-L-02 |
| `list_templates` | R1a | OTSV-L-04 |
| `list_templates` | R2 | OTSV-L-03 |
| `delete_template` | R1, Returns | OTSV-D-01, OTSV-D-02 |
| `delete_template` | R2 | OTSV-D-03 |
| `delete_template` | R3 | OTSV-D-04 |
| `add_item` | R1 | OTSV-A-01, OTSV-A-03 |
| `add_item` | R2 | OTSV-A-02 |
| `add_item` | R3 (TC4, TC5) | covered once on create: OTSV-C-03, OTSV-C-04 |
| `update_item` | R1 | OTSV-I-01, OTSV-I-04 |
| `update_item` | R2 | OTSV-I-02 |
| `update_item` | R3 [BUG-1226] | OTSV-I-03 |
| `update_item` | R4 (TC4, TC5) | covered once on create: OTSV-C-03, OTSV-C-04 |
| `remove_item` | R1, Returns | OTSV-R-01 |
| `remove_item` | R2 | OTSV-R-02 |
| `remove_item` | R3 | OTSV-R-03 |
| `get_items` | R1 | OTSV-GI-01, OTSV-GI-02 |
| `get_items` | R1 [BUG-2366] | OTSV-GI-03 |
| `get_items` | R2 | OTSV-GI-01 |
| TC1 | per write | C-01, U-01, D-01, A-01, I-01, R-01 |
| TC2 | once | OTSV-C-01 (also U-01, A-01, I-01) |
| TC3 | per write | C-02, U-02, D-03, A-02, I-02, R-02 |
| TC4 | create; non-refreshing writes | OTSV-C-03, OTSV-D-04, OTSV-R-03 |
| TC5 | once | OTSV-C-04 |
| TC6 | per read | OTSV-G-01, OTSV-G-02, OTSV-L-03, OTSV-GI-01 |
