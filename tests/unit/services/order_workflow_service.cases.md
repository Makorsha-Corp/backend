# Test cases — `app/services/order_workflow_service.py`

> **Spec:** `tests/unit/services/order_workflow_service.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-06; revised 2026-11-07: OQ-24 answered → BUG-2348; cases gaps 1–3 closed).
> **Revision:** 2 (2026-11-07) — spec apply-review and fill-gaps. OQ-24 → BUG-2348 (`create_workflow` R6 now intended): OWFS-Q24-01 … Q24-03 rewritten as strict xfail BUG-2348 (same IDs, same setups; Q24-03 now expects the 400 before the duplicate check); new Q24-04 (xfail: 400 before the status check), Q24-05, Q24-06 (pass: other spellings stay ordinary types), Q24-07 (pass: a second `purchase` row is never stored). Gap 1 (G1) → new passing TC3 cards OWFS-U-29, OWFS-D-20 (patched DAO, `Author: claude`). Gap 2 (G2) → OWFS-D-11 now compares the exact list; new D-21 (the foreign order has the lower id, its entry is still last), D-22 (two foreign orders, one entry, last). Gap 3 (G3) → new D-23 (a voided order blocks). Section Q24 renamed. No ID retired.
> **Revision:** 3 (2026-11-09) — from `order_workflow_service.verify.md` and the spec's revision 2026-11-09 (V1: the list order is now `get_workflows` R1a [BUG-100], non-strict). Finding 2 → new OWFS-GL-04 (an earlier row updated before the read), GL-05 (the same, paged one row at a time), both xfail BUG-100 **non-strict** as R1a and the skill's missing-sort rule require (physical order can match by accident; a strict card there would itself be flaky), and GL-06, the strict SQL-recorder card that asserts an `ORDER BY … id` and fails today. Names in GL-04 … GL-06 run against id order, so a name sort fails too. GL-01 … GL-03 keep their insert-only checks for the workspace filter and skip / limit (finding 3: their flake comes from the missing order; they now cite R1 only). Finding 4 → OWFS-C-01 and OWFS-U-01: `loaded(result)` moved to Then 1, before any attribute read; the other Then lines renumbered. Finding 5 → new OWFS-U-30 (strict xfail BUG-1223: a foreign status id sent to the purchase row gets the 400 STEPS, not the 404). Conventions gain the statement recorder and the non-strict line. No ID retired. Also (coordinator, same day): GL-01 … GL-03 no longer name rows chosen by an unordered query (they flaked about once in 56 runs): GL-01 compares a set; GL-02 now proves `limit` (4 rows, `skip=1, limit=2` → 2 distinct rows of the four); new GL-07 proves `skip` (3 rows, `skip=2` → 1); GL-03 checks 100 distinct rows of the 101. The order itself stays in the non-strict GL-04, GL-05 and the strict SQL alarm GL-06.
> **Counts:** 90 cases · 49 expected-to-pass · 41 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Per callable:** `get_workflows` 7 (3 bug) · `get_by_id` 5 · `get_by_type` 2 · `create_workflow` 16 (7 bug) · `update_workflow` 30 (15 bug) · `delete_workflow` 23 (12 bug) · section Q24 (`create_workflow` R6, BUG-2348) 7 (4 bug).
- **Depth:** services are the lighter target (TC1–TC6 plus pass-throughs), but this one writes order state: the purchase workflow's last step decides which purchase orders count as finished. So the decisions get full shapes: BUG-1215 (status of W0, built before W1; of W2, built after; unknown; the first bad id named), BUG-1223 (four shapes of a sent `status_sequence` on `purchase`, plus the fields still allowed), BUG-1222 (one card per blocker type and per cross-workspace shape: own order, finished order, voided order, an order of W2, an order of W0, own plus W2, a W0 order with a lower id than the own one, two foreign orders; `purchase` with and without orders; a non-blocking order of another workflow), BUG-2348 (no row, a row in W0 and W2, an empty list, an existing row, a foreign status id).
- **Transaction contract:** TC1 and TC3 per write method (spec Notes); TC2, TC5 on create; TC4 on update (exactly one rollback, verified) and delete. TC6 on each read. Update and delete "not found" (R3) leave a pending row pending, with no commit and no rollback.
- **TC3 on update and delete** passes through a patched `order_workflow_dao.update` / `remove` (spec Notes, G1): OWFS-U-29, OWFS-D-20, `Author: claude`. The bug-path TC3 cards (U-27 BUG-1223, D-16 BUG-1222) stay as xfail.
- **Expected-to-fail:** BUG-100 3 (GL-04, GL-05 non-strict, `Author: claude`; GL-06 strict, the SQL recorder). All others strict: BUG-1215 7 · BUG-1222 12 · BUG-1223 6 · BUG-2385 5 · BUG-2386 4 · BUG-2348 4. Passing companions: own-workspace ids stored (C-01, U-03), omitted fields kept (U-02), `name` / `description` / `allowed_reverts_json` still changeable on `purchase` (U-25), other workflows' orders do not block (D-06), `Purchase` / ` purchase` are ordinary types (Q24-05, Q24-06), a second `purchase` row is never stored (Q24-07).
- **OQ-24 answered (BUG-2348):** every create of type `purchase` sits in section Q24; the other create cards use `PFM`. Q24-03 and Q24-04 check that the 400 comes before the duplicate check and before the status check; U-30 does the same for `update_workflow` R8 against R6.
- **Needs a decision:** None. Gaps 1–3 closed by the spec's Gap log (G1–G3).

## Conventions for this module

**IDs.** `OWFS` = `app/services/order_workflow_service.py`. `GL` get_workflows · `GI` get_by_id · `GT` get_by_type · `C` create_workflow · `U` update_workflow · `D` delete_workflow · `Q24` OQ-24's rule (`create_workflow` R6, BUG-2348).

**Actors and fixed values.**
- `svc` = `order_workflow_service` (`from app.services.order_workflow_service import OrderWorkflowService, order_workflow_service`). `dao` = `order_workflow_dao` (`app.dao.order_workflow`). `db` = the test's real session, first argument; the rest by keyword. `result` = what the When returns.
- `OrderWorkflow` (`app.models.order_workflow`), `Status` (`app.models.status`), `PurchaseOrder` (`app.models.purchase_order`), `Workspace` (`app.models.workspace`). `OrderWorkflowCreate`, `OrderWorkflowUpdate` (`app.schemas.order_workflow`). `HTTPException` (`fastapi`). `AppValidationError` = `ValidationError` of `app.core.exceptions` (not pydantic's). `PydanticValidationError` = `pydantic.ValidationError`. `IntegrityError` (`sqlalchemy.exc`). `inspect`, `select`, `func` (`sqlalchemy`). `patch` (`unittest.mock`).
- MISSING = `999999999`. STEPS = `"The purchase workflow's steps are managed by the system"`. INUSE = `"Order workflow is in use by purchase orders"`. NODEL = `"The purchase workflow cannot be deleted"`. SYSTEM = `"The purchase workflow is managed by the system"`.

**Standing rows** (every test, in this order, no Given line): W0, W1, W2 = `make_workspace(db)` three times, so `W0.id < W1.id < W2.id`; U1 = `make_profile(db)`; then statuses, `Status(workspace_id=…, name=…, comment="Stage")`: T0 (W0, `"Draft"`), S1 (W1, `"Draft"`), S2 (W1, `"Approved"`), S3 (W1, `"Complete"`), T2 (W2, `"Draft"`). So `T0.id < S1.id < S2.id < S3.id < T2.id`. No workflow and no order exist unless the Given builds them.

**Given rows.** Inserted directly (never through `svc`), flushed one at a time in the order written. After "but" a line lists every column that differs.
- **workflow** = `OrderWorkflow(workspace_id=W1.id, name="Flow", type="PFM", status_sequence=[S1.id, S2.id], description="Old", allowed_reverts_json={"S2": ["S1"]})`.
- **purchase workflow** = a workflow, but `name "Purchase"`, `type "purchase"`, `status_sequence [S1.id, S2.id, S3.id]`.
- **order on F** = `PurchaseOrder(workspace_id=W1.id, po_number="PO-1", destination_type="storage", destination_id=1, current_status_id=S1.id, created_by=U1.id, order_workflow_id=F.id)`.
- **commit point** = after the last Given line the test runs `db.commit()`. Snapshots for `unchanged` and `nothing written` are taken there.
- **X** (only where the card lists it, after the commit point) = `X = make_workspace(db)`, flushed, not committed; `X_ID = X.id`.
- A Given line written as code is a step to run exactly.

**Externals.** None mocked, except in `Author: claude` cards: **failing dao m** = `E = RuntimeError("boom")`, then `with pytest.raises(RuntimeError) as exc:` around `with patch.object(app.services.order_workflow_service.order_workflow_dao, "m", side_effect=E):` around the When (`m` is `update` or `remove`; the DAO object the service imports, spec Notes G1).

**Named checks.**
- **re-read F** = `db.expire_all()`, then `db.get(OrderWorkflow, F.id)`; database values.
- **unchanged(F)** = after re-read, `workspace_id`, `name`, `type`, `description`, `status_sequence`, `allowed_reverts_json` of F equal their values at the commit point. For an order P: `order_workflow_id`, `current_status_id`.
- **nothing written** = the numbers of `order_workflows` rows and of `purchase_orders` rows (all workspaces) equal their values at the commit point.
- **loaded(r)** = `inspect(r).expired_attributes.isdisjoint({c.key for c in inspect(OrderWorkflow).column_attrs})` (column attributes only).
- **x_gone** = `db.get(Workspace, X_ID) is None` (checked after the `committed:` rollback).
- `committed:` lines: before the first, the test runs `db.rollback()` once; each line then re-reads with a fresh query.
- `session:` lines check the session directly after the call, before any re-read: `not db.new`, `not db.dirty`, `not db.deleted` as written.
- `raises: <Type>` = plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint; further lines on `exc.value` after the block, one `assert` per line. A `schema` card wraps only building the schema; `svc` is not called.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "refresh", side_effect=RuntimeError("boom")):` around the When.

**xfail cards.** Strict unless the Expect line says `(non-strict)`: `pytest.mark.xfail(strict=True, reason="BUG-n")`, or `strict=False` for a non-strict card. Write the call and checks exactly as shown; a non-strict card's assertion is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT … FROM order_workflows` sent; `order_part` = the text of `sql` after its first `ORDER BY` and before any `LIMIT` (`""` when there is no `ORDER BY`). A `statement:` line is a check on these.

**Race simulations.** None.

## `OrderWorkflowService.get_workflows`

### OWFS-GL-01 — returns the workspace's workflows, none of W0 or W2 (compared as a set)
- **Rules:** `get_workflows` R1 (insert-only rows; the order itself is R1a, GL-04 … GL-06)
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z0 = workflow, but `workspace_id W0.id`, `status_sequence [T0.id]`.
2. A = workflow.
3. B = workflow, but `name "Sales"`, `type "SFM"`.
4. Z2 = workflow, but `workspace_id W2.id`, `status_sequence [T2.id]`.

**When**
- `result = svc.get_workflows(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `len(result) == 2`.
3. returns: `{r.id for r in result} == {A.id, B.id}`.

### OWFS-GL-02 — limit is passed on: 4 rows, skip=1, limit=2 give 2 of them
- **Rules:** `get_workflows` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = workflow.
2. B = workflow, but `type "SFM"`.
3. C = workflow, but `type "TFM"`.
4. D = workflow, but `type "WFM"`.

**When**
- `result = svc.get_workflows(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `{r.id for r in result} <= {A.id, B.id, C.id, D.id}`.
3. returns: `len({r.id for r in result}) == 2`.

### OWFS-GL-07 — skip is passed on: 3 rows, skip=2 give 1 of them
- **Rules:** `get_workflows` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = workflow.
2. B = workflow, but `type "SFM"`.
3. C = workflow, but `type "TFM"`.

**When**
- `result = svc.get_workflows(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in {A.id, B.id, C.id}`.

### OWFS-GL-03 — with no skip or limit, 101 rows give 100 distinct ones; the read neither commits nor rolls back
- **Rules:** `get_workflows` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 workflows E1 … E101, built with `add_all` and one flush: Ek = workflow, but `type` = `f"T{k}"`.
2. `all_ids` = the set of the ids of E1 … E101.
3. X.

**When**
- spies: `result = svc.get_workflows(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`, `len({r.id for r in result}) == 100`, `{r.id for r in result} <= all_ids`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.
5. committed: x_gone.

### OWFS-GL-04 — after an earlier row is updated, the list is still in id order
- **Rules:** `get_workflows` R1a [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no `ORDER BY`: after the update the list comes back in storage order, [B, A] in the verifier's probe)

**Given**
1. A = workflow, but `name "Zed"`.
2. B = workflow, but `name "Abe"`, `type "SFM"`.
3. `A.description = "x"`, then `db.flush()`.
4. `db.expire_all()`

**When**
- `result = svc.get_workflows(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `[r.id for r in result] == [A.id, B.id]`.

### OWFS-GL-05 — paged one row at a time after an earlier row is updated, no row is missed or repeated
- **Rules:** `get_workflows` R1a [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no `ORDER BY`: the updated row A appears on no page in the verifier's probe)

**Given**
1. A = workflow, but `name "Zed"`.
2. B = workflow, but `name "Mid"`, `type "SFM"`.
3. C = workflow, but `name "Abe"`, `type "TFM"`.
4. `A.description = "x"`, then `db.flush()`.
5. `db.expire_all()`

**When**
- `pages = [svc.get_workflows(db, workspace_id=W1.id, skip=k, limit=1) for k in range(3)]` (one list comprehension: a single window cannot show this).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1]`.
2. returns: `[p[0].id for p in pages] == [A.id, B.id, C.id]`.

### OWFS-GL-06 — the list query orders by id
- **Rules:** `get_workflows` R1a [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100
- **Fails today on:** Then 2 (the base DAO's query has no `ORDER BY`)

**Given**
1. A = workflow, but `name "Zed"`.
2. B = workflow, but `name "Abe"`, `type "SFM"`.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = svc.get_workflows(db, workspace_id=W1.id)`.

**Then**
1. returns: `{r.id for r in result} == {A.id, B.id}`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"name" not in order_part`.

## `OrderWorkflowService.get_by_id`

### OWFS-GI-01 — returns the workflow of that id in the workspace; the read neither commits nor rolls back
- **Rules:** `get_by_id` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = workflow, but `type "SFM"`.
2. F = workflow.
3. X.

**When**
- spies: `result = svc.get_by_id(db, workflow_id=F.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, OrderWorkflow)`.
2. returns: `result.id == F.id`, `result.status_sequence == [S1.id, S2.id]`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.
6. committed: x_gone.

### OWFS-GI-02 — a W0 workflow's id (lower) returns None
- **Rules:** `get_by_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z0 = workflow, but `workspace_id W0.id`, `status_sequence [T0.id]`.
2. F = workflow.

**When**
- `result = svc.get_by_id(db, workflow_id=Z0.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### OWFS-GI-03 — a W2 workflow's id (higher) returns None
- **Rules:** `get_by_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F = workflow.
2. Z2 = workflow, but `workspace_id W2.id`, `status_sequence [T2.id]`.

**When**
- `result = svc.get_by_id(db, workflow_id=Z2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### OWFS-GI-04 — an unknown id returns None
- **Rules:** `get_by_id` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F = workflow.

**When**
- `result = svc.get_by_id(db, workflow_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### OWFS-GI-05 — id 0 returns None
- **Rules:** `get_by_id` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F = workflow.

**When**
- `result = svc.get_by_id(db, workflow_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

## `OrderWorkflowService.get_by_type`

### OWFS-GT-01 — returns the workspace's row of that type, as the DAO does; the read neither commits nor rolls back
- **Rules:** `get_by_type` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z0 = workflow, but `workspace_id W0.id`, `status_sequence [T0.id]`.
2. F = workflow.
3. Z2 = workflow, but `workspace_id W2.id`, `status_sequence [T2.id]`.
4. X.

**When**
- spies: `result = svc.get_by_type(db, workflow_type="PFM", workspace_id=W1.id)`.

**Then**
1. returns: `result.id == F.id`.
2. returns: `result.id == dao.get_by_type(db, workflow_type="PFM", workspace_id=W1.id).id`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.
6. committed: x_gone.

### OWFS-GT-02 — another spelling of the type returns None
- **Rules:** `get_by_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F = workflow.

**When**
- `result = svc.get_by_type(db, workflow_type="pfm", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

## `OrderWorkflowService.create_workflow`

> No card in this section creates a workflow of type `purchase`: that path is `create_workflow` R6 (BUG-2348, OQ-24 answered) and lives only in section Q24.

### OWFS-C-01 — create stores every field, commits, and returns the row re-read
- **Rules:** `create_workflow` R1, R5, TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No workflow in W1 (commit point after this line).

**When**
- `result = svc.create_workflow(db, workflow_in=OrderWorkflowCreate(name="Flow", type="PFM", description="Main", status_sequence=[S1.id, S2.id], allowed_reverts_json={"S2": ["S1"]}), workspace_id=W1.id)`.

**Then**
1. returns: loaded(result) (checked first, before any attribute of `result` is read).
2. returns: `isinstance(result, OrderWorkflow)`.
3. returns: `result.id is not None`, `result.workspace_id == W1.id`.
4. committed: the row with id `result.id`: `name == "Flow"`, `type == "PFM"`, `description == "Main"`.
5. committed: the row with id `result.id`: `status_sequence == [S1.id, S2.id]`, `allowed_reverts_json == {"S2": ["S1"]}`, `workspace_id == W1.id`.

### OWFS-C-02 — description and allowed_reverts_json left out read back None
- **Rules:** `create_workflow` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No workflow in W1 (commit point after this line).

**When**
- `result = svc.create_workflow(db, workflow_in=OrderWorkflowCreate(name="Flow", type="PFM", status_sequence=[S1.id]), workspace_id=W1.id)`.

**Then**
1. returns: `result.description is None`, `result.allowed_reverts_json is None`.
2. committed: the row with id `result.id`: `description is None`, `allowed_reverts_json is None`.

### OWFS-C-03 — a whitespace-only name is refused by the schema
- **Rules:** `create_workflow` R2 [BUG-2385], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-2385
- **Fails today on:** Then 1 (the schema accepts `"  "`)

**Given**
1. No workflow in W1.

**When**
- build `OrderWorkflowCreate(name="  ", type="PFM", status_sequence=[S1.id])` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### OWFS-C-04 — an empty name is refused by the schema
- **Rules:** `create_workflow` R2 [BUG-2385], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-2385
- **Fails today on:** Then 1 (the schema accepts `""`)

**Given**
1. No workflow in W1.

**When**
- build `OrderWorkflowCreate(name="", type="PFM", status_sequence=[S1.id])` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### OWFS-C-05 — the name is stored trimmed
- **Rules:** `create_workflow` R2 [BUG-2385]
- **Kind:** bug
- **Expect:** xfail BUG-2385
- **Fails today on:** Then 2 (stored as typed, `" Flow B "`)

**Given**
1. No workflow in W1 (commit point after this line).

**When**
- `result = svc.create_workflow(db, workflow_in=OrderWorkflowCreate(name=" Flow B ", type="PFM", status_sequence=[S1.id]), workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: the row with id `result.id`: `name == "Flow B"`.

### OWFS-C-06 — a second workflow of the type in the workspace: IntegrityError, rolled back with other pending changes
- **Rules:** `create_workflow` R3, R7, TC3, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. F = workflow (commit point after this line).
2. X.

**When**
- `svc.create_workflow(db, workflow_in=OrderWorkflowCreate(name="Other", type="PFM", status_sequence=[S2.id]), workspace_id=W1.id)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. raises: `"uq_order_workflows_workspace_type" in str(exc.value)`.
4. session: `not db.new and not db.dirty and not db.deleted`.
5. committed: x_gone.
6. nothing written: nothing written.
7. unchanged: unchanged(F).

### OWFS-C-07 — the same type in W0 and W2 does not stop a create in W1
- **Rules:** `create_workflow` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z0 = workflow, but `workspace_id W0.id`, `status_sequence [T0.id]`.
2. Z2 = workflow, but `workspace_id W2.id`, `status_sequence [T2.id]` (commit point after this line).

**When**
- `result = svc.create_workflow(db, workflow_in=OrderWorkflowCreate(name="Flow", type="PFM", status_sequence=[S1.id]), workspace_id=W1.id)`.

**Then**
1. returns: `result.workspace_id == W1.id`.
2. committed: `order_workflows` with `type == "PFM"` has exactly 3 rows.

### OWFS-C-08 — the type is exact: "pfm" next to "PFM" is a second row
- **Rules:** `create_workflow` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F = workflow (commit point after this line).

**When**
- `result = svc.create_workflow(db, workflow_in=OrderWorkflowCreate(name="Lower", type="pfm", status_sequence=[S1.id]), workspace_id=W1.id)`.

**Then**
1. returns: `result.type == "pfm"`.
2. committed: `order_workflows` with `workspace_id == W1.id` has exactly 2 rows.

### OWFS-C-09 — the type is exact: " PFM" next to "PFM" is a second row, stored as sent
- **Rules:** `create_workflow` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F = workflow (commit point after this line).

**When**
- `result = svc.create_workflow(db, workflow_in=OrderWorkflowCreate(name="Spaced", type=" PFM", status_sequence=[S1.id]), workspace_id=W1.id)`.

**Then**
1. returns: `result.type == " PFM"`.
2. committed: the row with id `result.id`: `type == " PFM"`.

### OWFS-C-10 — a status of W0 (lower id) in the sequence is refused as not found
- **Rules:** `create_workflow` R4 [BUG-1215], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1215
- **Fails today on:** Then 1 (no HTTPException: the list is stored unchecked)

**Given**
1. No workflow in W1 (commit point after this line).

**When**
- `svc.create_workflow(db, workflow_in=OrderWorkflowCreate(name="Flow", type="PFM", status_sequence=[S1.id, T0.id]), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Status with ID {T0.id} not found"`.
4. session: `not db.new and not db.dirty and not db.deleted`.
5. nothing written: nothing written.

### OWFS-C-11 — a status of W2 (higher id) in the sequence is refused as not found
- **Rules:** `create_workflow` R4 [BUG-1215], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1215
- **Fails today on:** Then 1 (no HTTPException: the list is stored unchecked)

**Given**
1. No workflow in W1 (commit point after this line).

**When**
- `svc.create_workflow(db, workflow_in=OrderWorkflowCreate(name="Flow", type="PFM", status_sequence=[T2.id, S1.id]), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Status with ID {T2.id} not found"`.
4. session: `not db.new and not db.dirty and not db.deleted`.
5. nothing written: nothing written.

### OWFS-C-12 — an unknown status id is refused as not found
- **Rules:** `create_workflow` R4 [BUG-1215], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1215
- **Fails today on:** Then 1 (no HTTPException: the list is stored unchecked)

**Given**
1. No workflow in W1 (commit point after this line).

**When**
- `svc.create_workflow(db, workflow_in=OrderWorkflowCreate(name="Flow", type="PFM", status_sequence=[MISSING]), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Status with ID 999999999 not found"`.
4. session: `not db.new and not db.dirty and not db.deleted`.
5. nothing written: nothing written.

### OWFS-C-13 — with two bad ids the first one in the list is named
- **Rules:** `create_workflow` R4 [BUG-1215]
- **Kind:** bug
- **Expect:** xfail BUG-1215
- **Fails today on:** Then 1 (no HTTPException: the list is stored unchecked)

**Given**
1. No workflow in W1 (commit point after this line).

**When**
- `svc.create_workflow(db, workflow_in=OrderWorkflowCreate(name="Flow", type="PFM", status_sequence=[S1.id, MISSING, T0.id]), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Status with ID 999999999 not found"`.
3. nothing written: nothing written.

### OWFS-C-14 — an empty sequence is stored as []
- **Rules:** `create_workflow` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No workflow in W1 (commit point after this line).

**When**
- `result = svc.create_workflow(db, workflow_in=OrderWorkflowCreate(name="Flow", type="PFM", status_sequence=[]), workspace_id=W1.id)`.

**Then**
1. returns: `result.status_sequence == []`.
2. committed: the row with id `result.id`: `status_sequence == []`.

### OWFS-C-15 — repeated ids are stored as sent
- **Rules:** `create_workflow` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No workflow in W1 (commit point after this line).

**When**
- `result = svc.create_workflow(db, workflow_in=OrderWorkflowCreate(name="Flow", type="PFM", status_sequence=[S2.id, S1.id, S2.id]), workspace_id=W1.id)`.

**Then**
1. returns: `result.status_sequence == [S2.id, S1.id, S2.id]`.
2. committed: the row with id `result.id`: `status_sequence == [S2.id, S1.id, S2.id]`.

### OWFS-C-16 — a failing re-read after the commit leaves the workflow saved
- **Rules:** `create_workflow` R7, TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. No workflow in W1 (commit point after this line).

**When**
- failing refresh: `svc.create_workflow(db, workflow_in=OrderWorkflowCreate(name="Flow", type="PFM", status_sequence=[S1.id]), workspace_id=W1.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: `order_workflows` with `workspace_id == W1.id` and `type == "PFM"` has exactly 1 row, `name == "Flow"`.

## `OrderWorkflowService.update_workflow`

### OWFS-U-01 — sent fields are set, the rest stay; committed and returned re-read
- **Rules:** `update_workflow` R2, TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. F = workflow (commit point after this line).

**When**
- `result = svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(name="Flow B", description="New"), workspace_id=W1.id)`.

**Then**
1. returns: loaded(result) (checked first, before any attribute of `result` is read).
2. returns: `result.id == F.id`.
3. committed: F: `name == "Flow B"`, `description == "New"`.
4. committed: F: `type == "PFM"`, `status_sequence == [S1.id, S2.id]`, `allowed_reverts_json == {"S2": ["S1"]}`.

### OWFS-U-02 — only the name sent: description, sequence and reverts keep their values
- **Rules:** `update_workflow` R2, R7 (omitted fields stay)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F = workflow (commit point after this line).

**When**
- `result = svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(name="Flow B"), workspace_id=W1.id)`.

**Then**
1. returns: `result.name == "Flow B"`.
2. committed: F: `description == "Old"`, `status_sequence == [S1.id, S2.id]`, `allowed_reverts_json == {"S2": ["S1"]}`.

### OWFS-U-03 — a sent sequence of own statuses replaces the list
- **Rules:** `update_workflow` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. F = workflow (commit point after this line).

**When**
- `result = svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(status_sequence=[S3.id, S1.id]), workspace_id=W1.id)`.

**Then**
1. returns: `result.status_sequence == [S3.id, S1.id]`.
2. committed: F: `status_sequence == [S3.id, S1.id]`, `name == "Flow"`.

### OWFS-U-04 — an empty sequence is stored as []
- **Rules:** `update_workflow` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F = workflow (commit point after this line).

**When**
- `result = svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(status_sequence=[]), workspace_id=W1.id)`.

**Then**
1. returns: `result.status_sequence == []`.
2. committed: F: `status_sequence == []`.

### OWFS-U-05 — repeated ids are stored as sent
- **Rules:** `update_workflow` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F = workflow (commit point after this line).

**When**
- `result = svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(status_sequence=[S2.id, S2.id]), workspace_id=W1.id)`.

**Then**
1. returns: `result.status_sequence == [S2.id, S2.id]`.
2. committed: F: `status_sequence == [S2.id, S2.id]`.

### OWFS-U-06 — allowed_reverts_json is replaced when sent
- **Rules:** `update_workflow` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. F = workflow (commit point after this line).

**When**
- `result = svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(allowed_reverts_json={"S3": ["S2"]}), workspace_id=W1.id)`.

**Then**
1. returns: `result.allowed_reverts_json == {"S3": ["S2"]}`.
2. committed: F: `allowed_reverts_json == {"S3": ["S2"]}`, `description == "Old"`.

### OWFS-U-07 — a W0 workflow's id (lower) returns None, nothing written
- **Rules:** `update_workflow` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z0 = workflow, but `workspace_id W0.id`, `status_sequence [T0.id]`.
2. F = workflow (commit point after this line).

**When**
- `result = svc.update_workflow(db, workflow_id=Z0.id, workflow_in=OrderWorkflowUpdate(name="Hacked"), workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. session: `not db.new and not db.dirty and not db.deleted`.
3. committed: the row Z0: `name == "Flow"`.
4. nothing written: nothing written.

### OWFS-U-08 — a W2 workflow's id (higher) returns None, nothing written
- **Rules:** `update_workflow` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F = workflow.
2. Z2 = workflow, but `workspace_id W2.id`, `status_sequence [T2.id]` (commit point after this line).

**When**
- `result = svc.update_workflow(db, workflow_id=Z2.id, workflow_in=OrderWorkflowUpdate(name="Hacked"), workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. session: `not db.new and not db.dirty and not db.deleted`.
3. committed: the row Z2: `name == "Flow"`.
4. nothing written: nothing written.

### OWFS-U-09 — an unknown id returns None
- **Rules:** `update_workflow` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F = workflow (commit point after this line).

**When**
- `result = svc.update_workflow(db, workflow_id=MISSING, workflow_in=OrderWorkflowUpdate(name="Hacked"), workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. session: `not db.new and not db.dirty and not db.deleted`.
3. nothing written: nothing written.
4. unchanged: unchanged(F).

### OWFS-U-10 — id 0 returns None with no commit and no rollback: a pending row stays pending
- **Rules:** `update_workflow` R1, R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F = workflow (commit point after this line).
2. X.

**When**
- spies: `result = svc.update_workflow(db, workflow_id=0, workflow_in=OrderWorkflowUpdate(name="Hacked"), workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.
5. committed: x_gone.
6. unchanged: unchanged(F).

### OWFS-U-11 — the update schema has no type field
- **Rules:** `update_workflow` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows needed.

**When**
- read `OrderWorkflowUpdate.model_fields` (target `schema`).

**Then**
1. returns: `"type" not in OrderWorkflowUpdate.model_fields`.

### OWFS-U-12 — a sent name is stored trimmed
- **Rules:** `update_workflow` R5 [BUG-2385]
- **Kind:** bug
- **Expect:** xfail BUG-2385
- **Fails today on:** Then 2 (stored as typed, `" Flow B "`)

**Given**
1. F = workflow (commit point after this line).

**When**
- `result = svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(name=" Flow B "), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == F.id`.
2. committed: F: `name == "Flow B"`.

### OWFS-U-13 — a whitespace-only name is refused by the update schema
- **Rules:** `update_workflow` R5 [BUG-2385], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-2385
- **Fails today on:** Then 1 (the schema accepts `"  "`)

**Given**
1. No rows needed.

**When**
- build `OrderWorkflowUpdate(name="  ")` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### OWFS-U-14 — a sent status of W0 (lower id) is refused as not found
- **Rules:** `update_workflow` R6 [BUG-1215], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1215
- **Fails today on:** Then 1 (no HTTPException: the list is stored unchecked)

**Given**
1. F = workflow (commit point after this line).

**When**
- `svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(status_sequence=[S1.id, T0.id]), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Status with ID {T0.id} not found"`.
4. session: `not db.new and not db.dirty and not db.deleted`.
5. unchanged: unchanged(F).

### OWFS-U-15 — a sent status of W2 (higher id) is refused as not found
- **Rules:** `update_workflow` R6 [BUG-1215], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1215
- **Fails today on:** Then 1 (no HTTPException: the list is stored unchecked)

**Given**
1. F = workflow (commit point after this line).

**When**
- `svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(status_sequence=[T2.id]), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Status with ID {T2.id} not found"`.
4. session: `not db.new and not db.dirty and not db.deleted`.
5. unchanged: unchanged(F).

### OWFS-U-16 — a sent unknown status id is refused, and the name sent with it is not stored
- **Rules:** `update_workflow` R6 [BUG-1215], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1215
- **Fails today on:** Then 1 (no HTTPException: the list is stored unchecked)

**Given**
1. F = workflow (commit point after this line).

**When**
- `svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(name="Flow B", status_sequence=[MISSING]), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Status with ID 999999999 not found"`.
3. session: `not db.new and not db.dirty and not db.deleted`.
4. unchanged: unchanged(F).

### OWFS-U-17 — an explicit null clears the description
- **Rules:** `update_workflow` R7 [BUG-2386]
- **Kind:** bug
- **Expect:** xfail BUG-2386
- **Fails today on:** Then 2 (the `null` is dropped; `description` stays `"Old"`)

**Given**
1. F = workflow (commit point after this line).

**When**
- `result = svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(description=None), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == F.id`.
2. committed: F: `description is None`.
3. committed: F: `name == "Flow"`, `allowed_reverts_json == {"S2": ["S1"]}`.

### OWFS-U-18 — an explicit null clears allowed_reverts_json
- **Rules:** `update_workflow` R7 [BUG-2386]
- **Kind:** bug
- **Expect:** xfail BUG-2386
- **Fails today on:** Then 2 (the `null` is dropped; the value stays `{"S2": ["S1"]}`)

**Given**
1. F = workflow (commit point after this line).

**When**
- `result = svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(allowed_reverts_json=None), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == F.id`.
2. committed: F: `allowed_reverts_json is None`.
3. committed: F: `description == "Old"`.

### OWFS-U-19 — an explicit null name is refused by the update schema
- **Rules:** `update_workflow` R7 [BUG-2386], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-2386
- **Fails today on:** Then 1 (the schema accepts `name=None`)

**Given**
1. No rows needed.

**When**
- build `OrderWorkflowUpdate(name=None)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### OWFS-U-20 — an explicit null sequence is refused by the update schema
- **Rules:** `update_workflow` R7 [BUG-2386], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-2386
- **Fails today on:** Then 1 (the schema accepts `status_sequence=None`)

**Given**
1. No rows needed.

**When**
- build `OrderWorkflowUpdate(status_sequence=None)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### OWFS-U-21 — on purchase, a new sequence is refused
- **Rules:** `update_workflow` R8 [BUG-1223], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1223
- **Fails today on:** Then 1 (no HTTPException: the sequence is stored)

**Given**
1. F = purchase workflow (commit point after this line).

**When**
- `svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(status_sequence=[S1.id]), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == STEPS`.
4. session: `not db.new and not db.dirty and not db.deleted`.
5. unchanged: unchanged(F).

### OWFS-U-22 — on purchase, the current sequence sent again is refused too
- **Rules:** `update_workflow` R8 [BUG-1223]
- **Kind:** bug
- **Expect:** xfail BUG-1223
- **Fails today on:** Then 1 (no HTTPException: the sequence is stored)

**Given**
1. F = purchase workflow (commit point after this line).

**When**
- `svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(status_sequence=[S1.id, S2.id, S3.id]), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == STEPS`.
4. unchanged: unchanged(F).

### OWFS-U-23 — on purchase, a sequence with a name: neither is stored
- **Rules:** `update_workflow` R8 [BUG-1223]
- **Kind:** bug
- **Expect:** xfail BUG-1223
- **Fails today on:** Then 1 (no HTTPException: both are stored)

**Given**
1. F = purchase workflow (commit point after this line).

**When**
- `svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(name="Buying", status_sequence=[S1.id]), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == STEPS`.
3. session: `not db.new and not db.dirty and not db.deleted`.
4. committed: F: `name == "Purchase"`.
5. unchanged: unchanged(F).

### OWFS-U-24 — on purchase, an empty sequence is refused
- **Rules:** `update_workflow` R8 [BUG-1223]
- **Kind:** bug
- **Expect:** xfail BUG-1223
- **Fails today on:** Then 1 (no HTTPException: `[]` is stored, leaving no finished stage)

**Given**
1. F = purchase workflow (commit point after this line).

**When**
- `svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(status_sequence=[]), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == STEPS`.
3. unchanged: unchanged(F).

### OWFS-U-25 — on purchase, name, description and reverts alone may still change
- **Rules:** `update_workflow` R8, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. F = purchase workflow (commit point after this line).

**When**
- `result = svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(name="Buying", description="New", allowed_reverts_json={"S3": ["S2"]}), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == F.id`.
2. committed: F: `name == "Buying"`, `description == "New"`, `allowed_reverts_json == {"S3": ["S2"]}`.
3. committed: F: `status_sequence == [S1.id, S2.id, S3.id]`, `type == "purchase"`.

### OWFS-U-26 — type "Purchase" in capitals is not the purchase row: its sequence may change
- **Rules:** `update_workflow` R8, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F = workflow, but `type "Purchase"` (commit point after this line).

**When**
- `result = svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(status_sequence=[S1.id]), workspace_id=W1.id)`.

**Then**
1. returns: `result.status_sequence == [S1.id]`.
2. committed: F: `status_sequence == [S1.id]`.

### OWFS-U-27 — a refusal rolls back other pending changes in the session too
- **Rules:** `update_workflow` R10, TC3 [BUG-1223]
- **Kind:** bug
- **Expect:** xfail BUG-1223
- **Fails today on:** Then 1 (no HTTPException: the sequence is stored and committed)

**Given**
1. F = purchase workflow (commit point after this line).
2. X.

**When**
- `svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(status_sequence=[S1.id]), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. session: `X not in db`.
3. committed: x_gone.
4. unchanged: unchanged(F).

### OWFS-U-28 — a failing commit gives exactly one rollback, and nothing is saved
- **Rules:** `update_workflow` R10, TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. F = workflow (commit point after this line).
2. X.

**When**
- failing commit: `svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(name="Flow B"), workspace_id=W1.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count == 1`.
3. committed: x_gone.
4. unchanged: unchanged(F).

### OWFS-U-29 — an error inside the update rolls back, reaches the caller as the same object, and discards other pending changes
- **Rules:** `update_workflow` R10, TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. F = workflow (commit point after this line).
2. X.

**When**
- failing dao update: `svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(name="Flow B"), workspace_id=W1.id)`.

**Then**
1. raises: `exc.value is E`.
2. session: `X not in db`.
3. session: `db.execute(select(func.count()).select_from(OrderWorkflow)).scalar() >= 1` (usable).
4. committed: x_gone.
5. unchanged: unchanged(F).

### OWFS-U-30 — on purchase, a sequence with a status of W2 gets the 400, not the status 404
- **Rules:** `update_workflow` R8 [BUG-1223], R6
- **Kind:** bug
- **Expect:** xfail BUG-1223
- **Fails today on:** Then 1 (no HTTPException: the foreign id is stored)

**Given**
1. F = purchase workflow (commit point after this line).

**When**
- `svc.update_workflow(db, workflow_id=F.id, workflow_in=OrderWorkflowUpdate(status_sequence=[T2.id]), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == STEPS`.
4. session: `not db.new and not db.dirty and not db.deleted`.
5. unchanged: unchanged(F).

## `OrderWorkflowService.delete_workflow`

### OWFS-D-01 — a workflow no order uses is deleted and committed
- **Rules:** `delete_workflow` R2, TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = workflow, but `type "SFM"`.
2. F = workflow (commit point after this line).

**When**
- `result = svc.delete_workflow(db, workflow_id=F.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. committed: `db.get(OrderWorkflow, F.id) is None`.
3. committed: `db.get(OrderWorkflow, B.id) is not None`.

### OWFS-D-02 — a W0 workflow's id (lower) returns False and deletes nothing
- **Rules:** `delete_workflow` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z0 = workflow, but `workspace_id W0.id`, `status_sequence [T0.id]`.
2. F = workflow (commit point after this line).

**When**
- `result = svc.delete_workflow(db, workflow_id=Z0.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.
2. session: `not db.deleted`.
3. committed: `db.get(OrderWorkflow, Z0.id) is not None`.
4. nothing written: nothing written.

### OWFS-D-03 — a W2 workflow's id (higher) returns False and deletes nothing
- **Rules:** `delete_workflow` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F = workflow.
2. Z2 = workflow, but `workspace_id W2.id`, `status_sequence [T2.id]` (commit point after this line).

**When**
- `result = svc.delete_workflow(db, workflow_id=Z2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.
2. session: `not db.deleted`.
3. committed: `db.get(OrderWorkflow, Z2.id) is not None`.
4. nothing written: nothing written.

### OWFS-D-04 — an unknown id returns False
- **Rules:** `delete_workflow` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F = workflow (commit point after this line).

**When**
- `result = svc.delete_workflow(db, workflow_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.
2. session: `not db.deleted`.
3. nothing written: nothing written.

### OWFS-D-05 — id 0 returns False with no commit and no rollback: a pending row stays pending
- **Rules:** `delete_workflow` R1, R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F = workflow (commit point after this line).
2. X.

**When**
- spies: `result = svc.delete_workflow(db, workflow_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.
5. committed: x_gone.
6. committed: `db.get(OrderWorkflow, F.id) is not None`.

### OWFS-D-06 — an order on another workflow does not block the delete
- **Rules:** `delete_workflow` R2, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. G = workflow, but `type "SFM"`.
2. F = workflow.
3. P = order on G (commit point after this line).

**When**
- `result = svc.delete_workflow(db, workflow_id=F.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. committed: `db.get(OrderWorkflow, F.id) is None`.
3. committed: the order P: `order_workflow_id == G.id`.

### OWFS-D-07 — a workflow one order uses is refused, the order listed
- **Rules:** `delete_workflow` R4 [BUG-1222], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1222
- **Fails today on:** Then 1 (no AppValidationError: the workflow is deleted)

**Given**
1. F = workflow.
2. P = order on F (commit point after this line).

**When**
- `svc.delete_workflow(db, workflow_id=F.id, workspace_id=W1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == INUSE`.
4. raises: `exc.value.errors == [{"type": "purchase_order", "id": P.id}]`.
5. session: `not db.deleted and not db.dirty`.
6. unchanged: unchanged(F).
7. re-read P: `order_workflow_id == F.id`.

### OWFS-D-08 — two orders, one at the last (finished) step: both listed, in id order
- **Rules:** `delete_workflow` R4 [BUG-1222]
- **Kind:** bug
- **Expect:** xfail BUG-1222
- **Fails today on:** Then 1 (no AppValidationError: the workflow is deleted)

**Given**
1. F = workflow.
2. P1 = order on F.
3. P2 = order on F, but `po_number "PO-2"`, `current_status_id S2.id` (commit point after this line).

**When**
- `svc.delete_workflow(db, workflow_id=F.id, workspace_id=W1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.detail == INUSE`.
3. raises: `exc.value.errors == [{"type": "purchase_order", "id": P1.id}, {"type": "purchase_order", "id": P2.id}]`.
4. unchanged: unchanged(F).
5. re-read P2: `order_workflow_id == F.id`.

### OWFS-D-09 — only an order of W2 points at it: one other_workspace entry, no id
- **Rules:** `delete_workflow` R4 [BUG-1222] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-1222
- **Fails today on:** Then 1 (no AppValidationError: the workflow is deleted)

**Given**
1. F = workflow.
2. P = order on F, but `workspace_id W2.id`, `current_status_id T2.id` (commit point after this line).

**When**
- `svc.delete_workflow(db, workflow_id=F.id, workspace_id=W1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.detail == INUSE`.
3. raises: `exc.value.errors == [{"type": "other_workspace"}]`.
4. unchanged: unchanged(F).
5. re-read P: `order_workflow_id == F.id`.

### OWFS-D-10 — only an order of W0 points at it: one other_workspace entry, no id
- **Rules:** `delete_workflow` R4 [BUG-1222] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-1222
- **Fails today on:** Then 1 (no AppValidationError: the workflow is deleted)

**Given**
1. F = workflow.
2. P = order on F, but `workspace_id W0.id`, `current_status_id T0.id` (commit point after this line).

**When**
- `svc.delete_workflow(db, workflow_id=F.id, workspace_id=W1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.errors == [{"type": "other_workspace"}]`.
3. unchanged: unchanged(F).
4. re-read P: `order_workflow_id == F.id`.

### OWFS-D-11 — an own order and an order of W2: the own entry, then the foreign one without id, last
- **Rules:** `delete_workflow` R4 [BUG-1222] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-1222
- **Fails today on:** Then 1 (no AppValidationError: the workflow is deleted)

**Given**
1. F = workflow.
2. P1 = order on F.
3. P2 = order on F, but `po_number "PO-2"`, `workspace_id W2.id`, `current_status_id T2.id` (commit point after this line).

**When**
- `svc.delete_workflow(db, workflow_id=F.id, workspace_id=W1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.detail == INUSE`.
3. raises: `exc.value.errors == [{"type": "purchase_order", "id": P1.id}, {"type": "other_workspace"}]`.
4. unchanged: unchanged(F).

### OWFS-D-12 — the purchase workflow is never deleted, even with no orders
- **Rules:** `delete_workflow` R5 [BUG-1222], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1222
- **Fails today on:** Then 1 (no AppValidationError: the row is deleted)

**Given**
1. F = purchase workflow (commit point after this line).

**When**
- `svc.delete_workflow(db, workflow_id=F.id, workspace_id=W1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == NODEL`.
4. raises: `exc.value.errors == []`.
5. session: `not db.deleted`.
6. unchanged: unchanged(F).

### OWFS-D-13 — the purchase workflow with an order gets the purchase answer, not the in-use one
- **Rules:** `delete_workflow` R5 [BUG-1222]
- **Kind:** bug
- **Expect:** xfail BUG-1222
- **Fails today on:** Then 1 (no AppValidationError: the row is deleted)

**Given**
1. F = purchase workflow.
2. P = order on F (commit point after this line).

**When**
- `svc.delete_workflow(db, workflow_id=F.id, workspace_id=W1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.detail == NODEL`.
3. raises: `exc.value.errors == []`.
4. unchanged: unchanged(F).
5. re-read P: `order_workflow_id == F.id`.

### OWFS-D-14 — a failing commit rolls back: the workflow stays, other pending changes go
- **Rules:** `delete_workflow` R6, TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. F = workflow (commit point after this line).
2. X.

**When**
- failing commit: `svc.delete_workflow(db, workflow_id=F.id, workspace_id=W1.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. committed: x_gone.
4. committed: `db.get(OrderWorkflow, F.id) is not None`.

### OWFS-D-15 — type "Purchase" in capitals is not the purchase row: it is deleted
- **Rules:** `delete_workflow` R2, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F = workflow, but `type "Purchase"` (commit point after this line).

**When**
- `result = svc.delete_workflow(db, workflow_id=F.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. committed: `db.get(OrderWorkflow, F.id) is None`.

### OWFS-D-16 — a refusal rolls back other pending changes in the session too
- **Rules:** `delete_workflow` R6, TC3 [BUG-1222]
- **Kind:** bug
- **Expect:** xfail BUG-1222
- **Fails today on:** Then 1 (no AppValidationError: the workflow is deleted and committed)

**Given**
1. F = workflow.
2. P = order on F (commit point after this line).
3. X.

**When**
- `svc.delete_workflow(db, workflow_id=F.id, workspace_id=W1.id)`.

**Then**
1. raises: `AppValidationError`.
2. session: `X not in db`.
3. committed: x_gone.
4. unchanged: unchanged(F).

### OWFS-D-17 — the refused delete leaves the order's link as it was (session side)
- **Rules:** `delete_workflow` R4 [BUG-1222]
- **Kind:** bug
- **Expect:** xfail BUG-1222
- **Fails today on:** Then 1 (no AppValidationError: the ORM sets the order's `order_workflow_id` to `NULL` and deletes)

**Given**
1. F = workflow.
2. P = order on F, but `current_status_id S2.id` (commit point after this line).

**When**
- `svc.delete_workflow(db, workflow_id=F.id, workspace_id=W1.id)`.

**Then**
1. raises: `AppValidationError`.
2. session: `not db.dirty and not db.deleted`.
3. committed: the order P: `order_workflow_id == F.id`, `current_status_id == S2.id`.

### OWFS-D-18 — an order of W2 on a W2 workflow does not block deleting a W1 workflow
- **Rules:** `delete_workflow` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F = workflow.
2. Z2 = workflow, but `workspace_id W2.id`, `status_sequence [T2.id]`.
3. P = order on Z2, but `workspace_id W2.id`, `current_status_id T2.id` (commit point after this line).

**When**
- `result = svc.delete_workflow(db, workflow_id=F.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. committed: `db.get(OrderWorkflow, F.id) is None`.
3. committed: the order P: `order_workflow_id == Z2.id`.

### OWFS-D-19 — delete commits once
- **Rules:** `delete_workflow` R2, TC1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F = workflow (commit point after this line).

**When**
- spies: `result = svc.delete_workflow(db, workflow_id=F.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. mock called: `cm.call_count == 1`.
3. mock called: `rb.call_count == 0`.

### OWFS-D-20 — an error inside the delete rolls back, reaches the caller as the same object, and discards other pending changes
- **Rules:** `delete_workflow` R6, TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. F = workflow (commit point after this line).
2. X.

**When**
- failing dao remove: `svc.delete_workflow(db, workflow_id=F.id, workspace_id=W1.id)`.

**Then**
1. raises: `exc.value is E`.
2. session: `X not in db`.
3. session: `db.execute(select(func.count()).select_from(OrderWorkflow)).scalar() >= 1` (usable).
4. committed: x_gone.
5. committed: `db.get(OrderWorkflow, F.id) is not None`.
6. unchanged: unchanged(F).

### OWFS-D-21 — an order of W0 with a lower id than the own order: its entry is still last
- **Rules:** `delete_workflow` R4 [BUG-1222] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-1222
- **Fails today on:** Then 1 (no AppValidationError: the workflow is deleted)

**Given**
1. F = workflow.
2. P0 = order on F, but `po_number "PO-0"`, `workspace_id W0.id`, `current_status_id T0.id`.
3. P1 = order on F (commit point after this line).

**When**
- `svc.delete_workflow(db, workflow_id=F.id, workspace_id=W1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.errors == [{"type": "purchase_order", "id": P1.id}, {"type": "other_workspace"}]`.
3. session: `not db.dirty and not db.deleted`.
4. unchanged: unchanged(F).
5. re-read P0: `order_workflow_id == F.id`.

### OWFS-D-22 — orders of W0 and of W2 beside an own order: one other_workspace entry, last
- **Rules:** `delete_workflow` R4 [BUG-1222] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-1222
- **Fails today on:** Then 1 (no AppValidationError: the workflow is deleted)

**Given**
1. F = workflow.
2. P0 = order on F, but `po_number "PO-0"`, `workspace_id W0.id`, `current_status_id T0.id`.
3. P1 = order on F.
4. P2 = order on F, but `po_number "PO-2"`, `workspace_id W2.id`, `current_status_id T2.id` (commit point after this line).

**When**
- `svc.delete_workflow(db, workflow_id=F.id, workspace_id=W1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.errors == [{"type": "purchase_order", "id": P1.id}, {"type": "other_workspace"}]`.
3. unchanged: unchanged(F).
4. re-read P2: `order_workflow_id == F.id`.

### OWFS-D-23 — a voided order blocks the delete and is listed
- **Rules:** `delete_workflow` R4 [BUG-1222]
- **Kind:** bug
- **Expect:** xfail BUG-1222
- **Fails today on:** Then 1 (no AppValidationError: the workflow is deleted)

**Given**
1. F = workflow.
2. P = order on F, but `voided True` (commit point after this line).

**When**
- `svc.delete_workflow(db, workflow_id=F.id, workspace_id=W1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.detail == INUSE`.
3. raises: `exc.value.errors == [{"type": "purchase_order", "id": P.id}]`.
4. session: `not db.dirty and not db.deleted`.
5. unchanged: unchanged(F).
6. re-read P: `order_workflow_id == F.id`, `voided is True`.

## OQ-24 answered — BUG-2348 (`create_workflow` R6)

> The owner answered OQ-24 on 2026-11-07: `purchase` cannot be created through the service. Every create of type `purchase` is in this section. Cards Q24-01 … Q24-03 keep their IDs and setups; they now expect the intended 400.

### OWFS-Q24-01 — purchase is refused where W1 has none, beside W0's and W2's; pending changes discarded
- **Rules:** `create_workflow` R6 [BUG-2348], Errors row 4, R7
- **Kind:** bug
- **Expect:** xfail BUG-2348
- **Fails today on:** Then 1 (no HTTPException: the row is created and committed)

**Given**
1. Z0 = purchase workflow, but `workspace_id W0.id`, `status_sequence [T0.id]`.
2. Z2 = purchase workflow, but `workspace_id W2.id`, `status_sequence [T2.id]` (commit point after this line).
3. X.

**When**
- `svc.create_workflow(db, workflow_in=OrderWorkflowCreate(name="Purchase", type="purchase", status_sequence=[S1.id]), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == SYSTEM`.
4. session: `not db.new and not db.dirty and not db.deleted`.
5. committed: x_gone.
6. nothing written: nothing written.
7. committed: `order_workflows` with `type == "purchase"` has exactly 2 rows.

### OWFS-Q24-02 — purchase with an empty list is refused
- **Rules:** `create_workflow` R6 [BUG-2348]
- **Kind:** bug
- **Expect:** xfail BUG-2348
- **Fails today on:** Then 1 (no HTTPException: the row is created with `[]`)

**Given**
1. No workflow in W1 (commit point after this line).

**When**
- `svc.create_workflow(db, workflow_in=OrderWorkflowCreate(name="Purchase", type="purchase", status_sequence=[]), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == SYSTEM`.
4. session: `not db.new`.
5. nothing written: nothing written.

### OWFS-Q24-03 — where W1 already has purchase: the 400, not the duplicate error
- **Rules:** `create_workflow` R6 [BUG-2348], R3
- **Kind:** bug
- **Expect:** xfail BUG-2348
- **Fails today on:** Then 1 (the call raises IntegrityError 23505: the duplicate check answers first)

**Given**
1. F = purchase workflow (commit point after this line).

**When**
- `svc.create_workflow(db, workflow_in=OrderWorkflowCreate(name="Purchase", type="purchase", status_sequence=[S1.id]), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == SYSTEM`.
4. session: `not db.new and not db.dirty and not db.deleted`.
5. nothing written: nothing written.
6. unchanged: unchanged(F).

### OWFS-Q24-04 — purchase with a status of W2: the 400, not the status 404
- **Rules:** `create_workflow` R6 [BUG-2348], R4
- **Kind:** bug
- **Expect:** xfail BUG-2348
- **Fails today on:** Then 1 (no HTTPException: the row is created with the foreign id)

**Given**
1. No workflow in W1 (commit point after this line).

**When**
- `svc.create_workflow(db, workflow_in=OrderWorkflowCreate(name="Purchase", type="purchase", status_sequence=[T2.id]), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == SYSTEM`.
4. session: `not db.new`.
5. nothing written: nothing written.

### OWFS-Q24-05 — type "Purchase" in capitals is an ordinary type and is created
- **Rules:** `create_workflow` R6, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No workflow in W1 (commit point after this line).

**When**
- `result = svc.create_workflow(db, workflow_in=OrderWorkflowCreate(name="Purchase", type="Purchase", status_sequence=[S1.id]), workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`, `result.type == "Purchase"`.
2. committed: the row with id `result.id`: `type == "Purchase"`, `status_sequence == [S1.id]`.

### OWFS-Q24-06 — type " purchase" with a leading space is an ordinary type, stored as sent
- **Rules:** `create_workflow` R6, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No workflow in W1 (commit point after this line).

**When**
- `result = svc.create_workflow(db, workflow_in=OrderWorkflowCreate(name="Purchase", type=" purchase", status_sequence=[S1.id]), workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`, `result.type == " purchase"`.
2. committed: the row with id `result.id`: `type == " purchase"`.

### OWFS-Q24-07 — a second purchase row in W1 is never stored, whichever refusal answers
- **Rules:** `create_workflow` R6, R3, R7
- **Kind:** error
- **Expect:** pass

**Given**
1. F = purchase workflow (commit point after this line).

**When**
- `svc.create_workflow(db, workflow_in=OrderWorkflowCreate(name="Purchase", type="purchase", status_sequence=[S1.id]), workspace_id=W1.id)`, inside `with pytest.raises((IntegrityError, HTTPException)) as exc:` (today `IntegrityError`, after BUG-2348's fix `HTTPException`; this card checks only what holds on both).

**Then**
1. raises: `isinstance(exc.value, (IntegrityError, HTTPException))`.
2. session: `not db.new and not db.dirty and not db.deleted`.
3. nothing written: nothing written.
4. unchanged: unchanged(F).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| 404 `Order workflow not found` for `None` / `False` | `app/api/v1/endpoints/order_workflows.py` (integration) | update, delete, get by id |
| 409 for `IntegrityError` (HR-2) | global handler (integration) | duplicate type |
| `ValidationError` 400 body format | `api_exception_handler` (integration) | `detail` and `errors` in the response |
| BUG-1217 — `limit >= 1` on `GET /order-workflows/` | endpoint (integration) | 422 |
| 201 / 204 status codes | endpoint (integration) | — |
| BUG-1227 — in-place list changes | `tests/unit/dao/order_workflow.cases.md` (OWF-IN-07) | nothing here changes a list in place |
| The terminal check reads `status_sequence` (OQ-24 example) | `app/utils/order_workflow_terminal.py` spec | which stage counts as finished |

## Spec gaps
None open. Gaps 1–3 of revision 1 were closed by the spec's Gap log (2026-11-07):
- G1: TC3 on update / delete by patching `order_workflow_dao.update` / `remove` → OWFS-U-29, OWFS-D-20.
- G2: order entries by id, the single `other_workspace` entry last → OWFS-D-11 (exact list), OWFS-D-21, OWFS-D-22.
- G3: a voided order is `voided = True` → OWFS-D-23.
- V1 (2026-11-09, verifier finding 1): the list order is `get_workflows` R1a [BUG-100], today's storage order → OWFS-GL-04 … GL-06.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_workflows` | R1 | OWFS-GL-01, OWFS-GL-02, OWFS-GL-03, OWFS-GL-07 |
| `get_workflows` | R1a [BUG-100] | OWFS-GL-04, OWFS-GL-05, OWFS-GL-06 |
| `get_workflows` | R2 (TC6) | OWFS-GL-03 |
| `get_by_id` | R1 | OWFS-GI-01 … OWFS-GI-05 |
| `get_by_id` | R2 (TC6) | OWFS-GI-01 |
| `get_by_type` | R1 | OWFS-GT-01, OWFS-GT-02 |
| `get_by_type` | R2 (TC6) | OWFS-GT-01 |
| `create_workflow` | R1, TC1, TC2 | OWFS-C-01, OWFS-C-02 |
| `create_workflow` | R2 [BUG-2385], Errors row 3 | OWFS-C-03, OWFS-C-04, OWFS-C-05 |
| `create_workflow` | R3, Errors row 1 | OWFS-C-06, OWFS-C-07, OWFS-C-08, OWFS-C-09 |
| `create_workflow` | R4 [BUG-1215], Errors row 2 | OWFS-C-10, OWFS-C-11, OWFS-C-12, OWFS-C-13 |
| `create_workflow` | R5 | OWFS-C-01, OWFS-C-14, OWFS-C-15 |
| `create_workflow` | R6 [BUG-2348], Errors row 4 | OWFS-Q24-01, OWFS-Q24-02, OWFS-Q24-03, OWFS-Q24-04 |
| `create_workflow` | R6 (other spellings; never stored) | OWFS-Q24-05, OWFS-Q24-06, OWFS-Q24-07 |
| `create_workflow` | R7, TC3 | OWFS-C-06, OWFS-Q24-01, OWFS-Q24-07 |
| `create_workflow` | TC5 | OWFS-C-16 |
| `update_workflow` | R1 | OWFS-U-07, OWFS-U-08, OWFS-U-09, OWFS-U-10 |
| `update_workflow` | R2, TC1, TC2 | OWFS-U-01, OWFS-U-02, OWFS-U-06, OWFS-U-25 |
| `update_workflow` | R3 | OWFS-U-10 |
| `update_workflow` | R4 | OWFS-U-11 |
| `update_workflow` | R5 [BUG-2385], Errors row 3 | OWFS-U-12, OWFS-U-13 |
| `update_workflow` | R6 [BUG-1215], Errors row 1 | OWFS-U-14, OWFS-U-15, OWFS-U-16 |
| `update_workflow` | R7 [BUG-2386], Errors row 3 | OWFS-U-17, OWFS-U-18, OWFS-U-19, OWFS-U-20; omitted fields OWFS-U-02 |
| `update_workflow` | R8 [BUG-1223], Errors row 2 | OWFS-U-21, OWFS-U-22, OWFS-U-23, OWFS-U-24, OWFS-U-30 (before R6); allowed fields OWFS-U-25, OWFS-U-26 |
| `update_workflow` | R9 | OWFS-U-03, OWFS-U-04, OWFS-U-05, OWFS-U-26 |
| `update_workflow` | R10, TC3 | OWFS-U-29 |
| `update_workflow` | R10, TC3 [BUG-1223] | OWFS-U-27 |
| `update_workflow` | R10, TC4 | OWFS-U-28 |
| `delete_workflow` | R1 | OWFS-D-02, OWFS-D-03, OWFS-D-04, OWFS-D-05 |
| `delete_workflow` | R2, TC1 | OWFS-D-01, OWFS-D-06, OWFS-D-15, OWFS-D-18, OWFS-D-19 |
| `delete_workflow` | R3 | OWFS-D-05 |
| `delete_workflow` | R4 [BUG-1222], Errors row 1 | OWFS-D-07, OWFS-D-08, OWFS-D-09, OWFS-D-10, OWFS-D-11, OWFS-D-17, OWFS-D-21, OWFS-D-22, OWFS-D-23 |
| `delete_workflow` | R5 [BUG-1222], Errors row 2 | OWFS-D-12, OWFS-D-13 |
| `delete_workflow` | R6, TC3 | OWFS-D-20 |
| `delete_workflow` | R6, TC3 [BUG-1222] | OWFS-D-16 |
| `delete_workflow` | R6, TC4 | OWFS-D-14 |
