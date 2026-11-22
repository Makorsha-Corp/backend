# Test cases — `app/managers/transfer_order_manager.py`

> **Spec:** `tests/unit/managers/transfer_order_manager.spec.md` (source commit e48a092; APPROVED 2026-11-21)
> **Status:** READY
> **Revision:** 2 (2026-11-21) — spec Gap log G1–G10 applied. G1: TOM-C-12 retired, replaced by C-34 (BUG-1018); add_item check order AI-14 … AI-16. G2: hub filter cards HUB-07 … HUB-13. G3: return values asserted in LFC-01/02, GCU-13, GIM-04/05, AI-01, UI-01, RA-01. G4: empty profile name AA-12; the profile-missing fallbacks are unreachable (no card). G5: G-01 checks the eager `current_status` load. G6: MC-21, MC-22 (R4a runs after R2 and R3). G7: C-35 … C-38 (exact lower-case types). G8: U-23 … U-26 compare the whole event list. G9: `performed_by` in UI-11, UI-16, RI-01. G10: approver lock cards AA-11, RA-08 (BUG-2892).
> **Revision:** 2a (2026-11-21) — spec G11: `create_transfer_order` R4b [BUG-2889]; TOM-C-11 becomes a strict xfail (the duplicate 409 writes nothing). Gap 10 closed.
> **Revision:** 2b (2026-11-21) — spec G12: `delete_transfer_order` R4 [BUG-2890]; TOM-D-02 becomes a strict xfail (a foreign-workspace line fails the delete with `IntegrityError` today). NUMP patch target corrected to `patch.object(M.to_dao, "get_next_number")`, as used by the executor.
> **Revision:** 2c (2026-11-22) — spec G13: every BUG-821 / BUG-2892 lock rule gives the exact clause `FOR UPDATE OF transfer_orders`. The recorder's "locks t before the first write" now needs a SELECT from `t` that ends with `FOR UPDATE OF t` (whitespace collapsed), with no `SKIP LOCKED` / `NOWAIT`. The 9 lock cards (U-44, D-09, MC-19, AI-12, UI-23, RI-08, AA-11, RA-08, SA-16) reworded to match; all stay strict xfail. No other card, count or status changed.
> **Counts:** 363 cases · 281 expected-to-pass · 82 expected-to-fail (bugs) · 10 deferred

## Reviewer summary
- **Depth:** full (step 1a). The module moves stock at completion, decides approvals and holds order state.
- **Per callable:** `_is_completed` 3 · `_route_defined` 5 · `_route_valid` 5 · `_order_items` 3 · `_ready_for_approval` 6 · `_validate_ready_for_approval` 5 · `_has_any_approval` 5 · `_format_scalar_value` 11 · `_format_location_id` 19 · `_format_field_value` 16 · `_collect_field_changes` 9 · `_log_field_change_event` 2 · `_guard_confirmed_updates` 13 · `_guard_item_mutations` 5 · `create_transfer_order` 37 (23 bug, 11 build a schema) · `update_transfer_order` 45 (24 bug, 7 schema) · `get_transfer_order` 5 · hub reads 13 · `delete_transfer_order` 10 (4 bug) · `mark_order_complete` 22 (3 bug) · `_ensure_catalog_item_not_on_to` 6 · `add_item` 16 (5 bug) · `update_item` 24 (7 bug) · `remove_item` 8 (1 bug) · `get_items` 4 · `list_approvers` 7 (1 bug) · `approval_summary` 8 (1 bug) · `approvals_met` 2 · `add_approver` 12 (2 bug) · `remove_approver` 8 (2 bug) · `set_approval` 18 (5 bug) · `log_event` 6 (3 bug) · `list_events` 5 (1 bug).
- **Expected-to-fail by bug:** BUG-2894 12 · BUG-2895 9 (+1 shared with BUG-2903) · BUG-1018 9 · BUG-2892 8 · BUG-823 6 · BUG-2903 3 (+1 shared) · BUG-2893 4 · BUG-2897 4 · BUG-824 3 · BUG-2899 3 · BUG-1192 3 · BUG-825 2 · BUG-2898 2 · BUG-2900 2 · BUG-2902 2 · BUG-1194 2 · BUG-1203 2 · BUG-821 1 · BUG-2889 1 · BUG-2890 1 · BUG-2896 1 · BUG-2901 1. All are strict; no card compares an unordered result.
- **Notable design choices:**
  - **HR-10 locks (BUG-2892, BUG-821)** are checked at the public methods (`update_transfer_order`, `delete_transfer_order`, `add_item`, `update_item`, `remove_item`, `set_approval`, `mark_order_complete`, and since Revision 2 `add_approver`, `remove_approver`) by recording SQL: a `SELECT … FOR UPDATE OF transfer_orders` (spec G13), with no `SKIP LOCKED` / `NOWAIT`, before the first write. They are not checked on the two guards, because the fix may take the lock in the caller. The two-session race is deferred.
  - **Numbering:** every create runs with `to_dao.get_next_number` patched to a unique TNUM, as the spec Notes require (global index, BUG-2650). This is not a race simulation. Number format is a DAO matter.
  - **Stock:** `post_transfer_order_inventory` is patched in every `mark_order_complete` card, as the spec Notes allow. The cards check the call (order, lines, workspace, user), the count it returns and that an error reaches the caller unchanged. Real ledger rows are covered by `to_inventory`.
  - **BUG-2903 (OQ-55):** the pass cards U-22, U-27, U-28, U-29, U-31 and U-45 hold the parts that are true today and after the fix: the number is stored, the `updated` event, no wipe when nothing was approved or nothing changed. The wipe itself is in strict xfails U-23 … U-26, which compare the whole event list in id order: `updated`, then `approvals_reset` (spec R6c).
  - **Hub reads (G2):** HUB-01 … HUB-06 compare the default call with the DAO. HUB-07 … HUB-12 pass real filter keywords and also check that the filtered DAO result differs from the unfiltered one, so a dropped filter is caught. HUB-13 pins the `TypeError` for an unknown keyword.
  - **Check order after BUG-1018 (G1):** C-34 and AI-14 use a foreign item that is also a duplicate. The 404 must win over the 409. AI-15 shows that the item guard still runs before the item check.
  - **BUG-1194:** today's delete has no `user_id`. Pass cards call through DEL, which adds `user_id` only when the parameter exists, so they pass before and after the fix.
  - **BUG-2896:** the only xfail checks that `approved` is gone from `TransferOrderItemUpdate.model_fields`. Today's stamping of `approved_by` gets no pass card, because the fix removes it.
  - **Invalid cross-workspace rows** (a W2 line, approver or event on a W1 order) are inserted directly, on both sides of W1 (W0 and W2) where a filter on workspace is under test.
- **Needs a decision:** none. Gaps 1–9 are closed by the spec's Gap log G1–G9 and gap 10 by G11.

## Conventions for this module

**IDs.** `TOM` = this module. IC `_is_completed` · RD `_route_defined` · RVL `_route_valid` · OI `_order_items` · RFA `_ready_for_approval` · VRA `_validate_ready_for_approval` · HAA `_has_any_approval` · FSV `_format_scalar_value` · FLI `_format_location_id` · FFV `_format_field_value` · CFC `_collect_field_changes` · LFC `_log_field_change_event` · GCU `_guard_confirmed_updates` · GIM `_guard_item_mutations` · C `create_transfer_order` · U `update_transfer_order` · G `get_transfer_order` · HUB the six hub reads · D `delete_transfer_order` · MC `mark_order_complete` · ECI `_ensure_catalog_item_not_on_to` · AI `add_item` · UI `update_item` · RI `remove_item` · GI `get_items` · LA `list_approvers` · AS `approval_summary` · AM `approvals_met` · AA `add_approver` · RA `remove_approver` · SA `set_approval` · LE `log_event` · LEV `list_events`.

**Actors and fixed values.**
- `M` = `transfer_order_manager` (`from app.managers.transfer_order_manager import transfer_order_manager`). `db` = the test's real session, always the first argument. Public methods get every other argument by keyword (the spec's names); private helpers get them positionally, exactly as the card writes. `result` = what the When returns. The session does not autoflush.
- Models from `app.models.<snake_name>`: `TransferOrder`, `TransferOrderItem`, `TransferOrderApprover`, `TransferOrderEvent` (column `metadata`, mapped as `metadata_json`), `Status`, `Factory`, `Machine`, `Project`, `ProjectComponent`, `Item`, `WorkspaceMember`. Schemas `TransferOrderCreate`, `TransferOrderUpdate`, `TransferOrderItemCreate`, `TransferOrderItemUpdate` from `app.schemas.transfer_order`. `HTTPException` (fastapi), `ValidationError` (pydantic). `Decimal`, `date`, `datetime`, `timedelta`, `patch`, `os`, `uuid`, `inspect`, `text` are the usual ones.
- MISSING = `999999999`. GN(s) = `f"{s}-{os.getpid()}-{uuid.uuid4().hex[:6]}"`. XID(k) = `800_000_000 + (os.getpid() % 1_000_000) * 10 + k`. TNUM = `GN("TR-NEW")`, made once per test.
- TS(h) = `datetime(2026, 3, 4, 0, 0) + timedelta(hours=h)`. DONE = `datetime(2026, 3, 20, 9, 0)`. TOLD = `datetime(2026, 3, 22, 8, 0)`. NOW = `datetime(2026, 3, 25, 12, 0)`. All naive. A stamp "`== X`" compares the re-read value with any tzinfo removed.

**Externals (every test).**
- `app.managers.transfer_order_manager.utcnow` is patched to return NOW.
- NUMP = `patch.object(M.to_dao, "get_next_number", return_value=TNUM)` (M = `app.managers.transfer_order_manager`).
- MC cards also patch `app.managers.transfer_order_manager.post_transfer_order_inventory` as `pm`. POST(n) = `return_value=n`. POSTERR = `side_effect=ERR`, with ERR = `HTTPException(status_code=400, detail="Insufficient stock for Motor")`. **posted** = `inspect.signature(lambda session, to, items, workspace_id, user_id: None).bind(*pm.call_args.args, **pm.call_args.kwargs).arguments`.
- Race simulations: none.

**Standing rows** (every test, in this order, each flushed, no Given line):
1. W0, W1, W2 = `make_workspace(db)` three times (`W0.id < W1.id < W2.id`). U1 … U5 = `make_profile(db, name=…)` with `"Karim Ahmed"`, `"Nadia Islam"`, `"Rahim Uddin"`, `"Sumi Akter"`, `"Tanvir Hasan"`.
2. `WorkspaceMember(workspace_id=…, user_id=…, role="member", status=…, position=…)`: U1 (W1, `"active"`, "Store Manager"), U2 (W1, `"active"`, "Factory Head"), U3 (W1, `"active"`, None), U4 (W1, `"inactive"`, "Clerk"), U5 (W2, `"active"`, "Boss").
3. S0 / S1 / S2 = `Status(workspace_id=W0/W1/W2.id, name="Open", comment="stage")`.
4. `Factory(workspace_id, name, abbreviation)`: F0 (W0, "Zulu Depot", "ZD"), F1 (W1, "Alpha Works", "AW"), FB (W1, "Bravo Yard", "BY"), FD (W1, "Old Shed", "OS", deleted: `is_deleted True`, `deleted_at TS(0)`, `deleted_by U1.id`), F2 (W2, "Yankee Store", "YS").
5. `Machine(id, workspace_id, factory_id, name)`: M1 (XID(1), W1, F1, "Press Kilo"), MD (XID(2), W1, F1, "Old Lathe", deleted: `is_deleted True`, `is_active False`, `deleted_at TS(0)`, `deleted_by U1.id`), M0 (XID(3), W0, F0, "Drill Oscar"), M2 (XID(4), W2, F2, "Saw Romeo"). No machine id equals a factory id.
6. PJ1 = `Project(workspace_id=W1.id, factory_id=F1.id, name="Tower One", description="Main")`, C1 = `ProjectComponent(id=XID(5), workspace_id=W1.id, project_id=PJ1.id, name="Span Delta")`. PJ2 / C2 are the same in W2 with F2: "Tower Nine" / XID(6) "Pier Sierra".
7. `Item(workspace_id, name, name_normalized, unit="pcs")`: I1 (W1, "Motor", "motor"), I2 (W1, "Bearing", "bearing"), IN (W1, "Nut", "nut"), I0 (W0, "Gear", "gear"), IX (W2, "Valve", "valve").

**Given rows.** These are inserted directly (never through M) and flushed one at a time in the order written. After "but", a line lists every column that differs. A line written as code is a step to run exactly as written. "Invalid data" marks a row that HR-16 forbids, built only to prove a filter.
- **order O** = `TransferOrder(workspace_id=W1.id, transfer_number=GN("TR-O"), source_location_type="storage", source_location_id=F1.id, destination_location_type="storage", destination_location_id=FB.id, current_status_id=S1.id, created_by=U1.id, description="Old text", created_at=TS(1))`. `required_approvals`, `completed_at`, `completed_by`, `updated_by` stay NULL. **order O2** = the same, but `transfer_number GN("TR-O2")`. **order O0** = W0, `GN("TR-O0")`, storage F0 → machine M0, S0. **order O9** = W2, `GN("TR-O9")`, storage F2 → machine M2, S2. **completed** = `completed_at DONE`, `completed_by U1.id`.
- **line(T, k)** = `TransferOrderItem(workspace_id=T.workspace_id, transfer_order_id=T.id, line_number=k, item_id=I1.id, quantity=Decimal("10.00"))` (I0 on O0, IX on O9). `notes`, `transferred_at`, `transferred_by` are NULL and `approved` is False.
- **apr(T, U, h)** = `TransferOrderApprover(workspace_id=T.workspace_id, transfer_order_id=T.id, user_id=U.id, assigned_by=U1.id, approved=False, approved_at=None, assigned_at=TS(h))`. **approved** (on an approver) = `approved True`, `approved_at TOLD`.
- **ev(T, type, h)** = `TransferOrderEvent(workspace_id=T.workspace_id, transfer_order_id=T.id, event_type=type, description="Logged", created_at=TS(h))`. `performed_by` and `metadata_json` are not passed.
- **RT(k=v)** = a transient `TransferOrder(source_location_type="storage", source_location_id=11, destination_location_type="machine", destination_location_id=22)` with the listed keys replaced, never added to the session.

**Requests.**
- **CREATE(k=v)** = `TransferOrderCreate(source_location_type="storage", source_location_id=F1.id, destination_location_type="storage", destination_location_id=FB.id, current_status_id=S1.id, description="Monthly move")` with the listed keys replaced or added (`items` only when given).
- **ITEM(I, "q", notes=n)** = `TransferOrderItemCreate(item_id=I.id, quantity=Decimal("q"))`, plus `notes=n` when given.
- **UPD(k=v)** = `TransferOrderUpdate(**k)`; **IU(k=v)** = `TransferOrderItemUpdate(**k)`. Only the listed fields are sent (`model_fields_set`), including those listed as `None`.
- **CH(f, l, a, b)** = `{"field": f, "label": l, "from_value": a, "to_value": b}`.
- **DEL(id)** = `M.delete_transfer_order(db, to_id=id, workspace_id=W1.id)`, plus `user_id=U2.id` when `"user_id" in inspect.signature(M.delete_transfer_order).parameters`.

**Named checks.**
- **ids(result)** = `[r.id for r in result]`; the order is part of the check.
- **re-read X** = `db.flush()`, `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after a re-read, every column of X equals the snapshot taken after the last Given line.
- **session clean** = three asserts right after the raise, before any re-read: `not db.new`, `not db.dirty`, `not db.deleted`. `pending:` lines also read the session before anything expires it.
- **nothing written** = the row counts (all workspaces) of `transfer_orders`, `transfer_order_items`, `transfer_order_approvers`, `transfer_order_events`, `workspace_audit_logs` and `inventory_ledger` equal their values before the call.
- **evs(T)** = after a re-read, `[(e.event_type, e.description, e.performed_by, e.metadata_json) for e in <events with transfer_order_id == T.id, by id>]`. "events: exactly 1 row of O …" counts in that same set.
- **SUMMARY(T)** = `M.approval_summary(db, <T re-read>)`. It is used only in Then lines.
- **AUDIT(T)** = `db.execute(text("SELECT workspace_id, user_id, action, resource_type, resource_id, metadata FROM workspace_audit_logs WHERE resource_type = 'transfer_order' AND resource_id = :i"), {"i": T.id}).all()`.
- **Statement recorder** = a `before_cursor_execute` listener records the SQL from the start of the When. `selects` = every `SELECT`. `written` = every `INSERT` / `UPDATE` / `DELETE`. `sel(t)` = the SELECTs whose FROM names table `t`. **no lock** = no SELECT contains `FOR UPDATE`. **locks t before the first write** = some `s` in `sel(t)` ends with `FOR UPDATE OF t` once its whitespace is collapsed (spec G13), contains neither `SKIP LOCKED` nor `NOWAIT`, and `s` was recorded before the first statement of `written`. A recorder card ends its Given with `db.expunge_all()`; read ids into locals first.
- `raises: HTTPException` = plain `pytest.raises` with no savepoint, then `exc.value.status_code` and `exc.value.detail` with `==`. `raises: ValidationError` = around the schema's construction; "loc" = `exc.value.errors()[0]["loc"]`.
- **commit spy** = `sp = db.begin_nested()` directly before the call, inside `with patch.object(db, "commit", wraps=db.commit) as cm:`. The "inside" lines run first, then `sp.rollback()`, then the "after" lines.
- `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`. Write the call and checks exactly as shown, also when a parameter or field does not exist yet.

## `TransferOrderManager._is_completed`

### TOM-IC-01 — a set completion stamp means completed
- **Rules:** `_is_completed` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = `TransferOrder(completed_at=DONE)` (transient, never added to the session).

**When**
- `result = M._is_completed(T)`.

**Then**
1. returns: `result is True`.

### TOM-IC-02 — no completion stamp means not completed
- **Rules:** `_is_completed` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = `TransferOrder(completed_at=None)` (transient).

**When**
- `result = M._is_completed(T)`.

**Then**
1. returns: `result is False`.

### TOM-IC-03 — any stamp counts, even a very old one
- **Rules:** `_is_completed` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = `TransferOrder(completed_at=datetime(1970, 1, 1, 0, 0))` (transient).

**When**
- `result = M._is_completed(T)`.

**Then**
1. returns: `result is True`.

## `TransferOrderManager._route_defined`

### TOM-RD-01 — all four parts set
- **Rules:** `_route_defined` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = RT().

**When**
- `result = M._route_defined(T)`.

**Then**
1. returns: `result is True`.

### TOM-RD-02 — an empty source type is not set
- **Rules:** `_route_defined` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = RT(source_location_type="").

**When**
- `result = M._route_defined(T)`.

**Then**
1. returns: `result is False`.

### TOM-RD-03 — a missing destination type is not set
- **Rules:** `_route_defined` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = RT(destination_location_type=None).

**When**
- `result = M._route_defined(T)`.

**Then**
1. returns: `result is False`.

### TOM-RD-04 — a source id of 0 is not set
- **Rules:** `_route_defined` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = RT(source_location_id=0).

**When**
- `result = M._route_defined(T)`.

**Then**
1. returns: `result is False`.

### TOM-RD-05 — a missing destination id is not set
- **Rules:** `_route_defined` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = RT(destination_location_id=None).

**When**
- `result = M._route_defined(T)`.

**Then**
1. returns: `result is False`.

## `TransferOrderManager._route_valid`

### TOM-RVL-01 — an undefined route is not valid
- **Rules:** `_route_valid` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. T = `TransferOrder(source_location_type="storage", source_location_id=11, destination_location_type="machine", destination_location_id=0)` (transient).

**When**
- `result = M._route_valid(T)`.

**Then**
1. returns: `result is False`.

### TOM-RVL-02 — same type and same id is not valid
- **Rules:** `_route_valid` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. T = `TransferOrder(source_location_type="storage", source_location_id=11, destination_location_type="storage", destination_location_id=11)` (transient).

**When**
- `result = M._route_valid(T)`.

**Then**
1. returns: `result is False`.

### TOM-RVL-03 — same id with a different type is valid
- **Rules:** `_route_valid` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = `TransferOrder(source_location_type="storage", source_location_id=11, destination_location_type="damaged", destination_location_id=11)` (transient).

**When**
- `result = M._route_valid(T)`.

**Then**
1. returns: `result is True`.

### TOM-RVL-04 — the type comparison is case-sensitive
- **Rules:** `_route_valid` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = `TransferOrder(source_location_type="storage", source_location_id=11, destination_location_type="Storage", destination_location_id=11)` (transient).

**When**
- `result = M._route_valid(T)`.

**Then**
1. returns: `result is True`.

### TOM-RVL-05 — same type with a different id is valid
- **Rules:** `_route_valid` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = `TransferOrder(source_location_type="storage", source_location_id=11, destination_location_type="storage", destination_location_id=12)` (transient).

**When**
- `result = M._route_valid(T)`.

**Then**
1. returns: `result is True`.

## `TransferOrderManager._order_items`

### TOM-OI-01 — lines come by line number, not by insert order
- **Rules:** `_order_items` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O.
2. L3 = line(O, 3). L1 = line(O, 1). L2 = line(O, 2) (inserted in that order).

**When**
- `result = M._order_items(db, O, W1.id)`.

**Then**
1. returns: `ids(result) == [L1.id, L2.id, L3.id]`.

### TOM-OI-02 — lines stored under other workspaces and lines of another order are not returned
- **Rules:** `_order_items` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order O. O2 = order O2.
2. LA = line(O, 1), but `workspace_id W0.id`, `item_id I0.id` (invalid data).
3. L2 = line(O, 2).
4. LB = line(O, 3), but `workspace_id W2.id`, `item_id IX.id` (invalid data).
5. LO = line(O2, 1).

**When**
- `result = M._order_items(db, O, W1.id)`.

**Then**
1. returns: `ids(result) == [L2.id]`.

### TOM-OI-03 — an order with no lines gives an empty list
- **Rules:** `_order_items` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, no lines.

**When**
- `result = M._order_items(db, O, W1.id)`.

**Then**
1. returns: `list(result) == []`.

## `TransferOrderManager._ready_for_approval`

### TOM-RFA-01 — a valid route and one line is ready
- **Rules:** `_ready_for_approval` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O. L1 = line(O, 1). No approvers.

**When**
- `result = M._ready_for_approval(db, O, W1.id)`.

**Then**
1. returns: `result is True`.

### TOM-RFA-02 — no line is not ready
- **Rules:** `_ready_for_approval` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, no lines.

**When**
- `result = M._ready_for_approval(db, O, W1.id)`.

**Then**
1. returns: `result is False`.

### TOM-RFA-03 — a route with source = destination is not ready
- **Rules:** `_ready_for_approval` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, but `destination_location_id F1.id` (storage F1 → storage F1).
2. L1 = line(O, 1).

**When**
- `result = M._ready_for_approval(db, O, W1.id)`.

**Then**
1. returns: `result is False`.

### TOM-RFA-04 — an undefined route is not ready
- **Rules:** `_ready_for_approval` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, but `destination_location_id 0`.
2. L1 = line(O, 1).

**When**
- `result = M._ready_for_approval(db, O, W1.id)`.

**Then**
1. returns: `result is False`.

### TOM-RFA-05 — a line stored under another workspace does not count
- **Rules:** `_ready_for_approval` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order O.
2. LB = line(O, 1), but `workspace_id W2.id`, `item_id IX.id` (invalid data).

**When**
- `result = M._ready_for_approval(db, O, W1.id)`.

**Then**
1. returns: `result is False`.

### TOM-RFA-06 — approvals are not looked at
- **Rules:** `_ready_for_approval` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, but `required_approvals 5`.
2. L1 = line(O, 1).
3. A1 = apr(O, U1, 1) (not approved).

**When**
- `result = M._ready_for_approval(db, O, W1.id)`.

**Then**
1. returns: `result is True`.

## `TransferOrderManager._validate_ready_for_approval`

### TOM-VRA-01 — an undefined route is refused first
- **Rules:** `_validate_ready_for_approval` R1, R4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, but `destination_location_id 0`. No lines.

**When**
- `M._validate_ready_for_approval(db, O, W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Set source and destination before approving"`.

### TOM-VRA-02 — source = destination is refused
- **Rules:** `_validate_ready_for_approval` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, but `destination_location_id F1.id`.
2. L1 = line(O, 1).

**When**
- `M._validate_ready_for_approval(db, O, W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Source and destination cannot be the same"`.

### TOM-VRA-03 — no line is refused
- **Rules:** `_validate_ready_for_approval` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, no lines.

**When**
- `M._validate_ready_for_approval(db, O, W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Add at least one item before approving"`.

### TOM-VRA-04 — same route and no line: the route message wins
- **Rules:** `_validate_ready_for_approval` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, but `destination_location_id F1.id`. No lines.

**When**
- `M._validate_ready_for_approval(db, O, W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Source and destination cannot be the same"`.

### TOM-VRA-05 — a ready order passes
- **Rules:** `_validate_ready_for_approval` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O.
2. L1 = line(O, 1).

**When**
- `result = M._validate_ready_for_approval(db, O, W1.id)`.

**Then**
1. returns: `result is None`.

## `TransferOrderManager._has_any_approval`

### TOM-HAA-01 — one approved approver among two
- **Rules:** `_has_any_approval` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O.
2. A1 = apr(O, U1, 1).
3. A2 = apr(O, U2, 2), but approved.

**When**
- `result = M._has_any_approval(db, O)`.

**Then**
1. returns: `result is True`.

### TOM-HAA-02 — approvers but none approved
- **Rules:** `_has_any_approval` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O.
2. A1 = apr(O, U1, 1). A2 = apr(O, U2, 2).

**When**
- `result = M._has_any_approval(db, O)`.

**Then**
1. returns: `result is False`.

### TOM-HAA-03 — no approvers
- **Rules:** `_has_any_approval` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, no approvers.

**When**
- `result = M._has_any_approval(db, O)`.

**Then**
1. returns: `result is False`.

### TOM-HAA-04 — approved rows stored under other workspaces do not count
- **Rules:** `_has_any_approval` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order O.
2. A1 = apr(O, U1, 1) (not approved).
3. AZ = apr(O, U3, 2), but `workspace_id W0.id`, approved (invalid data).
4. AY = apr(O, U2, 3), but `workspace_id W2.id`, approved (invalid data).

**When**
- `result = M._has_any_approval(db, O)`.

**Then**
1. returns: `result is False`.

### TOM-HAA-05 — an approval on another order does not count
- **Rules:** `_has_any_approval` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order O. O2 = order O2.
2. A1 = apr(O, U1, 1).
3. B1 = apr(O2, U1, 2), but approved.

**When**
- `result = M._has_any_approval(db, O)`.

**Then**
1. returns: `result is False`.

## `TransferOrderManager._format_scalar_value`

Pure: no rows are needed. `field` is passed positionally first, then `value`.

### TOM-FSV-01 — None shows as a dash
- **Rules:** `_format_scalar_value` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_scalar_value("description", None)`.

**Then**
1. returns: `result == "—"`.

### TOM-FSV-02 — a date shows as ISO text
- **Rules:** `_format_scalar_value` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_scalar_value("description", date(2026, 3, 4))`.

**Then**
1. returns: `result == "2026-03-04"`.

### TOM-FSV-03 — a datetime shows as ISO text
- **Rules:** `_format_scalar_value` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_scalar_value("description", datetime(2026, 3, 4, 9, 0))`.

**Then**
1. returns: `result == "2026-03-04T09:00:00"`.

### TOM-FSV-04 — a whole Decimal shows as an integer
- **Rules:** `_format_scalar_value` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_scalar_value("quantity", Decimal("5.00"))`.

**Then**
1. returns: `result == "5"`.

### TOM-FSV-05 — a whole Decimal with trailing zeros in the integer part stays plain
- **Rules:** `_format_scalar_value` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_scalar_value("quantity", Decimal("100.00"))`.

**Then**
1. returns: `result == "100"`.

### TOM-FSV-06 — a fractional Decimal is normalised
- **Rules:** `_format_scalar_value` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_scalar_value("quantity", Decimal("2.50"))`.

**Then**
1. returns: `result == "2.5"`.

### TOM-FSV-07 — other text is trimmed
- **Rules:** `_format_scalar_value` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_scalar_value("description", "  Ship Monday  ")`.

**Then**
1. returns: `result == "Ship Monday"`.

### TOM-FSV-08 — whitespace-only text shows as a dash
- **Rules:** `_format_scalar_value` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_scalar_value("description", "   ")`.

**Then**
1. returns: `result == "—"`.

### TOM-FSV-09 — an empty string shows as a dash
- **Rules:** `_format_scalar_value` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_scalar_value("description", "")`.

**Then**
1. returns: `result == "—"`.

### TOM-FSV-10 — a bool shows as its str
- **Rules:** `_format_scalar_value` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_scalar_value("approved", True)`.

**Then**
1. returns: `result == "True"`.

### TOM-FSV-11 — the field name does not change the result
- **Rules:** `_format_scalar_value` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_scalar_value("required_approvals", None)`.

**Then**
1. returns: `result == "—"` (not "All assigned": that label belongs to `_format_field_value`).

## `TransferOrderManager._format_location_id`

Call: `M._format_location_id(db, W1.id, <type>, <id>)` with the type and id the card gives.

### TOM-FLI-01 — no id shows as a dash
- **Rules:** `_format_location_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_location_id(db, W1.id, "storage", None)`.

**Then**
1. returns: `result == "—"`.

### TOM-FLI-02 — a storage factory of the workspace is named
- **Rules:** `_format_location_id` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_location_id(db, W1.id, "storage", F1.id)`.

**Then**
1. returns: `result == "Alpha Works"`.

### TOM-FLI-03 — a damaged bucket names its factory
- **Rules:** `_format_location_id` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_location_id(db, W1.id, "damaged", FB.id)`.

**Then**
1. returns: `result == "Bravo Yard"`.

### TOM-FLI-04 — the type is compared lower-cased
- **Rules:** `_format_location_id` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_location_id(db, W1.id, "STORAGE", F1.id)`.

**Then**
1. returns: `result == "Alpha Works"`.

### TOM-FLI-05 — a missing factory shows its id
- **Rules:** `_format_location_id` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_location_id(db, W1.id, "storage", MISSING)`.

**Then**
1. returns: `result == "Factory #999999999"`.

### TOM-FLI-06 — a soft-deleted factory keeps its name
- **Rules:** `_format_location_id` R3 (Q6)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows (FD is the deleted factory of W1).

**When**
- `result = M._format_location_id(db, W1.id, "storage", FD.id)`.

**Then**
1. returns: `result == "Old Shed"`.

### TOM-FLI-07 — a machine of the workspace is named
- **Rules:** `_format_location_id` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_location_id(db, W1.id, "machine", M1.id)`.

**Then**
1. returns: `result == "Press Kilo"`.

### TOM-FLI-08 — a missing machine shows its id
- **Rules:** `_format_location_id` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_location_id(db, W1.id, "machine", MISSING)`.

**Then**
1. returns: `result == "Machine #999999999"`.

### TOM-FLI-09 — a soft-deleted machine keeps its name
- **Rules:** `_format_location_id` R4 (Q6)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows (MD is the deleted machine of W1).

**When**
- `result = M._format_location_id(db, W1.id, "machine", MD.id)`.

**Then**
1. returns: `result == "Old Lathe"`.

### TOM-FLI-10 — a machine id is looked up among machines, not factories
- **Rules:** `_format_location_id` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows (no machine has id F1.id).

**When**
- `result = M._format_location_id(db, W1.id, "machine", F1.id)`.

**Then**
1. returns: `result == f"Machine #{F1.id}"`.

### TOM-FLI-11 — a project component is named
- **Rules:** `_format_location_id` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_location_id(db, W1.id, "project", C1.id)`.

**Then**
1. returns: `result == "Span Delta"`.

### TOM-FLI-12 — a missing project component shows its id
- **Rules:** `_format_location_id` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_location_id(db, W1.id, "project", MISSING)`.

**Then**
1. returns: `result == "Project component #999999999"`.

### TOM-FLI-13 — an unknown type shows only the id
- **Rules:** `_format_location_id` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_location_id(db, W1.id, "warehouse", F1.id)`.

**Then**
1. returns: `result == f"#{F1.id}"`.

### TOM-FLI-14 — no type shows only the id
- **Rules:** `_format_location_id` R2, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_location_id(db, W1.id, None, 5)`.

**Then**
1. returns: `result == "#5"`.

### TOM-FLI-15 — a factory of a lower workspace is never named
- **Rules:** `_format_location_id` R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows (F0 is W0's factory).

**When**
- `result = M._format_location_id(db, W1.id, "storage", F0.id)`.

**Then**
1. returns: `result == f"Factory #{F0.id}"`.

### TOM-FLI-16 — a factory of a higher workspace is never named
- **Rules:** `_format_location_id` R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows (F2 is W2's factory).

**When**
- `result = M._format_location_id(db, W1.id, "damaged", F2.id)`.

**Then**
1. returns: `result == f"Factory #{F2.id}"`.

### TOM-FLI-17 — a machine of another workspace is never named
- **Rules:** `_format_location_id` R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows (M2 is W2's machine).

**When**
- `result = M._format_location_id(db, W1.id, "machine", M2.id)`.

**Then**
1. returns: `result == f"Machine #{M2.id}"`.

### TOM-FLI-18 — a machine of a lower workspace is never named
- **Rules:** `_format_location_id` R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows (M0 is W0's machine).

**When**
- `result = M._format_location_id(db, W1.id, "machine", M0.id)`.

**Then**
1. returns: `result == f"Machine #{M0.id}"`.

### TOM-FLI-19 — a project component of another workspace is never named
- **Rules:** `_format_location_id` R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows (C2 is W2's component).

**When**
- `result = M._format_location_id(db, W1.id, "project", C2.id)`.

**Then**
1. returns: `result == f"Project component #{C2.id}"`.

## `TransferOrderManager._format_field_value`

Call: `M._format_field_value(db, W1.id, <field>, <value>, source_type=<s>, destination_type=<d>)`; the card gives every argument.

### TOM-FFV-01 — a storage type gets its label
- **Rules:** `_format_field_value` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_field_value(db, W1.id, "source_location_type", "storage", source_type="storage", destination_type="storage")`.

**Then**
1. returns: `result == "Storage"`.

### TOM-FFV-02 — a machine type gets its label
- **Rules:** `_format_field_value` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_field_value(db, W1.id, "destination_location_type", "machine", source_type="storage", destination_type="storage")`.

**Then**
1. returns: `result == "Machine"`.

### TOM-FFV-03 — a damaged type gets its label
- **Rules:** `_format_field_value` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_field_value(db, W1.id, "source_location_type", "damaged", source_type="storage", destination_type="storage")`.

**Then**
1. returns: `result == "Damaged"`.

### TOM-FFV-04 — a project type gets its label
- **Rules:** `_format_field_value` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_field_value(db, W1.id, "destination_location_type", "project", source_type="storage", destination_type="storage")`.

**Then**
1. returns: `result == "Project"`.

### TOM-FFV-05 — the type label is found case-insensitively
- **Rules:** `_format_field_value` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_field_value(db, W1.id, "source_location_type", "STORAGE", source_type="storage", destination_type="storage")`.

**Then**
1. returns: `result == "Storage"`.

### TOM-FFV-06 — an unknown type is shown as sent
- **Rules:** `_format_field_value` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_field_value(db, W1.id, "destination_location_type", "Warehouse", source_type="storage", destination_type="storage")`.

**Then**
1. returns: `result == "Warehouse"`.

### TOM-FFV-07 — an empty type shows as a dash
- **Rules:** `_format_field_value` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_field_value(db, W1.id, "source_location_type", "", source_type="storage", destination_type="storage")`.

**Then**
1. returns: `result == "—"`.

### TOM-FFV-08 — a missing type shows as a dash
- **Rules:** `_format_field_value` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_field_value(db, W1.id, "destination_location_type", None, source_type="storage", destination_type="storage")`.

**Then**
1. returns: `result == "—"`.

### TOM-FFV-09 — the source id is labelled with the source type
- **Rules:** `_format_field_value` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_field_value(db, W1.id, "source_location_id", F1.id, source_type="storage", destination_type="machine")`.

**Then**
1. returns: `result == "Alpha Works"`.

### TOM-FFV-10 — the destination id is labelled with the destination type
- **Rules:** `_format_field_value` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_field_value(db, W1.id, "destination_location_id", M1.id, source_type="storage", destination_type="machine")`.

**Then**
1. returns: `result == "Press Kilo"`.

### TOM-FFV-11 — the destination id ignores the source type
- **Rules:** `_format_field_value` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_field_value(db, W1.id, "destination_location_id", F1.id, source_type="storage", destination_type="machine")`.

**Then**
1. returns: `result == f"Machine #{F1.id}"`.

### TOM-FFV-12 — required approvals None shows "All assigned"
- **Rules:** `_format_field_value` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_field_value(db, W1.id, "required_approvals", None, source_type="storage", destination_type="storage")`.

**Then**
1. returns: `result == "All assigned"`.

### TOM-FFV-13 — required approvals 0 shows "0"
- **Rules:** `_format_field_value` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_field_value(db, W1.id, "required_approvals", 0, source_type="storage", destination_type="storage")`.

**Then**
1. returns: `result == "0"`.

### TOM-FFV-14 — required approvals 2 shows "2"
- **Rules:** `_format_field_value` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_field_value(db, W1.id, "required_approvals", 2, source_type="storage", destination_type="storage")`.

**Then**
1. returns: `result == "2"`.

### TOM-FFV-15 — any other field uses the scalar format
- **Rules:** `_format_field_value` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_field_value(db, W1.id, "description", "  New text ", source_type="storage", destination_type="storage")`.

**Then**
1. returns: `result == "New text"`.

### TOM-FFV-16 — another field's None is a dash, not "All assigned"
- **Rules:** `_format_field_value` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = M._format_field_value(db, W1.id, "description", None, source_type="storage", destination_type="storage")`.

**Then**
1. returns: `result == "—"`.

## `TransferOrderManager._collect_field_changes`

Call: `M._collect_field_changes(db, W1.id, O, <update_dict>)`. **CH(field, label, from, to)** = the dict `{"field": field, "label": label, "from_value": from, "to_value": to}` (see Conventions).

### TOM-CFC-01 — all six logged fields, in the fixed order with their labels
- **Rules:** `_collect_field_changes` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O (storage F1 → storage FB, description "Old text", required_approvals NULL).

**When**
- `result = M._collect_field_changes(db, W1.id, O, {"required_approvals": 2, "description": "New text", "destination_location_id": F1.id, "destination_location_type": "damaged", "source_location_id": M1.id, "source_location_type": "machine"})` (keys deliberately in reverse order).

**Then**
1. returns: `result == [CH("source_location_type", "Source type", "Storage", "Machine"), CH("source_location_id", "Source location", "Alpha Works", "Press Kilo"), CH("destination_location_type", "Destination type", "Storage", "Damaged"), CH("destination_location_id", "Destination location", "Bravo Yard", "Alpha Works"), CH("description", "Description", "Old text", "New text"), CH("required_approvals", "Required approvals", "All assigned", "2")]`.

### TOM-CFC-02 — other keys are ignored
- **Rules:** `_collect_field_changes` R1, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O.

**When**
- `result = M._collect_field_changes(db, W1.id, O, {"current_status_id": S0.id, "notes": "x"})`.

**Then**
1. returns: `result == []`.

### TOM-CFC-03 — a value equal to the stored one gives no entry
- **Rules:** `_collect_field_changes` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O (description "Old text").

**When**
- `result = M._collect_field_changes(db, W1.id, O, {"description": "Old text", "destination_location_id": FB.id})`.

**Then**
1. returns: `result == []`.

### TOM-CFC-04 — an empty update gives no entry
- **Rules:** `_collect_field_changes` R2, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O.

**When**
- `result = M._collect_field_changes(db, W1.id, O, {})`.

**Then**
1. returns: `result == []`.

### TOM-CFC-05 — moving a route end to a machine labels the new id as a machine
- **Rules:** `_collect_field_changes` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O (destination storage FB).

**When**
- `result = M._collect_field_changes(db, W1.id, O, {"destination_location_type": "machine", "destination_location_id": M1.id})`.

**Then**
1. returns: `result == [CH("destination_location_type", "Destination type", "Storage", "Machine"), CH("destination_location_id", "Destination location", "Bravo Yard", "Press Kilo")]`.

### TOM-CFC-06 — moving a machine end to a factory labels the old id as a machine
- **Rules:** `_collect_field_changes` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, but `destination_location_type "machine"`, `destination_location_id M1.id`.

**When**
- `result = M._collect_field_changes(db, W1.id, O, {"destination_location_type": "storage", "destination_location_id": FB.id})`.

**Then**
1. returns: `result == [CH("destination_location_type", "Destination type", "Machine", "Storage"), CH("destination_location_id", "Destination location", "Press Kilo", "Bravo Yard")]`.

### TOM-CFC-07 — an id change alone uses the stored type for both values
- **Rules:** `_collect_field_changes` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O (source storage F1).

**When**
- `result = M._collect_field_changes(db, W1.id, O, {"source_location_id": FB.id})`.

**Then**
1. returns: `result == [CH("source_location_id", "Source location", "Alpha Works", "Bravo Yard")]`.

### TOM-CFC-08 — a type change with the same id gives only the type entry
- **Rules:** `_collect_field_changes` R2, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O (destination storage FB).

**When**
- `result = M._collect_field_changes(db, W1.id, O, {"destination_location_type": "damaged", "destination_location_id": FB.id})`.

**Then**
1. returns: `result == [CH("destination_location_type", "Destination type", "Storage", "Damaged")]`.

### TOM-CFC-09 — required approvals from a number to another number
- **Rules:** `_collect_field_changes` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O, but `required_approvals 2`.

**When**
- `result = M._collect_field_changes(db, W1.id, O, {"required_approvals": 0})`.

**Then**
1. returns: `result == [CH("required_approvals", "Required approvals", "2", "0")]`.

## `TransferOrderManager._log_field_change_event`

### TOM-LFC-01 — no changes, no event
- **Rules:** `_log_field_change_event` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, no events.

**When**
- `result = M._log_field_change_event(db, O.id, W1.id, U2.id, "updated", "Order details updated", [])`.

**Then**
1. pending: `not db.new`.
2. returns: `result is None`.
3. count: `transfer_order_events` for O has 0 rows (after `db.flush()`).

### TOM-LFC-02 — changes give one event with the changes as metadata
- **Rules:** `_log_field_change_event` R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O, no events.

**When**
- `result = M._log_field_change_event(db, O.id, W1.id, U2.id, "updated", "Order details updated", [CH("description", "Description", "Old text", "New text")])`.

**Then**
1. returns: `result is None`.
2. events: evs(O) == `[("updated", "Order details updated", U2.id, {"changes": [CH("description", "Description", "Old text", "New text")]})]`.
3. re-read the event: `workspace_id == W1.id`.

## `TransferOrderManager._guard_confirmed_updates`

Call: `M._guard_confirmed_updates(db, O, <update_dict>)`. The HR-10 lock of R6 is checked through `update_transfer_order` (TOM-U-44), where the caller may take it.

### TOM-GCU-01 — a completed order refuses any non-empty update
- **Rules:** `_guard_confirmed_updates` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, but completed.

**When**
- `M._guard_confirmed_updates(db, O, {"description": "New text"})`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Transfer order is complete and cannot be edited"`.
3. session clean.

### TOM-GCU-02 — a completed order lets an empty update through
- **Rules:** `_guard_confirmed_updates` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, but completed.

**When**
- `M._guard_confirmed_updates(db, O, {})`.

**Then**
1. unchanged: unchanged(O) (the call returns normally).

### TOM-GCU-03 — sending current_status_id is refused
- **Rules:** `_guard_confirmed_updates` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, no approvers.

**When**
- `M._guard_confirmed_updates(db, O, {"current_status_id": S1.id})`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Status is derived from workflow state — use Mark complete instead"`.
3. session clean.

### TOM-GCU-04 — completion is checked before the status
- **Rules:** `_guard_confirmed_updates` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, but completed.

**When**
- `M._guard_confirmed_updates(db, O, {"current_status_id": S1.id})`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Transfer order is complete and cannot be edited"`.

### TOM-GCU-05 — the status is checked before the approval lock
- **Rules:** `_guard_confirmed_updates` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O.
2. A1 = apr(O, U1, 1), but approved.

**When**
- `M._guard_confirmed_updates(db, O, {"description": "New text", "current_status_id": S1.id})`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Status is derived from workflow state — use Mark complete instead"`.

### TOM-GCU-06 — with an approval, a source type edit is refused
- **Rules:** `_guard_confirmed_updates` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.
2. A1 = apr(O, U1, 1), but approved.

**When**
- `M._guard_confirmed_updates(db, O, {"source_location_type": "damaged"})`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Withdraw all approvals before editing order details"`.
3. session clean.

### TOM-GCU-07 — with an approval, a source id edit is refused
- **Rules:** `_guard_confirmed_updates` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.
2. A1 = apr(O, U1, 1), but approved.

**When**
- `M._guard_confirmed_updates(db, O, {"source_location_id": FB.id})`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Withdraw all approvals before editing order details"`.

### TOM-GCU-08 — with an approval, a destination type edit is refused
- **Rules:** `_guard_confirmed_updates` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.
2. A1 = apr(O, U1, 1), but approved.

**When**
- `M._guard_confirmed_updates(db, O, {"destination_location_type": "machine"})`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Withdraw all approvals before editing order details"`.

### TOM-GCU-09 — with an approval, a destination id edit is refused
- **Rules:** `_guard_confirmed_updates` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.
2. A1 = apr(O, U1, 1), but approved.

**When**
- `M._guard_confirmed_updates(db, O, {"destination_location_id": F1.id})`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Withdraw all approvals before editing order details"`.

### TOM-GCU-10 — with an approval, a description edit is refused
- **Rules:** `_guard_confirmed_updates` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.
2. A1 = apr(O, U1, 1), but approved.

**When**
- `M._guard_confirmed_updates(db, O, {"description": "New text"})`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Withdraw all approvals before editing order details"`.

### TOM-GCU-11 — a value equal to the stored one still counts as sent
- **Rules:** `_guard_confirmed_updates` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O (description "Old text").
2. A1 = apr(O, U1, 1), but approved.

**When**
- `M._guard_confirmed_updates(db, O, {"description": "Old text"})`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Withdraw all approvals before editing order details"`.

### TOM-GCU-12 — required approvals alone passes while approvals are given
- **Rules:** `_guard_confirmed_updates` R4 (OQ-55)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O.
2. A1 = apr(O, U1, 1), but approved.

**When**
- `M._guard_confirmed_updates(db, O, {"required_approvals": 1})`.

**Then**
1. unchanged: unchanged(O) (the call returns normally).

### TOM-GCU-13 — without an approval, route and description edits pass
- **Rules:** `_guard_confirmed_updates` R4, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O.
2. A1 = apr(O, U1, 1) (not approved). A2 = apr(O, U2, 2) (not approved).

**When**
- `result = M._guard_confirmed_updates(db, O, {"destination_location_id": F1.id, "description": "New text"})`.

**Then**
1. returns: `result is None`.
2. pending: `not db.new`, `not db.dirty`, `not db.deleted`.
3. unchanged: unchanged(O).

## `TransferOrderManager._guard_item_mutations`

Call: `M._guard_item_mutations(db, O, W1.id)`. The HR-10 lock of R4 is checked through `add_item`, `update_item` and `remove_item` (TOM-AI-12, TOM-UI-23, TOM-RI-08).

### TOM-GIM-01 — a completed order refuses item changes
- **Rules:** `_guard_item_mutations` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, but completed.

**When**
- `M._guard_item_mutations(db, O, W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Transfer order is complete"`.

### TOM-GIM-02 — completion is checked before approvals
- **Rules:** `_guard_item_mutations` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, but completed.
2. A1 = apr(O, U1, 1), but approved.

**When**
- `M._guard_item_mutations(db, O, W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Transfer order is complete"`.

### TOM-GIM-03 — an approval refuses item changes
- **Rules:** `_guard_item_mutations` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.
2. A1 = apr(O, U1, 1). A2 = apr(O, U2, 2), but approved.

**When**
- `M._guard_item_mutations(db, O, W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Withdraw all approvals before editing transfer items"`.

### TOM-GIM-04 — approvers with no approval pass
- **Rules:** `_guard_item_mutations` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O.
2. A1 = apr(O, U1, 1) (not approved).

**When**
- `result = M._guard_item_mutations(db, O, W1.id)`.

**Then**
1. returns: `result is None`.
2. pending: `not db.new`, `not db.dirty`, `not db.deleted`.
3. unchanged: unchanged(O).

### TOM-GIM-05 — no approvers pass
- **Rules:** `_guard_item_mutations` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, no approvers.

**When**
- `result = M._guard_item_mutations(db, O, W1.id)`.

**Then**
1. returns: `result is None`.
2. pending: `not db.new`, `not db.dirty`, `not db.deleted`.
3. unchanged: unchanged(O).

## `TransferOrderManager.create_transfer_order`

Call: `result = M.create_transfer_order(db, data=<payload>, workspace_id=W1.id, user_id=U2.id)`. The numbering patch NUMP is active in every card (Conventions).

### TOM-C-01 — the order is stored with the sent fields
- **Rules:** `create_transfer_order` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no transfer orders.

**When**
- `result = M.create_transfer_order(db, data=CREATE(items=[ITEM(I1, "10")]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the order: `workspace_id == W1.id`, `transfer_number == TNUM`, `created_by == U2.id`.
3. re-read the order: `source_location_type == "storage"`, `source_location_id == F1.id`, `destination_location_type == "storage"`, `destination_location_id == FB.id`.
4. re-read the order: `description == "Monthly move"`, `current_status_id == S1.id`.
5. re-read the order: `required_approvals is None`, `completed_at is None`, `completed_by is None`.

### TOM-C-02 — lines are numbered in the sent order
- **Rules:** `create_transfer_order` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no transfer orders.

**When**
- `result = M.create_transfer_order(db, data=CREATE(items=[ITEM(I2, "5", notes="Fragile"), ITEM(I1, "10")]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `transfer_order_items` with `transfer_order_id == result.id` has exactly 2 rows.
3. re-read line 1: `item_id == I2.id`, `quantity == Decimal("5.00")`, `notes == "Fragile"`, `workspace_id == W1.id`.
4. re-read line 2: `item_id == I1.id`, `quantity == Decimal("10.00")`, `notes is None`, `workspace_id == W1.id`.
5. re-read both lines: `approved is False`, `transferred_at is None`, `transferred_by is None`.

### TOM-C-03 — the creator is the one unapproved approver
- **Rules:** `create_transfer_order` R3 (Q4)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no transfer orders.

**When**
- `result = M.create_transfer_order(db, data=CREATE(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `transfer_order_approvers` with `transfer_order_id == result.id` has exactly 1 row.
3. re-read that row: `user_id == U2.id`, `assigned_by == U2.id`, `approved is False`, `approved_at is None`, `workspace_id == W1.id`.

### TOM-C-04 — one `created` event, and no item events
- **Rules:** `create_transfer_order` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no transfer orders.

**When**
- `result = M.create_transfer_order(db, data=CREATE(items=[ITEM(I1, "10"), ITEM(I2, "3")]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. events: evs(result) == `[("created", "Transfer order created", U2.id, None)]`.

### TOM-C-05 — no items gives a draft with no lines
- **Rules:** `create_transfer_order` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no transfer orders.

**When**
- `result = M.create_transfer_order(db, data=CREATE(items=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `transfer_order_items` with `transfer_order_id == result.id` has 0 rows.

### TOM-C-06 — an empty items list gives a draft with no lines
- **Rules:** `create_transfer_order` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no transfer orders.

**When**
- `result = M.create_transfer_order(db, data=CREATE(items=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `transfer_order_items` with `transfer_order_id == result.id` has 0 rows.

### TOM-C-07 — source equal to destination is refused
- **Rules:** `create_transfer_order` R1; Errors 1
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no transfer orders.

**When**
- `M.create_transfer_order(db, data=CREATE(destination_location_id=F1.id, items=[ITEM(I1, "10")]), workspace_id=W1.id, user_id=U2.id)` (storage F1 → storage F1).

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Source and destination cannot be the same"`.
3. session clean.
4. nothing written.

### TOM-C-08 — the same id with another type is accepted
- **Rules:** `create_transfer_order` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no transfer orders.

**When**
- `result = M.create_transfer_order(db, data=CREATE(destination_location_type="damaged", destination_location_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the order: `source_location_type == "storage"`, `destination_location_type == "damaged"`, `destination_location_id == F1.id`.

### TOM-C-09 — a live machine of the workspace is accepted as destination
- **Rules:** `create_transfer_order` R2, R2a
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no transfer orders.

**When**
- `result = M.create_transfer_order(db, data=CREATE(destination_location_type="machine", destination_location_id=M1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the order: `destination_location_type == "machine"`, `destination_location_id == M1.id`.

### TOM-C-10 — the same catalog item twice is refused with its name
- **Rules:** `create_transfer_order` R4; Errors 2
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no transfer orders.

**When**
- `M.create_transfer_order(db, data=CREATE(items=[ITEM(I1, "10"), ITEM(I2, "1"), ITEM(I1, "4")]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 409`.
2. raises: `detail == "Motor appears more than once on this order"`.
3. count: `transfer_order_items` (all workspaces) has the same number of rows as before the call (after `db.flush()`).

### TOM-C-11 — the duplicate check writes nothing
- **Rules:** `create_transfer_order` R4, R4b [BUG-2889] (R2e)
- **Kind:** bug
- **Expect:** xfail BUG-2889
- **Fails today on:** Then 2 (the order row is already flushed when the 409 is raised)

**Given**
1. W1 has no transfer orders.

**When**
- `M.create_transfer_order(db, data=CREATE(items=[ITEM(I1, "10"), ITEM(I1, "4")]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 409`.
2. count: `transfer_orders` with `transfer_number == TNUM` has 0 rows (after `db.flush()`).
3. count: `transfer_order_approvers` (all orders) has the same number of rows as before the call (after `db.flush()`).

### TOM-C-13 — a source factory of a higher workspace is refused
- **Rules:** `create_transfer_order` R2a [BUG-2894] (HR-16); Errors 3
- **Kind:** bug
- **Expect:** xfail BUG-2894
- **Fails today on:** Then 1 (no exception: the order is created)

**Given**
1. W1 has no transfer orders.

**When**
- `M.create_transfer_order(db, data=CREATE(source_location_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Factory with ID {F2.id} not found"`.
3. session clean.
4. nothing written.

### TOM-C-14 — a destination factory of a lower workspace is refused
- **Rules:** `create_transfer_order` R2a [BUG-2894]; Errors 3
- **Kind:** bug
- **Expect:** xfail BUG-2894
- **Fails today on:** Then 1 (no exception: the order is created)

**Given**
1. W1 has no transfer orders.

**When**
- `M.create_transfer_order(db, data=CREATE(destination_location_type="damaged", destination_location_id=F0.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Factory with ID {F0.id} not found"`.
3. session clean.
4. nothing written.

### TOM-C-15 — a missing factory is refused
- **Rules:** `create_transfer_order` R2a [BUG-2894]; Errors 3
- **Kind:** bug
- **Expect:** xfail BUG-2894
- **Fails today on:** Then 1 (no exception: the id is stored unchecked)

**Given**
1. W1 has no transfer orders.

**When**
- `M.create_transfer_order(db, data=CREATE(destination_location_id=MISSING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Factory with ID 999999999 not found"`.
3. nothing written.

### TOM-C-16 — a soft-deleted factory is refused
- **Rules:** `create_transfer_order` R2a [BUG-2894]; Errors 3
- **Kind:** bug
- **Expect:** xfail BUG-2894
- **Fails today on:** Then 1 (no exception: the order is created)

**Given**
1. W1 has no transfer orders.

**When**
- `M.create_transfer_order(db, data=CREATE(source_location_id=FD.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Factory with ID {FD.id} not found"`.
3. nothing written.

### TOM-C-17 — a machine of a higher workspace is refused
- **Rules:** `create_transfer_order` R2a [BUG-2894]; Errors 3
- **Kind:** bug
- **Expect:** xfail BUG-2894
- **Fails today on:** Then 1 (no exception: the order is created)

**Given**
1. W1 has no transfer orders.

**When**
- `M.create_transfer_order(db, data=CREATE(destination_location_type="machine", destination_location_id=M2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Machine with ID {M2.id} not found"`.
3. session clean.
4. nothing written.

### TOM-C-18 — a source machine of a lower workspace is refused
- **Rules:** `create_transfer_order` R2a [BUG-2894]; Errors 3
- **Kind:** bug
- **Expect:** xfail BUG-2894
- **Fails today on:** Then 1 (no exception: the order is created)

**Given**
1. W1 has no transfer orders.

**When**
- `M.create_transfer_order(db, data=CREATE(source_location_type="machine", source_location_id=M0.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Machine with ID {M0.id} not found"`.
3. nothing written.

### TOM-C-19 — a soft-deleted machine is refused
- **Rules:** `create_transfer_order` R2a [BUG-2894]; Errors 3
- **Kind:** bug
- **Expect:** xfail BUG-2894
- **Fails today on:** Then 1 (no exception: the order is created)

**Given**
1. W1 has no transfer orders.

**When**
- `M.create_transfer_order(db, data=CREATE(destination_location_type="machine", destination_location_id=MD.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Machine with ID {MD.id} not found"`.
3. nothing written.

### TOM-C-20 — a factory id sent as a machine is refused as a machine
- **Rules:** `create_transfer_order` R2a [BUG-2894]; Errors 3
- **Kind:** bug
- **Expect:** xfail BUG-2894
- **Fails today on:** Then 1 (no exception: the order is created)

**Given**
1. W1 has no transfer orders (no machine has id FB.id).

**When**
- `M.create_transfer_order(db, data=CREATE(destination_location_type="machine", destination_location_id=FB.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Machine with ID {FB.id} not found"`.
3. nothing written.

### TOM-C-21 — a status of a higher workspace is refused
- **Rules:** `create_transfer_order` R2b [BUG-1018]; Errors 4
- **Kind:** bug
- **Expect:** xfail BUG-1018
- **Fails today on:** Then 1 (no exception: the status is stored unchecked)

**Given**
1. W1 has no transfer orders.

**When**
- `M.create_transfer_order(db, data=CREATE(current_status_id=S2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Status with ID {S2.id} not found"`.
3. session clean.
4. nothing written.

### TOM-C-22 — a status of a lower workspace is refused
- **Rules:** `create_transfer_order` R2b [BUG-1018]; Errors 4
- **Kind:** bug
- **Expect:** xfail BUG-1018
- **Fails today on:** Then 1 (no exception: the status is stored unchecked)

**Given**
1. W1 has no transfer orders.

**When**
- `M.create_transfer_order(db, data=CREATE(current_status_id=S0.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Status with ID {S0.id} not found"`.
3. nothing written.

### TOM-C-23 — a line item of a higher workspace is refused
- **Rules:** `create_transfer_order` R2b [BUG-1018]; Errors 4
- **Kind:** bug
- **Expect:** xfail BUG-1018
- **Fails today on:** Then 1 (no exception: the line is stored)

**Given**
1. W1 has no transfer orders.

**When**
- `M.create_transfer_order(db, data=CREATE(items=[ITEM(I1, "1"), ITEM(IX, "2")]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Item with ID {IX.id} not found"`.
3. session clean.
4. nothing written.

### TOM-C-24 — a line item of a lower workspace is refused
- **Rules:** `create_transfer_order` R2b [BUG-1018]; Errors 4
- **Kind:** bug
- **Expect:** xfail BUG-1018
- **Fails today on:** Then 1 (no exception: the line is stored)

**Given**
1. W1 has no transfer orders.

**When**
- `M.create_transfer_order(db, data=CREATE(items=[ITEM(I0, "2")]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Item with ID {I0.id} not found"`.
3. nothing written.

### TOM-C-25 — a project destination is refused
- **Rules:** `create_transfer_order` R2c [BUG-825] (Q7); Errors 5
- **Kind:** bug
- **Expect:** xfail BUG-825
- **Fails today on:** Then 1 (no exception: the order is created)

**Given**
1. W1 has no transfer orders.

**When**
- `M.create_transfer_order(db, data=CREATE(destination_location_type="project", destination_location_id=C1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Project destination is not yet supported"`.
3. session clean.
4. nothing written.

### TOM-C-26 — the create schema accepts the known factory and machine types
- **Rules:** `create_transfer_order` R2d [BUG-823] (the side that holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows (target `schema`; the manager is not called).

**When**
- `result = TransferOrderCreate(source_location_type="machine", source_location_id=1, destination_location_type="damaged", destination_location_id=2)`.

**Then**
1. returns: `result.source_location_type == "machine"`, `result.destination_location_type == "damaged"`.

### TOM-C-27 — the create schema refuses an unknown source type
- **Rules:** `create_transfer_order` R2d [BUG-823]
- **Kind:** bug
- **Expect:** xfail BUG-823
- **Fails today on:** Then 1 (no error: any text is accepted)

**Given**
1. Nothing beyond the standing rows (target `schema`).

**When**
- `TransferOrderCreate(source_location_type="warehouse", source_location_id=1, destination_location_type="storage", destination_location_id=2)`.

**Then**
1. raises: `ValidationError`, loc `== ("source_location_type",)`.

### TOM-C-28 — the create schema refuses an unknown destination type
- **Rules:** `create_transfer_order` R2d [BUG-823]
- **Kind:** bug
- **Expect:** xfail BUG-823
- **Fails today on:** Then 1 (no error: any text is accepted)

**Given**
1. Nothing beyond the standing rows (target `schema`).

**When**
- `TransferOrderCreate(source_location_type="storage", source_location_id=1, destination_location_type="shelf", destination_location_id=2)`.

**Then**
1. raises: `ValidationError`, loc `== ("destination_location_type",)`.

### TOM-C-29 — a line schema accepts whole quantities above 0
- **Rules:** `create_transfer_order` R2d [BUG-824] (the side that holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows (target `schema`).

**When**
- `result = TransferOrderItemCreate(item_id=1, quantity=Decimal("1"))`.

**Then**
1. returns: `result.quantity == Decimal("1")`.

### TOM-C-30 — a line schema refuses quantity 0
- **Rules:** `create_transfer_order` R2d [BUG-824]
- **Kind:** bug
- **Expect:** xfail BUG-824
- **Fails today on:** Then 1 (no error)

**Given**
1. Nothing beyond the standing rows (target `schema`).

**When**
- `TransferOrderItemCreate(item_id=1, quantity=Decimal("0"))`.

**Then**
1. raises: `ValidationError`, loc `== ("quantity",)`.

### TOM-C-31 — a line schema refuses a negative quantity
- **Rules:** `create_transfer_order` R2d [BUG-824]
- **Kind:** bug
- **Expect:** xfail BUG-824
- **Fails today on:** Then 1 (no error)

**Given**
1. Nothing beyond the standing rows (target `schema`).

**When**
- `TransferOrderItemCreate(item_id=1, quantity=Decimal("-1"))`.

**Then**
1. raises: `ValidationError`, loc `== ("quantity",)`.

### TOM-C-32 — a line schema refuses a fractional quantity
- **Rules:** `create_transfer_order` R2d [BUG-824]
- **Kind:** bug
- **Expect:** xfail BUG-824
- **Fails today on:** Then 1 (no error)

**Given**
1. Nothing beyond the standing rows (target `schema`).

**When**
- `TransferOrderItemCreate(item_id=1, quantity=Decimal("2.5"))`.

**Then**
1. raises: `ValidationError`, loc `== ("quantity",)`.

### TOM-C-33 — create does not commit
- **Rules:** `create_transfer_order` Returns (flushed, not committed)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. W1 has no transfer orders.

**When**
- commit spy around `result = M.create_transfer_order(db, data=CREATE(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. inside: count `transfer_orders` with `transfer_number == TNUM` is 1.
3. after: `cm.call_count == 0`.
4. after: count `transfer_orders` with `transfer_number == TNUM` is 0.

### TOM-C-34 — a foreign item sent twice is refused as not found, not as a duplicate
- **Rules:** `create_transfer_order` R2b [BUG-1018], R2e (R2b before R4); Errors 4
- **Kind:** bug
- **Expect:** xfail BUG-1018
- **Fails today on:** Then 1 (409 `Item #<id> appears more than once on this order`)

**Given**
1. W1 has no transfer orders.

**When**
- `M.create_transfer_order(db, data=CREATE(items=[ITEM(IX, "1"), ITEM(IX, "2")]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Item with ID {IX.id} not found"`.
3. session clean.
4. nothing written.

### TOM-C-35 — the create schema refuses `project` as a source type
- **Rules:** `create_transfer_order` R2d [BUG-823] (G7: `project` is a destination type only)
- **Kind:** bug
- **Expect:** xfail BUG-823
- **Fails today on:** Then 1 (no error: any text is accepted)

**Given**
1. Nothing beyond the standing rows (target `schema`; the manager is not called).

**When**
- `TransferOrderCreate(source_location_type="project", source_location_id=1, destination_location_type="storage", destination_location_id=2)`.

**Then**
1. raises: `ValidationError`, loc `== ("source_location_type",)`.

### TOM-C-36 — the create schema refuses "Storage", and does not lower-case it
- **Rules:** `create_transfer_order` R2d [BUG-823] (G7: exact lower-case values)
- **Kind:** bug
- **Expect:** xfail BUG-823
- **Fails today on:** Then 1 (no error: any text is accepted)

**Given**
1. Nothing beyond the standing rows (target `schema`).

**When**
- `TransferOrderCreate(source_location_type="Storage", source_location_id=1, destination_location_type="storage", destination_location_id=2)`.

**Then**
1. raises: `ValidationError`, loc `== ("source_location_type",)`.

### TOM-C-37 — the create schema accepts `project` as a destination type
- **Rules:** `create_transfer_order` R2d [BUG-823] (the side that holds today and after the fix; R2c refuses it later, see C-25)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows (target `schema`).

**When**
- `result = TransferOrderCreate(source_location_type="storage", source_location_id=1, destination_location_type="project", destination_location_id=2)`.

**Then**
1. returns: `result.source_location_type == "storage"`, `result.destination_location_type == "project"`.

### TOM-C-38 — the create schema refuses an empty destination type
- **Rules:** `create_transfer_order` R2d [BUG-823] (G7)
- **Kind:** bug
- **Expect:** xfail BUG-823
- **Fails today on:** Then 1 (no error: any text is accepted)

**Given**
1. Nothing beyond the standing rows (target `schema`).

**When**
- `TransferOrderCreate(source_location_type="storage", source_location_id=1, destination_location_type="", destination_location_id=2)`.

**Then**
1. raises: `ValidationError`, loc `== ("destination_location_type",)`.

## `TransferOrderManager.update_transfer_order`

Call: `result = M.update_transfer_order(db, to_id=O.id, data=<UPD>, workspace_id=W1.id, user_id=U2.id)`. O = order O (storage F1 → storage FB, description "Old text", `required_approvals` NULL, `updated_by` NULL) unless the card says otherwise.

### TOM-U-01 — a description edit is stored, stamped and logged
- **Rules:** `update_transfer_order` R4, R5, R7 (the stamp on a real change)
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O, no events.

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(description="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `description == "New text"`, `updated_by == U2.id`.
3. events: evs(O) == `[("updated", "Order details updated", U2.id, {"changes": [CH("description", "Description", "Old text", "New text")]})]`.

### TOM-U-02 — a destination moved to a machine is stored and logged with labels
- **Rules:** `update_transfer_order` R4, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O, no events.

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(destination_location_type="machine", destination_location_id=M1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `destination_location_type == "machine"`, `destination_location_id == M1.id`.
3. events: evs(O) == `[("updated", "Order details updated", U2.id, {"changes": [CH("destination_location_type", "Destination type", "Storage", "Machine"), CH("destination_location_id", "Destination location", "Bravo Yard", "Press Kilo")]})]`.

### TOM-U-03 — a missing order is 404
- **Rules:** `update_transfer_order` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.

**When**
- `M.update_transfer_order(db, to_id=MISSING, data=UPD(description="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Transfer order with ID 999999999 not found"`.
3. session clean.
4. nothing written.

### TOM-U-04 — an order of a higher workspace is 404
- **Rules:** `update_transfer_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order O9.

**When**
- `M.update_transfer_order(db, to_id=O9.id, data=UPD(description="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Transfer order with ID {O9.id} not found"`.
3. session clean.
4. unchanged: unchanged(O9).

### TOM-U-05 — an order of a lower workspace is 404
- **Rules:** `update_transfer_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O0 = order O0.

**When**
- `M.update_transfer_order(db, to_id=O0.id, data=UPD(description="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Transfer order with ID {O0.id} not found"`.
3. unchanged: unchanged(O0).

### TOM-U-06 — omitted fields are left unchanged
- **Rules:** `update_transfer_order` R2, R2a (omitted fields)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, but `required_approvals 2`.

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(description="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `source_location_type == "storage"`, `source_location_id == F1.id`, `destination_location_type == "storage"`, `destination_location_id == FB.id`.
3. re-read O: `required_approvals == 2`, `current_status_id == S1.id`.

### TOM-U-07 — an explicit null clears the description
- **Rules:** `update_transfer_order` R2a [BUG-2895]
- **Kind:** bug
- **Expect:** xfail BUG-2895
- **Fails today on:** Then 2 (the null is ignored: description stays "Old text")

**Given**
1. O = order O, no events.

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(description=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `description is None`.
3. events: evs(O) == `[("updated", "Order details updated", U2.id, {"changes": [CH("description", "Description", "Old text", "—")]})]`.

### TOM-U-08 — an explicit null sets required approvals back to "All assigned"
- **Rules:** `update_transfer_order` R2a [BUG-2895]
- **Kind:** bug
- **Expect:** xfail BUG-2895
- **Fails today on:** Then 2 (the null is ignored: `required_approvals` stays 2)

**Given**
1. O = order O, but `required_approvals 2`. No approvers.

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(required_approvals=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `required_approvals is None`.
3. events: evs(O) == `[("updated", "Order details updated", U2.id, {"changes": [CH("required_approvals", "Required approvals", "2", "All assigned")]})]`.

### TOM-U-09 — null for the source type is refused by the schema
- **Rules:** `update_transfer_order` R2a [BUG-2895]
- **Kind:** bug
- **Expect:** xfail BUG-2895
- **Fails today on:** Then 1 (no error: the null is accepted)

**Given**
1. Nothing beyond the standing rows (target `schema`).

**When**
- `TransferOrderUpdate(source_location_type=None)`.

**Then**
1. raises: `ValidationError`, loc `== ("source_location_type",)`.

### TOM-U-10 — null for the source id is refused by the schema
- **Rules:** `update_transfer_order` R2a [BUG-2895]
- **Kind:** bug
- **Expect:** xfail BUG-2895
- **Fails today on:** Then 1 (no error: the null is accepted)

**Given**
1. Nothing beyond the standing rows (target `schema`).

**When**
- `TransferOrderUpdate(source_location_id=None)`.

**Then**
1. raises: `ValidationError`, loc `== ("source_location_id",)`.

### TOM-U-11 — null for the destination type is refused by the schema
- **Rules:** `update_transfer_order` R2a [BUG-2895]
- **Kind:** bug
- **Expect:** xfail BUG-2895
- **Fails today on:** Then 1 (no error: the null is accepted)

**Given**
1. Nothing beyond the standing rows (target `schema`).

**When**
- `TransferOrderUpdate(destination_location_type=None)`.

**Then**
1. raises: `ValidationError`, loc `== ("destination_location_type",)`.

### TOM-U-12 — null for the destination id is refused by the schema
- **Rules:** `update_transfer_order` R2a [BUG-2895]
- **Kind:** bug
- **Expect:** xfail BUG-2895
- **Fails today on:** Then 1 (no error: the null is accepted)

**Given**
1. Nothing beyond the standing rows (target `schema`).

**When**
- `TransferOrderUpdate(destination_location_id=None)`.

**Then**
1. raises: `ValidationError`, loc `== ("destination_location_id",)`.

### TOM-U-13 — a completed order refuses an edit
- **Rules:** `update_transfer_order` R3 (`_guard_confirmed_updates` R1)
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, but completed. No events.

**When**
- `M.update_transfer_order(db, to_id=O.id, data=UPD(description="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Transfer order is complete and cannot be edited"`.
3. session clean.
4. nothing written.
5. unchanged: unchanged(O).

### TOM-U-14 — an empty update of a completed order goes through without a change
- **Rules:** `update_transfer_order` R3 (`_guard_confirmed_updates` R2), R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, but completed. No events.

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `description == "Old text"`, `completed_at == DONE`.
3. events: evs(O) == `[]`.

### TOM-U-15 — an empty update of a completed order does not stamp updated_by
- **Rules:** `update_transfer_order` R7 [BUG-2893] (HR-9)
- **Kind:** bug
- **Expect:** xfail BUG-2893
- **Fails today on:** Then 2 (`updated_by` is stamped U2 on every call)

**Given**
1. O = order O, but completed.

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `updated_by is None`.

### TOM-U-16 — an empty update of an open order does not stamp updated_by
- **Rules:** `update_transfer_order` R7 [BUG-2893]
- **Kind:** bug
- **Expect:** xfail BUG-2893
- **Fails today on:** Then 2 (`updated_by` is stamped U2)

**Given**
1. O = order O.

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `updated_by is None`.

### TOM-U-17 — an unchanged value writes no event
- **Rules:** `update_transfer_order` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, no events.

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(description="Old text", destination_location_id=FB.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `description == "Old text"`, `destination_location_id == FB.id`.
3. events: evs(O) == `[]`.

### TOM-U-18 — an unchanged value does not stamp updated_by
- **Rules:** `update_transfer_order` R7 [BUG-2893]
- **Kind:** bug
- **Expect:** xfail BUG-2893
- **Fails today on:** Then 2 (`updated_by` is stamped U2)

**Given**
1. O = order O.

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(description="Old text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `updated_by is None`.

### TOM-U-19 — sending current_status_id is refused
- **Rules:** `update_transfer_order` R3 (`_guard_confirmed_updates` R3)
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.

**When**
- `M.update_transfer_order(db, to_id=O.id, data=UPD(current_status_id=S1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Status is derived from workflow state — use Mark complete instead"`.
3. session clean.
4. nothing written.

### TOM-U-20 — with an approval, a route edit is refused
- **Rules:** `update_transfer_order` R3 (`_guard_confirmed_updates` R4)
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.
2. A1 = apr(O, U1, 1), but approved.

**When**
- `M.update_transfer_order(db, to_id=O.id, data=UPD(destination_location_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Withdraw all approvals before editing order details"`.
3. session clean.
4. nothing written.
5. unchanged: unchanged(O).

### TOM-U-21 — with an approval, resending the stored description is still refused
- **Rules:** `update_transfer_order` R3 (`_guard_confirmed_updates` R5)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O.
2. A1 = apr(O, U1, 1), but approved.

**When**
- `M.update_transfer_order(db, to_id=O.id, data=UPD(description="Old text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Withdraw all approvals before editing order details"`.
3. nothing written.

### TOM-U-22 — required approvals can change while approvals are given
- **Rules:** `update_transfer_order` R3, R4, R5 (OQ-55)
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O (required NULL), no events.
2. A1 = apr(O, U1, 1), but approved. A2 = apr(O, U3, 2).

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(required_approvals=1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `required_approvals == 1`.
3. events: exactly 1 row of O has `event_type == "updated"`.
4. events: that row has `description == "Order details updated"`, `performed_by == U2.id`, `metadata_json == {"changes": [CH("required_approvals", "Required approvals", "All assigned", "1")]}`.
5. count: `transfer_order_approvers` of O has exactly 2 rows.

### TOM-U-23 — a real change of required approvals wipes the approvals given
- **Rules:** `update_transfer_order` R6a [BUG-2903] (owner, OQ-55), R6c
- **Kind:** bug
- **Expect:** xfail BUG-2903
- **Fails today on:** Then 3 (A1 keeps `approved True`)

**Given**
1. O = order O (required NULL), no events.
2. A1 = apr(O, U1, 1), but approved. A2 = apr(O, U3, 2).

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(required_approvals=1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. count: `transfer_order_approvers` of O has exactly 2 rows.
3. re-read A1: `approved is False`, `approved_at is None`.
4. events: evs(O) == `[("updated", "Order details updated", U2.id, {"changes": [CH("required_approvals", "Required approvals", "All assigned", "1")]}), ("approvals_reset", "Required approvals changed (1 approval(s) cleared)", U2.id, None)]`.
5. summary: SUMMARY(O) == `(0, 1, False)`.

### TOM-U-24 — the wipe counts every cleared approval
- **Rules:** `update_transfer_order` R6a [BUG-2903]
- **Kind:** bug
- **Expect:** xfail BUG-2903
- **Fails today on:** Then 2 (A1 keeps `approved True`)

**Given**
1. O = order O, but `required_approvals 2`. No events.
2. A1 = apr(O, U1, 1), but approved. A2 = apr(O, U3, 2), but approved.

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(required_approvals=1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read A1: `approved is False`, `approved_at is None`.
3. re-read A2: `approved is False`, `approved_at is None`.
4. events: evs(O) == `[("updated", "Order details updated", U2.id, {"changes": [CH("required_approvals", "Required approvals", "2", "1")]}), ("approvals_reset", "Required approvals changed (2 approval(s) cleared)", U2.id, None)]`.

### TOM-U-25 — clearing required approvals to null is a change that wipes
- **Rules:** `update_transfer_order` R6a [BUG-2903], R2a [BUG-2895]
- **Kind:** bug
- **Expect:** xfail BUG-2903, BUG-2895
- **Fails today on:** Then 2 (the null is ignored: `required_approvals` stays 1)

**Given**
1. O = order O, but `required_approvals 1`. No events.
2. A1 = apr(O, U1, 1), but approved.

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(required_approvals=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `required_approvals is None`.
3. re-read A1: `approved is False`, `approved_at is None`.
4. events: evs(O) == `[("updated", "Order details updated", U2.id, {"changes": [CH("required_approvals", "Required approvals", "1", "All assigned")]}), ("approvals_reset", "Required approvals changed (1 approval(s) cleared)", U2.id, None)]`.

### TOM-U-26 — setting 0 wipes, and 0 is met at once
- **Rules:** `update_transfer_order` R6, R6a [BUG-2903]
- **Kind:** bug
- **Expect:** xfail BUG-2903
- **Fails today on:** Then 3 (A1 keeps `approved True`)

**Given**
1. O = order O (required NULL), no events.
2. A1 = apr(O, U1, 1), but approved.

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(required_approvals=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `required_approvals == 0`.
3. re-read A1: `approved is False`, `approved_at is None`.
4. summary: SUMMARY(O) == `(0, 0, True)`.
5. events: evs(O) == `[("updated", "Order details updated", U2.id, {"changes": [CH("required_approvals", "Required approvals", "All assigned", "0")]}), ("approvals_reset", "Required approvals changed (1 approval(s) cleared)", U2.id, None)]`.

### TOM-U-27 — a change with no approval given writes no reset event
- **Rules:** `update_transfer_order` R4, R6a (n = 0)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, but `required_approvals 2`. No events.
2. A1 = apr(O, U1, 1). A2 = apr(O, U3, 2) (neither approved).

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(required_approvals=1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. events: evs(O) == `[("updated", "Order details updated", U2.id, {"changes": [CH("required_approvals", "Required approvals", "2", "1")]})]`.

### TOM-U-28 — the new number is what the summary uses
- **Rules:** `update_transfer_order` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order O (required NULL).
2. A1 = apr(O, U1, 1). A2 = apr(O, U3, 2) (neither approved).

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(required_approvals=1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. summary: SUMMARY(O) == `(0, 1, False)`.

### TOM-U-29 — resending the stored number keeps the approvals
- **Rules:** `update_transfer_order` R6b, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, but `required_approvals 2`. No events.
2. A1 = apr(O, U1, 1), but approved. A2 = apr(O, U3, 2).

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(required_approvals=2), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read A1: `approved is True`, `approved_at == TOLD`.
3. events: evs(O) == `[]`.

### TOM-U-30 — resending the stored number does not stamp updated_by
- **Rules:** `update_transfer_order` R6b, R7 [BUG-2893]
- **Kind:** bug
- **Expect:** xfail BUG-2893
- **Fails today on:** Then 2 (`updated_by` is stamped U2)

**Given**
1. O = order O, but `required_approvals 2`.
2. A1 = apr(O, U1, 1), but approved.

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(required_approvals=2), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `updated_by is None`.

### TOM-U-31 — null when already "All assigned" keeps the approvals
- **Rules:** `update_transfer_order` R6b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O (required NULL), no events.
2. A1 = apr(O, U1, 1), but approved.

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(required_approvals=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `required_approvals is None`.
3. re-read A1: `approved is True`, `approved_at == TOLD`.
4. events: evs(O) == `[]`.

### TOM-U-32 — a negative required number is refused by the schema
- **Rules:** `approval_summary` R2a [BUG-2901]; `update_transfer_order` Errors (schema 422)
- **Kind:** bug
- **Expect:** xfail BUG-2901
- **Fails today on:** Then 1 (no error: `-1` is accepted)

**Given**
1. Nothing beyond the standing rows (target `schema`).

**When**
- `TransferOrderUpdate(required_approvals=-1)`.

**Then**
1. raises: `ValidationError`, loc `== ("required_approvals",)`.

### TOM-U-33 — 0 and positive required numbers build
- **Rules:** `approval_summary` R2a [BUG-2901] (the side that holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows (target `schema`).

**When**
- `result = TransferOrderUpdate(required_approvals=0)`.

**Then**
1. returns: `result.required_approvals == 0`.

### TOM-U-34 — a route end moved to a factory of a higher workspace is refused
- **Rules:** `update_transfer_order` R3a [BUG-2894] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-2894
- **Fails today on:** Then 1 (no exception: the id is stored)

**Given**
1. O = order O.

**When**
- `M.update_transfer_order(db, to_id=O.id, data=UPD(destination_location_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Factory with ID {F2.id} not found"`.
3. session clean.
4. nothing written.
5. unchanged: unchanged(O).

### TOM-U-35 — a route end moved to a machine of a lower workspace is refused
- **Rules:** `update_transfer_order` R3a [BUG-2894]
- **Kind:** bug
- **Expect:** xfail BUG-2894
- **Fails today on:** Then 1 (no exception: the id is stored)

**Given**
1. O = order O.

**When**
- `M.update_transfer_order(db, to_id=O.id, data=UPD(source_location_type="machine", source_location_id=M0.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Machine with ID {M0.id} not found"`.
3. nothing written.
4. unchanged: unchanged(O).

### TOM-U-36 — a route end moved to a soft-deleted factory is refused
- **Rules:** `update_transfer_order` R3a [BUG-2894]
- **Kind:** bug
- **Expect:** xfail BUG-2894
- **Fails today on:** Then 1 (no exception: the id is stored)

**Given**
1. O = order O.

**When**
- `M.update_transfer_order(db, to_id=O.id, data=UPD(destination_location_id=FD.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Factory with ID {FD.id} not found"`.
3. nothing written.

### TOM-U-37 — a type change alone re-checks the stored id under the new type
- **Rules:** `update_transfer_order` R3a [BUG-2894] (merged route)
- **Kind:** bug
- **Expect:** xfail BUG-2894
- **Fails today on:** Then 1 (no exception: the type is stored)

**Given**
1. O = order O (destination storage FB; no machine has id FB.id).

**When**
- `M.update_transfer_order(db, to_id=O.id, data=UPD(destination_location_type="machine"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Machine with ID {FB.id} not found"`.
3. nothing written.
4. unchanged: unchanged(O).

### TOM-U-38 — a project destination is refused on update
- **Rules:** `update_transfer_order` R3a (BUG-825 as create R2c)
- **Kind:** bug
- **Expect:** xfail BUG-825
- **Fails today on:** Then 1 (no exception: the route is stored)

**Given**
1. O = order O.

**When**
- `M.update_transfer_order(db, to_id=O.id, data=UPD(destination_location_type="project", destination_location_id=C1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Project destination is not yet supported"`.
3. nothing written.
4. unchanged: unchanged(O).

### TOM-U-39 — the update schema refuses an unknown type
- **Rules:** `update_transfer_order` R3a (BUG-823 as create R2d)
- **Kind:** bug
- **Expect:** xfail BUG-823
- **Fails today on:** Then 1 (no error: any text is accepted)

**Given**
1. Nothing beyond the standing rows (target `schema`).

**When**
- `TransferOrderUpdate(source_location_type="warehouse")`.

**Then**
1. raises: `ValidationError`, loc `== ("source_location_type",)`.

### TOM-U-40 — a destination edited to equal the source is refused
- **Rules:** `update_transfer_order` R3b [BUG-2899]
- **Kind:** bug
- **Expect:** xfail BUG-2899
- **Fails today on:** Then 1 (no exception: the route is stored)

**Given**
1. O = order O (storage F1 → storage FB).

**When**
- `M.update_transfer_order(db, to_id=O.id, data=UPD(destination_location_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Source and destination cannot be the same"`.
3. session clean.
4. nothing written.
5. unchanged: unchanged(O).

### TOM-U-41 — a source edited to equal the stored destination is refused
- **Rules:** `update_transfer_order` R3b [BUG-2899] (merged route)
- **Kind:** bug
- **Expect:** xfail BUG-2899
- **Fails today on:** Then 1 (no exception: the route is stored)

**Given**
1. O = order O (storage F1 → storage FB).

**When**
- `M.update_transfer_order(db, to_id=O.id, data=UPD(source_location_id=FB.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Source and destination cannot be the same"`.
3. nothing written.
4. unchanged: unchanged(O).

### TOM-U-42 — the same id with another type is accepted on update
- **Rules:** `update_transfer_order` R3b, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O (storage F1 → storage FB).

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(destination_location_type="damaged", destination_location_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `destination_location_type == "damaged"`, `destination_location_id == F1.id`.

### TOM-U-43 — update does not commit
- **Rules:** `update_transfer_order` Returns (flushed, not committed)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order O.

**When**
- commit spy around `result = M.update_transfer_order(db, to_id=O.id, data=UPD(description="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. inside: re-read O: `description == "New text"`.
3. after: `cm.call_count == 0`.
4. after: re-read O: `description == "Old text"`.

### TOM-U-44 — the order row is locked before the guards
- **Rules:** `_guard_confirmed_updates` R6 [BUG-2892] (HR-10)
- **Kind:** bug
- **Expect:** xfail BUG-2892
- **Fails today on:** Then 2 (no SELECT on `transfer_orders` has `FOR UPDATE OF transfer_orders`)

**Given**
1. O = order O.
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(description="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. statement: locks `transfer_orders` before the first write (`FOR UPDATE OF transfer_orders`, no `NOWAIT` / `SKIP LOCKED`).

### TOM-U-45 — required approvals 0 is stored and met at once
- **Rules:** `update_transfer_order` R5, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O (required NULL). A1 = apr(O, U1, 1) (not approved).

**When**
- `result = M.update_transfer_order(db, to_id=O.id, data=UPD(required_approvals=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `required_approvals == 0`.
3. summary: SUMMARY(O) == `(0, 0, True)`.

## `TransferOrderManager.get_transfer_order`

### TOM-G-01 — the order of the workspace is returned
- **Rules:** `get_transfer_order` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O, but completed. Read `oid = O.id` into a local.
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = M.get_transfer_order(db, to_id=oid, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == oid`, `result.workspace_id == W1.id`.
2. returns: `n = len(selects)` taken right after the call; then `result.current_status.id == S1.id` and `result.current_status.name == "Open"`.
3. statement: `len(selects) == n` after reading `current_status` (it was loaded with the order, G5).

### TOM-G-02 — a missing order is 404
- **Rules:** `get_transfer_order` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.

**When**
- `M.get_transfer_order(db, to_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Transfer order with ID 999999999 not found"`.

### TOM-G-03 — an order of a higher workspace is 404
- **Rules:** `get_transfer_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order O9.

**When**
- `M.get_transfer_order(db, to_id=O9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Transfer order with ID {O9.id} not found"`.

### TOM-G-04 — an order of a lower workspace is 404
- **Rules:** `get_transfer_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O0 = order O0.

**When**
- `M.get_transfer_order(db, to_id=O0.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Transfer order with ID {O0.id} not found"`.

### TOM-G-05 — the read writes nothing and takes no lock
- **Rules:** `get_transfer_order` R1 (reads)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order O.
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = M.get_transfer_order(db, to_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O.id`.
2. statement: `written == []`.
3. statement: no lock.

## Hub reads

`TOD` = `transfer_order_dao` (`from app.dao.transfer_order import transfer_order_dao`), called only in Then lines to compute the expected value. HUB-01 … HUB-06 call with `workspace_id` only. HUB-07 … HUB-12 pass filter keywords from spec R3 by keyword and compare with the DAO called with the same keywords. Each also checks that the result differs from the unfiltered DAO call, which proves the filter reached the DAO. That check is a precondition on the data, not a DAO rule. Orders are built with **hubrow(k)** = order O, but `transfer_number GN(f"TR-H{k}")`, `created_at TS(k)`.

### TOM-HUB-01 — the hub list is the DAO's list, 50 rows by default
- **Rules:** Hub reads R1, R2 (`skip = 0`, `limit = 50`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 51 orders hubrow(1) … hubrow(51) in W1.
2. O9 = order O9. O0 = order O0.

**When**
- `result = M.list_transfer_orders_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 50`.
2. returns: `result == TOD.list_for_hub(db, workspace_id=W1.id, skip=0, limit=50)`.

### TOM-HUB-02 — the hub count is the DAO's count
- **Rules:** Hub reads R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. hubrow(1), hubrow(2), hubrow(3) in W1.
2. O9 = order O9. O0 = order O0.

**When**
- `result = M.count_transfer_orders_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 3`.
2. returns: `result == TOD.count_for_hub(db, workspace_id=W1.id)`.

### TOM-HUB-03 — the hub stats are the DAO's stats
- **Rules:** Hub reads R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. hubrow(1); hubrow(2), but completed.
2. O9 = order O9.

**When**
- `result = M.transfer_order_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == TOD.aggregate_hub_stats(db, workspace_id=W1.id)`.

### TOM-HUB-04 — the recent list is the DAO's, 10 rows by default
- **Rules:** Hub reads R1, R2 (recent `limit = 10`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 11 orders hubrow(1) … hubrow(11) in W1.

**When**
- `result = M.list_transfer_orders_recent_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 10`.
2. returns: `result == TOD.list_recent_for_hub(db, workspace_id=W1.id, limit=10)`.

### TOM-HUB-05 — the machine-involved count is the DAO's
- **Rules:** Hub reads R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. hubrow(1), but `destination_location_type "machine"`, `destination_location_id M1.id`.
2. hubrow(2).
3. O9 = order O9 (storage F2 → machine M2).

**When**
- `result = M.count_transfer_orders_machine_involved_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == TOD.count_machine_involved_for_hub(db, workspace_id=W1.id)`.

### TOM-HUB-06 — the pending highlights are the DAO's
- **Rules:** Hub reads R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. hubrow(1); line(hubrow(1), 1).
2. hubrow(2), but completed.

**When**
- `result = M.transfer_order_pending_highlights_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == TOD.get_pending_highlights_for_hub(db, workspace_id=W1.id)`.

### TOM-HUB-07 — the hub list passes its filter and paging to the DAO
- **Rules:** Hub reads R1, R3 (G2)
- **Kind:** happy
- **Expect:** pass

**Given**
1. hubrow(1), but `destination_location_type "machine"`, `destination_location_id M1.id`.
2. hubrow(2). hubrow(3).

**When**
- `result = M.list_transfer_orders_for_hub(db, workspace_id=W1.id, skip=0, limit=5, destination_location_type="machine")`.

**Then**
1. returns: `result == TOD.list_for_hub(db, workspace_id=W1.id, skip=0, limit=5, destination_location_type="machine")`.
2. returns: `len(result) != len(TOD.list_for_hub(db, workspace_id=W1.id, skip=0, limit=5))` (the filter changed the result).

### TOM-HUB-08 — the hub count passes `exclude_complete=False` to the DAO
- **Rules:** Hub reads R1, R3 (G2)
- **Kind:** happy
- **Expect:** pass

**Given**
1. hubrow(1); hubrow(2), but completed.

**When**
- `result = M.count_transfer_orders_for_hub(db, workspace_id=W1.id, exclude_complete=False)`.

**Then**
1. returns: `result == TOD.count_for_hub(db, workspace_id=W1.id, exclude_complete=False)`.
2. returns: `result != TOD.count_for_hub(db, workspace_id=W1.id)` (the filter changed the result).

### TOM-HUB-09 — the hub stats pass their filter to the DAO
- **Rules:** Hub reads R1, R3 (G2)
- **Kind:** happy
- **Expect:** pass

**Given**
1. hubrow(1), but `source_location_type "machine"`, `source_location_id M1.id`.
2. hubrow(2); hubrow(3), but completed.

**When**
- `result = M.transfer_order_hub_stats(db, workspace_id=W1.id, source_location_type="machine")`.

**Then**
1. returns: `result == TOD.aggregate_hub_stats(db, workspace_id=W1.id, source_location_type="machine")`.
2. returns: `result != TOD.aggregate_hub_stats(db, workspace_id=W1.id)` (the filter changed the result).

### TOM-HUB-10 — the recent list passes its search and limit to the DAO
- **Rules:** Hub reads R1, R3 (G2)
- **Kind:** happy
- **Expect:** pass

**Given**
1. hubrow(1), hubrow(2), hubrow(3) in W1.

**When**
- `result = M.list_transfer_orders_recent_for_hub(db, workspace_id=W1.id, limit=5, search="TR-H2-")`.

**Then**
1. returns: `result == TOD.list_recent_for_hub(db, workspace_id=W1.id, limit=5, search="TR-H2-")`.
2. returns: `len(result) != len(TOD.list_recent_for_hub(db, workspace_id=W1.id, limit=5))` (the filter changed the result).

### TOM-HUB-11 — the machine-involved count passes `exclude_complete=False` to the DAO
- **Rules:** Hub reads R1, R3 (G2)
- **Kind:** happy
- **Expect:** pass

**Given**
1. hubrow(1), but `destination_location_type "machine"`, `destination_location_id M1.id`, completed.
2. hubrow(2), but `destination_location_type "machine"`, `destination_location_id M1.id`.

**When**
- `result = M.count_transfer_orders_machine_involved_for_hub(db, workspace_id=W1.id, exclude_complete=False)`.

**Then**
1. returns: `result == TOD.count_machine_involved_for_hub(db, workspace_id=W1.id, exclude_complete=False)`.
2. returns: `result != TOD.count_machine_involved_for_hub(db, workspace_id=W1.id)` (the filter changed the result).

### TOM-HUB-12 — the pending highlights pass their search to the DAO
- **Rules:** Hub reads R1, R3 (G2)
- **Kind:** happy
- **Expect:** pass

**Given**
1. hubrow(1); line(hubrow(1), 1).
2. hubrow(2); line(hubrow(2), 1).

**When**
- `result = M.transfer_order_pending_highlights_for_hub(db, workspace_id=W1.id, search="TR-H1-")`.

**Then**
1. returns: `result == TOD.get_pending_highlights_for_hub(db, workspace_id=W1.id, search="TR-H1-")`.
2. returns: `result != TOD.get_pending_highlights_for_hub(db, workspace_id=W1.id)` (the filter changed the result).

### TOM-HUB-13 — an unknown filter keyword raises TypeError
- **Rules:** Hub reads R3 (G2: unknown keyword → `TypeError`)
- **Kind:** error
- **Expect:** pass

**Given**
1. hubrow(1).

**When**
- `M.count_transfer_orders_for_hub(db, workspace_id=W1.id, colour="red")`.

**Then**
1. raises: `TypeError` (plain `pytest.raises`).

## `TransferOrderManager.delete_transfer_order`

Call: **DEL(to_id)** (Conventions) = `M.delete_transfer_order(db, to_id=<id>, workspace_id=W1.id)` plus `user_id=U2.id` only when the method has that parameter (BUG-1194 adds it).

### TOM-D-01 — the order goes with its lines, approvers and events, approvals or not
- **Rules:** `delete_transfer_order` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O. L1 = line(O, 1). L2 = line(O, 2), but `item_id I2.id`.
2. A1 = apr(O, U1, 1), but approved. A2 = apr(O, U3, 2).
3. E1 = ev(O, "created", 1). E2 = ev(O, "item_added", 2).
4. O2 = order O2. K1 = line(O2, 1). B1 = apr(O2, U1, 3). F1E = ev(O2, "created", 3).

**When**
- `result = DEL(O.id)`.

**Then**
1. returns: `result is None`.
2. count: `transfer_orders` with id O.id has 0 rows (after `db.flush()`, raw SQL).
3. count: `transfer_order_items` with `transfer_order_id == O.id` has 0 rows.
4. count: `transfer_order_approvers` with `transfer_order_id == O.id` has 0 rows.
5. count: `transfer_order_events` with `transfer_order_id == O.id` has 0 rows.
6. count: O2 still has 1 line, 1 approver and 1 event.

### TOM-D-02 — a line stored under another workspace is removed with the order
- **Rules:** `delete_transfer_order` R4 [BUG-2890] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-2890
- **Fails today on:** When (the delete raises `IntegrityError`: the ORM sets the foreign line's `transfer_order_id` to NULL at flush)

**Given**
1. O = order O. L1 = line(O, 1).
2. LB = line(O, 2), but `workspace_id W2.id`, `item_id IX.id` (invalid data).

**When**
- `result = DEL(O.id)`.

**Then**
1. returns: `result is None`.
2. count: `transfer_order_items` with `transfer_order_id == O.id` (all workspaces, raw SQL after `db.flush()`) has 0 rows.

### TOM-D-03 — a missing order is 404
- **Rules:** `delete_transfer_order` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.

**When**
- `DEL(MISSING)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Transfer order with ID 999999999 not found"`.
3. session clean.
4. nothing written.

### TOM-D-04 — an order of a higher workspace is 404 and stays
- **Rules:** `delete_transfer_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order O9. N1 = line(O9, 1).

**When**
- `DEL(O9.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Transfer order with ID {O9.id} not found"`.
3. session clean.
4. nothing written.

### TOM-D-05 — an order of a lower workspace is 404 and stays
- **Rules:** `delete_transfer_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O0 = order O0.

**When**
- `DEL(O0.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Transfer order with ID {O0.id} not found"`.
3. nothing written.

### TOM-D-06 — a completed order cannot be deleted
- **Rules:** `delete_transfer_order` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, but completed. L1 = line(O, 1). A1 = apr(O, U1, 1), but approved.

**When**
- `DEL(O.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Cannot delete a completed transfer order"`.
3. session clean.
4. nothing written.

### TOM-D-07 — a delete leaves one audit row
- **Rules:** `delete_transfer_order` R5 [BUG-1194] (owner, 2026-11-01)
- **Kind:** bug
- **Expect:** xfail BUG-1194
- **Fails today on:** Then 1 (the call raises TypeError: there is no `user_id` parameter)

**Given**
1. O = order O (`created_at TS(1)`, created by U1).

**When**
- `result = M.delete_transfer_order(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. audit: AUDIT(O) has exactly 1 row.
3. audit: that row has `workspace_id == W1.id`, `user_id == U2.id`, `action == "transfer_order_deleted"`, `resource_type == "transfer_order"`, `resource_id == O.id`.
4. audit: that row's metadata `== {"number": O.transfer_number, "created_by": U1.id, "created_at": TS(1).isoformat()}`.

### TOM-D-08 — a refused delete leaves no audit row
- **Rules:** `delete_transfer_order` R5 [BUG-1194]
- **Kind:** bug
- **Expect:** xfail BUG-1194
- **Fails today on:** Then 1 (the call raises TypeError, not HTTPException)

**Given**
1. O = order O, but completed.

**When**
- `M.delete_transfer_order(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. audit: AUDIT(O) has 0 rows.
3. nothing written.

### TOM-D-09 — the order row is locked before the completed check
- **Rules:** `delete_transfer_order` R6 [BUG-2892] (HR-10)
- **Kind:** bug
- **Expect:** xfail BUG-2892
- **Fails today on:** Then 2 (no SELECT on `transfer_orders` has `FOR UPDATE OF transfer_orders`)

**Given**
1. O = order O. L1 = line(O, 1).
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = DEL(O.id)`.

**Then**
1. returns: `result is None`.
2. statement: locks `transfer_orders` before the first write (`FOR UPDATE OF transfer_orders`, no `NOWAIT` / `SKIP LOCKED`).

### TOM-D-10 — delete does not commit
- **Rules:** `delete_transfer_order` R3 (flushed, never committed)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order O.

**When**
- commit spy around `result = DEL(O.id)`.

**Then**
1. returns: `result is None`.
2. inside: count `transfer_orders` with id O.id is 0.
3. after: `cm.call_count == 0`.
4. after: count `transfer_orders` with id O.id is 1.

## `TransferOrderManager.mark_order_complete`

Call: `result = M.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`. POST is active in every card (Conventions); the card says its return value. **Ready order** in a Given = order O, L1 = line(O, 1), L2 = line(O, 2), but `item_id I2.id`, `quantity Decimal("5.00")`, A1 = apr(O, U1, 1), but approved (required NULL: 1 of 1, met).

### TOM-MC-01 — completion stamps the order and every unrecorded line
- **Rules:** `mark_order_complete` R5, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. Ready order (O, L1, L2, A1). POST(2).

**When**
- `result = M.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `completed_at == NOW`, `completed_by == U2.id`, `updated_by == U2.id`.
3. re-read L1: `transferred_at == NOW`.
4. re-read L2: `transferred_at == NOW`.

### TOM-MC-02 — completion writes the line, posting and completion events in order
- **Rules:** `mark_order_complete` R5, R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Ready order (O, L1, L2, A1), no events. POST(2).

**When**
- `result = M.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. events: evs(O) == `[("transfer_recorded", "Item #1 transfer recorded", U2.id, {"line_number": 1, "item_id": I1.id}), ("transfer_recorded", "Item #2 transfer recorded", U2.id, {"line_number": 2, "item_id": I2.id}), ("inventory_posted", "2 item(s) posted to inventory", U2.id, {"lines_posted": 2}), ("order_completed", "Transfer order marked complete", U2.id, None)]`.

### TOM-MC-03 — stock is posted once for all lines of the order
- **Rules:** `mark_order_complete` R6
- **Kind:** external
- **Expect:** pass

**Given**
1. Ready order (O, L1, L2, A1). POST(2).

**When**
- `result = M.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. mock called: `pm.call_count == 1`.
3. mock called: posted["to"].id == O.id, `{i.id for i in posted["items"]} == {L1.id, L2.id}`, `posted["workspace_id"] == W1.id`, `posted["user_id"] == U2.id`.

### TOM-MC-04 — a line already recorded keeps its time and gets no event
- **Rules:** `mark_order_complete` R5 (Q5)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Ready order (O, L1, L2, A1), but L1 has `transferred_at TOLD`, `transferred_by "Rahim"`. No events. POST(2).

**When**
- `result = M.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read L1: `transferred_at == TOLD`, `transferred_by == "Rahim"`.
3. re-read L2: `transferred_at == NOW`.
4. events: exactly 1 row of O has `event_type == "transfer_recorded"`, with `description == "Item #2 transfer recorded"`.

### TOM-MC-05 — nothing posted: no posting event, the completion event still
- **Rules:** `mark_order_complete` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Ready order (O, L1, L2, A1), but both lines have `transferred_at TOLD`. No events. POST(0).

**When**
- `result = M.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. events: evs(O) == `[("order_completed", "Transfer order marked complete", U2.id, None)]`.
3. re-read O: `completed_at == NOW`.

### TOM-MC-06 — the posting event counts the lines the posting reports
- **Rules:** `mark_order_complete` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Ready order (O, L1, L2, A1), no events. POST(1).

**When**
- `result = M.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. events: exactly 1 row of O has `event_type == "inventory_posted"`.
3. events: that row has `description == "1 item(s) posted to inventory"`, `metadata_json == {"lines_posted": 1}`, `performed_by == U2.id`.

### TOM-MC-07 — a missing order is 404
- **Rules:** `mark_order_complete` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Ready order (O, L1, L2, A1). POST(2).

**When**
- `M.mark_order_complete(db, to_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Transfer order with ID 999999999 not found"`.
3. mock called: `pm.call_count == 0`.
4. nothing written.

### TOM-MC-08 — an order of a higher workspace is 404
- **Rules:** `mark_order_complete` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order O9. N1 = line(O9, 1). Z1 = apr(O9, U5, 1), but approved. POST(1).

**When**
- `M.mark_order_complete(db, to_id=O9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Transfer order with ID {O9.id} not found"`.
3. mock called: `pm.call_count == 0`.
4. unchanged: unchanged(O9).

### TOM-MC-09 — an order of a lower workspace is 404
- **Rules:** `mark_order_complete` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O0 = order O0. N0 = line(O0, 1), but `item_id I0.id`. POST(1).

**When**
- `M.mark_order_complete(db, to_id=O0.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Transfer order with ID {O0.id} not found"`.
3. unchanged: unchanged(O0).

### TOM-MC-10 — an already completed order is returned unchanged, before any other check
- **Rules:** `mark_order_complete` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, but completed. No lines, no approvers, no events. POST(0).

**When**
- `result = M.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. session clean.
3. re-read O: `completed_at == DONE`, `completed_by == U1.id`, `updated_by is None`.
4. events: evs(O) == `[]`.
5. mock called: `pm.call_count == 0`.

### TOM-MC-11 — approvals not met are refused
- **Rules:** `mark_order_complete` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. Ready order (O, L1, L2, A1), but A1 not approved (`approved False`, `approved_at None`). POST(2).

**When**
- `M.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Required approvals are not met"`.
3. session clean.
4. nothing written.
5. mock called: `pm.call_count == 0`.

### TOM-MC-12 — an order with no line is refused
- **Rules:** `mark_order_complete` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, no lines. A1 = apr(O, U1, 1), but approved. POST(0).

**When**
- `M.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Add at least one item before completing"`.
3. session clean.
4. nothing written.

### TOM-MC-13 — approvals are checked before lines
- **Rules:** `mark_order_complete` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, no lines. A1 = apr(O, U1, 1) (not approved). POST(0).

**When**
- `M.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Required approvals are not met"`.

### TOM-MC-14 — required 0 waives approval
- **Rules:** `mark_order_complete` R3; `approval_summary` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Ready order (O, L1, L2, A1), but O has `required_approvals 0` and A1 is not approved. POST(2).

**When**
- `result = M.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read O: `completed_at == NOW`.

### TOM-MC-15 — no approvers and "All assigned" cannot complete
- **Rules:** `mark_order_complete` R3; `approval_summary` R4 [BUG-1203]
- **Kind:** bug
- **Expect:** xfail BUG-1203
- **Fails today on:** Then 1 (no exception: 0 of 0 counts as met)

**Given**
1. O = order O (required NULL). L1 = line(O, 1). No approvers. POST(1).

**When**
- `M.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Required approvals are not met"`.
3. nothing written.
4. mock called: `pm.call_count == 0`.

### TOM-MC-16 — a stored route with source = destination is refused
- **Rules:** `mark_order_complete` R4a [BUG-2899]
- **Kind:** bug
- **Expect:** xfail BUG-2899
- **Fails today on:** Then 1 (no exception: the order completes)

**Given**
1. O = order O, but `destination_location_id F1.id`, `required_approvals 0` (storage F1 → storage F1). L1 = line(O, 1). POST(1).

**When**
- `M.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Source and destination cannot be the same"`.
3. session clean.
4. nothing written.
5. mock called: `pm.call_count == 0`.

### TOM-MC-17 — a posting error reaches the caller unchanged
- **Rules:** `mark_order_complete` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. Ready order (O, L1, L2, A1). POSTERR.

**When**
- `M.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `exc.value is ERR`.
2. mock called: `pm.call_count == 1`.

### TOM-MC-18 — lines stored under another workspace are neither stamped nor posted
- **Rules:** `mark_order_complete` R5, R6; `_order_items` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Ready order (O, L1, L2, A1).
2. LB = line(O, 3), but `workspace_id W2.id`, `item_id IX.id` (invalid data). POST(2).

**When**
- `result = M.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. re-read LB: `transferred_at is None`.
3. mock called: `{i.id for i in posted["items"]} == {L1.id, L2.id}`.

### TOM-MC-19 — the order row is locked before the completed check
- **Rules:** `mark_order_complete` R9 [BUG-821] (HR-10)
- **Kind:** bug
- **Expect:** xfail BUG-821
- **Fails today on:** Then 2 (no SELECT on `transfer_orders` has `FOR UPDATE OF transfer_orders`)

**Given**
1. Ready order (O, L1, L2, A1). POST(2).
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = M.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. statement: locks `transfer_orders` before the first write (`FOR UPDATE OF transfer_orders`, no `NOWAIT` / `SKIP LOCKED`).

### TOM-MC-20 — completion does not commit
- **Rules:** `mark_order_complete` Side effects (flushed, not committed)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. Ready order (O, L1, L2, A1). POST(2).

**When**
- commit spy around `result = M.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. inside: re-read O: `completed_at == NOW`.
3. after: `cm.call_count == 0`.
4. after: re-read O: `completed_at is None`.

### TOM-MC-21 — a completed order with source = destination is returned unchanged
- **Rules:** `mark_order_complete` R2, R4b (R2 before R4a; G6)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, but completed, `destination_location_id F1.id`, `required_approvals 0` (storage F1 → storage F1). L1 = line(O, 1). No events. POST(1).

**When**
- `result = M.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. session clean.
3. re-read O: `completed_at == DONE`, `completed_by == U1.id`.
4. events: evs(O) == `[]`.
5. mock called: `pm.call_count == 0`.

### TOM-MC-22 — unmet approvals win over source = destination
- **Rules:** `mark_order_complete` R3, R4b (R3 before R4a; G6)
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, but `destination_location_id F1.id` (storage F1 → storage F1; required NULL). L1 = line(O, 1). A1 = apr(O, U1, 1) (not approved). POST(1).

**When**
- `M.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Required approvals are not met"`.
3. session clean.
4. nothing written.
5. mock called: `pm.call_count == 0`.

## `TransferOrderManager._ensure_catalog_item_not_on_to`

### TOM-ECI-01 — an item already on the order is refused with its name
- **Rules:** `_ensure_catalog_item_not_on_to` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. L1 = line(O, 1) (item I1).

**When**
- `M._ensure_catalog_item_not_on_to(db, O.id, I1.id, W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 409`.
2. raises: `detail == "Motor is already on this order"`.

### TOM-ECI-02 — an item not on the order passes
- **Rules:** `_ensure_catalog_item_not_on_to` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O. L1 = line(O, 1) (item I1).

**When**
- `result = M._ensure_catalog_item_not_on_to(db, O.id, I2.id, W1.id)`.

**Then**
1. returns: `result is None`.

### TOM-ECI-03 — the excluded line does not count
- **Rules:** `_ensure_catalog_item_not_on_to` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O. L1 = line(O, 1) (item I1).

**When**
- `result = M._ensure_catalog_item_not_on_to(db, O.id, I1.id, W1.id, exclude_item_id=L1.id)`.

**Then**
1. returns: `result is None`.

### TOM-ECI-04 — an item outside the workspace is named by its id
- **Rules:** `_ensure_catalog_item_not_on_to` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O. L1 = line(O, 1), but `item_id IX.id` (invalid data: W2's item on a W1 line).

**When**
- `M._ensure_catalog_item_not_on_to(db, O.id, IX.id, W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 409`.
2. raises: `detail == f"Item #{IX.id} is already on this order"`.

### TOM-ECI-05 — a line stored under other workspaces does not count
- **Rules:** `_ensure_catalog_item_not_on_to` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order O.
2. LA = line(O, 1), but `workspace_id W0.id` (item I1; invalid data).
3. LB = line(O, 2), but `workspace_id W2.id` (item I1; invalid data).

**When**
- `result = M._ensure_catalog_item_not_on_to(db, O.id, I1.id, W1.id)`.

**Then**
1. returns: `result is None`.

### TOM-ECI-06 — the same item on another order does not count
- **Rules:** `_ensure_catalog_item_not_on_to` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order O. O2 = order O2. K1 = line(O2, 1) (item I1).

**When**
- `result = M._ensure_catalog_item_not_on_to(db, O.id, I1.id, W1.id)`.

**Then**
1. returns: `result is None`.

## `TransferOrderManager.add_item`

Call: `result = M.add_item(db, to_id=O.id, data=ITEM(...), workspace_id=W1.id, user_id=U2.id)`. It returns the new line, flushed (R6). Most cards read the line back from the database; AI-01 also checks the returned row. Check order (R4b): R1, R2, R4a, then R3.

### TOM-AI-01 — the new line takes the highest number + 1, gaps kept
- **Rules:** `add_item` R4, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O. L1 = line(O, 1). L3 = line(O, 3), but `item_id I2.id` (line 2 was removed).
2. A1 = apr(O, U1, 1) (not approved).

**When**
- `result = M.add_item(db, to_id=O.id, data=ITEM(IN, "7", notes="Top shelf"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, TransferOrderItem)`, `result.id is not None`, `result.transfer_order_id == O.id`, `result.item_id == IN.id`, `result.line_number == 4`, `result.notes == "Top shelf"`.
2. count: `transfer_order_items` of O (W1) has exactly 3 rows.
3. re-read the new line (id `result.id`): `item_id == IN.id`, `line_number == 4`, `quantity == Decimal("7.00")`, `notes == "Top shelf"`, `workspace_id == W1.id`.

### TOM-AI-02 — the first line of an empty order is number 1
- **Rules:** `add_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, no lines.

**When**
- `M.add_item(db, to_id=O.id, data=ITEM(I1, "10"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. count: `transfer_order_items` of O has exactly 1 row.
2. re-read that line: `line_number == 1`, `item_id == I1.id`.

### TOM-AI-03 — adding writes one item_added event
- **Rules:** `add_item` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order O, no events. L1 = line(O, 1).

**When**
- `M.add_item(db, to_id=O.id, data=ITEM(I2, "3"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. count: `transfer_order_items` of O has exactly 2 rows.
2. events: evs(O) == `[("item_added", "Item #2 added", U2.id, {"item_id": I2.id, "line_number": 2})]`.

### TOM-AI-04 — a missing order is 404
- **Rules:** `add_item` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.

**When**
- `M.add_item(db, to_id=MISSING, data=ITEM(I1, "1"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. session clean.
3. nothing written.

### TOM-AI-05 — an order of a higher workspace is 404
- **Rules:** `add_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order O9.

**When**
- `M.add_item(db, to_id=O9.id, data=ITEM(I1, "1"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. nothing written.

### TOM-AI-06 — an order of a lower workspace is 404
- **Rules:** `add_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O0 = order O0.

**When**
- `M.add_item(db, to_id=O0.id, data=ITEM(I1, "1"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. nothing written.

### TOM-AI-07 — a completed order refuses a new line
- **Rules:** `add_item` R2 (`_guard_item_mutations` R1)
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, but completed.

**When**
- `M.add_item(db, to_id=O.id, data=ITEM(I1, "1"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Transfer order is complete"`.
3. session clean.
4. nothing written.

### TOM-AI-08 — an approval refuses a new line
- **Rules:** `add_item` R2 (`_guard_item_mutations` R2)
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. A1 = apr(O, U1, 1), but approved.

**When**
- `M.add_item(db, to_id=O.id, data=ITEM(I1, "1"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Withdraw all approvals before editing transfer items"`.
3. session clean.
4. nothing written.

### TOM-AI-09 — an item already on the order is refused
- **Rules:** `add_item` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. L1 = line(O, 1) (item I1).

**When**
- `M.add_item(db, to_id=O.id, data=ITEM(I1, "2"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 409`.
2. raises: `detail == "Motor is already on this order"`.
3. session clean.
4. nothing written.

### TOM-AI-10 — an item of another workspace is refused
- **Rules:** `add_item` R4a [BUG-1018]
- **Kind:** bug
- **Expect:** xfail BUG-1018
- **Fails today on:** Then 1 (no exception: the line is stored)

**Given**
1. O = order O, no lines.

**When**
- `M.add_item(db, to_id=O.id, data=ITEM(IX, "1"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Item with ID {IX.id} not found"`.
3. session clean.
4. nothing written.

### TOM-AI-11 — an item of a lower workspace is refused
- **Rules:** `add_item` R4a [BUG-1018]
- **Kind:** bug
- **Expect:** xfail BUG-1018
- **Fails today on:** Then 1 (no exception: the line is stored)

**Given**
1. O = order O, no lines.

**When**
- `M.add_item(db, to_id=O.id, data=ITEM(I0, "1"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Item with ID {I0.id} not found"`.
3. nothing written.

### TOM-AI-12 — the order row is locked before the item guards
- **Rules:** `_guard_item_mutations` R4 [BUG-2892] (HR-10), via `add_item`
- **Kind:** bug
- **Expect:** xfail BUG-2892
- **Fails today on:** Then 2 (no SELECT on `transfer_orders` has `FOR UPDATE OF transfer_orders`)

**Given**
1. O = order O, no lines.
2. Statement recorder on. `db.expunge_all()`.

**When**
- `M.add_item(db, to_id=O.id, data=ITEM(I1, "1"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. count: `transfer_order_items` of O has exactly 1 row.
2. statement: locks `transfer_orders` before the first write (`FOR UPDATE OF transfer_orders`, no `NOWAIT` / `SKIP LOCKED`).

### TOM-AI-13 — add_item does not commit
- **Rules:** `add_item` (flushed, never committed)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order O, no lines.

**When**
- commit spy around `M.add_item(db, to_id=O.id, data=ITEM(I1, "1"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. inside: count `transfer_order_items` of O is 1.
2. after: `cm.call_count == 0`.
3. after: count `transfer_order_items` of O is 0.

### TOM-AI-14 — a foreign item already on the order is refused as not found, not as a duplicate
- **Rules:** `add_item` R4a [BUG-1018], R4b (R4a before R3)
- **Kind:** bug
- **Expect:** xfail BUG-1018
- **Fails today on:** Then 1 (409 `Item #<id> is already on this order`)

**Given**
1. O = order O. LX = line(O, 1), but `item_id IX.id` (invalid data: a W2 item on a W1 line).

**When**
- `M.add_item(db, to_id=O.id, data=ITEM(IX, "2"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Item with ID {IX.id} not found"`.
3. session clean.
4. nothing written.

### TOM-AI-15 — the item guard runs before the item check
- **Rules:** `add_item` R2, R4b (R2 before R4a)
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, but completed. No lines.

**When**
- `M.add_item(db, to_id=O.id, data=ITEM(IX, "1"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Transfer order is complete"`.
3. session clean.
4. nothing written.

### TOM-AI-16 — a missing item is refused
- **Rules:** `add_item` R4a [BUG-1018]
- **Kind:** bug
- **Expect:** xfail BUG-1018
- **Fails today on:** Then 1 (no `HTTPException` 404 is raised)

**Given**
1. O = order O, no lines.

**When**
- `M.add_item(db, to_id=O.id, data=TransferOrderItemCreate(item_id=MISSING, quantity=Decimal("1")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Item with ID {MISSING} not found"`.
3. session clean.
4. nothing written.

## `TransferOrderManager.update_item`

Call: `M.update_item(db, item_id=L1.id, data=IU(...), workspace_id=W1.id, user_id=U2.id)`. It returns the same line object, flushed (R10). UI-01 checks the returned row. **Open line** in a Given = order O, L1 = line(O, 1) (item I1, quantity 10.00, notes NULL), no approvers, no events. **Met line** = order O, L1 = line(O, 1), A1 = apr(O, U1, 1), but approved, no events.

### TOM-UI-01 — a quantity change is stored
- **Rules:** `update_item` R3, R5, R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. Open line (O, L1).

**When**
- `result = M.update_item(db, item_id=L1.id, data=IU(quantity=Decimal("25")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is L1` (the same object in the session), `result.quantity == Decimal("25")` compared as a number.
2. pending: `L1 not in db.dirty` (the change is flushed).
3. re-read L1: `quantity == Decimal("25.00")`, `notes is None`, `transferred_at is None`.

### TOM-UI-02 — a notes change is stored
- **Rules:** `update_item` R3, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. Open line (O, L1).

**When**
- `M.update_item(db, item_id=L1.id, data=IU(notes="Fragile"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read L1: `notes == "Fragile"`, `quantity == Decimal("10.00")`.

### TOM-UI-03 — a missing line is 404
- **Rules:** `update_item` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Open line (O, L1).

**When**
- `M.update_item(db, item_id=MISSING, data=IU(notes="x"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Transfer order item not found"`.
3. nothing written.

### TOM-UI-04 — a line of a higher workspace is 404
- **Rules:** `update_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order O9. N1 = line(O9, 1).

**When**
- `M.update_item(db, item_id=N1.id, data=IU(notes="x"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Transfer order item not found"`.
3. session clean.
4. unchanged: unchanged(N1).

### TOM-UI-05 — a line of a lower workspace is 404
- **Rules:** `update_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O0 = order O0. N0 = line(O0, 1), but `item_id I0.id`.

**When**
- `M.update_item(db, item_id=N0.id, data=IU(notes="x"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Transfer order item not found"`.
3. unchanged: unchanged(N0).

### TOM-UI-06 — a W1 line on another workspace's order is 404 on the order
- **Rules:** `update_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order O9. LX = line(O9, 1), but `workspace_id W1.id`, `item_id I1.id` (invalid data).

**When**
- `M.update_item(db, item_id=LX.id, data=IU(notes="x"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Transfer order with ID {O9.id} not found"`.
3. unchanged: unchanged(LX).

### TOM-UI-07 — a completed order refuses every line edit, even the transfer name
- **Rules:** `update_item` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, but completed. L1 = line(O, 1).

**When**
- `M.update_item(db, item_id=L1.id, data=IU(transferred_by="Rahim"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Transfer order is complete"`.
3. session clean.
4. unchanged: unchanged(L1).

### TOM-UI-08 — with an approval, a quantity edit is refused
- **Rules:** `update_item` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. Met line (O, L1, A1).

**When**
- `M.update_item(db, item_id=L1.id, data=IU(quantity=Decimal("25")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Withdraw all approvals before editing transfer items"`.
3. session clean.
4. unchanged: unchanged(L1).

### TOM-UI-09 — with an approval, a notes edit is refused
- **Rules:** `update_item` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. Met line (O, L1, A1).

**When**
- `M.update_item(db, item_id=L1.id, data=IU(notes="Fragile"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Withdraw all approvals before editing transfer items"`.
3. unchanged: unchanged(L1).

### TOM-UI-10 — with an approval, the transfer name is not locked
- **Rules:** `update_item` R3, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Met line (O, L1, A1).

**When**
- `M.update_item(db, item_id=L1.id, data=IU(transferred_by="Rahim"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read L1: `transferred_by == "Rahim"`, `transferred_at is None`.
2. events: evs(O) == `[]`.

### TOM-UI-11 — recording a transfer time stores it and logs it
- **Rules:** `update_item` R4, R5, R7, R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. Met line (O, L1, A1).

**When**
- `M.update_item(db, item_id=L1.id, data=IU(transferred_at=TOLD, transferred_by="Rahim"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read L1: `transferred_at == TOLD`, `transferred_by == "Rahim"`.
2. events: evs(O) == `[("transfer_recorded", "Item #1 transfer recorded", U2.id, {"line_number": 1, "item_id": I1.id})]`.
3. count: `inventory_ledger` (all workspaces) has the same number of rows as before the call.
4. re-read O: `completed_at is None`.

### TOM-UI-12 — recording a transfer needs the approvals met
- **Rules:** `update_item` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. Open line (O, L1), plus A1 = apr(O, U1, 1) (not approved).

**When**
- `M.update_item(db, item_id=L1.id, data=IU(transferred_at=TOLD), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Required approvals are not met"`.
3. session clean.
4. nothing written.

### TOM-UI-13 — a future transfer time is accepted
- **Rules:** `update_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Met line (O, L1, A1).

**When**
- `M.update_item(db, item_id=L1.id, data=IU(transferred_at=datetime(2030, 1, 1, 8, 0)), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read L1: `transferred_at == datetime(2030, 1, 1, 8, 0)`.

### TOM-UI-14 — replacing a recorded time stores the new one with no event
- **Rules:** `update_item` R4, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Met line (O, L1, A1), but L1 has `transferred_at TOLD`.

**When**
- `M.update_item(db, item_id=L1.id, data=IU(transferred_at=DONE), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read L1: `transferred_at == DONE`.
2. events: evs(O) == `[]`.

### TOM-UI-15 — fields not sent are left unchanged
- **Rules:** `update_item` R2, R2a (omitted fields)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Met line (O, L1, A1), but L1 has `transferred_at TOLD`, `transferred_by "Rahim"`, `notes "Top shelf"`.

**When**
- `M.update_item(db, item_id=L1.id, data=IU(transferred_by="Karim"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read L1: `transferred_by == "Karim"`, `transferred_at == TOLD`, `notes == "Top shelf"`, `quantity == Decimal("10.00")`.

### TOM-UI-16 — an explicit null clears a recorded transfer and logs it
- **Rules:** `update_item` R2a [BUG-2895], R8
- **Kind:** bug
- **Expect:** xfail BUG-2895
- **Fails today on:** Then 1 (the nulls are ignored: the line still shows TOLD)

**Given**
1. Met line (O, L1, A1), but L1 has `transferred_at TOLD`, `transferred_by "Rahim"`.

**When**
- `M.update_item(db, item_id=L1.id, data=IU(transferred_at=None, transferred_by=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read L1: `transferred_at is None`, `transferred_by is None`.
2. events: evs(O) == `[("transfer_cleared", "Item #1 transfer cleared", U2.id, None)]`.

### TOM-UI-17 — an explicit null clears the notes
- **Rules:** `update_item` R2a [BUG-2895]
- **Kind:** bug
- **Expect:** xfail BUG-2895
- **Fails today on:** Then 1 (the null is ignored: notes stay "Top shelf")

**Given**
1. Open line (O, L1), but L1 has `notes "Top shelf"`.

**When**
- `M.update_item(db, item_id=L1.id, data=IU(notes=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read L1: `notes is None`.

### TOM-UI-18 — a null quantity is refused by the schema
- **Rules:** `update_item` R2a [BUG-2895]
- **Kind:** bug
- **Expect:** xfail BUG-2895
- **Fails today on:** Then 1 (no error: the null is accepted)

**Given**
1. Nothing beyond the standing rows (target `schema`).

**When**
- `TransferOrderItemUpdate(quantity=None)`.

**Then**
1. raises: `ValidationError`, loc `== ("quantity",)`.

### TOM-UI-19 — the line `approved` flag is gone from the schema
- **Rules:** `update_item` R6 [BUG-2896]
- **Kind:** bug
- **Expect:** xfail BUG-2896
- **Fails today on:** Then 1 (`approved` is a field of `TransferOrderItemUpdate`)

**Given**
1. Nothing beyond the standing rows (target `schema`).

**When**
- `fields = TransferOrderItemUpdate.model_fields`.

**Then**
1. returns: `"approved" not in fields`.

### TOM-UI-20 — a quantity change is logged as item_updated
- **Rules:** `update_item` R8a [BUG-2900] (Q2)
- **Kind:** bug
- **Expect:** xfail BUG-2900
- **Fails today on:** Then 2 (no event is written)

**Given**
1. Open line (O, L1).

**When**
- `M.update_item(db, item_id=L1.id, data=IU(quantity=Decimal("25")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read L1: `quantity == Decimal("25.00")`.
2. events: evs(O) == `[("item_updated", "Item #1 updated", U2.id, {"line_number": 1, "item_id": I1.id, "changes": [CH("quantity", "Quantity", "10", "25")]})]`.

### TOM-UI-21 — a notes change is logged as item_updated
- **Rules:** `update_item` R8a [BUG-2900]
- **Kind:** bug
- **Expect:** xfail BUG-2900
- **Fails today on:** Then 2 (no event is written)

**Given**
1. Open line (O, L1) (notes NULL).

**When**
- `M.update_item(db, item_id=L1.id, data=IU(notes="Fragile"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read L1: `notes == "Fragile"`.
2. events: evs(O) == `[("item_updated", "Item #1 updated", U2.id, {"line_number": 1, "item_id": I1.id, "changes": [CH("notes", "Notes", "—", "Fragile")]})]`.

### TOM-UI-22 — an unchanged quantity writes no event
- **Rules:** `update_item` R8a (no change)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Open line (O, L1) (quantity 10.00).

**When**
- `M.update_item(db, item_id=L1.id, data=IU(quantity=Decimal("10")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read L1: `quantity == Decimal("10.00")`.
2. events: evs(O) == `[]`.

### TOM-UI-23 — the order row is locked before the item guards
- **Rules:** `_guard_item_mutations` R4 [BUG-2892] (HR-10), via `update_item`
- **Kind:** bug
- **Expect:** xfail BUG-2892
- **Fails today on:** Then 2 (no SELECT on `transfer_orders` has `FOR UPDATE OF transfer_orders`)

**Given**
1. Open line (O, L1).
2. Statement recorder on. `db.expunge_all()`.

**When**
- `M.update_item(db, item_id=L1.id, data=IU(quantity=Decimal("25")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read L1: `quantity == Decimal("25.00")`.
2. statement: locks `transfer_orders` before the first write (`FOR UPDATE OF transfer_orders`, no `NOWAIT` / `SKIP LOCKED`).

### TOM-UI-24 — update_item does not commit
- **Rules:** `update_item` (flushed, never committed)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. Open line (O, L1).

**When**
- commit spy around `M.update_item(db, item_id=L1.id, data=IU(notes="Fragile"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. inside: re-read L1: `notes == "Fragile"`.
2. after: `cm.call_count == 0`.
3. after: re-read L1: `notes is None`.

## `TransferOrderManager.remove_item`

Call: `result = M.remove_item(db, item_id=<line>.id, workspace_id=W1.id, user_id=U2.id)`.

### TOM-RI-01 — the line is deleted, the others keep their numbers
- **Rules:** `remove_item` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O, no events. L1 = line(O, 1). L2 = line(O, 2), but `item_id I2.id`. L3 = line(O, 3), but `item_id IN.id`.

**When**
- `result = M.remove_item(db, item_id=L2.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == L2.id`.
2. count: `transfer_order_items` with id L2.id has 0 rows (after `db.flush()`).
3. re-read L1: `line_number == 1`.
4. re-read L3: `line_number == 3`.
5. events: evs(O) == `[("item_removed", "Item #2 removed", U2.id, None)]`.

### TOM-RI-02 — a missing line is 404
- **Rules:** `remove_item` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. L1 = line(O, 1).

**When**
- `M.remove_item(db, item_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Transfer order item not found"`.
3. nothing written.

### TOM-RI-03 — a line of another workspace is 404 and stays
- **Rules:** `remove_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order O9. N1 = line(O9, 1).

**When**
- `M.remove_item(db, item_id=N1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Transfer order item not found"`.
3. session clean.
4. nothing written.

### TOM-RI-04 — a W1 line on another workspace's order is 404
- **Rules:** `remove_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order O9. LX = line(O9, 1), but `workspace_id W1.id`, `item_id I1.id` (invalid data).

**When**
- `M.remove_item(db, item_id=LX.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. nothing written.

### TOM-RI-05 — a completed order keeps its lines
- **Rules:** `remove_item` R2 (`_guard_item_mutations` R1)
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, but completed. L1 = line(O, 1).

**When**
- `M.remove_item(db, item_id=L1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Transfer order is complete"`.
3. session clean.
4. nothing written.

### TOM-RI-06 — an approval keeps the lines
- **Rules:** `remove_item` R2 (`_guard_item_mutations` R2)
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. L1 = line(O, 1). A1 = apr(O, U1, 1), but approved.

**When**
- `M.remove_item(db, item_id=L1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Withdraw all approvals before editing transfer items"`.
3. session clean.
4. nothing written.

### TOM-RI-07 — remove_item does not commit
- **Rules:** `remove_item` (flushed, never committed)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order O. L1 = line(O, 1).

**When**
- commit spy around `result = M.remove_item(db, item_id=L1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == L1.id`.
2. inside: count `transfer_order_items` with id L1.id is 0.
3. after: `cm.call_count == 0`.
4. after: count `transfer_order_items` with id L1.id is 1.

### TOM-RI-08 — the order row is locked before the item guards
- **Rules:** `_guard_item_mutations` R4 [BUG-2892] (HR-10), via `remove_item`
- **Kind:** bug
- **Expect:** xfail BUG-2892
- **Fails today on:** Then 2 (no SELECT on `transfer_orders` has `FOR UPDATE OF transfer_orders`)

**Given**
1. O = order O. L1 = line(O, 1).
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = M.remove_item(db, item_id=L1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == L1.id`.
2. statement: locks `transfer_orders` before the first write (`FOR UPDATE OF transfer_orders`, no `NOWAIT` / `SKIP LOCKED`).

## `TransferOrderManager.get_items`

### TOM-GI-01 — the order's lines by line number
- **Rules:** `get_items` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O. L2 = line(O, 2), but `item_id I2.id`. L1 = line(O, 1) (inserted in that order).
2. LB = line(O, 3), but `workspace_id W2.id`, `item_id IX.id` (invalid data).

**When**
- `result = M.get_items(db, to_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [L1.id, L2.id]`.

### TOM-GI-02 — no lines gives an empty list
- **Rules:** `get_items` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, no lines.

**When**
- `result = M.get_items(db, to_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `list(result) == []`.

### TOM-GI-03 — a missing order is 404
- **Rules:** `get_items` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.

**When**
- `M.get_items(db, to_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.

### TOM-GI-04 — an order of another workspace is 404
- **Rules:** `get_items` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order O9. N1 = line(O9, 1).

**When**
- `M.get_items(db, to_id=O9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.

## `TransferOrderManager.list_approvers`

Call: `result = M.list_approvers(db, to_id=O.id, workspace_id=W1.id)`. **trip(result)** = `[(a.id, p.id if p else None, pos) for a, p, pos in result]`.

### TOM-LA-01 — approvers by assignment time, with profile and position
- **Rules:** `list_approvers` R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O.
2. A1 = apr(O, U1, 5). A2 = apr(O, U2, 2) (inserted in that order: the later id has the earlier time).

**When**
- `result = M.list_approvers(db, to_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `trip(result) == [(A2.id, U2.id, "Factory Head"), (A1.id, U1.id, "Store Manager")]`.

### TOM-LA-02 — the position comes whatever the membership status; none without one
- **Rules:** `list_approvers` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O.
2. A4 = apr(O, U4, 1) (U4: W1 member, status `inactive`, position "Clerk").
3. A3 = apr(O, U3, 2) (U3: active W1 member, no position).

**When**
- `result = M.list_approvers(db, to_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `trip(result) == [(A4.id, U4.id, "Clerk"), (A3.id, U3.id, None)]`.

### TOM-LA-03 — a membership in another workspace gives no position
- **Rules:** `list_approvers` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order O.
2. A5 = apr(O, U5, 1) (U5: member of W2 only, position "Boss").

**When**
- `result = M.list_approvers(db, to_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `trip(result) == [(A5.id, U5.id, None)]`.

### TOM-LA-04 — approver rows stored under other workspaces are not listed
- **Rules:** `list_approvers` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order O.
2. AZ = apr(O, U3, 1), but `workspace_id W0.id` (invalid data).
3. A1 = apr(O, U1, 2).
4. AY = apr(O, U2, 3), but `workspace_id W2.id` (invalid data).

**When**
- `result = M.list_approvers(db, to_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `trip(result) == [(A1.id, U1.id, "Store Manager")]`.

### TOM-LA-05 — a missing order is 404
- **Rules:** `list_approvers` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.

**When**
- `M.list_approvers(db, to_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.

### TOM-LA-06 — an order of another workspace is 404
- **Rules:** `list_approvers` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order O9. Z1 = apr(O9, U5, 1).

**When**
- `M.list_approvers(db, to_id=O9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.

### TOM-LA-07 — profiles and memberships are read together
- **Rules:** `list_approvers` R4 [BUG-2902]
- **Kind:** bug
- **Expect:** xfail BUG-2902
- **Fails today on:** Then 2 (one profile read per approver: 3 SELECTs)

**Given**
1. O = order O.
2. A1 = apr(O, U1, 1). A2 = apr(O, U2, 2). A3 = apr(O, U3, 3).
3. Statement recorder on. `db.expunge_all()`.

**When**
- `result = M.list_approvers(db, to_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. statement: `len(sel("profiles")) <= 1`.
3. statement: `len(sel("workspace_members")) <= 1`.

## `TransferOrderManager.approval_summary`

Call: `result = M.approval_summary(db, O)` with the order object from the Given.

### TOM-AS-01 — "All assigned" needs every approver
- **Rules:** `approval_summary` R1, R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O (required NULL).
2. A1 = apr(O, U1, 1), but approved. A2 = apr(O, U2, 2).

**When**
- `result = M.approval_summary(db, O)`.

**Then**
1. returns: `result == (1, 2, False)`.

### TOM-AS-02 — every approver approved is met
- **Rules:** `approval_summary` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O (required NULL).
2. A1 = apr(O, U1, 1), but approved. A2 = apr(O, U2, 2), but approved.

**When**
- `result = M.approval_summary(db, O)`.

**Then**
1. returns: `result == (2, 2, True)`.

### TOM-AS-03 — an explicit number replaces the approver count
- **Rules:** `approval_summary` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, but `required_approvals 1`.
2. A1 = apr(O, U1, 1), but approved. A2 = apr(O, U2, 2).

**When**
- `result = M.approval_summary(db, O)`.

**Then**
1. returns: `result == (1, 1, True)`.

### TOM-AS-04 — an explicit 0 waives approval
- **Rules:** `approval_summary` R2 (`0` included)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, but `required_approvals 0`.
2. A1 = apr(O, U1, 1).

**When**
- `result = M.approval_summary(db, O)`.

**Then**
1. returns: `result == (0, 0, True)`.

### TOM-AS-05 — one approval short is not met
- **Rules:** `approval_summary` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, but `required_approvals 3`.
2. A1 = apr(O, U1, 1), but approved. A2 = apr(O, U2, 2), but approved.

**When**
- `result = M.approval_summary(db, O)`.

**Then**
1. returns: `result == (2, 3, False)`.

### TOM-AS-06 — approvals stored under other workspaces are not counted
- **Rules:** `approval_summary` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order O, but `required_approvals 1`.
2. AZ = apr(O, U3, 1), but `workspace_id W0.id`, approved (invalid data).
3. A1 = apr(O, U1, 2).
4. AY = apr(O, U2, 3), but `workspace_id W2.id`, approved (invalid data).

**When**
- `result = M.approval_summary(db, O)`.

**Then**
1. returns: `result == (0, 1, False)`.

### TOM-AS-07 — the order's own workspace is used, not a fixed one
- **Rules:** `approval_summary` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order O9 (W2, required NULL).
2. Z1 = apr(O9, U5, 1), but approved.

**When**
- `result = M.approval_summary(db, O9)`.

**Then**
1. returns: `result == (1, 1, True)`.

### TOM-AS-08 — no approvers and "All assigned" is 0 of 1, not met
- **Rules:** `approval_summary` R4 [BUG-1203] (owner)
- **Kind:** bug
- **Expect:** xfail BUG-1203
- **Fails today on:** Then 1 (today `(0, 0, True)`)

**Given**
1. O = order O (required NULL), no approvers.

**When**
- `result = M.approval_summary(db, O)`.

**Then**
1. returns: `result == (0, 1, False)`.

## `TransferOrderManager.approvals_met`

### TOM-AM-01 — met is returned
- **Rules:** `approvals_met` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O (required NULL). A1 = apr(O, U1, 1), but approved.

**When**
- `result = M.approvals_met(db, O)`.

**Then**
1. returns: `result is True`.

### TOM-AM-02 — not met is returned
- **Rules:** `approvals_met` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O (required NULL). A1 = apr(O, U1, 1), but approved. A2 = apr(O, U2, 2).

**When**
- `result = M.approvals_met(db, O)`.

**Then**
1. returns: `result is False`.

## `TransferOrderManager.add_approver`

Call: `result = M.add_approver(db, to_id=O.id, user_id=<U>.id, workspace_id=W1.id, assigned_by=U1.id)`.

### TOM-AA-01 — an active member is added and logged
- **Rules:** `add_approver` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O, no events. A1 = apr(O, U1, 1).

**When**
- `result = M.add_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. returns: `result.user_id == U2.id`, `result.id is not None`.
2. re-read the new row: `transfer_order_id == O.id`, `workspace_id == W1.id`, `assigned_by == U1.id`, `approved is False`.
3. events: evs(O) == `[("approver_added", "Added Nadia Islam as approver", U1.id, {"user_id": U2.id, "user_name": "Nadia Islam"})]`.

### TOM-AA-02 — adding raises "All assigned"
- **Rules:** `add_approver` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order O (required NULL). A1 = apr(O, U1, 1), but approved.

**When**
- `result = M.add_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. returns: `result.user_id == U2.id`.
2. summary: SUMMARY(O) == `(1, 2, False)`.

### TOM-AA-03 — a missing order is 404
- **Rules:** `add_approver` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.

**When**
- `M.add_approver(db, to_id=MISSING, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. nothing written.

### TOM-AA-04 — an order of another workspace is 404
- **Rules:** `add_approver` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order O9.

**When**
- `M.add_approver(db, to_id=O9.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. session clean.
3. nothing written.

### TOM-AA-05 — a member of another workspace only is refused
- **Rules:** `add_approver` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.

**When**
- `M.add_approver(db, to_id=O.id, user_id=U5.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "User is not an active member of this workspace"`.
3. session clean.
4. nothing written.

### TOM-AA-06 — an inactive member is refused
- **Rules:** `add_approver` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.

**When**
- `M.add_approver(db, to_id=O.id, user_id=U4.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "User is not an active member of this workspace"`.
3. nothing written.

### TOM-AA-07 — an existing approver is refused
- **Rules:** `add_approver` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. A2 = apr(O, U2, 1).

**When**
- `M.add_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 409`.
2. raises: `detail == "User is already an approver for this order"`.
3. session clean.
4. nothing written.

### TOM-AA-08 — being an approver of another order does not count
- **Rules:** `add_approver` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order O. O2 = order O2. B2 = apr(O2, U2, 1).

**When**
- `result = M.add_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. returns: `result.user_id == U2.id`.
2. count: `transfer_order_approvers` of O has exactly 1 row.

### TOM-AA-09 — a completed order refuses a new approver
- **Rules:** `add_approver` R5 [BUG-2897]
- **Kind:** bug
- **Expect:** xfail BUG-2897
- **Fails today on:** Then 1 (no exception: the approver is added)

**Given**
1. O = order O, but completed. A1 = apr(O, U1, 1), but approved.

**When**
- `M.add_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Transfer order is complete"`.
3. session clean.
4. nothing written.

### TOM-AA-10 — add_approver does not commit
- **Rules:** `add_approver` (flushed, never committed)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order O.

**When**
- commit spy around `result = M.add_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. returns: `result.user_id == U2.id`.
2. inside: count `transfer_order_approvers` of O is 1.
3. after: `cm.call_count == 0`.
4. after: count `transfer_order_approvers` of O is 0.

### TOM-AA-11 — the order row is locked before the completed check
- **Rules:** `add_approver` R6 [BUG-2892] (HR-10, G10)
- **Kind:** bug
- **Expect:** xfail BUG-2892
- **Fails today on:** Then 2 (no SELECT on `transfer_orders` has `FOR UPDATE OF transfer_orders`)

**Given**
1. O = order O. A1 = apr(O, U1, 1). Read `oid = O.id`, `u1 = U1.id`, `u2 = U2.id`, `w1 = W1.id` into locals.
2. Statement recorder on. `db.expunge_all()`.

**When**
- `M.add_approver(db, to_id=oid, user_id=u2, workspace_id=w1, assigned_by=u1)`.

**Then**
1. count: `transfer_order_approvers` of O has exactly 2 rows.
2. statement: locks `transfer_orders` before the first write (`FOR UPDATE OF transfer_orders`, no `NOWAIT` / `SKIP LOCKED`).

### TOM-AA-12 — an empty profile name is used as stored
- **Rules:** `add_approver` R4, R4a (G4)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. U6 = `make_profile(db, name="")`. `WorkspaceMember(workspace_id=W1.id, user_id=U6.id, role="member", status="active", position=None)`.
2. O = order O, no events.

**When**
- `result = M.add_approver(db, to_id=O.id, user_id=U6.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. returns: `result.user_id == U6.id`.
2. events: evs(O) == `[("approver_added", "Added  as approver", U1.id, {"user_id": U6.id, "user_name": ""})]` (two spaces between "Added" and "as").

## `TransferOrderManager.remove_approver`

Call: `M.remove_approver(db, to_id=O.id, user_id=<U>.id, workspace_id=W1.id, performed_by=U1.id)` unless the card leaves `performed_by` out. It returns `None` (R2b), which RA-01 checks.

### TOM-RA-01 — an approved approver is removed and logged
- **Rules:** `remove_approver` R2, R2b
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O, no events. A1 = apr(O, U1, 1). A2 = apr(O, U2, 2), but approved.

**When**
- `result = M.remove_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, performed_by=U1.id)`.

**Then**
1. returns: `result is None`.
2. count: `transfer_order_approvers` with id A2.id has 0 rows (after `db.flush()`).
3. count: `transfer_order_approvers` of O has exactly 1 row.
4. events: evs(O) == `[("approver_removed", "Removed Nadia Islam as approver", U1.id, {"user_id": U2.id, "user_name": "Nadia Islam"})]`.

### TOM-RA-02 — without performed_by the event has no performer
- **Rules:** `remove_approver` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, no events. A2 = apr(O, U2, 1).

**When**
- `M.remove_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. count: `transfer_order_approvers` of O has 0 rows.
2. events: exactly 1 row of O, `event_type == "approver_removed"`, `performed_by is None`.

### TOM-RA-03 — someone not an approver is 404
- **Rules:** `remove_approver` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. A1 = apr(O, U1, 1).

**When**
- `M.remove_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, performed_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Approver not found"`.
3. session clean.
4. nothing written.

### TOM-RA-04 — an approver of another workspace's order is 404
- **Rules:** `remove_approver` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order O9. Z1 = apr(O9, U5, 1).

**When**
- `M.remove_approver(db, to_id=O9.id, user_id=U5.id, workspace_id=W1.id, performed_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Approver not found"`.
3. nothing written.

### TOM-RA-05 — removing the other approver can make approvals met
- **Rules:** `remove_approver` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order O (required NULL). A1 = apr(O, U1, 1), but approved. A2 = apr(O, U2, 2).

**When**
- `M.remove_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, performed_by=U1.id)`.

**Then**
1. count: `transfer_order_approvers` of O has exactly 1 row.
2. summary: SUMMARY(O) == `(1, 1, True)`.

### TOM-RA-06 — a completed order keeps its approvers
- **Rules:** `remove_approver` R4 [BUG-2897]
- **Kind:** bug
- **Expect:** xfail BUG-2897
- **Fails today on:** Then 1 (no exception: the approver is removed)

**Given**
1. O = order O, but completed. A1 = apr(O, U1, 1), but approved. A2 = apr(O, U2, 2), but approved.

**When**
- `M.remove_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, performed_by=U1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Transfer order is complete"`.
3. session clean.
4. nothing written.

### TOM-RA-07 — remove_approver does not commit
- **Rules:** `remove_approver` (flushed, never committed)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order O. A2 = apr(O, U2, 1).

**When**
- commit spy around `M.remove_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, performed_by=U1.id)`.

**Then**
1. inside: count `transfer_order_approvers` of O is 0.
2. after: `cm.call_count == 0`.
3. after: count `transfer_order_approvers` of O is 1.

### TOM-RA-08 — the order row is locked before the completed check
- **Rules:** `remove_approver` R5 [BUG-2892] (HR-10, G10)
- **Kind:** bug
- **Expect:** xfail BUG-2892
- **Fails today on:** Then 2 (no SELECT on `transfer_orders` has `FOR UPDATE OF transfer_orders`; today the order is not read at all)

**Given**
1. O = order O. A1 = apr(O, U1, 1). A2 = apr(O, U2, 2). Read `oid = O.id`, `u1 = U1.id`, `u2 = U2.id`, `w1 = W1.id` into locals.
2. Statement recorder on. `db.expunge_all()`.

**When**
- `M.remove_approver(db, to_id=oid, user_id=u2, workspace_id=w1, performed_by=u1)`.

**Then**
1. count: `transfer_order_approvers` of O has exactly 1 row.
2. statement: locks `transfer_orders` before the first write (`FOR UPDATE OF transfer_orders`, no `NOWAIT` / `SKIP LOCKED`).

## `TransferOrderManager.set_approval`

Call: `result = M.set_approval(db, to_id=O.id, user_id=U1.id, workspace_id=W1.id, approved=<bool>)`. **Ready to approve** in a Given = order O, L1 = line(O, 1), A1 = apr(O, U1, 1) (not approved), no events.

### TOM-SA-01 — approving stamps the row and logs it
- **Rules:** `set_approval` R3, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. Ready to approve (O, L1, A1).

**When**
- `result = M.set_approval(db, to_id=O.id, user_id=U1.id, workspace_id=W1.id, approved=True)`.

**Then**
1. returns: `result.id == A1.id`.
2. re-read A1: `approved is True`, `approved_at == NOW`.
3. events: evs(O) == `[("approved", "Approved transfer order", U1.id, None)]`.

### TOM-SA-02 — withdrawing clears the stamp and logs it
- **Rules:** `set_approval` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. Ready to approve (O, L1, A1), but A1 approved.

**When**
- `result = M.set_approval(db, to_id=O.id, user_id=U1.id, workspace_id=W1.id, approved=False)`.

**Then**
1. returns: `result.id == A1.id`.
2. re-read A1: `approved is False`, `approved_at is None`.
3. events: evs(O) == `[("approval_withdrawn", "Withdrew approval", U1.id, None)]`.

### TOM-SA-03 — someone not an approver is refused
- **Rules:** `set_approval` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Ready to approve (O, L1, A1).

**When**
- `M.set_approval(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, approved=True)`.

**Then**
1. raises: `HTTPException`, `status_code == 403`.
2. raises: `detail == "You are not an assigned approver for this order"`.
3. session clean.
4. nothing written.

### TOM-SA-04 — an approver of another workspace's order is refused
- **Rules:** `set_approval` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order O9. N1 = line(O9, 1). Z1 = apr(O9, U5, 1).

**When**
- `M.set_approval(db, to_id=O9.id, user_id=U5.id, workspace_id=W1.id, approved=True)`.

**Then**
1. raises: `HTTPException`, `status_code == 403`.
2. raises: `detail == "You are not an assigned approver for this order"`.
3. unchanged: unchanged(Z1).

### TOM-SA-05 — the approver check runs before the order lookup
- **Rules:** `set_approval` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Ready to approve (O, L1, A1).

**When**
- `M.set_approval(db, to_id=MISSING, user_id=U1.id, workspace_id=W1.id, approved=True)`.

**Then**
1. raises: `HTTPException`, `status_code == 403`.
2. raises: `detail == "You are not an assigned approver for this order"`.

### TOM-SA-06 — an approver row whose order is not in the workspace is 404
- **Rules:** `set_approval` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order O9. N1 = line(O9, 1).
2. AX = apr(O9, U1, 1), but `workspace_id W1.id` (invalid data: a W1 approver row on W2's order).

**When**
- `M.set_approval(db, to_id=O9.id, user_id=U1.id, workspace_id=W1.id, approved=True)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. unchanged: unchanged(AX).

### TOM-SA-07 — approving needs a defined route
- **Rules:** `set_approval` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. Ready to approve (O, L1, A1), but O has `destination_location_id 0`.

**When**
- `M.set_approval(db, to_id=O.id, user_id=U1.id, workspace_id=W1.id, approved=True)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Set source and destination before approving"`.
3. session clean.
4. nothing written.

### TOM-SA-08 — approving needs a route that goes somewhere
- **Rules:** `set_approval` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. Ready to approve (O, L1, A1), but O has `destination_location_id F1.id` (storage F1 → storage F1).

**When**
- `M.set_approval(db, to_id=O.id, user_id=U1.id, workspace_id=W1.id, approved=True)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Source and destination cannot be the same"`.
3. nothing written.

### TOM-SA-09 — approving needs a line
- **Rules:** `set_approval` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, no lines, no events. A1 = apr(O, U1, 1).

**When**
- `M.set_approval(db, to_id=O.id, user_id=U1.id, workspace_id=W1.id, approved=True)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Add at least one item before approving"`.
3. nothing written.

### TOM-SA-10 — withdrawing has no readiness check
- **Rules:** `set_approval` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, but `destination_location_id 0`, no lines, no events. A1 = apr(O, U1, 1), but approved.

**When**
- `result = M.set_approval(db, to_id=O.id, user_id=U1.id, workspace_id=W1.id, approved=False)`.

**Then**
1. returns: `result.id == A1.id`.
2. re-read A1: `approved is False`, `approved_at is None`.

### TOM-SA-11 — approving twice keeps the first stamp and logs nothing
- **Rules:** `set_approval` R6 [BUG-2898]
- **Kind:** bug
- **Expect:** xfail BUG-2898
- **Fails today on:** Then 3 (`approved_at` moves to NOW)

**Given**
1. Ready to approve (O, L1, A1), but A1 approved (`approved_at TOLD`).

**When**
- `result = M.set_approval(db, to_id=O.id, user_id=U1.id, workspace_id=W1.id, approved=True)`.

**Then**
1. returns: `result.id == A1.id`.
2. re-read A1: `approved is True`.
3. re-read A1: `approved_at == TOLD`.
4. events: evs(O) == `[]`.

### TOM-SA-12 — approving twice still leaves the row approved
- **Rules:** `set_approval` R4, R6 (the side that holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Ready to approve (O, L1, A1), but A1 approved (`approved_at TOLD`).

**When**
- `result = M.set_approval(db, to_id=O.id, user_id=U1.id, workspace_id=W1.id, approved=True)`.

**Then**
1. returns: `result.id == A1.id`.
2. re-read A1: `approved is True`, `approved_at is not None`.

### TOM-SA-13 — withdrawing when not approved logs nothing
- **Rules:** `set_approval` R6 [BUG-2898]
- **Kind:** bug
- **Expect:** xfail BUG-2898
- **Fails today on:** Then 3 (an `approval_withdrawn` event is written)

**Given**
1. Ready to approve (O, L1, A1) (A1 not approved).

**When**
- `result = M.set_approval(db, to_id=O.id, user_id=U1.id, workspace_id=W1.id, approved=False)`.

**Then**
1. returns: `result.id == A1.id`.
2. re-read A1: `approved is False`, `approved_at is None`.
3. events: evs(O) == `[]`.

### TOM-SA-14 — a completed order refuses an approval
- **Rules:** `set_approval` R5 [BUG-2897]
- **Kind:** bug
- **Expect:** xfail BUG-2897
- **Fails today on:** Then 1 (no exception: the approval is written)

**Given**
1. Ready to approve (O, L1, A1), but O completed.

**When**
- `M.set_approval(db, to_id=O.id, user_id=U1.id, workspace_id=W1.id, approved=True)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Transfer order is complete"`.
3. session clean.
4. nothing written.
5. unchanged: unchanged(A1).

### TOM-SA-15 — a completed order refuses a withdrawal
- **Rules:** `set_approval` R5 [BUG-2897]
- **Kind:** bug
- **Expect:** xfail BUG-2897
- **Fails today on:** Then 1 (no exception: the approval is withdrawn)

**Given**
1. Ready to approve (O, L1, A1), but O completed and A1 approved.

**When**
- `M.set_approval(db, to_id=O.id, user_id=U1.id, workspace_id=W1.id, approved=False)`.

**Then**
1. raises: `HTTPException`, `status_code == 400`.
2. raises: `detail == "Transfer order is complete"`.
3. session clean.
4. nothing written.
5. unchanged: unchanged(A1).

### TOM-SA-16 — the order row is locked before the checks
- **Rules:** `set_approval` R7 [BUG-2892] (HR-10)
- **Kind:** bug
- **Expect:** xfail BUG-2892
- **Fails today on:** Then 2 (no SELECT on `transfer_orders` has `FOR UPDATE OF transfer_orders`)

**Given**
1. Ready to approve (O, L1, A1).
2. Statement recorder on. `db.expunge_all()`.

**When**
- `result = M.set_approval(db, to_id=O.id, user_id=U1.id, workspace_id=W1.id, approved=True)`.

**Then**
1. returns: `result.id == A1.id`.
2. statement: locks `transfer_orders` before the first write (`FOR UPDATE OF transfer_orders`, no `NOWAIT` / `SKIP LOCKED`).

### TOM-SA-17 — set_approval does not commit
- **Rules:** `set_approval` (flushed, never committed)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. Ready to approve (O, L1, A1).

**When**
- commit spy around `result = M.set_approval(db, to_id=O.id, user_id=U1.id, workspace_id=W1.id, approved=True)`.

**Then**
1. returns: `result.id == A1.id`.
2. inside: re-read A1: `approved is True`.
3. after: `cm.call_count == 0`.
4. after: re-read A1: `approved is False`.

### TOM-SA-18 — withdrawing when not approved still leaves the row unapproved
- **Rules:** `set_approval` R4, R6 (the side that holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Ready to approve (O, L1, A1) (A1 not approved).

**When**
- `result = M.set_approval(db, to_id=O.id, user_id=U1.id, workspace_id=W1.id, approved=False)`.

**Then**
1. returns: `result.id == A1.id`.
2. re-read A1: `approved is False`, `approved_at is None`.

## `TransferOrderManager.log_event`

### TOM-LE-01 — one row with the given values
- **Rules:** `log_event` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O, no events.

**When**
- `result = M.log_event(db, to_id=O.id, workspace_id=W1.id, event_type="attachment_added", description="File added", performed_by=U2.id, metadata={"file": "a.pdf", "n": 2})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the row: `transfer_order_id == O.id`, `workspace_id == W1.id`, `event_type == "attachment_added"`, `description == "File added"`, `performed_by == U2.id`.
3. re-read the row: `metadata_json == {"file": "a.pdf", "n": 2}`, `created_at is not None`.

### TOM-LE-02 — performer and metadata default to none
- **Rules:** `log_event` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, no events.

**When**
- `result = M.log_event(db, to_id=O.id, workspace_id=W1.id, event_type="note", description="Plain")`.

**Then**
1. returns: `result.id is not None`.
2. re-read the row: `performed_by is None`, `metadata_json is None`, `event_type == "note"`.

### TOM-LE-03 — an order of a higher workspace is refused
- **Rules:** `log_event` R2 [BUG-1192] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-1192
- **Fails today on:** Then 1 (no exception: the event is stored under W1)

**Given**
1. O9 = order O9.

**When**
- `M.log_event(db, to_id=O9.id, workspace_id=W1.id, event_type="note", description="Plain")`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Transfer order with ID {O9.id} not found"`.
3. session clean.
4. nothing written.

### TOM-LE-04 — an order of a lower workspace is refused
- **Rules:** `log_event` R2 [BUG-1192]
- **Kind:** bug
- **Expect:** xfail BUG-1192
- **Fails today on:** Then 1 (no exception: the event is stored under W1)

**Given**
1. O0 = order O0.

**When**
- `M.log_event(db, to_id=O0.id, workspace_id=W1.id, event_type="note", description="Plain")`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == f"Transfer order with ID {O0.id} not found"`.
3. nothing written.

### TOM-LE-05 — a missing order is 404, not a database error
- **Rules:** `log_event` R2 [BUG-1192]
- **Kind:** bug
- **Expect:** xfail BUG-1192
- **Fails today on:** Then 1 (the call raises IntegrityError at flush)
- **Author:** claude

**Given**
1. O = order O.

**When**
- `M.log_event(db, to_id=MISSING, workspace_id=W1.id, event_type="note", description="Plain")` inside `db.begin_nested()` (so a database error today leaves the session usable).

**Then**
1. raises: `HTTPException`, `status_code == 404`.
2. raises: `detail == "Transfer order with ID 999999999 not found"`.
3. nothing written.

### TOM-LE-06 — log_event does not commit
- **Rules:** `log_event` R1 (flushes, never commits)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order O, no events.

**When**
- commit spy around `result = M.log_event(db, to_id=O.id, workspace_id=W1.id, event_type="note", description="Plain")`.

**Then**
1. returns: `result.id is not None`.
2. inside: count `transfer_order_events` of O is 1.
3. after: `cm.call_count == 0`.
4. after: count `transfer_order_events` of O is 0.

## `TransferOrderManager.list_events`

Call: `result = M.list_events(db, to_id=O.id, workspace_id=W1.id)`. **pairs(result)** = `[(e.id, p.id if p else None) for e, p in result]`.

### TOM-LEV-01 — newest first, ties by id descending, with the performer's profile
- **Rules:** `list_events` R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O.
2. E1 = ev(O, "created", 2), but `performed_by U2.id`.
3. E2 = ev(O, "note", 5) (no performer).
4. E3 = ev(O, "note", 2), but `performed_by U1.id`.

**When**
- `result = M.list_events(db, to_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `pairs(result) == [(E2.id, None), (E3.id, U1.id), (E1.id, U2.id)]`.

### TOM-LEV-02 — events stored under other workspaces are not listed
- **Rules:** `list_events` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order O.
2. EZ = ev(O, "note", 3), but `workspace_id W0.id` (invalid data).
3. E1 = ev(O, "created", 1).
4. EY = ev(O, "note", 4), but `workspace_id W2.id` (invalid data).

**When**
- `result = M.list_events(db, to_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `pairs(result) == [(E1.id, None)]`.

### TOM-LEV-03 — a missing order is 404
- **Rules:** `list_events` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.

**When**
- `M.list_events(db, to_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.

### TOM-LEV-04 — an order of another workspace is 404
- **Rules:** `list_events` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O9 = order O9. EN = ev(O9, "created", 1).

**When**
- `M.list_events(db, to_id=O9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `status_code == 404`.

### TOM-LEV-05 — performers are read together
- **Rules:** `list_events` R4 [BUG-2902]
- **Kind:** bug
- **Expect:** xfail BUG-2902
- **Fails today on:** Then 2 (one profile read per event with a performer: 3 SELECTs)

**Given**
1. O = order O.
2. E1 = ev(O, "note", 1), but `performed_by U1.id`. E2 = ev(O, "note", 2), but `performed_by U2.id`. E3 = ev(O, "note", 3), but `performed_by U3.id`.
3. Statement recorder on. `db.expunge_all()`.

**When**
- `result = M.list_events(db, to_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. statement: `len(sel("profiles")) <= 1`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `_guard_confirmed_updates` R6, `_guard_item_mutations` R4, `delete_transfer_order` R6, `set_approval` R7, `add_approver` R6, `remove_approver` R5 [BUG-2892]; `mark_order_complete` R9 [BUG-821] race outcome | integration tests (two sessions) | the loser waits on the lock, sees the new state and gets the normal error; two completions post each line once |
| Hub reads R1: what each filter selects, paging, stage and status ticks (BUG-2654 … BUG-2660) | `tests/unit/dao/transfer_order.cases.md` | filters, order and stage rules; here the manager is only compared with the DAO for the same keywords (HUB-01 … HUB-13) |
| `create_transfer_order` R2: number format `TR-<year>-NNN` (BUG-2650 … BUG-2653) | `TransferOrderDAO.get_next_number` (DAO cases NN) | numbering per workspace and year; here the number is patched (NUMP) |
| `_order_items` R1 / `get_items` R2 ties (BUG-2657) | `TransferOrderItemDAO.get_by_order` | ties on line number |
| `list_approvers` R2 ties (BUG-1200) | `TransferOrderApproverDAO.get_by_order` | ties on `assigned_at` |
| `list_events` R2 order and ties | `TransferOrderEventDAO.get_by_order` | newest first, then id descending |
| `mark_order_complete` R6 stock moves | `tests/unit/managers/to_inventory.cases.md` | ledger rows, costs and shortage errors of `post_transfer_order_inventory` |
| `create_transfer_order` R4 / `mark_order_complete` R6: the service rolls back | `TransferOrderService` (TC1–TC6) | after the 409 or a posting error, nothing stays committed |
| Schema rules (BUG-823, BUG-824, BUG-2895 route nulls, BUG-2901) answer 422 | `POST` / `PUT /transfer-orders/…` endpoints | a `ValidationError` becomes 422 |
| `delete_transfer_order` R5 [BUG-1194]: the endpoint passes the current user; OQ-55 notifications | `DELETE /transfer-orders/{id}/`; `TransferOrderService` (`docs/future/notifications.md`) | `user_id` reaches the manager; nobody is told after an approval wipe today |

## Spec gaps
None. Gaps 1–9 of Revision 1 are closed by the spec's Gap log (G1–G9). G10, the approver locks, came from the coordinator. Gap 10 of Revision 2 (`create_transfer_order` R2e vs R4) is closed by G11: new rule R4b [BUG-2889], applied in TOM-C-11.

## Retired IDs
- **TOM-C-12** (Revision 2, G1): it pinned R4's `Item #<id>` fallback through create with a foreign item. After BUG-1018, R2b refuses that item first, so the fallback can't be reached through create. C-34 tests the intended 404 instead. The fallback text is still covered by direct call in ECI-04.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_is_completed` | R1 | TOM-IC-01, IC-02, IC-03 |
| `_route_defined` | R1 | TOM-RD-01 … RD-05 |
| `_route_valid` | R1 | TOM-RVL-01 |
| `_route_valid` | R2 | TOM-RVL-02 … RVL-05 |
| `_order_items` | R1 | TOM-OI-01, OI-02, OI-03, RFA-05, MC-18, GI-01 |
| `_ready_for_approval` | R1 | TOM-RFA-01 … RFA-06 |
| `_validate_ready_for_approval` | R1 | TOM-VRA-01, SA-07 |
| `_validate_ready_for_approval` | R2 | TOM-VRA-02, SA-08 |
| `_validate_ready_for_approval` | R3 | TOM-VRA-03, SA-09 |
| `_validate_ready_for_approval` | R4 | TOM-VRA-01, VRA-04, VRA-05 |
| `_has_any_approval` | R1 | TOM-HAA-01 … HAA-05 |
| `_format_scalar_value` | R1 | TOM-FSV-01, FSV-11 |
| `_format_scalar_value` | R2 | TOM-FSV-02, FSV-03 |
| `_format_scalar_value` | R3 | TOM-FSV-04, FSV-05, FSV-06 |
| `_format_scalar_value` | R4 | TOM-FSV-07 … FSV-10 |
| `_format_scalar_value` | R5 | TOM-FSV-11 |
| `_format_location_id` | R1 | TOM-FLI-01 |
| `_format_location_id` | R2 | TOM-FLI-04, FLI-14 |
| `_format_location_id` | R3 | TOM-FLI-02, FLI-03, FLI-05, FLI-06 |
| `_format_location_id` | R4 | TOM-FLI-07 … FLI-10 |
| `_format_location_id` | R5 | TOM-FLI-11, FLI-12 |
| `_format_location_id` | R6 | TOM-FLI-13, FLI-14 |
| `_format_location_id` | R7 | TOM-FLI-15 … FLI-19 |
| `_format_field_value` | R1 | TOM-FFV-01 … FFV-08 |
| `_format_field_value` | R2 | TOM-FFV-09, FFV-10, FFV-11 |
| `_format_field_value` | R3 | TOM-FFV-12, FFV-13, FFV-14 |
| `_format_field_value` | R4 | TOM-FFV-15, FFV-16 |
| `_collect_field_changes` | R1 | TOM-CFC-01, CFC-02 |
| `_collect_field_changes` | R2 | TOM-CFC-03, CFC-04, CFC-08 |
| `_collect_field_changes` | R3 | TOM-CFC-01, CFC-09 |
| `_collect_field_changes` | R4 | TOM-CFC-05 … CFC-08 |
| `_collect_field_changes` | R5 | TOM-CFC-02, CFC-04 |
| `_log_field_change_event` | R1 | TOM-LFC-01 |
| `_log_field_change_event` | R2 | TOM-LFC-02 |
| `_log_field_change_event` | R3 (G3) | TOM-LFC-01, LFC-02 |
| `_guard_confirmed_updates` | R1 | TOM-GCU-01, U-13 |
| `_guard_confirmed_updates` | R2 | TOM-GCU-02, U-14 |
| `_guard_confirmed_updates` | R3 | TOM-GCU-03, U-19 |
| `_guard_confirmed_updates` | R4 | TOM-GCU-06 … GCU-10, GCU-12, GCU-13, U-20, U-22 |
| `_guard_confirmed_updates` | R5 | TOM-GCU-04, GCU-05, GCU-11, U-21 |
| `_guard_confirmed_updates` | R6 [BUG-2892] | TOM-U-44 |
| `_guard_confirmed_updates` | R7 (G3) | TOM-GCU-13 |
| `_guard_item_mutations` | R1 | TOM-GIM-01, GIM-02, AI-07, RI-05 |
| `_guard_item_mutations` | R2 | TOM-GIM-03, AI-08, RI-06, UI-08, UI-09 |
| `_guard_item_mutations` | R3 (G3: returns None) | TOM-GIM-04, GIM-05, AI-01 |
| `_guard_item_mutations` | R4 [BUG-2892] | TOM-AI-12, UI-23, RI-08 |
| `create_transfer_order` | R1; Errors 1 | TOM-C-07, C-08 |
| `create_transfer_order` | R2 | TOM-C-01, C-08, C-09, C-33 |
| `create_transfer_order` | R2a [BUG-2894]; Errors 3 | TOM-C-13 … C-20 (pass side C-09) |
| `create_transfer_order` | R2b [BUG-1018]; Errors 4 | TOM-C-21 … C-24, C-34 |
| `create_transfer_order` | R2c [BUG-825]; Errors 5 | TOM-C-25 |
| `create_transfer_order` | R2d [BUG-823] / [BUG-824] (G7) | TOM-C-27, C-28, C-30, C-31, C-32, C-35, C-36, C-38 (pass side C-26, C-29, C-37) |
| `create_transfer_order` | R2e (G1) | TOM-C-34 (R2b before R4); R4 before the writes: Spec gaps 10 |
| `create_transfer_order` | R3 | TOM-C-03 |
| `create_transfer_order` | R4; Errors 2 | TOM-C-10, C-11 (C-12 retired; fallback text: ECI-04) |
| `create_transfer_order` | R4b [BUG-2889] | TOM-C-11 |
| `create_transfer_order` | R5 | TOM-C-02 |
| `create_transfer_order` | R6 | TOM-C-05, C-06 |
| `create_transfer_order` | R7 | TOM-C-04 |
| `update_transfer_order` | R1 | TOM-U-03, U-04, U-05 |
| `update_transfer_order` | R2 (omitted fields; today's ignored null is superseded by R2a) | TOM-U-06, U-31 |
| `update_transfer_order` | R2a [BUG-2895] | TOM-U-07 … U-12, U-25 |
| `update_transfer_order` | R3 | TOM-U-13, U-14, U-19, U-20, U-21, U-22 |
| `update_transfer_order` | R3a [BUG-2894], BUG-823 / BUG-825 | TOM-U-34 … U-39 (pass side U-02, U-42) |
| `update_transfer_order` | R3b [BUG-2899] | TOM-U-40, U-41 (pass side U-42) |
| `update_transfer_order` | R4 | TOM-U-01, U-02, U-17, U-22, U-27 |
| `update_transfer_order` | R5 | TOM-U-01, U-02, U-42, U-45 |
| `update_transfer_order` | R6 | TOM-U-28, U-45 |
| `update_transfer_order` | R6a [BUG-2903] | TOM-U-23 … U-26 (pass side U-22, U-27) |
| `update_transfer_order` | R6c (G8) | TOM-U-23 … U-26 (whole event list in id order) |
| `update_transfer_order` | R6b | TOM-U-29, U-31 (stamp: U-30) |
| `update_transfer_order` | R7 [BUG-2893] | TOM-U-15, U-16, U-18, U-30 (pass side U-01) |
| `update_transfer_order` | Errors: schema 422 (R2a, BUG-2901) | TOM-U-09 … U-12, U-32, U-33 |
| `update_transfer_order` | flushed, not committed | TOM-U-43 |
| `get_transfer_order` | R1 (G5: `current_status` joined-loaded) | TOM-G-01, G-05 |
| `get_transfer_order` | R2 | TOM-G-02, G-03, G-04 |
| Hub reads | R1 | TOM-HUB-01 … HUB-12 |
| Hub reads | R2 | TOM-HUB-01, HUB-04 |
| Hub reads | R3 (G2) | TOM-HUB-07 … HUB-13 |
| `delete_transfer_order` | R1 | TOM-D-03, D-04, D-05 |
| `delete_transfer_order` | R2 | TOM-D-06 |
| `delete_transfer_order` | R3 | TOM-D-01, D-10 |
| `delete_transfer_order` | R4 [BUG-2890] | TOM-D-02 |
| `delete_transfer_order` | R5 [BUG-1194] | TOM-D-07, D-08 |
| `delete_transfer_order` | R6 [BUG-2892] | TOM-D-09 |
| `mark_order_complete` | R1 | TOM-MC-07, MC-08, MC-09 |
| `mark_order_complete` | R2 | TOM-MC-10 |
| `mark_order_complete` | R3 | TOM-MC-11, MC-13, MC-14, MC-15 |
| `mark_order_complete` | R4 | TOM-MC-12, MC-13 |
| `mark_order_complete` | R4a [BUG-2899] | TOM-MC-16 |
| `mark_order_complete` | R4b (G6) | TOM-MC-21, MC-22 (with MC-10, MC-13) |
| `mark_order_complete` | R5 | TOM-MC-01, MC-02, MC-04, MC-18 |
| `mark_order_complete` | R6 | TOM-MC-03, MC-17, MC-18 |
| `mark_order_complete` | R7 | TOM-MC-01, MC-20 |
| `mark_order_complete` | R8 | TOM-MC-02, MC-05, MC-06 |
| `mark_order_complete` | R9 [BUG-821] | TOM-MC-19 |
| `_ensure_catalog_item_not_on_to` | R1 | TOM-ECI-01, ECI-03, ECI-04, ECI-05, ECI-06 |
| `_ensure_catalog_item_not_on_to` | R2 | TOM-ECI-02, ECI-03 |
| `add_item` | R1 | TOM-AI-04, AI-05, AI-06 |
| `add_item` | R2 | TOM-AI-07, AI-08, AI-15 |
| `add_item` | R3 | TOM-AI-09 |
| `add_item` | R4 | TOM-AI-01, AI-02 |
| `add_item` | R4a [BUG-1018], [BUG-824] | TOM-AI-10, AI-11, AI-14, AI-16; quantity schema TOM-C-29 … C-32 |
| `add_item` | R4b (G1) | TOM-AI-14 (R4a before R3), AI-15 (R2 before R4a) |
| `add_item` | R5 | TOM-AI-03 |
| `add_item` | R6 (G3) | TOM-AI-01 |
| `add_item` | flushed, not committed | TOM-AI-13 |
| `update_item` | R1 | TOM-UI-03 … UI-07 |
| `update_item` | R2 (omitted fields; today's ignored null is superseded by R2a) | TOM-UI-15 |
| `update_item` | R2a [BUG-2895] | TOM-UI-16, UI-17, UI-18 |
| `update_item` | R3 | TOM-UI-01, UI-02, UI-08, UI-09, UI-10 |
| `update_item` | R4 | TOM-UI-11 … UI-14 |
| `update_item` | R5 | TOM-UI-01, UI-02, UI-10, UI-11, UI-15 |
| `update_item` | R6 [BUG-2896] | TOM-UI-19 |
| `update_item` | R7 (G9: `performed_by`) | TOM-UI-11, UI-14 |
| `update_item` | R8 (G9: `performed_by`) | TOM-UI-16 |
| `update_item` | R8a [BUG-2900] | TOM-UI-20, UI-21 (pass side UI-22) |
| `update_item` | R9 | TOM-UI-11 |
| `update_item` | R10 (G3) | TOM-UI-01 |
| `update_item` | flushed, not committed | TOM-UI-24 |
| `remove_item` | R1 | TOM-RI-02, RI-03, RI-04 |
| `remove_item` | R2 | TOM-RI-05, RI-06 |
| `remove_item` | R3 (G9: `performed_by`) | TOM-RI-01, RI-07 |
| `get_items` | R1 | TOM-GI-03, GI-04 |
| `get_items` | R2 | TOM-GI-01, GI-02 |
| `list_approvers` | R1 | TOM-LA-05, LA-06 |
| `list_approvers` | R2 | TOM-LA-01, LA-04 |
| `list_approvers` | R2a (G4) | no card: no profile cannot be stored (FK, CASCADE) |
| `list_approvers` | R3 | TOM-LA-01, LA-02, LA-03 |
| `list_approvers` | R4 [BUG-2902] | TOM-LA-07 |
| `approval_summary` | R1 | TOM-AS-01, AS-06, AS-07 |
| `approval_summary` | R2 | TOM-AS-01, AS-03, AS-04, MC-14 |
| `approval_summary` | R2a [BUG-2901] | TOM-U-32 (pass side U-33) |
| `approval_summary` | R3 | TOM-AS-01 … AS-05 |
| `approval_summary` | R4 [BUG-1203] | TOM-AS-08, MC-15 |
| `approvals_met` | R1 | TOM-AM-01, AM-02 |
| `add_approver` | R1 | TOM-AA-03, AA-04 |
| `add_approver` | R2 | TOM-AA-05, AA-06 |
| `add_approver` | R3 | TOM-AA-07, AA-08 |
| `add_approver` | R4 | TOM-AA-01, AA-02, AA-10, AA-12 |
| `add_approver` | R4a (G4) | TOM-AA-12 (empty name); `User #<id>` fallback unreachable, no card |
| `add_approver` | R5 [BUG-2897] | TOM-AA-09 |
| `add_approver` | R6 [BUG-2892] (G10) | TOM-AA-11 |
| `remove_approver` | R1 | TOM-RA-03, RA-04 |
| `remove_approver` | R2 | TOM-RA-01, RA-02, RA-07 |
| `remove_approver` | R2a (G4) | no card: `User #<id>` fallback unreachable |
| `remove_approver` | R2b (G3) | TOM-RA-01 |
| `remove_approver` | R3 | TOM-RA-05 |
| `remove_approver` | R4 [BUG-2897] | TOM-RA-06 |
| `remove_approver` | R5 [BUG-2892] (G10) | TOM-RA-08 |
| `set_approval` | R1 | TOM-SA-03, SA-04, SA-05 |
| `set_approval` | R2 | TOM-SA-06 |
| `set_approval` | R3 | TOM-SA-01, SA-07 … SA-10 |
| `set_approval` | R4 | TOM-SA-01, SA-02, SA-12, SA-18, SA-17 |
| `set_approval` | R5 [BUG-2897] | TOM-SA-14, SA-15 |
| `set_approval` | R6 [BUG-2898] | TOM-SA-11, SA-13 (pass side SA-12, SA-18) |
| `set_approval` | R7 [BUG-2892] | TOM-SA-16 |
| `log_event` | R1 | TOM-LE-01, LE-02, LE-06 |
| `log_event` | R2 [BUG-1192] | TOM-LE-03, LE-04, LE-05 |
| `list_events` | R1 | TOM-LEV-03, LEV-04 |
| `list_events` | R2 | TOM-LEV-01, LEV-02 |
| `list_events` | R3 | TOM-LEV-01, RA-02 |
| `list_events` | R3a (G4) | TOM-LEV-01 (no performer); a performer without a profile cannot be stored, no card |
| `list_events` | R4 [BUG-2902] | TOM-LEV-05 |
