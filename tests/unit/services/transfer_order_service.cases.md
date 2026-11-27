# Test cases — `app/services/transfer_order_service.py`

> **Spec:** `tests/unit/services/transfer_order_service.spec.md` (source commit e48a092; APPROVED 2026-11-21)
> **Status:** READY
> **Revision:** 2 (2026-11-22) — spec Gap log G1–G5 applied: exact lock clause `FOR UPDATE OF transfer_orders` ("lock first" redefined, U-13 and AI-11 tightened); the pre-read 404 rolls back pending changes in `update_transfer_order` / `add_item` and leaves them pending in `approval_summary_for` (U-01, U-02, AI-06 gain X + x_gone; AS-02 gains spies + X stays); notification patch targets named (new U-18, AI-13, AA-10: a raise while notifying rolls everything back); R4b reason recorded on U-11 (no new card); G5 needs no card change.
> **Revision:** 3 (2026-11-22) — executor note: `_hub_filter_kwargs` is an instance method, so HF-01…04 call `svc._hub_filter_kwargs(...)`. Counts unchanged.
> **Revision:** 4 (2026-11-22) — verifier findings 1–6 (`transfer_order_service.verify.md`, NEEDS WORK). (1) TC3 refusal cards of delete / update_item / remove_item / remove_approver / set_approval (D-02, D-03, UI-02, UI-03, RI-03, RI-04, RA-03, SA-03, SA-04) check `X not in db` right after the call. (2) HR-16 W0 cards G-03, AS-03. (3) HF-05 passes `destination_location_type="all"` (and `source_location_type=""`). (4) HS-02 uses `exclude_complete=False` (not the DAO default), so the machine count expects 2. (5) U-13 uses a routed order with a line and a description edit, and checks that the snapshot read `transfer_order_items`. (6) MISSING-id 404 cards U-19, AI-14.
> **Counts:** 114 cases · 106 expected-to-pass · 8 expected-to-fail (bugs) · 9 deferred

## Reviewer summary
- **Per callable:** `create_transfer_order` 7 · `update_transfer_order` 19 (3 bug) · `get_transfer_order` 3 · `list_transfer_orders` 3 · `_hub_filter_kwargs` 5 · `list_transfer_orders_page` 7 · `get_transfer_order_hub_stats` 5 · `delete_transfer_order` 6 (2 bug) · `mark_order_complete` 8 · `add_item` 14 (1 bug) · `update_item` 5 · `remove_item` 5 · `get_items` 1 · `list_events` 1 · `list_approvers` 1 · `approval_summary_for` 3 · `add_approver` 10 (1 bug) · `remove_approver` 5 (1 bug) · `set_approval` 6.
- **Depth:** full for the decisions the service adds itself (readiness snapshot and the notifications, the hub page and stats shaping, `has_more`), because they cause duplicate side effects and drive order state. The transaction contract is covered per write: one commit card (TC1 + TC2 `loaded`), at least one refusal card that adds an **uncommitted extra workspace X** after the commit point and checks it is gone (TC3), one failing-commit card (TC4), and a failing-refresh card (TC5) where the spec applies TC5. Each read is checked with commit / rollback spies and a pending X that stays (TC6). Manager rules are not re-tested: one pass-through card per manager outcome the service exposes (404, guard 400, 409).
- **Expected-to-fail:** BUG-3142 2 (U-13, AI-11: SQL recorder, `FOR UPDATE OF transfer_orders` before the first readiness read of `transfer_order_items`, no `NOWAIT` / `SKIP LOCKED`) · BUG-1194 2 (D-05, D-06) · pass-through BUG-2899 1 (U-12) · BUG-2903 1 (U-14) · BUG-2897 2 (AA-08, RA-05). All strict. Passing companions: the notification paths that hold today and after the BUG-3142 fix (U-04 … U-08, AI-02 … AI-05); delete through DEL (D-01 … D-04); no notice on a `required_approvals` change (U-09).
- **Notable design choices:**
  - **Stock.** Every `mark_order_complete` card patches `post_transfer_order_inventory` (spec and manager Notes allow it). To prove the service rolls back writes made *inside* the posting, MC-04 and MC-07 use a probe side effect that flushes one marker event row before raising / returning; the marker must be gone. Real ledger rows are left to `to_inventory` and integration tests.
  - **U-11 (R4b) is tagged "retire when BUG-2899 is fixed":** it uses the source = destination edit, which BUG-2899 will refuse (U-12 is its strict xfail). Once BUG-2899, BUG-2894 and BUG-823 are fixed, R4b is unreachable through this method; it stays a pass-through pointer to the helper's R2 and gets no replacement card (spec G4).
  - **A raise while notifying** (U-18, AI-13, AA-10) patches the helper name the service imported with a probe that flushes one marker event row, then raises; the marker, the write and X must all be gone.
  - **Concurrency (BUG-3142)** is not reproduced: only the lock clause and its position are checked in the SQL; the two-session race is deferred.
  - Notifications are compared as a list sorted in Python (`notes(T)`), so their write order does not matter.
- **Needs a decision:** none. Every Revision 1 spec gap is closed (see Spec gaps).

## Conventions for this module

**IDs.** `TOS` = this module. C create · U update · G get · LT `list_transfer_orders` · HF `_hub_filter_kwargs` · LP `list_transfer_orders_page` · HS hub stats · D delete · MC `mark_order_complete` · AI `add_item` · UI `update_item` · RI `remove_item` · GI `get_items` · LE `list_events` · LA `list_approvers` · AS `approval_summary_for` · AA `add_approver` · RA `remove_approver` · SA `set_approval`.

**Actors and fixed values.**
- `svc` = `transfer_order_service` (`from app.services.transfer_order_service import TransferOrderService, transfer_order_service`); `M` = `svc.manager`. `db` = the test's real session, first argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- Models from `app.models.<snake_name>`: `TransferOrder`, `TransferOrderItem`, `TransferOrderApprover`, `TransferOrderEvent` (column `metadata` mapped as `metadata_json`), `Status`, `Factory`, `Machine`, `Item`, `WorkspaceMember`, `Workspace`, `Notification` (`app.models.notification`). Schemas `TransferOrderCreate`, `TransferOrderUpdate`, `TransferOrderItemCreate`, `TransferOrderItemUpdate`, `TransferOrderListResponse`, `TransferOrderHubStatsResponse` (`app.schemas.transfer_order`). `HTTPException` (fastapi), `IntegrityError` (sqlalchemy.exc), `Decimal`, `datetime`, `timedelta`, `patch`, `os`, `uuid`, `inspect`, `text`, `select`, `func`.
- MISSING = `999999999`. GN(s) = `f"{s}-{os.getpid()}-{uuid.uuid4().hex[:6]}"`. XID(k) = `800_000_000 + (os.getpid() % 1_000_000) * 10 + k`. TNUM = `GN("TR-NEW")`, made once per test.
- TS(h) = `datetime(2026, 3, 4, 0, 0) + timedelta(hours=h)`. DONE = `datetime(2026, 3, 20, 9, 0)`. TOLD = `datetime(2026, 3, 22, 8, 0)`. NOW = `datetime(2026, 3, 25, 12, 0)`. Naive; a stamp `== X` compares the re-read value with tzinfo removed.
- PEND(n, m) = `f"{n} of {m} approval(s) collected"`. GAP_ITEM = `"Add at least one item before approvals can proceed"`.

**Externals (every test).** `app.managers.transfer_order_manager.utcnow` patched to return NOW. NUMP = `patch.object(M.to_dao, "get_next_number", return_value=TNUM)`, active in every create card. MC cards patch `app.managers.transfer_order_manager.post_transfer_order_inventory` as `pm`: POST(n) = `return_value=n`; ERR = `HTTPException(status_code=400, detail="Insufficient stock for Motor")`; PROBE_OK / PROBE_ERR = `side_effect` = a function `(*args, **kwargs)` that runs `db.add(TransferOrderEvent(workspace_id=W1.id, transfer_order_id=O_ID, event_type="probe", description="Probe"))`, `db.flush()`, then returns `1` / raises `ERR` (`O_ID` = O.id read at the commit point). Notification-raise cards patch the helper name the service imported (spec G3): NU = `patch("app.services.transfer_order_service.handle_order_update_notifications", side_effect=NPROBE)`, NA = `patch("app.services.transfer_order_service.handle_add_approver", side_effect=NPROBE)`, each bound as `nh`; NPROBE = a function `(*args, **kwargs)` that adds and flushes the same probe event row as PROBE_ERR, then raises `RuntimeError("notify boom")`. Nothing else is mocked.

**Standing rows** (every test, in this order, each flushed, no Given line):
1. W0, W1, W2 = `make_workspace(db)` ×3 (`W0.id < W1.id < W2.id`). U1 … U5 = `make_profile(db, name=…)`: `"Karim Ahmed"`, `"Nadia Islam"`, `"Rahim Uddin"`, `"Sumi Akter"`, `"Tanvir Hasan"`.
2. `WorkspaceMember(workspace_id, user_id, role="member", status, position)`: U1 (W1, `"active"`, "Store Manager"), U2 (W1, `"active"`, "Factory Head"), U3 (W1, `"active"`, None), U4 (W1, `"inactive"`, "Clerk"), U5 (W2, `"active"`, "Boss").
3. S0 / S1 / S2 = `Status(workspace_id=W0/W1/W2.id, name="Open", comment="stage")`.
4. `Factory(workspace_id, name, abbreviation)`: F0 (W0, "Zulu Depot", "ZD"), F1 (W1, "Alpha Works", "AW"), FB (W1, "Bravo Yard", "BY"), F2 (W2, "Yankee Store", "YS").
5. M1 = `Machine(id=XID(1), workspace_id=W1.id, factory_id=F1.id, name="Press Kilo")`.
6. `Item(workspace_id, name, name_normalized, unit="pcs")`: I1 (W1, "Motor", "motor"), I2 (W1, "Bearing", "bearing"), IX (W2, "Valve", "valve").

**Given rows.** Inserted directly (never through `svc`), flushed one at a time in the order written. After "but" a line lists every column that differs. A line written as code is a step to run exactly.
- **order O** = `TransferOrder(workspace_id=W1.id, transfer_number=GN("TR-O"), source_location_type="storage", source_location_id=F1.id, destination_location_type="storage", destination_location_id=FB.id, current_status_id=S1.id, created_by=U1.id, description="Old text", created_at=TS(1))`; `required_approvals`, `completed_at`, `completed_by`, `updated_by` NULL. **order O0** = order O, but `workspace_id W0.id`, `transfer_number GN("TR-O0")`, `source_location_id F0.id`, `destination_location_type "damaged"`, `destination_location_id F0.id`, `current_status_id S0.id`. **order O9** = order O, but `workspace_id W2.id`, `transfer_number GN("TR-O9")`, `source_location_id F2.id`, `destination_location_type "damaged"`, `destination_location_id F2.id`, `current_status_id S2.id`. **completed** = `completed_at DONE`, `completed_by U1.id`. **looped** = `destination_location_id F1.id` (source = destination).
- **line(T, k)** = `TransferOrderItem(workspace_id=T.workspace_id, transfer_order_id=T.id, line_number=k, item_id=I1.id, quantity=Decimal("10.00"))` (IX on O9); notes, `transferred_at`, `transferred_by` NULL, `approved` False.
- **apr(T, U, h)** = `TransferOrderApprover(workspace_id=T.workspace_id, transfer_order_id=T.id, user_id=U.id, assigned_by=U1.id, approved=False, approved_at=None, assigned_at=TS(h))`. **approved** = `approved True`, `approved_at TOLD`.
- **ev(T, type, h)** = `TransferOrderEvent(workspace_id=T.workspace_id, transfer_order_id=T.id, event_type=type, description="Logged", created_at=TS(h))`.
- **commit point** = after the last Given line the test runs `db.commit()`; snapshots for `unchanged` and `nothing written` are taken there. **X** (after the commit point, only where listed) = `X = make_workspace(db)`, flushed, not committed; `X_ID = X.id`.
- **CREATE(k=v)** = `TransferOrderCreate(source_location_type="storage", source_location_id=F1.id, destination_location_type="storage", destination_location_id=FB.id, current_status_id=S1.id, description="Monthly move")` with the listed keys replaced or added. **ITEM(I, "q")** = `TransferOrderItemCreate(item_id=I.id, quantity=Decimal("q"))`. **UPD(k=v)** = `TransferOrderUpdate(**k)`; **IU(k=v)** = `TransferOrderItemUpdate(**k)`; only listed fields are sent.
- **DEL(id)** = `svc.delete_transfer_order(db, to_id=id, workspace_id=W1.id)`, plus `user_id=U2.id` when `"user_id" in inspect.signature(svc.delete_transfer_order).parameters`.
- **HO(k, h, **cols)** (hub cards) = order O, but `transfer_number GN(f"TR-H{k}")`, `created_at TS(h)`, plus the listed columns.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its commit-point value.
- **nothing written** = the row counts (all workspaces) of `transfer_orders`, `transfer_order_items`, `transfer_order_approvers`, `transfer_order_events`, `notifications`, `workspace_audit_logs`, `inventory_ledger` equal their commit-point values.
- **notes(T)** = `sorted((n.notification_type, n.recipient_user_id, n.actor_user_id, n.source_type, n.source_id, n.preview) for n in <Notification rows with entity_type == "transfer_order" and entity_id == T.id>)`, read with a fresh query.
- **types(T)** = `[e.event_type for e in <TransferOrderEvent rows of transfer_order_id T.id, by id>]`, fresh query.
- **loaded(r)** = `inspect(r).expired_attributes.isdisjoint({c.key for c in inspect(type(r)).column_attrs})`; runs first, before any attribute of `r` is read.
- **x_gone** = `db.get(Workspace, X_ID) is None`. It runs after the test's own `db.rollback()`, so on its own it cannot show that the service rolled back. The TC3 refusal cards of `delete_transfer_order`, `update_item`, `remove_item`, `remove_approver` and `set_approval`, and the MISSING-id cards U-19 and AI-14, therefore also check `session: X not in db` right after the call (Revision 4, verifier finding 1).
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads with a fresh query.
- `session:` lines check `db` right after the call, before any re-read. "usable" = `db.execute(text("SELECT 1")).scalar() == 1`.
- `raises: <Type>` = plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint; further lines on `exc.value`, one assert per line.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "refresh", side_effect=RuntimeError("boom")):` around the When.
- **Statement recorder** = a `before_cursor_execute` listener records every SQL statement of the When, in order. A recorder card reads the ids it needs into locals, then runs `db.expunge_all()` as its last Given line. **lock first** = some SELECT whose FROM names `transfer_orders` ends in exactly `FOR UPDATE OF transfer_orders` (whitespace collapsed; a bare `FOR UPDATE` or any other `OF` list does not count; spec G1) and is recorded **before** the first SELECT whose FROM names `transfer_order_items`; and no recorded statement of the call contains `NOWAIT` or `SKIP LOCKED`.

**xfail cards.** `pytest.mark.xfail(strict=True, reason="BUG-n")`. Write the call and checks exactly as shown, also when a parameter does not exist yet.

**Race simulations.** None.

## `TransferOrderService.create_transfer_order`

### TOS-C-01 — a new order is committed and returned re-read, with its creator approver and event
- **Rules:** `create_transfer_order` R1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no transfer orders.

**When**
- with NUMP: `result = svc.create_transfer_order(db, to_in=CREATE(), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `loaded(result)`.
2. returns: `isinstance(result, TransferOrder)`, `result.created_at is not None`, `result.transfer_number == TNUM`.
3. committed: the order `result.id` exists with `workspace_id == W1.id`, `created_by == U1.id`, `description == "Monthly move"`.
4. committed: `transfer_order_approvers` of `result.id`: exactly 1 row, `user_id == U1.id`, `approved is False`.
5. committed: `types(result) == ["created"]`.

### TOS-C-02 — an order ready at once (route and a line) sends no notification
- **Rules:** `create_transfer_order` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no transfer orders.

**When**
- with NUMP: `result = svc.create_transfer_order(db, to_in=CREATE(items=[ITEM(I1, "5")]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: `transfer_order_items` of `result.id`: exactly 1 row.
3. committed: `notes(result) == []`.

### TOS-C-03 — the same route is refused 400; the session is rolled back
- **Rules:** `create_transfer_order` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no transfer orders.
2. X (after the commit point).

**When**
- with NUMP: `svc.create_transfer_order(db, to_in=CREATE(destination_location_id=F1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Source and destination cannot be the same"`.
4. session: `not db.new`.
5. session: usable.
6. nothing written: nothing written.
7. committed: x_gone.

### TOS-C-04 — a duplicate item is refused 409; no order, approver, line or event is saved
- **Rules:** `create_transfer_order` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no transfer orders.
2. X (after the commit point).

**When**
- with NUMP: `svc.create_transfer_order(db, to_in=CREATE(items=[ITEM(I1, "5"), ITEM(I1, "2")]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Motor appears more than once on this order"`.
4. session: `not db.new`.
5. count: `transfer_orders` rows with `transfer_number == TNUM`: exactly 0.
6. nothing written: nothing written.
7. committed: x_gone.

### TOS-C-05 — a database error (unknown creator) passes unchanged and nothing is saved
- **Rules:** `create_transfer_order` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no transfer orders.
2. X (after the commit point).

**When**
- with NUMP: `svc.create_transfer_order(db, to_in=CREATE(), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. session: usable.
4. nothing written: nothing written.
5. committed: x_gone.

### TOS-C-06 — a failing commit is rolled back and re-raised
- **Rules:** `create_transfer_order` R4; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no transfer orders.

**When**
- with NUMP, inside **failing commit**: `svc.create_transfer_order(db, to_in=CREATE(items=[ITEM(I1, "5")]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `transfer_orders` rows with `transfer_number == TNUM`: exactly 0.
4. nothing written: nothing written.

### TOS-C-07 — a failing re-read after the commit leaves the order saved
- **Rules:** `create_transfer_order` R4; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no transfer orders.

**When**
- with NUMP, inside **failing refresh**: `svc.create_transfer_order(db, to_in=CREATE(), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: `transfer_orders` rows with `transfer_number == TNUM`: exactly 1, `created_by == U1.id`.

## `TransferOrderService.update_transfer_order`

### TOS-U-01 — an order of W0 (lower id) gets the 404, nothing is written, the session is rolled back
- **Rules:** `update_transfer_order` R1, R1a; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = order O0.
2. O = order O.
3. X (after the commit point).

**When**
- `svc.update_transfer_order(db, to_id=Z.id, to_in=UPD(description="New"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Transfer order with ID {Z.id} not found"`.
4. unchanged: unchanged(Z).
5. nothing written: nothing written.
6. committed: x_gone.

### TOS-U-02 — an order of W2 (higher id) gets the 404, nothing is written, the session is rolled back
- **Rules:** `update_transfer_order` R1, R1a; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order O.
2. Z = order O9.
3. X (after the commit point).

**When**
- `svc.update_transfer_order(db, to_id=Z.id, to_in=UPD(description="New"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Transfer order with ID {Z.id} not found"`.
4. unchanged: unchanged(Z).
5. nothing written: nothing written.
6. committed: x_gone.

### TOS-U-19 — an id that does not exist gets the 404, nothing is written, the session is rolled back
- **Rules:** `update_transfer_order` R1, R1a; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.
2. X (after the commit point).

**When**
- `svc.update_transfer_order(db, to_id=MISSING, to_in=UPD(description="New"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Transfer order with ID {MISSING} not found"`.
4. session: `X not in db`.
5. unchanged: unchanged(O).
6. nothing written: nothing written.
7. committed: x_gone.

### TOS-U-03 — an edit is committed and the order returned re-read
- **Rules:** `update_transfer_order` R3; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O.
2. apr(O, U1, 1).

**When**
- `result = svc.update_transfer_order(db, to_id=O.id, to_in=UPD(description="New text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `loaded(result)`.
2. returns: `result.id == O.id`, `result.description == "New text"`.
3. committed: re-read O: `description == "New text"`.
4. committed: `types(O) == ["updated"]`.
5. committed: `notes(O) == []`.

### TOS-U-04 — not ready → ready: every pending active approver gets "approval pending", the actor included
- **Rules:** `update_transfer_order` R2, R4a [companion of BUG-3142]
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order O, but looped.
2. line(O, 1).
3. apr(O, U1, 1). 4. apr(O, U2, 2). 5. apr(O, U4, 3).

**When**
- `result = svc.update_transfer_order(db, to_id=O.id, to_in=UPD(destination_location_id=FB.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.destination_location_id == FB.id`.
2. committed: `notes(O) == [("approval_pending", U1.id, U2.id, "order", O.id, PEND(0, 3)), ("approval_pending", U2.id, U2.id, "order", O.id, PEND(0, 3))]`.
3. committed: re-read O: `destination_location_id == FB.id`.

### TOS-U-05 — not ready → ready by an actor who is not an approver: both pending approvers are told
- **Rules:** `update_transfer_order` R4a [companion of BUG-3142]
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order O, but looped, `required_approvals 2`.
2. line(O, 1).
3. apr(O, U1, 1). 4. apr(O, U2, 2).

**When**
- `svc.update_transfer_order(db, to_id=O.id, to_in=UPD(destination_location_id=FB.id), workspace_id=W1.id, user_id=U3.id)`.

**Then**
1. committed: re-read O: `destination_location_id == FB.id`.
2. committed: `notes(O) == [("approval_pending", U1.id, U3.id, "order", O.id, PEND(0, 2)), ("approval_pending", U2.id, U3.id, "order", O.id, PEND(0, 2))]`.

### TOS-U-06 — ready → ready (a description edit) sends nothing
- **Rules:** `update_transfer_order` R4c
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order O.
2. line(O, 1).
3. apr(O, U1, 1). 4. apr(O, U2, 2).

**When**
- `svc.update_transfer_order(db, to_id=O.id, to_in=UPD(description="Again"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. committed: re-read O: `description == "Again"`.
2. committed: `notes(O) == []`.

### TOS-U-07 — not ready → not ready (no line) sends nothing
- **Rules:** `update_transfer_order` R4c
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order O, but looped.
2. apr(O, U1, 1).

**When**
- `svc.update_transfer_order(db, to_id=O.id, to_in=UPD(destination_location_id=FB.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. committed: re-read O: `destination_location_id == FB.id`.
2. committed: `notes(O) == []`.

### TOS-U-08 — no approvals required (`required_approvals` 0): becoming ready sends nothing
- **Rules:** `update_transfer_order` R4c
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, but looped, `required_approvals 0`.
2. line(O, 1).
3. apr(O, U1, 1).

**When**
- `svc.update_transfer_order(db, to_id=O.id, to_in=UPD(destination_location_id=FB.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. committed: re-read O: `destination_location_id == FB.id`.
2. committed: `notes(O) == []`.

### TOS-U-09 — a `required_approvals` change on a ready order with an approval sends nothing
- **Rules:** `update_transfer_order` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order O, but `required_approvals 2`.
2. line(O, 1).
3. apr(O, U1, 1), but approved. 4. apr(O, U2, 2).

**When**
- `result = svc.update_transfer_order(db, to_id=O.id, to_in=UPD(required_approvals=1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.required_approvals == 1`.
2. committed: re-read O: `required_approvals == 1`.
3. committed: `notes(O) == []`.

### TOS-U-10 — a guard refusal (approval given, description edit) rolls back, nothing saved
- **Rules:** `update_transfer_order` R6; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.
2. line(O, 1).
3. apr(O, U1, 1), but approved.
4. X (after the commit point).

**When**
- `svc.update_transfer_order(db, to_id=O.id, to_in=UPD(description="New"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Withdraw all approvals before editing order details"`.
4. session: usable.
5. unchanged: unchanged(O).
6. nothing written: nothing written.
7. committed: x_gone.

### TOS-U-15 — a completed order is refused 400 and rolled back
- **Rules:** `update_transfer_order` R6; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, but completed.
2. X (after the commit point).

**When**
- `svc.update_transfer_order(db, to_id=O.id, to_in=UPD(description="New"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Transfer order is complete and cannot be edited"`.
4. unchanged: unchanged(O).
5. nothing written: nothing written.
6. committed: x_gone.

### TOS-U-16 — a failing commit rolls back the edit, its event and its notifications
- **Rules:** `update_transfer_order` R6, R7; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, but looped.
2. line(O, 1).
3. apr(O, U1, 1).

**When**
- inside **failing commit**: `svc.update_transfer_order(db, to_id=O.id, to_in=UPD(destination_location_id=FB.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(O).
4. count: `notes(O) == []`.
5. nothing written: nothing written.

### TOS-U-17 — a failing re-read after the commit leaves the edit saved
- **Rules:** `update_transfer_order` R7; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.

**When**
- inside **failing refresh**: `svc.update_transfer_order(db, to_id=O.id, to_in=UPD(description="Kept"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: re-read O: `description == "Kept"`.

### TOS-U-18 — a raise while notifying rolls back the edit, its event, the helper's writes and other pending changes
- **Rules:** `update_transfer_order` R6; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, but looped.
2. line(O, 1).
3. apr(O, U1, 1).
4. X (after the commit point).

**When**
- inside NU: `with pytest.raises(RuntimeError) as exc:` around `svc.update_transfer_order(db, to_id=O.id, to_in=UPD(destination_location_id=FB.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `str(exc.value) == "notify boom"`.
2. mock called: `nh.call_count == 1`.
3. session: usable.
4. unchanged: unchanged(O).
5. count: `types(O) == []`.
6. count: `notes(O) == []`.
7. nothing written: nothing written.
8. committed: x_gone.

### TOS-U-11 — ready → not ready: the creator gets "confirm sections" (retire when BUG-2899 is fixed)
- **Rules:** `update_transfer_order` R4b
- **Kind:** side-effect
- **Expect:** pass
- **Retire when:** BUG-2899 is fixed. Reason (R4b, spec G4): this source = destination edit is then refused 400 (U-12); once BUG-2894 and BUG-823 are fixed as well, no update can make a ready order not ready, so R4b is unreachable through this method. R4b stays a pass-through pointer to `handle_order_update_notifications` R2 (covered by `approval_notification_service.cases.md`); no replacement card on the id-`0` / empty-type paths.

**Given**
1. O = order O.
2. line(O, 1).
3. apr(O, U2, 1).

**When**
- `svc.update_transfer_order(db, to_id=O.id, to_in=UPD(destination_location_id=F1.id), workspace_id=W1.id, user_id=U3.id)`.

**Then**
1. committed: `notes(O) == [("section_confirm", U1.id, U3.id, "section", O.id, GAP_ITEM)]`.

### TOS-U-12 — pass-through BUG-2899: an edit to source = destination is refused, nothing sent
- **Rules:** `update_transfer_order` R3, R6 [BUG-2899]
- **Kind:** bug
- **Expect:** xfail BUG-2899
- **Fails today on:** Then 1 (no error is raised: the edit is saved and `section_confirm` is sent)

**Given**
1. O = order O.
2. line(O, 1).
3. apr(O, U2, 1).

**When**
- `svc.update_transfer_order(db, to_id=O.id, to_in=UPD(destination_location_id=F1.id), workspace_id=W1.id, user_id=U3.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Source and destination cannot be the same"`.
4. unchanged: unchanged(O).
5. count: `notes(O) == []`.

### TOS-U-13 — BUG-3142: the order row is locked before the readiness snapshot
- **Rules:** `update_transfer_order` R2a [BUG-3142]
- **Kind:** bug
- **Expect:** xfail BUG-3142
- **Fails today on:** Then 2 (no `FOR UPDATE OF transfer_orders` before the first `transfer_order_items` read)

**Given**
1. O = order O (routed: storage F1 → storage FB).
2. line(O, 1).
3. apr(O, U1, 1).
4. after the commit point: `O_ID = O.id`, then `db.expunge_all()`; a statement recorder.

**When**
- `result = svc.update_transfer_order(db, to_id=O_ID, to_in=UPD(description="New text"), workspace_id=W1.id, user_id=U1.id)` (ready → ready, so the readiness snapshot reads `transfer_order_items`).

**Then**
1. returns: `result.id == O_ID`.
2. statement: lock first.
3. statement: some recorded SELECT names `transfer_order_items` (the snapshot read the lines, so a lock placed after the snapshot fails Then 2).

### TOS-U-14 — pass-through BUG-2903: a `required_approvals` change commits the approval wipe
- **Rules:** `update_transfer_order` R3, R5 [BUG-2903]
- **Kind:** bug
- **Expect:** xfail BUG-2903
- **Fails today on:** Then 2 (U1's approval is kept)

**Given**
1. O = order O, but `required_approvals 2`.
2. line(O, 1).
3. A1 = apr(O, U1, 1), but approved. 4. apr(O, U2, 2).

**When**
- `result = svc.update_transfer_order(db, to_id=O.id, to_in=UPD(required_approvals=1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.required_approvals == 1`.
2. committed: re-read A1: `approved is False`, `approved_at is None`.
3. committed: `types(O) == ["updated", "approvals_reset"]`.
4. committed: `notes(O) == []`.

## `TransferOrderService.get_transfer_order`

### TOS-G-01 — returns the workspace's order with its status; the read neither commits nor rolls back
- **Rules:** `get_transfer_order` R1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z = order O0.
2. O = order O.
3. X (after the commit point).

**When**
- spies: `result = svc.get_transfer_order(db, to_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, TransferOrder)`, `result.id == O.id`.
2. returns: `result.current_status.name == "Open"`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.

### TOS-G-02 — another workspace's order: the 404 passes unchanged, no rollback
- **Rules:** `get_transfer_order` R1; TC6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order O.
2. Z = order O9.
3. X (after the commit point).

**When**
- spies: `svc.get_transfer_order(db, to_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Transfer order with ID {Z.id} not found"`.
4. mock called: `cm.call_count == 0`.
5. mock called: `rb.call_count == 0`.
6. session: `X in db`.

### TOS-G-03 — an order of W0 (lower id): the 404 passes unchanged, no rollback
- **Rules:** `get_transfer_order` R1; TC6; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = order O0.
2. O = order O.
3. X (after the commit point).

**When**
- spies: `svc.get_transfer_order(db, to_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Transfer order with ID {Z.id} not found"`.
4. mock called: `cm.call_count == 0`.
5. mock called: `rb.call_count == 0`.
6. session: `X in db`.

## `TransferOrderService.list_transfer_orders`

### TOS-LT-01 — default limit is 100: 101 orders give 100 items and `has_more`
- **Rules:** `list_transfer_orders` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 orders by `add_all` and one flush: k = 1 … 101, HO(k, k).

**When**
- `result = svc.list_transfer_orders(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, TransferOrderListResponse)`.
2. returns: `len(result.items) == 100`, `result.total == 101`.
3. returns: `result.skip == 0`, `result.limit == 100`, `result.has_more is True`.

### TOS-LT-02 — skip, limit and a filter are passed on
- **Rules:** `list_transfer_orders` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = HO(1, 1).
2. B = HO(2, 2).
3. C = HO(3, 3, completed_at=DONE, completed_by=U1.id).

**When**
- `result = svc.list_transfer_orders(db, workspace_id=W1.id, skip=1, limit=1, exclude_complete=True)`.

**Then**
1. returns: `result.total == 2`.
2. returns: `[i.id for i in result.items] == [A.id]`.
3. returns: `result.skip == 1`, `result.limit == 1`, `result.has_more is False`.

### TOS-LT-03 — an unknown filter keyword raises `TypeError`
- **Rules:** `list_transfer_orders` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = HO(1, 1).

**When**
- `svc.list_transfer_orders(db, workspace_id=W1.id, colour="red")`.

**Then**
1. raises: `TypeError`.

## `TransferOrderService._hub_filter_kwargs`

### TOS-HF-01 — every value is passed as given, exactly eight keys
- **Rules:** `_hub_filter_kwargs` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows needed.

**When**
- `result = svc._hub_filter_kwargs(date_from=TS(1), date_to=TS(2), status_ids=[7, 8], factory_id=5, source_location_type="storage", destination_location_type="machine", search="TR-", exclude_complete=True)`.

**Then**
1. returns: `result == {"date_from": TS(1), "date_to": TS(2), "status_ids": [7, 8], "factory_id": 5, "source_location_type": "storage", "destination_location_type": "machine", "search": "TR-", "exclude_complete": True}`.

### TOS-HF-02 — no arguments: all None and `exclude_complete` False
- **Rules:** `_hub_filter_kwargs` R1, R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows needed.

**When**
- `result = svc._hub_filter_kwargs()`.

**Then**
1. returns: `result == {"date_from": None, "date_to": None, "status_ids": None, "factory_id": None, "source_location_type": None, "destination_location_type": None, "search": None, "exclude_complete": False}`.

### TOS-HF-03 — `"all"` and `""` mean no location filter
- **Rules:** `_hub_filter_kwargs` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows needed.

**When**
- `result = svc._hub_filter_kwargs(source_location_type="all", destination_location_type="")`.

**Then**
1. returns: `result["source_location_type"] is None`.
2. returns: `result["destination_location_type"] is None`.

### TOS-HF-04 — other spellings are kept exactly: `"All"`, `" all"`, `"al"`, `"ALL"`
- **Rules:** `_hub_filter_kwargs` R2 (D3)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows needed.

**When**
- `results = [svc._hub_filter_kwargs(source_location_type=s, destination_location_type=s) for s in ["All", " all", "al", "ALL"]]`.

**Then**
1. returns: `[r["source_location_type"] for r in results] == ["All", " all", "al", "ALL"]`.
2. returns: `[r["destination_location_type"] for r in results] == ["All", " all", "al", "ALL"]`.

### TOS-HF-05 — `"all"` as the destination and `""` as the source also mean no location filter
- **Rules:** `_hub_filter_kwargs` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows needed.

**When**
- `result = svc._hub_filter_kwargs(source_location_type="", destination_location_type="all")`.

**Then**
1. returns: `result["source_location_type"] is None`.
2. returns: `result["destination_location_type"] is None`.

## `TransferOrderService.list_transfer_orders_page`

### TOS-LP-01 — default: completed orders included, other workspaces left out, limit 50; neither commit nor rollback
- **Rules:** `list_transfer_orders_page` R1, R2, R4; `_hub_filter_kwargs` R3 (D2)
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z0 = order O0.
2. A = HO(1, 1).
3. C = HO(2, 2, completed_at=DONE, completed_by=U1.id).
4. Z2 = order O9.
5. X (after the commit point).

**When**
- spies: `result = svc.list_transfer_orders_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, TransferOrderListResponse)`.
2. returns: `[i.id for i in result.items] == [C.id, A.id]`.
3. returns: `result.total == 2`, `result.skip == 0`, `result.limit == 50`, `result.has_more is False`.
4. mock called: `cm.call_count == 0`.
5. mock called: `rb.call_count == 0`.
6. session: `X in db`.

### TOS-LP-02 — 51 orders: the default page holds 50 and `has_more` is true
- **Rules:** `list_transfer_orders_page` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 51 orders by `add_all` and one flush: k = 1 … 51, HO(k, k).

**When**
- `result = svc.list_transfer_orders_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result.items) == 50`, `result.total == 51`, `result.has_more is True`.

### TOS-LP-03 — the same filter reaches count and list: `exclude_complete=True`
- **Rules:** `list_transfer_orders_page` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = HO(1, 1).
2. C = HO(2, 2, completed_at=DONE, completed_by=U1.id).
3. B = HO(3, 3).

**When**
- `result = svc.list_transfer_orders_page(db, workspace_id=W1.id, exclude_complete=True)`.

**Then**
1. returns: `[i.id for i in result.items] == [B.id, A.id]`.
2. returns: `result.total == 2`.

### TOS-LP-04 — `"all"` source type lists every type; `"All"` finds nothing
- **Rules:** `list_transfer_orders_page` R1; `_hub_filter_kwargs` R2 (D3)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = HO(1, 1).
2. B = HO(2, 2, source_location_type="machine", source_location_id=M1.id).

**When**
- `results = [svc.list_transfer_orders_page(db, workspace_id=W1.id, source_location_type=s) for s in ["all", "All", "machine"]]`.

**Then**
1. returns: `[r.total for r in results] == [2, 0, 1]`.
2. returns: `[len(r.items) for r in results] == [2, 0, 1]`.

### TOS-LP-05 — `has_more` true while `skip + len(items) < total`
- **Rules:** `list_transfer_orders_page` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = HO(1, 1). 2. B = HO(2, 2). 3. C = HO(3, 3).

**When**
- `results = [svc.list_transfer_orders_page(db, workspace_id=W1.id, skip=s, limit=l) for s, l in [(0, 2), (1, 1)]]`.

**Then**
1. returns: `[[i.id for i in r.items] for r in results] == [[C.id, B.id], [B.id]]`.
2. returns: `[r.has_more for r in results] == [True, True]`.

### TOS-LP-06 — `has_more` false when `skip + len(items) == total`
- **Rules:** `list_transfer_orders_page` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = HO(1, 1). 2. B = HO(2, 2). 3. C = HO(3, 3).

**When**
- `results = [svc.list_transfer_orders_page(db, workspace_id=W1.id, skip=s, limit=l) for s, l in [(1, 2), (2, 1)]]`.

**Then**
1. returns: `[[i.id for i in r.items] for r in results] == [[B.id, A.id], [A.id]]`.
2. returns: `[r.has_more for r in results] == [False, False]`.
3. returns: `[r.total for r in results] == [3, 3]`.

### TOS-LP-07 — skip past the end: no items, `has_more` false
- **Rules:** `list_transfer_orders_page` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = HO(1, 1). 2. B = HO(2, 2).

**When**
- `result = svc.list_transfer_orders_page(db, workspace_id=W1.id, skip=5, limit=2)`.

**Then**
1. returns: `result.items == []`, `result.total == 2`, `result.skip == 5`, `result.has_more is False`.

## `TransferOrderService.get_transfer_order_hub_stats`

### TOS-HS-01 — stats of a workspace: counts, machine count, recent, highlights; neither commit nor rollback
- **Rules:** `get_transfer_order_hub_stats` R2, R3, R4, R5; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z0 = order O0.
2. A = HO(1, 1, destination_location_type="machine", destination_location_id=M1.id).
3. line(A, 1).
4. B = HO(2, 2, source_location_id=0).
5. C = HO(3, 3, completed_at=DONE, completed_by=U1.id).
6. Z2 = order O9.
7. X (after the commit point).

**When**
- spies: `result = svc.get_transfer_order_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, TransferOrderHubStatsResponse)`.
2. returns: `(result.total_count, result.open_count, result.completed_count) == (3, 2, 1)`.
3. returns: `result.machine_involved_count == 1`.
4. returns: `{r.id for r in result.recent_orders} == {A.id, B.id, C.id}`.
5. returns: `{r.status_name for r in result.recent_orders} == {"Open"}`.
6. returns: `(result.pending_planned_count, result.awaiting_setup_count) == (1, 1)`.
7. returns: `[(h.id, h.status_name) for h in result.pending_planned] == [(A.id, "Planned")]`.
8. returns: `[(h.id, h.status_name) for h in result.awaiting_setup] == [(B.id, "Draft")]`.
9. returns: `[h.id for h in result.oldest_drafts] == [B.id]`.
10. mock called: `cm.call_count == 0`.
11. mock called: `rb.call_count == 0`.
12. session: `X in db`.

### TOS-HS-02 — a filter that differs from the DAO's defaults reaches every hub read, the machine count included
- **Rules:** `get_transfer_order_hub_stats` R1, R2; `_hub_filter_kwargs` R3 (D2)
- **Kind:** happy
- **Expect:** pass
- **Note:** `exclude_complete=False` is the opposite of the DAO's own default (`True`, spec D2), so a read that drops the filters hides C; the destination filter hides B. A machine count without the filters gives 1, not 2 (verifier finding 4).

**Given**
1. A = HO(1, 1, destination_location_type="machine", destination_location_id=M1.id).
2. line(A, 1).
3. B = HO(2, 2, source_location_id=0).
4. C = HO(3, 3, destination_location_type="machine", destination_location_id=M1.id, completed_at=DONE, completed_by=U1.id).

**When**
- `result = svc.get_transfer_order_hub_stats(db, workspace_id=W1.id, destination_location_type="machine", exclude_complete=False)`.

**Then**
1. returns: `(result.total_count, result.open_count, result.completed_count) == (2, 1, 1)`.
2. returns: `result.machine_involved_count == 2`.
3. returns: `{r.id for r in result.recent_orders} == {A.id, C.id}`.
4. returns: `(result.pending_planned_count, result.awaiting_setup_count) == (1, 0)`.
5. returns: `result.awaiting_setup == []`, `result.oldest_drafts == []`.

### TOS-HS-03 — at most 10 recent orders
- **Rules:** `get_transfer_order_hub_stats` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 11 orders by `add_all` and one flush: k = 1 … 11, HO(k, k).
2. `all_ids` = their ids.

**When**
- `result = svc.get_transfer_order_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result.recent_orders) == 10`.
2. returns: `len({r.id for r in result.recent_orders}) == 10`, `{r.id for r in result.recent_orders} <= all_ids`.
3. returns: `result.total_count == 11`.

### TOS-HS-04 — an empty workspace: zeros and empty lists
- **Rules:** `get_transfer_order_hub_stats` R2, R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z2 = order O9 (W1 has no orders).

**When**
- `result = svc.get_transfer_order_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `(result.total_count, result.open_count, result.completed_count, result.machine_involved_count) == (0, 0, 0, 0)`.
2. returns: `(result.pending_planned_count, result.awaiting_setup_count) == (0, 0)`.
3. returns: `result.recent_orders == []`, `result.pending_planned == []`, `result.awaiting_setup == []`, `result.oldest_drafts == []`.

### TOS-HS-05 — `"All"` as a location type matches nothing in the stats
- **Rules:** `get_transfer_order_hub_stats` R1; `_hub_filter_kwargs` R2 (D3)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = HO(1, 1).

**When**
- `results = [svc.get_transfer_order_hub_stats(db, workspace_id=W1.id, source_location_type=s) for s in ["all", "All"]]`.

**Then**
1. returns: `[r.total_count for r in results] == [1, 0]`.

## `TransferOrderService.delete_transfer_order`

### TOS-D-01 — a delete is committed: order, lines, approvers and events are gone
- **Rules:** `delete_transfer_order` R1, R4; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O. 2. line(O, 1). 3. apr(O, U1, 1). 4. ev(O, "created", 1).
5. `O_ID = O.id`.

**When**
- `result = DEL(O_ID)`.

**Then**
1. returns: `result is None`.
2. committed: `db.get(TransferOrder, O_ID) is None`.
3. committed: `transfer_order_items` rows with `transfer_order_id == O_ID`: 0.
4. committed: `transfer_order_approvers` rows with `transfer_order_id == O_ID`: 0.
5. committed: `transfer_order_events` rows with `transfer_order_id == O_ID`: 0.
6. committed: `notifications` rows (all workspaces): as many as at the commit point.

### TOS-D-02 — a completed order is refused 400 and the session rolled back
- **Rules:** `delete_transfer_order` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, but completed. 2. line(O, 1).
3. X (after the commit point).

**When**
- `DEL(O.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot delete a completed transfer order"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(O).
6. nothing written: nothing written.
7. committed: x_gone.

### TOS-D-03 — another workspace's order gets the 404, rolled back
- **Rules:** `delete_transfer_order` R2; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order O.
2. Z = order O9.
3. X (after the commit point).

**When**
- `DEL(Z.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Transfer order with ID {Z.id} not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(Z).
6. nothing written: nothing written.
7. committed: x_gone.

### TOS-D-04 — a failing commit leaves the order in place
- **Rules:** `delete_transfer_order` R4; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. line(O, 1).

**When**
- inside **failing commit**: `DEL(O.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(O).
4. nothing written: nothing written.

### TOS-D-05 — BUG-1194: the deleter is passed on and the audit row is committed
- **Rules:** `delete_transfer_order` R3 [BUG-1194]
- **Kind:** bug
- **Expect:** xfail BUG-1194
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. O = order O.
2. `O_ID = O.id`, `NUM = O.transfer_number`.

**When**
- `result = svc.delete_transfer_order(db, to_id=O_ID, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. committed: `db.get(TransferOrder, O_ID) is None`.
3. committed: `workspace_audit_logs` rows with `resource_type == "transfer_order"` and `resource_id == O_ID`: exactly 1, `workspace_id == W1.id`, `user_id == U2.id`, `action == "transfer_order_deleted"`.
4. committed: that row's `metadata["number"] == NUM`, `metadata["created_by"] == U1.id`.

### TOS-D-06 — BUG-1194: `user_id` is a required parameter
- **Rules:** `delete_transfer_order` R3 [BUG-1194]
- **Kind:** bug
- **Expect:** xfail BUG-1194
- **Fails today on:** Then 1 (no `user_id` in the signature)

**Given**
1. No rows needed.

**When**
- `params = inspect.signature(svc.delete_transfer_order).parameters`.

**Then**
1. returns: `"user_id" in params`.
2. returns: `params["user_id"].default is inspect.Parameter.empty`.

## `TransferOrderService.mark_order_complete`

### TOS-MC-01 — a completion is committed and the order returned re-read; no notification
- **Rules:** `mark_order_complete` R1, R4; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O. 2. L1 = line(O, 1). 3. apr(O, U1, 1), but approved.

**When**
- with `pm` = POST(1): `result = svc.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `loaded(result)`.
2. returns: `result.id == O.id`, `result.completed_at is not None`.
3. mock called: `pm.call_count == 1`.
4. committed: re-read O: `completed_at == NOW`, `completed_by == U2.id`.
5. committed: re-read L1: `transferred_at == NOW`.
6. committed: `types(O) == ["transfer_recorded", "inventory_posted", "order_completed"]`.
7. committed: `notes(O) == []`.

### TOS-MC-02 — an already completed order is returned unchanged and the call still commits
- **Rules:** `mark_order_complete` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O, but completed. 2. line(O, 1).

**When**
- with `pm` = POST(1), spies: `result = svc.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. mock called: `cm.call_count == 1`.
3. mock called: `pm.call_count == 0`.
4. unchanged: unchanged(O).
5. nothing written: nothing written.

### TOS-MC-03 — unmet approvals: 400, rolled back
- **Rules:** `mark_order_complete` R3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. L1 = line(O, 1). 3. apr(O, U1, 1).
4. X (after the commit point).

**When**
- with `pm` = POST(1): `svc.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Required approvals are not met"`.
4. unchanged: unchanged(O).
5. unchanged: unchanged(L1).
6. nothing written: nothing written.
7. committed: x_gone.

### TOS-MC-04 — a stock-posting error rolls back every write of the call, the posting's own included
- **Rules:** `mark_order_complete` R3; TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order O. 2. L1 = line(O, 1). 3. apr(O, U1, 1), but approved.
4. X (after the commit point).

**When**
- with `pm` = PROBE_ERR: `svc.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value is ERR`.
3. session: usable.
4. re-read O: `completed_at is None`, `completed_by is None`.
5. re-read L1: `transferred_at is None`.
6. count: `transfer_order_events` rows with `event_type == "probe"`: exactly 0.
7. nothing written: nothing written.
8. committed: x_gone.

### TOS-MC-05 — no line: 400, rolled back
- **Rules:** `mark_order_complete` R3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, but `required_approvals 0`.
2. X (after the commit point).

**When**
- with `pm` = POST(0): `svc.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Add at least one item before completing"`.
4. unchanged: unchanged(O).
5. nothing written: nothing written.
6. committed: x_gone.

### TOS-MC-06 — another workspace's order: 404, rolled back
- **Rules:** `mark_order_complete` R3; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = order O0.
2. X (after the commit point).

**When**
- with `pm` = POST(1): `svc.mark_order_complete(db, to_id=Z.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Transfer order with ID {Z.id} not found"`.
4. unchanged: unchanged(Z).
5. committed: x_gone.

### TOS-MC-07 — a failing commit rolls back the completion and the posting's writes
- **Rules:** `mark_order_complete` R5; TC4
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order O. 2. L1 = line(O, 1). 3. apr(O, U1, 1), but approved.

**When**
- with `pm` = PROBE_OK, inside **failing commit**: `svc.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read O: `completed_at is None`.
4. re-read L1: `transferred_at is None`.
5. count: `transfer_order_events` rows with `event_type == "probe"`: exactly 0.
6. nothing written: nothing written.

### TOS-MC-08 — a failing re-read after the commit leaves the completion saved
- **Rules:** `mark_order_complete` R5; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. line(O, 1). 3. apr(O, U1, 1), but approved.

**When**
- with `pm` = POST(1), inside **failing refresh**: `svc.mark_order_complete(db, to_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: re-read O: `completed_at == NOW`.

## `TransferOrderService.add_item`

### TOS-AI-01 — a line is committed and returned re-read
- **Rules:** `add_item` R3, R6; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O, but looped.
2. apr(O, U1, 1).

**When**
- `result = svc.add_item(db, to_id=O.id, item_in=ITEM(I1, "5"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `loaded(result)`.
2. returns: `isinstance(result, TransferOrderItem)`, `result.line_number == 1`, `result.item_id == I1.id`.
3. committed: the line `result.id` exists with `transfer_order_id == O.id`, `quantity == Decimal("5.00")`.
4. committed: `types(O) == ["item_added"]`.
5. committed: `notes(O) == []`.

### TOS-AI-02 — the first line on a routed order: the pending creator gets "approval pending"
- **Rules:** `add_item` R2, R4 [companion of BUG-3142]
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order O.
2. apr(O, U1, 1).

**When**
- `result = svc.add_item(db, to_id=O.id, item_in=ITEM(I1, "5"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.line_number == 1`.
2. committed: `notes(O) == [("approval_pending", U1.id, U1.id, "order", O.id, PEND(0, 1))]`.

### TOS-AI-03 — the first line: every active pending approver is told, an inactive one is not
- **Rules:** `add_item` R4 [companion of BUG-3142]
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order O, but `required_approvals 2`.
2. apr(O, U1, 1). 3. apr(O, U4, 2). 4. apr(O, U3, 3).

**When**
- `svc.add_item(db, to_id=O.id, item_in=ITEM(I1, "5"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. committed: `notes(O) == [("approval_pending", U1.id, U2.id, "order", O.id, PEND(0, 2)), ("approval_pending", U3.id, U2.id, "order", O.id, PEND(0, 2))]`.

### TOS-AI-04 — a second line (ready → ready) sends nothing
- **Rules:** `add_item` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order O. 2. line(O, 1). 3. apr(O, U1, 1).

**When**
- `result = svc.add_item(db, to_id=O.id, item_in=ITEM(I2, "3"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.line_number == 2`.
2. committed: `notes(O) == []`.

### TOS-AI-05 — a line on an order without a valid route sends nothing
- **Rules:** `add_item` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order O, but looped.
2. apr(O, U1, 1).

**When**
- `svc.add_item(db, to_id=O.id, item_in=ITEM(I1, "5"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. committed: `transfer_order_items` rows of O: exactly 1.
2. committed: `notes(O) == []`.

### TOS-AI-06 — another workspace's order (W0) gets the 404, the session is rolled back
- **Rules:** `add_item` R1; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = order O0.
2. O = order O.
3. X (after the commit point).

**When**
- `svc.add_item(db, to_id=Z.id, item_in=ITEM(I1, "5"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Transfer order with ID {Z.id} not found"`.
4. nothing written: nothing written.
5. committed: x_gone.

### TOS-AI-14 — an id that does not exist gets the 404, the session is rolled back
- **Rules:** `add_item` R1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O.
2. X (after the commit point).

**When**
- `svc.add_item(db, to_id=MISSING, item_in=ITEM(I1, "5"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Transfer order with ID {MISSING} not found"`.
4. session: `X not in db`.
5. nothing written: nothing written.
6. committed: x_gone.

### TOS-AI-07 — an approval given: 400, no line, no notification, other pending changes discarded
- **Rules:** `add_item` R5; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. apr(O, U1, 1), but approved.
3. X (after the commit point).

**When**
- `svc.add_item(db, to_id=O.id, item_in=ITEM(I1, "5"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Withdraw all approvals before editing transfer items"`.
4. session: usable.
5. nothing written: nothing written.
6. committed: x_gone.

### TOS-AI-08 — a completed order: 400, rolled back
- **Rules:** `add_item` R5; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, but completed.
2. X (after the commit point).

**When**
- `svc.add_item(db, to_id=O.id, item_in=ITEM(I1, "5"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Transfer order is complete"`.
4. nothing written: nothing written.
5. committed: x_gone.

### TOS-AI-09 — the item already on the order: 409, rolled back
- **Rules:** `add_item` R5; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. line(O, 1). 3. apr(O, U1, 1).
4. X (after the commit point).

**When**
- `svc.add_item(db, to_id=O.id, item_in=ITEM(I1, "2"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Motor is already on this order"`.
4. nothing written: nothing written.
5. committed: x_gone.

### TOS-AI-10 — a failing commit rolls back the line, its event and its notification
- **Rules:** `add_item` R5, R6; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. apr(O, U1, 1).

**When**
- inside **failing commit**: `svc.add_item(db, to_id=O.id, item_in=ITEM(I1, "5"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `notes(O) == []`.
4. nothing written: nothing written.

### TOS-AI-12 — a failing re-read after the commit leaves the line saved
- **Rules:** `add_item` R6; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O, but looped.

**When**
- inside **failing refresh**: `svc.add_item(db, to_id=O.id, item_in=ITEM(I1, "5"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: `transfer_order_items` rows of O: exactly 1.

### TOS-AI-13 — a raise while notifying rolls back the line, its event, the helper's writes and other pending changes
- **Rules:** `add_item` R5; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. apr(O, U1, 1).
3. X (after the commit point).

**When**
- inside NU: `with pytest.raises(RuntimeError) as exc:` around `svc.add_item(db, to_id=O.id, item_in=ITEM(I1, "5"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `str(exc.value) == "notify boom"`.
2. mock called: `nh.call_count == 1`.
3. session: usable.
4. count: `transfer_order_items` rows of O: 0.
5. count: `types(O) == []`.
6. count: `notes(O) == []`.
7. nothing written: nothing written.
8. committed: x_gone.

### TOS-AI-11 — BUG-3142: the order row is locked before the readiness snapshot
- **Rules:** `add_item` R2a [BUG-3142]
- **Kind:** bug
- **Expect:** xfail BUG-3142
- **Fails today on:** Then 2 (no `FOR UPDATE OF transfer_orders` before the first `transfer_order_items` read)

**Given**
1. O = order O.
2. apr(O, U1, 1).
3. after the commit point: `O_ID = O.id`, then `db.expunge_all()`; a statement recorder.

**When**
- `result = svc.add_item(db, to_id=O_ID, item_in=ITEM(I1, "5"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.line_number == 1`.
2. statement: lock first.

## `TransferOrderService.update_item`

### TOS-UI-01 — a quantity change is committed and the line returned re-read; no notification
- **Rules:** `update_item` R1, R2; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O. 2. L1 = line(O, 1). 3. apr(O, U1, 1).

**When**
- `result = svc.update_item(db, item_id=L1.id, item_in=IU(quantity=Decimal("7")), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `loaded(result)`.
2. returns: `result.id == L1.id`, `result.quantity == Decimal("7.00")`.
3. committed: re-read L1: `quantity == Decimal("7.00")`.
4. committed: `notes(O) == []`.

### TOS-UI-02 — an approval given: 400 on a quantity change, rolled back
- **Rules:** `update_item` R3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. L1 = line(O, 1). 3. apr(O, U1, 1), but approved.
4. X (after the commit point).

**When**
- `svc.update_item(db, item_id=L1.id, item_in=IU(quantity=Decimal("7")), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Withdraw all approvals before editing transfer items"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(L1).
6. nothing written: nothing written.
7. committed: x_gone.

### TOS-UI-03 — another workspace's line: 404, rolled back
- **Rules:** `update_item` R3; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = order O9. 2. LZ = line(Z, 1).
3. X (after the commit point).

**When**
- `svc.update_item(db, item_id=LZ.id, item_in=IU(quantity=Decimal("7")), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Transfer order item not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(LZ).
6. committed: x_gone.

### TOS-UI-04 — a failing commit leaves the line unchanged
- **Rules:** `update_item` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. L1 = line(O, 1).

**When**
- inside **failing commit**: `svc.update_item(db, item_id=L1.id, item_in=IU(quantity=Decimal("7")), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(L1).

### TOS-UI-05 — a failing re-read after the commit leaves the change saved
- **Rules:** `update_item` R3; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. L1 = line(O, 1).

**When**
- inside **failing refresh**: `svc.update_item(db, item_id=L1.id, item_in=IU(quantity=Decimal("7")), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: re-read L1: `quantity == Decimal("7.00")`.

## `TransferOrderService.remove_item`

### TOS-RI-01 — the last line is removed and committed; no notification although the order stops being ready
- **Rules:** `remove_item` R1, R2; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O. 2. L1 = line(O, 1). 3. apr(O, U2, 1).
4. `L1_ID = L1.id`.

**When**
- `result = svc.remove_item(db, item_id=L1_ID, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == L1_ID`.
2. committed: `db.get(TransferOrderItem, L1_ID) is None`.
3. committed: `types(O) == ["item_removed"]`.
4. committed: `notes(O) == []`.

### TOS-RI-02 — the removed line is returned without a re-read
- **Rules:** `remove_item` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order O. 2. L1 = line(O, 1).
3. `L1_ID = L1.id`.

**When**
- with `patch.object(db, "refresh", wraps=db.refresh) as rf`: `result = svc.remove_item(db, item_id=L1_ID, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. mock called: `rf.call_count == 0`.
2. returns: `isinstance(result, TransferOrderItem)`, `result.id == L1_ID`.

### TOS-RI-03 — an approval given: 400, the line stays, rolled back
- **Rules:** `remove_item` R4; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. L1 = line(O, 1). 3. apr(O, U1, 1), but approved.
4. X (after the commit point).

**When**
- `svc.remove_item(db, item_id=L1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Withdraw all approvals before editing transfer items"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(L1).
6. nothing written: nothing written.
7. committed: x_gone.

### TOS-RI-04 — an unknown line: 404, rolled back
- **Rules:** `remove_item` R4; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. line(O, 1).
3. X (after the commit point).

**When**
- `svc.remove_item(db, item_id=MISSING, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Transfer order item not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. nothing written: nothing written.
6. committed: x_gone.

### TOS-RI-05 — a failing commit keeps the line
- **Rules:** `remove_item` R4; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. L1 = line(O, 1).

**When**
- inside **failing commit**: `svc.remove_item(db, item_id=L1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(L1).
4. nothing written: nothing written.

## Reads: `get_items`, `list_events`, `list_approvers`, `approval_summary_for`

### TOS-GI-01 — `get_items` returns the order's lines by number; neither commit nor rollback
- **Rules:** `get_items` R1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O. 2. L2 = line(O, 2). 3. L1 = line(O, 1), but `item_id I2.id`.
4. X (after the commit point).

**When**
- spies: `result = svc.get_items(db, to_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [L1.id, L2.id]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### TOS-LE-01 — `list_events` returns (event, profile) pairs newest first; neither commit nor rollback
- **Rules:** `list_events` R1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O.
2. E1 = ev(O, "created", 1), but `performed_by U2.id`.
3. E2 = ev(O, "updated", 2).
4. X (after the commit point).

**When**
- spies: `result = svc.list_events(db, to_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `[e.id for e, _ in result] == [E2.id, E1.id]`.
2. returns: `result[0][1] is None`, `result[1][1].id == U2.id`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.

### TOS-LA-01 — `list_approvers` returns (approver, profile, position); neither commit nor rollback
- **Rules:** `list_approvers` R1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O.
2. A2 = apr(O, U2, 2). 3. A1 = apr(O, U1, 1).
4. X (after the commit point).

**When**
- spies: `result = svc.list_approvers(db, to_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `[(a.id, p.id, pos) for a, p, pos in result] == [(A1.id, U1.id, "Store Manager"), (A2.id, U2.id, "Factory Head")]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### TOS-AS-01 — `approval_summary_for` returns (approved, required, met); neither commit nor rollback
- **Rules:** `approval_summary_for` R2; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O.
2. apr(O, U1, 1), but approved. 3. apr(O, U2, 2).
4. X (after the commit point).

**When**
- spies: `result = svc.approval_summary_for(db, to_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `tuple(result) == (1, 2, False)`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### TOS-AS-02 — another workspace's order: 404; neither commit nor rollback, pending changes stay
- **Rules:** `approval_summary_for` R1; TC6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order O.
2. Z = order O9.
3. X (after the commit point).

**When**
- `with pytest.raises(HTTPException) as exc:` around spies around `svc.approval_summary_for(db, to_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Transfer order with ID {Z.id} not found"`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.

### TOS-AS-03 — an order of W0 (lower id): 404; neither commit nor rollback, pending changes stay
- **Rules:** `approval_summary_for` R1; TC6; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = order O0.
2. O = order O.
3. X (after the commit point).

**When**
- `with pytest.raises(HTTPException) as exc:` around spies around `svc.approval_summary_for(db, to_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Transfer order with ID {Z.id} not found"`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.

## `TransferOrderService.add_approver`

### TOS-AA-01 — a new approver on a ready order is committed and gets "assigned · ready" with the new count
- **Rules:** `add_approver` R1, R2a, R2b; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O. 2. line(O, 1). 3. apr(O, U1, 1).

**When**
- `result = svc.add_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. returns: `loaded(result)`.
2. returns: `isinstance(result, TransferOrderApprover)`, `result.user_id == U2.id`, `result.approved is False`.
3. committed: the approver row `result.id` exists with `assigned_by == U1.id`.
4. committed: `types(O) == ["approver_added"]`.
5. committed: `notes(O) == [("approval_assigned", U2.id, U1.id, "approver", result.id, "Assigned by Karim Ahmed · ready for your approval · 0 of 2 approval(s) collected")]`.

### TOS-AA-02 — ready order: every other pending approver gets "approval pending", the actor does not
- **Rules:** `add_approver` R2b
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order O. 2. line(O, 1). 3. apr(O, U1, 1). 4. apr(O, U3, 2).

**When**
- `result = svc.add_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. returns: `result.user_id == U2.id`.
2. committed: `notes(O) == [("approval_assigned", U2.id, U1.id, "approver", result.id, "Assigned by Karim Ahmed · ready for your approval · 0 of 3 approval(s) collected"), ("approval_pending", U3.id, U1.id, "order", O.id, PEND(0, 3))]`.

### TOS-AA-03 — not ready: the new approver gets "assigned on TO-<id>" and the creator gets "confirm sections"
- **Rules:** `add_approver` R2a, R2c
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order O (no line). 2. apr(O, U1, 1).

**When**
- `result = svc.add_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U3.id)`.

**Then**
1. returns: `result.user_id == U2.id`.
2. committed: `notes(O) == [("approval_assigned", U2.id, U3.id, "approver", result.id, f"Assigned by Rahim Uddin on TO-{O.id}"), ("section_confirm", U1.id, U3.id, "section", O.id, GAP_ITEM)]`.

### TOS-AA-04 — a user who is not an active member: 400, rolled back, no notification
- **Rules:** `add_approver` R3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. line(O, 1). 3. apr(O, U1, 1).
4. X (after the commit point).

**When**
- `svc.add_approver(db, to_id=O.id, user_id=U4.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.
4. nothing written: nothing written.
5. committed: x_gone.

### TOS-AA-05 — already an approver: 409, rolled back
- **Rules:** `add_approver` R3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. apr(O, U1, 1). 3. apr(O, U2, 2).
4. X (after the commit point).

**When**
- `svc.add_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "User is already an approver for this order"`.
4. nothing written: nothing written.
5. committed: x_gone.

### TOS-AA-06 — a failing commit rolls back the row, its event and the notifications
- **Rules:** `add_approver` R4; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. line(O, 1). 3. apr(O, U1, 1).

**When**
- inside **failing commit**: `svc.add_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `notes(O) == []`.
4. nothing written: nothing written.

### TOS-AA-07 — a failing re-read after the commit leaves the approver saved
- **Rules:** `add_approver` R4; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. apr(O, U1, 1).

**When**
- inside **failing refresh**: `svc.add_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: approver rows of O with `user_id == U2.id`: exactly 1.

### TOS-AA-08 — pass-through BUG-2897: a completed order refuses a new approver, nothing sent
- **Rules:** `add_approver` R1, R3 [BUG-2897]
- **Kind:** bug
- **Expect:** xfail BUG-2897
- **Fails today on:** Then 1 (no error is raised: the approver is added)

**Given**
1. O = order O, but completed. 2. line(O, 1). 3. apr(O, U1, 1), but approved.

**When**
- `svc.add_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Transfer order is complete"`.
4. nothing written: nothing written.

### TOS-AA-09 — ready order: an approver who already approved gets no "approval pending"
- **Rules:** `add_approver` R2a, R2b
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order O. 2. line(O, 1).
3. apr(O, U1, 1), but approved. 4. apr(O, U3, 2).

**When**
- `result = svc.add_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. returns: `result.user_id == U2.id`.
2. committed: `notes(O) == [("approval_assigned", U2.id, U2.id, "approver", result.id, "Assigned by Nadia Islam · ready for your approval · 1 of 3 approval(s) collected"), ("approval_pending", U3.id, U2.id, "order", O.id, PEND(1, 3))]`.

### TOS-AA-10 — a raise while notifying rolls back the approver, its event, the helper's writes and other pending changes
- **Rules:** `add_approver` R3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. line(O, 1). 3. apr(O, U1, 1).
4. X (after the commit point).

**When**
- inside NA: `with pytest.raises(RuntimeError) as exc:` around `svc.add_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. raises: `str(exc.value) == "notify boom"`.
2. mock called: `nh.call_count == 1`.
3. session: usable.
4. count: approver rows of O with `user_id == U2.id`: 0.
5. count: `types(O) == []`.
6. count: `notes(O) == []`.
7. nothing written: nothing written.
8. committed: x_gone.

## `TransferOrderService.remove_approver`

### TOS-RA-01 — a removal is committed with the performer; no notice although approvals become met
- **Rules:** `remove_approver` R1, R2; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O. 2. line(O, 1).
3. apr(O, U1, 1), but approved. 4. apr(O, U2, 2).

**When**
- `result = svc.remove_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, performed_by=U1.id)`.

**Then**
1. returns: `result is None`.
2. committed: approver rows of O with `user_id == U2.id`: 0.
3. committed: the one `approver_removed` event of O has `performed_by == U1.id`.
4. committed: `notes(O) == []`.

### TOS-RA-02 — without `performed_by` the event has no performer
- **Rules:** `remove_approver` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order O. 2. apr(O, U1, 1). 3. apr(O, U2, 2).

**When**
- `svc.remove_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. committed: the one `approver_removed` event of O has `performed_by is None`.

### TOS-RA-03 — no such approver: 404, rolled back
- **Rules:** `remove_approver` R3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. apr(O, U1, 1).
3. X (after the commit point).

**When**
- `svc.remove_approver(db, to_id=O.id, user_id=U3.id, workspace_id=W1.id, performed_by=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Approver not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. nothing written: nothing written.
6. committed: x_gone.

### TOS-RA-04 — a failing commit keeps the approver
- **Rules:** `remove_approver` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. apr(O, U1, 1). 3. A2 = apr(O, U2, 2).

**When**
- inside **failing commit**: `svc.remove_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, performed_by=U1.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(A2).
4. nothing written: nothing written.

### TOS-RA-05 — pass-through BUG-2897: a completed order refuses the removal
- **Rules:** `remove_approver` R3 [BUG-2897]
- **Kind:** bug
- **Expect:** xfail BUG-2897
- **Fails today on:** Then 1 (no error is raised: the approver is removed)

**Given**
1. O = order O, but completed. 2. apr(O, U1, 1), but approved. 3. A2 = apr(O, U2, 2).

**When**
- `svc.remove_approver(db, to_id=O.id, user_id=U2.id, workspace_id=W1.id, performed_by=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Transfer order is complete"`.
4. unchanged: unchanged(A2).
5. nothing written: nothing written.

## `TransferOrderService.set_approval`

### TOS-SA-01 — approving is committed and the row returned re-read; no notice when approvals become met
- **Rules:** `set_approval` R1, R2; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O. 2. line(O, 1). 3. A1 = apr(O, U1, 1).

**When**
- `result = svc.set_approval(db, to_id=O.id, user_id=U1.id, workspace_id=W1.id, approved=True)`.

**Then**
1. returns: `loaded(result)`.
2. returns: `result.id == A1.id`, `result.approved is True`.
3. committed: re-read A1: `approved is True`, `approved_at == NOW`.
4. committed: `types(O) == ["approved"]`.
5. committed: `notes(O) == []`.

### TOS-SA-02 — withdrawing is committed; no notice
- **Rules:** `set_approval` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order O. 2. line(O, 1). 3. A1 = apr(O, U1, 1), but approved.

**When**
- `result = svc.set_approval(db, to_id=O.id, user_id=U1.id, workspace_id=W1.id, approved=False)`.

**Then**
1. returns: `result.approved is False`.
2. committed: re-read A1: `approved is False`, `approved_at is None`.
3. committed: `notes(O) == []`.

### TOS-SA-03 — not an approver: 403, rolled back
- **Rules:** `set_approval` R3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. line(O, 1). 3. apr(O, U1, 1).
4. X (after the commit point).

**When**
- `svc.set_approval(db, to_id=O.id, user_id=U3.id, workspace_id=W1.id, approved=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "You are not an assigned approver for this order"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. nothing written: nothing written.
6. committed: x_gone.

### TOS-SA-04 — approving an order with no line: 400, rolled back
- **Rules:** `set_approval` R3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. A1 = apr(O, U1, 1).
3. X (after the commit point).

**When**
- `svc.set_approval(db, to_id=O.id, user_id=U1.id, workspace_id=W1.id, approved=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Add at least one item before approving"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(A1).
6. nothing written: nothing written.
7. committed: x_gone.

### TOS-SA-05 — a failing commit keeps the approval unset
- **Rules:** `set_approval` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. line(O, 1). 3. A1 = apr(O, U1, 1).

**When**
- inside **failing commit**: `svc.set_approval(db, to_id=O.id, user_id=U1.id, workspace_id=W1.id, approved=True)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(A1).
4. nothing written: nothing written.

### TOS-SA-06 — a failing re-read after the commit leaves the approval saved
- **Rules:** `set_approval` R3; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order O. 2. line(O, 1). 3. A1 = apr(O, U1, 1).

**When**
- inside **failing refresh**: `svc.set_approval(db, to_id=O.id, user_id=U1.id, workspace_id=W1.id, approved=True)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: re-read A1: `approved is True`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `update_transfer_order` R2a, `add_item` R2a [BUG-3142] — the race itself | integration tests | two sessions editing one order at once: the second waits, sees "ready" and sends no second `approval_pending` |
| every passed-on `HTTPException` | `/transfer-orders/` endpoint tests | the HTTP status code and body |
| `list_transfer_orders` R2 | `GET /transfer-orders/` | `skip >= 0`, `1 <= limit <= 100`, query defaults (`limit` 50, `exclude_complete` false) |
| `delete_transfer_order`, `remove_item`, `remove_approver` | endpoint tests | 204 responses |
| `delete_transfer_order` R3 [BUG-1194] | `DELETE /transfer-orders/{id}/` | the endpoint passes the current user |
| `set_approval` R1 | endpoint tests | the caller is passed as `user_id` |
| manager rules R1–R9 cited by every write | `transfer_order_manager.cases.md` | events, guards, locks (BUG-2892, BUG-821), numbering |
| hub filters, order and highlights (BUG-2654 … BUG-2660) | `dao/transfer_order.cases.md` | filter semantics and sort order |
| DTO mapping | `order_hub_stats_helpers.cases.md` | `transfer_order_to_recent_summary`, `pending_highlight_from_dict` |

## Spec gaps
All Revision 1 gaps are closed by the spec's Gap log (2026-11-22). None is open. Revision 3 adds no gap: the executor note on HF-01…04 (instance method, call through `svc`) needed no spec change. Revision 4 adds none either: verifier findings 1–6 are all case-missing, and the spec already states every rule they test (TC3, HR-16, `_hub_filter_kwargs` R2 / R3, hub R1, R2a, R1).

| # | Where | Resolution | Cards changed |
|---|---|---|---|
| 1 | `update_transfer_order` R2a, `add_item` R2a | G1 (fact, verified): the clause is exactly `FOR UPDATE OF transfer_orders` on the pre-read, before the first `transfer_order_items` SELECT; a bare `FOR UPDATE` is refused by Postgres on this outer-joined get. | "lock first" pins the `OF transfer_orders` form and forbids `NOWAIT` / `SKIP LOCKED`; U-13, AI-11 tightened. |
| 2 | `update_transfer_order` R1a, `add_item` R1, `approval_summary_for` R1 | G2 (fact): the update / add-item pre-read 404 is inside the `try` and rolls back pending changes; `approval_summary_for` has no `try`, so its 404 leaves them pending. | U-01, U-02, AI-06 add X + x_gone; AS-02 adds spies (no commit, no rollback) and `X in db`. |
| 3 | `update_transfer_order` R6, `add_item` R5, `add_approver` R3 | G3: patch `app.services.transfer_order_service.handle_order_update_notifications` / `handle_add_approver`. | New U-18, AI-13, AA-10 (NU / NA with NPROBE). |
| 4 | `update_transfer_order` R4b | G4 (decided under delegation): R4b stays a pass-through pointer; its card retires when BUG-2899 is fixed; no replacement card. | U-11 keeps its tag and now states the reason; no new card. |
| 5 | `update_transfer_order` R4a | G5 (fact): every approver is pending whenever R4a fires through this method; the approved branch is covered by `add_approver` R2b and the helper spec. | None (AA-09 already covers it). |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_transfer_order` | R1 | TOS-C-01 |
| | R2 | TOS-C-03, C-04, C-05 |
| | R3 | TOS-C-02 |
| | R4 (TC4, TC5) | TOS-C-06, C-07 |
| `update_transfer_order` | R1 | TOS-U-01, U-02, U-19 |
| | R1a (TC3) | TOS-U-01, U-02, U-19 |
| | R2 | TOS-U-04, U-07 |
| | R2a [BUG-3142] | TOS-U-13 |
| | R3 | TOS-U-03; pass-through U-12 [BUG-2899], U-14 [BUG-2903] |
| | R4a | TOS-U-04, U-05 |
| | R4b | TOS-U-11 |
| | R4c | TOS-U-06, U-07, U-08 |
| | R5 | TOS-U-09, U-14 |
| | R6 | TOS-U-10, U-15, U-16, U-18 |
| | R7 (TC4, TC5) | TOS-U-16, U-17 |
| `get_transfer_order` | R1, TC6 | TOS-G-01, G-02, G-03 |
| `list_transfer_orders` | R1 | TOS-LT-01, LT-02 |
| | R2 | TOS-LT-01 |
| | R3 | TOS-LT-03 |
| `_hub_filter_kwargs` | R1 | TOS-HF-01, HF-02 |
| | R2 | TOS-HF-02, HF-03, HF-04, HF-05, LP-04, HS-05 |
| | R3 | TOS-HF-02, LP-01, HS-02 |
| `list_transfer_orders_page` | R1 | TOS-LP-01, LP-03, LP-04 |
| | R2 | TOS-LP-01, LP-02, LP-07 |
| | R3 | TOS-LP-02, LP-05, LP-06, LP-07 |
| | R4 | TOS-LP-01 |
| `get_transfer_order_hub_stats` | R1 | TOS-HS-02, HS-05 |
| | R2 | TOS-HS-01, HS-02, HS-04 |
| | R3 | TOS-HS-01, HS-03, HS-04 |
| | R4 | TOS-HS-01, HS-02, HS-04 |
| | R5 | TOS-HS-01 |
| `delete_transfer_order` | R1 | TOS-D-01 |
| | R2 | TOS-D-02, D-03 |
| | R3 [BUG-1194] | TOS-D-05, D-06 |
| | R4 | TOS-D-01, D-04 |
| `mark_order_complete` | R1 | TOS-MC-01 |
| | R2 | TOS-MC-02 |
| | R3 | TOS-MC-03, MC-04, MC-05, MC-06 |
| | R4 | TOS-MC-01 |
| | R5 (TC4, TC5) | TOS-MC-07, MC-08 |
| `add_item` | R1 (TC3) | TOS-AI-06, AI-14 |
| | R2 | TOS-AI-02, AI-04 |
| | R2a [BUG-3142] | TOS-AI-11 |
| | R3 | TOS-AI-01 |
| | R4 | TOS-AI-02, AI-03, AI-04, AI-05 |
| | R5 | TOS-AI-07, AI-08, AI-09, AI-10, AI-13 |
| | R6 (TC4, TC5) | TOS-AI-10, AI-12 |
| `update_item` | R1 | TOS-UI-01 |
| | R2 | TOS-UI-01 |
| | R3 | TOS-UI-02, UI-03, UI-04, UI-05 |
| `remove_item` | R1 | TOS-RI-01 |
| | R2 | TOS-RI-01 |
| | R3 | TOS-RI-01, RI-02 |
| | R4 | TOS-RI-03, RI-04, RI-05 |
| `get_items` | R1 | TOS-GI-01 |
| `list_events` | R1 | TOS-LE-01 |
| `list_approvers` | R1 | TOS-LA-01 |
| `approval_summary_for` | R1 (TC6) | TOS-AS-02, AS-03 |
| | R2 | TOS-AS-01 |
| `add_approver` | R1 | TOS-AA-01; pass-through AA-08 [BUG-2897] |
| | R2a | TOS-AA-01, AA-03, AA-09 |
| | R2b | TOS-AA-01, AA-02, AA-09 |
| | R2c | TOS-AA-03 |
| | R3 | TOS-AA-04, AA-05, AA-08, AA-10 |
| | R4 (TC4, TC5) | TOS-AA-06, AA-07 |
| `remove_approver` | R1 | TOS-RA-01, RA-02 |
| | R2 | TOS-RA-01 |
| | R3 | TOS-RA-03, RA-04; pass-through RA-05 [BUG-2897] |
| `set_approval` | R1 | TOS-SA-01, SA-02 |
| | R2 | TOS-SA-01, SA-02 |
| | R3 | TOS-SA-03, SA-04, SA-05, SA-06 |
