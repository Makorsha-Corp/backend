# Test cases — `app/managers/work_order_manager.py`

> **Spec:** `tests/unit/managers/work_order_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-21) — the spec's fill-gaps round closed gaps 1–15 (Gap log G1–G15): schema modules (G1); `_set_machine_status` returns text (G2, SMS-01/02); quantity texts pinned (G3: CI-02, CI-03, RIC-02, ADJ-13, AIC-05, AIC-08, AIC-10, UI-08); `_run_start_side_effects` tuple (G4, RSE-01/02); template-path 409 by patch (G5, CT-22); "Maintenance" fallback (G6, CT-23); recompute actor (G7, RMA-01, RMA-10, RMA-11); create-side check in the schema (G8, C-31 pins `ValidationError`); FC-22 retired, lock deferred to the work order service (G9); CI-14 retired, R6a card ADJ-15 (G10); full list parameters (G11, L-04, L-05, SH-06 … SH-08); empty names (G12, AA-12, RCW-11); event order (G13, U-38 by id); insufficient-stock texts (G14, CI-10, ST-11); approver row locks (G15, AA-11, RMA-09).
> **Revision:** 3 (2026-11-21) — spec G16: `_apply_item_completion` R8 restated; AIC-10 is the storage source (ledger row, no activity), new AIC-11 the machine source (activity on that machine). G17: AI-01 expects `Added 2 Bolt`. New V-17 covers `void_work_order` R4 with a live line never consumed (branch 1318->1317).
> **Revision:** 4 (2026-11-21) — verifier NEEDS WORK (F-1, F-2, F-4 and the case-missing survivors): LA-05 restated as a strict statement check, GI-05 retired (no non-strict card is left); lock convention tightened to "locks first `work_orders`" (F18, F20) in every lock card; new ADJ-16 … ADJ-21 (decrease after re-averaging, increase by 3, down to 1, no old total, machine source up and down); AIC-06 / AIC-08 pin the Replace activity texts; new U-77 … U-80 (null with a change, `assigned_to` not sent, account / required approvals / component logged), UI-24, RI-11, CT-24 (template slot), CAP-15 and CAP-02 Then 5 (started text), L-06 and SH-09 (signature defaults). Cards that need spec G18 (performers, ledger source, fallback cost, damaged-stock factory) are listed under Spec gaps as pending describer.
> **Revision:** 5 (2026-11-21) — spec G18 / G19 applied. New pass cards ADJ-22 (adjust down with no unit cost at 0.00), AIC-12 (damaged stock to the order's factory: source, machine factory and order factory all differ), AIC-13 … AIC-15 (Install, Replace-in, Borrow return at 0.00 with no unit cost), ST-22, CAP-16, FC-24, V-18 (performer = the caller, not the creator or the worker; `recorded_by`). Restated: ADJ-11, ADJ-18, ADJ-20, ADJ-21, AIC-06, AIC-08, AIC-10, AIC-11 pin the full notes and activity types (G19); RIC-01, ADJ-07, AIC-05 add ledger source and performer; SMS-01 adds the status row's performer. Spec gaps closed.
> **Counts:** 571 cases · 470 expected-to-pass · 101 expected-to-fail (bugs) · 10 deferred

## Reviewer summary
- **Depth:** full (step 1a): the module moves stock, changes order state and approvals, and decides who may edit cost and account.
- **Per callable:** pure helpers (`_is_locked` … `_derive_default_title`) 45 · `create_work_order` 38 (12 bug) · `create_work_order_from_template` 24 (3 bug) · `update_work_order` 80 (25 bug) · `get_work_order` 4 (2 bug) · `list_work_orders` 6 (1 bug) · `bulk_delete_future_recurrence_drafts` 5 (1 bug) · `delete_work_order` 10 · `list_approvers` 5 (1 bug) · `approval_summary` 6 · `approvals_met` 1 · `reset_approvals` 3 · `_recompute_approval_status` 5 · `add_approver` 12 (2 bug) · `remove_approver` 11 (3 bug) · `set_approval` 15 (5 bug) · `log_event` 7 (3 bug) · `list_events` 2 · `_consume_item` 16 (3 bug) · `_reverse_item_consumption` 4 · `_adjust_consumed_item_quantity` 22 (2 bug) · `_apply_item_completion` 15 · `_set_machine_status` 6 (1 bug) · `_previous_machine_status` 3 · `start_work_order` 22 (3 bug) · `_planned_date_noon_utc` 1 · `_run_start_side_effects` 2 · `_ensure_active_workspace_member` 3 · `_sync_assignees_from_text` 3 · `_resolve_completion_workers` 11 (1 bug) · `complete_as_planned` 16 (1 bug) · `finalize_completion` 23 (1 bug) · `void_work_order` 18 (3 bug) · `_ensure_catalog_item_not_on_wo` 2 · `_guard_item_mutations` 3 · `add_item` 38 (11 bug) · `update_item` 24 (7 bug) · `remove_item` 11 (1 bug) · `get_items` 4 (2 bug) · `_apply_sheet_entry_lines` 6 (1 bug) · `sheet_entry` 19 (6 bug) · `sync_recurrence_drafts_for_machine` 2 · `_maybe_seed_template_recurrence` 9 · sheet lists 9.
- **Notable design choices:**
  - **BUG-664 trap (spec Notes):** every stock bucket is seeded with one opening ledger row dated in the past (T0); no Given ever posts stock. Multi-step states (consumed, adjusted, started) are built directly as rows, so each When posts at most twice to one bucket (only CAP-03, a Borrow line out and back), and every posting reads one unique newest ledger row. The spec's "consume 3 → adjust to 4 → void" example is V-11, built from the adjusted state.
  - **Owner answers (2026-11-21):** BUG-2929 (U-42 … U-44 xfail; U-45 … U-47 pass edges: voided invoice, same value, no invoice), BUG-2930 (U-51 … U-53 xfail; U-54 … U-56 pass: another machine, Consume-only, deleted line; FC-21 builds the no-machine order directly), BUG-2931 (AA-05, RMA-04, SA-09/10, U-22/23 xfail; SA-11 pass: 403 still first), OQ-59 zero value (AIC-06/07 pass).
  - **Locks (BUG-2916):** one statement-recorder card per method (SA, AA, RMA, ST, CAP, V, AI, UI, RI), strict xfail on `FOR UPDATE` on the first `SELECT` of `work_orders`, before the state check and any write ("locks first", tightened in Revision 4 after verifier F18 / F20). `finalize_completion` takes no lock of its own (R18, G9); its lock card belongs to the work order service (Deferred). The two-transaction race is deferred.
  - **Schemas:** BUG-2912 / 2913 / 2918 are tested by building the schema directly, with pass cards on the edges that stay valid (0, 0.01, 13 digits, `required_approvals` 0 / None).
  - **Event texts with quantities** are pinned in full per the spec Notes (G3): integers in stock and activity texts; `update_item` R5 renders `str(Decimal)`, pinned by expiring the line first (UI-08).
  - **BUG-1040:** stored unit costs have 2 decimals (G10), so the rounding is observable only in the re-averaging division of `_adjust_consumed_item_quantity` (ADJ-09, ADJ-15).
  - Every update card starts from a **stamped** order, so the approval recompute adds no event the card did not ask for.
- **Needs a decision:** None. All 15 gaps of revision 1 were closed by the describer (spec Gap log); see Spec gaps.

## Conventions for this module

**IDs.** `WOM` = `app/managers/work_order_manager.py`. `LK` _is_locked · `HRA` _has_recorded_approvals · `IA` is_approvable · `GAP` approvability_gap_reason · `FSV` _format_scalar_value · `VAR` _variance_vs_planned · `SMA` _schedule_metadata_for_actual · `SWM` _started_worker_metadata · `CFC` _collect_field_changes · `TN` _work_order_type_name · `RIA` resolve_invoice_account_id · `DT` _derive_default_title · `C` create_work_order · `CT` create_work_order_from_template · `U` update_work_order · `G` get_work_order · `L` list_work_orders · `BD` bulk_delete_future_recurrence_drafts · `D` delete_work_order · `LA` list_approvers · `AS` approval_summary · `AM` approvals_met · `RA` reset_approvals · `RAS` _recompute_approval_status · `AA` add_approver · `RMA` remove_approver · `SA` set_approval · `CI` _consume_item · `RIC` _reverse_item_consumption · `ADJ` _adjust_consumed_item_quantity · `AIC` _apply_item_completion · `SMS` _set_machine_status · `PMS` _previous_machine_status · `ST` start_work_order · `PN` _planned_date_noon_utc · `RSE` _run_start_side_effects · `EAM` _ensure_active_workspace_member · `SAT` _sync_assignees_from_text · `RCW` _resolve_completion_workers · `CAP` complete_as_planned · `FC` finalize_completion · `V` void_work_order · `ECI` _ensure_catalog_item_not_on_wo · `GIM` _guard_item_mutations · `AI` add_item · `UI` update_item · `RI` remove_item · `GI` get_items · `ASL` _apply_sheet_entry_lines · `SE` sheet_entry · `SRD` sync_recurrence_drafts_for_machine · `MSR` _maybe_seed_template_recurrence · `SH` list_sheet_orders / count_sheet_orders / sheet_daily_counts · `LE` log_event · `LEV` list_events · `SCH` the schemas (target `schema`).

**Actors and fixed values.**
- `WOM` = `from app.managers.work_order_manager import work_order_manager as WOM`. `db` = the test's real session, first positional argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- Models = the class of that name in `app.models.<snake_case name>` (`WorkOrder`, `WorkOrderItem`, `WorkOrderApprover`, `WorkOrderAssignee`, `WorkOrderCompleter`, `WorkOrderEvent`, `WorkOrderType`, `WorkOrderTemplate`, `WorkOrderTemplateItem`, `WorkOrderTemplateApprover`, `Factory`, `Machine`, `Item`, `Account`, `AccountInvoice`, `Inventory`, `InventoryLedger`, `MachineItem`, `MachineItemLedger`, `MachineActivityEvent`, `Project`, `ProjectComponent`, `ProjectComponentActivityEvent`, `WorkspaceMember`). `WorkOrderPriorityEnum`, `InventoryTypeEnum` (STORAGE = `InventoryTypeEnum.STORAGE`, DAMAGED = `InventoryTypeEnum.DAMAGED`), `MachineEventTypeEnum` (`IDLE`, `RUNNING`, `MAINTENANCE`) from `app.models.enums`. Schemas, imported inside each test: `WorkOrderItemCreate`, `WorkOrderItemUpdate` from `app.schemas.work_order_item`; `WorkOrderCreate`, `WorkOrderUpdate`, `WorkOrderVoidRequest`, `WorkOrderSheetEntryCreate`, `WorkOrderSheetItemLine` from `app.schemas.work_order`; `WorkOrderFromTemplateCreate` from `app.schemas.work_order_template` (spec Notes, G1). `HTTPException` (fastapi), `ValidationError` (pydantic), `SimpleNamespace`, `Decimal`, `date`, `datetime`, `patch`, `uuid`, `text` = the usual ones.
- MISSING = `999999999`. TAG = `uuid.uuid4().hex[:8]`, once per test. Y = `datetime.now().year`, read at the start of the test. NEW = `f"WO-{Y}-001"`, the number the first created order of W1 gets.
- NOW = `datetime(2026, 3, 10, 9, 0, 0)`. T0 = `datetime(2026, 1, 5, 8, 0, 0)`. T1 = `datetime(2026, 3, 1, 8, 0, 0)`. D(n) = `date(2026, 3, n)` (D(2), D(9), D(16), D(23) are Mondays). NOON(n) = `datetime(2026, 3, n, 12, 0, 0)`.

**Time.** Every test patches `app.managers.work_order_manager.utcnow` to return NOW (same tz-awareness as `app.utils.time.utcnow`). Not patched: Python column defaults (`work_order_events.created_at`, machine ledger `performed_at`, activity `created_at`) and the database `now()` (inventory ledger `performed_at`). They use the real clock, which is always later than T0 and T1. No card asserts them.

**Standing rows** (every test, no Given line; built and flushed in this order, so within each table W0's rows have lower ids than W1's and W1's lower than W2's).
1. W0, W1, W2 = `make_workspace(db)` ×3. U1 `"Karim Ahmed"`, U2 `"Rahim Uddin"`, U3 `"Sara Khan"`, U4 `"Omar Faruk"`, U5 `"Nadia Islam"` = `make_profile(db, name=…)`.
2. `WorkspaceMember(workspace_id, user_id, role, status, position)`: (W1, U1, `"manager"`, `"active"`, `"Supervisor"`), (W1, U2, `"member"`, `"active"`, None), (W1, U3, `"member"`, `"active"`, None), (W1, U4, `"member"`, `"suspended"`, `"Fitter"`), (W0, U5, `"manager"`, `"active"`, None), (W2, U5, `"manager"`, `"active"`, None). U5 is not in W1.
3. `WorkOrderType(workspace_id, name)`: WT0 (W0, `"Service"`), WT1 (W1, `"Service"`), WT2 (W1, `"Repair"`), WT9 (W2, `"Service"`).
4. `Factory(workspace_id, name, abbreviation)`: F0 (W0, `"Plant Zero"`, `"P0"`), F1 (W1, `"Plant One"`, `"P1"`), F2 (W1, `"Plant Two"`, `"P2"`), F9 (W2, `"Plant Nine"`, `"P9"`).
5. `Machine(workspace_id, factory_id, name)`: M0 (W0, F0, `"Press"`), M1 (W1, F1, `"Lathe 3"`), M2 (W1, F1, `"Lathe 4"`), M3 (W1, F2, `"Pump"`), M9 (W2, F9, `"Press"`).
6. `Item(workspace_id, name, name_normalized, unit="pcs")`: I0 (W0, `"Bolt"`), I1 (W1, `"Bolt"`), I2 (W1, `"Bearing"`), I3 (W1, `"Belt"`), I9 (W2, `"Bolt"`); `name_normalized` = name lower-cased.
7. `Account(workspace_id, name, is_active=True, is_deleted=False)`: A0 (W0), A1 (W1), A9 (W2), all `"Rahman Traders"`; A2 (W1, `"Beta Supplies"`).
8. `Project(workspace_id, factory_id, name, description="Main")`: PJ1 (W1, F1, `"Project One"`), PJ9 (W2, F9, `"Project Nine"`). `ProjectComponent(workspace_id, project_id, name)`: PC1 (W1, PJ1, `"Panel A"`), PC9 (W2, PJ9, `"Panel Z"`).
No order, line, approver, assignee, stock, template, invoice or activity row exists unless the Given builds it.

**Given rows.** Inserted directly (never through `WOM`), flushed one at a time in the order written. After "but", a line lists every column that differs. A line written as code is a step run exactly there.
- **order N** = `WorkOrder(workspace_id=W1.id, work_order_number=f"WO-{TAG}-N", work_order_type_id=WT1.id, title="Service — Lathe 3", factory_id=F1.id, machine_id=M1.id, status="DRAFT", priority=WorkOrderPriorityEnum.MEDIUM, uses_inventory=True, description="Old desc", cost=Decimal("100.00"), planned_date=D(12), created_by=U1.id)`. NUM(O) = `O.work_order_number`.
  - **stamped** = `approved_by U1.id`, `approved_at T0`. **started** = `status "IN_PROGRESS"`, `started_by U1.id`, `started_at T1`, `planned_date D(1)`, plus stamped. **completed** = `status "COMPLETED"`, `completed_at T1`, `completed_by U1.id`. **voided** = `status "VOIDED"`, `voided_at T1`, `voided_by U1.id`, `void_note "Old"`. **gone** = `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`.
- **gone** (factory, type) = `is_deleted True`; (machine, account) = `is_deleted True`, `is_active False`.
- **line(O, I, "q")** = `WorkOrderItem(workspace_id=W1.id, work_order_id=O.id, item_id=I.id, quantity=Decimal("q"), uses_inventory=True, source_location_type="storage", source_location_id=F1.id, action_type="CONSUME", created_by=U1.id)`. **consumed(t)** = `consumed_at T1`, `consumed_by U1.id`, `unit_cost Decimal("2.50")`, `total_cost Decimal("t")`. **gone** (line) = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.
- **approver(O, U)** = `WorkOrderApprover(workspace_id=W1.id, work_order_id=O.id, user_id=U.id, assigned_by=U1.id, assigned_at=T0, approved=False)`. **approved** = `approved True`, `approved_at T0`. **assignee(O, U)** = `WorkOrderAssignee(workspace_id=W1.id, work_order_id=O.id, user_id=U.id)`.
- **event(O, "type", meta, at)** = `WorkOrderEvent(workspace_id=W1.id, work_order_id=O.id, event_type="type", description="Setup", metadata_json=meta, created_at=at)`. **status row(M, "S", at)** = `MachineActivityEvent(workspace_id=W1.id, machine_id=M.id, event_type="status_updated", description="Setup", metadata_json={"status": "S"}, created_at=at)`.
- **S(F, I, q, p)** / **SD(F, I, q, p)** = a STORAGE / DAMAGED bucket exactly as `inventory_movements.cases.md` S(): one `Inventory` row (workspace W1, `qty q`, `avg_price p`) plus one opening `InventoryLedger` row (`qty_after q`, `avg_price_after p`, `performed_at T0`). **MS(M, I, q, p)** = as there: one `MachineItem` row (`qty q`) plus one opening `MachineItemLedger` row (`qty_after q`, `avg_price_after p`, `performed_at T0`).
- **template** = `WorkOrderTemplate(workspace_id=W1.id, template_name="Oil change", work_order_type_id=WT1.id, uses_inventory=False, requires_approval=False, is_active=True, created_by=U1.id)`. **weekly** = `is_recurring True`, `recurrence_type "weekly"`, `recurrence_day 0`. **tline(T, I, "q")** = `WorkOrderTemplateItem(workspace_id=W1.id, work_order_template_id=T.id, item_id=I.id, quantity=Decimal("q"), action_type="CONSUME")`. **tapprover(T, U)** = `WorkOrderTemplateApprover(workspace_id=W1.id, work_order_template_id=T.id, user_id=U.id)`.
- **invoice("s")** = `AccountInvoice(workspace_id=W1.id, account_id=A1.id, invoice_type="receivable", invoice_amount=Decimal("100.00"), invoice_date=date(2026, 3, 1), invoice_status="s")`; other required columns neutral.

**BUG-664 guard** (spec Notes). Stock is seeded only with S / SD / MS (ledger row at T0, in the past), never posted in a Given. A state real code reaches in several steps (consumed, adjusted, started) is built directly as rows. So a When posts at most twice to one bucket (only CAP-03, with a BORROW line), and every posting reads one unique newest ledger row.

**Named checks.**
- **mark** = at the end of the Given, the highest id of `work_order_events`, `machine_activity_events`, `inventory_ledger`, `machine_item_ledger`, `project_component_activity_events` (0 when empty).
- **ev(O)** = `[(e.event_type, e.description) …]` of `WorkOrderEvent` rows with `work_order_id == O.id` and `id > mark`, by id. **evrow(O, "t")** = the one such row with that type.
- **acts(M)** = `[(a.event_type, a.description) …]` of `MachineActivityEvent` rows with `machine_id == M.id`, `id > mark`, by id. **stat(M)** = `[a.metadata_json["status"] …]` of those with `event_type "status_updated"`.
- **led(F, I, TYPE)** / **mled(M, I)** = new (`id > mark`) `InventoryLedger` rows of (W1, TYPE, F, I) / `MachineItemLedger` rows of (W1, M, I), by id. **qty(F, I, TYPE)** = re-read `Inventory.qty` of that bucket. **mqty(M, I)** = re-read `MachineItem.qty`, `Decimal("0")` with no row. **pcacts(C)** = new `ProjectComponentActivityEvent` rows of component C.
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = every column equals its value at the end of the Given.
- **nothing written** = row counts of `work_orders`, `work_order_items`, `work_order_approvers`, `work_order_assignees`, `work_order_completers`, `work_order_events`, `inventory`, `inventory_ledger`, `machine_items`, `machine_item_ledger`, `machine_activity_events`, `project_component_activity_events`, `account_invoices` (all workspaces) equal their values at the end of the Given.
- **session clean** = three asserts directly after the raise, before any re-read: `not db.new`, `not db.dirty`, `not db.deleted`.
- `raises: HTTPException` = plain `with pytest.raises(HTTPException) as exc:` around the call, no savepoint; `exc.value.status_code` / `exc.value.detail` compared with `==` unless the line says "starts with" / "contains". `raises: ValidationError` = around building the schema only; "message contains X" = `X in str(exc.value)`.
- **commit spy** = `sp = db.begin_nested()` directly before the call, inside `with patch.object(db, "commit", wraps=db.commit) as cm:`; "inside" lines first, then `sp.rollback()`, then "after" lines.
- **statement recorder** = the SQL sent from the start of the When is recorded. **A lock clause covers t** when it is `FOR UPDATE` with no `OF`, or `FOR UPDATE OF …` listing t, with no `SKIP LOCKED` / `NOWAIT` (`FOR SHARE` / `FOR NO KEY UPDATE` do not count). **locks first t** (Revision 4) = the **first** recorded `SELECT` whose `FROM` / `JOIN` names table t carries a lock clause that covers t, and it is sent before the first recorded `UPDATE` / `INSERT` / `DELETE`. That first read is the one the order's state is checked on, so a lock taken by a later `SELECT` (after a plain read and the state check) fails, and so does `FOR UPDATE OF work_order_items` on a join that names `work_orders` (verifier variants F20, F18). **locks t** = some recorded `SELECT` naming t carries a lock clause that covers t and is sent before the first recorded `UPDATE` / `INSERT` / `DELETE` (used only for the line row in UI-22, RI-09).
- **PROD(b)** = `patch("app.managers.work_order_manager.settings")` with `ENVIRONMENT = "production"`, `WORK_ORDER_ALLOW_DEV_DELETE = b` (cards marked `Author: claude`).

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`. Write the call and checks exactly as shown, also when a parameter does not exist yet. **Race simulations:** none. **Externals:** `utcnow` (always), `settings` (PROD cards), `datetime.date` (BD-04, BD-05).

**Requests** (each builds the default dict, then updates it with the keywords given, so a keyword replaces a default; `k=None` sends `None`).
- `CR(**k)` = `WorkOrderCreate(**{"work_order_type_id": WT1.id, "factory_id": F1.id, "machine_id": M1.id, **k})`. `CREATE(data)` = `WOM.create_work_order(db, data=data, workspace_id=W1.id, user_id=U1.id)`.
- `FROM(T, **k)` = `WOM.create_work_order_from_template(db, template_id=T.id, workspace_id=W1.id, user_id=U1.id, overrides=WorkOrderFromTemplateCreate(**{"machine_id": M1.id, **k}))`.
- `UP(O, **k)` = `WOM.update_work_order(db, wo_id=O.id, data=WorkOrderUpdate(**k), workspace_id=W1.id, user_id=U2.id)`; only the keywords given are sent (`model_fields_set`).
- `ITEM(O, **k)` = `WorkOrderItemCreate(**{"work_order_id": O.id, "item_id": I1.id, "quantity": Decimal("2"), "uses_inventory": True, "source_location_type": "storage", "source_location_id": F1.id, **k})`. `ADD(data)` = `WOM.add_item(db, data=data, workspace_id=W1.id, user_id=U2.id)`.
- `UIT(L, **k)` = `WOM.update_item(db, item_id=L.id, data=WorkOrderItemUpdate(**k), workspace_id=W1.id, user_id=U2.id)`.
- `SHEET(**k)` = `WorkOrderSheetEntryCreate(**{"machine_id": M1.id, "work_order_type_id": WT1.id, "planned_date": D(12), **k})`. `ENTRY(data)` = `WOM.sheet_entry(db, data=data, workspace_id=W1.id, user_id=U1.id)`.
- `FIN(O, **k)` = `WOM.finalize_completion(db, wo=O, performed_by_user_id=U2.id, **k)`.
## `WorkOrderManager._is_locked`

### WOM-LK-01 — completed and voided are locked
- **Rules:** `_is_locked` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = [WOM._is_locked(SimpleNamespace(status=s)) for s in ["COMPLETED", "VOIDED"]]`.

**Then**
1. returns: `result == [True, True]`.

### WOM-LK-02 — draft, in progress, lower-case and empty text are not locked
- **Rules:** `_is_locked` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = [WOM._is_locked(SimpleNamespace(status=s)) for s in ["DRAFT", "IN_PROGRESS", "completed", ""]]`.

**Then**
1. returns: `result == [False, False, False, False]`.

## `WorkOrderManager._has_recorded_approvals`

### WOM-HRA-01 — one approved approver among two is a recorded approval
- **Rules:** `_has_recorded_approvals` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".
2. approver(O, U2).
3. approver(O, U3), but approved.

**When**
- `result = WOM._has_recorded_approvals(db, O.id, W1.id)`.

**Then**
1. returns: `result is True`.

### WOM-HRA-02 — approvers with no approval, and no approvers, are not recorded approvals
- **Rules:** `_has_recorded_approvals` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".
2. approver(O, U2).
3. P = order "2".

**When**
- `result = (WOM._has_recorded_approvals(db, O.id, W1.id), WOM._has_recorded_approvals(db, P.id, W1.id))`.

**Then**
1. returns: `result == (False, False)`.

### WOM-HRA-03 — approved rows of other workspaces and of the neighbour orders do not count
- **Rules:** `_has_recorded_approvals` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = order "1". O2 = order "2". O3 = order "3".
2. approver(O1, U2), but approved.
3. approver(O3, U2), but approved.
4. approver(O2, U3), but approved, `workspace_id W0.id` (invalid data).
5. approver(O2, U4), but approved, `workspace_id W2.id` (invalid data).

**When**
- `result = WOM._has_recorded_approvals(db, O2.id, W1.id)`.

**Then**
1. returns: `result is False`.

## `WorkOrderManager.is_approvable`

### WOM-IA-01 — a stored order with a title and a factory is approvable
- **Rules:** `is_approvable` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `result = WOM.is_approvable(db, O)`.

**Then**
1. returns: `result is True`.

### WOM-IA-02 — a blank or missing title is not approvable
- **Rules:** `is_approvable` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = [WOM.is_approvable(db, SimpleNamespace(title=t, factory_id=F1.id)) for t in ["   ", None, ""]]`.

**Then**
1. returns: `result == [False, False, False]`.

### WOM-IA-03 — no factory is not approvable
- **Rules:** `is_approvable` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM.is_approvable(db, SimpleNamespace(title="Service", factory_id=None))`.

**Then**
1. returns: `result is False`.

## `WorkOrderManager.approvability_gap_reason`

### WOM-GAP-01 — a blank title is reported first, even with no factory
- **Rules:** `approvability_gap_reason` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = [WOM.approvability_gap_reason(db, SimpleNamespace(title=t, factory_id=None)) for t in ["  ", None]]`.

**Then**
1. returns: `result == ["Work order setup is incomplete", "Work order setup is incomplete"]`.

### WOM-GAP-02 — a title without a factory asks for the factory
- **Rules:** `approvability_gap_reason` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM.approvability_gap_reason(db, SimpleNamespace(title="Service", factory_id=None))`.

**Then**
1. returns: `result == "Set a factory before approvals can proceed"`.

### WOM-GAP-03 — a complete order has no gap
- **Rules:** `approvability_gap_reason` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `result = WOM.approvability_gap_reason(db, O)`.

**Then**
1. returns: `result is None`.

## `WorkOrderManager._format_scalar_value`

### WOM-FSV-01 — None shows as a dash
- **Rules:** `_format_scalar_value` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._format_scalar_value("cost", None)`.

**Then**
1. returns: `result == "—"`.

### WOM-FSV-02 — dates and datetimes show as ISO text
- **Rules:** `_format_scalar_value` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = [WOM._format_scalar_value("planned_date", D(10)), WOM._format_scalar_value("planned_date", datetime(2026, 3, 10, 9, 30, 0))]`.

**Then**
1. returns: `result == ["2026-03-10", "2026-03-10T09:30:00"]`.

### WOM-FSV-03 — a whole Decimal shows without decimals, another is normalised
- **Rules:** `_format_scalar_value` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = [WOM._format_scalar_value("cost", Decimal(v)) for v in ["150.00", "150.50", "0.05", "1000"]]`.

**Then**
1. returns: `result == ["150", "150.5", "0.05", "1000"]`.

### WOM-FSV-04 — an enum shows its value
- **Rules:** `_format_scalar_value` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._format_scalar_value("priority", WorkOrderPriorityEnum.HIGH)`.

**Then**
1. returns: `result == "HIGH"`.

### WOM-FSV-05 — other values are trimmed text; blank text shows as a dash; the field name is not used
- **Rules:** `_format_scalar_value` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = [WOM._format_scalar_value("description", "  Oil  "), WOM._format_scalar_value("description", "   "), WOM._format_scalar_value("required_approvals", 2), WOM._format_scalar_value("cost", "  Oil  ")]`.

**Then**
1. returns: `result == ["Oil", "—", "2", "Oil"]`.

## `WorkOrderManager._variance_vs_planned`

### WOM-VAR-01 — a missing planned date or actual time gives None
- **Rules:** `_variance_vs_planned` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = (WOM._variance_vs_planned(None, NOW), WOM._variance_vs_planned(D(10), None))`.

**Then**
1. returns: `result == (None, None)`.

### WOM-VAR-02 — the same day is on plan, whatever the time of day
- **Rules:** `_variance_vs_planned` R2, R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._variance_vs_planned(D(10), datetime(2026, 3, 10, 23, 59, 0))`.

**Then**
1. returns: `result == {"planned_date": "2026-03-10", "variance_days": 0, "variance_label": "On plan"}`.

### WOM-VAR-03 — one day late is singular
- **Rules:** `_variance_vs_planned` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._variance_vs_planned(D(10), datetime(2026, 3, 11, 0, 30, 0))`.

**Then**
1. returns: `result == {"planned_date": "2026-03-10", "variance_days": 1, "variance_label": "1 day late"}`.

### WOM-VAR-04 — three days late is plural
- **Rules:** `_variance_vs_planned` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._variance_vs_planned(D(10), datetime(2026, 3, 13, 8, 0, 0))`.

**Then**
1. returns: `result == {"planned_date": "2026-03-10", "variance_days": 3, "variance_label": "3 days late"}`.

### WOM-VAR-05 — one day early is negative and singular
- **Rules:** `_variance_vs_planned` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._variance_vs_planned(D(10), datetime(2026, 3, 9, 23, 0, 0))`.

**Then**
1. returns: `result == {"planned_date": "2026-03-10", "variance_days": -1, "variance_label": "1 day early"}`.

### WOM-VAR-06 — a plain date two days early is plural
- **Rules:** `_variance_vs_planned` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._variance_vs_planned(D(10), D(8))`.

**Then**
1. returns: `result == {"planned_date": "2026-03-10", "variance_days": -2, "variance_label": "2 days early"}`.

## `WorkOrderManager._schedule_metadata_for_actual`

### WOM-SMA-01 — without a planned date only the actual time is given
- **Rules:** `_schedule_metadata_for_actual` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._schedule_metadata_for_actual(SimpleNamespace(planned_date=None), NOW, actual_field="started_at")`.

**Then**
1. returns: `result == {"started_at": "2026-03-10T09:00:00"}`.

### WOM-SMA-02 — with a planned date the variance keys are added
- **Rules:** `_schedule_metadata_for_actual` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._schedule_metadata_for_actual(SimpleNamespace(planned_date=D(8)), NOW, actual_field="completed_at")`.

**Then**
1. returns: `result == {"completed_at": "2026-03-10T09:00:00", "planned_date": "2026-03-08", "variance_days": 2, "variance_label": "2 days late"}`.

## `WorkOrderManager._started_worker_metadata`

### WOM-SWM-01 — the assigned text, assignee ids in row order and the starter
- **Rules:** `_started_worker_metadata` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but `assigned_to "Sara Khan, Rahim Uddin"`.
2. assignee(O, U3).
3. assignee(O, U2).

**When**
- `result = WOM._started_worker_metadata(db, O, W1.id, U1.id)`.

**Then**
1. returns: `result == {"assigned_to": "Sara Khan, Rahim Uddin", "assignee_user_ids": [U3.id, U2.id], "started_by_user_id": U1.id}`.

### WOM-SWM-02 — no assigned text and no assignee rows
- **Rules:** `_started_worker_metadata` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".
2. P = order "2".
3. assignee(P, U3).

**When**
- `result = WOM._started_worker_metadata(db, O, W1.id, U2.id)`.

**Then**
1. returns: `result == {"assigned_to": None, "assignee_user_ids": [], "started_by_user_id": U2.id}`.

## `WorkOrderManager._collect_field_changes`

### WOM-CFC-01 — a changed logged field gives one entry; title and updated_by are ignored
- **Rules:** `_collect_field_changes` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `result = WOM._collect_field_changes(db, O, {"title": "Other", "updated_by": U2.id, "description": "New desc"})`.

**Then**
1. returns: `result == [{"field": "description", "label": "Description", "from_value": "Old desc", "to_value": "New desc"}]`.

### WOM-CFC-02 — equal values, also 150.00 against 150, give no entry
- **Rules:** `_collect_field_changes` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but `cost Decimal("150.00")`.

**When**
- `result = WOM._collect_field_changes(db, O, {"cost": Decimal("150"), "description": "Old desc", "planned_date": D(12)})`.

**Then**
1. returns: `result == []`.

### WOM-CFC-03 — entries follow the logged-field order, not the dict's
- **Rules:** `_collect_field_changes` R1, R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but `completion_notes None`.

**When**
- `result = WOM._collect_field_changes(db, O, {"completion_notes": "Done", "priority": WorkOrderPriorityEnum.HIGH, "description": "New desc"})`.

**Then**
1. returns: `[c["field"] for c in result] == ["description", "priority", "completion_notes"]`.
2. returns: `result[1] == {"field": "priority", "label": "Priority", "from_value": "MEDIUM", "to_value": "HIGH"}`.
3. returns: `result[2] == {"field": "completion_notes", "label": "Completion notes", "from_value": "—", "to_value": "Done"}`.

### WOM-CFC-04 — the type change shows type names
- **Rules:** `_collect_field_changes` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `result = WOM._collect_field_changes(db, O, {"work_order_type_id": WT2.id})`.

**Then**
1. returns: `result == [{"field": "work_order_type_id", "label": "Work order type", "from_value": "Service", "to_value": "Repair"}]`.

### WOM-CFC-05 — dates and money are formatted
- **Rules:** `_collect_field_changes` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but `planned_date None`.

**When**
- `result = WOM._collect_field_changes(db, O, {"planned_date": D(14), "cost": Decimal("150.50")})`.

**Then**
1. returns: `result == [{"field": "planned_date", "label": "Planned date", "from_value": "—", "to_value": "2026-03-14"}, {"field": "cost", "label": "Cost", "from_value": "100", "to_value": "150.5"}]`.

## `WorkOrderManager._work_order_type_name`

### WOM-TN-01 — None shows as a dash
- **Rules:** `_work_order_type_name` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._work_order_type_name(db, None, W1.id)`.

**Then**
1. returns: `result == "—"`.

### WOM-TN-02 — a type of the workspace, also a deleted one, gives its name
- **Rules:** `_work_order_type_name` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. WTD = `WorkOrderType(workspace_id=W1.id, name="Overhaul")`, but gone.

**When**
- `result = (WOM._work_order_type_name(db, WT2.id, W1.id), WOM._work_order_type_name(db, WTD.id, W1.id))`.

**Then**
1. returns: `result == ("Repair", "Overhaul")`.

### WOM-TN-03 — a type of W0 or W2, or an unknown id, shows as #id
- **Rules:** `_work_order_type_name` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = [WOM._work_order_type_name(db, t, W1.id) for t in [WT0.id, WT9.id, MISSING]]`.

**Then**
1. returns: `result == [f"#{WT0.id}", f"#{WT9.id}", "#999999999"]`.

## `WorkOrderManager.resolve_invoice_account_id`

### WOM-RIA-01 — a set account is returned
- **Rules:** `resolve_invoice_account_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but `account_id A1.id`.

**When**
- `result = WOM.resolve_invoice_account_id(O)`.

**Then**
1. returns: `result == A1.id`.

### WOM-RIA-02 — no account is refused with 422
- **Rules:** `resolve_invoice_account_id` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1" (no account).

**When**
- `WOM.resolve_invoice_account_id(O)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == "Set an account on the work order before creating an invoice"`.

### WOM-RIA-03 — account id 0 is refused the same way
- **Rules:** `resolve_invoice_account_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `WOM.resolve_invoice_account_id(SimpleNamespace(account_id=0))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == "Set an account on the work order before creating an invoice"`.

## `WorkOrderManager._derive_default_title`

### WOM-DT-01 — a given type name wins over the stored type
- **Rules:** `_derive_default_title` R1, R2, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._derive_default_title(db, W1.id, work_order_type_id=WT1.id, factory_id=F1.id, machine_id=M1.id, project_component_id=None, type_name="Overhaul")`.

**Then**
1. returns: `result == "Overhaul — Lathe 3"`.

### WOM-DT-02 — without a type name (or an empty one) the type's name is used
- **Rules:** `_derive_default_title` R1, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = [WOM._derive_default_title(db, W1.id, work_order_type_id=WT2.id, factory_id=F1.id, machine_id=M1.id, project_component_id=None, type_name=n) for n in [None, ""]]`.

**Then**
1. returns: `result == ["Repair — Lathe 3", "Repair — Lathe 3"]`.

### WOM-DT-03 — a deleted type of the workspace still names the order
- **Rules:** `_derive_default_title` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. WTD = `WorkOrderType(workspace_id=W1.id, name="Overhaul")`, but gone.

**When**
- `result = WOM._derive_default_title(db, W1.id, work_order_type_id=WTD.id, factory_id=F1.id, machine_id=M1.id, project_component_id=None)`.

**Then**
1. returns: `result == "Overhaul — Lathe 3"`.

### WOM-DT-04 — a type of W0 or W2 or an unknown type gives "Work order"
- **Rules:** `_derive_default_title` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = [WOM._derive_default_title(db, W1.id, work_order_type_id=t, factory_id=F1.id, machine_id=M1.id, project_component_id=None) for t in [WT0.id, WT9.id, MISSING]]`.

**Then**
1. returns: `result == ["Work order — Lathe 3", "Work order — Lathe 3", "Work order — Lathe 3"]`.

### WOM-DT-05 — a machine of another workspace shows as Machine #id; a deleted one of W1 by name
- **Rules:** `_derive_default_title` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MD = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Old press")`, but gone.

**When**
- `result = [WOM._derive_default_title(db, W1.id, work_order_type_id=WT1.id, factory_id=F1.id, machine_id=m, project_component_id=None) for m in [M0.id, M9.id, MD.id]]`.

**Then**
1. returns: `result == [f"Service — Machine #{M0.id}", f"Service — Machine #{M9.id}", "Service — Old press"]`.

### WOM-DT-06 — a machine wins over a component
- **Rules:** `_derive_default_title` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._derive_default_title(db, W1.id, work_order_type_id=WT1.id, factory_id=F1.id, machine_id=M2.id, project_component_id=PC1.id)`.

**Then**
1. returns: `result == "Service — Lathe 4"`.

### WOM-DT-07 — a component names the target; one of W2 shows as Component #id (revisit after launch)
- **Rules:** `_derive_default_title` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = [WOM._derive_default_title(db, W1.id, work_order_type_id=WT1.id, factory_id=F1.id, machine_id=None, project_component_id=c) for c in [PC1.id, PC9.id]]`.

**Then**
1. returns: `result == ["Service — Panel A", f"Service — Component #{PC9.id}"]`.

### WOM-DT-08 — without a target the factory names the order; an unknown or foreign factory leaves the type alone
- **Rules:** `_derive_default_title` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = [WOM._derive_default_title(db, W1.id, work_order_type_id=WT1.id, factory_id=f, machine_id=None, project_component_id=None) for f in [F1.id, F0.id, F9.id, MISSING]]`.

**Then**
1. returns: `result == ["Service — Plant One", "Service", "Service", "Service"]`.

## `WorkOrderManager.create_work_order`

### WOM-C-01 — the smallest request makes a numbered draft
- **Rules:** `create_work_order` R4, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = CREATE(CR())`.

**Then**
1. returns: `isinstance(result, WorkOrder)` and `result.id is not None`.
2. re-read result: `workspace_id == W1.id`, `work_order_number == NEW`, `created_by == U1.id`, `status == "DRAFT"`.
3. re-read result: `title == "Service — Lathe 3"`, `priority == WorkOrderPriorityEnum.MEDIUM`, `uses_inventory is True`, `factory_id == F1.id`, `machine_id == M1.id`.
4. re-read result: `description is None`, `cost is None`, `account_id is None`, `planned_date is None`, `end_date is None`, `assigned_to is None`, `project_component_id is None`, `work_order_template_id is None`.
5. count: `work_orders` with `workspace_id == W1.id` has exactly 1 row.

### WOM-C-02 — created and auto-approved events; the creator stamps the approval
- **Rules:** `create_work_order` R6, R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = CREATE(CR())`.

**Then**
1. returns: `result.id is not None`.
2. event: `ev(result) == [("created", f"Work order {NEW} created"), ("auto_approved", "Ready to start — no approval required")]`.
3. event: `evrow(result, "created").metadata_json is None`.
4. re-read result: `approved_by == U1.id`, `approved_at == NOW`.

### WOM-C-03 — a planned date adds a scheduled event between the two
- **Rules:** `create_work_order` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = CREATE(CR(planned_date=D(12)))`.

**Then**
1. returns: `result.id is not None`.
2. event: `ev(result) == [("created", f"Work order {NEW} created"), ("scheduled", "Scheduled for 2026-03-12"), ("auto_approved", "Ready to start — no approval required")]`.
3. event: `evrow(result, "scheduled").metadata_json == {"planned_date": "2026-03-12"}`.

### WOM-C-04 — every other field is stored as sent
- **Rules:** `create_work_order` R3, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = CREATE(CR(description="Fix seal", priority=WorkOrderPriorityEnum.HIGH, planned_date=D(12), end_date=D(14), uses_inventory=False, cost=Decimal("5000.00"), account_id=A1.id))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `description == "Fix seal"`, `priority == WorkOrderPriorityEnum.HIGH`, `planned_date == D(12)`, `end_date == D(14)`.
3. re-read result: `uses_inventory is False`, `cost == Decimal("5000.00")`, `account_id == A1.id`.

### WOM-C-05 — a typed title is trimmed and kept
- **Rules:** `create_work_order` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = CREATE(CR(title="  Fix leaking seal  "))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `title == "Fix leaking seal"`.

### WOM-C-06 — a blank title is derived from type and machine
- **Rules:** `create_work_order` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = CREATE(CR(title="   ", work_order_type_id=WT2.id))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `title == "Repair — Lathe 3"`.

### WOM-C-07 — no title and no target: the factory names the order
- **Rules:** `create_work_order` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = CREATE(CR(machine_id=None))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `title == "Service — Plant One"`, `machine_id is None`.

### WOM-C-08 — assigned text is matched to members and put in the created event
- **Rules:** `create_work_order` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = CREATE(CR(assigned_to="rahim uddin; Ghost"))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `assigned_to == "rahim uddin; Ghost"`.
3. count: `[a.user_id for a in WorkOrderAssignee rows with work_order_id == result.id] == [U2.id]`.
4. event: `evrow(result, "created").metadata_json == {"assigned_to": "rahim uddin; Ghost", "assignee_user_ids": [U2.id]}`.

### WOM-C-09 — an empty assigned text gives no metadata and no assignee rows
- **Rules:** `create_work_order` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = CREATE(CR(assigned_to=""))`.

**Then**
1. returns: `result.id is not None`.
2. event: `evrow(result, "created").metadata_json is None`.
3. count: `work_order_assignees` with `work_order_id == result.id` has 0 rows.

### WOM-C-10 — a factory of W2 is not found
- **Rules:** `create_work_order` R1, Errors
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `CREATE(CR(factory_id=F9.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {F9.id} not found"`.
4. session clean.
5. nothing written.

### WOM-C-11 — a factory of W0 is not found
- **Rules:** `create_work_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `CREATE(CR(factory_id=F0.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {F0.id} not found"`.
4. nothing written.

### WOM-C-12 — an unknown factory is not found
- **Rules:** `create_work_order` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `CREATE(CR(factory_id=MISSING))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
4. nothing written.

### WOM-C-13 — a soft-deleted factory is not found
- **Rules:** `create_work_order` R1a [BUG-2920]
- **Kind:** bug
- **Expect:** xfail BUG-2920
- **Fails today on:** Then 1 (no error is raised: the order is created)

**Given**
1. FD = `Factory(workspace_id=W1.id, name="Old Plant", abbreviation="OP")`, but gone.

**When**
- `CREATE(CR(factory_id=FD.id, machine_id=None))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {FD.id} not found"`.
4. session clean.
5. nothing written.

### WOM-C-14 — a type of W2 is not found
- **Rules:** `create_work_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `CREATE(CR(work_order_type_id=WT9.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order type with ID {WT9.id} not found"`.
4. session clean.
5. nothing written.

### WOM-C-15 — a type of W0 is not found
- **Rules:** `create_work_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `CREATE(CR(work_order_type_id=WT0.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order type with ID {WT0.id} not found"`.
4. nothing written.

### WOM-C-16 — the factory is checked before the type
- **Rules:** `create_work_order` R2 (order of checks)
- **Kind:** error
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `CREATE(CR(factory_id=F9.id, work_order_type_id=WT9.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {F9.id} not found"`.

### WOM-C-17 — the type is checked before the account
- **Rules:** `create_work_order` R2 (order of checks)
- **Kind:** error
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `CREATE(CR(work_order_type_id=WT9.id, account_id=A9.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order type with ID {WT9.id} not found"`.

### WOM-C-18 — a soft-deleted type is not found
- **Rules:** `create_work_order` R2 [BUG-1228]
- **Kind:** bug
- **Expect:** xfail BUG-1228
- **Fails today on:** Then 1 (no error is raised: the order is created)

**Given**
1. WTD = `WorkOrderType(workspace_id=W1.id, name="Overhaul")`, but gone.

**When**
- `CREATE(CR(work_order_type_id=WTD.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order type with ID {WTD.id} not found"`.
4. nothing written.

### WOM-C-19 — an account of W2 is not found
- **Rules:** `create_work_order` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `CREATE(CR(account_id=A9.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Account with ID {A9.id} not found"`.
4. session clean.
5. nothing written.

### WOM-C-20 — an account of W0 is not found
- **Rules:** `create_work_order` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `CREATE(CR(account_id=A0.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Account with ID {A0.id} not found"`.
4. nothing written.

### WOM-C-21 — a soft-deleted account is not found
- **Rules:** `create_work_order` R3 [BUG-2920]
- **Kind:** bug
- **Expect:** xfail BUG-2920
- **Fails today on:** Then 1 (no error is raised: the order is created)

**Given**
1. AD = `Account(workspace_id=W1.id, name="Gone Ltd")`, but gone.

**When**
- `CREATE(CR(account_id=AD.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Account with ID {AD.id} not found"`.
4. nothing written.

### WOM-C-22 — a machine of another factory than the order's is refused
- **Rules:** `create_work_order` R1b [BUG-2921]
- **Kind:** bug
- **Expect:** xfail BUG-2921
- **Fails today on:** Then 1 (no error is raised: the order is created with M3 under F1)

**Given**
1. No rows beyond the standing rows.

**When**
- `CREATE(CR(machine_id=M3.id, factory_id=F1.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Machine Pump belongs to another factory"`.
4. session clean.
5. nothing written.

### WOM-C-23 — a bad type is reported before the machine's factory
- **Rules:** `create_work_order` R1b (after R2)
- **Kind:** error
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `CREATE(CR(machine_id=M3.id, factory_id=F1.id, work_order_type_id=WT9.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order type with ID {WT9.id} not found"`.
4. nothing written.

### WOM-C-24 — a bad account is reported before the machine's factory
- **Rules:** `create_work_order` R1b (after R3)
- **Kind:** error
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `CREATE(CR(machine_id=M3.id, factory_id=F1.id, account_id=A9.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Account with ID {A9.id} not found"`.
4. nothing written.

### WOM-C-25 — machine and component may both be stored (revisit after launch)
- **Rules:** `create_work_order` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = CREATE(CR(project_component_id=PC1.id))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `machine_id == M1.id`, `project_component_id == PC1.id`, `title == "Service — Lathe 3"`.

### WOM-C-26 — a component alone names the order (revisit after launch)
- **Rules:** `create_work_order` R4, R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = CREATE(CR(machine_id=None, project_component_id=PC1.id))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `title == "Service — Panel A"`, `machine_id is None`.

### WOM-C-27 — a machine of W2 is not found
- **Rules:** `create_work_order` R9 [BUG-1016]
- **Kind:** bug
- **Expect:** xfail BUG-1016
- **Fails today on:** Then 1 (no error is raised: M9 is stored)

**Given**
1. No rows beyond the standing rows.

**When**
- `CREATE(CR(machine_id=M9.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
4. nothing written.

### WOM-C-28 — a machine of W0 is not found
- **Rules:** `create_work_order` R9 [BUG-1016]
- **Kind:** bug
- **Expect:** xfail BUG-1016
- **Fails today on:** Then 1 (no error is raised: M0 is stored)

**Given**
1. No rows beyond the standing rows.

**When**
- `CREATE(CR(machine_id=M0.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M0.id} not found"`.
4. nothing written.

### WOM-C-29 — a component of W2 is not found
- **Rules:** `create_work_order` R9 [BUG-1016]
- **Kind:** bug
- **Expect:** xfail BUG-1016
- **Fails today on:** Then 1 (no error is raised: PC9 is stored)

**Given**
1. No rows beyond the standing rows.

**When**
- `CREATE(CR(machine_id=None, project_component_id=PC9.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project component with ID {PC9.id} not found"`.
4. nothing written.

### WOM-C-30 — a soft-deleted machine of W1 is not found
- **Rules:** `create_work_order` R9 [BUG-2920]
- **Kind:** bug
- **Expect:** xfail BUG-2920
- **Fails today on:** Then 1 (no error is raised: the deleted machine is stored)

**Given**
1. MD = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Old press")`, but gone.

**When**
- `CREATE(CR(machine_id=MD.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {MD.id} not found"`.
4. nothing written.

### WOM-C-31 — an end date before the planned date is refused by the create schema
- **Rules:** `create_work_order` R3b [BUG-2926]
- **Kind:** bug
- **Expect:** xfail BUG-2926
- **Fails today on:** Then 1 (nothing raises: the schema accepts the dates and the order would be stored with end 1 May)

**Given**
1. No rows beyond the standing rows.

**When**
- `raises: ValidationError` around building `CR(planned_date=date(2026, 5, 10), end_date=date(2026, 5, 1))` only; the manager is not called (spec R3b, G8: the check lives in `WorkOrderCreate`).

**Then**
1. raises: `ValidationError` (`pydantic.ValidationError`).
2. raises: message contains `"End date cannot be before the planned date"`.
3. count: `work_orders` with `workspace_id == W1.id` has 0 rows.

### WOM-C-32 — an end date equal to the planned date is accepted
- **Rules:** `create_work_order` R3b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = CREATE(CR(planned_date=date(2026, 5, 10), end_date=date(2026, 5, 10)))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `planned_date == date(2026, 5, 10)`, `end_date == date(2026, 5, 10)`.

### WOM-C-33 — create flushes and never commits
- **Rules:** `create_work_order` Side effects
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. No rows beyond the standing rows.

**When**
- commit spy around `result = CREATE(CR())`.

**Then**
1. inside: `result.id is not None`.
2. inside: `cm.call_count == 0`.
3. after: count: `work_orders` with `workspace_id == W1.id` has 0 rows.

### WOM-C-34 — a negative cost is refused by the schema
- **Rules:** `create_work_order` R3a [BUG-2912]
- **Kind:** bug
- **Expect:** xfail BUG-2912
- **Fails today on:** Then 1 (the schema accepts -5)

**Given**
1. No rows beyond the standing rows.

**When**
- build `CR(cost=Decimal("-5"))` (target `schema`; the manager is not called).

**Then**
1. raises: `ValidationError`.
2. raises: message contains `"cost"`.

### WOM-C-35 — cost 0 and no cost are accepted by the schema
- **Rules:** `create_work_order` R3a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = (CR(cost=Decimal("0")), CR(cost=None))` (target `schema`).

**Then**
1. returns: `result[0].cost == Decimal("0")`.
2. returns: `result[1].cost is None`.

### WOM-C-36 — a cost with 3 decimals is refused by the schema
- **Rules:** `create_work_order` R3a [BUG-2913]
- **Kind:** bug
- **Expect:** xfail BUG-2913
- **Fails today on:** Then 1 (the schema accepts 99.999)

**Given**
1. No rows beyond the standing rows.

**When**
- build `CR(cost=Decimal("99.999"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: message contains `"cost"`.

### WOM-C-37 — a cost with 14 integer digits is refused by the schema
- **Rules:** `create_work_order` R3a [BUG-2913]
- **Kind:** bug
- **Expect:** xfail BUG-2913
- **Fails today on:** Then 1 (the schema accepts it)

**Given**
1. No rows beyond the standing rows.

**When**
- build `CR(cost=Decimal("10000000000000"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: message contains `"cost"`.

### WOM-C-38 — the largest cost that fits is accepted by the schema
- **Rules:** `create_work_order` R3a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = CR(cost=Decimal("9999999999999.99"))` (target `schema`).

**Then**
1. returns: `result.cost == Decimal("9999999999999.99")`.

## `WorkOrderManager.create_work_order_from_template`

### WOM-CT-01 — the order takes the template's fields and the machine's factory
- **Rules:** `create_work_order_from_template` R3, R4, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but `priority WorkOrderPriorityEnum.HIGH`, `cost Decimal("300.00")`, `account_id A1.id`, `description "Change oil"`.

**When**
- `result = FROM(T)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `work_order_type_id == WT1.id`, `priority == WorkOrderPriorityEnum.HIGH`, `cost == Decimal("300.00")`, `account_id == A1.id`.
3. re-read result: `factory_id == F1.id`, `machine_id == M1.id`, `title == "Service — Lathe 3"`, `description == "Change oil"`.
4. re-read result: `work_order_template_id == T.id`, `status == "DRAFT"`, `uses_inventory is False`, `planned_date is None`, `assigned_to is None`.
5. count: `work_order_items` with `work_order_id == result.id` has 0 rows.

### WOM-CT-02 — the last event says which template made the order
- **Rules:** `create_work_order_from_template` R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = FROM(T)`.

**Then**
1. returns: `result.id is not None`.
2. event: `ev(result) == [("created", f"Work order {NEW} created"), ("auto_approved", "Ready to start — no approval required"), ("created_from_template", 'Generated from template "Oil change"')]`.
3. event: `evrow(result, "created_from_template").metadata_json == {"work_order_template_id": T.id}`.

### WOM-CT-03 — a machine in another factory files the order under that factory
- **Rules:** `create_work_order_from_template` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = FROM(T, machine_id=M3.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `factory_id == F2.id`, `machine_id == M3.id`, `title == "Service — Pump"`.

### WOM-CT-04 — non-empty overrides win
- **Rules:** `create_work_order_from_template` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but `description "Change oil"`, `assigned_to "Rahim Uddin"`.

**When**
- `result = FROM(T, title="Night shift oil", description="Use 5W-30", assigned_to="Sara Khan", planned_date=D(12))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `title == "Night shift oil"`, `description == "Use 5W-30"`, `assigned_to == "Sara Khan"`, `planned_date == D(12)`.

### WOM-CT-05 — empty-string overrides fall back to the template
- **Rules:** `create_work_order_from_template` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `description "Change oil"`, `assigned_to "Rahim Uddin"`.

**When**
- `result = FROM(T, title="", description="", assigned_to="")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `title == "Service — Lathe 3"`, `description == "Change oil"`, `assigned_to == "Rahim Uddin"`.

### WOM-CT-06 — a template of W2 is not found
- **Rules:** `create_work_order_from_template` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T9 = template, but `workspace_id W2.id`, `work_order_type_id WT9.id`.

**When**
- `FROM(T9)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order template with ID {T9.id} not found"`.
4. nothing written.

### WOM-CT-07 — a template of W0 is not found
- **Rules:** `create_work_order_from_template` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T0x = template, but `workspace_id W0.id`, `work_order_type_id WT0.id`.

**When**
- `FROM(T0x)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order template with ID {T0x.id} not found"`.
4. nothing written.

### WOM-CT-08 — an inactive template is refused
- **Rules:** `create_work_order_from_template` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template, but `is_active False`.

**When**
- `FROM(T)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Template is inactive"`.
4. session clean.
5. nothing written.

### WOM-CT-09 — a machine of W2 is not found
- **Rules:** `create_work_order_from_template` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template.

**When**
- `FROM(T, machine_id=M9.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
4. nothing written.

### WOM-CT-10 — a machine of W0 is not found
- **Rules:** `create_work_order_from_template` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template.

**When**
- `FROM(T, machine_id=M0.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M0.id} not found"`.
4. nothing written.

### WOM-CT-11 — a soft-deleted machine is not found
- **Rules:** `create_work_order_from_template` R2 [BUG-2920]
- **Kind:** bug
- **Expect:** xfail BUG-2920
- **Fails today on:** Then 1 (no error is raised: the order is created on the deleted machine)

**Given**
1. T = template.
2. MD = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Old press")`, but gone.

**When**
- `FROM(T, machine_id=MD.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {MD.id} not found"`.
4. nothing written.

### WOM-CT-12 — template lines become order lines in template order
- **Rules:** `create_work_order_from_template` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, but `uses_inventory True`.
2. TL1 = tline(T, I2, "2"), but `notes "Check"`.
3. TL2 = tline(T, I1, "3"), but `action_type "REPLACE"`, `replaced_item_id I3.id`.

**When**
- `result = FROM(T)`.

**Then**
1. returns: `result.id is not None`.
2. re-read: `[(l.item_id, l.quantity, l.action_type) for l in WorkOrderItem rows with work_order_id == result.id, by id] == [(I2.id, Decimal("2.00"), "CONSUME"), (I1.id, Decimal("3.00"), "REPLACE")]`.
3. re-read: the first line has `notes == "Check"`, `uses_inventory is True`, `source_location_type == "storage"`, `source_location_id == F1.id`, `replaced_item_id is None`.
4. re-read: the second line has `replaced_item_id == I3.id`, `uses_inventory is True`, `source_location_id == F1.id`.

### WOM-CT-13 — a Replace template line with no replaced item fails the call
- **Rules:** `create_work_order_from_template` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template, but `uses_inventory True`.
2. tline(T, I1, "1"), but `action_type "REPLACE"`.

**When**
- `FROM(T)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Select the item being replaced"`.

### WOM-CT-14 — the same item twice on a template fails the call with 409
- **Rules:** `create_work_order_from_template` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template, but `uses_inventory True`.
2. tline(T, I1, "1").
3. tline(T, I1, "2").

**When**
- `FROM(T)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Bolt is already on this order"`.

### WOM-CT-15 — a template that does not use inventory copies no lines
- **Rules:** `create_work_order_from_template` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template (`uses_inventory False`).
2. tline(T, I1, "1").

**When**
- `result = FROM(T)`.

**Then**
1. returns: `result.id is not None`.
2. count: `work_order_items` with `work_order_id == result.id` has 0 rows.

### WOM-CT-16 — approvers of a template that requires approval are copied; the order is no longer approved
- **Rules:** `create_work_order_from_template` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, but `requires_approval True`.
2. tapprover(T, U2).
3. tapprover(T, U3).

**When**
- `result = FROM(T)`.

**Then**
1. returns: `result.id is not None`.
2. re-read: `[(a.user_id, a.assigned_by, a.approved) for a in WorkOrderApprover rows with work_order_id == result.id, by id] == [(U2.id, U1.id, False), (U3.id, U1.id, False)]`.
3. re-read result: `approved_by is None`, `approved_at is None`.
4. event: `[t for t, _ in ev(result)] == ["created", "auto_approved", "approver_added", "approval_revoked", "approver_added", "created_from_template"]`.

### WOM-CT-17 — an approver who is not an active member is skipped
- **Rules:** `create_work_order_from_template` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `requires_approval True`.
2. tapprover(T, U4).
3. tapprover(T, U2).

**When**
- `result = FROM(T)`.

**Then**
1. returns: `result.id is not None`.
2. re-read: `[a.user_id for a in WorkOrderApprover rows with work_order_id == result.id] == [U2.id]`.

### WOM-CT-18 — template approvers who all left: the order is not approved
- **Rules:** `create_work_order_from_template` R9 [BUG-2922]
- **Kind:** bug
- **Expect:** xfail BUG-2922
- **Fails today on:** Then 2 (`required_approvals` is None today; the order is 0 of 0, met)

**Given**
1. T = template, but `requires_approval True`.
2. tapprover(T, U4).

**When**
- `result = FROM(T)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `required_approvals == 1`.
3. re-read result: `approved_at is None`, `approved_by is None`.
4. event: `("approvals_needed", "Template approvers are no longer members — add an approver") in ev(result)`.
5. returns: `WOM.approval_summary(db, result) == (0, 1, False)`.

### WOM-CT-19 — template approvers who all left: no approver row, the draft is still made
- **Rules:** `create_work_order_from_template` R7, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `requires_approval True`.
2. tapprover(T, U4).

**When**
- `result = FROM(T)`.

**Then**
1. returns: `result.id is not None`.
2. count: `work_order_approvers` with `work_order_id == result.id` has 0 rows.
3. re-read result: `status == "DRAFT"`, `work_order_template_id == T.id`.

### WOM-CT-20 — without "requires approval" template approvers are not copied
- **Rules:** `create_work_order_from_template` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template (`requires_approval False`).
2. tapprover(T, U2).

**When**
- `result = FROM(T)`.

**Then**
1. returns: `result.id is not None`.
2. count: `work_order_approvers` with `work_order_id == result.id` has 0 rows.
3. re-read result: `approved_by == U1.id`, `approved_at == NOW`.

### WOM-CT-22 — a template approver listed twice is a conflict that is not swallowed
- **Rules:** `create_work_order_from_template` R8 [BUG-1206]
- **Kind:** bug
- **Expect:** xfail BUG-1206
- **Fails today on:** Then 1 (no error is raised: the second `add_approver` 409 is skipped and the order is made with one approver)

**Given**
1. T = template, but `requires_approval True`.
2. For the whole When, `patch("app.managers.work_order_manager.work_order_template_manager.get_approvers", return_value=[SimpleNamespace(user_id=U2.id, approver_slot=None), SimpleNamespace(user_id=U2.id, approver_slot=None)])` (the unique constraint `uq_wo_template_approver` makes a stored duplicate impossible; spec Notes, G5).

**When**
- `FROM(T)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "User is already an approver for this order"`.

### WOM-CT-23 — a template whose type has an empty name titles the order "Maintenance — <machine>"
- **Rules:** `create_work_order_from_template` R3, R3a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. TE = `WorkOrderType(workspace_id=W1.id, name="")` (an empty name stored directly; spec Notes, G6).
2. T = template, but `work_order_type_id TE.id`.

**When**
- `result = FROM(T)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `title == "Maintenance — Lathe 3"`, `work_order_type_id == TE.id`.

### WOM-CT-24 — a template approver's slot is copied to the order
- **Rules:** `create_work_order_from_template` R7; `add_approver` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, but `requires_approval True`.
2. tapprover(T, U2), but `approver_slot "QA"`.

**When**
- `result = FROM(T)`.

**Then**
1. returns: `result.id is not None`.
2. re-read: `[(a.user_id, a.approver_slot, a.assigned_by) for a in WorkOrderApprover rows with work_order_id == result.id, by id] == [(U2.id, "QA", U1.id)]`.

### WOM-CT-21 — create from template flushes and never commits
- **Rules:** `create_work_order_from_template` Side effects
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. T = template.

**When**
- commit spy around `result = FROM(T)`.

**Then**
1. inside: `result.id is not None`.
2. inside: `cm.call_count == 0`.
3. after: count: `work_orders` with `workspace_id == W1.id` has 0 rows.

## `WorkOrderManager.update_work_order`

### WOM-U-01 — a description change is written, logged and stamped
- **Rules:** `update_work_order` R10, R13, R16, R19
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = UP(O, description="New desc")`.

**Then**
1. returns: `result.id == O.id`.
2. returns: `result._approvals_reset is False`.
3. re-read O: `description == "New desc"`, `updated_by == U2.id`, `title == "Service — Lathe 3"`.
4. event: `ev(O) == [("updated", "Order details updated")]`.
5. event: `evrow(O, "updated").metadata_json == {"changes": [{"field": "description", "label": "Description", "from_value": "Old desc", "to_value": "New desc"}]}`.

### WOM-U-02 — an order of W2 is not found
- **Rules:** `update_work_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order "9", but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `machine_id M9.id`.

**When**
- `UP(O9, description="New desc")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order with ID {O9.id} not found"`.
4. session clean.
5. unchanged: unchanged(O9).

### WOM-U-03 — an order of W0 is not found
- **Rules:** `update_work_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O0 = order "0", but `workspace_id W0.id`, `work_order_type_id WT0.id`, `factory_id F0.id`, `machine_id M0.id`.

**When**
- `UP(O0, description="New desc")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order with ID {O0.id} not found"`.
4. unchanged: unchanged(O0).

### WOM-U-04 — a soft-deleted order is refused
- **Rules:** `update_work_order` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. O = order "1", but stamped, gone.

**When**
- `UP(O, description="New desc")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update a deleted work order"`.
4. session clean.
5. nothing written.

### WOM-U-05 — a title alone is dropped and nothing is written
- **Rules:** `update_work_order` R3, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = UP(O, title="Renamed")`.

**Then**
1. returns: `result.id == O.id`.
2. returns: `result._approvals_reset is False`.
3. session: `not db.dirty`, `not db.new`.
4. unchanged: unchanged(O).
5. nothing written.

### WOM-U-06 — a title sent with a description is still dropped
- **Rules:** `update_work_order` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `title "Fix seal"`.

**When**
- `result = UP(O, title="Renamed", description="New desc")`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `title == "Fix seal"`, `description == "New desc"`.

### WOM-U-07 — a description sent as null is dropped: nothing to do
- **Rules:** `update_work_order` R4, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = UP(O, description=None)`.

**Then**
1. returns: `result.id == O.id`.
2. returns: `result._approvals_reset is False`.
3. unchanged: unchanged(O).
4. nothing written.

### WOM-U-08 — nothing to do on a completed order is not an error
- **Rules:** `update_work_order` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped, completed.

**When**
- `result = UP(O, title="Renamed")`.

**Then**
1. returns: `result.id == O.id`.
2. unchanged: unchanged(O).
3. nothing written.

### WOM-U-09 — a completed order cannot be edited
- **Rules:** `update_work_order` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but stamped, completed.

**When**
- `UP(O, description="New desc")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order is completed and cannot be edited"`.
4. session clean.
5. nothing written.

### WOM-U-10 — a voided order cannot be edited
- **Rules:** `update_work_order` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but stamped, voided.

**When**
- `UP(O, planned_date=D(20))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order is voided and cannot be edited"`.
4. nothing written.

### WOM-U-11 — in progress, the planned date can change and is logged
- **Rules:** `update_work_order` R7, R13
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but started.

**When**
- `result = UP(O, planned_date=D(14))`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `planned_date == D(14)`, `status == "IN_PROGRESS"`, `updated_by == U2.id`.
3. event: `ev(O) == [("updated", "Order details updated"), ("schedule_updated", "Planned date changed")]`.

### WOM-U-12 — in progress, assigned text, end date and completion notes can change
- **Rules:** `update_work_order` R7, R21
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but started.

**When**
- `result = UP(O, assigned_to="Sara Khan", end_date=D(20), completion_notes="Half done")`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `assigned_to == "Sara Khan"`, `end_date == D(20)`, `completion_notes == "Half done"`.

### WOM-U-13 — the in-progress refusal names every locked field
- **Rules:** `update_work_order` R8 [BUG-2924]
- **Kind:** bug
- **Expect:** xfail BUG-2924
- **Fails today on:** Then 3 (today the detail names only target, type, cost and account)

**Given**
1. O = order "1", but started.

**When**
- `UP(O, description="New desc")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order is in progress — type, description, priority, target, cost and account are locked"`.

### WOM-U-14 — in progress, a description edit is refused and nothing is written
- **Rules:** `update_work_order` R7, R8
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started.

**When**
- `UP(O, description="New desc")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: detail starts with `"Work order is in progress — "`.
4. session clean.
5. nothing written.

### WOM-U-15 — in progress, sending the current description is refused too
- **Rules:** `update_work_order` R8 (presence, not change)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started.

**When**
- `UP(O, description="Old desc")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: detail starts with `"Work order is in progress — "`.
4. nothing written.

### WOM-U-16 — in progress, priority is locked
- **Rules:** `update_work_order` R7
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started.

**When**
- `UP(O, priority=WorkOrderPriorityEnum.HIGH)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: detail starts with `"Work order is in progress — "`.
4. nothing written.

### WOM-U-17 — in progress, cost is locked
- **Rules:** `update_work_order` R7
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started.

**When**
- `UP(O, cost=Decimal("200.00"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: detail starts with `"Work order is in progress — "`.
4. nothing written.

### WOM-U-18 — in progress, the account is locked
- **Rules:** `update_work_order` R7
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started.

**When**
- `UP(O, account_id=A1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: detail starts with `"Work order is in progress — "`.
4. nothing written.

### WOM-U-19 — in progress, the machine is locked, also when cleared
- **Rules:** `update_work_order` R7
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started.

**When**
- `UP(O, machine_id=None)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: detail starts with `"Work order is in progress — "`.
4. nothing written.

### WOM-U-20 — in progress, the type is locked
- **Rules:** `update_work_order` R7
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started.

**When**
- `UP(O, work_order_type_id=WT2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: detail starts with `"Work order is in progress — "`.
4. nothing written.

### WOM-U-21 — in progress, the project component is locked
- **Rules:** `update_work_order` R7
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started.

**When**
- `UP(O, project_component_id=PC1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: detail starts with `"Work order is in progress — "`.
4. nothing written.

### WOM-U-22 — in progress, the required approvals are frozen
- **Rules:** `update_work_order` R7a [BUG-2931]
- **Kind:** bug
- **Expect:** xfail BUG-2931
- **Fails today on:** Then 1 (no error is raised: the value is stored)

**Given**
1. O = order "1", but started.

**When**
- `UP(O, required_approvals=2)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work has started — approvals can no longer change"`.
4. session clean.
5. nothing written.

### WOM-U-23 — in progress, required approvals sent as null are refused too
- **Rules:** `update_work_order` R7a [BUG-2931]
- **Kind:** bug
- **Expect:** xfail BUG-2931
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. O = order "1", but started, `required_approvals 1`.

**When**
- `UP(O, required_approvals=None)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work has started — approvals can no longer change"`.
4. nothing written.

### WOM-U-24 — an account of W2 is not found
- **Rules:** `update_work_order` R9
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `UP(O, account_id=A9.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Selected account not found"`.
4. session clean.
5. nothing written.

### WOM-U-25 — an account of W0 is not found
- **Rules:** `update_work_order` R9
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `UP(O, account_id=A0.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Selected account not found"`.
4. nothing written.

### WOM-U-26 — a type of W2 is not found
- **Rules:** `update_work_order` R9
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `UP(O, work_order_type_id=WT9.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Selected work order type not found"`.
4. nothing written.

### WOM-U-27 — a type of W0 is not found
- **Rules:** `update_work_order` R9
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `UP(O, work_order_type_id=WT0.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Selected work order type not found"`.
4. nothing written.

### WOM-U-28 — a soft-deleted type is not found
- **Rules:** `update_work_order` R9 [BUG-1228]
- **Kind:** bug
- **Expect:** xfail BUG-1228
- **Fails today on:** Then 1 (no error is raised: the type is stored)

**Given**
1. O = order "1", but stamped.
2. WTD = `WorkOrderType(workspace_id=W1.id, name="Overhaul")`, but gone.

**When**
- `UP(O, work_order_type_id=WTD.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Selected work order type not found"`.
4. nothing written.

### WOM-U-29 — a soft-deleted account is not found
- **Rules:** `update_work_order` R11 [BUG-2920]
- **Kind:** bug
- **Expect:** xfail BUG-2920
- **Fails today on:** Then 1 (no error is raised: the account is stored)

**Given**
1. O = order "1", but stamped.
2. AD = `Account(workspace_id=W1.id, name="Gone Ltd")`, but gone.

**When**
- `UP(O, account_id=AD.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Selected account not found"`.
4. nothing written.

### WOM-U-30 — a negative cost is refused by WorkOrderUpdate
- **Rules:** `update_work_order` R9a [BUG-2912]
- **Kind:** bug
- **Expect:** xfail BUG-2912
- **Fails today on:** Then 1 (the schema accepts -1)

**Given**
1. No rows beyond the standing rows.

**When**
- build `WorkOrderUpdate(cost=Decimal("-1"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: message contains `"cost"`.

### WOM-U-31 — negative required approvals are refused by WorkOrderUpdate
- **Rules:** `update_work_order` R9a [BUG-2912]
- **Kind:** bug
- **Expect:** xfail BUG-2912
- **Fails today on:** Then 1 (the schema accepts -1)

**Given**
1. No rows beyond the standing rows.

**When**
- build `WorkOrderUpdate(required_approvals=-1)` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: message contains `"required_approvals"`.

### WOM-U-32 — a cost with 3 decimals is refused by WorkOrderUpdate
- **Rules:** `update_work_order` R9a [BUG-2913]
- **Kind:** bug
- **Expect:** xfail BUG-2913
- **Fails today on:** Then 1 (the schema accepts 0.001)

**Given**
1. No rows beyond the standing rows.

**When**
- build `WorkOrderUpdate(cost=Decimal("0.001"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: message contains `"cost"`.

### WOM-U-33 — zero and null approvals and a 2-decimal cost are accepted by WorkOrderUpdate
- **Rules:** `update_work_order` R9a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = (WorkOrderUpdate(required_approvals=0), WorkOrderUpdate(required_approvals=None), WorkOrderUpdate(cost=Decimal("0.01")))` (target `schema`).

**Then**
1. returns: `result[0].required_approvals == 0`.
2. returns: `result[1].required_approvals is None`.
3. returns: `result[2].cost == Decimal("0.01")`.

### WOM-U-34 — an end date before the stored planned date is refused
- **Rules:** `update_work_order` R9b [BUG-2926]
- **Kind:** bug
- **Expect:** xfail BUG-2926
- **Fails today on:** Then 1 (no error is raised: end 11 March is stored)

**Given**
1. O = order "1", but stamped (`planned_date D(12)`).

**When**
- `UP(O, end_date=D(11))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == "End date cannot be before the planned date"`.
4. nothing written.

### WOM-U-35 — a planned date after the stored end date is refused (merged values)
- **Rules:** `update_work_order` R9b [BUG-2926]
- **Kind:** bug
- **Expect:** xfail BUG-2926
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. O = order "1", but stamped, `end_date D(14)`.

**When**
- `UP(O, planned_date=D(20))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == "End date cannot be before the planned date"`.
4. nothing written.

### WOM-U-36 — an end date equal to the planned date is accepted
- **Rules:** `update_work_order` R9b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped (`planned_date D(12)`).

**When**
- `result = UP(O, end_date=D(12))`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `end_date == D(12)`.

### WOM-U-37 — two changes are logged in the logged-field order
- **Rules:** `update_work_order` R10, R13
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = UP(O, priority=WorkOrderPriorityEnum.HIGH, description="New desc")`.

**Then**
1. returns: `result.id == O.id`.
2. event: `[c["field"] for c in evrow(O, "updated").metadata_json["changes"]] == ["description", "priority"]`.

### WOM-U-38 — a details change on an approved draft clears the approvals
- **Rules:** `update_work_order` R12, R18, R19; `reset_approvals` R1, R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but `approved_by U2.id`, `approved_at T0`.
2. A = approver(O, U2), but approved.

**When**
- `result = UP(O, description="New desc")`.

**Then**
1. returns: `result._approvals_reset is True`.
2. re-read A: `approved is False`, `approved_at is None`.
3. re-read O: `approved_by is None`, `approved_at is None`.
4. event: `ev(O) == [("approvals_reset", "Order details edited (1 approval(s) cleared)"), ("updated", "Order details updated"), ("approval_revoked", "No longer meets approval requirements")]` (by id: the write order of spec Notes, G13).

### WOM-U-39 — sending the current description on an approved draft resets nothing
- **Rules:** `update_work_order` R12, R20 [BUG-2915]
- **Kind:** bug
- **Expect:** xfail BUG-2915
- **Fails today on:** Then 2 (today the approval is cleared and `_approvals_reset` is True)

**Given**
1. O = order "1", but `approved_by U2.id`, `approved_at T0`.
2. A = approver(O, U2), but approved.

**When**
- `result = UP(O, description="Old desc")`.

**Then**
1. returns: `result.id == O.id`.
2. returns: `result._approvals_reset is False`.
3. re-read A: `approved is True`, `approved_at == T0`.
4. event: `ev(O) == []`.
5. re-read O: `updated_by is None`.

### WOM-U-40 — sending the current description on a draft logs no change
- **Rules:** `update_work_order` R13 (no change, no event)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = UP(O, description="Old desc")`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `description == "Old desc"`.
3. event: `ev(O) == []`.

### WOM-U-41 — a schedule change on an approved draft keeps the approvals
- **Rules:** `update_work_order` R12 (details only)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but `approved_by U2.id`, `approved_at T0`.
2. A = approver(O, U2), but approved.

**When**
- `result = UP(O, planned_date=D(15))`.

**Then**
1. returns: `result._approvals_reset is False`.
2. re-read A: `approved is True`, `approved_at == T0`.
3. re-read O: `planned_date == D(15)`, `approved_at == T0`.

### WOM-U-42 — with a draft invoice, a new cost is refused
- **Rules:** `update_work_order` R12a [BUG-2929]
- **Kind:** bug
- **Expect:** xfail BUG-2929
- **Fails today on:** Then 1 (no error is raised: the cost becomes 4200.00)

**Given**
1. INV = invoice("draft").
2. O = order "1", but stamped, `cost Decimal("5000.00")`, `account_id A1.id`, `invoice_id INV.id`.

**When**
- `UP(O, cost=Decimal("4200.00"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "This work order has an invoice. Delete the draft invoice first to change the cost or account."`.
4. session clean.
5. nothing written.

### WOM-U-43 — with a confirmed invoice, a new account is refused
- **Rules:** `update_work_order` R12a [BUG-2929]
- **Kind:** bug
- **Expect:** xfail BUG-2929
- **Fails today on:** Then 1 (no error is raised: the account becomes A2)

**Given**
1. INV = invoice("confirmed").
2. O = order "1", but stamped, `account_id A1.id`, `invoice_id INV.id`.

**When**
- `UP(O, account_id=A2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "This work order has an invoice. Delete the draft invoice first to change the cost or account."`.
4. nothing written.

### WOM-U-44 — with a draft invoice, clearing the account is refused
- **Rules:** `update_work_order` R12a [BUG-2929]
- **Kind:** bug
- **Expect:** xfail BUG-2929
- **Fails today on:** Then 1 (no error is raised: the account is cleared)

**Given**
1. INV = invoice("draft").
2. O = order "1", but stamped, `account_id A1.id`, `invoice_id INV.id`.

**When**
- `UP(O, account_id=None)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "This work order has an invoice. Delete the draft invoice first to change the cost or account."`.
4. nothing written.

### WOM-U-45 — with a voided invoice, the cost may change
- **Rules:** `update_work_order` R12a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. INV = invoice("voided").
2. O = order "1", but stamped, `cost Decimal("5000.00")`, `account_id A1.id`, `invoice_id INV.id`.

**When**
- `result = UP(O, cost=Decimal("4200.00"))`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `cost == Decimal("4200.00")`.

### WOM-U-46 — with a draft invoice, resending the same cost is accepted
- **Rules:** `update_work_order` R12a (no change)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. INV = invoice("draft").
2. O = order "1", but stamped, `cost Decimal("5000.00")`, `account_id A1.id`, `invoice_id INV.id`.

**When**
- `result = UP(O, cost=Decimal("5000"))`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `cost == Decimal("5000.00")`, `invoice_id == INV.id`.
3. event: `ev(O) == []`.

### WOM-U-47 — without an invoice the cost change is logged as numbers
- **Rules:** `update_work_order` R12a, R13
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but stamped (`cost Decimal("100.00")`).

**When**
- `result = UP(O, cost=Decimal("4200.50"))`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `cost == Decimal("4200.50")`.
3. event: `evrow(O, "updated").metadata_json == {"changes": [{"field": "cost", "label": "Cost", "from_value": "100", "to_value": "4200.5"}]}`.

### WOM-U-48 — an assigned-text change re-matches workers and logs a workers event
- **Rules:** `update_work_order` R13
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but stamped (`assigned_to None`).

**When**
- `result = UP(O, assigned_to="Sara Khan")`.

**Then**
1. returns: `result.id == O.id`.
2. event: `ev(O) == [("updated", "Order details updated"), ("workers_updated", "Workers updated")]`.
3. event: `evrow(O, "updated").metadata_json == {"changes": [{"field": "assigned_to", "label": "Assigned to", "from_value": "—", "to_value": "Sara Khan"}], "assignee_user_ids": [U3.id]}`.
4. event: `evrow(O, "workers_updated").metadata_json == {"from_value": "—", "to_value": "Sara Khan", "assigned_to": "Sara Khan", "assignee_user_ids": [U3.id]}`.
5. count: `[a.user_id for a in WorkOrderAssignee rows with work_order_id == O.id] == [U3.id]`.

### WOM-U-49 — a planned-date change logs a schedule event
- **Rules:** `update_work_order` R13
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but stamped (`planned_date D(12)`).

**When**
- `result = UP(O, planned_date=D(15))`.

**Then**
1. returns: `result.id == O.id`.
2. event: `ev(O) == [("updated", "Order details updated"), ("schedule_updated", "Planned date changed")]`.
3. event: `evrow(O, "schedule_updated").metadata_json == {"field": "planned_date", "from_value": "2026-03-12", "to_value": "2026-03-15", "changes": [{"field": "planned_date", "label": "Planned date", "from_value": "2026-03-12", "to_value": "2026-03-15"}]}`.

### WOM-U-50 — end date and workers change: the extra events follow the change order
- **Rules:** `update_work_order` R13
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = UP(O, assigned_to="Sara Khan", end_date=D(16))`.

**Then**
1. returns: `result.id == O.id`.
2. event: `ev(O) == [("updated", "Order details updated"), ("schedule_updated", "End date changed"), ("workers_updated", "Workers updated")]`.

### WOM-U-51 — an Install line keeps the machine from being removed
- **Rules:** `update_work_order` R13a [BUG-2930]
- **Kind:** bug
- **Expect:** xfail BUG-2930
- **Fails today on:** Then 1 (no error is raised: the machine is removed)

**Given**
1. O = order "1", but stamped.
2. line(O, I1, "2"), but `action_type "INSTALL"`.

**When**
- `UP(O, machine_id=None)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Remove the Install / Replace / Borrow parts first — they need a machine"`.
4. session clean.
5. nothing written.

### WOM-U-52 — a Replace line keeps the order from moving to a component
- **Rules:** `update_work_order` R13a [BUG-2930]
- **Kind:** bug
- **Expect:** xfail BUG-2930
- **Fails today on:** Then 1 (no error is raised: the machine is replaced by PC1)

**Given**
1. O = order "1", but stamped.
2. line(O, I1, "1"), but `action_type "REPLACE"`, `replaced_item_id I2.id`.

**When**
- `UP(O, project_component_id=PC1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Remove the Install / Replace / Borrow parts first — they need a machine"`.
4. nothing written.

### WOM-U-53 — a Borrow line keeps the machine from being removed
- **Rules:** `update_work_order` R13a [BUG-2930]
- **Kind:** bug
- **Expect:** xfail BUG-2930
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. O = order "1", but stamped.
2. line(O, I3, "1"), but `action_type "BORROW"`.

**When**
- `UP(O, machine_id=None)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Remove the Install / Replace / Borrow parts first — they need a machine"`.
4. nothing written.

### WOM-U-54 — with an Install line, moving to another machine is accepted
- **Rules:** `update_work_order` R13a, R15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. line(O, I1, "2"), but `action_type "INSTALL"`.

**When**
- `result = UP(O, machine_id=M2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `machine_id == M2.id`, `title == "Service — Lathe 4"`.

### WOM-U-55 — with only Consume lines the machine may be removed
- **Rules:** `update_work_order` R4, R13a, R15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. line(O, I1, "2").

**When**
- `result = UP(O, machine_id=None)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `machine_id is None`, `project_component_id is None`, `title == "Service — Plant One"`.

### WOM-U-56 — a deleted Install line does not keep the machine
- **Rules:** `update_work_order` R13a (live lines only)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. line(O, I1, "2"), but `action_type "INSTALL"`, gone.

**When**
- `result = UP(O, machine_id=None)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `machine_id is None`.

### WOM-U-57 — a new machine moves the draft to that machine's factory
- **Rules:** `update_work_order` R13b [BUG-2921]
- **Kind:** bug
- **Expect:** xfail BUG-2921
- **Fails today on:** Then 2 (today `factory_id` stays F1)

**Given**
1. O = order "1", but stamped.

**When**
- `result = UP(O, machine_id=M3.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `factory_id == F2.id`.
3. event: `"Factory" in [c["label"] for c in evrow(O, "updated").metadata_json["changes"]]`.

### WOM-U-58 — a new machine is stored, logged and renames the draft
- **Rules:** `update_work_order` R10, R13, R15
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = UP(O, machine_id=M3.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `machine_id == M3.id`, `title == "Service — Pump"`.
3. event: `{"field": "machine_id", "label": "Machine", "from_value": str(M1.id), "to_value": str(M3.id)} in evrow(O, "updated").metadata_json["changes"]`.

### WOM-U-59 — a machine of W2 is not found
- **Rules:** `update_work_order` R14 [BUG-1016]
- **Kind:** bug
- **Expect:** xfail BUG-1016
- **Fails today on:** Then 1 (no error is raised: M9 is stored)

**Given**
1. O = order "1", but stamped.

**When**
- `UP(O, machine_id=M9.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
4. nothing written.

### WOM-U-60 — a machine of W0 is not found
- **Rules:** `update_work_order` R14 [BUG-1016]
- **Kind:** bug
- **Expect:** xfail BUG-1016
- **Fails today on:** Then 1 (no error is raised: M0 is stored)

**Given**
1. O = order "1", but stamped.

**When**
- `UP(O, machine_id=M0.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M0.id} not found"`.
4. nothing written.

### WOM-U-61 — a component of W2 is not found
- **Rules:** `update_work_order` R14 [BUG-1016]
- **Kind:** bug
- **Expect:** xfail BUG-1016
- **Fails today on:** Then 1 (no error is raised: PC9 is stored)

**Given**
1. O = order "1", but stamped.

**When**
- `UP(O, project_component_id=PC9.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project component with ID {PC9.id} not found"`.
4. nothing written.

### WOM-U-62 — a type change renames the draft
- **Rules:** `update_work_order` R15
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = UP(O, work_order_type_id=WT2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `work_order_type_id == WT2.id`, `title == "Repair — Lathe 3"`.

### WOM-U-63 — a typed title is replaced when the machine changes
- **Rules:** `update_work_order` R15 (✅ Q6)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `title "Fix seal"`.

**When**
- `result = UP(O, machine_id=M2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `title == "Service — Lathe 4"`.

### WOM-U-64 — a typed title survives a description change
- **Rules:** `update_work_order` R15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `title "Fix seal"`.

**When**
- `result = UP(O, description="New desc")`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `title == "Fix seal"`.

### WOM-U-65 — a component replaces the machine (revisit after launch)
- **Rules:** `update_work_order` R4, R15
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = UP(O, project_component_id=PC1.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `machine_id is None`, `project_component_id == PC1.id`, `title == "Service — Panel A"`.

### WOM-U-66 — an account sent as null clears it
- **Rules:** `update_work_order` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `account_id A1.id`.

**When**
- `result = UP(O, account_id=None)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `account_id is None`.

### WOM-U-67 — required approvals sent as null on a draft means "all approvers"
- **Rules:** `update_work_order` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `required_approvals 0`.

**When**
- `result = UP(O, required_approvals=None)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `required_approvals is None`.

### WOM-U-68 — a planned date sent as null clears it
- **Rules:** `update_work_order` R4 [BUG-2919]
- **Kind:** bug
- **Expect:** xfail BUG-2919
- **Fails today on:** Then 2 (today the null is dropped: the date stays 12 March)

**Given**
1. O = order "1", but stamped (`planned_date D(12)`).

**When**
- `result = UP(O, planned_date=None)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `planned_date is None`.

### WOM-U-69 — an end date sent as null clears it
- **Rules:** `update_work_order` R4 [BUG-2919]
- **Kind:** bug
- **Expect:** xfail BUG-2919
- **Fails today on:** Then 2 (today the null is dropped)

**Given**
1. O = order "1", but stamped, `end_date D(14)`.

**When**
- `result = UP(O, end_date=None)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `end_date is None`.

### WOM-U-70 — a cost sent as null clears it on a draft
- **Rules:** `update_work_order` R4 [BUG-2919]
- **Kind:** bug
- **Expect:** xfail BUG-2919
- **Fails today on:** Then 2 (today the null is dropped: cost stays 100.00)

**Given**
1. O = order "1", but stamped.

**When**
- `result = UP(O, cost=None)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `cost is None`.

### WOM-U-71 — resending the stored assigned text re-matches stale assignee rows
- **Rules:** `update_work_order` R17
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `assigned_to "Sara Khan"`.
2. assignee(O, U2).

**When**
- `result = UP(O, assigned_to="Sara Khan")`.

**Then**
1. returns: `result.id == O.id`.
2. count: `[a.user_id for a in WorkOrderAssignee rows with work_order_id == O.id] == [U3.id]`.
3. event: `ev(O) == []`.

### WOM-U-72 — lowering required approvals to the approved count stamps the draft
- **Rules:** `update_work_order` R18; `_recompute_approval_status` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1" (not stamped, `required_approvals None`).
2. approver(O, U2), but approved.
3. approver(O, U3).

**When**
- `result = UP(O, required_approvals=1)`.

**Then**
1. returns: `result._approvals_reset is False`.
2. re-read O: `required_approvals == 1`, `approved_by == U2.id`, `approved_at == NOW`.
3. event: `ev(O) == [("updated", "Order details updated"), ("approved", "All required approvals collected")]`.

### WOM-U-73 — raising required approvals above the approved count revokes the stamp
- **Rules:** `update_work_order` R18; `_recompute_approval_status` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. approver(O, U2), but approved.

**When**
- `result = UP(O, required_approvals=2)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `required_approvals == 2`, `approved_by is None`, `approved_at is None`.
3. event: `ev(O) == [("updated", "Order details updated"), ("approval_revoked", "No longer meets approval requirements")]`.

### WOM-U-74 — a request that changes nothing writes no updated_by
- **Rules:** `update_work_order` R20 [BUG-2915]
- **Kind:** bug
- **Expect:** xfail BUG-2915
- **Fails today on:** Then 2 (today `updated_by` is stamped U2)

**Given**
1. O = order "1", but stamped (`updated_by None`).

**When**
- `result = UP(O, description="Old desc", priority=WorkOrderPriorityEnum.MEDIUM)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `updated_by is None`.
3. event: `ev(O) == []`.

### WOM-U-75 — completion notes may be set on a draft and are logged
- **Rules:** `update_work_order` R21, R13
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = UP(O, completion_notes="Parts ordered")`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `completion_notes == "Parts ordered"`.
3. event: `evrow(O, "updated").metadata_json == {"changes": [{"field": "completion_notes", "label": "Completion notes", "from_value": "—", "to_value": "Parts ordered"}]}`.

### WOM-U-76 — update flushes and never commits
- **Rules:** `update_work_order` Side effects
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order "1", but stamped.

**When**
- commit spy around `result = UP(O, description="New desc")`.

**Then**
1. inside: `result.id == O.id`.
2. inside: `cm.call_count == 0`.
3. after: re-read O: `description == "Old desc"`.

### WOM-U-77 — a null for an ordinary field sent with a real change is dropped
- **Rules:** `update_work_order` R4, R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = UP(O, description=None, priority=WorkOrderPriorityEnum.HIGH)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `description == "Old desc"`, `priority == WorkOrderPriorityEnum.HIGH`.
3. event: `ev(O) == [("updated", "Order details updated")]`.
4. event: `evrow(O, "updated").metadata_json == {"changes": [{"field": "priority", "label": "Priority", "from_value": "MEDIUM", "to_value": "HIGH"}]}`.

### WOM-U-78 — assigned text not sent: assignee rows stay as they are
- **Rules:** `update_work_order` R13, R17
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `assigned_to "Sara Khan"`.
2. assignee(O, U2) (out of step with the text on purpose).

**When**
- `result = UP(O, description="New desc")`.

**Then**
1. returns: `result.id == O.id`.
2. count: `[a.user_id for a in WorkOrderAssignee rows with work_order_id == O.id] == [U2.id]`.
3. event: `evrow(O, "updated").metadata_json == {"changes": [{"field": "description", "label": "Description", "from_value": "Old desc", "to_value": "New desc"}]}` (no `assignee_user_ids` key).

### WOM-U-79 — account and required-approvals changes are logged with their labels
- **Rules:** `update_work_order` R4, R13; `_collect_field_changes` R1, R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `account_id None`, `required_approvals None`.

**When**
- `result = UP(O, account_id=A2.id, required_approvals=0)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `account_id == A2.id`, `required_approvals == 0`.
3. event: `ev(O)[0] == ("updated", "Order details updated")`.
4. event: `evrow(O, "updated").metadata_json == {"changes": [{"field": "account_id", "label": "Account", "from_value": "—", "to_value": str(A2.id)}, {"field": "required_approvals", "label": "Required approvals", "from_value": "—", "to_value": "0"}]}`.

### WOM-U-80 — a component change logs the cleared machine and the component (revisit after launch)
- **Rules:** `update_work_order` R4, R13; `_collect_field_changes` R1, R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = UP(O, project_component_id=PC1.id)`.

**Then**
1. returns: `result.id == O.id`.
2. event: `evrow(O, "updated").metadata_json == {"changes": [{"field": "machine_id", "label": "Machine", "from_value": str(M1.id), "to_value": "—"}, {"field": "project_component_id", "label": "Project component", "from_value": "—", "to_value": str(PC1.id)}]}`.

## `WorkOrderManager.get_work_order`

### WOM-G-01 — an order of the workspace is returned
- **Rules:** `get_work_order` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `result = WOM.get_work_order(db, O.id, W1.id)`.

**Then**
1. returns: `result.id == O.id`.

### WOM-G-02 — orders of W0 and W2 and an unknown id are not found
- **Rules:** `get_work_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O0 = order "0", but `workspace_id W0.id`, `work_order_type_id WT0.id`, `factory_id F0.id`, `machine_id M0.id`.
2. O9 = order "9", but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `machine_id M9.id`.

**When**
- `result = []`; for `i in [O0.id, O9.id, MISSING]`: call `WOM.get_work_order(db, i, W1.id)` inside `pytest.raises(HTTPException)` and append `(exc.value.status_code, exc.value.detail)`.

**Then**
1. returns: `result == [(404, f"Work order with ID {O0.id} not found"), (404, f"Work order with ID {O9.id} not found"), (404, "Work order with ID 999999999 not found")]`.

### WOM-G-03 — a soft-deleted order is not found by default
- **Rules:** `get_work_order` R2 [BUG-1279]
- **Kind:** bug
- **Expect:** xfail BUG-1279
- **Fails today on:** Then 1 (no error is raised: the deleted order is returned)

**Given**
1. O = order "1", but gone.

**When**
- `WOM.get_work_order(db, O.id, W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order with ID {O.id} not found"`.

### WOM-G-04 — include_deleted returns a soft-deleted order
- **Rules:** `get_work_order` R2 [BUG-1279]
- **Kind:** bug
- **Expect:** xfail BUG-1279
- **Fails today on:** Then 1 (the call raises TypeError: no `include_deleted` parameter)

**Given**
1. O = order "1", but gone.

**When**
- `result = WOM.get_work_order(db, O.id, W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == O.id`.

## `WorkOrderManager.list_work_orders`

### WOM-L-01 — the list is the DAO list of live W1 orders, newest first
- **Rules:** `list_work_orders` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = order "1", but `created_at T0`.
2. O2 = order "2", but `created_at T1`.
3. OG = order "3", but gone.
4. O9 = order "9", but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `machine_id M9.id`.

**When**
- `result = WOM.list_work_orders(db, workspace_id=W1.id)`.

**Then**
1. returns: `[o.id for o in result] == [O2.id, O1.id]`.

### WOM-L-02 — wo_status filters by status
- **Rules:** `list_work_orders` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order "1".
2. O2 = order "2", but started.

**When**
- `result = WOM.list_work_orders(db, workspace_id=W1.id, wo_status="IN_PROGRESS")`.

**Then**
1. returns: `[o.id for o in result] == [O2.id]`.

### WOM-L-03 — the list query ends its order with the id
- **Rules:** `list_work_orders` R1 [BUG-2670]
- **Kind:** bug
- **Expect:** xfail BUG-2670
- **Fails today on:** Then 2 (the SQL orders by `created_at DESC` only)

**Given**
1. O1 = order "1".
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = WOM.list_work_orders(db, workspace_id=W1.id)`.

**Then**
1. returns: `[o.id for o in result] == [O1.id]`.
2. statement: the recorded `SELECT` naming `work_orders` has an `ORDER BY` part that contains `"work_orders.id DESC"` after `"work_orders.created_at DESC"`.

### WOM-L-04 — every other filter is passed by keyword to the DAO
- **Rules:** `list_work_orders` R1 (parameter list, G11)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. O1 = order "1", but `work_order_type_id WT2.id`, `priority WorkOrderPriorityEnum.HIGH`, `work_order_template_id T.id`.
3. O2 = order "2".
4. O3 = order "3", but `work_order_type_id WT2.id`, `priority WorkOrderPriorityEnum.HIGH`, `work_order_template_id T.id`, `factory_id F2.id`, `machine_id M3.id`.

**When**
- `result = WOM.list_work_orders(db, workspace_id=W1.id, work_order_type_id=WT2.id, priority=WorkOrderPriorityEnum.HIGH, factory_id=F1.id, machine_id=M1.id, work_order_template_id=T.id, planned_date_from=D(10), planned_date_to=D(14), skip=0, limit=10)`.

**Then**
1. returns: `[o.id for o in result] == [O1.id]`.

### WOM-L-05 — skip and limit page the newest-first list
- **Rules:** `list_work_orders` R1 (parameter list, G11)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order "1", but `created_at datetime(2026, 1, 1, 8, 0, 0)`.
2. O2 = order "2", but `created_at datetime(2026, 2, 1, 8, 0, 0)`.
3. O3 = order "3", but `created_at datetime(2026, 3, 1, 8, 0, 0)`.

**When**
- `result = WOM.list_work_orders(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `[o.id for o in result] == [O2.id]`.

### WOM-L-06 — the list's paging defaults are skip 0 and limit 100
- **Rules:** `list_work_orders` (signature, G11)
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. No rows beyond the standing rows. `import inspect`.

**When**
- `result = inspect.signature(WOM.list_work_orders).parameters`.

**Then**
1. returns: `result["limit"].default == 100`.
2. returns: `result["skip"].default == 0`.

## `WorkOrderManager.bulk_delete_future_recurrence_drafts`

### WOM-BD-01 — live drafts of the template and machine after the cutoff are soft-deleted
- **Rules:** `bulk_delete_future_recurrence_drafts` R1, R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but weekly. T2 = template, but `template_name "Greasing"`.
2. A = order "a", but `work_order_template_id T.id`, `planned_date D(12)`.
3. B = order "b", but `work_order_template_id T.id`, `planned_date D(11)`.
4. ON = order "c", but `work_order_template_id T.id`, `planned_date D(10)`.
5. IP = order "d", but started, `work_order_template_id T.id`, `planned_date D(13)` (this date replaces the one in started).
6. OM = order "e", but `work_order_template_id T.id`, `planned_date D(14)`, `machine_id M2.id`.
7. OT = order "f", but `work_order_template_id T2.id`, `planned_date D(15)`.

**When**
- `result = WOM.bulk_delete_future_recurrence_drafts(db, workspace_id=W1.id, user_id=U2.id, work_order_template_id=T.id, machine_id=M1.id, after_date=D(10))`.

**Then**
1. returns: `result == [B.id, A.id]`.
2. re-read A: `is_deleted is True`, `deleted_by == U2.id`, `status == "DRAFT"`.
3. re-read B: `is_deleted is True`, `deleted_by == U2.id`.
4. unchanged: unchanged(ON).
5. unchanged: unchanged(IP).
6. unchanged: unchanged(OM).
7. unchanged: unchanged(OT).
8. count: `work_order_events` has 0 rows with id > mark.

### WOM-BD-02 — nothing to delete returns an empty list
- **Rules:** `bulk_delete_future_recurrence_drafts` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly.
2. ON = order "c", but `work_order_template_id T.id`, `planned_date D(10)`.

**When**
- `result = WOM.bulk_delete_future_recurrence_drafts(db, workspace_id=W1.id, user_id=U2.id, work_order_template_id=T.id, machine_id=M1.id, after_date=D(10))`.

**Then**
1. returns: `result == []`.
2. nothing written.

### WOM-BD-03 — without a cutoff, "today" is the UTC date
- **Rules:** `bulk_delete_future_recurrence_drafts` R1 [BUG-2925]
- **Kind:** bug
- **Expect:** xfail BUG-2925
- **Fails today on:** Then 1 (today the local `date.today()` = 9 March is the cutoff, so the 10 March draft is deleted)
- **Author:** claude

**Given**
1. Patch `datetime.date` with a subclass whose `today()` returns `D(9)` (utcnow stays NOW, 10 March).
2. T = template, but weekly.
3. A = order "a", but `work_order_template_id T.id`, `planned_date D(10)`.

**When**
- `result = WOM.bulk_delete_future_recurrence_drafts(db, workspace_id=W1.id, user_id=U2.id, work_order_template_id=T.id, machine_id=M1.id)`.

**Then**
1. returns: `result == []`.
2. re-read A: `is_deleted is False`.

### WOM-BD-04 — without a cutoff, a draft after both "todays" is deleted
- **Rules:** `bulk_delete_future_recurrence_drafts` R1, R2
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. Patch `datetime.date` with a subclass whose `today()` returns `D(9)` (utcnow stays NOW, 10 March).
2. T = template, but weekly.
3. A = order "a", but `work_order_template_id T.id`, `planned_date D(12)`.

**When**
- `result = WOM.bulk_delete_future_recurrence_drafts(db, workspace_id=W1.id, user_id=U2.id, work_order_template_id=T.id, machine_id=M1.id)`.

**Then**
1. returns: `result == [A.id]`.
2. re-read A: `is_deleted is True`, `deleted_by == U2.id`.

### WOM-BD-05 — bulk delete flushes and never commits
- **Rules:** `bulk_delete_future_recurrence_drafts` R2
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. T = template, but weekly.
2. A = order "a", but `work_order_template_id T.id`, `planned_date D(12)`.

**When**
- commit spy around `result = WOM.bulk_delete_future_recurrence_drafts(db, workspace_id=W1.id, user_id=U2.id, work_order_template_id=T.id, machine_id=M1.id, after_date=D(10))`.

**Then**
1. inside: `result == [A.id]`.
2. inside: `cm.call_count == 0`.
3. after: re-read A: `is_deleted is False`.

## `WorkOrderManager.delete_work_order`

### WOM-D-01 — a draft is soft-deleted, nothing else changes, no event
- **Rules:** `delete_work_order` R4, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = WOM.delete_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `is_deleted is True`, `is_active is False`, `deleted_by == U2.id`, `deleted_at is not None`.
3. re-read O: `status == "DRAFT"`, `updated_by is None`.
4. event: `ev(O) == []`.

### WOM-D-02 — orders of W0 and W2 and an unknown id are not found
- **Rules:** `delete_work_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O0 = order "0", but `workspace_id W0.id`, `work_order_type_id WT0.id`, `factory_id F0.id`, `machine_id M0.id`.
2. O9 = order "9", but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `machine_id M9.id`.

**When**
- `result = []`; for `i in [O0.id, O9.id, MISSING]`: call `WOM.delete_work_order(db, i, W1.id, U2.id)` inside `pytest.raises(HTTPException)` and append `(exc.value.status_code, exc.value.detail)`.

**Then**
1. returns: `result == [(404, f"Work order with ID {O0.id} not found"), (404, f"Work order with ID {O9.id} not found"), (404, "Work order with ID 999999999 not found")]`.
2. unchanged: unchanged(O0).
3. unchanged: unchanged(O9).

### WOM-D-03 — an already deleted order is refused
- **Rules:** `delete_work_order` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. O = order "1", but gone.

**When**
- `WOM.delete_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order is already deleted"`.
4. session clean.
5. unchanged: unchanged(O).

### WOM-D-04 — in production with the switch off, a started order cannot be deleted
- **Rules:** `delete_work_order` R3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. PROD(False).
2. O = order "1", but started.

**When**
- `WOM.delete_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Only a draft work order can be deleted — void it instead"`.
4. unchanged: unchanged(O).

### WOM-D-05 — in production with the switch off, a completed order cannot be deleted
- **Rules:** `delete_work_order` R3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. PROD(False).
2. O = order "1", but completed.

**When**
- `WOM.delete_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Only a draft work order can be deleted — void it instead"`.
4. unchanged: unchanged(O).

### WOM-D-06 — in production, a draft can be deleted
- **Rules:** `delete_work_order` R3, R4
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. PROD(False).
2. O = order "1".

**When**
- `result = WOM.delete_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `is_deleted is True`.

### WOM-D-07 — in production with the switch on, a started order can be deleted
- **Rules:** `delete_work_order` R3, R4
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. PROD(True).
2. O = order "1", but started.

**When**
- `result = WOM.delete_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `is_deleted is True`, `status == "IN_PROGRESS"`.

### WOM-D-08 — outside production a started order is deleted with its stock, lines and approvers untouched
- **Rules:** `delete_work_order` R4 (✅ Q7)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S(F1, I1, 7, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "3"), but consumed(7.50).
4. A = approver(O, U2), but approved.

**When**
- `result = WOM.delete_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `is_deleted is True`, `status == "IN_PROGRESS"`.
3. unchanged: unchanged(L).
4. unchanged: unchanged(A).
5. re-read: `qty(F1, I1, STORAGE) == Decimal("7")`.
6. count: `led(F1, I1, STORAGE) == []`.
7. count: `acts(M1) == []`.

### WOM-D-09 — the manager leaves a linked invoice alone (the BUG-2923 fix is in the service)
- **Rules:** `delete_work_order` R5, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. INV = invoice("draft").
2. O = order "1", but `account_id A1.id`, `invoice_id INV.id`.

**When**
- `result = WOM.delete_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `is_deleted is True`, `invoice_id == INV.id`.
3. unchanged: unchanged(INV).

### WOM-D-10 — delete flushes and never commits
- **Rules:** `delete_work_order` R6
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order "1".

**When**
- commit spy around `result = WOM.delete_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. inside: `result.id == O.id`.
2. inside: `cm.call_count == 0`.
3. after: re-read O: `is_deleted is False`.

## `WorkOrderManager.list_approvers`

### WOM-LA-01 — one tuple per approver with profile and member position
- **Rules:** `list_approvers` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".
2. A1r = approver(O, U1).
3. A2r = approver(O, U2), but `assigned_at T1`.

**When**
- `result = WOM.list_approvers(db, O.id, W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `{r.id: (p.id, pos) for r, p, pos in result} == {A1r.id: (U1.id, "Supervisor"), A2r.id: (U2.id, None)}`.

### WOM-LA-02 — the position is read whatever the membership status; no W1 membership gives None
- **Rules:** `list_approvers` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".
2. A4 = approver(O, U4).
3. A5 = approver(O, U5).

**When**
- `result = WOM.list_approvers(db, O.id, W1.id)`.

**Then**
1. returns: `{r.id: (p.id, pos) for r, p, pos in result} == {A4.id: (U4.id, "Fitter"), A5.id: (U5.id, None)}`.

### WOM-LA-03 — an order of W2 is not found
- **Rules:** `list_approvers` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order "9", but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `machine_id M9.id`.

**When**
- `WOM.list_approvers(db, O9.id, W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order with ID {O9.id} not found"`.

### WOM-LA-04 — approvers come in assignment order
- **Rules:** `list_approvers` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".
2. A1r = approver(O, U2), but `assigned_at T1`.
3. A2r = approver(O, U3), but `assigned_at T0`.

**When**
- `result = WOM.list_approvers(db, O.id, W1.id)`.

**Then**
1. returns: `[r.id for r, _, _ in result] == [A2r.id, A1r.id]`.

### WOM-LA-05 — the approver query breaks ties by id
- **Rules:** `list_approvers` R2 [BUG-1200]
- **Kind:** bug
- **Expect:** xfail BUG-1200
- **Fails today on:** Then 2 (the `ORDER BY` of the approver query has no id tie-break)

**Given**
1. O = order "1".
2. approver(O, U2).
3. Statement recorder on. `db.expunge_all()`.

**When**
- `result = WOM.list_approvers(db, O.id, W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. statement: in the first recorded `SELECT` whose `FROM` names `work_order_approvers`, the text after `ORDER BY` contains `"work_order_approvers.id"` (restated in Revision 4 as a statement check, like GI-04; physical row order is not tested).

## `WorkOrderManager.approval_summary`

### WOM-AS-01 — required defaults to the number of approvers
- **Rules:** `approval_summary` R1, R2, R3, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".
2. approver(O, U2), but approved.
3. approver(O, U3).

**When**
- `result = WOM.approval_summary(db, O)`.

**Then**
1. returns: `result == (1, 2, False)`.

### WOM-AS-02 — every approver approved is met
- **Rules:** `approval_summary` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".
2. approver(O, U2), but approved.
3. approver(O, U3), but approved.

**When**
- `result = WOM.approval_summary(db, O)`.

**Then**
1. returns: `result == (2, 2, True)`.

### WOM-AS-03 — an explicit required count wins over the number of approvers
- **Rules:** `approval_summary` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but `required_approvals 1`.
2. approver(O, U2), but approved.
3. approver(O, U3).

**When**
- `result = WOM.approval_summary(db, O)`.

**Then**
1. returns: `result == (1, 1, True)`.

### WOM-AS-04 — zero required is an explicit waiver
- **Rules:** `approval_summary` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but `required_approvals 0`.
2. approver(O, U2).

**When**
- `result = WOM.approval_summary(db, O)`.

**Then**
1. returns: `result == (0, 0, True)`.

### WOM-AS-05 — an order that never had an approver is 0 of 0, met
- **Rules:** `approval_summary` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `result = WOM.approval_summary(db, O)`.

**Then**
1. returns: `result == (0, 0, True)`.

### WOM-AS-06 — approved rows of W0 and W2 on the order are not counted
- **Rules:** `approval_summary` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order "1".
2. approver(O, U2).
3. approver(O, U3), but approved, `workspace_id W0.id` (invalid data).
4. approver(O, U5), but approved, `workspace_id W2.id` (invalid data).

**When**
- `result = WOM.approval_summary(db, O)`.

**Then**
1. returns: `result == (0, 1, False)`.

## `WorkOrderManager.approvals_met`

### WOM-AM-01 — approvals_met is the summary's met flag
- **Rules:** `approvals_met` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".
2. approver(O, U2).
3. P = order "2".
4. approver(P, U2), but approved.

**When**
- `result = (WOM.approvals_met(db, O), WOM.approvals_met(db, P))`.

**Then**
1. returns: `result == (False, True)`.

## `WorkOrderManager.reset_approvals`

### WOM-RA-01 — approved rows are cleared and one event is logged
- **Rules:** `reset_approvals` R1, R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. A = approver(O, U1), but approved.
3. B = approver(O, U2), but approved.
4. C = approver(O, U3).

**When**
- `result = WOM.reset_approvals(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result is None`.
2. re-read A: `approved is False`, `approved_at is None`.
3. re-read B: `approved is False`, `approved_at is None`.
4. unchanged: unchanged(C).
5. event: `ev(O) == [("approvals_reset", "Section unconfirmed (2 approval(s) cleared)")]`.
6. event: `evrow(O, "approvals_reset").performed_by == U2.id`.
7. re-read O: `approved_by == U1.id`, `approved_at == T0`.

### WOM-RA-02 — a given reason is used in the event
- **Rules:** `reset_approvals` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".
2. approver(O, U2), but approved.

**When**
- `result = WOM.reset_approvals(db, O.id, W1.id, U2.id, reason="Items edited")`.

**Then**
1. returns: `result is None`.
2. event: `ev(O) == [("approvals_reset", "Items edited (1 approval(s) cleared)")]`.

### WOM-RA-03 — nothing approved: nothing written, no event
- **Rules:** `reset_approvals` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".
2. C = approver(O, U3).
3. X = approver(O, U2), but approved, `workspace_id W2.id` (invalid data).

**When**
- `result = WOM.reset_approvals(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result is None`.
2. session: `not db.dirty`.
3. unchanged: unchanged(X).
4. nothing written.

## `WorkOrderManager._recompute_approval_status`

### WOM-RAS-01 — a met draft with no stamp is auto-approved when nothing is required
- **Rules:** `_recompute_approval_status` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1" (not stamped, no approvers).

**When**
- `result = WOM._recompute_approval_status(db, O, W1.id, U2.id)`.

**Then**
1. re-read O: `approved_by == U2.id`, `approved_at == NOW`.
2. event: `ev(O) == [("auto_approved", "Ready to start — no approval required")]`.

### WOM-RAS-02 — a met draft with approvals required is stamped approved
- **Rules:** `_recompute_approval_status` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".
2. approver(O, U2), but approved.

**When**
- `result = WOM._recompute_approval_status(db, O, W1.id, U2.id)`.

**Then**
1. re-read O: `approved_by == U2.id`, `approved_at == NOW`.
2. event: `ev(O) == [("approved", "All required approvals collected")]`.

### WOM-RAS-03 — an unmet stamped draft loses its stamp
- **Rules:** `_recompute_approval_status` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. approver(O, U2).

**When**
- `result = WOM._recompute_approval_status(db, O, W1.id, U2.id)`.

**Then**
1. re-read O: `approved_by is None`, `approved_at is None`.
2. event: `ev(O) == [("approval_revoked", "No longer meets approval requirements")]`.

### WOM-RAS-04 — met and stamped, or unmet and unstamped: nothing
- **Rules:** `_recompute_approval_status` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. P = order "2".
3. approver(P, U2).

**When**
- `result = (WOM._recompute_approval_status(db, O, W1.id, U2.id), WOM._recompute_approval_status(db, P, W1.id, U2.id))`.

**Then**
1. session: `not db.dirty`.
2. unchanged: unchanged(O).
3. unchanged: unchanged(P).
4. nothing written.

### WOM-RAS-05 — only drafts are looked at
- **Rules:** `_recompute_approval_status` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but `status "IN_PROGRESS"` (not stamped, met: no approvers).
2. P = order "2", but completed, stamped.
3. approver(P, U2).

**When**
- `result = (WOM._recompute_approval_status(db, O, W1.id, U2.id), WOM._recompute_approval_status(db, P, W1.id, U2.id))`.

**Then**
1. unchanged: unchanged(O).
2. unchanged: unchanged(P).
3. nothing written.

## `WorkOrderManager.add_approver`

### WOM-AA-01 — an active member is added, logged, and the met draft loses its stamp
- **Rules:** `add_approver` R1, R5, R6, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = WOM.add_approver(db, O.id, U2.id, W1.id, U1.id, approver_slot="QA")`.

**Then**
1. returns: `isinstance(result, WorkOrderApprover)` and `result.id is not None`.
2. re-read result: `work_order_id == O.id`, `user_id == U2.id`, `workspace_id == W1.id`, `approved is False`, `assigned_by == U1.id`, `approver_slot == "QA"`.
3. event: `ev(O) == [("approver_added", "Added Rahim Uddin as approver"), ("approval_revoked", "No longer meets approval requirements")]`.
4. event: `evrow(O, "approver_added").performed_by == U1.id`.
5. event: `evrow(O, "approver_added").metadata_json == {"user_id": U2.id, "user_name": "Rahim Uddin"}`.
6. re-read O: `approved_at is None`.

### WOM-AA-02 — no slot is stored as None
- **Rules:** `add_approver` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `result = WOM.add_approver(db, O.id, U3.id, W1.id, U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `approver_slot is None`, `approved_at is None`.

### WOM-AA-03 — a completed order takes no approver
- **Rules:** `add_approver` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but completed.

**When**
- `WOM.add_approver(db, O.id, U2.id, W1.id, U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order is completed"`.
4. session clean.
5. nothing written.

### WOM-AA-04 — a voided order takes no approver, checked before membership
- **Rules:** `add_approver` R2, R3 (order)
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but voided.

**When**
- `WOM.add_approver(db, O.id, U5.id, W1.id, U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order is voided"`.
4. nothing written.

### WOM-AA-05 — a started order takes no new approver
- **Rules:** `add_approver` R2a [BUG-2931]
- **Kind:** bug
- **Expect:** xfail BUG-2931
- **Fails today on:** Then 1 (no error is raised: the approver is added)

**Given**
1. O = order "1", but started.

**When**
- `WOM.add_approver(db, O.id, U2.id, W1.id, U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work has started — approvals can no longer change"`.
4. session clean.
5. nothing written.

### WOM-AA-06 — a suspended member cannot be an approver
- **Rules:** `add_approver` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `WOM.add_approver(db, O.id, U4.id, W1.id, U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.
4. nothing written.

### WOM-AA-07 — an active member of W0 and W2 only cannot be an approver
- **Rules:** `add_approver` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `WOM.add_approver(db, O.id, U5.id, W1.id, U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.
4. nothing written.

### WOM-AA-08 — the same person twice is a conflict
- **Rules:** `add_approver` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".
2. A = approver(O, U2).

**When**
- `WOM.add_approver(db, O.id, U2.id, W1.id, U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "User is already an approver for this order"`.
4. unchanged: unchanged(A).
5. nothing written.

### WOM-AA-09 — an order of W2 is not found
- **Rules:** `add_approver` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order "9", but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `machine_id M9.id`.

**When**
- `WOM.add_approver(db, O9.id, U2.id, W1.id, U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order with ID {O9.id} not found"`.
4. nothing written.

### WOM-AA-10 — add approver flushes and never commits
- **Rules:** `add_approver` R5
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order "1".

**When**
- commit spy around `result = WOM.add_approver(db, O.id, U2.id, W1.id, U1.id)`.

**Then**
1. inside: `result.id is not None`.
2. inside: `cm.call_count == 0`.
3. after: count: `work_order_approvers` with `work_order_id == O.id` has 0 rows.

### WOM-AA-11 — the order row is locked before its state is checked
- **Rules:** `add_approver` R8 [BUG-2916]
- **Kind:** bug
- **Expect:** xfail BUG-2916
- **Fails today on:** Then 2 (no `FOR UPDATE` is sent)

**Given**
1. O = order "1".
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = WOM.add_approver(db, O.id, U2.id, W1.id, U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. statement: locks first `work_orders`.

### WOM-AA-12 — an approver whose profile name is empty is logged with the empty name
- **Rules:** `add_approver` R6, R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. UE = `make_profile(db, name="")` (an empty name stored directly; spec Notes, G12).
2. `WorkspaceMember(workspace_id=W1.id, user_id=UE.id, role="member", status="active", position=None)`.
3. O = order "1".

**When**
- `result = WOM.add_approver(db, O.id, UE.id, W1.id, U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: `evrow(O, "approver_added").description == "Added  as approver"` (two spaces: the empty name is used as stored).
3. event: `evrow(O, "approver_added").metadata_json == {"user_id": UE.id, "user_name": ""}`.

## `WorkOrderManager.remove_approver`

### WOM-RMA-01 — the row is deleted and logged; the remaining approval meets the order
- **Rules:** `remove_approver` R1, R3, R4, R4a
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".
2. A = approver(O, U2).
3. B = approver(O, U3), but approved.

**When**
- `result = WOM.remove_approver(db, O.id, U2.id, W1.id, performed_by=U1.id)`.

**Then**
1. returns: `result is None`.
2. count: `work_order_approvers` with `id == A.id` has 0 rows.
3. event: `ev(O) == [("approver_removed", "Removed Rahim Uddin as approver"), ("approved", "All required approvals collected")]`.
4. event: `evrow(O, "approver_removed").performed_by == U1.id`.
5. event: `evrow(O, "approver_removed").metadata_json == {"user_id": U2.id, "user_name": "Rahim Uddin"}`.
6. re-read O: `approved_at == NOW`.
7. re-read O: `approved_by == U1.id` (the recompute's actor is `performed_by`, R4a).
8. event: `evrow(O, "approved").performed_by == U1.id`.

### WOM-RMA-02 — no performer is allowed
- **Rules:** `remove_approver` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. approver(O, U2), but approved.
3. approver(O, U3), but approved.

**When**
- `result = WOM.remove_approver(db, O.id, U2.id, W1.id)`.

**Then**
1. returns: `result is None`.
2. event: `ev(O) == [("approver_removed", "Removed Rahim Uddin as approver")]`.
3. event: `evrow(O, "approver_removed").performed_by is None`.

### WOM-RMA-03 — a completed or voided order keeps its approvers
- **Rules:** `remove_approver` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but voided.
2. A = approver(O, U2).

**When**
- `WOM.remove_approver(db, O.id, U2.id, W1.id, performed_by=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order is voided"`.
4. session clean.
5. unchanged: unchanged(A).

### WOM-RMA-04 — a started order keeps its approvers
- **Rules:** `remove_approver` R2a [BUG-2931]
- **Kind:** bug
- **Expect:** xfail BUG-2931
- **Fails today on:** Then 1 (no error is raised: the approver is removed)

**Given**
1. O = order "1", but started.
2. A = approver(O, U2), but approved.

**When**
- `WOM.remove_approver(db, O.id, U2.id, W1.id, performed_by=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work has started — approvals can no longer change"`.
4. unchanged: unchanged(A).
5. nothing written.

### WOM-RMA-05 — someone who is not an approver of this order is not found
- **Rules:** `remove_approver` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".
2. P = order "2".
3. X = approver(P, U2).

**When**
- `WOM.remove_approver(db, O.id, U2.id, W1.id, performed_by=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Approver not found"`.
4. unchanged: unchanged(X).
5. nothing written.

### WOM-RMA-06 — removing the last approver leaves the order unapproved
- **Rules:** `remove_approver` R4; `approval_summary` R4 [BUG-1204]
- **Kind:** bug
- **Expect:** xfail BUG-1204
- **Fails today on:** Then 3 (today the order is 0 of 0, met, and keeps its stamp)

**Given**
1. O = order "1", but `approved_by U2.id`, `approved_at T0`.
2. approver(O, U2), but approved.

**When**
- `result = WOM.remove_approver(db, O.id, U2.id, W1.id, performed_by=U1.id)`.

**Then**
1. returns: `result is None`.
2. count: `work_order_approvers` with `work_order_id == O.id` has 0 rows.
3. returns: `WOM.approval_summary(db, O)[2] is False`.
4. re-read O: `approved_at is None`.

### WOM-RMA-07 — removing the last approver deletes the row and logs it
- **Rules:** `remove_approver` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but `approved_by U2.id`, `approved_at T0`.
2. approver(O, U2), but approved.

**When**
- `result = WOM.remove_approver(db, O.id, U2.id, W1.id, performed_by=U1.id)`.

**Then**
1. returns: `result is None`.
2. count: `work_order_approvers` with `work_order_id == O.id` has 0 rows.
3. event: `ev(O)[0] == ("approver_removed", "Removed Rahim Uddin as approver")`.

### WOM-RMA-08 — remove approver flushes and never commits
- **Rules:** `remove_approver` R3
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order "1".
2. approver(O, U2).
3. approver(O, U3).

**When**
- commit spy around `WOM.remove_approver(db, O.id, U2.id, W1.id, performed_by=U1.id)`.

**Then**
1. inside: count: `work_order_approvers` with `work_order_id == O.id` has 1 row.
2. inside: `cm.call_count == 0`.
3. after: count: `work_order_approvers` with `work_order_id == O.id` has 2 rows.

### WOM-RMA-09 — the order row is locked before its state is checked
- **Rules:** `remove_approver` R5 [BUG-2916]
- **Kind:** bug
- **Expect:** xfail BUG-2916
- **Fails today on:** Then 2 (no `FOR UPDATE` is sent)

**Given**
1. O = order "1".
2. approver(O, U2).
3. approver(O, U3).
4. Statement recorder on. `db.expunge_all()`.

**When**
- `WOM.remove_approver(db, O.id, U2.id, W1.id, performed_by=U1.id)`.

**Then**
1. count: `work_order_approvers` with `work_order_id == O.id` has 1 row.
2. statement: locks first `work_orders`, and that `SELECT … FOR UPDATE` also comes before the first recorded `DELETE`.

### WOM-RMA-10 — without a performer, a removal that meets the order stamps no approver
- **Rules:** `remove_approver` R4, R4a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".
2. approver(O, U2).
3. approver(O, U3), but approved.

**When**
- `result = WOM.remove_approver(db, O.id, U2.id, W1.id)`.

**Then**
1. returns: `result is None`.
2. re-read O: `approved_at == NOW`, `approved_by is None`.
3. event: `evrow(O, "approved").performed_by is None`.

### WOM-RMA-11 — a removal that leaves the order unmet clears the stamp in the performer's name
- **Rules:** `remove_approver` R4, R4a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. approver(O, U2), but approved.
3. approver(O, U3).

**When**
- `result = WOM.remove_approver(db, O.id, U2.id, W1.id, performed_by=U1.id)`.

**Then**
1. returns: `result is None`.
2. re-read O: `approved_by is None`, `approved_at is None`.
3. event: `ev(O) == [("approver_removed", "Removed Rahim Uddin as approver"), ("approval_revoked", "No longer meets approval requirements")]`.
4. event: `evrow(O, "approval_revoked").performed_by == U1.id`.

## `WorkOrderManager.set_approval`

### WOM-SA-01 — approving stamps the row, logs it and approves the order
- **Rules:** `set_approval` R1, R2, R4, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".
2. A = approver(O, U2).

**When**
- `result = WOM.set_approval(db, O.id, U2.id, W1.id, True)`.

**Then**
1. returns: `result.id == A.id`.
2. re-read A: `approved is True`, `approved_at == NOW`.
3. event: `ev(O) == [("approved", "Approved work order"), ("approved", "All required approvals collected")]`.
4. event: the lowest-id `WorkOrderEvent` row of O with `id > mark` has `performed_by == U2.id`.
5. re-read O: `approved_by == U2.id`, `approved_at == NOW`.

### WOM-SA-02 — withdrawing clears the row and revokes the order's stamp
- **Rules:** `set_approval` R3, R4, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but `approved_by U2.id`, `approved_at T0`.
2. A = approver(O, U2), but approved.

**When**
- `result = WOM.set_approval(db, O.id, U2.id, W1.id, False)`.

**Then**
1. returns: `result.id == A.id`.
2. re-read A: `approved is False`, `approved_at is None`.
3. event: `ev(O) == [("approval_withdrawn", "Withdrew approval"), ("approval_revoked", "No longer meets approval requirements")]`.
4. re-read O: `approved_at is None`.

### WOM-SA-03 — someone who is not an approver is forbidden
- **Rules:** `set_approval` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".
2. approver(O, U2).

**When**
- `WOM.set_approval(db, O.id, U3.id, W1.id, True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "You are not an assigned approver for this order"`.
4. session clean.
5. nothing written.

### WOM-SA-04 — an unknown order and an order of W2 answer 403, not 404
- **Rules:** `set_approval` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order "9", but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `machine_id M9.id`.
2. A9 = approver(O9, U2), but `workspace_id W2.id`.

**When**
- `result = []`; for `i in [O9.id, MISSING]`: call `WOM.set_approval(db, i, U2.id, W1.id, True)` inside `pytest.raises(HTTPException)` and append `(exc.value.status_code, exc.value.detail)`.

**Then**
1. returns: `result == [(403, "You are not an assigned approver for this order"), (403, "You are not an assigned approver for this order")]`.
2. unchanged: unchanged(A9).

### WOM-SA-05 — a completed order cannot be approved
- **Rules:** `set_approval` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but completed.
2. A = approver(O, U2).

**When**
- `WOM.set_approval(db, O.id, U2.id, W1.id, True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order is completed"`.
4. unchanged: unchanged(A).
5. nothing written.

### WOM-SA-06 — on a voided order a non-approver still gets 403 first
- **Rules:** `set_approval` R1, R2 (order)
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but voided.

**When**
- `WOM.set_approval(db, O.id, U2.id, W1.id, True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "You are not an assigned approver for this order"`.

### WOM-SA-07 — approving an order with a blank title is refused with the gap reason
- **Rules:** `set_approval` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".
2. A = approver(O, U2).
3. `O.title = "   "` in memory only (not flushed; the session does not autoflush).

**When**
- `WOM.set_approval(db, O.id, U2.id, W1.id, True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order setup is incomplete"`.
4. re-read A: `approved is False`.

### WOM-SA-08 — withdrawing is not checked for approvability
- **Rules:** `set_approval` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".
2. A = approver(O, U2), but approved.
3. `O.title = "   "` in memory only.

**When**
- `result = WOM.set_approval(db, O.id, U2.id, W1.id, False)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.approved is False`.

### WOM-SA-09 — on a started order an approval can no longer be given
- **Rules:** `set_approval` R3a [BUG-2931]
- **Kind:** bug
- **Expect:** xfail BUG-2931
- **Fails today on:** Then 1 (no error is raised: the approval is stored)

**Given**
1. O = order "1", but started.
2. A = approver(O, U2).

**When**
- `WOM.set_approval(db, O.id, U2.id, W1.id, True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work has started — approvals can no longer change"`.
4. unchanged: unchanged(A).
5. nothing written.

### WOM-SA-10 — on a started order an approval can no longer be withdrawn
- **Rules:** `set_approval` R3a [BUG-2931]
- **Kind:** bug
- **Expect:** xfail BUG-2931
- **Fails today on:** Then 1 (no error is raised: the approval is withdrawn)

**Given**
1. O = order "1", but started.
2. A = approver(O, U2), but approved.

**When**
- `WOM.set_approval(db, O.id, U2.id, W1.id, False)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work has started — approvals can no longer change"`.
4. unchanged: unchanged(A).

### WOM-SA-11 — on a started order a non-approver still gets 403
- **Rules:** `set_approval` R1, R3a (order)
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. approver(O, U2).

**When**
- `WOM.set_approval(db, O.id, U3.id, W1.id, True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "You are not an assigned approver for this order"`.

### WOM-SA-12 — approving again writes nothing and logs nothing
- **Rules:** `set_approval` R6 [BUG-2917]
- **Kind:** bug
- **Expect:** xfail BUG-2917
- **Fails today on:** Then 3 (today `approved_at` is re-stamped to NOW)

**Given**
1. O = order "1", but `approved_by U2.id`, `approved_at T0`.
2. A = approver(O, U2), but approved.

**When**
- `result = WOM.set_approval(db, O.id, U2.id, W1.id, True)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.approved is True`.
3. re-read A: `approved_at == T0`.
4. event: `ev(O) == []`.

### WOM-SA-13 — withdrawing an approval that was never given logs nothing
- **Rules:** `set_approval` R6 [BUG-2917]
- **Kind:** bug
- **Expect:** xfail BUG-2917
- **Fails today on:** Then 2 (today an `approval_withdrawn` event is logged)

**Given**
1. O = order "1".
2. A = approver(O, U2).
3. approver(O, U3).

**When**
- `result = WOM.set_approval(db, O.id, U2.id, W1.id, False)`.

**Then**
1. returns: `result.id == A.id`.
2. event: `ev(O) == []`.

### WOM-SA-14 — the order row is locked before its state is checked
- **Rules:** `set_approval` R9 [BUG-2916]
- **Kind:** bug
- **Expect:** xfail BUG-2916
- **Fails today on:** Then 2 (no `FOR UPDATE` is sent)

**Given**
1. O = order "1".
2. approver(O, U2).
3. Statement recorder on. `db.expunge_all()`.

**When**
- `result = WOM.set_approval(db, O.id, U2.id, W1.id, True)`.

**Then**
1. returns: `result.approved is True`.
2. statement: locks first `work_orders`.

### WOM-SA-15 — set approval flushes and never commits
- **Rules:** `set_approval` R4
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order "1".
2. A = approver(O, U2).

**When**
- commit spy around `result = WOM.set_approval(db, O.id, U2.id, W1.id, True)`.

**Then**
1. inside: `result.approved is True`.
2. inside: `cm.call_count == 0`.
3. after: re-read A: `approved is False`.

## `WorkOrderManager.log_event`

### WOM-LE-01 — one event row with the arguments, flushed and returned
- **Rules:** `log_event` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `result = WOM.log_event(db, O.id, W1.id, "note", "Checked oil", performed_by=U2.id, metadata={"k": 1})`.

**Then**
1. returns: `isinstance(result, WorkOrderEvent)` and `result.id is not None`.
2. re-read result: `work_order_id == O.id`, `workspace_id == W1.id`, `event_type == "note"`, `description == "Checked oil"`, `performed_by == U2.id`, `metadata_json == {"k": 1}`.

### WOM-LE-02 — no metadata is stored as JSON null; no performer as None
- **Rules:** `log_event` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `result = WOM.log_event(db, O.id, W1.id, "note", "x")`.

**Then**
1. returns: `result.id is not None`.
2. re-read: `tuple(db.execute(text("SELECT metadata::text, metadata IS NULL FROM work_order_events WHERE id = :i"), {"i": result.id}).one()) == ("null", False)`.
3. re-read result: `performed_by is None`.

### WOM-LE-03 — an order of W2 is refused
- **Rules:** `log_event` R2 [BUG-1192]
- **Kind:** bug
- **Expect:** xfail BUG-1192
- **Fails today on:** Then 1 (no error is raised: the event is stored under W1)

**Given**
1. O9 = order "9", but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `machine_id M9.id`.

**When**
- `WOM.log_event(db, O9.id, W1.id, "note", "x")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order with ID {O9.id} not found"`.
4. nothing written.

### WOM-LE-04 — an order of W0 is refused
- **Rules:** `log_event` R2 [BUG-1192]
- **Kind:** bug
- **Expect:** xfail BUG-1192
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. O0 = order "0", but `workspace_id W0.id`, `work_order_type_id WT0.id`, `factory_id F0.id`, `machine_id M0.id`.

**When**
- `WOM.log_event(db, O0.id, W1.id, "note", "x")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order with ID {O0.id} not found"`.
4. nothing written.

### WOM-LE-05 — order id 0 is refused
- **Rules:** `log_event` R2 [BUG-1192]
- **Kind:** bug
- **Expect:** xfail BUG-1192
- **Fails today on:** Then 1 (today the insert reaches the database: it raises `IntegrityError`, not `HTTPException`)
- **Author:** claude

**Given**
1. No rows beyond the standing rows.

**When**
- `WOM.log_event(db, 0, W1.id, "note", "x")` inside `pytest.raises(HTTPException)` and `db.begin_nested()`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Work order with ID 0 not found"`.

### WOM-LE-06 — a soft-deleted order of the workspace still takes events
- **Rules:** `log_event` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. O = order "1", but gone.

**When**
- `result = WOM.log_event(db, O.id, W1.id, "note", "After delete")`.

**Then**
1. returns: `result.id is not None`.
2. event: `ev(O) == [("note", "After delete")]`.

### WOM-LE-07 — log event flushes and never commits
- **Rules:** `log_event` R1
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order "1".

**When**
- commit spy around `result = WOM.log_event(db, O.id, W1.id, "note", "x")`.

**Then**
1. inside: `result.id is not None`.
2. inside: `cm.call_count == 0`.
3. after: `ev(O) == []`.

## `WorkOrderManager.list_events`

### WOM-LEV-01 — events newest first, each with its performer or None
- **Rules:** `list_events` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".
2. E1 = event(O, "note", None, T0), but `performed_by U2.id`.
3. E2 = event(O, "note", None, T1).
4. P = order "2".
5. EP = event(P, "note", None, NOW).

**When**
- `result = WOM.list_events(db, O.id, W1.id)`.

**Then**
1. returns: `[(e.id, p.id if p else None) for e, p in result] == [(E2.id, None), (E1.id, U2.id)]`.

### WOM-LEV-02 — an order of W2 is not found
- **Rules:** `list_events` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order "9", but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `machine_id M9.id`.

**When**
- `WOM.list_events(db, O9.id, W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order with ID {O9.id} not found"`.

## `WorkOrderManager._consume_item`

### WOM-CI-01 — a storage line leaves stock and is stamped with the posting's cost
- **Rules:** `_consume_item` R4, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "3").

**When**
- `result = WOM._consume_item(db, O, L, U2.id)`.

**Then**
1. re-read: `qty(F1, I1, STORAGE) == Decimal("7")`.
2. re-read: `[(r.transaction_type, r.quantity, r.source_type, r.source_id) for r in led(F1, I1, STORAGE)] == [("consumption", Decimal("3"), "work_order", O.id)]`.
3. re-read: `led(F1, I1, STORAGE)[0].notes == f"{NUM(O)} — Bolt"`.
4. re-read L: `consumed_at == NOW`, `consumed_by == U2.id`, `unit_cost == Decimal("2.50")`, `total_cost == Decimal("7.50")`.

### WOM-CI-02 — on an order with a machine, a "used" activity names the storage source
- **Rules:** `_consume_item` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "3").

**When**
- `result = WOM._consume_item(db, O, L, U2.id)`.

**Then**
1. event: `[t for t, _ in acts(M1)] == ["work_order_item_used"]`.
2. event: the description of that row `== f"Used 3 Bolt from storage for work order {NUM(O)}"`.
3. event: its `metadata_json["item_id"] == I1.id`, `metadata_json["item_name"] == "Bolt"`, `metadata_json["work_order_id"] == O.id`.
4. event: `set(its metadata_json.keys()) == {"item_id", "item_name", "quantity", "work_order_id"}`.
5. event: its `metadata_json["quantity"] == 3` (an integer, spec Notes G3).

### WOM-CI-03 — a machine source line leaves that machine's stock and both activities are logged
- **Rules:** `_consume_item` R4, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. MS(M2, I1, 5, Decimal("4.00")).
2. O = order "1", but started.
3. L = line(O, I1, "3"), but `source_location_type "machine"`, `source_location_id M2.id`.

**When**
- `result = WOM._consume_item(db, O, L, U2.id)`.

**Then**
1. re-read: `mqty(M2, I1) == Decimal("2")`.
2. re-read: `[(r.transaction_type, r.quantity) for r in mled(M2, I1)] == [("consumption", Decimal("3"))]`.
3. event: `[t for t, _ in acts(M2)] == ["consumption"]`.
4. event: the description of that row `== f"Consumed for work order {NUM(O)}: 3 units of Bolt"`.
5. event: the one `acts(M1)` row is `work_order_item_used` and its description `== f"Used 3 Bolt from machine #{M2.id} for work order {NUM(O)}"`.
6. re-read L: `unit_cost == Decimal("4.00")`, `total_cost == Decimal("12.00")`.

### WOM-CI-04 — on an order with no machine no "used" activity is logged
- **Rules:** `_consume_item` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but started, `machine_id None`.
3. L = line(O, I1, "3").

**When**
- `result = WOM._consume_item(db, O, L, U2.id)`.

**Then**
1. re-read L: `consumed_at == NOW`.
2. count: `machine_activity_events` has 0 rows with `id > mark`.

### WOM-CI-05 — a line not using inventory is skipped
- **Rules:** `_consume_item` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "3"), but `uses_inventory False`.

**When**
- `result = WOM._consume_item(db, O, L, U2.id)`.

**Then**
1. session: `not db.dirty`.
2. unchanged: unchanged(L).
3. nothing written.

### WOM-CI-06 — an already consumed line is skipped
- **Rules:** `_consume_item` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S(F1, I1, 7, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "3"), but consumed(7.50).

**When**
- `result = WOM._consume_item(db, O, L, U2.id)`.

**Then**
1. unchanged: unchanged(L).
2. nothing written.

### WOM-CI-07 — an inventory line without a source type is refused
- **Rules:** `_consume_item` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. L = line(O, I1, "3"), but `source_location_type None`.

**When**
- `WOM._consume_item(db, O, L, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == f"Item line {L.id} uses inventory but has no source location set"`.
4. nothing written.

### WOM-CI-08 — a source id of 0 counts as missing
- **Rules:** `_consume_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. L = line(O, I1, "3"), but `source_location_id 0`.

**When**
- `WOM._consume_item(db, O, L, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == f"Item line {L.id} uses inventory but has no source location set"`.
4. nothing written.

### WOM-CI-09 — a fractional quantity cannot be consumed
- **Rules:** `_consume_item` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "2.50").

**When**
- `WOM._consume_item(db, O, L, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == f"Item line {L.id} has a fractional quantity; inventory consumption requires whole units"`.
4. nothing written.

### WOM-CI-10 — not enough stock is refused by the posting
- **Rules:** `_consume_item` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. S(F1, I1, 2, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "3").

**When**
- `WOM._consume_item(db, O, L, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Insufficient stock (2 available, 3 requested)"` (spec Notes, G14).
4. count: `led(F1, I1, STORAGE) == []`.

### WOM-CI-11 — a source factory of W2 is not found
- **Rules:** `_consume_item` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. L = line(O, I1, "3"), but `source_location_id F9.id`.

**When**
- `WOM._consume_item(db, O, L, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {F9.id} not found"`.

### WOM-CI-12 — a zero quantity is refused
- **Rules:** `_consume_item` R4 [BUG-665]
- **Kind:** bug
- **Expect:** xfail BUG-665
- **Fails today on:** Then 1 (no error is raised: a zero consumption row is written)

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "0").

**When**
- `WOM._consume_item(db, O, L, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. count: `led(F1, I1, STORAGE) == []`.

### WOM-CI-13 — a negative quantity never raises stock
- **Rules:** `_consume_item` R4 [BUG-665]
- **Kind:** bug
- **Expect:** xfail BUG-665
- **Fails today on:** Then 1 (no error is raised: storage goes from 10 to 12)

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "-2").

**When**
- `WOM._consume_item(db, O, L, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. re-read: `qty(F1, I1, STORAGE) == Decimal("10")`.

### WOM-CI-15 — on a component order the use is logged on the component (revisit after launch)
- **Rules:** `_consume_item` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but started, `machine_id None`, `project_component_id PC1.id`.
3. L = line(O, I1, "3").

**When**
- `result = WOM._consume_item(db, O, L, U2.id)`.

**Then**
1. re-read L: `consumed_at == NOW`.
2. event: `[r.event_type for r in pcacts(PC1)] == ["work_order_item_used"]`.

### WOM-CI-16 — a component of another workspace gets no entry
- **Rules:** `_consume_item` R7 [BUG-1884]
- **Kind:** bug
- **Expect:** xfail BUG-1884
- **Fails today on:** Then 2 (today an entry is written for PC9 under W1)

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but started, `machine_id None`, `project_component_id PC9.id` (invalid data).
3. L = line(O, I1, "3").

**When**
- `result = WOM._consume_item(db, O, L, U2.id)`.

**Then**
1. re-read L: `consumed_at == NOW`.
2. count: `project_component_activity_events` has 0 rows with `id > mark`.

### WOM-CI-17 — a component of another workspace does not stop the consumption
- **Rules:** `_consume_item` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but started, `machine_id None`, `project_component_id PC9.id` (invalid data).
3. L = line(O, I1, "3").

**When**
- `result = WOM._consume_item(db, O, L, U2.id)`.

**Then**
1. re-read L: `consumed_at == NOW`, `total_cost == Decimal("7.50")`.
2. re-read: `qty(F1, I1, STORAGE) == Decimal("7")`.

## `WorkOrderManager._reverse_item_consumption`

### WOM-RIC-01 — the whole line goes back at its unit cost and the line is cleared
- **Rules:** `_reverse_item_consumption` R2, R3; G18
- **Kind:** happy
- **Expect:** pass

**Given**
1. S(F1, I1, 7, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "3"), but consumed(7.50).

**When**
- `result = WOM._reverse_item_consumption(db, O, L, U2.id)`.

**Then**
1. re-read: `qty(F1, I1, STORAGE) == Decimal("10")`.
2. re-read: `[(r.transaction_type, r.quantity, r.unit_cost) for r in led(F1, I1, STORAGE)] == [("consumption_reversal", Decimal("3"), Decimal("2.50"))]`.
3. re-read: `led(F1, I1, STORAGE)[0].notes == f"{NUM(O)} voided — Bolt returned"`.
4. re-read L: `consumed_at is None`, `consumed_by is None`, `unit_cost is None`, `total_cost is None`.
5. event: `ev(O) == []`.
6. re-read: `all((r.source_type, r.source_id, r.performed_by) == ("work_order", O.id, U2.id) for r in led(F1, I1, STORAGE))` (G18: ledger source and performer).

### WOM-RIC-02 — a machine source gets its stock back with a "returned" activity
- **Rules:** `_reverse_item_consumption` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MS(M2, I1, 2, Decimal("4.00")).
2. O = order "1", but started.
3. L = line(O, I1, "3"), but consumed(12.00), `unit_cost Decimal("4.00")`, `source_location_type "machine"`, `source_location_id M2.id`.

**When**
- `result = WOM._reverse_item_consumption(db, O, L, U2.id)`.

**Then**
1. re-read: `mqty(M2, I1) == Decimal("5")`.
2. event: `[t for t, _ in acts(M2)] == ["consumption_reversed"]`.
3. event: that row's description `== f"Returned 3 Bolt — work order {NUM(O)} voided"`.

### WOM-RIC-03 — a line not consumed is skipped
- **Rules:** `_reverse_item_consumption` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "3").

**When**
- `result = WOM._reverse_item_consumption(db, O, L, U2.id)`.

**Then**
1. unchanged: unchanged(L).
2. nothing written.

### WOM-RIC-04 — a consumed line with no unit cost goes back at 0
- **Rules:** `_reverse_item_consumption` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S(F1, I1, 7, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "3"), but `consumed_at T1`, `consumed_by U1.id`, `unit_cost None`, `total_cost None`.

**When**
- `result = WOM._reverse_item_consumption(db, O, L, U2.id)`.

**Then**
1. re-read: `[(r.transaction_type, r.unit_cost) for r in led(F1, I1, STORAGE)] == [("consumption_reversal", Decimal("0"))]`.
2. re-read L: `consumed_at is None`.

## `WorkOrderManager._adjust_consumed_item_quantity`

### WOM-ADJ-01 — equal quantities do nothing
- **Rules:** `_adjust_consumed_item_quantity` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S(F1, I1, 7, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "3"), but consumed(7.50).

**When**
- `result = WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("3"), new_qty=Decimal("3"), user_id=U2.id)`.

**Then**
1. unchanged: unchanged(L).
2. nothing written.

### WOM-ADJ-02 — a line not using inventory does nothing
- **Rules:** `_adjust_consumed_item_quantity` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. L = line(O, I1, "3"), but `uses_inventory False`.

**When**
- `result = WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("3"), new_qty=Decimal("4"), user_id=U2.id)`.

**Then**
1. unchanged: unchanged(L).
2. nothing written.

### WOM-ADJ-03 — an order not in progress is refused
- **Rules:** `_adjust_consumed_item_quantity` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".
2. L = line(O, I1, "3"), but consumed(7.50).

**When**
- `WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("3"), new_qty=Decimal("4"), user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Consumed item quantity can only be adjusted while the work order is in progress"`.
4. nothing written.

### WOM-ADJ-04 — a new quantity of 0 is refused
- **Rules:** `_adjust_consumed_item_quantity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. L = line(O, I1, "3"), but consumed(7.50).

**When**
- `WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("3"), new_qty=Decimal("0"), user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Quantity must be a positive whole number for inventory-tracked consumed lines"`.
4. nothing written.

### WOM-ADJ-05 — a fractional new quantity is refused
- **Rules:** `_adjust_consumed_item_quantity` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. L = line(O, I1, "3"), but consumed(7.50).

**When**
- `WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("3"), new_qty=Decimal("3.5"), user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Quantity must be a positive whole number for inventory-tracked consumed lines"`.
4. nothing written.

### WOM-ADJ-06 — a fractional old quantity is refused
- **Rules:** `_adjust_consumed_item_quantity` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. L = line(O, I1, "2.50"), but consumed(6.25).

**When**
- `WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("2.5"), new_qty=Decimal("3"), user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Quantity must be a positive whole number for inventory-tracked consumed lines"`.
4. nothing written.

### WOM-ADJ-07 — an increase takes the difference out and adds it to the total
- **Rules:** `_adjust_consumed_item_quantity` R4, R6; G18
- **Kind:** happy
- **Expect:** pass

**Given**
1. S(F1, I1, 7, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "3"), but consumed(7.50).

**When**
- `result = WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("3"), new_qty=Decimal("4"), user_id=U2.id)`.

**Then**
1. re-read: `qty(F1, I1, STORAGE) == Decimal("6")`.
2. re-read: `[(r.transaction_type, r.quantity) for r in led(F1, I1, STORAGE)] == [("consumption", Decimal("1"))]`.
3. re-read: `led(F1, I1, STORAGE)[0].notes == f"{NUM(O)} — Bolt qty increased by 1"`.
4. re-read L: `total_cost == Decimal("10.00")`, `unit_cost == Decimal("2.50")`.
5. re-read: `all((r.source_type, r.source_id, r.performed_by) == ("work_order", O.id, U2.id) for r in led(F1, I1, STORAGE))` (G18: ledger source and performer).

### WOM-ADJ-08 — an increase at a new average cost re-averages the line
- **Rules:** `_adjust_consumed_item_quantity` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S(F1, I1, 7, Decimal("4.00")).
2. O = order "1", but started.
3. L = line(O, I1, "3"), but consumed(7.50).

**When**
- `result = WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("3"), new_qty=Decimal("4"), user_id=U2.id)`.

**Then**
1. re-read L: `total_cost == Decimal("11.50")`.
2. re-read L: `unit_cost == Decimal("2.88")`.

### WOM-ADJ-09 — the re-averaged unit cost rounds half up
- **Rules:** `_adjust_consumed_item_quantity` R6 [BUG-1040]
- **Kind:** bug
- **Expect:** xfail BUG-1040
- **Fails today on:** Then 2 (10.50 / 4 = 2.625 rounds half even to 2.62 today)

**Given**
1. S(F1, I1, 7, Decimal("3.00")).
2. O = order "1", but started.
3. L = line(O, I1, "3"), but consumed(7.50).

**When**
- `result = WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("3"), new_qty=Decimal("4"), user_id=U2.id)`.

**Then**
1. re-read L: `total_cost == Decimal("10.50")`.
2. re-read L: `unit_cost == Decimal("2.63")`.

### WOM-ADJ-10 — the re-averaged total holds whatever the rounding
- **Rules:** `_adjust_consumed_item_quantity` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S(F1, I1, 7, Decimal("3.00")).
2. O = order "1", but started.
3. L = line(O, I1, "3"), but consumed(7.50).

**When**
- `result = WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("3"), new_qty=Decimal("4"), user_id=U2.id)`.

**Then**
1. re-read L: `total_cost == Decimal("10.50")`.
2. re-read: `qty(F1, I1, STORAGE) == Decimal("6")`.

### WOM-ADJ-11 — a decrease returns the difference at the line's unit cost
- **Rules:** `_adjust_consumed_item_quantity` R5, R7; G18, G19
- **Kind:** happy
- **Expect:** pass

**Given**
1. S(F1, I1, 6, Decimal("3.00")).
2. O = order "1", but started.
3. L = line(O, I1, "4"), but consumed(10.00).

**When**
- `result = WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("4"), new_qty=Decimal("3"), user_id=U2.id)`.

**Then**
1. re-read: `qty(F1, I1, STORAGE) == Decimal("7")`.
2. re-read: `[(r.transaction_type, r.quantity, r.unit_cost) for r in led(F1, I1, STORAGE)] == [("consumption_reversal", Decimal("1"), Decimal("2.50"))]`.
3. re-read: `led(F1, I1, STORAGE)[0].notes == f"{NUM(O)} — Bolt qty reduced by 1"` (G19).
4. re-read L: `total_cost == Decimal("7.50")`, `unit_cost == Decimal("2.50")`.
5. re-read: `all((r.source_type, r.source_id, r.performed_by) == ("work_order", O.id, U2.id) for r in led(F1, I1, STORAGE))` (G18: ledger source and performer).

### WOM-ADJ-12 — a decrease with no unit cost leaves no total
- **Rules:** `_adjust_consumed_item_quantity` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S(F1, I1, 6, Decimal("3.00")).
2. O = order "1", but started.
3. L = line(O, I1, "4"), but `consumed_at T1`, `consumed_by U1.id`, `unit_cost None`, `total_cost None`.

**When**
- `result = WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("4"), new_qty=Decimal("3"), user_id=U2.id)`.

**Then**
1. re-read L: `total_cost is None`, `unit_cost is None`.
2. re-read: `qty(F1, I1, STORAGE) == Decimal("7")`.

### WOM-ADJ-13 — on an order with a machine the adjustment is logged on it
- **Rules:** `_adjust_consumed_item_quantity` R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S(F1, I1, 7, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "3"), but consumed(7.50).

**When**
- `result = WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("3"), new_qty=Decimal("4"), user_id=U2.id)`.

**Then**
1. event: `[t for t, _ in acts(M1)] == ["work_order_item_qty_adjusted"]`.
2. event: that row's description `== f"Adjusted Bolt from 3 to 4 (storage) for work order {NUM(O)}"`.
3. event: `set(that row's metadata_json.keys()) == {"item_id", "item_name", "old_quantity", "new_quantity", "work_order_id"}`.
4. event: that row's `metadata_json["work_order_id"] == O.id`.
5. event: that row's `metadata_json["old_quantity"] == 3`, `metadata_json["new_quantity"] == 4` (integers, spec Notes G3).

### WOM-ADJ-14 — on an order with no machine no activity is logged
- **Rules:** `_adjust_consumed_item_quantity` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S(F1, I1, 7, Decimal("2.50")).
2. O = order "1", but started, `machine_id None`.
3. L = line(O, I1, "3"), but consumed(7.50).

**When**
- `result = WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("3"), new_qty=Decimal("4"), user_id=U2.id)`.

**Then**
1. re-read L: `total_cost == Decimal("10.00")`.
2. count: `machine_activity_events` has 0 rows with `id > mark`.

### WOM-ADJ-15 — re-averaging 0.25 over two units rounds half up to 0.13
- **Rules:** `_adjust_consumed_item_quantity` R6, R6a [BUG-1040]
- **Kind:** bug
- **Expect:** xfail BUG-1040
- **Fails today on:** Then 3 (0.25 / 2 = 0.125 rounds half even to 0.12 today)

**Given**
1. S(F1, I1, 7, Decimal("0.00")).
2. O = order "1", but started.
3. L = line(O, I1, "1"), but `consumed_at T1`, `consumed_by U1.id`, `unit_cost Decimal("0.25")`, `total_cost Decimal("0.25")`.

**When**
- `result = WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("1"), new_qty=Decimal("2"), user_id=U2.id)`.

**Then**
1. re-read: `qty(F1, I1, STORAGE) == Decimal("6")`.
2. re-read L: `total_cost == Decimal("0.25")`.
3. re-read L: `unit_cost == Decimal("0.13")`.

### WOM-ADJ-16 — a decrease after a re-averaged increase prices the rest at the line's unit cost
- **Rules:** `_adjust_consumed_item_quantity` R5, R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S(F1, I1, 6, Decimal("4.00")).
2. O = order "1", but started.
3. L = line(O, I1, "4"), but `consumed_at T1`, `consumed_by U1.id`, `unit_cost Decimal("2.88")`, `total_cost Decimal("11.50")` (the state ADJ-08 leaves, built as a row).

**When**
- `result = WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("4"), new_qty=Decimal("3"), user_id=U2.id)`.

**Then**
1. re-read: `qty(F1, I1, STORAGE) == Decimal("7")`.
2. re-read: `[(r.transaction_type, r.quantity, r.unit_cost) for r in led(F1, I1, STORAGE)] == [("consumption_reversal", Decimal("1"), Decimal("2.88"))]`.
3. re-read L: `total_cost == Decimal("8.64")` (2.88 × 3; not 11.50 − 2.88 = 8.62), `unit_cost == Decimal("2.88")`.

### WOM-ADJ-17 — an increase by 3 adds unit cost × 3 and re-averages
- **Rules:** `_adjust_consumed_item_quantity` R4, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S(F1, I1, 7, Decimal("4.00")).
2. O = order "1", but started.
3. L = line(O, I1, "3"), but consumed(7.50).

**When**
- `result = WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("3"), new_qty=Decimal("6"), user_id=U2.id)`.

**Then**
1. re-read: `qty(F1, I1, STORAGE) == Decimal("4")`.
2. re-read: `[(r.transaction_type, r.quantity) for r in led(F1, I1, STORAGE)] == [("consumption", Decimal("3"))]`.
3. re-read: `led(F1, I1, STORAGE)[0].notes == f"{NUM(O)} — Bolt qty increased by 3"`.
4. re-read L: `total_cost == Decimal("19.50")` (7.50 + 4.00 × 3), `unit_cost == Decimal("3.25")` (19.50 / 6, exact).

### WOM-ADJ-18 — adjusting down to 1 is accepted
- **Rules:** `_adjust_consumed_item_quantity` R3, R5, R7; G19
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S(F1, I1, 6, Decimal("3.00")).
2. O = order "1", but started.
3. L = line(O, I1, "3"), but consumed(7.50).

**When**
- `result = WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("3"), new_qty=Decimal("1"), user_id=U2.id)`.

**Then**
1. re-read: `qty(F1, I1, STORAGE) == Decimal("8")`.
2. re-read: `[(r.transaction_type, r.quantity, r.unit_cost) for r in led(F1, I1, STORAGE)] == [("consumption_reversal", Decimal("2"), Decimal("2.50"))]`.
3. re-read: `led(F1, I1, STORAGE)[0].notes == f"{NUM(O)} — Bolt qty reduced by 2"` (G19).
4. re-read L: `total_cost == Decimal("2.50")`, `unit_cost == Decimal("2.50")`.

### WOM-ADJ-19 — an increase on a line with no total starts from 0
- **Rules:** `_adjust_consumed_item_quantity` R6 ("old total (or 0)")
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S(F1, I1, 7, Decimal("3.00")).
2. O = order "1", but started.
3. L = line(O, I1, "2"), but `consumed_at T1`, `consumed_by U1.id`, `unit_cost Decimal("2.50")`, `total_cost None`.

**When**
- `result = WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("2"), new_qty=Decimal("3"), user_id=U2.id)`.

**Then**
1. re-read: `qty(F1, I1, STORAGE) == Decimal("6")`.
2. re-read L: `total_cost == Decimal("3.00")` (0 + 3.00 × 1), `unit_cost == Decimal("1.00")` (3.00 / 3, exact).

### WOM-ADJ-20 — an increase from a machine source: stock, both activities and their texts
- **Rules:** `_adjust_consumed_item_quantity` R4, R6, R8; G18, G19
- **Kind:** happy
- **Expect:** pass

**Given**
1. MS(M2, I1, 5, Decimal("4.00")).
2. O = order "1", but started.
3. L = line(O, I1, "3"), but consumed(12.00), `unit_cost Decimal("4.00")`, `source_location_type "machine"`, `source_location_id M2.id`.

**When**
- `result = WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("3"), new_qty=Decimal("4"), user_id=U2.id)`.

**Then**
1. re-read: `mqty(M2, I1) == Decimal("4")`.
2. re-read: `[(r.transaction_type, r.quantity) for r in mled(M2, I1)] == [("consumption", Decimal("1"))]`.
3. event: `acts(M2) == [("consumption", f"Additional 1 Bolt consumed for work order {NUM(O)} (qty adjustment)")]` (G19).
4. event: `acts(M1) == [("work_order_item_qty_adjusted", f"Adjusted Bolt from 3 to 4 (machine #{M2.id}) for work order {NUM(O)}")]` (`<source>` written as in `_consume_item` R6).
5. re-read L: `total_cost == Decimal("16.00")`, `unit_cost == Decimal("4.00")`.
6. re-read: `mled(M2, I1)[0].notes == f"{NUM(O)} — Bolt qty increased by 1"` (R4).
7. re-read: `all((r.source_type, r.source_id, r.performed_by) == ("work_order", O.id, U2.id) for r in mled(M2, I1))` (G18: ledger source and performer).

### WOM-ADJ-21 — a decrease to a machine source: stock back, both activities and their texts
- **Rules:** `_adjust_consumed_item_quantity` R5, R7, R8; G18, G19
- **Kind:** happy
- **Expect:** pass

**Given**
1. MS(M2, I1, 1, Decimal("4.00")).
2. O = order "1", but started.
3. L = line(O, I1, "3"), but consumed(12.00), `unit_cost Decimal("4.00")`, `source_location_type "machine"`, `source_location_id M2.id`.

**When**
- `result = WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("3"), new_qty=Decimal("2"), user_id=U2.id)`.

**Then**
1. re-read: `mqty(M2, I1) == Decimal("2")`.
2. re-read: `[(r.transaction_type, r.quantity, r.unit_cost) for r in mled(M2, I1)] == [("consumption_reversal", Decimal("1"), Decimal("4.00"))]`.
3. event: `acts(M2) == [("consumption_reversed", f"Returned 1 Bolt — work order {NUM(O)} line qty adjusted")]` (G19; the ledger type is `consumption_reversal`, Then 2).
4. event: `acts(M1) == [("work_order_item_qty_adjusted", f"Adjusted Bolt from 3 to 2 (machine #{M2.id}) for work order {NUM(O)}")]`.
5. re-read L: `total_cost == Decimal("8.00")`, `unit_cost == Decimal("4.00")`.
6. re-read: `mled(M2, I1)[0].notes == f"{NUM(O)} — Bolt qty reduced by 1"` (G19).
7. re-read: `all((r.source_type, r.source_id, r.performed_by) == ("work_order", O.id, U2.id) for r in mled(M2, I1))` (G18: ledger source and performer).

### WOM-ADJ-22 — a decrease on a line with no unit cost posts the return at 0.00
- **Rules:** `_adjust_consumed_item_quantity` R5, R7; G18 (fallback cost, ledger source, performer)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S(F1, I1, 6, Decimal("3.00")).
2. O = order "1", but started.
3. L = line(O, I1, "4"), but `consumed_at T1`, `consumed_by U1.id`, `unit_cost None`, `total_cost None`.

**When**
- `result = WOM._adjust_consumed_item_quantity(db, O, L, old_qty=Decimal("4"), new_qty=Decimal("3"), user_id=U2.id)`.

**Then**
1. re-read: `qty(F1, I1, STORAGE) == Decimal("7")`.
2. re-read: `[(r.transaction_type, r.quantity, r.unit_cost) for r in led(F1, I1, STORAGE)] == [("consumption_reversal", Decimal("1"), Decimal("0.00"))]`.
3. re-read: `led(F1, I1, STORAGE)[0].notes == f"{NUM(O)} — Bolt qty reduced by 1"`.
4. re-read: `all((r.source_type, r.source_id, r.performed_by) == ("work_order", O.id, U2.id) for r in led(F1, I1, STORAGE))` (G18: ledger source and performer).
5. re-read L: `unit_cost is None`, `total_cost is None`.

## `WorkOrderManager._apply_item_completion`

### WOM-AIC-01 — a Consume line does nothing at completion
- **Rules:** `_apply_item_completion` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. L = line(O, I1, "2"), but consumed(5.00).

**When**
- `result = WOM._apply_item_completion(db, O, L, U2.id)`.

**Then**
1. unchanged: unchanged(L).
2. nothing written.

### WOM-AIC-02 — an Install line not consumed does nothing
- **Rules:** `_apply_item_completion` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. L = line(O, I1, "2"), but `action_type "INSTALL"`.

**When**
- `result = WOM._apply_item_completion(db, O, L, U2.id)`.

**Then**
1. nothing written.

### WOM-AIC-03 — an Install line not using inventory does nothing
- **Rules:** `_apply_item_completion` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. L = line(O, I1, "2"), but `action_type "INSTALL"`, `uses_inventory False`, `consumed_at T1`.

**When**
- `result = WOM._apply_item_completion(db, O, L, U2.id)`.

**Then**
1. nothing written.

### WOM-AIC-04 — an Install line on an order with no machine does nothing
- **Rules:** `_apply_item_completion` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started, `machine_id None`.
2. L = line(O, I1, "2"), but `action_type "INSTALL"`, consumed(5.00).

**When**
- `result = WOM._apply_item_completion(db, O, L, U2.id)`.

**Then**
1. nothing written.

### WOM-AIC-05 — Install puts the quantity on the order's machine at the line's cost
- **Rules:** `_apply_item_completion` R2, R9; G18
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. L = line(O, I1, "2"), but `action_type "INSTALL"`, consumed(5.00).

**When**
- `result = WOM._apply_item_completion(db, O, L, U2.id)`.

**Then**
1. re-read: `mqty(M1, I1) == Decimal("2")`.
2. re-read: `[(r.transaction_type, r.quantity, r.unit_cost) for r in mled(M1, I1)] == [("work_order_install", Decimal("2"), Decimal("2.50"))]`.
3. re-read: `mled(M1, I1)[0].notes == f"{NUM(O)} — Bolt installed"`.
4. event: `[t for t, _ in acts(M1)] == ["item_installed"]`.
5. event: that row's description `== f"Installed 2 Bolt — work order {NUM(O)}"`.
6. unchanged: unchanged(L).
7. re-read: `all((r.source_type, r.source_id, r.performed_by) == ("work_order", O.id, U2.id) for r in mled(M1, I1))` (G18: ledger source and performer).

### WOM-AIC-06 — Replace with enough on the machine: old part off, to damaged stock at 0, new part on
- **Rules:** `_apply_item_completion` R3, R4, R6, R7; G18, G19
- **Kind:** happy
- **Expect:** pass

**Given**
1. MS(M1, I2, 2, Decimal("300.00")).
2. O = order "1", but started.
3. L = line(O, I1, "2"), but `action_type "REPLACE"`, `replaced_item_id I2.id`, consumed(5.00).

**When**
- `result = WOM._apply_item_completion(db, O, L, U2.id)`.

**Then**
1. re-read: `mqty(M1, I2) == Decimal("0")`.
2. re-read: `[(r.transaction_type, r.quantity) for r in mled(M1, I2)] == [("work_order_replace_out", Decimal("2"))]`.
3. re-read: `qty(F1, I2, DAMAGED) == Decimal("2")`.
4. re-read: `[(r.transaction_type, r.quantity, r.unit_cost) for r in led(F1, I2, DAMAGED)] == [("work_order_replace_damaged", Decimal("2"), Decimal("0"))]`.
5. re-read: `mqty(M1, I1) == Decimal("2")`.
6. re-read: `[(r.transaction_type, r.unit_cost) for r in mled(M1, I1)] == [("work_order_replace_in", Decimal("2.50"))]`.
7. event: `[t for t, _ in acts(M1)] == ["item_replaced_removed", "item_replaced"]`.
8. event: `acts(M1) == [("item_replaced_removed", f"Removed 2 Bearing (replaced) — work order {NUM(O)}"), ("item_replaced", f"Installed 2 Bolt as a replacement — work order {NUM(O)}")]` (Revision 4).
9. re-read: `led(F1, I2, DAMAGED)[0].notes == f"{NUM(O)} — Bearing moved to damaged stock"` (G19).
10. re-read: `mled(M1, I2)[0].notes == f"{NUM(O)} — Bearing removed for replacement"` (G19).
11. re-read: `mled(M1, I1)[0].notes == f"{NUM(O)} — Bolt installed (replacement)"` (G19).
12. re-read: `all((r.source_type, r.source_id, r.performed_by) == ("work_order", O.id, U2.id) for r in mled(M1, I2) + led(F1, I2, DAMAGED) + mled(M1, I1))` (G18: ledger source and performer).

### WOM-AIC-07 — the removed part joins existing damaged stock at zero value (✅ OQ-59)
- **Rules:** `_apply_item_completion` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MS(M1, I2, 3, Decimal("300.00")).
2. SD(F1, I2, 1, Decimal("50.00")).
3. O = order "1", but started.
4. L = line(O, I1, "2"), but `action_type "REPLACE"`, `replaced_item_id I2.id`, consumed(5.00).

**When**
- `result = WOM._apply_item_completion(db, O, L, U2.id)`.

**Then**
1. re-read: `qty(F1, I2, DAMAGED) == Decimal("3")`.
2. re-read: `[r.unit_cost for r in led(F1, I2, DAMAGED)] == [Decimal("0")]`.
3. re-read: `mqty(M1, I2) == Decimal("1")`.

### WOM-AIC-08 — Replace with too little on the machine installs without removing and logs why
- **Rules:** `_apply_item_completion` R5, R7; G18, G19
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MS(M1, I2, 1, Decimal("300.00")).
2. O = order "1", but started.
3. L = line(O, I1, "2"), but `action_type "REPLACE"`, `replaced_item_id I2.id`, consumed(5.00).

**When**
- `result = WOM._apply_item_completion(db, O, L, U2.id)`.

**Then**
1. re-read: `mqty(M1, I2) == Decimal("1")`.
2. count: `mled(M1, I2) == []`.
3. count: `led(F1, I2, DAMAGED) == []`.
4. re-read: `mqty(M1, I1) == Decimal("2")`.
5. event: `[t for t, _ in ev(O)] == ["item_replace_degraded"]`.
6. event: its description `== "Machine only had 1 of Bearing on hand (needed 2) — installed 2 Bolt without removing anything"`.
7. event: `acts(M1) == [("item_replaced", f"Installed 2 Bolt as a replacement — work order {NUM(O)}")]` (Revision 4; nothing removed, so no `item_replaced_removed`).
8. re-read: `[(r.transaction_type, r.quantity, r.unit_cost, r.notes) for r in mled(M1, I1)] == [("work_order_replace_in", Decimal("2"), Decimal("2.50"), f"{NUM(O)} — Bolt installed (replacement)")]` (G19).
9. re-read: `all((r.source_type, r.source_id, r.performed_by) == ("work_order", O.id, U2.id) for r in mled(M1, I1))` (G18: ledger source and performer).

### WOM-AIC-09 — Replace with no machine row counts as 0 on hand
- **Rules:** `_apply_item_completion` R3, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. L = line(O, I1, "1"), but `action_type "REPLACE"`, `replaced_item_id I2.id`, consumed(2.50).

**When**
- `result = WOM._apply_item_completion(db, O, L, U2.id)`.

**Then**
1. event: `[t for t, _ in ev(O)] == ["item_replace_degraded"]`.
2. re-read: `mqty(M1, I1) == Decimal("1")`.
3. count: `led(F1, I2, DAMAGED) == []`.

### WOM-AIC-10 — Borrow from storage gives the quantity back with a ledger row and no activity
- **Rules:** `_apply_item_completion` R8 (G16); G18, G19
- **Kind:** happy
- **Expect:** pass

**Given**
1. S(F1, I1, 8, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "2"), but `action_type "BORROW"`, consumed(5.00).

**When**
- `result = WOM._apply_item_completion(db, O, L, U2.id)`.

**Then**
1. re-read: `qty(F1, I1, STORAGE) == Decimal("10")`.
2. re-read: `[(r.transaction_type, r.quantity, r.unit_cost) for r in led(F1, I1, STORAGE)] == [("work_order_borrow_returned", Decimal("2"), Decimal("2.50"))]`.
3. count: `MachineActivityEvent` rows with `id > mark` (any machine) has 0 rows.
4. unchanged: unchanged(L).
5. re-read: `led(F1, I1, STORAGE)[0].notes == f"{NUM(O)} — Bolt returned"` (G19).
6. re-read: `all((r.source_type, r.source_id, r.performed_by) == ("work_order", O.id, U2.id) for r in led(F1, I1, STORAGE))` (G18: ledger source and performer).

### WOM-AIC-11 — Borrow from a machine gives the quantity back and logs the activity on that machine
- **Rules:** `_apply_item_completion` R8 (G16); G18, G19
- **Kind:** happy
- **Expect:** pass

**Given**
1. MS(M2, I1, 3, Decimal("4.00")).
2. O = order "1", but started.
3. L = line(O, I1, "2"), but `action_type "BORROW"`, consumed(8.00), `unit_cost Decimal("4.00")`, `source_location_type "machine"`, `source_location_id M2.id`.

**When**
- `result = WOM._apply_item_completion(db, O, L, U2.id)`.

**Then**
1. re-read: `mqty(M2, I1) == Decimal("5")`.
2. re-read: `[(r.transaction_type, r.quantity, r.unit_cost) for r in mled(M2, I1)] == [("work_order_borrow_returned", Decimal("2"), Decimal("4.00"))]`.
3. event: `[t for t, _ in acts(M2)] == ["item_borrowed_returned"]`.
4. event: that row's description `== f"Returned 2 Bolt — work order {NUM(O)}"`.
5. event: `acts(M1) == []`.
6. unchanged: unchanged(L).
7. re-read: `mled(M2, I1)[0].notes == f"{NUM(O)} — Bolt returned"` (G19).
8. re-read: `all((r.source_type, r.source_id, r.performed_by) == ("work_order", O.id, U2.id) for r in mled(M2, I1))` (G18: ledger source and performer).

### WOM-AIC-12 — the removed part goes to the damaged stock of the order's factory
- **Rules:** `_apply_item_completion` R4, R6; G18 (damaged stock factory)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. FX = `Factory(workspace_id=W1.id, name="Plant Three", abbreviation="P3")`.
2. MS(M3, I2, 2, Decimal("300.00")) (M3 sits in F2).
3. O = order "1", but started, `factory_id FX.id`, `machine_id M3.id` (a legacy order whose machine is in another factory; BUG-2921).
4. L = line(O, I1, "2"), but `action_type "REPLACE"`, `replaced_item_id I2.id`, consumed(5.00) (source F1, the line default).

So the line's source (F1), the machine's factory (F2) and the order's factory (FX) all differ.

**When**
- `result = WOM._apply_item_completion(db, O, L, U2.id)`.

**Then**
1. re-read: `[(r.transaction_type, r.quantity, r.unit_cost) for r in led(FX, I2, DAMAGED)] == [("work_order_replace_damaged", Decimal("2"), Decimal("0.00"))]`.
2. re-read: `qty(FX, I2, DAMAGED) == Decimal("2")`.
3. count: `led(F1, I2, DAMAGED) == []`, `led(F2, I2, DAMAGED) == []`.
4. re-read: `mqty(M3, I2) == Decimal("0")`, `mqty(M3, I1) == Decimal("2")`.
5. re-read: `led(FX, I2, DAMAGED)[0].notes == f"{NUM(O)} — Bearing moved to damaged stock"`.

### WOM-AIC-13 — Install with no unit cost posts at 0.00
- **Rules:** `_apply_item_completion` R2; G18 (fallback cost)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. L = line(O, I1, "2"), but `action_type "INSTALL"`, `consumed_at T1`, `consumed_by U1.id`, `unit_cost None`, `total_cost None`.

**When**
- `result = WOM._apply_item_completion(db, O, L, U2.id)`.

**Then**
1. re-read: `mqty(M1, I1) == Decimal("2")`.
2. re-read: `[(r.transaction_type, r.quantity, r.unit_cost) for r in mled(M1, I1)] == [("work_order_install", Decimal("2"), Decimal("0.00"))]`.
3. re-read: `all((r.source_type, r.source_id, r.performed_by) == ("work_order", O.id, U2.id) for r in mled(M1, I1))` (G18: ledger source and performer).

### WOM-AIC-14 — Replace-in with no unit cost posts at 0.00
- **Rules:** `_apply_item_completion` R4, R6, R7; G18 (fallback cost)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MS(M1, I2, 2, Decimal("300.00")).
2. O = order "1", but started.
3. L = line(O, I1, "2"), but `action_type "REPLACE"`, `replaced_item_id I2.id`, `consumed_at T1`, `consumed_by U1.id`, `unit_cost None`, `total_cost None`.

**When**
- `result = WOM._apply_item_completion(db, O, L, U2.id)`.

**Then**
1. re-read: `[(r.transaction_type, r.quantity, r.unit_cost) for r in mled(M1, I1)] == [("work_order_replace_in", Decimal("2"), Decimal("0.00"))]`.
2. re-read: `[(r.transaction_type, r.unit_cost) for r in led(F1, I2, DAMAGED)] == [("work_order_replace_damaged", Decimal("0.00"))]`.
3. re-read: `mqty(M1, I1) == Decimal("2")`, `mqty(M1, I2) == Decimal("0")`.

### WOM-AIC-15 — Borrow return with no unit cost posts at 0.00
- **Rules:** `_apply_item_completion` R8; G18 (fallback cost)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S(F1, I1, 8, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "2"), but `action_type "BORROW"`, `consumed_at T1`, `consumed_by U1.id`, `unit_cost None`, `total_cost None`.

**When**
- `result = WOM._apply_item_completion(db, O, L, U2.id)`.

**Then**
1. re-read: `qty(F1, I1, STORAGE) == Decimal("10")`.
2. re-read: `[(r.transaction_type, r.quantity, r.unit_cost) for r in led(F1, I1, STORAGE)] == [("work_order_borrow_returned", Decimal("2"), Decimal("0.00"))]`.
3. re-read: `led(F1, I1, STORAGE)[0].notes == f"{NUM(O)} — Bolt returned"`.

## `WorkOrderManager._set_machine_status`

### WOM-SMS-01 — a new status writes one status event with the order's note and id
- **Rules:** `_set_machine_status` R1, R3, R4, R5; G18
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".
2. status row(M1, "RUNNING", T0).

**When**
- `result = WOM._set_machine_status(db, M1.id, W1.id, U2.id, MachineEventTypeEnum.MAINTENANCE, work_order_number="WO-77", work_order_id=O.id)`.

**Then**
1. returns: `result == "RUNNING"`.
2. event: `stat(M1) == ["MAINTENANCE"]`.
3. event: that row's `metadata_json["note"] == "Work order WO-77"`, `metadata_json["work_order_id"] == O.id`, `description == "Status set to maintenance (Work order WO-77)"`.
4. returns: `type(result) is str` (the stored text, not a `MachineEventTypeEnum` member; R5).
5. event: that status row's `performed_by == U2.id` (G18).

### WOM-SMS-02 — the same status does nothing
- **Rules:** `_set_machine_status` R2, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. status row(M1, "MAINTENANCE", T0).

**When**
- `result = WOM._set_machine_status(db, M1.id, W1.id, U2.id, MachineEventTypeEnum.MAINTENANCE, work_order_number="WO-77")`.

**Then**
1. returns: `result == "MAINTENANCE"`.
2. nothing written.
3. returns: `type(result) is str` (R5).

### WOM-SMS-03 — no status before: one event, returns None; no number gives no note
- **Rules:** `_set_machine_status` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No status row for M1.

**When**
- `result = WOM._set_machine_status(db, M1.id, W1.id, U2.id, MachineEventTypeEnum.IDLE)`.

**Then**
1. returns: `result is None`.
2. event: `stat(M1) == ["IDLE"]`.
3. event: that row's `description == "Status set to idle"`, `metadata_json["note"] is None`, `"work_order_id" not in metadata_json`.

### WOM-SMS-04 — a deleted machine is refused
- **Rules:** `_set_machine_status` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. MD = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Old press")`, but gone.

**When**
- `WOM._set_machine_status(db, MD.id, W1.id, U2.id, MachineEventTypeEnum.MAINTENANCE)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create event for a deleted machine"`.
4. nothing written.

### WOM-SMS-05 — a machine of W2 is not found
- **Rules:** `_set_machine_status` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `WOM._set_machine_status(db, M9.id, W1.id, U2.id, MachineEventTypeEnum.MAINTENANCE)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
4. nothing written.

### WOM-SMS-06 — a work order id that is not a live order of the workspace is refused
- **Rules:** `_set_machine_status` R3 [BUG-1000]
- **Kind:** bug
- **Expect:** xfail BUG-1000
- **Fails today on:** Then 1 (no error is raised: the status event stores the id)

**Given**
1. O = order "1", but gone.
2. status row(M1, "RUNNING", T0).

**When**
- `WOM._set_machine_status(db, M1.id, W1.id, U2.id, MachineEventTypeEnum.MAINTENANCE, work_order_number=NUM(O), work_order_id=O.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order with ID {O.id} not found"`.
4. nothing written.

## `WorkOrderManager._previous_machine_status`

### WOM-PMS-01 — the newest started event decides; other event types are ignored
- **Rules:** `_previous_machine_status` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. event(O, "started", {"previous_machine_status": "RUNNING"}, T0).
3. event(O, "started", {"previous_machine_status": "IDLE"}, T1).
4. event(O, "note", {"previous_machine_status": "OFF"}, NOW).

**When**
- `result = WOM._previous_machine_status(db, O)`.

**Then**
1. returns: `result == "IDLE"`.

### WOM-PMS-02 — no started event gives None
- **Rules:** `_previous_machine_status` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. event(O, "note", {"previous_machine_status": "OFF"}, T1).

**When**
- `result = WOM._previous_machine_status(db, O)`.

**Then**
1. returns: `result is None`.

### WOM-PMS-03 — a started event without the key gives None
- **Rules:** `_previous_machine_status` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. event(O, "started", {"previous_machine_status": "RUNNING"}, T0).
3. event(O, "started", {"items_consumed": 0}, T1).

**When**
- `result = WOM._previous_machine_status(db, O)`.

**Then**
1. returns: `result is None`.

## `WorkOrderManager.start_work_order`

### WOM-ST-01 — start consumes the lines and moves the order in progress
- **Rules:** `start_work_order` R1, R4, R6; `_run_start_side_effects` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but stamped.
3. status row(M1, "RUNNING", T0).
4. L = line(O, I1, "3").

**When**
- `result = WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `status == "IN_PROGRESS"`, `started_by == U2.id`, `started_at == NOW`, `planned_date == D(12)`.
3. re-read L: `consumed_at == NOW`, `unit_cost == Decimal("2.50")`, `total_cost == Decimal("7.50")`.
4. re-read: `qty(F1, I1, STORAGE) == Decimal("7")`.

### WOM-ST-02 — start puts the machine into maintenance for this order
- **Rules:** `start_work_order` R5; `_run_start_side_effects` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but stamped.
3. status row(M1, "RUNNING", T0).
4. L = line(O, I1, "3").

**When**
- `result = WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. event: `stat(M1) == ["MAINTENANCE"]`.
3. event: that status row's `metadata_json["work_order_id"] == O.id`, `metadata_json["note"] == f"Work order {NUM(O)}"`.

### WOM-ST-03 — the started event carries the count, the status before, the schedule and the workers
- **Rules:** `start_work_order` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but stamped.
3. status row(M1, "RUNNING", T0).
4. L = line(O, I1, "3").

**When**
- `result = WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. event: `ev(O) == [("started", "Work started — 1 item(s) consumed")]`.
3. event: `evrow(O, "started").metadata_json == {"items_consumed": 1, "previous_machine_status": "RUNNING", "started_at": "2026-03-10T09:00:00", "planned_date": "2026-03-12", "variance_days": -2, "variance_label": "2 days early", "assigned_to": None, "assignee_user_ids": [], "started_by_user_id": U2.id}`.

### WOM-ST-04 — with no lines the event says so
- **Rules:** `start_work_order` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. status row(M1, "RUNNING", T0).

**When**
- `result = WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. event: `ev(O) == [("started", "Work started — no inventory items to consume")]`.
3. event: `evrow(O, "started").metadata_json["items_consumed"] == 0`.

### WOM-ST-05 — an empty planned date becomes today
- **Rules:** `start_work_order` R6, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `planned_date None`.
2. status row(M1, "RUNNING", T0).

**When**
- `result = WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `planned_date == D(10)`.
3. event: `evrow(O, "started").metadata_json["planned_date"] == "2026-03-10"`, `["variance_label"] == "On plan"`.

### WOM-ST-06 — an order in progress cannot be started again
- **Rules:** `start_work_order` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started.

**When**
- `WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order must be in draft to be started"`.
4. session clean.
5. nothing written.

### WOM-ST-07 — a voided order cannot be started
- **Rules:** `start_work_order` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but voided.

**When**
- `WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order must be in draft to be started"`.
4. nothing written.

### WOM-ST-08 — unmet approvals block the start
- **Rules:** `start_work_order` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1".
3. approver(O, U2).
4. L = line(O, I1, "3").

**When**
- `WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Assigned approvers must approve before work can start"`.
4. session clean.
5. nothing written.

### WOM-ST-09 — zero required approvals waives an unapproved approver
- **Rules:** `start_work_order` R3; `approval_summary` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `required_approvals 0`.
2. approver(O, U2).
3. status row(M1, "RUNNING", T0).

**When**
- `result = WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `status == "IN_PROGRESS"`.

### WOM-ST-10 — only live, pending inventory lines are consumed
- **Rules:** `start_work_order` R4; `_run_start_side_effects` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. S(F1, I3, 10, Decimal("1.00")).
3. O = order "1", but stamped.
4. status row(M1, "RUNNING", T0).
5. LP = line(O, I1, "3").
6. LG = line(O, I2, "1"), but gone.
7. LN = line(O, I3, "1"), but `uses_inventory False`.
8. LC = line(O, I2, "2"), but consumed(5.00).

**When**
- `result = WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. event: `evrow(O, "started").metadata_json["items_consumed"] == 1`.
3. re-read LP: `consumed_at == NOW`.
4. unchanged: unchanged(LG).
5. unchanged: unchanged(LN).
6. unchanged: unchanged(LC).
7. re-read: `qty(F1, I3, STORAGE) == Decimal("10")`.

### WOM-ST-11 — a line that cannot be consumed stops the start
- **Rules:** `start_work_order` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. S(F1, I2, 2, Decimal("5.00")).
3. O = order "1", but stamped.
4. status row(M1, "RUNNING", T0).
5. line(O, I1, "3").
6. line(O, I2, "5").

**When**
- `WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Insufficient stock (2 available, 5 requested)"` (spec Notes, G14).
4. event: `ev(O) == []`.

### WOM-ST-12 — a fractional stock line stops the start
- **Rules:** `start_work_order` R4; `_consume_item` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but stamped.
3. status row(M1, "RUNNING", T0).
4. L = line(O, I1, "2.50").

**When**
- `WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == f"Item line {L.id} has a fractional quantity; inventory consumption requires whole units"`.

### WOM-ST-13 — a machine already in maintenance gets no new status event
- **Rules:** `start_work_order` R5; `_set_machine_status` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. status row(M1, "MAINTENANCE", T0).

**When**
- `result = WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. event: `stat(M1) == []`.
3. event: `evrow(O, "started").metadata_json["previous_machine_status"] == "MAINTENANCE"`.

### WOM-ST-14 — an order with no machine changes no machine status
- **Rules:** `start_work_order` R5; `_run_start_side_effects` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `machine_id None`.

**When**
- `result = WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. count: `machine_activity_events` has 0 rows with `id > mark`.
3. event: `evrow(O, "started").metadata_json["previous_machine_status"] is None`.

### WOM-ST-15 — an order on a deleted machine cannot be started
- **Rules:** `start_work_order` R5; `_set_machine_status` R3 (machine O5)
- **Kind:** error
- **Expect:** pass

**Given**
1. MD = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Old press")`, but gone.
2. O = order "1", but stamped, `machine_id MD.id`.

**When**
- `WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create event for a deleted machine"`.

### WOM-ST-16 — the assigned workers go into the started event
- **Rules:** `start_work_order` R7; `_started_worker_metadata` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `assigned_to "Sara Khan"`.
2. assignee(O, U3).
3. status row(M1, "RUNNING", T0).

**When**
- `result = WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. event: `evrow(O, "started").metadata_json["assigned_to"] == "Sara Khan"`.
3. event: `evrow(O, "started").metadata_json["assignee_user_ids"] == [U3.id]`.

### WOM-ST-17 — a soft-deleted order is not found
- **Rules:** `start_work_order` R1; `get_work_order` R2 [BUG-1279]
- **Kind:** bug
- **Expect:** xfail BUG-1279
- **Fails today on:** Then 1 (no error is raised: the deleted order is started)

**Given**
1. O = order "1", but stamped, gone.
2. status row(M1, "RUNNING", T0).

**When**
- `WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order with ID {O.id} not found"`.
4. nothing written.

### WOM-ST-18 — the order row is locked before its state is checked
- **Rules:** `start_work_order` R9 [BUG-2916]
- **Kind:** bug
- **Expect:** xfail BUG-2916
- **Fails today on:** Then 2 (no `FOR UPDATE` is sent)

**Given**
1. O = order "1", but stamped, `machine_id None`.
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.status == "IN_PROGRESS"`.
2. statement: locks first `work_orders`.

### WOM-ST-19 — a component of another workspace gets no entry at start
- **Rules:** `start_work_order` R8 [BUG-1884]
- **Kind:** bug
- **Expect:** xfail BUG-1884
- **Fails today on:** Then 2 (today an entry is written for PC9)

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but stamped, `machine_id None`, `project_component_id PC9.id` (invalid data).
3. line(O, I1, "3").

**When**
- `result = WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.status == "IN_PROGRESS"`.
2. count: `project_component_activity_events` has 0 rows with `id > mark`.

### WOM-ST-20 — a component of another workspace does not stop the start
- **Rules:** `start_work_order` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but stamped, `machine_id None`, `project_component_id PC9.id` (invalid data).
3. line(O, I1, "3").

**When**
- `result = WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.status == "IN_PROGRESS"`.
2. re-read: `qty(F1, I1, STORAGE) == Decimal("7")`.

### WOM-ST-21 — start flushes and never commits
- **Rules:** `start_work_order` R6
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order "1", but stamped, `machine_id None`.

**When**
- commit spy around `result = WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. inside: `result.status == "IN_PROGRESS"`.
2. inside: `cm.call_count == 0`.
3. after: re-read O: `status == "DRAFT"`.

### WOM-ST-22 — the starter is the performer of the event, the status change and the consumption
- **Rules:** `start_work_order` R4, R5, R7; G18 (performer, ledger source)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but stamped (created and stamped by U1).
3. status row(M1, "RUNNING", T0).
4. L = line(O, I1, "3") (created by U1).

**When**
- `result = WOM.start_work_order(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. event: `evrow(O, "started").performed_by == U2.id`.
3. event: the new `status_updated` row of M1 has `performed_by == U2.id`.
4. re-read: `[(r.transaction_type, r.quantity) for r in led(F1, I1, STORAGE)] == [("consumption", Decimal("3"))]`.
5. re-read: `all((r.source_type, r.source_id, r.performed_by) == ("work_order", O.id, U2.id) for r in led(F1, I1, STORAGE))` (G18: ledger source and performer).

## `WorkOrderManager._planned_date_noon_utc`

### WOM-PN-01 — noon of the date, naive
- **Rules:** `_planned_date_noon_utc` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._planned_date_noon_utc(D(8))`.

**Then**
1. returns: `result == NOON(8)`.
2. returns: `result.tzinfo is None`.

## `WorkOrderManager._run_start_side_effects`

### WOM-RSE-01 — returns the count of lines consumed and the machine's status before
- **Rules:** `_run_start_side_effects` R1, R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but stamped.
3. status row(M1, "RUNNING", T0).
4. L = line(O, I1, "3").

**When**
- `result = WOM._run_start_side_effects(db, O, W1.id, U2.id)`.

**Then**
1. returns: `result == (1, "RUNNING")`.
2. returns: `type(result[0]) is int`, `type(result[1]) is str`.
3. re-read: `qty(F1, I1, STORAGE) == Decimal("7")`.
4. event: `stat(M1) == ["MAINTENANCE"]`.
5. re-read O: `status == "DRAFT"` (status is not changed here).

### WOM-RSE-02 — no lines and no machine give (0, None)
- **Rules:** `_run_start_side_effects` R1, R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `machine_id None`.

**When**
- `result = WOM._run_start_side_effects(db, O, W1.id, U2.id)`.

**Then**
1. returns: `result == (0, None)`.
2. nothing written.

## `WorkOrderManager._ensure_active_workspace_member`

### WOM-EAM-01 — an active member passes
- **Rules:** `_ensure_active_workspace_member` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._ensure_active_workspace_member(db, W1.id, U2.id)`.

**Then**
1. returns: `result is None`.

### WOM-EAM-02 — a suspended member is refused
- **Rules:** `_ensure_active_workspace_member` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `WOM._ensure_active_workspace_member(db, W1.id, U4.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.

### WOM-EAM-03 — an active member of W0 and W2 only is refused in W1
- **Rules:** `_ensure_active_workspace_member` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `WOM._ensure_active_workspace_member(db, W1.id, U5.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.

## `WorkOrderManager._sync_assignees_from_text`

### WOM-SAT-01 — matched names become the assignee rows
- **Rules:** `_sync_assignees_from_text` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".
2. assignee(O, U3).

**When**
- `result = WOM._sync_assignees_from_text(db, O, "rahim uddin, Ghost")`.

**Then**
1. returns: `result == [U2.id]`.
2. count: `[a.user_id for a in WorkOrderAssignee rows with work_order_id == O.id] == [U2.id]`.

### WOM-SAT-02 — no text removes every assignee row
- **Rules:** `_sync_assignees_from_text` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".
2. assignee(O, U3).

**When**
- `result = WOM._sync_assignees_from_text(db, O, None)`.

**Then**
1. returns: `result == []`.
2. count: `work_order_assignees` with `work_order_id == O.id` has 0 rows.

### WOM-SAT-03 — blank text, a suspended member and a member of other workspaces match nobody
- **Rules:** `_sync_assignees_from_text` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order "1".
2. P = order "2".

**When**
- `result = (WOM._sync_assignees_from_text(db, O, "   "), WOM._sync_assignees_from_text(db, P, "Omar Faruk, Nadia Islam"))`.

**Then**
1. returns: `result == ([], [])`.
2. count: `work_order_assignees` with `work_order_id in (O.id, P.id)` has 0 rows.

## `WorkOrderManager._resolve_completion_workers`

### WOM-RCW-01 — ids give their display names, in the order given
- **Rules:** `_resolve_completion_workers` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._resolve_completion_workers(db, W1.id, U1.id, completed_by_user_ids=[U3.id, U2.id])`.

**Then**
1. returns: `result == ("Sara Khan, Rahim Uddin", [U3.id, U2.id])`.

### WOM-RCW-02 — names given with ids are used trimmed
- **Rules:** `_resolve_completion_workers` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._resolve_completion_workers(db, W1.id, U1.id, completed_by_user_ids=[U3.id], completed_by_names="  Team A  ")`.

**Then**
1. returns: `result == ("Team A", [U3.id])`.

### WOM-RCW-03 — an empty id list falls back to the single id
- **Rules:** `_resolve_completion_workers` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._resolve_completion_workers(db, W1.id, U1.id, completed_by_user_ids=[], completed_by_user_id=U3.id)`.

**Then**
1. returns: `result == ("Sara Khan", [U3.id])`.

### WOM-RCW-04 — an id that is not an active member is refused
- **Rules:** `_resolve_completion_workers` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `WOM._resolve_completion_workers(db, W1.id, U1.id, completed_by_user_ids=[U2.id, U4.id])`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.

### WOM-RCW-05 — a repeated id keeps its repeats in the ids
- **Rules:** `_resolve_completion_workers` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._resolve_completion_workers(db, W1.id, U1.id, completed_by_user_ids=[U2.id, U2.id])`.

**Then**
1. returns: `result[1] == [U2.id, U2.id]`.

### WOM-RCW-06 — a repeated id shows its name once
- **Rules:** `_resolve_completion_workers` R2 [BUG-381]
- **Kind:** bug
- **Expect:** xfail BUG-381
- **Fails today on:** Then 2 (today the names read "Rahim Uddin, Rahim Uddin")

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._resolve_completion_workers(db, W1.id, U1.id, completed_by_user_ids=[U2.id, U2.id])`.

**Then**
1. returns: `result[1] == [U2.id, U2.id]`.
2. returns: `result[0] == "Rahim Uddin"`.

### WOM-RCW-07 — names alone are matched to active members
- **Rules:** `_resolve_completion_workers` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._resolve_completion_workers(db, W1.id, U1.id, completed_by_names="sara khan, Ghost")`.

**Then**
1. returns: `result == ("Sara Khan, Ghost", [U3.id])`.

### WOM-RCW-08 — names that match nobody give no ids
- **Rules:** `_resolve_completion_workers` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._resolve_completion_workers(db, W1.id, U1.id, completed_by_names="Ghost")`.

**Then**
1. returns: `result == ("Ghost", [])`.

### WOM-RCW-09 — neither ids nor names: the performer did the work
- **Rules:** `_resolve_completion_workers` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM._resolve_completion_workers(db, W1.id, U1.id, completed_by_names="   ")`.

**Then**
1. returns: `result == ("Karim Ahmed", [U1.id])`.

### WOM-RCW-10 — a performer who is not an active member is refused
- **Rules:** `_resolve_completion_workers` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `WOM._resolve_completion_workers(db, W1.id, U4.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.

### WOM-RCW-11 — a performer whose profile name is empty shows as "User #<id>"
- **Rules:** `_resolve_completion_workers` R4, R4a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. UE = `make_profile(db, name="")` (an empty name stored directly; spec Notes, G12).
2. `WorkspaceMember(workspace_id=W1.id, user_id=UE.id, role="member", status="active", position=None)`.

**When**
- `result = WOM._resolve_completion_workers(db, W1.id, UE.id)`.

**Then**
1. returns: `result == (f"User #{UE.id}", [UE.id])`.

## `WorkOrderManager.complete_as_planned`

### WOM-CAP-01 — a draft is started and completed at noon of its planned date
- **Rules:** `complete_as_planned` R6, R7, R9, R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but stamped, `planned_date D(8)`.
3. status row(M1, "RUNNING", T0).
4. L = line(O, I1, "3").

**When**
- `result = WOM.complete_as_planned(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `status == "COMPLETED"`, `started_by == U2.id`, `started_at == NOON(8)`, `completed_at == NOON(8)`.
3. re-read O: `completed_by == U2.id`, `completed_by_names == "Rahim Uddin"`.
4. re-read: `qty(F1, I1, STORAGE) == Decimal("7")`.
5. event: `stat(M1) == ["MAINTENANCE", "RUNNING"]`.

### WOM-CAP-02 — the started and completed events carry the planned mode
- **Rules:** `complete_as_planned` R8, R9
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but stamped, `planned_date D(8)`.
3. status row(M1, "RUNNING", T0).
4. line(O, I1, "3").

**When**
- `result = WOM.complete_as_planned(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. event: `[t for t, _ in ev(O)] == ["started", "completed"]`.
3. event: `evrow(O, "started").metadata_json == {"items_consumed": 1, "previous_machine_status": "RUNNING", "started_at": "2026-03-08T12:00:00", "planned_date": "2026-03-08", "variance_days": 0, "variance_label": "On plan", "assigned_to": None, "assignee_user_ids": [], "started_by_user_id": U2.id, "completion_mode": "complete_as_planned"}`.
4. event: `evrow(O, "completed").metadata_json == {"completed_at": "2026-03-08T12:00:00", "planned_date": "2026-03-08", "variance_days": 0, "variance_label": "On plan", "completion_mode": "complete_as_planned", "completed_by_names": "Rahim Uddin", "completed_by_name": "Rahim Uddin", "completed_by_user_ids": [U2.id], "completed_by": U2.id}`.
5. event: `evrow(O, "started").description == "Work started — 1 item(s) consumed"` (Revision 4; as `start_work_order` R7).

### WOM-CAP-03 — a Borrow line leaves and comes back in the same call
- **Rules:** `complete_as_planned` R6, R9; `_apply_item_completion` R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S(F1, I3, 5, Decimal("1.00")).
2. O = order "1", but stamped, `planned_date D(8)`.
3. status row(M1, "RUNNING", T0).
4. line(O, I3, "1"), but `action_type "BORROW"`.

**When**
- `result = WOM.complete_as_planned(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.status == "COMPLETED"`.
2. re-read: `[r.transaction_type for r in led(F1, I3, STORAGE)] == ["consumption", "work_order_borrow_returned"]`.
3. re-read: `qty(F1, I3, STORAGE) == Decimal("5")`.

### WOM-CAP-04 — a planned date of today is allowed
- **Rules:** `complete_as_planned` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `planned_date D(10)`, `machine_id None`.

**When**
- `result = WOM.complete_as_planned(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.status == "COMPLETED"`.
2. re-read O: `completed_at == NOON(10)`.

### WOM-CAP-05 — a planned date tomorrow is refused
- **Rules:** `complete_as_planned` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `planned_date D(11)`.

**When**
- `WOM.complete_as_planned(db, O.id, W1.id, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Complete as planned is only allowed when the planned date is today or in the past"`.
4. session clean.
5. nothing written.

### WOM-CAP-06 — an order that is not a draft is refused
- **Rules:** `complete_as_planned` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started.

**When**
- `WOM.complete_as_planned(db, O.id, W1.id, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order must be in draft to complete as planned"`.
4. nothing written.

### WOM-CAP-07 — an order with no planned date is refused
- **Rules:** `complete_as_planned` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `planned_date None`.

**When**
- `WOM.complete_as_planned(db, O.id, W1.id, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order must have a planned date"`.
4. nothing written.

### WOM-CAP-08 — unmet approvals are refused
- **Rules:** `complete_as_planned` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but `planned_date D(8)`.
2. approver(O, U2).

**When**
- `WOM.complete_as_planned(db, O.id, W1.id, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Assigned approvers must approve before work can be completed"`.
4. nothing written.

### WOM-CAP-09 — status is checked before the planned date
- **Rules:** `complete_as_planned` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started, `planned_date None`.

**When**
- `WOM.complete_as_planned(db, O.id, W1.id, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Work order must be in draft to complete as planned"`.

### WOM-CAP-10 — a missing planned date is reported before unmet approvals
- **Rules:** `complete_as_planned` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but `planned_date None`.
2. approver(O, U2).

**When**
- `WOM.complete_as_planned(db, O.id, W1.id, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Work order must have a planned date"`.

### WOM-CAP-11 — a future date is reported before unmet approvals
- **Rules:** `complete_as_planned` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but `planned_date D(11)`.
2. approver(O, U2).

**When**
- `WOM.complete_as_planned(db, O.id, W1.id, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Complete as planned is only allowed when the planned date is today or in the past"`.

### WOM-CAP-12 — notes, machine status and workers are passed to the completion
- **Rules:** `complete_as_planned` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `planned_date D(8)`.
2. status row(M1, "RUNNING", T0).

**When**
- `result = WOM.complete_as_planned(db, O.id, W1.id, U2.id, completion_notes="Done", machine_status=MachineEventTypeEnum.IDLE, completed_by_user_ids=[U3.id])`.

**Then**
1. returns: `result.status == "COMPLETED"`.
2. re-read O: `completion_notes == "Done"`, `completed_by == U3.id`, `completed_by_names == "Sara Khan"`.
3. event: `stat(M1) == ["MAINTENANCE", "IDLE"]`.
4. event: `evrow(O, "completed").metadata_json["recorded_by"] == U2.id`.

### WOM-CAP-13 — the order row is locked before its state is checked
- **Rules:** `complete_as_planned` R11 [BUG-2916]
- **Kind:** bug
- **Expect:** xfail BUG-2916
- **Fails today on:** Then 2 (no `FOR UPDATE` is sent)

**Given**
1. O = order "1", but stamped, `planned_date D(8)`, `machine_id None`.
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = WOM.complete_as_planned(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.status == "COMPLETED"`.
2. statement: locks first `work_orders`.

### WOM-CAP-14 — complete as planned flushes and never commits
- **Rules:** `complete_as_planned` R10
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order "1", but stamped, `planned_date D(8)`, `machine_id None`.

**When**
- commit spy around `result = WOM.complete_as_planned(db, O.id, W1.id, U2.id)`.

**Then**
1. inside: `result.status == "COMPLETED"`.
2. inside: `cm.call_count == 0`.
3. after: re-read O: `status == "DRAFT"`.

### WOM-CAP-15 — with no stock lines the started event says nothing was consumed
- **Rules:** `complete_as_planned` R8; `start_work_order` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `planned_date D(8)`, `machine_id None`.

**When**
- `result = WOM.complete_as_planned(db, O.id, W1.id, U2.id)`.

**Then**
1. returns: `result.status == "COMPLETED"`.
2. event: `[t for t, _ in ev(O)] == ["started", "completed"]`.
3. event: `evrow(O, "started").description == "Work started — no inventory items to consume"`.
4. event: `evrow(O, "started").metadata_json["items_consumed"] == 0`.

### WOM-CAP-16 — the caller is the performer of both events and the machine entries, not the worker
- **Rules:** `complete_as_planned` R8, R9; `finalize_completion` R6, R7, R9; G18 (performer)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `planned_date D(8)` (created by U1).
2. status row(M1, "RUNNING", T0).

**When**
- `result = WOM.complete_as_planned(db, O.id, W1.id, U2.id, completed_by_user_ids=[U3.id])`.

**Then**
1. returns: `result.status == "COMPLETED"`.
2. event: `evrow(O, "started").performed_by == U2.id`, `evrow(O, "completed").performed_by == U2.id`.
3. event: `evrow(O, "completed").metadata_json["recorded_by"] == U2.id`.
4. event: every new `MachineActivityEvent` row of M1 (`status_updated` ×2, `work_order_completed`) has `performed_by == U2.id`.

## `WorkOrderManager.finalize_completion`

### WOM-FC-01 — the order is completed by the performer and the completer rows are written
- **Rules:** `finalize_completion` R2, R3, R4, R11; `_resolve_completion_workers` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. status row(M1, "RUNNING", T0).
3. status row(M1, "MAINTENANCE", T1).
4. event(O, "started", {"previous_machine_status": "RUNNING"}, T1).

**When**
- `result = FIN(O)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `status == "COMPLETED"`, `completed_by == U2.id`, `completed_by_names == "Rahim Uddin"`, `completed_at == NOW`, `completion_notes is None`.
3. count: `[c.user_id for c in WorkOrderCompleter rows with work_order_id == O.id] == [U2.id]`.

### WOM-FC-02 — the completed event carries schedule and workers
- **Rules:** `finalize_completion` R9
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. status row(M1, "RUNNING", T0).
3. status row(M1, "MAINTENANCE", T1).
4. event(O, "started", {"previous_machine_status": "RUNNING"}, T1).

**When**
- `result = FIN(O)`.

**Then**
1. returns: `result.id == O.id`.
2. event: `ev(O) == [("completed", f"Work order {NUM(O)} marked complete")]`.
3. event: `evrow(O, "completed").metadata_json == {"completed_at": "2026-03-10T09:00:00", "planned_date": "2026-03-01", "variance_days": 9, "variance_label": "9 days late", "completed_by_names": "Rahim Uddin", "completed_by_name": "Rahim Uddin", "completed_by_user_ids": [U2.id], "completed_by": U2.id}`.

### WOM-FC-03 — the machine returns to its status before start and logs the completion
- **Rules:** `finalize_completion` R6, R7 (✅ Q9)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. status row(M1, "RUNNING", T0).
3. status row(M1, "MAINTENANCE", T1).
4. event(O, "started", {"previous_machine_status": "RUNNING"}, T1).

**When**
- `result = FIN(O)`.

**Then**
1. returns: `result.id == O.id`.
2. event: `stat(M1) == ["RUNNING"]`.
3. event: `("work_order_completed", f"Work order completed: {NUM(O)} — Service — Lathe 3") in acts(M1)`.
4. event: the `work_order_completed` row's `metadata_json == {"work_order_id": O.id}`.

### WOM-FC-04 — someone else did the work: recorded_by is the performer
- **Rules:** `finalize_completion` R3, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started, `machine_id None`.

**When**
- `result = FIN(O, completed_by_user_ids=[U3.id])`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `completed_by == U3.id`, `completed_by_names == "Sara Khan"`.
3. event: `evrow(O, "completed").metadata_json["recorded_by"] == U2.id`.
4. event: `"completed_by" not in evrow(O, "completed").metadata_json`.

### WOM-FC-05 — no matched completer: no completed_by, neither key in the event
- **Rules:** `finalize_completion` R3, R4, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started, `machine_id None`.

**When**
- `result = FIN(O, completed_by_names="Ghost")`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `completed_by is None`, `completed_by_names == "Ghost"`.
3. count: `work_order_completers` with `work_order_id == O.id` has 0 rows.
4. event: `"recorded_by" not in evrow(O, "completed").metadata_json`.
5. event: `"completed_by" not in evrow(O, "completed").metadata_json`.

### WOM-FC-06 — a given completion time and extra metadata are used
- **Rules:** `finalize_completion` R3, R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but started, `machine_id None`.

**When**
- `result = FIN(O, completed_at=datetime(2026, 3, 9, 17, 0, 0), event_metadata_extra={"completion_mode": "manual"})`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `completed_at == datetime(2026, 3, 9, 17, 0, 0)`.
3. event: `evrow(O, "completed").metadata_json["completed_at"] == "2026-03-09T17:00:00"`, `["variance_label"] == "8 days late"`, `["completion_mode"] == "manual"`.

### WOM-FC-07 — completion notes replace the stored ones
- **Rules:** `finalize_completion` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but started, `machine_id None`, `completion_notes "Half done"`.

**When**
- `result = FIN(O, completion_notes="Done")`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `completion_notes == "Done"`.

### WOM-FC-08 — empty notes clear them; no notes keep them
- **Rules:** `finalize_completion` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started, `machine_id None`, `completion_notes "Half done"`.
2. P = order "2", but started, `machine_id None`, `completion_notes "Half done"`.

**When**
- `result = (FIN(O, completion_notes=""), FIN(P))`.

**Then**
1. returns: `result[0].id == O.id`.
2. re-read O: `completion_notes == ""`.
3. re-read P: `completion_notes == "Half done"`.

### WOM-FC-09 — there is no state check of its own: a draft is completed
- **Rules:** `finalize_completion` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `machine_id None`.

**When**
- `result = FIN(O)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `status == "COMPLETED"`.

### WOM-FC-10 — a completer who is not an active member stops the call before any write
- **Rules:** `finalize_completion` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started.

**When**
- `FIN(O, completed_by_user_ids=[U4.id])`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.
4. session clean.
5. nothing written.

### WOM-FC-11 — a repeated completer id gives one completer row
- **Rules:** `finalize_completion` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started, `machine_id None`.

**When**
- `result = FIN(O, completed_by_user_ids=[U3.id, U3.id])`.

**Then**
1. returns: `result.id == O.id`.
2. count: `[c.user_id for c in WorkOrderCompleter rows with work_order_id == O.id] == [U3.id]`.
3. event: `evrow(O, "completed").metadata_json["completed_by_user_ids"] == [U3.id, U3.id]`.

### WOM-FC-12 — live Install lines are installed; deleted ones are not
- **Rules:** `finalize_completion` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. status row(M1, "MAINTENANCE", T1).
3. event(O, "started", {"previous_machine_status": "RUNNING"}, T1).
4. line(O, I1, "2"), but `action_type "INSTALL"`, consumed(5.00).
5. line(O, I2, "1"), but `action_type "INSTALL"`, consumed(2.50), gone.

**When**
- `result = FIN(O)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read: `mqty(M1, I1) == Decimal("2")`.
3. re-read: `mqty(M1, I2) == Decimal("0")`.

### WOM-FC-13 — a chosen machine status wins over the status before start
- **Rules:** `finalize_completion` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. status row(M1, "MAINTENANCE", T1).
3. event(O, "started", {"previous_machine_status": "RUNNING"}, T1).

**When**
- `result = FIN(O, machine_status=MachineEventTypeEnum.IDLE)`.

**Then**
1. returns: `result.id == O.id`.
2. event: `stat(M1) == ["IDLE"]`.

### WOM-FC-14 — no started event: the machine goes idle
- **Rules:** `finalize_completion` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. status row(M1, "MAINTENANCE", T1).

**When**
- `result = FIN(O)`.

**Then**
1. returns: `result.id == O.id`.
2. event: `stat(M1) == ["IDLE"]`.

### WOM-FC-15 — a machine already in maintenance before start stays in it
- **Rules:** `finalize_completion` R7 (✅ Q9)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. status row(M1, "MAINTENANCE", T0).
3. event(O, "started", {"previous_machine_status": "MAINTENANCE"}, T1).

**When**
- `result = FIN(O)`.

**Then**
1. returns: `result.id == O.id`.
2. event: `stat(M1) == []`.

### WOM-FC-16 — a stored status that is not a machine status raises ValueError
- **Rules:** `finalize_completion` R7
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. status row(M1, "MAINTENANCE", T1).
3. event(O, "started", {"previous_machine_status": "BOGUS"}, T1).

**When**
- `FIN(O)` inside `pytest.raises(ValueError)`.

**Then**
1. raises: `ValueError`.

### WOM-FC-17 — a component order logs the completion and notes on the component (revisit after launch)
- **Rules:** `finalize_completion` R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but started, `machine_id None`, `project_component_id PC1.id`, `title "Service — Panel A"`.

**When**
- `result = FIN(O, completion_notes="Done")`.

**Then**
1. returns: `result.id == O.id`.
2. event: `[(r.event_type, r.description) for r in pcacts(PC1)] == [("work_order_completed", f"Work order {NUM(O)} completed: Service — Panel A. Done")]`.

### WOM-FC-18 — without notes the component entry has no suffix (revisit after launch)
- **Rules:** `finalize_completion` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started, `machine_id None`, `project_component_id PC1.id`, `title "Service — Panel A"`.

**When**
- `result = FIN(O)`.

**Then**
1. returns: `result.id == O.id`.
2. event: `[r.description for r in pcacts(PC1)] == [f"Work order {NUM(O)} completed: Service — Panel A"]`.

### WOM-FC-19 — a component of another workspace gets no entry
- **Rules:** `finalize_completion` R8 [BUG-1884]
- **Kind:** bug
- **Expect:** xfail BUG-1884
- **Fails today on:** Then 2 (today an entry is written for PC9)

**Given**
1. O = order "1", but started, `machine_id None`, `project_component_id PC9.id` (invalid data).

**When**
- `result = FIN(O)`.

**Then**
1. returns: `result.id == O.id`.
2. count: `project_component_activity_events` has 0 rows with `id > mark`.

### WOM-FC-20 — a component of another workspace does not stop the completion
- **Rules:** `finalize_completion` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started, `machine_id None`, `project_component_id PC9.id` (invalid data).

**When**
- `result = FIN(O)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `status == "COMPLETED"`.

### WOM-FC-21 — without a machine, Install / Replace / Borrow lines do nothing at completion
- **Rules:** `finalize_completion` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S(F1, I3, 4, Decimal("1.00")).
2. O = order "1", but started, `machine_id None`.
3. line(O, I1, "2"), but `action_type "INSTALL"`, consumed(5.00).
4. line(O, I3, "1"), but `action_type "BORROW"`, consumed(2.50).

**When**
- `result = FIN(O)`.

**Then**
1. returns: `result.status == "COMPLETED"`.
2. count: `machine_item_ledger` has 0 rows with `id > mark`.
3. count: `led(F1, I3, STORAGE) == []`.

### WOM-FC-23 — finalize flushes and never commits
- **Rules:** `finalize_completion` R3
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order "1", but started, `machine_id None`.

**When**
- commit spy around `result = FIN(O)`.

**Then**
1. inside: `result.status == "COMPLETED"`.
2. inside: `cm.call_count == 0`.
3. after: re-read O: `status == "IN_PROGRESS"`.

### WOM-FC-24 — the recorder, not the worker, is the performer of the event, the machine entries and the postings
- **Rules:** `finalize_completion` R5, R6, R7, R9; G18 (performer, ledger source)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but started (created and started by U1).
2. status row(M1, "RUNNING", T0).
3. status row(M1, "MAINTENANCE", T1).
4. event(O, "started", {"previous_machine_status": "RUNNING"}, T1).
5. L = line(O, I1, "2"), but `action_type "INSTALL"`, consumed(5.00).

**When**
- `result = FIN(O, completed_by_user_ids=[U3.id])`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `completed_by == U3.id`.
3. event: `evrow(O, "completed").performed_by == U2.id`, `metadata_json["recorded_by"] == U2.id`.
4. event: the new `work_order_completed` row of M1 has `performed_by == U2.id` and `metadata_json == {"work_order_id": O.id}`.
5. event: the new `status_updated` row of M1 has `performed_by == U2.id`.
6. re-read: `[(r.transaction_type, r.quantity) for r in mled(M1, I1)] == [("work_order_install", Decimal("2"))]`.
7. re-read: `all((r.source_type, r.source_id, r.performed_by) == ("work_order", O.id, U2.id) for r in mled(M1, I1))` (G18: ledger source and performer).

## `WorkOrderManager.void_work_order`

### WOM-V-01 — a started order gets its consumed stock back
- **Rules:** `void_work_order` R4, R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. S(F1, I1, 7, Decimal("2.50")).
2. O = order "1", but started.
3. status row(M1, "MAINTENANCE", T1).
4. event(O, "started", {"previous_machine_status": "RUNNING"}, T1).
5. L = line(O, I1, "3"), but consumed(7.50).

**When**
- `result = WOM.void_work_order(db, O.id, W1.id, U2.id, "Wrong machine")`.

**Then**
1. returns: `result.id == O.id`.
2. re-read: `qty(F1, I1, STORAGE) == Decimal("10")`.
3. re-read L: `consumed_at is None`, `is_deleted is False`.

### WOM-V-02 — the order is voided with its note and logged
- **Rules:** `void_work_order` R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. status row(M1, "MAINTENANCE", T1).
3. event(O, "started", {"previous_machine_status": "RUNNING"}, T1).

**When**
- `result = WOM.void_work_order(db, O.id, W1.id, U2.id, "Wrong machine")`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `status == "VOIDED"`, `void_note == "Wrong machine"`, `voided_at == NOW`, `voided_by == U2.id`.
3. event: `ev(O) == [("voided", f"Work order {NUM(O)} voided. Reason: Wrong machine")]`.
4. event: `evrow(O, "voided").metadata_json == {"void_note": "Wrong machine"}`.

### WOM-V-03 — the machine returns to its status before start
- **Rules:** `void_work_order` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. status row(M1, "MAINTENANCE", T1).
3. event(O, "started", {"previous_machine_status": "RUNNING"}, T1).

**When**
- `result = WOM.void_work_order(db, O.id, W1.id, U2.id, "Wrong machine")`.

**Then**
1. returns: `result.id == O.id`.
2. event: `stat(M1) == ["RUNNING"]`.

### WOM-V-04 — with no status before start the machine goes idle
- **Rules:** `void_work_order` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. status row(M1, "MAINTENANCE", T1).

**When**
- `result = WOM.void_work_order(db, O.id, W1.id, U2.id, "Wrong machine")`.

**Then**
1. returns: `result.id == O.id`.
2. event: `stat(M1) == ["IDLE"]`.

### WOM-V-05 — a draft is voided with no stock or machine change
- **Rules:** `void_work_order` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but stamped.
3. status row(M1, "RUNNING", T0).
4. L = line(O, I1, "3").

**When**
- `result = WOM.void_work_order(db, O.id, W1.id, U2.id, "Not needed")`.

**Then**
1. returns: `result.status == "VOIDED"`.
2. count: `led(F1, I1, STORAGE) == []`.
3. count: `acts(M1) == []`.
4. unchanged: unchanged(L).

### WOM-V-06 — voiding clears the approvals but keeps the order's stamp
- **Rules:** `void_work_order` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but `approved_by U2.id`, `approved_at T0`.
2. A = approver(O, U2), but approved.

**When**
- `result = WOM.void_work_order(db, O.id, W1.id, U2.id, "Not needed")`.

**Then**
1. returns: `result.status == "VOIDED"`.
2. re-read A: `approved is False`, `approved_at is None`.
3. re-read O: `approved_by == U2.id`, `approved_at == T0`.
4. event: `ev(O) == [("approvals_reset", "Work order voided (1 approval(s) cleared)"), ("voided", f"Work order {NUM(O)} voided. Reason: Not needed")]`.

### WOM-V-07 — a completed order cannot be voided
- **Rules:** `void_work_order` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but completed.

**When**
- `WOM.void_work_order(db, O.id, W1.id, U2.id, "Late")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot void a completed work order"`.
4. session clean.
5. nothing written.

### WOM-V-08 — a voided order cannot be voided again
- **Rules:** `void_work_order` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but voided.

**When**
- `WOM.void_work_order(db, O.id, W1.id, U2.id, "Again")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order is already voided"`.
4. unchanged: unchanged(O).

### WOM-V-09 — an order of W2 is not found
- **Rules:** `void_work_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order "9", but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `machine_id M9.id`.

**When**
- `WOM.void_work_order(db, O9.id, W1.id, U2.id, "x")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order with ID {O9.id} not found"`.
4. unchanged: unchanged(O9).

### WOM-V-10 — a deleted consumed line is not returned
- **Rules:** `void_work_order` R4 (live lines)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S(F1, I1, 7, Decimal("2.50")).
2. O = order "1", but started, `machine_id None`.
3. L = line(O, I1, "3"), but consumed(7.50), gone.

**When**
- `result = WOM.void_work_order(db, O.id, W1.id, U2.id, "x")`.

**Then**
1. returns: `result.status == "VOIDED"`.
2. re-read: `qty(F1, I1, STORAGE) == Decimal("7")`.
3. unchanged: unchanged(L).

### WOM-V-11 — consume 3, adjust to 4, void: all 4 come back
- **Rules:** `void_work_order` R4; `_reverse_item_consumption` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S(F1, I1, 6, Decimal("2.50")).
2. O = order "1", but started, `machine_id None`.
3. L = line(O, I1, "4"), but consumed(10.00).

**When**
- `result = WOM.void_work_order(db, O.id, W1.id, U2.id, "x")`.

**Then**
1. returns: `result.status == "VOIDED"`.
2. re-read: `qty(F1, I1, STORAGE) == Decimal("10")`.
3. re-read: `[(r.quantity, r.unit_cost) for r in led(F1, I1, STORAGE)] == [(Decimal("4"), Decimal("2.50"))]`.

### WOM-V-17 — a live line that was never consumed is skipped; the consumed one comes back
- **Rules:** `void_work_order` R4 (only consumed live lines)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S(F1, I1, 7, Decimal("2.50")). S(F1, I2, 5, Decimal("1.00")).
2. O = order "1", but started, `machine_id None`.
3. L1 = line(O, I1, "3"), but consumed(7.50).
4. L2 = line(O, I2, "2") (live, `consumed_at None`).

**When**
- `result = WOM.void_work_order(db, O.id, W1.id, U2.id, "x")`.

**Then**
1. returns: `result.status == "VOIDED"`.
2. re-read: `qty(F1, I1, STORAGE) == Decimal("10")`.
3. re-read: `qty(F1, I2, STORAGE) == Decimal("5")` and `led(F1, I2, STORAGE) == []`.
4. unchanged: unchanged(L2).

### WOM-V-18 — the voider is the performer of the event, the status change and the reversal
- **Rules:** `void_work_order` R4, R5, R8; `_reverse_item_consumption` R2; G18 (performer, ledger source)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S(F1, I1, 7, Decimal("2.50")).
2. O = order "1", but started (created and started by U1).
3. status row(M1, "MAINTENANCE", T1).
4. event(O, "started", {"previous_machine_status": "RUNNING"}, T1).
5. L = line(O, I1, "3"), but consumed(7.50) (consumed by U1).

**When**
- `result = WOM.void_work_order(db, O.id, W1.id, U2.id, "Wrong machine")`.

**Then**
1. returns: `result.status == "VOIDED"`.
2. event: `evrow(O, "voided").performed_by == U2.id`.
3. event: the new `status_updated` row of M1 has `performed_by == U2.id`.
4. re-read: `[(r.transaction_type, r.quantity, r.unit_cost, r.notes) for r in led(F1, I1, STORAGE)] == [("consumption_reversal", Decimal("3"), Decimal("2.50"), f"{NUM(O)} voided — Bolt returned")]`.
5. re-read: `all((r.source_type, r.source_id, r.performed_by) == ("work_order", O.id, U2.id) for r in led(F1, I1, STORAGE))` (G18: ledger source and performer).

### WOM-V-12 — a blank void reason is refused by the schema
- **Rules:** `void_work_order` R8 [BUG-2918]
- **Kind:** bug
- **Expect:** xfail BUG-2918
- **Fails today on:** Then 1 (the schema accepts "  ")

**Given**
1. No rows beyond the standing rows.

**When**
- build `WorkOrderVoidRequest(void_note="  ")` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: message contains `"void_note"`.

### WOM-V-13 — the void reason is trimmed by the schema
- **Rules:** `void_work_order` R8 [BUG-2918]
- **Kind:** bug
- **Expect:** xfail BUG-2918
- **Fails today on:** Then 1 (today the padding is kept)

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WorkOrderVoidRequest(void_note="  Wrong machine  ")` (target `schema`).

**Then**
1. returns: `result.void_note == "Wrong machine"`.

### WOM-V-14 — a plain reason is accepted by the schema
- **Rules:** `void_work_order` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WorkOrderVoidRequest(void_note="Wrong machine")` (target `schema`).

**Then**
1. returns: `result.void_note == "Wrong machine"`.

### WOM-V-15 — the order row is locked before its state is checked
- **Rules:** `void_work_order` R10 [BUG-2916]
- **Kind:** bug
- **Expect:** xfail BUG-2916
- **Fails today on:** Then 2 (no `FOR UPDATE` is sent)

**Given**
1. O = order "1", but stamped, `machine_id None`.
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = WOM.void_work_order(db, O.id, W1.id, U2.id, "x")`.

**Then**
1. returns: `result.status == "VOIDED"`.
2. statement: locks first `work_orders`.

### WOM-V-16 — void flushes and never commits
- **Rules:** `void_work_order` R8
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order "1", but stamped, `machine_id None`.

**When**
- commit spy around `result = WOM.void_work_order(db, O.id, W1.id, U2.id, "x")`.

**Then**
1. inside: `result.status == "VOIDED"`.
2. inside: `cm.call_count == 0`.
3. after: re-read O: `status == "DRAFT"`.

## `WorkOrderManager._ensure_catalog_item_not_on_wo`

### WOM-ECI-01 — a live line with the item is a conflict
- **Rules:** `_ensure_catalog_item_not_on_wo` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".
2. line(O, I1, "1").

**When**
- `WOM._ensure_catalog_item_not_on_wo(db, O.id, I1.id, W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Bolt is already on this order"`.

### WOM-ECI-02 — a deleted line, an excluded line or a line of another order is no conflict
- **Rules:** `_ensure_catalog_item_not_on_wo` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".
2. line(O, I1, "1"), but gone.
3. LX = line(O, I2, "1").
4. P = order "2".
5. line(P, I3, "1").

**When**
- `result = (WOM._ensure_catalog_item_not_on_wo(db, O.id, I1.id, W1.id), WOM._ensure_catalog_item_not_on_wo(db, O.id, I2.id, W1.id, exclude_item_id=LX.id), WOM._ensure_catalog_item_not_on_wo(db, O.id, I3.id, W1.id))`.

**Then**
1. returns: `result == (None, None, None)`.

## `WorkOrderManager._guard_item_mutations`

### WOM-GIM-01 — an order without stock items is refused first, even when completed
- **Rules:** `_guard_item_mutations` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but completed, `uses_inventory False`.

**When**
- `WOM._guard_item_mutations(O)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "This work order does not use stock items"`.

### WOM-GIM-02 — completed and voided orders are refused
- **Rules:** `_guard_item_mutations` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but completed.
2. P = order "2", but voided.

**When**
- `result = []`; for `x in [O, P]`: call `WOM._guard_item_mutations(x)` inside `pytest.raises(HTTPException)` and append `(exc.value.status_code, exc.value.detail)`.

**Then**
1. returns: `result == [(400, "Work order is completed"), (400, "Work order is voided")]`.

### WOM-GIM-03 — drafts and started orders pass
- **Rules:** `_guard_item_mutations` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".
2. P = order "2", but started.

**When**
- `result = (WOM._guard_item_mutations(O), WOM._guard_item_mutations(P))`.

**Then**
1. returns: `result == (None, None)`.

## `WorkOrderManager.add_item`

### WOM-AI-01 — a stock line is added to a draft and logged
- **Rules:** `add_item` R1, R8, R9 (G17), R13
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = ADD(ITEM(O))`.

**Then**
1. returns: `isinstance(result, WorkOrderItem)` and `result.id is not None`.
2. re-read result: `work_order_id == O.id`, `item_id == I1.id`, `quantity == Decimal("2.00")`, `uses_inventory is True`, `workspace_id == W1.id`, `created_by == U2.id`.
3. re-read result: `source_location_type == "storage"`, `source_location_id == F1.id`, `action_type == "CONSUME"`, `replaced_item_id is None`, `notes is None`, `consumed_at is None`.
4. event: `ev(O) == [("item_added", "Added 2 Bolt")]` (G17: the quantity as sent).
5. event: `evrow(O, "item_added").metadata_json == {"item_id": I1.id, "item_name": "Bolt"}`.

### WOM-AI-02 — a line that does not use inventory needs no source
- **Rules:** `add_item` R2, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = ADD(ITEM(O, uses_inventory=False, source_location_type=None, source_location_id=None, notes="Spare"))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `uses_inventory is False`, `source_location_type is None`, `notes == "Spare"`.

### WOM-AI-03 — an order of W2 is not found
- **Rules:** `add_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order "9", but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `machine_id M9.id`.

**When**
- `ADD(ITEM(O9))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order with ID {O9.id} not found"`.
4. nothing written.

### WOM-AI-04 — an order without stock items takes no line
- **Rules:** `add_item` R1; `_guard_item_mutations` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `uses_inventory False`.

**When**
- `ADD(ITEM(O))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "This work order does not use stock items"`.
4. session clean.
5. nothing written.

### WOM-AI-05 — a completed order takes no line
- **Rules:** `add_item` R1; `_guard_item_mutations` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but completed.

**When**
- `ADD(ITEM(O))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order is completed"`.
4. nothing written.

### WOM-AI-06 — a stock line without a source type is refused
- **Rules:** `add_item` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `ADD(ITEM(O, source_location_type=None))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Select a source location for this item"`.
4. nothing written.

### WOM-AI-07 — a stock line without a source id is refused
- **Rules:** `add_item` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `ADD(ITEM(O, source_location_id=None))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Select a source location for this item"`.
4. nothing written.

### WOM-AI-08 — Install needs "uses inventory"
- **Rules:** `add_item` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `ADD(ITEM(O, action_type="INSTALL", uses_inventory=False))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == 'Install requires "uses inventory" to be on'`.
4. nothing written.

### WOM-AI-09 — Replace needs "uses inventory", checked before the replaced item
- **Rules:** `add_item` R3, R7 (order)
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `ADD(ITEM(O, action_type="REPLACE", uses_inventory=False))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == 'Replace requires "uses inventory" to be on'`.
4. nothing written.

### WOM-AI-10 — Borrow needs "uses inventory"
- **Rules:** `add_item` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `ADD(ITEM(O, action_type="BORROW", uses_inventory=False))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == 'Borrow requires "uses inventory" to be on'`.
4. nothing written.

### WOM-AI-11 — Install on an order with no machine is refused
- **Rules:** `add_item` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `machine_id None`.

**When**
- `ADD(ITEM(O, action_type="INSTALL"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Install/Replace/Borrow only apply to work orders that target a machine"`.
4. nothing written.

### WOM-AI-12 — a missing source is reported before the Install rules
- **Rules:** `add_item` R7 (R2 before R3)
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `machine_id None`.

**When**
- `ADD(ITEM(O, action_type="INSTALL", source_location_id=None))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Select a source location for this item"`.

### WOM-AI-13 — Replace without the replaced item is refused
- **Rules:** `add_item` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `ADD(ITEM(O, action_type="REPLACE"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Select the item being replaced"`.
4. nothing written.

### WOM-AI-14 — a replaced item of W2 is not found
- **Rules:** `add_item` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `ADD(ITEM(O, action_type="REPLACE", replaced_item_id=I9.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {I9.id} not found"`.
4. nothing written.

### WOM-AI-15 — a replaced item of W0 is not found
- **Rules:** `add_item` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `ADD(ITEM(O, action_type="REPLACE", replaced_item_id=I0.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {I0.id} not found"`.
4. nothing written.

### WOM-AI-16 — a Replace line with its replaced item is stored
- **Rules:** `add_item` R4, R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = ADD(ITEM(O, action_type="REPLACE", replaced_item_id=I2.id))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `action_type == "REPLACE"`, `replaced_item_id == I2.id`.

### WOM-AI-17 — a replaced item on a Consume line is refused
- **Rules:** `add_item` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `ADD(ITEM(O, replaced_item_id=I2.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "replaced_item_id only applies to Replace"`.
4. nothing written.

### WOM-AI-18 — a replaced item on an Install line is refused
- **Rules:** `add_item` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `ADD(ITEM(O, action_type="INSTALL", replaced_item_id=I2.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "replaced_item_id only applies to Replace"`.

### WOM-AI-19 — quantity 0 is refused by WorkOrderItemCreate
- **Rules:** `add_item` R5a [BUG-2912]
- **Kind:** bug
- **Expect:** xfail BUG-2912
- **Fails today on:** Then 1 (the schema accepts 0)

**Given**
1. O = order "1".

**When**
- build `ITEM(O, quantity=Decimal("0"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: message contains `"quantity"`.

### WOM-AI-20 — a negative quantity is refused by WorkOrderItemCreate
- **Rules:** `add_item` R5a [BUG-2912]
- **Kind:** bug
- **Expect:** xfail BUG-2912
- **Fails today on:** Then 1 (the schema accepts -2)

**Given**
1. O = order "1".

**When**
- build `ITEM(O, quantity=Decimal("-2"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: message contains `"quantity"`.

### WOM-AI-21 — a quantity with 3 decimals is refused by WorkOrderItemCreate
- **Rules:** `add_item` R5a [BUG-2913]
- **Kind:** bug
- **Expect:** xfail BUG-2913
- **Fails today on:** Then 1 (the schema accepts 1.005)

**Given**
1. O = order "1".

**When**
- build `ITEM(O, quantity=Decimal("1.005"), uses_inventory=False)` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: message contains `"quantity"`.

### WOM-AI-22 — the smallest positive quantity and the default are accepted; an unknown action is not
- **Rules:** `add_item` R5a; Inputs (`action_type`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `result = (ITEM(O, quantity=Decimal("0.01")), WorkOrderItemCreate(work_order_id=O.id, item_id=I1.id))` (target `schema`).

**Then**
1. returns: `result[0].quantity == Decimal("0.01")`.
2. returns: `result[1].quantity == 1`, `result[1].uses_inventory is False`, `result[1].action_type == "CONSUME"`.
3. raises: building `ITEM(O, action_type="SWAP")` raises `ValidationError`.

### WOM-AI-23 — a fractional stock line is refused when added
- **Rules:** `add_item` R5b [BUG-2914]
- **Kind:** bug
- **Expect:** xfail BUG-2914
- **Fails today on:** Then 1 (no error is raised: the 2.5 line is stored)

**Given**
1. O = order "1", but stamped.

**When**
- `ADD(ITEM(O, quantity=Decimal("2.5")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Bolt has a fractional quantity; inventory consumption requires whole units"`.
4. session clean.
5. nothing written.

### WOM-AI-24 — a fractional line that does not use inventory is accepted
- **Rules:** `add_item` R5b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = ADD(ITEM(O, quantity=Decimal("2.5"), uses_inventory=False, source_location_type=None, source_location_id=None))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `quantity == Decimal("2.50")`.

### WOM-AI-25 — the same item twice is a conflict
- **Rules:** `add_item` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. line(O, I1, "1").

**When**
- `ADD(ITEM(O))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Bolt is already on this order"`.
4. nothing written.

### WOM-AI-26 — a deleted line of the item does not block a new one
- **Rules:** `add_item` R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. line(O, I1, "1"), but gone.

**When**
- `result = ADD(ITEM(O))`.

**Then**
1. returns: `result.id is not None`.
2. count: `work_order_items` with `work_order_id == O.id` and `is_deleted False` has 1 row.

### WOM-AI-27 — a source factory of W2 is refused at add
- **Rules:** `add_item` R6a [BUG-2927]
- **Kind:** bug
- **Expect:** xfail BUG-2927
- **Fails today on:** Then 1 (no error is raised: the source is stored)

**Given**
1. O = order "1", but stamped.

**When**
- `ADD(ITEM(O, source_location_id=F9.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {F9.id} not found"`.
4. nothing written.

### WOM-AI-28 — a source machine of W2 is refused at add
- **Rules:** `add_item` R6a [BUG-2927]
- **Kind:** bug
- **Expect:** xfail BUG-2927
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. O = order "1", but stamped.

**When**
- `ADD(ITEM(O, source_location_type="machine", source_location_id=M9.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
4. nothing written.

### WOM-AI-29 — a soft-deleted source factory of W1 is refused at add
- **Rules:** `add_item` R6a [BUG-2927]
- **Kind:** bug
- **Expect:** xfail BUG-2927
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. FD = `Factory(workspace_id=W1.id, name="Old Plant", abbreviation="OP")`, but gone.
2. O = order "1", but stamped.

**When**
- `ADD(ITEM(O, source_location_id=FD.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {FD.id} not found"`.
4. nothing written.

### WOM-AI-30 — an unknown source type is refused at add
- **Rules:** `add_item` R6a [BUG-2927]
- **Kind:** bug
- **Expect:** xfail BUG-2927
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. O = order "1", but stamped.

**When**
- `ADD(ITEM(O, source_location_type="shelf"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Unsupported source location type: shelf"`.
4. nothing written.

### WOM-AI-31 — another live factory or machine of W1 is a valid source
- **Rules:** `add_item` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = (ADD(ITEM(O, source_location_id=F2.id)), ADD(ITEM(O, item_id=I2.id, source_location_type="machine", source_location_id=M2.id)))`.

**Then**
1. returns: `result[0].id is not None`, `result[1].id is not None`.
2. re-read result[0]: `source_location_id == F2.id`.
3. re-read result[1]: `source_location_type == "machine"`, `source_location_id == M2.id`.

### WOM-AI-32 — a duplicate is reported before a foreign source
- **Rules:** `add_item` R7 (R6 before R6a)
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. line(O, I1, "1").

**When**
- `ADD(ITEM(O, source_location_id=F9.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Bolt is already on this order"`.

### WOM-AI-33 — a fractional quantity is reported before a duplicate
- **Rules:** `add_item` R7 (R5b before R6) [BUG-2914]
- **Kind:** bug
- **Expect:** xfail BUG-2914
- **Fails today on:** Then 2 (today the 409 duplicate is raised)

**Given**
1. O = order "1", but stamped.
2. line(O, I1, "1").

**When**
- `ADD(ITEM(O, quantity=Decimal("2.5")))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Bolt has a fractional quantity; inventory consumption requires whole units"`.

### WOM-AI-34 — adding to an approved draft clears the approvals
- **Rules:** `add_item` R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but `approved_by U2.id`, `approved_at T0`.
2. A = approver(O, U2), but approved.

**When**
- `result = ADD(ITEM(O))`.

**Then**
1. returns: `result.id is not None`.
2. re-read A: `approved is False`, `approved_at is None`.
3. event: `("approvals_reset", "Items edited (1 approval(s) cleared)") in ev(O)`.

### WOM-AI-35 — adding to a started order consumes the line at once
- **Rules:** `add_item` R11
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but started.

**When**
- `result = ADD(ITEM(O))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `consumed_at == NOW`, `consumed_by == U2.id`, `total_cost == Decimal("5.00")`.
3. re-read: `qty(F1, I1, STORAGE) == Decimal("8")`.

### WOM-AI-36 — an item of W2 is not found
- **Rules:** `add_item` R12 [BUG-1016]
- **Kind:** bug
- **Expect:** xfail BUG-1016
- **Fails today on:** Then 1 (no error is raised: the foreign item is stored)

**Given**
1. O = order "1", but stamped.

**When**
- `ADD(ITEM(O, item_id=I9.id, uses_inventory=False, source_location_type=None, source_location_id=None))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {I9.id} not found"`.
4. nothing written.

### WOM-AI-37 — on a started order the order row is locked before the state check
- **Rules:** `add_item` R14 [BUG-2916]
- **Kind:** bug
- **Expect:** xfail BUG-2916
- **Fails today on:** Then 2 (no `FOR UPDATE` is sent)

**Given**
1. O = order "1", but started.
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = ADD(ITEM(O, uses_inventory=False, source_location_type=None, source_location_id=None))`.

**Then**
1. returns: `result.id is not None`.
2. statement: locks first `work_orders`.

### WOM-AI-38 — add item flushes and never commits
- **Rules:** `add_item` R8
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order "1", but stamped.

**When**
- commit spy around `result = ADD(ITEM(O))`.

**Then**
1. inside: `result.id is not None`.
2. inside: `cm.call_count == 0`.
3. after: count: `work_order_items` with `work_order_id == O.id` has 0 rows.

## `WorkOrderManager.update_item`

### WOM-UI-01 — a line not yet consumed is written and logged
- **Rules:** `update_item` R2, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. L = line(O, I1, "2").

**When**
- `result = UIT(L, quantity=Decimal("3"), notes="Check")`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `quantity == Decimal("3.00")`, `notes == "Check"`, `updated_by == U2.id`.
3. event: `ev(O) == [("item_updated", f"Item line {L.id} updated")]`.

### WOM-UI-02 — a line of W2 is not found
- **Rules:** `update_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order "9", but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `machine_id M9.id`.
2. L9 = line(O9, I9, "1"), but `workspace_id W2.id`, `source_location_id F9.id`.

**When**
- `UIT(L9, notes="x")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Work order item not found"`.
4. unchanged: unchanged(L9).

### WOM-UI-03 — a deleted line is not found
- **Rules:** `update_item` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. L = line(O, I1, "2"), but gone.

**When**
- `UIT(L, notes="x")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Work order item not found"`.
4. nothing written.

### WOM-UI-04 — a line of a completed order cannot change
- **Rules:** `update_item` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but completed.
2. L = line(O, I1, "2").

**When**
- `UIT(L, notes="x")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order is completed"`.
4. unchanged: unchanged(L).

### WOM-UI-05 — only nulls: the line is returned unchanged
- **Rules:** `update_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. L = line(O, I1, "2").

**When**
- `result = UIT(L, notes=None, quantity=None)`.

**Then**
1. returns: `result.id == L.id`.
2. unchanged: unchanged(L).
3. nothing written.

### WOM-UI-06 — a consumed line cannot change its source
- **Rules:** `update_item` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. S(F1, I1, 7, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "3"), but consumed(7.50).

**When**
- `UIT(L, source_location_id=F2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Consumed lines only support quantity and notes updates"`.
4. unchanged: unchanged(L).
5. nothing written.

### WOM-UI-07 — a consumed line cannot stop using inventory
- **Rules:** `update_item` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. L = line(O, I1, "3"), but consumed(7.50).

**When**
- `UIT(L, uses_inventory=False)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Consumed lines only support quantity and notes updates"`.
4. unchanged: unchanged(L).

### WOM-UI-08 — a consumed line's new quantity moves stock and is logged; approvals stay
- **Rules:** `update_item` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S(F1, I1, 7, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "3"), but consumed(7.50).
4. A = approver(O, U2), but approved.
5. `db.expire(L)` (so the session holds the stored `3.00`; spec Notes G3 recipe).

**When**
- `result = UIT(L, quantity=Decimal("4"))`.

**Then**
1. returns: `result.id == L.id`.
2. re-read: `qty(F1, I1, STORAGE) == Decimal("6")`.
3. re-read L: `quantity == Decimal("4.00")`, `total_cost == Decimal("10.00")`, `updated_by == U2.id`.
4. event: `[t for t, _ in ev(O)] == ["item_quantity_adjusted"]`.
5. event: its description `== "Adjusted Bolt from 3.00 to 4"`.
6. event: `set(evrow(O, "item_quantity_adjusted").metadata_json.keys()) == {"item_id", "old_quantity", "new_quantity"}`.
7. unchanged: unchanged(A).
8. event: `evrow(O, "item_quantity_adjusted").metadata_json["old_quantity"] == "3.00"`, `metadata_json["new_quantity"] == "4"`.

### WOM-UI-09 — a consumed line's notes are written with no event and no stock move
- **Rules:** `update_item` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S(F1, I1, 7, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "3"), but consumed(7.50).

**When**
- `result = UIT(L, quantity=Decimal("3"), notes="Torque checked")`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `notes == "Torque checked"`, `total_cost == Decimal("7.50")`.
3. event: `ev(O) == []`.
4. count: `led(F1, I1, STORAGE) == []`.

### WOM-UI-10 — a changed source of W2 is refused
- **Rules:** `update_item` R7a [BUG-2927]
- **Kind:** bug
- **Expect:** xfail BUG-2927
- **Fails today on:** Then 1 (no error is raised: the source is stored)

**Given**
1. O = order "1", but stamped.
2. L = line(O, I1, "2").

**When**
- `UIT(L, source_location_id=F9.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {F9.id} not found"`.
4. unchanged: unchanged(L).

### WOM-UI-11 — quantity 0 is refused by WorkOrderItemUpdate
- **Rules:** `update_item` R7b [BUG-2912]
- **Kind:** bug
- **Expect:** xfail BUG-2912
- **Fails today on:** Then 1 (the schema accepts 0)

**Given**
1. No rows beyond the standing rows.

**When**
- build `WorkOrderItemUpdate(quantity=Decimal("0"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: message contains `"quantity"`.

### WOM-UI-12 — a quantity with 3 decimals is refused by WorkOrderItemUpdate
- **Rules:** `update_item` R7b [BUG-2913]
- **Kind:** bug
- **Expect:** xfail BUG-2913
- **Fails today on:** Then 1 (the schema accepts 1.005)

**Given**
1. No rows beyond the standing rows.

**When**
- build `WorkOrderItemUpdate(quantity=Decimal("1.005"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: message contains `"quantity"`.

### WOM-UI-13 — 0.01 is accepted by WorkOrderItemUpdate
- **Rules:** `update_item` R7b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WorkOrderItemUpdate(quantity=Decimal("0.01"))` (target `schema`).

**Then**
1. returns: `result.quantity == Decimal("0.01")`.

### WOM-UI-14 — a fractional quantity on a stock line is refused when updated
- **Rules:** `update_item` R7c [BUG-2914]
- **Kind:** bug
- **Expect:** xfail BUG-2914
- **Fails today on:** Then 1 (no error is raised: 2.5 is stored)

**Given**
1. O = order "1", but stamped.
2. L = line(O, I1, "2").

**When**
- `UIT(L, quantity=Decimal("2.5"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == f"Item line {L.id} has a fractional quantity; inventory consumption requires whole units"`.
4. unchanged: unchanged(L).

### WOM-UI-15 — switching a fractional line to inventory is refused
- **Rules:** `update_item` R7c [BUG-2914]
- **Kind:** bug
- **Expect:** xfail BUG-2914
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. O = order "1", but stamped.
2. L = line(O, I1, "2.50"), but `uses_inventory False`.

**When**
- `UIT(L, uses_inventory=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == f"Item line {L.id} has a fractional quantity; inventory consumption requires whole units"`.
4. unchanged: unchanged(L).

### WOM-UI-16 — a fractional quantity on a line that does not use inventory is accepted
- **Rules:** `update_item` R7c
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. L = line(O, I1, "2"), but `uses_inventory False`.

**When**
- `result = UIT(L, quantity=Decimal("2.5"))`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `quantity == Decimal("2.50")`.

### WOM-UI-17 — editing a line of an approved draft clears the approvals
- **Rules:** `update_item` R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but `approved_by U2.id`, `approved_at T0`.
2. A = approver(O, U2), but approved.
3. L = line(O, I1, "2").

**When**
- `result = UIT(L, quantity=Decimal("3"))`.

**Then**
1. returns: `result.id == L.id`.
2. re-read A: `approved is False`, `approved_at is None`.
3. event: `("approvals_reset", "Items edited (1 approval(s) cleared)") in ev(O)`.

### WOM-UI-18 — on a started order a line switched to inventory is consumed now
- **Rules:** `update_item` R9
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S(F1, I1, 10, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "2"), but `uses_inventory False`, `source_location_type None`, `source_location_id None`.

**When**
- `result = UIT(L, uses_inventory=True, source_location_type="storage", source_location_id=F1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `uses_inventory is True`, `consumed_at == NOW`.
3. re-read: `qty(F1, I1, STORAGE) == Decimal("8")`.

### WOM-UI-19 — on a started order a line switched to inventory without a source is refused
- **Rules:** `update_item` R9
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. L = line(O, I1, "2"), but `uses_inventory False`, `source_location_type None`, `source_location_id None`.

**When**
- `UIT(L, uses_inventory=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == f"Item line {L.id} uses inventory but has no source location set"`.

### WOM-UI-20 — a request that changes nothing writes, logs and resets nothing
- **Rules:** `update_item` R10 [BUG-2915]
- **Kind:** bug
- **Expect:** xfail BUG-2915
- **Fails today on:** Then 2 (today `updated_by` is stamped)

**Given**
1. O = order "1", but `approved_by U2.id`, `approved_at T0`.
2. A = approver(O, U2), but approved.
3. L = line(O, I1, "2"), but `notes "Check"`.

**When**
- `result = UIT(L, notes="Check", quantity=Decimal("2"))`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `updated_by is None`.
3. event: `ev(O) == []`.
4. re-read A: `approved is True`.

### WOM-UI-21 — a request that changes nothing keeps the line's values
- **Rules:** `update_item` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. L = line(O, I1, "2"), but `notes "Check"`.

**When**
- `result = UIT(L, notes="Check")`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `notes == "Check"`, `quantity == Decimal("2.00")`.

### WOM-UI-22 — on a started order the order and line rows are locked
- **Rules:** `update_item` R11 [BUG-2916]
- **Kind:** bug
- **Expect:** xfail BUG-2916
- **Fails today on:** Then 2 (no `FOR UPDATE` is sent)

**Given**
1. O = order "1", but started.
2. L = line(O, I1, "2"), but `uses_inventory False`.
3. Statement recorder on. `db.expunge_all()`.

**When**
- `result = UIT(L, notes="x")`.

**Then**
1. returns: `result.id == L.id`.
2. statement: locks first `work_orders`.
3. statement: locks `work_order_items`.

### WOM-UI-23 — update item flushes and never commits
- **Rules:** `update_item` R7
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order "1", but stamped.
2. L = line(O, I1, "2").

**When**
- commit spy around `result = UIT(L, notes="x")`.

**Then**
1. inside: `result.id == L.id`.
2. inside: `cm.call_count == 0`.
3. after: re-read L: `notes is None`.

### WOM-UI-24 — a null for notes sent with a new quantity keeps the notes
- **Rules:** `update_item` R3, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. L = line(O, I1, "2"), but `notes "Keep"`.

**When**
- `result = UIT(L, quantity=Decimal("3"), notes=None)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `quantity == Decimal("3.00")`, `notes == "Keep"`.
3. event: `ev(O) == [("item_updated", f"Item line {L.id} updated")]`.

## `WorkOrderManager.remove_item`

### WOM-RI-01 — a draft line is soft-deleted and logged as removed
- **Rules:** `remove_item` R1, R4, R5, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. L = line(O, I1, "2").

**When**
- `result = WOM.remove_item(db, L.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `is_deleted is True`, `deleted_at == NOW`, `deleted_by == U2.id`.
3. event: `ev(O) == [("item_removed", "Removed Bolt")]`.

### WOM-RI-02 — a consumed line on a started order goes back to stock and is logged as voided
- **Rules:** `remove_item` R3, R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S(F1, I1, 7, Decimal("2.50")).
2. O = order "1", but started.
3. L = line(O, I1, "3"), but consumed(7.50).

**When**
- `result = WOM.remove_item(db, L.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read: `qty(F1, I1, STORAGE) == Decimal("10")`.
3. re-read L: `is_deleted is True`, `consumed_at is None`.
4. event: `ev(O) == [("item_voided", "Voided Bolt")]`.

### WOM-RI-03 — a line not consumed on a started order is logged as removed
- **Rules:** `remove_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. L = line(O, I1, "2"), but `uses_inventory False`.

**When**
- `result = WOM.remove_item(db, L.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == L.id`.
2. event: `ev(O) == [("item_removed", "Removed Bolt")]`.

### WOM-RI-04 — a deleted line is not found
- **Rules:** `remove_item` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. O = order "1", but stamped.
2. L = line(O, I1, "2"), but gone.

**When**
- `WOM.remove_item(db, L.id, W1.id, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Work order item not found"`.
4. unchanged: unchanged(L).

### WOM-RI-05 — a line of W2 is not found
- **Rules:** `remove_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order "9", but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `machine_id M9.id`.
2. L9 = line(O9, I9, "1"), but `workspace_id W2.id`, `source_location_id F9.id`.

**When**
- `WOM.remove_item(db, L9.id, W1.id, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Work order item not found"`.
4. unchanged: unchanged(L9).

### WOM-RI-06 — a line of a voided order cannot be removed
- **Rules:** `remove_item` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but voided.
2. L = line(O, I1, "2").

**When**
- `WOM.remove_item(db, L.id, W1.id, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order is voided"`.
4. unchanged: unchanged(L).

### WOM-RI-07 — a line of an order without stock items cannot be removed
- **Rules:** `remove_item` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but stamped, `uses_inventory False`.
2. L = line(O, I1, "2"), but `uses_inventory False`.

**When**
- `WOM.remove_item(db, L.id, W1.id, U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "This work order does not use stock items"`.

### WOM-RI-08 — removing a line from an approved draft clears the approvals
- **Rules:** `remove_item` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but `approved_by U2.id`, `approved_at T0`.
2. A = approver(O, U2), but approved.
3. L = line(O, I1, "2").

**When**
- `result = WOM.remove_item(db, L.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read A: `approved is False`.
3. event: `("approvals_reset", "Items edited (1 approval(s) cleared)") in ev(O)`.

### WOM-RI-09 — on a started order the order and line rows are locked
- **Rules:** `remove_item` R9 [BUG-2916]
- **Kind:** bug
- **Expect:** xfail BUG-2916
- **Fails today on:** Then 2 (no `FOR UPDATE` is sent)

**Given**
1. O = order "1", but started.
2. L = line(O, I1, "2"), but `uses_inventory False`.
3. Statement recorder on. `db.expunge_all()`.

**When**
- `result = WOM.remove_item(db, L.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == L.id`.
2. statement: locks first `work_orders`.
3. statement: locks `work_order_items`.

### WOM-RI-10 — remove item flushes and never commits
- **Rules:** `remove_item` R4
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order "1", but stamped.
2. L = line(O, I1, "2").

**When**
- commit spy around `result = WOM.remove_item(db, L.id, W1.id, U2.id)`.

**Then**
1. inside: `result.id == L.id`.
2. inside: `cm.call_count == 0`.
3. after: re-read L: `is_deleted is False`.

### WOM-RI-11 — removing a line from a started order keeps its approvals
- **Rules:** `remove_item` R5, R6 (draft only)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. A = approver(O, U2), but approved.
3. L = line(O, I1, "2"), but `uses_inventory False`.

**When**
- `result = WOM.remove_item(db, L.id, W1.id, U2.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read A: `approved is True`, `approved_at == T0`.
3. event: `ev(O) == [("item_removed", "Removed Bolt")]`.

## `WorkOrderManager.get_items`

### WOM-GI-01 — the live lines of the order, in id order *(revised 2026-11-27)*
- **Rules:** `get_items` R1, R2 [BUG-1272]
- **Kind:** happy
- **Expect:** xfail BUG-1272 (non-strict): the line query has no `ORDER BY` (BUG-1272), so id order holds only when the physical order happens to match. It passed on Windows and failed on the first Linux CI run. WOM-GI-04 is the strict proof.

**Given**
1. O = order "1".
2. L1 = line(O, I1, "1").
3. LG = line(O, I2, "1"), but gone.
4. L2 = line(O, I3, "1").
5. P = order "2".
6. line(P, I1, "1").

**When**
- `result = WOM.get_items(db, O.id, W1.id)`.

**Then**
1. returns: `[l.id for l in result] == [L1.id, L2.id]`.

### WOM-GI-02 — an order of W2 is not found
- **Rules:** `get_items` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order "9", but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `machine_id M9.id`.

**When**
- `WOM.get_items(db, O9.id, W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order with ID {O9.id} not found"`.

### WOM-GI-03 — include_deleted also returns deleted lines
- **Rules:** `get_items` R3 [BUG-1273]
- **Kind:** bug
- **Expect:** xfail BUG-1273
- **Fails today on:** Then 1 (the call raises TypeError: no `include_deleted` parameter)

**Given**
1. O = order "1".
2. L1 = line(O, I1, "1").
3. LG = line(O, I2, "1"), but gone.

**When**
- `result = WOM.get_items(db, O.id, W1.id, include_deleted=True)`.

**Then**
1. returns: `[l.id for l in result] == [L1.id, LG.id]`.

### WOM-GI-04 — the line query sends an ORDER BY
- **Rules:** `get_items` R2 [BUG-1272]
- **Kind:** bug
- **Expect:** xfail BUG-1272
- **Fails today on:** Then 2 (the `work_order_items` SELECT has no `ORDER BY`)

**Given**
1. O = order "1".
2. line(O, I1, "1").
3. Statement recorder on. `db.expunge_all()`.

**When**
- `result = WOM.get_items(db, O.id, W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. statement: the recorded `SELECT` naming `work_order_items` contains `"ORDER BY"` and, after it, `"work_order_items.id"`.

## `WorkOrderManager._apply_sheet_entry_lines`

### WOM-ASL-01 — an item dict becomes a storage Consume line of the factory
- **Rules:** `_apply_sheet_entry_lines` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = WOM._apply_sheet_entry_lines(db, O, items=[{"item_id": I1.id, "quantity": 2}], approvers=[], machine_id=M1.id, factory_id=F1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. re-read: `[(l.item_id, l.quantity, l.uses_inventory, l.source_location_type, l.source_location_id, l.action_type) for l in WorkOrderItem rows with work_order_id == O.id] == [(I1.id, Decimal("2.00"), True, "storage", F1.id, "CONSUME")]`.

### WOM-ASL-02 — a machine source with no id uses the entry's machine; a given id is kept
- **Rules:** `_apply_sheet_entry_lines` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = WOM._apply_sheet_entry_lines(db, O, items=[{"item_id": I2.id, "quantity": 1, "source_location_type": "machine"}, {"item_id": I3.id, "quantity": 1, "source_location_type": "storage", "source_location_id": F2.id}], approvers=[], machine_id=M1.id, factory_id=F1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. re-read: `[(l.item_id, l.source_location_type, l.source_location_id) for l in WorkOrderItem rows with work_order_id == O.id, by id] == [(I2.id, "machine", M1.id), (I3.id, "storage", F2.id)]`.

### WOM-ASL-03 — a given action and replaced item are passed on
- **Rules:** `_apply_sheet_entry_lines` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but stamped.

**When**
- `result = WOM._apply_sheet_entry_lines(db, O, items=[{"item_id": I1.id, "quantity": 1, "action_type": "REPLACE", "replaced_item_id": I2.id}], approvers=[], machine_id=M1.id, factory_id=F1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. re-read: `[(l.action_type, l.replaced_item_id) for l in WorkOrderItem rows with work_order_id == O.id] == [("REPLACE", I2.id)]`.

### WOM-ASL-04 — an approver dict is added with its slot
- **Rules:** `_apply_sheet_entry_lines` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `result = WOM._apply_sheet_entry_lines(db, O, items=[], approvers=[{"user_id": U2.id, "approver_slot": "QA"}], machine_id=M1.id, factory_id=F1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. re-read: `[(a.user_id, a.approver_slot, a.assigned_by) for a in WorkOrderApprover rows with work_order_id == O.id] == [(U2.id, "QA", U1.id)]`.

### WOM-ASL-05 — an approver already on the order is a 409 that propagates
- **Rules:** `_apply_sheet_entry_lines` R2 [BUG-1206]
- **Kind:** bug
- **Expect:** xfail BUG-1206
- **Fails today on:** Then 1 (the 409 is swallowed today)

**Given**
1. O = order "1".
2. A = approver(O, U2).

**When**
- `WOM._apply_sheet_entry_lines(db, O, items=[], approvers=[{"user_id": U2.id}], machine_id=M1.id, factory_id=F1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "User is already an approver for this order"`.

### WOM-ASL-06 — any other approver refusal propagates
- **Rules:** `_apply_sheet_entry_lines` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `WOM._apply_sheet_entry_lines(db, O, items=[], approvers=[{"user_id": U4.id}], machine_id=M1.id, factory_id=F1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.

## `WorkOrderManager.sheet_entry`

### WOM-SE-01 — an entry without items makes a draft that uses no stock
- **Rules:** `sheet_entry` R3, R6, R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = ENTRY(SHEET())`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `title == "Service — Lathe 3"`, `factory_id == F1.id`, `machine_id == M1.id`, `planned_date == D(12)`, `status == "DRAFT"`.
3. re-read result: `uses_inventory is False`, `work_order_template_id is None`.

### WOM-SE-02 — the factory is the machine's
- **Rules:** `sheet_entry` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = ENTRY(SHEET(machine_id=M3.id))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `factory_id == F2.id`, `title == "Service — Pump"`.

### WOM-SE-03 — the other entry fields are stored
- **Rules:** `sheet_entry` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = ENTRY(SHEET(assigned_to="Sara Khan", description="Grease", priority=WorkOrderPriorityEnum.HIGH, account_id=A1.id, cost=Decimal("250.00")))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `assigned_to == "Sara Khan"`, `description == "Grease"`, `priority == WorkOrderPriorityEnum.HIGH`, `account_id == A1.id`, `cost == Decimal("250.00")`.

### WOM-SE-04 — items make stock lines and an order that uses stock
- **Rules:** `sheet_entry` R3, R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = ENTRY(SHEET(items=[{"item_id": I1.id, "quantity": 2, "action_type": "CONSUME"}]))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `uses_inventory is True`.
3. re-read: `[(l.item_id, l.quantity, l.source_location_type, l.source_location_id) for l in WorkOrderItem rows with work_order_id == result.id] == [(I1.id, Decimal("2.00"), "storage", F1.id)]`.

### WOM-SE-05 — a machine of W2 is not found
- **Rules:** `sheet_entry` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `ENTRY(SHEET(machine_id=M9.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
4. nothing written.

### WOM-SE-06 — a machine of W0 is not found
- **Rules:** `sheet_entry` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `ENTRY(SHEET(machine_id=M0.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M0.id} not found"`.
4. nothing written.

### WOM-SE-07 — a soft-deleted machine is not found
- **Rules:** `sheet_entry` R1 [BUG-2920]
- **Kind:** bug
- **Expect:** xfail BUG-2920
- **Fails today on:** Then 1 (no error is raised: a draft is saved on the deleted machine)

**Given**
1. MD = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Old press")`, but gone.

**When**
- `ENTRY(SHEET(machine_id=MD.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {MD.id} not found"`.
4. nothing written.

### WOM-SE-08 — a type of W2 is not found
- **Rules:** `sheet_entry` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `ENTRY(SHEET(work_order_type_id=WT9.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Work order type not found"`.
4. nothing written.

### WOM-SE-09 — a soft-deleted type is not found
- **Rules:** `sheet_entry` R2 [BUG-1228]
- **Kind:** bug
- **Expect:** xfail BUG-1228
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. WTD = `WorkOrderType(workspace_id=W1.id, name="Overhaul")`, but gone.

**When**
- `ENTRY(SHEET(work_order_type_id=WTD.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Work order type not found"`.
4. nothing written.

### WOM-SE-10 — an active non-recurring template is linked and makes no drafts
- **Rules:** `sheet_entry` R4, R8, R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = ENTRY(SHEET(template_id=T.id))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `work_order_template_id == T.id`.
3. count: `work_orders` with `work_order_template_id == T.id` has exactly 1 row.

### WOM-SE-11 — a template of W2 is not found
- **Rules:** `sheet_entry` R9
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T9 = template, but `workspace_id W2.id`, `work_order_type_id WT9.id`.

**When**
- `ENTRY(SHEET(template_id=T9.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order template with ID {T9.id} not found"`.

### WOM-SE-12 — an inactive template is refused
- **Rules:** `sheet_entry` R9 [BUG-2928]
- **Kind:** bug
- **Expect:** xfail BUG-2928
- **Fails today on:** Then 1 (no error is raised: the order is linked to the inactive template)

**Given**
1. T = template, but `is_active False`.

**When**
- `ENTRY(SHEET(template_id=T.id))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Template is inactive"`.
4. nothing written.

### WOM-SE-13 — approvers are added
- **Rules:** `sheet_entry` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = ENTRY(SHEET(approvers=[{"user_id": U2.id}, {"user_id": U3.id, "approver_slot": "QA"}]))`.

**Then**
1. returns: `result.id is not None`.
2. re-read: `[(a.user_id, a.approver_slot) for a in WorkOrderApprover rows with work_order_id == result.id, by id] == [(U2.id, None), (U3.id, "QA")]`.
3. re-read result: `approved_at is None`.

### WOM-SE-14 — the same approver twice is a 409
- **Rules:** `sheet_entry` R7 [BUG-1206]
- **Kind:** bug
- **Expect:** xfail BUG-1206
- **Fails today on:** Then 1 (today the second approver is dropped silently)

**Given**
1. No rows beyond the standing rows.

**When**
- `ENTRY(SHEET(approvers=[{"user_id": U2.id}, {"user_id": U2.id}]))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "User is already an approver for this order"`.

### WOM-SE-15 — an approver who is not an active member propagates 400
- **Rules:** `sheet_entry` R7
- **Kind:** error
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `ENTRY(SHEET(approvers=[{"user_id": U4.id}]))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.

### WOM-SE-16 — a recurring template placed with an end date seeds its drafts
- **Rules:** `sheet_entry` R8; `_maybe_seed_template_recurrence` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, but weekly.

**When**
- `result = ENTRY(SHEET(planned_date=D(2), template_id=T.id, recurrence_end_date=D(16)))`.

**Then**
1. returns: `result.planned_date == D(2)`.
2. re-read: `sorted((o.planned_date, o.machine_id, o.status) for o in WorkOrder rows with work_order_template_id == T.id and is_deleted False) == [(D(2), M1.id, "DRAFT"), (D(9), M1.id, "DRAFT"), (D(16), M1.id, "DRAFT")]`.

### WOM-SE-17 — a negative sheet line quantity is refused by the schema
- **Rules:** `sheet_entry` Inputs; P1 [BUG-2912]
- **Kind:** bug
- **Expect:** xfail BUG-2912
- **Fails today on:** Then 1 (the schema accepts -1)

**Given**
1. No rows beyond the standing rows.

**When**
- build `WorkOrderSheetItemLine(item_id=I1.id, quantity=Decimal("-1"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: message contains `"quantity"`.

### WOM-SE-18 — a negative sheet entry cost is refused by the schema
- **Rules:** `sheet_entry` Inputs; P1 [BUG-2912]
- **Kind:** bug
- **Expect:** xfail BUG-2912
- **Fails today on:** Then 1 (the schema accepts -5)

**Given**
1. No rows beyond the standing rows.

**When**
- build `SHEET(cost=Decimal("-5"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: message contains `"cost"`.

### WOM-SE-19 — sheet entry flushes and never commits
- **Rules:** `sheet_entry` R10
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. No rows beyond the standing rows.

**When**
- commit spy around `result = ENTRY(SHEET())`.

**Then**
1. inside: `result.id is not None`.
2. inside: `cm.call_count == 0`.
3. after: count: `work_orders` with `workspace_id == W1.id` has 0 rows.

## `WorkOrderManager.sync_recurrence_drafts_for_machine`

### WOM-SRD-01 — drafts outside the range are soft-deleted; the range is regenerated
- **Rules:** `sync_recurrence_drafts_for_machine` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but weekly, `recurrence_start_date D(2)`, `recurrence_end_date D(9)`, `next_generation_date D(9)`.
2. OA = order "a", but `work_order_template_id T.id`, `planned_date date(2026, 2, 23)`.
3. OC = order "c", but `work_order_template_id T.id`, `planned_date D(9)`.
4. OB = order "b", but `work_order_template_id T.id`, `planned_date D(16)`.

**When**
- `result = WOM.sync_recurrence_drafts_for_machine(db, workspace_id=W1.id, user_id=U2.id, template=T, machine_id=M1.id, range_start=D(2), range_end=D(9))`.

**Then**
1. re-read OA: `is_deleted is True`, `deleted_by == U2.id`.
2. re-read OB: `is_deleted is True`, `deleted_by == U2.id`.
3. re-read OC: `is_deleted is False`.
4. count: `work_orders` with `work_order_template_id == T.id` and `is_deleted False` has exactly 1 row.
5. re-read T: `next_generation_date == D(16)`.

### WOM-SRD-02 — started orders and other machines' drafts are left alone
- **Rules:** `sync_recurrence_drafts_for_machine` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `recurrence_start_date D(2)`, `recurrence_end_date D(9)`, `next_generation_date D(9)`.
2. OC = order "c", but `work_order_template_id T.id`, `planned_date D(9)`.
3. IP = order "d", but started, `work_order_template_id T.id`, `planned_date D(16)` (this date replaces the one in started).
4. OM = order "e", but `work_order_template_id T.id`, `planned_date D(16)`, `machine_id M2.id`.

**When**
- `result = WOM.sync_recurrence_drafts_for_machine(db, workspace_id=W1.id, user_id=U2.id, template=T, machine_id=M1.id, range_start=D(2), range_end=D(9))`.

**Then**
1. unchanged: unchanged(IP).
2. unchanged: unchanged(OM).
3. re-read OC: `is_deleted is False`.

## `WorkOrderManager._maybe_seed_template_recurrence`

### WOM-MSR-01 — a template that does not recur does nothing
- **Rules:** `_maybe_seed_template_recurrence` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = WOM._maybe_seed_template_recurrence(db, template_id=T.id, workspace_id=W1.id, user_id=U2.id, machine_id=M1.id, planned_date=D(2), recurrence_end_date=D(16))`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(T).
3. nothing written.

### WOM-MSR-02 — a template of W2 is not found
- **Rules:** `_maybe_seed_template_recurrence` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T9 = template, but `workspace_id W2.id`, `work_order_type_id WT9.id`, weekly.

**When**
- `WOM._maybe_seed_template_recurrence(db, template_id=T9.id, workspace_id=W1.id, user_id=U2.id, machine_id=M1.id, planned_date=D(2), recurrence_end_date=D(16))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Work order template with ID {T9.id} not found"`.
4. unchanged: unchanged(T9).

### WOM-MSR-03 — an unanchored recurring template without an end date is refused
- **Rules:** `_maybe_seed_template_recurrence` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template, but weekly.

**When**
- `WOM._maybe_seed_template_recurrence(db, template_id=T.id, workspace_id=W1.id, user_id=U2.id, machine_id=M1.id, planned_date=D(2), recurrence_end_date=None)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "recurrence_end_date is required when placing an unanchored recurring template"`.
4. unchanged: unchanged(T).

### WOM-MSR-04 — an anchored template without an end date does nothing
- **Rules:** `_maybe_seed_template_recurrence` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `recurrence_start_date D(2)`, `recurrence_end_date D(16)`, `next_generation_date D(9)`.

**When**
- `result = WOM._maybe_seed_template_recurrence(db, template_id=T.id, workspace_id=W1.id, user_id=U2.id, machine_id=M1.id, planned_date=D(2), recurrence_end_date=None)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(T).
3. nothing written.

### WOM-MSR-05 — an unanchored template is anchored on the placement and its drafts are made
- **Rules:** `_maybe_seed_template_recurrence` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but weekly.

**When**
- `result = WOM._maybe_seed_template_recurrence(db, template_id=T.id, workspace_id=W1.id, user_id=U2.id, machine_id=M1.id, planned_date=D(2), recurrence_end_date=D(16))`.

**Then**
1. returns: `result is None`.
2. re-read T: `recurrence_start_date == D(2)`, `recurrence_end_date == D(16)`, `recurrence_day is None`, `next_generation_date == D(23)`.
3. re-read: `sorted(o.planned_date for o in WorkOrder rows with work_order_template_id == T.id and is_deleted False) == [D(9), D(16)]`.

### WOM-MSR-06 — a range over 183 days is refused with the recurrence message
- **Rules:** `_maybe_seed_template_recurrence` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template, but weekly.

**When**
- `WOM._maybe_seed_template_recurrence(db, template_id=T.id, workspace_id=W1.id, user_id=U2.id, machine_id=M1.id, planned_date=D(2), recurrence_end_date=date(2026, 9, 30))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Recurrence range cannot exceed 183 days (~6 months)"`.
4. unchanged: unchanged(T).
5. count: `work_orders` with `work_order_template_id == T.id` has 0 rows.

### WOM-MSR-07 — the same start and end as the anchor does nothing
- **Rules:** `_maybe_seed_template_recurrence` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `recurrence_start_date D(2)`, `recurrence_end_date D(16)`, `next_generation_date D(9)`.

**When**
- `result = WOM._maybe_seed_template_recurrence(db, template_id=T.id, workspace_id=W1.id, user_id=U2.id, machine_id=M1.id, planned_date=D(2), recurrence_end_date=D(16))`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(T).
3. nothing written.

### WOM-MSR-08 — a new range re-anchors the template and drops drafts outside it
- **Rules:** `_maybe_seed_template_recurrence` R5; `sync_recurrence_drafts_for_machine` R1, R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, but weekly, `recurrence_start_date D(2)`, `recurrence_end_date D(16)`, `next_generation_date D(23)`.
2. O9 = order "9", but `work_order_template_id T.id`, `planned_date D(9)`.
3. O16 = order "16", but `work_order_template_id T.id`, `planned_date D(16)`.

**When**
- `result = WOM._maybe_seed_template_recurrence(db, template_id=T.id, workspace_id=W1.id, user_id=U2.id, machine_id=M1.id, planned_date=D(2), recurrence_end_date=D(9))`.

**Then**
1. returns: `result is None`.
2. re-read T: `recurrence_end_date == D(9)`, `next_generation_date == D(16)`.
3. re-read O16: `is_deleted is True`, `deleted_by == U2.id`.
4. re-read O9: `is_deleted is False`.
5. count: `work_orders` with `work_order_template_id == T.id` and `is_deleted False` has exactly 1 row.

### WOM-MSR-09 — a re-anchor over 183 days is refused
- **Rules:** `_maybe_seed_template_recurrence` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template, but weekly, `recurrence_start_date D(2)`, `recurrence_end_date D(16)`, `next_generation_date D(23)`.

**When**
- `WOM._maybe_seed_template_recurrence(db, template_id=T.id, workspace_id=W1.id, user_id=U2.id, machine_id=M1.id, planned_date=D(2), recurrence_end_date=date(2026, 9, 30))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Recurrence range cannot exceed 183 days (~6 months)"`.
4. unchanged: unchanged(T).

## `WorkOrderManager.list_sheet_orders` · `count_sheet_orders` · `sheet_daily_counts`

### WOM-SH-01 — the sheet lists the workspace's orders
- **Rules:** `list_sheet_orders` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".
2. O9 = order "9", but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `machine_id M9.id`.

**When**
- `result = WOM.list_sheet_orders(db, workspace_id=W1.id)`.

**Then**
1. returns: `[o.id for o in result] == [O.id]`.

### WOM-SH-02 — the sheet list holds 50 rows by default
- **Rules:** `list_sheet_orders` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 51 orders: order "k" for k = 1 … 51 (all W1, machine M1, planned D(12)).

**When**
- `result = WOM.list_sheet_orders(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 50`.

### WOM-SH-03 — the sheet count counts the workspace's orders
- **Rules:** `count_sheet_orders` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. order "1".
2. order "2".
3. order "9", but `workspace_id W2.id`, `work_order_type_id WT9.id`, `factory_id F9.id`, `machine_id M9.id`.

**When**
- `result = WOM.count_sheet_orders(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 2`.

### WOM-SH-04 — daily counts are keyed by ISO date text
- **Rules:** `sheet_daily_counts` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. order "1", but `planned_date D(10)`.
2. order "2", but `planned_date D(10)`.
3. order "3", but `planned_date D(12)`.

**When**
- `result = WOM.sheet_daily_counts(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == {"2026-03-10": 2, "2026-03-12": 1}`.

### WOM-SH-05 — no orders give an empty dict
- **Rules:** `sheet_daily_counts` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `result = WOM.sheet_daily_counts(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == {}`.

### WOM-SH-06 — the sheet list passes its filters by keyword
- **Rules:** `list_sheet_orders` R0, R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".
2. OA = order "2", but `factory_id F2.id`, `machine_id M3.id`.
3. OB = order "3", but `planned_date D(20)`.
4. OC = order "4", but `work_order_type_id WT2.id`.

**When**
- `result = WOM.list_sheet_orders(db, workspace_id=W1.id, factory_id=F1.id, machine_id=M1.id, planned_date_from=D(10), planned_date_to=D(14), work_order_type_id=WT1.id, priority=WorkOrderPriorityEnum.MEDIUM, skip=0, limit=10)`.

**Then**
1. returns: `[o.id for o in result] == [O.id]`.

### WOM-SH-07 — the sheet count passes the same filters
- **Rules:** `count_sheet_orders` R0, R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".
2. OA = order "2", but `factory_id F2.id`, `machine_id M3.id`.
3. OB = order "3", but `planned_date D(20)`.
4. OC = order "4", but `work_order_type_id WT2.id`.

**When**
- `result = WOM.count_sheet_orders(db, workspace_id=W1.id, factory_id=F1.id, machine_id=M1.id, planned_date_from=D(10), planned_date_to=D(14), work_order_type_id=WT1.id, priority=WorkOrderPriorityEnum.MEDIUM)`.

**Then**
1. returns: `result == 1`.

### WOM-SH-08 — daily counts pass their filters
- **Rules:** `sheet_daily_counts` R0, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".
2. OA = order "2", but `factory_id F2.id`, `machine_id M3.id`.
3. OB = order "3", but `planned_date D(20)`.
4. OC = order "4", but `work_order_type_id WT2.id`.

**When**
- `result = WOM.sheet_daily_counts(db, workspace_id=W1.id, factory_id=F1.id, machine_id=M1.id, planned_date_from=D(10), planned_date_to=D(14), work_order_type_id=WT1.id, priority=WorkOrderPriorityEnum.MEDIUM)`.

**Then**
1. returns: `result == {"2026-03-12": 1}`.

### WOM-SH-09 — the sheet list and count do not exclude completed orders by default
- **Rules:** `list_sheet_orders` · `count_sheet_orders` R0 (signature, G11)
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. No rows beyond the standing rows. `import inspect`.

**When**
- `result = [inspect.signature(f).parameters["exclude_completed"].default for f in (WOM.list_sheet_orders, WOM.count_sheet_orders)]`.

**Then**
1. returns: `result == [False, False]` (`is False` for each).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| BUG-2916 / HR-10 races (`start_work_order` R9, `complete_as_planned` R11, `void_work_order` R10, `set_approval` R9, `add_approver` R8, `remove_approver` R5, `add_item` R14, `update_item` R11, `remove_item` R9) | integration tests (two transactions) | Two concurrent starts, voids, completions, approvals or line edits: the loser waits, sees the new state and gets the method's normal wrong-state error; stock and parts move once. |
| `finalize_completion` R18 [BUG-2916] (G9) | future `WorkOrderService` spec (`complete_work_order`) | The order row is read `FOR UPDATE` before the service's `IN_PROGRESS` check (statement-recorder card, formerly WOM-FC-22); `finalize_completion` itself takes no lock. |
| `delete_work_order` R5 [BUG-2923] | `WorkOrderService.delete_work_order` | A linked draft invoice is deleted, `invoice_id` cleared, event `invoice_voided`; a non-draft invoice refuses with 400 `This work order has a confirmed invoice — void the invoice first`. |
| `create_work_order` R3a, R3b; `update_work_order` R9a; `add_item` R5a; `update_item` R7b; `void_work_order` R8 (422 on the wire) | `POST /work-orders/`, `PUT /work-orders/{id}/`, item and void endpoints | The schema refusals reach the client as 422 and nothing is stored. |
| `list_work_orders` R1 (filters, order; [BUG-2670] tie) | `tests/unit/dao/work_order.cases.md` (`get_by_workspace`) | Every filter, newest first, the id tie-break. Here only one pass of the delegation, one filter and the SQL check (L-01 … L-03). |
| `list_sheet_orders` / `count_sheet_orders` R1 [BUG-2672, BUG-2673, BUG-2674]; `sheet_daily_counts` R2 [BUG-2675] | `tests/unit/dao/work_order.cases.md` | The sheet filters, search, scope and date keys; here only delegation, default limit and the ISO key mapping (SH-01 … SH-05). |
| `create_work_order` R5 numbering [BUG-2676, BUG-2677, BUG-2678] | `tests/unit/dao/work_order.cases.md`; integration for the race | Highest numeric suffix, UTC year, race-free numbering. Here only `NEW` for the first order. |
| `create_work_order_from_template` R5 and `sheet_entry` R9 ("nothing saved") | `WorkOrderService` | A refused line or template rolls back the whole request. Here the cards check the raised error only. |
| `update_work_order` R12 / R19 ("re-approve" notifications) | `WorkOrderService.update_work_order`, `approval_notification_service` | Notifications go out exactly when `_approvals_reset` is True. |
| `get_items` R3 [BUG-1273] (reachable from the API) | `GET /work-orders/{id}/items/` | The new `include_deleted` query option reaches the manager. |

## Retired IDs
- **WOM-GI-05** (Revision 4, verifier F-1) — a non-strict xfail resting on physical row order; it passed or failed from run to run and gave no signal. GI-04 pins the `ORDER BY … id` of BUG-1272 by statement.
- **WOM-FC-22** — `finalize_completion` takes no lock of its own (spec R18, G9); the lock card belongs to the future work order service spec (Deferred).
- **WOM-CI-14** — every cost column is `Numeric(15, 2)` (G10), so a 0.125 unit cost cannot be stored and the card could never fail; the observable BUG-1040 case is WOM-ADJ-15 (`_adjust_consumed_item_quantity` R6a).

## Spec gaps
None. The three gaps of Revision 4 and the four pending-describer items were closed by the describer on 2026-11-21 (spec G18, G19); Revision 5 applies them:

| # | Gap log | Applied as |
|---|---|---|
| R4-1 | G19 machine-source activity types (`consumption`, `consumption_reversed`) | ADJ-20, ADJ-21 pin `(type, text)`. |
| R4-2 | G19 decrease notes `<number> — <name> qty reduced by <d>` | ADJ-11, ADJ-18, ADJ-21, ADJ-22 pin the full text. |
| R4-3 | G19 Replace out / damaged / in and Borrow-return notes | AIC-06, AIC-08, AIC-10, AIC-11, AIC-12, AIC-15. |
| pending | G18 damaged stock goes to the order's factory | AIC-12 (source F1, machine M3 in F2, order in FX). |
| pending | G18 performers | ST-22, CAP-16, FC-24 (worker U3, recorder U2, `recorded_by`), V-18, SMS-01 Then 5; ledger `performed_by` in the cards of the G18 matrix row. |
| pending | G18 ledger `source_type` / `source_id` | reversal (RIC-01, V-18), adjust (ADJ-07, ADJ-11, ADJ-20, ADJ-21, ADJ-22), completion (AIC-05, AIC-06, AIC-08, AIC-10, AIC-11, AIC-13, FC-24), consumption (ST-22). |
| pending | G18 fallback cost (G19: reversal type `consumption_reversal`) | AIC-13, AIC-14, AIC-15, ADJ-22; RIC-04 already covers the reversal. No card asserted `consumption_reversed` as a ledger type, so none needed correcting. |

Gaps 1–15 of revision 1 were closed by the describer on 2026-11-21 (spec Gap log), and revision 2 applies them:

| # | Gap log | Applied as |
|---|---|---|
| 1 | G1 schema modules | Conventions: `WorkOrderFromTemplateCreate` from `app.schemas.work_order_template`. |
| 2 | G2 `_set_machine_status` types | SMS-01, SMS-02 check `type(result) is str`. |
| 3 | G3 number rendering | CI-02, CI-03, RIC-02, ADJ-13, AIC-05, AIC-08, AIC-10, UI-08 pin full texts and metadata. |
| 4 | G4 `_run_start_side_effects` return | RSE-01, RSE-02. |
| 5 | G5 template-path 409 | CT-22 (patched `get_approvers`, xfail BUG-1206). |
| 6 | G6 "Maintenance" fallback | CT-23. |
| 7 | G7 recompute actor | RMA-01 (Then 7, 8), RMA-10, RMA-11. |
| 8 | G8 create-side check in the schema | C-31 pins `pydantic.ValidationError`. |
| 9 | G9 completion lock | FC-22 retired; Deferred to the work order service. |
| 10 | G10 cost scale | CI-14 retired; ADJ-15 (R6a, xfail BUG-1040). `_consume_item` R5a and `_adjust_consumed_item_quantity` R7a: no failing card, per the spec. |
| 11 | G11 list parameters | L-04, L-05, SH-06, SH-07, SH-08. |
| 12 | G12 empty names | AA-12 (`add_approver` R6a: no fallback card, unreachable), RCW-11. |
| 13 | G13 event order | U-38 compares by id. |
| 14 | G14 insufficient-stock texts | CI-10, ST-11 pin the detail. |
| 15 | G15 HR-10 for approvers | AA-11, RMA-09 (xfail BUG-2916). |

## Coverage matrix
IDs without the `WOM-` prefix; "(xfail)" marks an expected-to-fail card.

| Callable | Rule | Cases |
|---|---|---|
| `_is_locked` | R1 | LK-01, LK-02 |
| `_has_recorded_approvals` | R1 | HRA-01, HRA-02, HRA-03 |
| `is_approvable` | R1 | IA-01, IA-02, IA-03 |
| `is_approvable` | R2 | IA-01, IA-02 |
| `approvability_gap_reason` | R1 | GAP-01 |
| `approvability_gap_reason` | R2 | GAP-02 |
| `approvability_gap_reason` | R3 | GAP-03 |
| `_format_scalar_value` | R1 | FSV-01 |
| `_format_scalar_value` | R2 | FSV-02 |
| `_format_scalar_value` | R3 | FSV-03 |
| `_format_scalar_value` | R4 | FSV-04 |
| `_format_scalar_value` | R5 | FSV-05 |
| `_variance_vs_planned` | R1 | VAR-01 |
| `_variance_vs_planned` | R2 | VAR-02, VAR-03, VAR-05, VAR-06 |
| `_variance_vs_planned` | R3 | VAR-02, VAR-03, VAR-04, VAR-05, VAR-06 |
| `_variance_vs_planned` | R4 | VAR-02 |
| `_schedule_metadata_for_actual` | R1 | SMA-01, SMA-02 |
| `_schedule_metadata_for_actual` | R2 | SMA-01, SMA-02 |
| `_started_worker_metadata` | R1 | ST-16, SWM-01, SWM-02 |
| `_collect_field_changes` | R1 | CFC-01, CFC-03, U-79, U-80 |
| `_collect_field_changes` | R2 | CFC-02 |
| `_collect_field_changes` | R3 | CFC-01, CFC-03, CFC-04, CFC-05, U-79, U-80 |
| `_work_order_type_name` | R1 | TN-01 |
| `_work_order_type_name` | R2 | TN-02, TN-03 |
| `resolve_invoice_account_id` | R1 | RIA-01 |
| `resolve_invoice_account_id` | R2 | RIA-02, RIA-03 |
| `_derive_default_title` | R1 | DT-01, DT-02, DT-03, DT-04 |
| `_derive_default_title` | R2 | DT-01, DT-05, DT-06 |
| `_derive_default_title` | R3 | DT-07 |
| `_derive_default_title` | R4 | DT-01, DT-02 |
| `_derive_default_title` | R5 | DT-08 |
| `create_work_order` | R1 | C-10, C-11, C-12 |
| `create_work_order` | R1a | C-13 (xfail) |
| `create_work_order` | R1b | C-22 (xfail), C-23, C-24 |
| `create_work_order` | R2 | C-14, C-15, C-16, C-17, C-18 (xfail), C-23 |
| `create_work_order` | R3 | C-04, C-19, C-20, C-21 (xfail), C-24 |
| `create_work_order` | R3a | C-34 (xfail), C-35, C-36 (xfail), C-37 (xfail), C-38 |
| `create_work_order` | R3b | C-31 (xfail), C-32 |
| `create_work_order` | R4 | C-01, C-05, C-06, C-07, C-26 |
| `create_work_order` | R5 | C-01, C-04 |
| `create_work_order` | R6 | C-02, C-08, C-09 |
| `create_work_order` | R7 | C-02, C-03 |
| `create_work_order` | R8 | C-25, C-26 |
| `create_work_order` | R9 | C-27 (xfail), C-28 (xfail), C-29 (xfail), C-30 (xfail) |
| `create_work_order` | Side effects | C-33 |
| `create_work_order_from_template` | R1 | CT-06, CT-07, CT-08 |
| `create_work_order_from_template` | R2 | CT-09, CT-10, CT-11 (xfail) |
| `create_work_order_from_template` | R3 | CT-01, CT-03, CT-04, CT-05, CT-23 |
| `create_work_order_from_template` | R3a | CT-23 |
| `create_work_order_from_template` | R4 | CT-01 |
| `create_work_order_from_template` | R5 | CT-12, CT-13, CT-14 |
| `create_work_order_from_template` | R6 | CT-01, CT-15 |
| `create_work_order_from_template` | R7 | CT-16, CT-17, CT-19, CT-20, CT-24 |
| `create_work_order_from_template` | R8 | CT-22 (xfail) |
| `create_work_order_from_template` | R9 | CT-18 (xfail), CT-19 |
| `create_work_order_from_template` | R10 | CT-02 |
| `create_work_order_from_template` | Side effects | CT-21 |
| `update_work_order` | R1 | U-02, U-03 |
| `update_work_order` | R2 | U-04 |
| `update_work_order` | R3 | U-05, U-06 |
| `update_work_order` | R4 | U-07, U-55, U-65, U-66, U-67, U-68 (xfail), U-69 (xfail), U-70 (xfail), U-77, U-79, U-80 |
| `update_work_order` | R5 | U-05, U-07, U-08 |
| `update_work_order` | R6 | U-09, U-10 |
| `update_work_order` | R7 | U-11, U-12, U-14, U-16, U-17, U-18, U-19, U-20, U-21 |
| `update_work_order` | R7a | U-22 (xfail), U-23 (xfail) |
| `update_work_order` | R8 | U-13 (xfail), U-14, U-15 |
| `update_work_order` | R9 | U-24, U-25, U-26, U-27, U-28 (xfail) |
| `update_work_order` | R9a | U-30 (xfail), U-31 (xfail), U-32 (xfail), U-33 |
| `update_work_order` | R9b | U-34 (xfail), U-35 (xfail), U-36 |
| `update_work_order` | R10 | U-01, U-37, U-58 |
| `update_work_order` | R11 | U-29 (xfail) |
| `update_work_order` | R12 | U-38, U-39 (xfail), U-41 |
| `update_work_order` | R12a | U-42 (xfail), U-43 (xfail), U-44 (xfail), U-45, U-46, U-47 |
| `update_work_order` | R13 | U-01, U-11, U-37, U-40, U-47, U-48, U-49, U-50, U-58, U-75, U-77, U-78, U-79, U-80 |
| `update_work_order` | R13a | U-51 (xfail), U-52 (xfail), U-53 (xfail), U-54, U-55, U-56 |
| `update_work_order` | R13b | U-57 (xfail) |
| `update_work_order` | R14 | U-59 (xfail), U-60 (xfail), U-61 (xfail) |
| `update_work_order` | R15 | U-54, U-55, U-58, U-62, U-63, U-64, U-65 |
| `update_work_order` | R16 | U-01 |
| `update_work_order` | R17 | U-71, U-78 |
| `update_work_order` | R18 | U-38, U-72, U-73 |
| `update_work_order` | R19 | U-01, U-38 |
| `update_work_order` | R20 | U-39 (xfail), U-74 (xfail) |
| `update_work_order` | R21 | U-12, U-75 |
| `update_work_order` | Side effects | U-76 |
| `get_work_order` | R1 | G-01, G-02 |
| `get_work_order` | R2 | G-03 (xfail), G-04 (xfail), ST-17 (xfail) |
| `list_work_orders` | R1 | L-01, L-02, L-03 (xfail), L-04, L-05, L-06 (signature defaults) |
| `bulk_delete_future_recurrence_drafts` | R1 | BD-01, BD-03 (xfail), BD-04 |
| `bulk_delete_future_recurrence_drafts` | R2 | BD-01, BD-04, BD-05 |
| `bulk_delete_future_recurrence_drafts` | R3 | BD-01, BD-02 |
| `delete_work_order` | R1 | D-02 |
| `delete_work_order` | R2 | D-03 |
| `delete_work_order` | R3 | D-04, D-05, D-06, D-07 |
| `delete_work_order` | R4 | D-01, D-06, D-07, D-08 |
| `delete_work_order` | R5 | D-09 |
| `delete_work_order` | R6 | D-01, D-09, D-10 |
| `list_approvers` | R1 | LA-01, LA-03 |
| `list_approvers` | R2 | LA-01, LA-02, LA-04, LA-05 (xfail, statement check) |
| `approval_summary` | R1 | AS-01, AS-06 |
| `approval_summary` | R2 | AS-01, AS-03 |
| `approval_summary` | R3 | AS-01, AS-02, AS-03, AS-04, ST-09 |
| `approval_summary` | R4 | AS-05, RMA-06 (xfail) |
| `approval_summary` | R5 | AS-01 |
| `approvals_met` | R1 | AM-01 |
| `reset_approvals` | R1 | RA-01, U-38 |
| `reset_approvals` | R2 | RA-01, RA-02, U-38 |
| `reset_approvals` | R3 | RA-01, RA-03 |
| `_recompute_approval_status` | R1 | RAS-05 |
| `_recompute_approval_status` | R2 | RAS-01, RAS-02, U-72 |
| `_recompute_approval_status` | R3 | RAS-03, U-73 |
| `_recompute_approval_status` | R4 | RAS-04 |
| `add_approver` | R1 | AA-01, AA-09 |
| `add_approver` | R2 | AA-03, AA-04 |
| `add_approver` | R2a | AA-05 (xfail) |
| `add_approver` | R3 | AA-04, AA-06, AA-07 |
| `add_approver` | R4 | AA-08 |
| `add_approver` | R5 | AA-01, AA-02, AA-10 |
| `add_approver` | R6 | AA-01, AA-12 |
| `add_approver` | R6a | AA-12 (the `User #<id>` fallback is unreachable: no card, per the spec) |
| `add_approver` | R7 | AA-01 |
| `add_approver` | R8 | AA-11 (xfail) |
| `remove_approver` | R1 | RMA-01, RMA-03 |
| `remove_approver` | R2a | RMA-04 (xfail) |
| `remove_approver` | R2 | RMA-05 |
| `remove_approver` | R3 | RMA-01, RMA-02, RMA-07, RMA-08 |
| `remove_approver` | R4 | RMA-01, RMA-06 (xfail), RMA-10, RMA-11 |
| `remove_approver` | R4a | RMA-01, RMA-10, RMA-11 |
| `remove_approver` | R5 | RMA-09 (xfail) |
| `set_approval` | R1 | SA-01, SA-03, SA-04, SA-06, SA-11 |
| `set_approval` | R2 | SA-01, SA-05, SA-06 |
| `set_approval` | R3 | SA-02, SA-07, SA-08 |
| `set_approval` | R3a | SA-09 (xfail), SA-10 (xfail), SA-11 |
| `set_approval` | R4 | SA-01, SA-02, SA-15 |
| `set_approval` | R5 | SA-01, SA-02 |
| `set_approval` | R6 | SA-12 (xfail), SA-13 (xfail) |
| `set_approval` | R9 | SA-14 (xfail) |
| `_consume_item` | R1 | CI-05, CI-06 |
| `_consume_item` | R2 | CI-07, CI-08 |
| `_consume_item` | R3 | CI-09, ST-12 |
| `_consume_item` | R4 | CI-01, CI-03, CI-10, CI-11, CI-12 (xfail), CI-13 (xfail), ST-11 |
| `_consume_item` | R5 | CI-01, CI-03 |
| `_consume_item` | R5a | CI-01, CI-03 (2-decimal costs; no failing card, per the spec) |
| `_consume_item` | R6 | CI-02, CI-03, CI-04 |
| `_consume_item` | R7 | CI-15, CI-16 (xfail), CI-17 |
| `_reverse_item_consumption` | R1 | RIC-03 |
| `_reverse_item_consumption` | R2 | RIC-01, RIC-02, RIC-04, V-11, V-18 |
| `_reverse_item_consumption` | R3 | RIC-01 |
| `_adjust_consumed_item_quantity` | R1 | ADJ-01, ADJ-02 |
| `_adjust_consumed_item_quantity` | R2 | ADJ-03 |
| `_adjust_consumed_item_quantity` | R3 | ADJ-04, ADJ-05, ADJ-06, ADJ-18 |
| `_adjust_consumed_item_quantity` | R4 | ADJ-07, ADJ-17, ADJ-20 |
| `_adjust_consumed_item_quantity` | R5 | ADJ-11, ADJ-16, ADJ-18, ADJ-21, ADJ-22 |
| `_adjust_consumed_item_quantity` | R6 | ADJ-07, ADJ-08, ADJ-09 (xfail), ADJ-10, ADJ-15 (xfail), ADJ-17, ADJ-19, ADJ-20 |
| `_adjust_consumed_item_quantity` | R6a | ADJ-15 (xfail) |
| `_adjust_consumed_item_quantity` | R7 | ADJ-11, ADJ-12, ADJ-16, ADJ-18, ADJ-21, ADJ-22 |
| `_adjust_consumed_item_quantity` | R7a | ADJ-11 (no failing card, per the spec) |
| `_adjust_consumed_item_quantity` | R8 | ADJ-13, ADJ-14, ADJ-20, ADJ-21 |
| `_apply_item_completion` | R1 | AIC-01, AIC-02, AIC-03, AIC-04 |
| `_apply_item_completion` | R2 | AIC-05, AIC-13 |
| `_apply_item_completion` | R3 | AIC-06, AIC-09 |
| `_apply_item_completion` | R4 | AIC-06, AIC-12, AIC-14 |
| `_apply_item_completion` | R5 | AIC-08, AIC-09 |
| `_apply_item_completion` | R6 | AIC-06, AIC-07, AIC-12, AIC-14 |
| `_apply_item_completion` | R7 | AIC-06, AIC-08, AIC-14 |
| `_apply_item_completion` | R8 (G16) | AIC-10, AIC-11, AIC-15, CAP-03 |
| `_apply_item_completion` | R9 | AIC-05 |
| `_set_machine_status` | R1 | SMS-01 |
| `_set_machine_status` | R2 | SMS-02, ST-13 |
| `_set_machine_status` | R3 | SMS-01, SMS-03, SMS-04, SMS-05, SMS-06 (xfail), ST-15 |
| `_set_machine_status` | R4 | SMS-01, SMS-03 |
| `_set_machine_status` | R5 | SMS-01, SMS-02, SMS-03 |
| `_previous_machine_status` | R1 | PMS-01, PMS-02, PMS-03 |
| `start_work_order` | R1 | ST-01, ST-17 (xfail) |
| `start_work_order` | R2 | ST-06, ST-07 |
| `start_work_order` | R3 | ST-08, ST-09 |
| `start_work_order` | R4 | ST-01, ST-10, ST-11, ST-12, ST-22 |
| `start_work_order` | R5 | ST-02, ST-13, ST-14, ST-15 |
| `start_work_order` | R6 | ST-01, ST-05, ST-21 |
| `start_work_order` | R7 | ST-03, ST-04, ST-05, ST-16, ST-22 |
| `start_work_order` | R8 | ST-19 (xfail), ST-20 |
| `start_work_order` | R9 | ST-18 (xfail) |
| `_planned_date_noon_utc` | R1 | PN-01 |
| `_run_start_side_effects` | R1 | RSE-01, RSE-02, ST-01, ST-10 |
| `_run_start_side_effects` | R2 | RSE-01, RSE-02, ST-02, ST-14 |
| `_run_start_side_effects` | R3 | RSE-01, RSE-02 |
| `_ensure_active_workspace_member` | R1 | EAM-01, EAM-02, EAM-03 |
| `_sync_assignees_from_text` | R1 | SAT-01, SAT-02, SAT-03 |
| `_resolve_completion_workers` | R1 | RCW-01, RCW-03 |
| `_resolve_completion_workers` | R2 | RCW-01, RCW-02, RCW-04, RCW-05, RCW-06 (xfail) |
| `_resolve_completion_workers` | R3 | RCW-07, RCW-08 |
| `_resolve_completion_workers` | R4 | FC-01, RCW-09, RCW-10, RCW-11 |
| `_resolve_completion_workers` | R4a | RCW-11 |
| `complete_as_planned` | R1 | CAP-06 |
| `complete_as_planned` | R2 | CAP-07 |
| `complete_as_planned` | R3 | CAP-04, CAP-05 |
| `complete_as_planned` | R4 | CAP-08 |
| `complete_as_planned` | R5 | CAP-09, CAP-10, CAP-11 |
| `complete_as_planned` | R6 | CAP-01, CAP-03 |
| `complete_as_planned` | R7 | CAP-01 |
| `complete_as_planned` | R8 | CAP-02, CAP-15, CAP-16 |
| `complete_as_planned` | R9 | CAP-01, CAP-02, CAP-03, CAP-12, CAP-16 |
| `complete_as_planned` | R10 | CAP-01, CAP-14 |
| `complete_as_planned` | R11 | CAP-13 (xfail) |
| `finalize_completion` | R1 | FC-09 |
| `finalize_completion` | R2 | FC-01, FC-10 |
| `finalize_completion` | R3 | FC-01, FC-04, FC-05, FC-06, FC-07, FC-08, FC-23 |
| `finalize_completion` | R4 | FC-01, FC-05, FC-11 |
| `finalize_completion` | R5 | FC-12, FC-24 |
| `finalize_completion` | R6 | FC-03, FC-24 |
| `finalize_completion` | R7 | FC-03, FC-13, FC-14, FC-15, FC-16 |
| `finalize_completion` | R8 | FC-17, FC-18, FC-19 (xfail), FC-20 |
| `finalize_completion` | R9 | FC-02, FC-04, FC-05, FC-06, FC-24 |
| `finalize_completion` | R10 | FC-21 |
| `finalize_completion` | R11 | FC-01 |
| `finalize_completion` | R18 | — (no lock in this method; Deferred to the work order service, FC-22 retired) |
| `void_work_order` | R1 | V-09 |
| `void_work_order` | R2 | V-07 |
| `void_work_order` | R3 | V-08 |
| `void_work_order` | R4 | V-01, V-10, V-11, V-17 |
| `void_work_order` | R5 | V-03, V-04 |
| `void_work_order` | R6 | V-05 |
| `void_work_order` | R7 | V-06 |
| `void_work_order` | R8 | V-02, V-12 (xfail), V-13 (xfail), V-14, V-16, V-18 |
| `void_work_order` | R9 | V-01 |
| `void_work_order` | R10 | V-15 (xfail) |
| G18 | Performer | ST-22, CAP-16, FC-24, V-18, SMS-01, RIC-01, ADJ-07, ADJ-11, ADJ-20, ADJ-21, ADJ-22, AIC-05, AIC-06, AIC-08, AIC-10, AIC-11, AIC-13 |
| G18 | Ledger source (`work_order`, order id) | ST-22, V-18, RIC-01, ADJ-07, ADJ-11, ADJ-20, ADJ-21, ADJ-22, AIC-05, AIC-06, AIC-08, AIC-10, AIC-11, AIC-13, FC-24 |
| G18 | Fallback cost 0.00 | AIC-13 (Install), AIC-14 (Replace-in), AIC-15 (Borrow return), ADJ-22 (adjust down), RIC-04 (reversal) |
| G18 | Damaged stock to the order's factory | AIC-12 |
| G19 | Ledger notes and activity types | ADJ-11, ADJ-18, ADJ-20, ADJ-21, ADJ-22, AIC-06, AIC-08, AIC-10, AIC-11, AIC-12, AIC-15 |
| `_ensure_catalog_item_not_on_wo` | R1 | ECI-01, ECI-02 |
| `_guard_item_mutations` | R1 | AI-04, GIM-01, GIM-03 |
| `_guard_item_mutations` | R2 | AI-05, GIM-02, GIM-03 |
| `add_item` | R1 | AI-01, AI-03, AI-04, AI-05 |
| `add_item` | R2 | AI-02, AI-06, AI-07, AI-12 |
| `add_item` | R3 | AI-08, AI-09, AI-10, AI-11, AI-12 |
| `add_item` | R4 | AI-13, AI-14, AI-15, AI-16 |
| `add_item` | R5 | AI-17, AI-18 |
| `add_item` | R5a | AI-19 (xfail), AI-20 (xfail), AI-21 (xfail), AI-22 |
| `add_item` | R5b | AI-23 (xfail), AI-24, AI-33 (xfail) |
| `add_item` | R6 | AI-25, AI-26, AI-32, AI-33 (xfail) |
| `add_item` | R6a | AI-27 (xfail), AI-28 (xfail), AI-29 (xfail), AI-30 (xfail), AI-31, AI-32 |
| `add_item` | R7 | AI-09, AI-12, AI-32, AI-33 (xfail) |
| `add_item` | R8 | AI-01, AI-02, AI-16, AI-38 |
| `add_item` | R9 | AI-01 |
| `add_item` | R10 | AI-34 |
| `add_item` | R11 | AI-35 |
| `add_item` | R12 | AI-36 (xfail) |
| `add_item` | R13 | AI-01 |
| `add_item` | R14 | AI-37 (xfail) |
| `update_item` | R1 | UI-02, UI-03 |
| `update_item` | R2 | UI-01, UI-04 |
| `update_item` | R3 | UI-05, UI-24 |
| `update_item` | R4 | UI-06, UI-07 |
| `update_item` | R5 | UI-08 |
| `update_item` | R6 | UI-09 |
| `update_item` | R7 | UI-01, UI-23 |
| `update_item` | R7a | UI-10 (xfail) |
| `update_item` | R7b | UI-11 (xfail), UI-12 (xfail), UI-13 |
| `update_item` | R7c | UI-14 (xfail), UI-15 (xfail), UI-16 |
| `update_item` | R8 | UI-17 |
| `update_item` | R9 | UI-18, UI-19 |
| `update_item` | R10 | UI-20 (xfail), UI-21 |
| `update_item` | R11 | UI-22 (xfail) |
| `remove_item` | R1 | RI-01, RI-04, RI-05, RI-06, RI-07 |
| `remove_item` | R3 | RI-02 |
| `remove_item` | R4 | RI-01, RI-10 |
| `remove_item` | R5 | RI-01, RI-02, RI-03 |
| `remove_item` | R6 | RI-08, RI-11 |
| `remove_item` | R7 | RI-01 |
| `remove_item` | R9 | RI-09 (xfail) |
| `get_items` | R1 | GI-01, GI-02 |
| `get_items` | R2 | GI-01, GI-04 (xfail) |
| `get_items` | R3 | GI-03 (xfail) |
| `_apply_sheet_entry_lines` | R1 | ASL-01, ASL-02, ASL-03 |
| `_apply_sheet_entry_lines` | R2 | ASL-04, ASL-05 (xfail), ASL-06 |
| `sheet_entry` | R1 | SE-05, SE-06, SE-07 (xfail) |
| `sheet_entry` | R2 | SE-08, SE-09 (xfail) |
| `sheet_entry` | R3 | SE-01, SE-02, SE-03, SE-04 |
| `sheet_entry` | R4 | SE-10 |
| `sheet_entry` | R5 | SE-04 |
| `sheet_entry` | R6 | SE-01 |
| `sheet_entry` | R7 | SE-13, SE-14 (xfail), SE-15 |
| `sheet_entry` | R8 | SE-10, SE-16 |
| `sheet_entry` | R9 | SE-10, SE-11, SE-12 (xfail) |
| `sheet_entry` | R10 | SE-01, SE-19 |
| `sync_recurrence_drafts_for_machine` | R1 | MSR-08, SRD-01, SRD-02 |
| `sync_recurrence_drafts_for_machine` | R2 | MSR-08, SRD-01 |
| `_maybe_seed_template_recurrence` | R1 | MSR-01, MSR-02 |
| `_maybe_seed_template_recurrence` | R2 | MSR-03, MSR-04 |
| `_maybe_seed_template_recurrence` | R3 | MSR-05, MSR-06, SE-16 |
| `_maybe_seed_template_recurrence` | R4 | MSR-07 |
| `_maybe_seed_template_recurrence` | R5 | MSR-08, MSR-09 |
| `list_sheet_orders` · `count_sheet_orders` · `sheet_daily_counts` | R0 | SH-06, SH-07, SH-08, SH-09 |
| `list_sheet_orders` · `count_sheet_orders` · `sheet_daily_counts` | R1 | SH-01, SH-02, SH-03, SH-06, SH-07 |
| `list_sheet_orders` · `count_sheet_orders` · `sheet_daily_counts` | R2 | SH-04, SH-05, SH-08 |
| `log_event` | R1 | LE-01, LE-02, LE-07 |
| `log_event` | R2 | LE-03 (xfail), LE-04 (xfail), LE-05 (xfail), LE-06 |
| `list_events` | R1 | LEV-01, LEV-02 |
| `list_events` | R2 | LEV-01 |

**Bug tags** (every card that names the bug in its Rules or Expect line):

| Bug | Cases |
|---|---|
| BUG-381 | RCW-06 (xfail) |
| BUG-665 | CI-12 (xfail), CI-13 (xfail) |
| BUG-1000 | SMS-06 (xfail) |
| BUG-1016 | AI-36 (xfail), C-27 (xfail), C-28 (xfail), C-29 (xfail), U-59 (xfail), U-60 (xfail), U-61 (xfail) |
| BUG-1040 | ADJ-09 (xfail), ADJ-15 (xfail) |
| BUG-1192 | LE-03 (xfail), LE-04 (xfail), LE-05 (xfail) |
| BUG-1200 | LA-05 (xfail) |
| BUG-1204 | RMA-06 (xfail) |
| BUG-1206 | ASL-05 (xfail), CT-22 (xfail), SE-14 (xfail) |
| BUG-1228 | C-18 (xfail), SE-09 (xfail), U-28 (xfail) |
| BUG-1272 | GI-04 (xfail) |
| BUG-1273 | GI-03 (xfail) |
| BUG-1279 | G-03 (xfail), G-04 (xfail), ST-17 (xfail) |
| BUG-1884 | CI-16 (xfail), FC-19 (xfail), ST-19 (xfail) |
| BUG-2670 | L-03 (xfail) |
| BUG-2912 | AI-19 (xfail), AI-20 (xfail), C-34 (xfail), SE-17 (xfail), SE-18 (xfail), U-30 (xfail), U-31 (xfail), UI-11 (xfail) |
| BUG-2913 | AI-21 (xfail), C-36 (xfail), C-37 (xfail), U-32 (xfail), UI-12 (xfail) |
| BUG-2914 | AI-23 (xfail), AI-33 (xfail), UI-14 (xfail), UI-15 (xfail) |
| BUG-2915 | U-39 (xfail), U-74 (xfail), UI-20 (xfail) |
| BUG-2916 | AA-11 (xfail), AI-37 (xfail), CAP-13 (xfail), RI-09 (xfail), RMA-09 (xfail), SA-14 (xfail), ST-18 (xfail), UI-22 (xfail), V-15 (xfail) |
| BUG-2917 | SA-12 (xfail), SA-13 (xfail) |
| BUG-2918 | V-12 (xfail), V-13 (xfail) |
| BUG-2919 | U-68 (xfail), U-69 (xfail), U-70 (xfail) |
| BUG-2920 | C-13 (xfail), C-21 (xfail), C-30 (xfail), CT-11 (xfail), SE-07 (xfail), U-29 (xfail) |
| BUG-2921 | C-22 (xfail), U-57 (xfail) |
| BUG-2922 | CT-18 (xfail) |
| BUG-2924 | U-13 (xfail) |
| BUG-2925 | BD-03 (xfail) |
| BUG-2926 | C-31 (xfail), U-34 (xfail), U-35 (xfail) |
| BUG-2927 | AI-27 (xfail), AI-28 (xfail), AI-29 (xfail), AI-30 (xfail), UI-10 (xfail) |
| BUG-2928 | SE-12 (xfail) |
| BUG-2929 | U-42 (xfail), U-43 (xfail), U-44 (xfail) |
| BUG-2930 | U-51 (xfail), U-52 (xfail), U-53 (xfail) |
| BUG-2931 | AA-05 (xfail), RMA-04 (xfail), SA-09 (xfail), SA-10 (xfail), U-22 (xfail), U-23 (xfail) |
| BUG-2923 | Deferred (`WorkOrderService.delete_work_order`); D-09 pins that this manager leaves the invoice alone |
| BUG-2672, BUG-2673, BUG-2674, BUG-2675, BUG-2677 | Deferred (work order DAO) |
